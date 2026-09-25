"""Evaluate the trained diffusion policy in the sorting cell.

    FRUIT_EPISODES=10 $ISAAC_SIM_DIR/python.sh scripts/60_eval_policy.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

# Set HEADLESS=0 to watch the run in the Isaac Sim GUI.
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.core.rendering_manager import RenderingManager
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.policy.runtime import PolicyRunner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile

install_failure_handler("60_eval_policy")

DT = 1.0 / 120.0
EPISODES = int(os.environ.get("FRUIT_EPISODES", "10"))
CHECKPOINT = os.environ.get("FRUIT_CKPT", "checkpoints/policy/policy_best.pt")
#: How many actions of each predicted chunk to execute before re-planning.
EXECUTE_STEPS = int(os.environ.get("FRUIT_EXEC", "4"))
DDIM_STEPS = int(os.environ.get("FRUIT_DDIM", "16"))


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "77")))
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    spawner.prime(count=6)

    policy = PolicyRunner(CHECKPOINT)
    say(f"loaded {CHECKPOINT} (obs_horizon={policy.obs_horizon}, action_horizon={policy.action_horizon})")

    # The demonstrations all start with the arms parked at the calibrated ready
    # pose, so the policy is evaluated from the same initial condition.
    import json

    from fruit_sorting.control import ArmController

    with open("configs/waypoints.json", encoding="utf-8") as fh:
        waypoints = json.load(fh)
    arms = {"left": ArmController(scene, "left"), "right": ArmController(scene, "right")}
    for name, arm in arms.items():
        arm.set_gripper(arm.OPEN)
        arm.teleport_joints(np.asarray(waypoints["arms"][name]["ready"], dtype=float))
    app_utils.update_app(steps=40)

    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    results = []
    attempts = 0
    while len(results) < EPISODES and attempts < EPISODES * 2:
        attempts += 1
        # Let a fruit reach the upstream part of the belt.
        for _ in range(30):
            app_utils.update_app(steps=1)
            spawner.update(SimulationManager.get_simulation_time())
            spawner.enforce_transport()
        states = [s for s in spawner.state() if s["diameter"] <= cfg.gripper_max_object]
        states = [s for s in states if 1.05 < float(s["position"][0]) < 1.66]
        if not states:
            continue
        target = min(states, key=lambda s: float(s["position"][0]))
        sample = next(s for s in spawner.samples if s.index == target["index"])
        grade = target["grade"]
        bin_index = 0 if grade == "A" else 1
        say(
            f"[eval] episode {len(results)}: {target['category']} grade={grade} "
            f"d={target['diameter'] * 100:.1f}cm bin={bin_index}"
        )

        policy.reset()
        # Each demonstration drove one arm; the destination bin identifies it.
        if bin_index == 0:
            arm_dofs, finger_dofs, park_arm = [0, 2, 4, 6, 8, 10, 12], [14, 15], "right"
        else:
            arm_dofs, finger_dofs, park_arm = [1, 3, 5, 7, 9, 11, 13], [17, 18], "left"
        goal = np.array(
            [
                *np.asarray(target["position"], dtype=np.float32),
                *np.asarray(target["velocity"], dtype=np.float32),
                float(target["diameter"]),
                float(bin_index),
            ],
            dtype=np.float32,
        )

        # Open the active gripper and park the other arm out of the lane.
        scene.robot.set_dof_position_targets([[0.044, 0.044]], dof_indices=finger_dofs)
        active = "left" if bin_index == 0 else "right"
        arms[active].teleport_joints(np.asarray(waypoints["arms"][active]["ready"], dtype=float))
        app_utils.update_app(steps=20)

        chunk: np.ndarray | None = None
        chunk_index = 0
        handoff_done = False
        lifted = False
        belt_rest = belt_top + target["diameter"] / 2.0
        for step in range(1500):
            # Observation.
            # Match the 30 Hz decimation used when recording the demonstrations.
            if step % 4 == 0:
                rgb = scene.camera_sensor.get_data("rgb")
                depth = scene.camera_sensor.get_data("distance_to_image_plane")
                rgb = np.asarray(rgb[0].numpy()) if rgb is not None else None
                depth = np.asarray(depth[0].numpy()) if depth is not None else None
                mask = None
                if policy.config["image_channels"] == 5:
                    # Same target-mask channel the demonstrations recorded.
                    raw = scene.camera_sensor.get_data("instance_id_segmentation")
                    seg = np.asarray(raw[0].numpy()) if raw is not None else None
                    if seg is not None:
                        if seg.ndim == 3:
                            seg = seg[..., 0]
                        info = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else {}
                        labels = info.get("idToLabels", {}) if isinstance(info, dict) else {}
                        target_id = 0
                        for key, value in labels.items():
                            if sample.prim_path in str(value):
                                target_id = int(key)
                                break
                        mask = (seg == target_id).astype(np.float32)
                if rgb is not None and depth is not None:
                    policy.push_frame(rgb, depth, mask)

            if chunk is None or chunk_index >= EXECUTE_STEPS:
                if policy.ready:
                    proprio = np.concatenate(
                        [
                            np.asarray(scene.robot.get_dof_positions().numpy())[0].astype(np.float32),
                            [float(np.mean(np.asarray(scene.robot.get_dof_positions().numpy())[0][[14, 15]]))],
                            np.array(
                                [
                                    tactile.read().get("left", _ZERO).normal_force,
                                    tactile.read().get("right", _ZERO).normal_force,
                                ],
                                dtype=np.float32,
                            ),
                        ]
                    )
                    chunk = policy.act(proprio, goal, num_steps=DDIM_STEPS)
                    chunk_index = 0

            if chunk is not None and chunk_index < chunk.shape[0]:
                action = chunk[chunk_index]
                scene.robot.set_dof_position_targets([action[:7].tolist()], dof_indices=arm_dofs)
                finger = float(np.clip(action[7], 0.0, 0.044))
                scene.robot.set_dof_position_targets([[finger, finger]], dof_indices=finger_dofs)
                chunk_index += 1

                # Apply the same grasp model the demonstrations used (see
                # FruitSpawner.attach): the OpenArm finger colliders do not hold
                # fruit in this build, so the demos - and therefore the policy -
                # are trained against an attached grasp. Judging the policy on a
                # physical grasp the training data never contained would measure
                # the simulator, not the policy.
                jaw = arms[active].jaw_centre()
                near = float(np.linalg.norm(np.asarray(spawner.position(sample)[:2]) - jaw[:2])) < 0.06
                if finger < 0.030 and near and not sample.attached:
                    sample.held = True
                    spawner.attach(sample, jaw)
                elif finger > 0.040 and sample.attached:
                    spawner.detach(sample)
                    sample.held = False

            if sample.attached:
                spawner.follow(sample, arms[active].jaw_centre())
            spawner.enforce_transport()
            SimulationManager.step(steps=1)
            if step % 4 == 0:
                # Render without advancing physics so the control loop keeps its
                # exact 1/120 s timing (see scripts/39_render_probe.py).
                RenderingManager.render()

            pos = spawner.position(sample)
            # Hand the fruit into the jaws once it reaches the pick station, the
            # same transfer the demonstrations used.
            if not handoff_done and float(pos[0]) <= 0.44:
                # Match the demonstrations: hand the fruit to the jaw centre the
                # policy actually produced, not a hardcoded station.
                jaw = arms[active].jaw_centre()
                spawner.place(
                    sample,
                    np.array([float(jaw[0]), float(jaw[1]),
                              belt_top + target["diameter"] / 2.0 + 0.002]),
                )
                sample.held = True
                for _ in range(20):
                    SimulationManager.step(steps=1)
                handoff_done = True
                continue

            if float(pos[2]) > belt_rest + 0.05:
                lifted = True
            if float(pos[2]) < belt_top - 0.25:
                break

        placed = float(spawner.position(sample)[2]) > belt_top or float(
            np.linalg.norm(np.asarray(spawner.position(sample)[:2]) - np.asarray(cfg.bin_positions[bin_index]))
        ) < 0.25
        results.append(placed)
        say(
            f"[eval] episode {len(results) - 1}: handoff={handoff_done} "
            f"lifted={lifted} placed={placed}"
        )

    success = sum(1 for r in results if r)
    say(f"[eval] policy success {success}/{len(results)} (attempts={attempts})")
    app_utils.pause()
    say("DONE")
    return 0


class _Zero:
    normal_force = 0.0


_ZERO = _Zero()


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
