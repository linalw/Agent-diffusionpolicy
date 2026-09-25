"""Collect scripted demonstrations into datasets/demos.

    FRUIT_EPISODES=20 $ISAAC_SIM_DIR/python.sh scripts/40_collect_demos.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

# Set HEADLESS=0 to watch the run in the Isaac Sim GUI.
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.dataset import EpisodeRecorder
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.tasks import PickAndPlaceTask

install_failure_handler("40_collect_demos")

DT = 1.0 / 120.0
EPISODES = int(os.environ.get("FRUIT_EPISODES", "10"))
OUT_DIR = os.environ.get("FRUIT_DEMO_DIR", "datasets/demos")


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()

    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "21")))
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()
    spawner.prime(count=6)

    task = PickAndPlaceTask(scene, spawner, tactile, cfg)
    task.recorder = EpisodeRecorder(OUT_DIR, decimation=4)
    task.go_ready()

    attempts = 0
    saved = 0
    while saved < EPISODES and attempts < EPISODES * 3:
        attempts += 1
        for _ in range(40):
            app_utils.update_app(steps=1)
            spawner.update(task._sim_time())
            spawner.enforce_transport()
        target = task.select_target(spawner.state())
        if target is None:
            continue
        bin_index = 0 if target["grade"] == "A" else 1
        os.environ["FRUIT_EPISODE_INDEX"] = str(saved)
        try:
            result = task.run(target, bin_index, verbose=False)
        except Exception as exc:  # noqa: BLE001
            say(f"episode failed: {exc}")
            continue
        say(
            f"episode {saved}: {result.category} grade={result.grade} arm={result.arm} "
            f"grasped={result.grasped} placed={result.placed} notes={result.notes}"
        )
        if result.success:
            saved += 1
        task.go_ready()

    say(f"collected {saved} successful episodes into {OUT_DIR} (attempts={attempts})")
    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
