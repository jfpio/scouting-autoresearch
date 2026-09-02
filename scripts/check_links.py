#!/usr/bin/env python3
"""Check internal links and assets in the generated GitHub Pages tree."""

from __future__ import annotations

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
        self.html_lang: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self.html_lang = attributes.get("lang")
        if tag == "article" and "data-card" in attributes:
            self.card_count += 1
            if (attributes.get("data-search") or "").strip():
                self.searchable_card_count += 1
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
    broken: list[str] = []
    checked = 0
    page_metrics: dict[str, tuple[int, int, str | None]] = {}
    for html_path in DIST.rglob("*.html"):
        parser = Links()
        parser.feed(html_path.read_text(encoding="utf-8"))
        page_metrics[str(html_path.relative_to(DIST))] = (
            parser.card_count,
            parser.searchable_card_count,
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
        "index.html": 202,
        "all/index.html": 202,
        "games/index.html": 117,
        "trials/index.html": 85,
        "en/index.html": 202,
        "en/all/index.html": 202,
        "en/games/index.html": 117,
        "en/trials/index.html": 85,
    }
    metric_errors = []
    for path, expected in expected_cards.items():
        actual, searchable, language = page_metrics.get(path, (-1, -1, None))
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
    for path in ("en/index.html", "en/all/index.html", "en/games/index.html", "en/trials/index.html"):
        text = (DIST / path).read_text(encoding="utf-8")
        if "Automatic translations:" not in text or "have not been verified by a person" not in text:
            metric_errors.append(f"{path}: missing the automatic-translation disclosure")
    english_activity_pages = list((DIST / "en" / "activities").glob("*/index.html"))
    if len(english_activity_pages) != 202:
        metric_errors.append(f"Expected 202 English activity pages, found {len(english_activity_pages)}")
    for path in english_activity_pages:
        text = path.read_text(encoding="utf-8")
        activity_id = path.parent.name
        if "Automatic translation." not in text or "has not been verified by a person" not in text:
            metric_errors.append(f"{path.relative_to(DIST)}: missing translation disclosure")
        if f"/scouting-autoresearch/activities/{activity_id}/" not in text:
            metric_errors.append(f"{path.relative_to(DIST)}: missing source Polish transcription link")
        if "public beta" in text.lower():
            metric_errors.append(f"{path.relative_to(DIST)}: obsolete translation beta wording")
    if metric_errors:
        print("Rendered-site checks failed:")
        for value in metric_errors:
            print(f"- {value}")
        raise SystemExit(1)
    print(f"Internal link check passed: {checked} links and assets across {len(list(DIST.rglob('*.html')))} pages.")
    print("Rendered explorer check passed: 202 total, 117 games and 85 trials in both languages; Pagefind present.")


if __name__ == "__main__":
    main()
