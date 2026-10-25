#!/usr/bin/env python3
"""P40 phase 3 - the two-line `[cycle] grip` -> probe-count map (k = failures).

`REGRASP_YIELD.md` section 2 established that the two-line re-seat rows cannot be
attributed positionally (the arms' grip phases interleave and the row carries
neither arm nor tick), so the per-attempt probe count `k` is read from that
attempt's own `[cycle] grip` segment, whose value is a deterministic function of
`k`. This prints the pairing check and the class table for two logs:

  * the `[cycle]` row -> slot pairing is `total` == the slot's printed span
    (`[biarm] result ... sim=Ds` / `[run] attempt N: ... sim=a-b`), the same
    key `logs/p40/arrival_split.py` uses (the rows print in completion order);
  * `k` bands from the measured classes: `grip < 2.5` -> 0, `2.5-3.6` -> 1,
    `3.6-4.6` -> 2, `> 4.6` -> 3. The bands are wide because the classes are
    (k=0 1.67-1.95, k=1 3.08-3.28, k=3 5.38-5.45 over the P40 corpus).

    python3 logs/p40/p3/k_map.py LOG [LOG...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CYCLE = re.compile(r"\[cycle\] attempt (\d+): .*grip=([0-9.]+)s.*total=([0-9.]+)s")
BIARM = re.compile(r"\[biarm\] result (\w+) index=(\d+) (\w+) .* sim=([0-9.]+)s")
RUNSPAN = re.compile(r"\[run\] attempt (\d+): picking .* sim=([0-9.]+)-([0-9.]+)s")
RUNOUT = re.compile(r"\[run\] attempt (\d+): grasped=.* sim=([0-9.]+)-([0-9.]+)s")
ROWS = re.compile(r"dynamic regrasp: re-seated")


def band(grip: float) -> int:
    if grip < 2.5:
        return 0
    if grip < 3.6:
        return 1
    if grip < 4.6:
        return 2
    return 3


def main(argv: list[str]) -> int:
    for path in argv[1:]:
        text = Path(path).read_text(errors="replace").splitlines()
        cycles = []
        slots = []
        for line in text:
            if m := CYCLE.search(line):
                cycles.append((float(m.group(3)), float(m.group(2))))
            if m := BIARM.search(line):
                slots.append((m.group(1), float(m.group(4)), m.group(2), m.group(3)))
            elif m := RUNSPAN.search(line):
                slots.append(("", float(m.group(3)) - float(m.group(2)), m.group(1), ""))
            elif m := RUNOUT.search(line):
                slots.append(("", float(m.group(3)) - float(m.group(2)), m.group(1), ""))
        rows = sum(1 for ln in text if ROWS.search(ln))
        print(f"== {path}")
        print(f"   re-seat rows printed: {rows}; [cycle] rows: {len(cycles)}; slots: {len(slots)}")
        used: set[int] = set()
        total = 0
        for slot_i, (arm, span, idx, fruit) in enumerate(slots):
            best, best_d = None, 1e9
            for ci, (ctot, cgrip) in enumerate(cycles):
                if ci in used:
                    continue
                d = abs(ctot - span)
                if d < best_d:
                    best, best_d = ci, d
            if best is None:
                continue
            used.add(best)
            ctot, cgrip = cycles[best]
            k = band(cgrip)
            total += k
            print(
                f"   slot {slot_i:2d} {arm:6s} {fruit:10s} idx={idx:>3s} span={span:6.2f}"
                f" cycle_total={ctot:6.2f} (d={best_d:.2f}) grip={cgrip:5.2f} -> k={k}"
            )
        print(f"   sum of k = {total} (must equal the re-seat rows on a cap-off log)")
        unmatched = [c for i, c in enumerate(cycles) if i not in used]
        if unmatched:
            print(f"   unmatched [cycle] rows: {unmatched}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
