#!/usr/bin/env python3
"""P71: compare two scripted logs' `[fruit]` streams (the identity instrument).

    python3 logs/p71/accept_diff.py logs/p71/accept_rails_both.log \
        logs/p71/accept_rails_none.log [--ref logs/p66/p2/accept_noharm.log]

Prints, per log, the `[fruit]` line count and the run's own summary, then the
pairwise identity: how many lines are identical at the same index (and where the
first difference is), and how many are common as a multiset. The scene change
(the rails) is a *collider* change, so a moved stream is expected - the question
this answers is **by how much** and whether the control still replays the
archive (which is what attributes the move to the flip).
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

STATS = re.compile(r"^\[stats\].*$")
SUMMARY = re.compile(r"^\[run\] summary.*$")


def fruit_lines(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith("[fruit]")
    ]


def summary(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if STATS.match(line) or SUMMARY.match(line):
            out.append(line[:190])
    return out


def compare(a: list[str], b: list[str], name_a: str, name_b: str) -> None:
    identical = 0
    first = None
    for i, (x, y) in enumerate(zip(a, b)):
        if x == y:
            identical += 1
        elif first is None:
            first = i
            break
    common = collections.Counter(a) & collections.Counter(b)
    print(f"  {name_a} vs {name_b}:")
    print(f"    same index-ordered prefix: {identical} line(s)"
          + (f", first difference at line {first}" if first is not None else " (all shared prefix equal)"))
    if first is not None:
        print(f"      A[{first}]: {a[first][:170]}")
        print(f"      B[{first}]: {b[first][:170]}")
    print(f"    common as a multiset: {sum(common.values())} of "
          f"{len(a)} / {len(b)} lines")


def main(argv: list[str]) -> int:
    ref = None
    if "--ref" in argv:
        i = argv.index("--ref")
        ref = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    paths = [Path(a) for a in argv if not a.startswith("--")]
    streams = {}
    for path in paths:
        if not path.is_file():
            print(f"FAIL: {path} missing")
            return 1
        lines = fruit_lines(path)
        streams[path.name] = lines
        print(f"{path.name}: {len(lines)} [fruit] lines")
        for line in summary(path):
            print(f"  {line}")
    print()
    names = list(streams)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            compare(streams[names[i]], streams[names[j]], names[i], names[j])
    if ref is not None:
        print()
        ref_lines = fruit_lines(ref)
        print(f"reference {ref.name}: {len(ref_lines)} [fruit] lines")
        for name, lines in streams.items():
            same = sum(1 for x, y in zip(lines, ref_lines) if x == y)
            print(f"  {name}: {same} identical at the same index vs the reference "
                  f"({'byte-identical' if same == len(lines) == len(ref_lines) else 'MOVED'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
