"""Run scripted pick-and-place attempts on the moving belt.

    $ISAAC_SIM_DIR/python.sh scripts/20_pick_place.py
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
from fruit_sorting.common import install_failure_handler, look_at_quat, say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.tasks import PickAndPlaceTask
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

install_failure_handler("20_pick_place")

DT = 1.0 / 120.0
ATTEMPTS = int(os.environ.get("ATTEMPTS", "4"))


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()

    capture = os.environ.get("FRUIT_CAPTURE", "0") == "1"
    if capture:
        eye = (1.75, 1.55, 2.35)
        observer = RtxCamera(
            "/World/ObserverCamera",
            tick_rate=30.0,
            positions=[eye],
            orientations=[look_at_quat(eye, (0.45, 0.0, 1.05))],
        )
        observer.camera.set_focal_lengths(0.016)
        observer.camera.set_apertures((0.036, 0.02025))
        observer.camera.set_clipping_ranges(0.01, 50.0)
        observer_sensor = CameraSensor(observer, resolution=(600, 1000), annotators=["rgb"])

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
            summary = [
                (s["category"], round(float(s["position"][0]), 3), round(s["diameter"], 3))
                for s in states
            ]
            say(f"[run] attempt {attempt}: no eligible fruit; active={summary} stats={spawner.stats}")
            continue
        grade = target["grade"]
        bin_index = 0 if grade == "A" else 1
        bin_xy = cfg.bin_positions[bin_index]
        say(
            f"[run] attempt {attempt}: picking {target['category']} grade {grade} "
            f"into bin at {bin_xy}"
        )
        result = task.run(target, bin_index)
        results.append(result)
        say(
            f"[run] attempt {attempt}: grasped={result.grasped} placed={result.placed} "
            f"lift={result.peak_lift:+.3f} m force={result.max_tactile_force:.2f} N "
            f"notes={result.notes}"
        )
        task.go_ready()
        app_utils.update_app(steps=30)

    if capture:
        for tag, sensor in (("observer", observer_sensor), ("head", scene.camera_sensor)):
            data = sensor.get_data("rgb")
            if data is None:
                continue
            arr = np.asarray(data[0].numpy() if hasattr(data, "__getitem__") else data)
            from PIL import Image

            path = f"logs/pick_{tag}.png"
            Image.fromarray(arr[..., :3].astype(np.uint8)).save(path)
            say(f"saved {path}")

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
