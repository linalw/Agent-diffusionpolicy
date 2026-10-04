"""Evaluate the trained diffusion policy in the sorting cell.

    FRUIT_EPISODES=10 scripts/run.sh scripts/60_eval_policy.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

# Set HEADLESS=0 to watch the run in the Isaac Sim GUI.
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

# Raise the fd limit before Isaac Sim starts: this build opens ~2100
# `/dev/nvidiactl` descriptors on the first camera read and dies with
# `dup failed ... Too many open files` at the default limit.
raise_fd_limit()

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.core.rendering_manager import RenderingManager
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.grasp import GraspPrimitive
from fruit_sorting.policy.runtime import PolicyRunner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.tasks import EpisodeResult, PickAndPlaceTask

install_failure_handler("60_eval_policy")

DT = 1.0 / 120.0
EPISODES = int(os.environ.get("FRUIT_EPISODES", "10"))
CHECKPOINT = os.environ.get("FRUIT_CKPT", "checkpoints/policy/policy_best.pt")
#: How many actions of each predicted chunk to execute before re-planning.
EXECUTE_STEPS = int(os.environ.get("FRUIT_EXEC", "4"))
DDIM_STEPS = int(os.environ.get("FRUIT_DDIM", "16"))
#: Hybrid evaluation: let the policy drive the approach for this many control
#: steps, then hand over to the deterministic grasp/carry/place primitives. The
#: policy still decides when it is close enough to attempt, and the contact work
#: is identical to the demonstrations'.
HYBRID = os.environ.get("FRUIT_HYBRID_EVAL", "0") == "1"
APPROACH_STEPS = int(os.environ.get("FRUIT_APPROACH_STEPS", "400"))
#: Print the grasp-time diagnostics (`pads aimed at ... residual/align/hand_gap`)
#: for each hybrid episode. Off by default because it is verbose; on when probing
#: *why* a particular fruit fails, which is the question the per-episode outcome
#: cannot answer (see WORKLOG "the small fruit is the policy loop's reproducible
#: failure").
EVAL_VERBOSE = os.environ.get("FRUIT_EVAL_VERBOSE", "0") == "1"


def place_jaw_target(cfg, bin_index: int) -> np.ndarray:
    """Jaw-centre target above the output conveyor (mirrors PickAndPlaceTask).

    `bin_index` is the output lane: 0 = +Y belt, 1 = -Y belt.
    """
    px, py = cfg.output_belt_drop_points[bin_index]
    return np.array([px, py, cfg.output_place_z])


def carry_and_release(arm, cfg, bin_index: int, steps: int = 220) -> None:
    """Post-grasp primitive: carry the held fruit over the output belt and open.

    The fruit is held by friction, so this only has to move the arm smoothly -
    no attachment, and it is the same Cartesian path the scripted demonstrator
    uses. There is no lowering leg any more: the pads open `output_place_clearance`
    above the moving belt and the fruit drops onto it.
    """
    goal = place_jaw_target(cfg, bin_index)
    for _ in range(steps):
        arm.ik_step(arm.tcp_target_for_jaw(goal))
        SimulationManager.step(steps=1)
        if float(np.linalg.norm(arm.jaw_centre() - goal)) < 0.010:
            break
    for value in np.linspace(arm.finger_opening(), arm.OPEN, 16):
        arm.set_gripper(float(value))
        for _ in range(3):
            SimulationManager.step(steps=1)
    for _ in range(60):
        SimulationManager.step(steps=1)


def main() -> int:
    # `app_utils.update_app(steps=N)` is not a fixed advance - it moves physics by
    # elapsed wall-clock time, and sixty such calls measured 118 ticks on one run and
    # 120 on the next, which was enough to send the whole run down a different branch
    # (WORKLOG "found it: `update_app` is not a fixed step"). `FRUIT_FIXED_STEPPING`
    # (default on) uses the tick-exact API the control loop itself uses, so a hybrid
    # evaluation is reproducible too - which is what makes an A/B on it meaningful.
    fixed_stepping = os.environ.get("FRUIT_FIXED_STEPPING", "1") == "1"

    def advance(steps: int) -> None:
        if fixed_stepping:
            # Physics tick-exact, plus a pump-only update: `update_app` is also what
            # services the camera/sensor callbacks, and dropping it entirely made the
            # evaluator crash on an empty frame (`rgb[0]` was None). `steps=0` pumps
            # without advancing physics.
            SimulationManager.step(steps=steps)
            app_utils.update_app(steps=0)
        else:
            app_utils.update_app(steps=steps)

    if os.environ.get("FRUIT_CAMERA_NO_TAA", "0") == "1":
        # The policy conditions on rendered frames, and rendering is what makes the
        # hybrid loop non-reproducible: with constant frames and a seeded sampler
        # three runs come out bit-identical, with real frames they do not (WORKLOG
        # "the hybrid loop is still not reproducible"). Temporal anti-aliasing
        # accumulates across frames, so it is the first thing to remove when a
        # deterministic frame is wanted.
        import carb

        settings = carb.settings.get_settings()
        settings.set("/rtx/post/taa/enabled", False)
        settings.set("/rtx/post/dlss/enabled", False)
        say("camera: TAA and DLSS disabled for a deterministic frame")

    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "77")))
    spawner.create_pool()
    advance(30)
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
    advance(40)

    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    results = []
    attempts = 0
    while len(results) < EPISODES and attempts < EPISODES * 2:
        attempts += 1
        # Let a fruit reach the upstream part of the belt.
        for _ in range(30):
            advance(1)
            spawner.update(SimulationManager.get_simulation_time())
            spawner.enforce_transport()
        states = [s for s in spawner.state() if s["diameter"] <= cfg.gripper_max_object]
        states = [
            s
            for s in states
            if abs(float(s["position"][0]) - cfg.belt_center[0]) < 0.30
            and cfg.pick_y + 0.15 < float(s["position"][1]) < cfg.spawn_y + 0.05
        ]
        if not states:
            continue
        target = min(states, key=lambda s: float(s["position"][1]))
        sample = next(s for s in spawner.samples if s.index == target["index"])
        grade = target["grade"]
        bin_index = 0 if grade == "A" else 1
        say(
            f"[eval] episode {len(results)}: {target['category']} grade={grade} "
            f"d={target['diameter'] * 100:.1f}cm lane={bin_index}"
        )

        policy.reset()
        # Each demonstration drove one arm; the destination lane identifies it.
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
        advance(20)
        # The grasp primitive indexes (stops) the line; make sure it is running
        # again even if the previous episode ended with it stopped.
        if spawner.belt is not None:
            spawner.belt.start()

        chunk: np.ndarray | None = None
        chunk_index = 0
        handoff_done = False
        grasp_done = False
        hybrid_task = None
        if HYBRID:
            hybrid_task = PickAndPlaceTask(scene, spawner, tactile, cfg)
            hybrid_task.recorder = None
        hybrid_scored = False
        lifted = False
        belt_rest = belt_top + target["diameter"] / 2.0
        for step in range(1500):
            if HYBRID and step % 25 == 0 and step < APPROACH_STEPS:
                pos = np.asarray(spawner.position(sample), dtype=float)
                say(
                    f"[eval]   approach step {step:4d}: fruit=({pos[0]:.3f},{pos[1]:+.3f},"
                    f"{pos[2]:.3f}) z-gap={pos[2] - belt_top:+.3f} "
                    f"tcp={np.round(arms[active].tcp_position(), 3).tolist()}"
                )
            if HYBRID and step >= APPROACH_STEPS:
                # Hand over: the policy has driven the approach, the primitives do
                # the contact work (seat, close, carry, release) exactly as in the
                # demonstrations. Scoring uses the same lift/output-belt criteria.
                # Where did the policy actually leave the arm? This distinguishes
                # "the policy never got close" from "it got close but the hand-over
                # conditions were not met".
                jaw = arms[active].jaw_centre()
                fruit = np.asarray(spawner.position(sample), dtype=float)
                say(
                    f"[eval] approach diagnostic: jaw={np.round(jaw, 3).tolist()} "
                    f"fruit={np.round(fruit, 3).tolist()} "
                    f"dist={float(np.linalg.norm(jaw - fruit)) * 100:.1f}cm "
                    f"fruit_on_belt={'yes' if fruit[2] < belt_top + 0.06 else 'no'}"
                )
                res = EpisodeResult(
                    sample_index=sample.index, category=sample.category,
                    grade=sample.grade, arm=active,
                )
                res = hybrid_task.grasp_carry_place(
                    active, sample, bin_index, res, verbose=EVAL_VERBOSE
                )
                lifted = bool(res.grasped)
                results.append(bool(res.success))
                # Skip the legacy scoring below: it used to run as well, so every
                # hybrid episode was counted twice (a success from the primitives
                # and a spurious failure from the scripted path) - that is where
                # the "3/8" in logs/197-201 came from.
                hybrid_scored = True
                say(
                    f"[eval] episode {len(results) - 1}: hybrid "
                    f"grasped={res.grasped} placed={res.placed} lift={res.peak_lift * 100:+.1f}cm "
                    f"notes={res.notes}"
                )
                break
            # Observation.
            # Match the 30 Hz decimation used when recording the demonstrations.
            if step % 4 == 0:
                # Refresh the camera before reading it. This used to happen by
                # accident, because the loop advanced the app with `update_app`;
                # with tick-exact stepping the sensor must be pumped explicitly, and
                # `RenderingManager.render()` is the project's pattern for that
                # (renders without advancing physics, see `70_record_video.py`).
                RenderingManager.render()
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
                    # `FRUIT_POLICY_FRAME_MODE` isolates the camera from the rest of
                    # the loop. The policy conditions on these frames, and RTX
                    # rendering is not bit-deterministic, so this is the prime
                    # suspect for the hybrid loop's residual run-to-run variation
                    # (WORKLOG: "the hybrid loop is still not reproducible").
                    #   real   - the rendered frame (default)
                    #   cached - the first frame of the episode, reused
                    #   zero   - a constant frame of the same shape
                    # `zero` + `FRUIT_POLICY_SEED` removes *all* input variation, so
                    # if two runs still differ the camera is not the (only) cause.
                    mode = os.environ.get("FRUIT_POLICY_FRAME_MODE", "real")
                    if mode != "real":
                        cached_frames = getattr(main, "_cached_frames", None)
                        if mode == "zero":
                            rgb = np.zeros_like(rgb)
                            depth = np.zeros_like(depth)
                            if mask is not None:
                                mask = np.zeros_like(mask)
                        elif cached_frames is None:
                            main._cached_frames = (
                                rgb.copy(),
                                depth.copy(),
                                None if mask is None else mask.copy(),
                            )
                        else:
                            rgb, depth, mask = cached_frames
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
                if not np.isfinite(np.asarray(action, dtype=np.float64)).all():
                    # A policy can predict a non-finite action (the arm then goes
                    # NaN and nothing else works: logs/195 showed jaw=[nan,nan,nan]).
                    # A real cell guards its joint commands; if the previous chunk
                    # is invalid, drop it, re-plan next step, and if the arm itself
                    # is already invalid, put it back at the ready pose.
                    chunk = None
                    chunk_index = 0
                    if not np.isfinite(
                        np.asarray(scene.robot.get_dof_positions().numpy(), dtype=np.float64)
                    ).all():
                        say(f"[eval] episode {len(results)}: arm state invalid, resetting")
                        arms[active].teleport_joints(
                            np.asarray(waypoints["arms"][active]["ready"], dtype=float)
                        )
                    continue
                scene.robot.set_dof_position_targets([action[:7].tolist()], dof_indices=arm_dofs)
                finger = float(np.clip(action[7], 0.0, 0.044))
                scene.robot.set_dof_position_targets([[finger, finger]], dof_indices=finger_dofs)
                chunk_index += 1

                # Grasp model. The 210-episode dataset was collected with the
                # modelled attach (the OpenArm finger colliders did not hold fruit
                # in this build), so evaluating that policy has to use the same
                # model. FRUIT_NO_ATTACH=1 evaluates a policy trained on the
                # physical demos instead (datasets/demos_physical_v2): the grip is
                # then whatever the pads do by contact, exactly as in training.
                jaw = arms[active].jaw_centre()
                near = (
                    float(np.linalg.norm(np.asarray(spawner.position(sample)[:2]) - jaw[:2]))
                    < 0.06
                )
                if os.environ.get("FRUIT_NO_ATTACH", "0") != "1":
                    if finger < 0.030 and near and not sample.attached:
                        sample.held = True
                        spawner.attach(sample, jaw)
                    elif finger > 0.040 and sample.attached:
                        spawner.detach(sample)
                        sample.held = False
                elif not grasp_done and finger < 0.030 and near:
                    # Deterministic grasp primitive: hand-off, pad alignment,
                    # force-limited close, loading and slip check. The policy
                    # supplies the approach and everything after the grip; the
                    # grip itself is firmware.
                    primitive = GraspPrimitive(
                        cfg, spawner, arms[active], tactile, active, waypoints=waypoints
                    )
                    held = primitive.run(sample)
                    grasp_done = True
                    say(
                        f"[eval] grasp primitive: {'held' if held else 'failed'} "
                        f"({primitive.last_note})"
                    )
                    if held and os.environ.get("FRUIT_PRIMITIVE_CARRY", "0") == "1":
                        # Deterministic carry/place as well: the policy keeps the
                        # approach and the goal selection, the primitives do the
                        # contact work until the dataset is large enough to hand
                        # those skills back to the model.
                        carry_and_release(arms[active], cfg, bin_index)
                        grasp_done = True
                        say(
                            f"[eval] carry primitive: released at "
                            f"{np.round(spawner.position(sample), 3).tolist()}"
                        )

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
            if not handoff_done and float(pos[1]) <= cfg.pick_y + 0.10:
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

        # A fruit that never left the belt used to count as "placed" (`z > belt_top`
        # is true just from resting on it), which inflated every earlier closed-loop
        # number. Success now requires the fruit to have been *lifted clear of the
        # belt* and to have finished on (or next to) its output conveyor.
        if hybrid_scored:
            # The hybrid branch already appended this episode's result.
            continue
        final = np.asarray(spawner.position(sample), dtype=float)
        # "On or next to the output conveyor": the fruit has to be over the belt
        # footprint and off the floor (see `SceneConfig.on_output_belt`). A fruit
        # that bounced off the raised belt to the floor fails the height test.
        on_output = bool(cfg.on_output_belt(final))
        placed = bool(lifted) and on_output
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
