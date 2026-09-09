#!/usr/bin/env python3
"""Build the approved bilingual DataMapPlot hierarchy and its portable report."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
BASE_REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-v3-analysis.json"
HIERARCHY_REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-hierarchy-pilot-v1.json"
PROPOSAL_REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-hierarchy-label-proposals-v1.json"
SELECTION_PATH = ROOT / "config" / "semantic-map-hierarchy-selection-v1.yaml"
LABEL_REGISTRY_PATH = ROOT / "config" / "semantic-map-hierarchy-labels-v1.yaml"
PUBLICATION_REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-hierarchy-public-v1.json"
PUBLIC_OUTPUT_PATH = ROOT / "public" / "semantic-map"
DATAMAPPLOT_VERSION = "0.7.3"
SITE_BASE = "/scouting-autoresearch"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    result = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return result


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def approved_label_map(
    hierarchy: dict[str, Any],
    proposals: dict[str, Any],
    selection: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return approved labels, refusing partial, stale, or self-approved registries."""
    if selection.get("status") != "human-approved":
        raise ValueError("Hierarchy publication requires a human-approved variant")
    if selection.get("scope") != "navigational-cluster-presentation-only":
        raise ValueError("Hierarchy selection has an unsupported approval scope")
    if registry.get("status") != "human-approved":
        raise ValueError("Hierarchy publication requires human-approved labels")
    if registry.get("approvedBy") != "repository-owner":
        raise ValueError("Hierarchy labels were not approved by the repository owner")
    if registry.get("scope") != "navigational-cluster-presentation-only":
        raise ValueError("Hierarchy-label approval has an unsupported scope")
    approved_at = registry.get("approvedAt")
    if not isinstance(approved_at, str):
        raise ValueError("Hierarchy-label approval lacks an approval timestamp")
    try:
        parsed_approved_at = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Hierarchy-label approval timestamp is invalid") from error
    if parsed_approved_at.tzinfo is None:
        raise ValueError("Hierarchy-label approval timestamp must include a timezone")

    digest = hierarchy.get("corpus", {}).get("corpusDigest")
    for name, value in (
        ("selection", selection.get("corpusDigest")),
        ("proposals", proposals.get("corpusDigest")),
        ("registry", registry.get("corpusDigest")),
    ):
        if value != digest:
            raise ValueError(f"The {name} corpus digest is stale")
    if proposals.get("blindVariantId") != selection.get("blindVariantId"):
        raise ValueError("Label proposals do not match the selected hierarchy")

    expected: dict[str, dict[str, Any]] = {}
    for level in ("fine", "top"):
        values = proposals.get(level)
        if not isinstance(values, dict):
            raise ValueError(f"Proposal report lacks the {level} label layer")
        for cluster_id, proposal in values.items():
            expected[cluster_id] = {"level": level, **proposal}

    approved = registry.get("approvedLabels")
    if not isinstance(approved, list):
        raise ValueError("Approved labels must be a list")
    approved_by_id: dict[str, dict[str, Any]] = {}
    required_text = ("namePl", "descriptionPl", "nameEn", "descriptionEn")
    for item in approved:
        if not isinstance(item, dict):
            raise ValueError("Each approved label must be a mapping")
        cluster_id = str(item.get("clusterId") or "")
        if not cluster_id or cluster_id in approved_by_id:
            raise ValueError(f"Duplicate or missing approved cluster ID: {cluster_id!r}")
        proposal = expected.get(cluster_id)
        if proposal is None:
            raise ValueError(f"Unexpected approved cluster ID: {cluster_id}")
        if item.get("status") != "human-approved":
            raise ValueError(f"Label {cluster_id} is not human-approved")
        if item.get("level") != proposal["level"]:
            raise ValueError(f"Label {cluster_id} has the wrong hierarchy level")
        if item.get("proposalInputHash") != proposal.get("inputHash"):
            raise ValueError(f"Label {cluster_id} does not reference the current proposal")
        if any(not str(item.get(field) or "").strip() for field in required_text):
            raise ValueError(f"Label {cluster_id} lacks complete Polish and English text")
        approved_by_id[cluster_id] = item

    missing = sorted(set(expected) - set(approved_by_id))
    if missing:
        raise ValueError(f"Hierarchy-label approval is incomplete: {', '.join(missing)}")
    if len(approved_by_id) != 40:
        raise ValueError(f"Expected 40 approved hierarchy labels, found {len(approved_by_id)}")

    for level in ("fine", "top"):
        for locale_key in ("namePl", "nameEn"):
            names = [
                item[locale_key].strip().casefold()
                for item in approved_by_id.values()
                if item["level"] == level
            ]
            if len(names) != len(set(names)):
                raise ValueError(f"Approved {level} labels contain duplicate {locale_key} names")
    return approved_by_id


def convex_hull(points: list[tuple[float, float]]) -> list[list[float]]:
    """Return a deterministic convex boundary without adding another dependency."""
    unique = sorted(set(points))
    if len(unique) <= 2:
        return [[round(x, 8), round(y, 8)] for x, y in unique]

    def cross(origin: tuple[float, float], left: tuple[float, float], right: tuple[float, float]) -> float:
        return (left[0] - origin[0]) * (right[1] - origin[1]) - (left[1] - origin[1]) * (right[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    boundary = lower[:-1] + upper[:-1]
    return [[round(x, 8), round(y, 8)] for x, y in boundary]


def build_publication_report(
    base: dict[str, Any],
    hierarchy: dict[str, Any],
    selection: dict[str, Any],
    registry: dict[str, Any],
    labels: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    variants = {
        variant["blindVariantId"]: variant for variant in hierarchy.get("variants", [])
    }
    variant = variants.get(selection.get("blindVariantId"))
    if variant is None or variant.get("algorithm") != selection.get("algorithm"):
        raise ValueError("Selected hierarchy variant is absent or mismatched")

    base_points = {point["activityId"]: point for point in base.get("points", [])}
    assignments = {point["activityId"]: point for point in variant.get("points", [])}
    if set(base_points) != set(assignments) or len(base_points) != 914:
        raise ValueError("Selected hierarchy does not cover the 914-point base map exactly")
    points = []
    for activity_id in sorted(base_points):
        source = base_points[activity_id]
        assignment = assignments[activity_id]
        points.append(
            {
                "activityId": activity_id,
                "sourceId": source["sourceId"],
                "sourceHash": source["sourceHash"],
                "inputHash": source["inputHash"],
                "x": source["x"],
                "y": source["y"],
                "fineClusterId": assignment["fineClusterId"],
                "topClusterId": assignment["topClusterId"],
            }
        )

    def cluster_geometry(cluster_id: str, level: str) -> dict[str, Any]:
        member_points = [
            (point["x"], point["y"])
            for point in points
            if point[f"{level}ClusterId"] == cluster_id
        ]
        if not member_points:
            raise ValueError(f"Approved cluster has no points: {cluster_id}")
        return {
            "centroid": [
                round(sum(point[index] for point in member_points) / len(member_points), 8)
                for index in (0, 1)
            ],
            "boundaryPolygon": convex_hull(member_points),
        }

    fine_clusters = []
    for source in variant.get("fineClusters", []):
        cluster_id = source["fineClusterId"]
        approved = labels[cluster_id]
        fine_clusters.append(
            {
                "id": cluster_id,
                "parentId": source["topClusterId"],
                "size": source["size"],
                **cluster_geometry(cluster_id, "fine"),
                "status": "human-approved",
                "labels": {
                    "pl": {"name": approved["namePl"], "description": approved["descriptionPl"]},
                    "en": {"name": approved["nameEn"], "description": approved["descriptionEn"]},
                },
            }
        )
    top_clusters = []
    for source in variant.get("topClusters", []):
        cluster_id = source["topClusterId"]
        approved = labels[cluster_id]
        top_clusters.append(
            {
                "id": cluster_id,
                "parentId": None,
                "childFineClusterIds": source["childFineClusterIds"],
                "size": sum(point["topClusterId"] == cluster_id for point in points),
                **cluster_geometry(cluster_id, "top"),
                "status": "human-approved",
                "labels": {
                    "pl": {"name": approved["namePl"], "description": approved["descriptionPl"]},
                    "en": {"name": approved["nameEn"], "description": approved["descriptionEn"]},
                },
            }
        )

    approved_relations = [
        relation
        for relation in base.get("approvedRelationOverlays", [])
        if relation.get("status") == "human-approved"
    ]
    report = {
        "schemaVersion": 1,
        "pipeline": "semantic-map-hierarchy-public-v1",
        "status": "human-approved",
        "generatedAt": registry["approvedAt"],
        "projectionIsNavigationalOnly": True,
        "corpus": hierarchy["corpus"],
        "selection": {
            "blindVariantId": selection["blindVariantId"],
            "algorithm": selection["algorithm"],
            "approvedBy": selection["approvedBy"],
            "approvedAt": selection["approvedAt"],
            "scope": selection["scope"],
        },
        "labelApproval": {
            "approvedBy": registry["approvedBy"],
            "approvedAt": registry["approvedAt"],
            "scope": registry["scope"],
        },
        "implementation": {
            **hierarchy["implementation"],
            "dataMapPlot": DATAMAPPLOT_VERSION,
            "renderer": "bilingual-hierarchic-datamapplot-v1",
        },
        "metrics": variant["metrics"],
        "clusters": {"top": top_clusters, "fine": fine_clusters},
        "points": points,
        "approvedRelationOverlays": approved_relations,
    }
    report["reportDigest"] = canonical_digest(report)
    return report


def cluster_download_options(report: dict[str, Any], locale: str) -> list[dict[str, Any]]:
    options = []
    labels = {
        "top": "Region" if locale == "pl" else "Region",
        "fine": "Podregion" if locale == "pl" else "Subregion",
    }
    for level in ("top", "fine"):
        for cluster in sorted(report["clusters"][level], key=lambda item: item["id"]):
            options.append(
                {
                    "level": level,
                    "id": cluster["id"],
                    "name": cluster["labels"][locale]["name"],
                    "size": cluster["size"],
                    "label": labels[level],
                    "url": f"downloads/{level}/{cluster['id']}.txt",
                }
            )
    return options


def accessible_html(
    records: list[dict[str, Any]],
    locale: str,
    relations: list[dict[str, Any]],
    download_options: list[dict[str, Any]] | None = None,
) -> str:
    is_pl = locale == "pl"
    back_label = "Powrót do strony mapy" if is_pl else "Back to the map page"
    list_label = "Dostępna lista wszystkich 914 gier" if is_pl else "Accessible list of all 914 games"
    caveat = (
        "Położenie i regiony służą wyłącznie nawigacji; nie są klasyfikacją historyczną."
        if is_pl
        else "Positions and regions are navigational only; they are not a historical classification."
    )
    back_url = f"{SITE_BASE}/{'en/' if not is_pl else ''}map/"
    items = []
    for record in sorted(records, key=lambda value: (value["title"].casefold(), value["id"])):
        detail = f'{record["author"]}, {record["sourceTitle"]} ({record["year"]}) · {record["topName"]} → {record["fineName"]}'
        items.append(
            f'<li data-map-list-item><a target="_top" href="{html.escape(record["activityUrl"], quote=True)}">'
            f'{html.escape(record["title"])}</a><span>{html.escape(detail)}</span></li>'
        )
    relation_notes = []
    record_by_id = {record["id"]: record for record in records}
    for relation in relations:
        left, right = (record_by_id[item] for item in relation["activityIds"])
        label = "Zatwierdzony wariant" if is_pl else "Approved variant link"
        relation_notes.append(
            f'<p data-map-relation><strong>{label}:</strong> '
            f'<a target="_top" href="{html.escape(left["activityUrl"], quote=True)}">{html.escape(left["title"])}</a> — '
            f'<a target="_top" href="{html.escape(right["activityUrl"], quote=True)}">{html.escape(right["title"])}</a></p>'
        )
    download_options = download_options or []
    download_heading = "Pobierz klaster jako TXT" if is_pl else "Download a cluster as TXT"
    download_intro = (
        "Wybierz region lub podregion. Plik zawiera pełne teksty gier i ich proweniencję do dalszej pracy z LLM."
        if is_pl
        else "Choose a region or subregion. The file contains full game texts and provenance for further LLM work."
    )
    choose_label = "Wybierz klaster" if is_pl else "Choose a cluster"
    button_label = "Pobierz TXT" if is_pl else "Download TXT"
    option_groups = []
    for level in ("top", "fine"):
        group = [item for item in download_options if item["level"] == level]
        if not group:
            continue
        if level == "top":
            group_label = "Regiony" if is_pl else "Regions"
        else:
            group_label = "Podregiony" if is_pl else "Subregions"
        choices = "".join(
            f'<option value="{html.escape(item["url"], quote=True)}">'
            f'{html.escape(item["label"])}: {html.escape(item["name"])} ({item["size"]})</option>'
            for item in group
        )
        option_groups.append(f'<optgroup label="{group_label}">{choices}</optgroup>')
    downloads = (
        '<details class="cluster-downloads" data-cluster-downloads><summary>'
        f'{download_heading}</summary><p>{download_intro}</p>'
        f'<label for="cluster-download-select">{choose_label}</label>'
        '<select id="cluster-download-select" data-cluster-download-select '
        'onchange="const link=this.parentElement.querySelector(\'[data-cluster-download-link]\');'
        'link.href=this.value;link.hidden=!this.value">'
        f'<option value="">— {choose_label} —</option>{"".join(option_groups)}</select>'
        f'<a data-cluster-download-link download hidden href="">{button_label}</a></details>'
    )
    return (
        '<nav class="project-nav" aria-label="Scouting Autoresearch">'
        f'<a target="_top" href="{back_url}">← {back_label}</a><p>{caveat}</p></nav>'
        + "".join(relation_notes)
        + downloads
        + f'<details class="accessible-map-list" data-accessible-map-list><summary>{list_label}</summary>'
        + '<ol class="accessible-map-items">'
        + "".join(items)
        + "</ol></details>"
    )


def cluster_txt(
    report: dict[str, Any],
    cluster: dict[str, Any],
    level: str,
    records: list[dict[str, Any]],
    locale: str,
) -> str:
    is_pl = locale == "pl"
    id_key = f"{level}ClusterId"
    members = sorted(
        (record for record in records if record[id_key] == cluster["id"]),
        key=lambda item: (item["title"].casefold(), item["id"]),
    )
    if len(members) != cluster["size"]:
        raise ValueError(
            f"TXT export size mismatch for {locale} {cluster['id']}: "
            f"expected {cluster['size']}, found {len(members)}"
        )
    label = cluster["labels"][locale]
    level_name = (
        ("region" if level == "top" else "podregion")
        if is_pl
        else ("region" if level == "top" else "subregion")
    )
    lines = [
        "SCOUTING AUTORESEARCH — EKSPORT KLASTRA TXT" if is_pl else "SCOUTING AUTORESEARCH — CLUSTER TXT EXPORT",
        f"Język: polski (pl)" if is_pl else "Language: English (en)",
        f"Poziom: {level_name}" if is_pl else f"Level: {level_name}",
        f"ID klastra: {cluster['id']}" if is_pl else f"Cluster ID: {cluster['id']}",
        f"Nazwa: {label['name']}" if is_pl else f"Name: {label['name']}",
        f"Opis: {label['description']}" if is_pl else f"Description: {label['description']}",
        f"Liczba gier: {len(members)}" if is_pl else f"Games: {len(members)}",
        f"Hash raportu: {report['reportDigest']}" if is_pl else f"Report digest: {report['reportDigest']}",
        "Zakres: klaster nawigacyjny; nie jest klasyfikacją historyczną." if is_pl else "Scope: navigational cluster; not a historical classification.",
        "Każdy rekord zachowuje własny status prawny, status tekstu i odnośniki źródłowe." if is_pl else "Each record retains its own rights status, text status, and source links.",
        "",
    ]
    for index, record in enumerate(members, 1):
        text_status = (
            "tekst źródłowy"
            if record["translationStatus"] == "source-text" and is_pl
            else "source text"
            if record["translationStatus"] == "source-text"
            else f"tłumaczenie automatyczne ({record.get('translationModel') or 'model nieustalony'}, bez weryfikacji człowieka)"
            if is_pl
            else f"automatic translation ({record.get('translationModel') or 'unknown model'}, not human-verified)"
        )
        lines.extend(
            [
                "=" * 80,
                f"[{index}/{len(members)}]",
                f"ID: {record['id']}",
                f"Tytuł: {record['title']}" if is_pl else f"Title: {record['title']}",
                f"Autor: {record['author']}" if is_pl else f"Author: {record['author']}",
                f"Źródło: {record['sourceTitle']} ({record['year']})" if is_pl else f"Source: {record['sourceTitle']} ({record['year']})",
                f"Rekord źródłowy: {record['sourceUrl']}" if is_pl else f"Source record: {record['sourceUrl']}",
                f"Wydanie cyfrowe: {record['digitalEditionUrl']}" if is_pl else f"Digital edition: {record['digitalEditionUrl']}",
                f"Faksymile: {record.get('facsimileUrl') or '-'}" if is_pl else f"Facsimile: {record.get('facsimileUrl') or '-'}",
                f"Status prawny: {record['rightsStatus']}" if is_pl else f"Rights status: {record['rightsStatus']}",
                f"Język oryginału: {record['originalLanguage']}" if is_pl else f"Original language: {record['originalLanguage']}",
                f"Status tekstu: {text_status}" if is_pl else f"Text status: {text_status}",
                f"Karta gry: {record['activityUrl']}" if is_pl else f"Activity page: {record['activityUrl']}",
                "",
                "TEKST" if is_pl else "TEXT",
                "",
                str(record["body"]).strip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_cluster_downloads(
    report: dict[str, Any], records: list[dict[str, Any]], locale: str, output_dir: Path
) -> list[Path]:
    outputs = []
    for level in ("top", "fine"):
        directory = output_dir / "downloads" / level
        directory.mkdir(parents=True, exist_ok=True)
        for cluster in sorted(report["clusters"][level], key=lambda item: item["id"]):
            path = directory / f"{cluster['id']}.txt"
            path.write_text(cluster_txt(report, cluster, level, records, locale), encoding="utf-8")
            outputs.append(path)
    if len(outputs) != 40:
        raise ValueError(f"Expected 40 TXT cluster exports for {locale}, found {len(outputs)}")
    return outputs


def relation_svg(
    output: Path,
    coordinates: list[list[float]],
    activity_ids: list[str],
    relations: list[dict[str, Any]],
) -> None:
    import numpy as np
    from datamapplot.rendering_helpers import compute_percentile_bounds

    raw = np.asarray(coordinates, dtype=float)
    bounds = compute_percentile_bounds(raw)
    scale = 30.0 / max(bounds[1] - bounds[0], bounds[3] - bounds[2])
    transformed = scale * (raw - np.mean(raw, axis=0))
    by_id = {activity_id: transformed[index] for index, activity_id in enumerate(activity_ids)}
    min_x, min_y = np.min(transformed, axis=0)
    max_x, max_y = np.max(transformed, axis=0)
    width = max_x - min_x
    height = max_y - min_y
    lines = []
    for relation in relations:
        left, right = (by_id[item] for item in relation["activityIds"])
        lines.append(
            f'<line x1="{left[0]:.8f}" y1="{-left[1]:.8f}" x2="{right[0]:.8f}" y2="{-right[1]:.8f}" '
            'stroke="#ffe08a" stroke-width="0.16" stroke-linecap="round" opacity="0.95" />'
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{min_x:.8f} {-max_y:.8f} {width:.8f} {height:.8f}" '
        'preserveAspectRatio="none" data-approved-relation-layer="true">'
        + "".join(lines)
        + "</svg>\n"
    )
    output.write_text(svg, encoding="utf-8")


def finalize_offline_html(path: Path, locale: str) -> None:
    """Remove DataMapPlot's redundant remote CSS/font hints after offline embedding."""
    rendered = path.read_text(encoding="utf-8")
    rendered = rendered.replace("<html>", f'<html lang="{locale}">', 1)
    rendered = re.sub(
        r'<link\b[^>]*\bhref="https://(?:fonts\.(?:googleapis|gstatic)\.com|maxcdn\.bootstrapcdn\.com)(?:/[^\"]*)?"[^>]*>\s*',
        "",
        rendered,
        flags=re.IGNORECASE,
    )
    path.write_text(rendered, encoding="utf-8")


def render_locale(report: dict[str, Any], locale: str, output_root: Path) -> list[Path]:
    import datamapplot
    import numpy as np
    import pandas as pd

    if datamapplot.__version__ != DATAMAPPLOT_VERSION:
        raise ValueError(f"Expected DataMapPlot {DATAMAPPLOT_VERSION}, found {datamapplot.__version__}")
    activities = read_json(ROOT / "data" / "generated" / f"activities.{locale}.json")
    activity_by_id = {item["id"]: item for item in activities}
    top_by_id = {item["id"]: item for item in report["clusters"]["top"]}
    fine_by_id = {item["id"]: item for item in report["clusters"]["fine"]}
    locale_key = locale
    records = []
    coordinates = []
    fine_labels = []
    top_labels = []
    for point in report["points"]:
        activity = activity_by_id.get(point["activityId"])
        if activity is None:
            raise ValueError(f"Missing {locale} activity for {point['activityId']}")
        top_label = top_by_id[point["topClusterId"]]["labels"][locale_key]
        fine_label = fine_by_id[point["fineClusterId"]]["labels"][locale_key]
        activity_url = f"{SITE_BASE}/{'en/' if locale == 'en' else ''}activities/{activity['id']}/"
        record = {
            "id": activity["id"],
            "title": activity["title"],
            "author": activity["author"],
            "year": activity["year"],
            "sourceTitle": activity["sourceTitle"],
            "summary": activity["summary"],
            "body": activity["body"],
            "rightsStatus": activity["rightsStatus"],
            "originalLanguage": activity["originalLanguage"],
            "translationStatus": activity["translationStatus"],
            "translationModel": activity.get("translationModel"),
            "sourceUrl": activity["sourceUrl"],
            "digitalEditionUrl": activity["digitalEditionUrl"],
            "facsimileUrl": activity.get("facsimileUrl"),
            "fineClusterId": point["fineClusterId"],
            "topClusterId": point["topClusterId"],
            "topName": top_label["name"],
            "topDescription": top_label["description"],
            "fineName": fine_label["name"],
            "fineDescription": fine_label["description"],
            "activityUrl": activity_url,
        }
        records.append(record)
        coordinates.append([point["x"], point["y"]])
        fine_labels.append(fine_label["name"])
        top_labels.append(top_label["name"])

    escaped = lambda value: html.escape(str(value), quote=True)
    extra_data = pd.DataFrame(
        {
            "activity_id": [escaped(item["id"]) for item in records],
            "author": [escaped(item["author"]) for item in records],
            "year": [escaped(item["year"]) for item in records],
            "source_title": [escaped(item["sourceTitle"]) for item in records],
            "summary": [escaped(item["summary"]) for item in records],
            "top_name": [escaped(item["topName"]) for item in records],
            "fine_name": [escaped(item["fineName"]) for item in records],
            "activity_url": [item["activityUrl"] for item in records],
            "search_text": [
                " ".join(
                    str(item[key])
                    for key in ("id", "title", "author", "year", "sourceTitle", "topName", "fineName")
                )
                for item in records
            ],
        }
    )
    labels = {
        "pl": {
            "title": "Semantyczna mapa historycznych gier harcerskich",
            "subtitle": "914 gier · 8 regionów · 32 podregiony · układ Amber",
            "tree": "Regiony i podregiony",
            "book": "Książka",
            "region": "Region",
            "subregion": "Podregion",
        },
        "en": {
            "title": "Semantic map of historical scouting games",
            "subtitle": "914 games · 8 regions · 32 subregions · Amber layout",
            "tree": "Regions and subregions",
            "book": "Book",
            "region": "Region",
            "subregion": "Subregion",
        },
    }[locale]
    tooltip = (
        '<div class="tooltip-card"><h2>{hover_text}</h2>'
        '<p>{author} · {year}</p>'
        f'<p><strong>{labels["book"]}:</strong> {{source_title}}</p>'
        '<p>{summary}</p>'
        f'<p><strong>{labels["region"]}:</strong> {{top_name}}<br>'
        f'<strong>{labels["subregion"]}:</strong> {{fine_name}}</p>'
        '<p class="tooltip-id">{activity_id}</p></div>'
    )
    custom_css = """
html, body { background: #0b1016 !important; color: #f4ead8 !important; }
.project-nav { position: fixed; z-index: 20; left: 1rem; bottom: 1rem; max-width: min(34rem, calc(100vw - 2rem)); padding: .65rem .85rem; border: 1px solid #86662f; border-radius: .65rem; background: #101821ee; color: #eadfc9; font: 600 13px/1.35 system-ui, sans-serif; }
.project-nav a, .accessible-map-list a, [data-map-relation] a { color: #ffe08a; }
.project-nav p { margin: .25rem 0 0; font-weight: 400; }
.accessible-map-list { position: fixed; z-index: 21; right: 1rem; bottom: 1rem; width: min(32rem, calc(100vw - 2rem)); max-height: 45vh; overflow: auto; padding: .65rem .85rem; border: 1px solid #86662f; border-radius: .65rem; background: #101821f5; color: #f4ead8; font: 14px/1.4 system-ui, sans-serif; }
.accessible-map-list summary { cursor: pointer; font-weight: 800; }
.accessible-map-items { padding-left: 1.4rem; }
.accessible-map-items li { margin: .55rem 0; }
.accessible-map-items span { display: block; color: #c9bda8; font-size: 12px; }
[data-map-relation] { position: fixed; z-index: 20; right: 1rem; top: 4.2rem; max-width: min(32rem, calc(100vw - 2rem)); padding: .55rem .75rem; border-left: 4px solid #ffe08a; background: #101821ee; color: #f4ead8; font: 13px/1.4 system-ui, sans-serif; }
.cluster-downloads { position: fixed; z-index: 21; left: 1rem; top: 4.2rem; width: min(30rem, calc(100vw - 2rem)); padding: .65rem .85rem; border: 1px solid #86662f; border-radius: .65rem; background: #101821f5; color: #f4ead8; font: 14px/1.4 system-ui, sans-serif; }
.cluster-downloads summary { cursor: pointer; font-weight: 800; }
.cluster-downloads p { margin: .5rem 0; color: #c9bda8; }
.cluster-downloads label { display: block; margin-bottom: .25rem; font-weight: 700; }
.cluster-downloads select { max-width: 100%; padding: .4rem; border: 1px solid #86662f; border-radius: .35rem; background: #0b1016; color: #f4ead8; }
.cluster-downloads [data-cluster-download-link] { display: inline-block; margin-left: .5rem; color: #ffe08a; font-weight: 800; }
.cluster-downloads [data-cluster-download-link][hidden] { display: none; }
.tooltip-card h2 { margin: 0 0 .35rem; font-size: 1.05rem; }
.tooltip-card p { margin: .35rem 0; }
.tooltip-id { color: #c9bda8; font-family: ui-monospace, monospace; }
@media (max-width: 48rem) { .project-nav { bottom: 4rem; } .accessible-map-list { max-height: 38vh; } [data-map-relation] { top: 7rem; } .cluster-downloads { top: 7rem; } }
"""

    output_dir = output_root / locale
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    relation_svg(
        output_dir / "approved-relations.svg",
        coordinates,
        [item["id"] for item in records],
        report["approvedRelationOverlays"],
    )
    figure = datamapplot.create_interactive_plot(
        np.asarray(coordinates, dtype=float),
        np.asarray(fine_labels, dtype=object),
        np.asarray(top_labels, dtype=object),
        hover_text=np.asarray([escaped(item["title"]) for item in records], dtype=object),
        extra_point_data=extra_data,
        hover_text_html_template=tooltip,
        on_click="window.top.location.assign(`{activity_url}`)",
        enable_search=True,
        search_field="search_text",
        enable_topic_tree=True,
        topic_tree_kwds={"title": labels["tree"], "color_bullets": True, "max_width": "34vw"},
        cluster_boundary_polygons=True,
        color_cluster_boundaries=True,
        polygon_alpha=0.08,
        darkmode=True,
        background_color="#0b1016",
        background_image="approved-relations.svg",
        title=labels["title"],
        sub_title=labels["subtitle"],
        font_family="Roboto",
        color_label_text=True,
        label_wrap_width=24,
        initial_zoom_fraction=0.96,
        point_radius_min_pixels=1.1,
        point_radius_max_pixels=14,
        point_hover_color="#ffe08a",
        inline_data=False,
        offline_data_path=output_dir / "map",
        offline_mode=True,
        custom_html=accessible_html(
            records,
            locale,
            report["approvedRelationOverlays"],
            cluster_download_options(report, locale),
        ),
        custom_css=custom_css,
    )
    figure.save(str(output_dir / "index.html"))
    finalize_offline_html(output_dir / "index.html", locale)
    downloads = write_cluster_downloads(report, records, locale, output_dir)
    required = [output_dir / "index.html", output_dir / "approved-relations.svg"]
    required.extend(sorted(output_dir.glob("map_*.zip")))
    required.extend(downloads)
    if len(required) < 5 or any(not path.is_file() or path.stat().st_size == 0 for path in required):
        raise ValueError(f"Incomplete DataMapPlot output for {locale}: {[path.name for path in required]}")
    return required


def smoke_render(output_root: Path) -> None:
    import datamapplot
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(20260909)
    coordinates = np.vstack(
        [rng.normal(loc=(index % 4 * 4, index // 4 * 4), scale=0.55, size=(16, 2)) for index in range(4)]
    )
    fine = np.asarray([f"Smoke fine {index // 16 + 1}" for index in range(64)], dtype=object)
    top = np.asarray([f"Smoke top {index // 32 + 1}" for index in range(64)], dtype=object)
    output_dir = output_root / "smoke"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    figure = datamapplot.create_interactive_plot(
        coordinates,
        fine,
        top,
        hover_text=np.asarray([f"Smoke game {index + 1}" for index in range(64)], dtype=object),
        extra_point_data=pd.DataFrame({"search_text": [f"smoke-{index + 1}" for index in range(64)]}),
        enable_search=True,
        enable_topic_tree=True,
        cluster_boundary_polygons=True,
        darkmode=True,
        inline_data=False,
        offline_data_path=output_dir / "map",
        offline_mode=True,
        title="Hierarchy smoke render",
    )
    figure.save(str(output_dir / "index.html"))
    finalize_offline_html(output_dir / "index.html", "en")
    outputs = [output_dir / "index.html", *sorted(output_dir.glob("map_*.zip"))]
    if len(outputs) < 4 or any(path.stat().st_size == 0 for path in outputs):
        raise ValueError(f"Smoke render is incomplete: {[path.name for path in outputs]}")
    print(f"DataMapPlot smoke render passed: 64 points, {len(outputs)} files")


def load_approved_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    base = read_json(BASE_REPORT_PATH)
    hierarchy = read_json(HIERARCHY_REPORT_PATH)
    proposals = read_json(PROPOSAL_REPORT_PATH)
    selection = read_yaml(SELECTION_PATH)
    registry = read_yaml(LABEL_REGISTRY_PATH)
    labels = approved_label_map(hierarchy, proposals, selection, registry)
    report = build_publication_report(base, hierarchy, selection, registry, labels)
    return report, registry


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_outputs(report: dict[str, Any], output_root: Path) -> None:
    if not PUBLICATION_REPORT_PATH.is_file():
        raise ValueError("Portable hierarchy publication report is missing")
    persisted = read_json(PUBLICATION_REPORT_PATH)
    if persisted != report:
        raise ValueError("Portable hierarchy publication report is stale")
    for locale in ("pl", "en"):
        output_dir = output_root / locale
        html_path = output_dir / "index.html"
        if not html_path.is_file():
            raise ValueError(f"Public DataMapPlot output is missing for {locale}")
        rendered = html_path.read_text(encoding="utf-8")
        for required in ("topic-tree", "search-container", "data-accessible-map-list", "data-map-relation"):
            if required not in rendered:
                raise ValueError(f"Public {locale} map lacks {required}")
        for forbidden in ("algorithmicCandidates", "nearestNeighbors", "algorithmic-candidate"):
            if forbidden in rendered:
                raise ValueError(f"Public {locale} map exposes {forbidden}")
        if re.search(r'<(?:script|link)\b[^>]*(?:src|href)="https?://', rendered, re.IGNORECASE):
            raise ValueError(f"Public {locale} map still depends on a CDN")
        if len(list(output_dir.glob("map_*.zip"))) < 3:
            raise ValueError(f"Public {locale} map lacks non-inline compressed data")
        expected_downloads = {
            output_dir / "downloads" / level / f"{cluster['id']}.txt"
            for level in ("top", "fine")
            for cluster in report["clusters"][level]
        }
        actual_downloads = set((output_dir / "downloads").glob("*/*.txt"))
        if actual_downloads != expected_downloads or any(path.stat().st_size == 0 for path in actual_downloads):
            raise ValueError(f"Public {locale} map lacks complete TXT cluster exports")
    print("Approved bilingual DataMapPlot outputs are current")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--output", type=Path, default=PUBLIC_OUTPUT_PATH)
    args = parser.parse_args()
    if args.smoke:
        smoke_render(args.output)
        return
    report, _ = load_approved_inputs()
    if args.check:
        check_outputs(report, args.output)
        return
    write_json(PUBLICATION_REPORT_PATH, report)
    outputs = []
    for locale in ("pl", "en"):
        outputs.extend(render_locale(report, locale, args.output))
    check_outputs(report, args.output)
    print(f"Rendered bilingual semantic map: {len(report['points'])} points, {len(outputs)} files")


if __name__ == "__main__":
    main()
