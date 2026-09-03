#!/usr/bin/env python3
"""Acceptance checks for the committed V0 corpus and generated site."""

from __future__ import annotations

import json
import re
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
from propose_taxonomy import (
    PROPOSAL_PATH as TAXONOMY_PROPOSAL_PATH,
    REPORT_PATH as TAXONOMY_MAPPING_PROPOSAL_PATH,
    build_proposal_report,
)
from validate_candidates import validate_candidates


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> None:
    errors: list[str] = []
    activity_paths = sorted((VAULT / "activities").glob("*.md"))
    translation_paths = sorted((VAULT / "translations" / "en").glob("*.md"))
    require(len(activity_paths) == 202, f"Expected 202 activities, found {len(activity_paths)}", errors)
    require(len(translation_paths) == 202, f"Expected 202 English translations, found {len(translation_paths)}", errors)

    sources = {}
    for path in (VAULT / "sources").glob("*.md"):
        metadata, _ = load_markdown(path)
        sources[metadata["id"]] = metadata
        require(metadata.get("rightsStatus") == "public-domain", f"Source {path.stem} is not public-domain", errors)
        for key in ("author", "title", "year", "sourceUrl", "rightsEvidenceUrl", "digitalEditionUrl", "pdfUrl"):
            require(bool(metadata.get(key)), f"Source {path.stem} lacks {key}", errors)

    expected_ids = {f"hwp-{number:03d}" for number in range(1, 118)} | {f"pw-{number:03d}" for number in range(1, 86)}
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
        require(metadata.get("sourceHash") == source_hash(metadata.get("title", ""), body), f"Bad source hash in {path.name}", errors)
        require(bool(metadata.get("printedPages")), f"Missing printed pages in {path.name}", errors)
        require(bool(metadata.get("pdfPages")), f"Missing PDF pages in {path.name}", errors)
        require(metadata.get("safetyStatus") == "historical-unreviewed", f"Unexpected safety status in {path.name}", errors)
    require(actual_ids == expected_ids, f"Activity IDs differ: missing={sorted(expected_ids - actual_ids)}, extra={sorted(actual_ids - expected_ids)}", errors)

    translation_ids: set[str] = set()
    for path in translation_paths:
        metadata, body = load_markdown(path)
        activity_id = metadata.get("activityId")
        translation_ids.add(activity_id)
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
        require(metadata.get("status") == "machine-translation", f"Bad translation status: {path.name}", errors)
        for key in ("model", "modelRequested", "promptVersion", "generatedAt", "title", "section"):
            require(bool(metadata.get(key)), f"Translation {path.name} lacks {key}", errors)
        require(bool(body.strip()), f"Empty translation body: {path.name}", errors)
        if original_path.exists():
            source_urls = set(re.findall(r"https?://[^\s)]+", original_body))
            translated_urls = set(re.findall(r"https?://[^\s)]+", body))
            require(source_urls.issubset(translated_urls), f"Translation dropped a URL or image: {path.name}", errors)
    require(translation_ids == expected_ids, "English and Polish record IDs differ", errors)
    models = {load_markdown(path)[0].get("model") for path in translation_paths}
    require(models == {"mistral-medium-2604"}, f"Unexpected translation model set: {sorted(models)}", errors)

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

    taxonomy_config = load_config()
    embedding_config = taxonomy_config["embedding"]
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
                activity_items(taxonomy_config),
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
                [load_markdown(path) for path in activity_paths],
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
                all_activity_ids=sorted(actual_ids),
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
                [activity_metadata[activity_id] for activity_id in sorted(activity_metadata)],
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
                {mapping.get("activityId") for mapping in mappings} == actual_ids,
                "Taxonomy proposal mapping IDs differ from the corpus",
                errors,
            )
            source_traits = {
                activity_id: metadata.get("traits", [])
                for activity_id, metadata in activity_metadata.items()
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
            require(len(records) == 202, f"{locale} export has {len(records)} records", errors)
            for record in records:
                for key in ("author", "sourceTitle", "year", "sourceId", "printedPages", "pdfPages", "sourceCommit"):
                    require(bool(record.get(key)), f"{locale}/{record.get('id')} lacks {key}", errors)
        if jsonl_path.exists():
            lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            require(len(lines) == 202, f"{locale} JSONL has {len(lines)} lines", errors)

    docs = list((ROOT / "src" / "content" / "docs").rglob("*.md")) + list((ROOT / "src" / "content" / "docs").rglob("*.mdx"))
    require(len(docs) == 418, f"Expected 418 generated docs, found {len(docs)}", errors)
    for path in docs:
        text = path.read_text(encoding="utf-8")
        require(text.startswith("---\n"), f"Missing frontmatter in {path}", errors)
        require("/harcerz-w-polu/book/" not in text or "https://jfpio.github.io/harcerz-w-polu/book/" in text, f"Broken relative source asset in {path}", errors)

    forbidden_files = [path for path in ROOT.rglob("*") if path.is_file() and (path.suffix.lower() == ".pdf" or path.name == ".env")]
    require(not forbidden_files, f"Forbidden files committed locally: {forbidden_files}", errors)
    nested_git = [path for path in ROOT.rglob(".git") if path != ROOT / ".git"]
    require(not nested_git, f"Nested repositories found: {nested_git}", errors)
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {"node_modules", ".venv", ".git"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        require(not re.search(r"MISTRAL_API_KEY[ \t]*=[ \t]*[^\s#]+", text), f"Possible Mistral secret in {path}", errors)

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(
        "Validation passed: 202 activities, 202 translations, 2 public-domain sources, "
        f"{len(embedding_paths)} taxonomy embeddings, {candidate_count} source candidate "
        "record(s), bilingual exports and docs."
    )


if __name__ == "__main__":
    main()
