import sys
import unittest
import json
import copy
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_semantic_map import (
    algorithmic_candidates,
    cosine_similarities,
    load_config,
    nearest_neighbors,
    portable_report_view,
)


class SemanticMapAnalysisTests(unittest.TestCase):
    def test_config_pins_reproducible_umap(self):
        analysis = load_config()["analysis"]
        self.assertEqual(analysis["projectionAlgorithm"], "umap")
        self.assertEqual(analysis["projectionLibrary"], "umap-learn")
        self.assertEqual(str(analysis["projectionVersion"]), "0.5.12")
        self.assertEqual(analysis["distanceMetric"], "cosine")
        self.assertEqual(analysis["projectionDimensions"], 2)
        self.assertEqual(len(analysis["stabilitySeeds"]), 3)

    def test_cosine_neighbours_are_deterministic_and_tie_break_by_id(self):
        activity_ids = ["a", "b", "c"]
        vectors = np.asarray([[1.0, 0.0], [0.0, 1.0], [0.0, -1.0]])
        records, ranks = nearest_neighbors(
            activity_ids, cosine_similarities(vectors), count=2
        )
        self.assertEqual(
            [neighbor["activityId"] for neighbor in records[0]["neighbors"]],
            ["b", "c"],
        )
        self.assertEqual(ranks["a"], {"b": 1, "c": 2})
        self.assertEqual(records[1]["neighbors"][0]["activityId"], "a")

    def test_candidates_are_cross_source_mutual_and_not_approved(self):
        records = [
            {
                "activityId": "a",
                "neighbors": [
                    {"activityId": "b", "cosineSimilarity": 0.9},
                    {"activityId": "c", "cosineSimilarity": 0.8},
                ],
            },
            {
                "activityId": "b",
                "neighbors": [{"activityId": "a", "cosineSimilarity": 0.9}],
            },
            {
                "activityId": "c",
                "neighbors": [{"activityId": "a", "cosineSimilarity": 0.8}],
            },
        ]
        candidates = algorithmic_candidates(
            records,
            {"a": "one", "b": "two", "c": "one"},
            {frozenset(("a", "b"))},
            limit=10,
        )
        self.assertEqual(candidates, [])
        candidates = algorithmic_candidates(
            records,
            {"a": "one", "b": "two", "c": "three"},
            set(),
            limit=1,
        )
        self.assertEqual(candidates[0]["activityIds"], ["a", "b"])
        self.assertEqual(candidates[0]["status"], "algorithmic-candidate")
        self.assertTrue(candidates[0]["reviewRequired"])
        self.assertFalse(candidates[0]["productionRelation"])

    def test_committed_report_keeps_candidates_out_of_production(self):
        report_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "reports"
            / "semantic-map-v3-analysis.json"
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "proposal-only")
        self.assertTrue(report["proposalOnly"])
        self.assertTrue(report["reviewRequired"])
        self.assertEqual(report["productionRelationsWritten"], [])
        self.assertEqual(len(report["points"]), 199)
        self.assertEqual(len(report["nearestNeighbors"]), 199)
        self.assertTrue(report["algorithmicCandidates"])
        self.assertTrue(
            all(
                candidate["reviewRequired"]
                and not candidate["productionRelation"]
                for candidate in report["algorithmicCandidates"]
            )
        )

    def test_portable_view_ignores_only_projection_specific_values(self):
        report = {
            "corpus": {"corpusDigest": "stable"},
            "quality": {
                "trustworthinessAtK": 0.7,
                "crossSourceDirectedNeighborRate": 0.3,
                "nearestNeighborSimilarity": {"mean": 0.8},
                "stabilityRuns": [{"seed": 1}],
                "minimumSpearmanPairwiseDistanceCorrelation": 0.8,
                "minimumMeanNeighborRetentionAtK": 0.5,
            },
            "points": [
                {
                    "activityId": "a",
                    "sourceHash": "source",
                    "inputHash": "input",
                    "x": 1.0,
                    "y": 2.0,
                }
            ],
            "nearestNeighbors": [
                {"activityId": "a", "neighbors": [{"activityId": "b"}]}
            ],
            "approvedRelationOverlays": [
                {
                    "relationId": "rel",
                    "cosineSimilarity": 0.9,
                    "projectedDistance": 1.2,
                }
            ],
        }
        changed_projection = copy.deepcopy(report)
        changed_projection["points"][0]["x"] = 99.0
        changed_projection["quality"]["trustworthinessAtK"] = 0.1
        changed_projection["approvedRelationOverlays"][0]["projectedDistance"] = 88.0
        self.assertEqual(
            portable_report_view(report), portable_report_view(changed_projection)
        )

        changed_semantics = copy.deepcopy(report)
        changed_semantics["nearestNeighbors"][0]["neighbors"][0]["activityId"] = "c"
        self.assertNotEqual(
            portable_report_view(report), portable_report_view(changed_semantics)
        )


if __name__ == "__main__":
    unittest.main()
