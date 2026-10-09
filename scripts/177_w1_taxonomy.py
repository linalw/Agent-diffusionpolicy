#!/usr/bin/env python3
"""W1 failure taxonomy: per-attempt classes from a log + its trace directories.

    python3 scripts/177_w1_taxonomy.py logs/w1/10_tax_single.log \\
        --traces logs/w1/dyn_single --catch logs/w1/catch_single
    python3 scripts/177_w1_taxonomy.py logs/w1/11_tax_twoline.log \\
        --traces logs/w1/dyn_twoline --catch logs/w1/catch_twoline
    python3 scripts/177_w1_taxonomy.py --self-test

Read-only: parses the `[run]`/`[biarm]`/`[task]`/`[motion]` lines and the
opt-in `FRUIT_DYNAMIC_TRACE=1` / `FRUIT_CATCH_TRACE=1` JSON rows that run wrote.
For every attempt it reports the fruit, arm, outcome, the catch geometry
(handover lead, descent intercept, catch-up residual), the close geometry
(close-start offset, force, span, cross-belt motion), the in-hand slide during
the carry legs (payload displacement in the tool frame), the onset tick of the
failure, and - from the catch trace - the joint-2 trajectory and how many
ticks the IK command hit a joint limit.

The failure class comes from the *lift* leg first: a payload lost during the
lift (including after a failed probe whose re-seat kept the gap but did not
re-establish a load-bearing grip) is reported by the lift's `clearance:
lowest payload point` and slip / in-hand |v|, while the later place legs only
echo the already-lost payload. The single-arm log carries that evidence in its
own `[motion] carry` lines; a biarm log interleaves the two arms' legs without
an arm tag, so per-attempt evidence there comes from `--traces` (the trace-on
run is proven non-perturbing). With no evidence the class is `unknown`.

Classes:
  catch-miss      the catch-up/grasp never met the fruit
  lift-loss       grasp closed with contact but the payload left during the
                  lift - including the re-seat-does-not-re-establish case
  place-escape    payload held through the lift but left during a place leg
  place-miss      payload held to the release but placed=False (geometry)
  no-trigger      the wait loop never saw the fruit inside the window
  unknown         no per-attempt evidence (trace-less biarm; pass --traces)
  other           everything else (includes a held-not-placed with no drift)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re

RE_ATTEMPT = re.compile(
    r"\[run\] attempt (\d+)(?: \(([a-z]+)\))?: picking (\S+) grade (\S+)"
    r"(?: into output lane (\d+))?(?:.*?sim=([\d.]+)-([\d.]+)s)?"
)
#: The bimanual driver prints the outcome lines *after* the batch, in the sorted
#: (`sim_start`) order: `[run] attempt N (arm): grasped=... sim=X-Ys`.
RE_TRACE_DUMP = re.compile(
    r"\[trace\] scripted (left|right) (ok|fail): (\d+) rows -> (\S+)"
)
RE_RESULT_RUN_SORTED = re.compile(
    r"\[run\] attempt (\d+) \(([a-z]+)\): grasped=(\w+) placed=(\w+) "
    r"lift=([+-][\d.]+) m force=([\d.]+) N sim=([\d.]+)s notes=(\[.*\])"
)
RE_RESULT_BI = re.compile(
    r"\[biarm\] result (left|right) index=(-?\d+) (\S+) grasped=(\w+) placed=(\w+) "
    r"lift=([+-][\d.]+) force=([\d.]+) sim=([\d.]+)s notes=(\[.*\])"
)
RE_RESULT_RUN = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+-][\d.]+) m "
    r"force=([\d.]+) N notes=(\[.*\])"
)
RE_HANDOVER = re.compile(
    r"intercept handover: fruit_y=([+-][\d.]+) dy=([+-][\d.]+) m lead=([\d.]+) m"
)
RE_DESCENT = re.compile(
    r"dynamic descent: waited (\d+) ticks, intercept=([+-][\d.]+) m "
    r"\(station ([+-][\d.]+), shift ([+-][\d.]+) m\), fruit dy=([+-][\d.]+) m, "
    r"deadline=([\d.]+) m, t_desc=([\d.]+) s"
)
RE_CATCHUP = re.compile(r"dynamic catch-up: residual=([\d.]+) mm")
RE_LIFT = re.compile(r"lift ([+-][\d.]+) m, grasped=(\w+)")
RE_STATION_FRUIT = re.compile(r"fruit left the pick station during the close \(([\d.]+) mm\)")
RE_REGRASP = re.compile(
    r"dynamic regrasp: re-seated (?:in place|on the moving fruit)"
)
RE_CLEARANCE = re.compile(
    r"\[motion\] carry (grasp_lift|place[01]) clearance: lowest payload point "
    r"([+-][\d.]+) mm to the (.*)"
)
RE_DIVERT = re.compile(r"diverting (\S+) \(index (\d+)\)")
RE_CARRY = re.compile(
    r"\[motion\] carry (grasp_lift|place[01]): [\d.]+ cm, (\d+) ticks, "
    r".*?slip_max=([\d.]+) mm, in-hand \|v\|max=([\d.]+) m/s.*?cone=([\d.]+)x"
)
RE_DYN_CLOSE = re.compile(
    r"dynamic close: sustained contact after (\d+) ticks \(force=([\d.]+) N, "
    r"span=([\d.]+) mm\); freezing the closing command at ([\d.]+) mm"
)
RE_STATS = re.compile(r"\[stats\] attempts=(\d+) successes=(\d+)")
RE_INDEXED = re.compile(r"indexed:")


def load_traces(directory: str):
    """Return a list of trace recordings: {key, name, arm, rows}.

    Two writers exist in the tree:
    * `_dynamic_trace_flush` writes `dynamic_trace_NN.json` (attempt index);
    * `_dynamic_trace_dump` (the public `grasp_carry_place` wrapper) writes
      `trace_NN_<arm>_<mode>_<outcome>.json` (1-based sequence).
    Both are accepted; the caller points `--traces` at either directory.
    """
    out = []
    if not directory:
        return out
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        base = os.path.basename(path)
        if base.endswith("_summary.json"):
            continue
        match = re.search(r"dynamic_trace_(\d+)\.json", base)
        key = int(match.group(1)) if match else None
        if key is None:
            match = re.match(r"trace_(\d+)_.*\.json", base)
            key = int(match.group(1)) - 1 if match else None
        if key is None:
            continue
        arm = None
        for side in ("left", "right"):
            if f"_{side}_" in base:
                arm = side
        try:
            with open(path, encoding="utf-8") as handle:
                rows = json.load(handle)
            rows = rows.get("rows", []) if isinstance(rows, dict) else rows
        except (OSError, ValueError):
            continue
        out.append({"key": key, "name": base, "arm": arm, "rows": rows})
    return out


def load_catch(directory: str):
    """Return the catch-trace files as a list of (path, rows), name-sorted."""
    out = []
    if not directory:
        return out
    for path in sorted(glob.glob(os.path.join(directory, "catch_*.json"))):
        try:
            with open(path, encoding="utf-8") as handle:
                out.append((os.path.basename(path), json.load(handle)))
        except (OSError, ValueError):
            continue
    return out


def hand_slide(rows, phase: str, ref_mode: str = "first"):
    """Max tool-frame payload displacement within `phase` rows [m], and t of onset.

    `ref_mode='first'`: reference is the first row of the phase (what the carry
    legs call slip). The onset time is the first row where the displacement
    exceeds 10 mm.
    """
    subset = [r for r in rows if r.get("phase") == phase]
    if not subset:
        return None, None
    ref = subset[0]["hand_rel"]
    peak, onset = 0.0, None
    for row in subset:
        rel = row["hand_rel"]
        d = sum((float(a) - float(b)) ** 2 for a, b in zip(rel, ref)) ** 0.5
        if d > peak:
            peak = d
        if onset is None and d > 0.010:
            onset = float(row["t"])
    return peak, onset


def catch_geometry(rows, catch_rows, log_catchup):
    """Catch/close geometry from one attempt's dynamic trace rows."""
    info = {}
    close = [r for r in rows if r.get("phase") == "close"]
    if close:
        o = close[0]["offset"]
        info["close_offset_mm"] = [round(float(v) * 1000.0, 1) for v in o]
        info["close_t"] = float(close[0]["t"])
        info["force_max"] = max(float(r.get("force", 0.0)) for r in rows)
        info["sep_min"] = min(float(r["sep"]) for r in close)
        dx = float(close[-1]["fruit"][0]) - float(close[0]["fruit"][0])
        info["close_dx_mm"] = round(dx * 1000.0, 1)
        info["close_vx0"] = round(float(close[0].get("fruit_vel", [0, 0, 0])[0]), 4)
    if log_catchup is not None:
        info["catchup_residual_mm"] = log_catchup
    if catch_rows:
        q2 = [float(r["q_cmd"][1]) for r in catch_rows if r.get("q_cmd")]
        clipped = [r for r in catch_rows if r.get("limit_clipped")]
        info["catch_ticks"] = len(catch_rows)
        info["catch_clipped"] = len(clipped)
        info["catch_q2_start"] = round(q2[0], 4) if q2 else None
        info["catch_q2_end"] = round(q2[-1], 4) if q2 else None
        info["catch_q2_min"] = round(min(q2), 4) if q2 else None
        info["catch_q2_max"] = round(max(q2), 4) if q2 else None
        info["catch_err_end_mm"] = round(
            float(catch_rows[-1]["error6_norm"]) * 1000.0, 1
        )
        info["catch_t0"] = float(catch_rows[0]["sim_time"])
        info["catch_t1"] = float(catch_rows[-1]["sim_time"])
    return info


#: Classification thresholds. The lift leg is the honest witness: after a
#: failed probe the re-seat can keep the pads on the moving fruit but not
#: re-establish a load-bearing grip, and the place legs then only report the
#: already-lost payload. A lift whose lowest payload point reaches the surface
#: it is carried over (`clearance <= 0`: the fruit is resting on the belt, and
#: -1.3 m means the floor) lost the payload *there*; a small negative
#: clearance on its own can be the seat (the P2-3 note), so the near-surface
#: case also wants a slip far beyond any held carry. A trace-only record (no
#: clearance) needs both a large slip and a large in-hand speed.
CARRY_SLIP_MM = 50.0
LIFT_CLEARANCE_LOST_MM = -10.0
LIFT_SLIP_LOST_MM = 150.0
LIFT_INHAND_LOST_M_S = 0.25


def _mm(value) -> str:
    return f"{value:.0f}" if value is not None else "-"


def lift_evidence(rec) -> dict:
    """The attempt's lift-leg evidence, from the log and/or the trace rows.

    Returns `{slip_mm, in_hand, clearance_mm, where, regrasps}`; a field is
    None when no source carried it. `slip_mm` is the largest lift-leg slip
    over the `[motion] carry` lines and the trace's hand-frame displacement;
    `clearance_mm` is the smallest `lowest payload point` the lift reported.
    """
    lifts = [c for c in rec.get("carry", []) if c.get("leg") == "grasp_lift"]
    slips = [float(c.get("slip_max_mm", 0.0)) for c in lifts]
    speeds = [float(c.get("inh_speed", 0.0)) for c in lifts]
    clears = [c for c in rec.get("clearance", []) if c.get("leg") == "grasp_lift"]
    trace = rec.get("carry_slide", {}).get("grasp_lift")
    if trace and trace[0] is not None:
        slips.append(float(trace[0]) * 1000.0)
    if not slips and not clears:
        return {
            "slip_mm": None,
            "in_hand": None,
            "clearance_mm": None,
            "where": None,
            "regrasps": rec.get("regrasps", 0),
        }
    clearance = min(float(c["mm"]) for c in clears) if clears else None
    where = None
    if clearance is not None:
        where = next(
            (c["where"] for c in clears if float(c["mm"]) == clearance), None
        )
    return {
        "slip_mm": max(slips) if slips else None,
        "in_hand": max(speeds) if speeds else None,
        "clearance_mm": clearance,
        "where": where,
        "regrasps": rec.get("regrasps", 0),
    }


def lift_lost(rec):
    """True when the lift leg shows the payload left the grip; None if unknown."""
    ev = lift_evidence(rec)
    clear, slip = ev["clearance_mm"], ev["slip_mm"]
    if clear is None and slip is None:
        return None
    if clear is not None and clear <= LIFT_CLEARANCE_LOST_MM:
        return True
    if (
        clear is not None
        and clear <= 0
        and slip is not None
        and slip > LIFT_SLIP_LOST_MM
    ):
        return True
    if (
        clear is None
        and slip is not None
        and slip > LIFT_SLIP_LOST_MM
        and ev["in_hand"] is not None
        and ev["in_hand"] > LIFT_INHAND_LOST_M_S
    ):
        return True
    return False


def classify(rec):
    grasped = rec.get("grasped")
    placed = rec.get("placed")
    notes = " ".join(rec.get("notes", []))
    if "never settled" in notes or "no fruit left" in notes:
        return "no-trigger"
    if "already passed" in notes:
        return "no-trigger"
    if "left the pick station" in notes:
        return "catch-miss"
    if grasped and placed:
        return "ok"
    # A failed attempt is judged on its lift first: the place legs of a payload
    # lost there only report the post-loss slide.
    if lift_lost(rec):
        return "lift-loss"
    if not grasped:
        residual = rec.get("catchup_residual_mm")
        if residual is not None and residual > 12.0:
            return "catch-miss"
        return "lift-loss"
    place_logs = [c for c in rec.get("carry", []) if c["leg"].startswith("place")]
    place_trace = [
        rec.get("carry_slide", {}).get(p, (None, None))[0]
        for p in ("place0", "place1")
    ]
    if not place_logs and not any(v is not None for v in place_trace):
        # No per-attempt evidence at all (a trace-less biarm log: the two
        # arms' interleaved legs are not text-attributable). Say so rather
        # than inventing a place class.
        return "unknown"
    slide = max(
        [float(c["slip_max_mm"]) / 1000.0 for c in place_logs]
        + [float(v or 0.0) for v in place_trace]
        + [0.0]
    )
    return "place-escape" if slide > CARRY_SLIP_MM / 1000.0 else "place-miss"


def _case(**kw) -> dict:
    rec = {
        "notes": [],
        "carry": [],
        "clearance": [],
        "carry_slide": {},
        "catchup_residual_mm": None,
    }
    rec.update(kw)
    return rec


def self_test() -> int:
    """Cheap offline check of the classifier, the lift evidence and the regexes."""
    ok = True
    cases = [
        (
            "winner peach: re-seat kept the gap, lift slipped the payload out",
            _case(
                grasped=True,
                placed=False,
                carry=[
                    {"leg": "grasp_lift", "slip_max_mm": 164.4, "inh_speed": 0.354},
                    {"leg": "place1", "slip_max_mm": 361.3, "inh_speed": 0.783},
                    {"leg": "place0", "slip_max_mm": 84.0, "inh_speed": 0.058},
                ],
                clearance=[
                    {"leg": "grasp_lift", "mm": -1354.0, "where": "output belt"}
                ],
                regrasps=1,
            ),
            "lift-loss",
        ),
        (
            "winner strawberry: lift slip 262.5 mm, payload back on the belt",
            _case(
                grasped=False,
                placed=False,
                carry=[
                    {"leg": "grasp_lift", "slip_max_mm": 262.5, "inh_speed": 0.289}
                ],
                clearance=[{"leg": "grasp_lift", "mm": -1.0, "where": "main belt"}],
                regrasps=1,
                notes=["fruit did not follow the gripper"],
            ),
            "lift-loss",
        ),
        (
            "winner lychee: lift slip 253.5 mm to the floor",
            _case(
                grasped=False,
                placed=False,
                carry=[
                    {"leg": "grasp_lift", "slip_max_mm": 253.5, "inh_speed": 0.398}
                ],
                clearance=[
                    {"leg": "grasp_lift", "mm": -1352.0, "where": "output belt"}
                ],
                regrasps=2,
                notes=["fruit did not follow the gripper"],
            ),
            "lift-loss",
        ),
        (
            "single-arm kiwi: held through the lift (+52 mm), lost in place0",
            _case(
                grasped=True,
                placed=False,
                carry=[
                    {"leg": "grasp_lift", "slip_max_mm": 111.0, "inh_speed": 1.169},
                    {"leg": "place0", "slip_max_mm": 1021.8, "inh_speed": 0.452},
                ],
                clearance=[{"leg": "grasp_lift", "mm": 52.0, "where": "main belt"}],
            ),
            "place-escape",
        ),
        (
            "clean attempt",
            _case(
                grasped=True,
                placed=True,
                carry=[
                    {"leg": "grasp_lift", "slip_max_mm": 24.7, "inh_speed": 0.043}
                ],
                clearance=[{"leg": "grasp_lift", "mm": 50.0, "where": "main belt"}],
            ),
            "ok",
        ),
        (
            "catch-up never met the fruit",
            _case(grasped=False, placed=False, catchup_residual_mm=41.0),
            "catch-miss",
        ),
        (
            "trace-less biarm: no per-attempt evidence",
            _case(grasped=True, placed=False),
            "unknown",
        ),
        (
            "wait loop never saw the fruit",
            _case(
                grasped=False,
                placed=False,
                notes=["fruit never settled at the pick point (dy=+0.511 m)"],
            ),
            "no-trigger",
        ),
    ]
    for name, rec, want in cases:
        got = classify(rec)
        mark = "ok  " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{mark}] {name}: {got} (want {want})")

    for text, want in (
        (
            "[fruit] [task]   dynamic regrasp: re-seated in place (gap 47.4 mm kept)",
            True,
        ),
        ("[fruit] [task]   dynamic regrasp: re-seated on the moving fruit", True),
        ("[fruit] [task]   dynamic regrasp: opened the pads around the fruit", False),
    ):
        got = bool(RE_REGRASP.search(text))
        if got != want:
            ok = False
        print(f"  [{'ok  ' if got == want else 'FAIL'}] RE_REGRASP on {text!r}: {got}")

    m = RE_CLEARANCE.search(
        "[fruit] [motion] carry grasp_lift clearance: lowest payload point "
        "-1354 mm to the output belt"
    )
    got = (m.group(1), m.group(2), m.group(3)) if m else None
    want = ("grasp_lift", "-1354", "output belt")
    if got != want:
        ok = False
    print(f"  [{'ok  ' if got == want else 'FAIL'}] RE_CLEARANCE: {got}")

    print("w1 taxonomy self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", nargs="?", default="")
    parser.add_argument("--traces", default="")
    parser.add_argument("--catch", default="")
    parser.add_argument("--label", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.log:
        parser.error("a log path is required (or pass --self-test)")

    lines = open(args.log, encoding="utf-8", errors="replace").read().splitlines()
    traces = load_traces(args.traces)
    catches = load_catch(args.catch)
    # The run's own `[trace] scripted ... -> path` dump lines name exactly which
    # file belongs to each attempt (in completion order, per arm). This is the
    # authoritative map: the dump counter is not thread-safe under the
    # bimanual scheduler and the shared `logs/dynamic_trace/` directory holds
    # files from several runs.
    dump_entries = {"left": [], "right": []}
    for line in lines:
        m = RE_TRACE_DUMP.search(line)
        if m:
            dump_entries[m.group(1)].append(
                {
                    "outcome": m.group(2),
                    "rows": int(m.group(3)),
                    "basename": os.path.basename(m.group(4)),
                }
            )

    # Per-attempt records, in order of `[fruit]`/`[biarm] result` lines. For a
    # biarm log that block is printed only after the batch; the two arms'
    # `[motion]` legs interleave in the body without an arm tag, so per-attempt
    # lift evidence there comes from `--traces` (the trace-on run is proven
    # non-perturbing), not from a text heuristic.
    attempts = []
    pending = None  # the attempt whose [task] lines are currently streaming

    for line in lines:
        m = RE_ATTEMPT.search(line)
        if m:
            pending = {
                "seq": len(attempts),
                "attempt": int(m.group(1)),
                "arm": m.group(2) or (
                    "left" if m.group(5) == "0" else ("right" if m.group(5) else None)
                ),
                "fruit": m.group(3),
                "grade": m.group(4),
                "notes": [],
                "carry": [],
                "clearance": [],
                "catchup_residual_mm": None,
            }
            if m.group(6) and m.group(7):
                pending["sim_window"] = (float(m.group(6)), float(m.group(7)))
            attempts.append(pending)
            continue
        if pending is None:
            continue
        m = RE_HANDOVER.search(line)
        if m:
            pending["handover_dy"] = float(m.group(2))
            pending["handover_lead"] = float(m.group(3))
            continue
        m = RE_DESCENT.search(line)
        if m:
            pending["descent"] = {
                "waited": int(m.group(1)),
                "intercept": float(m.group(2)),
                "station": float(m.group(3)),
                "shift": float(m.group(4)),
                "fruit_dy": float(m.group(5)),
                "deadline": float(m.group(6)),
                "t_desc": float(m.group(7)),
            }
            continue
        m = RE_CATCHUP.search(line)
        if m:
            pending["catchup_residual_mm"] = float(m.group(1))
            continue
        m = RE_CARRY.search(line)
        if m:
            pending["carry"].append(
                {
                    "leg": m.group(1),
                    "ticks": int(m.group(2)),
                    "slip_max_mm": float(m.group(3)),
                    "inh_speed": float(m.group(4)),
                    "cone": float(m.group(5)),
                }
            )
            continue
        m = RE_CLEARANCE.search(line)
        if m:
            pending.setdefault("clearance", []).append(
                {"leg": m.group(1), "mm": float(m.group(2)), "where": m.group(3)}
            )
            continue
        m = RE_DYN_CLOSE.search(line)
        if m:
            pending["freeze"] = {
                "ticks": int(m.group(1)),
                "force": float(m.group(2)),
                "span_mm": float(m.group(3)),
                "cmd_mm": float(m.group(4)),
            }
            continue
        if RE_STATION_FRUIT.search(line):
            pending["notes"].append(RE_STATION_FRUIT.search(line).group(0))
        if RE_REGRASP.search(line):
            pending["regrasps"] = pending.get("regrasps", 0) + 1
        if RE_DIVERT.search(line):
            pending["diverted"] = True
        m = RE_RESULT_BI.search(line)
        if m:
            arm, index, fruit, grasped, placed, lift, force, sim, notes = m.groups()
            rec = attempts[-1]
            rec.update(
                arm=arm,
                index=int(index),
                fruit=fruit,
                grasped=grasped == "True",
                placed=placed == "True",
                lift=float(lift),
                force=float(force),
                sim=float(sim),
                notes=rec["notes"] + eval(notes),
            )
            continue
        m = RE_RESULT_RUN_SORTED.search(line)
        if m:
            rec = attempts[-1]
            rec.update(
                grasped=m.group(3) == "True",
                placed=m.group(4) == "True",
                lift=float(m.group(5)),
                force=float(m.group(6)),
                notes=rec["notes"] + eval(m.group(8)),
            )
            continue
        m = RE_RESULT_RUN.search(line)
        if m:
            rec = attempts[-1]
            rec.update(
                grasped=m.group(2) == "True",
                placed=m.group(3) == "True",
                lift=float(m.group(4)),
                force=float(m.group(5)),
                notes=rec["notes"] + eval(m.group(6)),
            )

    stats = None
    for line in lines:
        m = RE_STATS.search(line)
        if m:
            stats = (int(m.group(1)), int(m.group(2)))

    # Attach traces: per arm, the k-th trace dump belongs to the k-th attempt of
    # that arm (attempts on one arm are strictly sequential, both single-arm and
    # in the bimanual scheduler).
    if any(dump_entries.values()):
        for arm, entries in dump_entries.items():
            recs = [r for r in attempts if (r.get("arm") or "?") == arm]
            if any(r.get("sim_window") for r in recs):
                recs.sort(key=lambda r: (r.get("sim_window") or (1e9, 1e9)))
            for rec, entry in zip(recs, entries):
                path = os.path.join(args.traces, entry["basename"])
                try:
                    with open(path, encoding="utf-8") as handle:
                        payload = json.load(handle)
                    rec["rows"] = payload.get("rows", []) if isinstance(payload, dict) else payload
                except (OSError, ValueError):
                    rec["rows"] = []
    else:
        by_arm: dict[str | None, list] = {}
        for entry in traces:
            by_arm.setdefault(entry["arm"], []).append(entry)
        for arm, entries in by_arm.items():
            entries.sort(
                key=lambda item: min(float(r["t"]) for r in item["rows"])
                if item["rows"]
                else 1e9
            )
            if arm is None:
                recs = [r for r in attempts if not r.get("arm")]
            else:
                recs = [r for r in attempts if (r.get("arm") or "?") == arm]
            if any(r.get("sim_window") for r in recs):
                recs.sort(key=lambda r: (r.get("sim_window") or (1e9, 1e9)))
            for rec, entry in zip(recs, entries):
                rec["rows"] = entry["rows"]

    # Attach catch traces by sim-time overlap (the catch trace's first row
    # falls inside the attempt's trace window when both exist; otherwise use
    # the log order: the Nth `dynamic catch-up` line of the log maps to the
    # Nth catch file, globally, and the arm is in the file name).
    for rec in attempts:
        rec.setdefault("rows", [])
        rec.setdefault("carry_slide", {})
        if rec["rows"] and not rec.get("carry_slide"):
            rec["carry_slide"] = split_carry_segments(rec["rows"])
        rec["catch"] = None
        rows = rec.get("rows") or []
        if rows:
            ts = [float(r["t"]) for r in rows]
            rec["_win"] = (min(ts), max(ts))
        elif rec.get("sim_window"):
            rec["_win"] = tuple(rec["sim_window"])
    log_catchups = [rec for rec in attempts if rec.get("catchup_residual_mm") is not None]

    for path, rows in catches:
        if not rows:
            continue
        base = os.path.basename(path)
        arm_from_name = "left" if "_left" in base else ("right" if "_right" in base else None)
        t0 = float(rows[0]["sim_time"])
        best = None
        for rec in attempts:
            if arm_from_name and rec.get("arm") and rec["arm"] != arm_from_name:
                continue
            win = rec.get("_win")
            if win and win[0] - 0.001 <= t0 <= win[1] + 0.001:
                best = rec
                break
        if best is None:
            for rec in log_catchups:
                if rec.get("catch") is None:
                    if arm_from_name and rec.get("arm") and rec["arm"] != arm_from_name:
                        continue
                    best = rec
                    break
        if best is not None:
            best["catch"] = rows

    # Attempt time windows from the trace rows (first/last t).
    print(f"== W1 taxonomy: {args.label or args.log} ==")
    print(f"stats={stats} attempts={len(attempts)} indexed={sum(1 for l in lines if 'indexed:' in l)}")
    print()
    header = (
        "attempt arm    fruit      grade gras placed lift   Fmax  catchup "
        "close_off(x,y)      force  slideL slideP coneL coneP q2[end,min,max] clip class"
    )
    print(header)
    classes = {}
    for rec in attempts:
        rows = rec.get("rows") or []
        geo = catch_geometry(rows, rec.get("catch"), rec.get("catchup_residual_mm"))
        rec["geo"] = geo
        carry_logs = rec.get("carry", [])
        slide_l = rec["carry_slide"].get("grasp_lift", (0.0, None))[0] or max(
            [
                c["slip_max_mm"] / 1000.0
                for c in carry_logs
                if c["leg"] == "grasp_lift"
            ]
            + [0.0]
        )
        slide_p = max(
            [
                rec["carry_slide"].get(k, (0.0, None))[0] or 0.0
                for k in ("place0", "place1")
            ]
            + [
                c["slip_max_mm"] / 1000.0
                for c in carry_logs
                if c["leg"].startswith("place")
            ]
            + [0.0]
        )
        cone_l = next(
            (c["cone"] for c in rec.get("carry", []) if c["leg"] == "grasp_lift"), None
        )
        cone_p = max(
            [c["cone"] for c in rec.get("carry", []) if c["leg"].startswith("place")]
            + [0.0]
        )
        q2 = (
            f"[{geo.get('catch_q2_end')},{geo.get('catch_q2_min')},{geo.get('catch_q2_max')}]"
            if "catch_q2_end" in geo
            else "-"
        )
        cls = classify(rec)
        rec["class"] = cls
        rec["lift_ev"] = lift_evidence(rec)
        classes[cls] = classes.get(cls, 0) + 1
        off = geo.get("close_offset_mm", [None, None, None])
        catchup = rec.get("catchup_residual_mm")
        catchup_s = f"{catchup:6.1f}" if catchup is not None else "     -"
        lift_s = f"{rec.get('lift', 0.0):+.3f}" if "lift" in rec else "  -   "
        force_s = f"{rec.get('force', 0.0):5.2f}" if "force" in rec else "  -  "
        print(
            f"{rec['attempt']:>3d}    {(rec.get('arm') or '?'):6s} "
            f"{rec.get('fruit','?'):10s} {rec.get('grade','?')}    "
            f"{'T' if rec.get('grasped') else 'F'}    "
            f"{'T' if rec.get('placed') else 'F'}    "
            f"{lift_s} {force_s} "
            f"{catchup_s} "
            f"[{off[0]},{off[1]}]  {geo.get('force_max', 0.0):5.2f} "
            f"{slide_l * 1000:6.0f} {slide_p * 1000:6.0f} "
            f"{cone_l or 0:5.2f} {cone_p:5.2f} {q2:>26s} "
            f"{geo.get('catch_clipped', 0):3d}  {cls}"
        )
        rec["slide_l_mm"] = slide_l * 1000.0
        rec["slide_p_mm"] = slide_p * 1000.0

    print()
    print("class totals:", ", ".join(f"{k}={v}" for k, v in sorted(classes.items())))
    if classes.get("unknown"):
        print(
            "note: unknown = no per-attempt evidence; a trace-less biarm log"
            " interleaves the two arms' legs - pass --traces for those."
        )
    print()
    for rec in attempts:
        if rec["class"] == "ok":
            continue
        geo = rec.get("geo", {})
        print(
            f"- attempt {rec['attempt']} {rec.get('arm')} {rec.get('fruit')} "
            f"({rec.get('grade')}): {rec['class']} | "
            f"handover_dy={rec.get('handover_dy')} descent={rec.get('descent')} | "
            f"catchup={rec.get('catchup_residual_mm')} mm | "
            f"close_off={geo.get('close_offset_mm')} Fmax={geo.get('force_max')} "
            f"sep_min={geo.get('sep_min')} | slide_l={rec.get('slide_l_mm'):.0f} "
            f"slide_p={rec.get('slide_p_mm'):.0f} mm | "
            f"lift: slip={_mm(rec['lift_ev'].get('slip_mm'))} mm "
            f"clear={_mm(rec['lift_ev'].get('clearance_mm'))} mm "
            f"to the {rec['lift_ev'].get('where') or '?'} "
            f"regrasps={rec['lift_ev'].get('regrasps', 0)} | "
            f"catch: ticks={geo.get('catch_ticks')} clipped={geo.get('catch_clipped')} "
            f"q2 end={geo.get('catch_q2_end')} min={geo.get('catch_q2_min')} "
            f"max={geo.get('catch_q2_max')} err_end={geo.get('catch_err_end_mm')} mm | "
            f"notes={rec.get('notes')}"
        )
    return 0


def split_carry_segments(rows):
    """Split `carry`-phase rows into grasp_lift/place segments by time gaps.

    The trace rows are appended only for dynamic capture and (with
    `FRUIT_DYNAMIC_TRACE_PLACE=1`) for place legs; between two legs a large
    sim-time gap normally exists (the close/hold/takeoff rows are not `carry`).
    Segment order is the leg order, so name them by the [motion] carry line
    order via the caller.
    """
    carries = [r for r in rows if r.get("phase") == "carry"]
    out = {}
    if not carries:
        return out
    segments = [[carries[0]]]
    for row in carries[1:]:
        # The lift->place boundary is a 0.59 s pause (the lift tail + place
        # setup); within a leg the rows are contiguous at the 120 Hz rate.
        if float(row["t"]) - float(segments[-1][-1]["t"]) > 0.3:
            segments.append([row])
        else:
            segments[-1].append(row)
    names = ["grasp_lift", "place0", "place1"]
    for index, seg in enumerate(segments[:3]):
        ref = seg[0]["hand_rel"]
        peak, onset = 0.0, None
        for row in seg:
            d = sum(
                (float(a) - float(b)) ** 2 for a, b in zip(row["hand_rel"], ref)
            ) ** 0.5
            peak = max(peak, d)
            if onset is None and d > 0.010:
                onset = float(row["t"])
        out[names[index]] = (peak, onset)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
