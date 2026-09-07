from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"
GENERATED = ROOT / "data" / "generated"
PUBLIC_DATA = ROOT / "public" / "data"
ARTIFACTS = ROOT / "artifacts"


def assert_artifact_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ARTIFACTS.resolve())
    except ValueError as error:
        raise ValueError(f"Path is outside the repository artifact store: {path}") from error
    return resolved


def artifact_relative_path(path: Path) -> str:
    return str(assert_artifact_path(path).relative_to(ROOT.resolve()))


def persisted_artifact_path(record: dict[str, Any]) -> Path:
    """Resolve a durable artifact, with a read-only fallback for legacy scratch records."""
    relative = record.get("artifactRelativePath")
    if relative:
        return assert_artifact_path(ROOT / str(relative))

    legacy = record.get("scratchRelativePath")
    if not legacy:
        raise ValueError("Artifact record has no persisted path")
    legacy_path = Path(str(legacy))
    parts = legacy_path.parts
    if len(parts) >= 2 and parts[0] == "scouting-autoresearch":
        durable = assert_artifact_path(ARTIFACTS.joinpath(*parts[1:]))
        if durable.exists():
            return durable
    scratch = os.environ.get("SCRATCH")
    if scratch:
        candidate = (Path(scratch) / legacy_path).resolve()
        allowed = (Path(scratch) / "scouting-autoresearch").resolve()
        try:
            candidate.relative_to(allowed)
        except ValueError as error:
            raise ValueError("Legacy artifact path is outside project scratch") from error
        return candidate
    raise ValueError("Legacy artifact is absent from the durable store and SCRATCH is not set")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_hash(title: str, body: str) -> str:
    canonical = f"{title.strip()}\n{body.strip()}\n".encode("utf-8")
    return sha256_bytes(canonical)


def dump_markdown(path: Path, metadata: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
    ).strip()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(f"---\n{frontmatter}\n---\n\n{body.strip()}\n", encoding="utf-8")
    temporary.replace(path)


def load_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Missing YAML frontmatter: {path}")
    try:
        raw_meta, body = text[4:].split("\n---\n", 1)
    except ValueError as error:
        raise ValueError(f"Unclosed YAML frontmatter: {path}") from error
    metadata = yaml.safe_load(raw_meta) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Frontmatter is not an object: {path}")
    return metadata, body.strip()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
