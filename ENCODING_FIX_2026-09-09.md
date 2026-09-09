# RSS text encoding correction — 2026-09-09

The publisher sends `Content-Type: text/html` without a charset, while the HTML declares UTF-8. Reading `requests.Response.text` applied the HTTP default Latin-1 decoding before parsing. This corrupted Greek letters, subscripts, accents and punctuation.

- Parse response bytes so BeautifulSoup respects the document's UTF-8 declaration.
- Re-fetch and verify 137 affected RSS 2025/2026 publisher records by exact DOI; repair only matching corrupted fields in the merged datasets.
- Correct title: **π*₀.₆: a VLA That Learns From Experience**, DOI `10.15607/rss.2026.xxii.087`.
- Repair titles, author names and publisher abstracts, including copied abstract fallbacks; regenerate the explorer, Excel exports, word book and coauthor data.
- Keep the dataset at 94,699 papers and retain citation counts.
- Add a regression test reproducing the Latin-1 HTTP default with a UTF-8 HTML declaration. Existing enrichment tests also pass.
- Allow refreshed RSS publisher text to replace that source's existing text during future merges, preserving DBLP identities and text from other sources.

Verified that no C1 control characters remain in RSS titles, authors or abstracts, and no suspect mojibake title patterns remain in the merged dataset.
