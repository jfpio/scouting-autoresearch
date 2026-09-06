#!/usr/bin/env python3
"""Validate conservative invariants for protected and uncertain sources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from common import ROOT


CONFIG_PATH = ROOT / "config" / "protected-source-use.yaml"
POLICY_PATH = ROOT / "vault" / "policies" / "protected-sources.md"
REQUIRED_QUOTE_EVIDENCE = {
    "lawfully-disseminated-work",
    "independent-context",
    "purpose-and-extent-justification",
    "author",
    "title",
    "source",
    "canonical-url",
    "precise-location",
    "human-decision",
}
REQUIRED_PROHIBITED_USES = {
    "corpus-ingestion",
    "activity-reconstruction",
    "substitute-for-source",
    "systematic-extraction",
    "machine-translation",
    "image-or-scan-copy",
}


def load_policy(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def protected_source_policy_errors(policy: dict[str, Any], policy_document: Path = POLICY_PATH) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(policy.get("schemaVersion") == 1, "bad protected-source policy schemaVersion")
    require(policy.get("policyVersion") == "protected-source-use-v1", "bad policyVersion")
    require(policy.get("defaultMode") == "link-only", "protected sources are not link-only by default")
    link_only = policy.get("linkOnly") or {}
    excluded = set(link_only.get("excludedContent") or [])
    require({"source-body", "ocr", "transcription", "translation", "images", "scans"}.issubset(excluded), "link-only exclusions are incomplete")

    quotation = policy.get("quotation") or {}
    require(quotation.get("enabledByDefault") is False, "quotation is enabled by default")
    require(quotation.get("humanApprovalRequiredPerExcerpt") is True, "quotation lacks per-excerpt human approval")
    require(quotation.get("noNumericSafeHarbor") is True, "policy claims a numeric quotation safe harbor")
    require(REQUIRED_QUOTE_EVIDENCE.issubset(set(quotation.get("requiredEvidence") or [])), "quotation evidence is incomplete")
    require(REQUIRED_PROHIBITED_USES.issubset(set(quotation.get("prohibitedUses") or [])), "quotation prohibitions are incomplete")

    automation = policy.get("automation") or {}
    for action in (
        "fetchProtectedContent",
        "ocrProtectedContent",
        "translateProtectedContent",
        "embedProtectedContent",
        "publishProtectedContent",
        "followLinkWithoutRegisteredCollection",
    ):
        require(automation.get(action) is False, f"protected-source automation enables {action}")

    legal = policy.get("legalBasis") or {}
    require(legal.get("informationalOnly") is True, "legal basis is not marked informational-only")
    source_ids = {source.get("id") for source in legal.get("sources") or []}
    require(
        {
            "polish-copyright-act-art-29",
            "polish-copyright-act-art-34",
            "polish-copyright-act-art-35",
            "eu-information-society-directive-art-5",
        }.issubset(source_ids),
        "legal sources are incomplete",
    )
    require(policy_document.is_file(), "protected-source policy document is missing")
    return errors


def validate_protected_source_policy() -> list[str]:
    return protected_source_policy_errors(load_policy())


def main() -> None:
    errors = validate_protected_source_policy()
    if errors:
        print("Protected-source policy validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("Protected-source policy validation passed.")


if __name__ == "__main__":
    main()
