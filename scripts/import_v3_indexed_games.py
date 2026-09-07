#!/usr/bin/env python3
"""Import agent-reviewed games from V3 books with pinned embedded text."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from common import ROOT, VAULT, dump_markdown, persisted_artifact_path, read_json, source_hash, write_json
from inventory_v3_indexed_games import SOURCE_PLANS, _page_lines, normalize_space


SOURCE_ID = "piasecki-schreiber-polish-scoutcraft-1917"
PREFIX = "hmp"
SOURCE_URL = "https://www.wbc.poznan.pl/publication/515207/edition/440525/"
PDF_URL = "https://www.wbc.poznan.pl/Content/440525/PDF/515207.pdf"
REPORT_PATH = ROOT / "data" / "reports" / f"{SOURCE_ID}-candidates.json"
INSPECTION_PATH = ROOT / "data" / "checkpoints" / "source-inspection" / f"{SOURCE_ID}.json"


# Exclusive logical-line boundaries pinned after side-by-side inspection of the
# embedded text and rendered facsimile pages. Candidate 38 corrects a bad index
# page: its actual heading is on printed page 229 / PDF page 244.
REVIEWED_BOUNDS: dict[int, tuple[str, str]] = {
    1: ("p0068-l0013", "p0069-l0004"),
    2: ("p0069-l0004", "p0069-l0013"),
    3: ("p0069-l0013", "p0069-l0024"),
    4: ("p0070-l0003", "p0070-l0024"),
    5: ("p0070-l0024", "p0071-l0007"),
    6: ("p0071-l0007", "p0072-l0007"),
    7: ("p0088-l0003", "p0088-l0012"),
    8: ("p0088-l0012", "p0088-l0021"),
    9: ("p0088-l0021", "p0089-l0008"),
    10: ("p0091-l0011", "p0091-l0021"),
    11: ("p0094-l0023", "p0095-l0017"),
    12: ("p0108-l0020", "p0109-l0012"),
    13: ("p0109-l0012", "p0109-l0020"),
    14: ("p0109-l0020", "p0110-l0016"),
    18: ("p0166-l0009", "p0166-l0019"),
    19: ("p0166-l0019", "p0167-l0006"),
    20: ("p0167-l0006", "p0167-l0014"),
    21: ("p0167-l0015", "p0167-l0024"),
    22: ("p0167-l0024", "p0168-l0005"),
    23: ("p0168-l0005", "p0168-l0015"),
    24: ("p0168-l0015", "p0169-l0005"),
    25: ("p0180-l0009", "p0180-l0016"),
    26: ("p0180-l0016", "p0180-l0023"),
    27: ("p0180-l0023", "p0181-l0008"),
    28: ("p0181-l0008", "p0181-l0028"),
    29: ("p0190-l0026", "p0191-l0004"),
    30: ("p0191-l0004", "p0191-l0012"),
    31: ("p0191-l0012", "p0191-l0023"),
    32: ("p0191-l0023", "p0192-l0011"),
    33: ("p0192-l0011", "p0192-l0027"),
    34: ("p0192-l0027", "p0193-l0013"),
    35: ("p0193-l0013", "p0194-l0018"),
    36: ("p0204-l0013", "p0205-l0004"),
    37: ("p0208-l0009", "p0208-l0016"),
    38: ("p0244-l0021", "p0244-l0028"),
    39: ("p0277-l0014", "p0277-l0026"),
}


REJECTED_REASONS = {
    15: "bibliographic reference only; this edition does not supply a self-contained game procedure",
    16: "bibliographic reference only; this edition does not supply a self-contained game procedure",
    17: "bibliographic reference only; this edition does not supply a self-contained game procedure",
    40: "creative pantomime proposal without game rules, scoring or another bounded outcome procedure",
}


# Inclusive source ranges excluded from accepted blocks because they are table or
# illustration furniture rather than the rule prose.
OMITTED_RANGES: dict[int, tuple[tuple[str, str], ...]] = {
    6: (("p0071-l0017", "p0071-l0036"),),
    11: (("p0095-l0007", "p0095-l0007"),),
    14: (("p0110-l0001", "p0110-l0001"),),
    34: (("p0192-l0031", "p0192-l0031"),),
    35: (("p0193-l0025", "p0193-l0033"),),
}


# Corrections are limited to readings confirmed on rendered facsimiles. The one
# word obscured by a library stamp is explicitly marked as a reconstruction.
LINE_REPLACEMENTS = {
    "p0069-l0008": "wykonuje zastęp nieprzyjacielski napad na nią, posługu­",
    "p0070-l0009": "mają zdążać. Jako taki punkt może służyć stromy pa­",
    "p0070-l0015": "koniecznem, aby zastępy maszerowały w zbitej groma­",
    "p0070-l0017": "którego zastępowy pierwszy wzniesie w górę chorągiew­",
    "p0070-l0018": "kę, powinni harcerze zostawać z sobą w ciągłej styczno­",
    "p0070-l0032": "wadzące go z powrotem, są już obsadzone przez har­",
    "p0070-l0033": "cerzy, których [zastępowi] ustawiają, aby mogli",
    "p0071-l0011": "nożyków, sznurków, obrazków, wogóle co jest pod ręką)",
    "p0071-l0016": "widzieć wszystko i znów przykrywa.",
    "p0088-l0015": "swą laskę w pozycyi, którą uważa za dokładnie półno-",
    "p0088-l0016": "cno-południową, bez użycia jakiegokolwiek instrumentu",
    "p0088-l0019": "który jest najbliżej prawdy. Grę tę należy ćwiczyć tak",
    "p0088-l0030": "że podchodzący, zbliżywszy się niespostrzeżenie na 15",
    "p0089-l0002": "ści w tem miejscu jakiś przedmiot i cofają się tak,",
    "p0089-l0007": "przewiązując oczy czatownikom.",
    "p0091-l0013": "cerzy »świstaków«, aby ukryli się w górach. Po śnia­",
    "p0094-l0024": "W odległości 1½ km. od siebie zakładają dwa zastępy",
    "p0094-l0026": "biorący w zabawie udziału, puszcza tymczasem na wodę",
    "p0108-l0030": "jednak, niż 300 m. od Zbaraża (najlepiej wyznaczyć pe­",
    "p0166-l0021": "pów i pozwala im patrzeć ½ minuty na każdą wy­",
    "p0167-l0007": "Harcmistrz posyła po kolei harcerzy na ½ minuty",
    "p0167-l0027": "guziczków i t. p. i każe porzucać tu i ówdzie nieco tych",
    "p0168-l0003": "»charty« muszą zacierać zaraz po dostrzeżeniu, dla schlu­",
    "p0168-l0010": "w szereg w odległości ½ m. jedna od drugiej i każe",
    "p0190-l0027": "Daje się czas jednemu z harcerzy, aby się ukrył;",
    "p0192-l0009": "w czasie krótkim, n. p. 1½ min., dotknąć niewidomego",
    "p0192-l0029": "część miasta o powierzchni 1—3 km.², opisuje się",
    "p0193-l0017": "umieszczonych ½ m. nad ziemią), nie bliżej jak 200 m.",
    "p0194-l0007": "liczy się podwójnie. Przy grze tej są czynni czterej",
    "p0204-l0026": "góle brać udziału w grze. Gdy myśliwy trafił piłką",
    "p0244-l0027": "wyścigi (»dobry uczynek na wyścigi«).",
    "p0277-l0015": "Jeden zastęp, w roli »omdlałych«, kładzie się w rzę­",
    "p0277-l0029": "pantomimy interesujące bardzo tak widzów, jak i wykona­",
}


INLINE_HEADING_BODY = {
    38: "Harcerze wychodzą pojedynczo, pa­",
}


def locator_key(locator: str) -> tuple[int, int]:
    match = re.fullmatch(r"p(\d{4})-l(\d{4})", locator)
    if not match:
        raise ValueError(f"Invalid logical-line locator: {locator}")
    return int(match.group(1)), int(match.group(2))


def logical_lines(pages: list[str]) -> list[dict[str, Any]]:
    result = []
    for pdf_page, page in enumerate(pages, start=1):
        for line in _page_lines(page):
            result.append({
                "pdfPage": pdf_page,
                "line": line["line"],
                "lineId": f"p{pdf_page:04d}-l{line['line']:04d}",
                "text": line["text"],
            })
    return result


def in_ranges(locator: str, ranges: tuple[tuple[str, str], ...]) -> bool:
    key = locator_key(locator)
    return any(locator_key(start) <= key <= locator_key(end) for start, end in ranges)


def render_source_lines(lines: list[dict[str, Any]]) -> str:
    paragraphs: list[str] = []
    current = ""
    for item in lines:
        text = normalize_space(str(item["text"]))
        if not text or re.fullmatch(r"\d{1,3}\*?", text):
            continue
        if not current:
            current = text
        elif current.endswith("\u00ad"):
            current = current[:-1] + text
        elif current.endswith("-") and re.match(r"^[a-ząćęłńóśźż]", text):
            current = current[:-1] + text
        else:
            current += " " + text
    if current:
        paragraphs.append(current.strip())
    body = "\n\n".join(paragraphs)
    body = re.sub(r"\s+([,.;:!?])", r"\1", body)
    if not body:
        raise ValueError("Source block contains no prose")
    return body


def _load_source() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    report = read_json(REPORT_PATH)
    inspection = read_json(INSPECTION_PATH)
    embedded = inspection.get("embeddedText") or {}
    text_path = persisted_artifact_path(embedded)
    payload = text_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != embedded.get("sha256"):
        raise ValueError("Pinned embedded-text hash mismatch")
    pages = payload.decode("utf-8", errors="strict").split("\f")
    return report, embedded, logical_lines(pages)


def build_import() -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any], str]], dict[str, Any]]:
    report, embedded, all_lines = _load_source()
    positions = {str(line["lineId"]): index for index, line in enumerate(all_lines)}
    candidates = report.get("candidates") or []
    if [int(item["number"]) for item in candidates] != list(range(1, 41)):
        raise ValueError("Candidate report no longer contains the pinned 1-40 sequence")
    if set(REVIEWED_BOUNDS) | set(REJECTED_REASONS) != set(range(1, 41)):
        raise ValueError("Every candidate must have one reviewed decision")

    outputs: list[tuple[Path, dict[str, Any], str]] = []
    activities: list[dict[str, Any]] = []
    body_hashes: dict[str, int] = {}
    revision = f"sha256:{embedded['sha256']}"
    for candidate in candidates:
        number = int(candidate["number"])
        if number in REJECTED_REASONS:
            continue
        start_line, end_exclusive = REVIEWED_BOUNDS[number]
        start = positions[start_line]
        end = positions[end_exclusive]
        raw = all_lines[start:end]
        reviewed_hash = hashlib.sha256(
            ("\n".join(normalize_space(str(line["text"])) for line in raw) + "\n").encode("utf-8")
        ).hexdigest()
        ranges = OMITTED_RANGES.get(number, ())
        kept = []
        for index, line in enumerate(raw):
            if index == 0:
                inline = INLINE_HEADING_BODY.get(number)
                if inline:
                    kept.append({**line, "text": inline})
                continue
            if in_ranges(str(line["lineId"]), ranges):
                continue
            replacement = LINE_REPLACEMENTS.get(str(line["lineId"]))
            kept.append({**line, "text": replacement if replacement is not None else line["text"]})
        source_body = render_source_lines(kept)
        normalized_hash = hashlib.sha256(normalize_space(source_body).encode("utf-8")).hexdigest()
        if normalized_hash in body_hashes:
            raise ValueError(f"Exact body duplicate: {number} and {body_hashes[normalized_hash]}")
        body_hashes[normalized_hash] = number

        title = normalize_space(str(candidate["titleRaw"]))
        pdf_start = locator_key(start_line)[0]
        pdf_end = int(kept[-1]["pdfPage"])
        printed_start = 229 if number == 38 else int(candidate["printedPageStart"])
        printed_end = max(printed_start, pdf_end - 15)
        activity_id = f"{PREFIX}-{number:03d}"
        facsimile_url = f"{PDF_URL}#page={pdf_start}"
        editorial_notes = []
        if ranges:
            editorial_notes.append(
                "*Zakres transkrypcji: tabelę, tekst ilustracji lub nagłówek strony pominięto; dokładne granice zapisano w raporcie ekstrakcji.*"
            )
        if number == 5:
            editorial_notes.append(
                "*Uwaga transkrypcyjna: słowo „zastępowi” zrekonstruowano w nawiasie kwadratowym, ponieważ częściowo zasłania je pieczęć biblioteczna.*"
            )
        source_note = (
            "---\n\n"
            + ("\n\n".join(editorial_notes) + "\n\n" if editorial_notes else "")
            + f"*Źródło skanu: [Wielkopolska Biblioteka Cyfrowa]({SOURCE_URL}), "
            + f"oznaczenie „domena publiczna”. [Zobacz PDF — strona {pdf_start}]({facsimile_url}).*"
        )
        body = f"{source_body}\n\n{source_note}"
        metadata: dict[str, Any] = {
            "id": activity_id,
            "kinds": ["game"],
            "sourceId": SOURCE_ID,
            "originalLanguage": "pl",
            "title": title,
            "traits": [],
            "section": candidate["section"],
            "printedPages": list(range(printed_start, printed_end + 1)),
            "pdfPages": list(range(pdf_start, pdf_end + 1)),
            "transcriptionStatus": "embedded-text-unreviewed",
            "safetyStatus": "historical-unreviewed",
            "rightsStatus": "public-domain",
            "sourceUrl": SOURCE_URL,
            "digitalEditionUrl": SOURCE_URL,
            "facsimileUrl": facsimile_url,
            "sourceRevision": revision,
            "participantScales": ["unknown"],
            "participantScaleBasis": "unknown",
        }
        if ranges:
            metadata["contentOmissions"] = ["table-illustration-or-page-furniture"]
        if number == 5:
            metadata["transcriptionNotes"] = ["one word reconstructed where the facsimile is obscured by a library stamp"]
        metadata["sourceHash"] = source_hash(title, body)
        outputs.append((VAULT / "activities" / f"{activity_id}.md", metadata, body))
        activity = {
            "id": activity_id,
            "candidateNumber": number,
            "title": title,
            "startLine": start_line,
            "endLineExclusive": end_exclusive,
            "pdfPages": metadata["pdfPages"],
            "printedPages": metadata["printedPages"],
            "sourceBlockSha256": reviewed_hash,
            "publishedSourceHash": metadata["sourceHash"],
        }
        if ranges:
            activity["omittedSourceRanges"] = [
                {"startLine": first, "endLine": last, "reason": "table-illustration-or-page-furniture-outside-record-scope"}
                for first, last in ranges
            ]
        activities.append(activity)

    extraction = {
        "schemaVersion": 1,
        "sourceId": SOURCE_ID,
        "sourceSha256": embedded["sha256"],
        "parserVersion": "harce-1917-reviewed-indexed-game-import-v1",
        "reviewRequired": False,
        "activityCount": len(activities),
        "wholeSourceCopiedToRepository": False,
        "selection": {
            "candidateCount": len(candidates),
            "acceptedGameCount": len(activities),
            "rejectedCount": len(REJECTED_REASONS),
            "basis": "bounded, self-contained game or competitive exercise confirmed against rendered facsimile pages",
            "rejectedCandidates": [
                {"candidateNumber": number, "reason": reason}
                for number, reason in sorted(REJECTED_REASONS.items())
            ],
        },
        "transcriptionEvidence": {
            "sourceStatement": "Pinned embedded text and rendered pages stored in gitignored repository artifacts on Group Storage.",
            "sourceLocation": PDF_URL,
            "deterministicNormalization": [
                "omit the activity heading represented in frontmatter",
                "omit isolated printed-page numbers and pinned table or illustration ranges",
                "join layout soft wraps and dehyphenate line-break continuations",
                "apply only facsimile-confirmed OCR corrections",
                "mark the one reconstruction obscured by a library stamp with square brackets",
                "preserve source spelling and paragraph order without lexical modernization",
            ],
            "lexicalModernization": False,
        },
        "deduplication": {"exactBodyMatches": [], "nearDuplicateCandidates": []},
        "activities": activities,
    }

    rights_evidence = report["selection"]["rightsEvidence"]
    source_metadata = {
        "id": SOURCE_ID,
        "activityPrefix": PREFIX,
        "author": "Mieczysław Schreiber i Eugeniusz Piasecki",
        "title": "Harce młodzieży polskiej",
        "year": 1917,
        "edition": "wydanie 2",
        "publicationPlace": "Lwów",
        "publisher": "Książnica Polska Towarzystwa Nauczycieli Szkół Wyższych",
        "originalLanguage": "pl",
        "rightsStatus": "public-domain",
        "rightsStatement": "„domena publiczna” — oznaczenie konkretnego obiektu w WBC",
        "rightsEvidenceUrl": SOURCE_URL,
        "rightsEvidence": rights_evidence,
        "sourceUrl": SOURCE_URL,
        "digitalEditionUrl": SOURCE_URL,
        "pdfUrl": PDF_URL,
        "accessedOn": "2026-09-07",
        "sourceRevision": revision,
        "extractionReport": f"data/reports/{SOURCE_ID}-extraction.json",
        "translationPolicy": {
            "targetLocale": "en",
            "modelRequested": "mistral-large-2512",
            "reasoningMode": "disabled",
            "promptVersion": "translation-pl-en-v5",
            "usageRequired": True,
            "requestBudgetRequired": True,
            "billingMode": "education-credit",
            "enforceReferenceCostLimit": True,
            "maxReferenceCostUsd": 10,
            "report": f"data/reports/{SOURCE_ID}-translation-pl-en.json",
            "priceAccessedOn": "2026-09-04",
            "smokeTestActivityIds": [
                "hmp-001", "hmp-006", "hmp-012", "hmp-024", "hmp-035", "hmp-039",
            ],
        },
    }
    return extraction, outputs, source_metadata


def execute_import() -> dict[str, Any]:
    extraction, outputs, source_metadata = build_import()
    expected_names = {path.name for path, _metadata, _body in outputs}
    for path, metadata, body in outputs:
        dump_markdown(path, metadata, body)
    for stale in (VAULT / "activities").glob(f"{PREFIX}-*.md"):
        if stale.name not in expected_names:
            stale.unlink()
    source_body = (
        "# Harce młodzieży polskiej\n\n"
        "Źródło bibliograficzne dla gier wyodrębnionych z obiektu WBC jawnie oznaczonego "
        "jako domena publiczna. PDF, warstwa tekstowa i renderowane strony są przechowywane "
        "lokalnie w ignorowanym przez Git katalogu `artifacts/` na Group Storage; publikowany "
        "korpus zawiera tylko wybrane, udokumentowane rekordy.\n\n"
        f"- [Rekord cyfrowy w WBC]({SOURCE_URL})\n"
        f"- [PDF wydania]({PDF_URL})\n"
    )
    dump_markdown(VAULT / "sources" / f"{SOURCE_ID}.md", source_metadata, source_body)
    write_json(ROOT / "data" / "reports" / f"{SOURCE_ID}-extraction.json", extraction)

    report = read_json(REPORT_PATH)
    accepted = {item["candidateNumber"] for item in extraction["activities"]}
    for candidate in report["candidates"]:
        number = int(candidate["number"])
        candidate["recordReviewStatus"] = "accepted-game" if number in accepted else "rejected-not-game"
        if number in REJECTED_REASONS:
            candidate["recordReviewReason"] = REJECTED_REASONS[number]
        else:
            candidate.pop("recordReviewReason", None)
            start, end = REVIEWED_BOUNDS[number]
            candidate["reviewedStartLine"] = start
            candidate["reviewedEndLineExclusive"] = end
            if number == 38:
                candidate["printedPageStart"] = 229
                candidate["pdfPageStart"] = 244
                candidate["pageLocator"] = "p0244"
                candidate["bestLineLocator"] = "p0244-l0021"
                candidate["titleLocatorMatch"] = "Błędni rycerze."
                candidate["locatorStatus"] = "heading-located-after-index-correction"
    expected_activity_ids = sorted(item["id"] for item in extraction["activities"])
    translation_report_path = ROOT / "data" / "reports" / f"{SOURCE_ID}-translation-pl-en.json"
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
    report["selection"]["importedActivityCount"] = len(outputs)
    report["selection"]["recordReviewRequired"] = False
    write_json(REPORT_PATH, report)
    return extraction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_id", choices=[SOURCE_ID])
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    extraction, _outputs, _source = build_import()
    if args.execute:
        extraction = execute_import()
    print(json.dumps({
        "mode": "execute" if args.execute else "dry-run",
        "sourceId": args.source_id,
        **extraction["selection"],
        "activityPrefix": PREFIX,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
