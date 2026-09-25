"""Measure how much simulated time one app update advances, and fix it.

    $ISAAC_SIM_DIR/python.sh scripts/34_timestep_probe.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import carb

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager


def measure(label: str, n: int = 20) -> None:
    t0 = SimulationManager.get_simulation_time()
    app_utils.update_app(steps=n)
    dt = SimulationManager.get_simulation_time() - t0
    say(f"{label}: {dt / n * 1000:.2f} ms of sim per app update")


def main() -> int:
    scene = SortingScene(SceneConfig()).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=30)
    settings = carb.settings.get_settings()

    for key in (
        "/app/player/useFixedTimeStep",
        "/app/player/fixedTimeStep",
        "/persistent/simulation/minFrameRate",
        "/persistent/simulation/useFixedTimeStep",
    ):
        say(f"before {key} = {settings.get(key)}")
    measure("baseline")

    settings.set("/app/player/useFixedTimeStep", True)
    settings.set("/app/player/fixedTimeStep", 1.0 / 120.0)
    measure("after setting player/*")

    settings.set("/persistent/simulation/useFixedTimeStep", True)
    settings.set("/persistent/simulation/minFrameRate", 60)
    measure("after setting persistent/*")

    # Explicit single physics step + one app frame for rendering/sensors.
    t0 = SimulationManager.get_simulation_time()
    for _ in range(10):
        SimulationManager.step(steps=1)
        app_utils.update_app(steps=1)
    dt = SimulationManager.get_simulation_time() - t0
    say(f"explicit step + update: {dt / 10 * 1000:.2f} ms of sim per iteration")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
