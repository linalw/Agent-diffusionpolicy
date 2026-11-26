#!/usr/bin/env python3
"""P283: per-species read of the truth-free contact phase.

Every `[rl] episode` row names its species, diameter, arm and outcome, so the
question "how do the *other* fruits do" can be answered from the logs already on
disk before spending a cell on any one of them.

Two blocks are separated on purpose:

* **truth-fed** - the deployment cells (P261/P262/P274), 0.08, where the contact
  phase still reads the simulator;
* **truth-free** - the P276-P282 cells, where the contact phase runs on the
  estimate (with the wrist / the pad mount / the light, as each phase fixed it).

The difference between the two blocks, per species, is where the truth-free
contact phase actually bites. A count here is still a branch draw (P93); the read
is the *class* per species, not a rate.

Usage: python3 logs/p283/species_census.py [--verbose]
"""
from __future__ import annotations

import glob
import os
import re
import sys

ROW = re.compile(
    r"episode \d+: (?P<sp>\w+) d=(?P<d>[0-9.]+)cm bin=\d+ arm=(?P<arm>\w+) "
    r"success=(?P<ok>\w+) grasped=(?P<g>\w+) placed=(?P<p>\w+)"
)

#: the two blocks. `glob` patterns, and a label.
BLOCKS = {
    "truth-fed": [
        "logs/p274/*.log", "logs/p262/*.log", "logs/p261/*.log",
        "logs/p260/*.log", "logs/p259/*.log",
    ],
    "truth-free": [
        "logs/p282/A_s*.log", "logs/p282/B_s*.log",
        "logs/p281/C_s*.log", "logs/p280/S09_s*.log",
        "logs/p279/L_s*.log", "logs/p278/T_s*.log",
        "logs/p277/K_s*.log", "logs/p276b/TFs_s*.log",
    ],
}


def rows(paths):
    out = []
    for pat in paths:
        for f in glob.glob(pat):
            try:
                txt = open(f, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for m in ROW.finditer(txt):
                out.append(
                    (
                        m.group("sp"),
                        float(m.group("d")),
                        m.group("arm"),
                        m.group("ok") == "True",
                        m.group("g") == "True",
                        m.group("p") == "True",
                        os.path.basename(f),
                    )
                )
    return out


def bucket(d: float) -> str:
    if d < 4.0:
        return "<=4 cm"
    if d < 5.0:
        return "4-5"
    if d < 6.0:
        return "5-6"
    return ">=6"


def table(label: str, rs, verbose: bool):
    print(f"\n{label}: {len(rs)} attempts")
    if not rs:
        print("  (no rows)")
        return
    print(f"{'species':12s} {'n':>4s} {'placed':>7s} {'rate':>6s}  "
          f"{'never-grasped':>13s} {'carried-not-placed':>19s}")
    for sp in sorted({r[0] for r in rs}):
        sub = [r for r in rs if r[0] == sp]
        n = len(sub)
        ok = sum(1 for r in sub if r[3])
        ng = sum(1 for r in sub if not r[4])
        cnp = sum(1 for r in sub if r[4] and not r[5])
        print(f"{sp:12s} {n:>4d} {ok:>7d} {100.0 * ok / n:>5.0f}%  "
              f"{ng:>13d} {cnp:>19d}")
    print(f"{'TOTAL':12s} {len(rs):>4d} {sum(1 for r in rs if r[3]):>7d} "
          f"{100.0 * sum(1 for r in rs if r[3]) / len(rs):>5.0f}%  "
          f"{sum(1 for r in rs if not r[4]):>13d} "
          f"{sum(1 for r in rs if r[4] and not r[5]):>19d}")

    print(f"\n  by size bucket")
    for b in ("<=4 cm", "4-5", "5-6", ">=6"):
        sub = [r for r in rs if bucket(r[1]) == b]
        if sub:
            ok = sum(1 for r in sub if r[3])
            print(f"    {b:8s} {ok:>3d}/{len(sub):<3d} = {100.0 * ok / len(sub):>3.0f}%")

    if verbose:
        print("\n  arms")
        for arm in ("left", "right"):
            sub = [r for r in rs if r[2] == arm]
            if sub:
                ok = sum(1 for r in sub if r[3])
                print(f"    {arm:6s} {ok:>3d}/{len(sub):<3d} = {100.0 * ok / len(sub):>3.0f}%")


def main(argv):
    verbose = "--verbose" in argv
    data = {k: rows(v) for k, v in BLOCKS.items()}
    for label, rs in data.items():
        table(label, rs, verbose)
    print(
        "\nRead: the truth-free block pools several levers (wrist, pad mount, light), so a\n"
        "per-species gap there is the *contact phase's* cost, not one lever's. Counts are\n"
        "branch draws (P93); the class column is what moves."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
