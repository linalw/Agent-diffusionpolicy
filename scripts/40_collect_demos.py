"""Collect scripted demonstrations into datasets/demos.

    FRUIT_EPISODES=20 scripts/run.sh scripts/40_collect_demos.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

# Set HEADLESS=0 to watch the run in the Isaac Sim GUI.
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

# Raise the fd limit before Isaac Sim starts: this build opens ~2100
# `/dev/nvidiactl` descriptors on the first camera read and dies with
# `dup failed ... Too many open files` at the default limit.
raise_fd_limit()

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils

try:  # pragma: no cover - import guard mirrors the other entry scripts
    from isaacsim.core.simulation_manager import SimulationManager
except ImportError:  # pragma: no cover
    SimulationManager = None

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
FIXED_STEPPING = os.environ.get("FRUIT_FIXED_STEPPING", "1") == "1"


def advance(steps: int) -> None:
    """Advance the feeder exactly, then pump the camera/sensor callbacks.

    `update_app(steps=N)` is not a fixed step (WORKLOG: sixty calls advanced 118
    ticks on one run and 120 on the next) and the collector's inter-episode feed
    is a scripted path, so route it through `SimulationManager.step` and keep the
    pump-only `update_app(steps=0)` - the sensors starve without it.
    """
    if FIXED_STEPPING and SimulationManager is not None:
        SimulationManager.step(steps=steps)
        app_utils.update_app(steps=0)
    else:
        app_utils.update_app(steps=steps)


def _md5(path: str) -> str:
    import hashlib

    try:
        with open(path, "rb") as handle:
            return hashlib.md5(handle.read()).hexdigest()
    except OSError:
        return ""


def write_manifest(out_dir: str) -> None:
    """Record what produced this shard: sources, configs, seed, knobs.

    The index alone cannot tell two datasets apart; a policy number is only
    quotable with the tree that collected it (AGENTS: a run is one sample of a
    configuration). Written before the first episode, so even a failed shard is
    identifiable afterwards.
    """
    import json
    import time

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    sources = [
        "src/fruit_sorting/tasks.py",
        "src/fruit_sorting/assets.py",
        "src/fruit_sorting/conveyor.py",
        "src/fruit_sorting/scene.py",
        "src/fruit_sorting/fruits.py",
        "src/fruit_sorting/dataset.py",
        "scripts/40_collect_demos.py",
        "configs/waypoints.json",
        "configs/motion_reference.json",
    ]
    manifest = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "episodes": EPISODES,
        "seed": os.environ.get("SEED", "21"),
        "camera_res": os.environ.get("FRUIT_CAMERA_RES", ""),
        "fixed_stepping": FIXED_STEPPING,
        "md5": {name: _md5(os.path.join(root, name)) for name in sources},
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    say(f"[collect] manifest -> {os.path.join(out_dir, 'manifest.json')}")


def main() -> int:
    write_manifest(OUT_DIR)
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
    spawner.belt = scene.belt
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
            advance(1)
            spawner.update(task._sim_time())
            spawner.enforce_transport()
        target = task.select_target(spawner.state())
        if target is None:
            continue
        bin_index = 0 if target["grade"] == "A" else 1
        os.environ["FRUIT_EPISODE_INDEX"] = str(saved)
        try:
            result = task.run(
                target, bin_index, verbose=os.environ.get("FRUIT_VERBOSE", "0") == "1"
            )
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
