"""
Split robopaper_atlas_all.xlsx 'papers' sheet into per-venue xlsx files.

실행: python _split_by_venue.py
출력: by_venue/<venue>.xlsx
"""
import os
import re
import pandas as pd

INPUT = "robopaper_atlas_all.xlsx"
OUT_DIR = "by_venue"

os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_excel(INPUT, sheet_name="papers")
print(f"loaded {len(df):,} papers")

def safe_name(v: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', '_', str(v)).strip() or "unknown"

for venue, sub in df.groupby("venue", sort=False):
    fname = os.path.join(OUT_DIR, f"{safe_name(venue)}.xlsx")
    sub.reset_index(drop=True).to_excel(fname, index=False, sheet_name="papers")
    print(f"  {venue:>8}: {len(sub):>6,} -> {fname}")

print("done.")
