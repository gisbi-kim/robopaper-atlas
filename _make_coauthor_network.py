"""공저자 네트워크 생성 — 공저 N회 이상 쌍을 엣지로.

출력:
  - _coauthor_network.json : {nodes, edges, meta}
  - _coauthor_network.html : d3-force 기반 인터랙티브 그래프

파라미터 (변수로 조절):
  MIN_AUTHOR_PAPERS : 각 저자가 최소 몇 편 이상 등장해야 노드로 남는지
  MIN_EDGE_COLLABS  : 두 저자가 최소 몇 번 공저해야 엣지로 남는지
"""
import collections
import html as htmllib
import json
import os
import re
from itertools import combinations

INPUT = 'all_enriched.json'
OUT_JSON = 'coauthor_network.json'
OUT_HTML = 'coauthor_network.html'

MIN_AUTHOR_PAPERS = 5
MIN_EDGE_COLLABS  = 5

_dblp = re.compile(r'\s+\d{4}$')
def clean_author(s):
    return _dblp.sub('', htmllib.unescape(s)).strip()

with open(INPUT, encoding='utf-8') as f:
    papers = json.load(f)

per_author = collections.Counter()  # author -> paper count
author_max_year = {}
paper_authors = []  # list of {authors, year}

for p in papers:
    a_str = (p.get('authors') or '').strip()
    if not a_str:
        continue
    authors = [clean_author(a) for a in a_str.split(';')]
    authors = [a for a in authors if a]
    if not authors:
        continue
    try:
        y = int(p.get('year') or 0)
    except (ValueError, TypeError):
        y = 0
    paper_authors.append((authors, y))
    per_author.update(authors)
    for a in authors:
        if y > author_max_year.get(a, 0):
            author_max_year[a] = y

eligible = {a for a, c in per_author.items() if c >= MIN_AUTHOR_PAPERS}
print(f'전체 고유 저자: {len(per_author):,}')
print(f'{MIN_AUTHOR_PAPERS}편 이상 저자: {len(eligible):,}')

pair_counts = collections.Counter()
for authors, _y in paper_authors:
    elig = sorted({a for a in authors if a in eligible})
    if len(elig) < 2:
        continue
    for a, b in combinations(elig, 2):
        pair_counts[(a, b)] += 1

edges_raw = [(a, b, c) for (a, b), c in pair_counts.items() if c >= MIN_EDGE_COLLABS]
print(f'edges (>= {MIN_EDGE_COLLABS} collab): {len(edges_raw):,}')

# Keep only authors that appear in at least one qualifying edge
nodes_set = {a for e in edges_raw for a in e[:2]}
print(f'connected authors: {len(nodes_set):,}')

# Build output
# Assign stable ids (index) for performance
author_to_id = {a: i for i, a in enumerate(sorted(nodes_set))}
nodes = [
    {
        'id': author_to_id[a],
        'label': a,
        'papers': per_author[a],
        'last_year': author_max_year.get(a, 0),
    }
    for a in sorted(nodes_set)
]
edges = [
    {'source': author_to_id[a], 'target': author_to_id[b], 'weight': w}
    for a, b, w in edges_raw
]

meta = {
    'min_author_papers': MIN_AUTHOR_PAPERS,
    'min_edge_collabs': MIN_EDGE_COLLABS,
    'total_authors_unique': len(per_author),
    'eligible_authors': len(eligible),
    'nodes': len(nodes),
    'edges': len(edges),
}

out = {'nodes': nodes, 'edges': edges, 'meta': meta}
with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False)
print(f'wrote {OUT_JSON} ({os.path.getsize(OUT_JSON)/1024/1024:.1f} MB)')

# --- Generate HTML with embedded data ---
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Co-authorship network — RoboPaper Atlas (local preview)</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; font-family: -apple-system, "Segoe UI", sans-serif; background: #0f1117; color: #e5e7eb; overflow: hidden; }
  canvas { display: block; background: #0f1117; }
  .panel {
    position: fixed; background: rgba(17, 24, 39, 0.92); color: #e5e7eb;
    border: 1px solid #374151; border-radius: 8px; padding: 12px 14px;
    font-size: 12.5px; backdrop-filter: blur(6px);
  }
  #info { top: 14px; left: 14px; max-width: 280px; }
  #info h1 { font-size: 15px; margin: 0 0 6px; font-weight: 600; color: #f3f4f6; }
  #info .meta { color: #9ca3af; font-size: 11px; margin-bottom: 8px; line-height: 1.6; }
  #info .controls { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
  #info button, #info select, #info input {
    font-size: 11px; padding: 4px 8px; background: #1f2937; color: #e5e7eb;
    border: 1px solid #374151; border-radius: 4px; cursor: pointer;
  }
  #info button:hover { background: #374151; }
  #selected { margin-top: 10px; padding-top: 8px; border-top: 1px solid #374151; min-height: 28px; }
  #selected .name { font-weight: 600; color: #38bdf8; font-size: 13px; }
  #selected .stat { color: #9ca3af; font-size: 11px; margin-top: 2px; }
  #search {
    width: 100%; padding: 5px 8px; font-size: 12px;
    background: #1f2937; color: #e5e7eb; border: 1px solid #374151;
    border-radius: 4px; outline: none;
  }
  #search:focus { border-color: #38bdf8; }
  #results { margin-top: 6px; max-height: 260px; overflow-y: auto; }
  .result-item {
    padding: 4px 8px; cursor: pointer; display: flex;
    justify-content: space-between; gap: 8px;
    border-radius: 3px; font-size: 12px;
  }
  .result-item:hover { background: #374151; }
  .result-item .count { color: #9ca3af; font-variant-numeric: tabular-nums; }
  .result-item.unconn { opacity: 0.5; }
  .result-item.unconn:hover { background: #2a1f1f; }

  .toggle-small {
    width: 100%; text-align: left;
    font-size: 12px; padding: 5px 8px;
    background: #1f2937; color: #e5e7eb;
    border: 1px solid #374151; border-radius: 4px; cursor: pointer;
  }
  .toggle-small:hover { background: #2d3748; }
  #hubs-list { max-height: 280px; overflow-y: auto; margin-top: 4px; }
  .hub-item {
    padding: 4px 6px; cursor: pointer; display: flex;
    align-items: baseline; gap: 6px; border-radius: 3px; font-size: 12px;
  }
  .hub-item:hover { background: #374151; }
  .hub-item .rank { color: #6b7280; font-size: 10px; min-width: 22px; text-align: right; }
  .hub-item .name { flex: 1; }
  .hub-item .count { color: #9ca3af; font-variant-numeric: tabular-nums; font-size: 11px; }
  #legend { bottom: 14px; left: 14px; font-size: 11px; color: #9ca3af; }
  #tooltip {
    position: fixed; background: #1f2937; color: #e5e7eb; padding: 8px 10px;
    border-radius: 4px; font-size: 12px; pointer-events: none;
    display: none; z-index: 100; max-width: 320px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
    border: 1px solid #374151;
  }
  #tooltip .tt-name { font-weight: 600; color: #f3f4f6; }
  #tooltip .tt-stat { color: #9ca3af; font-size: 11px; margin: 2px 0 5px; }
  #tooltip .tt-co { font-size: 11px; color: #cbd5e1; line-height: 1.55; }
  #tooltip .tt-co b { color: #38bdf8; font-weight: 500; }
  .slider-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
  .slider-row input[type="range"] { flex: 1; }
  .slider-row .val { font-variant-numeric: tabular-nums; min-width: 22px; text-align: right; color: #9ca3af; }
</style>
</head>
<body>
<canvas id="net"></canvas>
<div class="panel" id="info">
  <h1>Co-authorship network</h1>
  <div class="meta" id="meta-text"></div>
  <div class="slider-row">
    <span style="font-size:11px;">Edge threshold</span>
    <input type="range" id="edge-slider" min="__MIN_EDGE__" max="30" value="__MIN_EDGE__">
    <span class="val" id="edge-val">__MIN_EDGE__</span>
  </div>
  <div class="slider-row">
    <span style="font-size:11px;">Sparsity</span>
    <input type="range" id="sparsity-slider" min="1" max="10" step="0.5" value="3.5">
    <span class="val" id="sparsity-val">3.5</span>
  </div>
  <div class="controls">
    <button id="restart">Restart</button>
    <button id="freeze">Freeze</button>
    <button id="center">Center</button>
  </div>
  <div style="margin-top: 10px;">
    <input type="text" id="search" placeholder="Search author name…" autocomplete="off">
    <div id="results"></div>
  </div>
  <div style="margin-top: 10px;">
    <button id="btn-hubs" class="toggle-small">▸ Top 100 hubs (most co-authors)</button>
    <div id="hubs-list" style="display:none;"></div>
  </div>
  <div style="margin-top: 8px; font-size: 12px;">
    <label style="display: inline-flex; align-items: center; gap: 6px; cursor: pointer;">
      <input type="checkbox" id="show-degrees">
      Show 2nd/3rd degree connections
    </label>
    <div id="tier-legend" style="display:none; margin-top: 4px; font-size: 11px; color: #9ca3af;">
      <span style="color:#34d399;">● 1st</span>
      <span style="color:#818cf8; margin-left: 10px;">● 2nd</span>
      <span style="color:#f59e0b; margin-left: 10px;">● 3rd</span>
    </div>
  </div>
  <div id="selected"></div>
</div>
<div class="panel" id="legend">
  Node size = # papers · Edge thickness = # co-authored papers · Color = last-active year
  <br>Drag to pan · wheel to zoom · click node to pin · drag node to reposition
</div>
<div id="tooltip">
  <div class="tt-name" id="tt-name"></div>
  <div class="tt-stat" id="tt-stat"></div>
  <div class="tt-co" id="tt-co"></div>
</div>

<script>
const DATA = __DATA__;
const META = DATA.meta;

document.getElementById('meta-text').textContent =
  `${META.nodes.toLocaleString()} authors · ${META.edges.toLocaleString()} co-author pairs\n`
  + `(≥ ${META.min_author_papers} papers, ≥ ${META.min_edge_collabs} collabs)`;

const canvas = document.getElementById('net');
const ctx = canvas.getContext('2d');
let width = canvas.width = window.innerWidth;
let height = canvas.height = window.innerHeight;

// --- Build working data (copies we can filter on) ---
const allNodes = DATA.nodes.map(d => ({ ...d }));
const allEdges = DATA.edges.map(d => ({ ...d }));
let nodes = allNodes.slice();
let edges = allEdges.slice();
let nodeById = new Map(nodes.map(n => [n.id, n]));
edges.forEach(e => { e.source = nodeById.get(e.source); e.target = nodeById.get(e.target); });

// Year color scale (blue old → orange recent)
const years = nodes.map(n => n.last_year).filter(y => y > 0);
const yMin = Math.min(...years), yMax = Math.max(...years);
const colorScale = d3.scaleSequential(d3.interpolateInferno).domain([yMin - 5, yMax]);

const rScale = d3.scaleSqrt()
  .domain([d3.min(nodes, d => d.papers), d3.max(nodes, d => d.papers)])
  .range([2, 14]);
const eScale = d3.scaleLog()
  .domain([META.min_edge_collabs, d3.max(edges, d => d.weight) || 10])
  .range([0.3, 3]);

// --- Adjacency for fast BFS (tier computation) ---
let adjacency = new Map();
function buildAdjacency() {
  adjacency.clear();
  for (const n of nodes) adjacency.set(n, []);
  for (const e of edges) {
    adjacency.get(e.source).push(e.target);
    adjacency.get(e.target).push(e.source);
  }
}
buildAdjacency();

let showDegrees = false;
let edgeTier = new Map();  // edge -> 1|2|3 (only for edges within current radius of selectedNode)

function recomputeEdgeTiers() {
  edgeTier.clear();
  if (!selectedNode) return;
  const maxHop = showDegrees ? 3 : 1;
  // BFS distances from selectedNode
  const dist = new Map();
  dist.set(selectedNode, 0);
  const queue = [selectedNode];
  while (queue.length) {
    const n = queue.shift();
    const d = dist.get(n);
    if (d >= maxHop) continue;
    for (const other of (adjacency.get(n) || [])) {
      if (dist.has(other)) continue;
      dist.set(other, d + 1);
      queue.push(other);
    }
  }
  for (const e of edges) {
    const ds = dist.get(e.source), dt = dist.get(e.target);
    if (ds === undefined || dt === undefined) continue;
    const tier = Math.max(ds, dt);
    if (tier >= 1 && tier <= 3) edgeTier.set(e, tier);
  }
}

// --- Force simulation ---
let sparsity = 3.5;  // controls overall spread (repulsion & link distance)
const CHARGE_BASE = -14;   // multiplied by sparsity
const LINK_BASE = 30;
const LINK_WEIGHT_INV = 70;

function linkDistance(d) {
  return LINK_BASE + LINK_WEIGHT_INV / d.weight * Math.sqrt(sparsity);
}

let simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(edges).id(d => d.id).distance(linkDistance).strength(0.35))
  .force('charge', d3.forceManyBody().strength(CHARGE_BASE * sparsity))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collide', d3.forceCollide().radius(d => rScale(d.papers) + 2))
  .on('tick', draw);

function applySparsity(s) {
  sparsity = s;
  simulation.force('charge').strength(CHARGE_BASE * s);
  simulation.force('link').distance(linkDistance);
  simulation.alpha(0.4).restart();
}

// --- View transform (pan/zoom) ---
let transform = d3.zoomIdentity;
const zoom = d3.zoom().scaleExtent([0.02, 8]).on('zoom', (e) => {
  transform = e.transform;
  draw();
});
d3.select(canvas).call(zoom);

function draw() {
  ctx.save();
  ctx.clearRect(0, 0, width, height);
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  // Edges — if no selection: all gray. If selection: gray (non-tier) then 3rd/2nd/1st.
  ctx.lineCap = 'round';
  // Zoom-adaptive width: when zoomed out (k<1), thicken lines so they stay visible.
  const wMult = Math.max(1, 1 / transform.k);
  const TIER_STYLE = {
    1: { color: '#34d399', alpha: 1.0,  w: 2.4 },  // emerald — most salient
    2: { color: '#818cf8', alpha: 0.85, w: 1.5 },  // indigo — medium
    3: { color: '#f59e0b', alpha: 0.45, w: 0.9 },  // amber (yellow-orange) — distant
  };
  if (!selectedNode) {
    ctx.strokeStyle = 'rgba(156, 163, 175, 0.35)';
    for (const e of edges) {
      ctx.beginPath();
      ctx.lineWidth = eScale(e.weight) * wMult;
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.stroke();
    }
  } else {
    // background (untiered) edges, dimmer so tiers stand out
    ctx.strokeStyle = 'rgba(156, 163, 175, 0.15)';
    for (const e of edges) {
      if (edgeTier.has(e)) continue;
      ctx.beginPath();
      ctx.lineWidth = eScale(e.weight) * wMult;
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.stroke();
    }
    // 3rd, then 2nd, then 1st (1st drawn on top = most prominent)
    for (const tier of [3, 2, 1]) {
      const s = TIER_STYLE[tier];
      ctx.globalAlpha = s.alpha;
      ctx.strokeStyle = s.color;
      for (const e of edges) {
        if (edgeTier.get(e) !== tier) continue;
        ctx.beginPath();
        ctx.lineWidth = eScale(e.weight) * s.w * wMult;
        ctx.moveTo(e.source.x, e.source.y);
        ctx.lineTo(e.target.x, e.target.y);
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }

  // Nodes
  for (const n of nodes) {
    ctx.beginPath();
    ctx.arc(n.x, n.y, rScale(n.papers), 0, Math.PI * 2);
    ctx.fillStyle = n.last_year > 0 ? colorScale(n.last_year) : '#888';
    ctx.fill();
    if (n === selectedNode) {
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2 / transform.k;
      ctx.stroke();
    }
  }

  // Labels for large nodes only
  if (transform.k > 0.8) {
    ctx.font = `${Math.max(9, 10 / transform.k * 1.2)}px -apple-system, sans-serif`;
    ctx.fillStyle = 'rgba(229, 231, 235, 0.85)';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const n of nodes) {
      if (n.papers < 20 && transform.k < 1.6) continue;
      if (transform.k > 2 || n.papers >= 30 || n === selectedNode) {
        ctx.fillText(n.label, n.x, n.y + rScale(n.papers) + 2);
      }
    }
  }
  ctx.restore();
}

// --- Interaction ---
let selectedNode = null;
let draggingNode = null;

function nodeAtScreen(sx, sy) {
  const x = (sx - transform.x) / transform.k;
  const y = (sy - transform.y) / transform.k;
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i];
    const r = rScale(n.papers) + 1.5;
    if ((n.x - x) ** 2 + (n.y - y) ** 2 < r * r) return n;
  }
  return null;
}

const tipEl = document.getElementById('tooltip');
const ttName = document.getElementById('tt-name');
const ttStat = document.getElementById('tt-stat');
const ttCo = document.getElementById('tt-co');

function collectCoauthors(n) {
  const co = [];
  for (const e of edges) {
    const other = e.source === n ? e.target : (e.target === n ? e.source : null);
    if (other) co.push({ name: other.label, w: e.weight });
  }
  co.sort((a, b) => b.w - a.w);
  return co;
}

canvas.addEventListener('mousemove', (e) => {
  const n = nodeAtScreen(e.clientX, e.clientY);
  if (n) {
    canvas.style.cursor = 'pointer';
    ttName.textContent = n.label;
    ttStat.textContent = `${n.papers} papers · last active ${n.last_year}`;
    const co = collectCoauthors(n);
    if (co.length) {
      const top = co.slice(0, 10);
      ttCo.innerHTML = `<b>Co-authors (${co.length}):</b> `
        + top.map(c => `${c.name} (${c.w})`).join(', ')
        + (co.length > 10 ? `, … +${co.length - 10} more` : '');
    } else {
      ttCo.textContent = '';
    }
    // Position: keep within viewport
    let x = e.clientX + 12, y = e.clientY + 12;
    const w = tipEl.offsetWidth || 320, h = tipEl.offsetHeight || 80;
    if (x + w > window.innerWidth - 8)  x = e.clientX - w - 12;
    if (y + h > window.innerHeight - 8) y = e.clientY - h - 12;
    tipEl.style.left = x + 'px';
    tipEl.style.top = y + 'px';
    tipEl.style.display = 'block';
  } else {
    canvas.style.cursor = 'grab';
    tipEl.style.display = 'none';
  }
});
canvas.addEventListener('mouseleave', () => { tipEl.style.display = 'none'; });

function updateSelectedPanel(n) {
  const box = document.getElementById('selected');
  if (!n) { box.innerHTML = ''; return; }
  const neighbors = edges.filter(x => x.source === n || x.target === n).length;
  box.innerHTML = `<div class="name">${n.label}</div>`
    + `<div class="stat">${n.papers} papers · ${neighbors} co-authors in view · last ${n.last_year}</div>`;
}

function centerOnNode(n, scale = 1.8) {
  selectedNode = n;
  updateSelectedPanel(n);
  recomputeEdgeTiers();
  const tx = width / 2 - n.x * scale;
  const ty = height / 2 - n.y * scale;
  d3.select(canvas).transition().duration(500)
    .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
}

canvas.addEventListener('click', (e) => {
  const n = nodeAtScreen(e.clientX, e.clientY);
  selectedNode = n;
  updateSelectedPanel(n);
  recomputeEdgeTiers();
  draw();
});

// --- Search ---
const searchInput = document.getElementById('search');
const resultsDiv = document.getElementById('results');

searchInput.addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  if (!q) { resultsDiv.innerHTML = ''; return; }
  const visibleIds = new Set(nodes.map(n => n.id));
  const matches = allNodes
    .filter(n => n.label.toLowerCase().includes(q))
    .sort((a, b) => b.papers - a.papers)
    .slice(0, 25);
  if (matches.length === 0) {
    resultsDiv.innerHTML = '<div style="color:#888; padding:4px 8px; font-size:12px;">No matches</div>';
    return;
  }
  resultsDiv.innerHTML = matches.map(n => {
    const connected = visibleIds.has(n.id);
    const cls = connected ? 'result-item' : 'result-item unconn';
    const title = connected ? '' : ' title="Not in current view — try lowering edge threshold"';
    return `<div class="${cls}" data-id="${n.id}"${title}>`
      + `<span>${n.label}</span><span class="count">${n.papers}</span></div>`;
  }).join('');
});

searchInput.addEventListener('keyup', (e) => {
  if (e.key === 'Enter') {
    const first = resultsDiv.querySelector('.result-item');
    if (first) first.click();
  }
});

resultsDiv.addEventListener('click', (e) => {
  const item = e.target.closest('.result-item');
  if (!item) return;
  const id = parseInt(item.dataset.id);
  const node = nodes.find(n => n.id === id);
  if (!node) {
    alert('This author is not in the current view. Lower the edge threshold to include them.');
    return;
  }
  centerOnNode(node);
});

// --- Top 100 hubs toggle ---
const btnHubs = document.getElementById('btn-hubs');
const hubsList = document.getElementById('hubs-list');

function populateHubs() {
  const degree = new Map();
  const weighted = new Map();
  for (const n of nodes) { degree.set(n.id, 0); weighted.set(n.id, 0); }
  for (const e of edges) {
    degree.set(e.source.id, degree.get(e.source.id) + 1);
    degree.set(e.target.id, degree.get(e.target.id) + 1);
    weighted.set(e.source.id, weighted.get(e.source.id) + e.weight);
    weighted.set(e.target.id, weighted.get(e.target.id) + e.weight);
  }
  const ranked = nodes.slice()
    .sort((a, b) => degree.get(b.id) - degree.get(a.id))
    .slice(0, 100);
  hubsList.innerHTML = ranked.map((n, i) =>
    `<div class="hub-item" data-id="${n.id}" title="${weighted.get(n.id)} total collaborations">`
    + `<span class="rank">${i + 1}</span>`
    + `<span class="name">${n.label}</span>`
    + `<span class="count">${degree.get(n.id)}</span>`
    + `</div>`
  ).join('');
}

btnHubs.addEventListener('click', () => {
  const show = hubsList.style.display === 'none';
  if (show) {
    populateHubs();
    hubsList.style.display = 'block';
    btnHubs.textContent = '▾ Top 100 hubs (most co-authors)';
  } else {
    hubsList.style.display = 'none';
    btnHubs.textContent = '▸ Top 100 hubs (most co-authors)';
  }
});

hubsList.addEventListener('click', (e) => {
  const item = e.target.closest('.hub-item');
  if (!item) return;
  const id = parseInt(item.dataset.id);
  const node = nodes.find(n => n.id === id);
  if (node) centerOnNode(node);
});

// Drag node
d3.select(canvas).call(d3.drag()
  .container(canvas)
  .subject((event) => nodeAtScreen(event.sourceEvent.clientX, event.sourceEvent.clientY))
  .filter((event) => nodeAtScreen(event.clientX, event.clientY))
  .on('start', (event) => { if (!event.active) simulation.alphaTarget(0.3).restart(); event.subject.fx = event.subject.x; event.subject.fy = event.subject.y; })
  .on('drag', (event) => { event.subject.fx = (event.x - transform.x) / transform.k; event.subject.fy = (event.y - transform.y) / transform.k; })
  .on('end', (event) => { if (!event.active) simulation.alphaTarget(0); event.subject.fx = null; event.subject.fy = null; })
);

// --- Buttons ---
const INITIAL_SPARSITY = 3.5;
let frozen = false;

function fullReset() {
  // Clear user state
  selectedNode = null;
  frozen = false;
  showDegrees = false;
  document.getElementById('show-degrees').checked = false;
  document.getElementById('tier-legend').style.display = 'none';
  document.getElementById('selected').innerHTML = '';
  edgeTier.clear();

  // Reset search + hubs panels
  searchInput.value = '';
  resultsDiv.innerHTML = '';
  hubsList.style.display = 'none';
  btnHubs.textContent = '▸ Top 100 hubs (most co-authors)';

  // Reset sliders to defaults
  slider.value = META.min_edge_collabs;
  sliderVal.textContent = META.min_edge_collabs;
  sparsitySlider.value = INITIAL_SPARSITY;
  sparsityVal.textContent = INITIAL_SPARSITY;
  sparsity = INITIAL_SPARSITY;

  // Reset graph to full unfiltered
  edges = allEdges.map(d => ({ source: d.source, target: d.target, weight: d.weight }));
  nodes = allNodes.slice();
  // Rebind source/target references to node objects
  edges.forEach(e => {
    if (typeof e.source !== 'object') e.source = nodeById.get(e.source);
    if (typeof e.target !== 'object') e.target = nodeById.get(e.target);
  });

  // Scramble initial positions so layout forms fresh
  for (const n of nodes) {
    n.fx = null; n.fy = null;
    n.x = width / 2 + (Math.random() - 0.5) * 200;
    n.y = height / 2 + (Math.random() - 0.5) * 200;
    n.vx = 0; n.vy = 0;
  }

  buildAdjacency();

  simulation.nodes(nodes);
  simulation.force('link').links(edges).distance(linkDistance);
  simulation.force('charge').strength(CHARGE_BASE * sparsity);
  simulation.force('center', d3.forceCenter(width / 2, height / 2));
  simulation.alpha(1).restart();

  // Reset zoom
  d3.select(canvas).transition().duration(450)
    .call(zoom.transform, d3.zoomIdentity);

  document.getElementById('freeze').textContent = 'Freeze';
}

document.getElementById('restart').onclick = fullReset;
document.getElementById('freeze').onclick = () => {
  frozen = !frozen;
  if (frozen) { simulation.stop(); document.getElementById('freeze').textContent = 'Resume'; }
  else { simulation.alpha(0.3).restart(); document.getElementById('freeze').textContent = 'Freeze'; }
};
document.getElementById('center').onclick = () => {
  d3.select(canvas).transition().duration(400).call(zoom.transform, d3.zoomIdentity);
};

// Edge threshold slider — filter edges on the fly
const slider = document.getElementById('edge-slider');
const sliderVal = document.getElementById('edge-val');
slider.oninput = (e) => {
  const th = parseInt(e.target.value);
  sliderVal.textContent = th;
  edges = allEdges.filter(d => d.weight >= th).map(d => ({ ...d }));
  edges.forEach(e => { e.source = nodeById.get(typeof e.source === 'object' ? e.source.id : e.source); e.target = nodeById.get(typeof e.target === 'object' ? e.target.id : e.target); });
  // Keep connected subset only
  const used = new Set();
  edges.forEach(e => { used.add(e.source.id); used.add(e.target.id); });
  nodes = allNodes.filter(n => used.has(n.id));
  nodes.forEach(n => { n.x = nodeById.get(n.id).x; n.y = nodeById.get(n.id).y; });
  simulation.nodes(nodes);
  simulation.force('link').links(edges);
  simulation.alpha(0.4).restart();
  buildAdjacency();
  recomputeEdgeTiers();
  // Refresh hub list if open (degrees change with threshold)
  if (hubsList.style.display === 'block') populateHubs();
};

// Checkbox: show 2nd/3rd degree connections
document.getElementById('show-degrees').addEventListener('change', (e) => {
  showDegrees = e.target.checked;
  document.getElementById('tier-legend').style.display = showDegrees ? 'block' : 'none';
  recomputeEdgeTiers();
  draw();
});

// Sparsity slider: controls how "exploded" the graph is
const sparsitySlider = document.getElementById('sparsity-slider');
const sparsityVal = document.getElementById('sparsity-val');
sparsitySlider.oninput = (e) => {
  const s = parseFloat(e.target.value);
  sparsityVal.textContent = s;
  applySparsity(s);
};

window.addEventListener('resize', () => {
  width = canvas.width = window.innerWidth;
  height = canvas.height = window.innerHeight;
  simulation.force('center', d3.forceCenter(width / 2, height / 2));
  simulation.alpha(0.3).restart();
});
</script>
</body>
</html>
"""

html_out = (HTML
            .replace('__DATA__', json.dumps(out, ensure_ascii=False))
            .replace('__MIN_EDGE__', str(MIN_EDGE_COLLABS)))

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html_out)
print(f'wrote {OUT_HTML} ({os.path.getsize(OUT_HTML)/1024/1024:.1f} MB)')
