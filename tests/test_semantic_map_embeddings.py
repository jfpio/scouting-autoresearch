import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from embed_semantic_map import (
    activity_items,
    build_embedding_input,
    build_progress_report,
    cache_is_current,
    canonical_hash,
    load_config,
    source_selection,
)


class SemanticMapEmbeddingTests(unittest.TestCase):
    def test_recipe_contains_both_languages_and_bounds_clean_context(self):
        embedding = {
            "sourceContextCharacters": 20,
            "parallelContextCharacters": 12,
        }
        value = build_embedding_input(
            {"originalLanguage": "en", "title": "Source title"},
            "Source [body](https://example.test) with extra words.",
            {"locale": "pl", "title": "Tytuł"},
            "Polski tekst i dalszy kontekst.",
            embedding,
        )
        self.assertIn("original-title: Source title", value)
        self.assertIn("original-context: Source body with ext", value)
        self.assertIn("parallel-title: Tytuł", value)
        self.assertIn("parallel-context: Polski tekst", value)
        self.assertNotIn("https://", value)

    def test_current_corpus_contains_every_game_and_no_trial(self):
        config = load_config()
        items = activity_items(config)
        self.assertEqual(len(items), 199)
        self.assertEqual(len({item["id"] for item in items}), 199)
        self.assertNotIn("pw-001", {item["id"] for item in items})
        self.assertEqual(items[0]["sourceId"], "bsh-1911-seton-games")
        self.assertLessEqual(
            max(item["estimatedInputTokens"] for item in items),
            config["embedding"]["modelMaxInputTokens"],
        )

    def test_translation_change_invalidates_input_hash(self):
        embedding = {
            "sourceContextCharacters": 200,
            "parallelContextCharacters": 200,
        }
        source = {"originalLanguage": "en", "title": "Game"}
        parallel = {"locale": "pl", "title": "Gra"}
        first = build_embedding_input(source, "Run.", parallel, "Biegnij.", embedding)
        second = build_embedding_input(source, "Run.", parallel, "Idź.", embedding)
        self.assertNotEqual(canonical_hash(first), canonical_hash(second))

    def test_source_selection_never_spills_into_another_book(self):
        config = {"corpus": {"sourceOrder": ["a", "b"]}}
        items = [
            {"id": "a-1", "sourceId": "a"},
            {"id": "a-2", "sourceId": "a"},
            {"id": "b-1", "sourceId": "b"},
        ]
        source_id, selected = source_selection(config, items, {"a-1"}, None)
        self.assertEqual(source_id, "a")
        self.assertEqual([item["id"] for item in selected], ["a-2"])

    def test_cache_namespace_requires_v3_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bsh-001.json"
            item = {
                "id": "bsh-001",
                "sourceId": "source",
                "sourceHash": "source-hash",
                "inputHash": "input-hash",
                "input": "input",
            }
            embedding = {
                "model": "mistral-embed-2312",
                "recipeVersion": "bilingual-game-context-v1",
                "dimensions": 3,
            }
            payload = {
                "schemaVersion": 1,
                "pipeline": "semantic-map-v3-embeddings",
                "activityId": "bsh-001",
                "sourceId": "source",
                "sourceHash": "source-hash",
                "modelRequested": "mistral-embed-2312",
                "model": "mistral-embed-2312",
                "recipeVersion": "bilingual-game-context-v1",
                "inputHash": "input-hash",
                "input": "input",
                "dimensions": 3,
                "vector": [0.1, 0.2, 0.3],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(cache_is_current(path, item, embedding))
            path.write_text(json.dumps({**payload, "pipeline": "taxonomy-v1-embeddings"}), encoding="utf-8")
            self.assertFalse(cache_is_current(path, item, embedding))

    def test_config_rejects_non_education_or_unbounded_execution(self):
        config = load_config()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            import yaml

            bad = copy.deepcopy(config)
            bad["execution"]["billingMode"] = "experimental-no-charge"
            path.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Education"):
                load_config(path)
            bad = copy.deepcopy(config)
            bad["execution"]["maxTotalReferenceCostUsd"] = 10.01
            path.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "at most 10"):
                load_config(path)

    def test_progress_report_keeps_source_completion_and_unknown_billed_cost(self):
        config = load_config()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            items = [
                {
                    "id": "a-1",
                    "sourceId": "bsh-1911-seton-games",
                    "sourceHash": "s",
                    "inputHash": "i",
                    "input": "input",
                    "cachePath": root / "a-1.json",
                }
            ]
            cache = {
                "schemaVersion": 1,
                "pipeline": "semantic-map-v3-embeddings",
                "activityId": "a-1",
                "sourceId": "bsh-1911-seton-games",
                "sourceHash": "s",
                "modelRequested": config["embedding"]["model"],
                "model": config["embedding"]["model"],
                "recipeVersion": config["embedding"]["recipeVersion"],
                "inputHash": "i",
                "input": "input",
                "dimensions": config["embedding"]["dimensions"],
                "vector": [0.0] * config["embedding"]["dimensions"],
            }
            items[0]["cachePath"].write_text(json.dumps(cache), encoding="utf-8")
            reduced_config = copy.deepcopy(config)
            reduced_config["corpus"]["sourceOrder"] = ["bsh-1911-seton-games"]
            report = build_progress_report(
                reduced_config,
                items,
                [
                    {
                        "batchId": "batch",
                        "activityIds": ["a-1"],
                        "usage": {
                            "promptTokens": 10,
                            "billedCostUsd": None,
                            "referenceCostUsd": 0.000001,
                        },
                    }
                ],
                generated_at="2026-09-04T00:00:00+00:00",
            )
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["sources"][0]["status"], "complete")
            self.assertIsNone(report["usage"]["billedCostUsd"])


if __name__ == "__main__":
    unittest.main()
