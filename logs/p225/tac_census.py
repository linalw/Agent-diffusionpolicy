#!/usr/bin/env python3
"""P225o: per-attempt per-pad force census on a `[carry-force]` log.

The instrument is the P225o row (`pads=[f0,f1,...]`, one row per 8 ticks while
the carry-force servo runs). This script groups the rows into attempts (a gap
of >120 ticks starts a new group), joins them to the `[rl] episode` rows in
order, and reports per attempt:

  * `one_sided` - the fraction of rows with `min(pads) < 0.5 N` while
    `max(pads) > 2 N` (P75's measured escape signature);
  * `t_one` / `t_loss` - the first one-sided tick and the first tick at which
    the sum falls below 1 N *after* having been above 5 N;
  * `lead` - `t_loss - t_one` (the reaction window the scalar pair preserves).

Run:  python3 logs/p225/tac_census.py <log> [<log> ...]
"""
from __future__ import annotations

import re
import sys

ROW = re.compile(
    r"\[carry-force\] t=(\d+) arm=(\w+) F=\s*([0-9.]+)N pads=\[([^\]]*)\]"
)
EP = re.compile(r"\[rl\] episode (\d+): (\w+) d=([0-9.]+)cm bin=(\d) arm=(\w+) "
                r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)")


def groups(rows, gap=120):
    """Split on a gap **or an arm change** (attempts alternate arms)."""
    out, cur = [], []
    last = None
    last_arm = None
    for t, arm, pads in rows:
        if last is not None and (t <= last or t - last > gap or arm != last_arm):
            out.append(cur)
            cur = []
        cur.append((t, arm, pads))
        last, last_arm = t, arm
    if cur:
        out.append(cur)
    return out


def main(argv):
    for path in argv[1:]:
        text = open(path, errors="ignore").read()
        rows = []
        for m in ROW.finditer(text):
            pads = [float(v) for v in m.group(4).split(",") if v.strip()]
            rows.append((int(m.group(1)), m.group(2), pads))
        eps = [
            dict(ep=int(m.group(1)), cat=m.group(2), dia=float(m.group(3)),
                 arm=m.group(5), ok=m.group(6) == "True",
                 g=m.group(7) == "True", p=m.group(8) == "True",
                 ticks=int(m.group(9)))
            for m in EP.finditer(text)
        ]
        print(f"== {path}: {len(eps)} episodes, {len(rows)} carry-force rows")
        for g in groups(rows):
            n = len(g)
            one = sum(
                1 for _, _, pads in g
                if len(pads) >= 2 and min(pads) < 0.5 and max(pads) > 2.0
            )
            t_one = next(
                (t for t, _, pads in g
                 if len(pads) >= 2 and min(pads) < 0.5 and max(pads) > 2.0),
                None,
            )
            peak = 0.0
            t_loss = None
            for t, _, pads in g:
                s = sum(pads) if pads else 0.0
                if s > 5.0:
                    peak = max(peak, s)
                elif peak > 5.0 and s < 1.0 and t_loss is None:
                    t_loss = t
            lead = None if (t_one is None or t_loss is None) else t_loss - t_one
            print(
                f"  arm={g[0][1]:5s} rows={n:4d} t={g[0][0]:5d}-{g[-1][0]:5d} "
                f"one_sided={one/max(1,n):.2f} t_one={t_one} t_loss={t_loss} "
                f"lead={lead}"
            )
        for e in eps:
            print(
                f"  ep {e['ep']:2d} {e['cat']:10s} {e['dia']:4.1f}cm {e['arm']:5s} "
                f"ok={int(e['ok'])} g={int(e['g'])} p={int(e['p'])} ticks={e['ticks']}"
            )


if __name__ == "__main__":
    main(sys.argv)
