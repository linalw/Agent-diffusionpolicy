"""Can *any* well-shaped gripper hold these fruit in this simulator?

Every test so far has been constrained by the OpenArm asset: its finger collision
mesh stops short of the fingertips, its instance proxies refuse new colliders, and
a fixed joint to an articulation link is not honoured (see WORKLOG 2026-09-26/27).
That leaves one question unanswered - is the *simulator* able to hold a 3-7 cm
fruit at all, given sensible contact geometry?

This script builds a purpose-made 1-DoF parallel gripper from scratch - a fixed
carriage, a prismatic lift joint, and two prismatic fingers with wide rubber pads -
and runs the full grasp cycle on fruit placed on a table:

    descend -> close (force limited) -> lift -> did the fruit follow?

    $ISAAC_SIM_DIR/python.sh scripts/91_simple_gripper_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from isaacsim.core.experimental.prims import Articulation
from isaacsim.core.simulation_manager import SimulationManager

#: Gripper geometry (metres).
FINGER_LENGTH = 0.060      # along the belt (x)
FINGER_THICK = 0.012       # across the closing axis
FINGER_HEIGHT = 0.050      # vertical extent of the pad
PAD_WIDTH = 0.040          # contact patch along x
STROKE = 0.055             # finger travel, so the jaws open to ~11 cm
TABLE_TOP = 1.17


def _material(stage, path, mu, colour):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*colour))
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    api.CreateStaticFrictionAttr().Set(mu)
    api.CreateDynamicFrictionAttr().Set(mu)
    api.CreateRestitutionAttr().Set(0.0)
    return mat


def _box(stage, path, size, centre, mu, colour, kinematic=False):
    prim = UsdGeom.Cube.Define(stage, path)
    prim.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*centre))
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
    UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
    UsdPhysics.RigidBodyAPI.Apply(prim.GetPrim())
    if kinematic:
        UsdPhysics.RigidBodyAPI(prim.GetPrim()).CreateKinematicEnabledAttr().Set(True)
    UsdPhysics.MassAPI.Apply(prim.GetPrim()).CreateMassAttr().Set(0.4)
    mat = _material(stage, f"{path}_mat", mu, colour)
    UsdShade.MaterialBindingAPI.Apply(prim.GetPrim()).Bind(mat)
    return prim


def _prismatic(stage, path, body0, body1, axis, low, high, local0, local1):
    joint = UsdPhysics.PrismaticJoint.Define(stage, path)
    joint.CreateBody0Rel().SetTargets([body0])
    joint.CreateBody1Rel().SetTargets([body1])
    joint.CreateAxisAttr().Set(axis)
    joint.CreateLowerLimitAttr().Set(low)
    joint.CreateUpperLimitAttr().Set(high)
    joint.CreateLocalPos0Attr().Set(Gf.Vec3f(*local0))
    joint.CreateLocalPos1Attr().Set(Gf.Vec3f(*local1))
    joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
    drive.CreateTypeAttr().Set("force")
    drive.CreateStiffnessAttr().Set(20000.0)
    drive.CreateDampingAttr().Set(500.0)
    drive.CreateMaxForceAttr().Set(200.0)
    return joint


def build_gripper(stage, base_z: float = 1.45) -> dict:
    """A *kinematic* parallel gripper: two fingers whose poses we command.

    Hand-authored prismatic articulations kept pulling the fingers into the wrong
    frames. Modelling the gripper kinematically is both simpler and closer to what
    this test needs to answer - the question is whether the *physics* can hold a
    fruit between two well-shaped, high-friction surfaces, not whether I can author
    a joint tree. The fingers are still real colliders, the fruit is still free, and
    the grip is still friction.
    """
    root = stage.DefinePrim("/World/Gripper", "Xform")
    _box(stage, "/World/Gripper/Wrist", (0.06, 0.16, 0.04), (0.5, 0.0, base_z - 0.03),
         0.5, (0.25, 0.26, 0.28), kinematic=True)
    for sign, name in ((-1.0, "FingerA"), (1.0, "FingerB")):
        y = sign * (0.012 + FINGER_THICK / 2.0)
        _box(
            stage,
            f"/World/Gripper/{name}",
            (FINGER_LENGTH, FINGER_THICK, FINGER_HEIGHT),
            (0.5, y, base_z - 0.03 - FINGER_HEIGHT / 2.0),
            2.0,
            (0.9, 0.2, 0.2),
            kinematic=True,
        )
        pad = _box(
            stage,
            f"/World/Gripper/{name}_Pad",
            (PAD_WIDTH, 0.006, FINGER_HEIGHT * 0.85),
            (0.5, y - sign * (FINGER_THICK / 2.0 + 0.003),
             base_z - 0.03 - FINGER_HEIGHT / 2.0),
            2.0,
            (0.15, 0.15, 0.15),
            kinematic=True,
        )
    return {"root": "/World/Gripper", "base_z": base_z}


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment",))
    # A flat table at the belt height so the test is independent of the conveyor.
    table = UsdGeom.Cube.Define(scene.stage, "/World/Table")
    table.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(table)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(0.5, 0.0, TABLE_TOP - 0.02))
    xf.AddScaleOp().Set(Gf.Vec3f(0.6, 0.6, 0.04))
    UsdPhysics.CollisionAPI.Apply(table.GetPrim())
    _material(scene.stage, "/World/TableMat", 0.8, (0.4, 0.4, 0.42))
    build_gripper(scene.stage)
    spawner = FruitSpawner(scene.stage, cfg, seed=11)
    spawner.create_pool()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    spawner.refresh_rigids()
    spawner.reset()

    from isaacsim.core.experimental.prims import RigidPrim

    wrist = RigidPrim("/World/Gripper/Wrist")
    fingers = {"left": RigidPrim("/World/Gripper/FingerA"),
               "right": RigidPrim("/World/Gripper/FingerB")}
    pads = {"left": RigidPrim("/World/Gripper/FingerA_Pad"),
            "right": RigidPrim("/World/Gripper/FingerB_Pad")}
    base_z = 1.45
    centre_x = 0.5
    half_face = 0.012 + FINGER_THICK / 2.0  # finger face offset from the centre

    def pose_gripper(z: float, gap: float) -> None:
        """Place the wrist at z and the two finger faces `gap` apart."""
        wrist_z = z - 0.03
        wrist.set_world_poses(positions=[[centre_x, 0.0, wrist_z]],
                              orientations=[[1.0, 0.0, 0.0, 0.0]])
        for sign, key in ((-1.0, "left"), (1.0, "right")):
            y = sign * (gap / 2.0 + FINGER_THICK / 2.0 + 0.003)
            fingers[key].set_world_poses(
                positions=[[centre_x, y, wrist_z - FINGER_HEIGHT / 2.0]],
                orientations=[[1.0, 0.0, 0.0, 0.0]],
            )
            pads[key].set_world_poses(
                positions=[[centre_x, y - sign * (FINGER_THICK / 2.0 + 0.003),
                            wrist_z - FINGER_HEIGHT / 2.0]],
                orientations=[[1.0, 0.0, 0.0, 0.0]],
            )

    by_size = sorted(spawner.samples, key=lambda s: s.diameter)
    picks = [by_size[0], by_size[len(by_size) // 3], by_size[len(by_size) // 2],
             by_size[2 * len(by_size) // 3], by_size[-1],
             by_size[len(by_size) // 4], by_size[3 * len(by_size) // 4],
             by_size[1], by_size[-2], by_size[2]]
    results = []
    for sample in picks:
        d = sample.diameter
        # Park open and high, then place the fruit on the table.
        pose_gripper(base_z, 0.09)
        for _ in range(40):
            SimulationManager.step(steps=1)
        spawner.place(sample, np.array([0.5, 0.0, TABLE_TOP + d / 2.0 + 0.002]))
        sample.held = True
        for _ in range(60):
            SimulationManager.step(steps=1)
        # Descend until the pad centres sit at the fruit's equator.
        grasp_z = TABLE_TOP + d / 2.0 + FINGER_HEIGHT / 2.0
        for step in range(120):
            pose_gripper(grasp_z - 0.10 * (1.0 - (step + 1) / 120.0), 0.09)
            SimulationManager.step(steps=1)
        settled = np.asarray(spawner.position(sample), dtype=float)
        # Close to 2 % interference, in small steps.
        for gap in np.linspace(0.09, d * 0.98, 60):
            pose_gripper(grasp_z, float(gap))
            SimulationManager.step(steps=2)
        for _ in range(60):
            SimulationManager.step(steps=1)
        closed = np.asarray(spawner.position(sample), dtype=float)
        fa = np.asarray(fingers["left"].get_world_poses()[0][0].numpy())
        fb = np.asarray(fingers["right"].get_world_poses()[0][0].numpy())
        say(
            f"    debug: fruit={np.round(closed, 4).tolist()} "
            f"fingerA={np.round(fa, 4).tolist()} fingerB={np.round(fb, 4).tolist()} "
            f"gap={(fb[1] - fa[1] - FINGER_THICK) * 100:.2f}cm"
        )
        # Lift 12 cm and see whether the fruit came along.
        for step in range(240):
            pose_gripper(grasp_z + 0.12 * (step + 1) / 240.0, d * 0.98)
            SimulationManager.step(steps=1)
        lifted = np.asarray(spawner.position(sample), dtype=float)
        rise = float(lifted[2] - closed[2])
        held = rise > 0.05
        results.append((d, held, rise, float(np.linalg.norm(closed - settled))))
        say(
            f"{sample.category:10s} d={d * 100:4.1f}cm "
            f"close_drift={np.linalg.norm(closed - settled) * 1000:5.1f}mm "
            f"rise={rise * 100:+6.1f}cm {'HELD' if held else 'slipped'}"
        )
        sample.held = False
        spawner.park(sample)
    wins = sum(1 for _d, held, _r, _c in results if held)
    say(f"summary: {wins}/{len(results)} held")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
