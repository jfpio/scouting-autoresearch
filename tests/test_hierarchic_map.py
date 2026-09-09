import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_hierarchic_map import canonical_labels, fit_labels, source_concentration
from embed_semantic_map import load_config


class HierarchicMapTests(unittest.TestCase):
    def test_config_pins_hierarchy_parameters(self):
        pilot = load_config()["hierarchicPilot"]
        self.assertEqual(pilot["fineClusterCount"], 32)
        self.assertEqual(pilot["topClusterCount"], 8)
        self.assertEqual(pilot["kMeansNInit"], 50)
        self.assertEqual(pilot["minimumFineClusterSize"], 5)
        self.assertEqual(len(pilot["stabilitySeeds"]), 3)

    def test_kmeans_and_canonical_ids_are_deterministic(self):
        features = np.asarray(
            [[-2.0, 0.0], [-1.9, 0.1], [0.0, 2.0], [0.1, 1.9], [2.0, 0.0], [1.9, -0.1]]
        )
        ids = ["f", "e", "d", "c", "b", "a"]
        first, first_centroids = fit_labels(features, ids, 3, 7, 10)
        second, second_centroids = fit_labels(features, ids, 3, 7, 10)
        np.testing.assert_array_equal(first, second)
        np.testing.assert_allclose(first_centroids, second_centroids)
        self.assertEqual(set(first.tolist()), {0, 1, 2})

    def test_canonical_labels_ignore_arbitrary_model_numbers(self):
        features = np.asarray([[5.0], [5.1], [-5.0], [-5.1]])
        ids = ["b", "a", "d", "c"]
        left = canonical_labels(np.asarray([9, 9, 3, 3]), features, ids)
        right = canonical_labels(np.asarray([1, 1, 8, 8]), features, ids)
        np.testing.assert_array_equal(left, right)

    def test_source_concentration_has_bounded_metrics(self):
        metrics = source_concentration(
            np.asarray([0, 0, 1, 1]), ["a", "b", "a", "a"]
        )
        self.assertGreaterEqual(metrics["meanLargestSourceShare"], 0)
        self.assertLessEqual(metrics["maximumLargestSourceShare"], 1)
        self.assertGreaterEqual(metrics["meanNormalizedSourceEntropy"], 0)
        self.assertLessEqual(metrics["meanNormalizedSourceEntropy"], 1)


if __name__ == "__main__":
    unittest.main()
