#!/usr/bin/env python3
"""P104 stage (ii): the axial break-away fixture - does more contact beat the pinch?

**What this measures.** A static grasp on one fruit, loaded along the tool axis
(the direction the payload leaves in the shipped cell: `logs/p61`, `logs/p75`,
`logs/p102`) by an external force ramped at a controlled rate, until the payload
has moved `P104_BREAK_MM` (the survey's own `clean_slip > 2 mm` criterion,
`docs/PLATFORM_SURVEY.md` section 3.3). The number reported is the **axial load
at break** = applied force + the payload's own weight, in newtons.

**Why it is a fixture and not a policy run.** No arm, no scheduler, no attempt
machinery, no camera: one fruit, `n` pads on prismatic drives, one force ramp.
The pads are primitive boxes carrying the *measured* pad geometry
(`logs/p66/COLLIDER_READ.md`: face 61.000 x 84.902 mm, distal plane 80.5 mm below
the jaw centre, `tasks.FINGER_TIP_BELOW_JAW`) and the *shipped* drive stiffness
(`control.finger_drive_profile`, `finger_damp02`: k = 1e5 N/m) at the *measured*
per-face pinch force (`logs/p41/P3_RESULTS.md`: 9.75-9.9 N total over two faces
= 4.9 N per face), so every form is loaded with the same per-contact normal
force and differs only in how many contacts there are and where they sit.

**Cells** (`P104_FORM`):
  `pinch_plate`        two 61 mm plates, opposed            - the shipped pinch
  `pinch_tip`          two 16 mm tips, opposed             - the matched control
  `tripod`             three tips at 120 deg
  `quad`               four tips at 90 deg
  `lip`                two tips + a static distal ledge    - the geometry case
  `pinch_tip_moment`   two tips, pull 20 mm off the axis
  `tripod_moment`      three tips, pull 20 mm off the axis

**What it cannot decide** (stated before the run, `RESULTS.md` section 0): the
static axial break-away only. Not the acquisition (`logs/p47`/`p48`), not the
carry dynamics, not a real hand's kinematics, not the policy.

    P104_FORM=pinch_tip scripts/run.sh logs/p104/fixture_probe.py

Every form is its own app session (the pad set is authored before `play()`), so
the driver loops the form list: `bash logs/p104/run_p104.sh`.
"""

from __future__ import annotations

import os
import sys
import time

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import numpy as np
from pxr import Gf, Sdf, UsdGeom, UsdPhysics, UsdShade

from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say, substeps
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent
from fruit_sorting.motion import min_jerk_ramp
from fruit_sorting.scene import SortingScene

DT = 1.0 / 120.0

FORM = os.environ.get("P104_FORM", "pinch_tip")
FORMS = (
    "pinch_plate",
    "pinch_tip",
    "tripod",
    "quad",
    "lip",
    "pinch_tip_moment",
    "tripod_moment",
)
FRUITS = tuple(
    f.strip() for f in os.environ.get("P104_FRUITS", "pear,orange,strawberry").split(",") if f.strip()
)
REPEATS = int(os.environ.get("P104_REPEATS", "3"))
SEED = int(os.environ.get("P104_SEED", "5"))

#: Per-contact normal force [N]: half the measured delivered pinch
#: (`logs/p41/P3_RESULTS.md`: 9.75-9.9 N total over the two faces).
N_CONTACT = float(os.environ.get("P104_N_CONTACT", "4.90"))
#: The shipped finger drive stiffness (`control.finger_drive_profile`).
PAD_STIFFNESS = float(os.environ.get("P104_PAD_STIFFNESS", "100000.0"))
#: Near-critically damped for the pad mass below (`2*sqrt(k*m)` = 89). The drive
#: is **force-saturated** for the whole measurement, so neither constant enters
#: the measured break-away - the cap does.
PAD_DAMPING = float(os.environ.get("P104_PAD_DAMPING", "100.0"))
PAD_MASS = float(os.environ.get("P104_PAD_MASS", "0.02"))
PAD_MU = float(os.environ.get("P104_PAD_MU", "2.0"))
#: Face radius at the pads' authored home [m]. Wider than the 76 mm maximum the
#: real fingers open to, so the pear clears it.
HOME_FACE_R = float(os.environ.get("P104_HOME_R", "0.042"))
#: Commanded interference inside the measured extent [m]; the drive saturates,
#: so this only has to exceed `N_CONTACT / PAD_STIFFNESS` (49 um).
INTERFERENCE = float(os.environ.get("P104_INTERFERENCE", "0.005"))
#: Close ramp [ticks]. The closure *speed* is not a variable here - the drive is
#: saturated at the cap either way - but a slow one keeps the pad on its target.
CLOSE_TICKS = int(os.environ.get("P104_CLOSE_TICKS", "150"))
#: Pin the payload while the pads close (a free fruit falls during the ramp).
PIN_TICKS = int(os.environ.get("P104_PIN_TICKS", "230"))
#: Settle after the pin is released, before the ramp starts.
SETTLE_TICKS = int(os.environ.get("P104_SETTLE_TICKS", "90"))
#: Force ramp [N/s] and its ceiling [N].
RATE = float(os.environ.get("P104_RATE", "5.0"))
F_MAX = float(os.environ.get("P104_F_MAX", "40.0"))
#: The survey's break criterion (`clean_slip > 2 mm`) and the "gone" distance.
BREAK_M = float(os.environ.get("P104_BREAK_MM", "2.0")) / 1000.0
EXIT_M = float(os.environ.get("P104_EXIT_MM", "30.0")) / 1000.0
#: Off-axis lever for the moment cells [m].
MOMENT_OFFSET = float(os.environ.get("P104_MOMENT_OFFSET", "0.020"))

#: The fixture's jaw centre. The pads hang below it and the payload's centre sits
#: `PAD_STANDOFF` (70 mm = `FRUIT_FINGER_LEN` 60 + `FRUIT_PAD_LIFT` 10) further
#: along the tool axis, which is world -Z here (the pull is with gravity).
JAW_Z = 1.30
PAD_STANDOFF = 0.070
#: The plate's distal plane, from `tasks.FINGER_TIP_BELOW_JAW` (80.5 mm).
DISTAL_Z = 0.0805
PLATE_LEN = 0.0849
PLATE_WIDTH = 0.0610
TIP_WIDTH = 0.0160
TIP_LEN = 0.0300
PAD_THICK = 0.010


def theta_slots(form: str) -> tuple[float, ...]:
    if form in ("pinch_plate", "pinch_tip", "lip", "pinch_tip_moment"):
        return (0.0, 180.0)
    if form in ("tripod", "tripod_moment"):
        return (30.0, 150.0, 270.0)
    if form == "quad":
        return (45.0, 135.0, 225.0, 315.0)
    raise SystemExit(f"unknown form {form!r}")


def pad_width(form: str) -> float:
    return PLATE_WIDTH if form == "pinch_plate" else TIP_WIDTH


def pad_length(form: str) -> float:
    return PLATE_LEN if form == "pinch_plate" else TIP_LEN


def pad_z_centre(form: str) -> float:
    """Pad centre in the *fixture* frame (+Z = down the tool axis) [m]."""
    # Both shapes share the distal plane, so both have the same 10.5 mm lip
    # below the payload's equator.
    return DISTAL_Z - pad_length(form) / 2.0


def _pad_material(stage, path: str):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
        Gf.Vec3f(0.15, 0.15, 0.16)
    )
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    api.CreateStaticFrictionAttr().Set(PAD_MU)
    api.CreateDynamicFrictionAttr().Set(PAD_MU)
    api.CreateRestitutionAttr().Set(0.0)
    return mat


def author_pads(stage, form: str):
    """One anchor, one prismatic pad body per contact, plus the optional ledge."""
    anchor_path = "/World/P104/Anchor"
    anchor = UsdGeom.Xform.Define(stage, anchor_path)
    xf = UsdGeom.Xformable(anchor)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, JAW_Z))
    UsdPhysics.RigidBodyAPI.Apply(anchor.GetPrim()).CreateKinematicEnabledAttr().Set(True)
    UsdPhysics.MassAPI.Apply(anchor.GetPrim()).CreateMassAttr().Set(1.0)

    pads = []
    for k, theta in enumerate(theta_slots(form)):
        th = np.deg2rad(theta)
        u = np.array([np.cos(th), np.sin(th), 0.0])
        roll = th + np.pi / 2.0  # the joint frame's +Y -> -u (inward)
        body_path = f"/World/P104/Pad{k}"
        body = UsdGeom.Xform.Define(stage, body_path)
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
        UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr().Set(PAD_MASS)
        bxf = UsdGeom.Xformable(body)
        bxf.ClearXformOpOrder()
        centre = u * (HOME_FACE_R + PAD_THICK / 2.0) + np.array(
            [0.0, 0.0, JAW_Z - pad_z_centre(form)]
        )
        bxf.AddTranslateOp().Set(Gf.Vec3d(*[float(c) for c in centre]))
        bxf.AddRotateZOp().Set(float(np.rad2deg(roll)))

        cube = UsdGeom.Cube.Define(stage, f"{body_path}/Pad")
        cube.GetSizeAttr().Set(1.0)
        cxf = UsdGeom.Xformable(cube)
        cxf.ClearXformOpOrder()
        cxf.AddScaleOp().Set(Gf.Vec3f(pad_width(form), PAD_THICK, pad_length(form)))
        UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
        UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(
            _pad_material(stage, f"{body_path}/Pad_mat")
        )

        joint = UsdPhysics.PrismaticJoint.Define(stage, f"{body_path}_joint")
        joint.CreateBody0Rel().SetTargets([anchor_path])
        joint.CreateBody1Rel().SetTargets([body_path])
        joint.CreateAxisAttr().Set("Y")
        joint.CreateLowerLimitAttr().Set(0.0)
        joint.CreateUpperLimitAttr().Set(0.080)
        joint.CreateLocalPos0Attr().Set(
            Gf.Vec3f(*[float(c) for c in (centre - np.array([0.0, 0.0, JAW_Z]))])
        )
        joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        joint.CreateLocalRot0Attr().Set(
            Gf.Quatf(float(np.cos(roll / 2.0)), 0.0, 0.0, float(np.sin(roll / 2.0)))
        )
        joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
        drive.CreateTypeAttr().Set("force")
        drive.CreateStiffnessAttr().Set(PAD_STIFFNESS)
        drive.CreateDampingAttr().Set(PAD_DAMPING)
        drive.CreateMaxForceAttr().Set(N_CONTACT)
        drive.CreateTargetPositionAttr().Set(0.0)
        pads.append(
            {
                "name": f"Pad{k}",
                "theta": theta,
                "u": u,
                "home": centre,
                "body": body_path,
                "drive": drive,
            }
        )

    ledge = None
    if form == "lip":
        ledge_path = "/World/P104/Ledge"
        box = UsdGeom.Cube.Define(stage, ledge_path)
        box.GetSizeAttr().Set(1.0)
        lxf = UsdGeom.Xformable(box)
        lxf.ClearXformOpOrder()
        # Translate *then* scale: USD composes the ops left to right, so a scale
        # authored first would scale the translation too (the `_box` order).
        ledge = {"path": ledge_path, "translate": lxf.AddTranslateOp()}
        lxf.AddScaleOp().Set(Gf.Vec3f(0.050, 0.050, 0.008))
        UsdPhysics.CollisionAPI.Apply(box.GetPrim())
        UsdShade.MaterialBindingAPI.Apply(box.GetPrim()).Bind(
            _pad_material(stage, f"{ledge_path}_mat")
        )
    return pads, ledge


def step(n: int = 1) -> None:
    for _ in range(max(1, int(n))):
        SimulationManager.step(steps=substeps())


def enable_tracking(path: str):
    """Contact tracking must be armed at authoring time and re-asserted after play."""
    try:
        prim = RigidPrim(path)
        prim.set_enabled_contact_tracking(True, threshold=1e-3)
        return prim
    except Exception as exc:  # noqa: BLE001
        say(f"[p104] WARNING: contact tracking unavailable for {path}: {exc}")
        return None


def main() -> int:
    wall0 = time.time()
    if FORM not in FORMS:
        raise SystemExit(f"P104_FORM must be one of {FORMS}")
    if substeps() != 1:
        say("[p104] WARNING: FRUIT_SUBSTEPS != 1; the force ramp is per substep")
    say(
        f"[p104] form={FORM} fruits={FRUITS} repeats={REPEATS} seed={SEED} "
        f"substeps={substeps()} N_contact={N_CONTACT:.2f}N rate={RATE:.1f}N/s"
    )

    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment",))
    spawner = FruitSpawner(scene.stage, cfg, seed=SEED)
    spawner.create_pool()
    pads, ledge = author_pads(scene.stage, FORM)

    # Contact tracking at authoring time (a fruit authored before play gets its
    # physics view at play time; see scripts/210_squeeze_probe.py).
    for p in pads:
        p["authoring_handle"] = enable_tracking(p["body"])
    for sample in spawner.samples:
        enable_tracking(sample.prim_path)

    scene.start(physics_dt=DT, warmup_steps=60)
    step(30)
    spawner.refresh_rigids()
    for p in pads:
        p["handle"] = enable_tracking(p["body"]) or p["authoring_handle"]
    for sample in spawner.samples:
        enable_tracking(sample.prim_path)
    for sample in spawner.samples:
        spawner.park(sample)
    step(20)

    picks: dict[str, object] = {}
    for sample in spawner.samples:
        picks.setdefault(sample.category, sample)

    rows = []
    for category in FRUITS:
        sample = picks.get(category)
        if sample is None:
            say(f"[p104] WARNING: no {category} in the pool")
            continue
        shape = FRUIT_SHAPES[category]
        rigid = spawner._rigids[sample.index]
        fruit_z = JAW_Z - PAD_STANDOFF
        # Per-pad normal force: a contact view filtered to this payload.
        for p in pads:
            try:
                p["force_handle"] = RigidPrim(p["body"], contact_filter_paths=[sample.prim_path])
            except Exception as exc:  # noqa: BLE001
                say(f"[p104] WARNING: no contact view for {p['body']}: {exc}")
                p["force_handle"] = None
        quarter = axis_extent(shape, float(sample.diameter), np.array([1.0, 0.0, 0.0])) / 2.0
        say(
            f"[p104] geometry: {category} d={sample.diameter*1000:.1f}mm "
            f"mass={sample.mass*1000:.1f}g mu={sample.friction:.3f} "
            f"half_x={quarter*1000:.1f}mm pads={len(pads)} "
            f"widths={[round(pad_width(FORM)*1000,1)]} len={pad_length(FORM)*1000:.1f}mm "
            f"distal={JAW_Z-DISTAL_Z:.3f} fruit_z={fruit_z:.3f}"
        )
        if ledge is not None:
            half_down = axis_extent(shape, float(sample.diameter), np.array([0.0, 0.0, 1.0])) / 2.0
            top = fruit_z - half_down - 0.0002  # 0.2 mm clearance: supports, not preloads
            ledge["translate"].Set(Gf.Vec3d(0.0, 0.0, float(top - 0.004)))
            say(f"[p104] ledge top={top:.4f} (fruit bottom {fruit_z - half_down:.4f})")

        # Per-direction extents, from the profile (no mesh read in the loop).
        for rep in range(REPEATS):
            spawner.place(sample, np.array([0.0, 0.0, fruit_z]))
            step(2)
            targets = []
            for p in pads:
                extent = axis_extent(shape, float(sample.diameter), p["u"])
                targets.append(HOME_FACE_R - (extent / 2.0 - INTERFERENCE))
            for p in pads:
                p["drive"].CreateTargetPositionAttr().Set(0.0)
            step(10)
            for frac in min_jerk_ramp(0.0, 1.0, CLOSE_TICKS):
                for p, target in zip(pads, targets):
                    p["drive"].CreateTargetPositionAttr().Set(float(target * frac))
                spawner.place(sample, np.array([0.0, 0.0, fruit_z]))
                step(1)
            for _ in range(max(1, PIN_TICKS - CLOSE_TICKS)):
                spawner.place(sample, np.array([0.0, 0.0, fruit_z]))
                step(1)
            # Release: the payload is held by the contacts alone.
            step(SETTLE_TICKS)
            start = spawner.position(sample).copy()
            settle_vec = start - np.array([0.0, 0.0, fruit_z])
            settle_slip = float(np.linalg.norm(settle_vec))
            pad_n = []
            for p in pads:
                try:
                    forces = np.asarray(
                        p["force_handle"].get_net_contact_forces().numpy(), dtype=float
                    )[0]
                    pad_n.append(float((forces @ p["u"]) / DT))
                except Exception:  # noqa: BLE001
                    pad_n.append(float("nan"))
            weight = float(sample.mass) * 9.81
            say(
                f"[p104]   seat: targets={[round(t*1000,1) for t in targets]}mm "
                f"padN={[round(v,2) for v in pad_n]} settle={settle_slip*1000:.2f}mm "
                f"(dx={settle_vec[0]*1000:+.2f} dy={settle_vec[1]*1000:+.2f} "
                f"dz={settle_vec[2]*1000:+.2f})"
            )

            # Ramp the axial load. +z is down the tool axis (with gravity), so every
            # contact normal is perpendicular to the pull: the pure Coulomb axial
            # case the analytic table prices.
            moment = FORM.endswith("_moment")
            applied = 0.0
            f_break = float("nan")
            f_exit = float("nan")
            reported_disp = 0.0
            max_disp = 0.0
            pry_at_break = float("nan")
            n_at_break = ""

            def pad_radial() -> list[float]:
                out = []
                for p in pads:
                    try:
                        pos = np.asarray(p["handle"].get_world_poses()[0].numpy(), dtype=float)[0]
                        home = np.asarray(p["home"], dtype=float)
                        out.append(float((pos - home) @ p["u"]) * 1000.0)
                    except Exception:  # noqa: BLE001
                        out.append(float("nan"))
                return out

            def pad_normal() -> list[float]:
                out = []
                for p in pads:
                    try:
                        forces = np.asarray(
                            p["force_handle"].get_net_contact_forces().numpy(), dtype=float
                        )[0]
                        out.append(float((forces @ p["u"]) / DT))
                    except Exception:  # noqa: BLE001
                        out.append(float("nan"))
                return out

            n_steps = int(round(F_MAX / (RATE * DT)))
            radial0 = pad_radial()
            for _ in range(n_steps):
                applied = min(F_MAX, applied + RATE * DT)
                force = np.array([[0.0, 0.0, -applied]], dtype=float)
                if moment:
                    rigid.apply_forces_and_torques_at_pos(
                        forces=force,
                        positions=[[start[0] + MOMENT_OFFSET, start[1], start[2]]],
                    )
                else:
                    rigid.apply_forces(force)
                step(1)
                delta = spawner.position(sample) - start
                disp = float(np.linalg.norm(delta))
                max_disp = max(max_disp, disp)
                if np.isnan(f_break) and disp >= BREAK_M:
                    f_break = applied + weight
                    reported_disp = disp
                    pry_at_break = max(
                        (a - b for a, b in zip(pad_radial(), radial0)), default=float("nan")
                    )
                    n_at_break = ",".join(f"{v:.2f}" for v in pad_normal())
                if not np.isnan(f_break) and max_disp >= EXIT_M:
                    f_exit = applied + weight
                    break
            rows.append(
                {
                    "form": FORM,
                    "fruit": category,
                    "d_mm": float(sample.diameter) * 1000.0,
                    "mass_g": float(sample.mass) * 1000.0,
                    "mu_fruit": float(sample.friction),
                    "n_pads": len(pads),
                    "n_mean": float(np.nanmean(pad_n)) if pad_n else 0.0,
                    "n_rows": ",".join(f"{v:.2f}" for v in pad_n),
                    "settle_mm": settle_slip * 1000.0,
                    "settle_dx": float(settle_vec[0]) * 1000.0,
                    "settle_dy": float(settle_vec[1]) * 1000.0,
                    "settle_dz": float(settle_vec[2]) * 1000.0,
                    "f_break": f_break,
                    "disp_mm": reported_disp * 1000.0,
                    "f_exit": f_exit,
                    "max_disp_mm": max_disp * 1000.0,
                    "pry_mm": pry_at_break,
                    "n_break": n_at_break,
                    "rep": rep,
                }
            )
            say(
                f"[p104] {FORM:16s} {category:10s} d={sample.diameter*1000:5.1f}mm "
                f"mu={sample.friction:4.2f} pads={len(pads)} N={rows[-1]['n_mean']:4.2f}N "
                f"settle={settle_slip*1000:4.1f}mm F2mm={f_break:6.2f}N "
                f"disp={rows[-1]['disp_mm']:5.1f}mm Fexit={f_exit:6.2f}N "
                f"max={max_disp*1000:5.1f}mm pry={pry_at_break:6.2f}mm "
                f"n@2mm=[{n_at_break}]"
            )
            # Open the pads and park the payload for the next repeat.
            for p in pads:
                p["drive"].CreateTargetPositionAttr().Set(0.0)
            step(20)
            spawner.park(sample)
            step(10)

    print()
    print(
        "form             fruit       d[mm]  mu   n  N[N]  settle[mm]  F2mm[N]  "
        "disp[mm]  Fexit[N]  max[mm]  pry[mm]"
    )
    for r in rows:
        print(
            f"{r['form']:16s} {r['fruit']:10s} {r['d_mm']:6.1f} {r['mu_fruit']:4.2f} "
            f"{r['n_pads']:2d} {r['n_mean']:5.2f} {r['settle_mm']:9.2f} "
            f"{r['f_break']:8.2f} {r['disp_mm']:8.1f} {r['f_exit']:8.2f} "
            f"{r['max_disp_mm']:7.1f} {r['pry_mm']:7.2f}"
        )
    say(f"[p104] DONE form={FORM} rows={len(rows)} wall={time.time()-wall0:.1f}s")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
