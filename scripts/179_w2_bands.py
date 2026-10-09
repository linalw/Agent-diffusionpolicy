"""Attribute two-line clearance near-misses to arm phases (W2).

    python3 scripts/179_w2_bands.py logs/w2/10_trace_before.log \
        --trace logs/w2/10_trace_before.jsonl

Pure text/JSONL analysis, no simulator. For each `[biarm] clearance trace`
sample below a threshold it prints the bands (contiguous runs), the link pair,
the sampled minimum, and - when `FRUIT_CYCLE_REPORT=1` and
`FRUIT_BIARM_PARK_TRACE=1` were on - which phase each arm was in: the phase
durations from the `[cycle]` lines are matched to the `[run] attempt` windows
by total duration (the cycle lines print at attempt end, the run lines carry
the sim window), and the park trace supplies the post-attempt return windows.

The trace is invasive (link reads), so this describes the instrumented
scenario; use it for mechanism, quote rates from trace-off runs.
"""

from __future__ import annotations

import argparse
import json
import re
from bisect import bisect_right

CYCLE = re.compile(
    r"\[cycle\] attempt (?P<n>\d+): (?P<body>.*?) total=(?P<total>[\d.]+)s"
)
SEG = re.compile(r"(?P<name>\w+)=(?P<dur>[\d.]+)s")
ATTEMPT = re.compile(
    r"\[run\] attempt (?P<slot>\d+) \((?P<arm>\w+)\): picking .*? sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s"
)
PARK = re.compile(
    r"\[biarm\] (?P<arm>\w+): park (?P<event>wait start|moving|done) t=(?P<t>[\d.]+)s"
)
ARM_ACQ = re.compile(r"\[biarm\] (?P<arm>\w+): station acquired at t=(?P<t>[\d.]+)s")


def parse_log(path: str):
    cycles, attempts, parks, acquired = [], [], [], []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            found = CYCLE.search(line)
            if found:
                segments = [(m.group("name"), float(m.group("dur"))) for m in SEG.finditer(found.group("body"))]
                cycles.append((int(found.group("n")), segments, float(found.group("total"))))
                continue
            found = ATTEMPT.search(line)
            if found:
                attempts.append(
                    (
                        int(found.group("slot")),
                        found.group("arm"),
                        float(found.group("t0")),
                        float(found.group("t1")),
                    )
                )
                continue
            found = PARK.search(line)
            if found:
                parks.append((found.group("arm"), found.group("event"), float(found.group("t"))))
            found = ARM_ACQ.search(line)
            if found:
                acquired.append((found.group("arm"), float(found.group("t"))))
    return cycles, attempts, parks, acquired


def build_windows(cycles, attempts, parks):
    """attempt -> list of (start, end, phase) per arm, sorted; plus unmatched.

    The `[cycle]` lines print in attempt *completion* order and the `[run]
    attempt` lines in start order, so they are matched by total duration with a
    +/-0.2 s tolerance, closest first (float rounding alone made 16.45 vs 16.5 a
    spurious mismatch in the first version).
    """
    pending = [(segments, total) for _n, segments, total in cycles]
    windows = {"left": [], "right": []}
    unmatched = 0
    for slot, arm, t0, t1 in attempts:
        span = t1 - t0
        best_index, best_delta = None, 1e9
        for index, (_segments, total) in enumerate(pending):
            delta = abs(total - span)
            if delta < best_delta and delta <= 0.2:
                best_index, best_delta = index, delta
        if best_index is None:
            unmatched += 1
            continue
        segments = pending.pop(best_index)[0]
        t = t0
        for name, dur in segments:
            windows[arm].append((t, t + dur, name))
            t += dur
    return windows, unmatched


def phase_at(windows, arm, t):
    rows = windows[arm]
    times = [row[1] for row in rows]
    index = bisect_right(times, t)
    if index >= len(rows):
        return "past-end"
    start, end, name = rows[index]
    if t >= start:
        return name
    return "idle"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log")
    parser.add_argument("--trace", required=True)
    parser.add_argument("--threshold", type=float, default=0.030)
    parser.add_argument("--positions", action="store_true", help="print hand positions inside each band")
    args = parser.parse_args()

    cycles, attempts, parks, acquired = parse_log(args.log)
    windows, unmatched = build_windows(cycles, attempts, parks)
    rows = [json.loads(line) for line in open(args.trace, encoding="utf-8")]

    print(f"== {args.log}")
    print(f"   cycles={len(cycles)} attempts={len(attempts)} park-events={len(parks)} "
          f"trace-samples={len(rows)} unmatched-cycle={unmatched}")
    for arm in ("left", "right"):
        print(f"   {arm}: {len(windows[arm])} phase windows; "
              f"{sum(1 for r in rows if r['min_m'] < args.threshold)} samples < "
              f"{args.threshold * 1000:.0f} mm overall")

    bands = []
    current = None
    for row in rows:
        if row["min_m"] < args.threshold:
            if current is None:
                current = {"t0": row["t"], "t1": row["t"], "min": row["min_m"],
                           "pairs": set(), "rows": 0}
            current["t1"] = row["t"]
            current["min"] = min(current["min"], row["min_m"])
            current["pairs"].add((row["left_link"], row["right_link"]))
            current["rows"] += 1
        else:
            if current is not None:
                bands.append(current)
                current = None
    if current is not None:
        bands.append(current)

    print(f"   {len(bands)} band(s) < {args.threshold * 1000:.0f} mm")
    for band in bands:
        tin = 0.5 * (band["t0"] + band["t1"])
        lp = phase_at(windows, "left", tin)
        rp = phase_at(windows, "right", tin)
        pairs = "; ".join(f"{l.replace('openarm_left_', 'L')}|{r.replace('openarm_right_', 'R')}"
                          for l, r in sorted(band["pairs"]))
        print(
            f"   t={band['t0']:7.2f}-{band['t1']:7.2f}s ({band['t1'] - band['t0']:4.2f}s): "
            f"min={band['min'] * 1000:5.1f} mm left={lp:<10s} right={rp:<10s} pairs={pairs}"
        )
        if args.positions:
            samples = [
                row
                for row in rows
                if band["t0"] - 1e-9 <= row["t"] <= band["t1"] + 1e-9
                and (row.get("pos") or {}).get("openarm_left_hand")
            ]
            picks = samples[:1]
            if samples:
                picks.append(min(samples, key=lambda row: row["min_m"]))
            for row in picks:
                pos = row.get("pos") or {}
                left = pos.get("openarm_left_hand")
                right = pos.get("openarm_right_hand")
                if not left or not right:
                    continue
                print(
                    f"        t={row['t']:7.2f} min={row['min_m'] * 1000:5.1f} "
                    f"Lhand=({left[0]:+.3f},{left[1]:+.3f},{left[2]:.3f}) "
                    f"Rhand=({right[0]:+.3f},{right[1]:+.3f},{right[2]:.3f})"
                )

    # Minimum by (left phase, right phase) pair for the phases in play.
    worst: dict[tuple[str, str], float] = {}
    for row in rows:
        key = (phase_at(windows, "left", row["t"]), phase_at(windows, "right", row["t"]))
        worst[key] = min(worst.get(key, 9.9), row["min_m"])
    print("   phase-pair minima (only pairs under 60 mm):")
    for (lp, rp), value in sorted(worst.items(), key=lambda kv: kv[1]):
        if value < 0.060:
            print(f"     left={lp:<12s} right={rp:<12s} min={value * 1000:5.1f} mm")

    if parks:
        print("   park events:")
        for arm, event, t in parks:
            print(f"     {arm:<5s} {event:<10s} t={t:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
