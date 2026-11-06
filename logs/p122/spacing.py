#!/usr/bin/env python3
"""P122 - the destination-separation spec, from the measured release scatter.

Reads every `[sort] attempt ... dest=<d> target=(x,y) placed=1 release=(x,y,z)`
row in the P114/P115/P116/P121 logs, and answers one question: **how far apart
must two destinations be for the payload's release to be attributable to the
one the instruction named?**

  python3 logs/p122/spacing.py

The measured offset `o = release - target` has a **systematic** part - the
payload hangs from the jaw along the tool axis, **+48 mm in x and +-35..37 mm in
y** - and a **random** part (sd 6-9 mm in x, 6-17 mm in y).  Two consequences:

* the systematic is the same for every zone served by the same leg, so it
  **cancels between neighbours** only if the classifier compares *calibrated*
  positions.  Compared raw (as the ledger does today), a zone's payload lands
  ~48 mm downstream, i.e. **on the next zone's target** when the zones are
  50 mm apart - so calibration is not optional for a multi-zone lane;
* the random part is what remains, and it sets the spacing: for a separation
  `s` along one axis, `P(mis-sort) = P(|residual| > s/2)`.

The tables are **bootstrap** (20 000 draws, offsets resampled from the measured
pool of the leg that serves the zone) rather than Gaussian, because the tails
are heavier than Gaussian at this n.  Zone 1 of a lane reuses the lane's own
pool: the leg is the same, only the target moves.
"""

from __future__ import annotations

import glob
import math
import random
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAT = re.compile(
    r"\[sort\] attempt \d+ idx=\d+ (\S+) d=([\d.]+)cm grade=(\S+) ripeness=[\d.]+ "
    r"arm=(\w+) (?:rule=(\S+))? ?dest=(\d+) target=\(([-\d.]+),([+-][\d.]+)\) "
    r"placed=1 release=\(([-\d.]+),([+-][\d.]+),([-\d.]+)\)"
)


def collect():
    rows = []
    for f in (
        glob.glob(str(ROOT / "logs/p11[456]/**/*.log"), recursive=True)
        + glob.glob(str(ROOT / "logs/p121/direct/*.log"))
    ):
        try:
            text = Path(f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in PAT.finditer(text):
            rows.append(
                {
                    "dest": int(m.group(6)),
                    "target": (float(m.group(7)), float(m.group(8))),
                    "release": (float(m.group(9)), float(m.group(10))),
                }
            )
    return rows


def offsets(rows):
    out: dict[int, list[tuple[float, float]]] = {}
    for r in rows:
        out.setdefault(r["dest"], []).append(
            (r["release"][0] - r["target"][0], r["release"][1] - r["target"][1])
        )
    return out


def classify(release, targets, calib):
    best, dist = None, float("inf")
    for d, (tx, ty) in targets.items():
        cx, cy = calib[d]
        dd = math.hypot(release[0] - (tx + cx), release[1] - (ty + cy))
        if dd < dist:
            best, dist = d, dd
    return best


def rate(pools, targets, calib, n=20000, seed=11):
    """Bootstrap the mis-attribution rate of one layout.

    `pools[d]` is the offset pool of the leg that serves zone `d`; `calib[d]` is
    the mean of that pool (the calibrated target is `target - mean`).
    """
    rng = random.Random(seed)
    err = 0
    for _ in range(n):
        d = rng.choice(sorted(pools))
        ox, oy = rng.choice(pools[d])
        tx, ty = targets[d]
        if classify((tx + ox, ty + oy), targets, calib) != d:
            err += 1
    return err / n


def means(pools):
    return {d: (st.mean([a for a, _ in v]), st.mean([b for _, b in v]))
            for d, v in pools.items()}


def main() -> int:
    rows = collect()
    pools = offsets(rows)
    print(f"P122 destination spacing - {len(rows)} measured releases "
          f"({', '.join(f'dest {d}: n={len(v)}' for d, v in sorted(pools.items()))})")
    print()
    print("1. THE OFFSET (release - commanded target), mm")
    print(f"{'dest':>5} {'n':>4} {'dx mean':>8} {'dx sd':>6} {'dy mean':>8} {'dy sd':>6}")
    for d, v in sorted(pools.items()):
        dx = [a for a, _ in v]
        dy = [b for _, b in v]
        print(f"{d:>5} {len(v):>4} {st.mean(dx)*1000:>+8.0f} {st.pstdev(dx)*1000:>6.0f} "
              f"{st.mean(dy)*1000:>+8.0f} {st.pstdev(dy)*1000:>6.0f}")

    # lane 0 zones reuse dest 0's pool; lane 1 zones reuse dest 1's.
    lane0, lane1 = pools[0], pools[1]
    cal = {0: means({0: lane0})[0], 1: means({0: lane0})[0],
           2: means({0: lane1})[0], 3: means({0: lane1})[0]}

    print()
    print("2. THE SEPARATION CURVE (bootstrap; zone 0 vs zone 1 in one lane)")
    print(f"{'separation':>11} {'axis':>5} {'calibrated':>11} {'raw':>9}")
    for s in (0.030, 0.040, 0.050, 0.060, 0.075, 0.100, 0.150):
        tg = {0: (0.43, +0.50), 1: (0.43 + s, +0.50), 2: (0.43, -0.50)}
        pools_t = {0: lane0, 1: lane0, 2: lane1}
        pc = rate(pools_t, tg, cal)
        pr = rate(pools_t, tg, {k: (0.0, 0.0) for k in tg})
        print(f"{s*1000:>9.0f}mm {'x':>5} {pc:>11.2%} {pr:>9.2%}")
    for s in (0.050, 0.075, 0.100, 0.150):
        tg = {0: (0.43, +0.50), 1: (0.43, +0.50 + s), 2: (0.43, -0.50)}
        pools_t = {0: lane0, 1: lane0, 2: lane1}
        pc = rate(pools_t, tg, cal)
        pr = rate(pools_t, tg, {k: (0.0, 0.0) for k in tg})
        print(f"{s*1000:>9.0f}mm {'y':>5} {pc:>11.2%} {pr:>9.2%}")

    print()
    print("3. THE LAYOUTS (measured, calibrated; the count is per release)")
    layouts = {
        "shipped: 2 lanes, 1.0 m apart in y": (
            {0: (0.43, +0.50), 1: (0.43, -0.50)},
            {0: lane0, 1: lane1}),
        "P114/P121 three_dest: (-50,+50) = 71 mm": (
            {0: (0.43, +0.50), 1: (0.43, -0.50), 2: (0.38, +0.55)},
            {0: lane0, 1: lane1, 2: pools[2]}),
        "three zones: x-only 50 mm, same lane": (
            {0: (0.38, +0.50), 1: (0.43, +0.50), 2: (0.43, -0.50)},
            {0: lane0, 1: lane0, 2: lane1}),
        "three zones: x-only 100 mm, same lane": (
            {0: (0.33, +0.50), 1: (0.43, +0.50), 2: (0.43, -0.50)},
            {0: lane0, 1: lane0, 2: lane1}),
        "four zones: x-only 50 mm x 2 lanes": (
            {0: (0.38, +0.50), 1: (0.43, +0.50), 2: (0.38, -0.50), 3: (0.43, -0.50)},
            {0: lane0, 1: lane0, 2: lane1, 3: lane1}),
    }
    for name, (tg, pools_t) in layouts.items():
        c = {d: (st.mean([a for a, _ in pools_t[d]]),
                   st.mean([b for _, b in pools_t[d]])) for d in tg}
        pc = rate(pools_t, tg, c)
        pr = rate(pools_t, tg, {k: (0.0, 0.0) for k in tg})
        print(f"  {name:<42} calibrated {pc:>7.2%}   raw {pr:>7.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
