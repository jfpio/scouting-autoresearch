import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_taxonomy import (
    agglomerative_clusters,
    build_analysis,
    cosine_similarity,
    pairwise_similarities,
    write_analysis_checkpoint,
)


class TaxonomyAnalysisTests(unittest.TestCase):
    def test_cosine_similarity_rejects_zero_vectors(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [1.0, 1.0]), 2**-0.5)
        with self.assertRaises(ValueError):
            cosine_similarity([0.0, 0.0], [1.0, 0.0])

    def test_average_linkage_is_deterministic(self):
        vectors = {
            "a": [1.0, 0.0],
            "b": [0.99, 0.01],
            "c": [0.0, 1.0],
            "d": [0.01, 0.99],
        }
        similarities = pairwise_similarities(vectors)
        self.assertEqual(
            agglomerative_clusters(list(reversed(vectors)), similarities, 2),
            [("a", "b"), ("c", "d")],
        )

    def test_partial_report_is_proposal_only_and_preserves_traits(self):
        parameters = {
            "algorithmVersion": "test-v1",
            "targetClusterCount": 2,
            "nearestNeighborCount": 2,
            "ambiguityMargin": 0.03,
            "outlierIqrMultiplier": 1.5,
        }
        caches = [
            {
                "activityId": activity_id,
                "sourceId": "source-1",
                "sourceTraits": traits,
                "modelRequested": "mistral-embed-2312",
                "model": "mistral-embed-2312",
                "dimensions": 2,
                "recipeVersion": "activity-context-v1",
                "inputHash": f"hash-{activity_id}",
                "generatedAt": "2026-09-02T12:00:00+00:00",
                "vector": vector,
            }
            for activity_id, traits, vector in (
                ("a", ["Źródłowa"], [1.0, 0.0]),
                ("b", [], [0.9, 0.1]),
                ("c", ["Inna"], [0.0, 1.0]),
            )
        ]
        report = build_analysis(
            caches,
            all_activity_ids=["a", "b", "c", "d"],
            parameters=parameters,
            usage={"promptTokens": 10, "estimatedCostUsd": 0.000001},
        )
        self.assertEqual(report["status"], "partial")
        self.assertTrue(report["proposalOnly"])
        self.assertTrue(report["reviewRequired"])
        self.assertFalse(report["productionTaxonomyChanged"])
        self.assertEqual(report["coverage"]["missingActivityIds"], ["d"])
        self.assertEqual(report["items"][0]["sourceTraits"], ["Źródłowa"])
        self.assertEqual(report["unassignedProductionCategoryActivityIds"], ["a", "b", "c"])
        singleton = next(item for item in report["ambiguousAssignments"] if item["activityId"] == "c")
        self.assertEqual(singleton["reason"], "singleton-cluster")
        self.assertIsNone(singleton["margin"])

    def test_analysis_hash_is_deterministic(self):
        parameters = {
            "algorithmVersion": "test-v1",
            "targetClusterCount": 1,
            "nearestNeighborCount": 1,
            "ambiguityMargin": 0.03,
            "outlierIqrMultiplier": 1.5,
        }
        caches = [
            {
                "activityId": activity_id,
                "sourceId": "source-1",
                "sourceTraits": [],
                "modelRequested": "model",
                "model": "model",
                "dimensions": 2,
                "recipeVersion": "recipe",
                "inputHash": activity_id,
                "generatedAt": "2026-09-02T12:00:00+00:00",
                "vector": vector,
            }
            for activity_id, vector in (("a", [1.0, 0.0]), ("b", [0.0, 1.0]))
        ]
        first = build_analysis(caches, all_activity_ids=["a", "b"], parameters=parameters, usage={})
        second = build_analysis(list(reversed(caches)), all_activity_ids=["b", "a"], parameters=parameters, usage={})
        self.assertEqual(first["analysisHash"], second["analysisHash"])
        self.assertEqual(first, second)

    def test_analysis_checkpoint_preserves_cycle_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            path.write_text(
                json.dumps({"status": "daily-limit-reached", "nextCycleAt": "tomorrow"}),
                encoding="utf-8",
            )
            write_analysis_checkpoint(
                {
                    "status": "partial",
                    "analysisHash": "abc",
                    "algorithmVersion": "test-v1",
                    "generatedAt": "2026-09-02T12:00:00+00:00",
                    "coverage": {"embeddedActivities": 20, "totalActivities": 202},
                },
                path,
            )
            checkpoint = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint["status"], "daily-limit-reached")
            self.assertEqual(checkpoint["nextCycleAt"], "tomorrow")
            self.assertEqual(checkpoint["analysis"]["analysisHash"], "abc")


if __name__ == "__main__":
    unittest.main()
