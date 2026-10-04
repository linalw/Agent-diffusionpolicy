"""Can the OpenArm's OWN fingers grip if we make their visual meshes collidable?

The runtime asset's finger `collisions/` subtrees are empty (world bounds invalid),
so the original gripper has never had contact geometry. The `visuals/` subtree does
have a mesh. This probe applies `UsdPhysics.CollisionAPI` to those existing visual
prims - an override on an existing prim, which is the class of edit that does reach
the instanced robot - and then tries a real pinch-and-lift.

    scripts/run.sh scripts/419_original_gripper_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import numpy as np
from pxr import PhysxSchema, Usd, UsdPhysics

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.motion import min_jerk_ramp
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

DT = 1.0 / 120.0
SIDE = os.environ.get("FRUIT_TEST_ARM", "right")
FINGERS = ("left", "right")


def make_finger_meshes_collidable(stage) -> int:
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    count = 0
    for side in ("left", "right"):
        for which in FINGERS:
            path = f"/World/OpenArm/openarm_{side}_{which}_finger/visuals"
            root = stage.GetPrimAtPath(path)
            if not root.IsValid():
                say(f"missing {path}")
                continue
            for prim in Usd.PrimRange(root, proxies):
                if prim.GetTypeName() != "Mesh":
                    continue
                if not prim.HasAPI(UsdPhysics.CollisionAPI):
                    UsdPhysics.CollisionAPI.Apply(prim)
                UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(True)
                PhysxSchema.PhysxCollisionAPI.Apply(prim).CreateContactOffsetAttr().Set(0.002)
                if hasattr(PhysxSchema, "PhysxConvexHullCollisionAPI"):
                    PhysxSchema.PhysxConvexHullCollisionAPI.Apply(prim)
                count += 1
    return count


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    scene.start(physics_dt=DT, warmup_steps=60)
    made = make_finger_meshes_collidable(scene.stage)
    say(f"applied collision to {made} finger visual mesh prims")
    spawner = FruitSpawner(scene.stage, cfg, seed=3)
    spawner.create_pool()
    SimulationManager.step(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()

    arm = ArmController(scene, SIDE)
    waypoints = None
    import json

    with open("configs/waypoints.json", encoding="utf-8") as fh:
        waypoints = json.load(fh)
    sample = spawner.samples[0]
    d = sample.diameter
    lift = float(os.environ.get("FRUIT_LIFTER_HEIGHT", "0.06"))
    seat = cfg.belt_center[2] + cfg.belt_size[2] / 2.0 + lift + d / 2.0
    spawner.place(sample, np.array([cfg.pick_x, cfg.pick_y, seat]))
    sample.held = True
    for _ in range(30):
        SimulationManager.step(steps=1)
    say(f"fruit {sample.category} d={d*100:.1f}cm placed at z={seat:.4f}")

    arm.teleport_joints(np.asarray(waypoints["arms"][SIDE]["grasp"], dtype=float))
    for _ in range(60):
        SimulationManager.step(steps=1)
    goal = np.array([cfg.pick_x, cfg.pick_y, cfg.belt_center[2] + cfg.belt_size[2] / 2.0
                     + float(os.environ.get("FRUIT_GRASP_Z", "0.095"))])
    residual = arm.solve_to(goal, iterations=600, tolerance=0.006, restarts=3, seed=5)[1]
    say(f"jaw at {np.round(arm.jaw_centre(), 4).tolist()} residual={residual*1000:.1f}mm "
        f"separation={arm.jaw_separation()*1000:.1f}mm")
    for _ in range(40):
        SimulationManager.step(steps=1)

    # Close the fingers all the way and hold.
    close = float(os.environ.get("FRUIT_TEST_CLOSE", "0.004"))
    for value in min_jerk_ramp(arm.OPEN, close, 120):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=1)
    for _ in range(60):
        SimulationManager.step(steps=1)
    say(f"closed: separation={arm.jaw_separation()*1000:.1f}mm "
        f"tactile={getattr(arm, 'tactile', None)}")

    # Lift: command the jaw up and see whether the fruit follows.
    start = arm.jaw_centre().copy()
    for dz in min_jerk_ramp(0.0, 0.15, 200):
        arm.ik_step(arm.tcp_target_for_jaw(start + np.array([0.0, 0.0, float(dz)])))
        SimulationManager.step(steps=1)
    for _ in range(60):
        SimulationManager.step(steps=1)
    pos = spawner.position(sample)
    say(f"lifted: fruit z={pos[2]:.4f} (started {seat:.4f}, delta={(pos[2]-seat)*1000:+.0f}mm) "
        f"fruit_xy={np.round(pos[:2], 4).tolist()}")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
