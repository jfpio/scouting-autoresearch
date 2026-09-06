#!/usr/bin/env python3
"""OCR approved local page images with Mistral and resumable cost accounting."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from common import ROOT, read_json, write_json
from translate import retry_at_from_headers, safe_http_diagnostics


OCR_API_URL = "https://api.mistral.ai/v1/ocr"
MODELS_API_URL = "https://api.mistral.ai/v1/models"
DEFAULT_CHECKPOINT_DIR = ROOT / "data" / "checkpoints" / "gallica-fetch"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}
EXPECTED_API_HOST = "api.mistral.ai"
MAX_RESPONSE_BYTES = {
    MODELS_API_URL: 4 * 1024 * 1024,
    OCR_API_URL: 64 * 1024 * 1024,
}


@dataclass(frozen=True)
class OCRConfig:
    source_id: str
    model: str
    execution_ready: bool
    approved_view_ranges: tuple[tuple[int, int], ...]
    input_directory_under_scratch: str
    recipe_version: str
    include_blocks: bool
    confidence_granularity: str
    billing_mode: str
    max_reference_cost_usd: float
    usd_per_1000_pages: float
    price_mode: str
    price_source: str
    price_accessed_on: str
    results_under_scratch: str


class OCRError(RuntimeError):
    def __init__(
        self,
        reason: str,
        diagnostics: dict[str, Any],
        retry_at: datetime | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.diagnostics = diagnostics
        self.retry_at = retry_at


def load_config(path: Path) -> OCRConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    request = payload.get("request") or {}
    execution = payload.get("execution") or {}
    pricing = payload.get("pricing") or {}
    if payload.get("schemaVersion") != 1:
        raise RuntimeError("Unsupported OCR config schema")
    source_id = str(payload.get("sourceId") or "")
    model = str(payload.get("model") or "")
    if not source_id or not model:
        raise RuntimeError("OCR sourceId and exact model are required")
    if execution.get("requireExplicitExecute") is not True:
        raise RuntimeError("OCR config must require explicit execution")
    if execution.get("requireExactModelAccessCheck") is not True:
        raise RuntimeError("OCR config must require an exact model access check")
    if execution.get("sequentialRequests") is not True:
        raise RuntimeError("OCR requests must be sequential")
    if execution.get("billingMode") != "education-credit":
        raise RuntimeError("OCR must use education-credit accounting")
    if execution.get("enforceReferenceCostLimit") is not True:
        raise RuntimeError("OCR reference cost limit must be enforced")
    limit = execution.get("maxReferenceCostUsd")
    price = pricing.get("usdPer1000Pages")
    if not isinstance(limit, (int, float)) or not 0 < float(limit) <= 10:
        raise RuntimeError("OCR reference cost limit must be between 0 and 10 USD")
    if not isinstance(price, (int, float)) or float(price) <= 0:
        raise RuntimeError("OCR reference price must be positive")
    if request.get("confidenceScoresGranularity") != "page":
        raise RuntimeError("OCR confidence granularity must be page")
    recipe_version = str(request.get("recipeVersion") or "")
    if not recipe_version:
        raise RuntimeError("OCR recipeVersion is required")
    ranges = execution.get("approvedViewRanges")
    if not isinstance(ranges, list) or any(
        not isinstance(item, list)
        or len(item) != 2
        or not all(isinstance(value, int) for value in item)
        or item[0] < 1
        or item[1] < item[0]
        for item in ranges
    ):
        raise RuntimeError("OCR approvedViewRanges must contain inclusive [start, end] pairs")
    if execution.get("executionReady") is True and not ranges:
        raise RuntimeError("Ready OCR config must contain at least one approved view range")
    input_directory = str(execution.get("inputDirectoryUnderScratch") or "")
    if input_directory != f"scouting-autoresearch/sources/{source_id}":
        raise RuntimeError("OCR input directory must match the configured source")
    results = str(execution.get("resultsUnderScratch") or "")
    if not results.startswith("scouting-autoresearch/"):
        raise RuntimeError("OCR results must be under SCRATCH/scouting-autoresearch")
    return OCRConfig(
        source_id=source_id,
        model=model,
        execution_ready=execution.get("executionReady") is True,
        approved_view_ranges=tuple((item[0], item[1]) for item in ranges),
        input_directory_under_scratch=input_directory,
        recipe_version=recipe_version,
        include_blocks=request.get("includeBlocks") is True,
        confidence_granularity="page",
        billing_mode="education-credit",
        max_reference_cost_usd=float(limit),
        usd_per_1000_pages=float(price),
        price_mode=str(pricing.get("mode") or ""),
        price_source=str(pricing.get("source") or ""),
        price_accessed_on=str(pricing.get("accessedOn") or ""),
        results_under_scratch=results,
    )


def load_secret() -> str:
    values: dict[str, str] = {}
    secret_path = Path.home() / ".secrets" / "mistral.env"
    if secret_path.exists():
        for raw_line in secret_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    key = os.environ.get("MISTRAL_API_KEY") or values.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is missing")
    return key


def scratch_root() -> Path:
    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise RuntimeError("SCRATCH is not set")
    return (Path(scratch) / "scouting-autoresearch").resolve()


def assert_scratch_path(path: Path) -> None:
    try:
        path.resolve().relative_to(scratch_root())
    except ValueError as error:
        raise RuntimeError(
            "OCR inputs and outputs must remain under SCRATCH/scouting-autoresearch"
        ) from error


def validate_image(path: Path) -> tuple[bytes, str, str]:
    assert_scratch_path(path)
    data = path.read_bytes()
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise RuntimeError("OCR image is empty or exceeds the 20 MiB limit")
    if data.startswith(b"\xff\xd8"):
        media_type = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    else:
        raise RuntimeError("OCR input must be a JPEG or PNG image")
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and guessed not in {"image/jpeg", "image/png"}:
        raise RuntimeError("OCR filename extension does not match an allowed image type")
    return data, media_type, hashlib.sha256(data).hexdigest()


def assert_source_input(path: Path, config: OCRConfig) -> None:
    expected = (
        Path(os.environ["SCRATCH"]) / config.input_directory_under_scratch
    ).resolve()
    try:
        path.resolve().relative_to(expected)
    except ValueError as error:
        raise RuntimeError("OCR input must be inside the configured source directory") from error


def approved_view(image: Path, config: OCRConfig) -> int | None:
    match = re.match(r"^f(\d+)-", image.name)
    if not match:
        return None
    view = int(match.group(1))
    return view if any(start <= view <= end for start, end in config.approved_view_ranges) else None


def approved_views(config: OCRConfig) -> set[int]:
    return {
        view
        for start, end in config.approved_view_ranges
        for view in range(start, end + 1)
    }


def request_identity(config: OCRConfig) -> str:
    canonical = json.dumps(
        {
            "model": config.model,
            "recipeVersion": config.recipe_version,
            "includeBlocks": config.include_blocks,
            "confidenceScoresGranularity": config.confidence_granularity,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def default_output(config: OCRConfig, image: Path, digest: str) -> Path:
    return (
        Path(os.environ["SCRATCH"])
        / config.results_under_scratch
        / config.source_id
        / f"{image.stem}-{digest[:12]}-{request_identity(config)[:12]}.json"
    )


def request_json(url: str, payload: dict[str, Any] | None, api_key: str) -> dict[str, Any]:
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or parsed_url.hostname != EXPECTED_API_HOST:
        raise RuntimeError("Mistral request URL is outside the expected API host")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    observed_at = datetime.now(UTC)
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            final = urlparse(response.geturl())
            if final.scheme != "https" or final.hostname != EXPECTED_API_HOST:
                raise OCRError("provider-redirected-outside-expected-host", {})
            limit = MAX_RESPONSE_BYTES.get(url, 4 * 1024 * 1024)
            response_bytes = response.read(limit + 1)
            if len(response_bytes) > limit:
                raise OCRError("provider-response-too-large", {"limitBytes": limit})
            result = json.loads(response_bytes.decode("utf-8"))
    except urllib.error.HTTPError as error:
        diagnostics = safe_http_diagnostics(error)
        retry_at = (
            retry_at_from_headers(error.headers, observed_at)
            if error.code in TRANSIENT_HTTP_CODES
            else None
        )
        raise OCRError(
            "transient-provider-error" if retry_at else "permanent-provider-error",
            diagnostics,
            retry_at,
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise OCRError(
            "transient-network-error",
            {"transport": "network"},
            observed_at + timedelta(hours=1),
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OCRError("invalid-provider-json", {"responseShape": "invalid-json"}) from error
    if not isinstance(result, dict):
        raise OCRError("invalid-provider-json", {"responseShape": "not-an-object"})
    return result


def ensure_exact_model(api_key: str, model: str) -> None:
    payload = request_json(MODELS_API_URL, None, api_key)
    models = payload.get("data")
    if not isinstance(models, list):
        raise OCRError("invalid-model-list-response", {"responseShape": "missing-data-list"})
    available = {
        item.get("id")
        for item in models or []
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if model not in available:
        raise OCRError("model-not-available-for-account", {"missingModels": [model]})


def page_confidence(page: dict[str, Any]) -> float | None:
    scores = page.get("confidence_scores")
    if isinstance(scores, dict):
        average = scores.get("average_page_confidence_score")
        if isinstance(average, (int, float)):
            return float(average)
        words = scores.get("word_confidence_scores")
        values = (
            [float(value) for value in words if isinstance(value, (int, float))]
            if isinstance(words, list)
            else []
        )
    elif isinstance(scores, list):
        values = [float(value) for value in scores if isinstance(value, (int, float))]
    else:
        values = []
    return sum(values) / len(values) if values else None


def validate_response(payload: dict[str, Any], model: str) -> dict[str, Any]:
    if payload.get("model") != model:
        raise OCRError("provider-returned-unexpected-model", {"model": payload.get("model")})
    pages = payload.get("pages")
    if not isinstance(pages, list) or len(pages) != 1 or not isinstance(pages[0], dict):
        raise OCRError("invalid-ocr-response", {"responseShape": "expected-one-page"})
    markdown = pages[0].get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise OCRError("invalid-ocr-response", {"responseShape": "missing-markdown"})
    usage = payload.get("usage_info") or {}
    pages_processed = usage.get("pages_processed")
    if pages_processed != 1:
        raise OCRError("invalid-ocr-usage", {"pagesProcessed": pages_processed})
    return {
        "pagesProcessed": 1,
        "markdownCharacters": len(markdown),
        "averagePageConfidence": page_confidence(pages[0]),
    }


def completed_item(
    checkpoint: dict[str, Any], digest: str, config: OCRConfig
) -> dict[str, Any] | None:
    identity = request_identity(config)
    for item in (checkpoint.get("ocrRun") or {}).get("items", []):
        if (
            item.get("sourceImageSha256") != digest
            or item.get("status") != "complete"
            or item.get("requestIdentity") != identity
            or item.get("model") != config.model
        ):
            continue
        relative = item.get("scratchRelativePath")
        if relative:
            raw_path = Path(os.environ["SCRATCH"]) / relative
            if (
                raw_path.exists()
                and hashlib.sha256(raw_path.read_bytes()).hexdigest()
                == item.get("responseSha256")
            ):
                return item
    return None


def active_cooldown(checkpoint: dict[str, Any], now: datetime) -> datetime | None:
    run = checkpoint.get("ocrRun") or {}
    value = run.get("nextRetryAt")
    if run.get("status") != "retry-pending" or not value:
        return None
    retry_at = datetime.fromisoformat(value)
    if retry_at.tzinfo is None:
        raise RuntimeError("OCR nextRetryAt must contain a timezone")
    return retry_at if retry_at > now else None


def reference_cost(checkpoint: dict[str, Any]) -> float:
    smoke = float((checkpoint.get("ocrSmoke") or {}).get("referenceCostUsd", 0))
    production = float(
        ((checkpoint.get("ocrRun") or {}).get("usage") or {}).get("referenceCostUsd", 0)
    )
    return smoke + production


def record_error(checkpoint_path: Path, error: OCRError) -> None:
    checkpoint = read_json(checkpoint_path)
    run = checkpoint.setdefault("ocrRun", {})
    run["status"] = "retry-pending" if error.retry_at else "failed"
    run["reason"] = error.reason
    run["providerDiagnostics"] = error.diagnostics
    if error.retry_at:
        run["nextRetryAt"] = error.retry_at.astimezone(UTC).isoformat()
    else:
        run.pop("nextRetryAt", None)
    write_json(checkpoint_path, checkpoint)


def record_success(
    checkpoint_path: Path,
    config: OCRConfig,
    image: Path,
    digest: str,
    output: Path,
    response_bytes: bytes,
    summary: dict[str, Any],
    completed_at: datetime,
) -> dict[str, Any]:
    checkpoint = read_json(checkpoint_path)
    run = checkpoint.setdefault("ocrRun", {})
    items = run.setdefault("items", [])
    cost = round(config.usd_per_1000_pages / 1000, 8)
    item = {
        "status": "complete",
        "sourceImage": image.name,
        "sourceImageSha256": digest,
        "model": config.model,
        "recipeVersion": config.recipe_version,
        "requestIdentity": request_identity(config),
        "scratchRelativePath": str(
            output.resolve().relative_to(Path(os.environ["SCRATCH"]).resolve())
        ),
        "responseSha256": hashlib.sha256(response_bytes).hexdigest(),
        "completedAt": completed_at.astimezone(UTC).isoformat(),
        **summary,
        "referenceCostUsd": cost,
    }
    items.append(item)
    run.update(
        {
            "status": "in-progress",
            "provider": "mistral",
            "endpoint": "/v1/ocr",
            "modelRequested": config.model,
            "model": config.model,
            "billingMode": config.billing_mode,
            "billedCostUsd": None,
            "referencePricing": {
                "model": config.model,
                "mode": config.price_mode,
                "usdPer1000Pages": config.usd_per_1000_pages,
                "retrievedAt": config.price_accessed_on,
                "url": config.price_source,
            },
            "usage": {
                "pagesProcessed": sum(int(entry["pagesProcessed"]) for entry in items),
                "referenceCostUsd": round(
                    sum(float(entry["referenceCostUsd"]) for entry in items), 8
                ),
                "referenceCostLimitUsd": config.max_reference_cost_usd,
                "referenceCostLimitEnforced": True,
            },
        }
    )
    run.pop("reason", None)
    run.pop("nextRetryAt", None)
    run.pop("providerDiagnostics", None)
    write_json(checkpoint_path, checkpoint)
    return item


def finalize_run(checkpoint_path: Path, config: OCRConfig, completed_at: datetime) -> bool:
    checkpoint = read_json(checkpoint_path)
    run = checkpoint.setdefault("ocrRun", {})
    expected = approved_views(config)
    completed = {
        view
        for item in run.get("items", [])
        if item.get("status") == "complete"
        and (view := approved_view(Path(str(item.get("sourceImage") or "")), config))
        is not None
    }
    run["approvedViewCount"] = len(expected)
    run["completedApprovedViewCount"] = len(completed)
    is_complete = bool(expected) and completed >= expected
    run["status"] = "complete" if is_complete else "in-progress"
    if is_complete:
        run["completedAt"] = completed_at.astimezone(UTC).isoformat()
    else:
        run.pop("completedAt", None)
    write_json(checkpoint_path, checkpoint)
    return is_complete


def ocr_image(
    image: Path,
    output: Path,
    config: OCRConfig,
    api_key: str,
) -> tuple[bytes, dict[str, Any], str]:
    assert_source_input(image, config)
    data, media_type, digest = validate_image(image)
    payload = {
        "model": config.model,
        "document": {
            "type": "image_url",
            "image_url": f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}",
        },
        "include_blocks": config.include_blocks,
        "confidence_scores_granularity": config.confidence_granularity,
    }
    response = request_json(OCR_API_URL, payload, api_key)
    summary = validate_response(response, config.model)
    response_bytes = (
        json.dumps(response, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    assert_scratch_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        temporary.write_bytes(response_bytes)
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return response_bytes, summary, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--image", required=True, action="append", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    checkpoint_path = args.checkpoint or DEFAULT_CHECKPOINT_DIR / f"{config.source_id}.json"
    checkpoint = read_json(checkpoint_path)
    if checkpoint.get("sourceId") != config.source_id:
        raise SystemExit("OCR config and checkpoint sourceId differ")

    prepared: list[tuple[Path, str, Path]] = []
    reused: list[dict[str, Any]] = []
    unapproved: list[str] = []
    seen_digests: set[str] = set()
    for image in args.image:
        assert_source_input(image, config)
        _, _, digest = validate_image(image)
        if digest in seen_digests:
            raise SystemExit(f"Duplicate OCR input: {image.name}")
        seen_digests.add(digest)
        if approved_view(image, config) is None:
            unapproved.append(image.name)
        prior = completed_item(checkpoint, digest, config)
        if prior:
            reused.append(prior)
        else:
            prepared.append((image, digest, default_output(config, image, digest)))

    now = datetime.now(UTC)
    retry_at = active_cooldown(checkpoint, now) if prepared else None
    forecast = (
        reference_cost(checkpoint)
        + len(prepared) * config.usd_per_1000_pages / 1000
    )
    plan: dict[str, Any] = {
        "status": "dry-run" if not args.execute else "ready",
        "sourceId": config.source_id,
        "model": config.model,
        "pendingImages": len(prepared),
        "reusedImages": len(reused),
        "referenceCostAfterUsd": round(forecast, 8),
        "referenceCostLimitUsd": config.max_reference_cost_usd,
        "cooldownActive": retry_at is not None,
        "executionReady": config.execution_ready,
        "inputsApproved": not unapproved,
        "unapprovedInputs": unapproved,
        "approvedViewCount": len(approved_views(config)),
    }
    if retry_at:
        plan["nextRetryAt"] = retry_at.isoformat()
    if not args.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if not prepared:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if not config.execution_ready:
        raise SystemExit("Mistral OCR production is not ready; inspect and approve prose view ranges")
    if unapproved:
        raise SystemExit("Mistral OCR input is outside the approved prose view ranges")
    if retry_at:
        raise SystemExit(f"Mistral OCR cooldown is active; nextRetryAt={retry_at.isoformat()}")
    if forecast > config.max_reference_cost_usd:
        raise SystemExit("Mistral OCR reference cost limit would be exceeded")

    api_key = load_secret()
    try:
        ensure_exact_model(api_key, config.model)
        checkpoint = read_json(checkpoint_path)
        checkpoint.setdefault("ocrRun", {})["modelAccessVerifiedAt"] = datetime.now(UTC).isoformat()
        write_json(checkpoint_path, checkpoint)
        completed: list[dict[str, Any]] = []
        for image, digest, output in prepared:
            response_bytes, summary, observed_digest = ocr_image(image, output, config, api_key)
            if observed_digest != digest:
                raise RuntimeError("OCR source image changed during execution")
            completed.append(
                record_success(
                    checkpoint_path,
                    config,
                    image,
                    digest,
                    output,
                    response_bytes,
                    summary,
                    datetime.now(UTC),
                )
            )
        plan["sourceComplete"] = finalize_run(
            checkpoint_path, config, datetime.now(UTC)
        )
    except OCRError as error:
        record_error(checkpoint_path, error)
        suffix = f"; nextRetryAt={error.retry_at.isoformat()}" if error.retry_at else ""
        raise SystemExit(f"{error.reason}{suffix}") from error
    print(json.dumps({**plan, "completed": completed}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
