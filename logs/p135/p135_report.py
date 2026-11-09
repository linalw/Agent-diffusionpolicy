#!/usr/bin/env python3
"""P135 report: the non-uniform-motion envelope and the tracker's rows.

Reads the cell logs written by `run_envelope.sh` / `run_perception.sh` and
prints one row per cell:

    cell  attempts  grasp  placed  catch_residuals(mm)  corr_max(mm)  track

`grasp` is `grasped=True` (the pads closed on the payload), `placed` is the
attempt outcome.  `catch` is every `[task] dynamic catch-up: residual=` value,
which is the *measured* distance between the fingertip and the fruit at the end
of the catch-up loop - the number the tracker is trying to make small.  A
residual equal to the tolerance (6.0 mm) means the loop converged; a residual
near or above 200 mm means it timed out at the reach budget.
"""
from __future__ import annotations

import glob
import os
import re
import statistics
import sys

CATCH = re.compile(r"dynamic catch-up: residual=([0-9.]+) mm")
ATTEMPT = re.compile(r"\[run\] attempt \d+: (.*)")
SUMMARY = re.compile(r"\[run\] summary: (\d+)/(\d+) successful")
TRACK = re.compile(r"\[track\] (.*)")
PERCEIVE = re.compile(r"\[perceive\] (.*)")
PERTURB = re.compile(r"\[perturb\] (.*)")


def parse(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    catches = [float(m) for m in CATCH.findall(text)]
    attempts = [m for m in ATTEMPT.findall(text) if "grasped=" in m]
    grasps = sum("grasped=True" in a for a in attempts)
    placed = sum("placed=True" in a for a in attempts)
    tracks = TRACK.findall(text)
    corr = []
    for row in tracks:
        match = re.search(r"corr_max=([0-9.]+)mm", row)
        if match:
            corr.append(float(match.group(1)))
    summary = SUMMARY.search(text)
    return {
        "attempts": len(attempts),
        "grasps": grasps,
        "placed": placed,
        "catches": catches,
        "corr": corr,
        "summary": summary.groups() if summary else None,
        "tracks": len(tracks),
        "perceive": PERCEIVE.findall(text),
        "perturb": PERTURB.findall(text),
        "notes": sorted(
            {
                note
                for a in attempts
                for note in re.findall(r"'([^']+)'", a.split("notes=")[-1])
            }
        ),
    }


def fmt(values, digits=1):
    if not values:
        return "-"
    if len(values) == 1:
        return f"{values[0]:.{digits}f}"
    return f"{statistics.median(values):.{digits}f} [{min(values):.{digits}f},{max(values):.{digits}f}]"


def main(argv):
    root = argv[1] if len(argv) > 1 else "logs/p135/envelope"
    files = sorted(glob.glob(os.path.join(root, "*.log")))
    files = [f for f in files if os.path.basename(f) != "driver.log"]
    if not files:
        print(f"no cells under {root}")
        return 1
    print(f"{'cell':<22}{'n':>3}{'grasp':>7}{'place':>7}"
          f"  {'catch residual mm':<24}{'corr mm':<12}{'track':>6}")
    for path in files:
        row = parse(path)
        name = os.path.basename(path)[:-4]
        print(
            f"{name:<22}{row['attempts']:>3}{row['grasps']:>7}{row['placed']:>7}"
            f"  {fmt(row['catches']):<24}{fmt(row['corr']):<12}{row['tracks']:>6}"
        )
        if row["notes"]:
            print(f"    notes: {', '.join(row['notes'])}")
        if row["perceive"]:
            for line in row["perceive"]:
                print(f"    [perceive] {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
