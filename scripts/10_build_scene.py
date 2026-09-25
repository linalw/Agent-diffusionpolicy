"""Build the sorting cell, drop fruit on the belt, and verify transport + capture.

    $ISAAC_SIM_DIR/python.sh scripts/10_build_scene.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

# Set HEADLESS=0 to watch the run in the Isaac Sim GUI.
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

simulation_app = SimulationApp({"headless": HEADLESS, "width": 1280, "height": 720})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, look_at_quat, say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene

install_failure_handler("10_build_scene")

DT = 1.0 / 120.0
RUN_SECONDS = float(os.environ.get("RUN_SECONDS", "6.0"))


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()

    # An extra fixed camera purely for layout review screenshots. It must be
    # created before the simulation starts so its render product is valid.
    eye = (1.15, 1.25, 1.70)
    observer = RtxCamera(
        "/World/ObserverCamera",
        tick_rate=30.0,
        positions=[eye],
        orientations=[look_at_quat(eye, (0.15, 0.0, 0.85))],
    )
    observer.camera.set_focal_lengths(0.020)
    observer.camera.set_apertures((0.036, 0.02025))
    observer.camera.set_clipping_ranges(0.01, 50.0)
    observer_sensor = CameraSensor(observer, resolution=(540, 960), annotators=["rgb"])

    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    scene.report_robot()

    spawner = FruitSpawner(scene.stage, cfg, seed=7)
    spawner.create_pool()
    # Give the newly authored rigid bodies a physics view before moving them.
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()
    spawner.prime(count=4)

    steps = int(RUN_SECONDS / DT)
    captured = 0
    for step in range(steps):
        app_utils.update_app(steps=1)
        sim_time = SimulationManager.get_simulation_time()
        spawner.update(sim_time)
        if step % max(1, steps // 3) == 0:
            scene.capture(f"logs/scene_head_{captured}.png")
            from PIL import Image

            rgb = np.asarray(observer_sensor.get_data("rgb")[0].numpy())
            Image.fromarray(rgb[..., :3].astype(np.uint8)).save(f"logs/scene_observer_{captured}.png")
            states = spawner.state()
            say(f"t={sim_time:.2f}s live_fruit={len(states)} stats={spawner.stats}")
            for s in states[:4]:
                p = s["position"]
                say(
                    f"   {s['category']:10s} grade={s['grade']} d={s['diameter'] * 100:.1f}cm "
                    f"pos=({p[0]:+.3f},{p[1]:+.3f},{p[2]:+.3f})"
                )
            captured += 1

    say(f"captured {captured} frames; fruit live={len(spawner.active)} stats={spawner.stats}")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
