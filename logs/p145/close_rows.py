#!/usr/bin/env python3
"""P145d.6: the close latch's 3-D certificate, from one or more cell logs.

    python3 logs/p145/close_rows.py logs/p145_e_77.log logs/p145_e_101.log

Reads the `[close]` rows (`FRUIT_POLICY_TRACE=1`) and the episode outcome rows,
joins them in order (one `[close]` row per attempt that latched), and prints the
dz distribution that the xy gap cannot see: a hand 12 cm above the fruit closes
on air and still reports a 1-2 cm xy gap.
"""
from __future__ import annotations

import re
import sys

CLOSE = re.compile(
    r"\[close\] t=(?P<t>\d+) trigger=(?P<trigger>\w+) xy=(?P<xy>[+-]?\d+)mm "
    r"dz=(?P<dz>[+-]?\d+)mm dx=(?P<dx>[+-]?\d+)mm jaw_z=(?P<jz>[+-]?\d+\.\d+) "
    r"fruit_z=(?P<fz>[+-]?\d+\.\d+) grip=(?P<grip>[\d.]+)"
)
EP = re.compile(r"episode (\d+): (\w+) d=([\d.]+)cm.*success=(\w+) grasped=(\w+) placed=(\w+)")


def main(paths: list[str]) -> int:
    rows = []
    for path in paths:
        closes = []
        eps = []
        with open(path, "r", errors="replace") as handle:
            for line in handle:
                if "[close]" in line:
                    m = CLOSE.search(line)
                    if m:
                        closes.append(m.groupdict())
                elif "episode " in line and "success=" in line:
                    m = EP.search(line)
                    if m:
                        eps.append(m.group(0))
        for i, row in enumerate(closes):
            row["cell"] = path.rsplit("/", 1)[-1].replace(".log", "")
            row["ep"] = eps[i] if i < len(eps) else "(no outcome row)"
            rows.append(row)
    if not rows:
        print("[close] no rows")
        return 1
    print(f"[close] latches={len(rows)}")
    for row in rows:
        print(
            f"  {row['cell']:>14} t={row['t']:>4} {row['trigger']:<6} "
            f"xy={row['xy']:>4} dz={row['dz']:>5} dx={row['dx']:>5} "
            f"jz={row['jz']} fz={row['fz']} grip={row['grip']}  | {row['ep']}"
        )
    dz = [int(r["dz"]) for r in rows]
    xy = [int(r["xy"]) for r in rows]
    ok = [r for r in rows if abs(int(r["dz"])) <= 25]
    print(
        f"[close] dz: |dz|<=25mm {len(ok)}/{len(rows)}  "
        f"median {sorted(dz)[len(dz)//2]:+d}mm  range [{min(dz):+d},{max(dz):+d}]"
    )
    print(f"[close] xy: median {sorted(xy)[len(xy)//2]}mm  max {max(xy)}mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["logs/p145_e_77.log"]))
