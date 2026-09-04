#!/usr/bin/env python3
"""Check internal links and assets in the generated GitHub Pages tree."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ORIGIN = "https://jfpio.github.io"
BASE = "/scouting-autoresearch/"


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[str] = []
        self.card_count = 0
        self.searchable_card_count = 0
        self.map_point_count = 0
        self.map_list_item_count = 0
        self.map_relation_count = 0
        self.html_lang: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self.html_lang = attributes.get("lang")
        if tag == "article" and "data-card" in attributes:
            self.card_count += 1
            if (attributes.get("data-search") or "").strip():
                self.searchable_card_count += 1
        if tag == "a" and "data-map-point" in attributes:
            self.map_point_count += 1
        if tag == "li" and "data-map-list-item" in attributes:
            self.map_list_item_count += 1
        if tag == "line" and "data-map-relation" in attributes:
            self.map_relation_count += 1
        attr = "href" if tag in {"a", "link"} else "src" if tag in {"img", "script", "source"} else None
        if not attr:
            return
        for key, value in attrs:
            if key == attr and value:
                self.values.append(value)


def target_path(url_path: str) -> Path | None:
    if not url_path.startswith(BASE):
        return None
    relative = unquote(url_path[len(BASE) :]).lstrip("/")
    target = DIST / relative
    if url_path == f"{BASE}404/" and (DIST / "404.html").exists():
        return DIST / "404.html"
    if not target.suffix or url_path.endswith("/"):
        target = target / "index.html"
    return target


def main() -> None:
    if not DIST.is_dir():
        raise SystemExit("dist/ is missing; run npm run build first")
    records_by_locale = {}
    for locale in ("pl", "en"):
        export = ROOT / "data" / "generated" / f"activities.{locale}.json"
        if not export.exists():
            raise SystemExit(f"{export} is missing; run scripts/build_content.py first")
        records_by_locale[locale] = json.loads(export.read_text(encoding="utf-8"))
    totals = {locale: len(records) for locale, records in records_by_locale.items()}
    if totals["pl"] != totals["en"]:
        raise SystemExit(f"Locale exports differ in size: {totals}")
    kind_counts = {
        locale: {
            kind: sum(kind in record.get("kinds", []) for record in records)
            for kind in ("game", "trial")
        }
        for locale, records in records_by_locale.items()
    }
    broken: list[str] = []
    checked = 0
    page_metrics: dict[str, tuple[int, int, int, int, int, str | None]] = {}
    html_paths = list(DIST.rglob("*.html"))
    for html_path in html_paths:
        parser = Links()
        parser.feed(html_path.read_text(encoding="utf-8"))
        page_metrics[str(html_path.relative_to(DIST))] = (
            parser.card_count,
            parser.searchable_card_count,
            parser.map_point_count,
            parser.map_list_item_count,
            parser.map_relation_count,
            parser.html_lang,
        )
        route = "/" + str(html_path.relative_to(DIST)).replace("index.html", "")
        page_url = f"{ORIGIN}{BASE}{route.lstrip('/')}"
        for raw in parser.values:
            if raw.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
                continue
            parsed_raw = urlparse(raw)
            if parsed_raw.scheme in {"http", "https"} and parsed_raw.netloc != "jfpio.github.io":
                continue
            resolved = urlparse(urljoin(page_url, raw))
            target = target_path(resolved.path)
            if target is None:
                continue
            checked += 1
            if not target.exists():
                broken.append(f"{html_path.relative_to(DIST)} -> {raw} ({target.relative_to(DIST)})")
    if broken:
        print("Broken internal links:")
        for value in broken[:100]:
            print(f"- {value}")
        raise SystemExit(1)
    expected_cards = {
        "index.html": totals["pl"],
        "all/index.html": totals["pl"],
        "games/index.html": kind_counts["pl"]["game"],
        "trials/index.html": kind_counts["pl"]["trial"],
        "en/index.html": totals["en"],
        "en/all/index.html": totals["en"],
        "en/games/index.html": kind_counts["en"]["game"],
        "en/trials/index.html": kind_counts["en"]["trial"],
    }
    metric_errors = []
    for path, expected in expected_cards.items():
        actual, searchable, _, _, _, language = page_metrics.get(
            path, (-1, -1, -1, -1, -1, None)
        )
        expected_language = "en" if path.startswith("en/") else "pl"
        if actual != expected:
            metric_errors.append(f"{path}: expected {expected} cards, found {actual}")
        if searchable != expected:
            metric_errors.append(f"{path}: expected {expected} searchable cards, found {searchable}")
        if language != expected_language:
            metric_errors.append(f"{path}: expected lang={expected_language}, found {language}")
    site_css = (ROOT / "src" / "styles" / "site.css").read_text(encoding="utf-8")
    if ".activity-card[hidden] { display: none; }" not in site_css:
        metric_errors.append("Activity cards do not honor the hidden state")
    if not (DIST / "pagefind" / "pagefind.js").exists():
        metric_errors.append("Pagefind index is missing")
    semantic_report_path = ROOT / "data" / "reports" / "semantic-map-v3-analysis.json"
    if semantic_report_path.is_file():
        semantic_report = json.loads(semantic_report_path.read_text(encoding="utf-8"))
        approved_relation_count = len(semantic_report.get("approvedRelationOverlays") or [])
    else:
        approved_relation_count = -1
        metric_errors.append("Semantic-map analysis report is missing")
    review_packet_path = ROOT / "data" / "reports" / "semantic-map-v3-review-packet.json"
    if review_packet_path.is_file():
        review_packet = json.loads(review_packet_path.read_text(encoding="utf-8"))
        review_candidate_ids = [
            str(candidate.get("candidateId"))
            for candidate in review_packet.get("candidates") or []
        ]
    else:
        review_candidate_ids = []
        metric_errors.append("Semantic-map review packet is missing")
    for path, expected_language in (("map/index.html", "pl"), ("en/map/index.html", "en")):
        _, _, points, list_items, relations, language = page_metrics.get(
            path, (-1, -1, -1, -1, -1, None)
        )
        expected_games = kind_counts[expected_language]["game"]
        if points != expected_games:
            metric_errors.append(f"{path}: expected {expected_games} map points, found {points}")
        if list_items != expected_games:
            metric_errors.append(
                f"{path}: expected {expected_games} accessible list items, found {list_items}"
            )
        if relations != approved_relation_count:
            metric_errors.append(
                f"{path}: expected {approved_relation_count} approved relation, found {relations}"
            )
        if language != expected_language:
            metric_errors.append(f"{path}: expected lang={expected_language}, found {language}")
        rendered_path = DIST / path
        if not rendered_path.is_file():
            metric_errors.append(f"{path}: rendered semantic map is missing")
            continue
        text = rendered_path.read_text(encoding="utf-8")
        if any(
            forbidden in text
            for forbidden in ("algorithmic-candidate", "algorithmicCandidates", "nearestNeighbors")
        ):
            metric_errors.append(f"{path}: exposes unreviewed semantic candidates")
        if any(candidate_id in text for candidate_id in review_candidate_ids):
            metric_errors.append(f"{path}: exposes a review-only semantic pair")
        for required in (
            'data-map-query',
            'data-map-source',
            'aria-live="polite"',
            'aria-labelledby="semantic-map-title semantic-map-description"',
        ):
            if required not in text:
                metric_errors.append(f"{path}: missing accessible map control {required}")
    disclosure_checks = {
        "pl": ("Tłumaczenia automatyczne:", "nie zostały zweryfikowane przez człowieka"),
        "en": ("Automatic translations:", "have not been verified by a person"),
    }
    for locale, prefix in (("pl", ""), ("en", "en/")):
        expected_phrases = disclosure_checks[locale]
        for route in ("index.html", "all/index.html", "games/index.html", "trials/index.html"):
            path = prefix + route
            rendered_path = DIST / path
            if not rendered_path.exists():
                metric_errors.append(f"{path}: rendered explorer page is missing")
                continue
            text = rendered_path.read_text(encoding="utf-8")
            if any(phrase not in text for phrase in expected_phrases):
                metric_errors.append(f"{path}: missing the automatic-translation disclosure")
    obsolete_safety_notices = (
        "materiały historyczne wymagają współczesnej oceny ryzyka",
        "historical materials require a modern risk assessment",
    )
    for path in expected_cards:
        rendered_path = DIST / path
        if not rendered_path.exists():
            continue
        text = rendered_path.read_text(encoding="utf-8")
        if any(notice in text for notice in obsolete_safety_notices):
            metric_errors.append(f"{path}: obsolete safety callout is still visible")
    activity_disclosures = {
        "pl": ("Tłumaczenie automatyczne.", "nie został zweryfikowany przez człowieka"),
        "en": ("Automatic translation.", "has not been verified by a person"),
    }
    for locale, records in records_by_locale.items():
        directory = DIST / ("en/activities" if locale == "en" else "activities")
        pages = list(directory.glob("*/index.html"))
        if len(pages) != totals[locale]:
            metric_errors.append(f"Expected {totals[locale]} {locale} activity pages, found {len(pages)}")
        page_ids = {path.parent.name for path in pages}
        record_ids = {record["id"] for record in records}
        if page_ids != record_ids:
            metric_errors.append(f"{locale} activity page IDs differ from the generated export")
        for record in records:
            path = directory / record["id"] / "index.html"
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            phrases = activity_disclosures[locale]
            if record.get("translationStatus") == "machine-translation":
                if any(phrase not in text for phrase in phrases):
                    metric_errors.append(f"{path.relative_to(DIST)}: missing translation disclosure")
                source_path = (
                    f"/scouting-autoresearch/en/activities/{record['id']}/"
                    if record.get("originalLanguage") == "en"
                    else f"/scouting-autoresearch/activities/{record['id']}/"
                )
                if source_path not in text:
                    metric_errors.append(f"{path.relative_to(DIST)}: missing source-text link")
            elif any(phrase in text for phrase in phrases):
                metric_errors.append(f"{path.relative_to(DIST)}: source text is mislabeled as a translation")
            if "public beta" in text.lower():
                metric_errors.append(f"{path.relative_to(DIST)}: obsolete translation beta wording")
    if metric_errors:
        print("Rendered-site checks failed:")
        for value in metric_errors:
            print(f"- {value}")
        raise SystemExit(1)
    print(f"Internal link check passed: {checked} links and assets across {len(html_paths)} pages.")
    print(
        f"Rendered explorer check passed: {totals['pl']} total, "
        f"{kind_counts['pl']['game']} games and {kind_counts['pl']['trial']} trials "
        "in both languages; Pagefind present."
    )
    print(
        f"Rendered semantic-map check passed: {kind_counts['pl']['game']} points, "
        f"{kind_counts['pl']['game']} list items and {approved_relation_count} approved relation "
        "in both languages; no unreviewed candidates exposed."
    )


if __name__ == "__main__":
    main()
