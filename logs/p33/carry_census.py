#!/usr/bin/env python3
"""P33 phase 2 - the carried-not-placed census (offline, read-only).

Re-derives, from the acceptance/battery logs on the P32/P33 tree, every
`grasped=True placed=False` episode and its leg context.  No simulator, no
state change.

Usage:
    python3 logs/p33/carry_census.py            # the census file
    python3 logs/p33/carry_census.py --all      # every episode (both classes)

The two-line logs carry `[biarm] result <arm> index=...`; the single-arm logs
carry `[run] attempt N: grasped=... placed=...`.  Both are parsed.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The current-tree population.  Grouped by scenario so the two-line and the
# acceptance never pool: different supply schedules are different scenarios.
FAMILIES = [
    ("acceptance (single-arm, shipped scatter, pear-on; 3 bit-identical runs)",
     ["logs/p32/80_accept_raw.log",
      "logs/p32/89_accept_r1r2.log",
      "logs/p32/93_accept_raw_pear_on.log",
      "logs/p32/D1_accept_pear.log",
      "logs/p33/00_accept_shipped.log",
      "logs/p33/40_accept_final.log"]),
    ("acceptance (single-arm, pear-off control)", [
        "logs/p32/92_accept_raw_pear_off_current.log",
        "logs/p32/81_accept_raw_pear_off.log",
    ]),
    ("pear battery (species-locked, single-arm)", [
        "logs/p32/90_pear_battery_new.log",
        "logs/p32/91_pear_battery_old.log",
    ]),
    ("bed battery (single-arm, bed supply)", [
        "logs/p32/72_bed_10_arm1.log",
        "logs/p32/77_bed_cadence1.log",
        "logs/p32/79_bed_20_settle.log",
        "logs/p32/87_bed_10_r1r2.log",
        "logs/p32/88_bed_20_settle_r1r2.log",
        "logs/p33/20_single_control.log",
    ]),
    ("bed battery (two-line)", [
        "logs/p32/A0_bed_twoline_1.log",
        "logs/p32/A1_bed_twoline_prepared.log",
        "logs/p32/A3_bed_twoline_trace.log",
        "logs/p33/10_twoline_control.log",
    ]),
    ("acceptance (shared-station bimanual, FRUIT_BIARM=1)", [
        "logs/p32/E1_accept_biarm.log",
    ]),
]

ATTEMPT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+-][\d.]+) m "
    r"force=([\d.]+) N notes=\[(.*?)\]"
)
TARGET = re.compile(r"\[task\] target (\w+) \(grade (\w), ([\d.]+) cm\) with (\w+) arm")
BIARM = re.compile(
    r"\[biarm\] result (\w+) index=(\d+) (\w+) grasped=(\w+) placed=(\w+) "
    r"lift=([+-][\d.]+) force=([\d.]+) sim=([\d.]+)s notes=\[(.*?)\]"
)
LIFT = re.compile(r"\[task\] lift ([+-][\d.]+) m, grasped=(\w+)")
CARRY = re.compile(
    r"\[motion\] carry (\w+): ([\d.]+) cm, (\d+) ticks.*?slip_max=([\d.]+) mm, "
    r"in-hand \|v\|max=([\d.]+) m/s, recoveries=(\d+)"
)
RELEASE = re.compile(r"\[task\] released at \[([^\]]+)\], placed=(\w+) \((.*?)\)")
SERVO = re.compile(
    r"\[task\] force servo: (\w+): ref=([\d.]+)N F\[([\d.]+),([\d.]+)\]N "
    r"gap=([\d.]+)mm sep=([\d.]+)mm closed=([\d.]+)mm opened=([\d.]+)mm trips=(\d+)"
)


def parse_single_arm(path: str):
    """Return the episode list of one single-arm log."""
    eps = []
    cur = None
    with open(path, errors="replace") as fh:
        for line in fh:
            m = TARGET.search(line)
            if m and cur is None:
                cur = {
                    "species": m.group(1), "grade": m.group(2),
                    "dia_cm": float(m.group(3)), "arm": m.group(4),
                    "carries": [], "release": None, "servo": None,
                }
                continue
            m = LIFT.search(line)
            if m and cur is not None:
                cur["lift_task"] = float(m.group(1))
                continue
            m = CARRY.search(line)
            if m and cur is not None:
                cur["carries"].append({
                    "leg": m.group(1), "dist_cm": float(m.group(2)),
                    "ticks": int(m.group(3)), "slip_max": float(m.group(4)),
                    "inhand_v": float(m.group(5)), "recoveries": int(m.group(6)),
                })
                continue
            m = RELEASE.search(line)
            if m and cur is not None:
                xyz = [float(v) for v in m.group(1).split(",")]
                cur["release"] = {"z": xyz[2], "y": xyz[1], "x": xyz[0],
                                  "placed": m.group(2), "note": m.group(3)}
                continue
            m = SERVO.search(line)
            if m and cur is not None:
                cur["servo"] = {
                    "arm": m.group(1), "fmin": float(m.group(3)),
                    "fmax": float(m.group(4)), "gap": float(m.group(5)),
                    "sep": float(m.group(6)), "closed": float(m.group(7)),
                    "opened": float(m.group(8)), "trips": int(m.group(9)),
                }
                continue
            m = ATTEMPT.search(line)
            if m and cur is not None:
                cur.update({
                    "ep": int(m.group(1)), "grasped": m.group(2) == "True",
                    "placed": m.group(3) == "True",
                    "lift": float(m.group(4)), "force": float(m.group(5)),
                    "notes": m.group(6),
                })
                eps.append(cur)
                cur = None
    return eps


def parse_two_line(path: str):
    eps = []
    with open(path, errors="replace") as fh:
        for line in fh:
            m = BIARM.search(line)
            if not m:
                continue
            eps.append({
                "ep": int(m.group(2)), "arm": m.group(1),
                "species": m.group(3), "grasped": m.group(4) == "True",
                "placed": m.group(5) == "True", "lift": float(m.group(6)),
                "force": float(m.group(7)), "notes": m.group(9),
                "carries": [], "release": None, "servo": None, "dia_cm": None,
            })
    return eps


def fmt_ep(e):
    parts = []
    parts.append(f"{e['species']:<10s}")
    if e.get("dia_cm"):
        parts.append(f"{e['dia_cm']:4.1f} cm")
    else:
        parts.append("  ?   ")
    parts.append(f"{e['arm']:<5s}")
    parts.append(f"ep{e['ep']:<2d}")
    parts.append(f"lift {e['lift']:+.3f} m")
    parts.append(f"force {e['force']:5.2f} N")
    if e.get("release"):
        r = e["release"]
        parts.append(f"release y={r['y']:+.3f} z={r['z']:.3f}")
    if e.get("servo"):
        s = e["servo"]
        parts.append(
            f"servo F[{s['fmin']:.2f},{s['fmax']:.2f}] gap/sep "
            f"{s['gap']:.1f}/{s['sep']:.1f} closed {s['closed']:.2f} trips {s['trips']}"
        )
    notes = [n.strip() for n in e.get("notes", "").split(",") if n.strip()]
    if notes:
        parts.append("notes=" + ",".join(notes))
    line = "  " + " | ".join(parts)
    for c in e.get("carries", []):
        line += (
            f"\n      {c['leg']:<12s} {c['dist_cm']:5.1f} cm {c['ticks']:4d} ticks"
            f"  slip_max {c['slip_max']:8.1f} mm  in-hand |v| {c['inhand_v']:.3f}"
            f"  recov {c['recoveries']}"
        )
    return line


def per_arm_and_legs():
    """Per-arm outcome totals and the per-leg in-hand speed by class."""
    out = ["", "== per-arm totals (the distinct logs only)"]
    for family, paths in FAMILIES:
        arm_stats = {}
        leg_rows = {"fail_lift": [], "fail_place": [], "ok_lift": [], "ok_place": []}
        seen = set()
        for rel in paths:
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                continue
            two_line = ("A0" in rel or "A1" in rel or "A3" in rel
                        or "twoline" in rel or "E1" in rel)
            eps = parse_two_line(path) if two_line else parse_single_arm(path)
            key = tuple(
                (e["ep"], e["species"], e["grasped"], e["placed"],
                 round(e["lift"], 3), round(e["force"], 2))
                for e in eps
            )
            if key in seen:
                continue
            seen.add(key)
            for e in eps:
                st = arm_stats.setdefault(e["arm"], [0, 0, 0, 0])
                st[0] += 1
                st[1] += 1 if e["placed"] else 0
                st[2] += 1 if (e["grasped"] and not e["placed"]) else 0
                st[3] += 1 if not e["grasped"] else 0
                for c in e.get("carries", []):
                    bucket = ("ok_" if e["placed"] else "fail_") + (
                        "lift" if c["leg"] == "grasp_lift" else "place")
                    leg_rows[bucket].append((c["inhand_v"], c["dist_cm"], c["ticks"]))
        out.append(f"  -- {family}")
        for arm, (a, ok, cnp, no) in sorted(arm_stats.items()):
            out.append(f"    {arm:<5s}: attempts={a:3d} placed={ok:3d} "
                       f"carried-not-placed={cnp:3d} no-grasp={no:3d}")
        for bucket in ("ok_lift", "ok_place", "fail_lift", "fail_place"):
            rows = leg_rows[bucket]
            if not rows:
                continue
            v = sorted(r[0] for r in rows)
            d = sorted(r[1] for r in rows)
            t = sorted(r[2] for r in rows)
            out.append(
                f"    {bucket:<10s} n={len(rows):3d}  in-hand |v|max "
                f"min/med/max {v[0]:.3f}/{v[len(v)//2]:.3f}/{v[-1]:.3f} m/s  "
                f"dist {d[0]:.1f}-{d[-1]:.1f} cm  ticks {t[0]}-{t[-1]} (med {t[len(t)//2]})"
            )
    out.extend(size_table())
    return out


def size_table():
    """Arm x diameter-band contingency (the census's secondary correlate)."""
    out = ["", "== arm x diameter contingency (the distinct logs; species is NOT controlled here)"]
    cells = {}
    for family, paths in FAMILIES:
        seen = set()
        for rel in paths:
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                continue
            two_line = ("A0" in rel or "A1" in rel or "A3" in rel
                        or "twoline" in rel or "E1" in rel)
            eps = parse_two_line(path) if two_line else parse_single_arm(path)
            key = tuple(
                (e["ep"], e["species"], e["grasped"], e["placed"],
                 round(e["lift"], 3), round(e["force"], 2))
                for e in eps
            )
            if key in seen:
                continue
            seen.add(key)
            for e in eps:
                dia = e.get("dia_cm")
                if not dia:
                    continue
                band = "<=4.0" if dia <= 4.0 else ("4.1-5.9" if dia < 5.9 else
                                                   ("5.9-6.4" if dia <= 6.45 else ">6.4"))
                cell = cells.setdefault((e["arm"], band), [0, 0, 0, 0])
                cell[0] += 1
                cell[1] += 1 if e["placed"] else 0
                cell[2] += 1 if (e["grasped"] and not e["placed"]) else 0
                cell[3] += 1 if not e["grasped"] else 0
    for arm in sorted({k[0] for k in cells}):
        for band in ("<=4.0", "4.1-5.9", "5.9-6.4", ">6.4"):
            cell = cells.get((arm, band))
            if not cell:
                continue
            a, ok, cnp, no = cell
            out.append(f"    {arm:<5s} {band:<6s} attempts={a:3d} placed={ok:3d} "
                       f"cnp={cnp:3d} no-grasp={no:3d}  placed {100.0 * ok / a:5.1f} %")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="list every episode")
    args = ap.parse_args()
    out = []
    total = {}
    for family, paths in FAMILIES:
        rows = []
        seen = {}
        for rel in paths:
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                out.append(f"MISSING {rel}")
                continue
            eps = (parse_two_line if "A0" in rel or "A1" in rel or "A3" in rel
                   or "twoline" in rel or "E1" in rel else parse_single_arm)(path)
            key = tuple(
                (e["ep"], e["species"], e["grasped"], e["placed"],
                 round(e["lift"], 3), round(e["force"], 2))
                for e in eps
            )
            ident = "new"
            for prev, prevrel in seen.items():
                if prev == key:
                    ident = f"identical to {prevrel}"
                    break
            if ident == "new":
                seen[key] = rel
            rows.append((rel, eps, ident))
        out.append(f"== {family}")
        for rel, eps, ident in rows:
            n_att = len(eps)
            n_ok = sum(1 for e in eps if e["placed"])
            n_cnp = sum(1 for e in eps if e["grasped"] and not e["placed"])
            n_no = sum(1 for e in eps if not e["grasped"])
            out.append(
                f"  {rel}: attempts={n_att} placed={n_ok} "
                f"carried-not-placed={n_cnp} no-grasp={n_no} [{ident}]"
            )
            total.setdefault(family, [0, 0, 0, 0])
            if ident == "new":
                total[family][0] += n_att
                total[family][1] += n_ok
                total[family][2] += n_cnp
                total[family][3] += n_no
            if args.all or ident == "new":
                for e in eps:
                    if args.all or (e["grasped"] and not e["placed"]):
                        out.append(fmt_ep(e))
        out.append("")
    out.append("== the distinct population (bit-identical replays counted once)")
    for family, (a, ok, cnp, no) in total.items():
        out.append(f"  {family}: {a} attempts, {ok} placed, {cnp} carried-not-placed, {no} no-grasp")
    out.extend(per_arm_and_legs())
    text = "\n".join(out)
    print(text)
    dest = os.path.join(ROOT, "logs/p33/50_carry_census.txt")
    with open(dest, "w") as fh:
        fh.write(text + "\n")
    print(f"\n[written] {dest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
