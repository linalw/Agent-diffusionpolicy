#!/usr/bin/env python3
"""P39 phase 3 - the `[fruit]`-stream filter and the filtered identity test.

PREREG **Amendment A2.2** makes every byte-identity criterion in this phase a
*filtered* claim:

    grep '\\[fruit\\]' <log> | grep -v '\\[attitude\\]'

plus, for the phase-2 logs only, `grep -v 'finger tip delta'` (the build print
that used `say()` before A2.2 moved it to a plain `[p39]` print).  `[p39]` rows
are not `[fruit]` at all, so they never appear.

    python3 logs/p39/p3/filter_stream.py --counts LOG [LOG...]
    python3 logs/p39/p3/filter_stream.py --diff A B        # exit 0 iff identical
    python3 logs/p39/p3/filter_stream.py LOG               # print the stream
"""

from __future__ import annotations

from pathlib import Path

FRUIT = "[fruit]"
DROP = ("[attitude]", "finger tip delta")
#: The output-belt clearance message rows - **print-only** text (they describe the
#: scene's belt placement, not a physics step). The P32 phase D pair
#: (`93` vs `D1`) is recorded in AGENTS section 2 as identical "except the two
#: print-only output-belt clearance message lines", so the phase-3 F-6 read is
#: quoted both with and without them (`--drop-belt`).
BELT = ("[fruit] output belt ",)


def raw_lines(path: str) -> list[str]:
    return [
        line.rstrip("\n")
        for line in Path(path).read_text(errors="replace").splitlines()
        if line.startswith(FRUIT)
    ]


def filtered(path: str, drop_belt: bool = False) -> list[str]:
    out = [ln for ln in raw_lines(path) if not any(m in ln for m in DROP)]
    if drop_belt:
        out = [ln for ln in out if not any(ln.startswith(m) for m in BELT)]
    return out


def counts(path: str) -> tuple[int, int, int]:
    raw = raw_lines(path)
    att = sum("[attitude]" in ln for ln in raw)
    build = sum("finger tip delta" in ln for ln in raw)
    return len(raw), att, len(raw) - att - build


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:]]
    drop_belt = "--drop-belt" in args
    args = [a for a in args if a != "--drop-belt"]
    if args and args[0] == "--counts":
        print("| log | raw `[fruit]` | `[attitude]` | build print | filtered |")
        print("|---|---|---|---|---|")
        for path in args[1:]:
            raw, att, filt = counts(path)
            print(f"| `{path}` | {raw} | {att} | {raw - att - filt} | **{filt}** |")
        return 0
    if args and args[0] == "--diff":
        if len(args) != 3:
            print(__doc__)
            return 2
        a, b = filtered(args[1], drop_belt), filtered(args[2], drop_belt)
        ca, cb = counts(args[1]), counts(args[2])
        print(f"A `{args[1]}`: raw={ca[0]} attitude={ca[1]} filtered={ca[2]}")
        print(f"B `{args[2]}`: raw={cb[0]} attitude={cb[1]} filtered={cb[2]}")
        if drop_belt:
            print("(--drop-belt: the print-only `output belt` message rows are removed)")
        if a == b:
            print(f"IDENTICAL: {len(a)}/{len(a)} filtered `[fruit]` lines")
            return 0
        print(f"DIFFERENT: {len(a)} vs {len(b)} filtered `[fruit]` lines")
        for i, (la, lb) in enumerate(zip(a, b)):
            if la != lb:
                print(f"first difference at filtered line {i + 1}/{min(len(a), len(b))}:")
                print(f"  A: {la}")
                print(f"  B: {lb}")
                break
        else:
            longer = a if len(a) > len(b) else b
            print(f"first difference beyond the shorter stream (line {min(len(a), len(b)) + 1}):")
            print(f"  {'A' if len(a) > len(b) else 'B'}: {longer[min(len(a), len(b))]}")
        return 1
    if len(args) == 1:
        print("\n".join(filtered(args[0])))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
