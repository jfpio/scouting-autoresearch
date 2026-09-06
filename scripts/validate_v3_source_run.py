#!/usr/bin/env python3
"""Validate the pinned multi-source manifest for the V3-R1 corpus expansion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from common import ROOT


MANIFEST_PATH = ROOT / "config" / "v3-source-expansion.yaml"
REGISTRY_PATH = ROOT / "config" / "source-registry.yaml"
QUEUE_PATH = ROOT / "config" / "research-queue.yaml"
CHECKPOINT_PATH = ROOT / "data" / "checkpoints" / "research-runs" / "v3-source-expansion-2026-09.json"

EXPECTED_SOURCE_IDS = {
    "jasinski-field-games-1938",
    "mojmir-scout-games-1912",
    "dabrowski-indoor-games-1934",
    "piasecki-schreiber-movement-games-1920",
    "dabrowski-winter-games-1935",
    "pawelek-young-troop-1919",
    "zwolakowska-cub-pack-1945",
    "sedlaczek-fieldcraft-method-1935",
    "piasecki-schreiber-polish-scoutcraft-1917",
    "sedlaczek-scout-school-1921",
    "chamarande-1934",
}


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def v3_source_run_errors(
    manifest: dict[str, Any],
    registry: dict[str, Any],
    queue: dict[str, Any],
    checkpoint: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(manifest.get("schemaVersion") == 1, "V3 source manifest has a bad schema version")
    run_id = manifest.get("runId")
    require(run_id == "v3-source-expansion-2026-09", "V3 source manifest has an unexpected run ID")
    require(manifest.get("status") == "prepared-human-gates-pending", "V3 source run hides pending gates")

    scope = manifest.get("scope") or {}
    require(scope.get("productionKinds") == ["game"], "V3 source run silently expands production kinds")
    require(scope.get("polishSourceUnits") == 10, "V3 source run must contain ten Polish sources")
    require(scope.get("totalSourceUnits") == 11, "V3 source run must contain eleven sources in total")

    policy = manifest.get("runPolicy") or {}
    require(policy.get("intermediatePullRequests") is False, "V3 source run enables intermediate PRs")
    require(policy.get("pullRequestCount") == 1, "V3 source run must end in one PR")
    require(policy.get("sourceCheckpointsRequired") is True, "V3 source run lacks source checkpoints")
    require(
        policy.get("runCheckpointPath")
        == "data/checkpoints/research-runs/v3-source-expansion-2026-09.json",
        "V3 source run points to the wrong run checkpoint",
    )
    required_terminal = {"imported", "zero-yield", "skipped-with-reason", "blocked-with-reason"}
    require(set(policy.get("terminalStatuses") or []) == required_terminal, "V3 source run has bad terminal statuses")
    report_path = policy.get("reportPath")
    require(report_path == "data/reports/v3-source-expansion-2026-09.json", "V3 source run has a bad report path")
    require(len(policy.get("requiredReportSections") or []) >= 10, "V3 source report contract is incomplete")

    translation = manifest.get("translationPolicy") or {}
    require(translation.get("reasoningMode") == "disabled", "V3 translations must not enable reasoning")
    require(translation.get("directions") == {"pl": ["en"], "fr": ["pl", "en"]}, "V3 translation directions are incomplete")

    units = manifest.get("sourceUnits") or []
    ids = [unit.get("id") for unit in units]
    require(len(units) == 11, "V3 source manifest does not contain eleven units")
    require(len(ids) == len(set(ids)), "V3 source IDs are not unique")
    require(set(ids) == EXPECTED_SOURCE_IDS, "V3 source manifest differs from the approved shortlist")
    require([unit.get("order") for unit in units] == list(range(1, 12)), "V3 source order is not contiguous")
    require(sum(unit.get("language") == "pl" for unit in units) == 10, "V3 source manifest needs ten Polish-language units")
    require(sum(unit.get("language") == "fr" for unit in units) == 1, "V3 source manifest needs one French-language unit")

    collections = {item.get("id"): item for item in registry.get("collections", [])}
    for unit in units:
        unit_id = unit.get("id") or "<missing-id>"
        require(bool(unit.get("title")), f"{unit_id}: missing title")
        require(bool(unit.get("authorStatement")), f"{unit_id}: missing author statement")
        require(isinstance(unit.get("year"), int), f"{unit_id}: missing numeric publication year")
        require(str(unit.get("url", "")).startswith(("http://", "https://")), f"{unit_id}: missing source URL")
        require(unit.get("discoveryCollectionId") in collections, f"{unit_id}: unregistered discovery collection")
        require(unit.get("targetCollectionId") in collections, f"{unit_id}: unregistered target collection")
        require(bool(unit.get("accessStatus")), f"{unit_id}: missing access status")

    chamarande = next((unit for unit in units if unit.get("id") == "chamarande-1934"), {})
    require(chamarande.get("itemIdentifier") == "bpt6k3373518k", "Chamarande has a bad Gallica identifier")
    for field in ("rightsReviewRecord", "pageScopeReviewRecord"):
        path_value = chamarande.get(field)
        require(bool(path_value) and (ROOT / str(path_value)).is_file(), f"Chamarande lacks {field}")

    gates = {gate.get("id"): gate for gate in manifest.get("humanGates", [])}
    require(gates.get("historyczna-directory-access", {}).get("status") == "pending", "Historyczna access gate is not pending")
    require(gates.get("chamarande-ocr-page-scope", {}).get("proposedViewCount") == 113, "Chamarande OCR gate does not pin 113 views")

    active_run = queue.get("activeRun") or {}
    require(active_run.get("id") == run_id, "Research queue does not point to the V3 source run")
    require(active_run.get("manifest") == "config/v3-source-expansion.yaml", "Research queue points to the wrong manifest")
    require(
        active_run.get("checkpoint") == policy.get("runCheckpointPath"),
        "Research queue points to the wrong run checkpoint",
    )
    require(active_run.get("sourceUnitCount") == len(units), "Research queue has a stale source count")
    review_path = active_run.get("reviewRecord")
    require(bool(review_path) and (ROOT / str(review_path)).is_file(), "Research queue lacks the V3 review record")

    checkpoint_units = checkpoint.get("sourceUnits") or []
    checkpoint_ids = [unit.get("id") for unit in checkpoint_units]
    require(checkpoint.get("runId") == run_id, "V3 run checkpoint has the wrong run ID")
    require(checkpoint.get("status") == "human-gates-pending", "V3 run checkpoint hides pending gates")
    require(checkpoint_ids == ids, "V3 run checkpoint source order differs from the manifest")
    require(
        all(unit.get("status") == "not-started" for unit in checkpoint_units),
        "Prepared V3 checkpoint contains a source that has already started",
    )
    require(checkpoint.get("pullRequestOpened") is False, "Prepared V3 checkpoint claims an open PR")
    return errors


def validate_v3_source_run() -> tuple[int, list[str]]:
    manifest = load_yaml(MANIFEST_PATH)
    registry = load_yaml(REGISTRY_PATH)
    queue = load_yaml(QUEUE_PATH)
    checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return len(manifest.get("sourceUnits") or []), v3_source_run_errors(
        manifest, registry, queue, checkpoint
    )


def main() -> None:
    count, errors = validate_v3_source_run()
    if errors:
        print("V3 source-run validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"V3 source-run validation passed: {count} pinned source unit(s).")


if __name__ == "__main__":
    main()
