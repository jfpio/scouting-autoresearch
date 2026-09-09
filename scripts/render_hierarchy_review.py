#!/usr/bin/env python3
"""Render the lightweight Markdown view of the hierarchy review packet."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REVIEW_JSON_PATH = ROOT / "data" / "reports" / "semantic-map-hierarchy-review-v1.json"
REVIEW_MD_PATH = ROOT / "vault" / "reviews" / "inbox" / "semantic-map-hierarchy-review-v1.md"


def review_markdown(review: dict[str, Any]) -> str:
    def sample_titles(items: list[dict[str, Any]]) -> str:
        return "<br>".join(
            f"`{item['activityId']}` — {str(item['title']).replace('|', '&#124;')}"
            for item in items
        )

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
        "Pełne próbki wraz z fragmentami treści znajdują się w "
        "`data/reports/semantic-map-hierarchy-review-v1.json`.",
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
                "| Klaster | Rodzic | n | Centrum | Brzeg | Najbliższe spoza klastra |",
                "| --- | --- | ---: | --- | --- | --- |",
            ]
        )
        for cluster in variant["fineClusters"]:
            lines.append(
                f"| `{cluster['fineClusterId']}` | `{cluster['topClusterId']}` | "
                f"{cluster['size']} | {sample_titles(cluster['central'])} | "
                f"{sample_titles(cluster['boundary'])} | "
                f"{sample_titles(cluster['nearestOutside'])} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Pytania pomocnicze (nie etykiety)",
            "",
            *[f"- {question}" for question in review["expertReviewQuestions"]],
            "",
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


def main() -> None:
    review = json.loads(REVIEW_JSON_PATH.read_text(encoding="utf-8"))
    REVIEW_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_MD_PATH.write_text(review_markdown(review), encoding="utf-8")
    print(f"Updated hierarchy review note: {REVIEW_MD_PATH}")


if __name__ == "__main__":
    main()
