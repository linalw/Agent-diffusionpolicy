#!/usr/bin/env python3
"""P42 phase 1 - is the seat instrument free, and is the default inert?

    python3 logs/p42/p2/identity.py > logs/p42/p2/identity.txt

Read-only. Three comparisons on the physics `[fruit]` stream:

1. **default inert** - `control_accept.log` (the P42 tree, `FRUIT_SEAT_DIAG`
   unset) against the P41 tree's own control `logs/p41/p3/accept_control.log`
   (the record `configs/motion_reference.json` **8a399626** was written from).
   A difference here is the P42 edit leaking into the shipped path.
2. **instrument free** - `seat_accept.log` (`FRUIT_SEAT_DIAG=1`) against
   `control_accept.log`, with every `[seat]` row filtered out. A difference here
   is the instrument's cost on the branch (the reads it adds), not the tree's.
3. the same pair for the pear battery (`pear_control.log` unset vs
   `seat_pear.log`).

`[seat]` rows are removed before every comparison, so comparison 2/3 is
"everything except the new print". `[trace]`/`[drive]`/build-profile lines are
filtered as in `logs/p41/p3/first_divergence.py` (print-only, documented).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path("logs/p42/p2")


def rows(path: Path) -> list[str]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith("[fruit]"):
            continue
        if "[seat]" in line:
            continue
        # Print-only rows that differ by *which* instrument was armed, not by
        # behaviour: `[trace]`/`[drive]`/the build profile (as in
        # `logs/p41/p3/first_divergence.py`) and P41's own `[diag] carry-assist`
        # rows, which only exist under `FRUIT_CARRY_DIAG=1` (the P41 control ran
        # with it, the P42 control does not).
        if (
            "[trace]" in line
            or "[drive]" in line
            or "[diag]" in line
            or "[carry]" in line
            or "finger drive profile=" in line
        ):
            continue
        out.append(line)
    return out


def compare(label: str, left_path: Path, right_path: Path) -> None:
    left = rows(left_path)
    right = rows(right_path)
    print(f"=== {label}")
    print(f"  A {left_path} ({len(left)} rows)")
    print(f"  B {right_path} ({len(right)} rows)")
    diff = None
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            diff = index
            break
    if diff is None and len(left) == len(right):
        print(f"  IDENTICAL on all {len(left)} rows")
        print()
        return
    if diff is None:
        diff = min(len(left), len(right))
        print(f"  prefix identical for {diff} rows, then one stream ends")
    else:
        print(f"  FIRST DIFFERENCE at row {diff}")
    for k in range(max(0, diff - 1), min(diff + 2, len(left), len(right))):
        print(f"    A[{k}]: {left[k]}")
        print(f"    B[{k}]: {right[k]}")
    print()


def main() -> int:
    compare(
        "1 default inert: P42 tree (knob unset) vs the P41 record",
        ROOT / "control_accept.log",
        Path("logs/p41/p3/accept_control.log"),
    )
    compare(
        "2 instrument free: seat-on vs knob-unset (acceptance)",
        ROOT / "seat_accept.log",
        ROOT / "control_accept.log",
    )
    compare(
        "3 instrument free: seat-on vs knob-unset (pear)",
        ROOT / "seat_pear.log",
        ROOT / "pear_control.log",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
