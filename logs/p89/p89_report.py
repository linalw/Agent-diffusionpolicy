#!/usr/bin/env python3
"""P89 readout: the two-line-scoped lift raise - the gate's six clauses.

    python3 logs/p89/p89_report.py --predict logs/p88/T5.log logs/p88/T6.log
    python3 logs/p89/p89_report.py --blocks           # the registered table + verdict
    python3 logs/p89/p89_report.py --cells LOG...     # one cell's endpoints
    python3 logs/p89/p89_report.py --same REF CAND    # `[fruit]` stream, sealed filter
    python3 logs/p89/p89_report.py --same-raw REF CAND
    python3 logs/p89/p89_report.py --profile LOG...   # the three profile rows
    python3 logs/p89/p89_report.py --landing LOG...
    python3 logs/p89/p89_report.py --classes LOG...

P88's parser is reused verbatim (`logs/p88/p88_report.py` -> `logs/p80/p80lib.py` ->
`scripts/186_w6_report.py`): a placement is the attempt's `t1`, the placement window
is `t_last_place - t_first_place`, the batch span is `t_last_end - t_first_start`,
and the wall comes from the `.stamps` stream. Nothing here re-derives a rate.

What is **new** in this phase is the `lift` block, and it is read the way P88 read
the place:

* the `[cycle] lift=` block is the `grasp_lift` `_carry_leg` call, so it pairs one
  to one with that leg's `[motion] carry grasp_lift: NN cm, T ticks` row. The two
  arms interleave, so the pairing is **per arm, in order** (the arm comes from the
  `[fruit] [carry] <arm> grasp_lift` row that prints immediately before the leg's
  `[motion]` row) - a global zip is wrong by construction (P89's first pass, kept
  in the WORKLOG).
* P1a is the block **mean** (a median across 0.05-0.50 m legs is mix-sensitive;
  P88's lesson), against a prediction built from **each control attempt's own**
  printed distance re-generated at 0.37/1.0 with that attempt's own remainder.
* P1b is the **per-leg** read: ticks against the re-generated profile, `|v|cmd`
  against that profile's own peak, and the remainder band.

Read-only: nothing here writes outside stdout.
"""

from __future__ import annotations

import importlib.util
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p88 = _load("p88_report", os.path.join(ROOT, "logs/p88/p88_report.py"))
from fruit_sorting.motion import TrajectoryLimits, jerk_limited  # noqa: E402

fmt = p88.fmt
_mean, _p50, _block = p88._mean, p88._p50, p88._block
motion105 = p88.motion105

#: P87's sealed filter + P88's rows + **this phase's own row** (`[biarm] lift
#: profile:`). The lift row is the one line the flip is *expected* to move (a
#: treatment cell reads `=0.37(default)` where its control reads
#: `=0.30(explicit)`), so it is dropped from the physics comparison and read on
#: its own (`--profile`). P88's logs have no lift row at all, which is why the
#: G0 replay works against them with the same filter.
DROP = p88.DROP + ("[fruit] [biarm] lift profile:",)
p88.DROP = DROP  # the shared parsers read the module global

LIFT_PROFILE = re.compile(
    r"\[fruit\] \[biarm\] lift profile: (?P<label>\S+) scope=(?P<scope>\S+) "
    r"v_max=(?P<vmax>[\d.]+) a_max=(?P<amax>[\d.]+) "
    r"\((?P<ticks>-?\d+) ticks at (?P<distance>[\d.]+) m; "
    r"shipped (?P<shipped>-?\d+), saved (?P<saved>-?\d+)\)")
#: `[fruit] [motion] carry grasp_lift: 20 cm, 133 ticks, |v|cmd=0.339 |a|cmd=...`
LIFT_LEG = re.compile(
    r"\[motion\] carry grasp_lift: (?P<cm>\d+) cm, (?P<ticks>\d+) ticks, "
    r"\|v\|cmd=(?P<v>[\d.]+)")
CARRY_ARM = re.compile(r"\[fruit\] \[carry\] (?P<arm>left|right) (?P<leg>\w+):")

#: The scoped cell's pair (P44's S3-v, `tasks._LIFT_SCOPED_VMAX` + the shipped
#: `_SPEED_SHIPPED["lift_amax"]`) and the shipped pair it replaces.
SCOPED = (0.37, 1.0)
SHIPPED = (0.30, 1.0)


def profile_ticks(distance: float, v_max: float, a_max: float) -> int:
    """A carry leg's clock at one distance, from the leg's own profile chain."""
    limits = TrajectoryLimits(
        v_max=float(v_max), a_max=float(a_max),
        j_max=min(25.0, max(float(a_max) * 10.0, 1.0)), dt=1.0 / 120.0,
    )
    positions, _v, _a = jerk_limited(float(distance), limits)
    return int(len(positions))


def lift_legs(path: str) -> list[dict]:
    """Every `grasp_lift` leg with its own printed distance, ticks and peak."""
    legs: list[dict] = []
    arm = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if m := CARRY_ARM.search(line):
                arm = m.group("arm") if m.group("leg") == "grasp_lift" else arm
                continue
            if m := LIFT_LEG.search(line):
                legs.append({"arm": arm, "cm": int(m.group("cm")),
                             "ticks": int(m.group("ticks")), "v": float(m.group("v"))})
    return legs


def lift_pairs(path: str) -> dict:
    """Each `[cycle] lift=` block paired with **its own** `grasp_lift` leg.

    Per arm, in order: the k-th lift block of an arm belongs to that arm's k-th
    `grasp_lift` leg. The arms interleave attempts, so a global zip pairs a
    block with the other arm's leg - the mistake this function exists to avoid.
    """
    data = p88.scan(path)
    legs = lift_legs(path)
    pairs: list[dict] = []
    unpaired = {"cycles": 0, "legs": 0}
    for arm in ("left", "right"):
        cycles = [c for c in data["cycles"] if "lift" in c["blocks"] and c["arm"] == arm]
        arm_legs = [leg for leg in legs if leg["arm"] == arm]
        for cycle, leg in zip(cycles, arm_legs):
            pairs.append({
                "arm": arm, "cm": leg["cm"], "ticks": leg["ticks"], "v": leg["v"],
                "block": cycle["blocks"]["lift"],
                "rest": cycle["blocks"]["lift"] - leg["ticks"] / 120.0,
            })
        unpaired["cycles"] += max(0, len(cycles) - len(arm_legs))
        unpaired["legs"] += max(0, len(arm_legs) - len(cycles))
    unknown = sum(1 for leg in legs if leg["arm"] is None)
    return {"pairs": pairs, "unpaired": unpaired, "unknown_arm": unknown,
            "cycles": data["cycles"], "scan": data}


def lift_prediction(path: str, v_max: float = SCOPED[0], a_max: float = SCOPED[1]) -> dict:
    """Per-attempt prediction of the treatment's `lift` block, from the control.

    For every attempt that carries a lift block and its own `grasp_lift` leg:
    `predicted = ticks(distance; v_max, a_max)/120 + (block - ticks/120)`, i.e.
    the leg re-generated at the treatment cap over **that attempt's own printed
    distance**, with the remainder (the `_carry` return/finish around the profile)
    left as the control ran it - the cell touches nothing else.
    """
    data = lift_pairs(path)
    rows = []
    for pair in data["pairs"]:
        distance = pair["cm"] / 100.0
        ticks_pred = profile_ticks(distance, v_max, a_max)
        rows.append({**pair, "distance": distance, "predicted_ticks": ticks_pred,
                     "predicted": ticks_pred / 120.0 + pair["rest"]})
    return {"rows": rows, "unpaired": data["unpaired"],
            "control_median": _p50([r["block"] for r in rows]),
            "predicted_median": _p50([r["predicted"] for r in rows]),
            "control_mean": _mean([r["block"] for r in rows]),
            "predicted_mean": _mean([r["predicted"] for r in rows]),
            "rest_lo": min((r["rest"] for r in rows), default=None),
            "rest_hi": max((r["rest"] for r in rows), default=None)}


def show_profile(path: str) -> int:
    """The three `[biarm] … profile:` rows, as the run printed them."""
    rows = {"release": None, "place": None, "lift": None}
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if rows["release"] is None and (m := p88.RELEASE_PROFILE.search(line)):
                rows["release"] = m.groupdict()
            if rows["place"] is None and (m := p88.PLACE_PROFILE.search(line)):
                rows["place"] = m.groupdict()
            if rows["lift"] is None and (m := LIFT_PROFILE.search(line)):
                rows["lift"] = m.groupdict()
    print(f"[profile] {path}")
    for name in ("release", "place", "lift"):
        row = rows[name]
        if row is None:
            print(f"  {name}: NO ROW (a non-bimanual log)")
            continue
        if name == "release":
            print(f"  release: {row['label']} scope={row['scope']} "
                  f"dwell={row['dwell']} pad_hold={row['pad']} "
                  f"finger_hold={row['finger']} ({row['ticks']} ticks; "
                  f"shipped {row['shipped']}, saved {row['saved']})")
        else:
            print(f"  {name}: {row['label']} scope={row['scope']} "
                  f"v_max={row['vmax']} a_max={row['amax']} ({row['ticks']} ticks "
                  f"at {row['distance']} m; shipped {row['shipped']}, "
                  f"saved {row['saved']})")
    return 0


def cell(path: str) -> dict:
    """One cell's endpoints: the lift block, the interval, landing, class, budgets."""
    m = p88.p80lib.metrics(path)
    stats = m.get("stats") or {}
    data = lift_pairs(path)
    cycles = data["cycles"]
    print(f"\n== {path} ==")
    for row in (data["scan"]["release_profiles"], data["scan"]["place_profiles"]):
        if row:
            print(f"  {row[0]['label']} ({row[0]['scope']})")
    lift_profile = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if (mm := LIFT_PROFILE.search(line)):
                lift_profile = mm.groupdict()
                break
    if lift_profile:
        print(f"  lift profile {lift_profile['label']} scope={lift_profile['scope']} -> "
              f"v_max={lift_profile['vmax']} a_max={lift_profile['amax']} "
              f"({lift_profile['ticks']} ticks at {lift_profile['distance']} m; "
              f"shipped {lift_profile['shipped']}, saved {lift_profile['saved']})")
    else:
        print("  lift profile: NO ROW (a non-bimanual log)")
    print(f"  [cycle] rows {len(cycles)}  lift pairs {len(data['pairs'])}  "
          f"unpaired {data['unpaired']}  legs w/o arm {data['unknown_arm']}")
    print(f"  placed {m['placed']}/{m['attempts']} = {100.0 * (m['rate'] or 0):.1f} %   "
          f"s/attempt {fmt(stats.get('per_attempt'))}   sim {fmt(stats.get('sim_total'))} s")
    if stats.get("biarm"):
        b = stats["biarm"]
        print(f"  per arm  left {b['l']}/{b['la']}   right {b['r']}/{b['ra']}   "
              f"pipelined slots {b['slots']}")
    lifts = _block(cycles, "lift")
    print(f"  lift block  mean {fmt(_mean(lifts), 3)} s   MEDIAN {fmt(_p50(lifts), 3)} s  "
          f"n={len(lifts)}")
    pairs = data["pairs"]
    if pairs:
        print(f"  lift legs   cm {min(p['cm'] for p in pairs)}-{max(p['cm'] for p in pairs)}  "
              f"ticks {min(p['ticks'] for p in pairs)}-{max(p['ticks'] for p in pairs)}  "
              f"|v|cmd {fmt(min(p['v'] for p in pairs), 3)}-{fmt(max(p['v'] for p in pairs), 3)}  "
              f"remainder {fmt(min(p['rest'] for p in pairs), 3)}-"
              f"{fmt(max(p['rest'] for p in pairs), 3)} s")
        err = [p["ticks"] - profile_ticks(p["cm"] / 100.0, SHIPPED[0], SHIPPED[1])
               for p in pairs]
        print(f"  ticks vs the profile at 0.30 from each leg's own cm: median "
              f"{fmt(_p50(err), 1)}, max |{max(abs(e) for e in err)}|")
    print(f"  pooled interval {fmt(m['pooled']['mean'])} s mean / {fmt(m['pooled']['p50'])} p50 / "
          f"{fmt(m['pooled']['p90'])} p90 (n={m['pooled']['n']})")
    for arm, data_arm in sorted(m["per_arm"].items()):
        print(f"    {arm}: placed {data_arm['placed']}/{data_arm['attempts']}  "
              f"interval {fmt(data_arm['interval_mean'])} / {fmt(data_arm['interval_p90'])} s  "
              f"idle {fmt((data_arm['idle_frac'] or 0) * 100, 1)} %")
    print(f"  window {fmt(m['window_rate'])} placed/min   batch {fmt(m['batch_rate'])} placed/min"
          f"   window span {fmt(m['window'])} s   batch span {fmt(m['batch_span'])} s")
    if stats.get("wall"):
        print(f"  wall {fmt(stats['wall'], 1)} s   wall/pick {fmt(stats['wall_per_pick'])} s   "
              f"wall/sim {fmt(stats['wall_over_sim'])}x   "
              f"placed/min wall {fmt(60.0 * m['placed'] / stats['wall'])}")
    else:
        print("  wall: NO STAMPS")
    traces = data["scan"]["traces"]
    if traces:
        guests = [t for t in traces if t["bottom"] >= 0.0]
        print(f"  landing: {len(traces)} traces, {len(guests)} payload-present, "
              f"on_belt {sum(1 for t in guests if t['on_belt'])}/{len(guests)}"
              f"   discharged {data['scan']['discharged']}")
    descents = p88.descent_legs(path)
    if descents:
        worst = max(descents, key=lambda d: d["v_max"])
        over = [d for d in descents if d["over"]]
        print(f"  descent legs {len(descents)}  over budget {len(over)}  "
              f"worst |v|max {fmt(worst['v_max'], 3)} (leg {worst['n']}, "
              f"{worst['distance_cm']:.1f} cm)")
    table = p88.classes(data["scan"])
    print("  classes (per arm:leg; escaped = clean_slip>100 mm with a pinch):")
    for key in sorted(table):
        row = table[key]
        print(f"    {key}: n={row['n']} escaped={row['escaped']} "
              f"never-held={row['never']} force_min==0={row['zero']} "
              f"slip>800={row['slip800']}")
    print(f"  reasons {m['reasons']}")
    return {"m": m, "data": data, "descents": descents, "classes": table}


def totals(res: dict) -> dict:
    """The class aggregate, per leg class, for P4."""
    agg = {"escaped": 0, "never": 0, "zero": 0, "left_escaped": 0,
           "lift_legs": 0, "lift_escaped": 0, "lift_zero": 0, "lift_never": 0,
           "left_lift_escaped": 0, "place_legs": 0, "place_escaped": 0}
    for key, row in res["classes"].items():
        arm, leg = key.split(":")
        agg["escaped"] += row["escaped"]
        agg["never"] += row["never"]
        agg["zero"] += row["zero"]
        if arm == "left":
            agg["left_escaped"] += row["escaped"]
        if leg == "grasp_lift":
            agg["lift_legs"] += row["n"]
            agg["lift_escaped"] += row["escaped"]
            agg["lift_zero"] += row["zero"]
            agg["lift_never"] += row["never"]
            if arm == "left":
                agg["left_lift_escaped"] += row["escaped"]
        if leg.startswith("place"):
            agg["place_legs"] += row["n"]
            agg["place_escaped"] += row["escaped"]
    return agg


def blocks() -> int:
    print("P89 - the lift raise as a two-line-scoped default (PREREG S5)")
    print("=" * 78)
    verdicts = {}
    pairs = (("5", "logs/p89/C5.log", "logs/p89/T5.log"),
             ("6", "logs/p89/C6.log", "logs/p89/T6.log"))
    for seed, control, treatment in pairs:
        c, r = cell(control), cell(treatment)
        cm, rm = c["m"], r["m"]
        pred = lift_prediction(control)
        c_lift = _block(c["data"]["cycles"], "lift")
        r_lift = _block(r["data"]["cycles"], "lift")
        c_mean, r_mean = _mean(c_lift), _mean(r_lift)
        d_mean = (r_mean or 0.0) - (c_mean or 0.0)
        d_pred = (pred["predicted_mean"] or 0.0) - (pred["control_mean"] or 0.0)
        d_interval = rm["pooled"]["mean"] - cm["pooled"]["mean"]
        print(f"\n## seed {seed}")
        print(f"  P1a lift block MEAN   C {fmt(c_mean, 3)} s -> T {fmt(r_mean, 3)} s   "
              f"delta {fmt(d_mean, 3)} s   predicted {fmt(d_pred, 3)} s "
              f"(control legs re-generated at 0.37/1.0)   band +-0.08 s")
        print(f"  report: MEDIAN  C {fmt(_p50(c_lift), 3)} -> T {fmt(_p50(r_lift), 3)} s   "
              f"delta {fmt((_p50(r_lift) or 0) - (_p50(c_lift) or 0), 3)} s   "
              f"predicted {fmt((pred['predicted_median'] or 0) - (pred['control_median'] or 0), 3)} s")
        # P1b: leg-by-leg materialisation.
        rlegs = r["data"]["pairs"]
        cles = c["data"]["pairs"]
        if rlegs:
            err = [p["ticks"] - profile_ticks(p["cm"] / 100.0, SCOPED[0], SCOPED[1])
                   for p in rlegs]
            peak_err = [p["v"] - 1.875 * (p["cm"] / 100.0) / ((p["ticks"] - 1) / 120.0)
                        for p in rlegs]
            rests = [p["rest"] for p in rlegs]
            c_err = [p["ticks"] - profile_ticks(p["cm"] / 100.0, SHIPPED[0], SHIPPED[1])
                     for p in cles]
            print(f"  P1b ticks vs the raised profile (each leg's own cm): median "
                  f"{fmt(_p50(err), 1)}, max |{max(abs(e) for e in err)}|   "
                  f"control vs the shipped profile: median {fmt(_p50(c_err), 1)}, "
                  f"max |{max(abs(e) for e in c_err)}|")
            print(f"       |v|cmd  C {fmt(min(p['v'] for p in cles), 3)}-"
                  f"{fmt(max(p['v'] for p in cles), 3)} (median "
                  f"{fmt(_p50([p['v'] for p in cles]), 3)}) -> T "
                  f"{fmt(min(p['v'] for p in rlegs), 3)}-"
                  f"{fmt(max(p['v'] for p in rlegs), 3)} (median "
                  f"{fmt(_p50([p['v'] for p in rlegs]), 3)})   peak err "
                  f"max |{fmt(max(abs(e) for e in peak_err), 3)}| m/s")
            print(f"       remainder  C {fmt(pred['rest_lo'], 3)}-"
                  f"{fmt(pred['rest_hi'], 3)} s -> T {fmt(min(rests), 3)}-"
                  f"{fmt(max(rests), 3)} s   (every treatment leg inside "
                  f"0.41-0.43 s: {all(0.41 <= x <= 0.43 for x in rests)})")
        print(f"  P2 pooled interval  C {fmt(cm['pooled']['mean'])} s -> "
              f"T {fmt(rm['pooled']['mean'])} s   delta {fmt(d_interval)} s")
        for arm in ("left", "right"):
            ca = cm["per_arm"].get(arm) or {}
            ra = rm["per_arm"].get(arm) or {}
            print(f"    {arm}: interval {fmt(ca.get('interval_mean'))} -> "
                  f"{fmt(ra.get('interval_mean'))} s   "
                  f"placed {ca.get('placed')}/{ca.get('attempts')} -> "
                  f"{ra.get('placed')}/{ra.get('attempts')}")
        print(f"  P5 placed  C {cm['placed']}/{cm['attempts']} -> "
              f"T {rm['placed']}/{rm['attempts']}"
              f"   window span {fmt(cm['window'])} -> {fmt(rm['window'])} s"
              f"   window {fmt(cm['window_rate'])} -> {fmt(rm['window_rate'])} placed/min"
              f"   batch {fmt(cm['batch_rate'])} -> {fmt(rm['batch_rate'])}")
        cw = (cm["stats"] or {}).get("wall")
        rw = (rm["stats"] or {}).get("wall")
        if cw and rw:
            print(f"  P5 wall  C {fmt(cw, 1)} s -> T {fmt(rw, 1)} s   "
                  f"placed/min wall {fmt(60.0 * cm['placed'] / cw)} -> "
                  f"{fmt(60.0 * rm['placed'] / rw)}")

        def land(res):
            guests = [t for t in res["data"]["scan"]["traces"] if t["bottom"] >= 0.0]
            return len(guests), sum(1 for t in guests if t["on_belt"])

        cg, cok = land(c)
        rg, rok = land(r)
        print(f"  P3 landing  C {cok}/{cg} on belt -> T {rok}/{rg} on belt")
        ct, rt = totals(c), totals(r)
        print(f"  P4 class  escaped {ct['escaped']} -> {rt['escaped']}   "
              f"never-held {ct['never']} -> {rt['never']}   "
              f"force_min==0 {ct['zero']} -> {rt['zero']}")
        print(f"     lift legs  C escaped {ct['lift_escaped']}/{ct['lift_legs']} "
              f"zero {ct['lift_zero']} never {ct['lift_never']}  ->  T escaped "
              f"{rt['lift_escaped']}/{rt['lift_legs']} zero {rt['lift_zero']} "
              f"never {rt['lift_never']}   (left lift escaped "
              f"{ct['left_lift_escaped']} -> {rt['left_lift_escaped']})")
        print(f"     place legs escaped {ct['place_escaped']}/{ct['place_legs']} -> "
              f"{rt['place_escaped']}/{rt['place_legs']}")
        new_reasons = {k: v for k, v in rm["reasons"].items() if k not in cm["reasons"]}
        print(f"     new reason keys {new_reasons or 'none'}")
        for tag, res in (("C", c), ("T", r)):
            over = [d for d in res["descents"] if d["over"]]
            print(f"  P6 {tag}: {len(res['descents'])} descent legs, {len(over)} over budget"
                  + (f" -> legs {[d['n'] for d in over]}" if over else ""))
        p1b = bool(rlegs) and (
            abs(_p50(err) or 0.0) <= 3.0
            and max(abs(e) for e in peak_err) <= 0.02
            and all(0.41 <= x <= 0.43 for x in rests)
        )
        p1a = d_mean < 0.0 and abs(d_mean - d_pred) <= 0.08
        p2 = d_interval <= 0.0
        p3 = (rg == 0) or (rok == rg)
        p4 = (not new_reasons) and (rt["lift_escaped"] - ct["lift_escaped"] < 1) \
            and (rt["place_escaped"] <= 3) and (rt["escaped"] - ct["escaped"] < 5)
        print(f"  -> P1a {'PASS' if p1a else 'FAIL'}  P1b {'PASS' if p1b else 'FAIL'}  "
              f"P2 {'PASS' if p2 else 'FAIL'}  P3 {'PASS' if p3 else 'FAIL'}  "
              f"P4 {'PASS' if p4 else 'FAIL'}")
        verdicts[seed] = {"p1a": p1a, "p1b": p1b, "p2": p2, "p3": p3, "p4": p4,
                          "d_mean": d_mean, "d_pred": d_pred, "d_interval": d_interval,
                          "landing": f"{rok}/{rg}", "escaped": f"{ct['escaped']}->{rt['escaped']}",
                          "control_totals": ct, "treatment_totals": rt}
    print("\n" + "=" * 78)
    pooled_c = sum(v["control_totals"]["place_legs"] for v in verdicts.values())
    pooled_t = sum(v["treatment_totals"]["place_legs"] for v in verdicts.values())
    p4b = (sum(v["treatment_totals"]["place_escaped"] for v in verdicts.values()) <= 3
           and pooled_c >= 0)
    print(f"P4b pooled place-leg escapes: control "
          f"{sum(v['control_totals']['place_escaped'] for v in verdicts.values())}/{pooled_c}, "
          f"treatment "
          f"{sum(v['treatment_totals']['place_escaped'] for v in verdicts.values())}/{pooled_t} -> "
          f"{'PASS' if p4b else 'FAIL'}")
    ok = all(all(v[k] for k in ("p1a", "p1b", "p2", "p3", "p4"))
             for v in verdicts.values()) and p4b
    for seed, v in verdicts.items():
        print(f"seed {seed}: lift mean {fmt(v['d_mean'], 3)} s (predicted "
              f"{fmt(v['d_pred'], 3)}), interval {fmt(v['d_interval'], 2)} s, "
              f"landing {v['landing']}, escaped {v['escaped']}")
    print(f"P89 gate: {'PASS' if ok else 'FAIL'} "
          f"({'the scoped default may ship' if ok else 'do not flip'})")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "--same":
        return max(p88.show_same(p, q) for p, q in [(argv[2], argv[3])])
    if cmd == "--same-raw":
        return max(p88.show_same(p, q, drop=False) for p, q in [(argv[2], argv[3])])
    if cmd == "--profile":
        return max(show_profile(path) for path in argv[2:])
    if cmd == "--predict":
        for path in argv[2:]:
            pred = lift_prediction(path)
            print(f"[predict] {path}: {len(pred['rows'])} lift attempts   block median "
                  f"{fmt(pred['control_median'], 3)} -> {fmt(pred['predicted_median'], 3)} s "
                  f"(delta {fmt((pred['predicted_median'] or 0) - (pred['control_median'] or 0), 3)})   "
                  f"mean {fmt(pred['control_mean'], 3)} -> {fmt(pred['predicted_mean'], 3)} "
                  f"(delta {fmt((pred['predicted_mean'] or 0) - (pred['control_mean'] or 0), 3)})   "
                  f"remainder {fmt(pred['rest_lo'], 3)}-{fmt(pred['rest_hi'], 3)} s   "
                  f"unpaired {pred['unpaired']}")
            legs = sorted(r["distance"] for r in pred["rows"])
            print(f"           distances {fmt(legs[0], 2)}-{fmt(legs[-1], 2)} m   "
                  f"ticks {min(r['ticks'] for r in pred['rows'])}-"
                  f"{max(r['ticks'] for r in pred['rows'])} shipped")
        return 0
    if cmd == "--landing":
        rc = 0
        for path in argv[2:]:
            data = p88.scan(path)
            guests = [t for t in data["traces"] if t["bottom"] >= 0.0]
            ok = sum(1 for t in guests if t["on_belt"])
            print(f"[landing] {path}: {ok}/{len(guests)} payload-present releases on the belt"
                  f"  ({len(data['traces']) - len(guests)} upstream-lost of "
                  f"{len(data['traces'])})")
            if guests and ok != len(guests):
                rc = 1
        return rc
    if cmd == "--classes":
        for path in argv[2:]:
            table = p88.classes(p88.scan(path))
            print(f"[classes] {path}")
            for key in sorted(table):
                row = table[key]
                print(f"    {key}: n={row['n']} escaped={row['escaped']} "
                      f"never-held={row['never']} force_min==0={row['zero']} "
                      f"slip>800={row['slip800']}")
        return 0
    if cmd == "--cells":
        for path in argv[2:]:
            cell(path)
        return 0
    if cmd == "--blocks":
        return blocks()
    print(f"unknown command {cmd!r}")
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
