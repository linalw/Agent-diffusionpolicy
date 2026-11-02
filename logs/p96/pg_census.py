#!/usr/bin/env python3
"""P96 section 1-2: the **pre-leg pad census** - does the inactive hand clear the fruit?

    python3 logs/p96/pg_census.py                  # -> logs/p96/pg_census.txt
    python3 logs/p96/pg_census.py --same A B       # longest common `[fruit]` prefix

The criterion is `logs/p95/METHOD_A1.md` A1.2 verbatim (P96 PREREG section 1): a
**contact** is `pad gap <= 6 mm` **and** that hand's **measured jaw-span swing
`>= 2 mm`** within +-4 ticks of the closest tick. The span is the verdict (a
commanded close cannot move the span 2 mm: the finger drive is stiffness-limited
to 0.1 mm at P41's `k = 1e5 N/m` and the 10 N cap); the gap ranks, +-5 mm,
because the finger plates are angled at a 98 mm span.

Geometry, inherited from `logs/p95/probe.py` (same constants, same sign
conventions): the **pad point** of a hand is `jaw - 0.0805 z` displaced
`+-sep/2` along the closing axis (X on this cell), so `pad gap = |pad - fruit| -
radius` with the fruit's radius taken as 31 mm, and `dy` is that pad's along-belt
offset. `logs/p95/probe.py`'s own note applies: the pad point is a *proxy* - the
authored pad body is a plate around it - which is why the gap is an indicator and
the span is the verdict. The same proxy is applied to every cell, so the
before/after comparison is like-for-like, and the phase's **static** witness
(the authored pad bodies' lowest world point) is `prepose_check_rows*.json`.

The **descent leg's start** is the first `descent`-labelled tick minus that leg's
own `[motion] approach ... steps=` (P95 A1.3: `_cycle_mark("descent")` fires after
`_approach`). Everything before that tick is the window the invariant is about:
the pre-pose blend, the hover and the descent's wait.

Read-only.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PAD_DROP = 0.0805
DSEP_TOUCH = 2.0      # mm of jaw-span change = a pad contact (P95 A1.2)
GAP_TOUCH = 6.0       # mm, the +-5 mm indicator's own band (P95 A1.2)
RADIUS = 0.031        # the fruit's radius used by P95's pad-point proxy

#: cell -> (seed, treatment?, trace dir, its own record)
CELLS = [
    ("C5", 5, False, "tr5c", "logs/p94/T5.log"),
    ("T5", 5, True, "tr5t", "logs/p94/T5.log"),
    ("C6", 6, False, "tr6c", "logs/p94/T6.log"),
    ("T6", 6, True, "tr6t", "logs/p94/T6.log"),
]

#: The cells added to the census for the *treatment* (the invariant's own cells).
CELL_ORDER = [c[0] for c in CELLS]


def fruit_lines(path, drop=("[ftrace]",)):
    out = []
    with open(path, errors="ignore") as fh:
        for line in fh:
            if "[fruit]" not in line:
                continue
            if any(tag in line for tag in drop):
                continue
            out.append(line.rstrip("\n"))
    return out


def compare(a, b):
    la, lb = fruit_lines(a), fruit_lines(b)
    n = 0
    for x, y in zip(la, lb):
        if x != y:
            break
        n += 1
    return {"a": a, "b": b, "lines_a": len(la), "lines_b": len(lb), "common": n,
            "identical": n == len(la) == len(lb),
            "first_a": la[n][:150] if n < len(la) else "",
            "first_b": lb[n][:150] if n < len(lb) else ""}


def traces(trace_dir):
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, trace_dir, "ftrace_*.json"))):
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        if not d["rows"] or d["rows"][0] is None:
            continue
        for row in d["rows"]:
            for key in ("left", "right"):
                arm = row.get("arm", {}).get(key)
                if arm is not None:
                    arm["_fruit"] = row["p"]
        out.append(d)
    return out


def approach_steps(cell):
    text = open(os.path.join(HERE, f"{cell}.log"), errors="ignore").read()
    return [int(m) for m in
            re.findall(r"\[motion\] approach\(cartesian\):.*?steps=(\d+)", text)]


def pad_of(arm):
    jaw, sep, fruit = arm.get("jaw"), arm.get("sep"), arm.get("_fruit")
    if jaw is None or sep is None or fruit is None:
        return None
    half = 0.5 * float(sep) * 1e-3
    dx = abs(float(jaw[0]) - float(fruit[0])) - half
    dy = float(jaw[1]) - float(fruit[1])
    dz = float(jaw[2]) - PAD_DROP - float(fruit[2])
    return ((dx * dx + dy * dy + dz * dz) ** 0.5 - RADIUS) * 1e3, dx * 1e3, dy * 1e3


def sep_swing(rows, key, i0, i1):
    vals = []
    for i in range(max(0, i0 - 1), min(len(rows), i1 + 2)):
        arm = rows[i].get("arm", {}).get(key) or {}
        if "sep" in arm:
            vals.append(float(arm["sep"]))
    return None if len(vals) < 2 else max(vals) - min(vals)


def pair_legs(cell, trace_dir):
    """`[(trace, leg_start_tick)]` - paired by the leg end's sim time (P95)."""
    steps = approach_steps(cell)
    entries = []
    for d in traces(trace_dir):
        first = next((i for i, r in enumerate(d["rows"]) if r["phase"] == "descent"), None)
        if first is None:
            continue
        entries.append((d["rows"][first]["t"], d, first))
    entries.sort(key=lambda e: e[0])
    out = []
    for k, (_, d, first) in enumerate(entries):
        n = steps[k] if k < len(steps) else None
        out.append((d, None if n is None else first - n, first, n))
    return out


def census_cell(cell, seed, treat, trace_dir, record, print_):
    """One cell's pre-leg pad table + the summary the phase is gated on."""
    print_("=" * 116)
    print_(f"{cell} (seed {seed}, {'clearance pre-pose' if treat else 'shipped pre-pose'})")
    print_("=" * 116)
    print_(f"  {'att':>3} {'arm':<5} {'fruit':<11} {'other':<5} {'min gap':>8} {'at t':>7} "
           f"{'dy':>6} {'dsep':>6} {'leg t':>7} {'pre-leg':>7} {'contact':>8}")
    rows_out = []
    for d, i_leg, first, steps in pair_legs(cell, trace_dir):
        rows = d["rows"]
        other = "left" if d["arm"] == "right" else "right"
        best = None
        for i in range(0, i_leg if i_leg is not None else first):
            arm = rows[i].get("arm", {}).get(other)
            if arm is None:
                continue
            p = pad_of(arm)
            if p is None:
                continue
            if best is None or abs(p[0]) < abs(best[0]):
                best = (p[0], rows[i]["t"], p[2], i)
        if best is None:
            continue
        swing = sep_swing(rows, other, best[3] - 4, best[3] + 4) or 0.0
        hit = abs(best[0]) <= GAP_TOUCH and swing >= DSEP_TOUCH
        rows_out.append({
            "att": d["attempt"], "arm": d["arm"], "fruit": d["category"], "other": other,
            "gap": best[0], "t": best[1], "dy": best[2], "swing": swing, "contact": hit,
            "leg_t": rows[first]["t"], "i_leg": i_leg, "tick": best[3],
        })
        print_(f"  {d['attempt']:>3} {d['arm']:<5} {d['category']:<11} {other:<5} "
               f"{best[0]:>+8.1f} {best[1]:>7.2f} {best[2]:>+6.0f} {swing:>6.1f} "
               f"{rows[first]['t']:>7.2f} {rows[best[3]]['phase']:>7} "
               f"{'CONTACT' if hit else '-':>8}")
    near = [r for r in rows_out if abs(r["gap"]) <= GAP_TOUCH]
    hits = [r for r in rows_out if r["contact"]]
    gaps = [r["gap"] for r in rows_out]
    print_()
    print_(f"  n={len(rows_out)}  min gap {min(gaps, default=float('nan')):+.1f} mm  "
           f"median {st.median(gaps) if gaps else float('nan'):+.1f} mm  "
           f"<= 6 mm {len(near)}/{len(rows_out)}  CONTACTS {len(hits)}/{len(rows_out)}")
    if hits:
        print_("  contacts: " + "; ".join(
            f"att {r['att']} {r['arm']} {r['fruit']} gap {r['gap']:+.1f} swing {r['swing']:.1f}"
            for r in hits))
    print_()
    return rows_out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--same", nargs=2, metavar=("A", "B"))
    ap.add_argument("--cells", nargs="*", default=None)
    args = ap.parse_args()
    if args.same:
        print(json.dumps(compare(args.same[0], args.same[1]), indent=1))
        return 0
    out = []

    def print_(line=""):
        out.append(line)

    print_("P96 - the pre-leg pad census: does the inactive hand clear the fruit's band?")
    print_("Criterion: P95 A1.2 - a CONTACT is `pad gap <= 6 mm` AND that hand's measured")
    print_("jaw-span swing `>= 2 mm` within +-4 ticks. The gap ranks (+-5 mm, the plates are")
    print_("angled at a 98 mm span); the span is the verdict (0.1 mm of commanded deflection).")
    print_()
    table = {}
    for cell, seed, treat, trace_dir, record in CELLS:
        if args.cells and cell not in args.cells:
            continue
        table[cell] = census_cell(cell, seed, treat, trace_dir, record, print_)

    # ---- the phase's endpoint: pooled over both seeds, per arm ----------------- #
    print_("=" * 116)
    print_("THE ENDPOINT - pooled per arm, control vs treatment")
    print_("=" * 116)
    print_(f"  {'cell':<4} {'set':<10} {'seed':>4} {'n':>3} {'min gap':>8} {'median':>7} "
           f"{'<=6mm':>6} {'contacts':>8}")
    summary = {}
    for cell, seed, treat, trace_dir, record in CELLS:
        rows = table.get(cell, [])
        if not rows:
            continue
        gaps = [r["gap"] for r in rows]
        summary[cell] = {
            "seed": seed, "treat": treat, "n": len(rows),
            "min": min(gaps), "median": st.median(gaps),
            "near": sum(1 for r in rows if abs(r["gap"]) <= GAP_TOUCH),
            "contacts": sum(1 for r in rows if r["contact"]),
        }
        s = summary[cell]
        print_(f"  {cell:<4} {'clearance' if treat else 'shipped':<10} {seed:>4} {s['n']:>3} "
               f"{s['min']:>+8.1f} {s['median']:>+7.1f} {s['near']:>6} {s['contacts']:>8}")
    # per arm, pooled over the two seeds
    print_()
    for arm in ("left", "right"):
        line = []
        for treat, name in ((False, "shipped"), (True, "clearance")):
            rows = [r for c in table for r in table[c] if (r["arm"] == arm)
                    and summary.get(c, {}).get("treat") is treat]
            if not rows:
                continue
            gaps = [r["gap"] for r in rows]
            line.append(
                f"{name}: n={len(rows)} min {min(gaps):+.1f} med {st.median(gaps):+.1f} "
                f"<=6mm {sum(1 for r in rows if abs(r['gap']) <= GAP_TOUCH)} "
                f"contacts {sum(1 for r in rows if r['contact'])}"
            )
        print_(f"  {arm:<5} " + "   |   ".join(line))
    print_()
    for treat, name in ((False, "shipped"), (True, "clearance")):
        rows = [r for c in table for r in table[c]
                if summary.get(c, {}).get("treat") is treat]
        if not rows:
            continue
        gaps = [r["gap"] for r in rows]
        print_(f"  {name:<10} pooled: n={len(rows)} min {min(gaps):+.1f} mm "
               f"median {st.median(gaps):+.1f} mm  <= 6 mm "
               f"{sum(1 for r in rows if abs(r['gap']) <= GAP_TOUCH)}/{len(rows)}  "
               f"CONTACTS {sum(1 for r in rows if r['contact'])}/{len(rows)}")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "pg_census.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
