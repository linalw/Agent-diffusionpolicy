"""Author a plain sphere exactly like the working box, next to a real fruit.

    $ISAAC_SIM_DIR/python.sh scripts/44_sphere_vs_fruit.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Gf, UsdGeom, UsdPhysics

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager


def close_and_report(arm, label):
    before = arm.jaw_separation()
    for value in np.linspace(arm.OPEN, 0.0, 30):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(80):
        SimulationManager.step(steps=1)
    say(f"{label:26s} sep {before*100:5.2f}cm -> {arm.jaw_separation()*100:5.2f}cm")


def main() -> int:
    with open("configs/waypoints.json", encoding="utf-8") as fh:
        waypoints = json.load(fh)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    spawner = FruitSpawner(scene.stage, cfg, seed=4)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()

    arm = ArmController(scene, "left")
    arm.teleport_joints(np.asarray(waypoints["arms"]["left"]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)
    jaw = arm.jaw_centre()
    y = float(jaw[1])
    z = float(jaw[2]) - 0.040

    # A: real fruit, resized to 5 cm
    fruit = spawner.samples[1]
    d = 0.05
    fruit.diameter = d
    UsdGeom.Sphere(scene.stage.GetPrimAtPath(fruit.prim_path)).GetRadiusAttr().Set(d / 2.0)
    UsdPhysics.MassAPI(scene.stage.GetPrimAtPath(fruit.prim_path)).GetMassAttr().Set(0.05)
    app_utils.update_app(steps=20)
    spawner.place(fruit, np.array([float(jaw[0]), y, z]))
    fruit.held = True
    if fruit not in spawner.active:
        spawner.active.append(fruit)
    for _ in range(40):
        SimulationManager.step(steps=1)
    say(f"fruit authored by FruitSpawner at {np.round(spawner.position(fruit), 4).tolist()}")
    close_and_report(arm, "A fruit (FruitSpawner)")

    # B: plain sphere authored by hand, identical to the box that DID block
    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)
    sph = UsdGeom.Sphere.Define(scene.stage, "/World/PlainSphere")
    sph.GetRadiusAttr().Set(0.025)
    xf = UsdGeom.Xformable(sph)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(float(jaw[0]), y, z))
    UsdPhysics.CollisionAPI.Apply(sph.GetPrim())
    UsdPhysics.RigidBodyAPI.Apply(sph.GetPrim())
    UsdPhysics.MassAPI.Apply(sph.GetPrim()).CreateMassAttr().Set(0.05)
    app_utils.update_app(steps=40)
    say("plain sphere authored at the same place (see A vs B)")
    close_and_report(arm, "B plain sphere")

    # C: plain sphere authored far away, then TELEPORTED to the jaw
    # (my fruit pipeline teleports bodies constantly)
    scene.stage.RemovePrim("/World/PlainSphere")
    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)
    sph2 = UsdGeom.Sphere.Define(scene.stage, "/World/PlainSphere2")
    sph2.GetRadiusAttr().Set(0.025)
    xf2 = UsdGeom.Xformable(sph2)
    xf2.ClearXformOpOrder()
    xf2.AddTranslateOp().Set(Gf.Vec3d(5.0, 0.0, 0.5))
    UsdPhysics.CollisionAPI.Apply(sph2.GetPrim())
    UsdPhysics.RigidBodyAPI.Apply(sph2.GetPrim())
    UsdPhysics.MassAPI.Apply(sph2.GetPrim()).CreateMassAttr().Set(0.05)
    app_utils.update_app(steps=40)
    from isaacsim.core.experimental.prims import RigidPrim
    rp = RigidPrim("/World/PlainSphere2")
    rp.set_world_poses(positions=[[float(jaw[0]), y, z]], orientations=[[1.0, 0.0, 0.0, 0.0]])
    rp.set_velocities(linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]])
    for _ in range(60):
        SimulationManager.step(steps=1)
    now = np.asarray(rp.get_world_poses()[0].numpy())[0]
    say(f"teleported sphere now at {np.round(now, 4).tolist()}")
    close_and_report(arm, "C plain sphere TELEPORTED")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
