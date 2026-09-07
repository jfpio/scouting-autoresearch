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
    rejected_reasons: tuple[tuple[int, str], ...]
    repeated_headers: tuple[str, ...]
    join_soft_wraps: bool
    smoke_numbers: tuple[int, ...]
    selection_basis: str
    translation_prompt: str
    repeated_header_patterns: tuple[str, ...] = ()
    stop_heading_patterns: tuple[str, ...] = ()
    candidate_stop_headings: tuple[tuple[int, str], ...] = ()
    preserve_inline_heading_body: bool = False
    use_inventory_title: bool = False
    inline_only_numbers: tuple[int, ...] = ()
    title_overrides: tuple[tuple[int, str], ...] = ()
    heading_is_body_numbers: tuple[int, ...] = ()
    use_inventory_section: bool = False


JASINSKI_REJECTED_REASONS = (
    (65, "composite instructional essay with an embedded example but no bounded standalone game block"),
    (77, "cross-reference-only variant without a self-contained procedure"),
    (100, "heading-only signal without a bounded procedure"),
    *(
        (number, "fragment of a service-task list, not a self-contained game")
        for number in range(116, 123)
    ),
    *(
        (number, "reconnaissance checklist without a game or competitive procedure")
        for number in range(137, 149)
    ),
    *(
        (number, "interview topic or editorial guidance, not a bounded game")
        for number in range(150, 171)
    ),
    *(
        (
            number,
            "source-labelled scout-course proposal composed of multiple tasks; retained as evidence for the proposed scout-course kind outside the current game-only production scope",
        )
        for number in range(171, 186)
    ),
)


DABROWSKI_REJECTED_REASONS = (
    (55, "source names a commonly known game but supplies no self-contained procedure"),
    (116, "song dramatization without game rules or a competitive procedure"),
    (129, "educational performance proposal without game rules or a competitive procedure"),
    (133, "general knot-training advice and an external reference, not a bounded game"),
    (139, "catalogue of distinct handicraft contest ideas, not one bounded game"),
    (140, "catalogue of distinct self-reliance contest ideas, not one bounded game"),
    (141, "catalogue of distinct nature-game ideas, not one bounded game"),
    (143, "catalogue of distinct drawing contest ideas, not one bounded game"),
    (159, "general field-signalling guidance without a self-contained game procedure"),
)


PAWELEK_ACCEPTED_NUMBERS = (
    1, 2, 3, 5, 7, 8, 10, 11, 12, 13, 14, 15, 20, 21, 22, 25,
    28, 29, 30, 31, 32,
    35, 36, 38, 39, 43, 44, 45, 46, 47, 48, 49, 50, 51, 53, 57,
    63, 64, 65, 70, 71, 72, 73, 74, 75, 76, 78, 79, 80, 81, 82, 83,
    84, 85, 92, 93, 94, 97,
    101, 103, 106,
)


def _pawelek_rejected_reasons() -> tuple[tuple[int, str], ...]:
    reasons: dict[int, str] = {}

    def mark(numbers: tuple[int, ...], reason: str) -> None:
        for number in numbers:
            reasons[number] = reason

    mark(
        (4, 6, 9, 23, 24, 26, 34, 37, 40, 55, 56, 58, 62, 66, 67, 68,
         87, 88, 90, 91, 98, 99, 100, 114),
        "title, shorthand or cross-reference without a self-contained game procedure",
    )
    mark(
        (16, 17, 18, 27, 33, 42, 54, 59, 60, 61, 95, 96, 107, 108, 109,
         110, 111, 112, 113, 115),
        "technical exercise, programme item or task outside the current game-only production scope",
    )
    mark(
        (19,),
        "composite catalogue of three distinct puzzles without separate paragraph boundaries",
    )
    mark(
        (41, 52, 77, 86, 102),
        "variant or traditional game whose paragraph depends on rules supplied elsewhere",
    )
    mark(
        (69, 89),
        "fragmentary procedure without enough setup or outcome rules to stand alone",
    )
    mark(
        (104, 105),
        "observation task without a game or competitive procedure",
    )
    for accepted in PAWELEK_ACCEPTED_NUMBERS:
        reasons.pop(accepted, None)
    rejected = set(range(1, 116)) - set(PAWELEK_ACCEPTED_NUMBERS)
    missing = rejected - set(reasons)
    extra = set(reasons) - rejected
    if missing or extra:
        raise ValueError(f"Invalid Pawełek rejection plan; missing={sorted(missing)}, extra={sorted(extra)}")
    return tuple(sorted(reasons.items()))


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
        rejected_reasons=(),
        repeated_headers=(),
        join_soft_wraps=False,
        smoke_numbers=(1, 12, 24, 47, 53, 74),
        selection_basis="dedicated game chapter with bounded headings",
        translation_prompt="translation-pl-en-v3",
    ),
    "mojmir-scout-games-1912": ImportPlan(
        prefix="ciz",
        sections=((85, "Ćwiczenia i zabawy skautowe"),),
        author="Herman A. Mojmir",
        title="Ćwiczenia i zabawy skautowe",
        year=1912,
        edition="wydanie z 1912 r.",
        publication_place="Lwów",
        publisher="Związek polskich towarzystw gimnast. sokolich",
        source_url="https://polona.pl/preview/71788615-5b35-4973-88c0-f6e1550be578",
        rights_evidence_url=(
            "https://polona.pl/api/library-object-query/digital-objects/"
            "71788615-5b35-4973-88c0-f6e1550be578"
        ),
        rights_statement="„Domena Publiczna” — oznaczenie konkretnego obiektu w Polonie",
        accessed_on="2026-09-07",
        extraction_recipe="v3-bounded-ocr-game-import-v2",
        accepted_numbers=tuple(
            number for number in range(1, 86) if number not in {3, 26, 60, 70, 73}
        ),
        rejected_reasons=(
            (3, "educational exhortation without a bounded game procedure"),
            (26, "historical tracking technique and quotation referring to other games, not self-contained rules"),
            (60, "catalogue of physical exercises and general training advice, not one bounded game"),
            (70, "collection of rescue drills and safety instruction, not one bounded game"),
            (73, "meeting and discussion format, not a bounded game"),
        ),
        repeated_headers=("Ćwiczenia i zabawy skautowe.",),
        join_soft_wraps=True,
        smoke_numbers=(1, 12, 27, 46, 59, 85),
        selection_basis=(
            "source-numbered entries with a bounded, executable game or competitive exercise; "
            "advice, drill catalogues and non-game meeting formats are excluded"
        ),
        translation_prompt="translation-pl-en-v5",
    ),
    "jasinski-field-games-1938": ImportPlan(
        prefix="gct",
        sections=(
            (5, "I. Gry poszukiwawcze"),
            (9, "II. Gry obserwacyjne"),
            (12, "III. Gry obserwacyjno-pamięciowe"),
            (29, "IV. Podchody"),
            (51, "V. Tropienia"),
            (58, "VI. Ocenianie odległości"),
            (66, "VII. Pomiary"),
            (89, "VIII. Gry terenoznawcze"),
            (97, "IX. Szukanie skarbów"),
            (115, "X. Łączność"),
            (131, "XI. Dobre uczynki i pierwsza pomoc"),
            (149, "XII. Patrolowanie i zwiady"),
            (166, "XIII. Wywiady"),
            (185, "XIV. Biegi harcerskie"),
            (196, "XV. Gry wojenne"),
        ),
        author="Jan Jasiński",
        title="Gry i ćwiczenia terenowe (Harce terenowe)",
        year=1938,
        edition="wydanie 2 poprawione i rozszerzone",
        publication_place="Poznań",
        publisher="Drukarnia i Księgarnia św. Wojciecha",
        source_url="https://polona.pl/preview/b1600bcb-668f-4daf-a37b-81fade26971f",
        rights_evidence_url=(
            "https://polona.pl/api/library-object-query/digital-objects/"
            "b1600bcb-668f-4daf-a37b-81fade26971f"
        ),
        rights_statement="„Domena Publiczna” — oznaczenie konkretnego obiektu w Polonie",
        accessed_on="2026-09-07",
        extraction_recipe="v3-bounded-ocr-game-import-v3",
        accepted_numbers=tuple(
            number
            for number in range(1, 197)
            if number not in {rejected for rejected, _reason in JASINSKI_REJECTED_REASONS}
        ),
        rejected_reasons=JASINSKI_REJECTED_REASONS,
        repeated_headers=(),
        join_soft_wraps=True,
        smoke_numbers=(1, 32, 89, 123, 149, 196),
        selection_basis=(
            "source-numbered entries with a bounded, executable game or competitive exercise; "
            "lists, reconnaissance prompts, interview topics, cross-reference-only variants and "
            "whole scout-course proposals are retained in the review report but excluded from the "
            "current game-only production scope"
        ),
        translation_prompt="translation-pl-en-v5",
        repeated_header_patterns=(r"^Gry i ćwiczenia terenowe\.\s*\d*$",),
        stop_heading_patterns=(
            r"^#{1,6}\s+(?:[IVXLCDM]+\.\s+|GRY I ĆWICZENIA TERENOWE WYŻSZEGO STOPNIA\b).*$",
        ),
        candidate_stop_headings=((36, "Tropienie według śladów sztucznych."),),
        preserve_inline_heading_body=True,
        use_inventory_title=True,
        inline_only_numbers=(36,),
    ),
    "dabrowski-indoor-games-1934": ImportPlan(
        prefix="gih",
        sections=(
            (10, "Gry ćwiczące zdolność zapamiętywania tego, co się zobaczyło"),
            (18, "Gry ćwiczące spostrzegawczość"),
            (28, "Gry ćwiczące bystrą orientację i szybką reakcję"),
            (37, "Gry ćwiczące domyślność i wnioskowanie"),
            (42, "Gry ćwiczące rozdwojenie uwagi"),
            (64, "Gry ćwiczące zmysł słuchu i pamięć słuchową"),
            (69, "Gry ćwiczące zmysł dotyku"),
            (85, "Gry ćwiczące zręczność i zwinność"),
            (112, "Gry towarzyskie"),
            (146, "Gry służące do ćwiczeń na stopień młodzika"),
            (162, "Gry służące do ćwiczenia się w sygnalizacji"),
            (171, "Gry służące do ćwiczenia się w samarytance"),
            (184, "Gry służące do ćwiczenia się w terenoznawstwie"),
        ),
        author="Juliusz Dąbrowski",
        title="Gry i zabawy w izbie harcerskiej",
        year=1934,
        edition="wydanie 2",
        publication_place="Warszawa",
        publisher="Harcerskie Biuro Wydawnicze",
        source_url="https://polona.pl/preview/f8a00528-6a07-4916-9a76-c1e094e317da",
        rights_evidence_url=(
            "https://polona.pl/api/library-object-query/digital-objects/"
            "f8a00528-6a07-4916-9a76-c1e094e317da"
        ),
        rights_statement="„Domena Publiczna” — oznaczenie konkretnego obiektu w Polonie",
        accessed_on="2026-09-07",
        extraction_recipe="v3-bounded-ocr-game-import-v4",
        accepted_numbers=tuple(
            number
            for number in range(1, 185)
            if number not in {
                rejected for rejected, _reason in DABROWSKI_REJECTED_REASONS
            }
        ),
        rejected_reasons=DABROWSKI_REJECTED_REASONS,
        repeated_headers=(),
        join_soft_wraps=True,
        smoke_numbers=(6, 43, 119, 138, 162, 170),
        selection_basis=(
            "source-indexed entries with a bounded, executable game or competitive exercise; "
            "cross-references, performances, general guidance and catalogues of multiple "
            "unseparated ideas remain in the review report but are excluded from the current "
            "game-only production scope"
        ),
        translation_prompt="translation-pl-en-v5",
        stop_heading_patterns=(
            r"^#{1,6}\s+\**(?:Gry\b.*|Inne gry\b.*|Zastosowanie w terenie\b.*)$",
        ),
        candidate_stop_headings=((156, "Ranny w górach."),),
        preserve_inline_heading_body=True,
        use_inventory_title=True,
        title_overrides=(
            (54, "Gdzieżeś Jakóbku?"),
            (57, "Gra Kima uderzeń (z odmianą)"),
            (58, "Poznaj po głosie"),
            (60, "Gra Kima zegarków"),
            (61, "Szukanie przy dźwiękach"),
            (62, "Depesza więźnia"),
            (63, "Poszedł Marek"),
            (64, "Kto to powiedział?"),
            (65, "Gra Kima dotykowa"),
            (69, "Poznaj po ubraniu (z odmianą)"),
            (70, "Wąż na uwięzi"),
            (71, "Jeleń i wilk"),
            (72, "Przeciąganie w szeregach"),
            (74, "Przedmuchiwanie piórka"),
            (75, "Walka wężów"),
            (76, "Piłka do czapki"),
            (77, "Wyścig tkacki"),
            (78, "Wańka-wstańka"),
            (79, "Walki byków"),
            (84, "Raz-dwa-trzy"),
            (128, "Roztrzepany sekretarz"),
            (162, "Oblężenie Czorsztyna"),
        ),
        heading_is_body_numbers=(6, 66, 67),
    ),
    "pawelek-young-troop-1919": ImportPlan(
        prefix="mdr",
        sections=((115, "Młoda drużyna"),),
        author="Alojzy Pawełek",
        title="Młoda drużyna",
        year=1919,
        edition="wydanie 2",
        publication_place="Warszawa",
        publisher="Skład główny Kom. D. Harc. w Warszawie",
        source_url="https://pbc.biaman.pl/dlibra/publication/29783/edition/28922",
        rights_evidence_url="https://pbc.biaman.pl/dlibra/publication/29783/edition/28922",
        rights_statement="„Domena publiczna” — oznaczenie konkretnego obiektu w Podlaskiej Bibliotece Cyfrowej",
        accessed_on="2026-09-06",
        extraction_recipe="v3-reviewed-paragraph-ocr-game-import-v1",
        accepted_numbers=PAWELEK_ACCEPTED_NUMBERS,
        rejected_reasons=_pawelek_rejected_reasons(),
        repeated_headers=(),
        join_soft_wraps=True,
        smoke_numbers=(1, 29, 43, 63, 75, 103),
        selection_basis=(
            "reviewed paragraph-level descriptions with enough setup, procedure and outcome "
            "to function as a standalone game or competitive exercise; meeting-program labels, "
            "technical drills, catalogues, bare names and rules dependent on another entry remain "
            "in the review report but outside the game-only production corpus"
        ),
        translation_prompt="translation-pl-en-v5",
        preserve_inline_heading_body=True,
        use_inventory_title=True,
        heading_is_body_numbers=(3, 12, 28, 51, 101, 106),
        use_inventory_section=True,
    ),
}


def parse_end_locator(locator: str) -> tuple[int, int] | None:
    if locator.endswith("-eof"):
        return None
    match = re.fullmatch(r"view-(\d{4})-l(\d{4})", locator)
    if not match:
        raise ValueError(f"Unexpected end locator: {locator}")
    return int(match.group(1)), int(match.group(2))


PRINTED_PAGE_MARKER = re.compile(r"^(?:[—-]\s*)?(\d{1,3})(?:\s*[—-])?$")


def printed_pages_for_block(
    pages_by_view: dict[int, Any],
    start: tuple[int, int],
    end: tuple[int, int] | None,
    range_end: int,
) -> list[int]:
    """Map OCR lines to the most recent printed-page marker in a two-page scan."""
    current_page: int | None = None
    result: list[int] = []
    final_view = end[0] if end else range_end
    for view in sorted(pages_by_view):
        if view > final_view:
            break
        for line_number, line in enumerate(pages_by_view[view].markdown.splitlines(), start=1):
            marker = PRINTED_PAGE_MARKER.fullmatch(line.strip())
            if marker:
                current_page = int(marker.group(1))
            locator = (view, line_number)
            if locator < start or (end is not None and locator >= end):
                continue
            if current_page is not None and not marker and current_page not in result:
                result.append(current_page)
    return result


def source_heading_title(raw_block: str) -> str:
    lines = [line.strip() for line in raw_block.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Empty source block")
    heading = re.sub(r"^#{1,6}\s*", "", lines[0]).strip()
    heading = re.sub(r"^(?:\d+|[IVXLCDM]+)[.)]?\s+", "", heading, flags=re.IGNORECASE)
    heading = re.sub(r"[.\s]+$", "", heading)
    if not heading:
        raise ValueError("Source block has an empty heading")
    return heading


def clean_source_block(
    raw_block: str,
    repeated_headers: tuple[str, ...] = (),
    *,
    join_soft_wraps: bool = False,
    repeated_header_patterns: tuple[str, ...] = (),
    preserve_inline_heading_body: bool = False,
    inline_heading_title: str | None = None,
    preserve_heading_as_body: bool = False,
) -> str:
    """Remove only deterministic OCR furniture, never modernize source prose."""
    if join_soft_wraps:
        raw_block = re.sub(r"\n\s*\n\d{1,3}\n\s*\n", "\n", raw_block)
    lines = raw_block.splitlines()
    if not lines:
        raise ValueError("Empty source block")
    heading_line = lines[0]
    inline_body = ""
    if preserve_heading_as_body:
        inline_body = re.sub(r"^#{1,6}\s*", "", heading_line).strip()
    elif inline_heading_title:
        plain_heading = re.sub(r"^#{1,6}\s*", "", heading_line).strip()
        plain_heading = re.sub(
            r"^(?:\d+|[IVXLCDM]+)[.)]?\s+", "", plain_heading, flags=re.IGNORECASE
        )
        match_heading = plain_heading.replace("**", "").replace("__", "")
        title_offset = match_heading.casefold().find(inline_heading_title.casefold())
        if title_offset >= 0:
            suffix = match_heading[title_offset + len(inline_heading_title):]
            if re.match(r"^\.\s+[a-ząćęłńóśźż]", suffix):
                inline_body = match_heading[title_offset:]
            else:
                inline_body = suffix.lstrip(" .:;—-")
    lines = lines[1:]  # candidate title is represented in frontmatter
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r"(?:[—-]\s*)?\d{1,3}\*?(?:\s*[—-])?", stripped):
            continue
        if re.fullmatch(r"!\[[^\]]*\]\([^)]*\)", stripped):
            continue
        if stripped == "*":
            continue
        furniture = stripped.lstrip("-").strip()
        if furniture in repeated_headers:
            continue
        if any(re.fullmatch(pattern, furniture, re.IGNORECASE) for pattern in repeated_header_patterns):
            continue
        if re.fullmatch(r"#{1,6}\s+DZIAŁ\s+[IVXLCDM]+\.?", stripped, re.IGNORECASE):
            continue
        kept.append(line.rstrip())
    body = "\n".join(kept).strip()
    if inline_body:
        body = f"{inline_body}\n\n{body}".strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    if join_soft_wraps:
        body = re.sub(
            r"(?<=[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ])\-\n\n(?=[a-ząćęłńóśźż])",
            "",
            body,
        )
        body = re.sub(r"(?<=[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ])\-\n(?=[a-ząćęłńóśźż])", "", body)
        body = re.sub(r"(?<!\n)\n(?!\n)", " ", body)
    body = re.sub(
        r"(?<=[\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ,;:])\n\n(?=[a-ząćęłńóśźż])",
        " ",
        body,
    )
    if not body and preserve_inline_heading_body:
        body = re.sub(r"^#{1,6}\s*", "", heading_line).strip()
        body = re.sub(r"^(?:\d+|[IVXLCDM]+)[.)]?\s+", "", body, flags=re.IGNORECASE)
    if not body:
        raise ValueError("Source block contains no prose after furniture removal")
    return body


def find_stop_heading(
    pages_by_view: dict[int, Any],
    start: tuple[int, int],
    end: tuple[int, int] | None,
    range_end: int,
    patterns: tuple[str, ...],
    exact_headings: tuple[str, ...],
) -> tuple[tuple[int, int], str] | None:
    """Locate an approved section boundary after a candidate opening."""
    final_view = end[0] if end else range_end
    for view in range(start[0], final_view + 1):
        page = pages_by_view.get(view)
        if page is None:
            continue
        for line_number, line in enumerate(page.markdown.splitlines(), start=1):
            locator = (view, line_number)
            if locator <= start or (end is not None and locator >= end):
                continue
            stripped = line.strip()
            heading = re.sub(r"^#{1,6}\s*", "", stripped).strip()
            if heading in exact_headings or any(
                re.fullmatch(pattern, stripped, re.IGNORECASE) for pattern in patterns
            ):
                return locator, heading
    return None


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
        not in {
            "bounded-by-next-heading",
            "bounded-by-approved-range-end",
            "bounded-by-reviewed-paragraph",
        }
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
        exact_stop_headings = tuple(
            heading
            for candidate_number, heading in plan.candidate_stop_headings
            if candidate_number == number
        )
        stop = find_stop_heading(
            pages_by_view,
            start,
            end,
            range_end,
            plan.stop_heading_patterns,
            exact_stop_headings,
        )
        if stop is not None:
            raw_block, view_end, _ = _block_text(pages_by_view, start, stop[0], range_end)
        if number in plan.inline_only_numbers:
            raw_block = raw_block.splitlines()[0]
            view_end = start[0]
        try:
            source_body = clean_source_block(
                raw_block,
                plan.repeated_headers,
                join_soft_wraps=plan.join_soft_wraps,
                repeated_header_patterns=plan.repeated_header_patterns,
                preserve_inline_heading_body=plan.preserve_inline_heading_body,
                inline_heading_title=str(item["titleRaw"]),
                preserve_heading_as_body=number in plan.heading_is_body_numbers,
            )
        except ValueError as error:
            raise ValueError(f"Candidate {number}: {error}") from error
        content_hash = hashlib.sha256(normalize_space(source_body).encode("utf-8")).hexdigest()
        if content_hash in source_bodies:
            raise ValueError(
                f"Exact source-body duplicate: candidate {number} and {source_bodies[content_hash]}"
            )
        source_bodies[content_hash] = str(number)

        views = set(range(start[0], view_end + 1))
        selected_views.update(views)
        if source_id == "pawelek-young-troop-1919":
            printed_pages = printed_pages_for_block(
                pages_by_view, start, stop[0] if stop is not None else end, range_end
            )
        else:
            printed_pages = []
            for view in sorted(views):
                label = str((checkpoint_items.get(view) or {}).get("printedLabel") or "")
                if label.isdigit() and int(label) not in printed_pages:
                    printed_pages.append(int(label))
        if not printed_pages:
            raise ValueError(f"Candidate {number} lacks printed-page provenance")
        if source_id == "pawelek-young-troop-1919":
            source_item = next(
                (entry for entry in checkpoint.get("items", []) if entry.get("kind") == "pdf"),
                {},
            )
            pdf_url = str(source_item.get("finalUrl") or source_item.get("url") or "")
            if not pdf_url.startswith("https://pbc.biaman.pl/Content/"):
                raise ValueError(f"Candidate {number} lacks a pinned PBC PDF URL")
            facsimile_url = f"{pdf_url}#page={start[0]}"
        else:
            facsimile_url = str((checkpoint_items.get(start[0]) or {}).get("url") or "")
            if not facsimile_url.startswith("https://polona.pl/iiif/3/"):
                raise ValueError(f"Candidate {number} lacks a pinned Polona facsimile URL")

        activity_id = f"{plan.prefix}-{number:03d}"
        title = dict(plan.title_overrides).get(
            number,
            str(item["titleRaw"]) if plan.use_inventory_title else source_heading_title(raw_block),
        )
        provider_name = (
            "Podlaska Biblioteka Cyfrowa"
            if source_id == "pawelek-young-troop-1919"
            else "Polona / Biblioteka Narodowa"
        )
        source_note = (
            "---\n\n"
            f"*Źródło skanu: [{provider_name}]({plan.source_url}), "
            f"oznaczenie „Domena publiczna”. [Zobacz skan — widok {start[0]}]"
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
            "section": (
                str(item["section"])
                if plan.use_inventory_section
                else section_for_number(plan, number)
            ),
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
        activity_report = {
            "id": activity_id,
            "candidateNumber": number,
            "title": title,
            "viewStart": start[0],
            "viewEnd": view_end,
            "printedPages": printed_pages,
            "sourceBlockSha256": raw_hash,
            "publishedSourceHash": metadata["sourceHash"],
        }
        if stop is not None:
            activity_report["truncatedBeforeHeading"] = {
                "locator": f"view-{stop[0][0]:04d}-l{stop[0][1]:04d}",
                "heading": stop[1],
            }
        activities.append(activity_report)

    revision = source_revision(checkpoint, selected_views)
    for output, metadata, body in output_records:
        metadata["sourceRevision"] = f"sha256:{revision}"
        dump_markdown(output, metadata, body)
    expected_names = {f"{plan.prefix}-{number:03d}.md" for number in plan.accepted_numbers}
    for stale in (VAULT / "activities").glob(f"{plan.prefix}-*.md"):
        if stale.name not in expected_names:
            stale.unlink()

    if source_id == "pawelek-young-troop-1919":
        source_item = next(
            (entry for entry in checkpoint.get("items", []) if entry.get("kind") == "pdf"),
            {},
        )
        first_facsimile = (
            f"{source_item.get('finalUrl') or source_item.get('url')}#page={min(selected_views)}"
        )
    else:
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
            "promptVersion": plan.translation_prompt,
            "usageRequired": True,
            "requestBudgetRequired": True,
            "billingMode": "education-credit",
            "enforceReferenceCostLimit": True,
            "maxReferenceCostUsd": 10,
            "report": f"data/reports/{source_id}-translation-pl-en.json",
            "priceAccessedOn": "2026-09-04",
            "smokeTestActivityIds": [
                f"{plan.prefix}-{number:03d}" for number in plan.smoke_numbers
            ],
        },
    }
    source_provider = (
        "Podlaskiej Bibliotece Cyfrowej"
        if source_id == "pawelek-young-troop-1919"
        else "Polonie"
    )
    source_body = (
        f"# {plan.title}\n\n"
        "Źródło bibliograficzne dla gier wyodrębnionych z obiektu bibliotecznego jawnie "
        "oznaczonego jako domena publiczna. Obrazy stron, OCR i pełna książka pozostają "
        "w ignorowanym przez Git katalogu `artifacts/` przy checkoutcie na Group Storage.\n\n"
        f"- [Rekord cyfrowy w {source_provider}]({plan.source_url})\n"
        f"- [Dokładny dowód statusu prawnego]({plan.rights_evidence_url})\n"
    )
    dump_markdown(VAULT / "sources" / f"{source_id}.md", source_metadata, source_body)

    selection = {
        "candidateCount": len(candidates),
        "acceptedGameCount": len(activities),
        "rejectedCount": len(candidates) - len(activities),
        "basis": plan.selection_basis,
    }
    if plan.rejected_reasons:
        selection["rejectedCandidates"] = [
            {"candidateNumber": number, "reason": reason}
            for number, reason in plan.rejected_reasons
        ]
    normalization = [
        "omit the repeated activity heading represented in frontmatter",
        "omit isolated numeric printed-page furniture",
        "omit the following section heading when it falls inside the preceding block",
    ]
    if plan.repeated_headers:
        normalization.extend(
            [
                "omit non-text illustration placeholders while retaining page provenance",
                "omit source-specific repeated running headers",
            ]
        )
    if plan.repeated_header_patterns:
        normalization.append("omit source-specific repeated running headers matched by pinned patterns")
    if plan.stop_heading_patterns or plan.candidate_stop_headings:
        normalization.append(
            "truncate a candidate at the first pinned following chapter or subsection heading"
        )
    if plan.join_soft_wraps:
        normalization.append(
            "join OCR soft line wraps and dehyphenate lowercase word continuations"
        )
    normalization.extend(
        [
            "join a page-break blank line only before a lowercase sentence continuation, including after comma, semicolon or colon",
            "preserve spelling, punctuation and paragraph order without modernization",
        ]
    )
    extraction = {
        "schemaVersion": 1,
        "sourceId": source_id,
        "sourceSha256": revision,
        "parserVersion": plan.extraction_recipe,
        "reviewRequired": False,
        "activityCount": len(activities),
        "wholeSourceCopiedToRepository": False,
        "selection": selection,
        "transcriptionEvidence": {
            "sourceStatement": "Mistral OCR output from pinned page images; raw responses remain in the gitignored artifacts store on Group Storage.",
            "sourceLocation": plan.source_url,
            "deterministicNormalization": normalization,
            "lexicalModernization": False,
        },
        "deduplication": {"exactBodyMatches": [], "nearDuplicateCandidates": []},
        "activities": activities,
    }
    write_json(extraction_path, extraction)

    accepted_numbers = set(plan.accepted_numbers)
    rejected_reasons = dict(plan.rejected_reasons)
    for item in report["candidates"]:
        number = int(item["number"])
        item["recordReviewStatus"] = "accepted-game" if number in accepted_numbers else "rejected-not-game"
        if number in rejected_reasons:
            item["recordReviewReason"] = rejected_reasons[number]
        else:
            item.pop("recordReviewReason", None)
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
