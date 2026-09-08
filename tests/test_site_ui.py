import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SiteUiTests(unittest.TestCase):
    def test_activity_filters_are_multiselect_with_removable_chips_and_no_sections(self):
        component = (ROOT / "src" / "components" / "ActivityExplorer.astro").read_text(encoding="utf-8")
        self.assertIn('type="checkbox" data-filter="year"', component)
        self.assertIn("params.append(facet, value)", component)
        self.assertIn("data-remove-filter", component)
        self.assertIn("scout-course", component)
        self.assertNotIn('data-filter="section"', component)
        self.assertNotIn("item.section", component)

    def test_primary_navigation_contains_all_five_tabs_in_both_languages(self):
        header = (ROOT / "src" / "components" / "SiteHeader.astro").read_text(encoding="utf-8")
        for label in ("Aktywności", "Mapa semantyczna", "Książki", "Autorzy", "O projekcie"):
            self.assertIn(label, header)
        for label in ("Activities", "Semantic map", "Books", "Authors", "About"):
            self.assertIn(label, header)

    def test_semantic_map_component_is_not_extended_in_this_phase(self):
        component = (ROOT / "src" / "components" / "SemanticMap.astro").read_text(encoding="utf-8")
        self.assertIn("All three sources", component)
        self.assertNotIn("scout-course", component)


if __name__ == "__main__":
    unittest.main()
