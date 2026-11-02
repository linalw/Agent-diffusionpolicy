#!/usr/bin/env python3
"""P100 selftest: the park return's fixed clock is a **two-line-scoped** cell.

    python3 scripts/254_p100_park_selftest.py

No simulator (the `225` / `247` / `248` / `249` / `250` stub-the-imports
pattern): the **real** `park_profile_resolution` runs, and the manifest builder's
own block is built through the real `scene._park_provenance`.

Why each item matters. P99's census (`logs/p99/CENSUS.md` §0) names the park
return as the largest remaining non-semantic term of the two-line's slot loop -
**2.47 s (seed 5) / 2.69 s (seed 6) of motion per attempt slot** - and P100 reads
its code path: the worker's `finally` calls `_biarm_park`, which gates then calls
`go_ready` -> `_ready_move` -> `_transit_to("ready")` -> `_ready_transit`, i.e.
`_catch_up_drive` + `_lift_clear` + `_blend_to`'s min-jerk **ramp** + its
**settle** hold. Only the last two are fixed (they tick-clock the block), and the
arm carries nothing on this path. `_ready_move` is also the single-arm `go_ready`
path, so the cell is scoped to a two-line session - exactly like the release
(P87), the place (P88), the lift (P89) and the take-off ramp (P91). This leg pins:

1. **Unset, no session = the shipped 90/120** - the literals the site used before
   P100 - so the single arm, the shared-station pipeline, the hybrid canary and
   the direct/policy presentation are byte-identical.
2. **The scope is enforced, not argued**: with the env *set* and no two-line
   session the resolver still returns the shipped pair. That covers the driver's
   own **pre-session prime transit**, which prints the same `[ready]` row before
   `run_bimanual` installs the session (`20_pick_place.py`), so a value cannot
   leak into the prime.
3. **Unset + two-line = the shipped 90/120 and the default is OFF**
   (`PARK_TWO_LINE_DEFAULT is False`): the shipped tree resolves the pre-P100
   clock on every path and the measured arm is the explicit pair.
4. **The cell (60/75) = 135 ticks, saved 75 = -0.625 s at 120 Hz**, two-line
   only; each half is an independent override (the unset half keeps the scope's
   own default), and the clamps hold (`blend >= 1`, `settle >= 0`).
5. **The flip's cell** (`PARK_TWO_LINE_DEFAULT = True`) resolves 45/45 in the
   two-line scope and the shipped pair outside it - the flip is a resolution.
6. **The two fixed tails are the only lever**: `_PARK_SHIPPED_BLEND` *is* the
   class constant the transit's own accounting reads
   (`READY_TRANSIT_BLEND_TICKS`) and `_PARK_SHIPPED_SETTLE` *is* `_ready_settle`'s
   own shipped default, so the published 90/120 cannot drift away from the code.
7. **One consumer, the session predicate.** `_ready_move` is the only site that
   reads a park value, it passes `self.two_line_enabled()`, and the hardcoded
   `else 120` is gone from that call.
8. **`q_step` is arithmetic, not a read**: it is computed inside
   `if stats is not None:` (the `FRUIT_READY_DIAG` block) from the two
   configurations `_blend_to` already holds, so the shipped path gains no read
   and no work.
9. **The row and the provenance.** `[biarm] park profile:` prints only inside
   `run_bimanual` and reads the resolver; `physics.park` is written by the one
   builder both manifest writers call.

Exit 0 on pass, 1 on the first failure. Run by `scripts/selfcheck.sh`.
"""
from __future__ import annotations

import ast
import hashlib
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks + scene --- #
for name in (
    "pxr",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.sensors",
    "isaacsim.sensors.experimental",
    "isaacsim.core.experimental.utils",
    "isaacsim.core.experimental.objects",
    "isaacsim.core.experimental.utils.app",
    "isaacsim.core.experimental.utils.stage",
    "isaacsim.core.experimental.prims",
):
    module = sys.modules.setdefault(name, types.ModuleType(name))
    module.__path__ = []
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
sys.modules["isaacsim.core.experimental.utils.app"].update_app = lambda **kwargs: None
sys.modules["isaacsim.core.experimental.utils.stage"].create_prim = lambda *a, **k: None
prims_mod = sys.modules["isaacsim.core.experimental.prims"]
prims_mod.RigidPrim = object
prims_mod.Articulation = object
objects_mod = sys.modules["isaacsim.core.experimental.objects"]
objects_mod.DistantLight = object
objects_mod.GroundPlane = object
sys.modules.setdefault(
    "isaacsim.core.simulation_manager",
    types.SimpleNamespace(
        SimulationManager=types.SimpleNamespace(step=staticmethod(lambda **kw: None))
    ),
)
sys.modules.setdefault(
    "isaacsim.core.rendering_manager",
    types.SimpleNamespace(
        RenderingManager=types.SimpleNamespace(render=staticmethod(lambda: None))
    ),
)
sensors_mod = types.ModuleType("isaacsim.sensors.experimental.physics")
sensors_mod.Contact = object
sensors_mod.ContactSensor = object
sys.modules.setdefault("isaacsim.sensors.experimental.physics", sensors_mod)
rtx_mod = types.ModuleType("isaacsim.sensors.experimental.rtx")
rtx_mod.CameraSensor = object
rtx_mod.RtxCamera = object
sys.modules.setdefault("isaacsim.sensors.experimental.rtx", rtx_mod)

import fruit_sorting.tasks as tasks_mod  # noqa: E402
from fruit_sorting.scene import _park_provenance  # noqa: E402
from fruit_sorting.tasks import (  # noqa: E402
    CONTROL_DT,
    PARK_TWO_LINE_DEFAULT,
    PickAndPlaceTask,
    _PARK_SCOPED_BLEND,
    _PARK_SCOPED_SETTLE,
    _PARK_SHIPPED_BLEND,
    _PARK_SHIPPED_SETTLE,
    _PARK_SHIPPED_TICKS,
    park_profile_resolution,
)

TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
SCENE = ROOT / "src" / "fruit_sorting" / "scene.py"
COLLECT = ROOT / "scripts" / "40_collect_demos.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
TASKS_SRC = TASKS.read_text(encoding="utf-8")
SCENE_SRC = SCENE.read_text(encoding="utf-8")

ENVS = ("FRUIT_BIARM_PARK_BLEND", "FRUIT_BIARM_PARK_SETTLE",
        "FRUIT_READY_SETTLE")


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


class cell:
    """Set exactly the given park env vars for the duration of the block."""

    def __init__(self, **env: str):
        self.env = env
        self._saved: dict[str, str] = {}

    def __enter__(self):
        for name in ENVS:
            self._saved[name] = os.environ.pop(name, "")
        for name, value in self.env.items():
            os.environ[name] = str(value)
        return self

    def __exit__(self, *exc):
        for name, value in self._saved.items():
            os.environ.pop(name, None)
            if value:
                os.environ[name] = value
        return False


def main() -> int:
    print("P100 - the park return's fixed clock is a two-line-scoped tick cell")
    print("=" * 78)

    # [1] unset + no session = the shipped pair, exactly.
    with cell():
        single = park_profile_resolution(False)
        check((single["blend"], single["settle"]) == (90, 120),
              f"unset/no-scope resolves the shipped 90/120 "
              f"({single['blend']}/{single['settle']})")
        check(single["origin"] == "scope-off" and single["on"] is False,
              f"… with `origin=scope-off` and the cell off ({single['origin']})")
        check(single["ticks"] == single["shipped_ticks"] == _PARK_SHIPPED_TICKS == 210
              and single["saved_ticks"] == 0,
              "… and its own shipped clock is the same 210 ticks, so saved = 0")

    # [2] the scope is enforced: the env is NOT read outside a two-line session.
    with cell(FRUIT_BIARM_PARK_BLEND="60", FRUIT_BIARM_PARK_SETTLE="75"):
        single = park_profile_resolution(False)
        check((single["blend"], single["settle"]) == (90, 120)
              and single["origin"] == "scope-off",
              "an explicit pair is not read without a two-line session - the "
              "driver's pre-session prime transit keeps the shipped clock")

    # [3] unset + two-line = the shipped pair, and the default is OFF.
    with cell():
        two = park_profile_resolution(True)
        check(PARK_TWO_LINE_DEFAULT is False,
              "the P100 default is OFF (the gate's verdict is `logs/p100/RESULTS.md`)")
        check((two["blend"], two["settle"]) == (90, 120) and two["on"] is False,
              f"unset + two-line resolves the shipped 90/120 ({two['blend']}/"
              f"{two['settle']})")

    # [4] the cell: 60/75 = 135 ticks, saved 75 = -0.625 s, two-line only.
    with cell(FRUIT_BIARM_PARK_BLEND="60", FRUIT_BIARM_PARK_SETTLE="75"):
        treat = park_profile_resolution(True)
        check((treat["blend"], treat["settle"]) == (60, 75),
              f"the cell resolves 60/75 ({treat['blend']}/{treat['settle']})")
        check(treat["origin"] == "explicit" and treat["on"] is True,
              f"… as `origin=explicit` ({treat['origin']})")
        check(treat["ticks"] == 135 and treat["saved_ticks"] == 75,
              f"… 135 of the shipped 210 ticks, saved 75 ({treat['ticks']})")
        check(abs(treat["saved_ticks"] * CONTROL_DT - 0.625) < 5e-4,
              f"… = {treat['saved_ticks'] * CONTROL_DT:.3f} s at 120 Hz "
              "(the registered delta)")
        check(treat["profile"] == "trim",
              "… and the profile names itself `trim`")
    # … the halves are independent overrides, and the clamps hold.
    with cell(FRUIT_BIARM_PARK_SETTLE="75"):
        half = park_profile_resolution(True)
        check((half["blend"], half["settle"]) == (90, 75) and half["on"] is True,
              f"setting only the settle keeps the shipped ramp ({half['blend']}/"
              f"{half['settle']}, saved {half['saved_ticks']})")
    with cell(FRUIT_BIARM_PARK_BLEND="0", FRUIT_BIARM_PARK_SETTLE="0"):
        clamped = park_profile_resolution(True)
        check(clamped["blend"] >= 1 and clamped["settle"] >= 0,
              f"the read sites' own clamps hold (blend {clamped['blend']}, "
              f"settle {clamped['settle']})")

    # [5] the flip's cell resolves 45/45 in the two-line scope only.
    with cell():
        old = tasks_mod.PARK_TWO_LINE_DEFAULT
        tasks_mod.PARK_TWO_LINE_DEFAULT = True
        try:
            scoped = park_profile_resolution(True)
            plain = park_profile_resolution(False)
        finally:
            tasks_mod.PARK_TWO_LINE_DEFAULT = old
        check((scoped["blend"], scoped["settle"]) == (_PARK_SCOPED_BLEND,
                                                      _PARK_SCOPED_SETTLE) == (45, 45),
              f"the flip resolves 45/45 ({scoped['blend']}/{scoped['settle']})")
        check(scoped["origin"] == "default" and scoped["on"] is True,
              f"… as `origin=default` ({scoped['origin']})")
        check(plain["origin"] == "scope-off" and plain["saved_ticks"] == 0,
              "… while every non-two-line path still resolves the shipped 210")

    # [6] the shipped pair is the site's own constants - the pin cannot drift.
    check(_PARK_SHIPPED_BLEND == PickAndPlaceTask.READY_TRANSIT_BLEND_TICKS == 90,
          "the shipped ramp IS `READY_TRANSIT_BLEND_TICKS` (90) - the constant "
          "the transit's own tick accounting reads")
    import inspect
    default_settle = inspect.signature(PickAndPlaceTask._ready_settle).parameters[
        "shipped"].default
    check(default_settle == _PARK_SHIPPED_SETTLE == 120,
          f"the shipped settle IS `_ready_settle`'s own default ({default_settle})")
    check(_PARK_SHIPPED_TICKS == 210, "the two fixed tails are 210 ticks")

    # [7] one consumer, the session predicate; the hardcoded 120 is gone.
    tree = ast.parse(TASKS_SRC)
    ready_move = next((n for n in ast.walk(tree)
                       if isinstance(n, ast.FunctionDef) and n.name == "_ready_move"),
                      None)
    check(ready_move is not None, "`_ready_move` is the consumer")
    body = ast.unparse(ready_move)
    check("park_profile_resolution(self.two_line_enabled())" in body,
          "… and it passes the session predicate (`self.two_line_enabled()`)")
    check('int(park[\'blend\'])' in body and 'int(park[\'settle\'])' in body,
          "… taking both halves from the one resolver")
    check("else 120" not in body,
          "the hardcoded `else 120` is gone from the transit call - one authority")
    callers = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "park_profile_resolution"]
    check(len(callers) == 2,
          f"one resolver call in `_ready_move` + one in the row ({len(callers)})")

    # [8] `q_step` is arithmetic inside the diag block - no read on the shipped path.
    blend_to = next((n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == "_blend_to"),
                    None)
    check(blend_to is not None, "`_blend_to` holds the ramp")
    guarded = [n for n in ast.walk(blend_to)
               if isinstance(n, ast.If)
               and ast.unparse(n.test) == "stats is not None"
               and "q_step" in ast.unparse(n)]
    check(bool(guarded),
          "`q_step` is computed inside `if stats is not None:` (the diag block)")
    check("1.875" in ast.unparse(guarded[0]),
          "… from the min-jerk peak derivative (1.875), i.e. arithmetic on the "
          "two configurations the ramp already holds")
    assigns = [n for n in ast.walk(guarded[0])
               if isinstance(n, ast.Assign)
               and any("q_step" in ast.unparse(t) for t in n.targets)]
    check(len(assigns) == 1 and "joint_positions" not in ast.unparse(assigns[0].value)
          and "jaw_centre" not in ast.unparse(assigns[0].value),
          "… and that assignment adds no articulation read (the block's other "
          "read is P9-A's own `ramp_err`)")

    # [9] the row and the provenance.
    run_bi = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "run_bimanual"), None)
    check(run_bi is not None and "[biarm] park profile:" in ast.unparse(run_bi),
          "the row is inside `run_bimanual` (so only a bimanual session prints it)")

    def _prints_row(fn) -> bool:
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "say"):
                if "[biarm] park profile:" in ast.unparse(node):
                    return True
        return False

    printers = sorted(n.name for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and _prints_row(n))
    check(printers == ["run_bimanual"],
          f"only `run_bimanual` prints the row ({printers}) - the single-arm "
          "path stays silent and therefore byte-identical")

    check("def _park_provenance" in SCENE_SRC,
          "the block has one builder in `scene.py`")
    check('"park": _park_provenance(two_line)' in SCENE_SRC,
          "`finger_physics_provenance` writes it under `physics`")
    check("from .tasks import park_profile_resolution" in SCENE_SRC,
          "… and it reads the one resolver")
    keys = ("blend", "settle", "ticks", "shipped_ticks", "saved_ticks",
            "profile", "origin", "two_line")
    for scope in (False, True):
        block = _park_provenance(scope)
        check(all(k in block for k in keys),
              f"the block carries the required keys, scope two_line={scope}")
        check(block["ticks"] == park_profile_resolution(scope)["ticks"]
              and block["two_line"] is scope,
              f"… and matches the resolver for two_line={scope}")
    writers = sum(path.read_text(encoding="utf-8").count("finger_physics_provenance(")
                  for path in (COLLECT, RL_ENV))
    check(writers >= 2,
          f"both manifest writers call the one builder ({writers} call sites)")

    # [10] the pin, reported (the shipped selfcheck asserts the equality).
    from fruit_sorting.rl_env import TASKS_MD5  # noqa: E402

    actual = hashlib.md5(TASKS.read_bytes()).hexdigest()
    check(TASKS_MD5 == actual, f"TASKS_MD5 follows tasks.py ({TASKS_MD5[:8]})")

    print("=" * 78)
    print("PASS: the park cell is two-line-scoped, its default is OFF, and the "
          "measured arm is explicit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
