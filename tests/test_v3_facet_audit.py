import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_v3_facets import (
    build_checkpoint,
    build_report,
    deterministic_sample,
    load_config,
    load_game_records,
)


class V3FacetAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.records = load_game_records()
        cls.report = build_report(cls.config, cls.records)

    def dimension(self, dimension_id):
        return next(
            item
            for item in self.report["dimensions"]
            if item["dimensionId"] == dimension_id
        )

    def value_ids(self, dimension_id, value_id):
        value = next(
            item
            for item in self.dimension(dimension_id)["values"]
            if item["valueId"] == value_id
        )
        return set(value["activityIds"])

    def test_report_covers_all_games_without_assigning_facets(self):
        self.assertEqual(len(self.records), 199)
        self.assertEqual(
            self.report["corpus"]["activityIds"],
            sorted(record["activityId"] for record in self.records),
        )
        self.assertEqual(len(self.report["dimensions"]), 12)
        self.assertTrue(self.report["proposalOnly"])
        self.assertTrue(self.report["humanReviewRequired"])
        self.assertFalse(self.report["signalsAreAssignments"])
        self.assertEqual(self.report["productionFieldsWritten"], [])
        self.assertEqual(self.report["execution"]["externalApiRequests"], 0)
        self.assertEqual(self.report["execution"]["referenceCostUsd"], 0)

    def test_known_phrases_surface_as_review_evidence_only(self):
        self.assertIn("bsh-037", self.value_ids("dominant-mechanic", "chase-capture"))
        self.assertIn("bsh-037", self.value_ids("light-weather-season", "night-darkness"))
        self.assertIn("hwp-041", self.value_ids("equipment", "portable-items"))
        self.assertIn(
            "sfb-033", self.value_ids("physical-contact-risk", "physical-contact")
        )
        for dimension in self.report["dimensions"]:
            self.assertEqual(
                dimension["humanSearchValueAssessment"]["status"],
                "human-rating-required",
            )
            self.assertIsNone(dimension["humanSearchValueAssessment"]["scores"])
            self.assertTrue(
                dimension["editorialCostProxy"][
                    "manualVerificationRequiredForEveryAssignment"
                ]
            )
            self.assertIsNone(dimension["editorialCostProxy"]["estimatedMinutes"])

    def test_report_exposes_source_bias_and_non_user_value_proxies(self):
        for dimension in self.report["dimensions"]:
            self.assertEqual(len(dimension["signalCoverage"]["bySource"]), 3)
            self.assertEqual(len(dimension["signalCoverage"]["byLanguage"]), 2)
            self.assertIn(
                "not-observed-user-value",
                dimension["searchDifferentiationProxy"]["interpretation"],
            )
            self.assertIn(
                "not-necessarily-conflicts",
                dimension["ambiguityProxy"]["interpretation"],
            )

    def test_deterministic_samples_are_order_independent(self):
        left = deterministic_sample(["c", "a", "b", "d"], 2, "facet")
        right = deterministic_sample(["b", "d", "a", "c"], 2, "facet")
        self.assertEqual(left, right)
        self.assertEqual(len(left), 2)

    def test_config_cannot_turn_signals_into_assignments(self):
        config = copy.deepcopy(self.config)
        config["signalsAreAssignments"] = True
        with self.assertRaisesRegex(ValueError, "may not become"):
            build_report(config, self.records)

    def test_empty_pattern_cannot_match_the_corpus(self):
        config = copy.deepcopy(self.config)
        config["dimensions"][0]["values"][0]["patterns"]["pl"][0]["regex"] = ""
        with self.assertRaisesRegex(ValueError, "empty pl regex"):
            build_report(config, self.records)

    def test_checkpoint_is_deterministic_and_human_gated(self):
        checkpoint = build_checkpoint(self.report)
        self.assertEqual(
            checkpoint,
            build_checkpoint(build_report(self.config, self.records)),
        )
        self.assertEqual(checkpoint["status"], "human-review-required")
        self.assertEqual(checkpoint["dimensionCount"], 12)
        self.assertTrue(checkpoint["humanReviewRequired"])
        self.assertEqual(checkpoint["productionFieldsWritten"], [])


if __name__ == "__main__":
    unittest.main()
