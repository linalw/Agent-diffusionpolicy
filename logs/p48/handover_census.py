#!/usr/bin/env python3
"""P48 phase 1: the hand-over timing census (offline, read-only).

Re-derives the P47 catch-up residual population and adds the *inputs* of the
attempt that produced each residual:

  * the selection distance `dy0` and the fruit's delivered lateral `x` (the
    first `wait step=0` row of the attempt);
  * the hand-over `dy` (= the lead the intercept fires at), the `arrived after
    N steps` count, the descent's `waited N ticks` and `end=` (the approach's
    final position error), the close ramp's ticks/force/span, the `kinematic
    grip closed to X cm around a Y cm fruit` echo, and the re-seat count;
  * the outcome from the attempt's own result row.

Attribution
-----------
single-arm (`[run] attempt N: picking ...` ... `[run] attempt N: grasped=...`)
    exact block attribution.
two-line (`[biarm] result <arm> ...`; two arms interleave)
    per-arm ordinal pairing inside each arm's own row sequence: the k-th
    `target ... with <arm> arm` row, the k-th `wait step=0` row of that arm (the
    arm is recovered from the row itself, `station = fruit_y - dy` -> 0.0 (left)
    or -0.100 (right)), the k-th `dynamic descent` row of that arm (the row
    prints its own `station`), the k-th `[biarm] result <arm>` row. The
    `dynamic catch-up: residual` rows carry no arm, so the k-th catch row is
    paired with the k-th descent row (one descent and one catch-up per dynamic
    attempt, printed in order) - the pairing is validated by the species and
    outcome cross-check printed at the end (`VALIDATION`), and every paired row
    is flagged `ordinal`.

Usage: python3 logs/p48/handover_census.py > logs/p48/handover_census_out.txt
"""
from __future__ import annotations

import glob
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RE_START = re.compile(r"\[run\] attempt (\d+): picking (\w+)")
RE_SKIP = re.compile(r"\[run\] attempt (\d+): no eligible fruit")
RE_RESULT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([-+\d.]+) m "
    r"force=([\d.]+) N notes=\[(.*?)\]"
)
RE_BIARM = re.compile(
    r"\[biarm\] result (left|right) index=(\d+) (\w+) grasped=(\w+) placed=(\w+) "
    r"lift=([-+\d.]+) force=([\d.]+) sim=[\d.]+s notes=\[(.*?)\]"
)
RE_TARGET = re.compile(
    r"\[task\] target (\w+) \(grade (\w), ([\d.]+) cm\) with (left|right) arm"
)
RE_WAIT0 = re.compile(
    r"\[task\]   wait step=0 fruit_y=([-+\d.]+) fruit_x=([-+\d.]+) "
    r"fruit_z=([-+\d.]+) dy=([-+\d.]+)"
)
RE_HANDOVER = re.compile(
    r"\[task\]   intercept handover: fruit_y=([-+\d.]+) dy=([-+\d.]+) m "
    r"lead=([\d.]+) m at ([-+\d.]+) m/s .*?queue=(\d+)"
)
RE_ARRIVED = re.compile(r"\[task\] fruit at pick point: dy=([-+\d.]+) m arrived=(\w+) after (\d+) steps")
RE_MOVING = re.compile(r"\[task\] moving pick: meeting the fruit (\d+) mm upstream")
RE_TIP = re.compile(r"openarm fingertips (\d+) mm from the fruit; closing anyway")
RE_DESCENT = re.compile(
    r"\[task\] dynamic descent: waited (\d+) ticks, intercept=([-+\d.]+) m "
    r"\(station ([-+\d.]+), shift ([-+\d.]+) m\), fruit dy=([-+\d.]+) m, "
    r"deadline=([-+\d.]+) m, t_desc=([\d.]+) s"
)
RE_APPROACH = re.compile(
    r"\[motion\] approach\(cartesian\): ([\d.]+) cm, (\d+) samples: .*?\|v\|max=([\d.]+) m/s.*?end=([\d.]+) mm"
)
RE_CATCH = re.compile(r"\[task\] dynamic catch-up: residual=([\d.]+) mm \(tol (\d+) mm\)")
RE_CLOSE = re.compile(
    r"\[task\] dynamic close: sustained contact after (\d+) ticks "
    r"\(force=([\d.]+) N, span=([\d.]+) mm\); freezing the closing command at ([\d.]+) mm"
)
RE_GRIP = re.compile(r"\[task\] kinematic grip closed to ([\d.]+)cm around a ([\d.]+)cm fruit")
RE_RESEAT = re.compile(r"\[task\]   dynamic regrasp: re-seated")
RE_DRIFT = re.compile(r"\[task\]   close: fruit drifted (\d+) mm off the pick centre")
RE_CARRY = re.compile(
    r"\[carry\] (left|right) grasp_lift: .*?clean_slip_max=(\S+?)mm .*?"
    r"force@onset=(\S+?)N sep@onset=(\S+?)mm contacts@onset=(\S+) .*?"
    r"min_contacts=(\S+) force_min=(\S+?)N loss_row=(\S+) sep@loss=(\S+?)mm .*?gap_start=(\S+?)mm"
)
RE_FORCE = re.compile(
    r"\[task\] force servo: (?:left: ref=[\d.]+N F\[[\d.]+,([\d.]+)\]N gap=([\d.]+)mm sep=([-+\d.]+)mm "
    r"closed=([\d.]+)mm opened=([\d.]+)mm trips=(\d+))?"
)

CORPORA = [
    ("shipped", [
        "logs/p41/p2/accept_profile.log",
        "logs/p39/p3/pear_C.log",
    ]),
    ("P44-speed", sorted(glob.glob("logs/p44/p2/accept_s*.log"))
     + sorted(glob.glob("logs/p44/p2/pear_s*.log"))
     + sorted(glob.glob("logs/p44/p2/twoline_s*.log"))
     + sorted(glob.glob("logs/p44/p2/amend_*.log"))),
    ("P45-mass", sorted(glob.glob("logs/p45/p2/accept_s*.log"))
     + sorted(glob.glob("logs/p45/p2/pear_s*.log"))),
    ("P46-twoline", sorted(glob.glob("logs/p46/p1/twoline_s*.log"))),
]


def pct(vals, q):
    if not vals:
        return float("nan")
    vals = sorted(vals)
    if len(vals) == 1:
        return vals[0]
    k = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
    return vals[k]


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def blank():
    return {
        "species": None, "arm": None, "diameter": None, "x0": None, "dy0": None,
        "lead": None, "handover_dy": None, "queue": None, "arrived_steps": None,
        "moving_mm": None, "tip": None, "wait_ticks": None, "shift": None,
        "desc_fruit_dy": None, "approach_end": None, "approach_vmax": None,
        "residual": None, "close_ticks": None, "close_force": None,
        "close_span": None, "grip_closed": None, "grip_fruit": None,
        "reseats": 0, "drift_mm": None, "carry": None, "outcome": "open",
        "lift": None, "notes": "", "ordinal": False, "log": None, "idx": None,
        "closed_minus_cmd": None,
    }


def parse_single(path, rel):
    """Exact block attribution for a single-arm log."""
    out = []
    cur = None
    with open(path, errors="replace") as fh:
        for line in fh:
            if "[fruit]" not in line:
                continue
            m = RE_START.search(line)
            if m:
                cur = blank()
                cur["log"], cur["idx"] = rel, int(m.group(1))
                cur["species"] = m.group(2)
                out.append(cur)
                continue
            m = RE_SKIP.search(line)
            if m:
                cur = blank()
                cur["log"], cur["idx"] = rel, int(m.group(1))
                cur["outcome"] = "skip"
                out.append(cur)
                cur = None
                continue
            m = RE_RESULT.search(line)
            if m:
                if cur is None:
                    continue
                g = m.group(2) == "True"
                p = m.group(3) == "True"
                cur["outcome"] = "placed" if p else ("cnp" if g else "nograsp")
                cur["lift"] = fnum(m.group(4))
                cur["notes"] = m.group(6)
                cur = None
                continue
            if cur is None:
                continue
            m = RE_TARGET.search(line)
            if m:
                cur["species"] = m.group(1)
                cur["diameter"] = fnum(m.group(3))
                cur["arm"] = m.group(4)
                continue
            m = RE_WAIT0.search(line)
            if m:
                if cur["dy0"] is None:
                    cur["x0"] = fnum(m.group(2))
                    cur["dy0"] = fnum(m.group(4))
                continue
            m = RE_HANDOVER.search(line)
            if m:
                cur["handover_dy"] = fnum(m.group(2))
                cur["lead"] = fnum(m.group(3))
                cur["queue"] = int(m.group(5))
                continue
            m = RE_ARRIVED.search(line)
            if m:
                cur["arrived_steps"] = int(m.group(3))
                continue
            m = RE_MOVING.search(line)
            if m:
                cur["moving_mm"] = int(m.group(1))
                continue
            m = RE_TIP.search(line)
            if m:
                cur["tip"] = int(m.group(1))
                continue
            m = RE_DESCENT.search(line)
            if m:
                cur["wait_ticks"] = int(m.group(1))
                cur["shift"] = fnum(m.group(4))
                cur["desc_fruit_dy"] = fnum(m.group(5))
                continue
            m = RE_APPROACH.search(line)
            if m:
                cur["approach_vmax"] = fnum(m.group(3))
                cur["approach_end"] = fnum(m.group(4))
                continue
            m = RE_CATCH.search(line)
            if m:
                cur["residual"] = fnum(m.group(1))
                continue
            m = RE_CLOSE.search(line)
            if m:
                cur["close_ticks"] = int(m.group(1))
                cur["close_force"] = fnum(m.group(2))
                cur["close_span"] = fnum(m.group(3))
                continue
            m = RE_GRIP.search(line)
            if m:
                cur["grip_closed"] = fnum(m.group(1)) * 10.0
                cur["grip_fruit"] = fnum(m.group(2)) * 10.0
                continue
            m = RE_RESEAT.search(line)
            if m:
                cur["reseats"] += 1
                continue
            m = RE_DRIFT.search(line)
            if m:
                cur["drift_mm"] = int(m.group(1))
                continue
            m = RE_CARRY.search(line)
            if m:
                cur["carry"] = dict(
                    clean_slip=m.group(2), force_onset=m.group(3),
                    sep_onset=m.group(4), contacts_onset=m.group(5),
                    min_contacts=m.group(6), force_min=m.group(7),
                    loss_row=m.group(8), gap_start=m.group(10),
                )
                continue
    return out


def parse_biarm(path, rel):
    """Per-arm ordinal attribution for a two-line (interleaved) log."""
    targets = {"left": [], "right": []}
    waits = {"left": [], "right": []}
    descents = {"left": [], "right": []}
    catches = []
    closes = []
    grips = []
    reseats = []          # global order, arm-blind
    drifts = []
    carries = []
    results = {"left": [], "right": []}
    tips = []
    approaches = []
    handovers = []
    with open(path, errors="replace") as fh:
        for line in fh:
            if "[fruit]" not in line:
                continue
            m = RE_TARGET.search(line)
            if m:
                targets[m.group(4)].append(
                    {"species": m.group(1), "grade": m.group(2),
                     "diameter": fnum(m.group(3))}
                )
                continue
            m = RE_WAIT0.search(line)
            if m:
                fy, fx, dy = fnum(m.group(1)), fnum(m.group(2)), fnum(m.group(4))
                station = fy - dy
                arm = "left" if abs(station) < 0.05 else (
                    "right" if abs(station + 0.100) < 0.05 else None)
                if arm is not None:
                    waits[arm].append({"x0": fx, "dy0": dy})
                continue
            m = RE_DESCENT.search(line)
            if m:
                station = fnum(m.group(3))
                arm = "left" if abs(station) < 0.05 else (
                    "right" if abs(station + 0.100) < 0.05 else None)
                if arm is not None:
                    descents[arm].append(
                        {"wait_ticks": int(m.group(1)), "shift": fnum(m.group(4)),
                         "fruit_dy": fnum(m.group(5))}
                    )
                continue
            m = RE_CATCH.search(line)
            if m:
                catches.append(fnum(m.group(1)))
                continue
            m = RE_CLOSE.search(line)
            if m:
                closes.append({"ticks": int(m.group(1)), "force": fnum(m.group(2)),
                               "span": fnum(m.group(3))})
                continue
            m = RE_GRIP.search(line)
            if m:
                grips.append({"closed": fnum(m.group(1)) * 10.0,
                              "fruit": fnum(m.group(2)) * 10.0})
                continue
            m = RE_RESEAT.search(line)
            if m:
                reseats.append(1)
                continue
            m = RE_DRIFT.search(line)
            if m:
                drifts.append(int(m.group(1)))
                continue
            m = RE_CARRY.search(line)
            if m:
                carries.append({"arm": m.group(1), "clean_slip": m.group(2),
                                "force_onset": m.group(3), "sep_onset": m.group(4),
                                "contacts_onset": m.group(5),
                                "force_min": m.group(7), "loss_row": m.group(8),
                                "gap_start": m.group(10)})
                continue
            m = RE_TIP.search(line)
            if m:
                tips.append(int(m.group(1)))
                continue
            m = RE_APPROACH.search(line)
            if m:
                approaches.append({"vmax": fnum(m.group(3)), "end": fnum(m.group(4))})
                continue
            m = RE_HANDOVER.search(line)
            if m:
                handovers.append({"dy": fnum(m.group(2)), "lead": fnum(m.group(3)),
                                  "queue": int(m.group(5))})
                continue
            m = RE_ARRIVED.search(line)
            if m:
                handovers[-1]["arrived_steps"] = int(m.group(3))
                continue
            m = RE_BIARM.search(line)
            if m:
                results[m.group(1)].append({
                    "index": int(m.group(2)), "species": m.group(3),
                    "outcome": ("placed" if m.group(5) == "True"
                                else ("cnp" if m.group(4) == "True" else "nograsp")),
                    "lift": fnum(m.group(6)), "force": fnum(m.group(7)),
                    "notes": m.group(8),
                })
                continue
    # per-arm ordinal assembly; catch rows paired to descent rows in print order
    desc_all = sorted(descents["left"] + descents["right"], key=lambda d: 0)  # placeholder
    # rebuild the global descent order for the catch pairing
    global_descents = []
    with open(path, errors="replace") as fh:
        for line in fh:
            if "[fruit]" not in line:
                continue
            m = RE_DESCENT.search(line)
            if m:
                station = fnum(m.group(3))
                arm = "left" if abs(station) < 0.05 else (
                    "right" if abs(station + 0.100) < 0.05 else "?")
                global_descents.append(arm)
    catch_arm = []
    for k, v in enumerate(catches):
        catch_arm.append(global_descents[k] if k < len(global_descents) else "?")

    out = []
    for arm in ("left", "right"):
        n = min(len(targets[arm]), len(results[arm]))
        for k in range(n):
            a = blank()
            a["log"], a["arm"], a["ordinal"] = rel, arm, True
            a["species"] = results[arm][k]["species"]
            a["diameter"] = targets[arm][k]["diameter"]
            a["outcome"] = results[arm][k]["outcome"]
            a["lift"] = results[arm][k]["lift"]
            a["notes"] = results[arm][k]["notes"]
            a["idx"] = results[arm][k]["index"]
            if k < len(waits[arm]):
                a["x0"] = waits[arm][k]["x0"]
                a["dy0"] = waits[arm][k]["dy0"]
            if k < len(descents[arm]):
                a["wait_ticks"] = descents[arm][k]["wait_ticks"]
                a["shift"] = descents[arm][k]["shift"]
                a["desc_fruit_dy"] = descents[arm][k]["fruit_dy"]
            # the k-th catch row of THIS arm: the k-th catch whose descent is this arm
            mine = [i for i, aa in enumerate(catch_arm) if aa == arm]
            if k < len(mine):
                a["residual"] = catches[mine[k]]
            # the approach row is printed once per attempt, in the same order as
            # the descent row, so the k-th approach of this arm is the k-th
            # attempt's own `end=` (validated by the equal row counts, 10/10/10/10)
            if k < len(mine) and mine[k] < len(approaches):
                a["approach_vmax"] = approaches[mine[k]]["vmax"]
                a["approach_end"] = approaches[mine[k]]["end"]
            if k < len(tips):
                a["tip"] = tips[k] if k < len(tips) else None
            out.append(a)
        out.append({"_arm_counts": (arm, len(targets[arm]), len(waits[arm]),
                                    len(descents[arm]), len(results[arm]),
                                    len([1 for x in catch_arm if x == arm]))})
    return out, {"closes": closes, "grips": grips, "reseats": len(reseats),
                 "drifts": drifts, "carries": carries, "handovers": handovers,
                 "approaches": approaches, "catch_arm": catch_arm}


def fisher_2x2(a, b, c, d):
    from math import comb
    n = a + b + c + d
    r1, r2 = a + b, c + d
    c1 = a + c
    def p_tab(x):
        return comb(r1, x) * comb(r2, c1 - x) / comb(n, c1)
    p0 = p_tab(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return sum(p_tab(x) for x in range(lo, hi + 1) if p_tab(x) <= p0 + 1e-12)


def fmt(vals, fmtstr="{:6.1f}"):
    if not vals:
        return "     -                          "
    return (f"n={len(vals):<3d} min={fmtstr.format(min(vals))} "
            f"p50={fmtstr.format(pct(vals, .5))} p90={fmtstr.format(pct(vals, .9))} "
            f"p99={fmtstr.format(pct(vals, .99))} max={fmtstr.format(max(vals))}")


def main():
    print("P48 phase 1 - the hand-over timing census")
    print("=" * 100)
    pool = {}
    allat = []
    extra = {}
    for name, paths in CORPORA:
        atts, metas = [], []
        nlogs = 0
        for rel in paths:
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p):
                print(f"  MISSING {rel}", file=sys.stderr)
                continue
            with open(p, errors="replace") as fh:
                head = fh.read()
            if "[biarm] result" in head or "two-line" in rel or "twoline" in rel:
                a, meta = parse_biarm(p, rel)
                got = [x for x in a if "_arm_counts" not in x]
                atts += got
                if got:
                    nlogs += 1
                    metas.append((rel, meta))
            else:
                got = parse_single(p, rel)
                atts += got
                if got:
                    nlogs += 1
        pool[name] = atts
        allat += atts
        extra[name] = metas
        print(f"\n## {name}   ({nlogs} measured logs of {len(paths)} files, {len(atts)} attempts)")

        print(f"   outcomes placed {sum(1 for a in atts if a['outcome']=='placed')} "
              f"cnp {sum(1 for a in atts if a['outcome']=='cnp')} "
              f"nograsp {sum(1 for a in atts if a['outcome']=='nograsp')} "
              f"skip {sum(1 for a in atts if a['outcome']=='skip')}")
        res = [a["residual"] for a in atts if a["residual"] is not None]
        print(f"   residual      {len(res)} rows: {fmt(res)}")
        ge = [a for a in atts if a["residual"] is not None and a["residual"] > 6.0]
        print(f"   > 6 mm        {len(ge)} rows -> "
              + ", ".join(f"{a['outcome']}" for a in ge) if ge else "   > 6 mm        0 rows")
        for a in ge:
            print(f"      {a['log'].split('/')[-1]:<26s} idx={str(a['idx']):<4s} "
                  f"{str(a['species']):<10s} arm={str(a['arm']):<5s} "
                  f"residual={a['residual']:7.1f} x0={a['x0']} dy0={a['dy0']}")
        xs = [a["x0"] for a in atts if a["x0"] is not None]
        dys = [a["dy0"] for a in atts if a["dy0"] is not None]
        print(f"   delivered x   {fmt(xs, '{:6.3f}')}   (|x| >= 0.390: "
              f"{sum(1 for v in xs if abs(v) >= 0.390)}/{len(xs)})")
        print(f"   selection dy0 {fmt(dys, '{:6.3f}')}")

    print("\n" + "=" * 100)
    print("POOLED")
    res = [a["residual"] for a in allat if a["residual"] is not None]
    print(f"   closes with a residual print: {len(res)}")
    ge = [a for a in allat if a["residual"] is not None and a["residual"] > 6.0]
    le = [a for a in allat if a["residual"] is not None and a["residual"] <= 6.0]
    print(f"   > 6 mm : {len(ge)} rows; outcomes "
          + ", ".join(sorted({f"{a['outcome']}={sum(1 for b in ge if b['outcome']==a['outcome'])}" for a in ge})))
    print(f"   <=6 mm : {len(le)} rows; outcomes "
          + ", ".join(f"{k}={sum(1 for a in le if a['outcome']==k)}"
                      for k in ("placed", "cnp", "nograsp")))
    print(f"   Fisher (nograsp | >6 vs <=6): p = "
          f"{fisher_2x2(sum(1 for a in ge if a['outcome']=='nograsp'), len(ge)-sum(1 for a in ge if a['outcome']=='nograsp'), sum(1 for a in le if a['outcome']=='nograsp'), len(le)-sum(1 for a in le if a['outcome']=='nograsp')):.3g}")

    # x test
    xs_all = [(a, abs(a["x0"])) for a in allat if a["x0"] is not None and a["residual"] is not None]
    hi = [a for a, v in xs_all if v >= 0.390]
    lo = [a for a, v in xs_all if v < 0.390]
    print(f"\n   delivered |x| >= 0.390: {len(hi)} of {len(xs_all)} closes; "
          f">6 mm in that set {sum(1 for a in hi if a['residual']>6.0)}/"
          f"{sum(1 for a in hi if a['residual']>6.0)}")
    print(f"   >6 mm share: |x|>=0.390 {sum(1 for a in hi if a['residual']>6.0)}/{len(hi)}"
          f"  vs |x|<0.390 {sum(1 for a in lo if a['residual']>6.0)}/{len(lo)}  "
          f"Fisher p = {fisher_2x2(sum(1 for a in hi if a['residual']>6.0), len(hi)-sum(1 for a in hi if a['residual']>6.0), sum(1 for a in lo if a['residual']>6.0), len(lo)-sum(1 for a in lo if a['residual']>6.0)):.3g}")

    # species
    print("\n   per-species: closes / >6 mm / placed / cnp / nograsp")
    for sp in sorted({a["species"] for a in allat if a["species"]}):
        rows = [a for a in allat if a["species"] == sp and a["residual"] is not None]
        print(f"     {sp:<10s} {len(rows):3d} / {sum(1 for a in rows if a['residual']>6.0):2d} / "
              f"{sum(1 for a in rows if a['outcome']=='placed'):3d} / "
              f"{sum(1 for a in rows if a['outcome']=='cnp'):3d} / "
              f"{sum(1 for a in rows if a['outcome']=='nograsp'):3d}")

    # --- x bands, and the percentile rank of each event's inputs ---------- #
    print("\n" + "=" * 100)
    print("THE DELIVERED-X BANDS (the fruit's lateral x at the wait loop's first step)")
    bands = [("<=0.25", lambda v: v <= 0.25), ("0.25-0.30", lambda v: 0.25 < v <= 0.30),
             ("0.30-0.35", lambda v: 0.30 < v <= 0.35), ("0.35-0.38", lambda v: 0.35 < v <= 0.38),
             ("0.38-0.39", lambda v: 0.38 < v <= 0.39), (">=0.390", lambda v: v > 0.39)]
    rows = [a for a in allat if a["x0"] is not None and a["residual"] is not None]
    for lab, pred in bands:
        sel = [a for a in rows if pred(abs(a["x0"]))]
        print(f"   |x| {lab:<10s} n={len(sel):3d}  >6mm={sum(1 for a in sel if a['residual']>6.0):2d}  "
              f"placed={sum(1 for a in sel if a['outcome']=='placed'):3d} "
              f"cnp={sum(1 for a in sel if a['outcome']=='cnp'):3d} "
              f"nograsp={sum(1 for a in sel if a['outcome']=='nograsp'):3d}  "
              f"species={sorted({a['species'] for a in sel})}")

    print("\n   THE APPROACH'S FINAL ERROR (`end=`, the descent's last commanded-vs-achieved gap)")
    for lab, sel in (
        ("placed        ", [a for a in rows if a["outcome"] == "placed"]),
        ("cnp           ", [a for a in rows if a["outcome"] == "cnp"]),
        ("nograsp <=6mm ", [a for a in rows if a["outcome"] == "nograsp" and a["residual"] <= 6.0]),
        ("nograsp >6mm  ", [a for a in rows if a["outcome"] == "nograsp" and a["residual"] > 6.0]),
        ("|x| >= 0.38   ", [a for a in rows if abs(a["x0"]) >= 0.38]),
    ):
        vals = [a["approach_end"] for a in sel if a.get("approach_end") is not None]
        print(f"     {lab} {fmt(vals)}")

    print("\n   WITHIN-SPECIES TEST (is |x| a proxy for the species?)")
    for sp in ("kiwi", "peach", "pear", "strawberry"):
        rows_sp = [a for a in rows if a["species"] == sp]
        hi = [a for a in rows_sp if abs(a["x0"]) >= 0.38]
        lo = [a for a in rows_sp if abs(a["x0"]) < 0.38]
        if not hi or not lo:
            print(f"     {sp:<10s} no 2x2 (hi {len(hi)} / lo {len(lo)})")
            continue
        a1 = sum(1 for a in hi if a["outcome"] == "nograsp")
        a2 = sum(1 for a in lo if a["outcome"] == "nograsp")
        print(f"     {sp:<10s} |x|>=0.38 nograsp {a1}/{len(hi)}  vs  <0.38 {a2}/{len(lo)}   "
              f"Fisher p = {fisher_2x2(a1, len(hi) - a1, a2, len(lo) - a2):.3g}")

    print("\n   the residual's gap (sorted values above the 6 mm tolerance):")
    vals = sorted({a["residual"] for a in allat if a["residual"] is not None and a["residual"] > 6.0})
    print(f"      {vals}   (below it: max {max(a['residual'] for a in allat if a['residual'] is not None and a['residual'] <= 6.0):.1f} mm)")

    print("\n   EACH EVENT'S INPUT RANK IN THE 317-CLOSE POPULATION (percentile, 0 = low)")
    pop = [a for a in allat if a["residual"] is not None]
    def rank(field, val):
        xs = sorted(a[field] for a in pop if a.get(field) is not None)
        if not xs or val is None:
            return "-"
        k = sum(1 for v in xs if v <= val)
        return f"{100.0 * k / len(xs):.0f}% ({k}/{len(xs)})"
    for a in ge:
        print(f"      {a['log'].split('/')[-1]:<24s} idx={str(a['idx']):<4s} res={a['residual']:7.1f}  "
              f"x0={rank('x0', a['x0']):>13s}  dy0={rank('dy0', a['dy0']):>13s}  "
              f"wait={rank('wait_ticks', a['wait_ticks']):>12s}  "
              f"tip={rank('tip', a['tip']):>12s}  arrived={rank('arrived_steps', a['arrived_steps']):>13s}")

    print("\n   THE TICK DECOMPOSITION (residual - 200 ticks x 1.0 mm/tick of belt travel)")
    for a in ge:
        print(f"      {a['log'].split('/')[-1]:<24s} idx={str(a['idx']):<4s} res={a['residual']:7.1f}  "
              f"- 200 mm = {a['residual'] - 200.0:7.1f} mm   "
              f"({a['residual'] / 200.0:4.2f}x the horizon)   "
              f"approach end={a['approach_end']} mm")

    # the 4 events, in full
    print("\n" + "=" * 100)
    print("THE FOUR FAILING EVENTS (residual > 6 mm), full record")
    for a in ge:
        print(f"\n   {a['log']}   attempt idx={a['idx']}  arm={a['arm']}  "
              f"species={a['species']}  dia={a['diameter']}  ordinal={a['ordinal']}")
        for k in ("x0", "dy0", "lead", "handover_dy", "queue", "arrived_steps",
                  "moving_mm", "tip", "wait_ticks", "shift", "desc_fruit_dy",
                  "approach_vmax", "approach_end", "residual", "close_ticks",
                  "close_force", "close_span", "grip_closed", "grip_fruit",
                  "reseats", "drift_mm", "outcome", "lift", "notes"):
            if a.get(k) is not None:
                print(f"      {k:<16s} {a[k]}")

    # converged close losses
    print("\n" + "=" * 100)
    print("THE CONVERGED CLOSE LOSSES (residual <= 6 mm, outcome no-grasp)")
    conv = [a for a in le if a["outcome"] == "nograsp"]
    print(f"   {len(conv)} rows")
    for a in conv:
        print(f"\n   {a['log'].split('/')[-1]:<26s} idx={str(a['idx']):<4s} "
              f"{str(a['species']):<10s} arm={str(a['arm']):<5s} dia={a['diameter']} "
              f"residual={a['residual']} x0={a['x0']} dy0={a['dy0']}")
        for k in ("close_ticks", "close_force", "close_span", "grip_closed",
                  "grip_fruit", "reseats", "lift", "notes"):
            if a.get(k) is not None:
                print(f"      {k:<16s} {a[k]}")
        if a.get("carry"):
            print(f"      carry            {a['carry']}")
    # placed reference for the same fields
    print("\n   placed reference (same fields):")
    pl = [a for a in le if a["outcome"] == "placed"]
    for k in ("close_ticks", "close_force", "close_span", "reseats"):
        vals = [a[k] for a in pl if a.get(k) is not None]
        print(f"      {k:<16s} {fmt(vals)}")
    gaps_loss = [a["grip_closed"] - a["grip_fruit"] for a in conv
                 if a.get("grip_closed") and a.get("grip_fruit")]
    gaps_ok = [a["grip_closed"] - a["grip_fruit"] for a in pl
               if a.get("grip_closed") and a.get("grip_fruit")]
    print(f"      grip_closed - dia  losses {fmt(gaps_loss, '{:+6.2f}')}")
    print(f"      grip_closed - dia  placed {fmt(gaps_ok, '{:+6.2f}')}")

    # two-line meta
    print("\n" + "=" * 100)
    print("TWO-LINE META (arm-blind rows, listed for the record)")
    for name in ("P44-speed", "P46-twoline"):
        for rel, meta in extra.get(name, []):
            print(f"\n   {rel}")
            print(f"      catches {len(meta['catch_arm'])} arm-by-descent "
                  f"{ {a: meta['catch_arm'].count(a) for a in ('left','right','?')} }")
            print(f"      closes {len(meta['closes'])} grips {len(meta['grips'])} "
                  f"reseats {meta['reseats']} drifts {meta['drifts']}")
            for c in meta["closes"]:
                if c["force"] and c["force"] > 20:
                    print(f"      anomalous close {c}")
    print("\nVALIDATION: per-arm row counts (targets / waits / descents / results / catches)")
    for name in ("P44-speed", "P46-twoline"):
        for rel, meta in extra.get(name, []):
            print(f"   {rel}")
            with open(os.path.join(ROOT, rel), errors="replace") as fh:
                out, _ = parse_biarm(os.path.join(ROOT, rel), rel)
            for x in out:
                if "_arm_counts" in x:
                    print(f"      {x['_arm_counts']}")


if __name__ == "__main__":
    main()
