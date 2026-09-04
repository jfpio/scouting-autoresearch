import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from similar_activities import load_activity_metadata, load_config, relation_errors


class SimilarActivityTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.activities = load_activity_metadata()

    def test_approved_relation_passes(self):
        self.assertEqual(relation_errors(self.config, self.activities), [])

    def test_unapproved_relation_fails(self):
        config = copy.deepcopy(self.config)
        config["relations"][0]["status"] = "proposed"
        self.assertTrue(any("human approval" in error for error in relation_errors(config, self.activities)))

    def test_same_record_cannot_link_to_itself(self):
        config = copy.deepcopy(self.config)
        config["relations"][0]["activityIds"] = ["bsh-037", "bsh-037"]
        self.assertTrue(any("two distinct" in error for error in relation_errors(config, self.activities)))

    def test_evidence_score_must_match_candidate_report(self):
        config = copy.deepcopy(self.config)
        config["relations"][0]["evidence"]["tfidfCosine"] = 1.0
        self.assertTrue(any("score evidence is stale" in error for error in relation_errors(config, self.activities)))


if __name__ == "__main__":
    unittest.main()
