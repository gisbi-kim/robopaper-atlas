"""
Step 2: OpenAlex API로 초록/인용수/키워드 보강
- DOI 배치 필터로 한 번에 최대 50개씩 쿼리 (훨씬 빠름)
- 결과를 50편마다 체크포인트 저장
- 중단 후 재실행하면 이미 처리한 것 스킵

실행: python step2_openalex.py
예상 소요: 1~3시간 (총 편수 / 50 × 요청 시간)

OpenAlex:
- 무료, API키 없어도 됨
- polite pool 가입용 이메일만 User-Agent에 넣으면 우선순위 상승
- rate limit: 공식 10 req/sec, polite pool은 더 여유
"""
import requests
import time
import json
import os

from _checkpoint import load_checkpoint, save_checkpoint

INPUT = "all_dblp.json"
OUT_FILE = "all_enriched.json"
BATCH_SIZE = 50  # OpenAlex DOI 필터 한 번에 최대 50개

# !!! 여기에 본인 이메일 넣으세요 (polite pool용) !!!
USER_EMAIL = "gisbi.kim@gmail.com"


def reconstruct_abstract(inv_idx):
    """OpenAlex의 abstract_inverted_index → 평문 복원"""
    if not inv_idx:
        return ''
    try:
        max_pos = max((max(positions) for positions in inv_idx.values()), default=-1)
        words = [''] * (max_pos + 1)
        for word, positions in inv_idx.items():
            for pos in positions:
                if pos < len(words):
                    words[pos] = word
        return ' '.join(w for w in words if w)
    except Exception:
        return ''


def fetch_batch(dois):
    """DOI 리스트를 OpenAlex에 배치 쿼리"""
    # OpenAlex filter: doi:X|Y|Z (pipe 구분)
    doi_filter = '|'.join(f"https://doi.org/{d}" for d in dois)
    url = "https://api.openalex.org/works"
    params = {
        'filter': f'doi:{doi_filter}',
        'per-page': len(dois),
        'mailto': USER_EMAIL,
    }

    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.json().get('results', [])
            elif r.status_code == 429:
                print(f"      rate limited, waiting 60s...")
                time.sleep(60)
            else:
                print(f"      HTTP {r.status_code}")
                time.sleep(5)
        except Exception as e:
            print(f"      error: {e}")
            time.sleep(5)
    return []


def main():
    # 입력 로드
    with open(INPUT, encoding='utf-8') as f:
        papers = json.load(f)
    print(f"Total papers: {len(papers)}")

    # DOI별 인덱스 (DOI 없는 건 따로)
    doi_to_paper = {}
    no_doi = []
    for p in papers:
        doi = p.get('doi', '').strip().lower()
        if doi:
            # 정규화: https://doi.org/ 프리픽스 제거
            if doi.startswith('https://doi.org/'):
                doi = doi[len('https://doi.org/'):]
            elif doi.startswith('http://doi.org/'):
                doi = doi[len('http://doi.org/'):]
            doi_to_paper[doi] = p
        else:
            no_doi.append(p)

    print(f"With DOI: {len(doi_to_paper)}")
    print(f"No DOI:   {len(no_doi)}")

    # 체크포인트 로드 (샤드로 분할 저장됨 — _checkpoint.py 참조)
    enriched = load_checkpoint()
    processed_dois = set(enriched.keys())
    if processed_dois:
        print(f"Resuming from checkpoint: {len(processed_dois)} already processed")

    # 배치 처리
    all_dois = [d for d in doi_to_paper.keys() if d not in processed_dois]
    print(f"Remaining: {len(all_dois)}")

    for i in range(0, len(all_dois), BATCH_SIZE):
        batch = all_dois[i:i+BATCH_SIZE]
        results = fetch_batch(batch)

        # 결과 파싱
        found_dois = set()
        for w in results:
            w_doi = (w.get('doi') or '').lower()
            if w_doi.startswith('https://doi.org/'):
                w_doi = w_doi[len('https://doi.org/'):]
            if not w_doi:
                continue
            found_dois.add(w_doi)

            concepts = w.get('concepts', [])[:5]
            # OpenAlex의 biblio.first_page-last_page 도 같이 추출 — DBLP가 비워둔 경우
            # 병합 단계에서 fallback으로 채워줌. 형식은 DBLP와 동일하게 "first-last".
            biblio = w.get('biblio') or {}
            fp, lp = biblio.get('first_page'), biblio.get('last_page')
            pages_oa = f'{fp}-{lp}' if fp and lp else (fp or lp or '')
            enriched[w_doi] = {
                'abstract': reconstruct_abstract(w.get('abstract_inverted_index')),
                'cited_by_count': w.get('cited_by_count', 0),
                'concepts': '; '.join([c.get('display_name', '') for c in concepts]),
                'openalex_id': w.get('id', ''),
                'pages_oa': pages_oa,
            }

        # 못 찾은 DOI도 빈 값으로 표시 (재처리 방지)
        for d in batch:
            if d not in found_dois:
                enriched[d] = {'abstract': '', 'cited_by_count': '', 'concepts': '', 'openalex_id': '', 'pages_oa': ''}

        done = i + len(batch)
        print(f"  [{done}/{len(all_dois)}] batch ok, found {len(found_dois)}/{len(batch)}")

        # 10 배치마다 체크포인트 저장 (500편)
        if (i // BATCH_SIZE) % 10 == 9:
            save_checkpoint(enriched)
            print(f"    checkpoint saved ({len(enriched)} entries)")

        time.sleep(0.2)  # ~5 req/sec, polite

    # 최종 저장
    save_checkpoint(enriched)

    # 병합: 원본 papers에 enriched 필드 추가
    for p in papers:
        doi = p.get('doi', '').strip().lower()
        if doi.startswith('https://doi.org/'):
            doi = doi[len('https://doi.org/'):]
        e = enriched.get(doi, {})
        p['abstract'] = e.get('abstract', '')
        p['cited_by_count'] = e.get('cited_by_count', '')
        p['concepts'] = e.get('concepts', '')
        p['openalex_id'] = e.get('openalex_id', '')
        # pages 백필: DBLP가 비워둔 경우 OpenAlex의 biblio 값으로 채움
        if not (p.get('pages') or '').strip() and e.get('pages_oa'):
            p['pages'] = e['pages_oa']

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(papers, f, ensure_ascii=False)

    # 통계
    with_abstract = sum(1 for p in papers if p.get('abstract'))
    print(f"\n=== DONE ===")
    print(f"Total: {len(papers)}")
    print(f"With abstract: {with_abstract} ({100*with_abstract/len(papers):.1f}%)")


if __name__ == '__main__':
    main()
