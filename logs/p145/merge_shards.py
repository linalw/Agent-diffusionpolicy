#!/usr/bin/env python3
"""Merge `--record` shards into one store (P145).

`111_rl_finetune.py --rollouts` takes one directory. A collection writes one
`index.json` per shard (`direct_none_seed77`, ...); the chunked collection writes
one per chunk *and* per seed, so the stores are nested. This accepts any number
of sources: a source is either a store directory (has `index.json`) or a
directory whose immediate children are store directories.

Files are symlinked, not copied - the store is read-only here.

    python3 logs/p145/merge_shards.py datasets/p145_c01 ... datasets/p145_all
"""
from __future__ import annotations

import json
import os
import sys


def store_dirs(path: str) -> list[str]:
    """A source -> the store directories it contains (one level of nesting)."""
    if os.path.exists(os.path.join(path, "index.json")):
        return [path]
    found = []
    for name in sorted(os.listdir(path)):
        child = os.path.join(path, name)
        if os.path.isdir(child) and os.path.exists(os.path.join(child, "index.json")):
            found.append(child)
    return found


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    sources = sys.argv[1:-1]
    dst = sys.argv[-1]
    os.makedirs(dst, exist_ok=True)
    entries: list[dict] = []
    seen: set[str] = set()
    n_stores = 0
    for source in sources:
        for store in store_dirs(source):
            n_stores += 1
            with open(os.path.join(store, "index.json"), encoding="utf-8") as fh:
                rows = json.load(fh)
            tag = os.path.basename(os.path.normpath(store))
            for row in rows:
                name = f"{tag}__{row['file']}"
                if name in seen:
                    continue
                seen.add(name)
                target = os.path.join(dst, name)
                if not os.path.exists(target):
                    os.symlink(os.path.abspath(os.path.join(store, row["file"])), target)
                merged = dict(row)
                merged["file"] = name
                merged["shard"] = tag
                entries.append(merged)
    with open(os.path.join(dst, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2)
    frames = sum(int(r.get("frames", 0)) for r in entries)
    print(
        f"[merge] {len(sources)} source(s), {n_stores} store(s) -> {dst}: "
        f"{len(entries)} episodes, {frames} frames"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
