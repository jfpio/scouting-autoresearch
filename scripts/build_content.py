#!/usr/bin/env python3
"""Generate the website and public exports from the Obsidian vault."""

from __future__ import annotations

import html
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

from common import GENERATED, PUBLIC_DATA, ROOT, VAULT, load_markdown, read_json, write_json
from similar_activities import add_similarity_links


DOCS = ROOT / "src" / "content" / "docs"
SITE_ROOT = "https://jfpio.github.io/scouting-autoresearch"
TRAIT_ALIASES = ROOT / "config" / "trait-filter-aliases-v1.json"


def normalize_trait_term(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def display_trait(value: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", value).split())
    return normalized[:1].upper() + normalized[1:]


def apply_filter_traits(records: list[dict]) -> None:
    """Add a search-only facet layer while preserving source and translated traits."""
    config = read_json(TRAIT_ALIASES)
    facets = {facet["id"]: facet for facet in config["facets"]}
    aliases: dict[tuple[str, str], str] = {}
    for facet in facets.values():
        for source_locale, terms in facet.get("terms", {}).items():
            for term in terms:
                key = (source_locale, normalize_trait_term(term))
                if key in aliases:
                    raise RuntimeError(f"Duplicate trait alias: {source_locale}/{term}")
                aliases[key] = facet["id"]
    compounds = {
        (source_locale, normalize_trait_term(term)): facet_ids
        for source_locale, mapping in config.get("compoundTerms", {}).items()
        for term, facet_ids in mapping.items()
    }

    def facet_ids(source_locale: str, source_term: str) -> list[str]:
        key = (source_locale, normalize_trait_term(source_term))
        if key in compounds:
            return compounds[key]
        if key in aliases:
            return [aliases[key]]
        return [f"source:{source_locale}:{key[1]}"]

    candidates: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for record in records:
        source_terms = record["_sourceTraits"]
        localized_terms = record["traits"]
        if len(source_terms) != len(localized_terms):
            raise RuntimeError(f"Trait count differs for {record['id']}/{record['locale']}")
        for source_term, localized_term in zip(source_terms, localized_terms, strict=True):
            for facet_id in facet_ids(record["_sourceTraitLocale"], source_term):
                if facet_id.startswith("source:"):
                    candidates[(facet_id, record["locale"])][localized_term] += 1

    labels: dict[tuple[str, str], str] = {}
    for facet_id, facet in facets.items():
        for locale in ("pl", "en"):
            labels[(facet_id, locale)] = facet["labels"][locale]
    for key, values in candidates.items():
        preferred = sorted(values.items(), key=lambda item: (-item[1], normalize_trait_term(item[0]), item[0]))[0][0]
        labels[key] = display_trait(preferred)

    for record in records:
        filter_traits: list[str] = []
        for source_term in record["_sourceTraits"]:
            for facet_id in facet_ids(record["_sourceTraitLocale"], source_term):
                label = labels[(facet_id, record["locale"])]
                if label not in filter_traits:
                    filter_traits.append(label)
        record["filterTraits"] = filter_traits
        record.pop("_sourceTraits")
        record.pop("_sourceTraitLocale")


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def plain_text(markdown: str) -> str:
    value = re.sub(r"!\[[^]]*\]\([^)]+\)", " ", markdown)
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[#*_>`~|]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return html.unescape(value)


def summary(markdown: str, limit: int = 260) -> str:
    value = plain_text(markdown)
    if len(value) <= limit:
        return value
    shortened = value[:limit].rsplit(" ", 1)[0]
    return f"{shortened}…"


def pages_label(values: list[int]) -> str:
    if not values:
        return "—"
    if len(values) == 1:
        return str(values[0])
    contiguous = values == list(range(values[0], values[-1] + 1))
    return f"{values[0]}–{values[-1]}" if contiguous else ", ".join(map(str, values))


def load_sources() -> dict[str, dict[str, Any]]:
    sources = {}
    for path in sorted((VAULT / "sources").glob("*.md")):
        metadata, _ = load_markdown(path)
        sources[metadata["id"]] = metadata
    return sources


def translated_record(metadata: dict, body: str, common: dict, locale: str) -> dict:
    record = {
        **common,
        "locale": locale,
        "title": metadata["title"],
        "body": body,
        "traits": metadata.get("traits", []),
        "section": metadata.get("section", ""),
        "translationStatus": metadata.get("status", "source-text"),
        "summary": summary(body),
    }
    if record["translationStatus"] == "machine-translation":
        record.update(
            {
                "translationModel": metadata["model"],
                "translationPromptVersion": metadata["promptVersion"],
                "translationGeneratedAt": metadata["generatedAt"],
            }
        )
    record["searchText"] = " ".join(
        [record["title"], plain_text(body), *record["traits"], record["section"], common["author"], common["sourceTitle"]]
    ).lower()
    return record


def load_records(*, include_similarities: bool = True) -> tuple[list[dict], list[dict], dict[str, dict]]:
    sources = load_sources()
    polish: list[dict] = []
    english: list[dict] = []
    for path in sorted((VAULT / "activities").glob("*.md")):
        metadata, body = load_markdown(path)
        source = sources[metadata["sourceId"]]
        original_locale = metadata["originalLanguage"]
        if original_locale not in {"pl", "en", "fr"}:
            raise RuntimeError(f"Unsupported source language in {path.name}: {original_locale}")
        target_locales = {
            "pl": ("en",),
            "en": ("pl",),
            "fr": ("pl", "en"),
        }[original_locale]
        common = {
            "id": metadata["id"],
            "kinds": metadata["kinds"],
            "sourceId": metadata["sourceId"],
            "author": source["author"],
            "sourceTitle": source["title"],
            "year": source["year"],
            "publisher": source.get("publisher"),
            "printedPages": metadata["printedPages"],
            "pdfPages": metadata.get("pdfPages", []),
            "sourceUrl": metadata["sourceUrl"],
            "digitalEditionUrl": metadata["digitalEditionUrl"],
            "pdfUrl": source.get("pdfUrl"),
            "facsimileUrl": metadata.get("facsimileUrl"),
            "sourceCommit": metadata.get("sourceCommit"),
            "sourceRevision": metadata.get("sourceRevision", metadata.get("sourceCommit")),
            "sourceHash": metadata["sourceHash"],
            "rightsStatus": metadata["rightsStatus"],
            "transcriptionStatus": metadata["transcriptionStatus"],
            "safetyStatus": metadata["safetyStatus"],
            "originalLanguage": metadata["originalLanguage"],
            "_sourceTraits": metadata.get("traits", []),
            "_sourceTraitLocale": original_locale,
        }
        if original_locale in {"pl", "en"}:
            original = translated_record(
                {**metadata, "status": "source-text"}, body, common, original_locale
            )
            (polish if original_locale == "pl" else english).append(original)
        for target_locale in target_locales:
            translation_path = VAULT / "translations" / target_locale / path.name
            if not translation_path.exists():
                raise RuntimeError(f"Missing {target_locale} translation: {translation_path.name}")
            translation, translated_body = load_markdown(translation_path)
            if translation.get("activityId") != metadata["id"]:
                raise RuntimeError(f"Translation activity ID mismatch: {translation_path.name}")
            if translation.get("sourceHash") != metadata["sourceHash"]:
                raise RuntimeError(f"Stale translation: {translation_path.name}")
            if translation.get("locale") != target_locale:
                raise RuntimeError(f"Wrong translation locale: {translation_path.name}")
            if translation.get("status") != "machine-translation":
                raise RuntimeError(f"Wrong translation status: {translation_path.name}")
            translated = translated_record(
                translation, translated_body, common, target_locale
            )
            if original_locale == "fr":
                translated.update(
                    {
                        "sourceActivityTitle": metadata["title"],
                        "sourceText": body,
                        "sourceTextUrl": (
                            f"{SITE_ROOT}/{'en/' if target_locale == 'en' else ''}"
                            f"activities/{metadata['id']}/#source-text"
                        ),
                    }
                )
            (polish if target_locale == "pl" else english).append(translated)
    polish = sorted(polish, key=lambda item: item["id"])
    english = sorted(english, key=lambda item: item["id"])
    apply_filter_traits([*polish, *english])
    if include_similarities:
        add_similarity_links(polish, "pl")
        add_similarity_links(english, "en")
    return polish, english, sources


def frontmatter(record: dict, *, locale: str) -> str:
    description = record["summary"][:155]
    return "\n".join(
        [
            "---",
            f"title: {yaml_scalar(record['title'])}",
            f"description: {yaml_scalar(description)}",
            f"slug: {yaml_scalar(('en/' if locale == 'en' else '') + 'activities/' + record['id'])}",
            f"activityId: {record['id']}",
            "kinds:",
            *[f"  - {kind}" for kind in record["kinds"]],
            f"sourceId: {record['sourceId']}",
            "traits:",
            *([f"  - {yaml_scalar(trait)}" for trait in record["traits"]] or ["  []"]),
            "printedPages:",
            *[f"  - {page}" for page in record["printedPages"]],
            "pdfPages:",
            *([f"  - {page}" for page in record["pdfPages"]] or ["  []"]),
            f"transcriptionStatus: {record['transcriptionStatus']}",
            f"translationStatus: {record['translationStatus']}",
            f"safetyStatus: {record['safetyStatus']}",
            "sidebar:",
            "  hidden: true",
            "---",
        ]
    )


def activity_page(record: dict, *, locale: str) -> str:
    is_pl = locale == "pl"
    kind_labels = {
        "game": "gra",
        "trial": "próba",
        "scout-course": "bieg harcerski",
    }
    english_kind_labels = {
        "game": "game",
        "trial": "trial",
        "scout-course": "scout course",
    }
    kinds = ", ".join(
        kind_labels.get(value, value) if is_pl else english_kind_labels.get(value, value)
        for value in record["kinds"]
    )
    traits = ", ".join(record["traits"]) or ("Nie podano w źródle" if is_pl else "Not stated in the source")
    machine = ""
    if record["translationStatus"] == "machine-translation":
        source_locale_names = {
            "pl": ("polsku", "Polish"),
            "en": ("angielsku", "English"),
            "fr": ("francusku", "French"),
        }
        source_locale_pl, source_locale_en = source_locale_names[
            record["originalLanguage"]
        ]
        if record["originalLanguage"] == "fr":
            source_path = "#source-text"
        else:
            source_path = (
                f"{SITE_ROOT}/en/activities/{record['id']}/"
                if record["originalLanguage"] == "en"
                else f"{SITE_ROOT}/activities/{record['id']}/"
            )
        machine = (
            f'<div class="machine-notice"><strong>{"Tłumaczenie automatyczne." if is_pl else "Automatic translation."}</strong> '
            + (
                'Ten tekst nie został zweryfikowany przez człowieka. '
                if is_pl
                else 'This text has not been verified by a person. '
            )
            + f'<div class="notice-links"><a href="{source_path}">{f"Tekst źródłowy po {source_locale_pl}" if is_pl else f"Source text in {source_locale_en}"}</a> · '
            + f'<a href="{html.escape(record["digitalEditionUrl"])}">{"Wydanie cyfrowe" if is_pl else "Digital edition"}</a></div>'
            + f'<details><summary>{"Szczegóły tłumaczenia" if is_pl else "Translation details"}</summary>'
            + f'Model: <code>{html.escape(record["translationModel"])}</code>.</details></div>\n\n'
        )
    pl_link = f"{SITE_ROOT}/activities/{record['id']}/"
    en_link = f"{SITE_ROOT}/en/activities/{record['id']}/"
    labels = {
        "meta": "Metadane" if is_pl else "Metadata",
        "type": "Rodzaj" if is_pl else "Type",
        "traits": "Cechy" if is_pl else "Traits",
        "source": "Źródło" if is_pl else "Source",
        "pages": "Strony drukowane" if is_pl else "Printed pages",
        "edition": "Wydanie cyfrowe" if is_pl else "Digital edition",
        "facsimile": "Otwórz wydanie na właściwej stronie" if is_pl else "Open the edition at the relevant page",
        "other": (
            "Przeczytaj tekst źródłowy" if record["translationStatus"] == "machine-translation" else "Zobacz tłumaczenie automatyczne"
        ) if is_pl else (
            "Read the source text" if record["translationStatus"] == "machine-translation" else "Read the automatic translation"
        ),
    }
    other_link = en_link if is_pl else pl_link
    pages = pages_label(record["printedPages"])
    if record["pdfPages"]:
        pages += f" / PDF {pages_label(record['pdfPages'])}"
    facsimile_url = record.get("facsimileUrl")
    if not facsimile_url and record.get("pdfUrl") and record["pdfPages"]:
        facsimile_url = f"{record['pdfUrl']}#page={record['pdfPages'][0]}"
    similar = ""
    if record.get("similarActivities"):
        similar_heading = "Bardzo podobne gry" if is_pl else "Highly similar games"
        similar_intro = (
            "Ta aktywność ma zatwierdzone powiązanie z innym historycznym wariantem. "
            "Rekordy pozostają osobne, aby zachować tekst i pochodzenie każdego źródła."
            if is_pl
            else "This activity has an approved link to another historical variant. "
            "The records remain separate to preserve each source text and provenance."
        )
        similar_items = "".join(
            "<li>"
            f'<a href="{html.escape(item["url"])}">{html.escape(item["title"])}</a>'
            f'<details><summary>{"Źródło i powiązanie" if is_pl else "Source and relationship"}</summary>'
            f'{html.escape(item["author"])}, <cite>{html.escape(item["sourceTitle"])}</cite> '
            f'({item["year"]}). {html.escape(item["note"])} {similar_intro}</details></li>'
            for item in record["similarActivities"]
        )
        similar = (
            f'<div class="similar-notice"><strong>{similar_heading}.</strong> '
            f"<ul>{similar_items}</ul></div>\n\n"
        )
    source_appendix = ""
    if (
        record["translationStatus"] == "machine-translation"
        and record["originalLanguage"] == "fr"
    ):
        heading = "Francuski tekst źródłowy" if is_pl else "French source text"
        source_appendix = (
            '\n\n<span id="source-text"></span>\n\n'
            f"## {heading}\n\n"
            f"**{record['sourceActivityTitle']}**\n\n"
            f"{record['sourceText'].strip()}"
        )
    return (
        frontmatter(record, locale=locale)
        + "\n\n"
        + machine
        + similar
        + "## "
        + (("Treść źródłowa" if is_pl else "Source text") if record["translationStatus"] == "source-text" else ("Tekst przetłumaczony" if is_pl else "Translated text"))
        + "\n\n"
        + record["body"].strip()
        + "\n\n"
        + f"## {labels['meta']}\n\n"
        + f"- **{labels['type']}:** {kinds}\n"
        + f"- **{labels['traits']}:** {traits}\n"
        + f"- **{labels['source']}:** {record['author']}, *{record['sourceTitle']}* ({record['year']})\n"
        + f"- **{labels['pages']}:** {pages}\n"
        + f"- **{labels['edition']}:** "
        + (
            f"[Wydanie cyfrowe]({record['digitalEditionUrl']}) · [Rekord źródłowy]({record['sourceUrl']})\n"
            if is_pl
            else f"[Digital edition]({record['digitalEditionUrl']}) · [Source record]({record['sourceUrl']})\n"
        )
        + (
            f"- **{labels['facsimile']}:** [{'s.' if is_pl else 'p.'} {record['printedPages'][0]}]({facsimile_url})\n"
            if facsimile_url
            else ""
        )
        + f"- **{labels['other']}:** [{record['id']}]({other_link})"
        + source_appendix
        + "\n"
    )


def explorer_page(locale: str, *, activity_count: int, source_count: int, kind: str | None = None, home: bool = False) -> str:
    is_pl = locale == "pl"
    titles = {
        None: ("Wszystkie aktywności", "All activities"),
        "game": ("Gry", "Games"),
        "trial": ("Próby", "Trials"),
        "scout-course": ("Biegi harcerskie", "Scout courses"),
    }
    title = ("Znajdź aktywność" if is_pl else "Find an activity") if home else titles[kind][0 if is_pl else 1]
    description = (
        "Przeszukuj historyczne gry, próby i biegi według treści, cech, autora, książki oraz roku."
        if is_pl
        else "Search historical games, trials, and scout courses by text, traits, author, book, and year."
    )
    component_path = "../../components/ActivityExplorer.astro" if locale == "pl" else "../../../components/ActivityExplorer.astro"
    hero = ""
    if home:
        eyebrow = "OTWARTA BAZA WIEDZY · V0" if is_pl else "OPEN KNOWLEDGE BASE · V0"
        text = (
            f"{activity_count} aktywności z {source_count} książek w domenie publicznej. Teksty źródłowe po polsku, angielsku lub francusku mają automatyczne warstwy polskie i angielskie."
            if is_pl
            else f"{activity_count} activities from {source_count} public-domain books. Polish, English, or French source texts have Polish and English machine-translation layers."
        )
        hero = f'<p class="eyebrow">{eyebrow}</p>\n\n{text}\n\n'
    else:
        hero = f"{description}\n\n"
    kind_prop = f' kind="{kind}"' if kind else ""
    translation_note = (
        "> **Tłumaczenia automatyczne:** wersje w języku innym niż źródłowy nie zostały zweryfikowane przez człowieka. Każdy rekord prowadzi do tekstu źródłowego i wydania cyfrowego.\n\n"
        if is_pl
        else "> **Automatic translations:** versions in a language other than the source have not been verified by a person. Every record links to the source text and digital edition.\n\n"
    )
    return (
        "---\n"
        f"title: {yaml_scalar(title)}\n"
        f"description: {yaml_scalar(description)}\n"
        "template: splash\n"
        "---\n\n"
        f"import ActivityExplorer from '{component_path}';\n\n"
        + hero
        + translation_note
        + f'<ActivityExplorer locale="{locale}"{kind_prop} />\n'
    )


def explorer_filter_url(locale: str, facet: str, value: str) -> str:
    prefix = "/scouting-autoresearch/en/all/" if locale == "en" else "/scouting-autoresearch/all/"
    return f"{prefix}?{facet}={quote(str(value), safe='')}"


def sources_page(locale: str, sources: dict[str, dict], records: list[dict]) -> str:
    is_pl = locale == "pl"
    title = "Książki" if is_pl else "Books"
    intro = (
        "Pełne teksty są publikowane wyłącznie dla wydań z potwierdzonym statusem domeny publicznej. Oznaczenie praw przypisujemy instytucji źródłowej."
        if is_pl
        else "Full text is published only for editions with confirmed public-domain status. Rights statements are attributed to the source institution."
    )
    lines = ["---", f"title: {yaml_scalar(title)}", f"description: {yaml_scalar(intro)}", "---", "", intro, ""]
    activity_counts = Counter(record["sourceId"] for record in records)
    for source in sources.values():
        count = activity_counts[source["id"]]
        lines += [
            f"## {source['title']}",
            "",
            f"**{source['author']} · {source['year']} · {source['publicationPlace']} · {source['publisher']}**",
            "",
            f"{source['rightsStatement']}",
            "",
            f"[{'Pokaż aktywności' if is_pl else 'Show activities'} ({count})]({explorer_filter_url(locale, 'book', source['title'])}) · "
            f"[{'Rekord źródłowy' if is_pl else 'Source record'}]({source['sourceUrl']}) · "
            f"[{'Wydanie cyfrowe' if is_pl else 'Digital edition'}]({source['digitalEditionUrl']})",
            "",
        ]
    return "\n".join(lines)


def authors_page(locale: str, sources: dict[str, dict], records: list[dict]) -> str:
    is_pl = locale == "pl"
    title = "Autorzy" if is_pl else "Authors"
    intro = (
        "Autorstwo zachowujemy dokładnie tak, jak opisano je dla danego źródła; nie rozdzielamy automatycznie współautorów ani prac zbiorowych."
        if is_pl
        else "Authorship is preserved exactly as recorded for each source; co-authors and collective works are not split automatically."
    )
    records_by_source = Counter(record["sourceId"] for record in records)
    sources_by_author: dict[str, list[dict]] = defaultdict(list)
    for source in sources.values():
        sources_by_author[source["author"]].append(source)
    lines = ["---", f"title: {yaml_scalar(title)}", f"description: {yaml_scalar(intro)}", "---", "", intro, ""]
    for author in sorted(sources_by_author, key=lambda value: value.casefold()):
        author_sources = sorted(sources_by_author[author], key=lambda source: (source["year"], source["title"]))
        count = sum(records_by_source[source["id"]] for source in author_sources)
        lines += [
            f"## {author}",
            "",
            f"[{'Pokaż aktywności' if is_pl else 'Show activities'} ({count})]({explorer_filter_url(locale, 'author', author)})",
            "",
            *[f"- *{source['title']}* ({source['year']}) — {records_by_source[source['id']]}" for source in author_sources],
            "",
        ]
    return "\n".join(lines)


def semantic_map_page(locale: str) -> str:
    is_pl = locale == "pl"
    title = "Mapa semantyczna gier" if is_pl else "Semantic map of games"
    description = (
        "Odkrywaj 914 historycznych gier. Przeszukuj listę lub mapę i pobieraj teksty według regionów."
        if is_pl
        else "Explore 914 historical games. Search the list or map and download game texts by region."
    )
    component_path = (
        "../../components/SemanticMap.astro"
        if is_pl
        else "../../../components/SemanticMap.astro"
    )
    return (
        "---\n"
        f"title: {yaml_scalar(title)}\n"
        f"description: {yaml_scalar(description)}\n"
        "template: splash\n"
        "---\n\n"
        f"import SemanticMap from '{component_path}';\n\n"
        f'<SemanticMap locale="{locale}" />\n'
    )


def about_page(locale: str) -> str:
    is_pl = locale == "pl"
    title = "O projekcie" if is_pl else "About"
    body = (
        """Scouting Autoresearch porządkuje historyczne gry, próby i ćwiczenia harcerskie w jednej, przeszukiwalnej bazie. Korpus zachowuje teksty źródłowe i nie kopiuje PDF-ów.

Wersje w języku innym niż źródłowy są tłumaczeniami automatycznymi i nie są weryfikowane przez człowieka. Każdy rekord prowadzi do tekstu źródłowego i wydania cyfrowego oraz zachowuje autora, oryginalny tytuł książki, rok i strony. Brakujące dane pozostają nieznane — nie dopowiadamy wieku, czasu, sprzętu ani ryzyka.

Kod projektu jest udostępniony na licencji MIT. Projektowe metadane i tłumaczenia są domyślnie udostępniane na CC BY 4.0 wyłącznie w zakresie posiadanych praw; importowane teksty zachowują indywidualne oznaczenia praw i warunki źródła. Materiał odtworzony z reprodukcji Gallici oraz oparte na nim tłumaczenia są wyjątkiem niekomercyjnym opisanym w [licencjach danych](https://github.com/jfpio/scouting-autoresearch/blob/main/DATA-LICENSE.md).

## Następny etap

V2 prowadzi kontrolowany proces pozyskiwania dzieł Roberta Baden-Powella, Ernesta Thompsona Setona i Jacques’a Sevina z potwierdzonym statusem prawnym. Szczegóły zawiera [plan projektu](https://github.com/jfpio/scouting-autoresearch/blob/main/project-plan.md)."""
        if is_pl
        else """Scouting Autoresearch organizes historical scouting games, trials, and exercises in one searchable knowledge base. The corpus preserves source texts without copying PDFs.

Versions in a language other than the source are automatic translations and are not verified by a person. Every record links to its source text and digital edition while preserving the author, original book title, year, and page references. Missing facts remain unknown: the project does not invent ages, duration, equipment, or risk levels.

The project code is MIT-licensed. Project metadata and translations are offered under CC BY 4.0 by default, only to the extent that the project owns the relevant rights; imported texts retain their record-level rights statements and source terms. Material transcribed from Gallica reproductions and translations based on it are a noncommercial exception described in the [data licensing policy](https://github.com/jfpio/scouting-autoresearch/blob/main/DATA-LICENSE.md).

## Next stage

V2 runs a controlled acquisition process for works by Robert Baden-Powell, Ernest Thompson Seton, and Jacques Sevin whose legal status has been confirmed. See the [project plan](https://github.com/jfpio/scouting-autoresearch/blob/main/project-plan.md)."""
    )
    return f"---\ntitle: {yaml_scalar(title)}\ndescription: {yaml_scalar(plain_text(body)[:155])}\n---\n\n{body}\n"


def write_docs(polish: list[dict], english: list[dict], sources: dict[str, dict]) -> None:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "activities").mkdir(parents=True)
    (DOCS / "en" / "activities").mkdir(parents=True)
    page_args = {"activity_count": len(polish), "source_count": len(sources)}
    (DOCS / "index.mdx").write_text(explorer_page("pl", home=True, **page_args), encoding="utf-8")
    (DOCS / "all.mdx").write_text(explorer_page("pl", **page_args), encoding="utf-8")
    (DOCS / "games.mdx").write_text(explorer_page("pl", kind="game", **page_args), encoding="utf-8")
    (DOCS / "map.mdx").write_text(semantic_map_page("pl"), encoding="utf-8")
    (DOCS / "trials.mdx").write_text(explorer_page("pl", kind="trial", **page_args), encoding="utf-8")
    (DOCS / "courses.mdx").write_text(explorer_page("pl", kind="scout-course", **page_args), encoding="utf-8")
    (DOCS / "sources.md").write_text(sources_page("pl", sources, polish), encoding="utf-8")
    (DOCS / "authors.md").write_text(authors_page("pl", sources, polish), encoding="utf-8")
    (DOCS / "about.md").write_text(about_page("pl"), encoding="utf-8")
    (DOCS / "en" / "index.mdx").write_text(explorer_page("en", home=True, **page_args), encoding="utf-8")
    (DOCS / "en" / "all.mdx").write_text(explorer_page("en", **page_args), encoding="utf-8")
    (DOCS / "en" / "games.mdx").write_text(explorer_page("en", kind="game", **page_args), encoding="utf-8")
    (DOCS / "en" / "map.mdx").write_text(semantic_map_page("en"), encoding="utf-8")
    (DOCS / "en" / "trials.mdx").write_text(explorer_page("en", kind="trial", **page_args), encoding="utf-8")
    (DOCS / "en" / "courses.mdx").write_text(explorer_page("en", kind="scout-course", **page_args), encoding="utf-8")
    (DOCS / "en" / "sources.md").write_text(sources_page("en", sources, english), encoding="utf-8")
    (DOCS / "en" / "authors.md").write_text(authors_page("en", sources, english), encoding="utf-8")
    (DOCS / "en" / "about.md").write_text(about_page("en"), encoding="utf-8")
    (DOCS / "404.md").write_text(
        '---\ntitle: "Nie znaleziono strony"\ndescription: "Żądana strona nie istnieje."\nsidebar:\n  hidden: true\n---\n\n[Wróć do wyszukiwarki](/scouting-autoresearch/).\n',
        encoding="utf-8",
    )
    (DOCS / "en" / "404.md").write_text(
        '---\ntitle: "Page not found"\ndescription: "The requested page does not exist."\nsidebar:\n  hidden: true\n---\n\n[Return to the activity finder](/scouting-autoresearch/en/).\n',
        encoding="utf-8",
    )
    for record in polish:
        (DOCS / "activities" / f"{record['id']}.md").write_text(activity_page(record, locale="pl"), encoding="utf-8")
    for record in english:
        (DOCS / "en" / "activities" / f"{record['id']}.md").write_text(activity_page(record, locale="en"), encoding="utf-8")


def public_record(record: dict) -> dict:
    return {
        key: value
        for key, value in record.items()
        if key not in {"searchText", "sourceText"}
    }


def strip_trailing_whitespace(value: str) -> str:
    """Keep source line breaks while avoiding whitespace-only export changes."""
    return "\n".join(line.rstrip() for line in value.split("\n"))


def write_exports(polish: list[dict], english: list[dict], sources: dict[str, dict]) -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    pl_public = [public_record(record) for record in polish]
    en_public = [public_record(record) for record in english]
    source_list = list(sources.values())
    for output in (GENERATED, PUBLIC_DATA):
        write_json(output / "activities.pl.json", pl_public)
        write_json(output / "activities.en.json", en_public)
        write_json(output / "sources.json", source_list)
        with (output / "activities.pl.jsonl").open("w", encoding="utf-8") as handle:
            for record in pl_public:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        with (output / "activities.en.jsonl").open("w", encoding="utf-8") as handle:
            for record in en_public:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    public = ROOT / "public"
    public.mkdir(exist_ok=True)
    index_lines = [
        "# Scouting Autoresearch",
        "",
        f"> {len(polish)} historical scouting activities with source texts and machine translations in Polish and English.",
        "",
        "- [Polish JSON](https://jfpio.github.io/scouting-autoresearch/data/activities.pl.json)",
        "- [English JSON](https://jfpio.github.io/scouting-autoresearch/data/activities.en.json)",
        "- [Semantic map — Polish](https://jfpio.github.io/scouting-autoresearch/map/)",
        "- [Semantic map — English](https://jfpio.github.io/scouting-autoresearch/en/map/)",
        "- [Polish JSONL](https://jfpio.github.io/scouting-autoresearch/data/activities.pl.jsonl)",
        "- [English JSONL](https://jfpio.github.io/scouting-autoresearch/data/activities.en.jsonl)",
        "- [Sources](https://jfpio.github.io/scouting-autoresearch/data/sources.json)",
        "- [Full bilingual text](https://jfpio.github.io/scouting-autoresearch/llms-full.txt)",
    ]
    (public / "llms.txt").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    full = ["# Scouting Autoresearch — full bilingual corpus", ""]
    for pl, en in zip(polish, english, strict=True):
        full += [
            f"## {pl['id']} — {pl['title']} / {en['title']}",
            "",
            f"Source: {pl['author']}, {pl['sourceTitle']} ({pl['year']}); {pl['sourceUrl']}",
            f"Kinds: {', '.join(pl['kinds'])}; printed pages: {pages_label(pl['printedPages'])}",
            "",
            "### Polski" + (" — tekst źródłowy" if pl["translationStatus"] == "source-text" else f" — tłumaczenie automatyczne ({pl['translationModel']}, bez weryfikacji człowieka)"),
            "",
            pl["body"],
            "",
            "### English" + (" — source text" if en["translationStatus"] == "source-text" else f" — automatic translation ({en['translationModel']}, not human-verified)"),
            "",
            en["body"],
            "",
        ]
        if pl["originalLanguage"] == "fr":
            full += [
                "### Français — texte source",
                "",
                pl["sourceText"],
                "",
            ]
    (public / "llms-full.txt").write_text(
        strip_trailing_whitespace("\n".join(full)), encoding="utf-8"
    )
    (public / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")


def main() -> None:
    polish, english, sources = load_records()
    write_exports(polish, english, sources)
    write_docs(polish, english, sources)
    print(f"Generated {len(polish)} Polish and {len(english)} English records.")


if __name__ == "__main__":
    main()
