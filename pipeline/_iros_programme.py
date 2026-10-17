"""Include the complete IROS 2026 programme in the explorer.

The source snapshot retains original author names and programme identifiers.
Zero citations are user-requested placeholders, not measured citation counts.
No DOI or paper URL is inferred. Other venue records are left unchanged.
"""
import json
from pathlib import Path


def with_iros_programme(rows):
    source = json.loads((Path(__file__).parent / 'iros2026_source.json').read_text(encoding='utf-8'))
    papers = source['papers']
    assert len(papers) == len({p['id'] for p in papers}) == 1933
    # Idempotent across rebuilds. Published IROS records take precedence if added later.
    norm = lambda title: ''.join(c for c in title.casefold() if c.isalnum())
    existing = {norm(r[2]) for r in rows if r[0] == 'IROS' and r[1] == 2026}
    added = []
    for paper in papers:
        if norm(paper['title']) in existing:
            continue
        authors = '; '.join(a['name'].strip() for a in paper['authors'])
        added.append(['IROS', 2026, paper['title'], authors, 0, '', 'IROS', 0, '', False])
    return [*rows, *added]
