"""P38 phase 1: where does the delivered lateral x drift come from?

    SEED=5 scripts/154_claim_run.sh logs/p38/probe_drift_s5.log \
        scripts/run.sh logs/p38/probe_drift.py

Read-only probe: builds the shipped scene + spawner and runs the **free
cadence** (the feeder as a continuously running device, the same cadence
`logs/v1/12b_supply_after_free.log` measured the delivered band on), and runs
no attempt. It records every live fruit's across-the-belt x once per physics
tick, and reports where the drift happens.

The question the phase-1 census leaves open (`drift_census.txt`): the delivered
x has a low tail - the spawn draws `rng.uniform(0.20, 0.36)` (`fruits.py:1089`)
yet the station-zone attempts reach x = 0.143-0.159 (`[1]`/`[2]`), and 3-6 % of
attempts deliver below the spawn floor. Three mechanisms could produce it, and
they have different levers:

* **a release/drop kick** - the fruit is placed 3 cm above the belt with v=(0,
  belt, 0), w=0 (`FruitSpawner.respawn`); an asymmetric hull (a pear's stem, a
  kiwi's taper) landing off-normal gives a lateral impulse in the first ~0.3 s.
  Lever: the release (settle height, orientation, a settle check).
* **a fruit-fruit contact** - the transport ratio is 1.01-1.14x of the encoder
  with a spread (`logs/173`), so a faster fruit closes on a slower one; an
  off-centre contact in a dense sheet (patch 8.9 fruit/m, bed 21 bodies) gives
  a lateral kick. Lever: the supply density / the pair separation.
* **a rolling drift** - a sphere spun up by the moving surface has no lateral
  restoring force (the cleats are **off** by default, `conveyor.py`), so any
  lateral velocity persists. Lever: a lane keeper on the transport.

The probe separates them by *where* the lateral displacement happens: the
per-edge profile of mean x (a systematic drift moves the mean; a kick moves
one fruit's x at one along position), the size of the largest per-tick lateral
step, the along position of that step, and the nearest-neighbour distance at
that tick.

Report rows (`[drift] ...`):

    [drift] class <name>: n=  drift_mean=  drift_sd=  min=  max=  n|d|>10mm= ...
    [drift] edge <y>: n=  mean  sd  p10  p90  n(<0.20)      per-edge profile
    [drift] steps: n(|dx|>2mm/tick)=  at edge histogram  nearest-neighbour median
    [drift] delivery: P(x<0.173)  P(x<0.20)  P(x>0.36)  vs the spawn band
    [drift] summary: DONE

`FRUIT_SUPPLY_*` are honoured as usual, so the same probe can be run on the
patch sheet (`FRUIT_SUPPLY_PATCH=1`) or a forced band.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.simulation_manager import SimulationManager
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.tasks import PickAndPlaceTask

install_failure_handler("p38_probe_drift")

DT = 1.0 / 120.0
#: Which arm pose to hold while the supply runs. `none` = no task at all (the
#: arms stay at their authored USD pose); `ready` = both arms at the calibrated
#: ready pose (`PickAndPlaceTask.go_ready`, what the shipped line holds while
#: the feeder runs); `grasp` = left at ready + right at its calibrated grasp
#: pose (the direct env's reset for a right-arm episode, `rl_env.py`). The
#: standalone transport probe (`[drift]` with `none`) is the control: with no
#: arm in the loop the transport's own lateral drift is what it is.
ARMS = os.environ.get("FRUIT_DRIFT_ARMS", "none").strip().lower()
#: 120 s of simulated time: at 0.12 m/s that is ~14 m of belt travel, i.e. 3-4
#: residence times, and ~90 fruit draws on the free cadence (the pool is
#: recycled) - enough for a per-class read of a ~5 % tail.
SECONDS = float(os.environ.get("FRUIT_DRIFT_SECONDS", "120"))
PRIME = int(os.environ.get("FRUIT_SUPPLY_PRIME", "4"))
#: The along positions the x is sampled at (m). 0.64 is just after the 3 cm
#: release drop (spawn_y = 0.68); 0.04 is the pick station's upstream edge.
EDGES = tuple(float(v) for v in os.environ.get(
    "FRUIT_DRIFT_EDGES", "0.64,0.60,0.54,0.48,0.42,0.36,0.30,0.24,0.18,0.12,0.06,0.02"
).split(","))
#: A per-tick lateral step above this is a *discrete* kick, not transport noise
#: (0.12 m/s of along travel is 1 mm/tick; a 2 mm lateral step is 240 mm/s).
STEP_MM = float(os.environ.get("FRUIT_DRIFT_STEP_MM", "2.0"))
#: The trigger admission floor and the spawn band, for the delivery summary.
ADMIT_X = 0.173
SPAWN_LO = 0.20
SPAWN_HI = 0.36


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
    spawner.reset()
    spawner.prime(count=PRIME)

    arm_pose = "none"
    if ARMS != "none":
        import json

        task = PickAndPlaceTask(scene, spawner, tactile, cfg)
        with open("configs/waypoints.json", encoding="utf-8") as fh:
            waypoints = json.load(fh)
        if ARMS == "grasp":
            # the direct env's reset for a right-arm episode (the P37 ep-6
            # configuration): the inactive arm at ready, the active at grasp
            task.arms["left"].teleport_joints(
                np.asarray(waypoints["arms"]["left"]["ready"], dtype=float)
            )
            task.arms["right"].teleport_joints(
                np.asarray(waypoints["arms"]["right"]["grasp"], dtype=float)
            )
            arm_pose = "left=ready right=grasp"
        else:
            task.go_ready()
            arm_pose = "both=ready"
        app_utils.update_app(steps=30)

    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(
        f"[drift] probe: seed={seed} seconds={SECONDS:.0f} arms={arm_pose} "
        f"schedule={spawner.supply.schedule} "
        f"spawn_y={cfg.spawn_y:+.2f} belt={cfg.belt_center[0]:.2f}+/-"
        f"{cfg.belt_size[0] / 2:.2f} speed={cfg.belt_speed:+.3f} m/s "
        f"band={spawner.supply.x_min:.2f}-{spawner.supply.x_max:.2f}"
    )

    #: `current[index]` is the transit in progress; `finished` holds completed
    #: transits (one per release - the pool is recycled, so an index repeats).
    current: dict[int, dict] = {}
    finished: list[dict] = []
    last: dict[int, tuple[float, float, float]] = {}
    ticks = int(SECONDS / DT)

    def on_belt(state: dict) -> bool:
        pos = state["position"]
        if abs(float(pos[0]) - cfg.belt_center[0]) > 0.30:
            return False
        if float(pos[2]) < belt_top - 0.05 or float(pos[2]) > belt_top + 0.12:
            return False
        if float(pos[1]) > cfg.spawn_y + 0.05:
            return False
        return True

    def new_transit(state: dict, x: float, y: float) -> dict:
        return {
            "cat": state["category"],
            "diameter": float(state["diameter"]),
            "x_first": x,
            "y_first": y,
            "y_last": y,
            "edge": {},
            "max_step_mm": 0.0,
            "max_step_edge": None,
            "max_step_neighbour": None,
            "vx_at_step": 0.0,
            "ticks": 0,
            "last_tick": tick,
        }

    for tick in range(ticks):
        spawner.update(SimulationManager.get_simulation_time())
        SimulationManager.step(steps=1)
        app_utils.update_app(steps=0)
        states = spawner.state()
        live = [s for s in states if on_belt(s)]
        positions = {
            int(s["index"]): (float(s["position"][1]), float(s["position"][0]))
            for s in live
        }
        for state in live:
            index = int(state["index"])
            y, x = positions[index]
            vx = float(np.asarray(state["velocity"], dtype=float)[0])
            track = current.get(index)
            if track is not None:
                # a recycle teleports the body back to the spawn end (+Y);
                # a gap in sight is either a re-spawn or a bounce out of the
                # belt window - both start a new transit, never a lateral step
                if y > track["y_last"] + 0.02 or (tick - track["last_tick"]) > 5:
                    finished.append(track)
                    track = None
                    last.pop(index, None)
            if track is None:
                track = new_transit(state, x, y)
                current[index] = track
            track["ticks"] += 1
            track["last_tick"] = tick
            track["y_last"] = y
            # the per-tick lateral step (the kick detector)
            previous = last.get(index)
            if previous is not None:
                step_mm = abs(x - previous[1]) * 1000.0
                if step_mm > track["max_step_mm"]:
                    neighbours = [
                        ((other_y - y) ** 2 + (other_x - x) ** 2) ** 0.5
                        for other, (other_y, other_x) in positions.items()
                        if other != index
                    ]
                    track["max_step_mm"] = step_mm
                    track["max_step_edge"] = y
                    track["max_step_neighbour"] = min(neighbours) if neighbours else float("nan")
                    track["vx_at_step"] = vx
            last[index] = (y, x, vx)
            # the per-edge x sample (first downward crossing)
            for edge in EDGES:
                if y <= edge and edge not in track["edge"]:
                    track["edge"][edge] = (x, vx, y)
    finished.extend(current.values())

    # ------------------------------------------------------------------ #
    done = [t for t in finished if EDGES[0] in t["edge"] and t["ticks"] > 30]
    say(
        f"[drift] tracked {len(finished)} transits ({len(current)} still on the belt), "
        f"{len(done)} with a full transit from edge {EDGES[0]:.2f} to {EDGES[-1]:.2f}"
    )

    # per-class drift, two baselines: `spawn` = the first tick (y ~ spawn_y, the
    # release drop window) and `belt` = edge EDGES[0] (0.04 m downstream). The
    # difference between them is the release; between `belt` and the delivery
    # edge is the transport.
    target_edge = EDGES[-1]
    per_class: dict[str, list[tuple[float, float]]] = {}
    drifts: list[tuple[float, float, str, dict]] = []
    for track in done:
        last_edge = max(
            (edge for edge in track["edge"] if edge >= target_edge), default=None
        )
        if last_edge is None:
            continue
        spawn_mm = (track["edge"][last_edge][0] - track["x_first"]) * 1000.0
        belt_mm = (track["edge"][last_edge][0] - track["edge"][EDGES[0]][0]) * 1000.0
        per_class.setdefault(track["cat"], []).append((spawn_mm, belt_mm))
        drifts.append((spawn_mm, belt_mm, track["cat"], track))
    say(
        f"[drift] class <name>: drift = x(edge {target_edge:.2f}) - x(spawn) "
        f"[total] and - x(edge {EDGES[0]:.2f}) [transport only], mm"
    )
    for name in sorted(per_class):
        values = np.asarray([v[0] for v in per_class[name]], dtype=float)
        belt = np.asarray([v[1] for v in per_class[name]], dtype=float)
        big = int((np.abs(values) > 10.0).sum())
        huge = int((np.abs(values) > 20.0).sum())
        say(
            f"[drift] class {name:<11s}: n={values.size:3d} total mean {values.mean():+7.2f} "
            f"sd {values.std():6.2f} min {values.min():+7.2f} max {values.max():+7.2f} "
            f"n|d|>10mm {big:2d} n|d|>20mm {huge:2d} | transport mean {belt.mean():+7.2f} "
            f"sd {belt.std():6.2f}"
        )
    if drifts:
        allv = np.asarray([d[0] for d in drifts], dtype=float)
        allb = np.asarray([d[1] for d in drifts], dtype=float)
        say(
            f"[drift] pooled: n={allv.size} total mean {allv.mean():+7.2f} sd {allv.std():6.2f} "
            f"min {allv.min():+7.2f} max {allv.max():+7.2f} "
            f"n|d|>10mm {int((np.abs(allv) > 10).sum())} "
            f"n|d|>20mm {int((np.abs(allv) > 20).sum())} | transport mean {allb.mean():+7.2f} "
            f"sd {allb.std():6.2f} min {allb.min():+7.2f} max {allb.max():+7.2f}"
        )

    # the per-edge profile: is the mean moving (a drift) or only the tail?
    say("[drift] edge profile (mean/sd/p10/p90 of x at each edge, mm from the spawn floor):")
    for edge in EDGES:
        values = np.asarray(
            [t["edge"][edge][0] for t in done if edge in t["edge"]], dtype=float
        )
        if values.size < 3:
            continue
        below = int((values < SPAWN_LO).sum())
        admit = int((values < ADMIT_X).sum())
        say(
            f"[drift] edge {edge:.2f}: n={values.size:3d} mean {values.mean():+.3f} "
            f"sd {values.std():.3f} p10 {np.percentile(values, 10):+.3f} "
            f"p50 {np.percentile(values, 50):+.3f} "
            f"p90 {np.percentile(values, 90):+.3f} "
            f"n<{SPAWN_LO:.2f} {below:2d} n<{ADMIT_X:.3f} {admit:2d}"
        )

    # the kick detector: where, and with a neighbour?
    say(
        f"[drift] per-tick lateral steps > {STEP_MM:.1f} mm "
        "(a discrete kick; a rolling drift would not step):"
    )
    kicks = [t for t in done if t["max_step_mm"] > STEP_MM]
    say(f"[drift]   n fruit with a step > {STEP_MM:.1f} mm: {len(kicks)}/{len(done)}")
    if kicks:
        for edge in EDGES:
            members = [t for t in kicks if abs((t["max_step_edge"] or -9) - edge) < 0.03]
            if members:
                near = np.asarray(
                    [t["max_step_neighbour"] for t in members if t["max_step_neighbour"] == t["max_step_neighbour"]],
                    dtype=float,
                )
                amps = np.asarray([t["max_step_mm"] for t in members], dtype=float)
                say(
                    f"[drift]   near y={edge:.2f}: n={len(members):2d} "
                    f"step median {np.median(amps):.1f} mm max {amps.max():.1f} mm "
                    f"nearest-fruit median "
                    f"{(1000 * np.median(near) if near.size else float('nan')):.0f} mm"
                )
        amps = np.asarray([t["max_step_mm"] for t in kicks], dtype=float)
        say(
            f"[drift]   steps > {STEP_MM:.1f} mm: median {np.median(amps):.1f} mm "
            f"p90 {np.percentile(amps, 90):.1f} mm max {amps.max():.1f} mm; "
            f"classes among them: "
            + ", ".join(
                f"{name}:{sum(1 for t in kicks if t['cat'] == name)}"
                for name in sorted({t["cat"] for t in kicks})
            )
        )

    # the delivery read at the station edge
    values = np.asarray(
        [t["edge"][target_edge][0] for t in done if target_edge in t["edge"]],
        dtype=float,
    )
    if values.size:
        say(
            f"[drift] delivery edge {target_edge:.2f}: n={values.size} "
            f"min {values.min():+.3f} p1 {np.percentile(values, 1):+.3f} "
            f"p10 {np.percentile(values, 10):+.3f} p50 {np.percentile(values, 50):+.3f} "
            f"p90 {np.percentile(values, 90):+.3f} max {values.max():+.3f}  "
            f"n<{ADMIT_X:.3f} {int((values < ADMIT_X).sum())} "
            f"n<{SPAWN_LO:.2f} {int((values < SPAWN_LO).sum())} "
            f"n>{SPAWN_HI:.2f} {int((values > SPAWN_HI).sum())}"
        )
    # which fruit sit outside the spawn band at delivery, and where they started
    out_of_band = [
        (t["edge"][target_edge][0], t["x_first"], t["cat"], t["diameter"])
        for t in done
        if target_edge in t["edge"] and not (SPAWN_LO <= t["edge"][target_edge][0] <= SPAWN_HI)
    ]
    say(f"[drift] out of band at delivery: {len(out_of_band)}/{len(values)} "
        "(x_delivery, x_spawn, class, dia):")
    for x_del, x_spawn, cat, dia in sorted(out_of_band):
        say(
            f"[drift]   x={x_del:+.3f} spawn={x_spawn:+.3f} ({1000 * (x_del - x_spawn):+.1f} mm) "
            f"{cat} dia {1000 * dia:.0f} mm"
        )
    say(f"[drift] feeder stats: {spawner.stats}")
    say("[drift] summary: DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
