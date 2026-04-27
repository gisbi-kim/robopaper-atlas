"""
Step 2b: Semantic Scholar로 인용수 갱신 (OpenAlex 인용수 → S2로 교체)

OpenAlex의 cited_by_count는 Crossref deposited refs 기반이라 보수적이고,
preprint/blog/poster 인용을 거의 못 잡음 (예: ColoRadar 2022 — OpenAlex 3,
S2 93, GS 107). Semantic Scholar는 PDF NLP 파싱 + arXiv 광범위 색인으로
CS/robotics에서 거의 Google Scholar 수준. CS 도메인이라 S2가 더 적절.

호출:
    python step2b_semanticscholar.py            # 체크포인트에 cited_by_s2 없는 DOI만
    python step2b_semanticscholar.py --refresh  # 모든 DOI 다시 조회

Output: enriched_checkpoint_*.json 에 cited_by_s2 / influential_cites_s2 필드 추가,
all_enriched.json 에서 cited_by_count 를 S2 값으로 교체 (S2에 없는 경우 OpenAlex 유지).

API: Semantic Scholar batch endpoint (최대 500 DOI/call, 무료, polite).
예상 소요: 90k DOI / 500 batch ≈ 180 calls × ~1s = ~3-5분.
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


def _norm_doi(d):
    d = (d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/"):
        if d.startswith(p):
            d = d[len(p):]
            break
    return d


def fetch_batch(dois):
    """S2 batch API 호출. 입력 dois 순서대로 결과 list 반환 (없으면 None).
    Unauthenticated S2는 글로벌 ~1 batch/min 정도 허용 → 첫 시도 후 429 시 길게 backoff.
    """
    body = {"ids": [f"DOI:{d}" for d in dois]}
    params = {"fields": "citationCount,influentialCitationCount"}
    # 시도 3회 (60+120+180s = 최대 6분 대기) 후 batch 포기. 다음 배치로 넘어감.
    # 포기된 batch DOI들은 cited_by_s2 미설정 상태 → 다음 실행 때 자동 재시도됨.
    for attempt in range(3):
        try:
            r = requests.post(S2_BATCH_URL, json=body, params=params, timeout=120)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = 60 * (attempt + 1)  # 60, 120, 180s
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
                    help="re-fetch S2 for all DOIs (default: only ones missing cited_by_s2)")
    args = ap.parse_args()

    with open(INPUT, encoding="utf-8") as f:
        papers = json.load(f)

    enriched = load_checkpoint()
    if not enriched:
        raise SystemExit("ERROR: enriched_checkpoint is empty. Run step2_openalex.py first.")

    # 입력 DOI 모음 (체크포인트에 들어있는 것만 — step2가 이미 fetch한 OpenAlex 항목 위에 덧붙임)
    todo = []
    for p in papers:
        d = _norm_doi(p.get("doi"))
        if not d or d not in enriched:
            continue
        if args.refresh or "cited_by_s2" not in enriched[d]:
            todo.append(d)
    print(f"DOIs to fetch from Semantic Scholar: {len(todo)} (refresh={args.refresh})")

    n = len(todo)
    for i in range(0, n, BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        results = fetch_batch(batch)
        # batch 전체가 fail (rate-limit 다 소진)이면 enriched 갱신 안 함 → 다음 실행 때 재시도.
        all_failed = all(not isinstance(w, dict) for w in results)
        if all_failed:
            print(f"  [{i + len(batch)}/{n}] batch SKIPPED (will retry next run)")
            time.sleep(3)
            continue
        miss = 0
        for doi, w in zip(batch, results):
            if not isinstance(w, dict):
                enriched[doi]["cited_by_s2"] = ""  # S2가 정말 모르는 paper (단일 null in successful batch)
                miss += 1
                continue
            cc = w.get("citationCount")
            ic = w.get("influentialCitationCount")
            enriched[doi]["cited_by_s2"] = cc if cc is not None else ""
            if ic is not None:
                enriched[doi]["influential_cites_s2"] = ic
        done = i + len(batch)
        print(f"  [{done}/{n}] batch ok ({len(batch) - miss}/{len(batch)} found in S2)")

        # 5 배치마다 체크포인트 저장 (2,500 DOI)
        if (i // BATCH_SIZE) % 5 == 4:
            save_checkpoint(enriched)
            print(f"    checkpoint saved")
        time.sleep(3)  # polite — unauthenticated S2 글로벌 풀이 빡빡함

    save_checkpoint(enriched)
    print("\n=== merging into all_enriched.json ===")

    # 병합: cited_by_count 를 S2 값으로 교체 (S2 miss인 경우 OpenAlex 유지)
    s2_filled = 0
    for p in papers:
        d = _norm_doi(p.get("doi"))
        e = enriched.get(d, {})
        # 기존 OpenAlex 필드 유지
        p["abstract"] = e.get("abstract", "")
        p["concepts"] = e.get("concepts", "")
        p["openalex_id"] = e.get("openalex_id", "")
        if not (p.get("pages") or "").strip() and e.get("pages_oa"):
            p["pages"] = e["pages_oa"]
        # 인용수: S2 우선, 없으면 OpenAlex 폴백
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

    print(f"S2 인용수로 채워진 행: {s2_filled} / {len(papers)} ({100 * s2_filled / len(papers):.1f}%)")
    print(f"나머지는 OpenAlex 값 유지 (S2에 없는 DOI)")


if __name__ == "__main__":
    main()
