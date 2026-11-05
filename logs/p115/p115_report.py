#!/usr/bin/env python3
"""P115 report - the instruction's decision ledger, read by rule.

P115 adds `rule=<n>` to each `[sort] attempt` row, so a run can be read as
*which rule decided what*, not only *where the fruit went*. That matters as soon
as a rule carries `and`: an apple on the right belt is rule 1
(`species=apple and size>=66`), not a grade decision.

  python3 logs/p115/p115_report.py --ledger logs/p115/compound.log
  python3 logs/p115/p115_report.py --same logs/p115/accept_unset.log logs/p110/accept_noharm.log

`--same` drops the `[sort]`/`[scenario]` rows and compares the physics stream
line for line (the P114 convention). Exit 0 on pass / on a readable log.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SORT = "[fruit] [sort] "
ATTEMPT = re.compile(
    r"\[sort\] attempt (\d+) idx=(\d+) (\S+) d=([\d.]+)cm grade=(\S+) "
    r"ripeness=([\d.]+) arm=(\S+) (?:rule=(\S+) )?dest=(\d+) "
    r"target=\(([^)]+)\) placed=(\d+)(?: .*?in_dest=(\d+))?"
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
COVERAGE = re.compile(r"\[sort\] coverage: pool=(\d+) mapped=(\d+) unassigned=(\d+) skip=(\d+)")


def stream(path: str) -> list[str]:
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if "[fruit]" not in line:
            continue
        if SORT in line:
            continue
        out.append(line)
    return out


def same(a: str, b: str) -> int:
    left, right = stream(a), stream(b)
    print(f"A {a}: {len(left)} [fruit] lines")
    print(f"B {b}: {len(right)} [fruit] lines")
    if left == right:
        print(f"IDENTICAL: {len(left)}/{len(left)} lines (the [sort] rows dropped)")
        return 0
    for index, (x, y) in enumerate(zip(left, right)):
        if x != y:
            print(f"DIFFERS at line {index}:")
            print(f"  A: {x[:150]}")
            print(f"  B: {y[:150]}")
            break
    print(f"{sum(1 for x, y in zip(left, right) if x == y)}/{min(len(left), len(right))} prefix-identical")
    return 1


def ledger(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    rows = [m for m in ATTEMPT.finditer(text)]
    ledger_row = LEDGER.search(text)
    if not rows and ledger_row is None:
        print(f"{path}: no [sort] rows - was FRUIT_SORT_INSTRUCTION set?")
        return 1

    print(f"P115 ledger - {path}")
    coverage = COVERAGE.search(text)
    if coverage:
        pool, mapped, unassigned, skip = coverage.groups()
        print(f"  coverage: pool={pool} mapped={mapped} unassigned={unassigned} skip={skip}")
    if ledger_row:
        (attempts, assigned, released, in_destination, mis_sorted, not_placed,
         refused, unassigned, skip) = ledger_row.groups()
        accuracy = (int(in_destination) / int(released)) if int(released) else float("nan")
        print(
            f"  attempts={attempts} assigned={assigned} released={released} "
            f"in_destination={in_destination} mis_sorted={mis_sorted} "
            f"not_placed={not_placed} refused={refused} "
            f"-> assignment accuracy {accuracy:.1%}"
        )
    for match in PER_DEST.finditer(text):
        dest, attempts, released, in_dest, mis, not_placed = match.groups()
        print(
            f"  dest {dest}: attempts={attempts} released={released} "
            f"in_destination={in_dest} mis_sorted={mis} not_placed={not_placed}"
        )

    by_rule: dict[str, dict[str, int]] = {}
    for match in rows:
        rule = match.group(8) or "?"
        placed = match.group(11) == "1"
        in_dest = match.group(12)
        entry = by_rule.setdefault(rule, {"attempts": 0, "released": 0, "in": 0})
        entry["attempts"] += 1
        if placed:
            entry["released"] += 1
            entry["in"] += int(in_dest or 0)
    print("  by rule (which rule decided):")
    for rule in sorted(by_rule, key=lambda r: (not r.isdigit(), int(r) if r.isdigit() else 0)):
        entry = by_rule[rule]
        label = f"rule {rule}" if rule.isdigit() else rule
        print(
            f"    {label:<12} attempts={entry['attempts']:>2} "
            f"released={entry['released']:>2} in_destination={entry['in']:>2}"
        )
    return 0


def main() -> int:
    if len(sys.argv) >= 4 and sys.argv[1] == "--same":
        return same(sys.argv[2], sys.argv[3])
    if len(sys.argv) >= 3 and sys.argv[1] == "--ledger":
        return ledger(sys.argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
