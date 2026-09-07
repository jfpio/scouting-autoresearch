import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from inventory_v3_ocr_games import OCRPage, _deduplicate, _toc_pairs, parse_mojmir


ROOT = Path(__file__).resolve().parents[1]


class V3OCRInventoryTests(unittest.TestCase):
    def test_table_and_plain_toc_pairs(self):
        self.assertEqual(
            _toc_pairs("| Gra Kima | 11 | Gra Morgana | 13 |"),
            [("Gra Kima", 11), ("Gra Morgana", 13)],
        )
        self.assertEqual(_toc_pairs("Szukanie zegarka . . . 25"), [("Szukanie zegarka", 25)])

    def test_deduplication_ignores_punctuation_and_case(self):
        items = [
            {"titleRaw": "Gra Kima"},
            {"titleRaw": "GRA KIMA."},
            {"titleRaw": "Gra Morgana"},
        ]
        self.assertEqual([item["titleRaw"] for item in _deduplicate(items)], ["Gra Kima", "Gra Morgana"])

    def test_mojmir_requires_all_85_numbered_toc_entries(self):
        toc = "\n".join(f"{number}. Gra {number}." for number in range(1, 86))
        body = "\n".join(f"## {number}. Gra {number}." for number in range(1, 86))
        pages = [
            OCRPage(11, "view-0011.jpg", None, toc, "a" * 64),
            OCRPage(13, "view-0013.jpg", "1", body, "b" * 64),
        ]
        candidates = parse_mojmir(pages)
        self.assertEqual(len(candidates), 85)
        self.assertTrue(all(item["locatorStatus"] == "heading-located" for item in candidates))

    def test_checked_in_candidate_reports_are_metadata_only_and_complete(self):
        expected_counts = {
            "jasinski-field-games-1938": 181,
            "mojmir-scout-games-1912": 85,
            "dabrowski-indoor-games-1934": 183,
            "pawelek-young-troop-1919": 24,
            "zwolakowska-cub-pack-1945": 74,
        }
        prohibited_candidate_keys = {
            "sourceText", "sourceProse", "markdown", "description", "rules", "fullText",
            "titleLocatorMatch",
        }
        total = 0
        for source_id, expected_count in expected_counts.items():
            report_path = ROOT / "data" / "reports" / f"{source_id}-candidates.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["selection"]["candidateCount"], expected_count)
            self.assertEqual(len(report["candidates"]), expected_count)
            self.assertIsNotNone(report["sourceText"]["recipeVersion"])
            for candidate in report["candidates"]:
                self.assertTrue(candidate["pageLocator"].startswith("view-"))
                self.assertEqual(len(candidate["ocrResponseSha256"]), 64)
                self.assertEqual(len(candidate["sourcePageSha256"]), 64)
                self.assertEqual(len(candidate["titleLocatorLineSha256"]), 64)
                self.assertFalse(prohibited_candidate_keys.intersection(candidate))
            total += expected_count
        self.assertEqual(total, 547)


if __name__ == "__main__":
    unittest.main()
