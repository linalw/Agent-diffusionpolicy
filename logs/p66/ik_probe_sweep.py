"""P66 phase 1a - the left station feasibility sweep over (x, y, depth).

    scripts/run.sh logs/p66/ik_probe_sweep.py

A **copy** of `logs/p62/ik_probe.py` (kept byte-untouched so the P62/P64 artifacts
stay reproducible) with three additions:

* `FRUIT_P66_Y` - a **y sweep** (along the belt; the catch's own aim y is chosen
  by *when* it fires, so along-belt offset is a free station variable);
* `FRUIT_P66_Z` - a **depth sweep**, a comma list of heights **above the belt
  top**: `0.09` is the grip depth the P62 probe used, `0.09 + LIFT_HEIGHT`
  (`tasks.py:615`, 0.16 m) is where the geometric lift ends, and `0.36` is the
  shipped `jaw_target("grasp_lift")` height (`belt_top + 0.28` plus the OpenArm
  `FRUIT_OPENARM_TRANSFER_LIFT` 0.08). The same x/y grid is used at every depth;
* `FRUIT_P66_JSON` - its own raw-row file (the P62 one is never written).

The question it answers (`logs/p66/STATION_SWEEP.md`): is there **any** station
point (any y, any depth) where the top-down attitude `T0` holds with
`qerr <= 2 deg` **and** `margin >= 0.05 rad` **and** `pad >= 2 mm`? `C0` (the
shipped quaternion, which *is* `configs/waypoints_oriented.json`'s left
`grasp_quaternion` - the probe prints `|dot|`) is the control at every cell.

Everything else is the P62 recipe, unchanged: build the same scene, teleport the
**left** arm to `configs/waypoints.json`'s `arms.left.grasp` seed, pin
`ArmController.hold_quaternion`, solve the catch's own position IK (jaw centre at
`(x, y, belt_top + z)`, `iterations=400`, `tolerance=6 mm`, `restarts=1`), and
read `res` / `qerr` / `margin@joint` / pads-above-belt / jaw axis.
"""

from __future__ import annotations

import json
import os
import sys
import time

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

install_failure_handler("p66_station_sweep")

DT = 1.0 / 120.0
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

CANDIDATES = tuple(
    name.strip()
    for name in os.environ.get("FRUIT_P66_CANDIDATES", "T0,C0").split(",")
    if name.strip()
)
XS = tuple(float(v) for v in os.environ.get("FRUIT_P66_X", "0.188,0.24,0.274,0.32,0.398").split(","))
YS = tuple(float(v) for v in os.environ.get("FRUIT_P66_Y", "-0.10,-0.05,0.00,0.05,0.10").split(","))
ZS = tuple(float(v) for v in os.environ.get("FRUIT_P66_Z", "0.09,0.25,0.36").split(","))
TOL = float(os.environ.get("FRUIT_P66_TOL", "0.006"))
RESTARTS = int(os.environ.get("FRUIT_P66_RESTARTS", "1"))
#: Which calibrated joint seed each cell is solved from. `grasp` (the default) is
#: the P62 recipe and the pose the catch actually starts the lift from; `grasp_lift`
#: asks the capability question - does *any* configuration hold the commanded
#: attitude at that height - from the named lift pose instead.
SEED_NAME = os.environ.get("FRUIT_P66_SEED", "grasp").strip() or "grasp"
PAD_RADIUS = float(os.environ.get("FRUIT_PAD_RADIUS", "0.010"))
JSON_OUT = os.environ.get("FRUIT_P66_JSON", os.path.join(HERE, "sweep_rows.json"))

#: `tasks.py:615` `PickAndPlaceTask.LIFT_HEIGHT` (read by `logs/p66/DEPTH_READ.md`
#: and restated here only so the row can label the depth it actually used).
LIFT_HEIGHT = 0.16

BELT = np.array([0.0, -1.0, 0.0])

#: The pass criterion of the question (P66 phase 1a).
QERR_MAX_DEG = 2.0
MARGIN_MIN_RAD = 0.05
PAD_MIN_MM = 2.0


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
    t_start = time.time()
    with open(os.path.join(HERE, "..", "p62", "candidates.json"), encoding="utf-8") as handle:
        candidates = {row["name"]: row for row in json.load(handle)["rows"]}
    with open(os.path.join(ROOT, "configs", "waypoints_oriented.json"), encoding="utf-8") as handle:
        waypoints = json.load(handle)
    with open(os.path.join(ROOT, "configs", "finger_pads.json"), encoding="utf-8") as handle:
        pads = json.load(handle)["left"]
    with open(os.path.join(ROOT, "configs", "waypoints.json"), encoding="utf-8") as handle:
        # Only for the P62 caveat: `174`/`183` solve from *this* file's seed, which
        # is a different calibration. The probe uses `waypoints_oriented`'s seed,
        # the one the catch's reset teleports to.
        legacy = json.load(handle)

    q_control = np.asarray(candidates["C0"]["quat"], dtype=float)
    q_control = q_control / np.linalg.norm(q_control)
    q_file = np.asarray(waypoints["grasp_quaternion"]["left"], dtype=float)
    q_file = q_file / np.linalg.norm(q_file)
    # C0 *is* the waypoints_oriented left quaternion (P62 §1). Print the agreement
    # so the control's identity is a measurement, not a claim.
    say(
        f"[p66] control check: |dot(C0, waypoints_oriented.left)| = "
        f"{abs(float(q_control @ q_file)):.9f} (1.0 = the control IS the file value)"
    )

    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(
        f"[p66] belt_top={belt_top:.3f} pick=({cfg.pick_x:.3f},{cfg.pick_y:.3f}) "
        f"z_above_belt={','.join(f'{v:.3f}' for v in ZS)} (grip 0.090, +LIFT_HEIGHT "
        f"{0.09 + LIFT_HEIGHT:.3f}, shipped grasp_lift 0.360) "
        f"tol={TOL * 1000:.1f}mm cand={','.join(CANDIDATES)} "
        f"x={','.join(f'{v:.3f}' for v in XS)} y={','.join(f'{v:+.2f}' for v in YS)} "
        f"seed={SEED_NAME} restarts={RESTARTS} "
        f"cells={len(CANDIDATES) * len(XS) * len(YS) * len(ZS)}"
    )

    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=40)
    seed = np.asarray(waypoints["arms"]["left"][SEED_NAME], dtype=float)
    seed_legacy = np.asarray(legacy["arms"]["left"]["grasp"], dtype=float)
    say(
        f"[p66] legacy seed (configs/waypoints.json, the 174/183 calibration - not used "
        f"here): Linf={float(np.abs(seed - seed_legacy).max()):.3f} rad "
        f"(P62's quoted 1.21), L2={float(np.linalg.norm(seed - seed_legacy)):.3f} rad"
    )

    # ---- the seed under the shipped attitude (the P62 frame check, condensed) -- #
    arm.teleport_joints(seed)
    arm.hold_quaternion = q_control
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=20)
    tcp_seed, quat_seed = arm.tcp_pose()
    jaw_seed = np.asarray(arm.jaw_centre(), dtype=float)
    approach = np.asarray(arm.approach_axis(), dtype=float)
    jaw_axis = np.asarray(arm.jaw_axis(), dtype=float)
    left_f, right_f = arm.jaw_positions()
    say(
        f"[p66] seed jaw=[{jaw_seed[0]:+.4f},{jaw_seed[1]:+.4f},{jaw_seed[2]:.4f}] "
        f"z-belt={1000 * (jaw_seed[2] - belt_top):+.1f}mm "
        f"approach=[{approach[0]:+.3f},{approach[1]:+.3f},{approach[2]:+.3f}] "
        f"jaw_axis=[{jaw_axis[0]:+.3f},{jaw_axis[1]:+.3f},{jaw_axis[2]:+.3f}] "
        f"jaw_sep={1000 * float(np.linalg.norm(np.asarray(left_f) - np.asarray(right_f))):.1f}mm "
        f"qerr_shipped_vs_achieved="
        f"{np.degrees(np.linalg.norm(quaternion_error(q_control, quat_seed))):.2f}deg"
    )

    # ---- the sweep ---------------------------------------------------------- #
    rows = []
    t_sweep = time.time()
    for name in CANDIDATES:
        q = np.asarray(candidates[name]["quat"], dtype=float)
        q = q / np.linalg.norm(q)
        proj_cmd, jawz_cmd = attitude_reads(q)
        for z in ZS:
            for y in YS:
                for x in XS:
                    t_cell = time.time()
                    arm.teleport_joints(seed)
                    arm.hold_quaternion = q
                    arm.set_gripper(arm.OPEN)
                    app_utils.update_app(steps=20)
                    target = np.array([x, y, belt_top + z], dtype=float)
                    config, residual = arm.solve_to(
                        target, iterations=400, tolerance=TOL, restarts=RESTARTS, seed=7
                    )
                    tcp, quat = arm.tcp_pose()
                    jaw = np.asarray(arm.jaw_centre(), dtype=float)
                    qerr = float(np.degrees(np.linalg.norm(quaternion_error(q, quat))))
                    r_ach = quat_matrix(quat)
                    proj_ach = float(r_ach[:, 2] @ BELT)
                    jawz_ach = float(r_ach[2, 1])
                    jaw_sep = float(
                        np.linalg.norm(
                            np.asarray(arm.jaw_positions()[1]) - np.asarray(arm.jaw_positions()[0])
                        )
                    )
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
                    pad_mm = 1000 * (left_pads - belt_top)
                    margin = float(margins[joint])
                    row = {
                        "cand": name,
                        "x": x,
                        "y": y,
                        "z_above_belt": z,
                        "z_world": belt_top + z,
                        "restarts": RESTARTS,
                        "residual_mm": 1000 * residual,
                        "qerr_deg": qerr,
                        "belt_proj_cmd": proj_cmd,
                        "belt_proj_ach": proj_ach,
                        "jaw_z_cmd": jawz_cmd,
                        "jaw_z_ach": jawz_ach,
                        "jaw_sep_mm": 1000 * jaw_sep,
                        "jaw_pad_dz_mm": 1000 * abs(jawz_ach) * jaw_sep,
                        "margin_rad": margin,
                        "margin_joint": joint + 1,
                        "config": [float(v) for v in config],
                        "jaw": [float(v) for v in jaw],
                        "jaw_dz_mm": 1000 * (float(jaw[2]) - target[2]),
                        "pad_low_belt_mm": pad_mm,
                        "finger_min_belt_mm": 1000 * (finger_min - belt_top),
                        "tcp_z_belt_mm": 1000 * (float(tcp[2]) - belt_top),
                        "solved": bool(residual <= TOL),
                        "pass": bool(
                            qerr <= QERR_MAX_DEG
                            and margin >= MARGIN_MIN_RAD
                            and pad_mm >= PAD_MIN_MM
                        ),
                        "wall_s": time.time() - t_cell,
                    }
                    rows.append(row)
                    say(
                        f"[p66] {name:4s} z={z:.3f} y={y:+.2f} x={x:.3f} "
                        f"res={row['residual_mm']:6.1f}mm qerr={qerr:5.2f}deg "
                        f"margin={margin:+.3f}rad@j{joint + 1} pad_belt={pad_mm:+7.1f}mm "
                        f"jaw_z={jawz_ach:+.4f} proj_ach={proj_ach:+.4f} "
                        f"PASS={int(row['pass'])} wall={row['wall_s']:.2f}s"
                    )
    t_sweep = time.time() - t_sweep

    # ---- the verdict grid --------------------------------------------------- #
    say("[p66] ---- pass grid (qerr<=2deg AND margin>=0.05rad AND pad>=2mm) ----")
    summary = {}
    for name in CANDIDATES:
        for z in ZS:
            cells = [r for r in rows if r["cand"] == name and r["z_above_belt"] == z]
            passed = [r for r in cells if r["pass"]]
            say(
                f"[p66] {name:4s} z={z:.3f} pass={len(passed)}/{len(cells)} "
                f"best_margin={max(r['margin_rad'] for r in cells):+.3f}rad "
                f"worst_qerr={min(r['qerr_deg'] for r in cells):.2f}.."
                f"{max(r['qerr_deg'] for r in cells):.2f}deg "
                f"min_pad={min(r['pad_low_belt_mm'] for r in cells):+.1f}mm "
                f"solved={sum(1 for r in cells if r['solved'])}/{len(cells)}"
            )
            for x in XS:
                ys = [r for r in cells if r["x"] == x]
                ok = [f"{r['y']:+.2f}" for r in ys if r["pass"]]
                say(
                    f"[p66]   {name:4s} z={z:.3f} x={x:.3f} pass_y=[{','.join(ok) if ok else '-'}] "
                    f"best_margin={max(r['margin_rad'] for r in ys):+.3f}@j"
                    f"{min(ys, key=lambda r: -r['margin_rad'])['margin_joint']} "
                    f"qerr={min(r['qerr_deg'] for r in ys):.2f}..{max(r['qerr_deg'] for r in ys):.2f} "
                    f"pad={min(r['pad_low_belt_mm'] for r in ys):+.1f} "
                    f"res={min(r['residual_mm'] for r in ys):.1f}..{max(r['residual_mm'] for r in ys):.1f}"
                )
            summary[f"{name}|{z:.3f}"] = {
                "pass": len(passed),
                "of": len(cells),
                "best_margin_rad": max(r["margin_rad"] for r in cells),
                "solved": sum(1 for r in cells if r["solved"]),
            }

    wall = time.time() - t_start
    say(
        f"[p66] cells={len(rows)} sweep_wall={t_sweep:.1f}s total_wall={wall:.1f}s "
        f"per_cell={t_sweep / max(1, len(rows)):.2f}s"
    )

    with open(JSON_OUT, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "belt_top": belt_top,
                "pick": [cfg.pick_x, cfg.pick_y],
                "xs": list(XS),
                "ys": list(YS),
                "zs": list(ZS),
                "lift_height": LIFT_HEIGHT,
                "seed_name": SEED_NAME,
                "restarts_setting": RESTARTS,
                "tol": TOL,
                "pass_criteria": {
                    "qerr_max_deg": QERR_MAX_DEG,
                    "margin_min_rad": MARGIN_MIN_RAD,
                    "pad_min_mm": PAD_MIN_MM,
                },
                "control_dot_file": abs(float(q_control @ q_file)),
                "quats": {n: [float(v) for v in candidates[n]["quat"]] for n in CANDIDATES},
                "seed": {"jaw": [float(v) for v in jaw_seed],
                         "approach_axis": [float(v) for v in approach],
                         "jaw_axis": [float(v) for v in jaw_axis]},
                "rows": rows,
                "summary": summary,
                "wall": {"sweep_s": t_sweep, "total_s": wall,
                         "per_cell_s": t_sweep / max(1, len(rows))},
            },
            handle,
            indent=1,
        )
    say(f"[p66] wrote {JSON_OUT}")
    say("[p66] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
