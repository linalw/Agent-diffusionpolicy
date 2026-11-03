#!/usr/bin/env python3
"""P110 fixture - the metering gate's physics, on the real belt and the real pool.

**What this is.**  A static/kinematic kerb across the belt at the pick station
(the "metering gate" of the brief: a fixed element that holds the fruit's
along-belt position while the belt slips under it, the belt never stopping), and
one fruit from the **shipped pool** carried into it at the shipped 0.12 m/s.
No arm, no scheduler, no attempt machinery, no camera - one scene, one gate, the
pool's own meshes, masses and friction draws (`fruits.FruitSpawner`), and the
shipped belt (`conveyor.CleatedBelt`, kinematic body + `PhysxSurfaceVelocityAPI`).

**Why a fixture.**  The gate's geometry is over-constrained before it is built:
the hand's lowest solid part at the grip is `jaw - 0.0805 m` = **14.5 mm** above
the belt (`tasks.FINGER_TIP_BELOW_JAW`), so a gate at the station is at most
~14.5 mm tall, and the pool spans **36-70 mm** of fruit.  Whether a 14.5 mm kerb
holds a 70 mm sphere at 0.12 m/s - or the fruit rides up and over it - is the
one clause (`K4`) a measurement can still overturn, and it is a contact question
with no honest arithmetic answer (the quasi-static climb condition
`(r - h)/r <= mu` holds for the pool, 0.19-0.59 <= 1.3, but the impact and the
belt slip are not in it).

**Cells** (env-driven, one gate height per app session; the driver loops):

  `P110_H`     gate height above the belt [mm]  (default 14.0)
  `P110_OFF`   station -> the gate's upstream face [mm] (default 20.0)
  `P110_MU`    the gate's friction (default 2.0 = the pad material; PhysX
               combines a pair by **average**, P104, so the pair reads ~1.65)
  `P110_N`     how many fruit the stream releases (default 1); the first is the
               row's subject, the rest are placed at the spawn line every
               `P110_GAP` metres of belt travel (the shipped mean gap) - i.e.
               the delivered cadence, not a pre-built pack (a pack of 8 does
               not fit: the gate's upstream side holds ~5 fruit)
  `P110_GAP`   the stream's spacing [m] (default 0.225 = the shipped mean)
  `P110_WAKE`  1 = call `spawner.enforce_transport` every tick exactly as the
               shipped line does; 0 = only the belt's own `step` (isolates the
               line's own wake/nudge rule, which forces `-0.048 m/s` on any
               fruit below 0.02 m/s - see `fruits.enforce_transport`)
  `P110_TICKS` the run's length per trial (default 600 = 5 s)
  `P110_SEED`  the pool's seed (default 5)

**Rows.**  One `[p110] gate ...` build row, one `[p110] parked ...` row per
fruit (the parked along-position, the climb, the gate's force on that fruit, the
belt slip, whether it escaped), and one `[p110] queue ...` row for `P110_N > 1`.

**What it cannot decide** (stated before the run): the arm, the enclosure, the
selection, the cadence's *delivered* side.  It measures the gate's contact
mechanics only - the drag, the hold height, the crush, the queue's load and the
state the release would start from.

    P110_H=14 scripts/run.sh logs/p110/fixture_gate.py
    bash logs/p110/run_p110.sh            # the driver: heights x queue
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
from pxr import Gf, UsdGeom, UsdPhysics

from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene, _add_physics_material, _define_box, _set_color

DT = 1.0 / 120.0
H = float(os.environ.get("P110_H", "14.0")) / 1000.0      # gate height [m]
OFF = float(os.environ.get("P110_OFF", "20.0")) / 1000.0  # station -> face [m]
MU = float(os.environ.get("P110_MU", "2.0"))
NQ = int(os.environ.get("P110_N", "1"))
GAP = float(os.environ.get("P110_GAP", "0.225"))
WAKE = os.environ.get("P110_WAKE", "1") == "1"
TICKS = int(os.environ.get("P110_TICKS", "900"))
SEED = int(os.environ.get("SEED", "5"))
THICK = 0.012
GATE_PATH = "/World/P110/StationGate"


def author_gate(cfg: SceneConfig) -> str:
    """A kerb across the belt, `OFF` upstream-face -> station, `H` tall."""
    bx, _, _ = (float(v) for v in cfg.belt_center)
    sx = float(cfg.belt_size[0])
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    face_y = float(cfg.pick_y) - OFF
    centre_y = face_y - THICK / 2.0  # the *upstream* face is at `face_y`
    prim = _define_box(
        _stage(),
        GATE_PATH,
        size=(sx, THICK, H),
        center=(bx, centre_y, belt_top + H / 2.0),
    )
    _set_color(prim, (0.72, 0.45, 0.10))
    UsdPhysics.CollisionAPI.Apply(prim.GetPrim())
    # A kinematic body (not a static collider) so its contacts can be *read*:
    # the force the belt drags the fruit into the gate with is the whole point.
    body = UsdPhysics.RigidBodyAPI.Apply(prim.GetPrim())
    body.CreateKinematicEnabledAttr().Set(True)
    UsdPhysics.MassAPI.Apply(prim.GetPrim()).CreateMassAttr().Set(2.0)
    # The gate's own friction, authored deliberately: the pair with the fruit's
    # draw is the *average* in this PhysX (P104 section 2), so mu 2.0 pairs to
    # ~1.65 against the fruit's 1.26-1.41.
    _add_physics_material(prim.GetPrim(), MU, MU, 0.0)
    say(
        f"[p110] gate: height={H * 1000:.1f} mm, thickness={THICK * 1000:.0f} mm, "
        f"upstream face y={face_y:+.4f} (station {cfg.pick_y:+.4f} - {OFF * 1000:.1f} mm), "
        f"x span={sx:.3f} m, mu={MU:.2f} (pair ~{(MU + 1.33) / 2:.2f}), "
        f"top z={belt_top + H:.4f} (belt top {belt_top:.4f}), "
        f"hand clearance {'OK' if H <= 0.0145 else 'COLLIDES with the pads (14.5 mm)'}"
    )
    return GATE_PATH


_STAGE = None


def _stage():
    return _STAGE


def main() -> int:
    global _STAGE
    wall0 = time.time()
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "conveyor"))
    _STAGE = scene.stage
    gate_path = author_gate(cfg)
    scene.start(physics_dt=DT, warmup_steps=60)
    SimulationManager.step(steps=1)
    app_utils.update_app(steps=0)

    gate = RigidPrim(gate_path)
    try:
        gate.set_enabled_contact_tracking(True, threshold=1e-3)
    except Exception as exc:  # noqa: BLE001
        say(f"[p110] WARNING: gate contact tracking unavailable: {exc}")

    spawner = FruitSpawner(scene.stage, cfg, seed=SEED)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    belt_x = float(cfg.belt_center[0])
    say(
        f"[p110] belt: commanded {cfg.belt_speed:+.3f} m/s, top z={belt_top:.4f}, "
        f"pool={len(spawner.samples)} seed={SEED} wake={int(WAKE)} queue={NQ} "
        f"ticks={TICKS}"
    )

    # Every fruit in the pool, one at a time - the radius sweep is the cell.
    order = sorted(spawner.samples, key=lambda s: float(s.diameter))
    rows = []
    for sample in order:
        r = float(sample.diameter) / 2.0
        # Park everything, then place the trial's fruit at the spawn line with
        # `NQ - 1` companions 0.15 m behind it (front-first = furthest downstream).
        for other in spawner.samples:
            spawner.park(other)
        stream = [sample]
        for other in order:
            if other is sample or len(stream) >= max(1, NQ):
                continue
            stream.append(other)
        for s in stream:
            spawner.park(s)
        rr = float(sample.diameter) / 2.0
        spawner.place(sample, np.array([belt_x, cfg.spawn_y, belt_top + rr + 0.0015]))
        # The rest are released at the delivered cadence: one per `GAP` of belt
        # travel (`GAP / speed` seconds), from the spawn line.
        release_every = max(1, int(round(GAP / max(abs(float(cfg.belt_speed)), 1e-6) / DT)))
        next_release = 1
        SimulationManager.step(steps=1)
        app_utils.update_app(steps=0)

        force_handle = None
        try:
            force_handle = RigidPrim(gate_path, contact_filter_paths=[sample.prim_path])
        except Exception:  # noqa: BLE001
            pass

        peak_gate = 0.0
        parked_ticks = 0
        parked_at = None
        escaped = False
        enc0 = None
        enc1 = None
        z_free = None      # the fruit's height on the free belt (0.10 m upstream)
        z_parked = None    # its height once at the gate
        ys = []            # the parked along-positions, for the hold's tightness
        fs = []            # the gate's force while parked (the *steady* drag)
        z_peak = float(spawner.position(sample)[2])
        for tick in range(TICKS):
            if next_release < len(stream) and tick >= release_every * next_release:
                s2 = stream[next_release]
                spawner.place(
                    s2,
                    np.array(
                        [belt_x, cfg.spawn_y, belt_top + float(s2.diameter) / 2.0 + 0.0015]
                    ),
                )
                next_release += 1
            if WAKE:
                spawner.enforce_transport(DT)
            elif scene.belt is not None:
                scene.belt.step(DT)
            SimulationManager.step(steps=1)
            app_utils.update_app(steps=0)
            pos = np.asarray(spawner.position(sample), dtype=float)
            vel = np.asarray(spawner.velocity(sample), dtype=float)
            z_peak = max(z_peak, float(pos[2]))
            if force_handle is not None:
                try:
                    f = np.asarray(force_handle.get_net_contact_forces().numpy(), dtype=float)[0]
                    peak_gate = max(peak_gate, float(np.linalg.norm(f)) / DT)
                except Exception:  # noqa: BLE001
                    pass
            face_y = float(cfg.pick_y) - OFF
            # Only after the fruit has travelled (the first ticks are the settle).
            if tick > 90 and pos[1] < float(cfg.pick_y) + 0.06:
                if abs(float(vel[1])) < 0.012 and pos[1] > face_y - THICK - 0.004:
                    parked_ticks += 1
                    ys.append(float(pos[1]))
                    if force_handle is not None:
                        try:
                            f = np.asarray(
                                force_handle.get_net_contact_forces().numpy(), dtype=float
                            )[0]
                            fs.append(float(np.linalg.norm(f)) / DT)
                        except Exception:  # noqa: BLE001
                            pass
                    if parked_at is None:
                        parked_at = pos.copy()
                        z_parked = float(pos[2])
                        enc0 = float(getattr(scene.belt, "encoder_speed", 0.0))
                elif parked_at is not None and enc1 is None:
                    enc1 = float(getattr(scene.belt, "encoder_speed", 0.0))
            if z_free is None and pos[1] <= float(cfg.pick_y) + 0.10 + THICK:
                z_free = float(pos[2])
            if pos[1] < face_y - THICK - 0.05:
                escaped = True
                break
        end = np.asarray(spawner.position(sample), dtype=float)
        # The climb is measured against the fruit's own height on the free belt
        # (a mesh is not a sphere, so `belt_top + r` is not its resting z).
        climb = (
            (z_parked - z_free) * 1000.0
            if (z_parked is not None and z_free is not None)
            else float("nan")
        )
        span_y = (max(ys) - min(ys)) * 1000.0 if len(ys) > 2 else float("nan")
        row = {
            "cat": sample.category,
            "dia": float(sample.diameter) * 1000.0,
            "mass": float(sample.mass) * 1000.0,
            "mu": float(sample.friction),
            "y": float(end[1]),
            "y_park": float(parked_at[1]) if parked_at is not None else float("nan"),
            "climb": float(climb),
            "gate_F": float(peak_gate),
            "parked_ticks": int(parked_ticks),
            "escaped": bool(escaped),
            "belt": float(getattr(scene.belt, "encoder_speed", 0.0)),
            "y_span": float(span_y),
            "gate_steady": float(np.median(fs)) if len(fs) > 2 else float("nan"),
        }
        rows.append(row)
        say(
            f"[p110] parked {row['cat']:10s} d={row['dia']:5.1f}mm m={row['mass']:5.1f}g "
            f"mu={row['mu']:.2f} | y_end={row['y']:+.4f} y_park={row['y_park']:+.4f} "
            f"climb={row['climb']:+6.1f}mm y_span={row['y_span']:5.2f}mm gate_F={row['gate_F']:6.2f}N "
            f"gate_ss={row['gate_steady']:5.2f}N "
            f"parked={row['parked_ticks']:3d}t escaped={int(row['escaped'])} "
            f"belt={row['belt']:+.3f}"
        )
        # The queue's state at the end of the trial: how many of the stream's
        # fruit are upstream of the gate, and how tight the chain is.
        face_y = float(cfg.pick_y) - OFF
        behind = []
        for s2 in stream:
            if s2 is sample:
                continue
            q = np.asarray(spawner.position(s2), dtype=float)
            if float(q[1]) > face_y:
                behind.append(q.copy())
        behind.sort(key=lambda q: -q[1])
        if behind:
            gaps = [float(behind[i][1] - behind[i + 1][1]) for i in range(len(behind) - 1)]
            noise = (float(behind[0][1] - end[1]), float(np.min(gaps)) if gaps else float("nan"))
        else:
            noise = (float("nan"), float("nan"))
        if NQ > 1:
            say(
                f"[p110] queue {row['cat']:10s} d={row['dia']:5.1f}mm n_released="
                f"{next_release} behind_gate={len(behind)} "
                f"subject_y={end[1]:+.4f} behind_y={behind[0][1]:+.4f} "
                f"min_gap={noise[1] * 1000 if np.isfinite(noise[1]) else float('nan'):.1f}mm "
                f"y_span={row['y_span']:.2f}mm y_park={row['y_park']:+.4f} "
                f"gate_F={row['gate_F']:.2f}N"
            )
        for s in stream:
            spawner.park(s)

    if not rows:
        say("[p110] no rows")
        return 1
    held = [r for r in rows if not r["escaped"] and r["parked_ticks"] >= 20]
    climbed = [r for r in rows if r["climb"] > 3.0]
    say(
        f"[p110] summary h={H * 1000:.1f}mm n={len(rows)} held={len(held)} "
        f"climbed={len(climbed)} escaped={sum(1 for r in rows if r['escaped'])} "
        f"gate_F p50={np.median([r['gate_F'] for r in rows]):.2f}N "
        f"ss p50={np.nanmedian([r['gate_steady'] for r in rows]):.2f}N "
        f"max={max(r['gate_F'] for r in rows):.2f}N "
        f"climb p50={np.nanmedian([r['climb'] for r in rows]):+.1f}mm "
        f"hold_span p50={np.nanmedian([r['y_span'] for r in rows]):.2f}mm "
        f"max={np.nanmax([r['y_span'] for r in rows]):.2f}mm "
        f"y_park p50={np.nanmedian([r['y_park'] for r in rows]):+.4f} "
        f"wall={time.time() - wall0:.1f}s"
    )
    if NQ > 1:
        say(
            f"[p110] queue n={NQ}: stream gate_F max={max(r['gate_F'] for r in rows):.2f}N "
            f"hold_span p50={np.nanmedian([r['y_span'] for r in rows]):.2f}mm "
            f"max={np.nanmax([r['y_span'] for r in rows]):.2f}mm "
            f"escaped={sum(1 for r in rows if r['escaped'])}"
        )
    say("[p110] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
