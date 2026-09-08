#!/usr/bin/env python3
"""Inspect an acquired V3 PDF for usable embedded text on a CPU Slurm node."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common import (
    ROOT,
    artifact_relative_path,
    assert_artifact_path,
    persisted_artifact_path,
)


ACQUISITION_DIR = ROOT / "data" / "checkpoints" / "source-acquisition"
INSPECTION_DIR = ROOT / "data" / "checkpoints" / "source-inspection"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_pdfinfo(text: str) -> dict[str, Any]:
    allowed = {
        "Pages": "pages",
        "Page size": "pageSize",
        "PDF version": "pdfVersion",
        "Encrypted": "encrypted",
        "Tagged": "tagged",
    }
    result: dict[str, Any] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key not in allowed:
            continue
        value = value.strip()
        result[allowed[key]] = int(value) if key == "Pages" else value
    if not isinstance(result.get("pages"), int) or result["pages"] < 1:
        raise RuntimeError("pdfinfo did not return a positive page count")
    return result


def text_classification(text: str, pages: int) -> str:
    non_whitespace = sum(not character.isspace() for character in text)
    return (
        "embedded-text-available"
        if non_whitespace >= max(1000, pages * 20)
        else "image-ocr-required"
    )


def source_pdf(source_id: str) -> tuple[Path, dict[str, Any]]:
    checkpoint_path = ACQUISITION_DIR / f"{source_id}.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if checkpoint.get("status") != "complete" or checkpoint.get("sourceId") != source_id:
        raise RuntimeError("source acquisition is not complete")
    item = next(
        (entry for entry in checkpoint.get("items", []) if entry.get("kind") == "pdf"),
        None,
    )
    if not item:
        raise RuntimeError("source acquisition checkpoint has no PDF")
    try:
        path = persisted_artifact_path(item)
    except ValueError as error:
        raise RuntimeError("source PDF is outside the repository artifact store") from error
    if not path.is_file() or sha256(path) != item.get("sha256"):
        raise RuntimeError("source PDF is missing or does not match its acquisition hash")
    return path, item


def write_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def approved_artifact_file(path: Path) -> Path:
    try:
        resolved = assert_artifact_path(path)
    except ValueError as error:
        raise RuntimeError("inspection input is outside the repository artifact store") from error
    if not resolved.is_file():
        raise RuntimeError("inspection input is missing")
    return resolved


def inspect(source_id: str, pdfinfo_path: Path, text_path: Path) -> dict[str, Any]:
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("PDF inspection must run inside Slurm")
    pdf, item = source_pdf(source_id)
    pdfinfo_path = approved_artifact_file(pdfinfo_path)
    text_path = approved_artifact_file(text_path)
    safe_info = parse_pdfinfo(pdfinfo_path.read_text(encoding="utf-8", errors="replace"))
    text = text_path.read_text(encoding="utf-8", errors="replace")
    non_whitespace = sum(not character.isspace() for character in text)
    checkpoint = {
        "schemaVersion": 1,
        "pipeline": "v3-source-pdf-inspection",
        "sourceId": source_id,
        "status": "complete",
        "classification": text_classification(text, safe_info["pages"]),
        "sourcePdf": {
            "artifactRelativePath": artifact_relative_path(pdf),
            "sha256": item["sha256"],
            "bytes": item["bytes"],
        },
        "pdf": safe_info,
        "embeddedText": {
            "artifactRelativePath": artifact_relative_path(text_path),
            "sha256": sha256(text_path),
            "bytes": text_path.stat().st_size,
            "characters": len(text),
            "nonWhitespaceCharacters": non_whitespace,
            "lines": len(text.splitlines()),
            "replacementCharacters": text.count("\ufffd"),
        },
        "slurm": {
            "jobId": os.environ["SLURM_JOB_ID"],
            "partition": os.environ.get("SLURM_JOB_PARTITION"),
            "account": os.environ.get("SLURM_JOB_ACCOUNT"),
            "node": os.uname().nodename,
            "architecture": os.uname().machine,
            "gitRevision": subprocess.run(
                ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
            ).stdout.strip(),
        },
        "completedAt": datetime.now(UTC).isoformat(),
        "sourceFilesCommittedToRepository": 0,
    }
    write_checkpoint(INSPECTION_DIR / f"{source_id}.json", checkpoint)
    return checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--pdfinfo-file", required=True, type=Path)
    parser.add_argument("--text-file", required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.source_id, args.pdfinfo_file, args.text_file)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
