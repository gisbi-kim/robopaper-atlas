"""Add Leiden community detection + TF-IDF topic labels to coauthor_network.json.

Runs AFTER _make_coauthor_network.py. Reads coauthor_network.json and
all_enriched.json, writes back to coauthor_network.json with extra fields
(in-place update — no new output file).

Added fields:
    nodes[i].community    int | None  — Leiden community id, None if node is
                                        outside the giant component at GIANT_THRESHOLD
    meta.communities      list        — per-community info:
        {id, size, top_authors, label_words, color}

Giant component is computed at the default HTML slider threshold (5 co-authored
papers), which is what the user sees on first load. Authors only visible at
lower thresholds fall outside and keep community=None.

Requires: networkx, leidenalg, igraph, scikit-learn
"""
import argparse
import html as htmllib
import json
import math
import re
from collections import defaultdict

import igraph as ig
import leidenalg
import networkx as nx
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from _clean import is_front_matter

COAUTHOR_JSON = "coauthor_network.json"
ENRICHED_JSON = "all_enriched.json"

GIANT_THRESHOLD = 5           # edge weight cutoff for Leiden (strong ties only)
BASE_THRESHOLD  = 2           # edge weight cutoff for the full graph (used for
                              #   neighbour-propagation + island detection)
ISLAND_MIN_SIZE = 10          # outside components this size or larger become
                              #   their own community; smaller ones go to "misc"
TOPIC_WORDS_PER_COMMUNITY = 10
TOP_AUTHORS_PER_COMMUNITY = 5
LEIDEN_SEED = 42
MISC_COLOR = 'hsl(0, 0%, 45%)'  # neutral grey for the misc lump

# Stop words tuned for robotics titles (common-but-uninformative terms).
_STOP = {
    'a', 'an', 'and', 'or', 'the', 'of', 'on', 'in', 'for', 'to', 'with',
    'via', 'using', 'based', 'new', 'novel', 'improved', 'approach', 'method',
    'methods', 'toward', 'towards', 'from', 'by', 'at', 'is', 'are', 'be',
    'this', 'that', 'these', 'those', 'we', 'its', 'their', 'our', 'as', 'not',
    'also', 'which', 'than', 'between', 'through', 'under', 'over', 'two',
    'three', 'four', 'one', 'robot', 'robots', 'robotic', 'robotics', 'system',
    'systems', 'control', 'controller', 'design', 'model', 'models', 'paper',
    'note', 'brief', 'case', 'study', 'application', 'applications',
    'algorithm', 'algorithms', 'research', 'results', 'into', 'such', 'can',
    'has', 'have', 'had', 'was', 'were', 'been', 'being', 'do', 'does', 'did',
    'done', 'real', 'online', 'offline', 'performance', 'evaluation',
    'framework', 'survey', 'review', 'experimental', 'simulation',
    'experiments', 'analysis', 'problem', 'problems', 'work', 'works',
    'technique', 'techniques', 'efficient', 'effective', 'fast', 'adaptive',
    'dynamic', 'static', 'general', 'generalized', 'learning', 'optimal',
    'optimization', 'planning', 'estimation', 'tracking', 'sensor', 'sensors',
    'data', 'time', 'high', 'low', 'non', 'multi', 'single', 'full', 'mobile',
    'field', 'task', 'tasks', 'part', 'parts',
}

_dblp_suffix = re.compile(r'\s+\d{4}$')


def clean_author(s: str) -> str:
    return _dblp_suffix.sub('', htmllib.unescape(s)).strip()


def community_color(cid: int, total: int) -> str:
    """HSL golden-angle hue spacing for stable, perceptually varied colors."""
    hue = (cid * 137.508) % 360
    # Alternate saturation/lightness by parity so adjacent hues look even more distinct
    sat = 70 if cid % 2 == 0 else 55
    light = 58 if cid % 3 == 0 else 50
    return f'hsl({hue:.1f}, {sat}%, {light}%)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--giant-threshold', type=int, default=GIANT_THRESHOLD,
                    help='edge weight cutoff for Leiden subdivision of the mainland')
    ap.add_argument('--base-threshold', type=int, default=BASE_THRESHOLD,
                    help='edge weight cutoff for full graph (propagation + islands)')
    args = ap.parse_args()

    # 1) Load coauthor network
    with open(COAUTHOR_JSON, encoding='utf-8') as f:
        data = json.load(f)
    nodes = data['nodes']
    edges = data['edges']
    nid_to_label = {n['id']: n['label'] for n in nodes}
    print(f'Loaded {len(nodes):,} nodes, {len(edges):,} edges from {COAUTHOR_JSON}')

    # 2) Build the mainland (giant component at strong-tie threshold)
    G_strong = nx.Graph()
    for e in edges:
        if e['weight'] >= args.giant_threshold:
            G_strong.add_edge(e['source'], e['target'], weight=e['weight'])
    if G_strong.number_of_nodes() == 0:
        print(f'No edges at giant_threshold {args.giant_threshold} — aborting.')
        return
    mainland = max(nx.connected_components(G_strong), key=len)
    Gi = G_strong.subgraph(mainland).copy()
    print(f'Mainland (weight>={args.giant_threshold}): '
          f'{Gi.number_of_nodes():,} nodes, {Gi.number_of_edges():,} edges')

    # 3) Leiden on the mainland
    ig_nodes = list(Gi.nodes())
    ig_idx = {v: i for i, v in enumerate(ig_nodes)}
    g = ig.Graph(
        n=len(ig_nodes),
        edges=[(ig_idx[u], ig_idx[v]) for u, v in Gi.edges()],
        directed=False,
    )
    g.es['weight'] = [Gi[u][v]['weight'] for u, v in Gi.edges()]
    partition = leidenalg.find_partition(
        g, leidenalg.ModularityVertexPartition,
        weights='weight', seed=LEIDEN_SEED,
    )
    node_to_cid: dict[int, int] = {}
    for local_cid, members in enumerate(partition):
        for i in members:
            node_to_cid[ig_nodes[i]] = local_cid
    print(f'Leiden on mainland: {len(partition)} communities  '
          f'(modularity Q = {partition.modularity:.4f})')

    # 4) Propagate labels outward using the full (weight>=base) graph. Unassigned
    #    nodes adopt the community of their strongest-connected assigned neighbour.
    adj_full: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for e in edges:
        if e['weight'] >= args.base_threshold:
            adj_full[e['source']].append((e['target'], e['weight']))
            adj_full[e['target']].append((e['source'], e['weight']))
    n_before = len(node_to_cid)
    for _ in range(20):  # usually converges in 2-3 passes
        changed = False
        for nid in list(adj_full.keys()):
            if nid in node_to_cid:
                continue
            votes: dict[int, int] = defaultdict(int)
            for nb, w in adj_full[nid]:
                if nb in node_to_cid:
                    votes[node_to_cid[nb]] += w
            if votes:
                node_to_cid[nid] = max(votes.items(), key=lambda kv: kv[1])[0]
                changed = True
        if not changed:
            break
    propagated = len(node_to_cid) - n_before
    print(f'Label propagation attached {propagated:,} fringe nodes '
          f'to existing Leiden communities.')

    # 5) Remaining unassigned nodes live in islands disconnected from the
    #    mainland. Group them into connected components at weight>=base.
    unassigned = {nid for nid in adj_full if nid not in node_to_cid}
    G_un = nx.Graph()
    G_un.add_nodes_from(unassigned)
    for e in edges:
        if (e['weight'] >= args.base_threshold
                and e['source'] in unassigned and e['target'] in unassigned):
            G_un.add_edge(e['source'], e['target'])
    island_comps = sorted(nx.connected_components(G_un), key=len, reverse=True)
    next_cid = max(node_to_cid.values()) + 1
    n_island_comms = 0
    misc_members: list[int] = []
    for comp in island_comps:
        if len(comp) >= ISLAND_MIN_SIZE:
            for m in comp:
                node_to_cid[m] = next_cid
            next_cid += 1
            n_island_comms += 1
        else:
            misc_members.extend(comp)
    misc_cid = next_cid if misc_members else None
    if misc_cid is not None:
        for m in misc_members:
            node_to_cid[m] = misc_cid
    print(f'Islands (size >= {ISLAND_MIN_SIZE}): {n_island_comms} communities. '
          f'Misc bucket: {len(misc_members)} authors across smaller islands.')

    # 6) Renumber by size descending (but pin misc to the last slot so its
    #    neutral colour doesn't land in the middle of the palette).
    sizes = defaultdict(int)
    for cid in node_to_cid.values():
        sizes[cid] += 1
    ordered = sorted(
        (cid for cid in sizes if cid != misc_cid),
        key=lambda c: -sizes[c],
    )
    old_to_new = {old: new for new, old in enumerate(ordered)}
    new_misc_cid = len(ordered) if misc_cid is not None else None
    if misc_cid is not None:
        old_to_new[misc_cid] = new_misc_cid
    node_to_cid = {nid: old_to_new[cid] for nid, cid in node_to_cid.items()}
    n_comm = len(ordered) + (1 if misc_cid is not None else 0)

    # 7) Author titles for TF-IDF
    print('Loading all_enriched.json for topic extraction...')
    with open(ENRICHED_JSON, encoding='utf-8') as f:
        papers = json.load(f)
    author_titles: dict[str, list[str]] = defaultdict(list)
    for p in papers:
        title = htmllib.unescape((p.get('title') or '').strip()).rstrip('.').strip()
        if not title or is_front_matter(title):
            continue
        a_str = (p.get('authors') or '').strip()
        if not a_str:
            continue
        for a in a_str.split(';'):
            name = clean_author(a)
            if name:
                author_titles[name].append(title.lower())

    # 8) TF-IDF across communities. Misc is given a flat document so it gets
    #    low TF-IDF scores everywhere (and we override its label below anyway).
    comm_members: dict[int, list[int]] = defaultdict(list)
    for nid, cid in node_to_cid.items():
        comm_members[cid].append(nid)

    comm_docs = [''] * n_comm
    for cid, members in comm_members.items():
        comm_docs[cid] = ' '.join(
            t for m in members for t in author_titles.get(nid_to_label[m], [])
        )
    vec = TfidfVectorizer(
        max_df=0.5, min_df=3,
        stop_words=sorted(_STOP),
        token_pattern=r'[A-Za-z][A-Za-z-]{2,}',
    )
    X = vec.fit_transform(comm_docs)
    vocab = vec.get_feature_names_out()

    # 9) Per-community metadata. Hub ranking uses weighted degree in the full
    #    (weight>=base) graph so island hubs are meaningful too.
    G_full = nx.Graph()
    for e in edges:
        if e['weight'] >= args.base_threshold:
            G_full.add_edge(e['source'], e['target'], weight=e['weight'])

    communities_meta = []
    for cid in range(n_comm):
        members_nids = comm_members.get(cid, [])
        is_misc = (cid == new_misc_cid)
        if is_misc:
            top_auth, words, color = [], [], MISC_COLOR
        else:
            top_auth = sorted(
                members_nids,
                key=lambda v: -G_full.degree(v, weight='weight') if G_full.has_node(v) else 0,
            )[:TOP_AUTHORS_PER_COMMUNITY]
            row = X[cid].toarray().flatten()
            top_word_idx = np.argsort(-row)[:TOPIC_WORDS_PER_COMMUNITY]
            words = [vocab[i] for i in top_word_idx if row[i] > 0]
            color = community_color(cid, n_comm)
        communities_meta.append({
            'id': cid,
            'size': len(members_nids),
            'top_authors': [nid_to_label[v] for v in top_auth],
            'label_words': words,
            'color': color,
            'misc': is_misc,
        })

    # 10) Write back
    for n in nodes:
        cid = node_to_cid.get(n['id'])
        n['community'] = cid if cid is not None else None
    data['meta']['communities'] = communities_meta
    data['meta']['community_giant_threshold'] = args.giant_threshold
    data['meta']['community_base_threshold'] = args.base_threshold
    data['meta']['community_island_min_size'] = ISLAND_MIN_SIZE

    with open(COAUTHOR_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

    n_in = sum(1 for n in nodes if n.get('community') is not None)
    print(f'\nWrote {COAUTHOR_JSON} with community field on {n_in:,}/{len(nodes):,} nodes.')
    print(f'Total communities: {n_comm}  (mainland-Leiden {len(partition)} + '
          f'islands {n_island_comms}' + (' + misc 1' if misc_cid is not None else '') + ')')
    print()
    print('Top 10 communities by size:')
    for c in communities_meta[:10]:
        authors = ', '.join(c['top_authors'][:3]) or '(none)'
        words = ' · '.join(c['label_words']) or '(none)'
        tag = ' [misc]' if c['misc'] else ''
        print(f'  [{c["id"]:>3}] {c["size"]:>4,}{tag}  — {authors}')
        print(f'         words: {words}')
    # Also show the misc bucket summary if present
    misc = next((c for c in communities_meta if c['misc']), None)
    if misc:
        print(f'\nMisc bucket: {misc["size"]:,} authors across many small islands '
              f'(<{ISLAND_MIN_SIZE} members each).')


if __name__ == '__main__':
    main()
