#!/usr/bin/env python3
"""Merge `--record` shard directories into one store (P145).

`111_rl_finetune.py --rollouts` takes one directory. A collection run writes one
subdirectory per seed (`direct_none_seed77`, ...), each with its own
`index.json`, so the shards have to be unioned before a fine-tune. Files are
symlinked, not copied - the store is read-only here.

    python3 logs/p145/merge_shards.py datasets/p145_dagger datasets/p145_dagger_all
"""
from __future__ import annotations

import json
import os
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src = sys.argv[1]
    dst = sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    entries: list[dict] = []
    seen: set[str] = set()
    shards = [
        d for d in sorted(os.listdir(src))
        if os.path.isdir(os.path.join(src, d))
        and os.path.exists(os.path.join(src, d, "index.json"))
    ]
    for shard in shards:
        path = os.path.join(src, shard, "index.json")
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh)
        for row in rows:
            name = f"{shard}__{row['file']}"
            if name in seen:
                continue
            seen.add(name)
            target = os.path.join(dst, name)
            if not os.path.exists(target):
                os.symlink(
                    os.path.abspath(os.path.join(src, shard, row["file"])), target
                )
            merged = dict(row)
            merged["file"] = name
            merged["shard"] = shard
            entries.append(merged)
    with open(os.path.join(dst, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2)
    n_frames = sum(int(r.get("frames", 0)) for r in entries)
    print(
        f"[merge] {len(shards)} shard(s) -> {dst}: {len(entries)} episodes, "
        f"{n_frames} frames"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
