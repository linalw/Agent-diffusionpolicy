#!/usr/bin/env python3
"""P82 report: per-cell throughput + the arbiter decomposition, and the A/B checks.

    python3 logs/p82/p82_report.py logs/p82/R1.log logs/p82/R2.log ...
    python3 logs/p82/p82_report.py --same logs/p80/T20.log logs/p82/R1.log

`--same` compares the `[fruit]` stream of two logs line-for-line (the bit-identity
test: a profile build or an optimization is admissible only if the physics record
is identical), and prints the first difference if any.

Throughput endpoints come from `logs/p80/p80lib.py` — the *same* parser and the
same wall definition (`[run] attempt 0` -> `[fruit] DONE` on the stamp stream) that
produced P80 §6, so a P82 cell and a P80 cell are one measurement. The arbiter
decomposition comes from the I2 timers JSON (`logs/p82/timers.py`), which exists
only for the profile builds.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("p80lib", os.path.join(HERE, "..", "p80", "p80lib.py"))
p80lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p80lib)

TIMERS = os.environ.get("P82_TIMERS")


def fruit_stream(path: str) -> list[str]:
    """Every `[fruit]`-prefixed line, in order (the physics record)."""
    out = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "[fruit]" in line:
                out.append(line.rstrip("\n"))
    return out


def show_same(reference: str, candidate: str) -> int:
    a, b = fruit_stream(reference), fruit_stream(candidate)
    same = a == b
    print(f"[same] reference={reference} ({len(a)} lines)  candidate={candidate} ({len(b)} lines)")
    if same:
        print("[same] IDENTICAL: every [fruit] line matches in order")
        return 0
    index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    print(f"[same] DIFFERS at line {index}")
    for name, stream in (("ref", a), ("cand", b)):
        if index < len(stream):
            print(f"  {name}: {stream[index][:200]}")
    print(f"  common prefix: {index} lines")
    return 1


def timers_of(path: str) -> dict | None:
    timer_path = os.path.splitext(path)[0] + ".timers.json"
    if not os.path.exists(timer_path):
        return None
    with open(timer_path, encoding="utf-8") as handle:
        return json.load(handle)


def cell(path: str, attempts_note: str = "") -> None:
    m = p80lib.metrics(path)
    stats = m.get("stats") or {}
    biarm = stats.get("biarm") or {}
    placed = m["placed"]
    att = m["attempts"]
    print(f"\n== {path} {attempts_note} ==")
    print(f"  placed {placed}/{att} = {100.0 * placed / max(1, att):.1f} %   "
          f"s/attempt {stats.get('per_attempt')}   sim span {stats.get('sim_total')} s"
          + (f"   per arm {biarm.get('l')}/{biarm.get('la')} left, "
             f"{biarm.get('r')}/{biarm.get('ra')} right" if biarm else ""))
    if stats.get("wall") is None:
        print("  wall: NO STAMPS")
        return
    wall = stats["wall"]
    print(f"  wall {wall:.1f} s   wall/pick {stats['wall_per_pick']:.1f} s   "
          f"wall/sim {stats['wall_over_sim']:.2f}   "
          f"placed/min wall {60.0 * placed / wall:.2f}")
    if m.get("pooled", {}).get("mean"):
        print(f"  interval mean {m['pooled']['mean']:.2f} s  p90 "
              f"{m['pooled']['p90']:.2f} s   placed/min window "
              f"{60.0 / m['pooled']['mean']:.2f}   batch "
              f"{(m['batch_rate'] or 0.0):.2f}")
    timers = timers_of(path)
    if timers:
        sched, steps = timers["sched"], timers["steps"]
        wall_main = timers.get("wall_main_s")
        span = timers.get("wall_from_first_round_s") or wall_main
        rounds, ticks = sched["rounds"], steps["ticks"]
        print(f"  [I2] rounds {rounds}  ticks {ticks}  rounds/tick "
              f"{timers['rounds_per_tick']}  wall(main) {wall_main} s  "
              f"wall(first round->exit) {span} s  "
              f"per-round {1000.0 * span / max(1, rounds):.2f} ms  "
              f"per-tick {1000.0 * span / max(1, ticks):.2f} ms")
        share = lambda value: 100.0 * value / max(1e-9, span)  # noqa: E731
        print(f"  [I2] physics {steps['step_total_s']:.1f} s ({share(steps['step_total_s']):.1f} %)  "
              f"arbiter {timers['arbiter_overhead_s']:.2f} s "
              f"({share(timers['arbiter_overhead_s']):.1f} %)  "
              f"worker segments {timers['segments']['total_s']:.1f} s "
              f"({share(timers['segments']['total_s']):.1f} %)  "
              f"main-thread wait {timers['pump']['total_s']:.1f} s "
              f"({share(timers['pump']['total_s']):.1f} %)")
        resid = span - (steps["step_total_s"] + timers["segments"]["total_s"]
                        + float(timers["arbiter_overhead_s"]))
        print(f"  [I2] residual (wait + handoff + feed/driver) "
              f"{resid:.1f} s ({share(resid):.1f} %)   "
              f"pump timeouts {timers['pump']['timeouts']}/{timers['pump']['calls']}")
        print(f"  [I2] per-round means: step {steps['per_step']['mean_ms']} ms  "
              f"segment {timers['segments']['per_segment']['mean_ms']} ms  "
              f"pump {timers['pump']['wait']['mean_ms']} ms  "
              f"round_self {sched['round_self']['mean_ms']} ms  "
              f"tick_frame calls {timers['tick_frame']['calls']} "
              f"({timers['tick_frame']['total_s']} s)")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--same":
        return show_same(argv[1], argv[2])
    for path in argv:
        cell(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
