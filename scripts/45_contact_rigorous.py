"""Rigorous finger-contact test: re-command the arm before every case.

    $ISAAC_SIM_DIR/python.sh scripts/45_contact_rigorous.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import UsdPhysics

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene, _define_box, _set_color
from isaacsim.core.simulation_manager import SimulationManager

CONFIG = json.load(open("configs/waypoints.json"))


def fresh_pose(arm):
    """Re-command the grasp pose and return the jaw centre."""
    arm.teleport_joints(np.asarray(CONFIG["arms"]["left"]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)
    return arm.jaw_centre().copy()


def close_and_report(arm, label):
    before = arm.jaw_separation()
    for value in np.linspace(arm.OPEN, 0.0, 30):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(80):
        SimulationManager.step(steps=1)
    say(f"{label:28s} sep {before*100:5.2f} -> {arm.jaw_separation()*100:5.2f} cm")


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    # Author the fruit BEFORE play(): rigid bodies created at runtime may not get
    # their collision shapes cooked, which would explain fruit passing through the
    # gripper while runtime boxes sometimes do not.
    spawner = FruitSpawner(scene.stage, cfg, seed=4)
    spawner.create_pool()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()

    arm = ArmController(scene, "left")

    for tag, size in (("box y=0.055", (0.06, 0.055, 0.055)), ("box y=0.075", (0.06, 0.075, 0.06))):
        jaw = fresh_pose(arm)
        box = _define_box(scene.stage, "/World/TB", size=size,
                          center=(float(jaw[0]), float(jaw[1]), float(jaw[2]) - 0.040))
        UsdPhysics.CollisionAPI.Apply(box.GetPrim())
        _set_color(box, (0.9, 0.4, 0.1))
        app_utils.update_app(steps=40)
        say(f"{tag}: jaw={np.round(jaw, 3).tolist()}")
        close_and_report(arm, tag)
        scene.stage.RemovePrim("/World/TB")

    for sample in spawner.samples[:3]:
        jaw = fresh_pose(arm)
        spawner.place(sample, np.array([float(jaw[0]), float(jaw[1]), float(jaw[2]) - 0.040]))
        sample.held = True
        if sample not in spawner.active:
            spawner.active.append(sample)
        for _ in range(40):
            SimulationManager.step(steps=1)
        p = spawner.position(sample)
        close_and_report(arm, f"{sample.category} d={sample.diameter*100:.1f}cm")
        say(f"    moved {np.linalg.norm(spawner.position(sample) - p) * 1000:.1f} mm")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
