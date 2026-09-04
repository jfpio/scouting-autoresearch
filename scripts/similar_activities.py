#!/usr/bin/env python3
"""Validate and materialize approved bidirectional links between similar activities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown, read_json


CONFIG_PATH = ROOT / "config" / "similar-activities.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_activity_metadata() -> dict[str, dict[str, Any]]:
    activities: dict[str, dict[str, Any]] = {}
    for path in sorted((VAULT / "activities").glob("*.md")):
        metadata, _ = load_markdown(path)
        activities[metadata["id"]] = metadata
    return activities


def relation_errors(
    config: dict[str, Any],
    activities: dict[str, dict[str, Any]],
    root: Path = ROOT,
) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(config.get("schemaVersion") == 1, "bad similar-activity schemaVersion")
    policy = config.get("policy") or {}
    require(policy.get("keepSeparateRecords") is True, "similar games may not be merged")
    require(policy.get("bidirectionalLinks") is True, "similar-game links are not bidirectional")
    require(policy.get("humanApprovalRequired") is True, "similar-game links lack a human gate")
    require(policy.get("exposeAlgorithmicCandidates") is False, "unreviewed candidates may be exposed")

    relation_ids: list[str] = []
    pairs: list[frozenset[str]] = []
    for relation in config.get("relations") or []:
        relation_id = relation.get("id") or "<missing-id>"
        relation_ids.append(relation_id)
        activity_ids = relation.get("activityIds") or []
        pair = frozenset(activity_ids)
        pairs.append(pair)
        require(relation.get("relationType") == "highly-similar-variant", f"{relation_id}: bad relationType")
        require(len(activity_ids) == 2 and len(pair) == 2, f"{relation_id}: relation must contain two distinct activities")
        require(relation.get("status") == "human-approved", f"{relation_id}: relation lacks human approval")
        decision = relation.get("humanDecision") or {}
        require(
            all(bool(decision.get(field)) for field in ("approvedBy", "approvedAt", "basis")),
            f"{relation_id}: human decision is incomplete",
        )
        notes = relation.get("notes") or {}
        require(all(bool(notes.get(locale)) for locale in ("pl", "en")), f"{relation_id}: bilingual notes are missing")
        for activity_id in activity_ids:
            require(activity_id in activities, f"{relation_id}: unknown activity {activity_id}")
            if activity_id in activities:
                require("game" in (activities[activity_id].get("kinds") or []), f"{relation_id}: {activity_id} is not a game")
        evidence = relation.get("evidence") or {}
        report_path = root / str(evidence.get("report", ""))
        require(report_path.is_file(), f"{relation_id}: evidence report is missing")
        if report_path.is_file() and len(activity_ids) == 2:
            report = read_json(report_path)
            require(
                evidence.get("algorithmVersion") == report.get("algorithmVersion"),
                f"{relation_id}: algorithm evidence is stale",
            )
            matching = [
                candidate
                for candidate in report.get("candidates") or []
                if {candidate.get("leftId"), candidate.get("rightId")} == set(activity_ids)
            ]
            require(len(matching) == 1, f"{relation_id}: pair is absent or repeated in evidence")
            if len(matching) == 1:
                require(
                    evidence.get("tfidfCosine") == matching[0].get("tfidfCosine"),
                    f"{relation_id}: similarity score evidence is stale",
                )
    require(len(relation_ids) == len(set(relation_ids)), "similar-activity relation IDs repeat")
    require(len(pairs) == len(set(pairs)), "similar-activity pairs repeat")
    return errors


def validate_similar_activity_relations() -> tuple[int, list[str]]:
    config = load_config()
    errors = relation_errors(config, load_activity_metadata())
    return len(config.get("relations") or []), errors


def add_similarity_links(records: list[dict[str, Any]], locale: str) -> None:
    config = load_config()
    lookup = {record["id"]: record for record in records}
    activity_view = {
        activity_id: {"id": activity_id, "sourceId": record["sourceId"], "kinds": record["kinds"]}
        for activity_id, record in lookup.items()
    }
    errors = relation_errors(config, activity_view)
    if errors:
        raise RuntimeError("Invalid similar-activity relations: " + "; ".join(errors))
    for relation in config.get("relations") or []:
        left_id, right_id = relation["activityIds"]
        for source_id, target_id in ((left_id, right_id), (right_id, left_id)):
            target = lookup[target_id]
            lookup[source_id].setdefault("similarActivities", []).append(
                {
                    "activityId": target_id,
                    "title": target["title"],
                    "sourceId": target["sourceId"],
                    "sourceTitle": target["sourceTitle"],
                    "author": target["author"],
                    "year": target["year"],
                    "relationType": relation["relationType"],
                    "note": relation["notes"][locale],
                    "url": (
                        f"https://jfpio.github.io/scouting-autoresearch/{'en/' if locale == 'en' else ''}"
                        f"activities/{target_id}/"
                    ),
                }
            )
    for record in records:
        if "similarActivities" in record:
            record["similarActivities"].sort(key=lambda item: item["activityId"])


def main() -> None:
    count, errors = validate_similar_activity_relations()
    if errors:
        print("Similar-activity validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Similar-activity validation passed: {count} approved relation(s).")


if __name__ == "__main__":
    main()
