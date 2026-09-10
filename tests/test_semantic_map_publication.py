import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_content import semantic_map_page


ROOT = Path(__file__).resolve().parents[1]


class SemanticMapPublicationTests(unittest.TestCase):
    def test_pages_embed_map_with_limits_explained_in_its_help(self):
        polish = semantic_map_page("pl")
        english = semantic_map_page("en")
        shell = (ROOT / "scripts/semantic_map/shell.py").read_text(encoding="utf-8")
        self.assertIn('<details class="map-help">', shell)
        self.assertIn("nie są klasyfikacją historyczną", shell)
        self.assertIn("not a historical classification", shell)
        self.assertNotIn("pojawią się", polish)
        self.assertNotIn("will appear", english)
        self.assertIn('<SemanticMap locale="pl" />', polish)
        self.assertIn('<SemanticMap locale="en" />', english)

    def test_client_component_does_not_render_algorithmic_candidates(self):
        component = (ROOT / "src" / "components" / "SemanticMap.astro").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("analysis.algorithmicCandidates", component)
        self.assertNotIn("analysis.nearestNeighbors", component)
        self.assertIn("data-semantic-map-frame", component)
        renderer = (ROOT / "scripts" / "render_semantic_map.py").read_text(encoding="utf-8")
        self.assertIn('relation.get("status") == "human-approved"', renderer)
        shell = (ROOT / "scripts/semantic_map/shell.py").read_text(encoding="utf-8")
        self.assertIn("data-map-list-item", shell)


if __name__ == "__main__":
    unittest.main()
