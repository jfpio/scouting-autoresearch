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
    estimated_tokens,
    input_hash,
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
        value = build_embedding_input(metadata, "  Pierwszy\n\n drugi akapit  ", 15)
        self.assertIn("cechy źródłowe: Spryt | cierpliwość", value)
        self.assertIn("kontekst: Pierwszy drugi", value)
        self.assertFalse(value.endswith(" "))
        self.assertEqual(input_hash(value), input_hash(value))

    def test_token_estimate_uses_utf8_conservative_bound(self):
        self.assertEqual(estimated_tokens("abc"), 1)
        self.assertEqual(estimated_tokens("ąąą"), 2)

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
