#!/usr/bin/env python3
"""P31-A: measure the direct loop's WAIT anatomy from the existing logs.

Read-only. Two questions:

1. **Where is the fruit when the model is called?** The direct loop samples one
   action chunk per `execute_steps=4` control ticks from the first tick the
   observation horizon is full, all the way to the attempt's end. This script
   reconstructs the fruit's along-distance (station frame, `+` = upstream) at
   every model-call tick from the per-step `[rl]   step=` traces and prints the
   distribution split by episode class.

2. **Where does the decision happen?** The two fire channels are the scripted
   trigger (`should_fire`, fires at `dy ~ lead*speed`) and the learned close
   (`finger < 0.030 and |jaw-fruit|xy < 0.06`). Both are read from the logs
   (`intercept trigger (dy=...)` notes and the `[acq]` `close_start=` rows), so
   the gate's threshold can be placed above the whole measured fire band.

Outputs the tables quoted in `logs/p31/WAIT_GATE_DESIGN.md`. Usage:

    python3 logs/p31/30_wait_anatomy.py [--x 0.20,0.25,0.30,0.35,0.40]

Every input is an existing log; nothing is re-run and nothing is written.
"""

from __future__ import annotations

import argparse
import collections
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Logs carrying per-step `[rl]   step=` rows (the `RL_ENV_DEBUG=1` trace).
TRACE_GLOBS = [
    "logs/w4/51_direct_debug_rlenv.log",
    "logs/810_diag_moe_v10_debug.log",
    "logs/731_rl_moe_v8_direct_debug.log",
    "logs/714_rl_direct_debug.log",
    "logs/748_rl_direct_debug_v9.log",
    "logs/749_rl_direct_debug_v9_open.log",
    "logs/820_trigger_diag_seed77.log",
    "logs/830_trigger_diag_seed101.log",
    "logs/831_trigger_diag_seed202.log",
]

#: Logs with `[rl] episode` rows only - the class counts (P30-B's source).
EPISODE_GLOBS = [
    "logs/p28/probe_A.log",
    "logs/r11/B_N/A_1.log",
    "logs/r11/B_N/B_1.log",
    "logs/r7/A_edge_fix.log",
    "logs/r7/A_ship_fix.log",
]

TRACE_A = re.compile(
    r"step=(\d+) finger=([\d.]+) \|jaw-fruit\|xy=([\d.]+)cm "
    r"fruit=\(([-\d.]+),([+-][\d.]+),([-\d.]+)\) "
    r"jaw=\(([-\d.]+),([+-][\d.]+),([-\d.]+)\)"
)
TRACE_B = re.compile(
    r"step=(\d+) finger=([\d.]+) .*station=\(([-\d.]+),([+-][\d.]+)\).*"
    r"dy=([+-][\d.]+) dx=([+-][\d.]+).*fire=(True|False)"
)
HEADER = re.compile(r"\[rl\] episode (\d+):")
RESULT = re.compile(
    r"\[rl\] episode \d+: .*success=(\w+) grasped=(\w+) placed=(\w+) "
    r"ticks=(\d+) decision=(\d+)"
)
NOTE_DY = re.compile(r"intercept trigger \(dy=([-\d.]+)cm")
ACQ_CLOSE = re.compile(r"close_start=\(([+-][\d.]+),([+-][\d.]+),([+-][\d.]+)\)mm")


def rel(path: str) -> str:
    return os.path.join(ROOT, path)


def classify(success: bool, grasped: bool, placed: bool, notes: str) -> str:
    if success:
        return "success"
    if grasped and not placed:
        return "carried"          # carried-not-placed (grip escape)
    if "fruit fell off the line" in notes or "timeout" in notes:
        return "no-fire"          # never closed / never fired
    return "close-drop"           # closed, did not follow the gripper


def parse_traces(paths: list[str]):
    """One record per episode: header y0, result class, per-step rows."""
    episodes = []
    for path in paths:
        if not os.path.exists(rel(path)):
            continue
        cur = None
        for line in open(rel(path), errors="replace"):
            if HEADER.search(line):
                if RESULT.search(line):
                    if cur is not None:
                        m = RESULT.search(line)
                        cur["success"] = m.group(1) == "True"
                        cur["grasped"] = m.group(2) == "True"
                        cur["placed"] = m.group(3) == "True"
                        cur["ticks"] = int(m.group(4))
                        cur["decision"] = int(m.group(5))
                        cur["result"] = line.strip()
                        cur["class"] = classify(
                            cur["success"], cur["grasped"], cur["placed"], line
                        )
                        episodes.append(cur)
                        cur = None
                else:
                    if cur is not None:
                        episodes.append(cur)
                    cur = {
                        "file": path,
                        "header": line.strip(),
                        "rows": [],
                        "station_y": None,
                        "success": None,
                        "grasped": None,
                        "placed": None,
                        "ticks": None,
                        "decision": None,
                        "class": "unfinished",
                        "result": "",
                    }
                continue
            if cur is None:
                continue
            m = TRACE_B.search(line)
            if m:
                cur["rows"].append(
                    {
                        "step": int(m.group(1)),
                        "finger": float(m.group(2)),
                        "station_y": float(m.group(4)),
                        "dy": float(m.group(5)),
                        "dx": float(m.group(6)),
                        "fire": m.group(7) == "True",
                        "fruit_y": float(m.group(4)) + float(m.group(5)),
                        "jaw_y": float("nan"),
                    }
                )
                continue
            m = TRACE_A.search(line)
            if m:
                cur["rows"].append(
                    {
                        "step": int(m.group(1)),
                        "finger": float(m.group(2)),
                        "fruit_y": float(m.group(5)),
                        "jaw_y": float(m.group(8)),
                        "dy": float("nan"),
                        "dx": float("nan"),
                        "fire": False,
                    }
                )
        if cur is not None:
            episodes.append(cur)
    return episodes


def station_of(ep) -> float:
    """The station y the along-distance is measured from.

    Format B prints it; format A does not, so the first traced row's *jaw* y is
    used (the arm is at the calibrated grasp pose at reset, and
    `_trigger_station` is exactly that point - the difference is <= 1 cm).
    """
    rows = ep["rows"]
    if not rows:
        return 0.0
    if rows[0]["dy"] == rows[0]["dy"]:  # format B
        return rows[0]["station_y"]
    return rows[0]["jaw_y"]


def along_at(ep, station_y: float, step: float) -> float:
    """Fruit along-distance [m] at `step`, linear between traced rows."""
    rows = ep["rows"]
    if not rows:
        return float("nan")
    if step <= rows[0]["step"]:
        # Extrapolate back to step 0 with the first measured segment's slope.
        if len(rows) > 1:
            a, b = rows[0], rows[1]
            slope = (b["fruit_y"] - a["fruit_y"]) / max(1, b["step"] - a["step"])
        else:
            slope = -0.001
        return rows[0]["fruit_y"] - station_y + slope * (step - rows[0]["step"])
    lo = rows[0]
    for hi in rows[1:]:
        if hi["step"] >= step:
            span = max(1, hi["step"] - lo["step"])
            f = (step - lo["step"]) / span
            return (lo["fruit_y"] + f * (hi["fruit_y"] - lo["fruit_y"])) - station_y
        lo = hi
    # Past the last traced row: the fruit keeps riding at the last slope.
    if len(rows) > 1:
        a, b = rows[-2], rows[-1]
        slope = (b["fruit_y"] - a["fruit_y"]) / max(1, b["step"] - a["step"])
    else:
        slope = -0.001
    return rows[-1]["fruit_y"] - station_y + slope * (step - rows[-1]["step"])


def call_ticks(ep, execute_steps: int) -> int:
    """Model-call ticks in the episode: one chunk per `execute_steps` ticks.

    The model's span is `min(decision, ticks)`: on a fired episode `decision` is
    the tick `_run_primitive` took over (no model call after it, the primitive
    runs to the end); on a no-fire/no-grasp episode `decision == ticks` (the
    fruit fell off the line or the horizon expired).
    """
    end = min(ep["ticks"] or 0, ep["decision"] or 0) or ep["rows"][-1]["step"]
    return end // execute_steps


def ladder(episodes, xs, pasts, execute_steps: int):
    """Calls with along > X (upstream gate) and along < -P (past gate), per class."""
    out = collections.defaultdict(
        lambda: collections.defaultdict(lambda: [0, 0, 0])  # total, skipped>X, skipped<-P
    )
    for ep in episodes:
        if ep["class"] == "unfinished" or not ep["rows"]:
            continue
        st = station_of(ep)
        n = call_ticks(ep, execute_steps)
        for k in range(n):
            t = k * execute_steps
            a = along_at(ep, st, t)
            if a != a:
                continue
            rec = out[ep["class"]]
            rec["calls"][0] += 1
            for x in xs:
                if a > x:
                    rec[("far", x)][0] += 1
                    rec[("far", x)][1] += 1
                else:
                    rec[("far", x)][0] += 1
            for p in pasts:
                if p > 0.0 and a < -p:
                    rec[("past", p)][0] += 1
                    rec[("past", p)][1] += 1
                else:
                    rec[("past", p)][0] += 1
    return out


def fire_distances(paths):
    """The fire-time along distances from the trigger notes and [acq] rows."""
    trigger = []
    close_start = []
    for path in paths:
        if not os.path.exists(rel(path)):
            continue
        for line in open(rel(path), errors="replace"):
            m = NOTE_DY.search(line)
            if m:
                trigger.append(float(m.group(1)) / 100.0)
            if "[acq]" in line:
                m = ACQ_CLOSE.search(line)
                if m:
                    # close_start is the tip-fruit offset in the arm frame:
                    # the +Y component is the along-distance.
                    close_start.append((float(m.group(1)), float(m.group(2)),
                                       float(m.group(3))))
    return trigger, close_start


def derive_from_episodes():
    """Per-episode derivation on the current scenario from `[rl] episode` rows.

    `along0` is the fruit's reset `y=` minus the measured post-selection travel
    (0.096-0.107 m on the three traced 0.12 episodes: the header prints the
    *selection* state, then `reset` runs its teleport + `advance(20)` + the first
    observation, so the first model call sees the fruit already ~0.10 m closer).

    `along@fire` is the trigger's `dy` when the trigger fired, else 0.054 m (the
    learned gate's `|jaw-fruit|xy = 6.0 cm` with the measured lateral offset).
    The gate's skipped calls at `X` are `(along0 - X) / (v_belt * execute_steps)`.
    """
    header = re.compile(
        r"\[rl\] episode \d+: \S+ grade=\w d=[\d.]+cm bin=\d arm=\w+ "
        r"y=([+-][\d.]+) presentation=direct"
    )
    result = re.compile(
        r"\[rl\] episode \d+: .*success=(\w+) grasped=(\w+) placed=(\w+) "
        r"ticks=(\d+) decision=(\d+).*notes=\[(.*)\] presentation=direct"
    )
    note_dy = re.compile(r"intercept trigger \(dy=([+-]?[\d.]+)cm")
    files = [
        "logs/p28/probe_A.log",
        "logs/r11/B_N/A_1.log", "logs/r11/B_N/B_1.log", "logs/r11/B_M0.log",
        "logs/r7/A_edge_fix.log", "logs/r7/A_ship_fix.log",
        "logs/r7/A_control_edge.log", "logs/r9/A_direct_ab/A_1.log",
        "logs/w7/B_ab/A_1.log", "logs/w7/B_ab/B_1.log",
        "logs/w4/51_direct_debug_rlenv.log",
    ]
    reset_offset = 0.10   # m of belt travel between the header and step 0
    v_chunk = 0.004       # m per 4-tick chunk at 0.12 m/s
    x = 0.35
    acc = collections.defaultdict(
        lambda: {"n": 0, "calls": [], "skip": [], "a0": [], "share": []}
    )
    for path in files:
        if not os.path.exists(rel(path)):
            continue
        pend = None
        for line in open(rel(path), errors="replace"):
            m = header.search(line)
            if m:
                pend = float(m.group(1))
                continue
            m = result.search(line)
            if not m or pend is None:
                continue
            success = m.group(1) == "True"
            grasped = m.group(2) == "True"
            placed = m.group(3) == "True"
            notes = m.group(6)
            ticks = int(m.group(4))
            decision = int(m.group(5))
            cls = classify(success, grasped, placed, notes)
            dy = note_dy.search(notes)
            fire = float(dy.group(1)) / 100.0 if dy else 0.054
            a0 = pend - reset_offset
            calls = min(ticks, decision) / 4.0
            skip = max(0.0, (a0 - x) / v_chunk)
            skip = min(skip, calls)
            rec = acc[(os.path.basename(path).replace(".log", ""), cls)]
            rec["n"] += 1
            rec["calls"].append(calls)
            rec["skip"].append(skip)
            rec["a0"].append(a0)
            rec["share"].append(skip / calls if calls else 0.0)
            pend = None
    out = {}
    for key, rec in acc.items():
        n = rec["n"]
        out[key] = {
            "n": n,
            "a0": sorted(rec["a0"])[n // 2],
            "calls": sum(rec["calls"]) / n,
            "skip": sum(rec["skip"]) / n,
            "share": sum(rec["share"]) / n,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--x", default="0.15,0.20,0.25,0.30,0.35,0.40,0.50")
    ap.add_argument("--past", default="0.05,0.10,0.20,0.50,0.90")
    ap.add_argument("--execute-steps", type=int, default=4)
    args = ap.parse_args()
    xs = [float(v) for v in args.x.split(",") if v.strip()]
    pasts = [float(v) for v in args.past.split(",") if v.strip()]

    trace_paths = [p for p in TRACE_GLOBS]
    episodes = [e for e in parse_traces(trace_paths) if e["class"] != "unfinished"]
    print(f"# traced episodes: {len(episodes)} "
          f"({len(trace_paths)} candidate logs)")
    print()
    print("## 1. Per-episode: the fruit's along-distance at the model's calls")
    print()
    print("| log | ep | class | span | calls | along@fire | call@0.35 | jaw walk |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for ep in episodes:
        st = station_of(ep)
        n = call_ticks(ep, args.execute_steps)
        fire = ep["decision"] if ep["success"] is not None else None
        a_fire = (
            f"{along_at(ep, st, fire):+.3f}" if fire is not None else "-"
        )
        first_035 = None
        for k in range(n):
            if along_at(ep, st, k * args.execute_steps) <= 0.35:
                first_035 = k
                break
        jaw = ep["rows"][-1]["jaw_y"] - ep["rows"][0]["jaw_y"]
        jaw_txt = f"{jaw:+.3f}" if jaw == jaw else "n/a"
        base = os.path.basename(ep["file"]).replace("_direct_debug", "").replace(".log", "")
        print(
            f"| {base} | {HEADER.search(ep['header']).group(1)} | {ep['class']} | "
            f"{min(ep['ticks'], ep['decision'])} | {n} | {a_fire} | "
            f"{first_035 if first_035 is not None else '-'} | {jaw_txt} |"
        )
    print()

    print("## 2. Calls by class and the along-distance at them")
    print()
    hist = collections.defaultdict(collections.Counter)
    for ep in episodes:
        st = station_of(ep)
        n = call_ticks(ep, args.execute_steps)
        for k in range(n):
            a = along_at(ep, st, k * args.execute_steps)
            if a != a:
                continue
            bucket = (
                ">0.50" if a > 0.50 else
                "0.40-0.50" if a > 0.40 else
                "0.35-0.40" if a > 0.35 else
                "0.25-0.35" if a > 0.25 else
                "0.10-0.25" if a > 0.10 else
                "0.00-0.10" if a > 0.0 else
                "-0.10-0.00" if a > -0.10 else
                "<-0.10"
            )
            hist[ep["class"]][bucket] += 1
    order = [">0.50", "0.40-0.50", "0.35-0.40", "0.25-0.35", "0.10-0.25",
             "0.00-0.10", "-0.10-0.00", "<-0.10"]
    print("| class | " + " | ".join(order) + " |")
    print("| --- | " + " | ".join("---" for _ in order) + " |")
    for cls in sorted(hist):
        print(f"| {cls} | " + " | ".join(str(hist[cls][b]) for b in order) + " |")
    print()

    print("## 3. The gate ladder: calls skipped per class")
    print()
    table = ladder(episodes, xs, pasts, args.execute_steps)
    for cls in sorted(table):
        calls = table[cls]["calls"][0]
        print(f"### {cls} ({calls} calls)")
        print()
        print("| term | skipped | share |")
        print("| --- | --- | --- |")
        for x in xs:
            s = table[cls][("far", x)][1]
            print(f"| along > {x:.2f} | {s} | {s / calls:.1%} |")
        for p in pasts:
            if p <= 0:
                continue
            s = table[cls][("past", p)][1]
            print(f"| along < -{p:.2f} | {s} | {s / calls:.1%} |")
        print()

    print("## 4. The 0.12 m/s trace corpus: along0 and the skipped calls per episode")
    print()
    print("| log | ep | class | slope mm/tick | along0 | calls | skip@0.35 | share |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    twelves = []
    for ep in episodes:
        rows = ep["rows"]
        if len(rows) < 2:
            continue
        # Belt speed from the first ~100 ticks only: late in a fired episode the
        # fruit is attached to the hand, so a whole-episode slope is not the belt.
        a = rows[0]
        b = next((r for r in rows if r["step"] >= a["step"] + 50), rows[-1])
        slope = (b["fruit_y"] - a["fruit_y"]) / max(1, b["step"] - a["step"]) * 1000.0
        if abs(slope) < 0.85 or abs(slope) > 1.35:
            continue  # not the 0.12 m/s scenario
        twelves.append(ep)
        st = station_of(ep)
        n = call_ticks(ep, args.execute_steps)
        a0 = along_at(ep, st, 0)
        skip = sum(1 for k in range(n)
                   if along_at(ep, st, k * args.execute_steps) > 0.35)
        base = os.path.basename(ep["file"]).replace("_direct_debug", "").replace(".log", "")
        print(f"| {base} | {HEADER.search(ep['header']).group(1)} | {ep['class']} | "
              f"{slope:+.3f} | {a0:+.3f} | {n} | {skip} | {skip / max(1, n):.1%} |")
    print()
    if twelves:
        starts = [along_at(ep, station_of(ep), 0) for ep in twelves]
        calls = [call_ticks(ep, args.execute_steps) for ep in twelves]
        skips = [
            sum(1 for k in range(call_ticks(ep, args.execute_steps))
                if along_at(ep, station_of(ep), k * args.execute_steps) > 0.35)
            for ep in twelves
        ]
        print(f"0.12 corpus: n={len(twelves)} episodes, along0 "
              f"min {min(starts):+.3f} p50 {sorted(starts)[len(starts) // 2]:+.3f} "
              f"max {max(starts):+.3f} m; calls {sum(calls)}; "
              f"skipped@0.35 {sum(skips)} = {sum(skips) / max(1, sum(calls)):.1%}")
        print()

    print("## 5. The fire-time along distance (the decision zone)")
    print()
    trigger, acq = fire_distances(
        [
            "logs/r11/B_N/A_1.log", "logs/r11/B_N/B_1.log",
            "logs/r7/A_edge_fix.log", "logs/r7/A_ship_fix.log",
            "logs/w7/B_ab/A_1.log", "logs/w7/B_ab/B_1.log",
            "logs/p28/probe_A.log", "logs/r11/B_M0.log",
        ]
    )
    if trigger:
        s = sorted(trigger)
        print(f"trigger fire dy (n={len(s)}): "
              f"min {s[0]:+.3f} p50 {s[len(s) // 2]:+.3f} max {s[-1]:+.3f} m")
    else:
        print("trigger fire dy: no rows")
    print()
    print("## 6. Per-episode derivation on the current scenario (episode rows only)")
    print()
    print("along0 = the fruit's reset `y=` (station frame, + = upstream);")
    print("along@fire = the note's `intercept trigger (dy=...)` when the trigger")
    print("fired, else 0.054 m (the learned gate: `|jaw-fruit|xy=6.0cm`).")
    print()
    rows_out = derive_from_episodes()
    print("| log | class | n | along0 p50 | calls p50 | skip@0.35 p50 | share |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for (log, cls), rec in sorted(rows_out.items()):
        if not rec["n"]:
            continue
        print(f"| {log} | {cls} | {rec['n']} | {rec['a0']:+.3f} | "
              f"{rec['calls']:.0f} | {rec['skip']:.0f} | {rec['share']:.1%} |")
    print()
    tot_calls = sum(r["calls"] * r["n"] for r in rows_out.values())
    tot_skip = sum(r["skip"] * r["n"] for r in rows_out.values())
    tot_n = sum(r["n"] for r in rows_out.values())
    print(f"pooled: {tot_n} episodes, {tot_calls:.1f} calls/episode, "
          f"{tot_skip:.1f} skipped = {tot_skip / max(1e-9, tot_calls):.1%} "
          f"({tot_skip / max(1, tot_n):.1f} chunks/episode)")
    print()
    print("## 7. What the held action would freeze (traced 0.12 episodes)")
    print()
    print("| log | ep | jaw_y@call0 | jaw_y@0.35 | walk in the wait | finger@0.35 |")
    print("| --- | --- | --- | --- | --- | --- |")
    for ep in twelves:
        st = station_of(ep)
        n = call_ticks(ep, args.execute_steps)
        boundary = None
        for k in range(n):
            if along_at(ep, st, k * args.execute_steps) <= 0.35:
                boundary = k * args.execute_steps
                break
        if boundary is None:
            continue
        j0 = ep["rows"][0]["jaw_y"]
        j1 = next((r["jaw_y"] for r in ep["rows"] if r["step"] >= boundary), float("nan"))
        f1 = next((r["finger"] for r in ep["rows"] if r["step"] >= boundary), float("nan"))
        base = os.path.basename(ep["file"]).replace("_direct_debug", "").replace(".log", "")
        print(f"| {base} | {HEADER.search(ep['header']).group(1)} | {j0:+.3f} | "
              f"{j1:+.3f} | {j1 - j0:+.3f} | {f1:.4f} |")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
