import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from prepare_editorial_review import build_pending_review, load_editorial_config
from validate_editorial_reviews import editorial_review_errors


class EditorialReviewTests(unittest.TestCase):
    def setUp(self):
        self.config = load_editorial_config()
        self.activity_path = Path(__file__).resolve().parents[1] / "vault" / "activities" / "bsh-001.md"
        self.review, self.body = build_pending_review(self.activity_path, self.config)
        from common import load_markdown

        activity, activity_body = load_markdown(self.activity_path)
        self.activities = {activity["id"]: (activity, activity_body, self.activity_path)}

    def errors(self, review=None, stage="inbox"):
        return editorial_review_errors(
            review or self.review,
            self.body,
            self.activities,
            self.config,
            stage,
        )

    def test_pending_review_passes(self):
        self.assertEqual(self.errors(), [])

    def test_stale_review_fails(self):
        review = copy.deepcopy(self.review)
        review["sourceHash"] = "0" * 64
        self.assertTrue(any("stale" in error for error in self.errors(review)))

    def test_pending_review_cannot_contain_ratings(self):
        review = copy.deepcopy(self.review)
        review["valueReview"]["ratings"]["clarity"] = "strong"
        self.assertTrue(any("has value ratings" in error for error in self.errors(review)))

    def test_editorial_review_cannot_approve_rights(self):
        review = copy.deepcopy(self.review)
        review["safetyReview"]["rightsStatus"] = "public-domain"
        self.assertTrue(any("forbidden" in error for error in self.errors(review)))

    def test_accepted_controlled_review_requires_controls(self):
        review = copy.deepcopy(self.review)
        review.update(
            {
                "status": "accepted",
                "reviewRequired": False,
                "humanApproved": True,
                "publicationRecommendation": "publish-with-warning",
                "humanDecision": {
                    "date": "2026-09-04",
                    "reviewedBy": "human-reviewer",
                    "basis": "Manual review",
                },
            }
        )
        review["valueReview"]["outcome"] = "adapt"
        review["valueReview"]["ratings"] = {
            dimension: "adequate" for dimension in self.config["valueReview"]["dimensions"]
        }
        review["safetyReview"]["outcome"] = "suitable-with-controls"
        review["safetyReview"]["riskAreas"] = ["projectiles-or-weapons"]
        self.assertTrue(any("lacks controls" in error for error in self.errors(review, "accepted")))

        review["safetyReview"]["controls"] = ["Use a closed range and a supervised firing line."]
        self.assertEqual(self.errors(review, "accepted"), [])


if __name__ == "__main__":
    unittest.main()
