"""A radial **four-pad cage** hand on the OpenArm flange - the P107 retrofit probe.

**What this is.** The owner's decision after P104/P106 was to build the *shape*
that passed the survey's bar, not to buy a product: four pads at **4 x 90 deg**
around the tool axis, closed by a **single closure synergy** (one scalar command
moves all four pads radially inward), on force-capped prismatic drives
(k = 1e5 N/m, c = 100 Ns/m, **4.90 N/pad**). It is the P104 `quad` form carried
into the pipeline: four contacts whose normals are perpendicular to the tool
axis, plus the plate's own distal lip - the two things
`docs/PLATFORM_SURVEY.md` section 3.3 says the loaded slide should be answered
with ("win by envelopment, not force"; P76 measured that force alone does not
convert the class).

**Geometry.** The *face* is the record's pad plate (`logs/p66/COLLIDER_READ.md`:
61.000 x 84.902 mm, 10.000 mm thick, distal plane 80.500 mm below the jaw
centre); the **width and the length are cut**, and both cuts were forced by
measurement (`logs/p107/METHOD.md` section 2):

| quantity | value | source |
|---|---|---|
| pad face | **26.000 x 60.000 mm**, 10.000 mm thick | the shipped plate, cut twice: `pad width <= aperture` (four 61 mm plates at 4 x 90 deg intersect below a 61 mm aperture and, being dynamic, jam), and the shipped 84.9 mm length puts its proximal end 4.4 mm **above** the jaw centre, inside the OpenArm's palm |
| plate distal plane | **80.500 mm** below the jaw centre - *unchanged* | `tasks.FINGER_TIP_BELOW_JAW` |
| lip below the payload's equator | **10.5 mm** - *unchanged* | the shipped pinch's own |
| per-pad force cap | **4.90 N** | `logs/p41/P3_RESULTS.md` (9.75-9.9 N over two faces) |
| drive | k **1e5** N/m, c **100** Ns/m | P104's own near-critical pair (`2*sqrt(k*m)` = 89 for this pad); the shipped fingers' 2000 is numerically unstable for a 0.020 kg pad on a standalone joint at 120 Hz |
| pad material | mu **2.0**, restitution 0 | `scene`'s finger material; PhysX averages the pair (P104) |
| aperture, open | **120.0 mm** (face radius 60.0 mm) | this module, `FRUIT_CAGE_OPEN_FACE_R`: the open cage has to swallow the line's **~24 mm** pursuit error |
| aperture, closed | down to **26.0 mm** (the smallest pool fruit with squeeze) | this module |
| pad count | **4**, at 0/90/180/270 deg | the brief / P104 `quad` |

**The tool offset** that replaces `_pad_standoff` is derived, not copied: the
plate's distal plane sits 80.5 mm below the jaw centre, and the lip that catches
an axial slide is 10.5 mm below the payload's equator, so the payload's centre
sits **70.0 mm** below the jaw centre - `GRASP_STANDOFF = DISTAL_Z - LIP` - and it
is **constant across the aperture** because the synergy is radial only (the
plate's axial mid-plane does not move). **Measured spread: 0.00 mm over nine
apertures** (`logs/p107/m1_cage.txt`). That is the number P106 could not have on
the Allegro (its fingertip centroid read 100-216 mm across a posture sweep).
Because 70.0 mm is also `FRUIT_FINGER_LEN` 60 + `PAD_LIFT` 10, the shipped aim
expressions are unchanged for this hand - the coincidence is a *consequence* of
the derivation, not a reuse of the jaws' number.

**Three facts this mount has to live with, all measured and reported.**

1. **`pad width <= aperture`.** Four plates of half-width `w/2` meet at the
   corners when the face radius equals `w/2`, so the shipped 61 mm plate is legal
   only above a 61 mm aperture - i.e. for the pool's two largest classes. The
   width is cut to 26 mm (the smallest aperture's own). The **capacity is
   unaffected**: `F_crit = n * mu * N` is area-independent (P104 section 2), so
   the licensed 4-contact number is about the count, not the plate.
2. **The plate's axial length is bounded above by the hand it is bolted to**
   (4.4 mm above the jaw centre is inside the palm; measured as `|a|max` 2421
   m/s2 and the payload ejected).
3. **The OpenArm's finger plates keep their _asset_ colliders** even with
   `FRUIT_FINGER_COLLIDERS=0` (that flag only *adds* the flat faces), so
   `author_cage` disables them - exactly what `KinematicGripper` does for its
   pads. Without it the cage's pads jam against the fingers with the aperture
   frozen at 89 mm.

**Scope.** Default off: nothing here exists unless `FRUIT_GRIPPER_KIND=cage4`.
The shipped `openarm` hand, its collider set, its materials and every default
are untouched (`FRUIT_GRIPPER_KIND` unset -> `openarm`, byte-identical; the
acceptance's 421 `[fruit]` lines replay byte-for-byte).

**What it does not answer, stated before any number** (`logs/p107/RESULTS.md`):
a radial cage needs its axis on the fruit *before* the descent, and this cell's
aim is a point hand's - so the retrofit measures the **integration**, not the
pad. M2b's letter passes while its mechanism fails and M3 kills; the next spend
is a centring step or a workstation, not a hand.

Authoring happens at **build** time (`scene.build`, before `play()`) because the
contact-tracking flags must be set before the physics views are built
(`tactile.GripperTactile.attach`'s contract); the *driver* below writes the base
pose and the four drive targets every control tick (`track_arm`), because a hand
mounted on the tool has to be on the tool at all times.
"""

from __future__ import annotations

import math
import os

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from .common import say

def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        raise SystemExit(f"{name} must be a number, got {os.environ.get(name)!r}")


def cage_enabled() -> bool:
    return os.environ.get("FRUIT_GRIPPER_KIND", "openarm") == CAGE_KIND


#: `FRUIT_GRIPPER_KIND` value that selects this hand.
CAGE_KIND = "cage4"

#: The measured pad plate (`logs/p66/COLLIDER_READ.md`, `logs/p104/fixture_probe.py`).
PLATE_WIDTH = 0.0610
PLATE_LENGTH = 0.0849
#: Smallest face radius the cage is commanded to [m]: a 26 mm aperture clears the
#: smallest pool fruit (37 mm) with the 2 % squeeze.
MIN_FACE_R = _f("FRUIT_CAGE_MIN_FACE_R", 0.013)
#: **The pad width is cut, and this is the retrofit's first measured design
#: iteration.** Four 61 mm plates at 4 x 90 deg have corners that intersect below
#: a 61 mm aperture (`pad_width <= aperture` is the constraint: adjacent faces
#: meet when the face radius equals the plate's half width), and with *dynamic*
#: pads they do not merely overlap - they **collide with each other**, jam the
#: cage and crush the payload (measured: 69-100 N per pad against a 4.9 N drive
#: cap, `logs/p107/smoke4.log`). The width is therefore the largest legal one,
#: `2 * MIN_FACE_R` = 26 mm, while the **84.9 mm length (the lip) is kept**, and
#: the Coulomb capacity is area-independent (`n * mu * N`, P104 section 2), so
#: the four-contact capacity is the licensed one - only the lip's *width* shrinks.
PAD_WIDTH = _f("FRUIT_CAGE_PAD_WIDTH", 2.0 * MIN_FACE_R)
#: **The pad length is cut too, and the reason is the mount**, not the grip. The
#: shipped plate is 84.902 mm long with its distal plane 80.5 mm below the jaw
#: centre, so its *proximal* end sits **4.4 mm above** the jaw centre - inside the
#: hand it is mounted on. With dynamic pads that is a hard contact with the
#: OpenArm's own palm, and it thrashes the arm (measured: `|v|max` 20 m/s,
#: `|a|max` 2421 m/s^2, the payload ejected, `logs/p107/smoke5.log`). Cutting the
#: length to 60 mm while **keeping the distal plane at 80.5 mm** moves the
#: proximal end to 20.5 mm below the jaw centre, and changes neither the lip
#: (10.5 mm) nor the tool offset (70.0 mm) - the two numbers the grasp needs.
CAGE_PLATE_LENGTH = _f("FRUIT_CAGE_PAD_LENGTH", 0.060)
PAD_THICK = 0.010
PAD_MASS = 0.020

#: `tasks.FINGER_TIP_BELOW_JAW` - the shipped plate's distal plane below the jaw
#: centre. Kept as a literal here (not imported) so this module can be imported
#: by the scene before `tasks` is; `tasks` asserts they agree (`_cage_assert`).
DISTAL_Z = 0.0805
#: The shipped pinch's distal lip below the payload's equator.
LIP = 0.0105


#: Face radius of the open cage [m]: aperture = 2x this. 45 mm -> a 90 mm
#: aperture, 12 mm/side over the largest pool fruit (66 mm).
HOME_FACE_R = _f("FRUIT_CAGE_OPEN_FACE_R", 0.060)
#: The line's own "open" command (`FRUIT_GRIPPER_OPEN`, 90 mm for the jaws). A
#: command at or above it means "open", which for this hand is *its* aperture -
#: 120 mm, because the open cage has to swallow the shipped line's **pursuit
#: error** (the arm reaches the aim to ~8 mm but the fruit can sit 24 mm off the
#: cage's axis when the descent starts; a 90 mm aperture leaves 12 mm of radial
#: slack and the pads hit the fruit on the way down - measured `clr = -20.5 mm`
#: and a 546 mm bat, `logs/p107/smoke9.log`).
SHIPPED_OPEN = _f("FRUIT_GRIPPER_OPEN", 0.090)
#: Closed limit of the joint travel [m]; the smallest pool fruit with squeeze
#: needs `HOME_FACE_R - 0.013` = 32 mm of it.
STROKE = HOME_FACE_R - MIN_FACE_R
#: Per-pad force cap [N]. `4.90` = the shipped pinch's delivered per-face force
#: (P41), which is P104's own per-contact value; the asset's 10 N/joint cap is 2x
#: that and would confound contact *count* with force (P76 measured that force
#: alone does not convert the class).
PAD_FORCE = _f("FRUIT_CAGE_PAD_FORCE", 4.90)
#: The shipped finger drive (`control.finger_drive_profile`, `finger_damp02`).
PAD_STIFFNESS = _f("FRUIT_CAGE_PAD_STIFFNESS", 100000.0)
#: **100**, not the shipped fingers' 2000: `2*sqrt(k*m)` for the fixture's
#: 0.020 kg pad is 89 Ns/m, and a standalone (non-articulation) prismatic joint
#: with `c = 2000` at 120 Hz is numerically unstable - measured as a cage whose
#: pads did not track their targets and put 90-100 N into the payload
#: (`logs/p107/smoke3.log`). This is P104's own per-contact default ("near
#: critically damped for the pad mass below, 2*sqrt(k*m) = 89"), i.e. the exact
#: pair that produced the licensed 1.87-2.05x numbers.
PAD_DAMPING = _f("FRUIT_CAGE_PAD_DAMPING", 100.0)
#: **The hard stop** (P111, default off = the shipped single-profile drive).
#: A compliant closure is only half a hand: at `k = 1e3` the delivered force at
#: the shipped squeeze is `k*s` = 0.7 N per pad (a 4-7x weaker hold than the
#: 4.90 N the rigid drive delivers), because the *cap* is never reached.  A real
#: spring-loaded pad bottoms out, and that is what this authors: when the close's
#: command settles, the four drives are re-written at `FRUIT_CAGE_HOLD_STIFFNESS`
#: (default 0 = off) with the target unchanged, so the pad re-loads to
#: `min(k_hold * penetration, cap)` = the cap, at the aperture it found.
#: The soft pair is what the *close* runs; the firm pair is what the *carry*
#: holds with.  `logs/p111/RESULTS.md` prices both halves.
#: **The close window** (P111, default off = the shipped single-profile drive).
#: P111 measured why the compliance has to be *scoped*: a `k = 1e3` pad is a weak
#: **position source**, so during the approach and the descent - where the plates
#: are pushed by whatever they meet - it is displaced instead of holding the
#: ring's geometry, and the cell's jams and huge non-payload contacts multiply
#: (`T1` 1/20 placed against the rigid ring's 7/19).  A real compliant pad is
#: stiff until it is loaded; this authors that window: the drives are
#: `FRUIT_CAGE_CLOSE_STIFFNESS` between the close's start and its freeze, and the
#: approach/hover/descent keep the authored `FRUIT_CAGE_PAD_STIFFNESS`.
CLOSE_STIFFNESS = _f("FRUIT_CAGE_CLOSE_STIFFNESS", 0.0)
#: Damping of the close profile; 0 (the default) means `2*sqrt(k_close*m)`.
CLOSE_DAMPING = _f("FRUIT_CAGE_CLOSE_DAMPING", 0.0)
HOLD_STIFFNESS = _f("FRUIT_CAGE_HOLD_STIFFNESS", 0.0)
#: Damping of the hold profile; 0 (the default) means `2*sqrt(k_hold*m)`, the
#: same near-critical rule as `PAD_DAMPING`.
HOLD_DAMPING = _f("FRUIT_CAGE_HOLD_DAMPING", 0.0)
#: Pad contact friction; the shipped finger material's own value (P104: PhysX
#: combines the pair by average, measured `mu_app` 1.05-1.45).
PAD_MU = _f("FRUIT_CAGE_PAD_MU", 2.0)
#: Displacement from the jaw centre down to the **payload's centre** at the
#: equatorial seat - the number that replaces `_pad_standoff` (0.070 m).
GRASP_STANDOFF = DISTAL_Z - LIP
#: Displacement from the jaw centre down to the **pads' own mid-plane**.
PAD_MID_OFFSET = DISTAL_Z - CAGE_PLATE_LENGTH / 2.0

#: Pad azimuths. 0 deg = the shipped jaw-open direction, +90 = across it.
THETAS = (0.0, 90.0, 180.0, 270.0)


def _material(stage, path: str):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.16, 0.42, 0.62))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    api.CreateStaticFrictionAttr().Set(PAD_MU)
    api.CreateDynamicFrictionAttr().Set(PAD_MU)
    api.CreateRestitutionAttr().Set(0.0)
    return mat


def cage_root(side: str) -> str:
    return f"/World/Cage_{side}"


def pad_paths(side: str) -> list[str]:
    return [f"{cage_root(side)}/Pad{k}" for k in range(len(THETAS))]


def author_cage(stage, side: str) -> None:
    """Author the four-pad cage under `/World/Cage_<side>` (at a park pose).

    The root is a **kinematic** body placed at the jaw centre every tick (see
    `CageHand.follow_centre`), so the pads ride the arm rigidly except for their
    own radial joints - the `actuated_gripper.py` mount model, which is the one
    this tree already measured stable. The root carries **no collider**: it sits
    inside the arm's own wrist and a kinematic collider there pushes the arm
    (`logs/432`).
    """
    root = cage_root(side)
    stage.DefinePrim(root, "Xform")

    home = Gf.Vec3d(0.0, 0.0, -3.0)
    # The **base must carry no scale**: the four joints' `localPos0` are expressed
    # in this body's local space, and a scale op on a rigid-body prim scales them -
    # measured as eight "found a joint with disjointed body transforms" warnings
    # and a cage whose pads collapsed onto the wrist (`logs/p107/m1_cage.txt`
    # first runs). The visual is a child cube, exactly like the pads' plates.
    base = UsdGeom.Xform.Define(stage, f"{root}/Base")
    bxf = UsdGeom.Xformable(base)
    bxf.ClearXformOpOrder()
    bxf.AddTranslateOp().Set(home)
    UsdPhysics.RigidBodyAPI.Apply(base.GetPrim()).CreateKinematicEnabledAttr().Set(True)
    UsdPhysics.MassAPI.Apply(base.GetPrim()).CreateMassAttr().Set(0.30)
    flange = UsdGeom.Cube.Define(stage, f"{root}/Base/Flange")
    flange.GetSizeAttr().Set(1.0)
    fxf = UsdGeom.Xformable(flange)
    fxf.ClearXformOpOrder()
    fxf.AddScaleOp().Set(Gf.Vec3f(0.070, 0.070, 0.016))
    UsdShade.MaterialBindingAPI.Apply(flange.GetPrim()).Bind(
        _material(stage, f"{root}/Base/Flange_mat")
    )
    # NB: no `UsdPhysics.CollisionAPI` anywhere on the base - see the docstring.

    for k, theta in enumerate(THETAS):
        th = np.deg2rad(theta)
        u = np.array([np.cos(th), np.sin(th), 0.0])
        roll = th + np.pi / 2.0  # the joint frame's +Y -> -u (inward)
        centre = u * (HOME_FACE_R + PAD_THICK / 2.0) + np.array([0.0, 0.0, PAD_MID_OFFSET])
        body_path = f"{root}/Pad{k}"
        body = UsdGeom.Xform.Define(stage, body_path)
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
        UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr().Set(PAD_MASS)
        bxf = UsdGeom.Xformable(body)
        bxf.ClearXformOpOrder()
        bxf.AddTranslateOp().Set(
            Gf.Vec3d(*[float(c + h) for c, h in zip(centre, (0.0, 0.0, -3.0))])
        )
        bxf.AddRotateZOp().Set(float(np.rad2deg(roll)))

        cube = UsdGeom.Cube.Define(stage, f"{body_path}/Pad")
        cube.GetSizeAttr().Set(1.0)
        cxf = UsdGeom.Xformable(cube)
        cxf.ClearXformOpOrder()
        cxf.AddScaleOp().Set(Gf.Vec3f(PAD_WIDTH, PAD_THICK, CAGE_PLATE_LENGTH))
        UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
        UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(
            _material(stage, f"{body_path}/Pad_mat")
        )

        joint = UsdPhysics.PrismaticJoint.Define(stage, f"{body_path}_joint")
        joint.CreateBody0Rel().SetTargets([f"{root}/Base"])
        joint.CreateBody1Rel().SetTargets([body_path])
        joint.CreateAxisAttr().Set("Y")
        joint.CreateLowerLimitAttr().Set(0.0)
        joint.CreateUpperLimitAttr().Set(float(STROKE))
        joint.CreateLocalPos0Attr().Set(Gf.Vec3f(*[float(c) for c in centre]))
        joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        joint.CreateLocalRot0Attr().Set(
            Gf.Quatf(float(np.cos(roll / 2.0)), 0.0, 0.0, float(np.sin(roll / 2.0)))
        )
        joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
        drive.CreateTypeAttr().Set("force")
        drive.CreateStiffnessAttr().Set(PAD_STIFFNESS)
        drive.CreateDampingAttr().Set(PAD_DAMPING)
        drive.CreateMaxForceAttr().Set(PAD_FORCE)
        drive.CreateTargetPositionAttr().Set(0.0)

    # The OpenArm's own finger plates keep their **asset** colliders even with
    # `FRUIT_FINGER_COLLIDERS=0` (that flag only *adds* the flat faces). The cage
    # is mounted at the same place, so its pads sit inside the fingers' own
    # volume and jam against them: measured 4.3-30.8 N per pad with the aperture
    # frozen at 89 mm, the arm thrashed (`|a|max` 132-246 m/s^2) and no payload
    # held (`logs/p107/smoke6.log`). Disable them, exactly as `KinematicGripper`
    # does for its pads (an attribute override reaches the instanced asset where
    # a new prim does not).
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    for which in ("left", "right"):
        link = stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_{which}_finger")
        if not link.IsValid():
            continue
        for prim in Usd.PrimRange(link, proxies):
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)

    say(
        f"[cage] {side}: 4 pads at {len(THETAS)}x{360 // len(THETAS)} deg, plate "
        f"{PAD_WIDTH * 1000:.3f} x {CAGE_PLATE_LENGTH * 1000:.3f} mm (shipped "
        f"{PLATE_WIDTH * 1000:.3f} x {PLATE_LENGTH * 1000:.3f}, width cut to the "
        f"legal {2 * MIN_FACE_R * 1000:.1f} and length to clear the flange), aperture "
        f"{2 * HOME_FACE_R * 1000:.1f} -> {2 * (HOME_FACE_R - STROKE) * 1000:.1f} mm, "
        f"drive k={PAD_STIFFNESS:.0f} N/m c={PAD_DAMPING:.0f} Ns/m "
        f"cap={PAD_FORCE:.2f} N/pad, "
        f"tool offset={GRASP_STANDOFF * 1000:.1f} mm"
        + (
            f", close k={CLOSE_STIFFNESS:.0f} N/m "
            f"c={(CLOSE_DAMPING if CLOSE_DAMPING > 0 else 2.0 * math.sqrt(CLOSE_STIFFNESS * PAD_MASS)):.1f} Ns/m "
            f"(the closure window only)"
            if CLOSE_STIFFNESS > 0
            else ""
        )
        + (
            f", hold k={HOLD_STIFFNESS:.0f} N/m "
            f"c={(HOLD_DAMPING if HOLD_DAMPING > 0 else 2.0 * math.sqrt(HOLD_STIFFNESS * PAD_MASS)):.1f} Ns/m "
            f"(the hard stop: soft close, firm carry)"
            if HOLD_STIFFNESS > 0
            else ""
        )
    )


def _quat_matrix(quat) -> np.ndarray:
    w, x, y, z = (float(v) for v in quat)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def _quat_from_z_to(direction) -> np.ndarray:
    """Quaternion (w, x, y, z) rotating +Z onto `direction` (unit)."""
    vec = np.asarray(direction, dtype=float)
    vec = vec / max(float(np.linalg.norm(vec)), 1e-9)
    z = np.array([0.0, 0.0, 1.0])
    dot = float(np.clip(np.dot(z, vec), -1.0, 1.0))
    if dot > 1.0 - 1e-9:
        return np.array([1.0, 0.0, 0.0, 0.0])
    if dot < -1.0 + 1e-9:
        return np.array([0.0, 1.0, 0.0, 0.0])
    axis = np.cross(z, vec)
    angle = float(np.arccos(dot))
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    half = angle / 2.0
    return np.array([np.cos(half), *(axis * np.sin(half))])


def _quat_mul(a, b) -> np.ndarray:
    aw, ax, ay, az = (float(v) for v in a)
    bw, bx, by, bz = (float(v) for v in b)
    return np.array(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ]
    )


def _quat_from_matrix(rot) -> np.ndarray:
    """Quaternion (w, x, y, z) of a rotation matrix (Shepperd's method)."""
    m = np.asarray(rot, dtype=float)
    trace = float(m[0, 0] + m[1, 1] + m[2, 2])
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        return np.array(
            [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s,
             (m[1, 0] - m[0, 1]) / s]
        )
    if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        return np.array(
            [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s,
             (m[0, 2] + m[2, 0]) / s]
        )
    if m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        return np.array(
            [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s,
             (m[1, 2] + m[2, 1]) / s]
        )
    s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
    return np.array(
        [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s,
         0.25 * s]
    )


class CageHand:
    """The four-pad cage as the task's hand (`kind = "cage4"`).

    The interface is the OpenArm hand's - `follow_centre(centre, quat, gap)`,
    `pad_centre()`, `pad_faces()` - so the grasp, close, carry and release code
    is unchanged. The differences are physical:

    * `gap` is a **face separation** (an aperture) and one command moves all
      four pads (**the synergy**); each pad's drive is force-capped at
      `FRUIT_CAGE_PAD_FORCE`, so the delivered normal force is set by the cap and
      not by the command's depth (P104's own protocol);
    * the root is teleported to the arm's **measured jaw pose** every tick, so
      the cage rides the arm rigidly and `pad_centre()` is the four faces'
      centroid (a real body read, not the arm's estimate).
    """

    kind = CAGE_KIND

    def __init__(self, stage, side: str, arm, mu: float | None = None):
        self.stage = stage
        self.side = side
        self.arm = arm
        self.mu = float(os.environ.get("FRUIT_CAGE_PAD_MU", str(PAD_MU))) if mu is None else mu
        self.enabled = cage_enabled()
        self.highlight = False
        self.v_max = 0.0
        #: Replaces `_pad_standoff`: jaw centre -> payload centre at the seat.
        self.grasp_standoff = GRASP_STANDOFF
        #: Jaw centre -> the pads' own mid-plane (the slip/diag frame).
        self.pad_mid_offset = PAD_MID_OFFSET
        #: The plate's distal lip below the payload's equator.
        self.lip = LIP
        #: P107: the cage has no assisted "pad frame" - its pads *are* the tool,
        #: so the carry must take `_carry`'s coherent branch even when the
        #: fingertip tracker's error is above the fallback threshold (the
        #: shipped OpenArm hand legitimately falls back; this hand must not).
        self.always_coherent = True
        self.root = cage_root(side)
        self.open_gap = 2.0 * HOME_FACE_R
        self.last_gap = self.open_gap
        self._placed = False
        self._correction = None
        #: P111: True while the drives are on the *hold* profile (the hard stop).
        self._stiffened = False
        if not self.enabled:
            return
        from isaacsim.core.experimental.prims import RigidPrim

        self._base = RigidPrim(f"{self.root}/Base")
        self._pads = [RigidPrim(path) for path in pad_paths(side)]
        self._drives = [
            UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{self.root}/Pad{k}_joint"), "linear")
            for k in range(len(THETAS))
        ]
        #: The base pose the pads' joints were last told about. A **jump** (an
        #: arm teleport, the attempt loop's `go_ready`, a park) is written as a
        #: pose step of metres, and a kinematic body's implied velocity is then
        #: hundreds of m/s - the pads inherit it through the joints and are
        #: launched out of the cell (measured: 1e4-1e8 m pad positions,
        #: `logs/p107/m1_cage.txt`). After a jump the pads' velocities are
        #: zeroed, so the drives take over from rest.
        self._base_prev: np.ndarray | None = None
        self._jump_m = _f("FRUIT_CAGE_JUMP_M", 0.020)
        self._jumps = 0
        self._place(self.open_gap)

    # ------------------------------------------------------------------ #
    def _write_base(self, jaw, q_base) -> None:
        jaw = np.asarray(jaw, dtype=float)
        jump = self._base_prev is None or float(np.linalg.norm(jaw - self._base_prev)) > self._jump_m
        self._base.set_world_poses(positions=[jaw.tolist()], orientations=[q_base.tolist()])
        self._base_prev = jaw.copy()
        if jump:
            self._jumps += 1
            # The pads are *rigidly* carried by the base except along their own
            # prismatic axes, so a base jump hands them the base's implied
            # velocity. Zero it: the drives then close from rest.
            for prim in self._pads:
                try:
                    prim.set_velocities(
                        linear_velocities=[[0.0, 0.0, 0.0]],
                        angular_velocities=[[0.0, 0.0, 0.0]],
                    )
                except Exception:  # noqa: BLE001 - a probe must not stop a run
                    pass

    def track_arm(self) -> None:
        """Re-seat the cage on the arm's measured pose (every control tick).

        A hand mounted on the tool has to *be* on the tool at all times, including
        the pre-pose, the hover and the descent - phases in which the shipped
        OpenArm hand needs no call because its fingers are the arm's own links.
        Without this the cage stays where the last `follow_centre` left it (for a
        whole attempt: at the previous grip pose, at belt height, in the supply's
        path - measured as 5 fruit knocked off the belt and two starved slots,
        `logs/p107/smoke8.log`). One base write and one aperture re-command.
        """
        if not self.enabled:
            return
        quat = np.asarray(self.arm.tcp_pose()[1], dtype=float)
        jaw = np.asarray(self.arm.jaw_centre(), dtype=float)
        self._write_base(jaw, _quat_mul(quat, self._tool_correction(quat)))
        self._command(self.last_gap)

    def _pad_targets(self, aperture: float) -> list[tuple[np.ndarray, np.ndarray]]:
        """The four pads' rest (world position, world quaternion) at an aperture."""
        base_pos, base_quat = self._base.get_world_poses()
        base_pos = np.asarray(base_pos.numpy())[0].astype(float)
        base_quat = np.asarray(base_quat.numpy())[0].astype(float)
        rot = _quat_matrix(base_quat)
        out = []
        for centre, pad_rot in pad_boxes(aperture):
            out.append((base_pos + rot @ centre, _quat_from_matrix(rot @ pad_rot)))
        return out

    def _place(self, aperture: float) -> None:
        """Put the four pads at `aperture` (used by `park` and by a jump)."""
        for prim, (pos, quat) in zip(self._pads, self._pad_targets(aperture)):
            prim.set_world_poses(positions=[pos.tolist()], orientations=[quat.tolist()])
        self._aperture = float(aperture)

    def _command(self, gap: float) -> None:
        """The **single closure synergy**: one aperture -> four radial targets.

        Every pad gets the same travel, so one scalar closes all four - the
        definition of a synergy. Each pad's drive is force-capped at
        `FRUIT_CAGE_PAD_FORCE`, so the delivered normal force is the cap and the
        *shape* (four contacts + the lip) is what varies against the shipped
        two-pad pinch (P104 section 2).

        P111: an **open** command also releases the hard stop, so the next close
        runs the soft profile again. The open command is `FRUIT_GRIPPER_OPEN`
        (90 mm) or anything above it - exactly what the pre-pose, the hover and
        `park()` send - so the release needs no extra call site.
        """
        gap = float(gap)
        if gap >= SHIPPED_OPEN - 1e-9:
            gap = self.open_gap
            if self._stiffened:
                self._profile(PAD_STIFFNESS, PAD_DAMPING)
        gap = float(np.clip(gap, 2.0 * (HOME_FACE_R - STROKE), self.open_gap))
        travel = float(np.clip(HOME_FACE_R - gap / 2.0, 0.0, STROKE))
        for drive in self._drives:
            drive.CreateTargetPositionAttr().Set(travel)
        self._aperture = gap
        self.last_gap = gap

    def _profile(self, stiffness: float, damping: float) -> None:
        """Re-write the four drives' stiffness/damping (the cap and target stay).

        A write with the profile already in place is skipped, so the two window
        calls (`close_begin`/`close_done`) are free when their knobs are unset -
        the shipped cage issues no drive write at all.
        """
        stiffness, damping = float(stiffness), float(damping)
        have = self._drives[0].CreateStiffnessAttr().Get()
        have_c = self._drives[0].CreateDampingAttr().Get()
        if (
            have is not None
            and have_c is not None
            and abs(float(have) - stiffness) < 1e-9
            and abs(float(have_c) - damping) < 1e-9
        ):
            return
        for drive in self._drives:
            drive.CreateStiffnessAttr().Set(stiffness)
            drive.CreateDampingAttr().Set(damping)
        self._stiffened = stiffness != PAD_STIFFNESS

    def close_begin(self) -> None:
        """The close starts: swap to the **close** profile if one is set (P111).

        A no-op unless `FRUIT_CAGE_CLOSE_STIFFNESS` is set, so the shipped cage
        and P111's always-soft arms are unchanged.  See the knob's note: the
        compliance must be *scoped* to the closure, because a soft pad cannot
        hold the ring's geometry while the approach pushes on it.
        """
        if not self.enabled:
            return
        if CLOSE_STIFFNESS <= 0.0:
            return
        damping = (
            CLOSE_DAMPING
            if CLOSE_DAMPING > 0.0
            else 2.0 * math.sqrt(CLOSE_STIFFNESS * PAD_MASS)
        )
        self._profile(CLOSE_STIFFNESS, damping)

    def close_done(self) -> None:
        """The close's depth is settled: load the pad, or end the close window.

        Called **once per attempt** by the task, right after the close decides
        the gap the carry will hold.  Two forms, one knob each, both default off:

        * `FRUIT_CAGE_HOLD_STIFFNESS` set -> the **hard stop**: the four drives
          are re-written at the hold profile with their target unchanged, so a
          soft close re-loads to `min(k_hold * penetration, cap)` = the cap **at
          the aperture it found**.  The pad body cannot move (the payload is in
          the way), so the stop loads the grip without shifting the aperture.
        * only `FRUIT_CAGE_CLOSE_STIFFNESS` set -> the close window ends and the
          drives go back to the authored approach profile (the compliance was
          scoped to the closure).

        Why the stop is not optional for an always-soft arm: the close's
        delivered force is `min(k_close * penetration, cap)`, and at `k = 1e3`
        the shipped 1 % squeeze gives **0.7 N** per pad - a 4-7x weaker hold than
        the rigid ring's 4.90 N, so the arm would lose placements for a *grip*
        reason and could not answer the centring question.
        """
        if not self.enabled:
            return
        if HOLD_STIFFNESS > 0.0:
            damping = (
                HOLD_DAMPING
                if HOLD_DAMPING > 0.0
                else 2.0 * math.sqrt(HOLD_STIFFNESS * PAD_MASS)
            )
            self._profile(HOLD_STIFFNESS, damping)
            say(
                f"[cage] {self.side}: hard stop at the close (k {PAD_STIFFNESS:.0f} -> "
                f"{HOLD_STIFFNESS:.0f} N/m, c {PAD_DAMPING:.0f} -> {damping:.1f} Ns/m, "
                f"aperture {self._aperture * 1000:.1f} mm, cap {PAD_FORCE:.2f} N/pad)"
            )
            return
        if CLOSE_STIFFNESS > 0.0:
            # the close window ends here: back to the authored approach profile
            self._profile(PAD_STIFFNESS, PAD_DAMPING)
            say(
                f"[cage] {self.side}: close window end (k {CLOSE_STIFFNESS:.0f} -> "
                f"{PAD_STIFFNESS:.0f} N/m, aperture {self._aperture * 1000:.1f} mm)"
            )

    def command_gap(self, gap: float) -> None:
        self._command(gap)

    def park(self) -> None:
        """Open the cage and keep it on the arm (no far-away home).

        The old far home was (0, 0, -3); sending the base there and back is a
        3 m pose step, which is what launched the pads. The cage is a tool on the
        arm, so "park" is simply "open, where the arm is".
        """
        if not self.enabled:
            return
        quat = np.asarray(self.arm.tcp_pose()[1], dtype=float)
        jaw = np.asarray(self.arm.jaw_centre(), dtype=float)
        self._write_base(jaw, _quat_mul(quat, self._tool_correction(quat)))
        self._command(self.open_gap)
        self._place(self.open_gap)
        self._placed = False

    def _tool_correction(self, quat) -> np.ndarray:
        """Local +Z -> the arm's own "down the fingers" direction, in the TCP frame.

        Constant while the hand is rigidly mounted: both the TCP pose and the
        measured jaw->TCP axis rotate together, so it is computed once.
        """
        if self._correction is not None:
            return self._correction
        rot = _quat_matrix(quat)
        down = np.asarray(self.arm.approach_axis(), dtype=float)
        local = rot.T @ down
        self._correction = _quat_from_z_to(local)
        return self._correction

    def follow_centre(self, centre, quat, gap: float) -> np.ndarray:
        """Ride the arm and close the synergy. `centre` is not used.

        The cage is a **rigid tool**: its pose is the arm's pose, so the pads are
        where the arm put them (the `coherent` branch of `tasks._carry`). `centre`
        is accepted for interface compatibility and ignored, exactly like
        `OpenArmHand.follow_centre`.
        """
        if not self.enabled:
            return np.asarray(centre, dtype=float)
        quat = np.asarray(quat, dtype=float)
        jaw = np.asarray(self.arm.jaw_centre(), dtype=float)
        q_base = _quat_mul(quat, self._tool_correction(quat))
        rot = _quat_matrix(q_base)
        self._write_base(jaw, q_base)
        self._placed = True
        self._command(gap)
        return jaw

    # ------------------------------------------------------------------ #
    def _pad_world(self) -> tuple[np.ndarray, np.ndarray]:
        base_pos, base_quat = self._base.get_world_poses()
        rot = _quat_matrix(np.asarray(base_quat.numpy())[0])
        pts = np.array(
            [np.asarray(p.get_world_poses()[0].numpy())[0] for p in self._pads], dtype=float
        )
        return pts, rot

    def base_pose(self) -> tuple[np.ndarray, np.ndarray]:
        """World pose of the cage's kinematic root (the jaw centre + tool frame)."""
        pos, quat = self._base.get_world_poses()
        return (
            np.asarray(pos.numpy())[0].astype(float),
            np.asarray(quat.numpy())[0].astype(float),
        )

    def pad_centre(self) -> np.ndarray:
        """Centroid of the four pad bodies (a real read; the slip monitor's frame)."""
        if not self.enabled:
            return np.zeros(3)
        return np.asarray(self._pad_world()[0], dtype=float).mean(axis=0)

    def pad_faces(self) -> tuple[np.ndarray, np.ndarray]:
        pts, rot = self._pad_world()
        u = rot @ np.array([1.0, 0.0, 0.0])
        inward = pts[0] - u * (PAD_THICK / 2.0)
        inward2 = pts[2] + u * (PAD_THICK / 2.0)
        return inward, inward2

    def apertures(self) -> tuple[float, ...]:
        """Measured face-to-face aperture on each of the two axes [m]."""
        pts, rot = self._pad_world()
        out = []
        for axis, (i, j) in enumerate(((0, 2), (1, 3))):
            u = rot @ np.eye(3)[axis]
            a = float(np.dot(pts[i] - pts[j], u)) - PAD_THICK
            out.append(abs(a))
        return tuple(out)

    def separation(self) -> float:
        return float(np.mean(self.apertures()))

    def pad_dirs(self) -> np.ndarray:
        """World radial direction of each pad (4x3)."""
        _, rot = self._pad_world()
        dirs = []
        for theta in THETAS:
            u = np.array([np.cos(np.deg2rad(theta)), np.sin(np.deg2rad(theta)), 0.0])
            dirs.append(rot @ u)
        return np.asarray(dirs, dtype=float)

    def summary(self) -> str:
        if not self.enabled:
            return f"cage {self.side}: disabled"
        a = self.apertures()
        profile = (
            f"k={PAD_STIFFNESS:.0f}/{HOLD_STIFFNESS:.0f} N/m"
            if HOLD_STIFFNESS > 0.0
            else f"k={PAD_STIFFNESS:.0f} N/m"
        )
        return (
            f"cage hand {self.side}: aperture_cmd={self.last_gap * 1000:.1f}mm "
            f"measured=({a[0] * 1000:.1f},{a[1] * 1000:.1f})mm "
            f"cap={PAD_FORCE:.2f}N/pad mu={self.mu:.2f} "
            f"drive={profile}{'(hold)' if self._stiffened else ''} "
            f"tool_offset={self.grasp_standoff * 1000:.1f}mm"
        )


def pad_boxes(aperture: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """The four pads' (centre, rotation) in the **base frame** at an aperture.

    Pure arithmetic on the authored geometry (`HOME_FACE_R`, `PAD_THICK`,
    `PLATE_*`), so a diagnostic can read the cage's own commanded state from one
    base-pose read instead of four body reads. The pad's local frame is
    `X = width (tangential), Y = thickness (radial), Z = length (axial)`; the
    same convention `author_cage` writes.
    """
    half = float(np.clip(aperture, 2.0 * (HOME_FACE_R - STROKE), 2.0 * HOME_FACE_R)) / 2.0
    out = []
    for theta in THETAS:
        th = np.deg2rad(theta)
        roll = th + np.pi / 2.0
        u = np.array([np.cos(th), np.sin(th), 0.0])
        centre = u * (half + PAD_THICK / 2.0) + np.array([0.0, 0.0, PAD_MID_OFFSET])
        c, s = np.cos(roll), np.sin(roll)
        rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        out.append((centre, rot))
    return out


def _box_distance(point_local: np.ndarray, half: np.ndarray) -> float:
    """Unsigned distance from a point to a box surface, in the box's own frame."""
    rel = np.abs(np.asarray(point_local, dtype=float)) - half
    outside = np.maximum(rel, 0.0)
    inside = min(float(np.max(rel)), 0.0)
    return float(np.linalg.norm(outside) + inside)


def pad_fruit_clearance(
    base_pos, base_quat, aperture: float, fruit, radius: float
) -> tuple[float, int]:
    """Closest **pad surface to fruit surface** distance at an aperture [m].

    The payload is the sphere proxy the tree already uses for clearance
    (`diameter / 2`); the pads are the authored boxes. Returns
    `(clearance, nearest_pad_index)`; positive = separated, negative =
    interpenetrating (which is what the close's squeeze *is*).
    """
    rot = _quat_matrix(base_quat)
    local = rot.T @ (np.asarray(fruit, dtype=float) - np.asarray(base_pos, dtype=float))
    half = np.array([PAD_WIDTH / 2.0, PAD_THICK / 2.0, CAGE_PLATE_LENGTH / 2.0])
    best, best_k = float("inf"), -1
    for k, (centre, pad_rot) in enumerate(pad_boxes(aperture)):
        point = pad_rot.T @ (local - centre)
        gap = _box_distance(point, half) - float(radius)
        if gap < best:
            best, best_k = gap, k
    return best, best_k
