"""Merge several demonstration shards into one dataset.

Parallel collection workers each write their own directory; this concatenates
them, renumbering episodes and files so the result looks like a single run.

    python scripts/41_merge_demos.py --inputs datasets/shard0 datasets/shard1 --out datasets/demos_v5
"""

from __future__ import annotations

import argparse
import json
import os
import shutil


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    merged: list[dict] = []
    index = 0
    for src in args.inputs:
        index_path = os.path.join(src, "index.json")
        if not os.path.exists(index_path):
            print(f"skip {src}: no index.json")
            continue
        with open(index_path, encoding="utf-8") as fh:
            entries = json.load(fh)
        for entry in entries:
            if not entry.get("success"):
                continue
            dst_name = f"episode_{index:05d}.npz"
            shutil.copyfile(os.path.join(src, entry["file"]), os.path.join(args.out, dst_name))
            record = dict(entry)
            record["file"] = dst_name
            record["index"] = index
            record["shard"] = src
            merged.append(record)
            index += 1

    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
    print(f"merged {len(merged)} successful episodes into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
