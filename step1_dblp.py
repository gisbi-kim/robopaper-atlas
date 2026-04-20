"""
Step 1: DBLP에서 ICRA/IROS 전체 논문 메타데이터 수집
- 연도별로 수집하여 dblp_raw/ 폴더에 JSON으로 저장 (체크포인트)
- 중단되어도 이미 받은 연도는 스킵
- 최종 all_dblp.json 합본 생성

실행:
    python step1_dblp.py                  # core 6 venues (ICRA/IROS/RA-L/T-RO/RSS/IJRR)
    python step1_dblp.py --include-optional   # + Science Robotics

예상 소요: 30분~1시간 (연결 속도 따라)
"""
import argparse
import requests
import time
import json
import os
from urllib.parse import quote

DBLP_BASE = "https://dblp.org/search/publ/api"
OUT_DIR = "dblp_raw"
os.makedirs(OUT_DIR, exist_ok=True)


def fetch_dblp_year(stream, venue_label, year):
    """DBLP에서 한 stream·연도 논문 전부 수집
    stream: 'conf/icra', 'conf/iros', 'journals/ral' 등
    venue_label: 결과 레코드의 venue 필드 값 ('ICRA', 'IROS', 'RA-L')
    """
    results = []
    offset = 0
    batch_size = 1000  # DBLP 최대

    while True:
        query = f"stream:{stream}: year:{year}:"
        url = f"{DBLP_BASE}?q={quote(query)}&format=json&h={batch_size}&f={offset}"

        # 재시도 로직
        r = None
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=60)
                if r.status_code == 200:
                    break
                elif r.status_code == 429:
                    print(f"    rate limited, waiting 30s...")
                    time.sleep(30)
                else:
                    print(f"    HTTP {r.status_code}, retry {attempt+1}")
                    time.sleep(5)
            except Exception as e:
                print(f"    error {e}, retry {attempt+1}")
                time.sleep(5)

        if r is None or r.status_code != 200:
            print(f"    FAILED {venue_label} {year}")
            return results

        data = r.json()
        hits = data.get('result', {}).get('hits', {})
        total = int(hits.get('@total', 0))

        if total == 0:
            return results

        hit_list = hits.get('hit', [])
        if not hit_list:
            break

        for h in hit_list:
            info = h.get('info', {})
            authors_data = info.get('authors', {}).get('author', [])
            if isinstance(authors_data, dict):
                authors_data = [authors_data]
            authors = [a.get('text', '') for a in authors_data]

            results.append({
                'venue': venue_label,
                'year': str(info.get('year', year)),
                'title': info.get('title', ''),
                'authors': '; '.join(authors),
                'doi': info.get('doi', '').lower() if info.get('doi') else '',
                'ee': info.get('ee', ''),
                'pages': info.get('pages', ''),
                'dblp_key': info.get('key', ''),
            })

        offset += len(hit_list)
        if offset >= total or len(hit_list) < batch_size:
            break
        time.sleep(1)  # courtesy delay

    return results


# (cache_key, dblp_stream, venue_label, year_range)
CORE_VENUES = [
    ('icra', 'conf/icra',     'ICRA', range(1984, 2026)),
    ('iros', 'conf/iros',     'IROS', range(1988, 2026)),
    ('ral',  'journals/ral',  'RA-L', range(2016, 2026)),  # RA-L 창간 2016
    ('tro',  'journals/trob', 'T-RO', range(2004, 2026)),  # T-RO: 2004~ (이전 T-RA는 제외)
    ('rss',  'conf/rss',      'RSS',  range(2005, 2026)),  # Robotics: Science and Systems
    ('ijrr', 'journals/ijrr', 'IJRR', range(1982, 2026)),  # Int. J. of Robotics Research (창간 1982)
]

# DBLP에 색인된 optional venues. (Soft Robotics, IEEE TMech은 DBLP 미색인 →
# step1_extra_openalex.py에서 OpenAlex로 수집)
OPTIONAL_VENUES = [
    ('scirob', 'journals/scirobotics', 'Sci-Rob', range(2016, 2026)),  # Science Robotics 창간 2016
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--include-optional', action='store_true',
                    help='also fetch optional DBLP venues (Science Robotics)')
    args = ap.parse_args()

    venues_config = CORE_VENUES + (OPTIONAL_VENUES if args.include_optional else [])

    jobs = []
    for key, stream, label, years in venues_config:
        for y in years:
            jobs.append((key, stream, label, y))

    all_papers = []
    for i, (key, stream, label, year) in enumerate(jobs):
        fpath = f"{OUT_DIR}/{key}_{year}.json"

        # 이미 수집했으면 스킵 — 단 비어있는(0편) 캐시는 상류(DBLP)가
        # 당시 해당 연도를 아직 인덱싱 안 했던 경우이므로 재시도.
        if os.path.exists(fpath) and os.path.getsize(fpath) > 2:
            with open(fpath, encoding='utf-8') as f:
                papers = json.load(f)
            print(f"[{i+1}/{len(jobs)}] {label} {year}: cached ({len(papers)})")
            all_papers.extend(papers)
            continue

        print(f"[{i+1}/{len(jobs)}] {label} {year}: fetching...", flush=True)
        papers = fetch_dblp_year(stream, label, year)
        print(f"    got {len(papers)} papers")

        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(papers, f, ensure_ascii=False)

        all_papers.extend(papers)
        time.sleep(2)  # DBLP courtesy between years

    # 전체 합본
    with open('all_dblp.json', 'w', encoding='utf-8') as f:
        json.dump(all_papers, f, ensure_ascii=False)

    print(f"\n=== TOTAL: {len(all_papers)} papers ===")
    with_doi = sum(1 for p in all_papers if p.get('doi'))
    print(f"With DOI: {with_doi} ({100*with_doi/len(all_papers):.1f}%)")


if __name__ == '__main__':
    main()
