#!/usr/bin/env python3
"""P33 phase 1: compare two logs' `[fruit]` streams with pure-reporting rows dropped.

    python3 logs/p33/stream_identity.py REF.log NEW.log \
        --drop '[bed-sel] arm=' --drop '[feed] two-line:'

`scripts/182_run_equiv.py` compares the raw `[fruit]` streams. A P33 run against
an older record also has to drop the rows this phase *added* (the two-line
`[bed-sel] arm=` census, the batch `[feed] two-line:` row) when both are pure
reporting: the physics stream is what has to be identical. Every `--drop`
argument is a substring; a line containing it is removed from both sides.

Exit 0 iff the filtered streams are identical; prints the first difference.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def stream(path: str, drops: list[str]) -> list[str]:
    rows = []
    for line in Path(path).read_text(errors="replace").splitlines():
        if not line.startswith("[fruit]"):
            continue
        if any(token in line for token in drops):
            continue
        rows.append(line)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ref")
    parser.add_argument("new")
    parser.add_argument("--drop", action="append", default=[])
    args = parser.parse_args()
    ref = stream(args.ref, args.drop)
    new = stream(args.new, args.drop)
    print(f"{args.ref}: {len(ref)} [fruit] line(s) after {len(args.drop)} drop filter(s)")
    print(f"{args.new}: {len(new)} [fruit] line(s)")
    if ref == new:
        print(f"IDENTICAL: {args.new} == {args.ref}")
        return 0
    ok = 0
    for i in range(min(len(ref), len(new))):
        if ref[i] != new[i]:
            ok = i
            break
    else:
        ok = min(len(ref), len(new))
    print(f"DIFFERENT: first difference at [fruit] line {ok + 1}")
    print(f"  ref: {ref[ok] if ok < len(ref) else '<missing>'}")
    print(f"  new: {new[ok] if ok < len(new) else '<missing>'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
