import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import ROOT, load_markdown


class SevinAlternativeAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = (
            ROOT
            / "vault"
            / "reviews"
            / "inbox"
            / "candidate-jacques-sevin-chamarande-gallica.md"
        )
        cls.metadata, cls.body = load_markdown(cls.path)
        cls.rights = cls.metadata["rightsReview"]
        cls.search = cls.rights["alternativeAccessResearch"]

    def test_negative_search_does_not_change_rights_or_download_state(self):
        self.assertEqual(self.metadata["status"], "rights-review")
        self.assertTrue(self.metadata["publicationBlocked"])
        self.assertFalse(self.rights["humanApproved"])
        self.assertFalse(self.rights["fullTextEligible"])
        self.assertFalse(self.rights["translationEligible"])
        self.assertEqual(
            self.search["status"],
            "no-equivalent-digital-edition-found-in-approved-metadata-searches",
        )
        self.assertEqual(self.search["interpretation"], "negative-search-result-not-proof-of-absence")
        self.assertEqual(self.search["sourceFilesDownloaded"], 0)
        self.assertEqual(self.metadata["discovery"]["sourceFilesDownloaded"], 0)

    def test_owner_approved_only_controlled_noncommercial_download(self):
        decision = self.rights["accessDecision"]
        self.assertEqual(decision["status"], "human-approved-for-controlled-download")
        self.assertEqual(decision["date"], "2026-09-05")
        self.assertEqual(decision["approvedBy"], "repository-owner")
        self.assertEqual(decision["useMode"], "noncommercial-research-and-publication")
        self.assertEqual(
            decision["requiredAttribution"],
            "Source gallica.bnf.fr / Bibliothèque nationale de France",
        )
        self.assertTrue(any("original French prose" in item for item in decision["approvedScope"]))
        self.assertTrue(any("music" in item for item in decision["excludes"]))

    def test_registry_approval_is_limited_to_this_item(self):
        import yaml

        registry_path = ROOT / "config" / "source-registry.yaml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        gallica = next(item for item in registry["collections"] if item["id"] == "gallica-bnf")
        self.assertEqual(gallica["status"], "approved-per-item")
        self.assertIn("documented-download", gallica["allowedMethods"])
        self.assertEqual(len(gallica["itemApprovals"]), 1)
        self.assertEqual(gallica["itemApprovals"][0]["identifier"], "bpt6k3373518k")

    def test_gallica_material_is_excluded_from_the_default_commercial_license(self):
        import yaml

        registry_path = ROOT / "config" / "source-registry.yaml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        gallica = next(item for item in registry["collections"] if item["id"] == "gallica-bnf")
        licensing = gallica["itemApprovals"][0]["downstreamLicensing"]
        self.assertEqual(licensing["projectMetadata"], "CC-BY-4.0")
        self.assertEqual(
            licensing["sourceTextAndTranscription"],
            "gallica-noncommercial-reuse-terms",
        )
        self.assertEqual(
            licensing["projectTranslation"],
            "CC-BY-NC-4.0-and-gallica-noncommercial-reuse-terms",
        )
        self.assertEqual(licensing["commercialReuse"], "separate-bnf-license-required")

        policy = (ROOT / "DATA-LICENSE.md").read_text(encoding="utf-8")
        self.assertIn("bpt6k3373518k", policy)
        self.assertIn("CC BY-NC 4.0", policy)
        self.assertIn("Source gallica.bnf.fr / Bibliothèque nationale de France", policy)

        software_license = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("applies only to the software code", software_license)
        self.assertIn("DATA-LICENSE.md", software_license)

    def test_searches_use_only_registered_metadata_or_link_methods(self):
        queries = self.search["queries"]
        self.assertEqual(len(queries), 6)
        self.assertEqual(
            {query["collectionId"] for query in queries},
            {
                "internet-archive",
                "wikisource",
                "scoutscan-the-dump",
                "project-gutenberg",
            },
        )
        self.assertTrue(
            all(query["method"] in {"metadata-only", "link-discovery"} for query in queries)
        )
        self.assertEqual([query["result"]["numFound"] for query in queries[:3]], [0, 5, 1])
        self.assertEqual(queries[3]["result"]["totalHits"], 0)
        self.assertEqual(queries[4]["result"]["matchingEntries"], 0)
        self.assertEqual(queries[5]["result"]["matchingRows"], 0)
        self.assertFalse(queries[5]["result"]["persistedCatalogFile"])

    def test_record_states_the_limits_of_negative_evidence(self):
        self.assertIn("nieistnienia", self.body)
        self.assertIn("nie pobrano żadnego pliku", self.body.lower())
        self.assertIn("Gallici", self.body)


if __name__ == "__main__":
    unittest.main()
