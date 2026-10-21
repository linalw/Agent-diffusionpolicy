#!/usr/bin/env python3
"""P30-A: one table for every arm - outcome, cadence, the place clearance, the releases.

    python3 logs/p30a/summarise.py logs/p30a/0*.log logs/p30a/2*.log

Pure text parsing (no simulator). Per log it prints:

  * the outcome line (`[stats]` / `[biarm]`) - attempts, successes, span, throughput;
  * the **place-leg clearance to the output rail** (`[motion] carry placeN clearance`):
    the count, the positive minimum and the median, and how many rows are negative
    (the negative population is dominated by payloads that had already escaped -
    a -215..-219 mm row is a fruit sitting on the *main* belt, so it is counted
    separately from the small-negative rows that are genuine rail skims);
  * the **worst place-leg acceleration** (`|a|max`) and the worst `slip_max`;
  * the **released-|y| histogram** against the inner rail's footprint
    (|y| < 0.400 inboard, 0.400-0.425 on the rail's top face, else on the slab)
    with the placed rate of each bin.

Those are the numbers `RESULTS.md` quotes; the mode-specific mechanism (the rail
audit line) is printed too when the log has one.
"""

from __future__ import annotations

import re
import statistics
import sys

STATS = re.compile(r"\[stats\] attempts=(\d+) successes=(\d+) .*?success_rate=(\d+)% sim=([\d.]+)s total, ([\d.]+)s/attempt")
BIARM = re.compile(r"\[biarm\] .*?(\d+) successes, ([\d.]+)s sim span, ([\d.]+)s/attempt.*?per arm left=(\d+)/(\d+) right=(\d+)/(\d+)")
CLEAR = re.compile(r"\[motion\] carry (place[01]) clearance: lowest payload point ([+-]?\d+) mm to the ([\w ]+)")
CARRY = re.compile(r"\[motion\] carry (place[01]): .*?\|a\|max=([\d.]+) m/s\^2.*?slip=([\d.]+) mm")
REL = re.compile(r"\[task\] released at \[[-\d.e]+, ([-\d.e]+), [-\d.e]+\], placed=(\w+)")
RAIL = re.compile(r"\[fruit\] output belt rails (\w+): (.*)")


def analyse(path):
    text = open(path, errors="replace").read()
    out = {"path": path}
    m = STATS.search(text)
    out["stats"] = m.groups() if m else None
    m = BIARM.search(text)
    out["biarm"] = m.groups() if m else None
    clears = [(g1, int(g2), g3.strip()) for g1, g2, g3 in CLEAR.findall(text)]
    rail = [v for _, v, w in clears if w == "output rail"]
    out["place_rows"] = len(clears)
    out["rail_pos"] = sorted(v for v in rail if v >= 0)
    out["rail_neg_small"] = [v for v in rail if -50 < v < 0]
    out["rail_neg_escape"] = [v for v in rail if v <= -50]
    acc = [(g, float(a), float(s)) for g, a, s in CARRY.findall(text)]
    out["worst_place_acc"] = max((a for _, a, _ in acc), default=float("nan"))
    out["worst_place_slip"] = max((s for _, _, s in acc), default=float("nan"))
    rel = [(abs(float(y)), p == "True") for y, p in REL.findall(text)]
    bins = {"<0.400": [0, 0], "0.400-0.425": [0, 0], ">0.425": [0, 0]}
    for y, ok in rel:
        k = "<0.400" if y < 0.400 else ("0.400-0.425" if y <= 0.425 else ">0.425")
        bins[k][0] += 1
        bins[k][1] += int(ok)
    out["rel_bins"] = bins
    out["rel_n"] = len(rel)
    out["rail_line"] = RAIL.findall(text)
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    for path in argv[1:]:
        o = analyse(path)
        print(f"== {path}")
        if o["stats"]:
            a, s, r, span, per = o["stats"]
            print(f"   outcome        attempts={a} successes={s} ({r}%) span={span}s {per}s/attempt")
        if o["biarm"]:
            s, span, per, ls, ln, rs, rn = o["biarm"]
            print(f"   two-line       successes={s} span={span}s {per}s/attempt "
                  f"left={ls}/{ln} right={rs}/{rn}")
        rp = o["rail_pos"]
        if rp:
            print(f"   place clearance {len(rp)} positive rows: min {rp[0]} mm, "
                  f"p10 {rp[max(0, len(rp) // 10)]} mm, median {statistics.median(rp):.0f} mm; "
                  f"small negatives {len(o['rail_neg_small'])} "
                  f"{sorted(o['rail_neg_small'])[:6]}; escaped rows {len(o['rail_neg_escape'])}")
        print(f"   worst place    |a|max={o['worst_place_acc']:.2f} m/s^2, slip={o['worst_place_slip']:.0f} mm")
        b = o["rel_bins"]
        if o["rel_n"]:
            parts = []
            for k in ("<0.400", "0.400-0.425", ">0.425"):
                n, ok = b[k]
                parts.append(f"{k} n={n} placed={100 * ok / n:.0f}%" if n else f"{k} n=0")
            print(f"   releases       {o['rel_n']}: " + " | ".join(parts))
        for tag, rest in o["rail_line"]:
            print(f"   rail audit     {tag}: {rest[:130]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
