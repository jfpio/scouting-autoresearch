import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_candidates import candidate_errors, registry_errors


class SourceCandidateTests(unittest.TestCase):
    def setUp(self):
        self.registry = {
            "collection": {
                "baseUrl": "https://example.test/",
                "allowedMethods": ["metadata-only"],
            }
        }
        self.candidate = {
            "id": "candidate-1",
            "recordType": "source-candidate",
            "status": "rights-review",
            "sourceType": "bibliographic-metadata",
            "reviewRequired": True,
            "publicationBlocked": True,
            "subjectId": "author-1",
            "title": "Title",
            "author": {"name": "Author"},
            "originalLanguage": "en",
            "collectionId": "collection",
            "allowedMethodUsed": "metadata-only",
            "canonicalUrl": "https://example.test/item/1",
            "digitalEdition": {
                "identifier": "item-1",
                "editionIdentityStatus": "ambiguous",
            },
            "rightsReview": {
                "status": "human-review-required",
                "humanApproved": False,
                "fullTextEligible": False,
                "imagesEligible": False,
                "translationEligible": False,
                "unresolved": ["Question"],
            },
            "provenanceEvidence": [
                {"id": "evidence-1", "url": "https://example.test/item/1", "supports": ["title"]}
            ],
            "discovery": {
                "metadataPagesInspected": 1,
                "sourceFilesDownloaded": 0,
                "fullTextCopied": False,
                "repositoryContentAdded": "metadata-only",
                "estimatedCostUsd": 0,
            },
        }

    def test_review_only_candidate_passes(self):
        self.assertEqual(candidate_errors(self.candidate, "Review notes", self.registry), [])

    def test_human_accepted_candidate_passes(self):
        self.candidate.update(
            {
                "status": "accepted",
                "reviewRequired": False,
                "publicationBlocked": False,
            }
        )
        self.candidate["rightsReview"] = {
            "status": "human-approved",
            "humanApproved": True,
            "rightsStatus": "public-domain",
            "approvedScope": ["original-text"],
            "fullTextEligible": True,
            "imagesEligible": False,
            "translationEligible": True,
            "humanDecision": {
                "date": "2026-09-03",
                "approvedBy": "repository-owner",
                "basis": "Documented review",
            },
        }
        self.assertEqual(
            candidate_errors(self.candidate, "Decision notes", self.registry, "accepted"), []
        )

    def test_accepted_candidate_requires_recorded_human_decision(self):
        self.candidate.update(
            {
                "status": "accepted",
                "reviewRequired": False,
                "publicationBlocked": False,
            }
        )
        self.candidate["rightsReview"].update(
            {
                "status": "human-approved",
                "humanApproved": True,
                "rightsStatus": "public-domain",
                "approvedScope": ["original-text"],
                "fullTextEligible": True,
                "translationEligible": True,
                "unresolved": [],
            }
        )
        errors = candidate_errors(self.candidate, "Decision notes", self.registry, "accepted")
        self.assertTrue(any("approved collection policy" in error for error in errors))

    def test_accepted_candidate_can_use_approved_collection_policy(self):
        self.registry["collection"]["rightsPresumption"] = {
            "id": "collection-pd-policy",
            "humanApproved": True,
        }
        self.candidate.update(
            {
                "status": "accepted",
                "reviewRequired": False,
                "publicationBlocked": False,
            }
        )
        self.candidate["rightsReview"].update(
            {
                "status": "policy-approved",
                "humanApproved": True,
                "rightsStatus": "public-domain",
                "approvalPolicyId": "collection-pd-policy",
                "catalogClaim": "public-domain-in-the-usa",
                "approvedScope": ["collection-marked-content"],
                "fullTextEligible": True,
                "translationEligible": True,
                "unresolved": [],
                "calculation": {
                    "relevantAuthors": [
                        {
                            "name": "Author",
                            "deathDate": "1941-01-08",
                            "evidenceId": "evidence-1",
                        }
                    ],
                    "lastRelevantAuthorDeathDate": "1941-01-08",
                    "protectionEnded": "2011-12-31",
                    "publicDomainFrom": "2012-01-01",
                },
            }
        )
        self.assertEqual(
            candidate_errors(self.candidate, "Policy notes", self.registry, "accepted"), []
        )

        self.candidate["rightsReview"]["calculation"]["publicDomainFrom"] = "2011-01-01"
        errors = candidate_errors(self.candidate, "Policy notes", self.registry, "accepted")
        self.assertTrue(any("calculation" in error for error in errors))

    def test_policy_approved_collection_configuration_is_validated(self):
        self.registry["collection"].update(
            {
                "status": "approved-by-policy",
                "allowedMethods": ["metadata-only", "documented-download"],
                "rightsPresumption": {
                    "id": "collection-pd-policy",
                    "conditions": [
                        "catalog-public-domain-claim",
                        "seventy-full-calendar-years-after-author-death",
                    ],
                    "resultRightsStatus": "public-domain",
                    "jurisdictions": ["PL", "EU"],
                    "humanApproved": True,
                    "approvedBy": "repository-owner",
                    "approvedAt": "2026-09-03",
                },
            }
        )
        self.assertEqual(registry_errors(self.registry), [])

        self.registry["collection"]["rightsPresumption"]["humanApproved"] = False
        self.assertTrue(any("lacks human approval" in error for error in registry_errors(self.registry)))

    def test_pending_candidate_cannot_enable_full_text(self):
        self.candidate["rightsReview"]["fullTextEligible"] = True
        errors = candidate_errors(self.candidate, "Review notes", self.registry)
        self.assertTrue(any("enables full text" in error for error in errors))

    def test_candidate_must_use_registered_allowed_method(self):
        self.candidate["allowedMethodUsed"] = "documented-download"
        errors = candidate_errors(self.candidate, "Review notes", self.registry)
        self.assertTrue(any("is not allowed" in error for error in errors))

    def test_candidate_url_must_stay_inside_collection(self):
        self.candidate["canonicalUrl"] = "https://elsewhere.test/item/1"
        errors = candidate_errors(self.candidate, "Review notes", self.registry)
        self.assertTrue(any("outside the registered collection" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
