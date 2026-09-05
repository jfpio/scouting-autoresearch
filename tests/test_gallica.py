import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gallica import (
    ApprovedItem,
    GallicaFetchError,
    active_cooldown,
    artifact_url,
    assert_scratch_output,
    fetch_artifact,
    load_approved_item,
    record_fetch_error,
    record_pdf_success,
    reserve_request_slot,
    retry_at_from_headers,
    safe_http_diagnostics,
)


ITEM = ApprovedItem(
    source_id="chamarande-1934",
    identifier="bpt6k3373518k",
    canonical_url="https://gallica.bnf.fr/ark:/12148/bpt6k3373518k",
    rate_limit_per_minute=5,
    required_attribution="Source gallica.bnf.fr / Bibliothèque nationale de France",
)


class FakeResponse:
    def __init__(self, data: bytes, content_type: str, url: str):
        self.data = data
        self.url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.headers["Content-Length"] = str(len(data))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.data if size < 0 else self.data[:size]

    def geturl(self) -> str:
        return self.url


class GallicaTests(unittest.TestCase):
    def registry(self, path: Path, approvals: list[dict] | None = None) -> None:
        payload = {
            "collections": [
                {
                    "id": "gallica-bnf",
                    "status": "approved-per-item",
                    "allowedMethods": ["metadata-only", "documented-download"],
                    "rateLimitPerMinute": 5,
                    "attribution": ITEM.required_attribution,
                    "itemApprovals": approvals
                    if approvals is not None
                    else [
                        {
                            "identifier": ITEM.identifier,
                            "sourceId": ITEM.source_id,
                            "canonicalUrl": ITEM.canonical_url,
                            "useMode": "noncommercial-research-and-publication",
                            "requiredAttribution": ITEM.required_attribution,
                            "downstreamLicensing": {
                                "sourceTextAndTranscription": "gallica-noncommercial-reuse-terms"
                            },
                        }
                    ],
                }
            ]
        }
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    def test_registry_requires_an_exact_per_item_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "registry.yaml"
            self.registry(registry)
            item = load_approved_item(ITEM.source_id, registry)
            self.assertEqual(item.identifier, ITEM.identifier)
            self.assertEqual(item.rate_limit_per_minute, 5)
            with self.assertRaisesRegex(RuntimeError, "not approved per item"):
                load_approved_item("another-source", registry)

    def test_registry_rejects_a_commercial_or_mislicensed_item(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "registry.yaml"
            approval = {
                "identifier": ITEM.identifier,
                "sourceId": ITEM.source_id,
                "canonicalUrl": ITEM.canonical_url,
                "useMode": "commercial",
                "downstreamLicensing": {},
            }
            self.registry(registry, [approval])
            with self.assertRaisesRegex(RuntimeError, "noncommercial use mode"):
                load_approved_item(ITEM.source_id, registry)

    def test_urls_are_derived_from_the_approved_identifier(self):
        self.assertEqual(artifact_url(ITEM, "pdf"), f"{ITEM.canonical_url}.pdf")
        self.assertEqual(
            artifact_url(ITEM, "pagination"),
            "https://gallica.bnf.fr/services/Pagination?ark=bpt6k3373518k",
        )
        self.assertEqual(
            artifact_url(ITEM, "view", 19),
            "https://gallica.bnf.fr/iiif/ark:/12148/bpt6k3373518k/f19/full/1200,/0/native.jpg",
        )
        with self.assertRaises(ValueError):
            artifact_url(ITEM, "view", 0)

    def test_output_must_stay_in_project_scratch(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            allowed = Path(directory) / "scouting-autoresearch" / "source.pdf"
            assert_scratch_output(allowed)
            with self.assertRaisesRegex(RuntimeError, "must be stored under SCRATCH"):
                assert_scratch_output(Path(directory) / "outside.pdf")

    def test_fetch_is_atomic_hash_pinned_and_reused(self):
        data = b"%PDF-1.7\nexample"
        url = artifact_url(ITEM, "pdf")
        response = FakeResponse(data, "application/pdf", url)
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            output = Path(directory) / "scouting-autoresearch" / "source.pdf"
            with patch("gallica.urllib.request.urlopen", return_value=response) as request:
                result = fetch_artifact(
                    ITEM,
                    "pdf",
                    output,
                    expected_sha256=hashlib.sha256(data).hexdigest(),
                    now=datetime(2026, 9, 5, tzinfo=UTC),
                )
            self.assertFalse(result["reused"])
            self.assertEqual(output.read_bytes(), data)
            request.assert_called_once()
            with patch("gallica.urllib.request.urlopen") as no_request:
                reused = fetch_artifact(ITEM, "pdf", output)
            self.assertTrue(reused["reused"])
            no_request.assert_not_called()

    def test_redirect_outside_gallica_is_rejected(self):
        response = FakeResponse(b"%PDF-1.7\nexample", "application/pdf", "https://evil.test/x")
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ), patch("gallica.urllib.request.urlopen", return_value=response):
            output = Path(directory) / "scouting-autoresearch" / "source.pdf"
            with self.assertRaisesRegex(RuntimeError, "redirected outside"):
                fetch_artifact(ITEM, "pdf", output)
            self.assertFalse(output.exists())

    def test_fetch_error_reason_contains_the_http_status(self):
        error = urllib.error.HTTPError(
            artifact_url(ITEM, "pdf"),
            429,
            "do not persist this",
            {},
            io.BytesIO(b"{}"),
        )
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ), patch("gallica.urllib.request.urlopen", side_effect=error):
            output = Path(directory) / "scouting-autoresearch" / "source.pdf"
            with self.assertRaises(GallicaFetchError) as raised:
                fetch_artifact(
                    ITEM,
                    "pdf",
                    output,
                    now=datetime(2026, 9, 5, tzinfo=UTC),
                )
        self.assertEqual(raised.exception.reason, "transient-http-429")

    def test_429_diagnostics_are_allowlisted_and_use_retry_after(self):
        headers = {
            "Retry-After": "120",
            "X-RateLimit-Remaining": "0",
            "Set-Cookie": "secret-cookie",
        }
        error = urllib.error.HTTPError(
            artifact_url(ITEM, "pdf"),
            429,
            "do not persist this",
            headers,
            io.BytesIO(b'{"type":"rate_limit","code":"429","message":"secret"}'),
        )
        diagnostics = safe_http_diagnostics(error)
        serialized = json.dumps(diagnostics)
        self.assertEqual(diagnostics["httpStatus"], 429)
        self.assertEqual(diagnostics["headers"]["retry-after"], "120")
        self.assertEqual(diagnostics["error"], {"type": "rate_limit", "code": "429"})
        self.assertNotIn("cookie", serialized.lower())
        self.assertNotIn("secret", serialized)
        now = datetime(2026, 9, 5, tzinfo=UTC)
        self.assertEqual(retry_at_from_headers(headers, now), now + timedelta(seconds=120))
        self.assertEqual(retry_at_from_headers({}, now), now + timedelta(hours=1))

    def test_checkpoint_records_transient_error_and_success(self):
        base = {
            "sourceId": ITEM.source_id,
            "status": "retry-pending",
            "nextRetryAt": "2026-09-05T06:00:00+00:00",
            "fullDocument": {"url": artifact_url(ITEM, "pdf")},
        }
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            checkpoint = Path(directory) / "checkpoint.json"
            checkpoint.write_text(json.dumps(base), encoding="utf-8")
            failure = GallicaFetchError(
                "transient-http-error",
                {"httpStatus": 429, "headers": {}},
                datetime(2026, 9, 5, 7, tzinfo=UTC),
            )
            record_fetch_error(
                checkpoint,
                failure,
                datetime(2026, 9, 5, 6, tzinfo=UTC),
            )
            failed = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(failed["status"], "retry-pending")
            self.assertEqual(failed["nextRetryAt"], "2026-09-05T07:00:00+00:00")
            self.assertEqual(failed["fullDocument"]["attempts"][0]["attempt"], 1)
            self.assertEqual(
                failed["fullDocument"]["attempts"][0]["providerDiagnostics"],
                {"httpStatus": 429, "headers": {}},
            )
            record_fetch_error(
                checkpoint,
                failure,
                datetime(2026, 9, 5, 6, 30, tzinfo=UTC),
            )
            failed = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(failed["fullDocument"]["attempts"][1]["attempt"], 2)

            output = (
                Path(directory)
                / "scouting-autoresearch"
                / "sources"
                / ITEM.source_id
                / f"{ITEM.source_id}-gallica.pdf"
            )
            result = {
                "url": artifact_url(ITEM, "pdf"),
                "path": str(output),
                "sha256": "a" * 64,
                "bytes": 42,
                "contentType": "application/pdf",
                "retrievedAt": "2026-09-05T07:00:01+00:00",
                "reused": False,
            }
            record_pdf_success(checkpoint, result, ITEM)
            succeeded = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(succeeded["status"], "fetched")
            self.assertNotIn("nextRetryAt", succeeded)
            self.assertEqual(succeeded["fullDocument"]["sha256"], "a" * 64)
            self.assertEqual(
                [item["attempt"] for item in succeeded["fullDocument"]["attempts"]],
                [1, 2],
            )

    def test_active_cooldown_only_blocks_future_retry(self):
        now = datetime(2026, 9, 5, 6, tzinfo=UTC)
        checkpoint = {"status": "retry-pending", "nextRetryAt": "2026-09-05T07:00:00+00:00"}
        self.assertEqual(active_cooldown(checkpoint, now), now + timedelta(hours=1))
        self.assertIsNone(active_cooldown(checkpoint, now + timedelta(hours=2)))

    def test_request_slots_enforce_the_registered_interval_without_sleeping(self):
        now = datetime(2026, 9, 5, 6, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            state = Path(directory) / "scouting-autoresearch" / "provider-state" / "gallica.json"
            self.assertIsNone(reserve_request_slot(state, now, 5))
            self.assertEqual(
                reserve_request_slot(state, now + timedelta(seconds=1), 5),
                now + timedelta(seconds=12),
            )
            self.assertIsNone(reserve_request_slot(state, now + timedelta(seconds=12), 5))


if __name__ == "__main__":
    unittest.main()
