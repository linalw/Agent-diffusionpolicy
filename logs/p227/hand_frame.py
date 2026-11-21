#!/usr/bin/env python3
"""P227j: the Panda's hand frame, pad geometry and the attitude that grasps.

    FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/hand_frame.py

P227i (`logs/p227/finger_probe.log`) showed the finger drive tracks (0 -> 80 mm)
and P227i's grasp probe (`grasp_probe.log`) then dropped 0/6, with the pads
closing *to the commanded span* and the fruit slipping 170-230 mm - which is
what a wrong closing direction looks like, not a weak pinch. Two suspects, both
measurable in one session:

1. **the hand frame.** `top_down_quaternion("x")` is calibrated to the OpenArm's
   TCP frame (closing axis = its Y). The Panda's finger joints have
   `physics:axis = X` under `panda_hand`, so the same quaternion may point the
   pads *along the belt*. This probe prints the hand-frame axes actually
   measured: the closing axis, the finger/down axis, and the attitude error of
   each candidate hold.
2. **the standoff.** `dz` was copied from the OpenArm's tuned 60 mm, but the pad
   faces sit elsewhere on the Panda's fingers. This probe prints the finger
   meshes' extent in the tool frame relative to the jaw centre, so the standoff
   is *derived*, and then grasps at the derived value.

Read-only on `src/`.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import numpy as np  # noqa: E402
from pxr import Usd, UsdGeom  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.control import ArmController, arm_specs, quaternion_error  # noqa: E402
from fruit_sorting.fruits import FruitSpawner  # noqa: E402
from fruit_sorting.motion import min_jerk_ramp, top_down_quaternion  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

DT = 1.0 / 120.0
os.environ.setdefault("FRUIT_NO_SLEEP", "1")


def say(text: str) -> None:
    print(f"[fruit] [hf] {text}", flush=True)


def quat_matrix(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def mesh_world_corners(prim) -> np.ndarray:
    corners = []
    for sub in Usd.PrimRange(prim):
        if sub.GetTypeName() != "Mesh":
            continue
        box = UsdGeom.Boundable(sub).ComputeWorldBound(
            Usd.TimeCode.Default(), UsdGeom.Tokens.default_
        )
        rng = box.ComputeAlignedRange()
        mn = np.array(rng.GetMin(), dtype=float)
        mx = np.array(rng.GetMax(), dtype=float)
        corners.extend(
            [x, y, z] for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])
        )
    return np.array(corners) if corners else np.zeros((0, 3))


def pad_frame(stage, arm) -> dict:
    """The pads' geometry in the *tool* frame (jaw centre origin, hand rotation)."""
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    rot = quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
    spec = arm_specs()[0]
    out = {}
    for name in spec.finger_link_names:
        prim = stage.GetPrimAtPath(f"{spec.link_root}/{name}")
        corners = mesh_world_corners(prim) if prim.IsValid() else np.zeros((0, 3))
        if len(corners) == 0:
            out[name] = None
            continue
        rel = (corners - jaw) @ rot
        out[name] = {
            "close": (rel[:, 0].min(), rel[:, 0].max()),
            "along": (rel[:, 1].min(), rel[:, 1].max()),
            "down": (rel[:, 2].min(), rel[:, 2].max()),
        }
    return out


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    # static grasp gate: `SortingScene.step` is `update_app`, so the belt's own
    # `step()` (the only place a target speed reaches the collider) does not run
    # here - write the surface velocity directly, or the moving belt drags the
    # fruit ~0.12 m during the close and the probe measures the catch, not the
    # grasp (P227i's 0/6 was exactly that plus the 6 mm face offset).
    scene.belt.set_speed(0.0)
    scene.belt.speed = 0.0
    scene.belt._apply_speed(0.0)
    belt_top = float(scene.belt.belt_top)
    stage = scene.stage
    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)
    SimulationManager.step(steps=20)

    # ---- 1. the hand frame at the free hanging pose -------------------
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    tcp = np.asarray(arm.tcp_position(), dtype=float)
    rot = quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
    say(f"hand rotation columns (world): x={np.round(rot[:, 0], 3)} "
        f"y={np.round(rot[:, 1], 3)} z={np.round(rot[:, 2], 3)}")
    say(f"jaw - tcp (world)={np.round(jaw - tcp, 4)} -> hand frame "
        f"{np.round(rot.T @ (jaw - tcp), 4)}")
    axis_world = np.asarray(arm.jaw_axis(), dtype=float)
    say(f"closing axis (world)={np.round(axis_world, 3)} -> hand frame "
        f"{np.round(rot.T @ axis_world, 3)}")
    for name, box in pad_frame(stage, arm).items():
        if box is None:
            say(f"pad {name}: no mesh bound")
        else:
            say(f"pad {name}: close[{box['close'][0]:+.3f},{box['close'][1]:+.3f}] "
                f"along[{box['along'][0]:+.3f},{box['along'][1]:+.3f}] "
                f"down[{box['down'][0]:+.3f},{box['down'][1]:+.3f}] (tool frame, m)")

    # ---- 2. attitude candidates at the grasp pose ---------------------
    target = np.array([cfg.pick_x, cfg.pick_y, belt_top + float(cfg.grasp_clearance)])
    q0 = np.asarray(arm.joint_positions(), dtype=float)
    arm.teleport_joints(q0)
    arm.hold_quaternion = None
    above = np.array([target[0], target[1], target[2] + 0.12])
    arm.solve_to(above, iterations=600, tolerance=0.006, restarts=1, move_on_fail=True)
    SimulationManager.step(steps=5)
    q_sol, _ = arm.solve_to(target, iterations=1500, tolerance=0.004, restarts=2,
                            move_on_fail=True)
    SimulationManager.step(steps=5)
    q_grasp = np.asarray(q_sol, dtype=float)
    jaw_free = np.asarray(arm.jaw_centre(), dtype=float)
    say(f"grasp conf jaw=({jaw_free[0]:+.3f},{jaw_free[1]:+.3f},{jaw_free[2]:.3f}) "
        f"err={np.linalg.norm(jaw_free - target) * 1e3:.1f} mm")
    rot_free = quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
    a_local = rot_free.T @ np.asarray(arm.jaw_axis(), dtype=float)
    say(f"at the grasp conf: closing axis in hand frame={np.round(a_local, 3)}; "
        f"hand z (world)={np.round(rot_free[:, 2], 3)}; "
        f"jaw-tcp in hand frame={np.round(rot_free.T @ (jaw_free - np.asarray(arm.tcp_position(), dtype=float)), 4)}")
    for name, box in pad_frame(stage, arm).items():
        if box:
            say(f"  pad {name}: close[{box['close'][0]:+.3f},{box['close'][1]:+.3f}] "
                f"down[{box['down'][0]:+.3f},{box['down'][1]:+.3f}]")

    # the hold that maps the *measured* hand-frame closing axis to world X and
    # the fingers down. Build it from the measured axes, so it cannot inherit
    # the OpenArm's convention.
    a = a_local / max(float(np.linalg.norm(a_local)), 1e-9)
    # the finger/down direction in the hand frame: from the tcp to the jaw
    d_local = rot_free.T @ (jaw_free - np.asarray(arm.tcp_position(), dtype=float))
    d = d_local / max(float(np.linalg.norm(d_local)), 1e-9)
    third = np.cross(a, d)
    third /= max(float(np.linalg.norm(third)), 1e-9)
    a_w = np.array([1.0, 0.0, 0.0])
    d_w = np.array([0.0, 0.0, 1.0])
    third_w = np.cross(a_w, d_w)
    R_desired = np.column_stack([a_w, d_w, third_w]) @ np.column_stack([a, d, third]).T
    # to quaternion (w, x, y, z)
    m = R_desired
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2.0
        q = np.array([0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s])
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        q = np.array([(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s])
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        q = np.array([(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s])
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        q = np.array([(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s])
    q = q / np.linalg.norm(q)

    holds = {
        "td-x": top_down_quaternion("x"),
        "td-y": top_down_quaternion("y"),
        "measured": q,
    }
    for name, hold in holds.items():
        arm.teleport_joints(np.asarray(q_grasp, dtype=float))
        SimulationManager.step(steps=10)
        arm.hold_quaternion = np.asarray(hold, dtype=float)
        arm.sync_command_to_measured()
        worst = 0.0
        for _ in range(400):
            arm.ik_step(arm.tcp_target_for_jaw(target))
            SimulationManager.step(steps=1)
            err = float(np.linalg.norm(quaternion_error(hold, arm.tcp_pose()[1])))
            worst = max(worst, err)
        jaw_now = np.asarray(arm.jaw_centre(), dtype=float)
        pos_err = float(np.linalg.norm(jaw_now - target))
        att = quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
        att_err = float(np.linalg.norm(quaternion_error(hold, arm.tcp_pose()[1])))
        say(
            f"hold {name:8s} pos_err={pos_err * 1e3:6.1f} mm att_err={np.degrees(att_err):6.2f} deg "
            f"(worst {np.degrees(worst):6.2f})  closing(world)={np.round(att.T @ a_local, 3)} "
            f"down(world)={np.round(att[:, 2], 3)}"
        )
        for pad, box in pad_frame(stage, arm).items():
            if box:
                say(f"   {pad}: close[{box['close'][0]:+.3f},{box['close'][1]:+.3f}] "
                    f"down[{box['down'][0]:+.3f},{box['down'][1]:+.3f}]")

    # ---- 3. grasp with the best attitude and the derived standoff -----
    spawner = FruitSpawner(stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    SimulationManager.step(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    picks = {}
    for sample in spawner.samples:
        picks.setdefault(sample.category, sample)

    from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent

    def pinch_extent(sample, quat) -> float:
        # the closing axis is the hand's -Y (measured, `hand_frame.log`), i.e.
        # rotation column 1 - column 0 is the 76 mm plate width.
        shape = FRUIT_SHAPES.get(sample.category)
        if shape is None:
            return float(sample.diameter)
        axis_world = quat_matrix(quat)[:, 1]
        _, fruit_quat = spawner.fruit_pose(sample)
        local_axis = quat_matrix(fruit_quat).T @ axis_world
        return float(axis_extent(shape, float(sample.diameter), local_axis))

    hold_name = os.environ.get("PROBE_HOLD", "td-x")
    hold = holds[hold_name]
    dz_values = [float(v) for v in os.environ.get("PROBE_DZ", "0.025,0.035,0.045").split(",")]
    # the task uses a **fixed** jaw height, not a per-fruit standoff: `PROBE_JAW_Z`
    # overrides dz with `jaw_z = PROBE_JAW_Z` (world), which is what
    # `grasp_clearance` 0.070 = 1.240 m is.
    fixed_z = os.environ.get("PROBE_JAW_Z", "").strip()
    if fixed_z:
        dz_values = [float(fixed_z) - float(belt_top)]
        say(f"fixed jaw z={fixed_z} -> dz={dz_values[0]:+.4f} (per fruit adjusted below)")
    for dz in dz_values:
      for category in os.environ.get("PROBE_FRUITS", "apple,orange,strawberry,lychee").split(","):
        sample = picks.get(category)
        if sample is None:
            continue
        d = float(sample.diameter)
        seat = np.array([cfg.pick_x, cfg.pick_y, belt_top + d / 2.0])
        spawner.place(sample, seat)
        sample.held = True
        SimulationManager.step(steps=30)
        arm.teleport_joints(np.asarray(q_grasp, dtype=float))
        SimulationManager.step(steps=40)
        arm.hold_quaternion = np.asarray(hold, dtype=float)
        arm.sync_command_to_measured()
        for _ in range(240):
            fruit = np.asarray(spawner.position(sample), dtype=float)
            goal_z = float(fixed_z) if fixed_z else fruit[2] + dz
            arm.ik_step(arm.tcp_target_for_jaw(np.array([fruit[0], fruit[1], goal_z])))
            SimulationManager.step(steps=1)
        fruit = np.asarray(spawner.position(sample), dtype=float)
        jaw = np.asarray(arm.jaw_centre(), dtype=float)
        quat = np.asarray(arm.tcp_pose()[1], dtype=float)
        width = pinch_extent(sample, quat)
        value = arm.gripper_value_for_separation(width * 0.98)
        for cmd in min_jerk_ramp(arm.OPEN, value, 60):
            fruit = np.asarray(spawner.position(sample), dtype=float)
            arm.ik_step(arm.tcp_target_for_jaw(fruit + np.array([0.0, 0.0, dz])))
            arm.set_gripper(float(cmd))
            SimulationManager.step(steps=1)
            SimulationManager.step(steps=1)
        for _ in range(60):
            SimulationManager.step(steps=1)
        sep = arm.jaw_separation()
        start = np.asarray(arm.jaw_centre(), dtype=float).copy()
        rel0 = quat_matrix(quat).T @ (fruit - jaw)
        slip = 0.0
        for lift in min_jerk_ramp(0.0, 0.10, 200):
            arm.ik_step(arm.tcp_target_for_jaw(start + np.array([0.0, 0.0, float(lift)])))
            SimulationManager.step(steps=1)
            now = np.asarray(spawner.position(sample), dtype=float)
            rot_now = quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
            slip = max(slip, float(np.linalg.norm(rot_now.T @ (now - arm.jaw_centre()) - rel0)))
        for _ in range(60):
            SimulationManager.step(steps=1)
        after = np.asarray(spawner.position(sample), dtype=float)
        lifted = float(after[2] - fruit[2])
        say(
            f"grasp {category:11s} d={d * 1000:5.1f} hold={hold_name} dz={dz * 1000:+.0f}mm "
            f"width={width * 1000:5.1f} sep={sep * 1000:5.1f} "
            f"lift={lifted * 1000:7.1f}mm slip={slip * 1000:6.1f}mm "
            f"{'HOLD' if lifted >= 0.03 else 'DROP'}"
        )
        for cmd in min_jerk_ramp(value, arm.OPEN, 30):
            arm.set_gripper(float(cmd))
            SimulationManager.step(steps=1)
        arm.hold_quaternion = None
        spawner.place(sample, np.array([1.9, 0.0, 0.4]))
        SimulationManager.step(steps=20)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
