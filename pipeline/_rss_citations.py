"""Apply the audited RSS citation snapshot to newly built explorer rows.
Only the Full Explorer uses this snapshot; raw checkpoints and Excel are unchanged.
Replace this snapshot when performing the next RSS citation refresh.
"""
import json
from pathlib import Path

def with_rss_citations(rows):
    """Return copied rows with exact DOI/title/year-matched RSS citation counts."""
    path = Path(__file__).with_name("rss_citations_2026-10-17.json")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    updates = {entry["doi"]: entry for entry in snapshot["entries"]}
    result = []
    for row in rows:
        copy = list(row)
        entry = updates.get(copy[5])
        if (copy[0] == "RSS" and entry is not None
                and copy[1] == entry["year"] and copy[2] == entry["title"]):
            copy[4] = entry["cited_by_count"]
            if len(copy) > 9:
                copy[9] = False
        result.append(copy)
    return result
