"""Give the left arm the mirrored version of the right arm's grasp pose.

The orientation term of ``ik_step`` turns out to have no effect at all in this
build (see ``logs/53_orient.log``: the commanded 20 deg rotation never moves),
so the wrist orientation has to come from the *joint configuration* instead.

The two arms are mirror-symmetric hardware, so the right arm's calibrated grasp
configuration, mirrored across the robot's symmetry plane, is a valid left-arm
grasp configuration. Which joints flip sign is not documented, so this script
tries all 128 sign patterns and scores each candidate on physical quantities
that are actually measurable:

  * jaw centre distance to the pick point
  * jaw closing axis ``u`` (from the two finger links)
  * approach axis ``a`` (from the jaw centre towards the TCP)

    $ISAAC_SIM_DIR/python.sh scripts/54_mirror_waypoints.py
"""

from __future__ import annotations

import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

V1 = json.load(open("configs/waypoints.json", encoding="utf-8"))
OUT = "configs/waypoints_oriented.json"
MIRROR = np.diag([1.0, -1.0, 1.0])


def grasp_frame(arm) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(jaw centre, closing axis, approach axis) for the current pose."""
    left_f, right_f = arm.jaw_positions()
    left_f = np.asarray(left_f, dtype=float)
    right_f = np.asarray(right_f, dtype=float)
    centre = (left_f + right_f) / 2.0
    axis = right_f - left_f
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    approach = arm.tcp_position() - centre
    approach = approach / max(float(np.linalg.norm(approach)), 1e-9)
    return centre, axis, approach


def score(arm, target_centre, target_axis, target_approach) -> float:
    centre, axis, approach = grasp_frame(arm)
    pos_err = float(np.linalg.norm(centre - target_centre))
    axis_err = float(np.linalg.norm(axis - target_axis))
    appr_err = float(np.linalg.norm(approach - target_approach))
    return pos_err + 0.05 * axis_err + 0.05 * appr_err


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    pick = np.array([cfg.pick_x, 0.0, belt_top + 0.055])

    right = ArmController(scene, "right")
    right.teleport_joints(np.asarray(V1["arms"]["right"]["grasp"], dtype=float))
    for _ in range(90):
        SimulationManager.step(steps=1)
    c_r, u_r, a_r = grasp_frame(right)
    say(f"right v1 grasp: centre={np.round(c_r, 4).tolist()} "
        f"axis={np.round(u_r, 3).tolist()} approach={np.round(a_r, 3).tolist()}")
    jac = right.robot.get_jacobian_matrices().numpy()[0, right.tcp_jacobian_index]
    say(f"right tcp jacobian: |linear|={np.linalg.norm(jac[0:3, right.arm_dofs]):.3f} "
        f"|angular|={np.linalg.norm(jac[3:6, right.arm_dofs]):.3f}")

    target_centre = MIRROR @ c_r
    target_axis = MIRROR @ u_r
    target_approach = MIRROR @ a_r
    say(f"left target   : centre={np.round(target_centre, 4).tolist()} "
        f"axis={np.round(target_axis, 3).tolist()} "
        f"approach={np.round(target_approach, 3).tolist()}")

    left = ArmController(scene, "left")
    base = np.asarray(V1["arms"]["right"]["grasp"], dtype=float)
    # A mirrored configuration very likely flips the sign of the second joint and
    # of the wrist; brute force is cheap because a teleport is instantaneous.
    candidates = []
    for signs in itertools.product((1.0, -1.0), repeat=7):
        config = base * np.asarray(signs)
        left.teleport_joints(config, settle=0)
        left._q_cmd = None  # noqa: SLF001 - keep the integrator honest
        candidates.append((score(left, target_centre, target_axis, target_approach), signs, config.copy()))
    candidates.sort(key=lambda item: item[0])
    for sc, signs, config in candidates[:5]:
        left.teleport_joints(config, settle=0)
        c, u, a = grasp_frame(left)
        say(f"  score={sc:.4f} signs={signs} centre={np.round(c, 4).tolist()} "
            f"axis={np.round(u, 3).tolist()} approach={np.round(a, 3).tolist()}")

    best_score, best_signs, best_config = candidates[0]
    left.teleport_joints(best_config)
    for _ in range(60):
        SimulationManager.step(steps=1)
    say(f"best mirror config score={best_score:.4f} signs={tuple(int(s) for s in best_signs)}")

    # Refine the pick point with the *position-only* integrator, in small steps so
    # the wrist cannot wander, and keep whichever iterate scores best.
    arm_hold = ArmController(scene, "left", max_step=0.05)
    arm_hold.teleport_joints(best_config)
    best = (score(arm_hold, target_centre, target_axis, target_approach), arm_hold.joint_positions().copy())
    for step in range(900):
        arm_hold.ik_step(arm_hold.tcp_target_for_jaw(pick))
        SimulationManager.step(steps=1)
        if step % 25 == 0:
            current = score(arm_hold, target_centre, target_axis, target_approach)
            if current < best[0]:
                best = (current, arm_hold.joint_positions().copy())
    arm_hold.teleport_joints(best[1])
    for _ in range(40):
        SimulationManager.step(steps=1)
    c, u, a = grasp_frame(arm_hold)
    say(f"left grasp after refine: score={best[0]:.4f} centre={np.round(c, 4).tolist()} "
        f"axis={np.round(u, 3).tolist()} approach={np.round(a, 3).tolist()}")
    say(f"   centre error={np.linalg.norm(c - target_centre) * 1000:.1f}mm "
        f"axis error={np.linalg.norm(u - target_axis):.3f} "
        f"approach error={np.linalg.norm(a - target_approach):.3f}")

    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else json.loads(json.dumps(V1))
    out["arms"]["left"]["grasp"] = np.asarray(best[1], dtype=float).round(6).tolist()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    say(f"wrote left grasp into {OUT}")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
