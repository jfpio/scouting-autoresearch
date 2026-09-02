#!/usr/bin/env python3
"""Create a deterministic, proposal-only analysis of cached V1 embeddings."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path
from typing import Any

from common import ROOT, read_json
from embed_taxonomy import (
    BATCH_DIR,
    CACHE_DIR,
    CHECKPOINT_PATH,
    activity_items,
    atomic_write_json,
    cache_is_current,
    load_config,
    summarize_batch_usage,
)


REPORT_PATH = ROOT / "data" / "reports" / "taxonomy-v1-analysis.json"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vectors must have equal dimensions")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("Zero vectors cannot be compared")
    return dot / (left_norm * right_norm)


def pair_key(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left < right else (right, left)


def pairwise_similarities(vectors: dict[str, list[float]]) -> dict[tuple[str, str], float]:
    return {
        (left, right): cosine_similarity(vectors[left], vectors[right])
        for left, right in combinations(sorted(vectors), 2)
    }


def agglomerative_clusters(
    activity_ids: list[str], similarities: dict[tuple[str, str], float], target_count: int
) -> list[tuple[str, ...]]:
    if not activity_ids:
        return []
    if target_count < 1 or target_count > len(activity_ids):
        raise ValueError("target_count must be between 1 and the number of activities")

    ordered_ids = sorted(activity_ids)
    clusters: dict[int, tuple[str, ...]] = {
        index: (activity_id,) for index, activity_id in enumerate(ordered_ids)
    }
    sizes = {index: 1 for index in clusters}
    cluster_similarities: dict[tuple[int, int], float] = {}
    for left, right in combinations(clusters, 2):
        cluster_similarities[(left, right)] = similarities[(clusters[left][0], clusters[right][0])]

    next_cluster_id = len(clusters)
    while len(clusters) > target_count:
        best_pair: tuple[int, int] | None = None
        best_similarity = -math.inf
        best_members: tuple[tuple[str, ...], tuple[str, ...]] | None = None
        for left, right in combinations(sorted(clusters), 2):
            similarity = cluster_similarities[pair_key(left, right)]
            members = tuple(sorted((clusters[left], clusters[right])))
            if similarity > best_similarity or (
                math.isclose(similarity, best_similarity, abs_tol=1e-15)
                and (best_members is None or members < best_members)
            ):
                best_pair = (left, right)
                best_similarity = similarity
                best_members = members
        if best_pair is None:
            raise RuntimeError("Could not select clusters to merge")

        left, right = best_pair
        left_size = sizes[left]
        right_size = sizes[right]
        others = [cluster_id for cluster_id in clusters if cluster_id not in best_pair]
        new_similarities = {
            other: (
                left_size * cluster_similarities[pair_key(left, other)]
                + right_size * cluster_similarities[pair_key(right, other)]
            )
            / (left_size + right_size)
            for other in others
        }
        for key in [key for key in cluster_similarities if left in key or right in key]:
            del cluster_similarities[key]
        members = tuple(sorted(clusters.pop(left) + clusters.pop(right)))
        del sizes[left]
        del sizes[right]
        clusters[next_cluster_id] = members
        sizes[next_cluster_id] = left_size + right_size
        for other, similarity in new_similarities.items():
            cluster_similarities[pair_key(next_cluster_id, other)] = similarity
        next_cluster_id += 1

    return sorted(clusters.values())


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a quantile of an empty list")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def centroid(member_ids: tuple[str, ...], vectors: dict[str, list[float]]) -> list[float]:
    dimensions = len(vectors[member_ids[0]])
    return [
        sum(vectors[activity_id][index] for activity_id in member_ids) / len(member_ids)
        for index in range(dimensions)
    ]


def vector_hash(vector: list[float]) -> str:
    serialized = json.dumps(vector, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_analysis(
    caches: list[dict[str, Any]], *, all_activity_ids: list[str], parameters: dict[str, Any], usage: dict[str, Any]
) -> dict[str, Any]:
    if len(caches) < 2:
        raise ValueError("At least two current embedding caches are required")
    caches = sorted(caches, key=lambda payload: payload["activityId"])
    activity_ids = [payload["activityId"] for payload in caches]
    if len(activity_ids) != len(set(activity_ids)):
        raise ValueError("Embedding cache contains duplicate activity IDs")
    metadata_keys = ("modelRequested", "model", "dimensions", "recipeVersion")
    for key in metadata_keys:
        values = {json.dumps(payload.get(key), sort_keys=True) for payload in caches}
        if len(values) != 1:
            raise ValueError(f"Embedding caches disagree on {key}")

    vectors = {payload["activityId"]: payload["vector"] for payload in caches}
    similarities = pairwise_similarities(vectors)
    neighbor_count = min(int(parameters["nearestNeighborCount"]), len(caches) - 1)
    nearest_neighbors: list[dict[str, Any]] = []
    connectivity: dict[str, float] = {}
    for activity_id in activity_ids:
        neighbors = []
        for other_id in activity_ids:
            if other_id == activity_id:
                continue
            key = tuple(sorted((activity_id, other_id)))
            neighbors.append((other_id, similarities[key]))
        neighbors.sort(key=lambda item: (-item[1], item[0]))
        selected = neighbors[:neighbor_count]
        connectivity[activity_id] = sum(similarity for _, similarity in selected) / len(selected)
        nearest_neighbors.append(
            {
                "activityId": activity_id,
                "neighbors": [
                    {"activityId": other_id, "cosineSimilarity": round(similarity, 8)}
                    for other_id, similarity in selected
                ],
            }
        )

    target_count = min(int(parameters["targetClusterCount"]), len(caches))
    cluster_members = agglomerative_clusters(activity_ids, similarities, target_count)
    cluster_ids = {members: f"technical-cluster-{index:02d}" for index, members in enumerate(cluster_members, 1)}
    membership = {activity_id: cluster_ids[members] for members in cluster_members for activity_id in members}
    members_by_activity = {activity_id: members for members in cluster_members for activity_id in members}
    centroids = {cluster_ids[members]: centroid(members, vectors) for members in cluster_members}

    ambiguity_margin = float(parameters["ambiguityMargin"])
    ambiguous_assignments = []
    for activity_id in activity_ids:
        chosen = membership[activity_id]
        alternatives = sorted(
            (
                (cluster_id, cosine_similarity(vectors[activity_id], cluster_centroid))
                for cluster_id, cluster_centroid in centroids.items()
                if cluster_id != chosen
            ),
            key=lambda item: (-item[1], item[0]),
        )
        alternative_id, alternative_score = alternatives[0] if alternatives else (None, -1.0)
        chosen_members = tuple(member for member in members_by_activity[activity_id] if member != activity_id)
        if not chosen_members:
            ambiguous_assignments.append(
                {
                    "activityId": activity_id,
                    "technicalClusterId": chosen,
                    "alternativeTechnicalClusterId": alternative_id,
                    "reason": "singleton-cluster",
                    "margin": None,
                    "clusterSimilarity": None,
                    "alternativeSimilarity": round(alternative_score, 8),
                }
            )
            continue
        chosen_score = cosine_similarity(vectors[activity_id], centroid(chosen_members, vectors))
        margin = chosen_score - alternative_score
        if margin < ambiguity_margin:
            ambiguous_assignments.append(
                {
                    "activityId": activity_id,
                    "technicalClusterId": chosen,
                    "alternativeTechnicalClusterId": alternative_id,
                    "reason": "low-leave-one-out-margin",
                    "margin": round(margin, 8),
                    "clusterSimilarity": round(chosen_score, 8),
                    "alternativeSimilarity": round(alternative_score, 8),
                }
            )

    connectivity_values = list(connectivity.values())
    first_quartile = quantile(connectivity_values, 0.25)
    third_quartile = quantile(connectivity_values, 0.75)
    outlier_threshold = first_quartile - float(parameters["outlierIqrMultiplier"]) * (
        third_quartile - first_quartile
    )
    outlier_ids = sorted(activity_id for activity_id, score in connectivity.items() if score < outlier_threshold)
    inspection_count = max(1, math.ceil(len(caches) * 0.05))
    lowest_connectivity = sorted(connectivity.items(), key=lambda item: (item[1], item[0]))[:inspection_count]

    all_ids = sorted(all_activity_ids)
    missing_ids = sorted(set(all_ids) - set(activity_ids))
    cache_fingerprint = [
        {
            "activityId": payload["activityId"],
            "inputHash": payload["inputHash"],
            "vectorHash": vector_hash(payload["vector"]),
        }
        for payload in caches
    ]
    analysis_hash = hashlib.sha256(
        json.dumps(
            {"caches": cache_fingerprint, "parameters": parameters},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    generated_at = max(str(payload["generatedAt"]) for payload in caches)

    return {
        "schemaVersion": 1,
        "pipeline": "taxonomy-v1-analysis",
        "status": "complete-input" if not missing_ids else "partial",
        "proposalOnly": True,
        "reviewRequired": True,
        "productionTaxonomyChanged": False,
        "generatedAt": generated_at,
        "analysisHash": analysis_hash,
        "algorithmVersion": parameters["algorithmVersion"],
        "coverage": {
            "totalActivities": len(all_ids),
            "embeddedActivities": len(activity_ids),
            "missingActivities": len(missing_ids),
            "missingActivityIds": missing_ids,
            "sourceIds": sorted({payload["sourceId"] for payload in caches}),
        },
        "embedding": {key: caches[0][key] for key in metadata_keys},
        "parameters": parameters,
        "usage": usage,
        "clusters": [
            {"technicalClusterId": cluster_ids[members], "size": len(members), "activityIds": list(members)}
            for members in cluster_members
        ],
        "items": [
            {
                "activityId": payload["activityId"],
                "sourceId": payload["sourceId"],
                "sourceTraits": payload.get("sourceTraits", []),
                "technicalClusterId": membership[payload["activityId"]],
                "neighborConnectivity": round(connectivity[payload["activityId"]], 8),
            }
            for payload in caches
        ],
        "nearestNeighbors": nearest_neighbors,
        "outliers": {
            "method": "mean-neighbor-similarity-below-q1-minus-iqr-multiplier",
            "threshold": round(outlier_threshold, 8),
            "activityIds": outlier_ids,
            "lowestConnectivityForInspection": [
                {"activityId": activity_id, "score": round(score, 8)} for activity_id, score in lowest_connectivity
            ],
        },
        "ambiguousAssignments": ambiguous_assignments,
        "unassignedProductionCategoryActivityIds": activity_ids,
    }


def load_usage() -> dict[str, Any]:
    batches = [read_json(path) for path in sorted(BATCH_DIR.glob("*.json"))]
    config = load_config()["embedding"]
    usage = summarize_batch_usage(batches, float(config["priceUsdPerMillionInputTokens"]))
    usage.update(
        {
            "batchIds": sorted(str(batch["batchId"]) for batch in batches),
            "priceUsdPerMillionInputTokens": config["priceUsdPerMillionInputTokens"],
            "priceSource": config["priceSource"],
        }
    )
    return usage


def write_analysis_checkpoint(
    report: dict[str, Any], path: Path = CHECKPOINT_PATH, report_path: Path = REPORT_PATH
) -> None:
    checkpoint = read_json(path) if path.exists() else {}
    checkpoint.update({"schemaVersion": 1, "pipeline": "taxonomy-v1-embeddings"})
    checkpoint["analysis"] = {
        "status": report["status"],
        "analysisHash": report["analysisHash"],
        "algorithmVersion": report["algorithmVersion"],
        "generatedAt": report["generatedAt"],
        "embeddedActivities": report["coverage"]["embeddedActivities"],
        "totalActivities": report["coverage"]["totalActivities"],
        "reportPath": (
            str(report_path.relative_to(ROOT)) if report_path.is_relative_to(ROOT) else str(report_path)
        ),
    }
    atomic_write_json(path, checkpoint)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true", help="Refuse to write a partial-corpus analysis")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    config = load_config()
    parameters = config.get("analysis")
    if not isinstance(parameters, dict):
        raise SystemExit("taxonomy-v1.yaml lacks analysis configuration")
    required_parameters = {
        "algorithmVersion",
        "targetClusterCount",
        "nearestNeighborCount",
        "ambiguityMargin",
        "outlierIqrMultiplier",
    }
    missing_parameters = required_parameters - set(parameters)
    if missing_parameters:
        raise SystemExit(f"taxonomy analysis configuration lacks: {sorted(missing_parameters)}")
    items = activity_items(config)
    expected_by_id = {item["id"]: item for item in items}
    caches = []
    embedding = config["embedding"]
    for path in sorted(CACHE_DIR.glob("*.json")):
        payload = read_json(path)
        expected = expected_by_id.get(payload.get("activityId"))
        if not expected:
            raise SystemExit(f"embedding cache has no matching activity: {path}")
        if not cache_is_current(
            path,
            activity_id=expected["id"],
            model=embedding["model"],
            recipe_version=embedding["recipeVersion"],
            expected_hash=expected["inputHash"],
            dimensions=int(embedding["dimensions"]),
        ):
            raise SystemExit(f"embedding cache is stale or invalid: {path}")
        caches.append(payload)
    activity_ids = [item["id"] for item in items]
    report = build_analysis(caches, all_activity_ids=activity_ids, parameters=parameters, usage=load_usage())
    if args.require_complete and report["status"] != "complete-input":
        raise SystemExit(
            f"analysis input is incomplete: {report['coverage']['embeddedActivities']}/{report['coverage']['totalActivities']}"
        )
    atomic_write_json(args.output, report)
    write_analysis_checkpoint(report, report_path=args.output)
    print(
        json.dumps(
            {
                "status": report["status"],
                "analysisHash": report["analysisHash"],
                "coverage": report["coverage"],
                "clusters": len(report["clusters"]),
                "outliers": len(report["outliers"]["activityIds"]),
                "ambiguousAssignments": len(report["ambiguousAssignments"]),
                "output": str(args.output),
                "checkpoint": str(CHECKPOINT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
