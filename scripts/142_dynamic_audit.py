#!/usr/bin/env python3
"""Per-attempt audit of the P2 moving-catch runs.

    python3 scripts/142_dynamic_audit.py logs/p2_trace10.log
    python3 scripts/142_dynamic_audit.py logs/p2_speed_006.log logs/p2_speed_009.log
    python3 scripts/142_dynamic_audit.py --traces logs/p2b_pretrace logs/p2_trace10.log

Prints, per ten-attempt run, every attempt's fruit, outcome, close-start
offsets, catch-up residual, descent speed/end and the grasp_lift friction
cone; then the run totals.  The dynamic mechanism trace is opt-in
(`FRUIT_DYNAMIC_TRACE=1`), so the close-phase columns are only present for
runs that wrote `logs/dynamic_trace_*.json` (use `--traces DIR` to point at a
preserved copy).

The audit is deliberately read-only: a single run is one sample, so the tool
exists to let every number in the documents be re-derived from the log it came
from.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

RE_ATTEMPT = re.compile(r"\[run\] attempt (\d+): picking (.+?) grade (\S+)")
RE_OUTCOME = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+-][\d.]+) m "
    r"force=([\d.]+) N notes=(\[.*\])"
)
RE_DESCENT = re.compile(
    r"\[motion\] approach\(cartesian\): [\d.]+ cm, \d+ samples: .*?"
    r"\|v\|max=([\d.]+) m/s.*?end=([\d.]+) mm"
)
RE_CARRY = re.compile(
    r"\[motion\] carry (grasp_lift|place[01]): .*?"
    r"cone=([\d.]+)x budget"
)
RE_CATCHUP = re.compile(r"dynamic catch-up: residual=([\d.]+) mm")
RE_TRACE = re.compile(
    r"\[trace\] dynamic attempt (\d+): rows=(\d+) close_start_offset=(\[.*?\])"
)
RE_STATS = re.compile(
    r"\[stats\] attempts=(\d+) successes=(\d+).*?gate_open=([\d.]+)s"
)


def parse_log(path: str) -> dict:
    run = {"path": path, "attempts": {}, "order": [], "stats": None, "indexed": 0}
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "indexed:" in line:
                run["indexed"] += 1
            match = RE_ATTEMPT.search(line)
            if match:
                index = int(match.group(1))
                row = run["attempts"].setdefault(index, {})
                row["fruit"] = match.group(2).strip()
                row["grade"] = match.group(3)
                run["order"].append(index)
                continue
            match = RE_OUTCOME.search(line)
            if match:
                row = run["attempts"].setdefault(int(match.group(1)), {})
                row["grasped"] = match.group(2) == "True"
                row["placed"] = match.group(3) == "True"
                row["lift"] = float(match.group(4))
                row["force"] = float(match.group(5))
                row["notes"] = match.group(6)
                row["success"] = row["grasped"] and row["placed"]
                run["order"] = [i for i in run["order"] if i != int(match.group(1))]
                run["order"].append(int(match.group(1)))
                continue
            match = RE_DESCENT.search(line)
            if match:
                # Descents and catch-up prints precede the outcome line; attach
                # to the oldest attempt without a descent yet.
                for index in run["order"]:
                    row = run["attempts"][index]
                    if "descent_vmax" not in row and "success" not in row:
                        row["descent_vmax"] = float(match.group(1))
                        row["descent_end_mm"] = float(match.group(2))
                        break
                continue
            match = RE_CARRY.search(line)
            if match:
                for index in run["order"]:
                    row = run["attempts"][index]
                    if f"cone_{match.group(1)}" not in row and "success" not in row:
                        row[f"cone_{match.group(1)}"] = float(match.group(2))
                        break
                continue
            match = RE_CATCHUP.search(line)
            if match:
                for index in run["order"]:
                    row = run["attempts"][index]
                    if "catchup_mm" not in row and "success" not in row:
                        row["catchup_mm"] = float(match.group(1))
                        break
                continue
            match = RE_TRACE.search(line)
            if match:
                row = run["attempts"].setdefault(int(match.group(1)), {})
                row["trace"] = {
                    "rows": int(match.group(2)),
                    "close_start_offset": json.loads(match.group(3)),
                }
                continue
            match = RE_STATS.search(line)
            if match:
                run["stats"] = {
                    "attempts": int(match.group(1)),
                    "successes": int(match.group(2)),
                    "gate_open": float(match.group(3)),
                }
    return run


def trace_table(directory: str) -> dict:
    """close-phase metrics for one preserved trace dump.

    dx/dy are the fruit's cross-belt / along-belt displacement over the close
    rows; `lost` is the first tick after a sustained force at which the force
    stays gone for the rest of the close; `hold_force` is the force range over
    the hold rows.
    """
    table = {}
    for path in sorted(glob.glob(os.path.join(directory, "dynamic_trace_*.json"))):
        if path.endswith("_summary.json"):
            continue
        rows = json.load(open(path))
        attempt = int(os.path.basename(path).split("_")[-1].split(".")[0])
        close = [r for r in rows if r["phase"] == "close"]
        hold = [r for r in rows if r["phase"] == "hold"]
        if not close:
            continue
        x0, y0, _ = close[0]["fruit"]
        x1, y1, _ = close[-1]["fruit"]
        sustained = [i for i, r in enumerate(close) if r["force"] >= 0.5]
        lost = None
        if sustained:
            first = sustained[0]
            # first index after `first` where the force drops below 0.5 and
            # never returns for the rest of the close
            for i in range(first + 1, len(close)):
                if close[i]["force"] < 0.5 and all(
                    r["force"] < 0.5 for r in close[i:]
                ):
                    lost = close[i]
                    break
        table[attempt] = {
            "dx_mm": (x1 - x0) * 1000.0,
            "dy_mm": (y1 - y0) * 1000.0,
            "contact_t": close[sustained[0]]["t"] if sustained else None,
            "lost_t": lost["t"] if lost is not None else None,
            "lost_force": lost["force"] if lost is not None else None,
            "hold_force": (min(r["force"] for r in hold), max(r["force"] for r in hold))
            if hold
            else None,
            "sep_min_mm": min(r["sep"] for r in close) * 1000.0,
            "force_max": max(r["force"] for r in close),
        }
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", help="run logs to audit")
    parser.add_argument(
        "--traces",
        action="append",
        default=[],
        help="preserved directory of dynamic_trace_*.json (attempts keyed 0-9)",
    )
    args = parser.parse_args()

    # If exactly one trace dump is given, merge its close-phase columns into
    # the per-attempt rows; more than one is printed as separate tables because
    # the attempt index alone cannot say which run a dump belongs to.
    merged = trace_table(args.traces[0]) if len(args.traces) == 1 else {}

    for path in args.logs:
        run = parse_log(path)
        print(f"\n=== {path}")
        if run["stats"]:
            stats = run["stats"]
            print(
                f"    total {stats['successes']}/{stats['attempts']} "
                f"gate_open={stats['gate_open']}s indexed_lines={run['indexed']}"
            )
        header = (
            f"    {'A':>2} {'fruit':<11} {'ok':>3} {'force':>6} {'lift':>7} "
            f"{'catchup':>8} {'|v|max':>7} {'end':>6} {'cone':>5} "
            f"{'dx':>8} {'dy':>8} {'lost_t':>7} {'holdF':>13}"
        )
        print(header)
        for index in sorted(run["attempts"]):
            row = run["attempts"][index]
            cone = row.get("cone_grasp_lift")
            traced = merged.get(index, {})
            hold = traced.get("hold_force")
            hold_text = f"({hold[0]:.2f},{hold[1]:.2f})" if hold is not None else ""
            print(
                f"    {index:>2} {row.get('fruit', '?'):<11} "
                f"{str(row.get('success', '?')):>3} "
                f"{row.get('force', float('nan')):>6.2f} "
                f"{row.get('lift', float('nan')):>+7.3f} "
                f"{row.get('catchup_mm', float('nan')):>8.1f} "
                f"{row.get('descent_vmax', float('nan')):>7.3f} "
                f"{row.get('descent_end_mm', float('nan')):>6.1f} "
                f"{cone if cone is not None else float('nan'):>5.2f} "
                f"{traced.get('dx_mm', float('nan')):>+8.1f} "
                f"{traced.get('dy_mm', float('nan')):>+8.1f} "
                f"{_fmt(traced.get('lost_t')):>7} {hold_text:>13}"
            )
    if args.traces:
        for directory in args.traces:
            table = trace_table(directory)
            print(f"\n=== traces {directory} ({len(table)} attempts)")
            print(
                f"    {'A':>2} {'dx':>8} {'dy':>8} {'contact_t':>9} "
                f"{'lost_t':>9} {'lostF':>6} {'holdF':>13} {'sep_min':>8} {'Fmax':>6}"
            )
            for attempt in sorted(table):
                row = table[attempt]
                hf = row["hold_force"]
                print(
                    f"    {attempt:>2} {row['dx_mm']:>+8.1f} {row['dy_mm']:>+8.1f} "
                    f"{_fmt(row['contact_t']):>9} {_fmt(row['lost_t']):>9} "
                    f"{_fmt(row['lost_force']):>6} "
                    f"{'(%.2f, %.2f)' % hf if hf else '(none)':>13} "
                    f"{row['sep_min_mm']:>8.1f} {row['force_max']:>6.2f}"
                )
    return 0


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


if __name__ == "__main__":
    sys.exit(main())
