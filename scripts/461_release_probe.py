"""Release probe: does the payload leave the output belt when an interference grip opens?

    RELEASE_VARIANT=old     TRIALS=20 scripts/run.sh scripts/461_release_probe.py
    RELEASE_VARIANT=relax   TRIALS=20 scripts/run.sh scripts/461_release_probe.py
    RELEASE_VARIANT=fast    TRIALS=20 scripts/run.sh scripts/461_release_probe.py
    RELEASE_VARIANT=support TRIALS=20 SINK=0.0 scripts/run.sh scripts/461_release_probe.py

The line's release is a 1-in-10 ejection (`logs/415` attempt 4, `logs/416`; the
release trace in `logs/460` attempt 9 measured 1.105 m/s on the payload while the
pad faces were still inside the fruit). A ten-attempt run is the acceptance, but it
is a single sample of a rare event and 12 minutes long. This probe isolates the
release: the same scene, the same kinematic gripper, the same fruit pool and the
same close (`d * 0.98` on the measured extent), with a grip-and-carry sequence
that ends with the payload *hanging* at the v3 release height (10 cm above the
output belt top), as the line does. Variants:

* ``old``     - the shipped single ramp from the closed gap to `max(gap+0.10,
                d+0.03)` over 40 min-jerk steps;
* ``relax``   - relax the span to `pinch_width + PAD_THICK + margin` (the first
                span whose physical faces clear the fruit) and then open, with the
                payload still at the release height;
* ``fast``    - same, with a 4-step relax ramp instead of 24;
* ``support`` - descend the closed pads until the fruit's lowest point is `SINK`
                past the belt surface, then relax, then open (the set-down
                ordering; off by default on the line).

It reports, per trial, the payload's peak speed and lateral speed through the
release, the highest z it reaches (the side rail is at belt_top+0.035) and
whether it ends off the belt (fell to the floor or drifted past an edge).
``TRACE_TRIAL=N`` prints a per-tick trace of trial N. This is a probe, not the
shipping line: it has no arm and no merge into the demo pipeline, so it measures
the *release* mechanism with more samples than a line run can.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import numpy as np

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.kinematic_gripper import PAD_THICK, KinematicGripper
from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent
from fruit_sorting.motion import min_jerk_ramp, top_down_quaternion
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

DT = 1.0 / 120.0


def _rot(quat) -> np.ndarray:
    w, x, y, z = (float(v) for v in quat)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def main() -> int:
    variant = os.environ.get("RELEASE_VARIANT", "relax")
    trials = int(os.environ.get("TRIALS", "20"))
    trace_trial = int(os.environ.get("TRACE_TRIAL", "-1"))
    sink = float(os.environ.get("SINK", "0.0"))
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "output_belts"))
    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    scene.start(physics_dt=DT, warmup_steps=60)
    spawner.refresh_rigids()
    spawner.reset()
    gripper = KinematicGripper(scene.stage, "left")
    quat = top_down_quaternion("x")  # closing axis +X, fingers down
    belt_xy = np.array(cfg.output_belt_drop_points[1], dtype=float)
    floor = float(cfg.output_belt_top_z)
    rim = floor + 0.035  # side rail top
    release_z = float(cfg.output_place_z)

    def pinch_width(sample, hand_quat) -> float:
        shape = FRUIT_SHAPES.get(sample.category)
        if shape is None:
            return float(sample.diameter)
        axis_world = _rot(hand_quat)[:, 1]
        _, fruit_quat = spawner.fruit_pose(sample)
        local = _rot(fruit_quat).T @ axis_world
        return float(axis_extent(shape, float(sample.diameter), local))

    def support_down(sample) -> float:
        shape = FRUIT_SHAPES.get(sample.category)
        half = float(sample.diameter) / 2.0
        if shape is None:
            return half
        _, fruit_quat = spawner.fruit_pose(sample)
        local = _rot(fruit_quat).T @ np.array([0.0, 0.0, -1.0])
        scale = half
        radial = float(np.hypot(local[0], local[1]))
        axial = float(shape.length_scale) * float(local[2])
        return float(max(r * scale * radial + z * scale * axial for (r, z) in shape.profile()))

    samples = sorted(spawner.samples, key=lambda s: float(s.diameter))
    say(
        f"[probe] variant={variant} trials={trials} pool={len(samples)} sink={sink} "
        f"belt={belt_xy.tolist()} floor={floor:.3f} rim={rim:.3f} "
        f"release={release_z:.3f}"
    )
    ejections = 0
    peaks: list[float] = []
    lateral: list[float] = []
    above_rim = 0
    for trial in range(trials):
        sample = samples[trial % len(samples)]
        d = float(sample.diameter)
        # Close the pads on the fruit where it rests on the conveyor surface (the
        # line closes on the main belt), then lift it to the release height and
        # stroke it sideways, so the release starts from the same state the line's
        # `place{index}` leg leaves: grip closed, payload hanging above the belt,
        # rattle stoked by real carrying.
        gripper.park()
        spawner.place(
            sample,
            np.array([belt_xy[0], belt_xy[1], floor + support_down(sample) + 0.002]),
        )
        for _ in range(30):
            SimulationManager.step(steps=1)
        side = 1.0 if trial % 2 == 0 else -1.0
        offset = np.array([side * 0.001 * (trial % 3), 0.0, 0.0])
        gap = pinch_width(sample, quat) * 0.98

        state = {"peak": 0.0, "lateral": 0.0, "zmax": -1.0, "gap_at_peak": 0.0,
                 "stage_at_peak": ""}
        trace = trial == trace_trial
        stage = ["close"]
        tick = [0]
        current_gap = [gap]

        def measure() -> None:
            pos = np.asarray(spawner.position(sample), dtype=float)
            vel = np.asarray(spawner.velocity(sample), dtype=float)
            speed = float(np.linalg.norm(vel))
            if speed > state["peak"]:
                state["peak"] = speed
                state["gap_at_peak"] = current_gap[0]
                state["stage_at_peak"] = stage[0]
            state["lateral"] = max(state["lateral"], float(np.hypot(vel[0], vel[1])))
            state["zmax"] = max(state["zmax"], float(pos[2]))
            if trace:
                tick[0] += 1
                pad_a, pad_b = gripper.pad_faces()
                say(
                    f"[trace] t={tick[0]:4d} {stage[0]:6s} gap={current_gap[0] * 1000:7.1f} "
                    f"fruit={np.round(pos, 4).tolist()} |v|={speed:.3f} "
                    f"vel={np.round(vel, 3).tolist()} "
                    f"padA={np.round(np.asarray(pad_a, dtype=float), 4).tolist()} "
                    f"padB={np.round(np.asarray(pad_b, dtype=float), 4).tolist()}"
                )

        for value in min_jerk_ramp(0.09, gap, 60):
            current_gap[0] = float(value)
            centre = np.asarray(spawner.position(sample), dtype=float) + offset
            gripper.follow_centre(centre, quat, float(value))
            SimulationManager.step(steps=2)
            measure()
        for _ in range(30):
            SimulationManager.step(steps=1)
            measure()
        # Lift to the release height, then a 16 cm lateral stroke and back.
        stage[0] = "lift"
        hold = np.asarray(spawner.position(sample), dtype=float) + offset
        for dz in min_jerk_ramp(0.0, release_z - hold[2], 60):
            gripper.follow_centre(hold + np.array([0.0, 0.0, float(dz)]), quat, gap)
            SimulationManager.step(steps=1)
            measure()
        stage[0] = "carry"
        for dy in min_jerk_ramp(0.0, 0.08, 80):
            gripper.follow_centre(hold + np.array([0.0, float(dy), release_z - hold[2]]), quat, gap)
            SimulationManager.step(steps=1)
            measure()
        for dy in min_jerk_ramp(0.08, 0.0, 80):
            gripper.follow_centre(hold + np.array([0.0, float(dy), release_z - hold[2]]), quat, gap)
            SimulationManager.step(steps=1)
            measure()
        centre = np.asarray(spawner.position(sample), dtype=float) + offset

        # Release. Only the pad commands differ between variants.
        release_gap = max(gap + 0.10, d + 0.03)
        relax_target = min(
            release_gap, max(gap, pinch_width(sample, quat) + PAD_THICK + 0.006)
        )
        lowered = np.asarray(centre, dtype=float).copy()
        if variant == "old":
            stage[0] = "open"
            for value in min_jerk_ramp(gap, release_gap, 40):
                current_gap[0] = float(value)
                gripper.follow_centre(centre, quat, float(value))
                for _ in range(3):
                    SimulationManager.step(steps=1)
                    measure()
        else:
            # (support/asym, the shipped ordering) 1. lower the *gripped* payload
            # to first contact with the tray floor, sink 0 (no press).
            if variant in ("support", "asym"):
                stage[0] = "lower"
                floor_drop = max(
                    0.0,
                    (float(spawner.position(sample)[2]) - support_down(sample))
                    - floor
                    + sink,
                )
                base = np.asarray(centre, dtype=float).copy()
                for dz in min_jerk_ramp(0.0, floor_drop, 60):
                    lowered = base - np.array([0.0, 0.0, float(dz)])
                    gripper.follow_centre(lowered, quat, gap)
                    SimulationManager.step(steps=1)
                    measure()
            # 2. relax to the first span whose physical faces clear the fruit.
            # `asym` keeps pad A still while pad B retreats first (the stored
            # normal force then pushes the payload along the closing axis, along
            # the floor, instead of trapping it between two retreating contacts),
            # then opens symmetrically.
            stage[0] = "relax"
            if variant == "asym":
                axis = _rot(quat)[:, 1]
                base = lowered.copy()
                for value in min_jerk_ramp(gap, relax_target, 4):
                    shift = (float(value) - gap) / 2.0
                    gripper.follow_centre(base + axis * shift, quat, float(value))
                    for _ in range(2):
                        SimulationManager.step(steps=1)
                        measure()
                lowered = base + axis * ((relax_target - gap) / 2.0)
            else:
                relax_steps = 4 if variant in ("fast", "support") else 24
                for value in min_jerk_ramp(gap, relax_target, relax_steps):
                    current_gap[0] = float(value)
                    gripper.follow_centre(lowered, quat, float(value))
                    for _ in range(2):
                        SimulationManager.step(steps=1)
                        measure()
            # 3. dwell: residual motion decays while the pads do nothing.
            stage[0] = "dwell"
            dwell = 20 if variant == "support" else 0
            for _ in range(dwell):
                gripper.follow_centre(lowered, quat, relax_target)
                SimulationManager.step(steps=1)
                measure()
            # 4. open, with nothing in contact.
            stage[0] = "open"
            for value in min_jerk_ramp(relax_target, release_gap, 40):
                current_gap[0] = float(value)
                gripper.follow_centre(lowered, quat, float(value))
                for _ in range(3):
                    SimulationManager.step(steps=1)
                    measure()
        stage[0] = "settle"
        for _ in range(60):
            SimulationManager.step(steps=1)
            measure()

        final = np.asarray(spawner.position(sample), dtype=float)
        off_y = abs(float(final[1]) - belt_xy[1]) > cfg.output_belt_size[1] / 2.0 + 0.03
        off_x = not (cfg.output_belt_x_range[0] - 0.05 <= float(final[0])
                     <= cfg.output_belt_x_range[1] + 0.05)
        fell = float(final[2]) < floor - 0.05
        ejected = off_y or off_x or fell
        ejections += int(ejected)
        peaks.append(state["peak"])
        lateral.append(state["lateral"])
        above_rim += int(state["zmax"] > rim - float(sample.diameter) / 2 + 0.005)
        say(
            f"[probe] trial {trial:2d} {sample.category:10s} d={d * 100:4.1f}cm "
            f"peak|v|={state['peak']:.3f} lat={state['lateral']:.3f} "
            f"zmax={state['zmax']:.4f} gap@peak={state['gap_at_peak'] * 1000:.1f}mm "
            f"at={state['stage_at_peak']} final={np.round(final, 4).tolist()} "
            f"{'EJECTED' if ejected else 'placed'}"
        )
        gripper.park()
        spawner.park(sample)
        for _ in range(10):
            SimulationManager.step(steps=1)

    peaks_arr = np.asarray(peaks)
    lat_arr = np.asarray(lateral)
    say(
        f"[probe] {variant}: {ejections}/{trials} ejected | "
        f"peak|v| max={peaks_arr.max():.3f} p50={np.median(peaks_arr):.3f} | "
        f"lateral max={lat_arr.max():.3f} p50={np.median(lat_arr):.3f} | "
        f"over-rim {above_rim}/{trials}"
    )
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
