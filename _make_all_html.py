"""전체 논문 시각화 HTML 생성 (venue-config driven, DOI dedup)"""
import json
import html
import os
import re
from datetime import datetime
import pandas as pd

from _clean import is_front_matter, is_translated_dup

# Single source of truth for venues — priority order = display order.
# Adding a venue: append a dict here; HTML/JS sections regenerate automatically.
VENUES_CFG = [
    {'label': 'ICRA',    'id': 'icra',   'color': '#1f77b4', 'since': 1984},
    {'label': 'IROS',    'id': 'iros',   'color': '#ff7f0e', 'since': 1988},
    {'label': 'RA-L',    'id': 'ral',    'color': '#2ca02c', 'since': 2016},
    {'label': 'T-RO',    'id': 'tro',    'color': '#d62728', 'since': 2004},
    {'label': 'RSS',     'id': 'rss',    'color': '#9467bd', 'since': 2005},
    {'label': 'IJRR',    'id': 'ijrr',   'color': '#8c564b', 'since': 1982},
    {'label': 'Sci-Rob', 'id': 'scirob', 'color': '#17becf', 'since': 2016},
    {'label': 'SoRo',    'id': 'soro',   'color': '#e377c2', 'since': 2014},
    {'label': 'T-Mech',  'id': 'tmech',  'color': '#bcbd22', 'since': 1996},
    {'label': 'T-FR',    'id': 'tfr',    'color': '#7f7f7f', 'since': 2024},
    {'label': 'RA-P',    'id': 'rap',    'color': '#d4a017', 'since': 2025},
    {'label': 'T-ASE',   'id': 'tase',   'color': '#2c8c8c', 'since': 2004},
    {'label': 'RAM',     'id': 'ram',    'color': '#3f51b5', 'since': 1994},
]

# Dedup priority: when one paper is cross-listed (RA-L→ICRA, etc.) we keep
# the JOURNAL version as the primary venue. Order MUST match step3_excel.py
# so summary cards / by_year totals stay consistent across pages.
_DEDUP_ORDER = ['T-RO', 'IJRR', 'Sci-Rob', 'T-FR', 'SoRo', 'T-Mech', 'T-ASE', 'RAM', 'RA-L', 'RA-P', 'RSS', 'ICRA', 'IROS']
VENUE_PRIORITY = {v: i for i, v in enumerate(_DEDUP_ORDER)}
VENUE_LABELS   = [v['label'] for v in VENUES_CFG]
VENUE_COLORS   = {v['label']: v['color'] for v in VENUES_CFG}
VENUE_IDS      = {v['label']: v['id'] for v in VENUES_CFG}
TITLE_STR      = ' / '.join(VENUE_LABELS) + ' Paper Explorer'

# 인용수 기준일: all_enriched.json의 mtime (step2 마지막 실행일)
try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime('all_enriched.json')).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()

with open('all_enriched.json', encoding='utf-8') as f:
    papers = json.load(f)
df = pd.DataFrame(papers)
slim = df[['venue', 'year', 'title', 'authors', 'cited_by_count', 'doi', 'pages']].copy()
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

# Page count from `pages` string. Handles "117-122", "117", "117-22" (DBLP
# abbreviation = 117-122), "117:1-25" (article-id style). Returns 0 if unknown.
_pg_range = re.compile(r'^\s*(\d+)\s*[-–]\s*(\d+)\s*$')
_pg_single = re.compile(r'^\s*(\d+)\s*$')
_pg_article = re.compile(r'^\s*\d+\s*:\s*(\d+)\s*[-–]\s*(\d+)\s*$')
def _page_count(p):
    if not p:
        return 0
    s = str(p).strip()
    m = _pg_article.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return max(0, b - a + 1)
    m = _pg_range.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b < a:
            sa, sb = str(a), str(b)
            if len(sb) < len(sa):
                b = int(sa[:len(sa) - len(sb)] + sb)
        return max(0, b - a + 1)
    if _pg_single.match(s):
        return 1
    return 0
# Sanity-clip per venue. Default cap is 50 pages — robotics conf / letter
# papers are template-fixed at 6–8 pages, so anything longer is almost always
# a DBLP proceedings-span artifact. Long-form journals (IJRR, T-RO) legitimately
# publish 50–100 page surveys, so they get a higher cap.
PAGE_CAP_DEFAULT = 50
PAGE_CAP_OVERRIDES = {'IJRR': 100, 'T-RO': 100}
def _clean_page_count(p, venue):
    n = _page_count(p)
    cap = PAGE_CAP_OVERRIDES.get(venue, PAGE_CAP_DEFAULT)
    return n if 2 <= n <= cap else 0
slim['pages_n'] = [
    _clean_page_count(p, v)
    for v, p in zip(slim['venue'], slim['pages'].fillna('').astype(str))
]

before = len(slim)
slim = slim[slim['authors'].str.strip() != ''].reset_index(drop=True)
print(f"proceedings 표제 제외: {before - len(slim)}건")

# 저널 front-matter 제거 (Editorial, Table of Contents, Publication Info 등)
before = len(slim)
slim = slim[~slim['title'].map(is_front_matter)].reset_index(drop=True)
slim = slim[~slim['title'].map(is_translated_dup)].reset_index(drop=True)
# DOI 없는 행은 거의 다 학회 proceedings volume 표제 등 비논문 → drop.
slim = slim[slim['doi'].astype(str).str.strip() != ''].reset_index(drop=True)
print(f"front-matter / 비영어 / DOI-less 제외: {before - len(slim)}건")

# DOI 기반 dedup — 우선순위는 VENUE_PRIORITY
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

# 제목+연도 기반 추가 dedup — 같은 venue 안에서 DOI만 다른 중복 인덱스만 합침.
# 다른 venue 간(예: IJRR vs ICRA)에 같은-제목·같은-연도가 있어도 보통 저널 확장본/
# 학회 원본으로 별개 publication이므로 절대 합치지 않음.
def _norm_title(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())
before = len(slim)
slim['_tn'] = slim['title'].map(_norm_title)
short = slim['_tn'].str.len() < 20  # "Editorial" 같은 짧은 제목은 제외
pool = slim[~short].copy()
keep = slim[short].copy()
pool['_pri'] = pool['venue'].map(VENUE_PRIORITY).fillna(99).astype(int)
pool = pool.sort_values(['_tn', 'year', 'venue', '_pri'])
pool = pool.drop_duplicates(subset=['_tn', 'year', 'venue'], keep='first').drop(columns=['_pri'])
slim = pd.concat([pool, keep], ignore_index=True).drop(columns=['_tn'])
print(f"제목+연도 dedup (within-venue): {before} → {len(slim)} ({before - len(slim)}건 병합)")

arr = [[r['venue'], r['year'], r['title'], r['authors'], r['cited_by_count'], r['doi'], r['venues_all'], int(r['pages_n'])]
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


def _class_key(label: str) -> str:
    """Mirror JS venueClass(): strip non-alphanumerics, uppercase. 'RA-L' → 'RAL'."""
    return re.sub(r'[^A-Za-z0-9]', '', label).upper()


# HTML fragments — generated once from VENUES_CFG and injected via placeholders.
CARD_BORDER_CSS = ''.join(
    f'  .card.v-{v["id"]} {{ border-top: 3px solid {v["color"]}; }}\n'
    for v in VENUES_CFG
)
VENUE_TEXT_CSS = ''.join(
    f'  .venue-{_class_key(v["label"])} {{ color: {v["color"]}; font-weight: 600; }}\n'
    for v in VENUES_CFG
)
SUMMARY_CARDS = ''.join(
    f'  <div class="card v-{v["id"]} venue-card" data-venue-id="{v["id"]}" '
    f'title="Click to solo this venue (click again to restore all)">'
    f'<div class="num" id="c-{v["id"]}">-</div>'
    f'<div class="label">{v["label"]} ({v["since"]}~)</div></div>\n'
    for v in VENUES_CFG
)
FILTER_A_CHECKBOXES = ''.join(
    f'      <label><input type="checkbox" id="f-{v["id"]}" checked> {v["label"]} <span class="since">({v["since"]}~)</span></label>\n'
    for v in VENUES_CFG
)
FILTER_B_CHECKBOXES = ''.join(
    f'      <label><input type="checkbox" id="f-{v["id"]}-b" checked> {v["label"]} <span class="since">({v["since"]}~)</span></label>\n'
    for v in VENUES_CFG
)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__TITLE_STR__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/wordcloud@1.2.2/src/wordcloud2.js"></script>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 20px; background: #fafafa; color: #222; }
  .brand { font-size: 12px; letter-spacing: 0.5px; color: #888; margin-bottom: 4px; }
  .brand a { color: inherit; text-decoration: none; font-weight: 600; }
  .brand a:hover { color: #1f77b4; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: #666; font-size: 13px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
  .stat-line { display: flex; gap: 28px; font-size: 13px; color: #555; margin: 8px 0 14px; flex-wrap: wrap; }
  .stat-line b { color: #222; font-size: 16px; font-variant-numeric: tabular-nums; margin-left: 6px; font-weight: 700; }
  .wrap { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; }
  h2 { font-size: 14px; margin: 0 0 10px; color: #333; }
  canvas { max-height: 340px; }

  .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .card { min-width: 0; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 10px 14px; }
  .card .num { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
  .card .label { color: #666; font-size: 11px; margin-top: 2px; }
  .venue-card { cursor: pointer; transition: background 0.1s, transform 0.08s; }
  .venue-card:hover { background: #fafafa; transform: translateY(-1px); }
  .venue-card.solo { background: #f0f7ff; border-color: #1f77b4; }
  .card.dim { opacity: 0.45; }

  .venue-filters {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(135px, 1fr));
    gap: 4px 14px; padding: 8px 12px; margin-bottom: 10px;
    background: #fafafa; border: 1px solid #eee; border-radius: 6px;
  }
  .venue-filters label { font-size: 13px; color: #444; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
  .venue-filters label .since { color: #999; font-size: 11px; }
__CARD_BORDER_CSS__
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
  col.col-venue { width: 88px; }
  col.col-year { width: 56px; }
  col.col-pages { width: 64px; }
  col.col-cites { width: 72px; }
  col.col-title { width: auto; }
  col.col-authors { width: 230px; }

  td.rank, td.cites, td.year, td.pages { text-align: right; font-variant-numeric: tabular-nums; }
  td.pages { color: #888; font-size: 12px; }
  td.cites { font-weight: 600; }
  td.rank { color: #999; }
__VENUE_TEXT_CSS__  .venue-also { color: #888; font-weight: 400; font-size: 10px; }
  td.authors { color: #555; font-size: 11px; white-space: nowrap; }
  .author-click { cursor: pointer; }
  .author-click:hover { color: #1f77b4; text-decoration: underline; }
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

  #wordcloud span {
    cursor: pointer;
    transition: filter 0.12s;
    padding: 1px 3px;
    border-radius: 3px;
  }
  #wordcloud span:hover {
    filter: brightness(0.7);
    background: rgba(31, 119, 180, 0.08);
  }

  .pager { display: flex; gap: 8px; align-items: center; justify-content: flex-end; margin-top: 10px; font-size: 13px; flex-wrap: wrap; }
  .pager button { border: 1px solid #ccc; background: #fff; padding: 4px 10px; border-radius: 4px; cursor: pointer; }
  .pager button:disabled { opacity: 0.4; cursor: not-allowed; }

  .toggle-btn { border: 1px solid #ccc; background: #fff; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; }
  .toggle-btn:hover { background: #f4f4f4; }
  .toggle-btn.active { background: #1f77b4; color: #fff; border-color: #1f77b4; }
  .zone-label { display: inline-block; font-size: 10px; color: #fff; background: #1f77b4; padding: 2px 7px; border-radius: 10px; vertical-align: middle; margin-left: 6px; font-weight: 700; letter-spacing: 0.3px; }
  .zone-label.b { background: #d62728; }
  .chart-label { font-size: 12px; color: #666; margin-bottom: 6px; text-align: center; }
  #filter-b-wrap { background: #fff8f3; border-color: #ffd7bd; }
</style>
</head>
<body>

<div class="brand"><a href="index.html">RoboPaper Atlas</a></div>
<h1>__TITLE_STR__</h1>
<div class="sub">
  <span>DBLP + OpenAlex · __TOTAL_FMT__ papers (DOI-deduped) · __YMIN__ ~ __YMAX__ · Filter · Sort · Search</span>
  <span style="color:#888; text-align:right; line-height:1.4;">
    <a href="REFRESH.md" style="color:#1f77b4; text-decoration:none; font-size:11px;">How to refresh? ↻</a><br>
    Citations from Semantic Scholar · as of __AS_OF__
  </span>
</div>

<!-- Row 1: aggregate stats (no venue colour bar) -->
<div class="summary" style="margin-bottom: 8px;">
  <div class="card"><div class="num" id="c-total">-</div><div class="label">Total</div></div>
  <div class="card"><div class="num" id="c-maxcite">-</div><div class="label">Max citations</div></div>
  <div class="card"><div class="num" id="c-meancite">-</div><div class="label">Mean citations</div></div>
</div>
<!-- Row 2: per-venue cards (each with its own colour stripe) -->
<div class="summary">
__SUMMARY_CARDS__</div>

<div style="margin-bottom: 12px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">
  <button id="btn-compare" class="toggle-btn">+ Compare mode</button>
  <label id="lock-y-axis-label" style="display:none; font-size: 13px; color: #555;">
    <input type="checkbox" id="lock-y-axis"> Share y-axis between A and B
  </label>
  <span id="compare-hint" style="color:#888; font-size:12px;">Add a second filter zone to compare two trends side by side</span>
</div>

<div class="wrap">
  <h2>Filters <span class="zone-label" id="zone-label-a" style="display:none;">A</span></h2>
  <div class="venue-filters">
__FILTER_A_CHECKBOXES__  </div>
  <div class="controls">
    <label>Year
      <input type="number" id="f-year-from" min="__YMIN__" max="__YMAX__" value="__YMIN__">
      ~
      <input type="number" id="f-year-to" min="__YMIN__" max="__YMAX__" value="__YMAX__">
    </label>
    <label>Min citations
      <input type="number" id="f-mincite" min="0" value="0">
    </label>
    <label>Title:
      <input type="text" id="f-title-1" placeholder="word 1" style="min-width: 90px; width: 100px;">
      <input type="text" id="f-title-2" placeholder="word 2" style="min-width: 90px; width: 100px;">
      <input type="text" id="f-title-3" placeholder="word 3" style="min-width: 90px; width: 100px;">
      <select id="f-title-op" style="padding: 4px 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; background: #fff;">
        <option value="AND">AND</option>
        <option value="OR">OR</option>
      </select>
    </label>
    <label>Author:
      <input type="text" id="f-author" placeholder="author name" style="min-width: 130px; width: 150px;">
    </label>
    <button id="btn-apply">Apply</button>
    <button id="btn-reset" class="reset">Reset</button>
  </div>
  <div class="result-info" id="result-info"></div>
</div>

<div class="wrap" id="filter-b-wrap" style="display:none;">
  <h2>Filters <span class="zone-label b">B</span></h2>
  <div class="venue-filters">
__FILTER_B_CHECKBOXES__  </div>
  <div class="controls">
    <label>Year
      <input type="number" id="f-year-from-b" min="__YMIN__" max="__YMAX__" value="__YMIN__">
      ~
      <input type="number" id="f-year-to-b" min="__YMIN__" max="__YMAX__" value="__YMAX__">
    </label>
    <label>Min citations
      <input type="number" id="f-mincite-b" min="0" value="0">
    </label>
    <label>Title:
      <input type="text" id="f-title-1-b" placeholder="word 1" style="min-width: 90px; width: 100px;">
      <input type="text" id="f-title-2-b" placeholder="word 2" style="min-width: 90px; width: 100px;">
      <input type="text" id="f-title-3-b" placeholder="word 3" style="min-width: 90px; width: 100px;">
      <select id="f-title-op-b" style="padding: 4px 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; background: #fff;">
        <option value="AND">AND</option>
        <option value="OR">OR</option>
      </select>
    </label>
    <label>Author:
      <input type="text" id="f-author-b" placeholder="author name" style="min-width: 130px; width: 150px;">
    </label>
    <button id="btn-apply-b">Apply</button>
    <button id="btn-reset-b" class="reset">Reset</button>
  </div>
  <div class="result-info" id="result-info-b"></div>
</div>

<div class="wrap">
  <h2>Papers per year (stacked by venue, filtered)</h2>
  <div id="bar-grid" style="display: flex; gap: 16px; align-items: flex-start;">
    <div style="flex: 1; min-width: 0;">
      <div class="chart-label" id="chart-label-a" style="display:none;"><span class="zone-label">A</span></div>
      <div style="position: relative; height: 340px;"><canvas id="chart-bar"></canvas></div>
    </div>
    <div id="bar-b-col" style="flex: 1; min-width: 0; display: none;">
      <div class="chart-label"><span class="zone-label b">B</span></div>
      <div style="position: relative; height: 340px;"><canvas id="chart-bar-b"></canvas></div>
    </div>
    <div id="bar-overlay-col" style="flex: 1; min-width: 0; display: none;">
      <div class="chart-label"><span class="zone-label">A</span> vs <span class="zone-label b">B</span> overlay</div>
      <div style="position: relative; height: 340px;"><canvas id="chart-bar-overlay"></canvas></div>
    </div>
  </div>
  <div style="margin-top: 18px;">
    <div style="font-size:12px; color:#666; margin-bottom: 4px;">
      Per-venue lines (overlaid) — easier to compare growth curves than the stack.
    </div>
    <div style="position: relative; height: 320px;"><canvas id="chart-line"></canvas></div>
  </div>
</div>

<div class="wrap">
  <h2>Venue comparison
    <span style="font-weight:normal; color:#888; font-size:12px;">
      — three angles on venue impact for the current filter. 1 rewards any
      one mega-cited paper; 2 asks where the biggest hits live; 3 asks for
      consistent depth of high-cited work.
    </span>
  </h2>

  <!-- max 3 columns per row — with 4 charts this naturally wraps 3+1 -->
  <style>
    .vcol { display: flex; flex-direction: column; }
    .vcol h3 { font-size: 13px; margin: 0 0 4px; color: #333; min-height: 32px; display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }
    .vcol .desc { color: #888; font-size: 11px; margin-bottom: 6px; min-height: 30px; line-height: 1.45; }
    .vcol .canv { position: relative; height: 220px; margin-top: auto; }
  </style>
  <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px;">

    <div class="vcol">
      <h3>1 · Total citations</h3>
      <div class="desc">Σ cited_by_count. Volume — a single big hit can dominate.</div>
      <div class="canv"><canvas id="chart-vtot"></canvas></div>
    </div>

    <div class="vcol">
      <h3>2 · Avg citations / paper</h3>
      <div class="desc">Σ / #. Normalises for venue size; still biased by mega-hits.</div>
      <div class="canv"><canvas id="chart-vavg"></canvas></div>
    </div>

    <div class="vcol">
      <h3>3 · Median citations</h3>
      <div class="desc">Middle paper's cites. Outlier-resistant — the "typical paper".</div>
      <div class="canv"><canvas id="chart-vmed"></canvas></div>
    </div>

    <div class="vcol">
      <h3>4 · h-index</h3>
      <div class="desc">Largest h with h papers each ≥ h cites. Consistent depth.</div>
      <div class="canv"><canvas id="chart-vh"></canvas></div>
    </div>

    <div class="vcol">
      <h3>
        5 · Top-K composition
        <select id="topk-select" style="padding:2px 6px; font-size: 12px; border:1px solid #ccc; border-radius: 4px; background: #fff;">
          <option>10</option><option>50</option><option selected>100</option><option>500</option><option>1000</option>
        </select>
      </h3>
      <div class="desc"># of top-K most-cited papers from each venue — where the hits concentrate.</div>
      <div class="canv"><canvas id="chart-vtopk"></canvas></div>
    </div>

    <div class="vcol">
      <h3>6 · Avg authors / paper</h3>
      <div class="desc">Team size culture. Low = solo / small-group, high = mass-collab culture.</div>
      <div class="canv"><canvas id="chart-vauth"></canvas></div>
    </div>

    <div class="vcol">
      <h3>7 · Avg # pages / paper</h3>
      <div class="desc">Mean page length per venue. Thin black <b>±1σ pin</b> shows within-venue variance. Clipped to 2–50 pages (IJRR · T-RO: up to 100) to filter out early-access placeholders and DBLP proceedings-span artifacts.</div>
      <div class="canv"><canvas id="chart-vpages"></canvas></div>
    </div>
  </div>
</div>

<div class="wrap">
  <h2>Word cloud
    <span style="font-weight:normal; color:#888; font-size:12px;">
      top terms across the abstracts of the current filter — pick an author + year range to see what they write about
    </span>
  </h2>
  <div id="wordcloud" style="width: 100%; height: 440px; position: relative; background: #fff; border-radius: 4px; overflow: hidden;"></div>
  <div style="color:#888; font-size:11px; margin-top: 6px;" id="wc-note">Click a word to add it to the title filter.</div>
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
    <span>mean <b id="stat-mean">-</b></span>
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
      <col class="col-rank"><col class="col-venue"><col class="col-year"><col class="col-pages">
      <col class="col-title"><col class="col-authors"><col class="col-cites">
    </colgroup>
    <thead>
      <tr>
        <th>#</th>
        <th data-sort="venue">Venue<span class="arrow"></span></th>
        <th data-sort="year">Year<span class="arrow"></span></th>
        <th data-sort="pages"># pages<span class="arrow"></span></th>
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
        <option>50</option><option>100</option><option>200</option><option selected>500</option>
        <option>1000</option><option>2000</option><option>5000</option><option>10000</option>
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
const KEYS = { venue: 0, year: 1, title: 2, authors: 3, cites: 4, doi: 5, pages: 7 };
const YMIN = __YMIN__, YMAX = __YMAX__;

const VENUE_COLOR = __VENUE_COLOR_JSON__;
const VENUES      = __VENUES_JSON__;
const VENUE_IDS   = __VENUE_IDS_JSON__;  // venue label → id-suffix (e.g. 'RA-L' → 'ral')

function emptyVenueCounts() {
  const m = {};
  for (const v of VENUES) m[v] = 0;
  return m;
}
function allVenuesTrue() {
  const m = {};
  for (const v of VENUES) m[v] = true;
  return m;
}

const state = {
  yearFrom: YMIN, yearTo: YMAX,
  venueFilter: allVenuesTrue(),
  minCite: 0,
  titleTerms: ['', '', ''],
  titleOp: 'AND',
  author: '',
  sortKey: 'cites', sortDesc: true,
  page: 1, pageSize: 500,
  filtered: [],
  compareMode: false,
  shareYAxis: false,
  filterB: {
    yearFrom: YMIN, yearTo: YMAX,
    venueFilter: allVenuesTrue(),
    minCite: 0,
    titleTerms: ['', '', ''],
    titleOp: 'AND',
    author: '',
  },
  filteredB: [],
};

let barChart, barChartB, overlayChart, lineChart, histChart;

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

function buildHistBins(cites) {
  if (!cites.length) return { labels: [], counts: [] };
  const step = 10;
  const cap = 200;
  let max = 0;
  for (const c of cites) if (c > max) max = c;
  const nFine = max <= cap ? Math.ceil((max + 1) / step) : cap / step;
  const hasOverflow = max > cap;
  const labels = [];
  for (let i = 0; i < nFine; i++) {
    const lo = i * step, hi = lo + step - 1;
    labels.push(`${lo}\u2013${hi}`);
  }
  if (hasOverflow) labels.push(`${cap}+`);
  const counts = new Array(labels.length).fill(0);
  for (const c of cites) {
    if (c >= cap) counts[counts.length - 1]++;
    else counts[Math.min(nFine - 1, Math.floor(c / step))]++;
  }
  return { labels, counts };
}

function computeFiltered(f) {
  const terms = f.titleTerms.map(t => t.trim().toLowerCase()).filter(t => t);
  const author = f.author.trim().toLowerCase();
  const useOr = f.titleOp === 'OR';
  const out = [];
  for (let i = 0; i < ALL.length; i++) {
    const r = ALL[i];
    if (r[1] < f.yearFrom || r[1] > f.yearTo) continue;
    if (!f.venueFilter[r[0]]) continue;
    if (r[4] < f.minCite) continue;
    if (terms.length > 0) {
      const t = r[2].toLowerCase();
      if (useOr) {
        let hit = false;
        for (const term of terms) { if (t.includes(term)) { hit = true; break; } }
        if (!hit) continue;
      } else {
        let all = true;
        for (const term of terms) { if (!t.includes(term)) { all = false; break; } }
        if (!all) continue;
      }
    }
    if (author && !r[3].toLowerCase().includes(author)) continue;
    out.push(r);
  }
  return out;
}

function filterAndSort() {
  const out = computeFiltered(state);
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
  if (state.compareMode) {
    state.filteredB = computeFiltered(state.filterB);
  }
}

function renderStats() {
  const f = state.filtered;
  document.getElementById('c-total').textContent = f.length.toLocaleString();
  const counts = emptyVenueCounts();
  let maxC = 0, sumC = 0;
  for (const r of f) {
    if (counts[r[0]] !== undefined) counts[r[0]]++;
    if (r[4] > maxC) maxC = r[4];
    sumC += r[4];
  }
  for (const v of VENUES) {
    const el = document.getElementById('c-' + VENUE_IDS[v]);
    if (el) el.textContent = counts[v].toLocaleString();
  }
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

function yearTotalMax(filteredArr) {
  const totals = {};
  for (const r of filteredArr) totals[r[1]] = (totals[r[1]] || 0) + 1;
  let m = 0;
  for (const k in totals) if (totals[k] > m) m = totals[k];
  return m;
}

function drawBarChart(canvasId, filteredArr, which, yMax) {
  const counts = {};
  for (const r of filteredArr) {
    if (!counts[r[1]]) counts[r[1]] = emptyVenueCounts();
    if (counts[r[1]][r[0]] !== undefined) counts[r[1]][r[0]]++;
  }
  const years = [];
  for (let y = YMIN; y <= YMAX; y++) years.push(y);
  const datasets = VENUES.map(v => ({
    label: v,
    data: years.map(y => (counts[y] && counts[y][v]) || 0),
    backgroundColor: VENUE_COLOR[v],
  }));
  const yOpts = { stacked: true, beginAtZero: true, title: { display: true, text: 'Papers' } };
  if (yMax) yOpts.max = yMax;
  const config = {
    type: 'bar',
    data: { labels: years, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { tooltip: { mode: 'index', intersect: false } },
      scales: {
        x: { stacked: true, title: { display: true, text: 'Year' } },
        y: yOpts,
      }
    }
  };
  if (which === 'A') {
    if (barChart) barChart.destroy();
    barChart = new Chart(document.getElementById(canvasId), config);
  } else {
    if (barChartB) barChartB.destroy();
    barChartB = new Chart(document.getElementById(canvasId), config);
  }
}

function drawOverlayChart(yMax) {
  const totalsA = {}, totalsB = {};
  for (const r of state.filtered)  totalsA[r[1]] = (totalsA[r[1]] || 0) + 1;
  for (const r of state.filteredB) totalsB[r[1]] = (totalsB[r[1]] || 0) + 1;
  const years = [];
  for (let y = YMIN; y <= YMAX; y++) years.push(y);
  const dataA = years.map(y => totalsA[y] || 0);
  const dataB = years.map(y => totalsB[y] || 0);
  const yOpts = { beginAtZero: true, title: { display: true, text: 'Papers' } };
  if (yMax) yOpts.max = yMax;
  if (overlayChart) overlayChart.destroy();
  overlayChart = new Chart(document.getElementById('chart-bar-overlay'), {
    type: 'line',
    data: {
      labels: years,
      datasets: [
        { label: 'A', data: dataA, borderColor: '#1f77b4', backgroundColor: 'rgba(31, 119, 180, 0.35)', fill: 'origin', tension: 0.25, pointRadius: 0, borderWidth: 1.8 },
        { label: 'B', data: dataB, borderColor: '#d62728', backgroundColor: 'rgba(214, 39, 40, 0.35)', fill: 'origin', tension: 0.25, pointRadius: 0, borderWidth: 1.8 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { tooltip: { mode: 'index', intersect: false }, legend: { position: 'top' } },
      scales: {
        x: { title: { display: true, text: 'Year' } },
        y: yOpts
      }
    }
  });
}

function drawLineChart(filteredArr) {
  // Per-venue lines on the same axes — easier to compare growth curves than the stack.
  const counts = {};
  for (const r of filteredArr) {
    if (!counts[r[1]]) counts[r[1]] = {};
    counts[r[1]][r[0]] = (counts[r[1]][r[0]] || 0) + 1;
  }
  const years = [];
  for (let y = YMIN; y <= YMAX; y++) years.push(y);
  const datasets = VENUES.map(v => ({
    label: v,
    data: years.map(y => (counts[y] && counts[y][v]) || 0),
    borderColor: VENUE_COLOR[v],
    backgroundColor: VENUE_COLOR[v] + '22',
    tension: 0.25,
    pointRadius: 0,
    pointHoverRadius: 4,
    borderWidth: 1.8,
    fill: false,
  }));
  if (lineChart) lineChart.destroy();
  lineChart = new Chart(document.getElementById('chart-line'), {
    type: 'line',
    data: { labels: years, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        tooltip: { mode: 'index', intersect: false },
        legend: { position: 'top' },
      },
      scales: {
        x: { title: { display: true, text: 'Year' } },
        y: { title: { display: true, text: 'Papers' }, beginAtZero: true },
      },
    },
  });
}

function renderBarChart() {
  let yMax = null;
  if (state.compareMode && state.shareYAxis) {
    yMax = Math.max(yearTotalMax(state.filtered), yearTotalMax(state.filteredB));
  }
  drawBarChart('chart-bar', state.filtered, 'A', yMax);
  drawLineChart(state.filtered);
  if (state.compareMode) {
    drawBarChart('chart-bar-b', state.filteredB, 'B', yMax);
    drawOverlayChart(yMax);
  } else {
    if (barChartB) { barChartB.destroy(); barChartB = null; }
    if (overlayChart) { overlayChart.destroy(); overlayChart = null; }
  }
}

let vtotChart, vavgChart, vmedChart, vhChart, vtopkChart, vauthChart, vpagesChart;

function venueStats(filtered, topK) {
  const sum = {}, count = {}, cites = {}, authorsTot = {}, pagesArr = {};
  for (const v of VENUES) {
    sum[v] = 0; count[v] = 0; cites[v] = []; authorsTot[v] = 0; pagesArr[v] = [];
  }
  for (const r of filtered) {
    const v = r[0], c = r[4];
    if (sum[v] === undefined) continue;
    sum[v] += c; count[v]++; cites[v].push(c);
    const nAuth = (r[3] || '').split(';').filter(s => s.trim()).length;
    authorsTot[v] += nAuth;
    const pn = r[7] || 0;
    if (pn > 0) pagesArr[v].push(pn);
  }
  const avg = {}, avgAuth = {}, med = {}, hidx = {}, pagesAvg = {}, pagesSd = {};
  for (const v of VENUES) {
    const n = count[v];
    avg[v]     = n ? sum[v] / n : 0;
    avgAuth[v] = n ? authorsTot[v] / n : 0;
    const pa = pagesArr[v];
    if (pa.length) {
      const m = pa.reduce((a, b) => a + b, 0) / pa.length;
      const variance = pa.reduce((a, b) => a + (b - m) * (b - m), 0) / pa.length;
      pagesAvg[v] = m;
      pagesSd[v] = Math.sqrt(variance);
    } else {
      pagesAvg[v] = 0;
      pagesSd[v] = 0;
    }
    // Median
    const asc = cites[v].slice().sort((a, b) => a - b);
    if (!asc.length) { med[v] = 0; }
    else if (asc.length % 2) { med[v] = asc[(asc.length - 1) >> 1]; }
    else { med[v] = (asc[asc.length / 2 - 1] + asc[asc.length / 2]) / 2; }
    // h-index
    const desc = cites[v].slice().sort((a, b) => b - a);
    let h = 0;
    for (let i = 0; i < desc.length; i++) {
      if (desc[i] >= i + 1) h = i + 1; else break;
    }
    hidx[v] = h;
  }
  // Top-K composition
  const sorted = filtered.slice().sort((a, b) => b[4] - a[4]).slice(0, topK);
  const topN = {};
  for (const v of VENUES) topN[v] = 0;
  for (const r of sorted) if (topN[r[0]] !== undefined) topN[r[0]]++;
  return { sum, avg, med, hidx, topN, topK: sorted.length, avgAuth, pagesAvg, pagesSd };
}

function _venueBar(data, xTitle, formatValue) {
  // data: object venue -> value. Sort venues by value descending.
  const labels = VENUES.slice().sort((a, b) => (data[b] || 0) - (data[a] || 0));
  const vals = labels.map(v => data[v] || 0);
  const colors = labels.map(v => VENUE_COLOR[v]);
  const fmt = formatValue || ((v) => Number(v).toLocaleString());
  return {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data: vals, backgroundColor: colors, borderColor: colors, borderWidth: 0 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => ' ' + fmt(ctx.raw) } },
      },
      scales: {
        x: { title: { display: true, text: xTitle }, beginAtZero: true,
             ticks: { callback: (v) => fmt(v) } },
        y: { ticks: { autoSkip: false } },
      },
    },
  };
}

function _venueBarWithPin(meanData, sdData, xTitle, formatValue) {
  const labels = VENUES.slice().sort((a, b) => (meanData[b] || 0) - (meanData[a] || 0));
  const means  = labels.map(v => meanData[v] || 0);
  const sds    = labels.map(v => sdData[v]   || 0);
  const ranges = labels.map((_, i) => [Math.max(0, means[i] - sds[i]), means[i] + sds[i]]);
  const colors = labels.map(v => VENUE_COLOR[v]);
  const fmt = formatValue || ((v) => Number(v).toFixed(1));
  return {
    type: 'bar',
    data: {
      labels,
      datasets: [
        // mean bar
        { data: means, backgroundColor: colors, borderColor: colors, borderWidth: 0,
          barPercentage: 0.7, categoryPercentage: 0.9 },
        // ±1σ pin overlay (thin dark bar across mean)
        { data: ranges, backgroundColor: 'rgba(40,40,40,0.85)', borderColor: 'rgba(40,40,40,0.85)',
          borderWidth: 0, barPercentage: 0.10, categoryPercentage: 0.9, grouped: false },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: {
          label: (ctx) => ctx.datasetIndex === 0
            ? ' mean: ' + fmt(ctx.raw)
            : ' ±1σ: ' + fmt(ctx.raw[0]) + ' – ' + fmt(ctx.raw[1]),
        } },
      },
      scales: {
        x: { title: { display: true, text: xTitle }, beginAtZero: true,
             ticks: { callback: (v) => fmt(v) } },
        y: { ticks: { autoSkip: false } },
      },
    },
  };
}

function renderVenueComparison() {
  const topK = parseInt(document.getElementById('topk-select').value) || 100;
  const s = venueStats(state.filtered, topK);
  const f1 = (v) => Number(v).toFixed(1);

  if (vtotChart)  vtotChart.destroy();
  vtotChart  = new Chart(document.getElementById('chart-vtot'),   _venueBar(s.sum,     'Σ citations'));
  if (vavgChart)  vavgChart.destroy();
  vavgChart  = new Chart(document.getElementById('chart-vavg'),   _venueBar(s.avg,     'cites / paper',    f1));
  if (vmedChart)  vmedChart.destroy();
  vmedChart  = new Chart(document.getElementById('chart-vmed'),   _venueBar(s.med,     'median cites',     f1));
  if (vhChart)    vhChart.destroy();
  vhChart    = new Chart(document.getElementById('chart-vh'),     _venueBar(s.hidx,    'h-index'));
  if (vtopkChart) vtopkChart.destroy();
  vtopkChart = new Chart(document.getElementById('chart-vtopk'),  _venueBar(s.topN,    `# in top ${s.topK}`));
  if (vauthChart) vauthChart.destroy();
  vauthChart = new Chart(document.getElementById('chart-vauth'),  _venueBar(s.avgAuth, 'authors / paper',  f1));
  if (vpagesChart) vpagesChart.destroy();
  vpagesChart = new Chart(document.getElementById('chart-vpages'), _venueBarWithPin(s.pagesAvg, s.pagesSd, 'pages / paper', f1));
}


function venueClass(v) {
  return 'venue-' + String(v).replace(/[^A-Za-z0-9]/g, '').toUpperCase();
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
    const authorsHtml = r[3]
      ? r[3].split(';').map(a => {
          const name = a.trim();
          if (!name) return '';
          return `<span class="author-click" data-author="${escapeAttr(name)}">${escapeHtml(name)}</span>`;
        }).filter(Boolean).join('; ')
      : '';
    rows.push(
      `<tr>`
      + `<td class="rank">${i + 1}</td>`
      + `<td>${renderVenueCell(r)}</td>`
      + `<td class="year">${r[1]}</td>`
      + `<td class="pages">${r[7] ? r[7] : 'N/A'}</td>`
      + `<td>${title}</td>`
      + `<td class="authors" title="${escapeAttr(r[3])}">${authorsHtml}</td>`
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
    setText('stat-mean', '-'); setText('stat-median', '-'); setText('stat-std', '-');
    if (histChart) { histChart.destroy(); histChart = null; }
    return;
  }
  const sorted = cites.slice().sort((a, b) => a - b);
  const mean = cites.reduce((a, b) => a + b, 0) / cites.length;
  setText('stat-h', hIndex(cites).toLocaleString());
  setText('stat-i10', i10Index(cites).toLocaleString());
  setText('stat-mean', mean.toFixed(1));
  setText('stat-median', median(sorted).toLocaleString());
  setText('stat-std', stdDev(cites, mean).toFixed(1));

  const { labels, counts } = buildHistBins(cites);
  if (histChart) histChart.destroy();
  histChart = new Chart(document.getElementById('chart-hist'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Papers', data: counts, backgroundColor: '#1f77b4cc' }] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: 'Citation count range (bin size 10, 200+ overflow)' }, ticks: { autoSkip: true, maxRotation: 0 } },
        y: { beginAtZero: true, title: { display: true, text: 'Papers' } }
      }
    }
  });
}

function addTitleFilterWord(word) {
  const ids = ['f-title-1', 'f-title-2', 'f-title-3'];
  let placed = false;
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el.value.trim()) { el.value = word; placed = true; break; }
  }
  if (!placed) document.getElementById('f-title-1').value = word;
  applyFilters();
}

function renderWordCloud() {
  const container = document.getElementById('wordcloud');
  const note = document.getElementById('wc-note');
  container.innerHTML = '';

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
  const top = pairs.slice(0, 50);

  if (covered === 0 || top.length === 0) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#aaa;font-size:13px;">No abstracts available for this filter</div>';
    note.textContent = `${state.filtered.length.toLocaleString()} papers · 0 with indexed abstracts`;
    return;
  }

  const maxW = top[0][1];
  if (typeof WordCloud !== 'undefined') {
    WordCloud(container, {
      list: top,
      gridSize: 14,
      weightFactor: (size) => Math.max(16, (size / maxW) * 72),
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
      click: (item) => addTitleFilterWord(item[0]),
    });
  }
  note.textContent = `${state.filtered.length.toLocaleString()} papers · ${covered.toLocaleString()} with abstracts · top ${top.length} of ${pairs.length.toLocaleString()} unique terms · click a word to add to title filter`;
}

let wcDebounceTimer = null;
function rerenderAll() {
  filterAndSort();
  renderStats();
  renderBarChart();
  renderVenueComparison();
  renderCitationStats();
  renderTable();
  // Word cloud layout is the slowest — debounce so rapid filter clicks don't relayout repeatedly.
  clearTimeout(wcDebounceTimer);
  wcDebounceTimer = setTimeout(renderWordCloud, 180);
}

function applyFilters() {
  const yf = parseInt(document.getElementById('f-year-from').value) || YMIN;
  const yt = parseInt(document.getElementById('f-year-to').value) || YMAX;
  state.yearFrom = Math.min(yf, yt);
  state.yearTo = Math.max(yf, yt);
  for (const v of VENUES) {
    state.venueFilter[v] = document.getElementById('f-' + VENUE_IDS[v]).checked;
  }
  state.minCite = parseInt(document.getElementById('f-mincite').value) || 0;
  state.titleTerms = [
    document.getElementById('f-title-1').value,
    document.getElementById('f-title-2').value,
    document.getElementById('f-title-3').value,
  ];
  state.titleOp = document.getElementById('f-title-op').value;
  state.author = document.getElementById('f-author').value;
  rerenderAll();
}

function resetFilters() {
  document.getElementById('f-year-from').value = YMIN;
  document.getElementById('f-year-to').value = YMAX;
  for (const v of VENUES) {
    document.getElementById('f-' + VENUE_IDS[v]).checked = true;
  }
  document.getElementById('f-mincite').value = 0;
  ['f-title-1','f-title-2','f-title-3','f-author'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('f-title-op').value = 'AND';
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

// Venue cards: click to solo (= only that venue checked), click again to restore all.
function syncVenueCardStyles() {
  const checked = {};
  for (const v of VENUES) checked[v] = document.getElementById('f-' + VENUE_IDS[v]).checked;
  const checkedList = VENUES.filter(v => checked[v]);
  const isSoloed = checkedList.length === 1;
  document.querySelectorAll('.venue-card').forEach(card => {
    const vid = card.dataset.venueId;
    // Map id-suffix back to label for state lookup
    const label = VENUES.find(v => VENUE_IDS[v] === vid);
    card.classList.toggle('solo', isSoloed && checked[label]);
    card.classList.toggle('dim', !checked[label] && checkedList.length < VENUES.length);
  });
}
document.querySelectorAll('.venue-card').forEach(card => {
  card.addEventListener('click', () => {
    const vid = card.dataset.venueId;
    const targetId = 'f-' + vid;
    const allBoxes = VENUES.map(v => document.getElementById('f-' + VENUE_IDS[v]));
    const isSoloed = allBoxes.every(cb => cb.checked === (cb.id === targetId));
    if (isSoloed) {
      allBoxes.forEach(cb => cb.checked = true);     // toggle off → restore all
    } else {
      allBoxes.forEach(cb => cb.checked = (cb.id === targetId));  // solo
    }
    applyFilters();
    syncVenueCardStyles();
  });
});
// Keep card highlight in sync when user toggles checkboxes manually.
VENUES.forEach(v => {
  const cb = document.getElementById('f-' + VENUE_IDS[v]);
  if (cb) cb.addEventListener('change', syncVenueCardStyles);
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

const _aChangeIds = ['f-year-from', 'f-year-to', 'f-mincite', 'f-title-op']
  .concat(VENUES.map(v => 'f-' + VENUE_IDS[v]));
_aChangeIds.forEach(id =>
  document.getElementById(id).addEventListener('change', applyFilters)
);
['f-title-1', 'f-title-2', 'f-title-3', 'f-author'].forEach(id => {
  document.getElementById(id).addEventListener('keyup', (e) => {
    if (e.key === 'Enter') applyFilters();
  });
});

// Top-K selector — only affects chart 2 so just re-render the venue block
document.getElementById('topk-select').addEventListener('change', renderVenueComparison);

// --- Compare mode (filter B) ---
function applyFiltersB() {
  const yf = parseInt(document.getElementById('f-year-from-b').value) || YMIN;
  const yt = parseInt(document.getElementById('f-year-to-b').value) || YMAX;
  state.filterB.yearFrom = Math.min(yf, yt);
  state.filterB.yearTo = Math.max(yf, yt);
  for (const v of VENUES) {
    state.filterB.venueFilter[v] = document.getElementById('f-' + VENUE_IDS[v] + '-b').checked;
  }
  state.filterB.minCite = parseInt(document.getElementById('f-mincite-b').value) || 0;
  state.filterB.titleTerms = [
    document.getElementById('f-title-1-b').value,
    document.getElementById('f-title-2-b').value,
    document.getElementById('f-title-3-b').value,
  ];
  state.filterB.titleOp = document.getElementById('f-title-op-b').value;
  state.filterB.author = document.getElementById('f-author-b').value;
  state.filteredB = computeFiltered(state.filterB);
  document.getElementById('result-info-b').textContent =
    `Showing ${state.filteredB.length.toLocaleString()} / ${ALL.length.toLocaleString()} papers`;
  if (state.compareMode) renderBarChart();
}

function resetFiltersB() {
  document.getElementById('f-year-from-b').value = YMIN;
  document.getElementById('f-year-to-b').value = YMAX;
  for (const v of VENUES) {
    document.getElementById('f-' + VENUE_IDS[v] + '-b').checked = true;
  }
  document.getElementById('f-mincite-b').value = 0;
  ['f-title-1-b','f-title-2-b','f-title-3-b','f-author-b'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('f-title-op-b').value = 'AND';
  applyFiltersB();
}

function copyFilterAtoBInputs() {
  document.getElementById('f-year-from-b').value = document.getElementById('f-year-from').value;
  document.getElementById('f-year-to-b').value = document.getElementById('f-year-to').value;
  for (const v of VENUES) {
    const id = VENUE_IDS[v];
    document.getElementById('f-' + id + '-b').checked = document.getElementById('f-' + id).checked;
  }
  document.getElementById('f-mincite-b').value = document.getElementById('f-mincite').value;
  [1,2,3].forEach(i => document.getElementById('f-title-' + i + '-b').value = document.getElementById('f-title-' + i).value);
  document.getElementById('f-title-op-b').value = document.getElementById('f-title-op').value;
  document.getElementById('f-author-b').value = document.getElementById('f-author').value;
}

function toggleCompareMode() {
  state.compareMode = !state.compareMode;
  const btn = document.getElementById('btn-compare');
  const zoneB = document.getElementById('filter-b-wrap');
  const chartBCol = document.getElementById('bar-b-col');
  const labelA = document.getElementById('zone-label-a');
  const chartLabelA = document.getElementById('chart-label-a');
  const hint = document.getElementById('compare-hint');
  const lockLabel = document.getElementById('lock-y-axis-label');

  btn.classList.toggle('active', state.compareMode);
  btn.textContent = state.compareMode ? '✕ Compare mode' : '+ Compare mode';
  hint.textContent = state.compareMode
    ? 'Change filter B below to contrast against filter A.'
    : 'Add a second filter zone to compare two trends side by side';
  zoneB.style.display = state.compareMode ? '' : 'none';
  chartBCol.style.display = state.compareMode ? '' : 'none';
  document.getElementById('bar-overlay-col').style.display = state.compareMode ? '' : 'none';
  labelA.style.display = state.compareMode ? '' : 'none';
  chartLabelA.style.display = state.compareMode ? '' : 'none';
  lockLabel.style.display = state.compareMode ? '' : 'none';

  if (state.compareMode) {
    copyFilterAtoBInputs();
    applyFiltersB();
  }
  renderBarChart();
}

document.getElementById('btn-apply-b').onclick = applyFiltersB;
document.getElementById('btn-reset-b').onclick = resetFiltersB;
document.getElementById('btn-compare').onclick = toggleCompareMode;
document.getElementById('lock-y-axis').addEventListener('change', (e) => {
  state.shareYAxis = e.target.checked;
  renderBarChart();
});

// Word cloud uses wordcloud2.js which layouts on draw; re-render on resize
let wcResizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(wcResizeTimer);
  wcResizeTimer = setTimeout(renderWordCloud, 200);
});
const _bChangeIds = ['f-year-from-b', 'f-year-to-b', 'f-mincite-b', 'f-title-op-b']
  .concat(VENUES.map(v => 'f-' + VENUE_IDS[v] + '-b'));
_bChangeIds.forEach(id =>
  document.getElementById(id).addEventListener('change', applyFiltersB)
);
['f-title-1-b', 'f-title-2-b', 'f-title-3-b', 'f-author-b'].forEach(id => {
  document.getElementById(id).addEventListener('keyup', (e) => {
    if (e.key === 'Enter') applyFiltersB();
  });
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

// Clicking an author in the paper list populates the Author filter
document.getElementById('tbody').addEventListener('click', (e) => {
  const s = e.target.closest('.author-click');
  if (!s) return;
  e.preventDefault();
  document.getElementById('f-author').value = s.dataset.author;
  ['f-title-1','f-title-2','f-title-3'].forEach(id => document.getElementById(id).value = '');
  applyFilters();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});
</script>

</body>
</html>
"""

html_out = (HTML
            .replace('__TITLE_STR__', TITLE_STR)
            .replace('__CARD_BORDER_CSS__', CARD_BORDER_CSS)
            .replace('__VENUE_TEXT_CSS__', VENUE_TEXT_CSS)
            .replace('__SUMMARY_CARDS__', SUMMARY_CARDS)
            .replace('__FILTER_A_CHECKBOXES__', FILTER_A_CHECKBOXES)
            .replace('__FILTER_B_CHECKBOXES__', FILTER_B_CHECKBOXES)
            .replace('__VENUES_JSON__', json.dumps(VENUE_LABELS))
            .replace('__VENUE_COLOR_JSON__', json.dumps(VENUE_COLORS))
            .replace('__VENUE_IDS_JSON__', json.dumps(VENUE_IDS))
            .replace('__TOTAL_FMT__', f'{total:,}')
            .replace('__YMIN__', str(year_min))
            .replace('__YMAX__', str(year_max))
            .replace('__AS_OF__', AS_OF)
            .replace('__ARR_JSON__', json.dumps(arr, ensure_ascii=False))
            .replace('__WB_VOCAB__', json.dumps(wb_vocab, ensure_ascii=False))
            .replace('__WB_PAPERS__', json.dumps(wb_papers_slim, ensure_ascii=False)))

OUT = 'explorer.html'
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_out)
print(f'wrote {OUT} ({len(html_out)/1024/1024:.1f} MB, {total:,} papers)')
