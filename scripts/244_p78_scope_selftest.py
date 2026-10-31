#!/usr/bin/env python3
"""P78 scoped-finger-force selftest (offline; a selfcheck leg).

Pins the **contained** form of P77's 60 N count win: a runtime finger-drive force
cap that is raised for the left arm's `place*` legs only and restored at each
leg's end (`FRUIT_FINGER_MAXFORCE_SCOPE=place-left`, default off).

Why the form exists at all: P77 measured the win (left placed 11/21 -> 17/20,
Fisher p = 0.043, 3/3 seeds) and the price of the *global* cap - a per-joint
drive property written at build time on both arms of every presentation, so a
flip moves the scripted acceptance at attempt 0 (`fingerprint: DIFFERS`) and the
two-line's fingerprint too, owing both motion references, a scripted re-baseline
and every store's provenance. P77 §2 also measured the class's **site**: every
escape and every pry in both arms is a left `place0` leg.

What this leg checks (no simulator, no file writes):

1. `rl_env.resolve_finger_cap_scope`'s resolution table - non-`direct` is
   `(None, None)` before it looks at any value (the containment), the unset
   path is `(None, None)`, an explicit global `FRUIT_FINGER_MAXFORCE` wins over
   the scope, `place-left` resolves to `{"left": cap}`, and the strict forms
   raise (unknown token, non-number, non-finite, `<= 0`) rather than falling
   back to the shipped cap;
2. `tasks.finger_cap_scope_for`'s scope - the **`place*` leg only**, per side,
   so `grasp_lift` can never be armed (the pick keeps the shipped grip);
3. `PickAndPlaceTask` receives the kwarg and `_carry` is a **wrapper** whose
   body is `_carry_leg`, with the write in a `try` and the restore in a
   `finally` (an exception cannot leave the cap raised);
4. the write is the **live-view** API (`set_dof_max_efforts`), not the USD
   attribute, and the restore target is the cap **read** at the leg's start -
   never a hard-coded 10 N;
5. exactly **one** scoped write site and one place-leg `_carry` call site exist
   (a second one would be an unscoped leg);
6. the build-time global writer is untouched (`scene.apply_finger_maxforce`
   still writes both arms' `joint1` before the articulation exists), so the
   global path keeps its meaning;
7. the manifest field (`scene.finger_physics_provenance(scope=...)`) names the
   site and is absent when the scope is off.

Exit 0 on pass, 1 on the first failure.
"""
from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS: list[str] = []
CHECKS = 0


def check(cond, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(msg)


def load(name: str, path: Path):
    """Import a module object from a path without executing a simulator."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    # ------------------------------------------------------------------ 1
    # the resolvers, as pure functions (no simulator needed: `tasks` and the
    # resolver in `rl_env` are import-light enough for a static read of the
    # *source*, so the arithmetic is checked through `ast` + a tiny exec of the
    # two functions' own source, exactly like the neighbouring legs do).
    scenario = ROOT / "src/fruit_sorting/tasks.py"
    tasks_src = scenario.read_text(encoding="utf-8")

    # `finger_cap_scope_for` is pure (numpy-free), so exec its own source.
    import re

    def grab(src: str, name: str) -> str:
        i = src.index(f"def {name}(")
        j = src.find("\ndef ", i + 5)
        return src[i:j if j > 0 else len(src)]

    ns: dict = {}
    exec(grab(tasks_src, "finger_cap_scope_for"), ns)  # noqa: S102 - pinned source
    scope_for = ns["finger_cap_scope_for"]

    check(scope_for(None, "left", "place0") is None, "no scope -> None")
    check(scope_for({"left": 60.0}, "left", "place0") == 60.0, "left place0 armed")
    check(scope_for({"left": 60.0}, "left", "place1") == 60.0, "left place1 armed")
    check(scope_for({"left": 60.0}, "left", "grasp_lift") is None,
          "grasp_lift is NEVER in scope (the pick keeps the shipped grip)")
    check(scope_for({"left": 60.0}, "right", "place0") is None,
          "the scope is per side - the right arm is never armed")
    check(scope_for({"left": 60.0}, "left", "after_place0") is None,
          "only the leg itself, not a follow-on name")
    check(scope_for({}, "left", "place0") is None, "an empty dict is the off state")

    # ------------------------------------------------------------------ 2
    # the resolution table in `rl_env`, same treatment (it imports `say`/`math`)
    rl_src = (ROOT / "src/fruit_sorting/rl_env.py").read_text(encoding="utf-8")
    env_ns: dict = {"math": __import__("math")}
    env_ns["say"] = lambda *_a, **_k: None
    for name in ("FINGER_CAP_SCOPE_TOKEN", "FINGER_CAP_SCOPE_DEFAULT"):
        m = re.search(rf"^{name} = (.+)$", rl_src, re.M)
        check(m is not None, f"{name} is defined at module level")
        if m:
            env_ns[name] = ast.literal_eval(m.group(1))
    exec(grab(rl_src, "resolve_finger_cap_scope"), env_ns)  # noqa: S102
    resolve = env_ns["resolve_finger_cap_scope"]

    def raises(fn, *a) -> bool:
        try:
            fn(*a)
        except ValueError:
            return True
        except Exception:  # noqa: BLE001
            return False
        return False

    # the containment: no presentation but `direct` resolves, ever
    check(resolve("scripted", "place-left", "60", None) == (None, None),
          "scripted + scope -> (None, None): the scripted line cannot be armed")
    check(resolve("handoff", "place-left", "60", None) == (None, None),
          "handoff -> (None, None)")
    check(resolve("direct", None, None, None) == (None, None), "unset -> off")
    check(resolve("direct", "", "60", None) == (None, None), "empty -> off")
    check(resolve("direct", "place-left", None, None)
          == ({"left": 60.0}, 60.0),
          "the default scoped cap is the P77 60 N rung")
    check(resolve("direct", "place-left", "45", None) == ({"left": 45.0}, 45.0),
          "an explicit scoped cap wins")
    check(resolve("direct", "place-left", "60", "30") == (None, None),
          "an explicit GLOBAL FRUIT_FINGER_MAXFORCE wins over the scope")
    check(resolve("direct", "place-left", "60", "") == ({"left": 60.0}, 60.0),
          "an empty global value is not 'set' (the P43 empty-restore precedent)")
    for bad in ("place-right", "left", "1", "PLACE-LEFT"):
        check(raises(resolve, "direct", bad, "60", None),
              f"unknown scope token {bad!r} raises (a typo must not be a null)")
    for bad in ("sixty", "", "nan", "inf", "0", "-1"):
        if bad == "":
            check(resolve("direct", "place-left", "", None)
                  == ({"left": 60.0}, 60.0), "an empty cap falls back to 60")
            continue
        check(raises(resolve, "direct", "place-left", bad, None),
              f"cap {bad!r} raises")

    # ------------------------------------------------------------------ 3
    # the wrapper: the write is inside `try`, the restore inside `finally`
    tree = ast.parse(tasks_src)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "PickAndPlaceTask")
    funcs = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    check("finger_cap_scope" in [a.arg for a in funcs["__init__"].args.args],
          "PickAndPlaceTask takes the caller-owned `finger_cap_scope` kwarg")
    check("_carry" in funcs and "_carry_leg" in funcs,
          "`_carry` is the wrapper and `_carry_leg` the leg body")
    wrapper = ast.get_source_segment(tasks_src, funcs["_carry"]) or ""
    check("finger_cap_scope_for(self._finger_cap_scope, side, name)" in wrapper,
          "the wrapper resolves the only site function")
    check("try:" in wrapper and "finally:" in wrapper,
          "the leg runs in a try with the restore in a finally")
    check(wrapper.index("try:") < wrapper.rindex("self._carry_leg(")
          < wrapper.index("finally:"),
          "the leg is inside the try (so a raise still restores)")
    check(wrapper.index("finally:") < wrapper.index("_finger_cap_write(side, base)"),
          "the restore write is in the finally")
    check("self._carry_base" not in wrapper and "10.0" not in wrapper,
          "the restore target is the READ cap, never a hard-coded 10 N")
    # the write goes through the live view, and only once
    check(tasks_src.count("set_dof_max_efforts(") == 1,
          "exactly one runtime cap write site")
    check(tasks_src.count("get_dof_max_efforts(") >= 2,
          "the read-back exists (read + write verification)")
    check("arm.robot.set_dof_max_efforts([float(value)], dof_indices=[dof])"
          in tasks_src,
          "the write is the live articulation view, not the USD attribute")
    # the leg-body call sites: exactly one place leg goes through `_carry`
    check(tasks_src.count('self._carry(arm_name, sample, f"place{bin_index}")') == 1,
          "one place-leg dispatch site (a second would be an unscoped leg)")
    check(tasks_src.count("self._carry(arm_name, sample, \"grasp_lift\")") == 1,
          "the lift still dispatches through the wrapper (it resolves to None)")

    # ------------------------------------------------------------------ 4
    # the build-time global writer is untouched in meaning
    scene_src = (ROOT / "src/fruit_sorting/scene.py").read_text(encoding="utf-8")
    check("def apply_finger_maxforce(" in scene_src
          and 'for side in ("left", "right"):' in grab(scene_src, "apply_finger_maxforce"),
          "the global writer still writes BOTH arms at build time")
    prov = grab(scene_src, "finger_physics_provenance")
    check("scope: dict | None = None" in prov, "the provenance builder takes the scope")
    check('block["finger_cap_scope"]' in prov and "if scope:" in prov,
          "the block is written only when armed")

    # ------------------------------------------------------------------ 5
    # the env passes it to the task (one wiring site)
    check(rl_src.count("finger_cap_scope=self._finger_cap_scope") == 1,
          "the env passes the resolved scope to the task exactly once")
    check('os.environ.get("FRUIT_FINGER_MAXFORCE_SCOPE")' in rl_src
          and 'os.environ.get("FRUIT_FINGER_MAXFORCE_SCOPED")' in rl_src,
          "the two env reads are named")
    check(rl_src.count("set_dof_max_efforts") == 0,
          "the env never writes a drive itself (the task owns the leg window)")

    # ------------------------------------------------------------------ report
    if FAILS:
        print(f"P78 selftest FAILED: {len(FAILS)} of {CHECKS} checks")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print(f"P78 selftest OK: {CHECKS} checks (scope resolution table, the place*-leg "
          f"scope, the try/finally wrapper, the live-view write, one site)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
