#!/usr/bin/env python3
"""P83 report: the fail-fast A/B (one parser, the P80 definition of every number).

    python3 logs/p83/p83_report.py                 # all five armed arms
    python3 logs/p83/p83_report.py --check         # exit 1 if a registered guard fails
    python3 logs/p83/p83_report.py C5 F5           # named arms

Every throughput endpoint comes from `logs/p80/p80lib.py` - the **same** parser
and the same wall definition (`[run] attempt 0` -> `[fruit] DONE` on the stamp
stream) that produced P80 §6 - so a P83 arm and a P80 arm are one measurement.
The fail-fast additions are read from the two line kinds the lever prints
(`[fail-fast]`) and the tracker already printed (`[carry]`).

Registered reads (`logs/p83/PREREG.md` §3-§6):

* **E1** pooled inter-placement interval (mean/p50/p90), **E2** placed/min on the
  placement window **and** the batch span, **E3** the failed attempt's cost in
  seconds *and* ticks (the lever's own mechanism), **E4** `s/attempt`, **E5** the
  placed attempts' span (a placement must not get slower), **E6** the count and
  class split (a draw), **E7** wall per pick / wall over sim, **E9** the
  aborted-leg audit, **E10** the `[cycle]` block the abort removes.
* **Guards**: G1 off-path byte-identity (C5 vs `logs/p80/S20.log`), G2 tracker
  neutrality (D vs C), G3 in-batch prefix identity (the treatment equals the
  control up to its first trip), G4 the trip only fires on a lost payload
  (`force = 0.00 N` or `contacts = 0` at the trip), G5 no placed attempt's leg
  was cut short, G6 no new failure reason, G8 the run accounted.
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

_spec = importlib.util.spec_from_file_location(
    "p80lib", os.path.join(HERE, "..", "p80", "p80lib.py"))
p80lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p80lib)
w6 = p80lib.w6

_spec = importlib.util.spec_from_file_location(
    "p82_report", os.path.join(HERE, "..", "p82", "p82_report.py"))
p82 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p82)

#: The seed-6 control is P80's own record (PREREG §2: same tree, no re-run).
CONTROL_OF_SEED = {5: os.path.join(HERE, "C5.log"), 6: os.path.join(ROOT, "logs/p80/S6.log")}
STAMP_OF_CONTROL = {5: os.path.join(HERE, "C5.stamps"), 6: os.path.join(ROOT, "logs/p80/S6.stamps")}
ARMS = {
    "C5": (5, "control replay (knob unset)"),
    "D5": (5, "tracker only (FRUIT_CARRY_DIAG=1)"),
    "F5": (5, "fail-fast 150 mm + tracker"),
    "D6": (6, "tracker only (FRUIT_CARRY_DIAG=1)"),
    "F6": (6, "fail-fast 150 mm + tracker"),
}

TRIP = re.compile(
    r"\[fail-fast\] (?P<side>\w+) (?P<leg>\w+): trip=t(?P<tick>\d+)/(?P<ticks>\d+) "
    r"clean_slip=(?P<slip>[\d.]+)mm >= (?P<thr>[\d.]+)mm "
    r"d=\((?P<dx>[+\-\d.]+),(?P<dy>[+\-\d.]+),(?P<dz>[+\-\d.]+)\)mm "
    r"sep=(?P<sep>[\d.]+)mm gap=(?P<gap>[\d.]+)mm "
    r"force=(?P<force>[\d.]+)N force_min=(?P<fmin>[\-\d.]+)N "
    r"contacts=(?P<contacts>\w+) onset_row=(?P<onset>\w+) loss_row=(?P<loss>\w+) "
    r"leg_left=(?P<left>\d+)"
)
CARRY = re.compile(
    r"\[carry\] (?P<side>\w+) (?P<leg>\w+): ticks=(?P<ticks>\d+)/(?P<total>\d+) "
    r"clean_slip_max=(?P<slip>[\d.]+)mm"
)
RUN_PICK = re.compile(r"\[run\] attempt (?P<n>\d+): picking ")
RUN_END = re.compile(
    r"\[run\] attempt (?P<n>\d+): grasped=(?P<g>\w+) placed=(?P<p>\w+) "
    r"lift=(?P<lift>[+\-\d.]+) m force=(?P<force>[\d.]+) N notes=(?P<notes>\[[^\]]*\]) "
    r"sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s")
STATS = re.compile(
    r"\[stats\] attempts=(?P<att>\d+) successes=(?P<ok>\d+) diverted=(?P<div>\d+)")

#: Diag-only line kinds the treatment prints and the shipped control cannot:
#: they are dropped from the prefix comparison (G3), never from the audit.
#: `[diag] carry-assist` is the W8-B block's own first-three-ticks row
#: (`FRUIT_CARRY_DIAG=1 ... and i < 3`), i.e. the tracker's own print.
DIAG_ONLY = ("[carry]", "[fail-fast]", "[diag] carry-assist")


def lines_of(path: str) -> list[str]:
    with open(path, encoding="utf-8", errors="ignore") as handle:
        return [ln.rstrip("\n") for ln in handle if "[fruit]" in ln]


def attempt_table(path: str) -> list[dict]:
    """The `[run] attempt` rows in order, with the carry legs each attempt ran."""
    rows: list[dict] = []
    current = None
    for line in lines_of(path):
        m = RUN_PICK.search(line)
        if m:
            current = {"slot": int(m.group("n")), "legs": [], "placed": None}
            rows.append(current)
            continue
        m = CARRY.search(line)
        if m and current is not None:
            current["legs"].append(
                {
                    "side": m.group("side"),
                    "leg": m.group("leg"),
                    "ticks": int(m.group("ticks")),
                    "total": int(m.group("total")),
                    "slip": float(m.group("slip")),
                    "cut": int(m.group("ticks")) < int(m.group("total")),
                }
            )
            continue
        m = RUN_END.search(line)
        if m:
            slot = int(m.group("n"))
            target = next((r for r in rows if r["slot"] == slot), None)
            if target is None:
                target = {"slot": slot, "legs": []}
                rows.append(target)
            target.update(
                grasped=m.group("g") == "True",
                placed=m.group("p") == "True",
                lift=float(m.group("lift")),
                force=float(m.group("force")),
                notes=m.group("notes"),
                t0=float(m.group("t0")),
                t1=float(m.group("t1")),
            )
            target["span"] = target["t1"] - target["t0"]
            current = None
    return rows


def trips_of(path: str) -> list[dict]:
    out = []
    for line in lines_of(path):
        m = TRIP.search(line)
        if m:
            row = m.groupdict()
            out.append(
                {
                    "side": row["side"],
                    "leg": row["leg"],
                    "tick": int(row["tick"]),
                    "ticks": int(row["ticks"]),
                    "slip": float(row["slip"]),
                    "thr": float(row["thr"]),
                    "sep": float(row["sep"]),
                    "gap": float(row["gap"]),
                    "force": float(row["force"]),
                    "fmin": float(row["fmin"]),
                    "contacts": row["contacts"],
                    "onset": row["onset"],
                    "loss": row["loss"],
                    "left": int(row["left"]),
                    "d": (float(row["dx"]), float(row["dy"]), float(row["dz"])),
                }
            )
    return out


def span_stats(values: list[float]) -> str:
    if not values:
        return "n=0"
    ordered = sorted(values)
    p90 = ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))]
    return (
        f"n={len(ordered)} mean {st.fmean(ordered):.2f}s "
        f"p50 {st.median(ordered):.2f}s p90 {p90:.2f}s "
        f"[{ordered[0]:.2f}-{ordered[-1]:.2f}]"
    )


def arm_block(name: str, path: str) -> dict:
    seed, label = ARMS[name]
    m = p80lib.metrics(path)
    table = attempt_table(path)
    trips = trips_of(path)
    executed = [r for r in table if r.get("placed") is not None]
    placed = [r for r in executed if r["placed"]]
    failed = [r for r in executed if not r["placed"]]

    print(f"\n=== {name} (seed {seed}) - {label}")
    print(f"    log={os.path.relpath(path, ROOT)}  [stats] "
          f"{m['attempts']} attempts, {m['placed']} placed")
    print(f"    E1 interval   mean {fmt(m['pooled']['mean'])}  p50 {fmt(m['pooled']['p50'])}"
          f"  p90 {fmt(m['pooled']['p90'])} s  (n={m['pooled']['n']})")
    print(f"    E2 placed/min window {fmt(m['window_rate'])}   batch {fmt(m['batch_rate'])}"
          f"   (window {fmt(m['window'])} s / batch {fmt(m['batch_span'])} s)")
    print(f"    E3 FAILED attempt span  {span_stats([r['span'] for r in failed])}"
          f"  = {fmt(120.0 * st.fmean([r['span'] for r in failed]) if failed else None)} ticks")
    print(f"    E5 PLACED attempt span  {span_stats([r['span'] for r in placed])}")
    print(f"    E4 s/attempt [stats] {fmt(m['stats']['per_attempt'])}   "
          f"E6 count {m['placed']}/{m['attempts']}"
          f"  classes {m['classes']}")
    print(f"    E6 reasons {m['reasons']}")
    print(f"    E7 wall/pick {fmt(m['stats']['wall_per_pick'])} s   "
          f"wall/sim {fmt(m['stats']['wall_over_sim'])}   "
          f"placed/min wall {fmt(60.0 * m['placed'] / m['stats']['wall'] if m['stats'].get('wall') else None)}")
    print(f"    E9 trips: {len(trips)}")
    for trip in trips:
        print(
            f"      {trip['leg']:10s} t{trip['tick']:>3}/{trip['ticks']:<3} "
            f"slip {trip['slip']:7.1f} mm  sep {trip['sep']:5.1f} gap {trip['gap']:5.1f}  "
            f"force {trip['force']:5.2f} N  contacts {trip['contacts']:>4}  "
            f"onset {trip['onset']:>4} loss {trip['loss']:>4}  "
            f"leg_left {trip['left']:>3} ticks  d=({trip['d'][0]:+.0f},{trip['d'][1]:+.0f},{trip['d'][2]:+.0f}) mm"
        )
    if trips:
        print(f"      legs tripped: "
              f"{ {t['leg'] for t in trips} }  skipped-leg ticks "
              f"mean {st.fmean([t['left'] + 50 for t in trips]):.1f}")
    cycles = w6.parse(path)["cycles"]
    if cycles:
        blocks: dict[str, list[float]] = {}
        for cycle in cycles:
            for nm, dur in cycle["blocks"]:
                blocks.setdefault(nm, []).append(dur)
        top = " ".join(
            f"{nm}={st.fmean(v):.2f}" for nm, v in blocks.items()
        )
        print(f"    E10 [cycle] means (all attempts): {top}")
    return {"metrics": m, "table": table, "trips": trips,
            "placed": placed, "failed": failed, "seed": seed}


def fmt(value, nd: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{nd}f}"


def physics_stream(path: str) -> list[str]:
    """Every `[fruit]` line except the diag-only kinds (the G2/G3 comparison).

    The tracker prints `[carry]` / `[diag] carry-assist` rows that the shipped
    path cannot print; dropping exactly those makes a tracker-only arm and the
    control comparable line for line, and it is the same stream G3 uses.
    """
    return [ln for ln in lines_of(path) if not any(k in ln for k in DIAG_ONLY)]


def prefix_check(control: str, treatment: str) -> tuple[bool, int, int]:
    """G3: the treatment equals the control up to its first trip.

    Returns (passes, common_prefix_lines, index_of_the_first_trip_in_the_prefix).
    Diag-only rows (`[carry]`, `[fail-fast]`) are dropped from the treatment's
    stream before comparing: they are the instrumentation, not the physics.
    """
    ref = lines_of(control)
    cand = [ln for ln in lines_of(treatment) if not any(k in ln for k in DIAG_ONLY)]
    index = next((i for i, (a, b) in enumerate(zip(ref, cand)) if a != b), min(len(ref), len(cand)))
    # how many *kept* treatment lines precede its first trip?
    kept, first_trip = 0, None
    for line in lines_of(treatment):
        if "[fail-fast]" in line:
            first_trip = kept
            break
        if not any(k in line for k in DIAG_ONLY):
            kept += 1
    if first_trip is None:
        return (index == len(cand) == len(ref), index, -1)
    return (first_trip <= index, index, first_trip)


def main() -> int:
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    check_mode = "--check" in sys.argv
    names = argv or list(ARMS)
    results = {}
    missing = []
    for name in names:
        path = os.path.join(HERE, f"{name}.log")
        if not os.path.exists(path):
            missing.append(name)
            continue
        results[name] = arm_block(name, path)
    if missing:
        print(f"\n[p83] arms not run yet: {missing}")

    # ---------------------------------------------------------------- guards
    print("\n=== guards (PREREG §5)")
    verdicts: dict[str, bool] = {}
    guards: list[str] = []

    def guard(name: str, cond: bool, detail: str) -> None:
        verdicts[name] = bool(cond)
        guards.append(f"{'PASS' if cond else 'FAIL'}  {name}: {detail}")

    c5 = os.path.join(HERE, "C5.log")
    if os.path.exists(c5):
        same = p82.fruit_stream(c5) == p82.fruit_stream(os.path.join(ROOT, "logs/p80/S20.log"))
        guard("G1 off-path inertness", same,
              f"C5 vs logs/p80/S20.log - {'IDENTICAL' if same else 'DIFFERS'} "
              f"({len(p82.fruit_stream(c5))} lines)")
    for diag, ctrl, seed in (("D5", "C5", 5), ("D6", None, 6)):
        path = os.path.join(HERE, f"{diag}.log")
        if not os.path.exists(path):
            continue
        ref = os.path.join(HERE, ctrl + ".log") if ctrl else CONTROL_OF_SEED[seed]
        if not os.path.exists(ref):
            continue
        same = physics_stream(path) == physics_stream(ref)
        guard(f"G2 tracker neutrality ({diag})", same,
              f"{diag} vs {os.path.relpath(ref, ROOT)} - "
              f"{'IDENTICAL' if same else 'DIFFERS'} "
              f"({len(physics_stream(path))} physics lines, diag rows dropped)")
    for trt in ("F5", "F6"):
        if trt not in results:
            continue
        seed = results[trt]["seed"]
        ctrl = CONTROL_OF_SEED[seed]
        ok, index, trip_at = prefix_check(ctrl, os.path.join(HERE, f"{trt}.log"))
        guard(f"G3 prefix identity ({trt})", ok,
              f"common prefix {index} lines, first trip at kept line {trip_at} "
              f"({'trip inside the prefix' if ok else 'DIVERGES BEFORE THE TRIP'})")
    for name, data in results.items():
        trips = data["trips"]
        if not trips:
            continue
        lost = all(t["force"] <= 0.01 or t["contacts"] in ("0", "None") for t in trips)
        weak = all(t["fmin"] <= 0.01 for t in trips)
        guard(f"G4 trip = lost payload ({name})", lost and weak,
              f"{len(trips)} trips; force=0.00 or contacts=0 on {sum(1 for t in trips if t['force'] <= 0.01 or t['contacts'] in ('0', 'None'))}"
              f"/{len(trips)}, force_min=0.00 on {sum(1 for t in trips if t['fmin'] <= 0.01)}/{len(trips)}")
        cut = [leg for row in data["placed"] for leg in row["legs"] if leg["cut"]]
        worst = max((leg["slip"] for row in data["placed"] for leg in row["legs"]), default=0.0)
        guard(f"G5 no placed leg shortened ({name})", not cut,
              f"{len(data['placed'])} placed attempts, {sum(len(r['legs']) for r in data['placed'])} carry legs, "
              f"{len(cut)} cut short, worst placed-leg clean_slip {worst:.1f} mm")
    if "C5" in results:
        base = set(results["C5"]["metrics"]["reasons"])
        for name in ("F5", "F6"):
            if name not in results:
                continue
            new = set(results[name]["metrics"]["reasons"]) - base
            guard(f"G6 no new failure reason ({name})", not new,
                  f"new reasons: {sorted(new) if new else 'none'}")
            lost = [r for r in results[name]["failed"] if not r["grasped"]]
            aborts = len(results[name]["trips"])
            guard(f"G6 aborted attempts score cnp ({name})",
                  all(r["grasped"] for r in results[name]["failed"] if r["notes"] == "[]"),
                  f"{aborts} trips, failed-with-cnp "
                  f"{sum(1 for r in results[name]['failed'] if r['grasped'])}/"
                  f"{len(results[name]['failed'])}, never-grasped {len(lost)}")
    for name, data in results.items():
        m = data["metrics"]
        accounted = m["attempts"] == m["placed"] + len(data["failed"])
        guard(f"G8 accounted ({name})", accounted,
              f"{m['attempts']} executed = {m['placed']} placed + {len(data['failed'])} failed")
    for line in guards:
        print(f"  {line}")

    # ------------------------------------------------------------- decisions
    print("\n=== registered decision (PREREG §6)")
    print("  M2 (failed-attempt cost) and T1 (interval) are printed against BOTH")
    print("  controls: C = the shipped instrumentation (P80's record at seed 6),")
    print("  D = the tracker-only arm (identical instrumentation to F, so the")
    print("  abort is the only difference; PREREG §1's registered fallback).")
    for seed in (5, 6):
        trt = f"F{seed}"
        if trt not in results:
            continue
        tm = results[trt]["metrics"]
        tf = [r["span"] for r in results[trt]["failed"]]
        for tag, ctrl_path, diag_path in (
            ("C", CONTROL_OF_SEED[seed], None),
            ("D", None, os.path.join(HERE, f"D{seed}.log")),
        ):
            ref = ctrl_path or diag_path
            if not ref or not os.path.exists(ref):
                continue
            cm = p80lib.metrics(ref)
            cf = [r["span"] for r in attempt_table(ref) if r.get("placed") is False]
            d_cost = (st.fmean(cf) - st.fmean(tf)) if cf and tf else None
            d_int = ((tm["pooled"]["mean"] - cm["pooled"]["mean"]) / cm["pooled"]["mean"] * 100.0
                     if tm["pooled"]["mean"] and cm["pooled"]["mean"] else None)
            print(f"  seed {seed}  F{seed} vs {tag} ({os.path.relpath(ref, ROOT)})")
            print(f"    M2 failed-attempt cost {fmt(st.fmean(cf) if cf else None)} -> "
                  f"{fmt(st.fmean(tf) if tf else None)} s "
                  f"(delta {fmt(d_cost)} s, bar >= 3.0 -> "
                  f"{'PASS' if (d_cost or 0) >= 3.0 else 'FAIL'})")
            if d_int is None:
                print("    T1 interval n/a")
            else:
                print(f"    T1 interval {fmt(cm['pooled']['mean'])} -> {fmt(tm['pooled']['mean'])} s "
                      f"({d_int:+.1f} %, bar <= -8 -> {'PASS' if d_int <= -8.0 else 'FAIL'})")
            print(f"    T2 count {cm['placed']}/{cm['attempts']} -> {tm['placed']}/{tm['attempts']}"
                  f"  (bar >= control-1 -> {'PASS' if tm['placed'] >= cm['placed'] - 1 else 'FAIL'})")
            print(f"    T3 window {fmt(cm['window_rate'])} -> {fmt(tm['window_rate'])}"
                  f"  batch {fmt(cm['batch_rate'])} -> {fmt(tm['batch_rate'])}"
                  f"  wall/pick {fmt(cm['stats']['wall_per_pick'])} -> {fmt(tm['stats']['wall_per_pick'])}")
    if check_mode and any(not v for v in verdicts.values()):
        print("\n[p83] CHECK FAILED")
        return 1
    if check_mode:
        print(f"\n[p83] CHECK PASSED ({len(verdicts)} guards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
