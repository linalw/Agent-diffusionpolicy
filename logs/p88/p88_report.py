#!/usr/bin/env python3
"""P88 readout: the two-line-scoped place raise - the gate's six clauses.

    python3 logs/p88/p88_report.py --predict logs/p87/T5.log logs/p87/T6.log
    python3 logs/p88/p88_report.py --blocks           # the registered table + verdict
    python3 logs/p88/p88_report.py --cells LOG...     # one cell's endpoints
    python3 logs/p88/p88_report.py --same REF CAND    # `[fruit]` stream, sealed filter
    python3 logs/p88/p88_report.py --same-raw REF CAND
    python3 logs/p88/p88_report.py --profile LOG      # the two profile rows
    python3 logs/p88/p88_report.py --landing LOG
    python3 logs/p88/p88_report.py --classes LOG      # the loaded-slide read, per arm/leg

Every delivered endpoint is P80's (`logs/p80/p80lib.py` -> `scripts/186_w6_report.py`):
a placement is the attempt's `t1`, the placement window is
`t_last_place - t_first_place`, the batch span is `t_last_end - t_first_start`,
and the wall comes from the `.stamps` stream. Nothing here re-derives a rate.

**P1 is a median** (P87's convention) and it is read two ways:

* P1a the `[cycle] place=` **block** median, against a prediction built from the
  **control's own** legs - for every control attempt the transit's tick count is
  re-generated at the treatment cap over that attempt's own printed distance
  (`[motion] carry placeX: NN cm`), and the non-transit remainder (the `place
  low` descent) is taken from the control itself. The prediction therefore
  follows the leg mix instead of assuming one.
* P1b the **per-leg** transit ticks and the commanded peak: `[motion] carry
  placeX` prints the leg's own distance, its tick count and `|v|cmd`, so the
  mechanism is checked on every leg (a cell that did not materialise would leave
  `|v|cmd` at 0.34).

**P6** reads every descent leg's `|v|max`/lurch out of `[motion] descent` rows and
names the worst leg per seed; the budget is `105`'s own (the shipped profile's
1.10x peak) and is not re-tuned here.

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

from fruit_sorting.motion import TrajectoryLimits, jerk_limited  # noqa: E402

#: P87's sealed filter plus **this phase's own row** (`[biarm] place profile:`).
#: The place row is the one line the flip is *expected* to move (a treatment cell
#: reads `=0.52(default)` where its control reads `=0.35(explicit)`), so it is
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
#: `[motion] carry place0: 55 cm, 364 ticks, |v|cmd=0.343 |a|cmd=0.348, ...`
PLACE_LEG = re.compile(
    r"\[motion\] carry (?P<leg>place\d+): (?P<cm>\d+) cm, (?P<ticks>\d+) ticks, "
    r"\|v\|cmd=(?P<v>[\d.]+) \|a\|cmd=(?P<a>[\d.]+)")
#: `[fruit] [carry] left place0: ticks=... force_min=... clean_slip_max=... fmax=...`
CARRY = re.compile(
    r"\[fruit\] \[carry\] (?P<arm>left|right) (?P<leg>\w+): (?P<rest>.*)$")
RELEASE_PROFILE = re.compile(
    r"\[fruit\] \[biarm\] release profile: (?P<label>\S+) scope=(?P<scope>\S+) "
    r"dwell=(?P<dwell>-?\d+) pad_hold=(?P<pad>\d+) "
    r"finger_hold=(?P<finger>\d+) \((?P<ticks>\d+) ticks; "
    r"shipped (?P<shipped>\d+), saved (?P<saved>-?\d+)\)")
PLACE_PROFILE = re.compile(
    r"\[fruit\] \[biarm\] place profile: (?P<label>\S+) scope=(?P<scope>\S+) "
    r"v_max=(?P<vmax>[\d.]+) a_max=(?P<amax>[\d.]+) "
    r"\((?P<ticks>-?\d+) ticks at (?P<distance>[\d.]+) m; "
    r"shipped (?P<shipped>-?\d+), saved (?P<saved>-?\d+)\)")
DISCHARGED = re.compile(r"\[belt\] .* discharged to the tray")


def fmt(value, nd: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value != value:  # nan
        return "nan"
    return f"{value:.{nd}f}"


def place_ticks(distance: float, v_max: float, a_max: float) -> int:
    """The profile clock a place leg of `distance` would run (the leg's own chain)."""
    limits = TrajectoryLimits(
        v_max=float(v_max), a_max=float(a_max),
        j_max=min(25.0, max(float(a_max) * 10.0, 1.0)), dt=1.0 / 120.0,
    )
    positions, _v, _a = jerk_limited(float(distance), limits)
    return int(len(positions))


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


def show_profile(path: str) -> int:
    """The two `[biarm] … profile:` rows, as the run printed them."""
    release = place = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if release is None and (m := RELEASE_PROFILE.search(line)):
                release = m.groupdict()
            if place is None and (m := PLACE_PROFILE.search(line)):
                place = m.groupdict()
    print(f"[profile] {path}")
    for name, row in (("release", release), ("place", place)):
        if row is None:
            print(f"  {name}: NO ROW (a non-bimanual log)")
            continue
        print(f"  {name}: {row['label']} scope={row['scope']} "
              + (f"dwell={row['dwell']} pad_hold={row['pad']} finger_hold={row['finger']} "
                 if name == "release" else f"v_max={row['vmax']} a_max={row['amax']} ")
              + f"({row['ticks']} ticks; shipped {row['shipped']}, saved {row['saved']})")
    return 0


def scan(path: str) -> dict:
    """`[cycle]` blocks paired to their arm, the windows, traces, legs, classes."""
    cycles: list[dict] = []
    pending: dict | None = None
    pending_place: dict | None = None
    last_carry: dict | None = None
    place_legs: list[dict] = []
    windows: list[dict] = []
    traces: list[dict] = []
    descents: list[dict] = []
    carry: list[dict] = []
    place_profiles: list[dict] = []
    release_profiles: list[dict] = []
    discharged = 0
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if m := RELEASE_PROFILE.search(line):
                release_profiles.append(m.groupdict())
                continue
            if m := PLACE_PROFILE.search(line):
                place_profiles.append(m.groupdict())
                continue
            if m := PLACE_LEG.search(line):
                leg = {"leg": m.group("leg"), "cm": int(m.group("cm")),
                       "ticks": int(m.group("ticks")),
                       "v": float(m.group("v")), "a": float(m.group("a")),
                       "arm": None}
                # the two-line arms interleave, so the leg names its arm through
                # the `[carry] <arm> placeX` row printed immediately before it.
                if last_carry is not None and last_carry["leg"] == leg["leg"]:
                    leg["arm"] = last_carry["arm"]
                place_legs.append(leg)
                continue
            if m := CARRY.search(line):
                rest = m.group("rest")
                row = {"arm": m.group("arm"), "leg": m.group("leg")}

                def num(key, cast=float):
                    found = re.search(rf"{key}=([+\-\d.]+|n/a)", rest)
                    if not found or found.group(1) == "n/a":
                        return None
                    try:
                        return cast(found.group(1))
                    except ValueError:
                        return None

                row["clean_slip"] = num("clean_slip_max")
                row["force_min"] = num("force_min")
                row["fmax"] = num("fmax")
                row["loss_row"] = num("loss_row", lambda s: int(float(s)))
                row["ticks"] = None
                found = re.search(r"ticks=(\d+)/(\d+)", rest)
                if found:
                    row["ticks"] = int(found.group(1))
                    row["ticks_total"] = int(found.group(2))
                carry.append(row)
                last_carry = row
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
                    "settle": None if settle == "nan" else float(settle),
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
    # Pair each attempt's place block with its own transit leg. Stream order is
    # not reliable (the two arms interleave between a leg and its cycle row), so
    # the pairing is **per arm**, in order: each arm's k-th place leg belongs to
    # that arm's k-th attempt that carries a place block.
    for arm in ("left", "right"):
        arm_cycles = [c for c in cycles if "place" in c["blocks"] and c["arm"] == arm]
        arm_legs = [leg for leg in place_legs if leg["arm"] == arm]
        for cycle, leg in zip(arm_cycles, arm_legs):
            cycle["place_leg"] = leg
    unpaired_cycles = [c for c in cycles if "place" in c["blocks"] and "place_leg" not in c]
    unpaired_legs = len([leg for leg in place_legs if leg["arm"]]) - sum(
        1 for c in cycles if c.get("place_leg") is not None)
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
            "descents": descents, "carry": carry, "place_legs": place_legs,
            "unpaired_cycles": len(unpaired_cycles),
            "unpaired_legs": max(0, unpaired_legs), "discharged": discharged,
            "release_profiles": release_profiles, "place_profiles": place_profiles,
            "worst_total_delta": worst, "arm_mismatches": len(mismatched)}


def _mean(values):
    return st.fmean(values) if values else None


def _p50(values):
    return st.median(values) if values else None


def _block(cycles: list[dict], name: str) -> list[float]:
    return [c["blocks"][name] for c in cycles if name in c["blocks"]]


def place_prediction(control: str, v_max: float = 0.52, a_max: float = 1.089) -> dict:
    """Per-attempt prediction of the treatment's place block, from the control.

    For every attempt that carries both a `[motion] carry placeX` row and a
    `[cycle] place=` block: `predicted = ticks(distance; v_max, a_max)/120 +
    (block - transit_ticks/120)`, i.e. the transit re-generated at the treatment
    cap over **that attempt's own printed distance**, with the `place low`
    remainder left as the control ran it (the cell does not touch that descent).
    """
    data = scan(control)
    pairs = []
    for cycle in data["cycles"]:
        leg = cycle.get("place_leg")
        if leg is None or "place" not in cycle["blocks"]:
            continue
        distance = leg["cm"] / 100.0
        rest = cycle["blocks"]["place"] - leg["ticks"] / 120.0
        predicted = place_ticks(distance, v_max, a_max) / 120.0 + rest
        pairs.append({"distance": distance, "control_ticks": leg["ticks"],
                      "control": cycle["blocks"]["place"], "rest": rest,
                      "predicted_ticks": place_ticks(distance, v_max, a_max),
                      "predicted": predicted, "arm": cycle["arm"]})
    return {"pairs": pairs,
            "control_median": _p50([p["control"] for p in pairs]),
            "predicted_median": _p50([p["predicted"] for p in pairs]),
            "control_mean": _mean([p["control"] for p in pairs]),
            "predicted_mean": _mean([p["predicted"] for p in pairs])}


def descent_legs(path: str) -> list[dict]:
    """Every descent leg judged by **`105`'s own** parser and per-leg budget."""
    legs, _carries, _tally, dynamic = motion105.parse(path)
    out = []
    for index, leg in enumerate(legs, 1):
        peak = motion105.descent_profile_peak(leg["distance_cm"] / 100.0, dynamic)
        budget = (peak * motion105.ACHIEVED_MARGIN) if peak else motion105.REFERENCE_VMAX
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


def classes(data: dict) -> dict:
    """The loaded-slide read, per arm and per carry-leg class (P74's classes).

    * **escaped** - `clean_slip_max > 100 mm` **with a pinch** (`fmax > 0`): a
      payload that left the jaws (P74's mechanism count; the `> 800 mm`
      threshold is *not* speed-invariant, so it is reported, never gated).
    * **never-held** - `fmax == 0`: no contact at all (the acquisition class).
    * **force-zero** - `force_min == 0`: the W8-B loaded-slide guard row.
    """
    out = {}
    for row in data["carry"]:
        key = f"{row['arm']}:{row['leg']}"
        slot = out.setdefault(key, {"n": 0, "escaped": 0, "never": 0, "zero": 0,
                                    "slip": [], "slip800": 0})
        slot["n"] += 1
        if (row["clean_slip"] or 0.0) > 800.0:
            slot["slip800"] += 1
        if row["fmax"] is None or row["fmax"] <= 0.0:
            slot["never"] += 1
            if (row["clean_slip"] or 0.0) > 100.0:
                slot["slip"].append(row["clean_slip"] or 0.0)
            continue
        if (row["clean_slip"] or 0.0) > 100.0:
            slot["escaped"] += 1
            slot["slip"].append(row["clean_slip"] or 0.0)
        if row["force_min"] is not None and row["force_min"] <= 0.0:
            slot["zero"] += 1
    return out


def cell(path: str) -> dict:
    m = p80lib.metrics(path)
    stats = m.get("stats") or {}
    data = scan(path)
    cycles = data["cycles"]
    released = [c for c in cycles if "release" in c["blocks"]]
    print(f"\n== {path} ==")
    for row, name in ((data["release_profiles"], "release"), (data["place_profiles"], "place")):
        if not row:
            print(f"  {name} profile: NO ROW (a non-bimanual log)")
            continue
        p = row[0]
        if name == "release":
            print(f"  release profile {p['label']} scope={p['scope']} -> "
                  f"{p['dwell']}/{p['pad']}/{p['finger']} ({p['ticks']} ticks, "
                  f"shipped {p['shipped']}, saved {p['saved']})")
        else:
            print(f"  place profile   {p['label']} scope={p['scope']} -> "
                  f"v_max={p['vmax']} a_max={p['amax']} ({p['ticks']} ticks at "
                  f"{p['distance']} m; shipped {p['shipped']}, saved {p['saved']})")
    print(f"  [cycle] rows {len(cycles)}  [run] windows {len(data['windows'])}  "
          f"paired {len(released)} with a release block  "
          f"worst |total-window| {fmt(data['worst_total_delta'])} s  "
          f"arm mismatches {data['arm_mismatches']}")
    print(f"  placed {m['placed']}/{m['attempts']} = {100.0 * (m['rate'] or 0):.1f} %   "
          f"s/attempt {fmt(stats.get('per_attempt'))}   sim {fmt(stats.get('sim_total'))} s")
    if stats.get("biarm"):
        b = stats["biarm"]
        print(f"  per arm  left {b['l']}/{b['la']}   right {b['r']}/{b['ra']}   "
              f"pipelined slots {b['slots']}   biarm {b['rate']} fruits/min")
    print("  blocks (mean s; n in brackets):")
    print("   " + "  ".join(f"{name}={fmt(_mean(_block(cycles, name)))}"
                            f"[{len(_block(cycles, name))}]" for name in
                            ["prepose", "hover", "descent", "close", "grip", "lift",
                             "place", "release", "return", "end", "total"]))
    print(f"  place block  mean {fmt(_mean(_block(cycles, 'place')))} s   "
          f"MEDIAN {fmt(_p50(_block(cycles, 'place')))} s")
    # the per-leg mechanism: each place transit's own distance against its ticks
    legs = [c["place_leg"] for c in cycles if c.get("place_leg")]
    if legs:
        errors = []
        for leg in legs:
            want = place_ticks(leg["cm"] / 100.0, 0.35, 1.089)
            errors.append(leg["ticks"] - want)
        print(f"  place transits {len(legs)}  cm {min(l['cm'] for l in legs)}"
              f"-{max(l['cm'] for l in legs)}  |v|cmd "
              f"{fmt(min(l['v'] for l in legs), 3)}..{fmt(max(l['v'] for l in legs), 3)}  "
              f"ticks vs the profile at the leg's own cm: median error "
              f"{fmt(_p50(errors), 1)} ticks (max |{max(abs(e) for e in errors)}|)")
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
    traces = data["traces"]
    if traces:
        guests = [t for t in traces if t["bottom"] >= 0.0]
        print(f"  landing: {len(traces)} traces, {len(guests)} payload-present, "
              f"on_belt {sum(1 for t in guests if t['on_belt'])}/{len(guests)}"
              f"   discharged {data['discharged']}")
        if guests:
            print(f"    release_bottom {fmt(min(t['bottom'] for t in guests), 1)}"
                  f"..{fmt(max(t['bottom'] for t in guests), 1)} mm   "
                  f"impact {fmt(min(t['impact'] for t in guests))}"
                  f"..{fmt(max(t['impact'] for t in guests))} m/s   "
                  f"bounce <= {fmt(max(t['bounce'] for t in guests), 1)} mm   "
                  f"upstream-lost {len(traces) - len(guests)}")
    else:
        print("  landing: no place traces (FRUIT_PLACE_TRACE off)")
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
    table = classes(data)
    print("  classes (per arm:leg; escaped = clean_slip>100 mm with a pinch):")
    for key in sorted(table):
        row = table[key]
        print(f"    {key}: n={row['n']} escaped={row['escaped']} "
              f"never-held={row['never']} force_min==0={row['zero']} "
              f"slip>800={row['slip800']}  slip "
              + (f"{fmt(min(row['slip']), 1)}..{fmt(max(row['slip']), 1)} mm"
                 if row["slip"] else "-"))
    print(f"  reasons {m['reasons']}")
    return {"m": m, "data": data, "descents": descents, "classes": table}


def blocks() -> int:
    print("P88 - the place raise as a two-line-scoped default (PREREG S5)")
    print("=" * 78)
    verdicts = {}
    pairs = (("5", "logs/p88/C5.log", "logs/p88/T5.log"),
             ("6", "logs/p88/C6.log", "logs/p88/T6.log"))
    for seed, control, treatment in pairs:
        c, r = cell(control), cell(treatment)
        cm, rm = c["m"], r["m"]
        pred = place_prediction(control)
        ccyc = [x for x in c["data"]["cycles"] if "place" in x["blocks"]]
        rcyc = [x for x in r["data"]["cycles"] if "place" in x["blocks"]]
        c_p50, r_p50 = _p50(_block(ccyc, "place")), _p50(_block(rcyc, "place"))
        d_p50 = (r_p50 or 0.0) - (c_p50 or 0.0)
        d_pred = (pred["predicted_median"] or 0.0) - (pred["control_median"] or 0.0)
        d_interval = rm["pooled"]["mean"] - cm["pooled"]["mean"]
        print(f"\n## seed {seed}")
        print(f"  P1a place block MEDIAN  C {fmt(c_p50, 3)} s -> T {fmt(r_p50, 3)} s   "
              f"delta {fmt(d_p50, 3)} s   predicted delta {fmt(d_pred, 3)} s "
              f"(control legs re-generated at 0.52)   band +-0.12 s")
        print(f"  report: place block MEAN  C {fmt(_mean(_block(ccyc, 'place')), 3)} -> "
              f"T {fmt(_mean(_block(rcyc, 'place')), 3)}   predicted mean delta "
              f"{fmt((pred['predicted_mean'] or 0.0) - (pred['control_mean'] or 0.0), 3)} s")
        # P1b (PREREG A1): the per-leg mechanism - ticks and `|v|cmd` against the
        # profile re-generated at the raised cap from the leg's own printed cm.
        rlegs = [x["place_leg"] for x in rcyc if x.get("place_leg")]
        clegs = [x["place_leg"] for x in ccyc if x.get("place_leg")]
        if rlegs and clegs:
            rv = [l["v"] for l in rlegs]
            cv = [l["v"] for l in clegs]
            err = [l["ticks"] - place_ticks(l["cm"] / 100.0, 0.52, 1.089) for l in rlegs]
            peak_err = []
            regimes = {"long": 0, "accel": 0, "jerk": 0}
            contrast = []
            for leg in rlegs:
                d = leg["cm"] / 100.0
                raise_ticks = place_ticks(d, 0.52, 1.089)
                ship_ticks = place_ticks(d, 0.35, 1.089)
                peak_err.append(leg["v"] - 1.875 * d / (leg["ticks"] / 120.0))
                regimes["long" if ship_ticks < raise_ticks and d >= 0.408
                        else ("accel" if ship_ticks > raise_ticks else "jerk")] += 1
                if 1.875 * d / (raise_ticks / 120.0) >= 0.45:
                    contrast.append(leg["v"])
            print(f"  P1b |v|cmd  C {fmt(min(cv), 3)}-{fmt(max(cv), 3)} -> "
                  f"T {fmt(min(rv), 3)}-{fmt(max(rv), 3)} (median {fmt(_p50(rv), 3)})   "
                  f"regimes long/accel/jerk {regimes['long']}/{regimes['accel']}/{regimes['jerk']}")
            print(f"       ticks vs the profile at 0.52 from each leg's own cm: median "
                  f"{fmt(_p50(err), 1)}, max |{max(abs(e) for e in err)}|   "
                  f"|v|cmd - 1.875 d/(ticks/120): max |{fmt(max(abs(e) for e in peak_err), 3)}|   "
                  f"legs with a raised prediction >= 0.45: "
                  f"{len(contrast)} (min |v|cmd {fmt(min(contrast), 3) if contrast else '-'})")
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
              f"   window {fmt(cm['window_rate'])} -> {fmt(rm['window_rate'])} placed/min"
              f"   batch {fmt(cm['batch_rate'])} -> {fmt(rm['batch_rate'])}")
        cw = (cm["stats"] or {}).get("wall")
        rw = (rm["stats"] or {}).get("wall")
        if cw and rw:
            print(f"  P5 wall  C {fmt(cw, 1)} s -> T {fmt(rw, 1)} s   "
                  f"placed/min wall {fmt(60.0 * cm['placed'] / cw)} -> "
                  f"{fmt(60.0 * rm['placed'] / rw)}")
        # P3 the landing
        def land(cellres):
            guests = [t for t in cellres["data"]["traces"] if t["bottom"] >= 0.0]
            return len(guests), sum(1 for t in guests if t["on_belt"])

        cg, cok = land(c)
        rg, rok = land(r)
        print(f"  P3 landing  C {cok}/{cg} on belt -> T {rok}/{rg} on belt")
        # P4 the class read (per arm:leg, both cells)
        def totals(cellres):
            agg = {"escaped": 0, "never": 0, "zero": 0, "left_escaped": 0,
                   "left_zero": 0, "place_escaped": 0, "left_place_escaped": 0,
                   "place_legs": 0}
            for key, row in cellres["classes"].items():
                arm, leg = key.split(":")
                agg["escaped"] += row["escaped"]
                agg["never"] += row["never"]
                agg["zero"] += row["zero"]
                if arm == "left":
                    agg["left_escaped"] += row["escaped"]
                    agg["left_zero"] += row["zero"]
                if leg.startswith("place"):
                    agg["place_legs"] += row["n"]
                    agg["place_escaped"] += row["escaped"]
                    if arm == "left":
                        agg["left_place_escaped"] += row["escaped"]
            return agg

        ct, rt = totals(c), totals(r)
        print(f"  P4 class  escaped {ct['escaped']} -> {rt['escaped']} "
              f"(left {ct['left_escaped']} -> {rt['left_escaped']}, "
              f"place-legs {ct['place_escaped']}/{ct['place_legs']} -> "
              f"{rt['place_escaped']}/{rt['place_legs']})   "
              f"never-held {ct['never']} -> {rt['never']}   "
              f"force_min==0 {ct['zero']} -> {rt['zero']}")
        new_reasons = {k: v for k, v in rm["reasons"].items() if k not in cm["reasons"]}
        print(f"     new reason keys {new_reasons or 'none'}")
        # P6 the descent budgets (per cell), reported here and gated in gates.sh
        for tag, res in (("C", c), ("T", r)):
            over = [d for d in res["descents"] if d["over"]]
            print(f"  P6 {tag}: {len(res['descents'])} descent legs, {len(over)} over budget"
                  + (f" -> legs {[d['n'] for d in over]}" if over else ""))
        # P1b (PREREG A1): the cell materialised on every treatment leg.
        p1b = False
        if rlegs:
            p1b = (abs(_p50(err) or 0.0) <= 3.0
                   and max(abs(e) for e in peak_err) <= 0.02
                   and (_p50(rv) or 0.0) >= 0.48
                   and (not contrast or min(contrast) >= 0.45))
        # verdict, per PREREG S5
        p1a = abs(d_p50 - d_pred) <= 0.12 and d_p50 < 0.0
        both_arms = all(
            ((rm["per_arm"].get(a) or {}).get("interval_mean") or 0.0)
            <= ((cm["per_arm"].get(a) or {}).get("interval_mean") or 0.0)
            for a in ("left", "right")
        ) if cm["per_arm"] and rm["per_arm"] else False
        p2 = d_interval < 0.0
        p3 = (rg == 0) or (rok == rg)
        p4 = (not new_reasons) and (rt["left_escaped"] - ct["left_escaped"] < 4) \
            and (rt["escaped"] - ct["escaped"] < 5)
        print(f"  -> P1a {'PASS' if p1a else 'FAIL'}  P1b {'PASS' if p1b else 'FAIL'}  "
              f"P2 {'PASS' if p2 else 'FAIL'} (per-arm down {both_arms})  "
              f"P3 {'PASS' if p3 else 'FAIL'}  P4 {'PASS' if p4 else 'FAIL'}")
        verdicts[seed] = {"p1a": p1a, "p1b": p1b, "p2": p2, "p3": p3, "p4": p4,
                          "per_arm": both_arms, "d_p50": d_p50, "d_pred": d_pred,
                          "d_interval": d_interval, "landing": f"{rok}/{rg}",
                          "escaped": f"{ct['escaped']}->{rt['escaped']}",
                          "control_totals": ct, "treatment_totals": rt}
    print("\n" + "=" * 78)
    # P4b is a **pooled** clause (PREREG §3): place-leg escapes over both seeds
    # (<= 3) and the left's (<= 2). The per-seed line above is the report.
    pooled_c = sum(v["control_totals"]["place_legs"] for v in verdicts.values())
    pooled_t = sum(v["treatment_totals"]["place_legs"] for v in verdicts.values())
    place_c = sum(v["control_totals"]["place_escaped"] for v in verdicts.values())
    place_t = sum(v["treatment_totals"]["place_escaped"] for v in verdicts.values())
    left_place_t = sum(v["treatment_totals"]["left_place_escaped"]
                       for v in verdicts.values())
    p4b = place_t <= 3 and left_place_t <= 2
    print(f"P4b pooled place-leg escapes: control {place_c}/{pooled_c}, "
          f"treatment {place_t}/{pooled_t} (left {left_place_t}) -> "
          f"{'PASS' if p4b else 'FAIL'}")
    ok = all(all(v[k] for k in ("p1a", "p1b", "p2", "p3", "p4")) for v in verdicts.values()) \
        and p4b
    for seed, v in verdicts.items():
        print(f"seed {seed}: place delta {fmt(v['d_p50'], 3)} s (predicted "
              f"{fmt(v['d_pred'], 3)}), interval {fmt(v['d_interval'], 2)} s, "
              f"landing {v['landing']}, escaped {v['escaped']}, "
              f"per-arm down {v['per_arm']}")
    print(f"P88 gate: {'PASS' if ok else 'FAIL'} "
          f"({'the scoped default may ship' if ok else 'do not flip'})")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "--same":
        return show_same(argv[2], argv[3])
    if cmd == "--same-raw":
        return show_same(argv[2], argv[3], drop=False)
    if cmd == "--profile":
        return max(show_profile(p) for p in argv[2:])
    if cmd == "--predict":
        rc = 0
        for path in argv[2:]:
            pred = place_prediction(path)
            n = len(pred["pairs"])
            print(f"[predict] {path}: {n} place attempts   block median "
                  f"{fmt(pred['control_median'], 3)} -> {fmt(pred['predicted_median'], 3)} s "
                  f"(delta {fmt((pred['predicted_median'] or 0) - (pred['control_median'] or 0), 3)})   "
                  f"mean {fmt(pred['control_mean'], 3)} -> {fmt(pred['predicted_mean'], 3)} "
                  f"(delta {fmt((pred['predicted_mean'] or 0) - (pred['control_mean'] or 0), 3)})")
            legs = sorted(p["distance"] for p in pred["pairs"])
            print(f"           distances {fmt(legs[0], 2)}-{fmt(legs[-1], 2)} m   "
                  f"transit ticks {min(p['control_ticks'] for p in pred['pairs'])}-"
                  f"{max(p['control_ticks'] for p in pred['pairs'])} shipped")
        return rc
    if cmd == "--landing":
        rc = 0
        for path in argv[2:]:
            data = scan(path)
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
            data = scan(path)
            table = classes(data)
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
