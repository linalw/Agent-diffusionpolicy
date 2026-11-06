#!/usr/bin/env python3
"""P117 report - re-derive both fixtures' tables from their logs.

    python3 logs/p117/p117_report.py            # fixture 1 + fixture 2
    python3 logs/p117/p117_report.py --pad      # fixture 1 only
    python3 logs/p117/p117_report.py --station  # fixture 2 only

Reads `logs/p117/fixture1.log` and `logs/p117/st_*.log`; prints the per-cell
medians (3 repeats), the ratio-to-flat table, and the station table.  No numbers
in `RESULTS.md` are hand-copied: every one comes from here.
"""

from __future__ import annotations

import glob
import os
import re
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
PAD = os.path.join(HERE, "fixture1.log")
#: The station cells, pinned by name so a re-run cannot double-count a cell.
ST_FILES = (
    "st_support2.log",   # B1: the pocket floor, 1200-tick drift trace
    "st_closed4.log",    # B4: the closed shutter, shipped cadence
    "st_closed_fast.log",# B4: the closed shutter, 0.833 s cadence
    "st_drop2.log",      # B2/B3/B6/B7: 16 drops
    "st_stream.log",     # B5: one drop + 3 followers, both cadences
)

SEAT = re.compile(
    r"\[p117\]\s+seat\s+(\S+)\s+(\S+)\s+rep\d\s+padN=\[([^\]]*)\]\s+loaded=(\d+)\s+"
    r"seat=([\d.]+)mm creep_g=\s*([\d.]+)mm creep_op=\s*([\d.]+)mm load=\s*([\d.]+)mm "
    r"dz=\s*([+-][\d.]+)mm"
)
RAMP = re.compile(
    r"\[p117\] ramp\s+(\S+)\s+(\S+)\s+rep\d\s+F2mm=\s*([\d.]+)N Fexit=\s*([\d.]+)N "
    r"max=\s*([\d.]+)mm fmax=\s*([\d.]+)N"
)
FRUITS = ("pear", "orange", "strawberry", "lychee")


def pad() -> int:
    cells: dict[tuple[str, str], list[dict]] = {}
    cur = None
    with open(PAD) as fh:
        for line in fh:
            m = SEAT.search(line)
            if m:
                cur = {
                    "padN": m.group(3), "loaded": int(m.group(4)),
                    "seat": float(m.group(5)), "creep_g": float(m.group(6)),
                    "creep_op": float(m.group(7)), "load": float(m.group(8)),
                    "dz": float(m.group(9)),
                }
                continue
            m = RAMP.search(line)
            if m and cur is not None:
                cur.update(f2=float(m.group(3)), fexit=float(m.group(4)), fmax=float(m.group(6)))
                cells.setdefault((m.group(1), m.group(2)), []).append(cur)
                cur = None
    if not cells:
        print("no fixture-1 rows")
        return 1
    print("== fixture 1: the pad face (medians of 3; creep in mm, forces in N) ==")
    print(
        f"{'profile':10s} {'fruit':10s} {'n':>2s} {'creep_g':>8s} {'creep_op':>9s} "
        f"{'load':>7s} {'dz':>7s} {'F2mm':>7s} {'Fexit':>7s} {'fmax':>6s} {'pads':>4s}"
    )
    med = lambda v, k: st.median([r[k] for r in v])
    for (prof, fruit), v in cells.items():
        print(
            f"{prof:10s} {fruit:10s} {len(v):2d} {med(v,'creep_g'):8.2f} {med(v,'creep_op'):9.2f} "
            f"{med(v,'load'):7.2f} {med(v,'dz'):+7.2f} {med(v,'f2'):7.2f} {med(v,'fexit'):7.2f} "
            f"{med(v,'fmax'):6.2f} {int(med(v,'loaded')):4d}"
        )
    flat = {f: med(cells[("flat", f)], "creep_op") for f in FRUITS if ("flat", f) in cells}
    flatf = {f: med(cells[("flat", f)], "fexit") for f in FRUITS if ("flat", f) in cells}
    print()
    print("== ratios to flat: creep_op / Fexit (a groove promotes only if < 1.0 on both) ==")
    for prof in ("arc06", "arc09", "v90", "cradle90", "flat_mu3", "flat_mu4"):
        out = []
        for f in FRUITS:
            key = (prof, f)
            if key not in cells or f not in flat:
                continue
            c = med(cells[key], "creep_op")
            fe = med(cells[key], "fexit")
            out.append(f"{f[:4]}:{c / flat[f]:5.2f}x/{fe / flatf[f]:5.2f}x")
        if out:
            print(f"{prof:10s} " + "  ".join(out))
    print()
    print("== the load-direction split: dz is the load axis, the rest is lateral ==")
    print(f"{'profile':10s} {'fruit':10s} {'creep_op':>9s} {'dz':>7s} {'lateral':>8s}")
    for (prof, fruit), v in cells.items():
        c = med(v, "creep_op")
        z = med(v, "dz")
        print(f"{prof:10s} {fruit:10s} {c:9.2f} {z:+7.2f} {max(0.0, (c * c - z * z)) ** 0.5:8.2f}")
    return 0


def station() -> int:
    print()
    print("== fixture 2: the station pocket ==")
    support, closed, drop, stream = [], [], [], []
    for path in (os.path.join(HERE, name) for name in ST_FILES if os.path.exists(os.path.join(HERE, name))):
        with open(path) as fh:
            for line in fh:
                if "[p117s] support " in line and "verdict" in line:
                    m = re.search(r"support (\S+)\s+d=\s*([\d.]+)mm settle=\s*([\d.]+)mm drift=\s*([\d.]+)mm", line)
                    if m:
                        support.append((m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))))
                elif "[p117s] support drift-vs-tick" in line:
                    support.append(("marks", line.split("drift-vs-tick")[1].strip()))
                elif "[p117s] closed " in line:
                    m = re.search(
                        r"closed (\S+)\s+n=(\d+) cadence=([\d.]+)s passed=(\d+)/(\d+) stalls=(\d+) "
                        r"door_F=\s*([\d.]+)N belt_jitter=\s*([\d.]+)mm v=([\d.]+)", line
                    )
                    if m:
                        closed.append((m.group(1), int(m.group(2)), float(m.group(3)), int(m.group(4)),
                                       int(m.group(5)), float(m.group(8)), float(m.group(9))))
                elif "[p117s] drop " in line and "st_stream" not in path:
                    m = re.search(
                        r"drop (\S+)\s+d=\s*([\d.]+)mm hold=\s*([\d.]+)mm x=\s*([+-][\d.]+) "
                        r"y=\s*([+-][\d.]+) z=\s*([+-][\d.]+) door_F=\s*([\d.]+)N "
                        r"open=([\d.]+)s in_pocket=(\d)", line
                    )
                    if m:
                        drop.append(dict(fruit=m.group(1), d=float(m.group(2)), hold=float(m.group(3)),
                                         x=float(m.group(4)), y=float(m.group(5)), z=float(m.group(6)),
                                         doorF=float(m.group(7)), open_s=float(m.group(8)),
                                         inside=int(m.group(9))))
                elif "[p117s] stream cadence" in line:
                    m = re.search(
                        r"cadence=([\d.]+)s subject=(\S+)\s+hold=\s*([\d.]+)mm followers_passed=(\d+)/(\d+) "
                        r"stalls=(\d+) door_F=\s*([\d.]+)N", line
                    )
                    if m:
                        stream.append((float(m.group(1)), float(m.group(3)), int(m.group(4)), int(m.group(5)),
                                       float(m.group(7))))
    for row in support:
        print("  support", *row)
    if drop:
        holds = [r["hold"] for r in drop]
        xs = [r["x"] for r in drop]
        ys = [r["y"] for r in drop]
        zs = [r["z"] for r in drop]
        print(
            f"  drop cells={len(drop)} in_pocket={sum(r['inside'] for r in drop)}/{len(drop)} "
            f"hold p50={st.median(holds):.3f} max={max(holds):.3f} mm | "
            f"x {min(xs):+.1f}..{max(xs):+.1f} (span {max(xs) - min(xs):.1f}) "
            f"y {min(ys):+.1f}..{max(ys):+.1f} z {min(zs):+.1f}..{max(zs):+.1f} mm | "
            f"open {min(r['open_s'] for r in drop):.2f}-{max(r['open_s'] for r in drop):.2f} s "
            f"door_F max={max(r['doorF'] for r in drop):.2f} N"
        )
    for row in closed:
        print(f"  closed  {row}")
    for row in stream:
        print(f"  stream  cadence={row[0]:.3f}s hold={row[1]:.3f}mm passed={row[2]}/{row[3]} door_F={row[4]:.2f}N")
    return 0


def main() -> int:
    import sys

    args = set(sys.argv[1:])
    if "--station" not in args:
        pad()
    if "--pad" not in args:
        station()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
