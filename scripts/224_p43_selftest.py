"""Offline selftest of the P43-L1 selector scope (`direct` keyword).

    python3 scripts/224_p43_selftest.py

No simulator. The **real** `select_target` runs on a stubbed task (the
`213_prepared_next_selftest.py` / `198` / `176` pattern), so what is pinned is
the code the runs use, not a copy of it.

What this pins, and why each one matters:

1. **The flag protects the direct/policy path.** With
   `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` unset, the direct environment's call
   (`direct=True`, `rl_env.py`) takes the shipped **farthest-upstream** pick -
   whatever the scripted line's default is. The rule is the same code that loop
   reaches (its task runs `_prefer_upstream`), so without the flag a flip of the
   scripted default would silently re-baseline every direct store and direct A/B
   (P33/W7-C/W8-A/R9/P35/P36/P37/P38). The measured F5 gate is exactly this
   (`logs/p43/P2_RESULTS.md`: unset and `=0` select the same fruit, `=1` moves it).
2. **The scripted default is a named constant** (`NEAREST_ABOVE_FLOOR_SCRIPTED`,
   **off** in the shipped tree: the P43 flip was measured and not adopted) and
   the scripted call follows it.
3. **The env value wins on both paths** (the regrasp-cap precedent): `=0` gives
   the shipped pick everywhere, `=1` arms the rule everywhere - which is how the
   measured treatment arm stays reproducible without a code change.
4. **The two-line selector and the shared-station worker cannot reach the rule**:
   their calls pass `prefer_lane=` / `lane=` and return above it. The test
   asserts a **three-way identity** on those calls - the same fruit with the env
   unset, `=0` and `=1` - and that the returned fruit is the nearest of its lane
   (so it is not accidentally the `_balance_arm` pick).
5. **The call sites say so** (AST, no text matching): every `select_target` call
   inside `src/fruit_sorting/tasks.py` passes `lane=` or `prefer_lane=` (or is a
   `**kwargs` pass-through / a one-item re-check), and every unlaned call in
   `src/fruit_sorting/rl_env.py` passes `direct=True`.
6. **Provenance**: `rl_env.py`'s `TASKS_MD5` pin matches `tasks.py` (a stale pin
   makes the direct env refuse to start - the P39/R11-A failure mode).
7. **The arm park's default and scope** (P43 phase 4, A1): the resolved park is
   `back` on the **direct** presentation and empty on `handoff` (an unscoped
   default would make every handoff construction raise), `=ready` restores the
   shipped pose everywhere (the pre-P43 reproduction), an explicit value always
   wins, and both the printed rows and the manifest name the resolved state -
   the `[park]` row with the **per-arm** resolution, the manifest with
   `defaulted`. The `+` rows pin the guard and the two label sites textually,
   which is all an offline test can do for code that needs a simulator.

Run by `scripts/selfcheck.sh`.
"""

from __future__ import annotations

import ast
import hashlib
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks ---------- #
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

from fruit_sorting.tasks import (  # noqa: E402
    NEAREST_ABOVE_FLOOR_SCRIPTED,
    PickAndPlaceTask,
)

BELT_V = -0.12
SRC = Path(ROOT, "src", "fruit_sorting")
TASKS_SRC = (SRC / "tasks.py").read_text(encoding="utf-8")
RL_ENV_SRC = (SRC / "rl_env.py").read_text(encoding="utf-8")
KNOB = "FRUIT_SELECT_NEAREST_ABOVE_FLOOR"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok: {message}")


# --------------------------------------------------------------------------- #
# The stubbed task (exactly what `select_target` reads on the single-arm branch)
# --------------------------------------------------------------------------- #
def stub_task(*, prefer_upstream: bool = True):
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
    task._prefer_upstream = bool(prefer_upstream)
    task._reach_anywhere = False
    task._reach_diag = False
    task._reach_aim_key = None
    task._reach_aim_point = None
    task._active_session = None
    task.station_y = {"left": 0.0, "right": -0.10}
    task._episodes_by_arm = {"left": 0, "right": 0}
    task._dynamic_pick_lead = lambda: 0.189
    task._belt_speed_estimate = lambda: BELT_V
    task._dynamic_select_floor = (
        lambda min_lead_s=None, lead_override_s=None: (
            PickAndPlaceTask._dynamic_select_floor(
                task, min_lead_s, lead_override_s
            )
        )
    )
    task._balance_arm = lambda ordered: PickAndPlaceTask._balance_arm(task, ordered)
    task._pure_grade_routing = lambda: PickAndPlaceTask._pure_grade_routing(task)
    task._reach_anywhere_active = lambda: PickAndPlaceTask._reach_anywhere_active(task)
    task._reach_anywhere_select = (
        lambda states, lane=None, prefer_lane=None, exclude=None: (
            PickAndPlaceTask._reach_anywhere_select(
                task, states, lane, prefer_lane, exclude
            )
        )
    )
    task.station_y_for = lambda arm: float(task.station_y.get(arm, task.cfg.pick_y))
    task.select_target = (
        lambda states, **kwargs: PickAndPlaceTask.select_target(task, states, **kwargs)
    )
    task._sim_time = lambda: 100.0
    return task


def fruit(index: int, grade: str, y: float, *, x: float = 0.28, diameter: float = 0.06):
    return {
        "index": index,
        "grade": grade,
        "diameter": diameter,
        "position": np.array([x, y, 1.17 + diameter / 2.0]),
        "velocity": np.array([0.0, BELT_V, 0.0]),
    }


# Two eligible candidates per grade lane, all above the catch floor (~0.40 m),
# ordered so that nearest != farthest in both the unlaned and the per-lane set.
ROWS = [
    fruit(0, "A", 0.45),
    fruit(1, "B", 0.55),
    fruit(2, "A", 0.70),
    fruit(3, "B", 0.82),
]


def chosen(task, **kwargs) -> int | None:
    state = task.select_target(kwargs.pop("states", ROWS), **kwargs)
    return None if state is None else int(state["index"])


def with_env(value):
    """Context manager: set/clear the knob and restore it."""

    class _Ctx:
        def __enter__(self):
            self._prev = os.environ.get(KNOB)
            if value is None:
                os.environ.pop(KNOB, None)
            else:
                os.environ[KNOB] = value

        def __exit__(self, *exc):
            if self._prev is None:
                os.environ.pop(KNOB, None)
            else:
                os.environ[KNOB] = self._prev
            return False

    return _Ctx()


# --------------------------------------------------------------------------- #
# 1. The scoped default
# --------------------------------------------------------------------------- #
def test_scope_default() -> None:
    print("[1] the direct/policy path and the scripted default (env unset)")
    task = stub_task()
    with with_env(None):
        scripted = chosen(task)
        direct = chosen(task, direct=True)
    check(
        direct == 3,
        f"direct/policy call (direct=True) keeps the shipped FARTHEST-upstream "
        f"pick ({direct} == 3) whatever the scripted default is",
    )
    if NEAREST_ABOVE_FLOOR_SCRIPTED == "1":
        check(scripted == 0, f"scripted default ON: nearest ({scripted} == 0)")
    else:
        check(scripted == 3, f"scripted default OFF: shipped pick ({scripted} == 3)")
    check(
        NEAREST_ABOVE_FLOOR_SCRIPTED == "0",
        "the shipped scripted default is OFF (the P43 flip measured and not "
        "adopted, logs/p43/P2_RESULTS.md)",
    )
    # The floor itself is untouched: nearest-above-floor never selects below it.
    below = [fruit(9, "A", 0.20)]
    with with_env(None):
        none_below = task.select_target(below)
    check(
        none_below is None,
        "a candidate below the catch floor is still refused (0.20 m < the ~0.40 m floor)",
    )


# --------------------------------------------------------------------------- #
# 2. An explicit env value wins on both paths
# --------------------------------------------------------------------------- #
def test_env_wins() -> None:
    print("[2] an explicit env value wins on both paths")
    task = stub_task()
    with with_env("0"):
        scripted = chosen(task)
        direct = chosen(task, direct=True)
    check(scripted == 3, f"=0 keeps the shipped pick on the scripted path ({scripted} == 3)")
    check(direct == 3, f"=0 keeps the shipped pick on the direct path ({direct} == 3)")
    with with_env("1"):
        scripted = chosen(task)
        direct = chosen(task, direct=True)
    check(scripted == 0, f"=1 arms the near rule on the scripted path ({scripted} == 0)")
    check(
        direct == 0,
        f"=1 arms it on the direct path too ({direct} == 0) - so the measured "
        "treatment arm (unset-with-the-default-on) = `=1` on the shipped tree",
    )


# --------------------------------------------------------------------------- #
# 3. The two-line selector / shared-station worker are above the rule
# --------------------------------------------------------------------------- #
def test_lane_callers_are_above_the_rule() -> None:
    print("[3] lane / prefer_lane calls are structurally above the rule")
    task = stub_task()
    for label, kwargs, expected in (
        ("lane=0 (shared-station worker, left)", {"lane": 0}, 0),
        ("lane=1 (shared-station worker, right)", {"lane": 1}, 1),
        ("prefer_lane=0 (two-line, left)", {"prefer_lane": 0}, 0),
        ("prefer_lane=1 (two-line, right)", {"prefer_lane": 1}, 1),
    ):
        seen = set()
        for value in (None, "0", "1"):
            with with_env(value):
                seen.add(chosen(task, **kwargs))
        check(
            len(seen) == 1,
            f"{label}: the same fruit with the env unset/0/1 ({sorted(seen)})",
        )
        check(
            seen == {expected},
            f"{label}: nearest of its own lane ({sorted(seen)} == [{expected}])",
        )


# --------------------------------------------------------------------------- #
# 4. The call sites (AST, not text)
# --------------------------------------------------------------------------- #
def _select_target_calls(source: str, path: str) -> list[dict]:
    """Every `select_target(...)` call: line, keywords, `**` expansion, arity."""
    tree = ast.parse(source, filename=path)
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "select_target":
            continue
        first = node.args[0] if node.args else None
        single_item = (
            isinstance(first, (ast.List, ast.Tuple)) and len(first.elts) == 1
        )
        calls.append(
            {
                "line": getattr(node, "lineno", 0),
                "keywords": {kw.arg for kw in node.keywords if kw.arg},
                "star": any(kw.arg is None for kw in node.keywords),
                "single_item": single_item,
            }
        )
    return calls


def test_call_sites() -> None:
    print("[4] the call sites (AST)")
    task_calls = _select_target_calls(TASKS_SRC, "tasks.py")
    check(bool(task_calls), f"tasks.py has {len(task_calls)} select_target call sites")

    def laned(call) -> bool:
        return "lane" in call["keywords"] or "prefer_lane" in call["keywords"]

    unlaned = [call for call in task_calls if not laned(call)]
    # Two shapes are allowed to be unlaned: a `**kwargs` pass-through (it
    # forwards the caller's own lane/prefer_lane - the prepared-next ranking) and
    # a one-item re-check (nearest == farthest on a single candidate, so the rule
    # cannot change its answer). Everything else must pass a lane.
    bad = [
        call["line"]
        for call in unlaned
        if not call["star"] and not call["single_item"]
    ]
    check(
        not bad,
        "every unlaned in-module select_target call is a **-pass-through or a "
        f"one-item re-check; offending lines: {bad}",
    )
    check(
        any(call["star"] for call in unlaned),
        "the prepared-next ranking forwards its caller's kwargs "
        f"({[c['line'] for c in unlaned if c['star']]})",
    )
    check(
        any(call["single_item"] for call in unlaned),
        "the prepared-next consume re-checks one item at a time "
        f"({[c['line'] for c in unlaned if c['single_item']]})",
    )

    env_calls = _select_target_calls(RL_ENV_SRC, "rl_env.py")
    check(bool(env_calls), f"rl_env.py has {len(env_calls)} select_target call sites")
    bad_env = [
        call["line"]
        for call in env_calls
        if not laned(call) and "direct" not in call["keywords"]
    ]
    check(
        not bad_env,
        "every unlaned select_target call in rl_env.py passes direct=True; "
        f"offending lines: {bad_env}",
    )
    check(
        'nearest_default = "0" if direct else NEAREST_ABOVE_FLOOR_SCRIPTED' in TASKS_SRC,
        "the default is resolved per path (`\"0\" if direct else "
        "NEAREST_ABOVE_FLOOR_SCRIPTED`)",
    )
    # The one-item re-check is value-identical under the rule (a single candidate
    # has nearest == farthest): the shipped `take_prepared_target` consume path.
    task = stub_task()
    single = [fruit(2, "A", 0.70)]
    seen = set()
    for value in (None, "0", "1"):
        with with_env(value):
            state = task.select_target(single)
            seen.add(None if state is None else int(state["index"]))
    check(seen == {2}, f"a one-item re-check is invariant under the rule ({sorted(seen)})")


# --------------------------------------------------------------------------- #
# 5. Provenance
# --------------------------------------------------------------------------- #
def test_provenance() -> None:
    print("[5] provenance")
    md5 = hashlib.md5((SRC / "tasks.py").read_bytes()).hexdigest()
    pinned = None
    for line in RL_ENV_SRC.splitlines():
        if line.startswith("TASKS_MD5 = "):
            pinned = line.split("=", 1)[1].strip().strip('"')
            break
    check(pinned is not None, "rl_env.py declares TASKS_MD5")
    check(
        pinned == md5,
        f"TASKS_MD5 follows tasks.py ({pinned} == {md5})",
    )


def test_park_default() -> None:
    """P43 phase 4 (A1): the arm park's default, and its scope.

    The park (P43 phase 3) is adopted as the **direct** presentation's default,
    and the scope is the safety property: an unscoped default would make every
    `handoff` construction raise (the park is only applicable where the reset
    teleports the arms). `ready` - explicit - is the escape hatch that
    reproduces every pre-P43 direct arm, so it must resolve to the shipped pose
    on both presentations.
    """
    print("[6] the arm park's default and scope (P43 phase 4)")
    from fruit_sorting.rl_env import resolve_arm_park

    check(resolve_arm_park("direct", None) == ("back", True),
          "direct + unset -> park=back, defaulted=true")
    check(resolve_arm_park("handoff", None) == ("", False),
          "handoff + unset -> no park (the shipped ready pose), defaulted=false")
    check(resolve_arm_park("direct", "ready") == ("ready", False),
          "direct + =ready -> the shipped pose, defaulted=false (the escape hatch)")
    check(resolve_arm_park("handoff", "ready") == ("ready", False),
          "handoff + =ready -> no raise, no park")
    check(resolve_arm_park("direct", "back") == ("back", False),
          "direct + =back -> the pre-P43 opt-in arm, defaulted=false")
    check(resolve_arm_park("direct", "") == ("", False),
          "direct + ='' -> the shipped pose, defaulted=false")
    check(resolve_arm_park("handoff", "back") == ("back", False),
          "handoff + =back still resolves the name (the guard raises on it)")

    # The guard itself: a named park on a non-direct presentation must still
    # raise, i.e. the default did not widen the knob's domain.
    src = RL_ENV_SRC
    guard = ('if self._arm_park and self._arm_park != "ready":\n'
             '            if presentation != "direct":')
    check(guard in src,
          "the non-direct guard is unchanged (a named park still raises there)")
    check('self._arm_park_source = {\n                "name": self._arm_park,' in src,
          "the applied park is recorded in the manifest")
    check('"defaulted": self._arm_park_defaulted,' in src,
          "the manifest distinguishes a defaulted park from an explicit one")
    check("park={self._park_label()}" in src,
          "`[rl] env ready` prints the resolved park state")
    check('park={self._park_label()}[{self._park_poses_label()}]' in src,
          "the `[park]` row prints the name AND the per-arm resolution")


def main() -> int:
    test_scope_default()
    test_env_wins()
    test_lane_callers_are_above_the_rule()
    test_call_sites()
    test_provenance()
    test_park_default()
    print("\nALL P43 CHECKS PASSED (the L1 selector scope + the phase-4 park default)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
