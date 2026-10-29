#!/usr/bin/env python3
"""P64 phase 1: derive the left `grasp_lift` achieved-attitude drift from the
measured corpus, and the pre-compensated command `q_cmd = q_drift^-1 x q_T0`.

Reads only the logs (no simulator, no pxr):
  * `logs/p63/p2/A1_77.log`  - P63 phase 2 addendum A1, `[attitude]` rows (3 left legs)
  * `logs/p62/p2/P0{A,B}.log`, `P0b{A,B}.log` - P62's two arm pairs (1 left leg each)
and, for the angle cross-check, the `[carry] ... hold_drift=` rows of the same runs.

Convention: `[w, x, y, z]`, Hamilton product, so `R(q1 (x) q2) = R(q1) R(q2)`.
The tool axis is the TCP frame's column 2 (`motion.top_down_quaternion`'s
convention), `(0, 0, -1)` at the commanded T0. `q_drift` is the **minimal**
rotation taking the commanded axis to the achieved one (the brief's definition:
axis = (0,0,-1) x t, angle = acos(-t_z)) - roll about the tool axis is not
observable from the axis and does not move the axis or its belt projection.
"""
from __future__ import annotations

import glob
import math
import os
import re

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

T0_LEFT = np.array([0.0, -0.7071067811865475, 0.7071067811865476, 0.0])
T0_RIGHT = np.array([0.0, 0.7071067811865475, 0.7071067811865476, 0.0])
BELT = np.array([0.0, -1.0, 0.0])          # world direction the belt travels


def qmul(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    w1, v1 = a[0], a[1:]
    w2, v2 = b[0], b[1:]
    return np.array([w1 * w2 - float(v1 @ v2), *(w1 * v2 + w2 * v1 + np.cross(v1, v2))])


def qconj(q):
    q = np.asarray(q, dtype=float)
    return np.array([q[0], -q[1], -q[2], -q[3]])


def qnorm(q):
    q = np.asarray(q, dtype=float)
    return q / float(np.linalg.norm(q))


def qrot(q):
    w, x, y, z = qnorm(q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def qaxis(axis, deg):
    axis = np.asarray(axis, dtype=float)
    axis = axis / float(np.linalg.norm(axis))
    h = math.radians(deg) / 2.0
    return np.array([math.cos(h), *(math.sin(h) * axis)])


def tool_axis(q):
    return qrot(q)[:, 2]


def belt_proj(q):
    return float(tool_axis(q) @ BELT)


ATT = re.compile(
    r"\[attitude\] (?P<side>left|right) (?P<leg>\w+): tilt=(?P<tilt>[-\d.]+)deg .*?"
    r"tool_axis=\((?P<x>[+-][\d.]+),(?P<y>[+-][\d.]+),(?P<z>[+-][\d.]+)\)"
)
CARRY = re.compile(
    r"\[carry\] (?P<side>left|right) (?P<leg>\w+): .*?hold_drift=(?P<drift>[-\d.]+)deg"
)


def parse(path):
    att, carry = [], []
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            m = ATT.search(line)
            if m:
                att.append(
                    (
                        m.group("side"),
                        m.group("leg"),
                        np.array([float(m.group("x")), float(m.group("y")), float(m.group("z"))]),
                        float(m.group("tilt")),
                    )
                )
                continue
            m = CARRY.search(line)
            if m:
                carry.append((m.group("side"), m.group("leg"), float(m.group("drift"))))
    return att, carry


def main() -> int:
    logs = [
        "logs/p63/p2/A1_77.log",
        "logs/p62/p2/P0_A.log",
        "logs/p62/p2/P0_B.log",
        "logs/p62/p2/P0b_A.log",
        "logs/p62/p2/P0b_B.log",
    ]
    rows = []
    print("P64 phase 1 - derived drift of the left `grasp_lift` achieved attitude")
    print("=" * 78)
    for rel in logs:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print(f"  MISSING {rel}")
            continue
        att, carry = parse(path)
        left_att = [a for a in att if a[0] == "left" and a[1] == "grasp_lift"]
        left_carry = [c for c in carry if c[0] == "left" and c[1] == "grasp_lift"]
        print(f"\n{rel}: {len(att)} [attitude] rows, {len(carry)} [carry] rows, "
              f"left grasp_lift: {len(left_att)} attitude / {len(left_carry)} carry")
        # pair by order: both are printed once per left grasp_lift leg, the
        # attitude row first (it is printed at the leg's end, before the row)
        for i, (_, _, t, tilt) in enumerate(left_att):
            drift = left_carry[i][2] if i < len(left_carry) else float("nan")
            ang = math.degrees(math.acos(max(-1.0, min(1.0, -float(t[2])))))
            axis = np.array([t[1], -t[0], 0.0])
            axis = axis / float(np.linalg.norm(axis))
            qd = qaxis(axis, ang)
            proj = float(t @ BELT)
            rows.append((rel, t, tilt, ang, axis, drift, proj, qd))
            print(
                f"  leg {i}: tilt={tilt:5.1f}deg (acos(-tz)={ang:5.1f}) tool=("
                f"{t[0]:+.4f},{t[1]:+.4f},{t[2]:+.4f}) belt_proj={proj:+.4f} "
                f"drift_row={drift:5.1f}deg | q_drift axis=({axis[0]:+.4f},"
                f"{axis[1]:+.4f},{axis[2]:+.4f})"
            )
    # right legs, for the report's contrast
    print("\nright `grasp_lift` (contrast only, not used for the left constant):")
    for rel in logs:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        att, _ = parse(path)
        for side, leg, t, tilt in att:
            if side == "right" and leg == "grasp_lift":
                print(f"  {rel}: tilt={tilt:5.1f} tool=({t[0]:+.4f},{t[1]:+.4f},{t[2]:+.4f}) "
                      f"belt_proj={float(t @ BELT):+.4f}")

    A = np.array([r[1] for r in rows])
    angles = np.array([r[3] for r in rows])
    med = np.median(A, axis=0)
    med = med / float(np.linalg.norm(med))
    med_ang = float(np.median(angles))
    axis = np.array([med[1], -med[0], 0.0])
    axis = axis / float(np.linalg.norm(axis))
    qd = qaxis(axis, med_ang)
    q_cmd = qnorm(qmul(qconj(qd), T0_LEFT))
    q_cmd_alt = qnorm(qmul(T0_LEFT, qconj(qd)))
    print("\n" + "-" * 78)
    print(f"n = {len(rows)} left grasp_lift legs (P63 A1 + P62 P0/P0b)")
    print(f"  achieved tool axis spread: tilt {angles.min():.1f}..{angles.max():.1f} deg "
          f"(median {med_ang:.2f}); belt_proj {min(r[6] for r in rows):+.4f}.."
          f"{max(r[6] for r in rows):+.4f}")
    print(f"  per-leg q_drift angle: " + ", ".join(f"{a:.1f}" for a in angles))
    print(f"  per-leg axis azimuth (deg from +y, belt-frame): "
          + ", ".join(f"{math.degrees(math.atan2(a[0], a[1])):+.1f}" for a in (r[4] for r in rows)))
    print(f"  median achieved tool axis t = ({med[0]:+.6f}, {med[1]:+.6f}, {med[2]:+.6f})")
    print(f"  q_drift: axis=({axis[0]:+.6f}, {axis[1]:+.6f}, {axis[2]:+.6f}) "
          f"angle={med_ang:.4f} deg")
    print(f"  q_drift[c] = {np.round(qd, 8).tolist()}")
    print(f"  q_cmd = q_drift^-1 (x) q_T0 = {np.round(q_cmd, 8).tolist()}")
    print(f"    cmd tool axis = {np.round(tool_axis(q_cmd), 6).tolist()} "
          f"belt_proj={belt_proj(q_cmd):+.4f}")
    print(f"    predicted achieved proj = +0.0000 (q_drift (x) q_cmd = q_T0 up to float)")
    pred = qmul(qd, q_cmd)
    print(f"    check q_drift (x) q_cmd = {np.round(pred, 8).tolist()} "
          f"(q_T0 up to sign: dot={abs(float(pred @ T0_LEFT)):.10f})")
    print(f"  NOTE alt composition q_T0 (x) q_drift^-1 = {np.round(q_cmd_alt, 8).tolist()} "
          f"(cmd proj {belt_proj(q_cmd_alt):+.4f}) - not the registered form")
    print(f"\n  T0_LEFT = {np.round(T0_LEFT, 8).tolist()}  (belt_proj {belt_proj(T0_LEFT):+.4f})")
    print(f"  T0_RIGHT = {np.round(T0_RIGHT, 8).tolist()} (belt_proj {belt_proj(T0_RIGHT):+.4f})")
    # A1-only robustness
    a1 = [r for r in rows if "A1_77" in r[0]]
    A1 = np.array([r[1] for r in a1])
    m1 = np.median(A1, axis=0)
    m1 = m1 / float(np.linalg.norm(m1))
    ang1 = float(np.median([r[3] for r in a1]))
    ax1 = np.array([m1[1], -m1[0], 0.0])
    ax1 = ax1 / float(np.linalg.norm(ax1))
    q1 = qnorm(qmul(qconj(qaxis(ax1, ang1)), T0_LEFT))
    print(f"  A1-only check (n={len(a1)}): axis=({ax1[0]:+.4f},{ax1[1]:+.4f},{ax1[2]:+.4f}) "
          f"angle={ang1:.2f} -> q_cmd={np.round(q1, 6).tolist()} "
          f"(cmd proj {belt_proj(q1):+.4f}, dot vs pooled "
          f"{abs(float(q1 @ q_cmd)):.6f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
