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


if __name__ == "__main__":
    unittest.main()
