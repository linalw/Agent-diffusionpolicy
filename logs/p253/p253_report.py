#!/usr/bin/env python3
"""P253: the continuous (deployment-shape) cells - one report, reproducible.

    python3 logs/p253/p253_report.py logs/p253/cont_*.log

Reads only **result** rows (`[rl] episode N: ... success=`). The trap this report
exists to avoid: every episode prints **two** `[rl] episode N:` rows (an
announcement without `success=`, then the result), so `grep -c "rl] episode"`
counts one episode twice (`docs/SINGLE_ARM_SPEC.md` section 7).
"""
from __future__ import annotations

import re
import statistics as st
import sys

RESULT = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+)"
)
PICK = re.compile(
    r"\[cont\] pick (\d+)/(\d+): (\w+) grade=([A-C]) y=([-+\d.]+) "
    r"gap_ticks=(\d+) placed_so_far=(\d+)"
)
SUMMARY = re.compile(r"picks placed (\d+)/(\d+)")
CYCLE = re.compile(r"\[cycle\] attempt 0:(.*)")
BLOCK = re.compile(r"(\w+)=([\d.]+)s")
NOTE = re.compile(r"'([^']*)'")


def main(paths: list[str]) -> int:
    if not paths:
        raise SystemExit("usage: p253_report.py <cell.log> [...]")
    print(f"{'cell':34s} {'placed':>8} {'skips':>6} {'gaps':>6} {'cycle':>7}  species drawn")
    total_n = total_placed = 0
    for path in paths:
        text = open(path, encoding="utf-8", errors="replace").read()
        res = RESULT.findall(text)
        summary = SUMMARY.search(text)
        placed = int(summary.group(1)) if summary else sum(1 for r in res if r[5] == "True")
        n = int(summary.group(2)) if summary else len(res)
        skips = text.count("[skip]")
        gaps = [int(m.group(6)) for m in PICK.finditer(text)]
        cycles = [dict(BLOCK.findall(m.group(1))) for m in CYCLE.finditer(text)]
        totals = [float(c["total"]) for c in cycles if "total" in c]
        species = sorted({m.group(3) for m in PICK.finditer(text)})
        gap_med = f"{st.median(gaps):.0f}" if gaps else "-"
        cyc = f"{st.median(totals):.2f}s" if totals else "-"
        print(f"{path.split('/')[-1]:34s} {placed:4d}/{n:<3d} {skips:6d} {gap_med:>6} "
              f"{cyc:>7}  {', '.join(species)}")
        total_n += n
        total_placed += placed
        # The two-row trap, asserted: announcement + result per episode.
        allrows = len(re.findall(r"\[rl\] episode \d+:", text))
        if res and allrows != 2 * len(res):
            print(f"  WARNING {path}: {allrows} episode rows for {len(res)} results "
                  "(expected 2x - the announcement row may have changed shape)")
        # losses, with the species and **their own** notes (the notes are read
        # from the result line only: the startup banner carries quoted args that
        # a whole-file scan would pick up)
        losses = [r for r in res if r[5] == "False"]
        if losses:
            print(f"  losses: {[(r[1], r[2] + 'cm') for r in losses]}")
            for r in losses:
                line = next((ln for ln in text.splitlines()
                             if f"[rl] episode {r[0]}:" in ln and "success=" in ln), "")
                notes = [t for t in NOTE.findall(line)
                         if not t.startswith(("intercept trigger", "policy closed"))]
                if notes:
                    print(f"    ep{r[0]} {r[1]} {r[2]}cm: {notes}")
    if total_n:
        print(f"\npooled: {total_placed}/{total_n} = {100 * total_placed / total_n:.1f}% "
              "(cells are one draw each; no cross-cell rate is claimed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
