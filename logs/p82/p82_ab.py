#!/usr/bin/env python3
"""P82 A/B: the wake-on-request cell against its control, and the wall arithmetic.

    python3 logs/p82/p82_ab.py

Cells (all `ATTEMPTS=20 SEED=<seed> FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`,
shipped scenario, the P80 battery):

    seed 5  two-line  off = logs/p80/T20.log   on = W1/W2/W3 (this phase)
    seed 6  two-line  off = logs/p80/T6.log    on = W4
    single  seed 5 = logs/p80/S20.log (+ this phase's R2, byte-identical)
            seed 6 = logs/p80/S6.log

The walls come from the same stamp instrument and the same definition as P80
(`[run] attempt 0` / first station-acquired -> `[fruit] DONE`), so the "1.02x
pooled" this phase is compared against is P80's own number recomputed here.
`--same` runs in `logs/p82/p82_report.py`.
"""

from __future__ import annotations

import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys_path = os.path.join(HERE, "..", "p80", "p80lib.py")
_spec = importlib.util.spec_from_file_location("p80lib", sys_path)
p80lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p80lib)

CELLS = [
    ("two-line OFF, seed 5 (P80 T20)", "logs/p80/T20.log"),
    ("two-line OFF, seed 5 (W0, post-patch tree)", "logs/p82/W0.log"),
    ("two-line ON,  seed 5 (W1)", "logs/p82/W1.log"),
    ("two-line ON,  seed 5 (W2 repeat)", "logs/p82/W2.log"),
    ("two-line ON,  seed 5 (W3, + timers)", "logs/p82/W3.log"),
    ("two-line OFF, seed 6 (P80 T6)", "logs/p80/T6.log"),
    ("two-line ON,  seed 6 (W4)", "logs/p82/W4.log"),
    ("single    ,   seed 5 (P80 S20)", "logs/p80/S20.log"),
    ("single    ,   seed 5 (R2, + timers)", "logs/p82/R2.log"),
    ("single    ,   seed 6 (P80 S6)", "logs/p80/S6.log"),
]


def row(path: str) -> dict:
    m = p80lib.metrics(path)
    stats = m["stats"]
    biarm = stats.get("biarm") or {}
    wall = stats.get("wall")
    # `[stats] sim=` is the *sum of attempt spans* on the single arm (the driver
    # gaps sit between them) but the whole batch on the two-line, so the clock
    # factor uses `batch_span` (`t_last_end - t_first_start`, P80's definition).
    s_span = m["batch_span"]
    return {
        "placed": m["placed"],
        "attempts": m["attempts"],
        "rate": m["rate"],
        "sim": stats.get("sim_total"),
        "batch_span": s_span,
        "per_attempt": stats.get("per_attempt"),
        "wall": wall,
        "wall_per_pick": stats.get("wall_per_pick"),
        "wall_over_sim": stats.get("wall_over_sim"),
        "wall_rate": (60.0 * m["placed"] / wall) if wall else None,
        "left": biarm.get("l"),
        "left_n": biarm.get("la"),
        "right": biarm.get("r"),
        "right_n": biarm.get("ra"),
    }


def main() -> int:
    print(f"{'cell':44s} {'placed':>8s} {'sim s':>7s} {'s/att':>6s} "
          f"{'wall s':>7s} {'wall/pick':>9s} {'wall/sim':>8s} {'placed/min':>10s}")
    table = {}
    for label, path in CELLS:
        if not os.path.exists(path):
            print(f"{label:44s}  MISSING {path}")
            continue
        r = row(path)
        table[path] = r
        arm = (f"{r['left']}/{r['left_n']}+{r['right']}/{r['right_n']}"
               if r["left"] is not None else "")
        print(f"{label:44s} {r['placed']:3d}/{r['attempts']:<4d} {r['sim']:7.1f} "
              f"{r['per_attempt']:6.2f} {r['wall']:7.1f} {r['wall_per_pick']:9.2f} "
              f"{r['wall_over_sim']:8.2f} {r['wall_rate']:10.2f}   {arm}")

    single = [table["logs/p80/S20.log"], table["logs/p80/S6.log"]]
    off = [table["logs/p80/T20.log"], table["logs/p80/T6.log"]]
    on = [table["logs/p82/W1.log"], table["logs/p82/W4.log"]]
    single_wall = sum(c["wall_rate"] for c in single) / 2
    off_wall = sum(c["wall_rate"] for c in off) / 2
    on_wall = sum(c["wall_rate"] for c in on) / 2
    single_pick = sum(c["wall_per_pick"] for c in single) / 2
    on_pick = sum(c["wall_per_pick"] for c in on) / 2
    off_pick = sum(c["wall_per_pick"] for c in off) / 2
    single_wsi = sum(c["wall_over_sim"] for c in single) / 2
    on_wsi = sum(c["wall_over_sim"] for c in on) / 2
    off_wsi = sum(c["wall_over_sim"] for c in off) / 2
    clock = sum(c["batch_span"] / c["attempts"] for c in single) / 2 / (
        sum(c["batch_span"] / c["attempts"] for c in on) / 2)
    clock_off = sum(c["batch_span"] / c["attempts"] for c in single) / 2 / (
        sum(c["batch_span"] / c["attempts"] for c in off) / 2)

    print("\n== the wall arithmetic (mean of the two seeds' per-cell rates) ==")
    print(f"  single arm placed/min wall        {single_wall:.2f}  "
          f"(wall/pick {single_pick:.1f} s, wall/sim {single_wsi:.2f})")
    print(f"  two-line OFF placed/min wall      {off_wall:.2f}  "
          f"(wall/pick {off_pick:.1f} s, wall/sim {off_wsi:.2f})  -> {off_wall / single_wall:.2f}x")
    print(f"  two-line ON  placed/min wall      {on_wall:.2f}  "
          f"(wall/pick {on_pick:.1f} s, wall/sim {on_wsi:.2f})  -> {on_wall / single_wall:.2f}x")
    print(f"  harness factor ON/single (wall/sim) {on_wsi / single_wsi:.2f}x   "
          f"OFF/single {off_wsi / single_wsi:.2f}x")
    print(f"  wall per pick ON/single           {single_pick / on_pick:.2f}x   "
          f"OFF/single {single_pick / off_pick:.2f}x")
    print(f"  the arithmetic: sim clock {clock:.2f}x (OFF {clock_off:.2f}x) / harness "
          f"{on_wsi / single_wsi:.2f}x = {clock / (on_wsi / single_wsi):.2f}x wall per pick")
    print(f"  the count: placed per attempt    "
          f"single {sum(c['rate'] for c in single) / 2:.3f}  "
          f"OFF {sum(c['rate'] for c in off) / 2:.3f}  "
          f"ON {sum(c['rate'] for c in on) / 2:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
