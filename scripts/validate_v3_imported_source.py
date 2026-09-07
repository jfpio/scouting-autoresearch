#!/usr/bin/env python3
"""Validate one imported V3 source without requiring rebuilt corpus-wide artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import ROOT, VAULT, load_markdown, read_json, source_hash
from translate import current_translation


def imported_source_errors(source_id: str) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    source_path = VAULT / "sources" / f"{source_id}.md"
    require(source_path.is_file(), "source record is missing")
    if not source_path.is_file():
        return errors
    source, _ = load_markdown(source_path)
    revision = str(source.get("sourceRevision") or "").removeprefix("sha256:")
    report_path = ROOT / str(source.get("extractionReport") or "")
    require(report_path.is_file(), "extraction report is missing")
    if not report_path.is_file():
        return errors
    report = read_json(report_path)
    activity_paths = []
    for path in sorted((VAULT / "activities").glob("*.md")):
        metadata, _ = load_markdown(path)
        if metadata.get("sourceId") == source_id:
            activity_paths.append(path)
    activity_ids = [path.stem for path in activity_paths]
    report_ids = sorted(item.get("id") for item in report.get("activities") or [])
    require(report.get("sourceId") == source_id, "extraction report has another source ID")
    require(report.get("sourceSha256") == revision, "source revision differs from extraction report")
    require(report.get("activityCount") == len(activity_ids), "extraction activity count is stale")
    require(report_ids == activity_ids, "extraction activity IDs differ from vault records")
    require(report.get("wholeSourceCopiedToRepository") is False, "report claims whole-source copy")
    require(not (report.get("deduplication") or {}).get("exactBodyMatches"), "exact duplicate was imported")

    policy = source.get("translationPolicy") or {}
    target_locale = str(policy.get("targetLocale") or "")
    model = str(policy.get("modelRequested") or "")
    prompt = str(policy.get("promptVersion") or "")
    for path in activity_paths:
        metadata, body = load_markdown(path)
        require(metadata.get("id") == path.stem, f"{path.stem}: ID/path mismatch")
        require(metadata.get("kinds") == ["game"], f"{path.stem}: not a single game")
        require(metadata.get("rightsStatus") == "public-domain", f"{path.stem}: rights are not public-domain")
        require(bool(metadata.get("printedPages")), f"{path.stem}: printed pages are missing")
        require(
            bool(metadata.get("digitalEditionUrl")),
            f"{path.stem}: digital edition URL is missing",
        )
        require(bool(metadata.get("facsimileUrl")), f"{path.stem}: facsimile URL is missing")
        require(
            str(metadata.get("sourceRevision") or "").removeprefix("sha256:") == revision,
            f"{path.stem}: source revision is stale",
        )
        expected_hash = source_hash(str(metadata.get("title") or ""), body)
        require(metadata.get("sourceHash") == expected_hash, f"{path.stem}: source hash is stale")
        translation_path = VAULT / "translations" / target_locale / path.name
        require(
            current_translation(
                translation_path,
                expected_hash,
                expected_locale=target_locale,
                expected_model=model,
                expected_prompt=prompt,
                expected_reasoning_mode=str(policy.get("reasoningMode") or ""),
                expected_billing_mode=str(policy.get("billingMode") or ""),
                usage_required=policy.get("usageRequired") is True,
                request_budget_required=policy.get("requestBudgetRequired") is True,
            ),
            f"{path.stem}: translation is missing or stale",
        )

    translation_report_path = ROOT / str(policy.get("report") or "")
    require(translation_report_path.is_file(), "translation report is missing")
    if translation_report_path.is_file():
        translation_report = read_json(translation_report_path)
        require(translation_report.get("status") == "complete", "translation report is incomplete")
        require(
            translation_report.get("selectedActivityIds") == activity_ids
            and translation_report.get("completedActivityIds") == activity_ids
            and translation_report.get("pendingActivityIds") == [],
            "translation report selection differs from imported activities",
        )
        require(
            translation_report.get("modelRequested") == model
            and translation_report.get("promptVersion") == prompt,
            "translation report model or prompt is stale",
        )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_id")
    args = parser.parse_args()
    errors = imported_source_errors(args.source_id)
    if errors:
        raise SystemExit("\n".join(errors))
    source = read_json(
        ROOT / "data" / "reports" / f"{args.source_id}-extraction.json"
    )
    print(f"V3 source validation passed: {args.source_id}, {source['activityCount']} games")


if __name__ == "__main__":
    main()
