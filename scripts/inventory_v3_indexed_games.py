#!/usr/bin/env python3
"""Inventory game-like entries from two V3 books with embedded text.

The reports deliberately stop at page/heading provenance.  They do not emit full
source text and do not decide whether a block is safe to publish; both books say
that material from other authors was incorporated.
"""

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


def _items(section: str, values: list[tuple[str, int]]) -> list[dict[str, Any]]:
    return [
        {"titleRaw": title, "printedPageStart": printed_page, "section": section}
        for title, printed_page in values
    ]


SOURCE_PLANS: dict[str, dict[str, Any]] = {
    "piasecki-schreiber-polish-scoutcraft-1917": {
        "sourceTitle": "Harce młodzieży polskiej",
        "authorStatement": "Mieczysław Schreiber i Eugeniusz Piasecki",
        "edition": "wydanie 2",
        "year": 1917,
        "printedToPdfPageOffset": 15,
        "methodVersion": "harce-1917-index-and-heading-locators-v1",
        "candidates": (
            _items("Zabawy harcerzy — zimą", [
                ("Wyprawa do bieguna", 53), ("Twierdza ze śniegu", 54),
                ("Ucieczka Sybiraka", 54),
            ])
            + _items("Zabawy harcerzy — w lecie i w zimie", [
                ("Kozak i Tatarzyn", 55), ("Goniec", 55), ("Gra Kima", 56),
            ])
            + _items("Zwiady i orientacja", [
                ("Przewodnik", 73), ("Gdzie północ?", 73),
                ("Podejście czaty", 74), ("Świstaki", 76),
                ("Połów wieloryba", 80),
            ])
            + _items("Sygnały i rozkazy", [
                ("Goniec Króla Jegomości", 93), ("Karawana", 94),
                ("Wyścig zwiadowców", 94),
            ])
            + _items("Gry obozowe", [
                ("Palant", 142), ("Piłka nożna", 142), ("Piłka koszykowa", 142),
            ])
            + _items("Gry obserwacyjne", [
                ("Szukaj naparstka", 151), ("Okna sklepowe", 151),
                ("Co zawiera pokój?", 152), ("Rozpoznawanie obrazków", 152),
                ("Zając i charty", 152), ("Węch harcerza", 153),
                ("Daleko i blizko", 153),
            ])
            + _items("Ćwiczenia i gry tropicielskie", [
                ("Pamięć tropu", 165), ("Rysowanie tropu", 165),
                ("Wskaż złodzieja!", 165), ("Przemytnicy", 166),
            ])
            + _items("Podchodzenie", [
                ("Polowanie na harcerza", 175),
                ("Kuryer Rządu Narodowego", 176), ("Bieg rozstawny", 176),
                ("Podejście zwierzyny", 176), ("Podejście i sprawozdanie", 177),
                ("Pająk i mucha", 177), ("Porwanie chorągwi", 179),
            ])
            + _items("Myślistwo i rośliny", [
                ("Łowy na niedźwiedzia", 189), ("Wyścig za rośliną", 193),
            ])
            + _items("Rycerskość i ratownictwo", [
                ("Błędni rycerze", 220), ("Wyścig strażaków", 262),
                ("Pantomimy", 262),
            ])
        ),
        "excludedIndexEntries": [
            {"titleRaw": "Obozowe gry", "reason": "section-heading-not-a-standalone-game"},
            {"titleRaw": "Obserwacyjne gry", "reason": "section-heading-not-a-standalone-game"},
            {"titleRaw": "Tropicielskie gry", "reason": "section-heading-not-a-standalone-game"},
            {"titleRaw": "Przedstawienia dramatyczne", "reason": "activity-kind-outside-v3-production-scope"},
        ],
        "componentEvidence": [
            "The title page calls the book an adaptation based on Baden-Powell's Scouting for Boys.",
            "The first-edition preface says named collaborators supplied examples and descriptions.",
            "The report therefore inventories candidate locations but leaves every prose block pending human component review.",
        ],
    },
    "sedlaczek-scout-school-1921": {
        "sourceTitle": "Szkoła harcerza",
        "authorStatement": "Stanisław Sedlaczek",
        "edition": "wydanie 3",
        "year": 1921,
        "printedToPdfPageOffset": 1,
        "methodVersion": "sedlaczek-1921-toc-page-locators-v1",
        "candidates": (
            _items("Ćwiczenia i gry pokojowe", [
                ("Opis ściany", 55), ("Szukanie naparstka", 55), ("Kim", 65),
                ("Szukanie zegarka", 70), ("Nieład na stole", 70),
                ("Ćwiczenie węchu", 92), ("Rysowanie śladu", 118),
                ("Gra Morgana", 129), ("Ocenianie długości etc.", 138),
                ("Karton Bineta", 179), ("Dobieranie barw", 188),
            ])
            + _items("Ćwiczenia ruchowe", [
                ("Podrywka ze zwodzeniem (Kozacy i Tatarzy)", 71),
                ("Ciuciu babka", 71), ("Bieg rozstawny", 94),
                ("Ptasznik", 139), ("Walka byków", 139),
            ])
            + _items("Ćwiczenia harcowe", [
                ("Polowanie na jelenia", 15), ("Podchodzenie ślepego", 83),
                ("Przedkradanka (mur ślepych)", 83), ("Wyprawa po rośliny", 83),
                ("Ocenianie odległości", 92), ("Zbieranie bawełny", 93),
                ("Ognisko na wyścigi", 94), ("Blisko — daleko", 111),
                ("Bieg harcowy", 112), ("Tropienie za skrawkami (zając)", 118),
                ("Pamiętanie śladów", 118), ("Podchodzenie straży", 129),
                ("Podchodzenie zwierzyny", 130), ("Wycieczka po mieście", 147),
                ("Łapanka w mieście", 168), ("Rysunek śladu", 180),
                ("Fort śnieżny", 188), ("Dwaj gońce z depeszami", 189),
                ("Polowanie na lisa", 195), ("Pająk i mucha", 198),
                ("Kozacki proceder w stepie", 198), ("Zwiady w mieście", 208),
                ("Wyprawa do bieguna", 208), ("Ucieczka Sybiraka", 216),
            ])
        ),
        "excludedIndexEntries": [
            {"titleRaw": "Przepisy ogólne gier z podchodzeniem", "reason": "shared-rules-section-not-a-standalone-game"},
        ],
        "componentEvidence": [
            "The preface describes Sedlaczek as primarily the editor rather than the author of the whole book.",
            "It says most games came from Herman Mojmir, several from Edmund Cenar, and additional exercises from Tadeusz Jaroszyński.",
            "The named contributors died in 1919, 1913 and 1933 respectively, so their own prose is public domain in Poland and the EU; component attribution must still be retained.",
            "The report therefore inventories candidate locations but leaves every prose block pending human component review.",
        ],
    },
}


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def compact(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in value if character.isalnum())


def title_similarity(title: str, line: str) -> float:
    line = re.sub(r"^\s*\d+[.)]?\s*", "", line)
    expected = compact(title)
    actual = compact(line)
    if not expected or not actual:
        return 0.0
    if expected in actual:
        return 1.0 if actual.startswith(expected) else 0.9
    if actual in expected:
        return min(len(expected), len(actual)) / max(len(expected), len(actual))
    return SequenceMatcher(None, expected, actual).ratio()


def _page_lines(page: str) -> list[dict[str, Any]]:
    result = []
    logical_line = 0
    for raw_line in page.splitlines():
        text = normalize_space(raw_line)
        if not text:
            continue
        logical_line += 1
        result.append({"line": logical_line, "text": text})
    return result


def build_report(source_id: str) -> dict[str, Any]:
    plan = SOURCE_PLANS[source_id]
    inspection_path = ROOT / "data" / "checkpoints" / "source-inspection" / f"{source_id}.json"
    inspection = read_json(inspection_path)
    embedded = inspection.get("embeddedText") or {}
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise ValueError("SCRATCH is not set")
    text_path = Path(scratch) / str(embedded.get("scratchRelativePath") or "")
    payload = text_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != embedded.get("sha256"):
        raise ValueError("Pinned embedded-text hash mismatch")
    pages = payload.decode("utf-8", errors="strict").split("\f")

    candidates = []
    located_count = 0
    for number, source_item in enumerate(plan["candidates"], start=1):
        item = dict(source_item)
        expected_pdf_page = item["printedPageStart"] + plan["printedToPdfPageOffset"]
        if not 1 <= expected_pdf_page <= len(pages):
            raise ValueError(
                f"Candidate page outside PDF: {item['titleRaw']} -> {expected_pdf_page}"
            )
        ranked = sorted(
            (
                (title_similarity(item["titleRaw"], line["text"]), pdf_page, line)
                for pdf_page in range(
                    max(1, expected_pdf_page - 1), min(len(pages), expected_pdf_page + 1) + 1
                )
                for line in _page_lines(pages[pdf_page - 1])
            ),
            key=lambda value: (
                value[0],
                -abs(value[1] - expected_pdf_page),
                -value[2]["line"],
            ),
            reverse=True,
        )
        score, matched_pdf_page, best = (
            ranked[0]
            if ranked
            else (0.0, expected_pdf_page, {"line": None, "text": None})
        )
        locator_status = "heading-located" if score >= 0.55 else "page-located-heading-needs-review"
        if locator_status == "heading-located":
            located_count += 1
        pdf_page = matched_pdf_page if locator_status == "heading-located" else expected_pdf_page
        lines = _page_lines(pages[pdf_page - 1])
        normalized_page = "\n".join(line["text"] for line in lines) + "\n"
        item.update(
            {
                "number": number,
                "expectedPdfPageFromIndex": expected_pdf_page,
                "pdfPageStart": pdf_page,
                "pageLocator": f"p{pdf_page:04d}",
                "bestLineLocator": f"p{pdf_page:04d}-l{best['line']:04d}" if best["line"] else None,
                "titleLocatorMatch": best["text"],
                "titleLocatorScore": round(score, 4),
                "locatorStatus": locator_status,
                "sourcePageSha256": hashlib.sha256(normalized_page.encode("utf-8")).hexdigest(),
                "componentReviewStatus": "pending-human-review",
            }
        )
        candidates.append(item)

    return {
        "schemaVersion": 1,
        "sourceId": source_id,
        "sourceTitle": plan["sourceTitle"],
        "authorStatement": plan["authorStatement"],
        "edition": plan["edition"],
        "year": plan["year"],
        "status": "candidate-inventory-complete-component-review-pending",
        "sourceText": {
            "classification": "embedded-text-available",
            "sha256": embedded.get("sha256"),
            "storage": "scratch-only",
            "pdfPages": inspection.get("pdf", {}).get("pages"),
        },
        "method": {
            "version": plan["methodVersion"],
            "printedToPdfPageOffset": plan["printedToPdfPageOffset"],
            "normalization": [
                "collapse whitespace only for title matching and page hashing",
                "retain printed/PDF page and best-line provenance",
                "do not emit or modernize full source text",
            ],
            "locatorCaveat": "A page-level locator is retained when OCR prevents a reliable heading match; exact block boundaries remain a review task.",
        },
        "selection": {
            "productionKind": "game",
            "candidateCount": len(candidates),
            "headingLocatedCount": located_count,
            "pageOnlyLocatorCount": len(candidates) - located_count,
            "importedActivityCount": 0,
            "humanReviewRequiredBeforeFullTextPublication": True,
            "componentEvidence": plan["componentEvidence"],
            "excludedIndexEntries": plan["excludedIndexEntries"],
        },
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_id", choices=sorted(SOURCE_PLANS))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    report = build_report(args.source_id)
    report_path = ROOT / "data" / "reports" / f"{args.source_id}-candidates.json"
    if args.execute:
        write_json(report_path, report)
    print(json.dumps({
        "mode": "execute" if args.execute else "dry-run",
        "sourceId": args.source_id,
        "candidateCount": report["selection"]["candidateCount"],
        "headingLocatedCount": report["selection"]["headingLocatedCount"],
        "pageOnlyLocatorCount": report["selection"]["pageOnlyLocatorCount"],
        "reportPath": str(report_path.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
