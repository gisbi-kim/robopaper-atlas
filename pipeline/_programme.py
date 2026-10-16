"""Exact committed programme snapshots, not a general DOI-less exemption."""
import json
from pathlib import Path
ROWS = json.loads((Path(__file__).parent / "publisher_raw/corl_programme_2026.json").read_text(encoding="utf-8"))
ROWS += json.loads((Path(__file__).parent / "publisher_raw/ssrr_programme_2026.json").read_text(encoding="utf-8"))
BY_URL = {p["ee"]: p for p in ROWS}
def is_programme(row):
    ref = BY_URL.get(str(row.get("ee", "")))
    return bool(ref and row.get("venue") == ref["venue"] and str(row.get("year")) == str(ref["year"]) and str(row.get("title", "")).rstrip(".").strip() == ref["title"].rstrip(".").strip())
def programme_mask(df):
    return df.apply(is_programme, axis=1)
