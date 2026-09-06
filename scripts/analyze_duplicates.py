#!/usr/bin/env python3
"""Propose near-duplicate activity pairs for human review without merging records."""

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

from common import ROOT, VAULT, load_markdown, write_json


CONFIG_PATH = ROOT / "config" / "near-duplicates.yaml"
REPORT_PATH = ROOT / "data" / "reports" / "near-duplicates.json"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if config.get("schemaVersion") != 1:
        raise ValueError("Unsupported near-duplicate configuration")
    if config.get("automaticMerge") is not False:
        raise ValueError("Near-duplicate analysis cannot enable automatic merging")
    return config


def strip_provenance_footer(body: str) -> str:
    return body.split("\n\n---\n", 1)[0].strip()


def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", value.casefold())


def terms(title: str, body: str, title_repetitions: int) -> Counter[str]:
    tokens = tokenize(((title + " ") * title_repetitions) + strip_provenance_footer(body))
    values = list(tokens)
    values.extend(f"{tokens[index]} {tokens[index + 1]}" for index in range(len(tokens) - 1))
    return Counter(values)


def comparison_record(activity_path: Path, locale: str) -> dict[str, Any]:
    activity, source_body = load_markdown(activity_path)
    if activity.get("originalLanguage") == locale:
        title = activity.get("title")
        body = source_body
        comparison_path = activity_path
        comparison_kind = "source-text"
    else:
        comparison_path = VAULT / "translations" / locale / activity_path.name
        translation, body = load_markdown(comparison_path)
        if translation.get("activityId") != activity.get("id") or translation.get("locale") != locale:
            raise ValueError(f"Mismatched comparison translation: {comparison_path}")
        if translation.get("sourceHash") != activity.get("sourceHash"):
            raise ValueError(f"Stale comparison translation: {comparison_path}")
        title = translation.get("title")
        comparison_kind = "machine-translation"
    canonical_text = f"{str(title).strip()}\n{strip_provenance_footer(body)}\n"
    return {
        "activityId": activity["id"],
        "sourceId": activity["sourceId"],
        "sourceHash": activity["sourceHash"],
        "title": title,
        "comparisonKind": comparison_kind,
        "comparisonPath": str(comparison_path.relative_to(ROOT)),
        "comparisonHash": hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
        "body": body,
    }


def normalized_vectors(records: list[dict[str, Any]], title_repetitions: int) -> dict[str, dict[str, float]]:
    counts = {
        record["activityId"]: terms(record["title"], record["body"], title_repetitions)
        for record in records
    }
    document_frequency = Counter(term for counter in counts.values() for term in counter)
    document_count = len(records)
    vectors: dict[str, dict[str, float]] = {}
    for activity_id, counter in counts.items():
        weights = {
            term: (1 + math.log(frequency))
            * (1 + math.log((document_count + 1) / (document_frequency[term] + 1)))
            for term, frequency in counter.items()
        }
        norm = math.sqrt(sum(weight * weight for weight in weights.values()))
        vectors[activity_id] = {
            term: weight / norm for term, weight in weights.items()
        } if norm else {}
    return vectors


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(weight * right.get(term, 0.0) for term, weight in left.items())


def build_report(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    locale = config["comparisonLocale"]
    records = [
        comparison_record(path, locale)
        for path in sorted((VAULT / "activities").glob("*.md"))
    ]
    vectors = normalized_vectors(records, int(config["titleRepetitions"]))
    candidates: list[dict[str, Any]] = []
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            if config["crossSourceOnly"] and left["sourceId"] == right["sourceId"]:
                continue
            score = cosine(vectors[left["activityId"]], vectors[right["activityId"]])
            if score < float(config["candidateThreshold"]):
                continue
            candidates.append(
                {
                    "leftId": left["activityId"],
                    "leftSourceId": left["sourceId"],
                    "leftTitle": left["title"],
                    "rightId": right["activityId"],
                    "rightSourceId": right["sourceId"],
                    "rightTitle": right["title"],
                    "tfidfCosine": round(score, 8),
                    "decision": "human-review-required",
                }
            )
    candidates.sort(key=lambda item: (-item["tfidfCosine"], item["leftId"], item["rightId"]))
    candidates = candidates[: int(config["maxCandidates"])]
    corpus_evidence = [
        {
            key: record[key]
            for key in (
                "activityId",
                "sourceId",
                "sourceHash",
                "comparisonKind",
                "comparisonPath",
                "comparisonHash",
            )
        }
        for record in records
    ]
    corpus_digest = hashlib.sha256(
        json.dumps(corpus_evidence, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schemaVersion": 1,
        "algorithmVersion": config["algorithmVersion"],
        "comparisonLocale": locale,
        "crossSourceOnly": config["crossSourceOnly"],
        "activityCount": len(records),
        "corpusDigest": corpus_digest,
        "candidateThreshold": config["candidateThreshold"],
        "maxCandidates": config["maxCandidates"],
        "candidateCount": len(candidates),
        "candidates": candidates,
        "automaticMerges": [],
        "proposalOnly": True,
        "reviewRequired": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.check:
        if not args.output.is_file() or json.loads(args.output.read_text(encoding="utf-8")) != report:
            raise SystemExit(f"Near-duplicate report is missing or stale: {args.output}")
        print(f"Near-duplicate report is current: {report['candidateCount']} candidate(s).")
        return
    write_json(args.output, report)
    print(f"Wrote {report['candidateCount']} near-duplicate candidate(s) to {args.output}")


if __name__ == "__main__":
    main()
