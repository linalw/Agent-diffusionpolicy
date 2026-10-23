#!/usr/bin/env python3
"""P33 phase 3: read-only report over the post-pear recollection store.

    python3 logs/p33/C_store_report.py [--root datasets/p33_pear]

Prints the merged store's provenance (the shard manifests' pins), the episode /
frame / window counts, the per-arm and per-grade balance (the Gate-2 constraint:
the single-arm store is left-poor, the two-line is the balanced choice), the
fruit classes and diameters, and the per-shard contributions. Numbers only; no
judgement.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os


def md5(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.md5(handle.read()).hexdigest()
    except OSError:
        return ""


def windows(frames: int, obs_horizon: int = 2, action_horizon: int = 16) -> int:
    """Training windows per episode, the loader's own convention
    (`scripts/106_index_audit.py` `windows_of`: `frames - (obs+act) + 1`)."""
    span = obs_horizon + action_horizon
    return max(0, frames - span + 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="datasets/p33_pear")
    parser.add_argument("--shards", nargs="*", default=None)
    args = parser.parse_args()

    index_path = os.path.join(args.root, "index.json")
    rows = json.load(open(index_path, encoding="utf-8"))
    frames = sum(int(r["frames"]) for r in rows)
    print(f"store: {args.root}")
    print(f"episodes: {len(rows)}  frames: {frames}  windows: {sum(windows(int(r['frames'])) for r in rows)}")
    print(f"index_md5: {md5(index_path)}")
    print("arms:", dict(collections.Counter(r["arm"] for r in rows)))
    print("grades:", dict(collections.Counter(r["grade"] for r in rows)))
    print("stations:", dict(collections.Counter(r.get("station_y") for r in rows)))
    print("classes:", dict(collections.Counter(r["category"] for r in rows)))
    diam = sorted(float(r["diameter"]) for r in rows)
    if diam:
        import statistics as st

        print(
            f"diameter: min {diam[0]:.3f} median {st.median(diam):.3f} max {diam[-1]:.3f} m"
        )
    print("shards:", dict(collections.Counter(r.get("shard", "?") for r in rows)))
    notes = sum(1 for r in rows if r.get("notes"))
    print(f"episodes with notes: {notes}")

    shards = args.shards
    if shards is None:
        manifest = os.path.join(args.root, "manifest.json")
        if os.path.exists(manifest):
            shards = json.load(open(manifest, encoding="utf-8")).get("inputs", [])
    for shard in shards or []:
        path = os.path.join(shard, "manifest.json")
        if not os.path.exists(path):
            continue
        m = json.load(open(path, encoding="utf-8"))
        print(
            f"shard {shard}: seed={m.get('seed')} target={m.get('episodes_target')} "
            f"patch={m.get('supply', {}).get('patch')} "
            f"park_early={m.get('collection', {}).get('park_early')} "
            f"tasks={m.get('md5', {}).get('src/fruit_sorting/tasks.py')} "
            f"meshes={m.get('md5', {}).get('src/fruit_sorting/meshes.py')} "
            f"bed={m.get('md5', {}).get('src/fruit_sorting/bed.py')} "
            f"manifest_md5={md5(path)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
