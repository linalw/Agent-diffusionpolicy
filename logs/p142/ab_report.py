#!/usr/bin/env python3
"""P142's two-arm read: the moving catch against the shipped indexed primitive.

Both arms run the same seeds, the same checkpoint, the same wave and the same
declared endpoint (`FRUIT_SCORE_ENDPOINT=release`); only `FRUIT_DYNAMIC_PICK`
differs. The output is a paired table plus the failure-note classes, because a
count without its classes is a branch and not a result.
"""
from __future__ import annotations

import argparse
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EPISODE = re.compile(
    r"\[rl\] episode (\d+): (\S+) d=([\d.]+)cm bin=(\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+).*?notes=\[(.*?)\]"
)
ABORT = re.compile(r"abort: the sample handed to the close is not at the station")
RESELECT = re.compile(r"reselecting across lanes")


def parse(path: str) -> list[dict]:
    rows = []
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                if "[rl] episode " not in line:
                    continue
                match = EPISODE.search(line)
                if match is None:
                    continue
                notes = match.group(10)
                rows.append(
                    {
                        "seed": int(re.search(r"_s(\d+)\.log$", path).group(1)),
                        "episode": int(match.group(1)),
                        "category": match.group(2),
                        "arm": match.group(5),
                        "success": match.group(6) == "True",
                        "grasped": match.group(7) == "True",
                        "placed": match.group(8) == "True",
                        "ticks": int(match.group(9)),
                        "notes": notes,
                    }
                )
    except FileNotFoundError:
        pass
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="logs/p142/ab")
    args = parser.parse_args()

    arms = {}
    for arm in ("dynamic", "indexed"):
        rows = []
        for path in sorted(glob.glob(os.path.join(ROOT, args.dir, f"{arm}_s*.log"))):
            rows.extend(parse(path))
        arms[arm] = rows
        if not rows:
            print(f"[ab] {arm}: no cells yet")
            continue
        placed = sum(1 for row in rows if row["placed"])
        success = sum(1 for row in rows if row["success"])
        print(
            f"[ab] {arm:8s} n={len(rows):2d} placed={placed:2d} "
            f"({100 * placed / len(rows):5.1f} %) success={success:2d} "
            f"({100 * success / len(rows):5.1f} %)"
        )
        per_seed = {}
        for row in rows:
            per_seed.setdefault(row["seed"], []).append(row)
        for seed in sorted(per_seed):
            block = per_seed[seed]
            print(
                f"        seed {seed}: {sum(1 for r in block if r['placed'])}/"
                f"{len(block)} placed, {sum(1 for r in block if r['success'])}"
                f"/{len(block)} success"
            )
        classes = {}
        for row in rows:
            for note in row["notes"].split("', '"):
                note = note.strip("' ")
                if not note:
                    continue
                key = note.split(" (")[0]
                classes[key] = classes.get(key, 0) + 1
        for key, count in sorted(classes.items(), key=lambda kv: -kv[1]):
            print(f"        note {count:2d}x {key[:96]}")

    if arms.get("dynamic") and arms.get("indexed"):
        # Paired on (seed, episode): the same slot of the same seed.
        index = {(r["seed"], r["episode"]): r for r in arms["indexed"]}
        pairs = [
            (row, index[(row["seed"], row["episode"])])
            for row in arms["dynamic"]
            if (row["seed"], row["episode"]) in index
        ]
        dyn_only = sum(1 for a, b in pairs if a["placed"] and not b["placed"])
        idx_only = sum(1 for a, b in pairs if b["placed"] and not a["placed"])
        print(
            f"\n[ab] paired on (seed, episode): n={len(pairs)} "
            f"dynamic-only {dyn_only}, indexed-only {idx_only}"
        )
        if len(pairs) >= 10:
            # Exact two-sided sign test on the discordant pairs.
            from math import comb

            n = dyn_only + idx_only
            if n:
                k = min(dyn_only, idx_only)
                p = 2.0 * sum(comb(n, i) for i in range(k + 1)) / (2.0**n)
                p = min(1.0, p)
                print(f"[ab] sign test (two-sided): p = {p:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
