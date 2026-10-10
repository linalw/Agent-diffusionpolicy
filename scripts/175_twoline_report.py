"""Report a v9/V2 two-line bimanual run (throughput, starvation, idle, routing).

    python3 scripts/175_twoline_report.py logs/v2/10_rate_twoline_1.log ...
    python3 scripts/175_twoline_report.py logs/v2/*_rate_twoline_*.log --label 10x5

Pure text parsing of one pick-and-place log (no simulator). For each file it
prints:

* the `[biarm] two-line scheduler` geometry line and the per-station pre-pose
  solve residuals;
* per-arm station slots, `no eligible fruit` events (the delivered starvation:
  the fraction of slots an arm could not fill) and attempts/successes, plus the
  steady-state split: misses acquired before the arm's first attempt are the
  batch-start belt-prime, reported separately rather than dropped (the V3
  review of the V2 44.4 % note);
* **idle per turn** per arm: from the `[run] attempt ... sim=t0-t1s` windows,
  the total gap between one attempt's end and the arm's next attempt start,
  divided by the number of turns (the waiting the owner's directive is about);
* the **routing crosstab**: attempts by grade vs output lane (the grade-bias
  semantics change: +Y is the left arm's stream, mostly A; -Y the right's,
  mostly B/C, with the crossover counts);
* the throughput from the `[biarm] ... pipelined slots` summary line and the
  clearance trace when the run recorded one - the *exact* minimum is read from
  the appended `.jsonl` (`min_m`, 5 decimals) and the log's rounded "N mm"
  value is only printed alongside it (the log rounds to whole mm: 2.58 -> "3").
"""

from __future__ import annotations

import argparse
import re

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
RESULT = re.compile(
    r"\[biarm\] result (?P<arm>\w+) index=(?P<index>\d+) (?P<fruit>\w+) "
    r"grasped=(?P<grasped>True|False) placed=(?P<placed>True|False) "
    r"lift=(?P<lift>[+\-\d.]+) force=(?P<force>[\d.]+) sim=(?P<span>[\d.]+)s"
)
ACQUIRED = re.compile(r"\[biarm\] (?P<arm>\w+): station acquired at t=(?P<t>[\d.]+)s")
NO_ELIGIBLE = re.compile(r"\[biarm\] (?P<arm>\w+): no eligible fruit")
SUMMARY = re.compile(
    r"\[biarm\] (?P<slots>\d+) pipelined slots, (?P<attempts>\d+) attempts, "
    r"(?P<successes>\d+) successes, (?P<span>[\d.]+)s sim span, "
    r"(?P<per_attempt>[\d.]+)s/attempt, (?P<per_success>[\d.]+)s/success, "
    r"(?P<rate>[\d.]+) fruits/min; per arm left=(?P<l_s>\d+)/(?P<l_a>\d+) "
    r"right=(?P<r_s>\d+)/(?P<r_a>\d+)"
)
CLEARANCE = re.compile(
    r"\[biarm\] clearance trace: min link separation (?P<mm>[-\d.]+) mm "
    r"at t=(?P<t>[\d.]+)s \((?P<left>\w+) vs (?P<right>\w+)\), (?P<n>\d+) samples"
)
CLEARANCE_APPEND = re.compile(r"\[biarm\] clearance trace appended -> (?P<path>\S+)")
STATIONS = re.compile(r"\[biarm\] two-line scheduler: (?P<text>.*)")
GRADE_ROUTING = re.compile(r"\[biarm\] grade routing: (?P<text>.*)")
SOLVE = re.compile(r"\[biarm\] station (?P<arm>\w+) y=(?P<y>[+\-\d.]+): pre-pose solve residual (?P<mm>[\d.]+) mm")
STATS = re.compile(r"\[stats\] attempts=(?P<attempts>\d+) successes=(?P<successes>\d+) .*?sim=(?P<sim>[\d.]+)s total")


def _jsonl_clearance(path: str) -> tuple[float, int, int] | None:
    """Exact `(min_mm, samples, under_30mm)` from an appended clearance `.jsonl`.

    The log's clearance line rounds to whole millimetres (2.58 -> "3 mm"); the
    jsonl rows carry `min_m` with 5 decimals. The file is append-mode per
    batch, so a multi-batch log's file holds the union - report it as such.
    """
    import json

    try:
        rows = [
            json.loads(line)
            for line in open(path, encoding="utf-8", errors="ignore")
            if line.strip()
        ]
    except OSError:
        return None
    values = [float(row["min_m"]) for row in rows if "min_m" in row]
    if not values:
        return None
    return min(values) * 1000.0, len(values), sum(1 for v in values if v < 0.030)


def report(path: str) -> bool:
    acquired = {"left": 0, "right": 0}
    starved = {"left": 0, "right": 0}
    #: Timed miss list per arm: (acquire time of the slot, miss). The batch-start
    #: priming (the belt has not delivered to the stations yet) is separated from
    #: the steady-state starvation the directive is about.
    misses: dict[str, list[tuple[float, int]]] = {"left": [], "right": []}
    last_acquired = {"left": 0.0, "right": 0.0}
    attempts = {"left": 0, "right": 0}
    wins = {"left": 0, "right": 0}
    spans: dict[str, list[tuple[float, float]]] = {"left": [], "right": []}
    routes: dict[tuple[str, int], int] = {}
    summary = None
    clearance = None
    clearance_path = None
    stats = None
    station_line = None
    grade_routing = None
    solves: list[str] = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            found = SOLVE.search(line)
            if found:
                solves.append(
                    f"{found.group('arm')} y={found.group('y')} "
                    f"{found.group('mm')} mm"
                )
                continue
            found = GRADE_ROUTING.search(line)
            if found:
                grade_routing = found.group("text").strip()
                continue
            found = STATIONS.search(line)
            if found:
                station_line = found.group("text").strip()
                continue
            found = ACQUIRED.search(line)
            if found:
                arm = found.group("arm")
                acquired[arm] += 1
                last_acquired[arm] = float(found.group("t"))
                continue
            found = NO_ELIGIBLE.search(line)
            if found:
                arm = found.group("arm")
                starved[arm] += 1
                misses[arm].append((last_acquired[arm], 1))
                continue
            found = PICK.search(line)
            if found:
                values = found.groupdict()
                key = (values["grade"], int(values["lane"]))
                routes[key] = routes.get(key, 0) + 1
                spans[values["arm"]].append(
                    (float(values["t0"]), float(values["t1"]))
                )
                continue
            found = OUTCOME.search(line)
            if found:
                values = found.groupdict()
                attempts[values["arm"]] += 1
                if values["grasped"] == "True" and values["placed"] == "True":
                    wins[values["arm"]] += 1
                continue
            found = SUMMARY.search(line)
            if found:
                summary = found.groupdict()
                continue
            found = CLEARANCE.search(line)
            if found:
                clearance = found.groupdict()
                continue
            found = CLEARANCE_APPEND.search(line)
            if found:
                clearance_path = found.group("path")
                continue
            found = STATS.search(line)
            if found:
                stats = found.groupdict()

    print(f"== {path}")
    if station_line:
        print(f"   geometry: {station_line}")
    if solves:
        print("   station pre-pose solves: " + "; ".join(solves))
    for arm in ("left", "right"):
        total = acquired[arm]
        share = f"{starved[arm] / total * 100:.1f}%" if total else "n/a"
        print(
            f"   {arm:<5}: slots={total} no-eligible={starved[arm]} ({share} of slots) "
            f"attempts={attempts[arm]} placed={wins[arm]}/{attempts[arm]}"
        )
        windows = sorted(spans[arm])
        if windows:
            # Steady-state starvation: the batch-start priming slots (acquired
            # before this arm's first attempt started) are the driver's feed
            # spin-up, not structural waiting; report them separately, never
            # silently dropped.
            first = windows[0][0]
            warmup = [t for t, _ in misses[arm] if t + 1e-9 < first]
            steady_total = total - len(warmup)
            steady_missed = starved[arm] - len(warmup)
            steady_share = (
                f"{steady_missed / steady_total * 100:.1f}%" if steady_total else "n/a"
            )
            line = (
                f"         steady-state (after the first attempt at {first:.1f}s): "
                f"no-eligible={steady_missed}/{steady_total} ({steady_share})"
            )
            if warmup:
                line += (
                    f"; {len(warmup)} batch-start miss(es) excluded "
                    f"(t={min(warmup):.1f}-{max(warmup):.1f}s)"
                )
            print(line)
        if len(windows) >= 2:
            # Idle per turn: the dead time between one attempt's end and this
            # arm's next attempt start (the arm waiting for a target/its slot).
            gaps = [
                max(0.0, windows[i + 1][0] - windows[i][1])
                for i in range(len(windows) - 1)
            ]
            idle = sum(gaps)
            span = windows[-1][1] - windows[0][0]
            print(
                f"         idle between turns: {idle:.1f}s over {len(gaps)} gaps "
                f"(median {sorted(gaps)[len(gaps) // 2]:.1f}s), {idle / max(span, 1e-9) * 100:.0f}% "
                f"of the {span:.1f}s arm span"
            )
    crossovers = routes.get(("A", 1), 0) + sum(
        count for (grade, lane), count in routes.items() if grade != "A" and lane == 0
    )
    total_picked = sum(routes.values())
    if routes:
        parts = ", ".join(
            f"{grade}->lane{lane}: {count}" for (grade, lane), count in sorted(routes.items())
        )
        print(
            f"   routing: {parts} (crossovers {crossovers}/{total_picked} = "
            f"{crossovers / max(1, total_picked) * 100:.0f}%)"
        )
    if grade_routing:
        # The W3 purity report, printed by `run_bimanual` per batch.
        print(f"   grade routing: {grade_routing}")
    if summary:
        s = summary
        print(
            f"   throughput: {s['successes']}/{s['attempts']} placed, "
            f"{float(s['span']):.1f}s span, {float(s['per_attempt']):.1f}s/attempt, "
            f"{float(s['rate']):.2f} placed/min "
            f"(per arm left={s['l_s']}/{s['l_a']} right={s['r_s']}/{s['r_a']})"
        )
    elif stats:
        print(f"   [stats]: {stats}")
    if clearance:
        exact = _jsonl_clearance(clearance_path) if clearance_path else None
        if exact is not None:
            min_mm, samples, under30 = exact
            print(
                f"   clearance: min {min_mm:.2f} mm at "
                f"t={float(clearance['t']):.2f}s ({clearance['left']} vs "
                f"{clearance['right']}), {samples} samples, {under30} <30 mm "
                f"(jsonl {clearance_path}; log rounds to "
                f"{float(clearance['mm']):.0f} mm)"
            )
        else:
            print(
                f"   clearance: min {float(clearance['mm']):.0f} mm at "
                f"t={float(clearance['t']):.2f}s ({clearance['left']} vs "
                f"{clearance['right']}), {clearance['n']} samples"
                + (f" (jsonl {clearance_path} unreadable)" if clearance_path else "")
            )
    return bool(summary or stats)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+")
    parser.add_argument("--label", default=None)
    args = parser.parse_args()
    ok = True
    for path in args.logs:
        ok = report(path) and ok
        print()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
