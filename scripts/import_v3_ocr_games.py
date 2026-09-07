#!/usr/bin/env python3
"""Import reviewed V3 game blocks from pinned OCR responses in scratch.

The raw OCR and page images stay outside the repository. Imported activity files
contain only bounded game blocks plus provenance links to the exact library object
and starting facsimile image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from common import ROOT, VAULT, dump_markdown, read_json, source_hash, write_json
from inventory_v3_ocr_games import (
    SOURCE_PLANS,
    _block_text,
    _line_from_locator,
    load_ocr_pages,
    normalize_space,
)


RUN_CHECKPOINT = (
    ROOT
    / "data"
    / "checkpoints"
    / "research-runs"
    / "v3-source-expansion-2026-09.json"
)


@dataclass(frozen=True)
class ImportPlan:
    prefix: str
    sections: tuple[tuple[int, str], ...]
    author: str
    title: str
    year: int
    edition: str
    publication_place: str
    publisher: str
    source_url: str
    rights_evidence_url: str
    rights_statement: str
    accessed_on: str
    extraction_recipe: str
    accepted_numbers: tuple[int, ...]


IMPORT_PLANS = {
    "zwolakowska-cub-pack-1945": ImportPlan(
        prefix="wgz",
        sections=(
            (24, "Dział I"),
            (39, "Dział II"),
            (63, "Dział III"),
            (74, "Dział IV"),
        ),
        author="praca zbiorowa pod redakcją Jadwigi Zwolakowskiej",
        title="W gromadzie zuchów",
        year=1945,
        edition="Biblioteka Harcerska",
        publication_place="New York",
        publisher="Gril Scouts of America",
        source_url="https://polona.pl/preview/3f71abd7-af13-4f31-9b48-cab79f380362",
        rights_evidence_url=(
            "https://polona.pl/api/library-object-query/digital-objects/"
            "3f71abd7-af13-4f31-9b48-cab79f380362"
        ),
        rights_statement="„Domena Publiczna” — oznaczenie konkretnego obiektu w Polonie",
        accessed_on="2026-09-07",
        extraction_recipe="v3-bounded-ocr-game-import-v1",
        accepted_numbers=tuple(range(1, 75)),
    ),
}


def parse_end_locator(locator: str) -> tuple[int, int] | None:
    if locator.endswith("-eof"):
        return None
    match = re.fullmatch(r"view-(\d{4})-l(\d{4})", locator)
    if not match:
        raise ValueError(f"Unexpected end locator: {locator}")
    return int(match.group(1)), int(match.group(2))


def clean_source_block(raw_block: str) -> str:
    """Remove only deterministic OCR furniture, never modernize source prose."""
    lines = raw_block.splitlines()
    if not lines:
        raise ValueError("Empty source block")
    lines = lines[1:]  # candidate title is represented in frontmatter
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r"\d{1,3}", stripped):
            continue
        if re.fullmatch(r"#{1,6}\s+DZIAŁ\s+[IVXLCDM]+\.?", stripped, re.IGNORECASE):
            continue
        kept.append(line.rstrip())
    body = "\n".join(kept).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(
        r"(?<=[\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ])\n\n(?=[a-ząćęłńóśźż])",
        " ",
        body,
    )
    if not body:
        raise ValueError("Source block contains no prose after furniture removal")
    return body


def section_for_number(plan: ImportPlan, number: int) -> str:
    for upper, section in plan.sections:
        if number <= upper:
            return section
    raise ValueError(f"No section for candidate {number}")


def source_revision(checkpoint: dict[str, Any], selected_views: set[int]) -> str:
    items = []
    for item in checkpoint.get("ocrRun", {}).get("items", []):
        match = re.fullmatch(r"view-(\d{4})\.(?:jpg|png)", str(item.get("sourceImage") or ""))
        if match and int(match.group(1)) in selected_views:
            items.append(
                {
                    "view": int(match.group(1)),
                    "sourceImageSha256": item.get("sourceImageSha256"),
                    "responseSha256": item.get("responseSha256"),
                    "model": item.get("model"),
                    "recipeVersion": item.get("recipeVersion"),
                }
            )
    items.sort(key=lambda value: value["view"])
    payload = json.dumps(items, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def import_source(source_id: str) -> dict[str, Any]:
    plan = IMPORT_PLANS[source_id]
    report_path = ROOT / "data" / "reports" / f"{source_id}-candidates.json"
    report = read_json(report_path)
    if report.get("status") not in {
        "candidate-inventory-complete-record-review-pending",
        "record-review-complete-original-imported-translation-pending",
        "complete-imported",
    }:
        raise ValueError("Candidate inventory is not ready for record review")
    candidates = report.get("candidates") or []
    accepted = [item for item in candidates if int(item["number"]) in plan.accepted_numbers]
    if len(accepted) != len(plan.accepted_numbers):
        raise ValueError("Accepted candidate numbers differ from the pinned import plan")
    if any(
        item.get("boundaryStatus")
        not in {"bounded-by-next-heading", "bounded-by-approved-range-end"}
        for item in accepted
    ):
        raise ValueError("Accepted candidates include an uncertain OCR boundary")

    checkpoint, pages = load_ocr_pages(source_id)
    pages_by_view = {page.view: page for page in pages}
    checkpoint_items = {
        int(item["viewIndex"]): item
        for item in checkpoint.get("items", [])
        if isinstance(item.get("viewIndex"), int)
    }
    activities: list[dict[str, Any]] = []
    selected_views: set[int] = set()
    output_records: list[tuple[Path, dict[str, Any], str]] = []
    source_bodies: dict[str, str] = {}

    for item in accepted:
        number = int(item["number"])
        start = (int(item["viewStart"]), _line_from_locator(item["bestLineLocator"]))
        end = parse_end_locator(str(item["endExclusiveLocator"]))
        range_end = next(
            upper
            for lower, upper in SOURCE_PLANS[source_id].body_ranges
            if lower <= start[0] <= upper
        )
        raw_block, view_end, _ = _block_text(pages_by_view, start, end, range_end)
        raw_hash = hashlib.sha256((normalize_space(raw_block) + "\n").encode("utf-8")).hexdigest()
        if raw_hash != item.get("sourceBlockSha256"):
            raise ValueError(f"Pinned block hash differs for candidate {number}")
        source_body = clean_source_block(raw_block)
        content_hash = hashlib.sha256(normalize_space(source_body).encode("utf-8")).hexdigest()
        if content_hash in source_bodies:
            raise ValueError(
                f"Exact source-body duplicate: candidate {number} and {source_bodies[content_hash]}"
            )
        source_bodies[content_hash] = str(number)

        views = set(range(start[0], view_end + 1))
        selected_views.update(views)
        printed_pages = []
        for view in sorted(views):
            label = str((checkpoint_items.get(view) or {}).get("printedLabel") or "")
            if label.isdigit() and int(label) not in printed_pages:
                printed_pages.append(int(label))
        if not printed_pages:
            raise ValueError(f"Candidate {number} lacks printed-page provenance")
        facsimile_url = str((checkpoint_items.get(start[0]) or {}).get("url") or "")
        if not facsimile_url.startswith("https://polona.pl/iiif/3/"):
            raise ValueError(f"Candidate {number} lacks a pinned Polona facsimile URL")

        activity_id = f"{plan.prefix}-{number:03d}"
        title = re.sub(r"[.\s]+$", "", normalize_space(str(item["titleRaw"])))
        source_note = (
            "---\n\n"
            f"*Źródło skanu: [Polona / Biblioteka Narodowa]({plan.source_url}), "
            f"oznaczenie „Domena Publiczna”. [Zobacz skan — widok {start[0]}]"
            f"({facsimile_url}).*"
        )
        body = f"{source_body}\n\n{source_note}"
        metadata = {
            "id": activity_id,
            "kinds": ["game"],
            "sourceId": source_id,
            "originalLanguage": "pl",
            "title": title,
            "traits": [],
            "section": section_for_number(plan, number),
            "printedPages": printed_pages,
            "sourceViewStart": start[0],
            "sourceViewEnd": view_end,
            "transcriptionStatus": "mistral-ocr-unreviewed",
            "safetyStatus": "historical-unreviewed",
            "rightsStatus": "public-domain",
            "sourceUrl": plan.source_url,
            "digitalEditionUrl": plan.source_url,
            "facsimileUrl": facsimile_url,
            "sourceHash": source_hash(title, body),
            "participantScales": ["unknown"],
            "participantScaleBasis": "unknown",
        }
        output_records.append((VAULT / "activities" / f"{activity_id}.md", metadata, body))
        activities.append(
            {
                "id": activity_id,
                "candidateNumber": number,
                "title": title,
                "viewStart": start[0],
                "viewEnd": view_end,
                "printedPages": printed_pages,
                "sourceBlockSha256": raw_hash,
                "publishedSourceHash": metadata["sourceHash"],
            }
        )

    revision = source_revision(checkpoint, selected_views)
    for output, metadata, body in output_records:
        metadata["sourceRevision"] = f"sha256:{revision}"
        dump_markdown(output, metadata, body)
    expected_names = {f"{plan.prefix}-{number:03d}.md" for number in plan.accepted_numbers}
    for stale in (VAULT / "activities").glob(f"{plan.prefix}-*.md"):
        if stale.name not in expected_names:
            stale.unlink()

    first_facsimile = str((checkpoint_items[min(selected_views)]).get("url") or "")
    extraction_path = ROOT / "data" / "reports" / f"{source_id}-extraction.json"
    source_metadata = {
        "id": source_id,
        "activityPrefix": plan.prefix,
        "author": plan.author,
        "title": plan.title,
        "year": plan.year,
        "edition": plan.edition,
        "publicationPlace": plan.publication_place,
        "publisher": plan.publisher,
        "originalLanguage": "pl",
        "rightsStatus": "public-domain",
        "rightsStatement": plan.rights_statement,
        "rightsEvidenceUrl": plan.rights_evidence_url,
        "rightsEvidence": report["selection"]["rightsEvidence"],
        "sourceUrl": plan.source_url,
        "digitalEditionUrl": plan.source_url,
        "imageServiceEvidenceUrl": first_facsimile,
        "accessedOn": plan.accessed_on,
        "sourceRevision": f"sha256:{revision}",
        "extractionReport": str(extraction_path.relative_to(ROOT)),
        "translationPolicy": {
            "targetLocale": "en",
            "modelRequested": "mistral-large-2512",
            "reasoningMode": "disabled",
            "promptVersion": "translation-pl-en-v3",
            "usageRequired": True,
            "requestBudgetRequired": True,
            "billingMode": "education-credit",
            "enforceReferenceCostLimit": True,
            "maxReferenceCostUsd": 10,
            "report": f"data/reports/{source_id}-translation-pl-en.json",
            "priceAccessedOn": "2026-09-04",
            "smokeTestActivityIds": [
                f"{plan.prefix}-{number:03d}" for number in (1, 12, 24, 47, 53, 74)
            ],
        },
    }
    source_body = (
        f"# {plan.title}\n\n"
        "Źródło bibliograficzne dla gier wyodrębnionych z obiektu bibliotecznego jawnie "
        "oznaczonego jako domena publiczna. Obrazy stron i pełna książka pozostają poza "
        "repozytorium.\n\n"
        f"- [Rekord cyfrowy w Polonie]({plan.source_url})\n"
        f"- [Dokładny dowód statusu prawnego]({plan.rights_evidence_url})\n"
    )
    dump_markdown(VAULT / "sources" / f"{source_id}.md", source_metadata, source_body)

    extraction = {
        "schemaVersion": 1,
        "sourceId": source_id,
        "sourceSha256": revision,
        "parserVersion": plan.extraction_recipe,
        "reviewRequired": False,
        "activityCount": len(activities),
        "wholeSourceCopiedToRepository": False,
        "selection": {
            "candidateCount": len(candidates),
            "acceptedGameCount": len(activities),
            "rejectedCount": len(candidates) - len(activities),
            "basis": "dedicated game chapter with bounded headings",
        },
        "transcriptionEvidence": {
            "sourceStatement": "Mistral OCR output from pinned Polona IIIF page images; raw responses remain in scratch.",
            "sourceLocation": plan.source_url,
            "deterministicNormalization": [
                "omit the repeated activity heading represented in frontmatter",
                "omit isolated numeric printed-page furniture",
                "omit the following section heading when it falls inside the preceding block",
                "join a page-break blank line only when it interrupts a word-continuing sentence",
                "preserve spelling, punctuation and paragraph order without modernization",
            ],
            "lexicalModernization": False,
        },
        "deduplication": {"exactBodyMatches": [], "nearDuplicateCandidates": []},
        "activities": activities,
    }
    write_json(extraction_path, extraction)

    accepted_numbers = set(plan.accepted_numbers)
    for item in report["candidates"]:
        item["recordReviewStatus"] = (
            "accepted-game" if int(item["number"]) in accepted_numbers else "rejected-not-game"
        )
    expected_activity_ids = sorted(item["id"] for item in activities)
    translation_report_path = (
        ROOT / "data" / "reports" / f"{source_id}-translation-pl-en.json"
    )
    translation_complete = False
    if translation_report_path.is_file():
        translation_report = read_json(translation_report_path)
        translation_complete = (
            translation_report.get("status") == "complete"
            and translation_report.get("selectedActivityIds") == expected_activity_ids
            and translation_report.get("completedActivityIds") == expected_activity_ids
            and translation_report.get("pendingActivityIds") == []
        )
    report["status"] = (
        "complete-imported"
        if translation_complete
        else "record-review-complete-original-imported-translation-pending"
    )
    report["selection"]["importedActivityCount"] = len(activities)
    report["selection"]["recordReviewRequired"] = False
    write_json(report_path, report)
    return extraction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_id", choices=sorted(IMPORT_PLANS))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        plan = IMPORT_PLANS[args.source_id]
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "sourceId": args.source_id,
                    "acceptedGameCount": len(plan.accepted_numbers),
                },
                indent=2,
            )
        )
        return
    extraction = import_source(args.source_id)
    print(json.dumps({"mode": "execute", **extraction["selection"]}, indent=2))


if __name__ == "__main__":
    main()
