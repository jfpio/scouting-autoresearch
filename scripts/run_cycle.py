#!/usr/bin/env python3
"""Materialize one bounded V2 proposal cycle for Codex.

The current scaffold has no network collection adapters. It validates configuration,
materializes a review packet for the queued authors, and records the latest checkpoint. It does
not orchestrate Codex or resume incomplete network work. Later adapters must keep the same human
rights-review and pull-request gates.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

from common import ROOT, write_json


STATE_PATH = ROOT / "data" / "checkpoints" / "cycle-state.json"
REPORT_DIR = ROOT / "data" / "reports"


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Configuration must be an object: {path}")
    return value


def git_branch() -> str:
    return subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()


def main() -> None:
    queue = load_yaml(ROOT / "config" / "research-queue.yaml")
    registry = load_yaml(ROOT / "config" / "source-registry.yaml")
    defaults = queue["dailyLimits"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-documents", type=int, default=int(os.environ.get("AUTORESEARCH_MAX_DOCUMENTS", defaults["documents"])))
    parser.add_argument("--max-cost-usd", type=float, default=float(os.environ.get("AUTORESEARCH_MAX_COST_USD", defaults["estimatedCostUsd"])))
    parser.add_argument("--propose-only", action="store_true", default=True)
    args = parser.parse_args()
    if args.max_documents < 1 or args.max_documents > defaults["documents"]:
        raise SystemExit(f"max-documents must be between 1 and {defaults['documents']}")
    if args.max_cost_usd <= 0 or args.max_cost_usd > defaults["estimatedCostUsd"]:
        raise SystemExit(f"max-cost-usd must be between 0 and {defaults['estimatedCostUsd']}")
    branch = git_branch()
    if branch in {"main", "master"}:
        raise SystemExit("Refusing to run an autoresearch cycle directly on the default branch")

    now = datetime.now(UTC)
    cycle_id = now.strftime("%Y%m%dT%H%M%SZ")
    candidates = []
    for subject in queue.get("subjects", [])[: args.max_documents]:
        candidates.append(
            {
                "subjectId": subject["id"],
                "author": subject["name"],
                "status": "discovery-pending",
                "rightsStatus": "rights-review",
                "fullTextEligible": False,
                "nextAction": "Find concrete editions in registered collections and submit evidence for human review.",
            }
        )
    report = {
        "schemaVersion": 1,
        "cycleId": cycle_id,
        "createdAt": now.isoformat(),
        "mode": "propose-only",
        "branch": branch,
        "limits": {"documents": args.max_documents, "estimatedCostUsd": args.max_cost_usd},
        "estimatedCostUsd": 0,
        "documentsFetched": 0,
        "collectionAdaptersEnabled": [],
        "registeredCollections": [item["id"] for item in registry.get("collections", [])],
        "candidates": candidates,
        "publicationBlocked": True,
        "blockReason": "V0 has no approved foreign collection adapter; candidates require human rights review.",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"cycle-{cycle_id}.json"
    write_json(report_path, report)
    write_json(
        STATE_PATH,
        {"schemaVersion": 1, "lastCycleId": cycle_id, "lastCompletedAt": now.isoformat(), "report": str(report_path.relative_to(ROOT))},
    )
    print(json.dumps({"cycleId": cycle_id, "status": "proposal-ready", "candidates": len(candidates), "report": str(report_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
