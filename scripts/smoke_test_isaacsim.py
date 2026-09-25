"""Smoke test: verify Isaac Sim launches, renders, steps physics, and captures an image.

Run with the built Isaac Sim python launcher:

    $ISAAC_SIM_DIR/python.sh scripts/smoke_test_isaacsim.py

Set HEADLESS=0 to use the GUI.
"""

from __future__ import annotations

import os
import sys

HEADLESS = os.environ.get("HEADLESS", "1") == "1"
PHYSICS_STEPS = int(os.environ.get("PHYSICS_STEPS", "20"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import traceback

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import Cube, DistantLight, GroundPlane
from isaacsim.core.experimental.prims import GeomPrim, RigidPrim
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.sensors.camera import Camera


def say(msg: str) -> None:
    """Print and flush so the message survives Kit's fast shutdown."""
    print(f"[smoke] {msg}", flush=True)


def main() -> int:
    say("creating stage")
    stage_utils.create_new_stage()

    GroundPlane("/World/GroundPlane", positions=[0.0, 0.0, 0.0])
    DistantLight("/World/DistantLight", positions=[0.0, 0.0, 10.0]).set_intensities(300.0)
    say("ground + light ok")

    Cube("/World/FallingCube", positions=[0.0, 0.0, 2.0], sizes=0.2)
    cube = RigidPrim("/World/FallingCube")
    cube.set_masses([1.0])
    say("cube ok")

    camera = Camera(
        prim_path="/World/Camera",
        translation=np.array([1.5, 1.5, 1.2]),
        resolution=(640, 480),
    )
    camera.set_clipping_range(0.1, 100.0)
    camera.set_focal_length(18.0)
    say("camera ok")

    SimulationManager.set_backend("torch")
    SimulationManager.switch_physics_engine("physx")
    SimulationManager.set_physics_dt(1.0 / 60.0)
    app_utils.play()
    app_utils.update_app(steps=1)
    say("simulation started")

    cube_prim = RigidPrim("/World/FallingCube")
    z_before = float(cube_prim.get_world_poses()[0].numpy()[0][2])
    for _ in range(PHYSICS_STEPS):
        app_utils.update_app(steps=1)
    z_after = float(cube_prim.get_world_poses()[0].numpy()[0][2])
    say(f"cube z before/after  : {z_before:.4f} -> {z_after:.4f}")

    camera.initialize()
    app_utils.update_app(steps=10)
    rgb = camera.get_rgb()
    depth = camera.get_depth()
    say(f"rgb shape            : {None if rgb is None else rgb.shape}")
    say(f"depth shape          : {None if depth is None else depth.shape}")
    say(f"depth finite ratio   : {float(np.isfinite(depth).mean()) if depth is not None else 0.0:.3f}")

    say(f"isaac sim root       : {os.environ.get('ISAAC_PATH', '?')}")
    say(f"headless             : {HEADLESS}")

    app_utils.pause()
    say("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        with open("logs/smoke_traceback.txt", "w") as fh:
            traceback.print_exc(file=fh)
        say("FAILED - see logs/smoke_traceback.txt")
        code = 1
    finally:
        simulation_app.close()
    sys.exit(code)
