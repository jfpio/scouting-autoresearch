#!/usr/bin/env python3
"""Materialize a deterministic, review-only V1 taxonomy mapping proposal."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from common import ROOT, VAULT, load_markdown, read_json, sha256_bytes, write_json


PROPOSAL_PATH = VAULT / "exploration" / "taxonomy" / "idea-v1-broad-categories.md"
ANALYSIS_PATH = ROOT / "data" / "reports" / "taxonomy-v1-analysis.json"
REPORT_PATH = ROOT / "data" / "reports" / "taxonomy-v1-mapping-proposal.json"


def validate_proposal(proposal: dict[str, Any]) -> None:
    if proposal.get("proposalType") != "taxonomy":
        raise ValueError("V1 proposal must have proposalType: taxonomy")
    if proposal.get("status") != "proposed":
        raise ValueError("V1 proposal must remain proposed until human review")
    if proposal.get("sourceType") != "editorial-hypothesis":
        raise ValueError("V1 proposal must be marked as an editorial hypothesis")
    if proposal.get("reviewRequired") is not True:
        raise ValueError("V1 proposal must require human review")

    categories = proposal.get("categories") or []
    if not 10 <= len(categories) <= 15:
        raise ValueError("V1 proposal must contain between 10 and 15 broad categories")
    category_ids = [category.get("id") for category in categories]
    if len(set(category_ids)) != len(category_ids) or not all(category_ids):
        raise ValueError("V1 category IDs must be present and unique")
    for category in categories:
        if set((category.get("labels") or {}).keys()) != {"pl", "en"}:
            raise ValueError(f"Category {category.get('id')} lacks bilingual labels")
        if set((category.get("definition") or {}).keys()) != {"pl", "en"}:
            raise ValueError(f"Category {category.get('id')} lacks bilingual definitions")
        if not category.get("evidenceActivityIds") or not category.get("counterexampleActivityIds"):
            raise ValueError(f"Category {category.get('id')} lacks evidence or counterexamples")

    known = set(category_ids)
    rules = proposal.get("mappingRules") or {}
    for rule_group in ("sourceSections", "legacyTraitCategories"):
        for value, mapped_ids in (rules.get(rule_group) or {}).items():
            unknown = set(mapped_ids) - known
            if unknown:
                raise ValueError(f"Rule {rule_group}/{value} refers to unknown categories: {sorted(unknown)}")


def build_candidate_mappings(
    activities: list[dict[str, Any]],
    proposal: dict[str, Any],
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    validate_proposal(proposal)
    category_order = [category["id"] for category in proposal["categories"]]
    rules = proposal["mappingRules"]
    section_rules = rules.get("sourceSections") or {}
    legacy_rules = rules.get("legacyTraitCategories") or {}
    analysis_items = {item["activityId"]: item for item in analysis.get("items", [])}
    ambiguous_ids = {
        item["activityId"] for item in analysis.get("ambiguousAssignments", [])
    }
    outlier_ids = set((analysis.get("outliers") or {}).get("activityIds", []))
    manual_review_ids = set(proposal.get("manualReviewActivityIds") or [])

    mappings: list[dict[str, Any]] = []
    for activity in sorted(activities, key=lambda item: item["id"]):
        assigned: set[str] = set()
        basis: list[dict[str, Any]] = []
        section = activity.get("section")
        section_categories = list(section_rules.get(section, []))
        if section_categories:
            assigned.update(section_categories)
            basis.append({"field": "section", "value": section, "categoryIds": section_categories})

        for legacy_category in activity.get("traitCategories") or []:
            mapped_categories = list(legacy_rules.get(legacy_category, []))
            if mapped_categories:
                assigned.update(mapped_categories)
                basis.append(
                    {
                        "field": "traitCategories",
                        "value": legacy_category,
                        "categoryIds": mapped_categories,
                    }
                )

        flags: list[str] = []
        if activity["id"] in ambiguous_ids:
            flags.append("embedding-ambiguous")
        if activity["id"] in outlier_ids:
            flags.append("embedding-outlier")
        if activity["id"] in manual_review_ids:
            flags.append("editorial-boundary")
        technical = analysis_items.get(activity["id"], {})
        category_ids = [category_id for category_id in category_order if category_id in assigned]
        mappings.append(
            {
                "activityId": activity["id"],
                "sourceId": activity["sourceId"],
                "status": "proposed" if category_ids else "unassigned",
                "categoryIds": category_ids,
                "mappingBasis": basis,
                "sourceSection": section,
                "sourceTraits": list(activity.get("traits") or []),
                "legacyTraitCategories": list(activity.get("traitCategories") or []),
                "technicalClusterId": technical.get("technicalClusterId"),
                "reviewFlags": flags,
            }
        )
    return mappings


def build_proposal_report(
    activities: list[dict[str, Any]],
    proposal: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    mappings = build_candidate_mappings(activities, proposal, analysis)
    mappings_by_id = {mapping["activityId"]: mapping for mapping in mappings}
    for category in proposal["categories"]:
        category_id = category["id"]
        for activity_id in category["evidenceActivityIds"]:
            if activity_id not in mappings_by_id:
                raise ValueError(f"Unknown evidence activity {activity_id} for {category_id}")
            if category_id not in mappings_by_id[activity_id]["categoryIds"]:
                raise ValueError(f"Evidence activity {activity_id} is not mapped to {category_id}")
        for activity_id in category["counterexampleActivityIds"]:
            if activity_id not in mappings_by_id:
                raise ValueError(f"Unknown counterexample {activity_id} for {category_id}")
            if category_id in mappings_by_id[activity_id]["categoryIds"]:
                raise ValueError(f"Counterexample {activity_id} is mapped to {category_id}")
    unassigned = [item["activityId"] for item in mappings if not item["categoryIds"]]
    category_counts = Counter(
        category_id for item in mappings for category_id in item["categoryIds"]
    )
    category_ids = [category["id"] for category in proposal["categories"]]
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "pipeline": "taxonomy-v1-mapping-proposal",
        "status": "proposed",
        "proposalOnly": True,
        "reviewRequired": True,
        "productionTaxonomyChanged": False,
        "proposalId": proposal["id"],
        "proposalVersion": proposal["proposalVersion"],
        "createdAt": proposal["createdAt"],
        "sourceType": proposal["sourceType"],
        "categories": proposal["categories"],
        "mappingRules": proposal["mappingRules"],
        "coverage": {
            "totalActivities": len(mappings),
            "proposedMappedActivities": len(mappings) - len(unassigned),
            "unassignedActivities": len(unassigned),
            "unassignedActivityIds": unassigned,
            "categoryCounts": [
                {"categoryId": category_id, "activities": category_counts[category_id]}
                for category_id in category_ids
            ],
        },
        "technicalAnalysis": {
            "analysisHash": analysis.get("analysisHash"),
            "clusterCount": len(analysis.get("clusters", [])),
            "ambiguousActivityIds": sorted(
                item["activityId"] for item in analysis.get("ambiguousAssignments", [])
            ),
            "outlierActivityIds": sorted(
                (analysis.get("outliers") or {}).get("activityIds", [])
            ),
            "manualReviewActivityIds": sorted(proposal.get("manualReviewActivityIds") or []),
        },
        "mappings": mappings,
    }
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report["proposalHash"] = sha256_bytes(canonical.encode("utf-8"))
    return report


def load_activities() -> list[dict[str, Any]]:
    return [load_markdown(path)[0] for path in sorted((VAULT / "activities").glob("*.md"))]


def main() -> None:
    proposal, _ = load_markdown(PROPOSAL_PATH)
    analysis = read_json(ANALYSIS_PATH)
    report = build_proposal_report(load_activities(), proposal, analysis)
    write_json(REPORT_PATH, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "proposalVersion": report["proposalVersion"],
                "proposalHash": report["proposalHash"],
                "categories": len(report["categories"]),
                "coverage": report["coverage"],
                "ambiguousAssignments": len(
                    report["technicalAnalysis"]["ambiguousActivityIds"]
                ),
                "output": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
