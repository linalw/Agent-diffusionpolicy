#!/usr/bin/env python3
"""K2 accounting for the P10-C monitor runs (MONITOR_DIAG runs only).

NOTE (advisory, 2026-10-17): the att/span columns are off by one attempt - the
`[monitor] attempt` row precedes its own `[cycle]` row, so pair with the FOLLOWING cycle
row. The clean_slip/fire/K2 columns are correct.

Pairs each `[monitor] attempt:` row with the nearest preceding `[carry]` row of the
fired leg (the same leg name from the fired=[...] list) and classifies the fire by the
frozen K2 rule: clean_slip_max <= 2.0 mm -> a clean-leg abort (K2); else an escape fire.

Usage: python3 logs/p10c/k2_report.py LOG [LOG...]
"""
import re
import sys


def k2_report(path):
    lines = open(path, errors="ignore").read().splitlines()
    fires = []  # (attempt_idx, side, leg, tick, clean_slip, span_s)
    cur_attempt = None
    pending_carry = []  # recent (side, leg, ticks, clean_slip)
    span = None
    for line in lines:
        if "[cycle] attempt" in line:
            m = re.search(r"attempt (\d+): .*total=([\d.]+)s", line)
            if m:
                cur_attempt = int(m.group(1))
                span = float(m.group(2))
        m = re.search(r"\[carry\] (\w+) (\w+): ticks=(\d+)/(\d+) clean_slip_max=([\d.]+)mm", line)
        if m:
            pending_carry.append((m.group(1), m.group(2), int(m.group(3)), float(m.group(5))))
            if len(pending_carry) > 6:
                pending_carry.pop(0)
        m = re.search(r"\[monitor\] attempt: legs=(\d+) fires=(\d+) skip=(\d+) fired=\[(.*?)\]", line)
        if m and int(m.group(2)) > 0:
            fired = m.group(4)
            for item in [x for x in fired.split(",") if x.strip() and x.strip() != "-"]:
                lm = re.match(r"(\w+)@(\d+)/(\d+)", item.strip())
                if not lm:
                    continue
                leg = lm.group(1)
                # nearest preceding carry row with this leg name
                cand = [c for c in pending_carry if c[1] == leg]
                if cand:
                    side, legname, ticks, cs = cand[-1]
                else:
                    side, legname, ticks, cs = ("?", leg, 0, float("nan"))
                fires.append((cur_attempt, side, leg, int(lm.group(2)), cs, span))
    k2 = [f for f in fires if f[4] <= 2.0]
    print(f"== {path}")
    print(f"   fires={len(fires)}  K2-aborts={len(k2)}")
    for f in fires:
        cls = "K2-ABORT" if f[4] <= 2.0 else "escape"
        print(f"   att {f[0]} {f[1]} {f[2]} fired@{f[3]} clean_slip={f[4]:.1f}mm span={f[5]}s -> {cls}")
    return len(fires), len(k2)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        k2_report(p)
