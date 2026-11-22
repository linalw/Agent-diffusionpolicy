"""Merge several demonstration shards into one dataset.

Parallel collection workers each write their own directory; this concatenates
them, renumbering episodes and files so the result looks like a single run.

    python scripts/41_merge_demos.py --inputs datasets/shard0 datasets/shard1 --out datasets/demos_v5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    merged: list[dict] = []
    index = 0
    seen_content: dict[str, tuple[str, str]] = {}
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
            source = os.path.join(src, entry["file"])
            if not os.path.exists(source):
                # A shard that was restarted keeps the older index.json, so it can
                # list episodes whose files have been overwritten by the new run.
                print(f"skip {src}:{entry['file']} (file missing)")
                continue
            # Read the frame count from the file, not from the shard's index: a
            # restarted shard leaves a stale `frames` value behind, and trusting it
            # is how the merged dataset ended up claiming 26,838 frames for 26,955
            # (WORKLOG "the dataset index did not match the dataset").
            import hashlib

            import numpy as np

            digest = hashlib.md5(open(source, "rb").read()).hexdigest()
            if digest in seen_content:
                print(
                    f"skip {src}:{entry['file']} (byte-identical to "
                    f"{seen_content[digest][1]} from {seen_content[digest][0]})"
                )
                continue
            seen_content[digest] = (src, entry["file"])
            frames = int(np.load(source)["action"].shape[0])
            dst_name = f"episode_{index:05d}.npz"
            shutil.copyfile(source, os.path.join(args.out, dst_name))
            record = dict(entry)
            record["file"] = dst_name
            record["index"] = index
            record["shard"] = src
            record["frames"] = frames
            merged.append(record)
            index += 1

    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)

    # A merged dataset needs its own provenance: which shards went in, and the
    # hash of the index a checkpoint would pin. The shard manifests (written by
    # `40_collect_demos.py`) carry the source md5s.
    shard_manifests = {}
    for src in args.inputs:
        path = os.path.join(src, "manifest.json")
        if os.path.exists(path):
            with open(path, "rb") as fh:
                shard_manifests[os.path.basename(os.path.normpath(src))] = hashlib.md5(
                    fh.read()
                ).hexdigest()
    #: P227x: carry the shards' **descriptive** blocks over when every shard that
    #: has them agrees. A merged store otherwise loses what a shard names - the
    #: arm asset (`scene.arm`), the drive (`physics.*`), the supply band - and the
    #: first merge of this arm's shards read `scene.arm: null` even though every
    #: input carried `kind: franka`. A disagreement is **reported and dropped**
    #: (the merge already records each shard's manifest md5), never silently
    #: picked from the first input.
    carried: dict[str, object] = {}
    disagreed: dict[str, list[str]] = {}
    _CARRIED = (
        "scene", "physics", "supply", "camera_res", "fixed_stepping",
        "episodes_target", "seed",
    )
    shard_blocks: list[dict] = []
    for src in args.inputs:
        path = os.path.join(src, "manifest.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            body = json.load(fh)
        shard_blocks.append({k: body[k] for k in _CARRIED if k in body})
    for key in _CARRIED:
        values = [b[key] for b in shard_blocks if key in b]
        if not values:
            continue
        if all(json.dumps(v, sort_keys=True) == json.dumps(values[0], sort_keys=True)
               for v in values):
            carried[key] = values[0]
        else:
            disagreed[key] = sorted({
                json.dumps(v, sort_keys=True) for v in values
            })
    manifest = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "inputs": [os.path.normpath(p) for p in args.inputs],
        "episodes": len(merged),
        "index_md5": hashlib.md5(
            json.dumps(merged, indent=2).encode("utf-8")
        ).hexdigest(),
        "shard_manifests": shard_manifests,
        **carried,
    }
    if disagreed:
        manifest["shards_disagree"] = disagreed
        print(
            "[merge] the shards disagree on "
            + ", ".join(sorted(disagreed))
            + " - dropped from the merged manifest (each shard's own md5 is in "
            "shard_manifests)"
        )
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    print(f"merged {len(merged)} successful episodes into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
