#!/usr/bin/env python3
"""Acquire only owner-approved V3 source artifacts into project scratch storage."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import yaml

from common import ROOT


MANIFEST_PATH = ROOT / "config" / "v3-source-expansion.yaml"
REGISTRY_PATH = ROOT / "config" / "source-registry.yaml"
CHECKPOINT_DIR = ROOT / "data" / "checkpoints" / "source-acquisition"
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_PDF_BYTES = 512 * 1024 * 1024
MAX_DJVU_BYTES = 512 * 1024 * 1024
USER_AGENT = "scouting-autoresearch/1.0 (+https://github.com/jfpio/scouting-autoresearch)"


@dataclass(frozen=True)
class AcquisitionPlan:
    source_id: str
    collection_id: str
    method: str
    artifact_type: str | None
    source_url: str
    artifact_url: str | None
    expected_host: str
    rate_limit_per_minute: int
    source_directory: Path
    checkpoint_path: Path
    uuid: str | None = None


class AcquisitionError(RuntimeError):
    def __init__(
        self,
        reason: str,
        diagnostics: dict[str, Any] | None = None,
        next_retry_at: datetime | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.diagnostics = diagnostics or {}
        self.next_retry_at = next_retry_at


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def scratch_root() -> Path:
    value = os.environ.get("SCRATCH")
    if not value:
        raise AcquisitionError("SCRATCH-is-not-set")
    return (Path(value) / "scouting-autoresearch").resolve()


def assert_scratch_path(path: Path) -> None:
    try:
        path.resolve().relative_to(scratch_root())
    except ValueError as error:
        raise AcquisitionError("artifact-path-is-outside-project-scratch") from error


def load_plan(source_id: str) -> AcquisitionPlan:
    manifest = load_yaml(MANIFEST_PATH)
    if manifest.get("status") not in {"active", "complete"}:
        raise AcquisitionError("v3-run-is-not-active")
    acquisition = manifest.get("acquisitionPreparation") or {}
    decision = acquisition.get("humanDecision") or {}
    if (
        acquisition.get("contentDownloadsApproved") is not True
        or decision.get("approvedBy") != "repository-owner"
        or decision.get("robotsBlockedZipDownloadsApproved") is not False
    ):
        raise AcquisitionError("owner-acquisition-approval-is-missing-or-unbounded")

    unit = next(
        (item for item in manifest.get("sourceUnits", []) if item.get("id") == source_id),
        None,
    )
    if not unit:
        raise AcquisitionError("source-is-not-in-the-v3-manifest")
    if unit.get("runDisposition") == "skipped-with-reason":
        raise AcquisitionError("source-is-skipped-in-the-current-v3-run")
    proposed = unit.get("proposedAcquisition") or {}
    method = str(proposed.get("method") or "")
    if method == "zip-link-blocked-by-robots":
        gates = {gate.get("id"): gate for gate in manifest.get("humanGates", [])}
        alternative = unit.get("alternativeCandidate") or {}
        approval = gates.get("pbc-direct-djvu-artifacts") or {}
        if (
            alternative.get("method") != "direct-djvu-from-official-reader"
            or alternative.get("status") != "approved-resolve-before-fetch"
            or alternative.get("artifactType") != "djvu"
            or approval.get("status") != "approved"
            or approval.get("approvedBy") != "repository-owner"
        ):
            raise AcquisitionError("artifact-is-blocked-by-robots-use-a-permitted-alternative")
        proposed = alternative
        method = str(proposed.get("method"))
    if method not in {
        "polona-uuid-record",
        "direct-artifact-link-from-metadata-page",
        "direct-djvu-from-official-reader",
    }:
        raise AcquisitionError("source-does-not-use-this-acquisition-adapter")
    if proposed.get("status") != "approved-resolve-before-fetch":
        raise AcquisitionError("source-acquisition-is-not-owner-approved")

    collections = {
        item.get("id"): item for item in load_yaml(REGISTRY_PATH).get("collections", [])
    }
    collection_id = str(unit.get("targetCollectionId") or "")
    collection = collections.get(collection_id) or {}
    if collection.get("status") != "approved-per-item" or "documented-download" not in (
        collection.get("allowedMethods") or []
    ):
        raise AcquisitionError("target-collection-is-not-approved-for-documented-download")
    expected_host = str(
        unit.get("targetDomain")
        or urlparse(str(collection.get("baseUrl") or "")).hostname
        or ""
    )
    if not expected_host:
        raise AcquisitionError("target-collection-has-no-approved-host")
    source_url = str(proposed.get("discoveryUrl") or unit.get("url") or "")
    parsed_source = urlparse(source_url)
    if parsed_source.scheme != "https" or not parsed_source.hostname:
        raise AcquisitionError("source-record-url-is-not-https")

    artifact_url = str(proposed.get("url") or "") or None
    if artifact_url:
        parsed_artifact = urlparse(artifact_url)
        if parsed_artifact.scheme != "https" or parsed_artifact.hostname != expected_host:
            raise AcquisitionError("artifact-url-is-outside-the-approved-https-host")
    directory = scratch_root() / "sources" / source_id
    assert_scratch_path(directory)
    return AcquisitionPlan(
        source_id=source_id,
        collection_id=collection_id,
        method=method,
        artifact_type=str(proposed.get("artifactType") or "") or None,
        source_url=source_url,
        artifact_url=artifact_url,
        expected_host=expected_host,
        rate_limit_per_minute=int(collection.get("rateLimitPerMinute") or 1),
        source_directory=directory,
        checkpoint_path=CHECKPOINT_DIR / f"{source_id}.json",
        uuid=str(proposed.get("uuid") or "") or None,
    )


def safe_http_diagnostics(error: urllib.error.HTTPError) -> dict[str, Any]:
    return {
        "httpStatus": error.code,
        "retryAfter": error.headers.get("Retry-After") if error.headers else None,
        "requestId": (
            error.headers.get("x-request-id") or error.headers.get("x-amzn-requestid")
            if error.headers
            else None
        ),
    }


def retry_time(error: urllib.error.HTTPError) -> datetime | None:
    if error.code not in {429, 500, 502, 503, 504}:
        return None
    value = error.headers.get("Retry-After") if error.headers else None
    if value and value.isdigit():
        return datetime.now(UTC) + timedelta(seconds=max(1, int(value)))
    return datetime.now(UTC) + timedelta(hours=1)


def fetch_bytes(url: str, expected_host: str, limit: int) -> tuple[bytes, str, str | None]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != expected_host:
        raise AcquisitionError("request-url-is-outside-the-approved-https-host")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            final_url = response.geturl()
            final = urlparse(final_url)
            if final.scheme != "https" or final.hostname != expected_host:
                raise AcquisitionError("provider-redirected-outside-the-approved-host")
            payload = response.read(limit + 1)
            if len(payload) > limit:
                raise AcquisitionError("provider-response-exceeds-size-limit", {"limitBytes": limit})
            return payload, final_url, response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        raise AcquisitionError(
            "transient-provider-error" if retry_time(error) else "permanent-provider-error",
            safe_http_diagnostics(error),
            retry_time(error),
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise AcquisitionError(
            "transient-network-error",
            {"transport": "network"},
            datetime.now(UTC) + timedelta(hours=1),
        ) from error


def write_atomic(path: Path, payload: bytes) -> None:
    assert_scratch_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_checkpoint(plan: AcquisitionPlan) -> dict[str, Any]:
    if plan.checkpoint_path.exists():
        checkpoint = json.loads(plan.checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("sourceId") != plan.source_id:
            raise AcquisitionError("source-checkpoint-id-mismatch")
        return checkpoint
    return {
        "schemaVersion": 1,
        "pipeline": "v3-source-acquisition",
        "sourceId": plan.source_id,
        "collectionId": plan.collection_id,
        "status": "not-started",
        "sourceFilesCommittedToRepository": 0,
        "items": [],
    }


def normalized_artifact_identity(url: str) -> tuple[str, str]:
    parsed = urlparse(html.unescape(url))
    return (parsed.hostname or "").removeprefix("www."), unquote(parsed.path)


def resolve_direct_artifact(plan: AcquisitionPlan) -> tuple[str, dict[str, Any]]:
    if not plan.artifact_url:
        raise AcquisitionError("direct-artifact-url-is-missing")
    source_host = str(urlparse(plan.source_url).hostname or "")
    page, final_url, content_type = fetch_bytes(plan.source_url, source_host, MAX_METADATA_BYTES)
    text = page.decode("utf-8", errors="replace")
    if plan.artifact_type not in {"pdf", "djvu"}:
        raise AcquisitionError("direct-artifact-type-is-not-supported")
    extension = re.escape(f".{plan.artifact_type}")
    candidates = re.findall(
        rf"(?:https?:)?//[^\"'<>\s]+{extension}|/Content/[^\"'<>\s]+{extension}",
        text,
        re.I,
    )
    target = normalized_artifact_identity(plan.artifact_url)
    resolved = None
    for candidate in candidates:
        absolute = urljoin(final_url, html.unescape(candidate))
        if normalized_artifact_identity(absolute) == target:
            resolved = plan.artifact_url
            break
    if resolved is None:
        raise AcquisitionError("approved-artifact-was-not-re-resolved-from-record-page")
    return resolved, {
        "recordUrl": plan.source_url,
        "recordFinalUrl": final_url,
        "recordContentType": content_type,
        "recordSha256": hashlib.sha256(page).hexdigest(),
        "recordBytes": len(page),
        "resolvedAt": now_iso(),
    }


def validate_pdf(payload: bytes, content_type: str | None) -> None:
    if not payload.startswith(b"%PDF-"):
        raise AcquisitionError("artifact-signature-is-not-pdf")
    if content_type and content_type not in {"application/pdf", "application/octet-stream"}:
        raise AcquisitionError("artifact-content-type-is-not-pdf", {"contentType": content_type})


def validate_djvu(payload: bytes, content_type: str | None) -> None:
    if not payload.startswith(b"AT&TFORM") or payload[12:16] not in {b"DJVU", b"DJVM"}:
        raise AcquisitionError("artifact-signature-is-not-djvu")
    if content_type and content_type not in {
        "image/vnd.djvu",
        "image/x-djvu",
        "image/x.djvu",
        "application/octet-stream",
    }:
        raise AcquisitionError("artifact-content-type-is-not-djvu", {"contentType": content_type})


def polona_image_url(info_url: str) -> str:
    parsed = urlparse(info_url)
    if parsed.scheme != "https" or parsed.hostname != "polona.pl":
        raise AcquisitionError("polona-tile-is-outside-the-approved-host")
    if not parsed.path.startswith("/iiif/3/") or not parsed.path.endswith("/info.json"):
        raise AcquisitionError("polona-tile-info-url-has-an-unexpected-shape")
    return info_url[: -len("info.json")] + "full/1600,/0/default.jpg"


def polona_image_fallback_url(info_url: str) -> str:
    """Return the native-size IIIF URL used when a small image rejects width 1600."""
    parsed = urlparse(info_url)
    if parsed.scheme != "https" or parsed.hostname != "polona.pl":
        raise AcquisitionError("polona-tile-is-outside-the-approved-host")
    if not parsed.path.startswith("/iiif/3/") or not parsed.path.endswith("/info.json"):
        raise AcquisitionError("polona-tile-info-url-has-an-unexpected-shape")
    return info_url[: -len("info.json")] + "full/max/0/default.jpg"


def validate_image(payload: bytes, content_type: str | None) -> str:
    if payload.startswith(b"\xff\xd8"):
        kind = "jpeg"
    elif payload.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "png"
    else:
        raise AcquisitionError("artifact-signature-is-not-an-approved-image")
    if content_type and content_type not in {"image/jpeg", "image/png", "application/octet-stream"}:
        raise AcquisitionError("artifact-content-type-is-not-an-image", {"contentType": content_type})
    return kind


def acquire_direct_artifact(plan: AcquisitionPlan) -> dict[str, Any]:
    checkpoint = read_checkpoint(plan)
    artifact_url, resolution = resolve_direct_artifact(plan)
    if plan.artifact_type not in {"pdf", "djvu"}:
        raise AcquisitionError("direct-artifact-type-is-not-supported")
    output = plan.source_directory / f"source.{plan.artifact_type}"
    existing = next(
        (item for item in checkpoint.get("items", []) if item.get("kind") == plan.artifact_type),
        None,
    )
    if existing and output.exists() and hashlib.sha256(output.read_bytes()).hexdigest() == existing.get("sha256"):
        return checkpoint
    size_limit = MAX_PDF_BYTES if plan.artifact_type == "pdf" else MAX_DJVU_BYTES
    payload, final_url, content_type = fetch_bytes(artifact_url, plan.expected_host, size_limit)
    if plan.artifact_type == "pdf":
        validate_pdf(payload, content_type)
    else:
        validate_djvu(payload, content_type)
    write_atomic(output, payload)
    checkpoint.update(
        {
            "status": "complete",
            "method": plan.method,
            "recordResolution": resolution,
            "completedAt": now_iso(),
            "items": [
                {
                    "kind": plan.artifact_type,
                    "status": "complete",
                    "url": artifact_url,
                    "finalUrl": final_url,
                    "scratchRelativePath": str(output.relative_to(Path(os.environ["SCRATCH"]))),
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "contentType": content_type,
                    "retrievedAt": now_iso(),
                }
            ],
        }
    )
    write_checkpoint(plan.checkpoint_path, checkpoint)
    return checkpoint


def acquire_polona(plan: AcquisitionPlan, limit: int | None) -> dict[str, Any]:
    if plan.expected_host != "polona.pl" or not plan.uuid:
        raise AcquisitionError("polona-plan-is-incomplete")
    metadata_url = f"https://polona.pl/api/library-object-query/digital-objects/{plan.uuid}"
    metadata, final_url, content_type = fetch_bytes(metadata_url, "polona.pl", MAX_METADATA_BYTES)
    try:
        record = json.loads(metadata.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcquisitionError("polona-metadata-is-not-valid-json") from error
    if (
        record.get("uuid") != plan.uuid
        or record.get("copyrightProtected") is not False
        or (record.get("license") or {}).get("downloadable") is not True
    ):
        raise AcquisitionError("polona-record-no-longer-matches-the-approved-public-domain-scope")
    tiles = record.get("tiles") or []
    image_urls: list[tuple[int, str, str, str | None]] = []
    for index, tile in enumerate(tiles, start=1):
        if not isinstance(tile, dict) or not tile.get("info"):
            continue
        label = (tile.get("label") or {}).get("pl")
        info_url = str(tile["info"])
        image_urls.append(
            (
                index,
                polona_image_url(info_url),
                polona_image_fallback_url(info_url),
                str(label) if label else None,
            )
        )
    if not image_urls:
        raise AcquisitionError("polona-record-has-no-downloadable-iiif-images")

    checkpoint = read_checkpoint(plan)
    items = checkpoint.setdefault("items", [])
    complete_by_index = {item.get("viewIndex"): item for item in items if item.get("status") == "complete"}
    pending = [item for item in image_urls if item[0] not in complete_by_index]
    selected = pending[:limit] if limit is not None else pending
    if len(selected) > 1 and not os.environ.get("SLURM_JOB_ID"):
        raise AcquisitionError("multi-view-polona-acquisition-must-run-inside-slurm")
    interval = 60.0 / max(1, plan.rate_limit_per_minute)
    metadata_path = plan.source_directory / "metadata.json"
    write_atomic(metadata_path, metadata)
    checkpoint.pop("reason", None)
    checkpoint.pop("providerDiagnostics", None)
    checkpoint.pop("nextRetryAt", None)
    checkpoint.update(
        {
            "status": "in-progress",
            "method": plan.method,
            "metadata": {
                "url": metadata_url,
                "finalUrl": final_url,
                "contentType": content_type,
                "scratchRelativePath": str(metadata_path.relative_to(Path(os.environ["SCRATCH"]))),
                "bytes": len(metadata),
                "sha256": hashlib.sha256(metadata).hexdigest(),
                "retrievedAt": now_iso(),
                "tileCount": len(tiles),
                "downloadableImageCount": len(image_urls),
                "license": (record.get("license") or {}).get("baseName"),
                "copyrightProtected": record.get("copyrightProtected"),
            },
        }
    )
    write_checkpoint(plan.checkpoint_path, checkpoint)
    for position, (index, preferred_url, fallback_url, label) in enumerate(selected):
        if position:
            time.sleep(interval)
        url = preferred_url
        fallback_after_http_status = None
        try:
            payload, image_final_url, image_content_type = fetch_bytes(
                url, "polona.pl", MAX_IMAGE_BYTES
            )
        except AcquisitionError as error:
            # Polona's IIIF server returns 400 instead of downscaling when the requested
            # width is larger than the native scan. Retry only that deterministic case at
            # native size; all other provider failures retain their normal classification.
            if error.reason != "permanent-provider-error" or error.diagnostics.get("httpStatus") != 400:
                raise
            time.sleep(interval)
            url = fallback_url
            fallback_after_http_status = 400
            payload, image_final_url, image_content_type = fetch_bytes(
                url, "polona.pl", MAX_IMAGE_BYTES
            )
        kind = validate_image(payload, image_content_type)
        suffix = ".jpg" if kind == "jpeg" else ".png"
        output = plan.source_directory / "views" / f"view-{index:04d}{suffix}"
        write_atomic(output, payload)
        item = {
                "viewIndex": index,
                "printedLabel": label,
                "kind": kind,
                "status": "complete",
                "url": url,
                "finalUrl": image_final_url,
                "scratchRelativePath": str(output.relative_to(Path(os.environ["SCRATCH"]))),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "retrievedAt": now_iso(),
            }
        if fallback_after_http_status is not None:
            item["fallbackAfterHttpStatus"] = fallback_after_http_status
        items.append(item)
        checkpoint["completedImageCount"] = len(
            {item.get("viewIndex") for item in items if item.get("status") == "complete"}
        )
        checkpoint["expectedImageCount"] = len(image_urls)
        write_checkpoint(plan.checkpoint_path, checkpoint)
    checkpoint["status"] = (
        "complete" if checkpoint.get("completedImageCount") == len(image_urls) else "in-progress"
    )
    if checkpoint["status"] == "complete":
        checkpoint["completedAt"] = now_iso()
    write_checkpoint(plan.checkpoint_path, checkpoint)
    return checkpoint


def record_error(plan: AcquisitionPlan, error: AcquisitionError) -> None:
    checkpoint = read_checkpoint(plan)
    checkpoint["status"] = "retry-pending" if error.next_retry_at else "failed"
    checkpoint["reason"] = error.reason
    checkpoint["providerDiagnostics"] = error.diagnostics
    if error.next_retry_at:
        checkpoint["nextRetryAt"] = error.next_retry_at.isoformat()
    write_checkpoint(plan.checkpoint_path, checkpoint)


def summarize(plan: AcquisitionPlan, checkpoint: dict[str, Any], execute: bool) -> dict[str, Any]:
    return {
        "mode": "execute" if execute else "dry-run",
        "sourceId": plan.source_id,
        "collectionId": plan.collection_id,
        "method": plan.method,
        "status": checkpoint.get("status"),
        "completedItems": len([item for item in checkpoint.get("items", []) if item.get("status") == "complete"]),
        "expectedItems": checkpoint.get("expectedImageCount", 1 if plan.method.startswith("direct-") else None),
        "sourceDirectory": str(plan.source_directory),
        "checkpointPath": str(plan.checkpoint_path.relative_to(ROOT)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be positive")
    try:
        plan = load_plan(args.source_id)
    except AcquisitionError as error:
        raise SystemExit(error.reason) from error
    checkpoint = read_checkpoint(plan)
    if not args.execute:
        print(json.dumps(summarize(plan, checkpoint, False), ensure_ascii=False, indent=2))
        return
    try:
        if plan.method.startswith("direct-"):
            checkpoint = acquire_direct_artifact(plan)
        else:
            checkpoint = acquire_polona(plan, args.limit)
    except AcquisitionError as error:
        record_error(plan, error)
        suffix = f"; nextRetryAt={error.next_retry_at.isoformat()}" if error.next_retry_at else ""
        raise SystemExit(f"{error.reason}{suffix}") from error
    print(json.dumps(summarize(plan, checkpoint, True), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
