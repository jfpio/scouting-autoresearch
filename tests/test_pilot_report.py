import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_pilot_report import build_report, elapsed_seconds


class PilotReportTests(unittest.TestCase):
    def test_elapsed_seconds(self):
        self.assertEqual(elapsed_seconds("01:02:03"), 3723)

    def test_current_pilot_preserves_unknown_human_measurements(self):
        report = build_report()
        self.assertEqual(report["status"], "human-quality-and-timing-review-pending")
        self.assertIsNone(report["time"]["humanReviewMinutes"])
        self.assertFalse(report["conclusions"]["safeToScaleFromThisPilot"])

    def test_cost_components_sum_to_total(self):
        cost = build_report()["cost"]
        self.assertAlmostEqual(
            cost["benchmarkReferenceCost"] + cost["productionReferenceCost"],
            cost["totalReferenceCost"],
        )


if __name__ == "__main__":
    unittest.main()
