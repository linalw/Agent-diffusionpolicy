"""Find a loop structure that renders fresh frames without breaking fine physics control.

    $ISAAC_SIM_DIR/python.sh scripts/39_render_probe.py
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
from fruit_sorting.common import say, to_numpy
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager


def frame(camera):
    data = camera.get_data("rgb")
    return None if data is None else np.asarray(to_numpy(data))


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    spawner = FruitSpawner(scene.stage, cfg, seed=9)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()
    spawner.prime(count=6)
    app_utils.update_app(steps=10)

    camera = scene.camera_sensor
    say(f"playing={app_utils.is_playing()} paused={app_utils.is_paused()}")

    # --- A: current approach, update_app(steps=0) ---
    a_frames = []
    t0 = SimulationManager.get_simulation_time()
    for i in range(40):
        SimulationManager.step(steps=1)
        if i % 10 == 0:
            app_utils.update_app(steps=0)
            a_frames.append(frame(camera))
    dt_a = SimulationManager.get_simulation_time() - t0
    say(f"A step+update0 : sim {dt_a * 1000:.1f}ms over 40 iters, distinct frames={len({f.tobytes() for f in a_frames if f is not None})}/{len(a_frames)}")

    # --- B: manual physics step + explicit render call (no app update) ---
    from isaacsim.core.rendering_manager import RenderingManager

    b_frames = []
    t0 = SimulationManager.get_simulation_time()
    for i in range(40):
        SimulationManager.step(steps=1)
        RenderingManager.render()
        if i % 10 == 0:
            b_frames.append(frame(camera))
    dt_b = SimulationManager.get_simulation_time() - t0
    say(f"B step+render(): sim {dt_b * 1000:.1f}ms over 40 iters, distinct frames={len({f.tobytes() for f in b_frames if f is not None})}/{len(b_frames)}")

    # --- C: render only, no physics step ---
    c_frames = []
    t0 = SimulationManager.get_simulation_time()
    for i in range(40):
        RenderingManager.render()
        if i % 10 == 0:
            c_frames.append(frame(camera))
    dt_c = SimulationManager.get_simulation_time() - t0
    say(f"C render only  : sim {dt_c * 1000:.1f}ms over 40 iters, distinct frames={len({f.tobytes() for f in c_frames if f is not None})}/{len(c_frames)}")

    # Does the world still evolve with the explicit render loop?
    sample = spawner.active[0]
    x0 = float(spawner.position(sample)[0])
    for _ in range(120):
        spawner.enforce_transport()
        SimulationManager.step(steps=1)
        RenderingManager.render()
    x1 = float(spawner.position(sample)[0])
    say(f"fruit moved {x0:.4f} -> {x1:.4f} (delta {x1 - x0:+.4f} m)")

    d1 = frame(camera)
    SimulationManager.step(steps=60)
    app_utils.update_app(steps=1)
    d2 = frame(camera)
    say(f"frames differ after motion: {not np.array_equal(d1, d2)}")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
