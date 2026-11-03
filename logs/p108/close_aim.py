#!/usr/bin/env python3
"""P108 - the close-time aim, from the trace corpus that already exists.

`FRUIT_DYNAMIC_TRACE=1` writes one JSON per attempt with per-tick `close` rows
carrying the arm's jaw centre and the payload's position.  Every such file under
`logs/` is a *shipped-hand* attempt, and the close is the moment the pads are on
the payload - i.e. the number P107's "24 mm off the cage's axis" is *not*.

Prints one line per cell directory: |dx| (across the belt), |dy| (along it) and
the radial offset at the close's **first** row, plus the largest radial offset
over the whole close window.  Purpose: establish that the aim at the grasp is a
3-5 mm figure, so the aperture a radial cage needs is not a *capture* dimension
but an *arrival-path* one.
"""

from __future__ import annotations

import collections
import glob
import json
import math

import numpy as np

CELLS: dict[str, list] = collections.defaultdict(list)
for path in glob.glob("logs/**/trace_*.json", recursive=True):
    try:
        with open(path) as fh:
            d = json.load(fh)
    except Exception:  # noqa: BLE001 - a broken old trace is not a measurement
        continue
    if not isinstance(d, dict) or "rows" not in d:
        continue
    close = [r for r in d["rows"] if r.get("phase") == "close"]
    if not close:
        continue
    first = close[0]
    dx = first["fruit"][0] - first["jaw"][0]
    dy = first["fruit"][1] - first["jaw"][1]
    rad = max(
        math.hypot(r["fruit"][0] - r["jaw"][0], r["fruit"][1] - r["jaw"][1])
        for r in close
    )
    CELLS["/".join(path.split("/")[1:3])].append((abs(dx), abs(dy), rad))


def pct(v, q):
    return float(np.percentile(np.asarray(v, float), q)) * 1000.0


print("P108 close-time aim census (FRUIT_DYNAMIC_TRACE cells already on disk)")
print(f"{'cell':24s} {'n':>3} {'|dx| p50':>9} {'|dy| p50':>9} {'rad p50':>8} "
      f"{'|dx| p95':>9} {'|dy| p95':>9} {'rad max':>8}")
pool = []
for cell, rows in sorted(CELLS.items()):
    dx = [r[0] for r in rows]
    dy = [r[1] for r in rows]
    rad = [r[2] for r in rows]
    pool.extend(rows)
    print(f"{cell:24s} {len(rows):>3} {pct(dx, 50):9.1f} {pct(dy, 50):9.1f} "
          f"{pct(rad, 50):8.1f} {pct(dx, 95):9.1f} {pct(dy, 95):9.1f} "
          f"{max(rad) * 1000:8.1f}")
dx = [r[0] for r in pool]
dy = [r[1] for r in pool]
rad = [r[2] for r in pool]
print(f"{'POOLED':24s} {len(pool):>3} {pct(dx, 50):9.1f} {pct(dy, 50):9.1f} "
      f"{pct(rad, 50):8.1f} {pct(dx, 95):9.1f} {pct(dy, 95):9.1f} "
      f"{max(rad) * 1000:8.1f}")
print("\n(units: mm; the close's first row is the tick the pads start closing)")
