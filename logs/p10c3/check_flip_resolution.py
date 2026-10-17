#!/usr/bin/env python3
"""P10-C.3 stub check: the two-line carry-monitor default flip, offline.

Tier-C-level implementation evidence - NOT a substitute for the pre-registered
Tier-A battery (`logs/p10c2/PREREG_ADOPT_FLIP.md`; the battery starts only
after this implementation is verified, and is a separate lane). Layers:

1. Source checks: the `__init__` knob reads are unchanged (one env read each,
   shipped defaults pinned); `_resolve_carry_monitor_knobs` is defined exactly
   once, is the only other writer of the four attributes, and is called exactly
   once - from `grasp_carry_place`, before the `_grasp_carry_place_impl` call;
   the four resolution statements are `_dynamic_profile` calls with the exact
   (name, shipped, two-line) triples; `_grasp_carry_place_impl` still never
   reads the confirm knob.
2. The resolution truth table (the REAL statements, exec'd): the real
   `_dynamic_profile` method and the four real resolution statements are
   extracted by AST and re-evaluated over the 4 knobs x the session kinds
   (two-line / shared-station / single-arm / direct) x the env states
   (unset / 0 / 1 / 8.0), against an independent reference. The byte-inert
   property is proven by comparison with the real `__init__` read statements:
   per knob, the resolved value equals the init value on every row except
   two-line-unset (the flip), where it equals the pre-registered two-line
   value and differs from the shipped one.
3. The restores, end-to-end: resolution -> the REAL scope predicate
   (`two_line_catch` + `_carry_monitor_active`, extracted from
   `_grasp_carry_place_impl`): the two-line no-env row arms; explicit
   `FRUIT_CARRY_MONITOR_TWOLINE=0` / `FRUIT_CARRY_MONITOR=0` do not;
   `FRUIT_CARRY_MONITOR_CONFIRM_MM=0` keeps the monitor armed at 0.0; the
   shared-station, single-arm and direct scopes resolve exactly as before.
4. The collector manifest field: the shared `write_manifest`'s `collection`
   block gains `carry_monitor` = `os.environ.get("FRUIT_CARRY_MONITOR",
   "auto")` next to `park_early` (the W7-C.1 pattern), evaluated for
   unset / 0 / 1.
5. `rl_env.TASKS_MD5 == md5(tasks.py)`.

Run:  python3 logs/p10c3/check_flip_resolution.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import hashlib
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
COLLECT = ROOT / "scripts" / "40_collect_demos.py"

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def _method(tree: ast.Module, cls: str, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == name:
                    return sub
    raise SystemExit(f"STUB FAIL: {cls}.{name} not found in tasks.py")


#: The four flipped knobs: attr -> (env name, shipped default, two-line value,
#: parse kind). The shipped/two-line strings are the exact `_dynamic_profile`
#: literals the source must carry; the kind picks the value form (`== "1"` vs
#: `float(...)`).
EXPECT = {
    "_carry_monitor": ("FRUIT_CARRY_MONITOR", "0", "1", "bool"),
    "_carry_monitor_twoline": ("FRUIT_CARRY_MONITOR_TWOLINE", "0", "1", "bool"),
    "_carry_monitor_confirm_mm": (
        "FRUIT_CARRY_MONITOR_CONFIRM_MM", "0.0", "8.0", "float"
    ),
    "_carry_monitor_load_floor": (
        "FRUIT_CARRY_MONITOR_LOAD_FLOOR", "0.0", "3.5", "float"
    ),
}
MONITOR_ENVS = tuple(spec[0] for spec in EXPECT.values())


def parse(kind: str, raw: str):
    return raw == "1" if kind == "bool" else float(raw)


class env_guard:
    """Set the four monitor envs for the block; restore exactly afterwards."""

    def __init__(self, overrides: dict):
        self.overrides = overrides
        self.prev: dict = {}

    def __enter__(self):
        for name in MONITOR_ENVS:
            self.prev[name] = os.environ.get(name)
            value = self.overrides.get(name)
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def __exit__(self, *exc):
        for name, value in self.prev.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _assign_count(tree: ast.Module, attr: str) -> int:
    """Assignments whose single target is exactly `self.<attr>` (whole file)."""
    count = 0
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Attribute)
            and node.targets[0].attr == attr
        ):
            count += 1
    return count


def _profile_triple(value: ast.expr):
    """Return (name, shipped, two_line, kind) for a resolution value, else None."""
    kind = "bool"
    inner = value
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "float"
        and len(value.args) == 1
    ):
        kind = "float"
        inner = value.args[0]
    else:
        if not (
            isinstance(inner, ast.Compare)
            and len(inner.ops) == 1
            and isinstance(inner.ops[0], ast.Eq)
            and len(inner.comparators) == 1
            and isinstance(inner.comparators[0], ast.Constant)
            and inner.comparators[0].value == "1"
        ):
            return None
        inner = inner.left
    if not (
        isinstance(inner, ast.Call)
        and isinstance(inner.func, ast.Attribute)
        and inner.func.attr == "_dynamic_profile"
        and len(inner.args) == 3
    ):
        return None
    args = []
    for arg in inner.args:
        if not isinstance(arg, ast.Constant):
            return None
        args.append(arg.value)
    return (*args, kind)


def main() -> int:
    source = TASKS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    init = _method(tree, "PickAndPlaceTask", "__init__")
    impl = _method(tree, "PickAndPlaceTask", "_grasp_carry_place_impl")
    wrapper = _method(tree, "PickAndPlaceTask", "grasp_carry_place")
    helper = _method(tree, "PickAndPlaceTask", "_resolve_carry_monitor_knobs")

    # ---- 1. source checks ----------------------------------------------------
    print("== 1. source checks ==")
    check(
        "the four `__init__` reads are unchanged (one env read each, shipped "
        "defaults pinned)",
        source.count('os.environ.get("FRUIT_CARRY_MONITOR"') == 1
        and 'os.environ.get("FRUIT_CARRY_MONITOR", "0")' in source
        and source.count('os.environ.get("FRUIT_CARRY_MONITOR_TWOLINE"') == 1
        and 'os.environ.get("FRUIT_CARRY_MONITOR_TWOLINE", "0")' in source
        and source.count('os.environ.get("FRUIT_CARRY_MONITOR_CONFIRM_MM"') == 1
        and 'os.environ.get("FRUIT_CARRY_MONITOR_CONFIRM_MM", "0.0")' in source
        and source.count('os.environ.get("FRUIT_CARRY_MONITOR_LOAD_FLOOR"') == 1
        and 'os.environ.get("FRUIT_CARRY_MONITOR_LOAD_FLOOR", "0.0")' in source,
    )
    check(
        "`_resolve_carry_monitor_knobs` is defined exactly once and called "
        "exactly once in the file",
        sum(
            1 for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "_resolve_carry_monitor_knobs"
        ) == 1
        and source.count("self._resolve_carry_monitor_knobs()") == 1,
    )
    check(
        "each of the four knob attributes is assigned exactly twice in the "
        "file (the `__init__` base read + the resolution helper - no other "
        "writer)",
        all(_assign_count(tree, attr) == 2 for attr in EXPECT),
    )
    # The wrapper call site: the resolution runs before the primitive call.
    res_idx = impl_idx = None
    for i, st in enumerate(wrapper.body):
        for node in ast.walk(st):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_resolve_carry_monitor_knobs"
            ):
                res_idx = i if res_idx is None else min(res_idx, i)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_grasp_carry_place_impl"
            ):
                impl_idx = i if impl_idx is None else min(impl_idx, i)
    check(
        "the resolution is called from `grasp_carry_place` before the "
        "`_grasp_carry_place_impl` call",
        res_idx is not None and impl_idx is not None and res_idx < impl_idx,
    )
    # The four real resolution statements, in source order.
    res_stmts = [
        st for st in helper.body
        if isinstance(st, ast.Assign)
        and len(st.targets) == 1
        and isinstance(st.targets[0], ast.Attribute)
        and st.targets[0].attr in EXPECT
    ]
    check(
        "the helper holds exactly the four resolution statements (AST)",
        len(res_stmts) == 4
        and {st.targets[0].attr for st in res_stmts} == set(EXPECT),
    )
    shape_bad = []
    for st in res_stmts:
        attr = st.targets[0].attr
        got = _profile_triple(st.value)
        if got != EXPECT[attr]:
            shape_bad.append(f"{attr}: {ast.unparse(st.value)} -> {got}")
    check(
        "each statement is `self._dynamic_profile(<name>, <shipped>, "
        "<two-line>)` with the pre-registered triple (float() on the numeric "
        "knobs, `== \"1\"` on the booleans)",
        not shape_bad and len(res_stmts) == 4,
    )
    check(
        "the helper resolves exactly four `_dynamic_profile` calls (the diag "
        "knob is not part of the flip)",
        sum(
            1 for n in ast.walk(helper)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "_dynamic_profile"
        ) == 4,
    )
    check(
        "the pre-existing monitor checks are unchanged: the diag read is "
        "env-only (one read, default \"0\") and the impl never reads the "
        "confirm knob",
        source.count('os.environ.get("FRUIT_CARRY_MONITOR_DIAG"') == 1
        and 'os.environ.get("FRUIT_CARRY_MONITOR_DIAG", "0")' in source
        and "_carry_monitor_confirm_mm" not in ast.unparse(impl),
    )

    # ---- 2. the resolution truth table (real statements, exec'd) -------------
    print("== 2. resolution truth table (real statements, exec'd) ==")
    dp_fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_dynamic_profile"
    )
    dp_ns: dict = {"os": os}
    exec(compile(ast.Module(body=[dp_fn], type_ignores=[]), str(TASKS), "exec"), dp_ns)
    dynamic_profile = dp_ns["_dynamic_profile"]

    init_stmts = [
        st for st in init.body
        if isinstance(st, ast.Assign)
        and len(st.targets) == 1
        and isinstance(st.targets[0], ast.Attribute)
        and st.targets[0].attr in EXPECT
    ]
    check(
        "the four `__init__` base reads are extracted for the byte-inert "
        "comparison",
        len(init_stmts) == 4
        and {st.targets[0].attr for st in init_stmts} == set(EXPECT),
    )

    class _Self:
        pass

    def resolved(session, overrides: dict) -> dict:
        """Run the REAL resolution statements under an env/session state."""
        fake = _Self()
        fake._active_session = session
        fake._dynamic_profile = dynamic_profile.__get__(fake)
        with env_guard(overrides):
            exec(
                compile(ast.Module(body=res_stmts, type_ignores=[]), str(TASKS), "exec"),
                {"self": fake},
            )
        return {attr: getattr(fake, attr) for attr in EXPECT}

    def init_values(overrides: dict) -> dict:
        """Run the REAL `__init__` read statements under the same env state."""
        fake = _Self()
        with env_guard(overrides):
            exec(
                compile(ast.Module(body=init_stmts, type_ignores=[]), str(TASKS), "exec"),
                {"self": fake, "os": os},
            )
        return {attr: getattr(fake, attr) for attr in EXPECT}

    class _Session:
        def __init__(self, twoline):
            self.twoline = twoline

    SESSIONS = (
        ("two-line", _Session(True)),
        ("shared-station", _Session(False)),
        ("single-arm", None),
        ("direct", None),
    )

    def reference(session, overrides: dict) -> dict:
        """Independent reference: env wins; else the two-line value in a
        two-line session; else the shipped default."""
        out = {}
        for attr, (name, shipped, two_line, kind) in EXPECT.items():
            raw = overrides.get(name)
            if raw is None:
                twoline = session is not None and getattr(session, "twoline", False)
                raw = two_line if twoline else shipped
            out[attr] = parse(kind, raw)
        return out

    STATES = (None, "0", "1", "8.0")
    rows = bad = inert_bad = flip_rows = flip_bad = 0
    for skey, session in SESSIONS:
        for knob, (name, _shipped, _two_line, _kind) in EXPECT.items():
            for state in STATES:
                overrides = {} if state is None else {name: state}
                got = resolved(session, overrides)
                want = reference(session, overrides)
                base = init_values(overrides)
                rows += 1
                if got != want:
                    bad += 1
                    failures.append(
                        f"resolution mismatch: session={skey} knob={name} "
                        f"env={state!r}: live={got} reference={want}"
                    )
                for attr, (name2, shipped2, two_line2, kind2) in EXPECT.items():
                    if skey == "two-line" and name2 not in overrides:
                        # The flip row: the two-line value, not the shipped one.
                        flip_rows += 1
                        want_flip = parse(kind2, two_line2)
                        if got[attr] != want_flip or got[attr] == parse(kind2, shipped2):
                            flip_bad += 1
                            failures.append(
                                f"flip row not flipped: {skey}/{name2} "
                                f"(under {name}={state!r}): {got[attr]!r}"
                            )
                    elif got[attr] != base[attr]:
                        # Byte-inert: every other row equals the init read.
                        inert_bad += 1
                        failures.append(
                            f"not byte-inert: session={skey} knob={name} "
                            f"env={state!r} attr={attr}: resolved={got[attr]!r} "
                            f"init={base[attr]!r}"
                        )
    check(
        f"full sweep ({rows} rows: 4 sessions x 4 knobs x the unset/0/1/8.0 "
        "states) vs the independent reference",
        bad == 0,
    )
    check(
        f"every flip row ({flip_rows}) reads the pre-registered two-line value "
        "and differs from the shipped one",
        flip_bad == 0,
    )
    check(
        "every non-flip row is byte-inert vs the real `__init__` reads",
        inert_bad == 0,
    )
    extended_bad = 0
    for skey, session in SESSIONS:
        for knob, (name, _s, _t, kind) in EXPECT.items():
            states = (
                ("3.5", "-1", "true", "0.5", "auto")
                if kind == "bool"
                else ("3.5", "-1", "0.5", "1")
            )
            for state in states:
                overrides = {name: state}
                if resolved(session, overrides) != reference(session, overrides):
                    extended_bad += 1
                    failures.append(
                        f"extended grid mismatch: {skey}/{name}={state!r}"
                    )
    check("extended env grid (bool: 3.5 / -1 / true / 0.5 / auto; float: "
          "3.5 / -1 / 0.5 / 1) vs the reference", extended_bad == 0)

    # ---- 3. the restores, end-to-end (resolution -> the real predicate) ------
    print("== 3. restores, end-to-end (resolution -> the real scope predicate) ==")
    two_line_stmts = [
        st for st in impl.body
        if isinstance(st, ast.Assign)
        and len(st.targets) == 1
        and isinstance(st.targets[0], ast.Name)
        and st.targets[0].id == "two_line_catch"
    ]
    active_stmts = [
        st for st in impl.body
        if isinstance(st, ast.Assign)
        and len(st.targets) == 1
        and isinstance(st.targets[0], ast.Attribute)
        and st.targets[0].attr == "_carry_monitor_active"
    ]
    check(
        "the real scope statements are still the single `two_line_catch` + "
        "`_carry_monitor_active` pair",
        len(two_line_stmts) == 1 and len(active_stmts) == 1,
    )
    if len(two_line_stmts) != 1 or len(active_stmts) != 1:
        print("cannot continue without the scope statements")
        return 1
    scope_body = [two_line_stmts[0], active_stmts[0]]

    def armed(session, overrides, scripted, dynamic_capture, direct_capture):
        vals = resolved(session, overrides)
        fake = _Self()
        fake._carry_monitor = vals["_carry_monitor"]
        fake._carry_monitor_twoline = vals["_carry_monitor_twoline"]
        fake._active_session = session
        fake._carry_monitor_active = None
        ns = {
            "self": fake,
            "scripted": bool(scripted),
            "dynamic_capture": bool(dynamic_capture),
            "direct_capture": bool(direct_capture),
        }
        exec(
            compile(ast.Module(body=scope_body, type_ignores=[]), str(TASKS), "exec"),
            ns,
        )
        return bool(fake._carry_monitor_active), vals

    TL = SESSIONS[0][1]
    SH = SESSIONS[1][1]
    named = [
        ("THE FLIP: two-line, no relevant env, scripted dynamic catch",
         TL, {}, True, True, False, True,
         {"_carry_monitor": True, "_carry_monitor_twoline": True,
          "_carry_monitor_confirm_mm": 8.0, "_carry_monitor_load_floor": 3.5}),
        ("restore: FRUIT_CARRY_MONITOR_TWOLINE=0 (pre-flip: no monitor)",
         TL, {"FRUIT_CARRY_MONITOR_TWOLINE": "0"}, True, True, False, False,
         {"_carry_monitor_twoline": False}),
        ("restore: FRUIT_CARRY_MONITOR=0 (the master wins)",
         TL, {"FRUIT_CARRY_MONITOR": "0"}, True, True, False, False,
         {"_carry_monitor": False}),
        ("restore: FRUIT_CARRY_MONITOR_CONFIRM_MM=0 (the ungated monitor)",
         TL, {"FRUIT_CARRY_MONITOR_CONFIRM_MM": "0"}, True, True, False, True,
         {"_carry_monitor_confirm_mm": 0.0, "_carry_monitor": True,
          "_carry_monitor_twoline": True}),
        ("two-line, no env, indexed catch (dynamic_capture off) never arms",
         TL, {}, True, False, False, False,
         {"_carry_monitor": True}),
        ("shared-station bimanual, no env: untouched (shipped values)",
         SH, {}, True, True, False, False,
         {"_carry_monitor": False, "_carry_monitor_twoline": False,
          "_carry_monitor_confirm_mm": 0.0, "_carry_monitor_load_floor": 0.0}),
        ("single-arm scripted line, no env: untouched (shipped values)",
         None, {}, True, True, False, False,
         {"_carry_monitor": False, "_carry_monitor_twoline": False,
          "_carry_monitor_confirm_mm": 0.0, "_carry_monitor_load_floor": 0.0}),
        ("direct/policy handover, no env: untouched (shipped values)",
         None, {}, False, True, True, False,
         {"_carry_monitor": False, "_carry_monitor_confirm_mm": 0.0}),
        ("direct/policy handover, FRUIT_CARRY_MONITOR=1: unchanged",
         None, {"FRUIT_CARRY_MONITOR": "1"}, False, True, True, True,
         {"_carry_monitor": True, "_carry_monitor_twoline": False,
          "_carry_monitor_confirm_mm": 0.0, "_carry_monitor_load_floor": 0.0}),
        ("direct/policy handover, monitor + gate: unchanged",
         None, {"FRUIT_CARRY_MONITOR": "1", "FRUIT_CARRY_MONITOR_CONFIRM_MM": "8.0"},
         False, True, True, True, {"_carry_monitor_confirm_mm": 8.0}),
        ("single-arm scripted line, FRUIT_CARRY_MONITOR=1: never arms",
         None, {"FRUIT_CARRY_MONITOR": "1"}, True, True, False, False,
         {"_carry_monitor": True}),
        ("two-line, explicit scope knob =1: same as the flip (env wins)",
         TL, {"FRUIT_CARRY_MONITOR_TWOLINE": "1"}, True, True, False, True,
         {"_carry_monitor_twoline": True}),
        ("two-line, explicit floor =0: explicit wins, monitor still armed",
         TL, {"FRUIT_CARRY_MONITOR_LOAD_FLOOR": "0"}, True, True, False, True,
         {"_carry_monitor_load_floor": 0.0, "_carry_monitor": True}),
        ("two-line, no env, direct_capture=True: the direct scope is unchanged",
         TL, {}, False, True, True, True,
         {"_carry_monitor": True}),
    ]
    for label, session, overrides, scripted, dynamic, direct, want_active, subset in named:
        got_active, vals = armed(session, overrides, scripted, dynamic, direct)
        ok = got_active == want_active and all(
            vals[attr] == value for attr, value in subset.items()
        )
        detail = "" if ok else f" (active={got_active}, vals={vals})"
        check(f"{label}: active={got_active} (expected {want_active}){detail}", ok)

    # ---- 4. the collector manifest field -------------------------------------
    print("== 4. collector manifest field (`collection.carry_monitor`) ==")
    ctree = ast.parse(COLLECT.read_text(encoding="utf-8"))
    writers = [
        n for n in ast.walk(ctree)
        if isinstance(n, ast.FunctionDef) and n.name == "write_manifest"
    ]
    check("exactly one `write_manifest` (the shared collector writer)",
          len(writers) == 1)
    coll = None
    if len(writers) == 1:
        for node in ast.walk(writers[0]):
            if isinstance(node, ast.Dict):
                keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
                if "park_early" in keys and "carry_monitor" in keys:
                    coll = node
                    break
    check(
        "one `collection` block carries both `park_early` and `carry_monitor` "
        "(the W7-C.1 pattern; shared by both collector modes)",
        coll is not None,
    )
    if coll is not None:
        entries = {
            k.value: v for k, v in zip(coll.keys, coll.values)
            if isinstance(k, ast.Constant)
        }
        check("`collection.mode` sits in the same shared block",
              "mode" in entries)
        expr = entries["carry_monitor"]
        check(
            "`collection.carry_monitor` is structurally "
            "`os.environ.get(\"FRUIT_CARRY_MONITOR\", \"auto\")`",
            isinstance(expr, ast.Call)
            and isinstance(expr.func, ast.Attribute)
            and isinstance(expr.func.value, ast.Attribute)
            and isinstance(expr.func.value.value, ast.Name)
            and expr.func.value.value.id == "os"
            and expr.func.value.attr == "environ"
            and expr.func.attr == "get"
            and [a.value for a in expr.args if isinstance(a, ast.Constant)]
            == ["FRUIT_CARRY_MONITOR", "auto"],
        )

        def manifest_value(state):
            with env_guard({"FRUIT_CARRY_MONITOR": state}):
                return eval(
                    compile(ast.Expression(body=expr), str(COLLECT), "eval"),
                    {"os": os},
                )

        check('manifest field, env unset -> "auto" (the flip)',
              manifest_value(None) == "auto")
        check('manifest field, env =0 -> "0" (explicit override)',
              manifest_value("0") == "0")
        check('manifest field, env =1 -> "1" (explicit override)',
              manifest_value("1") == "1")
        check(
            'the sibling `park_early` keeps the same convention',
            ast.unparse(entries["park_early"])
            == ast.unparse(expr).replace("FRUIT_CARRY_MONITOR", "FRUIT_BIARM_PARK_EARLY"),
        )

    # ---- 5. rl_env pin -------------------------------------------------------
    print("== 5. rl_env pin ==")
    digest = hashlib.md5(TASKS.read_bytes()).hexdigest()
    pin = None
    for line in RL_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("TASKS_MD5"):
            pin = line.split('"')[1]
    check(f"rl_env TASKS_MD5 == live tasks.py md5 ({digest})", pin == digest)

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s) failed)")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(
        "RESULT: PASS (the four knob reads are unchanged; the real resolution "
        "statements read the pre-registered two-line values in a two-line "
        "session with the env unset and the env/shipped values everywhere "
        "else; the explicit restores resolve exactly; the real scope "
        "predicate arms the two-line flip and nothing else; the collector "
        "manifest carries `collection.carry_monitor` = auto/0/1; the pin "
        "matches)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
