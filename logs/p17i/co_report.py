#!/usr/bin/env python3
"""P18-A co-report: the interval + the per-leg motion budgets for the Stage-P battery.

The Oracle Gate-2 item 3: the data was collected (CYCLE_REPORT/MOTION_REPORT on) but not
reported. Interval = the per-attempt cycle span (the sum of the `[cycle]` phase seconds);
per-leg motion = the descent `approach(cartesian)` |v|max per leg. Read-only.
"""
import re
import statistics as st

LOGS = {
    "s11 control": "logs/p12a2/10_seed11_mass.log",
    "s11 gate": "logs/p17i/50_seed11_slide.log",
    "s5 control": "logs/p12a2/11_seed5_mass.log",
    "s5 gate": "logs/p17i/52_seed5_slide.log",
    "s23 control": "logs/p12a2/12_seed23_mass.log",
    "s23 gate": "logs/p17i/54_seed23_slide.log",
}
CYCLE = re.compile(r"\[cycle\] attempt \d+: (.+)$")
PHASE = re.compile(r"([a-z]+)=([0-9.]+)s")
VMAX = re.compile(r"approach\(cartesian\): [0-9.]+ cm, \d+ samples: .*\|v\|max=([0-9.]+) m/s")


def read(path):
    spans, vmax = [], []
    for line in open(path, errors="replace"):
        m = CYCLE.search(line)
        if m:
            vals = [float(v) for _, v in PHASE.findall(m.group(1))]
            if vals:
                spans.append(sum(vals))
        m = VMAX.search(line)
        if m:
            vmax.append(float(m.group(1)))
    return spans, vmax


print("| log | attempts | span med s | span max s | descent legs | |v|max med | |v|max max | >0.161 |")
print("| --- | --- | --- | --- | --- | --- | --- | --- |")
for name, path in LOGS.items():
    spans, vmax = read(path)
    over = sum(1 for v in vmax if v > 0.161)
    print(
        f"| {name} | {len(spans)} | {st.median(spans):.2f} | {max(spans):.2f} | "
        f"{len(vmax)} | {st.median(vmax):.3f} | {max(vmax):.3f} | {over} |"
    )
