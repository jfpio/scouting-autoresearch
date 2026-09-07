#!/usr/bin/env python3
"""Import reviewed game blocks from Sedlaczek's 1921 *Szkoła harcerza*.

The importer deliberately reads the pinned Mistral OCR responses from the
gitignored Group Storage artifact store.  Only bounded activity prose,
provenance, hashes and review decisions are written to Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common import ROOT, VAULT, dump_markdown, read_json, source_hash, write_json


SOURCE_ID = "sedlaczek-scout-school-1921"
PREFIX = "shc"
SOURCE_URL = "https://www.sbc.org.pl/dlibra/publication/68754/edition/64835"
PDF_URL = "https://www.sbc.org.pl/Content/64835/PDF/64835.pdf"
CHECKPOINT_PATH = ROOT / "data" / "checkpoints" / "source-acquisition" / f"{SOURCE_ID}.json"
REPORT_PATH = ROOT / "data" / "reports" / f"{SOURCE_ID}-candidates.json"


@dataclass(frozen=True)
class ReviewedSpan:
    start_view: int
    end_view: int
    start_pattern: str
    end_pattern: str | None
    include_start: bool = False
    excluded_patterns: tuple[str, ...] = ()


# Character-level boundaries are necessary because this edition sometimes puts
# two activities in one OCR paragraph.  Patterns are pinned to the persisted raw
# responses and verified against the rendered facsimiles.
REVIEWED_SPANS: dict[int, ReviewedSpan] = {
    2: ReviewedSpan(
        56,
        57,
        r"^2\. Szukanie naparstka\.",
        r"^\*\*Pieśni\.\*\*",
        excluded_patterns=(r"^\*\*\) Tyle tylko można było pisać .+$",),
    ),
    3: ReviewedSpan(66, 66, r"^# K i m\.$", r"^Uprawiając grę Kima"),
    4: ReviewedSpan(71, 71, r"^Ćwiczenie pokojowe\. 1\. Szukanie zegarka\.", r"^2\. Nielad na stole\."),
    5: ReviewedSpan(71, 71, r"^2\. Nielad na stole\.", r"^Rysowanie znaków patrolowych\."),
    6: ReviewedSpan(93, 93, r"^2\. Ćwiczenie węchu\.", r"^Organizowanie pracy\."),
    8: ReviewedSpan(130, 130, r"^4\) Gra Morgana\.", r"^# Wycieczka\."),
    10: ReviewedSpan(180, 181, r"^\*Karton Bineta\.\*", r"^Obserwowanie obrazków"),
    11: ReviewedSpan(189, 189, r"^\*Ćwiczenia pokojowe\.\* 1\) Dobieranie barw\.", r"^2\) Rysowanie z pamięci"),
    12: ReviewedSpan(71, 72, r"^3\. Podrywka ze zwodzeniem\.", r"4\. \*Ciuc u-babka\*\."),
    13: ReviewedSpan(72, 72, r"4\. \*Ciuc u-babka\*\.", r"5\. Kucie 120\."),
    14: ReviewedSpan(95, 95, r"2\. Bieg rozstawny 65\.", r"3\) \*Dołki\* 126\."),
    15: ReviewedSpan(140, 140, r"^Ptasznik\.", r"Walka byków\."),
    16: ReviewedSpan(140, 141, r"Walka byków\.", None),
    17: ReviewedSpan(16, 16, r"^3\. W porze poobiedniej", r"^W podobny sposób", include_start=True),
    18: ReviewedSpan(84, 84, r"^2\. \*Podchodzenie ślepego\.\*", r"^4\. \*Przekradanka\*"),
    19: ReviewedSpan(84, 84, r"^4\. \*Przekradanka\* \(mur ślepych\)\.", r"^5\. \*Wyprawa po rośliny\*"),
    20: ReviewedSpan(84, 84, r"^5\. \*Wyprawa po rośliny\*,", r"^\*Gry ruchowe\.\*", include_start=True),
    22: ReviewedSpan(94, 94, r"^\*Zbieranie bawełny\.\*", None),
    23: ReviewedSpan(95, 95, r"^3\. \*Ognisko na wyścigi\.\*", r"^\*Gry ruchowe\.\*"),
    24: ReviewedSpan(112, 113, r"3\. Blisko daleko\.", r"^\*Bieg harcowy\.\*"),
    26: ReviewedSpan(119, 119, r"^1\) Tropienie za skrawkami \(Zając\) \(przygotowanie do biegu na przełaj\)\.", r"^2\) Pamiętanie śladów\."),
    27: ReviewedSpan(119, 120, r"^2\) Pamiętanie śladów\.", r"^4\) \*Polowanie na jelenia\*"),
    28: ReviewedSpan(130, 131, r"^1\) Podchodzenie straży\.", r"^Odmianą tej gry jest: podchodzenie zwierzyny\."),
    29: ReviewedSpan(131, 131, r"^Odmianą tej gry jest: podchodzenie zwierzyny\.", None),
    31: ReviewedSpan(169, 170, r"^# Łapanka w mieście\.$", None),
    32: ReviewedSpan(181, 181, r"^1\) Tropienie po śniegu\. 2\) Rysunek śladu\.", r"^Gry ruchowe\."),
    33: ReviewedSpan(189, 190, r"^Fort śnieżny\.", r"^Dwaj gońce z depeszami\."),
    34: ReviewedSpan(190, 190, r"^Dwaj gońce z depeszami\.", None),
    35: ReviewedSpan(
        196,
        197,
        r"^1\) Polowanie na lisa\.",
        r"^2\) Fort śnieżny\.",
        excluded_patterns=(r"^1\) Przeczytaj: Baden-Powell .+$",),
    ),
    36: ReviewedSpan(199, 199, r"^### \*Pająk i muchą\.\*$", r"^\*Kozacki proceder w stepie\.\*"),
    37: ReviewedSpan(
        199,
        200,
        r"^\*Kozacki proceder w stepie\.\*",
        None,
        excluded_patterns=(r"^\*\) Szereg takich gier .+$",),
    ),
    38: ReviewedSpan(
        208,
        209,
        r"^1\) \*Zwiady w mieście\.\*",
        r"^2\) \*Wyprawa do bieguna\.\*",
        excluded_patterns=(r"^\*\) Baden-Powell: Odezwa na zlot w Birmingham\.$",),
    ),
    39: ReviewedSpan(209, 209, r"^2\) \*Wyprawa do bieguna\.\*", None),
    40: ReviewedSpan(217, 218, r"^\*Ucieczka Sybiraka\.\*", r"^## Próba i przyrzeczenie\."),
}


REJECTED_REASONS = {
    1: "short observation drill without a game or competitive procedure",
    7: "drawing exercise without a game or competitive procedure",
    9: "measurement drill without a game or competitive procedure",
    21: "distance-estimation drill without a game or competitive procedure",
    25: "running technique and practice advice, not a bounded game",
    30: "urban reconnaissance checklist without a game or competitive procedure",
}


# Only readings checked on the rendered facsimiles are corrected.  Source-era
# spelling and even evident printed wording (for example “serdatki” and “bieg
# został schwytany”) remain unchanged.
FACSIMILE_CONFIRMED_CORRECTIONS: dict[int, tuple[tuple[str, str], ...]] = {
    2: (
        (
            "Zastępowy kaźne na pare minut opuscić izbe swemu zastȩpowi, a sam tymczasem kładzie na parstek",
            "Zastępowy każe na parę minut opuścić izbę swemu zastępowi, a sam tymczasem kładzie naparstek",
        ),
        ("kawełek", "kawałek"),
    ),
    16: (("chustka bykowi", "chustką bykowi"), ("druga połowy gry", "druga połowa gry")),
    17: (("połowanie na jelenia", "polowanie na jelenia"), ("„jelen”", "„jeleń”")),
    23: (("wyteżających zabawach", "wytężających zabawach"),),
    24: (("kogutów pialo", "kogutów piało"),),
    29: (("zrządka porosły", "zrzadka porosły"), ("starałą się", "starają się")),
    31: (("w tem przepuszczeniu", "w tem przypuszczeniu"),),
    34: (("drużyńowy", "drużynowy"),),
    35: (("wytepienia", "wytępienia"),),
    36: (("ta wykrywa", "ta wygrywa"),),
    37: (("wyteżają wzrok", "wytężają wzrok"),),
}


def _raw_ocr_pages() -> tuple[dict[str, Any], dict[int, str], dict[int, dict[str, Any]]]:
    checkpoint = read_json(CHECKPOINT_PATH)
    ocr_run = checkpoint.get("ocrRun") or {}
    if ocr_run.get("status") != "complete" or ocr_run.get("model") != "mistral-ocr-4-1":
        raise ValueError("Pinned Sedlaczek OCR run is not complete")
    pages: dict[int, str] = {}
    items: dict[int, dict[str, Any]] = {}
    for item in ocr_run.get("items") or []:
        match = re.fullmatch(r"view-(\d{4})\.(?:jpg|png)", str(item.get("sourceImage") or ""))
        if not match or item.get("status") != "complete":
            continue
        view = int(match.group(1))
        path = ROOT / str(item.get("artifactRelativePath") or "")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != item.get("responseSha256"):
            raise ValueError(f"Pinned OCR response hash mismatch for view {view}")
        response = json.loads(payload)
        response_pages = response.get("pages") or []
        if len(response_pages) != 1 or not isinstance(response_pages[0].get("markdown"), str):
            raise ValueError(f"Unexpected OCR response shape for view {view}")
        pages[view] = response_pages[0]["markdown"]
        items[view] = item
    approved_count = int(ocr_run.get("approvedViewCount") or 0)
    if len(pages) != approved_count or approved_count != 34:
        raise ValueError(f"Expected 34 pinned OCR pages, found {len(pages)}")
    return checkpoint, pages, items


def source_revision(items: dict[int, dict[str, Any]]) -> str:
    payload = [
        {
            "view": view,
            "sourceImageSha256": item.get("sourceImageSha256"),
            "responseSha256": item.get("responseSha256"),
            "model": item.get("model"),
            "recipeVersion": item.get("recipeVersion"),
        }
        for view, item in sorted(items.items())
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _one_match(pattern: str, text: str, label: str) -> re.Match[str]:
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"{label}: expected one match for {pattern!r}, found {len(matches)}")
    return matches[0]


def clean_ocr_body(raw: str, number: int) -> str:
    raw = re.sub(r"^\s*\d{1,3}\s*$", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"^#{1,6}\s*", "", raw, flags=re.MULTILINE)
    raw = raw.replace("*", "")
    raw = re.sub(r"(?<=[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ])-\s*\n\s*\n?\s*(?=[a-ząćęłńóśźż])", "", raw)
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", raw):
        value = " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
        if value:
            paragraphs.append(value)
    body = "\n\n".join(paragraphs)
    body = re.sub(r"(?<=[\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ,;:])\n\n(?=[a-ząćęłńóśźż])", " ", body)
    body = re.sub(r"\s+([,.;:!?])", r"\1", body).strip()
    body = re.sub(r"^\d+[.)]\s+", "", body)
    for before, after in FACSIMILE_CONFIRMED_CORRECTIONS.get(number, ()):
        if body.count(before) != 1:
            raise ValueError(f"Candidate {number}: correction input occurs {body.count(before)} times: {before!r}")
        body = body.replace(before, after)
    if not body:
        raise ValueError(f"Candidate {number}: empty source body")
    return body


def extract_candidate(number: int, pages: dict[int, str]) -> tuple[str, str]:
    span = REVIEWED_SPANS[number]
    missing = [view for view in range(span.start_view, span.end_view + 1) if view not in pages]
    if missing:
        raise ValueError(f"Candidate {number}: missing OCR views {missing}")
    window = "\n\n".join(pages[view] for view in range(span.start_view, span.end_view + 1))
    start = _one_match(span.start_pattern, window, f"candidate {number} start")
    begin = start.start() if span.include_start else start.end()
    if span.end_pattern is None:
        end = len(window)
    else:
        matches = list(re.finditer(span.end_pattern, window[begin:], flags=re.MULTILINE))
        if len(matches) != 1:
            raise ValueError(
                f"candidate {number} end: expected one match for {span.end_pattern!r}, found {len(matches)}"
            )
        end = begin + matches[0].start()
    raw = window[begin:end]
    for pattern in span.excluded_patterns:
        raw, count = re.subn(pattern, "", raw, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"Candidate {number}: exclusion {pattern!r} matched {count} times")
    raw_hash = hashlib.sha256((raw.strip() + "\n").encode("utf-8")).hexdigest()
    return clean_ocr_body(raw, number), raw_hash


def build_import() -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any], str]], dict[str, Any]]:
    report = read_json(REPORT_PATH)
    candidates = report.get("candidates") or []
    if [int(item["number"]) for item in candidates] != list(range(1, 41)):
        raise ValueError("Candidate report no longer contains the pinned 1-40 sequence")
    if set(REVIEWED_SPANS) | set(REJECTED_REASONS) != set(range(1, 41)):
        raise ValueError("Every candidate must have exactly one reviewed decision")
    if set(REVIEWED_SPANS) & set(REJECTED_REASONS):
        raise ValueError("Accepted and rejected candidate sets overlap")

    checkpoint, pages, items = _raw_ocr_pages()
    revision = source_revision(items)
    outputs: list[tuple[Path, dict[str, Any], str]] = []
    activities = []
    source_bodies: dict[str, int] = {}
    by_number = {int(item["number"]): item for item in candidates}
    for number, span in sorted(REVIEWED_SPANS.items()):
        candidate = by_number[number]
        source_body, raw_hash = extract_candidate(number, pages)
        normalized_hash = hashlib.sha256(" ".join(source_body.split()).encode("utf-8")).hexdigest()
        if normalized_hash in source_bodies:
            raise ValueError(f"Exact body duplicate: candidates {source_bodies[normalized_hash]} and {number}")
        source_bodies[normalized_hash] = number
        activity_id = f"{PREFIX}-{number:03d}"
        printed_pages = list(range(span.start_view - 1, span.end_view))
        pdf_pages = list(range(span.start_view, span.end_view + 1))
        facsimile_url = f"{PDF_URL}#page={span.start_view}"
        notes = []
        if span.excluded_patterns:
            notes.append(
                "*Zakres transkrypcji: przypis lub tekst redakcyjny poza procedurą pominięto; dokładne wyłączenia zapisano w raporcie ekstrakcji.*"
            )
        source_note = (
            "---\n\n"
            + ("\n\n".join(notes) + "\n\n" if notes else "")
            + f"*Źródło skanu: [Śląska Biblioteka Cyfrowa]({SOURCE_URL}), oznaczenie „domena publiczna”. "
            + f"[Zobacz PDF — strona {span.start_view}]({facsimile_url}).*"
        )
        body = f"{source_body}\n\n{source_note}"
        metadata: dict[str, Any] = {
            "id": activity_id,
            "kinds": ["game"],
            "sourceId": SOURCE_ID,
            "originalLanguage": "pl",
            "title": str(candidate["titleRaw"]),
            "traits": [],
            "section": str(candidate["section"]),
            "printedPages": printed_pages,
            "pdfPages": pdf_pages,
            "transcriptionStatus": "mistral-ocr-unreviewed",
            "safetyStatus": "historical-unreviewed",
            "rightsStatus": "public-domain",
            "sourceUrl": SOURCE_URL,
            "digitalEditionUrl": SOURCE_URL,
            "facsimileUrl": facsimile_url,
            "sourceRevision": f"sha256:{revision}",
            "participantScales": ["unknown"],
            "participantScaleBasis": "unknown",
        }
        if span.excluded_patterns:
            metadata["contentOmissions"] = ["footnote-or-editorial-text-outside-record-scope"]
        if number in FACSIMILE_CONFIRMED_CORRECTIONS:
            metadata["transcriptionNotes"] = ["facsimile-confirmed OCR corrections applied reproducibly"]
        metadata["sourceHash"] = source_hash(str(candidate["titleRaw"]), body)
        outputs.append((VAULT / "activities" / f"{activity_id}.md", metadata, body))
        activity: dict[str, Any] = {
            "id": activity_id,
            "candidateNumber": number,
            "title": str(candidate["titleRaw"]),
            "startView": span.start_view,
            "endView": span.end_view,
            "startPattern": span.start_pattern,
            "endPattern": span.end_pattern,
            "pdfPages": pdf_pages,
            "printedPages": printed_pages,
            "rawSourceBlockSha256": raw_hash,
            "publishedSourceHash": metadata["sourceHash"],
        }
        if span.excluded_patterns:
            activity["excludedPatterns"] = list(span.excluded_patterns)
        if number in FACSIMILE_CONFIRMED_CORRECTIONS:
            activity["facsimileConfirmedCorrections"] = [
                {"ocr": before, "source": after}
                for before, after in FACSIMILE_CONFIRMED_CORRECTIONS[number]
            ]
        activities.append(activity)

    extraction = {
        "schemaVersion": 1,
        "sourceId": SOURCE_ID,
        "sourceSha256": revision,
        "parserVersion": "sedlaczek-1921-reviewed-character-spans-v1",
        "reviewRequired": False,
        "activityCount": len(activities),
        "wholeSourceCopiedToRepository": False,
        "selection": {
            "candidateCount": len(candidates),
            "acceptedGameCount": len(activities),
            "rejectedCount": len(REJECTED_REASONS),
            "basis": "bounded, executable game or competitive exercise verified against Mistral OCR and rendered facsimile pages",
            "rejectedCandidates": [
                {"candidateNumber": number, "reason": reason}
                for number, reason in sorted(REJECTED_REASONS.items())
            ],
        },
        "transcriptionEvidence": {
            "sourceStatement": "Pinned Mistral OCR responses and rendered pages stored in gitignored repository artifacts on Group Storage.",
            "sourceLocation": PDF_URL,
            "ocrModel": checkpoint["ocrRun"]["model"],
            "ocrRecipeVersion": "mistral-ocr-image-v1",
            "ocrViewCount": len(items),
            "billingMode": checkpoint["ocrRun"].get("billingMode"),
            "billedCostUsd": checkpoint["ocrRun"].get("billedCostUsd"),
            "referenceCostUsd": sum(float(item.get("referenceCostUsd") or 0) for item in items.values()),
            "deterministicNormalization": [
                "select pinned character spans from exact OCR responses",
                "omit the activity heading represented in frontmatter",
                "omit isolated printed-page numbers and pinned footnote or editorial ranges",
                "join OCR soft wraps and dehyphenate lowercase word continuations",
                "apply only facsimile-confirmed OCR corrections listed per activity",
                "preserve source spelling and wording without lexical modernization",
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
        "author": "Stanisław Sedlaczek",
        "title": "Szkoła harcerza",
        "year": 1921,
        "edition": "wydanie 3",
        "publicationPlace": "Warszawa",
        "publisher": "Księgarnia J. Lisowskiej",
        "originalLanguage": "pl",
        "rightsStatus": "public-domain",
        "rightsStatement": "„domena publiczna” — oznaczenie konkretnego obiektu w Śląskiej Bibliotece Cyfrowej",
        "rightsEvidenceUrl": SOURCE_URL,
        "rightsEvidence": rights_evidence,
        "sourceUrl": SOURCE_URL,
        "digitalEditionUrl": SOURCE_URL,
        "pdfUrl": PDF_URL,
        "accessedOn": "2026-09-07",
        "sourceRevision": f"sha256:{revision}",
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
                "shc-002", "shc-003", "shc-016", "shc-024", "shc-035", "shc-040"
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
        "# Szkoła harcerza\n\n"
        "Źródło bibliograficzne dla gier wyodrębnionych z obiektu Śląskiej Biblioteki "
        "Cyfrowej jawnie oznaczonego jako domena publiczna. PDF, odpowiedzi OCR i "
        "renderowane strony są przechowywane w ignorowanym przez Git katalogu "
        "`artifacts/` przy repozytorium na Group Storage; publikowany korpus zawiera "
        "tylko wybrane, udokumentowane rekordy.\n\n"
        f"- [Rekord cyfrowy w ŚBC]({SOURCE_URL})\n"
        f"- [PDF wydania]({PDF_URL})\n"
    )
    dump_markdown(VAULT / "sources" / f"{SOURCE_ID}.md", source_metadata, source_body)
    write_json(ROOT / "data" / "reports" / f"{SOURCE_ID}-extraction.json", extraction)

    report = read_json(REPORT_PATH)
    accepted = set(REVIEWED_SPANS)
    for candidate in report["candidates"]:
        number = int(candidate["number"])
        candidate["recordReviewStatus"] = "accepted-game" if number in accepted else "rejected-not-game"
        if number in REJECTED_REASONS:
            candidate["recordReviewReason"] = REJECTED_REASONS[number]
        else:
            candidate.pop("recordReviewReason", None)
            span = REVIEWED_SPANS[number]
            candidate["reviewedStartView"] = span.start_view
            candidate["reviewedEndView"] = span.end_view
            candidate["reviewedStartPattern"] = span.start_pattern
            candidate["reviewedEndPattern"] = span.end_pattern
    expected_ids = sorted(item["id"] for item in extraction["activities"])
    translation_path = ROOT / "data" / "reports" / f"{SOURCE_ID}-translation-pl-en.json"
    translation_complete = False
    if translation_path.is_file():
        translation = read_json(translation_path)
        translation_complete = (
            translation.get("status") == "complete"
            and translation.get("selectedActivityIds") == expected_ids
            and translation.get("completedActivityIds") == expected_ids
            and translation.get("pendingActivityIds") == []
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
