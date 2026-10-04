"""A parallel gripper modelled as two kinematic fingers.

The OpenArm asset's own gripper cannot be made to work here: its finger collision
mesh stops short of the fingertips, its instance proxies refuse new colliders, and
a fixed joint to an articulation link is not honoured (WORKLOG 2026-09-26/27).

`scripts/91_simple_gripper_test.py` therefore asked the question the asset could
not answer - *can this simulator hold a 3-7 cm fruit at all?* - with a purpose-made
two-finger gripper: **10/10 fruit held and carried 12 cm** (3.3-6.9 cm, friction
only, no attachment). The geometry that works is simple:

* two fingers 1.2 cm thick, 5 cm tall, 6 cm long;
* a 4 cm wide pad on each inner face, friction 2.0;
* faces closed to 2 % less than the fruit's diameter.

This module reproduces that gripper in the sorting cell, with the wrist pose
slaved to the arm's tool point so the existing waypoints and IK still drive it.
"""

from __future__ import annotations

import os

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from .common import say

#: Control period the hand's speed limit is expressed in.
CONTROL_DT = 1.0 / 120.0
FINGER_LENGTH = 0.060
FINGER_THICK = 0.012
#: Vertical size of the fingers and pads. A 5 cm-tall pad is fine when the pads are
#: *commanded* to the fruit's measured centre (the assisted pipeline), but when the
#: pads are mounted on the arm's real fingertips every residual of the arm's pose
#: reaches the closure geometry, and a tall pad's lower edge then catches the belt
#: and ejects the fruit (measured: `lift = -1.17 m`, logs/325). A 2 cm pad is the
#: finger-mountable geometry for the coherent hand.
FINGER_HEIGHT = float(os.environ.get("FRUIT_PAD_HEIGHT", "0.050"))
PAD_WIDTH = 0.040
PAD_THICK = 0.006


def _material(stage, path: str, mu: float, colour):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*colour))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.6)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    api.CreateStaticFrictionAttr().Set(mu)
    api.CreateDynamicFrictionAttr().Set(mu)
    api.CreateRestitutionAttr().Set(0.0)
    # Compliant contact. The grip is modelled by commanding the pad faces *inside*
    # the fruit, so the normal force that carries the payload comes from the
    # solver pushing the fruit back out. With a rigid contact that push is an
    # impulse: the payload rattles at 0.3-0.7 m/s inside the closed pads
    # (measured, logs/271) even though the grip holds. Capping the depenetration
    # velocity instead *destroys* the grip (0/3, logs/272) because it removes the
    # very force that does the carrying. A spring-damper contact is the model that
    # keeps the force while making it smooth:
    #   F_n = k * penetration + c * d(penetration)/dt
    # Both are opt-in through the environment.
    stiffness = float(os.environ.get("FRUIT_PAD_CONTACT_STIFFNESS", "0"))
    if stiffness > 0.0:
        contact = PhysxSchema.PhysxMaterialAPI.Apply(mat.GetPrim())
        contact.CreateCompliantContactStiffnessAttr().Set(stiffness)
        contact.CreateCompliantContactDampingAttr().Set(
            float(os.environ.get("FRUIT_PAD_CONTACT_DAMPING", "20"))
        )
    return mat


def _quat_from_z(direction) -> list[float]:
    """Quaternion (w, x, y, z) that rotates +Z onto `direction`."""
    vec = np.asarray(direction, dtype=float)
    length = float(np.linalg.norm(vec))
    if length < 1e-9:
        return [1.0, 0.0, 0.0, 0.0]
    vec = vec / length
    axis = np.cross(np.array([0.0, 0.0, 1.0]), vec)
    sine = float(np.linalg.norm(axis))
    cosine = float(vec[2])
    if sine < 1e-9:
        return [1.0, 0.0, 0.0, 0.0] if cosine > 0 else [0.0, 1.0, 0.0, 0.0]
    axis = axis / sine
    angle = float(np.arctan2(sine, cosine))
    return [float(np.cos(angle / 2.0)), *(axis * float(np.sin(angle / 2.0))).tolist()]


def _box(
    stage,
    path: str,
    size,
    centre,
    mu: float,
    colour,
    collide: bool = True,
    body: bool = True,
):
    prim = UsdGeom.Cube.Define(stage, path)
    prim.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*centre))
    xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
    if collide:
        UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
    if body:
        rigid = UsdPhysics.RigidBodyAPI.Apply(prim.GetPrim())
        rigid.CreateKinematicEnabledAttr().Set(True)
        UsdPhysics.MassAPI.Apply(prim.GetPrim()).CreateMassAttr().Set(0.2)
    UsdShade.MaterialBindingAPI.Apply(prim.GetPrim()).Bind(
        _material(stage, f"{path}_mat", mu, colour)
    )
    return prim


class OpenArmHand:
    """The robot's *own* parallel jaws used as the hand.

    The owner's complaint about the kinematic pads is a render/mechanics
    mismatch: the bodies that hold the fruit are invisible and sit below the
    visible OpenArm jaws. This class makes the OpenArm's own fingers those
    bodies. It is selected with `FRUIT_GRIPPER_KIND=openarm` (the shipped
    default on the de-instanced asset) and presents the same interface as
    `KinematicGripper` so the task's grasp/carry/release code is unchanged:

    * `follow_centre(centre, quat, gap)` commands the two prismatic finger
      joints to a *face* separation of `gap` (via the arm's calibrated
      `gripper_value_for_separation`); the drive is force limited by the asset
      (10 N per finger), so closing past the fruit is a real pinch, not a pose.
    * `pad_centre()` is the measured midpoint between the two finger links, so
      the slip monitor reports the payload's motion in the hand frame.
    * `pad_faces()` exposes the two link origins for the closure diagnostic.

    The arm itself is commanded by the task's coherent-hand servo: the class
    never moves the arm. The finger drives target 0 (closed) when left alone,
    so the task must keep commanding `gap` (it does, every close/carry tick).
    """

    kind = "openarm"

    def __init__(self, stage, side: str, arm, mu: float | None = None):
        self.stage = stage
        self.side = side
        self.arm = arm
        #: Friction coefficient used for the carry's cone budget. The finger
        #: material is bound to `FRUIT_FINGER_MU` in the scene (default 2.0 when
        #: this hand is active, the same gripper material as the kinematic pads'
        #: `FRUIT_GRIPPER_MU`); PhysX takes the *minimum* of the two surfaces.
        self.mu = float(os.environ.get("FRUIT_FINGER_MU", "2.0")) if mu is None else mu
        self.enabled = True
        self.wrist_back = float(os.environ.get("FRUIT_HAND_WRIST_BACK", "0.06"))
        self.last_gap = float(os.environ.get("FRUIT_GRIPPER_OPEN", "0.09"))
        self.highlight = False
        self.v_max = 0.0
        self._prims: dict = {}
        self._jaw_prims: list = []

    # ------------------------------------------------------------------ #
    def park(self) -> None:
        """Open the jaws (a park above the cell is the arm's job, not the hand's)."""
        self.arm.set_gripper(self.arm.OPEN)
        self.last_gap = float(os.environ.get("FRUIT_GRIPPER_OPEN", "0.09"))

    def follow_centre(self, centre, quat, gap: float) -> np.ndarray:
        """Drive the finger faces to `gap` apart; the arm pose is the caller's."""
        self.arm.set_gripper(self.arm.gripper_value_for_separation(float(gap)))
        self.last_gap = float(gap)
        return np.asarray(centre, dtype=float)

    def pad_centre(self) -> np.ndarray:
        return np.asarray(self.arm.jaw_centre(), dtype=float)

    def pad_faces(self) -> tuple[np.ndarray, np.ndarray]:
        left, right = self.arm.jaw_positions()
        return np.asarray(left, dtype=float), np.asarray(right, dtype=float)

    #: The OpenArm pads are *at* the finger link origins; no thickness offset.
    pad_face_offset = 0.0

    def summary(self) -> str:
        return (
            f"openarm hand {self.side}: jaw={self.arm.jaw_separation() * 100:.2f}cm "
            f"gap_cmd={self.last_gap * 100:.2f}cm mu={self.mu:.2f}"
        )


class KinematicGripper:
    """Two kinematic fingers whose poses are commanded each control step."""

    def __init__(self, stage, side: str, mu: float | None = None, park=(0.0, 0.0, -3.0)):
        self.stage = stage
        self.side = side
        self.mu = float(os.environ.get("FRUIT_GRIPPER_MU", "2.0")) if mu is None else mu
        self.root = f"/World/Gripper_{side}"
        self.home = np.asarray(park, dtype=float)
        self.enabled = os.environ.get("FRUIT_KINEMATIC_GRIPPER", "1") == "1"
        #: Speed cap for the commanded pad centre [m/s]. The pads are kinematic, so
        #: `follow_centre` places them exactly where it is told; when the reactive
        #: re-seat after a slip moves them 25-40 mm in one tick, the hand moves at
        #: **2.96-4.95 m/s** - 8-13x the fastest carry profile (0.371), which is the
        #: flicker the carry report's `in-hand |v|max` is actually measuring
        #: (`logs/145`). Capping it looks like the obvious fix and **it is not**:
        #: with `FRUIT_HAND_VMAX=0.45` the pads can no longer catch a payload that is
        #: already leaving the jaws, so the relation degrades instead of being
        #: restored - the slip inside one `bin1_inside` leg climbs 27.4 -> 39.7 ->
        #: 53.1 -> 59.5 mm, i.e. to the edge of `FRUIT_SLIP_REACT_MAX` (60 mm, beyond
        #: which the controller deliberately stops reacting and the fruit is lost),
        #: and the lagging pads then break the *carry* cone budget (1.28x/1.73x) and
        #: push one descent past its speed reference (`logs/150` vs `logs/145/146`).
        #: So the default is 0 (off) and the teleport stays: it is a rescue for a
        #: payload that is already leaving, not a motion-planning defect. The open
        #: item is to stop the payload leaving in the first place - which is what
        #: `FRUIT_SLIP_SQUEEZE_STEP=0` addresses (see the WORKLOG).
        self.v_max = float(os.environ.get("FRUIT_HAND_VMAX", "0.0"))
        #: How far the wrist block sits behind the pad centre along the tool axis.
        #: The arm is commanded so its jaw centre lands *here*, which is what makes
        #: the arm visibly hold the hand instead of floating 5-14 cm above it (see
        #: `_gripper_offset` in tasks.py). 6 cm keeps the resulting jaw target
        #: (fruit centre + 6 cm) inside the measured reachable band.
        self.wrist_back = float(os.environ.get("FRUIT_HAND_WRIST_BACK", "0.06"))
        #: Draw the wrist block. Off by default now that the arm's jaw is placed at
        #: the wrist: the block overlapped the arm's own fingers and read as
        #: clipping, and the arm already provides the visual connection.
        self.wrist_visual = os.environ.get("FRUIT_HAND_WRIST", "0") == "1"
        #: Diagnostic colours: magenta pads, cyan fingers, yellow wrist. The pads
        #: are the *real* gripping surfaces but are small and dark by default, so
        #: they are invisible in a clip; this makes the grip legible.
        self.highlight = os.environ.get("FRUIT_HAND_HIGHLIGHT", "0") == "1"
        self._cmd_centre: np.ndarray | None = None
        self._prims = {}
        self._stem = None
        self._stem_scale = False
        self._jaw_prims = []
        if not self.enabled:
            return
        UsdGeom.Xform.Define(stage, self.root)
        # The wrist block is the back of the hand, and it is mounted *inside* the
        # robot: the pads sit only 5-8 cm from the OpenArm's own jaw centre, so the
        # block at 9 cm behind the pads overlaps the arm's wrist links. As a
        # kinematic (infinite-mass) collider it therefore pushes the arm - measured
        # as joint 5 running away at ~34 rad/s against its own drive target with a
        # zero velocity target, a 23 mm single-tick TCP lurch (logs/432). It only
        # ever needs to be visible, so it gets no collider by default; set
        # `FRUIT_HAND_WRIST_COLLIDER=1` to restore the old behaviour.
        for name in ("Wrist", "FingerA", "FingerB"):
            if name == "Wrist" and not self.wrist_visual:
                # The wrist block is a 5 cm cube drawn at the back of the hand. It
                # used to overlap the arm's own fingers/wrist and read as clipping
                # (`logs/video_hand` close-ups). Now that the arm is commanded so
                # its jaw sits *at* the wrist (`FRUIT_HAND_WRIST_BACK`), the arm
                # itself visually holds the hand, so the block is redundant and off
                # by default. `FRUIT_HAND_WRIST=1` restores it.
                continue
            _box(
                stage,
                f"{self.root}/{name}",
                (0.05, 0.05, 0.03) if name == "Wrist" else (FINGER_LENGTH, FINGER_THICK, FINGER_HEIGHT),
                tuple(float(v) for v in self.home),
                self.mu,
                (
                    (1.0, 0.85, 0.1)
                    if name == "Wrist"
                    else (0.1, 0.8, 1.0)
                )
                if self.highlight
                else ((0.25, 0.26, 0.28) if name == "Wrist" else (0.88, 0.22, 0.18)),
                collide=name != "Wrist"
                or os.environ.get("FRUIT_HAND_WRIST_COLLIDER", "0") == "1",
            )
        for sign, name in ((-1.0, "A"), (1.0, "B")):
            _box(
                stage,
                f"{self.root}/Pad{name}",
                (PAD_WIDTH, PAD_THICK, FINGER_HEIGHT * 0.85),
                tuple(float(v) for v in self.home),
                self.mu,
                (1.0, 0.1, 0.9) if self.highlight else (0.15, 0.15, 0.15),
            )
        # Rigid standoff between the arm's own jaws and this hand. The pads sit
        # 5-8 cm from the OpenArm's jaw centre (the calibrated pick pose is past
        # the arm's reachable band at belt height), so without a drawn link the
        # render reads as a fruit floating next to an empty gripper. The standoff
        # is the physical truth of this cell, so it is drawn rather than hidden.
        # Rigid standoff between the arm's own jaws and this hand. With the arm now
        # commanded so its jaw sits *at* the wrist (`FRUIT_HAND_WRIST_BACK`), the
        # standoff is nearly zero and the drawn bar sits inside the arm's own
        # fingers, which reads as clipping - off by default. `FRUIT_HAND_STEM=1`
        # restores it for the assisted frame's old, long standoff.
        self._stem_scale = os.environ.get("FRUIT_HAND_STEM", "0") == "1"
        if self._stem_scale:
            self._stem = _box(
                stage,
                f"{self.root}/Stem",
                (0.014, 0.014, 0.08),
                tuple(float(v) for v in self.home),
                self.mu,
                (0.35, 0.36, 0.38),
                collide=False,
                body=False,
            )
        from isaacsim.core.experimental.prims import RigidPrim

        for name in ("Wrist", "FingerA", "FingerB", "PadA", "PadB"):
            if name == "Wrist" and not self.wrist_visual:
                continue
            self._prims[name] = RigidPrim(f"{self.root}/{name}")
        # The arm's own jaws, so the standoff can be drawn between them and the
        # wrist block without the task having to pass its state in.
        self._jaw_prims = []
        for which in ("left", "right"):
            path = f"/World/OpenArm/openarm_{side}_{which}_finger"
            if stage.GetPrimAtPath(path).IsValid():
                self._jaw_prims.append(RigidPrim(path))
        # The hand is a kinematic body mounted where the arm already is: the pads
        # sit 5-8 cm from the OpenArm jaw centre, so the wrist block overlaps the
        # arm's own wrist links. A kinematic collider there *pushes the arm* -
        # measured as joint 5 running away at ~34 rad/s against its own drive
        # target with a zero velocity target, a 23 mm single-tick TCP lurch
        # (logs/432). Filtering the whole hand against the arm's links keeps every
        # contact the hand needs (fruit, belts) and removes the ones it must
        # never have.
        # Default off: measured *worse* than simply dropping the collider. With the
        # hand filtered against the arm's links instead, the same ten-attempt suite
        # falls to **6/10** (`logs/435`) - the filtered pads lose grip contact and
        # two picks fail with "fruit did not follow the gripper" - so the filter
        # does more than remove the arm contact and is not a safe substitute.
        if os.environ.get("FRUIT_HAND_FILTER", "0") == "1":
            arm_links = [
                prim.GetPath()
                for prim in Usd.PrimRange(
                    stage.GetPrimAtPath("/World/OpenArm"),
                    Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate),
                )
                if prim.HasAPI(UsdPhysics.RigidBodyAPI)
                and f"_{side}_" in prim.GetName()
                and "finger" not in prim.GetName()
            ]
            for name in ("Wrist", "FingerA", "FingerB", "PadA", "PadB"):
                prim = stage.GetPrimAtPath(f"{self.root}/{name}")
                if not prim.IsValid() or not prim.HasAPI(UsdPhysics.CollisionAPI):
                    continue
                pairs = UsdPhysics.FilteredPairsAPI.Apply(prim)
                for link in arm_links:
                    pairs.CreateFilteredPairsRel().AddTarget(link)
        # The asset's own fingers are left in place visually but must not fight the
        # kinematic pads for the fruit: disabling their colliders is an attribute
        # override, which - unlike new prims - does reach the instanced robot.
        proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
        for which in ("left", "right"):
            link = stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_{which}_finger")
            if not link.IsValid():
                continue
            for prim in Usd.PrimRange(link, proxies):
                if prim.HasAPI(UsdPhysics.CollisionAPI):
                    UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)

    # ------------------------------------------------------------------ #
    def park(self) -> None:
        for prim in self._prims.values():
            prim.set_world_poses(
                positions=[self.home.tolist()], orientations=[[1.0, 0.0, 0.0, 0.0]]
            )
        if self._stem is not None:
            UsdGeom.Xformable(self._stem).GetTranslateOp().Set(
                Gf.Vec3d(*[float(v) for v in self.home])
            )
        # Parking is a deliberate jump (the hand leaves the cell), so the next
        # command has to place it rather than crawl to it from (0, 0, -3).
        self._cmd_centre = None

    def follow_centre(self, centre, quat, gap: float) -> np.ndarray:
        """Put the finger faces `gap` apart, centred on `centre` (world metres).

        Returns the centre the pads were actually placed at, which is the requested
        one unless the rate limiter clipped it - callers that command the arm to
        follow the hand must use the return value, not their own request.

        Taking the pad centre explicitly removes the OpenArm peculiarity that made
        alignment so fragile: the tool point sits ~7.8 cm past the jaws and the
        asset's pads sit ~1.6 cm below the link origins, so "where are the pads"
        was always an estimate. Here it is the input.
        """
        if not self.enabled:
            return np.asarray(centre, dtype=float)
        centre = np.asarray(centre, dtype=float)
        if self._cmd_centre is not None and self.v_max > 0.0:
            delta = centre - self._cmd_centre
            step = self.v_max * CONTROL_DT
            distance = float(np.linalg.norm(delta))
            if distance > step:
                centre = self._cmd_centre + delta * (step / distance)
        self._cmd_centre = centre.copy()
        quat = np.asarray(quat, dtype=float)
        w, x, y, z = (float(v) for v in quat)
        rot = np.array(
            [
                [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
            ]
        )
        axis = rot[:, 1]     # jaw opening axis in world coordinates
        down = rot[:, 2]
        for sign, key in ((-1.0, "A"), (1.0, "B")):
            offset = axis * (sign * (gap / 2.0 + FINGER_THICK / 2.0 + PAD_THICK / 2.0))
            self._prims[f"Finger{key}"].set_world_poses(
                positions=[(centre + offset).tolist()],
                orientations=[quat.tolist()],
            )
            self._prims[f"Pad{key}"].set_world_poses(
                positions=[
                    (centre + offset - axis * sign * (FINGER_THICK / 2.0 + PAD_THICK / 2.0)).tolist()
                ],
                orientations=[quat.tolist()],
            )
        if "Wrist" in self._prims:
            self._prims["Wrist"].set_world_poses(
                # Behind the pads, towards the hand: putting the wrist *at* the pad
                # centre drops a 5 cm block on top of the fruit and launches it
                # (fruit coordinates of -2 m in logs/170).
                positions=[(centre - down * self.wrist_back).tolist()],
                orientations=[quat.tolist()],
            )
        if self._stem_scale:
            self._place_stem(centre - down * self.wrist_back)
        return centre

    def _place_stem(self, wrist) -> None:
        """Span the standoff from the arm's jaw centre to the wrist block."""
        if not self._jaw_prims:
            return
        points = []
        for prim in self._jaw_prims:
            try:
                points.append(np.asarray(prim.get_world_poses()[0][0].numpy(), dtype=float))
            except (AttributeError, IndexError, RuntimeError):
                continue
        if not points:
            return
        jaw = np.mean(points, axis=0)
        vector = np.asarray(wrist, dtype=float) - jaw
        length = float(np.linalg.norm(vector))
        if length < 1e-4:
            return
        xf = UsdGeom.Xformable(self._stem)
        centre = jaw + vector / 2.0
        xf.GetTranslateOp().Set(Gf.Vec3d(*[float(v) for v in centre]))
        quat = _quat_from_z(vector)
        xf.GetOrientOp().Set(
            Gf.Quatf(float(quat[0]), Gf.Vec3f(float(quat[1]), float(quat[2]), float(quat[3])))
        )
        # A tiny extra covers the joint at both ends; the box is visual only
        # (no collider), so overlapping the jaws and the wrist block is fine.
        xf.GetScaleOp().Set(Gf.Vec3f(0.014, 0.014, max(length * 1.15, 0.01)))


    def summary(self) -> str:
        if not self.enabled:
            return f"gripper_{self.side}: disabled"
        a = np.asarray(self._prims["PadA"].get_world_poses()[0][0].numpy())
        b = np.asarray(self._prims["PadB"].get_world_poses()[0][0].numpy())
        return f"gripper_{self.side}: gap={np.linalg.norm(b - a) * 100:.2f}cm"

    def pad_centre(self) -> np.ndarray:
        a = np.asarray(self._prims["PadA"].get_world_poses()[0][0].numpy())
        b = np.asarray(self._prims["PadB"].get_world_poses()[0][0].numpy())
        return (a + b) / 2.0

    def pad_faces(self) -> tuple[np.ndarray, np.ndarray]:
        """World centres of the two pad prims, whose span is the face separation.

        `follow_centre` places each pad's *prim centre* at `centre +/- axis * gap/2`,
        so the inner faces are one pad thickness closer together than the prim
        centres. Exposed here so the closure diagnostic can report the geometry the
        grip actually closed with instead of the commanded number.
        """
        a = np.asarray(self._prims["PadA"].get_world_poses()[0][0].numpy(), dtype=float)
        b = np.asarray(self._prims["PadB"].get_world_poses()[0][0].numpy(), dtype=float)
        return a, b

    #: Inner-face separation is the prim-centre span minus this (one pad thickness).
    pad_face_offset = PAD_THICK
