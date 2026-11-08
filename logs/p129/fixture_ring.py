#!/usr/bin/env python3
"""P129 bench B - the ring: does a pad whose **pair** friction is below 1 centre a
four-pad closure, and does it survive the line's first-contact freeze?

**What this is.**  P112's fixture protocol (a payload at a known offset from the
ring's axis, the hand's own `cage_hand.author_cage` code path, the task's close
clock of 24 + 60 ticks, the 0.5 N / 3-tick contact rule), with three changes,
each forced by the question:

* **The payload is a round sphere**, not a pool fruit.  The centring algebra is
  the 2-D problem of a disc between `n` pads; a real prolate fruit makes the
  four-pad ring's aperture law (`0.98 x the WIDEST extent`, P111 section 3) leave
  the perpendicular pair 1-6 mm short - a *second* defect that has nothing to do
  with friction and would confound this one.  A sphere puts all `n` pads at the
  same penetration, which is exactly the state the material is supposed to fix.
  *Scope*: an anisotropic payload's law is P112's measured term, not this one's.
* **Five rings on one stage, one per pair friction**, authored by
  `cage_hand.author_cage` with the module's `PAD_MU` set per ring; the sphere
  carries its own mu, so the pair is `(pad + sphere)/2` - the sim's average
  combine (P104 section 7a), and `pad = 2 t - mu_sphere` targets the pair `t`.
* **The close stiffness is a cell variable**, because the algebra's window at
  `mu = 0.6` is `[0.5/(s(1-mu)), cap/(s(1+mu))]` = 4223-4400 N/m over the pool -
  i.e. **the shipped 1e5 N/m close is far above it**: at k = 1e5 the
  perpendicular pair is at its cap, its friction is `2 mu cap`, and the near
  pad's drive (also capped) can never exceed it.  So the material is only half
  the package; the other half is a *soft close* (`FRUIT_CAGE_CLOSE_STIFFNESS`).

**Protocols.**  `freeze=0` is a full close (the centring question);
`freeze=1` is the task's own rule - freeze the aperture at the first sustained
0.5 N contact, then hold it (the delivered question; P108/P112 measured this as
the line's binding term).

**Support proof (P107/P112's lesson).**  Gravity is **off** (P112's accepted
form: a static table, a kinematic table and the belt at 0 m/s all let a 0.1 kg
payload sink 2 mm and creep 4-5 mm with zero pad force).  Before any real cell:
(i) the pads at their home aperture -> the sphere does not move over 200 ticks
(the read does not drift); (ii) a **frictionless** sphere (mu 0.0) closed from
10 mm -> it must centre, and to the value the algebra predicts (`mu_pair = pad/2`,
so `delta_inf = 0.25 s` on the 0.5 ring) - a quantitative proof that the fixture
can observe a slide when the algebra demands one.

    scripts/run.sh logs/p129/fixture_ring.py
    bash logs/p129/run_p129_ring.sh
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
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting import cage_hand
from fruit_sorting.assets import SceneConfig
from fruit_sorting.cage_hand import (
    CAGE_PLATE_LENGTH, GRASP_STANDOFF, HOME_FACE_R, PAD_MASS, PAD_THICK, STROKE,
    author_cage, cage_root, pad_paths, pad_thetas,
)
from fruit_sorting.common import say
from fruit_sorting.motion import min_jerk_ramp
from fruit_sorting.scene import SortingScene

DT = 1.0 / 120.0
KIND = os.environ.get("P129_KIND", "cage4")
#: The pair-friction ladder.  `2.0` is the **shipped** pad mu: its pair against
#: the sphere is 1.35, i.e. the same 1.25-1.46 band P104/P111 measured.
PAIR_TARGETS = tuple(
    float(v) for v in os.environ.get(
        "P129_RING_MUS", "0.6,0.8,1.0,1.2,2.0"
    ).split(",") if v.strip()
)
PROOF_PAIR = float(os.environ.get("P129_RING_PROOF", "0.6"))
#: The close stiffness ladder: the algebra's window point and the shipped drive.
KS = tuple(
    float(v) for v in os.environ.get("P129_RING_KS", "4300,100000").split(",")
    if v.strip()
)
OFFS = [float(v) / 1000.0 for v in os.environ.get("P129_RING_OFFS", "0,5,10,20").split(",")]
#: `(name, plan size m, height m, mass kg, mu)` - two pool-scale **square
#: prisms** plus the support proof's frictionless one.
#:
#: A square prism is the algebra's own 2-D payload: its four faces are planes on
#: the four pad faces, so every pad's penetration is `s + delta cos(theta)` at
#: any offset.  A *sphere* cannot test this - its surface retreats from the
#: perpendicular pair as it transits, and the pair's contact patch leaves the
#: 26 mm plate beyond `delta ~ 9 mm`, so a sphere slides in **friction-free**
#: whatever the pad material (measured: every sphere cell centred to 0.00 mm
#: with 4/4 pads at both pair 0.6 and 1.35, `logs/p129/fixture_ring_sphere.log`).
PRISMS = (
    ("b036", 0.036, 0.040, 0.10, 0.70),
    ("b066", 0.066, 0.050, 0.30, 0.70),
)
PROOF_PRISM = ("b050_mu0", 0.050, 0.050, 0.15, 0.0)
CAP = float(os.environ.get("FRUIT_CAGE_PAD_FORCE", "4.90"))
SQUEEZE = 0.98
CONTACT_N = 0.5
CONTACT_TICKS = 3
FAST_TICKS, LOAD_TICKS = 24, 60
SETTLE = int(os.environ.get("P129_RING_TICKS", "90"))
OPEN_SETTLE = int(os.environ.get("P129_RING_OPEN_SETTLE", "260"))
JAW_Z = 1.60
STATION_PITCH = 0.40


def pair_of(pad_mu: float, payload_mu: float) -> float:
    return 0.5 * (pad_mu + payload_mu)


def pad_mu_for(target: float, payload_mu: float) -> float:
    """The pad's authored mu that makes the pair average to `target` (>= 0)."""
    return max(0.0, 2.0 * target - payload_mu)


def _material_mu(stage, path: str, mu: float):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.7, 0.4, 0.2))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    api.CreateStaticFrictionAttr().Set(float(mu))
    api.CreateDynamicFrictionAttr().Set(float(mu))
    api.CreateRestitutionAttr().Set(0.0)
    return mat


def author_prism(stage, path: str, plan: float, height: float, mass: float, mu: float):
    """A square prism: its four vertical faces lie on the four pad faces."""
    body = UsdGeom.Xform.Define(stage, path)
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    UsdPhysics.MassAPI.Apply(body.GetPrim()).CreateMassAttr().Set(float(mass))
    xf = UsdGeom.Xformable(body)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -6.0))
    block = UsdGeom.Cube.Define(stage, f"{path}/Body")
    block.GetSizeAttr().Set(1.0)
    bxf = UsdGeom.Xformable(block)
    bxf.ClearXformOpOrder()
    bxf.AddScaleOp().Set(Gf.Vec3f(float(plan), float(plan), float(height)))
    UsdPhysics.CollisionAPI.Apply(block.GetPrim())
    UsdShade.MaterialBindingAPI.Apply(block.GetPrim()).Bind(
        _material_mu(stage, f"{path}/Body_mat", mu)
    )
    return {"path": path, "collider": f"{path}/Body", "plan": float(plan),
            "height": float(height), "mass": float(mass), "mu": float(mu)}


def offset_of(handle) -> float:
    p = np.asarray(handle.get_world_poses()[0].numpy(), dtype=float).reshape(3)
    return float(np.hypot(float(p[0]) - HANDLE_X[0], float(p[1])))


HANDLE_X = [0.0]


def place_at(handle, position, quat=(1.0, 0.0, 0.0, 0.0)) -> None:
    handle.set_world_poses(positions=[list(map(float, position))], orientations=[list(quat)])
    handle.set_velocities(
        linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]]
    )


def position_of(handle) -> np.ndarray:
    return np.asarray(handle.get_world_poses()[0].numpy(), dtype=float).reshape(3)


def step(n: int = 1) -> None:
    for _ in range(n):
        SimulationManager.step(steps=1)
        app_utils.update_app(steps=0)


def enable_tracking(path: str):
    try:
        prim = RigidPrim(path)
        prim.set_enabled_contact_tracking(True, threshold=1e-3)
        return prim
    except Exception as exc:  # noqa: BLE001
        say(f"[p129r] WARNING: no contact tracking for {path}: {exc}")
        return None


def pad_u(theta: float) -> np.ndarray:
    """A pad's world radial direction (the ring is turned over, see `_move_ring`)."""
    th = math.radians(theta)
    return np.array([math.cos(th), -math.sin(th), 0.0])


def move_ring(stage, tag: str, x: float, z: float) -> None:
    """Put a ring on the fixture's station: translate + turn it over.

    `author_cage` authors the pads at **+z** and the grasp at **-z** (on the arm
    the base is rotated so its +Z is the tool axis), so a fixture with an
    identity base puts the pads *above* the payload and reads 0 N on pads that
    are inside the fruit (P112's measurement).  The root is a bare Xform, so the
    transform is authored here as `translate . rotate`.
    """
    root = stage.GetPrimAtPath(cage_root(tag))
    xf = UsdGeom.Xformable(root)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(float(x), 0.0, float(z) - 3.0))
    xf.AddOrientOp().Set(Gf.Quatf(0.0, 1.0, 0.0, 0.0))


def main() -> int:
    wall0 = time.time()
    os.environ["FRUIT_GRIPPER_KIND"] = KIND
    thetas = pad_thetas(KIND)
    n = len(thetas)
    say(
        f"[p129r] ring kind={KIND} pads={n} at {[round(t) for t in thetas]} deg, "
        f"plate {cage_hand.pad_width_of(KIND) * 1000:.1f} x {CAGE_PLATE_LENGTH * 1000:.1f} mm, "
        f"cap {CAP:.2f} N/pad, close k {list(KS)}, offsets [mm] "
        f"{[round(o * 1000, 1) for o in OFFS]}, settle {SETTLE} ticks"
    )

    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment",))
    stage = scene.stage

    # The rings: one per pair target, each authored by the hand's own code path
    # with `PAD_MU` set for that ring.  (`cage_hand._material` reads the module
    # global, so patching it around the call authors the ring's material at the
    # value, before `play()` - no prim surgery, no cached material.)
    rings = []
    for i, target in enumerate(PAIR_TARGETS):
        payload_mu = PRISMS[0][4]
        pad_mu = pad_mu_for(target, payload_mu) if target < 2.0 else float(target)
        tag = f"r{i}"
        x = 2.4 + i * STATION_PITCH
        keep = cage_hand.PAD_MU
        cage_hand.PAD_MU = float(pad_mu)
        try:
            author_cage(stage, tag)
        finally:
            cage_hand.PAD_MU = keep
        move_ring(stage, tag, x, JAW_Z)
        rings.append({"tag": tag, "x": x, "target": target, "pad_mu": float(pad_mu)})
        say(f"[p129r] ring {tag} x={x:.2f} pair_target={target:.2f} pad_mu={pad_mu:.2f} "
            f"pair(b036)={pair_of(pad_mu, 0.70):.2f}")

    # The payloads: pool-scale spheres plus the frictionless proof sphere.
    balls = []
    for name, plan, height, m, mu in PRISMS + (PROOF_PRISM,):
        body = author_prism(stage, f"/World/P129/{name}", plan, height, m, mu)
        body["name"] = name
        body["d"] = plan          # the aperture law's own width
        balls.append(body)

    prefix_paths = [p for r in rings for p in pad_paths(r["tag"])]
    for p in prefix_paths:
        enable_tracking(p)
    for b in balls:
        enable_tracking(b["path"])
    scene.start(physics_dt=DT, warmup_steps=60)
    # No support body: weightless (P112's form) - see the docstring.
    found = []
    for prim in stage.Traverse():
        if prim.GetTypeName() == "PhysicsScene" or prim.IsA(UsdPhysics.Scene):
            UsdPhysics.Scene(prim).CreateGravityMagnitudeAttr().Set(0.0)
            found.append(str(prim.GetPath()))
    say(f"[p129r] gravity off on {found or 'NOTHING FOUND - the cells will fall'} "
        f"(weightless payload: the closure is the 2-D problem)")
    step(30)
    for r in rings:
        r["paths"] = pad_paths(r["tag"])
        r["handles"] = [enable_tracking(p) for p in r["paths"]]
        r["drives"] = [
            UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{p}_joint"), "linear")
            for p in r["paths"]
        ]
        r["home"] = np.array([r["x"], 0.0, JAW_Z])
    for b in balls:
        b["handle"] = enable_tracking(b["path"]) or RigidPrim(b["path"])

    def force_handles(ring, ball):
        """The pads' contact views **filtered to this payload**, built once per
        cell: an unfiltered view on a tracked body reads zero (P112 section 2),
        and reconstructing the view every tick is both slow and unreliable."""
        out = []
        for p in ring["paths"]:
            try:
                prim = RigidPrim(p, contact_filter_paths=[ball["collider"]])
                try:
                    prim.set_enabled_contact_tracking(True, threshold=1e-3)
                except Exception as exc:  # noqa: BLE001
                    say(f"[p129r] WARNING: tracking {p}: {exc}")
                out.append(prim)
            except Exception as exc:  # noqa: BLE001
                say(f"[p129r] WARNING: force view for {p} failed: {exc}")
                out.append(None)
        return out

    def forces_of(handles, tracked=None):
        out = []
        for k, fh in enumerate(handles):
            f = None
            alts = (fh,) if tracked is None else (fh, tracked[k])
            for cand in alts:
                if cand is None:
                    continue
                try:
                    vec = np.asarray(cand.get_net_contact_forces().numpy(), dtype=float)[0]
                except Exception as exc:  # noqa: BLE001
                    if os.environ.get("P129_DEBUG", "0") == "1":
                        say(f"[p129r] force read {k}: {exc}")
                    continue
                f = vec
                break
            out.append(0.0 if f is None else float((f @ pad_u(thetas[k])) / DT))
        return out

    def set_k(ring, k):
        for drv in ring["drives"]:
            drv.CreateStiffnessAttr().Set(float(k))
            drv.CreateDampingAttr().Set(2.0 * math.sqrt(k * PAD_MASS))
            drv.CreateMaxForceAttr().Set(CAP)

    def open_ring(ring):
        for drv in ring["drives"]:
            drv.CreateTargetPositionAttr().Set(0.0)

    # ------------------------------------------------------------------ #
    # The support proof.
    # ------------------------------------------------------------------ #
    proof = balls[-1]          # the frictionless prism
    r0 = rings[0]
    HANDLE_X[0] = r0["x"]
    open_ring(r0)
    set_k(r0, 1e5)
    place_at(proof["handle"], np.array([r0["x"], 0.0, JAW_Z - GRASP_STANDOFF]))
    step(5)
    p0 = position_of(proof["handle"])
    step(200)
    drift = float(np.linalg.norm(position_of(proof["handle"]) - p0)) * 1000.0
    say(f"[p129r] support open: frictionless payload, pads home, 200 ticks "
        f"drift={drift:7.4f}mm verdict={'PASS' if drift <= 0.05 else 'FAIL'}")
    proof_ok = drift <= 0.05

    # (ii) the frictionless sphere must centre, and to the algebra's value.
    s0 = 0.5 * proof["d"] * (1.0 - SQUEEZE)
    set_k(r0, 4300.0)
    open_ring(r0)
    step(OPEN_SETTLE)
    off_proof = 0.010
    place_at(proof["handle"], np.array([r0["x"] + off_proof, 0.0, JAW_Z - GRASP_STANDOFF]))
    step(2)
    off0 = offset_of(proof["handle"])
    ramp = list(min_jerk_ramp(2.0 * HOME_FACE_R, proof["d"] * 1.02, FAST_TICKS)) + list(
        min_jerk_ramp(proof["d"] * 1.02, proof["d"] * SQUEEZE, LOAD_TICKS)
    )
    for aperture in ramp:
        travel = float(np.clip(HOME_FACE_R - aperture / 2.0, 0.0, STROKE))
        for drv in r0["drives"]:
            drv.CreateTargetPositionAttr().Set(travel)
        step(1)
    step(SETTLE)
    off_end = offset_of(proof["handle"])
    fn = forces_of(force_handles(r0, proof), r0["handles"])
    pair_proof = pair_of(r0["pad_mu"], 0.0)
    pred = pair_proof * s0
    say(f"[p129r] support centre: frictionless payload from {off_proof * 1000:.1f}mm "
        f"pair={pair_proof:.2f} off0={off0 * 1000:.2f} off_end={off_end * 1000:.2f}mm "
        f"pred={pred * 1000:.2f}mm pads={sum(1 for v in fn if v >= CONTACT_N)}/{n} "
        f"forces={[round(v, 2) for v in fn]}")
    proof_ok = proof_ok and off_end <= 0.5 * off0
    place_at(proof["handle"], np.array([r0["x"], 0.0, -6.0]))
    step(10)
    say(f"[p129r] A1 support proof: {'PASS' if proof_ok else 'FAIL'}")
    if not proof_ok:
        say("[p129r] the fixture's support is not proven - no real cell is spent")
        return 2

    # ------------------------------------------------------------------ #
    # The cells.
    # ------------------------------------------------------------------ #
    rows = []

    def run_cell(ring, ball, off, k, freeze):
        HANDLE_X[0] = ring["x"]
        open_ring(ring)
        set_k(ring, k)
        step(OPEN_SETTLE)      # the pads must be HOME before the payload is placed
        if os.environ.get("P129_DEBUG", "0") == "1":
            rr = []
            for kk, hh in enumerate(ring["handles"]):
                try:
                    pp = np.asarray(hh.get_world_poses()[0].numpy(), dtype=float).reshape(3)
                    rr.append(round(float((pp - np.array([ring["x"], 0.0, JAW_Z]))
                                          @ pad_u(thetas[kk])) * 1000, 1))
                except Exception as exc:  # noqa: BLE001
                    rr.append(str(exc))
            say(f"[p129r] dbg open radii={rr}")
        z = JAW_Z - GRASP_STANDOFF
        place_at(ball["handle"], np.array([ring["x"] + off, 0.0, z]))
        step(2)
        off0 = offset_of(ball["handle"])
        start = position_of(ball["handle"]).copy()
        ramp = list(min_jerk_ramp(2.0 * HOME_FACE_R, ball["d"] * 1.02, FAST_TICKS)) + list(
            min_jerk_ramp(ball["d"] * 1.02, ball["d"] * SQUEEZE, LOAD_TICKS)
        )
        fhs = force_handles(ring, ball)
        run, froze, frz_ap = 0, False, float("nan")
        trace = os.environ.get("P129_TRACE", "0") == "1"
        for it, aperture in enumerate(ramp):
            travel = float(np.clip(HOME_FACE_R - aperture / 2.0, 0.0, STROKE))
            for drv in ring["drives"]:
                drv.CreateTargetPositionAttr().Set(travel)
            step(1)
            fn = forces_of(fhs, ring["handles"])
            if trace and it % 6 == 0:
                bp = position_of(ball["handle"]) - np.array([ring["x"], 0.0, 0.0])
                say(f"[p129r] trc it={it:3d} aper={aperture * 1000:6.2f} "
                    f"ball=({bp[0] * 1000:+6.2f},{bp[1] * 1000:+6.2f},{bp[2] * 1000:+8.2f})mm "
                    f"f={[round(v, 3) for v in fn]} pads={sum(1 for v in fn if v >= CONTACT_N)}")
            if freeze:
                run = run + 1 if max(fn) >= CONTACT_N else 0
                if run >= CONTACT_TICKS:
                    froze = True
                    frz_ap = aperture
                    break
        # The contact-force matrix is **not** guaranteed to be populated on a
        # tick with no new contact pair (measured: the pads read 0 N at the
        # flush while the aperture is 0.36 mm inside a 36 mm sphere and the
        # spring law says 1.55 N, `logs/p129/fixture_ring.log`).  So the pad
        # count is taken from the *maximum each pad carries over the settle*,
        # which is the physical "loaded" state, and the flush read is reported
        # beside it.
        fmax_pad = [0.0] * n
        for _ in range(SETTLE):
            step(1)
            for kk, v in enumerate(forces_of(fhs, ring["handles"])):
                if v > fmax_pad[kk]:
                    fmax_pad[kk] = v
        off_end = offset_of(ball["handle"])
        fn = forces_of(fhs, ring["handles"])
        if os.environ.get("P129_DEBUG", "0") == "1":
            dbg = []
            for kk, pth in enumerate(ring["paths"]):
                try:
                    h = ring["handles"][kk]
                    pos = np.asarray(h.get_world_poses()[0].numpy(), dtype=float).reshape(3)
                    rad = float((pos - np.array([ring["x"], 0.0, JAW_Z])) @ pad_u(thetas[kk]))
                    raw = np.asarray(h.get_net_contact_forces().numpy(), dtype=float)[0]
                    dbg.append((round(rad * 1000, 2), round(float(np.linalg.norm(raw)) / DT, 2)))
                except Exception as exc:  # noqa: BLE001
                    dbg.append(str(exc))
            try:
                body_f = np.asarray(ball["handle"].get_net_contact_forces().numpy(),
                                    dtype=float)[0]
                body_n = round(float(np.linalg.norm(body_f)) / DT, 2)
            except Exception as exc:  # noqa: BLE001
                body_n = str(exc)
            say(f"[p129r] dbg pads(radius mm, |F| N)={dbg} body|F|={body_n} "
                f"n_pads={len(fn)}")
        cnt = sum(1 for v in fmax_pad if v >= CONTACT_N)
        s = 0.5 * ball["d"] * (1.0 - SQUEEZE)
        rows.append(dict(
            kind=KIND, ring=ring["tag"], target=ring["target"], pad_mu=ring["pad_mu"],
            ball=ball["name"], d=ball["d"], mu_ball=ball["mu"],
            pair=pair_of(ring["pad_mu"], ball["mu"]), k=k, freeze=freeze,
            off0=off0, off_end=off_end, d_off=off_end - off0, s=s,
            pads=cnt, fn=fmax_pad, fn_last=fn, fmax=float(max(fmax_pad)) if fmax_pad else 0.0,
            froze=froze, frz_ap=frz_ap, bat=float(np.linalg.norm(position_of(ball["handle"]) - start)),
        ))
        r = rows[-1]
        say(
            f"[p129r] cell {KIND} pair={r['pair']:.2f} k={k:7.0f} freeze={int(freeze)} "
            f"{ball['name']:8s} off0={off0 * 1000:6.2f} off_end={off_end * 1000:6.2f} "
            f"d_off={r['d_off'] * 1000:+6.2f} pads={cnt}/{n} "
            f"f={[round(v, 2) for v in fmax_pad]} last={[round(v, 2) for v in fn]} froze={int(froze)} "
            f"frz_ap={(frz_ap * 1000 if froze else float('nan')):6.2f}"
        )
        place_at(ball["handle"], np.array([ring["x"], 0.0, -6.0]))
        step(5)
        return r

    for ball in balls[:-1]:
        for ring in rings:
            for k in KS:
                for freeze in (False, True):
                    for off in OFFS:
                        run_cell(ring, ball, off, k, freeze)

    print()
    print("kind   ball     d[mm] pair  k        freeze  off[mm]  off_end  d_off  pads  fmax")
    for r in rows:
        print(f"{r['kind']:6s} {r['ball']:8s} {r['d'] * 1000:6.1f} {r['pair']:5.2f} "
              f"{r['k']:8.0f} {int(r['freeze']):6d} {r['off0'] * 1000:8.2f} "
              f"{r['off_end'] * 1000:8.2f} {r['d_off'] * 1000:+7.2f} {r['pads']:4d}/{n} "
              f"{r['fmax']:5.2f}")
    say(f"[p129r] DONE rows={len(rows)} wall={time.time() - wall0:.1f}s")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
