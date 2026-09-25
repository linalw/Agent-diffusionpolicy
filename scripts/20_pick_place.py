"""Run scripted pick-and-place attempts on the moving belt.

    $ISAAC_SIM_DIR/python.sh scripts/20_pick_place.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.tasks import PickAndPlaceTask

install_failure_handler("20_pick_place")

DT = 1.0 / 120.0
ATTEMPTS = int(os.environ.get("ATTEMPTS", "4"))


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()

    tactile = GripperTactile()
    # Attach before play() so the contact views are valid.
    tactile.attach(stage=scene.stage)

    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()
    spawner.prime(count=4)

    task = PickAndPlaceTask(scene, spawner, tactile, cfg)
    task.go_ready()
    say(f"arms ready; belt top z={task.belt_top:.3f}")

    results = []
    for attempt in range(ATTEMPTS):
        for _ in range(60):
            app_utils.update_app(steps=1)
            spawner.update(__import__("isaacsim.core.simulation_manager", fromlist=["SimulationManager"]).SimulationManager.get_simulation_time())
        states = spawner.state()
        target = task.select_target(states)
        if target is None:
            say(f"[run] attempt {attempt}: no eligible fruit")
            continue
        grade = target["grade"]
        bin_xy = cfg.bin_positions[0] if grade == "A" else cfg.bin_positions[1]
        say(
            f"[run] attempt {attempt}: picking {target['category']} grade {grade} "
            f"into bin at {bin_xy}"
        )
        result = task.run(target, bin_xy)
        results.append(result)
        say(
            f"[run] attempt {attempt}: grasped={result.grasped} placed={result.placed} "
            f"lift={result.peak_lift:+.3f} m force={result.max_tactile_force:.2f} N "
            f"notes={result.notes}"
        )
        task.go_ready()
        app_utils.update_app(steps=30)

    if results:
        successes = sum(1 for r in results if r.success)
        say(f"[run] summary: {successes}/{len(results)} successful")
    for r in results:
        say(
            f"[run]   {r.category:10s} arm={r.arm:5s} grasped={r.grasped} placed={r.placed} "
            f"lift={r.peak_lift:+.3f} N={r.max_tactile_force:.2f}"
        )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
