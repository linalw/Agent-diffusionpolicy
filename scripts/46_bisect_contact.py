"""One-run bisect: which property of the fruit kills gripper contact?

    $ISAAC_SIM_DIR/python.sh scripts/46_bisect_contact.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, UsdGeom, UsdPhysics, UsdShade

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

CONFIG = json.load(open("configs/waypoints.json"))


def sphere(stage, path, radius, center):
    prim = UsdGeom.Sphere.Define(stage, path)
    prim.GetRadiusAttr().Set(radius)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in center]))
    UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
    UsdPhysics.RigidBodyAPI.Apply(prim.GetPrim())
    UsdPhysics.MassAPI.Apply(prim.GetPrim()).CreateMassAttr().Set(0.05)
    return prim.GetPrim()


def with_visual_material(stage, prim, path):
    mat = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, f"{path}/s")
    sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.5, 0.1, 0.1))
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(mat)


def with_physics_material(stage, prim, path):
    mat = UsdShade.Material.Define(stage, path)
    api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    api.CreateStaticFrictionAttr().Set(0.6)
    api.CreateDynamicFrictionAttr().Set(0.6)
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(mat, UsdShade.Tokens.weakerThanDescendants, "physics")


def with_physx_rb(prim):
    PhysxSchema.PhysxRigidBodyAPI.Apply(prim)


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    arm = ArmController(scene, "left")

    def fresh():
        arm.teleport_joints(np.asarray(CONFIG["arms"]["left"]["grasp"], dtype=float))
        arm.set_gripper(arm.OPEN)
        for _ in range(80):
            SimulationManager.step(steps=1)
        return arm.jaw_centre().copy()

    def close(label):
        before = arm.jaw_separation()
        for value in np.linspace(arm.OPEN, 0.0, 30):
            arm.set_gripper(float(value))
            SimulationManager.step(steps=2)
        for _ in range(80):
            SimulationManager.step(steps=1)
        say(f"  {label:34s} {before*100:5.2f} -> {arm.jaw_separation()*100:5.2f} cm")

    cases = {}
    jaw = fresh()
    cases["1 plain sphere"] = sphere(scene.stage, "/World/T1", 0.028, (jaw[0], jaw[1], jaw[2] - 0.04))
    cases["2 + PhysxRigidBodyAPI"] = sphere(scene.stage, "/World/T2", 0.028, (jaw[0], jaw[1], jaw[2] - 0.04))
    with_physx_rb(cases["2 + PhysxRigidBodyAPI"])
    cases["3 + visual material"] = sphere(scene.stage, "/World/T3", 0.028, (jaw[0], jaw[1], jaw[2] - 0.04))
    with_visual_material(scene.stage, cases["3 + visual material"], "/World/M3")
    cases["4 + physics material"] = sphere(scene.stage, "/World/T4", 0.028, (jaw[0], jaw[1], jaw[2] - 0.04))
    with_physics_material(scene.stage, cases["4 + physics material"], "/World/M4")
    cases["5 + both materials"] = sphere(scene.stage, "/World/T5", 0.028, (jaw[0], jaw[1], jaw[2] - 0.04))
    with_visual_material(scene.stage, cases["5 + both materials"], "/World/M5")
    with_physics_material(scene.stage, cases["5 + both materials"], "/World/M5p")

    from isaacsim.core.experimental.prims import RigidPrim

    for label, prim in cases.items():
        jaw = fresh()
        xf = UsdGeom.Xformable(prim)
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(float(jaw[0]), float(jaw[1]), float(jaw[2]) - 0.04))
        UsdPhysics.RigidBodyAPI(prim).CreateKinematicEnabledAttr().Set(False)
        # Hold the object on the jaw centre line: the belt otherwise carries it
        # away before the fingers close, which invalidates the test.
        rp = RigidPrim(str(prim.GetPath()))
        for _ in range(60):
            rp.set_velocities(linear_velocities=[[0.0, 0.0, 0.0]],
                              angular_velocities=[[0.0, 0.0, 0.0]])
            SimulationManager.step(steps=1)
        rp = RigidPrim(str(prim.GetPath()))
        now = np.asarray(rp.get_world_poses()[0].numpy())[0]
        say(f"  {label:34s} object at {np.round(now, 3).tolist()} jaw={np.round(arm.jaw_centre(), 3).tolist()}")
        close(label)

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
