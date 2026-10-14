#!/usr/bin/env python3
"""Merge rollout shards (dirs written by `scripts/110_rl_rollout.py --record`) into one store.

    python3 scripts/197_r9_merge_rollouts.py --out datasets/rl_rollouts/r9_awr_merged \
        datasets/rl_rollouts/r9_parts/shard_a datasets/rl_rollouts/r9_parts/shard_b
    python3 scripts/197_r9_merge_rollouts.py --self-test

Why this exists (R9): a recorded direct-env run in this environment can hit the
RTX `multitick.render` stall (OPS.md (b)) after a few minutes - the non-recorded
runs do not - so the AWR rollouts are collected in *short shards* (a few
episodes per process) and merged here into the one store `scripts/111_rl_finetune.py`
consumes. The merge is a byte copy with renumbering: each input row's file is
copied to `rollout_%05d.npz` in the output store, rows are concatenated in the
given shard order, each row's `index` is renumbered and a `shard` field names
its source dir. Every other field (success / reward / notes / category / ...)
is preserved untouched, and a `merge_manifest.json` records the inputs and
their index md5s.

Report-only checks: refuses an existing output store, refuses a shard without a
readable `index.json`, and refuses an entry whose file is missing or empty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time


def _md5(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def merge(inputs: list[str], out: str) -> dict:
    index_path = os.path.join(out, "index.json")
    if os.path.exists(index_path):
        raise SystemExit(f"refusing to overwrite an existing store: {index_path}")
    os.makedirs(out, exist_ok=True)

    rows: list[dict] = []
    provenance: list[dict] = []
    counter = 0
    for src in inputs:
        src_index = os.path.join(src, "index.json")
        if not os.path.exists(src_index):
            raise SystemExit(f"shard {src} has no index.json")
        with open(src_index, encoding="utf-8") as fh:
            entries = json.load(fh)
        if not isinstance(entries, list):
            raise SystemExit(f"shard {src}: index.json is not a list")
        shard = os.path.basename(os.path.normpath(src))
        for entry in entries:
            name = entry.get("file")
            if not name:
                raise SystemExit(f"shard {src}: an index row has no file")
            source = os.path.join(src, name)
            if not os.path.exists(source) or os.path.getsize(source) == 0:
                raise SystemExit(f"shard {src}: missing/empty {name}")
            target = f"rollout_{counter:05d}.npz"
            shutil.copy2(source, os.path.join(out, target))
            row = dict(entry)
            row["file"] = target
            row["index"] = counter
            row["shard"] = shard
            rows.append(row)
            counter += 1
        provenance.append(
            {
                "dir": os.path.abspath(src),
                "index_md5": _md5(src_index),
                "episodes": len(entries),
            }
        )

    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    manifest = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "kind": "rollout_merge",
        "inputs": provenance,
        "episodes": len(rows),
        "successes": int(sum(1 for r in rows if r.get("success"))),
    }
    with open(os.path.join(out, "merge_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


def self_test() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for shard, rows in (
            ("a", [{"file": "rollout_00000.npz", "index": 0, "success": True},
                   {"file": "rollout_00001.npz", "index": 1, "success": False}]),
            ("b", [{"file": "rollout_00000.npz", "index": 0, "success": True}]),
        ):
            d = os.path.join(tmp, shard)
            os.makedirs(d)
            for row in rows:
                with open(os.path.join(d, row["file"]), "wb") as fh:
                    fh.write(b"npz" + shard.encode())
            with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as fh:
                json.dump(rows, fh)
        out = os.path.join(tmp, "merged")
        manifest = merge([os.path.join(tmp, "a"), os.path.join(tmp, "b")], out)
        with open(os.path.join(out, "index.json"), encoding="utf-8") as fh:
            merged = json.load(fh)
        if [r["file"] for r in merged] != [
            "rollout_00000.npz", "rollout_00001.npz", "rollout_00002.npz"
        ]:
            failures.append("renumbering wrong")
        if [r["index"] for r in merged] != [0, 1, 2]:
            failures.append("index field not renumbered")
        if [r["shard"] for r in merged] != ["a", "a", "b"]:
            failures.append("shard provenance wrong")
        if manifest["successes"] != 2 or manifest["episodes"] != 3:
            failures.append("manifest counts wrong")
        with open(os.path.join(out, "rollout_00002.npz"), "rb") as fh:
            if fh.read() != b"npzb":
                failures.append("file copy wrong")
        # Refuse-to-overwrite check.
        try:
            merge([os.path.join(tmp, "a")], out)
            failures.append("overwrite was not refused")
        except SystemExit:
            pass
    if failures:
        print("197 self-test FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("197 self-test PASS (merge, renumber, provenance, overwrite refusal)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="*", help="shard dirs with index.json + npz")
    ap.add_argument("--out", default="datasets/rl_rollouts/r9_awr_merged")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.inputs:
        ap.error("at least one shard dir is required")
    manifest = merge(args.inputs, args.out)
    print(
        f"[merge] {manifest['episodes']} episodes "
        f"({manifest['successes']} successful) -> {args.out}"
    )
    for item in manifest["inputs"]:
        print(f"[merge]   {item['dir']} ({item['episodes']}, index {item['index_md5'][:8]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
