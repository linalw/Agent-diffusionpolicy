#!/usr/bin/env python3
"""P78/P79 scoped-finger-force selftest (offline; a selfcheck leg).

Pins the **contained** form of P77's 60 N count win: a runtime finger-drive force
cap that is raised for **one carry-leg class of the left arm** and restored at
each leg's end. Two tokens, disjoint by construction:

* `FRUIT_FINGER_MAXFORCE_SCOPE=place-left` (P78) - the left arm's `place*` legs;
* `FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left` (P79) - the left arm's single
  `grasp_lift` leg, i.e. the **pick** half.

Why the form exists at all: P77 measured the win (left placed 11/21 -> 17/20,
Fisher p = 0.043, 3/3 seeds) and the price of the *global* cap - a per-joint
drive property written at build time on both arms of every presentation, so a
flip moves the scripted acceptance at attempt 0 (`fingerprint: DIFFERS`) and the
two-line's fingerprint too, owing both motion references, a scripted re-baseline
and every store's provenance. P77 §2 measured the place class's **site** (every
escape and pry is a left `place0` leg) and left `never-held` 3 -> 0 - a **pick**
class - which is what P79's token isolates.

What this leg checks (no simulator, no file writes):

1. `rl_env.resolve_finger_cap_scope`'s resolution table - non-`direct` is
   `(None, None)` before it looks at any value (the containment), the unset
   path is `(None, None)`, an explicit global `FRUIT_FINGER_MAXFORCE` wins over
   the scope, `place-left` resolves to `{"left:place": cap}`, `grasp-left` to
   `{"left:grasp": cap}`, and the strict forms raise (unknown token,
   non-number, non-finite, `<= 0`) rather than falling back to the shipped cap;
2. `tasks.finger_cap_scope_for`'s scope - **one leg class per key**, so
   `place*` can never be armed by a `grasp` key and `grasp_lift` can never be
   armed by a `place` key (the P78 property and the P79 one, both pinned);
3. the two tokens' classes are disjoint, and the label/legs helpers derive
   their text from the dict's own keys (a row cannot name a token the resolver
   did not resolve);
4. `PickAndPlaceTask` receives the kwarg and `_carry` is a **wrapper** whose
   body is `_carry_leg`, with the write in a `try` and the restore in a
   `finally` (an exception cannot leave the cap raised);
5. the write is the **live-view** API (`set_dof_max_efforts`), not the USD
   attribute, and the restore target is the cap **read** at the leg's start -
   never a hard-coded 10 N;
6. exactly **one** scoped write site, one place-leg dispatch site and one lift
   dispatch site exist (a fourth `_carry` call would be an unscoped leg);
7. the build-time global writer is untouched (`scene.apply_finger_maxforce`
   still writes both arms' `joint1` before the articulation exists), so the
   global path keeps its meaning;
8. the manifest field (`scene.finger_physics_provenance(scope=...)`) names the
   site (`legs` + the exact `sites` keys) and is absent when the scope is off.

Exit 0 on pass, 1 on the first failure.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS: list[str] = []
CHECKS = 0


def check(cond, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(msg)


def grab(src: str, name: str) -> str:
    i = src.index(f"def {name}(")
    j = src.find("\ndef ", i + 5)
    return src[i:j if j > 0 else len(src)]


def main() -> int:
    # ------------------------------------------------------------------ 1
    # `finger_cap_scope_for` is pure (numpy-free), so exec its own source.
    tasks_src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")
    ns: dict = {}
    exec(grab(tasks_src, "finger_cap_scope_for"), ns)  # noqa: S102 - pinned source
    scope_for = ns["finger_cap_scope_for"]

    check(scope_for(None, "left", "place0") is None, "no scope -> None")
    check(scope_for({}, "left", "grasp_lift") is None, "an empty dict is the off state")
    # the P78 class: place* only
    check(scope_for({"left:place": 60.0}, "left", "place0") == 60.0,
          "left:place arms place0")
    check(scope_for({"left:place": 60.0}, "left", "place1") == 60.0,
          "left:place arms place1")
    check(scope_for({"left:place": 60.0}, "left", "grasp_lift") is None,
          "left:place NEVER arms the lift (the pick keeps the shipped grip)")
    # the P79 class: grasp_lift only - and never the place
    check(scope_for({"left:grasp": 60.0}, "left", "grasp_lift") == 60.0,
          "left:grasp arms grasp_lift (the pick half)")
    check(scope_for({"left:grasp": 60.0}, "left", "place0") is None,
          "left:grasp NEVER arms a place leg")
    check(scope_for({"left:grasp": 60.0}, "left", "place1") is None,
          "left:grasp never arms place1 either")
    # per side, and only the leg itself
    check(scope_for({"left:grasp": 60.0}, "right", "grasp_lift") is None,
          "the scope is per side - the right arm is never armed")
    check(scope_for({"left:place": 60.0}, "right", "place0") is None,
          "right place0 stays at the shipped cap")
    check(scope_for({"left:grasp": 60.0}, "left", "after_grasp_lift") is None,
          "only the leg itself, not a follow-on name")
    check(scope_for({"left:place": 60.0}, "left", "after_place0") is None,
          "only the leg itself, not a follow-on place name")
    check(scope_for({"left:grasp": 60.0}, "left", "grasp") is None,
          "the close is not a `_carry` leg, so it is not in scope")
    # a mixed dict arms each class on its own legs and nothing else
    check(scope_for({"left:grasp": 30.0, "left:place": 60.0}, "left", "grasp_lift")
          == 30.0, "a mixed dict arms the lift at its own cap")
    check(scope_for({"left:grasp": 30.0, "left:place": 60.0}, "left", "place0")
          == 60.0, "a mixed dict arms the place at its own cap")
    check(scope_for({"left:grasp": 30.0, "left:place": 60.0}, "left", "grasp_lift")
          != scope_for({"left:grasp": 30.0, "left:place": 60.0}, "left", "place0"),
          "the two classes never share a key")

    # ------------------------------------------------------------------ 2
    # the resolution table in `rl_env` (it imports `math` + `say`)
    rl_src = (ROOT / "src/fruit_sorting/rl_env.py").read_text(encoding="utf-8")
    env_ns: dict = {"math": __import__("math")}
    env_ns["say"] = lambda *_a, **_k: None
    for name in ("FINGER_CAP_SCOPE_DEFAULT", "FINGER_CAP_LEG_TEXT"):
        m = re.search(rf"^{name}(?:: [^=]+)? = (.+)$", rl_src, re.M)
        check(m is not None, f"{name} is defined at module level")
        if m:
            env_ns[name] = ast.literal_eval(m.group(1))
    m = re.search(r"^FINGER_CAP_SCOPE_TOKENS(?:: [^=]+)? = \{(.+?)^\}", rl_src, re.M | re.S)
    check(m is not None, "FINGER_CAP_SCOPE_TOKENS is a module-level literal")
    tokens = ast.literal_eval("{" + (m.group(1) if m else "") + "}")
    env_ns["FINGER_CAP_SCOPE_TOKENS"] = tokens
    for fn in ("finger_cap_scope_label", "finger_cap_scope_legs"):
        exec(grab(rl_src, fn), env_ns)  # noqa: S102 - pinned source
    exec(grab(rl_src, "resolve_finger_cap_scope"), env_ns)  # noqa: S102
    resolve = env_ns["resolve_finger_cap_scope"]
    label = env_ns["finger_cap_scope_label"]
    legs_text = env_ns["finger_cap_scope_legs"]

    check(set(tokens) == {"place-left", "grasp-left"},
          "exactly the two measured tokens exist")
    check(tokens["place-left"] == ("left", "place") and tokens["grasp-left"] == ("left", "grasp"),
          "both tokens are left-arm and their leg classes are the two carry classes")
    check(len({site[1] for site in tokens.values()}) == 2,
          "the tokens' leg classes are disjoint (no token can arm the other's leg)")

    def raises(fn, *a) -> bool:
        try:
            fn(*a)
        except ValueError:
            return True
        except Exception:  # noqa: BLE001
            return False
        return False

    # the containment: no presentation but `direct` resolves, ever
    for token in ("place-left", "grasp-left"):
        check(resolve("scripted", token, "60", None) == (None, None),
              f"scripted + {token} -> (None, None): the scripted line cannot be armed")
        check(resolve("handoff", token, "60", None) == (None, None),
              f"handoff + {token} -> (None, None)")
    check(resolve("direct", None, None, None) == (None, None), "unset -> off")
    check(resolve("direct", "", "60", None) == (None, None), "empty -> off")
    check(resolve("direct", "place-left", None, None)
          == ({"left:place": 60.0}, 60.0),
          "place-left defaults to the P77 60 N rung")
    check(resolve("direct", "grasp-left", None, None)
          == ({"left:grasp": 60.0}, 60.0),
          "grasp-left defaults to the P77 60 N rung")
    check(resolve("direct", "place-left", "45", None) == ({"left:place": 45.0}, 45.0),
          "an explicit scoped cap wins (place)")
    check(resolve("direct", "grasp-left", "30", None) == ({"left:grasp": 30.0}, 30.0),
          "an explicit scoped cap wins (grasp)")
    check(resolve("direct", "grasp-left", "60", "30") == (None, None),
          "an explicit GLOBAL FRUIT_FINGER_MAXFORCE wins over the grasp scope")
    check(resolve("direct", "grasp-left", "60", "") == ({"left:grasp": 60.0}, 60.0),
          "an empty global value is not 'set' (the P43 empty-restore precedent)")
    for bad in ("place-right", "grasp-right", "left", "grasp", "1", "GRASP-LEFT"):
        check(raises(resolve, "direct", bad, "60", None),
              f"unknown scope token {bad!r} raises (a typo must not be a null)")
    for bad in ("sixty", "nan", "inf", "0", "-1"):
        check(raises(resolve, "direct", "grasp-left", bad, None),
              f"cap {bad!r} raises (grasp scope)")
    check(resolve("direct", "grasp-left", "", None) == ({"left:grasp": 60.0}, 60.0),
          "an empty cap falls back to 60 (grasp scope)")

    # the helpers derive their text from the dict itself
    check(label({"left:grasp": 60.0}) == "grasp-left", "the label names the token")
    check(label({"left:place": 60.0}) == "place-left", "the place label is unchanged")
    check(label(None) == "" and label({}) == "", "no scope -> no label")
    check(legs_text({"left:grasp": 60.0}) == "grasp_lift",
          "the grasp scope names `grasp_lift`, not a place leg")
    check(legs_text({"left:place": 60.0}) == "place*",
          "the place scope's text is unchanged")

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
    # the leg-body dispatch sites: one place leg and one lift, both via `_carry`
    check(tasks_src.count('self._carry(arm_name, sample, f"place{bin_index}")') == 1,
          "one place-leg dispatch site (a second would be an unscoped leg)")
    check(tasks_src.count("self._carry(arm_name, sample, \"grasp_lift\")") == 1,
          "one lift dispatch site, through the wrapper (it resolves per class)")
    check(tasks_src.count("self._carry(") == 2,
          "only the two scoped classes ever reach the wrapper")

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
    check('"sites"' in prov and "partition(\":\")" in prov,
          "the manifest block keeps the exact `<side>:<legs>` sites")

    # ------------------------------------------------------------------ 5
    # the env passes it to the task (one wiring site)
    check(rl_src.count("finger_cap_scope=self._finger_cap_scope") == 1,
          "the env passes the resolved scope to the task exactly once")
    check('os.environ.get("FRUIT_FINGER_MAXFORCE_SCOPE")' in rl_src
          and 'os.environ.get("FRUIT_FINGER_MAXFORCE_SCOPED")' in rl_src,
          "the two env reads are named")
    check(rl_src.count("set_dof_max_efforts") == 0,
          "the env never writes a drive itself (the task owns the leg window)")
    check("finger_cap_scope_label(self._finger_cap_scope)" in rl_src,
          "the armed run's row names the token it resolved")

    # ------------------------------------------------------------------ report
    if not FAILS:
        print(f"P78/P79 selftest OK: {CHECKS} checks (the two-token resolution "
              f"table, disjoint leg classes, the try/finally wrapper, the "
              f"live-view write, one site)")
        return 0
    print(f"P78/P79 selftest FAILED: {len(FAILS)} of {CHECKS} checks")
    for f in FAILS:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
