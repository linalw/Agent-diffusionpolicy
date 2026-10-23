#!/usr/bin/env python3
"""P33 phase 3 / Gate 3 (M1): the **exact-instance** paired read of the direct A/B.

    python3 logs/p33/E_ab/E_pairs_exact.py

Read-only. `logs/w8/A_pairs.py` pairs by (run, episode index) and treats two
episodes as "same-fruit" when the parser's fruit **species** string matches, so
after the two arms' branches diverge it pairs e.g. a 3.6 cm strawberry with a
4.3 cm one. This script applies the stricter test - same run, episode index,
species, **diameter** and **arm** - i.e. the same spawned instance - and reports
the outcome pairing and the exact two-sided sign test.

Result on `logs/p33/E_ab` (3 runs/arm x 15): 13 instance pairs, 2 both-ok,
9 both-fail, **2 B-only / 0 A-only** (two-sided p = 0.50, one-sided 0.25);
the class-matched `A_pairs.py` read is 3 B-only / 1 A-only (one-sided
p = 0.3125) over 16 pairs, with 29/45 unpairable.
"""
from __future__ import annotations

import glob
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "w7"))

import B_ab_report as mech  # noqa: E402  (the pinned W7-B parser)


def klass(e: dict) -> str:
    if e.get("success"):
        return "ok"
    if e.get("success") is False and not e.get("grasped"):
        return "no-contact"
    if e.get("success") is False and e.get("grasped") and not e.get("placed"):
        return "carried"
    return "other"


def arm_runs(directory: str, label: str) -> dict[int, dict[int, dict]]:
    runs: dict[int, dict[int, dict]] = {}
    for path in sorted(glob.glob(os.path.join(directory, f"{label}_*.log"))):
        run = int(os.path.basename(path)[:-4].rsplit("_", 1)[1])
        runs[run] = {e["ep"]: e for e in mech.parse_log(path)}
    return runs


def exact(ea: dict, eb: dict) -> bool:
    return (
        ea["fruit"] == eb["fruit"]
        and round(ea["d"], 3) == round(eb["d"], 3)
        and ea["arm"] == eb["arm"]
    )


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    a, b = arm_runs(here, "A"), arm_runs(here, "B")
    counts = {"both_ok": 0, "both_fail": 0, "b_only": 0, "a_only": 0}
    rows: list[str] = []
    for run in sorted(set(a) & set(b)):
        for ep in sorted(set(a[run]) & set(b[run])):
            ea, eb = a[run][ep], b[run][ep]
            if ea.get("success") is None or eb.get("success") is None:
                continue
            if not exact(ea, eb):
                continue
            oa, ob = bool(ea["success"]), bool(eb["success"])
            key = (
                "both_ok" if oa and ob else
                "a_only" if oa else
                "b_only" if ob else
                "both_fail"
            )
            counts[key] += 1
            rows.append(
                f"  run{run} ep{ep:2d} {ea['fruit']:10s} {ea['d']:4.1f} cm "
                f"{ea['arm']:5s} A={klass(ea):10s} B={klass(eb):10s} {key}"
            )
    n = counts["b_only"] + counts["a_only"]
    one_sided = (
        sum(math.comb(n, k) for k in range(counts["b_only"], n + 1)) / 2 ** n
        if n else 1.0
    )
    two_sided = min(1.0, 2.0 * one_sided)
    print("P33 exact-instance pairing (same run, episode, species, diameter, arm)")
    print("\n".join(rows))
    print()
    print(
        f"pairs={sum(counts.values())} both_ok={counts['both_ok']} "
        f"both_fail={counts['both_fail']} B-only={counts['b_only']} "
        f"A-only={counts['a_only']}"
    )
    print(
        f"sign test: one-sided p={one_sided:.4f}, "
        f"two-sided p={two_sided:.4f} (discordant {n})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
