"""체크포인트에서 특정 연도 이후 DOI 항목 제거 (선택적 refresh용)

사용법:
  python refresh_recent.py 2019    # 2019년 이후 논문 DOI만 제거 (재조사 대상)

이후 `python step2_openalex.py`를 실행하면 제거된 DOI만 다시 OpenAlex에 조회됨.
"""
import json
import sys

from _checkpoint import load_checkpoint, save_checkpoint

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
