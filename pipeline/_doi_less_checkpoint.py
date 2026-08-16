"""Checkpoint helpers for papers that do not have a DOI.

DOI-backed enrichment remains in ``enriched_checkpoint_*.json``. PMLR
conference papers such as CoRL are keyed by their stable DBLP key instead.
"""
import html
import json
import os
import re
import unicodedata


CHECKPOINT_FILE = "enriched_doi_less_checkpoint.json"


def normalize_title(title: str) -> str:
    """Return a conservative comparison form for title-match validation."""
    text = unicodedata.normalize("NFKC", html.unescape(title or "")).lower()
    text = re.sub(r"\\([a-z]+)", r"\1", text)
    return "".join(ch for ch in text if ch.isalnum())


def paper_key(paper: dict) -> str:
    """Build a stable key without pretending that a non-DOI is a DOI."""
    dblp_key = (paper.get("dblp_key") or "").strip()
    if dblp_key:
        return f"dblp:{dblp_key}"
    venue = (paper.get("venue") or "").strip()
    year = str(paper.get("year") or "").strip()
    return f"title:{venue}|{year}|{normalize_title(paper.get('title') or '')}"


def load_doi_less_checkpoint(path: str = CHECKPOINT_FILE) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_doi_less_checkpoint(data: dict, path: str = CHECKPOINT_FILE) -> None:
    """Atomically save the small DOI-less lookup cache."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)
