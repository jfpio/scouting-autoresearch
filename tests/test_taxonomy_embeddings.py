import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import embed_taxonomy as taxonomy_embeddings
from embed_taxonomy import (
    build_embedding_input,
    cache_is_current,
    daily_usage,
    estimated_tokens,
    input_hash,
    next_daily_reset,
    prepare_context,
    recover_cached_items,
    retry_at,
)


class TaxonomyEmbeddingTests(unittest.TestCase):
    def test_input_preserves_source_traits_and_bounds_context(self):
        metadata = {
            "id": "pw-001",
            "kinds": ["trial"],
            "title": "Próba",
            "section": "Dział",
            "traits": ["Spryt", "cierpliwość"],
        }
        value = build_embedding_input(
            metadata,
            "  Pierwszy\n\n drugi akapit  ",
            15,
            "activity-context-v1",
        )
        self.assertIn("cechy źródłowe: Spryt | cierpliwość", value)
        self.assertIn("kontekst: Pierwszy drugi", value)
        self.assertFalse(value.endswith(" "))
        self.assertEqual(input_hash(value), input_hash(value))

    def test_token_estimate_uses_utf8_conservative_bound(self):
        self.assertEqual(estimated_tokens("abc"), 1)
        self.assertEqual(estimated_tokens("ąąą"), 2)

    def test_v2_context_removes_provenance_footer_and_markdown_urls(self):
        body = (
            "Idź według [szkicu drogi](https://example.test/route). "
            "![rysunek](https://example.test/image.jpg)\n\n"
            "---\n\n"
            "*Źródło skanu: [Biblioteka](https://example.test/record).*"
        )
        value = prepare_context(body, "activity-context-v2")
        self.assertEqual(value, "Idź według szkicu drogi. rysunek")
        self.assertNotIn("Źródło skanu", value)
        self.assertNotIn("https://", value)

    def test_recipe_version_changes_input_and_rejects_unknown_recipe(self):
        metadata = {
            "id": "hwp-001",
            "kinds": ["game"],
            "title": "Gra",
            "section": "Dział",
            "traits": [],
        }
        body = "Treść [odnośnika](https://example.test)."
        v1 = build_embedding_input(metadata, body, 600, "activity-context-v1")
        v2 = build_embedding_input(metadata, body, 600, "activity-context-v2")
        self.assertNotEqual(input_hash(v1), input_hash(v2))
        self.assertIn("https://example.test", v1)
        self.assertNotIn("https://example.test", v2)
        with self.assertRaises(ValueError):
            prepare_context(body, "activity-context-unknown")

    def test_cache_requires_matching_recipe_hash_and_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pw-001.json"
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "activityId": "pw-001",
                        "modelRequested": "mistral-embed-2312",
                        "recipeVersion": "activity-context-v1",
                        "inputHash": "abc",
                        "dimensions": 3,
                        "vector": [0.1, 0.2, 0.3],
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(
                cache_is_current(
                    path,
                    activity_id="pw-001",
                    model="mistral-embed-2312",
                    recipe_version="activity-context-v1",
                    expected_hash="abc",
                    dimensions=3,
                )
            )
            self.assertFalse(
                cache_is_current(
                    path,
                    activity_id="pw-001",
                    model="mistral-embed-2312",
                    recipe_version="activity-context-v2",
                    expected_hash="abc",
                    dimensions=3,
                )
            )

    def test_retry_never_precedes_twelve_hours(self):
        now = datetime(2026, 9, 2, tzinfo=UTC)
        self.assertEqual(retry_at(now, "60"), now + timedelta(hours=12))
        self.assertEqual(retry_at(now, str(13 * 60 * 60)), now + timedelta(hours=13))

    def test_daily_usage_uses_configured_local_date(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            first.write_text(
                json.dumps(
                    {
                        "batchId": "first",
                        "generatedAt": "2026-09-01T22:30:00+00:00",
                        "activityIds": ["hwp-001", "hwp-002"],
                        "usage": {"promptTokens": 100},
                    }
                ),
                encoding="utf-8",
            )
            second.write_text(
                json.dumps(
                    {
                        "batchId": "second",
                        "generatedAt": "2026-09-02T22:30:00+00:00",
                        "activityIds": ["hwp-003"],
                        "usage": {"promptTokens": 50},
                    }
                ),
                encoding="utf-8",
            )
            usage = daily_usage(
                [first, second],
                now=datetime(2026, 9, 2, 12, tzinfo=UTC),
                timezone_name="Europe/Warsaw",
                price_per_million_tokens=0.1,
            )
            self.assertEqual(usage["documents"], 2)
            self.assertEqual(usage["promptTokens"], 100)
            self.assertEqual(usage["batchIds"], ["first"])

    def test_next_daily_reset_is_local_midnight(self):
        reset = next_daily_reset(datetime(2026, 9, 2, 22, 30, tzinfo=UTC), "Europe/Warsaw")
        self.assertEqual(reset.isoformat(), "2026-09-04T00:00:00+02:00")

    def test_batch_ledger_can_recover_a_missing_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch_dir = root / "batches"
            batch_dir.mkdir()
            cache_path = root / "pw-001.json"
            payload = {
                "schemaVersion": 1,
                "activityId": "pw-001",
                "modelRequested": "mistral-embed-2312",
                "model": "mistral-embed-2312",
                "recipeVersion": "activity-context-v1",
                "inputHash": "abc",
                "dimensions": 3,
                "vector": [0.1, 0.2, 0.3],
            }
            (batch_dir / "batch.json").write_text(json.dumps({"items": [payload]}), encoding="utf-8")
            config = {
                "embedding": {
                    "model": "mistral-embed-2312",
                    "recipeVersion": "activity-context-v1",
                    "dimensions": 3,
                }
            }
            items = [{"id": "pw-001", "inputHash": "abc", "cachePath": cache_path}]
            with mock.patch.object(taxonomy_embeddings, "BATCH_DIR", batch_dir):
                self.assertEqual(recover_cached_items(config, items), 1)
            self.assertEqual(json.loads(cache_path.read_text(encoding="utf-8")), payload)


if __name__ == "__main__":
    unittest.main()
