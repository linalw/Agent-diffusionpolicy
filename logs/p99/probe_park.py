"""P99 step 1: calibrate the per-slot remainder against a park-traced record.

`logs/p84/D5.log` is the pre-P87 two-line cell (the shipped-shaped slot loop)
with `FRUIT_BIARM_PARK_TRACE=1`. It replays `logs/p80/T20.log` 865/865 with the
trace rows dropped, so the trace is line-neutral there. This probe joins the
three park rows to the slot timeline and answers: is
`acq_(N+1) - acq_N - span_N` == park_wait + park_motion + feed + polls?
"""
import re
import sys

import probe_timeline as T

PARK = re.compile(
    r"\[biarm\] (\w+): park (wait start|moving|done) t=([0-9.]+)s"
    r"(?: \(waited (\d+) ticks\))?"
)


def parks(path):
    rows = []
    for line in open(path, errors="replace"):
        m = PARK.search(line)
        if m:
            rows.append(
                (m.group(1), m.group(2), float(m.group(3)),
                 int(m.group(4)) if m.group(4) else None)
            )
    return rows


def main(path):
    slots, cycles, results = T.parse(path)
    pr = parks(path)
    print(f"== {path}: park rows={len(pr)}")
    for arm in ("left", "right"):
        ev = [r for r in pr if r[0] == arm]
        waits = [r for r in ev if r[1] == "wait start"]
        movings = [r for r in ev if r[1] == "moving"]
        dones = [r for r in ev if r[1] == "done"]
        print(f"   {arm}: parks started={len(waits)} moved={len(movings)} "
              f"done={len(dones)}")
        for w, m, d in zip(waits, movings, dones):
            print(f"     t={w[2]:7.2f} wait={m[2] - w[2]:5.2f}s "
                  f"move={d[2] - m[2]:5.2f}s  (waited {m[3]} ticks)")
    # the slot timeline of the same arm
    for arm in ("left", "right"):
        ev = [r for r in pr if r[0] == arm and r[1] == "wait start"]
        att = [s for s in slots[arm] if not s["starved"]]
        print(f"   {arm} slot joins:")
        for i, (a, b) in enumerate(zip(att, att[1:])):
            gap = b["t_acq"] - a["t_acq"] - (a["span"] or 0)
            # the park that follows attempt i
            after = [e[2] for e in ev if abs(e[2] - (a["t_acq"] + (a["span"] or 0))) < 6]
            polls = [s for s in slots[arm] if s["t_acq"] > a["t_acq"] and s["t_acq"] < b["t_acq"] and s["starved"]]
            print(f"     slot {i}: acq={a['t_acq']:7.2f} span={a['span']:5.2f} "
                  f"-> next acq={b['t_acq']:7.2f} gap={gap:5.2f} "
                  f"park_at={after} polls={len(polls)}")
    return 0


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
