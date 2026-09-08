import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from import_sedlaczek_scout_school import (
    FACSIMILE_CONFIRMED_CORRECTIONS,
    REJECTED_REASONS,
    REVIEWED_SPANS,
    clean_ocr_body,
)


class ImportSedlaczekScoutSchoolTests(unittest.TestCase):
    def test_all_candidates_have_one_decision(self):
        self.assertEqual(set(REVIEWED_SPANS) | set(REJECTED_REASONS), set(range(1, 41)))
        self.assertFalse(set(REVIEWED_SPANS) & set(REJECTED_REASONS))
        self.assertEqual(len(REVIEWED_SPANS), 34)

    def test_non_game_drills_are_rejected(self):
        self.assertEqual(set(REJECTED_REASONS), {1, 7, 9, 21, 25, 30})

    def test_cleaner_joins_page_break_and_dehyphenates(self):
        raw = "139\n\nPierwsza część gra-\n\n140\n\nczy dalej, a następny aka-\npit trwa."
        self.assertEqual(
            clean_ocr_body(raw, 3),
            "Pierwsza część graczy dalej, a następny akapit trwa.",
        )

    def test_cleaner_applies_only_pinned_candidate_corrections(self):
        raw = "Teren był zrządka porosły krzakami, a harcerze starałą się podejść."
        self.assertEqual(
            clean_ocr_body(raw, 29),
            "Teren był zrzadka porosły krzakami, a harcerze starają się podejść.",
        )
        self.assertIn(29, FACSIMILE_CONFIRMED_CORRECTIONS)

    def test_inline_spans_split_shared_ocr_paragraph(self):
        self.assertEqual(REVIEWED_SPANS[12].end_pattern, REVIEWED_SPANS[13].start_pattern)
        self.assertEqual(REVIEWED_SPANS[13].start_view, 72)


if __name__ == "__main__":
    unittest.main()
