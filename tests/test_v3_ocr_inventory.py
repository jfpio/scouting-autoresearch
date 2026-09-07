import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from inventory_v3_ocr_games import (
    OCRPage,
    SourcePlan,
    _deduplicate,
    _toc_pairs,
    annotate_candidate_boundaries,
    parse_jasinski,
    parse_mojmir,
)


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

    def test_jasinski_includes_numbered_scout_race_examples(self):
        pages = [
            OCRPage(
                227,
                "view-0227.jpg",
                "216",
                "# Przykłady biegów harcerskich.\n# Bieg 1:\nOpis.\n# Bieg 2 (nocny):\nOpis.",
                "a" * 64,
            )
        ]
        candidates = parse_jasinski(pages)
        self.assertEqual(
            [(item["sourceNumber"], item["titleRaw"]) for item in candidates],
            [("Bieg 1", "Bieg 1"), ("Bieg 2", "Bieg 2 (nocny)")],
        )

    def test_boundary_annotation_hashes_prose_without_emitting_it(self):
        pages = [
            OCRPage(10, "view-0010.jpg", "1", "## Pierwsza\nOpis według Setona.\n## Druga\nOpis.", "a" * 64),
        ]
        candidates = [
            {
                "titleRaw": "Pierwsza", "viewStart": 10,
                "bestLineLocator": "view-0010-l0001", "locatorStatus": "heading-located",
            },
            {
                "titleRaw": "Druga", "viewStart": 10,
                "bestLineLocator": "view-0010-l0003", "locatorStatus": "heading-located",
            },
        ]
        plan = SourcePlan("T", "A", 1900, "test", ((10, 10),))
        annotate_candidate_boundaries(plan, pages, candidates)
        self.assertEqual(candidates[0]["endExclusiveLocator"], "view-0010-l0003")
        self.assertEqual(candidates[0]["viewEndInclusive"], 10)
        self.assertIn("explicit-attribution-language", candidates[0]["componentRiskSignalIds"])
        self.assertIn("known-external-source-name", candidates[0]["componentRiskSignalIds"])
        self.assertEqual(len(candidates[0]["sourceBlockSha256"]), 64)
        self.assertNotIn("Opis", str(candidates[0]))

    def test_checked_in_candidate_reports_are_metadata_only_and_complete(self):
        expected_counts = {
            "jasinski-field-games-1938": 196,
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
                if candidate["boundaryStatus"].startswith("bounded-by"):
                    self.assertEqual(len(candidate["sourceBlockSha256"]), 64)
                    self.assertGreater(candidate["blockNonEmptyLineCount"], 0)
                self.assertFalse(prohibited_candidate_keys.intersection(candidate))
            total += expected_count
        self.assertEqual(total, 562)


if __name__ == "__main__":
    unittest.main()
