"""Builds the bimanual fruit-sorting cell in Isaac Sim 6.

Layout (robot at the origin, facing +X):

    +Y  upstream   [ raised output belt, travel +X ]  [ left arm ]
     ^                             | discharge chute -> tray
     |   ================= main conveyor, fruit travel -Y =================
     |                 [ pedestal + OpenArm + head camera ]
     |   [ raised output belt, travel +X ]  [ right arm ]
    -Y  downstream                | discharge chute -> tray

The robot lifts a fruit off the main line and sets it down on the raised output
belt beside it; that belt carries it away along +X. One RGB-D camera is mounted
above the torso where a humanoid head would be; that is the single camera
available to the policy.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import numpy as np
from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import DistantLight, GroundPlane
from isaacsim.core.experimental.prims import Articulation, RigidPrim
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

from .assets import (
    OPENARM_BIMANUAL_USD,
    OPENARM_TCP_LINKS,
    FingerColliderError,
    FingerColliderVerdict,
    SceneConfig,
    assert_finger_colliders,
)
from .common import look_at_quat, say, substeps, to_numpy


def _define_box(stage: Usd.Stage, path: str, size: tuple[float, float, float], center: tuple[float, float, float]):
    """Axis-aligned box authored as a unit cube plus a scale xform."""
    prim = UsdGeom.Cube.Define(stage, path)
    prim.GetSizeAttr().Set(1.0)
    xformable = UsdGeom.Xformable(prim)
    xformable.ClearXformOpOrder()
    xformable.AddTranslateOp().Set(Gf.Vec3d(*center))
    xformable.AddScaleOp().Set(Gf.Vec3f(*size))
    return prim


def _quat_to_matrix(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    n = np.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def _matrix_to_quat(r: np.ndarray) -> list[float]:
    trace = float(np.trace(r))
    if trace > 0.0:
        s = np.sqrt(trace + 1.0) * 2.0
        q = [0.25 * s, (r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s]
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2.0
        q = [(r[2, 1] - r[1, 2]) / s, 0.25 * s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s]
    elif r[1, 1] > r[2, 2]:
        s = np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2.0
        q = [(r[0, 2] - r[2, 0]) / s, (r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s]
    else:
        s = np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2.0
        q = [(r[1, 0] - r[0, 1]) / s, (r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s]
    q = np.asarray(q, dtype=float)
    q = q / np.linalg.norm(q)
    return [float(v) for v in q]


def _local_to_world(link_prim, spec) -> dict:
    """World pose of a pad whose transform is given in the link's frame."""
    link_world = np.array(
        UsdGeom.Xformable(link_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    ).reshape(4, 4).T
    local = np.eye(4)
    local[0:3, 0:3] = _quat_to_matrix(spec["quat"])
    local[0:3, 3] = [float(v) for v in spec["translate"]]
    world = link_world @ local
    return {
        "translate": [float(v) for v in world[0:3, 3]],
        "quat": _matrix_to_quat(world[0:3, 0:3]),
    }


def _set_color(prim, rgba: tuple[float, float, float]) -> None:
    """Give a prim a simple preview-surface material of the given colour."""
    usd_prim = prim.GetPrim()
    stage = usd_prim.GetStage()
    mat_path = f"{usd_prim.GetPath()}_mat"
    material = UsdShade.Material.Define(stage, mat_path)
    shader = UsdShade.Shader.Define(stage, f"{mat_path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgba))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.6)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(usd_prim).Bind(material)


def _add_physics_material(
    prim,
    static_friction: float,
    dynamic_friction: float,
    restitution: float = 0.0,
    compliant_stiffness: float = 0.0,
    compliant_damping: float = 0.0,
    colour: tuple[float, float, float] | None = None,
):
    """Bind a physics material, optionally a spring-damper contact and a colour.

    The default call (no stiffness, no colour) authors exactly the shipped
    material, so the pad-era numbers are unchanged when the new knobs are off.
    A compliant material replaces the rigid contact response with
    ``F = k * penetration + c * d(penetration)/dt`` - the "soft pad" of the P3
    contact-face phase (see WORKLOG "P3-faces"): the flat hard pads saturate the
    10 N/joint finger drive for any interference over ~10 um, and a compliant
    face is the model that lets the force grow gradually instead.
    """
    usd_prim = prim.GetPrim()
    stage = usd_prim.GetStage()
    mat_path = f"{usd_prim.GetPath()}_physmat"
    material = UsdShade.Material.Define(stage, mat_path)
    api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    api.CreateStaticFrictionAttr().Set(static_friction)
    api.CreateDynamicFrictionAttr().Set(dynamic_friction)
    api.CreateRestitutionAttr().Set(restitution)
    if colour is not None:
        shader = UsdShade.Shader.Define(stage, f"{mat_path}/shader")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(*colour)
        )
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.85)
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    friction_combine = str(
        os.environ.get("FRUIT_FINGER_FRICTION_COMBINE", "")
    ).strip().lower()
    if compliant_stiffness > 0.0 or friction_combine:
        contact = PhysxSchema.PhysxMaterialAPI.Apply(material.GetPrim())
        if compliant_stiffness > 0.0:
            contact.CreateCompliantContactStiffnessAttr().Set(float(compliant_stiffness))
            contact.CreateCompliantContactDampingAttr().Set(float(compliant_damping))
        if friction_combine:
            # PhysX's default friction combine takes the *minimum* of the pair
            # (WORKLOG: the finger material's mu=2.0 cannot lift the effective
            # grip above each fruit's own 0.4-1.1), which is exactly the
            # friction limit the A2/A8 carry slide and the A6 walk live under.
            # `max` makes the finger material the governing one.
            try:
                contact.CreateFrictionCombineModeAttr().Set(friction_combine)
            except Exception as exc:  # noqa: BLE001 - schema probe
                say(f"friction combine mode {friction_combine!r} unavailable: {exc}")
    UsdShade.MaterialBindingAPI.Apply(usd_prim).Bind(material)
    return material


def _world_matrix(prim) -> np.ndarray:
    """The prim's local-to-world transform as a column-vector 4x4 numpy matrix."""
    return np.array(
        UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    ).reshape(4, 4).T


#: The finger drive's force cap, in **raw attribute** form. This is exactly what
#: `UsdPhysics.DriveAPI.GetMaxForceAttr()` returns (the API's instance name is
#: `linear`), but reading it by name does not touch the prim's applied schemas.
#: `UsdPhysics.DriveAPI.Get(prim, "linear")` is documented to **apply** the
#: schema, which is harmless on `joint1` (already `PhysicsDriveAPI:linear`,
#: usda:3799-3803) and wrong on the `joint2` mimic, which carries no drive block
#: at all (usda:3822-3843) - asking for its cap would author one. Measured on
#: this USD/lib (`logs/p41/p4/a4_drive_read_out.txt`): the `Get` does **not**
#: author an applied-schema opinion, so the pre-P41-phase-4 builds were inert;
#: this form removes the question instead of relying on that.
_DRIVE_MAXFORCE_ATTR = "drive:linear:physics:maxForce"


def _drive_maxforce_cap(prim) -> float | None:
    """The authored `PhysicsDriveAPI:linear` force cap, or `None` if unauthored.

    Never `UsdPhysics.DriveAPI.Get`: see `_DRIVE_MAXFORCE_ATTR`. `GetAttribute`
    only reads; `None` is the asset's own "this joint cannot push" state, so a
    drive-less mimic answers `None` instead of being handed an opinion.
    """
    try:
        attr = prim.GetAttribute(_DRIVE_MAXFORCE_ATTR)
        if not attr or not attr.HasAuthoredValue():
            return None
        return float(attr.Get())
    except Exception:  # noqa: BLE001 - a header read must not stop a build
        return None


def _finger_drive_caps(stage, side: str = "left") -> str:
    """The asset's own finger-drive force caps, `joint1/joint2`, from the USD.

    `joint2` is a drive-less `PhysxMimicJointAPI` mimic: it has no drive block
    at all, so its cap reads `0.0` - the second jaw face is nominally driven
    and cannot push (P41 phase 1: authoring gains on it is byte-inert). This is
    the cap the runtime gain call does not move, so it belongs in the build
    header beside the programmed k/c. Read through `_drive_maxforce_cap`, i.e.
    **without** `DriveAPI.Get`, so this header cannot apply a drive schema to
    the mimic it is describing.
    """
    caps = []
    for index in (1, 2):
        prim = stage.GetPrimAtPath(
            f"/World/OpenArm/joints/openarm_{side}_finger_joint{index}"
        )
        if not prim.IsValid():
            return "n/a"
        cap = _drive_maxforce_cap(prim)
        caps.append(0.0 if cap is None else cap)
    return "/".join(f"{value:.1f}" for value in caps)


def resolve_finger_maxforce() -> float | None:
    """`FRUIT_FINGER_MAXFORCE` - the finger drives' force cap for this build [N].

    **Default off**: unset (or empty) returns `None`, nothing is written, and the
    drives keep the asset's own caps exactly (`10 N` on each `joint1`, `0` on the
    drive-less `joint2` mimic) - the byte-identical shipped build. A value is the
    per-joint clamp the drive may apply; the pinch the pads deliver is at most
    twice it. Non-positive or unparsable values are refused with a print rather
    than silently authoring a free jaw.
    """
    text = os.environ.get("FRUIT_FINGER_MAXFORCE", "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        say(
            f"FRUIT_FINGER_MAXFORCE={text!r} is not a number; the drives keep the "
            "asset's own caps"
        )
        return None
    if value <= 0.0:
        say(
            f"FRUIT_FINGER_MAXFORCE={value:g} N refused (must be > 0); the drives keep "
            "the asset's own caps"
        )
        return None
    return value


def _finger_drive_rows(stage) -> list[dict]:
    """The four finger joints' drive caps, read back off the stage per joint.

    `joint1` is the arm's only finger actuator (k = 1e6 N/m, `maxForce` 10 N in
    `assets/openarm_flat/openarm_flat_deinst.usda:3798-3820`); `joint2` is a
    `PhysxMimicJointAPI` mimic with **no drive block at all** (usda:3822-3843),
    so its cap is physically 0 and a cap written there would make it fight its
    own reference joint. The readback uses `HasAPI` and the raw attribute name
    (never `DriveAPI.Get`, which applies the schema) so asking a question
    cannot change the asset.
    """
    rows = []
    for side in ("left", "right"):
        for index in (1, 2):
            name = f"openarm_{side}_finger_joint{index}"
            prim = stage.GetPrimAtPath(f"/World/OpenArm/joints/{name}")
            row = {"joint": name, "drive": False, "maxForce": None}
            if prim.IsValid():
                row["drive"] = prim.HasAPI(UsdPhysics.DriveAPI, "linear")
                if row["drive"]:
                    row["maxForce"] = _drive_maxforce_cap(prim)
            rows.append(row)
    return rows


def apply_finger_maxforce(stage, value: float) -> str:
    """Write `value` N onto every finger **drive**; return the per-joint readback.

    Runs in `build()` - i.e. *before* `start()` creates the `Articulation`, so
    PhysX parses the cap when it builds the DOFs. Writing the USD after the
    articulation view exists would be inert (only `set_dof_gains` /
    `set_dof_max_efforts` act on a live view), which is why this is a build-time
    authoring step and the print is a *stage* readback, not a physics claim.
    """
    for side in ("left", "right"):
        prim = stage.GetPrimAtPath(
            f"/World/OpenArm/joints/openarm_{side}_finger_joint1"
        )
        if not prim.IsValid() or not prim.HasAPI(UsdPhysics.DriveAPI, "linear"):
            say(
                f"FRUIT_FINGER_MAXFORCE={value:g} N: {side} joint1 has no linear "
                "drive on this asset - nothing written for that arm"
            )
            continue
        # `Get` (not the raw attribute) is correct *here*: this is the writer,
        # it is reached only for a prim that already has the schema (the
        # `HasAPI` guard above), and it must be able to `CreateMaxForceAttr`.
        # The readers never use it (`_drive_maxforce_cap`).
        drive = UsdPhysics.DriveAPI.Get(prim, "linear")
        attr = drive.GetMaxForceAttr()
        if attr is None:
            attr = drive.CreateMaxForceAttr()
        attr.Set(float(value))
    rows = _finger_drive_rows(stage)
    parts = []
    for row in rows:
        cap = row["maxForce"]
        text = "n/a" if cap is None else f"{cap:.1f}"
        suffix = "" if row["drive"] else " (drive-less mimic)"
        parts.append(f"{row['joint']}={text}{suffix}")
    return (
        f" | FRUIT_FINGER_MAXFORCE={value:g} N -> "
        + ", ".join(parts)
        + " (written on the stage before the articulation is created)"
    )


#: The asset's authored `joint1` finger force cap
#: (`assets/openarm_flat/openarm_flat_deinst.usda:3803`). `joint2`'s is 0 by
#: construction (a drive-less `PhysxMimicJointAPI` mimic, usda:3822-3843).
ASSET_FINGER_MAXFORCE = 10.0


def finger_maxforce_intent() -> tuple[float, float]:
    """The per-finger-joint force caps this build intends, `(joint1, joint2)` [N].

    `FRUIT_FINGER_MAXFORCE` (default off) writes `joint1` on both arms and never
    `joint2`, so unset means the asset's own 10.0 N. A read-back is compared
    against this pair, not against k/c alone: a `nan` or an absent cap must not
    read like an `mf10` shard (P41 phase 4 A4).
    """
    value = resolve_finger_maxforce()
    return (ASSET_FINGER_MAXFORCE if value is None else float(value), 0.0)


def _finger_drive_readback(arms: dict) -> tuple[dict, bool, str]:
    """Per-finger-joint runtime gains and caps; `(rows, matches, why_not)`.

    Reads the **live articulations** (one array read each per joint, outside any
    control loop), because the gain call is not symmetric: it programs both
    finger joints, while `joint2`'s 0.0 N cap means it cannot push. `matches`
    is true only if every joint's k/c is the resolver's pair (skipped on the
    asset path, which programs nothing) **and** its cap is the intent cap.
    """
    from .control import finger_drive_profile

    intent_j1, intent_j2 = finger_maxforce_intent()
    intent = {"joint1": intent_j1, "joint2": intent_j2}
    rows: dict[str, dict] = {}
    for side in ("left", "right"):
        arm = arms.get(side)
        if arm is None:
            return {}, False, f"no {side} arm"
        dofs = list(arm.finger_dofs)
        names = list(arm.spec.finger_joint_names)
        try:
            stiffness, damping = arm.robot.get_dof_gains(dof_indices=dofs)
            ks = [float(v) for v in stiffness.numpy()[0]]
            cs = [float(v) for v in damping.numpy()[0]]
        except Exception as exc:  # noqa: BLE001 - report, do not hide
            return {}, False, f"gain read-back failed on {side}: {exc}"
        try:
            caps = [
                float(v)
                for v in arm.robot.get_dof_max_efforts(dof_indices=dofs).numpy()[0]
            ]
        except Exception:  # noqa: BLE001 - a cap must not stop a manifest
            caps = [float("nan")] * len(dofs)
        for name, joint_k, joint_c, cap in zip(names, ks, cs, caps):
            rows[name] = {"k": joint_k, "c": joint_c, "maxForce": cap}
    resolved_k, resolved_c, _ = finger_drive_profile()
    wrong = []
    for name, row in rows.items():
        want_cap = intent.get(name.rsplit("_", 1)[-1])
        cap = row["maxForce"]
        if want_cap is None or not math.isfinite(cap) or abs(cap - want_cap) > 1e-3:
            wrong.append(f"{name} maxForce={cap}")
        if resolved_k > 0.0 and (
            abs(row["k"] - resolved_k) > 1e-6 or abs(row["c"] - resolved_c) > 1e-6
        ):
            wrong.append(f"{name} k/c={row['k']:.0f}/{row['c']:.0f}")
    return rows, not wrong, "; ".join(wrong)


def _release_provenance(two_line: bool = False) -> dict:
    """The `physics.release` block (P87): the release clock and its origin.

    Pure (`tasks.release_speed_resolution`, an env + scope read with no
    simulator), so it is written before the first episode and cannot fail a
    build. The three holds are the block's contract (`dwell`, `pad_hold`,
    `finger_hold`, in ticks); `ticks` is the clock a release actually spends, and
    `origin` / `profile` / `two_line` say *why* it resolved that way (`default` =
    P87's two-line scope, `scope-off` = every non-two-line path, `explicit` /
    `speed-all` = a caller's own override). A manifest without the key predates
    P87.
    """
    from .tasks import release_speed_resolution

    release = release_speed_resolution(two_line)
    return {
        "dwell": release["dwell"],
        "pad_hold": release["pad_hold"],
        "finger_hold": release["finger_hold"],
        "ticks": release["ticks"],
        "shipped_ticks": release["shipped_ticks"],
        "saved_ticks": release["saved_ticks"],
        "profile": release["profile"],
        "origin": release["origin"],
        "two_line": bool(two_line),
        "label": release["label"],
    }


def _place_provenance(two_line: bool = False) -> dict:
    """The `physics.place` block (P88): the place cap and its origin.

    Pure (`tasks.place_speed_resolution`, an env + scope read with no
    simulator), so it is written before the first episode and cannot fail a
    build. The cap pair (`v_max`, `a_max`, m/s and m/s^2) is the block's
    contract; `ticks` / `shipped_ticks` / `saved_ticks` are the profile clock at
    the resolver's **reference distance** (`reference_distance_m`) - the place is
    a transit, so this is a named like-for-like number, not the run's own leg
    length. `origin` / `profile` / `two_line` say *why* it resolved that way:
    `explicit` / `speed-all` = a caller's own override, `default` = the two-line
    scope (reachable only if `PLACE_TWO_LINE_DEFAULT` is flipped - **not
    shipped**, `logs/p88/RESULTS.md`), and `scope-off` = the shipped resolution
    on every path today. A manifest without the key predates P88.
    """
    from .tasks import place_speed_resolution

    place = place_speed_resolution(two_line)
    return {
        "v_max": place["v_max"],
        "a_max": place["a_max"],
        "ticks": place["ticks"],
        "shipped_ticks": place["shipped_ticks"],
        "saved_ticks": place["saved_ticks"],
        "reference_distance_m": place["reference_distance_m"],
        "profile": place["profile"],
        "origin": place["origin"],
        "two_line": bool(two_line),
        "label": place["label"],
    }


def _lift_provenance(two_line: bool = False) -> dict:
    """The `physics.lift` block (P89): the lift cap and its origin.

    Pure (`tasks.lift_speed_resolution`, an env + scope read with no simulator),
    so it is written before the first episode and cannot fail a build. The cap
    pair (`v_max`, `a_max`, m/s and m/s^2) is the block's contract - for the
    shipped clock that is **0.30 / 1.0**, and the scoped cell under test is P44's
    S3-v (**0.37 / 1.0**, the acceleration deliberately *not* raised). `ticks` /
    `shipped_ticks` / `saved_ticks` are the profile clock at the resolver's
    **reference distance** (`reference_distance_m`, the median `grasp_lift` leg of
    the shipped two-line record) - the lift is a short vertical move, but its tick
    count still depends on the distance, so the reference travels beside it.
    `origin` / `profile` / `two_line` say *why* it resolved that way: `explicit` /
    `speed-all` = a caller's own override, `default` = the two-line scope
    (reachable only if `LIFT_TWO_LINE_DEFAULT` is flipped - **not shipped**,
    `logs/p89/RESULTS.md`), and `scope-off` = the shipped resolution on every
    path today. A manifest without the key predates P89.
    """
    from .tasks import lift_speed_resolution

    lift = lift_speed_resolution(two_line)
    return {
        "v_max": lift["v_max"],
        "a_max": lift["a_max"],
        "ticks": lift["ticks"],
        "shipped_ticks": lift["shipped_ticks"],
        "saved_ticks": lift["saved_ticks"],
        "reference_distance_m": lift["reference_distance_m"],
        "profile": lift["profile"],
        "origin": lift["origin"],
        "two_line": bool(two_line),
        "label": lift["label"],
    }


def _takeoff_provenance(two_line: bool = False) -> dict:
    """The `physics.takeoff` block (P91): the validation ramp and its origin.

    Pure (`tasks.probe_ticks_resolution`, an env + scope read with no
    simulator), so it is written before the first episode and cannot fail a
    build. `ticks` is the probe ramp's **tick count** - the block the cell moves
    - and `probe_lift` the height it lifts over [m], because a rate without its
    travel says nothing; `shipped_ticks` is the same session's pre-P91 value (60
    two-line / 40 single-arm) and `saved_ticks` the difference. `origin` /
    `two_line` say *why* it resolved that way: `explicit` = a caller's own
    `FRUIT_DYNAMIC_PROBE_TICKS`, `default` = P91's two-line scope (reachable only
    if `PROBE_TWO_LINE_DEFAULT` is flipped - see `logs/p91/RESULTS.md`),
    `two-line` / `single` = the shipped resolution. A manifest without the key
    predates P91.
    """
    from .tasks import probe_ticks_resolution

    takeoff = probe_ticks_resolution(two_line)
    return {
        "ticks": takeoff["ticks"],
        "shipped_ticks": takeoff["shipped_ticks"],
        "saved_ticks": takeoff["saved_ticks"],
        "probe_lift": takeoff["probe_lift"],
        "origin": takeoff["origin"],
        "two_line": bool(two_line),
        "label": takeoff["label"],
    }


def _park_provenance(two_line: bool = False) -> dict:
    """The `physics.park` block (P100): the return's fixed clock and its origin.

    Pure (`tasks.park_profile_resolution`, an env + scope read with no
    simulator), so it is written before the first episode and cannot fail a
    build. The block's contract is the pair the profile owns: `blend` (the
    `_blend_to` min-jerk ramp, ticks) and `settle` (its convergence hold, ticks);
    `ticks` is their sum, `shipped_ticks` the same session's pre-P100 210, and
    `saved_ticks` the difference. The park's other two stages -
    `_catch_up_drive`'s 20/40-tick re-anchor and `_lift_clear`'s step-capped IK
    lift - are seed- and distance-dependent and are **not** part of the cell, so
    a run's own block never predicts its park; the log's `[biarm] park profile:`
    row and the worker's `[ready]` rows carry the achieved pair.
    `origin` / `profile` / `two_line` say *why* it resolved that way:
    `explicit` = a caller's own `FRUIT_BIARM_PARK_BLEND`/`_SETTLE`, `default` =
    P100's two-line scope (reachable only if `PARK_TWO_LINE_DEFAULT` is flipped),
    `scope-off` = the shipped resolution on every path today. A manifest without
    the key predates P100.
    """
    from .tasks import park_profile_resolution

    park = park_profile_resolution(two_line)
    return {
        "blend": park["blend"],
        "settle": park["settle"],
        "ticks": park["ticks"],
        "shipped_ticks": park["shipped_ticks"],
        "saved_ticks": park["saved_ticks"],
        "profile": park["profile"],
        "origin": park["origin"],
        "two_line": bool(two_line),
        "label": park["label"],
    }


def finger_physics_provenance(arms: dict | None = None,
                              control_dt: float = 1.0 / 120.0,
                              scope: dict | None = None,
                              two_line: bool = False) -> dict:
    """The physics that sets the grip, as a store manifest's `physics` block.

    P41 phase 2: a store is reusable only if its *contact forces* are
    identifiable. The shipped finger-drive profile moves the delivered pinch
    2.2x (4.4 -> 9.8 N per pinch) without touching a single trajectory, and
    `FRUIT_SUBSTEPS` reaches the same force at 3.08x wall; neither left a trace
    in a pre-P41 manifest, so a pre/post-profile shard was indistinguishable by
    its own metadata (`logs/p41/FIDELITY_SWEEP.md` section 6.6).

    `arms` (a `{side: ArmController}` mapping) switches `finger_drive` to the
    **runtime read-back** and fills `readback_matches`; without it the block
    carries the env-resolved pair, so a build that dies before the task exists
    still leaves a named block. `finger_contact.combine` is `None` when unset -
    the engine's default pair rule, which `GRIP_CENSUS` section 3 records as
    **unverified** (min vs average is a 2.7x capacity spread), so it must not be
    asserted here. The fruit side is what makes the *pair* reconstructible.

    `release` (P87) is the **release clock**: the three open-loop holds of the
    place leg's release block (`dwell` / `pad_hold` / `finger_hold`, 188 ticks
    shipped, 112 under the P86 trim) and their origin. The trim is ~0.64 s of
    pure dwell inside the per-attempt span, so a store recorded under it differs
    from a pre-P87 one in its **attempt timing** without moving one trajectory
    endpoint - exactly the class the P41 `physics` and P72 `scene` blocks exist
    for. `two_line` is the caller's session scope (the collector's mode; `False`
    on the direct env, which never runs a `CoopSession`), because the trim is a
    two-line-scoped default (`tasks.release_speed_resolution`). A manifest
    **without** this key predates P87 (the `arm_park.defaulted` convention).

    `place` (P88) is the **place cap**: `v_max` 0.35 -> 0.52 at the shipped
    `a_max` (a transit's clock is distance-dependent, so `ticks` is priced at a
    named reference distance and `reference_distance_m` travels with it). The
    cell's two-line default is **off** - P88 measured it and the gate failed -
    so the shipped tree records 0.35 with `origin="scope-off"`; a store recorded
    under the raise says `explicit`. A manifest without the key predates P88.

    `lift` (P89) is the **lift cap**: the shipped 0.30/1.0 against P44's S3-v
    0.37/1.0 (the acceleration deliberately not raised). Its two-line default is
    **off** as well - P89 measured it and the gate failed - so the shipped tree
    records 0.30 with `origin="scope-off"`. A manifest without the key predates
    P89.
    """
    from .control import finger_drive_profile
    from .fruits import REAL_CONTACT_DAMPING
    from .meshes import FRUIT_SHAPES, physics_real_compliance

    stiffness, damping, profile = finger_drive_profile()
    kind = os.environ.get("FRUIT_GRIPPER_KIND", "openarm")
    fruit_compliant = physics_real_compliance()
    steps = substeps()
    block = {
        "profile": profile,
        "substeps": steps,
        "control_dt": control_dt,
        "dt": control_dt / steps,
        #: The ratio the collapse is measured on (phase 1 section 3); `None` on
        #: the asset's own drive, which the profile does not express as k/c.
        "c_over_k": (damping / stiffness) if stiffness > 0.0 else None,
        #: The *intent* land: `None` = the asset's own caps (10 N / 0 N). The
        #: read-back below is what the articulation carries.
        "finger_maxforce": resolve_finger_maxforce(),
        "finger_drive": {
            "source": "env-resolved",
            "k": stiffness,
            "c": damping,
            "maxForce": "read back at task start",
        },
        "finger_contact": {
            "compliance": float(os.environ.get("FRUIT_FINGER_COMPLIANCE", "0")),
            "contact_damping": float(
                os.environ.get("FRUIT_FINGER_CONTACT_DAMPING", "60")
            ),
            "mu": float(
                os.environ.get("FRUIT_FINGER_MU", "2.0" if kind == "openarm" else "0.0")
            ),
            "combine": os.environ.get("FRUIT_FINGER_FRICTION_COMBINE", "").strip()
            or None,
            "fruit": {
                "mu": "per-class draw",
                "mu_band": [
                    min(shape.friction[0] for shape in FRUIT_SHAPES.values()),
                    max(shape.friction[1] for shape in FRUIT_SHAPES.values()),
                ],
                "compliance": (
                    "per-class (FRUIT_PHYSICS_REAL_COMPLIANCE)"
                    if fruit_compliant
                    else 0.0
                ),
                "contact_damping": REAL_CONTACT_DAMPING if fruit_compliant else None,
            },
        },
        #: P87: the **release clock** (the S2 trim). Same one resolver the
        #: per-attempt holds and the `[biarm] release profile:` row read
        #: (`tasks.release_speed_resolution`), so a store, a log and a run cannot
        #: disagree. `shipped` 20/3/3 = 188 ticks; the P86 trim is 0/2/2 = 112.
        #: The block is always written (both origins are meaningful); a manifest
        #: without the key predates P87.
        "release": _release_provenance(two_line),
        #: P88: the **place cap** (the S1 cell). Same one resolver the
        #: per-attempt caps and the `[biarm] place profile:` row read
        #: (`tasks.place_speed_resolution`); the place is a transit, so the
        #: tick fields are priced at the resolver's own reference distance and
        #: carry that distance beside them. A manifest without the key predates
        #: P88.
        "place": _place_provenance(two_line),
        #: P89: the **lift cap** (the S3-v cell). Same one resolver the
        #: per-attempt caps and the `[biarm] lift profile:` row read
        #: (`tasks.lift_speed_resolution`); the lift's clock is priced at the
        #: resolver's own reference distance and carries that distance beside it.
        #: A manifest without the key predates P89.
        "lift": _lift_provenance(two_line),
        #: P91: the **take-off validation ramp**. Same one resolver the probe
        #: loop and the `[biarm] take-off profile:` row read
        #: (`tasks.probe_ticks_resolution`). It is a tick count, not a speed, so
        #: the block names the ticks and the ramp height the probe lifts over;
        #: the belt-break clock (`FRUIT_DYNAMIC_TAKEOFF_MATCH`/`_TRANS`, the P3
        #: anti-shear constant) is outside this block and unchanged by the cell.
        #: A manifest without the key predates P91.
        "takeoff": _takeoff_provenance(two_line),
        #: P100: the **park / ready-transit** clock - the return an attempt's
        #: worker runs in its `finally` (`_biarm_park`). Same one resolver the
        #: `_ready_move` consumer and the `[biarm] park profile:` row read
        #: (`tasks.park_profile_resolution`). The block names the pair the
        #: profile owns (the ramp and its settle hold); the block's
        #: `_catch_up_drive` and `_lift_clear` stages are seed-dependent and are
        #: not part of the cell. A manifest without the key predates P100.
        "park": _park_provenance(two_line),
    }
    if scope:
        #: P78/P79: the **runtime, per-leg** clamp
        #: (`rl_env.resolve_finger_cap_scope`). `None` = the shipped build-time
        #: cap. The block names the site (which arm, which carry-leg class) and
        #: the cap, because the write is transient: this block is built *after*
        #: the last leg's restore, so `finger_drive`'s read-back below shows the
        #: shipped cap and could never say a scoped run happened. The in-leg
        #: read-back is the `[drive] <side> <leg> finger cap raise/restore` row
        #: (P78), not this field. `sites` keeps the exact `"<side>:<legs>"` keys
        #: (`left:grasp` for P79's pick half, `left:place` for P78's place half),
        #: because `arms` collapses the side and the leg class is the whole
        #: point of the P79 arm.
        classes = sorted({str(key).partition(":")[2] for key in scope})
        block["finger_cap_scope"] = {
            "mode": "runtime",
            "legs": ", ".join(f"{cls}*" for cls in classes),
            "arms": {str(key).partition(":")[0]: float(cap)
                     for key, cap in sorted(scope.items())},
            "sites": {str(key): float(cap) for key, cap in sorted(scope.items())},
            "restore": "the cap read from the drive at the leg's start",
        }
    if not arms:
        return block
    rows, matches, why_not = _finger_drive_readback(arms)
    if not rows:
        block["finger_drive"] = {"source": "runtime-failed", "why": why_not}
        return block
    block["finger_drive"] = {
        "source": "runtime",
        "joints": rows,
        "readback_matches": bool(matches),
    }
    if why_not:
        block["finger_drive"]["readback_mismatch"] = why_not
    #: The name comes from the *resolver* (it alone knows whether the gain call
    #: was skipped, i.e. the asset path); the read-back is the check that the
    #: articulation really carries that pair. A disagreement names the run
    #: `custom` rather than trusting either side.
    block["profile"] = profile if matches else "custom"
    first = rows.get("openarm_left_finger_joint1")
    if first is not None:
        block["c_over_k"] = (first["c"] / first["k"]) if first["k"] > 0.0 else None
    return block


def _link_local_mesh_points(visuals, link_world_inv: np.ndarray, budget: int = 60000) -> np.ndarray:
    """All Mesh points under `visuals`, expressed in the finger link's frame.

    The flattened OpenArm finger is a plate; the face frame is derived from
    these points (their extents along the link axes) plus the joint direction
    and the TCP - see :func:`_finger_face_frame`. Points are capped at `budget`
    per subtree so the build-time geometry read stays a few milliseconds even
    if the de-instanced asset's meshes are dense.
    """
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    chunks: list[np.ndarray] = []
    for prim in Usd.PrimRange(visuals, proxies):
        if prim.GetTypeName() != "Mesh":
            continue
        pts = UsdGeom.Mesh(prim).GetPointsAttr().Get()
        if not pts:
            continue
        arr = np.array([[float(p[0]), float(p[1]), float(p[2])] for p in pts], dtype=float)
        if len(arr) > budget:
            arr = arr[:: max(1, len(arr) // budget)]
        world = _world_matrix(prim)
        arr_h = np.concatenate([arr, np.ones((len(arr), 1))], axis=1)
        chunks.append((link_world_inv @ world @ arr_h.T).T[:, :3])
    if not chunks:
        return np.zeros((0, 3))
    return np.concatenate(chunks, axis=0)


def _finger_face_frame(finger_prim, other_prim, tcp_prim, points: np.ndarray):
    """The finger's exact contact frame in its own link frame.

    Returns ``(e_face, e_mid, e_long, face_coord, mid_coord, tip_coord,
    extents)`` where ``e_face`` is the unit contact-face normal *pointing at the
    other finger*, ``e_mid`` is across the finger and ``e_long`` runs down the
    finger (toward the fingertip); the coordinates are the face plane, the
    across-finger centre and the fingertip extreme of the visual mesh, and
    ``extents`` are its extents along the three axes.

    The finger link's local frame *is* the contact frame: the prismatic joint
    that drives it slides along local Y (asset joints `openarm_*_finger_joint*`,
    axis Y), and the finger plate runs from its joint at local Z~0 to the
    fingertip at local Z~+0.08. A first version took the principal axes of the
    visual mesh; those are tilted ~15 deg from the link axes, which put a 71 mm
    wing 16 mm into the jaw gap and jammed the catch-up on the fruit
    (`logs/p3face/probe_geom_v`). The joint axis and the tip direction from the
    TCP link are exact, so they define the frame instead.
    """
    link_world = _world_matrix(finger_prim)
    other_world = _world_matrix(other_prim)
    tcp_world = _world_matrix(tcp_prim)
    rot = link_world[:3, :3]
    to_other = rot.T @ (other_world[:3, 3] - link_world[:3, 3])
    # The joint slides along local Y, so the other finger lies along +/-Y.
    e_face = np.zeros(3)
    e_face[1] = 1.0 if float(to_other[1]) >= 0.0 else -1.0
    # The TCP (tool point) is past the jaws, i.e. on the fingertip side of the
    # link origin; local Z is the finger's long axis.
    to_tcp = rot.T @ (tcp_world[:3, 3] - link_world[:3, 3])
    e_long = np.zeros(3)
    e_long[2] = 1.0 if float(to_tcp[2]) >= 0.0 else -1.0
    e_mid = np.zeros(3)
    e_mid[0] = 1.0
    # Keep (e_face, e_mid, e_long) right-handed: `e_mid`'s sign is free (the
    # faces are symmetric across it) and a right-handed frame makes the quat
    # authoring below unambiguous.
    if float(np.dot(np.cross(e_face, e_mid), e_long)) < 0.0:
        e_mid = -e_mid
    proj_face = points @ e_face
    proj_mid = points @ e_mid
    proj_long = points @ e_long
    extents = (
        float(proj_face.max() - proj_face.min()),
        float(proj_mid.max() - proj_mid.min()),
        float(proj_long.max() - proj_long.min()),
    )
    #: Raw extents of every axis, so a *recessed* face can cover the whole
    #: original plate (the shipped mesh collider is disabled in that mode).
    bounds = (
        float(proj_mid.min()),
        float(proj_mid.max()),
        float(proj_long.min()),
        float(proj_long.max()),
    )
    return (
        e_face,
        e_mid,
        e_long,
        float(proj_face.max()),
        float((proj_mid.min() + proj_mid.max()) / 2.0),
        float(proj_long.max()),
        extents,
        bounds,
    )


@dataclass
class SortingScene:
    """Handles to everything in the cell."""

    cfg: SceneConfig
    stage: Usd.Stage | None = None
    robot: Articulation | None = None
    camera: RtxCamera | None = None
    camera_sensor: CameraSensor | None = None
    belt_prim_path: str = "/World/Conveyor/Belt"
    belt: object | None = None
    #: OutputBelt handles, one per side (index 0 = +Y, 1 = -Y).
    output_belts: list[object] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    DEFAULT_PARTS = ("environment", "pedestal", "robot", "conveyor", "output_belts", "camera")

    def build(self, parts: tuple[str, ...] | None = None) -> "SortingScene":
        if parts is None:
            # `FRUIT_SCENE_PARTS` lets a run drop a part - e.g. the head camera - to
            # separate the render/sensor path from the physics path when chasing
            # run-to-run differences (WORKLOG "the run is not reproducible").
            override = os.environ.get("FRUIT_SCENE_PARTS", "").strip()
            parts = (
                tuple(p for p in override.split(",") if p)
                if override
                else self.DEFAULT_PARTS
            )
        stage_utils.create_new_stage()
        stage = stage_utils.get_current_stage()
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        self.stage = stage
        say("stage created (meters, Z-up)")

        builders = {
            "environment": self._add_environment,
            "pedestal": self._add_pedestal,
            "robot": self._add_robot,
            "conveyor": self._add_conveyor,
            "output_belts": self._add_output_belts,
            # The v3 output conveyors replaced the old output bins; keep the old
            # part name working so older probe scripts still build a scene.
            "bins": self._add_output_belts,
            "camera": self._add_head_camera,
        }
        for name in parts:
            say(f"building part: {name}")
            builders[name]()
        if os.environ.get("FRUIT_FINGER_PADS", "0") == "1":
            self._add_finger_pads()
        # The `openarm` hand grips with the robot's own finger meshes, so their
        # colliders and friction are part of that hand, not an experiment: on by
        # default in that mode, off for the kinematic pads (which bring their own
        # contact bodies).
        openarm_hand = os.environ.get("FRUIT_GRIPPER_KIND", "openarm") == "openarm"
        finger_colliders = os.environ.get(
            "FRUIT_FINGER_COLLIDERS", "1" if openarm_hand else "0"
        ) == "1"
        if finger_colliders:
            verdict = self._add_finger_colliders()
            if openarm_hand and "robot" in parts:
                # Hard gate (P1 gate remediation): the de-instanced asset is
                # gitignored, so on a fresh checkout the instanced fallback is
                # used, PhysX never parses its finger subtree, and without this
                # the shipped default silently runs the old "fruit floats"
                # hand. Refuse the build instead.
                try:
                    assert_finger_colliders(verdict, OPENARM_BIMANUAL_USD)
                except FingerColliderError as exc:
                    # Kit catches an uncaught exception in a SimulationApp
                    # script and still exits 0 (measured: `scripts/run.sh` with
                    # a raising script -> exit 0), so raising alone could still
                    # pass a shell pipeline silently. Print and hard-exit.
                    say(f"FATAL: {exc}")
                    os._exit(1)
        elif openarm_hand and "robot" in parts:
            say(
                "WARNING: FRUIT_FINGER_COLLIDERS=0 with FRUIT_GRIPPER_KIND=openarm - "
                "the visible jaws have no colliders and cannot hold fruit; only "
                "valid for probes that author them after build (e.g. scripts/431)"
            )
        finger_mu = float(
            os.environ.get("FRUIT_FINGER_MU", "2.0" if openarm_hand else "0.0")
        )
        #: Compliant contact knobs for the P3 contact-face phase. Off by default:
        #: 0 authors exactly the shipped rigid material (bit-identical build).
        finger_stiffness = float(os.environ.get("FRUIT_FINGER_COMPLIANCE", "0"))
        finger_damping = float(os.environ.get("FRUIT_FINGER_CONTACT_DAMPING", "60"))
        if finger_mu > 0.0:
            # Override the finger links' physics material. The asset's own material
            # may be frictionless, and PhysX's default combine mode takes the
            # *minimum* of the two coefficients - which would make a firm pinch
            # unable to carry anything, however hard it squeezes.
            for side in ("left", "right"):
                for which in ("left", "right"):
                    prim = self.stage.GetPrimAtPath(
                        f"/World/OpenArm/openarm_{side}_{which}_finger"
                    )
                    if prim.IsValid():
                        _add_physics_material(
                            prim,
                            finger_mu,
                            finger_mu,
                            0.0,
                            finger_stiffness,
                            finger_damping,
                        )
            combine = os.environ.get("FRUIT_FINGER_FRICTION_COMBINE", "").strip()
            # P41 phase 2: the header names the finger *drive* as well as the
            # contact material, so every entry script's log is self-describing.
            # The gains are what `ArmController` will program (the same
            # resolver, so the print cannot drift from the call); the caps are
            # the asset's own and are not moved by that call. No JSON here.
            from .control import finger_drive_profile

            drive_k, drive_c, drive_profile = finger_drive_profile()
            # P41 phase 3: the drive's force cap, `FRUIT_FINGER_MAXFORCE`
            # (default off). Written on the stage *here* - before `start()`
            # creates the articulation - so PhysX parses it; the print below is
            # the stage's own post-write readback, per joint.
            finger_maxforce = resolve_finger_maxforce()
            maxforce_note = (
                ""
                if finger_maxforce is None
                else apply_finger_maxforce(self.stage, finger_maxforce)
            )
            caps = _finger_drive_caps(self.stage)
            say(
                f"finger links bound with mu={finger_mu}"
                + (
                    f", compliant k={finger_stiffness:.0f} N/m c={finger_damping:.0f} Ns/m"
                    if finger_stiffness > 0.0
                    else ""
                )
                + (f", friction combine={combine}" if combine else "")
                + " (friction combine override)"
                + f" | finger drive profile={drive_profile}"
                + (
                    f" k={drive_k:.0f} N/m c={drive_c:.0f} Ns/m"
                    if drive_k > 0.0
                    else " (the asset's own gains)"
                )
                + f" maxForce={caps}N (joint1/joint2; joint2 is a drive-less mimic)"
                + maxforce_note
            )
        # P39 L1 (opt-in, **presence-gated**: unset = the shipped mesh colliders,
        # byte-identical build): replace the four finger plates' collider with a
        # convex box on the same face plane whose distal plane sits at
        # `tip_coord + FRUIT_FINGER_TIP_DELTA`. The gate is presence, not value:
        # `=0` re-authors the plate as an AABB of the shipped mesh (arm S, "box
        # == mesh") so the mechanism can be separated from the geometry change;
        # a negative value shortens the plate (F1), a positive one extends it.
        # Must run after `_add_finger_colliders` (its verdict and
        # `assert_finger_colliders` count the shipped meshes) and before the
        # modes that author their own finger geometry, which it refuses to mix
        # with. See `_author_finger_tip_delta`.
        tip_delta_text = os.environ.get("FRUIT_FINGER_TIP_DELTA")
        if tip_delta_text is not None:
            if not (openarm_hand and finger_colliders):
                # Nothing to replace: without the OpenArm hand's mesh colliders
                # there is no plate surface, and the kinematic-pad hand brings
                # its own contact bodies.
                say(
                    f"finger tip delta {tip_delta_text!r} ignored: needs "
                    "FRUIT_GRIPPER_KIND=openarm and FRUIT_FINGER_COLLIDERS=1"
                )
            else:
                try:
                    tip_delta = float(tip_delta_text)
                except ValueError:
                    tip_delta = math.nan
                # A typo must not silently run the shipped hand, which is
                # what an ignored parse would do (Kit exits 0 on a raising
                # script, see the finger-collider gate above). Two further
                # values have to take the same FATAL path: a **non-finite**
                # one (NaN compares False against the downstream
                # `length < 0.005` guard, so `nan` would author an undefined
                # plate) and an **absurd** one (`=1.0` would author a 1 m
                # plate). The bound is a sanity envelope, not the lever's
                # legal range - the physical bounds are in `logs/p39/02_
                # finger_geometry.txt` §2 (`-4.2 / +7.2 mm` on the pool).
                if not math.isfinite(tip_delta) or abs(tip_delta) > 0.05:
                    say(
                        f"FATAL: FRUIT_FINGER_TIP_DELTA={tip_delta_text!r} must be "
                        "a finite tip delta in [-0.05, 0.05] m"
                    )
                    os._exit(1)
                self._author_finger_tip_delta(tip_delta)
        # P3 contact faces: grooved/rounded pads on the robot's own fingers. The
        # shipped default is `flat` (no new geometry at all); `v`/`h`/`x`/`c`
        # author them during build, before play, so PhysX parses them as part of
        # the finger links. See `_add_contact_faces`.
        face_shape = os.environ.get("FRUIT_FINGER_FACE", "flat").strip().lower()
        if openarm_hand and finger_colliders and face_shape not in ("", "flat", "none", "0"):
            self._add_contact_faces(face_shape)
        # D2 mechanism attempt (task option 1, opt-in, default off): a real
        # compliant pad body on each finger face. See `_add_soft_pads`.
        if (
            openarm_hand
            and finger_colliders
            and os.environ.get("FRUIT_FINGER_SOFT_PAD", "0") == "1"
        ):
            self._add_soft_pads()
        # D2b cradle/scoop (R8-A screen, opt-in, default off): a passive ledge
        # below each fingertip that the payload lands on once it starts walking
        # +z out of the pinch. See `_add_finger_scoops`.
        if (
            openarm_hand
            and finger_colliders
            and os.environ.get("FRUIT_FINGER_SCOOP", "0") == "1"
        ):
            self._add_finger_scoops()
        say(f"scene built (parts={list(parts)})")
        return self

    # ------------------------------------------------------------------ #
    def _add_finger_colliders(self) -> FingerColliderVerdict:
        """Make the robot's own finger meshes collidable, and report what happened.

        The shipped asset is instanced and its finger `collisions/` subtree is an
        instance proxy: PhysX never parses it and no collider can be authored onto
        it (`Cannot create prim spec ... authoring to an instance proxy is not
        allowed`). With a flattened, de-instanced copy (`FRUIT_ROBOT_USD`) the
        finger *visual* meshes take a CollisionAPI - measured: the fingers then
        close on a 3.4 cm fruit and lift it 85 mm (`logs/422`).

        The returned verdict is what the caller asserts on in `openarm` mode:
        instance-proxy failures are collected here instead of being logged and
        forgotten, because with the pad hand gone a collider-less build is the
        old "fruit floats" configuration and must not run (P1 gate remediation).
        """
        proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
        enabled = 0
        skipped = 0
        roots = 0
        for side in ("left", "right"):
            for which in ("left", "right"):
                root = self.stage.GetPrimAtPath(
                    f"/World/OpenArm/openarm_{side}_{which}_finger/visuals"
                )
                if not root.IsValid():
                    continue
                roots += 1
                for prim in Usd.PrimRange(root, proxies):
                    if prim.GetTypeName() != "Mesh":
                        continue
                    try:
                        if not prim.HasAPI(UsdPhysics.CollisionAPI):
                            UsdPhysics.CollisionAPI.Apply(prim)
                        UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(True)
                        if hasattr(PhysxSchema, "PhysxConvexHullCollisionAPI"):
                            PhysxSchema.PhysxConvexHullCollisionAPI.Apply(prim)
                        enabled += 1
                    except Exception as exc:  # noqa: BLE001
                        skipped += 1
                        say(f"finger collider skipped on {prim.GetPath()}: {exc}")
        say(
            f"finger colliders: {enabled} mesh prims enabled"
            + (f", {skipped} skipped (instanced asset?)" if skipped else "")
        )
        return FingerColliderVerdict(enabled=enabled, skipped=skipped, roots=roots)

    def _add_finger_pads(self) -> None:
        """Add fingertip pad colliders as standalone bodies tied to the fingers.

        The asset's finger links are instanced and their `collisions` subtree is an
        instance proxy, so a collider authored as a child of the link is invisible
        to PhysX - a kinematic sphere passes straight through it (logs/151-156),
        even though USD reports `collisionEnabled=True`. Standalone rigid bodies
        are always parsed, so each pad is authored under `/World/GraspPads` at the
        world pose implied by the calibration file, and pinned to its finger link
        with a fixed joint.
        """
        import json

        path = os.environ.get("FRUIT_FINGER_PADS_FILE", "configs/finger_pads.json")
        with open(path, encoding="utf-8") as fh:
            pads = json.load(fh)
        self.stage.DefinePrim("/World/GraspPads", "Xform")
        only_pads = os.environ.get("FRUIT_PAD_ONLY", "0") == "1"
        shape = os.environ.get("FRUIT_PAD_SHAPE", "capsule")
        radius = float(os.environ.get("FRUIT_PAD_RADIUS", "0.010"))
        pad_mu = float(os.environ.get("FRUIT_PAD_MU", "1.0"))
        proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
        count = 0
        for side_links in pads.values():
            for link_name, spec in side_links.items():
                link_path = f"/World/OpenArm/{link_name}"
                link_prim = self.stage.GetPrimAtPath(link_path)
                if not link_prim.IsValid():
                    continue
                if only_pads:
                    for prim in Usd.PrimRange(link_prim, proxies):
                        if prim.HasAPI(UsdPhysics.CollisionAPI):
                            UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)

                size = [float(v) for v in spec["size"]]
                pad_path = f"/World/GraspPads/{link_name}"
                if shape == "capsule":
                    pad = UsdGeom.Capsule.Define(self.stage, pad_path)
                    pad.GetRadiusAttr().Set(radius)
                    pad.GetHeightAttr().Set(max(size[2] - 2.0 * radius, 0.005))
                    pad.GetAxisAttr().Set("Z")
                else:
                    pad = UsdGeom.Cube.Define(self.stage, pad_path)
                    pad.GetSizeAttr().Set(1.0)

                world = _local_to_world(link_prim, spec)
                xf = UsdGeom.Xformable(pad)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in world["translate"]]))
                q = world["quat"]
                xf.AddOrientOp().Set(Gf.Quatf(q[0], q[1], q[2], q[3]))
                if shape != "capsule":
                    xf.AddScaleOp().Set(Gf.Vec3f(*size))

                UsdPhysics.CollisionAPI.Apply(pad.GetPrim())
                UsdPhysics.CollisionAPI(pad.GetPrim()).GetCollisionEnabledAttr().Set(True)
                UsdPhysics.RigidBodyAPI.Apply(pad.GetPrim())
                UsdPhysics.MassAPI.Apply(pad.GetPrim()).CreateMassAttr().Set(0.02)
                _add_physics_material(pad.GetPrim(), pad_mu, pad_mu, 0.0)

                joint = UsdPhysics.FixedJoint.Define(self.stage, f"{pad_path}_joint")
                joint.CreateBody0Rel().SetTargets([pad.GetPath()])
                joint.CreateBody1Rel().SetTargets([link_path])
                joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
                joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                joint.CreateLocalPos1Attr().Set(
                    Gf.Vec3f(*[float(v) for v in spec["translate"]])
                )
                lq = [float(v) for v in spec["quat"]]
                joint.CreateLocalRot1Attr().Set(Gf.Quatf(lq[0], lq[1], lq[2], lq[3]))
                count += 1
        say(f"added {count} {shape} fingertip pads as rigid bodies from {path}")

    def _add_contact_faces(self, shape: str) -> None:
        """Author grooved/rounded contact faces on the OpenArm finger links (P3).

        The flat finger plate cannot hold a moving fruit: once the faces touch,
        the 10 N/joint drive cap fixes the normal force for any interference over
        ~10 um, and the squeeze-out is then pure geometry (A2/A8 slide down the
        tool axis, A4 is ejected downstream, A6 walks across the belt -
        `logs/p3fix/mech_diag1`). This authors *additive* faces in front of the
        plate so no shipped collider is removed:

        * `v` - a V groove whose valley runs along the tool axis (wings above and
          below the contact line in the across-finger direction): the sphere is
          centred across the belt and resisted from rolling downstream.
        * `h` - a V groove whose valley runs across the finger (wings along the
          tool axis): the sphere is cradled above and below its equator, which
          is the direct opposition to the tool-axis slide of A2/A8.
        * `x` - both grooves (four wings per finger), a pyramidal socket.
        * `c` - `x` with a flat valley floor (`FRUIT_FINGER_FACE_FLAT`): a cup.

        Every wing's *valley* lies on the finger's true face plane, so the
        commanded link-origin separation keeps its shipped meaning (the shipped
        close reaches the fruit when the span crosses the diameter, as before);
        only the wings protrude, and they protrude by `FRUIT_FINGER_FACE_DEPTH`
        which is clamped below half the minimum link separation so two fingers
        can still close on air without the wings meeting.

        Authored before `play()`, as children of the finger links, so PhysX
        parses them into the same rigid bodies as the existing finger-mesh
        colliders (the same mechanism `_add_finger_colliders` relies on).
        """
        depth = float(os.environ.get("FRUIT_FINGER_FACE_DEPTH", "0.003"))
        half = float(os.environ.get("FRUIT_FINGER_FACE_HALF", "0.006"))
        flat = max(0.0, float(os.environ.get("FRUIT_FINGER_FACE_FLAT", "0.0")))
        thick = float(os.environ.get("FRUIT_FINGER_FACE_THICK", "0.0022"))
        span = float(os.environ.get("FRUIT_FINGER_FACE_SPAN", "0.032"))
        #: Where the *groove* pads sit along the tool: the pad covers the fruit's
        #: equator, which the dynamic close places `FRUIT_DYNAMIC_PAD_LIFT`
        #: (5 mm) above the fingertip, so the V pad centre sits 16 mm above the
        #: tip (span/2 below covers the equator, the rest is finger length).
        place_back = float(os.environ.get("FRUIT_FINGER_FACE_PLACE_BACK", "0.016"))
        #: Where a horizontal (tool-axis) wing pair sits: it must straddle the
        #: equator, so its centre is right at the fingertip + lift.
        center_back = float(os.environ.get("FRUIT_FINGER_FACE_CENTER_BACK", "0.006"))
        mu = float(os.environ.get("FRUIT_FINGER_MU", "2.0"))
        stiffness = float(os.environ.get("FRUIT_FINGER_COMPLIANCE", "0"))
        damping = float(os.environ.get("FRUIT_FINGER_CONTACT_DAMPING", "60"))
        # Two wings of `depth` each must not meet when the drives close fully:
        # the asset's minimum link-origin separation is 10 mm (ArmController),
        # so depth < 5 mm leaves a gap. Clamp rather than silently jam.
        depth = min(depth, 0.0045)
        half = max(half, flat + 0.001)
        flat = min(flat, half * 0.8)
        span = min(max(span, 0.010), 0.050)
        # `h2`/`v2`/`x2`: a *recessed* groove - the valley sits behind the
        # original face plane and the wings stop at it, so the entry envelope is
        # the shipped one (the additive `h`/`v`/`x` protrude 3 mm and were
        # measured to bat the fruit during the catch-up/close). A recessed
        # groove cannot coexist with the flat mesh collider, so that collider is
        # disabled on this link and replaced by a complete face built from
        # convex boxes (wing slopes + a surrounding frame + a body behind).
        recessed = shape.endswith("2")
        base_shape = shape[:-1] if recessed else shape
        # v6 experiment 2 (opt-in): `p`/`plate` authors one co-planar flat pad
        # per finger that extends `FRUIT_FINGER_FACE_PLATE_DEEP` [m] past the
        # fingertip along the tool axis. The A2/A8 wedge slides *down* the tool
        # axis out of the span (`hand_rel.z` grows while `sep` opens, v5
        # traces); a longer flat contact gives it more length to walk before it
        # can leave the faces. The front surface stays on the true face plane,
        # so the commanded link separation and the close's depth arithmetic are
        # unchanged, exactly like the v/h wings' valleys. Default off: `flat`
        # remains the shipped build.
        plate = base_shape in ("p", "plate")
        plate_deep = max(
            0.0, float(os.environ.get("FRUIT_FINGER_FACE_PLATE_DEEP", "0.012"))
        )
        plate_wide = max(
            0.0, float(os.environ.get("FRUIT_FINGER_FACE_PLATE_WIDE", "0.018"))
        )
        pairs = {
            "v": (("v", "mid"),),
            "h": (("h", "long"),),
            "x": (("h", "long"), ("v", "mid")),
            "c": (("h", "long"), ("v", "mid")),
        }.get(base_shape)
        if pairs is None and not plate:
            say(f"contact faces: unknown FRUIT_FINGER_FACE={shape!r}; nothing authored")
            return
        if recessed:
            # The frame plates need to be at least as thick as the groove is
            # deep, or a penetrating fruit would meet a void behind them.
            thick = max(thick, depth + 0.001)
        made = 0
        for side in ("left", "right"):
            for which in ("left", "right"):
                path = f"/World/OpenArm/openarm_{side}_{which}_finger"
                other = "right" if which == "left" else "left"
                link = self.stage.GetPrimAtPath(path)
                other_link = self.stage.GetPrimAtPath(
                    f"/World/OpenArm/openarm_{side}_{other}_finger"
                )
                tcp = self.stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_ee_tcp")
                visuals = self.stage.GetPrimAtPath(f"{path}/visuals")
                if not (
                    link.IsValid() and other_link.IsValid() and tcp.IsValid()
                    and visuals.IsValid()
                ):
                    continue
                points = _link_local_mesh_points(visuals, np.linalg.inv(_world_matrix(link)))
                if len(points) < 32:
                    say(f"contact faces: {path} has {len(points)} visual points; skipped")
                    continue
                (
                    e_face, e_mid, e_long, face_coord, mid_coord, tip_coord,
                    extents, bounds,
                ) = _finger_face_frame(link, other_link, tcp, points)
                span_long = min(span, 0.9 * float(extents[2]))
                span_mid = min(span, 0.9 * float(extents[1]))
                base = e_face * face_coord + e_mid * mid_coord
                if recessed:
                    disabled = self._disable_link_colliders(link)
                    say(f"contact faces[{shape}] {path}: {disabled} shipped colliders disabled")
                if plate:
                    # One pad from `place_back` above the fingertip to
                    # `plate_deep` past it, on the true face plane.
                    back = min(
                        max(float(place_back), 0.004),
                        max(tip_coord - float(extents[2]) + 0.010, 0.004),
                    )
                    origin = base + e_long * (tip_coord - back)
                    length = back + plate_deep
                    width = min(plate_wide, 0.9 * float(extents[1]))
                    made += self._author_flat_face(
                        link, "plate", origin, e_face, e_mid, e_long,
                        length, width, thick, mu, stiffness, damping,
                    )
                    say(
                        f"contact faces[{shape}] {side}_{which}: extent "
                        f"(face/mid/long)=({extents[0] * 1000:.1f}/{extents[1] * 1000:.1f}/"
                        f"{extents[2] * 1000:.1f}) mm, tip={tip_coord * 1000:.1f} mm, "
                        f"plate back={back * 1000:.1f} mm deep={plate_deep * 1000:.1f} mm "
                        f"long={length * 1000:.1f} mm wide={width * 1000:.1f} mm "
                        f"thick={thick * 1000:.1f} mm"
                    )
                else:
                    for tag, axis in pairs:
                        back = place_back if axis == "mid" else center_back
                        # Keep the pad centre on the finger: never deeper than the
                        # palm end of the plate, never right at the tip edge.
                        back = min(
                            max(float(back), 0.004),
                            max(tip_coord - float(extents[2]) + 0.010, 0.004),
                        )
                        origin = base + e_long * (tip_coord - back)
                        if axis == "mid":
                            e_a, e_g, pair_span = e_mid, e_long, span_long
                        else:
                            e_a, e_g, pair_span = e_long, e_mid, span_mid
                        made += self._author_v_pair(
                            link, tag, origin, e_face, e_a, pair_span,
                            depth, half, flat, thick, mu, stiffness, damping,
                            recessed=recessed,
                        )
                        if recessed:
                            made += self._author_recess_frame(
                                link, tag, origin, e_face, e_a, e_g, pair_span, back,
                                depth, half, thick, mu, stiffness, damping,
                                bounds, tip_coord, mid_coord, axis,
                            )
                    say(
                        f"contact faces[{shape}] {side}_{which}: extent "
                        f"(face/mid/long)=({extents[0] * 1000:.1f}/{extents[1] * 1000:.1f}/"
                        f"{extents[2] * 1000:.1f}) mm, tip={tip_coord * 1000:.1f} mm, "
                        f"face={face_coord * 1000:.1f} mm, depth={depth * 1000:.1f} mm, "
                        f"half={half * 1000:.1f} mm flat={flat * 1000:.1f} mm "
                        f"spans=({span_mid * 1000:.1f}/{span_long * 1000:.1f}) mm"
                    )
        say(
            f"contact faces: {made} face prims authored on the finger links "
            f"({shape}; depth={depth * 1000:.1f} mm, mu={mu}, recessed={recessed})"
        )

    def _disable_finger_plate_colliders(self, link) -> tuple[int, list[str]]:
        """Turn off the shipped *plate* colliders under one finger link (P39 L1).

        `_disable_link_colliders` switches off **every** CollisionAPI prim under
        a link, which is only correct when the link carries nothing but the
        plate. The four OpenArm finger links do: `visuals/<link>_visual/mesh`
        (the plate's render mesh, which `_add_finger_colliders` makes collidable)
        and `collisions/<link>_collision/mesh` (the asset's convex-decomposition
        collision proxy, whose extent equals the visual plate's), plus the
        `contact_faces` subtree this class authors. The palm is **not** a
        descendant of a finger link - it is a sibling link
        (`/World/OpenArm/openarm_<side>_hand`) - so this walks the link and
        disables only prims inside `visuals/` or `collisions/`, and returns the
        paths of any CollisionAPI prim it found *outside* those subtrees
        **still enabled**, for the caller to report instead of silently
        widening the disable.

        Returns `(disabled_count, kept_paths)`; the kept paths are CollisionAPI
        prims outside the plate's own subtrees that were left **enabled**.
        """
        proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
        prefix = link.GetPath().pathString
        plate_roots = (
            f"{prefix}/visuals",
            f"{prefix}/collisions",
            # Authored by `_author_flat_face`/`_add_contact_faces`; the caller
            # authors or has authored the replacements there.
            f"{prefix}/contact_faces",
        )
        disabled = 0
        kept: list[str] = []
        for prim in Usd.PrimRange(link, proxies):
            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                continue
            path = prim.GetPath().pathString
            if not any(path == root or path.startswith(f"{root}/") for root in plate_roots):
                kept.append(path)
                continue
            UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)
            disabled += 1
        return disabled, kept

    def _link_collider_counts(self, link) -> tuple[int, int]:
        """`(CollisionAPI prims, enabled CollisionAPI prims)` under a link."""
        proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
        total = enabled = 0
        for prim in Usd.PrimRange(link, proxies):
            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                continue
            total += 1
            api = UsdPhysics.CollisionAPI(prim)
            attr = api.GetCollisionEnabledAttr()
            if attr.IsValid() and not bool(attr.Get()):
                continue
            enabled += 1
        return total, enabled

    def _disable_link_colliders(self, link) -> int:
        """Turn off every shipped collider under a finger link (recessed faces).

        A recessed groove is a *removal* of material, which no additive collider
        can express next to the flat mesh collider; the face is rebuilt in full
        instead. Only the shipped colliders are touched - the new `contact_faces`
        prims are authored after this call.
        """
        proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
        disabled = 0
        for prim in Usd.PrimRange(link, proxies):
            if prim.GetPath().pathString.startswith(f"{link.GetPath()}/contact_faces"):
                continue
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)
                disabled += 1
        return disabled

    def _author_recess_frame(
        self, link, tag, origin, e_face, e_a, e_g, span, back,
        depth, half, thick, mu, stiffness, damping, bounds, tip_coord, mid_coord, axis,
    ) -> int:
        """Close the rest of the face around a recessed groove.

        Four frame plates cover the original face plane outside the groove
        rectangle and one body box fills the volume behind the valley, so the
        rebuilt finger has no hole a fruit could pass through. Coordinates are
        (face, across=e_a, groove) with the groove axis taken right-handed.
        """
        e_g_rh = np.cross(e_face, e_a)
        frame = np.column_stack([e_face, e_a, e_g_rh])
        g_flip = 1.0 if float(e_g_rh @ e_g) >= 0.0 else -1.0
        mid_lo, mid_hi, long_lo, long_hi = bounds
        if axis == "mid":
            # e_a = e_mid (across), e_g = e_long (down the finger); the pair is
            # placed `back` above the fingertip.
            u_lo, u_hi = mid_lo - mid_coord, mid_hi - mid_coord
            g_lo, g_hi = long_lo - (tip_coord - back), long_hi - (tip_coord - back)
        else:
            # e_a = e_long (down the finger), e_g = e_mid (across).
            u_lo, u_hi = long_lo - (tip_coord - back), long_hi - (tip_coord - back)
            g_lo, g_hi = mid_lo - mid_coord, mid_hi - mid_coord
        if g_flip < 0.0:
            g_lo, g_hi = -g_hi, -g_lo
        root = f"{link.GetPath()}/contact_faces"
        plates = []
        half_span = span / 2.0
        # top / bottom: full groove-axis extent, outside the wing separation.
        if u_hi - half > 0.002:
            plates.append(("frame_up", (half + u_hi) / 2.0, 0.0, u_hi - half, g_hi - g_lo))
        if -half - u_lo > 0.002:
            plates.append(("frame_down", (u_lo - half) / 2.0, 0.0, -half - u_lo, g_hi - g_lo))
        # left / right: only the central wing band, outside the groove span.
        if g_hi - half_span > 0.002:
            plates.append(("frame_right", 0.0, (half_span + g_hi) / 2.0, 2.0 * half, g_hi - half_span))
        if -half_span - g_lo > 0.002:
            plates.append(("frame_left", 0.0, (g_lo - half_span) / 2.0, 2.0 * half, -half_span - g_lo))
        made = 0
        quat = _matrix_to_quat(frame)
        for name, cu, cg, du, dg in plates:
            centre = np.array([-thick / 2.0, cu, cg])
            prim = UsdGeom.Cube.Define(self.stage, f"{root}/{tag}_{name}")
            prim.GetSizeAttr().Set(1.0)
            xf = UsdGeom.Xformable(prim)
            xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in (origin + frame @ centre)]))
            xf.AddOrientOp().Set(Gf.Quatf(quat[0], Gf.Vec3f(quat[1], quat[2], quat[3])))
            xf.AddScaleOp().Set(Gf.Vec3f(thick, max(du, 0.002), max(dg, 0.002)))
            UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
            _add_physics_material(
                prim.GetPrim(), mu, mu, 0.0, stiffness, damping, colour=(0.07, 0.07, 0.08)
            )
            made += 1
        # Body behind the valley: closes the groove floor across the whole face.
        body_thick = 0.010
        centre = np.array(
            [-depth - body_thick / 2.0, (u_lo + u_hi) / 2.0, (g_lo + g_hi) / 2.0]
        )
        prim = UsdGeom.Cube.Define(self.stage, f"{root}/{tag}_body")
        prim.GetSizeAttr().Set(1.0)
        xf = UsdGeom.Xformable(prim)
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in (origin + frame @ centre)]))
        xf.AddOrientOp().Set(Gf.Quatf(quat[0], Gf.Vec3f(quat[1], quat[2], quat[3])))
        xf.AddScaleOp().Set(
            Gf.Vec3f(body_thick, max(u_hi - u_lo, 0.010), max(g_hi - g_lo, 0.010))
        )
        UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
        _add_physics_material(
            prim.GetPrim(), mu, mu, 0.0, stiffness, damping, colour=(0.07, 0.07, 0.08)
        )
        return made + 1

    def _author_v_pair(
        self, link, tag, origin, e_face, e_a, span,
        depth, half, flat, thick, mu, stiffness, damping,
        recessed: bool = False,
    ) -> int:
        """Author the two wings of one V groove as boxes in the link's frame.

        Additive (`recessed=False`): the valley is on the finger's face plane
        and the wings protrude by `depth`. Recessed: the valley is `depth`
        *behind* the plane, the tips end at it, and the caller has already
        disabled the shipped flat collider and closed the rest of the face.
        """
        e_g = np.cross(e_face, e_a)
        frame = np.column_stack([e_face, e_a, e_g])  # columns; right-handed
        run = max(half - flat, 1e-4)
        length = float(np.hypot(depth, run))
        root = f"{link.GetPath()}/contact_faces"
        made = 0
        for sign, side_name in ((1.0, "up"), (-1.0, "down")):
            # Surface from the valley (0, sign*flat) to the tip (depth, sign*half)
            # in the (face, across) plane; the box sits just behind that surface.
            tangent = np.array([depth / length, sign * run / length, 0.0])
            normal = np.array([run / length, -sign * depth / length, 0.0])
            valley_x = -depth if recessed else 0.0
            centre = (
                np.array([valley_x + depth / 2.0, sign * (flat + half) / 2.0, 0.0])
                - normal * (thick / 2.0)
            )
            rot = np.column_stack([normal, tangent, sign * np.array([0.0, 0.0, 1.0])])
            prim = UsdGeom.Cube.Define(self.stage, f"{root}/{tag}_{side_name}")
            prim.GetSizeAttr().Set(1.0)
            xf = UsdGeom.Xformable(prim)
            xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in (origin + frame @ centre)]))
            rot_local = frame @ rot
            quat = _matrix_to_quat(rot_local)
            xf.AddOrientOp().Set(Gf.Quatf(quat[0], Gf.Vec3f(quat[1], quat[2], quat[3])))
            xf.AddScaleOp().Set(Gf.Vec3f(thick, length, span))
            UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
            _add_physics_material(
                prim.GetPrim(), mu, mu, 0.0, stiffness, damping, colour=(0.07, 0.07, 0.08)
            )
            made += 1
        return made

    def _author_flat_face(
        self, link, tag, origin, e_face, e_mid, e_long,
        length, width, thick, mu, stiffness, damping,
    ) -> int:
        """One co-planar flat pad along the tool axis (v6 experiment 2).

        The pad's front surface lies on the finger's true face plane (so the
        commanded link separation keeps its shipped meaning, the same invariant
        the v/h wings keep) and it runs from the `origin` (which the caller has
        placed `back` above the fingertip) `length` further along `e_long`,
        i.e. `length - back` past the fingertip. Coordinates are (face, across,
        along).
        """
        e_a = np.asarray(e_mid, dtype=float).copy()
        e_g = np.cross(e_face, e_a)
        if float(e_g @ e_long) < 0.0:
            # Make (e_face, e_a, e_g) right-handed with e_g parallel to e_long.
            e_a = -e_a
            e_g = -e_g
        frame = np.column_stack([e_face, e_a, e_g])
        centre = np.array([-thick / 2.0, 0.0, length / 2.0])
        prim = UsdGeom.Cube.Define(self.stage, f"{link.GetPath()}/contact_faces/{tag}")
        prim.GetSizeAttr().Set(1.0)
        xf = UsdGeom.Xformable(prim)
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in (origin + frame @ centre)]))
        quat = _matrix_to_quat(frame)
        xf.AddOrientOp().Set(Gf.Quatf(quat[0], Gf.Vec3f(quat[1], quat[2], quat[3])))
        xf.AddScaleOp().Set(Gf.Vec3f(thick, max(width, 0.004), max(length, 0.004)))
        UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
        _add_physics_material(
            prim.GetPrim(), mu, mu, 0.0, stiffness, damping, colour=(0.07, 0.07, 0.08)
        )
        return 1

    def _author_finger_tip_delta(self, delta: float) -> None:
        """P39 L1: re-author the four finger plates with a signed distal plane.

        `FRUIT_FINGER_TIP_DELTA=<m>` (signed, presence-gated in `build`) is the
        hardware lever from `logs/p39/P1_READ.md` §2: the plate's grip margin is
        `lip + tip-belt clearance == r`, so moving the **distal plane** trades
        lip against belt clearance 1:1. A negative value shortens the plate (F1,
        the authorized "short tip"), a positive one extends it (F2, the
        lip/class form, withheld for owner sign-off), and `0` re-authors the
        shipped plate as its own bounding box (arm S) so the box-for-mesh
        substitution can be measured apart from the geometry change.

        Per link, in the `_finger_face_frame` contact frame (`e_face` toward the
        other finger, `e_mid` across the plate, `e_long` toward the fingertip):

        1. the shipped plate colliders are disabled **by path** - only the
           `visuals/` and `collisions/` subtrees, which is the plate's render
           mesh (made collidable by `_add_finger_colliders`) and the asset's
           convex-decomposition proxy of the same plate. Any CollisionAPI prim
           outside those subtrees is left enabled and reported, never disabled
           wholesale; the palm is a *sibling* link, not a descendant, and its
           collider count is read before and after;
        2. one convex box is authored through `_author_flat_face` - the shipped
           face plane (`face_coord`) unchanged, the full across-width
           (`extents[1]`, ~61 mm) and the full plate thickness in the closing
           direction (`extents[0]`, ~33.3 mm), running from the plate's proximal
           end (`bounds[2]`) to `tip_coord + delta`. The cross-section is the
           whole plate, so the finger cannot go hollow behind the new distal
           plane; at `delta = 0` the box *is* the plate's AABB (long extent
           `84.9 mm`);
        3. the link is re-counted (`_link_collider_counts`) so the build log
           states the collider the finger actually has.

        The **visual** mesh is never touched, so the rendered image is
        unchanged - the reason the finger arms are scripted-line only.

        One build line reports the change; per-link readouts are only printed
        for a link that had to be skipped.
        """
        conflicts: list[str] = []
        face_shape = os.environ.get("FRUIT_FINGER_FACE", "flat").strip().lower()
        if face_shape not in ("", "flat", "none", "0"):
            conflicts.append(f"FRUIT_FINGER_FACE={face_shape}")
        for knob in ("FRUIT_FINGER_PADS", "FRUIT_FINGER_SOFT_PAD", "FRUIT_FINGER_SCOOP"):
            if os.environ.get(knob, "0") == "1":
                conflicts.append(f"{knob}=1")
        if conflicts:
            # Each of those authors its own finger contact geometry (and the
            # soft pads *re-disable* every link collider, which would drop the
            # box again). Refuse rather than build a half-replaced hand.
            say(
                "finger tip delta NOT authored: it replaces the plate collider and "
                "cannot be combined with another finger-geometry mode ("
                + ", ".join(conflicts)
                + ")"
            )
            return
        mu = float(os.environ.get("FRUIT_FINGER_MU", "2.0"))
        stiffness = float(os.environ.get("FRUIT_FINGER_COMPLIANCE", "0"))
        damping = float(os.environ.get("FRUIT_FINGER_CONTACT_DAMPING", "60"))
        palms: dict[str, tuple[int, int] | None] = {}
        for side in ("left", "right"):
            palm = self.stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_hand")
            palms[side] = self._link_collider_counts(palm) if palm.IsValid() else None
        rows: list[dict] = []
        kept_all: list[str] = []
        disabled_total = 0
        for side in ("left", "right"):
            for which in ("left", "right"):
                path = f"/World/OpenArm/openarm_{side}_{which}_finger"
                other = "right" if which == "left" else "left"
                link = self.stage.GetPrimAtPath(path)
                other_link = self.stage.GetPrimAtPath(
                    f"/World/OpenArm/openarm_{side}_{other}_finger"
                )
                tcp = self.stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_ee_tcp")
                visuals = self.stage.GetPrimAtPath(f"{path}/visuals")
                if not (
                    link.IsValid() and other_link.IsValid() and tcp.IsValid()
                    and visuals.IsValid()
                ):
                    say(f"finger tip delta: {path} incomplete; skipped")
                    continue
                points = _link_local_mesh_points(
                    visuals, np.linalg.inv(_world_matrix(link))
                )
                if len(points) < 32:
                    say(f"finger tip delta: {path} has {len(points)} visual points; skipped")
                    continue
                (
                    e_face, e_mid, e_long, face_coord, mid_coord, tip_coord,
                    extents, bounds,
                ) = _finger_face_frame(link, other_link, tcp, points)
                long_lo = float(bounds[2])
                distal = float(tip_coord) + float(delta)
                length = distal - long_lo
                if length < 0.005:
                    say(
                        f"finger tip delta {delta * 1000:+.1f} mm puts the distal "
                        f"plane at {distal * 1000:+.1f} mm, inside the plate's "
                        f"proximal end ({long_lo * 1000:+.1f} mm); {path} skipped"
                    )
                    continue
                disabled, kept = self._disable_finger_plate_colliders(link)
                disabled_total += disabled
                kept_all.extend(kept)
                # Front face on the true face plane, full plate cross-section,
                # proximal end to `tip_coord + delta`. `_author_flat_face` builds
                # the box behind `origin` along `e_face` and forward along
                # `e_long`, and binds FRUIT_FINGER_MU/COMPLIANCE/CONTACT_DAMPING.
                origin = (
                    e_face * float(face_coord)
                    + e_mid * float(mid_coord)
                    + e_long * long_lo
                )
                self._author_flat_face(
                    link, "tip_delta", origin, e_face, e_mid, e_long,
                    length, float(extents[1]), float(extents[0]),
                    mu, stiffness, damping,
                )
                _total, enabled_after = self._link_collider_counts(link)
                rows.append(
                    {
                        "path": path,
                        "face": float(extents[0]),
                        "mid": float(extents[1]),
                        "long": length,
                        "face_plane": float(face_coord),
                        "distal": distal,
                        "tip": float(tip_coord),
                        "enabled": enabled_after,
                    }
                )
        if not rows:
            say(
                f"finger tip delta {delta * 1000:+.1f} mm: no finger link could be "
                "re-authored (see the per-link skips above)"
            )
            return

        def _span(values: list[float]) -> str:
            lo, hi = min(values), max(values)
            if hi - lo <= 5e-5:  # 0.05 mm: the four links are the same plate
                return f"{lo * 1000:.1f}"
            return f"{lo * 1000:.1f}..{hi * 1000:.1f}"

        palms_after = {}
        for side in ("left", "right"):
            palm = self.stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_hand")
            palms_after[side] = self._link_collider_counts(palm) if palm.IsValid() else None
        if palms_after != palms:
            say(
                "WARNING: a palm link's collider count changed while re-authoring the "
                f"finger plates (before={palms}, after={palms_after})"
            )
        palm_text = ", ".join(
            f"openarm_{side}_hand="
            + ("absent" if palms[side] is None else f"{palms[side][0]} prims")
            for side in ("left", "right")
        )
        # Plain `print`, **not** `say`: `say` prefixes `[fruit]` unconditionally
        # (`common.py:28-30`) and every byte-identity criterion in this tree counts
        # `[fruit]` lines, so a knob-set arm would read as a moved stream (the
        # phase-2 `c2` run read 98 `[fruit]` lines against the 92-row physics
        # stream). The identity census filters this tag out (plus `[attitude]`);
        # `accepted` echoes the parsed value, not the raw text.
        print(
            f"[p39] finger tip delta accepted {delta * 1000:+.1f} mm "
            f"(FRUIT_FINGER_TIP_DELTA={os.environ.get('FRUIT_FINGER_TIP_DELTA')!r}): "
            f"{len(rows)}/4 finger links "
            f"re-authored, shipped plate colliders disabled={disabled_total} "
            f"(visuals+collisions), colliders left enabled outside the plate="
            f"{len(kept_all)}"
            + (f" ({', '.join(kept_all)})" if kept_all else "")
            + f"; box face/mid/long={_span([r['face'] for r in rows])}/"
            f"{_span([r['mid'] for r in rows])}/{_span([r['long'] for r in rows])} mm "
            f"(closing x across x down the finger), face plane="
            f"{_span([r['face_plane'] for r in rows])} mm, distal plane="
            f"{_span([r['distal'] for r in rows])} mm (shipped tip "
            f"{_span([r['tip'] for r in rows])} mm), enabled colliders per link after="
            f"{max(r['enabled'] for r in rows)} (contact_faces/tip_delta), palms unchanged: "
            f"{palm_text}",
            flush=True,
        )
        if len(rows) != 4:
            say(f"WARNING: finger tip delta authored on {len(rows)} of 4 finger links")

    def _add_soft_pads(self) -> None:
        """Author the opt-in compliant pad bodies on the OpenArm finger faces.

        This is the D2 mechanism attempt (task option 1): the shipped rigid
        finger face holds a *fixed* separation, so when the payload's local width
        shrinks under the first lift the contact force collapses in the tick the
        faces run out of travel - measured on A2: the in-hand slide grows while
        the force dies and the pop precedes the force signal (`logs/dyn_v5`,
        `logs/dyn_v7`: escape at carry tick 124, hand-frame dev 10.1 mm -> a
        279 mm runaway). Each pad here is a real body on a linear spring-damper
        prismatic joint whose axis is the finger's face normal, so the pad
        follows the local width with millimetres of travel instead of losing
        contact, and it does so passively (no force feedback, no control tick).

        Geometry per finger (link-local, from `_finger_face_frame`):

        * front face `FRUIT_FINGER_SOFT_PAD_PROUD` (0.25 mm) in front of the
          true face plane at rest - a real, visible feature, deliberately much
          smaller than the rejected additive shapes (3-12 mm);
        * the pad spans `FRUIT_FINGER_SOFT_PAD_LEN` (22 mm) along the finger and
          ends `FRUIT_FINGER_SOFT_PAD_BACK` (1 mm) above the fingertip, where
          the dynamic grip and the A2 walk-out sit; it is `WIDE` (24 mm) across
          the finger - a soft-layer footprint, not a narrow strip;
        * with `FRUIT_FINGER_SOFT_PAD_MESH=1` (default) the finger link's own
          colliders are disabled: the pad *is* the contact surface. The first
          form filtered the link from the fruit-pool paths with
          `FilteredPairsAPI`, and that is **measured not to resolve** - the
          fruits are spawned after `play()`, so their paths do not exist at
          PhysX parse (smoke1: the meshes carried ~3 of 4.6 N while the pads
          compressed 0.29 mm). A real pad assembly replaces the contact surface,
          which is what this does (the shipped `FRUIT_PAD_ONLY` mode does the
          same for the kinematic pads); `=0` keeps the meshes for an A/B;
        * `FRUIT_FINGER_SOFT_PAD_FILTER=1` additionally removes the
          pad<->own-link pair, so the pad can compress into the finger volume
          (its bounds are the joint limits, not the mesh).

        The joint is `body0 = pad, body1 = finger link`, `axis = X` in the pad's
        own frame (whose first column is `e_face`), limits `[-TRAVEL, +RELEASE]`
        and a drive of type `force` with `targetPosition = 0`: the spring pushes
        the pad towards the fruit, the fruit pushes it in, and as the local width
        shrinks the spring extends the pad back out to maintain contact. All
        values are baked at build time (before `play()`), so the pad body,
        collider and joint are parsed with the robot.

        Default off: `FRUIT_FINGER_SOFT_PAD=1` selects it and the shipped build
        authors nothing.
        """
        k = float(os.environ.get("FRUIT_FINGER_SOFT_PAD_K", "5000"))
        damp = float(os.environ.get("FRUIT_FINGER_SOFT_PAD_C", "25"))
        travel = max(0.0, float(os.environ.get("FRUIT_FINGER_SOFT_PAD_TRAVEL", "0.005")))
        release = max(0.0, float(os.environ.get("FRUIT_FINGER_SOFT_PAD_RELEASE", "0.001")))
        proud = float(os.environ.get("FRUIT_FINGER_SOFT_PAD_PROUD", "0.00025"))
        thick = max(0.001, float(os.environ.get("FRUIT_FINGER_SOFT_PAD_THICK", "0.003")))
        length = max(0.004, float(os.environ.get("FRUIT_FINGER_SOFT_PAD_LEN", "0.022")))
        wide = max(0.004, float(os.environ.get("FRUIT_FINGER_SOFT_PAD_WIDE", "0.024")))
        back = max(0.0, float(os.environ.get("FRUIT_FINGER_SOFT_PAD_BACK", "0.001")))
        mass = max(1e-4, float(os.environ.get("FRUIT_FINGER_SOFT_PAD_MASS", "0.02")))
        max_force = float(os.environ.get("FRUIT_FINGER_SOFT_PAD_MAX_FORCE", "50"))
        mu = float(os.environ.get("FRUIT_FINGER_MU", "2.0"))
        stiffness = float(os.environ.get("FRUIT_FINGER_COMPLIANCE", "0"))
        damping = float(os.environ.get("FRUIT_FINGER_CONTACT_DAMPING", "60"))
        filter_pairs = os.environ.get("FRUIT_FINGER_SOFT_PAD_FILTER", "1") == "1"
        mesh_off = os.environ.get("FRUIT_FINGER_SOFT_PAD_MESH", "1") == "1"
        colour = (0.85, 0.35, 0.10)

        self.stage.DefinePrim("/World/SoftPads", "Xform")
        info: dict[str, list[dict]] = {"left": [], "right": []}
        made = 0
        disabled_total = 0
        for side in ("left", "right"):
            for which in ("left", "right"):
                path = f"/World/OpenArm/openarm_{side}_{which}_finger"
                other = "right" if which == "left" else "left"
                link = self.stage.GetPrimAtPath(path)
                other_link = self.stage.GetPrimAtPath(
                    f"/World/OpenArm/openarm_{side}_{other}_finger"
                )
                tcp = self.stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_ee_tcp")
                visuals = self.stage.GetPrimAtPath(f"{path}/visuals")
                if not (
                    link.IsValid() and other_link.IsValid() and tcp.IsValid()
                    and visuals.IsValid()
                ):
                    continue
                points = _link_local_mesh_points(visuals, np.linalg.inv(_world_matrix(link)))
                if len(points) < 32:
                    say(f"soft pads: {path} has {len(points)} visual points; skipped")
                    continue
                (
                    e_face, e_mid, e_long, face_coord, mid_coord, tip_coord,
                    extents, _bounds,
                ) = _finger_face_frame(link, other_link, tcp, points)
                # Pad body frame in the link frame: column 0 is the face normal
                # (the joint axis, `axis="X"`), column 1 across the finger,
                # column 2 along it (towards the tip). Right-handed so the quat
                # authoring is unambiguous.
                e_a = np.asarray(e_mid, dtype=float).copy()
                e_g = np.cross(e_face, e_a)
                if float(e_g @ e_long) < 0.0:
                    e_a = -e_a
                    e_g = -e_g
                frame = np.column_stack([e_face, e_a, e_g])
                pad_len = min(length, max(0.9 * float(extents[2]) - back, 0.004))
                pad_wide = min(wide, 0.9 * float(extents[1]))
                # Centre: front face at `face_coord + proud`; distal end `back`
                # above the fingertip (the pad never extends past the tip - the
                # v6 experiment 2 distal plate batted the catch).
                face_off = face_coord + proud - thick / 2.0
                long_off = tip_coord - back - pad_len / 2.0
                local = e_face * face_off + e_mid * mid_coord + e_long * long_off
                link_world = _world_matrix(link)
                world_pos = (link_world @ np.append(local, 1.0))[:3]
                world_rot = link_world[:3, :3] @ frame
                pad_path = f"/World/SoftPads/{side}_{which}"
                pad = UsdGeom.Cube.Define(self.stage, pad_path)
                pad.GetSizeAttr().Set(1.0)
                xf = UsdGeom.Xformable(pad)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in world_pos]))
                quat = _matrix_to_quat(world_rot)
                xf.AddOrientOp().Set(Gf.Quatf(quat[0], Gf.Vec3f(quat[1], quat[2], quat[3])))
                xf.AddScaleOp().Set(Gf.Vec3f(thick, pad_wide, pad_len))
                UsdPhysics.CollisionAPI.Apply(pad.GetPrim())
                UsdPhysics.RigidBodyAPI.Apply(pad.GetPrim())
                UsdPhysics.MassAPI.Apply(pad.GetPrim()).CreateMassAttr().Set(mass)
                _add_physics_material(
                    pad.GetPrim(), mu, mu, 0.0, stiffness, damping, colour=colour
                )
                joint = UsdPhysics.PrismaticJoint.Define(self.stage, f"{pad_path}_joint")
                joint.CreateBody0Rel().SetTargets([pad.GetPath()])
                joint.CreateBody1Rel().SetTargets([link.GetPath()])
                joint.CreateAxisAttr().Set("X")
                joint.CreateLowerLimitAttr().Set(-travel)
                joint.CreateUpperLimitAttr().Set(release)
                joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
                joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                joint.CreateLocalPos1Attr().Set(Gf.Vec3f(*[float(v) for v in local]))
                jq = _matrix_to_quat(frame)
                joint.CreateLocalRot1Attr().Set(Gf.Quatf(jq[0], Gf.Vec3f(jq[1], jq[2], jq[3])))
                drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
                drive.CreateTypeAttr().Set("force")
                drive.CreateStiffnessAttr().Set(k)
                drive.CreateDampingAttr().Set(damp)
                drive.CreateMaxForceAttr().Set(max_force)
                drive.CreateTargetPositionAttr().Set(0.0)
                if filter_pairs:
                    # The pad compresses into the finger volume (its bounds are
                    # the joint limits, not the mesh), so it must not collide
                    # with its own link.
                    pairs = UsdPhysics.FilteredPairsAPI.Apply(pad.GetPrim())
                    pairs.CreateFilteredPairsRel().AddTarget(link.GetPath())
                if mesh_off:
                    # The pad is the grip surface, so the rigid finger mesh
                    # must not take the fruit back after `proud` of travel.
                    # The first form was `FilteredPairsAPI` on the link against
                    # the fruit-pool paths, and it is **measured not to resolve**:
                    # the fruits are spawned *after* `play()`, so their paths do
                    # not exist at PhysX parse and the pair is silently dropped
                    # (`logs/d2_mechanism/smoke1.log`: the finger meshes carried
                    # ~3 of the 4.6 N while the pads compressed only 0.29 mm).
                    # Disable the link's colliders for the pads-on configuration
                    # instead - the pad assembly *is* the contact surface,
                    # exactly like the shipped `FRUIT_PAD_ONLY` kinematic-pad
                    # mode. `FRUIT_FINGER_SOFT_PAD_MESH=0` restores the meshes
                    # for an A/B.
                    disabled = 0
                    for prim in Usd.PrimRange(
                        link, Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
                    ):
                        if prim.HasAPI(UsdPhysics.CollisionAPI):
                            UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)
                            disabled += 1
                    disabled_total += disabled
                info[side].append(
                    {
                        "which": which,
                        "pad_path": pad_path,
                        "link_name": f"openarm_{side}_{which}_finger",
                        "e_face": e_face.copy(),
                        # Projection of the pad centre on the face normal at
                        # rest; the trace reads this back to report compression.
                        "rest_proj": float(face_off),
                    }
                )
                made += 1
                say(
                    f"soft pad {side}_{which}: face={face_coord * 1000:.1f} mm "
                    f"proud={proud * 1000:.2f} mm at {face_off * 1000:.2f} mm, "
                    f"long {pad_len * 1000:.1f} mm ending {back * 1000:.1f} mm "
                    f"above the tip ({tip_coord * 1000:.1f} mm), wide "
                    f"{pad_wide * 1000:.1f} mm, k={k:.0f} N/m c={damp:.0f} Ns/m "
                    f"travel=-{travel * 1000:.1f}/+{release * 1000:.1f} mm "
                    f"mass={mass * 1000:.0f} g"
                )
        self._soft_pad_info = info
        say(
            f"soft pads: {made} compliant pad bodies on the finger faces "
            f"(D2 mechanism; filter_pairs={filter_pairs}, "
            f"finger-mesh colliders disabled={disabled_total} (mesh_off={mesh_off}))"
        )

    def soft_pad_states(self, side: str) -> list[dict]:
        """Per-pad compression [mm] for the dynamic trace (trace-on only).

        `comp_mm` is how far the pad has been pushed *into* the finger relative
        to its authored rest position, positive = compressed. Read live from the
        pad body and its finger link; a trace must never change an outcome, so
        any failure returns `None` rather than raising.
        """
        info = getattr(self, "_soft_pad_info", {}).get(side)
        if not info:
            return []
        out: list[dict] = []
        for pad in info:
            try:
                handle = pad.get("handle")
                if handle is None:
                    handle = RigidPrim(pad["pad_path"])
                    pad["handle"] = handle
                pos = np.asarray(to_numpy(handle.get_world_poses()[0])[0], dtype=float)
                link_pos, link_quat = self.link_pose(pad["link_name"])
                rot = _quat_to_matrix(link_quat)
                face_world = rot @ np.asarray(pad["e_face"], dtype=float)
                comp = float(pad["rest_proj"]) - float(np.dot(pos - link_pos, face_world))
                out.append({"which": pad["which"], "comp_mm": round(comp * 1000.0, 3)})
            except Exception:  # noqa: BLE001 - a trace must never change an outcome
                out.append({"which": pad["which"], "comp_mm": None})
        return out

    def _add_finger_scoops(self) -> None:
        """Author the D2b cradle/scoop ledges on the finger links (opt-in).

        The W8-B mechanism (`logs/w8/B_RESULTS.md`): the payload walks **+z out
        of the fingertip pinch** - it slides down the finger plates while the
        jaws are pried toward their 98-99 mm limit - so a passive support the
        payload can rest on once it starts walking blocks the escape *without
        raising the squeeze* (the squeeze-side family is measured closed;
        `logs/r6/B_RESULTS.md`).

        Geometry per finger, in the `_finger_face_frame` contact frame
        (`e_face` toward the other finger, `e_mid` across the finger, `e_long`
        toward the fingertip):

        * a ledge whose **top face runs from the true face plane** at
          `FRUIT_FINGER_SCOOP_BACK` (2 mm) past the fingertip, inward by
          `FRUIT_FINGER_SCOOP_DEPTH` (6 mm at its distal end) over
          `FRUIT_FINGER_SCOOP_LEN` (12 mm) along the tool axis - a shallow
          sloped shelf, `FRUIT_FINGER_SCOOP_WIDE` (14 mm) across the finger,
          `FRUIT_FINGER_SCOOP_THICK` (4 mm) thick behind its top face;
        * the ledge's proximal top edge sits on the finger's face plane, so the
          shipped close arithmetic is unchanged; the slope grows inward only
          *below* the fingertip, where the payload's local half-width shrinks
          (`clearance` for the widest pool fruit, a 7 cm apple, is ~3.7 mm at
          the proximal edge and grows distally);
        * once the payload's widest section reaches the ledge band, the gap
          between the two ledges is narrower than the payload, so the payload
          comes to rest on the sloped shelves - a V-cradle under the pinch;
        * it is open along `e_mid` (the belt/approach axis): the fruit arrives
          from -Y and the hand descends from +Z, so no approach path is blocked.

        Authored before `play()` as children of the finger links, so PhysX
        parses them into the same rigid bodies as the finger colliders (the
        mechanism `_add_contact_faces` relies on). Default off: with
        `FRUIT_FINGER_SCOOP` unset the shipped build authors nothing.
        """
        depth = max(0.0005, float(os.environ.get("FRUIT_FINGER_SCOOP_DEPTH", "0.006")))
        run = max(0.002, float(os.environ.get("FRUIT_FINGER_SCOOP_LEN", "0.012")))
        back = max(0.0, float(os.environ.get("FRUIT_FINGER_SCOOP_BACK", "0.002")))
        wide = max(0.004, float(os.environ.get("FRUIT_FINGER_SCOOP_WIDE", "0.014")))
        thick = max(0.001, float(os.environ.get("FRUIT_FINGER_SCOOP_THICK", "0.004")))
        mu = float(os.environ.get("FRUIT_FINGER_MU", "2.0"))
        stiffness = float(os.environ.get("FRUIT_FINGER_COMPLIANCE", "0"))
        damping = float(os.environ.get("FRUIT_FINGER_CONTACT_DAMPING", "60"))
        made = 0
        for side in ("left", "right"):
            for which in ("left", "right"):
                path = f"/World/OpenArm/openarm_{side}_{which}_finger"
                other = "right" if which == "left" else "left"
                link = self.stage.GetPrimAtPath(path)
                other_link = self.stage.GetPrimAtPath(
                    f"/World/OpenArm/openarm_{side}_{other}_finger"
                )
                tcp = self.stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_ee_tcp")
                visuals = self.stage.GetPrimAtPath(f"{path}/visuals")
                if not (
                    link.IsValid() and other_link.IsValid() and tcp.IsValid()
                    and visuals.IsValid()
                ):
                    continue
                points = _link_local_mesh_points(visuals, np.linalg.inv(_world_matrix(link)))
                if len(points) < 32:
                    say(f"scoop: {path} has {len(points)} visual points; skipped")
                    continue
                (
                    e_face, e_mid, e_long, face_coord, mid_coord, tip_coord,
                    _extents, _bounds,
                ) = _finger_face_frame(link, other_link, tcp, points)
                # Ledge top face from A (face plane, `back` past the tip) to
                # B (A + depth inward + run along the tool axis).
                origin = e_face * float(face_coord) + e_mid * float(mid_coord)
                a = origin + e_long * (float(tip_coord) + back)
                along = e_face * depth + e_long * run
                length = float(np.linalg.norm(along))
                d_axis = along / length
                n_axis = (e_face * run - e_long * depth) / length
                v_axis = np.cross(n_axis, d_axis)
                if float(v_axis @ e_mid) < 0.0:
                    v_axis = -v_axis
                    d_axis = -d_axis
                centre = a + along / 2.0 - n_axis * (thick / 2.0)
                frame = np.column_stack([n_axis, d_axis, v_axis])
                prim = UsdGeom.Cube.Define(self.stage, f"{path}/scoop")
                prim.GetSizeAttr().Set(1.0)
                xf = UsdGeom.Xformable(prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in centre]))
                quat = _matrix_to_quat(frame)
                xf.AddOrientOp().Set(Gf.Quatf(quat[0], Gf.Vec3f(quat[1], quat[2], quat[3])))
                xf.AddScaleOp().Set(Gf.Vec3f(thick, length, wide))
                UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
                _add_physics_material(
                    prim.GetPrim(), mu, mu, 0.0, stiffness, damping,
                    colour=(0.05, 0.6, 0.25),
                )
                made += 1
                say(
                    f"scoop {side}_{which}: face={face_coord * 1000:.1f} mm, tip="
                    f"{tip_coord * 1000:.1f} mm, top edge {back * 1000:.1f} mm past "
                    f"the tip at the face plane, inward {depth * 1000:.1f} mm over "
                    f"{run * 1000:.1f} mm, wide {wide * 1000:.1f} mm, thick "
                    f"{thick * 1000:.1f} mm"
                )
        say(
            f"scoops: {made} cradle ledges authored on the finger links "
            f"(D2b; depth={depth * 1000:.1f} mm, mu={mu})"
        )

    def _add_environment(self) -> None:
        """Studio-style lighting and a real floor, instead of an infinite grid."""
        from isaacsim.core.experimental.objects import DomeLight, RectLight

        # Matte concrete floor.
        floor = _define_box(
            self.stage, "/World/Floor", size=(8.0, 8.0, 0.04), center=(0.9, 0.0, -0.02)
        )
        _set_color(floor, (0.42, 0.42, 0.43))
        UsdPhysics.CollisionAPI.Apply(floor.GetPrim())

        # Backdrop wall so the cell does not float in a void.
        back = _define_box(
            self.stage, "/World/BackWall", size=(8.0, 0.06, 2.6), center=(0.9, 2.6, 1.3)
        )
        _set_color(back, (0.55, 0.56, 0.58))

        # Sky / ambient dome.
        dome = DomeLight("/World/SkyDome", positions=[0.0, 0.0, 6.0])
        dome.set_intensities(140.0)
        dome.set_colors([0.72, 0.80, 0.92])

        # Sun: a few degrees wide so shadows have a soft edge.
        sun = DistantLight("/World/Sun", positions=[3.5, -3.0, 6.0])
        sun.set_intensities(620.0)
        sun.set_colors([1.0, 0.96, 0.90])
        if hasattr(sun, "set_angles"):
            sun.set_angles(2.5)
        if hasattr(sun, "set_color_temperatures"):
            sun.set_color_temperatures(5400.0)

        # Large soft fill from the camera side, so the fruit do not go black
        # underneath.
        try:
            fill = RectLight(
                "/World/FillPanel",
                positions=[2.2, -2.4, 1.9],
                orientations=[look_at_quat((2.2, -2.4, 1.9), (0.5, 0.0, 1.1))],
            )
            fill.set_intensities(2200.0)
            fill.set_colors([0.95, 0.97, 1.0])
        except Exception as exc:  # noqa: BLE001
            say(f"rect fill light unavailable: {exc}")

        say("studio lighting + floor + backdrop added")

    def _add_pedestal(self) -> None:
        cfg = self.cfg
        height = cfg.table_top_z
        sx, sy = cfg.pedestal_size
        prim = _define_box(
            self.stage,
            "/World/Pedestal",
            size=(sx, sy, height),
            center=(cfg.pedestal_center_xy[0], cfg.pedestal_center_xy[1], height / 2.0),
        )
        _set_color(prim, (0.35, 0.37, 0.40))
        UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
        say(f"pedestal top at z={height:.2f} m")

    def _add_robot(self) -> None:
        prim = self.stage.DefinePrim("/World/OpenArm", "Xform")
        prim.GetReferences().AddReference(OPENARM_BIMANUAL_USD)
        UsdGeom.Xformable(prim).ClearXformOpOrder()
        UsdGeom.Xformable(prim).AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, self.cfg.robot_base_z))
        local = not str(OPENARM_BIMANUAL_USD).startswith("http") and os.path.exists(
            str(OPENARM_BIMANUAL_USD)
        )
        say(
            f"robot referenced -> {'local flattened asset' if local else 'remote asset'} "
            f"({OPENARM_BIMANUAL_USD})"
        )

    def _add_conveyor(self) -> None:
        """Cleated track conveyor: belt surface, cleats, pulleys, frame."""
        from .conveyor import CleatedBelt

        self.belt = CleatedBelt(self.stage, self.cfg)
        self.belt.build()
        say(f"belt surface z={self.belt.belt_top:.3f}")

    def _add_output_belts(self) -> None:
        """Two raised output conveyors, one per side, carrying along +X.

        They replace the old output bins: instead of the arm lowering a fruit
        into a chute beside itself, it lifts the fruit over the main line and
        sets it down on the raised belt, which carries it away - the real
        "put it on the output line" motion. At the far (+X) end each belt
        discharges over a chute into a shallow tray (real line hardware, so a
        placed fruit has somewhere to end up instead of the floor). The
        geometry and the clearances are in `SceneConfig`; the builder reports
        them (`OutputBelt.build`).
        """
        from .conveyor import OutputBelt

        self.output_belts = []
        for index, sign in ((0, 1.0), (1, -1.0)):
            belt = OutputBelt(self.stage, self.cfg, index, sign)
            belt.build()
            self.output_belts.append(belt)
        say("output conveyors added (2 x raised belts along +X)")

    def _add_head_camera(self) -> None:
        cfg = self.cfg
        annotators = [
            a.strip()
            for a in os.environ.get(
                "FRUIT_CAMERA_ANNOTATORS",
                # NOTE: the "instance_segmentation" and "pointcloud" annotators
                # segfault this Isaac Sim 6.0.1-rc build headless. Use
                # "instance_id_segmentation" for per-prim masks instead; it gives
                # the same per-fruit instance information.
                #
                # "bounding_box_2d_tight" is deliberately *not* in the default
                # list: nothing in this repo consumes it (the target mask comes
                # from "instance_id_segmentation"), and asking for it makes
                # omni.syntheticdata build the semantic-label graph, which then
                # floods the log with "OgnSdSemanticLabelsMap: invalid input AOV
                # SemanticLabelTokenSD" at every frame. Add it back with
                # FRUIT_CAMERA_ANNOTATORS=rgb,distance_to_image_plane,instance_id_segmentation,bounding_box_2d_tight
                # if a demo wants drawn boxes.
                "rgb,distance_to_image_plane,instance_id_segmentation",
            ).split(",")
            if a.strip()
        ]
        resolution = tuple(
            int(v) for v in os.environ.get(
                "FRUIT_CAMERA_RES",
                f"{cfg.camera_resolution[0]},{cfg.camera_resolution[1]}",
            ).split(",")
        )
        eye = (cfg.head_camera_forward, 0.0, cfg.head_camera_z)
        target = cfg.head_camera_target

        # Head mast + housing: a physical-looking mount for the camera. They sit
        # *behind* the lens (a mast in front of it is a black column over half the
        # image - measured, logs/pick_head.png), and both are visual-only so the
        # arms cannot collide with the robot's own head.
        mast = _define_box(
            self.stage,
            "/World/HeadMast",
            size=(0.03, 0.03, 0.22),
            center=(eye[0] - 0.12, 0.0, cfg.head_camera_z - 0.11),
        )
        _set_color(mast, (0.20, 0.21, 0.23))
        housing = _define_box(
            self.stage,
            "/World/HeadHousing",
            size=(0.10, 0.13, 0.08),
            center=(eye[0] - 0.05, 0.0, eye[2]),
        )
        _set_color(housing, (0.16, 0.17, 0.19))

        self.camera = RtxCamera(
            "/World/HeadCamera",
            tick_rate=30.0,
            positions=[eye],
            orientations=[look_at_quat(eye, target)],
        )
        # OpenUSD optics are in tenths of a scene unit.
        self.camera.camera.set_focal_lengths(cfg.camera_focal_length)
        self.camera.camera.set_apertures(cfg.camera_aperture)
        self.camera.camera.set_focus_distances(1.0)
        self.camera.camera.set_clipping_ranges(0.01, 50.0)
        self.camera_sensor = CameraSensor(
            self.camera,
            resolution=resolution,
            annotators=annotators,
        )
        say(f"head camera at {eye} looking at {target}, res={resolution}, annotators={annotators}")

    # ------------------------------------------------------------------ #
    # Runtime
    # ------------------------------------------------------------------ #
    def start(self, physics_dt: float = 1.0 / 120.0, warmup_steps: int = 60) -> None:
        """Start physics and instantiate the articulation handle."""
        import carb

        from isaacsim.core.simulation_manager import SimulationManager

        # Pin the simulation to a fixed timestep. Otherwise Kit advances physics
        # by wall-clock time, so a slow frame (camera + sensors + IK) makes the
        # world jump many physics steps at once and the belt appears to teleport.
        # `FRUIT_SUBSTEPS` shrinks the *physics* step below the control period so
        # contacts can be resolved as stiff springs instead of impulses.
        self.control_dt = physics_dt
        physics_dt = physics_dt / substeps()
        say(f"physics substeps = {substeps()} (dt = {physics_dt:.5f}s)")
        settings = carb.settings.get_settings()
        settings.set("/app/player/useFixedTimeStep", True)
        settings.set("/app/player/fixedTimeStep", physics_dt)

        say("setting tensor backend = torch")
        SimulationManager.set_backend("torch")
        say("switching physics engine = physx")
        SimulationManager.switch_physics_engine("physx")
        say(f"setting physics dt = {physics_dt:.5f}s")
        SimulationManager.set_physics_dt(physics_dt)
        say("play(commit=True)")
        app_utils.play(commit=True)
        say(f"warm-up {warmup_steps} steps")
        if os.environ.get("FRUIT_FIXED_STEPPING", "1") == "1":
            # Tick-exact warm-up; see the note in `scripts/20_pick_place.py`. The
            # app-driven advance is wall-clock dependent (118 vs 120 ticks measured
            # for the same 60 calls), which is enough to change which branch a run
            # takes. Default on for that reason; =0 restores the app-driven advance.
            SimulationManager.step(steps=warmup_steps)
            # ... plus a pump-only update, because `update_app` is also what services
            # the camera/sensor callbacks.
            app_utils.update_app(steps=0)
        else:
            app_utils.update_app(steps=warmup_steps)
        # Prime the head camera's annotators. With the flattened local robot asset
        # the first `get_data("rgb")` after `play()` can still return an empty
        # buffer - the evaluator reads it at its first step and its guard raises on
        # `rgb[0]` (`logs/455/456`). Two render passes (which do not advance
        # physics) make the first annotated frame available.
        if self.camera_sensor is not None:
            from isaacsim.core.rendering_manager import RenderingManager

            for _ in range(2):
                RenderingManager.render()
                self.camera_sensor.get_data("rgb")
        if os.environ.get("FRUIT_PAUSE_TIMELINE", "0") == "1":
            # Stop the app's own timeline. With it running, Kit advances physics by
            # *wall-clock* time on every update, so the number of steps a run takes
            # depends on how busy the machine is - measured directly: one scripted
            # attempt lands its fruit at 8.5 cm (328-tick descent) on an idle
            # machine and 8.7 cm (334 ticks) under load, and the whole run follows
            # one of those two branches (WORKLOG "the attractor is chosen by the
            # clock"). With the timeline paused, physics only advances when the code
            # steps it, which is what makes `SimulationManager.step`/`update_app(steps=)`
            # mean a fixed number of ticks.
            app_utils.pause()
            say("timeline paused: physics advances only when the code steps it")
        if self.belt is not None:
            self.belt.reset()
        if self.stage.GetPrimAtPath("/World/OpenArm").IsValid():
            self.robot = Articulation("/World/OpenArm")
            say(f"simulation running, dt={physics_dt:.5f}s, joints={len(self.robot.joint_names)}")
        else:
            say(f"simulation running, dt={physics_dt:.5f}s (no robot in this scene)")

    def step(self, n: int = 1) -> None:
        app_utils.update_app(steps=n)

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    def report_robot(self) -> None:
        for side, link in OPENARM_TCP_LINKS.items():
            pose, _ = self.link_pose(link)
            say(f"TCP {side:5s} at {np.round(pose, 4).tolist()}")

    def _link_handle(self, link_name: str):
        """Cache a RigidPrim handle for one articulation link (root pose reads only cover the base)."""
        if not hasattr(self, "_link_handles"):
            self._link_handles = {}
        if link_name not in self._link_handles:
            index = list(self.robot.link_names).index(link_name)
            paths = self.robot.link_paths
            if paths and isinstance(paths[0], (list, tuple)):
                paths = paths[0]
            path = paths[index]
            if isinstance(path, (list, tuple)):
                path = path[0]
            self._link_handles[link_name] = RigidPrim(str(path))
        return self._link_handles[link_name]

    def link_pose(self, link_name: str) -> tuple[np.ndarray, np.ndarray]:
        positions, orientations = self._link_handle(link_name).get_world_poses()
        return to_numpy(positions)[0], to_numpy(orientations)[0]

    def capture(self, path: str) -> dict[str, np.ndarray]:
        from PIL import Image

        images = {
            "rgb": to_numpy(self.camera_sensor.get_data("rgb")),
            "depth": to_numpy(self.camera_sensor.get_data("distance_to_image_plane")),
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if images["rgb"] is not None:
            Image.fromarray(images["rgb"][..., :3].astype(np.uint8)).save(path)
            say(f"saved {path}")
        if images["depth"] is not None:
            depth = images["depth"][..., 0].astype(np.float32)
            finite = np.isfinite(depth) & (depth > 0.0)
            if np.any(finite):
                lo, hi = np.percentile(depth[finite], [2, 98])
                norm = np.clip((depth - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
                norm[~finite] = 0.0
                Image.fromarray((norm * 255).astype(np.uint8)).save(path.replace(".png", "_depth.png"))
                say(f"depth valid={int(finite.sum())}/{finite.size} range=[{lo:.2f},{hi:.2f}] m")
        return images
