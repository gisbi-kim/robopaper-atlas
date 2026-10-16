"""Import the user-specified SSRR 2026 explorer's accepted-paper programme.

Source data is committed in ssrr2026_source.json. No DOI, abstract or citation
is inferred from titles. Programme links filter the source explorer by title.
"""
import json
from pathlib import Path
from urllib.parse import quote
from collections import Counter

def main():
    source = json.loads(Path('ssrr2026_source.json').read_text(encoding='utf-8'))
    papers = source['papers']
    assert len(papers) == len({p['id'] for p in papers}) == len({p['title'] for p in papers}) == 46
    assert [Counter(p['session'] for p in papers)[i] for i in range(1,8)] == [6,8,8,6,8,6,4]
    sessions = {s['id']: s for s in source['sessions']}
    rows = []
    for p in papers:
        assert p['authors']
        url = 'https://gisbi-kim.github.io/conference-explorers/ssrr2026/?q=' + quote(p['title'], safe='') + '#finder'
        rows.append({'venue':'SSRR', 'year':'2026', 'title':p['title'],
            'authors':'; '.join(p['authors']), 'doi':'', 'ee':url,
            'explorer_url':url, 'pages':'', 'dblp_key':'',
            'metadata_source':'User-specified SSRR 2026 accepted-paper programme',
            'metadata_retrieved':source['snapshot'], 'source_provenance':source['provenance'],
            'programme_id':p['id'], 'session':sessions[p['session']]['title'],
            'session_start':sessions[p['session']]['schedule'],
            'award_finalist':p['awardFinalist'], 'publisher_abstract':''})
    Path('publisher_raw/ssrr_programme_2026.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
    path = Path('all_dblp.json')
    all_papers = json.loads(path.read_text(encoding='utf-8'))
    existing = {(p['venue'],p.get('ee','')) for p in all_papers}
    added = [p for p in rows if (p['venue'],p['ee']) not in existing]
    all_papers.extend(added)
    path.write_text(json.dumps(all_papers,ensure_ascii=False),encoding='utf-8')
    from _checkpoint import load_checkpoint
    from _doi_less_checkpoint import load_doi_less_checkpoint
    from step2_openalex import _merge
    _merge(all_papers,load_checkpoint(),load_doi_less_checkpoint())
    print(f'Added {len(added)} SSRR 2026 programme papers')

if __name__ == '__main__':
    main()
