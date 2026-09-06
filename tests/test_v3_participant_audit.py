import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_v3_participants import build_checkpoint, build_report, load_config, load_game_records


class V3ParticipantAuditTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.records = load_game_records()
        self.report = build_report(self.config, self.records)

    def scale_ids(self, scale_id):
        scale = next(item for item in self.report["scales"] if item["scaleId"] == scale_id)
        return set(scale["activityIds"])

    def test_report_covers_exactly_all_source_games_without_assigning_scales(self):
        self.assertEqual(
            self.report["corpus"]["activityIds"],
            sorted(record["activityId"] for record in self.records),
        )
        self.assertTrue(self.report["proposalOnly"])
        self.assertTrue(self.report["humanReviewRequired"])
        self.assertFalse(self.report["signalsAreAssignments"])
        self.assertEqual(self.report["productionFieldsWritten"], [])
        self.assertEqual(self.report["execution"]["externalApiRequests"], 0)
        self.assertEqual(self.report["execution"]["referenceCostUsd"], 0)
        self.assertFalse(self.report["numericParticipantSignals"]["minParticipantsWritten"])
        self.assertFalse(self.report["numericParticipantSignals"]["maxParticipantsWritten"])

    def test_known_source_phrases_are_only_lexical_signals(self):
        self.assertIn("bsh-037", self.scale_ids("pair"))
        self.assertIn("bsh-037", self.scale_ids("single-patrol"))
        self.assertIn("bsh-037", self.scale_ids("single-troop"))
        self.assertIn("hwp-019", self.scale_ids("multiple-patrols"))
        self.assertIn("sfb-033", self.scale_ids("pair"))
        numeric_ids = set(self.report["numericParticipantSignals"]["activityIds"])
        self.assertIn("bsh-037", numeric_ids)
        self.assertIn("hwp-019", numeric_ids)
        self.assertIn("sfb-033", numeric_ids)

    def test_config_cannot_turn_signals_into_production_assignments(self):
        config = copy.deepcopy(self.config)
        config["signalsAreAssignments"] = True
        with self.assertRaisesRegex(ValueError, "may not become"):
            build_report(config, self.records)

    def test_empty_pattern_cannot_silently_match_the_whole_corpus(self):
        config = copy.deepcopy(self.config)
        config["scales"][0]["patterns"]["pl"][0]["regex"] = ""
        with self.assertRaisesRegex(ValueError, "empty pl regex"):
            build_report(config, self.records)

    def test_checkpoint_is_deterministic_and_human_gated(self):
        checkpoint = build_checkpoint(self.report)
        self.assertEqual(checkpoint, build_checkpoint(build_report(self.config, self.records)))
        self.assertEqual(checkpoint["status"], "human-review-required")
        self.assertTrue(checkpoint["humanReviewRequired"])
        self.assertEqual(checkpoint["productionFieldsWritten"], [])
        self.assertEqual(checkpoint["externalApiRequests"], 0)


if __name__ == "__main__":
    unittest.main()
