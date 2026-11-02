#!/usr/bin/env python3
"""P104 report: read `logs/p104/fixture.txt` and print the tables RESULTS.md quotes.

    python3 logs/p104/p104_report.py            # -> logs/p104/fixture_table.txt
    python3 logs/p104/p104_report.py --json     # the same rows as JSON

Pure python: the fixture file is the record, this only aggregates it. Three
columns matter, and they are three different questions:

* `settle`   - the payload's displacement **under its own weight** before the
               ramp starts: the static hold at the load the cell applies.
* `F2mm`     - `apply` + the payload's weight at the tick its displacement first
               reaches 2 mm: the survey's own criterion (`clean_slip > 2 mm`).
               A 3+ contact grasp can **re-seat** after 2 mm, so this is a first
               slip, not necessarily a break.
* `Fexit`    - the same load at the tick the payload is finally lost (30 mm).
               This is the sustained capacity, and it is the one the ratios use.
"""

from __future__ import annotations

import json
import re
import statistics as st
import sys

PATH = "logs/p104/fixture.txt"
FORMS = (
    "pinch_plate",
    "pinch_tip",
    "tripod",
    "quad",
    "lip",
    "pinch_tip_moment",
    "tripod_moment",
)
FRUITS = ("pear", "orange", "strawberry")
NUM = r"([-\d.]+|nan)"
ROW = re.compile(
    r"^(pinch_plate|pinch_tip|tripod|quad|lip|pinch_tip_moment|tripod_moment)\s+(\w+)\s+"
    r"([\d.]+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+" + NUM + r"\s+([\d.]+)\s+" + NUM
    + r"\s+([\d.]+)"
)


def load(path: str = PATH) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = ROW.match(line.strip())
            if not m:
                continue
            rows.append(
                {
                    "form": m.group(1),
                    "fruit": m.group(2),
                    "d_mm": float(m.group(3)),
                    "mu_fruit": float(m.group(4)),
                    "n": int(m.group(5)),
                    "N": float(m.group(6)),
                    "settle_mm": float(m.group(7)),
                    "f2mm": float(m.group(8)),
                    "disp_mm": float(m.group(9)),
                    "fexit": float(m.group(10)),
                    "max_mm": float(m.group(11)),
                }
            )
    return rows


def main(argv: list[str]) -> int:
    rows = load()
    if not rows:
        print(f"{PATH}: no rows", file=sys.stderr)
        return 2
    if "--json" in argv:
        print(json.dumps(rows, indent=1))
        return 0

    print(f"P104 fixture: {len(rows)} rows from {PATH}")
    print("(N = per-contact normal force, measured; settle = the payload's own-weight")
    print(" displacement before the ramp; F2mm = the survey's criterion; Fexit = the")
    print(" sustained capacity; sd = the spread over 3 repeats)")
    tab: dict[tuple[str, str], float] = {}
    for fruit in FRUITS:
        print(f"\n== {fruit} ==")
        print(f"{'form':16s} {'n':>2s} {'N[N]':>5s} {'settle':>7s} {'F2mm':>7s} "
              f"{'Fexit':>7s} {'sd':>5s}  reps")
        for form in FORMS:
            cell = [r for r in rows if r["form"] == form and r["fruit"] == fruit]
            if not cell:
                continue
            exits = [r["fexit"] for r in cell]
            good = [v for v in exits if v == v]
            mean = st.mean(good) if good else float("nan")
            sd = st.pstdev(good) if len(good) > 1 else 0.0
            tab[(form, fruit)] = mean
            print(
                f"{form:16s} {cell[0]['n']:2d} {cell[0]['N']:5.2f} "
                f"{st.mean([r['settle_mm'] for r in cell]):7.2f} "
                f"{st.mean([r['f2mm'] for r in cell]):7.2f} {mean:7.2f} {sd:5.2f}  "
                f"{[round(v, 2) for v in exits]}"
            )
    print("\n== ratios: sustained capacity vs the two controls ==")
    print("(tip = the matched 16 mm two-pad control, plate = the shipped 61 mm pinch;")
    print(" >N = the payload never left inside the 40 N ramp cap, so it is a bound)")
    for fruit in FRUITS:
        tip = tab[("pinch_tip", fruit)]
        plate = tab[("pinch_plate", fruit)]
        line = f"{fruit:11s} tip={tip:5.2f} plate={plate:5.2f} | "
        for form in ("tripod", "quad", "lip", "pinch_tip_moment", "tripod_moment"):
            v = tab[(form, fruit)]
            if v != v:
                line += f"{form}=>40.00  "
            else:
                line += f"{form}={v:5.2f}({v/tip:4.2f}x/{v/plate:4.2f}x) "
        print(line)
    print("\n== implied pair friction mu_app = Fexit / (n * N) ==")
    for form in ("pinch_plate", "pinch_tip", "tripod", "quad"):
        vals = []
        for fruit in FRUITS:
            cell = [r for r in rows if r["form"] == form and r["fruit"] == fruit]
            for r in cell:
                if r["fexit"] == r["fexit"]:
                    vals.append(r["fexit"] / (r["n"] * r["N"]))
        if vals:
            print(f"  {form:12s} {min(vals):4.2f} .. {max(vals):4.2f}  (mean {st.mean(vals):4.2f})")
    print("\n== the survey's criterion (F2mm) vs the sustained one (Fexit) ==")
    for fruit in FRUITS:
        tip = tab[("pinch_tip", fruit)]
        plate = tab[("pinch_plate", fruit)]
        tri2 = st.mean([r["f2mm"] for r in rows if r["form"] == "tripod" and r["fruit"] == fruit])
        tri = tab[("tripod", fruit)]
        print(f"  {fruit:11s} tripod F2mm {tri2/tip:4.2f}x / {tri2/plate:4.2f}x   "
              f"tripod Fexit {tri/tip:4.2f}x / {tri/plate:4.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
