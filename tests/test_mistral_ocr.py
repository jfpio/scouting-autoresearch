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

from mistral_ocr import (
    OCRError,
    active_cooldown,
    approved_view,
    assert_source_input,
    completed_item,
    ensure_exact_model,
    finalize_run,
    load_config,
    record_success,
    request_identity,
    request_json,
    validate_image,
    validate_response,
)


JPEG = b"\xff\xd8\xff\xe0test-image"


class MistralOCRTests(unittest.TestCase):
    def config(self, directory: str) -> Path:
        path = Path(directory) / "ocr.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "schemaVersion": 1,
                    "sourceId": "chamarande-1934",
                    "model": "mistral-ocr-4-1",
                    "request": {
                        "recipeVersion": "mistral-ocr-image-v1",
                        "includeBlocks": True,
                        "confidenceScoresGranularity": "page",
                    },
                    "execution": {
                        "requireExplicitExecute": True,
                        "executionReady": True,
                        "approvedViewRanges": [[19, 29]],
                        "inputDirectoryUnderScratch": "scouting-autoresearch/sources/chamarande-1934",
                        "requireExactModelAccessCheck": True,
                        "sequentialRequests": True,
                        "billingMode": "education-credit",
                        "enforceReferenceCostLimit": True,
                        "maxReferenceCostUsd": 10,
                        "resultsUnderScratch": "scouting-autoresearch/ocr",
                    },
                    "pricing": {
                        "mode": "standard",
                        "usdPer1000Pages": 4.0,
                        "source": "https://docs.mistral.ai/models/ocr-4-1",
                        "accessedOn": "2026-09-05",
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_config_enforces_billing_exact_model_check_and_cost_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.config(directory)
            config = load_config(path)
            self.assertEqual(config.model, "mistral-ocr-4-1")
            self.assertEqual(config.approved_view_ranges, ((19, 29),))
            self.assertEqual(len(request_identity(config)), 64)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["execution"]["maxReferenceCostUsd"] = 11
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "between 0 and 10"):
                load_config(path)

    def test_repository_config_stays_blocked_until_page_boundaries_are_recorded(self):
        root = Path(__file__).resolve().parents[1]
        config = load_config(root / "config" / "ocr" / "chamarande-1934.yaml")
        self.assertFalse(config.execution_ready)
        self.assertEqual(config.approved_view_ranges, ())

    def test_images_must_be_valid_and_under_project_scratch(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            image = (
                Path(directory)
                / "scouting-autoresearch"
                / "sources"
                / "chamarande-1934"
                / "page.jpg"
            )
            image.parent.mkdir(parents=True)
            image.write_bytes(JPEG)
            data, media_type, digest = validate_image(image)
            self.assertEqual(data, JPEG)
            self.assertEqual(media_type, "image/jpeg")
            self.assertEqual(digest, hashlib.sha256(JPEG).hexdigest())
            config = load_config(self.config(directory))
            assert_source_input(image, config)
            with self.assertRaisesRegex(RuntimeError, "configured source directory"):
                assert_source_input(
                    Path(directory) / "scouting-autoresearch" / "other.jpg", config
                )
            self.assertEqual(approved_view(image.with_name("f19-page.jpg"), config), 19)
            self.assertIsNone(approved_view(image.with_name("f30-page.jpg"), config))
            outside = Path(directory) / "outside.jpg"
            outside.write_bytes(JPEG)
            with self.assertRaisesRegex(RuntimeError, "must remain under"):
                validate_image(outside)

    def test_exact_model_check_rejects_missing_model(self):
        with patch("mistral_ocr.request_json", return_value={"data": [{"id": "other"}]}):
            with self.assertRaisesRegex(OCRError, "model-not-available"):
                ensure_exact_model("unused", "mistral-ocr-4-1")

    def test_safe_transient_http_error_uses_retry_after(self):
        headers = Message()
        headers["Retry-After"] = "120"
        headers["Set-Cookie"] = "secret"
        error = urllib.error.HTTPError(
            "https://api.mistral.ai/v1/ocr",
            429,
            "private message",
            headers,
            io.BytesIO(b'{"type":"rate_limit","code":"429","message":"private"}'),
        )
        with patch("mistral_ocr.urllib.request.urlopen", side_effect=error):
            before = datetime.now(UTC)
            with self.assertRaises(OCRError) as raised:
                request_json("https://api.mistral.ai/v1/ocr", {}, "secret-key")
        self.assertEqual(raised.exception.reason, "transient-provider-error")
        self.assertGreaterEqual(raised.exception.retry_at, before + timedelta(seconds=119))
        serialized = json.dumps(raised.exception.diagnostics)
        self.assertNotIn("cookie", serialized.lower())
        self.assertNotIn("private", serialized.lower())

    def test_response_requires_exact_model_one_page_and_markdown(self):
        response = {
            "model": "mistral-ocr-4-1",
            "pages": [{"markdown": "Tekst", "confidence_scores": [0.9, 1.0]}],
            "usage_info": {"pages_processed": 1},
        }
        summary = validate_response(response, "mistral-ocr-4-1")
        self.assertEqual(summary["pagesProcessed"], 1)
        self.assertAlmostEqual(summary["averagePageConfidence"], 0.95)
        with self.assertRaisesRegex(OCRError, "unexpected-model"):
            validate_response({**response, "model": "other"}, "mistral-ocr-4-1")

    def test_success_is_costed_and_reused_by_input_and_response_hash(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            config = load_config(self.config(directory))
            root = Path(directory) / "scouting-autoresearch"
            image = root / "sources" / "chamarande-1934" / "f19-page.jpg"
            output = root / "ocr" / "response.json"
            image.parent.mkdir(parents=True)
            image.write_bytes(JPEG)
            output.parent.mkdir(parents=True)
            response = b'{"model":"mistral-ocr-4-1"}\n'
            output.write_bytes(response)
            checkpoint = Path(directory) / "checkpoint.json"
            checkpoint.write_text(json.dumps({"sourceId": config.source_id}), encoding="utf-8")
            digest = hashlib.sha256(JPEG).hexdigest()
            item = record_success(
                checkpoint,
                config,
                image,
                digest,
                output,
                response,
                {
                    "pagesProcessed": 1,
                    "markdownCharacters": 5,
                    "averagePageConfidence": 0.9,
                },
                datetime(2026, 9, 5, tzinfo=UTC),
            )
            stored = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(stored["ocrRun"]["billingMode"], "education-credit")
            self.assertIsNone(stored["ocrRun"]["billedCostUsd"])
            self.assertEqual(stored["ocrRun"]["usage"]["referenceCostUsd"], 0.004)
            self.assertEqual(completed_item(stored, digest, config), item)
            output.write_bytes(b"changed")
            self.assertIsNone(completed_item(stored, digest, config))

    def test_cache_identity_changes_with_the_model_or_request_recipe(self):
        from dataclasses import replace

        with tempfile.TemporaryDirectory() as directory:
            config = load_config(self.config(directory))
            self.assertNotEqual(
                request_identity(config),
                request_identity(replace(config, model="mistral-ocr-future")),
            )
            self.assertNotEqual(
                request_identity(config),
                request_identity(replace(config, include_blocks=False)),
            )

    def test_run_is_complete_only_when_every_approved_view_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            config = load_config(self.config(directory))
            checkpoint = Path(directory) / "checkpoint.json"
            items = [
                {"status": "complete", "sourceImage": f"f{view}-page.jpg"}
                for view in range(19, 29)
            ]
            checkpoint.write_text(
                json.dumps({"sourceId": config.source_id, "ocrRun": {"items": items}}),
                encoding="utf-8",
            )
            now = datetime(2026, 9, 5, tzinfo=UTC)
            self.assertFalse(finalize_run(checkpoint, config, now))
            payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            payload["ocrRun"]["items"].append(
                {"status": "complete", "sourceImage": "f29-page.jpg"}
            )
            checkpoint.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(finalize_run(checkpoint, config, now))
            finished = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(finished["ocrRun"]["status"], "complete")
            self.assertEqual(finished["ocrRun"]["completedApprovedViewCount"], 11)

    def test_cost_accounting_includes_the_prior_smoke(self):
        from mistral_ocr import reference_cost

        checkpoint = {
            "ocrSmoke": {"referenceCostUsd": 0.004},
            "ocrRun": {"usage": {"referenceCostUsd": 0.008}},
        }
        self.assertEqual(reference_cost(checkpoint), 0.012)

    def test_ocr_cooldown_is_nested_and_timezone_aware(self):
        now = datetime(2026, 9, 5, 6, tzinfo=UTC)
        checkpoint = {
            "ocrRun": {
                "status": "retry-pending",
                "nextRetryAt": "2026-09-05T07:00:00+00:00",
            }
        }
        self.assertEqual(active_cooldown(checkpoint, now), now + timedelta(hours=1))
        self.assertIsNone(active_cooldown(checkpoint, now + timedelta(hours=2)))


if __name__ == "__main__":
    unittest.main()
