"""Import the complete ICRA 2026 Crossref proceedings, preserving other venues.

Run from pipeline. Exact container title + DOI prefix validation; cursor
pagination must match Crossref's reported total before any merge is written.
"""
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from step1c_crossref_conferences import _to_record
from _checkpoint import load_checkpoint, save_checkpoint
from _doi_less_checkpoint import load_doi_less_checkpoint
from step2_openalex import _enrich_dois, _merge

TITLE = '2026 IEEE International Conference on Robotics and Automation (ICRA)'
SNAPSHOT = Path('publisher_raw/icra_2026_crossref_2026-10-16.json')

def collect():
    records = {}
    cursor = '*'
    total = None
    while True:
        for attempt in range(4):
            r = requests.get('https://api.crossref.org/works', params={
                'filter': f'container-title:{TITLE},type:proceedings-article',
                'rows': 1000, 'cursor': cursor,
            }, timeout=90)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        r.raise_for_status()
        data = r.json()['message']
        if total is None:
            total = data['total-results']
        assert total == data['total-results'], 'Source total changed during collection'
        for item in data['items']:
            assert item['container-title'] == [TITLE]
            row = _to_record(item, 'ICRA', 2026)
            assert row['doi'].startswith('10.1109/icra57385.2026.')
            assert row['year'] == '2026' and row['title']
            row['metadata_source'] = 'Crossref'
            row['metadata_retrieved'] = '2026-10-16'
            if item.get('abstract'):
                row['publisher_abstract'] = BeautifulSoup(item['abstract'], 'html.parser').get_text(' ', strip=True)
            records[row['doi']] = row
        print(f'ICRA 2026: {len(records)}/{total}', flush=True)
        if len(records) == total:
            break
        assert data['items'] and data['next-cursor'] != cursor, 'Incomplete pagination'
        cursor = data['next-cursor']
        time.sleep(0.5)
    assert total and len(records) == total
    rows = sorted(records.values(), key=lambda p: p['doi'])
    SNAPSHOT.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    return rows

def main():
    rows = collect()
    missing = [p for p in rows if not p['authors'] and not p['title'].startswith('ICRA 2026 ')]
    if missing:
        r = requests.post('https://api.semanticscholar.org/graph/v1/paper/batch',
            params={'fields': 'title,authors,externalIds'},
            json={'ids': ['DOI:' + p['doi'] for p in missing]}, timeout=90)
        r.raise_for_status()
        for row, work in zip(missing, r.json()):
            assert work and work.get('externalIds', {}).get('DOI', '').lower() == row['doi'], row
            row['authors'] = '; '.join(a['name'] for a in work.get('authors', []) if a.get('name'))
            assert row['authors'], row
            row['authors_source'] = 'Semantic Scholar DOI match'
        SNAPSHOT.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    path = Path('all_dblp.json')
    papers = json.loads(path.read_text(encoding='utf-8'))
    seen = {(p['venue'], p.get('doi', '').lower()) for p in papers}
    added = [p for p in rows if (p['venue'], p['doi']) not in seen]
    papers.extend(added)
    path.write_text(json.dumps(papers, ensure_ascii=False), encoding='utf-8')
    checkpoint = load_checkpoint()
    _enrich_dois(added, checkpoint, False)
    save_checkpoint(checkpoint)
    _merge(papers, checkpoint, load_doi_less_checkpoint())
    print(f'ICRA 2026: added {len(added)} raw records', flush=True)

if __name__ == '__main__':
    main()
