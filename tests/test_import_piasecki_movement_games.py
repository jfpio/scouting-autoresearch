import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from import_piasecki_movement_games import build_import


class ImportPiaseckiMovementGamesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extraction, outputs, cls.source = build_import()
        cls.activities = {
            metadata["id"]: (metadata, body)
            for _path, metadata, body in outputs
        }

    def test_review_keeps_117_self_contained_games(self):
        self.assertEqual(self.extraction["activityCount"], 117)
        self.assertEqual(self.extraction["selection"]["rejectedCount"], 16)
        self.assertNotIn("zgr-002", self.activities)
        self.assertNotIn("zgr-092", self.activities)
        self.assertIn("zgr-133", self.activities)

    def test_song_text_is_omitted_without_breaking_retained_procedure(self):
        metadata, body = self.activities["zgr-021"]
        self.assertEqual(metadata["contentOmissions"], ["musical-notation", "song-lyrics"])
        self.assertIn("kulała przy poprzednich zwrotkach, poskakuje", body)
        self.assertNotIn("wając.", body)

    def test_mixed_diagram_lines_are_reconstructed_from_scan(self):
        _metadata, body = self.activities["zgr-084"]
        self.assertIn("długość boku każdego kwadratu = krokowi", body)
        self.assertIn("2) obejść klasy z zamkniętemi oczyma, 3) przeskakać", body)
        self.assertNotIn("V //", body)
        self.assertNotIn("zamk«iętemi", body)

    def test_scan_verified_title_is_preserved(self):
        metadata, body = self.activities["zgr-080"]
        self.assertEqual(metadata["title"], "Plinje")
        self.assertTrue(body.startswith("Gra pospolita"))
        self.assertNotIn("£>o", body)

    def test_false_title_locator_does_not_split_palant_games(self):
        _simple_metadata, simple_body = self.activities["zgr-130"]
        metadata, body = self.activities["zgr-131"]
        self.assertNotIn("Sami biją, sami galą", simple_body)
        self.assertEqual(metadata["title"], "Palant z matkami, bez galenia")
        self.assertEqual(metadata["pdfPages"][0], 218)
        self.assertIn("1) P o l e g r y jest prostokątem", body)
        self.assertIn("¹) Patrz Cz. ogólna, V a.", body)

    def test_source_footnotes_are_relocated_after_the_procedure(self):
        _metadata, fox_body = self.activities["zgr-066"]
        self.assertIn("zmieniają miejsca¹). Wszędzie lis", fox_body)
        self.assertTrue(fox_body.index("¹) W Krakowskiem") > fox_body.index("trzy niedziele"))
        self.assertNotIn("')•", fox_body)

        _metadata, body = self.activities["zgr-097"]
        procedure = body.index("1) Technika chwytów")
        footnote = body.index("¹) U Gołębiowskiego")
        self.assertGreater(footnote, procedure)
        self.assertNotIn("itdwolno", body)

        metadata, throwing_body = self.activities["zgr-100"]
        self.assertEqual(metadata["title"], "Ducza")
        self.assertTrue(throwing_body.index("¹) Podobną grę") > throwing_body.index("słupek wygrywa"))
        self.assertNotIn("G r e 1e", throwing_body)

    def test_known_illustration_text_does_not_leak(self):
        _metadata, body = self.activities["zgr-103"]
        self.assertIn("wykluczyć przewagę jednego gracza", body)
        self.assertNotIn("PrzyJc/aafy", body)
        self.assertNotIn("C zenw onycA", body)

    def test_piestowka_repairs_ball_word_and_caption_overlap(self):
        _metadata, body = self.activities["zgr-133"]
        self.assertIn("podrzuca piłkę", body)
        self.assertIn("byle po każdem podbiciu piłka nie uczyniła", body)
        self.assertNotIn("P/ęs/ów", body)
        self.assertNotIn("piłę", body)


if __name__ == "__main__":
    unittest.main()
