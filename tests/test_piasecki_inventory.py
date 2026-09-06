import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from inventory_piasecki_movement_games import compact, section_for, title_similarity


class PiaseckiInventoryTests(unittest.TestCase):
    def test_compact_ignores_spacing_and_case(self):
        self.assertEqual(compact("P t a s z e k"), compact("Ptaszek"))

    def test_title_similarity_tolerates_ocr_spacing(self):
        self.assertGreater(title_similarity("Stoi ró ży czk a", "4. Stoi różyczka"), 0.8)

    def test_sections_cover_all_numbered_games(self):
        self.assertEqual(section_for(1), "Zabawy i gry chodne")
        self.assertEqual(section_for(91), "Gry kopne")
        self.assertEqual(section_for(133), "Gry z podbijaniem")


if __name__ == "__main__":
    unittest.main()
