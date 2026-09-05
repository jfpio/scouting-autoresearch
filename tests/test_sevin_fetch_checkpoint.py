import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import ROOT


class SevinFetchCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "data" / "checkpoints" / "gallica-fetch" / "chamarande-1934.json"
        cls.checkpoint = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_retry_is_resumable_and_provider_specific(self):
        checkpoint = self.checkpoint
        self.assertEqual(checkpoint["status"], "retry-pending")
        self.assertEqual(checkpoint["reason"], "transient-http-429")
        self.assertEqual(checkpoint["collectionId"], "gallica-bnf")
        self.assertEqual(checkpoint["fullDocument"]["providerDiagnostics"]["httpStatus"], 429)
        datetime.fromisoformat(checkpoint["nextRetryAt"])

    def test_smoke_downloads_stay_outside_repository(self):
        checkpoint = self.checkpoint
        self.assertEqual(checkpoint["sourceFilesCommittedToRepository"], 0)
        self.assertFalse(checkpoint["fullTextCommittedToRepository"])
        self.assertFalse(checkpoint["fullDocument"]["persisted"])
        self.assertEqual(checkpoint["scratchRelativeDirectory"], "scouting-autoresearch/sources/chamarande-1934")
        self.assertEqual(len(checkpoint["downloadedViewSmoke"]), 3)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in checkpoint["downloadedViewSmoke"]))

    def test_ocr_is_pinned_and_costed(self):
        smoke = self.checkpoint["ocrSmoke"]
        self.assertEqual(smoke["status"], "complete")
        self.assertEqual(smoke["modelRequested"], "mistral-ocr-4-1")
        self.assertEqual(smoke["model"], "mistral-ocr-4-1")
        self.assertEqual(smoke["pagesProcessed"], 1)
        self.assertEqual(smoke["billingMode"], "education-credit")
        self.assertIsNone(smoke["billedCostUsd"])
        self.assertEqual(smoke["referenceCostUsd"], 0.004)

    def test_reuse_scope_remains_component_limited(self):
        checkpoint = self.checkpoint
        self.assertIn("Jacques Sevin", checkpoint["approvedComponent"])
        self.assertIn("music", checkpoint["excludedComponents"])
        self.assertIn("Source gallica.bnf.fr", checkpoint["requiredAttribution"])


if __name__ == "__main__":
    unittest.main()
