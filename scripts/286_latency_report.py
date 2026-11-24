#!/usr/bin/env python3
"""P228 (Stage 0): read the latency sweep `scripts/285_latency_bench.sh` ran.

    python3 scripts/286_latency_report.py logs/p228/latency

Reports, per (d, seed) and pooled per d:

* **placed / total** from the `[rl] episode` rows;
* the `[lat]` accounting the injector printed (`d`, the measured inference wall,
  the simulated pause) - this is the manipulation check: if `d` is 0 the arm
  never paid anything, and a cell whose `[lat]` rows are missing is not a
  latency cell at all;
* the **mechanism** columns, which are branch-free: `t_arrive` at the fire, the
  number of `close: fruit drifted ... mm` rows (the catch-up lost the fruit),
  and the failure-reason keys.

Read it as a **direction with a mechanism, not a rate** (P93's rule): the direct
loop conditions on rendered frames, so a 6-episode cell is one draw. What is
comparable across `d` is the per-attempt mechanism (the fire's `t_arrive`, the
drift rows) - and, if the effect is real, a monotone placed count against `d`.

At the shipped 0.12 m/s **one control tick is 1.0 mm of belt**, so `d` is also
the displacement: 4 mm is inside the 6 mm catch tolerance, 16 mm is 2.7x it.
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

EP = re.compile(
    r"^\[fruit\] \[rl\] episode (\d+): (\w+) d=([\d.]+)cm .*?"
    r"success=(\w+) grasped=(\w+) placed=(\w+)"
)
LAT = re.compile(r"\[lat\] d=(\d+) mode=(\S+) infer_ms=([\d.]+) sim_ms=([\d.]+)")
TARRIVE = re.compile(r"t_arrive=([\d.]+)s")
DRIFT = re.compile(r"close: fruit drifted (\d+) mm")
NOTE_TEXT = re.compile(r"'([^']*)'")


def parse(path: Path) -> dict:
    placed = total = 0
    fires = 0
    lat: list[tuple[int, float, float]] = []
    tarrive: list[float] = []
    drift = 0
    notes: Counter[str] = Counter()
    for line in path.read_text(errors="replace").splitlines():
        if m := EP.search(line):
            total += 1
            placed += int(m.group(6) == "True")
            # The episode row **carries the notes**, so the trigger and the
            # failure keys have to be read off the same line (an `elif` chain
            # would stop at the episode match and report `t_arrive = nan` -
            # measured on the first pass).
            body = line.split("notes=", 1)[-1]
            for value in TARRIVE.findall(body):
                tarrive.append(float(value))
            for text in NOTE_TEXT.findall(body):
                if "intercept trigger" in text:
                    fires += 1
                # keep the class, drop the numbers so keys aggregate
                notes[re.sub(r"[\d.]+", "#", text)[:70]] += 1
        elif m := LAT.search(line):
            lat.append((int(m.group(1)), float(m.group(3)), float(m.group(4))))
        elif DRIFT.search(line):
            drift += 1
    return {
        "placed": placed,
        "total": total,
        "fires": fires,
        "lat": lat,
        "tarrive": tarrive,
        "drift": drift,
        "notes": notes,
    }


def med(xs: list[float]) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else "logs/p228/latency")
    cells = sorted(root.glob("D*_s*.log"))
    if not cells:
        print(f"no cells under {root} - run scripts/285_latency_bench.sh first")
        return 1

    by_d: dict[str, list[dict]] = defaultdict(list)
    rows = []
    for path in cells:
        m = re.match(r"D(.+)_s(\d+)\.log$", path.name)
        if not m:
            continue
        d, seed = m.group(1), m.group(2)
        r = parse(path)
        by_d[d].append(r)
        rows.append((d, seed, path, r))

    print(f"{'d':>5} {'seed':>5} {'placed':>7} {'lat':>4} {'fires':>5} "
          f"{'d_meas':>7} {'infer_ms':>9} {'t_arrive':>9} {'drift':>6}")
    print("-" * 70)
    for d, seed, _path, r in rows:
        d_meas = med([x[0] for x in r["lat"]])
        infer = med([x[1] for x in r["lat"]])
        ta = med(r["tarrive"])
        print(f"{d:>5} {seed:>5} {r['placed']:>3}/{r['total']:<3} "
              f"{len(r['lat']):>4} {r['fires']:>5} {d_meas:>7.1f} "
              f"{infer:>9.1f} {ta:>9.2f} {r['drift']:>6}")
    print("-" * 70)

    def dkey(x: str) -> tuple[int, float]:
        return (1, 0.0) if x == "auto" else (0, float(x))

    print(f"\n{'d':>5} {'placed':>9} {'pct':>6} {'cells':>6} "
          f"{'d_meas':>7} {'infer_ms':>9} {'t_arrive':>9} {'drift':>6}")
    for d in sorted(by_d, key=dkey):
        arms = by_d[d]
        p = sum(a["placed"] for a in arms)
        t = sum(a["total"] for a in arms)
        lat = [x for a in arms for x in a["lat"]]
        ta = [x for a in arms for x in a["tarrive"]]
        print(f"{d:>5} {p:>4}/{t:<4} {100.0 * p / max(t, 1):>5.1f}% "
              f"{len(arms):>6} {med([x[0] for x in lat]):>7.1f} "
              f"{med([x[1] for x in lat]):>9.1f} {med(ta):>9.2f} "
              f"{sum(a['drift'] for a in arms):>6}")

    print("\nfailure keys (digit-normalised; the counter is over every cell):")
    keys: Counter[str] = Counter()
    for _d, _s, _p, r in rows:
        keys.update(r["notes"])
    for k, n in keys.most_common(12):
        print(f"  {n:>3}  {k}")

    # The manipulation check: a latency cell with no `[lat]` rows measured nothing.
    silent = [d for d, arms in by_d.items() if d != "0" and all(not a["lat"] for a in arms)]
    if silent:
        print(f"\nWARNING: {', '.join(sorted(silent))} produced no [lat] rows - "
              "those cells are not latency cells (check FRUIT_EVAL_LATENCY)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
