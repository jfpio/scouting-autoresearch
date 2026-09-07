import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from import_v3_ocr_games import IMPORT_PLANS, clean_source_block, section_for_number, source_revision


class ImportV3OcrGamesTests(unittest.TestCase):
    def test_clean_source_block_removes_only_heading_page_and_next_section(self):
        raw = "# GRA.\n\nPierwszy akapit.\n\n291\n\n## DZIAŁ II.\n"
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

    def test_section_boundaries_are_explicit(self):
        plan = IMPORT_PLANS["zwolakowska-cub-pack-1945"]
        self.assertEqual(section_for_number(plan, 24), "Dział I")
        self.assertEqual(section_for_number(plan, 25), "Dział II")
        self.assertEqual(section_for_number(plan, 64), "Dział IV")

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
