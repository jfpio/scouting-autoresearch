#!/usr/bin/env python3
"""Validate human-gated editorial value and safety review records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import ROOT, VAULT, load_markdown, source_hash
from prepare_editorial_review import load_editorial_config


REVIEW_DIRS = {
    "inbox": VAULT / "reviews" / "editorial" / "inbox",
    "accepted": VAULT / "reviews" / "editorial" / "accepted",
}
FORBIDDEN_DECISION_FIELDS = {
    "rightsStatus",
    "rightsDecision",
    "rightsApproved",
    "publicationApproved",
}


def nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in nested_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in nested_keys(item)}
    return set()


def editorial_review_errors(
    metadata: dict[str, Any],
    body: str,
    activities: dict[str, tuple[dict[str, Any], str, Path]],
    config: dict[str, Any],
    review_stage: str = "inbox",
) -> list[str]:
    review_id = metadata.get("id") or "<missing-id>"
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(f"{review_id}: {message}")

    require(metadata.get("recordType") == "activity-editorial-review", "bad recordType")
    require(metadata.get("schemaVersion") == 1, "bad schemaVersion")
    require(metadata.get("frameworkVersion") == config.get("frameworkVersion"), "bad frameworkVersion")
    require(bool(body.strip()), "empty review body")
    require(
        not (FORBIDDEN_DECISION_FIELDS & nested_keys(metadata)),
        "contains a forbidden rights or publication approval field",
    )

    activity_id = metadata.get("activityId")
    activity_entry = activities.get(activity_id)
    require(activity_entry is not None, f"unknown activity {activity_id}")
    if activity_entry:
        activity, activity_body, activity_path = activity_entry
        expected_hash = source_hash(str(activity.get("title", "")), activity_body)
        require(metadata.get("id") == f"editorial-review-{activity_id}", "ID does not match activity")
        require(metadata.get("sourceId") == activity.get("sourceId"), "sourceId does not match activity")
        require(metadata.get("sourceHash") == expected_hash, "review is stale for the activity sourceHash")
        require(metadata.get("activityPath") == str(activity_path.relative_to(ROOT)), "activityPath does not match activity")

    value = metadata.get("valueReview") or {}
    safety = metadata.get("safetyReview") or {}
    ratings = value.get("ratings") or {}
    dimensions = set(config["valueReview"]["dimensions"])
    require(set(ratings) == dimensions, "value ratings do not match configured dimensions")
    require(isinstance(value.get("notes"), list), "value notes must be a list")
    require(isinstance(safety.get("riskAreas"), list), "riskAreas must be a list")
    require(
        len(safety.get("riskAreas") or []) == len(set(safety.get("riskAreas") or [])),
        "riskAreas contain duplicates",
    )
    require(isinstance(safety.get("controls"), list), "safety controls must be a list")
    require(isinstance(safety.get("notes"), list), "safety notes must be a list")

    separation = metadata.get("separationChecks") or {}
    for field in ("rightsDecisionChanged", "sourceTextChanged", "translationChanged"):
        require(separation.get(field) is False, f"editorial review changed protected concern {field}")

    if review_stage == "inbox":
        defaults = config["pendingDefaults"]
        require(metadata.get("status") == "editorial-review", "inbox status must be editorial-review")
        require(metadata.get("reviewRequired") is True, "pending review lacks human-review gate")
        require(metadata.get("humanApproved") is False, "pending review claims human approval")
        require(value.get("outcome") == defaults["valueOutcome"], "pending review has a value decision")
        require(all(rating is None for rating in ratings.values()), "pending review has value ratings")
        require(safety.get("outcome") == defaults["safetyOutcome"], "pending review has a safety decision")
        require(safety.get("riskAreas") == [], "pending review has selected risks")
        require(safety.get("controls") == [], "pending review has safety controls")
        require(
            metadata.get("publicationRecommendation") == defaults["publicationRecommendation"],
            "pending review has a publication recommendation",
        )
    elif review_stage == "accepted":
        require(metadata.get("status") == "accepted", "accepted status must be accepted")
        require(metadata.get("reviewRequired") is False, "accepted review still requires human action")
        require(metadata.get("humanApproved") is True, "accepted review lacks human approval")
        require(value.get("outcome") in config["valueReview"]["outcomes"], "bad value outcome")
        allowed_ratings = set(config["valueReview"]["ratings"])
        require(all(rating in allowed_ratings for rating in ratings.values()), "bad value rating")
        require(safety.get("outcome") in config["safetyReview"]["outcomes"], "bad safety outcome")
        require(
            set(safety.get("riskAreas") or []).issubset(set(config["safetyReview"]["riskAreas"])),
            "unknown safety risk area",
        )
        if safety.get("outcome") == "suitable-with-controls":
            require(bool(safety.get("controls")), "controlled safety outcome lacks controls")
        require(
            metadata.get("publicationRecommendation") in config["publicationReview"]["outcomes"],
            "bad publication recommendation",
        )
        decision = metadata.get("humanDecision") or {}
        require(
            all(bool(decision.get(field)) for field in ("date", "reviewedBy", "basis")),
            "accepted review lacks a recorded human decision",
        )
    else:
        require(False, f"unknown review stage {review_stage}")
    return errors


def load_activities() -> dict[str, tuple[dict[str, Any], str, Path]]:
    activities: dict[str, tuple[dict[str, Any], str, Path]] = {}
    for path in sorted((VAULT / "activities").glob("*.md")):
        metadata, body = load_markdown(path)
        activities[metadata.get("id")] = (metadata, body, path)
    return activities


def validate_editorial_reviews() -> tuple[int, int, list[str]]:
    activities = load_activities()
    config = load_editorial_config()
    errors: list[str] = []
    ids: list[str] = []
    total = 0
    accepted = 0
    for review_stage, directory in REVIEW_DIRS.items():
        for path in sorted(directory.glob("*.md")):
            if path.name == "README.md":
                continue
            metadata, body = load_markdown(path)
            ids.append(metadata.get("id"))
            errors.extend(editorial_review_errors(metadata, body, activities, config, review_stage))
            total += 1
            accepted += review_stage == "accepted"
    if len(ids) != len(set(ids)):
        errors.append("Editorial-review IDs are not unique")
    return total, accepted, errors


def main() -> None:
    total, accepted, errors = validate_editorial_reviews()
    if errors:
        print("Editorial-review validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Editorial-review validation passed: {total} record(s), {accepted} accepted.")


if __name__ == "__main__":
    main()
