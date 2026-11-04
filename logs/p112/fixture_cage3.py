#!/usr/bin/env python3
"""P112 fixture - does the **three-jaw** ring centre a payload? The closure alone.

**What this is.**  The phase's decisive test, and it costs one scene: a payload
from the shipped pool at a **known offset** from the ring's axis, resting on a
static table under gravity, and a ring of `n` pads closing on it at the task's
own clock.  No arm, no scheduler, no belt, no camera, no attempt machinery.  The
question is the algebra's: **does `off` fall below `off0`** - and to what.

**Why a fixture.**  P111 ran the ring on the line and could only report the
*net* effect of the aim, the descent, the catch-up, the carrier's motion, the
freeze and the carry.  Centring is a **closure** property: 5 offsets x 3 fruits x
2 hand kinds is 30 closures in one app session, and every one of them is a
controlled experiment (same fruit, same squeeze, one variable).

**The ring.**  The same authoring code path as `scene.build` authors
(`cage_hand.author_cage` is imported, not copied, so the fixture cannot drift
from the hand): `FRUIT_GRIPPER_KIND` selects `cage3` (3 x 120 deg, 20 mm plate)
or `cage4` (4 x 90 deg, 26 mm plate); the plates are the hand's 60 mm, the distal
plane 80.5 mm below the anchor and the pads' mid-plane 50.5 mm below it, so the
payload's centre sits 70.0 mm below the anchor - the hand's own `GRASP_STANDOFF`.

**The table.**  A static box whose top is 0.2 mm under the payload's lowest
point, with the same friction material as the pads (PhysX averages the pair, so
the table's pair with the fruit is the belt's own 1.25-1.46 - P104 section 2).

**Cells** (env, one app session per `(kind, hold)` pair; the driver loops):

  `P112_KIND`   `cage3` / `cage4`
  `P112_HOLD`   0 = no hard stop (the pure-soft closure) / 1e5 = P111's stop
  `P112_KS`     the stiffness ladder [N/m]  (default `330,1000,3300,10000`)
  `P112_OFFS`   the arrival offsets [mm]    (default `0,2,5,10,20`)
  `P112_FRUITS` how many pool classes       (default 3: smallest, mid, largest)
  `P112_FREEZE` 1 = the task's freeze rule (0.5 N for 3 ticks; the depth the
                carry holds), 0 = close to the full commanded depth
  `P112_TICKS`  the settle after the close (default 90)
  `P112_SEED`   the pool seed (default 5)

**Rows.**  `[p112] ring` (the authored geometry, once), `[p112] geo` (per fruit:
the extents along the pads, the law's width and the squeeze), and one
`[p112] cell` per closure with `off0`, `off_frz`, `off_end`, the pad count and
forces at the flush, the bat, `sep_min - dia` (the crush measure) and the class.

**What it cannot decide** (stated before the run): the arm, the descent, the
carry, the delivered rate.  It measures the **closure's** mechanics only - which
is exactly the clause the battery would otherwise confound with the aim.
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
from pxr import Gf, UsdGeom, UsdPhysics

from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting import cage_hand
from fruit_sorting.assets import SceneConfig
from fruit_sorting.cage_hand import (
    CAGE_PLATE_LENGTH, DISTAL_Z, GRASP_STANDOFF, HOME_FACE_R, PAD_MID_OFFSET,
    PAD_MASS, PAD_THICK, STROKE, author_cage, pad_paths, pad_thetas, pad_width_of,
)
from fruit_sorting.common import say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent
from fruit_sorting.motion import min_jerk_ramp
from fruit_sorting.scene import SortingScene

DT = 1.0 / 120.0
KIND = os.environ.get("P112_KIND", "cage3")
HOLD = float(os.environ.get("P112_HOLD", "0"))
KS = [float(v) for v in os.environ.get("P112_KS", "330,1000,3300,10000").split(",")]
OFFS = [float(v) / 1000.0 for v in os.environ.get("P112_OFFS", "0,2,5,10,20").split(",")]
NFRUIT = int(os.environ.get("P112_FRUITS", "3"))
FREEZE = os.environ.get("P112_FREEZE", "1") == "1"
SETTLE = int(os.environ.get("P112_TICKS", "90"))
SEED = int(os.environ.get("SEED", "5"))
CAP = float(os.environ.get("FRUIT_CAGE_PAD_FORCE", "4.90"))
SQUEEZE = 0.98
CONTACT_N = 0.5
CONTACT_TICKS = 3
FAST_TICKS, LOAD_TICKS = 24, 60
#: The ring's anchor: set per app session, because the payload rests on the
#: **shipped belt** (a proven collider: P110's fixture) and the hand's seat puts
#: the payload's centre `GRASP_STANDOFF` below the anchor - so a different fruit
#: radius is a different ring height, i.e. one fruit per session.
JAW_Z = 1.60
#: The ring's axis (the belt's centreline, x) - set in `main`, before any cell.
AXIS_X = 0.0
#: The belt's top z (the support plane) - set in `main`.
BELT_TOP = 1.17
#: The payload **lies on its side**, as it does on the belt: a 90 deg rotation
#: about x puts the fruit's own long axis horizontal, which is the case the
#: hand's aperture law has to answer (an upright fruit's horizontal cross-section
#: is a circle and every pad axis reads the same extent - measured `anisotropy`
#: 1.000 in the smoke run, `logs/p112/METHOD.md` section 2).
Q_SIDE = (math.cos(math.pi / 4.0), math.sin(math.pi / 4.0), 0.0, 0.0)


def offset_of(spawner, sample) -> float:
    """The payload's radial distance from the **ring's axis** (the belt line) [m]."""
    p = np.asarray(spawner.position(sample), dtype=float)
    return float(np.hypot(float(p[0]) - AXIS_X, float(p[1])))


def place_at(spawner, sample, position, quat) -> None:
    spawner._rigids[sample.index].set_world_poses(
        positions=[np.asarray(position, dtype=float).tolist()],
        orientations=[list(quat)],
    )
    spawner.stop(sample)


def _move_ring(stage, z: float) -> None:
    """Put the authored ring on the fixture's anchor, before `play()`.

    Two things have to move, and the second is the one that is easy to miss:

    * the whole ring goes from the authored park (the base at z = -3 m) to `z`;
    * the ring is **turned over**.  `cage_hand` authors its pads at **+z** in the
      base frame and the grasp at **-z**, because on the arm `_write_base`
      rotates the base so its +Z is the tool axis *down the fingers*
      (`_quat_from_z_to(arm.approach_axis())`).  A fixture with an identity base
      therefore has its pads 50.5 mm *above* the payload and reads **0.00 N on
      three pads that are 0.6 mm inside the fruit** (measured, `METHOD.md`
      section 2).  Rotating the ring's root by 180 deg about x restores the
      authored relationship under world gravity.

    The root is a bare Xform with no ops, so the transform is authored here as
    `translate . rotate` - the pads, their joints and the drive frames are all
    inside it and need no edit.
    """
    root = stage.GetPrimAtPath(cage_hand.cage_root("left"))
    xf = UsdGeom.Xformable(root)
    xf.ClearXformOpOrder()
    # USD composes the ops as `translate . rotate` (p -> R p + t), so the base's
    # authored z = -3 lands on `z` when t = z - 3 (measured: the other sign puts
    # the pads at 4.35 m, `METHOD.md` section 2).
    xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, z - 3.0))
    xf.AddOrientOp().Set(Gf.Quatf(0.0, 1.0, 0.0, 0.0))


def pad_u(theta: float) -> np.ndarray:
    """A pad's **world** radial direction (the ring is turned over, see `_move_ring`)."""
    th = math.radians(theta)
    return np.array([math.cos(th), -math.sin(th), 0.0])


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
        say(f"[p112] WARNING: no contact tracking for {path}: {exc}")
        return None


def main() -> int:
    wall0 = time.time()
    os.environ["FRUIT_GRIPPER_KIND"] = KIND
    kind = KIND
    thetas = pad_thetas(kind)
    width = pad_width_of(kind)
    say(
        f"[p112] ring kind={kind} pads={len(thetas)} at "
        f"{[round(t) for t in thetas]} deg, plate {width * 1000:.1f} x "
        f"{CAGE_PLATE_LENGTH * 1000:.1f} mm, cap {CAP:.2f} N/pad, "
        f"hold={'1e5 hard stop' if HOLD > 0 else 'none (pure soft)'}, "
        f"freeze={'task rule' if FREEZE else 'full close'}, settle={SETTLE} ticks"
    )

    cfg = SceneConfig()
    # **No support body at all**: the payload is made weightless (an anti-gravity
    # force is applied to it every tick), so the closure is the pure 2-D problem
    # the algebra models.  A bespoke static table, a kinematic one and the
    # shipped belt at 0 m/s were all tried first; each let a 0.1 kg payload sink
    # 2 mm and creep 4-5 mm laterally **with zero pad force** (`METHOD.md`
    # section 2), which is exactly the quantity the fixture has to resolve.  What
    # this drops is the table's own friction term (`mu_b m g` = 0.1-1.3 N against
    # a 5-15 N drive); it is stated, not hidden.
    scene = SortingScene(cfg).build(parts=("environment",))
    stage = scene.stage
    AXIS_X = 0.0


    # The ring, authored by the hand's own code path (`scene.build`'s call).
    author_cage(stage, "left")
    # ... and **moved to the fixture's anchor before `play()`**.  `author_cage`
    # parks the base at z = -3 m (the real driver re-seats it on the arm every
    # tick); here the ring is static, so the base and the three pad bodies are
    # written in USD before the physics view exists - a teleport *after* play
    # gives the pads the base's implied velocity and launches them (P107's
    # measured jump class, `logs/p107/m1_cage.txt`).
    spawner = FruitSpawner(stage, cfg, seed=SEED)
    spawner.create_pool()
    pads = [
        {"path": p, "theta": t}
        for p, t in zip(pad_paths("left"), thetas)
    ]

    for p in pads:
        enable_tracking(p["path"])
    for sample in spawner.samples:
        enable_tracking(sample.prim_path)
    scene.start(physics_dt=DT, warmup_steps=60)
    # Zero gravity: the closure is the 2-D problem the algebra models, and it
    # removes the support body the fixture could not make honest (see above).
    from pxr import UsdPhysics as _UP
    found = []
    for prim in stage.Traverse():
        if prim.GetTypeName() == "PhysicsScene" or prim.IsA(_UP.Scene):
            _UP.Scene(prim).CreateGravityMagnitudeAttr().Set(0.0)
            found.append(str(prim.GetPath()))
    say(f"[p112] gravity off on {found or 'NOTHING FOUND - the cells will fall'}")
    step(30)
    spawner.refresh_rigids()
    for p in pads:
        p["handle"] = enable_tracking(p["path"])
        p["drive"] = UsdPhysics.DriveAPI(
            stage.GetPrimAtPath(f"{p['path']}_joint"), "linear"
        )
    for sample in spawner.samples:
        enable_tracking(sample.prim_path)

    order = sorted(spawner.samples, key=lambda s: float(s.diameter))
    if NFRUIT >= len(order):
        picks = order
    else:
        idx = np.linspace(0, len(order) - 1, NFRUIT).round().astype(int)
        picks = [order[i] for i in dict.fromkeys(idx)]
    picks = [order[min(max(int(os.environ.get("P112_FRUIT", "-1")), 0), len(order) - 1)]]
    # The ring's anchor: the payload's centre sits `GRASP_STANDOFF` below it at
    # the belt's top, so a different fruit is a different ring height.
    JAW_Z = 1.60
    _move_ring(stage, JAW_Z)
    say(f"[p112] ring anchor z={JAW_Z:.4f} (payload centre "
        f"{GRASP_STANDOFF * 1000:.1f} mm below it); the payload is weightless")
    say(
        f"[p112] pool seed={SEED} {len(order)} fruits, cells on "
        f"{[f'{float(s.diameter) * 1000:.1f}' for s in picks]} mm"
    )

    rows = []
    for sample in picks:
        d = float(sample.diameter)
        shape = FRUIT_SHAPES[sample.category]
        fq = Q_SIDE
        rq = cage_hand._quat_matrix(fq)
        rot = np.eye(3)          # the ring is the world frame here
        ext = [float(axis_extent(shape, d, rq.T @ np.array(
            [math.cos(math.radians(t)), math.sin(math.radians(t)), 0.0]))) for t in thetas]
        law = min(ext) if len(thetas) == 3 else max(ext)
        squeeze = 0.5 * law * (1.0 - SQUEEZE)
        say(
            f"[p112] geo {sample.category:10s} d={d * 1000:.1f}mm m={float(sample.mass) * 1000:.1f}g "
            f"mu={float(sample.friction):.2f} ext={[round(v * 1000, 2) for v in ext]}mm "
            f"law={law * 1000:.2f}mm s={squeeze * 1000:.3f}mm "
            f"anisotropy={max(ext) / max(min(ext), 1e-9):.3f}"
        )
        for off in OFFS:
            for k in KS:
                rows.append(
                    run_cell(spawner, sample, pads, stage, kind, thetas, d, fq, ext,
                             law, squeeze, off, k, HOLD, FREEZE, SETTLE)
                )
            if HOLD <= 0.0:
                continue
            # one cell at the chosen stiffness to price the hard stop's effect
            rows.append(
                run_cell(spawner, sample, pads, stage, kind, thetas, d, fq, ext,
                         law, squeeze, off, 3300.0, HOLD, FREEZE, SETTLE)
            )
    deltas = [r["off_end"] - r["off0"] for r in rows]
    say(
        f"[p112] done {len(rows)} closures, "
        f"median(off-off0)={np.median(deltas) * 1000:+.2f} mm, "
        f"wall={time.time() - wall0:.1f}s"
    )
    return 0


def run_cell(spawner, sample, pads, stage, kind, thetas, d, fq, ext, law, squeeze,
             off, k, hold, freeze, settle) -> dict:
    """One closure: place at `off`, close at `k`, hold, read."""
    home = np.array([AXIS_X, 0.0, JAW_Z])
    centre_z = JAW_Z - GRASP_STANDOFF
    # the rest radius: the payload's own extent along the **vertical**, in the
    # lying pose it is placed in (a prolate fruit rests on its radial width)
    from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent
    shape = FRUIT_SHAPES[sample.category]
    rq = cage_hand._quat_matrix(fq)
    r_rest = 0.5 * float(axis_extent(shape, float(d), rq.T @ np.array([0.0, 0.0, 1.0])))
    for other in spawner.samples:
        spawner.park(other)
    place_at(spawner, sample, np.array([AXIS_X + off, 0.0, centre_z]), fq)
    # the pads go wide open, then the ramp starts from rest
    for p in pads:
        # The force view must be **filtered to this payload**: an unfiltered
        # `get_net_contact_forces()` on a body whose contacts are tracked reads
        # zero here (measured: 0.00 N on three pads that were 0.6 mm inside the
        # fruit, `logs/p112/METHOD.md` section 2).
        try:
            p["force"] = RigidPrim(p["path"], contact_filter_paths=[sample.prim_path])
        except Exception:  # noqa: BLE001
            p["force"] = p["handle"]
        p["drive"].CreateTargetPositionAttr().Set(0.0)
        p["drive"].CreateStiffnessAttr().Set(k)
        p["drive"].CreateDampingAttr().Set(2.0 * math.sqrt(k * PAD_MASS))
        p["drive"].CreateMaxForceAttr().Set(CAP)
    for _ in range(2):
        step(1)
        if os.environ.get("P112_DEBUG2", "0") == "1":
            pos = np.asarray(spawner.position(sample), dtype=float)
            vel = np.asarray(spawner.velocity(sample), dtype=float)
            say(f"[p112] set z={pos[2] * 1000:8.2f} x={pos[0] * 1000:+6.2f} "
                f"v={np.round(vel, 5)}")
        if float(np.linalg.norm(np.asarray(spawner.velocity(sample), dtype=float))) < 5.0e-4:
            break
    place_at(spawner, sample, np.array([AXIS_X + off, 0.0, centre_z]), fq)
    step(2)
    off0 = offset_of(spawner, sample)
    start = np.asarray(spawner.position(sample), dtype=float).copy()
    ramp = list(min_jerk_ramp(2.0 * HOME_FACE_R, law * 1.02, FAST_TICKS)) + list(
        min_jerk_ramp(law * 1.02, law * SQUEEZE, LOAD_TICKS)
    )
    run, froze, frz_off, frz_aperture = 0, False, float("nan"), float("nan")
    _trace = [0]
    for aperture in ramp:
        travel = float(np.clip(HOME_FACE_R - aperture / 2.0, 0.0, STROKE))
        for p in pads:
            p["drive"].CreateTargetPositionAttr().Set(travel)
        step(1)
        fn = []
        for p in pads:
            try:
                f = np.asarray(p["force"].get_net_contact_forces().numpy(), dtype=float)[0]
                fn.append(float((f @ pad_u(p["theta"])) / DT))
            except Exception:  # noqa: BLE001
                fn.append(0.0)
        if os.environ.get("P112_TRACE", "0") == "1" and _trace[0] % 3 == 0:
            pos = np.asarray(spawner.position(sample), dtype=float)
            say(f"[p112] trc t={_trace[0]:3d} aper={aperture * 1000:6.2f} "
                f"d=({pos[0] * 1000:+6.2f},{pos[1] * 1000:+6.2f},{pos[2] * 1000:+7.2f}) "
                f"f={[round(v, 2) for v in fn]}")
        _trace[0] += 1
        if freeze:
            run = run + 1 if max(fn) >= CONTACT_N else 0
            if run >= CONTACT_TICKS and not froze:
                froze = True
                frz_aperture = aperture
                frz_off = offset_of(spawner, sample)
                break
    if hold > 0.0:
        for p in pads:
            p["drive"].CreateStiffnessAttr().Set(hold)
            p["drive"].CreateDampingAttr().Set(2.0 * math.sqrt(hold * PAD_MASS))
    step(settle)
    if os.environ.get("P112_DEBUG", "0") == "1":
        fpos = np.asarray(spawner.position(sample), dtype=float)
        for p in pads:
            pp = np.asarray(p["handle"].get_world_poses()[0].numpy(), dtype=float)[0]
            raw = np.asarray(p["force"].get_net_contact_forces().numpy(), dtype=float)[0]
            say(f"[p112] dbg pad{p['theta']:5.0f} pos=({pp[0]*1000:+7.2f},{pp[1]*1000:+7.2f},"
                f"{pp[2]*1000:+8.2f})mm raw={np.round(raw,5)}")
        say(f"[p112] dbg fruit pos=({fpos[0]*1000:+.2f},{fpos[1]*1000:+.2f},{fpos[2]*1000:+.2f})mm "
            f"r_rest={r_rest*1000:.2f} table_top={table_top*1000:.2f}")
    off_end = offset_of(spawner, sample)
    end = np.asarray(spawner.position(sample), dtype=float)
    fn_end = []
    for p in pads:
        try:
            f = np.asarray(p["force"].get_net_contact_forces().numpy(), dtype=float)[0]
            fn_end.append(float((f @ pad_u(p["theta"])) / DT))
        except Exception:  # noqa: BLE001
            fn_end.append(0.0)
    n_end = sum(1 for v in fn_end if v >= CONTACT_N)
    bat = float(np.linalg.norm(end - start))
    # The **measured** aperture: the inscribed diameter `2 * mean face radius`,
    # read off the pad bodies (not the command), so a pad the payload pushed out
    # shows up - `sep - dia` is the crush measure the battery gates on.
    radii = []
    for p in pads:
        try:
            pos = np.asarray(p["handle"].get_world_poses()[0].numpy(), dtype=float)[0]
            radii.append(float((pos - home) @ pad_u(p["theta"])) - PAD_THICK / 2.0)
        except Exception:  # noqa: BLE001
            pass
    measured = 2.0 * float(np.mean(radii)) if radii else float("nan")
    rows = dict(
        kind=kind, k=k, hold=hold, freeze=freeze, fruit=sample.category,
        d=d, off0=off0, off_frz=frz_off, off_end=off_end,
        pads=n_end, f=",".join(f"{v:.2f}" for v in fn_end),
        fmax=float(np.max(fn_end)) if fn_end else 0.0,
        bat=bat, caught=froze,
        aperture=measured,
        cmd_aperture=frz_aperture if froze else float(ramp[-1]),
        s=squeeze,
        face=",".join(f"{v * 1000:.2f}" for v in radii),
        pen=",".join(
            f"{(r - 0.5 * (frz_aperture if froze else float(ramp[-1]))) * 1000:+.2f}"
            for r, f in zip(radii, fn_end)
        ),
        pen_max=float(max(
            (r - 0.5 * (frz_aperture if froze else float(ramp[-1])))
            for r, f in zip(radii, fn_end) if f >= CONTACT_N
        )) if any(v >= CONTACT_N for v in fn_end) else float("nan"),
        sep_minus_dia=measured - d,
    )
    say(
        f"[p112] cell kind={rows['kind']} k={k:7.0f} hold={hold:6.0f} "
        f"freeze={int(freeze)} {sample.category:8s} d={d * 1000:5.1f} "
        f"off0={off0 * 1000:6.2f} off_frz={rows['off_frz'] * 1000:6.2f} "
        f"off_end={off_end * 1000:6.2f} d_off={(off_end - off0) * 1000:+6.2f} "
        f"pads={n_end}/{len(pads)} fmax={rows['fmax']:5.2f}N bat={bat * 1000:6.2f} "
        f"aper={rows['aperture'] * 1000:6.2f} (cmd {rows['cmd_aperture'] * 1000:6.2f}) "
        f"sep-dia={rows['sep_minus_dia'] * 1000:+6.2f} dz={(end[2] - start[2]) * 1000:+5.2f}"
    )
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
