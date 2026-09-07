import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from import_v3_indexed_games import (
    REJECTED_REASONS,
    REVIEWED_BOUNDS,
    build_import,
    locator_key,
)


class V3IndexedImportTests(unittest.TestCase):
    def test_every_candidate_has_exactly_one_review_decision(self):
        self.assertEqual(set(REVIEWED_BOUNDS).isdisjoint(REJECTED_REASONS), True)
        self.assertEqual(set(REVIEWED_BOUNDS) | set(REJECTED_REASONS), set(range(1, 41)))

    def test_reviewed_bounds_are_ordered(self):
        for start, end in REVIEWED_BOUNDS.values():
            self.assertLess(locator_key(start), locator_key(end))

    def test_build_import_has_pinned_outputs_and_no_exact_duplicates(self):
        extraction, outputs, source = build_import()
        self.assertEqual(extraction["activityCount"], 36)
        self.assertEqual(extraction["selection"]["rejectedCount"], 4)
        self.assertEqual(len(outputs), 36)
        self.assertEqual(source["activityPrefix"], "hmp")
        self.assertFalse(extraction["deduplication"]["exactBodyMatches"])
        self.assertEqual(outputs[0][1]["id"], "hmp-001")
        self.assertEqual(outputs[-1][1]["id"], "hmp-039")

    def test_corrected_index_page_and_stamp_reconstruction_are_explicit(self):
        extraction, outputs, _source = build_import()
        by_id = {metadata["id"]: (metadata, body) for _path, metadata, body in outputs}
        self.assertEqual(by_id["hmp-038"][0]["printedPages"], [229])
        self.assertTrue(by_id["hmp-038"][1].startswith("Harcerze wychodzą pojedynczo"))
        self.assertIn("[zastępowi]", by_id["hmp-005"][1])
        self.assertIn("transcriptionNotes", by_id["hmp-005"][0])
        item = next(item for item in extraction["activities"] if item["id"] == "hmp-038")
        self.assertEqual(item["startLine"], "p0244-l0021")


if __name__ == "__main__":
    unittest.main()
