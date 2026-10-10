"""W6 throughput report: per-attempt table, inter-placement intervals, lock-on.

    python3 scripts/186_w6_report.py logs/w6/10_battery_twoline_1.log ...
    python3 scripts/186_w6_report.py logs/w6/*_battery_*.log --label w6

Pure text parsing of one or more pick-and-place logs (no simulator). The
metric definitions are pre-registered in `logs/w6/SPEC.md`; in short:

* a **placement** is the attempt's `sim_end` (`t1`): the moment the release,
  its settle/retreat and the attempt's book-keeping have completed
  (`note_result`). The log does not carry the exact release tick, so `t1` is
  used consistently for both arms; the post-release tail is part of every
  span and cancels in an interval between two similar attempts;
* the **inter-placement interval** is the `t1` difference between consecutive
  placements of one arm. The **pooled** interval sorts all arms' placements by
  `t1` and attributes each gap to the arm of the *later* placement (the arm
  that closed the interval); the attribution split is printed;
* the **lock-on latency** is the gap from the previous attempt's end (`t1`) to
  this attempt's `[biarm] <arm>: station acquired` line. In the two-line
  worker the selection happens in the same run-permit segment as the
  acquisition (the default `FRUIT_BIARM_START_GAP=0` adds no wait), so the
  acquisition time is the selection time. Starved slots
  (`<arm>: no eligible fruit; station released`) inside the window are
  included in the latency and also counted per interval (the `retries`
  column); they are the polling the directive is about;
* the **idle fraction** per arm is `sum(t0_next - t1_prev) / (t1_last -
  t0_first)`: the share of the arm's active span that is not inside an
  attempt (park, feed, retries, selection, pre-pose);
* the **prefetch fields** (W6-C L1, `FRUIT_BIARM_PREFETCH=1`): the worker's
  `prefetch reserved/consumed/stale` lines give the **reservation age**
  (selection -> station acquired) and the stale drops; the
  `[biarm] <arm>: handover at t=` line (the wait-loop break) gives
  **wait-to-handover** (station acquired -> handover). Under prefetch the
  lock-on above is park+gap, not the selection latency - it is reported but
  labelled;
* **throughput** is placed fruit per simulated minute over the batch span
  (`t_last_end - t_first_start`, the run's own `[biarm] ... fruits/min`
  denominator) and over the placement window (`t_last_place - t_first_place`,
  the steady-state reading). The per-arm rows use the arm's own span;
* the **interval decomposition** (W6-A follow-up, W6-B) aggregates the
  per-attempt `[cycle]` marks: each attempt span splits into the pre-pose move
  (`prepose`), hover move (`hover`), wait-for-arrival + descent (`descent`),
  close (`close`), grip/probe (`grip`), lift carry (`lift`), place carry
  (`place`), release (`release`), retreat (`return`) and the book-keeping tail
  (`end` plus any span after the last mark). The `[cycle]` lines print at
  attempt *completion* while the `[run]` lines print in *start* order
  (two-line), so the two sequences are matched by total duration (0.35 s
  tolerance), the same convention as `scripts/179_w2_bands.py`. The report
  prints per-arm + pooled means and, when an arm has >= 2 placements, the
  placement-interval decomposition (interval = idle + the attempts inside it);
* percentiles: `p90` is the nearest-order statistic at index `int(0.9 * n)` of
  the ascending sample (`sorted[min(n-1, int(0.9n))]`), not an interpolated
  quantile.

Two-line logs carry the per-attempt `[run] attempt N (arm): ... sim=t0-t1s`
lines and the `[biarm]` acquisition/retry lines; single-arm logs carry the
window on the `[run] attempt N: ...` outcome line (W6+). A run that predates
the window (single-arm) still prints its table but no intervals; `[run]` rows
with `t0 <= 0` or `t1 <= 0` (an attempt that never got a sim window, e.g. a
watchdog timeout) are dropped from the timed aggregates and counted.
"""

from __future__ import annotations

import argparse
import re
import statistics

# -- two-line per-attempt lines -------------------------------------------- #
PICK = re.compile(
    r"\[run\] attempt (?P<slot>\d+) \((?P<arm>\w+)\): picking (?P<fruit>\w+) "
    r"grade (?P<grade>\w+) into output lane (?P<lane>\d+) at "
    r"\((?P<x>[-\d.]+), (?P<y>[+\-\d.]+)\) sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s"
)
OUTCOME = re.compile(
    r"\[run\] attempt (?P<slot>\d+) \((?P<arm>\w+)\): grasped=(?P<grasped>True|False) "
    r"placed=(?P<placed>True|False) lift=(?P<lift>[+\-\d.]+) m "
    r"force=(?P<force>[\d.]+) N sim=(?P<span>[\d.]+)s notes=(?P<notes>\[.*\])"
)
# -- single-arm per-attempt lines (the W6 outcome line carries the window) -- #
SINGLE_PICK = re.compile(
    r"\[run\] attempt (?P<slot>\d+): picking (?P<fruit>\w+) grade (?P<grade>\w+) "
    r"into output lane (?P<lane>\d+) at"
)
SINGLE_OUTCOME = re.compile(
    r"\[run\] attempt (?P<slot>\d+): grasped=(?P<grasped>True|False) "
    r"placed=(?P<placed>True|False) lift=(?P<lift>[+\-\d.]+) m "
    r"force=(?P<force>[\d.]+) N notes=(?P<notes>\[.*?\])"
    r"(?: sim=(?P<t0>[\d.]+)-(?P<t1>[\d.]+)s)?"
)
SINGLE_NOFRUIT = re.compile(r"\[run\] attempt (?P<slot>\d+): no eligible fruit")
# -- bimanual events --------------------------------------------------------- #
RESULT = re.compile(
    r"\[biarm\] result (?P<arm>\w+) index=(?P<index>\d+) (?P<fruit>\w+) "
    r"grasped=(?P<grasped>True|False) placed=(?P<placed>True|False) "
    r"lift=(?P<lift>[+\-\d.]+) force=(?P<force>[\d.]+) sim=(?P<span>[\d.]+)s"
)
ACQUIRED = re.compile(r"\[biarm\] (?P<arm>\w+): station acquired at t=(?P<t>[\d.]+)s")
NO_ELIGIBLE = re.compile(r"\[biarm\] (?P<arm>\w+): no eligible fruit")
#: W6-C L1 prefetch (`FRUIT_BIARM_PREFETCH=1`, two-line only): the reservation
#: is made at attempt end and consumed (or dropped) at the next slot start.
PREFETCH_RESERVED = re.compile(
    r"\[biarm\] (?P<arm>\w+): prefetch reserved index=(?P<index>\d+) .* at t=(?P<t>[\d.]+)s"
)
PREFETCH_CONSUMED = re.compile(
    r"\[biarm\] (?P<arm>\w+): prefetch consumed index=(?P<index>\d+) "
    r"at t=(?P<t>[\d.]+)s \(age (?P<age>[\d.]+)s\)"
)
PREFETCH_STALE = re.compile(
    r"\[biarm\] (?P<arm>\w+): prefetch stale index=(?P<index>\d+) at t=(?P<t>[\d.]+)s"
)
#: The wait-loop break (the descent handover), printed under prefetch so the
#: report can quote wait-to-handover = handover - station acquired.
HANDOVER = re.compile(r"\[biarm\] (?P<arm>\w+): handover at t=(?P<t>[\d.]+)s")
#: Park trace (`FRUIT_BIARM_PARK_TRACE=1`, pure reporting): the idle split -
#: the gate-blocked time (wait start -> moving) against the return motion
#: (moving -> done). An arm already at ready returns before any of these lines.
PARK_WAIT = re.compile(r"\[biarm\] (?P<arm>\w+): park wait start t=(?P<t>[\d.]+)s")
PARK_MOVING = re.compile(
    r"\[biarm\] (?P<arm>\w+): park moving t=(?P<t>[\d.]+)s \(waited (?P<ticks>\d+) ticks\)"
)
PARK_DONE = re.compile(r"\[biarm\] (?P<arm>\w+): park done t=(?P<t>[\d.]+)s")
SUMMARY = re.compile(
    r"\[biarm\] (?P<slots>\d+) pipelined slots, (?P<attempts>\d+) attempts, "
    r"(?P<successes>\d+) successes, (?P<span>[\d.]+)s sim span, "
    r"(?P<per_attempt>[\d.]+)s/attempt, (?P<per_success>[\d.]+)s/success, "
    r"(?P<rate>[\d.]+) fruits/min; per arm left=(?P<l_s>\d+)/(?P<l_a>\d+) "
    r"right=(?P<r_s>\d+)/(?P<r_a>\d+)"
)
# -- per-attempt `[cycle]` marks (FRUIT_CYCLE_REPORT=1) --------------------- #
CYCLE = re.compile(
    r"\[cycle\] attempt (?P<n>\d+): (?P<body>.*?) total=(?P<total>[\d.]+)s"
)
CYCLE_SEG = re.compile(r"(?P<name>\w+)=(?P<dur>[\d.]+)s")
#: Canonical phase order of the `[cycle]` segments (the `_cycle_begin` /
#: `_cycle_mark` labels in `tasks.py`, printed as `next_mark - mark`). An
#: early-return attempt stops at `hover`/`descent`, so a name missing from a
#: line is a zero for that attempt, not an error.
BLOCKS = (
    "prepose", "hover", "descent", "close", "grip",
    "lift", "place", "release", "return", "end",
)


def _first_reason(notes: str) -> str:
    if notes in ("[]", ""):
        return "-"
    text = notes.strip("[]")
    first = text.split(",")[0].strip().strip("'\"")
    return first or "-"


def parse(path: str) -> dict:
    """One log -> {attempts, results, retries, summary}.

    `attempts` is keyed by `[run]` attempt slot (the per-attempt table rows);
    `results` keeps the per-arm `[biarm] result` lines in *completion* order -
    the two sequences are per-arm sequential, so they are zipped afterwards
    (the result line's `index=` is the fruit index, **not** the slot).
    """
    attempts: dict[int, dict] = {}
    results: dict[str, list[dict]] = {"left": [], "right": []}
    retries = {"left": 0, "right": 0}
    summary = None
    cycles: list[dict] = []
    #: Lock-on book-keeping in log order: for each arm, the last acquisition
    #: time and the retries since the previous result.
    last_acq: dict[str, float] = {}
    pending_retries: dict[str, int] = {"left": 0, "right": 0}
    #: W6-C prefetch book-keeping: reservation age per consumed target, stale
    #: drops, and the handover timestamps (wait-to-handover).
    prefetch_age: dict[str, list[float]] = {"left": [], "right": []}
    prefetch_stale: dict[str, int] = {"left": 0, "right": 0}
    handovers: list[tuple[str, float]] = []
    #: Park trace: per arm, the gate-blocked spans and the return-motion spans
    #: (seconds), plus the ticks the gate actually waited.
    park_blocked: dict[str, list[float]] = {"left": [], "right": []}
    park_motion: dict[str, list[float]] = {"left": [], "right": []}
    park_ticks: dict[str, list[int]] = {"left": [], "right": []}
    park_open: dict[str, float | None] = {"left": None, "right": None}
    park_move_at: dict[str, float | None] = {"left": None, "right": None}
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            found = RESULT.search(line)
            if found:
                values = found.groupdict()
                arm = values["arm"]
                results.setdefault(arm, []).append(
                    {
                        "fruit": values["fruit"],
                        "grasped": values["grasped"] == "True",
                        "placed": values["placed"] == "True",
                        "span": float(values["span"]),
                        "acq": last_acq.get(arm),
                        "retries": pending_retries.get(arm, 0),
                    }
                )
                pending_retries[arm] = 0
                continue
            found = ACQUIRED.search(line)
            if found:
                arm = found.group("arm")
                last_acq[arm] = float(found.group("t"))
                continue
            found = NO_ELIGIBLE.search(line)
            if found:
                arm = found.group("arm")
                retries[arm] += 1
                pending_retries[arm] = pending_retries.get(arm, 0) + 1
                continue
            found = PREFETCH_CONSUMED.search(line)
            if found:
                prefetch_age.setdefault(found.group("arm"), []).append(
                    float(found.group("age"))
                )
                continue
            found = PREFETCH_STALE.search(line)
            if found:
                arm = found.group("arm")
                prefetch_stale[arm] = prefetch_stale.get(arm, 0) + 1
                continue
            found = HANDOVER.search(line)
            if found:
                handovers.append((found.group("arm"), float(found.group("t"))))
                continue
            found = PARK_WAIT.search(line)
            if found:
                park_open[found.group("arm")] = float(found.group("t"))
                continue
            found = PARK_MOVING.search(line)
            if found:
                arm = found.group("arm")
                start = park_open.get(arm)
                if start is not None:
                    park_blocked.setdefault(arm, []).append(
                        float(found.group("t")) - start
                    )
                park_ticks.setdefault(arm, []).append(int(found.group("ticks")))
                park_move_at[arm] = float(found.group("t"))
                continue
            found = PARK_DONE.search(line)
            if found:
                arm = found.group("arm")
                start = park_move_at.get(arm)
                if start is not None:
                    park_motion.setdefault(arm, []).append(
                        float(found.group("t")) - start
                    )
                park_move_at[arm] = None
                park_open[arm] = None
                continue
            found = PREFETCH_RESERVED.search(line)
            if found:
                # A reservation without a consumed/stale line at the batch end
                # (budget exhausted) is dropped by the worker; nothing to pair.
                continue
            found = PICK.search(line)
            if found:
                values = found.groupdict()
                entry = attempts.setdefault(int(values["slot"]), {})
                entry.update(
                    {
                        "arm": values["arm"],
                        "fruit": values["fruit"],
                        "grade": values["grade"],
                        "lane": int(values["lane"]),
                        "t0": float(values["t0"]),
                        "t1": float(values["t1"]),
                        "span": float(values["t1"]) - float(values["t0"]),
                    }
                )
                continue
            found = OUTCOME.search(line)
            if found:
                values = found.groupdict()
                entry = attempts.setdefault(int(values["slot"]), {})
                entry.update(
                    {
                        "grasped": values["grasped"] == "True",
                        "placed": values["placed"] == "True",
                        "notes": values["notes"],
                    }
                )
                continue
            found = SINGLE_PICK.search(line)
            if found:
                values = found.groupdict()
                attempts.setdefault(int(values["slot"]), {}).update(
                    {
                        "arm": "single",
                        "fruit": values["fruit"],
                        "grade": values["grade"],
                        "lane": int(values["lane"]),
                    }
                )
                continue
            found = SINGLE_OUTCOME.search(line)
            if found:
                values = found.groupdict()
                entry = attempts.setdefault(int(values["slot"]), {})
                entry.update(
                    {
                        "grasped": values["grasped"] == "True",
                        "placed": values["placed"] == "True",
                        "notes": values["notes"],
                    }
                )
                if values.get("t0") and values.get("t1"):
                    entry["t0"] = float(values["t0"])
                    entry["t1"] = float(values["t1"])
                    entry["span"] = entry["t1"] - entry["t0"]
                continue
            found = SINGLE_NOFRUIT.search(line)
            if found:
                attempts.setdefault(int(found.group("slot")), {}).update(
                    {"arm": "single", "no_fruit": True}
                )
                continue
            found = CYCLE.search(line)
            if found:
                cycles.append(
                    {
                        "n": int(found.group("n")),
                        "blocks": [
                            (m.group("name"), float(m.group("dur")))
                            for m in CYCLE_SEG.finditer(found.group("body"))
                        ],
                        "total": float(found.group("total")),
                    }
                )
                continue
            found = SUMMARY.search(line)
            if found:
                summary = found.groupdict()

    # Zip each arm's timed `[run]` rows with its `[biarm] result` lines (both
    # per-arm sequential) and carry the acquisition/retry book-keeping over;
    # fall back to the live result fields when a `[run]` outcome is missing.
    mismatches = 0
    for arm, arm_results in results.items():
        timed = [
            row
            for _, row in sorted(attempts.items())
            if row.get("arm") == arm and "t0" in row and "t1" in row
        ]
        for row, result in zip(timed, arm_results):
            row["acq"] = result["acq"]
            row["retries"] = result["retries"]
            row.setdefault("fruit", result["fruit"])
            if "grasped" not in row:
                row["grasped"] = result["grasped"]
                row["placed"] = result["placed"]
                row["notes"] = "-"
            if abs((row["t1"] - row["t0"]) - result["span"]) > 0.35:
                mismatches += 1
    return {
        "attempts": attempts,
        "results": results,
        "retries": retries,
        "summary": summary,
        "cycles": cycles,
        "mismatches": mismatches,
        "prefetch_age": prefetch_age,
        "prefetch_stale": prefetch_stale,
        "handovers": handovers,
        "park_blocked": park_blocked,
        "park_motion": park_motion,
        "park_ticks": park_ticks,
    }


def _stats(values: list[float]) -> str:
    """mean/p50/p90/min/max string; `p90` is the nearest-order statistic at
    index `int(0.9 * n)` of the ascending sample (never interpolated)."""
    if not values:
        return "n/a"
    ordered = sorted(values)
    median = statistics.median(ordered)
    return (
        f"n={len(ordered)} mean {statistics.fmean(ordered):.2f}s "
        f"p50 {median:.2f}s p90 {ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))]:.2f}s "
        f"min {ordered[0]:.2f}s max {ordered[-1]:.2f}s"
    )


def _match_cycles(rows: list[dict], cycles: list[dict], tol: float = 0.35) -> int:
    """Attach the closest-duration `[cycle]` breakdown to each timed attempt.

    The `[cycle]` line prints at attempt *completion* while the two-line
    `[run]` lines print in *start* order, so the two sequences are paired by
    total duration, closest first (the same convention as
    `scripts/179_w2_bands.py`). Returns the number of attempts without a
    matched cycle line.
    """
    pending = list(cycles)
    matched = 0
    for row in rows:
        span = row["t1"] - row["t0"]
        best_index, best_delta = None, tol
        for index, cycle in enumerate(pending):
            delta = abs(cycle["total"] - span)
            if delta < best_delta:
                best_index, best_delta = index, delta
        if best_index is None:
            continue
        cycle = pending.pop(best_index)
        row["blocks"] = dict(cycle["blocks"])
        row["cycle_total"] = cycle["total"]
        matched += 1
    return len(rows) - matched


def report(path: str) -> bool:
    data = parse(path)
    rows = [dict(row, slot=slot) for slot, row in sorted(data["attempts"].items())]
    real = [row for row in rows if not row.get("no_fruit")]
    killed = False
    if not real and any(data["results"].values()):
        # A killed batch (or a log read mid-run) has no `[run]` lines; the
        # `[biarm] result` lines still walk the outcomes (no sim windows).
        rows = []
        slot = 0
        for arm in sorted(data["results"]):
            for result in data["results"][arm]:
                rows.append(
                    {
                        "slot": slot,
                        "arm": arm,
                        "fruit": result["fruit"],
                        "grasped": result["grasped"],
                        "placed": result["placed"],
                        "notes": "",
                        "live_span": result["span"],
                    }
                )
                slot += 1
        real = rows
        killed = True
    print(f"== {path}")
    print("   percentiles are nearest-order statistics (p90 = sorted[int(0.9*n)], not interpolated)")
    if killed:
        print(
            f"   warning: no [run] lines (killed batch?); using the "
            f"{len(rows)} [biarm] result lines"
        )

    if not real:
        print("   no attempt lines found")
        return False
    two_line = (
        any(row.get("acq") is not None for row in real) or bool(data["summary"])
    )

    # Per-attempt table.
    print(
        f"   {'slot':>4} {'arm':<6} {'fruit':<10} {'grade':<5} {'lane':<4} "
        f"{'t0':>7} {'t1':>7} {'span':>6} {'grasp':<5} {'place':<5}  notes"
    )
    for row in rows:
        if row.get("no_fruit"):
            print(f"   {row['slot']:>4} {'-':<6} no eligible fruit")
            continue
        t0 = f"{row['t0']:>7.1f}" if "t0" in row else f"{'-':>7}"
        t1 = f"{row['t1']:>7.1f}" if "t1" in row else f"{'-':>7}"
        span_value = row.get("span", row.get("live_span"))
        span = (
            f"{span_value:>6.1f}"
            if span_value is not None
            else f"{'-':>6}"
        )
        print(
            f"   {row['slot']:>4} {row.get('arm', '?'):<6} {row.get('fruit', '?'):<10} "
            f"{row.get('grade', '?'):<5} {row.get('lane', '-'):<4} {t0} {t1} {span} "
            f"{str(row.get('grasped', '-')):<5} {str(row.get('placed', '-')):<5}  "
            f"{_first_reason(row.get('notes', ''))}"
        )

    timed = [row for row in real if "t0" in row and "t1" in row]
    with_times = [
        row for row in timed if row.get("t0", 0.0) > 0.0 and row.get("t1", 0.0) > 0.0
    ]
    dropped = len(timed) - len(with_times)
    # A placement is a placed outcome regardless of the window: count over all
    # attempt rows, so a pre-W6 single-arm log (no `sim=` window) still reads
    # its placed/failed counts instead of the misleading `placements=0`.
    placements = [row for row in real if row.get("placed")]
    failures = [
        row for row in real if not (row.get("grasped") and row.get("placed"))
    ]
    print(
        f"   attempts={len(real)} placements={len(placements)} "
        f"failures={len(failures)} window="
        + (
            "yes"
            if with_times
            else ("no (killed batch)" if killed else "no (pre-W6 log)")
        )
    )
    if dropped:
        print(f"   dropped {dropped} attempt row(s) with t0/t1 <= 0 (no sim window)")
    if data.get("mismatches"):
        print(
            f"   warning: {data['mismatches']} attempt/result span mismatch(es) - "
            "check the per-arm event order"
        )

    if not with_times:
        placed_n = sum(1 for row in real if row.get("placed"))
        print(
            f"   window absent ({'killed batch' if killed else 'pre-W6 log'}): "
            f"placed {placed_n}/{len(real)}; intervals and lock-on need the "
            "W6 outcome window"
        )
        if data["summary"]:
            s = data["summary"]
            print(
                f"   throughput: {s['successes']}/{s['attempts']} placed, "
                f"{float(s['span']):.1f}s span, {float(s['rate']):.2f} placed/min "
                f"(per arm left={s['l_s']}/{s['l_a']} right={s['r_s']}/{s['r_a']})"
            )
        return True

    # Inter-placement intervals.
    arms = sorted({row["arm"] for row in with_times})
    placed_times = [row for row in with_times if row.get("placed")]
    print("   inter-placement intervals (t1 of consecutive placements):")
    for arm in arms:
        marks = sorted(row["t1"] for row in placed_times if row["arm"] == arm)
        gaps = [b - a for a, b in zip(marks, marks[1:])]
        print(f"     {arm:<6}: {_stats(gaps)}")
    pooled_marks = sorted((row["t1"], row["arm"]) for row in placed_times)
    pooled_gaps: dict[str, list[float]] = {arm: [] for arm in arms}
    for (t_a, _arm_a), (t_b, arm_b) in zip(pooled_marks, pooled_marks[1:]):
        pooled_gaps.setdefault(arm_b, []).append(t_b - t_a)
    pooled_flat = [
        t_b - t_a for (t_a, _), (t_b, _) in zip(pooled_marks, pooled_marks[1:])
    ]
    split = ", ".join(
        f"{arm} {len(gaps)}" for arm, gaps in pooled_gaps.items() if gaps
    )
    print(f"     pooled : {_stats(pooled_flat)} (attributed to the later arm: {split})")

    # Lock-on latencies (two-line only).
    if two_line:
        print("   lock-on latency (previous attempt end -> this attempt's station acquired):")
        for arm in arms:
            arm_rows = sorted(
                (row for row in with_times if row["arm"] == arm and row.get("acq") is not None),
                key=lambda row: row["t0"],
            )
            gaps = []
            retries = []
            for previous, row in zip(arm_rows, arm_rows[1:]):
                gaps.append(row["acq"] - previous["t1"])
                retries.append(row.get("retries", 0))
            detail = (
                f" (retries per interval: {retries})" if retries else ""
            )
            print(f"     {arm:<6}: {_stats(gaps)}{detail}")
        # Starved acquisitions before the first attempt are the batch-start prime.
        for arm in arms:
            first = min(
                (row for row in with_times if row["arm"] == arm and row.get("acq") is not None),
                key=lambda row: row["t0"],
                default=None,
            )
            if first is not None and first.get("acq") is not None:
                prime = first["acq"] - min(row["t0"] for row in with_times)
                print(
                    f"     {arm:<6}: pre-first-attempt acquisition {prime:.1f}s after the "
                    f"batch's first attempt started, {first.get('retries', 0)} starved "
                    f"slot(s) before it (batch-start priming)"
                )

    # W6-C prefetch (L1): with `FRUIT_BIARM_PREFETCH=1` the target is selected
    # at the previous attempt's end, so lock-on (arm-free -> selected) is
    # negative by construction. Reservation age (selection -> station acquired)
    # and wait-to-handover (station acquired -> the wait-loop break) keep the
    # interval attributable. Printed only when the log carries the lines.
    prefetch_age = data.get("prefetch_age") or {}
    prefetch_stale = data.get("prefetch_stale") or {}
    handovers = data.get("handovers") or []
    have_prefetch = (
        any(prefetch_age.get(arm) for arm in arms)
        or any(prefetch_stale.get(arm) for arm in arms)
        or bool(handovers)
    )
    if have_prefetch:
        print(
            "   prefetch (reservation age: selection -> station acquired; the "
            "lock-on above is park+gap under prefetch, not select-to-free):"
        )
        for arm in arms:
            ages = list(prefetch_age.get(arm, []))
            stale = int(prefetch_stale.get(arm, 0))
            stale_text = f" (stale dropped: {stale})" if stale else ""
            print(f"     {arm:<6}: {_stats(ages)}{stale_text}")
        waits: dict[str, list[float]] = {arm: [] for arm in arms}
        for handover_arm, handover_t in handovers:
            if handover_arm not in waits:
                continue
            candidates = [
                row
                for row in with_times
                if row["arm"] == handover_arm
                and row["t0"] - 0.5 <= handover_t <= row["t1"] + 0.5
            ]
            if not candidates:
                continue
            row = min(candidates, key=lambda item: abs(item["t0"] - handover_t))
            base = row.get("acq")
            base = float(base) if base is not None else float(row["t0"])
            waits[handover_arm].append(handover_t - base)
        if any(waits.get(arm) for arm in arms):
            print(
                "   wait-to-handover (station acquired -> wait-loop handover):"
            )
            for arm in arms:
                if waits.get(arm):
                    print(f"     {arm:<6}: {_stats(waits[arm])}")

    # Interval decomposition ([cycle] marks; W6-A follow-up). See the module
    # docstring: matched by total duration, per arm + pooled.
    cycles = data.get("cycles", [])
    if cycles:
        unmatched = _match_cycles(with_times, cycles)
        matched = [row for row in with_times if row.get("blocks")]
        if matched:
            print(
                "   interval decomposition ([cycle] marks; mean s per matched attempt):"
            )
            header = (
                f"     {'arm':<6} {'n':>3} "
                + " ".join(f"{name:>7}" for name in BLOCKS)
                + f" {'tail':>6} {'span':>7}"
            )
            print(header)
            for arm in arms + ["pooled"]:
                rows_for = (
                    matched
                    if arm == "pooled"
                    else [row for row in matched if row["arm"] == arm]
                )
                if not rows_for:
                    continue
                cells = " ".join(
                    f"{statistics.fmean(row['blocks'].get(name, 0.0) for row in rows_for):>7.2f}"
                    for name in BLOCKS
                )
                tail = statistics.fmean(
                    row["t1"] - row["t0"] - row["cycle_total"] for row in rows_for
                )
                span = statistics.fmean(row["t1"] - row["t0"] for row in rows_for)
                print(f"     {arm:<6} {len(rows_for):>3} {cells} {tail:>6.2f} {span:>7.2f}")
            if unmatched:
                print(
                    f"     note: {unmatched} timed attempt(s) have no matched "
                    "[cycle] line (not in the means)"
                )
        else:
            print("   interval decomposition: [cycle] lines present but none matched")

        # Placement-interval decomposition per arm: interval = idle + the
        # attempts inside it. A pooled interval interleaves both arms, so only
        # the per-arm split is attributable.
        print(
            "   placement-interval decomposition (interval = idle + attempts inside):"
        )
        for arm in arms:
            arm_rows = sorted(
                (row for row in with_times if row["arm"] == arm),
                key=lambda row: row["t0"],
            )
            arm_places = [row for row in arm_rows if row.get("placed")]
            if len(arm_places) < 2:
                print(f"     {arm:<6}: n/a (<2 placements)")
                continue
            intervals: list[tuple[float, float, list[dict]]] = []
            for previous, current in zip(arm_places, arm_places[1:]):
                inside = [
                    row
                    for row in arm_rows
                    if row["t0"] >= previous["t1"] - 1e-9
                    and row["t1"] <= current["t1"] + 1e-9
                ]
                if not inside:
                    continue
                idle = (inside[0]["t0"] - previous["t1"]) + sum(
                    max(0.0, b["t0"] - a["t1"])
                    for a, b in zip(inside, inside[1:])
                )
                intervals.append((current["t1"] - previous["t1"], idle, inside))
            if not intervals:
                print(f"     {arm:<6}: n/a")
                continue
            n_int = float(len(intervals))
            mean_interval = statistics.fmean(iv for iv, _, _ in intervals)
            mean_idle = statistics.fmean(idle for _, idle, _ in intervals)
            inside_all = [row for _, _, inside in intervals for row in inside]
            inside_matched = [row for row in inside_all if row.get("blocks")]
            block_means = {
                name: statistics.fmean(
                    sum(row["blocks"].get(name, 0.0) for row in inside)
                    for _, _, inside in intervals
                )
                for name in BLOCKS
            }
            block_tail = statistics.fmean(
                sum(
                    (row["t1"] - row["t0"] - row["cycle_total"])
                    if row.get("blocks")
                    else (row["t1"] - row["t0"])
                    for row in inside
                )
                for _, _, inside in intervals
            )
            blocks_text = " ".join(
                f"{name} {block_means[name]:.1f}" for name in BLOCKS
            )
            share = mean_idle / mean_interval * 100.0 if mean_interval else 0.0
            print(
                f"     {arm:<6}: n={len(intervals)} mean {mean_interval:.1f}s = "
                f"idle {mean_idle:.1f}s ({share:.0f}%) + attempts "
                f"{mean_interval - mean_idle:.1f}s"
            )
            print(
                f"            per interval: {blocks_text} tail {block_tail:.1f} "
                f"(attempts decomposed {len(inside_matched)}/{len(inside_all)})"
            )

    # Park trace idle split (`FRUIT_BIARM_PARK_TRACE=1`; mechanism-only runs):
    # the gate-blocked span (wait start -> moving) against the return motion
    # (moving -> done). An arm already at ready returns without any trace line,
    # so n counts real parks only.
    park_blocked = data.get("park_blocked") or {}
    park_motion = data.get("park_motion") or {}
    park_ticks = data.get("park_ticks") or {}
    if any(park_motion.get(arm) for arm in arms):
        print("   park trace (gate-blocked vs return motion; real parks only):")
        for arm in arms:
            blocked = list(park_blocked.get(arm, []))
            motion = list(park_motion.get(arm, []))
            if not motion and not blocked:
                continue
            blocked_text = (
                f"blocked {sum(blocked):.1f}s (mean {statistics.fmean(blocked):.1f}s)"
                if blocked
                else "blocked 0.0s"
            )
            motion_text = (
                f"motion {sum(motion):.1f}s (mean {statistics.fmean(motion):.1f}s)"
                if motion
                else "motion 0.0s"
            )
            print(f"     {arm:<6}: n={len(motion)} {blocked_text} + {motion_text}")
            ticks = park_ticks.get(arm) or []
            if ticks:
                print(
                    f"            gate waits: {len(ticks)} parks, "
                    f"{sum(ticks)} ticks total ({sum(ticks) / 120.0:.1f}s at 120 Hz)"
                )

    # Idle fractions and per-arm throughput.
    print("   per-arm spans:")
    for arm in arms:
        arm_rows = sorted(
            (row for row in with_times if row["arm"] == arm), key=lambda row: row["t0"]
        )
        t0_first = arm_rows[0]["t0"]
        t1_last = max(row["t1"] for row in arm_rows)
        span = max(0.0, t1_last - t0_first)
        idle = sum(
            max(0.0, b["t0"] - a["t1"]) for a, b in zip(arm_rows, arm_rows[1:])
        )
        wins = sum(1 for row in arm_rows if row.get("placed"))
        fraction = idle / span * 100.0 if span else 0.0
        rate = wins / span * 60.0 if span else 0.0
        print(
            f"     {arm:<6}: span {span:.1f}s, idle {idle:.1f}s ({fraction:.0f}%), "
            f"{wins}/{len(arm_rows)} placed, {rate:.2f} placed/min arm"
        )

    # Throughput from the per-attempt windows.
    t_first = min(row["t0"] for row in with_times)
    t_last = max(row["t1"] for row in with_times)
    batch_span = max(1e-9, t_last - t_first)
    place_span = (
        max(1e-9, pooled_marks[-1][0] - pooled_marks[0][0])
        if len(placed_times) >= 2
        else None
    )
    print(
        f"   throughput (batch span {batch_span:.1f}s): "
        f"{len(placements)}/{len(real)} placed = {len(placements) / batch_span * 60:.2f} placed/min"
        + (
            f"; placement window {place_span:.1f}s -> "
            f"{(len(placed_times) - 1) / place_span * 60:.2f} placed/min steady state"
            if place_span
            else ""
        )
    )
    if data["summary"]:
        s = data["summary"]
        print(
            f"   run summary line: {s['successes']}/{s['attempts']} placed, "
            f"{float(s['span']):.1f}s span, {float(s['per_attempt']):.1f}s/attempt, "
            f"{float(s['rate']):.2f} placed/min; per arm "
            f"left={s['l_s']}/{s['l_a']} right={s['r_s']}/{s['r_a']}"
        )
    if two_line and (data["retries"]["left"] or data["retries"]["right"]):
        # A starved slot is attributed to the interval that follows it (or to
        # the batch-start prime for the first); the slots after the last
        # attempt of an arm have no following acquisition and are only the
        # tail count.
        attributed = {
            arm: sum(row.get("retries", 0) for row in with_times if row["arm"] == arm)
            for arm in ("left", "right")
        }
        tail = {
            arm: data["retries"][arm] - attributed[arm] for arm in ("left", "right")
        }
        print(
            f"   starved slots: left {data['retries']['left']}, "
            f"right {data['retries']['right']} "
            f"(attributed to a lock-on interval or the batch-start prime: "
            f"left {attributed['left']}, right {attributed['right']}; "
            f"trailing before the batch end: left {tail['left']}, right {tail['right']})"
        )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+")
    parser.add_argument("--label", default=None, help="echoed in the header")
    args = parser.parse_args()
    if args.label:
        print(f"# W6 report: {args.label}")
    ok = True
    for path in args.logs:
        ok = report(path) and ok
        print()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
