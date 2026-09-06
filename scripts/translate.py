#!/usr/bin/env python3
"""Create resumable Polish/English machine-translation overlays with Mistral."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from functools import cache
from pathlib import Path
from typing import Any

from common import ROOT, VAULT, dump_markdown, load_markdown, read_json, source_hash, write_json


API_URL = "https://api.mistral.ai/v1/chat/completions"
MODELS_API_URL = "https://api.mistral.ai/v1/models"
DEFAULT_MODEL = "mistral-large-2512"
CHECKPOINT_DIR = ROOT / "data" / "checkpoints" / "translations"
REPORT_DIR = ROOT / "data" / "reports"
TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}
PRICE_SOURCE = "https://docs.mistral.ai/inference/pricing"
PRICE_ACCESSED_ON = "2026-09-04"
MIN_OUTPUT_TOKENS = 512
MAX_OUTPUT_TOKENS = 8192
MODEL_PRICING = {
    "ministral-14b-2512": {"input": 0.2, "output": 0.2},
    "mistral-large-2512": {"input": 0.5, "output": 1.5},
    "mistral-medium-2604": {"input": 1.5, "output": 7.5},
    "mistral-small-2603": {"input": 0.15, "output": 0.6},
}
DEFAULT_BILLING_MODE = "education-credit"


SYSTEM_PROMPTS = {
    ("pl", "en"): """You translate historical Polish scouting texts into clear, faithful English.
Return one JSON object with exactly these keys: title, body, traits, section.
Preserve Markdown structure, lists, emphasis, image URLs, HTML, numbers, and source references.
Translate image alt text when useful, but never alter a URL. Preserve the historical meaning and tone;
do not modernize instructions, add safety advice, summarize, censor, or invent missing facts.
Translate the supplied traits as short noun phrases. Output valid JSON only.""",
    ("en", "pl"): """Translate historical English scouting texts into clear, faithful Polish.
Return one JSON object with exactly these keys: title, body, traits, section.
Preserve Markdown structure, lists, emphasis, image URLs, HTML, numbers, and source references.
Translate image alt text when useful, but never alter a URL. Preserve the historical meaning and tone;
do not modernize instructions, add safety advice, summarize, censor, or invent missing facts.
Translate the supplied traits as short noun phrases in exactly the same order and count; if traits is
empty, return an empty array and do not infer traits. Preserve every numeral and unit exactly: do not
convert units, clock notation, currencies, add equivalents, dates, quantities, or explanatory numbers;
retain the original digits (for example, keep the digit 4 in 4 p.m. rather than converting it to 16:00
or spelling it out). Keep number words as number words and digits as digits; never turn English "one"
into the digit 1 or an English digit into a Polish number word. Preserve historical gender and age
terms: translate boy, scout, he, and his with
grammatically masculine Polish forms and never expand them into paired feminine-and-masculine forms.
If the source record contains no girl or girls, do not use any Polish word beginning with harcerk-.
Preserve paragraph breaks with JSON newline escapes; never replace them with visible symbols such as ⏎.
Output valid JSON only.""",
}


def prompt_version(source_locale: str, target_locale: str) -> str:
    version = "v6" if (source_locale, target_locale) == ("en", "pl") else "v1"
    return f"translation-{source_locale}-{target_locale}-{version}"


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


def translation_fidelity_checks(
    metadata: dict[str, Any],
    body: str,
    translated: dict[str, Any],
) -> dict[str, Any]:
    source_urls = Counter(re.findall(r"https?://[^\s)]+", body))
    translated_urls = Counter(re.findall(r"https?://[^\s)]+", translated["body"]))
    number_pattern = r"(?<!\w)(?:\d{1,3}(?:[ ,.\u00a0]\d{3})+|\d+(?:[.,]\d+)?)"

    def normalized_numbers(text: str, locale: str) -> Counter[str]:
        normalized: list[str] = []
        for value in re.findall(number_pattern, text):
            compact = value.replace(" ", "").replace("\u00a0", "")
            if locale == "en" and re.fullmatch(r"\d{1,3}(?:,\d{3})+", compact):
                compact = compact.replace(",", "")
            elif locale == "pl" and re.fullmatch(r"\d{1,3}(?:[.]\d{3})+", compact):
                compact = compact.replace(".", "")
            else:
                compact = compact.replace(",", ".")
            normalized.append(compact)
        return Counter(normalized)

    source_locale = str(metadata.get("originalLanguage") or "en")
    target_locale = translation_target(source_locale)
    source_numbers = normalized_numbers(body, source_locale)
    translated_numbers = normalized_numbers(translated["body"], target_locale)
    body_ratio = len(translated["body"].strip()) / max(1, len(body.strip()))
    checks = {
        "nonemptyFields": all(
            isinstance(translated.get(field), str) and bool(translated[field].strip())
            for field in ("title", "section", "body")
        ),
        "traitCountPreserved": len(translated.get("traits") or [])
        == len(metadata.get("traits") or []),
        "urlsPreserved": source_urls == translated_urls,
        "numbersPreserved": source_numbers == translated_numbers,
        "paragraphBreaksPreserved": len(re.findall(r"\n\s*\n", body))
        == len(re.findall(r"\n\s*\n", translated["body"])),
        "noLiteralLineBreakMarkers": not any(
            marker in translated["body"] for marker in ("⏎", "↵", "\\n")
        ),
        "noInclusiveGenderExpansion": not re.search(
            r"harcer(?:ka|ki|ek)\s+(?:lub|i|albo)\s+harcerz|"
            r"harcerz\w*\s+(?:lub|i|albo)\s+harcer(?:ka|ki|ek)",
            translated["body"],
            flags=re.IGNORECASE,
        ),
        "noInventedFemaleScout": bool(re.search(r"\bgirls?\b", body, flags=re.IGNORECASE))
        or not re.search(r"\bharcerk", translated["body"], flags=re.IGNORECASE),
        "bodyLengthRatioWithinBounds": 0.55 <= body_ratio <= 1.8,
    }
    return {
        **checks,
        "bodyLengthRatio": round(body_ratio, 4),
        "automaticPass": all(checks.values()),
    }


class TransientTranslationError(RuntimeError):
    def __init__(
        self,
        reason: str,
        retry_at: datetime,
        diagnostics: dict[str, Any] | None = None,
    ):
        super().__init__(reason)
        self.reason = reason
        self.retry_at = retry_at
        self.diagnostics = diagnostics or {}


class PermanentTranslationError(RuntimeError):
    def __init__(self, reason: str, diagnostics: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.diagnostics = diagnostics or {}


def available_model_ids(api_key: str) -> set[str]:
    request = urllib.request.Request(
        MODELS_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        diagnostics = safe_http_diagnostics(error)
        if error.code in TRANSIENT_HTTP_CODES:
            raise TransientTranslationError(
                f"transient-model-access-http-{error.code}",
                retry_at_from_headers(error.headers),
                diagnostics,
            ) from error
        raise PermanentTranslationError(
            f"permanent-model-access-http-{error.code}", diagnostics
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise TransientTranslationError(
            "transient-model-access-network-error",
            datetime.now(UTC) + timedelta(hours=1),
            {"transport": "network"},
        ) from error
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise PermanentTranslationError(
            "invalid-model-access-response", {"responseShape": "missing-data-list"}
        )
    return {
        str(item["id"])
        for item in data
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
    }


def ensure_models_available(api_key: str, models: list[str] | set[str]) -> set[str]:
    requested = {str(model) for model in models}
    available = available_model_ids(api_key)
    missing = sorted(requested - available)
    if missing:
        raise PermanentTranslationError(
            "models-not-available-for-account",
            {"missingModels": missing},
        )
    return available


def retry_at_from_headers(headers: Any, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    fallback = current + timedelta(hours=1)
    value = headers.get("Retry-After") if headers is not None else None
    if not value:
        return fallback
    try:
        candidate = current + timedelta(seconds=max(0, int(value)))
    except (TypeError, ValueError):
        try:
            candidate = parsedate_to_datetime(str(value))
            if candidate.tzinfo is None:
                candidate = candidate.replace(tzinfo=UTC)
            candidate = candidate.astimezone(UTC)
        except (TypeError, ValueError, OverflowError):
            return fallback
    return max(current, candidate)


def safe_http_diagnostics(error: urllib.error.HTTPError) -> dict[str, Any]:
    """Keep useful provider diagnostics without persisting credentials or response text."""
    diagnostics: dict[str, Any] = {"httpStatus": int(error.code)}
    safe_headers: dict[str, str] = {}
    if error.headers is not None:
        for raw_name, raw_value in error.headers.items():
            name = str(raw_name).lower()
            if name in {"retry-after", "x-request-id", "request-id"} or name.startswith("x-ratelimit-"):
                safe_headers[name] = str(raw_value).strip()[:200]
    if safe_headers:
        diagnostics["headers"] = dict(sorted(safe_headers.items()))
    try:
        payload = json.loads(error.read(16_384).decode("utf-8", errors="replace"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict):
        safe_error: dict[str, str | int | float | bool | None] = {}
        for key in ("type", "code", "param"):
            value = payload.get(key)
            if value is None or isinstance(value, (str, int, float, bool)):
                if value is None or len(str(value)) <= 200:
                    safe_error[key] = value
        if safe_error:
            diagnostics["error"] = safe_error
    return diagnostics


def model_pricing(model: str) -> dict[str, float]:
    try:
        return MODEL_PRICING[model]
    except KeyError as error:
        raise ValueError(f"No pinned reference pricing for translation model {model}") from error


def translation_output_token_budget(user_payload: dict[str, Any]) -> int:
    """Size output conservatively without reserving the old fixed 16k tokens per record."""
    payload_bytes = len(json.dumps(user_payload, ensure_ascii=False).encode("utf-8"))
    estimated_upper_bound = math.ceil(payload_bytes / 2) + 256
    return min(MAX_OUTPUT_TOKENS, max(MIN_OUTPUT_TOKENS, estimated_upper_bound))


def request_reference_cost_upper_bound(
    metadata: dict[str, Any], body: str, model: str
) -> float:
    source_locale = str(metadata["originalLanguage"])
    target_locale = translation_target(source_locale)
    user_payload = {
        "id": metadata["id"],
        "title": metadata["title"],
        "traits": metadata.get("traits", []),
        "section": metadata.get("section", ""),
        "body": body,
    }
    prompt_token_upper_bound = len(
        (
            SYSTEM_PROMPTS[(source_locale, target_locale)]
            + json.dumps(user_payload, ensure_ascii=False)
        ).encode("utf-8")
    )
    output_token_upper_bound = translation_output_token_budget(user_payload)
    pricing = model_pricing(model)
    return round(
        prompt_token_upper_bound * pricing["input"] / 1_000_000
        + output_token_upper_bound * pricing["output"] / 1_000_000,
        8,
    )


def enforce_reference_cost_limit(
    policy: dict[str, Any],
    spent_usd: float,
    metadata: dict[str, Any],
    body: str,
    model: str,
) -> None:
    if policy.get("enforceReferenceCostLimit") is not True:
        return
    limit = float(policy.get("maxReferenceCostUsd", 0))
    if not 0 < limit <= 10:
        raise ValueError("Translation reference-cost limit must be within (0, 10] USD")
    projected = spent_usd + 2 * request_reference_cost_upper_bound(metadata, body, model)
    if projected > limit:
        raise ValueError(
            f"Translation reference-cost limit would be exceeded: {projected:.8f} > {limit:.2f} USD"
        )


def usage_record(
    payload: dict[str, Any],
    model: str = DEFAULT_MODEL,
    *,
    request_max_output_tokens: int | None = None,
    billing_mode: str = DEFAULT_BILLING_MODE,
) -> dict[str, Any]:
    prompt_tokens = int(payload.get("prompt_tokens", 0))
    completion_tokens = int(payload.get("completion_tokens", 0))
    if prompt_tokens <= 0 or completion_tokens <= 0:
        raise ValueError("Mistral response lacks positive prompt/completion token usage")
    pricing = model_pricing(model)
    record = {
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "billedCostUsd": None if billing_mode == "education-credit" else 0,
        "referenceCostUsd": round(
            prompt_tokens * pricing["input"] / 1_000_000
            + completion_tokens * pricing["output"] / 1_000_000,
            8,
        ),
        "billingMode": billing_mode,
        "inputPriceUsdPerMillionTokens": pricing["input"],
        "outputPriceUsdPerMillionTokens": pricing["output"],
        "priceSource": PRICE_SOURCE,
        "priceAccessedOn": PRICE_ACCESSED_ON,
    }
    if request_max_output_tokens is not None:
        record["requestMaxOutputTokens"] = request_max_output_tokens
    return record


def request_translation(
    api_key: str,
    model: str,
    activity_id: str,
    metadata: dict,
    body: str,
    source_locale: str,
    target_locale: str,
    fidelity_feedback: str | None = None,
) -> tuple[dict, str, dict[str, Any]]:
    system_prompt = SYSTEM_PROMPTS.get((source_locale, target_locale))
    if not system_prompt:
        raise ValueError(f"Unsupported translation direction: {source_locale}->{target_locale}")
    user_payload = {
        "id": activity_id,
        "title": metadata["title"],
        "traits": metadata.get("traits", []),
        "section": metadata.get("section", ""),
        "body": body,
    }
    max_output_tokens = translation_output_token_budget(user_payload)
    effective_system_prompt = system_prompt
    if fidelity_feedback:
        effective_system_prompt = f"{system_prompt}\n\n{fidelity_feedback}"
    request_body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max_output_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": effective_system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        diagnostics = safe_http_diagnostics(error)
        if error.code in TRANSIENT_HTTP_CODES:
            raise TransientTranslationError(
                f"transient-http-{error.code}",
                retry_at_from_headers(error.headers),
                diagnostics,
            ) from error
        raise PermanentTranslationError(
            f"permanent-http-{error.code}", diagnostics
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise TransientTranslationError(
            "transient-network-error",
            datetime.now(UTC) + timedelta(hours=1),
            {"transport": "network"},
        ) from error
    choice = result["choices"][0]
    if choice.get("finish_reason") not in ("stop", None):
        raise ValueError(f"Unexpected finish reason: {choice.get('finish_reason')}")
    actual_model = result.get("model")
    if not isinstance(actual_model, str) or not actual_model.strip():
        raise ValueError("Mistral response lacks the actual model identifier")
    translated = parse_json_content(choice["message"]["content"])
    billing_mode = str(
        source_translation_policy(str(metadata["sourceId"])).get("billingMode")
        or DEFAULT_BILLING_MODE
    )
    return translated, actual_model, usage_record(
        result.get("usage") or {},
        model,
        request_max_output_tokens=max_output_tokens,
        billing_mode=billing_mode,
    )


def current_translation(
    path: Path,
    expected_hash: str,
    *,
    expected_locale: str | None = None,
    expected_model: str | None = None,
    expected_prompt: str | None = None,
    expected_reasoning_mode: str | None = None,
    expected_billing_mode: str | None = None,
    usage_required: bool = False,
    request_budget_required: bool = False,
) -> bool:
    if not path.exists():
        return False
    try:
        metadata, body = load_markdown(path)
    except (ValueError, OSError):
        return False
    if not (
        metadata.get("sourceHash") == expected_hash
        and metadata.get("status") == "machine-translation"
        and bool(body)
    ):
        return False
    if expected_locale is not None and metadata.get("locale") != expected_locale:
        return False
    if expected_model is not None and metadata.get("modelRequested") != expected_model:
        return False
    if expected_prompt is not None and metadata.get("promptVersion") != expected_prompt:
        return False
    if expected_reasoning_mode is not None and metadata.get("reasoningMode") != expected_reasoning_mode:
        return False
    if usage_required:
        usage = metadata.get("usage") or {}
        usage_is_current = (
            isinstance(usage.get("promptTokens"), int)
            and usage["promptTokens"] > 0
            and isinstance(usage.get("completionTokens"), int)
            and usage["completionTokens"] > 0
            and usage.get("billedCostUsd") in (0, None)
            and isinstance(usage.get("referenceCostUsd"), (int, float))
            and usage["referenceCostUsd"] >= 0
            and bool(usage.get("priceSource"))
            and bool(usage.get("priceAccessedOn"))
        )
        if request_budget_required:
            budget = usage.get("requestMaxOutputTokens")
            usage_is_current = (
                usage_is_current
                and isinstance(budget, int)
                and MIN_OUTPUT_TOKENS <= budget <= MAX_OUTPUT_TOKENS
            )
        if expected_billing_mode is not None:
            usage_is_current = usage_is_current and usage.get("billingMode") == expected_billing_mode
        return usage_is_current
    return True


def translation_target(source_locale: str) -> str:
    if source_locale == "pl":
        return "en"
    if source_locale == "en":
        return "pl"
    raise ValueError(f"Unsupported source language: {source_locale}")


@cache
def source_translation_policy(source_id: str) -> dict[str, Any]:
    source_path = VAULT / "sources" / f"{source_id}.md"
    if not source_path.exists():
        return {}
    metadata, _ = load_markdown(source_path)
    policy = metadata.get("translationPolicy") or {}
    if not isinstance(policy, dict):
        raise ValueError(f"Source {source_id} has an invalid translation policy")
    return policy


def translation_requirements(metadata: dict[str, Any], model: str) -> dict[str, Any]:
    source_locale = metadata["originalLanguage"]
    target_locale = translation_target(source_locale)
    expected_prompt = prompt_version(source_locale, target_locale)
    source_id = metadata["sourceId"]
    policy = source_translation_policy(source_id)
    if policy:
        if policy.get("targetLocale") != target_locale:
            raise ValueError(f"Source {source_id} translation target differs from its policy")
        if policy.get("modelRequested") != model:
            raise ValueError(
                f"Source {source_id} requires model {policy.get('modelRequested')}, not {model}"
            )
        if policy.get("promptVersion") != expected_prompt:
            raise ValueError(f"Source {source_id} translation prompt differs from its policy")
        if policy.get("billingMode") not in {"experimental-no-charge", "education-credit"}:
            raise ValueError(f"Source {source_id} has an unsupported translation billing mode")
        if policy.get("billingMode") == "education-credit":
            if policy.get("enforceReferenceCostLimit") is not True:
                raise ValueError(f"Source {source_id} must enforce a translation cost limit")
            limit = float(policy.get("maxReferenceCostUsd", 0))
            if not 0 < limit <= 10:
                raise ValueError(f"Source {source_id} translation cost limit must be within (0, 10] USD")
    return {
        "targetLocale": target_locale,
        "expectedModel": policy.get("modelRequested") if policy else None,
        "expectedPrompt": policy.get("promptVersion") if policy else None,
        "expectedReasoningMode": policy.get("reasoningMode") if policy else None,
        "expectedBillingMode": policy.get("billingMode") if policy else None,
        "usageRequired": policy.get("usageRequired") is True,
        "requestBudgetRequired": policy.get("requestBudgetRequired") is True,
    }


def resolved_translation_model(metadata: dict[str, Any], explicit_model: str | None) -> str:
    policy = source_translation_policy(metadata["sourceId"])
    policy_model = policy.get("modelRequested")
    if explicit_model and policy_model and explicit_model != policy_model:
        raise ValueError(
            f"Source {metadata['sourceId']} requires model {policy_model}, not {explicit_model}"
        )
    return str(explicit_model or policy_model or DEFAULT_MODEL)


def translate_one(
    api_key: str,
    model: str,
    path: Path,
) -> tuple[str, str | None, dict[str, Any] | None]:
    metadata, body = load_markdown(path)
    activity_id = metadata["id"]
    source_locale = metadata["originalLanguage"]
    requirements = translation_requirements(metadata, model)
    target_locale = requirements["targetLocale"]
    expected_hash = source_hash(metadata["title"], body)
    output_path = VAULT / "translations" / target_locale / f"{activity_id}.md"
    if current_translation(
        output_path,
        expected_hash,
        expected_locale=target_locale,
        expected_model=requirements["expectedModel"],
        expected_prompt=requirements["expectedPrompt"],
        expected_reasoning_mode=requirements["expectedReasoningMode"],
        expected_billing_mode=requirements["expectedBillingMode"],
        usage_required=requirements["usageRequired"],
        request_budget_required=requirements["requestBudgetRequired"],
    ):
        return activity_id, None, None
    translated, actual_model, usage = request_translation(
        api_key,
        model,
        activity_id,
        metadata,
        body,
        source_locale,
        target_locale,
    )
    fidelity = translation_fidelity_checks(metadata, body, translated)
    if not fidelity["automaticPass"]:
        failed = sorted(key for key, value in fidelity.items() if isinstance(value, bool) and not value)
        exact_numeric_tokens = re.findall(
            r"(?<!\w)(?:\d{1,3}(?:[ ,.\u00a0]\d{3})+|\d+(?:[.,]\d+)?)",
            body,
        )
        feedback = (
            f"The previous candidate failed these fidelity checks: {', '.join(failed)}. "
            f"Return a corrected translation. Preserve this exact ordered list of digit-containing "
            f"tokens in the body, including multiplicity and notation: "
            f"{json.dumps(exact_numeric_tokens, ensure_ascii=False)}. "
            "Do not create any additional digit-containing token."
        )
        corrected, corrected_model, corrected_usage = request_translation(
            api_key,
            model,
            activity_id,
            metadata,
            body,
            source_locale,
            target_locale,
            fidelity_feedback=feedback,
        )
        corrected_fidelity = translation_fidelity_checks(metadata, body, corrected)
        if not corrected_fidelity["automaticPass"]:
            corrected_failed = sorted(
                key
                for key, value in corrected_fidelity.items()
                if isinstance(value, bool) and not value
            )
            raise ValueError(
                f"Translation failed fidelity checks twice for {activity_id}: "
                f"{', '.join(corrected_failed)}"
            )
        translated = corrected
        actual_model = corrected_model
        usage = combine_usage_records([usage, corrected_usage])
    translated_meta = {
        "activityId": activity_id,
        "locale": target_locale,
        "title": translated["title"].strip(),
        "traits": [item.strip() for item in translated["traits"] if item.strip()],
        "section": translated["section"].strip(),
        "modelRequested": model,
        "model": actual_model,
        "promptVersion": prompt_version(source_locale, target_locale),
        "reasoningMode": "disabled",
        "generatedAt": date.today().isoformat(),
        "sourceHash": expected_hash,
        "status": "machine-translation",
        "usage": usage,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dump_markdown(output_path, translated_meta, translated["body"])
    print(f"translated {activity_id} ({actual_model})", flush=True)
    return activity_id, actual_model, usage


def combine_usage_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("Cannot combine an empty usage list")
    first = records[0]
    identity_keys = (
        "billingMode",
        "inputPriceUsdPerMillionTokens",
        "outputPriceUsdPerMillionTokens",
        "priceSource",
        "priceAccessedOn",
    )
    for record in records[1:]:
        if any(record.get(key) != first.get(key) for key in identity_keys):
            raise ValueError("Cannot combine usage records with different billing identities")
    requested = [int(record.get("requestMaxOutputTokens", 0)) for record in records]
    return {
        "promptTokens": sum(int(record["promptTokens"]) for record in records),
        "completionTokens": sum(int(record["completionTokens"]) for record in records),
        "requestAttempts": len(records),
        "requestMaxOutputTokens": max(requested),
        "requestMaxOutputTokensTotal": sum(requested),
        "billedCostUsd": None if first.get("billingMode") == "education-credit" else 0,
        "referenceCostUsd": round(
            sum(float(record["referenceCostUsd"]) for record in records), 8
        ),
        **{key: first.get(key) for key in identity_keys},
    }


def checkpoint_path(source_id: str, source_locale: str, target_locale: str) -> Path:
    return CHECKPOINT_DIR / f"{source_id}-{source_locale}-{target_locale}.json"


def report_path(source_id: str, source_locale: str, target_locale: str) -> Path:
    return REPORT_DIR / f"{source_id}-translation-{source_locale}-{target_locale}.json"


def error_report_path(source_id: str, source_locale: str, target_locale: str) -> Path:
    return REPORT_DIR / f"{source_id}-translation-{source_locale}-{target_locale}-errors.json"


def translation_state(paths: list[Path], model: str) -> dict[str, Any]:
    selected_ids: list[str] = []
    completed_ids: list[str] = []
    actual_models: set[str] = set()
    prompt_tokens = 0
    completion_tokens = 0
    reference_cost = 0.0
    request_max_output_tokens = 0
    for path in paths:
        metadata, body = load_markdown(path)
        activity_id = metadata["id"]
        selected_ids.append(activity_id)
        requirements = translation_requirements(metadata, model)
        target_locale = requirements["targetLocale"]
        output = VAULT / "translations" / target_locale / f"{activity_id}.md"
        expected_hash = source_hash(metadata["title"], body)
        if not current_translation(
            output,
            expected_hash,
            expected_locale=target_locale,
            expected_model=requirements["expectedModel"],
            expected_prompt=requirements["expectedPrompt"],
            expected_reasoning_mode=requirements["expectedReasoningMode"],
            expected_billing_mode=requirements["expectedBillingMode"],
            usage_required=requirements["usageRequired"],
            request_budget_required=requirements["requestBudgetRequired"],
        ):
            continue
        completed_ids.append(activity_id)
        translated, _ = load_markdown(output)
        if translated.get("model"):
            actual_models.add(translated["model"])
        usage = translated.get("usage") or {}
        prompt_tokens += int(usage.get("promptTokens", 0))
        completion_tokens += int(usage.get("completionTokens", 0))
        reference_cost += float(usage.get("referenceCostUsd", 0))
        request_max_output_tokens += int(usage.get("requestMaxOutputTokens", 0))
    completed = set(completed_ids)
    pricing = model_pricing(model)
    first_metadata, _ = load_markdown(paths[0])
    policy = source_translation_policy(str(first_metadata["sourceId"]))
    billing_mode = str(policy.get("billingMode") or DEFAULT_BILLING_MODE)
    return {
        "selectedActivityIds": selected_ids,
        "completedActivityIds": completed_ids,
        "pendingActivityIds": [activity_id for activity_id in selected_ids if activity_id not in completed],
        "modelRequested": model,
        "models": sorted(actual_models),
        "usage": {
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "requestMaxOutputTokens": request_max_output_tokens,
            "billedCostUsd": None if billing_mode == "education-credit" else 0,
            "referenceCostUsd": round(reference_cost, 8),
            "billingMode": billing_mode,
            "inputPriceUsdPerMillionTokens": pricing["input"],
            "outputPriceUsdPerMillionTokens": pricing["output"],
            "priceSource": PRICE_SOURCE,
            "priceAccessedOn": PRICE_ACCESSED_ON,
            "referenceCostLimitEnforced": policy.get("enforceReferenceCostLimit") is True,
            "maxReferenceCostUsd": policy.get("maxReferenceCostUsd"),
        },
    }


def advance_translation_state(
    state: dict[str, Any],
    activity_id: str,
    actual_model: str | None,
    usage: dict[str, Any] | None,
) -> None:
    if usage is None:
        return
    completed = set(state["completedActivityIds"])
    completed.add(activity_id)
    state["completedActivityIds"] = [
        selected for selected in state["selectedActivityIds"] if selected in completed
    ]
    state["pendingActivityIds"] = [
        selected for selected in state["selectedActivityIds"] if selected not in completed
    ]
    if actual_model:
        state["models"] = sorted(set(state["models"]) | {actual_model})
    totals = state["usage"]
    totals["promptTokens"] += int(usage.get("promptTokens", 0))
    totals["completionTokens"] += int(usage.get("completionTokens", 0))
    totals["requestMaxOutputTokens"] = int(totals.get("requestMaxOutputTokens", 0)) + int(
        usage.get("requestMaxOutputTokens", 0)
    )
    totals["referenceCostUsd"] = round(
        float(totals["referenceCostUsd"]) + float(usage.get("referenceCostUsd", 0)),
        8,
    )


def write_checkpoint(
    path: Path,
    *,
    status: str,
    source_id: str,
    source_locale: str,
    target_locale: str,
    model: str,
    paths: list[Path],
    state: dict[str, Any] | None = None,
    reason: str | None = None,
    next_retry_at: datetime | None = None,
    provider_error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_state = state or translation_state(paths, model)
    payload = {
        "schemaVersion": 1,
        "pipeline": "machine-translation",
        "status": status,
        "sourceId": source_id,
        "sourceLocale": source_locale,
        "targetLocale": target_locale,
        "promptVersion": prompt_version(source_locale, target_locale),
        **current_state,
    }
    reasoning_mode = source_translation_policy(source_id).get("reasoningMode")
    if reasoning_mode:
        payload["reasoningMode"] = reasoning_mode
    if reason:
        payload["reason"] = reason
    if next_retry_at:
        payload["nextRetryAt"] = next_retry_at.astimezone(UTC).isoformat()
    if provider_error:
        payload["providerError"] = provider_error
    write_json(path, payload)
    return payload


def active_retry(path: Path) -> datetime | None:
    if not path.exists():
        return None
    payload = read_json(path)
    if payload.get("status") != "retry-pending" or not payload.get("nextRetryAt"):
        return None
    retry_at = datetime.fromisoformat(payload["nextRetryAt"])
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return retry_at if retry_at > datetime.now(UTC) else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("MISTRAL_TRANSLATION_MODEL"))
    parser.add_argument("--workers", type=int, default=1, help="Must remain 1 so a provider cooldown stops the batch immediately")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--source-id")
    args = parser.parse_args()
    paths = sorted((VAULT / "activities").glob("*.md"))
    if args.ids:
        wanted = set(args.ids)
        paths = [path for path in paths if path.stem in wanted]
    if args.source_id:
        paths = [path for path in paths if load_markdown(path)[0].get("sourceId") == args.source_id]
    if args.limit:
        paths = paths[: args.limit]
    if not paths:
        raise SystemExit("No activity records selected")
    if args.workers != 1:
        raise SystemExit("Parallel translation is disabled; use --workers 1 for checkpoint-safe provider cooldowns")
    source_groups: dict[tuple[str, str, str, str], list[Path]] = {}
    for path in paths:
        metadata, _ = load_markdown(path)
        source_locale = metadata["originalLanguage"]
        target_locale = translation_target(source_locale)
        try:
            model = resolved_translation_model(metadata, args.model)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        source_groups.setdefault(
            (metadata["sourceId"], source_locale, target_locale, model), []
        ).append(path)
    # Determine stale groups without crossing an atomic source boundary.
    stale_groups: dict[tuple[str, str, str, str], list[Path]] = {}
    for group, group_paths in source_groups.items():
        model = group[3]
        pending = False
        for path in group_paths:
            metadata, body = load_markdown(path)
            try:
                requirements = translation_requirements(metadata, model)
            except ValueError as error:
                raise SystemExit(str(error)) from error
            output = VAULT / "translations" / requirements["targetLocale"] / path.name
            if not current_translation(
                output,
                source_hash(metadata["title"], body),
                expected_locale=requirements["targetLocale"],
                expected_model=requirements["expectedModel"],
                expected_prompt=requirements["expectedPrompt"],
                expected_reasoning_mode=requirements["expectedReasoningMode"],
                expected_billing_mode=requirements["expectedBillingMode"],
                usage_required=requirements["usageRequired"],
                request_budget_required=requirements["requestBudgetRequired"],
            ):
                pending = True
                break
        if pending:
            stale_groups[group] = group_paths
    if len(stale_groups) > 1:
        sources = ", ".join(sorted(group[0] for group in stale_groups))
        raise SystemExit(f"Missing translations span multiple sources ({sources}); rerun with --source-id")
    if not stale_groups:
        print(f"Translations current: {len(paths)}/{len(paths)}")
        return
    (source_id, source_locale, target_locale, model), paths = next(iter(stale_groups.items()))
    state_path = checkpoint_path(source_id, source_locale, target_locale)
    retry_at = active_retry(state_path)
    if retry_at:
        raise SystemExit(f"Provider cooldown is active; nextRetryAt={retry_at.isoformat()}")
    api_key = load_secret()
    errors: list[dict[str, str]] = []
    state = translation_state(paths, model)
    try:
        ensure_models_available(api_key, {model})
    except TransientTranslationError as error:
        write_checkpoint(
            state_path,
            status="retry-pending",
            source_id=source_id,
            source_locale=source_locale,
            target_locale=target_locale,
            model=model,
            paths=paths,
            state=state,
            reason=error.reason,
            next_retry_at=error.retry_at,
            provider_error=error.diagnostics,
        )
        raise SystemExit(f"{error.reason}; nextRetryAt={error.retry_at.isoformat()}") from error
    except PermanentTranslationError as error:
        write_checkpoint(
            state_path,
            status="failed-permanent",
            source_id=source_id,
            source_locale=source_locale,
            target_locale=target_locale,
            model=model,
            paths=paths,
            state=state,
            reason=error.reason,
            provider_error=error.diagnostics,
        )
        raise SystemExit(
            f"{error.reason}; provider access or configuration requires review"
        ) from error
    write_checkpoint(
        state_path,
        status="in-progress",
        source_id=source_id,
        source_locale=source_locale,
        target_locale=target_locale,
        model=model,
        paths=paths,
        state=state,
    )
    for path in paths:
        try:
            metadata, body = load_markdown(path)
            enforce_reference_cost_limit(
                source_translation_policy(source_id),
                float(state["usage"]["referenceCostUsd"]),
                metadata,
                body,
                model,
            )
            activity_id, actual_model, usage = translate_one(api_key, model, path)
            advance_translation_state(state, activity_id, actual_model, usage)
            write_checkpoint(
                state_path,
                status="in-progress",
                source_id=source_id,
                source_locale=source_locale,
                target_locale=target_locale,
                model=model,
                paths=paths,
                state=state,
            )
        except TransientTranslationError as error:
            write_checkpoint(
                state_path,
                status="retry-pending",
                source_id=source_id,
                source_locale=source_locale,
                target_locale=target_locale,
                model=model,
                paths=paths,
                state=state,
                reason=error.reason,
                next_retry_at=error.retry_at,
                provider_error=error.diagnostics,
            )
            raise SystemExit(f"{error.reason}; nextRetryAt={error.retry_at.isoformat()}") from error
        except PermanentTranslationError as error:
            write_checkpoint(
                state_path,
                status="failed-permanent",
                source_id=source_id,
                source_locale=source_locale,
                target_locale=target_locale,
                model=model,
                paths=paths,
                state=state,
                reason=error.reason,
                provider_error=error.diagnostics,
            )
            raise SystemExit(
                f"{error.reason}; provider access or configuration requires review"
            ) from error
        except Exception as error:  # preserve the completed prefix for manual diagnosis
            errors.append({"id": path.stem, "error": str(error)})
            write_checkpoint(
                state_path,
                status="failed",
                source_id=source_id,
                source_locale=source_locale,
                target_locale=target_locale,
                model=model,
                paths=paths,
                state=state,
                reason=f"translation-failed:{path.stem}",
            )
            print(f"ERROR {path.stem}: {error}", flush=True)
            break
    completed = len(state["completedActivityIds"])
    if errors:
        write_json(
            error_report_path(source_id, source_locale, target_locale),
            {"modelRequested": model, "selected": len(paths), "completed": completed, "errors": errors},
        )
        raise SystemExit(f"{len(errors)} translations failed; rerun to resume")
    final_checkpoint = write_checkpoint(
        state_path,
        status="complete",
        source_id=source_id,
        source_locale=source_locale,
        target_locale=target_locale,
        model=model,
        paths=paths,
        state=state,
    )
    report = {**final_checkpoint, "generatedAt": date.today().isoformat()}
    write_json(report_path(source_id, source_locale, target_locale), report)
    print(f"Translations current: {completed}/{len(paths)}")


if __name__ == "__main__":
    main()
