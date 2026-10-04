#!/usr/bin/env python3
"""Per-class mechanism audit of the dynamic-pick failure set.

    python3 scripts/143_dynamic_classes.py logs/p3fix/probe_slow.log \
        --traces logs/p3fix/traces_slow
    python3 scripts/143_dynamic_classes.py logs/p3fix/rate_v3_1.log ... \
        --traces logs/p3fix/traces_v3

`142_dynamic_audit.py` answers "what did the ten attempts score and where did
each descent/close end"; this tool answers the three *remaining failure classes*
from `logs/p3_arrival_takeoff/` and the P3-fix lane: the left-arm carry slide, the
small-fruit squeeze (strawberry), and the lateral walk through the close (kiwi).
It reads the same log lines plus the opt-in `FRUIT_DYNAMIC_TRACE=1` rows, so the
classes get a mechanism number rather than an outcome:

* **carry slide** - `FRUIT_DYNAMIC_LIFT` trace rows of `grasp_lift`: the payload's
  displacement in the hand frame along the tool axis (`hand_rel`), i.e. how far it
  slid *out* of the jaws. A hold keeps it <1 mm; a slip grows to hundreds of mm.
* **squeeze** - the close/hold force range and the smallest measured link span
  (`sep`). The strawberry crush shows up as a force spike and a span that keeps
  travelling after contact (the pads drive past the fruit and eject it).
* **lateral walk** - the fruit's cross-belt (world x) displacement over the close
  rows and its start-of-close velocity. The kiwi walks +40 mm at ~+0.08 m/s; the
  pinned jaw then lets it leave the span.

Every number is a read of the trace/log; the tool never runs a simulator.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re

CARRIES = {2: "left carry slide", 4: "strawberry crush", 6: "kiwi walk"}
NAMES = {
    0: "apple", 1: "orange", 2: "peach", 3: "pear", 4: "strawberry",
    5: "lychee", 6: "kiwi", 7: "tomato", 8: "apple", 9: "orange",
}
RE_OUTCOME = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+-][\d.]+) m "
    r"force=([\d.]+) N"
)
RE_CARRY_SLIP = re.compile(r"\[motion\] carry grasp_lift: .*?slip=([\d.]+) mm")
RE_STATS = re.compile(r"\[stats\] attempts=(\d+) successes=(\d+).*?gate_open=([\d.]+)s")
RE_INDEXED = re.compile(r"indexed:")
RE_FREEZE = re.compile(r"dynamic close: sustained contact after (\d+) ticks .*?at ([\d.]+) mm")
RE_WALK = re.compile(r"close x-lock off: fruit walks at ([+-][\d.]+) m/s")
RE_ATTEMPT = re.compile(r"\[run\] attempt (\d+): picking")


def read_log(path: str) -> dict:
    run = {"outcomes": {}, "carry_slip": [], "stats": None, "indexed": 0,
           "freeze_mm": {}, "walk_mps": {}}
    current = -1
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if RE_INDEXED.search(line):
                run["indexed"] += 1
            match = RE_ATTEMPT.search(line)
            if match:
                current = int(match.group(1))
            match = RE_FREEZE.search(line)
            if match:
                run["freeze_mm"][current] = float(match.group(2))
            match = RE_WALK.search(line)
            if match:
                run["walk_mps"][current] = float(match.group(1))
            match = RE_OUTCOME.search(line)
            if match:
                run["outcomes"][int(match.group(1))] = {
                    "fruit": NAMES.get(int(match.group(1)), "?"),
                    "success": match.group(2) == "True" and match.group(3) == "True",
                    "lift": float(match.group(4)),
                    "force": float(match.group(5)),
                }
            match = RE_CARRY_SLIP.search(line)
            if match:
                run["carry_slip"].append(float(match.group(1)))
            match = RE_STATS.search(line)
            if match:
                run["stats"] = {
                    "successes": int(match.group(2)),
                    "attempts": int(match.group(1)),
                    "gate_open": float(match.group(3)),
                }
    return run


def carry_mechanism(rows: list) -> dict:
    """Tool-axis slide of the payload during the `grasp_lift` carry rows."""
    car = [r for r in rows if r["phase"] == "carry" and "hand_rel" in r]
    if len(car) < 2:
        return {}
    rel = [json.loads(json.dumps(r["hand_rel"])) for r in car]
    z0 = rel[0][2]
    worst = 0.0
    onset = None
    for index, row in enumerate(rel):
        slide = abs(row[2] - z0)
        if slide > 0.005 and onset is None:
            onset = index
        worst = max(worst, slide)
    return {"slide_mm": worst * 1000.0, "onset": onset, "rows": len(car)}


def close_mechanism(rows: list) -> dict:
    """Force/spans of the first close attempt and the fruit's lateral walk."""
    close = [r for r in rows if r["phase"] == "close"][:84]
    hold = [r for r in rows if r["phase"] == "hold"][:24]
    if not close:
        return {}
    x0 = close[0]["fruit"][0]
    x1 = close[-1]["fruit"][0]
    vx = close[0].get("fruit_vel", [0.0, 0.0, 0.0])[0]
    forces = [r["force"] for r in close] + [r["force"] for r in hold]
    return {
        "dx_mm": (x1 - x0) * 1000.0,
        "vx0": vx,
        "force_max": max(forces) if forces else 0.0,
        "force_min_hold": min((r["force"] for r in hold), default=0.0),
        "sep_min_mm": min(r["sep"] for r in close) * 1000.0,
    }


def trace_table(directory: str) -> dict:
    table = {}
    for path in sorted(glob.glob(os.path.join(directory, "dynamic_trace_*.json"))):
        if path.endswith("_summary.json"):
            continue
        index = int(os.path.basename(path).split("_")[-1].split(".")[0])
        rows = json.load(open(path))
        table[index] = {"carry": carry_mechanism(rows), "close": close_mechanism(rows)}
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", help="dynamic run logs (trace-off or on)")
    parser.add_argument("--traces", default=None, help="trace directory for the last run")
    args = parser.parse_args()

    table = trace_table(args.traces) if args.traces else {}
    for path in args.logs:
        run = read_log(path)
        stats = run["stats"]
        print(f"\n=== {path}")
        if stats:
            print(
                f"    {stats['successes']}/{stats['attempts']} "
                f"gate_open={stats['gate_open']}s indexed={run['indexed']}"
            )
        print(
            f"    {'A':>2} {'fruit':<11} {'ok':>5} {'lift':>7} {'force':>6} "
            f"{'log slip':>8} | {'hand slide':>10} {'onset':>5} | "
            f"{'close dx':>8} {'vx0':>7} {'Fmax':>6} {'sep_min':>7} "
            f"{'freeze':>7} {'walk':>7}"
        )
        for index in sorted(run["outcomes"]):
            row = run["outcomes"][index]
            traced = table.get(index, {})
            carry = traced.get("carry", {})
            close = traced.get("close", {})
            log_slip = (
                f"{run['carry_slip'][index]:.1f}"
                if index < len(run["carry_slip"])
                else "-"
            )
            print(
                f"    {index:>2} {row['fruit']:<11} {str(row['success']):>5} "
                f"{row['lift']:>+7.3f} {row['force']:>6.2f} {log_slip:>8} | "
                f"{carry.get('slide_mm', float('nan')):>10.1f} "
                f"{str(carry.get('onset', '-')):>5} | "
                f"{close.get('dx_mm', float('nan')):>+8.1f} "
                f"{close.get('vx0', float('nan')):>+7.4f} "
                f"{close.get('force_max', float('nan')):>6.1f} "
                f"{close.get('sep_min_mm', float('nan')):>7.1f} "
                f"{run['freeze_mm'].get(index, float('nan')):>7.1f} "
                f"{run['walk_mps'].get(index, float('nan')):>+7.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
