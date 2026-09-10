import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STYLING_BOUNDARY_EXCEPTIONS = {}


def embedded_astro_components() -> set[Path]:
    imports = set()
    pattern = re.compile(r"^import\s+\w+\s+from\s+['\"]([^'\"]+\.astro)['\"];?\s*$", re.MULTILINE)
    for page in (ROOT / "src" / "content" / "docs").rglob("*.mdx"):
        for relative_path in pattern.findall(page.read_text(encoding="utf-8")):
            imports.add((page.parent / relative_path).resolve())
    return imports


def first_rendered_tag(component: Path) -> str:
    source = component.read_text(encoding="utf-8")
    template = source.split("---", 2)[-1]
    match = re.search(r"<[a-z][^>]*>", template)
    if not match:
        raise AssertionError(f"No rendered root element found in {component.relative_to(ROOT)}")
    return match.group(0)


class SiteUiTests(unittest.TestCase):
    def test_embedded_ui_components_opt_out_of_starlight_content_styles(self):
        components = embedded_astro_components()
        self.assertTrue(components)
        self.assertFalse(set(STYLING_BOUNDARY_EXCEPTIONS) - components)
        self.assertTrue(all(reason.strip() for reason in STYLING_BOUNDARY_EXCEPTIONS.values()))

        for component in sorted(components - set(STYLING_BOUNDARY_EXCEPTIONS)):
            with self.subTest(component=component.relative_to(ROOT)):
                self.assertIn(
                    "not-content",
                    first_rendered_tag(component),
                    "Self-styled UI embedded in MDX must isolate its root from Starlight content styles",
                )

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

    def test_semantic_map_component_embeds_bilingual_fullscreen_explorer(self):
        component = (ROOT / "src" / "components" / "SemanticMap.astro").read_text(encoding="utf-8")
        self.assertIn("not-content", component)
        self.assertIn("data-semantic-map-frame", component)
        self.assertIn("/scouting-autoresearch/semantic-map/${locale}/", component)
        self.assertIn("Otwórz pełną mapę", component)
        self.assertIn("Open the full map", component)
        self.assertIn("pobrać teksty gier", component)
        self.assertIn("download game texts", component)

    def test_generic_historical_safety_warning_is_not_rendered(self):
        builder = (ROOT / "scripts" / "build_content.py").read_text(encoding="utf-8")
        stylesheet = (ROOT / "src" / "styles" / "site.css").read_text(encoding="utf-8")
        for forbidden in (
            "Uwaga bezpieczeństwa.",
            "Historyczna aktywność nie jest automatycznie rekomendacją metodyczną",
            "A historical activity is not automatically a modern recommendation",
            "safety-notice",
        ):
            self.assertNotIn(forbidden, builder)
            self.assertNotIn(forbidden, stylesheet)


if __name__ == "__main__":
    unittest.main()
