import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_duplicates import cosine, normalized_vectors, strip_provenance_footer, terms


class DuplicateAnalysisTests(unittest.TestCase):
    def test_provenance_footer_is_not_compared(self):
        self.assertEqual(strip_provenance_footer("Game body\n\n---\nSource link"), "Game body")

    def test_terms_include_unigrams_and_bigrams(self):
        values = terms("Night Game", "Follow the light", 2)
        self.assertGreaterEqual(values["night"], 2)
        self.assertEqual(values["follow the"], 1)

    def test_identical_documents_have_unit_similarity(self):
        records = [
            {"activityId": "a", "title": "Same", "body": "same body"},
            {"activityId": "b", "title": "Same", "body": "same body"},
        ]
        vectors = normalized_vectors(records, 2)
        self.assertAlmostEqual(cosine(vectors["a"], vectors["b"]), 1.0)

    def test_distinct_documents_have_zero_similarity(self):
        records = [
            {"activityId": "a", "title": "North", "body": "compass stars"},
            {"activityId": "b", "title": "Cooking", "body": "potatoes fire"},
        ]
        vectors = normalized_vectors(records, 2)
        self.assertEqual(cosine(vectors["a"], vectors["b"]), 0.0)


if __name__ == "__main__":
    unittest.main()
