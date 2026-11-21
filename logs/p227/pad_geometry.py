#!/usr/bin/env python3
"""P227k: where the Panda's pad faces actually are, and do they collide?

    FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/pad_geometry.py

`hand_frame.log` read the Panda's frame exactly (closing = hand -Y, jaw 58.4 mm
down the hand +Z) and showed `top_down_quaternion("x")` puts the hand top-down
with the pads closing across the belt at **0.8 mm / 0.11 deg** - so the P227i
grasp failure is not the attitude. What it did not show is where the *pad faces*
sit relative to the jaw centre, because the finger link prims report no mesh
bound under a plain traversal: the robot is a **reference**, and its subtree is
instance proxies (`Usd.PrimRange` does not enter them by default).

So this probe walks the finger links **with `Usd.TraverseInstanceProxies`** and
prints, in the tool frame (jaw-centre origin, hand rotation): the meshes, their
collision state, and the pads' `close/along/down` extents. Those extents are
what the grasp standoff has to be derived from - `dz` was copied from the
OpenArm's tuned 60 mm, which puts a 100 mm finger's contact band somewhere else
entirely.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import numpy as np  # noqa: E402
from pxr import Usd, UsdGeom, UsdPhysics  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.control import ArmController, arm_specs  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

DT = 1.0 / 120.0


def say(text: str) -> None:
    print(f"[fruit] [pg] {text}", flush=True)


def quat_matrix(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = float(scene.belt.belt_top)
    stage = scene.stage
    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)
    SimulationManager.step(steps=20)
    spec = arm_specs()[0]
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)

    # the hand and the two fingers, with proxies
    for name in (spec.tcp_link, *spec.finger_link_names):
        prim = stage.GetPrimAtPath(f"{spec.link_root}/{name}")
        say(f"link {name}: valid={prim.IsValid()} type={prim.GetTypeName()}")
        meshes = 0
        colliders = 0
        for sub in Usd.PrimRange(prim, proxies):
            if sub.GetTypeName() != "Mesh":
                continue
            meshes += 1
            col = sub.HasAPI(UsdPhysics.CollisionAPI) and bool(
                UsdPhysics.CollisionAPI(sub).GetCollisionEnabledAttr().Get()
            )
            colliders += 1 if col else 0
        say(f"   meshes={meshes} colliders={colliders}")

    def bounds_in_tool(name: str) -> None:
        prim = stage.GetPrimAtPath(f"{spec.link_root}/{name}")
        jaw = np.asarray(arm.jaw_centre(), dtype=float)
        rot = quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
        corners = []
        for sub in Usd.PrimRange(prim, proxies):
            if sub.GetTypeName() != "Mesh":
                continue
            box = UsdGeom.Boundable(sub).ComputeWorldBound(
                Usd.TimeCode.Default(), UsdGeom.Tokens.default_
            )
            rng = box.ComputeAlignedRange()
            mn = np.array(rng.GetMin(), dtype=float)
            mx = np.array(rng.GetMax(), dtype=float)
            corners.extend(
                [x, y, z] for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])
            )
        if not corners:
            say(f"   {name}: no mesh corners")
            return
        rel = (np.array(corners) - jaw) @ rot
        say(
            f"   {name}: close[{rel[:, 0].min():+.3f},{rel[:, 0].max():+.3f}] "
            f"along[{rel[:, 1].min():+.3f},{rel[:, 1].max():+.3f}] "
            f"down[{rel[:, 2].min():+.3f},{rel[:, 2].max():+.3f}]  "
            f"world z[{np.array(corners)[:, 2].min():.3f},{np.array(corners)[:, 2].max():.3f}]"
        )

    say("--- open, at the hanging pose (tool frame: close=X, along=Y, down=Z) ---")
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    tcp = np.asarray(arm.tcp_position(), dtype=float)
    say(f"jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}) tcp=({tcp[0]:+.3f},{tcp[1]:+.3f},{tcp[2]:.3f})")
    for name in (spec.tcp_link, *spec.finger_link_names):
        bounds_in_tool(name)

    say("--- closed (q=0) ---")
    arm.set_gripper(0.0)
    SimulationManager.step(steps=40)
    for name in spec.finger_link_names:
        bounds_in_tool(name)

    say("--- open again, at the grasp pose ---")
    arm.set_gripper(arm.OPEN)
    target = np.array([cfg.pick_x, cfg.pick_y, belt_top + float(cfg.grasp_clearance)])
    q0 = np.asarray(arm.joint_positions(), dtype=float)
    arm.teleport_joints(q0)
    arm.hold_quaternion = None
    above = np.array([target[0], target[1], target[2] + 0.12])
    arm.solve_to(above, iterations=600, tolerance=0.006, restarts=1, move_on_fail=True)
    SimulationManager.step(steps=5)
    arm.solve_to(target, iterations=1500, tolerance=0.004, restarts=2, move_on_fail=True)
    SimulationManager.step(steps=10)
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    say(f"grasp jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}) belt_top={belt_top:.3f} target_z={target[2]:.3f}")
    for name in spec.finger_link_names:
        bounds_in_tool(name)
    say(f"finger span (open)={arm.jaw_separation() * 1000:.1f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
