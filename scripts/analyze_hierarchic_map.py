#!/usr/bin/env python3
"""Compare two deterministic two-level clusterings for the semantic-map pilot."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(variable, "1")

import numpy as np
import sklearn
import yaml
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

from analyze_semantic_map import load_current_caches
from common import ROOT, VAULT, load_markdown, read_json, write_json
from embed_semantic_map import activity_items, canonical_hash, corpus_digest, load_config


BASE_REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-v3-analysis.json"
REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-hierarchy-pilot-v1.json"
REVIEW_JSON_PATH = ROOT / "data" / "reports" / "semantic-map-hierarchy-review-v1.json"
REVIEW_MD_PATH = ROOT / "vault" / "reviews" / "inbox" / "semantic-map-hierarchy-review-v1.md"


def normalized(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms == 0):
        raise ValueError("Hierarchy input contains a zero vector")
    return vectors / norms[:, np.newaxis]


def canonical_labels(labels: np.ndarray, features: np.ndarray, ids: list[str]) -> np.ndarray:
    """Replace arbitrary K-Means labels with stable centroid/min-ID ordering."""

    keys = []
    for old in sorted(set(int(value) for value in labels)):
        members = np.flatnonzero(labels == old)
        centroid = np.mean(features[members], axis=0)
        keys.append((tuple(np.round(centroid, 12)), min(ids[index] for index in members), old))
    mapping = {old: new for new, (_, _, old) in enumerate(sorted(keys))}
    return np.asarray([mapping[int(value)] for value in labels], dtype=np.int64)


def fit_labels(
    features: np.ndarray,
    ids: list[str],
    cluster_count: int,
    seed: int,
    n_init: int,
) -> tuple[np.ndarray, np.ndarray]:
    model = KMeans(
        n_clusters=cluster_count,
        n_init=n_init,
        random_state=seed,
        algorithm="lloyd",
    )
    raw = model.fit_predict(features)
    labels = canonical_labels(raw, features, ids)
    centroids = np.asarray(
        [np.mean(features[labels == label], axis=0) for label in range(cluster_count)],
        dtype=np.float64,
    )
    return labels, centroids


def source_concentration(labels: np.ndarray, sources: list[str]) -> dict[str, float]:
    maximum_shares = []
    normalized_entropies = []
    source_count = len(set(sources))
    entropy_denominator = math.log(source_count) if source_count > 1 else 1.0
    for label in sorted(set(int(value) for value in labels)):
        counts = Counter(sources[index] for index in np.flatnonzero(labels == label))
        size = sum(counts.values())
        shares = [count / size for count in counts.values()]
        maximum_shares.append(max(shares))
        entropy = -sum(share * math.log(share) for share in shares)
        normalized_entropies.append(entropy / entropy_denominator)
    return {
        "meanLargestSourceShare": round(float(np.mean(maximum_shares)), 8),
        "maximumLargestSourceShare": round(float(max(maximum_shares)), 8),
        "meanNormalizedSourceEntropy": round(float(np.mean(normalized_entropies)), 8),
    }


def activity_summaries(ids: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    wanted = set(ids)
    for path in sorted((VAULT / "activities").glob("*.md")):
        if path.stem not in wanted:
            continue
        metadata, body = load_markdown(path)
        excerpt = " ".join(body.split())[:360].rstrip()
        result[path.stem] = {
            "activityId": path.stem,
            "title": metadata["title"],
            "sourceId": metadata["sourceId"],
            "year": metadata.get("year"),
            "excerpt": excerpt,
        }
    if set(result) != wanted:
        raise ValueError("Cannot build hierarchy review metadata for the full corpus")
    return result


def sample_cluster(
    label: int,
    labels: np.ndarray,
    features: np.ndarray,
    centroid: np.ndarray,
    ids: list[str],
    config: dict[str, Any],
) -> dict[str, list[str]]:
    members = np.flatnonzero(labels == label)
    outsiders = np.flatnonzero(labels != label)
    member_distances = np.linalg.norm(features[members] - centroid, axis=1)
    outside_distances = np.linalg.norm(features[outsiders] - centroid, axis=1)
    central = sorted(
        zip(member_distances, (ids[index] for index in members), strict=True)
    )[: int(config["representativeCount"])]
    boundary = sorted(
        zip(member_distances, (ids[index] for index in members), strict=True), reverse=True
    )[: int(config["boundaryCount"])]
    outside = sorted(
        zip(outside_distances, (ids[index] for index in outsiders), strict=True)
    )[: int(config["nearestOutsideCount"])]
    return {
        "centralActivityIds": [activity_id for _, activity_id in central],
        "boundaryActivityIds": [activity_id for _, activity_id in boundary],
        "nearestOutsideActivityIds": [activity_id for _, activity_id in outside],
    }


def build_variant(
    *,
    blind_id: str,
    algorithm: str,
    clustering_features: np.ndarray,
    semantic_features: np.ndarray,
    visual_features: np.ndarray,
    ids: list[str],
    sources: list[str],
    pilot: dict[str, Any],
) -> dict[str, Any]:
    fine_count = int(pilot["fineClusterCount"])
    top_count = int(pilot["topClusterCount"])
    seed = int(pilot["randomSeed"])
    n_init = int(pilot["kMeansNInit"])
    fine_labels, fine_centroids = fit_labels(
        clustering_features, ids, fine_count, seed, n_init
    )
    top_ids = [f"fine-{index + 1:02d}" for index in range(fine_count)]
    top_labels, top_centroids = fit_labels(
        fine_centroids, top_ids, top_count, seed, n_init
    )
    sizes = [int(np.sum(fine_labels == label)) for label in range(fine_count)]
    stability = []
    for stability_seed in pilot["stabilitySeeds"]:
        alternate, _ = fit_labels(
            clustering_features,
            ids,
            fine_count,
            int(stability_seed),
            n_init,
        )
        stability.append(
            {
                "seed": int(stability_seed),
                "adjustedRandIndex": round(
                    float(adjusted_rand_score(fine_labels, alternate)), 8
                ),
            }
        )
    clusters = []
    for label in range(fine_count):
        sample = sample_cluster(
            label,
            fine_labels,
            clustering_features,
            fine_centroids[label],
            ids,
            pilot,
        )
        clusters.append(
            {
                "fineClusterId": f"fine-{label + 1:02d}",
                "topClusterId": f"top-{int(top_labels[label]) + 1:02d}",
                "size": sizes[label],
                "sample": sample,
                "status": "proposal-only",
            }
        )
    minimum = min(sizes)
    return {
        "blindVariantId": blind_id,
        "algorithm": algorithm,
        "eligibleForHumanReview": minimum >= int(pilot["minimumFineClusterSize"]),
        "metrics": {
            "semanticSilhouette": round(
                float(silhouette_score(semantic_features, fine_labels, metric="cosine")), 8
            ),
            "visualSilhouette": round(
                float(silhouette_score(visual_features, fine_labels, metric="euclidean")), 8
            ),
            "minimumFineClusterSize": minimum,
            "medianFineClusterSize": round(float(np.median(sizes)), 8),
            "maximumFineClusterSize": max(sizes),
            "stabilityRuns": stability,
            "minimumAdjustedRandIndex": min(
                run["adjustedRandIndex"] for run in stability
            ),
            "sourceConcentration": source_concentration(fine_labels, sources),
        },
        "fineClusters": clusters,
        "topClusters": [
            {
                "topClusterId": f"top-{label + 1:02d}",
                "childFineClusterIds": [
                    f"fine-{index + 1:02d}"
                    for index in range(fine_count)
                    if int(top_labels[index]) == label
                ],
                "centroid": [round(float(value), 8) for value in top_centroids[label]],
                "status": "proposal-only",
            }
            for label in range(top_count)
        ],
        "points": [
            {
                "activityId": activity_id,
                "fineClusterId": f"fine-{int(fine_labels[index]) + 1:02d}",
                "topClusterId": f"top-{int(top_labels[int(fine_labels[index])]) + 1:02d}",
            }
            for index, activity_id in enumerate(ids)
        ],
    }


def review_view(report: dict[str, Any], summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    variants = []
    for variant in report["variants"]:
        clusters = []
        for cluster in variant["fineClusters"]:
            sample = cluster["sample"]
            clusters.append(
                {
                    "fineClusterId": cluster["fineClusterId"],
                    "topClusterId": cluster["topClusterId"],
                    "size": cluster["size"],
                    "central": [summaries[value] for value in sample["centralActivityIds"]],
                    "boundary": [summaries[value] for value in sample["boundaryActivityIds"]],
                    "nearestOutside": [
                        summaries[value] for value in sample["nearestOutsideActivityIds"]
                    ],
                }
            )
        variants.append(
            {
                "blindVariantId": variant["blindVariantId"],
                "eligibleForHumanReview": variant["eligibleForHumanReview"],
                "metrics": variant["metrics"],
                "fineClusters": clusters,
            }
        )
    return {
        "schemaVersion": 1,
        "pipeline": "semantic-map-hierarchy-blind-review-v1",
        "status": "human-review-required",
        "generatedAt": report["generatedAt"],
        "corpusDigest": report["corpus"]["corpusDigest"],
        "selectionRequired": True,
        "expertQuestionsAreNotLabels": True,
        "expertReviewQuestions": [
            "Czy w wariancie wyłaniają się gry leśne?",
            "Czy w wariancie wyłaniają się gry w pomieszczeniu?",
            "Czy w wariancie wyłaniają się duże gry terenowe?",
            "Czy w wariancie wyłaniają się gry i zabawy zuchowe?",
        ],
        "variants": variants,
    }


def review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "---",
        "title: Ślepa recenzja klastrów mapy semantycznej V1",
        "status: human-review-required",
        "sourceType: algorithmic-proposal",
        "---",
        "",
        "# Ślepa recenzja klastrów mapy semantycznej V1",
        "",
        "Wybierz jeden wariant na podstawie spójności grup, nie nazwy algorytmu. "
        "Pełne próbki znajdują się w `data/reports/semantic-map-hierarchy-review-v1.json`.",
        "",
    ]
    for variant in review["variants"]:
        metrics = variant["metrics"]
        lines.extend(
            [
                f"## {variant['blindVariantId']}",
                "",
                f"- kwalifikuje się do recenzji: `{str(variant['eligibleForHumanReview']).lower()}`",
                f"- semantic silhouette: `{metrics['semanticSilhouette']}`",
                f"- visual silhouette: `{metrics['visualSilhouette']}`",
                f"- najmniejszy klaster: `{metrics['minimumFineClusterSize']}`",
                f"- minimalne ARI: `{metrics['minimumAdjustedRandIndex']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Decyzja właściciela",
            "",
            "- [ ] wybieram `candidate-amber`",
            "- [ ] wybieram `candidate-blue`",
            "- [ ] odrzucam oba warianty",
            "",
            "Ta decyzja zatwierdza wyłącznie wariant geometrii do dalszego nazywania. "
            "Nie zatwierdza nazw, filtrów ani klasyfikacji historycznej.",
            "",
        ]
    )
    return "\n".join(lines)


def build_reports(generated_at: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    config = load_config()
    pilot = config.get("hierarchicPilot") or {}
    required = {
        "schemaVersion", "algorithmVersion", "fineClusterCount", "topClusterCount",
        "minimumFineClusterSize", "kMeansNInit", "randomSeed", "stabilitySeeds",
        "representativeCount", "boundaryCount", "nearestOutsideCount",
        "reviewPacketVersion", "status",
    }
    if required - set(pilot) or pilot["status"] != "proposed":
        raise ValueError("Hierarchic-map pilot configuration is incomplete")
    items = activity_items(config)
    caches = load_current_caches(config, items)
    base = read_json(BASE_REPORT_PATH)
    if base.get("status") != "proposal-only":
        raise ValueError("Base semantic-map analysis is not an approved pilot input")
    if base["corpus"]["corpusDigest"] != corpus_digest(items):
        raise ValueError("Base semantic-map corpus digest is stale")
    ids = [str(payload["activityId"]) for payload in caches]
    sources = [str(payload["sourceId"]) for payload in caches]
    vectors = normalized(np.asarray([payload["vector"] for payload in caches], dtype=np.float64))
    coordinate_by_id = {
        point["activityId"]: [point["x"], point["y"]] for point in base["points"]
    }
    coordinates = np.asarray([coordinate_by_id[activity_id] for activity_id in ids], dtype=np.float64)
    variants = [
        build_variant(
            blind_id="candidate-amber",
            algorithm="kmeans-on-umap-2d",
            clustering_features=coordinates,
            semantic_features=vectors,
            visual_features=coordinates,
            ids=ids,
            sources=sources,
            pilot=pilot,
        ),
        build_variant(
            blind_id="candidate-blue",
            algorithm="kmeans-on-normalized-embeddings",
            clustering_features=vectors,
            semantic_features=vectors,
            visual_features=coordinates,
            ids=ids,
            sources=sources,
            pilot=pilot,
        ),
    ]
    report = {
        "schemaVersion": 1,
        "pipeline": "semantic-map-hierarchy-pilot-v1",
        "status": "human-review-required",
        "generatedAt": generated_at,
        "proposalOnly": True,
        "projectionIsNavigationalOnly": True,
        "selection": None,
        "publicationBlocked": not any(item["eligibleForHumanReview"] for item in variants),
        "corpus": {
            "activities": len(ids),
            "corpusDigest": corpus_digest(items),
            "baseAnalysisDigest": canonical_hash(base),
        },
        "implementation": {
            "algorithmVersion": pilot["algorithmVersion"],
            "numpy": np.__version__,
            "scikitLearn": sklearn.__version__,
            "threads": 1,
        },
        "parameters": {key: pilot[key] for key in sorted(required)},
        "variants": variants,
    }
    review = review_view(report, activity_summaries(ids))
    return report, review, review_markdown(review)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        if not REPORT_PATH.is_file() or not REVIEW_JSON_PATH.is_file() or not REVIEW_MD_PATH.is_file():
            raise SystemExit("Hierarchic-map pilot report or review packet is missing")
        actual = read_json(REPORT_PATH)
        expected_report, expected_review, expected_markdown = build_reports(str(actual["generatedAt"]))
        if actual != expected_report or read_json(REVIEW_JSON_PATH) != expected_review:
            raise SystemExit("Hierarchic-map pilot reports are stale")
        if REVIEW_MD_PATH.read_text(encoding="utf-8") != expected_markdown:
            raise SystemExit("Hierarchic-map pilot review note is stale")
        print(f"Hierarchic-map pilot is current: {actual['corpus']['activities']} activities")
        return
    report, review, markdown = build_reports(datetime.now(UTC).isoformat())
    write_json(REPORT_PATH, report)
    write_json(REVIEW_JSON_PATH, review)
    REVIEW_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_MD_PATH.write_text(markdown, encoding="utf-8")
    print(json.dumps({
        "report": str(REPORT_PATH),
        "review": str(REVIEW_JSON_PATH),
        "publicationBlocked": report["publicationBlocked"],
        "variants": [
            {"id": item["blindVariantId"], **item["metrics"]} for item in report["variants"]
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
