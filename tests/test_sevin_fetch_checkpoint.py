import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import ROOT, load_markdown


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
        self.assertIn(
            checkpoint["status"],
            {"view-fetch-in-progress", "views-fetched", "page-scope-review-pending"},
        )
        self.assertEqual(
            checkpoint["fetchStrategy"],
            "iiif-view-fallback-after-two-pdf-429s",
        )
        view_fetch = checkpoint["viewFetch"]
        self.assertEqual(view_fetch["totalViews"], checkpoint["pagination"]["viewCount"])
        self.assertEqual(view_fetch["completedViews"], len(view_fetch["items"]))
        self.assertGreater(view_fetch["completedViews"], 0)
        self.assertEqual(
            checkpoint["status"] in {"views-fetched", "page-scope-review-pending"},
            view_fetch["completedViews"] == view_fetch["totalViews"],
        )

    def test_completed_view_fetch_has_a_contiguous_verified_ledger(self):
        view_fetch = self.checkpoint["viewFetch"]
        self.assertEqual(view_fetch["status"], "complete")
        self.assertEqual(view_fetch["completedViews"], 188)
        self.assertEqual(view_fetch["totalViews"], 188)
        items = view_fetch["items"]
        self.assertEqual([item["view"] for item in items], list(range(1, 189)))
        self.assertTrue(all(item["status"] == "complete" for item in items))
        self.assertTrue(all(len(item["sha256"]) == 64 for item in items))
        self.assertTrue(all(item["bytes"] > 0 for item in items))
        self.assertEqual(sum(item["bytes"] for item in items), 55_797_764)
        self.assertEqual(view_fetch["retrievedBytes"], 55_797_764)
        self.assertEqual([item["view"] for item in items if item["reused"]], [13, 19, 29])
        self.assertEqual(view_fetch["reusedViews"], [13, 19, 29])
        self.assertEqual(view_fetch["failedViewAttempts"], 0)
        datetime.fromisoformat(view_fetch["completedAt"])

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

    def test_full_contact_sheet_job_is_reproducible_and_user_portable(self):
        path = ROOT / "jobs" / "helios" / "chamarande-contact-sheets.slurm"
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/bin/bash -l\n"))
        self.assertIn("#SBATCH --partition=plgrid", text)
        self.assertIn("#SBATCH --account=plgcredibleai2026-cpu", text)
        self.assertIn("/plgrid/%u/scouting-autoresearch/logs/", text)
        self.assertNotIn("plgjfpio", text)
        self.assertIn("expected_view_count=188", text)
        self.assertIn(self.checkpoint["pagination"]["sha256"], text)
        self.assertIn("contact-sheet-view-order.jpg", text)
        self.assertIn("contact-sheet-printed-order.jpg", text)
        self.assertIn('rm -rf -- "${temporary_dir}"', text)
        self.assertIn('b"<!DOCTYPE"', text)

    def test_full_contact_sheet_run_is_recorded_with_slurm_evidence(self):
        run = self.checkpoint["iiifFullContactSheets"]
        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["scheduler"], "slurm")
        self.assertEqual(run["jobId"], "21977902")
        self.assertEqual(run["architecture"], "x86_64")
        self.assertEqual(run["partition"], "plgrid")
        self.assertEqual(run["account"], "plgcredibleai2026-cpu")
        self.assertEqual(run["requestedCpus"], 1)
        self.assertEqual(run["requestedMemory"], "2G")
        self.assertEqual(run["exitCode"], "0:0")
        self.assertEqual(run["inputViews"], 188)
        self.assertEqual(run["numericPrintedPages"], 133)
        self.assertEqual(run["paginationSha256"], self.checkpoint["pagination"]["sha256"])
        self.assertEqual(
            [output["order"] for output in run["outputs"]],
            ["gallica-view", "numeric-printed-page"],
        )
        self.assertTrue(all(len(output["sha256"]) == 64 for output in run["outputs"]))
        self.assertTrue(
            all(
                output["resultPathUnderScratch"].startswith("scouting-autoresearch/")
                for output in run["outputs"]
            )
        )
        self.assertEqual(run["sourceFilesCommittedToRepository"], 0)

    def test_prose_scope_is_only_a_human_review_proposal(self):
        review_path = ROOT / self.checkpoint["componentScopeReview"]["reviewPath"]
        review, body = load_markdown(review_path)
        proposed = review["proposedOcrScope"]
        proposed_ranges = proposed["proposedViewRanges"]
        proposed_count = sum(end - start + 1 for start, end in proposed_ranges)

        self.assertEqual(review["recordType"], "source-component-scope")
        self.assertEqual(review["status"], "proposed")
        self.assertTrue(review["reviewRequired"])
        self.assertFalse(review["humanApproved"])
        self.assertFalse(proposed["executionReady"])
        self.assertEqual(proposed_count, 113)
        self.assertEqual(proposed_count, proposed["proposedViewCount"])
        self.assertEqual(proposed["plannedModel"], "mistral-ocr-4-1")
        self.assertEqual(proposed["referenceCostEstimateUsd"], 0.452)
        self.assertIsNone(proposed["billedCostUsd"])
        self.assertEqual(
            proposed_ranges,
            self.checkpoint["componentScopeReview"]["proposedViewRanges"],
        )
        self.assertTrue(self.checkpoint["componentScopeReview"]["mixedPageBlockReviewRequired"])
        self.assertIn("propozycją, nie zgodą", body)

        ocr = yaml.safe_load(
            (ROOT / "config" / "ocr" / "chamarande-1934.yaml").read_text(encoding="utf-8")
        )
        self.assertFalse(ocr["execution"]["executionReady"])
        self.assertEqual(ocr["execution"]["approvedViewRanges"], [])

    def test_reuse_scope_remains_component_limited(self):
        checkpoint = self.checkpoint
        self.assertIn("Jacques Sevin", checkpoint["approvedComponent"])
        self.assertIn("music", checkpoint["excludedComponents"])
        self.assertIn("Source gallica.bnf.fr", checkpoint["requiredAttribution"])


if __name__ == "__main__":
    unittest.main()
