#!/usr/bin/env python3
"""Fetch one missing Gallica IIIF view per invocation with a resumable checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common import ROOT, read_json, write_json
from gallica import (
    DEFAULT_CHECKPOINT_DIR,
    GallicaFetchError,
    active_cooldown,
    default_output,
    default_provider_state_path,
    fetch_artifact,
    load_approved_item,
    reserve_request_slot,
)


MAX_VIEWS = 1000


def pagination_views(source_id: str) -> int:
    item = load_approved_item(source_id)
    path = default_output(item, "pagination")
    if not path.exists():
        raise RuntimeError("Gallica pagination cache is missing")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise RuntimeError("Gallica pagination cache exceeds the size limit")
    data = path.read_bytes()
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise RuntimeError("Gallica pagination must not contain DTD or entity declarations")
    root = ET.fromstring(data)
    identifier = root.findtext("./structure/idUPN")
    count_text = root.findtext("./structure/nbVueImages")
    pages = root.findall("./pages/page")
    if identifier != item.identifier:
        raise RuntimeError("Gallica pagination identifier differs from the approved item")
    try:
        count = int(count_text or "")
        orders = [int(page.findtext("ordre") or "") for page in pages]
    except ValueError as error:
        raise RuntimeError("Gallica pagination contains invalid view numbers") from error
    if not 1 <= count <= MAX_VIEWS or len(pages) != count or orders != list(range(1, count + 1)):
        raise RuntimeError("Gallica pagination view count or order is inconsistent")
    return count


def valid_cached_view(path: Path, expected_sha256: str | None = None) -> bool:
    if not path.exists():
        return False
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8"):
        return False
    digest = hashlib.sha256(data).hexdigest()
    return expected_sha256 is None or digest == expected_sha256


def known_view_entry(checkpoint: dict[str, Any], view: int) -> dict[str, Any] | None:
    candidates = list((checkpoint.get("viewFetch") or {}).get("items", []))
    candidates.extend(checkpoint.get("downloadedViewSmoke") or [])
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        recorded_view = entry.get("view")
        if isinstance(recorded_view, str) and recorded_view == f"f{view}":
            recorded_view = view
        if recorded_view != view:
            continue
        digest = entry.get("sha256")
        if (
            isinstance(digest, str)
            and len(digest) == 64
            and all(character in "0123456789abcdef" for character in digest)
        ):
            return entry
    return None


def reusable_cached_view(checkpoint: dict[str, Any], source_id: str, view: int) -> bool:
    item = load_approved_item(source_id)
    known = known_view_entry(checkpoint, view)
    return bool(
        known
        and valid_cached_view(default_output(item, "view", view), known["sha256"])
    )


def completed_views(checkpoint: dict[str, Any], source_id: str) -> set[int]:
    item = load_approved_item(source_id)
    completed: set[int] = set()
    for entry in (checkpoint.get("viewFetch") or {}).get("items", []):
        view = entry.get("view")
        digest = entry.get("sha256")
        if not isinstance(view, int) or not isinstance(digest, str):
            continue
        if valid_cached_view(default_output(item, "view", view), digest):
            completed.add(view)
    return completed


def next_pending_view(checkpoint: dict[str, Any], source_id: str, count: int) -> int | None:
    completed = completed_views(checkpoint, source_id)
    return next((view for view in range(1, count + 1) if view not in completed), None)


def record_view_success(
    checkpoint_path: Path,
    source_id: str,
    count: int,
    view: int,
    result: dict[str, Any],
) -> bool:
    checkpoint = read_json(checkpoint_path)
    if checkpoint.get("sourceId") != source_id:
        raise RuntimeError("Gallica view result sourceId differs from checkpoint")
    prior = known_view_entry(checkpoint, view)
    state = checkpoint.setdefault("viewFetch", {})
    items = [
        entry
        for entry in state.get("items", [])
        if isinstance(entry.get("view"), int)
        and 1 <= entry["view"] <= count
        and entry["view"] != view
    ]
    items.append(
        {
            "view": view,
            "status": "complete",
            "url": result["url"],
            "scratchRelativePath": str(
                Path(result["path"]).resolve().relative_to(Path(os.environ["SCRATCH"]).resolve())
            ),
            "sha256": result["sha256"],
            "bytes": result["bytes"],
            "retrievedAt": result.get("retrievedAt")
            or (prior or {}).get("retrievedAt"),
            "reused": result["reused"],
        }
    )
    items.sort(key=lambda entry: entry["view"])
    state.update(
        {
            "strategy": "iiif-view-fallback-after-two-pdf-429s",
            "status": "in-progress",
            "totalViews": count,
            "completedViews": len(items),
            "items": items,
        }
    )
    state.pop("reason", None)
    state.pop("nextRetryAt", None)
    state.pop("providerDiagnostics", None)
    complete = len(items) == count
    if complete:
        state["status"] = "complete"
        state["completedAt"] = datetime.now(UTC).isoformat()
        checkpoint["status"] = "views-fetched"
        checkpoint["nextStep"] = (
            "Build a contact sheet on an x86_64 CPU node and identify only prose views "
            "explicitly attributable to Jacques Sevin."
        )
    else:
        checkpoint["status"] = "view-fetch-in-progress"
        checkpoint["nextStep"] = "Resume the next missing Gallica IIIF view after the provider interval."
    checkpoint["fetchStrategy"] = state["strategy"]
    checkpoint.pop("reason", None)
    checkpoint.pop("nextRetryAt", None)
    write_json(checkpoint_path, checkpoint)
    return complete


def record_view_error(
    checkpoint_path: Path,
    error: GallicaFetchError,
    view: int,
    observed_at: datetime | None = None,
) -> None:
    checkpoint = read_json(checkpoint_path)
    state = checkpoint.setdefault("viewFetch", {})
    failures = state.setdefault("failedAttempts", [])
    attempted_at = observed_at or datetime.now(UTC)
    failures.append(
        {
            "attempt": len(failures) + 1,
            "view": view,
            "attemptedAt": attempted_at.astimezone(UTC).isoformat(),
            "reason": error.reason,
            "providerDiagnostics": error.diagnostics,
            "nextRetryAt": error.retry_at.astimezone(UTC).isoformat()
            if error.retry_at
            else None,
        }
    )
    state["status"] = "retry-pending" if error.retry_at else "failed"
    state["reason"] = error.reason
    state["providerDiagnostics"] = error.diagnostics
    checkpoint["status"] = state["status"]
    checkpoint["reason"] = error.reason
    if error.retry_at:
        retry_at = error.retry_at.astimezone(UTC).isoformat()
        state["nextRetryAt"] = retry_at
        checkpoint["nextRetryAt"] = retry_at
    else:
        state.pop("nextRetryAt", None)
        checkpoint.pop("nextRetryAt", None)
    write_json(checkpoint_path, checkpoint)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    item = load_approved_item(args.source_id)
    count = pagination_views(args.source_id)
    checkpoint_path = args.checkpoint or DEFAULT_CHECKPOINT_DIR / f"{args.source_id}.json"
    checkpoint = read_json(checkpoint_path)
    if checkpoint.get("sourceId") != args.source_id:
        raise SystemExit("Gallica view checkpoint and sourceId differ")
    view = next_pending_view(checkpoint, args.source_id, count)
    if view is None:
        print(json.dumps({"status": "complete", "sourceId": args.source_id, "totalViews": count}))
        return
    output = default_output(item, "view", view)
    known = known_view_entry(checkpoint, view)
    expected_sha256 = known.get("sha256") if known else None
    needs_network = not reusable_cached_view(checkpoint, args.source_id, view)
    now = datetime.now(UTC)
    retry_at = active_cooldown(checkpoint, now)
    plan: dict[str, Any] = {
        "status": "dry-run" if not args.execute else "ready",
        "sourceId": args.source_id,
        "strategy": "iiif-view-fallback-after-two-pdf-429s",
        "nextView": view,
        "totalViews": count,
        "completedViews": len(completed_views(checkpoint, args.source_id)),
        "wouldUseNetwork": needs_network,
        "cooldownActive": retry_at is not None,
        "rateLimitPerMinute": item.rate_limit_per_minute,
    }
    if retry_at:
        plan["nextRetryAt"] = retry_at.isoformat()
    if not args.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
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
            "view",
            output,
            view=view,
            expected_sha256=expected_sha256,
            refresh=needs_network and output.exists(),
            now=now,
        )
    except GallicaFetchError as error:
        record_view_error(checkpoint_path, error, view)
        suffix = f"; nextRetryAt={error.retry_at.isoformat()}" if error.retry_at else ""
        raise SystemExit(f"{error.reason}{suffix}") from error
    complete = record_view_success(checkpoint_path, args.source_id, count, view, result)
    print(
        json.dumps(
            {**plan, "status": "complete" if complete else "ready", "result": result},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
