"""Measure the incoming supply: gaps, lateral spread, mix, density, starvation.

    scripts/run.sh scripts/171_supply_probe.py

The v9/V1 directive replaces the neat fixed-spacing fruit line with a
scattered, dense supply. This probe measures the *supply itself* over a long
horizon - the quantities the directive names - without spending attempts on it:

* **density**: how many fruit are on the main belt at once (mean / min / max);
* **gaps**: the along-the-line clearance between consecutive fruit;
* **lateral**: the across-the-belt (x) distribution, against the station's
  measured reach band (`scripts/174_station_reach.py`,
  `logs/v1/61_station_reach_seeded.log`: x = 0.18..0.39 holds ~6 mm, x >= 0.42
  is 55-96 mm out);
* **mix**: the released class and grade counts (the lane rule is A -> lane 0,
  the rest -> lane 1);
* **starvation**: every tick, the *real* selector
  (`PickAndPlaceTask.select_target`) is asked for the next target on the
  single-arm line and for each bimanual lane (`lane=0/1`, `min_lead_s=1.4` as
  the bimanual worker passes). The fraction of ticks with no candidate per arm
  is the starvation - the number the owner's directive is about. Reading fruit
  poses is the documented safe read class; no attempt is ever run.

Run it on the fixed line (`FRUIT_SUPPLY_SCATTER=0`) and on the scattered
default to compare. The tree is not touched; output is one trace line every
`FRUIT_SUPPLY_PROBE_EVERY` ticks (default 600 = 5 s) plus a summary.

Cadence (`FRUIT_SUPPLY_PROBE_CADENCE`): `free` calls `spawner.update` every
tick - the feeder as a continuously running device, which measures the *supply
design* (density, gaps, lateral, lane starvation of the stocked line).
`driver` mirrors the shipped single-arm driver (a 60-tick feed window once per
~1900-tick attempt cycle): it is the *line state the single-arm selector asks
about*, and it shows the old line's between-attempt emptiness (`queue_peak=0`).
The bimanual worker is a third cadence (it feeds during every starved station
spin); its delivered starvation is read from the real `FRUIT_BIARM=1` runs by
`scripts/173_supply_report.py`, not from this probe.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

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

install_failure_handler("171_supply_probe")

DT = 1.0 / 120.0
SECONDS = float(os.environ.get("FRUIT_SUPPLY_SECONDS", "90"))
TICKS = int(SECONDS / DT)
EVERY = int(os.environ.get("FRUIT_SUPPLY_PROBE_EVERY", "600"))
PRIME = int(os.environ.get("FRUIT_SUPPLY_PRIME", "4"))
BIARM_LEAD_S = float(os.environ.get("FRUIT_BIARM_SELECT_LEAD_S", "1.4"))
#: v9/V2 two-line stations (the scheduler's defaults): left upstream at the
#: calibrated station, right 0.20 m downstream. The probe asks the real
#: selector at each arm's own station with the two-line preference rule.
STATION_L = float(os.environ.get("FRUIT_BIARM_STATION_L", "0.0"))
STATION_R = float(os.environ.get("FRUIT_BIARM_STATION_R", "-0.10"))
KEYS = (
    "single", "left", "right", "left_biarm", "right_biarm",
    "left_line", "right_line",
)
#: `free` calls `spawner.update` every tick (the feeder as a continuously
#: running device); `driver` (default) mirrors the shipped single-arm driver:
#: a 60-tick feed window once per ~1900-tick attempt cycle. `driver` is the
#: *delivered* supply of the shipped loop; `free` measures the supply design's
#: spacing/density without the driver's sparse-call artifact.
CADENCE = os.environ.get("FRUIT_SUPPLY_PROBE_CADENCE", "driver")
FEED_TICKS = int(os.environ.get("FRUIT_SUPPLY_PROBE_FEED", "60"))
CYCLE_TICKS = int(os.environ.get("FRUIT_SUPPLY_PROBE_CYCLE", "1900"))


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

    task = PickAndPlaceTask(scene, spawner, tactile, cfg)
    task.go_ready()
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(f"[supply] contact tracking on {spawner.enable_contact_tracking()} fruit")

    # Pool composition: the scattered pool carries the designed mix by
    # construction; the release order is a seeded shuffle of it.
    mix_class: dict[str, int] = {}
    mix_grade: dict[str, int] = {}
    for sample in spawner.samples:
        mix_class[sample.category] = mix_class.get(sample.category, 0) + 1
        mix_grade[sample.grade] = mix_grade.get(sample.grade, 0) + 1

    frames = 0
    counts: list[int] = []
    lateral: list[float] = []
    gaps: list[float] = []
    stacked = 0
    max_contact = 0.0
    starve = {key: 0 for key in KEYS}
    starve_run = {key: 0 for key in KEYS}
    starve_max = {key: 0 for key in KEYS}
    #: Grade crossing of the two-line selections: {lane: {"A": n, "BC": n}}.
    route = {0: {"A": 0, "BC": 0}, 1: {"A": 0, "BC": 0}}

    def on_belt(states: list[dict]) -> list[dict]:
        out = []
        for state in states:
            pos = state["position"]
            if abs(float(pos[0]) - cfg.belt_center[0]) > 0.30:
                continue  # on an output conveyor or off the line
            if float(pos[2]) < belt_top - 0.05 or float(pos[2]) > belt_top + 0.12:
                continue  # fell off / above the main belt
            if float(pos[1]) > cfg.spawn_y + 0.05:
                continue
            out.append(state)
        return out

    for tick in range(TICKS):
        if CADENCE == "free" or (tick % CYCLE_TICKS) < FEED_TICKS:
            spawner.update(SimulationManager.get_simulation_time())
        SimulationManager.step(steps=1)
        app_utils.update_app(steps=0)
        states = spawner.state()
        live = on_belt(states)
        frames += 1
        counts.append(len(live))
        ordered = sorted(live, key=lambda item: float(item["position"][1]))
        for first, second in zip(ordered, ordered[1:]):
            gaps.append(abs(float(first["position"][1]) - float(second["position"][1])))
        for state in live:
            lateral.append(float(state["position"][0]))
            # "Stacked" = a fruit resting higher than its own belt radius plus
            # the release drop would put it (it sits on another body, not on
            # the belt). 0.06 m clears the 0.03 m spawn drop.
            surface = belt_top + float(state["diameter"]) / 2.0
            if float(state["position"][2]) > surface + 0.06:
                stacked += 1
        try:
            contacts = spawner.net_contact_forces()
            if contacts:
                max_contact = max(
                    max_contact, max(float(np.linalg.norm(v)) for v in contacts.values())
                )
        except Exception:  # noqa: BLE001 - contact tracking is optional
            pass

        # Starvation: the real selector, exactly as the two lines call it.
        targets = {
            "single": task.select_target(states),
            "left": task.select_target(states, lane=0),
            "right": task.select_target(states, lane=1),
            "left_biarm": task.select_target(states, lane=0, min_lead_s=BIARM_LEAD_S),
            "right_biarm": task.select_target(states, lane=1, min_lead_s=BIARM_LEAD_S),
            # Two-line (v9/V2): the arm's own station, grade preference with the
            # any-grade fallback (lane=None). These are the eligibility numbers
            # the two-line scheduler delivers.
            "left_line": task.select_target(
                states, station_y=STATION_L, prefer_lane=0, min_lead_s=BIARM_LEAD_S
            ),
            "right_line": task.select_target(
                states, station_y=STATION_R, prefer_lane=1, min_lead_s=BIARM_LEAD_S
            ),
        }
        for key, target in targets.items():
            if target is None:
                starve[key] += 1
                starve_run[key] += 1
                starve_max[key] = max(starve_max[key], starve_run[key])
            else:
                starve_run[key] = 0
        for lane, key in ((0, "left_line"), (1, "right_line")):
            target = targets[key]
            if target is not None:
                route[lane]["A" if target.get("grade") == "A" else "BC"] += 1

        if tick % EVERY == 0:
            parts = []
            for sample in sorted(spawner.active, key=lambda s: s.index):
                if sample.parked:
                    continue
                pos = spawner.position(sample)
                vel = spawner.velocity(sample)
                parts.append(
                    f"#{sample.index} {sample.category[:4]} "
                    f"y={float(pos[1]):+.2f} z={float(pos[2]):.3f} vy={float(vel[1]):+.3f}"
                )
            say(
                f"[supply] t={tick * DT:6.2f}s on_belt={len(live):2d} "
                f"single={'y' if targets['single'] else '-'} "
                f"L={'y' if targets['left'] else '-'} "
                f"R={'y' if targets['right'] else '-'} | " + " | ".join(parts)
            )

    frames = max(frames, 1)
    say(f"[supply] ---- summary (cadence={CADENCE}) ----")
    arr = np.asarray(counts, dtype=float)
    say(
        f"[supply] density: on-belt mean {arr.mean():.2f}, min {int(arr.min())}, "
        f"max {int(arr.max())} (frames with 0: {(arr == 0).mean() * 100:.1f}%)"
    )
    gap_arr = np.asarray(gaps, dtype=float)
    if gap_arr.size:
        say(
            f"[supply] gaps: n={gap_arr.size} min {gap_arr.min():.3f} "
            f"p10 {np.percentile(gap_arr, 10):.3f} p50 {np.percentile(gap_arr, 50):.3f} "
            f"p90 {np.percentile(gap_arr, 90):.3f} max {gap_arr.max():.3f} m"
        )
    lat_arr = np.asarray(lateral, dtype=float)
    if lat_arr.size:
        say(
            f"[supply] lateral x: min {lat_arr.min():+.3f} "
            f"p10 {np.percentile(lat_arr, 10):+.3f} "
            f"p50 {np.percentile(lat_arr, 50):+.3f} "
            f"p90 {np.percentile(lat_arr, 90):+.3f} max {lat_arr.max():+.3f} m "
            f"(belt {cfg.belt_center[0] - cfg.belt_size[0] / 2:.3f}"
            f"..{cfg.belt_center[0] + cfg.belt_size[0] / 2:.3f})"
        )
    say(
        "[supply] mix (pool): classes="
        + ",".join(f"{key}:{mix_class[key]}" for key in sorted(mix_class))
        + " grades="
        + ",".join(f"{key}:{mix_grade[key]}" for key in sorted(mix_grade))
    )
    for key in KEYS:
        say(
            f"[supply] starvation {key:11s}: no candidate {starve[key]}/{frames} "
            f"ticks = {starve[key] / frames * 100:.2f}%, longest run "
            f"{starve_max[key] * DT:.2f}s"
        )
    for lane in (0, 1):
        counts = route[lane]
        total = counts["A"] + counts["BC"]
        crossover = counts["BC"] if lane == 0 else counts["A"]
        say(
            f"[supply] two-line routing lane {lane}: selected {total} ticks "
            f"(A {counts['A']}, B/C {counts['BC']}, crossover "
            f"{crossover / max(1, total) * 100:.1f}%)"
        )
    say(f"[supply] feeder stats: {spawner.stats}")
    say(
        f"[supply] stacked/flying fruit frames: {stacked} "
        f"(a fruit above its own belt radius); max |contact force| {max_contact:.1f} N"
    )
    say("[supply] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
