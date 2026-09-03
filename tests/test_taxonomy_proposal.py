import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from propose_taxonomy import build_candidate_mappings, build_proposal_report


class TaxonomyProposalTests(unittest.TestCase):
    def setUp(self):
        self.proposal = {
            "id": "proposal",
            "proposalType": "taxonomy",
            "proposalVersion": "candidate-1",
            "status": "proposed",
            "createdAt": "2026-09-03",
            "sourceType": "editorial-hypothesis",
            "reviewRequired": True,
            "manualReviewActivityIds": ["b"],
            "categories": [
                {
                    "id": f"category-{index:02d}",
                    "labels": {"pl": f"Kategoria {index}", "en": f"Category {index}"},
                    "definition": {"pl": "Definicja", "en": "Definition"},
                    "evidenceActivityIds": ["a"],
                    "counterexampleActivityIds": ["b"],
                }
                for index in range(1, 11)
            ],
            "mappingRules": {
                "sourceSections": {
                    "Dział": [f"category-{index:02d}" for index in range(1, 11)]
                },
                "legacyTraitCategories": {"stara": ["category-02"]},
            },
        }
        self.analysis = {
            "analysisHash": "analysis-hash",
            "clusters": [{"technicalClusterId": "cluster-1"}],
            "items": [
                {"activityId": "a", "technicalClusterId": "cluster-1"},
                {"activityId": "b", "technicalClusterId": "cluster-1"},
            ],
            "ambiguousAssignments": [{"activityId": "a"}],
            "outliers": {"activityIds": []},
        }
        self.activities = [
            {
                "id": "a",
                "sourceId": "source-1",
                "section": "Dział",
                "traits": ["Źródłowa"],
                "traitCategories": ["stara"],
            },
            {
                "id": "b",
                "sourceId": "source-1",
                "section": "Bez reguły",
                "traits": [],
            },
        ]

    def test_mapping_preserves_source_data_and_combines_explicit_rules(self):
        mappings = build_candidate_mappings(self.activities, self.proposal, self.analysis)
        self.assertEqual(
            mappings[0]["categoryIds"],
            [f"category-{index:02d}" for index in range(1, 11)],
        )
        self.assertEqual(mappings[0]["sourceTraits"], ["Źródłowa"])
        self.assertEqual(mappings[0]["reviewFlags"], ["embedding-ambiguous"])
        self.assertEqual(mappings[1]["status"], "unassigned")
        self.assertEqual(mappings[1]["categoryIds"], [])
        self.assertEqual(mappings[1]["reviewFlags"], ["editorial-boundary"])

    def test_report_is_deterministic_and_never_claims_production_change(self):
        first = build_proposal_report(self.activities, self.proposal, self.analysis)
        second = build_proposal_report(list(reversed(self.activities)), self.proposal, self.analysis)
        self.assertEqual(first, second)
        self.assertTrue(first["proposalOnly"])
        self.assertTrue(first["reviewRequired"])
        self.assertFalse(first["productionTaxonomyChanged"])
        self.assertEqual(first["coverage"]["unassignedActivityIds"], ["b"])

    def test_unknown_rule_category_is_rejected(self):
        self.proposal["mappingRules"]["sourceSections"]["Dział"] = ["missing"]
        with self.assertRaises(ValueError):
            build_candidate_mappings(self.activities, self.proposal, self.analysis)


if __name__ == "__main__":
    unittest.main()
