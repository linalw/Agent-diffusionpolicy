"""Per-step trace of one grasp: where exactly does the hold fail?

    $ISAAC_SIM_DIR/python.sh scripts/78_hold_trace.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene, _add_physics_material
from fruit_sorting.tactile import GripperTactile
from isaacsim.core.simulation_manager import SimulationManager

CONFIG = json.load(open(os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints_oriented.json"),
                        encoding="utf-8"))
SIDE = os.environ.get("FRUIT_SIDE", "left")


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    for which in ("left", "right"):
        prim = scene.stage.GetPrimAtPath(f"/World/OpenArm/openarm_{SIDE}_{which}_finger")
        if prim.IsValid():
            _add_physics_material(prim, 1.2, 1.2, 0.0)
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    spawner = FruitSpawner(scene.stage, cfg, seed=4)
    spawner.create_pool()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    tactile.refresh()
    spawner.refresh_rigids()
    spawner.reset()
    if spawner.belt is not None:
        spawner.belt.stop()
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0

    target_d = float(os.environ.get("FRUIT_D", "0.055"))
    sample = min(spawner.samples, key=lambda s: abs(s.diameter - target_d))
    d = sample.diameter
    say(f"sample {sample.category} d={d * 100:.2f}cm m={sample.mass * 1000:.0f}g "
        f"mu={sample.friction:.2f}")

    arm = ArmController(scene, SIDE)
    other = ArmController(scene, "right" if SIDE == "left" else "left")
    target = np.array([cfg.pick_x, 0.0, belt_top + d / 2.0 + 0.003])
    arm.teleport_joints(np.asarray(CONFIG["arms"][SIDE]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(60):
        SimulationManager.step(steps=1)
    _cfg, residual = arm.solve_to(target, iterations=500, tolerance=0.004)
    if residual > 0.010:
        _cfg, residual = arm.solve_to(target, iterations=500, tolerance=0.004,
                                      restarts=4, seed=7)
    jaw = arm.jaw_centre().copy()
    say(f"grasp pose: jaw={np.round(jaw, 4).tolist()} residual={residual * 1000:.1f}mm "
        f"target={np.round(target, 4).tolist()}")
    spawner.place(sample, np.array([jaw[0], jaw[1], belt_top + d / 2.0]))
    sample.held = True
    say(f"other arm jaw={np.round(other.jaw_centre(), 4).tolist()} "
        f"tcp={np.round(other.tcp_position(), 4).tolist()}")
    for _ in range(40):
        SimulationManager.step(steps=1)
    say(f"after settle: fruit={np.round(spawner.position(sample), 4).tolist()} "
        f"other arm jaw={np.round(other.jaw_centre(), 4).tolist()}")

    grip = arm.gripper_value_for_separation(d * 0.99)
    say(f"--- closing to {grip:.4f} (face target {d * 0.99 * 100:.2f}cm) ---")
    for i, value in enumerate(np.linspace(arm.OPEN, grip, 40)):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
        if i % 8 == 0:
            pos = spawner.position(sample)
            say(f"  close {i:2d} cmd={value:.4f} jaw_sep={arm.jaw_separation() * 100:5.2f}cm "
                f"fruit=({pos[0]:.3f},{pos[1]:+.3f},{pos[2]:.4f}) "
                f"force={tactile.read()[SIDE].normal_force:7.2f}N")
    for i in range(60):
        SimulationManager.step(steps=1)
        if i % 20 == 0:
            pos = spawner.position(sample)
            say(f"  settle {i:2d} jaw_sep={arm.jaw_separation() * 100:5.2f}cm "
                f"fruit_z={pos[2]:.4f} force={tactile.read()[SIDE].normal_force:7.2f}N")

    say("--- lift ---")
    goal = target + [0.0, 0.0, 0.12]
    for i in range(240):
        step_target = target + [0.0, 0.0, 0.12 * (i + 1) / 240.0]
        arm.ik_step(arm.tcp_target_for_jaw(step_target))
        SimulationManager.step(steps=1)
        if i % 30 == 0:
            pos = spawner.position(sample)
            say(f"  lift {i:3d} jaw_z={arm.jaw_centre()[2]:.4f} fruit_z={pos[2]:.4f} "
                f"fruit=({pos[0]:.3f},{pos[1]:+.3f}) "
                f"force={tactile.read()[SIDE].normal_force:7.2f}N")
    for i in range(40):
        arm.ik_step(arm.tcp_target_for_jaw(goal))
        SimulationManager.step(steps=1)
    pos = spawner.position(sample)
    say(f"end: jaw_z={arm.jaw_centre()[2]:.4f} fruit_z={pos[2]:.4f} "
        f"lift={pos[2] - (belt_top + d / 2.0):+.4f} m")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
