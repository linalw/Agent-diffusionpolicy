#!/usr/bin/env python3
"""P178: the finger command -> pad span map, per arm. No attempt loop.

The direct cell reads **0 grasps in 31** on the right arm against 21/35 on the
left, with the same latch geometry, and the same close command (`fing=0.0295`)
produces a **different measured span** (69.1 mm right, 77.4 mm left). The span
constants are class-level (`JAW_SEPARATION_OFFSET 0.010`,
`JAW_SEPARATION_PER_JOINT 2.0`), so the two arms cannot differ in arithmetic -
this probe reads what they actually do: one ladder of finger commands per arm,
each held until settled, with the two finger joint positions and the span.

    scripts/run.sh logs/p145/finger_probe.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np  # noqa: E402

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import install_failure_handler, say  # noqa: E402
from fruit_sorting.control import ArmController  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402

install_failure_handler("finger_probe")
DT = 1.0 / 120.0
SETTLE = int(os.environ.get("FRUIT_FPROBE_SETTLE", "40"))
LADDER = [float(v) for v in os.environ.get(
    "FRUIT_FPROBE_LADDER", "0.044,0.040,0.035,0.030,0.025,0.020,0.015,0.010"
).split(",")]


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    scene.start(physics_dt=DT, warmup_steps=60)
    arms = {s: ArmController(scene, s) for s in ("left", "right")}
    say(f"[fprobe] arms built; finger dofs left={arms['left'].finger_dofs} "
        f"right={arms['right'].finger_dofs}")
    for side, arm in arms.items():
        say(f"[fprobe] {side}: OPEN={arm.OPEN} CLOSED={getattr(arm, 'CLOSED', '?')} "
            f"offset={arm.JAW_SEPARATION_OFFSET} per_joint={arm.JAW_SEPARATION_PER_JOINT} "
            f"face={arm.FINGER_FACE_OFFSET}")
    rows = []
    for value in LADDER:
        for side, arm in arms.items():
            arm.set_gripper(float(value))
        for _ in range(SETTLE):
            scene.step()
        for side, arm in arms.items():
            q = np.asarray(arm.dof_positions(), dtype=float)
            qf = q[list(arm.finger_dofs)]
            sep = float(arm.jaw_separation())
            want = arm.JAW_SEPARATION_PER_JOINT * float(value) + arm.JAW_SEPARATION_OFFSET
            rows.append((float(value), side, qf[0], qf[1], sep, want))
            say(f"[fprobe] cmd={value:.4f} {side:5s} j1={qf[0]:+.4f} j2={qf[1]:+.4f} "
                f"sep={sep * 1000:7.2f}mm want={want * 1000:7.2f}mm "
                f"err={(sep - want) * 1000:+7.2f}mm")
    # the same command on both arms, the number the direct cell compares
    say("")
    for value in (0.0295, 0.0250):
        for side, arm in arms.items():
            arm.set_gripper(float(value))
        for _ in range(SETTLE):
            scene.step()
        a = {s: float(arms[s].jaw_separation()) * 1000 for s in arms}
        say(f"[fprobe] SEP@cmd={value:.4f}: left={a['left']:.2f}mm right={a['right']:.2f}mm "
            f"delta={a['right'] - a['left']:+.2f}mm")
    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
