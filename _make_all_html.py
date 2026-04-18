"""전체 논문 시각화 HTML 생성 (ICRA·IROS·RA-L, 필터·정렬·페이지네이션, DOI dedup)"""
import json
import html
import os
import re
from datetime import datetime
import pandas as pd

VENUE_PRIORITY = {'T-RO': 0, 'RA-L': 1, 'RSS': 2, 'ICRA': 3, 'IROS': 4}

# 인용수 기준일: all_enriched.json의 mtime (step2 마지막 실행일)
try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime('all_enriched.json')).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()

with open('all_enriched.json', encoding='utf-8') as f:
    papers = json.load(f)
df = pd.DataFrame(papers)
slim = df[['venue', 'year', 'title', 'authors', 'cited_by_count', 'doi']].copy()
slim['title'] = (slim['title'].fillna('').astype(str).map(html.unescape)
                 .str.rstrip('.').str.strip().str[:300])
# DBLP 동명이인 식별자 ("0001" 등) 제거 + HTML 엔티티 디코딩
_dblp_suffix = re.compile(r'\s+\d{4}$')
def _clean_authors(s):
    return '; '.join(_dblp_suffix.sub('', a.strip()) for a in html.unescape(str(s)).split(';') if a.strip())
slim['authors'] = slim['authors'].fillna('').astype(str).map(_clean_authors).str[:300]
slim['doi'] = slim['doi'].fillna('').astype(str).str.strip().str.lower()
slim['doi'] = slim['doi'].str.replace(r'^https?://doi\.org/', '', regex=True)
slim['cited_by_count'] = pd.to_numeric(slim['cited_by_count'], errors='coerce').fillna(0).astype(int)
slim['year'] = pd.to_numeric(slim['year'], errors='coerce').fillna(0).astype(int)

before = len(slim)
slim = slim[slim['authors'].str.strip() != ''].reset_index(drop=True)
print(f"proceedings 표제 제외: {before - len(slim)}건")

# DOI 기반 dedup (RA-L > ICRA > IROS 우선순위)
before = len(slim)
with_doi = slim[slim['doi'] != ''].copy()
without_doi = slim[slim['doi'] == ''].copy()
with_doi['_pri'] = with_doi['venue'].map(VENUE_PRIORITY).fillna(99).astype(int)
with_doi = with_doi.sort_values(['doi', '_pri'])
venues_per_doi = with_doi.groupby('doi')['venue'].apply(
    lambda s: ','.join(sorted(set(s), key=lambda v: VENUE_PRIORITY.get(v, 99)))
)
with_doi = with_doi.drop_duplicates(subset=['doi'], keep='first').drop(columns=['_pri'])
with_doi['venues_all'] = with_doi['doi'].map(venues_per_doi)
without_doi['venues_all'] = without_doi['venue']
slim = pd.concat([with_doi, without_doi], ignore_index=True)
print(f"DOI dedup: {before} → {len(slim)} ({before - len(slim)}건 병합)")

# 제목+연도 기반 추가 dedup (DOI는 다르지만 같은 논문이 RA-L과 ICRA/IROS에 교차 게재)
def _norm_title(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())
before = len(slim)
slim['_tn'] = slim['title'].map(_norm_title)
short = slim['_tn'].str.len() < 20  # "Editorial" 같은 짧은 제목은 제외
pool = slim[~short].copy()
keep = slim[short].copy()
pool['_pri'] = pool['venue'].map(VENUE_PRIORITY).fillna(99).astype(int)
pool = pool.sort_values(['_tn', 'year', '_pri'])
combined = pool.groupby(['_tn', 'year'])['venues_all'].apply(
    lambda s: ','.join(sorted(set(v for row in s for v in str(row).split(',')), key=lambda v: VENUE_PRIORITY.get(v, 99)))
)
pool = pool.drop_duplicates(subset=['_tn', 'year'], keep='first').drop(columns=['_pri'])
pool['venues_all'] = pool.set_index(['_tn', 'year']).index.map(combined)
slim = pd.concat([pool, keep], ignore_index=True).drop(columns=['_tn'])
print(f"제목+연도 dedup: {before} → {len(slim)} ({before - len(slim)}건 병합)")

arr = [[r['venue'], r['year'], r['title'], r['authors'], r['cited_by_count'], r['doi'], r['venues_all']]
       for r in slim.to_dict('records')]

total = len(arr)
year_min = int(slim['year'].min())
year_max = int(slim['year'].max())

# Word book (초록 단어 cloud용) — slim embed: 논문당 top 15
WB_TOP_PER_PAPER_EMBED = 15
try:
    with open('word_book.json', encoding='utf-8') as f:
        wb = json.load(f)
    wb_vocab = wb['vocab']
    wb_papers_slim = {doi: idx_list[:WB_TOP_PER_PAPER_EMBED]
                      for doi, idx_list in wb['papers'].items()}
    print(f"word_book: {len(wb_vocab):,} vocab, {len(wb_papers_slim):,} papers")
except FileNotFoundError:
    print("warning: word_book.json not found — run _make_word_book.py first")
    wb_vocab = []
    wb_papers_slim = {}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ICRA / IROS / RA-L / T-RO / RSS Paper Explorer</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/wordcloud@1.2.2/src/wordcloud2.js"></script>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 20px; background: #fafafa; color: #222; }
  .brand { font-size: 12px; letter-spacing: 0.5px; color: #888; margin-bottom: 4px; }
  .brand a { color: inherit; text-decoration: none; font-weight: 600; }
  .brand a:hover { color: #1f77b4; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: #666; font-size: 13px; margin-bottom: 16px; }
  .stat-line { display: flex; gap: 28px; font-size: 13px; color: #555; margin: 8px 0 14px; flex-wrap: wrap; }
  .stat-line b { color: #222; font-size: 16px; font-variant-numeric: tabular-nums; margin-left: 6px; font-weight: 700; }
  .wrap { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; }
  h2 { font-size: 14px; margin: 0 0 10px; color: #333; }
  canvas { max-height: 340px; }

  .summary { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .card { flex: 1; min-width: 120px; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 10px 14px; }
  .card .num { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
  .card .label { color: #666; font-size: 11px; margin-top: 2px; }

  .controls { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
  .controls label { font-size: 13px; color: #555; display: inline-flex; align-items: center; gap: 6px; }
  .controls input[type="number"] { width: 78px; padding: 4px 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
  .controls input[type="text"] { padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; min-width: 180px; }
  .controls button { border: 1px solid #ccc; background: #fff; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; }
  .controls button:hover { background: #f4f4f4; }
  .controls .reset { color: #c33; }

  .result-info { font-size: 12px; color: #666; margin: 8px 0 10px; }

  table { width: 100%; border-collapse: collapse; font-size: 12px; table-layout: fixed; }
  th, td { border-bottom: 1px solid #eee; padding: 5px 8px; vertical-align: top; overflow: hidden; text-overflow: ellipsis; }
  th { background: #f4f4f4; font-weight: 600; text-align: left; cursor: pointer; user-select: none; white-space: nowrap; }
  th:hover { background: #ebebeb; }
  th.sorted { background: #e0ebf5; }
  th .arrow { font-size: 10px; color: #1f77b4; margin-left: 4px; }

  col.col-rank { width: 52px; }
  col.col-venue { width: 110px; }
  col.col-year { width: 56px; }
  col.col-cites { width: 72px; }
  col.col-title { width: auto; }
  col.col-authors { width: 230px; }

  td.rank, td.cites, td.year { text-align: right; font-variant-numeric: tabular-nums; }
  td.cites { font-weight: 600; }
  td.rank { color: #999; }
  .venue-ICRA { color: #1f77b4; font-weight: 600; }
  .venue-IROS { color: #ff7f0e; font-weight: 600; }
  .venue-RAL  { color: #2ca02c; font-weight: 600; }
  .venue-TRO  { color: #d62728; font-weight: 600; }
  .venue-RSS  { color: #9467bd; font-weight: 600; }
  .venue-also { color: #888; font-weight: 400; font-size: 10px; }
  td.authors { color: #555; font-size: 11px; white-space: nowrap; }
  a { color: inherit; text-decoration: none; }
  a:hover { text-decoration: underline; color: #1f77b4; }
  a[data-doi] { border-bottom: 1px dotted #bbb; }
  a[data-doi]:hover { border-bottom: 1px solid #1f77b4; text-decoration: none; }

  #abstract-tooltip {
    position: fixed; display: none; background: #fff;
    border: 1px solid #ccc; border-radius: 6px;
    padding: 12px 14px; max-width: 480px; min-width: 280px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.15);
    font-size: 12.5px; line-height: 1.55; color: #333;
    z-index: 1000; pointer-events: none;
  }
  #abstract-tooltip .tt-head {
    font-size: 11px; color: #888; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 6px;
  }
  #abstract-tooltip em { color: #999; font-style: italic; }

  .pager { display: flex; gap: 8px; align-items: center; justify-content: flex-end; margin-top: 10px; font-size: 13px; flex-wrap: wrap; }
  .pager button { border: 1px solid #ccc; background: #fff; padding: 4px 10px; border-radius: 4px; cursor: pointer; }
  .pager button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
</head>
<body>

<div class="brand"><a href="index.html">RoboPaper Atlas</a></div>
<h1>ICRA / IROS / RA-L / T-RO / RSS Paper Explorer</h1>
<div class="sub">
  DBLP + OpenAlex · __TOTAL_FMT__ papers (DOI-deduped) · __YMIN__ ~ __YMAX__ · Filter · Sort · Search
  <span style="float:right; color:#888;">Citations as of __AS_OF__</span>
</div>

<div class="summary">
  <div class="card"><div class="num" id="c-total">-</div><div class="label">Total</div></div>
  <div class="card"><div class="num" id="c-icra">-</div><div class="label">ICRA</div></div>
  <div class="card"><div class="num" id="c-iros">-</div><div class="label">IROS</div></div>
  <div class="card"><div class="num" id="c-ral">-</div><div class="label">RA-L</div></div>
  <div class="card"><div class="num" id="c-tro">-</div><div class="label">T-RO</div></div>
  <div class="card"><div class="num" id="c-rss">-</div><div class="label">RSS</div></div>
  <div class="card"><div class="num" id="c-maxcite">-</div><div class="label">Max citations</div></div>
  <div class="card"><div class="num" id="c-meancite">-</div><div class="label">Mean citations</div></div>
</div>

<div class="wrap">
  <h2>Filters</h2>
  <div class="controls">
    <label>Year
      <input type="number" id="f-year-from" min="__YMIN__" max="__YMAX__" value="__YMIN__">
      ~
      <input type="number" id="f-year-to" min="__YMIN__" max="__YMAX__" value="__YMAX__">
    </label>
    <label><input type="checkbox" id="f-icra" checked> ICRA</label>
    <label><input type="checkbox" id="f-iros" checked> IROS</label>
    <label><input type="checkbox" id="f-ral" checked> RA-L</label>
    <label><input type="checkbox" id="f-tro" checked> T-RO</label>
    <label><input type="checkbox" id="f-rss" checked> RSS</label>
    <label>Min citations
      <input type="number" id="f-mincite" min="0" value="0">
    </label>
    <label>Search
      <input type="text" id="f-search" placeholder="Title or author">
    </label>
    <button id="btn-apply">Apply</button>
    <button id="btn-reset" class="reset">Reset</button>
  </div>
  <div class="result-info" id="result-info"></div>
</div>

<div class="wrap">
  <h2>Papers per year (stacked ICRA / IROS / RA-L / T-RO / RSS, filtered)</h2>
  <canvas id="chart-bar"></canvas>
</div>

<div class="wrap">
  <h2>Year × Citations (max 5,000 points; top-cited sampled if more)</h2>
  <canvas id="chart-scatter"></canvas>
</div>

<div class="wrap">
  <h2>Word cloud
    <span style="font-weight:normal; color:#888; font-size:12px;">
      top terms across the abstracts of the current filter — pick an author + year range to see what they write about
    </span>
  </h2>
  <canvas id="wordcloud" style="width: 100%; height: 380px; display: block; background: #fff; border-radius: 4px;"></canvas>
  <div style="color:#888; font-size:11px; margin-top: 6px;" id="wc-note"></div>
</div>

<div class="wrap">
  <h2>Citation stats
    <span style="font-weight:normal; color:#888; font-size:12px;">
      computed on the current filter result — respects year range, venue selection, min-citations, and search
    </span>
  </h2>
  <div class="stat-line">
    <span>h-index <b id="stat-h">-</b></span>
    <span>i10-index <b id="stat-i10">-</b></span>
    <span>median <b id="stat-median">-</b></span>
    <span>std dev <b id="stat-std">-</b></span>
  </div>
  <div style="color:#888; font-size:11px; margin: 0 0 8px;">
    Tip: search an author name and narrow the year range to see that author's stats for the chosen period only.
  </div>
  <canvas id="chart-hist" style="max-height: 220px;"></canvas>
</div>

<div class="wrap">
  <h2>
    Paper list
    <span style="font-weight:normal; color:#888; font-size:12px;">(click column header to sort · "also:..." = same paper also listed in that venue)</span>
  </h2>
  <table>
    <colgroup>
      <col class="col-rank"><col class="col-venue"><col class="col-year">
      <col class="col-title"><col class="col-authors"><col class="col-cites">
    </colgroup>
    <thead>
      <tr>
        <th>#</th>
        <th data-sort="venue">Venue<span class="arrow"></span></th>
        <th data-sort="year">Year<span class="arrow"></span></th>
        <th data-sort="title">Title<span class="arrow"></span></th>
        <th data-sort="authors">Authors<span class="arrow"></span></th>
        <th data-sort="cites">Cites<span class="arrow"></span></th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  <div class="pager">
    <span id="page-info"></span>
    <label>per page
      <select id="page-size">
        <option>50</option><option selected>100</option><option>200</option><option>500</option>
      </select>
    </label>
    <button id="page-first">« First</button>
    <button id="page-prev">‹ Prev</button>
    <button id="page-next">Next ›</button>
    <button id="page-last">Last »</button>
  </div>
</div>

<script>
// columns: [venue, year, title, authors, cites, doi, venues_all]
const ALL = __ARR_JSON__;
const WB_VOCAB = __WB_VOCAB__;
const WB_PAPERS = __WB_PAPERS__;
const KEYS = { venue: 0, year: 1, title: 2, authors: 3, cites: 4, doi: 5 };
const YMIN = __YMIN__, YMAX = __YMAX__;

const VENUE_COLOR = { 'ICRA': '#1f77b4', 'IROS': '#ff7f0e', 'RA-L': '#2ca02c', 'T-RO': '#d62728', 'RSS': '#9467bd' };
const VENUES = ['ICRA', 'IROS', 'RA-L', 'T-RO', 'RSS'];

const state = {
  yearFrom: YMIN, yearTo: YMAX,
  venueFilter: { 'ICRA': true, 'IROS': true, 'RA-L': true, 'T-RO': true, 'RSS': true },
  minCite: 0,
  search: '',
  sortKey: 'cites', sortDesc: true,
  page: 1, pageSize: 100,
  filtered: [],
};

let barChart, scatterChart, histChart;

function hIndex(cites) {
  const s = cites.slice().sort((a, b) => b - a);
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    if (s[i] >= i + 1) h = i + 1;
    else break;
  }
  return h;
}
function i10Index(cites) { return cites.filter(c => c >= 10).length; }
function median(sorted) {
  const n = sorted.length;
  if (n === 0) return 0;
  return n % 2 === 0 ? (sorted[n/2 - 1] + sorted[n/2]) / 2 : sorted[Math.floor(n/2)];
}
function stdDev(vals, mean) {
  if (vals.length < 2) return 0;
  let s = 0;
  for (const v of vals) s += (v - mean) ** 2;
  return Math.sqrt(s / (vals.length - 1));
}

const HIST_LABELS = ['0', '1-9', '10-49', '50-99', '100-499', '500-999', '1000-4999', '5000+'];
function citeBin(c) {
  if (c === 0) return 0;
  if (c < 10) return 1;
  if (c < 50) return 2;
  if (c < 100) return 3;
  if (c < 500) return 4;
  if (c < 1000) return 5;
  if (c < 5000) return 6;
  return 7;
}

function filterAndSort() {
  const q = state.search.trim().toLowerCase();
  const out = [];
  for (let i = 0; i < ALL.length; i++) {
    const r = ALL[i];
    if (r[1] < state.yearFrom || r[1] > state.yearTo) continue;
    if (!state.venueFilter[r[0]]) continue;
    if (r[4] < state.minCite) continue;
    if (q && !(r[2].toLowerCase().includes(q) || r[3].toLowerCase().includes(q))) continue;
    out.push(r);
  }
  const k = KEYS[state.sortKey];
  const dir = state.sortDesc ? -1 : 1;
  out.sort((a, b) => {
    const va = a[k], vb = b[k];
    if (va < vb) return -1 * dir;
    if (va > vb) return 1 * dir;
    return 0;
  });
  state.filtered = out;
  state.page = 1;
}

function renderStats() {
  const f = state.filtered;
  document.getElementById('c-total').textContent = f.length.toLocaleString();
  const counts = { 'ICRA': 0, 'IROS': 0, 'RA-L': 0, 'T-RO': 0, 'RSS': 0 };
  let maxC = 0, sumC = 0;
  for (const r of f) {
    if (counts[r[0]] !== undefined) counts[r[0]]++;
    if (r[4] > maxC) maxC = r[4];
    sumC += r[4];
  }
  document.getElementById('c-icra').textContent = counts['ICRA'].toLocaleString();
  document.getElementById('c-iros').textContent = counts['IROS'].toLocaleString();
  document.getElementById('c-ral').textContent  = counts['RA-L'].toLocaleString();
  document.getElementById('c-tro').textContent  = counts['T-RO'].toLocaleString();
  document.getElementById('c-rss').textContent  = counts['RSS'].toLocaleString();
  if (f.length === 0) {
    document.getElementById('c-maxcite').textContent = '-';
    document.getElementById('c-meancite').textContent = '-';
  } else {
    document.getElementById('c-maxcite').textContent = maxC.toLocaleString();
    document.getElementById('c-meancite').textContent = (sumC / f.length).toFixed(1);
  }
  document.getElementById('result-info').textContent =
    `Showing ${f.length.toLocaleString()} / ${ALL.length.toLocaleString()} papers`;
}

function renderBarChart() {
  const counts = {}; // year -> {ICRA, IROS, RA-L, T-RO, RSS}
  for (const r of state.filtered) {
    if (!counts[r[1]]) counts[r[1]] = { 'ICRA': 0, 'IROS': 0, 'RA-L': 0, 'T-RO': 0, 'RSS': 0 };
    if (counts[r[1]][r[0]] !== undefined) counts[r[1]][r[0]]++;
  }
  const years = Object.keys(counts).map(Number).sort((a, b) => a - b);
  const datasets = VENUES.map(v => ({
    label: v,
    data: years.map(y => counts[y][v]),
    backgroundColor: VENUE_COLOR[v],
  }));
  if (barChart) barChart.destroy();
  barChart = new Chart(document.getElementById('chart-bar'), {
    type: 'bar',
    data: { labels: years, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { tooltip: { mode: 'index', intersect: false } },
      scales: {
        x: { stacked: true, title: { display: true, text: 'Year' } },
        y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Papers' } }
      }
    }
  });
}

function renderScatter() {
  const MAX_POINTS = 5000;
  let pool = state.filtered;
  if (pool.length > MAX_POINTS) {
    pool = pool.slice().sort((a, b) => b[4] - a[4]).slice(0, MAX_POINTS);
  }
  const byVenue = { 'ICRA': [], 'IROS': [], 'RA-L': [], 'T-RO': [], 'RSS': [] };
  for (const r of pool) {
    if (byVenue[r[0]]) byVenue[r[0]].push({ x: r[1], y: r[4], t: r[2], a: r[3] });
  }
  const datasets = VENUES.map(v => ({
    label: v, data: byVenue[v],
    backgroundColor: VENUE_COLOR[v] + '99', borderColor: VENUE_COLOR[v], pointRadius: 2.5
  }));
  if (scatterChart) scatterChart.destroy();
  scatterChart = new Chart(document.getElementById('chart-scatter'), {
    type: 'scatter',
    data: { datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const d = ctx.raw;
              const a = d.a ? (d.a.length > 60 ? d.a.slice(0, 60) + '...' : d.a) : '';
              return [`${ctx.dataset.label} ${d.x} · ${d.y.toLocaleString()} cites`, d.t.slice(0, 80), a];
            }
          }
        }
      },
      scales: {
        x: { title: { display: true, text: 'Year' }, ticks: { stepSize: 1, callback: (v) => String(Math.round(v)) } },
        y: { title: { display: true, text: 'Cited by count' }, beginAtZero: true }
      }
    }
  });
}

function venueClass(v) {
  if (v === 'RA-L') return 'venue-RAL';
  if (v === 'T-RO') return 'venue-TRO';
  if (v === 'RSS')  return 'venue-RSS';
  return 'venue-' + v;
}

function renderVenueCell(r) {
  const primary = r[0];
  const all = (r[6] || '').split(',').filter(x => x && x !== primary);
  let s = `<span class="${venueClass(primary)}">${primary}</span>`;
  if (all.length) s += ` <span class="venue-also">+${all.join(',')}</span>`;
  return s;
}

function renderTable() {
  const f = state.filtered;
  const total = f.length;
  const pages = Math.max(1, Math.ceil(total / state.pageSize));
  if (state.page > pages) state.page = pages;
  const start = (state.page - 1) * state.pageSize;
  const end = Math.min(start + state.pageSize, total);

  const rows = [];
  for (let i = start; i < end; i++) {
    const r = f[i];
    const title = r[5]
      ? `<a href="https://doi.org/${r[5]}" data-doi="${r[5]}" target="_blank" rel="noopener">${escapeHtml(r[2])}</a>`
      : escapeHtml(r[2]);
    rows.push(
      `<tr>`
      + `<td class="rank">${i + 1}</td>`
      + `<td>${renderVenueCell(r)}</td>`
      + `<td class="year">${r[1]}</td>`
      + `<td>${title}</td>`
      + `<td class="authors" title="${escapeAttr(r[3])}">${escapeHtml(r[3])}</td>`
      + `<td class="cites">${r[4].toLocaleString()}</td>`
      + `</tr>`
    );
  }
  document.getElementById('tbody').innerHTML = rows.join('');
  document.getElementById('page-info').textContent = total === 0
    ? '0 / 0'
    : `${(start + 1).toLocaleString()} ~ ${end.toLocaleString()} / ${total.toLocaleString()} (p.${state.page}/${pages})`;
  document.getElementById('page-prev').disabled = state.page <= 1;
  document.getElementById('page-first').disabled = state.page <= 1;
  document.getElementById('page-next').disabled = state.page >= pages;
  document.getElementById('page-last').disabled = state.page >= pages;

  document.querySelectorAll('th[data-sort]').forEach(th => {
    const arrow = th.querySelector('.arrow');
    if (th.dataset.sort === state.sortKey) {
      th.classList.add('sorted');
      arrow.textContent = state.sortDesc ? '▼' : '▲';
    } else {
      th.classList.remove('sorted');
      arrow.textContent = '';
    }
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

function renderCitationStats() {
  const cites = state.filtered.map(r => r[4]);
  const setText = (id, v) => { document.getElementById(id).textContent = v; };
  if (cites.length === 0) {
    setText('stat-h', '-'); setText('stat-i10', '-');
    setText('stat-median', '-'); setText('stat-std', '-');
    if (histChart) { histChart.destroy(); histChart = null; }
    return;
  }
  const sorted = cites.slice().sort((a, b) => a - b);
  const mean = cites.reduce((a, b) => a + b, 0) / cites.length;
  setText('stat-h', hIndex(cites).toLocaleString());
  setText('stat-i10', i10Index(cites).toLocaleString());
  setText('stat-median', median(sorted).toLocaleString());
  setText('stat-std', stdDev(cites, mean).toFixed(1));

  const counts = new Array(HIST_LABELS.length).fill(0);
  for (const c of cites) counts[citeBin(c)]++;
  if (histChart) histChart.destroy();
  histChart = new Chart(document.getElementById('chart-hist'), {
    type: 'bar',
    data: { labels: HIST_LABELS, datasets: [{ label: 'Papers', data: counts, backgroundColor: '#1f77b4cc' }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: 'Citation count range' } },
        y: { beginAtZero: true, title: { display: true, text: 'Papers' } }
      }
    }
  });
}

function renderWordCloud() {
  const canvas = document.getElementById('wordcloud');
  const note = document.getElementById('wc-note');
  if (!WB_VOCAB || WB_VOCAB.length === 0) {
    note.textContent = 'Word book not loaded. Run _make_word_book.py and regenerate this page.';
    return;
  }
  const counts = new Array(WB_VOCAB.length).fill(0);
  let covered = 0;
  for (const r of state.filtered) {
    const doi = r[5];
    const words = WB_PAPERS[doi];
    if (words) {
      covered++;
      for (const idx of words) counts[idx]++;
    }
  }
  const pairs = [];
  for (let i = 0; i < counts.length; i++) {
    if (counts[i] > 0) pairs.push([WB_VOCAB[i], counts[i]]);
  }
  pairs.sort((a, b) => b[1] - a[1]);
  const top = pairs.slice(0, 100);

  // Retina-friendly canvas sizing
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const cssW = canvas.offsetWidth || 800;
  const cssH = 380;
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  canvas.style.width = cssW + 'px';
  canvas.style.height = cssH + 'px';

  if (covered === 0 || top.length === 0) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#aaa';
    ctx.font = `${14 * dpr}px -apple-system, sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText('No abstracts available for this filter', canvas.width / 2, canvas.height / 2);
    note.textContent = `${state.filtered.length.toLocaleString()} papers · 0 with indexed abstracts`;
    return;
  }

  const maxW = top[0][1];
  if (typeof WordCloud !== 'undefined') {
    WordCloud(canvas, {
      list: top,
      gridSize: Math.round(8 * dpr),
      weightFactor: (size) => Math.max(10 * dpr, (size / maxW) * 64 * dpr),
      fontFamily: '-apple-system, "Segoe UI", sans-serif',
      color: (word, weight) => {
        const t = weight / maxW;
        if (t > 0.65) return '#1a4e80';
        if (t > 0.35) return '#1f77b4';
        if (t > 0.15) return '#2ca02c';
        return '#6b6b6b';
      },
      rotateRatio: 0.22,
      rotationSteps: 2,
      backgroundColor: '#fff',
      drawOutOfBound: false,
      shrinkToFit: true,
    });
  }
  note.textContent = `${state.filtered.length.toLocaleString()} papers in filter · ${covered.toLocaleString()} with indexed abstracts · showing top ${top.length} of ${pairs.length.toLocaleString()} unique terms`;
}

function rerenderAll() {
  filterAndSort();
  renderStats();
  renderBarChart();
  renderScatter();
  renderCitationStats();
  renderWordCloud();
  renderTable();
}

function applyFilters() {
  const yf = parseInt(document.getElementById('f-year-from').value) || YMIN;
  const yt = parseInt(document.getElementById('f-year-to').value) || YMAX;
  state.yearFrom = Math.min(yf, yt);
  state.yearTo = Math.max(yf, yt);
  state.venueFilter['ICRA'] = document.getElementById('f-icra').checked;
  state.venueFilter['IROS'] = document.getElementById('f-iros').checked;
  state.venueFilter['RA-L'] = document.getElementById('f-ral').checked;
  state.venueFilter['T-RO'] = document.getElementById('f-tro').checked;
  state.venueFilter['RSS']  = document.getElementById('f-rss').checked;
  state.minCite = parseInt(document.getElementById('f-mincite').value) || 0;
  state.search = document.getElementById('f-search').value;
  rerenderAll();
}

function resetFilters() {
  document.getElementById('f-year-from').value = YMIN;
  document.getElementById('f-year-to').value = YMAX;
  document.getElementById('f-icra').checked = true;
  document.getElementById('f-iros').checked = true;
  document.getElementById('f-ral').checked = true;
  document.getElementById('f-tro').checked = true;
  document.getElementById('f-rss').checked = true;
  document.getElementById('f-mincite').value = 0;
  document.getElementById('f-search').value = '';
  applyFilters();
}

document.querySelectorAll('th[data-sort]').forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.sort;
    if (state.sortKey === key) state.sortDesc = !state.sortDesc;
    else { state.sortKey = key; state.sortDesc = (key === 'cites' || key === 'year'); }
    filterAndSort();
    renderTable();
  });
});

document.getElementById('page-first').onclick = () => { state.page = 1; renderTable(); };
document.getElementById('page-prev').onclick = () => { state.page--; renderTable(); };
document.getElementById('page-next').onclick = () => { state.page++; renderTable(); };
document.getElementById('page-last').onclick = () => {
  state.page = Math.ceil(state.filtered.length / state.pageSize); renderTable();
};
document.getElementById('page-size').onchange = (e) => {
  state.pageSize = parseInt(e.target.value); state.page = 1; renderTable();
};

document.getElementById('btn-apply').onclick = applyFilters;
document.getElementById('btn-reset').onclick = resetFilters;
['f-year-from', 'f-year-to', 'f-icra', 'f-iros', 'f-ral', 'f-tro', 'f-rss', 'f-mincite'].forEach(id =>
  document.getElementById(id).addEventListener('change', applyFilters)
);
document.getElementById('f-search').addEventListener('keyup', (e) => {
  if (e.key === 'Enter') applyFilters();
});

rerenderAll();

// --- Abstract tooltip on title hover (OpenAlex on-demand, cached) ---
const abstractCache = new Map();
const tooltip = document.createElement('div');
tooltip.id = 'abstract-tooltip';
document.body.appendChild(tooltip);

function reconstructAbstract(invIdx) {
  if (!invIdx) return '';
  let maxPos = -1;
  for (const positions of Object.values(invIdx)) {
    for (const p of positions) if (p > maxPos) maxPos = p;
  }
  const words = new Array(maxPos + 1).fill('');
  for (const [word, positions] of Object.entries(invIdx)) {
    for (const p of positions) if (p < words.length) words[p] = word;
  }
  return words.filter(w => w).join(' ');
}

function positionTooltip(rect) {
  const tooltipW = 480, tooltipH = tooltip.offsetHeight || 200;
  let left = rect.left;
  let top = rect.bottom + 6;
  if (left + tooltipW > window.innerWidth - 10) left = window.innerWidth - tooltipW - 10;
  if (top + tooltipH > window.innerHeight - 10) top = Math.max(10, rect.top - tooltipH - 6);
  tooltip.style.left = left + 'px';
  tooltip.style.top = top + 'px';
}

function showTooltip(html, rect) {
  tooltip.innerHTML = html;
  tooltip.style.display = 'block';
  positionTooltip(rect);
}

function hideTooltip() { tooltip.style.display = 'none'; }

let hoverDoi = null;
let hoverTimer = null;
let hoverCtrl = null;

function renderAbstract(abs, rect) {
  if (!abs) {
    showTooltip('<div class="tt-head">Abstract</div><em>Not available on OpenAlex</em>', rect);
    return;
  }
  const MAX = 650;
  const truncated = abs.length > MAX ? escapeHtml(abs.slice(0, MAX)) + '…' : escapeHtml(abs);
  showTooltip(`<div class="tt-head">Abstract</div>${truncated}`, rect);
}

function handleEnter(a) {
  const doi = a.dataset.doi;
  if (!doi) return;
  if (hoverCtrl) { hoverCtrl.abort(); hoverCtrl = null; }
  clearTimeout(hoverTimer);
  hoverDoi = doi;
  const rect = a.getBoundingClientRect();

  hoverTimer = setTimeout(async () => {
    if (hoverDoi !== doi) return;
    if (abstractCache.has(doi)) { renderAbstract(abstractCache.get(doi), rect); return; }
    showTooltip('<div class="tt-head">Abstract</div><em>Loading…</em>', rect);
    hoverCtrl = new AbortController();
    try {
      const r = await fetch(
        `https://api.openalex.org/works/doi:${doi}?select=abstract_inverted_index&mailto=gisbi.kim@gmail.com`,
        { signal: hoverCtrl.signal }
      );
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      const abs = reconstructAbstract(data.abstract_inverted_index);
      abstractCache.set(doi, abs);
      if (hoverDoi === doi) renderAbstract(abs, a.getBoundingClientRect());
    } catch (err) {
      if (err.name !== 'AbortError') {
        abstractCache.set(doi, '');
        if (hoverDoi === doi) renderAbstract('', a.getBoundingClientRect());
      }
    }
  }, 220);
}

function handleLeave(e) {
  const to = e.relatedTarget;
  if (to && to.closest && to.closest('a[data-doi]')) return;
  clearTimeout(hoverTimer);
  if (hoverCtrl) { hoverCtrl.abort(); hoverCtrl = null; }
  hoverDoi = null;
  hideTooltip();
}

document.getElementById('tbody').addEventListener('mouseover', (e) => {
  const a = e.target.closest('a[data-doi]');
  if (a) handleEnter(a);
});
document.getElementById('tbody').addEventListener('mouseout', handleLeave);
</script>

</body>
</html>
"""

html_out = (HTML
            .replace('__TOTAL_FMT__', f'{total:,}')
            .replace('__YMIN__', str(year_min))
            .replace('__YMAX__', str(year_max))
            .replace('__AS_OF__', AS_OF)
            .replace('__ARR_JSON__', json.dumps(arr, ensure_ascii=False))
            .replace('__WB_VOCAB__', json.dumps(wb_vocab, ensure_ascii=False))
            .replace('__WB_PAPERS__', json.dumps(wb_papers_slim, ensure_ascii=False)))

OUT = 'icra_iros_ral_tro_rss_explorer.html'
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_out)
print(f'wrote {OUT} ({len(html_out)/1024/1024:.1f} MB, {total:,} papers)')
