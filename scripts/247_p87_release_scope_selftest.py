#!/usr/bin/env python3
"""P87 selftest: the release trim is a **two-line-scoped** default.

    python3 scripts/247_p87_release_scope_selftest.py

No simulator (the `225` stub-the-imports pattern): the **real**
`release_speed_resolution` / `speed_cell_defaults` run, and the manifest
builder's own block is built through the real `scene._release_provenance`.

Why each item matters. P86 measured the S2 trim (`FRUIT_SPEED_RELEASE`: dwell
20 -> 0, the pad ramp 40 x (3 -> 2), the finger ramp 16 x (3 -> 2) = **-76
ticks = -0.633 s**) as a clean positive on the shipped two-line - and the knob
is read at a site **every** presentation shares (`_grasp_carry_place_impl`'s
release block). P87 therefore ships it as a **session-scoped** default rather
than a global one, and this leg pins the scope:

1. **Unset, no session = the shipped strings.** `speed_cell_defaults()` (and
   `speed_cell_defaults(False)`) must still return `_SPEED_SHIPPED` *exactly*
   (string-for-string), so `os.environ.get` falls back to the same literal and
   the single arm, the shared-station pipeline, the hybrid canary and the
   direct/policy presentation cannot move - the `225` contract, re-asserted for
   the scoped form.
2. **Unset + two-line = the measured trim** (`0/2/2`, 112 ticks, saved 76,
   origin `default`) - the arm P86 measured must be what a defaulted two-line
   run resolves.
3. **The overrides.** `FRUIT_SPEED_RELEASE=0` restores the shipped clock *even
   on the two-line*; an explicit `=1` wins **globally** (the single arm too);
   `FRUIT_SPEED_ALL=1` (S13) wins globally; an explicit `=0` beats the union;
   `FRUIT_SPEED_RELEASE_SETTLE` still moves the settle, and is read only when
   the cell is on.
4. **The clock arithmetic** is the read sites' own clamps
   (`max(0, dwell) + 40*max(1, pad) + 16*max(1, finger)`): 188 shipped,
   112 trimmed, 76 saved - the delta P86 registered (its PREREG's absolute
   208/132 rows carry a +20 slip in *both*, so the delta is unaffected).
5. **The scope is the session predicate.** The release-carrying call site
   passes `self.two_line_enabled()` (AST), which is `session.twoline` - False
   whenever no `CoopSession` is active - and the per-leg `_carry_leg` consumer
   keeps the unscoped call (it reads the place/lift keys only).
6. **The row exists and names the resolution** in `run_bimanual` (both modes),
   in the `[biarm] scheduler:` / `[drive] finger cap scope:` form, inside the
   session scope and **never** on the single-arm path (that is what makes the
   single-arm acceptance byte-identical rather than "identical modulo a row").
7. **The provenance.** `scene._release_provenance` writes
   `physics.release={dwell,pad_hold,finger_hold,...}` and matches the resolver
   for both scopes, and **both** manifest writers pass their own scope into
   `finger_physics_provenance` (the collector its `TWO_LINE`, the direct env
   `False`).
8. **`TASKS_MD5` provenance** is the `rl_env` metadata pin - the shipped
   selfcheck already asserts the equality; here it is only reported.

Exit 0 on pass, 1 on the first failure. Run by `scripts/selfcheck.sh`.
"""
from __future__ import annotations

import ast
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

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
    module.__path__ = []  # a package, so the submodule imports below resolve
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
    types.SimpleNamespace(SimulationManager=SimpleNamespace(step=staticmethod(lambda **kw: None))),
)
sys.modules.setdefault(
    "isaacsim.core.rendering_manager",
    types.SimpleNamespace(RenderingManager=SimpleNamespace(render=staticmethod(lambda: None))),
)
sensors_mod = types.ModuleType("isaacsim.sensors.experimental.physics")
sensors_mod.Contact = object
sensors_mod.ContactSensor = object
sys.modules.setdefault("isaacsim.sensors.experimental.physics", sensors_mod)
rtx_mod = types.ModuleType("isaacsim.sensors.experimental.rtx")
rtx_mod.CameraSensor = object
rtx_mod.RtxCamera = object
sys.modules.setdefault("isaacsim.sensors.experimental.rtx", rtx_mod)

from fruit_sorting.tasks import (  # noqa: E402
    _SPEED_SHIPPED,
    release_speed_resolution,
    speed_cell_defaults,
)

TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
SCENE = ROOT / "src" / "fruit_sorting" / "scene.py"
COLLECT = ROOT / "scripts" / "40_collect_demos.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
TASKS_SRC = TASKS.read_text(encoding="utf-8")
SCENE_SRC = SCENE.read_text(encoding="utf-8")
COLLECT_SRC = COLLECT.read_text(encoding="utf-8")
RL_ENV_SRC = RL_ENV.read_text(encoding="utf-8")

ENVS = (
    "FRUIT_SPEED_RELEASE",
    "FRUIT_SPEED_RELEASE_SETTLE",
    "FRUIT_SPEED_ALL",
)

#: The three hold keys this phase scopes, in `_SPEED_SHIPPED`'s spelling.
HOLDS = ("release_dwell", "release_pad_hold", "release_finger_hold")


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


class cells:
    """Set exactly the given speed-cell env vars for the duration of the block."""

    def __init__(self, **env: str):
        self.env = env

    def __enter__(self):
        for name in ENVS:
            os.environ.pop(name, None)
        for name, value in self.env.items():
            os.environ[name] = str(value)
        return self

    def resolution(self, two_line: bool) -> dict:
        return release_speed_resolution(two_line)

    def defaults(self, two_line: bool) -> dict:
        return speed_cell_defaults(two_line)

    def __exit__(self, *exc):
        for name in ENVS:
            os.environ.pop(name, None)
        return False


def holds(d: dict) -> tuple[str, str, str]:
    return tuple(d[key] for key in HOLDS)


def main() -> int:
    print("P87 - the release trim is a two-line-scoped default")
    print("=" * 78)

    # [1] unset + no session = the shipped strings, exactly.
    with cells() as c:
        plain = c.defaults(False)
        check(plain == _SPEED_SHIPPED,
              f"unset/no-scope resolves to the shipped dict exactly ({holds(plain)})")
        check(all(isinstance(v, str) for v in plain.values()),
              "every shipped default is still a string (no float round-trip)")
        check(holds(plain) == ("20", "3", "3"), "the shipped release clock is 20/3/3")
        res = c.resolution(False)
        check(res["on"] is False and res["origin"] == "scope-off",
              "unset/no-scope is off with origin `scope-off`")
        check(res["ticks"] == 188 and res["saved_ticks"] == 0,
              "the shipped clock is 188 ticks (20 + 40*3 + 16*3) and saves nothing")

    # [2] unset + two-line = P86's measured arm.
    with cells() as c:
        res = c.resolution(True)
        d = c.defaults(True)
        check(holds(d) == ("0", "2", "2"),
              "unset inside a two-line session resolves P86's trim (0/2/2)")
        check(res["on"] is True and res["origin"] == "default",
              "the two-line default is on with origin `default`")
        check(res["profile"] == "trim", "the profile reads `trim`")
        check(res["ticks"] == 112, "the trim clock is 112 ticks (0 + 40*2 + 16*2)")
        check(res["saved_ticks"] == 76, "the trim saves 76 ticks (0.633 s at 120 Hz)")
        check(res["label"] == "FRUIT_SPEED_RELEASE=1(default)",
              f"the label is the P43 form ({res['label']})")
        # the scope touches the three release keys and nothing else.
        unset = c.defaults(False)
        moved = {k for k in d if d[k] != unset[k]}
        check(moved == set(HOLDS),
              f"only the three release keys move with the scope ({sorted(moved)})")

    # [3] the override table.
    with cells(FRUIT_SPEED_RELEASE="0") as c:
        check(c.defaults(True) == _SPEED_SHIPPED,
              "an explicit =0 restores the shipped clock on the two-line line")
        check(c.resolution(True)["origin"] == "explicit",
              "an explicit 0 is labelled `explicit` (not the scope default)")
    with cells(FRUIT_SPEED_RELEASE="1") as c:
        check(holds(c.defaults(False)) == ("0", "2", "2"),
              "an explicit =1 wins globally (the single-arm line too)")
        check(holds(c.defaults(True)) == ("0", "2", "2"),
              "an explicit =1 also wins on the two-line line")
        check(c.resolution(False)["on"] is True, "the single-arm resolution is on")
    with cells(FRUIT_SPEED_ALL="1") as c:
        check(holds(c.defaults(False)) == ("0", "2", "2"),
              "FRUIT_SPEED_ALL=1 (the S13 union) still turns the cell on globally")
        check(c.resolution(False)["origin"] == "speed-all",
              "the union's origin is `speed-all`")
    with cells(FRUIT_SPEED_ALL="1", FRUIT_SPEED_RELEASE="0") as c:
        check(holds(c.defaults(False)) == ("20", "3", "3"),
              "an explicit =0 beats the union (225's own precedence rule)")
    with cells(FRUIT_SPEED_RELEASE="1", FRUIT_SPEED_RELEASE_SETTLE="1") as c:
        check(holds(c.defaults(False)) == ("0", "1", "1"),
              "FRUIT_SPEED_RELEASE_SETTLE still moves the settle (the 3 -> 1 form)")
        check(c.resolution(False)["ticks"] == 56, "the 3 -> 1 form is 56 ticks")
    with cells(FRUIT_SPEED_RELEASE_SETTLE="1") as c:
        check(holds(c.defaults(False)) == ("20", "3", "3"),
              "the settle is read only when the cell is on (the shipped clock is 20/3/3)")
        check(holds(c.defaults(True)) == ("0", "1", "1"),
              "… and it applies to the scoped two-line default too")

    # [4] the read sites' own clamps, recomputed independently.
    with cells() as c:
        for two_line, want in ((False, 188), (True, 112)):
            res = c.resolution(two_line)
            dwell, pad, fing = (int(res[k]) for k in ("dwell", "pad_hold", "finger_hold"))
            check(res["ticks"] == max(0, dwell) + 40 * max(1, pad) + 16 * max(1, fing)
                  == want,
                  f"the {want}-tick clock is the read sites' own clamps "
                  f"(two_line={int(two_line)})")

    # [5] the scope is the session predicate, at the release-carrying site.
    tree = ast.parse(TASKS_SRC)
    scoped_calls = [n for n in ast.walk(tree)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "speed_cell_defaults"]
    check(len(scoped_calls) == 2,
          f"two consumers build the resolver dict ({len(scoped_calls)})")
    scoped = [n for n in scoped_calls if n.args]
    check(len(scoped) == 1,
          "exactly one consumer passes the session scope (the release-carrying one)")
    check(ast.unparse(scoped[0].args[0]) == "self.two_line_enabled()",
          "the scope argument is the session predicate "
          f"(`{ast.unparse(scoped[0].args[0])}`)")
    enabled = next((n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "two_line_enabled"), None)
    check(enabled is not None, "`two_line_enabled` exists")
    body = ast.unparse(enabled)
    norm = body.replace("'", '"')
    check('getattr(session, "twoline", False)' in norm and "session is None" in norm,
          "`two_line_enabled` is session-scoped (None outside a CoopSession)")

    # [6] the row: in `run_bimanual`, naming the resolution, never on the single arm.
    check("[biarm] release profile:" in TASKS_SRC,
          "the row prints in the `[biarm] ...` form")
    run_bi = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "run_bimanual"), None)
    check(run_bi is not None and "[biarm] release profile:" in ast.unparse(run_bi),
          "the row is inside `run_bimanual` (so only a bimanual session prints it)")
    def _prints_row(fn) -> bool:
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "say"):
                text = ast.unparse(node)
                if "[biarm] release profile:" in text:
                    return True
        return False

    printers = sorted(n.name for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and _prints_row(n))
    check(printers == ["run_bimanual"],
          f"only `run_bimanual` prints the row ({printers}) - the single-arm "
          "path stays silent and therefore byte-identical")
    check("release_speed_resolution(" in ast.unparse(run_bi),
          "the row reads the one resolver, not a re-derived clock")

    # [7] the provenance: one builder, both writers, the three required keys.
    check("def _release_provenance" in SCENE_SRC,
          "the block has one builder in `scene.py`")
    check('"release": _release_provenance(two_line)' in SCENE_SRC,
          "`finger_physics_provenance` writes it under `physics`")
    check("from .tasks import release_speed_resolution" in SCENE_SRC,
          "the builder reads the same resolver the run does")
    check("two_line=TWO_LINE" in COLLECT_SRC,
          "the collector passes its own scheduler mode")
    check("two_line=False" in RL_ENV_SRC,
          "the direct env passes False (it never runs a CoopSession)")

    from fruit_sorting.scene import _release_provenance  # noqa: E402

    with cells() as c:
        shipped = _release_provenance(False)
        trimmed = _release_provenance(True)
        check(all(k in shipped and k in trimmed for k in ("dwell", "pad_hold", "finger_hold")),
              "both blocks carry `dwell`/`pad_hold`/`finger_hold`")
        check((shipped["dwell"], shipped["pad_hold"], shipped["finger_hold"]) == (20, 3, 3),
              "a non-two-line store records the shipped 20/3/3")
        check((trimmed["dwell"], trimmed["pad_hold"], trimmed["finger_hold"]) == (0, 2, 2),
              "a two-line store records the trim 0/2/2")
        check(shipped["origin"] == "scope-off" and trimmed["origin"] == "default",
              "the block names the origin (a pre-P87 manifest has no key at all)")
        check((shipped["ticks"], trimmed["ticks"], trimmed["saved_ticks"]) == (188, 112, 76),
              "the block's clock matches the resolver (188 / 112 / saved 76)")
        check(trimmed["two_line"] is True and shipped["two_line"] is False,
              "the block names its scope")

    # [8] the pin, reported (the shipped selfcheck asserts the equality).
    sys.path.insert(0, str(ROOT / "src"))
    from fruit_sorting.rl_env import TASKS_MD5  # noqa: E402
    import hashlib  # noqa: E402

    actual = hashlib.md5(TASKS.read_bytes()).hexdigest()
    check(TASKS_MD5 == actual, f"TASKS_MD5 follows tasks.py ({TASKS_MD5[:8]})")

    print("=" * 78)
    print("PASS: the release trim is on for a two-line session and inert everywhere else")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
