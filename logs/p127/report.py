#!/usr/bin/env python3
"""P127 report - the shipped three-lane scene's baseline (4 seeds x 20 attempts)
and the three-destination cell's tray census.

  python3 logs/p127/report.py

The numbers are the new scene's **own** baseline: every pre-P126 rate/interval is
a two-lane number. A count is a branch (AGENTS section 2), so the report prints
the per-seed counts and the classes, and quotes the interval per seed.
"""

from __future__ import annotations

import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WIN = re.compile(r"\[run\] attempt (\d+) \((\w+)\): picking .*? sim=([\d.]+)-([\d.]+)s")
OUT = re.compile(r"\[run\] attempt (\d+) \((\w+)\): grasped=(\w+) placed=(\w+)")
CARRY = re.compile(r"\[carry\] (\w+) (\w+): ticks=(\d+)/(\d+) clean_slip_max=([\d.]+)mm")
CLR = re.compile(r"clr=([+-][\d.]+)mm")
SORT = re.compile(r"\[sort\] attempt \d+ idx=(\d+).*?dest=(\d+).*?in_dest=(\d+)")
TRAY = re.compile(r"\[belt\].*?\[tray (\d)\].*?discharged", re.S)


def read(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    windows, outcomes = {}, {}
    for line in text.splitlines():
        m = WIN.search(line)
        if m:
            windows[(int(m.group(1)), m.group(2))] = (float(m.group(3)), float(m.group(4)))
        m = OUT.search(line)
        if m:
            outcomes[(int(m.group(1)), m.group(2))] = (m.group(3) == "True", m.group(4) == "True")
    placed = sorted(windows[k][1] for k in windows if outcomes.get(k, (False, False))[1])
    per_arm = {}
    for k, t in [(k, windows[k][1]) for k in windows if outcomes.get(k, (False, False))[1]]:
        per_arm.setdefault(k[1], []).append(t)
    intervals = {arm: [b - a for a, b in zip(sorted(v), sorted(v)[1:])]
                 for arm, v in per_arm.items()}
    pooled = [b - a for a, b in zip(placed, placed[1:])]
    clr = [float(x) for x in CLR.findall(text)]
    carries = [tuple(m.groups()) for m in CARRY.finditer(text)]
    ledger = [tuple(int(x) for x in m.groups()) for m in SORT.finditer(text)]
    return dict(text=text, windows=windows, outcomes=outcomes, placed=placed,
                pooled=pooled, intervals=intervals, clr=clr, carries=carries,
                ledger=ledger)


def stats(v):
    if not v:
        return "n=0"
    return (f"n={len(v)} mean={st.mean(v):.2f} p50={st.median(v):.2f} "
            f"p90={sorted(v)[int(0.9 * (len(v) - 1))]:.2f}")


def main() -> int:
    print("P127 - the shipped three-lane scene's baseline")
    print(f"{'cell':>4} {'placed':>7} {'dnf':>4} {'noElig':>6} {'land':>9} {'clr_min':>8} "
          f"{'interval (pooled)':>34}")
    total = attempts = 0
    for seed in (5, 6, 101, 202):
        path = ROOT / f"logs/p127/S{seed}.log"
        if not path.exists():
            continue
        r = read(path)
        n = len(r["outcomes"])
        total += len(r["placed"])
        attempts += n
        dnf = r["text"].count("did not follow")
        noe = r["text"].count("no eligible")
        land = (r["text"].count("on_belt=True"), r["text"].count("on_belt="))
        clr = min(r["clr"]) if r["clr"] else float("nan")
        print(f"{seed:>4} {len(r['placed']):>4}/{n:<2} {dnf:>4} {noe:>6} "
              f"{land[0]:>4}/{land[1]:<4} {clr:>+8.0f} {stats(r['pooled']):>34}")
    if attempts:
        print(f"{'all':>4} {total:>4}/{attempts:<2}  = {100.0 * total / attempts:.1f} %")
    path = ROOT / "logs/p127/T5.log"
    if path.exists():
        r = read(path)
        print()
        print("three-destination cell (seed 5):")
        if r["ledger"]:
            by = {}
            for idx, dest, ind in r["ledger"]:
                e = by.setdefault(dest, [0, 0])
                e[0] += 1
                e[1] += ind
            for dest in sorted(by):
                print(f"  dest {dest}: {by[dest][1]}/{by[dest][0]} in destination")
        trays = TRAY.findall(r["text"])
        print(f"  tray discharge rows: {len(trays)} (by tray: "
              f"{ {t: trays.count(t) for t in sorted(set(trays))} })")
        print(f"  placed {len(r['placed'])}/{len(r['outcomes'])}, interval {stats(r['pooled'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
