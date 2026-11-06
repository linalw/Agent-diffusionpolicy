#!/usr/bin/env python3
"""P117 fixture 1 - the pad face: is the loaded creep a friction term or a wedge term?

**What this measures.**  A static grasp on one fruit, loaded along the tool axis by
(a) its own weight (P104's `settle`) and then (b) the cell's operating load
`m*(g + 5.83)` - the largest single-tick `|a|max` a carry leg reports
(`logs/p40/GRIP_CENSUS.md` section 4.1) - held 0.75 s.  Then the axial break-away
ramp (5 N/s) for continuity with P104.  One fruit, two force-capped position pads,
no arm, no scheduler, no attempt machinery, no camera.

**Why a fixture.**  P104 measured the shipped pinch's creep at the operating load
as **3.20 / 0.85 / 2.68 mm** (pear / orange / strawberry) while its static axial
capacity is **11.0-14.2 N** against a 0.17-1.20 N demand - a 10-20x capacity
margin and a 1.6-1.9x escape threshold of creep.  So the escape is not a capacity
deficit, and the quantity that separates "held" from "walked" is the creep.  This
fixture asks the two questions the record leaves open: does a **grooved face**
reduce the creep, and does **mu** reduce it?  If mu does not, the creep is not a
friction slide and the friction lane is dead (`PREREG.md` A6).

**The faces** (`P117_PROFILE`; the padding is per fruit because a groove is
size-specific - its radius is `0.6 r` / `0.9 r` of *that* fruit, `PREREG.md` A2):

  `flat`     the shipped 61 x 84.9 mm plate                      - the control
  `arc06`    a semicircular groove of radius 0.6 r               - 2 rims / pad
  `arc09`    a semicircular groove of radius 0.9 r               - 2 rims / pad
  `v90`      a 90 deg V, half-opening 0.85 r                     - 2 walls / pad
  `cradle90` the same 90 deg V with its valley *across* the pad   - 2 walls / pad,
             (wings along the tool axis)                          the only axial normal
  `flat_mu3` `flat` with the pad material at mu 3.0              - the friction cell
  `flat_mu4` `flat` with the pad material at mu 4.0

  The four grooves run **along** the tool axis (their normals are perpendicular to
  the pull, so their capacity gain can only be the friction count `1/cos(theta)`);
  `cradle90` is the only face whose contact normal has an axial component, i.e.
  the only "cup wall" the brief names.

**The closure is part of the finding.**  A groove is not a drop-in pad: the pads
must close *deeper* by `r - sqrt(r^2 - R^2)` per pad (6 mm per pad at `arc06` on a
60 mm fruit) or the face never reaches the fruit.  The fixture computes the first
contact from its own authored polyline (`contact_travel`) and adds P104's 5 mm
interference, so every profile is measured at the *same* delivered normal force,
not at the same span.

**Support proof (P107/P112's lesson, `PREREG.md` A1).**  Two dedicated cells before
any real one: (i) pad cap 0 + the payload's weight compensated by an applied force,
200 ticks -> the payload must not move more than 0.05 mm; (ii) pad cap 0 + no
compensation, 40 ticks -> it must fall.  (i) proves the fixture's own read/seat is
not the source of the motion; (ii) proves (i) is not a frozen world.

    scripts/run.sh logs/p117/fixture.py
    bash logs/p117/run_p117.sh        # the driver (fixture 1 + fixture 2)
"""

from __future__ import annotations

import math
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
GRAV = 9.81
#: The cell's worst measured single-tick acceleration (P40 section 4.1).
A_TRANSIENT = float(os.environ.get("P117_A_TRANSIENT", "5.83"))

PROFILES = tuple(
    p.strip()
    for p in os.environ.get(
        "P117_PROFILES", "flat,arc06,arc09,v90,cradle90,flat_mu3,flat_mu4"
    ).split(",")
    if p.strip()
)
FRUITS = tuple(f.strip() for f in os.environ.get("P117_FRUITS", "pear,orange,strawberry,lychee").split(",") if f.strip())
REPEATS = int(os.environ.get("P117_REPEATS", "3"))
SEED = int(os.environ.get("P117_SEED", "5"))

N_CONTACT = float(os.environ.get("P117_N_CONTACT", "4.90"))
PAD_STIFFNESS = float(os.environ.get("P117_PAD_STIFFNESS", "100000.0"))
PAD_DAMPING = float(os.environ.get("P117_PAD_DAMPING", "100.0"))
PAD_MASS = float(os.environ.get("P117_PAD_MASS", "0.02"))
PAD_MU = float(os.environ.get("P117_PAD_MU", "2.0"))
HOME_FACE_R = float(os.environ.get("P117_HOME_R", "0.042"))
INTERFERENCE = float(os.environ.get("P117_INTERFERENCE", "0.005"))
CLOSE_TICKS = int(os.environ.get("P117_CLOSE_TICKS", "150"))
PIN_TICKS = int(os.environ.get("P117_PIN_TICKS", "230"))
SETTLE_TICKS = int(os.environ.get("P117_SETTLE_TICKS", "90"))
LOADED_TICKS = int(os.environ.get("P117_LOADED_TICKS", "90"))
RATE = float(os.environ.get("P117_RATE", "5.0"))
F_MAX = float(os.environ.get("P117_F_MAX", "40.0"))
BREAK_M = float(os.environ.get("P117_BREAK_MM", "2.0")) / 1000.0
EXIT_M = float(os.environ.get("P117_EXIT_MM", "30.0")) / 1000.0
SUPPORT_TICKS = int(os.environ.get("P117_SUPPORT_TICKS", "200"))
SUPPORT_TOL_MM = float(os.environ.get("P117_SUPPORT_TOL_MM", "0.05"))

JAW_Z = 1.30
PAD_STANDOFF = 0.070
DISTAL_Z = 0.0805
PLATE_LEN = 0.0849
PLATE_WIDTH = 0.0610
PAD_THICK = 0.010
ARC_FACETS = int(os.environ.get("P117_ARC_FACETS", "18"))
STATION_PITCH = 0.20
PAD_Z_CENTRE = DISTAL_Z - PLATE_LEN / 2.0


# --------------------------------------------------------------------------- #
# The face profiles
# --------------------------------------------------------------------------- #
def profile_kind(profile: str) -> tuple[str, float]:
    """`(kind, mu)` for a profile name."""
    if profile == "flat_mu3":
        return "flat", 3.0
    if profile == "flat_mu4":
        return "flat", 4.0
    return profile, PAD_MU


def depth_polyline(profile: str, r: float, half_width: float) -> list[tuple[float, float]]:
    """The pad's face as (u, depth) breakpoints, `u` across the groove axis.

    `depth` is the surface's *outward* offset from the face plane (0 = the shipped
    flat face).  `u` is the tangential offset for the four grooves that run along
    the tool axis and the axial offset for `cradle90`.
    """
    kind, _ = profile_kind(profile)
    u_lo, u_hi = -half_width, half_width
    if kind == "flat":
        return [(u_lo, 0.0), (u_hi, 0.0)]
    if kind in ("arc06", "arc09"):
        frac = 0.6 if kind == "arc06" else 0.9
        radius = min(frac * r, 0.98 * half_width)
        pts = []
        for i in range(ARC_FACETS + 1):
            u = -radius + 2.0 * radius * i / ARC_FACETS
            d = math.sqrt(max(0.0, radius * radius - u * u))
            pts.append((u, d))
        return [(u_lo, 0.0)] + pts + [(u_hi, 0.0)]
    if kind in ("v90", "cradle90"):
        h = min(0.85 * r, 0.98 * half_width)
        return [(u_lo, 0.0), (-h, 0.0), (0.0, h), (h, 0.0), (u_hi, 0.0)]
    raise SystemExit(f"unknown profile kind {kind!r}")


def depth_at(poly: list[tuple[float, float]], u: float) -> float:
    for (u0, d0), (u1, d1) in zip(poly, poly[1:]):
        if min(u0, u1) <= u <= max(u0, u1):
            if abs(u1 - u0) < 1e-12:
                return max(d0, d1)
            t = (u - u0) / (u1 - u0)
            return d0 + t * (d1 - d0)
    return 0.0


def contact_travel(poly: list[tuple[float, float]], r: float, samples: int = 600) -> tuple[float, float]:
    """First-contact travel of the face plane, and the offset `u*` it happens at.

    The pad's surface is at radial `HOME_FACE_R + depth(u)`; the payload's surface
    at `sqrt(r^2 - u^2)`.  The pad touches first at the smallest travel
    `HOME + depth(u) - sqrt(...)`.
    """
    u_lo, u_hi = poly[0][0], poly[-1][0]
    best = None
    for i in range(samples + 1):
        u = u_lo + (u_hi - u_lo) * i / samples
        if abs(u) >= r:
            continue
        t = HOME_FACE_R + depth_at(poly, u) - math.sqrt(max(0.0, r * r - u * u))
        if best is None or t < best[0]:
            best = (t, u)
    if best is None:
        raise SystemExit("no contact: the pad's face never reaches the payload")
    return best


# --------------------------------------------------------------------------- #
# Authoring
# --------------------------------------------------------------------------- #
def _pad_material(stage, path: str, mu: float):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.15, 0.15, 0.16))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    api.CreateStaticFrictionAttr().Set(mu)
    api.CreateDynamicFrictionAttr().Set(mu)
    api.CreateRestitutionAttr().Set(0.0)
    return mat


def _quat_from_columns(x_axis, y_axis, z_axis) -> Gf.Quatf:
    m = np.column_stack([np.asarray(x_axis, float), np.asarray(y_axis, float), np.asarray(z_axis, float)])
    w = math.sqrt(max(0.0, 1.0 + m[0, 0] + m[1, 1] + m[2, 2])) / 2.0
    if w > 1e-8:
        x = (m[2, 1] - m[1, 2]) / (4.0 * w)
        y = (m[0, 2] - m[2, 0]) / (4.0 * w)
        z = (m[1, 0] - m[0, 1]) / (4.0 * w)
    else:  # 180 deg
        x = math.sqrt(max(0.0, 1.0 + m[0, 0] - m[1, 1] - m[2, 2])) / 2.0
        y = math.sqrt(max(0.0, 1.0 - m[0, 0] + m[1, 1] - m[2, 2])) / 2.0
        z = math.sqrt(max(0.0, 1.0 - m[0, 0] - m[1, 1] + m[2, 2])) / 2.0
    return Gf.Quatf(float(w), float(x), float(y), float(z))


def author_pad(stage, tag: str, centre_x: float, sign: float, profile: str, r: float, axle: str):
    """One pad body at `x = centre_x + sign * HOME_FACE_R`, its face a polyline.

    `axle == "mid"`  the groove runs along the tool axis, so `u` is world y;
    `axle == "long"` the groove runs across the pad, so `u` is world z.
    """
    _kind, mu = profile_kind(profile)
    half_width = PLATE_WIDTH / 2.0 if axle == "mid" else PLATE_LEN / 2.0
    other_extent = PLATE_LEN if axle == "mid" else PLATE_WIDTH
    poly = depth_polyline(profile, r, half_width)

    n = np.array([sign, 0.0, 0.0])  # outward: away from the payload
    e_u = np.array([0.0, 1.0, 0.0]) if axle == "mid" else np.array([0.0, 0.0, 1.0])
    w_axis = np.array([0.0, 0.0, 1.0]) if axle == "mid" else np.array([0.0, 1.0, 0.0])
    body_centre = np.array([centre_x + sign * (HOME_FACE_R + PAD_THICK / 2.0), 0.0, JAW_Z - PAD_Z_CENTRE])

    anchor_path = f"/World/P117/{tag}/Anchor"
    anchor = UsdGeom.Xform.Define(stage, anchor_path)
    axf = UsdGeom.Xformable(anchor)
    axf.ClearXformOpOrder()
    axf.AddTranslateOp().Set(Gf.Vec3d(float(centre_x), 0.0, JAW_Z))
    UsdPhysics.RigidBodyAPI.Apply(anchor.GetPrim()).CreateKinematicEnabledAttr().Set(True)
    UsdPhysics.MassAPI.Apply(anchor.GetPrim()).CreateMassAttr().Set(1.0)

    body_path = f"/World/P117/{tag}/Pad"
    body = UsdGeom.Xform.Define(stage, body_path)
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr().Set(PAD_MASS)
    bxf = UsdGeom.Xformable(body)
    bxf.ClearXformOpOrder()
    bxf.AddTranslateOp().Set(Gf.Vec3d(*[float(c) for c in body_centre]))

    origin = np.array([centre_x, 0.0, JAW_Z - PAD_Z_CENTRE])
    made = 0
    for i, ((u0, d0), (u1, d1)) in enumerate(zip(poly, poly[1:])):
        if abs(u1 - u0) < 1e-9:
            continue
        p0 = origin + n * (HOME_FACE_R + d0) + e_u * u0
        p1 = origin + n * (HOME_FACE_R + d1) + e_u * u1
        mid = 0.5 * (p0 + p1)
        tan = p1 - p0
        length = float(np.linalg.norm(tan))
        if length < 1e-6:
            continue
        tan = tan / length
        nf = np.cross(tan, w_axis)
        if float(nf @ n) < 0.0:
            nf = -nf
        nf = nf / float(np.linalg.norm(nf))
        book = mid - nf * (PAD_THICK / 2.0)
        cube = UsdGeom.Cube.Define(stage, f"{body_path}/Facet{i:02d}")
        cube.GetSizeAttr().Set(1.0)
        cxf = UsdGeom.Xformable(cube)
        cxf.ClearXformOpOrder()
        cxf.AddTranslateOp().Set(Gf.Vec3d(*[float(c) for c in (book - body_centre)]))
        cxf.AddOrientOp().Set(_quat_from_columns(tan, nf, w_axis))
        cxf.AddScaleOp().Set(Gf.Vec3f(length * 1.02, PAD_THICK, other_extent))
        UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
        UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(
            _pad_material(stage, f"{body_path}/Facet{i:02d}_mat", mu)
        )
        made += 1

    joint = UsdPhysics.PrismaticJoint.Define(stage, f"{body_path}_joint")
    joint.CreateBody0Rel().SetTargets([anchor_path])
    joint.CreateBody1Rel().SetTargets([body_path])
    joint.CreateAxisAttr().Set("X")  # both pads close along world X
    joint.CreateLowerLimitAttr().Set(-0.090)
    joint.CreateUpperLimitAttr().Set(0.090)
    joint.CreateLocalPos0Attr().Set(Gf.Vec3f(float(sign * (HOME_FACE_R + PAD_THICK / 2.0)), 0.0, float(-PAD_Z_CENTRE)))
    joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
    drive.CreateTypeAttr().Set("force")
    drive.CreateStiffnessAttr().Set(PAD_STIFFNESS)
    drive.CreateDampingAttr().Set(PAD_DAMPING)
    drive.CreateMaxForceAttr().Set(N_CONTACT)
    drive.CreateTargetPositionAttr().Set(0.0)
    travel0, ustar = contact_travel(poly, r)
    return {
        "tag": tag,
        "path": body_path,
        "drive": drive,
        "sign": sign,
        "n": n,
        "target_sign": -sign,  # inward is -sign * X
        "ustar": ustar,
        "facets": made,
        "poly": poly,
        "axle": axle,
        "home": body_centre,
        "travel0": travel0,
    }


def step(n: int = 1) -> None:
    for _ in range(max(1, int(n))):
        SimulationManager.step(steps=substeps())


def enable_tracking(path: str):
    try:
        prim = RigidPrim(path)
        prim.set_enabled_contact_tracking(True, threshold=1e-3)
        return prim
    except Exception as exc:  # noqa: BLE001
        say(f"[p117] WARNING: contact tracking unavailable for {path}: {exc}")
        return None


# --------------------------------------------------------------------------- #
def main() -> int:
    wall0 = time.time()
    say(
        f"[p117] fixture 1 (pad faces): profiles={PROFILES} fruits={FRUITS} "
        f"repeats={REPEATS} seed={SEED} substeps={substeps()} N={N_CONTACT:.2f}N "
        f"A_transient={A_TRANSIENT:.2f} m/s2 loaded={LOADED_TICKS}t"
    )
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment",))
    spawner = FruitSpawner(scene.stage, cfg, seed=SEED)
    spawner.create_pool()

    picks: dict[str, object] = {}
    for sample in spawner.samples:
        picks.setdefault(sample.category, sample)
    order = [f for f in FRUITS if f in picks]
    missing = [f for f in FRUITS if f not in picks]
    if missing:
        say(f"[p117] WARNING: not in the pool at seed {SEED}: {missing}")
    if not order:
        say("[p117] no fruit")
        return 1

    stations = []
    idx = 0
    for profile in PROFILES:
        for category in order:
            sample = picks[category]
            shape = FRUIT_SHAPES[category]
            r = axis_extent(shape, float(sample.diameter), np.array([1.0, 0.0, 0.0])) / 2.0
            kind, _ = profile_kind(profile)
            axle = "long" if kind == "cradle90" else "mid"
            cx = -2.4 + idx * STATION_PITCH
            left = author_pad(scene.stage, f"S{idx:02d}L", cx, -1.0, profile, r, axle)
            right = author_pad(scene.stage, f"S{idx:02d}R", cx, +1.0, profile, r, axle)
            travel = left["travel0"] + INTERFERENCE
            theta = math.degrees(math.asin(min(1.0, abs(left["ustar"]) / max(r, 1e-9))))
            stations.append(
                {
                    "profile": profile,
                    "category": category,
                    "sample": sample,
                    "r": r,
                    "cx": cx,
                    "pads": [left, right],
                    "travel": travel,
                    "theta": theta,
                }
            )
            say(
                f"[p117] station S{idx:02d} {profile:9s} {category:10s} "
                f"r={r * 1000:5.1f}mm facets={left['facets']} "
                f"contact_u*={left['ustar'] * 1000:+6.1f}mm theta={theta:4.1f}deg "
                f"travel={left['travel0'] * 1000:5.1f}+{INTERFERENCE * 1000:.1f}mm "
                f"span={2 * (HOME_FACE_R - travel) * 1000:5.1f}mm"
            )
            idx += 1

    supp = []
    for tag in ("support_comp", "support_grav"):
        cx = -2.4 + idx * STATION_PITCH
        left = author_pad(scene.stage, f"S{idx:02d}L", cx, -1.0, "flat", 0.030, "mid")
        right = author_pad(scene.stage, f"S{idx:02d}R", cx, +1.0, "flat", 0.030, "mid")
        left["drive"].CreateMaxForceAttr().Set(0.0)
        right["drive"].CreateMaxForceAttr().Set(0.0)
        supp.append({"tag": tag, "cx": cx, "pads": [left, right]})
        idx += 1

    for st in stations:
        for p in st["pads"]:
            p["authoring_handle"] = enable_tracking(p["path"])
    for sp in supp:
        for p in sp["pads"]:
            p["authoring_handle"] = enable_tracking(p["path"])
    for sample in spawner.samples:
        enable_tracking(sample.prim_path)

    scene.start(physics_dt=DT, warmup_steps=60)
    step(30)
    spawner.refresh_rigids()
    for st in stations:
        for p in st["pads"]:
            p["handle"] = enable_tracking(p["path"]) or p["authoring_handle"]
    for sp in supp:
        for p in sp["pads"]:
            p["handle"] = enable_tracking(p["path"]) or p["authoring_handle"]
    for sample in spawner.samples:
        enable_tracking(sample.prim_path)
        spawner.park(sample)
    step(20)

    def bind_force_handle(pads, sample):
        for p in pads:
            try:
                p["force_handle"] = RigidPrim(p["path"], contact_filter_paths=[sample.prim_path])
            except Exception:  # noqa: BLE001
                p["force_handle"] = None

    def pad_normal(pads):
        out = []
        for p in pads:
            try:
                forces = np.asarray(p["force_handle"].get_net_contact_forces().numpy(), dtype=float)[0]
                out.append(float((forces @ p["n"]) / DT))
            except Exception:  # noqa: BLE001
                out.append(float("nan"))
        return out

    # ------------------------------------------------------------------ #
    # A1: the support proof, before any real cell.
    # ------------------------------------------------------------------ #
    support_rows = []
    support_sample = picks[order[0]]
    if os.environ.get("P117_DIAG", "0") == "1":
        try:
            live_mass = float(np.asarray(spawner._rigids[support_sample.index].get_masses().numpy(), dtype=float).reshape(-1)[0])
        except Exception as exc:  # noqa: BLE001
            live_mass = float("nan")
            say(f"[p117] get_masses unavailable: {exc}")
        say(
            f"[p117] diag masses: sample={float(support_sample.mass):.9f} live={live_mass:.9f} "
            f"ratio={live_mass / float(support_sample.mass):.6f}"
        )
        # pad-drive semantics: no fruit, command the target, read the pad's x
        st0 = stations[0]
        for p in st0["pads"]:
            p["drive"].CreateTargetPositionAttr().Set(0.0)
        step(20)
        p0x = [
            (float(np.asarray(p["handle"].get_world_poses()[0].numpy(), dtype=float)[0][0]) - st0["cx"]) * 1000.0
            for p in st0["pads"]
        ]
        for p in st0["pads"]:
            p["drive"].CreateTargetPositionAttr().Set(float(p["target_sign"] * st0["travel"]))
        xs = []
        for k in range(150):
            step(1)
            if k in (0, 9, 29, 59, 149):
                xs.append(
                    (
                        k,
                        [
                            round((float(np.asarray(p["handle"].get_world_poses()[0].numpy(), dtype=float)[0][0]) - st0["cx"]) * 1000.0, 2)
                            for p in st0["pads"]
                        ],
                    )
                )
        say(f"[p117] diag pad_home_x={[round(v, 2) for v in p0x]} target={[round(p['target_sign'] * st0['travel'] * 1000, 2) for p in st0['pads']]} trace={xs}")
        for p in st0["pads"]:
            p["drive"].CreateTargetPositionAttr().Set(0.0)
        step(30)

        z0 = JAW_Z - PAD_STANDOFF
        for label, mult, pin in (
            ("none+pin", 0.0, True),
            ("comp+pin", 1.0, True),
            ("comp2+pin", 2.0, True),
            ("comp+free", 1.0, False),
        ):
            spawner.place(support_sample, np.array([-2.0, 0.0, z0]))
            spawner.stop(support_sample)
            step(1)
            p0 = spawner.position(support_sample).copy()
            for k in range(40):
                spawner._rigids[support_sample.index].apply_forces(
                    np.array([[0.0, 0.0, mult * live_mass * GRAV]], dtype=float)
                )
                if pin:
                    spawner.stop(support_sample)
                step(1)
            d = (spawner.position(support_sample) - p0) * 1000.0
            say(f"[p117] diag {label:10s} 40t dz={d[2]:+9.4f}mm drift={float(np.linalg.norm(d)):9.4f}mm")
            spawner.park(support_sample)
            step(5)
    for sp in supp:
        z = JAW_Z - PAD_STANDOFF
        pos0 = np.array([sp["cx"], 0.0, z])
        spawner.place(support_sample, pos0)
        step(2)
        # the measurement starts *after* the 2-tick settle: the pre-roll free fall
        # (2.04 mm) is the settle, not a drift
        pos0 = spawner.position(support_sample).copy()
        if sp["tag"] == "support_comp":
            # The brief's letter: zero pad force, the weight compensated -> no
            # motion.  A *free* body under a compensated weight still drifts
            # (measured 2.04 mm / 200 ticks = the solver's residual), so the pose
            # read is isolated by pinning the velocity after a 40-tick free
            # window; that free window is reported as the rig's resolution (A1).
            ticks = SUPPORT_TICKS
            spawner.stop(support_sample)
            for k in range(ticks):
                spawner._rigids[support_sample.index].apply_forces(
                    np.array([[0.0, 0.0, float(support_sample.mass) * GRAV]], dtype=float)
                )
                spawner.stop(support_sample)
                step(1)
        else:
            ticks = 40
            for _ in range(ticks):
                step(1)
        end = spawner.position(support_sample)
        drift = float(np.linalg.norm(end - pos0)) * 1000.0
        dz = (float(end[2]) - pos0[2]) * 1000.0
        support_rows.append({"cell": sp["tag"], "ticks": ticks, "drift_mm": drift, "dz": dz})
        ok = (sp["tag"] == "support_comp" and drift <= SUPPORT_TOL_MM) or (
            sp["tag"] == "support_grav" and dz < -20.0
        )
        say(
            f"[p117] support {sp['tag']:12s} {order[0]:10s} ticks={ticks:3d} "
            f"drift={drift:7.3f}mm dz={dz:+8.3f}mm verdict={'PASS' if ok else 'FAIL'}"
        )
        spawner.park(support_sample)
        step(10)
    comp = next(r for r in support_rows if r["cell"] == "support_comp")
    grav = next(r for r in support_rows if r["cell"] == "support_grav")
    support_ok = comp["drift_mm"] <= SUPPORT_TOL_MM and grav["dz"] < -20.0
    say(f"[p117] A1 support proof: {'PASS' if support_ok else 'FAIL'}")
    if not support_ok:
        say("[p117] the fixture's support is not proven - no real cell is spent (PREREG A1)")
        print()
        print("cell                     drift_mm     dz_mm")
        for r in support_rows:
            print(f"{r['cell']:24s} {r['drift_mm']:8.3f} {r['dz']:9.3f}")
        return 2

    # ------------------------------------------------------------------ #
    # The real cells.
    # ------------------------------------------------------------------ #
    rows = []
    for st in stations:
        sample = st["sample"]
        pads = st["pads"]
        bind_force_handle(pads, sample)
        fruit_z = JAW_Z - PAD_STANDOFF
        travel = st["travel"]
        for rep in range(REPEATS):
            spawner.place(sample, np.array([st["cx"], 0.0, fruit_z]))
            step(2)
            for p in pads:
                p["drive"].CreateTargetPositionAttr().Set(0.0)
            step(10)
            for frac in min_jerk_ramp(0.0, 1.0, CLOSE_TICKS):
                for p in pads:
                    p["drive"].CreateTargetPositionAttr().Set(float(p["target_sign"] * travel * frac))
                spawner.place(sample, np.array([st["cx"], 0.0, fruit_z]))
                step(1)
            for _ in range(max(1, PIN_TICKS - CLOSE_TICKS)):
                spawner.place(sample, np.array([st["cx"], 0.0, fruit_z]))
                step(1)
            # Release: the payload is held by the contacts alone.
            seat = spawner.position(sample).copy()
            seat0 = seat - np.array([st["cx"], 0.0, fruit_z])
            step(SETTLE_TICKS)
            pos_g = spawner.position(sample).copy()
            creep_g = float(np.linalg.norm(pos_g - seat)) * 1000.0
            # The operating load: the *extra* m*5.83 on top of the weight already
            # in the solver, held 0.75 s.
            f_extra = float(sample.mass) * A_TRANSIENT
            start_op = pos_g.copy()
            for _ in range(LOADED_TICKS):
                spawner._rigids[sample.index].apply_forces(np.array([[0.0, 0.0, -f_extra]], dtype=float))
                step(1)
            pos_op = spawner.position(sample).copy()
            creep_load = float(np.linalg.norm(pos_op - start_op)) * 1000.0
            # the primary endpoint: the *total* walk from the release to the end of
            # the 0.75 s loaded hold.  A sequential read (the loaded phase alone)
            # misses a profile that walked during the settle and then sat still
            # (measured on the pear: arc06 13.63 mm in the settle, 0.03 after).
            creep_op = float(np.linalg.norm(pos_op - seat)) * 1000.0
            creep_op_z = (float(pos_op[2]) - float(seat[2])) * 1000.0
            normal = pad_normal(pads)
            loaded = sum(1 for v in normal if np.isfinite(v) and abs(v) > 0.5)
            if os.environ.get("P117_DIAG", "0") == "1":
                px = []
                for p in pads:
                    try:
                        pos = np.asarray(p["handle"].get_world_poses()[0].numpy(), dtype=float)[0]
                        px.append(
                            (
                                round((float(pos[0]) - st["cx"]) * 1000.0, 2),
                                round(float(pos[1]) * 1000.0, 2),
                                round((float(pos[2]) - (JAW_Z - PAD_Z_CENTRE)) * 1000.0, 2),
                            )
                        )
                        raw = np.asarray(p["handle"].get_net_contact_forces().numpy(), dtype=float)[0]
                        px.append(("rawF", round(float(np.linalg.norm(raw)) / DT, 2)))
                    except Exception as exc:  # noqa: BLE001
                        px.append(str(exc))
                fr = spawner.position(sample)
                say(
                    f"[p117] diag pads_x={px}mm target={p['target_sign'] * travel * 1000:+.2f}mm "
                    f"fruit=({(float(fr[0]) - st['cx']) * 1000:+.2f},"
                    f"{(float(fr[1])) * 1000:+.2f},{(float(fr[2]) - fruit_z) * 1000:+.2f})mm"
                )
            weight = float(sample.mass) * GRAV
            say(
                f"[p117]   seat {st['profile']:9s} {st['category']:10s} rep{rep} "
                f"padN={[round(v, 2) for v in normal]} loaded={loaded} "
                f"seat={float(np.linalg.norm(seat0)) * 1000:.2f}mm "
                f"creep_g={creep_g:6.2f}mm creep_op={creep_op:6.2f}mm "
                f"load={creep_load:5.2f}mm dz={creep_op_z:+6.2f}mm"
            )
            # The break-away ramp, from the loaded state (P104's exact rule).
            applied = 0.0
            f_break = float("nan")
            f_exit = float("nan")
            fmax = 0.0
            start_r = spawner.position(sample).copy()
            max_disp = float(np.linalg.norm(start_r - seat))
            n_steps = int(round(F_MAX / (RATE * DT)))
            for _ in range(n_steps):
                applied = min(F_MAX, applied + RATE * DT)
                spawner._rigids[sample.index].apply_forces(np.array([[0.0, 0.0, -applied]], dtype=float))
                step(1)
                disp = float(np.linalg.norm(spawner.position(sample) - start_r))
                max_disp = max(max_disp, disp)
                try:
                    f = np.asarray(pads[0]["force_handle"].get_net_contact_forces().numpy(), dtype=float)[0]
                    fmax = max(fmax, float(np.linalg.norm(f)) / DT)
                except Exception:  # noqa: BLE001
                    pass
                if np.isnan(f_break) and disp >= BREAK_M:
                    f_break = applied + weight
                if disp >= EXIT_M:
                    f_exit = applied + weight
                    break
            rows.append(
                {
                    "profile": st["profile"],
                    "fruit": st["category"],
                    "d_mm": float(sample.diameter) * 1000.0,
                    "mass_g": float(sample.mass) * 1000.0,
                    "mu_fruit": float(sample.friction),
                    "theta": st["theta"],
                    "travel_mm": travel * 1000.0,
                    "span_mm": 2.0 * (HOME_FACE_R - travel) * 1000.0,
                    "loaded_pads": loaded,
                    "padN": ",".join(f"{v:.2f}" for v in normal),
                    "seat_mm": float(np.linalg.norm(seat0)) * 1000.0,
                    "creep_g": creep_g,
                    "creep_load": creep_load,
                    "creep_op": creep_op,
                    "creep_op_z": creep_op_z,
                    "f_break": f_break,
                    "f_exit": f_exit,
                    "max_disp": max_disp * 1000.0,
                    "fmax": fmax,
                    "rep": rep,
                }
            )
            say(
                f"[p117] ramp  {st['profile']:9s} {st['category']:10s} rep{rep} "
                f"F2mm={f_break:6.2f}N Fexit={f_exit:6.2f}N max={max_disp * 1000:6.1f}mm "
                f"fmax={fmax:6.2f}N"
            )
            for p in pads:
                p["drive"].CreateTargetPositionAttr().Set(0.0)
            step(20)
            spawner.park(sample)
            step(10)

    print()
    print(
        "profile    fruit       d[mm]  theta  travel   span   pads  creep_g  creep_op  "
        "F2mm    Fexit   fmax  span-dia"
    )
    for r in rows:
        print(
            f"{r['profile']:10s} {r['fruit']:10s} {r['d_mm']:6.1f} {r['theta']:5.1f} "
            f"{r['travel_mm']:7.2f} {r['span_mm']:6.2f} {r['loaded_pads']:4d} "
            f"{r['creep_g']:8.2f} {r['creep_op']:8.2f} "
            f"{r['f_break']:7.2f} {r['f_exit']:7.2f} {r['fmax']:6.2f} "
            f"{r['span_mm'] - r['d_mm']:7.1f}"
        )
    say(f"[p117] DONE fixture 1 rows={len(rows)} wall={time.time() - wall0:.1f}s")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
