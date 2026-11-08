#!/usr/bin/env python3
"""P130 report - the cage4 ring with the close freeze OFF (P129's named cell).

Reads the `[cage]` rows and the preceding `[motion] approach ... end=` of each
attempt, and applies P110's split: a row is **jam** when the descent ended more
than 15 mm short, **over-closure** when the aperture is below the fruit diameter
minus 4 mm or the force exceeds four times the cap's 1.5 (29.4 N), and **clean**
otherwise when at least three pads are loaded. The raw pad count is not the
endpoint (P110).

  python3 logs/p130/report.py logs/p130/F5.log logs/p130/F6.log \
      logs/p108/B_s5.log logs/p108/B_s6.log
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CAGE = re.compile(
    r"\[cage\] idx=(\d+) arm=(\w+) species=(\w+) dia=([\d.]+)mm .*?"
    r"clr=([+-][\d.]+)mm .*?pads=(\d+)/4 f=\(([^)]*)\) F=([\d.]+)N "
    r"aper=([\d.]+)mm no_contact=(\d)"
)
END = re.compile(r"\[motion\] approach\(cartesian\): [\d.]+ cm, \d+ samples: steps=\d+,.*?end=")
END2 = re.compile(r"end=([\d.]+)mm")


def read(path: Path):
    rows = []
    ends = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = CAGE.search(line)
        if m:
            rows.append(
                dict(idx=int(m.group(1)), dia=float(m.group(4)),
                     pads=int(m.group(6)), F=float(m.group(8)),
                     aper=float(m.group(9)), no_contact=int(m.group(10))))
        m = END2.search(line) if "approach(cartesian)" in line else None
        if m:
            ends.append(float(m.group(1)))
    return rows, ends


def main() -> int:
    for name in sys.argv[1:]:
        path = Path(name)
        if not path.exists():
            print(f"{name}: missing")
            continue
        rows, ends = read(path)
        clean = jam = over = noc = 0
        for i, r in enumerate(rows):
            end = ends[i] if i < len(ends) else 0.0
            if r["no_contact"] or r["pads"] == 0:
                noc += 1
            if end > 15.0:
                jam += 1
            elif r["aper"] < r["dia"] - 4.0 or r["F"] > 4 * 4.90 * 1.5:
                over += 1
            elif r["pads"] >= 3:
                clean += 1
        rates = re.search(r"attempts=(\d+) successes=(\d+)", path.read_text(errors="replace"))
        rate = (f"{rates.group(2)}/{rates.group(1)}" if rates else "?")
        print(f"{path.name:>12}: placed {rate:>7} | cage rows {len(rows):>3} "
              f"| clean {clean:>2} jam {jam:>2} over {over:>2} no-contact {noc:>2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
