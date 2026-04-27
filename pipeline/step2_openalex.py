"""
Step 2: Semantic Scholar로 초록/인용수/분야 보강
(구버전 OpenAlex → S2로 전환. step2b_semanticscholar.py 기능 통합.)

S2 batch API (최대 500 DOI/call):
- abstract, citationCount, influentialCitationCount, fieldsOfStudy
- 무료 (unauthenticated ~1 batch/min), API key 있으면 훨씬 빠름

실행:
    python step2_openalex.py            # 체크포인트에 cited_by_s2 없는 DOI만
    python step2_openalex.py --refresh  # 모든 DOI 다시 조회

예상 소요: 91k DOI / 500 ≈ 182 calls × ~3s = ~9분 (unauthenticated, 1 call/min 제한 없을 때)
API key 설정: 환경변수 S2_API_KEY 또는 아래 S2_API_KEY 상수에 직접 입력.
"""
import argparse
import json
import time

import requests

from _checkpoint import load_checkpoint, save_checkpoint

INPUT = "all_dblp.json"
OUT_FILE = "all_enriched.json"
BATCH_SIZE = 500
S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
S2_FIELDS = "abstract,citationCount,influentialCitationCount,fieldsOfStudy"

# S2 API key (선택) — 설정하면 rate limit이 100배 완화됨.
# https://www.semanticscholar.org/product/api 에서 무료 신청 가능.
import os
S2_API_KEY = os.environ.get("S2_API_KEY", "")


def _norm_doi(d):
    d = (d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/"):
        if d.startswith(p):
            d = d[len(p):]
            break
    return d


def fetch_batch(dois: list[str]) -> list:
    """S2 batch API 호출. 입력 dois 순서대로 결과 반환 (못 찾으면 None)."""
    body = {"ids": [f"DOI:{d}" for d in dois]}
    params = {"fields": S2_FIELDS}
    headers = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
    for attempt in range(3):
        try:
            r = requests.post(S2_BATCH_URL, json=body, params=params,
                              headers=headers, timeout=120)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"    rate limited, sleeping {wait}s")
                time.sleep(wait)
                continue
            print(f"    HTTP {r.status_code}: {r.text[:200]}")
            time.sleep(10 * (attempt + 1))
        except Exception as e:
            print(f"    error: {e}")
            time.sleep(10 * (attempt + 1))
    print(f"    giving up on this batch -- moving on")
    return [None] * len(dois)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch S2 for all DOIs (default: only missing cited_by_s2)")
    args = ap.parse_args()

    with open(INPUT, encoding="utf-8") as f:
        papers = json.load(f)

    enriched = load_checkpoint()
    if not enriched:
        print("WARNING: checkpoint is empty — first-time run, no existing data to augment.")

    # 처리 대상: checkpoint에 있고 cited_by_s2 없는 DOI
    # (checkpoint에 없는 DOI는 step2_openalex_legacy.py로 먼저 OpenAlex 기본 데이터 채워야 함
    #  → 신규 venue 추가 시 step2_openalex_legacy.py 먼저 실행 권장)
    todo = []
    for p in papers:
        d = _norm_doi(p.get("doi"))
        if not d:
            continue
        # checkpoint에 없어도 S2에서 바로 받을 수 있음
        if args.refresh or d not in enriched or "cited_by_s2" not in enriched.get(d, {}):
            todo.append(d)

    print(f"DOIs to fetch from S2: {len(todo)} (refresh={args.refresh})")

    n = len(todo)
    for i in range(0, n, BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        results = fetch_batch(batch)

        all_failed = all(not isinstance(w, dict) for w in results)
        if all_failed:
            print(f"  [{i + len(batch)}/{n}] batch SKIPPED (will retry next run)")
            time.sleep(3)
            continue

        miss = 0
        for doi, w in zip(batch, results):
            if doi not in enriched:
                enriched[doi] = {}
            if not isinstance(w, dict):
                enriched[doi].setdefault("cited_by_s2", "")
                miss += 1
                continue

            cc = w.get("citationCount")
            ic = w.get("influentialCitationCount")
            abstract = (w.get("abstract") or "").strip()
            fields = [f.get("category", "") for f in (w.get("fieldsOfStudy") or [])]

            enriched[doi]["cited_by_s2"] = cc if cc is not None else ""
            if ic is not None:
                enriched[doi]["influential_cites_s2"] = ic
            # abstract: S2 값이 있고 기존 OA abstract가 없으면 채움
            if abstract and not enriched[doi].get("abstract"):
                enriched[doi]["abstract"] = abstract
            # concepts: OA concepts가 없으면 S2 fieldsOfStudy로 채움
            if fields and not enriched[doi].get("concepts"):
                enriched[doi]["concepts"] = "; ".join(fields)
            # openalex_id가 없으면 빈 값 보장
            enriched[doi].setdefault("openalex_id", "")
            enriched[doi].setdefault("pages_oa", "")

        done = i + len(batch)
        print(f"  [{done}/{n}] batch ok ({len(batch) - miss}/{len(batch)} found in S2)")

        if (i // BATCH_SIZE) % 5 == 4:
            save_checkpoint(enriched)
            print(f"    checkpoint saved")
        time.sleep(3)

    save_checkpoint(enriched)
    print("\n=== merging into all_enriched.json ===")

    s2_filled = 0
    for p in papers:
        d = _norm_doi(p.get("doi"))
        e = enriched.get(d, {})
        p["abstract"] = e.get("abstract", "")
        p["concepts"] = e.get("concepts", "")
        p["openalex_id"] = e.get("openalex_id", "")
        if not (p.get("pages") or "").strip() and e.get("pages_oa"):
            p["pages"] = e["pages_oa"]
        s2 = e.get("cited_by_s2")
        if isinstance(s2, int):
            p["cited_by_count"] = s2
            p["cites_source"] = "s2"
            s2_filled += 1
        else:
            p["cited_by_count"] = e.get("cited_by_count", "")
            p["cites_source"] = "openalex"
        if e.get("influential_cites_s2") is not None:
            p["influential_cites"] = e["influential_cites_s2"]

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False)

    print(f"S2 인용수: {s2_filled} / {len(papers)} ({100 * s2_filled / len(papers):.1f}%)")
    with_abstract = sum(1 for p in papers if p.get("abstract"))
    print(f"With abstract: {with_abstract} ({100 * with_abstract / len(papers):.1f}%)")


if __name__ == "__main__":
    main()
