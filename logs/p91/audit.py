#!/usr/bin/env python3
"""P91 STEP 1 - the offline audit of the five never-profiled `[cycle]` blocks.

    python3 logs/p91/audit.py                     # the table over the three logs
    python3 logs/p91/audit.py --predict           # the profile arithmetic per block
    python3 logs/p91/audit.py --grip LOG...       # the grip block by outcome class

There is **no simulator** here and nothing is re-derived from a model that the
log can check: every block value is the `[cycle]` row's own number, and the
sub-terms are the *printed* counts of the loops the block contains
(`dynamic descent: waited N ticks`, `fruit at pick point: arrived=True after N
steps`, `[motion] approach(cartesian): ... N samples`, `dynamic close: sustained
contact after N ticks`, `[motion] carry ... N ticks`). The model's residual is
reported on its own line so a reader can see how much of the block the named
loops do *not* explain.

Block definitions (the marks are `tasks._cycle_mark`; the segment's name is the
mark that **ends** it, `_cycle_report`):

  prepose  `_cycle_begin()`            -> `_cycle_mark("prepose")`
  hover    `_cycle_mark("prepose")`    -> `_cycle_mark("hover")`
  descent  `_cycle_mark("hover")`      -> `_cycle_mark("descent")`
  close    `_cycle_mark("descent")`    -> `_cycle_mark("close")`
  grip     `_cycle_mark("close")`      -> `_cycle_mark("grip")`
  lift / place / release / return      the `_carry("grasp_lift")` / `_carry("placeN")`
                                       legs, the release block and the retreat

Read-only: nothing here writes outside stdout.
"""

from __future__ import annotations

import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

DT = 1.0 / 120.0            # CONTROL_DT, `fruit_sorting.common`
BLOCKS = ["prepose", "hover", "descent", "close", "grip", "lift", "place",
          "release", "return", "end", "total"]

CY = re.compile(r"\[cycle\] attempt (\d+): (.+)")
RES = re.compile(r"\[biarm\] result (?P<arm>\w+) index=\d+ .*?"
                 r"grasped=(?P<g>\w+) placed=(?P<p>\w+)")
PICKPOSE = re.compile(r"\[task\] at pick pose after (?P<t>[\d.]+) s")
ARRIVED = re.compile(r"arrived=True after (?P<n>\d+) steps")
WAITED = re.compile(r"dynamic descent: waited (?P<n>\d+) ticks")
APPROACH = re.compile(r"\[motion\] approach\(cartesian\): (?P<d>[\d.]+) cm, "
                      r"(?P<n>\d+) samples:.*end=(?P<end>[\d.]+) mm")
APPROACH_ANY = re.compile(r"\[motion\] approach\(cartesian\): (?P<d>[\d.]+) cm, "
                          r"(?P<n>\d+) samples")
CATCHUP = re.compile(r"dynamic catch-up: residual=(?P<r>[\d.]+) mm")
CLOSE = re.compile(r"dynamic close: sustained contact after (?P<n>\d+) ticks")
LIFT = re.compile(r"\[motion\] carry grasp_lift: (?P<d>[\d.]+) cm, (?P<n>\d+) ticks")
REGRASP = re.compile(r"dynamic regrasp: re-seated in place")


def parse(path: str) -> dict:
    rows: list[dict] = []
    pend = None
    ev = {k: [] for k in ("pick_pose", "arrived", "waited", "approach",
                          "approach_any", "catchup", "close", "lift", "regrasp")}
    for line in open(path, encoding="utf-8", errors="ignore"):
        if m := CY.search(line):
            seg = {}
            for part in m.group(2).split():
                name, _, value = part.partition("=")
                seg[name] = float(value.rstrip("s"))
            pend = seg
            rows.append(seg)
            continue
        if (m := RES.search(line)) and pend is not None:
            pend["arm"] = m.group("arm")
            pend["grasped"] = m.group("g") == "True"
            pend["placed"] = m.group("p") == "True"
            pend = None
            continue
        if m := PICKPOSE.search(line):
            ev["pick_pose"].append(float(m.group("t")))
        elif m := ARRIVED.search(line):
            ev["arrived"].append(int(m.group("n")))
        elif m := WAITED.search(line):
            ev["waited"].append(int(m.group("n")))
        elif m := APPROACH.search(line):
            ev["approach"].append((float(m.group("d")), int(m.group("n")),
                                   float(m.group("end"))))
        elif m := APPROACH_ANY.search(line):
            ev["approach_any"].append((float(m.group("d")), int(m.group("n"))))
        elif m := CATCHUP.search(line):
            ev["catchup"].append(float(m.group("r")))
        elif m := CLOSE.search(line):
            ev["close"].append(int(m.group("n")))
        elif m := LIFT.search(line):
            ev["lift"].append((float(m.group("d")), int(m.group("n"))))
        elif REGRASP.search(line):
            ev["regrasp"].append(1)
    return {"rows": rows, "ev": ev}


def mean(values):
    return st.mean(values) if values else float("nan")


def block_table(path: str) -> dict:
    data = parse(path)
    rows, ev = data["rows"], data["ev"]
    print(f"\n== {path} ==")
    print(f"  [cycle] rows {len(rows)}  paired {sum(1 for r in rows if 'arm' in r)}")
    placed = [r for r in rows if r.get("placed")]
    failed = [r for r in rows if r.get("arm") and not r.get("grasped")]
    print(f"  placed {len(placed)}  never-grasped {len(failed)}")
    print("  block          n     mean   median    min    max")
    for name in BLOCKS:
        vals = [r[name] for r in rows if name in r]
        if not vals:
            continue
        print(f"  {name:10s} {len(vals):5d} {mean(vals):7.2f} {st.median(vals):7.2f} "
              f"{min(vals):6.2f} {max(vals):6.2f}")
    # ---- the five, decomposed -------------------------------------------
    n = len(rows)
    arrive = sum(ev["arrived"]) * DT
    waited = sum(ev["waited"]) * DT
    appr = sum(v[1] for v in ev["approach"]) * DT
    appr_any = sum(v[1] for v in ev["approach_any"]) * DT
    descent = sum(r.get("descent", 0.0) for r in rows)
    close_block = sum(r.get("close", 0.0) for r in rows)
    close_loop = sum(ev["close"]) * DT
    grip = sum(r.get("grip", 0.0) for r in rows)
    hover = sum(r.get("hover", 0.0) for r in rows)
    prepose = sum(r.get("prepose", 0.0) for r in rows)
    print(f"\n  ---- the five blocks, summed over {n} attempts ({n} x block mean) ----")
    print(f"  prepose      {prepose:7.2f} s  printed `at pick pose after` "
          f"{sum(ev['pick_pose']) / n:5.2f} s/attempt "
          f"(= the block: {abs(sum(ev['pick_pose']) - prepose) < 0.01})")
    print(f"  hover        {hover:7.2f} s  = move_to(~69 ticks) + "
          f"FRUIT_DYNAMIC_HOVER_SETTLE 20 ticks (0.17 s), no profile knob")
    print(f"  descent      {descent:7.2f} s  of which")
    print(f"      arrival wait   {arrive:7.2f} s  ({sum(ev['arrived']) / n:5.1f} ticks/att, "
          f"{len(ev['arrived'])} rows)   <- the fruit-arrival wait")
    print(f"      dynamic wait   {waited:7.2f} s  ({sum(ev['waited']) / n:5.1f} ticks/att, "
          f"{len(ev['waited'])} rows)   <- the scheduled wait, this is NOT motion")
    print(f"      approach       {appr:7.2f} s  ({sum(v[1] for v in ev['approach']) / n:5.1f} "
          f"ticks/att, {len(ev['approach'])} rows)   <- the profiled descent (motion)")
    print(f"      residual       {descent - arrive - waited - appr:7.2f} s  (unmodelled)")
    print(f"  close        {close_block:7.2f} s  of which printed close ramp "
          f"{close_loop:6.2f} s ({len(ev['close'])} rows), "
          f"fixed hold {48 * DT * n:5.2f} s,")
    print(f"      catch-up       {close_block - close_loop - 48 * DT * n:7.2f} s "
          f"(the chase; residual median {st.median(ev['catchup']):.1f} mm, "
          f"{len(ev['catchup'])} rows)")
    print(f"  grip         {grip:7.2f} s  of which probe {60 * DT * n:5.2f} s "
          f"(60 ticks), belt-break {54 * DT * n:5.2f} s (54 ticks), "
          f"regrasps {len(ev['regrasp'])}")
    print(f"      residual       {grip - 60 * DT * n - 54 * DT * n:7.2f} s (unmodelled)")
    # ---- the grip's failure tax ----------------------------------------
    for label, group in (("placed", placed), ("never-grasped", failed)):
        if not group:
            continue
        print(f"    grip[{label}] n={len(group):2d} mean {mean([r['grip'] for r in group]):5.2f} s "
              f"descent {mean([r['descent'] for r in group]):5.2f} "
              f"close {mean([r['close'] for r in group]):5.2f}")
    clean = [r["grip"] for r in rows if r.get("grasped") and 1.6 <= r["grip"] <= 1.85]
    print(f"    grip clean single-probe legs n={len(clean)} "
          f"mean {mean(clean):.2f} s = {mean(clean) / DT:.0f} ticks")
    if placed and failed:
        print(f"    tax: a failed probe +{(mean([r['grip'] for r in failed]) - mean(clean)) / 2:.2f} s "
              f"(the never-grasped class burns the cap, 2 probes)")
    print(f"  end gaps: median {st.median([v[2] for v in ev['approach']]):.1f} mm "
          f"({min(v[2] for v in ev['approach']):.1f}-{max(v[2] for v in ev['approach']):.1f})")
    return {"rows": rows, "ev": ev}


def predict() -> int:
    """The profile arithmetic a block could buy, per candidate."""
    from fruit_sorting.motion import TrajectoryLimits, jerk_limited

    def ticks(distance, v, a, j=25.0):
        limits = TrajectoryLimits(v_max=v, a_max=a, j_max=j, dt=DT)
        return len(jerk_limited(float(distance), limits)[0])

    print("P91 - the profile ceilings, from the log's own printed distances")
    print("=" * 78)
    print("\ndescent (approach leg, 5.5 cm at the shipped 0.15 / 0.8):")
    base = ticks(0.055, 0.15, 0.8)
    for v, a in ((0.15, 0.8), (0.15, 1.6), (0.25, 0.8), (0.25, 1.6), (0.30, 1.9)):
        print(f"   v={v:.2f} a={a:.2f} -> {ticks(0.055, v, a):3d} ticks "
              f"({ticks(0.055, v, a) - base:+d} vs shipped)")
    print("   NB the block is *scheduled*: the wait exits at speed*(t_desc+margin),")
    print("      so block = lead/speed - margin + residual -> invariant in t_desc.")
    print("\nplace (0.55-0.62 m, measured P88): 0.35 -> 382, 0.52 -> 257, 0.61 -> 220 ticks")
    print("lift  (0.21 m, measured P89):      0.30 -> 162, 0.37 -> 136 ticks")
    print("\ngrip, clean (208 ticks measured):")
    print("   probe ramp   60 ticks (6 mm, min_jerk_ramp)  <- the only profile here")
    print("   belt-break   54 ticks (match 0.20 + trans 0.25, the P3 anti-shear fix)")
    print("   probe 60 -> 36: -24 ticks = -0.20 s   probe 60 -> 24: -36 ticks = -0.30 s")
    print("\nclose (145 ticks clean):")
    print("   catch-up ~75 (servo convergence), ramp 22 (printed), hold 48 (fixed)")
    print("   hold 48 -> 24: -24 ticks = -0.20 s")
    print("\nhover (89 ticks): move_to ~69 + 20-tick settle -> settle 20 -> 0: -0.17 s")
    print("prepose (85 ticks): 45-tick blend + 20-tick pump + ~20 -> pump 20 -> 0: -0.17 s")
    return 0


def grip_by_class(paths) -> int:
    print("P91 - the grip block by outcome class (the failure tax)")
    print("=" * 78)
    for path in paths:
        data = parse(path)
        rows = data["rows"]
        clean = [r["grip"] for r in rows if r.get("grasped") and r["grip"] <= 1.9]
        one = [r["grip"] for r in rows if r.get("grasped") and r["grip"] > 1.9]
        bad = [r["grip"] for r in rows if not r.get("grasped")]
        print(f"  {path}")
        print(f"    clean (1 probe)     n={len(clean):2d}  mean {mean(clean):5.2f} s "
              f"= {mean(clean) / DT:3.0f} ticks")
        print(f"    1 failed probe      n={len(one):2d}  mean {mean(one):5.2f} s "
              f"= {mean(one) / DT:3.0f} ticks  (+{mean(one) - mean(clean):.2f} s)")
        print(f"    2 probes (cap)      n={len(bad):2d}  mean {mean(bad):5.2f} s "
              f"= {mean(bad) / DT:3.0f} ticks  (+{mean(bad) - mean(clean):.2f} s)")
        print(f"    regrasp rows {len(data['ev']['regrasp'])}")
    return 0


def schedule(paths) -> int:
    """The descent's own variance against the leg's: can `t_desc` be the block's variable?"""
    pat = re.compile(r"dynamic descent: waited (?P<w>\d+) ticks, .*?deadline="
                     r"(?P<d>[\d.]+) m, t_desc=(?P<t>[\d.]+) s")
    print("P91 - the descent block's variance against its leg's (the schedule, measured)")
    print("=" * 78)
    for path in paths:
        rows = [(int(m.group("w")), float(m.group("d")), float(m.group("t")))
                for m in pat.finditer(open(path, errors="ignore").read())]
        if not rows:
            continue
        block = [w + t * 120.0 for w, _d, t in rows]
        waited = [w for w, _d, _t in rows]
        legs = [t * 120.0 for _w, _d, t in rows]
        print(f"  {path}  n={len(rows)}")
        print(f"    waited      {min(waited):5.0f}-{max(waited):5.0f} ticks "
              f"(spread {(max(waited) - min(waited)) * DT:.2f} s)")
        print(f"    leg (t_desc) {min(legs):5.1f}-{max(legs):5.1f} ticks "
              f"(spread {(max(legs) - min(legs)) * DT:.2f} s)")
        print(f"    waited+leg  {min(block):5.1f}-{max(block):5.1f} ticks "
              f"(spread {(max(block) - min(block)) * DT:.2f} s, sd "
              f"{st.stdev(block):.1f}) -> the LEAD's variance, not the leg's:")
        print(f"      the leg's whole range is {(max(legs) - min(legs)) / max(st.stdev(block), 1e-9):.1f}x "
              f"the block's sd, so within this cell the leg's duration is not an "
              f"available variable - the block's spread is the per-fruit handover lead.")
    return 0


def main(argv) -> int:
    if "--predict" in argv:
        return predict()
    if "--schedule" in argv:
        return schedule([a for a in argv[1:] if a.endswith(".log")]
                        or ["logs/p87/T5.log", "logs/p86/C5.log"])
    logs = [a for a in argv[1:] if a.endswith(".log")]
    if "--grip" in argv:
        return grip_by_class(logs or ["logs/p87/T5.log", "logs/p86/C5.log"])
    logs = logs or ["logs/p87/T5.log", "logs/p86/C5.log", "logs/p89/C5.log"]
    print("P91 - the five never-profiled blocks, from the existing records")
    print("=" * 78)
    for path in logs:
        block_table(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
