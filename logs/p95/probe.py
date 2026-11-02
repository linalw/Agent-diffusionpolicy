"""P95 report: the incoming fruit's velocity history, and what moves it.

    python3 logs/p95/probe.py                 # -> logs/p95/probe.txt
    python3 logs/p95/probe.py --same A B      # longest common `[fruit]` prefix

Read-only. Reads the phase's cells (`logs/p95/{F6,A6,A5}.log`), the recorded
branches they are gated against (`logs/p94/{T6,T5}.log`) and the P93 witness
(`logs/p93/p1/D6C/trace/trace_01_right_scripted_fail.json`).

Definitions are pinned in `logs/p95/METHOD.md` (+ `A1`): a **jump** is one tick
changing the fruit's speed by >= 0.03 m/s or its spin by >= 2.0 rad/s; a
**cluster** merges such ticks across <= 3-tick gaps; a **departure** is a
cluster whose peak one-tick speed change is >= 0.05 m/s. The **pad point** of a
hand is `jaw - 0.0805 z` displaced `+-sep/2` along the closing axis (X on this
cell - `configs/waypoints_oriented.json`'s own constraint), so
`pad gap = |pad - fruit| - radius` is a clearance and `dy` the along-belt
offset. The **descent leg's start** is the first `descent`-labelled tick minus
that leg's `[motion] approach ... steps=`, because `_cycle_mark("descent")` fires
*after* `_approach`.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PAD_DROP = 0.0805          # FINGER_TIP_BELOW_JAW, P39's measured identity
DS_JUMP = 0.03             # m/s in one tick
DW_JUMP = 2.0              # rad/s in one tick (A1: the rolling jitter is < 2)
DS_DEPART = 0.05           # m/s in one tick = tick-scale (METHOD P1)
DSEP_TOUCH = 2.0           # mm of jaw-span change in a cluster = a pad contact
MERGE = 3                  # ticks
CELLS = [
    # cell, seed, trace dir, record, note
    ("F6", 6, "tr6", "logs/p94/T6.log", "fruit reads only"),
    ("A6", 6, "tr6", "logs/p94/T6.log", "fruit + both arms' link reads"),
    ("A5", 5, "tr5", "logs/p94/T5.log", "fruit + both arms' link reads"),
]


# --------------------------------------------------------------------------- #
# io
# --------------------------------------------------------------------------- #
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
            "first_a": la[n][:140] if n < len(la) else "",
            "first_b": lb[n][:140] if n < len(lb) else ""}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def traces(cell):
    out = []
    trace_dir = next(c[2] for c in CELLS if c[0] == cell)
    for path in sorted(glob.glob(os.path.join(HERE, trace_dir, "ftrace_*.json"))):
        d = load(path)
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


def pair_legs(cell):
    """`[(trace, leg_start_tick)]`, paired by the sim time of each leg's end.

    The `[motion] approach` row prints the tick its leg ends, and the arbiter
    serialises the two arms, so the log's print order is the sim order: sort the
    traces by the `t` of their first `descent` row and pair. Validated on seed 6
    attempt 0, whose leg start reproduces P93's own `descent` row exactly.
    """
    steps = approach_steps(cell)
    entries = []
    for d in traces(cell):
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


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #
def pads(arm):
    jaw, sep, fruit = arm.get("jaw"), arm.get("sep"), arm.get("_fruit")
    if jaw is None or sep is None or fruit is None:
        return None
    half = 0.5 * float(sep) * 1e-3
    dx = abs(float(jaw[0]) - float(fruit[0])) - half
    dy = float(jaw[1]) - float(fruit[1])
    dz = float(jaw[2]) - PAD_DROP - float(fruit[2])
    radius = 0.031
    return ((dx * dx + dy * dy + dz * dz) ** 0.5 - radius) * 1e3, dx * 1e3, dy * 1e3


def clusters(rows):
    hits = []
    for i, row in enumerate(rows):
        prev = rows[i - 1] if i else None
        ds = abs(row["s"] - prev["s"]) if prev else 0.0
        dw = abs(row["spin"] - prev["spin"]) if prev else 0.0
        if ds >= DS_JUMP or dw >= DW_JUMP:
            hits.append(i)
    out = []
    for i in hits:
        if out and i - out[-1][-1] <= MERGE:
            out[-1].append(i)
        else:
            out.append([i])
    return out


def sep_swing(rows, key, i0, i1):
    vals = []
    for i in range(max(0, i0 - 1), min(len(rows), i1 + 2)):
        arm = rows[i].get("arm", {}).get(key) or {}
        if "sep" in arm:
            vals.append(float(arm["sep"]))
    return None if len(vals) < 2 else max(vals) - min(vals)


def nb_swing(rows, i, span=2):
    best = 0.0
    for j in range(max(1, i - span + 1), min(len(rows), i + span + 1)):
        cur = {n["i"]: n["s"] for n in rows[j]["nb"]}
        prev = {n["i"]: n["s"] for n in rows[j - 1]["nb"]}
        for idx, s in cur.items():
            if idx in prev:
                best = max(best, abs(s - prev[idx]))
    return best


def attribute(rows, cl, arm_name):
    i0, i1 = cl[0], cl[-1]
    row = rows[i0]
    other = "left" if arm_name == "right" else "right"
    swings = {k: sep_swing(rows, k, i0, i1) for k in ("left", "right")}
    gaps = {}
    for j in range(i0, i1 + 1):
        for key in ("left", "right"):
            arm = rows[j].get("arm", {}).get(key)
            if arm is None:
                continue
            p = pads(arm)
            if p is None:
                continue
            if key not in gaps or abs(p[0]) < abs(gaps[key][0]):
                gaps[key] = p
    for key in (other, arm_name):
        if swings.get(key) is not None and swings[key] >= DSEP_TOUCH:
            gap, dx, dy = gaps.get(key, (float("nan"),) * 3)
            cls = "arm-other" if key == other else "arm-self"
            return cls, (f"{key} hand: sep {swings[key]:.1f} mm, pad gap {gap:+.0f} mm, "
                         f"dx {dx:+.0f}, dy {dy:+.0f}")
    if row["p"][2] > 1.205 and row["p"][1] > 0.30:
        return "release", "airborne at the cluster (spawn drop)"
    nbs = nb_swing(rows, i0)
    if nbs >= 0.02:
        return "fruit-fruit", f"neighbour dv {nbs:.3f} m/s"
    if abs(row["s"] - abs(row["belt"])) < 0.02:
        return "belt/roll", "speed at belt, spin only"
    return "unattributed", "no pad swing, no neighbour, speed not at belt"


# --------------------------------------------------------------------------- #
# sections
# --------------------------------------------------------------------------- #
def section_admissible(print_):
    print_("=" * 104)
    print_("1. ADMISSIBILITY - every cell runs on the recorded branch")
    print_("=" * 104)
    ok = True
    for cell, seed, _, record, note in CELLS:
        r = compare(os.path.join(ROOT, record), os.path.join(HERE, f"{cell}.log"))
        print_(f"  {cell} (seed {seed:>3}, {note:<32s}): "
               f"{r['common']}/{r['lines_a']} [fruit] lines vs {record}, "
               f"{'IDENTICAL' if r['identical'] else 'DIFFERS'}")
        if not r["identical"]:
            ok = False
            print_(f"      A: {r['first_a']}")
            print_(f"      B: {r['first_b']}")
    print_()
    print_("  Every cell replays its record end to end with only the `[ftrace]` rows dropped.")
    print_("  The fruit-only trace is the branch-neutral class AGENTS 2 predicts (fruit")
    print_("  reads, WORKLOG 'it is the arm-link readback, not reads in general'); the")
    print_("  two-arm link read is *measured here as branch-neutral too* (see RESULTS 0).")
    print_()
    return ok


def section_witness(print_):
    print_("=" * 104)
    print_("2. THE P93 WITNESS, REPRODUCED - seed 6 attempt 0, the right arm's kiwi")
    print_("=" * 104)
    legs = pair_legs("A6")
    d, i_leg, first, steps = legs[0]
    rows = d["rows"]
    p93 = load(os.path.join(ROOT, "logs/p93/p1/D6C/trace/trace_01_right_scripted_fail.json"))
    p93_des = next(r for r in p93["rows"] if r["phase"] == "descent")
    p93_s = sum(v * v for v in p93_des["fruit_vel"]) ** 0.5
    p93_w = sum(v * v for v in p93_des["fruit_omega"]) ** 0.5
    row = rows[i_leg]
    print_(f"  P93 recorded, at the descent leg's start:  |v| {p93_s:.3f} m/s, |w| {p93_w:.2f} rad/s")
    print_(f"  this trace, tick {i_leg} t={row['t']:.3f}s (leg start): |v| {row['s']:.3f} m/s, "
           f"|w| {row['spin']:.2f} rad/s")
    print_(f"  and the same row's fruit position {[round(v, 5) for v in row['p']]} matches P93's")
    print_(f"  {[round(v, 5) for v in p93_des['fruit']]} - so this IS the recorded event, on the")
    print_(f"  unmodified branch (section 1).  belt {abs(row['belt']):.3f} m/s -> "
           f"{row['s'] / abs(row['belt']):.2f}x belt at the leg's start.")
    print_()
    print_(f"  The leg spans ticks {i_leg}..{first - 1} ({steps} ticks, the log's own `steps=`).")
    print_("  `_cycle_mark('descent')` fires *after* `_approach`, so rows labelled `descent`")
    print_("  are the leg's END - the wait window that P93 could not see is the `hover` run")
    print_("  from the hover move to the leg's start, and it is all in this trace.")
    print_()
    print_("  the departure, tick by tick (s = |v|; the two hands' geometry on every row)")
    print_(f"  {'tick':>5} {'t':>7} {'phase':>8} {'y':>7} {'z':>6} {'s':>6} {'/belt':>6} "
           f"{'spin':>6} {'dv':>6} | {'Lsep':>6} {'Lpad':>6} {'Ldy':>6} | {'Rsep':>6} {'Rpad':>6} {'Rdy':>6}")
    prev = None
    for i, r in enumerate(rows):
        ds = 0.0 if prev is None else r["s"] - prev["s"]
        hot = prev is not None and (abs(ds) >= DS_JUMP or abs(r["spin"] - prev["spin"]) >= DW_JUMP)
        if (hot and i < first) or i in (0, i_leg):
            arm = r["arm"]
            lp, rp = pads(arm.get("left") or {}), pads(arm.get("right") or {})
            def cell_(p, k):
                return "-" if p is None else f"{p[k]:>+6.0f}"
            print_(f"  {i:>5} {r['t']:>7.2f} {r['phase']:>8} {r['p'][1]:>+7.3f} {r['p'][2]:>6.3f} "
                   f"{r['s']:>6.3f} {r['s'] / abs(r['belt']):>6.2f} {r['spin']:>6.1f} {ds:>+6.3f} | "
                   f"{arm['left']['sep']:>6.1f} {cell_(lp, 0)} {cell_(lp, 2)} | "
                   f"{arm['right']['sep']:>6.1f} {cell_(rp, 0)} {cell_(rp, 2)}")
        prev = r
    print_()
    print_("  `Lpad`/`Rpad` = pad-point clearance to the fruit's surface [mm], `Ldy`/`Rdy` the")
    print_("  same pad's along-belt offset [mm].  A positive `sep` swing of >= 2 mm with the")
    print_("  pad within a few mm of the surface is a contact: the pad body is a plate a few")
    print_("  mm thick around that point, and the finger drive is stiffness-limited to 0.1 mm")
    print_("  at its 10 N cap, so a 5-30 mm span displacement cannot be commanded.")
    print_()


def section_census(print_):
    print_("=" * 104)
    print_("3. THE CENSUS - departures before the descent leg, both seeds")
    print_("=" * 104)
    rows_out, counts = [], {}
    for cell, seed, _, _, _ in CELLS:
        if cell == "A6":
            continue    # same branch as F6; the geometry comes from A6/A5 below
        for d, i_leg, first, steps in pair_legs(cell):
            for cl in clusters(d["rows"]):
                if i_leg is None or cl[0] >= i_leg:
                    continue
                peak = max((abs(d["rows"][i]["s"] - d["rows"][i - 1]["s"])
                            for i in range(cl[0], cl[-1] + 1) if i), default=0.0)
                if peak < DS_DEPART:
                    continue
                cls, why = attribute(d["rows"], cl, d["arm"])
                counts[cls] = counts.get(cls, 0) + 1
                rows_out.append((cell, seed, d["attempt"], d["arm"], d["category"], cl[0],
                                 d["rows"][cl[0]]["t"], d["rows"][cl[0]]["phase"],
                                 d["rows"][cl[0]]["p"][1], d["rows"][cl[0]]["s"], peak,
                                 d["rows"][cl[-1]]["spin"], cls, why))
    print_(f"  {len(rows_out)} departures before the leg over 20 + 20 attempts")
    print_(f"  {'cell':<4} {'seed':>4} {'att':>3} {'arm':<5} {'fruit':<11} {'tick':>5} {'t':>7} "
           f"{'phase':>8} {'y':>7} {'s':>6} {'dv':>6} {'spin':>6} {'class':<12} evidence")
    for r in rows_out:
        print_(f"  {r[0]:<4} {r[1]:>4} {r[2]:>3} {r[3]:<5} {r[4]:<11} {r[5]:>5} {r[6]:>7.2f} "
               f"{r[7]:>8} {r[8]:>+7.3f} {r[9]:>6.3f} {r[10]:>+6.3f} {r[11]:>6.1f} "
               f"{r[12]:<12} {r[13]}")
    print_()
    print_("  classes: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"))
    print_()


def section_descent(print_):
    print_("=" * 104)
    print_("4. THE P93 QUANTITY AT EVERY LEG START - |v| / belt, both seeds")
    print_("=" * 104)
    for cell, seed, _, _, _ in CELLS:
        if cell != "F6" and cell != "A5":
            continue
        legs = pair_legs(cell)
        vals = []
        print_(f"  {cell} (seed {seed}): {'att':>3} {'arm':<5} {'fruit':<11} {'t':>7} "
               f"{'|v|':>6} {'/belt':>6} {'spin':>6}")
        for d, i_leg, first, steps in legs:
            r = d["rows"][i_leg]
            vals.append(r["s"] / abs(r["belt"]))
            print_(f"       {d['attempt']:>14} {d['arm']:<5} {d['category']:<11} {r['t']:>7.2f} "
                   f"{r['s']:>6.3f} {r['s'] / abs(r['belt']):>6.2f} {r['spin']:>6.1f}")
        over = [v for v in vals if v > 1.15]
        print_(f"       -> {len(vals) - len(over)}/{len(vals)} legs start at the belt "
               f"(<= 1.15x); the overspeeding ones: "
               f"{', '.join(f'{v:.2f}x' for v in over) or 'none'}")
        print_()


def section_exposure(print_):
    print_("=" * 104)
    print_("5. THE EXPOSURE and the CONTACT TEST - the OTHER hand, before the leg")
    print_("=" * 104)
    print_("  For every attempt: the closest the hand that is *not* taking this fruit comes")
    print_("  to it (pad point to the fruit's surface) between the attempt's start and the")
    print_("  leg's start, and that hand's measured jaw-span swing within +-4 ticks of that")
    print_("  closest tick - the local contact signature, so the other arm's own close")
    print_("  (which happens elsewhere in the window) cannot be mistaken for one.")
    print_()
    print_(f"  {'cell':<4} {'seed':>4} {'att':>3} {'arm':<5} {'fruit':<11} {'other':<5} "
           f"{'min gap':>8} {'at t':>7} {'dy':>6} {'dsep':>6} {'contact':>8}")
    near = contacts = total = 0
    for cell, seed, _, _, _ in CELLS:
        if cell == "F6":
            continue
        for d, i_leg, first, steps in pair_legs(cell):
            rows = d["rows"]
            other = "left" if d["arm"] == "right" else "right"
            best = None
            for i in range(0, i_leg):
                arm = rows[i].get("arm", {}).get(other)
                if arm is None:
                    continue
                p = pads(arm)
                if p is None:
                    continue
                if best is None or abs(p[0]) < abs(best[0]):
                    best = (p[0], rows[i]["t"], p[2], i)
            if best is None:
                continue
            total += 1
            swing = sep_swing(rows, other, best[3] - 4, best[3] + 4) or 0.0
            hit = abs(best[0]) <= 6.0 and swing >= DSEP_TOUCH
            near += abs(best[0]) <= 6.0
            contacts += 1 if hit else 0
            print_(f"  {cell:<4} {seed:>4} {d['attempt']:>3} {d['arm']:<5} {d['category']:<11} "
                   f"{other:<5} {best[0]:>+8.1f} {best[1]:>7.2f} {best[2]:>+6.0f} {swing:>6.1f} "
                   f"{'CONTACT' if hit else '-':>8}")
    print_()
    print_(f"  {near}/{total} attempts come within 6 mm of the other hand's pad point before")
    print_(f"  the leg; {contacts}/{total} also displace that hand's span by >= 2 mm there, i.e.")
    print_("  are contacts. The pad's own body is a few mm thick around the point, so")
    print_("  `<= 6 mm` is the contact band and the rest is the near-miss tail.")
    print_()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--same", nargs=2, metavar=("A", "B"))
    args = ap.parse_args()
    if args.same:
        print(json.dumps(compare(args.same[0], args.same[1]), indent=1))
        return 0
    out = []

    def print_(line=""):
        out.append(line)

    ok = section_admissible(print_)
    section_witness(print_)
    section_census(print_)
    section_descent(print_)
    section_exposure(print_)
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "probe.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
