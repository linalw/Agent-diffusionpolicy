#!/usr/bin/env python3
"""P227i: why the Panda's finger joints do not track the position target.

    FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/finger_probe.py

P227h measured `set_gripper(0.000 .. 0.040)` leaving the two finger joints at
0.0164-0.0195 m (jaw 32.9-38.5 mm) on the Isaac Franka asset, while the arm
solves fine. The separation law itself is right (sep = 2 q at the measured
pairs), so the question is the **drive**: is it authored, is it applied, what
cap does the live articulation carry, and does any of (target on both joints,
joint 1 only, opposed commands, the asset's own gains, a raised cap) make the
joints move?

Read-only on `src/`: this probe only reads the stage and drives the
articulation, so it cannot change the shipped build.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import numpy as np  # noqa: E402
from pxr import UsdPhysics  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.control import ArmController  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402


def say(text: str) -> None:
    print(f"[fruit] [fp] {text}", flush=True)


def dump_stage(stage) -> None:
    say("--- stage: prims whose name mentions finger ---")
    for prim in stage.Traverse():
        name = prim.GetName()
        if "finger" not in name.lower():
            continue
        type_name = prim.GetTypeName()
        path = prim.GetPath()
        say(f"prim {path} type={type_name}")
        schemas = [s for s in prim.GetAppliedSchemas()]
        if schemas:
            say(f"  applied schemas: {schemas}")
        for attr in prim.GetAttributes():
            attr_name = attr.GetName()
            if attr_name.startswith("drive:") or "mimic" in attr_name.lower() or attr_name.startswith("physx"):
                value = attr.Get()
                say(f"  attr {attr_name} = {value!r}")
        # the joint's own geometry attributes
        for attr_name in ("physics:axis", "physics:localPos0", "physics:localPos1", "physics:lowerLimit", "physics:upperLimit"):
            attr = prim.GetAttribute(attr_name)
            if attr and attr.HasAuthoredValue():
                say(f"  {attr_name} = {attr.Get()!r}")


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=30)
    stage = scene.stage
    dump_stage(stage)

    arm = ArmController(scene, "left")
    names = list(arm.robot.dof_names)
    say(f"dof_names={names}")
    gains = arm.robot.get_dof_gains()
    # `get_dof_gains` returns (stiffness, damping) each shaped (1, n_dofs)
    k_arr = np.asarray(gains[0].numpy())[0]
    c_arr = np.asarray(gains[1].numpy())[0]
    caps = np.asarray(arm.robot.get_dof_max_efforts().numpy())[0]
    for index, name in enumerate(names):
        say(
            f"dof {index:2d} {name:22s} k={k_arr[index]:12.3f} c={c_arr[index]:12.3f} "
            f"cap={caps[index]:9.3f} lo={np.asarray(arm.robot.get_dof_limits()[0].numpy())[0][index]:+.4f} "
            f"hi={np.asarray(arm.robot.get_dof_limits()[1].numpy())[0][index]:+.4f}"
        )
    say(f"finger_dofs={arm.finger_dofs} arm_dofs={arm.arm_dofs}")

    f = list(arm.finger_dofs)
    q0 = np.asarray(arm.joint_positions(), dtype=float)

    def measure() -> tuple[np.ndarray, float]:
        dof = np.asarray(arm.robot.get_dof_positions().numpy())[0]
        return dof[f], float(arm.jaw_separation())

    def run_cell(label: str, k: float, c: float, cap: float | None,
                 targets, steps: int = 90) -> None:
        arm.teleport_joints(np.asarray(q0, dtype=float))
        scene.step(10)
        if k > 0.0:
            arm.robot.set_dof_gains(k, c, dof_indices=f)
        if cap is not None:
            arm.robot.set_dof_max_efforts(cap, dof_indices=f)
        # report what the live view now carries
        g = arm.robot.get_dof_gains()
        live_k = np.asarray(g[0].numpy())[0][f]
        live_c = np.asarray(g[1].numpy())[0][f]
        live_cap = np.asarray(arm.robot.get_dof_max_efforts().numpy())[0][f]
        for q in targets:
            if isinstance(q, (list, tuple)):
                arm.robot.set_dof_position_targets([[float(v) for v in q]], dof_indices=f)
                text = f"targets={q}"
            else:
                arm.set_gripper(float(q))
                text = f"set_gripper({q:.3f})"
            scene.step(steps)
            qs, sep = measure()
            say(
                f"{label} {text:34s} -> q={np.array2string(qs, precision=4)} "
                f"jaw={sep * 1000:6.1f} mm"
            )
        say(f"{label} live k={live_k} c={live_c} cap={live_cap}")

    pos = (0.0, 0.010, 0.020, 0.030, 0.040)
    run_cell("C0-shipped ", 100000.0, 2000.0, None, pos)
    run_cell("C1-cap60   ", 100000.0, 2000.0, 60.0, pos)
    run_cell("C2-cap300  ", 100000.0, 2000.0, 300.0, pos)
    run_cell("C3-j1only  ", 100000.0, 2000.0, 60.0, [(0.0, 0.0), (0.04, 0.0), (0.0, 0.04)])
    run_cell("C4-opposed ", 100000.0, 2000.0, 60.0, [(-0.04, 0.04), (0.04, -0.04)])
    run_cell("C5-asset   ", 1000000.0, 100.0, None, pos)
    run_cell("C6-noGain  ", 0.0, 0.0, None, pos)
    # how long does a step response take when the drive does act?
    arm.teleport_joints(np.asarray(q0, dtype=float))
    arm.robot.set_dof_gains(100000.0, 2000.0, dof_indices=f)
    arm.robot.set_dof_max_efforts(60.0, dof_indices=f)
    arm.set_gripper(0.040)
    elapsed = 0
    for n in (1, 2, 4, 8, 16, 32, 64, 120):
        scene.step(n - elapsed)
        elapsed = n
        qs, sep = measure()
        say(f"T40 tick~{n:3d} q={np.array2string(qs, precision=4)} jaw={sep * 1000:6.1f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
