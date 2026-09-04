#!/usr/bin/env python3
"""Prepare a source-independent, human-gated editorial review record."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, dump_markdown, load_markdown, source_hash


CONFIG_PATH = ROOT / "config" / "editorial-review.yaml"
DEFAULT_REVIEW_DIR = VAULT / "reviews" / "editorial" / "inbox"


def load_editorial_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if config.get("schemaVersion") != 1 or not config.get("frameworkVersion"):
        raise ValueError("Unsupported or incomplete editorial-review configuration")
    return config


def build_pending_review(activity_path: Path, config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    activity, body = load_markdown(activity_path)
    activity_id = activity.get("id")
    if not activity_id or activity_id != activity_path.stem:
        raise ValueError(f"Invalid activity ID in {activity_path}")
    actual_hash = source_hash(str(activity.get("title", "")), body)
    if activity.get("sourceHash") != actual_hash:
        raise ValueError(f"Stale sourceHash in {activity_path}")

    defaults = config["pendingDefaults"]
    dimensions = config["valueReview"]["dimensions"]
    metadata = {
        "id": f"editorial-review-{activity_id}",
        "recordType": "activity-editorial-review",
        "schemaVersion": 1,
        "frameworkVersion": config["frameworkVersion"],
        "status": "editorial-review",
        "reviewRequired": True,
        "activityId": activity_id,
        "activityPath": str(activity_path.relative_to(ROOT)),
        "sourceId": activity.get("sourceId"),
        "sourceHash": actual_hash,
        "valueReview": {
            "outcome": defaults["valueOutcome"],
            "ratings": {dimension: None for dimension in dimensions},
            "notes": [],
        },
        "safetyReview": {
            "outcome": defaults["safetyOutcome"],
            "riskAreas": [],
            "controls": [],
            "notes": [],
        },
        "publicationRecommendation": defaults["publicationRecommendation"],
        "humanApproved": False,
        "separationChecks": {
            "rightsDecisionChanged": False,
            "sourceTextChanged": False,
            "translationChanged": False,
        },
    }
    review_body = (
        "## Wartość redakcyjna\n\n"
        "Do oceny przez człowieka. Oceniaj użyteczność aktywności, a nie wiarygodność "
        "lub status prawny źródła.\n\n"
        "## Bezpieczeństwo\n\n"
        "Do oceny przez człowieka. Ryzyka i środki kontroli zapisuj bez zmiany tekstu "
        "historycznego.\n\n"
        "## Rekomendacja publikacyjna\n\n"
        "Do decyzji przez człowieka. Ten rekord sam nie publikuje, nie usuwa i nie "
        "modyfikuje aktywności."
    )
    return metadata, review_body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    activity_path = VAULT / "activities" / f"{args.activity_id}.md"
    if not activity_path.is_file():
        raise SystemExit(f"Unknown activity: {args.activity_id}")
    output = args.output or DEFAULT_REVIEW_DIR / f"{args.activity_id}.md"
    if output.exists():
        existing, _ = load_markdown(output)
        source, body = load_markdown(activity_path)
        current_hash = source_hash(str(source.get("title", "")), body)
        if existing.get("sourceHash") != current_hash:
            raise SystemExit(f"Existing review is stale and was not overwritten: {output}")
        raise SystemExit(f"Review already exists and was not overwritten: {output}")
    metadata, body = build_pending_review(activity_path, load_editorial_config())
    dump_markdown(output, metadata, body)
    print(f"Prepared pending editorial review: {output}")


if __name__ == "__main__":
    main()
