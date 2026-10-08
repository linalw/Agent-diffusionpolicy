"""Summarise the lowered-place landing traces from pick-and-place run logs.

    python3 scripts/145_place_low_report.py logs/place_low/01_base_trace.log
    python3 scripts/145_place_low_report.py LOG_A LOG_B   # side-by-side compare

Reads the `[task] place trace ...` lines printed by `FRUIT_PLACE_TRACE=1`
(`tasks.py::_place_trace_report`) and the `[stats]` line, so it is pure offline
reporting. One row per place: release height (fruit bottom above the output-belt
top), impact (largest downward speed), bounce (peak rebound of the lowest point),
roll (along-belt travel after release), skid (the part of that travel that was
not just riding the belt), settle time, final accuracy and whether the fruit
ended on the belt. The `clearance=`/`drop=`/`ik=` tail is present only on the
lowered-place line.
"""

from __future__ import annotations

import math
import re
import sys

TRACE = re.compile(
    r"place trace (?P<arm>\w+): release_bottom=(?P<release>[-\d.]+)mm "
    r"impact=(?P<impact>[-\d.]+)m/s bounce=(?P<bounce>[-\d.]+)mm "
    r"roll=(?P<roll>[+\-\d.]+)mm"
    r"(?: skid=(?P<skid>[+\-\d.]+)mm)? "
    r"settle=(?P<settle>[-\d.]+|nan)ms "
    r"final=\((?P<fx>[-\d.]+),(?P<fy>[+\-\d.]+),(?P<fz>[-\d.]+)\) "
    r"off=\((?P<ox>[+\-\d.]+),(?P<oy>[+\-\d.]+)\)mm on_belt=(?P<on>\w+)"
    r"(?: clearance=(?P<clear>[-\d.]+)mm target=(?P<target>[-\d.]+)mm "
    r"drop=(?P<drop>[-\d.]+)mm(?P<finger> FINGER_FLOOR\(budget (?P<budget>[-\d.]+)mm\))?"
    r" ik=(?P<ik>[-\d.]+)mm(?: a=(?P<apeak>[-\d.]+)/(?P<abudget>[-\d.]+)m/s\^2)?)?"
)
STATS = re.compile(r"\[stats\] attempts=(\d+) successes=(\d+).*?sim=([\d.]+)s total,\s*([\d.]+)s/attempt")


def parse(path: str):
    rows = []
    tally = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            found = TRACE.search(line)
            if found:
                values = found.groupdict()
                rows.append(
                    {
                        "arm": values["arm"],
                        "release": float(values["release"]),
                        "impact": abs(float(values["impact"])),
                        "bounce": float(values["bounce"]),
                        "roll": float(values["roll"]),
                        "skid": float(values["skid"]) if values["skid"] else None,
                        "settle": (
                            float("nan")
                            if values["settle"] == "nan"
                            else float(values["settle"])
                        ),
                        "off_x": float(values["ox"]),
                        "off_y": float(values["oy"]),
                        "on_belt": values["on"] == "True",
                        "clear": float(values["clear"]) if values["clear"] else None,
                        "target": float(values["target"]) if values["target"] else None,
                        "drop": float(values["drop"]) if values["drop"] else None,
                        "finger": bool(values["finger"]),
                        "ik": float(values["ik"]) if values["ik"] else None,
                    }
                )
            found = STATS.search(line)
            if found:
                tally = (int(found.group(1)), int(found.group(2)), float(found.group(4)))
    return rows, tally


def stat(values, fmt=".1f", empty="-"):  # noqa: ANN001
    values = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not values:
        return empty
    return f"{min(values):{fmt}}/{(sum(values) / len(values)):{fmt}}/{max(values):{fmt}}"


def show(path: str, rows, tally) -> None:
    name = path.split("/")[-1]
    rule = "-" * 100
    print(f"\n{name}")
    print(rule)
    print(
        f"{'#':>2} {'arm':<5} {'release':>7} {'impact':>6} {'bounce':>6} "
        f"{'roll':>6} {'skid':>6} {'settle':>7} {'off_x':>6} {'off_y':>6} "
        f"{'belt':>4} {'clear':>6} {'finger':>6} {'ik':>5}"
    )
    for index, row in enumerate(rows, 1):
        settle = "nan" if math.isnan(row["settle"]) else f"{row['settle']:.0f}"
        print(
            f"{index:2d} {row['arm']:<5} {row['release']:6.0f} {row['impact']:6.2f} "
            f"{row['bounce']:6.1f} {row['roll']:6.0f} "
            f"{(row['skid'] if row['skid'] is not None else float('nan')):6.0f} "
            f"{settle:>7} {row['off_x']:6.0f} {row['off_y']:6.0f} "
            f"{'yes' if row['on_belt'] else 'NO':>4} "
            f"{(row['clear'] if row['clear'] is not None else float('nan')):6.0f} "
            f"{'FLOOR' if row['finger'] else '':>6} "
            f"{(row['ik'] if row['ik'] is not None else float('nan')):5.1f}"
        )
    print(rule)
    if tally:
        attempts, successes, per = tally
        print(f"attempts={attempts} successes={successes} {per:.1f} s/attempt")
    print(
        f"release mm  min/mean/max = {stat([r['release'] for r in rows], '.0f')}   "
        f"impact m/s = {stat([r['impact'] for r in rows], '.2f')}"
    )
    print(
        f"bounce mm   min/mean/max = {stat([r['bounce'] for r in rows], '.1f')}   "
        f"skid mm = {stat([r['skid'] for r in rows], '+.0f')}   "
        f"settle ms = {stat([r['settle'] for r in rows], '.0f')}"
    )
    print(
        f"cross-belt |off_y| mm = {stat([abs(r['off_y']) for r in rows], '.0f')}   "
        f"on-belt = {sum(1 for r in rows if r['on_belt'])}/{len(rows)}"
    )


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for path in sys.argv[1:]:
        rows, tally = parse(path)
        if not rows:
            print(f"{path}: no place trace lines (run with FRUIT_PLACE_TRACE=1)")
            continue
        show(path, rows, tally)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
