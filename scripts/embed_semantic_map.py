#!/usr/bin/env python3
"""Build an isolated, resumable V3 embedding cache for every game."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown, read_json, write_json
from translate import (
    PermanentTranslationError,
    TransientTranslationError,
    ensure_models_available,
    load_secret,
    retry_at_from_headers,
    safe_http_diagnostics,
)


API_URL = "https://api.mistral.ai/v1/embeddings"
CONFIG_PATH = ROOT / "config" / "semantic-map-v3.yaml"
CACHE_DIR = ROOT / "data" / "embeddings" / "v3"
BATCH_DIR = CACHE_DIR / "batches"
REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-v3-embedding-progress.json"
CHECKPOINT_PATH = ROOT / "data" / "checkpoints" / "semantic-map-v3-state.json"
TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    corpus = config.get("corpus") or {}
    embedding = config.get("embedding") or {}
    execution = config.get("execution") or {}
    if config.get("schemaVersion") != 1 or corpus.get("kind") != "game":
        raise ValueError("Unsupported semantic-map V3 configuration")
    source_order = corpus.get("sourceOrder") or []
    if not source_order or len(source_order) != len(set(source_order)):
        raise ValueError("Semantic-map V3 sourceOrder is missing or repeated")
    required_embedding = {
        "model",
        "dimensions",
        "recipeVersion",
        "sourceContextCharacters",
        "parallelContextCharacters",
        "modelMaxInputTokens",
        "priceUsdPerMillionInputTokens",
        "priceSource",
        "priceAccessedOn",
    }
    if required_embedding - set(embedding):
        raise ValueError("Semantic-map V3 embedding configuration is incomplete")
    if embedding["recipeVersion"] != "bilingual-game-context-v1":
        raise ValueError("Unsupported semantic-map V3 embedding recipe")
    if int(embedding["dimensions"]) < 1:
        raise ValueError("Semantic-map V3 dimensions must be positive")
    if min(
        int(embedding["sourceContextCharacters"]),
        int(embedding["parallelContextCharacters"]),
        int(embedding["modelMaxInputTokens"]),
    ) < 1:
        raise ValueError("Semantic-map V3 context and token bounds must be positive")
    if execution.get("billingMode") != "education-credit":
        raise ValueError("New semantic-map V3 requests must use Education credits")
    if execution.get("enforceReferenceCostLimit") is not True:
        raise ValueError("Semantic-map V3 must enforce the reference-cost limit")
    total_limit = float(execution.get("maxTotalReferenceCostUsd", 0))
    if not 0 < total_limit <= 10:
        raise ValueError("Semantic-map V3 reference-cost limit must be at most 10 USD")
    if not 0 < int(execution.get("maxDocumentsPerRequest", 0)) <= 50:
        raise ValueError("Semantic-map V3 request size must be between 1 and 50 documents")
    if execution.get("requireExactModelAccessCheck") is not True:
        raise ValueError("Semantic-map V3 must check exact model access")
    return config


def normalize_context(value: str) -> str:
    value = value.split("\n\n---\n", 1)[0]
    value = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"https?://\S+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def build_embedding_input(
    source_metadata: dict[str, Any],
    source_body: str,
    parallel_metadata: dict[str, Any],
    parallel_body: str,
    embedding: dict[str, Any],
) -> str:
    source_context = normalize_context(source_body)[
        : int(embedding["sourceContextCharacters"])
    ].rstrip()
    parallel_context = normalize_context(parallel_body)[
        : int(embedding["parallelContextCharacters"])
    ].rstrip()
    return "\n".join(
        [
            "task: semantic similarity between historical scouting games",
            f"original-language: {source_metadata['originalLanguage']}",
            f"original-title: {source_metadata['title']}",
            f"original-context: {source_context}",
            f"parallel-language: {parallel_metadata['locale']}",
            f"parallel-title: {parallel_metadata['title']}",
            f"parallel-context: {parallel_context}",
        ]
    )


def estimated_tokens(value: str) -> int:
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


def translation_locale(source_locale: str) -> str:
    if source_locale == "pl":
        return "en"
    if source_locale == "en":
        return "pl"
    raise ValueError(f"Unsupported semantic-map source language: {source_locale}")


def activity_items(
    config: dict[str, Any],
    *,
    vault: Path = VAULT,
    cache_dir: Path = CACHE_DIR,
) -> list[dict[str, Any]]:
    embedding = config["embedding"]
    source_order = list(config["corpus"]["sourceOrder"])
    source_rank = {source_id: index for index, source_id in enumerate(source_order)}
    items: list[dict[str, Any]] = []
    discovered_game_sources: set[str] = set()
    for activity_path in sorted((vault / "activities").glob("*.md")):
        metadata, source_body = load_markdown(activity_path)
        if config["corpus"]["kind"] not in (metadata.get("kinds") or []):
            continue
        source_id = str(metadata["sourceId"])
        discovered_game_sources.add(source_id)
        if source_id not in source_rank:
            continue
        target_locale = translation_locale(str(metadata["originalLanguage"]))
        translation_path = vault / "translations" / target_locale / activity_path.name
        if not translation_path.is_file():
            raise ValueError(f"Semantic-map V3 translation is missing: {translation_path}")
        parallel_metadata, parallel_body = load_markdown(translation_path)
        if (
            parallel_metadata.get("activityId") != metadata.get("id")
            or parallel_metadata.get("locale") != target_locale
            or parallel_metadata.get("sourceHash") != metadata.get("sourceHash")
            or parallel_metadata.get("status") != "machine-translation"
        ):
            raise ValueError(f"Semantic-map V3 translation is stale: {translation_path}")
        embedding_input = build_embedding_input(
            metadata,
            source_body,
            parallel_metadata,
            parallel_body,
            embedding,
        )
        input_tokens = estimated_tokens(embedding_input)
        if input_tokens > int(embedding["modelMaxInputTokens"]):
            raise ValueError(
                f"Semantic-map V3 input exceeds the model context: {metadata['id']} "
                f"({input_tokens} > {embedding['modelMaxInputTokens']})"
            )
        items.append(
            {
                "id": metadata["id"],
                "sourceId": source_id,
                "sourceHash": metadata["sourceHash"],
                "sourceLocale": metadata["originalLanguage"],
                "parallelLocale": target_locale,
                "input": embedding_input,
                "inputHash": canonical_hash(embedding_input),
                "estimatedInputTokens": input_tokens,
                "cachePath": cache_dir / f"{metadata['id']}.json",
            }
        )
    if discovered_game_sources != set(source_order):
        missing = sorted(discovered_game_sources - set(source_order))
        stale = sorted(set(source_order) - discovered_game_sources)
        raise ValueError(
            f"Semantic-map V3 sourceOrder differs from game corpus; missing={missing}, stale={stale}"
        )
    return sorted(items, key=lambda item: (source_rank[item["sourceId"]], item["id"]))


def cache_payload_is_current(
    payload: dict[str, Any], item: dict[str, Any], embedding: dict[str, Any]
) -> bool:
    vector = payload.get("vector")
    return (
        payload.get("schemaVersion") == 1
        and payload.get("pipeline") == "semantic-map-v3-embeddings"
        and payload.get("activityId") == item["id"]
        and payload.get("sourceId") == item["sourceId"]
        and payload.get("sourceHash") == item["sourceHash"]
        and payload.get("modelRequested") == embedding["model"]
        and payload.get("recipeVersion") == embedding["recipeVersion"]
        and payload.get("inputHash") == item["inputHash"]
        and payload.get("input") == item["input"]
        and payload.get("dimensions") == int(embedding["dimensions"])
        and isinstance(payload.get("model"), str)
        and bool(payload["model"])
        and isinstance(vector, list)
        and len(vector) == int(embedding["dimensions"])
        and all(isinstance(value, (int, float)) for value in vector)
    )


def cache_is_current(path: Path, item: dict[str, Any], embedding: dict[str, Any]) -> bool:
    if not path.is_file():
        return False
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and cache_payload_is_current(payload, item, embedding)


def current_ids(config: dict[str, Any], items: list[dict[str, Any]]) -> set[str]:
    return {
        item["id"]
        for item in items
        if cache_is_current(item["cachePath"], item, config["embedding"])
    }


def update_checkpoint(
    updates: dict[str, Any],
    *,
    remove_keys: tuple[str, ...] = (),
    path: Path = CHECKPOINT_PATH,
) -> dict[str, Any]:
    checkpoint = read_json(path) if path.is_file() else {}
    for key in remove_keys:
        checkpoint.pop(key, None)
    checkpoint.update(
        {"schemaVersion": 1, "pipeline": "semantic-map-v3-embeddings", **updates}
    )
    write_json(path, checkpoint)
    return checkpoint


def recover_cached_items(
    config: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    batch_dir: Path = BATCH_DIR,
) -> int:
    embedding = config["embedding"]
    expected = {item["id"]: item for item in items}
    recovered = 0
    for batch_path in sorted(batch_dir.glob("*.json")):
        batch = read_json(batch_path)
        batch_items = batch.get("items") or []
        for payload in batch_items:
            item = expected.get(payload.get("activityId"))
            if not item:
                continue
            if (
                payload.get("sourceId") != item["sourceId"]
                or payload.get("sourceHash") != item["sourceHash"]
                or payload.get("modelRequested") != embedding["model"]
                or payload.get("recipeVersion") != embedding["recipeVersion"]
                or payload.get("inputHash") != item["inputHash"]
                or payload.get("dimensions") != int(embedding["dimensions"])
            ):
                continue
            if not cache_payload_is_current(payload, item, embedding):
                continue
            if not cache_is_current(item["cachePath"], item, embedding):
                write_json(item["cachePath"], payload)
                recovered += 1
        if batch_items and all(
            (item := expected.get(payload.get("activityId")))
            and cache_is_current(item["cachePath"], item, embedding)
            for payload in batch_items
        ):
            batch.pop("items", None)
            write_json(batch_path, batch)
    return recovered


def load_batches(batch_dir: Path = BATCH_DIR) -> list[dict[str, Any]]:
    return [read_json(path) for path in sorted(batch_dir.glob("*.json"))]


def summarize_usage(batches: list[dict[str, Any]]) -> dict[str, Any]:
    prompt_tokens = sum(int((batch.get("usage") or {}).get("promptTokens", 0)) for batch in batches)
    reference_cost = sum(
        float((batch.get("usage") or {}).get("referenceCostUsd", 0)) for batch in batches
    )
    billed_values = [(batch.get("usage") or {}).get("billedCostUsd") for batch in batches]
    return {
        "requests": len(batches),
        "documentsProcessed": sum(len(batch.get("activityIds") or []) for batch in batches),
        "promptTokens": prompt_tokens,
        "billedCostUsd": (
            round(sum(float(value) for value in billed_values), 8)
            if billed_values and all(value is not None for value in billed_values)
            else None
        ),
        "referenceCostUsd": round(reference_cost, 8),
    }


def corpus_digest(items: list[dict[str, Any]]) -> str:
    return canonical_hash(
        [
            {
                "activityId": item["id"],
                "sourceId": item["sourceId"],
                "sourceHash": item["sourceHash"],
                "inputHash": item["inputHash"],
            }
            for item in items
        ]
    )


def build_progress_report(
    config: dict[str, Any],
    items: list[dict[str, Any]],
    batches: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    cached_ids = current_ids(config, items)
    sources: list[dict[str, Any]] = []
    for source_id in config["corpus"]["sourceOrder"]:
        source_ids = [item["id"] for item in items if item["sourceId"] == source_id]
        source_cached = sorted(set(source_ids) & cached_ids)
        sources.append(
            {
                "sourceId": source_id,
                "total": len(source_ids),
                "cached": len(source_cached),
                "remaining": len(source_ids) - len(source_cached),
                "status": (
                    "complete"
                    if len(source_cached) == len(source_ids)
                    else "not-started"
                    if not source_cached
                    else "in-progress"
                ),
                "cachedActivityIds": source_cached,
            }
        )
    usage = summarize_usage(batches)
    limit = float(config["execution"]["maxTotalReferenceCostUsd"])
    return {
        "schemaVersion": 1,
        "pipeline": "semantic-map-v3-embeddings",
        "status": "complete" if len(cached_ids) == len(items) else "in-progress",
        "generatedAt": generated_at,
        "corpusDigest": corpus_digest(items),
        "cacheNamespace": "data/embeddings/v3",
        "modelRequested": config["embedding"]["model"],
        "dimensions": config["embedding"]["dimensions"],
        "recipeVersion": config["embedding"]["recipeVersion"],
        "activities": {
            "total": len(items),
            "cached": len(cached_ids),
            "remaining": len(items) - len(cached_ids),
        },
        "sources": sources,
        "cachedActivityIds": sorted(cached_ids),
        "batchIds": sorted(str(batch["batchId"]) for batch in batches),
        "costAccounting": {
            "billingMode": config["execution"]["billingMode"],
            "billedCostKnown": False,
            "referencePriceUsdPerMillionInputTokens": config["embedding"][
                "priceUsdPerMillionInputTokens"
            ],
            "referencePriceSource": config["embedding"]["priceSource"],
            "referencePriceAccessedOn": config["embedding"]["priceAccessedOn"],
            "maxTotalReferenceCostUsd": limit,
            "referenceCostRemainingUsd": round(limit - usage["referenceCostUsd"], 8),
        },
        "usage": usage,
    }


def write_progress_report(
    config: dict[str, Any], items: list[dict[str, Any]], *, generated_at: str
) -> dict[str, Any]:
    report = build_progress_report(config, items, load_batches(), generated_at=generated_at)
    write_json(REPORT_PATH, report)
    return report


def write_retry_checkpoint(
    config: dict[str, Any],
    *,
    source_id: str,
    reason: str,
    next_retry_at: datetime,
    diagnostics: dict[str, Any],
) -> None:
    update_checkpoint(
        {
            "status": "retry-pending",
            "sourceId": source_id,
            "modelRequested": config["embedding"]["model"],
            "recipeVersion": config["embedding"]["recipeVersion"],
            "billingMode": config["execution"]["billingMode"],
            "reason": reason,
            "nextRetryAt": next_retry_at.astimezone(UTC).isoformat(),
            "providerDiagnostics": diagnostics,
        }
    )


def ensure_model_access(config: dict[str, Any], api_key: str, source_id: str) -> None:
    model = str(config["embedding"]["model"])
    try:
        ensure_models_available(api_key, {model})
    except TransientTranslationError as error:
        write_retry_checkpoint(
            config,
            source_id=source_id,
            reason=error.reason,
            next_retry_at=error.retry_at,
            diagnostics=error.diagnostics,
        )
        raise RuntimeError("Transient Mistral model-access failure; checkpoint saved") from error
    except PermanentTranslationError as error:
        update_checkpoint(
            {
                "status": "failed-permanent",
                "sourceId": source_id,
                "modelRequested": model,
                "recipeVersion": config["embedding"]["recipeVersion"],
                "billingMode": config["execution"]["billingMode"],
                "reason": error.reason,
                "providerDiagnostics": error.diagnostics,
            },
            remove_keys=("nextRetryAt",),
        )
        raise RuntimeError("Permanent Mistral model-access failure; checkpoint saved") from error


def request_embeddings(
    config: dict[str, Any], api_key: str, inputs: list[str], *, source_id: str
) -> dict[str, Any]:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            {"model": config["embedding"]["model"], "input": inputs}
        ).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        diagnostics = safe_http_diagnostics(error)
        reason = f"mistral-http-{error.code}"
        if error.code in TRANSIENT_HTTP_CODES:
            write_retry_checkpoint(
                config,
                source_id=source_id,
                reason=reason,
                next_retry_at=retry_at_from_headers(error.headers),
                diagnostics=diagnostics,
            )
            raise RuntimeError(f"Transient Mistral HTTP {error.code}; checkpoint saved") from error
        update_checkpoint(
            {
                "status": "failed-permanent",
                "sourceId": source_id,
                "modelRequested": config["embedding"]["model"],
                "recipeVersion": config["embedding"]["recipeVersion"],
                "billingMode": config["execution"]["billingMode"],
                "reason": reason,
                "providerDiagnostics": diagnostics,
            },
            remove_keys=("nextRetryAt",),
        )
        raise RuntimeError(f"Permanent Mistral HTTP {error.code}; checkpoint saved") from error
    except (urllib.error.URLError, TimeoutError) as error:
        write_retry_checkpoint(
            config,
            source_id=source_id,
            reason="mistral-network-unavailable",
            next_retry_at=datetime.now(UTC) + timedelta(hours=1),
            diagnostics={"transport": "network"},
        )
        raise RuntimeError("Transient Mistral network failure; checkpoint saved") from error


def source_selection(
    config: dict[str, Any],
    items: list[dict[str, Any]],
    cached_ids: set[str],
    requested_source_id: str | None,
) -> tuple[str | None, list[dict[str, Any]]]:
    source_order = config["corpus"]["sourceOrder"]
    if requested_source_id and requested_source_id not in source_order:
        raise ValueError(f"Unknown semantic-map V3 source: {requested_source_id}")
    source_id = requested_source_id
    if not source_id:
        source_id = next(
            (
                candidate
                for candidate in source_order
                if any(
                    item["sourceId"] == candidate and item["id"] not in cached_ids
                    for item in items
                )
            ),
            None,
        )
    if source_id is None:
        return None, []
    return source_id, [
        item
        for item in items
        if item["sourceId"] == source_id and item["id"] not in cached_ids
    ]


def main() -> None:
    config = load_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-id")
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    max_documents = int(config["execution"]["maxDocumentsPerRequest"])
    if not 1 <= args.limit <= max_documents:
        raise SystemExit(f"limit must be between 1 and {max_documents}")

    items = activity_items(config)
    recovered = recover_cached_items(config, items)
    cached_before = current_ids(config, items)
    try:
        source_id, source_pending = source_selection(
            config, items, cached_before, args.source_id
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    selected = source_pending[: args.limit]
    batches = load_batches()
    usage_before = summarize_usage(batches)
    token_estimate = sum(estimated_tokens(item["input"]) for item in selected)
    price = float(config["embedding"]["priceUsdPerMillionInputTokens"])
    estimated_cost = token_estimate * price / 1_000_000
    worst_case_cost = (
        len(selected) * int(config["embedding"]["modelMaxInputTokens"]) * price / 1_000_000
    )
    cost_limit = float(config["execution"]["maxTotalReferenceCostUsd"])
    plan = {
        "mode": "execute" if args.execute else "dry-run",
        "pipeline": "semantic-map-v3-embeddings",
        "sourceId": source_id,
        "modelRequested": config["embedding"]["model"],
        "recipeVersion": config["embedding"]["recipeVersion"],
        "selectedIds": [item["id"] for item in selected],
        "selectedDocuments": len(selected),
        "remainingSourceBeforeBatch": len(source_pending),
        "cachedCorpusBeforeBatch": len(cached_before),
        "totalCorpus": len(items),
        "recoveredFromBatchLedger": recovered,
        "estimatedInputTokens": token_estimate,
        "billingMode": config["execution"]["billingMode"],
        "billedCostUsd": None,
        "estimatedReferenceCostUsd": round(estimated_cost, 8),
        "worstCaseReferenceCostUsd": round(worst_case_cost, 8),
        "referenceCostBeforeBatchUsd": usage_before["referenceCostUsd"],
        "maxTotalReferenceCostUsd": cost_limit,
        "exactModelAccessCheckRequired": True,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if usage_before["referenceCostUsd"] + worst_case_cost > cost_limit:
        raise SystemExit("planned batch exceeds the total reference-cost limit")
    if not args.execute:
        return
    if not selected:
        return

    api_key = load_secret()
    ensure_model_access(config, api_key, str(source_id))
    result = request_embeddings(
        config,
        api_key,
        [item["input"] for item in selected],
        source_id=str(source_id),
    )
    vectors_by_index = {entry["index"]: entry["embedding"] for entry in result.get("data", [])}
    if set(vectors_by_index) != set(range(len(selected))):
        raise RuntimeError("Mistral response indexes do not match the V3 request")
    dimensions = int(config["embedding"]["dimensions"])
    if any(
        not isinstance(vector, list)
        or len(vector) != dimensions
        or not all(isinstance(value, (int, float)) for value in vector)
        for vector in vectors_by_index.values()
    ):
        raise RuntimeError(f"Mistral returned a V3 embedding other than {dimensions} numbers")

    completed_at = datetime.now(UTC)
    generated_at = completed_at.isoformat()
    batch_id = completed_at.strftime("%Y%m%dT%H%M%S%fZ")
    actual_model = str(result.get("model") or config["embedding"]["model"])
    response_usage = result.get("usage") or {}
    prompt_tokens = int(
        response_usage.get("prompt_tokens", response_usage.get("total_tokens", token_estimate))
    )
    reference_cost = prompt_tokens * price / 1_000_000
    if usage_before["referenceCostUsd"] + reference_cost > cost_limit:
        raise RuntimeError("Mistral response would exceed the V3 reference-cost limit")
    cache_payloads = [
        {
            "schemaVersion": 1,
            "pipeline": "semantic-map-v3-embeddings",
            "activityId": item["id"],
            "sourceId": item["sourceId"],
            "sourceHash": item["sourceHash"],
            "sourceLocale": item["sourceLocale"],
            "parallelLocale": item["parallelLocale"],
            "modelRequested": config["embedding"]["model"],
            "model": actual_model,
            "dimensions": dimensions,
            "recipeVersion": config["embedding"]["recipeVersion"],
            "inputHash": item["inputHash"],
            "input": item["input"],
            "generatedAt": generated_at,
            "batchId": batch_id,
            "vector": vectors_by_index[index],
        }
        for index, item in enumerate(selected)
    ]
    batch = {
        "schemaVersion": 1,
        "pipeline": "semantic-map-v3-embeddings",
        "batchId": batch_id,
        "generatedAt": generated_at,
        "sourceId": source_id,
        "modelRequested": config["embedding"]["model"],
        "model": actual_model,
        "dimensions": dimensions,
        "recipeVersion": config["embedding"]["recipeVersion"],
        "billingMode": config["execution"]["billingMode"],
        "modelAccess": {
            "checked": True,
            "modelId": config["embedding"]["model"],
        },
        "referencePriceUsdPerMillionInputTokens": price,
        "referencePriceSource": config["embedding"]["priceSource"],
        "referencePriceAccessedOn": config["embedding"]["priceAccessedOn"],
        "activityIds": [item["id"] for item in selected],
        "usage": {
            "promptTokens": prompt_tokens,
            "billedCostUsd": None,
            "referenceCostUsd": round(reference_cost, 8),
        },
        "items": cache_payloads,
    }
    write_json(BATCH_DIR / f"{batch_id}.json", batch)
    for item, payload in zip(selected, cache_payloads, strict=True):
        write_json(item["cachePath"], payload)
    batch.pop("items")
    write_json(BATCH_DIR / f"{batch_id}.json", batch)

    report = write_progress_report(config, activity_items(config), generated_at=generated_at)
    source_report = next(entry for entry in report["sources"] if entry["sourceId"] == source_id)
    next_source_id = next(
        (entry["sourceId"] for entry in report["sources"] if entry["remaining"] > 0), None
    )
    update_checkpoint(
        {
            "status": (
                "complete"
                if report["status"] == "complete"
                else "source-complete"
                if source_report["status"] == "complete"
                else "source-batch-complete"
            ),
            "sourceId": source_id,
            "lastBatchId": batch_id,
            "lastCompletedAt": generated_at,
            "lastBatchActivityCount": len(selected),
            "lastBatchPromptTokens": prompt_tokens,
            "lastBatchBilledCostUsd": None,
            "lastBatchReferenceCostUsd": round(reference_cost, 8),
            "cachedActivities": report["activities"]["cached"],
            "totalActivities": report["activities"]["total"],
            "completedSourceIds": [
                entry["sourceId"] for entry in report["sources"] if entry["status"] == "complete"
            ],
            "nextSourceId": next_source_id,
            "modelRequested": config["embedding"]["model"],
            "model": actual_model,
            "dimensions": dimensions,
            "recipeVersion": config["embedding"]["recipeVersion"],
            "corpusDigest": report["corpusDigest"],
            "billingMode": config["execution"]["billingMode"],
            "referenceCostUsd": report["usage"]["referenceCostUsd"],
            "maxTotalReferenceCostUsd": cost_limit,
        },
        remove_keys=("nextRetryAt", "providerDiagnostics", "reason"),
    )
    print(
        json.dumps(
            {
                "batchId": batch_id,
                "sourceId": source_id,
                "model": actual_model,
                "activityIds": batch["activityIds"],
                "usage": batch["usage"],
                "progress": report["activities"],
                "sourceProgress": source_report,
                "checkpoint": str(CHECKPOINT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
