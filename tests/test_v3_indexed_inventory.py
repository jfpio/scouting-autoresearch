import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from inventory_v3_indexed_games import SOURCE_PLANS, compact, title_similarity


class V3IndexedInventoryTests(unittest.TestCase):
    def test_pinned_candidate_counts(self):
        self.assertEqual(
            len(SOURCE_PLANS["piasecki-schreiber-polish-scoutcraft-1917"]["candidates"]),
            40,
        )
        self.assertEqual(
            len(SOURCE_PLANS["sedlaczek-scout-school-1921"]["candidates"]),
            40,
        )

    def test_printed_to_pdf_offsets_are_pinned(self):
        self.assertEqual(
            SOURCE_PLANS["piasecki-schreiber-polish-scoutcraft-1917"]["printedToPdfPageOffset"],
            15,
        )
        self.assertEqual(
            SOURCE_PLANS["sedlaczek-scout-school-1921"]["printedToPdfPageOffset"],
            1,
        )

    def test_title_matching_tolerates_ocr_punctuation(self):
        self.assertEqual(compact("Blisko — daleko"), compact("Blisko-daleko"))
        self.assertGreater(title_similarity("Pająk i mucha", "Pająk i mucfra."), 0.75)


if __name__ == "__main__":
    unittest.main()
