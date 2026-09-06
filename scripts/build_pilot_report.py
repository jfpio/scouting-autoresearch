#!/usr/bin/env python3
"""Build a measured pilot report while preserving missing human measurements as unknown."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown, read_json, write_json


DEFAULT_CONFIG_PATH = ROOT / "config" / "pilots" / "bsh-1911-seton-games.yaml"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if config.get("schemaVersion") != 1:
        raise ValueError("Unsupported pilot configuration")
    return config


def elapsed_seconds(value: str) -> int:
    parts = [int(part) for part in value.split(":")]
    if len(parts) != 3:
        raise ValueError(f"Invalid elapsed time: {value}")
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def editorial_review(activity_id: str) -> tuple[str, dict[str, Any]]:
    for stage in ("accepted", "inbox"):
        path = VAULT / "reviews" / "editorial" / stage / f"{activity_id}.md"
        if path.is_file():
            metadata, _ = load_markdown(path)
            return stage, metadata
    raise ValueError(f"Missing editorial pilot review: {activity_id}")


def build_report(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    source_review, _ = load_markdown(ROOT / config["sourceReview"])
    extraction = read_json(ROOT / config["extractionReport"])
    translation = read_json(ROOT / config["translationReport"])
    evaluation = yaml.safe_load((ROOT / config["translationEvaluation"]).read_text(encoding="utf-8"))
    processing = source_review["processing"]

    sample_results = []
    review_minutes: list[float] = []
    accepted_count = 0
    for activity_id in config["editorialSample"]:
        stage, review = editorial_review(activity_id)
        decision = review.get("humanDecision") or {}
        duration = decision.get("reviewDurationMinutes")
        if stage == "accepted":
            accepted_count += 1
        if isinstance(duration, (int, float)) and duration >= 0:
            review_minutes.append(float(duration))
        sample_results.append(
            {
                "activityId": activity_id,
                "stage": stage,
                "sourceHash": review.get("sourceHash"),
                "valueOutcome": (review.get("valueReview") or {}).get("outcome"),
                "safetyOutcome": (review.get("safetyReview") or {}).get("outcome"),
                "publicationRecommendation": review.get("publicationRecommendation"),
                "reviewDurationMinutes": duration,
            }
        )

    sample_count = len(config["editorialSample"])
    timing_complete = len(review_minutes) == sample_count
    review_complete = accepted_count == sample_count and timing_complete
    benchmark = processing["translation"]["evaluation"]
    benchmark_cost = round(
        float(benchmark["large"]["referenceCostUsd"])
        + float(benchmark["small"]["referenceCostUsd"]),
        8,
    )
    production_cost = float(translation["usage"]["referenceCostUsd"])
    total_reference_cost = round(benchmark_cost + production_cost, 8)
    excluded_variants = processing.get("excludedExistingVariants") or []
    build_elapsed = processing["buildValidation"]["slurm"]["elapsed"]
    return {
        "schemaVersion": 1,
        "pilotId": config["pilotId"],
        "sourceId": config["sourceId"],
        "status": "complete" if review_complete else "human-quality-and-timing-review-pending",
        "evidence": {
            "sourceReview": config["sourceReview"],
            "extractionReport": config["extractionReport"],
            "translationReport": config["translationReport"],
            "translationEvaluation": config["translationEvaluation"],
        },
        "scope": {
            "curatedCandidates": processing["curatedCandidateCount"],
            "importedActivities": extraction["activityCount"],
            "excludedExistingVariants": len(excluded_variants),
            "wholeSourceCopiedToRepository": extraction["wholeSourceCopiedToRepository"],
        },
        "translation": {
            "productionModel": translation["modelRequested"],
            "productionActivities": len(translation["completedActivityIds"]),
            "productionAutomaticFailures": 0,
            "benchmarkSampleSize": len(evaluation["activityIds"]),
            "largeAutomaticFailures": benchmark["large"]["automaticFailures"],
            "smallAutomaticFailures": benchmark["small"]["automaticFailures"],
            "smallFailedActivityIds": benchmark["small"].get("failedActivityIds", []),
            "reasoningMode": translation["reasoningMode"],
        },
        "cost": {
            "currency": "USD",
            "billingMode": translation["usage"]["billingMode"],
            "benchmarkReferenceCost": benchmark_cost,
            "productionReferenceCost": production_cost,
            "totalReferenceCost": total_reference_cost,
            "billedCost": None,
            "billedCostKnown": False,
        },
        "time": {
            "buildElapsed": build_elapsed,
            "buildElapsedSeconds": elapsed_seconds(build_elapsed),
            "endToEndPipelineElapsed": None,
            "endToEndMeasurementStatus": "not-recorded",
            "humanReviewMinutes": round(sum(review_minutes), 2) if timing_complete else None,
            "humanReviewMeasurementStatus": "complete" if timing_complete else "not-recorded",
        },
        "qualityReview": {
            "sampleSize": sample_count,
            "acceptedCount": accepted_count,
            "status": "complete" if review_complete else "human-review-pending",
            "records": sample_results,
        },
        "conclusions": {
            "costMeasured": True,
            "automaticQualityChecksMeasured": True,
            "humanQualityMeasured": review_complete,
            "humanReviewTimeMeasured": timing_complete,
            "safeToScaleFromThisPilot": review_complete,
            "nextStep": None if review_complete else "review-the-five-editorial-sample-records-and-record-duration",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    output = args.output or ROOT / config["reportPath"]
    report = build_report(config)
    if args.check:
        if not output.is_file() or read_json(output) != report:
            raise SystemExit(f"Pilot report is missing or stale: {output}")
        print(f"Pilot report is current: {report['status']}.")
        return
    write_json(output, report)
    print(f"Wrote pilot report: {output}")


if __name__ == "__main__":
    main()
