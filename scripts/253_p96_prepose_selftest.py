#!/usr/bin/env python3
"""P96 selftest: the **clearance pre-pose** is a two-line-scoped, default-off cell.

    python3 scripts/253_p96_prepose_selftest.py

No simulator (the `247`/`248` stub-the-imports pattern): the **real**
`prepose_clear_resolution` runs, and the solve site is pinned from the source.

Why each item matters. P95 measured the defect - the two-line pre-pose dives to
the **grasp plane** (the left station's pose is the calibrated `grasp` config, so
its pads end 29 mm below a fruit's top) and the pre-pose blend therefore sweeps
*through* the fruit band on every attempt, while the stations are ordered so a
**right**-arm fruit must cross the **left** station: 1 pad contact in 40
attempts, 5/19 right-arm attempts inside 6.4 mm. P96's fix is one solve height.
This leg pins:

1. **The resolver table.** Unset + no two-line session is `scope-off`; unset +
   two-line is `PREPOSE_CLEAR_TWO_LINE_DEFAULT` (False while the ship decision is
   open, i.e. the pre-P96 path bit for bit); `=0` is the pre-P96 path explicitly;
   `=1` is on; the height band `[0.155, 0.25]` raises outside itself (a
   "clearance" pose below the invariant only looks configured), and so does an
   unknown hold mode.
2. **The height arithmetic.** The solve lands its residual **low**, so the
   registered target must be the invariant *plus* the solve tolerance:
   `0.165 - 0.006 = 0.159 >= 0.155` passes, `0.155 - 0.006 = 0.149 < 0.155`
   fails - which is exactly what the phase-0 map measured (achieved jaw
   149.1-151.7 mm at a 0.155 target, 159.1-160.2 mm at 0.165).
3. **The solve site** (AST): one `prepose_clear_resolution` call, in
   `_prepare_two_line_stations`; the station skip is bypassed when the cell is on
   (the left station *is* the pick point - P39 - so this is the whole point); the
   hold is the measured calibrated attitude (`capture_hold_pose`) or free
   (`nat`); the target is `belt_top + clear["z"]`; the cache identity carries the
   resolution (a phase's A/B re-solves in one process).
4. **The print is gated.** The `[biarm] pre-pose` row lives inside `if clear["on"]:`
   - so the pre-P96 path prints nothing new, which is what makes the control cell
   byte-identical to its record rather than "identical modulo a row".
5. **The provenance.** The collector resolves the same function and writes
   `collection.prepose_clear` / `prepose_clear_defaulted` / `prepose_clear_z`.
6. **`TASKS_MD5`** in `rl_env.py` matches the shipped `tasks.py` (the metadata
   guard: the direct/policy path must be able to start).

Exit 0 on pass, 1 on the first failure. Run by `scripts/selfcheck.sh`.
"""

from __future__ import annotations

import ast
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks ---------- #
for name in (
    "pxr",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.core.experimental.utils",
    "isaacsim.core.experimental.objects",
    "isaacsim.core.experimental.utils.app",
    "isaacsim.core.experimental.utils.stage",
    "isaacsim.core.experimental.prims",
    "isaacsim.sensors",
    "isaacsim.sensors.experimental",
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
    types.SimpleNamespace(SimulationManager=types.SimpleNamespace(step=staticmethod(lambda **kw: None))),
)
sys.modules.setdefault(
    "isaacsim.core.rendering_manager",
    types.SimpleNamespace(RenderingManager=types.SimpleNamespace(render=staticmethod(lambda: None))),
)
sensors_mod = types.ModuleType("isaacsim.sensors.experimental.physics")
sensors_mod.Contact = object
sensors_mod.ContactSensor = object
sys.modules.setdefault("isaacsim.sensors.experimental.physics", sensors_mod)
rtx_mod = types.ModuleType("isaacsim.sensors.experimental.rtx")
rtx_mod.CameraSensor = object
rtx_mod.RtcCamera = object
sys.modules.setdefault("isaacsim.sensors.experimental.rtx", rtx_mod)

from fruit_sorting.tasks import (  # noqa: E402
    PREPOSE_CLEAR_TWO_LINE_DEFAULT,
    _PREPOSE_CLEAR_HOLD_SHIPPED,
    _PREPOSE_CLEAR_Z_MAX,
    _PREPOSE_CLEAR_Z_MIN,
    _PREPOSE_CLEAR_Z_SHIPPED,
    prepose_clear_resolution,
)

TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
COLLECT = ROOT / "scripts" / "40_collect_demos.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
TASKS_SRC = TASKS.read_text(encoding="utf-8")
COLLECT_SRC = COLLECT.read_text(encoding="utf-8")
RL_ENV_SRC = RL_ENV.read_text(encoding="utf-8")

ENVS = (
    "FRUIT_BIARM_PREPOSE_CLEAR",
    "FRUIT_BIARM_PREPOSE_CLEAR_Z",
    "FRUIT_BIARM_PREPOSE_CLEAR_HOLD",
)


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


class cells:
    """Set exactly the given pre-pose env vars for the duration of the block."""

    def __init__(self, **env: str):
        self.env = env

    def __enter__(self):
        for name in ENVS:
            os.environ.pop(name, None)
        for name, value in self.env.items():
            os.environ[name] = str(value)
        return self

    def resolution(self, two_line: bool) -> dict:
        return prepose_clear_resolution(two_line)

    def __exit__(self, *exc):
        for name in ENVS:
            os.environ.pop(name, None)
        return False


def node_at(src: str, name: str) -> ast.AST:
    tree = ast.parse(src)
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    check(len(hits) == 1, f"`{name}` is defined once in tasks.py")
    return hits[0]


def count_calls(src: str, attr: str) -> int:
    tree = ast.parse(src)
    return sum(
        1
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == attr
    )


def main() -> int:
    print("P96 - the clearance pre-pose is a two-line-scoped, default-off cell")
    print("=" * 78)

    # [1] the resolver table ------------------------------------------------ #
    check(PREPOSE_CLEAR_TWO_LINE_DEFAULT is False,
          "PREPOSE_CLEAR_TWO_LINE_DEFAULT is False - the cell is not shipped yet")
    with cells() as c:
        plain = c.resolution(False)
        check(plain["on"] is False and plain["origin"] == "scope-off",
              "unset + no two-line session is off with origin `scope-off`")
        check(plain["z"] == _PREPOSE_CLEAR_Z_SHIPPED and plain["z_defaulted"] is True,
              f"the height defaults to {_PREPOSE_CLEAR_Z_SHIPPED} m above the belt top")
        check(plain["hold"] == _PREPOSE_CLEAR_HOLD_SHIPPED,
              f"the attitude defaults to `{_PREPOSE_CLEAR_HOLD_SHIPPED}`")
        tl = c.resolution(True)
        check(tl["on"] is False,
              "unset inside a two-line session follows the (still False) scoped default")
        check(tl["two_line"] is True and tl["origin"] == "explicit",
              "… and says so in `two_line`/`origin`")
    with cells(FRUIT_BIARM_PREPOSE_CLEAR="0") as c:
        r = c.resolution(True)
        check(r["on"] is False and r["origin"] == "explicit",
              "an explicit =0 is the pre-P96 path, origin `explicit`")
        check("z=" not in r["label"], "… and the label carries no height")
    with cells(FRUIT_BIARM_PREPOSE_CLEAR="1") as c:
        r = c.resolution(True)
        check(r["on"] is True and r["origin"] == "explicit" and r["z"] == 0.165,
              "=1 is on at the default height (0.165)")
        check(r["label"] == "FRUIT_BIARM_PREPOSE_CLEAR=1(explicit), z=+0.165, hold=calib",
              f"the label names value, origin, height and hold ({r['label']})")
        check(c.resolution(False)["on"] is True,
              "… an explicit =1 also applies outside a two-line session (the override rule)")

    # [2] the height arithmetic the phase-0 map measured --------------------- #
    check(abs((_PREPOSE_CLEAR_Z_SHIPPED - 0.006) - 0.159) < 1e-9,
          "a 0.165 target with the solve's 6 mm residual lands at 0.159")
    check(_PREPOSE_CLEAR_Z_SHIPPED - 0.006 >= _PREPOSE_CLEAR_Z_MIN,
          "… which clears the invariant's floor (jaw >= belt_top + 0.155)")
    check((_PREPOSE_CLEAR_Z_MIN - 0.006) < _PREPOSE_CLEAR_Z_MIN,
          "… while a 0.155 target would land at 0.149, i.e. BELOW the floor "
          "(the phase-0 map's 149.1-151.7 mm rows)")
    check(_PREPOSE_CLEAR_Z_MIN == 0.155 and _PREPOSE_CLEAR_Z_MAX == 0.25,
          "the band is [0.155, 0.25] - the invariant's floor and the map's ceiling")
    for bad in ("0.12", "0.30", "0.0", "-0.1"):
        with cells(FRUIT_BIARM_PREPOSE_CLEAR="1", FRUIT_BIARM_PREPOSE_CLEAR_Z=bad):
            try:
                prepose_clear_resolution(True)
            except ValueError:
                pass
            else:
                check(False, f"a height of {bad} m must raise")
        print(f"ok: a height of {bad} m raises")
    with cells(FRUIT_BIARM_PREPOSE_CLEAR="1", FRUIT_BIARM_PREPOSE_CLEAR_Z="0.18") as c:
        check(c.resolution(True)["z"] == 0.18 and c.resolution(True)["z_defaulted"] is False,
              "a registered override moves the height and clears `z_defaulted`")
    with cells(FRUIT_BIARM_PREPOSE_CLEAR="1", FRUIT_BIARM_PREPOSE_CLEAR_HOLD="nat") as c:
        check(c.resolution(True)["hold"] == "nat", "hold=nat is the free-attitude form")
    with cells(FRUIT_BIARM_PREPOSE_CLEAR="1", FRUIT_BIARM_PREPOSE_CLEAR_HOLD="c0"):
        try:
            prepose_clear_resolution(True)
        except ValueError:
            print("ok: an unknown hold mode raises")
        else:
            check(False, "an unknown hold mode must raise")
    with cells(FRUIT_BIARM_PREPOSE_CLEAR="1", FRUIT_BIARM_PREPOSE_CLEAR_Z="0.12"):
        try:
            prepose_clear_resolution(False)
        except ValueError:
            print("ok: the band is enforced even with no two-line session (an explicit =1)")
        else:
            check(False, "the band must be enforced whenever the cell resolves on")

    # [3] the solve site (AST) ---------------------------------------------- #
    check(count_calls(TASKS_SRC, "prepose_clear_resolution") == 1,
          "`prepose_clear_resolution` has exactly one call site in tasks.py")
    prep = node_at(TASKS_SRC, "_prepare_two_line_stations")
    body = ast.unparse(prep)
    check('prepose_clear_resolution(self.two_line_enabled())' in body,
          "the call site is the station solve and passes the session predicate")
    check("if on_pick_point and (not clear['on'])" in body,
          "the station-on-the-pick-point skip is bypassed when the cell is on "
          "(the left station had no solve at all - P39)")
    check("capture_hold_pose()" in body,
          "hold=calib freezes the arm's own **measured** calibrated attitude")
    check("clear['hold'] == 'calib'" in body and "arm.hold_quaternion = None" in body,

          "hold=nat leaves the attitude free (the position-only form)")
    check("z_above_belt = float(clear['z'])" in body
          and "z_above_belt = float(self.cfg.grasp_clearance)" in body,
          "the target height is the cell's when on and the grasp plane when off")
    check("cache = (key, bool(clear['on']), float(clear['z']) if clear['on'] else None)" in body,
          "the solve cache carries the resolution (one process, two cells)")
    check("self._prepose_clear_ok[side]" in body,
          "the per-side verdict is recorded, not inferred from the residual")
    check("_tilt_deg(achieved_quat)" in body and "margin" in body,
          "the achieved tilt and joint margin are read at the solve")
    # the print is gated: the row must be inside the `if clear["on"]:` block
    gated = False
    for node in ast.walk(prep):
        if isinstance(node, ast.If) and "clear['on']" in ast.unparse(node.test):
            if "[biarm] pre-pose" in ast.unparse(node):
                gated = True
    check(gated,
          "the `[biarm] pre-pose` row is printed **only** when the cell is on, so the "
          "pre-P96 path adds no line (byte-identity, not 'modulo a row')")

    # [4] the collector's provenance ---------------------------------------- #
    check("PREPOSE = prepose_clear_resolution(TWO_LINE)" in COLLECT_SRC,
          "the collector resolves the same function, per shard")
    for key in ('"prepose_clear": int(PREPOSE["on"])',
                '"prepose_clear_defaulted": bool(PREPOSE["origin"] != "explicit")',
                '"prepose_clear_z": float(PREPOSE["z"]) if PREPOSE["on"] else 0.0'):
        check(key in COLLECT_SRC, f"the shard manifest writes {key.split(':')[0]}")

    # [5] the metadata pin --------------------------------------------------- #
    import hashlib

    digest = hashlib.md5(TASKS.read_bytes()).hexdigest()
    pin = next((ln.split('"')[1] for ln in RL_ENV_SRC.splitlines()
                if ln.startswith("TASKS_MD5 = ")), "")
    check(pin == digest,
          f"rl_env.TASKS_MD5 == tasks.py ({digest[:8]}) - the direct env can start")

    print()
    print("P96 pre-pose selftest: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
