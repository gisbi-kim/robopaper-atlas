"""
Step 1 (extra): DBLP에 색인되지 않은 로봇학 저널을 OpenAlex에서 직접 수집
- Soft Robotics (Mary Ann Liebert, ISSN 2169-5172)
- IEEE/ASME Transactions on Mechatronics (ISSN 1083-4435)

- 연도별로 수집하여 openalex_raw/ 폴더에 JSON으로 저장 (체크포인트)
- DBLP 스키마와 호환되는 레코드를 만들어 all_dblp.json에 머지
- 중단되어도 이미 받은 연도는 스킵

실행 순서:
    python step1_dblp.py [--include-optional]
    python step1_extra_openalex.py
    python step2_openalex.py

예상 소요: 10~20분 (두 저널 모두, 연결 속도 따라)
"""
import argparse
import json
import os
import time

import requests

OUT_DIR = "openalex_raw"
os.makedirs(OUT_DIR, exist_ok=True)

DBLP_MERGE_FILE = "all_dblp.json"
USER_EMAIL = "gisbi.kim@gmail.com"  # step2와 동일

OPENALEX_WORKS = "https://api.openalex.org/works"

# (cache_key, venue_label, issn, year_range)
EXTRA_VENUES = [
    ('soro',  'SoRo',   '2169-5172', range(2014, 2027)),  # Soft Robotics (Liebert) 창간 2014
    ('tmech', 'T-Mech', '1083-4435', range(1996, 2027)),  # IEEE/ASME TMech 창간 1996
    ('tfr',   'T-FR',   '2997-1101', range(2024, 2027)),  # IEEE Transactions on Field Robotics 창간 2024
    ('rap',   'RA-P',   '2995-4304', range(2025, 2027)),  # IEEE Robotics and Automation Practice 창간 2024 (2024 호는 front-matter only → 2025부터 수집)
    ('tase',  'T-ASE',  '1545-5955', range(2004, 2027)),  # IEEE Transactions on Automation Science and Engineering 창간 2004
]


def _strip_doi(doi_url):
    """OpenAlex의 doi는 'https://doi.org/…' 형태. DBLP 포맷(소문자 bare DOI)으로 변환."""
    if not doi_url:
        return ''
    d = doi_url.lower()
    for p in ('https://doi.org/', 'http://doi.org/'):
        if d.startswith(p):
            d = d[len(p):]
            break
    return d


def _authors_str(work):
    names = []
    for a in work.get('authorships', []) or []:
        n = (a.get('author') or {}).get('display_name') or ''
        if n:
            names.append(n)
    return '; '.join(names)


def _pages(work):
    b = work.get('biblio') or {}
    fp, lp = b.get('first_page'), b.get('last_page')
    if fp and lp:
        return f'{fp}-{lp}'
    return fp or lp or ''


def fetch_venue_year(issn, venue_label, year):
    """OpenAlex에서 한 저널·연도 논문 전부 수집. cursor 페이지네이션."""
    results = []
    cursor = '*'
    while cursor:
        params = {
            'filter': f'primary_location.source.issn:{issn},publication_year:{year}',
            'per-page': 200,
            'cursor': cursor,
            'mailto': USER_EMAIL,
        }
        r = None
        for attempt in range(3):
            try:
                r = requests.get(OPENALEX_WORKS, params=params, timeout=60)
                if r.status_code == 200:
                    break
                if r.status_code == 429:
                    print('    rate limited, waiting 60s...')
                    time.sleep(60)
                    continue
                print(f'    HTTP {r.status_code}, retry {attempt+1}')
                time.sleep(5)
            except Exception as e:
                print(f'    error {e}, retry {attempt+1}')
                time.sleep(5)
        if r is None or r.status_code != 200:
            print(f'    FAILED {venue_label} {year}')
            return results

        data = r.json()
        for w in data.get('results', []):
            results.append({
                'venue': venue_label,
                'year': str(w.get('publication_year') or year),
                'title': w.get('title') or '',
                'authors': _authors_str(w),
                'doi': _strip_doi(w.get('doi') or ''),
                'ee': w.get('doi') or '',
                'pages': _pages(w),
                'dblp_key': '',  # DBLP에 없으므로 비움
                'openalex_id': w.get('id') or '',
            })

        cursor = (data.get('meta') or {}).get('next_cursor')
        time.sleep(0.2)  # polite delay
    return results


def load_existing_dblp():
    if not os.path.exists(DBLP_MERGE_FILE):
        print(f'  {DBLP_MERGE_FILE} not found — writing only OpenAlex records')
        return []
    with open(DBLP_MERGE_FILE, encoding='utf-8') as f:
        return json.load(f)


def merge_and_write(extra_papers):
    """all_dblp.json에 extra 레코드를 append (DOI 기준 dedup)."""
    existing = load_existing_dblp()
    seen_dois = {p.get('doi', '').strip().lower() for p in existing if p.get('doi')}
    seen_keys = {(p.get('venue'), p.get('title', '').strip().lower(), p.get('year'))
                 for p in existing}

    added = 0
    for p in extra_papers:
        doi = (p.get('doi') or '').strip().lower()
        if doi and doi in seen_dois:
            continue
        key = (p.get('venue'), (p.get('title') or '').strip().lower(), p.get('year'))
        if not doi and key in seen_keys:
            continue
        existing.append(p)
        if doi:
            seen_dois.add(doi)
        seen_keys.add(key)
        added += 1

    with open(DBLP_MERGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False)
    print(f'\n  merged {added} new records → {DBLP_MERGE_FILE} '
          f'(total {len(existing)})')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='',
                    help='comma list of venue keys to fetch (default: all). '
                         'e.g. --only soro,tmech')
    ap.add_argument('--no-merge', action='store_true',
                    help='skip merging into all_dblp.json (cache only)')
    ap.add_argument('--refresh-cache', action='store_true',
                    help='refetch selected venue/year caches instead of reusing them')
    args = ap.parse_args()

    wanted = set(k.strip().lower() for k in args.only.split(',') if k.strip())
    venues = [v for v in EXTRA_VENUES if not wanted or v[0] in wanted]

    jobs = [(k, lbl, issn, y) for k, lbl, issn, yrs in venues for y in yrs]

    all_extra = []
    for i, (key, label, issn, year) in enumerate(jobs):
        fpath = f'{OUT_DIR}/{key}_{year}.json'
        if os.path.exists(fpath) and not args.refresh_cache:
            with open(fpath, encoding='utf-8') as f:
                papers = json.load(f)
            print(f'[{i+1}/{len(jobs)}] {label} {year}: cached ({len(papers)})')
        else:
            print(f'[{i+1}/{len(jobs)}] {label} {year}: fetching...', flush=True)
            papers = fetch_venue_year(issn, label, year)
            print(f'    got {len(papers)} papers')
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(papers, f, ensure_ascii=False)
            time.sleep(1)
        all_extra.extend(papers)

    print(f'\n=== TOTAL extra: {len(all_extra)} papers ===')
    with_doi = sum(1 for p in all_extra if p.get('doi'))
    if all_extra:
        print(f'With DOI: {with_doi} ({100*with_doi/len(all_extra):.1f}%)')

    if args.no_merge:
        print('  --no-merge set: skipping merge into all_dblp.json')
        return
    merge_and_write(all_extra)


if __name__ == '__main__':
    main()
