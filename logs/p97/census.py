#!/usr/bin/env python3
"""P97: the shipped default's own pre-leg pad census (P95/P96's criterion, one cell).

    python3 logs/p97/census.py          # -> logs/p97/census.txt

The cell is `S5` (seed 5, 20 attempts, `FRUIT_BIARM_PREPOSE_CLEAR` **unset** - the
shipped default) with P96's trace instrumentation. The instrument is
`logs/p96/pg_census.py` run against this phase's own `S5.log` / `trS5/` - the
geometry, the constants and the verdict rule are P96's, unchanged (a **contact**
is `pad gap <= 6 mm` **and** that hand's measured span swing `>= 2 mm` within
+-4 ticks; the gap ranks, the span is the verdict). Re-implementing the geometry
here would be a second source of truth, which is the thing P72/P93 forbid.
"""

from __future__ import annotations

import importlib.util
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

spec = importlib.util.spec_from_file_location(
    "pg_census_p96", os.path.join(ROOT, "logs", "p96", "pg_census.py")
)
pg = importlib.util.module_from_spec(spec)
sys.modules["pg_census_p96"] = pg
spec.loader.exec_module(pg)

#: The census resolves this phase's own log and trace dir through `HERE`.
pg.HERE = HERE


def main() -> int:
    out = []

    def print_(line=""):
        out.append(line)

    print_("P97 - the shipped default's pre-leg pad census (P95/P96 criterion, unchanged)")
    print_("Criterion: a CONTACT is `pad gap <= 6 mm` AND that hand's measured jaw-span")
    print_("swing `>= 2 mm` within +-4 ticks. The gap ranks (+-5 mm, angled plates);")
    print_("the span is the verdict (the drive is stiffness-limited to 0.1 mm).")
    print_()
    rows = pg.census_cell("S5", 5, True, "trS5", "logs/p94/T5.log", print_)
    gaps = [r["gap"] for r in rows]
    hits = [r for r in rows if r["contact"]]
    print_("=" * 116)
    print_("THE SHIPPED DEFAULT (seed 5, 20 attempts) - the contact count is the endpoint")
    print_("=" * 116)
    print_(f"  n={len(rows)}  min gap {min(gaps, default=float('nan')):+.1f} mm  "
           f"median {st.median(gaps) if gaps else float('nan'):+.1f} mm  "
           f"<= 6 mm {sum(1 for g in gaps if abs(g) <= pg.GAP_TOUCH)}/{len(rows)}  "
           f"CONTACTS {len(hits)}/{len(rows)}")
    for arm in ("left", "right"):
        sub = [r for r in rows if r["arm"] == arm]
        if not sub:
            continue
        print_(f"  {arm:<5} n={len(sub)} min {min(r['gap'] for r in sub):+.1f} "
               f"median {st.median([r['gap'] for r in sub]):+.1f} "
               f"<=6mm {sum(1 for r in sub if abs(r['gap']) <= pg.GAP_TOUCH)} "
               f"contacts {sum(1 for r in sub if r['contact'])}")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "census.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return 0 if not hits else 3


if __name__ == "__main__":
    raise SystemExit(main())
