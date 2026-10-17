"""Apply the audited T-RO/CoRL/IJRR citation snapshot to explorer rows.
Replace the dated snapshot at the next citation refresh.
Raw checkpoints and exports are not modified by this explorer-only overlay.
"""
import json
from pathlib import Path

def with_trio_citations(rows):
    """Return copied rows; match venue, year, title and DOI exactly."""
    path = Path(__file__).with_name("trio_citations_2026-10-17.json")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    updates = {
        (e["venue"], e["year"], e["title"], e["doi"]): e["cited_by_count"]
        for e in snapshot["entries"]
    }
    result = []
    for row in rows:
        copy = list(row)
        key = (copy[0], copy[1], copy[2], copy[5])
        if key in updates:
            copy[4] = updates[key]
            if len(copy) > 9:
                copy[9] = False
        result.append(copy)
    return result
