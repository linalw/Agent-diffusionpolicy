"""Offline selftest of the P32 phase-2 prepared-next pipeline and feeder cadence.

    python3 scripts/213_prepared_next_selftest.py            # the checks
    python3 scripts/213_prepared_next_selftest.py --cost     # + the pump cost probe

No simulator. The *real* selector is driven on a stubbed task (the
`176`/`198` pattern), so what is pinned is the code the runs use, not a copy:

* **the ranking** (`_prepared_rank`): the prepared set is the shipped selector
  applied repeatedly with `exclude=already_ranked`, so on the single-arm moving
  catch it is farthest-upstream-first and on the two-line selector nearest-first
  within the arm's own grade; a starved line yields a short/empty set, never a
  filler, and no candidate appears twice;
* **the refresh policy** (`_PreparedNext.store`): the release-stage read
  supersedes the carry-stage one, a later carry-stage store cannot downgrade it,
  and an empty read keeps the previous set (a transiently empty `state()` must
  not throw away a usable set) while counting itself;
* **the consume** (`take_prepared_target`): the first row that still passes a
  one-item `select_target` on the *live* state is returned; a row inside the
  catch's selection floor, or one the feeder recycled away, is dropped and the
  next row upstream is taken; when every row fails the set is emptied and the
  caller selects fresh (the shipped path);
* **the scope and the defaults**: both knobs default off, the pipeline is
  single-arm-scripted only (no `CoopSession`, no direct/policy hand, smooth
  pre-pose required), the return's convergence pair is the W8-R3 hot-hold pair
  (140/80) and the stride's default is 4;
* **the feed cadence** (`_feed_tick`): exactly `floor(ticks / stride)` pump calls
  over `ticks`, and every one of them passes `advance_furniture=False` - the
  conveyor's kinematic furniture keeps the shipped per-pump cadence, so the
  lever is the release schedule alone. Off the knob `_carry` never calls it (the
  hook is one attribute read);
* **`fruits.update`'s split**: the default still steps the belt (every existing
  call site is byte-identical) and `advance_furniture=False` does not, while the
  wake loop still runs.

`--cost` is the measured per-call cost the gate asks for: it drives the real
`FruitSpawner.update` on `211_bed_audit.py`'s fake belt (the imported module, not
a copy) at a ~20-body live count, and reports the wall time per call, the
fruit-pose reads per call and the implied overhead per simulated second at
stride 1 and 4. The fake belt's pose read is an attribute read, so the number is
the **Python-side floor**; the real per-call cost is the same O(live)
`get_world_poses()` count in the safe fruit-pose read class, and the battery's
wall-clock delta is the number of record. Run `--cost` to a log
(`logs/p32/prepared_next_cost.txt`) rather than quoting this docstring.

Run by `scripts/selfcheck.sh` (the checks only; `--cost` is a manual probe).
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import os
import re
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks ---------- #
# (same pattern as `176_twoline_selftest.py` / `198_r10_selftest.py`)
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

from fruit_sorting.tasks import PickAndPlaceTask, _PreparedNext  # noqa: E402

BELT_V = -0.12
TASKS_SRC = Path(ROOT, "src", "fruit_sorting", "tasks.py").read_text(encoding="utf-8")
FRUITS_SRC = Path(ROOT, "src", "fruit_sorting", "fruits.py").read_text(encoding="utf-8")
DRIVER_SRC = Path(ROOT, "scripts", "20_pick_place.py").read_text(encoding="utf-8")
AUDIT = Path(ROOT, "scripts", "211_bed_audit.py")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok: {message}")


def near(value: float, target: float, tol: float, label: str) -> None:
    if abs(value - target) > tol:
        raise AssertionError(f"{label}: {value} != {target} (+/- {tol})")
    print(f"ok: {label} ({value:.4f} ~ {target:.4f})")


# --------------------------------------------------------------------------- #
# The stubbed task (only what the selector and the prepared pipeline read)
# --------------------------------------------------------------------------- #
def stub_task(*, prefer_upstream: bool = True, session=None, scripted: bool = True):
    """A task-shaped object carrying exactly the attributes the code reads."""
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
    # The reach rule is off (the shipped default): `select_target` only reads it
    # through `_reach_anywhere_active()` when `_prefer_upstream`, and False is
    # the shipped value (`FRUIT_REACH_ANYWHERE` default 0).
    task._reach_anywhere = False
    task._reach_diag = False
    task._reach_aim_key = None
    task._reach_aim_point = None
    task._active_session = session
    task.station_y = {"left": 0.0, "right": -0.10}
    task._prepared_next = True
    task._prepared_pending = None
    task._prepared = {"left": _PreparedNext(), "right": _PreparedNext()}
    task._prepose_armed = {"left": False, "right": False}
    task._prepared_count = 4
    task._prepared_diag = False
    task._dynamic_pick_lead = lambda: 0.189
    task._belt_speed_estimate = lambda: BELT_V
    task._approach_duration = (
        lambda distance, v_max, a_max=None: PickAndPlaceTask._approach_duration(
            task, distance, v_max, a_max
        )
    )
    task._dynamic_select_floor = (
        lambda min_lead_s=None, lead_override_s=None: PickAndPlaceTask._dynamic_select_floor(
            task, min_lead_s, lead_override_s
        )
    )
    task._balance_arm = lambda ordered: PickAndPlaceTask._balance_arm(task, ordered)
    task._pure_grade_routing = lambda: PickAndPlaceTask._pure_grade_routing(task)
    task._reach_anywhere_active = lambda: PickAndPlaceTask._reach_anywhere_active(task)
    task._reach_anywhere_select = (
        lambda states, lane=None, prefer_lane=None, exclude=None: PickAndPlaceTask._reach_anywhere_select(
            task, states, lane, prefer_lane, exclude
        )
    )
    task.station_y_for = lambda arm: float(task.station_y.get(arm, task.cfg.pick_y))
    task.select_target = (
        lambda states, **kwargs: PickAndPlaceTask.select_target(task, states, **kwargs)
    )
    task._prepared_rank = (
        lambda states, limit, **kwargs: PickAndPlaceTask._prepared_rank(
            task, states, limit, **kwargs
        )
    )
    task._prepared_scope = (
        lambda scripted_flag: PickAndPlaceTask._prepared_scope(task, scripted_flag)
    )
    task._prepared_lane = PickAndPlaceTask._prepared_lane
    task.take_prepared_target = (
        lambda states=None: PickAndPlaceTask.take_prepared_target(task, states)
    )
    task._sim_time = lambda: 100.0
    task.spawner = FakeSpawner()
    return task


class FakeSample:
    def __init__(self, index: int, y: float, *, x: float = 0.28, diameter: float = 0.06):
        self.index = index
        self.diameter = diameter
        self._pos = np.array([x, y, 1.17 + diameter / 2.0])
        self._vel = np.array([0.0, BELT_V, 0.0])


class FakeSpawner:
    def __init__(self):
        self.rows: list[dict] = []
        self.samples: list[FakeSample] = []
        self.protected_indices: set[int] = set()

    def state(self):
        return list(self.rows)

    def position(self, sample):
        return np.asarray(sample._pos, dtype=float)

    def velocity(self, sample):
        return np.asarray(sample._vel, dtype=float)

    def protect(self, index):
        if index is not None:
            self.protected_indices.add(int(index))

    def unprotect(self, index):
        if index is not None:
            self.protected_indices.discard(int(index))


def fruit(index: int, grade: str, y: float, *, x: float = 0.28, diameter: float = 0.06):
    return {
        "index": index,
        "grade": grade,
        "diameter": diameter,
        "position": np.array([x, y, 1.17 + diameter / 2.0]),
        "velocity": np.array([0.0, BELT_V, 0.0]),
    }


def set_live(task, rows) -> None:
    """Publish a live supply to the stub (the selector reads `states` only)."""
    task.spawner.rows = list(rows)


# --------------------------------------------------------------------------- #
# 1. The ranking
# --------------------------------------------------------------------------- #
def test_ranking() -> None:
    print("[1] the prepared ranking (the shipped selector, applied repeatedly)")
    task = stub_task()
    # Four eligible candidates in the upstream window, all above the catch floor
    # (0.399 m at the shipped values), spread so the order is unambiguous.
    rows = [
        fruit(0, "A", 0.45),
        fruit(1, "B", 0.55),
        fruit(2, "A", 0.70),
        fruit(3, "B", 0.82),
    ]
    set_live(task, rows)
    far = task._prepared_rank(rows, 4)
    check(
        [int(row["index"]) for row in far] == [3, 2, 1, 0],
        "single-arm nearest-usable rule: farthest upstream first, then downstream",
    )
    check(
        len({int(row["index"]) for row in far}) == len(far),
        "no candidate appears twice in the prepared set",
    )
    floor = task._dynamic_select_floor()
    check(
        all(float(row["position"][1]) >= floor for row in far),
        f"every prepared row is above the catch floor ({floor:.3f} m)",
    )
    # A fruit inside the floor is refused exactly as the selector refuses it:
    # the prepared set cannot smuggle a candidate past the rule.
    inside = [fruit(9, "A", 0.30)] + rows
    check(
        [int(row["index"]) for row in task._prepared_rank(inside, 4)] == [3, 2, 1, 0],
        "a fruit inside the catch floor is not prepared",
    )
    # Starved line: a short set, not a filler.
    check(task._prepared_rank([fruit(9, "A", 0.30)], 4) == [], "starved line -> empty set")
    check(
        [int(row["index"]) for row in task._prepared_rank(rows, 2)] == [3, 2],
        "the set size is the requested limit, in rule order",
    )
    # `exclude` is forwarded: the current attempt's protected fruit cannot be
    # prepared as its own successor.
    check(
        [int(row["index"]) for row in task._prepared_rank(rows, 4, exclude={3})]
        == [2, 1, 0],
        "the protected/current fruit is excluded from the ranking",
    )

    # Second arm (the two-line worker's rules): its own grade, nearest first.
    # The bands sit above each station's own catch floor (station -0.10 for the
    # right, so its floor is +0.299 m rather than the single arm's +0.399).
    two = stub_task(prefer_upstream=True)
    mixed = [
        fruit(0, "A", 0.55),
        fruit(1, "B", 0.35),
        fruit(2, "B", 0.45),
        fruit(3, "C", 0.40),
    ]
    right = two._prepared_rank(
        mixed, 3, station_y=-0.10, prefer_lane=1, min_lead_s=None,
        lead_override_s=None,
    )
    check(
        [int(row["index"]) for row in right] == [1, 2],
        "two-line right lane: grade B only, nearest of its lane first (C never)",
    )
    left = two._prepared_rank(
        mixed, 3, station_y=0.0, prefer_lane=0, min_lead_s=None, lead_override_s=None
    )
    check([int(row["index"]) for row in left] == [0], "two-line left lane: grade A only")

    check(
        PickAndPlaceTask._prepared_lane(fruit(0, "A", 0.5)) == "left"
        and PickAndPlaceTask._prepared_lane(fruit(0, "B", 0.5)) == "right"
        and PickAndPlaceTask._prepared_lane(fruit(0, "C", 0.5)) == "right",
        "the prepared target's lane is the driver's grade rule (A -> left)",
    )


# --------------------------------------------------------------------------- #
# 2. The refresh policy
# --------------------------------------------------------------------------- #
def test_refresh_policy() -> None:
    print("[2] the refresh policy (release supersedes carry, no downgrade, empty keeps)")
    store = _PreparedNext()
    carry = [fruit(1, "A", 0.7), fruit(2, "B", 0.8)]
    release = [fruit(3, "B", 0.5)]
    check(store.store("carry", carry, 10.0) == "stored", "carry-stage store accepted")
    check(bool(store) and store.stage == "carry" and store.t == 10.0, "carry stage recorded")
    check(store.store("release", release, 20.0) == "stored", "release-stage store accepted")
    check(
        [int(row["index"]) for row in store.rows] == [3] and store.stage == "release",
        "the release read supersedes the carry read",
    )
    check(
        store.store("carry", carry, 30.0) == "kept-release",
        "a later carry-stage store cannot downgrade the release set",
    )
    check([int(row["index"]) for row in store.rows] == [3], "the release set is kept")
    check(store.store("release", [], 40.0) == "empty", "an empty read is counted")
    check(
        [int(row["index"]) for row in store.rows] == [3] and store.empty == 1,
        "an empty read keeps the previous set (a transient empty state is not a loss)",
    )
    store.clear()
    check(not store and store.stage == "" and store.t is None, "clear drops set and stage")


# --------------------------------------------------------------------------- #
# 3. The consume (the one-item re-check)
# --------------------------------------------------------------------------- #
def test_take() -> None:
    print("[3] the consume (one-item re-check on the live state)")
    task = stub_task()
    now = 200.0
    task._sim_time = lambda: now
    # The set was built at t=190 with three rows.
    task._prepared["left"].store(
        "release", [fruit(0, "A", 0.42), fruit(1, "A", 0.60), fruit(2, "A", 0.80)], 190.0
    )
    task._prepared_pending = "left"
    # Row 0 has moved inside the floor since; row 1 is the first still-usable one.
    live = [fruit(0, "A", 0.30), fruit(1, "A", 0.55), fruit(2, "A", 0.78)]
    state = task.take_prepared_target(live)
    check(state is not None and int(state["index"]) == 1, "the first row that still passes wins")
    store = task._prepared["left"]
    near(store.age_s, 10.0, 1e-6, "the consume age is quoted (selection -> dispatch)")
    check(store.dropped == 1, "the row inside the floor is counted as dropped")
    check(not store.rows and task._prepared_pending is None, "the set is consumed once")

    # A recycled-away row (not in the live state) is dropped the same way.
    task._prepared["right"].store("release", [fruit(5, "B", 0.60)], 195.0)
    task._prepared_pending = "right"
    check(
        task.take_prepared_target([fruit(6, "B", 0.9)]) is None,
        "a row the feeder recycled away is refused",
    )
    check(task._prepared["right"].dropped == 1, "the missing row is counted as dropped")

    # Every row fails -> None, and the caller selects fresh.
    task._prepared["left"].store("release", [fruit(7, "A", 0.65)], 196.0)
    task._prepared_pending = "left"
    check(
        task.take_prepared_target([fruit(7, "A", 0.20)]) is None,
        "a whole set that dropped inside the floor returns None (select fresh)",
    )
    check(not task._prepared["left"], "the failed set is emptied")
    # Nothing pending / knob off: the shipped path exactly.
    check(task.take_prepared_target([]) is None, "nothing pending -> None")
    task._prepared_next = False
    task._prepared_pending = "left"
    task._prepared["left"].store("release", [fruit(8, "A", 0.7)], 197.0)
    check(task.take_prepared_target([fruit(8, "A", 0.7)]) is None, "knob off -> None")


# --------------------------------------------------------------------------- #
# 4. The scope and the defaults
# --------------------------------------------------------------------------- #
def stub_two_line(session):
    """A stub task + session for the two-line prepared-set plumbing."""
    task = stub_task(session=session)
    task._prepared_count = 3
    task._biarm_lead_args = lambda arm: (None, None)
    task._prepared_rank = (
        lambda states, limit, **kwargs: PickAndPlaceTask._prepared_rank(
            task, states, limit, **kwargs
        )
    )
    task._biarm_prepare_other = (
        lambda s, arm: PickAndPlaceTask._biarm_prepare_other(task, s, arm)
    )
    task._biarm_take_prepared = (
        lambda s, arm, lane: PickAndPlaceTask._biarm_take_prepared(task, s, arm, lane)
    )
    task._biarm_clear_prepared = (
        lambda s, arm: PickAndPlaceTask._biarm_clear_prepared(task, s, arm)
    )
    return task


def make_session():
    return SimpleNamespace(
        prepared={"left": _PreparedNext(), "right": _PreparedNext()},
        prepared_stats={
            "built": 0, "empty": 0, "kept": 0, "dropped": 0, "stale": 0,
        },
    )


def test_two_line_prepared() -> None:
    print("[4b] the two-line prepared set (built at the other arm's carry start)")
    session = make_session()
    task = stub_two_line(session)
    live = [
        fruit(0, "A", 0.55),
        fruit(1, "B", 0.35),
        fruit(2, "B", 0.45),
        fruit(3, "A", 0.62),
    ]
    task.spawner.rows = live
    # The left arm's payload clears (its carry start): the right arm's set is
    # ranked and its top entry is reserved.
    task._biarm_prepare_other(session, "left")
    right = session.prepared["right"]
    check(right and session.prepared_stats["built"] == 1, "the idle arm's set is built once")
    check(
        [int(row["index"]) for row in right.rows] == [1, 2],
        "the set is the worker's own rule: grade B, nearest of its station lane",
    )
    check(
        task.spawner.protected_indices == {1},
        "only the top entry is reserved (the alternates cannot starve the lane)",
    )
    check(
        not session.prepared["left"],
        "the preparing arm's own set is not touched by the other arm's build",
    )
    # The slot start consumes it and releases the reservation.
    state = task._biarm_take_prepared(session, "right", 1)
    check(
        state is not None and int(state["index"]) == 1,
        "the slot start consumes the prepared top entry",
    )
    check(
        task.spawner.protected_indices == set(),
        "the reservation is released at the consume",
    )
    check(
        session.prepared_stats["kept"] == 1 and not session.prepared["right"],
        "the consumed set is empty and counted",
    )
    # A build that has gone stale is refused and released: the fruit walks
    # inside the floor while the arm parks.
    task._biarm_prepare_other(session, "left")
    check(task.spawner.protected_indices == {1}, "a fresh build reserves again")
    task.spawner.rows = [
        fruit(0, "A", 0.55),
        fruit(1, "B", 0.10),   # inside the right station's floor (+0.299)
        fruit(2, "B", 0.12),   # ditto
    ]
    check(
        task._biarm_take_prepared(session, "right", 1) is None,
        "a set that dropped inside the floor is refused (the slot selects fresh)",
    )
    check(
        task.spawner.protected_indices == set(),
        "the reservation is released even when the whole set is refused",
    )
    check(
        session.prepared_stats["dropped"] == 1,
        "the refused set is counted in the batch-end report",
    )
    # A recycled-away top row falls through to the next-ranked alternate ...
    task.spawner.rows = live
    task._biarm_prepare_other(session, "left")
    task.spawner.rows = [row for row in live if int(row["index"]) != 1]
    state = task._biarm_take_prepared(session, "right", 1)
    check(
        state is not None and int(state["index"]) == 2,
        "a recycled-away top row falls through to the next-ranked alternate",
    )
    check(session.prepared_stats["stale"] == 1, "the missing row is counted as stale")
    # ... and with every row gone the set is stale as a whole.
    task.spawner.rows = live
    task._biarm_prepare_other(session, "left")
    reserved = set(task.spawner.protected_indices)
    task.spawner.rows = [row for row in live if int(row["index"]) not in (1, 2)]
    check(
        task._biarm_take_prepared(session, "right", 1) is None,
        "a set whose rows are all gone is refused",
    )
    check(session.prepared_stats["stale"] == 3, "every missing row is counted as stale")
    check(
        task.spawner.protected_indices == set() and reserved,
        "the reservation is released by the take",
    )
    task.spawner.rows = live
    task._biarm_prepare_other(session, "left")
    task._biarm_clear_prepared(session, "right")
    check(
        task.spawner.protected_indices == set() and not session.prepared["right"],
        "abandoning the set (the worker's finally) releases the reservation",
    )
    check(
        bool(
            re.search(
                r"session\.prepared_latch\[arm\] = False", TASKS_SRC
            )
        ),
        "the prepare latch is reset at every slot start",
    )
    check(
        "self._biarm_prepare_other(session, self.current_arm)" in TASKS_SRC,
        "the build is triggered from the payload-clear tick (the park-gate instant)",
    )


def test_scope_and_defaults() -> None:
    print("[4] the scope and the default-off pins")
    check(
        PickAndPlaceTask._prepared_scope(stub_task(), True) is True,
        "single-arm scripted attempt: the pipeline is in scope",
    )
    check(
        PickAndPlaceTask._prepared_scope(stub_task(), False) is False,
        "direct/policy handover: out of scope",
    )
    check(
        PickAndPlaceTask._prepared_scope(stub_task(session=object()), True) is False,
        "a CoopSession (two-line / shared station): out of scope",
    )
    saved = os.environ.get("FRUIT_SMOOTH_TRANSIT_PREPOSE")
    try:
        os.environ["FRUIT_SMOOTH_TRANSIT_PREPOSE"] = "0"
        check(
            PickAndPlaceTask._prepared_scope(stub_task(), True) is False,
            "teleport pre-pose (smooth transit off): out of scope",
        )
    finally:
        if saved is None:
            os.environ.pop("FRUIT_SMOOTH_TRANSIT_PREPOSE", None)
        else:
            os.environ["FRUIT_SMOOTH_TRANSIT_PREPOSE"] = saved

    def default(name: str, fallback: str, text: str = TASKS_SRC) -> bool:
        return bool(
            re.search(
                r'os\.environ\.get\(\s*["\']'
                + re.escape(name)
                + r'["\']\s*,\s*["\']'
                + re.escape(fallback)
                + r'["\']\s*\)',
                text,
            )
        )

    check(default("FRUIT_PREPARED_NEXT", "0"), "FRUIT_PREPARED_NEXT defaults to 0 (off)")
    check(default("FRUIT_FEED_CADENCE", "0"), "FRUIT_FEED_CADENCE defaults to 0 (off)")
    check(default("FRUIT_FEED_STRIDE", "4"), "FRUIT_FEED_STRIDE defaults to 4 ticks")
    check(default("FRUIT_PREPARED_SET", "4"), "FRUIT_PREPARED_SET defaults to 4 rows")
    check(
        default("FRUIT_PREPARED_RETURN_TICKS", "140")
        and default("FRUIT_PREPARED_RETURN_SETTLE", "80"),
        "the return uses the measured convergence pair 140+80 (W8-R3 hot hold)",
    )
    check(
        default("FRUIT_PREPARED_RETURN_EMPTY", "0"),
        "an empty set does not run the return by default (the A/B control knob)",
    )
    check(
        bool(
            re.search(
                r"def update\(\s*self,\s*sim_time:\s*float,\s*advance_furniture:\s*bool\s*=\s*True",
                FRUITS_SRC,
            )
        ),
        "fruits.update keeps advance_furniture=True as its default (byte-identical callers)",
    )
    check(
        "take_prepared_target" in DRIVER_SRC and "at_prepose" in DRIVER_SRC,
        "the driver consumes the prepared set and honours at_prepose",
    )
    check(
        "if self._feed_on:" in TASKS_SRC and "self._feed_tick()" in TASKS_SRC,
        "the carry hook is a single gated call (`if self._feed_on:`)",
    )


# --------------------------------------------------------------------------- #
# 5. The feeder cadence
# --------------------------------------------------------------------------- #
class RecordingSpawner:
    def __init__(self):
        self.calls = 0
        self.kwargs: list[dict] = []

    def update(self, sim_time, **kwargs):
        self.calls += 1
        self.kwargs.append(dict(kwargs))


def test_feed_cadence() -> None:
    print("[5] the feeder cadence (stride arithmetic, furniture flag)")
    for stride, ticks, expect in ((1, 10, 10), (4, 10, 2), (4, 12, 3), (2, 7, 3), (4, 1, 0)):
        task = object.__new__(PickAndPlaceTask)
        spawner = RecordingSpawner()
        task.spawner = spawner
        task._sim_time = lambda: 1.0
        task._feed_on = True
        task._feed_ticks = 0
        task._feed_calls = 0
        task._feed_stride = stride
        for _ in range(ticks):
            PickAndPlaceTask._feed_tick(task)
        check(
            spawner.calls == expect,
            f"stride {stride} over {ticks} ticks -> {expect} pump calls",
        )
        check(task._feed_ticks == ticks, f"stride {stride}: every tick is counted")
        check(
            all(kw == {"advance_furniture": False} for kw in spawner.kwargs),
            f"stride {stride}: every pump keeps the conveyor furniture on the shipped cadence",
        )
    # The count is per attempt: the arming site resets both counters.
    check(
        re.search(r"self\._feed_ticks = 0\s*\n\s*self\._feed_calls = 0", TASKS_SRC)
        is not None,
        "the arming site resets the cadence counters per attempt",
    )


# --------------------------------------------------------------------------- #
# 6. fruits.update's split (the real spawner, a fake belt)
# --------------------------------------------------------------------------- #
class FakeBelt:
    def __init__(self):
        self.speed = BELT_V
        self.steps = 0

    def step(self, dt):
        self.steps += 1


def load_audit():
    spec = importlib.util.spec_from_file_location("p32_bed_audit", AUDIT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_cost_spawner(audit, *, preload: int = 20):
    """A real `FruitSpawner` on the bed supply, optionally pre-loaded to a count."""
    audit.clear_supply_env()
    os.environ["FRUIT_SUPPLY_SCATTER"] = "1"
    os.environ["FRUIT_SUPPLY_BED"] = "1"
    os.environ["FRUIT_QUEUE_MAX"] = "6"
    cfg = audit.SceneConfig()
    grades = audit.SupplyPlan.from_env(cfg).grades
    items = audit.synthetic_pool(cfg, audit.POOL, audit.SEED, grades)
    spawner = audit.make_spawner(cfg, items)
    spawner.belt = FakeBelt()
    # Fill the belt to the bed's measured live count (17-20) by hand: the cost
    # probe measures the pump's per-call work, not the transport.
    for k, sample in enumerate(spawner.samples[:preload]):
        sample.parked = False
        sample.held = False
        sample.attached = False
        sample.prim_path = f"/World/Fruits/Fruit_{sample.index:02d}"
        spawner._rigids[sample.index].pos = np.array(
            [0.28, 0.62 - 0.045 * k, 1.17 + sample.diameter / 2.0]
        )
        spawner._rigids[sample.index].vel = np.array([0.0, BELT_V, 0.0])
        spawner.active.append(sample)
    return spawner, cfg


def test_update_split(audit) -> None:
    print("[6] fruits.update's furniture split (the real spawner)")
    spawner, _cfg = make_cost_spawner(audit)
    spawner.belt.steps = 0
    spawner.update(0.0)
    check(spawner.belt.steps == 1, "update() with the default steps the conveyor (unchanged)")
    spawner.belt.steps = 0
    spawner.update(0.0, advance_furniture=False)
    check(
        spawner.belt.steps == 0,
        "advance_furniture=False keeps the cleat phase where it is (the cadence lever only)",
    )
    # The wake loop still runs in both cases (a sleeping body would stall the
    # supply): the fake bodies are given < 0.02 m/s and must be woken.
    sleeping = [s for s in spawner.active[:3]]
    for sample in sleeping:
        spawner._rigids[sample.index].vel = np.array([0.0, 0.0, 0.0])
    spawner.update(0.0, advance_furniture=False)
    check(
        all(abs(float(spawner._rigids[s.index].vel[1])) > 0.02 for s in sleeping),
        "the transport wake loop still runs without the furniture step",
    )


def run_cost(audit) -> None:
    print("[7] the pump cost probe (fake belt, real `FruitSpawner.update`)")
    spawner, cfg = make_cost_spawner(audit)
    # Advance the schedule ~25 s so the pump's cursor is in the steady state and
    # the queue sees a realistic backlog, without moving the bodies. (The
    # recirculation clock is 60 s of accumulated wait, so the whole probe stays
    # inside it - a parked body would change the live count mid-measurement.)
    dt = 1.0 / 120.0
    for tick in range(3000):
        spawner.update(tick * dt)
    released0 = int(spawner.stats.get("released", 0))
    placed0 = int(spawner.stats.get("bed_placed", 0))
    live = len([s for s in spawner.active if not s.parked and not s.held])
    print(f"    live bodies: {live} (bed steady state, pool {audit.POOL})")
    reads = [0]
    original = audit.FakeRigid.get_world_poses

    def counting_get_world_poses(self):
        reads[0] += 1
        return original(self)

    audit.FakeRigid.get_world_poses = counting_get_world_poses
    try:
        t_fixed = 3000 * dt + 1e-9  # just past the fill: cursor is ahead of it
        for _ in range(5):
            spawner.update(t_fixed)
        reads[0] = 0
        n = 400
        start = time.perf_counter()
        for _ in range(n):
            spawner.update(t_fixed)
        steady = (time.perf_counter() - start) / n
        steady_reads = reads[0] / n
        # Due calls: a *fresh* pre-loaded spawner (the bed's own first rows), so
        # each call really releases the slots that came due (`_release_clear`
        # would refuse every row behind the static bodies above). 1 s between
        # calls stays inside the 60 s recirculation clock.
        due_spawner, _ = make_cost_spawner(audit, preload=4)
        due_spawner.prime(count=4)
        t = 0.1
        due_spawner.update(t)
        released0 = int(due_spawner.stats.get("released", 0))
        placed0 = int(due_spawner.stats.get("bed_placed", 0))
        reads[0] = 0
        start = time.perf_counter()
        live_sum = 0
        for _ in range(20):
            t += 1.0
            # Fake transport: one second of belt travel for the live bodies, so
            # the spawn point and the queue drain and the due rows really place
            # (`_release_clear` refuses a row behind a static body, which would
            # measure the draw without the placement).
            for sample in list(due_spawner.active):
                if sample.parked:
                    continue
                due_spawner._rigids[sample.index].pos[1] += BELT_V * 1.0
            due_spawner.update(t)
            live_sum += len(
                [s for s in due_spawner.active if not s.parked and not s.held]
            )
        due = (time.perf_counter() - start) / 20
        due_reads = reads[0] / 20
        due_live = live_sum / 20
    finally:
        audit.FakeRigid.get_world_poses = original
    released = int(due_spawner.stats.get("released", 0)) - released0
    placed = int(due_spawner.stats.get("bed_placed", 0)) - placed0
    live_end = len([s for s in spawner.active if not s.parked and not s.held])
    print(
        f"    steady call: {steady * 1e6:8.1f} us, {steady_reads:5.1f} pose reads "
        f"(belt {cfg.belt_speed:+.2f} m/s, stride-independent)"
    )
    print(
        f"    due call:    {due * 1e6:8.1f} us, {due_reads:5.1f} pose reads "
        f"(released {released}, placed {placed}, mean live {due_live:.0f})"
    )
    print(f"    live bodies at the end: {live_end} (no recirculation inside the probe)")
    for stride in (1, 4):
        calls = 120.0 / stride
        steady_ms = steady * calls * 1000.0
        due_share = min(1.0, calls * (1.0 / 120.0) / 30.0)  # ~1 due slot per 30 sim-s
        print(
            f"    stride {stride}: {calls:5.1f} calls/sim-s -> steady "
            f"{steady_ms:6.2f} ms/sim-s (+ due slots; {due_share * 100:.0f}% of calls are due)"
        )
    print(
        "    NOTE: the fake belt's pose read is an attribute read, so this is the "
        "Python-side FLOOR.\n          The real cost is the same pose-read class "
        "(the safe class, AGENTS section 2); the\n          battery's wall-clock "
        "delta is the number of record."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cost",
        action="store_true",
        help="also run the pump cost probe (the fake-belt wall-time measurement)",
    )
    args = parser.parse_args()
    test_ranking()
    test_refresh_policy()
    test_take()
    test_scope_and_defaults()
    test_two_line_prepared()
    test_feed_cadence()
    audit = load_audit()
    test_update_split(audit)
    if args.cost:
        run_cost(audit)
    print("PASS: prepared-next pipeline selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
