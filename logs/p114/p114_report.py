#!/usr/bin/env python3
"""P114 report: the coupling audit's data layer, read back from the runs.

    python3 logs/p114/p114_report.py --same logs/p114/accept_off.log logs/p114/accept_today.log
    python3 logs/p114/p114_report.py --ledger logs/p114/accept_three_dest.log
    python3 logs/p114/p114_report.py --accept logs/p114/accept_off.log

`--same` compares the `[fruit]` streams of two runs with the P114 `[sort]` rows
dropped (the instruction layer's only print), so a replay claim is "N/N lines
identical" whatever N is.

`--ledger` reads the `[sort]` rows: the instruction/capability/reach rows, the
coverage row, every attempt row and the per-destination summary. Its accuracy is
the endpoint (not the placed count): a released payload counts as *in the
destination* when it is on an output belt, on the assigned destination's side,
and nearer that destination's target than any other destination on that side;
*mis-sorted* is a released payload that is not. An attempt that never released
is `not_placed` and is excluded from the accuracy denominator, so the number is
"of the payloads the arm actually delivered, how many went where instructed".

`--accept` prints the run's own success rate and fingerprint verdict line.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

SORT = "[fruit] [sort] "
ATTEMPT = re.compile(
    r"\[sort\] attempt (\d+) idx=(\d+) (\S+) d=([\d.]+)cm grade=(\S+) "
    r"ripeness=([\d.]+) arm=(\S+) (?:rule=(\S+) )?dest=(\d+) target=\(([^)]+)\) "
    r"placed=(\d+)(?: release=\(([^)]+)\) on_belt=(\d+) side=(\S+) nearest=(\S+) "
    r"dist=(\d+)mm in_dest=(\d+))?"
)
LEDGER = re.compile(
    r"\[sort\] ledger: attempts=(\d+) assigned=(\d+) released=(\d+) "
    r"in_destination=(\d+) mis_sorted=(\d+) not_placed=(\d+) refused=(\d+) "
    r"\(pool unassigned=(\d+) skip=(\d+)\)"
)
PER_DEST = re.compile(
    r"\[sort\] ledger dest=(\d+): attempts=(\d+) released=(\d+) "
    r"in_destination=(\d+) mis_sorted=(\d+) not_placed=(\d+)"
)


def fruit_stream(path: str, keep_sort: bool = False) -> list[str]:
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("[fruit]"):
            continue
        if not keep_sort and line.startswith(SORT):
            continue
        out.append(line)
    return out


def same(a: str, b: str, keep_sort: bool = False) -> int:
    left = fruit_stream(a, keep_sort)
    right = fruit_stream(b, keep_sort)
    md5 = hashlib.md5("".join(left).encode()).hexdigest()
    print(f"A {a}: {len(left)} [fruit] lines, md5 {md5}")
    print(f"B {b}: {len(right)} [fruit] lines")
    if left == right:
        print(f"IDENTICAL: {len(left)}/{len(right)} lines (the [sort] rows dropped)")
        return 0
    print(f"DIFFER: first difference at line {next(i for i, (x, y) in enumerate(zip(left, right)) if x != y)}")
    for index, (x, y) in enumerate(zip(left, right)):
        if x != y:
            print(f"  A: {x[:200]}")
            print(f"  B: {y[:200]}")
            break
    if len(left) != len(right):
        print(f"  length differs: {len(left)} vs {len(right)}")
    return 1


def ledger(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    rows = []
    summary = None
    per_dest = []
    for line in text:
        if not line.startswith(SORT):
            continue
        body = line[len(SORT):]
        if body.startswith(("instruction:", "capability:", "reach:", "coverage:")):
            print(body)
        match = ATTEMPT.search(line)
        if match:
            rows.append(match.groups())
        match = LEDGER.search(line)
        if match:
            summary = tuple(int(v) for v in match.groups())
        match = PER_DEST.search(line)
        if match:
            per_dest.append(tuple(int(v) for v in match.groups()))

    print()
    print(f"{'att':>3} {'idx':>3} {'fruit':<11} {'d cm':>4} {'grade':>5} {'arm':<5} "
          f"{'dest':>4} {'target':<15} {'placed':>6} {'release':<20} {'on':>2} "
          f"{'side':>4} {'near':>4} {'dist':>5} {'in':>2}")
    for row in rows:
        (attempt, index, fruit, diameter, grade, ripeness, arm, dest, target,
         placed, release, on_belt, side, nearest, dist, in_dest) = row
        print(
            f"{attempt:>3} {index:>3} {fruit:<11} {diameter:>4} {grade:>5} {arm:<5} "
            f"{dest:>4} {target:<15} {placed:>6} {(release or '-'):<20} "
            f"{(on_belt or '-'):>2} {(side or '-'):>4} {(nearest or '-'):>4} "
            f"{(dist or '-'):>5} {(in_dest or '-'):>2}"
        )
    print()
    if summary is None:
        print("no ledger summary row (the run did not reach the end)")
        return 1
    attempts, assigned, released, in_dest, mis, not_placed, refused, unassigned, skip = summary
    accuracy = (100.0 * in_dest / released) if released else 0.0
    print(
        f"ledger: attempts={attempts} assigned={assigned} released={released} "
        f"in_destination={in_dest} mis_sorted={mis} not_placed={not_placed} "
        f"refused={refused} pool unassigned={unassigned} skip={skip}"
    )
    print(
        f"assignment accuracy: {in_dest}/{released} = {accuracy:.1f}% "
        f"(mis-sorted {mis}; not-placed attempts excluded)"
    )
    for dest, att, rel, good, bad, miss in per_dest:
        print(f"  dest {dest}: attempts={att} released={rel} in={good} mis={bad} not_placed={miss}")
    return 0 if mis == 0 and refused == 0 and released == in_dest else 1


def accept(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    stats = [line for line in text.splitlines() if "[stats]" in line]
    fingerprint = [line for line in text.splitlines() if "fingerprint:" in line]
    for line in stats[-1:]:
        print(line)
    for line in fingerprint[-1:]:
        print(line)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--same", nargs=2, metavar=("A", "B"))
    parser.add_argument("--ledger")
    parser.add_argument("--accept")
    parser.add_argument("--keep-sort", action="store_true")
    args = parser.parse_args()
    if args.same:
        return same(args.same[0], args.same[1], args.keep_sort)
    if args.ledger:
        return ledger(args.ledger)
    if args.accept:
        return accept(args.accept)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
