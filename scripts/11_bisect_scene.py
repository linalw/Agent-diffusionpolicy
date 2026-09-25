"""Bisect which scene part causes a physics/RTX crash.

    FRUIT_PARTS=environment,robot $ISAAC_SIM_DIR/python.sh scripts/11_bisect_scene.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.scene import SortingScene

PARTS = tuple(p.strip() for p in os.environ.get("FRUIT_PARTS", "environment,pedestal,robot").split(",") if p.strip())
STEPS = int(os.environ.get("FRUIT_STEPS", "60"))


def main() -> int:
    scene = SortingScene(SceneConfig()).build(parts=PARTS)
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=STEPS)
    scene.step(10)
    say(f"OK parts={list(PARTS)} steps={STEPS}")
    app_utils.pause()
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
