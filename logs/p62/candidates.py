"""P62 phase 1 - the left grasp-attitude candidates, computed exactly (no simulator).

Reads `configs/waypoints_oriented.json` (`grasp_quaternion['left']`, [w, x, y, z] -
`tasks.py::_grasp_quat` feeds it to `ArmController.hold_quaternion`, and
`control.py::quaternion_error` documents the same order) and reports, per
candidate attitude:

* the quaternion (normalised, the file's [w, x, y, z] order),
* the TCP frame's three axes (the rotation matrix's columns) in the world,
* the **z column's world-belt projection** (the belt runs toward -y:
  `fruits.py:1429` sets the conveyor's surface velocity to `[0, belt_speed, 0]`
  with a negative `belt_speed`),
* the predicted share of P61's observed slip along the new z column.

Three rotation families are compared; only one changes the projection:

  F1 rotation about **world z** (the brief's "yaw") - changes it;
  F2 rotation about the frame's **z column** (the brief's "roll") - cannot
     change it (a rotation about an axis leaves that axis fixed);
  F3 rotation about **world y** (the belt axis) - cannot change it either.

Exactness: F1 preserves the z-component of **every** column, so the attitude's
relation to the vertical (the finger axis, the pads' droop) is invariant under it
- which is why the yaw family cannot break the top-down approach by construction.
What it does move is the *azimuth* of the frame's two horizontal axes: the
jaw-opening axis (column 1) and the z column.

No `src/`/`configs/` edit: this writes `logs/p62/candidates.json` for the IK probe
and prints the table that `CANDIDATES.md` carries.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.motion import mirror_across_xz, top_down_quaternion  # pure numpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CONFIG = os.path.join(ROOT, "configs", "waypoints_oriented.json")

#: The belt's travel direction: the conveyor's surface velocity is
#: `[0, cfg.belt_speed, 0]` with `belt_speed < 0` (`fruits.py:1429`), so the
#: fruit moves toward -y.
BELT = np.array([0.0, -1.0, 0.0])

#: P61's measured mean **world unit** slip direction (left, n = 14 in-hand
#: slides; `logs/p61/P2_RESULTS.md` section 3.1).
SLIP_WORLD = np.array([0.623, -0.658, -0.422])


# --------------------------------------------------------------------------- #
# quaternion / rotation helpers, [w, x, y, z] throughout
# --------------------------------------------------------------------------- #
def quat_mul(a, b):
    aw, ax, ay, az = (float(v) for v in a)
    bw, bx, by, bz = (float(v) for v in b)
    return np.array(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ]
    )


def quat_matrix(q):
    q = np.asarray(q, dtype=float)
    q = q / np.linalg.norm(q)
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def matrix_quat(m):
    t = float(np.trace(m))
    if t > 0.0:
        s = np.sqrt(t + 1.0) * 2.0
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    q = np.asarray(q, dtype=float)
    # Canonical sign: largest-magnitude component positive, so a quaternion is
    # printed once and not twice as +/-q.
    if q[int(np.argmax(np.abs(q)))] < 0.0:
        q = -q
    return q / np.linalg.norm(q)


def axis_quat(axis, angle):
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    half = 0.5 * float(angle)
    return np.concatenate([[np.cos(half)], np.sin(half) * axis])


def angle_between(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    c = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def describe(name, label, q, deg=True):
    q = np.asarray(q, dtype=float)
    q = q / np.linalg.norm(q)
    m = quat_matrix(q)
    cols = [m[:, i] for i in range(3)]
    tool = cols[2]
    proj = float(tool @ BELT)
    slip_share = float(SLIP_WORLD @ tool)
    jaw = cols[1]
    up = cols[0]
    # The pure-drag reference triple of P61 (a belt-only displacement in this
    # frame), and the one the candidate would give.
    drag_triple = tuple(float(c @ BELT) for c in cols)
    return {
        "name": name,
        "label": label,
        "quat": [float(v) for v in q],
        "axes": {
            "col0_up": [float(v) for v in up],
            "col1_jaw": [float(v) for v in jaw],
            "col2_tool": [float(v) for v in tool],
        },
        "tool_axis": [float(v) for v in tool],
        "belt_projection": proj,
        "belt_projection_abs": abs(proj),
        "slip_share_col2": slip_share,
        "drag_triple": [float(v) for v in drag_triple],
        "jaw_axis_belt_dot": float(abs(jaw @ BELT)),
        "jaw_axis_off_belt_deg": float(np.degrees(np.arccos(np.clip(abs(jaw @ BELT), 0, 1)))),
        "col0_vertical_dot": float(up @ np.array([0.0, 0.0, 1.0])),
        "col0_off_vertical_deg": float(
            np.degrees(np.arccos(np.clip(abs(up @ np.array([0.0, 0.0, 1.0])), 0, 1)))
        ),
        "col2_z": float(tool[2]),
        "col1_z": float(jaw[2]),
    }


def main() -> int:
    with open(CONFIG, encoding="utf-8") as handle:
        cfg = json.load(handle)
    q_left = np.asarray(cfg["grasp_quaternion"]["left"], dtype=float)
    q_right = np.asarray(cfg["grasp_quaternion"]["right"], dtype=float)
    q_left = q_left / np.linalg.norm(q_left)
    q_right = q_right / np.linalg.norm(q_right)

    rows = []
    shipped = describe("C0", "shipped left (control)", q_left)
    shipped["family"] = "(control)"
    shipped["dtheta_deg"] = 0.0
    rows.append(shipped)
    right = describe("R", "shipped right (reference)", q_right)

    # ---- F1: rotation about world z ------------------------------------- #
    def proj_after_yaw(theta: float) -> float:
        return float(quat_matrix(quat_mul(axis_quat((0, 0, 1), theta), q_left))[:, 2] @ BELT)

    # proj(theta) = -(t_x sin + t_y cos); bracket the two roots the brief names.
    t = quat_matrix(q_left)[:, 2]
    theta0 = float(np.arctan2(-t[1], t[0]))  # proj == 0
    theta_mirror = 2.0 * theta0  # proj == -proj(shipped)
    # Newton polish so the printed angle is the exact root of the printed proj.
    for _ in range(8):
        h = 1e-6
        f = proj_after_yaw(theta0)
        df = (proj_after_yaw(theta0 + h) - proj_after_yaw(theta0 - h)) / (2 * h)
        theta0 -= f / df
    theta_mirror = 2.0 * theta0

    yaw_specs = [
        ("Y15", "half of the null", 0.5 * theta0),
        ("Y21", "0.7 of the null (the measured feasibility frontier)", 0.7 * theta0),
        ("Y31", "proj == 0", theta0),
        ("Y46", "half of the mirror", 1.5 * theta0),
        ("Y62", "proj == -shipped (the right's regime)", theta_mirror),
    ]
    for name, label, theta in yaw_specs:
        q = quat_mul(axis_quat((0, 0, 1), theta), q_left)
        d = describe(name, f"yaw {np.degrees(theta):+.2f} deg about world z ({label})", q)
        d["dtheta_deg"] = float(np.degrees(theta))
        d["family"] = "F1 world-z yaw"
        rows.append(d)

    # ---- T0: the reach harness's own top-down attitude ------------------- #
    # `scripts/174_station_reach.py` / `183_reach_intercept.py` solve with this
    # attitude (fingers straight down, jaws across the belt), and their published
    # maps are the only measured evidence that the *left* holds a second attitude
    # at this station. Its z column is (0, 0, -1): the belt projection is 0 by
    # construction, independently of the yaw family.
    q_t0 = mirror_across_xz(top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x")))
    d = describe("T0", "the reach harness's top-down (fingers down, jaws across)", q_t0)
    d["dtheta_deg"] = 0.0
    d["family"] = "T0 harness top-down"
    rows.append(d)

    # ---- F2: rotation about the frame's z column ------------------------ #
    for phi in (45.0, 90.0):
        q = quat_mul(q_left, axis_quat((0, 0, 1), np.radians(phi)))
        d = describe(name=f"Z{int(phi)}", label=f"roll {phi:+.0f} deg about the z column", q=q)
        d["dtheta_deg"] = 0.0
        d["family"] = "F2 z-column roll"
        rows.append(d)
    # ---- F2b: roll about the *jaw* axis (column 1) ---------------------- #
    q = quat_mul(q_left, axis_quat((0, 1, 0), np.radians(45.0)))
    d = describe("J45", "roll +45 deg about the jaw axis (column 1)", q=q)
    d["dtheta_deg"] = 0.0
    d["family"] = "F2b jaw-axis roll"
    rows.append(d)
    # ---- F3: rotation about world y (the belt axis) --------------------- #
    q = quat_mul(axis_quat((0, 1, 0), np.radians(15.0)), q_left)
    d = describe("F3", "rotation +15 deg about world y (the belt axis)", q=q)
    d["dtheta_deg"] = 0.0
    d["family"] = "F3 world-y"
    rows.append(d)

    # ---- the exact invariants the families claim ------------------------ #
    invariants = {
        "shipped_tool_belt_projection": shipped["belt_projection"],
        "shipped_slip_share_col2": shipped["slip_share_col2"],
        "yaw_preserves_all_column_z": all(
            abs(abs(r["col2_z"]) - abs(shipped["col2_z"])) < 1e-12
            and abs(abs(r["col1_z"]) - abs(shipped["col1_z"])) < 1e-12
            and abs(abs(r["col0_vertical_dot"]) - abs(shipped["col0_vertical_dot"])) < 1e-12
            for r in rows
            if str(r.get("family", "")).startswith("F1")
        ),
        "z_column_roll_projection_delta": [
            r["belt_projection"] - shipped["belt_projection"]
            for r in rows
            if str(r.get("family", "")).startswith("F2 ")
        ],
        "world_y_projection_delta": [
            r["belt_projection"] - shipped["belt_projection"]
            for r in rows
            if str(r.get("family", "")).startswith("F3")
        ],
        "theta_null_deg": float(np.degrees(theta0)),
        "theta_mirror_deg": float(np.degrees(theta_mirror)),
        "theta_mirror_projection": proj_after_yaw(theta_mirror),
        "y62_vs_right_col2_deg": angle_between(
            quat_matrix(quat_mul(axis_quat((0, 0, 1), theta_mirror), q_left))[:, 2],
            quat_matrix(q_right)[:, 2],
        ),
        "y62_vs_right_col1_deg": angle_between(
            quat_matrix(quat_mul(axis_quat((0, 0, 1), theta_mirror), q_left))[:, 1],
            quat_matrix(q_right)[:, 1],
        ),
    }

    out = {"rows": rows, "right": right, "invariants": invariants}
    with open(os.path.join(HERE, "candidates.json"), "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1)

    print("[p62] shipped left quaternion [w,x,y,z]:")
    print("      " + ", ".join(f"{v:+.6f}" for v in q_left))
    print(f"[p62] theta_null = {np.degrees(theta0):.4f} deg, "
          f"theta_mirror = {np.degrees(theta_mirror):.4f} deg "
          f"(proj there = {proj_after_yaw(theta_mirror):+.6f})")
    print("[p62] world-y rotation vs the shipped belt axis: "
          f"belt = {BELT.tolist()}")
    header = (
        f"{'cand':5s} {'family':16s} {'dtheta':>8s} "
        f"{'quat (w,x,y,z)':52s} {'tool axis (z col)':28s} {'proj':>7s} "
        f"{'slip.sh':>7s} {'jaw-vs-belt':>11s} {'up-vs-vert':>10s}"
    )
    print("[p62] " + header)
    for r in rows:
        q = r["quat"]
        ax = r["tool_axis"]
        print(
            f"[p62] {r['name']:5s} {r['family']:16s} {r['dtheta_deg']:+8.2f} "
            f"{q[0]:+.6f},{q[1]:+.6f},{q[2]:+.6f},{q[3]:+.6f}   "
            f"{ax[0]:+.4f},{ax[1]:+.4f},{ax[2]:+.4f}   "
            f"{r['belt_projection']:+7.4f} {r['slip_share_col2']:+7.4f} "
            f"{r['jaw_axis_off_belt_deg']:10.1f}D {r['col0_off_vertical_deg']:9.1f}D"
        )
    print("[p62] --- families ---")
    by_name = {r["name"]: r for r in rows}
    print(f"[p62] F1 yaw about world z: proj {shipped['belt_projection']:+.4f} -> "
          f"{by_name['Y15']['belt_projection']:+.4f} (Y15) -> "
          f"{by_name['Y31']['belt_projection']:+.4f} (Y31) -> "
          f"{by_name['Y62']['belt_projection']:+.4f} (Y62); every column's z-component "
          f"invariant: {invariants['yaw_preserves_all_column_z']}")
    print("[p62] F2 roll about the z column: proj deltas "
          f"{['%+.2e' % v for v in invariants['z_column_roll_projection_delta']]} "
          "(zero by construction: a rotation about an axis fixes that axis), "
          "but the up column tilts "
          f"{shipped['col0_off_vertical_deg']:.1f} -> "
          f"{[round(r['col0_off_vertical_deg'],1) for r in rows if r['family'].startswith('F2 ')]} deg "
          "off vertical")
    print(f"[p62] F3 world-y: proj deltas "
          f"{['%+.2e' % v for v in invariants['world_y_projection_delta']]} (zero)")
    print(f"[p62] Y62's z column vs the right's: {invariants['y62_vs_right_col2_deg']:.2f} deg; "
          f"jaw axis vs the right's: {invariants['y62_vs_right_col1_deg']:.2f} deg")
    print(f"[p62] control check: shipped slip share on col2 = "
          f"{shipped['slip_share_col2']:.4f} (P61 published 0.905)")
    print("[p62] wrote candidates.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
