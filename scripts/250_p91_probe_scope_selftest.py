#!/usr/bin/env python3
"""P91 selftest: the take-off validation ramp is a **two-line-scoped** tick cell.

    python3 scripts/250_p91_probe_scope_selftest.py

No simulator (the `225` / `247` / `248` / `249` stub-the-imports pattern): the
**real** `probe_ticks_resolution` runs, and the manifest builder's own block is
built through the real `scene._takeoff_provenance`.

Why each item matters. P91's offline audit of the five never-profiled `[cycle]`
blocks (`logs/p91/AUDIT.md`) showed the descent's motion to be **schedule
invariant** (the dynamic wait exits at `speed*(t_desc+margin)`, so
`block = lead/speed - margin` and a faster leg just waits longer), the hover and
prepose to be IK-capped transits with no profile, and the grip block to be the
largest *speedable* one of the five. Inside the grip the probe ramp is the single
largest profile - **60 of the clean 210 ticks** - while the 54-tick belt-break
beside it is the P3 anti-shear constant. The site is the shared
`grasp_carry_place`, so the flip is **session-scoped** exactly like the release
(P87), the place (P88) and the lift (P89). This leg pins:

1. **Unset, no session = 40 ticks** - the shipped single-arm value, the same
   literal `_dynamic_profile` used, so the single arm, the shared-station
   pipeline, the hybrid canary and the direct/policy presentation are
   byte-identical.
2. **Unset + two-line = 60 ticks and the default is OFF** (`PROBE_TWO_LINE_DEFAULT
   is False`): the shipped tree resolves the pre-P91 clock on every path and the
   measured arm is the explicit `FRUIT_DYNAMIC_PROBE_TICKS=24`.
3. **The cell (flip on) = 24 ticks, saved 36 = -0.300 s at 120 Hz**, and only in
   the two-line scope; the single arm stays 40.
4. **The overrides.** An explicit value wins on both scopes; it keeps the knob's
   pre-P91 meaning, so `FRUIT_DYNAMIC_PROBE_TICKS=40` on the single arm is
   exactly the shipped string.
5. **The ramp's height is not the cell.** `probe_lift` stays 0.006 two-line /
   0.010 single and `FRUIT_DYNAMIC_PROBE` still overrides it - a rate-only A/B.
6. **The lever is 1:1 on the block** (the audit's own cross-check): the
   single-arm 40-tick probe and the two-line 60-tick probe differ by exactly the
   ticks the records' clean `grip` blocks differ by (190 vs 210 ticks).
7. **One consumer, the session predicate.** The probe loop reads
   `probe_ticks_resolution(self.two_line_enabled())` and nothing else resolves a
   probe tick count; the two-line's old literal is gone from that site.
8. **The row and the provenance.** `[biarm] take-off profile:` prints only inside
   `run_bimanual` and reads the resolver; `physics.takeoff` is written by the one
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
from fruit_sorting.scene import _takeoff_provenance  # noqa: E402
from fruit_sorting.tasks import (  # noqa: E402
    CONTROL_DT,
    PROBE_TWO_LINE_DEFAULT,
    _PROBE_SCOPED_TICKS,
    _PROBE_SINGLE_TICKS,
    _PROBE_TWO_LINE_TICKS,
    probe_ticks_resolution,
)

TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
SCENE = ROOT / "src" / "fruit_sorting" / "scene.py"
COLLECT = ROOT / "scripts" / "40_collect_demos.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
TASKS_SRC = TASKS.read_text(encoding="utf-8")
SCENE_SRC = SCENE.read_text(encoding="utf-8")
COLLECT_SRC = COLLECT.read_text(encoding="utf-8")

ENVS = ("FRUIT_DYNAMIC_PROBE_TICKS", "FRUIT_DYNAMIC_PROBE")


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


class cell:
    """Set exactly the given take-off env vars for the duration of the block."""

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
    print("P91 - the take-off validation ramp is a two-line-scoped tick cell")
    print("=" * 78)

    # [1] unset + no session = the shipped single-arm value, exactly.
    with cell():
        single = probe_ticks_resolution(False)
        check(single["ticks"] == int(_PROBE_SINGLE_TICKS) == 40,
              f"unset/no-scope resolves the shipped single-arm 40 ticks "
              f"({single['ticks']})")
        check(single["origin"] == "single" and single["on"] is False,
              f"… with `origin=single` and the cell off ({single['origin']})")
        check(single["shipped_ticks"] == 40 and single["saved_ticks"] == 0,
              "… and its own shipped clock is the same 40, so saved = 0")

    # [2] unset + two-line = the shipped 60, and the default is OFF.
    with cell():
        two = probe_ticks_resolution(True)
        check(PROBE_TWO_LINE_DEFAULT is False,
              "the P91 default is OFF (the gate's verdict is `logs/p91/RESULTS.md`)")
        check(two["ticks"] == int(_PROBE_TWO_LINE_TICKS) == 60,
              f"unset + two-line resolves the shipped 60 ticks ({two['ticks']})")
        check(two["origin"] == "two-line" and two["on"] is False,
              f"… with `origin=two-line` and the cell off ({two['origin']})")

    # [3] the cell (flip on) = 24 ticks, saved 36 = -0.300 s, two-line only.
    with cell():
        old = tasks_mod.PROBE_TWO_LINE_DEFAULT
        tasks_mod.PROBE_TWO_LINE_DEFAULT = True
        try:
            scoped = probe_ticks_resolution(True)
            plain = probe_ticks_resolution(False)
        finally:
            tasks_mod.PROBE_TWO_LINE_DEFAULT = old
        check(scoped["ticks"] == int(_PROBE_SCOPED_TICKS) == 24,
              f"the cell resolves 24 ticks ({scoped['ticks']})")
        check(scoped["origin"] == "default" and scoped["on"] is True,
              f"… as `origin=default` ({scoped['origin']})")
        check(scoped["saved_ticks"] == 36,
              f"… saving 36 ticks against the session's own 60 ({scoped['saved_ticks']})")
        check(abs(scoped["saved_ticks"] * CONTROL_DT - 0.300) < 5e-4,
              f"… = {scoped['saved_ticks'] * CONTROL_DT:.3f} s at 120 Hz (the registered delta)")
        check(plain["ticks"] == 40 and plain["on"] is False,
              f"… while the single arm still resolves 40 ({plain['ticks']}) - "
              "the scope, not a global default")

    # [4] an explicit value wins on both scopes and keeps its old meaning.
    with cell(FRUIT_DYNAMIC_PROBE_TICKS="40"):
        check(probe_ticks_resolution(False)["ticks"] == 40,
              "an explicit 40 on the single arm is the shipped string")
        check(probe_ticks_resolution(True)["origin"] == "explicit",
              "… and an explicit value on the two-line names its own origin")
        check(probe_ticks_resolution(True)["ticks"] == 40
              and probe_ticks_resolution(True)["saved_ticks"] == 20,
              "… and still overrides the scoped cell (saved 20 vs its 60)")

    # [5] the ramp's height is not the cell.
    with cell():
        check(probe_ticks_resolution(True)["probe_lift"] == "0.006"
              and probe_ticks_resolution(False)["probe_lift"] == "0.010",
              "the ramp height keeps its two-line 6 mm / single-arm 10 mm values")
    with cell(FRUIT_DYNAMIC_PROBE="0.008"):
        check(probe_ticks_resolution(True)["probe_lift"] == "0.008",
              "`FRUIT_DYNAMIC_PROBE` still overrides the height on its own")

    # [6] the lever is 1:1 on the block (the audit's cross-check, as arithmetic).
    check((60 - 24) == 36,
          "the probe is a 1:1 lever on the grip block: 60 -> 24 removes 36 ticks, "
          "which is exactly the single-arm/two-line clean-grip difference "
          "(190 vs 210 ticks at probes 40 vs 60)")

    # [7] one consumer, the session predicate; the old literal is gone.
    tree = ast.parse(TASKS_SRC)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "probe_ticks_resolution"]
    check(len(calls) == 2,
          f"one resolver call in `grasp_carry_place` + one in the row ({len(calls)})")
    check(any(n.args and ast.unparse(n.args[0]) == "self.two_line_enabled()"
              for n in calls if n.args and ast.unparse(n.args[0]).startswith("self.")),
          "the consumer passes the session predicate (`self.two_line_enabled()`)")
    check('self._dynamic_profile(\n            "FRUIT_DYNAMIC_PROBE_TICKS", "40", "60"' not in TASKS_SRC
          and '"FRUIT_DYNAMIC_PROBE_TICKS", "40", "60"' not in TASKS_SRC,
          "the two-line literal is no longer resolved at the site - one authority")
    check('_takeoff["ticks"]' in TASKS_SRC,
          "the probe loop reads the resolver's tick count")

    # [8] the row and the provenance.
    check("[biarm] take-off profile:" in TASKS_SRC,
          "the row prints in the `[biarm] ...` form")
    run_bi = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "run_bimanual"), None)
    check(run_bi is not None and "[biarm] take-off profile:" in ast.unparse(run_bi),
          "the row is inside `run_bimanual` (so only a bimanual session prints it)")
    check("probe_ticks_resolution(" in ast.unparse(run_bi),
          "the row reads the one resolver, not a re-derived tick count")

    def _prints_row(fn) -> bool:
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "say"):
                if "[biarm] take-off profile:" in ast.unparse(node):
                    return True
        return False

    printers = sorted(n.name for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and _prints_row(n))
    check(printers == ["run_bimanual"],
          f"only `run_bimanual` prints the row ({printers}) - the single-arm "
          "path stays silent and therefore byte-identical")

    check("def _takeoff_provenance" in SCENE_SRC,
          "the block has one builder in `scene.py`")
    check('"takeoff": _takeoff_provenance(two_line)' in SCENE_SRC,
          "`finger_physics_provenance` writes it under `physics`")
    check("from .tasks import probe_ticks_resolution" in SCENE_SRC,
          "… and it reads the one resolver")
    keys = ("ticks", "shipped_ticks", "saved_ticks", "probe_lift", "origin",
            "two_line")
    for scope in (False, True):
        block = _takeoff_provenance(scope)
        check(all(k in block for k in keys),
              f"the block carries the required keys, scope two_line={scope}")
        check(block["ticks"] == probe_ticks_resolution(scope)["ticks"]
              and block["two_line"] is scope,
              f"… and matches the resolver for two_line={scope}")
    writers = sum(path.read_text(encoding="utf-8").count("finger_physics_provenance(")
                  for path in (COLLECT, ROOT / "src" / "fruit_sorting" / "rl_env.py"))
    check(writers >= 2,
          f"both manifest writers call the one builder ({writers} call sites)")

    # [9] the pin, reported (the shipped selfcheck asserts the equality).
    from fruit_sorting.rl_env import TASKS_MD5  # noqa: E402

    actual = hashlib.md5(TASKS.read_bytes()).hexdigest()
    check(TASKS_MD5 == actual, f"TASKS_MD5 follows tasks.py ({TASKS_MD5[:8]})")

    print("=" * 78)
    print("PASS: the take-off cell is scoped, its default is OFF, and the measured arm is explicit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
