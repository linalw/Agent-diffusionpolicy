"""Inspect joint drive gains and the contact-sensor data layout.

    $ISAAC_SIM_DIR/python.sh scripts/16_gains_probe.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import inspect

import numpy as np

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from isaacsim.core.experimental.prims import Articulation
from isaacsim.sensors.experimental.physics import Contact, ContactSensor


def main() -> int:
    scene = SortingScene(SceneConfig()).build(parts=("environment", "robot"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=30)
    robot = scene.robot

    say(f"set_dof_gains signature: {inspect.signature(Articulation.set_dof_gains)}")
    gains = robot.get_dof_gains()
    say(f"get_dof_gains returned {type(gains)} len={len(gains) if hasattr(gains, '__len__') else '?'}")
    if isinstance(gains, tuple):
        stiffness, damping = gains[0], gains[1]
        s = np.asarray(stiffness.numpy() if hasattr(stiffness, "numpy") else stiffness)
        d = np.asarray(damping.numpy() if hasattr(damping, "numpy") else damping)
        names = list(robot.dof_names)
        for i, name in enumerate(names):
            say(f"  gain {name:34s} k={s.reshape(-1)[i]:9.3f} c={d.reshape(-1)[i]:8.3f}")
    else:
        say(f"  gains={gains}")

    tactile = GripperTactile()
    tactile.attach(robot)
    key, sensor = next(iter(tactile.sensors.items()))
    data = sensor.get_data()
    say(f"contact get_data type={type(data)}")
    if isinstance(data, dict):
        for k, v in data.items():
            arr = v.numpy() if hasattr(v, "numpy") else v
            arr = np.asarray(arr) if not isinstance(arr, dict) else arr
            say(f"  key={k!r} type={type(v)} shape={getattr(arr, 'shape', None)}")

    sensor.reset()
    say(f"after reset: {sensor.get_data()}")
    say(f"get_sensor_reading: {sensor.get_sensor_reading()!r}"[:400])

    app_utils_pause = __import__("isaacsim.core.experimental.utils.app", fromlist=["pause"])
    app_utils_pause.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
