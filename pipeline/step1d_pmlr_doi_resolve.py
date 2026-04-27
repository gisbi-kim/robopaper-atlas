"""
Step 1d: PMLR 학회 DOI 해결 (arXiv API 제목 검색 → arXiv DOI 역추적)

CoRL 등 PMLR 학회 논문은 DBLP에 doi 필드가 비어있음.
arXiv API 제목 검색으로 동명 preprint를 찾아 DOI(10.48550/arxiv.*)를 구성,
all_dblp.json에 역기재. 이후 step2_openalex.py가 해당 DOI를 정상 처리함.

실행:
    python step1d_pmlr_doi_resolve.py             # 기본: 모든 PMLR 학회 (CoRL)
    python step1d_pmlr_doi_resolve.py --venue CoRL

예상 소요: ~8분 (CoRL 1,200편 × 0.4s)
"""
import argparse
import json
import time
import xml.etree.ElementTree as ET

import requests

DBLP_MERGE_FILE = "all_dblp.json"
ARXIV_API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}

# PMLR 기반 학회 목록 (doi-less)
PMLR_VENUES = {"CoRL"}


def _norm_title(t: str) -> str:
    return " ".join(t.lower().rstrip(".").split())


def search_arxiv(title: str) -> str:
    """arXiv API 제목 검색 → arXiv DOI (10.48550/arxiv.XXXX.XXXXX) 반환. 없으면 ''."""
    params = {
        "search_query": f'ti:"{title}"',
        "max_results": 5,
        "sortBy": "relevance",
    }
    for attempt in range(3):
        try:
            r = requests.get(ARXIV_API, params=params, timeout=30)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                for entry in root.findall("a:entry", NS):
                    arxiv_title = (entry.find("a:title", NS).text or "").strip()
                    if _norm_title(arxiv_title) == _norm_title(title):
                        arxiv_url = (entry.find("a:id", NS).text or "").strip()
                        # http://arxiv.org/abs/2407.01812v3 → 2407.01812
                        arxiv_id = arxiv_url.split("/abs/")[-1].split("v")[0]
                        if arxiv_id:
                            return f"10.48550/arxiv.{arxiv_id}"
                return ""
            if r.status_code == 429 or r.status_code == 503:
                print(f"    arXiv rate limit (HTTP {r.status_code}), sleeping 30s...")
                time.sleep(30)
            else:
                print(f"    arXiv HTTP {r.status_code}")
                time.sleep(5)
        except Exception as e:
            print(f"    error: {e}")
            time.sleep(5)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", default="", help="처리할 venue (기본: 모든 PMLR 학회)")
    args = ap.parse_args()

    target_venues = {args.venue.upper()} if args.venue else PMLR_VENUES

    with open(DBLP_MERGE_FILE, encoding="utf-8") as f:
        papers = json.load(f)

    targets = [
        (i, p) for i, p in enumerate(papers)
        if p.get("venue") in target_venues and not (p.get("doi") or "").strip()
    ]
    print(f"Target papers (no DOI in {target_venues}): {len(targets)}", flush=True)

    found = missed = 0
    for j, (i, p) in enumerate(targets):
        title = (p.get("title") or "").rstrip(".")
        doi = search_arxiv(title)

        if doi:
            papers[i]["doi"] = doi
            found += 1
        else:
            missed += 1

        if (j + 1) % 100 == 0:
            print(f"  [{j+1}/{len(targets)}] found={found}, missed={missed}", flush=True)

        time.sleep(0.4)  # arXiv polite: 3 req/s max

    print(f"\n=== Done: found={found}, missed={missed} ({100*found/max(len(targets),1):.1f}%) ===", flush=True)

    with open(DBLP_MERGE_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False)
    print(f"Saved {DBLP_MERGE_FILE}", flush=True)


if __name__ == "__main__":
    main()
