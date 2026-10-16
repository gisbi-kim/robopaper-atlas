"""Refresh recent journal metadata using publisher deposits in Crossref.

Only journal records are merged; conference caches are never re-imported.
Run from pipeline: python refresh_journals_crossref.py
"""
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from step1c_crossref_conferences import _to_record

JOURNALS = [
    ('ral', 'RA-L', '2377-3766'), ('tro', 'T-RO', '1552-3098'),
    ('ijrr', 'IJRR', '0278-3649'), ('ram', 'RAM', '1070-9932'),
    ('scirob', 'Sci-Rob', '2470-9476'), ('soro', 'SoRo', '2169-5172'),
    ('tmech', 'T-Mech', '1083-4435'), ('tfr', 'T-FR', '2997-1101'),
    ('rap', 'RA-P', '2995-4304'), ('tase', 'T-ASE', '1545-5955'),
]

def fetch(issn, label):
    cursor = '*'
    records = {}
    expected = None
    while True:
        for attempt in range(4):
            response = requests.get(f'https://api.crossref.org/journals/{issn}/works',
                params={'filter': 'from-pub-date:2025-01-01,until-pub-date:2026-10-16',
                        'rows': 1000, 'cursor': cursor}, timeout=90)
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            response.raise_for_status()
            break
        response.raise_for_status()
        message = response.json()['message']
        expected = message['total-results'] if expected is None else expected
        items = message['items']
        if not items:
            break
        for item in items:
            assert issn in item.get('ISSN', []), (label, item.get('ISSN'))
            row = _to_record(item, label, 2026)
            if not row['doi']:
                raise RuntimeError('Missing Crossref DOI')
            row['metadata_source'] = 'Crossref'
            row['metadata_retrieved'] = '2026-10-16'
            if item.get('abstract'):
                row['publisher_abstract'] = BeautifulSoup(item['abstract'], 'html.parser').get_text(' ', strip=True)
            records[row['doi']] = row
        print(f'{label}: {len(records)}/{expected}', flush=True)
        if len(records) >= expected:
            break
        next_cursor = message['next-cursor']
        if next_cursor == cursor:
            raise RuntimeError(f'Stalled cursor: {label}')
        cursor = next_cursor
        time.sleep(0.5)
    if len(records) != expected:
        raise RuntimeError(f'Incomplete {label}: {len(records)}/{expected}')
    return list(records.values())

def main():
    out = Path('publisher_raw')
    rows = []
    for key, label, issn in JOURNALS:
        path = out / f'{key}_crossref_2026-10-16.json'
        if path.exists():
            found = json.loads(path.read_text(encoding='utf-8'))
        else:
            found = fetch(issn, label)
            path.write_text(json.dumps(found, ensure_ascii=False), encoding='utf-8')
        rows.extend(found)
    path = Path('all_dblp.json')
    papers = json.loads(path.read_text(encoding='utf-8'))
    existing = {(p['venue'], p.get('doi', '').lower()): p for p in papers if p.get('doi')}
    counts = {}
    for row in rows:
        key = (row['venue'], row['doi'])
        if key in existing:
            old = existing[key]
            for field, value in row.items():
                if value and not old.get(field):
                    old[field] = value
        else:
            papers.append(row)
            existing[key] = row
            counts[row['venue']] = counts.get(row['venue'], 0) + 1
    path.write_text(json.dumps(papers, ensure_ascii=False), encoding='utf-8')
    print('Added raw records:', counts, flush=True)

if __name__ == '__main__':
    main()
