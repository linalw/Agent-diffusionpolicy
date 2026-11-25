#!/usr/bin/env python3
"""P269: the powered cell for the catch exit tolerance - the registered read.

    python3 logs/p269/p269_report.py

Reads the four cells (`C_s907`, `C_s908`, `T_s907`, `T_s908`) and prints the endpoints the
**pre-registration** fixed (`logs/p269/PREREG.md`):

  P1  the true-stall rate (`residual > 20 mm`, over catches) must be **<= 15 %**
  P2  `T placed >= C placed - 2` of 40, and no place-side loss in T
      (a `grasped=True placed=False` row means the 1 mm offset is costing landings)
  P3  the attempt cycle and the picked interval, per arm (a report)

A missing cell is reported as **MISSING**, never as zero: a hung cell leaves no result row
(`logs/p269/METHOD.md` section 1).
"""
from __future__ import annotations

import os
import re
import statistics as st
import sys

CELLS = {"C": ["C_s907", "C_s908"], "T": ["T_s907", "T_s908"]}
ROOT = os.path.dirname(os.path.abspath(__file__))


def read_cell(name: str) -> dict | None:
    path = os.path.join(ROOT, f"{name}.log")
    if not os.path.exists(path):
        return None
    txt = open(path, encoding="utf-8", errors="replace").read()
    placed = re.search(r"picks placed (\d+)/(\d+)", txt)
    if placed is None:
        return None                      # started and never finished: MISSING, not zero
    catches = [
        (int(a), float(b))
        for a, b in re.findall(r"\[catch\][^\n]*ticks=(\d+) residual=([\d.]+)mm", txt)
    ]
    losses = re.findall(
        r"\[rl\] episode \d+: \w+ d=[\d.]+cm bin=[-\d]+ arm=\w+ "
        r"success=(\w+) grasped=(\w+) placed=(\w+)",
        txt,
    )
    cycles = [float(x) for x in re.findall(r"\[cycle\] attempt \d+:.*?total=([\d.]+)s", txt)]
    gaps = [int(x) for x in re.findall(r"gap_ticks=(\d+)", txt)]
    return {
        "placed": int(placed.group(1)),
        "n": int(placed.group(2)),
        "catches": catches,
        "episodes": losses,
        "cycle": st.median(cycles) if cycles else float("nan"),
        "gap": st.median(gaps) if gaps else float("nan"),
    }


def main() -> int:
    missing = [c for arm in CELLS.values() for c in arm
               if read_cell(c) is None]
    cells = {c: read_cell(c) for arm in CELLS.values() for c in arm}
    print(f"{'cell':10s} {'placed':>8} {'catches':>8} {'true':>5} {'slow':>5} {'>=100':>6} {'cycle':>7}")
    for name, r in cells.items():
        if r is None:
            print(f"{name:10s} {'MISSING':>8}")
            continue
        true = [x for x in r["catches"] if x[1] > 20.0]
        slow = [x for x in r["catches"] if x[0] >= 100 and x[1] <= 12.0]
        print(f"{name:10s} {r['placed']:3d}/{r['n']:<4d} {len(r['catches']):8d} "
              f"{len(true):5d} {len(slow):5d} {sum(1 for x in r['catches'] if x[0] >= 100):6d} "
              f"{r['cycle']:6.2f}s")

    if missing:
        print(f"\nMISSING cells: {', '.join(missing)} - the registration cannot be read "
              f"until they are re-run (a hung cell leaves no result; see METHOD.md).")
        return 2

    agg = {}
    for arm, names in CELLS.items():
        rs = [cells[n] for n in names]
        catches = sum(len(r["catches"]) for r in rs)
        true = sum(1 for r in rs for x in r["catches"] if x[1] > 20.0)
        placed = sum(r["placed"] for r in rs)
        n = sum(r["n"] for r in rs)
        place_loss = sum(1 for r in rs for s, g, p in r["episodes"] if g == "True" and p == "False")
        agg[arm] = dict(catches=catches, true=true, placed=placed, n=n,
                        rate=(100.0 * true / catches) if catches else float("nan"),
                        place_loss=place_loss,
                        cycle=st.median([r["cycle"] for r in rs]),
                        s_per_pick=st.median([r["cycle"] + r["gap"] / 120.0 for r in rs]))
    c, t = agg["C"], agg["T"]
    print(f"\nC: {c['placed']}/{c['n']} placed, {c['true']}/{c['catches']} true stalls "
          f"({c['rate']:.0f}%), cycle {c['cycle']:.2f}s, s/pick {c['s_per_pick']:.2f}")
    print(f"T: {t['placed']}/{t['n']} placed, {t['true']}/{t['catches']} true stalls "
          f"({t['rate']:.0f}%), cycle {t['cycle']:.2f}s, s/pick {t['s_per_pick']:.2f}, "
          f"place-side losses {t['place_loss']}")

    p1 = t["rate"] <= 15.0
    p2 = t["placed"] >= c["placed"] - 2 and t["place_loss"] == 0
    print(f"\nP1 (true-stall rate <= 15%):        {'PASS' if p1 else 'FAIL'}  "
          f"({t['rate']:.0f}% vs C's {c['rate']:.0f}%)")
    print(f"P2 (count >= C-2 and no place loss): {'PASS' if p2 else 'FAIL'}  "
          f"({t['placed']} vs C {c['placed']}, place-side losses {t['place_loss']})")
    print(f"P3 (report):                         cycle {t['cycle']:.2f} vs {c['cycle']:.2f}s, "
          f"s/pick {t['s_per_pick']:.2f} vs {c['s_per_pick']:.2f}")
    if p1 and p2:
        print("\nThe registration passes - which licenses PROPOSING 7 mm, and owes the four "
              "items PREREG section 'What a pass licenses' lists (two more seeds, the "
              "two-line gate, both references, every store, the 0.08 re-check).")
    else:
        print("\nThe registration does not pass: the tolerance stays at 6 mm.")
    return 0 if (p1 and p2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
