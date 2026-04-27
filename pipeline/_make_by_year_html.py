"""연도별 편수 시각화 HTML 생성 (venue-config driven)"""
import json
import os
import re
from datetime import datetime
import pandas as pd

# Single source of truth — must match _make_all_html.py for visual consistency.
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
VENUE_LABELS = [v['label'] for v in VENUES_CFG]
TITLE_STR = ' / '.join(VENUE_LABELS) + ' Papers by Year'


def _class_key(label: str) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', label).upper()


try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime('all_enriched.json')).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()

df = pd.read_excel('../robopaper_atlas_all.xlsx', sheet_name='by_year_pivot')
df['year'] = df['year'].astype(int)
for v in VENUE_LABELS:
    if v not in df.columns:
        df[v] = 0
    df[v] = df[v].fillna(0).astype(int)
df['total'] = df[VENUE_LABELS].sum(axis=1)
df = df.sort_values('year', ascending=True).reset_index(drop=True)

# rows: [year, count_for_each_venue_in_VENUE_LABELS_order]
rows = [[int(r['year'])] + [int(r[v]) for v in VENUE_LABELS]
        for r in df.to_dict('records')]

totals = {v: int(df[v].sum()) for v in VENUE_LABELS}
grand_total = sum(totals.values())

# Peak year (max total)
peak_row = df.loc[df['total'].idxmax()]
peak_year = int(peak_row['year'])
peak_total = int(peak_row['total'])

# HTML fragments
CARD_BORDER_CSS = ''.join(
    f'  .card.v-{v["id"]} {{ border-top: 3px solid {v["color"]}; }}\n'
    for v in VENUES_CFG
)
CELL_TEXT_CSS = ''.join(
    f'  td.c-{v["id"]} {{ color: {v["color"]}; font-variant-numeric: tabular-nums; }}\n'
    for v in VENUES_CFG
)
SUMMARY_CARDS = ''.join(
    f'  <div class="card v-{v["id"]}"><div class="num">{totals[v["label"]]:,}</div>'
    f'<div class="label">{v["label"]} ({v["since"]}~)</div></div>\n'
    for v in VENUES_CFG
)
TABLE_HEAD = ''.join(f'<th>{v}</th>' for v in VENUE_LABELS)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__TITLE_STR__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 24px; background: #fafafa; color: #222; }
  .brand { font-size: 12px; letter-spacing: 0.5px; color: #888; margin-bottom: 4px; }
  .brand a { color: inherit; text-decoration: none; font-weight: 600; }
  .brand a:hover { color: #1f77b4; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: #666; font-size: 13px; margin-bottom: 20px; }
  .controls { margin-bottom: 12px; }
  .controls button {
    border: 1px solid #ccc; background: #fff; padding: 6px 14px; margin-right: 6px;
    border-radius: 6px; cursor: pointer; font-size: 13px;
  }
  .controls button.active { background: #1f77b4; color: #fff; border-color: #1f77b4; }
  .wrap { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 16px; }
  canvas { max-height: 520px; }
  .summary { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px; margin-top: 20px; }
  .card { min-width: 0; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 14px 18px; }
  .card .num { font-size: 24px; font-weight: 600; }
  .card .label { color: #666; font-size: 12px; }
__CARD_BORDER_CSS__  table { width: 100%; border-collapse: collapse; margin-top: 24px; font-size: 12px; }
  th, td { border-bottom: 1px solid #eee; padding: 6px 10px; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
  th { background: #f4f4f4; font-weight: 600; }
__CELL_TEXT_CSS__  td.c-total { font-weight: 600; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>

<div class="brand"><a href="index.html">RoboPaper Atlas</a></div>
<h1>__TITLE_STR__</h1>
<div class="sub" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap;">
  <span>DBLP + OpenAlex · __YMIN__ ~ __YMAX__ · __TOTAL__ papers (DOI-deduped)</span>
  <span style="color:#888; text-align:right; line-height:1.4;">
    <a href="REFRESH.md" style="color:#1f77b4; text-decoration:none; font-size:11px;">How to refresh? ↻</a><br>
    Data as of __AS_OF__
  </span>
</div>

<div class="summary">
__SUMMARY_CARDS__  <div class="card"><div class="num">__TOTAL__</div><div class="label">Grand total</div></div>
  <div class="card"><div class="num">__PEAK_YEAR__ (__PEAK_TOT__)</div><div class="label">Peak year</div></div>
</div>

<div style="margin-top: 24px;">
  <div class="controls">
    <button id="btn-stacked" class="active">Stacked</button>
    <button id="btn-grouped">Grouped</button>
    <button id="btn-line">Line</button>
  </div>
  <div class="wrap"><canvas id="chart"></canvas></div>
</div>

<table>
  <thead><tr><th>Year</th>__TABLE_HEAD__<th>Total</th></tr></thead>
  <tbody id="tbody"></tbody>
</table>

<script>
// rows: [year, ...counts in VENUES order]
const VENUES = __VENUES_JSON__;
const VENUE_COLOR = __VENUE_COLOR_JSON__;
const VENUE_IDS = __VENUE_IDS_JSON__;
const raw = __ROWS_JSON__;
raw.sort((a, b) => a[0] - b[0]);
const labels = raw.map(r => r[0]);
// byVenue[i] = array of counts for VENUES[i] across years
const byVenue = VENUES.map((_v, i) => raw.map(r => r[i + 1]));

const tbody = document.getElementById('tbody');
[...raw].reverse().forEach(r => {
  const y = r[0];
  const counts = r.slice(1);
  const tot = counts.reduce((a, b) => a + b, 0);
  const cells = counts.map((c, i) =>
    `<td class="c-${VENUE_IDS[VENUES[i]]}">${c.toLocaleString()}</td>`
  ).join('');
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${y}</td>${cells}<td class="c-total">${tot.toLocaleString()}</td>`;
  tbody.appendChild(tr);
});

const ctx = document.getElementById('chart').getContext('2d');
let chart;

function makeDatasets(mode) {
  if (mode === 'line') {
    return VENUES.map((v, i) => ({
      label: v, data: byVenue[i],
      borderColor: VENUE_COLOR[v],
      backgroundColor: VENUE_COLOR[v] + '33',
      tension: 0.25, fill: false,
    }));
  }
  return VENUES.map((v, i) => ({
    label: v, data: byVenue[i], backgroundColor: VENUE_COLOR[v],
  }));
}

function render(mode) {
  if (chart) chart.destroy();
  const common = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top' },
      tooltip: { mode: 'index', intersect: false }
    },
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: { title: { display: true, text: 'Year' } },
      y: { title: { display: true, text: 'Papers' }, beginAtZero: true }
    }
  };
  if (mode === 'line') {
    chart = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets: makeDatasets('line') },
      options: common,
    });
  } else {
    const stacked = mode === 'stacked';
    chart = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: makeDatasets(mode) },
      options: {
        ...common,
        scales: {
          x: { ...common.scales.x, stacked },
          y: { ...common.scales.y, stacked }
        }
      }
    });
  }
}

render('stacked');

const btns = { stacked: 'btn-stacked', grouped: 'btn-grouped', line: 'btn-line' };
Object.entries(btns).forEach(([mode, id]) => {
  document.getElementById(id).addEventListener('click', () => {
    Object.values(btns).forEach(x => document.getElementById(x).classList.remove('active'));
    document.getElementById(id).classList.add('active');
    render(mode);
  });
});
</script>

</body>
</html>
"""

html_out = (HTML
            .replace('__TITLE_STR__', TITLE_STR)
            .replace('__CARD_BORDER_CSS__', CARD_BORDER_CSS)
            .replace('__CELL_TEXT_CSS__', CELL_TEXT_CSS)
            .replace('__SUMMARY_CARDS__', SUMMARY_CARDS)
            .replace('__TABLE_HEAD__', TABLE_HEAD)
            .replace('__YMIN__', str(int(df['year'].min())))
            .replace('__YMAX__', str(int(df['year'].max())))
            .replace('__TOTAL__', f'{grand_total:,}')
            .replace('__AS_OF__', AS_OF)
            .replace('__PEAK_YEAR__', str(peak_year))
            .replace('__PEAK_TOT__', f'{peak_total:,}')
            .replace('__VENUES_JSON__', json.dumps(VENUE_LABELS))
            .replace('__VENUE_COLOR_JSON__', json.dumps({v['label']: v['color'] for v in VENUES_CFG}))
            .replace('__VENUE_IDS_JSON__', json.dumps({v['label']: v['id'] for v in VENUES_CFG}))
            .replace('__ROWS_JSON__', json.dumps(rows)))

OUT = '../by_year.html'
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_out)
print(f'wrote {OUT} ({len(html_out):,} chars)')
