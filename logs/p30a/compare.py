#!/usr/bin/env python3
"""Compare two run logs on the `[fruit]` stream (P30-A's byte-identity check).

    python3 logs/p30a/compare.py logs/p30a/01_accept_control.log logs/p30a/02_accept_rails_outer.log
    python3 logs/p30a/compare.py --physics-only A.log B.log

Same contract as `logs/w4/compare_streams.py` (drops the trace-only rows and, with
`--physics-only`, the `[run] attempt` book-keeping rows), plus the P30-A rail audit
row (`output belt rails ...`), which *must* differ between a default build and a
rail-knob build - it is geometry reporting, not physics. Exit 0 iff the remaining
streams are identical line for line.
"""

from __future__ import annotations

import sys
from pathlib import Path

TRACE_ONLY = (
    "[biarm] clearance trace:",
    "[biarm] clearance trace appended",
    ": park wait start",
    ": park moving",
    ": park done",
    "[trace]",
    "[supply-diag]",
    "[supply] diag:",
    # P30-A: the rail-mode audit line (present only when a rail knob is off its
    # default, so a default-vs-knob pair differs here by construction).
    "output belt rails ",
)
NON_PHYSICS = ("[fruit] [run] attempt",)


def fruit_lines(path: str, physics_only: bool = False) -> list[str]:
    out = []
    for line in Path(path).read_text(errors="replace").splitlines():
        if not line.startswith("[fruit]"):
            continue
        if any(marker in line for marker in TRACE_ONLY):
            continue
        if physics_only and line.startswith(NON_PHYSICS):
            continue
        out.append(line.rstrip("\n"))
    return out


def main(argv: list[str]) -> int:
    physics_only = "--physics-only" in argv
    args = [a for a in argv[1:] if a != "--physics-only"]
    if len(args) != 2:
        print(__doc__)
        return 2
    a, b = (fruit_lines(p, physics_only) for p in args)
    print(f"A {args[0]}: {len(a)} [fruit] lines")
    print(f"B {args[1]}: {len(b)} [fruit] lines")
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            print(f"first difference at line {i + 1}:")
            print(f"  A: {a[i][:200]}")
            print(f"  B: {b[i][:200]}")
            return 1
    if len(a) != len(b):
        print(f"lengths differ after {n} identical lines")
        return 1
    print(f"IDENTICAL: {n}/{n} [fruit] lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
