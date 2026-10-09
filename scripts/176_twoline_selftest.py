"""Offline selftest for the v9/V2 two-line selector and pre-pose-lock decision.

    python3 scripts/176_twoline_selftest.py

No simulator. It exercises the *real* `PickAndPlaceTask.select_target` on a
stubbed task (only the attributes the selector reads are set) plus
`_two_line_prepose_locked`, so the acceptance can trust the two-line rules
before any Isaac Sim time is spent:

* per-arm station windows: the moving catch's `_dynamic_select_floor` is
  measured from the arm's own station (`station_y`), so a fruit below the floor
  of the downstream station is not selectable there;
* `prefer_lane` with `lane=None` under the **W3 pure grade routing** (default):
  the left arm (lane 0) takes grade A only, the right (lane 1) grade B only,
  grade C is never selected, and there is no cross-grade fallback;
* `FRUIT_GRADE_ROUTING=0` restores the V2 grade preference with the any-grade
  fallback (the checks below are grouped accordingly);
* `exclude`: a fruit protected by the other arm's in-flight attempt is never
  selected;
* the legacy `lane=` grade filter is unchanged;
* the pre-pose lock is required only when an off-centre station fell back to
  the shared grasp configuration.

Mirrors `scripts/152_biarm_selftest.py`'s role: a pure-Python pin of the new
mechanism, run by `scripts/selfcheck.sh` before simulator time.
"""

from __future__ import annotations

import os
import sys
import types
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks ---------- #
# (same pattern as `172_supply_selftest.py`: only the pure selector logic runs)
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


def stub_task(*, pick_y: float = 0.0, prefer_upstream: bool = True):
    """A task-shaped object carrying only what `select_target` reads."""
    task = SimpleNamespace()
    task.cfg = SimpleNamespace(
        pick_y=pick_y,
        belt_speed=-0.12,
        belt_center=(0.34, 0.0, 1.14),
        gripper_max_object=0.072,
    )
    task.belt_top = 1.17
    task.failures = {}
    task.max_retries = 2
    task._prefer_upstream = prefer_upstream
    task._belt_speed_estimate = lambda: -0.12
    task._dynamic_pick_lead = lambda: 0.189
    task._dynamic_select_floor = lambda min_lead_s=None: PickAndPlaceTask._dynamic_select_floor(
        task, min_lead_s
    )
    task._balance_arm = lambda ordered: PickAndPlaceTask._balance_arm(task, ordered)
    task._pure_grade_routing = lambda: PickAndPlaceTask._pure_grade_routing(task)
    task.station_y_for = lambda arm: float(task.station_y.get(arm, task.cfg.pick_y))
    task.station_y = {"left": 0.0, "right": -0.10}
    task._station_grasp = {}
    return task


def fruit(index: int, grade: str, y: float, *, x: float = 0.28, diameter: float = 0.06):
    return {
        "index": index,
        "grade": grade,
        "diameter": diameter,
        "position": np.array([x, y, 1.17 + diameter / 2.0]),
        "velocity": np.array([0.0, -0.12, 0.0]),
    }


def select(task, states, **kwargs):
    return PickAndPlaceTask.select_target(task, states, **kwargs)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok: {message}")


def main() -> int:
    task = stub_task()
    # The V2 fallback semantics checks below run with the routing knob off; the
    # W3 pure per-arm routing is checked separately after them.
    os.environ["FRUIT_GRADE_ROUTING"] = "0"
    # Floor = lead 0.189 + 1.5 s * 0.12 + 0.03 = 0.399 above the station.
    floor = task._dynamic_pick_lead() + 0.12 * 1.5 + 0.03
    print(f"selector floor above the station: {floor:.3f} m")

    # 1. The floor is measured from the arm's own station.
    below_right_floor = fruit(0, "A", 0.20 - floor + 0.02)  # 0.02 above right floor? no
    above_right_floor = fruit(1, "A", -0.20 + floor + 0.01)
    below = select(task, [below_right_floor], station_y=-0.20, prefer_lane=0)
    check(below is None, "fruit under the downstream station's floor is refused")
    above = select(task, [above_right_floor], station_y=-0.20, prefer_lane=0)
    check(above is not None and above["index"] == 1,
          "fruit above the downstream station's floor is selectable")

    # 2. prefer_lane picks the lane's grade even when a cross-lane fruit is nearer.
    a_far = fruit(2, "A", 0.60)
    b_near = fruit(3, "B", 0.50)
    chosen = select(task, [a_far, b_near], station_y=0.0, prefer_lane=0)
    check(chosen is not None and chosen["index"] == 2,
          "lane 0 prefers grade A over a nearer grade B")
    chosen = select(task, [a_far, b_near], station_y=0.0, prefer_lane=1)
    check(chosen is not None and chosen["index"] == 3,
          "lane 1 prefers grade B over a farther grade A")
    chosen = select(task, [a_far, b_near], station_y=0.0)
    check(chosen is not None and chosen["index"] == 2,
          "no preference keeps the single-arm farthest-upstream rule")

    # 3. Fallback: no lane-grade fruit -> the nearest any-grade fruit (no starvation).
    chosen = select(task, [b_near], station_y=0.0, prefer_lane=0)
    check(chosen is not None and chosen["index"] == 3,
          "lane 0 falls back to a cross-lane fruit instead of starving")
    # ... but never below the floor.
    deep_b = fruit(4, "B", 0.30)
    check(select(task, [deep_b], station_y=0.0, prefer_lane=0) is None,
          "the fallback still respects the catch floor")

    # 4. Nearest preferred wins among several.
    a_near = fruit(5, "A", 0.45)
    a_mid = fruit(6, "A", 0.55)
    chosen = select(task, [a_mid, a_near, b_near], station_y=0.0, prefer_lane=0)
    check(chosen is not None and chosen["index"] == 5,
          "the nearest preferred fruit is taken (shortest hover)")

    # 5. exclude: the other arm's protected target is never selected.
    chosen = select(task, [a_near, a_mid], station_y=0.0, prefer_lane=0,
                    exclude={5})
    check(chosen is not None and chosen["index"] == 6,
          "an excluded (protected) fruit is skipped")
    check(select(task, [a_near], station_y=0.0, prefer_lane=0, exclude={5}) is None,
          "exclusion can empty the window")

    # 6. The legacy lane grade filter is unchanged.
    check(select(task, [b_near], lane=0) is None,
          "lane=0 is still grade-filtered (V1 semantics preserved)")
    check(select(task, [b_near], lane=1)["index"] == 3,
          "lane=1 takes the B fruit")

    # 6b. W3 pure grade routing (default): left = A only, right = B only, C
    # never selected, no cross-grade fallback.
    os.environ.pop("FRUIT_GRADE_ROUTING", None)
    check(PickAndPlaceTask._pure_grade_routing(task) is True,
          "pure routing is the default when the knob is unset")
    c_far = fruit(7, "C", 0.60)
    chosen = select(task, [a_far, b_near, c_far], station_y=0.0, prefer_lane=0)
    check(chosen is not None and chosen["index"] == 2,
          "pure lane 0 selects the grade-A fruit")
    chosen = select(task, [a_far, b_near, c_far], station_y=-0.10, prefer_lane=1)
    check(chosen is not None and chosen["index"] == 3,
          "pure lane 1 selects the grade-B fruit")
    check(select(task, [c_far], station_y=0.0, prefer_lane=0) is None,
          "grade C is refused by lane 0 (unsorted, passes the line)")
    check(select(task, [c_far], station_y=0.0, prefer_lane=1) is None,
          "grade C is refused by lane 1")
    check(select(task, [b_near], station_y=0.0, prefer_lane=0) is None,
          "pure lane 0 does not fall back to a cross-grade fruit")
    check(select(task, [a_near], station_y=0.0, prefer_lane=1) is None,
          "pure lane 1 does not fall back to a cross-grade fruit")
    check(select(task, [fruit(8, "A", 0.30)], station_y=0.0, prefer_lane=0) is None,
          "pure routing still respects the catch floor")
    # The single-arm path (no prefer_lane) keeps its own behaviour: it may pick
    # any grade, C included - the shipped single-arm default is unchanged.
    chosen = select(task, [c_far, b_near])
    check(chosen is not None and chosen["index"] == 7,
          "single-arm selection (no prefer_lane) still sees grade C")
    # Explicit knob values.
    os.environ["FRUIT_GRADE_ROUTING"] = "0"
    check(PickAndPlaceTask._pure_grade_routing(task) is False,
          "FRUIT_GRADE_ROUTING=0 restores the V2 fallback")
    os.environ["FRUIT_GRADE_ROUTING"] = "pure"
    check(PickAndPlaceTask._pure_grade_routing(task) is True,
          "an explicit non-fallback value keeps purity")
    os.environ["FRUIT_GRADE_ROUTING"] = "0"

    # 7. Pre-pose lock: only an unsolved off-centre station requires it.
    lock_task = stub_task()
    lock_task.station_y = {"left": 0.0, "right": -0.10}
    lock_task._station_grasp = {}
    check(PickAndPlaceTask._two_line_prepose_locked(lock_task) is True,
          "off-centre station without its own pre-pose -> lock required")
    lock_task._station_grasp = {(0.0, -0.10): {"right": np.zeros(7)}}
    check(PickAndPlaceTask._two_line_prepose_locked(lock_task) is False,
          "solved off-centre stations -> lock not needed")
    lock_task.station_y = {"left": 0.0, "right": 0.0}
    lock_task._station_grasp = {}
    check(PickAndPlaceTask._two_line_prepose_locked(lock_task) is False,
          "shared station (single arm) -> lock not needed")

    os.environ.pop("FRUIT_GRADE_ROUTING", None)
    print("two-line selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
