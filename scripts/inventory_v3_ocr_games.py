#!/usr/bin/env python3
"""Build metadata-only candidate inventories from completed V3 OCR runs.

Raw OCR stays in scratch.  Reports retain titles, page/view locators and hashes,
but never copy the source prose.  A candidate is not a publication decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from common import ROOT, read_json, read_yaml, write_json


@dataclass(frozen=True)
class SourcePlan:
    title: str
    author_statement: str
    year: int
    method: str
    body_ranges: tuple[tuple[int, int], ...]
    index_ranges: tuple[tuple[int, int], ...] = ()
    rights_scope: str = "game prose in the library object explicitly marked public domain"
    component_exceptions: tuple[str, ...] = ()


SOURCE_PLANS = {
    "jasinski-field-games-1938": SourcePlan(
        "Gry i ćwiczenia terenowe (Harce terenowe)",
        "Jan Jasiński",
        1938,
        "numbered-game-or-exercise-and-scout-race-openings-v2",
        ((89, 268), (281, 303)),
        ((81, 86), (305, 308)),
        "Game prose in the Polona object explicitly marked public domain; non-game media remain outside the product scope.",
        (
            "The author's preface says the selection is based on his long practical experience; no blanket third-party contribution credit was found in the inspected front matter.",
        ),
    ),
    "mojmir-scout-games-1912": SourcePlan(
        "Ćwiczenia i zabawy skautowe",
        "Herman Mojmir",
        1912,
        "numbered-toc-and-body-heading-locators-v1",
        ((13, 85),),
        ((11, 12), (86, 87)),
        "Game prose in the Polona object explicitly marked public domain; non-game media remain outside the product scope.",
        (
            "The book cites Baden-Powell, Seton and other collections as sources; retain these signals as provenance and similarity evidence.",
        ),
    ),
    "dabrowski-indoor-games-1934": SourcePlan(
        "Gry i zabawy w izbie harcerskiej",
        "Juliusz Dąbrowski",
        1934,
        "toc-page-and-fuzzy-heading-locators-v1",
        ((5, 82),),
        ((83, 90),),
        "Game prose in the Polona object explicitly marked public domain; non-game media remain outside the product scope.",
        (
            "The author's introduction says games came from many scouts and Warsaw troops and credits W. Dehnel with review and additions.",
            "The introduction also names Gilcraft's Games Book, Ewa Grodecka's edited collection and periodicals as sources without mapping them to individual games.",
        ),
    ),
    "pawelek-young-troop-1919": SourcePlan(
        "Młoda drużyna",
        "Alojzy Pawełek",
        1919,
        "explicit-game-label-locators-v1",
        ((19, 101),),
        ((116, 118),),
        "Game prose in the PBC object explicitly marked public domain; non-game media remain outside the product scope.",
        (
            "Meeting programmes are not games by themselves; only explicitly labelled game blocks are inventoried.",
            "The author's preface says coworkers may recognize their ideas and names three earlier books used while writing; retain this as provenance and similarity evidence.",
        ),
    ),
    "zwolakowska-cub-pack-1945": SourcePlan(
        "W gromadzie zuchów",
        "praca zbiorowa pod redakcją Jadwigi Zwolakowskiej",
        1945,
        "game-chapter-heading-locators-v1",
        ((294, 321),),
        ((293, 293), (322, 324)),
        "Game prose in the Polona object explicitly marked public domain; non-game media remain outside the product scope.",
        (
            "Hanna Kopciówna signs the introduction immediately before Dział I; retain the unresolved signature scope as provenance rather than a legal blocker.",
            "The edition is a collective work and expressly contains contributed and reprinted components; retain these signals for attribution and similarity review.",
        ),
    ),
}


@dataclass(frozen=True)
class OCRPage:
    view: int
    source_image: str
    printed_page: str | None
    markdown: str
    response_sha256: str


def in_ranges(value: int, ranges: Iterable[tuple[int, int]]) -> bool:
    return any(start <= value <= end for start, end in ranges)


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def strip_markup(value: str) -> str:
    value = re.sub(r"^#{1,6}\s+", "", value.strip())
    value = value.replace("**", "").replace("__", "")
    return normalize_space(value).strip(" |")


def compact(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in value if character.isalnum())


def title_similarity(title: str, line: str) -> float:
    expected = compact(title)
    actual = compact(re.sub(r"^\d{1,3}\s*[.)]\s*", "", strip_markup(line)))
    if not expected or not actual:
        return 0.0
    if expected in actual or actual in expected:
        return min(len(expected), len(actual)) / max(len(expected), len(actual))
    return SequenceMatcher(None, expected, actual).ratio()


def _view_from_name(name: str) -> int:
    match = re.fullmatch(r"view-(\d{4})\.(?:jpg|png)", name, re.IGNORECASE)
    if not match:
        raise ValueError(f"Unexpected OCR source image name: {name}")
    return int(match.group(1))


def load_ocr_pages(source_id: str) -> tuple[dict[str, Any], list[OCRPage]]:
    checkpoint_path = ROOT / "data" / "checkpoints" / "source-acquisition" / f"{source_id}.json"
    checkpoint = read_json(checkpoint_path)
    run = checkpoint.get("ocrRun") or {}
    if run.get("status") != "complete":
        raise ValueError(f"OCR run is not complete for {source_id}")
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise ValueError("SCRATCH is not set")
    printed = {
        int(item["viewIndex"]): item.get("printedLabel")
        for item in checkpoint.get("items", [])
        if item.get("viewIndex") is not None
    }
    pages = []
    for item in run.get("items", []):
        path = Path(scratch) / item["scratchRelativePath"]
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != item["responseSha256"]:
            raise ValueError(f"Pinned OCR response hash mismatch: {path.name}")
        response = json.loads(payload)
        markdown = "\n".join(page.get("markdown", "") for page in response.get("pages", []))
        view = _view_from_name(item["sourceImage"])
        pages.append(
            OCRPage(
                view=view,
                source_image=item["sourceImage"],
                printed_page=printed.get(view),
                markdown=markdown,
                response_sha256=item["responseSha256"],
            )
        )
    return checkpoint, sorted(pages, key=lambda page: page.view)


def parse_mojmir(pages: list[OCRPage]) -> list[dict[str, Any]]:
    toc = {}
    for page in pages:
        if not in_ranges(page.view, ((11, 12),)):
            continue
        for raw_line in page.markdown.splitlines():
            match = re.match(r"^(\d{1,3})\.\s+(.+?)\.?$", strip_markup(raw_line))
            if match and 1 <= int(match.group(1)) <= 85:
                toc[int(match.group(1))] = {
                    "titleRaw": match.group(2).strip().rstrip("."),
                    "indexView": page.view,
                }
    missing = [number for number in range(1, 86) if number not in toc]
    if missing:
        raise ValueError(f"Mojmir TOC parser did not recover all 85 entries; missing {missing}")
    body = [page for page in pages if in_ranges(page.view, ((13, 85),))]
    result = []
    for number in range(1, 86):
        item = dict(toc[number])
        item["sourceNumber"] = number
        candidates = []
        pattern = re.compile(rf"^#{{1,6}}\s+\**{number}\.\s+", re.IGNORECASE)
        for page in body:
            for line_number, line in enumerate(page.markdown.splitlines(), start=1):
                if pattern.match(line.strip()):
                    candidates.append((page, line_number, line))
        if candidates:
            page, line_number, line = max(
                candidates,
                key=lambda candidate: title_similarity(item["titleRaw"], candidate[2]),
            )
            item.update(_locator(page, line_number, line))
        else:
            ranked = [
                (title_similarity(item["titleRaw"], line), page, line_number, line)
                for page in body
                for line_number, line in enumerate(page.markdown.splitlines(), start=1)
                if re.match(r"^#{1,6}\s+", line)
            ]
            score, page, line_number, line = max(ranked, key=lambda value: value[0])
            if score >= 0.7:
                item.update(_locator(page, line_number, line))
                item["titleLocatorScore"] = round(score, 4)
            else:
                item["locatorStatus"] = "numbered-heading-not-recovered"
        result.append(item)
    return result


TOC_EXCLUSIONS = {
    "od autora", "o grach", "wstęp", "odmiany", "przykłady", "inne gry",
    "zastosowanie w terenie", "str", "str.",
}


def _toc_pairs(line: str) -> list[tuple[str, int]]:
    pairs = []
    if line.strip().startswith("|"):
        cells = [normalize_space(cell) for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r"[-: ]*", cell) for cell in cells):
            return []
        for index in range(0, len(cells) - 1, 2):
            title = cells[index].strip(" .,;:-")
            page = cells[index + 1].strip()
            if title and page.isdigit():
                pairs.append((title, int(page)))
        return pairs
    plain = strip_markup(line)
    match = re.match(r"^(.+?)(?:\s*\.\s*){2,}\s*(\d{1,3})$", plain)
    if not match:
        match = re.match(r"^(.+?\D)\s+(\d{1,3})$", plain)
    if match:
        pairs.append((match.group(1).strip(" .,;:-"), int(match.group(2))))
    return pairs


def parse_dabrowski(pages: list[OCRPage]) -> list[dict[str, Any]]:
    by_title = {}
    for page in pages:
        if not in_ranges(page.view, ((83, 90),)):
            continue
        for line in page.markdown.splitlines():
            for title, printed_page in _toc_pairs(line):
                key = compact(title)
                if (
                    key
                    and key not in {compact(value) for value in TOC_EXCLUSIONS}
                    and not title.casefold().startswith("gry ćwiczące")
                    and not title.casefold().startswith("gry służące")
                ):
                    by_title.setdefault(key, {
                        "titleRaw": title,
                        "printedPageStart": printed_page,
                        "indexView": page.view,
                    })
    body = [page for page in pages if in_ranges(page.view, ((5, 82),))]
    for item in by_title.values():
        expected = [page for page in body if page.printed_page == str(item["printedPageStart"])]
        search_pages = expected or body
        ranked = [
            (title_similarity(item["titleRaw"], line), page, line_number, line)
            for page in search_pages
            for line_number, line in enumerate(page.markdown.splitlines(), start=1)
            if normalize_space(line)
        ]
        if ranked:
            score, page, line_number, line = max(ranked, key=lambda value: value[0])
            item.update(_locator(page, line_number, line))
            item["titleLocatorScore"] = round(score, 4)
            if score < 0.5:
                item["locatorStatus"] = "page-located-heading-needs-review"
    return sorted(by_title.values(), key=lambda item: (item["printedPageStart"], item["titleRaw"]))


def parse_pawelek(pages: list[OCRPage]) -> list[dict[str, Any]]:
    result = []
    for page in pages:
        if not in_ranges(page.view, ((19, 101),)):
            continue
        for line_number, raw_line in enumerate(page.markdown.splitlines(), start=1):
            line = strip_markup(raw_line)
            match = re.match(r"^Gra\s*:\s*(.+?)(?:\.|$)", line, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
            else:
                match = re.match(r"^Gra\s+Kima\.(?:\s|$)", line, re.IGNORECASE)
                title = "Gra Kima" if match else ""
            if title:
                item = {"titleRaw": title}
                item.update(_locator(page, line_number, raw_line))
                result.append(item)
        if 90 <= page.view <= 101:
            for line_number, raw_line in enumerate(page.markdown.splitlines(), start=1):
                if re.match(r"^#{2,6}\s+", raw_line):
                    title = strip_markup(raw_line).rstrip(".")
                    if compact(title) == compact("Piłka nożna"):
                        item = {"titleRaw": title}
                        item.update(_locator(page, line_number, raw_line))
                        result.append(item)
    return _deduplicate(result)


def parse_jasinski(pages: list[OCRPage]) -> list[dict[str, Any]]:
    result = []
    for page in pages:
        if not in_ranges(page.view, ((89, 268), (281, 303))):
            continue
        current_section = None
        for line_number, raw_line in enumerate(page.markdown.splitlines(), start=1):
            if re.match(r"^#{1,6}\s+", raw_line):
                current_section = strip_markup(raw_line)
            line = strip_markup(raw_line)
            scout_race = re.match(r"^Bieg\s+(\d{1,2})(.*)$", line, re.IGNORECASE)
            match = re.match(r"^(\d{1,3})\.\s+(.+)$", line)
            if scout_race and re.match(r"^#{1,6}\s+", raw_line):
                source_number: int | str = f"Bieg {scout_race.group(1)}"
                title = normalize_space(line).rstrip(":.")
            elif match:
                source_number = int(match.group(1))
                title = re.split(r"[.;]", match.group(2), maxsplit=1)[0].strip()
            else:
                continue
            if len(title) < 3:
                continue
            item = {
                "sourceNumber": source_number,
                "titleRaw": title,
                "section": current_section,
                "candidateKind": "game-or-exercise-needs-review",
            }
            item.update(_locator(page, line_number, raw_line))
            result.append(item)
    return result


def parse_zwolakowska(pages: list[OCRPage]) -> list[dict[str, Any]]:
    result = []
    exclusions = {
        compact(value)
        for value in (
            "Gry zuchów", "Dział I", "Dział II", "Dział III", "Dział IV",
            "Spis rzeczy", "Spis znanych gier ruchowych, stosowanych z powodzeniem w gromadkach",
        )
    }
    for page in pages:
        if not in_ranges(page.view, ((294, 321),)):
            continue
        for line_number, raw_line in enumerate(page.markdown.splitlines(), start=1):
            if not re.match(r"^#{1,6}\s+", raw_line):
                continue
            title = strip_markup(raw_line).strip(" .")
            if compact(title) in exclusions or title.casefold().startswith("dział "):
                continue
            item = {"titleRaw": title}
            item.update(_locator(page, line_number, raw_line))
            result.append(item)
    return _deduplicate(result)


def _locator(page: OCRPage, line_number: int, line: str) -> dict[str, Any]:
    normalized_page = normalize_space(page.markdown) + "\n"
    normalized_line = normalize_space(strip_markup(line)) + "\n"
    return {
        "viewStart": page.view,
        "printedPageStart": page.printed_page,
        "pageLocator": f"view-{page.view:04d}",
        "bestLineLocator": f"view-{page.view:04d}-l{line_number:04d}",
        "titleLocatorLineSha256": hashlib.sha256(normalized_line.encode("utf-8")).hexdigest(),
        "locatorStatus": "heading-located",
        "ocrResponseSha256": page.response_sha256,
        "sourcePageSha256": hashlib.sha256(normalized_page.encode("utf-8")).hexdigest(),
    }


def _deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for item in items:
        key = compact(item["titleRaw"])
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


PARSERS = {
    "jasinski-field-games-1938": parse_jasinski,
    "mojmir-scout-games-1912": parse_mojmir,
    "dabrowski-indoor-games-1934": parse_dabrowski,
    "pawelek-young-troop-1919": parse_pawelek,
    "zwolakowska-cub-pack-1945": parse_zwolakowska,
}


COMPONENT_RISK_PATTERNS = {
    "explicit-attribution-language": re.compile(
        r"\b(?:według|wg\.?|zaczerpnięt\w*|nadesłał\w*|podał\w*|opisał\w*|autorstw\w*)\b",
        re.IGNORECASE,
    ),
    "known-external-source-name": re.compile(
        r"\b(?:baden[ -]powell\w*|seton\w*|gilcraft\w*|grodeck\w*|mojmir\w*|cenar\w*|jaroszyń\w*|lutosławsk\w*|sedlaczek\w*|gibess\w*|glass\w*|sopoćk\w*)\b",
        re.IGNORECASE,
    ),
    "verse-song-or-music-language": re.compile(
        r"\b(?:pieś\w*|piosen\w*|melodi\w*|śpiew\w*|zwrotk\w*|refren\w*|wiersz\w*|nuty?)\b",
        re.IGNORECASE,
    ),
    "illustration-reference": re.compile(r"\b(?:rys|ryc|fig)\s*\.", re.IGNORECASE),
}


def _line_from_locator(locator: str) -> int:
    match = re.fullmatch(r"view-\d{4}-l(\d{4})", locator)
    if not match:
        raise ValueError(f"Unexpected OCR line locator: {locator}")
    return int(match.group(1))


def _body_range(view: int, ranges: tuple[tuple[int, int], ...]) -> tuple[int, int] | None:
    return next((bounds for bounds in ranges if bounds[0] <= view <= bounds[1]), None)


def _block_text(
    pages_by_view: dict[int, OCRPage],
    start: tuple[int, int],
    end: tuple[int, int] | None,
    range_end: int,
) -> tuple[str, int, int]:
    fragments = []
    last_included_view = start[0]
    nonempty_line_count = 0
    final_view = end[0] if end else range_end
    for view in range(start[0], final_view + 1):
        page = pages_by_view.get(view)
        if page is None:
            continue
        lines = page.markdown.splitlines()
        first_index = start[1] - 1 if view == start[0] else 0
        final_index = end[1] - 1 if end and view == end[0] else len(lines)
        selected = lines[first_index:final_index]
        if selected:
            last_included_view = view
            nonempty_line_count += sum(bool(normalize_space(line)) for line in selected)
            fragments.extend(selected)
    return "\n".join(fragments), last_included_view, nonempty_line_count


def annotate_candidate_boundaries(
    plan: SourcePlan,
    pages: list[OCRPage],
    candidates: list[dict[str, Any]],
) -> None:
    pages_by_view = {page.view: page for page in pages}
    anchors = []
    anchor_counts: dict[tuple[int, int], int] = {}
    for item in candidates:
        locator = item.get("bestLineLocator")
        if not locator:
            continue
        anchor = (int(item["viewStart"]), _line_from_locator(locator))
        anchors.append((anchor, item))
        anchor_counts[anchor] = anchor_counts.get(anchor, 0) + 1

    reliable = [
        (anchor, item)
        for anchor, item in anchors
        if item.get("locatorStatus") == "heading-located" and anchor_counts[anchor] == 1
    ]
    reliable.sort(key=lambda value: value[0])
    unreliable_anchors = sorted(
        anchor
        for anchor, item in anchors
        if item.get("locatorStatus") != "heading-located" or anchor_counts[anchor] != 1
    )

    for item in candidates:
        locator = item.get("bestLineLocator")
        if not locator:
            item["boundaryStatus"] = "manual-review-required-missing-heading"
            continue
        start = (int(item["viewStart"]), _line_from_locator(locator))
        bounds = _body_range(start[0], plan.body_ranges)
        if item.get("locatorStatus") != "heading-located" or anchor_counts[start] != 1 or bounds is None:
            item["boundaryStatus"] = "manual-review-required-uncertain-heading"
            continue
        next_anchor = next(
            (
                anchor
                for anchor, _other in reliable
                if anchor > start and _body_range(anchor[0], plan.body_ranges) == bounds
            ),
            None,
        )
        intervening_unreliable = sum(
            start < anchor < next_anchor if next_anchor else start < anchor and anchor[0] <= bounds[1]
            for anchor in unreliable_anchors
        )
        raw_block, view_end, nonempty_lines = _block_text(
            pages_by_view,
            start,
            next_anchor,
            bounds[1],
        )
        normalized_block = normalize_space(raw_block) + "\n"
        risk_signals = [
            signal_id
            for signal_id, pattern in COMPONENT_RISK_PATTERNS.items()
            if pattern.search(raw_block)
        ]
        if raw_block.count("„") + raw_block.count('"') >= 2:
            risk_signals.append("quotation-markers")
        item.update({
            "viewEndInclusive": view_end,
            "endExclusiveLocator": (
                f"view-{next_anchor[0]:04d}-l{next_anchor[1]:04d}"
                if next_anchor
                else f"view-{bounds[1]:04d}-eof"
            ),
            "sourceBlockSha256": hashlib.sha256(normalized_block.encode("utf-8")).hexdigest(),
            "blockMarkdownCharacterCount": len(raw_block),
            "blockNonEmptyLineCount": nonempty_lines,
            "componentRiskSignalIds": sorted(set(risk_signals)),
            "boundaryStatus": (
                "review-required-adjacent-uncertain-locator"
                if intervening_unreliable
                else "bounded-by-next-heading" if next_anchor else "bounded-by-approved-range-end"
            ),
        })
        if intervening_unreliable:
            item["interveningUnreliableCandidateCount"] = intervening_unreliable


def build_report(source_id: str) -> dict[str, Any]:
    plan = SOURCE_PLANS[source_id]
    manifest = read_yaml(ROOT / "config" / "v3-source-expansion.yaml") or {}
    manifest_unit = next(
        item for item in manifest.get("sourceUnits", []) if item.get("id") == source_id
    )
    rights_evidence = manifest_unit.get("rightsEvidence") or {}
    if not rights_evidence:
        raise ValueError(f"Missing institutional rights evidence for {source_id}")
    checkpoint, pages = load_ocr_pages(source_id)
    candidates = PARSERS[source_id](pages)
    if not candidates:
        raise ValueError(f"No candidate locators recovered for {source_id}")
    annotate_candidate_boundaries(plan, pages, candidates)
    for number, item in enumerate(candidates, start=1):
        item["number"] = number
        item["recordReviewStatus"] = "pending-agent-review"
    run = checkpoint["ocrRun"]
    item_recipe_versions = {
        item.get("recipeVersion")
        for item in run.get("items", [])
        if item.get("recipeVersion")
    }
    recipe_version = run.get("recipeVersion")
    if recipe_version is None and len(item_recipe_versions) == 1:
        recipe_version = item_recipe_versions.pop()
    return {
        "schemaVersion": 1,
        "sourceId": source_id,
        "sourceTitle": plan.title,
        "authorStatement": plan.author_statement,
        "year": plan.year,
        "status": "candidate-inventory-complete-record-review-pending",
        "sourceText": {
            "classification": "mistral-ocr-scratch-only",
            "storage": "scratch-only",
            "model": run.get("model"),
            "recipeVersion": recipe_version,
            "approvedViewCount": run.get("completedApprovedViewCount"),
        },
        "method": {
            "version": plan.method,
            "bodyViewRanges": [list(value) for value in plan.body_ranges],
            "indexViewRanges": [list(value) for value in plan.index_ranges],
            "normalization": [
                "collapse whitespace and remove Markdown emphasis only for matching",
                "retain raw OCR-derived title, view/page locator and hashes; do not retain the matched OCR line",
                "hash candidate blocks from their start heading to the next reliable heading without emitting block text",
                "do not emit or modernize full source prose",
            ],
            "locatorCaveat": "Candidate boundaries, kinds and provenance notes remain a record-review task; the library's explicit public-domain status establishes publication eligibility for this digital object.",
        },
        "selection": {
            "productionKind": "game",
            "candidateCount": len(candidates),
            "importedActivityCount": 0,
            "rightsScope": plan.rights_scope,
            "rightsStatus": "public-domain",
            "rightsEvidencePolicy": "explicit-library-public-domain-status-is-ground-truth",
            "rightsEvidence": rights_evidence,
            "humanReviewRequiredBeforeFullTextPublication": False,
            "knownComponentExceptions": list(plan.component_exceptions),
        },
        "ocrUsage": run.get("usage"),
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
        "reportPath": str(report_path.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
