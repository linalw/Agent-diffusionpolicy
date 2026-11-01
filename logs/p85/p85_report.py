#!/usr/bin/env python3
"""P85 readout: the flip's evidence and the speed-union re-price.

    python3 logs/p85/p85_report.py --same-with-diag logs/p80/T20.log logs/p85/base20_s5.log
    python3 logs/p85/p85_report.py --cells logs/p85/base20_s5.log logs/p85/speed20_s5.log ...
    python3 logs/p85/p85_report.py --accel

`--same-with-diag` is the P84 convention: compare the `[fruit]` stream line for
line, dropping only the phase's instrumentation rows (`[fruit] [carry]` tracker
lines and the one new `[fruit] [biarm] scheduler:` banner). A difference on the
filtered stream is a physics difference.

`--cells` prints the P80/P83 endpoints (placed, `s/attempt`, pooled and per-arm
interval, both denominators, the wall column, lock-on, idle, starvation, the
class/reason split, the arm split and the E3 slip guard) for each log.

`--accel` is the pre-registered E1-E4 table for seeds 5 and 6.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

_spec = importlib.util.spec_from_file_location("p80lib", os.path.join(HERE, "..", "p80", "p80lib.py"))
p80lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p80lib)

#: Instrumentation rows the sealed comparison drops (P84's convention).
DROP = (
    "[fruit] [carry]",
    "[fruit] [biarm] scheduler:",
    # P84's list, in full: the carry tracker, its per-tick `[diag] carry-assist`
    # rows and the park trace. None of them is a control input.
    "[fruit] [diag] carry-assist",
    "[fruit] [biarm] left: park",
    "[fruit] [biarm] right: park",
)


def fruit_stream(path: str, drop_diag: bool = True) -> list[str]:
    out = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "[fruit]" not in line:
                continue
            text = line.rstrip("\n")
            if drop_diag and any(marker in text for marker in DROP):
                continue
            out.append(text)
    return out


def show_same(reference: str, candidate: str) -> int:
    a, b = fruit_stream(reference), fruit_stream(candidate)
    same = a == b
    print(f"[same] ref={reference} ({len(a)} physics lines)  cand={candidate} ({len(b)})")
    if same:
        print("[same] IDENTICAL on every physics line (diag rows dropped)")
        return 0
    index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    print(f"[same] DIFFERS at line {index}")
    for name, stream in (("ref", a), ("cand", b)):
        if index < len(stream):
            print(f"  {name}: {stream[index][:200]}")
    print(f"  common prefix: {index} lines")
    return 1


def carry_guard(path: str) -> dict:
    """E3's slip guard from the `[carry]` tracker rows (0 rows when the diag is off)."""
    rows = 0
    slips = []
    zero_force = 0
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "[carry]" not in line or "clean_slip" not in line:
                continue
            rows += 1
            match = re.search(r"clean_slip(?:max)?=([\d.]+)mm", line)
            if match:
                slips.append(float(match.group(1)))
            if re.search(r"force_min=0\.00", line):
                zero_force += 1
    return {
        "rows": rows,
        "over_50": sum(1 for v in slips if v > 50.0),
        "max": max(slips) if slips else None,
        "zero_force": zero_force,
    }


def cell(path: str) -> dict:
    m = p80lib.metrics(path)
    stats = m.get("stats") or {}
    guard = carry_guard(path)
    print(f"\n== {path} ==")
    print(
        f"  placed {m['placed']}/{m['attempts']} = {100.0 * (m['rate'] or 0):.1f} %   "
        f"s/attempt {p80lib.fmt(stats.get('per_attempt'))}   "
        f"sim {p80lib.fmt(stats.get('sim_total'))} s   diverted/stars {m['pending_slots']}"
    )
    if stats.get("biarm"):
        b = stats["biarm"]
        print(
            f"  per arm  left {b['l']}/{b['la']}   right {b['r']}/{b['ra']}   "
            f"pipelined slots {b['slots']}   biarm {b['rate']} fruits/min"
        )
    print(
        f"  pooled interval {p80lib.fmt(m['pooled']['mean'])} s mean / "
        f"{p80lib.fmt(m['pooled']['p50'])} p50 / {p80lib.fmt(m['pooled']['p90'])} p90 "
        f"(n={m['pooled']['n']})"
    )
    for arm, data in sorted(m["per_arm"].items()):
        print(
            f"    {arm}: placed {data['placed']}/{data['attempts']}  "
            f"interval {p80lib.fmt(data['interval_mean'])} / {p80lib.fmt(data['interval_p90'])} s  "
            f"idle {p80lib.fmt((data['idle_frac'] or 0) * 100, 1)} %"
        )
    print(
        f"  window {p80lib.fmt(m['window_rate'])} placed/min   "
        f"batch {p80lib.fmt(m['batch_rate'])} placed/min   "
        f"window span {p80lib.fmt(m['window'])} s   batch span {p80lib.fmt(m['batch_span'])} s"
    )
    if stats.get("wall") is not None:
        print(
            f"  wall {p80lib.fmt(stats['wall'], 1)} s   wall/pick {p80lib.fmt(stats['wall_per_pick'])} s   "
            f"wall/sim {p80lib.fmt(stats['wall_over_sim'])}x   "
            f"placed/min wall {p80lib.fmt(60.0 * m['placed'] / stats['wall'])}"
        )
    else:
        print("  wall: NO STAMPS")
    lock = m["lock_on"]
    if lock:
        for arm, data in sorted(lock.items()):
            print(
                f"  lock-on {arm}: {p80lib.fmt(data.get('mean'))} s mean / "
                f"{p80lib.fmt(data.get('p90'))} p90 (n={data.get('n')}, "
                f"retry polls {data.get('retries_total')})"
            )
    else:
        print("  lock-on: n/a (not a two-line log)")
    print(f"  classes {m['classes']}")
    print(f"  reasons {m['reasons']}")
    print(f"  carry guard: rows={guard['rows']} clean_slip_max>50mm={guard['over_50']} "
          f"max={guard['max']} force_min==0.00={guard['zero_force']}")
    return m


def accel(pairs: list[tuple[str, str, str]]) -> int:
    """E1-E4 per seed. `pairs` = [(seed, control, treatment)]."""
    print("P85 acceleration - the P44 speed union on the shipped two-line")
    print("=" * 78)
    ok = True
    for seed, control, treatment in pairs:
        c, u = p80lib.metrics(control), p80lib.metrics(treatment)
        pc = (c.get("stats") or {}).get("per_attempt")
        pu = (u.get("stats") or {}).get("per_attempt")
        delta = None if pc is None or pu is None else pu - pc
        cg, ug = carry_guard(control), carry_guard(treatment)
        new_reasons = {k: v for k, v in u["reasons"].items() if k not in c["reasons"]}
        window_delta = None
        if c["window_rate"] and u["window_rate"]:
            window_delta = 100.0 * (u["window_rate"] - c["window_rate"]) / c["window_rate"]
        e1 = delta is not None and delta <= -0.80
        e2 = (u["placed"] >= c["placed"] - 1) and (window_delta is None or window_delta >= -5.0)
        e3 = not new_reasons and ug["over_50"] <= cg["over_50"] and ug["zero_force"] <= cg["zero_force"]
        print(
            f"\nseed {seed}:  C {c['placed']}/{c['attempts']} @ {p80lib.fmt(pc)} s/attempt, "
            f"interval {p80lib.fmt(c['pooled']['mean'])}, window {p80lib.fmt(c['window_rate'])}"
            f"\n            U {u['placed']}/{u['attempts']} @ {p80lib.fmt(pu)} s/attempt, "
            f"interval {p80lib.fmt(u['pooled']['mean'])}, window {p80lib.fmt(u['window_rate'])}"
            f"\n            d s/attempt {p80lib.fmt(delta)}   d window {p80lib.fmt(window_delta, 1)} %"
            f"   new reasons {new_reasons or 'none'}"
            f"\n            slip>50 mm {cg['over_50']} -> {ug['over_50']}   "
            f"force_min==0 {cg['zero_force']} -> {ug['zero_force']}"
        )
        print(f"            E1 {'PASS' if e1 else 'FAIL'}  E2 {'PASS' if e2 else 'FAIL'}  "
              f"E3 {'PASS' if e3 else 'FAIL'}")
        ok = ok and e1 and e2 and e3
    print("\nverdict:", "E1-E3 pass on every seed -> recommend the union as the next "
          "adoption candidate" if ok else "measured, NOT adopted (a registered endpoint failed)")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "--same":
        return show_same(args[1], args[2])
    if args[0] == "--same-with-diag":
        return show_same(args[1], args[2])
    if args[0] == "--cells":
        for path in args[1:]:
            cell(path)
        return 0
    if args[0] == "--accel":
        pairs = [
            ("5", "logs/p85/base20_s5.log", "logs/p85/speed20_s5.log"),
            ("6", "logs/p85/base20_s6.log", "logs/p85/speed20_s6.log"),
        ]
        return accel(pairs)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
