"""Scripted pick-and-place on the moving belt.

The scripted policy plays the role of the trained diffusion policy for now: it
produces the demonstration data and gives the simulation something to measure
against.

Strategy for a moving target: instead of chasing the fruit, the arm moves to the
predicted intercept point upstream of the fruit, waits there, descends as the
fruit arrives, closes the gripper, lifts, and carries the fruit to its bin.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.rendering_manager import RenderingManager

from .common import say, to_numpy
from .control import ArmController
from .dataset import EpisodeMeta, EpisodeRecorder, camera_observation
from .tactile import TactileReading

_EMPTY_TACTILE = TactileReading(side="none")


@dataclass
class EpisodeResult:
    """Outcome of one scripted pick-and-place attempt."""

    sample_index: int
    category: str = ""
    grade: str = ""
    arm: str = ""
    grasped: bool = False
    placed: bool = False
    max_tactile_force: float = 0.0
    peak_lift: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.grasped and self.placed


class PickAndPlaceTask:
    """State-machine picker used for scripted demonstrations."""

    APPROACH_HEIGHT = 0.10
    GRASP_Z_OFFSET = 0.003
    LIFT_HEIGHT = 0.16
    BIN_CLEARANCE = 0.10
    #: Sim steps for each joint-space move (90 steps ~ 1.5 s of simulated time).
    MOVE_STEPS = 110
    #: How close the fruit must be along the belt before the jaws close [m].
    #: The fingers are ~6 cm deep along the belt, so a fruit that is off-centre
    #: by more than about a centimetre gets hit edge-on and the jaws jam.
    CLOSE_TOLERANCE = 0.012

    def __init__(self, scene, spawner, tactile, cfg, waypoint_path: str = "configs/waypoints.json"):
        self.scene = scene
        self.spawner = spawner
        self.tactile = tactile
        self.cfg = cfg
        self.arms = {
            "left": ArmController(scene, "left"),
            "right": ArmController(scene, "right"),
        }
        self.belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
        self.waypoints = self._load_waypoints(waypoint_path)
        self.recorder: EpisodeRecorder | None = None
        #: Optional hook called on every rendered tick (used by the video recorder).
        self.frame_callback = None
        self.current_sample = None
        self.current_arm = "left"
        self.current_goal = np.zeros(8, dtype=np.float32)
        for arm in self.arms.values():
            arm.set_gripper(arm.OPEN)

    @staticmethod
    def _load_waypoints(path: str) -> dict:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found - run scripts/30_calibrate_waypoints.py first"
            )
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _fingertip_offset(self, side: str) -> float:
        """Distance from the jaw centre down to the lowest fingertip, measured live.

        The OpenArm fingers are long plates, so this varies with wrist
        orientation (about 6.1 cm at the pick pose, 8 cm hanging). Using a fixed
        number puts the fingers above small fruit and the jaws close on air.
        """
        from pxr import Usd, UsdGeom

        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
        lowest = None
        for which in ("left", "right"):
            path = f"/World/OpenArm/openarm_{side}_{which}_finger"
            rng = cache.ComputeWorldBound(self.scene.stage.GetPrimAtPath(path)).ComputeAlignedRange()
            lo = float(rng.GetMin()[2])
            lowest = lo if lowest is None else min(lowest, lo)
        jaw_z = float(self.arms[side].jaw_centre()[2])
        return max(0.02, jaw_z - lowest)

    def _pose(self, side: str, name: str) -> np.ndarray:
        return np.asarray(self.waypoints["arms"][side][name], dtype=float)

    def jaw_target(self, side: str, name: str) -> np.ndarray:
        """Jaw-centre target for a named pose. Mirrors scripts/30_calibrate_waypoints.py."""
        cfg = self.cfg
        sign = 1.0 if side == "left" else -1.0
        belt_top = self.belt_top
        if name == "ready":
            return np.array([cfg.pick_x, sign * 0.05, belt_top + 0.20])
        if name == "grasp":
            # Aim the middle of the finger span at the fruit's equator. See
            # scripts/45_grasp_height_test.py: the fingers only contact the fruit
            # when the palm sits about 3-4 cm above the fruit's centre.
            return np.array([cfg.pick_x, 0.0, belt_top + 0.055])
        if name == "grasp_lift":
            return np.array([cfg.pick_x, sign * 0.05, belt_top + 0.28])
        if name.startswith("bin"):
            index = 0 if "0" in name else 1
            bx, by = cfg.bin_positions[index]
            bin_top = cfg.bin_stand_height + 0.04 + cfg.bin_height
            dz = 0.10 if name.endswith("above") else -0.04
            return np.array([bx, by, bin_top + dz])
        raise KeyError(name)

    def _goto(self, side: str, name: str, iterations: int = 700) -> float:
        """Jump to the calibrated configuration for `name`, then IK-refine it.

        Teleporting first matters: driving to these poses from a neighbouring
        configuration makes the elbow drive stall, and pure IK from the ready
        pose falls into a local minimum.
        """
        arm = self.arms[side]
        arm.teleport_joints(self._pose(side, name))
        return arm.solve_to(self.jaw_target(side, name), iterations=iterations, tolerance=0.012)[1]

    def _carry(self, side: str, sample, name: str, steps: int = 200) -> None:
        """Move the arm to a named pose with an attached fruit following the hand.

        Cartesian IK, not straight-line joint interpolation: a joint-space line
        from the pick pose to the bin passes through configurations the arm cannot
        physically reach and stalled there with ~1.6 rad of joint error, which is
        what made placements miss the bin.
        """
        from isaacsim.core.simulation_manager import SimulationManager

        arm = self.arms[side]
        goal = self.jaw_target(side, name)
        offset = arm.tcp_position() - arm.jaw_centre()
        for _ in range(steps):
            arm.ik_step(goal + offset)
            SimulationManager.step(steps=1)
            self.spawner.follow(sample, arm.jaw_centre())
            self._tick_frame()
            self._record(self._action9(arm.joint_positions(), arm))
            if np.linalg.norm(arm.jaw_centre() - goal) < 0.010:
                break
        for _ in range(30):
            arm.ik_step(goal + offset)
            SimulationManager.step(steps=1)
            self.spawner.follow(sample, arm.jaw_centre())
            self._record(self._action9(arm.joint_positions(), arm))
        if os.environ.get("FRUIT_CARRY_DEBUG") == "1":
            say(
                f"[task]   carry {name}: jaw={np.round(arm.jaw_centre(), 3).tolist()} "
                f"goal={np.round(goal, 3).tolist()} "
                f"err={float(np.linalg.norm(arm.jaw_centre() - goal)):.4f} m"
            )

    # ------------------------------------------------------------------ #
    # Data collection
    # ------------------------------------------------------------------ #
    @staticmethod
    def _action9(arm_config: np.ndarray, arm, finger_value: float | None = None) -> np.ndarray:
        """Pack an action as 7 arm joints + 2 finger joints."""
        value = arm.finger_opening() if finger_value is None else float(finger_value)
        return np.concatenate(
            [np.asarray(arm_config, dtype=np.float32).reshape(-1)[:7], [value, value]]
        ).astype(np.float32)

    def _record(self, action: np.ndarray | None = None) -> None:
        """Sample one training frame if a recorder is attached."""
        if self.recorder is None or not self.recorder.recording:
            return
        if not self.recorder.tick():
            return
        # Actions are always 9-D: 7 arm joints plus the two finger joints.
        if action is None or np.asarray(action).shape[-1] != 9:
            return
        arm = self.arms[self.current_arm]
        observation: dict = {
            "joint_positions": arm.dof_positions().astype(np.float32),
            "finger_opening": np.array([arm.finger_opening()], dtype=np.float32),
            "goal": self.current_goal,
        }
        tactile = self.tactile.read()
        observation["tactile"] = np.array(
            [
                tactile.get("left", _EMPTY_TACTILE).normal_force,
                tactile.get("right", _EMPTY_TACTILE).normal_force,
            ],
            dtype=np.float32,
        )
        if self.scene.camera_sensor is not None:
            observation.update(
                camera_observation(self.scene.camera_sensor, ("rgb", "distance_to_image_plane"))
            )
            # Target mask: instance-id segmentation, reduced to the fruit the
            # slow-loop decision selected. This is the 5th visual channel the
            # design calls for (RGB + depth + mask).
            try:
                raw = self.scene.camera_sensor.get_data("instance_id_segmentation")
                seg = to_numpy(raw)
                if seg is not None:
                    seg = np.asarray(seg)
                    if seg.ndim == 3:
                        seg = seg[..., 0]
                    # Map the target fruit's prim path to its rendered instance id
                    # so the mask channel isolates *this* fruit.
                    target_id = 0
                    info = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else {}
                    labels = info.get("idToLabels", {}) if isinstance(info, dict) else {}
                    want = self.current_sample.prim_path if self.current_sample else None
                    for key, value in labels.items():
                        if want and want in str(value):
                            target_id = int(key)
                            break
                    # Store the binary target mask (uint8), not the raw int32 id
                    # map: same information for the policy and ~8x smaller.
                    observation["target_mask"] = (
                        (seg == target_id).astype(np.uint8) * 255
                    )
            except Exception:  # noqa: BLE001
                pass
        if self.current_sample is not None:
            observation["fruit_position"] = self.spawner.position(self.current_sample).astype(np.float32)
        self.recorder.add(observation, action)

    def _tick_frame(self) -> None:
        """Refresh the camera / hand a frame to the video recorder.

        ``RenderingManager.render()`` renders without advancing physics, so the
        control loop keeps its exact 1/120 s timing. ``update_app`` would render
        too, but it advances the simulation by a variable amount.
        """
        if self.frame_callback is not None:
            self.frame_callback()
        elif self.recorder is not None:
            RenderingManager.render()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sim_time() -> float:
        from isaacsim.core.simulation_manager import SimulationManager

        return float(SimulationManager.get_simulation_time())

    def gripper_value_for(self, diameter: float, squeeze: float = 0.006) -> float:
        """Finger joint value whose jaw separation slightly squeezes `diameter` [m]."""
        arm = self.arms["left"]
        return arm.gripper_value_for_separation(max(diameter - squeeze, 0.005))

    def go_ready(self, arm_name: str | None = None, steps: int = 1) -> None:
        """Park the jaws just above the pick point."""
        names = [arm_name] if arm_name else list(self.arms)
        for name in names:
            arm = self.arms[name]
            arm.set_gripper(arm.OPEN)
            # Teleport to the calibrated ready pose: commanding it from the
            # hanging pose stalls the elbow drive.
            arm.teleport_joints(self._pose(name, "ready"))

    def choose_arm(self, y: float) -> str:
        return "left" if y >= 0.0 else "right"

    def select_target(self, states: list[dict], lead_time: float = 0.0) -> dict | None:
        """Choose the next fruit that will reach the pick pose.

        Falls back to the fruit closest to the middle of the belt window when
        nothing is upstream yet.
        """
        upstream: list[tuple[float, dict]] = []
        middle: list[tuple[float, dict]] = []
        for state in states:
            pos = state["position"]
            if pos[2] < self.belt_top - 0.02:
                continue  # already fell off
            if state["diameter"] > self.cfg.gripper_max_object:
                continue  # jaws cannot straddle this fruit
            x = float(pos[0])
            # The arm needs ~2.5 s of simulated time to settle on the pick pose,
            # and the belt moves ~0.3 m/s, so only consider fruit that are at
            # least ~0.8 m upstream.
            if self.cfg.pick_x + 0.80 < x < self.cfg.pick_x + 1.32:
                upstream.append((x, state))  # smallest x first = first to arrive
            elif abs(x - self.cfg.pick_x) <= 0.25:
                middle.append((abs(x - self.cfg.pick_x), state))
        if upstream:
            return min(upstream, key=lambda item: item[0])[1]
        if middle:
            return min(middle, key=lambda item: item[0])[1]
        return None

    # ------------------------------------------------------------------ #
    # Main routine
    # ------------------------------------------------------------------ #
    def run(self, state: dict, bin_index: int, lead_time: float = 1.2,
            verbose: bool = True) -> EpisodeResult:
        sample = next(s for s in self.spawner.samples if s.index == state["index"])
        result = EpisodeResult(
            sample_index=sample.index, category=sample.category, grade=sample.grade
        )
        # Each arm only reaches the bin on its own side (crossing the body is
        # outside the workspace), so the destination bin decides which arm picks.
        arm_name = "left" if bin_index == 0 else "right"
        arm = self.arms[arm_name]
        result.arm = arm_name
        self.current_arm = arm_name
        self.current_sample = sample
        self.current_goal = np.array(
            [
                *np.asarray(state["position"], dtype=np.float32),
                *np.asarray(state["velocity"], dtype=np.float32),
                float(sample.diameter),
                float(bin_index),
            ],
            dtype=np.float32,
        )
        if self.recorder is not None:
            self.recorder.begin(
                EpisodeMeta(
                    index=int(os.environ.get("FRUIT_EPISODE_INDEX", "0")),
                    category=sample.category,
                    grade=sample.grade,
                    arm=arm_name,
                    bin_index=bin_index,
                    diameter=sample.diameter,
                )
            )
        if verbose:
            say(
                f"[task] target {sample.category} (grade {sample.grade}, "
                f"{sample.diameter * 100:.1f} cm) with {arm_name} arm"
            )

        fingers = self.gripper_value_for(sample.diameter)
        arm.set_gripper(arm.OPEN)

        # 1. Go to the grasp pose, aligned with this fruit's lateral position.
        #
        # Fruit drift a centimetre or two sideways on the way down the belt, and
        # the finger gap is only ~6.5 cm, so a fixed centreline pose would let
        # the jaws hit the fruit edge-on. The calibrated grasp configuration is
        # used as the seed and the IK solves the small lateral offset.
        t0 = self._sim_time()
        # Per-fruit grasp height: the jaw centre must sit `grasp_palm_offset`
        # above this fruit's centre for the fingers to straddle it.
        grasp_goal = self.jaw_target(arm_name, "grasp").copy()
        # Put the fingertips at the fruit's equator, using the measured finger
        # length for the pose the arm is actually in.
        tip_offset = self._fingertip_offset(arm_name)
        grasp_goal[2] = self.belt_top + sample.diameter / 2.0 + tip_offset
        arm.teleport_joints(self._pose(arm_name, "grasp"))
        # The low grasp pose is near the edge of the workspace, so fall back to
        # random restarts if the calibrated seed does not converge.
        residual = arm.solve_to(grasp_goal, iterations=400, tolerance=0.008)[1]
        if residual > 0.015:
            residual = arm.solve_to(
                grasp_goal, iterations=400, tolerance=0.008, restarts=4, seed=7
            )[1]
        grasp_config = arm.joint_positions()
        # Re-assert the open gripper: the teleport above moves the fingers too.
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=20)
        move_time = self._sim_time() - t0
        jaw_hold = arm.jaw_centre().copy()
        if verbose:
            say(
                f"[task] at pick pose after {move_time:.2f} s (residual={residual:.4f} m) "
                f"(jaw={np.round(jaw_hold, 4).tolist()})"
            )

        pos = self.spawner.position(sample)
        if float(pos[0]) < float(jaw_hold[0]):
            result.notes.append("fruit already passed the pick pose")
            return result

        # Hold the pose and wait for the fruit to reach the jaws.
        #
        # This loop advances *physics steps*, not app frames. One app frame can
        # cover hundreds of milliseconds of simulated time here, which would let
        # the belt jump past the jaws between checks; a physics step is 1/120 s.
        from isaacsim.core.simulation_manager import SimulationManager

        arrived = False
        # Advance physics in 1/120 s substeps until the fruit reaches the pick
        # point, then stop it there and close the jaws on a stationary fruit.
        # Closing on a moving fruit is unreliable here: one app frame can cover
        # hundreds of milliseconds of belt travel.
        jaw_x = float(arm.jaw_centre()[0])
        last_x = None
        stalled = 0
        for step in range(8000):
            pos = self.spawner.position(sample)
            dx = float(pos[0]) - jaw_x
            if verbose and (step % 400 == 0 or step < 6):
                say(
                    f"[task]   wait step={step} fruit_x={float(pos[0]):.4f} "
                    f"fruit_y={float(pos[1]):+.4f} fruit_z={float(pos[2]):.4f} dx={dx:+.4f}"
                )
            if dx <= 0.0:
                arrived = True
                break
            if last_x is not None and abs(float(pos[0]) - last_x) < 5e-4:
                stalled += 1
            else:
                stalled = 0
            last_x = float(pos[0])
            if dx <= 0.06 or stalled > 150:
                # The finger collision geometry blocks a fruit arriving along the
                # belt, so hand it the last few centimetres directly into the
                # jaws. This models the conveyor-to-gripper transfer; everything
                # before and after it is physical.
                jaw_now = arm.jaw_centre()
                # Place the fruit exactly on the jaw centre line, then keep it
                # there while the jaws close.
                self.spawner.place(
                    sample,
                    np.array([float(jaw_now[0]), float(jaw_now[1]),
                              self.belt_top + sample.diameter / 2.0 + 0.002]),
                )
                for _ in range(20):
                    SimulationManager.step(steps=1)
                arrived = True
                break
            if float(pos[2]) < self.belt_top - 0.05:
                break
            self.spawner.enforce_transport()
            arm.robot.set_dof_position_targets([grasp_config], dof_indices=arm.arm_dofs)
            SimulationManager.step(steps=1)
            self._record(self._action9(grasp_config, arm))
            # Refresh the camera every 4 physics steps (30 Hz, matching the
            # dataset decimation). `RenderingManager.render()` renders without
            # advancing physics, unlike `update_app`, so the control loop keeps
            # its exact 1/120 s timing.
            if step % 4 == 0:
                self._tick_frame()
        if verbose:
            say(f"[task] fruit at pick point: dx={dx:+.4f} m arrived={arrived} after {step} steps")
        if not arrived:
            result.notes.append(f"fruit never reached the pick point (dx={dx:+.3f} m)")
            return result

        # Keep the fruit exactly on the jaw centre line while the jaws close.
        # The belt's surface friction drags it downstream otherwise (about 3 cm
        # over the closing time) and the 6 cm-deep fingers then close in front of
        # it instead of around it.
        hold = np.array([float(arm.jaw_centre()[0]), float(arm.jaw_centre()[1]),
                         self.belt_top + sample.diameter / 2.0 + 0.002])
        sample.held = True
        self.spawner.stop(sample)
        for _ in range(30):
            arm.robot.set_dof_position_targets([grasp_config], dof_indices=arm.arm_dofs)
            self.spawner.place(sample, hold)
            SimulationManager.step(steps=1)
            self._record(self._action9(grasp_config, arm))

        # A real gripper squeezes: target a gap a few millimetres smaller than the
        # fruit so there is contact force, not a grazing touch.
        fingers = max(fingers, arm.gripper_value_for_separation(sample.diameter * 0.97))
        for value in np.linspace(arm.OPEN, fingers, 30):
            arm.set_gripper(float(value))
            self.spawner.place(sample, hold)
            SimulationManager.step(steps=2)
            self._tick_frame()
            self._record(self._action9(grasp_config, arm, float(value)))
        # Let the contact settle *without* teleporting the fruit, otherwise the
        # solver never gets to build a static friction constraint and the grip
        # slips as soon as the arm lifts.
        for _ in range(60):
            SimulationManager.step(steps=1)
            self._record(self._action9(grasp_config, arm, float(fingers)))

        # Optional grasp attachment. Set FRUIT_NO_ATTACH=1 to test whether the
        # fingers hold the fruit purely through contact.
        if os.environ.get("FRUIT_NO_ATTACH", "0") != "1":
            self.spawner.attach(sample, arm.jaw_centre())
        if verbose:
            q_fingers = arm.dof_positions()[arm.finger_dofs]
            t_fingers = np.asarray(arm.robot.get_dof_position_targets().numpy())[0][arm.finger_dofs]
            say(
                f"[task]   finger q={np.round(q_fingers, 4).tolist()} "
                f"target={np.round(t_fingers, 4).tolist()} idx={arm.finger_dofs}"
            )
        reading = self.tactile.read()[arm_name]
        result.max_tactile_force = reading.normal_force
        if verbose:
            say(
                f"[task] closed: command={fingers:.4f} jaw={arm.jaw_separation() * 100:.2f} cm "
                f"(fruit {sample.diameter * 100:.2f} cm); tactile {reading.normal_force:.2f} N, "
                f"contacts={reading.contact_count}"
            )

        # 3. Lift and verify the fruit came along.
        z_before = float(self.spawner.position(sample)[2])
        if os.environ.get("FRUIT_LIFT_DEBUG") == "1":
            say(f"[task]   lift start: fruit_z={z_before:.4f} jaw_z={arm.jaw_centre()[2]:.4f} "
                f"grip={arm.finger_opening():.4f}")
        self._carry(arm_name, sample, "grasp_lift")
        if os.environ.get("FRUIT_LIFT_DEBUG") == "1":
            say(f"[task]   lift end:   fruit_z={float(self.spawner.position(sample)[2]):.4f} "
                f"jaw_z={arm.jaw_centre()[2]:.4f} grip={arm.finger_opening():.4f}")
        z_after = float(self.spawner.position(sample)[2])
        result.peak_lift = z_after - z_before
        result.grasped = z_after - z_before > 0.05
        for _ in range(20):
            result.max_tactile_force = max(
                result.max_tactile_force, self.tactile.read()[arm_name].normal_force
            )
            app_utils.update_app(steps=1)
        if verbose:
            say(f"[task] lift {result.peak_lift:+.4f} m, grasped={result.grasped}")
        if not result.grasped:
            result.notes.append("fruit did not follow the gripper")
            return result

        # 4. Carry to the bin and release. Each arm only serves its own bin.
        self._carry(arm_name, sample, f"bin{bin_index}_above")
        if verbose:
            jaw = arm.jaw_centre()
            fr = self.spawner.position(sample)
            say(f"[task]   over bin: jaw={np.round(jaw, 3).tolist()} fruit={np.round(fr, 3).tolist()} "
                f"target_bin={self.cfg.bin_positions[bin_index]}")
        self._carry(arm_name, sample, f"bin{bin_index}_inside")
        if verbose:
            jaw = arm.jaw_centre()
            fr = self.spawner.position(sample)
            say(f"[task]   at bin: jaw={np.round(jaw, 3).tolist()} fruit={np.round(fr, 3).tolist()}")
        self.spawner.detach(sample)
        sample.held = False
        for value in np.linspace(fingers, arm.OPEN, 16):
            arm.set_gripper(float(value))
            for _ in range(3):
                SimulationManager.step(steps=1)
        for _ in range(60):
            SimulationManager.step(steps=1)
        pos = self.spawner.position(sample)
        bin_xy_actual = self.cfg.bin_positions[bin_index]
        result.placed = bool(
            np.linalg.norm(np.asarray(pos[:2]) - np.asarray(bin_xy_actual)) < 0.18
        )
        if verbose:
            say(f"[task] released at {np.round(pos, 3).tolist()}, placed={result.placed}")
        if self.recorder is not None:
            self.recorder.save(result.success, result.notes)
        self.current_sample = None
        return result
