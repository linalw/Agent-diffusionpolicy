#!/usr/bin/env python3
"""P30-A: the release/clearance population over every log in the repo (offline).

    python3 logs/p30a/population.py            # the two tables RAILS_DESIGN.md quotes

Two questions, answered from the logs alone (no simulator):

1. **Where does the release put the fruit?** Every `[fruit] [task] released at [x, y, z],
   placed=...` row, binned by |y| against the output belts' inner rail (footprint
   |y| = 0.400-0.425, top 1.385 = belt top + 35 mm). This is the *catch-ledge* reading:
   a release over the rail's 25 mm top face, a release inboard of it (over the gap), and a
   release on the slab.
2. **How close does a carried payload get to the rail?** Every
   `[motion] carry placeN clearance: lowest payload point ... to the output rail` row.
   The small-negative band (-50..0 mm) is the genuine skim class; anything below ~-200 mm is a
   payload that had already escaped and was lying on the *main* belt (its |y| lands inside the
   0.40-0.46 window the metric uses, so the row is not a rail contact).

Caveat printed in the report: `_payload_clearance` labels every tick with 0.40 < |y| <= 0.46
against the rail's *nominal* top, so a negative value alone is not a contact - the A4/A5 pair
in `RESULTS.md` is what separates the two.
"""

from __future__ import annotations

import collections
import glob
import re
import statistics

RELEASE = re.compile(r"\[task\] released at \[[-\d.e]+, ([-0-9.e]+), [-\d.e]+\], placed=(\w+)")
CLEAR = re.compile(
    r"\[motion\] carry place[01] clearance: lowest payload point ([+-]?\d+) mm to the ([\w ]+)"
)
#: The inner rail's footprint and the slab edge, from `rails_geometry.py`.
RAIL_Y = (0.400, 0.425)


def main() -> int:
    rel = []
    clear = []
    files = 0
    for path in glob.glob("logs/**/*.log", recursive=True):
        try:
            text = open(path, errors="replace").read()
        except OSError:
            continue
        files += 1
        for m in RELEASE.finditer(text):
            rel.append((abs(float(m.group(1))), m.group(2) == "True"))
        for m in CLEAR.finditer(text):
            clear.append((int(m.group(1)), m.group(2).strip()))
    print(f"scanned {files} logs under logs/")
    print()
    print("1. releases, by |y| against the output belts' inner rail")
    bins = collections.OrderedDict(
        (
            (f"< {RAIL_Y[0]:.3f}  (inboard: over the gap)", lambda y: y < RAIL_Y[0]),
            (f"{RAIL_Y[0]:.3f}-{RAIL_Y[1]:.3f}  (on the rail's top face)", lambda y: RAIL_Y[0] <= y <= RAIL_Y[1]),
            (f"> {RAIL_Y[1]:.3f}  (on the slab)", lambda y: y > RAIL_Y[1]),
        )
    )
    n = len(rel)
    for name, pred in bins.items():
        sel = [ok for y, ok in rel if pred(y)]
        print(f"   {name:<44} n={len(sel):6d} ({100 * len(sel) / max(n, 1):5.1f} %) "
              f"placed={100 * sum(sel) / max(len(sel), 1):5.1f} %")
    print(f"   total {n} releases")
    print()
    print("2. place-leg clearance to the output rail")
    rail = [v for v, w in clear if w == "output rail"]
    pos = sorted(v for v in rail if v >= 0)
    small = sorted(v for v in rail if -50 < v < 0)
    esc = [v for v in rail if v <= -50]
    print(f"   {len(clear)} place-clearance rows ({len(rail)} to the output rail)")
    if pos:
        print(f"   positive: n={len(pos)} min={pos[0]} p1={pos[len(pos) // 100]} "
              f"p10={pos[len(pos) // 10]} median={statistics.median(pos):.0f} max={pos[-1]} mm")
    print(f"   small negatives (-50..0 mm, a genuine skim class): n={len(small)} "
          f"{small[:8]}{' ...' if len(small) > 8 else ''}")
    print(f"   escaped payload (<= -50 mm, a fruit on the main belt): n={len(esc)}")
    print()
    print("note: a negative row alone is not a rail contact (`_payload_clearance` uses the rail's")
    print("      nominal top for any 0.40 < |y| <= 0.46); see RESULTS.md section 5.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
