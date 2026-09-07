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

from common import ROOT, read_json, write_json


@dataclass(frozen=True)
class SourcePlan:
    title: str
    author_statement: str
    year: int
    method: str
    body_ranges: tuple[tuple[int, int], ...]
    index_ranges: tuple[tuple[int, int], ...] = ()
    rights_scope: str = "named public-domain prose only"
    component_exceptions: tuple[str, ...] = ()


SOURCE_PLANS = {
    "jasinski-field-games-1938": SourcePlan(
        "Gry i ćwiczenia terenowe (Harce terenowe)",
        "Jan Jasiński",
        1938,
        "numbered-game-or-exercise-openings-v1",
        ((89, 268), (281, 303)),
        ((81, 86), (305, 308)),
        "Jasiński's own prose only; cover artwork, illustrations and separately credited material are excluded.",
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
        "Mojmir's own prose only; quotations, illustrations and separately credited material are excluded.",
        (
            "The book cites Baden-Powell, Seton and other collections as sources; each prose block remains pending component review.",
        ),
    ),
    "dabrowski-indoor-games-1934": SourcePlan(
        "Gry i zabawy w izbie harcerskiej",
        "Juliusz Dąbrowski",
        1934,
        "toc-page-and-fuzzy-heading-locators-v1",
        ((5, 82),),
        ((83, 90),),
        "Dąbrowski's own prose only; cover artwork, graphics, quotations and separately credited material are excluded.",
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
        "Pawełek's own prose only; Lutosławski's foreword and other separately authored contributions are excluded.",
        (
            "Meeting programmes are not games by themselves; only explicitly labelled game blocks are inventoried.",
            "The author's preface says coworkers may recognize their ideas and names three earlier books used while writing; each candidate therefore needs component-level attribution before full-text publication.",
        ),
    ),
    "zwolakowska-cub-pack-1945": SourcePlan(
        "W gromadzie zuchów",
        "praca zbiorowa pod redakcją Jadwigi Zwolakowskiej",
        1945,
        "game-chapter-heading-locators-v1",
        ((294, 321),),
        ((293, 293), (322, 324)),
        "candidate mapping only until the author and rights of each game-chapter component are established",
        (
            "Hanna Kopciówna (Hanna Brzozowska-Kopciówna, 1907–1944) signs the introduction immediately before Dział I; her own prose is public domain in Poland and the EU, but the signature's scope over all 74 descriptions remains unresolved.",
            "The edition is a collective work and expressly contains contributed and reprinted components.",
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
            match = re.match(r"^(\d{1,3})\.\s+(.+)$", line)
            if not match:
                continue
            title = re.split(r"[.;]", match.group(2), maxsplit=1)[0].strip()
            if len(title) < 3:
                continue
            item = {
                "sourceNumber": int(match.group(1)),
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


def build_report(source_id: str) -> dict[str, Any]:
    plan = SOURCE_PLANS[source_id]
    checkpoint, pages = load_ocr_pages(source_id)
    candidates = PARSERS[source_id](pages)
    if not candidates:
        raise ValueError(f"No candidate locators recovered for {source_id}")
    for number, item in enumerate(candidates, start=1):
        item["number"] = number
        item["componentReviewStatus"] = "pending-human-review"
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
        "status": "candidate-inventory-complete-component-review-pending",
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
                "do not emit or modernize full source prose",
            ],
            "locatorCaveat": "Candidate boundaries and kinds remain a review task; a locator does not establish authorship or publication eligibility.",
        },
        "selection": {
            "productionKind": "game",
            "candidateCount": len(candidates),
            "importedActivityCount": 0,
            "rightsScope": plan.rights_scope,
            "humanReviewRequiredBeforeFullTextPublication": True,
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
