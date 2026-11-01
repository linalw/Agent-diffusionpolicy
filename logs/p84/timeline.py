#!/usr/bin/env python3
"""P84 post-hoc: the per-attempt timeline, and what follows a trip.

    python3 logs/p84/timeline.py D5 F5 D6 F6

Read-only. **The two-line prints its per-attempt `[run] attempt ...` rows in one
block at the end of the run** (the driver's summary table), while the
`[biarm] result` rows print live as each attempt completes - so this reads the
result rows in completion order (which is what the log gives) and attaches the
`[fail-fast]` trip that fired inside that attempt.

For each attempt it prints the arm, the fruit, whether a trip fired (and its
tick / the leg's length), the outcome, the lift and the span, plus the class of
the *previous* attempt on the same arm. That is the G8 read ("an aborted attempt
is followed by a normal attempt") and the read that asks whether the abort
**cascades**: if the attempts following a trip fail systematically, the abort is
not only re-timing the presentation, it is leaving the line in a state the next
attempt inherits.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRIP = re.compile(r"\[fail-fast\] (?P<arm>\w+) (?P<leg>\w+): trip=t(?P<t>\d+)/(?P<n>\d+)")
RESULT = re.compile(
    r"\[biarm\] result (?P<arm>\w+) index=(?P<i>\d+) (?P<fruit>\w+) "
    r"grasped=(?P<g>\w+) placed=(?P<p>\w+) lift=(?P<l>[+\-\d.]+) "
    r"force=(?P<f>[\d.]+) sim=(?P<s>[\d.]+)s")


def timeline(path: str) -> list[dict]:
    rows: list[dict] = []
    pending: dict | None = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = TRIP.search(line)
        if m:
            pending = {"arm": m.group("arm"), "tick": int(m.group("t")),
                       "ticks": int(m.group("n")), "leg": m.group("leg")}
            continue
        m = RESULT.search(line)
        if m:
            arm = m.group("arm")
            trip = pending if (pending and pending["arm"] == arm) else None
            pending = None
            rows.append({"arm": arm, "fruit": m.group("fruit"),
                         "grasped": m.group("g") == "True",
                         "placed": m.group("p") == "True",
                         "lift": float(m.group("l")), "sim": float(m.group("s")),
                         "trip": trip})
    return rows


def main(argv: list[str]) -> int:
    tags = argv or ["D5", "F5", "D6", "F6"]
    for tag in tags:
        path = os.path.join(HERE, f"{tag}.log")
        if not os.path.exists(path):
            print(f"== {tag}: MISSING")
            continue
        rows = timeline(path)
        n_trip = sum(1 for r in rows if r["trip"])
        print(f"== {tag}: {len(rows)} attempts, {n_trip} trips, "
              f"{sum(1 for r in rows if r['placed'])} placed")
        print(f"  {'#':>3} {'arm':>5} {'fruit':>10} {'trip':>15} {'outcome':>7} "
              f"{'lift':>7} {'sim':>6}  previous attempt on the same arm")
        prev = {"left": "—", "right": "—"}
        after_trip = {"n": 0, "placed": 0, "trip": 0, "fail_other": 0}
        for i, r in enumerate(rows):
            outcome = "placed" if r["placed"] else ("cnp" if r["grasped"] else "never")
            trip = (f"t{r['trip']['tick']}/{r['trip']['ticks']} {r['trip']['leg']}"
                    if r["trip"] else "-")
            print(f"  {i:>3} {r['arm']:>5} {r['fruit']:>10} {trip:>15} {outcome:>7} "
                  f"{r['lift']:>+7.3f} {r['sim']:>6.1f}  {prev[r['arm']]}")
            prev[r["arm"]] = outcome + (" +trip" if r["trip"] else "")
        # the cascade read: what follows a trip, on the same arm and on the other
        for i, r in enumerate(rows):
            if not r["trip"]:
                continue
            j = next((k for k in range(i + 1, len(rows)) if rows[k]["arm"] == r["arm"]), None)
            if j is None:
                continue
            after_trip["n"] += 1
            nxt = rows[j]
            if nxt["placed"]:
                after_trip["placed"] += 1
            elif nxt["trip"]:
                after_trip["trip"] += 1
            else:
                after_trip["fail_other"] += 1
        if after_trip["n"]:
            print(f"  after a trip, the same arm's next attempt: "
                  f"{after_trip['placed']}/{after_trip['n']} placed, "
                  f"{after_trip['trip']} tripped again, "
                  f"{after_trip['fail_other']} failed without a trip")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
