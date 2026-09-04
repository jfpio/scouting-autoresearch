import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_collection_reviews import collection_review_errors


class CollectionReviewTests(unittest.TestCase):
    def setUp(self):
        self.registry = {
            "collection": {
                "baseUrl": "https://example.test/",
                "status": "candidate",
                "allowedMethods": ["metadata-only"],
                "reviewRecord": "vault/reviews/inbox/collection-collection.md",
            }
        }
        self.review = {
            "id": "collection-review-1",
            "recordType": "source-collection-review",
            "status": "access-review",
            "reviewRequired": True,
            "collectionId": "collection",
            "canonicalUrl": "https://example.test/catalog",
            "accessReview": {
                "status": "human-review-required",
                "humanApproved": False,
            },
            "robotsTxt": {
                "url": "https://example.test/robots.txt",
                "checkedAt": "2026-09-04",
                "status": "not-found-404",
            },
            "termsOfUse": {
                "checkedAt": "2026-09-04",
                "status": "no-public-reuse-license-found",
                "inspectedPages": ["https://example.test/"],
            },
            "reuseDecision": {
                "pageMetadataAllowed": False,
                "linkDiscoveryAllowed": False,
                "fullTextAllowed": False,
                "directFileDownloadAllowed": False,
                "imagesAllowed": False,
                "followExternalLinksAutomatically": False,
            },
            "unresolved": ["Owner decision"],
            "provenanceEvidence": [
                {"id": "evidence-1", "url": "https://example.test/", "supports": ["identity"]}
            ],
            "discovery": {
                "metadataPagesInspected": 3,
                "sourceFilesDownloaded": 0,
                "fullTextCopied": False,
                "repositoryContentAdded": "metadata-only",
                "estimatedCostUsd": 0,
            },
        }

    def test_pending_metadata_only_review_passes(self):
        self.assertEqual(
            collection_review_errors(self.review, "Review notes", self.registry), []
        )

    def test_pending_review_cannot_enable_downloads(self):
        self.review["reuseDecision"]["directFileDownloadAllowed"] = True
        errors = collection_review_errors(self.review, "Review notes", self.registry)
        self.assertTrue(any("enables reuse" in error for error in errors))

    def test_pending_registry_cannot_enable_link_discovery(self):
        self.registry["collection"]["allowedMethods"].append("link-discovery")
        errors = collection_review_errors(self.review, "Review notes", self.registry)
        self.assertTrue(any("more than metadata" in error for error in errors))

    def test_review_url_must_match_collection(self):
        self.review["canonicalUrl"] = "https://elsewhere.test/catalog"
        errors = collection_review_errors(self.review, "Review notes", self.registry)
        self.assertTrue(any("outside the registered collection" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
