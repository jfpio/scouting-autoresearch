import tempfile
import unittest
from pathlib import Path

import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import dump_markdown, load_markdown, source_hash
from import_sources import clean_game_body
from translate import parse_json_content


class PipelineTests(unittest.TestCase):
    def test_markdown_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.md"
            metadata = {"id": "test-001", "title": "Żuraw", "traits": ["spryt"]}
            dump_markdown(path, metadata, "Treść **próby**.")
            loaded, body = load_markdown(path)
            self.assertEqual(loaded, metadata)
            self.assertEqual(body, "Treść **próby**.")

    def test_source_hash_is_stable_and_title_sensitive(self):
        self.assertEqual(source_hash(" Tytuł ", " Treść "), source_hash("Tytuł", "Treść"))
        self.assertNotEqual(source_hash("Tytuł", "Treść"), source_hash("Inny", "Treść"))

    def test_game_cleanup_removes_source_chrome_and_absolutizes_assets(self):
        raw = """---\ntitle: Test\n---\n\n> **Transkrypcja OCR — wersja beta.** Tekst.\n\nAkapit.\n\n![x](/harcerz-w-polu/book/assets/x.jpeg)\n\n<p class=\"source-note\">Źródło</p>\n"""
        cleaned = clean_game_body(raw)
        self.assertNotIn("Transkrypcja OCR", cleaned)
        self.assertNotIn("source-note", cleaned)
        self.assertIn("https://jfpio.github.io/harcerz-w-polu/book/assets/x.jpeg", cleaned)

    def test_translation_json_contract(self):
        payload = parse_json_content('{"title":"Fire","body":"Text","traits":["patience"],"section":"Trials"}')
        self.assertEqual(payload["title"], "Fire")
        with self.assertRaises(ValueError):
            parse_json_content('{"title":"Fire","body":"Text","traits":[],"section":"Trials","extra":true}')

    def test_azymut_is_approved_for_editorial_discovery_only(self):
        root = Path(__file__).resolve().parents[1]
        registry = yaml.safe_load((root / "config" / "source-registry.yaml").read_text(encoding="utf-8"))
        azymut = next(item for item in registry["collections"] if item["id"] == "azymut-zhr")
        self.assertEqual(azymut["baseUrl"], "https://azymut.zhr.pl/")
        self.assertEqual(azymut["status"], "approved-per-item")
        self.assertEqual(azymut["trustScope"], "editorial-discovery")
        self.assertEqual(azymut["allowedMethods"], ["article-metadata", "link-discovery"])


if __name__ == "__main__":
    unittest.main()
