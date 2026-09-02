#!/usr/bin/env python3
"""Deterministically import the two maintained digital editions into the vault."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path

from common import ROOT, VAULT, dump_markdown, read_json, sha256_bytes, source_hash, write_json


DEFAULT_HWP = Path("/Users/janpiotrowski/Projekty/harcerz-w-polu")
DEFAULT_PW = Path("/Users/janpiotrowski/Projekty/proby-wodzow")
LOCK_PATH = ROOT / "imports.lock.json"


SOURCES = {
    "hwp-1946": {
        "author": "Zygmunt Wyrobek",
        "title": "Harcerz w polu: zabawy i gry terenowe",
        "year": 1946,
        "edition": "Wydanie piąte",
        "publicationPlace": "Kraków",
        "publisher": "Wydawnictwo Zakładu Narodowego imienia Ossolińskich",
        "originalLanguage": "pl",
        "rightsStatus": "public-domain",
        "rightsStatement": "„Domena publiczna” — oznaczenie rekordu Polony",
        "rightsEvidenceUrl": "https://polona.pl/item-view/0782bd3a-4d20-41be-86f8-bcdfc65555c5?page=0",
        "sourceUrl": "https://polona.pl/item-view/0782bd3a-4d20-41be-86f8-bcdfc65555c5?page=0",
        "digitalEditionUrl": "https://jfpio.github.io/harcerz-w-polu/",
        "pdfUrl": "https://jfpio.github.io/harcerz-w-polu/book/harcerz-w-polu.pdf",
        "accessedOn": "2026-08-31",
    },
    "pw-1935": {
        "author": "L. Ungeheuer",
        "title": "Próby wodzów",
        "year": 1935,
        "publicationPlace": "Lwów",
        "publisher": "Skaut",
        "originalLanguage": "pl",
        "rightsStatus": "public-domain",
        "rightsStatement": "„Domena Publiczna” — oznaczenie rekordu Polony",
        "rightsEvidenceUrl": "https://polona.pl/item-view/55e3bbc2-7804-485e-88c7-e9c7ebf672bf?page=0",
        "sourceUrl": "https://polona.pl/item-view/55e3bbc2-7804-485e-88c7-e9c7ebf672bf?page=0",
        "digitalEditionUrl": "https://jfpio.github.io/proby-wodzow/",
        "pdfUrl": "https://jfpio.github.io/proby-wodzow/book/proby-wodzow.pdf",
        "accessedOn": "2026-09-02",
    },
}


def git_commit(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def selected_tree_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    common = Path(os.path.commonpath([str(path) for path in paths]))
    if common.is_file():
        common = common.parent
    for path in sorted(paths, key=lambda value: str(value)):
        digest.update(str(path.relative_to(common)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def clean_game_body(text: str) -> str:
    if text.startswith("---\n"):
        _, text = text[4:].split("\n---\n", 1)
    text = re.sub(
        r"^\s*> \*\*Transkrypcja OCR[^\n]*\n(?:>[^\n]*\n)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\n*<p class=\"source-note\">.*?</p>\s*$", "", text, flags=re.DOTALL)
    text = text.replace("](/harcerz-w-polu/", "](https://jfpio.github.io/harcerz-w-polu/")
    return text.strip()


def base_activity(
    *,
    activity_id: str,
    kinds: list[str],
    source_id: str,
    title: str,
    traits: list[str],
    section: str,
    printed_pages: list[int],
    pdf_pages: list[int],
    transcription_status: str,
    source_commit: str,
    body: str,
) -> dict:
    source = SOURCES[source_id]
    return {
        "id": activity_id,
        "kinds": kinds,
        "sourceId": source_id,
        "sourceCommit": source_commit,
        "originalLanguage": "pl",
        "title": title,
        "traits": traits,
        "section": section,
        "printedPages": printed_pages,
        "pdfPages": pdf_pages,
        "transcriptionStatus": transcription_status,
        "safetyStatus": "historical-unreviewed",
        "rightsStatus": "public-domain",
        "sourceUrl": source["sourceUrl"],
        "digitalEditionUrl": source["digitalEditionUrl"],
        "sourceHash": source_hash(title, body),
    }


def import_hwp(root: Path, commit: str) -> tuple[list[Path], int]:
    index_path = root / "data" / "ocr" / "games.json"
    games = read_json(index_path)
    selected = [index_path]
    for game in games:
        activity_id = f"hwp-{int(game['number']):03d}"
        markdown_path = root / "src" / "content" / "docs" / f"{game['route']}.md"
        selected.append(markdown_path)
        body = clean_game_body(markdown_path.read_text(encoding="utf-8"))
        metadata = base_activity(
            activity_id=activity_id,
            kinds=["game"],
            source_id="hwp-1946",
            title=game["title"],
            traits=[],
            section=game["section"],
            printed_pages=[int(value) for value in game["printedPages"]],
            pdf_pages=[int(value) for value in game["pdfPages"]],
            transcription_status="ocr-beta",
            source_commit=commit,
            body=body,
        )
        metadata["forOlderScouts"] = bool(game.get("forOlderScouts", False))
        dump_markdown(VAULT / "activities" / f"{activity_id}.md", metadata, body)
    return selected, len(games)


def import_pw(root: Path, commit: str) -> tuple[list[Path], int]:
    index_path = root / "data" / "trials.json"
    payload = read_json(index_path)
    trials = payload["trials"]
    for trial in trials:
        activity_id = f"pw-{int(trial['number']):03d}"
        body = trial["text"].strip()
        metadata = base_activity(
            activity_id=activity_id,
            kinds=["trial"],
            source_id="pw-1935",
            title=trial["title"],
            traits=list(trial.get("traits", [])),
            section="Próby dzielności",
            printed_pages=[int(value) for value in trial["printedPages"]],
            pdf_pages=[int(value) for value in trial["pdfPages"]],
            transcription_status=trial.get("status", "ocr-beta"),
            source_commit=commit,
            body=body,
        )
        metadata["traitCategories"] = list(trial.get("traitCategories", []))
        metadata["sourceNumbering"] = trial.get("numbering", "editorial")
        dump_markdown(VAULT / "activities" / f"{activity_id}.md", metadata, body)
    return [index_path], len(trials)


def write_source_records(commits: dict[str, str]) -> None:
    for source_id, source in SOURCES.items():
        metadata = {"id": source_id, **source, "sourceCommit": commits[source_id]}
        body = (
            f"# {source['title']}\n\n"
            f"Źródło bibliograficzne dla importowanych aktywności. Pełny skan nie jest kopiowany do tego repozytorium.\n\n"
            f"- [Rekord i dowód statusu prawnego w Polonie]({source['sourceUrl']})\n"
            f"- [Niezależne wydanie cyfrowe]({source['digitalEditionUrl']})\n"
        )
        dump_markdown(VAULT / "sources" / f"{source_id}.md", metadata, body)


def clean_stale_files() -> None:
    activity_dir = VAULT / "activities"
    activity_dir.mkdir(parents=True, exist_ok=True)
    for path in activity_dir.glob("*.md"):
        if re.fullmatch(r"(?:hwp|pw)-\d{3}\.md", path.name):
            path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harcerz", type=Path, default=DEFAULT_HWP)
    parser.add_argument("--proby", type=Path, default=DEFAULT_PW)
    args = parser.parse_args()
    for root in (args.harcerz, args.proby):
        if not root.is_dir():
            raise SystemExit(f"Source repository does not exist: {root}")

    previous = read_json(LOCK_PATH) if LOCK_PATH.exists() else {}
    imported_at = previous.get("importedAt", date.today().isoformat())
    hwp_commit = git_commit(args.harcerz)
    pw_commit = git_commit(args.proby)
    clean_stale_files()
    hwp_files, hwp_count = import_hwp(args.harcerz, hwp_commit)
    pw_files, pw_count = import_pw(args.proby, pw_commit)
    commits = {"hwp-1946": hwp_commit, "pw-1935": pw_commit}
    write_source_records(commits)

    lock = {
        "schemaVersion": 1,
        "importedAt": imported_at,
        "activityCount": hwp_count + pw_count,
        "sources": [
            {
                "id": "hwp-1946",
                "repository": "https://github.com/jfpio/harcerz-w-polu.git",
                "commit": hwp_commit,
                "selectedContentSha256": selected_tree_hash(hwp_files),
                "indexSha256": sha256_bytes(hwp_files[0].read_bytes()),
                "activityCount": hwp_count,
            },
            {
                "id": "pw-1935",
                "repository": "https://github.com/jfpio/proby-wodzow.git",
                "commit": pw_commit,
                "selectedContentSha256": selected_tree_hash(pw_files),
                "indexSha256": sha256_bytes(pw_files[0].read_bytes()),
                "activityCount": pw_count,
            },
        ],
    }
    write_json(LOCK_PATH, lock)
    print(f"Imported {hwp_count} games and {pw_count} trials ({hwp_count + pw_count} total).")


if __name__ == "__main__":
    main()
