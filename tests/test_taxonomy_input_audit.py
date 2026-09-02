import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_taxonomy_inputs import build_quality_report
from embed_taxonomy import build_embedding_input


def record(activity_id: str, body: str) -> tuple[dict, str]:
    return (
        {
            "id": activity_id,
            "sourceId": "hwp-1946",
            "kinds": ["game"],
            "title": f"Tytuł {activity_id}",
            "section": "Dział",
            "traits": [],
        },
        body,
    )


class TaxonomyInputAuditTests(unittest.TestCase):
    def test_report_counts_noise_and_recipe_invalidation_without_source_text(self):
        records = [
            record("hwp-001", "Długa treść bez odnośnika."),
            record(
                "hwp-002",
                "Krótka treść.\n\n---\n\n*Źródło skanu: [Biblioteka](https://example.test/record).*",
            ),
        ]
        caches = [
            {
                "activityId": metadata["id"],
                "generatedAt": "2026-09-02T12:00:00+00:00",
                "input": build_embedding_input(metadata, body, 600, "activity-context-v1"),
            }
            for metadata, body in records
        ]
        config = {
            "model": "mistral-embed-2312",
            "recipeVersion": "activity-context-v1",
            "contextCharacters": 600,
        }
        report = build_quality_report(records, caches, embedding_config=config)
        self.assertEqual(report["status"], "recipe-upgrade-pending")
        self.assertEqual(report["corpus"]["contentChangedActivityIds"], ["hwp-002"])
        self.assertEqual(report["corpus"]["activeNoise"]["sourceFooterIds"], ["hwp-002"])
        self.assertEqual(report["corpus"]["candidateNoise"]["sourceFooterIds"], [])
        self.assertEqual(report["corpus"]["candidateNoise"]["rawUrlIds"], [])
        self.assertEqual(report["existingCaches"]["invalidatedByRecipeChange"], 2)
        self.assertEqual(report["remediation"]["reembedBeforeNewActivities"], ["hwp-001", "hwp-002"])
        self.assertIsNone(report["remediation"]["nextNewActivityId"])
        serialized = str(report)
        self.assertNotIn("Krótka treść", serialized)
        self.assertNotIn("https://example.test", serialized)

    def test_report_is_independent_of_input_order(self):
        records = [record("hwp-001", "Pierwsza."), record("hwp-002", "Druga.")]
        caches = [
            {
                "activityId": metadata["id"],
                "generatedAt": "2026-09-02T12:00:00+00:00",
                "input": build_embedding_input(metadata, body, 600, "activity-context-v1"),
            }
            for metadata, body in records
        ]
        config = {
            "model": "mistral-embed-2312",
            "recipeVersion": "activity-context-v1",
            "contextCharacters": 600,
        }
        first = build_quality_report(records, caches, embedding_config=config)
        second = build_quality_report(
            list(reversed(records)),
            list(reversed(caches)),
            embedding_config=config,
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
