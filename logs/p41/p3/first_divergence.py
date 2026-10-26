#!/usr/bin/env python3
"""P41 phase 3 - where the three acceptance arms leave the same branch.

    python3 logs/p41/p3/first_divergence.py > logs/p41/p3/first_divergence.txt

Read-only. The three claimed acceptance logs differ by exactly two *print* lines
by construction (the build line gains `maxForce=<cap>` and an appended per-joint
readback note; `ArmController` prints a one-time `[drive]` readback when the knob
is set), so both are filtered here. What is left is behavioural: the first line
where the 30/60 N arms stop reproducing the 10 N arm, plus the attempt-0 close
and carry rows that the comparison turns on.
"""
from __future__ import annotations

import sys

ARMS = ("control", "mf30", "mf60")


def rows(path: str) -> list[str]:
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        if not line.startswith("[fruit]"):
            continue
        if "[trace]" in line or "[drive]" in line or "finger drive profile=" in line:
            continue
        out.append(line.rstrip("\n"))
    return out


def main() -> int:
    arms = {arm: rows(f"logs/p41/p3/accept_{arm}.log") for arm in ARMS}
    base = arms["control"]
    for arm in ARMS[1:]:
        other = arms[arm]
        for index, (left, right) in enumerate(zip(base, other)):
            if left != right:
                print(
                    f"=== control vs {arm}: first behavioural divergence at line {index} "
                    f"({len(base)}/{len(other)} lines)"
                )
                for k in range(max(0, index - 1), index + 2):
                    print("  C   :", base[k])
                    print(f"  {arm:<4}:", other[k])
                print()
                break
    print("=== the attempt-0 peach, close line per arm")
    for arm in ARMS:
        for line in arms[arm]:
            if "dynamic close: sustained contact" in line:
                print(f"  {arm:<8}: {line.replace('[fruit] ', '')}")
                break
    print()
    print("=== the attempt-0 peach, the attempt's own rows per arm")
    for arm in ARMS:
        print(f"  {arm}:")
        for line in arms[arm]:
            if "attempt 0:" in line or "[carry]" in line:
                print("   ", line.replace("[fruit] ", ""))
            if "attempt 0: grasped" in line:
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
