"""체크포인트에서 특정 연도 이후 citation 값을 제거 (선택적 refresh용)

사용법:
  python refresh_recent.py 2019    # 2019년 이후 논문 DOI만 제거 (재조사 대상)

이후 `python step2_openalex.py`를 실행하면 DOI 논문과 DOI-less S2 ID를 다시 조회함.
"""
import json
import sys

from _checkpoint import load_checkpoint, save_checkpoint
from _doi_less_checkpoint import (
    load_doi_less_checkpoint,
    paper_key,
    save_doi_less_checkpoint,
)

if len(sys.argv) != 2:
    print("Usage: python refresh_recent.py <from_year>")
    print("  e.g., python refresh_recent.py 2019")
    sys.exit(1)

from_year = int(sys.argv[1])

with open('all_dblp.json', encoding='utf-8') as f:
    papers = json.load(f)

target_dois = set()
for p in papers:
    try:
        y = int(p.get('year', 0))
    except (ValueError, TypeError):
        y = 0
    if y < from_year:
        continue
    doi = (p.get('doi') or '').strip().lower()
    if doi.startswith('https://doi.org/'):
        doi = doi[len('https://doi.org/'):]
    elif doi.startswith('http://doi.org/'):
        doi = doi[len('http://doi.org/'):]
    if doi:
        target_dois.add(doi)

print(f"{from_year}년 이후 DOI: {len(target_dois)}개")

cp = load_checkpoint()
if not cp:
    print("enriched_checkpoint shards가 없음 — step2 처음 실행하면 전체 조회됨")
    sys.exit(0)

before = len(cp)
for d in list(cp.keys()):
    if d in target_dois:
        del cp[d]
removed = before - len(cp)

save_checkpoint(cp)

print(f"체크포인트: {before} → {len(cp)} ({removed}개 제거, 다음 step2에서 재조사됨)")

doi_less_cp = load_doi_less_checkpoint()
doi_less_marked = 0
for p in papers:
    try:
        year = int(p.get('year', 0))
    except (ValueError, TypeError):
        year = 0
    if year < from_year or (p.get('doi') or '').strip():
        continue
    entry = doi_less_cp.get(paper_key(p))
    if not entry or not entry.get('s2_paper_id'):
        continue
    if 'cited_by_s2' in entry:
        del entry['cited_by_s2']
        doi_less_marked += 1

save_doi_less_checkpoint(doi_less_cp)
print(f"DOI-less S2 ID: {doi_less_marked}개 citation 재조사 예약")
