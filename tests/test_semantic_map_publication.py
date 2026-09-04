import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_content import semantic_map_page


ROOT = Path(__file__).resolve().parents[1]


class SemanticMapPublicationTests(unittest.TestCase):
    def test_pages_explain_limits_and_do_not_promise_unapproved_filters(self):
        polish = semantic_map_page("pl")
        english = semantic_map_page("en")
        self.assertIn("nie jest kategorią", polish)
        self.assertIn("ręcznym zatwierdzeniu", polish)
        self.assertIn("does not publish unreviewed relation candidates", english)
        self.assertIn('<SemanticMap locale="pl" />', polish)
        self.assertIn('<SemanticMap locale="en" />', english)

    def test_client_component_does_not_render_algorithmic_candidates(self):
        component = (ROOT / "src" / "components" / "SemanticMap.astro").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("analysis.algorithmicCandidates", component)
        self.assertNotIn("analysis.nearestNeighbors", component)
        self.assertIn("analysis.approvedRelationOverlays", component)
        self.assertIn("data-map-list-item", component)


if __name__ == "__main__":
    unittest.main()
