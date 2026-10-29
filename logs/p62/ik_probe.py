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
                f"[p62] {name:5s} x={x:.3f} res={row['residual_mm']:6.1f}mm "
                f"qerr={qerr:5.2f}deg margin={row['margin_rad']:+.3f}rad@j{row['margin_joint']} "
                f"jaw_dz={row['jaw_dz_mm']:+6.1f}mm pad_belt={row['pad_low_belt_mm']:+7.1f}mm "
                f"finger_belt={row['finger_min_belt_mm']:+7.1f}mm tcp_belt={row['tcp_z_belt_mm']:+7.1f}mm"
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
            f"[p62] {name:5s} solved {v['solved']}/{v['of']} (<=tol), "
            f"max_res={v['max_residual_mm']:.1f}mm worst_qerr={v['worst_qerr_deg']:.2f}deg "
            f"worst_margin={v['worst_margin_rad']:+.3f}rad "
            f"worst_pad_delta_vs_control={'-' if worst_pad_delta is None else f'{worst_pad_delta:+.1f}mm'}"
        )

    out = os.path.join(HERE, "ik_probe_rows.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "belt_top": belt_top,
                "pick": [cfg.pick_x, cfg.pick_y],
                "z_grip": Z_GRIP,
                "tol": TOL,
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
