"""Close-up render of the procedural fruit so the shapes can be reviewed.

    $ISAAC_SIM_DIR/python.sh scripts/51_fruit_preview.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 1280, "height": 720})

import numpy as np
from PIL import Image

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.rendering_manager import RenderingManager
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, look_at_quat, say, to_numpy
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene

install_failure_handler("51_fruit_preview")


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()

    # Two views: a hero close-up of one apple, and the whole row.
    hero_eye = (0.72, -0.30, 1.32)
    hero = RtxCamera(
        "/World/HeroCam", tick_rate=0.0,
        positions=[hero_eye], orientations=[look_at_quat(hero_eye, (0.98, 0.0, 1.19))],
    )
    hero.camera.set_focal_lengths(0.050)
    hero.camera.set_apertures((0.036, 0.02025))
    hero.camera.set_clipping_ranges(0.01, 50.0)
    hero_sensor = CameraSensor(hero, resolution=(720, 1280), annotators=["rgb"])

    eye = (1.28, 0.72, 1.52)
    cam = RtxCamera(
        "/World/PreviewCam", tick_rate=0.0,
        positions=[eye], orientations=[look_at_quat(eye, (0.95, -0.06, 1.18))],
    )
    cam.camera.set_focal_lengths(0.028)
    cam.camera.set_apertures((0.036, 0.02025))
    cam.camera.set_clipping_ranges(0.01, 50.0)
    sensor = CameraSensor(cam, resolution=(720, 1280), annotators=["rgb"])

    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    spawner = FruitSpawner(scene.stage, cfg, seed=12)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    belt_z = 1.17
    # One of each category in a row down the belt.
    x = 0.52
    for sample in spawner.samples[:8]:
        sample.held = True
        if sample not in spawner.active:
            spawner.active.append(sample)
        spawner.place(sample, np.array([x, 0.0, belt_z + sample.diameter * 0.45]))
        x += 0.14
    app_utils.update_app(steps=40)
    for _ in range(30):
        RenderingManager.render()

    row = to_numpy(sensor.get_data("rgb"))
    if row is not None:
        array = np.asarray(row)
        if array.ndim == 4:
            array = array[0]
        Image.fromarray(array[..., :3].astype(np.uint8)).save("logs/fruit_row.png")

    # Hero shot: park everything, then put a single apple on a turntable-height
    # pedestal in front of the camera.
    for s_ in spawner.samples:
        spawner.place(s_, np.array([5.0 + 0.3 * s_.index, 0.0, -5.0]))
    apple = next(s for s in spawner.samples if s.category == "apple")
    spawner.place(apple, np.array([0.86, -0.16, 1.26]))
    for _ in range(60):
        RenderingManager.render()
    data = to_numpy(hero_sensor.get_data("rgb"))
    say(f"hero apple: d={apple.diameter*100:.1f}cm mass={apple.mass*1000:.0f}g mu={apple.friction:.2f}")
    if data is not None:
        array = np.asarray(data)
        if array.ndim == 4:
            array = array[0]
        Image.fromarray(array[..., :3].astype(np.uint8)).save("logs/fruit_preview.png")
        say("saved logs/fruit_preview.png")
    for sample in spawner.samples[:8]:
        say(f"  {sample.category:11s} d={sample.diameter * 100:5.2f}cm mass={sample.mass * 1000:6.1f}g "
            f"mu={sample.friction:.2f}")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
