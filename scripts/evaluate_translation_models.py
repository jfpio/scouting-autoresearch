#!/usr/bin/env python3
"""Evaluate one or two pinned translation models on representative source records."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown, sha256_bytes, source_hash, write_json
from translate import (
    PermanentTranslationError,
    TransientTranslationError,
    active_retry,
    checkpoint_path,
    ensure_models_available,
    load_secret,
    model_pricing,
    prompt_version,
    request_translation,
    request_reference_cost_upper_bound,
    translation_fidelity_checks,
    translation_output_token_budget,
    translation_target,
)


DEFAULT_CONFIG = ROOT / "config" / "translation-model-evaluation.yaml"
EVALUATION_CHECKPOINT_DIR = ROOT / "data" / "checkpoints" / "translation-model-evaluation"


def load_evaluation_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schemaVersion") != 1:
        raise ValueError("Translation model evaluation requires schemaVersion 1")
    activity_ids = config.get("activityIds")
    candidates = config.get("candidates")
    execution = config.get("execution") or {}
    if not isinstance(activity_ids, list) or not activity_ids:
        raise ValueError("Translation model evaluation has no activity IDs")
    if len(activity_ids) != len(set(activity_ids)):
        raise ValueError("Translation model evaluation repeats an activity ID")
    if len(activity_ids) > int(execution.get("maxActivities", 0)):
        raise ValueError("Translation model evaluation exceeds its activity limit")
    if (
        not isinstance(candidates, list)
        or not 1 <= len(candidates) <= 2
        or len(candidates) != len(set(candidates))
    ):
        raise ValueError("Translation model evaluation requires one or two distinct models")
    if len(candidates) > int(execution.get("maxModels", 0)):
        raise ValueError("Translation model evaluation exceeds its model limit")
    if config.get("productionCandidate") not in candidates:
        raise ValueError("Production candidate is not one of the evaluated models")
    if execution.get("sequentialRequests") is not True:
        raise ValueError("Translation model evaluation must use sequential requests")
    if execution.get("requireExplicitExecute") is not True:
        raise ValueError("Translation model evaluation must require explicit execution")
    if config.get("reasoningMode") != "disabled":
        raise ValueError("Translation model evaluation must keep production reasoning disabled")
    if execution.get("billingMode") != "education-credit":
        raise ValueError("Translation model evaluation must record Education credit billing")
    if execution.get("enforceReferenceCostLimit") is not True:
        raise ValueError("Translation model evaluation must enforce its reference-cost limit")
    cost_limit = float(execution.get("maxReferenceCostUsd", 0))
    if not 0 < cost_limit <= 10:
        raise ValueError("Translation model evaluation cost limit must be within (0, 10] USD")
    for model in candidates:
        model_pricing(str(model))
    return config


def translation_quality_checks(
    metadata: dict[str, Any],
    body: str,
    translated: dict[str, Any],
) -> dict[str, Any]:
    return {
        **translation_fidelity_checks(metadata, body, translated),
        "humanReviewRequired": True,
    }


def user_payload(activity_id: str, metadata: dict[str, Any], body: str) -> dict[str, Any]:
    return {
        "id": activity_id,
        "title": metadata["title"],
        "traits": metadata.get("traits", []),
        "section": metadata.get("section", ""),
        "body": body,
    }


def activity_records(config: dict[str, Any]) -> list[tuple[Path, dict[str, Any], str]]:
    source_id = str(config["sourceId"])
    source_path = VAULT / "sources" / f"{source_id}.md"
    source, _ = load_markdown(source_path)
    if source.get("rightsStatus") != "public-domain":
        raise ValueError(f"Source {source_id} is not approved for full-text processing")
    records: list[tuple[Path, dict[str, Any], str]] = []
    for activity_id in config["activityIds"]:
        path = VAULT / "activities" / f"{activity_id}.md"
        metadata, body = load_markdown(path)
        if metadata.get("sourceId") != source_id:
            raise ValueError(f"Evaluation activity {activity_id} does not belong to {source_id}")
        records.append((path, metadata, body))
    return records


def result_location(config: dict[str, Any]) -> tuple[Path, str]:
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise ValueError("SCRATCH is required for temporary translation evaluation output")
    relative = Path(str(config["execution"]["resultsUnderScratch"])) / str(config["id"]) / "results.json"
    return Path(scratch) / relative, str(relative)


def summary_payload(
    config: dict[str, Any],
    config_hash: str,
    result_relative_path: str,
    results: list[dict[str, Any]],
    *,
    status: str,
    current_pair: str | None = None,
    transient_error: TransientTranslationError | None = None,
    permanent_error: PermanentTranslationError | None = None,
) -> dict[str, Any]:
    expected_pairs = [
        f"{model}:{activity_id}"
        for model in config["candidates"]
        for activity_id in config["activityIds"]
    ]
    completed_pairs = [str(item["pairId"]) for item in results]
    usage_by_model: dict[str, dict[str, int | float]] = {}
    for item in results:
        usage = item["usage"]
        totals = usage_by_model.setdefault(
            str(item["modelRequested"]),
            {"promptTokens": 0, "completionTokens": 0, "referenceCostUsd": 0.0},
        )
        totals["promptTokens"] += int(usage["promptTokens"])
        totals["completionTokens"] += int(usage["completionTokens"])
        totals["referenceCostUsd"] = round(
            float(totals["referenceCostUsd"]) + float(usage["referenceCostUsd"]), 8
        )
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "pipeline": "translation-model-evaluation",
        "evaluationId": config["id"],
        "sourceId": config["sourceId"],
        "status": status,
        "configHash": config_hash,
        "productionCandidate": config["productionCandidate"],
        "reasoningMode": config.get("reasoningMode", "disabled"),
        "candidates": config["candidates"],
        "activityIds": config["activityIds"],
        "completedPairs": completed_pairs,
        "pendingPairs": [pair for pair in expected_pairs if pair not in set(completed_pairs)],
        "usageByModel": usage_by_model,
        "automaticFailurePairs": [
            str(item["pairId"]) for item in results if not item["checks"]["automaticPass"]
        ],
        "humanReviewRequired": True,
        "resultPathUnderScratch": result_relative_path,
    }
    if current_pair:
        payload["currentPair"] = current_pair
    if transient_error:
        payload["reason"] = transient_error.reason
        payload["nextRetryAt"] = transient_error.retry_at.astimezone(UTC).isoformat()
        if transient_error.diagnostics:
            payload["providerError"] = transient_error.diagnostics
    if permanent_error:
        payload["reason"] = permanent_error.reason
        if permanent_error.diagnostics:
            payload["providerError"] = permanent_error.diagnostics
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config = load_evaluation_config(args.config)
    records = activity_records(config)
    source_locale = records[0][1]["originalLanguage"]
    target_locale = translation_target(source_locale)
    config_hash = sha256_bytes(args.config.read_bytes())
    plan = {
        "evaluationId": config["id"],
        "sourceId": config["sourceId"],
        "models": config["candidates"],
        "activityIds": config["activityIds"],
        "requests": len(config["candidates"]) * len(records),
        "requestMaxOutputTokens": {
            path.stem: translation_output_token_budget(user_payload(path.stem, metadata, body))
            for path, metadata, body in records
        },
        "execute": args.execute,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.execute:
        return

    production_retry = active_retry(checkpoint_path(str(config["sourceId"]), source_locale, target_locale))
    if production_retry:
        raise SystemExit(f"Provider cooldown is active; nextRetryAt={production_retry.isoformat()}")
    evaluation_checkpoint = EVALUATION_CHECKPOINT_DIR / f"{config['id']}.json"
    evaluation_retry = active_retry(evaluation_checkpoint)
    if evaluation_retry:
        raise SystemExit(f"Evaluation cooldown is active; nextRetryAt={evaluation_retry.isoformat()}")

    result_path, relative_result_path = result_location(config)
    results: list[dict[str, Any]] = []
    if result_path.exists():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing.get("configHash") == config_hash:
            results = list(existing.get("results") or [])
    completed = {str(item["pairId"]) for item in results}
    api_key = load_secret()
    try:
        ensure_models_available(api_key, {str(model) for model in config["candidates"]})
    except TransientTranslationError as error:
        write_json(
            evaluation_checkpoint,
            summary_payload(
                config,
                config_hash,
                relative_result_path,
                results,
                status="retry-pending",
                current_pair="model-access-preflight",
                transient_error=error,
            ),
        )
        raise SystemExit(f"{error.reason}; nextRetryAt={error.retry_at.isoformat()}") from error
    except PermanentTranslationError as error:
        write_json(
            evaluation_checkpoint,
            summary_payload(
                config,
                config_hash,
                relative_result_path,
                results,
                status="failed-permanent",
                current_pair="model-access-preflight",
                permanent_error=error,
            ),
        )
        raise SystemExit(
            f"{error.reason}; provider access or configuration requires review"
        ) from error
    for model in config["candidates"]:
        for path, metadata, body in records:
            pair_id = f"{model}:{path.stem}"
            if pair_id in completed:
                continue
            spent_usd = sum(
                float(item["usage"]["referenceCostUsd"]) for item in results
            )
            projected_usd = spent_usd + request_reference_cost_upper_bound(
                metadata, body, str(model)
            )
            cost_limit = float(config["execution"]["maxReferenceCostUsd"])
            if projected_usd > cost_limit:
                raise SystemExit(
                    f"Translation evaluation reference-cost limit would be exceeded: "
                    f"{projected_usd:.8f} > {cost_limit:.2f} USD"
                )
            try:
                translated, actual_model, usage = request_translation(
                    api_key,
                    str(model),
                    path.stem,
                    metadata,
                    body,
                    source_locale,
                    target_locale,
                )
            except TransientTranslationError as error:
                checkpoint = summary_payload(
                    config,
                    config_hash,
                    relative_result_path,
                    results,
                    status="retry-pending",
                    current_pair=pair_id,
                    transient_error=error,
                )
                write_json(evaluation_checkpoint, checkpoint)
                raise SystemExit(f"{error.reason}; nextRetryAt={error.retry_at.isoformat()}") from error
            except PermanentTranslationError as error:
                checkpoint = summary_payload(
                    config,
                    config_hash,
                    relative_result_path,
                    results,
                    status="failed-permanent",
                    current_pair=pair_id,
                    permanent_error=error,
                )
                write_json(evaluation_checkpoint, checkpoint)
                raise SystemExit(
                    f"{error.reason}; provider access or configuration requires review"
                ) from error
            results.append(
                {
                    "pairId": pair_id,
                    "activityId": path.stem,
                    "sourceHash": source_hash(metadata["title"], body),
                    "sourceLocale": source_locale,
                    "targetLocale": target_locale,
                    "modelRequested": model,
                    "model": actual_model,
                    "promptVersion": prompt_version(source_locale, target_locale),
                    "reasoningMode": "disabled",
                    "usage": usage,
                    "checks": translation_quality_checks(metadata, body, translated),
                    "translation": translated,
                }
            )
            completed.add(pair_id)
            write_json(
                result_path,
                {
                    "schemaVersion": 1,
                    "evaluationId": config["id"],
                    "configHash": config_hash,
                    "generatedAt": datetime.now(UTC).isoformat(),
                    "results": results,
                },
            )
            write_json(
                evaluation_checkpoint,
                summary_payload(
                    config,
                    config_hash,
                    relative_result_path,
                    results,
                    status="in-progress",
                    current_pair=pair_id,
                ),
            )

    write_json(
        evaluation_checkpoint,
        summary_payload(
            config,
            config_hash,
            relative_result_path,
            results,
            status="complete",
        ),
    )
    print(f"Evaluation complete; inspect $SCRATCH/{relative_result_path}")


if __name__ == "__main__":
    main()
