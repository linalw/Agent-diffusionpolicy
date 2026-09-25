"""Track a moving fruit with differential IK, close the gripper, lift, and report tactile.

    $ISAAC_SIM_DIR/python.sh scripts/15_pick_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile

DT = 1.0 / 120.0


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    scene.start(physics_dt=DT, warmup_steps=60)
    scene.report_robot()

    tactile = GripperTactile()
    tactile.attach(scene.robot)

    spawner = FruitSpawner(scene.stage, cfg, seed=11)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()
    spawner.prime(count=3)

    left = ArmController(scene, "left")
    right = ArmController(scene, "right")
    for arm in (left, right):
        arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=60)

    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(f"belt top z={belt_top:.3f}, pick window y={cfg.pick_y_range}")

    # Pick the live fruit closest to the middle of the pick window.
    states = spawner.state()
    if not states:
        say("no fruit to pick")
        app_utils.pause()
        return 1
    target = min(states, key=lambda s: abs(s["position"][1]))
    say(f"target: {target['category']} d={target['diameter'] * 100:.1f}cm at {np.round(target['position'], 3).tolist()}")
    sample = next(s for s in spawner.samples if s.index == target["index"])
    arm = left if target["position"][1] >= 0 else right
    say(f"using {arm.spec.side} arm")

    grasp_z = belt_top + target["diameter"] / 2.0 + 0.004

    # 1. Move above the predicted intercept.
    for _ in range(360):
        pos = spawner.position(sample)
        vel = spawner.velocity(sample)
        aim = pos + vel * 0.30
        goal = np.array([aim[0], aim[1], grasp_z + 0.12])
        arm.ik_step(goal)
        app_utils.update_app(steps=1)
        if np.linalg.norm(arm.tcp_position() - goal) < 0.02:
            break
    say(f"above target: tcp={np.round(arm.tcp_position(), 3).tolist()} target={np.round(goal, 3).tolist()}")

    # 2. Track and descend onto the moving fruit.
    min_horizontal = float("inf")
    for step in range(420):
        pos = spawner.position(sample)
        vel = spawner.velocity(sample)
        aim = pos + vel * 0.05
        goal = np.array([aim[0], aim[1], grasp_z])
        arm.ik_step(goal)
        app_utils.update_app(steps=1)
        tcp = arm.tcp_position()
        horizontal = float(np.linalg.norm(tcp[:2] - pos[:2]))
        min_horizontal = min(min_horizontal, horizontal)
        if step % 60 == 0:
            say(
                f"  descend step={step} tcp={np.round(tcp, 3).tolist()} "
                f"fruit={np.round(pos, 3).tolist()} horiz_err={horizontal:.4f}"
            )
        if horizontal < 0.012 and abs(tcp[2] - grasp_z) < 0.02:
            break
    say(f"descended; min horizontal error = {min_horizontal:.4f} m; tactile: {tactile.summary()}")

    # 3. Close the gripper.
    for opening in np.linspace(arm.OPEN, 0.006, 30):
        arm.set_gripper(float(opening))
        app_utils.update_app(steps=4)
    app_utils.update_app(steps=60)
    say(f"gripper closed to {arm.finger_opening():.4f}; tactile: {tactile.summary()}")

    # 4. Lift and check that the fruit follows the gripper.
    fruit_before = spawner.position(sample).copy()
    lift_goal = arm.tcp_position() + np.array([0.0, 0.0, 0.15])
    arm.move_to(lift_goal, max_steps=240, tolerance=0.01)
    app_utils.update_app(steps=60)
    fruit_after = spawner.position(sample)
    say(f"lift: fruit before={np.round(fruit_before, 3).tolist()} after={np.round(fruit_after, 3).tolist()}")
    say(f"fruit raised by {fruit_after[2] - fruit_before[2]:+.4f} m; tactile: {tactile.summary()}")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
