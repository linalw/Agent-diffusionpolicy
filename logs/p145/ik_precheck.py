#!/usr/bin/env python3
"""P145d pre-check: can the IK servo reach the demonstrations' close targets?

The cartesian-delta action is only worth building if the cell's own `ik_step`
reaches the grasp point from the close-start state to better than the catch
tolerance. This loads 20 real (start pose, fruit close position) pairs from
`demos_v11`, teleports the arm to the start, runs the same position-only IK the
scripted close uses for 120 ticks, and reports the achieved jaw error.

    scripts/run.sh logs/p145/ik_precheck.py
"""
from __future__ import annotations

import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"
from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()
simulation_app = SimulationApp({"headless": HEADLESS, "width": 1280, "height": 720})

import numpy as np  # noqa: E402

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import install_failure_handler, say  # noqa: E402
from fruit_sorting.fruits import FruitSpawner  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402
from fruit_sorting.tactile import GripperTactile  # noqa: E402
from fruit_sorting.tasks import PickAndPlaceTask  # noqa: E402

install_failure_handler("ik_precheck")
DT = 1.0 / 120.0
PAD_LIFT = float(os.environ.get("FRUIT_PAD_LIFT", "0.010"))
LIMIT = int(os.environ.get("P145_PAIRS", "20"))


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()
    spawner = FruitSpawner(scene.stage, cfg, seed=3, two_line=False)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    task = PickAndPlaceTask(scene, spawner, tactile, cfg)
    task.go_ready()
    app_utils.update_app(steps=10)

    pairs = []
    for path in sorted(glob.glob("datasets/demos_v11/**/*.npz", recursive=True)):
        data = np.load(path)
        action = np.asarray(data["action"], dtype=np.float32)
        finger = action[:, 7]
        closed = np.flatnonzero(finger < 0.0439)
        if not closed.size:
            continue
        c = int(closed[0])
        start = np.asarray(data["joint_positions"][max(0, c - 5)], dtype=np.float32)
        fruit = np.asarray(data["fruit_position"][c], dtype=np.float32)
        arm = "left" if int(data["goal"][0, 7]) == 0 else "right"
        pairs.append((arm, start, fruit))
        if len(pairs) >= LIMIT:
            break
    say(f"[ik] {len(pairs)} demo pairs")

    errors, holds = [], []
    for index, (side, start, fruit) in enumerate(pairs):
        arm = task.arms[side]
        arm.teleport_joints(np.asarray(start[arm.arm_dofs], dtype=float))
        app_utils.update_app(steps=30)
        arm.capture_hold_pose()
        target = fruit + np.array([0.0, 0.0, 0.070 + PAD_LIFT])
        arm.sync_command_to_measured()
        for _ in range(120):
            arm.ik_step(arm.tcp_target_for_jaw(target))
            app_utils.update_app(steps=1)
        jaw = np.asarray(arm.jaw_centre(), dtype=float)
        errors.append(float(np.linalg.norm(jaw - target)))
        # the measured jaw vs the pad standoff the scripted close uses
        holds.append(float(np.linalg.norm(arm.tcp_position() - arm.tcp_target_for_jaw(target))))
        say(
            f"[ik] pair {index:02d} {side}: target={np.round(target, 3).tolist()} "
            f"jaw={np.round(jaw, 3).tolist()} err={errors[-1] * 1000:.1f}mm "
            f"tcp_err={holds[-1] * 1000:.1f}mm"
        )
    if errors:
        e = np.asarray(errors)
        say(
            f"[ik] jaw error: median {np.median(e) * 1000:.1f} mm  "
            f"p90 {np.percentile(e, 90) * 1000:.1f}  max {e.max() * 1000:.1f}  "
            f"<= 2 mm {int((e <= 0.002).sum())}/{len(e)}  "
            f"<= 20 mm {int((e <= 0.020).sum())}/{len(e)}"
        )
    app_utils.pause()
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
