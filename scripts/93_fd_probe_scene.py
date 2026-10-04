"""Measure file-descriptor growth in the real sorting scene.

`92_fd_probe.py` shows a bare SimulationApp does not leak. This one builds the
actual cell (belt, arms, head camera with its annotators) and reports the
descriptor count after each phase, so the leaking phase is obvious.

    $ISAAC_SIM_DIR/python.sh scripts/93_fd_probe_scene.py
"""

from __future__ import annotations

import os
import resource
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"
simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.rendering_manager import RenderingManager
from isaacsim.core.simulation_manager import SimulationManager
from fruit_sorting.assets import SceneConfig
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile

DT = 1.0 / 120.0


def counters() -> dict[str, int]:
    buckets: dict[str, int] = {}
    for entry in os.listdir("/proc/self/fd"):
        try:
            target = os.readlink(f"/proc/self/fd/{entry}")
        except OSError:
            continue
        if target.endswith("nvidiactl"):
            key = "nvidiactl"
        elif "nvidia" in target:
            key = "nvidia-dev"
        elif target.startswith("/dev/shm"):
            key = "shm"
        elif target.startswith("/dev/dma_heap"):
            key = "dmabuf"
        elif target.startswith("pipe:"):
            key = "pipe"
        elif target.startswith("anon_inode"):
            key = "anon_inode"
        else:
            key = "other"
        buckets[key] = buckets.get(key, 0) + 1
    buckets["TOTAL"] = sum(v for k, v in buckets.items() if k != "TOTAL")
    return buckets


def report(tag: str) -> None:
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    data = counters()
    ordered = " ".join(f"{k}={data.get(k, 0)}" for k in ("TOTAL", "nvidiactl", "nvidia-dev", "shm", "dmabuf", "pipe", "anon_inode"))
    print(f"[fd] {tag:<34} soft={soft} {ordered}", flush=True)


def main() -> int:
    report("boot")
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    report("scene built (head camera + annotators)")

    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()
    report("after scene.start")

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    spawner.prime(count=4)
    report("after fruit spawn")

    for block in range(1, 6):
        for _ in range(60):
            SimulationManager.step(steps=1)
        report(f"physics only, {(block) * 60} steps")

    for block in range(1, 6):
        for _ in range(60):
            SimulationManager.step(steps=1)
            RenderingManager.render()
        report(f"+ RenderingManager.render, block {block}")

    for block in range(1, 4):
        for _ in range(30):
            SimulationManager.step(steps=1)
            RenderingManager.render()
            scene.camera_sensor.get_data("rgb")
            scene.camera_sensor.get_data("instance_id_segmentation")
        report(f"+ camera get_data, block {block} (30 frames)")

    # The pick-and-place loops advance the app with update_app; that is the one
    # call the phases above never make.
    for block in range(1, 6):
        for _ in range(60):
            app_utils.update_app(steps=1)
        report(f"+ update_app(steps=1), block {block}")

    simulation_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
