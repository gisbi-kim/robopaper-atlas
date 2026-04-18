"""Top 100 cited papers 시각화 HTML 생성 (all_enriched.json에서 직접 계산)"""
import json
import html
import os
import re
from datetime import datetime
import pandas as pd

try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime('all_enriched.json')).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()

_dblp_suffix = re.compile(r'\s+\d{4}$')
def _clean_authors(s):
    return '; '.join(_dblp_suffix.sub('', a.strip()) for a in html.unescape(str(s)).split(';') if a.strip())

with open('all_enriched.json', encoding='utf-8') as f:
    papers = json.load(f)
df = pd.DataFrame(papers)
df['title'] = df['title'].fillna('').astype(str).map(html.unescape).str.rstrip('.').str.strip()
df['authors'] = df['authors'].fillna('').astype(str).map(_clean_authors)
df['doi'] = df['doi'].fillna('').astype(str)
df['year'] = pd.to_numeric(df['year'], errors='coerce').fillna(0).astype(int)
df['cited_by_count'] = pd.to_numeric(df['cited_by_count'], errors='coerce')
# proceedings 표제 제거
df = df[df['authors'].str.strip() != ''].reset_index(drop=True)
# top 100 인용
df = df.dropna(subset=['cited_by_count']).nlargest(100, 'cited_by_count')
df['cited_by_count'] = df['cited_by_count'].astype(int)
top = df[['venue', 'year', 'title', 'authors', 'cited_by_count', 'doi']].to_dict('records')

pv = df.pivot_table(index='year', columns='venue', values='title', aggfunc='count', fill_value=0)
by_year = []
for y in sorted(pv.index):
    by_year.append({
        'year': int(y),
        'ICRA': int(pv.loc[y].get('ICRA', 0)),
        'IROS': int(pv.loc[y].get('IROS', 0)),
    })

icra_cnt = sum(1 for p in top if p['venue'] == 'ICRA')
iros_cnt = sum(1 for p in top if p['venue'] == 'IROS')
years = [r['year'] for r in by_year]
totals = {r['year']: r['ICRA'] + r['IROS'] for r in by_year}
peak_year = max(totals, key=totals.get)
peak_cnt = totals[peak_year]
top_cites = int(top[0]['cited_by_count'])

HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>ICRA / IROS / RA-L / T-RO / RSS Top 100 Most Cited Papers</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 24px; background: #fafafa; color: #222; }
  .brand { font-size: 12px; letter-spacing: 0.5px; color: #888; margin-bottom: 4px; }
  .brand a { color: inherit; text-decoration: none; font-weight: 600; }
  .brand a:hover { color: #1f77b4; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: #666; font-size: 13px; margin-bottom: 20px; }
  .wrap { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
  h2 { font-size: 15px; margin: 0 0 10px; color: #333; }
  canvas { max-height: 420px; }
  .summary { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
  .card { flex: 1; min-width: 140px; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 12px 16px; }
  .card .num { font-size: 22px; font-weight: 600; }
  .card .label { color: #666; font-size: 12px; margin-top: 2px; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { border-bottom: 1px solid #eee; padding: 6px 8px; vertical-align: top; }
  th { background: #f4f4f4; font-weight: 600; text-align: left; position: sticky; top: 0; }
  .tbl-wrap { max-height: 500px; overflow-y: auto; border: 1px solid #e5e5e5; border-radius: 8px; }
  .rank { width: 36px; text-align: right; color: #999; }
  .cites { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
  .venue-icra { color: #1f77b4; font-weight: 600; }
  .venue-iros { color: #ff7f0e; font-weight: 600; }
  .title-cell { max-width: 420px; }
  .authors-cell { max-width: 260px; color: #555; font-size: 11px; }
  a { color: inherit; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>

<div class="brand"><a href="index.html">RoboPaper Atlas</a></div>
<h1>ICRA / IROS / RA-L / T-RO / RSS Top 100 Most Cited Papers</h1>
<div class="sub" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap;">
  <span>OpenAlex 기준 인용수 · 출간 연도 분포 (최신 논문일수록 인용 축적 기간이 짧아 적게 잡힘)</span>
  <span style="color:#888; text-align:right; line-height:1.4;">
    <a href="REFRESH.md" style="color:#1f77b4; text-decoration:none; font-size:11px;">How to refresh? ↻</a><br>
    Citations as of __AS_OF__
  </span>
</div>

<div class="summary">
  <div class="card"><div class="num">__ICRA_CNT__</div><div class="label">ICRA (top 100 중)</div></div>
  <div class="card"><div class="num">__IROS_CNT__</div><div class="label">IROS (top 100 중)</div></div>
  <div class="card"><div class="num">__YR_MIN__~__YR_MAX__</div><div class="label">연도 범위</div></div>
  <div class="card"><div class="num">__PEAK_YEAR__ (__PEAK_CNT__편)</div><div class="label">최다 연도</div></div>
  <div class="card"><div class="num">__TOP_CITES__</div><div class="label">1위 인용수</div></div>
</div>

<div class="wrap">
  <h2>연도별 Top 100 편수 (ICRA / IROS, stacked)</h2>
  <canvas id="chart-bar"></canvas>
</div>

<div class="wrap">
  <h2>Scatter: 연도 × 인용수 (점 하나 = 논문 한 편, 마우스 올리면 제목)</h2>
  <canvas id="chart-scatter"></canvas>
</div>

<div class="wrap">
  <h2>Top 100 리스트 (제목 클릭 → DOI 링크)</h2>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th class="rank">#</th><th>Venue</th><th>Year</th><th>Title</th><th>Authors</th><th class="cites">Cites</th></tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>

<script>
const byYear = __BY_YEAR_JSON__;
const top100 = __TOP_JSON__;

const ICRA_COLOR = '#1f77b4';
const IROS_COLOR = '#ff7f0e';

const labels = byYear.map(r => r.year);
const icra = byYear.map(r => r.ICRA);
const iros = byYear.map(r => r.IROS);
new Chart(document.getElementById('chart-bar'), {
  type: 'bar',
  data: {
    labels,
    datasets: [
      { label: 'ICRA', data: icra, backgroundColor: ICRA_COLOR },
      { label: 'IROS', data: iros, backgroundColor: IROS_COLOR }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { tooltip: { mode: 'index', intersect: false } },
    scales: {
      x: { stacked: true, title: { display: true, text: 'Year' } },
      y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Papers in top 100' }, ticks: { stepSize: 1 } }
    }
  }
});

const icraPts = top100.filter(p => p.venue === 'ICRA').map(p => ({ x: p.year, y: p.cited_by_count, t: p.title, a: p.authors }));
const irosPts = top100.filter(p => p.venue === 'IROS').map(p => ({ x: p.year, y: p.cited_by_count, t: p.title, a: p.authors }));
new Chart(document.getElementById('chart-scatter'), {
  type: 'scatter',
  data: {
    datasets: [
      { label: 'ICRA', data: icraPts, backgroundColor: ICRA_COLOR + 'cc', borderColor: ICRA_COLOR, pointRadius: 5 },
      { label: 'IROS', data: irosPts, backgroundColor: IROS_COLOR + 'cc', borderColor: IROS_COLOR, pointRadius: 5 }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const d = ctx.raw;
            const author = d.a ? d.a.slice(0, 80) + (d.a.length > 80 ? '...' : '') : '';
            return [ctx.dataset.label + ' ' + d.x + ' · ' + d.y.toLocaleString() + ' cites', d.t, author];
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

const tbody = document.getElementById('tbody');
top100.forEach((p, i) => {
  const tr = document.createElement('tr');
  const vcls = p.venue === 'ICRA' ? 'venue-icra' : 'venue-iros';
  const titleCell = p.doi
    ? '<a href="https://doi.org/' + p.doi + '" target="_blank" rel="noopener">' + p.title + '</a>'
    : p.title;
  tr.innerHTML =
    '<td class="rank">' + (i + 1) + '</td>' +
    '<td class="' + vcls + '">' + p.venue + '</td>' +
    '<td>' + p.year + '</td>' +
    '<td class="title-cell">' + titleCell + '</td>' +
    '<td class="authors-cell">' + (p.authors || '') + '</td>' +
    '<td class="cites">' + p.cited_by_count.toLocaleString() + '</td>';
  tbody.appendChild(tr);
});
</script>

</body>
</html>
"""

html = (HTML
        .replace('__AS_OF__', AS_OF)
        .replace('__ICRA_CNT__', str(icra_cnt))
        .replace('__IROS_CNT__', str(iros_cnt))
        .replace('__YR_MIN__', str(min(years)))
        .replace('__YR_MAX__', str(max(years)))
        .replace('__PEAK_YEAR__', str(peak_year))
        .replace('__PEAK_CNT__', str(peak_cnt))
        .replace('__TOP_CITES__', f'{top_cites:,}')
        .replace('__BY_YEAR_JSON__', json.dumps(by_year))
        .replace('__TOP_JSON__', json.dumps(top, ensure_ascii=False)))

OUT = 'icra_iros_ral_tro_rss_top100.html'
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'wrote {OUT} ({len(html):,} chars)')
