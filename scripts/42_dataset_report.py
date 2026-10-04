"""Summarise a demonstration dataset: episodes, sizes, arms, categories, frames.

    python scripts/42_dataset_report.py datasets/demos_physical_v2 ...
"""

from __future__ import annotations

import collections
import json
import os
import sys


def report(path: str) -> None:
    index = os.path.join(path, "index.json")
    if not os.path.exists(index):
        print(f"{path}: no index.json")
        return
    with open(index, encoding="utf-8") as fh:
        episodes = json.load(fh)
    frames = sum(int(e.get("frames", 0)) for e in episodes)
    sizes = sorted(float(e.get("diameter", 0.0)) * 100 for e in episodes)
    buckets = collections.Counter(
        "2-4cm" if d < 4 else ("4-6cm" if d < 6 else "6-8cm") for d in sizes
    )
    print(f"\n{path}")
    print(f"  episodes={len(episodes)}  frames={frames}")
    if sizes:
        print(f"  diameter: min={sizes[0]:.1f} p50={sizes[len(sizes) // 2]:.1f} max={sizes[-1]:.1f} cm")
        print(f"  buckets: {dict(buckets)}")
    print(f"  arms: {dict(collections.Counter(e.get('arm') for e in episodes))}")
    print(f"  categories: {dict(collections.Counter(e.get('category') for e in episodes))}")


def main() -> int:
    paths = sys.argv[1:] or ["datasets/demos_physical_all"]
    for path in paths:
        report(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
