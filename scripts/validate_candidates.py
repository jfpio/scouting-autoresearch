#!/usr/bin/env python3
"""Validate review-only V2 source-candidate records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown


CANDIDATE_DIR = VAULT / "reviews" / "inbox"
REGISTRY_PATH = ROOT / "config" / "source-registry.yaml"


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {item["id"]: item for item in payload.get("collections", [])}


def candidate_errors(
    metadata: dict[str, Any], body: str, registry: dict[str, dict[str, Any]]
) -> list[str]:
    candidate_id = metadata.get("id") or "<missing-id>"
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(f"{candidate_id}: {message}")

    require(metadata.get("recordType") == "source-candidate", "bad recordType")
    require(metadata.get("status") == "rights-review", "status must remain rights-review")
    require(metadata.get("sourceType") == "bibliographic-metadata", "bad sourceType")
    require(metadata.get("reviewRequired") is True, "human review is not required")
    require(metadata.get("publicationBlocked") is True, "publication is not blocked")
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
    require(rights.get("status") == "human-review-required", "bad rights-review status")
    require(rights.get("humanApproved") is False, "candidate claims human approval")
    require(rights.get("fullTextEligible") is False, "candidate enables full text")
    require(rights.get("imagesEligible") is False, "candidate enables images")
    require(rights.get("translationEligible") is False, "candidate enables translation")
    require(bool(rights.get("unresolved")), "candidate lacks unresolved rights questions")

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
    paths = sorted(CANDIDATE_DIR.glob("candidate-*.md"))
    errors: list[str] = []
    ids: list[str] = []
    for path in paths:
        metadata, body = load_markdown(path)
        ids.append(metadata.get("id"))
        errors.extend(candidate_errors(metadata, body, registry))
    if len(ids) != len(set(ids)):
        errors.append("Source-candidate IDs are not unique")
    return len(paths), errors


def main() -> None:
    count, errors = validate_candidates()
    if errors:
        print("Candidate validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Candidate validation passed: {count} review-only source candidate(s).")


if __name__ == "__main__":
    main()
