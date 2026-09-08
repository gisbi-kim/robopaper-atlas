# RoboPaper Atlas refresh — 2026-09-08

Baseline: `3ce9c8add717e82657b2830d1f653dcae0c87617` (2026-08-16).

- All 16 existing venues checked, focusing on 2025 and 2026 publication records.
- Deduplicated papers: **93,649 → 94,699 (+1,050)**.
- Abstract coverage: 91878 (97.0%).
- Citation coverage: 94377 (99.7%).
- Network: 27,555 authors, 86,522 edges; Leiden communities rebuilt.
- Existing citation counts retained. New DOI records were queried through Semantic Scholar; missing counts remain missing. This was **not** a historical citation refresh.

| Venue | Before | After | Added |
|---|---:|---:|---:|
| RA-L | 10,730 | 11,104 | +374 |
| RSS | 1,472 | 1,682 | +210 |
| T-ASE | 5,849 | 6,047 | +198 |
| IJRR | 2,680 | 2,794 | +114 |
| T-Mech | 6,293 | 6,336 | +43 |
| T-RO | 3,515 | 3,558 | +43 |
| RAM | 1,715 | 1,753 | +38 |
| Sci-Rob | 916 | 936 | +20 |
| RA-P | 28 | 33 | +5 |
| SoRo | 835 | 838 | +3 |
| T-FR | 106 | 108 | +2 |
| ICRA | 30,612 | 30,612 | +0 |
| IROS | 26,594 | 26,594 | +0 |
| SSRR | 893 | 893 | +0 |
| CoRL | 1,257 | 1,257 | +0 |
| iSpaRo | 154 | 154 | +0 |

## Sources and availability

- DBLP search on both official hosts returned a bot-challenge HTML page. Existing DBLP caches and identifiers were preserved. The collector now handles non-JSON responses without crashing.
- All 10 journals: recent records queried through OpenAlex using verified journal ISSNs. Original DBLP records retained, with source-tagged supplementary records in `pipeline/publisher_raw/`.
- ICRA, IROS, SSRR, iSpaRo: Crossref queried for 2025/2026. Results strictly matched the conference DOI stem and paginated beyond 1,000 records. No matching 2026 records were found in these queries; this is an indexing observation, not a claim that no papers exist.
- RSS: [official 2025 proceedings](https://www.roboticsproceedings.org/rss21/) (163 papers) and [2026 proceedings](https://www.roboticsproceedings.org/rss22/) (210 papers) collected. All 210 RSS 2026 papers are newly included, with publisher abstracts.
- CoRL: [PMLR volume 305](https://proceedings.mlr.press/v305/) checked (263 papers); already covered. CoRL 2026 was not listed in the official PMLR proceedings index at retrieval time.
- No historical raw records were removed. The normal front-matter and duplicate cleanup rules were applied to rebuilt exports.

## Rebuilt outputs and checks

- Full Excel workbook, all 16 per-venue Excel files, explorer, year chart, dataset preview, word book, coauthor graph and communities, landing page and README.
- PASS: Excel summary, year pivot and explorer totals all equal 94,699.
- PASS: all 16 venue download row counts equal the explorer venue totals.
- PASS: DOI uniqueness after cleanup and preservation of baseline raw publication identities.
- PASS: RSS 2026 filter displays 210 papers and 210 abstracts in the browser.
- PASS: existing DOI-less enrichment tests (7 tests).
- Dataset dates are labelled `Data updated`; citation retrieval dates vary by paper. This fixes the previous misleading interpretation of file modification time as the date of every citation count.

The Windows build used SciPy 1.15.3 and scikit-learn 1.6.1 because the newest SciPy DLL was blocked by the local application-control policy. No security settings were changed.
