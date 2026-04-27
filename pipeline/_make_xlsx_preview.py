"""Generate dataset_preview.html — a browsable preview of every sheet in
robopaper_atlas_all.xlsx so visitors can eyeball the structure before they
download the 43 MB file.

Runs after step3_excel.py. No new deps; just pandas + openpyxl (already in
the pipeline).
"""
from __future__ import annotations

import html
import os
from datetime import datetime

import pandas as pd

XLSX = '../robopaper_atlas_all.xlsx'
OUT  = '../dataset_preview.html'

# How many rows to show per sheet. None = all.
ROW_LIMITS: dict[str, int | None] = {
    'summary':        None,
    'by_year_pivot':  None,    # ~40 years
    'by_year_detail': 30,
    'top_cited_100':  30,
    'papers':         30,
}

CELL_MAX = 180  # abstracts get truncated so the table doesn't explode


def _cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return '<span class="null">—</span>'
    s = str(v)
    if len(s) > CELL_MAX:
        s = s[:CELL_MAX].rstrip() + '…'
    return html.escape(s)


def _render_sheet(name: str, df: pd.DataFrame, limit: int | None) -> str:
    total = len(df)
    shown = df if limit is None else df.head(limit)
    head = ''.join(f'<th>{html.escape(str(c))}</th>' for c in shown.columns)
    rows = ''
    for _, r in shown.iterrows():
        rows += '<tr>' + ''.join(f'<td>{_cell(v)}</td>' for v in r) + '</tr>'
    trailer = ''
    if limit is not None and total > limit:
        trailer = (f'<div class="more">+ {total - limit:,} more rows — '
                   f'download the xlsx to see all {total:,}.</div>')
    return f'''
<section id="sheet-{html.escape(name)}">
  <h2>{html.escape(name)}
    <span class="ncol">{len(shown.columns)} cols</span>
    <span class="nrow">{total:,} rows{f" · showing first {len(shown):,}" if limit else ""}</span>
  </h2>
  <div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>
  {trailer}
</section>
'''


def main() -> None:
    as_of = datetime.fromtimestamp(os.path.getmtime(XLSX)).date().isoformat()
    file_mb = os.path.getsize(XLSX) / 1024 / 1024

    sections = []
    toc = []
    for name, limit in ROW_LIMITS.items():
        df = pd.read_excel(XLSX, sheet_name=name)
        sections.append(_render_sheet(name, df, limit))
        toc.append(f'<a href="#sheet-{html.escape(name)}">{html.escape(name)}</a>')

    out_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Dataset preview — RoboPaper Atlas</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", sans-serif;
    max-width: 1200px; margin: 0 auto; padding: 32px 20px 80px;
    background: #fafafa; color: #222; line-height: 1.55;
  }}
  .brand {{ font-size: 12px; letter-spacing: 0.5px; color: #888; margin-bottom: 4px; }}
  .brand a {{ color: inherit; text-decoration: none; font-weight: 600; }}
  .brand a:hover {{ color: #1f77b4; }}
  h1 {{ font-size: 26px; margin: 0 0 6px; letter-spacing: -0.3px; }}
  .sub {{ color: #666; font-size: 13.5px; margin-bottom: 20px; }}
  .dl {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 13px; border: 1px solid #1f77b4; border-radius: 5px;
    text-decoration: none; color: #1f77b4; font-size: 13px; background: #fff;
  }}
  .dl:hover {{ background: #1f77b4; color: #fff; }}
  .dl .sz {{ color: #9ca3af; font-size: 11px; margin-left: 4px; }}
  .dl:hover .sz {{ color: rgba(255,255,255,0.75); }}

  nav.toc {{
    display: flex; flex-wrap: wrap; gap: 6px; margin: 16px 0 28px;
    padding: 10px 12px; background: #fff; border: 1px solid #e5e5e5; border-radius: 6px;
  }}
  nav.toc a {{
    font-size: 12px; padding: 3px 9px; border: 1px solid #d1d5db;
    border-radius: 12px; color: #444; text-decoration: none; background: #f6f6f6;
  }}
  nav.toc a:hover {{ background: #1f77b4; color: #fff; border-color: #1f77b4; }}

  section {{ margin-bottom: 36px; }}
  h2 {{
    font-size: 15px; margin: 0 0 8px; color: #333; display: flex;
    align-items: baseline; gap: 10px; border-bottom: 2px solid #1f77b4;
    padding-bottom: 4px;
  }}
  h2 .ncol, h2 .nrow {{
    font-size: 11px; color: #888; font-weight: 400;
    font-variant-numeric: tabular-nums;
  }}
  .scroll {{
    overflow-x: auto; border: 1px solid #e5e5e5; border-radius: 6px;
    background: #fff; max-height: 520px;
  }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 11.5px;
    font-variant-numeric: tabular-nums;
  }}
  thead th {{
    position: sticky; top: 0; background: #f4f4f4; color: #222;
    text-align: left; padding: 7px 10px; font-weight: 600;
    border-bottom: 1px solid #d1d5db; white-space: nowrap;
  }}
  tbody td {{
    padding: 5px 10px; border-bottom: 1px solid #f1f1f1;
    vertical-align: top; max-width: 340px; color: #333;
  }}
  tbody tr:hover td {{ background: #fafbfc; }}
  .null {{ color: #c0c4cb; }}
  .more {{
    margin-top: 6px; font-size: 11.5px; color: #888; font-style: italic;
  }}

  footer {{ margin-top: 60px; padding-top: 16px; border-top: 1px solid #e5e5e5;
            color: #888; font-size: 11px; }}
  footer a {{ color: #666; }}
</style>
</head>
<body>

<div class="brand"><a href="index.html">RoboPaper Atlas</a></div>
<h1>Dataset preview</h1>
<div class="sub">
  First rows of every sheet inside <code>robopaper_atlas_all.xlsx</code>
  ({file_mb:.0f} MB, data as of {as_of}) — scan the structure before you
  download.
</div>

<a class="dl" href="{XLSX}">📊 Download full Excel <span class="sz">{file_mb:.0f} MB</span></a>

<nav class="toc">
  <span style="font-size:12px; color:#888; padding: 3px 0 3px 2px;">Jump to sheet:</span>
  {''.join(toc)}
</nav>

{''.join(sections)}

<footer>
  Source: <a href="https://github.com/gisbi-kim/robopaper-atlas">github.com/gisbi-kim/robopaper-atlas</a> ·
  generated by <code>_make_xlsx_preview.py</code>.
</footer>

</body>
</html>
'''

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(out_html)
    print(f'wrote {OUT} ({len(out_html) / 1024:.1f} KB)')


if __name__ == '__main__':
    main()
