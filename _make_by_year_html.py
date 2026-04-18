"""연도별 편수 시각화 HTML 생성 (ICRA + IROS + RA-L + T-RO + RSS, deduped)"""
import json
import os
from datetime import datetime
import pandas as pd

try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime('all_enriched.json')).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()

df = pd.read_excel('icra_iros_ral_tro_rss_all.xlsx', sheet_name='by_year_pivot')
df['year'] = df['year'].astype(int)
for c in ['ICRA', 'IROS', 'RA-L', 'T-RO', 'RSS']:
    if c not in df.columns:
        df[c] = 0
    df[c] = df[c].fillna(0).astype(int)
df['total'] = df[['ICRA', 'IROS', 'RA-L', 'T-RO', 'RSS']].sum(axis=1)
df = df.sort_values('year', ascending=True).reset_index(drop=True)

rows = [[int(r['year']), int(r['ICRA']), int(r['IROS']), int(r['RA-L']), int(r['T-RO']), int(r['RSS'])]
        for r in df.to_dict('records')]

total_icra = int(df['ICRA'].sum())
total_iros = int(df['IROS'].sum())
total_ral  = int(df['RA-L'].sum())
total_tro  = int(df['T-RO'].sum())
total_rss  = int(df['RSS'].sum())
grand_total = total_icra + total_iros + total_ral + total_tro + total_rss

# 최다 연도 찾기
peak_row = df.loc[df['total'].idxmax()]
peak_year = int(peak_row['year'])
peak_total = int(peak_row['total'])

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ICRA / IROS / RA-L / T-RO / RSS Papers by Year</title>
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
  .summary { display: flex; gap: 16px; margin-top: 20px; flex-wrap: wrap; }
  .card { flex: 1; min-width: 140px; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 14px 18px; }
  .card .num { font-size: 24px; font-weight: 600; }
  .card .label { color: #666; font-size: 12px; }
  .card.icra { border-top: 3px solid #1f77b4; }
  .card.iros { border-top: 3px solid #ff7f0e; }
  .card.ral  { border-top: 3px solid #2ca02c; }
  .card.tro  { border-top: 3px solid #d62728; }
  .card.rss  { border-top: 3px solid #9467bd; }
  table { width: 100%; border-collapse: collapse; margin-top: 24px; font-size: 12px; }
  th, td { border-bottom: 1px solid #eee; padding: 6px 10px; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
  th { background: #f4f4f4; font-weight: 600; }
  td.c-icra { color: #1f77b4; font-variant-numeric: tabular-nums; }
  td.c-iros { color: #ff7f0e; font-variant-numeric: tabular-nums; }
  td.c-ral  { color: #2ca02c; font-variant-numeric: tabular-nums; }
  td.c-tro  { color: #d62728; font-variant-numeric: tabular-nums; }
  td.c-rss  { color: #9467bd; font-variant-numeric: tabular-nums; }
  td.c-total { font-weight: 600; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>

<div class="brand"><a href="index.html">RoboPaper Atlas</a></div>
<h1>ICRA / IROS / RA-L / T-RO / RSS Papers by Year</h1>
<div class="sub">
  DBLP-based · __YMIN__ ~ __YMAX__ · __TOTAL__ papers (DOI-deduped)
  <span style="float:right; color:#888; text-align:right; line-height:1.4;">
    <a href="REFRESH.md" style="color:#1f77b4; text-decoration:none; font-size:11px;">How to refresh? ↻</a><br>
    Data as of __AS_OF__
  </span>
</div>

<div class="summary">
  <div class="card icra"><div class="num">__ICRA_TOT__</div><div class="label">ICRA (1984~)</div></div>
  <div class="card iros"><div class="num">__IROS_TOT__</div><div class="label">IROS (1988~)</div></div>
  <div class="card ral"><div class="num">__RAL_TOT__</div><div class="label">RA-L (2016~)</div></div>
  <div class="card tro"><div class="num">__TRO_TOT__</div><div class="label">T-RO (2004~)</div></div>
  <div class="card rss"><div class="num">__RSS_TOT__</div><div class="label">RSS (2005~)</div></div>
  <div class="card"><div class="num">__TOTAL__</div><div class="label">Grand total</div></div>
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
  <thead><tr><th>Year</th><th>ICRA</th><th>IROS</th><th>RA-L</th><th>T-RO</th><th>RSS</th><th>Total</th></tr></thead>
  <tbody id="tbody"></tbody>
</table>

<script>
// rows: [year, ICRA, IROS, RA-L, T-RO, RSS]
const raw = __ROWS_JSON__;
raw.sort((a, b) => a[0] - b[0]);
const labels = raw.map(r => r[0]);
const icra = raw.map(r => r[1]);
const iros = raw.map(r => r[2]);
const ral  = raw.map(r => r[3]);
const tro  = raw.map(r => r[4]);
const rss  = raw.map(r => r[5]);

const ICRA_COLOR = '#1f77b4';
const IROS_COLOR = '#ff7f0e';
const RAL_COLOR  = '#2ca02c';
const TRO_COLOR  = '#d62728';
const RSS_COLOR  = '#9467bd';

const tbody = document.getElementById('tbody');
[...raw].reverse().forEach(([y, a, b, c, d, e]) => {
  const tot = a + b + c + d + e;
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${y}</td>`
    + `<td class="c-icra">${a.toLocaleString()}</td>`
    + `<td class="c-iros">${b.toLocaleString()}</td>`
    + `<td class="c-ral">${c.toLocaleString()}</td>`
    + `<td class="c-tro">${d.toLocaleString()}</td>`
    + `<td class="c-rss">${e.toLocaleString()}</td>`
    + `<td class="c-total">${tot.toLocaleString()}</td>`;
  tbody.appendChild(tr);
});

const ctx = document.getElementById('chart').getContext('2d');
let chart;

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
      data: {
        labels,
        datasets: [
          { label: 'ICRA', data: icra, borderColor: ICRA_COLOR, backgroundColor: ICRA_COLOR + '33', tension: 0.25, fill: false },
          { label: 'IROS', data: iros, borderColor: IROS_COLOR, backgroundColor: IROS_COLOR + '33', tension: 0.25, fill: false },
          { label: 'RA-L', data: ral,  borderColor: RAL_COLOR,  backgroundColor: RAL_COLOR  + '33', tension: 0.25, fill: false },
          { label: 'T-RO', data: tro,  borderColor: TRO_COLOR,  backgroundColor: TRO_COLOR  + '33', tension: 0.25, fill: false },
          { label: 'RSS',  data: rss,  borderColor: RSS_COLOR,  backgroundColor: RSS_COLOR  + '33', tension: 0.25, fill: false }
        ]
      },
      options: common
    });
  } else {
    const stacked = mode === 'stacked';
    chart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'ICRA', data: icra, backgroundColor: ICRA_COLOR },
          { label: 'IROS', data: iros, backgroundColor: IROS_COLOR },
          { label: 'RA-L', data: ral,  backgroundColor: RAL_COLOR  },
          { label: 'T-RO', data: tro,  backgroundColor: TRO_COLOR  },
          { label: 'RSS',  data: rss,  backgroundColor: RSS_COLOR  }
        ]
      },
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
            .replace('__YMIN__', str(int(df['year'].min())))
            .replace('__YMAX__', str(int(df['year'].max())))
            .replace('__ICRA_TOT__', f'{total_icra:,}')
            .replace('__IROS_TOT__', f'{total_iros:,}')
            .replace('__RAL_TOT__',  f'{total_ral:,}')
            .replace('__TRO_TOT__',  f'{total_tro:,}')
            .replace('__RSS_TOT__',  f'{total_rss:,}')
            .replace('__TOTAL__', f'{grand_total:,}')
            .replace('__AS_OF__', AS_OF)
            .replace('__PEAK_YEAR__', str(peak_year))
            .replace('__PEAK_TOT__', f'{peak_total:,}')
            .replace('__ROWS_JSON__', json.dumps(rows)))

OUT = 'icra_iros_ral_tro_rss_by_year.html'
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_out)
print(f'wrote {OUT} ({len(html_out):,} chars)')
