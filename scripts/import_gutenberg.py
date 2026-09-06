#!/usr/bin/env python3
"""Deterministically import curated activities from pinned Gutenberg HTML."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, VAULT, dump_markdown, load_markdown, source_hash, write_json
from gutenberg import Block, default_cache_path, fetch, parse_html, parse_text


DEFAULT_MANIFEST = ROOT / "config" / "imports" / "pg-65993.yaml"
REPORT_PATH = ROOT / "data" / "reports" / "pg-65993-extraction.json"
HTML_PARSER_VERSION = "gutenberg-html-blocks-v2"
TEXT_PARSER_VERSION = "gutenberg-text-paragraphs-v1"
ACTIVITY_KEYS = {
    "id",
    "title",
    "section",
    "start",
    "endBefore",
    "stripPrefix",
    "preserveStartLabel",
}
LOCATOR_KEYS = {"page", "text", "prefix"}


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
        raise ValueError(f"Unsupported Gutenberg import manifest: {path}")
    activities = manifest.get("activities")
    if not isinstance(activities, list) or not activities:
        raise ValueError(f"Gutenberg import manifest has no activities: {path}")
    source = manifest.get("source") or {}
    source_id = source.get("id")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError(f"Gutenberg import manifest has no source ID: {path}")
    activity_prefix = source.get("activityPrefix") or source_id.split("-", 1)[0]
    if not isinstance(activity_prefix, str) or not re.fullmatch(r"[a-z][a-z0-9]*", activity_prefix):
        raise ValueError(f"Gutenberg import manifest has an invalid activity prefix: {path}")
    source["activityPrefix"] = activity_prefix
    download_format = (manifest.get("download") or {}).get("format", "html")
    if download_format not in {"html", "text"}:
        raise ValueError(f"Gutenberg import manifest has an invalid download format: {download_format}")
    ids: list[str] = []
    for index, item in enumerate(activities, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Activity {index} is not an object")
        unexpected = set(item) - ACTIVITY_KEYS
        if unexpected:
            raise ValueError(f"Activity {index} has unexpected keys: {sorted(unexpected)}")
        for field in ("id", "title", "section"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"Activity {index} lacks a non-empty {field}")
        if not re.fullmatch(rf"{re.escape(activity_prefix)}-\d{{3}}", item["id"]):
            raise ValueError(f"Activity {index} has an invalid ID: {item['id']}")
        ids.append(item["id"])
        for locator_name in ("start", "endBefore"):
            locator = item.get(locator_name)
            if not isinstance(locator, dict) or set(locator) - LOCATOR_KEYS:
                raise ValueError(f"Activity {item['id']} has an invalid {locator_name} locator")
            if not isinstance(locator.get("page"), int) or locator["page"] <= 0:
                raise ValueError(f"Activity {item['id']} has an invalid {locator_name} page")
            selectors = [key for key in ("text", "prefix") if isinstance(locator.get(key), str) and locator[key]]
            if len(selectors) != 1 or set(locator) != {"page", selectors[0]}:
                raise ValueError(f"Activity {item['id']} {locator_name} must use exactly one text selector")
        if "stripPrefix" in item and (not isinstance(item["stripPrefix"], str) or not item["stripPrefix"]):
            raise ValueError(f"Activity {item['id']} has an invalid stripPrefix")
        if "preserveStartLabel" in item and item["preserveStartLabel"] is not True:
            raise ValueError(f"Activity {item['id']} preserveStartLabel must be true when present")
        if item.get("stripPrefix") and item.get("preserveStartLabel"):
            raise ValueError(f"Activity {item['id']} cannot strip and preserve its start label")
    if len(ids) != len(set(ids)):
        raise ValueError("Gutenberg import activity IDs are not unique")
    return manifest


def locator_key(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))


def locate(blocks: list[Block], locator: dict[str, Any]) -> int:
    page = int(locator["page"])
    expected = locator_key(str(locator.get("text") or locator.get("prefix") or ""))
    prefix = "prefix" in locator
    matches: list[int] = []
    for index, block in enumerate(blocks):
        if not (block.page_start <= page <= block.page_end):
            continue
        values = [block.text]
        if block.leading_small_caps:
            values.append(block.leading_small_caps)
        keys = [locator_key(value) for value in values]
        if any(key.startswith(expected) if prefix else key == expected for key in keys):
            matches.append(index)
    if len(matches) != 1:
        raise ValueError(f"Locator {locator} matched {len(matches)} blocks: {matches}")
    return matches[0]


def strip_prefix(text: str, prefix: str) -> str:
    normalized_text = re.sub(r"\s+", " ", text).strip()
    normalized_prefix = re.sub(r"\s+", " ", prefix).strip()
    if not normalized_text.startswith(normalized_prefix):
        raise ValueError(f"Expected body prefix {prefix!r} in {normalized_text[:100]!r}")
    return normalized_text[len(normalized_prefix) :].lstrip()


def strip_leading_title(block: Block) -> str:
    text = block.text
    label = block.leading_small_caps
    if not label:
        return text
    match = re.search(re.escape(label), text, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Leading small-caps title {label!r} is absent from its block")
    return re.sub(r"^[\s\"'’.—:;,\-]+", "", text[match.end() :])


def block_markdown(block: Block, text: str | None = None) -> str:
    value = (text if text is not None else block.text).strip()
    if not value:
        return ""
    if block.kind.startswith("h"):
        return f"### {value}"
    if block.kind == "tr":
        return f"- {value}"
    if block.kind == "line":
        return f"    {value}"
    return value


def extract_activity(blocks: list[Block], item: dict[str, Any]) -> tuple[dict[str, Any], str]:
    start = locate(blocks, item["start"])
    end = locate(blocks, item["endBefore"])
    if start >= end:
        raise ValueError(f"Invalid block range for {item['id']}: {start}..{end}")
    selected = blocks[start:end]
    first_text: str | None = None
    if selected[0].kind.startswith("h") or locator_key(selected[0].text) == locator_key(item["title"]):
        selected = selected[1:]
    elif item.get("stripPrefix"):
        first_text = strip_prefix(selected[0].text, str(item["stripPrefix"]))
    elif selected[0].leading_small_caps and not item.get("preserveStartLabel"):
        first_text = strip_leading_title(selected[0])
    if not selected:
        raise ValueError(f"Empty block range for {item['id']}")
    rendered: list[str] = []
    for index, block in enumerate(selected):
        value = first_text if index == 0 and first_text is not None else block.text
        markdown = block_markdown(block, value)
        if markdown:
            rendered.append(markdown)
    body = "\n\n".join(rendered).strip()
    if not body:
        raise ValueError(f"Empty rendered body for {item['id']}")
    pages = sorted({page for block in selected for page in range(block.page_start, block.page_end + 1)})
    canonical_blocks = [
        {"kind": block.kind, "text": block.text, "pageStart": block.page_start, "pageEnd": block.page_end}
        for block in selected
    ]
    evidence = {
        "startBlock": start,
        "endBlockExclusive": end,
        "printedPages": pages,
        "sourceBlockSha256": hashlib.sha256(
            json.dumps(canonical_blocks, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    return evidence, body


def shingles(value: str, size: int = 5) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", value.casefold(), flags=re.UNICODE)
    return {tuple(words[index : index + size]) for index in range(max(0, len(words) - size + 1))}


def near_duplicates(records: list[tuple[dict[str, Any], str]], threshold: float = 0.45) -> list[dict[str, Any]]:
    fingerprints = [(metadata["id"], shingles(body)) for metadata, body in records]
    candidates: list[dict[str, Any]] = []
    for index, (left_id, left) in enumerate(fingerprints):
        if not left:
            continue
        for right_id, right in fingerprints[index + 1 :]:
            if not right:
                continue
            score = len(left & right) / len(left | right)
            if score >= threshold:
                candidates.append({"leftId": left_id, "rightId": right_id, "wordShingleJaccard": round(score, 6)})
    return candidates


def write_source(source: dict[str, Any], revision: str) -> None:
    metadata = {**source, "sourceRevision": f"sha256:{revision}"}
    body = f"""# {source['title']}

Źródło bibliograficzne dla wybranych gier z tekstu w domenie publicznej. Pełna książka,
warstwa Project Gutenberg i ilustracje nie są kopiowane do repozytorium.

- [Rekord i oznaczenie praw w Project Gutenberg]({source['sourceUrl']})
- [Wydanie HTML z paginacją drukowaną]({source['digitalEditionUrl']})
- Polityka prawna: `{source['approvalPolicyId']}`
"""
    dump_markdown(VAULT / "sources" / f"{source['id']}.md", metadata, body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    source = manifest["source"]
    download = manifest["download"]
    download_format = download.get("format", "html")
    suffix = ".txt" if download_format == "text" else ".htm"
    input_path = args.input or default_cache_path(str(source["ebookId"]), suffix)
    revision = fetch(download["url"], input_path, download["sha256"])
    parser_version = TEXT_PARSER_VERSION if download_format == "text" else HTML_PARSER_VERSION
    blocks = parse_text(input_path.read_bytes()) if download_format == "text" else parse_html(input_path.read_bytes())
    write_source(source, revision)

    activity_ids = {item["id"] for item in manifest["activities"]}
    for path in (VAULT / "activities").glob(f"{source['activityPrefix']}-*.md"):
        if path.stem not in activity_ids:
            path.unlink()

    imported: list[tuple[dict[str, Any], str]] = []
    report_items: list[dict[str, Any]] = []
    for item in manifest["activities"]:
        evidence, body = extract_activity(blocks, item)
        first_page = evidence["printedPages"][0]
        facsimile_template = source.get("facsimileUrlTemplate")
        facsimile_url = (
            str(facsimile_template).format(page=first_page)
            if facsimile_template
            else source["digitalEditionUrl"]
        )
        metadata = {
            "id": item["id"],
            "kinds": ["game"],
            "sourceId": source["id"],
            "sourceRevision": f"sha256:{revision}",
            "originalLanguage": source["originalLanguage"],
            "title": item["title"],
            "traits": [],
            "section": item["section"],
            "printedPages": evidence["printedPages"],
            "transcriptionStatus": "digital-proofread",
            "extractionMethod": parser_version,
            "sourceBlockSha256": evidence["sourceBlockSha256"],
            "safetyStatus": "historical-unreviewed",
            "rightsStatus": "public-domain",
            "sourceUrl": source["sourceUrl"],
            "digitalEditionUrl": source["digitalEditionUrl"],
            "facsimileUrl": facsimile_url,
            "sourceHash": source_hash(item["title"], body),
        }
        dump_markdown(VAULT / "activities" / f"{item['id']}.md", metadata, body)
        imported.append((metadata, body))
        report_items.append({"id": item["id"], "title": item["title"], **evidence})

    all_records = list(imported)
    for path in sorted((VAULT / "activities").glob("*.md")):
        if path.stem not in activity_ids:
            all_records.append(load_markdown(path))
    hashes: dict[str, list[str]] = {}
    for metadata, body in all_records:
        hashes.setdefault(hashlib.sha256(body.encode("utf-8")).hexdigest(), []).append(metadata["id"])
    exact_duplicates = [ids for ids in hashes.values() if len(ids) > 1 and any(value in activity_ids for value in ids)]
    report = {
        "schemaVersion": 1,
        "sourceId": source["id"],
        "sourceUrl": source["sourceUrl"],
        "downloadUrl": download["url"],
        "sourceSha256": revision,
        "parserVersion": parser_version,
        "transcriptionEvidence": manifest["transcriptionEvidence"],
        "selection": manifest["selection"],
        "activityCount": len(imported),
        "activities": report_items,
        "deduplication": {
            "exactBodyMatches": exact_duplicates,
            "nearDuplicateThreshold": 0.45,
            "nearDuplicateCandidates": near_duplicates(all_records),
        },
        "reviewRequired": True,
        "wholeSourceCopiedToRepository": False,
    }
    report_path = ROOT / source.get("extractionReport", str(REPORT_PATH.relative_to(ROOT)))
    checkpoint_path = ROOT / source.get(
        "checkpoint", f"data/checkpoints/{source['id']}-import.json"
    )
    write_json(report_path, report)
    write_json(
        checkpoint_path,
        {
            "schemaVersion": 1,
            "pipeline": f"{source['id']}-import",
            "status": "extraction-complete",
            "sourceSha256": revision,
            "activityCount": len(imported),
            "nextStep": "translate-en-pl",
        },
    )
    print(f"Imported {len(imported)} games from {source['title']} ({revision[:12]}).")


if __name__ == "__main__":
    main()
