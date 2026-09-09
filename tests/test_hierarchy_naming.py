import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from name_hierarchy_clusters import (
    GENERIC_NAMES,
    approved_variant,
    load_configuration,
    parse_response,
    prompt_payload,
    reference_upper_bound,
    review_markdown,
    update_totals,
    validate_registry_state,
)


class HierarchyNamingTests(unittest.TestCase):
    def setUp(self):
        self.config = load_configuration()
        self.unit = {
            "level": "fine",
            "clusterId": "fine-01",
            "parentId": "top-01",
            "size": 10,
            "allowedRepresentativeIds": ["a", "b", "c"],
            "examples": {"central": [], "boundary": [], "nearestOutsideForContrast": []},
        }

    def test_owner_selection_resolves_eligible_amber_variant(self):
        selection, variant = approved_variant(self.config)
        self.assertEqual(selection["blindVariantId"], "candidate-amber")
        self.assertEqual(variant["algorithm"], "kmeans-on-umap-2d")
        self.assertTrue(variant["eligibleForHumanReview"])

    def test_prompt_has_no_expert_hypotheses_or_reasoning_parameter(self):
        payload = prompt_payload(self.unit, [])
        serialized = str(payload).lower()
        for forbidden in ("las", "pomieszczenie", "zuch", "reasoning_effort"):
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn("reasoning_effort", self.config)
        self.assertEqual(self.config["temperature"], 0)

    def test_response_contract_and_representatives(self):
        response = {
            "clusterId": "fine-01", "namePl": "Tropienie śladów",
            "descriptionPl": "Gry skupione na odczytywaniu i podążaniu za śladami.",
            "nameEn": "Following tracks",
            "descriptionEn": "Games centred on reading and following tracks.",
            "representativeIds": ["a", "b"], "overlapNotesPl": "",
            "overlapNotesEn": "", "confidence": "high",
        }
        parsed = parse_response(__import__("json").dumps(response), self.unit, [])
        self.assertEqual(parsed["representativeIds"], ["a", "b"])
        response["representativeIds"] = ["a", "outside"]
        with self.assertRaisesRegex(ValueError, "representative"):
            parse_response(__import__("json").dumps(response), self.unit, [])

    def test_generic_or_repeated_names_are_rejected(self):
        self.assertIn("gry", GENERIC_NAMES)
        response = {
            "clusterId": "fine-01", "namePl": "Gry", "descriptionPl": "Opis.",
            "nameEn": "Games", "descriptionEn": "Description.",
            "representativeIds": ["a", "b"], "overlapNotesPl": "",
            "overlapNotesEn": "", "confidence": "low",
        }
        with self.assertRaisesRegex(ValueError, "generic"):
            parse_response(__import__("json").dumps(response), self.unit, [])

    def test_reference_upper_bound_is_small_and_positive(self):
        cost = reference_upper_bound(self.config, prompt_payload(self.unit, []), "fine")
        self.assertGreater(cost, 0)
        self.assertLess(cost, 0.01)

    def test_configuration_pins_cost_and_execution_safeguards(self):
        execution = self.config["execution"]
        self.assertEqual(self.config["model"], "mistral-large-2512")
        self.assertEqual(self.config["reasoningMode"], "disabled")
        self.assertEqual(execution["billingMode"], "education-credit")
        self.assertIsNone(execution["billedCostUsd"])
        self.assertEqual(execution["maxReferenceCostUsd"], 10)
        self.assertTrue(execution["checkpointAfterEverySuccess"])

    def test_ledger_totals_count_billable_contract_failures(self):
        ledger = {
            "entries": [
                {"usage": {"promptTokens": 10, "completionTokens": 2, "referenceCostUsd": 0.1}},
                {"status": "rejected-contract", "usage": {"promptTokens": 5, "completionTokens": 1, "referenceCostUsd": 0.05}},
            ]
        }
        update_totals(ledger)
        self.assertEqual(ledger["totals"]["requests"], 2)
        self.assertEqual(ledger["totals"]["promptTokens"], 15)
        self.assertEqual(ledger["totals"]["referenceCostUsd"], 0.15)

    def test_review_packet_asks_expert_questions_without_leaking_them_to_prompt(self):
        root = Path(__file__).resolve().parents[1]
        report = json.loads(
            (root / "data" / "reports" / "semantic-map-hierarchy-label-proposals-v1.json").read_text(encoding="utf-8")
        )
        ledger = json.loads(
            (root / "data" / "reports" / "semantic-map-hierarchy-label-ledger-v1.json").read_text(encoding="utf-8")
        )
        rendered = review_markdown(report, ledger)
        for phrase in ("gier w lesie", "gier w pomieszczeniu", "duże gry terenowe", "gry i zabawy zuchowe"):
            self.assertIn(phrase, rendered)
        self.assertNotIn("gier w lesie", str(prompt_payload(self.unit, [])).lower())

    def test_proposal_check_accepts_only_complete_human_registry_after_review(self):
        root = Path(__file__).resolve().parents[1]
        report = json.loads(
            (root / "data" / "reports" / "semantic-map-hierarchy-label-proposals-v1.json").read_text(encoding="utf-8")
        )
        approved = []
        for level in ("fine", "top"):
            for cluster_id, proposal in report[level].items():
                response = proposal["response"]
                approved.append(
                    {
                        "clusterId": cluster_id,
                        "level": level,
                        "status": "human-approved",
                        "proposalInputHash": proposal["inputHash"],
                        **{key: response[key] for key in ("namePl", "descriptionPl", "nameEn", "descriptionEn")},
                    }
                )
        registry = {
            "status": "human-approved",
            "approvedBy": "repository-owner",
            "approvedAt": "2026-09-09T17:30:00+02:00",
            "scope": "navigational-cluster-presentation-only",
            "corpusDigest": report["corpusDigest"],
            "approvedLabels": approved,
        }
        validate_registry_state(registry, report)
        registry["approvedLabels"].pop()
        with self.assertRaisesRegex(ValueError, "40 current proposals"):
            validate_registry_state(registry, report)

    def test_proposal_check_rejects_duplicate_approved_cluster(self):
        root = Path(__file__).resolve().parents[1]
        report = json.loads(
            (root / "data" / "reports" / "semantic-map-hierarchy-label-proposals-v1.json").read_text(encoding="utf-8")
        )
        proposal = report["fine"]["fine-01"]
        response = proposal["response"]
        item = {
            "clusterId": "fine-01",
            "level": "fine",
            "status": "human-approved",
            "proposalInputHash": proposal["inputHash"],
            **{key: response[key] for key in ("namePl", "descriptionPl", "nameEn", "descriptionEn")},
        }
        registry = {
            "status": "human-approved",
            "approvedBy": "repository-owner",
            "approvedAt": "2026-09-09T17:30:00+02:00",
            "scope": "navigational-cluster-presentation-only",
            "corpusDigest": report["corpusDigest"],
            "approvedLabels": [item] * 40,
        }
        with self.assertRaisesRegex(ValueError, "40 current proposals"):
            validate_registry_state(registry, report)


if __name__ == "__main__":
    unittest.main()
