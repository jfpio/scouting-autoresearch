#!/usr/bin/env python3
"""Build deterministic V3 neighbours, UMAP coordinates, and review candidates."""

from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

for variable in (
    "NUMBA_NUM_THREADS",
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
):
    os.environ.setdefault(variable, "1")

import numpy as np
import scipy
import sklearn
import umap
import yaml
from scipy.spatial.distance import pdist
from scipy.stats import spearmanr
from sklearn.manifold import trustworthiness

from common import ROOT, read_json, write_json
from embed_semantic_map import (
    CACHE_DIR,
    REPORT_PATH as EMBEDDING_REPORT_PATH,
    activity_items,
    cache_is_current,
    canonical_hash,
    corpus_digest,
    load_config,
)


REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-v3-analysis.json"
RELATIONS_PATH = ROOT / "config" / "similar-activities.yaml"


def portable_report_view(report: dict[str, Any]) -> dict[str, Any]:
    """Remove only UMAP outputs that can vary across CPU implementations.

    Cosine neighbours, review candidates, corpus hashes, source hashes, and the
    semantic part of approved overlays remain covered by exact comparison.
    """

    result = copy.deepcopy(report)
    for point in result.get("points", []):
        point.pop("x", None)
        point.pop("y", None)
    for overlay in result.get("approvedRelationOverlays", []):
        overlay.pop("projectedDistance", None)
    quality = result.get("quality", {})
    for key in (
        "trustworthinessAtK",
        "stabilityRuns",
        "minimumSpearmanPairwiseDistanceCorrelation",
        "minimumMeanNeighborRetentionAtK",
    ):
        quality.pop(key, None)
    return result


def load_current_caches(
    config: dict[str, Any], items: list[dict[str, Any]], cache_dir: Path = CACHE_DIR
) -> list[dict[str, Any]]:
    expected = {item["id"]: item for item in items}
    paths = sorted(cache_dir.glob("*.json"))
    payloads = [read_json(path) for path in paths]
    payload_ids = [payload.get("activityId") for payload in payloads]
    if len(payload_ids) != len(set(payload_ids)):
        raise ValueError("Semantic-map V3 cache repeats activity IDs")
    if set(payload_ids) != set(expected):
        missing = sorted(set(expected) - set(payload_ids))
        extra = sorted(set(payload_ids) - set(expected))
        raise ValueError(
            f"Semantic-map V3 analysis requires complete coverage; missing={missing}, extra={extra}"
        )
    for path, payload in zip(paths, payloads, strict=True):
        activity_id = str(payload["activityId"])
        if path.stem != activity_id or not cache_is_current(
            path, expected[activity_id], config["embedding"]
        ):
            raise ValueError(f"Semantic-map V3 cache is stale or invalid: {path}")
    return sorted(payloads, key=lambda payload: payload["activityId"])


def cosine_similarities(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms == 0):
        raise ValueError("Semantic-map V3 contains a zero vector")
    normalized = vectors / norms[:, np.newaxis]
    similarities = normalized @ normalized.T
    return np.clip(similarities, -1.0, 1.0)


def nearest_neighbors(
    activity_ids: list[str], similarities: np.ndarray, count: int
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    if similarities.shape != (len(activity_ids), len(activity_ids)):
        raise ValueError("Similarity matrix does not match activity IDs")
    if not 1 <= count < len(activity_ids):
        raise ValueError("Nearest-neighbour count is outside the corpus")
    records: list[dict[str, Any]] = []
    ranks: dict[str, dict[str, int]] = {}
    for index, activity_id in enumerate(activity_ids):
        ordered = sorted(
            (other for other in range(len(activity_ids)) if other != index),
            key=lambda other: (-float(similarities[index, other]), activity_ids[other]),
        )
        ranks[activity_id] = {
            activity_ids[other]: rank for rank, other in enumerate(ordered, start=1)
        }
        records.append(
            {
                "activityId": activity_id,
                "neighbors": [
                    {
                        "activityId": activity_ids[other],
                        "cosineSimilarity": round(float(similarities[index, other]), 8),
                    }
                    for other in ordered[:count]
                ],
            }
        )
    return records, ranks


def projected_neighbor_sets(coordinates: np.ndarray, count: int) -> list[set[int]]:
    differences = coordinates[:, np.newaxis, :] - coordinates[np.newaxis, :, :]
    distances = np.linalg.norm(differences, axis=2)
    return [
        set(
            sorted(
                (other for other in range(len(coordinates)) if other != index),
                key=lambda other: (float(distances[index, other]), other),
            )[:count]
        )
        for index in range(len(coordinates))
    ]


def mean_neighbor_retention(
    reference: np.ndarray, candidate: np.ndarray, count: int
) -> float:
    reference_sets = projected_neighbor_sets(reference, count)
    candidate_sets = projected_neighbor_sets(candidate, count)
    return float(
        np.mean(
            [len(left & right) / count for left, right in zip(reference_sets, candidate_sets)]
        )
    )


def project(vectors: np.ndarray, analysis: dict[str, Any], seed: int) -> np.ndarray:
    reducer = umap.UMAP(
        n_components=int(analysis["projectionDimensions"]),
        n_neighbors=int(analysis["projectionNeighbors"]),
        min_dist=float(analysis["projectionMinDistance"]),
        spread=float(analysis["projectionSpread"]),
        metric=str(analysis["distanceMetric"]),
        random_state=seed,
        n_jobs=1,
        low_memory=True,
    )
    return np.asarray(reducer.fit_transform(vectors), dtype=np.float64)


def approved_relations() -> list[dict[str, Any]]:
    config = yaml.safe_load(RELATIONS_PATH.read_text(encoding="utf-8")) or {}
    relations = []
    for relation in config.get("relations") or []:
        if relation.get("status") != "human-approved":
            raise ValueError(f"Non-approved relation in production registry: {relation.get('id')}")
        activity_ids = relation.get("activityIds") or []
        if len(activity_ids) != 2 or len(set(activity_ids)) != 2:
            raise ValueError(f"Invalid similar-game relation: {relation.get('id')}")
        relations.append(relation)
    return sorted(relations, key=lambda relation: relation["id"])


def relation_overlays(
    relations: list[dict[str, Any]],
    activity_ids: list[str],
    similarities: np.ndarray,
    ranks: dict[str, dict[str, int]],
    coordinates: np.ndarray,
) -> list[dict[str, Any]]:
    positions = {activity_id: index for index, activity_id in enumerate(activity_ids)}
    overlays = []
    for relation in relations:
        left, right = relation["activityIds"]
        if left not in positions or right not in positions:
            raise ValueError(f"Approved relation is outside the V3 game corpus: {relation['id']}")
        left_index = positions[left]
        right_index = positions[right]
        overlays.append(
            {
                "relationId": relation["id"],
                "relationType": relation["relationType"],
                "status": "human-approved",
                "activityIds": [left, right],
                "cosineSimilarity": round(
                    float(similarities[left_index, right_index]), 8
                ),
                "neighborRanks": {
                    left: ranks[left][right],
                    right: ranks[right][left],
                },
                "projectedDistance": round(
                    float(np.linalg.norm(coordinates[left_index] - coordinates[right_index])),
                    8,
                ),
            }
        )
    return overlays


def algorithmic_candidates(
    neighbor_records: list[dict[str, Any]],
    source_by_id: dict[str, str],
    approved_pairs: set[frozenset[str]],
    limit: int,
) -> list[dict[str, Any]]:
    neighbor_lookup = {
        record["activityId"]: {
            item["activityId"]: item["cosineSimilarity"] for item in record["neighbors"]
        }
        for record in neighbor_records
    }
    candidates = []
    for left in sorted(neighbor_lookup):
        for right, similarity in neighbor_lookup[left].items():
            if left >= right or left not in neighbor_lookup.get(right, {}):
                continue
            pair = frozenset((left, right))
            if source_by_id[left] == source_by_id[right] or pair in approved_pairs:
                continue
            candidates.append(
                {
                    "activityIds": [left, right],
                    "sourceIds": [source_by_id[left], source_by_id[right]],
                    "cosineSimilarity": similarity,
                    "status": "algorithmic-candidate",
                    "reviewRequired": True,
                    "productionRelation": False,
                }
            )
    candidates.sort(key=lambda item: (-item["cosineSimilarity"], item["activityIds"]))
    return candidates[:limit]


def build_report(
    config: dict[str, Any],
    items: list[dict[str, Any]],
    caches: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    analysis = config["analysis"]
    required = {
        "algorithmVersion",
        "nearestNeighborCount",
        "candidatePairLimit",
        "distanceMetric",
        "projectionAlgorithm",
        "projectionLibrary",
        "projectionVersion",
        "projectionDimensions",
        "projectionNeighbors",
        "projectionMinDistance",
        "projectionSpread",
        "randomSeed",
        "stabilitySeeds",
        "stabilityNeighborCount",
    }
    if required - set(analysis):
        raise ValueError("Semantic-map V3 analysis configuration is incomplete")
    if (
        analysis["projectionAlgorithm"] != "umap"
        or analysis["projectionLibrary"] != "umap-learn"
        or str(analysis["projectionVersion"]) != umap.__version__
        or analysis["distanceMetric"] != "cosine"
        or int(analysis["projectionDimensions"]) != 2
    ):
        raise ValueError("Semantic-map V3 projection implementation is not pinned")

    caches = sorted(caches, key=lambda payload: payload["activityId"])
    activity_ids = [str(payload["activityId"]) for payload in caches]
    source_by_id = {str(payload["activityId"]): str(payload["sourceId"]) for payload in caches}
    item_by_id = {str(item["id"]): item for item in items}
    vectors = np.asarray([payload["vector"] for payload in caches], dtype=np.float64)
    similarities = cosine_similarities(vectors)
    neighbor_count = int(analysis["nearestNeighborCount"])
    neighbor_records, ranks = nearest_neighbors(activity_ids, similarities, neighbor_count)

    primary = project(vectors, analysis, int(analysis["randomSeed"]))
    stability_count = int(analysis["stabilityNeighborCount"])
    stability_runs = []
    for seed in analysis["stabilitySeeds"]:
        alternative = project(vectors, analysis, int(seed))
        correlation = spearmanr(pdist(primary), pdist(alternative)).statistic
        stability_runs.append(
            {
                "seed": int(seed),
                "spearmanPairwiseDistanceCorrelation": round(float(correlation), 8),
                "meanNeighborRetentionAtK": round(
                    mean_neighbor_retention(primary, alternative, stability_count), 8
                ),
            }
        )

    relation_records = approved_relations()
    overlays = relation_overlays(
        relation_records, activity_ids, similarities, ranks, primary
    )
    approved_pairs = {
        frozenset(relation["activityIds"]) for relation in relation_records
    }
    candidates = algorithmic_candidates(
        neighbor_records,
        source_by_id,
        approved_pairs,
        int(analysis["candidatePairLimit"]),
    )
    directed_neighbors = [
        (record["activityId"], neighbor["activityId"])
        for record in neighbor_records
        for neighbor in record["neighbors"]
    ]
    cross_source = sum(
        source_by_id[left] != source_by_id[right] for left, right in directed_neighbors
    )
    top_similarities = [
        neighbor["cosineSimilarity"]
        for record in neighbor_records
        for neighbor in record["neighbors"]
    ]
    points = [
        {
            "activityId": activity_id,
            "sourceId": source_by_id[activity_id],
            "sourceHash": item_by_id[activity_id]["sourceHash"],
            "inputHash": item_by_id[activity_id]["inputHash"],
            "x": round(float(primary[index, 0]), 8),
            "y": round(float(primary[index, 1]), 8),
        }
        for index, activity_id in enumerate(activity_ids)
    ]
    embedding_report = read_json(EMBEDDING_REPORT_PATH)
    if embedding_report.get("status") != "complete":
        raise ValueError("Semantic-map V3 embedding report is not complete")

    return {
        "schemaVersion": 1,
        "pipeline": "semantic-map-v3-analysis",
        "status": "proposal-only",
        "generatedAt": generated_at,
        "proposalOnly": True,
        "reviewRequired": True,
        "projectionIsNavigationalOnly": True,
        "productionRelationsWritten": [],
        "corpus": {
            "kind": config["corpus"]["kind"],
            "activities": len(activity_ids),
            "sourceIds": config["corpus"]["sourceOrder"],
            "corpusDigest": corpus_digest(items),
            "embeddingProgressDigest": canonical_hash(embedding_report),
        },
        "embedding": {
            "modelRequested": config["embedding"]["model"],
            "dimensions": config["embedding"]["dimensions"],
            "recipeVersion": config["embedding"]["recipeVersion"],
        },
        "implementation": {
            "algorithmVersion": analysis["algorithmVersion"],
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikitLearn": sklearn.__version__,
            "umapLearn": umap.__version__,
            "threads": 1,
        },
        "parameters": {
            key: analysis[key]
            for key in (
                "nearestNeighborCount",
                "candidatePairLimit",
                "distanceMetric",
                "projectionAlgorithm",
                "projectionLibrary",
                "projectionVersion",
                "projectionDimensions",
                "projectionNeighbors",
                "projectionMinDistance",
                "projectionSpread",
                "randomSeed",
                "stabilitySeeds",
                "stabilityNeighborCount",
            )
        },
        "quality": {
            "trustworthinessAtK": round(
                float(
                    trustworthiness(
                        vectors,
                        primary,
                        n_neighbors=stability_count,
                        metric=str(analysis["distanceMetric"]),
                    )
                ),
                8,
            ),
            "crossSourceDirectedNeighborRate": round(
                cross_source / len(directed_neighbors), 8
            ),
            "nearestNeighborSimilarity": {
                "minimum": round(min(top_similarities), 8),
                "mean": round(float(np.mean(top_similarities)), 8),
                "maximum": round(max(top_similarities), 8),
            },
            "stabilityRuns": stability_runs,
            "minimumSpearmanPairwiseDistanceCorrelation": min(
                run["spearmanPairwiseDistanceCorrelation"] for run in stability_runs
            ),
            "minimumMeanNeighborRetentionAtK": min(
                run["meanNeighborRetentionAtK"] for run in stability_runs
            ),
        },
        "points": points,
        "nearestNeighbors": neighbor_records,
        "approvedRelationOverlays": overlays,
        "algorithmicCandidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--portable",
        action="store_true",
        help=(
            "with --check, compare all deterministic semantic outputs exactly but "
            "exclude UMAP coordinates and projection-only quality metrics"
        ),
    )
    args = parser.parse_args()
    if args.portable and not args.check:
        parser.error("--portable requires --check")
    config = load_config()
    items = activity_items(config)
    caches = load_current_caches(config, items)
    if args.check:
        if not REPORT_PATH.is_file():
            raise SystemExit("Semantic-map V3 analysis report is missing")
        actual = read_json(REPORT_PATH)
        expected = build_report(
            config,
            items,
            caches,
            generated_at=str(actual.get("generatedAt")),
        )
        comparable_actual = portable_report_view(actual) if args.portable else actual
        comparable_expected = portable_report_view(expected) if args.portable else expected
        if comparable_actual != comparable_expected:
            raise SystemExit("Semantic-map V3 analysis report is stale")
        print(
            f"Semantic-map V3 analysis is current"
            f"{' (portable check)' if args.portable else ''}: "
            f"{len(expected['points'])} points, "
            f"{len(expected['algorithmicCandidates'])} review candidates."
        )
        return
    report = build_report(
        config,
        items,
        caches,
        generated_at=datetime.now(UTC).isoformat(),
    )
    write_json(REPORT_PATH, report)
    print(
        json.dumps(
            {
                "report": str(REPORT_PATH),
                "activities": len(report["points"]),
                "candidates": len(report["algorithmicCandidates"]),
                "approvedRelations": len(report["approvedRelationOverlays"]),
                "quality": report["quality"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
