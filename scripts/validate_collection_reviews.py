#!/usr/bin/env python3
"""Validate collection access reviews and their conservative registry state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, load_markdown


REVIEW_DIRS = {
    "inbox": VAULT / "reviews" / "inbox",
    "accepted": VAULT / "reviews" / "accepted",
}
REGISTRY_PATH = ROOT / "config" / "source-registry.yaml"


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {item["id"]: item for item in payload.get("collections", [])}


def collection_review_errors(
    metadata: dict[str, Any],
    body: str,
    registry: dict[str, dict[str, Any]],
    review_stage: str = "inbox",
) -> list[str]:
    review_id = metadata.get("id") or "<missing-id>"
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(f"{review_id}: {message}")

    require(metadata.get("recordType") == "source-collection-review", "bad recordType")
    require(bool(body.strip()), "empty review body")
    collection_id = metadata.get("collectionId")
    collection = registry.get(collection_id)
    require(collection is not None, f"unregistered collection {collection_id}")
    if collection:
        base_url = collection.get("baseUrl")
        require(
            bool(base_url) and str(metadata.get("canonicalUrl", "")).startswith(str(base_url)),
            "canonicalUrl is outside the registered collection",
        )
    access = metadata.get("accessReview") or {}
    if review_stage == "inbox":
        require(metadata.get("status") == "access-review", "inbox status must be access-review")
        require(metadata.get("reviewRequired") is True, "human review is not required")
        require(access.get("status") == "human-review-required", "bad access-review status")
        require(access.get("humanApproved") is False, "review claims human approval")
        if collection:
            require(collection.get("status") == "candidate", "pending collection is not a candidate")
            require(collection.get("allowedMethods") == ["metadata-only"], "pending collection enables more than metadata")
    elif review_stage == "accepted":
        require(metadata.get("status") == "accepted", "accepted status must be accepted")
        require(metadata.get("reviewRequired") is False, "accepted review still requires human action")
        require(access.get("status") == "human-approved", "accepted review lacks approval")
        require(access.get("humanApproved") is True, "accepted review lacks human approval")
        decision = access.get("humanDecision") or {}
        require(
            all(bool(decision.get(field)) for field in ("date", "approvedBy", "basis")),
            "accepted review lacks a recorded human decision",
        )
    else:
        require(False, f"unknown review stage {review_stage}")

    robots = metadata.get("robotsTxt") or {}
    require(bool(robots.get("url")), "missing robots.txt URL")
    require(bool(robots.get("checkedAt")), "missing robots.txt check date")
    require(
        robots.get("status") in {"available", "not-found-404", "blocked", "unavailable"},
        "bad robots.txt status",
    )
    terms = metadata.get("termsOfUse") or {}
    require(bool(terms.get("checkedAt")), "missing terms check date")
    require(bool(terms.get("status")), "missing terms status")
    require(bool(terms.get("inspectedPages")), "missing inspected terms pages")

    reuse = metadata.get("reuseDecision") or {}
    for field in (
        "pageMetadataAllowed",
        "linkDiscoveryAllowed",
        "fullTextAllowed",
        "directFileDownloadAllowed",
        "imagesAllowed",
        "followExternalLinksAutomatically",
    ):
        require(isinstance(reuse.get(field), bool), f"missing boolean reuse decision {field}")
    if review_stage == "inbox":
        require(not any(reuse.get(field) for field in reuse if field.endswith("Allowed")), "pending review enables reuse")
        require(reuse.get("followExternalLinksAutomatically") is False, "pending review follows external links")
        require(bool(metadata.get("unresolved")), "pending review lacks unresolved questions")

    evidence = metadata.get("provenanceEvidence") or []
    require(bool(evidence), "missing provenance evidence")
    evidence_ids = [item.get("id") for item in evidence]
    require(len(evidence_ids) == len(set(evidence_ids)), "duplicate evidence IDs")
    for item in evidence:
        require(bool(item.get("url")), "evidence lacks URL")
        require(bool(item.get("supports")), "evidence lacks supported fields")

    discovery = metadata.get("discovery") or {}
    require(
        isinstance(discovery.get("metadataPagesInspected"), int)
        and discovery.get("metadataPagesInspected") > 0,
        "review did not record inspected metadata pages",
    )
    require(discovery.get("sourceFilesDownloaded") == 0, "access review downloaded a source file")
    require(discovery.get("fullTextCopied") is False, "access review copied full text")
    require(discovery.get("repositoryContentAdded") == "metadata-only", "access review is not metadata-only")
    require(discovery.get("estimatedCostUsd") == 0, "metadata review reports a cost")
    return errors


def validate_collection_reviews() -> tuple[int, list[str]]:
    registry = load_registry()
    errors: list[str] = []
    ids: list[str] = []
    count = 0
    for review_stage, directory in REVIEW_DIRS.items():
        for path in sorted(directory.glob("collection-*.md")):
            metadata, body = load_markdown(path)
            ids.append(metadata.get("id"))
            collection_id = metadata.get("collectionId")
            if collection_id and registry.get(collection_id, {}).get("reviewRecord") != str(path.relative_to(ROOT)):
                errors.append(f"{metadata.get('id')}: registry does not point to this review record")
            errors.extend(collection_review_errors(metadata, body, registry, review_stage))
            count += 1
    if len(ids) != len(set(ids)):
        errors.append("Collection-review IDs are not unique")
    return count, errors


def main() -> None:
    count, errors = validate_collection_reviews()
    if errors:
        print("Collection-review validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Collection-review validation passed: {count} record(s).")


if __name__ == "__main__":
    main()
