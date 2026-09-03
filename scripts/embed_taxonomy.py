#!/usr/bin/env python3
"""Build a bounded, resumable embedding cache for the proposed V1 taxonomy."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown, read_json
from translate import load_secret


API_URL = "https://api.mistral.ai/v1/embeddings"
CONFIG_PATH = ROOT / "config" / "taxonomy-v1.yaml"
CACHE_DIR = ROOT / "data" / "embeddings" / "v1"
BATCH_DIR = CACHE_DIR / "batches"
REPORT_PATH = ROOT / "data" / "reports" / "taxonomy-v1-embedding-progress.json"
INPUT_QUALITY_REPORT_PATH = ROOT / "data" / "reports" / "taxonomy-v1-input-quality.json"
CHECKPOINT_PATH = ROOT / "data" / "checkpoints" / "taxonomy-v1-state.json"
TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Configuration must be an object: {path}")
    return value


def load_config() -> dict[str, Any]:
    config = load_yaml(CONFIG_PATH)
    embedding = config.get("embedding")
    execution = config.get("execution")
    if (
        config.get("schemaVersion") != 1
        or not isinstance(embedding, dict)
        or not isinstance(execution, dict)
    ):
        raise ValueError(f"Unsupported taxonomy configuration: {CONFIG_PATH}")
    required = {
        "model",
        "dimensions",
        "recipeVersion",
        "contextCharacters",
        "modelMaxInputTokens",
        "priceUsdPerMillionInputTokens",
        "priceSource",
    }
    missing = required - set(embedding)
    if missing:
        raise ValueError(f"Taxonomy configuration lacks: {sorted(missing)}")
    required_execution = {
        "maxDocumentsPerRequest",
        "billingMode",
        "enforceReferenceCostLimit",
        "maxReferenceCostUsdPerRequest",
    }
    missing_execution = required_execution - set(execution)
    if missing_execution:
        raise ValueError(f"Taxonomy execution configuration lacks: {sorted(missing_execution)}")
    if int(execution["maxDocumentsPerRequest"]) < 1:
        raise ValueError("maxDocumentsPerRequest must be positive")
    if execution["billingMode"] not in {"experimental-no-charge", "metered"}:
        raise ValueError("Unsupported taxonomy billingMode")
    if float(execution["maxReferenceCostUsdPerRequest"]) <= 0:
        raise ValueError("maxReferenceCostUsdPerRequest must be positive")
    return config


def normalize_context(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def prepare_context(body: str, recipe_version: str) -> str:
    if recipe_version == "activity-context-v1":
        return normalize_context(body)
    if recipe_version != "activity-context-v2":
        raise ValueError(f"Unsupported embedding recipe: {recipe_version}")

    footer = re.search(r"\n---\s*\n+\*Źródło skanu:", body)
    if footer:
        body = body[: footer.start()]
    body = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", body)
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
    body = re.sub(r"https?://\S+", "", body)
    return normalize_context(body)


def build_embedding_input(
    metadata: dict[str, Any],
    body: str,
    context_characters: int,
    recipe_version: str,
) -> str:
    source_traits = metadata.get("traits") or []
    traits_text = " | ".join(str(item).strip() for item in source_traits) or "[brak cech w źródle]"
    context = prepare_context(body, recipe_version)[:context_characters].rstrip()
    kinds = " | ".join(metadata.get("kinds") or [])
    return "\n".join(
        [
            f"id: {metadata['id']}",
            f"rodzaj: {kinds}",
            f"tytuł: {metadata['title']}",
            f"dział: {metadata.get('section', '')}",
            f"cechy źródłowe: {traits_text}",
            f"kontekst: {context}",
        ]
    )


def input_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def estimated_tokens(value: str) -> int:
    # A conservative preflight estimate for UTF-8 Polish text. The API usage is authoritative.
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


def cache_is_current(path: Path, *, activity_id: str, model: str, recipe_version: str, expected_hash: str, dimensions: int) -> bool:
    if not path.exists():
        return False
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    vector = payload.get("vector")
    return (
        payload.get("schemaVersion") == 1
        and payload.get("activityId") == activity_id
        and payload.get("modelRequested") == model
        and payload.get("recipeVersion") == recipe_version
        and payload.get("inputHash") == expected_hash
        and payload.get("dimensions") == dimensions
        and isinstance(vector, list)
        and len(vector) == dimensions
        and all(isinstance(value, (int, float)) for value in vector)
    )


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def update_checkpoint(
    updates: dict[str, Any], *, remove_keys: tuple[str, ...] = (), path: Path | None = None
) -> dict[str, Any]:
    target = path or CHECKPOINT_PATH
    checkpoint = read_json(target) if target.exists() else {}
    for key in remove_keys:
        checkpoint.pop(key, None)
    checkpoint.update({"schemaVersion": 1, "pipeline": "taxonomy-v1-embeddings", **updates})
    atomic_write_json(target, checkpoint)
    return checkpoint


def retry_at(now: datetime, retry_after: str | None) -> datetime:
    minimum = now + timedelta(hours=12)
    if not retry_after:
        return minimum
    try:
        candidate = now + timedelta(seconds=max(0, int(retry_after)))
    except ValueError:
        try:
            candidate = parsedate_to_datetime(retry_after)
            if candidate.tzinfo is None:
                candidate = candidate.replace(tzinfo=UTC)
            candidate = candidate.astimezone(UTC)
        except (TypeError, ValueError, OverflowError):
            return minimum
    return max(minimum, candidate)


def batch_reference_cost(batch: dict[str, Any], fallback_price_per_million_tokens: float) -> float:
    usage = batch.get("usage", {})
    stored_cost = usage.get("referenceCostUsd", usage.get("estimatedCostUsd"))
    if stored_cost is not None:
        return float(stored_cost)
    return int(usage.get("promptTokens", 0)) * fallback_price_per_million_tokens / 1_000_000


def summarize_batch_usage(
    batches: list[dict[str, Any]], price_per_million_tokens: float
) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for batch in batches:
        recipe_version = str(batch.get("recipeVersion", "unknown"))
        group = groups.setdefault(
            recipe_version,
            {
                "recipeVersion": recipe_version,
                "batchIds": [],
                "documents": 0,
                "promptTokens": 0,
                "billedCostUsd": 0.0,
                "referenceCostUsd": 0.0,
                "_billedCostKnown": True,
            },
        )
        group["batchIds"].append(str(batch["batchId"]))
        group["documents"] += len(batch.get("activityIds", []))
        group["promptTokens"] += int(batch.get("usage", {}).get("promptTokens", 0))
        billed_cost = batch.get("usage", {}).get("billedCostUsd")
        if billed_cost is None:
            group["_billedCostKnown"] = False
        else:
            group["billedCostUsd"] += float(billed_cost)
        group["referenceCostUsd"] += batch_reference_cost(
            batch, price_per_million_tokens
        )
    by_recipe = []
    for recipe_version in sorted(groups):
        group = groups[recipe_version]
        group["batchIds"].sort()
        group["billedCostUsd"] = (
            round(group["billedCostUsd"], 8) if group.pop("_billedCostKnown") else None
        )
        group["referenceCostUsd"] = round(group["referenceCostUsd"], 8)
        by_recipe.append(group)
    prompt_tokens = sum(group["promptTokens"] for group in by_recipe)
    billed_cost = (
        sum(group["billedCostUsd"] for group in by_recipe)
        if all(group["billedCostUsd"] is not None for group in by_recipe)
        else None
    )
    reference_cost = sum(group["referenceCostUsd"] for group in by_recipe)
    return {
        "documentsProcessed": sum(group["documents"] for group in by_recipe),
        "promptTokens": prompt_tokens,
        "billedCostUsd": round(billed_cost, 8) if billed_cost is not None else None,
        "referenceCostUsd": round(reference_cost, 8),
        "byRecipe": by_recipe,
    }


def checkpoint_identity(embedding: dict[str, Any]) -> dict[str, Any]:
    return {
        "modelRequested": str(embedding["model"]),
        "recipeVersion": str(embedding["recipeVersion"]),
        "dimensions": int(embedding["dimensions"]),
    }


def recipe_execution_block_reason(
    embedding: dict[str, Any], input_quality_report: dict[str, Any] | None
) -> str | None:
    if not input_quality_report or input_quality_report.get("status") != "recipe-upgrade-pending":
        return None
    configured_recipe = str(embedding["recipeVersion"])
    audited_active_recipe = str(input_quality_report.get("activeRecipeVersion", ""))
    candidate_recipe = str(input_quality_report.get("candidateRecipeVersion", ""))
    if configured_recipe == audited_active_recipe and candidate_recipe != configured_recipe:
        return (
            f"input-quality audit requires recipe upgrade from {configured_recipe} "
            f"to {candidate_recipe} before API execution"
        )
    return None


def pending_recipe_migration_ids(
    embedding: dict[str, Any],
    input_quality_report: dict[str, Any] | None,
    current_ids: set[str],
) -> list[str]:
    if not input_quality_report:
        return []
    candidate_recipe = str(input_quality_report.get("candidateRecipeVersion", ""))
    if str(embedding["recipeVersion"]) != candidate_recipe:
        return []
    remediation = input_quality_report.get("remediation", {})
    required_ids = remediation.get("reembedBeforeNewActivities", [])
    if not isinstance(required_ids, list):
        raise ValueError("input-quality remediation IDs must be a list")
    return sorted(str(activity_id) for activity_id in required_ids if str(activity_id) not in current_ids)


def restrict_to_recipe_migration(
    pending: list[dict[str, Any]], migration_ids: list[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    if not migration_ids:
        return pending, []
    allowed = set(migration_ids)
    selected_pool = [item for item in pending if item["id"] in allowed]
    deferred_ids = [item["id"] for item in pending if item["id"] not in allowed]
    return selected_pool, deferred_ids


def restrict_to_current_source(
    pending: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not pending:
        return [], []
    source_id = pending[0]["sourceId"]
    return (
        [item for item in pending if item["sourceId"] == source_id],
        [item for item in pending if item["sourceId"] != source_id],
    )


def write_retry_checkpoint(
    *,
    now: datetime,
    reason: str,
    identity: dict[str, Any],
    retry_after: str | None = None,
) -> None:
    update_checkpoint(
        {
            "status": "retry-pending",
            "reason": reason,
            "nextRetryAt": retry_at(now, retry_after).isoformat(),
            **identity,
        },
        remove_keys=("nextCycleAt",),
    )


def request_embeddings(
    api_key: str,
    model: str,
    inputs: list[str],
    *,
    identity: dict[str, Any],
) -> dict[str, Any]:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps({"model": model, "input": inputs}).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    now = datetime.now(UTC)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code in TRANSIENT_HTTP_CODES:
            write_retry_checkpoint(
                now=now,
                reason=f"mistral-http-{error.code}",
                retry_after=error.headers.get("Retry-After"),
                identity=identity,
            )
            raise RuntimeError(f"Transient Mistral HTTP {error.code}; checkpoint saved") from error
        update_checkpoint(
            {
                "status": "failed-permanent",
                "reason": f"mistral-http-{error.code}",
                **identity,
            },
            remove_keys=("nextCycleAt", "nextRetryAt"),
        )
        raise RuntimeError(f"Permanent Mistral HTTP {error.code}; checkpoint saved") from error
    except (urllib.error.URLError, TimeoutError) as error:
        write_retry_checkpoint(now=now, reason="mistral-network-unavailable", identity=identity)
        raise RuntimeError("Transient Mistral network failure; checkpoint saved") from error


def activity_items(config: dict[str, Any]) -> list[dict[str, Any]]:
    embedding = config["embedding"]
    items: list[dict[str, Any]] = []
    for path in sorted((VAULT / "activities").glob("*.md")):
        metadata, body = load_markdown(path)
        text = build_embedding_input(
            metadata,
            body,
            int(embedding["contextCharacters"]),
            embedding["recipeVersion"],
        )
        items.append(
            {
                "id": metadata["id"],
                "sourceId": metadata["sourceId"],
                "sourceTraits": metadata.get("traits") or [],
                "input": text,
                "inputHash": input_hash(text),
                "cachePath": CACHE_DIR / f"{metadata['id']}.json",
            }
        )
    return items


def current_items(items: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    embedding = config["embedding"]
    return [
        item
        for item in items
        if cache_is_current(
            item["cachePath"],
            activity_id=item["id"],
            model=embedding["model"],
            recipe_version=embedding["recipeVersion"],
            expected_hash=item["inputHash"],
            dimensions=int(embedding["dimensions"]),
        )
    ]


def recover_cached_items(config: dict[str, Any], items: list[dict[str, Any]]) -> int:
    embedding = config["embedding"]
    expected_by_id = {item["id"]: item for item in items}
    recovered = 0
    for batch_path in sorted(BATCH_DIR.glob("*.json")):
        batch = read_json(batch_path)
        batch_items = batch.get("items", [])
        for payload in batch_items:
            expected = expected_by_id.get(payload.get("activityId"))
            if not expected:
                continue
            if (
                payload.get("modelRequested") != embedding["model"]
                or payload.get("recipeVersion") != embedding["recipeVersion"]
                or payload.get("inputHash") != expected["inputHash"]
                or payload.get("dimensions") != int(embedding["dimensions"])
            ):
                continue
            if not cache_is_current(
                expected["cachePath"],
                activity_id=expected["id"],
                model=embedding["model"],
                recipe_version=embedding["recipeVersion"],
                expected_hash=expected["inputHash"],
                dimensions=int(embedding["dimensions"]),
            ):
                atomic_write_json(expected["cachePath"], payload)
                recovered += 1
        if batch_items and all(
            (expected := expected_by_id.get(payload.get("activityId")))
            and cache_is_current(
                expected["cachePath"],
                activity_id=expected["id"],
                model=embedding["model"],
                recipe_version=embedding["recipeVersion"],
                expected_hash=expected["inputHash"],
                dimensions=int(embedding["dimensions"]),
            )
            for payload in batch_items
        ):
            del batch["items"]
            atomic_write_json(batch_path, batch)
    return recovered


def build_progress_report(
    config: dict[str, Any], items: list[dict[str, Any]], *, generated_at: str
) -> dict[str, Any]:
    embedding = config["embedding"]
    execution = config["execution"]
    current = current_items(items, config)
    batch_paths = sorted(BATCH_DIR.glob("*.json"))
    batches = [read_json(path) for path in batch_paths]
    usage = summarize_batch_usage(batches, float(embedding["priceUsdPerMillionInputTokens"]))
    return {
        "schemaVersion": 1,
        "pipeline": "taxonomy-v1-embeddings",
        "status": "complete" if len(current) == len(items) else "in-progress",
        "generatedAt": generated_at,
        "modelRequested": embedding["model"],
        "dimensions": embedding["dimensions"],
        "recipeVersion": embedding["recipeVersion"],
        "costAccounting": {
            "billingMode": execution["billingMode"],
            "referencePriceUsdPerMillionInputTokens": embedding["priceUsdPerMillionInputTokens"],
            "referencePriceSource": embedding["priceSource"],
        },
        "activities": {"total": len(items), "cached": len(current), "remaining": len(items) - len(current)},
        "usage": usage,
        "batchIds": sorted(str(batch["batchId"]) for batch in batches),
        "cachedActivityIds": [item["id"] for item in current],
    }


def write_progress_report(
    config: dict[str, Any], items: list[dict[str, Any]], *, generated_at: str
) -> dict[str, Any]:
    report = build_progress_report(config, items, generated_at=generated_at)
    atomic_write_json(REPORT_PATH, report)
    return report


def main() -> None:
    config = load_config()
    embedding = config["embedding"]
    execution = config["execution"]
    identity = {**checkpoint_identity(embedding), "billingMode": execution["billingMode"]}

    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Send the planned bounded batch to Mistral")
    parser.add_argument("--limit", type=int, default=int(execution["maxDocumentsPerRequest"]))
    parser.add_argument("--ids", nargs="*")
    args = parser.parse_args()

    request_document_limit = int(execution["maxDocumentsPerRequest"])
    billing_mode = str(execution["billingMode"])
    enforce_reference_cost_limit = bool(execution["enforceReferenceCostLimit"])
    max_reference_cost = float(execution["maxReferenceCostUsdPerRequest"])
    if args.limit < 1 or args.limit > request_document_limit:
        raise SystemExit(f"limit must be between 1 and {request_document_limit}")

    all_items = activity_items(config)
    recovered = recover_cached_items(config, all_items)
    items = all_items
    if args.ids:
        wanted = set(args.ids)
        unknown = wanted - {item["id"] for item in all_items}
        if unknown:
            raise SystemExit(f"unknown activity IDs: {sorted(unknown)}")
        items = [item for item in all_items if item["id"] in wanted]

    input_quality_report = (
        read_json(INPUT_QUALITY_REPORT_PATH) if INPUT_QUALITY_REPORT_PATH.exists() else None
    )
    execution_block_reason = recipe_execution_block_reason(embedding, input_quality_report)

    current_ids = {item["id"] for item in current_items(all_items, config)}
    requested_pending = [item for item in items if item["id"] not in current_ids]
    migration_ids = pending_recipe_migration_ids(embedding, input_quality_report, current_ids)
    pending, deferred_ids = restrict_to_recipe_migration(requested_pending, migration_ids)
    if migration_ids and requested_pending and not pending and not execution_block_reason:
        execution_block_reason = (
            "recipe migration must finish before requested new activities can be embedded"
        )
    source_pending, other_source_items = restrict_to_current_source(pending)
    selected = source_pending[: args.limit]
    token_estimate = sum(estimated_tokens(item["input"]) for item in selected)
    reference_cost = token_estimate * float(embedding["priceUsdPerMillionInputTokens"]) / 1_000_000
    worst_case_reference_cost = (
        len(selected)
        * int(embedding["modelMaxInputTokens"])
        * float(embedding["priceUsdPerMillionInputTokens"])
        / 1_000_000
    )
    plan = {
        "mode": "execute" if args.execute else "dry-run",
        "model": embedding["model"],
        "selectedIds": [item["id"] for item in selected],
        "alreadyCached": len(current_ids),
        "recoveredFromBatchLedger": recovered,
        "remainingBeforeBatch": len(pending),
        "requestedRemainingBeforeMigrationGate": len(requested_pending),
        "migrationPendingIds": migration_ids,
        "newActivitiesDeferred": len(deferred_ids),
        "nextDeferredActivityId": deferred_ids[0] if deferred_ids else None,
        "activeSourceId": source_pending[0]["sourceId"] if source_pending else None,
        "remainingSourceBeforeBatch": len(source_pending),
        "otherSourcesDeferred": len(other_source_items),
        "nextSourceId": other_source_items[0]["sourceId"] if other_source_items else None,
        "requestDocumentLimit": request_document_limit,
        "estimatedInputTokens": token_estimate,
        "billingMode": billing_mode,
        "billedCostUsd": 0.0 if billing_mode == "experimental-no-charge" else None,
        "referenceCostUsd": round(reference_cost, 8),
        "worstCaseReferenceCostUsd": round(worst_case_reference_cost, 8),
        "referenceCostLimitEnforced": enforce_reference_cost_limit,
        "maxReferenceCostUsdPerRequest": max_reference_cost,
        "executionBlocked": execution_block_reason is not None,
        "executionBlockReason": execution_block_reason,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if enforce_reference_cost_limit and worst_case_reference_cost > max_reference_cost:
        raise SystemExit("planned batch exceeds the reference cost limit")
    if args.execute and execution_block_reason:
        raise SystemExit(execution_block_reason)
    if not args.execute:
        return
    if not selected:
        next_item = next((item for item in all_items if item["id"] not in current_ids), None)
        update_checkpoint(
            {
                "status": "complete" if next_item is None else "selection-complete",
                "cachedActivities": len(current_ids),
                "totalActivities": len(all_items),
                "nextActivityId": next_item["id"] if next_item else None,
                "nextSourceId": next_item["sourceId"] if next_item else None,
                "billingMode": billing_mode,
                "requestDocumentLimit": request_document_limit,
                **identity,
            },
            remove_keys=(
                "dailyUsage",
                "dailyLimits",
                "nextCycleAt",
                "nextRetryAt",
                "reason",
                "documentsProcessedThisCycle",
                "estimatedCostUsdThisCycle",
            ),
        )
        return

    result = request_embeddings(
        load_secret(),
        embedding["model"],
        [item["input"] for item in selected],
        identity=identity,
    )
    vectors_by_index = {entry["index"]: entry["embedding"] for entry in result.get("data", [])}
    if set(vectors_by_index) != set(range(len(selected))):
        raise RuntimeError("Mistral response indexes do not match the request")
    dimensions = int(embedding["dimensions"])
    for vector in vectors_by_index.values():
        if not isinstance(vector, list) or len(vector) != dimensions or not all(isinstance(value, (int, float)) for value in vector):
            raise RuntimeError(f"Mistral returned an invalid embedding; expected {dimensions} numeric values")

    now = datetime.now(UTC)
    generated_at = now.isoformat()
    batch_id = now.strftime("%Y%m%dT%H%M%S%fZ")
    actual_model = result.get("model", embedding["model"])
    usage = result.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens", usage.get("total_tokens", token_estimate)))
    actual_reference_cost = (
        prompt_tokens * float(embedding["priceUsdPerMillionInputTokens"]) / 1_000_000
    )
    billed_cost = 0.0 if billing_mode == "experimental-no-charge" else None
    cache_payloads = []
    for index, item in enumerate(selected):
        cache_payloads.append(
            {
                "schemaVersion": 1,
                "activityId": item["id"],
                "sourceId": item["sourceId"],
                "sourceTraits": item["sourceTraits"],
                "modelRequested": embedding["model"],
                "model": actual_model,
                "dimensions": dimensions,
                "recipeVersion": embedding["recipeVersion"],
                "inputHash": item["inputHash"],
                "input": item["input"],
                "generatedAt": generated_at,
                "batchId": batch_id,
                "vector": vectors_by_index[index],
            }
        )
    batch = {
        "schemaVersion": 1,
        "batchId": batch_id,
        "generatedAt": generated_at,
        "modelRequested": embedding["model"],
        "model": actual_model,
        "recipeVersion": embedding["recipeVersion"],
        "sourceId": selected[0]["sourceId"],
        "billingMode": billing_mode,
        "referencePriceUsdPerMillionInputTokens": embedding["priceUsdPerMillionInputTokens"],
        "referencePriceSource": embedding["priceSource"],
        "activityIds": [item["id"] for item in selected],
        "usage": {
            "promptTokens": prompt_tokens,
            "billedCostUsd": billed_cost,
            "referenceCostUsd": round(actual_reference_cost, 8),
        },
        "items": cache_payloads,
    }
    atomic_write_json(BATCH_DIR / f"{batch_id}.json", batch)
    for item, payload in zip(selected, cache_payloads, strict=True):
        atomic_write_json(item["cachePath"], payload)
    del batch["items"]
    atomic_write_json(BATCH_DIR / f"{batch_id}.json", batch)

    report = write_progress_report(config, activity_items(config), generated_at=generated_at)
    refreshed_items = activity_items(config)
    current_after = set(report["cachedActivityIds"])
    next_item = next((item for item in refreshed_items if item["id"] not in current_after), None)
    next_source_item = next(
        (
            item
            for item in refreshed_items
            if item["sourceId"] == selected[0]["sourceId"] and item["id"] not in current_after
        ),
        None,
    )
    status = (
        "complete"
        if next_item is None
        else "source-batch-complete"
        if next_source_item is not None
        else "source-complete"
    )
    update_checkpoint(
        {
            "status": status,
            "lastBatchId": batch_id,
            "lastCompletedAt": generated_at,
            "lastBatchActivityCount": len(selected),
            "lastBatchSourceId": selected[0]["sourceId"],
            "lastBatchPromptTokens": prompt_tokens,
            "lastBatchBilledCostUsd": billed_cost,
            "lastBatchReferenceCostUsd": round(actual_reference_cost, 8),
            "cachedActivities": report["activities"]["cached"],
            "totalActivities": report["activities"]["total"],
            "nextActivityId": next_item["id"] if next_item else None,
            "nextSourceId": next_item["sourceId"] if next_item else None,
            "billingMode": billing_mode,
            "requestDocumentLimit": request_document_limit,
            **identity,
            "model": actual_model,
        },
        remove_keys=(
            "analysis",
            "inputQualityAudit",
            "dailyUsage",
            "dailyLimits",
            "nextCycleAt",
            "nextRetryAt",
            "reason",
            "documentsProcessedThisCycle",
            "estimatedCostUsdThisCycle",
        ),
    )
    print(
        json.dumps(
            {
                "batchId": batch_id,
                "model": actual_model,
                "activityIds": batch["activityIds"],
                "usage": batch["usage"],
                "progress": report["activities"],
                "checkpoint": str(CHECKPOINT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
