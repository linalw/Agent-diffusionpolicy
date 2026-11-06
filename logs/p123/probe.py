"""P123 - the scene survey and the candidate place solves (one static session).

    scripts/run.sh logs/p123/probe.py            # -> logs/p123/probe.log

Two sections, no attempt loop, no policy:

**S - the scene survey.** Builds the shipped bodies (environment, pedestal,
robot, main conveyor, the two raised output belts with their chutes and trays)
and prints every body's **world AABB** from the stage's own bounds cache, plus
the pick stations, the head camera's pose/FOV and the free space at the output
deck. This is the answer to "where can a third body physically go".

**R - the reach solve.** P90's machinery (`logs/p90/station_map.py`, `NAT` mode:
`hold_quaternion = None`, the position-only solve the shipped place leg actually
runs): teleports each arm to the `grasp_lift` seed and solves the candidate place
cells at both heights the place leg uses (1.450 = `output_place_z`, 1.530 = the
transfer, +0.08 for the rigid-tool hand). Per cell: residual, joint margin, the
achieved tilt, and the **pad clearance over the surface actually under it** (the
new lane's slab where a candidate sits on it, not the main belt - P90's own
switch charges the main belt for |y| < 0.40, which is exactly the band a third
inboard lane occupies). The pass clause is `logs/p123/PREREG.md`'s.

Env: `FRUIT_P123_X`, `FRUIT_P123_Y` (|y| ladder, comma separated),
`FRUIT_P123_Z`, `FRUIT_P123_ARMS`, `FRUIT_P123_JSON`.
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
from pxr import Usd, UsdGeom

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.control import ArmController, quaternion_error
from fruit_sorting.scene import SortingScene

install_failure_handler("p123_probe")

DT = 1.0 / 120.0
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

ARMS = tuple(a.strip() for a in os.environ.get("FRUIT_P123_ARMS", "left,right").split(",") if a.strip())
XS = tuple(float(v) for v in os.environ.get("FRUIT_P123_X", "0.48,0.46,0.44,0.43,0.38").split(","))
YS = tuple(float(v) for v in os.environ.get("FRUIT_P123_Y", "0.30,0.31,0.32,0.33,0.35,0.40,0.50,0.55").split(","))
ZS = tuple(float(v) for v in os.environ.get("FRUIT_P123_Z", "1.450,1.530").split(","))
SEED_NAME = os.environ.get("FRUIT_P123_SEED", "grasp_lift").strip() or "grasp_lift"
TOL = float(os.environ.get("FRUIT_P123_TOL", "0.006"))
RESTARTS = int(os.environ.get("FRUIT_P123_RESTARTS", "2"))
PAD_RADIUS = float(os.environ.get("FRUIT_PAD_RADIUS", "0.010"))
JSON_OUT = os.environ.get("FRUIT_P123_JSON", os.path.join(HERE, "probe_rows.json"))

#: `logs/p123/PREREG.md`'s pass clause, pinned before this ran.
RES_MAX_MM = 6.0
MARGIN_MIN_RAD = 0.05
PAD_MIN_MM = 2.0
TILT_BAND = (60.0, 110.0)
#: `assets.OUTPUT_RAIL_INSET`'s role for the clearance report: the shipped code
#: charges the output plane from |y| = 0.40 (the removed inner rail's face).
EARLY_Y = 0.40


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
    r = quat_matrix(q)
    return float(np.degrees(np.arccos(max(-1.0, min(1.0, -float(r[2, 2]))))))


def pad_lowest_z(link_pos, link_quat, spec) -> float:
    r_link = quat_matrix(link_quat)
    r_local = quat_matrix(spec["quat"])
    centre = np.asarray(link_pos, dtype=float) + r_link @ np.asarray(spec["translate"], dtype=float)
    axis = r_link @ r_local @ np.array([0.0, 0.0, 1.0])
    height = max(float(spec["size"][2]) - 2.0 * PAD_RADIUS, 0.005)
    return float(centre[2] - 0.5 * height * abs(float(axis[2])) - PAD_RADIUS)


# --------------------------------------------------------------------------- #
# S - the scene survey
# --------------------------------------------------------------------------- #
def survey(stage: Usd.Stage, cfg: SceneConfig) -> None:
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
    belt_top = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0

    print("[p123] == S. the shipped scene: every body's world AABB (stage bounds) ==")
    print(f"[p123] S0 config: belt x {cfg.belt_center[0] - cfg.belt_size[0] / 2:.3f}"
          f"..{cfg.belt_center[0] + cfg.belt_size[0] / 2:.3f}"
          f" y {cfg.belt_center[1] - cfg.belt_size[1] / 2:+.3f}"
          f"..{cfg.belt_center[1] + cfg.belt_size[1] / 2:+.3f} top {belt_top:.3f}"
          f" | output |y| {abs(cfg.output_belt_y) - cfg.output_belt_size[1] / 2:.3f}"
          f"..{abs(cfg.output_belt_y) + cfg.output_belt_size[1] / 2:.3f}"
          f" x {cfg.output_belt_x_range[0]:.2f}..{cfg.output_belt_x_range[1]:.2f}"
          f" top {cfg.output_belt_top_z:.3f}"
          f" | pedestal {cfg.pedestal_size} at {cfg.pedestal_center_xy}"
          f" | rails {cfg.output_rails}")

    roots = [
        "/World/Pedestal",
        "/World/Conveyor",
        "/World/OutputBeltP",
        "/World/OutputBeltN",
        "/World/OpenArm",
        "/World/HeadCamera",
    ]
    for root in roots:
        prim = stage.GetPrimAtPath(root)
        if not prim or not prim.IsValid():
            print(f"[p123] S1 {root}: (not built)")
            continue
        bound = cache.ComputeWorldBound(prim)
        rng = bound.ComputeAlignedRange()
        lo, hi = rng.GetMin(), rng.GetMax()
        print(f"[p123] S1 {root}: x {lo[0]:+.3f}..{hi[0]:+.3f}  y {lo[1]:+.3f}..{hi[1]:+.3f}"
              f"  z {lo[2]:.3f}..{hi[2]:.3f}")
        if root.startswith("/World/OutputBelt"):
            # the parts, so the reader can see the belt / chute / tray split
            for child in prim.GetChildren():
                cbound = cache.ComputeWorldBound(child).ComputeAlignedRange()
                clo, chi = cbound.GetMin(), cbound.GetMax()
                print(f"[p123] S2   {child.GetName():<12} x {clo[0]:+.3f}..{chi[0]:+.3f}"
                      f"  y {clo[1]:+.3f}..{chi[1]:+.3f}  z {clo[2]:.3f}..{chi[2]:.3f}")

    # the free space at the output deck: which |y| bands carry a body at z 1.30-1.35
    print("[p123] S3 the output deck's occupied |y| bands at z = 1.30..1.35 (slabs):")
    for root in ("/World/OutputBeltP", "/World/OutputBeltN"):
        prim = stage.GetPrimAtPath(f"{root}/Belt")
        if not prim or not prim.IsValid():
            continue
        rng = cache.ComputeWorldBound(prim).ComputeAlignedRange()
        lo, hi = rng.GetMin(), rng.GetMax()
        print(f"[p123] S3   {root}/Belt: y {lo[1]:+.3f}..{hi[1]:+.3f}, x {lo[0]:.3f}..{hi[0]:.3f},"
              f" z {lo[2]:.3f}..{hi[2]:.3f}")
    print("[p123] S3 free |y| bands at that deck, inside the arm's reach (|y| <= 0.68):")
    bands = [(0.0, 0.425), (0.675, 1.0)]
    for lo, hi in bands:
        print(f"[p123] S3   |y| {lo:.3f}..{hi:.3f} free of a slab"
              + (" (the inboard band; the pedestal is |y|<=0.35 at x<=0.10)"
                 if lo == 0.0 else " (outboard; outside P90's reach box)"))

    # the arm's own bounds, so a body's clearance to the robot is visible
    for root in ("/World/OpenArm",):
        prim = stage.GetPrimAtPath(root)
        if prim and prim.IsValid():
            for child in prim.GetChildren():
                if "hand" not in child.GetName() and "finger" not in child.GetName():
                    continue
                cbound = cache.ComputeWorldBound(child).ComputeAlignedRange()
                clo, chi = cbound.GetMin(), cbound.GetMax()
                print(f"[p123] S4 {child.GetName():<34} x {clo[0]:+.3f}..{chi[0]:+.3f}"
                      f"  y {clo[1]:+.3f}..{chi[1]:+.3f}  z {clo[2]:.3f}..{chi[2]:.3f}")
    print("[p123] S4 pick stations: left (0.34, 0.00), right (0.34, -0.10);"
          f" lift end z {belt_top + 0.36:.3f} scripted / {belt_top + 0.20:.3f} direct-low")
    print("[p123] S4 head camera: lens (0.05, 0.00, 2.00) -> target (0.34, 0.22, 1.10),"
          " 16 mm, 848 x 480, HFOV 96.7 deg")


# --------------------------------------------------------------------------- #
# R - the candidate reach solve
# --------------------------------------------------------------------------- #
def main() -> int:
    t_start = time.time()
    with open(os.path.join(ROOT, "configs", "finger_pads.json"), encoding="utf-8") as handle:
        pads = json.load(handle)
    with open(os.path.join(ROOT, "configs", "waypoints_oriented.json"), encoding="utf-8") as handle:
        waypoints = json.load(handle)

    cfg = SceneConfig()
    belt_top = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0
    out_top = float(cfg.output_belt_top_z)
    y_edge = abs(float(cfg.output_belt_y)) - float(cfg.output_belt_size[1]) / 2.0
    #: the candidate third lane's slab band (P123): |y| 0.280..0.395 at the same
    #: top. A cell inside it is charged against the new slab, not the main belt.
    new_band = (0.280, 0.395)

    scene = SortingScene(cfg).build(
        parts=("environment", "pedestal", "robot", "conveyor", "output_belts")
    )
    scene.start(physics_dt=DT, warmup_steps=60)
    survey(scene.stage, cfg)

    arms = {}
    for side in ARMS:
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        arms[side] = arm
    app_utils.update_app(steps=40)

    print("[p123] == R. the candidate place solves (NAT: hold_quaternion = None, the")
    print("[p123]    position-only solve the shipped place leg runs) ==")
    print(f"[p123] R0 gate: res <= {RES_MAX_MM:.0f} mm, margin >= {MARGIN_MIN_RAD:.2f} rad,"
          f" pad >= {PAD_MIN_MM:.0f} mm, tilt {TILT_BAND[0]:.0f}-{TILT_BAND[1]:.0f} deg;"
          f" seed {SEED_NAME}, restarts {RESTARTS}, tol {TOL * 1000:.1f} mm,"
          f" {len(ARMS) * len(XS) * len(YS) * len(ZS)} cells")

    rows = []
    for side in ARMS:
        arm = arms[side]
        sign = 1.0 if side == "left" else -1.0
        pad_specs = list(pads[side].values())
        seed = np.asarray(waypoints["arms"][side][SEED_NAME], dtype=float)
        arm.teleport_joints(seed)
        arm.hold_quaternion = None
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=20)
        jaw_seed = np.asarray(arm.jaw_centre(), dtype=float)
        _tcp, quat_seed = arm.tcp_pose()
        say(f"[p123] R0 {side} seed({SEED_NAME}) jaw=[{jaw_seed[0]:+.4f},"
            f"{jaw_seed[1]:+.4f},{jaw_seed[2]:.4f}] tilt={tilt_deg(quat_seed):.2f}deg")
        for z in ZS:
            for y_abs in YS:
                y = sign * y_abs
                surface = out_top if new_band[0] <= y_abs <= new_band[1] else (
                    out_top if y_abs >= EARLY_Y else belt_top)
                where = ("new lane" if new_band[0] <= y_abs <= new_band[1] else
                         ("output belt" if y_abs >= EARLY_Y else "main belt"))
                for x in XS:
                    t_cell = time.time()
                    arm.teleport_joints(seed)
                    arm.hold_quaternion = None
                    arm.set_gripper(arm.OPEN)
                    app_utils.update_app(steps=20)
                    target = np.array([x, y, z], dtype=float)
                    config, residual = arm.solve_to(
                        target, iterations=400, tolerance=TOL, restarts=RESTARTS, seed=7
                    )
                    _tcp, quat = arm.tcp_pose()
                    jaw = np.asarray(arm.jaw_centre(), dtype=float)
                    margins = np.minimum(config - arm.arm_lo, arm.arm_hi - config)
                    joint = int(np.argmin(margins))
                    margin = float(margins[joint])
                    pos_l, quat_l = arm._finger_prims[0].get_world_poses()
                    pos_r = np.asarray(arm._finger_prims[1].get_world_poses()[0])[0]
                    pad_low = min(
                        pad_lowest_z(np.asarray(pos_l)[0], np.asarray(quat_l)[0], pad_specs[0]),
                        pad_lowest_z(pos_r, np.asarray(quat_l)[0], pad_specs[1]),
                    )
                    res_mm = 1000.0 * residual
                    tilt = tilt_deg(quat)
                    pad_mm = 1000.0 * (pad_low - surface)
                    passed = bool(
                        res_mm <= RES_MAX_MM
                        and margin >= MARGIN_MIN_RAD
                        and pad_mm >= PAD_MIN_MM
                        and TILT_BAND[0] <= tilt <= TILT_BAND[1]
                    )
                    jaw_sep = float(np.linalg.norm(
                        np.asarray(arm.jaw_positions()[1]) - np.asarray(arm.jaw_positions()[0])))
                    row = {
                        "arm": side, "x": x, "y": y, "z_world": z,
                        "residual_mm": res_mm, "margin_rad": margin, "margin_joint": joint + 1,
                        "tilt_deg": tilt, "pad_lowest_z": pad_low,
                        "surface": surface, "surface_where": where,
                        "pad_above_surface_mm": pad_mm, "jaw_sep_mm": 1000.0 * jaw_sep,
                        "jaw": [float(v) for v in jaw],
                        "pass": passed, "seed": SEED_NAME, "restarts": RESTARTS,
                        "wall_s": time.time() - t_cell,
                    }
                    rows.append(row)
                    print(f"[p123] R1 {side:<5} z={z:.3f} y={y:+.3f} x={x:.3f} "
                          f"res={res_mm:5.1f}mm margin={margin:+.3f}rad@j{joint + 1} "
                          f"tilt={tilt:6.2f}deg pad={pad_mm:+7.1f}mm({where}) "
                          f"sep={1000 * jaw_sep:5.1f}mm PASS={int(passed)}")
                    sys.stdout.flush()
        # Park the arm before the next one moves: a solved place pose leaves a
        # link inside a kinematic slab, and a *second* arm's solve on top of that
        # wedges the contact island (measured: the first right-arm cell after 80
        # left-arm cells ran 4+ min at 400 % CPU and never printed a row).
        arm.hold_quaternion = None
        arm.teleport_joints(np.asarray(waypoints["arms"][side]["ready"], dtype=float))
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=20)
        say(f"[p123] R0 {side}: parked at the ready waypoint before the next arm")

    passed = [r for r in rows if r["pass"]]
    print(f"[p123] R2 {len(passed)} of {len(rows)} cells pass the gate "
          f"({time.time() - t_start:.0f} s)")
    for side in ARMS:
        sub = [r for r in passed if r["arm"] == side and abs(r["y"]) <= 0.40]
        print(f"[p123] R2 {side}: {len(sub)} inboard (|y| <= 0.40) passes: "
              + ", ".join(f"(x={r['x']:.2f},|y|={abs(r['y']):.2f},z={r['z_world']:.3f},"
                          f"res={r['residual_mm']:.1f}mm,pad={r['pad_above_surface_mm']:.0f}mm,"
                          f"tilt={r['tilt_deg']:.1f})" for r in sub))
    with open(JSON_OUT, "w", encoding="utf-8") as handle:
        json.dump({"rows": rows, "seed": SEED_NAME, "restarts": RESTARTS,
                   "gate": {"res_max_mm": RES_MAX_MM, "margin_min_rad": MARGIN_MIN_RAD,
                            "pad_min_mm": PAD_MIN_MM, "tilt_band": TILT_BAND},
                   "new_band": new_band}, handle, indent=1)
    say(f"[p123] wrote {JSON_OUT} ({len(rows)} rows)")
    print(f"[p123] done in {time.time() - t_start:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
