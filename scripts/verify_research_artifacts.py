#!/usr/bin/env python3
"""Verify durable research artifacts against their versioned checkpoint hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterator

from common import ARTIFACTS, ROOT, persisted_artifact_path


CHECKPOINT_GLOBS = (
    "data/checkpoints/source-acquisition/*.json",
    "data/checkpoints/source-inspection/*.json",
    "data/checkpoints/gallica-fetch/*.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def records(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("artifactRelativePath"):
            yield value
        for child in value.values():
            yield from records(child)
    elif isinstance(value, list):
        for child in value:
            yield from records(child)


def expected_hash(record: dict[str, Any]) -> str | None:
    value = record.get("responseSha256") or record.get("sha256")
    return str(value) if isinstance(value, str) and len(value) == 64 else None


def checkpoint_paths(source_id: str | None) -> list[Path]:
    paths = sorted({path for pattern in CHECKPOINT_GLOBS for path in ROOT.glob(pattern)})
    if source_id:
        paths = [path for path in paths if path.stem == source_id]
    return paths


def verify(source_id: str | None = None) -> dict[str, Any]:
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "artifacts/.verification-probe"],
        cwd=ROOT,
        check=False,
    )
    if ignored.returncode != 0:
        raise RuntimeError("artifacts/ is not ignored by Git")
    if not ARTIFACTS.is_dir():
        raise RuntimeError("repository artifact store is missing")

    verified: dict[Path, str] = {}
    referenced = 0
    total_bytes = 0
    for checkpoint_path in checkpoint_paths(source_id):
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        for record in records(payload):
            referenced += 1
            expected = expected_hash(record)
            if not expected:
                raise RuntimeError(
                    f"Artifact record has no usable hash: {checkpoint_path}: "
                    f"{record['artifactRelativePath']}"
                )
            path = persisted_artifact_path(record)
            if not path.is_file():
                raise RuntimeError(f"Artifact is missing: {path}")
            prior = verified.get(path)
            if prior and prior != expected:
                raise RuntimeError(f"Conflicting checkpoint hashes for artifact: {path}")
            if prior:
                continue
            observed = sha256(path)
            if observed != expected:
                raise RuntimeError(
                    f"Artifact hash mismatch: {path}; expected {expected}, observed {observed}"
                )
            verified[path] = expected
            total_bytes += path.stat().st_size
    return {
        "status": "complete",
        "artifactStore": str(ARTIFACTS.relative_to(ROOT)),
        "checkpointCount": len(checkpoint_paths(source_id)),
        "referencedRecords": referenced,
        "uniqueFilesVerified": len(verified),
        "verifiedBytes": total_bytes,
        "sourceId": source_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id")
    args = parser.parse_args()
    print(json.dumps(verify(args.source_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
