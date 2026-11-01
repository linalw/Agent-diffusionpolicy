#!/usr/bin/env python3
"""P87 readout: the two-line-scoped release trim - the gate's six clauses.

    python3 logs/p87/p87_report.py --blocks        # the registered table + verdict
    python3 logs/p87/p87_report.py --cells LOG...  # one cell's endpoints
    python3 logs/p87/p87_report.py --same REF CAND     # `[fruit]` stream, P86's filter
    python3 logs/p87/p87_report.py --same-raw REF CAND  # no filter at all
    python3 logs/p87/p87_report.py --landing LOG

Every endpoint is P80's (`logs/p80/p80lib.py` -> `scripts/186_w6_report.py`):
a placement is the attempt's `t1`, the placement window is
`t_last_place - t_first_place`, the batch span is `t_last_end - t_first_start`,
and the wall comes from the `.stamps` stream. Nothing here re-derives a rate.

**P1a is a median, not a mean** (P86 section 2: the mean is contaminated by one
long `place low` descent on each side while the median is exact). The attempt
span is printed as a **report** and is never a clause (P86 section 3: a per-seed
span is not branch-free). **P6** reads every descent leg's `|v|max`/lurch out of
`[motion] descent` rows and names the worst leg per seed; the budget itself is
`105`'s (the shipped profile's 1.10x peak) and is not re-tuned here.

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


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p80lib = _load("p80lib", os.path.join(ROOT, "logs/p80/p80lib.py"))
motion105 = _load("motion105", os.path.join(ROOT, "scripts/105_motion_regression.py"))

#: P86's sealed filter (`logs/p86/p86_report.py`'s DROP) plus **this phase's own
#: row**. The release-profile row is the one line the flip is *expected* to move
#: (T5/T6 read `=1(default)` where P86's R5/R6 read `=1(explicit)`), so it is
#: dropped from the physics comparison and read on its own.
DROP = (
    "[fruit] [carry]",
    "[fruit] [biarm] scheduler:",
    "[fruit] [diag] carry-assist",
    "[fruit] [biarm] left: park",
    "[fruit] [biarm] right: park",
    "[task]   place trace",
    "[fruit] [biarm] release profile:",
)

CYCLE = re.compile(r"\[cycle\] attempt \d+: (.+)")
RESULT = re.compile(r"\[biarm\] result (?P<arm>\w+) index=\d+")
PICKING = re.compile(
    r"\[run\] attempt (?P<n>\d+) \((?P<arm>\w+)\): picking .* sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s")
PLACE_TRACE = re.compile(
    r"\[task\]   place trace (?P<arm>\w+): release_bottom=(?P<bottom>[+\-\d.]+)mm "
    r"impact=(?P<impact>[+\-\d.]+)m/s bounce=(?P<bounce>[+\-\d.]+)mm "
    r"roll=(?P<roll>[+\-\d.]+)mm skid=(?P<skid>[+\-\d.]+)mm "
    r"settle=(?P<settle>[+\-\dnan]+)ms .*?on_belt=(?P<on_belt>True|False)")
DESCENT = re.compile(
    r"\[motion\] descent (?P<arm>\w+): .*?\|v\|max=(?P<v>[\d.]+).*?lurch=(?P<lurch>[\d.]+)")
DESCENT_ANY = re.compile(r"\[motion\] descent ")
DISCHARGED = re.compile(r"\[belt\] .* discharged to the tray")
PROFILE = re.compile(r"\[fruit\] \[biarm\] release profile: (?P<label>\S+) scope=(?P<scope>\S+) "
                     r"dwell=(?P<dwell>-?\d+) pad_hold=(?P<pad>\d+) "
                     r"finger_hold=(?P<finger>\d+) \((?P<ticks>\d+) ticks; "
                     r"shipped (?P<shipped>\d+), saved (?P<saved>-?\d+)\)")


def descent_legs(path: str) -> list[dict]:
    """Every descent leg judged by **`105`'s own** parser and per-leg budget.

    P6 asks whether a descent leg is over budget, and that budget is 105's
    (`descent_profile_peak(distance) * ACHIEVED_MARGIN`, the shipped profile's
    1.10x peak, and `LURCH_FACTOR * peak` for the per-tick lurch). Re-deriving it
    here would be a second definition of "over budget"; instead the legs come
    from `105_motion_regression.parse` and the verdict is 105's own comparison.
    """
    legs, _carries, _tally, dynamic = motion105.parse(path)
    out = []
    for index, leg in enumerate(legs, 1):
        peak = motion105.descent_profile_peak(leg["distance_cm"] / 100.0, dynamic)
        budget = (peak * motion105.ACHIEVED_MARGIN) if peak else motion105.REFERENCE_VMAX
        # 105's own lurch bound: `LURCH_FACTOR * peak / CONTROL_DT` [m/s^2], i.e.
        # `LURCH_FACTOR * peak` [m/s] per tick on the printed scale.
        lurch_bound = (
            motion105.LURCH_FACTOR * peak / motion105.CONTROL_DT
            if peak
            else motion105.LURCH_FACTOR * motion105.REFERENCE_VMAX / motion105.CONTROL_DT
        )
        over = []
        if leg["v_max"] > budget:
            over.append(f"|v|max {leg['v_max']:.3f}>{budget:.3f}")
        if leg["a_max"] > lurch_bound:
            over.append(f"lurch {leg['a_max'] * motion105.CONTROL_DT:.3f}"
                        f">{motion105.LURCH_FACTOR * peak:.3f} m/s/tick")
        out.append({"n": index, **leg, "budget": budget, "lurch_bound": lurch_bound,
                    "over": over})
    return out

BLOCKS = ["prepose", "hover", "descent", "close", "grip", "lift", "place",
          "release", "return", "end", "total"]


def fmt(value, nd: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value != value:  # nan
        return "nan"
    return f"{value:.{nd}f}"


def fruit_stream(path: str, drop: bool = True) -> list[str]:
    out = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "[fruit]" not in line:
                continue
            text = line.rstrip("\n")
            if drop and any(marker in text for marker in DROP):
                continue
            out.append(text)
    return out


def show_same(reference: str, candidate: str, drop: bool = True) -> int:
    a, b = fruit_stream(reference, drop), fruit_stream(candidate, drop)
    tag = "diag/trace rows dropped" if drop else "raw, no filter"
    print(f"[same] ref={reference} ({len(a)} lines)  cand={candidate} ({len(b)})  [{tag}]")
    if a == b:
        print("[same] IDENTICAL on every `[fruit]` line")
        return 0
    index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    print(f"[same] DIFFERS at line {index} (common prefix {index})")
    for name, stream in (("ref", a), ("cand", b)):
        if index < len(stream):
            print(f"  {name}: {stream[index][:220]}")
    return 1


def cycles_and_spans(path: str) -> dict:
    """`[cycle]` blocks paired to their arm, the driver's windows, the traces."""
    cycles: list[dict] = []
    pending: dict | None = None
    windows: list[dict] = []
    traces: list[dict] = []
    descents: list[dict] = []
    discharged = 0
    profile = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if m := PROFILE.search(line):
                profile = {k: (int(v) if v.lstrip("-").isdigit() else v)
                           for k, v in m.groupdict().items()}
                continue
            if m := CYCLE.search(line):
                seg = {}
                for part in m.group(1).split():
                    name, _, value = part.partition("=")
                    seg[name] = float(value.rstrip("s"))
                pending = {"blocks": seg, "arm": None}
                cycles.append(pending)
                continue
            if m := RESULT.search(line):
                if pending is not None:
                    pending["arm"] = m.group("arm")
                    pending = None
                continue
            if m := PICKING.search(line):
                windows.append({"n": int(m.group("n")), "arm": m.group("arm"),
                                "t0": float(m.group("t0")), "t1": float(m.group("t1"))})
                continue
            if m := PLACE_TRACE.search(line):
                settle = m.group("settle")
                traces.append({
                    "arm": m.group("arm"),
                    "bottom": float(m.group("bottom")),
                    "impact": float(m.group("impact")),
                    "bounce": float(m.group("bounce")),
                    "on_belt": m.group("on_belt") == "True",
                })
                continue
            if DESCENT_ANY.search(line):
                m = DESCENT.search(line)
                if m:
                    descents.append({"arm": m.group("arm"), "v": float(m.group("v")),
                                     "lurch": float(m.group("lurch"))})
                continue
            if DISCHARGED.search(line):
                discharged += 1
    missing = [i for i, c in enumerate(cycles) if c["arm"] is None]
    if missing:
        print(f"  !! {len(missing)} [cycle] rows without a following [biarm] result row")
    spans = []
    for cycle, window in zip(cycles, windows):
        cycle["span"] = window["t1"] - window["t0"]
        cycle["arm"] = cycle["arm"] or window["arm"]
        cycle["window_arm"] = window["arm"]
        cycle["delta"] = cycle["blocks"].get("total", float("nan")) - cycle["span"]
        spans.append(cycle)
    worst = max((abs(c["delta"]) for c in spans), default=0.0)
    mismatched = [i for i, c in enumerate(spans) if c["arm"] != c["window_arm"]]
    if mismatched:
        print(f"  !! {len(mismatched)} [cycle] rows disagree with their window's arm")
    return {"cycles": cycles, "windows": windows, "traces": traces,
            "descents": descents, "discharged": discharged, "profile": profile,
            "worst_total_delta": worst, "arm_mismatches": len(mismatched)}


def _mean(values):
    return st.fmean(values) if values else None


def _p50(values):
    return st.median(values) if values else None


def _block(cycles: list[dict], name: str) -> list[float]:
    return [c["blocks"][name] for c in cycles if name in c["blocks"]]


def cell(path: str) -> dict:
    m = p80lib.metrics(path)
    stats = m.get("stats") or {}
    extra = cycles_and_spans(path)
    cycles = extra["cycles"]
    released = [c for c in cycles if "release" in c["blocks"]]
    print(f"\n== {path} ==")
    if extra["profile"]:
        p = extra["profile"]
        print(f"  release profile {p['label']} scope={p['scope']} -> "
              f"{p['dwell']}/{p['pad']}/{p['finger']} ({p['ticks']} ticks, "
              f"shipped {p['shipped']}, saved {p['saved']})")
    else:
        print("  release profile: NO `[biarm] release profile:` row (a non-bimanual log)")
    print(f"  [cycle] rows {len(cycles)}  [run] windows {len(extra['windows'])}  "
          f"paired {len(released)} with a release block  "
          f"worst |total-window| {fmt(extra['worst_total_delta'])} s  "
          f"arm mismatches {extra['arm_mismatches']}")
    print(f"  placed {m['placed']}/{m['attempts']} = {100.0 * (m['rate'] or 0):.1f} %   "
          f"s/attempt {fmt(stats.get('per_attempt'))}   sim {fmt(stats.get('sim_total'))} s")
    if stats.get("biarm"):
        b = stats["biarm"]
        print(f"  per arm  left {b['l']}/{b['la']}   right {b['r']}/{b['ra']}   "
              f"pipelined slots {b['slots']}   biarm {b['rate']} fruits/min")
    print("  blocks (mean s; n in brackets):")
    print("   " + "  ".join(f"{name}={fmt(_mean(_block(cycles, name)))}"
                            f"[{len(_block(cycles, name))}]" for name in BLOCKS))
    print(f"  release block  mean {fmt(_mean(_block(cycles, 'release')))} s   "
          f"MEDIAN {fmt(_p50(_block(cycles, 'release')))} s   "
          f"p50 ticks {fmt((_p50(_block(cycles, 'release')) or 0) * 120, 0)}")
    for arm in sorted({c["arm"] for c in released if c["arm"]}):
        arm_rel = [c for c in released if c["arm"] == arm]
        arm_all = [c for c in cycles if c["arm"] == arm]
        print(f"    {arm}: release mean {fmt(_mean([c['blocks']['release'] for c in arm_rel]))} s "
              f"median {fmt(_p50([c['blocks']['release'] for c in arm_rel]))} s (n={len(arm_rel)})  "
              f"span@release {fmt(_mean([c['span'] for c in arm_rel]))} s")
    print(f"  pooled interval {fmt(m['pooled']['mean'])} s mean / {fmt(m['pooled']['p50'])} p50 / "
          f"{fmt(m['pooled']['p90'])} p90 (n={m['pooled']['n']})")
    for arm, data in sorted(m["per_arm"].items()):
        print(f"    {arm}: placed {data['placed']}/{data['attempts']}  "
              f"interval {fmt(data['interval_mean'])} / {fmt(data['interval_p90'])} s  "
              f"idle {fmt((data['idle_frac'] or 0) * 100, 1)} %")
    print(f"  window {fmt(m['window_rate'])} placed/min   batch {fmt(m['batch_rate'])} placed/min"
          f"   window span {fmt(m['window'])} s   batch span {fmt(m['batch_span'])} s")
    if stats.get("wall"):
        print(f"  wall {fmt(stats['wall'], 1)} s   wall/pick {fmt(stats['wall_per_pick'])} s   "
              f"wall/sim {fmt(stats['wall_over_sim'])}x   "
              f"placed/min wall {fmt(60.0 * m['placed'] / stats['wall'])}")
    else:
        print("  wall: NO STAMPS")
    traces = extra["traces"]
    if traces:
        guests = [t for t in traces if t["bottom"] >= 0.0]
        print(f"  landing: {len(traces)} traces, {len(guests)} payload-present, "
              f"on_belt {sum(1 for t in guests if t['on_belt'])}/{len(guests)}"
              f"   discharged {extra['discharged']}")
        if guests:
            print(f"    release_bottom {fmt(min(t['bottom'] for t in guests), 1)}"
                  f"..{fmt(max(t['bottom'] for t in guests), 1)} mm   "
                  f"impact {fmt(min(t['impact'] for t in guests))}"
                  f"..{fmt(max(t['impact'] for t in guests))} m/s   "
                  f"bounce <= {fmt(max(t['bounce'] for t in guests), 1)} mm   "
                  f"upstream-lost {len(traces) - len(guests)}")
    descents = descent_legs(path)
    if descents:
        worst = max(descents, key=lambda d: d["v_max"])
        over = [d for d in descents if d["over"]]
        budgets = sorted({round(d["budget"], 3) for d in descents})
        print(f"  descent legs {len(descents)} (105's parser + per-leg budget)  "
              f"over budget {len(over)}  budgets {budgets}  "
              f"worst |v|max {fmt(worst['v_max'], 3)} (leg {worst['n']}, "
              f"{worst['distance_cm']:.1f} cm)  "
              f"worst lurch {fmt(max(d['a_max'] * motion105.CONTROL_DT for d in descents), 3)}")
        for d in over:
            print(f"    OVER leg {d['n']} ({d['distance_cm']:.1f} cm): {', '.join(d['over'])}")
    print(f"  classes {m['classes']}")
    print(f"  reasons {m['reasons']}")
    return {"m": m, "extra": extra, "descents": descents}


def blocks() -> int:
    print("P87 - the release trim as a two-line-scoped default (PREREG S5)")
    print("=" * 78)
    verdicts = {}
    for seed, control, treatment in (("5", "logs/p87/C5.log", "logs/p87/T5.log"),
                                     ("6", "logs/p87/C6.log", "logs/p87/T6.log")):
        c, r = cell(control), cell(treatment)
        cm, rm = c["m"], r["m"]
        ccyc = [x for x in c["extra"]["cycles"] if "release" in x["blocks"]]
        rcyc = [x for x in r["extra"]["cycles"] if "release" in x["blocks"]]
        c_rel = _p50([x["blocks"]["release"] for x in ccyc])
        r_rel = _p50([x["blocks"]["release"] for x in rcyc])
        d_rel = (r_rel or 0.0) - (c_rel or 0.0)
        c_span = _mean([x["span"] for x in ccyc])
        r_span = _mean([x["span"] for x in rcyc])
        d_interval = rm["pooled"]["mean"] - cm["pooled"]["mean"]
        print(f"\n## seed {seed}")
        print(f"  P1a release block MEDIAN  C {fmt(c_rel, 3)} s -> T {fmt(r_rel, 3)} s   "
              f"delta {fmt(d_rel, 3)} s ({fmt(120.0 * d_rel, 1)} ticks; registered -76)"
              f"   band +-0.03 s")
        print(f"  report: attempt span (release attempts)  C {fmt(c_span)} s -> "
              f"T {fmt(r_span)} s   delta {fmt((r_span or 0) - (c_span or 0))} s   "
              f"rest {fmt(((r_span or 0) - (c_span or 0)) - d_rel)} s")
        for arm in ("left", "right"):
            ca = [x for x in ccyc if x["arm"] == arm]
            ra = [x for x in rcyc if x["arm"] == arm]
            if ca and ra:
                print(f"    {arm}: release median "
                      f"{fmt(_p50([x['blocks']['release'] for x in ca]), 3)} -> "
                      f"{fmt(_p50([x['blocks']['release'] for x in ra]), 3)} s   "
                      f"delta {fmt((_p50([x['blocks']['release'] for x in ra]) or 0)
                                    - (_p50([x['blocks']['release'] for x in ca]) or 0), 3)} s"
                      f" (n={len(ca)}/{len(ra)})")
        print(f"  P2 pooled interval  C {fmt(cm['pooled']['mean'])} -> "
              f"T {fmt(rm['pooled']['mean'])} s   delta {fmt(d_interval)} s")
        for arm in ("left", "right"):
            ca = cm["per_arm"].get(arm) or {}
            ra = rm["per_arm"].get(arm) or {}
            print(f"    {arm}: interval {fmt(ca.get('interval_mean'))} -> "
                  f"{fmt(ra.get('interval_mean'))} s   "
                  f"placed {ca.get('placed')}/{ca.get('attempts')} -> "
                  f"{ra.get('placed')}/{ra.get('attempts')}")
        cw = (cm["stats"] or {}).get("wall")
        rw = (rm["stats"] or {}).get("wall")
        print(f"  P5 placed  C {cm['placed']}/{cm['attempts']} -> T {rm['placed']}/{rm['attempts']}"
              f"   window {fmt(cm['window_rate'])} -> {fmt(rm['window_rate'])}"
              f"   batch {fmt(cm['batch_rate'])} -> {fmt(rm['batch_rate'])}")
        if cw and rw:
            print(f"    wall  C {fmt(cw, 1)} s -> T {fmt(rw, 1)} s   "
                  f"placed/min wall {fmt(60.0 * cm['placed'] / cw)} -> "
                  f"{fmt(60.0 * rm['placed'] / rw)}")

        def land(res):
            guests = [t for t in res["extra"]["traces"] if t["bottom"] >= 0.0]
            return len(guests), sum(1 for t in guests if t["on_belt"])

        cg, cok = land(c)
        rg, rok = land(r)
        new_reasons = {k: v for k, v in rm["reasons"].items() if k not in cm["reasons"]}
        forced = [d for d in r["descents"] if d["over"]]
        forced_c = [d for d in c["descents"] if d["over"]]
        print(f"  P3 landing  C {cok}/{cg} on belt -> T {rok}/{rg}   "
              f"P4 new reasons {new_reasons or 'none'}")
        print(f"  P6 descent budgets (105's per-leg budget)  C over "
              f"{len(forced_c)}/{len(c['descents'])} -> T over "
              f"{len(forced)}/{len(r['descents'])}"
              + ("" if not forced else
                 "   " + ", ".join(f"leg {d['n']} {d['v_max']:.3f}/{d['budget']:.3f}"
                                   f" ({d['distance_cm']:.1f} cm)" for d in forced)))
        p1a = abs(d_rel + 0.6333) <= 0.03
        p2 = d_interval < 0.0
        p3 = (rg == 0) or (rok == rg)
        p4 = not new_reasons
        p6 = not forced
        verdicts[seed] = {"p1a": p1a, "p2": p2, "p3": p3, "p4": p4, "p6": p6,
                          "forced": len(forced), "legs": len(r["descents"]),
                          "worst": max((d["v_max"] for d in forced), default=0.0),
                          "worst_budget": max((d["budget"] for d in forced), default=0.0)}
        print(f"  -> P1a {'PASS' if p1a else 'FAIL'}   P2 {'PASS' if p2 else 'FAIL'}   "
              f"P3 {'PASS' if p3 else 'FAIL'}   P4 {'PASS' if p4 else 'FAIL'}   "
              f"P6 {'PASS' if p6 else 'FAIL'}")

    seeds = sorted(verdicts)
    core = all(all(v[k] for k in ("p1a", "p2", "p3", "p4")) for v in verdicts.values())
    clean = core and all(v["p6"] for v in verdicts.values())
    total_forced = sum(v["forced"] for v in verdicts.values())
    worst = max(v["worst"] for v in verdicts.values())
    worst_budget = max(v["worst_budget"] for v in verdicts.values())
    trade = (core and not clean and total_forced <= 1
             and worst <= worst_budget * 1.025 + 1e-9)
    print("\nDECISION RULE (PREREG S5): clean pass = P1a (median -0.633 +- 0.03 s) AND "
          "P2 (interval down)\n  AND P3 (landing) AND P4 (no new class) AND P6 (no leg "
          "over budget) at BOTH seeds.\n  Considered trade = the core four hold and P6 "
          "shows exactly the one P86 R6 leg (<= 2.5 % over).")
    print(f"\nP6 pool: {total_forced} over-budget descent legs of "
          f"{sum(v['legs'] for v in verdicts.values())} treatment legs "
          f"(worst {worst:.3f} against a {worst_budget:.3f} budget)")
    print(f"verdict: {'CLEAN PASS - ship' if clean else ('CONSIDERED TRADE - ship, P6 documented' if trade else 'FAIL - do not flip')}")
    return 0 if (clean or trade) else 1


def landing(path: str) -> int:
    traces = cycles_and_spans(path)["traces"]
    bad = 0
    for t in traces:
        ok = t["on_belt"] or t["bottom"] < 0.0
        bad += 0 if ok else 1
        print(f"  {t['arm']:5s} bottom={t['bottom']:+8.1f}mm impact={t['impact']:+.2f}m/s "
              f"bounce={t['bounce']:6.1f}mm on_belt={t['on_belt']}"
              f"{'' if ok else '   <-- PAYLOAD PRESENT AND OFF BELT'}")
    print(f"[landing] {len(traces)} traces, {bad} payload-present off-belt")
    return 0 if bad == 0 else 1


def profile_of(path: str) -> dict | None:
    """The `[biarm] release profile:` row of a log, or `None`."""
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if m := PROFILE.search(line):
                return {k: (int(v) if v.lstrip("-").isdigit() else v)
                        for k, v in m.groupdict().items()}
    return None


def show_profile(ref: str, cand: str) -> int:
    """Compare two runs' resolved release clock, ignoring the **origin** label.

    Two runs of the same configuration legitimately differ in `origin` when one
    names the value explicitly and the other takes the scope default (`explicit`
    vs `scope-off`) - that is what the label is for (P43's `defaulted`
    convention). What must be equal is the **clock**: the three holds, the tick
    count and the shipped count. This is P87's recorded deviation A1 to
    `PREREG.md` G2b's literal "whole `[fruit]` stream" wording.
    """
    a, b = profile_of(ref), profile_of(cand)
    keys = ("dwell", "pad", "finger", "ticks", "shipped")
    print(f"[profile] ref={ref} ({a and a['label']} {a and a['scope']})")
    print(f"[profile] cand={cand} ({b and b['label']} {b and b['scope']})")
    if a is None or b is None:
        print("[profile] DIFFERS: a log has no release-profile row")
        return 1
    if all(a[k] == b[k] for k in keys) and a["scope"] == b["scope"]:
        print(f"[profile] IDENTICAL clock {tuple(a[k] for k in keys)} scope={a['scope']}"
              f" (origin {a['label']} vs {b['label']} - the label, not the clock)")
        return 0
    print(f"[profile] DIFFERS on the clock: "
          f"{ {k: (a[k], b[k]) for k in keys if a[k] != b[k]} }")
    return 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "--blocks":
        return blocks()
    if args[0] == "--cells":
        for path in args[1:]:
            cell(path)
        return 0
    if args[0] == "--same":
        return show_same(args[1], args[2], drop=True)
    if args[0] == "--same-raw":
        return show_same(args[1], args[2], drop=False)
    if args[0] == "--profile":
        return show_profile(args[1], args[2])
    if args[0] == "--landing":
        return landing(args[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
