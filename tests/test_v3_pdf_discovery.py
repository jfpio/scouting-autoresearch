import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from discover_v3_pdf_games import excerpt_for_pages, output_token_budget, parse_range, parse_response


class V3PdfDiscoveryTests(unittest.TestCase):
    def test_excerpt_has_stable_page_markers_and_normalized_whitespace(self):
        excerpt = excerpt_for_pages(["  one\n two  ", "three"], 1, 2)
        self.assertEqual(
            excerpt,
            "[PDF PAGE 1]\n[p0001-l0001] one\n[p0001-l0002] two\n\n"
            "[PDF PAGE 2]\n[p0002-l0001] three",
        )

    def test_range_must_be_bounded_and_safe(self):
        self.assertEqual(parse_range("part-01:2-4", 5), ("part-01", 2, 4))
        for value in ("missing", "../bad:1-2", "late:3-6", "backward:4-2"):
            with self.assertRaises((ValueError, TypeError)):
                parse_range(value, 5)

    def test_response_requires_exact_quotes_and_bounds(self):
        excerpt = (
            "[PDF PAGE 2]\n"
            "[p0002-l0001] Alpha beta gamma delta epsilon zeta\n"
            "[p0002-l0002] eta theta iota kappa"
        )
        payload = {
            "games": [{
                "title": "Alpha",
                "pageStart": 2,
                "pageEnd": 2,
                "startLine": "p0002-l0001",
                "endLine": "p0002-l0002",
                "printedAttribution": "book-authors",
                "attributionEvidenceLine": "",
                "section": "Test",
                "notes": "",
            }]
        }
        games = parse_response(json.dumps(payload), 2, 2, excerpt)
        self.assertEqual(games[0]["title"], "Alpha")
        payload["games"][0]["pageStart"] = 1
        payload["games"][0]["pageEnd"] = 1
        games = parse_response(json.dumps(payload), 2, 2, excerpt)
        self.assertEqual((games[0]["pageStart"], games[0]["pageEnd"]), (2, 2))
        payload["games"][0]["endLine"] = "p0002-l9999"
        with self.assertRaisesRegex(ValueError, "not present"):
            parse_response(json.dumps(payload), 2, 2, excerpt)

    def test_output_budget_is_dynamic_and_bounded(self):
        self.assertEqual(output_token_budget("short"), 768)
        self.assertEqual(output_token_budget("x" * 100_000), 8192)


if __name__ == "__main__":
    unittest.main()
