"""Feeder-only proof of the bed's release schedule (P32 phase A).

    FRUIT_SUPPLY_BED=1 FRUIT_BED_DIAG=1 scripts/run.sh \
      scripts/214_bed_feeder_probe.py

The bed's starvation in the simulator ("no eligible fruit" with a live fruit at
along 0.545) had to be attributed to the *feeder* or to the *arm*, and a
scripted battery costs ~4 min per sample. This probe removes the arm's motion
and keeps everything the supply depends on: the same scene, the real
`FruitSpawner`, the real `PickAndPlaceTask.select_target`, the task's own
control cadence and its feed stride. The only stand-in is the pick itself - the
chosen fruit is `park`ed (teleported off the belt), which is exactly what the
arm does to the feeder after a grasp, so the belt sees the same demand (one
fruit per attempt) without a grasp's physics.

Cadence, per attempt (the shipped driver's, `scripts/20_pick_place.py`):

* 60 ticks of `advance(1)` + `spawner.update(now)` - the between-attempt settle
  window, with the feeder pumped once per tick (the shipped loop);
* one `select_target` on the live state (the pick point of the measurement);
* `FRUIT_ATTEMPT_S` seconds of control ticks through `task._step_sim(1)`, i.e.
  the task's own primitive: with `FRUIT_FEED_CADENCE=1` it pumps the feeder on
  its stride, without it the belt runs with no pump at all (the shipped
  attempt-boundary cadence).

Per attempt it prints the live census in the three bands that matter (below the
station, the station window, the selector's window at/above the catch floor),
the chosen target or the first failing predicate (`FRUIT_BED_DIAG=1`), and the
pump's absolute clock lag. The summary is the metric the bed's density claim
needs: **the mean window candidate count at pick**, the empty slots, the
placements and the peak live bodies.

`FRUIT_ATTEMPTS` (default 10), `FRUIT_ATTEMPT_S` (default 15), `SEED` (5),
`FRUIT_BED_PROBE_DIAG` (0/1, the per-fruit predicate rows; default off - the
one-line-per-attempt census is always printed).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import install_failure_handler, say  # noqa: E402
from fruit_sorting.fruits import FruitSpawner  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402
from fruit_sorting.tasks import PickAndPlaceTask  # noqa: E402

install_failure_handler("214_bed_feeder_probe")

DT = 1.0 / 120.0
ATTEMPTS = int(os.environ.get("FRUIT_ATTEMPTS", "10"))
ATTEMPT_S = float(os.environ.get("FRUIT_ATTEMPT_S", "15"))
SETTLE_TICKS = int(os.environ.get("FRUIT_BED_PROBE_SETTLE_TICKS", "60"))
#: The selector's own floor is dynamic (`_dynamic_select_floor`); this is only
#: the *census* band, so the probe prints the real floor beside it.
CATCH_FLOOR = float(os.environ.get("FRUIT_BED_PROBE_FLOOR", "0.40"))


def advance(steps: int) -> None:
    """The driver's tick-exact advance (`20_pick_place.py`)."""
    SimulationManager.step(steps=steps)
    app_utils.update_app(steps=0)


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    scene.start(physics_dt=DT, warmup_steps=60)

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    advance(30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    spawner.prime(count=4)

    task = PickAndPlaceTask(scene, spawner, None, cfg)
    # `tactile=None`: the probe never grasps, and the constructor only stores it
    # (the contact sensors exist for the attempt legs; `select_target` and
    # `_feed_tick` never read them). Everything else is the shipped object, so
    # the selector's predicates and floors are the ones the scripted line runs.
    # The task arms the feed inside `_run_impl`; the probe never runs an attempt,
    # so mirror the same two lines here (`tasks.py` line ~7712).
    task._feed_on = bool(task._feed_cadence) and task._prepared_scope(True)
    say(
        f"[probe] feeder-only: attempts={ATTEMPTS} attempt_s={ATTEMPT_S:.1f} "
        f"feed_cadence={int(bool(task._feed_on))} stride={task._feed_stride} "
        f"prepared={int(task._prepared_next)} "
        f"queue_max={os.environ.get('FRUIT_QUEUE_MAX', '6')} "
        f"diag={os.environ.get('FRUIT_BED_DIAG', '0')}"
    )

    settle = SETTLE_TICKS
    attempt_ticks = max(1, int(round(ATTEMPT_S / DT)))
    window_counts: list[int] = []
    empty_slots = 0
    picks = 0
    marks = (
        int(spawner.stats.get("bed_placed", 0)),
        int(spawner.stats.get("released", 0)),
        int(spawner.stats.get("supply_skipped", 0)),
    )
    for attempt in range(ATTEMPTS):
        for _ in range(settle):
            advance(1)
            spawner.update(SimulationManager.get_simulation_time())
        states = spawner.state()
        diag = [] if os.environ.get("FRUIT_BED_DIAG", "0") == "1" else None
        target = task.select_target(states, diag=diag)
        now = SimulationManager.get_simulation_time()
        alongs = sorted(
            (
                float(state["position"][1]),
                float(state["position"][0]),
                state["category"],
            )
            for state in states
        )
        # Census bands: downstream of the station (< 0), the station window
        # [0, 0.18], the upstream window above the catch floor.
        below = sum(1 for along, _x, _c in alongs if along < cfg.pick_y)
        station = sum(
            1 for along, _x, _c in alongs if cfg.pick_y <= along < cfg.pick_y + 0.18
        )
        window = [along for along, _x, _c in alongs if along >= cfg.pick_y + CATCH_FLOOR]
        window_counts.append(len(window))
        placed = int(spawner.stats.get("bed_placed", 0)) - marks[0]
        released = int(spawner.stats.get("released", 0)) - marks[1]
        skipped = int(spawner.stats.get("supply_skipped", 0)) - marks[2]
        marks = (
            int(spawner.stats.get("bed_placed", 0)),
            int(spawner.stats.get("released", 0)),
            int(spawner.stats.get("supply_skipped", 0)),
        )
        say(
            f"[probe] attempt {attempt} t={now:.2f} live={len(states)} "
            f"below={below} station={station} window={len(window)} "
            f"top={window[-1] if window else float('nan'):+.3f} "
            f"pick="
            + ("none" if target is None else f"{target['category']}@{float(target['position'][1]):+.3f}")
            + f" pump_next={float(getattr(spawner, '_next_release', 0.0)):.2f} "
            f"lag={float(now - getattr(spawner, '_next_release', now)):+.2f} "
            f"placed=+{placed} draws=+{released} skipped=+{skipped}"
        )
        if diag is not None:
            task.bed_diag_report(attempt, diag)
        if target is None:
            empty_slots += 1
        else:
            picks += 1
            sample = next(
                (s for s in spawner.samples if s.index == int(target["index"])), None
            )
            if sample is not None:
                spawner.park(sample)
                if sample in spawner.active:
                    spawner.active.remove(sample)
        for _ in range(attempt_ticks):
            task._step_sim(1)

    mean_window = sum(window_counts) / max(1, len(window_counts))
    say(
        f"[probe] summary: picks={picks}/{ATTEMPTS} empty={empty_slots} "
        f"window mean={mean_window:.2f} min={min(window_counts)} "
        f"max={max(window_counts)} "
        f"bed_placed={int(spawner.stats.get('bed_placed', 0))} "
        f"bed_draws={int(spawner.stats.get('bed_draws', 0))} "
        f"live_recycled={int(spawner.stats.get('bed_live_recycled', 0))} "
        f"bed_refused={int(spawner.stats.get('bed_refused', 0))} "
        f"rebased={int(spawner.stats.get('bed_rebased', 0))} "
        f"holds={int(spawner.stats.get('bed_holds', 0))} "
        f"dropped={float(spawner.stats.get('bed_late_dropped_s', 0.0)):.1f}s "
        f"fell_off={int(spawner.stats.get('fell_off', 0))} "
        f"reached_end={int(spawner.stats.get('reached_end', 0))} "
        f"live={len([s for s in spawner.active if not s.parked])}"
    )
    floor = int(os.environ.get("FRUIT_BED_PROBE_MIN_PICKS", str(ATTEMPTS)))
    verdict = "PASS" if picks >= floor else "STARVED"
    say(f"[probe] verdict: {verdict} (picks {picks} vs floor {floor})")
    # Exit 0 with the verdict in the log: the probe is a measurement, and a
    # non-zero exit makes the claim wrapper report an "error" for a successful
    # starved read (which is itself a result).
    return 0


if __name__ == "__main__":
    sys.exit(main())
