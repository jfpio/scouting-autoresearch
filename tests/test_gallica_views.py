import hashlib
import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gallica import GallicaFetchError, artifact_url, load_approved_item
from gallica_views import (
    completed_views,
    known_view_entry,
    next_pending_view,
    pagination_views,
    record_view_error,
    record_view_success,
    reusable_cached_view,
    valid_cached_view,
)


JPEG = b"\xff\xd8\xff\xe0test-view"
SOURCE_ID = "chamarande-1934"


class GallicaViewTests(unittest.TestCase):
    def pagination(self, directory: str, count: int = 3) -> Path:
        path = (
            Path(directory)
            / "scouting-autoresearch"
            / "sources"
            / SOURCE_ID
            / "pagination.xml"
        )
        path.parent.mkdir(parents=True)
        pages = "".join(
            f"<page><numero>{view}</numero><ordre>{view}</ordre></page>"
            for view in range(1, count + 1)
        )
        path.write_text(
            "<livre><structure><idUPN>bpt6k3373518k</idUPN>"
            f"<nbVueImages>{count}</nbVueImages></structure><pages>{pages}</pages></livre>",
            encoding="utf-8",
        )
        return path

    def checkpoint(self, directory: str) -> Path:
        path = Path(directory) / "checkpoint.json"
        path.write_text(
            json.dumps({"sourceId": SOURCE_ID, "status": "retry-pending"}),
            encoding="utf-8",
        )
        return path

    def test_pagination_requires_exact_identifier_count_and_order(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            path = self.pagination(directory)
            self.assertEqual(pagination_views(SOURCE_ID), 3)
            text = path.read_text(encoding="utf-8").replace(
                "bpt6k3373518k", "another-id"
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "identifier differs"):
                pagination_views(SOURCE_ID)
            path.write_text(
                '<!DOCTYPE x [<!ENTITY y "unsafe">]><livre></livre>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "DTD or entity"):
                pagination_views(SOURCE_ID)

    def test_cache_requires_jpeg_signature_and_optional_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "f1.jpg"
            path.write_bytes(JPEG)
            digest = hashlib.sha256(JPEG).hexdigest()
            self.assertTrue(valid_cached_view(path))
            self.assertTrue(valid_cached_view(path, digest))
            self.assertFalse(valid_cached_view(path, "0" * 64))
            path.write_bytes(b"not-jpeg")
            self.assertFalse(valid_cached_view(path))

    def test_only_checkpointed_cache_is_reusable(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            self.pagination(directory)
            source = (
                Path(directory)
                / "scouting-autoresearch"
                / "sources"
                / SOURCE_ID
            )
            unrecorded = source / "f1-1200.jpg"
            unrecorded.write_bytes(JPEG + b"unrecorded")
            recorded = source / "f2-1200.jpg"
            recorded.write_bytes(JPEG + b"recorded")
            digest = hashlib.sha256(recorded.read_bytes()).hexdigest()
            checkpoint = {
                "downloadedViewSmoke": [
                    {
                        "view": "f2",
                        "sha256": digest,
                        "retrievedAt": "2026-09-05T07:00:00+00:00",
                    }
                ]
            }
            self.assertIsNone(known_view_entry(checkpoint, 1))
            self.assertFalse(reusable_cached_view(checkpoint, SOURCE_ID, 1))
            self.assertEqual(known_view_entry(checkpoint, 2)["sha256"], digest)
            self.assertTrue(reusable_cached_view(checkpoint, SOURCE_ID, 2))
            recorded.write_bytes(JPEG + b"changed")
            self.assertFalse(reusable_cached_view(checkpoint, SOURCE_ID, 2))

    def test_next_view_and_success_checkpoint_are_resumable(self):
        item = load_approved_item(SOURCE_ID)
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            self.pagination(directory)
            checkpoint = self.checkpoint(directory)
            self.assertEqual(next_pending_view(json.loads(checkpoint.read_text()), SOURCE_ID, 3), 1)
            for view in range(1, 4):
                output = (
                    Path(directory)
                    / "scouting-autoresearch"
                    / "sources"
                    / SOURCE_ID
                    / f"f{view}-1200.jpg"
                )
                output.write_bytes(JPEG + bytes([view]))
                data = output.read_bytes()
                result = {
                    "url": artifact_url(item, "view", view),
                    "path": str(output),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "retrievedAt": "2026-09-05T07:00:00+00:00",
                    "reused": False,
                }
                complete = record_view_success(checkpoint, SOURCE_ID, 3, view, result)
                self.assertEqual(complete, view == 3)
            stored = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "views-fetched")
            self.assertEqual(stored["viewFetch"]["completedViews"], 3)
            self.assertIsNone(next_pending_view(stored, SOURCE_ID, 3))

    def test_reused_smoke_view_preserves_original_retrieval_time(self):
        item = load_approved_item(SOURCE_ID)
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRATCH": directory}
        ):
            self.pagination(directory, count=20)
            checkpoint = self.checkpoint(directory)
            payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            payload["downloadedViewSmoke"] = [
                {
                    "view": "f13",
                    "sha256": hashlib.sha256(JPEG).hexdigest(),
                    "retrievedAt": "2026-09-05T07:06:30+02:00",
                }
            ]
            checkpoint.write_text(json.dumps(payload), encoding="utf-8")
            output = (
                Path(directory)
                / "scouting-autoresearch"
                / "sources"
                / SOURCE_ID
                / "f13-1200.jpg"
            )
            output.write_bytes(JPEG)
            result = {
                "url": artifact_url(item, "view", 13),
                "path": str(output),
                "sha256": hashlib.sha256(JPEG).hexdigest(),
                "bytes": len(JPEG),
                "reused": True,
            }
            record_view_success(checkpoint, SOURCE_ID, 20, 13, result)
            stored = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(
                stored["viewFetch"]["items"][0]["retrievedAt"],
                "2026-09-05T07:06:30+02:00",
            )

    def test_view_error_has_its_own_retry_history(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = self.checkpoint(directory)
            retry_at = datetime(2026, 9, 5, 8, tzinfo=UTC)
            error = GallicaFetchError(
                "transient-http-429",
                {"httpStatus": 429, "headers": {}},
                retry_at,
            )
            record_view_error(
                checkpoint,
                error,
                1,
                datetime(2026, 9, 5, 7, tzinfo=UTC),
            )
            stored = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "retry-pending")
            self.assertEqual(stored["nextRetryAt"], retry_at.isoformat())
            attempt = stored["viewFetch"]["failedAttempts"][0]
            self.assertEqual(attempt["view"], 1)
            self.assertEqual(attempt["providerDiagnostics"], {"httpStatus": 429, "headers": {}})


if __name__ == "__main__":
    unittest.main()
