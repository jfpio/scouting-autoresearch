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
    batch_reference_cost,
    build_embedding_input,
    cache_is_current,
    checkpoint_identity,
    estimated_tokens,
    input_hash,
    pending_recipe_migration_ids,
    prepare_context,
    recover_cached_items,
    recipe_execution_block_reason,
    restrict_to_current_source,
    restrict_to_recipe_migration,
    retry_at,
    summarize_batch_usage,
    update_checkpoint,
    write_retry_checkpoint,
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

    def test_pending_recipe_upgrade_blocks_old_recipe_but_allows_candidate(self):
        audit = {
            "status": "recipe-upgrade-pending",
            "activeRecipeVersion": "activity-context-v1",
            "candidateRecipeVersion": "activity-context-v2",
        }
        reason = recipe_execution_block_reason(
            {"recipeVersion": "activity-context-v1"},
            audit,
        )
        self.assertIn("activity-context-v2", reason or "")
        self.assertIsNone(
            recipe_execution_block_reason(
                {"recipeVersion": "activity-context-v2"},
                audit,
            )
        )
        self.assertIsNone(
            recipe_execution_block_reason(
                {"recipeVersion": "activity-context-v1"},
                {**audit, "status": "ready"},
            )
        )

    def test_partial_recipe_migration_never_spills_into_new_activities(self):
        audit = {
            "candidateRecipeVersion": "activity-context-v2",
            "remediation": {
                "reembedBeforeNewActivities": ["hwp-001", "hwp-002", "hwp-003"]
            },
        }
        migration_ids = pending_recipe_migration_ids(
            {"recipeVersion": "activity-context-v2"},
            audit,
            {"hwp-001"},
        )
        self.assertEqual(migration_ids, ["hwp-002", "hwp-003"])
        pending = [
            {"id": activity_id}
            for activity_id in ("hwp-002", "hwp-003", "hwp-021", "hwp-022")
        ]
        migration, deferred = restrict_to_recipe_migration(pending, migration_ids)
        self.assertEqual([item["id"] for item in migration], ["hwp-002", "hwp-003"])
        self.assertEqual(deferred, ["hwp-021", "hwp-022"])
        self.assertEqual(
            pending_recipe_migration_ids(
                {"recipeVersion": "activity-context-v2"},
                audit,
                {"hwp-001", "hwp-002", "hwp-003"},
            ),
            [],
        )

    def test_request_never_spills_into_the_next_source(self):
        pending = [
            {"id": "hwp-116", "sourceId": "hwp-1946"},
            {"id": "hwp-117", "sourceId": "hwp-1946"},
            {"id": "pw-001", "sourceId": "pw-1935"},
        ]
        current_source, deferred = restrict_to_current_source(pending)
        self.assertEqual([item["id"] for item in current_source], ["hwp-116", "hwp-117"])
        self.assertEqual([item["id"] for item in deferred], ["pw-001"])

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

    def test_retry_checkpoint_preserves_embedding_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint_path = Path(directory) / "checkpoint.json"
            checkpoint_path.write_text(
                json.dumps(
                    {
                        "status": "source-batch-complete",
                        "repository": {"lastPushedCommit": "abc"},
                    }
                ),
                encoding="utf-8",
            )
            identity = checkpoint_identity(
                {
                    "model": "mistral-embed-2312",
                    "recipeVersion": "activity-context-v2",
                    "dimensions": 1024,
                }
            )
            with mock.patch.object(taxonomy_embeddings, "CHECKPOINT_PATH", checkpoint_path):
                write_retry_checkpoint(
                    now=datetime(2026, 9, 3, tzinfo=UTC),
                    reason="mistral-http-429",
                    identity=identity,
                )
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint["status"], "retry-pending")
            self.assertEqual(checkpoint["nextRetryAt"], "2026-09-03T12:00:00+00:00")
            self.assertEqual(checkpoint["repository"], {"lastPushedCommit": "abc"})
            self.assertEqual(
                {key: checkpoint[key] for key in identity},
                identity,
            )

    def test_checkpoint_merge_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            path.write_text(
                json.dumps(
                    {
                        "status": "retry-pending",
                        "nextRetryAt": "2026-09-03T12:00:00+00:00",
                        "repository": {"lastPushedCommit": "abc"},
                    }
                ),
                encoding="utf-8",
            )
            checkpoint = update_checkpoint(
                {"status": "source-batch-complete", "nextActivityId": "hwp-051"},
                remove_keys=("nextRetryAt",),
                path=path,
            )
            self.assertEqual(checkpoint["repository"], {"lastPushedCommit": "abc"})
            self.assertNotIn("nextRetryAt", checkpoint)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), checkpoint)

    def test_reference_cost_falls_back_to_prompt_token_estimate(self):
        batch = {"usage": {"promptTokens": 250}}
        self.assertEqual(batch_reference_cost(batch, 0.2), 0.00005)

    def test_batch_usage_is_grouped_by_recipe_without_hiding_superseded_cost(self):
        batches = [
            {
                "batchId": "v1-batch-b",
                "recipeVersion": "activity-context-v1",
                "activityIds": ["hwp-002"],
                "usage": {"promptTokens": 40, "billedCostUsd": 0.0, "referenceCostUsd": 0.000004},
            },
            {
                "batchId": "v1-batch-a",
                "recipeVersion": "activity-context-v1",
                "activityIds": ["hwp-001"],
                "usage": {"promptTokens": 60, "billedCostUsd": 0.0, "referenceCostUsd": 0.000012},
            },
            {
                "batchId": "v2-batch",
                "recipeVersion": "activity-context-v2",
                "activityIds": ["hwp-001", "hwp-002", "hwp-003"],
                "usage": {"promptTokens": 150, "billedCostUsd": 0.0, "referenceCostUsd": 0.00003},
            },
        ]
        usage = summarize_batch_usage(list(reversed(batches)), 0.1)
        self.assertEqual(usage["documentsProcessed"], 5)
        self.assertEqual(usage["promptTokens"], 250)
        self.assertEqual(usage["billedCostUsd"], 0.0)
        self.assertEqual(usage["referenceCostUsd"], 0.000046)
        self.assertEqual(
            usage["byRecipe"],
            [
                {
                    "recipeVersion": "activity-context-v1",
                    "batchIds": ["v1-batch-a", "v1-batch-b"],
                    "documents": 2,
                    "promptTokens": 100,
                    "billedCostUsd": 0.0,
                    "referenceCostUsd": 0.000016,
                },
                {
                    "recipeVersion": "activity-context-v2",
                    "batchIds": ["v2-batch"],
                    "documents": 3,
                    "promptTokens": 150,
                    "billedCostUsd": 0.0,
                    "referenceCostUsd": 0.00003,
                },
            ],
        )

    def test_unknown_metered_cost_is_not_reported_as_zero(self):
        usage = summarize_batch_usage(
            [
                {
                    "batchId": "metered",
                    "recipeVersion": "activity-context-v2",
                    "activityIds": ["hwp-001"],
                    "usage": {"promptTokens": 100, "referenceCostUsd": 0.00001},
                }
            ],
            0.1,
        )
        self.assertIsNone(usage["billedCostUsd"])
        self.assertIsNone(usage["byRecipe"][0]["billedCostUsd"])
        self.assertEqual(usage["referenceCostUsd"], 0.00001)

    def test_batch_ledger_recovers_missing_and_superseded_caches_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch_dir = root / "batches"
            batch_dir.mkdir()
            cache_paths = [root / "pw-001.json", root / "pw-002.json"]
            payloads = [
                {
                    "schemaVersion": 1,
                    "activityId": activity_id,
                    "modelRequested": "mistral-embed-2312",
                    "model": "mistral-embed-2312",
                    "recipeVersion": "activity-context-v2",
                    "inputHash": expected_hash,
                    "dimensions": 3,
                    "vector": vector,
                }
                for activity_id, expected_hash, vector in (
                    ("pw-001", "v2-a", [0.1, 0.2, 0.3]),
                    ("pw-002", "v2-b", [0.4, 0.5, 0.6]),
                )
            ]
            batch_path = batch_dir / "batch.json"
            batch_path.write_text(
                json.dumps({"batchId": "v2-batch", "items": payloads}),
                encoding="utf-8",
            )
            cache_paths[0].write_text(
                json.dumps(
                    {
                        **payloads[0],
                        "recipeVersion": "activity-context-v1",
                        "inputHash": "v1-a",
                    }
                ),
                encoding="utf-8",
            )
            config = {
                "embedding": {
                    "model": "mistral-embed-2312",
                    "recipeVersion": "activity-context-v2",
                    "dimensions": 3,
                }
            }
            items = [
                {"id": payload["activityId"], "inputHash": payload["inputHash"], "cachePath": path}
                for payload, path in zip(payloads, cache_paths, strict=True)
            ]
            with mock.patch.object(taxonomy_embeddings, "BATCH_DIR", batch_dir):
                self.assertEqual(recover_cached_items(config, items), 2)
            self.assertEqual(
                [json.loads(path.read_text(encoding="utf-8")) for path in cache_paths],
                payloads,
            )
            self.assertNotIn("items", json.loads(batch_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
