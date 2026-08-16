"""
Step 2: Semantic Scholar로 초록/인용수/분야 보강
(파일명은 기존 워크플로 호환을 위해 유지.)

- DOI 보유 논문: S2 batch API로 최대 500편씩 조회
- DOI 없는 PMLR 논문(CoRL): title-match를 한 번 수행해 S2 paper ID를
  별도 checkpoint에 저장하고, 이후 갱신은 paper ID batch API 사용

실행:
    python step2_openalex.py            # 신규/미수집 항목만
    python step2_openalex.py --refresh  # 기존 DOI + DOI-less S2 ID 전체 갱신

API key: 환경변수 S2_API_KEY (선택)
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from difflib import SequenceMatcher
import json
import os
import random
import time

import requests

from _checkpoint import load_checkpoint, save_checkpoint
from _doi_less_checkpoint import (
    load_doi_less_checkpoint,
    normalize_title,
    paper_key,
    save_doi_less_checkpoint,
)

INPUT = "all_dblp.json"
OUT_FILE = "all_enriched.json"
BATCH_SIZE = 500
S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
S2_BULK_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
S2_MATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search/match"
S2_FIELDS = (
    "title,year,abstract,citationCount,influentialCitationCount,"
    "fieldsOfStudy,externalIds"
)
DOI_LESS_VENUES = {"CoRL"}
S2_VENUE_NAMES = {"CoRL": "Conference on Robot Learning"}
TITLE_MATCH_MIN_RATIO = 0.90
S2_API_KEY = os.environ.get("S2_API_KEY", "")


def _headers() -> dict:
    return {"x-api-key": S2_API_KEY} if S2_API_KEY else {}


def _norm_doi(doi):
    doi = (doi or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


def _request_wait(response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After") if response is not None else None
    try:
        return max(1.0, float(retry_after))
    except (TypeError, ValueError):
        return 10.0 * (attempt + 1) + random.random() * 2.0


def fetch_batch_ids(ids: list[str]) -> list:
    """Fetch DOI-prefixed or native S2 IDs, preserving input order."""
    if not ids:
        return []
    body = {"ids": ids}
    params = {"fields": S2_FIELDS}
    for attempt in range(4):
        response = None
        try:
            response = requests.post(
                S2_BATCH_URL,
                json=body,
                params=params,
                headers=_headers(),
                timeout=120,
            )
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429 or response.status_code >= 500:
                wait = _request_wait(response, attempt)
                print(f"    S2 HTTP {response.status_code}, retry in {wait:.1f}s")
                time.sleep(wait)
                continue
            print(f"    S2 HTTP {response.status_code}: {response.text[:200]}")
            break
        except requests.RequestException as exc:
            wait = _request_wait(response, attempt)
            print(f"    S2 batch error: {exc}; retry in {wait:.1f}s")
            time.sleep(wait)
    print("    giving up on this batch -- moving on")
    return [None] * len(ids)


def fetch_doi_batch(dois: list[str]) -> list:
    return fetch_batch_ids([f"DOI:{doi}" for doi in dois])


def fetch_venue_bulk(venue: str, years: list[int]) -> list[dict]:
    """Fetch one venue with the official paginated bulk-search endpoint."""
    venue_name = S2_VENUE_NAMES[venue]
    year_range = f"{min(years)}-{max(years)}"
    token = None
    works = []
    while True:
        params = {
            "venue": venue_name,
            "year": year_range,
            "fields": S2_FIELDS,
            "sort": "paperId",
        }
        if token:
            params["token"] = token
        response = None
        for attempt in range(5):
            try:
                response = requests.get(
                    S2_BULK_URL,
                    params=params,
                    headers=_headers(),
                    timeout=120,
                )
                if response.status_code == 200:
                    break
                if response.status_code == 429 or response.status_code >= 500:
                    time.sleep(_request_wait(response, attempt))
                    continue
                print(f"    S2 bulk HTTP {response.status_code}: {response.text[:200]}")
                return works
            except requests.RequestException as exc:
                print(f"    S2 bulk error: {exc}")
                time.sleep(_request_wait(response, attempt))
        if response is None or response.status_code != 200:
            return works
        try:
            payload = response.json()
        except ValueError:
            print("    S2 bulk returned invalid JSON")
            return works
        works.extend(work for work in payload.get("data", []) if isinstance(work, dict))
        token = payload.get("token")
        if not token:
            print(f"  S2 venue bulk: {venue_name} -> {len(works)} records")
            return works


def _match_payload(response: requests.Response):
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"][0] if payload["data"] else None
    return payload if isinstance(payload, dict) else None


def _title_match_is_valid(paper: dict, work: dict) -> tuple[bool, float]:
    source = normalize_title(paper.get("title") or "")
    matched = normalize_title(work.get("title") or "")
    ratio = SequenceMatcher(None, source, matched).ratio() if source and matched else 0.0

    source_year = str(paper.get("year") or "")
    matched_year = str(work.get("year") or "")
    try:
        year_delta = abs(int(source_year) - int(matched_year))
    except (TypeError, ValueError):
        year_delta = 0

    source_dblp = (paper.get("dblp_key") or "").strip().lower()
    matched_dblp = str((work.get("externalIds") or {}).get("DBLP") or "").strip().lower()
    dblp_exact = bool(source_dblp and source_dblp == matched_dblp)
    valid = (
        (dblp_exact and year_delta <= 1)
        or (ratio >= 0.98 and year_delta <= 1)
        or (ratio >= TITLE_MATCH_MIN_RATIO and year_delta == 0)
    )
    return valid, ratio


def _fields_of_study(work: dict) -> list[str]:
    fields = []
    for field in work.get("fieldsOfStudy") or []:
        value = field.get("category", "") if isinstance(field, dict) else field
        if value:
            fields.append(str(value))
    return fields


def _update_entry(entry: dict, work: dict) -> None:
    citation_count = work.get("citationCount")
    influential = work.get("influentialCitationCount")
    abstract = (work.get("abstract") or "").strip()
    fields = _fields_of_study(work)

    if citation_count is not None:
        entry["cited_by_s2"] = citation_count
    if influential is not None:
        entry["influential_cites_s2"] = influential
    if abstract:
        entry["abstract"] = abstract
    if fields:
        entry["concepts"] = "; ".join(fields)
    if work.get("paperId"):
        entry["s2_paper_id"] = work["paperId"]
    if work.get("externalIds"):
        entry["external_ids"] = work["externalIds"]
    entry["last_checked"] = time.strftime("%Y-%m-%d")


def fetch_title_match(paper: dict) -> tuple[str, dict]:
    """Resolve one DOI-less paper and return its checkpoint update."""
    key = paper_key(paper)
    query = (paper.get("title") or "").rstrip(".").strip()
    for attempt in range(5):
        response = None
        try:
            response = requests.get(
                S2_MATCH_URL,
                params={"query": query, "fields": S2_FIELDS},
                headers=_headers(),
                timeout=60,
            )
            if response.status_code == 200:
                work = _match_payload(response)
                if not isinstance(work, dict):
                    return key, {"lookup_status": "not_found", "last_checked": time.strftime("%Y-%m-%d")}
                valid, ratio = _title_match_is_valid(paper, work)
                if not valid:
                    return key, {
                        "lookup_status": "rejected",
                        "matched_title": work.get("title", ""),
                        "matched_year": work.get("year", ""),
                        "title_match_ratio": round(ratio, 4),
                        "last_checked": time.strftime("%Y-%m-%d"),
                    }
                entry = {
                    "lookup_status": "matched",
                    "matched_title": work.get("title", ""),
                    "matched_year": work.get("year", ""),
                    "title_match_ratio": round(ratio, 4),
                }
                _update_entry(entry, work)
                return key, entry
            if response.status_code == 404:
                return key, {"lookup_status": "not_found", "last_checked": time.strftime("%Y-%m-%d")}
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(_request_wait(response, attempt))
                continue
            return key, {
                "lookup_status": f"http_{response.status_code}",
                "last_checked": time.strftime("%Y-%m-%d"),
            }
        except requests.RequestException:
            time.sleep(_request_wait(response, attempt))
    return key, {"lookup_status": "request_failed", "last_checked": time.strftime("%Y-%m-%d")}


def _seed_from_venue_bulk(
    targets: list[dict],
    checkpoint: dict,
) -> int:
    """Resolve DOI-less targets by exact DBLP ID or normalized title/year."""
    unresolved = [
        paper for paper in targets
        if not checkpoint.get(paper_key(paper), {}).get("s2_paper_id")
    ]
    if not unresolved:
        return 0

    matched = 0
    for venue in sorted(DOI_LESS_VENUES):
        venue_targets = [paper for paper in unresolved if paper.get("venue") == venue]
        years = []
        for paper in venue_targets:
            try:
                years.append(int(paper.get("year")))
            except (TypeError, ValueError):
                pass
        if not venue_targets or not years or venue not in S2_VENUE_NAMES:
            continue
        works = fetch_venue_bulk(venue, years)
        by_dblp = {}
        by_title_year = defaultdict(list)
        for work in works:
            dblp_id = str((work.get("externalIds") or {}).get("DBLP") or "").lower()
            if dblp_id:
                by_dblp[dblp_id] = work
            key = (str(work.get("year") or ""), normalize_title(work.get("title") or ""))
            by_title_year[key].append(work)

        for paper in venue_targets:
            source_dblp = (paper.get("dblp_key") or "").strip().lower()
            work = by_dblp.get(source_dblp)
            if work is None:
                title_key = (
                    str(paper.get("year") or ""),
                    normalize_title(paper.get("title") or ""),
                )
                candidates = by_title_year.get(title_key, [])
                if candidates:
                    work = max(
                        candidates,
                        key=lambda item: (
                            str((item.get("externalIds") or {}).get("DBLP") or "").startswith("conf/corl/"),
                            item.get("citationCount") or 0,
                        ),
                    )
            if not isinstance(work, dict):
                continue
            valid, ratio = _title_match_is_valid(paper, work)
            if not valid:
                continue
            entry = {
                "lookup_status": "matched_bulk",
                "matched_title": work.get("title", ""),
                "matched_year": work.get("year", ""),
                "title_match_ratio": round(ratio, 4),
            }
            _update_entry(entry, work)
            checkpoint[paper_key(paper)] = entry
            matched += 1
    if matched:
        save_doi_less_checkpoint(checkpoint)
    print(f"  DOI-less venue bulk matched: {matched}/{len(unresolved)}")
    return matched


def _enrich_dois(papers: list[dict], enriched: dict, refresh: bool) -> None:
    todo = []
    for paper in papers:
        doi = _norm_doi(paper.get("doi"))
        if doi and (refresh or doi not in enriched or "cited_by_s2" not in enriched.get(doi, {})):
            todo.append(doi)

    print(f"DOIs to fetch from S2: {len(todo)} (refresh={refresh})")
    for offset in range(0, len(todo), BATCH_SIZE):
        batch = todo[offset:offset + BATCH_SIZE]
        results = fetch_doi_batch(batch)
        found = 0
        for doi, work in zip(batch, results):
            if not isinstance(work, dict):
                enriched.setdefault(doi, {}).setdefault("cited_by_s2", "")
                continue
            _update_entry(enriched.setdefault(doi, {}), work)
            enriched[doi].setdefault("openalex_id", "")
            enriched[doi].setdefault("pages_oa", "")
            found += 1
        print(f"  DOI [{offset + len(batch)}/{len(todo)}] batch ok ({found}/{len(batch)} found)")
        if (offset // BATCH_SIZE) % 5 == 4:
            save_checkpoint(enriched)
        time.sleep(3)


def _enrich_doi_less(
    papers: list[dict],
    checkpoint: dict,
    refresh: bool,
    retry_misses: bool,
    title_workers: int,
) -> None:
    targets = [
        paper for paper in papers
        if paper.get("venue") in DOI_LESS_VENUES and not _norm_doi(paper.get("doi"))
    ]
    by_key = {paper_key(paper): paper for paper in targets}

    _seed_from_venue_bulk(targets, checkpoint)

    known = []
    unresolved = []
    for key, paper in by_key.items():
        entry = checkpoint.get(key, {})
        if entry.get("s2_paper_id") and (refresh or "cited_by_s2" not in entry):
            known.append((key, entry["s2_paper_id"]))
        elif not entry or (retry_misses and not entry.get("s2_paper_id")):
            unresolved.append(paper)

    print(
        f"DOI-less {sorted(DOI_LESS_VENUES)}: {len(targets)} total, "
        f"{len(known)} S2-ID refresh, {len(unresolved)} title lookups"
    )

    for offset in range(0, len(known), BATCH_SIZE):
        batch = known[offset:offset + BATCH_SIZE]
        results = fetch_batch_ids([s2_id for _, s2_id in batch])
        found = 0
        for (key, _), work in zip(batch, results):
            if isinstance(work, dict):
                _update_entry(checkpoint.setdefault(key, {}), work)
                checkpoint[key]["lookup_status"] = "matched"
                found += 1
        print(f"  S2-ID [{offset + len(batch)}/{len(known)}] batch ok ({found}/{len(batch)} found)")
        save_doi_less_checkpoint(checkpoint)
        time.sleep(3)

    if unresolved:
        completed = matched = 0
        with ThreadPoolExecutor(max_workers=max(1, title_workers)) as pool:
            futures = {
                pool.submit(fetch_title_match, paper): paper for paper in unresolved
            }
            for future in as_completed(futures):
                paper = futures[future]
                try:
                    key, entry = future.result()
                except Exception as exc:
                    key = paper_key(paper)
                    entry = {
                        "lookup_status": "request_failed",
                        "error": type(exc).__name__,
                        "last_checked": time.strftime("%Y-%m-%d"),
                    }
                checkpoint[key] = entry
                completed += 1
                matched += entry.get("lookup_status") == "matched"
                if completed % 25 == 0 or completed == len(unresolved):
                    save_doi_less_checkpoint(checkpoint)
                    print(f"  title-match [{completed}/{len(unresolved)}] matched={matched}")


def _merge(papers: list[dict], enriched: dict, doi_less: dict) -> None:
    s2_filled = 0
    doi_less_filled = 0
    for paper in papers:
        doi = _norm_doi(paper.get("doi"))
        entry = enriched.get(doi, {}) if doi else doi_less.get(paper_key(paper), {})

        paper["abstract"] = entry.get("abstract", "")
        paper["concepts"] = entry.get("concepts", "")
        paper["openalex_id"] = entry.get("openalex_id", "")
        if entry.get("s2_paper_id"):
            paper["s2_paper_id"] = entry["s2_paper_id"]
        if not (paper.get("pages") or "").strip() and entry.get("pages_oa"):
            paper["pages"] = entry["pages_oa"]

        s2_citations = entry.get("cited_by_s2")
        if isinstance(s2_citations, int):
            paper["cited_by_count"] = s2_citations
            paper["cites_source"] = "s2"
            s2_filled += 1
            if not doi:
                doi_less_filled += 1
        else:
            paper["cited_by_count"] = entry.get("cited_by_count", "")
            paper["cites_source"] = "openalex" if doi else ""
        if entry.get("influential_cites_s2") is not None:
            paper["influential_cites"] = entry["influential_cites_s2"]

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False)

    print(f"S2 citations: {s2_filled}/{len(papers)} ({100 * s2_filled / len(papers):.1f}%)")
    print(f"DOI-less S2 citations: {doi_less_filled}")
    with_abstract = sum(1 for paper in papers if paper.get("abstract"))
    print(f"With abstract: {with_abstract}/{len(papers)} ({100 * with_abstract / len(papers):.1f}%)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="re-fetch all known S2 records")
    parser.add_argument(
        "--retry-doi-less-misses",
        action="store_true",
        help="retry DOI-less title matches previously marked missing/rejected",
    )
    parser.add_argument(
        "--title-workers",
        type=int,
        default=1,
        help="parallel DOI-less title lookups (default: 1; raise cautiously)",
    )
    args = parser.parse_args()

    with open(INPUT, encoding="utf-8") as f:
        papers = json.load(f)
    enriched = load_checkpoint()
    doi_less = load_doi_less_checkpoint()
    if not enriched:
        print("WARNING: DOI checkpoint is empty -- first-time run.")

    _enrich_dois(papers, enriched, args.refresh)
    save_checkpoint(enriched)
    _enrich_doi_less(
        papers,
        doi_less,
        args.refresh,
        args.retry_doi_less_misses,
        args.title_workers,
    )
    save_doi_less_checkpoint(doi_less)
    print("\n=== merging into all_enriched.json ===")
    _merge(papers, enriched, doi_less)


if __name__ == "__main__":
    main()
