#!/usr/bin/env python3
"""Build a bounded, resumable embedding cache for the proposed V1 taxonomy."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
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
QUEUE_PATH = ROOT / "config" / "research-queue.yaml"
CACHE_DIR = ROOT / "data" / "embeddings" / "v1"
BATCH_DIR = CACHE_DIR / "batches"
REPORT_PATH = ROOT / "data" / "reports" / "taxonomy-v1-embedding-progress.json"
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
    if config.get("schemaVersion") != 1 or not isinstance(embedding, dict):
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
    return config


def normalize_context(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def build_embedding_input(metadata: dict[str, Any], body: str, context_characters: int) -> str:
    source_traits = metadata.get("traits") or []
    traits_text = " | ".join(str(item).strip() for item in source_traits) or "[brak cech w źródle]"
    context = normalize_context(body)[:context_characters].rstrip()
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


def write_retry_checkpoint(*, now: datetime, reason: str, retry_after: str | None = None) -> None:
    atomic_write_json(
        CHECKPOINT_PATH,
        {
            "schemaVersion": 1,
            "pipeline": "taxonomy-v1-embeddings",
            "status": "retry-pending",
            "reason": reason,
            "nextRetryAt": retry_at(now, retry_after).isoformat(),
        },
    )


def request_embeddings(api_key: str, model: str, inputs: list[str]) -> dict[str, Any]:
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
            write_retry_checkpoint(now=now, reason=f"mistral-http-{error.code}", retry_after=error.headers.get("Retry-After"))
            raise RuntimeError(f"Transient Mistral HTTP {error.code}; checkpoint saved") from error
        atomic_write_json(
            CHECKPOINT_PATH,
            {
                "schemaVersion": 1,
                "pipeline": "taxonomy-v1-embeddings",
                "status": "failed-permanent",
                "reason": f"mistral-http-{error.code}",
            },
        )
        raise RuntimeError(f"Permanent Mistral HTTP {error.code}; checkpoint saved") from error
    except (urllib.error.URLError, TimeoutError) as error:
        write_retry_checkpoint(now=now, reason="mistral-network-unavailable")
        raise RuntimeError("Transient Mistral network failure; checkpoint saved") from error


def activity_items(config: dict[str, Any]) -> list[dict[str, Any]]:
    embedding = config["embedding"]
    items: list[dict[str, Any]] = []
    for path in sorted((VAULT / "activities").glob("*.md")):
        metadata, body = load_markdown(path)
        text = build_embedding_input(metadata, body, int(embedding["contextCharacters"]))
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


def write_progress_report(config: dict[str, Any], items: list[dict[str, Any]], *, generated_at: str) -> dict[str, Any]:
    embedding = config["embedding"]
    current = current_items(items, config)
    batch_paths = sorted(BATCH_DIR.glob("*.json"))
    batches = [read_json(path) for path in batch_paths]
    prompt_tokens = sum(int(batch.get("usage", {}).get("promptTokens", 0)) for batch in batches)
    estimated_cost = prompt_tokens * float(embedding["priceUsdPerMillionInputTokens"]) / 1_000_000
    report = {
        "schemaVersion": 1,
        "pipeline": "taxonomy-v1-embeddings",
        "status": "complete" if len(current) == len(items) else "in-progress",
        "generatedAt": generated_at,
        "modelRequested": embedding["model"],
        "dimensions": embedding["dimensions"],
        "recipeVersion": embedding["recipeVersion"],
        "priceUsdPerMillionInputTokens": embedding["priceUsdPerMillionInputTokens"],
        "priceSource": embedding["priceSource"],
        "activities": {"total": len(items), "cached": len(current), "remaining": len(items) - len(current)},
        "usage": {"promptTokens": prompt_tokens, "estimatedCostUsd": round(estimated_cost, 8)},
        "batchIds": [batch["batchId"] for batch in batches],
        "cachedActivityIds": [item["id"] for item in current],
    }
    atomic_write_json(REPORT_PATH, report)
    return report


def main() -> None:
    config = load_config()
    queue = load_yaml(QUEUE_PATH)
    daily_limits = queue["dailyLimits"]
    embedding = config["embedding"]

    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Send the planned bounded batch to Mistral")
    parser.add_argument("--limit", type=int, default=int(daily_limits["documents"]))
    parser.add_argument("--ids", nargs="*")
    args = parser.parse_args()

    hard_document_limit = int(daily_limits["documents"])
    hard_cost_limit = float(daily_limits["estimatedCostUsd"])
    if args.limit < 1 or args.limit > hard_document_limit:
        raise SystemExit(f"limit must be between 1 and {hard_document_limit}")

    items = activity_items(config)
    recovered = recover_cached_items(config, items)
    if args.ids:
        wanted = set(args.ids)
        unknown = wanted - {item["id"] for item in items}
        if unknown:
            raise SystemExit(f"unknown activity IDs: {sorted(unknown)}")
        items = [item for item in items if item["id"] in wanted]

    current_ids = {item["id"] for item in current_items(items, config)}
    pending = [item for item in items if item["id"] not in current_ids]
    selected = pending[: args.limit]
    token_estimate = sum(estimated_tokens(item["input"]) for item in selected)
    estimated_cost = token_estimate * float(embedding["priceUsdPerMillionInputTokens"]) / 1_000_000
    worst_case_cost = (
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
        "estimatedInputTokens": token_estimate,
        "estimatedCostUsd": round(estimated_cost, 8),
        "worstCaseCostUsd": round(worst_case_cost, 8),
        "hardCostLimitUsd": hard_cost_limit,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if worst_case_cost > hard_cost_limit:
        raise SystemExit("planned batch exceeds the hard cost limit")
    if not args.execute or not selected:
        return

    result = request_embeddings(load_secret(), embedding["model"], [item["input"] for item in selected])
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
    batch_cost = prompt_tokens * float(embedding["priceUsdPerMillionInputTokens"]) / 1_000_000
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
        "activityIds": [item["id"] for item in selected],
        "usage": {"promptTokens": prompt_tokens, "estimatedCostUsd": round(batch_cost, 8)},
        "items": cache_payloads,
    }
    atomic_write_json(BATCH_DIR / f"{batch_id}.json", batch)
    for item, payload in zip(selected, cache_payloads, strict=True):
        atomic_write_json(item["cachePath"], payload)
    del batch["items"]
    atomic_write_json(BATCH_DIR / f"{batch_id}.json", batch)

    report = write_progress_report(config, activity_items(config), generated_at=generated_at)
    next_id = next((item["id"] for item in activity_items(config) if item["id"] not in set(report["cachedActivityIds"])), None)
    atomic_write_json(
        CHECKPOINT_PATH,
        {
            "schemaVersion": 1,
            "pipeline": "taxonomy-v1-embeddings",
            "status": "complete" if next_id is None else "batch-complete",
            "lastBatchId": batch_id,
            "lastCompletedAt": generated_at,
            "documentsProcessedThisCycle": len(selected),
            "estimatedCostUsdThisCycle": round(batch_cost, 8),
            "cachedActivities": report["activities"]["cached"],
            "totalActivities": report["activities"]["total"],
            "nextActivityId": next_id,
        },
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
