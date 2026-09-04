#!/usr/bin/env python3
"""Acceptance checks for the committed multilingual corpus and generated site."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

from audit_taxonomy_inputs import REPORT_PATH as TAXONOMY_INPUT_AUDIT_PATH
from audit_taxonomy_inputs import build_quality_report
from analyze_taxonomy import REPORT_PATH as TAXONOMY_ANALYSIS_PATH
from analyze_taxonomy import build_analysis, load_usage
from common import GENERATED, ROOT, VAULT, load_markdown, read_json, source_hash
from embed_taxonomy import REPORT_PATH as TAXONOMY_PROGRESS_PATH
from embed_taxonomy import (
    activity_items,
    build_embedding_input,
    build_progress_report,
    input_hash,
    load_config,
)
from evaluate_translation_models import load_evaluation_config
from translate import MAX_OUTPUT_TOKENS, MIN_OUTPUT_TOKENS
from propose_taxonomy import (
    PROPOSAL_PATH as TAXONOMY_PROPOSAL_PATH,
    REPORT_PATH as TAXONOMY_MAPPING_PROPOSAL_PATH,
    build_proposal_report,
)
from validate_candidates import validate_candidates
from validate_collection_reviews import validate_collection_reviews
from validate_editorial_reviews import validate_editorial_reviews


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def repository_files() -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    nested_git: list[Path] = []
    skipped = {"node_modules", ".venv", ".git", "dist", ".astro", "__pycache__"}
    for current, directories, names in os.walk(ROOT):
        current_path = Path(current)
        for directory in directories:
            candidate = current_path / directory
            if directory == ".git" and candidate != ROOT / ".git":
                nested_git.append(candidate)
        directories[:] = [directory for directory in directories if directory not in skipped]
        files.extend(current_path / name for name in names)
    return files, nested_git


def main() -> None:
    errors: list[str] = []
    activity_paths = sorted((VAULT / "activities").glob("*.md"))
    translation_paths = sorted(
        path for path in (VAULT / "translations").glob("*/*.md") if path.name != "README.md"
    )

    sources = {}
    for path in (VAULT / "sources").glob("*.md"):
        metadata, _ = load_markdown(path)
        sources[metadata["id"]] = metadata
        require(metadata.get("rightsStatus") == "public-domain", f"Source {path.stem} is not public-domain", errors)
        for key in ("author", "title", "year", "sourceUrl", "rightsEvidenceUrl", "digitalEditionUrl"):
            require(bool(metadata.get(key)), f"Source {path.stem} lacks {key}", errors)
        require(
            bool(metadata.get("pdfUrl") or metadata.get("textUrl")),
            f"Source {path.stem} lacks a reusable digital text or PDF URL",
            errors,
        )
        if metadata.get("approvalPolicyId") == "project-gutenberg-pd-usa-plus-life-70":
            evidence = metadata.get("rightsEvidence") or {}
            authors = evidence.get("relevantAuthors") or []
            require(
                evidence.get("catalogClaim") == "Public domain in the USA",
                f"Source {path.stem} lacks the exact Gutenberg public-domain claim",
                errors,
            )
            require(bool(evidence.get("catalogUrl")), f"Source {path.stem} lacks the Gutenberg claim URL", errors)
            require(bool(authors), f"Source {path.stem} lacks relevant authors for the life-plus-70 rule", errors)
            death_dates = []
            for author in authors:
                try:
                    death_dates.append(date.fromisoformat(author.get("deathDate", "")))
                except (TypeError, ValueError):
                    require(False, f"Source {path.stem} has an invalid author death date", errors)
                require(bool(author.get("name")), f"Source {path.stem} has an unnamed relevant author", errors)
                require(bool(author.get("evidenceUrl")), f"Source {path.stem} lacks death-date evidence", errors)
            if death_dates:
                last_death_year = max(value.year for value in death_dates)
                expected_end = date(last_death_year + 70, 12, 31).isoformat()
                expected_start = date(last_death_year + 71, 1, 1)
                require(
                    evidence.get("protectionEnded") == expected_end,
                    f"Source {path.stem} has an incorrect life-plus-70 end date",
                    errors,
                )
                require(
                    evidence.get("publicDomainFrom") == expected_start.isoformat(),
                    f"Source {path.stem} has an incorrect public-domain start date",
                    errors,
                )
                require(
                    expected_start <= date.today(),
                    f"Source {path.stem} has not completed 70 full calendar years after the last author death",
                    errors,
                )
            review_record = ROOT / str(metadata.get("rightsReviewRecord", ""))
            require(
                bool(metadata.get("rightsReviewRecord")) and review_record.exists(),
                f"Source {path.stem} lacks its accepted rights-review record",
                errors,
            )
            if review_record.is_file():
                review, _ = load_markdown(review_record)
                processing = review.get("processing") or {}
                require(
                    review.get("rightsReview", {}).get("approvalPolicyId")
                    == metadata.get("approvalPolicyId"),
                    f"Source {path.stem} and its rights review use different policies",
                    errors,
                )
                require(
                    processing.get("sourceId") == path.stem,
                    f"Source {path.stem} and its processing record use different IDs",
                    errors,
                )
                require(
                    processing.get("sourceSha256")
                    == str(metadata.get("sourceRevision", "")).removeprefix("sha256:"),
                    f"Source {path.stem} and its processing record use different revisions",
                    errors,
                )

    v0_ids = {f"hwp-{number:03d}" for number in range(1, 118)} | {f"pw-{number:03d}" for number in range(1, 86)}
    actual_ids: set[str] = set()
    activity_metadata: dict[str, dict] = {}
    for path in activity_paths:
        metadata, body = load_markdown(path)
        activity_id = metadata.get("id")
        actual_ids.add(activity_id)
        activity_metadata[activity_id] = metadata
        require(activity_id == path.stem, f"ID/path mismatch in {path}", errors)
        require(metadata.get("sourceId") in sources, f"Unknown source in {path.name}", errors)
        require(metadata.get("rightsStatus") == "public-domain", f"Non-public full text in {path.name}", errors)
        require(bool(body.strip()), f"Empty body in {path.name}", errors)
        kinds = metadata.get("kinds") or []
        require(
            isinstance(kinds, list) and bool(kinds) and len(kinds) == len(set(kinds)),
            f"Missing or duplicate activity kinds in {path.name}",
            errors,
        )
        require(
            set(kinds).issubset({"game", "trial"}),
            f"Unapproved production activity kind in {path.name}: {kinds}",
            errors,
        )
        require(metadata.get("sourceHash") == source_hash(metadata.get("title", ""), body), f"Bad source hash in {path.name}", errors)
        require(bool(metadata.get("printedPages")), f"Missing printed pages in {path.name}", errors)
        require(metadata.get("originalLanguage") in {"pl", "en"}, f"Unsupported source language in {path.name}", errors)
        require(bool(metadata.get("sourceRevision") or metadata.get("sourceCommit")), f"Missing source revision in {path.name}", errors)
        require(bool(metadata.get("facsimileUrl") or metadata.get("pdfPages")), f"Missing page-level source link in {path.name}", errors)
        require(metadata.get("safetyStatus") == "historical-unreviewed", f"Unexpected safety status in {path.name}", errors)
    require(v0_ids.issubset(actual_ids), f"V0 activity IDs are missing: {sorted(v0_ids - actual_ids)}", errors)

    activities_by_source: dict[str, list[str]] = {}
    for activity_id, metadata in activity_metadata.items():
        activities_by_source.setdefault(metadata["sourceId"], []).append(activity_id)
    for source_id, source in sources.items():
        report_value = source.get("extractionReport")
        if not report_value:
            continue
        report_path = ROOT / report_value
        require(report_path.exists(), f"Source {source_id} extraction report is missing", errors)
        if not report_path.exists():
            continue
        report = read_json(report_path)
        source_ids = sorted(activities_by_source.get(source_id, []))
        report_items = report.get("activities") or []
        report_ids = sorted(item.get("id") for item in report_items)
        require(report.get("sourceId") == source_id, f"Source {source_id} extraction report has the wrong source", errors)
        require(report.get("activityCount") == len(source_ids), f"Source {source_id} extraction count is stale", errors)
        require(report_ids == source_ids, f"Source {source_id} extraction report IDs differ from the corpus", errors)
        require(report.get("wholeSourceCopiedToRepository") is False, f"Source {source_id} report claims a whole-source copy", errors)
        require(not (report.get("deduplication") or {}).get("exactBodyMatches"), f"Source {source_id} has exact duplicate bodies", errors)
        revision = str(source.get("sourceRevision", "")).removeprefix("sha256:")
        require(report.get("sourceSha256") == revision, f"Source {source_id} extraction revision is stale", errors)
        transcription_evidence = report.get("transcriptionEvidence") or {}
        require(
            bool(transcription_evidence.get("sourceStatement")),
            f"Source {source_id} extraction report lacks the source transcription statement",
            errors,
        )
        require(
            bool(transcription_evidence.get("sourceLocation")),
            f"Source {source_id} extraction report lacks the transcription-statement location",
            errors,
        )
        require(
            bool(transcription_evidence.get("deterministicNormalization")),
            f"Source {source_id} extraction report lacks deterministic normalization rules",
            errors,
        )
        require(
            transcription_evidence.get("lexicalModernization") is False,
            f"Source {source_id} extraction report does not prohibit lexical modernization",
            errors,
        )
        review_record = ROOT / str(source.get("rightsReviewRecord", ""))
        if review_record.is_file():
            review, _ = load_markdown(review_record)
            processing = review.get("processing") or {}
            require(
                processing.get("extractionReport") == report_value,
                f"Source {source_id} review points to a different extraction report",
                errors,
            )
            require(
                processing.get("parserVersion") == report.get("parserVersion"),
                f"Source {source_id} review has a stale parser version",
                errors,
            )
            require(
                processing.get("importedActivityCount") == len(source_ids),
                f"Source {source_id} review has a stale imported-activity count",
                errors,
            )
        for item in report_items:
            metadata = activity_metadata.get(item.get("id"), {})
            require(
                item.get("sourceBlockSha256") == metadata.get("sourceBlockSha256"),
                f"Source block evidence differs for {item.get('id')}",
                errors,
            )

    translation_ids: set[str] = set()
    translation_metadata: dict[str, dict] = {}
    for path in translation_paths:
        metadata, body = load_markdown(path)
        activity_id = metadata.get("activityId")
        require(activity_id not in translation_ids, f"Duplicate translation for {activity_id}", errors)
        translation_ids.add(activity_id)
        translation_metadata[activity_id] = metadata
        original_path = VAULT / "activities" / f"{activity_id}.md"
        require(original_path.exists(), f"Translation without original: {path.name}", errors)
        if original_path.exists():
            original, original_body = load_markdown(original_path)
            expected_hash = source_hash(original["title"], original_body)
            require(metadata.get("sourceHash") == expected_hash, f"Stale translation: {path.name}", errors)
            require(
                len(metadata.get("traits", [])) == len(original.get("traits", [])),
                f"Translation invented or dropped traits: {path.name}",
                errors,
            )
            expected_locale = "en" if original.get("originalLanguage") == "pl" else "pl"
            require(metadata.get("locale") == expected_locale, f"Wrong target locale in {path.name}", errors)
            require(path.parent.name == expected_locale, f"Translation is in the wrong directory: {path}", errors)
            translation_policy = sources[original["sourceId"]].get("translationPolicy") or {}
            if translation_policy:
                require(
                    metadata.get("locale") == translation_policy.get("targetLocale"),
                    f"Translation target differs from source policy: {path.name}",
                    errors,
                )
                require(
                    metadata.get("modelRequested") == translation_policy.get("modelRequested"),
                    f"Translation requested model differs from source policy: {path.name}",
                    errors,
                )
                require(
                    metadata.get("promptVersion") == translation_policy.get("promptVersion"),
                    f"Translation prompt differs from source policy: {path.name}",
                    errors,
                )
                if translation_policy.get("reasoningMode"):
                    require(
                        metadata.get("reasoningMode") == translation_policy.get("reasoningMode"),
                        f"Translation reasoning mode differs from source policy: {path.name}",
                        errors,
                    )
                if translation_policy.get("usageRequired"):
                    usage = metadata.get("usage") or {}
                    billing_mode = translation_policy.get("billingMode")
                    require(
                        isinstance(usage.get("promptTokens"), int) and usage["promptTokens"] > 0,
                        f"Translation lacks prompt-token usage: {path.name}",
                        errors,
                    )
                    require(
                        isinstance(usage.get("completionTokens"), int) and usage["completionTokens"] > 0,
                        f"Translation lacks completion-token usage: {path.name}",
                        errors,
                    )
                    require(usage.get("billingMode") == billing_mode, f"Translation billing mode differs from source policy: {path.name}", errors)
                    if billing_mode == "experimental-no-charge":
                        require(usage.get("billedCostUsd") == 0, f"Experimental translation has a nonzero billed cost: {path.name}", errors)
                    elif billing_mode == "education-credit":
                        require(usage.get("billedCostUsd") is None, f"Education-credit translation claims a known billed cost: {path.name}", errors)
                    require(
                        isinstance(usage.get("referenceCostUsd"), (int, float))
                        and usage["referenceCostUsd"] >= 0,
                        f"Translation lacks reference cost: {path.name}",
                        errors,
                    )
                    require(bool(usage.get("priceSource")), f"Translation lacks a price source: {path.name}", errors)
                    require(bool(usage.get("priceAccessedOn")), f"Translation lacks a price access date: {path.name}", errors)
        require(metadata.get("status") == "machine-translation", f"Bad translation status: {path.name}", errors)
        for key in ("model", "modelRequested", "promptVersion", "generatedAt", "title", "section"):
            require(bool(metadata.get(key)), f"Translation {path.name} lacks {key}", errors)
        require(bool(body.strip()), f"Empty translation body: {path.name}", errors)
        if original_path.exists():
            source_urls = set(re.findall(r"https?://[^\s)]+", original_body))
            translated_urls = set(re.findall(r"https?://[^\s)]+", body))
            require(source_urls.issubset(translated_urls), f"Translation dropped a URL or image: {path.name}", errors)
    require(translation_ids == actual_ids, "Source and translation record IDs differ", errors)

    for source_id, source in sources.items():
        policy = source.get("translationPolicy") or {}
        if not policy:
            continue
        evaluation = policy.get("modelEvaluation")
        if evaluation:
            evaluation_path = (ROOT / str(evaluation)).resolve()
            require(
                evaluation_path.is_relative_to(ROOT.resolve()) and evaluation_path.is_file(),
                f"Source {source_id} translation evaluation config is missing",
                errors,
            )
            if evaluation_path.is_file():
                try:
                    evaluation_config = load_evaluation_config(evaluation_path)
                except (OSError, ValueError) as error:
                    require(False, f"Source {source_id} has an invalid translation evaluation: {error}", errors)
                else:
                    require(
                        evaluation_config.get("sourceId") == source_id,
                        f"Source {source_id} translation evaluation targets another source",
                        errors,
                    )
                    require(
                        evaluation_config.get("productionCandidate") == policy.get("modelRequested"),
                        f"Source {source_id} production model differs from its evaluation",
                        errors,
                    )
        report_path = ROOT / str(policy.get("report", ""))
        require(bool(policy.get("report")) and report_path.exists(), f"Source {source_id} translation report is missing", errors)
        if not report_path.is_file():
            continue
        report = read_json(report_path)
        expected_ids = sorted(activities_by_source.get(source_id, []))
        require(report.get("sourceId") == source_id, f"Source {source_id} translation report has the wrong source", errors)
        require(report.get("status") == "complete", f"Source {source_id} translation report is incomplete", errors)
        require(report.get("selectedActivityIds") == expected_ids, f"Source {source_id} translation selection is stale", errors)
        require(report.get("completedActivityIds") == expected_ids, f"Source {source_id} translation completion is stale", errors)
        require(report.get("pendingActivityIds") == [], f"Source {source_id} translation report has pending records", errors)
        require(
            report.get("modelRequested") == policy.get("modelRequested"),
            f"Source {source_id} translation report uses the wrong requested model",
            errors,
        )
        expected_prompt_tokens = sum(
            int((translation_metadata.get(activity_id, {}).get("usage") or {}).get("promptTokens", 0))
            for activity_id in expected_ids
        )
        expected_completion_tokens = sum(
            int((translation_metadata.get(activity_id, {}).get("usage") or {}).get("completionTokens", 0))
            for activity_id in expected_ids
        )
        expected_request_max_output_tokens = sum(
            int(
                (translation_metadata.get(activity_id, {}).get("usage") or {}).get(
                    "requestMaxOutputTokens", 0
                )
            )
            for activity_id in expected_ids
        )
        expected_reference_cost = round(
            sum(
                float((translation_metadata.get(activity_id, {}).get("usage") or {}).get("referenceCostUsd", 0))
                for activity_id in expected_ids
            ),
            8,
        )
        report_usage = report.get("usage") or {}
        require(report_usage.get("promptTokens") == expected_prompt_tokens, f"Source {source_id} prompt-token total is stale", errors)
        require(report_usage.get("completionTokens") == expected_completion_tokens, f"Source {source_id} completion-token total is stale", errors)
        if policy.get("requestBudgetRequired"):
            for activity_id in expected_ids:
                budget = (translation_metadata.get(activity_id, {}).get("usage") or {}).get(
                    "requestMaxOutputTokens"
                )
                require(
                    isinstance(budget, int) and MIN_OUTPUT_TOKENS <= budget <= MAX_OUTPUT_TOKENS,
                    f"Translation {activity_id} lacks a valid requested output-token budget",
                    errors,
                )
            require(
                report_usage.get("requestMaxOutputTokens") == expected_request_max_output_tokens,
                f"Source {source_id} requested output-token total is stale",
                errors,
            )
        require(report_usage.get("billingMode") == policy.get("billingMode"), f"Source {source_id} reports the wrong translation billing mode", errors)
        if policy.get("billingMode") == "experimental-no-charge":
            require(report_usage.get("billedCostUsd") == 0, f"Source {source_id} reports a nonzero billed translation cost", errors)
        elif policy.get("billingMode") == "education-credit":
            require(report_usage.get("billedCostUsd") is None, f"Source {source_id} claims a known billed translation cost", errors)
            require(report_usage.get("referenceCostLimitEnforced") is True, f"Source {source_id} does not report an enforced cost limit", errors)
            require(report_usage.get("maxReferenceCostUsd") == policy.get("maxReferenceCostUsd"), f"Source {source_id} reports the wrong cost limit", errors)
        require(report_usage.get("referenceCostUsd") == expected_reference_cost, f"Source {source_id} reference cost is stale", errors)

    exploration_paths = sorted((VAULT / "exploration").rglob("idea-*.md"))
    require(len(exploration_paths) >= 2, "Expected seeded taxonomy and activity-kind exploration notes", errors)
    for path in exploration_paths:
        metadata, body = load_markdown(path)
        require(metadata.get("proposalType") in {"taxonomy", "activity-kind"}, f"Bad proposal type in {path}", errors)
        require(metadata.get("status") == "proposed", f"Exploration note is not proposed: {path}", errors)
        require(metadata.get("sourceType") == "editorial-hypothesis", f"Exploration note lacks hypothesis marker: {path}", errors)
        require(metadata.get("reviewRequired") is True, f"Exploration note lacks human review gate: {path}", errors)
        require(set((metadata.get("labels") or {}).keys()) == {"pl", "en"}, f"Exploration note lacks bilingual labels: {path}", errors)
        require(bool(body.strip()), f"Empty exploration note: {path}", errors)

    candidate_count, candidate_validation_errors = validate_candidates()
    errors.extend(candidate_validation_errors)
    collection_review_count, collection_review_errors = validate_collection_reviews()
    errors.extend(collection_review_errors)
    editorial_review_count, accepted_editorial_review_count, editorial_review_errors = (
        validate_editorial_reviews()
    )
    errors.extend(editorial_review_errors)

    taxonomy_config = load_config()
    embedding_config = taxonomy_config["embedding"]
    taxonomy_items = activity_items(taxonomy_config)
    taxonomy_ids = {item["id"] for item in taxonomy_items}
    taxonomy_activity_paths = [path for path in activity_paths if path.stem in taxonomy_ids]
    embedding_paths = sorted((ROOT / "data" / "embeddings" / "v1").glob("*.json"))
    embedded_ids: set[str] = set()
    for path in embedding_paths:
        payload = read_json(path)
        activity_id = payload.get("activityId")
        require(activity_id not in embedded_ids, f"Duplicate taxonomy embedding: {activity_id}", errors)
        embedded_ids.add(activity_id)
        activity_path = VAULT / "activities" / f"{activity_id}.md"
        require(activity_path.exists(), f"Embedding without activity: {path}", errors)
        if activity_path.exists():
            metadata, body = load_markdown(activity_path)
            expected_input = build_embedding_input(
                metadata,
                body,
                int(embedding_config["contextCharacters"]),
                embedding_config["recipeVersion"],
            )
            require(payload.get("inputHash") == input_hash(expected_input), f"Stale taxonomy embedding: {path.name}", errors)
            require(payload.get("sourceTraits") == (metadata.get("traits") or []), f"Embedding changed source traits: {path.name}", errors)
        require(payload.get("modelRequested") == embedding_config["model"], f"Wrong embedding model: {path.name}", errors)
        require(payload.get("recipeVersion") == embedding_config["recipeVersion"], f"Wrong embedding recipe: {path.name}", errors)
        vector = payload.get("vector")
        require(
            isinstance(vector, list) and len(vector) == int(embedding_config["dimensions"]),
            f"Wrong embedding dimensions: {path.name}",
            errors,
        )

    if embedding_paths:
        require(TAXONOMY_PROGRESS_PATH.exists(), "Missing taxonomy V1 progress report", errors)
        if TAXONOMY_PROGRESS_PATH.exists():
            progress = read_json(TAXONOMY_PROGRESS_PATH)
            expected_progress = build_progress_report(
                taxonomy_config,
                taxonomy_items,
                generated_at=progress.get("generatedAt"),
            )
            require(
                progress == expected_progress,
                "Taxonomy V1 progress report is stale or nondeterministic",
                errors,
            )
        require(TAXONOMY_INPUT_AUDIT_PATH.exists(), "Missing taxonomy V1 input-quality report", errors)
        if TAXONOMY_INPUT_AUDIT_PATH.exists():
            input_audit = read_json(TAXONOMY_INPUT_AUDIT_PATH)
            expected_input_audit = build_quality_report(
                [load_markdown(path) for path in taxonomy_activity_paths],
                [read_json(path) for path in embedding_paths],
                embedding_config=embedding_config,
            )
            require(
                input_audit == expected_input_audit,
                "Taxonomy V1 input-quality report is stale or nondeterministic",
                errors,
            )
            require(
                not input_audit["corpus"]["candidateNoise"]["sourceFooterIds"],
                "Candidate embedding recipe retains source footers",
                errors,
            )
            require(
                not input_audit["corpus"]["candidateNoise"]["rawUrlIds"],
                "Candidate embedding recipe retains raw URLs",
                errors,
            )
        require(TAXONOMY_ANALYSIS_PATH.exists(), "Missing taxonomy V1 analysis report", errors)
        if TAXONOMY_ANALYSIS_PATH.exists():
            analysis = read_json(TAXONOMY_ANALYSIS_PATH)
            expected_analysis = build_analysis(
                [read_json(path) for path in embedding_paths],
                all_activity_ids=sorted(taxonomy_ids),
                parameters=taxonomy_config["analysis"],
                usage=load_usage(),
            )
            require(analysis == expected_analysis, "Taxonomy V1 analysis report is stale or nondeterministic", errors)
            require(analysis.get("proposalOnly") is True, "Taxonomy analysis is not marked proposal-only", errors)
            require(analysis.get("reviewRequired") is True, "Taxonomy analysis lacks a human-review gate", errors)
            require(
                analysis.get("productionTaxonomyChanged") is False,
                "Taxonomy analysis claims a production taxonomy change",
                errors,
            )
            require(
                set(analysis.get("unassignedProductionCategoryActivityIds", [])) == embedded_ids,
                "Taxonomy analysis silently assigns production categories",
                errors,
            )

    if TAXONOMY_PROPOSAL_PATH.exists():
        proposal, _ = load_markdown(TAXONOMY_PROPOSAL_PATH)
        require(
            TAXONOMY_MAPPING_PROPOSAL_PATH.exists(),
            "Missing taxonomy V1 mapping proposal report",
            errors,
        )
        if TAXONOMY_MAPPING_PROPOSAL_PATH.exists() and TAXONOMY_ANALYSIS_PATH.exists():
            mapping_proposal = read_json(TAXONOMY_MAPPING_PROPOSAL_PATH)
            expected_mapping_proposal = build_proposal_report(
                [activity_metadata[activity_id] for activity_id in sorted(taxonomy_ids)],
                proposal,
                read_json(TAXONOMY_ANALYSIS_PATH),
            )
            require(
                mapping_proposal == expected_mapping_proposal,
                "Taxonomy V1 mapping proposal is stale or nondeterministic",
                errors,
            )
            require(mapping_proposal.get("status") == "proposed", "Taxonomy proposal is not proposed", errors)
            require(mapping_proposal.get("proposalOnly") is True, "Taxonomy mapping is not proposal-only", errors)
            require(mapping_proposal.get("reviewRequired") is True, "Taxonomy mapping lacks human review", errors)
            require(
                mapping_proposal.get("productionTaxonomyChanged") is False,
                "Taxonomy proposal claims a production change",
                errors,
            )
            categories = mapping_proposal.get("categories", [])
            category_ids = [category.get("id") for category in categories]
            require(10 <= len(categories) <= 15, "Taxonomy proposal must have 10-15 categories", errors)
            require(len(category_ids) == len(set(category_ids)), "Taxonomy proposal category IDs repeat", errors)
            mappings = mapping_proposal.get("mappings", [])
            require(
                {mapping.get("activityId") for mapping in mappings} == taxonomy_ids,
                "Taxonomy proposal mapping IDs differ from the corpus",
                errors,
            )
            source_traits = {
                activity_id: metadata.get("traits", [])
                for activity_id, metadata in activity_metadata.items()
                if activity_id in taxonomy_ids
            }
            for mapping in mappings:
                require(
                    mapping.get("sourceTraits") == source_traits.get(mapping.get("activityId")),
                    f"Taxonomy proposal changed source traits for {mapping.get('activityId')}",
                    errors,
                )
                require(
                    set(mapping.get("categoryIds", [])).issubset(set(category_ids)),
                    f"Taxonomy proposal uses an unknown category for {mapping.get('activityId')}",
                    errors,
                )

    for locale in ("pl", "en"):
        json_path = GENERATED / f"activities.{locale}.json"
        jsonl_path = GENERATED / f"activities.{locale}.jsonl"
        require(json_path.exists(), f"Missing {json_path}", errors)
        require(jsonl_path.exists(), f"Missing {jsonl_path}", errors)
        if json_path.exists():
            records = read_json(json_path)
            require(len(records) == len(activity_paths), f"{locale} export has {len(records)} records", errors)
            for record in records:
                for key in ("author", "sourceTitle", "year", "sourceId", "printedPages", "sourceRevision"):
                    require(bool(record.get(key)), f"{locale}/{record.get('id')} lacks {key}", errors)
        if jsonl_path.exists():
            lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            require(len(lines) == len(activity_paths), f"{locale} JSONL has {len(lines)} lines", errors)

    docs = list((ROOT / "src" / "content" / "docs").rglob("*.md")) + list((ROOT / "src" / "content" / "docs").rglob("*.mdx"))
    expected_docs = 14 + 2 * len(activity_paths)
    require(len(docs) == expected_docs, f"Expected {expected_docs} generated docs, found {len(docs)}", errors)
    for path in docs:
        text = path.read_text(encoding="utf-8")
        require(text.startswith("---\n"), f"Missing frontmatter in {path}", errors)
        require("/harcerz-w-polu/book/" not in text or "https://jfpio.github.io/harcerz-w-polu/book/" in text, f"Broken relative source asset in {path}", errors)

    repo_files, nested_git = repository_files()
    forbidden_files = [path for path in repo_files if path.suffix.lower() == ".pdf" or path.name == ".env"]
    require(not forbidden_files, f"Forbidden files committed locally: {forbidden_files}", errors)
    require(not nested_git, f"Nested repositories found: {nested_git}", errors)
    for path in repo_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        require(not re.search(r"MISTRAL_API_KEY[ \t]*=[ \t]*[^\s#]+", text), f"Possible Mistral secret in {path}", errors)

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(
        f"Validation passed: {len(activity_paths)} activities, {len(translation_paths)} translations, {len(sources)} public-domain sources, "
        f"{len(embedding_paths)} taxonomy embeddings, {candidate_count} source candidate "
        f"record(s), {collection_review_count} collection review record(s), "
        f"{editorial_review_count} editorial review record(s) "
        f"({accepted_editorial_review_count} accepted), bilingual exports and docs."
    )


if __name__ == "__main__":
    main()
