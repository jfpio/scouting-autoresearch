#!/usr/bin/env python3
"""Acceptance checks for the committed V0 corpus and generated site."""

from __future__ import annotations

import json
import re
from pathlib import Path

from common import GENERATED, ROOT, VAULT, load_markdown, read_json, source_hash


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> None:
    errors: list[str] = []
    activity_paths = sorted((VAULT / "activities").glob("*.md"))
    translation_paths = sorted((VAULT / "translations" / "en").glob("*.md"))
    require(len(activity_paths) == 202, f"Expected 202 activities, found {len(activity_paths)}", errors)
    require(len(translation_paths) == 202, f"Expected 202 English translations, found {len(translation_paths)}", errors)

    sources = {}
    for path in (VAULT / "sources").glob("*.md"):
        metadata, _ = load_markdown(path)
        sources[metadata["id"]] = metadata
        require(metadata.get("rightsStatus") == "public-domain", f"Source {path.stem} is not public-domain", errors)
        for key in ("author", "title", "year", "sourceUrl", "rightsEvidenceUrl", "digitalEditionUrl", "pdfUrl"):
            require(bool(metadata.get(key)), f"Source {path.stem} lacks {key}", errors)

    expected_ids = {f"hwp-{number:03d}" for number in range(1, 118)} | {f"pw-{number:03d}" for number in range(1, 86)}
    actual_ids: set[str] = set()
    for path in activity_paths:
        metadata, body = load_markdown(path)
        activity_id = metadata.get("id")
        actual_ids.add(activity_id)
        require(activity_id == path.stem, f"ID/path mismatch in {path}", errors)
        require(metadata.get("sourceId") in sources, f"Unknown source in {path.name}", errors)
        require(metadata.get("rightsStatus") == "public-domain", f"Non-public full text in {path.name}", errors)
        require(bool(body.strip()), f"Empty body in {path.name}", errors)
        require(metadata.get("sourceHash") == source_hash(metadata.get("title", ""), body), f"Bad source hash in {path.name}", errors)
        require(bool(metadata.get("printedPages")), f"Missing printed pages in {path.name}", errors)
        require(bool(metadata.get("pdfPages")), f"Missing PDF pages in {path.name}", errors)
        require(metadata.get("safetyStatus") == "historical-unreviewed", f"Unexpected safety status in {path.name}", errors)
    require(actual_ids == expected_ids, f"Activity IDs differ: missing={sorted(expected_ids - actual_ids)}, extra={sorted(actual_ids - expected_ids)}", errors)

    translation_ids: set[str] = set()
    for path in translation_paths:
        metadata, body = load_markdown(path)
        activity_id = metadata.get("activityId")
        translation_ids.add(activity_id)
        original_path = VAULT / "activities" / f"{activity_id}.md"
        require(original_path.exists(), f"Translation without original: {path.name}", errors)
        if original_path.exists():
            original, original_body = load_markdown(original_path)
            expected_hash = source_hash(original["title"], original_body)
            require(metadata.get("sourceHash") == expected_hash, f"Stale translation: {path.name}", errors)
            require(
                len(metadata.get("traits", [])) == len(original.get("traits", [])),
                f"Translation invented or dropped traits: {path.name}",
                errors,
            )
        require(metadata.get("status") == "machine-translation", f"Bad translation status: {path.name}", errors)
        for key in ("model", "modelRequested", "promptVersion", "generatedAt", "title", "section"):
            require(bool(metadata.get(key)), f"Translation {path.name} lacks {key}", errors)
        require(bool(body.strip()), f"Empty translation body: {path.name}", errors)
        if original_path.exists():
            source_urls = set(re.findall(r"https?://[^\s)]+", original_body))
            translated_urls = set(re.findall(r"https?://[^\s)]+", body))
            require(source_urls.issubset(translated_urls), f"Translation dropped a URL or image: {path.name}", errors)
    require(translation_ids == expected_ids, "English and Polish record IDs differ", errors)
    models = {load_markdown(path)[0].get("model") for path in translation_paths}
    require(models == {"mistral-medium-2604"}, f"Unexpected translation model set: {sorted(models)}", errors)

    exploration_paths = sorted((VAULT / "exploration").rglob("idea-*.md"))
    require(len(exploration_paths) >= 2, "Expected seeded taxonomy and activity-kind exploration notes", errors)
    for path in exploration_paths:
        metadata, body = load_markdown(path)
        require(metadata.get("proposalType") in {"taxonomy", "activity-kind"}, f"Bad proposal type in {path}", errors)
        require(metadata.get("status") == "proposed", f"Exploration note is not proposed: {path}", errors)
        require(metadata.get("sourceType") == "editorial-hypothesis", f"Exploration note lacks hypothesis marker: {path}", errors)
        require(metadata.get("reviewRequired") is True, f"Exploration note lacks human review gate: {path}", errors)
        require(set((metadata.get("labels") or {}).keys()) == {"pl", "en"}, f"Exploration note lacks bilingual labels: {path}", errors)
        require(bool(body.strip()), f"Empty exploration note: {path}", errors)

    for locale in ("pl", "en"):
        json_path = GENERATED / f"activities.{locale}.json"
        jsonl_path = GENERATED / f"activities.{locale}.jsonl"
        require(json_path.exists(), f"Missing {json_path}", errors)
        require(jsonl_path.exists(), f"Missing {jsonl_path}", errors)
        if json_path.exists():
            records = read_json(json_path)
            require(len(records) == 202, f"{locale} export has {len(records)} records", errors)
            for record in records:
                for key in ("author", "sourceTitle", "year", "sourceId", "printedPages", "pdfPages", "sourceCommit"):
                    require(bool(record.get(key)), f"{locale}/{record.get('id')} lacks {key}", errors)
        if jsonl_path.exists():
            lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            require(len(lines) == 202, f"{locale} JSONL has {len(lines)} lines", errors)

    docs = list((ROOT / "src" / "content" / "docs").rglob("*.md")) + list((ROOT / "src" / "content" / "docs").rglob("*.mdx"))
    require(len(docs) == 418, f"Expected 418 generated docs, found {len(docs)}", errors)
    for path in docs:
        text = path.read_text(encoding="utf-8")
        require(text.startswith("---\n"), f"Missing frontmatter in {path}", errors)
        require("/harcerz-w-polu/book/" not in text or "https://jfpio.github.io/harcerz-w-polu/book/" in text, f"Broken relative source asset in {path}", errors)

    forbidden_files = [path for path in ROOT.rglob("*") if path.is_file() and (path.suffix.lower() == ".pdf" or path.name == ".env")]
    require(not forbidden_files, f"Forbidden files committed locally: {forbidden_files}", errors)
    nested_git = [path for path in ROOT.rglob(".git") if path != ROOT / ".git"]
    require(not nested_git, f"Nested repositories found: {nested_git}", errors)
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {"node_modules", ".venv", ".git"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        require(not re.search(r"MISTRAL_API_KEY[ \t]*=[ \t]*[^\s#]+", text), f"Possible Mistral secret in {path}", errors)

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("Validation passed: 202 activities, 202 translations, 2 public-domain sources, bilingual exports and docs.")


if __name__ == "__main__":
    main()
