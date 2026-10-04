"""A force-limited parallel gripper built as a real joint tree.

The shipped gripper (`kinematic_gripper.py`) models the grip by commanding the pad
faces *inside* the fruit, so the normal force is whatever the solver needs to push
the fruit back out. That contact model is what the four negative grasp-primitive
experiments could not improve on (WORKLOG 2026-09-27).

This module is the alternative the design document actually calls for: a
1-DoF-per-finger *actuated* gripper whose squeeze force is limited by the drive
effort (`FRUIT_GRIP_MAX_FORCE`, default 30 N), exactly like a real gripper.
`scripts/101_actuated_gripper.py` proved the authoring works once the frames are
explicit; this class packages the same recipe behind the interface the task
already uses (`follow_centre(centre, quat, gap)`), so the pipeline can switch
gripper model with `FRUIT_GRIPPER_KIND=actuated`.

Frame bookkeeping (the part that sank the earlier attempt):

* the wrist is a *kinematic* body and is the articulation root;
* each finger body's origin is its own centre, so the prismatic anchors are
  `localPos0 = (0, +-y_centre, z_centre)` (wrist frame) and `localPos1 = (0,0,0)`
  (finger frame), axis `Y`;
* the finger box and its pad are children of the finger body (one link per finger);
* drives are commanded through USD (`drive.CreateTargetPositionAttr()`), because
  the `Articulation` wrapper rejects this hand-authored tree.
"""

from __future__ import annotations

import os

import numpy as np
from pxr import Gf, Sdf, UsdGeom, UsdPhysics, UsdShade

from .common import say

#: Geometry (metres), matching the kinematic gripper so waypoints stay valid.
FINGER_LENGTH = 0.060
FINGER_THICK = 0.012
PAD_THICK = 0.006
PAD_WIDTH = 0.040
WRIST_HALF_Y = 0.024
#: Finger travel from the open position to fully closed (per finger).
STROKE = 0.040


def _material(stage, path: str, mu: float, colour):
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


def _box(stage, path: str, size, centre, mu: float, colour):
    prim = UsdGeom.Cube.Define(stage, path)
    prim.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*centre))
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
    UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
    UsdShade.MaterialBindingAPI.Apply(prim.GetPrim()).Bind(
        _material(stage, f"{path}_mat", mu, colour)
    )
    return prim


class ActuatedGripper:
    """Two prismatic fingers with force-limited drives under a kinematic wrist."""

    def __init__(self, stage, side: str, mu: float | None = None, park=(0.0, 0.0, -3.0)):
        self.stage = stage
        self.side = side
        self.mu = float(os.environ.get("FRUIT_GRIPPER_MU", "2.0")) if mu is None else mu
        self.finger_height = float(os.environ.get("FRUIT_PAD_HEIGHT", "0.030"))
        self.open_gap = float(os.environ.get("FRUIT_ACTUATED_OPEN", "0.090"))
        self.max_force = float(os.environ.get("FRUIT_GRIP_MAX_FORCE", "30"))
        self.stiffness = float(os.environ.get("FRUIT_GRIP_STIFFNESS", "5000"))
        self.damping = float(os.environ.get("FRUIT_GRIP_DAMPING", "150"))
        self.enabled = os.environ.get("FRUIT_GRIPPER_KIND", "kinematic") == "actuated"
        self.root = f"/World/ActuatedGripper_{side}"
        self.home = np.asarray(park, dtype=float)
        self.y_centre = WRIST_HALF_Y + FINGER_THICK / 2.0 + PAD_THICK / 2.0
        self.z_centre = -(self.finger_height / 2.0 + 0.004)
        self.last_gap = self.open_gap
        if not self.enabled:
            return
        self._build()

    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        stage = self.stage
        base = self.root
        stage.DefinePrim(base, "Xform")

        wrist = UsdGeom.Cube.Define(stage, f"{base}/Wrist")
        wrist.GetSizeAttr().Set(1.0)
        xf = UsdGeom.Xformable(wrist)
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(*self.home.tolist()))
        xf.AddScaleOp().Set(Gf.Vec3f(0.06, WRIST_HALF_Y * 2.0, 0.03))
        UsdPhysics.CollisionAPI.Apply(wrist.GetPrim())
        UsdPhysics.RigidBodyAPI.Apply(wrist.GetPrim()).CreateKinematicEnabledAttr().Set(True)
        UsdPhysics.MassAPI.Apply(wrist.GetPrim()).CreateMassAttr().Set(0.5)
        UsdShade.MaterialBindingAPI.Apply(wrist.GetPrim()).Bind(
            _material(stage, f"{base}/Wrist_mat", 0.5, (0.25, 0.26, 0.28))
        )

        # Optional compliant mount: instead of teleporting a *rigid* wrist every
        # tick (which gives the finger drives a base with infinite stiffness and
        # destabilises the contact, logs/352), insert a three-axis prismatic spring
        # chain between the kinematic anchor and the wrist. The anchor is what
        # follows the arm; the wrist the fingers hang from is then a *compliant*
        # body, which is also what a real wrist flange looks like.
        self.mount = os.environ.get("FRUIT_WRIST_MOUNT", "teleport")
        self.finger_parent = f"{base}/Wrist"
        if self.mount == "gantry":
            previous = f"{base}/Wrist"
            for axis in ("X", "Y", "Z"):
                link = f"{base}/Gantry{axis}"
                body = UsdGeom.Cube.Define(stage, link)
                body.GetSizeAttr().Set(1.0)
                lxf = UsdGeom.Xformable(body)
                lxf.ClearXformOpOrder()
                lxf.AddTranslateOp().Set(Gf.Vec3d(*self.home.tolist()))
                lxf.AddScaleOp().Set(Gf.Vec3f(0.02, 0.02, 0.02))
                UsdPhysics.CollisionAPI.Apply(body.GetPrim())
                UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
                UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr().Set(0.05)
                joint = UsdPhysics.PrismaticJoint.Define(stage, f"{link}_joint")
                joint.CreateBody0Rel().SetTargets([previous])
                joint.CreateBody1Rel().SetTargets([link])
                joint.CreateAxisAttr().Set(axis)
                joint.CreateLowerLimitAttr().Set(-0.03)
                joint.CreateUpperLimitAttr().Set(0.03)
                joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
                joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
                joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
                drive.CreateTypeAttr().Set("force")
                drive.CreateStiffnessAttr().Set(float(os.environ.get("FRUIT_MOUNT_STIFFNESS", "3000")))
                drive.CreateDampingAttr().Set(float(os.environ.get("FRUIT_MOUNT_DAMPING", "200")))
                drive.CreateMaxForceAttr().Set(float(os.environ.get("FRUIT_MOUNT_MAX_FORCE", "500")))
                drive.CreateTargetPositionAttr().Set(0.0)
                previous = link
            self.finger_parent = previous

        self.drives: dict[str, object] = {}
        for sign, name in ((-1.0, "A"), (1.0, "B")):
            body_path = f"{base}/Finger{name}"
            body = UsdGeom.Xform.Define(stage, body_path)
            UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
            UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr().Set(0.08)
            body_xf = UsdGeom.Xformable(body)
            body_xf.ClearXformOpOrder()
            body_xf.AddTranslateOp().Set(
                Gf.Vec3d(*(self.home + np.array([0.0, sign * self.y_centre, self.z_centre])).tolist())
            )
            _box(
                stage, f"{body_path}/Finger",
                (FINGER_LENGTH, FINGER_THICK, self.finger_height),
                (0.0, 0.0, 0.0), self.mu, (0.9, 0.2, 0.2),
            )
            _box(
                stage, f"{body_path}/Pad",
                (PAD_WIDTH, PAD_THICK, self.finger_height * 0.9),
                (0.0, -sign * (FINGER_THICK / 2.0 + PAD_THICK / 2.0), 0.0),
                self.mu, (0.15, 0.15, 0.15),
            )
            joint = UsdPhysics.PrismaticJoint.Define(stage, f"{body_path}_joint")
            joint.CreateBody0Rel().SetTargets([self.finger_parent])
            joint.CreateBody1Rel().SetTargets([body_path])
            joint.CreateAxisAttr().Set("Y")
            # travel measured from the authored (open) pose
            low, high = (-STROKE, 0.002) if sign < 0 else (-0.002, STROKE)
            joint.CreateLowerLimitAttr().Set(low)
            joint.CreateUpperLimitAttr().Set(high)
            joint.CreateLocalPos0Attr().Set(
                Gf.Vec3f(0.0, sign * self.y_centre, self.z_centre)
            )
            joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
            joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
            joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
            drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
            drive.CreateTypeAttr().Set("force")
            drive.CreateStiffnessAttr().Set(self.stiffness)
            drive.CreateDampingAttr().Set(self.damping)
            drive.CreateMaxForceAttr().Set(self.max_force)
            drive.CreateTargetPositionAttr().Set(0.0)
            self.drives[name] = drive
        say(
            f"actuated gripper {self.side}: force limit {self.max_force:.0f} N, "
            f"stiffness {self.stiffness:.0f}, stroke {STROKE * 1000:.0f} mm/finger"
        )

    # ------------------------------------------------------------------ #
    def _command(self, inward: float) -> None:
        """Command both fingers `inward` metres from the open pose."""
        value = float(np.clip(inward, 0.0, STROKE))
        self.drives["A"].CreateTargetPositionAttr().Set(+value)
        self.drives["B"].CreateTargetPositionAttr().Set(-value)

    def command_gap(self, gap: float) -> None:
        """Drive the finger faces to `gap` metres apart (force limited)."""
        inward = (self.open_gap - float(gap)) / 2.0
        self._command(inward)
        self.last_gap = float(gap)

    def park(self) -> None:
        if not self.enabled:
            return
        self.follow_centre(self.home, np.array([1.0, 0.0, 0.0, 0.0]), self.open_gap)

    def follow_centre(self, centre, quat, gap: float) -> None:
        """Place the *wrist* so the finger faces straddle `centre`, then close.

        Same signature as the kinematic gripper, so the task's grasp, carry and
        release code is unchanged. The difference is physical: here the gap is a
        drive target with a 30 N effort limit, not a pose the solver has to enforce.
        """
        if not self.enabled:
            return
        from isaacsim.core.experimental.prims import RigidPrim

        centre = np.asarray(centre, dtype=float)
        quat = np.asarray(quat, dtype=float)
        rot = np.array(
            [
                [
                    1 - 2 * (quat[2] ** 2 + quat[3] ** 2),
                    2 * (quat[1] * quat[2] - quat[3] * quat[0]),
                    2 * (quat[1] * quat[3] + quat[2] * quat[0]),
                ],
                [
                    2 * (quat[1] * quat[2] + quat[3] * quat[0]),
                    1 - 2 * (quat[1] ** 2 + quat[3] ** 2),
                    2 * (quat[2] * quat[3] - quat[1] * quat[0]),
                ],
                [
                    2 * (quat[1] * quat[3] - quat[2] * quat[0]),
                    2 * (quat[2] * quat[3] + quat[1] * quat[0]),
                    1 - 2 * (quat[1] ** 2 + quat[2] ** 2),
                ],
            ]
        )
        wrist_pos = centre - rot @ np.array([0.0, 0.0, self.z_centre])
        if not hasattr(self, "_wrist_prim"):
            self._wrist_prim = RigidPrim(f"{self.root}/Wrist")
            self._wrist_cmd = None
            self._quat_cmd = None
        # Feed the kinematic wrist a *smoothed* command. Copying the measured TCP
        # (and the fruit's measured position) every tick gives the finger joints
        # violent base accelerations, and the force-limited drives then launch the
        # fruit out of the world (logs/352: positions at -1050 m). Rate-limit the
        # translation and slerp the orientation towards the requested one.
        v_max = float(os.environ.get("FRUIT_WRIST_VMAX", "0.15")) * (1.0 / 120.0)
        lerp = float(os.environ.get("FRUIT_WRIST_SLERP", "0.10"))
        # Teleport the kinematic wrist only every `FRUIT_WRIST_EVERY` ticks: the
        # finger drives see the base as an infinitely stiff constraint, so a 5 mm
        # per-tick jump (0.6 m/s at 120 Hz) inside a stiff contact loop is what
        # destabilised the grip (fruit launched to -1050 m, logs/352). Holding the
        # pose for a few ticks gives the drives time to track.
        every = max(1, int(os.environ.get("FRUIT_WRIST_EVERY", "1")))
        self._wrist_tick = getattr(self, "_wrist_tick", 0) + 1
        if every > 1 and (self._wrist_tick % every) != 0 and self._wrist_cmd is not None:
            self.command_gap(gap)
            return
        if self._wrist_cmd is None:
            self._wrist_cmd = wrist_pos.copy()
            self._quat_cmd = quat.copy()
        else:
            delta = wrist_pos - self._wrist_cmd
            distance = float(np.linalg.norm(delta))
            if distance > v_max:
                wrist_pos = self._wrist_cmd + delta * (v_max / distance)
            else:
                wrist_pos = wrist_pos
            self._wrist_cmd = wrist_pos.copy()
            # shortest-arc slerp towards the requested orientation
            q0 = self._quat_cmd
            dot = float(np.clip(np.dot(q0, quat), -1.0, 1.0))
            q1 = quat if dot >= 0.0 else -quat
            self._quat_cmd = (1.0 - lerp) * q0 + lerp * q1
            self._quat_cmd /= max(float(np.linalg.norm(self._quat_cmd)), 1e-9)
        self._wrist_prim.set_world_poses(
            positions=[wrist_pos.tolist()], orientations=[self._quat_cmd.tolist()]
        )
        self.command_gap(gap)

    # ------------------------------------------------------------------ #
    def pad_centre(self) -> np.ndarray:
        from isaacsim.core.experimental.prims import RigidPrim

        if not hasattr(self, "_pad_prims"):
            self._pad_prims = [
                RigidPrim(f"{self.root}/Finger{name}/Pad") for name in ("A", "B")
            ]
        a = np.asarray(self._pad_prims[0].get_world_poses()[0].numpy())[0]
        b = np.asarray(self._pad_prims[1].get_world_poses()[0].numpy())[0]
        return (a + b) / 2.0

    def summary(self) -> str:
        if not self.enabled:
            return f"gripper_{self.side}: disabled"
        return (
            f"actuated gripper_{self.side}: gap_cmd={self.last_gap * 100:.2f}cm "
            f"force_limit={self.max_force:.0f}N"
        )
