"""Attribute the physical-grasp failure: sleeping fruit vs mesh collider.

An earlier probe found that the fingers close straight through a FruitSpawner
fruit while a hand-authored analytic sphere of the same size blocks them
(``logs/44_nophysmat.log``). Two candidate causes remain, and this script
separates them by holding everything else fixed - same fruit, same pose, same
close command, same lift:

  A  mesh fruit, default PhysX sleep settings   (today's behaviour)
  B  mesh fruit, sleep threshold 0              (body can never sleep)
  C  mesh fruit with its mesh collider disabled and an analytic sphere proxy
     child collider                              (visual mesh + collision proxy)
  D  sphere proxy *and* sleep threshold 0
  E  a hand-authored analytic sphere rigid body of the same diameter (control)

Each case places the body at the fruit's resting height on the belt, closes the
gripper to a 3 % squeeze, lets the contact settle, then lifts the hand 15 cm with
smooth Cartesian IK and reports how far the body followed.

    $ISAAC_SIM_DIR/python.sh scripts/48_collision_proxy.py
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
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene, _add_physics_material
from fruit_sorting.tactile import GripperTactile
from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

CONFIG = json.load(open("configs/waypoints.json", encoding="utf-8"))

#: Jaw centre height above the belt surface at the pick pose (see
#: PickAndPlaceTask.jaw_target("grasp") and scripts/45_grasp_height_test.py).
JAW_ABOVE_BELT = 0.055
LIFT_HEIGHT = 0.15
SQUEEZE = 0.97


def prim_collision(stage, path: str):
    prim = stage.GetPrimAtPath(path)
    return UsdPhysics.CollisionAPI(prim) if prim.IsValid() else None


class Rig:
    """One test body with a switchable collider / sleep configuration."""

    def __init__(self, stage, sample, diameter: float):
        self.stage = stage
        self.sample = sample
        self.diameter = diameter
        self.path = sample.prim_path
        self.proxy_path = f"{sample.prim_path}/proxy"
        self.rigid = RigidPrim(sample.prim_path)
        self.mesh_collision = prim_collision(stage, self.path)
        self._default_sleep = float(self.rigid.get_sleep_thresholds().numpy()[0][0])

    def rebind(self, path: str) -> None:
        """Point this rig at a different prim (used for the control sphere)."""
        self.path = path
        self.proxy_path = f"{path}/proxy"
        self.rigid = RigidPrim(path)
        self.mesh_collision = prim_collision(self.stage, path)
        self._default_sleep = float(self.rigid.get_sleep_thresholds().numpy()[0][0])

    def configure(self, mesh: bool, proxy: bool, awake: bool) -> None:
        self.stage.RemovePrim(self.proxy_path)
        if self.mesh_collision is not None:
            self.mesh_collision.GetCollisionEnabledAttr().Set(bool(mesh))
        if proxy:
            sphere = UsdGeom.Sphere.Define(self.stage, self.proxy_path)
            sphere.GetRadiusAttr().Set(float(self.diameter / 2.0))
            UsdPhysics.CollisionAPI.Apply(sphere.GetPrim())
        self.rigid.set_sleep_thresholds([0.0 if awake else self._default_sleep])

    def place(self, position) -> None:
        self.rigid.set_world_poses(
            positions=[np.asarray(position, dtype=float).tolist()],
            orientations=[[1.0, 0.0, 0.0, 0.0]],
        )
        self.rigid.set_velocities(
            linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]]
        )

    def position(self) -> np.ndarray:
        pos = self.rigid.get_world_poses()[0]
        return np.asarray(pos.numpy() if hasattr(pos, "numpy") else pos)[0]


def close_gripper(arm, value: float) -> None:
    for step in np.linspace(arm.OPEN, value, 30):
        arm.set_gripper(float(step))
        SimulationManager.step(steps=2)
    for _ in range(90):
        SimulationManager.step(steps=1)


def open_gripper(arm) -> None:
    for step in np.linspace(arm.finger_opening(), arm.OPEN, 16):
        arm.set_gripper(float(step))
        SimulationManager.step(steps=2)
    for _ in range(20):
        SimulationManager.step(steps=1)


def reset_arm(arm, pose, jaw_target) -> None:
    """Park at the calibrated pose, then IK-refine onto the actual grasp target.

    The raw waypoint puts the jaw 5.5 cm above the grasp target, so skipping the
    IK solve makes the fingers close *above* the fruit and every contact test
    reads zero - that mistake invalidated the first run of this probe.
    """
    arm.teleport_joints(np.asarray(pose, dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(40):
        SimulationManager.step(steps=1)
    _, residual = arm.solve_to(np.asarray(jaw_target, dtype=float), iterations=600, tolerance=0.004)
    for _ in range(20):
        SimulationManager.step(steps=1)
    arm.capture_hold_pose()
    return residual


def lift(arm, base_target: np.ndarray, height: float, steps: int = 300) -> None:
    """Smooth Cartesian lift so a friction grip is not shocked off."""
    goal = np.array(base_target, dtype=float) + [0.0, 0.0, height]
    for i in range(steps):
        target = np.array(base_target, dtype=float)
        target[2] += height * (i + 1) / steps
        arm.ik_step(arm.tcp_target_for_jaw(target))
        SimulationManager.step(steps=1)
    for _ in range(60):
        arm.ik_step(arm.tcp_target_for_jaw(goal))
        SimulationManager.step(steps=1)


def run_case(label, rig, arm, tactile, cfg, mesh, proxy, awake) -> bool:
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    rig.configure(mesh=mesh, proxy=proxy, awake=awake)
    base_target = np.array([cfg.pick_x, 0.0, belt_top + JAW_ABOVE_BELT])
    residual = reset_arm(arm, CONFIG["arms"]["left"]["grasp"], base_target)
    jaw = arm.jaw_centre().copy()
    rest = np.array([float(jaw[0]), float(jaw[1]), belt_top + rig.diameter / 2.0])
    rig.place(rest)
    for _ in range(40):
        SimulationManager.step(steps=1)

    placed = rig.position().copy()
    grip = arm.gripper_value_for_separation(rig.diameter * SQUEEZE)
    gap_open = arm.jaw_separation()
    close_gripper(arm, grip)
    gap_closed = arm.jaw_separation()
    after_close = rig.position().copy()
    reading = tactile.read()["left"]

    lift(arm, base_target, LIFT_HEIGHT)
    after_lift = rig.position().copy()
    jaw_lift = float(arm.jaw_centre()[2] - jaw[2])
    followed = float(after_lift[2] - placed[2])
    held = followed > 0.05

    say(
        f"{label:18s} | jaw_res={residual * 1000:4.1f}mm jaw_z={jaw[2]:.4f} "
        f"fruit_z={rest[2]:.4f} dz={(jaw[2] - rest[2]) * 100:4.1f}cm d={rig.diameter * 100:4.2f}cm "
        f"cmd={grip:.4f} "
        f"gap {gap_open * 100:4.2f}->{gap_closed * 100:4.2f}cm | "
        f"force {reading.normal_force:6.2f}N n={reading.contact_count} | "
        f"close drift ({(after_close[0] - placed[0]) * 1000:+5.1f},"
        f"{(after_close[1] - placed[1]) * 1000:+5.1f})mm | "
        f"jaw {jaw_lift * 100:+5.1f}cm fruit {followed * 100:+5.1f}cm | "
        f"{'HELD' if held else 'slipped'}"
    )
    open_gripper(arm)
    rig.configure(mesh=True, proxy=False, awake=False)
    return held


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    spawner = FruitSpawner(scene.stage, cfg, seed=4)
    spawner.create_pool()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    tactile.refresh()
    spawner.refresh_rigids()
    spawner.reset()

    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(f"belt_top={belt_top:.3f} m, finger span = jaw_z-0.076 .. jaw_z+0.031 m")

    # Closest sample to 5 cm so every case uses the same fruit.
    sample = min(spawner.samples, key=lambda s: abs(s.diameter - 0.05))
    say(
        f"using {sample.category} sample[{sample.index}] d={sample.diameter * 100:.2f}cm "
        f"m={sample.mass * 1000:.0f}g mu={sample.friction:.2f}"
    )
    rig = Rig(scene.stage, sample, sample.diameter)

    arm = ArmController(scene, "left")
    residual = reset_arm(
        arm, CONFIG["arms"]["left"]["grasp"], [cfg.pick_x, 0.0, belt_top + JAW_ABOVE_BELT]
    )
    say(f"pick pose jaw={np.round(arm.jaw_centre(), 4).tolist()} residual={residual * 1000:.1f}mm")

    cases = (
        ("A mesh", dict(mesh=True, proxy=False, awake=False)),
        ("B mesh+awake", dict(mesh=True, proxy=False, awake=True)),
        ("C sphere proxy", dict(mesh=False, proxy=True, awake=False)),
        ("D proxy+awake", dict(mesh=False, proxy=True, awake=True)),
    )
    results = {}
    for label, kwargs in cases:
        results[label] = run_case(label, rig, arm, tactile, cfg, **kwargs)

    # Control: a plain analytic sphere rigid body of the same diameter.
    sphere = UsdGeom.Sphere.Define(scene.stage, "/World/ControlSphere")
    sphere.GetRadiusAttr().Set(sample.diameter / 2.0)
    xf = UsdGeom.Xformable(sphere)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, -5.0))
    UsdPhysics.CollisionAPI.Apply(sphere.GetPrim())
    UsdPhysics.RigidBodyAPI.Apply(sphere.GetPrim())
    UsdPhysics.MassAPI.Apply(sphere.GetPrim()).CreateMassAttr().Set(sample.mass)
    _add_physics_material(sphere.GetPrim(), sample.friction, sample.friction, 0.1)
    control = Rig(scene.stage, sample, sample.diameter)
    control.rebind("/World/ControlSphere")
    results["E analytic sphere"] = run_case(
        "E analytic sphere", control, arm, tactile, cfg, mesh=True, proxy=False, awake=False
    )

    say("---- summary ----")
    for label, held in results.items():
        say(f"{label:18s} {'HELD' if held else 'slipped'}")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
