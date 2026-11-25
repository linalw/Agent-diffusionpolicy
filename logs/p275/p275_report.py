#!/usr/bin/env python3
"""P275 report: the truth-read census and the grasp judge's own fidelity.

Reads the cells' logs (never re-simulates) and prints three tables:

1. **Placed** per cell, with the two denominators the record asks for (placed per
   attempt and the per-pick wall clock the runner prints).
2. **Grasp judge** - the sensor decision against the truth label, attempt by
   attempt, so the judge is scored on its own fidelity rather than on the count
   (the count moves with the settle, P262).
3. **Truth census** - every remaining `spawner.position/velocity` read by call
   site, taken from the last (cumulative) block of each cell. `MISSING` is not
   zero: a cell with no census rows measured nothing.
"""
from __future__ import annotations

import glob
import os
import re
import sys

PLACED = re.compile(r"picks placed (\d+)/(\d+)")
JUDGE = re.compile(
    r"\[task\] grasp judge idx=(\d+) arm=(\w+) sensors=(\w+) truth=(\w+) "
    r"\(lift=([-+0-9.]+)m force=([0-9.]+)N span=([0-9.]+)mm ok=(\d+)/(\d+)\)"
)
CENSUS = re.compile(r"^\[truth\] ep=\d+\s+(\d+)\s+(\S+)$", re.M)
SELECT = re.compile(
    r"\[select\] percept: (\d+) detection\(s\), (\d+) on a live fruit, "
    r"(\d+) unmatched"
)
SELECT_FB = re.compile(r"\[select\] ep=\d+ source=percept truth_fallbacks=(\d+)")
FIRE_SRC = re.compile(r"\[fire\] source=(percept|truth)")


def read(path: str) -> str:
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def cells(paths: list[str]) -> dict[str, str]:
    """Group `TAG_sNNN.log` by tag (the arm)."""
    out: dict[str, list[str]] = {}
    for p in paths:
        tag = os.path.basename(p).split("_s")[0]
        out.setdefault(tag, []).append(p)
    return {k: "\n".join(read(p) for p in sorted(v)) for k, v in sorted(out.items())}


def main(argv: list[str]) -> int:
    paths = argv[1:] or sorted(glob.glob("logs/p275*/*.log"))
    if not paths:
        print("no logs", file=sys.stderr)
        return 2
    data = cells(paths)

    print("=" * 78)
    print("1. PLACED (each cell is one branch draw; P93)")
    print("=" * 78)
    print(f"{'arm':6s} {'placed':>10s} {'fraction':>9s}  cells")
    for tag, txt in data.items():
        p = sum(int(a) for a, _ in PLACED.findall(txt))
        n = sum(int(b) for _, b in PLACED.findall(txt))
        got = len(PLACED.findall(txt))
        frac = f"{100.0 * p / n:.1f}%" if n else "MISSING"
        print(f"{tag:6s} {p:>4d}/{n:<5d} {frac:>9s}  {got}")

    print()
    print("=" * 78)
    print("2. GRASP JUDGE - the sensor decision against the truth label")
    print("=" * 78)
    print(f"{'arm':6s} {'rows':>5s} {'agree':>6s} {'FP':>3s} {'FN':>3s}  disagreements")
    for tag, txt in data.items():
        rows = JUDGE.findall(txt)
        if not rows:
            print(f"{tag:6s} {'0':>5s} {'MISSING':>6s} {'-':>3s} {'-':>3s}  (no judge rows)")
            continue
        agree = sum(1 for r in rows if r[2] == r[3])
        fp = sum(1 for r in rows if r[2] == "held" and r[3] == "lost")
        fn = sum(1 for r in rows if r[2] == "lost" and r[3] == "held")
        bad = [
            f"idx{r[0]}:{r[2]}/{r[3]}(lift {r[4]}, {r[5]}N, {r[6]}mm)"
            for r in rows
            if r[2] != r[3]
        ]
        print(
            f"{tag:6s} {len(rows):>5d} {agree:>6d} {fp:>3d} {fn:>3d}  "
            f"{bad if bad else 'none'}"
        )

    print()
    print("=" * 78)
    print("2b. SELECTOR - what the perception candidate list actually saw")
    print("=" * 78)
    print(f"{'arm':6s} {'frames':>7s} {'det':>5s} {'live':>5s} {'unmatched':>10s} "
          f"{'fallbacks':>10s}")
    for tag, txt in data.items():
        rows = SELECT.findall(txt)
        fbs = [int(x) for x in SELECT_FB.findall(txt)]
        if not rows and not fbs:
            print(f"{tag:6s} {'-':>7s} {'-':>5s} {'-':>5s} {'-':>10s} {'-':>10s}"
                  "  (truth selector)")
            continue
        det = sum(int(r[0]) for r in rows)
        live = sum(int(r[1]) for r in rows)
        unm = sum(int(r[2]) for r in rows)
        print(f"{tag:6s} {len(rows):>7d} {det:>5d} {live:>5d} {unm:>10d} "
              f"{sum(fbs):>10d}")
    print("  `fallbacks` > 0 means that episode's selection went back to the")
    print("  simulator - a truth-free claim must quote it.")

    print()
    print("=" * 78)
    print("2c. TRIGGER SOURCE - did the fire decision read the tracker or the simulator?")
    print("=" * 78)
    print(f"{'arm':6s} {'percept':>8s} {'truth':>7s}   (one row per attempt)")
    for tag, txt in data.items():
        src = FIRE_SRC.findall(txt)
        if not src:
            print(f"{tag:6s} {'-':>8s} {'-':>7s}   (goal source is not perception)")
            continue
        pc = sum(1 for x in src if x == "percept")
        tr = len(src) - pc
        print(f"{tag:6s} {pc:>8d} {tr:>7d}"
              + ("   <- some fires fell back to truth" if tr else ""))

    print()
    print("=" * 78)
    print("3. TRUTH CENSUS - every remaining simulator fruit-state read")
    print("=" * 78)
    for tag, txt in data.items():
        blocks = CENSUS.findall(txt)
        if not blocks:
            print(f"\n{tag}: MISSING (no `[truth]` rows - FRUIT_TRUTH_AUDIT was not armed)")
            continue
        # cumulative per episode: the max per site is the total
        tot: dict[str, int] = {}
        for n, site in blocks:
            tot[site] = max(tot.get(site, 0), int(n))
        print(f"\n{tag}: {sum(tot.values())} reads over {len(blocks)} episode prints")
        for site, n in sorted(tot.items(), key=lambda kv: -kv[1]):
            print(f"    {n:7d}  {site}")

    print()
    print("Read: the judge is scored on table 2 (fidelity), never on table 1 - the")
    print("judge's own window is a settle, so a count delta is the settle's (P262).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
