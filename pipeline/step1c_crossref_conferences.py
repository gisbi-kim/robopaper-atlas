"""
Step 1c: Collect conference proceedings that are not indexed as DBLP streams.

iSpaRo is an IEEE proceedings venue. DBLP may not expose a stable stream for it,
and OpenAlex records often have only a raw source name, not an ISSN-backed
source. Crossref is the cleanest metadata source for these proceedings.

Run:
    python step1c_crossref_conferences.py --only isparo
"""
import argparse
import json
import os
import time

import requests

OUT_DIR = "crossref_raw"
os.makedirs(OUT_DIR, exist_ok=True)

DBLP_MERGE_FILE = "all_dblp.json"
CROSSREF_WORKS = "https://api.crossref.org/works"
USER_EMAIL = "gisbi.kim@gmail.com"

# (cache_key, venue_label, container_title_template, year_range, query_window)
CONFERENCE_VENUES = [
    (
        "isparo",
        "iSpaRo",
        "{year} International Conference on Space Robotics (iSpaRo)",
        range(2024, 2027),
        1,
    ),
]


def _authors_str(item):
    names = []
    for a in item.get("author", []) or []:
        parts = [a.get("given", ""), a.get("family", "")]
        name = " ".join(p.strip() for p in parts if p and p.strip()).strip()
        if name:
            names.append(name)
    return "; ".join(names)


def _published_year(item, fallback_year):
    for key in ("published-print", "published-online", "published"):
        parts = ((item.get(key) or {}).get("date-parts") or [])
        if parts and parts[0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                pass
    return fallback_year


def _title(item):
    vals = item.get("title") or []
    return vals[0] if vals else ""


def _container_matches(item, expected):
    expected_l = expected.casefold()
    for title in item.get("container-title") or []:
        if str(title).casefold() == expected_l:
            return True
    return False


def _doi(item):
    return (item.get("DOI") or "").strip().lower()


def _to_record(item, venue_label, fallback_year):
    doi = _doi(item)
    return {
        "venue": venue_label,
        "year": str(_published_year(item, fallback_year)),
        "title": _title(item),
        "authors": _authors_str(item),
        "doi": doi,
        "ee": f"https://doi.org/{doi}" if doi else "",
        "pages": item.get("page") or "",
        "dblp_key": "",
    }


def fetch_conference_year(container_title, venue_label, year, query_window=1):
    params = {
        "filter": (
            "prefix:10.1109,"
            f"from-pub-date:{year}-01-01,"
            f"until-pub-date:{year + query_window}-12-31"
        ),
        "query.container-title": container_title,
        "rows": 200,
        "select": "DOI,title,container-title,page,author,published-print,published-online,published",
        "mailto": USER_EMAIL,
    }

    for attempt in range(3):
        try:
            r = requests.get(CROSSREF_WORKS, params=params, timeout=60)
            if r.status_code == 200:
                items = (r.json().get("message") or {}).get("items", [])
                records = [
                    _to_record(item, venue_label, year)
                    for item in items
                    if _container_matches(item, container_title) and _doi(item)
                ]
                records.sort(key=lambda p: (int(str(p["year"]) or year), p["pages"], p["doi"]))
                return records
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"    rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"    HTTP {r.status_code}, retry {attempt + 1}: {r.text[:160]}")
        except Exception as e:
            print(f"    error {e}, retry {attempt + 1}")
        time.sleep(5)
    print(f"    FAILED {venue_label} {year}")
    return []


def load_existing_dblp():
    if not os.path.exists(DBLP_MERGE_FILE):
        print(f"  {DBLP_MERGE_FILE} not found - writing only Crossref records")
        return []
    with open(DBLP_MERGE_FILE, encoding="utf-8") as f:
        return json.load(f)


def merge_and_write(extra_papers):
    existing = load_existing_dblp()
    seen_dois = {p.get("doi", "").strip().lower() for p in existing if p.get("doi")}
    seen_keys = {
        (p.get("venue"), (p.get("title") or "").strip().lower(), p.get("year"))
        for p in existing
    }

    added = 0
    for p in extra_papers:
        doi = (p.get("doi") or "").strip().lower()
        if doi and doi in seen_dois:
            continue
        key = (p.get("venue"), (p.get("title") or "").strip().lower(), p.get("year"))
        if not doi and key in seen_keys:
            continue
        existing.append(p)
        if doi:
            seen_dois.add(doi)
        seen_keys.add(key)
        added += 1

    with open(DBLP_MERGE_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False)
    print(f"\n  merged {added} new records -> {DBLP_MERGE_FILE} (total {len(existing)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--only",
        default="",
        help="comma list of venue keys to fetch (default: all), e.g. --only isparo",
    )
    ap.add_argument("--no-merge", action="store_true", help="skip merging into all_dblp.json")
    args = ap.parse_args()

    wanted = {k.strip().lower() for k in args.only.split(",") if k.strip()}
    venues = [v for v in CONFERENCE_VENUES if not wanted or v[0] in wanted]

    all_extra = []
    jobs = [(k, lbl, template, year, window) for k, lbl, template, years, window in venues for year in years]
    for i, (key, label, template, year, query_window) in enumerate(jobs):
        fpath = os.path.join(OUT_DIR, f"{key}_{year}.json")
        if os.path.exists(fpath):
            with open(fpath, encoding="utf-8") as f:
                papers = json.load(f)
            print(f"[{i + 1}/{len(jobs)}] {label} {year}: cached ({len(papers)})")
        else:
            print(f"[{i + 1}/{len(jobs)}] {label} {year}: fetching...", flush=True)
            papers = fetch_conference_year(template.format(year=year), label, year, query_window)
            print(f"    got {len(papers)} papers")
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(papers, f, ensure_ascii=False)
            time.sleep(1)
        all_extra.extend(papers)

    print(f"\n=== TOTAL conference records: {len(all_extra)} ===")
    if args.no_merge:
        print("  --no-merge set: skipping merge into all_dblp.json")
        return
    merge_and_write(all_extra)


if __name__ == "__main__":
    main()
