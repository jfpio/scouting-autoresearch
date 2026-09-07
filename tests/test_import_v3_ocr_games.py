import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from import_v3_ocr_games import (
    IMPORT_PLANS,
    clean_source_block,
    find_stop_heading,
    section_for_number,
    source_heading_title,
    source_revision,
)


class ImportV3OcrGamesTests(unittest.TestCase):
    def test_clean_source_block_removes_only_heading_page_and_next_section(self):
        raw = "# GRA.\n\nPierwszy akapit.\n\n7*\n\n291\n\n## DZIAŁ II.\n"
        self.assertEqual(clean_source_block(raw), "Pierwszy akapit.")

    def test_clean_source_block_joins_only_mid_sentence_page_breaks(self):
        raw = (
            "# KOMPAS.\n\nDrużynowa rysuje duże koło — kompas\n\n302\n\n"
            "i wywołuje stronę świata.\n\nNowy akapit zaczyna się wielką literą.\n"
        )
        self.assertEqual(
            clean_source_block(raw),
            "Drużynowa rysuje duże koło — kompas i wywołuje stronę świata.\n\n"
            "Nowy akapit zaczyna się wielką literą.",
        )

    def test_clean_source_block_joins_page_break_after_comma_before_lowercase(self):
        raw = "# GRA.\n\nWolno go przytrzymać,\n\nodebrać list.\n"
        self.assertEqual(
            clean_source_block(raw),
            "Wolno go przytrzymać, odebrać list.",
        )

    def test_clean_source_block_removes_pinned_header_image_and_soft_wraps(self):
        raw = (
            "# 22. Gra.\n\nPierwszy aka-\npit i dru-\n\n15\n\n*\n\ngi akapit.\n\n"
            "![img-0.jpeg](img-0.jpeg)\n\nĆwiczenia i zabawy skautowe.\n"
        )
        self.assertEqual(
            clean_source_block(
                raw,
                ("Ćwiczenia i zabawy skautowe.",),
                join_soft_wraps=True,
            ),
            "Pierwszy akapit i drugi akapit.",
        )

    def test_clean_source_block_removes_patterned_running_header(self):
        raw = "# 1. Gra.\n\nTekst.\n\nGry i ćwiczenia terenowe. 91\n"
        self.assertEqual(
            clean_source_block(
                raw,
                join_soft_wraps=True,
                repeated_header_patterns=(r"^Gry i ćwiczenia terenowe\.\s*\d*$",),
            ),
            "Tekst.",
        )

    def test_clean_source_block_preserves_single_line_inline_procedure_when_pinned(self):
        raw = "## 2. Szukanie kamieni; wygrywa zastęp, który znajdzie ich najwięcej.\n"
        self.assertEqual(
            clean_source_block(raw, preserve_inline_heading_body=True),
            "Szukanie kamieni; wygrywa zastęp, który znajdzie ich najwięcej.",
        )

    def test_clean_source_block_preserves_prose_after_inline_title(self):
        raw = "1. Szukanie tropów. Wygrywa pierwszy zastęp.\n\nDalsze zasady.\n"
        self.assertEqual(
            clean_source_block(raw, inline_heading_title="Szukanie tropów"),
            "Wygrywa pierwszy zastęp.\n\nDalsze zasady.",
        )

    def test_clean_source_block_keeps_abbreviation_when_title_split_is_ambiguous(self):
        raw = "2. Szukanie przedmiotów, jak np. mostów i przepustów.\n"
        self.assertEqual(
            clean_source_block(
                raw,
                preserve_inline_heading_body=True,
                inline_heading_title="Szukanie przedmiotów, jak np",
            ),
            "Szukanie przedmiotów, jak np. mostów i przepustów.",
        )

    def test_find_stop_heading_returns_first_pinned_chapter_boundary(self):
        class Page:
            def __init__(self, markdown):
                self.markdown = markdown

        pages = {
            1: Page("# 1. Gra.\nTreść."),
            2: Page("Dalsza treść.\n## II. Następny rozdział.\nWstęp."),
        }
        self.assertEqual(
            find_stop_heading(
                pages,
                (1, 1),
                None,
                2,
                (r"^#{1,6}\s+[IVXLCDM]+\.\s+.*$",),
                (),
            ),
            ((2, 2), "II. Następny rozdział."),
        )

    def test_source_heading_title_uses_body_heading_and_strips_number(self):
        self.assertEqual(
            source_heading_title("### 48. Testament Woroby.\n\nTekst."),
            "Testament Woroby",
        )

    def test_section_boundaries_are_explicit(self):
        plan = IMPORT_PLANS["zwolakowska-cub-pack-1945"]
        self.assertEqual(section_for_number(plan, 24), "Dział I")
        self.assertEqual(section_for_number(plan, 25), "Dział II")
        self.assertEqual(section_for_number(plan, 64), "Dział IV")

    def test_mojmir_review_rejects_five_non_game_entries(self):
        plan = IMPORT_PLANS["mojmir-scout-games-1912"]
        self.assertEqual(len(plan.accepted_numbers), 80)
        self.assertEqual(
            {number for number, _ in plan.rejected_reasons},
            {3, 26, 60, 70, 73},
        )

    def test_jasinski_review_keeps_scout_courses_outside_game_only_scope(self):
        plan = IMPORT_PLANS["jasinski-field-games-1938"]
        self.assertEqual(len(plan.accepted_numbers), 138)
        rejected = {number for number, _ in plan.rejected_reasons}
        self.assertTrue(set(range(171, 186)).issubset(rejected))
        self.assertTrue(set(range(186, 197)).issubset(plan.accepted_numbers))

    def test_source_revision_is_ordered_and_scoped_to_selected_views(self):
        checkpoint = {
            "ocrRun": {
                "items": [
                    {
                        "sourceImage": "view-0002.jpg",
                        "sourceImageSha256": "b",
                        "responseSha256": "d",
                        "model": "m",
                        "recipeVersion": "r",
                    },
                    {
                        "sourceImage": "view-0001.jpg",
                        "sourceImageSha256": "a",
                        "responseSha256": "c",
                        "model": "m",
                        "recipeVersion": "r",
                    },
                    {"sourceImage": "view-0003.jpg", "responseSha256": "ignored"},
                ]
            }
        }
        expected = hashlib.sha256(
            json.dumps(
                [
                    {
                        "view": 1,
                        "sourceImageSha256": "a",
                        "responseSha256": "c",
                        "model": "m",
                        "recipeVersion": "r",
                    },
                    {
                        "view": 2,
                        "sourceImageSha256": "b",
                        "responseSha256": "d",
                        "model": "m",
                        "recipeVersion": "r",
                    },
                ],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(source_revision(checkpoint, {1, 2}), expected)


if __name__ == "__main__":
    unittest.main()
