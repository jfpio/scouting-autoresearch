#!/usr/bin/env python3
"""Compare versioned V1 embedding recipes without exposing source text or vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from common import ROOT, VAULT, load_markdown, read_json
from embed_taxonomy import (
    CACHE_DIR,
    CHECKPOINT_PATH,
    atomic_write_json,
    build_embedding_input,
    input_hash,
    load_config,
    update_checkpoint,
)


REPORT_PATH = ROOT / "data" / "reports" / "taxonomy-v1-input-quality.json"
DEFAULT_CANDIDATE_RECIPE = "activity-context-v2"


def embedded_context(value: str) -> str:
    marker = "kontekst: "
    if marker not in value:
        raise ValueError("Embedding input lacks a context field")
    return value.split(marker, 1)[1]


def noise_ids(inputs: dict[str, str]) -> dict[str, list[str]]:
    return {
        "sourceFooterIds": sorted(
            activity_id for activity_id, value in inputs.items() if "Źródło skanu:" in embedded_context(value)
        ),
        "rawUrlIds": sorted(
            activity_id for activity_id, value in inputs.items() if re.search(r"https?://", embedded_context(value))
        ),
    }


def build_quality_report(
    records: list[tuple[dict[str, Any], str]],
    caches: list[dict[str, Any]],
    *,
    embedding_config: dict[str, Any],
    candidate_recipe: str = DEFAULT_CANDIDATE_RECIPE,
) -> dict[str, Any]:
    active_recipe = str(embedding_config["recipeVersion"])
    context_characters = int(embedding_config["contextCharacters"])
    records = sorted(records, key=lambda record: record[0]["id"])
    caches = sorted(caches, key=lambda cache: cache["activityId"])
    record_ids = [metadata["id"] for metadata, _ in records]
    cache_ids = [cache["activityId"] for cache in caches]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("Activity records contain duplicate IDs")
    if len(cache_ids) != len(set(cache_ids)):
        raise ValueError("Embedding caches contain duplicate IDs")
    unknown_cache_ids = sorted(set(cache_ids) - set(record_ids))
    if unknown_cache_ids:
        raise ValueError(f"Embedding caches lack activity records: {unknown_cache_ids}")

    active_inputs = {
        metadata["id"]: build_embedding_input(
            metadata,
            body,
            context_characters,
            active_recipe,
        )
        for metadata, body in records
    }
    candidate_inputs = {
        metadata["id"]: build_embedding_input(
            metadata,
            body,
            context_characters,
            candidate_recipe,
        )
        for metadata, body in records
    }
    content_changed_ids = sorted(
        activity_id
        for activity_id in record_ids
        if input_hash(active_inputs[activity_id]) != input_hash(candidate_inputs[activity_id])
    )
    cached_set = set(cache_ids)
    content_changed_cached_ids = sorted(cached_set & set(content_changed_ids))
    actual_cached_inputs = {cache["activityId"]: str(cache["input"]) for cache in caches}
    active_noise = noise_ids(active_inputs)
    candidate_noise = noise_ids(candidate_inputs)
    cache_noise = noise_ids(actual_cached_inputs)

    fingerprint = {
        "activeRecipeVersion": active_recipe,
        "candidateRecipeVersion": candidate_recipe,
        "model": embedding_config["model"],
        "contextCharacters": context_characters,
        "records": [
            {
                "activityId": activity_id,
                "activeInputHash": input_hash(active_inputs[activity_id]),
                "candidateInputHash": input_hash(candidate_inputs[activity_id]),
                "cached": activity_id in cached_set,
            }
            for activity_id in record_ids
        ],
    }
    audit_hash = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    invalidated_cache_ids = cache_ids if candidate_recipe != active_recipe else []
    next_new_activity_id = next((activity_id for activity_id in record_ids if activity_id not in cached_set), None)
    evidence_through = max((str(cache["generatedAt"]) for cache in caches), default=None)

    return {
        "schemaVersion": 1,
        "pipeline": "taxonomy-v1-input-quality",
        "status": "recipe-upgrade-pending" if candidate_recipe != active_recipe else "ready",
        "generatedFrom": "activity-metadata-and-body",
        "evidenceThrough": evidence_through,
        "auditHash": audit_hash,
        "model": embedding_config["model"],
        "contextCharacters": context_characters,
        "activeRecipeVersion": active_recipe,
        "candidateRecipeVersion": candidate_recipe,
        "corpus": {
            "totalActivities": len(record_ids),
            "contentChangedActivities": len(content_changed_ids),
            "contentChangedActivityIds": content_changed_ids,
            "activeNoise": active_noise,
            "candidateNoise": candidate_noise,
        },
        "existingCaches": {
            "total": len(cache_ids),
            "contentChanged": len(content_changed_cached_ids),
            "contentChangedActivityIds": content_changed_cached_ids,
            "activeNoise": cache_noise,
            "invalidatedByRecipeChange": len(invalidated_cache_ids),
            "invalidatedActivityIds": invalidated_cache_ids,
        },
        "remediation": {
            "activateRecipeVersion": candidate_recipe,
            "configurationChangeRequired": candidate_recipe != active_recipe,
            "reembedBeforeNewActivities": invalidated_cache_ids,
            "nextNewActivityId": next_new_activity_id,
            "requiresExternalApi": bool(invalidated_cache_ids),
            "humanTaxonomyApprovalRequired": False,
        },
    }


def write_quality_checkpoint(
    report: dict[str, Any], path: Path = CHECKPOINT_PATH, report_path: Path = REPORT_PATH
) -> None:
    update_checkpoint(
        {
            "inputQualityAudit": {
                "status": report["status"],
                "auditHash": report["auditHash"],
                "reportPath": (
                    str(report_path.relative_to(ROOT))
                    if report_path.is_relative_to(ROOT)
                    else str(report_path)
                ),
                "activeRecipeVersion": report["activeRecipeVersion"],
                "candidateRecipeVersion": report["candidateRecipeVersion"],
                "cachedInputContentAffected": report["existingCaches"]["contentChanged"],
                "corpusInputContentAffected": report["corpus"]["contentChangedActivities"],
                "existingCachesInvalidatedByRecipeChange": report["existingCaches"][
                    "invalidatedByRecipeChange"
                ],
            }
        },
        path=path,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-recipe", default=DEFAULT_CANDIDATE_RECIPE)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    config = load_config()
    records = [load_markdown(path) for path in sorted((VAULT / "activities").glob("*.md"))]
    caches = [read_json(path) for path in sorted(CACHE_DIR.glob("*.json"))]
    report = build_quality_report(
        records,
        caches,
        embedding_config=config["embedding"],
        candidate_recipe=args.candidate_recipe,
    )
    atomic_write_json(args.output, report)
    write_quality_checkpoint(report, report_path=args.output)
    print(
        json.dumps(
            {
                "status": report["status"],
                "auditHash": report["auditHash"],
                "activeRecipeVersion": report["activeRecipeVersion"],
                "candidateRecipeVersion": report["candidateRecipeVersion"],
                "corpusContentChanged": report["corpus"]["contentChangedActivities"],
                "cachedContentChanged": report["existingCaches"]["contentChanged"],
                "cachesInvalidated": report["existingCaches"]["invalidatedByRecipeChange"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
