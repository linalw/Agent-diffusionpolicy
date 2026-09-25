"""Test whether the contact sensor reports a force when a contact actually exists.

    $ISAAC_SIM_DIR/python.sh scripts/37_contact_probe.py
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
from fruit_sorting.common import say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.sensors.experimental.physics import Contact, ContactSensor


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "conveyor"))

    spawner = FruitSpawner(scene.stage, cfg, seed=2)
    spawner.create_pool()

    # Contact sensor on a plain rigid body (a fruit), attached during authoring.
    sample = spawner.samples[0]
    contact = Contact(f"{sample.prim_path}/contact", min_threshold=0.0, max_threshold=1e6, radius=-1.0)
    sensor = ContactSensor(contact)

    scene.start(physics_dt=1.0 / 120.0, warmup_steps=30)
    spawner.refresh_rigids()
    spawner.reset()
    spawner.respawn(sample, y=cfg.spawn_x)
    spawner.active.append(sample)
    say("dropped a fruit on the belt")

    for step in range(600):
        SimulationManager.step(steps=1)
        if step % 100 == 0:
            reading = sensor.get_sensor_reading()
            data = sensor.get_data()
            keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
            z = float(spawner.position(sample)[2])
            say(f"step {step:4d} z={z:.4f} reading={reading} data_keys={keys}")

    say(f"final reading: {sensor.get_sensor_reading()}")
    say(f"final raw: {sensor.get_raw_data()!r}"[:300])

    # Also check the finger sensors from GripperTactile in this same run.
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    say(f"finger sensor reading: {list(tactile.sensors.values())[0].get_sensor_reading()}")
    say(f"finger force reader: {GripperTactile.__name__} prims={len(tactile._prims)}")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
