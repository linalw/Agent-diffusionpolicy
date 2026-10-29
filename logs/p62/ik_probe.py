"""P62 phase 1 - the left grasp-attitude IK/reach probe at the pick station.

    scripts/run.sh logs/p62/ik_probe.py

One claim, no control code. Builds the same scene `scripts/174_station_reach.py`
does, teleports the **left** arm to the calibrated `arms.left.grasp` seed (the
file's own seed, exactly like 174/183), pins `ArmController.hold_quaternion` to a
candidate attitude from `logs/p62/candidates.json` and solves the same position IK
the catch uses - jaw centre at `(x, pick_y, belt_top + 0.09)` - for x at the
left's delivered p50 / station / max (`logs/p60/LEFT_CENSUS.md`: selection-instant
x 0.274 m [0.188-0.398]).

Printed per (candidate, x):

* `res`  - the IK residual (jaw centre to target) [mm];
* `qerr` - the **achieved** attitude vs the commanded one [deg]: the orientation
  the differential IK did **not** deliver (it is a 6-DoF solve, but the wrist has
  only 7 joints and the arm's attitude error is what limits an azimuth change);
* `margin` - the smallest joint-limit margin of the solved configuration, and the
  binding joint;
* `pad`  - the fingertip pads' lowest world point above the belt top, from the
  live finger-link poses composed with `configs/finger_pads.json` (the same
  authored pad geometry `scene.py::_add_finger_pads` builds: a capsule of radius
  0.010 and total length `size[2]` along its local Z). This is the static
  belt-clearance read the descent's known 40-90 mm shortfall
  (`logs/161_accept_endmetric.log`: `end=` 42.1-88.1 mm) must not worsen;
* `finger_min` - the lower finger-link origin's height above the belt top.

The control (`C0`, the shipped quaternion) is the baseline for every comparison;
its jaw/pad geometry at the station also settles the **frame semantics** - which
TCP column is the finger long axis, which is the jaw-opening axis - which the
candidate table's "tool axis" label depends on.

Env: `FRUIT_P62_CANDIDATES` (comma list, default `C0,Y31,Y46,Y62`),
`FRUIT_P62_X` (default `0.274,0.34,0.398`), `FRUIT_P62_JSON` (raw rows).

P64 screen addition (default-off, additive - the P62 rows are unchanged): the
candidate list may name three **derived** attitudes that are not in
`candidates.json`:

* `QPREC`  - P64's pre-compensated command `q_drift^-1 (x) q_T0`
  (`logs/p64/P2_RESULTS.md`), the literal file value;
* `QDRIFT` - `q_drift (x) q_T0`, i.e. the command whose **own** attitude is the
  one the left actually achieves under `T0` (belt projection +0.351) - the
  reachable direction the Oracle named;
* `QFILE`  - `configs/waypoints_oriented.json`'s left `grasp_quaternion` (the
  shipped control's own file attitude, projection +0.513; sampled here as an
  independent re-solve, so `QFILE` must reproduce `C0` row for row).

Each row also carries the **jaw-opening axis' z** (`jaw_z`, the field the
`waypoints_oriented.json` note rejects: one pad above the other) and the
**achieved** belt projection, so a commanded attitude can be read against the
attitude the solve actually reaches.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.control import ArmController, quaternion_error
from fruit_sorting.scene import SortingScene

install_failure_handler("p62_ik_probe")

DT = 1.0 / 120.0
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

CANDIDATES = tuple(
    name.strip()
    for name in os.environ.get("FRUIT_P62_CANDIDATES", "C0,Y31,Y46,Y62").split(",")
    if name.strip()
)
XS = tuple(float(v) for v in os.environ.get("FRUIT_P62_X", "0.274,0.34,0.398").split(","))
Z_GRIP = float(os.environ.get("FRUIT_P62_Z", "0.09"))
TOL = float(os.environ.get("FRUIT_P62_TOL", "0.006"))
#: `solve_to` restarts: the catch's own fallback re-solves from random poses
#: (`tasks.py`: "the low grasp pose is near the edge of the workspace"), so a
#: candidate that only solves from the shipped seed has not been asked the
#: question the control path would ask it.
RESTARTS = int(os.environ.get("FRUIT_P62_RESTARTS", "1"))
PAD_RADIUS = float(os.environ.get("FRUIT_PAD_RADIUS", "0.010"))
JSON_OUT = os.environ.get("FRUIT_P62_JSON", os.path.join(HERE, "ik_probe_rows.json"))

#: The belt's travel direction (the conveyor's surface velocity is `[0, -, 0]`,
#: so the fruit moves toward -y); the frame columns are `col0`=up-ish,
#: `col1`=-jaw-opening, `col2`=approach (TCP) axis - see the seed print below.
BELT = np.array([0.0, -1.0, 0.0])

#: P64 phase 1's measured hold drift, as `q_drift (x) q_cmd = q_achieved`
#: (`logs/p64/P2_RESULTS.md`: axis (-0.7564,-0.6541,0), 26.798 deg, from 7 left
#: `grasp_lift` legs), and P64's shipped pre-compensated command
#: `q_cmd = q_drift^-1 (x) q_T0` - the literal file value, checked below.
DRIFT_AXIS = (-0.7564, -0.6541, 0.0)
DRIFT_ANGLE_DEG = 26.798
QPREC_FILE = np.array([+0.01675, -0.68786, +0.68786, +0.23113], dtype=float)


def quat_matrix(q) -> np.ndarray:
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


def quat_mul(a, b) -> np.ndarray:
    """Hamilton product, `[w, x, y, z]` order."""
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


def axis_quat(axis, angle_rad) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis = axis / max(float(np.linalg.norm(axis)), 1e-12)
    half = 0.5 * float(angle_rad)
    return np.concatenate([[np.cos(half)], np.sin(half) * axis])


def attitude_reads(q) -> tuple[float, float]:
    """(belt projection of the approach axis, jaw-opening axis' z), commanded frame."""
    r = quat_matrix(q)
    return float(r[:, 2] @ BELT), float(r[2, 1])


def pad_lowest_z(link_pos, link_quat, spec) -> float:
    """Lowest world point of an authored capsule pad rigidly tied to a finger link."""
    r_link = quat_matrix(link_quat)
    r_local = quat_matrix(spec["quat"])
    centre = np.asarray(link_pos, dtype=float) + r_link @ np.asarray(spec["translate"], dtype=float)
    axis = r_link @ r_local @ np.array([0.0, 0.0, 1.0])
    height = max(float(spec["size"][2]) - 2.0 * PAD_RADIUS, 0.005)
    return float(centre[2] - 0.5 * height * abs(float(axis[2])) - PAD_RADIUS)


def main() -> int:
    with open(os.path.join(HERE, "candidates.json"), encoding="utf-8") as handle:
        candidates = {row["name"]: row for row in json.load(handle)["rows"]}
    with open(os.path.join(ROOT, "configs", "waypoints_oriented.json"), encoding="utf-8") as handle:
        waypoints = json.load(handle)
    with open(os.path.join(ROOT, "configs", "finger_pads.json"), encoding="utf-8") as handle:
        pads = json.load(handle)["left"]

    # ---- the P64-screen derived attitudes (additive; C0..F3 rows unchanged) -- #
    q_t0 = np.asarray(candidates["T0"]["quat"], dtype=float)
    q_drift = axis_quat(DRIFT_AXIS, np.radians(DRIFT_ANGLE_DEG))
    q_prec = quat_mul(np.array([q_drift[0], -q_drift[1], -q_drift[2], -q_drift[3]]), q_t0)
    q_prec = q_prec / np.linalg.norm(q_prec)
    q_drift_cmd = quat_mul(q_drift, q_t0)
    q_drift_cmd = q_drift_cmd / np.linalg.norm(q_drift_cmd)
    # The file value is the shipped pre-compensation; the re-derivation must agree.
    same = abs(float(q_prec @ (QPREC_FILE / np.linalg.norm(QPREC_FILE))))
    say(
        f"[p62] QPREC check: q_drift^-1(x)q_T0 = "
        f"[{q_prec[0]:+.6f},{q_prec[1]:+.6f},{q_prec[2]:+.6f},{q_prec[3]:+.6f}] "
        f"vs file [{QPREC_FILE[0]:+.6f},{QPREC_FILE[1]:+.6f},{QPREC_FILE[2]:+.6f},"
        f"{QPREC_FILE[3]:+.6f}] |dot|={same:.6f} (1.0 = same rotation)"
    )
    candidates["QPREC"] = {"name": "QPREC", "quat": [float(v) for v in QPREC_FILE]}
    candidates["QDRIFT"] = {"name": "QDRIFT", "quat": [float(v) for v in q_drift_cmd]}
    candidates["QFILE"] = {
        "name": "QFILE",
        "quat": [float(v) for v in waypoints["grasp_quaternion"]["left"]],
    }
    for name in ("QPREC", "QDRIFT", "QFILE"):
        proj, jz = attitude_reads(candidates[name]["quat"])
        say(f"[p62] derived {name:6s} proj_cmd={proj:+.4f} jaw_z_cmd={jz:+.4f}")

    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(
        f"[p62] belt_top={belt_top:.3f} pick=({cfg.pick_x:.3f},{cfg.pick_y:.3f}) "
        f"z_grip={Z_GRIP:.3f} tol={TOL * 1000:.1f}mm cand={','.join(CANDIDATES)} "
        f"x={','.join(f'{v:.3f}' for v in XS)}"
    )

    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=40)
    seed = np.asarray(waypoints["arms"]["left"]["grasp"], dtype=float)
    q_shipped = np.asarray(candidates["C0"]["quat"], dtype=float)

    # ---- the calibrated seed under the shipped attitude: frame semantics ---- #
    arm.teleport_joints(seed)
    arm.hold_quaternion = q_shipped
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=20)
    tcp_seed, quat_seed = arm.tcp_pose()
    jaw_seed = np.asarray(arm.jaw_centre(), dtype=float)
    approach = np.asarray(arm.approach_axis(), dtype=float)
    jaw_axis = np.asarray(arm.jaw_axis(), dtype=float)
    r_seed = quat_matrix(quat_seed)
    left_f, right_f = arm.jaw_positions()
    say(
        f"[p62] seed jaw=[{jaw_seed[0]:+.4f},{jaw_seed[1]:+.4f},{jaw_seed[2]:.4f}] "
        f"z-belt={1000 * (jaw_seed[2] - belt_top):+.1f}mm "
        f"tcp_z-belt={1000 * (tcp_seed[2] - belt_top):+.1f}mm "
        f"|tcp-jaw|={1000 * float(np.linalg.norm(tcp_seed - jaw_seed)):.1f}mm"
    )
    say(
        f"[p62] seed approach_axis=[{approach[0]:+.3f},{approach[1]:+.3f},{approach[2]:+.3f}] "
        f"jaw_axis=[{jaw_axis[0]:+.3f},{jaw_axis[1]:+.3f},{jaw_axis[2]:+.3f}] "
        f"jaw_sep={1000 * float(np.linalg.norm(np.asarray(left_f) - np.asarray(right_f))):.1f}mm"
        f" |tcp-jaw|={1000 * float(np.linalg.norm(tcp_seed - jaw_seed)):.1f}mm"
    )
    say(
        "[p62] frame (achieved seed R, columns) "
        + " ".join(
            f"col{i}=[{r_seed[0, i]:+.3f},{r_seed[1, i]:+.3f},{r_seed[2, i]:+.3f}]"
            for i in range(3)
        )
    )
    say(
        "[p62] |dot| approach x cols = "
        + " ".join(f"{abs(float(approach @ r_seed[:, i])):.3f}" for i in range(3))
        + " | jaw x cols = "
        + " ".join(f"{abs(float(jaw_axis @ r_seed[:, i])):.3f}" for i in range(3))
        + f" | qerr_shipped_vs_achieved={np.degrees(np.linalg.norm(quaternion_error(q_shipped, quat_seed))):.2f}deg"
    )

    # ---- the candidate ladder ---------------------------------------------- #
    rows = []
    for name in CANDIDATES:
        q = np.asarray(candidates[name]["quat"], dtype=float)
        q = q / np.linalg.norm(q)
        for x in XS:
            arm.teleport_joints(seed)
            arm.hold_quaternion = q
            arm.set_gripper(arm.OPEN)
            app_utils.update_app(steps=20)
            target = np.array([x, cfg.pick_y, belt_top + Z_GRIP], dtype=float)
            config, residual = arm.solve_to(
                target, iterations=400, tolerance=TOL, restarts=RESTARTS, seed=7
            )
            tcp, quat = arm.tcp_pose()
            jaw = np.asarray(arm.jaw_centre(), dtype=float)
            qerr = float(np.degrees(np.linalg.norm(quaternion_error(q, quat))))
            # Achieved TCP frame: col2 is the approach axis, col1 the -jaw axis
            # (the seed print below settles that on the shipped attitude), so the
            # achieved belt projection is directly comparable to the command's.
            r_ach = quat_matrix(quat)
            proj_cmd, jawz_cmd = attitude_reads(q)
            proj_ach = float(r_ach[:, 2] @ BELT)
            jawz_ach = float(r_ach[2, 1])
            jaw_sep = float(np.linalg.norm(np.asarray(arm.jaw_positions()[1]) - np.asarray(arm.jaw_positions()[0])))
            margins = np.minimum(config - arm.arm_lo, arm.arm_hi - config)
            joint = int(np.argmin(margins))
            pos_l, quat_l = arm._finger_prims[0].get_world_poses()
            pos_l = np.asarray(pos_l)[0]
            quat_l = np.asarray(quat_l)[0]
            pos_r = np.asarray(arm._finger_prims[1].get_world_poses()[0])[0]
            left_pads = min(
                pad_lowest_z(pos_l, quat_l, pads["openarm_left_left_finger"]),
                pad_lowest_z(pos_r, quat_l, pads["openarm_left_right_finger"]),
            )
            finger_min = min(float(pos_l[2]), float(pos_r[2]))
            row = {
                "cand": name,
                "x": x,
                "restarts": RESTARTS,
                "residual_mm": 1000 * residual,
                "qerr_deg": qerr,
                "belt_proj_cmd": proj_cmd,
                "belt_proj_ach": proj_ach,
                "jaw_z_cmd": jawz_cmd,
                "jaw_z_ach": jawz_ach,
                "jaw_sep_mm": 1000 * jaw_sep,
                "jaw_pad_dz_mm": 1000 * abs(jawz_ach) * jaw_sep,
                "margin_rad": float(margins[joint]),
                "margin_joint": joint + 1,
                "config": [float(v) for v in config],
                "jaw": [float(v) for v in jaw],
                "jaw_dz_mm": 1000 * (float(jaw[2]) - target[2]),
                "pad_low_belt_mm": 1000 * (left_pads - belt_top),
                "finger_min_belt_mm": 1000 * (finger_min - belt_top),
                "tcp_z_belt_mm": 1000 * (float(tcp[2]) - belt_top),
                "pad_minus_control": None,
            }
            rows.append(row)
            say(
                f"[p62] {name:6s} x={x:.3f} res={row['residual_mm']:6.1f}mm "
                f"qerr={qerr:5.2f}deg margin={row['margin_rad']:+.3f}rad@j{row['margin_joint']} "
                f"jaw_dz={row['jaw_dz_mm']:+6.1f}mm pad_belt={row['pad_low_belt_mm']:+7.1f}mm "
                f"finger_belt={row['finger_min_belt_mm']:+7.1f}mm tcp_belt={row['tcp_z_belt_mm']:+7.1f}mm "
                f"proj_cmd={proj_cmd:+.4f} proj_ach={proj_ach:+.4f} "
                f"jaw_z={jawz_ach:+.4f} pad_dz={row['jaw_pad_dz_mm']:5.1f}mm"
            )

    # ---- verdict per candidate, against the control at the same x ---------- #
    say("[p62] ---- verdict (control C0 at the same x) ----")
    verds = {}
    for name in CANDIDATES:
        mine = [r for r in rows if r["cand"] == name]
        ctrl = [r for r in rows if r["cand"] == "C0"]
        solved = [r for r in mine if r["residual_mm"] <= 1000 * TOL]
        worst_pad_delta = None
        if name != "C0":
            deltas = [
                r["pad_low_belt_mm"] - c["pad_low_belt_mm"]
                for r, c in zip(mine, ctrl)
                if r["x"] == c["x"]
            ]
            worst_pad_delta = min(deltas) if deltas else None
            for r in mine:
                c = next((c for c in ctrl if c["x"] == r["x"]), None)
                if c is not None:
                    r["pad_minus_control"] = r["pad_low_belt_mm"] - c["pad_low_belt_mm"]
        verds[name] = {
            "solved": len(solved),
            "of": len(mine),
            "max_residual_mm": max((r["residual_mm"] for r in mine), default=None),
            "worst_qerr_deg": max((r["qerr_deg"] for r in mine), default=None),
            "worst_margin_rad": min((r["margin_rad"] for r in mine), default=None),
            "worst_pad_delta_mm": worst_pad_delta,
        }
        v = verds[name]
        say(
            f"[p62] {name:6s} solved {v['solved']}/{v['of']} (<=tol), "
            f"max_res={v['max_residual_mm']:.1f}mm worst_qerr={v['worst_qerr_deg']:.2f}deg "
            f"worst_margin={v['worst_margin_rad']:+.3f}rad "
            f"worst_pad_delta_vs_control={'-' if worst_pad_delta is None else f'{worst_pad_delta:+.1f}mm'}"
        )

    out = JSON_OUT
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "belt_top": belt_top,
                "pick": [cfg.pick_x, cfg.pick_y],
                "z_grip": Z_GRIP,
                "tol": TOL,
                "quats": {n: [float(v) for v in candidates[n]["quat"]] for n in CANDIDATES},
                "drift": {"axis": list(DRIFT_AXIS), "angle_deg": DRIFT_ANGLE_DEG,
                          "qprec_file": [float(v) for v in QPREC_FILE], "prec_dot": same},
                "seed": {
                    "jaw": [float(v) for v in jaw_seed],
                    "tcp_z_belt_mm": 1000 * (float(tcp_seed[2]) - belt_top),
                    "tcp_jaw_mm": 1000 * float(np.linalg.norm(tcp_seed - jaw_seed)),
                    "approach_axis": [float(v) for v in approach],
                    "jaw_axis": [float(v) for v in jaw_axis],
                    "cols": [[float(r_seed[r, c]) for r in range(3)] for c in range(3)],
                },
                "rows": rows,
                "verdict": verds,
            },
            handle,
            indent=1,
        )
    say(f"[p62] wrote {out}")
    say("[p62] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
