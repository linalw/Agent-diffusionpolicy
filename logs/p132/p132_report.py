#!/usr/bin/env python3
"""P132 report - re-derive the serrated-pad table from `fixture.log`.

    python3 logs/p132/p132_report.py            # the table + ratios to flat
    python3 logs/p132/p132_report.py --check    # exit 1 if a support proof failed

Every number in `RESULTS.md` comes from here; none is hand-copied.
"""

from __future__ import annotations

import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "fixture.log")

SEAT = re.compile(
    r"\[p132\]\s+seat\s+(\S+)\s+(\S+)\s+rep\d\s+padN=\[([^\]]*)\]\s+loaded=(\d+)\s+"
    r"seat=([\d.]+)mm creep_g=\s*([\d.]+)mm creep_op=\s*([\d.]+)mm load=\s*([\d.]+)mm "
    r"dz=\s*([+-][\d.]+)mm settle_dz=\s*([+-][\d.]+)mm walk=\s*([+-][\d.]+)mm "
    r"crush=\s*([+-][\d.]+)mm"
)
RAMP = re.compile(
    r"\[p132\] ramp\s+(\S+)\s+(\S+)\s+rep\d\s+F2mm=\s*([\d.]+)N Fexit=\s*([\d.]+)N "
    r"max=\s*([\d.]+)mm fmax=\s*([\d.]+)N"
)
SUPPORT = re.compile(r"\[p132\] support (\S+)\s+\S+\s+ticks=\s*(\d+) drift=\s*([\d.]+)mm dz=\s*([+-][\d.]+)mm verdict=(\S+)")
FRUITS = ("pear", "orange", "strawberry", "lychee")
PROFILES = ("flat", "serr", "serr45", "lip20")


def main() -> int:
    cells: dict[tuple[str, str], list[dict]] = {}
    support = []
    cur = None
    with open(LOG) as fh:
        for line in fh:
            m = SUPPORT.search(line)
            if m:
                support.append(
                    {"cell": m.group(1), "ticks": int(m.group(2)),
                     "drift": float(m.group(3)), "dz": float(m.group(4)), "ok": m.group(5) == "PASS"}
                )
                continue
            m = SEAT.search(line)
            if m:
                cur = {
                    "padN": m.group(3), "loaded": int(m.group(4)), "seat": float(m.group(5)),
                    "creep_g": float(m.group(6)), "creep_op": float(m.group(7)),
                    "load": float(m.group(8)), "dz_total": float(m.group(9)),
                    "settle_dz": float(m.group(10)), "walk": float(m.group(11)),
                    "crush": float(m.group(12)),
                }
                continue
            m = RAMP.search(line)
            if m and cur is not None:
                cur.update(f2=float(m.group(3)), fexit=float(m.group(4)),
                           max_disp=float(m.group(5)), fmax=float(m.group(6)))
                cells.setdefault((m.group(1), m.group(2)), []).append(cur)
                cur = None

    if not cells:
        print("no fixture rows")
        return 1

    print("== support proof (A1) ==")
    for r in support:
        print(f"  {r['cell']:14s} ticks={r['ticks']:3d} drift={r['drift']:8.3f}mm "
              f"dz={r['dz']:+9.3f}mm {'PASS' if r['ok'] else 'FAIL'}")
    comp = next((r for r in support if r["cell"] == "support_comp"), None)
    grav = next((r for r in support if r["cell"] == "support_grav"), None)
    proof = bool(comp and grav and comp["ok"] and grav["ok"])

    med = lambda v, k: st.median([r[k] for r in v])

    print()
    print("== fixture table (medians of 3) ==")
    print(f"{'profile':8s} {'fruit':10s} {'n':>2s} {'F2mm':>6s} {'Fexit':>6s} "
          f"{'settle_dz':>10s} {'walk':>7s} {'creep_g':>8s} {'creep_op':>9s} {'crush':>7s} {'pads':>4s}")
    for (prof, fruit), v in cells.items():
        if prof not in PROFILES or fruit not in FRUITS:
            continue
        print(
            f"{prof:8s} {fruit:10s} {len(v):2d} {med(v,'f2'):6.2f} {med(v,'fexit'):6.2f} "
            f"{med(v,'settle_dz'):+10.2f} {med(v,'walk'):+7.2f} {med(v,'creep_g'):8.2f} "
            f"{med(v,'creep_op'):9.2f} {med(v,'crush'):+7.2f} {int(med(v,'loaded')):4d}"
        )

    print()
    print("== ratios to flat: walk / F2mm / Fexit (the promotion rule is the first column) ==")
    for prof in ("serr", "serr45", "lip20"):
        for fruit in FRUITS:
            a = cells.get(("flat", fruit))
            b = cells.get((prof, fruit))
            if not a or not b:
                continue
            flat_w = abs(med(a, "walk"))
            w = med(b, "walk")
            # a floor: |walk| <= 0.05 mm is the rig's own resolution (P117's
            # support read is 0.000 mm; the 0.05 mm bar is that leg's tolerance)
            if flat_w <= 0.05 and abs(w) <= 0.05:
                wtext = f"floor (flat {flat_w:.2f} / {w:+.2f} mm)"
            else:
                wtext = f"{abs(w) / max(flat_w, 1e-9):5.2f}x ({w:+.2f} vs {med(a,'walk'):+.2f} mm)"
            print(
                f"{prof:8s} {fruit:10s} walk {wtext:34s} "
                f"F2mm {med(b,'f2') / max(med(a,'f2'), 1e-9):5.2f}x  "
                f"Fexit {med(b,'fexit') / max(med(a,'fexit'), 1e-9):5.2f}x"
            )

    print()
    print("== the promotion test (the brief's rule) ==")
    promoted = []
    for prof in ("serr", "serr45", "lip20"):
        rows = []
        for fruit in FRUITS:
            a = cells.get(("flat", fruit))
            b = cells.get((prof, fruit))
            if not a or not b:
                continue
            flat_w = abs(med(a, "walk"))
            w = abs(med(b, "walk"))
            walk_ok = flat_w > 0.05 and w <= 0.6 * flat_w
            break_ok = med(b, "fexit") >= med(a, "fexit") and med(b, "f2") >= med(a, "f2")
            crush_ok = med(b, "crush") >= -15.0
            rows.append((fruit, walk_ok, break_ok, crush_ok))
        walk_all = all(r[1] for r in rows) if rows else False
        break_all = all(r[2] for r in rows) if rows else False
        crush_all = all(r[3] for r in rows) if rows else False
        verdict = walk_all and break_all and crush_all
        if verdict:
            promoted.append(prof)
        print(
            f"  {prof:8s} walk={walk_all} break={break_all} crush={crush_all} -> "
            f"{'PROMOTE' if verdict else 'no'}"
        )
        for fruit, wk, bk, ck in rows:
            print(f"      {fruit:10s} walk={'ok' if wk else 'no':2s} "
                  f"break={'ok' if bk else 'no':2s} crush={'ok' if ck else 'no'}")
    print()
    print(f"support={'PASS' if proof else 'FAIL'} promoted={promoted or 'none'}")
    if "--check" in sys.argv:
        if not proof:
            print("FAIL: the fixture's support is not proven")
            return 1
        if promoted:
            print(f"NOTE: {promoted} promoted - the phase owes the build and the cell")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
