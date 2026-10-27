"""P50 phase 1: the per-instance release offset, measured one instance at a time.

    SEED=5 FRUIT_OFFSET_PASSES=2 scripts/154_claim_run.sh \
        logs/p50/p1/offset_probe_s5.log \
        scripts/run.sh logs/p50/p1/offset_probe.py

Reuses the skeleton of `logs/p38/probe_drift.py` (the shipped scene + spawner,
`raise_fd_limit`, the fixed-step pump `SimulationManager.step` +
`app_utils.update_app(steps=0)`, the `[drift]`-style `say` rows) and answers the
one question P38 left as a corollary:

    delivered x = spawn x + offset(instance)

so the offset can be measured once and applied at `respawn`
(`x_spawn = planned_x - offset(instance)`, P50's compensation).

**Why this is a different probe.** P38 measured the drift of whatever the
free-cadence feeder happened to release, so its `spawn x` was the seeded draw and
its rows could only be grouped by *class* (two instances per class, n = 7-16 per
class). This probe drives `FruitSpawner.respawn(sample, along=..., x=...)` - the
same entry point, and the very `x` override the patch schedule already uses - so
**one body at a time** is dropped at a commanded x, on an otherwise empty belt
(all other fruit parked). That gives, per pool instance:

* the offset at **3 commanded x values** (0.20 / 0.28 / 0.36 = the spawn band's
  floor, centre and ceiling), which is what decides whether the offset is
  x-independent (P38's claim) or needs an x term;
* a per-tick profile of the settle, so *when* the displacement happens is read
  rather than inferred (P38 saw no per-tick step > 2 mm because the whole
  displacement sits inside the first contact ticks);
* a second **pass** over the whole table in the same process (a same-seed,
  same-state repeat: the physics must reproduce), plus a dedicated 3-repeat
  block on one cell (the TASK-2 determinism read);
* a **ride check**: for the first `FRUIT_OFFSET_RIDE` instances the fruit is
  carried to the station edge after the settle, and the x is compared with the
  settle value (P38: the transport contributes exactly 0.000 mm).

`respawn` draws from `self.rng` only when `x`/`along` are `None`, so an explicit
`x` and `along` leave the pool's RNG stream untouched: pass A and pass B see
**identical instances**, which is what makes the repeat a determinism test
rather than a fresh draw.

Geometry read (no physics): the authored mesh's point cloud is read back from the
stage for every instance - the local `z` extent (is the commanded 30 mm bottom
clearance real for this hull?) and the lateral position of the lowest vertex
(does the hull's own asymmetry predict the offset?). The collider is the
`convexHull` of exactly these points (`meshes.author_fruit`), so if the offset
is a release-geometry property it should be visible here instead of only in the
settle.

Rows (`[offset] ...`):

    [offset] probe: seed= schedule= belt= speed= band= spawn_y= settle_ticks=
    [offset] row pass= idx= cat= dia_mm= grade= x_cmd= x1= x5= x10= x20= x40=
                     x80= x_settle= off_mm= max_step_mm= max_step_tick=
                     last_step_tick= dz_settle_mm=
    [offset] geom idx= cat= dia_mm= z_min_mm= x_at_zmin_mm= bottom_gap_mm=
                    centroid_x_mm= extent_x_mm=
    [offset] repeat idx= x= off_mm=          (the TASK-2 block)
    [offset] ride idx= x_cmd= x_settle= x_edge= drift_mm= ticks=
    [offset] instance idx= cat= dia_mm= x=... off_mm=... (the pooled per-cell median)
    [offset] summary: DONE

Nothing here is a control input: the probe reads fruit poses (the documented safe
read class) and runs no attempt. `FRUIT_SUPPLY_*` are honoured as usual, so the
same probe measures the pear pool (`FRUIT_SUPPLY_SPECIES=pear`) or a patch sheet.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.simulation_manager import SimulationManager
from pxr import UsdGeom
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile

install_failure_handler("p50_offset_probe")

DT = 1.0 / 120.0
#: The commanded (spawn) x values. The shipped scatter band is 0.20-0.36, so
#: these are its floor, centre and ceiling: the three points a linear x term
#: needs, and the two edges where a tail is created.
XS = tuple(float(v) for v in os.environ.get("FRUIT_OFFSET_XS", "0.20,0.28,0.36").split(","))
#: Ticks per spawn before the settle x is read. 420 = 3.5 s = 0.42 m of belt
#: travel: the release drop is 30 mm (~10 ticks to contact) but the *roll* a
#: lopsided hull converts that into is slow - at seed 77 a kiwi is still moving
#: at tick 137 (its x is flat by 160, and a 180-tick read and a 420-tick read of
#: the same cell agree to 0.01 mm), so 420 is ~3x margin. The per-tick profile
#: below proves it per cell (`last_step_tick`).
SETTLE = int(os.environ.get("FRUIT_OFFSET_SETTLE_TICKS", "420"))
#: Full passes over the 16 x |XS| table. Pass 1 is a same-seed, same-process
#: repeat: identical instances (no RNG draw on the probe path) and identical
#: physics, so any difference is the probe's own determinism.
PASSES = int(os.environ.get("FRUIT_OFFSET_PASSES", "2"))
#: The TASK-2 block: re-measure pool slot 0 at the middle x this many times.
REPEAT = int(os.environ.get("FRUIT_OFFSET_REPEAT", "3"))
#: How many instances (by pool index) get the ride check, and the along edge the
#: ride stops at (0.04 = just inside the pick station's upstream edge, P38's
#: `EDGES[-1]`).
RIDE = int(os.environ.get("FRUIT_OFFSET_RIDE", "3"))
RIDE_EDGE = float(os.environ.get("FRUIT_OFFSET_RIDE_EDGE", "0.04"))
RIDE_MAX = int(os.environ.get("FRUIT_OFFSET_RIDE_MAX", "1200"))
#: The ticks printed in the settle profile.
PROFILE_TICKS = (1, 5, 9, 10, 11, 12, 14, 16, 20, 30, 40, 60, 80, 120, 160)

#: `isolated` (default) = the per-instance table: one body at a time at a
#: commanded x. `live` = the shipped free-cadence feeder, i.e. P38's own
#: condition, but with the release **attributed**: `respawn` is wrapped so every
#: release records `(index, commanded x, tick)`, and each body's x is then
#: followed from its first tick to the station edge. P38's probe had to guess the
#: transit boundaries, which is why its per-class table loses the long rollers
#: (`x_first` restarts mid-roll and both halves read small); the wrapper removes
#: the guess. This mode is what decides whether the isolated offset is the
#: *delivered* offset in the running line.
MODE = os.environ.get("FRUIT_OFFSET_MODE", "isolated").strip().lower()

#: Run the feeder's own wake loop (`FruitSpawner.enforce_transport`) every tick
#: while the fruit settles. `0` (default) is the isolated release: no feeder call
#: at all, which is the state the belt is in **during an attempt** (the driver
#: calls `spawner.update` only in its between-attempt feed window). `1` is the
#: state right after a release: `update` -> `enforce_transport` wakes a fruit
#: whose along speed has dropped below 0.02 m/s by re-applying the belt's
#: expected speed **and zeroing its angular velocity** - which would arrest a
#: rolling hull. The knob exists to separate "the release offset" from "the
#: release offset as the feeder's wake loop leaves it".
WAKE = os.environ.get("FRUIT_OFFSET_WAKE", "0") == "1"


def step() -> None:
    """One tick through the fixed-step pump (AGENTS §3b: never `update_app(N)`)."""
    SimulationManager.step(steps=1)
    app_utils.update_app(steps=0)


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()

    seed = int(os.environ.get("SEED", "5"))
    spawner = FruitSpawner(scene.stage, cfg, seed=seed)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    # `reset` parks every body and clears the schedule. The probe never primes and
    # never calls `update`, so no fruit is released behind its back: the belt's
    # surface velocity is authored on the kinematic belt body, so a respawned
    # fruit rides it without the feeder running.
    spawner.reset()

    instances = sorted(spawner.samples, key=lambda s: int(s.index))
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(
        f"[offset] probe: seed={seed} schedule={spawner.supply.schedule} "
        f"pool={len(instances)} belt_center={cfg.belt_center[0]:.2f} "
        f"speed={cfg.belt_speed:+.3f} m/s band={spawner.supply.x_min:.2f}-"
        f"{spawner.supply.x_max:.2f} spawn_y={cfg.spawn_y:+.2f} "
        f"xs={','.join(f'{x:.2f}' for x in XS)} settle_ticks={SETTLE} "
        f"passes={PASSES} repeat={REPEAT} belt_top={belt_top:.3f}"
    )

    # ------------------------------------------------------------------ #
    # the geometry read: the authored hull of every instance
    # ------------------------------------------------------------------ #
    def geometry(sample) -> dict:
        mesh = UsdGeom.Mesh(scene.stage.GetPrimAtPath(sample.prim_path))
        attr = mesh.GetPointsAttr()
        if not attr or not attr.HasValue():
            return {}
        points = np.asarray(attr.Get(), dtype=float).reshape(-1, 3)
        if points.size == 0:
            return {}
        lowest = int(np.argmin(points[:, 2]))
        z_min = float(points[lowest, 2])
        # The commanded body origin is `belt_top + dia/2 + 0.03`; the hull's own
        # lowest local z is `z_min`, so `bottom_gap_mm` is the *real* clearance
        # under this hull (> 30 mm: the hull is shorter than a sphere of the same
        # diameter; < 0: it starts interpenetrating the belt).
        bottom_gap = (sample.diameter / 2.0 + 0.03 + z_min) * 1000.0
        return {
            "z_min_mm": z_min * 1000.0,
            "x_at_zmin_mm": float(points[lowest, 0]) * 1000.0,
            "y_at_zmin_mm": float(points[lowest, 1]) * 1000.0,
            "bottom_gap_mm": bottom_gap,
            "centroid_x_mm": float(points[:, 0].mean()) * 1000.0,
            "centroid_y_mm": float(points[:, 1].mean()) * 1000.0,
            "extent_x_mm": (float(points[:, 0].max()) - float(points[:, 0].min())) * 1000.0,
            "n_points": int(points.shape[0]),
        }

    geoms = {int(s.index): geometry(s) for s in instances}
    for sample in instances:
        g = geoms[int(sample.index)]
        say(
            f"[offset] geom idx={int(sample.index):02d} cat={sample.category:<10s} "
            f"dia_mm={sample.diameter * 1000:6.1f} "
            f"z_min_mm={g['z_min_mm']:+7.2f} x_at_zmin_mm={g['x_at_zmin_mm']:+6.2f} "
            f"y_at_zmin_mm={g['y_at_zmin_mm']:+6.2f} "
            f"bottom_gap_mm={g['bottom_gap_mm']:+6.2f} "
            f"centroid_x_mm={g['centroid_x_mm']:+6.2f} "
            f"centroid_y_mm={g['centroid_y_mm']:+6.2f} "
            f"extent_x_mm={g['extent_x_mm']:6.2f} n_points={g['n_points']}"
        )

    # ------------------------------------------------------------------ #
    # one spawn, one settle
    # ------------------------------------------------------------------ #
    def spawn_and_settle(sample, x_cmd: float, ticks: int) -> dict:
        """Drop one body at `x_cmd` on an empty belt and follow its x per tick."""
        spawner.respawn(sample, along=cfg.spawn_y, x=float(x_cmd))
        if WAKE and sample not in spawner.active:
            spawner.active.append(sample)
        xs: list[float] = []
        zs: list[float] = []
        ys: list[float] = []
        for _ in range(ticks):
            if WAKE:
                spawner.enforce_transport()
            step()
            pos = spawner.position(sample)
            xs.append(float(pos[0]))
            ys.append(float(pos[1]))
            zs.append(float(pos[2]))
        if WAKE and sample in spawner.active:
            spawner.active.remove(sample)
        steps_mm = [abs(xs[i] - xs[i - 1]) * 1000.0 for i in range(1, len(xs))]
        max_step = max(steps_mm) if steps_mm else 0.0
        max_tick = (steps_mm.index(max_step) + 1) if steps_mm else 0
        # the last tick with any motion above the print noise (0.02 mm/tick)
        noisy = [i + 1 for i, v in enumerate(steps_mm) if v > 0.02]
        last_tick = noisy[-1] if noisy else 0
        profile = {t: (xs[t - 1] if t - 1 < len(xs) else xs[-1]) for t in PROFILE_TICKS}
        return {
            "x_cmd": float(x_cmd),
            "x_settle": xs[-1] if xs else float("nan"),
            "profile": profile,
            "off_mm": (xs[-1] - x_cmd) * 1000.0 if xs else float("nan"),
            "max_step_mm": max_step,
            "max_step_tick": max_tick,
            "last_step_tick": last_tick,
            "y_settle": ys[-1] if ys else float("nan"),
            # how far the hull's own lowest point sits above the belt at rest
            # (0.0 = resting on it; >0 = floating; <0 = interpenetrating)
            "dz_settle_mm": (zs[-1] + geoms[int(sample.index)]["z_min_mm"] / 1000.0 - belt_top) * 1000.0
            if zs
            else float("nan"),
            "ticks": ticks,
        }

    def park(sample) -> None:
        spawner.park(sample)
        for _ in range(4):
            step()

    # ------------------------------------------------------------------ #
    # MODE live: the shipped free-cadence feeder, release-attributed
    # ------------------------------------------------------------------ #
    if MODE == "live":
        if not spawner.supply.scatter or spawner.supply.patch or spawner.supply.bed:
            say("[offset] warning: live mode is written for the shipped scatter "
                "schedule without patch/bed pairs; the attribution assumes the "
                "only respawn draw is the lateral uniform")
        seconds = float(os.environ.get("FRUIT_OFFSET_LIVE_SECONDS", "120"))
        prime_count = int(os.environ.get("FRUIT_OFFSET_LIVE_PRIME", "4"))
        edge = float(os.environ.get("FRUIT_OFFSET_LIVE_EDGE", "0.02"))
        say(
            f"[offset] live: seconds={seconds:.0f} prime={prime_count} "
            f"edge={edge:.3f} (the free cadence, `update` every tick: P38's "
            f"condition, with the release attributed by the respawn wrapper)"
        )

        pending: dict[int, dict] = {}
        finished: list[dict] = []
        clock = {"tick": 0}
        original = spawner.respawn

        def wrapped(sample, along=None, x_jitter: float = 0.10, x=None):
            """`respawn` with the commanded x recorded (and the draw kept in place).

            Drawing the lateral x here instead of inside `respawn` consumes the
            *same* single `rng.uniform(x_min, x_max)` call at the *same* point in
            the stream, so the schedule is unchanged; the only difference is that
            the probe now knows the value.
            """
            if x is None and spawner.supply.scatter:
                x = spawner.rng.uniform(spawner.supply.x_min, spawner.supply.x_max)
            pending[int(sample.index)] = {
                "index": int(sample.index),
                "category": sample.category,
                "diameter": sample.diameter,
                "grade": sample.grade,
                "x_cmd": float(x) if x is not None else float("nan"),
                "t_spawn": clock["tick"],
                "x_first": None,
                "prev_x": None,
                "max_step_mm": 0.0,
                "done": False,
            }
            return original(sample, along=along, x_jitter=x_jitter, x=x)

        spawner.respawn = wrapped
        spawner.prime(count=prime_count)
        ticks = int(seconds / DT)
        sim = 0.0
        for t in range(ticks):
            clock["tick"] = t
            spawner.update(sim)
            step()
            sim += DT
            for s in spawner.state():
                index = int(s["index"])
                rec = pending.get(index)
                if rec is None or rec["done"]:
                    continue
                x = float(s["position"][0])
                y = float(s["position"][1])
                if rec["x_first"] is None:
                    rec["x_first"] = x
                    rec["t_first"] = t
                if rec["prev_x"] is not None:
                    rec["max_step_mm"] = max(
                        rec["max_step_mm"], abs(x - rec["prev_x"]) * 1000.0
                    )
                rec["prev_x"] = x
                rec["x_edge"] = x
                rec["y_edge"] = y
                rec["t_edge"] = t
                if y <= edge:
                    rec["done"] = True
                    finished.append(rec)

        say(
            f"[offset] live: {len(finished)} releases reached edge {edge:.2f} "
            f"({sum(1 for r in pending.values() if not r['done'])} still riding), "
            f"sim={sim:.1f}s stats={spawner.stats}"
        )
        for rec in finished:
            say(
                f"[offset] live idx={rec['index']:02d} cat={rec['category']:<10s} "
                f"dia_mm={rec['diameter'] * 1000:6.1f} grade={rec['grade']} "
                f"x_cmd={rec['x_cmd']:+.5f} x_first={rec['x_first']:+.5f} "
                f"x_edge={rec['x_edge']:+.5f} "
                f"off_mm={(rec['x_edge'] - rec['x_cmd']) * 1000.0:+7.2f} "
                f"off_from_first_mm={(rec['x_edge'] - rec['x_first']) * 1000.0:+7.2f} "
                f"max_step_mm={rec['max_step_mm']:5.2f} "
                f"ticks={rec['t_edge'] - rec['t_spawn']:4d}"
            )
        by_index: dict[int, list[float]] = {}
        for rec in finished:
            by_index.setdefault(rec["index"], []).append(
                (rec["x_edge"] - rec["x_cmd"]) * 1000.0
            )
        say("[offset] live per instance: n / min / max / mean offset (mm)")
        by_sample = {int(s.index): s for s in spawner.samples}
        for index in sorted(by_index):
            values = np.asarray(by_index[index], dtype=float)
            sample = by_sample[index]
            say(
                f"[offset] live instance idx={index:02d} cat={sample.category:<10s} "
                f"dia_mm={sample.diameter * 1000:6.1f} n={values.size:2d} "
                f"min={values.min():+7.2f} max={values.max():+7.2f} "
                f"mean={values.mean():+7.2f} sd={values.std():5.2f}"
            )
        say("[offset] summary: DONE")
        return 0

    # ------------------------------------------------------------------ #
    # MODE along: does the offset depend on the along (belt-Y) position?
    # ------------------------------------------------------------------ #
    if MODE == "along":
        alongs = tuple(float(v) for v in os.environ.get(
            "FRUIT_OFFSET_ALONG", "0.68,0.50,0.32,0.14").split(","))
        wanted = tuple(int(v) for v in os.environ.get(
            "FRUIT_OFFSET_ALONG_INSTANCES", "2,5,10,13").split(",") if v.strip())
        x_cmd = float(os.environ.get("FRUIT_OFFSET_ALONG_X", f"{XS[len(XS) // 2]:.3f}"))
        say(
            f"[offset] along: instances={wanted} alongs="
            f"{','.join(f'{a:.2f}' for a in alongs)} x={x_cmd:.3f} "
            f"settle_ticks={SETTLE} (the offset must not depend on where on the "
            f"belt the drop happens for a ladder calibration to work)"
        )
        for sample in instances:
            if int(sample.index) not in wanted:
                continue
            for along in alongs:
                spawner.respawn(sample, along=along, x=x_cmd)
                for _ in range(SETTLE):
                    step()
                pos = spawner.position(sample)
                off = (float(pos[0]) - x_cmd) * 1000.0
                say(
                    f"[offset] along idx={int(sample.index):02d} "
                    f"cat={sample.category:<10s} dia_mm={sample.diameter * 1000:6.1f} "
                    f"along={along:+.2f} x_cmd={x_cmd:.3f} "
                    f"x_settle={float(pos[0]):+.5f} off_mm={off:+7.2f} "
                    f"y_end={float(pos[1]):+.4f}"
                )
                park(sample)
        say("[offset] summary: DONE")
        return 0

    # ------------------------------------------------------------------ #
    # MODE isolated: the table, PASSES x 16 instances x |XS|
    # ------------------------------------------------------------------ #
    rows: list[dict] = []
    for p in range(PASSES):
        for sample in instances:
            for x_cmd in XS:
                result = spawn_and_settle(sample, x_cmd, SETTLE)
                rows.append({"pass": p, "index": int(sample.index),
                             "category": sample.category, "diameter": sample.diameter,
                             "grade": sample.grade, **result})
                prof = " ".join(
                    f"x{t}={result['profile'][t]:+.4f}" for t in PROFILE_TICKS
                )
                say(
                    f"[offset] row pass={p} idx={int(sample.index):02d} "
                    f"cat={sample.category:<10s} dia_mm={sample.diameter * 1000:6.1f} "
                    f"grade={sample.grade} x_cmd={x_cmd:.3f} "
                    f"x_settle={result['x_settle']:+.5f} off_mm={result['off_mm']:+7.2f} "
                    f"max_step_mm={result['max_step_mm']:5.2f} "
                    f"max_step_tick={result['max_step_tick']:3d} "
                    f"last_step_tick={result['last_step_tick']:3d} "
                    f"y_settle={result['y_settle']:+.4f} "
                    f"dz_settle_mm={result['dz_settle_mm']:+6.2f} | {prof}"
                )
                park(sample)

    # ------------------------------------------------------------------ #
    # the TASK-2 block: one instance, one x, REPEAT fresh drops
    # ------------------------------------------------------------------ #
    repeat_index = int(os.environ.get("FRUIT_OFFSET_REPEAT_INDEX", str(int(instances[0].index))))
    repeat_x = float(os.environ.get("FRUIT_OFFSET_REPEAT_X", f"{XS[len(XS) // 2]:.3f}"))
    target = next(s for s in instances if int(s.index) == repeat_index)
    repeats: list[float] = []
    for r in range(REPEAT):
        result = spawn_and_settle(target, repeat_x, SETTLE)
        repeats.append(result["off_mm"])
        say(
            f"[offset] repeat r={r} idx={repeat_index:02d} cat={target.category:<10s} "
            f"dia_mm={target.diameter * 1000:6.1f} x_cmd={repeat_x:.3f} "
            f"off_mm={result['off_mm']:+7.2f} last_step_tick={result['last_step_tick']:3d}"
        )
        park(target)
    if repeats:
        say(
            f"[offset] repeat spread idx={repeat_index:02d} x={repeat_x:.3f} "
            f"n={len(repeats)} min={min(repeats):+7.2f} max={max(repeats):+7.2f} "
            f"spread_mm={max(repeats) - min(repeats):5.2f} "
            f"mean={float(np.mean(repeats)):+7.2f}"
        )

    # ------------------------------------------------------------------ #
    # the ride check: settle -> the station edge, x unchanged?
    # ------------------------------------------------------------------ #
    for sample in instances[: max(0, RIDE)]:
        x_cmd = XS[len(XS) // 2]
        result = spawn_and_settle(sample, x_cmd, SETTLE)
        xs = [result["x_settle"]]
        ticks = 0
        y = result["y_settle"]
        while y > RIDE_EDGE and ticks < RIDE_MAX:
            step()
            ticks += 1
            pos = spawner.position(sample)
            xs.append(float(pos[0]))
            y = float(pos[1])
        drift = (max(xs) - min(xs)) * 1000.0
        say(
            f"[offset] ride idx={int(sample.index):02d} cat={sample.category:<10s} "
            f"dia_mm={sample.diameter * 1000:6.1f} x_cmd={x_cmd:.3f} "
            f"x_settle={result['x_settle']:+.5f} x_edge={xs[-1]:+.5f} "
            f"drift_mm={drift:5.2f} ticks={ticks} y_end={y:+.4f}"
        )
        park(sample)

    # ------------------------------------------------------------------ #
    # the pooled per-cell read (median over passes, spread across passes)
    # ------------------------------------------------------------------ #
    cells: dict[tuple[int, float], list[float]] = {}
    for row in rows:
        cells.setdefault((row["index"], round(row["x_cmd"], 3)), []).append(row["off_mm"])
    say("[offset] cells: per instance x commanded x (median over passes, spread)")
    for sample in instances:
        cells_txt = " ".join(
            f"x{x:.2f}:{float(np.median(cells[(int(sample.index), round(x, 3))])):+7.2f}"
            f"({max(cells[(int(sample.index), round(x, 3))]) - min(cells[(int(sample.index), round(x, 3))]):4.2f})"
            for x in XS
        )
        say(
            f"[offset] instance idx={int(sample.index):02d} cat={sample.category:<10s} "
            f"dia_mm={sample.diameter * 1000:6.1f} grade={sample.grade} {cells_txt}"
        )
    say(f"[offset] feeder stats: {spawner.stats}")
    say("[offset] summary: DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
