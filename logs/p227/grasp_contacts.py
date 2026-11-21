#!/usr/bin/env python3
"""P227m: is the Panda's close touching the fruit at all, and what is in the way?

    FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/grasp_contacts.py

P227i/l fixed the two measurement-derived constants (the Panda's pad faces are
+6 mm at q=0, and the top-down attitude is the OpenArm's `td-x` form at 0.11 deg)
and the close now presses the *faces* into the fruit by the 2 % squeeze - yet
12/12 cells still drop. So this probe attaches contact readers to the Panda's
own finger links (pre-play, the shipped `GripperTactile` way) and prints, per
tick of the close and the lift: each finger's normal force and contact count,
the fruit's position, the jaw centre, and every link's world origin.

It also dumps each collision mesh under `panda_hand` separately - the palm's
bounding box reaches 47 mm below the jaw plane, which on a 65 mm fruit leaves
only ~18 mm of finger engagement and is the leading candidate for "the palm, not
the pads, is what the fruit meets".

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
from pxr import Usd, UsdGeom, UsdPhysics  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.control import ArmController, arm_specs  # noqa: E402
from fruit_sorting.fruits import FruitSpawner  # noqa: E402
from fruit_sorting.motion import min_jerk_ramp, top_down_quaternion  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402
from fruit_sorting.tactile import GripperTactile  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

DT = 1.0 / 120.0
os.environ.setdefault("FRUIT_NO_SLEEP", "1")


def say(text: str) -> None:
    print(f"[fruit] [gc] {text}", flush=True)


def quat_matrix(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def collision_meshes(stage, path: str) -> None:
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    prim = stage.GetPrimAtPath(path)
    say(f"collision meshes under {path}:")
    for sub in Usd.PrimRange(prim, proxies):
        if sub.GetTypeName() != "Mesh":
            continue
        col = sub.HasAPI(UsdPhysics.CollisionAPI) and bool(
            UsdPhysics.CollisionAPI(sub).GetCollisionEnabledAttr().Get()
        )
        box = UsdGeom.Boundable(sub).ComputeWorldBound(
            Usd.TimeCode.Default(), UsdGeom.Tokens.default_
        ).ComputeAlignedRange()
        mn = np.array(box.GetMin(), dtype=float)
        mx = np.array(box.GetMax(), dtype=float)
        say(
            f"  {sub.GetPath()} collider={col} size={np.round(mx - mn, 4)} "
            f"z=[{mn[2]:.3f},{mx[2]:.3f}]"
        )


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    spec = arm_specs()[0]
    tactile = GripperTactile()
    tactile.attach(
        stage=scene.stage,
        finger_links={"left": list(spec.finger_link_names)},
        robot_root=spec.link_root,
    )
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()
    # a *static* grasp gate: the moving belt drags the fruit ~0.12 m during the
    # close, which mixes the catch problem into the grasp question.
    # `SortingScene.step` is `update_app`, so the belt's own `step()` (which is
    # where a target speed reaches the collider) never runs here - write the
    # surface velocity directly.
    scene.belt.set_speed(0.0)
    scene.belt.speed = 0.0
    scene.belt._apply_speed(0.0)
    belt_top = float(scene.belt.belt_top)
    stage = scene.stage
    collision_meshes(stage, f"{spec.link_root}/{spec.tcp_link}")

    spawner = FruitSpawner(stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    SimulationManager.step(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)

    picks = {}
    for sample in spawner.samples:
        picks.setdefault(sample.category, sample)
    category = os.environ.get("PROBE_FRUIT", "apple")
    sample = picks[category]
    d = float(sample.diameter)
    seat = np.array([cfg.pick_x, cfg.pick_y, belt_top + d / 2.0])
    spawner.place(sample, seat)
    sample.held = True
    SimulationManager.step(steps=30)

    target = np.array([cfg.pick_x, cfg.pick_y, belt_top + float(cfg.grasp_clearance)])
    q0 = np.asarray(arm.joint_positions(), dtype=float)
    arm.teleport_joints(q0)
    arm.hold_quaternion = None
    arm.solve_to(np.array([target[0], target[1], target[2] + 0.12]),
                 iterations=600, tolerance=0.006, restarts=1, move_on_fail=True)
    SimulationManager.step(steps=5)
    q_grasp, _ = arm.solve_to(target, iterations=1500, tolerance=0.004, restarts=2,
                              move_on_fail=True)
    SimulationManager.step(steps=5)

    hold = top_down_quaternion("x")
    arm.teleport_joints(np.asarray(q_grasp, dtype=float))
    SimulationManager.step(steps=40)
    arm.hold_quaternion = np.asarray(hold, dtype=float)
    arm.sync_command_to_measured()
    dz = float(os.environ.get("PROBE_DZ", "0.042"))
    for _ in range(240):
        fruit = np.asarray(spawner.position(sample), dtype=float)
        arm.ik_step(arm.tcp_target_for_jaw(fruit + np.array([0.0, 0.0, dz])))
        SimulationManager.step(steps=1)
    fruit = np.asarray(spawner.position(sample), dtype=float)
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    say(f"fruit={np.round(fruit, 4)} d={d * 1000:.1f}mm jaw={np.round(jaw, 4)} "
        f"dz_real={(jaw - fruit)[2] * 1000:+.1f}mm")
    for name in spec.finger_link_names:
        lp = np.asarray(arm._finger_prims[list(spec.finger_link_names).index(name)].get_world_poses()[0].numpy()[0])
        say(f"  {name} origin={np.round(lp, 4)}")
    reading = tactile.read()["left"]
    say(f"  pre-close tactile: force={reading.normal_force:.2f} contacts={reading.contact_count} "
        f"per-pad={ {k: round(v, 2) for k, v in reading.fingertip_forces.items()} }")

    from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent

    quat = np.asarray(arm.tcp_pose()[1], dtype=float)
    shape = FRUIT_SHAPES.get(sample.category)
    axis_world = quat_matrix(quat)[:, 1]
    _, fruit_quat = spawner.fruit_pose(sample)
    local_axis = quat_matrix(fruit_quat).T @ axis_world
    width = float(axis_extent(shape, d, local_axis)) if shape else d
    value = arm.gripper_value_for_separation(width * 0.98)
    say(f"  close: width={width * 1000:.1f}mm q_cmd={value * 1000:.2f}mm "
        f"faces={(2 * value + 0.006) * 1000:.1f}mm")
    for i, cmd in enumerate(min_jerk_ramp(arm.OPEN, value, 60)):
        fruit = np.asarray(spawner.position(sample), dtype=float)
        arm.ik_step(arm.tcp_target_for_jaw(fruit + np.array([0.0, 0.0, dz])))
        arm.set_gripper(float(cmd))
        SimulationManager.step(steps=1)
        SimulationManager.step(steps=1)
        if i % 10 == 0 or i >= 58:
            reading = tactile.read()["left"]
            say(
                f"  close[{i:2d}] q={arm.finger_opening() * 1000:5.1f}mm "
                f"sep={arm.jaw_separation() * 1000:5.1f}mm "
                f"fruit={np.round(fruit, 3)} force={reading.normal_force:5.2f} "
                f"n={reading.contact_count} pads="
                f"{[round(v, 2) for v in reading.fingertip_forces.values()]}"
            )
    for i in range(60):
        SimulationManager.step(steps=1)
        if i % 15 == 0:
            reading = tactile.read()["left"]
            fruit = np.asarray(spawner.position(sample), dtype=float)
            say(f"  hold[{i:2d}] fruit={np.round(fruit, 3)} force={reading.normal_force:5.2f} "
                f"n={reading.contact_count}")
    start = np.asarray(arm.jaw_centre(), dtype=float).copy()
    fruit0 = np.asarray(spawner.position(sample), dtype=float)
    for i, lift in enumerate(min_jerk_ramp(0.0, 0.10, 200)):
        arm.ik_step(arm.tcp_target_for_jaw(start + np.array([0.0, 0.0, float(lift)])))
        SimulationManager.step(steps=1)
        if i % 40 == 0:
            reading = tactile.read()["left"]
            fruit = np.asarray(spawner.position(sample), dtype=float)
            say(f"  lift[{i:3d}] jaw_z={arm.jaw_centre()[2]:.3f} fruit_z={fruit[2]:.3f} "
                f"force={reading.normal_force:5.2f} n={reading.contact_count}")
    fruit = np.asarray(spawner.position(sample), dtype=float)
    say(f"result: lifted={(fruit[2] - fruit0[2]) * 1000:+.1f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
