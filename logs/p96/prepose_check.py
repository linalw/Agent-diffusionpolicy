"""P96 extension E1 - the pre-pose **attitude** and a static pad witness.

    scripts/run.sh logs/p96/prepose_check.py     # -> logs/p96/prepose_check_rows.json

Registration: `logs/p96/PREREG_A1.md` (the mode set, the readouts, the criterion
and the selection rule are pinned before this ran). Phase 0's grid is
`logs/p96/prepose_map.py` / `prepose_rows.json`.

Modes per arm at its own station, `x = cfg.pick_x`:

* `CFG` - the calibrated `grasp` configuration, teleported to and settled: **the
  shipped left pre-pose** (the left station *is* the pick point, so
  `_prepare_two_line_stations` skips its solve) and the pose P95 measured live.
* `C0`  - hold `configs/waypoints_oriented.json`'s own `grasp_quaternion` for this
  arm and solve: "the same attitude the line was calibrated with, only higher".
* `NAT` - `hold_quaternion = None`: the position-only staging solve.
* `T0`  - `mirror_across_xz(top_down_quaternion("x"))` (left) / the un-mirrored
  one (right): the hold `_prepare_two_line_stations` pins today.

Readouts: residual, `qerr` against the mode's hold, the **achieved tilt**
(`acos(-rot[2,2])`, 0 deg = tool axis straight down; P73's expression), joint
margin, and the **lowest authored finger-pad point** above the belt top (P66's
`pad_lowest_z` against `configs/finger_pads.json`) - the static clearance
witness.
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
from fruit_sorting.motion import mirror_across_xz, top_down_quaternion
from fruit_sorting.scene import SortingScene

install_failure_handler("p96_prepose_check")

DT = 1.0 / 120.0
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

PAD_DROP = 0.0805
FRUIT_TOP = 0.0585
CLEARANCE_J = 0.155
MARGIN_MIN_RAD = 0.02
PAD_RADIUS = 0.010
TOL = float(os.environ.get("FRUIT_P96_TOL", "0.006"))
RESTARTS = int(os.environ.get("FRUIT_P96_RESTARTS", "3"))
SEED_NAME = os.environ.get("FRUIT_P96_SEED", "grasp").strip() or "grasp"
ARMS = tuple(a.strip() for a in os.environ.get("FRUIT_P96_ARMS", "left,right").split(",") if a.strip())
XS = tuple(float(v) for v in os.environ.get("FRUIT_P96_X", f"{SceneConfig().pick_x:.2f}").split(","))
ZS = tuple(float(v) for v in os.environ.get("FRUIT_P96_Z", "0.155,0.165,0.18").split(","))
MODES = tuple(m.strip() for m in os.environ.get("FRUIT_P96_MODES", "CFG,C0,NAT,T0").split(",") if m.strip())
JSON_OUT = os.environ.get("FRUIT_P96_JSON", os.path.join(HERE, "prepose_check_rows.json"))
STATION_Y = {"left": 0.0, "right": -0.10}


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


def tilt_deg(q) -> float:
    """`acos(-rot[2,2])` in degrees: 0 = tool axis straight down (P73)."""
    r = quat_matrix(q)
    return float(np.degrees(np.arccos(np.clip(-float(r[2, 2]), -1.0, 1.0))))


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
    #: The **shipped** waypoints file is `configs/waypoints.json`; P66's recipe
    #: read the oriented variant, and the two files' `arms.<side>.grasp` seeds
    #: are *different poses* (Linf 1.21 rad apart, P66's own print). `calib`-mode
    #: rows are therefore run for both files: the shipped seed is the pose the
    #: task's pre-pose blend actually reaches.
    WP_FILE = os.environ.get("FRUIT_P96_WAYPOINTS", "configs/waypoints_oriented.json")
    with open(os.path.join(ROOT, WP_FILE), encoding="utf-8") as fh:
        waypoints = json.load(fh)
    with open(os.path.join(ROOT, "configs", "finger_pads.json"), encoding="utf-8") as fh:
        all_pads = json.load(fh)

    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(
        f"[p96a1] waypoints={WP_FILE} belt_top={belt_top:.4f} pick_x={cfg.pick_x:.3f} "
        f"modes={'/'.join(MODES)} "
        f"x={','.join(f'{v:.2f}' for v in XS)} z={','.join(f'{v:.3f}' for v in ZS)} "
        f"restarts={RESTARTS}"
    )

    rows = []
    for side in ARMS:
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=40)
        seed = np.asarray(waypoints["arms"][side][SEED_NAME], dtype=float)
        q_c0 = np.asarray(waypoints["grasp_quaternion"][side], dtype=float)
        q_c0 = q_c0 / np.linalg.norm(q_c0)
        q_t0 = top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x"))
        if side == "left":
            q_t0 = mirror_across_xz(q_t0)
        station_y = float(STATION_Y[side])
        pads = all_pads[side]

        def read(tag: str, mode: str, z: float, x: float, cfg_q):
            jaw = np.asarray(arm.jaw_centre(), dtype=float)
            _, quat = arm.tcp_pose()
            qerr = (
                float("nan")
                if cfg_q is None
                else float(np.degrees(np.linalg.norm(quaternion_error(cfg_q, quat))))
            )
            pos_l, quat_l = arm._finger_prims[0].get_world_poses()
            pos_l, quat_l = np.asarray(pos_l)[0], np.asarray(quat_l)[0]
            pos_r, quat_r = arm._finger_prims[1].get_world_poses()
            pos_r, quat_r = np.asarray(pos_r)[0], np.asarray(quat_r)[0]
            # `configs/finger_pads.json` names the boxes per hand; use each hand's
            # own pair so the pad body is the authored one.
            pl = pad_lowest_z(pos_l, quat_l, pads[f"openarm_{side}_left_finger"])
            pr = pad_lowest_z(pos_r, quat_r, pads[f"openarm_{side}_right_finger"])
            jl = np.minimum(arm.joint_positions() - arm.arm_lo, arm.arm_hi - arm.joint_positions())
            return {
                "arm": side,
                "cand": mode,
                "x": x,
                "y": station_y,
                "z_above_belt": z,
                "jaw_z_belt_mm": 1000 * (float(jaw[2]) - belt_top),
                "pad_point_z_belt_mm": 1000 * (float(jaw[2]) - PAD_DROP - belt_top),
                "pad_low_belt_mm": 1000 * (min(pl, pr) - belt_top),
                "tilt_deg": tilt_deg(quat),
                "qerr_deg": qerr,
                "margin_rad": float(jl.min()),
                "margin_joint": int(np.argmin(jl)) + 1,
            }

        # ---- CFG: the shipped pre-pose (teleported to, settled) ----------------- #
        if "CFG" in MODES:
            arm.hold_quaternion = None
            arm.teleport_joints(seed)
            arm.set_gripper(arm.OPEN)
            app_utils.update_app(steps=20)
            r = read("CFG", "CFG", float(seed[0] * 0.0), float(arm.jaw_centre()[0]), None)
            r["residual_mm"] = 0.0
            r["note"] = "the calibrated grasp config, teleported (the shipped pre-pose)"
            r["pass"] = bool(r["jaw_z_belt_mm"] >= 1000 * CLEARANCE_J)
            rows.append(r)
            say(
                f"[p96a1] {side} CFG: jaw={r['jaw_z_belt_mm']:+.1f}mm "
                f"pad_point={r['pad_point_z_belt_mm']:+.1f} pad_low={r['pad_low_belt_mm']:+.1f} "
                f"tilt={r['tilt_deg']:.1f}deg margin={r['margin_rad']:+.3f}@j{r['margin_joint']} "
                f"{'PASS' if r['pass'] else 'BELOW THE CLEARANCE'}"
            )

        for mode in [m for m in MODES if m != "CFG"]:
            q = {"T0": q_t0, "C0": q_c0, "NAT": None}[mode]
            for z in ZS:
                for x in XS:
                    target = np.array([x, station_y, belt_top + z], dtype=float)
                    arm.teleport_joints(seed)
                    arm.hold_quaternion = q
                    arm.set_gripper(arm.OPEN)
                    app_utils.update_app(steps=20)
                    config, residual = arm.solve_to(
                        target, iterations=400, tolerance=TOL, restarts=RESTARTS, seed=7
                    )
                    r = read(mode, mode, z, x, q)
                    r["residual_mm"] = 1000 * float(residual)
                    r["config"] = [float(v) for v in config]
                    r["jaw_dz_mm"] = 1000 * (r["jaw_z_belt_mm"] - 1000 * z) / 1000
                    r["pass"] = bool(
                        float(residual) <= TOL
                        and r["jaw_z_belt_mm"] >= 1000 * (z - TOL)
                        and r["margin_rad"] >= MARGIN_MIN_RAD
                        and r["jaw_z_belt_mm"] >= 1000 * CLEARANCE_J
                    )
                    rows.append(r)
                    say(
                        f"[p96a1] {side} {mode:>3} x={x:.2f} z=+{z:.3f}: "
                        f"res={r['residual_mm']:5.1f}mm qerr={r['qerr_deg']:6.1f} "
                        f"tilt={r['tilt_deg']:6.1f}deg jaw={r['jaw_z_belt_mm']:+6.1f} "
                        f"pad_low={r['pad_low_belt_mm']:+6.1f} "
                        f"margin={r['margin_rad']:+.3f}@j{r['margin_joint']} "
                        f"{'PASS' if r['pass'] else '-'}"
                    )
            arm.hold_quaternion = None

    with open(JSON_OUT, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)

    # ---- the selection rule (PREREG_A1), printed so the driver log carries it -- #
    say("")
    for z in ZS:
        both = []
        for mode in [m for m in MODES if m != "CFG"]:
            per_arm = {}
            for side in ARMS:
                cand = [
                    r for r in rows
                    if r["arm"] == side and r["cand"] == mode
                    and abs(r["z_above_belt"] - z) < 1e-9 and r["pass"]
                ]
                if cand:
                    per_arm[side] = max(cand, key=lambda r: r["margin_rad"])
            if len(per_arm) == len(ARMS):
                both.append((min(v["margin_rad"] for v in per_arm.values()), mode, per_arm))
        if not both:
            say(f"[p96a1] z=+{z:.3f}: NO mode passes on both arms")
            continue
        both.sort(key=lambda t: -t[0])
        m, mode, per_arm = both[0]
        tilts = {s: round(v["tilt_deg"], 1) for s, v in per_arm.items()}
        say(
            f"[p96a1] z=+{z:.3f}: best mode {mode} (min margin {m:+.3f} rad, "
            f"tilts {tilts}, pads {({s: round(v['pad_low_belt_mm'], 1) for s, v in per_arm.items()})})"
        )
    say(f"[p96a1] {len(rows)} rows -> {JSON_OUT} ({time.time() - t_start:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
