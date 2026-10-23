#!/usr/bin/env python3
"""P33 phase 1 report: the bed's delivered density at the shipped cadence.

    python3 logs/p33/phase1_report.py logs/p33/10_twoline_control.log ...

Pure text parsing (no simulator). For every log prints:

* the two-line summary (placed/attempts, per arm, span) or the single-arm
  `[stats]` row;
* the delivered approach band at the pump instants (`[bed-pump] band=X/10`):
  the observed values in line order, min/mean/max, and how many rows are at
  the 10-row design cap. **This is the density proxy P32 phase C quoted**;
* the per-selection census (`[bed-sel]`): for the two-line the new
  `arm=`/`window=` row, for the single arm the driver's `attempt` row -
  `window` is the number of candidates the moving catch's floor admits at the
  selection instant (the number the A/B is about);
* the `[bed] stats` counters (`late_dropped`, `rebased`, `holds`,
  `supply_skipped`, `fell_off`, `reached_end`, `live`);
* the `[feed] two-line: ... (batch)` row when the mid-attempt pump ran;
* the failure list (`[biarm] result ... placed=False`, `[run] attempt ...
  placed=False`) with each attempt's first note;
* the wall window, read from the sibling `<name>.driver.log`
  (`[claim_run] claimed the simulator HH:MM:SS` -> `[claim_run] exit=...`).

No claim is derived that the log does not contain: a missing row prints `-`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import statistics
from pathlib import Path

PUMP = re.compile(
    r"\[bed-pump\] t=(?P<t>[\d.]+) next=(?P<next>[-\d.]+) lag=(?P<lag>[+\-\d.]+) "
    r"due=(?P<due>\d+) rows=(?P<rows>\d+) band=(?P<band>\d+)/(?P<band_max>\d+)"
)
PICK_ROW = re.compile(
    r"\[bed-sel\] arm=(?P<arm>\w+) slot=(?P<slot>\d+) t=(?P<t>[\d.]+) "
    r"live=(?P<live>\d+) on_belt=(?P<on_belt>\d+) admitted=(?P<admitted>\d+) "
    r"window=(?P<window>\d+) (?:band=(?P<band>\d+)/(?P<band_cap>\d+) )?"
)
ATTEMPT_ROW = re.compile(
    r"\[bed-sel\] attempt (?P<attempt>\d+) t=(?P<t>[\d.]+) "
    r"live=(?P<live>\d+) on_belt=(?P<on_belt>\d+) admitted=(?P<admitted>\d+) "
    r"window=(?P<window>\d+)"
)
BED_STATS = re.compile(
    r"\[bed\] stats draws=(?P<draws>\d+) placed=(?P<placed>\d+) "
    r"live_recycled=(?P<recycled>\d+)/(?P<draws2>\d+).*?"
    r"holds=(?P<holds>\d+) refused=(?P<refused>\d+) rebased=(?P<rebased>\d+) "
    r"late_dropped=(?P<late>[\d.]+)s fell_off=(?P<fell>\d+) "
    r"reached_end=(?P<reached>\d+) sweeps=(?P<sweeps>\d+) swept=(?P<swept>\d+) "
    r"supply_skipped=(?P<skipped>\d+) live=(?P<live>\d+)"
)
FEED_ROW = re.compile(
    r"\[feed\] two-line: updates=(?P<updates>\d+) ticks=(?P<ticks>\d+) "
    r"stride=(?P<stride>\d+) released=\+(?P<released>\d+) "
    r"placed=\+(?P<placed>\d+) skipped=\+(?P<skipped>\d+)"
)
BIARM_SUM = re.compile(
    r"\[biarm\] (?P<slots>\d+) pipelined slots, (?P<attempts>\d+) attempts, "
    r"(?P<successes>\d+) successes, (?P<span>[\d.]+)s sim span, "
    r"(?P<per_attempt>[\d.]+)s/attempt, (?P<per_success>[\d.]+)s/success, "
    r"(?P<rate>[\d.]+) fruits/min; per arm left=(?P<l_s>\d+)/(?P<l_a>\d+) "
    r"right=(?P<r_s>\d+)/(?P<r_a>\d+)"
)
BIARM_RESULT = re.compile(
    r"\[biarm\] result (?P<arm>\w+) index=(?P<index>\d+) (?P<fruit>\w+) "
    r"grasped=(?P<grasped>\w+) placed=(?P<placed>\w+)"
)
RUN_RESULT = re.compile(
    r"\[run\] attempt (?P<attempt>\d+): grasped=(?P<grasped>\w+) "
    r"placed=(?P<placed>\w+)"
)
STATS = re.compile(
    r"\[stats\] attempts=(?P<attempts>\d+) successes=(?P<successes>\d+) "
    r"diverted=(?P<diverted>\d+)"
)
CLAIMED = re.compile(r"\[claim_run\] claimed the simulator (?P<time>\d\d:\d\d:\d\d)")
EXITED = re.compile(r"\[claim_run\] exit=(?P<code>\d+) (?P<time>\d\d:\d\d:\d\d)")


def _hms(text: str) -> int:
    hour, minute, second = (int(part) for part in text.split(":"))
    return hour * 3600 + minute * 60 + second


def _wall(path: Path) -> str:
    driver = path.with_suffix(".driver.log")
    if not driver.exists():
        return "-"
    claimed = exited = None
    for line in driver.read_text(errors="replace").splitlines():
        match = CLAIMED.search(line)
        if match:
            claimed = match.group("time")
        match = EXITED.search(line)
        if match:
            exited = match.group("time")
    if not claimed or not exited:
        return "-"
    delta = _hms(exited) - _hms(claimed)
    if delta < 0:
        delta += 24 * 3600
    return f"{delta} s ({claimed}->{exited})"


def _fmt(values: list[int]) -> str:
    if not values:
        return "-"
    return (
        f"n={len(values)} min={min(values)} mean={statistics.fmean(values):.1f} "
        f"max={max(values)} >=cap={sum(1 for v in values if v >= 10)}"
    )


def report(path: Path) -> None:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    print(f"\n=== {path.name} ===")

    summary = None
    stats = None
    bed = None
    feed = None
    pumps: list[tuple[int, int]] = []
    picks: list[dict] = []
    failures: list[str] = []
    for line in lines:
        match = BIARM_SUM.search(line)
        if match:
            summary = match.groupdict()
        match = STATS.search(line)
        if match:
            stats = match.groupdict()
        match = BED_STATS.search(line)
        if match:
            bed = match.groupdict()
        match = FEED_ROW.search(line)
        if match:
            feed = match.groupdict()
        match = PUMP.search(line)
        if match:
            pumps.append((int(match.group("band")), int(match.group("band_max"))))
        match = PICK_ROW.search(line)
        if match:
            picks.append(match.groupdict())
        else:
            match = ATTEMPT_ROW.search(line)
            if match:
                row = match.groupdict()
                row["arm"] = "-"
                picks.append(row)
        match = BIARM_RESULT.search(line)
        if match and match.group("placed") == "False":
            failures.append(
                f"{match.group('arm')} idx={match.group('index')} "
                f"{match.group('fruit')} grasped={match.group('grasped')} "
                f"placed=False"
            )
        match = RUN_RESULT.search(line)
        if match and match.group("placed") == "False":
            failures.append(
                f"attempt {match.group('attempt')} grasped={match.group('grasped')} "
                "placed=False"
            )

    if summary:
        print(
            f"  two-line: {summary['successes']}/{summary['attempts']} placed, "
            f"span {summary['span']}s, {summary['per_attempt']}s/attempt, "
            f"{summary['rate']} fruits/min; "
            f"left {summary['l_s']}/{summary['l_a']} right {summary['r_s']}/{summary['r_a']}"
        )
    elif stats:
        print(
            f"  single-arm: {stats['successes']}/{stats['attempts']} placed, "
            f"diverted={stats['diverted']}"
        )

    bands = [band for band, _ in pumps]
    caps = sorted({cap for _, cap in pumps})
    print(f"  [bed-pump] rows={len(pumps)} cap={caps or '-'} band: {_fmt(bands)}")
    if bands:
        print(f"  [bed-pump] band in line order: {bands}")

    for arm in ("left", "right", "-"):
        rows = [row for row in picks if row["arm"] == arm]
        if not rows:
            continue
        windows = [int(row["window"]) for row in rows]
        live = [int(row["live"]) for row in rows]
        print(
            f"  [bed-sel] {arm}: slots={len(rows)} window: {_fmt(windows)}; "
            f"live min/mean/max={min(live)}/{statistics.fmean(live):.1f}/{max(live)}"
        )
        bands = [int(row["band"]) for row in rows if row.get("band") is not None]
        if bands:
            print(f"  [bed-sel] {arm}: band at pick: {_fmt(bands)}")
        if arm == "-":
            print(f"  [bed-sel] single-arm windows in order: {windows}")

    if bed:
        print(
            f"  [bed] draws={bed['draws']} placed={bed['placed']} "
            f"recycled={bed['recycled']}/{bed['draws2']} holds={bed['holds']} "
            f"refused={bed['refused']} rebased={bed['rebased']} "
            f"late_dropped={bed['late']}s fell_off={bed['fell']} "
            f"reached_end={bed['reached']} sweeps={bed['sweeps']} "
            f"swept={bed['swept']} skipped={bed['skipped']} live={bed['live']}"
        )
    if feed:
        print(
            f"  [feed] updates={feed['updates']} ticks={feed['ticks']} "
            f"stride={feed['stride']} released=+{feed['released']} "
            f"placed=+{feed['placed']} skipped=+{feed['skipped']}"
        )
    if failures:
        print(f"  failures ({len(failures)}): " + "; ".join(failures))
    print(f"  wall: {_wall(path)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("logs", nargs="+")
    args = parser.parse_args()
    for name in args.logs:
        report(Path(name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
