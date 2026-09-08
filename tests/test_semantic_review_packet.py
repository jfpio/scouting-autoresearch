import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_semantic_review_packet import (
    build_checkpoint,
    build_markdown,
    build_report,
    load_config,
)


class SemanticReviewPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.report = build_report(cls.config)
        cls.note = build_markdown(cls.report)

    def test_packet_contains_all_pending_pairs_without_production_links(self):
        self.assertEqual(self.report["selection"]["candidateCount"], 50)
        self.assertEqual(len(self.report["candidates"]), 50)
        self.assertTrue(self.report["proposalOnly"])
        self.assertTrue(self.report["humanApprovalRequired"])
        self.assertFalse(self.report["publicSiteExposure"])
        self.assertEqual(self.report["productionRelationsWritten"], [])
        self.assertTrue(
            all(
                candidate["status"] == "human-review-required"
                and candidate["reviewRequired"]
                and not candidate["productionRelation"]
                and candidate["humanDecision"]["status"] == "pending"
                and candidate["humanDecision"]["outcome"] is None
                for candidate in self.report["candidates"]
            )
        )

    def test_top_pair_has_bilingual_context_and_reciprocal_rank_one(self):
        candidate = self.report["candidates"][0]
        self.assertEqual(candidate["activityIds"], ["ciz-042", "shc-035"])
        self.assertEqual(candidate["neighborRanks"], {"ciz-042": 1, "shc-035": 1})
        self.assertEqual(candidate["cosineSimilarity"], 0.99924048)
        self.assertEqual(
            [activity["localized"]["en"]["title"] for activity in candidate["activities"]],
            ["Fox Hunt", "Fox Hunt"],
        )
        for activity in candidate["activities"]:
            self.assertTrue(activity["localized"]["pl"]["summary"])
            self.assertTrue(activity["localized"]["en"]["summary"])

    def test_pairs_are_unique_cross_source_and_mutual(self):
        pairs = [frozenset(candidate["activityIds"]) for candidate in self.report["candidates"]]
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertTrue(
            all(len(set(candidate["sourceIds"])) == 2 for candidate in self.report["candidates"])
        )
        self.assertTrue(
            all(
                set(candidate["neighborRanks"]) == set(candidate["activityIds"])
                and all(1 <= rank <= 10 for rank in candidate["neighborRanks"].values())
                for candidate in self.report["candidates"]
            )
        )

    def test_review_note_marks_source_data_and_decisions(self):
        self.assertIn("niezaufanymi danymi źródłowymi", self.note)
        self.assertEqual(self.note.count("**Decyzja człowieka:** `pending`"), 50)
        self.assertEqual(self.note.count("**Uzasadnienie:** —"), 50)
        self.assertIn("../../activities/ciz-042.md", self.note)
        self.assertIn("../../activities/shc-035.md", self.note)

    def test_config_rejects_public_exposure_and_partial_selection(self):
        config = copy.deepcopy(self.config)
        config["publicSiteExposure"] = True
        with self.assertRaisesRegex(ValueError, "public site"):
            build_report(config)
        config = copy.deepcopy(self.config)
        config["candidateSelection"] = "top-five"
        with self.assertRaisesRegex(ValueError, "silently select"):
            build_report(config)

    def test_checkpoint_is_deterministic_and_preserves_gate(self):
        checkpoint = build_checkpoint(self.config, self.report, self.note)
        self.assertEqual(
            checkpoint,
            build_checkpoint(
                self.config,
                build_report(self.config),
                build_markdown(build_report(self.config)),
            ),
        )
        self.assertEqual(checkpoint["candidateCount"], 50)
        self.assertTrue(checkpoint["humanApprovalRequired"])
        self.assertFalse(checkpoint["publicSiteExposure"])
        self.assertEqual(checkpoint["productionRelationsWritten"], [])


if __name__ == "__main__":
    unittest.main()
