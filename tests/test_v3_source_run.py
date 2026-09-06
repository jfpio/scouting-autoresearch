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

    def errors(self, manifest=None):
        return v3_source_run_errors(
            manifest or self.manifest, self.registry, self.queue, self.checkpoint
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


if __name__ == "__main__":
    unittest.main()
