#!/usr/bin/env python3
"""Render a self-contained local HTML for the hierarchy selection gate."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-v3-analysis.json"
HIERARCHY_REPORT_PATH = ROOT / "data" / "reports" / "semantic-map-hierarchy-pilot-v1.json"
REVIEW_PATH = ROOT / "data" / "reports" / "semantic-map-hierarchy-review-v1.json"
ACTIVITIES_PATH = ROOT / "data" / "generated" / "activities.pl.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "hierarchic-map-pilot" / "cluster-comparison.html"
PUBLIC_BASE = "https://jfpio.github.io/scouting-autoresearch"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def short_text(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_payload() -> dict[str, Any]:
    base = read_json(BASE_REPORT_PATH)
    hierarchy = read_json(HIERARCHY_REPORT_PATH)
    review = read_json(REVIEW_PATH)
    activities = read_json(ACTIVITIES_PATH)
    if hierarchy.get("status") != "human-review-required" or not hierarchy.get("proposalOnly"):
        raise ValueError("Hierarchy comparison must remain proposal-only")
    if hierarchy["corpus"]["activities"] != 914:
        raise ValueError("Hierarchy comparison corpus must contain 914 activities")
    if hierarchy["corpus"]["corpusDigest"] != review["corpusDigest"]:
        raise ValueError("Hierarchy and review corpus digests differ")

    activity_by_id = {
        item["id"]: item for item in activities if "game" in (item.get("kinds") or [])
    }
    coordinate_by_id = {
        item["activityId"]: item for item in base.get("points") or []
    }
    assignment_by_variant = {
        variant["blindVariantId"]: {
            point["activityId"]: point for point in variant["points"]
        }
        for variant in hierarchy["variants"]
    }
    ids = sorted(coordinate_by_id)
    if set(ids) != set(activity_by_id) or any(
        set(ids) != set(assignments) for assignments in assignment_by_variant.values()
    ):
        raise ValueError("Comparison inputs do not cover the same game corpus")

    review_by_variant = {
        item["blindVariantId"]: item for item in review["variants"]
    }
    variants = []
    for variant in hierarchy["variants"]:
        blind_id = variant["blindVariantId"]
        review_clusters = {
            item["fineClusterId"]: item
            for item in review_by_variant[blind_id]["fineClusters"]
        }
        variants.append(
            {
                "id": blind_id,
                "eligible": variant["eligibleForHumanReview"],
                "metrics": variant["metrics"],
                "clusters": [
                    {
                        "id": cluster["fineClusterId"],
                        "parentId": cluster["topClusterId"],
                        "size": cluster["size"],
                        "central": [
                            {"id": item["activityId"], "title": item["title"]}
                            for item in review_clusters[cluster["fineClusterId"]]["central"]
                        ],
                    }
                    for cluster in variant["fineClusters"]
                ],
            }
        )

    points = []
    for activity_id in ids:
        activity = activity_by_id[activity_id]
        coordinate = coordinate_by_id[activity_id]
        points.append(
            {
                "id": activity_id,
                "x": coordinate["x"],
                "y": coordinate["y"],
                "title": short_text(activity.get("title"), 180),
                "summary": short_text(activity.get("summary"), 360),
                "author": short_text(activity.get("author"), 120),
                "year": activity.get("year"),
                "source": short_text(activity.get("sourceTitle"), 180),
                "url": f"{PUBLIC_BASE}/activities/{activity_id}/",
                "assignments": {
                    variant_id: {
                        "fine": assignments[activity_id]["fineClusterId"],
                        "top": assignments[activity_id]["topClusterId"],
                    }
                    for variant_id, assignments in assignment_by_variant.items()
                },
            }
        )

    overlays = []
    for relation in base.get("approvedRelationOverlays") or []:
        if relation.get("status") != "human-approved":
            raise ValueError("Comparison cannot expose unapproved similarity relations")
        overlays.append(
            {
                "id": relation["relationId"],
                "activityIds": relation["activityIds"],
                "status": "human-approved",
            }
        )
    return {
        "schemaVersion": 1,
        "purpose": "human-selection-gate",
        "proposalOnly": True,
        "projectionIsNavigationalOnly": True,
        "corpusDigest": hierarchy["corpus"]["corpusDigest"],
        "points": points,
        "variants": variants,
        "approvedRelations": overlays,
        "expertQuestions": review["expertReviewQuestions"],
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ślepa recenzja hierarchii mapy semantycznej</title>
<style>
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#0b0d12;color:#f6f7fb}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 25% 10%,#18213a 0,#0b0d12 36%)}
button,input,select{font:inherit}.app{display:grid;grid-template-columns:minmax(0,1fr) 390px;min-height:100vh}
.stage{position:relative;min-height:100vh;overflow:hidden}.topbar{position:absolute;z-index:5;top:16px;left:16px;right:16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px;background:#111622e8;border:1px solid #34405a;border-radius:14px;box-shadow:0 8px 30px #0008}
.brand{font-weight:750;margin-right:auto}.pill,.control{border:1px solid #485774;background:#171e2d;color:#fff;border-radius:10px;padding:8px 10px}.pill[aria-pressed=true]{background:#f0b429;color:#10131b;border-color:#f0b429;font-weight:750}.warning{color:#ffcf66}.ok{color:#8ee6a1}
#map{width:100%;height:100vh;display:block;touch-action:none;cursor:grab}#map.dragging{cursor:grabbing}.point{stroke:#0a0c11;stroke-width:.7;vector-effect:non-scaling-stroke;cursor:pointer}.point.dim{opacity:.07}.point.match{stroke:#fff;stroke-width:2.2}.relation{stroke:#fff;stroke-width:1.2;stroke-dasharray:4 3;opacity:.8;vector-effect:non-scaling-stroke;pointer-events:none}
.tooltip{position:absolute;z-index:8;max-width:360px;pointer-events:none;background:#090b10f2;border:1px solid #66718b;border-radius:12px;padding:12px;box-shadow:0 8px 30px #000b;display:none}.tooltip strong{display:block;font-size:1.04rem;margin-bottom:4px}.tooltip .meta{color:#b7c1d6;font-size:.84rem;margin-bottom:7px}.tooltip p{margin:0;color:#e4e8f2;line-height:1.35}
.help{position:absolute;z-index:4;left:16px;bottom:16px;color:#c2cad9;background:#111622d9;border:1px solid #34405a;border-radius:10px;padding:8px 10px;font-size:.82rem}
aside{height:100vh;overflow:auto;padding:18px;background:#10141f;border-left:1px solid #303a50}aside h1{font-size:1.15rem;margin:0 0 6px}aside p{color:#b8c1d4;line-height:1.4}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:14px 0}.metric{background:#181e2b;border:1px solid #303a50;border-radius:9px;padding:9px}.metric span{display:block;color:#9eabc4;font-size:.72rem}.metric b{font-size:1rem}.cluster{border:1px solid #303a50;background:#151a25;border-radius:10px;padding:10px;margin:8px 0;cursor:pointer}.cluster:hover,.cluster.active{border-color:#f0b429;background:#1d2432}.cluster-head{display:flex;align-items:center;gap:8px}.swatch{width:13px;height:13px;border-radius:50%;flex:none}.cluster small{color:#9eabc4}.cluster ul{padding-left:18px;margin:7px 0 0;color:#dce2ee;font-size:.82rem}.questions{border-top:1px solid #303a50;margin-top:18px;padding-top:12px}.questions li{margin:7px 0;color:#ccd4e4}
@media(max-width:850px){.app{grid-template-columns:1fr}.stage{min-height:70vh}.stage,#map{height:70vh}aside{height:auto;border-left:0;border-top:1px solid #303a50}.topbar{position:absolute}.brand{width:100%}}
</style>
</head>
<body>
<main class="app">
 <section class="stage" aria-label="Interaktywna mapa porównawcza">
  <div class="topbar">
   <span class="brand">Hierarchiczna mapa — ślepa recenzja</span>
   <button class="pill" data-variant="candidate-amber" aria-pressed="true">Amber</button>
   <button class="pill" data-variant="candidate-blue" aria-pressed="false">Blue</button>
   <input class="control" id="search" type="search" placeholder="Szukaj tytułu lub ID" aria-label="Szukaj gry">
   <select class="control" id="parent" aria-label="Filtr regionu nadrzędnego"><option value="">Wszystkie regiony</option></select>
   <button class="control" id="reset">Reset widoku</button>
  </div>
  <svg id="map" role="img" aria-label="914 gier na projekcji UMAP"><g id="viewport"><g id="relations"></g><g id="points"></g></g></svg>
  <div class="tooltip" id="tooltip"></div>
  <div class="help">Kółko myszy: zoom · przeciągnięcie: pan · kliknięcie punktu: pełna karta</div>
 </section>
 <aside>
  <h1 id="variant-title"></h1>
  <p id="gate"></p>
  <div class="metrics" id="metrics"></div>
  <p>Kliknij klaster, aby go wyróżnić. Rodzina barw oznacza region nadrzędny.</p>
  <div id="clusters"></div>
  <section class="questions"><h2>Pytania pomocnicze</h2><p>To pytania recenzenckie, nie gotowe etykiety.</p><ul id="questions"></ul></section>
 </aside>
</main>
<script id="payload" type="application/json">__DATA__</script>
<script>
const data=JSON.parse(document.getElementById('payload').textContent);
const svg=document.getElementById('map'), viewport=document.getElementById('viewport'), pointLayer=document.getElementById('points'), relationLayer=document.getElementById('relations');
const tooltip=document.getElementById('tooltip'), search=document.getElementById('search'), parent=document.getElementById('parent');
let variantId='candidate-amber', selectedCluster='', scale=1, panX=0, panY=0, dragging=false, lastX=0,lastY=0;
const xs=data.points.map(p=>p.x), ys=data.points.map(p=>p.y), minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
const pad=.04, dx=maxX-minX,dy=maxY-minY;
const norm=p=>({x:40+920*((p.x-minX+dx*pad)/(dx*(1+2*pad))),y:40+920*(1-(p.y-minY+dy*pad)/(dy*(1+2*pad)))});
const pointById=new Map(data.points.map(p=>[p.id,p])); data.points.forEach(p=>p.pos=norm(p));
function variant(){return data.variants.find(v=>v.id===variantId)}
function number(id){return Number(id.split('-')[1])}
function color(a){const top=number(a.top),fine=number(a.fine);const hue=(top*47+fine%5*6)%360;const light=48+(fine%4)*6;return `hsl(${hue} 78% ${light}%)`}
function transform(){viewport.setAttribute('transform',`translate(${panX} ${panY}) scale(${scale})`)}
function setTooltip(event,p){const a=p.assignments[variantId];tooltip.innerHTML=`<strong>${escapeHtml(p.title)}</strong><div class="meta">${p.id} · ${escapeHtml(p.author||'autor nieustalony')} · ${p.year||'rok nieustalony'}<br>${escapeHtml(p.source)}<br>${a.top} / ${a.fine}</div><p>${escapeHtml(p.summary||'Brak krótkiego streszczenia.')}</p>`;tooltip.style.display='block';moveTooltip(event)}
function moveTooltip(event){tooltip.style.left=Math.min(event.clientX+16,window.innerWidth-380)+'px';tooltip.style.top=Math.min(event.clientY+16,window.innerHeight-190)+'px'}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function renderPoints(){pointLayer.replaceChildren();relationLayer.replaceChildren();const q=search.value.trim().toLocaleLowerCase('pl');const parentValue=parent.value;for(const p of data.points){const a=p.assignments[variantId];const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('cx',p.pos.x);circle.setAttribute('cy',p.pos.y);circle.setAttribute('r',selectedCluster===a.fine?5:3.15);circle.setAttribute('fill',color(a));circle.classList.add('point');const matches=!q||`${p.id} ${p.title} ${p.author} ${p.source}`.toLocaleLowerCase('pl').includes(q);const visible=matches&&(!selectedCluster||a.fine===selectedCluster)&&(!parentValue||a.top===parentValue);if(!visible)circle.classList.add('dim');if(q&&matches)circle.classList.add('match');circle.addEventListener('pointerenter',e=>setTooltip(e,p));circle.addEventListener('pointermove',moveTooltip);circle.addEventListener('pointerleave',()=>tooltip.style.display='none');circle.addEventListener('click',()=>window.open(p.url,'_blank','noopener'));pointLayer.append(circle)}
for(const relation of data.approvedRelations){const [a,b]=relation.activityIds.map(id=>pointById.get(id));if(!a||!b)continue;const line=document.createElementNS('http://www.w3.org/2000/svg','line');line.setAttribute('x1',a.pos.x);line.setAttribute('y1',a.pos.y);line.setAttribute('x2',b.pos.x);line.setAttribute('y2',b.pos.y);line.classList.add('relation');relationLayer.append(line)}}
function metric(label,value){return `<div class="metric"><span>${label}</span><b>${value}</b></div>`}
function renderSidebar(){const v=variant();document.getElementById('variant-title').textContent=`Wariant ${variantId.replace('candidate-','')}`;const gate=document.getElementById('gate');gate.className=v.eligible?'ok':'warning';gate.textContent=v.eligible?'Spełnia bramkę minimalnego rozmiaru.':'Uwaga: zawiera klaster mniejszy niż 5 gier.';const m=v.metrics;document.getElementById('metrics').innerHTML=metric('semantic silhouette',m.semanticSilhouette)+metric('visual silhouette',m.visualSilhouette)+metric('najmniejszy klaster',m.minimumFineClusterSize)+metric('minimalne ARI',m.minimumAdjustedRandIndex);
const parents=[...new Set(v.clusters.map(c=>c.parentId))].sort();const old=parent.value;parent.innerHTML='<option value="">Wszystkie regiony</option>'+parents.map(id=>`<option>${id}</option>`).join('');parent.value=parents.includes(old)?old:'';const wrap=document.getElementById('clusters');wrap.replaceChildren();for(const c of v.clusters){const div=document.createElement('div');div.className='cluster'+(selectedCluster===c.id?' active':'');const a={fine:c.id,top:c.parentId};div.innerHTML=`<div class="cluster-head"><span class="swatch" style="background:${color(a)}"></span><b>${c.id}</b><small>${c.parentId} · ${c.size} gier</small></div><ul>${c.central.map(p=>`<li>${escapeHtml(p.title)} <small>(${p.id})</small></li>`).join('')}</ul>`;div.addEventListener('click',()=>{selectedCluster=selectedCluster===c.id?'':c.id;renderSidebar();renderPoints()});wrap.append(div)}}
document.querySelectorAll('[data-variant]').forEach(button=>button.addEventListener('click',()=>{variantId=button.dataset.variant;selectedCluster='';document.querySelectorAll('[data-variant]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));renderSidebar();renderPoints()}));
search.addEventListener('input',renderPoints);parent.addEventListener('change',renderPoints);document.getElementById('reset').addEventListener('click',()=>{scale=1;panX=panY=0;selectedCluster='';search.value='';parent.value='';transform();renderSidebar();renderPoints()});
svg.setAttribute('viewBox','0 0 1000 1000');svg.addEventListener('wheel',e=>{e.preventDefault();const factor=e.deltaY<0?1.16:1/1.16;scale=Math.max(.6,Math.min(12,scale*factor));transform()},{passive:false});svg.addEventListener('pointerdown',e=>{dragging=true;lastX=e.clientX;lastY=e.clientY;svg.classList.add('dragging');svg.setPointerCapture(e.pointerId)});svg.addEventListener('pointermove',e=>{if(!dragging)return;const rect=svg.getBoundingClientRect();panX+=(e.clientX-lastX)*1000/rect.width;panY+=(e.clientY-lastY)*1000/rect.height;lastX=e.clientX;lastY=e.clientY;transform()});svg.addEventListener('pointerup',()=>{dragging=false;svg.classList.remove('dragging')});
document.getElementById('questions').innerHTML=data.expertQuestions.map(q=>`<li>${escapeHtml(q)}</li>`).join('');renderSidebar();renderPoints();
</script>
</body></html>
"""


def render_html(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    return HTML_TEMPLATE.replace("__DATA__", encoded)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build_payload()
    rendered = render_html(payload)
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"Hierarchy comparison HTML is missing or stale: {args.output}")
        print(f"Hierarchy comparison HTML is current: {len(payload['points'])} points")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output} ({len(payload['points'])} points, {len(payload['variants'])} variants)")


if __name__ == "__main__":
    main()
