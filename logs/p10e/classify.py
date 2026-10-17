#!/usr/bin/env python3
"""P10-E mechanism classification over the no-grasp attempts (see NOGRASP_DIAGNOSIS.md).

Rules (all read off the paired rows; see census.py for the pairing):
  A  pre-close acquisition miss: catch-up residual > 20 mm, or no close row
     (the close never found sustained contact).
  C  carry-leg escape: contact present at the carry start (force@onset > 0 and
     contacts@onset >= 1) and the loss row > 10 (held for a while in the carry).
  B1 post-close probe/regrasp loss: the close found contact, the probe failed at
     least once (cycle grip phase >= 3.0 s), the fruit gone by the carry start.
  B2 post-close belt-break loss: the close found contact, the probe passed
     (grip phase <= 2.1 s), the fruit gone by the carry start.

Sub-tags: blowup (in-hand |v|max > 20 m/s or lowest payload point < -10 m);
          fell (lowest payload point <= -100 mm); stayed (>= -10 mm).
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")
from census import parse, pair_attempts

RUNS = [
    ("p10c/10_armA_diag", "A", 5),
    ("p10c/20_armB_1", "B", 5),
    ("p10c/50_seed11_A", "A", 11),
    ("p10c/51_seed11_B", "B", 11),
    ("p10c/52_seed23_A", "A", 23),
    ("p10c/53_seed23_B", "B", 23),
    ("p10c2/61_seed5_B_gate", "Bgate", 5),
    ("p10c2/62_seed11_B_gate", "Bgate", 11),
    ("p10c2/63_seed23_B_gate", "Bgate", 23),
    ("p10c3/70_flip_seed5", "flip", 5),
    ("p10c3/71_flip_seed11", "flip", 11),
    ("p10c3/72_flip_seed23", "flip", 23),
]
ROOT = "../"


def classify(rec):
    cu = rec.get("catchup", {}).get("res", 0.0)
    close = rec.get("close")
    grip_s = rec.get("cycle", {}).get("grip", 0.0)
    carry = rec.get("carry", {})
    try:
        f0 = float(carry.get("f_onset", "n/a"))
    except (TypeError, ValueError):
        f0 = -1.0
    try:
        c0 = int(carry.get("c_onset", "None"))
    except (TypeError, ValueError):
        c0 = -1
    try:
        loss = int(carry.get("loss", "None"))
    except (TypeError, ValueError):
        loss = -1
    if cu > 20.0 or close is None:
        return "A_pre_close_miss"
    if 0.0 < f0 <= 6.0 and c0 >= 1 and loss > 10:
        return "C_carry_leg_escape"
    if grip_s >= 3.0:
        return "B1_probe_cycle"
    return "B2_belt_break"


def main():
    print(f"{'run':26s} {'arm':5s} {'seed':4s} {'att':>3s} {'side':5s} {'species':10s} "
          f"{'class':18s} {'vmax':>8s} {'low':>7s} {'grip_s':>6s} {'F@o':>6s} {'sep@o':>6s} "
          f"{'loss':>4s} {'gap0':>6s} {'cu':>6s} {'sim':>5s} {'tag':6s}")
    counts = {}
    spans = {}
    tags = {}
    rows_out = []
    for rel, arm, seed in RUNS:
        lines, attempts, rows = parse(ROOT + rel + ".log")
        out = pair_attempts(attempts, rows)
        for num in sorted(out):
            r = out[num]
            if r.get("grasped"):
                continue
            cls = classify(r)
            carry = r.get("carry", {})
            vmax = float(carry.get("vmax", 0.0) or 0.0)
            try:
                low = int(r.get("clear", {}).get("lowest", 0))
            except (TypeError, ValueError):
                low = 0
            grip_s = r.get("cycle", {}).get("grip", 0.0)
            tag = "blowup" if (vmax > 20.0 or low < -10000) else (
                "fell" if low <= -100 else ("stayed" if low >= -10 else "sub-belt"))
            print(f"{rel:26s} {arm:5s} {seed:4d} a{num:02d} {r['side']:5s} "
                  f"{r['species']:10s} {cls:18s} {vmax:8.3f} {low:7d} {grip_s:6.2f} "
                  f"{carry.get('f_onset', '?'):>6s} {carry.get('sep_onset', '?'):>6s} "
                  f"{carry.get('loss', '?'):>4s} {carry.get('gap_start', '?'):>6s} "
                  f"{r.get('catchup', {}).get('res', 0.0):6.1f} {r.get('sim', 0.0):5.1f} {tag:6s}")
            counts[cls] = counts.get(cls, 0) + 1
            spans[cls] = spans.get(cls, 0.0) + r.get("sim", 0.0)
            tags[tag] = tags.get(tag, 0) + 1
            rows_out.append((rel, arm, seed, num, cls, tag))
    tot_n = sum(counts.values())
    tot_s = sum(spans.values())
    print()
    for k in sorted(counts):
        print(f"{k:20s} n={counts[k]:3d} ({100.0*counts[k]/tot_n:4.1f}%) "
              f"span={spans[k]:7.1f} attempt-s ({100.0*spans[k]/tot_s:4.1f}%)")
    print(f"{'TOTAL':20s} n={tot_n:3d} span={tot_s:7.1f} attempt-s")
    print("tags:", tags)


if __name__ == "__main__":
    main()
