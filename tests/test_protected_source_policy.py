import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_protected_source_policy import load_policy, protected_source_policy_errors


class ProtectedSourcePolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.document = Path(__file__)

    def errors(self, policy=None):
        return protected_source_policy_errors(policy or self.policy, self.document)

    def test_committed_policy_passes(self):
        self.assertEqual(self.errors(), [])

    def test_link_only_cannot_include_ocr(self):
        policy = copy.deepcopy(self.policy)
        policy["linkOnly"]["excludedContent"].remove("ocr")
        self.assertTrue(any("exclusions" in error for error in self.errors(policy)))

    def test_quote_requires_human_decision(self):
        policy = copy.deepcopy(self.policy)
        policy["quotation"]["humanApprovalRequiredPerExcerpt"] = False
        self.assertTrue(any("human approval" in error for error in self.errors(policy)))

    def test_quote_cannot_claim_numeric_safe_harbor(self):
        policy = copy.deepcopy(self.policy)
        policy["quotation"]["noNumericSafeHarbor"] = False
        self.assertTrue(any("numeric" in error for error in self.errors(policy)))

    def test_policy_document_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.md"
            self.assertTrue(any("document" in error for error in protected_source_policy_errors(self.policy, missing)))


if __name__ == "__main__":
    unittest.main()
