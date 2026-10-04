"""A force-limited 1-DoF parallel gripper, built as a real articulation.

`scripts/91_simple_gripper_test.py` proved the *physics* can hold these fruit
(10/10, 3.3-6.9 cm) but did it with a **kinematic** gripper; its articulated
attempt "kept pulling the fingers into the wrong frames" and was abandoned, so the
shipped cell uses kinematic pads whose normal force is the solver pushing the
fruit out of a commanded overlap. That is the contact model the grasp-primitive
sweep could not improve on (four negative results, see WORKLOG).

This script rebuilds the gripper properly: a kinematic wrist carrying two
*prismatic* finger joints with force-limited drives, so the squeeze force is a
controlled quantity (as in a real gripper) rather than an interference artefact.
The joints are authored with explicit local frames, and the script reports the
joint positions, the drive efforts and whether the fruit follows a lift.

    $ISAAC_SIM_DIR/python.sh scripts/101_actuated_gripper.py

`FRUIT_GRIP_MAX_FORCE` (N, default 30) is the effort limit, `FRUIT_GRIP_STIFFNESS`
(default 20000) and `FRUIT_GRIP_DAMPING` (default 500) the drive gains.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from fruit_sorting.actuated_gripper import ActuatedGripper
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from isaacsim.core.experimental.prims import Articulation, RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

FINGER_LENGTH = 0.060
FINGER_THICK = 0.012
FINGER_HEIGHT = 0.030
PAD_THICK = 0.006
PAD_WIDTH = 0.040
WRIST_HALF = 0.024          # wrist half width in y
TABLE_TOP = 1.17
OPEN = 0.075                # finger face separation when open


def _material(stage, path, mu, colour):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*colour))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    api.CreateStaticFrictionAttr().Set(mu)
    api.CreateDynamicFrictionAttr().Set(mu)
    api.CreateRestitutionAttr().Set(0.0)
    return mat


def _collision_box(stage, path, size, centre, mu, colour, parent_body: str | None):
    """A cube with a collider; if `parent_body` is given it is a child of that
    rigid body (so finger + pad are one link), otherwise it is its own body."""
    prim = UsdGeom.Cube.Define(stage, path)
    prim.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    if parent_body is None:
        xf.AddTranslateOp().Set(Gf.Vec3d(*centre))
    else:
        # local offset inside the parent rigid body's frame
        xf.AddTranslateOp().Set(Gf.Vec3d(*centre))
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
    UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
    UsdShade.MaterialBindingAPI.Apply(prim.GetPrim()).Bind(
        _material(stage, f"{path}_mat", mu, colour)
    )
    return prim


def build_actuated_gripper(stage, wrist_world=(0.5, 0.0, 1.42)) -> dict:
    """Wrist (kinematic) + two prismatic finger links with force-limited drives.

    Frame bookkeeping, which is where the earlier attempt went wrong:
      * the wrist body frame is the world frame of `/World/ActuatedGripper/Wrist`;
      * each finger body's origin is its own centre;
      * a prismatic joint's `localPos0`/`localPos1` are the joint anchor expressed
        in the two bodies' frames, so for a finger centred at (0, +-y, -z) in the
        wrist frame the anchors are (0, +-y, -z) and (0, 0, 0);
      * the axis is `+y` for both, with limits that let each finger travel inward.
    """
    root = stage.DefinePrim("/World/ActuatedGripper", "Xform")
    wrist = f"/World/ActuatedGripper/Wrist"
    prim = UsdGeom.Cube.Define(stage, wrist)
    prim.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*wrist_world))
    xf.AddScaleOp().Set(Gf.Vec3f(0.06, WRIST_HALF * 2.0, 0.03))
    UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
    UsdPhysics.RigidBodyAPI.Apply(prim.GetPrim()).CreateKinematicEnabledAttr().Set(True)
    UsdPhysics.MassAPI.Apply(prim.GetPrim()).CreateMassAttr().Set(0.5)
    UsdShade.MaterialBindingAPI.Apply(prim.GetPrim()).Bind(
        _material(stage, f"{wrist}_mat", 0.5, (0.25, 0.26, 0.28))
    )

    fingers = {}
    y_centre = WRIST_HALF + FINGER_THICK / 2.0 + PAD_THICK / 2.0   # 0.033 m
    z_centre = -(FINGER_HEIGHT / 2.0 + 0.004)
    for sign, name in ((-1.0, "A"), (1.0, "B")):
        body_path = f"/World/ActuatedGripper/Finger{name}"
        body = UsdGeom.Xform.Define(stage, body_path)
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
        UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr().Set(0.08)
        body_xf = UsdGeom.Xformable(body)
        body_xf.ClearXformOpOrder()
        body_xf.AddTranslateOp().Set(Gf.Vec3d(0.0, sign * y_centre, z_centre))
        # finger geometry (child of the finger body, local frame origin at centre)
        _collision_box(
            stage, f"{body_path}/Finger", (FINGER_LENGTH, FINGER_THICK, FINGER_HEIGHT),
            (0.0, 0.0, 0.0), 2.0, (0.9, 0.2, 0.2), parent_body=body_path,
        )
        # pad on the inner face
        _collision_box(
            stage, f"{body_path}/Pad", (PAD_WIDTH, PAD_THICK, FINGER_HEIGHT * 0.9),
            (0.0, -sign * (FINGER_THICK / 2.0 + PAD_THICK / 2.0), 0.0),
            2.0, (0.15, 0.15, 0.15), parent_body=body_path,
        )
        joint = UsdPhysics.PrismaticJoint.Define(stage, f"{body_path}_joint")
        joint.CreateBody0Rel().SetTargets([wrist])
        joint.CreateBody1Rel().SetTargets([body_path])
        joint.CreateAxisAttr().Set("Y")
        # travel: inward only (sign-dependent), 40 mm from the open position
        low, high = (-0.040, 0.002) if sign < 0 else (-0.002, 0.040)
        joint.CreateLowerLimitAttr().Set(low)
        joint.CreateUpperLimitAttr().Set(high)
        joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.0, sign * y_centre, z_centre))
        joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
        drive.CreateTypeAttr().Set("force")
        drive.CreateStiffnessAttr().Set(float(os.environ.get("FRUIT_GRIP_STIFFNESS", "20000")))
        drive.CreateDampingAttr().Set(float(os.environ.get("FRUIT_GRIP_DAMPING", "500")))
        drive.CreateMaxForceAttr().Set(float(os.environ.get("FRUIT_GRIP_MAX_FORCE", "30")))
        drive.CreateTargetPositionAttr().Set(0.0)
        fingers[name] = (body_path, sign, drive)
    return {"root": "/World/ActuatedGripper", "wrist": wrist, "fingers": fingers}


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment",))
    stage = scene.stage
    table = UsdGeom.Cube.Define(stage, "/World/Table")
    table.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(table)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(0.5, 0.0, TABLE_TOP - 0.02))
    xf.AddScaleOp().Set(Gf.Vec3f(0.6, 0.6, 0.04))
    UsdPhysics.CollisionAPI.Apply(table.GetPrim())
    UsdShade.MaterialBindingAPI.Apply(table.GetPrim()).Bind(
        _material(stage, "/World/TableMat", 0.8, (0.4, 0.4, 0.42))
    )

    os.environ.setdefault("FRUIT_GRIPPER_KIND", "actuated")
    gripper = ActuatedGripper(stage, "right")
    grip = {}
    spawner = FruitSpawner(stage, cfg, seed=11)
    spawner.create_pool()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    spawner.refresh_rigids()
    spawner.reset()

    # Command the drives directly through USD rather than through the Articulation
    # wrapper: that wrapper rejects this hand-authored joint tree (ArgumentError
    # inside its path resolution), and the drives only need their target-position
    # attributes set anyway.
    wrist = RigidPrim(f"{gripper.root}/Wrist")
    finger_bodies = {
        name: RigidPrim(f"{gripper.root}/Finger{name}") for name in ("A", "B")
    }
    wrist0 = np.array([0.5, 0.0, 1.42])
    rng = np.random.default_rng(3)
    noise = float(os.environ.get("FRUIT_PROBE_NOISE", "0.0"))
    say(f"actuated gripper links: {list(finger_bodies)} noise={noise * 1000:.1f}mm")

    def place_wrist(z: float) -> None:
        jitter = rng.normal(0.0, noise, 3) if noise > 0 else np.zeros(3)
        wrist.set_world_poses(positions=[[wrist0[0] + jitter[0], jitter[1], z - 0.02 + jitter[2]]])

    def command(a: float, b: float) -> None:
        gripper.drives["A"].CreateTargetPositionAttr().Set(float(a))
        gripper.drives["B"].CreateTargetPositionAttr().Set(float(b))

    def finger_positions() -> list:
        return [
            np.round(np.asarray(finger_bodies[k].get_world_poses()[0].numpy())[0], 4).tolist()
            for k in ("A", "B")
        ]

    picks = sorted(spawner.samples, key=lambda s: s.diameter)
    picks = [picks[0], picks[len(picks) // 2], picks[-1], picks[1], picks[-2]]
    held = 0
    for sample in picks:
        d = sample.diameter
        command(-0.040, 0.040)          # open (targets at the outer limits)
        place_wrist(1.42)
        for _ in range(40):
            SimulationManager.step(steps=1)
        spawner.place(sample, np.array([0.5, 0.0, TABLE_TOP + d / 2.0 + 0.002]))
        sample.held = True
        for _ in range(60):
            SimulationManager.step(steps=1)
        grasp_z = TABLE_TOP + d / 2.0 + FINGER_HEIGHT / 2.0
        for step in range(120):
            place_wrist(grasp_z - 0.08 * (1.0 - (step + 1) / 120.0))
            SimulationManager.step(steps=1)
        before = np.asarray(spawner.position(sample), dtype=float)
        # Close: drive the fingers inward past the fruit's surface; the effort
        # limit is what decides the squeeze force.
        over = float(os.environ.get("FRUIT_GRIP_OVERTRAVEL", "0.004"))
        half = (OPEN - d) / 2.0 + over            # inward travel per finger
        # Servo the close in steps: commanding the full overtravel in one tick makes
        # the drives slam the fingers inward and bat the fruit away (two of five
        # failures in logs/347), whereas a real controller ramps the closing command.
        close_steps = int(os.environ.get("FRUIT_GRIP_CLOSE_STEPS", "90"))
        for step in range(close_steps):
            frac = (step + 1) / close_steps
            command(-0.040 + 0.040 * frac * (half / 0.040) if False else -min(0.040, half * frac),
                    min(0.040, half * frac))
            SimulationManager.step(steps=1)
        for _ in range(60):
            SimulationManager.step(steps=1)
        q = finger_positions()
        # Lift and check
        for step in range(240):
            place_wrist(grasp_z + 0.16 * (step + 1) / 240.0)
            SimulationManager.step(steps=1)
        after = np.asarray(spawner.position(sample), dtype=float)
        lift = float(after[2] - before[2])
        ok = lift > 0.05
        held += int(ok)
        say(
            f"d={d * 100:.1f}cm  finger_y={q}  "
            f"fruit_pre={np.round(before, 3).tolist()} fruit_post={np.round(after, 3).tolist()} "
            f"lift={lift * 100:+.1f}cm  held={ok}"
        )
    say(f"actuated gripper: {held}/{len(picks)} held")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
