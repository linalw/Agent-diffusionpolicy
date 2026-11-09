#!/usr/bin/env python3
"""P135 perception bench: position/diameter error by estimator shape.

Reads the `[perceive]` bench rows written by
`FRUIT_TRACK_APPLY=0 FRUIT_TRACK_SOURCE=depth FRUIT_TRACK_DIAG=1` and prints,
per cell, the median/p90 of the centre error, its components and the diameter
error.  The first frame of each attempt is dropped: the fruit is entering the
frame there and its cap is a crescent (the row is still in the log, flagged by a
much larger `err`).

    python3 logs/p135/perception_bench.py logs/p135/perception/shape_sphere.log ...
"""
from __future__ import annotations

import re
import statistics
import sys

ROW = re.compile(
    r"\[perceive\] idx=(\d+) px=(\d+) err=([0-9.]+)mm "
    r"d=\(([-+0-9.]+),([-+0-9.]+),([-+0-9.]+)\)mm "
    r"dia=([0-9.]+)mm dia_err=([-+0-9.]+)mm rms=([0-9.]+)mm"
)


def collect(path):
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        match = ROW.search(line)
        if match:
            rows.append(
                {
                    "index": int(match.group(1)),
                    "px": int(match.group(2)),
                    "err": float(match.group(3)),
                    "dx": float(match.group(4)),
                    "dy": float(match.group(5)),
                    "dz": float(match.group(6)),
                    "dia": float(match.group(7)),
                    "dia_err": float(match.group(8)),
                    "rms": float(match.group(9)),
                }
            )
    return rows


def p90(values):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))]


def main(argv):
    print(f"{'cell':<24}{'n':>4}{'err med':>9}{'err p90':>9}"
          f"{'dx':>7}{'dy':>7}{'dz':>7}{'dia med':>9}{'dia p90':>9}")
    for path in argv[1:]:
        rows = collect(path)
        if not rows:
            print(f"{path:<24} no rows")
            continue
        # drop each attempt's first accepted frame (the fruit entering the view)
        firsts = set()
        seen = set()
        for row in rows:
            if row["index"] not in seen:
                seen.add(row["index"])
                firsts.add(id(row))
        kept = [row for row in rows if id(row) not in firsts]
        if not kept:
            kept = rows
        name = path.rsplit("/", 1)[-1].replace(".log", "")
        print(
            f"{name:<24}{len(kept):>4}"
            f"{statistics.median(r['err'] for r in kept):>9.2f}"
            f"{p90([r['err'] for r in kept]):>9.2f}"
            f"{statistics.median(r['dx'] for r in kept):>7.2f}"
            f"{statistics.median(r['dy'] for r in kept):>7.2f}"
            f"{statistics.median(r['dz'] for r in kept):>7.2f}"
            f"{statistics.median(abs(r['dia_err']) for r in kept):>9.2f}"
            f"{p90([abs(r['dia_err']) for r in kept]):>9.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
