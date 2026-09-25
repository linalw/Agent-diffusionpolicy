"""Isolate belt physics: track a single fruit on the belt and log its trajectory.

    $ISAAC_SIM_DIR/python.sh scripts/13_belt_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.simulation_manager import SimulationManager
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene

DT = 1.0 / 120.0
SECONDS = float(os.environ.get("BELT_TEST_SECONDS", "12"))


def main() -> int:
    cfg = SceneConfig()
    if os.environ.get("BELT_SPEED") is not None:
        cfg.belt_speed = float(os.environ["BELT_SPEED"])
    parts = tuple(p.strip() for p in os.environ.get("FRUIT_PARTS", "environment,conveyor").split(","))
    scene = SortingScene(cfg).build(parts=parts)
    scene.start(physics_dt=DT, warmup_steps=60)

    spawner = FruitSpawner(scene.stage, cfg, seed=3)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()

    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(f"belt center={cfg.belt_center} size={cfg.belt_size} top_z={belt_top:.3f}")

    samples = spawner.samples[:3]
    for i, sample in enumerate(samples):
        spawner.respawn(sample, y=cfg.spawn_x - 0.5 * i)
        sample.parked = False
        spawner.active.append(sample)
        p = spawner.position(sample)
        say(f"fruit {sample.index} {sample.category} d={sample.diameter * 100:.1f}cm start={np.round(p, 3).tolist()}")

    for step in range(int(SECONDS / DT)):
        app_utils.update_app(steps=1)
        if step % int(0.5 / DT) == 0:
            t = SimulationManager.get_simulation_time()
            for sample in samples:
                p = spawner.position(sample)
                v = spawner.velocity(sample)
                in_x = cfg.belt_center[0] - cfg.belt_size[0] / 2.0 <= p[0] <= cfg.belt_center[0] + cfg.belt_size[0] / 2.0
                say(
                    f"t={t:5.2f} fruit{sample.index} pos=({p[0]:+.3f},{p[1]:+.3f},{p[2]:+.3f}) "
                    f"vel=({v[0]:+.3f},{v[1]:+.3f},{v[2]:+.3f}) on_belt_x={in_x}"
                )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
