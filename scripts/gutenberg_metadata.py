#!/usr/bin/env python3
"""Fetch and normalize one Project Gutenberg machine-readable RDF record."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, write_json
from gutenberg import USER_AGENT, default_cache_path


COLLECTION_ID = "project-gutenberg"
MAX_RDF_BYTES = 2 * 1024 * 1024
NAMESPACES = {
    "dcterms": "http://purl.org/dc/terms/",
    "pgterms": "http://www.gutenberg.org/2009/pgterms/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dcam": "http://purl.org/dc/dcam/",
}
RDF_RESOURCE = f"{{{NAMESPACES['rdf']}}}resource"
RDF_ABOUT = f"{{{NAMESPACES['rdf']}}}about"


def metadata_url(ebook_id: int) -> str:
    if ebook_id <= 0:
        raise ValueError("Project Gutenberg ebook ID must be positive")
    return f"https://www.gutenberg.org/cache/epub/{ebook_id}/pg{ebook_id}.rdf"


def canonical_url(ebook_id: int) -> str:
    if ebook_id <= 0:
        raise ValueError("Project Gutenberg ebook ID must be positive")
    return f"https://www.gutenberg.org/ebooks/{ebook_id}"


def assert_registry_allows_metadata() -> None:
    registry_path = ROOT / "config" / "source-registry.yaml"
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    collection = next(
        (item for item in payload.get("collections", []) if item.get("id") == COLLECTION_ID),
        None,
    )
    if not collection or collection.get("status") != "approved-by-policy":
        raise RuntimeError("Project Gutenberg is not an approved collection")
    if "metadata-only" not in collection.get("allowedMethods", []):
        raise RuntimeError("Project Gutenberg metadata access is not allowed")
    template = collection.get("metadataUrlTemplate")
    if template != "https://www.gutenberg.org/cache/epub/{ebookId}/pg{ebookId}.rdf":
        raise RuntimeError("Project Gutenberg metadata URL template is not approved")


def _text(element: ET.Element, path: str) -> str | None:
    value = element.findtext(path, namespaces=NAMESPACES)
    return value.strip() if value and value.strip() else None


def _integer(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _agents(ebook: ET.Element, relation: str) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for wrapper in ebook.findall(f"dcterms:{relation}", NAMESPACES):
        agent = wrapper.find("pgterms:agent", NAMESPACES)
        if agent is None:
            continue
        name = _text(agent, "pgterms:name")
        if not name:
            continue
        record: dict[str, Any] = {"name": name}
        birth_year = _integer(_text(agent, "pgterms:birthdate"))
        death_year = _integer(_text(agent, "pgterms:deathdate"))
        if birth_year is not None:
            record["birthYear"] = birth_year
        if death_year is not None:
            record["deathYear"] = death_year
        aliases = sorted(
            value.text.strip()
            for value in agent.findall("pgterms:alias", NAMESPACES)
            if value.text and value.text.strip()
        )
        webpages = sorted(
            value.get(RDF_RESOURCE)
            for value in agent.findall("pgterms:webpage", NAMESPACES)
            if value.get(RDF_RESOURCE)
        )
        if aliases:
            record["aliases"] = aliases
        if webpages:
            record["webpages"] = webpages
        agents.append(record)
    return sorted(agents, key=lambda item: item["name"].casefold())


def _described_values(ebook: ET.Element, relation: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for wrapper in ebook.findall(f"dcterms:{relation}", NAMESPACES):
        description = wrapper.find("rdf:Description", NAMESPACES)
        if description is None:
            continue
        value = _text(description, "rdf:value")
        if not value:
            continue
        member = description.find("dcam:memberOf", NAMESPACES)
        scheme_url = member.get(RDF_RESOURCE) if member is not None else None
        record = {"value": value}
        if scheme_url:
            record["scheme"] = scheme_url.rstrip("/").rsplit("/", 1)[-1]
        records.append(record)
    return sorted(records, key=lambda item: (item.get("scheme", ""), item["value"].casefold()))


def _bookshelves(ebook: ET.Element) -> list[str]:
    values: list[str] = []
    for wrapper in ebook.findall("pgterms:bookshelf", NAMESPACES):
        description = wrapper.find("rdf:Description", NAMESPACES)
        value = _text(description, "rdf:value") if description is not None else None
        if value:
            values.append(value)
    return sorted(values, key=str.casefold)


def _formats(ebook: ET.Element) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for wrapper in ebook.findall("dcterms:hasFormat", NAMESPACES):
        file_element = wrapper.find("pgterms:file", NAMESPACES)
        if file_element is None or not file_element.get(RDF_ABOUT):
            continue
        record: dict[str, Any] = {"url": str(file_element.get(RDF_ABOUT))}
        extent = _integer(_text(file_element, "dcterms:extent"))
        modified = _text(file_element, "dcterms:modified")
        media_types = sorted(
            {
                value
                for format_wrapper in file_element.findall("dcterms:format", NAMESPACES)
                for description in format_wrapper.findall("rdf:Description", NAMESPACES)
                if (value := _text(description, "rdf:value"))
            }
        )
        if extent is not None:
            record["bytes"] = extent
        if modified:
            record["modifiedAt"] = modified
        if media_types:
            record["mediaTypes"] = media_types
        records.append(record)
    return sorted(records, key=lambda item: item["url"])


def parse_rdf(data: bytes, ebook_id: int) -> dict[str, Any]:
    if len(data) > MAX_RDF_BYTES:
        raise ValueError("Project Gutenberg RDF exceeds the size limit")
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("Project Gutenberg RDF contains a forbidden document type or entity")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError("Invalid Project Gutenberg RDF") from error
    ebook = root.find("pgterms:ebook", NAMESPACES)
    if ebook is None:
        raise ValueError("Project Gutenberg RDF lacks an ebook record")
    if ebook.get(RDF_ABOUT) != f"ebooks/{ebook_id}":
        raise ValueError("Project Gutenberg RDF ebook ID does not match the requested ID")
    title = _text(ebook, "dcterms:title")
    issued = _text(ebook, "dcterms:issued")
    rights = _text(ebook, "dcterms:rights")
    if not title or not issued or not rights:
        raise ValueError("Project Gutenberg RDF lacks title, issued date, or rights claim")
    return {
        "ebookId": ebook_id,
        "canonicalUrl": canonical_url(ebook_id),
        "metadataUrl": metadata_url(ebook_id),
        "title": title,
        "issued": issued,
        "rightsClaim": rights,
        "languages": [item["value"] for item in _described_values(ebook, "language")],
        "creators": _agents(ebook, "creator"),
        "contributors": _agents(ebook, "contributor"),
        "subjects": _described_values(ebook, "subject"),
        "bookshelves": _bookshelves(ebook),
        "formats": _formats(ebook),
    }


def fetch_rdf(
    ebook_id: int,
    cache_path: Path,
    expected_sha256: str | None = None,
    refresh: bool = False,
) -> tuple[bytes, str, bool]:
    if cache_path.exists() and not refresh:
        data = cache_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise RuntimeError(
                f"Cached RDF hash changed: expected {expected_sha256}, received {digest}"
            )
        parse_rdf(data, ebook_id)
        return data, digest, True
    assert_registry_allows_metadata()
    request = urllib.request.Request(metadata_url(ebook_id), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        declared_size = response.headers.get("Content-Length")
        if declared_size:
            try:
                if int(declared_size) > MAX_RDF_BYTES:
                    raise RuntimeError("Project Gutenberg RDF exceeds the size limit")
            except ValueError:
                pass
        data = response.read(MAX_RDF_BYTES + 1)
    if len(data) > MAX_RDF_BYTES:
        raise RuntimeError("Project Gutenberg RDF exceeds the size limit")
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise RuntimeError(
            f"Downloaded RDF hash changed: expected {expected_sha256}, received {digest}"
        )
    parse_rdf(data, ebook_id)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(cache_path)
    return data, digest, False


def build_record(data: bytes, ebook_id: int, retrieved_at: str) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "collectionId": COLLECTION_ID,
        "retrievedAt": retrieved_at,
        "sourceSha256": hashlib.sha256(data).hexdigest(),
        **parse_rdf(data, ebook_id),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ebook-id", required=True, type=int)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    assert_registry_allows_metadata()
    cache_path = args.cache or default_cache_path(str(args.ebook_id), ".rdf")
    data, _, _ = fetch_rdf(
        args.ebook_id,
        cache_path,
        expected_sha256=args.expected_sha256,
        refresh=args.refresh,
    )
    record = build_record(data, args.ebook_id, datetime.now(UTC).isoformat())
    if args.output:
        write_json(args.output, record)
    else:
        print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
