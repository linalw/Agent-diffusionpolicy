"""P11-B: measure the squeeze/"ejection" mechanism directly.

    scripts/154_claim_run.sh logs/p11b/10_sweep_tomato.log \
        scripts/run.sh scripts/210_squeeze_probe.py

The P11-A audit (`logs/p11/A_PHYSICS_AUDIT.md`) reads the ejection from the tree
and the existing logs: the fruit is a rigid body, the finger contact is
30 kN/m compliant, and the control can command a keep-gap 1.7-17.5 mm narrower
than the fruit under a saturated 10 N drive, so the commanded interference has
nowhere to go but into motion of the fruit. This probe measures that directly,
outside the task loop:

* `belt` group - the fruit rests on the (stopped) belt at the pick station, the
  arm is posed at the shipped grip standoff (`FRUIT_FINGER_LEN` + `FRUIT_PAD_LIFT`
  above the fruit's centre), the jaws close from open to a hold gap with the
  shipped close's min-jerk shape, and then the **sweep gap** `extent - delta` is
  commanded in one step and held.
* `air` group - the same close/hold, then the arm lifts 50 mm (the shipped
  close -> probe lift -> regrasp sequence) so the fruit is held with nothing
  under it, and the sweep gap is commanded.
* `plow` group - the shipped re-seat geometry: the jaws are *already* at the
  sweep gap (closed on air) and descend 40 mm onto the fruit, tracking its
  measured position (the `keep_gap` re-seat loop). This is the P10-E census's
  actual trigger: a position command below the fruit's width, driven into the
  fruit.
* `drop` baseline - the fruit is dropped from the belt-top height (1.17 m to the
  floor) so the free-fall landing speed the P10-E log falls are attributed to is
  reproduced by the same build.
* `baseline` - the jaws close with nothing between them (the `55_grasp_sweep`
  hard-stop control).

The sweep is `delta` in {-15, -5, 0, 2, 5, 10, 15} mm (negative = the commanded
gap is *wider* than the fruit, the no-contact anchor), 3 repeats each.

Per case the probe logs one `[squeeze]` row: the fruit's peak speed (fast window
and whole window), the displacement/dx/dy/dz, the peak finger force, the
achieved jaw separation (dof and link span) and the outcome
(stayed / escaped / fell / hold_failed / out_of_span). The sweep is repeated with
`FRUIT_SUBSTEPS=4`, with `FRUIT_FINGER_COMPLIANCE=4000`, with a fruit-side
compliant material (`FRUIT_SQUEEZE_FRUIT_COMPLIANCE`) and with a different grip
depth (`FRUIT_PAD_LIFT`) to separate the parameter and geometry sensitivities.

Standalone probe, not a battery: no shipped default is touched, and the numbers
are this probe's own scenario, not the acceptance line's.
"""

from __future__ import annotations

import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))

_CLASS = os.environ.get("FRUIT_SQUEEZE_CLASS", "tomato")

# A stopped belt: the sweep must be a squeeze measurement, not a transport one.
os.environ.setdefault("FRUIT_BELT_SPEED", "0")
os.environ.setdefault("FRUIT_BELT_RAMP", "0")
# The pool must contain the class under test (the P1c one-species lock).
os.environ["FRUIT_SUPPLY_SPECIES"] = _CLASS

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import PhysxSchema, Usd, UsdGeom, UsdPhysics

from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say, substeps, to_numpy
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile

install_failure_handler("p11b/210_squeeze_probe")

DT = 1.0 / 120.0
CLASS = _CLASS
SIDE = os.environ.get("FRUIT_SQUEEZE_SIDE", "left")
SEED = int(os.environ.get("SEED", "5"))
DELTAS_MM = tuple(
    float(v)
    for v in os.environ.get(
        "FRUIT_SQUEEZE_DELTAS_MM", "-15,-5,0,2,5,10,15"
    ).split(",")
)
REPEATS = int(os.environ.get("FRUIT_SQUEEZE_REPEATS", "3"))
GROUPS = tuple(
    g.strip()
    for g in os.environ.get("FRUIT_SQUEEZE_GROUPS", "belt,air,plow").split(",")
    if g.strip()
)
#: The catch interference the jaws close to before the sweep [mm].
HOLD_MM = float(os.environ.get("FRUIT_SQUEEZE_HOLD_MM", "1.0"))
#: Min-jerk close ramp length [ticks] - the shipped dynamic close's load phase.
CLOSE_TICKS = int(os.environ.get("FRUIT_SQUEEZE_CLOSE_TICKS", "45"))
#: `plow` group: how far above the grip pose the sub-width jaws start before
#: descending onto the fruit (the shipped re-seat trigger: a position command
#: below the fruit's width, driven into the fruit) [m].
PLOW_LIFT = float(os.environ.get("FRUIT_SQUEEZE_PLOW_LIFT", "0.040"))
#: How far the `air` group lifts the held fruit off the belt [m] (the shipped
#: close -> probe-lift -> regrasp sequence).
LIFT_M = float(os.environ.get("FRUIT_SQUEEZE_LIFT_M", "0.05"))
HOLD_TICKS = int(os.environ.get("FRUIT_SQUEEZE_HOLD_TICKS", "60"))
WATCH_TICKS = int(os.environ.get("FRUIT_SQUEEZE_WATCH_TICKS", "120"))
FAST_TICKS = int(os.environ.get("FRUIT_SQUEEZE_FAST_TICKS", "18"))
DROP = os.environ.get("FRUIT_SQUEEZE_DROP", "1") == "1"
BASELINE = os.environ.get("FRUIT_SQUEEZE_BASELINE", "1") == "1"
TRACE = os.environ.get("FRUIT_SQUEEZE_TRACE", "0") == "1"
ESCAPE_M = float(os.environ.get("FRUIT_SQUEEZE_ESCAPE_M", "0.02"))
FINGER_LEN = float(os.environ.get("FRUIT_FINGER_LEN", "0.060"))
PAD_LIFT = float(os.environ.get("FRUIT_PAD_LIFT", "0.010"))


def step(ticks: int = 1) -> None:
    """Advance physics by `ticks` control ticks (substep-aware, like the task)."""
    for _ in range(max(1, int(ticks))):
        SimulationManager.step(steps=substeps())


def quat_matrix(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    n = float(np.sqrt(w * w + x * x + y * y + z * z)) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def main() -> int:
    wall0 = time.time()
    with open(os.path.join(_ROOT, "configs", "waypoints.json"), encoding="utf-8") as fh:
        waypoints = json.load(fh)

    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))

    # The pool is authored before play so a material knob can be applied before
    # PhysX parses it (the `55_grasp_sweep` authoring pattern).
    spawner = FruitSpawner(scene.stage, cfg, seed=SEED)
    spawner.create_pool()
    sample = next((s for s in spawner.samples if s.category == CLASS), None)
    if sample is None:
        say(f"[squeeze] FATAL: no {CLASS} fruit in the pool")
        return 2

    # Fruit-side contact knobs (default: the shipped rigid fruit material).
    fruit_compliance = float(os.environ.get("FRUIT_SQUEEZE_FRUIT_COMPLIANCE", "0"))
    fruit_damping = float(os.environ.get("FRUIT_SQUEEZE_FRUIT_DAMPING", "80"))
    fruit_restitution = float(os.environ.get("FRUIT_SQUEEZE_FRUIT_RESTITUTION", "-1"))
    mat = scene.stage.GetPrimAtPath(f"{sample.prim_path}_physmat")
    if mat.IsValid():
        if fruit_restitution >= 0.0:
            UsdPhysics.MaterialAPI(mat).CreateRestitutionAttr().Set(fruit_restitution)
        if fruit_compliance > 0.0:
            api = PhysxSchema.PhysxMaterialAPI.Apply(mat)
            api.CreateCompliantContactStiffnessAttr().Set(fruit_compliance)
            api.CreateCompliantContactDampingAttr().Set(fruit_damping)
        say(
            f"[squeeze] fruit material: compliance={fruit_compliance:.0f} N/m "
            f"damping={fruit_damping:.0f} restitution={fruit_restitution}"
        )
    else:
        say(f"[squeeze] WARNING: fruit material {sample.prim_path}_physmat not found")

    def enable_tracking(path: str):
        """Enable contact tracking on a fresh handle (the tactile's two-step).

        A fruit prim authored before play gets its physics view at play time;
        enabling tracking later on the same view does not work, so the flag has
        to be set on the authoring-time view and re-asserted on a fresh handle
        once the simulation is playing.
        """
        try:
            prim = RigidPrim(path)
            prim.set_enabled_contact_tracking(True, threshold=1e-3)
            return prim
        except Exception as exc:  # noqa: BLE001
            say(f"[squeeze] WARNING: contact tracking unavailable for {path}: {exc}")
            return None

    enable_tracking(sample.prim_path)  # authoring-time (before play)

    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()
    step(30)
    spawner.refresh_rigids()

    rigid = enable_tracking(sample.prim_path) or RigidPrim(sample.prim_path)
    fruit_force_ok = True
    try:
        rigid.get_net_contact_forces()
    except Exception as exc:  # noqa: BLE001
        fruit_force_ok = False
        say(f"[squeeze] WARNING: fruit contact view invalid ({exc}); F_fruit reads 0")
    mesh = UsdGeom.Mesh(scene.stage.GetPrimAtPath(sample.prim_path))
    points = np.asarray(mesh.GetPointsAttr().Get(), dtype=float)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(
        f"[squeeze] probe setup: class={CLASS} sample=#{sample.index} "
        f"d={sample.diameter * 1000:.1f}mm mass={sample.mass * 1000:.1f}g "
        f"pool={len(spawner.samples)} belt_top={belt_top:.3f} "
        f"substeps={substeps()} compliance_env={os.environ.get('FRUIT_FINGER_COMPLIANCE')} "
        f"repeats={REPEATS} deltas_mm={list(DELTAS_MM)} groups={list(GROUPS)}"
    )

    def fruit_state():
        pos, quat = rigid.get_world_poses()
        lin, _ang = rigid.get_velocities()
        return (
            np.asarray(to_numpy(pos), dtype=float)[0],
            np.asarray(to_numpy(quat), dtype=float)[0],
            np.asarray(to_numpy(lin), dtype=float)[0],
        )

    def place(pos, quat=(1.0, 0.0, 0.0, 0.0)) -> None:
        rigid.set_world_poses(
            positions=[np.asarray(pos, dtype=float).tolist()], orientations=[list(quat)]
        )
        rigid.set_velocities(
            linear_velocities=[[0.0, 0.0, 0.0]], angular_velocities=[[0.0, 0.0, 0.0]]
        )

    def extent_along(quat, axis) -> float:
        """True collider extent along `axis`: the convex-hull support of the mesh."""
        local = quat_matrix(quat).T @ np.asarray(axis, dtype=float)
        proj = points @ local
        return float(proj.max() - proj.min())

    def support_along(quat, axis):
        """(lo, hi) of the mesh's support along `axis`, relative to the body origin."""
        local = quat_matrix(quat).T @ np.asarray(axis, dtype=float)
        proj = points @ local
        return float(proj.min()), float(proj.max())

    finger_prims = [
        scene.stage.GetPrimAtPath(f"/World/OpenArm/openarm_{SIDE}_{which}_finger")
        for which in ("left", "right")
    ]

    def finger_bounds():
        """Per-finger world AABBs: (left_lo, left_hi, right_lo, right_hi)."""
        out = []
        for prim in finger_prims:
            rng = cache.ComputeWorldBound(prim).ComputeAlignedRange()
            out.append(np.asarray(rng.GetMin(), dtype=float))
            out.append(np.asarray(rng.GetMax(), dtype=float))
        return out

    # --- arm: the shipped grasp pose, jaws open ------------------------------ #
    arm = ArmController(scene, SIDE)
    arm.teleport_joints(np.asarray(waypoints["arms"][SIDE]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    arm.capture_hold_pose()
    step(60)

    # Fingertip depth below the jaw centre, measured from the finger link bounds
    # (the `144_contact_face_probe` method; the task's own standoff uses the
    # nominal FRUIT_FINGER_LEN instead).
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    lowest = None
    for which in ("left", "right"):
        prim = scene.stage.GetPrimAtPath(f"/World/OpenArm/openarm_{SIDE}_{which}_finger")
        rng = cache.ComputeWorldBound(prim).ComputeAlignedRange()
        z = float(rng.GetMin()[2])
        lowest = z if lowest is None else min(lowest, z)
    fingertip_depth = float(arm.jaw_centre()[2]) - float(lowest)

    # --- the fruit's resting place on the belt ------------------------------- #
    rest = np.array(
        [cfg.pick_x, cfg.pick_y, belt_top + float(-points[:, 2].min())], dtype=float
    )
    place(rest)
    step(90)
    p_settled, q_settled, _ = fruit_state()
    say(
        f"[squeeze] fruit settled at {np.round(p_settled, 4).tolist()} "
        f"q={np.round(q_settled, 3).tolist()} "
        f"(placed {np.round(rest, 4).tolist()}, moved "
        f"{np.linalg.norm(p_settled - rest) * 1000:.1f}mm)"
    )

    standoff = FINGER_LEN + PAD_LIFT
    target = np.array(
        [p_settled[0], p_settled[1], p_settled[2] + standoff], dtype=float
    )

    def pose_to(jaw_target, iterations: int = 500) -> float:
        best = (float("inf"), arm.joint_positions())
        for _ in range(iterations):
            arm.ik_step(arm.tcp_target_for_jaw(jaw_target))
            step(1)
            residual = float(np.linalg.norm(arm.jaw_centre() - jaw_target))
            if residual < best[0]:
                best = (residual, arm.joint_positions().copy())
        arm.teleport_joints(best[1], settle=30)
        return best[0]

    residual = pose_to(target)
    jaw0 = np.asarray(arm.jaw_centre(), dtype=float)
    tool0 = np.asarray(arm.approach_axis(), dtype=float)
    axis0 = np.asarray(arm.jaw_axis(), dtype=float)
    extent = extent_along(q_settled, axis0)
    tip0 = jaw0 + tool0 * FINGER_LEN
    say(
        f"[squeeze] arm posed: jaw={np.round(jaw0, 4).tolist()} "
        f"tool={np.round(tool0, 3).tolist()} jaw_axis={np.round(axis0, 3).tolist()} "
        f"residual={residual * 1000:.1f}mm span={arm.jaw_separation() * 1000:.1f}mm"
    )
    say(
        f"[squeeze] geometry: extent={extent * 1000:.1f}mm standoff={standoff * 1000:.1f}mm "
        f"(finger_len={FINGER_LEN * 1000:.0f}+pad_lift={PAD_LIFT * 1000:.0f}) "
        f"fingertip_depth={fingertip_depth * 1000:.1f}mm "
        f"tip_vs_fruit_centre={(tip0[2] - p_settled[2]) * 1000:+.1f}mm "
        f"fruit_centre_vs_fingertip={(p_settled[2] - (jaw0[2] - fingertip_depth)) * 1000:+.1f}mm"
    )

    # --- one case ------------------------------------------------------------ #
    rows: list[dict] = []
    blend = 10 * ((np.arange(CLOSE_TICKS) + 1.0) / CLOSE_TICKS) ** 3 - 15 * (
        (np.arange(CLOSE_TICKS) + 1.0) / CLOSE_TICKS
    ) ** 4 + 6 * ((np.arange(CLOSE_TICKS) + 1.0) / CLOSE_TICKS) ** 5

    if BASELINE:
        # Where do the pads stop with nothing between them? The `55_grasp_sweep`
        # hard-stop baseline, re-measured on this tree so the sweep's achieved
        # spans can be read against it.
        place(np.array([-0.6, 0.0, belt_top + 0.05]))
        step(30)
        arm.set_gripper(arm.OPEN)
        step(20)
        arm.set_gripper(arm.gripper_value_for_separation(0.012))
        step(120)
        reading = tactile.read().get(SIDE)
        say(
            f"[squeeze] case=baseline group=baseline class={CLASS} "
            f"gap_cmd_mm=12.0 "
            f"sep_end_mm={(arm.JAW_SEPARATION_OFFSET + arm.JAW_SEPARATION_PER_JOINT * arm.finger_opening()) * 1000:.1f} "
            f"span_end_mm={arm.jaw_separation() * 1000:.1f} "
            f"F_finger_peak={float(reading.normal_force) if reading else 0.0:.2f}N "
            f"contacts={int(reading.contact_count) if reading else 0} outcome=hard_stop"
        )

    def run_case(group: str, delta_mm: float, rep: int) -> dict:
        gap = extent - delta_mm / 1000.0
        row = {
            "case": f"{group}-d{delta_mm:.0f}-r{rep}",
            "group": group,
            "delta_mm": delta_mm,
            "rep": rep,
            "gap_cmd_mm": gap * 1000.0,
            "extent_mm": extent * 1000.0,
            "outcome": "",
            "hold_failed": 0,
            "lift_dz_mm": float("nan"),
        }
        arm.set_gripper(arm.OPEN)
        step(20)

        # The previous case may have left the arm lifted (`air`); re-seat the jaw
        # centre on the base grip target before every case.
        jaw_now = np.asarray(arm.jaw_centre(), dtype=float)
        if float(np.linalg.norm(jaw_now - target)) > 0.002:
            for alpha in blend:
                arm.ik_step(arm.tcp_target_for_jaw(jaw_now + alpha * (target - jaw_now)))
                step(1)

        open_gap = arm.JAW_SEPARATION_OFFSET + arm.JAW_SEPARATION_PER_JOINT * arm.OPEN
        # The hold is never narrower than the sweep command, so an "above the
        # fruit's extent" sweep is a clean no-contact case (no saturated hold
        # has already loaded the fruit).
        hold_gap = max(extent - HOLD_MM / 1000.0, gap)

        if group == "plow":
            # The shipped re-seat trigger: the jaws are *already* at the
            # sub-width gap (closed on air) and descend onto the fruit, tracking
            # its measured position. This is the geometry the P10-E census
            # describes (`keep_gap` 1.7-17.5 mm inside the fruit, re-seated onto
            # the fruit's centre).
            place(p_settled, q_settled)
            step(40)
            # ORACLE R1 FIX: raise the jaw to the descent start (+PLOW_LIFT)
            # BEFORE closing the pads - so the pads close ON AIR and the descent
            # loop below is a pure descent onto the fruit (the shipped re-seat
            # geometry). The earlier version closed at the grip pose and let the
            # loop's first target (+40) raise the loaded jaws, which carried the
            # fruit - a probe artifact, not the re-seat.
            jaw_hi = np.asarray(arm.jaw_centre(), dtype=float) + np.array(
                [0.0, 0.0, PLOW_LIFT]
            )
            for alpha in blend:
                arm.ik_step(arm.tcp_target_for_jaw(jaw_hi))
                step(1)
            step(20)
            p_ref, q_ref, _ = fruit_state()
            jaw_ref = np.asarray(arm.jaw_centre(), dtype=float)
            tool_ref = np.asarray(arm.approach_axis(), dtype=float)
            axis_ref = np.asarray(arm.jaw_axis(), dtype=float)
            arm.set_gripper(arm.gripper_value_for_separation(gap))
            step(20)
        else:
            # Both other groups close on the fruit where it sits (on the belt)
            # with the same gentle min-jerk ramp to the hold gap, so the only
            # difference between them is whether the fruit is supported when the
            # sweep gap is commanded.
            place(p_settled, q_settled)
            step(40)
            for alpha in blend:
                arm.set_gripper(
                    arm.gripper_value_for_separation(
                        float(open_gap + alpha * (hold_gap - open_gap))
                    )
                )
                step(1)
            step(20)

            if group == "air":
                # Lift the held fruit off the belt (the shipped close -> probe
                # lift -> regrasp sequence), holding the gap.
                jaw_lift = np.asarray(arm.jaw_centre(), dtype=float)
                for alpha in blend:
                    arm.ik_step(
                        arm.tcp_target_for_jaw(
                            jaw_lift + np.array([0.0, 0.0, alpha * LIFT_M])
                        )
                    )
                    arm.set_gripper(arm.gripper_value_for_separation(hold_gap))
                    step(1)
                step(10)
                p_lifted, _, _ = fruit_state()
                row["lift_dz_mm"] = float(p_lifted[2] - p_settled[2]) * 1000.0
                if row["lift_dz_mm"] < 500.0 * LIFT_M:
                    row["hold_failed"] = 1
                    row["outcome"] = "hold_failed"

            p_ref, q_ref, _ = fruit_state()
            jaw_ref = np.asarray(arm.jaw_centre(), dtype=float)
            tool_ref = np.asarray(arm.approach_axis(), dtype=float)
            axis_ref = np.asarray(arm.jaw_axis(), dtype=float)
            arm.set_gripper(arm.gripper_value_for_separation(gap))

        row["off_tool_mm"] = float(np.dot(p_ref - jaw_ref, tool_ref)) * 1000.0
        row["off_axis_mm"] = float(np.dot(p_ref - jaw_ref, axis_ref)) * 1000.0
        row["in_span"] = int(
            abs(row["off_axis_mm"]) <= row["extent_mm"] / 2.0 + 5.0
            and abs(row["off_tool_mm"]) <= 120.0
        )
        row["sep_cmd_mm"] = gap * 1000.0

        descend_ticks = CLOSE_TICKS if group == "plow" else 0
        peak_fast = peak_all = 0.0
        tick_fast = tick_all = -1
        v_esc = float("nan")
        esc_tick = -1
        f_finger = f_fruit = 0.0
        contacts = 0
        for tick in range(descend_ticks + HOLD_TICKS + WATCH_TICKS):
            if group == "plow" and tick < descend_ticks:
                # Descend with the jaws at the sub-width gap, tracking the
                # fruit's measured position (the re-seat's own loop).
                alpha = float(blend[tick])
                p_now = fruit_state()[0]
                arm.ik_step(
                    arm.tcp_target_for_jaw(
                        np.array(
                            [
                                p_now[0],
                                p_now[1],
                                p_now[2] + standoff + PLOW_LIFT * (1.0 - alpha),
                            ]
                        )
                    )
                )
            step(1)
            p, _q, v = fruit_state()
            speed = float(np.linalg.norm(v))
            if speed > peak_all:
                peak_all, tick_all = speed, tick
            if tick < FAST_TICKS and speed > peak_fast:
                peak_fast, tick_fast = speed, tick
            disp = float(np.linalg.norm(p - p_ref))
            if esc_tick < 0 and disp > ESCAPE_M:
                esc_tick, v_esc = tick, speed
            reading = tactile.read().get(SIDE)
            if reading is not None:
                f_finger = max(f_finger, float(reading.normal_force))
                contacts = max(contacts, int(reading.contact_count))
            if fruit_force_ok:
                force = rigid.get_net_contact_forces()
                f_fruit = max(
                    f_fruit,
                    float(
                        np.linalg.norm(
                            np.asarray(to_numpy(force), dtype=float).reshape(-1)[:3]
                        )
                    ),
                )
            if TRACE and tick < 40:
                say(
                    f"[squeeze-t] case={row['case']} tick={tick:3d} |v|={speed:.3f} "
                    f"z={float(p[2]):.4f} dy={float(p[1] - p_ref[1]) * 1000:+.1f}mm "
                    f"dx={float(p[0] - p_ref[0]) * 1000:+.1f}mm F={f_finger:.2f}N"
                )

        p_end, _q_end, _v_end = fruit_state()
        d = p_end - p_ref
        f_lo_l, f_hi_l, f_lo_r, f_hi_r = finger_bounds()
        s_lo, s_hi = support_along(_q_end, np.array([1.0, 0.0, 0.0]))
        fruit_lo = float(p_end[0]) + s_lo
        fruit_hi = float(p_end[0]) + s_hi
        row.update(
            {
                "sep_end_mm": float(
                    (arm.JAW_SEPARATION_OFFSET + arm.JAW_SEPARATION_PER_JOINT * arm.finger_opening())
                    * 1000.0
                ),
                "span_end_mm": float(arm.jaw_separation() * 1000.0),
                "peak_v_fast": peak_fast,
                "tick_fast": tick_fast,
                "peak_v_all": peak_all,
                "tick_all": tick_all,
                "v_esc": v_esc,
                "esc_tick": esc_tick,
                "disp_mm": float(np.linalg.norm(d)) * 1000.0,
                "dx_mm": float(d[0]) * 1000.0,
                "dy_mm": float(d[1]) * 1000.0,
                "dz_mm": float(d[2]) * 1000.0,
                "F_finger_peak": f_finger,
                "F_fruit_peak": f_fruit,
                "contacts": contacts,
                "clear_l_mm": (fruit_lo - float(f_hi_l[0])) * 1000.0,
                "clear_r_mm": (float(f_lo_r[0]) - fruit_hi) * 1000.0,
                "finger_lo_z_mm": (min(float(f_lo_l[2]), float(f_lo_r[2])) - float(p_end[2])) * 1000.0,
                "finger_hi_z_mm": (max(float(f_hi_l[2]), float(f_hi_r[2])) - float(p_end[2])) * 1000.0,
            }
        )
        if row["hold_failed"]:
            outcome = "hold_failed"
        elif not row["in_span"]:
            outcome = "out_of_span"
        elif row["dz_mm"] < -35.0:
            outcome = "fell"
        elif row["disp_mm"] > ESCAPE_M * 1000.0:
            outcome = "escaped"
        else:
            outcome = "stayed"
        row["outcome"] = outcome
        say(
            f"[squeeze] case={row['case']} group={group} class={CLASS} "
            f"extent_mm={row['extent_mm']:.1f} gap_cmd_mm={row['gap_cmd_mm']:.1f} "
            f"sep_end_mm={row['sep_end_mm']:.1f} span_end_mm={row['span_end_mm']:.1f} "
            f"off_tool_mm={row['off_tool_mm']:+.1f} off_axis_mm={row['off_axis_mm']:+.1f} "
            f"in_span={row['in_span']} lift_dz_mm={row['lift_dz_mm']:+.1f} "
            f"peak_v_fast={row['peak_v_fast']:.3f}@{row['tick_fast']} "
            f"peak_v_all={row['peak_v_all']:.3f}@{row['tick_all']} "
            f"v_esc={row['v_esc']:.3f}@{row['esc_tick']} "
            f"disp_mm={row['disp_mm']:.1f} dx_mm={row['dx_mm']:+.1f} "
            f"dy_mm={row['dy_mm']:+.1f} dz_mm={row['dz_mm']:+.1f} "
            f"F_finger_peak={row['F_finger_peak']:.2f}N F_fruit_peak={row['F_fruit_peak']:.2f}N "
            f"contacts={row['contacts']} clear_l={row['clear_l_mm']:+.1f} "
            f"clear_r={row['clear_r_mm']:+.1f} finger_z=[{row['finger_lo_z_mm']:+.1f},"
            f"{row['finger_hi_z_mm']:+.1f}] "
            f"outcome={row['outcome']}"
        )
        return row

    for group in GROUPS:
        for delta_mm in DELTAS_MM:
            for rep in range(REPEATS):
                rows.append(run_case(group, delta_mm, rep))

    # --- resting-drop baseline ----------------------------------------------- #
    drop_rows: list[dict] = []
    if DROP:
        drop_start = np.array(
            [-0.6, 0.0, belt_top + float(-points[:, 2].min())], dtype=float
        )
        for rep in range(REPEATS):
            place(drop_start)
            step(5)
            peak = 0.0
            tick_peak = -1
            z_peak = float("nan")
            z_last = float(drop_start[2])
            for tick in range(150):
                step(1)
                p, _q, v = fruit_state()
                speed = float(np.linalg.norm(v))
                if speed > peak:
                    peak, tick_peak, z_peak = speed, tick, float(p[2])
                z_last = float(p[2])
            say(
                f"[squeeze] case=drop-r{rep} group=drop class={CLASS} "
                f"drop_h={belt_top:.3f} peak_v={peak:.3f}@{tick_peak} z_at_peak={z_peak:.4f} "
                f"z_end={z_last:.4f} outcome={'landed' if z_last < 0.06 else 'flying'}"
            )
            drop_rows.append({"peak": peak, "tick": tick_peak, "z": z_peak})

    # --- summary ------------------------------------------------------------- #
    say(
        f"[squeeze] ---- summary: class={CLASS} extent={extent * 1000:.1f}mm "
        f"d={sample.diameter * 1000:.1f}mm seed={SEED} side={SIDE} ----"
    )
    say(
        "[squeeze] group delta_mm n stayed escaped fell hold_failed out_of_span "
        "peak_v_fast med/max  v_esc med  disp med/max mm  dz med mm  F_finger med/max N"
    )
    for group in GROUPS:
        for delta_mm in DELTAS_MM:
            cell = [
                r for r in rows if r["group"] == group and r["delta_mm"] == delta_mm
            ]
            if not cell:
                continue
            n = len(cell)
            counts = {
                name: sum(1 for r in cell if r["outcome"] == name)
                for name in ("stayed", "escaped", "fell", "hold_failed", "out_of_span")
            }
            fast = np.asarray([r["peak_v_fast"] for r in cell], dtype=float)
            esc = np.asarray([r["v_esc"] for r in cell], dtype=float)
            disp = np.asarray([r["disp_mm"] for r in cell], dtype=float)
            dz = np.asarray([r["dz_mm"] for r in cell], dtype=float)
            ff = np.asarray([r["F_finger_peak"] for r in cell], dtype=float)
            esc_med = float(np.nanmedian(esc)) if np.any(np.isfinite(esc)) else float("nan")
            say(
                f"[squeeze] {group:5s} {delta_mm:5.1f} {n:2d} "
                f"{counts['stayed']:2d} {counts['escaped']:2d} {counts['fell']:2d} "
                f"{counts['hold_failed']:2d} {counts['out_of_span']:2d}   "
                f"{float(np.median(fast)):.3f}/{float(np.max(fast)):.3f}   "
                f"{esc_med:.3f}   {float(np.median(disp)):.1f}/{float(np.max(disp)):.1f}   "
                f"{float(np.median(dz)):+.1f}   "
                f"{float(np.median(ff)):.2f}/{float(np.max(ff)):.2f}"
            )
    if drop_rows:
        peaks = np.asarray([r["peak"] for r in drop_rows], dtype=float)
        say(
            f"[squeeze] drop baseline: n={len(peaks)} peak_v median {float(np.median(peaks)):.3f} "
            f"range {float(np.min(peaks)):.3f}-{float(np.max(peaks)):.3f} m/s "
            f"(free fall 1.17 m = {float(np.sqrt(2 * 9.81 * belt_top)):.3f} m/s)"
        )
    say(f"[squeeze] DONE wall={time.time() - wall0:.1f}s")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
