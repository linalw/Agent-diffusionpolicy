"""Where, relative to `jaw_centre`, do the pads actually close on a fruit?

Every placement rule so far was inferred (link origins, bounding boxes,
projected point clouds) and every inference disagreed with the next. This probe
measures the answer directly: a *kinematic* sphere of a given diameter is parked
at the fruit's resting height, and the gripper closes. Blocking means the pads
are on it; closing to the fully-closed separation means they are not.

    $ISAAC_SIM_DIR/python.sh scripts/84_offset_map.py
    FRUIT_WAYPOINTS=configs/waypoints_oriented.json FRUIT_D=0.055
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

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene, _add_physics_material, _set_color
from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

CONFIG = json.load(open(os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints_oriented.json"),
                        encoding="utf-8"))
DIAMETER = float(os.environ.get("FRUIT_D", "0.055"))


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    path = "/World/Probe"
    sphere = UsdGeom.Sphere.Define(scene.stage, path)
    sphere.GetRadiusAttr().Set(DIAMETER / 2.0)
    xf = UsdGeom.Xformable(sphere)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -3.0))
    xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    UsdPhysics.CollisionAPI.Apply(sphere.GetPrim())
    body = UsdPhysics.RigidBodyAPI.Apply(sphere.GetPrim())
    body.CreateKinematicEnabledAttr().Set(True)
    _add_physics_material(sphere.GetPrim(), 0.8, 0.8, 0.0)
    _set_color(sphere, (0.1, 0.9, 0.2))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    rigid = RigidPrim(path)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    seat = belt_top + cfg.nest_height
    say(f"belt_top={belt_top:.3f} seat={seat:.3f} diameter={DIAMETER * 100:.1f}cm "
        f"nest={cfg.nest_height}")

    for side in ("left", "right"):
        arm = ArmController(scene, side)
        base = np.array([cfg.pick_x, 0.0, seat + DIAMETER / 2.0 + 0.003])
        arm.teleport_joints(np.asarray(CONFIG["arms"][side]["grasp"], dtype=float))
        arm.set_gripper(arm.OPEN)
        for _ in range(60):
            SimulationManager.step(steps=1)
        _c, residual = arm.solve_to(base, iterations=600, tolerance=0.004)
        if residual > 0.012:
            _c, residual = arm.solve_to(base, iterations=600, tolerance=0.004,
                                        restarts=4, seed=7)
        for _ in range(30):
            SimulationManager.step(steps=1)
        left_f, right_f = arm.jaw_positions()
        centre = (np.asarray(left_f, dtype=float) + np.asarray(right_f, dtype=float)) / 2.0
        approach = arm.tcp_position() - centre
        approach = approach / max(float(np.linalg.norm(approach)), 1e-9)
        say(f"=== {side}: jaw={np.round(centre, 4).tolist()} residual={residual * 1000:.1f}mm "
            f"approach={np.round(approach, 3).tolist()}")

        # Baseline: close with nothing between the pads.
        rigid.set_world_poses(positions=[[0.0, 0.0, -2.0]], orientations=[[1.0, 0.0, 0.0, 0.0]])
        for _ in range(20):
            SimulationManager.step(steps=1)
        for value in np.linspace(arm.OPEN, 0.0, 40):
            arm.set_gripper(float(value))
            SimulationManager.step(steps=2)
        for _ in range(40):
            SimulationManager.step(steps=1)
        baseline = arm.jaw_separation()
        say(f"  baseline (nothing between the jaws): closed separation {baseline * 100:.2f} cm "
            f"finger_q={np.round(arm.dof_positions()[arm.finger_dofs], 4).tolist()}")

        say("  offset along the approach axis (negative = upstream of jaw centre):")
        for offset in np.arange(-0.04, 0.045, 0.005):
            pos = centre + approach * float(offset)
            pos[2] = seat + DIAMETER / 2.0
            rigid.set_world_poses(positions=[pos.tolist()], orientations=[[1.0, 0.0, 0.0, 0.0]])
            for _ in range(20):
                SimulationManager.step(steps=1)
            for value in np.linspace(arm.OPEN, 0.0, 40):
                arm.set_gripper(float(value))
                SimulationManager.step(steps=2)
            for _ in range(40):
                SimulationManager.step(steps=1)
            sep = arm.jaw_separation()
            blocked = sep > baseline + 0.004
            say(f"    {offset * 100:+6.1f}cm  pos=({pos[0]:.3f},{pos[1]:+.3f},{pos[2]:.3f})  "
                f"sep={sep * 100:5.2f}cm  {'BLOCKED' if blocked else 'passed'}")
        arm.set_gripper(arm.OPEN)
        for _ in range(40):
            SimulationManager.step(steps=1)
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
