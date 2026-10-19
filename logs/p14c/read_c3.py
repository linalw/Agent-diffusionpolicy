#!/usr/bin/env python3
"""P14-C.3 read: the ablation attribution on the direct interface (seed 77).

Inputs: the P13 A/B records (logs/p13/B_ab/{A,B}_1.log) + the C.2 ablation runs
(logs/p14c/B_ab/{A1,A2,A3}_1.log). Endpoints per the P13 readout: the left
close-start |y| (median/p90), the 200-tick catch-up chases, the per-episode
classes (no-contact / carried-not-placed), and the rollout success.

Read-only; prints one table. Usage: python3 logs/p14c/read_c3.py
"""
import os
import re
import statistics as st

LOGS = {
    "A  moe_v13s (ctrl)": "logs/p13/B_ab/A_1.log",
    "B  ev1 (full)": "logs/p13/B_ab/B_1.log",
    "A1 heads+aux": "logs/p14c/B_ab/A1_1.log",
    "A2 loss-only": "logs/p14c/B_ab/A2_1.log",
    "A3 6ep-only": "logs/p14c/B_ab/A3_1.log",
}

ACQ = re.compile(
    r"\[acq\] (left|right) idx=(\d+): setup\[premove=([0-9.]+) axis=([0-9.]+) "
    r"hover=([0-9.]+) wait=([0-9.]+) catchup=([0-9.]+)\]s catchup=(\d+)t "
    r"res=([0-9.]+)mm .*?close_start=\(([-+0-9.]+),([-+0-9.]+),([-+0-9.]+)\)mm"
)
EP = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=[0-9.]+cm .*?arm=(\w+) success=(\w+) "
    r"grasped=(\w+) placed=(\w+) ticks=(\d+)"
)


def pct(vals, q):
    if not vals:
        return float("nan")
    s = sorted(vals)
    i = min(len(s) - 1, int(round(q * (len(s) - 1))))
    return s[i]


def read(path):
    left, right = [], []
    eps = []
    success = None
    if not os.path.exists(path):
        return None
    for line in open(path, errors="replace"):
        m = ACQ.search(line)
        if m:
            arm = m.group(1)
            dy = abs(float(m.group(11)))
            catchup = int(m.group(8))
            row = (dy, catchup, float(m.group(3)), float(m.group(6)))
            (left if arm == "left" else right).append(row)
        m = EP.search(line)
        if m:
            eps.append(
                dict(
                    ep=int(m.group(1)),
                    fruit=m.group(2),
                    arm=m.group(3),
                    ok=m.group(4) == "True",
                    grasped=m.group(5) == "True",
                    placed=m.group(6) == "True",
                    ticks=int(m.group(7)),
                )
            )
        m = re.search(r"rollout success (\d+)/(\d+)", line)
        if m:
            success = (int(m.group(1)), int(m.group(2)))
    return dict(left=left, right=right, eps=eps, success=success)


def summarize(arm_rows):
    dy = [r[0] for r in arm_rows]
    ch = [r[1] for r in arm_rows]
    return dict(
        n=len(dy),
        dy_med=st.median(dy) if dy else float("nan"),
        dy_p90=pct(dy, 0.9),
        dy_max=max(dy) if dy else float("nan"),
        chases=sum(1 for c in ch if c >= 195),
        catchup_p50=st.median(ch) if ch else float("nan"),
    )


def main():
    hdr = (
        f"{'run':<20} {'succ':>6} | {'L n':>4} {'L |y| med':>9} {'p90':>7} "
        f"{'max':>7} {'chase':>5} | {'R |y| med':>9} {'R chase':>7} | "
        f"{'nc(L/R)':>8} {'carried':>7} {'ticks_med':>9}"
    )
    print(hdr)
    print("-" * len(hdr))
    for name, path in LOGS.items():
        d = read(path)
        if d is None:
            print(f"{name:<20} {'(missing)':>6}")
            continue
        L, R = summarize(d["left"]), summarize(d["right"])
        eps = d["eps"]
        nc = sum(1 for e in eps if not e["grasped"])
        carried = sum(1 for e in eps if e["grasped"] and not e["placed"])
        ticks = [e["ticks"] for e in eps if e["ok"]]
        succ = d["success"]
        s = f"{succ[0]}/{succ[1]}" if succ else "?"
        print(
            f"{name:<20} {s:>6} | {L['n']:>4} {L['dy_med']:>9.1f} {L['dy_p90']:>7.1f} "
            f"{L['dy_max']:>7.1f} {L['chases']:>5} | {R['dy_med']:>9.1f} "
            f"{R['chases']:>7} | {nc:>8} {carried:>7} "
            f"{(st.median(ticks) if ticks else float('nan')):>9.0f}"
        )
    print()
    print("notes:")
    print("  L/R |y| med  = the close-start |y| median (the acquisition error endpoint)")
    print("  chase        = catch-up runs at the 195-200-tick cap (the 200-tick chases)")
    print("  nc(L/R)      = episodes with grasped=False (the no-contact class)")
    print("  carried      = grasped but not placed (the carried-not-placed class)")
    print("  ticks_med    = median ticks among successes")


if __name__ == "__main__":
    main()
