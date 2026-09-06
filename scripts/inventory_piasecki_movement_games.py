#!/usr/bin/env python3
"""Build a deterministic candidate inventory for Piasecki's 1922 movement-games book."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from common import ROOT, read_json, write_json


SOURCE_ID = "piasecki-movement-games-1922"
INSPECTION_PATH = ROOT / "data" / "checkpoints" / "source-inspection" / f"{SOURCE_ID}.json"
REPORT_PATH = ROOT / "data" / "reports" / f"{SOURCE_ID}-candidates.json"
TOC_PDF_PAGES = range(232, 238)
BODY_PDF_PAGES = range(60, 232)
SPECIAL_PRINTED_PAGES = {49: 96, 50: 97}


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def compact(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in value if character.isalnum())


def parse_toc(pages: list[str]) -> list[dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    for pdf_page in TOC_PDF_PAGES:
        for line_number, raw_line in enumerate(pages[pdf_page - 1].splitlines(), start=1):
            line = normalize_space(raw_line)
            for _ in range(3):
                line = re.sub(r"(\d)\s+(\d)(\s*[>,]?$)", r"\1\2\3", line)
            match = re.match(r"^(\d{1,3})\.?\s+(.+?)(\d{2,3})\s*[>,]?$", line)
            if match:
                number = int(match.group(1))
                printed_page = int(match.group(3))
                title = re.sub(r"[\s.·•,\-]+$", "", match.group(2)).strip()
                if 1 <= number <= 133 and 55 <= printed_page <= 224:
                    found[number] = {
                        "number": number,
                        "titleRaw": title,
                        "printedPageStart": printed_page,
                        "tocLocator": f"p{pdf_page:04d}-l{line_number:04d}",
                    }
                    continue
            missing_page = re.match(r"^(49|50)\.\s+(.+?)\s*$", line)
            if missing_page:
                number = int(missing_page.group(1))
                found[number] = {
                    "number": number,
                    "titleRaw": re.sub(r"[\s.·•,\-]+$", "", missing_page.group(2)).strip(),
                    "printedPageStart": SPECIAL_PRINTED_PAGES[number],
                    "tocLocator": f"p{pdf_page:04d}-l{line_number:04d}",
                    "printedPageInferredFromAdjacentTocEntries": True,
                }
    missing = [number for number in range(1, 134) if number not in found]
    if missing:
        raise ValueError(f"TOC parser did not recover all 133 games; missing {missing}")
    return [found[number] for number in range(1, 134)]


def logical_lines(pages: list[str]) -> list[dict[str, Any]]:
    result = []
    for pdf_page in BODY_PDF_PAGES:
        logical_line = 0
        for raw_line in pages[pdf_page - 1].splitlines():
            text = normalize_space(raw_line)
            if not text:
                continue
            logical_line += 1
            result.append(
                {
                    "pdfPage": pdf_page,
                    "line": logical_line,
                    "lineId": f"p{pdf_page:04d}-l{logical_line:04d}",
                    "text": text,
                }
            )
    return result


def title_similarity(title: str, line: str) -> float:
    line = re.sub(r"^\d{1,3}\s*\.?\s*", "", line)
    expected = compact(title)
    actual = compact(line)
    if not expected or not actual:
        return 0.0
    if expected in actual or actual in expected:
        return min(len(expected), len(actual)) / max(len(expected), len(actual))
    return SequenceMatcher(None, expected, actual).ratio()


def locate_starts(items: list[dict[str, Any]], lines: list[dict[str, Any]]) -> None:
    by_page: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    for position, line in enumerate(lines):
        by_page.setdefault(line["pdfPage"], []).append((position, line))
    previous_position = -1
    for item in items:
        expected_pdf_page = item["printedPageStart"] + 5
        candidates = []
        for position, line in by_page.get(expected_pdf_page, []):
            if position <= previous_position:
                continue
            score = title_similarity(item["titleRaw"], line["text"])
            candidates.append((score, position, line))
        if not candidates:
            raise ValueError(f"No body lines on expected PDF page {expected_pdf_page} for game {item['number']}")
        score, position, line = max(candidates, key=lambda value: (value[0], -value[1]))
        if score < 0.52:
            raise ValueError(
                f"Low title match for game {item['number']} on PDF page {expected_pdf_page}: {score:.3f}"
            )
        item["startPosition"] = position
        item["startLine"] = line["lineId"]
        item["pdfPageStart"] = expected_pdf_page
        item["titleLocatorMatch"] = line["text"]
        item["titleLocatorScore"] = round(score, 4)
        previous_position = position


def section_for(number: int) -> str:
    bounds = [
        (21, "Zabawy i gry chodne"),
        (30, "Zabawy i gry taneczne"),
        (82, "Gry bieżne"),
        (86, "Gry skoczne"),
        (92, "Gry kopne"),
        (95, "Gry z mocowaniem"),
        (121, "Gry rzutne"),
        (133, "Gry z podbijaniem"),
    ]
    return next(label for upper, label in bounds if number <= upper)


def discovery_cost_summary() -> dict[str, Any]:
    paths = sorted((ROOT / "data" / "checkpoints" / "source-discovery").glob(f"{SOURCE_ID}-*.json"))
    actual = 0.0
    reserved = 0.0
    attempts = []
    for path in paths:
        payload = read_json(path)
        usage = payload.get("usage") or {}
        actual += float(usage.get("referenceCostUsd") or 0)
        reserved += float(payload.get("reservedReferenceCostUsd") or 0)
        attempts.append(
            {
                "checkpoint": str(path.relative_to(ROOT)),
                "status": payload.get("status"),
                "promptVersion": payload.get("promptVersion"),
                "referenceCostUsd": usage.get("referenceCostUsd"),
                "reservedReferenceCostUsd": payload.get("reservedReferenceCostUsd"),
            }
        )
    return {
        "purpose": "supplemental model-assisted locator smoke tests; not authoritative extraction",
        "attemptCount": len(attempts),
        "actualReferenceCostUsd": round(actual, 8),
        "reservedReferenceCostUsd": round(reserved, 8),
        "accountedReferenceCostUsd": round(actual + reserved, 8),
        "attempts": attempts,
    }


def build_report() -> dict[str, Any]:
    inspection = read_json(INSPECTION_PATH)
    embedded = inspection.get("embeddedText") or {}
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise ValueError("SCRATCH is not set")
    text_path = Path(scratch) / str(embedded.get("scratchRelativePath") or "")
    payload = text_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != embedded.get("sha256"):
        raise ValueError("Pinned embedded-text hash mismatch")
    pages = payload.decode("utf-8", errors="strict").split("\f")
    items = parse_toc(pages)
    lines = logical_lines(pages)
    locate_starts(items, lines)
    for index, item in enumerate(items):
        start = int(item.pop("startPosition"))
        end = int(items[index + 1]["startPosition"]) - 1 if index + 1 < len(items) else len(lines) - 1
        selected = lines[start : end + 1]
        item["endLine"] = selected[-1]["lineId"]
        item["pdfPageEnd"] = selected[-1]["pdfPage"]
        item["section"] = section_for(item["number"])
        item["sourceBlockSha256"] = hashlib.sha256(
            ("\n".join(line["text"] for line in selected) + "\n").encode("utf-8")
        ).hexdigest()
        item["componentReviewStatus"] = "pending-human-review"
        item["separateLyricsOrVerseReviewRequired"] = item["number"] <= 30
        if item["number"] == 103:
            item["separateContributorNamedInPreface"] = "Kazimierz Lutosławski"
    return {
        "schemaVersion": 1,
        "sourceId": SOURCE_ID,
        "sourceTitle": "Zabawy i gry ruchowe dzieci i młodzieży",
        "authorStatement": "Eugeniusz Piasecki",
        "edition": "wydanie 3 poprawione i rozszerzone",
        "year": 1922,
        "status": "candidate-inventory-complete-component-review-pending",
        "sourceText": {
            "classification": "embedded-text-available",
            "sha256": embedded.get("sha256"),
            "storage": "scratch-only",
            "pdfPages": inspection.get("pdf", {}).get("pages"),
        },
        "method": {
            "version": "piasecki-1922-toc-and-heading-locators-v1",
            "tocPdfPages": list(TOC_PDF_PAGES),
            "bodyPdfPages": [min(BODY_PDF_PAGES), max(BODY_PDF_PAGES)],
            "printedToPdfPageOffset": 5,
            "normalization": [
                "collapse whitespace only for locator matching and hashing",
                "retain raw OCR title and exact PDF-page/line provenance",
                "do not emit or modernize full source text",
            ],
            "locatorCaveat": "Candidate ranges run from one numbered heading to the line before the next; page furniture and separately authored sub-blocks still require block review before import.",
        },
        "selection": {
            "productionKind": "game",
            "tocGameCount": 133,
            "candidateCount": len(items),
            "importedActivityCount": 0,
            "rightsScope": "Piasecki's own prose only; illustrations, music, lyrics, quoted text and separate contributions remain excluded.",
            "humanReviewRequiredBeforeFullTextPublication": True,
            "knownComponentExceptions": [
                "Games 1-30 combine rule prose with verse or song material requiring block-level exclusion.",
                "The preface separately credits Kazimierz Lutosławski with the description of game 103, Kręgle polskie.",
                "The preface states that some unclear descriptions were repeated verbatim and that the collection draws on printed and living traditions; quotation and attribution evidence must be reviewed per game.",
            ],
        },
        "supplementalDiscovery": discovery_cost_summary(),
        "candidates": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.execute:
        write_json(REPORT_PATH, report)
    print(
        json.dumps(
            {
                "mode": "execute" if args.execute else "dry-run",
                "sourceId": SOURCE_ID,
                "candidateCount": report["selection"]["candidateCount"],
                "status": report["status"],
                "reportPath": str(REPORT_PATH.relative_to(ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
