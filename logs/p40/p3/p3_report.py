#!/usr/bin/env python3
"""P40 phase 3 - the single-arm per-attempt table (arrival wait, span, outcome).

Reads one or more `20_pick_place.py` single-arm logs (the acceptance scenario)
and prints, per attempt:

  * the commit tick (`sim=a` of the attempt's own span),
  * the pre-pose (`at pick pose after X s`),
  * the arrival wait (`fruit at pick point: ... after N steps`, N/120 s) -
    the wait loop's iteration count; `logs/p40/ARRIVAL_SPLIT.md` measured its
    belt identity (residual 0-10 ms over 109 attempts),
  * the attempt span (`sim=Ds`), and the outcome.

Plus the batch totals a rate claim needs (placed, span, s/attempt), the re-seat
row count, and the recycle counters the log actually prints (`discharged`
rows, `recirculated`/`diverted` from `[stats]`; `reached_end`/`skipped` are
**not printed** on this supply - the cap says so in the table header).

    python3 logs/p40/p3/p3_report.py LOG [LOG...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PICK = re.compile(r"\[run\] attempt (\d+): picking (\w+) grade (\w+)")
OUT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([-+0-9.]+) m "
    r"force=([0-9.]+) N notes=\[(.*?)\] sim=([0-9.]+)-([0-9.]+)s"
)
SPAN = re.compile(r"\[run\] attempt (\d+): picking .* sim=([0-9.]+)-([0-9.]+)s")
PREPOSE = re.compile(r"\[task\] at pick pose after ([0-9.]+) s")
ARRIVE = re.compile(r"\[task\] fruit at pick point: dy=\+?([0-9.]+) m .* after (\d+) steps")
STATS = re.compile(r"\[stats\] attempts=(\d+) successes=(\d+) diverted=(\d+).*sim=([0-9.]+)s")


def rows(path: str) -> tuple[list[dict], dict]:
    lines = Path(path).read_text(errors="replace").splitlines()
    attempts: dict[int, dict] = {}
    preposes: list[float] = []
    waits: list[int] = []
    regrasps = 0
    discharged = 0
    stats = ""
    for line in lines:
        if "dynamic regrasp: re-seated" in line or "recovery: re-grasped" in line:
            regrasps += 1
        if "[belt]" in line and "discharged to the tray" in line:
            discharged += 1
        if m := PICK.search(line):
            idx = int(m.group(1))
            attempts.setdefault(idx, {})["fruit"] = m.group(2)
        if m := SPAN.search(line):
            row = attempts.setdefault(int(m.group(1)), {})
            row["t0"] = float(m.group(2))
            row["t1"] = float(m.group(3))
        if m := PREPOSE.search(line):
            preposes.append(float(m.group(1)))
        if m := ARRIVE.search(line):
            waits.append(int(m.group(2)))
        if m := OUT.search(line):
            row = attempts.setdefault(int(m.group(1)), {})
            row["grasped"] = m.group(2) == "True"
            row["placed"] = m.group(3) == "True"
            row["notes"] = m.group(6)
            row["t0"] = float(m.group(7))
            row["t1"] = float(m.group(8))
            row["span"] = row["t1"] - row["t0"]
        if m := STATS.search(line):
            stats = m.group(0)
    out = []
    for k in sorted(attempts):
        attempts[k]["_k"] = k
        out.append(attempts[k])
    for row, pre, wait in zip(out, preposes, waits):
        row["prepose"] = pre
        row["wait"] = wait / 120.0
    return out, {"regrasps": regrasps, "discharged": discharged, "stats": stats}


def main(argv: list[str]) -> int:
    for path in argv[1:]:
        out, meta = rows(path)
        print(f"== {path}")
        print(
            "  att fruit       prepose  wait  span  grasped placed notes"
        )
        for row in out:
            print(
                f"  {row.get('_k', -1):3d} {row.get('fruit', '?'):10s} {row.get('prepose', float('nan')):7.2f}"
                f" {row.get('wait', float('nan')):5.2f} {row.get('span', float('nan')):5.1f}"
                f"  {str(row.get('grasped')):5s} {str(row.get('placed')):5s}"
                f"  {row.get('notes', '')}"
            )
        for row in out:
            if "span" not in row and "t0" in row and "t1" in row:
                row["span"] = row["t1"] - row["t0"]
        spans = [r["span"] for r in out if "span" in r]
        waits = [r["wait"] for r in out if "wait" in r]
        placed = sum(1 for r in out if r.get("placed"))
        grasped = sum(1 for r in out if r.get("grasped"))
        med = lambda xs: sorted(xs)[len(xs) // 2] if xs else float("nan")
        print(
            f"  attempts={len(out)} placed={placed} grasped={grasped} "
            f"re-seat rows={meta['regrasps']} discharged={meta['discharged']}"
        )
        print(
            f"  span sum={sum(spans):.1f}s mean={sum(spans) / len(spans):.2f}s "
            f"median={med(spans):.2f}s | arrival wait mean={sum(waits) / len(waits):.2f}s "
            f"median={med(waits):.2f}s min={min(waits):.2f} max={max(waits):.2f}"
        )
        if meta["stats"]:
            print(f"  {meta['stats']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
