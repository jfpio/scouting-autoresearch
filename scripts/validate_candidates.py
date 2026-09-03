#!/usr/bin/env python3
"""Validate V2 source-candidate records across the human review lifecycle."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown


CANDIDATE_DIRS = {
    "inbox": VAULT / "reviews" / "inbox",
    "accepted": VAULT / "reviews" / "accepted",
}
REGISTRY_PATH = ROOT / "config" / "source-registry.yaml"
PG_LIFE_PLUS_70_POLICY_ID = "project-gutenberg-pd-usa-plus-life-70"
PG_LIFE_PLUS_70_CONDITIONS = {
    "catalog-claim-public-domain-in-the-usa",
    "relevant-natural-authors-identified",
    "seventy-full-calendar-years-after-last-relevant-author-death",
}


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {item["id"]: item for item in payload.get("collections", [])}


def registry_errors(registry: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for collection_id, collection in registry.items():
        policy = collection.get("rightsPresumption")
        if collection.get("status") == "approved-by-policy" and not isinstance(policy, dict):
            errors.append(f"{collection_id}: approved collection lacks rightsPresumption")
            continue
        if not isinstance(policy, dict):
            continue
        for field in ("id", "conditions", "resultRightsStatus", "approvedBy", "approvedAt"):
            if not policy.get(field):
                errors.append(f"{collection_id}: rightsPresumption lacks {field}")
        if policy.get("humanApproved") is not True:
            errors.append(f"{collection_id}: rightsPresumption lacks human approval")
        if not policy.get("jurisdictions"):
            errors.append(f"{collection_id}: rightsPresumption lacks jurisdictions")
        if "documented-download" not in collection.get("allowedMethods", []):
            errors.append(f"{collection_id}: policy-approved collection cannot download")
        if policy.get("id") == PG_LIFE_PLUS_70_POLICY_ID:
            if not PG_LIFE_PLUS_70_CONDITIONS.issubset(set(policy.get("conditions") or [])):
                errors.append(f"{collection_id}: life-plus-70 conditions are incomplete")
            if policy.get("resultRightsStatus") != "public-domain":
                errors.append(f"{collection_id}: life-plus-70 result is not public-domain")
            if (
                policy.get("termCalculation")
                != "first-january-after-seventy-full-years-from-death-year"
            ):
                errors.append(f"{collection_id}: life-plus-70 calculation rule is invalid")
    return errors


def life_plus_70_policy_is_satisfied(rights: dict[str, Any]) -> bool:
    calculation = rights.get("calculation") or {}
    relevant_authors = calculation.get("relevantAuthors") or []
    if rights.get("catalogClaim") != "public-domain-in-the-usa" or not relevant_authors:
        return False
    try:
        death_dates = []
        for author in relevant_authors:
            if not author.get("name") or not author.get("evidenceId"):
                return False
            death_dates.append(date.fromisoformat(author["deathDate"]))
        last_death = max(death_dates)
        public_domain_from = date.fromisoformat(calculation["publicDomainFrom"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        calculation.get("lastRelevantAuthorDeathDate") == last_death.isoformat()
        and calculation.get("protectionEnded") == f"{last_death.year + 70}-12-31"
        and calculation.get("publicDomainFrom") == f"{last_death.year + 71}-01-01"
        and public_domain_from <= date.today()
    )


def candidate_errors(
    metadata: dict[str, Any],
    body: str,
    registry: dict[str, dict[str, Any]],
    review_stage: str = "inbox",
) -> list[str]:
    candidate_id = metadata.get("id") or "<missing-id>"
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(f"{candidate_id}: {message}")

    require(metadata.get("recordType") == "source-candidate", "bad recordType")
    require(metadata.get("sourceType") == "bibliographic-metadata", "bad sourceType")
    require(bool(metadata.get("subjectId")), "missing subjectId")
    require(bool(metadata.get("title")), "missing title")
    require(bool((metadata.get("author") or {}).get("name")), "missing author name")
    require(bool(metadata.get("originalLanguage")), "missing originalLanguage")
    require(bool(body.strip()), "empty review body")

    collection_id = metadata.get("collectionId")
    collection = registry.get(collection_id)
    require(collection is not None, f"unregistered collection {collection_id}")
    method = metadata.get("allowedMethodUsed")
    if collection:
        require(method in collection.get("allowedMethods", []), f"method {method} is not allowed")
        base_url = collection.get("baseUrl")
        require(
            bool(base_url) and str(metadata.get("canonicalUrl", "")).startswith(str(base_url)),
            "canonicalUrl is outside the registered collection",
        )

    digital = metadata.get("digitalEdition") or {}
    require(bool(digital.get("identifier")), "missing digital edition identifier")
    require(
        digital.get("editionIdentityStatus") in {"identified", "ambiguous"},
        "bad edition identity status",
    )

    rights = metadata.get("rightsReview") or {}
    if review_stage == "inbox":
        require(metadata.get("status") == "rights-review", "inbox status must be rights-review")
        require(metadata.get("reviewRequired") is True, "human review is not required")
        require(metadata.get("publicationBlocked") is True, "publication is not blocked")
        require(rights.get("status") == "human-review-required", "bad rights-review status")
        require(rights.get("humanApproved") is False, "candidate claims human approval")
        require(rights.get("fullTextEligible") is False, "candidate enables full text")
        require(rights.get("imagesEligible") is False, "candidate enables images")
        require(rights.get("translationEligible") is False, "candidate enables translation")
        require(bool(rights.get("unresolved")), "candidate lacks unresolved rights questions")
    elif review_stage == "accepted":
        require(metadata.get("status") == "accepted", "accepted status must be accepted")
        require(metadata.get("reviewRequired") is False, "accepted scope still requires review")
        require(metadata.get("publicationBlocked") is False, "accepted scope remains blocked")
        require(
            rights.get("status") in {"human-approved", "policy-approved"},
            "accepted scope lacks approval",
        )
        require(rights.get("humanApproved") is True, "accepted scope lacks human approval")
        require(rights.get("rightsStatus") == "public-domain", "accepted scope is not public-domain")
        require(bool(rights.get("approvedScope")), "accepted scope is missing")
        require(
            any(
                rights.get(field) is True
                for field in ("fullTextEligible", "imagesEligible", "translationEligible")
            ),
            "accepted record enables no reusable component",
        )
        decision = rights.get("humanDecision") or {}
        approval_policy_id = rights.get("approvalPolicyId")
        collection_policy = (collection or {}).get("rightsPresumption") or {}
        policy_matches = (
            bool(approval_policy_id)
            and approval_policy_id == collection_policy.get("id")
            and collection_policy.get("humanApproved") is True
        )
        policy_conditions_satisfied = policy_matches and life_plus_70_policy_is_satisfied(rights)
        if approval_policy_id:
            require(policy_matches, "approval policy does not match the collection")
            require(
                policy_conditions_satisfied,
                "life-plus-70 policy conditions or calculation are not satisfied",
            )
        decision_is_recorded = all(
            bool(decision.get(field)) for field in ("date", "approvedBy", "basis")
        )
        require(
            decision_is_recorded or policy_conditions_satisfied,
            "accepted scope lacks a recorded human decision or approved collection policy",
        )
    else:
        require(False, f"unknown review stage {review_stage}")

    evidence = metadata.get("provenanceEvidence") or []
    evidence_ids = [item.get("id") for item in evidence]
    require(bool(evidence), "missing provenance evidence")
    require(len(evidence_ids) == len(set(evidence_ids)), "duplicate evidence IDs")
    for item in evidence:
        require(bool(item.get("url")), "evidence lacks URL")
        require(bool(item.get("supports")), "evidence lacks supported fields")

    discovery = metadata.get("discovery") or {}
    require(
        isinstance(discovery.get("metadataPagesInspected"), int)
        and discovery.get("metadataPagesInspected") > 0,
        "discovery did not record inspected metadata pages",
    )
    require(discovery.get("sourceFilesDownloaded") == 0, "discovery downloaded a source file")
    require(discovery.get("fullTextCopied") is False, "discovery copied full text")
    require(discovery.get("repositoryContentAdded") == "metadata-only", "discovery is not metadata-only")
    require(discovery.get("estimatedCostUsd") == 0, "metadata-only discovery reports a cost")
    return errors


def validate_candidates() -> tuple[int, list[str]]:
    registry = load_registry()
    errors = registry_errors(registry)
    ids: list[str] = []
    count = 0
    for review_stage, directory in CANDIDATE_DIRS.items():
        for path in sorted(directory.glob("candidate-*.md")):
            metadata, body = load_markdown(path)
            ids.append(metadata.get("id"))
            errors.extend(candidate_errors(metadata, body, registry, review_stage))
            count += 1
    if len(ids) != len(set(ids)):
        errors.append("Source-candidate IDs are not unique")
    return count, errors


def main() -> None:
    count, errors = validate_candidates()
    if errors:
        print("Candidate validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Candidate validation passed: {count} source candidate record(s).")


if __name__ == "__main__":
    main()
