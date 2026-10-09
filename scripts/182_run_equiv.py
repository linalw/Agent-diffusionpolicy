#!/usr/bin/env python3
"""Compare the deterministic `[fruit]` stream of two or more pick-and-place logs.

    scripts/182_run_equiv.py logs/x1/eq_seq.log logs/x1/eq_c1.log logs/x1/eq_c2.log

Startup noise (Kit banners, warnings, timing lines) is ignored; every line that
starts with `[fruit]` is kept, in order, because those are the lines the run's
branch is read off (attempt/fruit/leg/stats). This is the X1 equivalence check:
a run executed alone and the same run executed concurrently with others must
produce the same `[fruit]` stream if the instances are isolated.

Exit 0 iff every file's `[fruit]` stream is bit-identical to the first file's.
"""

from __future__ import annotations

import sys
from pathlib import Path


def fruit_lines(path: str) -> list[str]:
    return [
        line.rstrip("\n")
        for line in Path(path).read_text(errors="replace").splitlines()
        if line.startswith("[fruit]")
    ]


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    files = argv[1:]
    streams = {f: fruit_lines(f) for f in files}
    for f, stream in streams.items():
        print(f"{f}: {len(stream)} [fruit] line(s)")

    ref = files[0]
    ok = True
    for f in files[1:]:
        a, b = streams[ref], streams[f]
        if a == b:
            print(f"IDENTICAL: {f} == {ref}")
            continue
        ok = False
        n = min(len(a), len(b))
        idx = next((i for i in range(n) if a[i] != b[i]), n)
        print(f"DIFFERENT: {f} vs {ref}: first difference at [fruit] line {idx + 1}")
        print(f"  {ref}: {a[idx] if idx < len(a) else '<missing>'}")
        print(f"  {f}: {b[idx] if idx < len(b) else '<missing>'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
