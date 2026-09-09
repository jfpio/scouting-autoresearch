import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from render_semantic_map import (
    BASE_REPORT_PATH,
    HIERARCHY_REPORT_PATH,
    LABEL_REGISTRY_PATH,
    PROPOSAL_REPORT_PATH,
    SELECTION_PATH,
    accessible_html,
    approved_label_map,
    build_publication_report,
    cluster_download_options,
    cluster_txt,
    convex_hull,
    finalize_offline_html,
    percentile_bounds,
    relation_svg,
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def approved_registry(proposals, selection):
    labels = []
    for level in ("fine", "top"):
        for cluster_id, proposal in proposals[level].items():
            response = proposal["response"]
            labels.append(
                {
                    "clusterId": cluster_id,
                    "level": level,
                    "status": "human-approved",
                    "proposalInputHash": proposal["inputHash"],
                    "namePl": response["namePl"],
                    "descriptionPl": response["descriptionPl"],
                    "nameEn": response["nameEn"],
                    "descriptionEn": response["descriptionEn"],
                }
            )
    return {
        "status": "human-approved",
        "approvedBy": "repository-owner",
        "approvedAt": "2026-09-09T17:30:00+02:00",
        "scope": "navigational-cluster-presentation-only",
        "corpusDigest": selection["corpusDigest"],
        "approvedLabels": labels,
    }


class SemanticMapHierarchyPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_json(BASE_REPORT_PATH)
        cls.hierarchy = load_json(HIERARCHY_REPORT_PATH)
        cls.proposals = load_json(PROPOSAL_REPORT_PATH)
        cls.selection = load_yaml(SELECTION_PATH)

    def test_unapproved_registry_keeps_publication_closed(self):
        registry = {
            "status": "human-review-required",
            "scope": "navigational-cluster-presentation-only",
            "approvedLabels": [],
        }
        with self.assertRaisesRegex(ValueError, "human-approved labels"):
            approved_label_map(self.hierarchy, self.proposals, self.selection, registry)

    def test_complete_human_approval_produces_portable_914_point_report(self):
        registry = approved_registry(self.proposals, self.selection)
        labels = approved_label_map(self.hierarchy, self.proposals, self.selection, registry)
        report = build_publication_report(
            self.base, self.hierarchy, self.selection, registry, labels
        )
        self.assertEqual(len(report["points"]), 914)
        self.assertEqual(len({item["activityId"] for item in report["points"]}), 914)
        self.assertEqual(len(report["clusters"]["fine"]), 32)
        self.assertEqual(len(report["clusters"]["top"]), 8)
        self.assertTrue(all(item["boundaryPolygon"] for item in report["clusters"]["fine"]))
        self.assertTrue(report["projectionIsNavigationalOnly"])
        self.assertEqual(report["generatedAt"], registry["approvedAt"])
        self.assertEqual(
            report["labelApproval"],
            {
                "approvedBy": "repository-owner",
                "approvedAt": registry["approvedAt"],
                "scope": "navigational-cluster-presentation-only",
            },
        )
        self.assertEqual(
            {item["status"] for item in report["approvedRelationOverlays"]},
            {"human-approved"},
        )
        serialized = json.dumps(report)
        self.assertNotIn("algorithmicCandidates", serialized)
        self.assertNotIn("nearestNeighbors", serialized)

    def test_partial_or_stale_approval_is_rejected(self):
        registry = approved_registry(self.proposals, self.selection)
        registry["approvedLabels"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            approved_label_map(self.hierarchy, self.proposals, self.selection, registry)
        registry = approved_registry(self.proposals, self.selection)
        registry["approvedLabels"][0]["proposalInputHash"] = "stale"
        with self.assertRaisesRegex(ValueError, "current proposal"):
            approved_label_map(self.hierarchy, self.proposals, self.selection, registry)

    def test_approval_without_a_zoned_timestamp_is_rejected(self):
        registry = approved_registry(self.proposals, self.selection)
        registry["approvedAt"] = "2026-09-09T17:30:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            approved_label_map(self.hierarchy, self.proposals, self.selection, registry)

    def test_accessible_list_uses_summaries_not_full_game_bodies(self):
        records = [
            {
                "id": "game-1",
                "title": "Visible title",
                "author": "Author",
                "sourceTitle": "Book",
                "year": 1911,
                "topName": "Region",
                "fineName": "Subregion",
                "activityUrl": "/scouting-autoresearch/activities/game-1/",
                "summary": "Short summary",
                "body": "FULL BODY MUST NOT LEAK",
            }
        ]
        rendered = accessible_html(records, "pl", [])
        self.assertIn("data-accessible-map-list", rendered)
        self.assertIn("Visible title", rendered)
        self.assertNotIn("Short summary", rendered)
        self.assertNotIn("FULL BODY MUST NOT LEAK", rendered)

    def test_cluster_txt_contains_only_members_with_full_text_and_provenance(self):
        report = {"reportDigest": "digest"}
        cluster = {
            "id": "fine-01",
            "size": 1,
            "labels": {
                "pl": {"name": "Tropienie", "description": "Gry tropieniowe."},
                "en": {"name": "Tracking", "description": "Tracking games."},
            },
        }
        common = {
            "author": "Autor",
            "year": 1911,
            "sourceTitle": "Książka",
            "sourceUrl": "https://example.test/source",
            "digitalEditionUrl": "https://example.test/edition",
            "facsimileUrl": "https://example.test/scan",
            "rightsStatus": "public-domain",
            "originalLanguage": "pl",
            "translationStatus": "source-text",
            "translationModel": None,
            "activityUrl": "/scouting-autoresearch/activities/game-1/",
            "topClusterId": "top-01",
        }
        records = [
            {**common, "id": "game-1", "title": "W klastrze", "body": "PEŁNY TEKST", "fineClusterId": "fine-01"},
            {**common, "id": "game-2", "title": "Poza klastrem", "body": "NIE DOŁĄCZAJ", "fineClusterId": "fine-02"},
        ]
        rendered = cluster_txt(report, cluster, "fine", records, "pl")
        self.assertIn("PEŁNY TEKST", rendered)
        self.assertIn("public-domain", rendered)
        self.assertIn("https://example.test/source", rendered)
        self.assertNotIn("NIE DOŁĄCZAJ", rendered)

    def test_download_selector_covers_all_40_approved_clusters(self):
        registry = approved_registry(self.proposals, self.selection)
        labels = approved_label_map(self.hierarchy, self.proposals, self.selection, registry)
        report = build_publication_report(
            self.base, self.hierarchy, self.selection, registry, labels
        )
        options = cluster_download_options(report, "pl")
        self.assertEqual(len(options), 40)
        self.assertEqual({item["level"] for item in options}, {"top", "fine"})
        rendered = accessible_html([], "pl", [], options)
        self.assertIn("data-cluster-downloads", rendered)
        self.assertIn("downloads/top/top-01.txt", rendered)
        self.assertIn("downloads/fine/fine-32.txt", rendered)
        self.assertIn("Pobierz TXT", rendered)
        self.assertIn("pracować nad tym typem gier z pomocą LLM", rendered)

    def test_convex_hull_is_stable_and_excludes_interior_points(self):
        points = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.5, 0.5)]
        self.assertEqual(
            convex_hull(points),
            [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        )

    def test_relation_svg_uses_pinned_local_coordinate_normalization(self):
        bounds = percentile_bounds([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)])
        self.assertEqual(len(bounds), 4)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "relations.svg"
            relation_svg(
                output,
                [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]],
                ["a", "b", "c"],
                [{"activityIds": ["a", "c"]}],
            )
            rendered = output.read_text(encoding="utf-8")
            self.assertIn('data-approved-relation-layer="true"', rendered)
            self.assertIn("<line ", rendered)

    def test_offline_postprocessing_removes_remote_resource_tags(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            path.write_text(
                '<html><head><link href="https://fonts.googleapis.com/example" rel="stylesheet">'
                '<script>const provenance = "https://unpkg.com/dependency";</script></head></html>',
                encoding="utf-8",
            )
            finalize_offline_html(path, "pl")
            rendered = path.read_text(encoding="utf-8")
            self.assertIn('<html lang="pl">', rendered)
            self.assertNotIn('<link href="https://', rendered)
            self.assertIn('"https://unpkg.com/dependency"', rendered)

    def test_renderer_reuses_analysis_without_embedding_requests(self):
        renderer = (Path(__file__).resolve().parents[1] / "scripts" / "render_semantic_map.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("inline_data=False", renderer)
        self.assertIn("offline_mode=True", renderer)
        self.assertIn("enable_topic_tree=True", renderer)
        self.assertIn("cluster_boundary_polygons=True", renderer)
        self.assertNotIn("/v1/embeddings", renderer)
        self.assertNotIn("MISTRAL_API_KEY", renderer)


if __name__ == "__main__":
    unittest.main()
