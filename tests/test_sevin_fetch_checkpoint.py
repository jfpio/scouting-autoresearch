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

    def test_fetch_state_is_resumable_and_provider_specific(self):
        checkpoint = self.checkpoint
        self.assertEqual(checkpoint["collectionId"], "gallica-bnf")
        self.assertEqual(checkpoint["fullDocument"]["providerDiagnostics"]["httpStatus"], 429)
        self.assertEqual(len(checkpoint["fullDocument"]["attempts"]), 2)
        if checkpoint["status"] == "retry-pending":
            self.assertEqual(checkpoint["reason"], "transient-http-429")
            datetime.fromisoformat(checkpoint["nextRetryAt"])
            return
        self.assertIn(checkpoint["status"], {"view-fetch-in-progress", "views-fetched"})
        self.assertEqual(
            checkpoint["fetchStrategy"],
            "iiif-view-fallback-after-two-pdf-429s",
        )
        view_fetch = checkpoint["viewFetch"]
        self.assertEqual(view_fetch["totalViews"], checkpoint["pagination"]["viewCount"])
        self.assertEqual(view_fetch["completedViews"], len(view_fetch["items"]))
        self.assertGreater(view_fetch["completedViews"], 0)
        self.assertEqual(
            checkpoint["status"] == "views-fetched",
            view_fetch["completedViews"] == view_fetch["totalViews"],
        )

    def test_smoke_downloads_stay_outside_repository(self):
        checkpoint = self.checkpoint
        self.assertEqual(checkpoint["sourceFilesCommittedToRepository"], 0)
        self.assertFalse(checkpoint["fullTextCommittedToRepository"])
        self.assertFalse(checkpoint["fullDocument"]["persisted"])
        self.assertEqual(checkpoint["scratchRelativeDirectory"], "scouting-autoresearch/sources/chamarande-1934")
        self.assertEqual(len(checkpoint["downloadedViewSmoke"]), 3)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in checkpoint["downloadedViewSmoke"]))

    def test_printed_pagination_is_complete_but_not_in_view_order(self):
        integrity = self.checkpoint["paginationIntegrity"]
        self.assertEqual(
            integrity["paginationSha256"],
            self.checkpoint["pagination"]["sha256"],
        )
        self.assertEqual(integrity["totalViews"], self.checkpoint["pagination"]["viewCount"])
        self.assertEqual(
            integrity["numericPrintedPages"],
            {
                "minimum": 9,
                "maximum": 141,
                "count": 133,
                "duplicates": [],
                "missingWithinRange": [],
            },
        )
        self.assertEqual(
            [item["toPrintedPage"] for item in integrity["outOfOrderPrintedPageTransitions"]],
            [49, 33, 65],
        )
        self.assertIn("printed page", integrity["textSequencingRule"])

    def test_ocr_is_pinned_and_costed(self):
        smoke = self.checkpoint["ocrSmoke"]
        self.assertEqual(smoke["status"], "complete")
        self.assertEqual(smoke["modelRequested"], "mistral-ocr-4-1")
        self.assertEqual(smoke["model"], "mistral-ocr-4-1")
        self.assertEqual(smoke["pagesProcessed"], 1)
        self.assertEqual(smoke["billingMode"], "education-credit")
        self.assertIsNone(smoke["billedCostUsd"])
        self.assertEqual(smoke["referenceCostUsd"], 0.004)

    def test_iiif_contact_sheet_smoke_stays_in_scratch(self):
        smoke = self.checkpoint["iiifContactSheetSmoke"]
        self.assertEqual(smoke["status"], "complete")
        self.assertEqual(smoke["scheduler"], "slurm")
        self.assertEqual(smoke["architecture"], "x86_64")
        self.assertEqual(smoke["renderedPages"], len(smoke["inputViews"]))
        self.assertEqual(len(smoke["outputSha256"]), 64)
        self.assertTrue(smoke["resultPathUnderScratch"].startswith("scouting-autoresearch/"))
        self.assertEqual(smoke["sourceFilesCommittedToRepository"], 0)

        ordering = self.checkpoint["iiifOrderingSmoke"]
        self.assertEqual(ordering["status"], "complete")
        self.assertEqual(ordering["scheduler"], "slurm")
        self.assertEqual(ordering["architecture"], "x86_64")
        self.assertEqual(
            [output["order"] for output in ordering["outputs"]],
            ["gallica-view", "numeric-printed-page"],
        )
        self.assertTrue(
            all(len(output["sha256"]) == 64 for output in ordering["outputs"])
        )
        self.assertTrue(
            all(
                output["resultPathUnderScratch"].startswith("scouting-autoresearch/")
                for output in ordering["outputs"]
            )
        )
        self.assertEqual(ordering["sourceFilesCommittedToRepository"], 0)

    def test_reuse_scope_remains_component_limited(self):
        checkpoint = self.checkpoint
        self.assertIn("Jacques Sevin", checkpoint["approvedComponent"])
        self.assertIn("music", checkpoint["excludedComponents"])
        self.assertIn("Source gallica.bnf.fr", checkpoint["requiredAttribution"])


if __name__ == "__main__":
    unittest.main()
