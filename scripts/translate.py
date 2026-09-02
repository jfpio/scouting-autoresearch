#!/usr/bin/env python3
"""Create resumable Polish-to-English machine translations with Mistral."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from threading import Lock

from common import ROOT, VAULT, dump_markdown, load_markdown, source_hash, write_json


API_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_MODEL = "mistral-medium-2604"
PROMPT_VERSION = "translation-pl-en-v1"
OUTPUT_DIR = VAULT / "translations" / "en"
ERROR_REPORT = ROOT / "data" / "reports" / "translation-errors.json"
print_lock = Lock()


SYSTEM_PROMPT = """You translate historical Polish scouting texts into clear, faithful English.
Return one JSON object with exactly these keys: title, body, traits, section.
Preserve Markdown structure, lists, emphasis, image URLs, HTML, numbers, and source references.
Translate image alt text when useful, but never alter a URL. Preserve the historical meaning and tone;
do not modernize instructions, add safety advice, summarize, censor, or invent missing facts.
Translate the supplied traits as short noun phrases. Output valid JSON only."""


def load_secret() -> str:
    secret_path = Path.home() / ".secrets" / "mistral.env"
    values: dict[str, str] = {}
    if secret_path.exists():
        for raw_line in secret_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    key = os.environ.get("MISTRAL_API_KEY") or values.get("MISTRAL_API_KEY")
    if not key:
        raise SystemExit("MISTRAL_API_KEY is missing from the environment and ~/.secrets/mistral.env")
    return key


def parse_json_content(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    payload = json.loads(content)
    required = {"title", "body", "traits", "section"}
    if set(payload) != required:
        raise ValueError(f"Translation keys differ from {sorted(required)}")
    if not isinstance(payload["title"], str) or not payload["title"].strip():
        raise ValueError("Empty translated title")
    if not isinstance(payload["body"], str) or not payload["body"].strip():
        raise ValueError("Empty translated body")
    if not isinstance(payload["traits"], list) or not all(isinstance(item, str) for item in payload["traits"]):
        raise ValueError("Translated traits are not a list of strings")
    if not isinstance(payload["section"], str) or not payload["section"].strip():
        raise ValueError("Empty translated section")
    return payload


def request_translation(api_key: str, model: str, activity_id: str, metadata: dict, body: str) -> tuple[dict, str]:
    user_payload = {
        "id": activity_id,
        "title": metadata["title"],
        "traits": metadata.get("traits", []),
        "section": metadata.get("section", ""),
        "body": body,
    }
    request_body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 16384,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
            choice = result["choices"][0]
            if choice.get("finish_reason") not in ("stop", None):
                raise ValueError(f"Unexpected finish reason: {choice.get('finish_reason')}")
            translated = parse_json_content(choice["message"]["content"])
            return translated, result.get("model", model)
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", errors="replace")[:800]
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 5:
                raise RuntimeError(f"Mistral HTTP {error.code}: {message}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 5:
                raise RuntimeError(f"Mistral request failed: {error}") from error
        time.sleep(min(30, (2**attempt) + random.random()))
    raise RuntimeError("Translation retries exhausted")


def current_translation(path: Path, expected_hash: str) -> bool:
    if not path.exists():
        return False
    try:
        metadata, body = load_markdown(path)
    except (ValueError, OSError):
        return False
    return metadata.get("sourceHash") == expected_hash and metadata.get("status") == "machine-translation" and bool(body)


def translate_one(api_key: str, model: str, path: Path) -> tuple[str, str | None]:
    metadata, body = load_markdown(path)
    activity_id = metadata["id"]
    expected_hash = source_hash(metadata["title"], body)
    output_path = OUTPUT_DIR / f"{activity_id}.md"
    if current_translation(output_path, expected_hash):
        return activity_id, None
    translated, actual_model = request_translation(api_key, model, activity_id, metadata, body)
    if len(translated["traits"]) != len(metadata.get("traits", [])):
        raise ValueError(
            f"Translation changed trait count for {activity_id}: "
            f"{len(metadata.get('traits', []))} -> {len(translated['traits'])}"
        )
    translated_meta = {
        "activityId": activity_id,
        "locale": "en",
        "title": translated["title"].strip(),
        "traits": [item.strip() for item in translated["traits"] if item.strip()],
        "section": translated["section"].strip(),
        "modelRequested": model,
        "model": actual_model,
        "promptVersion": PROMPT_VERSION,
        "generatedAt": date.today().isoformat(),
        "sourceHash": expected_hash,
        "status": "machine-translation",
    }
    dump_markdown(output_path, translated_meta, translated["body"])
    with print_lock:
        print(f"translated {activity_id} ({actual_model})", flush=True)
    return activity_id, actual_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("MISTRAL_TRANSLATION_MODEL", DEFAULT_MODEL))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="*")
    args = parser.parse_args()
    paths = sorted((VAULT / "activities").glob("*.md"))
    if args.ids:
        wanted = set(args.ids)
        paths = [path for path in paths if path.stem in wanted]
    if args.limit:
        paths = paths[: args.limit]
    if not paths:
        raise SystemExit("No activity records selected")
    api_key = load_secret()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(translate_one, api_key, args.model, path): path for path in paths}
        for future in concurrent.futures.as_completed(futures):
            path = futures[future]
            try:
                future.result()
                completed += 1
            except Exception as error:  # keep the batch resumable
                errors.append({"id": path.stem, "error": str(error)})
                with print_lock:
                    print(f"ERROR {path.stem}: {error}", flush=True)
    write_json(
        ERROR_REPORT,
        {"modelRequested": args.model, "selected": len(paths), "completed": completed, "errors": errors},
    )
    if errors:
        raise SystemExit(f"{len(errors)} translations failed; rerun to resume")
    print(f"Translations current: {completed}/{len(paths)}")


if __name__ == "__main__":
    main()
