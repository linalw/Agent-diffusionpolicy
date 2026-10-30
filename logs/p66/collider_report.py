"""P66 phase 1b report - S vs F1 on the authored finger-tip collider prims.

    python3 logs/p66/collider_report.py            # -> logs/p66/collider_report.txt
    python3 logs/p66/collider_report.py --check

Reads `collider_read_0.json` (arm S: `FRUIT_FINGER_TIP_DELTA=0`, an AABB of the
shipped mesh) and `collider_read_m0p004.json` (arm F1: `-4 mm`), prints the two
boxes' dimensions, the tilt `theta` of the box's long axis from the vertical, and
checks the register's arithmetic:

    long(S) - long(F1)                == 4.000 mm           (the box's own axis)
    span_z(S) - span_z(F1)            == 4*cos(theta)       (the vertical read)

`4*cos(theta)` is the *vertical* projection of the 4 mm distal-plane shift: the
shift is along the plate's long axis, so it moves the distal plane's height by
`4*cos(theta)` and its along-belt position by `4*sin(theta)`.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINKS = (
    "openarm_left_left_finger",
    "openarm_left_right_finger",
    "openarm_right_left_finger",
    "openarm_right_right_finger",
)


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    check_only = "--check" in sys.argv
    s = load("collider_read_0.json")
    f1 = load("collider_read_m0p004.json")
    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)
        if not check_only:
            print(text)

    out("P66 phase 1b - the static read of the authored finger-tip collider prims")
    out(f"S  : FRUIT_FINGER_TIP_DELTA={s['finger_tip_delta_env']!r}  "
        f"parts={s['parts']}  physics_started={s['physics_started']}")
    out(f"F1 : FRUIT_FINGER_TIP_DELTA={f1['finger_tip_delta_env']!r}  "
        f"parts={f1['parts']}  physics_started={f1['physics_started']}")
    out()
    out("link                          face    mid     long  | theta(deg)  span_z  | d_long  d_span_z  4cos(theta)")
    out("-" * 116)

    checks = []
    deltas = []
    for link in LINKS:
        a = s["boxes"][link]
        b = f1["boxes"][link]
        d_long = a["dims_own_mm"][2] - b["dims_own_mm"][2]
        d_span = a["vertical_span_mm"] - b["vertical_span_mm"]
        d_extent = a["z_extent_mm"] - b["z_extent_mm"]
        theta = a["theta_from_vertical_deg"]
        expect = 4.0 * float(__import__("math").cos(__import__("math").radians(theta)))
        deltas.append((d_long, d_span, d_extent, theta, expect))
        out(
            f"{link:28s} {a['dims_own_mm'][0]:6.2f} {a['dims_own_mm'][1]:6.2f} "
            f"{a['dims_own_mm'][2]:7.2f}  |"
            f"   {theta:7.3f}  {a['vertical_span_mm']:7.3f}  |"
            f" {d_long:6.3f}  {d_span:8.3f}   {expect:8.3f}"
        )
        checks.append((f"{link}: the two boxes differ only in the long axis", (
            abs(a["dims_own_mm"][0] - b["dims_own_mm"][0]) < 0.01
            and abs(a["dims_own_mm"][1] - b["dims_own_mm"][1]) < 0.01
        )))
        checks.append((f"{link}: long(S)-long(F1) == 4.000 mm", abs(d_long - 4.0) <= 0.002))
        checks.append((f"{link}: span_z(S)-span_z(F1) == 4*cos(theta)", abs(d_span - expect) <= 0.002))
        checks.append((f"{link}: the AABB z extent tracks the span", abs(d_extent - d_span) <= 0.002))
        checks.append((f"{link}: the proximal plane does not move",
                       abs(a["proximal_world_z_mm"] - b["proximal_world_z_mm"]) <= 0.002))
        checks.append((f"{link}: exactly one collision prim enabled (the box)",
                       f1["collision_report"][link]["collision_prims_enabled"] == 1))
    out()

    long_s = s["boxes"][LINKS[0]]["dims_own_mm"][2]
    long_f = f1["boxes"][LINKS[0]]["dims_own_mm"][2]
    theta = s["boxes"][LINKS[0]]["theta_from_vertical_deg"]
    out(f"box (S )  33.261 x 61.000 x {long_s:.3f} mm   (face x mid x long)")
    out(f"box (F1)  33.261 x 61.000 x {long_f:.3f} mm")
    out(f"long dimension:  {long_s:.3f} - {long_f:.3f} = {long_s - long_f:.3f} mm")
    out(f"theta (long axis vs the vertical, this static pose) = {theta:.4f} deg")
    out(f"4*cos(theta) = {4.0 * __import__('math').cos(__import__('math').radians(theta)):.4f} mm")
    out(f"distal plane (world z): {s['boxes'][LINKS[0]]['distal_world_z_mm']:.3f} -> "
        f"{f1['boxes'][LINKS[0]]['distal_world_z_mm']:.3f} mm "
        f"(+{f1['boxes'][LINKS[0]]['distal_world_z_mm'] - s['boxes'][LINKS[0]]['distal_world_z_mm']:.3f})")
    out(f"proximal plane (world z): {s['boxes'][LINKS[0]]['proximal_world_z_mm']:.3f} -> "
        f"{f1['boxes'][LINKS[0]]['proximal_world_z_mm']:.3f} mm")
    out()
    out("the same identity at a tilt (arithmetic on P63's measured carry attitude):")
    for tilt in (0.0, 10.0, 24.6, 30.0):
        out(f"  theta = {tilt:5.1f} deg -> 4*cos(theta) = {4.0 * __import__('math').cos(__import__('math').radians(tilt)):.3f} mm "
            f"(along the belt 4*sin(theta) = {4.0 * abs(float(__import__('math').sin(__import__('math').radians(tilt)))):.3f} mm)")
    out()
    out("== structural checks ==")
    npass = sum(1 for _n, ok in checks if ok)
    for name, ok in checks:
        out(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    out(f"  {npass}/{len(checks)}")

    if not check_only:
        with open(os.path.join(HERE, "collider_report.txt"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        print("wrote logs/p66/collider_report.txt")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
