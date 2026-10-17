#!/usr/bin/env python3
"""P10-C.2 fire/cancel table: parses the P10-C.2 monitor diag rows directly.

The new fire row carries the operand inline:
  [monitor] fire <side> <leg>: tick=T/N z=... asym@fire=... hot=... blocked=... min_contacts=... clean_slip_max=X.Xmm
  [monitor] cancel <side> <leg>: tick=T/N clean_slip=X.Xmm < T.Tmm

Usage: python3 logs/p10c2/fire_table.py LOG [LOG...]
"""
import re
import sys


def table(path):
    fires, cancels = [], []
    for line in open(path, errors="ignore"):
        m = re.search(r"\[monitor\] fire (\w+) (\w+): tick=(\d+)/(\d+).*?clean_slip_max=([\d.]+)mm", line)
        if m:
            fires.append((m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), float(m.group(5))))
        m = re.search(r"\[monitor\] cancel (\w+) (\w+): tick=(\d+)/(\d+) clean_slip=([\d.]+)mm < ([\d.]+)mm", line)
        if m:
            cancels.append((m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), float(m.group(5))))
    print(f"== {path}")
    print(f"   fires={len(fires)}  cancels={len(cancels)}")
    for f in fires:
        print(f"   FIRE   {f[0]:5s} {f[1]:11s} tick={f[2]:3d}/{f[3]:3d} clean_slip={f[4]:9.1f}mm")
    for c in cancels:
        print(f"   CANCEL {c[0]:5s} {c[1]:11s} tick={c[2]:3d}/{c[3]:3d} clean_slip={c[4]:6.1f}mm (below the gate)")
    return len(fires), len(cancels)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        table(p)
