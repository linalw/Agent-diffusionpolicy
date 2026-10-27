"""Where an episode's sim time actually goes: the policy phase vs the primitive.

    python3 logs/p52/p2/policy_share.py

No simulator. Reads the `[rl] episode ... ticks=... decision=...` rows of the
existing corpora and reports, over the **placed** episodes only, the median of

* ``decision=`` - the control-step index the primitive took over at
  (`rl_env.py::_run_primitive` sets `self._decision_step = self._step`), i.e. the
  **policy phase** in 120 Hz ticks;
* ``ticks=``   - the whole episode in 120 Hz ticks (`_finalize`, sim time);
* the difference - the **scripted primitive** plus finalisation.

Why this tool exists. `logs/p52/MODEL_CENSUS.md` section 1.4 reports a policy
phase of 1034/985 ticks = "54-57 %" of the episode and 6.4-6.8 s of "arm motion"
per episode, which is what its 11-12 % re-timing prediction is built on. That
decomposition does not reproduce: `decision=` is a *tick* index, and its
per-episode values are 250-270 ticks, not 985. The census's own belt-floor
number (2.08-2.23 s between the first model call and the fire tick) is
**larger than the whole policy phase**, which is the tell: the policy phase *is*
the rendezvous with the belt, and the arm motion inside it is a fraction of it.
`decision / 4` also reproduces the `[retime]` instrument's own decision count
(75 counted decisions for a 303-tick phase), i.e. ``decision`` really is a tick
index and not a count of 4-tick decisions - an independent cross-check.

No `src/` change is implied by this: it is a provenance correction to the
census, and the phase-2 verdict is read from the measured engine, not from it.
"""

from __future__ import annotations

import glob
import re
import statistics as st

EPISODE = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))?"
)

CORPORA = [
    ("P43 park A/B (moe_v13s, the P43 protocol)", "logs/p43/p3/[AB]_*.log"),
    ("P35 park A/B (moe_v13s)", "logs/p35/C_ab/[AB]_*.log"),
    ("P52 phase 2 lane A (this batch)", "logs/p52/p2/[AB]_[0-9].log"),
]


def census(pattern: str) -> dict | None:
    rows = []
    for path in sorted(glob.glob(pattern)):
        for line in open(path, encoding="utf-8", errors="ignore"):
            found = EPISODE.search(line)
            if not found or found.group(8) != "True" or not found.group(10):
                continue
            rows.append((int(found.group(9)), int(found.group(10)), found.group(2)))
    if not rows:
        return None
    total = [r[0] for r in rows]
    policy = [r[1] for r in rows]
    scripted = [t - p for t, p in zip(total, policy)]
    return {
        "n": len(rows),
        "policy_p50": st.median(policy),
        "total_p50": st.median(total),
        "scripted_p50": st.median(scripted),
        "share": st.median(policy) / st.median(total),
        # approximate: the last decision is partial, so `decision / 4` rounds
        "decisions_p50": st.median([p / 4 for p in policy]),
    }


def main() -> int:
    print("=" * 78)
    print("Where an episode's sim time goes (placed episodes, 120 Hz ticks)")
    print("=" * 78)
    for name, pattern in CORPORA:
        row = census(pattern)
        if row is None:
            print(f"  {name}: no placed rows")
            continue
        print(f"  {name}")
        print(f"    n={row['n']}  policy phase {row['policy_p50']:.0f} ticks "
              f"({row['policy_p50'] / 120:.2f} s, "
              f"{row['decisions_p50']:.0f} model calls)  "
              f"scripted {row['scripted_p50']:.0f} ticks "
              f"({row['scripted_p50'] / 120:.2f} s)  "
              f"total {row['total_p50']:.0f} ticks ({row['total_p50'] / 120:.2f} s)")
        print(f"    -> the policy phase is {row['share']:.0%} of the episode; "
              f"the scripted primitive is {1 - row['share']:.0%}")
    print()
    print("  The census's section 1.4 reads 54-57 % policy phase (1034/985 ticks).")
    print("  That does not reproduce: `decision=` is a tick index, not a count of")
    print("  4-tick decisions, and it is 250-270 ticks on every corpus above - less")
    print("  than the census's own 2.08-2.23 s belt floor, i.e. the policy phase is")
    print("  the belt rendezvous, not 6.4-6.8 s of arm motion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
