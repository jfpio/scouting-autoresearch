#!/usr/bin/env python3
"""Validate the pinned multi-source manifest for the V3-R1 corpus expansion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from common import ROOT, load_markdown


MANIFEST_PATH = ROOT / "config" / "v3-source-expansion.yaml"
REGISTRY_PATH = ROOT / "config" / "source-registry.yaml"
QUEUE_PATH = ROOT / "config" / "research-queue.yaml"
CHECKPOINT_PATH = ROOT / "data" / "checkpoints" / "research-runs" / "v3-source-expansion-2026-09.json"

EXPECTED_SOURCE_IDS = {
    "jasinski-field-games-1938",
    "mojmir-scout-games-1912",
    "dabrowski-indoor-games-1934",
    "piasecki-movement-games-1922",
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
    require(manifest.get("status") in {"active", "complete"}, "V3 source run is not active or complete")

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

    acquisition_preparation = manifest.get("acquisitionPreparation") or {}
    require(
        acquisition_preparation.get("contentDownloadsApproved") is True,
        "Active V3 run lacks owner approval for scoped content downloads",
    )
    acquisition_decision = acquisition_preparation.get("humanDecision") or {}
    require(
        acquisition_decision.get("approvedBy") == "repository-owner"
        and acquisition_decision.get("approvedAt") == "2026-09-06"
        and acquisition_decision.get("robotsBlockedZipDownloadsApproved") is False,
        "Active V3 run lacks a bounded owner acquisition decision",
    )
    require(
        acquisition_preparation.get("proposedArtifactLinksAreUntrustedMetadata") is True,
        "Prepared V3 run treats proposed artifact links as trusted",
    )
    require(
        acquisition_preparation.get("resolveAgainAfterHumanApproval") is True,
        "Prepared V3 run would not resolve artifact links again after approval",
    )
    require(
        acquisition_preparation.get("requireRegisteredHttpsHost") is True
        and acquisition_preparation.get("requireSignatureAndSizeValidation") is True,
        "Prepared V3 run lacks artifact safety checks",
    )
    require(
        acquisition_preparation.get("rawArtifactsStorage") == "scratch-only"
        and acquisition_preparation.get("repositorySourceFilesAllowed") is False,
        "Prepared V3 run may persist source files in the repository",
    )
    require(
        set(acquisition_preparation.get("automatedFetchBlockedByRobotsSourceUnits") or [])
        == {
            "dabrowski-winter-games-1935",
            "sedlaczek-fieldcraft-method-1935",
        },
        "Prepared V3 run does not preserve the PBC Rzeszów robots exclusions",
    )

    units = manifest.get("sourceUnits") or []
    ids = [unit.get("id") for unit in units]
    require(len(units) == 11, "V3 source manifest does not contain eleven units")
    require(len(ids) == len(set(ids)), "V3 source IDs are not unique")
    require(set(ids) == EXPECTED_SOURCE_IDS, "V3 source manifest differs from the approved shortlist")
    require([unit.get("order") for unit in units] == list(range(1, 12)), "V3 source order is not contiguous")
    require(sum(unit.get("language") == "pl" for unit in units) == 10, "V3 source manifest needs ten Polish-language units")
    require(sum(unit.get("language") == "fr" for unit in units) == 1, "V3 source manifest needs one French-language unit")

    collections = {item.get("id"): item for item in registry.get("collections", [])}
    regional_collection_ids = {"pbc-rzeszow", "kpbc", "pbc-bialystok", "wbc", "sbc"}
    for collection_id in regional_collection_ids:
        collection = collections.get(collection_id) or {}
        review_record = collection.get("reviewRecord")
        require(
            bool(review_record) and (ROOT / str(review_record)).is_file(),
            f"{collection_id}: regional access review is missing",
        )
        require(
            (collection.get("robotsTxt") or {}).get("checkedAt") == "2026-09-06",
            f"{collection_id}: robots review is missing or stale",
        )
        require(
            bool((collection.get("termsOfUse") or {}).get("status")),
            f"{collection_id}: terms review is missing",
        )
    require(
        (collections.get("pbc-rzeszow", {}).get("robotsTxt") or {}).get("decision")
        == "blocks-content-zip-endpoints",
        "PBC Rzeszów registry does not preserve its robots ZIP exclusion",
    )
    regional_review_path = ROOT / "vault" / "reviews" / "accepted" / "v3-regional-library-access.md"
    if regional_review_path.is_file():
        regional_review, regional_review_body = load_markdown(regional_review_path)
        require(
            regional_review.get("recordType") == "source-collection-batch-review"
            and regional_review.get("status") == "accepted"
            and regional_review.get("reviewRequired") is False
            and regional_review.get("humanApproved") is True,
            "Regional access review does not preserve the owner approval",
        )
        require(
            set(regional_review.get("collectionIds") or []) == regional_collection_ids
            and regional_review.get("sourceFilesDownloaded") == 0
            and regional_review.get("repositoryContentAdded") == "metadata-only",
            "Regional access review overstates its inspected scope",
        )
        require(
            "/Content/*/zip*" in regional_review_body
            and "nie wolno automatycznie pobierać trzech ZIP-ów" in regional_review_body,
            "Regional access review omits the PBC Rzeszów robots restriction",
        )
    acquisition_method_counts: dict[str, int] = {}
    for unit in units:
        unit_id = unit.get("id") or "<missing-id>"
        require(bool(unit.get("title")), f"{unit_id}: missing title")
        require(bool(unit.get("authorStatement")), f"{unit_id}: missing author statement")
        require(isinstance(unit.get("year"), int), f"{unit_id}: missing numeric publication year")
        require(str(unit.get("url", "")).startswith(("http://", "https://")), f"{unit_id}: missing source URL")
        require(unit.get("discoveryCollectionId") in collections, f"{unit_id}: unregistered discovery collection")
        require(unit.get("targetCollectionId") in collections, f"{unit_id}: unregistered target collection")
        require(bool(unit.get("accessStatus")), f"{unit_id}: missing access status")
        proposed = unit.get("proposedAcquisition") or {}
        method = proposed.get("method")
        acquisition_method_counts[method] = acquisition_method_counts.get(method, 0) + 1
        require(bool(method), f"{unit_id}: missing proposed acquisition method")
        if method == "direct-artifact-link-from-metadata-page":
            artifact_url = str(proposed.get("url") or "")
            parsed_artifact = urlparse(artifact_url)
            expected_host = unit.get("targetDomain") or urlparse(
                str((collections.get(unit.get("targetCollectionId")) or {}).get("baseUrl") or "")
            ).hostname
            require(
                proposed.get("status") == "approved-resolve-before-fetch",
                f"{unit_id}: direct artifact candidate lacks scoped approval",
            )
            require(
                proposed.get("artifactType") in {"pdf", "zip"},
                f"{unit_id}: direct artifact candidate has an unsupported type",
            )
            require(
                parsed_artifact.scheme == "https" and parsed_artifact.hostname == expected_host,
                f"{unit_id}: direct artifact candidate is outside the registered HTTPS host",
            )
        elif method == "zip-link-blocked-by-robots":
            artifact_url = str(proposed.get("url") or "")
            parsed_artifact = urlparse(artifact_url)
            require(
                unit.get("targetCollectionId") == "pbc-rzeszow"
                and proposed.get("status") == "blocked-by-robots"
                and proposed.get("artifactType") == "zip"
                and parsed_artifact.scheme == "https"
                and parsed_artifact.hostname == "www.pbc.rzeszow.pl"
                and "/Content/" in parsed_artifact.path
                and "/zip/" in parsed_artifact.path
                and proposed.get("alternativeRequired")
                == "permitted-non-zip-artifact-or-human-supplied-file",
                f"{unit_id}: robots-blocked PBC artifact is not safely represented",
            )
        elif method == "polona-uuid-record":
            uuid = str(proposed.get("uuid") or "")
            require(
                proposed.get("status") == "approved-resolve-before-fetch"
                and proposed.get("artifactType") == "unresolved"
                and isinstance(proposed.get("oldId"), int)
                and proposed.get("oldId") > 0
                and len(uuid) == 36
                and str(unit.get("url") or "") == f"https://polona.pl/preview/{uuid}"
                and not proposed.get("url"),
                f"{unit_id}: Polona acquisition proposal is not safely unresolved",
            )
        elif method == "pre-fetched-iiif-views":
            require(
                unit_id == "chamarande-1934"
                and proposed.get("status") == "approved-views-present-in-scratch"
                and proposed.get("completedViews") == 188
                and proposed.get("artifactType") == "jpeg-views",
                "Chamarande acquisition preparation is inconsistent",
            )
        else:
            require(False, f"{unit_id}: unsupported proposed acquisition method")
    require(
        acquisition_method_counts
        == {
            "direct-artifact-link-from-metadata-page": 4,
            "zip-link-blocked-by-robots": 2,
            "polona-uuid-record": 4,
            "pre-fetched-iiif-views": 1,
        },
        "V3 acquisition preparation does not cover all eleven source units",
    )

    chamarande = next((unit for unit in units if unit.get("id") == "chamarande-1934"), {})
    require(chamarande.get("itemIdentifier") == "bpt6k3373518k", "Chamarande has a bad Gallica identifier")
    for field in ("rightsReviewRecord", "pageScopeReviewRecord"):
        path_value = chamarande.get(field)
        require(bool(path_value) and (ROOT / str(path_value)).is_file(), f"Chamarande lacks {field}")

    movement_games = next(
        (unit for unit in units if unit.get("id") == "piasecki-movement-games-1922"), {}
    )
    require(
        movement_games.get("authorStatement") == "Eugeniusz Piasecki"
        and movement_games.get("year") == 1922
        and movement_games.get("edition") == "wydanie 3 poprawione i rozszerzone"
        and movement_games.get("targetCollectionId") == "kpbc",
        "Piasecki movement-games edition metadata is stale",
    )
    young_troop = next(
        (unit for unit in units if unit.get("id") == "pawelek-young-troop-1919"), {}
    )
    require(
        "/publication/29783/edition/28922" in str(young_troop.get("url", "")),
        "Młoda drużyna points to a stale publication ID",
    )
    polish_scoutcraft = next(
        (
            unit
            for unit in units
            if unit.get("id") == "piasecki-schreiber-polish-scoutcraft-1917"
        ),
        {},
    )
    require(
        polish_scoutcraft.get("targetCollectionId") == "wbc"
        and "/publication/515207/edition/440525" in str(polish_scoutcraft.get("url", "")),
        "Harce młodzieży polskiej does not point to the pinned open WBC edition",
    )

    gates = {gate.get("id"): gate for gate in manifest.get("humanGates", [])}
    require(gates.get("historyczna-directory-access", {}).get("status") == "approved", "Historyczna access gate is not approved")
    require(gates.get("chamarande-ocr-page-scope", {}).get("status") == "approved", "Chamarande OCR gate is not approved")
    require(gates.get("chamarande-ocr-page-scope", {}).get("proposedViewCount") == 113, "Chamarande OCR gate does not pin 113 views")
    polish_gate = gates.get("polish-source-acquisition-and-rights", {})
    require(polish_gate.get("status") == "approved", "Polish source acquisition gate is not approved")
    polish_review = polish_gate.get("reviewRecord")
    require(
        bool(polish_review) and (ROOT / str(polish_review)).is_file(),
        "Polish source acquisition gate lacks its review record",
    )

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
    require(checkpoint.get("status") in {"active", "complete"}, "V3 run checkpoint is not active or complete")
    require(checkpoint_ids == ids, "V3 run checkpoint source order differs from the manifest")
    require(
        all(
            unit.get("status")
            in {
                "not-started",
                "acquiring",
                "acquired",
                "ocr-pending",
                "ocr-in-progress",
                "extracting",
                "translating",
                "imported",
                "zero-yield",
                "skipped-with-reason",
                "blocked-with-reason",
            }
            for unit in checkpoint_units
        ),
        "V3 checkpoint contains an unknown source-unit status",
    )
    require(checkpoint.get("pullRequestOpened") is False, "Prepared V3 checkpoint claims an open PR")
    checkpoint_acquisition = (checkpoint.get("preparation") or {}).get(
        "acquisitionPreparation"
    ) or {}
    require(
        isinstance(checkpoint_acquisition.get("contentDownloadsPerformed"), int)
        and 0 <= checkpoint_acquisition.get("contentDownloadsPerformed") <= 9
        and checkpoint_acquisition.get("regionalDirectArtifactLinksDiscovered") == 7
        and checkpoint_acquisition.get("directArtifactCandidatesActionableAfterApproval") == 4
        and checkpoint_acquisition.get("automatedFetchBlockedByRobots") == 2
        and checkpoint_acquisition.get("robotsBlockedLinksWithPermittedAlternative") == 1
        and 0 <= checkpoint_acquisition.get("polonaRecordsRequiringPost-approvalResolution", -1) <= 4
        and checkpoint_acquisition.get("preFetchedGallicaSources") == 1,
        "V3 acquisition-preparation checkpoint is stale",
    )
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
