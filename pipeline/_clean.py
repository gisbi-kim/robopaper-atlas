"""Shared cleanup predicates.

OpenAlex (and occasionally DBLP) indexes journal front-matter — Table of
Contents, Editorial, Publication Information, yearly Index listings — as
"works" with an author attached. These pollute counts, inflate hubs in the
co-author network, and show up as nonsense in top-cited lists.

`is_front_matter(title)` returns True for these entries. Used by the views
that read `all_enriched.json` (step3_excel, _make_all_html, _make_coauthor_network).
"""
from __future__ import annotations

import re

# Whole title exactly one of these (case-insensitive, trailing period stripped).
FRONT_MATTER_EXACT = {
    'table of contents', 'front cover', 'back cover', 'blank page',
    'editorial', 'frontispiece', 'index', 'contents', 'toc',
    'publication information', 'information for authors',
    'masthead', 'colophon', 'title page',
}

# Title starts with one of these phrases — a plain prefix match means the
# whole thing is front-matter no matter what follows.
_FRONT_MATTER_PREFIX = re.compile(
    r'^(?:'
    r'table of contents\b|'
    r'front cover\b|'
    r'back cover\b|'
    r'blank page\b|'
    r'publication information\b|'
    r'information for authors\b|'
    r'\d{4}\s+index\s+ieee\b|'
    r'volume\s+\d+\s+index\b|'
    r'ieee\s*/\s*asme\s+transactions\s+on\s+mechatronics\s*'
    r'(?:-?\s*|:?\s*)(?:volume|vol\.?|publication\s+information)\b'
    r')',
    re.I,
)


def is_front_matter(title: str | None) -> bool:
    """True if the title looks like journal front-matter (TOC, editorial, etc.)."""
    t = (title or '').strip().rstrip('.').lower()
    if not t:
        return True
    if t in FRONT_MATTER_EXACT:
        return True
    return bool(_FRONT_MATTER_PREFIX.match(t))


# OpenAlex sometimes returns a Japanese (or other-language) translated copy of
# an English-only paper as a separate work — typically with an empty DOI and a
# title ending in '【Powered by NICT】'. Our ISSN-based fetch picks both up,
# polluting T-Mech / T-ASE with duplicate non-English titles.
_TRANSLATED_TITLE = re.compile(
    r'[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]'   # any Japanese / Chinese / Korean char
    r'|【\s*Powered\s+by\s+NICT\s*】',              # NICT translator stamp
    re.I,
)


def is_translated_dup(title: str | None) -> bool:
    """True if title looks like a non-English translation artifact (drop these)."""
    if not title:
        return False
    return bool(_TRANSLATED_TITLE.search(title))
