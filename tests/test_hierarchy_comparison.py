import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from render_hierarchy_comparison import build_payload, render_html


class HierarchyComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build_payload()

    def test_payload_covers_corpus_without_full_bodies_or_candidates(self):
        self.assertEqual(len(self.payload["points"]), 914)
        self.assertEqual(len({point["id"] for point in self.payload["points"]}), 914)
        self.assertTrue(self.payload["proposalOnly"])
        self.assertTrue(self.payload["projectionIsNavigationalOnly"])
        self.assertNotIn("algorithmicCandidates", self.payload)
        self.assertTrue(all("body" not in point for point in self.payload["points"]))
        self.assertTrue(
            all(relation["status"] == "human-approved" for relation in self.payload["approvedRelations"])
        )

    def test_both_blind_variants_assign_one_fine_and_top_cluster(self):
        variant_ids = {variant["id"] for variant in self.payload["variants"]}
        self.assertEqual(variant_ids, {"candidate-amber", "candidate-blue"})
        for point in self.payload["points"]:
            self.assertEqual(set(point["assignments"]), variant_ids)
            for assignment in point["assignments"].values():
                self.assertRegex(assignment["fine"], r"^fine-\d{2}$")
                self.assertRegex(assignment["top"], r"^top-\d{2}$")

    def test_html_is_self_contained_and_interactive(self):
        rendered = render_html(self.payload)
        self.assertIn('<script id="payload" type="application/json">', rendered)
        self.assertIn("candidate-amber", rendered)
        self.assertIn("candidate-blue", rendered)
        self.assertIn("Kółko myszy: zoom", rendered)
        self.assertNotIn("cdn.", rendered.lower())
        self.assertNotIn("<script src=", rendered.lower())


if __name__ == "__main__":
    unittest.main()
