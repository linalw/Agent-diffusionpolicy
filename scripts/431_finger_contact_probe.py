"""Is the finger-fruit contact real? Static A/B of the two collider recipes.

`logs/422` (probe `scripts/419_original_gripper_test.py`) closed the de-instanced
asset's finger meshes on a strawberry and lifted it 85 mm with this recipe,
applied *after* `scene.start()`:

    UsdPhysics.CollisionAPI.Apply(mesh) (enabled)
    PhysxSchema.PhysxCollisionAPI(contactOffset=0.002)
    PhysxSchema.PhysxConvexHullCollisionAPI.Apply(mesh)

`scene._add_finger_colliders` applies CollisionAPI + ConvexHullAPI (no contact
offset) during build, i.e. *before* play. This probe runs both recipes against a
**static** arm and a **static** fruit, so there is no tracking, no belt motion
and no dynamics confound: the only question is whether the closing fingers touch
the fruit.

    PROBE_COLLIDERS=scene scripts/run.sh scripts/431_finger_contact_probe.py
    PROBE_COLLIDERS=post  scripts/run.sh scripts/431_finger_contact_probe.py

For each fruit the arm is posed once, the fruit is teleported to a range of
heights below the jaw centre and the fingers are closed fully (target gap 4 mm).
If the fingers stall above the fully-closed separation, the fruit blocked them;
otherwise they closed through its space.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import json

import numpy as np
from pxr import PhysxSchema, Usd, UsdPhysics

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

DT = 1.0 / 120.0
os.environ.setdefault("FRUIT_FINGER_COLLIDERS", "0")  # applied explicitly below
os.environ.setdefault("FRUIT_NO_SLEEP", "1")


def apply_scene_recipe(stage) -> int:
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    count = 0
    for side in ("left", "right"):
        for which in ("left", "right"):
            root = stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_{which}_finger/visuals")
            if not root.IsValid():
                continue
            for prim in Usd.PrimRange(root, proxies):
                if prim.GetTypeName() != "Mesh":
                    continue
                if not prim.HasAPI(UsdPhysics.CollisionAPI):
                    UsdPhysics.CollisionAPI.Apply(prim)
                UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(True)
                if hasattr(PhysxSchema, "PhysxConvexHullCollisionAPI"):
                    PhysxSchema.PhysxConvexHullCollisionAPI.Apply(prim)
                count += 1
    return count


def apply_post_recipe(stage) -> int:
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    count = 0
    for side in ("left", "right"):
        for which in ("left", "right"):
            root = stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_{which}_finger/visuals")
            if not root.IsValid():
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


def bounds(stage, path: str) -> tuple[np.ndarray, np.ndarray]:
    from pxr import UsdGeom

    prim = stage.GetPrimAtPath(path)
    box = UsdGeom.Boundable(prim).ComputeWorldBound(
        Usd.TimeCode.Default(), UsdGeom.Tokens.default_
    )
    rng = box.ComputeAlignedRange()
    return np.array(rng.GetMin(), dtype=float), np.array(rng.GetMax(), dtype=float)


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    mode = os.environ.get("PROBE_COLLIDERS", "scene")
    if mode == "scene":
        made = apply_scene_recipe(scene.stage)
    else:
        made = 0
    scene.start(physics_dt=DT, warmup_steps=60)
    if mode != "scene":
        made = apply_post_recipe(scene.stage)
    say(f"collider recipe={mode}: {made} finger mesh prims")

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    SimulationManager.step(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()

    side = os.environ.get("PROBE_SIDE", "right")
    arm = ArmController(scene, side)
    arm.set_gripper(arm.OPEN)
    with open(os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json"), encoding="utf-8") as fh:
        waypoints = json.load(fh)
    arm.teleport_joints(np.asarray(waypoints["arms"][side]["grasp"], dtype=float))
    for _ in range(60):
        SimulationManager.step(steps=1)
    # Place the arm with the old calibrated solve (position-only, like 419/422).
    goal = np.array(
        [
            cfg.pick_x,
            cfg.pick_y,
            cfg.belt_center[2] + cfg.belt_size[2] / 2.0 + float(os.environ.get("FRUIT_GRASP_Z", "0.095")),
        ]
    )
    residual = arm.solve_to(goal, iterations=600, tolerance=0.006, restarts=3, seed=5)[1]
    for _ in range(40):
        SimulationManager.step(steps=1)
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    say(f"jaw at {np.round(jaw, 4).tolist()} residual={residual * 1000:.1f}mm")

    fruits = os.environ.get("PROBE_FRUITS", "apple,strawberry").split(",")
    dzs = [float(v) for v in os.environ.get("PROBE_DZ", "0.02,0.04,0.06,0.08").split(",")]
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    for category in fruits:
        sample = next((s for s in spawner.samples if s.category == category), None)
        if sample is None:
            continue
        d = float(sample.diameter)
        for dz in dzs:
            # Clean order: park the arm at the waypoint first, then present the
            # fruit, then aim the *arm* so the jaw centre is `dz` above it.
            arm.teleport_joints(np.asarray(waypoints["arms"][side]["grasp"], dtype=float))
            for _ in range(60):
                arm.set_gripper(arm.OPEN)
                SimulationManager.step(steps=1)
            spawner.place(sample, np.array([cfg.pick_x, cfg.pick_y, belt_top + d / 2.0]))
            sample.held = True
            if os.environ.get("PROBE_BELT", "run") == "stop" and scene.belt is not None:
                # `stop()` ramps and only takes effect inside `Conveyor.step`,
                # which this probe never calls; `hold()` applies immediately.
                scene.belt.hold()
            for _ in range(30):
                arm.set_gripper(arm.OPEN)
                SimulationManager.step(steps=1)
            arm.sync_command_to_measured()
            # Aim at where the fruit actually is: the pipeline measures it, and
            # a lumpy strawberry settles a centimetre or two off the mark.
            fruit0 = np.asarray(spawner.position(sample), dtype=float)
            goal = fruit0 + np.array([0.0, 0.0, float(dz)])
            arm.solve_to(goal, iterations=600, tolerance=0.006, restarts=3, seed=5)
            for tick in range(40):
                # The asset's own finger drive targets 0 (closed) with a 10 N
                # limit, so an uncommanded gripper creeps shut. Keep it open
                # until the close actually starts.
                arm.set_gripper(arm.OPEN)
                SimulationManager.step(steps=1)
            fruit = np.asarray(spawner.position(sample), dtype=float)
            jaw_now = np.asarray(arm.jaw_centre(), dtype=float)
            trace = os.environ.get("PROBE_TRACE", "0") == "1"
            close_steps = int(os.environ.get("PROBE_CLOSE_STEPS", "90"))
            # Fully closed target (4 mm): if the fruit does not block, the
            # fingers reach ~10 mm origin separation.
            for step, value in enumerate(np.linspace(arm.OPEN, 0.004, close_steps)):
                arm.set_gripper(float(value))
                SimulationManager.step(steps=2)
                if trace and step % 5 == 0:
                    now = np.asarray(spawner.position(sample), dtype=float)
                    vel = np.asarray(spawner.velocity(sample), dtype=float)
                    say(
                        f"[trace] step={step:2d} cmd={value:.4f} q={arm.dof_positions()[arm.finger_dofs].mean():.4f} "
                        f"sep={arm.jaw_separation() * 100:.2f}cm "
                        f"fruit={np.round(now, 4).tolist()} |d|={np.linalg.norm(now - fruit) * 1000:.1f}mm "
                        f"v={np.round(vel, 3).tolist()}"
                    )
            for step in range(60):
                SimulationManager.step(steps=1)
                if trace and step % 10 == 0:
                    now = np.asarray(spawner.position(sample), dtype=float)
                    vel = np.asarray(spawner.velocity(sample), dtype=float)
                    say(
                        f"[trace] settle step={step:2d} sep={arm.jaw_separation() * 100:.2f}cm "
                        f"fruit={np.round(now, 4).tolist()} |d|={np.linalg.norm(now - fruit) * 1000:.1f}mm "
                        f"v={np.round(vel, 3).tolist()}"
                    )
            sep = arm.jaw_separation()
            q = arm.dof_positions()[arm.finger_dofs].mean()
            stall = (sep - 0.014) * 1000.0
            after = np.asarray(spawner.position(sample), dtype=float)
            fmin, fmax = bounds(
                scene.stage, f"/World/OpenArm/openarm_{side}_left_finger/visuals"
            )
            rmin, _ = bounds(
                scene.stage, f"/World/OpenArm/openarm_{side}_right_finger/visuals"
            )
            say(
                f"[static] {category:10s} d={d * 100:4.1f}cm dz={dz * 100:4.1f}cm "
                f"fruit={np.round(fruit, 4).tolist()} after={np.round(after, 4).tolist()} "
                f"moved={np.linalg.norm(after - fruit) * 1000:.1f}mm "
                f"jaw={np.round(jaw_now, 4).tolist()} "
                f"sep={sep * 100:5.2f}cm q={q:.4f} stall={stall:+5.1f}mm "
                f"Lclose=[{fmin[0]:.3f},{fmax[0]:.3f}] Rclose=[{rmin[0]:.3f}]"
            )
            # Lift straight up and see whether the fruit follows.
            start = np.asarray(arm.jaw_centre(), dtype=float).copy()
            z0 = float(spawner.position(sample)[2])
            for value in np.linspace(0.0, 0.10, 200):
                arm.ik_step(arm.tcp_target_for_jaw(start + np.array([0.0, 0.0, float(value)])))
                SimulationManager.step(steps=1)
            for _ in range(60):
                SimulationManager.step(steps=1)
            lift = float(spawner.position(sample)[2]) - z0
            say(f"[static]   lift={lift * 100:+5.1f}cm")
            for value in np.linspace(0.004, arm.OPEN, 30):
                arm.set_gripper(float(value))
                SimulationManager.step(steps=1)
            arm.sync_command_to_measured()
            arm.teleport_joints(np.asarray(waypoints["arms"][side]["grasp"], dtype=float))
            for _ in range(40):
                SimulationManager.step(steps=1)
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
