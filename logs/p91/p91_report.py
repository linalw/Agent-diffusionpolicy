#!/usr/bin/env python3
"""P91 readout: the take-off validation ramp as a two-line-scoped tick cell.

    python3 logs/p91/p91_report.py --blocks           # the registered table + verdict
    python3 logs/p91/p91_report.py --cells LOG...     # one cell's endpoints
    python3 logs/p91/p91_report.py --same REF CAND    # the `[fruit]` stream, sealed filter
    python3 logs/p91/p91_report.py --window LOG...    # the catch window (P5)
    python3 logs/p91/p91_report.py --pinch LOG...     # the delivered pinch (P7)
    python3 logs/p91/p91_report.py --profile LOG      # the take-off row

Every delivered endpoint is P80's (`logs/p80/p80lib.py` -> `scripts/186_w6_report.py`):
a placement is the attempt's `t1`, the placement window is
`t_last_place - t_first_place`, the batch span is `t_last_end - t_first_start`,
and the wall comes from the `.stamps` stream. Nothing here re-derives a rate.

**P1 is read two ways** (`logs/p91/PREREG.md` section 4): P1a the `[cycle] grip=`
block's mean and median over the 20 attempts, against the registered
**-0.300 s**; P1b the **clean-attempt distribution** - a clean grip block is a
deterministic constant (the probe's loop count plus a fixed 150-tick remainder,
`logs/p91/AUDIT.md` section 4), so the per-attempt instance is the *clean* value,
and the treatment's clean set must sit **entirely below** the control's
(`max(T) < min(C) - 0.25`). A mean across the mixed clean/tax population is not
branch-free and is reported beside it, never as the gate.

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


p80lib = _load("p80lib", os.path.join(ROOT, "logs/p80/p80lib.py"))
motion105 = _load("motion105", os.path.join(ROOT, "scripts/105_motion_regression.py"))

#: P89's sealed filter plus **this phase's own row** (`[biarm] take-off profile:`).
#: The take-off row is the one line the flip is *expected* to move (a treatment
#: cell reads `=24(default)` where its control reads `=60(explicit)`), so it is
#: dropped from the physics comparison and read on its own (`--profile`).
DROP = (
    "[fruit] [carry]",
    "[fruit] [biarm] scheduler:",
    "[fruit] [diag] carry-assist",
    "[fruit] [biarm] left: park",
    "[fruit] [biarm] right: park",
    "[task]   place trace",
    "[fruit] [biarm] release profile:",
    "[fruit] [biarm] place profile:",
    "[fruit] [biarm] lift profile:",
    "[fruit] [biarm] take-off profile:",
)

CYCLE = re.compile(r"\[cycle\] attempt \d+: (.+)")
RESULT = re.compile(
    r"\[biarm\] result (?P<arm>\w+) index=\d+ .*?grasped=(?P<g>\w+) "
    r"placed=(?P<p>\w+).*?notes=\[(?P<notes>.*)\]")
PICKING = re.compile(
    r"\[run\] attempt (?P<n>\d+) \((?P<arm>\w+)\): picking .* sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s")
PLACE_TRACE = re.compile(
    r"\[task\]   place trace (?P<arm>\w+): release_bottom=(?P<bottom>[+\-\d.]+)mm "
    r"impact=(?P<impact>[+\-\d.]+)m/s bounce=(?P<bounce>[+\-\d.]+)mm "
    r"roll=(?P<roll>[+\-\d.]+)mm skid=(?P<skid>[+\-\d.]+)mm "
    r"settle=(?P<settle>[+\-\dnan]+)ms .*?on_belt=(?P<on_belt>True|False)")
CATCHUP = re.compile(r"dynamic catch-up: residual=(?P<r>[\d.]+) mm")
APPROACH = re.compile(
    r"\[motion\] approach\(cartesian\): (?P<cm>[\d.]+) cm, (?P<n>\d+) samples: "
    r".*?end=(?P<end>[\d.]+) mm")
DESCENT = re.compile(
    r"\[motion\] descent (?P<arm>\w+): .*?\|v\|max=(?P<v>[\d.]+).*?lurch=(?P<lurch>[\d.]+)")
DESCENT_ANY = re.compile(r"\[motion\] descent ")
CARRY = re.compile(r"\[fruit\] \[carry\] (?P<arm>left|right) (?P<leg>\w+): (?P<rest>.*)$")
TAKEOFF_PROFILE = re.compile(
    r"\[fruit\] \[biarm\] take-off profile: (?P<label>\S+) scope=(?P<scope>\S+) "
    r"probe_lift=(?P<lift>[\d.]+) \((?P<ticks>-?\d+) ticks; "
    r"shipped (?P<shipped>-?\d+), saved (?P<saved>-?\d+)\)")
RELEASE_PROFILE = re.compile(r"\[fruit\] \[biarm\] release profile: (?P<label>\S+)")
DISCHARGED = re.compile(r"\[belt\] .* discharged to the tray")


def fmt(value, nd: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value != value:
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
    tag = "sealed filter (diag/trace/profile rows dropped)" if drop else "raw, no filter"
    print(f"[same] ref={reference} ({len(a)} lines)  cand={candidate} ({len(b)})  [{tag}]")
    if a == b:
        print("[same] IDENTICAL on every `[fruit]` line")
        return 0
    index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                 min(len(a), len(b)))
    print(f"[same] DIFFERS at line {index} (common prefix {index})")
    for name, stream in (("ref", a), ("cand", b)):
        if index < len(stream):
            print(f"  {name}: {stream[index][:220]}")
    return 1


def show_profile(path: str) -> int:
    takeoff = release = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if takeoff is None and (m := TAKEOFF_PROFILE.search(line)):
                takeoff = m.groupdict()
            if release is None and (m := RELEASE_PROFILE.search(line)):
                release = m.groupdict()
    print(f"[profile] {path}")
    if takeoff is None:
        print("  take-off: NO ROW (a non-bimanual log)")
    else:
        print(f"  take-off: {takeoff['label']} scope={takeoff['scope']} "
              f"probe_lift={takeoff['lift']} m ({takeoff['ticks']} ticks; "
              f"shipped {takeoff['shipped']}, saved {takeoff['saved']})")
    print(f"  release:  {release['label'] if release else 'NO ROW'}")
    return 0


def _num(rest: str, key: str, cast=float):
    found = re.search(rf"{key}=([+\-\d.]+|n/a)", rest)
    if not found or found.group(1) == "n/a":
        return None
    try:
        return cast(found.group(1))
    except ValueError:
        return None


def scan(path: str) -> dict:
    """`[cycle]` blocks paired to their arm, plus the P91 guards."""
    cycles: list[dict] = []
    pending: dict | None = None
    windows: list[dict] = []
    traces: list[dict] = []
    carry: list[dict] = []
    descents: list[dict] = []
    results: list[dict] = []
    catchup: list[float] = []
    approach: list[dict] = []
    profiles: list[dict] = []
    discharged = 0
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if m := TAKEOFF_PROFILE.search(line):
                profiles.append(m.groupdict())
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
                row = {"arm": m.group("arm"), "grasped": m.group("g") == "True",
                       "placed": m.group("p") == "True",
                       "notes": [n.strip().strip("'\"") for n in m.group("notes").split(",")
                                 if n.strip()]}
                results.append(row)
                if pending is not None:
                    pending["arm"] = row["arm"]
                    pending["grasped"] = row["grasped"]
                    pending["placed"] = row["placed"]
                    pending["notes"] = row["notes"]
                    pending = None
                continue
            if m := PICKING.search(line):
                windows.append({"n": int(m.group("n")), "arm": m.group("arm"),
                                "t0": float(m.group("t0")), "t1": float(m.group("t1"))})
                continue
            if m := PLACE_TRACE.search(line):
                settle = m.group("settle")
                traces.append({"arm": m.group("arm"),
                               "bottom": float(m.group("bottom")),
                               "impact": float(m.group("impact")),
                               "bounce": float(m.group("bounce")),
                               "settle": None if settle == "nan" else float(settle),
                               "on_belt": m.group("on_belt") == "True"})
                continue
            if m := CATCHUP.search(line):
                catchup.append(float(m.group("r")))
                continue
            if m := APPROACH.search(line):
                approach.append({"cm": float(m.group("cm")), "samples": int(m.group("n")),
                                 "end": float(m.group("end"))})
                continue
            if DESCENT_ANY.search(line):
                if m := DESCENT.search(line):
                    descents.append({"arm": m.group("arm"), "v": float(m.group("v")),
                                     "lurch": float(m.group("lurch"))})
                continue
            if m := CARRY.search(line):
                rest = m.group("rest")
                row = {"arm": m.group("arm"), "leg": m.group("leg"),
                       "clean_slip": _num(rest, "clean_slip_max"),
                       "force_min": _num(rest, "force_min"),
                       "fmax": _num(rest, "fmax"),
                       "ticks": None}
                found = re.search(r"ticks=(\d+)/(\d+)", rest)
                if found:
                    row["ticks"] = int(found.group(1))
                carry.append(row)
                continue
            if DISCHARGED.search(line):
                discharged += 1
    missing = [i for i, c in enumerate(cycles) if c["arm"] is None]
    if missing:
        print(f"  !! {len(missing)} [cycle] rows without a following [biarm] result row")
    for cycle, window in zip(cycles, windows):
        cycle["span"] = window["t1"] - window["t0"]
        cycle["window_arm"] = window["arm"]
    mismatched = [i for i, c in enumerate(cycles)
                  if c["arm"] and c["window_arm"] and c["arm"] != c["window_arm"]]
    if mismatched:
        print(f"  !! {len(mismatched)} [cycle] rows disagree with their window's arm")
    return {"cycles": cycles, "windows": windows, "traces": traces, "carry": carry,
            "descents": descents, "results": results, "catchup": catchup,
            "approach": approach, "profiles": profiles, "discharged": discharged,
            "arm_mismatches": len(mismatched)}


def _mean(values):
    return st.fmean(values) if values else None


def _p50(values):
    return st.median(values) if values else None


def _block(cycles, name):
    return [c["blocks"][name] for c in cycles if name in c["blocks"]]


def _clean(cycles):
    """The clean single-probe grip values: the block's **lowest mode**.

    A clean grip block is a deterministic constant (the probe's loop count plus a
    fixed 150-tick remainder), so the arm's own minimum identifies it; the window
    is `min + 0.10 s` because the *cheap* W1 re-seat adds +0.21 s and would
    otherwise be counted as clean in one arm (where the minimum is lower) and not
    in the other - the bug this definition replaces. The whole histogram is
    printed beside it so a reader can see the modes, not just the label.
    """
    vals = _block(cycles, "grip")
    if not vals:
        return []
    low = min(vals)
    return sorted(v for v in vals if v <= low + 0.10)


def cell(path: str) -> dict:
    m = p80lib.metrics(path)
    stats = m.get("stats") or {}
    data = scan(path)
    cycles = data["cycles"]
    print(f"\n== {path} ==")
    if data["profiles"]:
        p = data["profiles"][0]
        print(f"  take-off profile {p['label']} scope={p['scope']} probe_lift="
              f"{p['lift']} m -> {p['ticks']} ticks (shipped {p['shipped']}, "
              f"saved {p['saved']})")
    else:
        print("  take-off profile: NO ROW")
    print(f"  [cycle] rows {len(cycles)}  [run] windows {len(data['windows'])}  "
          f"arm mismatches {data['arm_mismatches']}")
    print(f"  placed {m['placed']}/{m['attempts']} = {100.0 * (m['rate'] or 0):.1f} %   "
          f"s/attempt {fmt(stats.get('per_attempt'))}   sim {fmt(stats.get('sim_total'))} s")
    if stats.get("biarm"):
        b = stats["biarm"]
        print(f"  per arm  left {b['l']}/{b['la']}   right {b['r']}/{b['ra']}   "
              f"pipelined slots {b['slots']}")
    print("  blocks (mean s; n in brackets):")
    print("   " + "  ".join(f"{name}={fmt(_mean(_block(cycles, name)))}"
                            f"[{len(_block(cycles, name))}]" for name in
                            ["prepose", "hover", "descent", "close", "grip", "lift",
                             "place", "release", "return", "end", "total"]))
    grip = _block(cycles, "grip")
    print(f"  >>> P1  grip block  mean {fmt(_mean(grip))} s   MEDIAN {fmt(_p50(grip))} s"
          f"   = {fmt((_p50(grip) or 0) * 120, 0)} ticks (median)")
    modes = {}
    for v in _block(cycles, "grip"):
        modes[round(v, 1)] = modes.get(round(v, 1), 0) + 1
    print(f"      grip mode histogram (0.1 s bins): "
          + "  ".join(f"{k}s x{v}" for k, v in sorted(modes.items())))
    print(f"      clean (lowest mode, min + 0.10 s): "
          f"{[round(v, 2) for v in _clean(cycles)]}")
    print(f"  pooled interval {fmt(m['pooled']['mean'])} s mean / "
          f"{fmt(m['pooled']['p50'])} p50 / {fmt(m['pooled']['p90'])} p90 "
          f"(n={m['pooled']['n']})")
    for arm, data_arm in sorted(m["per_arm"].items()):
        print(f"    {arm}: placed {data_arm['placed']}/{data_arm['attempts']}  "
              f"interval {fmt(data_arm['interval_mean'])} / "
              f"{fmt(data_arm['interval_p90'])} s  idle "
              f"{fmt((data_arm['idle_frac'] or 0) * 100, 1)} %")
    print(f"  window {fmt(m['window_rate'])} placed/min   batch "
          f"{fmt(m['batch_rate'])} placed/min   window span {fmt(m['window'])} s   "
          f"batch span {fmt(m['batch_span'])} s")
    if stats.get("wall"):
        print(f"  wall {fmt(stats['wall'], 1)} s   wall/pick "
              f"{fmt(stats['wall_per_pick'])} s   wall/sim "
              f"{fmt(stats['wall_over_sim'])}x   placed/min wall "
              f"{fmt(60.0 * m['placed'] / stats['wall'])}")
    else:
        print("  wall: NO STAMPS")
    # P5 the catch window
    resid = data["catchup"]
    ends = [a["end"] for a in data["approach"]]
    print(f"  P5 catch window: residual median {fmt(_p50(resid), 1)} mm "
          f"(max {fmt(max(resid) if resid else None, 1)}), end= median "
          f"{fmt(_p50(ends), 1)} / max {fmt(max(ends) if ends else None, 1)} mm, "
          f"grasp {sum(1 for r in data['results'] if r['grasped'])}/"
          f"{len(data['results'])}")
    # P7 the delivered pinch (held lift legs only)
    held = [r for r in data["carry"] if r["leg"] == "grasp_lift"
            and r["fmax"] is not None and r["fmax"] > 0.0
            and r["force_min"] is not None]
    if held:
        below = [r["force_min"] for r in held if r["force_min"] < 9.0]
        print(f"  P7 pinch (held grasp_lift): force_min median "
              f"{fmt(_p50([r['force_min'] for r in held]))} N "
              f"(n={len(held)}), fmax median {fmt(_p50([r['fmax'] for r in held]))} N"
              f"   below the 9.0 N floor {len(below)}/{len(held)}")
    # P3/P4 landing and class
    traces = data["traces"]
    guests = [t for t in traces if t["bottom"] >= 0.0]
    if traces:
        print(f"  P3 landing: {len(traces)} traces, {len(guests)} payload-present, "
              f"on_belt {sum(1 for t in guests if t['on_belt'])}/{len(guests)}"
              f"   discharged {data['discharged']}")
        if guests:
            print(f"    release_bottom {fmt(min(t['bottom'] for t in guests), 1)}"
                  f"-{fmt(max(t['bottom'] for t in guests), 1)} mm   impact "
                  f"{fmt(min(t['impact'] for t in guests))}"
                  f"..{fmt(max(t['impact'] for t in guests))} m/s   bounce <= "
                  f"{fmt(max(t['bounce'] for t in guests), 1)} mm")
    reasons = {}
    for row in data["results"]:
        for note in row["notes"]:
            reasons[note] = reasons.get(note, 0) + 1
    print(f"  P4 classes {m['classes']}")
    print(f"  P4 reasons {reasons}")
    zero = [r for r in data["carry"] if r["force_min"] is not None and r["force_min"] <= 0.0]
    esc = [r for r in data["carry"] if (r["clean_slip"] or 0.0) > 100.0
           and (r["fmax"] or 0.0) > 0.0]
    print(f"  P4/P7 loaded-slide: force_min==0 legs {len(zero)}, escapes (>100 mm with a "
          f"pinch) {len(esc)}, place-leg escapes "
          f"{sum(1 for r in esc if r['leg'].startswith('place'))}")
    return {"m": m, "data": data}


def descent_legs(path: str) -> list[dict]:
    """Every descent leg judged by **`105`'s own** parser and per-leg budget."""
    legs, _carries, _tally, dynamic = motion105.parse(path)
    out = []
    for index, leg in enumerate(legs, 1):
        peak = motion105.descent_profile_peak(leg["distance_cm"] / 100.0, dynamic)
        budget = (peak * motion105.ACHIEVED_MARGIN) if peak else motion105.REFERENCE_VMAX
        over = []
        if leg["v_max"] > budget:
            over.append(f"|v|max {leg['v_max']:.3f}>{budget:.3f}")
        out.append({"n": index, **leg, "budget": budget, "over": over})
    return out


def blocks(pairs) -> int:
    """The registered P91 table: C vs T per seed, then section 6's decision rule."""
    print("P91 - the take-off validation ramp on the shipped two-line")
    print("=" * 78)
    verdicts = {}
    for seed, control, treatment in pairs:
        c, t = cell(control), cell(treatment)
        cm, tm = c["m"], t["m"]
        ccyc, tcyc = c["data"]["cycles"], t["data"]["cycles"]
        c_grip, t_grip = _block(ccyc, "grip"), _block(tcyc, "grip")
        c_mean, t_mean = _mean(c_grip), _mean(t_grip)
        c_med, t_med = _p50(c_grip), _p50(t_grip)
        d_mean, d_med = t_mean - c_mean, t_med - c_med
        c_clean, t_clean = _clean(ccyc), _clean(tcyc)
        # P1b: the clean instances must not overlap (a constant 150-tick remainder)
        separated = bool(c_clean and t_clean and max(t_clean) < min(c_clean) - 0.25)
        d_clean = (max(t_clean) - min(c_clean)) if (t_clean and c_clean) else None
        d_interval = tm["pooled"]["mean"] - cm["pooled"]["mean"]
        # the attempt span is the cycle's own `total` (its segments sum to it):
        # the driver's `[run] attempt` window pairing slips when the two arms'
        # attempts complete out of order (T5: 6 adjacent rows), which is why the
        # span is never read from `span` here.
        c_span = _mean(_block(ccyc, "total"))
        t_span = _mean(_block(tcyc, "total"))
        print(f"\n## seed {seed}")
        print(f"  P1a grip block  C {fmt(c_mean)} mean / {fmt(c_med)} median "
              f"({fmt(c_med * 120, 0)} ticks)  ->  T {fmt(t_mean)} / {fmt(t_med)} "
              f"({fmt(t_med * 120, 0)} ticks)")
        print(f"      delta mean {fmt(d_mean)} s  median {fmt(d_med)} s   "
              f"(registered -0.300 +- 0.04)")
        print(f"  P1b clean instances  C {[round(v, 2) for v in c_clean]}  "
              f"T {[round(v, 2) for v in t_clean]}  -> "
              f"{'SEPARATED' if separated else 'OVERLAP'} "
              f"(max T - min C = {fmt(d_clean)} s)")
        print(f"  span            C {fmt(c_span)} -> T {fmt(t_span)} s   "
              f"(delta {fmt(t_span - c_span)})")
        print(f"  P2 interval     C {fmt(cm['pooled']['mean'])} -> "
              f"T {fmt(tm['pooled']['mean'])} s   delta {fmt(d_interval)}")
        print(f"      placed      C {cm['placed']}/{cm['attempts']} -> "
              f"T {tm['placed']}/{tm['attempts']}")
        print(f"      window      C {fmt(cm['window_rate'])} -> "
              f"{fmt(tm['window_rate'])} placed/min   batch {fmt(cm['batch_rate'])} -> "
              f"{fmt(tm['batch_rate'])}")
        for name, res in (("C", c), ("T", t)):
            st_ = res["m"].get("stats") or {}
            if st_.get("wall"):
                print(f"      wall {name} {fmt(st_['wall'], 1)} s  placed/min wall "
                      f"{fmt(60.0 * res['m']['placed'] / st_['wall'])}")
        p1a = abs(d_mean + 0.300) <= 0.04 and abs(d_med + 0.300) <= 0.04
        p1b = separated
        p2 = d_interval
        p2_state = ("falls" if p2 < -0.10 else
                    "rises" if p2 > 0.10 else "flat")
        print(f"  P1 {'PASS' if p1a else 'FAIL'}   P1b "
              f"{'PASS' if p1b else 'FAIL'}   P2 {p2_state} ({fmt(p2)} s)")
        verdicts[seed] = {"p1a": p1a, "p1b": p1b, "p2": p2, "p2_state": p2_state,
                          "d_mean": d_mean, "d_med": d_med, "d_interval": d_interval,
                          "c": c, "t": t}
    # ---- the decision rule (PREREG section 6) ----
    print("\n## verdict (PREREG section 6)")
    seeds = sorted(verdicts)
    p1a = all(v["p1a"] for v in verdicts.values())
    p1b = all(v["p1b"] for v in verdicts.values())
    states = [v["p2_state"] for v in verdicts.values()]
    deltas = [v["d_interval"] for v in verdicts.values()]
    clean = all(s == "falls" for s in states)
    trade = all(s in ("falls", "flat") for s in states) and not clean
    print(f"  P1a {'PASS' if p1a else 'FAIL'}  P1b {'PASS' if p1b else 'FAIL'}  "
          f"P2 {states} deltas {[round(d, 2) for d in deltas]}")
    if p1a and p1b and clean:
        print("  -> ADOPTION candidate (P3-P9 are read by the report's sections)")
    elif p1a and p1b and trade:
        print("  -> CONSIDERED TRADE (the block moves, the interval does not fall at "
              "both seeds and rises at neither; shipping needs the owner)")
    else:
        print("  -> NOT ADOPTED (PROBE_TWO_LINE_DEFAULT stays False)")
    return 0


def main(argv) -> int:
    logs = [a for a in argv[1:] if a.endswith(".log")]
    if argv[1:2] == ["--same"]:
        return show_same(argv[2], argv[3]) if len(argv) >= 4 else 2
    if argv[1:2] == ["--same-raw"]:
        return show_same(argv[2], argv[3], drop=False) if len(argv) >= 4 else 2
    if argv[1:2] == ["--profile"]:
        return show_profile(logs[0]) if logs else 2
    if argv[1:2] == ["--blocks"]:
        return blocks([
            (5, os.path.join(HERE, "C5.log"), os.path.join(HERE, "T5.log")),
            (6, os.path.join(HERE, "C6.log"), os.path.join(HERE, "T6.log")),
        ])
    if argv[1:2] == ["--cells"]:
        for path in logs:
            cell(path)
        return 0
    if argv[1:2] == ["--window"]:
        for path in logs:
            data = scan(path)
            resid = data["catchup"]
            print(f"\n== {path} ==")
            print(f"  catch-up residual n={len(resid)} median {fmt(_p50(resid), 1)} "
                  f"p90 {fmt(st.quantiles(resid, n=10)[8] if len(resid) > 1 else None, 1)} "
                  f"max {fmt(max(resid) if resid else None, 1)}")
            print(f"  approach end= n={len(data['approach'])} median "
                  f"{fmt(_p50([a['end'] for a in data['approach']]), 1)} max "
                  f"{fmt(max([a['end'] for a in data['approach']], default=None), 1)} mm")
            print(f"  grasp {sum(1 for r in data['results'] if r['grasped'])}/"
                  f"{len(data['results'])}")
        return 0
    if argv[1:2] == ["--pinch"]:
        for path in logs:
            data = scan(path)
            held = [r for r in data["carry"] if r["leg"] == "grasp_lift"
                    and (r["fmax"] or 0.0) > 0.0 and r["force_min"] is not None]
            print(f"\n== {path} ==")
            print(f"  held grasp_lift n={len(held)}  force_min median "
                  f"{fmt(_p50([r['force_min'] for r in held]))} N  min "
                  f"{fmt(min([r['force_min'] for r in held], default=None))}")
            print(f"  fmax median {fmt(_p50([r['fmax'] for r in held]))} N")
        return 0
    if argv[1:2] == ["--motion"]:
        for path in logs:
            legs = descent_legs(path)
            worst = max(legs, key=lambda leg: leg["v_max"] / (leg["budget"] or 1.0))
            over = [leg for leg in legs if leg["over"]]
            print(f"\n== {path} ==")
            print(f"  descents {len(legs)}  over budget {len(over)}  worst leg "
                  f"{worst['n']}: |v|max {fmt(worst['v_max'])} vs "
                  f"{fmt(worst['budget'])}  lurch {fmt(worst['a_max'] * motion105.CONTROL_DT, 3)}")
            for leg in over:
                print(f"    leg {leg['n']}: {', '.join(leg['over'])}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
