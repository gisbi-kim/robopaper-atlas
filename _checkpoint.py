"""Sharded checkpoint I/O for enriched data.

The single `enriched_checkpoint.json` grew past GitHub's 100 MB per-file limit
after we added 3 venues. Split into N stable shards so each file stays well
under the limit, and so `git diff` on incremental refreshes only rewrites the
shards that actually changed.

Sharding: hash(doi) mod N — deterministic, so the same DOI always lands in
the same shard across runs and machines.
"""
import hashlib
import json
import os

CHECKPOINT_PREFIX = "enriched_checkpoint_"
CHECKPOINT_SHARDS = 3
LEGACY_CHECKPOINT = "enriched_checkpoint.json"


def _shard_for(key: str) -> int:
    h = hashlib.blake2s(key.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(h, "big") % CHECKPOINT_SHARDS


def _shard_path(i: int) -> str:
    return f"{CHECKPOINT_PREFIX}{i:02d}.json"


def load_checkpoint() -> dict:
    """Load all shards (and absorb legacy single-file if still present)."""
    enriched: dict = {}
    for i in range(CHECKPOINT_SHARDS):
        p = _shard_path(i)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                enriched.update(json.load(f))
    if os.path.exists(LEGACY_CHECKPOINT):
        with open(LEGACY_CHECKPOINT, encoding="utf-8") as f:
            enriched.update(json.load(f))
    return enriched


def save_checkpoint(enriched: dict) -> None:
    """Write the enriched dict partitioned across shards."""
    shards: list[dict] = [{} for _ in range(CHECKPOINT_SHARDS)]
    for k, v in enriched.items():
        shards[_shard_for(k)][k] = v
    for i, shard in enumerate(shards):
        with open(_shard_path(i), "w", encoding="utf-8") as f:
            json.dump(shard, f, ensure_ascii=False)
