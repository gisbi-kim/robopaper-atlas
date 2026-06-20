# RoboPaper Atlas Refresh Report - 2026-06-20

## Summary

Refresh scope: latest 2026 journal/proceedings records for the existing RoboPaper Atlas venue set, followed by enrichment, deduplication, Excel/HTML regeneration, co-author network rebuild, README/landing statistic sync, and push to `main`.

- Baseline commit: `13799ca` (`Add CVML atlas outbound card`)
- Final commit: `045f782` (`Refresh DBLP journal 2026 data`)
- Live URL: https://gisbi-kim.github.io/robopaper-atlas/
- Data date shown in generated files: `2026-06-20`
- Deduplicated papers: `91,457` -> `92,146` (`+689`)
- Abstract coverage: `96.9%`
- Citation coverage: `98.6%`
- Co-author network: `26,646` connected author nodes, `83,152` edges

## Added Papers By Venue

The counts below compare the pre-refresh deduplicated venue totals against the final deduplicated totals.

| Venue | Before | After | Added |
|---|---:|---:|---:|
| RA-L | 10,205 | 10,438 | +233 |
| T-ASE | 5,506 | 5,727 | +221 |
| T-Mech | 6,065 | 6,203 | +138 |
| T-RO | 3,435 | 3,472 | +37 |
| Sci-Rob | 886 | 906 | +20 |
| T-FR | 85 | 98 | +13 |
| IJRR | 2,656 | 2,668 | +12 |
| SoRo | 823 | 833 | +10 |
| RA-P | 19 | 24 | +5 |
| ICRA | 30,612 | 30,612 | +0 |
| IROS | 26,594 | 26,594 | +0 |
| RSS | 1,472 | 1,472 | +0 |
| RAM | 1,688 | 1,688 | +0 |
| CoRL | 1,257 | 1,257 | +0 |
| iSpaRo | 154 | 154 | +0 |
| **Total** | **91,457** | **92,146** | **+689** |

## Updated 2026 Venue Counts

Final deduplicated 2026 paper counts in the generated `by_year` / Excel summary:

| Venue | 2026 papers |
|---|---:|
| RA-L | 1,035 |
| T-ASE | 639 |
| T-Mech | 340 |
| T-RO | 122 |
| Sci-Rob | 49 |
| SoRo | 49 |
| IJRR | 36 |
| T-FR | 22 |
| RAM | 21 |
| RA-P | 20 |

Notes:

- DBLP-source 2026 rows are raw venue records before later cross-file deduplication.
- OpenAlex-source 2026 rows are the final rows after the pipeline cleanup/dedup rules.

## Pipeline Notes

- Re-fetched 2026 OpenAlex-source venues: `SoRo`, `T-Mech`, `T-FR`, `RA-P`, `T-ASE`.
- Re-fetched 2026 DBLP-source journal venues: `RA-L`, `T-RO`, `IJRR`, `RAM`, `Sci-Rob`.
- Enriched newly found DOI records with Semantic Scholar via `pipeline/step2_openalex.py`; this was not a full historical citation refresh.
- Regenerated:
  - `robopaper_atlas_all.xlsx`
  - `by_venue/*.xlsx`
  - `explorer.html`
  - `by_year.html`
  - `dataset_preview.html`
  - `word_book.csv`
  - `word_book.json`
  - `coauthor_network.json`
- Synced manual statistics in `index.html` and `README.md`.
- Fixed DBLP pagination in `pipeline/step1_dblp.py`: DBLP effectively returns 100 records per page, so the fetch loop now continues until `offset >= total`.

## Verification

- Local HTTP check passed for `index.html`, `explorer.html`, and generated statistic text.
- Raw GitHub verified at final commit with `92,146` papers.
- GitHub Pages verified after deployment cache refresh:
  - landing page shows `92,146` papers
  - dataset preview shows `Total papers = 92146`
  - Excel download label shows `5 sheets · 92,146 papers · 49 MB`
