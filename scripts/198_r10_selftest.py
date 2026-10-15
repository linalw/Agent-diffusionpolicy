"""Offline selftest for the R10-A reach-anywhere catch (selector + intercept).

    python3 scripts/198_r10_selftest.py

No simulator. It exercises the *real* `PickAndPlaceTask.select_target`,
`_reach_anywhere_select`, `_reach_predict`, `_reach_prepare_aim` and
`_dynamic_aim` on a stubbed task (only the attributes the code reads are set),
mirroring `176_twoline_selftest.py`:

* knob off: the shipped single-arm moving-catch selection is byte-unchanged
  (farthest-upstream among the usable set above `_dynamic_select_floor`);
* knob on: a fruit inside the shipped floor but with a feasible intercept is
  selected (the R10-A coverage gain), and a fruit whose predicted interception
  point is below the arm's downstream band edge is refused;
* R11-A (the adoption attempt): the shipped defaults stay the pre-adoption
  pair - `FRUIT_REACH_ANYWHERE` default 0 / `FRUIT_REACH_HOVER_SETTLE` default
  0 (the flipped candidate replays the measured arm B but fails its own gate
  on the shipped acceptance, `logs/r11/A_RESULTS.md`) - and the direct/policy
  environment opts out of the reach *selection*
  (`select_target(..., reach_anywhere=False)` in `rl_env.py`); both are pinned
  from the source literals like `96_motion_check.py` (the defaults live in
  `__init__`, which needs Isaac Sim);
* the choice is the earliest reachable intercept (minimum fruit travel to the
  clipped intercept), ties broken by the smallest along-position;
* the intercept arithmetic: the fixed point, the band clip, the feasibility
  boundary at `station + dn`, and the per-arm band env overrides;
* the A1 hover settle (`FRUIT_REACH_HOVER_SETTLE`): the `vy*S/(1-vy/v_hover)`
  downstream shift of the priced fixed point (the selection floor and the aim
  both read it);
* the A1 capped-hover fallback (`FRUIT_REACH_HOVER_FALLBACK`,
  `FRUIT_REACH_DELIVER_MARGIN`): a residual above tolerance + margin drops the
  cached aim and rebuilds the station grip/hover targets; a converged move and
  the knob-off path are no-ops;
* the aim cache: `_reach_prepare_aim` -> `_dynamic_aim` returns the intercept
  for the same attempt key and the station aim for any other key (the
  direct-path fallback);
* both arms route by grade (A -> left, else right) and use their own band.

Run by `scripts/selfcheck.sh` before simulator time.
"""

from __future__ import annotations

import os
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks ---------- #
# (same pattern as `176_twoline_selftest.py`)
for name in (
    "pxr",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.sensors",
    "isaacsim.sensors.experimental",
):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
app_mod = types.ModuleType("isaacsim.core.experimental.utils.app")
app_mod.update_app = lambda **kwargs: None
sys.modules.setdefault("isaacsim.core.experimental.utils.app", app_mod)
utils_mod = types.ModuleType("isaacsim.core.experimental.utils")
sys.modules.setdefault("isaacsim.core.experimental.utils", utils_mod)
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)
sim_mod = types.ModuleType("isaacsim.core.simulation_manager")
sim_mod.SimulationManager = SimpleNamespace(step=staticmethod(lambda **kw: None))
sys.modules.setdefault("isaacsim.core.simulation_manager", sim_mod)
render_mod = types.ModuleType("isaacsim.core.rendering_manager")
render_mod.RenderingManager = SimpleNamespace(render=staticmethod(lambda: None))
sys.modules.setdefault("isaacsim.core.rendering_manager", render_mod)
sensors_mod = types.ModuleType("isaacsim.sensors.experimental.physics")
sensors_mod.Contact = object
sensors_mod.ContactSensor = object
sys.modules.setdefault("isaacsim.sensors.experimental.physics", sensors_mod)

import numpy as np  # noqa: E402

from fruit_sorting.tasks import PickAndPlaceTask  # noqa: E402

BELT_V = -0.12


def stub_task(*, reach: bool = True, bands=None, y_dn_left=None, y_dn_right=None,
              settle: int = 0, fallback: bool = False, margin: float = 0.0):
    """A task-shaped object carrying only what the R10-A code reads."""
    task = SimpleNamespace()
    task.cfg = SimpleNamespace(
        pick_y=0.0,
        belt_speed=BELT_V,
        belt_center=(0.34, 0.0, 1.14),
        gripper_max_object=0.072,
    )
    task.belt_top = 1.17
    task.failures = {}
    task.max_retries = 2
    task._prefer_upstream = True
    task._reach_anywhere = reach
    task._reach_band = bands or {
        "left": ((0.20, -0.08, 0.13), (0.28, -0.03, 0.08), (None, 0.02, 0.08)),
        "right": ((0.20, -0.08, 0.08), (0.28, -0.08, 0.03), (None, -0.08, -0.02)),
    }
    task._reach_setup_s = 0.60
    task._reach_hover_speed = 0.80
    task._reach_margin_s = 0.15
    task._reach_select_s = 1.5
    task._reach_hover_settle_ticks = int(settle)
    task._reach_hover_fallback = bool(fallback)
    task._reach_deliver_margin = float(margin)
    task._reach_diag = False
    task._reach_aim_key = None
    task._reach_aim_point = None
    task._attempt_sim_t0 = 0.0
    task.current_arm = "left"
    task._active_session = None
    task._dynamic_pick_lead = lambda: 0.189
    task._belt_speed_estimate = lambda: BELT_V
    task._dynamic_select_floor = (
        lambda min_lead_s=None, lead_override_s=None: PickAndPlaceTask._dynamic_select_floor(
            task, min_lead_s, lead_override_s
        )
    )
    task._balance_arm = lambda ordered: PickAndPlaceTask._balance_arm(task, ordered)
    task._pure_grade_routing = lambda: PickAndPlaceTask._pure_grade_routing(task)
    task._prepose_lead_value = lambda: PickAndPlaceTask._prepose_lead_value(task)
    task._approach_duration = (
        lambda distance, v_max, a_max=None: PickAndPlaceTask._approach_duration(
            distance, v_max, a_max
        )
    )
    task.station_y_for = lambda arm: float(task.station_y.get(arm, task.cfg.pick_y))
    task.station_y = {"left": 0.0, "right": 0.0}
    task._reach_band_for = lambda arm, x=None: PickAndPlaceTask._reach_band_for(task, arm, x)
    task._reach_fruit_arm = lambda grade: PickAndPlaceTask._reach_fruit_arm(task, grade)
    task._reach_predict = (
        lambda position, vy, arm, base_s: PickAndPlaceTask._reach_predict(
            task, position, vy, arm, base_s
        )
    )
    task._reach_anywhere_select = (
        lambda states, lane=None, prefer_lane=None, exclude=None: PickAndPlaceTask._reach_anywhere_select(
            task, states, lane, prefer_lane, exclude
        )
    )
    task._reach_anywhere_active = lambda: PickAndPlaceTask._reach_anywhere_active(task)
    task._reach_prepare_aim = (
        lambda sample: PickAndPlaceTask._reach_prepare_aim(task, sample)
    )
    task._reach_capped_fallback = (
        lambda sample, residual, tolerance: PickAndPlaceTask._reach_capped_fallback(
            task, sample, residual, tolerance
        )
    )
    task._dynamic_aim = lambda sample: PickAndPlaceTask._dynamic_aim(task, sample)
    task._dynamic_grip_point = (
        lambda sample: PickAndPlaceTask._dynamic_grip_point(task, sample)
    )
    task._dynamic_hover_point = (
        lambda sample: PickAndPlaceTask._dynamic_hover_point(task, sample)
    )
    task._pad_standoff = lambda dynamic=False, sample=None: 0.12
    task._two_line_catch_lead = lambda: PickAndPlaceTask._two_line_catch_lead(task)
    return task


def fruit(index: int, grade: str, y: float, *, x: float = 0.28, diameter: float = 0.06,
          vy: float = BELT_V):
    return {
        "index": index,
        "grade": grade,
        "diameter": diameter,
        "position": np.array([x, y, 1.17 + diameter / 2.0]),
        "velocity": np.array([0.0, vy, 0.0]),
    }


class FakeSample:
    def __init__(self, index: int, y: float, *, x: float = 0.28, vy: float = BELT_V):
        self.index = index
        self.diameter = 0.06
        self._pos = np.array([x, y, 1.17 + 0.03])
        self._vel = np.array([0.0, vy, 0.0])


class FakeSpawner:
    def __init__(self, sample):
        self._sample = sample

    def position(self, sample):
        return np.asarray(sample._pos, dtype=float)

    def velocity(self, sample):
        return np.asarray(sample._vel, dtype=float)


def select(task, states, **kwargs):
    return PickAndPlaceTask.select_target(task, states, **kwargs)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok: {message}")


def near(value: float, target: float, tol: float, label: str) -> None:
    if abs(value - target) > tol:
        raise AssertionError(f"{label}: {value} != {target} (+/- {tol})")
    print(f"ok: {label} ({value:.4f} ~ {target:.4f})")


def main() -> int:
    # --- 0. the shipped defaults and the map's bands ---------------------- #
    # R11-A: the default flip was measured and rejected by its own gate (the
    # shipped acceptance 9/10 -> 4/10, `logs/r11/A_RESULTS.md`), so the shipped
    # pair stays off; the candidate is `FRUIT_REACH_ANYWHERE=1
    # FRUIT_REACH_HOVER_SETTLE=60` (the R10-A.1 arm B). The direct/policy
    # environment opts out of the reach selection. The defaults live in
    # `tasks.py`'s `__init__`, which imports Isaac Sim and cannot be imported
    # here, so the source literals + the opt-out call are pinned directly -
    # the `96_motion_check.py` pattern; drift is a hard failure.
    tasks_src = (Path(ROOT) / "src" / "fruit_sorting" / "tasks.py").read_text(
        encoding="utf-8"
    )
    rl_env_src = (Path(ROOT) / "src" / "fruit_sorting" / "rl_env.py").read_text(
        encoding="utf-8"
    )
    check(re.search(r'FRUIT_REACH_ANYWHERE",\s*"0"', tasks_src) is not None,
          "the shipped default keeps the reach catch off (FRUIT_REACH_ANYWHERE default 0)")
    check(re.search(r'FRUIT_REACH_HOVER_SETTLE",\s*"0"', tasks_src) is not None,
          "the shipped default keeps the hover settle off (FRUIT_REACH_HOVER_SETTLE default 0)")
    check(re.search(r"reach_anywhere=False", rl_env_src) is not None,
          "the direct/policy selection opts out of the reach rule (rl_env.py)")
    task = stub_task(reach=False)
    check(task._reach_anywhere_active() is False,
          "the knob off is a no-op (the pre-adoption line byte-for-byte)")
    task_on = stub_task(reach=True)
    check(task_on._reach_anywhere_active() is True,
          "the knob enables the reach-anywhere path on the moving-catch line")

    # --- 1. knob off: the shipped single-arm selection is unchanged ------- #
    shipped_floor = PickAndPlaceTask._dynamic_select_floor(task_on)
    print(f"shipped floor above the station: {shipped_floor:.3f} m")
    above = fruit(1, "B", shipped_floor + 0.01)
    below = fruit(2, "B", shipped_floor - 0.05)
    far = fruit(3, "B", shipped_floor + 0.30)
    chosen = select(task, [above, below, far])
    check(chosen is not None and chosen["index"] == 3,
          "knob off: the farthest-upstream usable fruit is selected (shipped rule)")
    check(select(task, [below]) is None,
          "knob off: a fruit below the shipped floor is refused")

    # --- 2. knob on: the coverage gain inside the shipped floor ----------- #
    # A fruit the shipped floor refuses but whose intercept is inside the band.
    # With beltable V=-0.12: eq = y + (-0.12)*(1.5 + 0.7 + 0.15 + travel).
    inside = fruit(4, "B", shipped_floor - 0.05)  # ~+0.34
    pred = task_on._reach_predict(
        inside["position"], BELT_V, "right", task_on._reach_select_s
    )
    print(
        f"inside candidate: y={inside['position'][1]:+.3f} -> intercept "
        f"{pred['y']:+.3f} (eq {pred['eq']:+.3f}, feasible {pred['feasible']})"
    )
    check(pred["feasible"], "the inside-floor fruit has a feasible intercept")
    chosen = select(task_on, [inside])
    check(chosen is not None and chosen["index"] == 4,
          "knob on: a fruit inside the shipped floor is selected (coverage gain)")

    # --- 2b. the direct/policy opt-out (R11-A scope) ----------------------- #
    # `reach_anywhere=False` is what `rl_env.py`'s direct presentation passes:
    # the shipped floor is restored for that call even with the knob on.
    check(select(task_on, [inside], reach_anywhere=False) is None,
          "reach_anywhere=False keeps the shipped floor (the direct/policy pin)")
    picked = select(task_on, [above], reach_anywhere=False)
    check(picked is not None and picked["index"] == 1,
          "reach_anywhere=False still selects above the floor (shipped rule)")
    picked = select(task_on, [above])
    check(picked is not None and picked["index"] == 1,
          "the default (scripted) call is unaffected by the opt-out")

    # --- 3. the band is the feasibility boundary -------------------------- #
    # Push the same fruit down until the predicted intercept falls below dn.
    dnf, upf = task_on._reach_band_for("right", 0.28)
    edge = None
    for y in np.arange(0.45, -0.30, -0.005):
        p = task_on._reach_predict(
            np.array([0.28, float(y), 1.20]), BELT_V, "right", task_on._reach_select_s
        )
        if not p["feasible"]:
            edge = float(y)
            break
    print(f"right arm: the feasibility edge sits at y = {edge:+.3f} (band dn {dnf:+.3f}, stall setup {task_on._reach_select_s}s)")
    check(edge is not None and 0.10 < edge < 0.40,
          "the right band's feasibility edge is a real boundary (fruit below it refused)")
    below_edge = fruit(5, "B", edge - 0.05 if edge is not None else 0.0)
    check(select(task_on, [below_edge]) is None,
          "knob on: a fruit past the band edge is refused by the reach rule")

    # --- 4. earliest reachable intercept, ties to the nearest ------------- #
    near_f = fruit(6, "B", 0.25)
    far_f = fruit(7, "B", 0.55)
    chosen = select(task_on, [far_f, near_f])
    check(chosen is not None and chosen["index"] == 6,
          "the earliest reachable intercept wins (nearest catchable fruit)")
    # Two immediately catchable fruit: the nearer (shorter hover) wins.
    a = fruit(8, "B", 0.30)
    b = fruit(9, "B", 0.42)
    chosen = select(task_on, [b, a])
    check(chosen is not None and chosen["index"] == 8,
          "among immediately catchable fruit the nearest is taken")

    # --- 5. the band clip: a far fruit intercepts at the upstream edge ---- #
    far_away = fruit(10, "B", 0.80)
    pred = task_on._reach_predict(
        far_away["position"], BELT_V, "right", task_on._reach_select_s
    )
    near(pred["y"], task_on.station_y_for("right") + upf, 1e-9,
         "a far fruit's intercept is clipped to the upstream band edge")
    check(pred["feasible"], "a far fruit's intercept is feasible (the wait absorbs)")
    check(pred["travel_s"] > 0.0, "the travel time to the clipped intercept is positive")

    # --- 6. per-arm bands and the fixed point ----------------------------- #
    # The left arm's band default is upstream-shifted; the same fruit routes
    # differently. Check the env override form the probe uses.
    flat = {"left": ((None, -0.06, 0.13),), "right": ((None, -0.20, 0.02),)}
    task_env = stub_task(reach=True, bands=flat)
    p_env = task_env._reach_predict(
        np.array([0.28, 0.20, 1.20]), BELT_V, "right", task_env._reach_select_s
    )
    check(task_env._reach_band_for("right", 0.30) == (-0.20, 0.02),
          "a flattened per-arm band is honoured (the env-override form)")
    check(task_on._reach_band_for("left", 0.36) == (0.02, 0.08),
          "the x column picks the outer band (left x=0.36; the inset sign is +)")
    check(task_on._reach_band_for("left", 0.18) == (-0.08, 0.13),
          "x at/below the first measured column gets the inner band")
    check(task_on._reach_band_for("left", 0.22) == (-0.03, 0.08),
          "x between measured columns takes the next (nested, narrower) column's band")
    # Fixed point: the travel term makes the intercept downstream of the flat
    # estimate by exactly the extra setup it prices. Verify against a direct
    # solution of the same equation.
    y0 = 0.40
    flat = y0 + BELT_V * (task_env._reach_select_s + p_env["t_desc"] + task_env._reach_margin_s)
    y_sol = flat
    for _ in range(60):
        y_sol = y0 + BELT_V * (
            task_env._reach_select_s
            + abs(y_sol - task_env.station_y_for("right")) / task_env._reach_hover_speed
            + p_env["t_desc"]
            + task_env._reach_margin_s
        )
    p_fix = task_env._reach_predict(
        np.array([0.28, y0, 1.20]), BELT_V, "right", task_env._reach_select_s
    )
    near(p_fix["eq"], y_sol, 2e-4, "the bounded fixed point converges to the solution")

    # --- 6b. A1: the hover settle is priced into the fixed point ---------- #
    # `FRUIT_REACH_HOVER_SETTLE=60` (0.5 s) must move the prediction downstream
    # by exactly `vy*S/(1 - vy/v_hover)` (both fixed points upstream of the
    # station, so the abs() terms subtract linearly).
    task_set = stub_task(reach=True, settle=60)
    task_off = stub_task(reach=True)
    p_off = task_off._reach_predict(
        np.array([0.28, y0, 1.20]), BELT_V, "right", task_off._reach_select_s
    )
    p_set = task_set._reach_predict(
        np.array([0.28, y0, 1.20]), BELT_V, "right", task_set._reach_select_s
    )
    settle_shift = BELT_V * 0.5 / (1.0 - BELT_V / task_set._reach_hover_speed)
    near(p_set["eq"] - p_off["eq"], settle_shift, 5e-4,
         "60 settle ticks shift the intercept by vy*S/(1-vy/v_hover) (downstream)")
    check(p_set["eq"] < p_off["eq"],
          "the settle shift is toward the belt flow (a later, downstream catch)")
    settle_far = fruit(20, "B", 0.80)
    p_far_set = task_set._reach_predict(
        settle_far["position"], BELT_V, "right", task_set._reach_select_s
    )
    near(p_far_set["y"], task_set.station_y_for("right") + task_set._reach_band_for("right", 0.28)[1],
         1e-9, "with the settle on, a far fruit still clips to the band edge")

    # --- 7. the aim cache: scripted aim vs the station fallback ----------- #
    aim_task = stub_task(reach=True)
    sample = FakeSample(11, 0.30)
    aim_task.spawner = FakeSpawner(sample)
    aim_task.current_arm = "right"
    aim_task._reach_anywhere_active = lambda: True
    aim_task._reach_intercept_side = None
    # `_reach_prepare_aim` reads `spawner.position/velocity` and the key parts.
    PickAndPlaceTask._reach_prepare_aim(aim_task, sample)
    check(aim_task._reach_aim_point is not None, "a feasible aim is cached")
    cached = aim_task._reach_aim_point
    aim = PickAndPlaceTask._dynamic_aim(aim_task, sample)
    near(float(aim[1]), float(cached[1]), 1e-9,
         "the cached intercept is returned as the aim's along-belt coordinate")
    near(float(aim[0]), float(cached[0]), 1e-9, "the aim's x is the fruit's measured x")
    # A different attempt key (the direct/non-scripted call) falls back to the
    # shipped station aim.
    aim_task._attempt_sim_t0 = 123.0
    fallback = PickAndPlaceTask._dynamic_aim(aim_task, sample)
    near(float(fallback[1]), aim_task.station_y_for("right"), 1e-9,
         "a stale key falls back to the station aim (the shipped path)")
    # Infeasible aim -> no cache -> the station fallback.
    deep = FakeSample(12, -0.30)
    aim_task.spawner = FakeSpawner(deep)
    aim_task._attempt_sim_t0 = 456.0
    PickAndPlaceTask._reach_prepare_aim(aim_task, deep)
    check(aim_task._reach_aim_point is None,
          "an infeasible interception point leaves the shipped aim in place")

    # --- 7b. A1: the capped-hover fallback re-aims at the station ---------- #
    def fallback_probe(*, fallback: bool, margin: float = 0.0, index: int = 21,
                       y0: float = 0.30, residual: float, tolerance: float = 0.008):
        t = stub_task(reach=True, fallback=fallback, margin=margin)
        s = FakeSample(index, y0)
        t.spawner = FakeSpawner(s)
        t.current_arm = "right"
        t._reach_anywhere_active = lambda: True
        t._attempt_sim_t0 = 100.0
        PickAndPlaceTask._reach_prepare_aim(t, s)
        cached = t._reach_aim_point is not None
        fired = PickAndPlaceTask._reach_capped_fallback(t, s, residual, tolerance)
        return t, cached, fired

    fb, cached, fired = fallback_probe(fallback=True, residual=0.02)
    check(cached, "fallback stub: the reach aim is cached")
    check(fired and fb._reach_aim_point is None,
          "a capped hover move drops the reach aim (the fallback fires)")
    near(float(fb._dynamic_grip_target[1]), fb.station_y_for("right"), 1e-9,
         "the rebuilt grip target is the station aim")
    near(float(fb._dynamic_hover_target[1]), fb.station_y_for("right"), 1e-9,
         "the rebuilt hover target is the station hover")
    t2, cached2, fired2 = fallback_probe(fallback=True, residual=0.005, index=22)
    check(cached2 and not fired2 and t2._reach_aim_point is not None,
          "a converged hover move keeps the reach aim")
    t3, _, fired3 = fallback_probe(fallback=False, residual=0.02, index=23)
    check(not fired3 and t3._reach_aim_point is not None,
          "the fallback knob off is a no-op (the aim is kept)")
    t4, _, fired4 = fallback_probe(fallback=True, margin=0.02, residual=0.02, index=24)
    check(not fired4 and t4._reach_aim_point is not None,
          "the deliverability margin admits a near-cap residual (tol + margin)")
    t5, _, fired5 = fallback_probe(fallback=True, margin=0.02, residual=0.05, index=25)
    check(fired5 and t5._reach_aim_point is None,
          "a residual past tol + margin still fires with the margin on")

    # --- 8. the two-line guard -------------------------------------------- #
    bi = stub_task(reach=True)
    bi._active_session = SimpleNamespace(twoline=True)
    check(bi._reach_anywhere_active() is False,
          "the two-line session is excluded (its stations are its clearance)")
    # The *shared-station* bimanual (`FRUIT_BIARM=1`, twoline False) runs the
    # same scripted moving catch, so the knob reaches it - a scope note, not a
    # second guard (the combination is opt-in).
    shared = stub_task(reach=True)
    shared._active_session = SimpleNamespace(twoline=False)
    check(shared._reach_anywhere_active() is True,
          "a non-two-line session keeps the reach rule (the shared-station scope note)")

    print("r10 reach-anywhere selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
