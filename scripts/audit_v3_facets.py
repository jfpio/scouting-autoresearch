#!/usr/bin/env python3
"""Audit source-text evidence for proposed practical V3 game facets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown, read_json, write_json


CONFIG_PATH = ROOT / "config" / "v3-facet-audit.yaml"
REPORT_PATH = ROOT / "data" / "reports" / "v3-practical-facet-audit.json"
CHECKPOINT_PATH = ROOT / "data" / "checkpoints" / "v3-practical-facet-audit.json"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_patterns(
    entries: list[dict[str, Any]], locale: str, dimension_id: str, value_id: str
) -> None:
    pattern_ids = [entry.get("id") for entry in entries]
    if not entries or len(pattern_ids) != len(set(pattern_ids)) or any(
        not pattern_id for pattern_id in pattern_ids
    ):
        raise ValueError(
            f"Facet {dimension_id}/{value_id} has missing or repeated {locale} pattern IDs"
        )
    for entry in entries:
        if not entry.get("regex"):
            raise ValueError(
                f"Facet {dimension_id}/{value_id} has an empty {locale} regex"
            )
        try:
            re.compile(str(entry["regex"]), flags=re.IGNORECASE)
        except re.error as error:
            raise ValueError(
                f"Facet {dimension_id}/{value_id} has an invalid {locale} regex"
            ) from error


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schemaVersion") != 1:
        raise ValueError("Unsupported V3 facet-audit schema")
    if config.get("status") != "proposed":
        raise ValueError("V3 practical facets must remain proposed")
    if config.get("sourceType") != "editorial-hypothesis":
        raise ValueError("V3 practical facets lack the editorial-hypothesis marker")
    if config.get("corpusKind") != "game":
        raise ValueError("The first V3 facet audit must cover games only")
    if config.get("signalsAreAssignments") is not False:
        raise ValueError("Lexical signals may not become practical-facet assignments")
    if config.get("productionFieldsWritten") != []:
        raise ValueError("The V3 facet audit may not write production fields")
    if config.get("humanReviewRequired") is not True:
        raise ValueError("The V3 facet audit lacks a human-review gate")
    for key in ("samplePerValue", "sampleWithoutSignal"):
        if not isinstance(config.get(key), int) or int(config[key]) < 1:
            raise ValueError(f"The V3 facet audit has an invalid {key}")

    rubric = config.get("searchValueRubric") or {}
    if rubric.get("status") != "human-rating-required":
        raise ValueError("Search-value assessment must remain human-rated")
    if rubric.get("scale") != [0, 1, 2]:
        raise ValueError("Search-value rubric must use the documented 0-2 scale")
    criteria = rubric.get("criteria") or []
    criterion_ids = [criterion.get("id") for criterion in criteria]
    if not criteria or len(criterion_ids) != len(set(criterion_ids)):
        raise ValueError("Search-value rubric criteria are missing or repeated")
    for criterion in criteria:
        if set((criterion.get("labels") or {}).keys()) != {"pl", "en"}:
            raise ValueError(f"Rubric criterion {criterion.get('id')} lacks labels")

    dimensions = config.get("dimensions") or []
    dimension_ids = [dimension.get("id") for dimension in dimensions]
    if not dimensions or len(dimension_ids) != len(set(dimension_ids)) or any(
        not dimension_id for dimension_id in dimension_ids
    ):
        raise ValueError("V3 practical-facet IDs are missing or repeated")
    allowed_uses = {"feasibility-filter", "exploration-facet", "human-review-only"}
    for dimension in dimensions:
        dimension_id = str(dimension.get("id"))
        if set((dimension.get("labels") or {}).keys()) != {"pl", "en"}:
            raise ValueError(f"Facet {dimension_id} lacks bilingual labels")
        if dimension.get("intendedUse") not in allowed_uses:
            raise ValueError(f"Facet {dimension_id} has an unsupported intended use")
        values = dimension.get("values") or []
        value_ids = [value.get("id") for value in values]
        if not values or len(value_ids) != len(set(value_ids)) or any(
            not value_id for value_id in value_ids
        ):
            raise ValueError(f"Facet {dimension_id} values are missing or repeated")
        pattern_ids: list[str] = []
        for value in values:
            value_id = str(value.get("id"))
            if set((value.get("labels") or {}).keys()) != {"pl", "en"}:
                raise ValueError(f"Facet {dimension_id}/{value_id} lacks bilingual labels")
            patterns = value.get("patterns") or {}
            if set(patterns.keys()) != {"pl", "en"}:
                raise ValueError(f"Facet {dimension_id}/{value_id} lacks bilingual patterns")
            for locale, entries in patterns.items():
                _validate_patterns(entries, locale, dimension_id, value_id)
                pattern_ids.extend(str(entry["id"]) for entry in entries)
        if len(pattern_ids) != len(set(pattern_ids)):
            raise ValueError(f"Facet {dimension_id} repeats a pattern ID")


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
        title = str(metadata.get("title") or "").strip()
        source_body = strip_provenance_footer(body)
        records.append(
            {
                "activityId": metadata["id"],
                "sourceId": metadata["sourceId"],
                "sourceHash": metadata["sourceHash"],
                "originalLanguage": metadata["originalLanguage"],
                "title": title,
                "text": f"{title}\n\n{source_body}".strip(),
            }
        )
    return records


def deterministic_sample(values: list[str], count: int, salt: str) -> list[str]:
    return sorted(
        sorted(
            set(values),
            key=lambda value: (
                hashlib.sha256(f"{salt}\0{value}".encode("utf-8")).hexdigest(),
                value,
            ),
        )[:count]
    )


def normalized_entropy(counts: list[int], configured_value_count: int) -> float:
    total = sum(counts)
    if total == 0 or configured_value_count <= 1:
        return 0.0
    probabilities = [count / total for count in counts if count]
    entropy = -sum(probability * math.log(probability) for probability in probabilities)
    return round(entropy / math.log(configured_value_count), 6)


def _coverage_by(
    records: list[dict[str, Any]], signaled_ids: set[str], key: str
) -> list[dict[str, Any]]:
    totals = Counter(str(record[key]) for record in records)
    signaled = Counter(
        str(record[key]) for record in records if record["activityId"] in signaled_ids
    )
    return [
        {
            key: value,
            "activityCount": totals[value],
            "activitiesWithSignal": signaled[value],
            "coverageFraction": round(signaled[value] / totals[value], 6),
        }
        for value in sorted(totals)
    ]


def build_dimension_report(
    dimension: dict[str, Any],
    records: list[dict[str, Any]],
    sample_per_value: int,
    sample_without_signal: int,
) -> dict[str, Any]:
    value_ids_by_activity: dict[str, list[str]] = {
        str(record["activityId"]): [] for record in records
    }
    value_reports: list[dict[str, Any]] = []
    value_counts: list[int] = []
    pattern_hit_total = 0
    for value in dimension["values"]:
        matching_ids: list[str] = []
        pattern_counts: Counter[str] = Counter()
        for record in records:
            locale = str(record["originalLanguage"])
            matched_patterns = [
                str(pattern["id"])
                for pattern in value["patterns"][locale]
                if re.search(str(pattern["regex"]), str(record["text"]), flags=re.IGNORECASE)
            ]
            if not matched_patterns:
                continue
            activity_id = str(record["activityId"])
            matching_ids.append(activity_id)
            value_ids_by_activity[activity_id].append(str(value["id"]))
            pattern_counts.update(matched_patterns)
            pattern_hit_total += len(matched_patterns)
        matching_ids.sort()
        value_counts.append(len(matching_ids))
        value_reports.append(
            {
                "valueId": value["id"],
                "labels": value["labels"],
                "activityCount": len(matching_ids),
                "coverageFraction": round(len(matching_ids) / len(records), 6)
                if records
                else 0,
                "activityIds": matching_ids,
                "reviewSampleActivityIds": deterministic_sample(
                    matching_ids,
                    sample_per_value,
                    f"{dimension['id']}:{value['id']}:with-signal",
                ),
                "patternCounts": [
                    {"patternId": pattern_id, "activityCount": count}
                    for pattern_id, count in sorted(pattern_counts.items())
                ],
            }
        )

    signaled_ids = sorted(
        activity_id for activity_id, values in value_ids_by_activity.items() if values
    )
    signaled_set = set(signaled_ids)
    no_signal_ids = sorted(set(value_ids_by_activity) - signaled_set)
    multi_value_ids = sorted(
        activity_id
        for activity_id, values in value_ids_by_activity.items()
        if len(values) > 1
    )
    nonzero_counts = [count for count in value_counts if count]
    dominant_share = round(max(nonzero_counts) / sum(nonzero_counts), 6) if nonzero_counts else 0
    return {
        "dimensionId": dimension["id"],
        "labels": dimension["labels"],
        "intendedUseHypothesis": dimension["intendedUse"],
        "interpretation": "lexical-evidence-candidates-not-facet-assignments",
        "signalCoverage": {
            "activityCount": len(signaled_ids),
            "coverageFraction": round(len(signaled_ids) / len(records), 6)
            if records
            else 0,
            "activityIds": signaled_ids,
            "activitiesWithoutSignal": len(no_signal_ids),
            "activityIdsWithoutSignal": no_signal_ids,
            "bySource": _coverage_by(records, signaled_set, "sourceId"),
            "byLanguage": _coverage_by(records, signaled_set, "originalLanguage"),
        },
        "ambiguityProxy": {
            "interpretation": "multiple-value-signals-require-review-but-are-not-necessarily-conflicts",
            "activitiesWithMultipleValueSignals": len(multi_value_ids),
            "fractionOfCorpus": round(len(multi_value_ids) / len(records), 6)
            if records
            else 0,
            "activityIds": multi_value_ids,
            "reviewSampleActivityIds": deterministic_sample(
                multi_value_ids,
                sample_without_signal,
                f"{dimension['id']}:multi-value",
            ),
        },
        "editorialCostProxy": {
            "interpretation": "record-count-workload-not-time-or-money-estimate",
            "candidateEvidenceRecordsToVerify": len(signaled_ids),
            "coldReadRecordsWithoutSignal": len(no_signal_ids),
            "multiValueRecordsNeedingInterpretation": len(multi_value_ids),
            "lexicalPatternHitsToVerify": pattern_hit_total,
            "manualVerificationRequiredForEveryAssignment": True,
            "estimatedMinutes": None,
        },
        "searchDifferentiationProxy": {
            "interpretation": "signal-distribution-proxy-not-observed-user-value",
            "configuredValueCount": len(dimension["values"]),
            "valuesWithSignals": sum(count > 0 for count in value_counts),
            "dominantValueShareOfSignalAssignments": dominant_share,
            "normalizedSignalEntropy": normalized_entropy(
                value_counts, len(dimension["values"])
            ),
        },
        "humanSearchValueAssessment": {
            "status": "human-rating-required",
            "scores": None,
        },
        "reviewSamples": {
            "withoutSignalActivityIds": deterministic_sample(
                no_signal_ids,
                sample_without_signal,
                f"{dimension['id']}:without-signal",
            )
        },
        "values": value_reports,
    }


def build_report(config: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    validate_config(config)
    records = sorted(records, key=lambda record: str(record["activityId"]))
    activity_ids = [str(record["activityId"]) for record in records]
    if len(activity_ids) != len(set(activity_ids)):
        raise ValueError("V3 facet-audit corpus contains duplicate activity IDs")
    if any(record.get("originalLanguage") not in {"pl", "en"} for record in records):
        raise ValueError("V3 facet-audit corpus contains an unsupported source language")

    corpus_evidence = [
        {
            key: record[key]
            for key in ("activityId", "sourceId", "sourceHash", "originalLanguage", "title")
        }
        for record in records
    ]
    source_counts = Counter(str(record["sourceId"]) for record in records)
    language_counts = Counter(str(record["originalLanguage"]) for record in records)
    dimensions = [
        build_dimension_report(
            dimension,
            records,
            int(config["samplePerValue"]),
            int(config["sampleWithoutSignal"]),
        )
        for dimension in config["dimensions"]
    ]
    return {
        "schemaVersion": 1,
        "pipeline": "v3-practical-facet-audit",
        "auditId": config["auditId"],
        "status": "human-review-required",
        "proposalOnly": True,
        "humanReviewRequired": True,
        "signalsAreAssignments": False,
        "productionFieldsWritten": [],
        "execution": {"externalApiRequests": 0, "model": None, "referenceCostUsd": 0},
        "configHash": canonical_hash(config),
        "corpusDigest": canonical_hash(corpus_evidence),
        "corpus": {
            "kind": config["corpusKind"],
            "activityCount": len(records),
            "activityIds": activity_ids,
            "sourceCounts": dict(sorted(source_counts.items())),
            "languageCounts": dict(sorted(language_counts.items())),
        },
        "method": {
            "textScope": "source-title-and-source-body-without-provenance-footer",
            "lexicalSignalsOnly": True,
            "absenceIsNotNegativeEvidence": True,
            "multiValueSignalsAreNotNecessarilyConflicts": True,
            "searchDifferentiationIsNotObservedUserValue": True,
            "humanSearchValueRubric": config["searchValueRubric"],
        },
        "dimensions": dimensions,
        "decisionGate": {
            "status": "human-review-required",
            "requiredBeforeProduction": [
                "review-samples-and-pattern-precision",
                "rate-search-value-rubric",
                "select-or-reject-dimensions",
                "approve-field-definitions-and-values",
            ],
        },
        "nextStep": "human-review-facet-samples-and-search-value-before-schema-or-filter-changes",
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
        "dimensionCount": len(report["dimensions"]),
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
            raise SystemExit(f"V3 facet audit is missing or stale: {REPORT_PATH}")
        if not CHECKPOINT_PATH.is_file() or read_json(CHECKPOINT_PATH) != checkpoint:
            raise SystemExit(f"V3 facet checkpoint is missing or stale: {CHECKPOINT_PATH}")
        print(
            f"V3 practical-facet audit is current: {report['corpus']['activityCount']} games, "
            f"{len(report['dimensions'])} dimensions."
        )
        return
    write_json(REPORT_PATH, report)
    write_json(CHECKPOINT_PATH, checkpoint)
    print(
        f"Wrote V3 practical-facet audit for {report['corpus']['activityCount']} games and "
        f"{len(report['dimensions'])} dimensions."
    )


if __name__ == "__main__":
    main()
