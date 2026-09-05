#!/usr/bin/env python3
"""Fetch one explicitly approved Gallica artifact into scratch with a resumable checkpoint."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml

from common import ROOT, read_json, write_json


COLLECTION_ID = "gallica-bnf"
EXPECTED_HOST = "gallica.bnf.fr"
USER_AGENT = "scouting-autoresearch/0.1 (+https://github.com/jfpio/scouting-autoresearch)"
DEFAULT_CHECKPOINT_DIR = ROOT / "data" / "checkpoints" / "gallica-fetch"
MAX_BYTES = {
    "pagination": 2 * 1024 * 1024,
    "view": 20 * 1024 * 1024,
    "pdf": 512 * 1024 * 1024,
}
CONTENT_TYPES = {
    "pagination": {"application/xml", "text/xml", "application/octet-stream"},
    "view": {"image/jpeg", "image/jpg", "application/octet-stream"},
    "pdf": {"application/pdf", "application/octet-stream"},
}


@dataclass(frozen=True)
class ApprovedItem:
    source_id: str
    identifier: str
    canonical_url: str
    rate_limit_per_minute: int
    required_attribution: str


class GallicaFetchError(RuntimeError):
    def __init__(
        self,
        reason: str,
        diagnostics: dict[str, Any],
        retry_at: datetime | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.diagnostics = diagnostics
        self.retry_at = retry_at


def load_approved_item(
    source_id: str,
    registry_path: Path = ROOT / "config" / "source-registry.yaml",
) -> ApprovedItem:
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    collection = next(
        (item for item in payload.get("collections", []) if item.get("id") == COLLECTION_ID),
        None,
    )
    if not collection or collection.get("status") != "approved-per-item":
        raise RuntimeError("Gallica is not approved for per-item access")
    if "documented-download" not in collection.get("allowedMethods", []):
        raise RuntimeError("Gallica documented downloads are not allowed")
    approval = next(
        (
            item
            for item in collection.get("itemApprovals", [])
            if item.get("sourceId") == source_id
        ),
        None,
    )
    if not approval:
        raise RuntimeError(f"Gallica source is not approved per item: {source_id}")
    canonical_url = str(approval.get("canonicalUrl") or "")
    parsed = urlparse(canonical_url)
    if parsed.scheme != "https" or parsed.hostname != EXPECTED_HOST:
        raise RuntimeError("Approved Gallica canonical URL is outside the expected host")
    identifier = str(approval.get("identifier") or "")
    if not identifier or canonical_url != f"https://{EXPECTED_HOST}/ark:/12148/{identifier}":
        raise RuntimeError("Approved Gallica identifier and canonical URL do not match")
    if approval.get("useMode") != "noncommercial-research-and-publication":
        raise RuntimeError("Gallica item lacks the approved noncommercial use mode")
    licensing = approval.get("downstreamLicensing") or {}
    if licensing.get("sourceTextAndTranscription") != "gallica-noncommercial-reuse-terms":
        raise RuntimeError("Gallica item lacks downstream noncommercial licensing metadata")
    attribution = str(approval.get("requiredAttribution") or collection.get("attribution") or "")
    if not attribution:
        raise RuntimeError("Gallica item lacks required attribution")
    rate_limit = collection.get("rateLimitPerMinute")
    if not isinstance(rate_limit, int) or rate_limit <= 0:
        raise RuntimeError("Gallica rate limit is missing or invalid")
    return ApprovedItem(source_id, identifier, canonical_url, rate_limit, attribution)


def artifact_url(item: ApprovedItem, artifact: str, view: int | None = None) -> str:
    if artifact == "pagination":
        return f"https://{EXPECTED_HOST}/services/Pagination?ark={item.identifier}"
    if artifact == "pdf":
        return f"{item.canonical_url}.pdf"
    if artifact == "view":
        if view is None or not 1 <= view <= 10000:
            raise ValueError("A Gallica view number between 1 and 10000 is required")
        return (
            f"https://{EXPECTED_HOST}/iiif/ark:/12148/{item.identifier}/"
            f"f{view}/full/1200,/0/native.jpg"
        )
    raise ValueError(f"Unsupported Gallica artifact: {artifact}")


def default_output(item: ApprovedItem, artifact: str, view: int | None = None) -> Path:
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise RuntimeError("SCRATCH is not set")
    directory = Path(scratch) / "scouting-autoresearch" / "sources" / item.source_id
    if artifact == "pagination":
        return directory / "pagination.xml"
    if artifact == "pdf":
        return directory / f"{item.source_id}-gallica.pdf"
    if artifact == "view" and view is not None:
        return directory / f"f{view}-1200.jpg"
    raise ValueError("Cannot derive output path")


def default_provider_state_path() -> Path:
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise RuntimeError("SCRATCH is not set")
    return Path(scratch) / "scouting-autoresearch" / "provider-state" / "gallica-bnf.json"


def assert_scratch_output(path: Path) -> None:
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise RuntimeError("SCRATCH is not set")
    allowed = (Path(scratch) / "scouting-autoresearch").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as error:
        raise RuntimeError("Gallica artifacts must be stored under SCRATCH/scouting-autoresearch") from error


def _normalized_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(name).lower(): str(value) for name, value in headers.items()}


def retry_at_from_headers(headers: Mapping[str, str], now: datetime) -> datetime:
    value = _normalized_headers(headers).get("retry-after")
    if value:
        try:
            seconds = float(value)
            if seconds >= 0:
                return now + timedelta(seconds=seconds)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                if parsed > now:
                    return parsed
            except (TypeError, ValueError, OverflowError):
                pass
    return now + timedelta(hours=1)


def safe_http_diagnostics(error: urllib.error.HTTPError) -> dict[str, Any]:
    headers = _normalized_headers(error.headers or {})
    allowed_headers = {
        name: value
        for name, value in headers.items()
        if name in {"retry-after", "x-request-id", "request-id"}
        or name.startswith("x-ratelimit-")
    }
    diagnostics: dict[str, Any] = {"httpStatus": int(error.code), "headers": allowed_headers}
    body = error.read(64 * 1024)
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = None
    if isinstance(payload, dict):
        detail = payload.get("detail") if isinstance(payload.get("detail"), dict) else payload
        safe_error = {
            key: detail.get(key)
            for key in ("type", "code", "param")
            if detail.get(key) is not None
        }
        if safe_error:
            diagnostics["error"] = safe_error
    return diagnostics


def _validate_signature(data: bytes, artifact: str) -> None:
    if artifact == "pdf" and not data.startswith(b"%PDF-"):
        raise RuntimeError("Gallica response is not a PDF")
    if artifact == "view" and not data.startswith(b"\xff\xd8"):
        raise RuntimeError("Gallica response is not a JPEG image")
    if artifact == "pagination" and not data.lstrip().startswith(b"<?xml"):
        raise RuntimeError("Gallica response is not XML pagination data")


def _read_limited(response: Any, limit: int) -> bytes:
    declared = response.headers.get("Content-Length")
    if declared:
        try:
            if int(declared) > limit:
                raise RuntimeError("Gallica artifact exceeds the configured size limit")
        except ValueError:
            pass
    data = response.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError("Gallica artifact exceeds the configured size limit")
    return data


def fetch_artifact(
    item: ApprovedItem,
    artifact: str,
    output: Path,
    *,
    view: int | None = None,
    expected_sha256: str | None = None,
    refresh: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    assert_scratch_output(output)
    if output.exists() and not refresh:
        data = output.read_bytes()
        _validate_signature(data, artifact)
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise RuntimeError(
                f"Cached Gallica artifact hash changed: expected {expected_sha256}, received {digest}"
            )
        return {
            "url": artifact_url(item, artifact, view),
            "path": str(output),
            "sha256": digest,
            "bytes": len(data),
            "reused": True,
        }

    url = artifact_url(item, artifact, view)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    observed_at = now or datetime.now(UTC)
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            final = urlparse(response.geturl())
            if final.scheme != "https" or final.hostname != EXPECTED_HOST:
                raise RuntimeError("Gallica redirected outside the approved host")
            content_type = response.headers.get_content_type()
            if content_type not in CONTENT_TYPES[artifact]:
                raise RuntimeError(f"Unexpected Gallica content type: {content_type}")
            data = _read_limited(response, MAX_BYTES[artifact])
    except urllib.error.HTTPError as error:
        diagnostics = safe_http_diagnostics(error)
        retry_at = (
            retry_at_from_headers(error.headers or {}, observed_at)
            if error.code == 429 or 500 <= error.code <= 599
            else None
        )
        reason = (
            f"transient-http-{error.code}"
            if retry_at
            else f"permanent-http-{error.code}"
        )
        raise GallicaFetchError(reason, diagnostics, retry_at) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise GallicaFetchError(
            "transient-network-error",
            {"type": "network-error"},
            observed_at + timedelta(hours=1),
        ) from error
    _validate_signature(data, artifact)
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise RuntimeError(
            f"Downloaded Gallica artifact hash changed: expected {expected_sha256}, received {digest}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        temporary.write_bytes(data)
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "url": url,
        "path": str(output),
        "sha256": digest,
        "bytes": len(data),
        "contentType": content_type,
        "retrievedAt": observed_at.astimezone(UTC).isoformat(),
        "reused": False,
    }


def active_cooldown(checkpoint: dict[str, Any], now: datetime) -> datetime | None:
    if checkpoint.get("status") != "retry-pending" or not checkpoint.get("nextRetryAt"):
        return None
    retry_at = datetime.fromisoformat(checkpoint["nextRetryAt"])
    if retry_at.tzinfo is None:
        raise RuntimeError("Checkpoint nextRetryAt must include a timezone")
    return retry_at if retry_at > now else None


def reserve_request_slot(
    state_path: Path,
    now: datetime,
    rate_limit_per_minute: int,
) -> datetime | None:
    """Atomically reserve one provider request slot without sleeping on the login node."""

    assert_scratch_output(state_path)
    if rate_limit_per_minute <= 0:
        raise ValueError("Rate limit must be positive")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_json(state_path) if state_path.exists() else {}
        value = state.get("nextAllowedAt")
        if value:
            next_allowed = datetime.fromisoformat(value)
            if next_allowed.tzinfo is None:
                raise RuntimeError("Provider nextAllowedAt must include a timezone")
            if next_allowed > now:
                return next_allowed
        interval = timedelta(seconds=60 / rate_limit_per_minute)
        write_json(
            state_path,
            {
                "schemaVersion": 1,
                "provider": COLLECTION_ID,
                "lastRequestAt": now.astimezone(UTC).isoformat(),
                "nextAllowedAt": (now + interval).astimezone(UTC).isoformat(),
                "rateLimitPerMinute": rate_limit_per_minute,
            },
        )
    return None


def record_pdf_success(
    checkpoint_path: Path,
    result: dict[str, Any],
    item: ApprovedItem,
) -> None:
    checkpoint = read_json(checkpoint_path)
    prior_attempts = (checkpoint.get("fullDocument") or {}).get("attempts", [])
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise RuntimeError("SCRATCH is not set")
    scratch_relative_path = str(
        Path(result["path"]).resolve().relative_to(Path(scratch).resolve())
    )
    checkpoint["status"] = "fetched"
    checkpoint.pop("reason", None)
    checkpoint.pop("nextRetryAt", None)
    checkpoint["fullDocument"] = {
        "url": result["url"],
        "status": "complete",
        "persisted": True,
        "scratchRelativePath": scratch_relative_path,
        "sha256": result["sha256"],
        "bytes": result["bytes"],
        "contentType": result.get("contentType", "application/pdf"),
        "retrievedAt": result.get("retrievedAt"),
        "reused": result["reused"],
        "attempts": prior_attempts,
    }
    checkpoint["nextStep"] = (
        "Inspect page-level component boundaries and select only prose explicitly attributable "
        "to Jacques Sevin before OCR."
    )
    write_json(checkpoint_path, checkpoint)


def record_fetch_error(
    checkpoint_path: Path,
    error: GallicaFetchError,
    observed_at: datetime | None = None,
) -> None:
    checkpoint = read_json(checkpoint_path)
    full_document = checkpoint.get("fullDocument") or {}
    attempts = full_document.setdefault("attempts", [])
    attempts.append(
        {
            "attempt": len(attempts) + 1,
            "attemptedAt": (observed_at or datetime.now(UTC)).astimezone(UTC).isoformat(),
            "reason": error.reason,
            "providerDiagnostics": error.diagnostics,
            "nextRetryAt": error.retry_at.astimezone(UTC).isoformat()
            if error.retry_at
            else None,
        }
    )
    full_document.update(
        {
            "status": "retry-pending" if error.retry_at else "failed",
            "persisted": False,
            "providerDiagnostics": error.diagnostics,
        }
    )
    checkpoint["fullDocument"] = full_document
    checkpoint["status"] = "retry-pending" if error.retry_at else "failed"
    checkpoint["reason"] = error.reason
    if error.retry_at:
        checkpoint["nextRetryAt"] = error.retry_at.astimezone(UTC).isoformat()
    else:
        checkpoint.pop("nextRetryAt", None)
    write_json(checkpoint_path, checkpoint)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--artifact", choices=sorted(MAX_BYTES), required=True)
    parser.add_argument("--view", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    item = load_approved_item(args.source_id)
    url = artifact_url(item, args.artifact, args.view)
    output = args.output or default_output(item, args.artifact, args.view)
    assert_scratch_output(output)
    checkpoint_path = args.checkpoint or DEFAULT_CHECKPOINT_DIR / f"{item.source_id}.json"
    checkpoint = read_json(checkpoint_path) if checkpoint_path.exists() else {}
    now = datetime.now(UTC)
    needs_network = args.refresh or not output.exists()
    retry_at = active_cooldown(checkpoint, now) if needs_network else None

    if not args.execute:
        payload = {
            "status": "dry-run",
            "sourceId": item.source_id,
            "artifact": args.artifact,
            "url": url,
            "output": str(output),
            "rateLimitPerMinute": item.rate_limit_per_minute,
            "requiredAttribution": item.required_attribution,
            "cooldownActive": retry_at is not None,
            "wouldUseNetwork": needs_network,
        }
        if retry_at:
            payload["nextRetryAt"] = retry_at.isoformat()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if retry_at:
        raise SystemExit(f"Gallica cooldown is active; nextRetryAt={retry_at.isoformat()}")
    if needs_network:
        next_allowed = reserve_request_slot(
            default_provider_state_path(), now, item.rate_limit_per_minute
        )
        if next_allowed:
            raise SystemExit(
                f"Gallica request interval is active; nextAllowedAt={next_allowed.isoformat()}"
            )

    try:
        result = fetch_artifact(
            item,
            args.artifact,
            output,
            view=args.view,
            expected_sha256=args.expected_sha256,
            refresh=args.refresh,
            now=now,
        )
    except GallicaFetchError as error:
        if args.artifact == "pdf" and checkpoint_path.exists():
            record_fetch_error(checkpoint_path, error)
        suffix = f"; nextRetryAt={error.retry_at.isoformat()}" if error.retry_at else ""
        raise SystemExit(f"{error.reason}{suffix}") from error
    if args.artifact == "pdf" and checkpoint_path.exists():
        record_pdf_success(checkpoint_path, result, item)
    print(json.dumps({"status": "ready", **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
