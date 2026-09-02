#!/usr/bin/env python3
"""Generate the website and public exports from the Obsidian vault."""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

from common import GENERATED, PUBLIC_DATA, ROOT, VAULT, load_markdown, write_json


DOCS = ROOT / "src" / "content" / "docs"
SITE_ROOT = "https://jfpio.github.io/scouting-autoresearch"


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


def load_records() -> tuple[list[dict], list[dict], dict[str, dict]]:
    sources = load_sources()
    polish: list[dict] = []
    english: list[dict] = []
    for path in sorted((VAULT / "activities").glob("*.md")):
        metadata, body = load_markdown(path)
        source = sources[metadata["sourceId"]]
        common = {
            "id": metadata["id"],
            "kinds": metadata["kinds"],
            "sourceId": metadata["sourceId"],
            "author": source["author"],
            "sourceTitle": source["title"],
            "year": source["year"],
            "publisher": source.get("publisher"),
            "printedPages": metadata["printedPages"],
            "pdfPages": metadata["pdfPages"],
            "sourceUrl": metadata["sourceUrl"],
            "digitalEditionUrl": metadata["digitalEditionUrl"],
            "pdfUrl": source["pdfUrl"],
            "sourceCommit": metadata["sourceCommit"],
            "sourceHash": metadata["sourceHash"],
            "rightsStatus": metadata["rightsStatus"],
            "transcriptionStatus": metadata["transcriptionStatus"],
            "safetyStatus": metadata["safetyStatus"],
            "originalLanguage": metadata["originalLanguage"],
        }
        pl_record = {
            **common,
            "locale": "pl",
            "title": metadata["title"],
            "body": body,
            "traits": metadata.get("traits", []),
            "section": metadata.get("section", ""),
            "translationStatus": "source-text",
            "summary": summary(body),
        }
        pl_record["searchText"] = " ".join(
            [pl_record["title"], plain_text(body), *pl_record["traits"], pl_record["section"], common["author"], common["sourceTitle"]]
        ).lower()
        polish.append(pl_record)

        translation_path = VAULT / "translations" / "en" / path.name
        if not translation_path.exists():
            raise RuntimeError(f"Missing English translation: {translation_path.name}")
        translation, translated_body = load_markdown(translation_path)
        if translation.get("sourceHash") != metadata["sourceHash"]:
            raise RuntimeError(f"Stale English translation: {translation_path.name}")
        en_record = {
            **common,
            "locale": "en",
            "title": translation["title"],
            "body": translated_body,
            "traits": translation.get("traits", []),
            "section": translation.get("section", ""),
            "translationStatus": translation["status"],
            "translationModel": translation["model"],
            "translationPromptVersion": translation["promptVersion"],
            "translationGeneratedAt": translation["generatedAt"],
            "summary": summary(translated_body),
        }
        en_record["searchText"] = " ".join(
            [en_record["title"], plain_text(translated_body), *en_record["traits"], en_record["section"], common["author"], common["sourceTitle"]]
        ).lower()
        english.append(en_record)
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
            *[f"  - {page}" for page in record["pdfPages"]],
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
    page = record["pdfPages"][0]
    kinds = ", ".join(("gra" if value == "game" else "próba") if is_pl else value for value in record["kinds"])
    traits = ", ".join(record["traits"]) or ("Nie podano w źródle" if is_pl else "Not stated in the source")
    machine = ""
    if not is_pl:
        machine = (
            '<div class="machine-notice"><strong>Automatic translation.</strong> '
            f'This English text was generated automatically with <code>{record["translationModel"]}</code> and has not been verified by a person. '
            f'<a href="{SITE_ROOT}/activities/{record["id"]}/">Read the source Polish transcription</a>; '
            "the source scan is linked in the metadata below.</div>\n\n"
        )
    warning = (
        "Historyczna aktywność nie jest automatycznie rekomendacją metodyczną. Przed użyciem oceń współczesne ryzyko, wiek uczestników, warunki i przepisy."
        if is_pl
        else "A historical activity is not automatically a modern recommendation. Assess present-day risk, participants’ ages, conditions, and applicable rules before use."
    )
    original_link = f"{SITE_ROOT}/activities/{record['id']}/"
    translated_link = f"{SITE_ROOT}/en/activities/{record['id']}/"
    labels = {
        "meta": "Metadane" if is_pl else "Metadata",
        "type": "Rodzaj" if is_pl else "Type",
        "traits": "Cechy" if is_pl else "Traits",
        "source": "Źródło" if is_pl else "Source",
        "pages": "Strony drukowane / PDF" if is_pl else "Printed / PDF pages",
        "edition": "Wydanie cyfrowe" if is_pl else "Digital edition",
        "facsimile": "Otwórz skan na właściwej stronie" if is_pl else "Open the scan at the relevant page",
        "other": "Zobacz tłumaczenie automatyczne" if is_pl else "Read the source Polish transcription",
    }
    other_link = translated_link if is_pl else original_link
    return (
        frontmatter(record, locale=locale)
        + "\n\n"
        + machine
        + f'<div class="safety-notice"><strong>{"Uwaga bezpieczeństwa." if is_pl else "Safety note."}</strong> {warning}</div>\n\n'
        + f"## {labels['meta']}\n\n"
        + f"- **{labels['type']}:** {kinds}\n"
        + f"- **{labels['traits']}:** {traits}\n"
        + f"- **{labels['source']}:** {record['author']}, *{record['sourceTitle']}* ({record['year']})\n"
        + f"- **{labels['pages']}:** {pages_label(record['printedPages'])} / {pages_label(record['pdfPages'])}\n"
        + f"- **{labels['edition']}:** [GitHub Pages]({record['digitalEditionUrl']}) · [Polona]({record['sourceUrl']})\n"
        + f"- **{labels['facsimile']}:** [PDF, s. {page}]({record['pdfUrl']}#page={page})\n"
        + f"- **{labels['other']}:** [{record['id']}]({other_link})\n\n"
        + "## "
        + ("Treść źródłowa" if is_pl else "Translated text")
        + "\n\n"
        + record["body"].strip()
        + "\n"
    )


def explorer_page(locale: str, *, kind: str | None = None, home: bool = False) -> str:
    is_pl = locale == "pl"
    titles = {
        None: ("Wszystkie aktywności", "All activities"),
        "game": ("Gry", "Games"),
        "trial": ("Próby", "Trials"),
    }
    title = ("Znajdź aktywność" if is_pl else "Find an activity") if home else titles[kind][0 if is_pl else 1]
    description = (
        "Przeszukuj historyczne gry i próby według treści, cech, autora, książki, roku oraz działu."
        if is_pl
        else "Search historical games and trials by text, traits, author, book, year, and section."
    )
    component_path = "../../components/ActivityExplorer.astro" if locale == "pl" else "../../../components/ActivityExplorer.astro"
    hero = ""
    if home:
        eyebrow = "OTWARTA BAZA WIEDZY · V0" if is_pl else "OPEN KNOWLEDGE BASE · V0"
        text = (
            "202 aktywności z dwóch książek w domenie publicznej. Oryginalne transkrypcje po polsku i automatyczne tłumaczenia po angielsku."
            if is_pl
            else "202 activities from two public-domain books. Original Polish transcriptions with machine-generated English translations."
        )
        hero = f'<p class="eyebrow">{eyebrow}</p>\n\n# {title}\n\n{text}\n\n'
    else:
        hero = f"# {title}\n\n{description}\n\n"
    kind_prop = f' kind="{kind}"' if kind else ""
    translation_note = (
        ""
        if is_pl
        else "> **Automatic translations:** all English texts were generated automatically and have not been verified by a person. Every activity links to its source Polish transcription and the scan.\n\n"
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


def sources_page(locale: str, sources: dict[str, dict]) -> str:
    is_pl = locale == "pl"
    title = "Źródła" if is_pl else "Sources"
    intro = (
        "Pełne teksty są publikowane wyłącznie dla wydań z potwierdzonym statusem domeny publicznej. Oznaczenie praw przypisujemy instytucji źródłowej."
        if is_pl
        else "Full text is published only for editions with confirmed public-domain status. Rights statements are attributed to the source institution."
    )
    lines = ["---", f"title: {yaml_scalar(title)}", f"description: {yaml_scalar(intro)}", "---", "", f"# {title}", "", intro, ""]
    for source in sources.values():
        lines += [
            f"## {source['title']}",
            "",
            f"**{source['author']} · {source['year']} · {source['publicationPlace']} · {source['publisher']}**",
            "",
            f"{source['rightsStatement']}",
            "",
            f"[{'Rekord Polony' if is_pl else 'Polona record'}]({source['sourceUrl']}) · "
            f"[{'Wydanie cyfrowe' if is_pl else 'Digital edition'}]({source['digitalEditionUrl']})",
            "",
        ]
    return "\n".join(lines)


def about_page(locale: str) -> str:
    is_pl = locale == "pl"
    title = "O projekcie" if is_pl else "About"
    body = (
        """Scouting Autoresearch porządkuje historyczne gry, próby i ćwiczenia harcerskie w jednej, przeszukiwalnej bazie. V0 importuje bezstratnie dwa niezależne wydania cyfrowe i nie kopiuje ich PDF-ów.

Angielskie wersje są tłumaczeniami automatycznymi i nie są weryfikowane przez człowieka. Każdy rekord prowadzi do polskiej transkrypcji źródłowej i skanu oraz zachowuje autora, oryginalny tytuł książki, rok i strony. Brakujące dane pozostają nieznane — nie dopowiadamy wieku, czasu, sprzętu ani ryzyka.

Kod projektu jest udostępniony na licencji MIT. Projektowe metadane i tłumaczenia są udostępniane na CC BY 4.0 wyłącznie w zakresie posiadanych praw; importowane teksty zachowują indywidualne oznaczenia praw.

## Następny etap

V2 przygotowuje kontrolowany proces wyszukiwania public-domain dzieł Roberta Baden-Powella, Ernesta Thompsona Setona i Jacques’a Sevina. Agent może proponować źródła, ale zatwierdzenie praw i publikacji zawsze wymaga człowieka. Szczegóły zawiera [plan projektu](https://github.com/jfpio/scouting-autoresearch/blob/main/project-plan.md)."""
        if is_pl
        else """Scouting Autoresearch organizes historical scouting games, trials, and exercises in one searchable knowledge base. V0 imports two independent digital editions without copying their PDFs.

English versions are automatic translations and are not verified by a person. Every record links to the source Polish transcription and scan while preserving the author, original book title, year, and page references. Missing facts remain unknown: the project does not invent ages, duration, equipment, or risk levels.

The project code is MIT-licensed. Project metadata and translations are offered under CC BY 4.0 only to the extent that the project owns the relevant rights; imported texts retain their record-level rights statements.

## Next stage

V2 prepares a controlled discovery process for public-domain works by Robert Baden-Powell, Ernest Thompson Seton, and Jacques Sevin. The agent may propose sources, but rights approval and publication always require a human. See the [project plan](https://github.com/jfpio/scouting-autoresearch/blob/main/project-plan.md)."""
    )
    return f"---\ntitle: {yaml_scalar(title)}\ndescription: {yaml_scalar(plain_text(body)[:155])}\n---\n\n# {title}\n\n{body}\n"


def write_docs(polish: list[dict], english: list[dict], sources: dict[str, dict]) -> None:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "activities").mkdir(parents=True)
    (DOCS / "en" / "activities").mkdir(parents=True)
    (DOCS / "index.mdx").write_text(explorer_page("pl", home=True), encoding="utf-8")
    (DOCS / "all.mdx").write_text(explorer_page("pl"), encoding="utf-8")
    (DOCS / "games.mdx").write_text(explorer_page("pl", kind="game"), encoding="utf-8")
    (DOCS / "trials.mdx").write_text(explorer_page("pl", kind="trial"), encoding="utf-8")
    (DOCS / "sources.md").write_text(sources_page("pl", sources), encoding="utf-8")
    (DOCS / "about.md").write_text(about_page("pl"), encoding="utf-8")
    (DOCS / "en" / "index.mdx").write_text(explorer_page("en", home=True), encoding="utf-8")
    (DOCS / "en" / "all.mdx").write_text(explorer_page("en"), encoding="utf-8")
    (DOCS / "en" / "games.mdx").write_text(explorer_page("en", kind="game"), encoding="utf-8")
    (DOCS / "en" / "trials.mdx").write_text(explorer_page("en", kind="trial"), encoding="utf-8")
    (DOCS / "en" / "sources.md").write_text(sources_page("en", sources), encoding="utf-8")
    (DOCS / "en" / "about.md").write_text(about_page("en"), encoding="utf-8")
    (DOCS / "404.md").write_text(
        '---\ntitle: "Nie znaleziono strony"\ndescription: "Żądana strona nie istnieje."\nsidebar:\n  hidden: true\n---\n\n# Nie znaleziono strony\n\n[Wróć do wyszukiwarki](/scouting-autoresearch/).\n',
        encoding="utf-8",
    )
    (DOCS / "en" / "404.md").write_text(
        '---\ntitle: "Page not found"\ndescription: "The requested page does not exist."\nsidebar:\n  hidden: true\n---\n\n# Page not found\n\n[Return to the activity finder](/scouting-autoresearch/en/).\n',
        encoding="utf-8",
    )
    for record in polish:
        (DOCS / "activities" / f"{record['id']}.md").write_text(activity_page(record, locale="pl"), encoding="utf-8")
    for record in english:
        (DOCS / "en" / "activities" / f"{record['id']}.md").write_text(activity_page(record, locale="en"), encoding="utf-8")


def public_record(record: dict) -> dict:
    return {key: value for key, value in record.items() if key != "searchText"}


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
        "> 202 historical scouting activities: original Polish texts and machine-translated English versions.",
        "",
        "- [Polish JSON](https://jfpio.github.io/scouting-autoresearch/data/activities.pl.json)",
        "- [English JSON](https://jfpio.github.io/scouting-autoresearch/data/activities.en.json)",
        "- [Polish JSONL](https://jfpio.github.io/scouting-autoresearch/data/activities.pl.jsonl)",
        "- [English JSONL](https://jfpio.github.io/scouting-autoresearch/data/activities.en.jsonl)",
        "- [Sources](https://jfpio.github.io/scouting-autoresearch/data/sources.json)",
        "- [Full bilingual text](https://jfpio.github.io/scouting-autoresearch/llms-full.txt)",
        "",
        "Historical material is not automatically a recommendation. Perform a modern risk assessment before use.",
    ]
    (public / "llms.txt").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    full = ["# Scouting Autoresearch — full bilingual corpus", ""]
    for pl, en in zip(polish, english, strict=True):
        full += [
            f"## {pl['id']} — {pl['title']} / {en['title']}",
            "",
            f"Source: {pl['author']}, {pl['sourceTitle']} ({pl['year']}); {pl['sourceUrl']}",
            f"Kinds: {', '.join(pl['kinds'])}; printed pages: {pages_label(pl['printedPages'])}; PDF pages: {pages_label(pl['pdfPages'])}",
            "",
            "### Polski — tekst źródłowy",
            "",
            pl["body"],
            "",
            f"### English — automatic translation ({en['translationModel']}, not human-verified)",
            "",
            en["body"],
            "",
        ]
    (public / "llms-full.txt").write_text("\n".join(full), encoding="utf-8")
    (public / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")


def main() -> None:
    polish, english, sources = load_records()
    write_exports(polish, english, sources)
    write_docs(polish, english, sources)
    print(f"Generated {len(polish)} Polish and {len(english)} English records.")


if __name__ == "__main__":
    main()
