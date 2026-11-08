#!/usr/bin/env python3
"""P131 report - the aperture-law cells, on the corrected enclosure split.

Reads the five P131 cells (`U5`,`U6` = the shipped law; `P5`,`P6` = `pad_axes`;
`M5` = the `max_extent` screen) and P130's two freeze-off controls (`F5`,`F6`),
and prints, per cell:

* the placed count (a branch, report only) and the diverted count,
* the **corrected enclosure split** (`census.classify`): jam / miss / over /
  crush / vblock / no-contact / clean, plus P110's literal `pads>=3` split,
* the over-closure rows by species and the `aper/ramp`, `aper/R`, `sep-aper`
  evidence (the law vs the drive),
* the V-block census (`off0` p50, the `pads` histogram),
* the guards: the crush proxy (`sep@loss - dia`), the landing (`on_belt` on
  payload-present releases) and the descent budgets (`105` is run separately).

  python3 logs/p131/p131_report.py
  python3 logs/p131/p131_report.py --cells logs/p131/P_s5.log ...
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

from census import CARRY, classify, parse, pct  # noqa: E402

#: The registered battery (P130's F cells are the pre-phase context).
CELLS = [
    "logs/p130/F5.log", "logs/p130/F6.log",
    "logs/p131/U_s5.log", "logs/p131/U_s6.log",
    "logs/p131/P_s5.log", "logs/p131/P_s6.log",
    "logs/p131/M_s5.log",
]
STATS = re.compile(r"\[stats\] attempts=(\d+) successes=(\d+) diverted=(\d+)")
PLACE = re.compile(
    r"\[task\]\s+place trace \w+: release_bottom=([-+0-9.]+)mm .*?on_belt=(\w+)"
)
CARRY_ROW = re.compile(
    r"\[carry\] \w+ (\w+):.*?clean_slip_max=([0-9.]+)mm .*?"
    r"sep@loss=([0-9.]+)mm|sep@loss=n/amm"
)
CAP = 4.90


def cell_stats(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = STATS.search(text)
    attempts = int(m.group(1)) if m else 0
    placed = int(m.group(2)) if m else 0
    diverted = int(m.group(3)) if m else 0
    rows = parse(path)
    classes = {}
    per_class_placed = {}
    for r in rows:
        p110, p131 = classify(r)
        classes[p131] = classes.get(p131, 0) + 1
        placed_here = bool(r["outcome"][1]) if r["outcome"] else False
        per_class_placed.setdefault(p131, [0, 0])
        per_class_placed[p131][1] += 1
        per_class_placed[p131][0] += int(placed_here)
    # The crush proxy: a loss tick when the measured span is below dia - 15 mm.
    crush = 0
    crush_legs = 0
    for line in text.splitlines():
        m = re.search(r"\[carry\] \w+ (\w+):.*?sep@loss=([0-9.]+)mm .*?dia=([0-9.]+) ", line)
        if m:
            crush_legs += 1
            if float(m.group(2)) - float(m.group(3)) < -15.0:
                crush += 1
    # Landing: only payload-present releases (the -184 mm rows are upstream-lost).
    land = land_present = 0
    for line in text.splitlines():
        m = PLACE.search(line)
        if m and float(m.group(1)) >= 0.0:
            land_present += 1
            land += int(m.group(2) == "True")
    return dict(path=path, attempts=attempts, placed=placed, diverted=diverted,
                rows=rows, classes=classes, per_class=per_class_placed,
                crush=crush, crush_legs=crush_legs,
                land=land, land_present=land_present)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", nargs="*", default=CELLS)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    data = {}
    for name in args.cells:
        p = Path(name)
        if not p.exists():
            print(f"{name}: missing")
            continue
        data[p.name] = cell_stats(p)

    print("P131 - the aperture-law cells")
    print("=" * 118)
    print("the corrected split: jam = end>15; miss = off>15; over = seated and "
          "(aper<R-4 or F>29.4);")
    print("clean = pads>=3 and none of those; vblock = pads 1-2 and none of those.")
    print(f"{'cell':>10} {'law':>10} {'placed':>7} {'div':>4} {'clean':>5} {'over':>4} "
          f"{'vblk':>4} {'miss':>4} {'jam':>3} {'n/c':>3} | {'P110 c/j/cr':>11} | "
          f"{'crush':>5} {'land':>5}")
    for name, d in data.items():
        c = d["classes"]
        law = "shipped" if name.startswith(("F", "U")) else ("pad_axes" if name.startswith("P") else "max_ext")
        p110 = [classify(r)[0] for r in d["rows"]]
        print(f"{name:>10} {law:>10} {d['placed']:>3}/{d['attempts']:<3} {d['diverted']:>4} "
              f"{c.get('clean', 0):>5} {c.get('over', 0):>4} {c.get('vblock', 0):>4} "
              f"{c.get('miss', 0):>4} {c.get('jam', 0):>3} {c.get('no-contact', 0):>3} | "
              f"{p110.count('clean'):>3}/{p110.count('jam'):>2}/{p110.count('crush'):<3} | "
              f"{d['crush']:>2}/{d['crush_legs']:<2} {d['land']:>2}/{d['land_present']:<2}")

    print("\nper-class placed (the count is a branch, reported not gated):")
    print(f"{'cell':>10} " + " ".join(f"{k:>10}" for k in
                                     ("clean", "over", "vblock", "miss", "jam", "no-contact")))
    for name, d in data.items():
        parts = []
        for k in ("clean", "over", "vblock", "miss", "jam", "no-contact"):
            got = d["per_class"].get(k, [0, 0])
            parts.append(f"{got[0]}/{got[1]:<9}")
        print(f"{name:>10} " + " ".join(parts))

    print("\nthe shrink of the over-closure (the law the census measures):")
    for name, d in data.items():
        over = [r for r in d["rows"] if classify(r)[1] == "over"]
        if not over:
            print(f"  {name:>10}: over-closure 0/{d['attempts']}")
            continue
        spec = {}
        for r in over:
            spec[r["species"]] = spec.get(r["species"], 0) + 1
        print(f"  {name:>10}: over-closure {len(over)}/{d['attempts']} {spec}  "
              f"aper/R p50 {pct([r['aper'] / r['radial'] for r in over], 50):.3f}  "
              f"aper/ramp p50 {pct([r['aper'] / r['ramp'] for r in over], 50):.3f}")

    print("\nthe drive test (`sep` = the measured pad span at the close's flush):")
    for name, d in data.items():
        sep = [r for r in d["rows"] if r["sep"] is not None]
        if not sep:
            continue
        delta = [r["sep"] - r["aper"] for r in sep]
        print(f"  {name:>10}: sep-aper p10 {pct(delta, 10):+6.2f} "
              f"p50 {pct(delta, 50):+6.2f} p90 {pct(delta, 90):+6.2f} mm  "
              f"(negative = the pads reached inside the command)")

    print("\nthe V-block: the pads over the 0.5 N threshold, and the close-time offset")
    for name, d in data.items():
        hist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        for r in d["rows"]:
            hist[r["pads"]] += 1
        offs = [r["off0"] for r in d["rows"] if r["off0"] is not None
                and r["off0"] == r["off0"] and r["off0"] < 50.0]
        print(f"  {name:>10}: pads 0:1:2:3:4 = {hist[0]}:{hist[1]}:{hist[2]}:{hist[3]}:{hist[4]}  "
              f"off0 p50 {pct(offs, 50):5.1f} mm (seated rows only)")

    print("\nthe `max_extent` screen: rows whose stated extent is the fruit's height")
    for name in ("M_s5.log",):
        d = data.get(name)
        if not d:
            continue
        tall = [r for r in d["rows"] if r["ext"] is not None and r["ext"] > r["radial"] + 2.0]
        print(f"  {name}: {len(tall)} rows with ext > R + 2 mm "
              f"(pear/kiwi: the ring closes on air)")
        for r in tall:
            out = r["outcome"]
            print(f"    att {r['attempt']:>2} {r['species']:11s} d={r['dia']:4.0f} "
                  f"R={r['radial']:5.1f} ext={r['ext']:5.1f} aper={r['aper']:5.1f} "
                  f"pads={r['pads']} placed={out[1] if out else '?'}")

    print("\nthe shipped acceptance (the no-harm; run separately by accept.sh)")
    if not args.check:
        return 0

    print("\nthe registered gates")
    rc = 0
    p_cells = [d for n, d in data.items() if n.startswith("P")]
    u_cells = [d for n, d in data.items() if n.startswith("U")]
    over = {n: sum(1 for r in d["rows"] if classify(r)[1] == "over")
            for n, d in data.items() if n.startswith(("U", "P"))}
    d1 = (all(over.get(n, 0) == 0 for n in data if n.startswith("P"))
          and any(over.get(n, 0) > 0 for n in data if n.startswith("U")))
    seps = [r["sep"] - r["aper"] for d in p_cells for r in d["rows"]
            if r["sep"] is not None]
    d1_sep = pct(seps, 10) >= -1.0
    print(f"  G1/D1 the over-closure is the law: P cells over 0, U cells "
          f"{ {n: v for n, v in over.items() if n.startswith('U')} }; "
          f"sep-aper p10 {pct(seps, 10):+.2f} mm  "
          f"[{'PASS' if d1 and d1_sep else 'FAIL'}]")
    rc |= 0 if (d1 and d1_sep) else 1
    clean_p = sum(d["classes"].get("clean", 0) for d in p_cells)
    clean_u = sum(d["classes"].get("clean", 0) for d in u_cells)
    d2 = clean_p >= 11
    print(f"  G2/D2 the enclosure: pad_axes clean {clean_p}/40 vs the fresh same-tree "
          f"control {clean_u}/40 (the PREREG's pinned bar is >= 11)  "
          f"[{'PASS' if d2 else 'FAIL'}]")
    rc |= 0 if d2 else 1
    landing_bad = {n: d["land_present"] - d["land"] for n, d in data.items()
                   if d["land_present"] and d["land"] < d["land_present"]}
    g3 = not landing_bad
    print(f"  G3 landing (payload-present releases off the belt): "
          f"{landing_bad or 'none'}  [{'PASS' if g3 else 'FAIL'}]")
    rc |= 0 if g3 else 1
    g4 = sum(d["crush"] for d in data.values()) == 0
    print(f"  G4 crush proxy (`sep@loss - dia < -15 mm`): "
          f"{sum(d['crush'] for d in data.values())} leg(s)  "
          f"[{'PASS' if g4 else 'FAIL'}]")
    rc |= 0 if g4 else 1
    notes = set()
    for d in data.values():
        for line in d["path"].read_text(errors="replace").splitlines():
            m = re.search(r"notes=\[([^]]*)\]", line)
            if m and m.group(1):
                notes.update(x.strip().strip("'") for x in m.group(1).split(","))
    baseline = {"fruit did not follow the gripper", "fruit fell off the line"}
    g5 = notes <= baseline
    print(f"  G5 no new failure-reason key: {sorted(notes)}  "
          f"[{'PASS' if g5 else 'FAIL'}]")
    rc |= 0 if g5 else 1
    print(f"  gates rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
