#!/usr/bin/env python3
"""Audit source-text signals for proposed V3 participant-scale fields."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown, read_json, write_json


CONFIG_PATH = ROOT / "config" / "v3-participant-audit.yaml"
REPORT_PATH = ROOT / "data" / "reports" / "v3-participant-input-audit.json"
CHECKPOINT_PATH = ROOT / "data" / "checkpoints" / "v3-participant-input-audit.json"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schemaVersion") != 1:
        raise ValueError("Unsupported V3 participant-audit schema")
    if config.get("status") != "proposed":
        raise ValueError("V3 participant scales must remain proposed")
    if config.get("sourceType") != "editorial-hypothesis":
        raise ValueError("V3 participant scales lack the editorial-hypothesis marker")
    if config.get("corpusKind") != "game":
        raise ValueError("The first V3 participant audit must cover games only")
    if config.get("signalsAreAssignments") is not False:
        raise ValueError("Lexical signals may not become participant-scale assignments")
    if config.get("productionFieldsWritten") != []:
        raise ValueError("The V3 participant audit may not write production fields")
    if config.get("humanReviewRequired") is not True:
        raise ValueError("The V3 participant audit lacks a human-review gate")

    numeric_patterns = config.get("numericParticipantPatterns") or {}
    if set(numeric_patterns) != {"pl", "en"}:
        raise ValueError("The V3 participant audit lacks bilingual numeric patterns")
    for locale, entries in numeric_patterns.items():
        pattern_ids = [entry.get("id") for entry in entries]
        if not entries or len(pattern_ids) != len(set(pattern_ids)) or any(
            not value for value in pattern_ids
        ):
            raise ValueError(f"The V3 participant audit has bad {locale} numeric pattern IDs")
        for entry in entries:
            if not entry.get("regex"):
                raise ValueError(
                    f"The V3 participant audit has an empty {locale} numeric regex"
                )
            try:
                re.compile(str(entry["regex"]), flags=re.IGNORECASE)
            except re.error as error:
                raise ValueError(
                    f"The V3 participant audit has an invalid {locale} numeric regex"
                ) from error

    scales = config.get("scales") or []
    scale_ids = [scale.get("id") for scale in scales]
    if (
        not scales
        or len(scale_ids) != len(set(scale_ids))
        or any(not value for value in scale_ids)
    ):
        raise ValueError("V3 participant-scale IDs are missing or repeated")
    for scale in scales:
        if set((scale.get("labels") or {}).keys()) != {"pl", "en"}:
            raise ValueError(f"Participant scale {scale.get('id')} lacks bilingual labels")
        patterns = scale.get("patterns") or {}
        if set(patterns) != {"pl", "en"}:
            raise ValueError(f"Participant scale {scale.get('id')} lacks bilingual patterns")
        for locale, entries in patterns.items():
            pattern_ids = [entry.get("id") for entry in entries]
            if not entries or len(pattern_ids) != len(set(pattern_ids)) or any(
                not value for value in pattern_ids
            ):
                raise ValueError(f"Participant scale {scale.get('id')} has bad {locale} pattern IDs")
            for entry in entries:
                if not entry.get("regex"):
                    raise ValueError(
                        f"Participant scale {scale.get('id')} has an empty {locale} regex"
                    )
                try:
                    re.compile(str(entry["regex"]), flags=re.IGNORECASE)
                except re.error as error:
                    raise ValueError(
                        f"Participant scale {scale.get('id')} has an invalid {locale} regex"
                    ) from error


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    validate_config(config)
    return config


def strip_provenance_footer(body: str) -> str:
    return body.split("\n\n---\n", 1)[0].strip()


def load_game_records(vault: Path = VAULT) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((vault / "activities").glob("*.md")):
        metadata, body = load_markdown(path)
        if "game" not in (metadata.get("kinds") or []):
            continue
        records.append(
            {
                "activityId": metadata["id"],
                "sourceId": metadata["sourceId"],
                "sourceHash": metadata["sourceHash"],
                "originalLanguage": metadata["originalLanguage"],
                "body": strip_provenance_footer(body),
            }
        )
    return records


def build_report(config: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    validate_config(config)
    records = sorted(records, key=lambda item: item["activityId"])
    activity_ids = [record["activityId"] for record in records]
    if len(activity_ids) != len(set(activity_ids)):
        raise ValueError("V3 participant-audit corpus contains duplicate activity IDs")
    if any(record.get("originalLanguage") not in {"pl", "en"} for record in records):
        raise ValueError("V3 participant-audit corpus contains an unsupported source language")

    corpus_evidence = [
        {
            key: record[key]
            for key in ("activityId", "sourceId", "sourceHash", "originalLanguage")
        }
        for record in records
    ]
    matched_scales_by_activity: dict[str, list[str]] = {activity_id: [] for activity_id in activity_ids}
    scale_reports: list[dict[str, Any]] = []
    for scale in config["scales"]:
        matching_ids: list[str] = []
        pattern_counts: Counter[str] = Counter()
        for record in records:
            locale = record["originalLanguage"]
            matched_pattern_ids = [
                entry["id"]
                for entry in scale["patterns"][locale]
                if re.search(entry["regex"], record["body"], flags=re.IGNORECASE)
            ]
            if not matched_pattern_ids:
                continue
            matching_ids.append(record["activityId"])
            matched_scales_by_activity[record["activityId"]].append(scale["id"])
            pattern_counts.update(matched_pattern_ids)
        scale_reports.append(
            {
                "scaleId": scale["id"],
                "labels": scale["labels"],
                "activityCount": len(matching_ids),
                "coverageFraction": round(len(matching_ids) / len(records), 6) if records else 0,
                "activityIds": matching_ids,
                "patternCounts": [
                    {"patternId": pattern_id, "activityCount": count}
                    for pattern_id, count in sorted(pattern_counts.items())
                ],
            }
        )

    any_signal_ids = sorted(
        activity_id for activity_id, scales in matched_scales_by_activity.items() if scales
    )
    no_signal_ids = sorted(set(activity_ids) - set(any_signal_ids))
    multiple_signal_ids = sorted(
        activity_id
        for activity_id, scales in matched_scales_by_activity.items()
        if len(scales) > 1
    )
    source_counts = Counter(record["sourceId"] for record in records)
    language_counts = Counter(record["originalLanguage"] for record in records)
    numeric_signal_ids: list[str] = []
    numeric_pattern_counts: Counter[str] = Counter()
    for record in records:
        matched_pattern_ids = [
            entry["id"]
            for entry in config["numericParticipantPatterns"][record["originalLanguage"]]
            if re.search(entry["regex"], record["body"], flags=re.IGNORECASE)
        ]
        if matched_pattern_ids:
            numeric_signal_ids.append(record["activityId"])
            numeric_pattern_counts.update(matched_pattern_ids)
    return {
        "schemaVersion": 1,
        "pipeline": "v3-participant-input-audit",
        "auditId": config["auditId"],
        "status": "human-review-required",
        "proposalOnly": True,
        "humanReviewRequired": True,
        "interpretation": "lexical-signal-coverage-not-classification",
        "signalsAreAssignments": False,
        "productionFieldsWritten": [],
        "execution": {
            "externalApiRequests": 0,
            "model": None,
            "referenceCostUsd": 0,
        },
        "configHash": canonical_hash(config),
        "corpusDigest": canonical_hash(corpus_evidence),
        "corpus": {
            "kind": config["corpusKind"],
            "activityCount": len(records),
            "activityIds": activity_ids,
            "sourceCounts": dict(sorted(source_counts.items())),
            "languageCounts": dict(sorted(language_counts.items())),
        },
        "lexicalSignalCoverage": {
            "activitiesWithAnySignal": len(any_signal_ids),
            "activityIdsWithAnySignal": any_signal_ids,
            "activitiesWithoutSignal": len(no_signal_ids),
            "activityIdsWithoutSignal": no_signal_ids,
            "activitiesWithMultipleScaleSignals": len(multiple_signal_ids),
            "activityIdsWithMultipleScaleSignals": multiple_signal_ids,
        },
        "numericParticipantSignals": {
            "interpretation": "candidate-mentions-not-total-participant-bounds",
            "activityCount": len(numeric_signal_ids),
            "coverageFraction": round(len(numeric_signal_ids) / len(records), 6)
            if records
            else 0,
            "activityIds": numeric_signal_ids,
            "patternCounts": [
                {"patternId": pattern_id, "activityCount": count}
                for pattern_id, count in sorted(numeric_pattern_counts.items())
            ],
            "minParticipantsWritten": False,
            "maxParticipantsWritten": False,
        },
        "scales": scale_reports,
        "nextStep": "human-review-scale-definitions-and-a-representative-sample-before-schema-or-filter-changes",
    }


def build_checkpoint(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "pipeline": report["pipeline"],
        "status": report["status"],
        "auditId": report["auditId"],
        "configHash": report["configHash"],
        "corpusDigest": report["corpusDigest"],
        "gameCount": report["corpus"]["activityCount"],
        "reportHash": canonical_hash(report),
        "reportPath": str(REPORT_PATH.relative_to(ROOT)),
        "humanReviewRequired": True,
        "productionFieldsWritten": [],
        "externalApiRequests": report["execution"]["externalApiRequests"],
        "referenceCostUsd": report["execution"]["referenceCostUsd"],
        "nextStep": report["nextStep"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report(load_config(), load_game_records())
    checkpoint = build_checkpoint(report)
    if args.check:
        if not REPORT_PATH.is_file() or read_json(REPORT_PATH) != report:
            raise SystemExit(f"V3 participant audit is missing or stale: {REPORT_PATH}")
        if not CHECKPOINT_PATH.is_file() or read_json(CHECKPOINT_PATH) != checkpoint:
            raise SystemExit(f"V3 participant checkpoint is missing or stale: {CHECKPOINT_PATH}")
        print(
            f"V3 participant audit is current: {report['corpus']['activityCount']} games, "
            f"{report['lexicalSignalCoverage']['activitiesWithAnySignal']} with lexical signals."
        )
        return
    write_json(REPORT_PATH, report)
    write_json(CHECKPOINT_PATH, checkpoint)
    print(
        f"Wrote V3 participant audit for {report['corpus']['activityCount']} games; "
        f"{report['lexicalSignalCoverage']['activitiesWithAnySignal']} have lexical signals."
    )


if __name__ == "__main__":
    main()
