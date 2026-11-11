#!/usr/bin/env python3
"""P142: the grade ledger of both arms, from the logs alone.

The direct env sets `bin_index = 0 if grade == "A" else 1`, so the *commanded*
destination is a pure function of the fruit's grade; the station reselect can then
move a lane-1 fruit onto the left arm (`cross-lane station fruit`), which is a
**sort error** whether or not the attempt placed. This reads the two facts apart:

* `bin` in the episode's start row is what the attempt was commanded to serve;
* the `cross-lane station fruit` note is the event where the arm served the wrong
  lane anyway.

A **mis-sort** is either (a) a commanded bin that disagrees with the grade, or
(b) a cross-lane note on an attempt that placed. Both are reported per arm.
"""
from __future__ import annotations

import argparse
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

START = re.compile(
    r"\[rl\] episode (\d+): (\S+) grade=(\w+) d=([\d.]+)cm bin=(\d+) arm=(\w+)"
)
OUTCOME = re.compile(
    r"\[rl\] episode (\d+): (\S+) d=([\d.]+)cm bin=(\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+)"
)


def parse(path: str) -> list[dict]:
    rows: dict[int, dict] = {}
    with open(path, errors="ignore") as fh:
        for line in fh:
            start = START.search(line)
            if start is not None:
                rows[int(start.group(1))] = {
                    "episode": int(start.group(1)),
                    "category": start.group(2),
                    "grade": start.group(3),
                    "bin": int(start.group(5)),
                    "arm": start.group(6),
                    "placed": None,
                    "cross_lane": False,
                }
                continue
            outcome = OUTCOME.search(line)
            if outcome is not None:
                row = rows.get(int(outcome.group(1)))
                if row is not None:
                    row["placed"] = outcome.group(8) == "True"
                    # The note lives in the outcome row's `notes=[...]`, not on a
                    # line of its own - read it here.
                    if "cross-lane station fruit" in line:
                        row["cross_lane"] = True
                        _m = re.search(r"cross-lane station fruit[^'\"]*", line)
                        row["cross_lane_note"] = _m.group(0) if _m else "cross-lane"
                continue
            if "cross-lane station fruit" in line and "[fruit]" in line:
                match = re.search(r"\(index (\d+)\)", line)
                if match is not None:
                    # The note names the fruit's index, not the episode; count it
                    # against the most recent episode that has not placed yet.
                    for row in reversed(list(rows.values())):
                        if row["placed"] is None:
                            row["cross_lane"] = True
                            row["cross_lane_note"] = line.strip()[:120]
                            break
    return [row for row in rows.values() if row["placed"] is not None]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="logs/p142/ab")
    parser.add_argument("--arms", default="dynamic,indexed",
                        help="comma-separated log prefixes in --dir")
    args = parser.parse_args()

    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        rows = []
        for path in sorted(glob.glob(os.path.join(ROOT, args.dir, f"{arm}_s*.log"))):
            rows.extend(parse(path))
        if not rows:
            print(f"[ledger] {arm}: no cells")
            continue
        expected_bad = [r for r in rows if (0 if r["grade"] == "A" else 1) != r["bin"]]
        cross = [r for r in rows if r["cross_lane"]]
        cross_placed = [r for r in cross if r["placed"]]
        graded = {}
        for row in rows:
            key = row["grade"]
            block = graded.setdefault(key, {"n": 0, "placed": 0, "bins": set()})
            block["n"] += 1
            block["placed"] += 1 if row["placed"] else 0
            block["bins"].add(row["bin"])
        print(f"\n[ledger] {arm}: {len(rows)} episodes")
        for grade in sorted(graded):
            block = graded[grade]
            print(
                f"        grade {grade}: {block['placed']}/{block['n']} placed, "
                f"bins={sorted(block['bins'])}"
            )
        print(
            f"        commanded-bin disagreements with the grade: {len(expected_bad)}"
        )
        print(
            f"        cross-lane events: {len(cross)} "
            f"({len(cross_placed)} on an attempt that placed)"
        )
        for row in cross[:3]:
            print(
                f"          ep{row['episode']} ({row['category']} {row['grade']}, "
                f"bin={row['bin']}, placed={row['placed']}) - "
                f"{row.get('cross_lane_note', 'cross-lane')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
