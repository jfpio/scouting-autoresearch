import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_v3_source_run import load_yaml, v3_source_run_errors
from validate_v3_source_run import CHECKPOINT_PATH, MANIFEST_PATH, QUEUE_PATH, REGISTRY_PATH


class V3SourceRunTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_yaml(MANIFEST_PATH)
        self.registry = load_yaml(REGISTRY_PATH)
        self.queue = load_yaml(QUEUE_PATH)
        self.checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))

    def errors(self, manifest=None, registry=None):
        return v3_source_run_errors(
            manifest or self.manifest,
            registry or self.registry,
            self.queue,
            self.checkpoint,
        )

    def test_repository_manifest_passes(self):
        self.assertEqual(self.errors(), [])

    def test_rejects_intermediate_pull_requests(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["runPolicy"]["intermediatePullRequests"] = True
        self.assertTrue(any("intermediate PRs" in error for error in self.errors(manifest)))

    def test_rejects_a_missing_shortlisted_source(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["sourceUnits"].pop()
        self.assertTrue(any("eleven units" in error for error in self.errors(manifest)))

    def test_rejects_silent_activity_kind_expansion(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["scope"]["productionKinds"].append("exercise")
        self.assertTrue(any("production kinds" in error for error in self.errors(manifest)))

    def test_rejects_stale_piasecki_edition_metadata(self):
        manifest = copy.deepcopy(self.manifest)
        unit = next(
            item
            for item in manifest["sourceUnits"]
            if item["id"] == "piasecki-movement-games-1922"
        )
        unit["year"] = 1920
        self.assertTrue(
            any("movement-games edition metadata" in error for error in self.errors(manifest))
        )

    def test_rejects_missing_polish_acquisition_gate(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["humanGates"] = [
            gate
            for gate in manifest["humanGates"]
            if gate["id"] != "polish-source-acquisition-and-rights"
        ]
        self.assertTrue(
            any("acquisition gate" in error for error in self.errors(manifest))
        )

    def test_rejects_a_proposed_download_that_claims_approval(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["acquisitionPreparation"]["contentDownloadsApproved"] = True
        self.assertTrue(
            any("content downloads are approved" in error for error in self.errors(manifest))
        )

    def test_rejects_an_artifact_candidate_on_another_host(self):
        manifest = copy.deepcopy(self.manifest)
        unit = next(
            item
            for item in manifest["sourceUnits"]
            if item["id"] == "piasecki-movement-games-1922"
        )
        unit["proposedAcquisition"]["url"] = "https://untrusted.example/source.zip"
        self.assertTrue(
            any("outside the registered HTTPS host" in error for error in self.errors(manifest))
        )

    def test_rejects_enabling_a_robots_blocked_zip(self):
        manifest = copy.deepcopy(self.manifest)
        unit = next(
            item
            for item in manifest["sourceUnits"]
            if item["id"] == "dabrowski-winter-games-1935"
        )
        unit["proposedAcquisition"]["status"] = "human-approval-required"
        self.assertTrue(
            any("robots-blocked PBC artifact" in error for error in self.errors(manifest))
        )

    def test_rejects_removing_the_pbc_robots_exclusion(self):
        registry = copy.deepcopy(self.registry)
        collection = next(
            item for item in registry["collections"] if item["id"] == "pbc-rzeszow"
        )
        collection["robotsTxt"]["decision"] = "download-allowed"
        self.assertTrue(
            any("robots ZIP exclusion" in error for error in self.errors(registry=registry))
        )


if __name__ == "__main__":
    unittest.main()
