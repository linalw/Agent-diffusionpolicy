"""Measure where and how large an object the gripper can actually pinch.

Uses *kinematic* spheres, so the probe is free of every confounder that spoiled
the earlier tests: a kinematic body never sleeps, never gets pushed away and
never slips. Blocking is then a pure question of collision geometry.

For each arm the script:

  1. poses the gripper at the pick point and measures the grasp frame
     (jaw centre, closing axis, approach axis) from the finger links;
  2. sweeps a sphere along the approach axis to find the grip band;
  3. sweeps the sphere diameter to find the usable range;
  4. reports, for every case, the jaw separation the gripper actually reached
     when commanded fully closed (baseline with nothing between the jaws is
     ~1.0 cm, so anything above that means the sphere blocked the fingers).

    $ISAAC_SIM_DIR/python.sh scripts/55_grasp_sweep.py
    FRUIT_WAYPOINTS=configs/waypoints_oriented.json ... to test the new poses
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Gf, UsdGeom, UsdPhysics

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene, _add_physics_material, _set_color
from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

WAYPOINTS = os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json")
CONFIG = json.load(open(WAYPOINTS, encoding="utf-8"))
#: Probe diameters [m]. Every size is authored before play() because PhysX does
#: not re-cook a collider whose radius is edited later, and creating or removing
#: prims at runtime invalidates the articulation's physics view.
PROBE_SIZES = (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09)
PARK = Gf.Vec3d(0.0, 0.0, -3.0)


def grasp_frame(arm) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    left_f, right_f = arm.jaw_positions()
    left_f = np.asarray(left_f, dtype=float)
    right_f = np.asarray(right_f, dtype=float)
    centre = (left_f + right_f) / 2.0
    axis = right_f - left_f
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    approach = arm.tcp_position() - centre
    approach = approach / max(float(np.linalg.norm(approach)), 1e-9)
    return centre, axis, approach


def pose_grasp(arm, target, seed_config) -> float:
    """Teleport to the seed pose then refine the pick point with small IK steps."""
    arm.teleport_joints(np.asarray(seed_config, dtype=float))
    for _ in range(80):
        SimulationManager.step(steps=1)
    best = (float(np.linalg.norm(arm.jaw_centre() - target)), arm.joint_positions().copy())
    for _ in range(400):
        arm.ik_step(arm.tcp_target_for_jaw(target))
        SimulationManager.step(steps=1)
        residual = float(np.linalg.norm(arm.jaw_centre() - target))
        if residual < best[0]:
            best = (residual, arm.joint_positions().copy())
    arm.teleport_joints(best[1])
    for _ in range(60):
        SimulationManager.step(steps=1)
    return best[0]


def close(arm, steps: int = 60) -> float:
    for value in np.linspace(arm.finger_opening(), 0.0, 40):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(steps):
        SimulationManager.step(steps=1)
    return arm.jaw_separation()


def open_(arm) -> None:
    for value in np.linspace(arm.finger_opening(), arm.OPEN, 20):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(30):
        SimulationManager.step(steps=1)


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))

    def author_probe(diameter: float) -> str:
        path = f"/World/Probes/Probe_{int(round(diameter * 1000)):03d}"
        sphere = UsdGeom.Sphere.Define(scene.stage, path)
        sphere.GetRadiusAttr().Set(float(diameter) / 2.0)
        xf = UsdGeom.Xformable(sphere)
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(PARK)
        xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        UsdPhysics.CollisionAPI.Apply(sphere.GetPrim())
        body = UsdPhysics.RigidBodyAPI.Apply(sphere.GetPrim())
        body.CreateKinematicEnabledAttr().Set(True)
        _add_physics_material(sphere.GetPrim(), 0.8, 0.8, 0.0)
        _set_color(sphere, (0.1, 0.9, 0.2))
        return path

    paths = {d: author_probe(d) for d in PROBE_SIZES}
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    rigids = {d: RigidPrim(path) for d, path in paths.items()}

    def use(diameter: float, pos) -> None:
        """Park every probe, then place the requested one."""
        for d, rigid in rigids.items():
            if d == diameter:
                rigid.set_world_poses(
                    positions=[np.asarray(pos, dtype=float).tolist()],
                    orientations=[[1.0, 0.0, 0.0, 0.0]],
                )
            else:
                rigid.set_world_poses(
                    positions=[[PARK[0], PARK[1], PARK[2] - d]],
                    orientations=[[1.0, 0.0, 0.0, 0.0]],
                )
        for _ in range(20):
            SimulationManager.step(steps=1)

    say(f"waypoints={WAYPOINTS}")

    for side in ("left", "right"):
        arm = ArmController(scene, side)
        target = np.array([cfg.pick_x, 0.0, belt_top + 0.055])
        residual = pose_grasp(arm, target, CONFIG["arms"][side]["grasp"])
        centre, axis, approach = grasp_frame(arm)
        say(
            f"=== {side}: jaw={np.round(centre, 4).tolist()} residual={residual * 1000:.1f}mm "
            f"axis={np.round(axis, 3).tolist()} approach={np.round(approach, 3).tolist()}"
        )

        use(0.02, (0.0, 0.0, -2.0))
        baseline = close(arm)
        open_(arm)
        say(f"  baseline: nothing between the jaws -> closed separation {baseline * 100:.2f} cm")

        # Sweep along the approach axis: where is the grip band?
        say("  approach-axis sweep (5 cm sphere):")
        for offset in np.arange(-0.07, 0.021, 0.01):
            pos = centre + approach * float(offset)
            use(0.05, pos)
            sep = close(arm)
            blocked = sep > baseline + 0.004
            say(
                f"    offset {offset * 100:+6.1f}cm  pos={np.round(pos, 3).tolist()}  "
                f"sep={sep * 100:5.2f}cm  {'BLOCKED' if blocked else 'passed'}"
            )
            open_(arm)

        # Sweep the diameter at several candidate offsets.
        say("  diameter sweep (sphere centred on the jaw axis):")
        for offset in (-0.03, -0.01, 0.01):
            pos = centre + approach * float(offset)
            row = []
            for diameter in PROBE_SIZES:
                use(diameter, pos)
                sep = close(arm, steps=40)
                blocked = sep > baseline + 0.004
                row.append(f"{diameter * 100:.0f}cm:{sep * 100:4.2f}{'B' if blocked else '.'}")
                open_(arm)
            say(f"    offset {offset * 100:+5.1f}cm  " + "  ".join(row))
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
