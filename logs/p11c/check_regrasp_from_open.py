#!/usr/bin/env python3
"""P11-C stub check: the re-seat arrival geometry (`FRUIT_DYNAMIC_REGRASP_FROM_OPEN`), offline.

Tier-C-level implementation evidence - NOT a substitute for the pre-registered
Tier-A battery (`logs/p11c/PREREG_REGRASP_ARRIVAL.md`; the battery is a
separate lane). Layers:

1. Source checks: the knob is resolved exactly once through
   `self._dynamic_profile("FRUIT_DYNAMIC_REGRASP_FROM_OPEN", "0", "0") == "1"`
   (default 0 = shipped; the W1-profile resolution channel, so a future
   adoption flip is one literal and an explicit env value always wins); the
   pre-existing W1 profile triples are unchanged; the keep branch keeps the
   shipped `keep_gap` expression, the shared 40-tick descent loop (whose gap
   argument is the new `descent_gap`, the rest of the shipped statement
   sequence byte-for-byte), the `_force_servo_reset`, and the say row; the
   non-keep regrasp branch and the ratchet are unchanged.
2. The resolution truth table (the REAL statements, exec'd): the real
   `_dynamic_profile` method and the real `regrasp_from_open` assignment are
   extracted by AST and re-evaluated over the sessions (two-line /
   shared-station / single-arm) x the env states (unset / 0 / 1 / true /
   auto), against an independent reference. Byte-inert: with the env unset
   the knob resolves False on every session (the shipped branch is taken).
3. The approach branch (the REAL statements, exec'd end-to-end): the real
   `gap_open` read, the `keep_gap` expression, the `descent_gap` assignment,
   the shared descent loop and the `if regrasp_from_open:` close block are
   re-evaluated against fakes that record every `follow_centre` gap.
   - knob off: the sequence is `[keep_gap] * 40` (the shipped
     descend-at-the-chased-gap; the close block is skipped), and the say row
     is the byte-identical shipped string;
   - knob on: `[gap_open] * 40` then the two-phase ramp from `gap_open`
     through `wide` to `keep_gap` (the same re-seat depth), monotone
     non-increasing, first tick still ~`gap_open` - the open-gap descent +
     horizontal close the P11-B probe measured as ejection-free (vs the
     shipped `plow` geometry: the descent gap below the fruit's extent);
   - the geometry invariant: `gap_open` (0.09) is wider than the measured
     blocking span (the pool's largest nominal extent 0.070 + the probe's
     measured link-span offset 0.0113);
   - the say row with the knob on gains exactly the ` [from-open]` suffix.
4. `rl_env.TASKS_MD5 == md5(tasks.py)`.

Run:  python3 logs/p11c/check_regrasp_from_open.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import hashlib
import os
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
MOTION = ROOT / "src" / "fruit_sorting" / "motion.py"

#: The pre-registered `_dynamic_profile` triple of the new knob: default 0 =
#: the shipped form on both paths (the battery sets `=1` explicitly).
KNOB = ("FRUIT_DYNAMIC_REGRASP_FROM_OPEN", "0", "0")

#: The probe's measured stop for this hand + fruit (P11-B section 1): the
#: pads stop at `extent + ~11 mm` of link span (tomato 51.0 -> 62.3 mm,
#: apple 64.5 -> 75.6 mm). The pool's largest nominal extent is 0.070 m
#: (apple/orange/peach/pear draws, `assets.py:400-417`).
BLOCKING_OFFSET = 0.0113
MAX_POOL_EXTENT = 0.070

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


def _exec_stmts(stmts: list, ns: dict, filename: str) -> None:
    exec(compile(ast.Module(body=stmts, type_ignores=[]), filename, "exec"), ns)


def _profile_triple(value: ast.expr):
    """Return (name, shipped, two_line, kind) for a `_dynamic_profile` read, else None."""
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


def _profile_calls(tree: ast.Module, name: str) -> list[tuple]:
    """The (shipped, two-line) triples of every `_dynamic_profile(<name>, ...)` call."""
    out = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_dynamic_profile"
            and len(node.args) == 3
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == name
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[2], ast.Constant)
        ):
            out.append((node.args[1].value, node.args[2].value))
    return out


def main() -> int:
    source = TASKS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    impl = _method(tree, "PickAndPlaceTask", "_grasp_carry_place_impl")

    # ---- 1. source checks ----------------------------------------------------
    print("== 1. source checks ==")
    check(
        'the knob env name is written exactly once, in the `_dynamic_profile` '
        'triple with the shipped/two-line defaults "0"/"0"',
        source.count('"FRUIT_DYNAMIC_REGRASP_FROM_OPEN"') == 1
        and 'self._dynamic_profile("FRUIT_DYNAMIC_REGRASP_FROM_OPEN", "0", "0")'
        ' == "1"' in source,
    )
    res_stmts = [
        st for st in impl.body
        if isinstance(st, ast.Assign)
        and len(st.targets) == 1
        and isinstance(st.targets[0], ast.Name)
        and st.targets[0].id == "regrasp_from_open"
    ]
    check(
        "one `regrasp_from_open = ...` resolution statement in "
        "`_grasp_carry_place_impl` (AST)",
        len(res_stmts) == 1,
    )
    triple = _profile_triple(res_stmts[0].value) if len(res_stmts) == 1 else None
    check(
        "the resolution is exactly the pre-registered triple "
        f"{KNOB} with the `== \"1\"` parse",
        triple == (*KNOB, "bool"),
    )
    check(
        "the pre-existing W1 profile triples are unchanged (one "
        "`_dynamic_profile` call each, exact triples)",
        _profile_calls(tree, "FRUIT_DYNAMIC_REGRASP_KEEP") == [("0", "1")]
        and _profile_calls(tree, "FRUIT_DYNAMIC_PROBE_TICKS") == [("40", "60")]
        and _profile_calls(tree, "FRUIT_DYNAMIC_PROBE") == [("0.010", "0.006")]
        and _profile_calls(tree, "FRUIT_DYNAMIC_TEST_STEP") == [("0.02", "0.01")],
    )
    check(
        "the knob name is consumed exactly in the four expected places "
        "(resolution target, descent ternary, close guard, say suffix)",
        sum(
            1 for n in ast.walk(impl)
            if isinstance(n, ast.Name) and n.id == "regrasp_from_open"
        ) == 4,
    )

    # The keep branch (the two-line W1 re-seat).
    keep_ifs = [
        n for n in ast.walk(impl)
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Name)
        and n.test.id == "regrasp_keep"
    ]
    check("one `if regrasp_keep:` branch in `_grasp_carry_place_impl`",
          len(keep_ifs) == 1)
    if len(keep_ifs) != 1:
        print("cannot continue without the keep branch")
        return 1
    keep_body = keep_ifs[0].body

    keep_stmts = [
        st for st in keep_body
        if isinstance(st, ast.Assign)
        and isinstance(st.targets[0], ast.Name)
        and st.targets[0].id == "keep_gap"
    ]
    check(
        "the keep branch keeps the shipped `keep_gap` expression "
        "(squeeze_gap if not None else grip_gap)",
        len(keep_stmts) == 1
        and ast.unparse(keep_stmts[0].value)
        == "float(squeeze_gap) if squeeze_gap is not None else float(grip_gap)",
    )
    descent_stmts = [
        st for st in keep_body
        if isinstance(st, ast.Assign)
        and isinstance(st.targets[0], ast.Name)
        and st.targets[0].id == "descent_gap"
    ]
    check(
        "one `descent_gap` assignment: `float(gap_open)` under the knob, "
        "`keep_gap` otherwise",
        len(descent_stmts) == 1
        and ast.unparse(descent_stmts[0].value)
        == "float(gap_open) if regrasp_from_open else keep_gap",
    )
    desc_loops = [
        st for st in keep_body
        if isinstance(st, ast.For)
        and isinstance(st.iter, ast.Call)
        and isinstance(st.iter.func, ast.Name)
        and st.iter.func.id == "range"
        and len(st.iter.args) == 1
        and isinstance(st.iter.args[0], ast.Constant)
        and st.iter.args[0].value == 40
    ]
    check("the shared 40-tick descent loop is present exactly once",
          len(desc_loops) == 1)
    if len(desc_loops) != 1:
        print("cannot continue without the descent loop")
        return 1
    desc_body = desc_loops[0].body
    shapes = []
    for st in desc_body:
        if isinstance(st, ast.Assign) and isinstance(st.targets[0], ast.Name):
            shapes.append(f"assign:{st.targets[0].id}")
        elif isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
            func = st.value.func
            shapes.append(
                "call:" + (func.attr if isinstance(func, ast.Attribute) else "?")
            )
    check(
        "the descent loop's statement sequence is the shipped one "
        "(fruit_now, fruit_v_now, ik_step, follow_centre, _step_sim)",
        shapes == [
            "assign:fruit_now",
            "assign:fruit_v_now",
            "call:ik_step",
            "call:follow_centre",
            "call:_step_sim",
        ],
    )
    desc_ik = desc_body[2].value.args[0]
    check(
        "the descent loop's ik_step target is the shipped fruit-tracking "
        "expression (unchanged)",
        ast.unparse(desc_ik)
        == "arm.tcp_target_for_jaw(fruit_now + np.array([0.0, 0.0, "
        "self._pad_standoff(True, sample)]) + np.array([0.0, "
        "float(fruit_v_now[1]) * dynamic_lead_s, 0.0]))",
    )
    desc_fc = [
        n for n in ast.walk(desc_loops[0])
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "follow_centre"
    ]
    check(
        "the descent loop's `follow_centre` holds the new `descent_gap` "
        "(the only shipped-path change; equal to `keep_gap` when the knob is off)",
        len(desc_fc) == 1
        and isinstance(desc_fc[0].args[2], ast.Name)
        and desc_fc[0].args[2].id == "descent_gap",
    )

    close_ifs = [
        st for st in keep_body
        if isinstance(st, ast.If)
        and isinstance(st.test, ast.Name)
        and st.test.id == "regrasp_from_open"
    ]
    check("one `if regrasp_from_open:` close block in the keep branch",
          len(close_ifs) == 1)
    if len(close_ifs) != 1:
        print("cannot continue without the close block")
        return 1
    ramp_stmts = [
        st for st in ast.walk(close_ifs[0])
        if isinstance(st, ast.Assign)
        and isinstance(st.targets[0], ast.Name)
        and st.targets[0].id == "reseat_close"
    ]
    check(
        "the close block builds `reseat_close` as the initial close's "
        "two-phase shape: np.concatenate([min_jerk_ramp(gap_open, wide, "
        "fast_ticks), min_jerk_ramp(wide, keep_gap, load_ticks)])",
        len(ramp_stmts) == 1
        and ast.unparse(ramp_stmts[0].value)
        == "np.concatenate([min_jerk_ramp(gap_open, wide, fast_ticks), "
        "min_jerk_ramp(wide, keep_gap, load_ticks)])",
    )
    close_loops = [
        st for st in ast.walk(close_ifs[0])
        if isinstance(st, ast.For)
        and isinstance(st.target, ast.Name)
        and st.target.id == "gap"
    ]
    check("the close block replays the ramp once (`for gap in reseat_close`)",
          len(close_loops) == 1)
    if len(close_loops) == 1:
        close_ik = [
            st for st in close_loops[0].body
            if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call)
            and isinstance(st.value.func, ast.Attribute)
            and st.value.func.attr == "ik_step"
        ]
        close_fc = [
            n for n in ast.walk(close_loops[0])
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "follow_centre"
        ]
        check(
            "the close loop tracks with the same ik_step expression as the "
            "descent and closes through `follow_centre(..., float(gap))`",
            len(close_ik) == 1
            and ast.unparse(close_ik[0].value.args[0]) == ast.unparse(desc_ik)
            and len(close_fc) == 1
            and ast.unparse(close_fc[0].args[2]) == "float(gap)",
        )
    resets = [
        st for st in keep_body
        if isinstance(st, ast.Expr)
        and isinstance(st.value, ast.Call)
        and isinstance(st.value.func, ast.Attribute)
        and st.value.func.attr == "_force_servo_reset"
    ]
    check(
        "the `_force_servo_reset(arm_name)` still follows the arrival block",
        len(resets) == 1 and keep_body.index(resets[0]) > keep_body.index(close_ifs[0]),
    )
    check(
        "the non-keep regrasp branch is unchanged (the 45-tick close to grip_gap)",
        source.count("min_jerk_ramp(gap_open, grip_gap, 45)") == 1,
    )
    check(
        "the ratchet is unchanged (`FRUIT_DYNAMIC_REGRASP_STEP`, one read)",
        source.count('os.environ.get("FRUIT_DYNAMIC_REGRASP_STEP"') == 1
        and 'os.environ.get("FRUIT_DYNAMIC_REGRASP_STEP", "0.0015")' in source,
    )
    check(
        "the close-shape variables (`wide`/`fast_ticks`/`load_ticks`) are "
        "defined earlier in the same function, under the same "
        "`dynamic_capture` local the re-seat guard reads",
        source.count("dynamic_capture = bool(") == 1
        and source.count("self._dynamic_capture_active = dynamic_capture") == 1
        and min(
            n.lineno for n in ast.walk(impl)
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "wide"
        ) < close_ifs[0].lineno,
    )

    # ---- 2. the resolution truth table (real statements, exec'd) -------------
    print("== 2. resolution truth table (real statements, exec'd) ==")
    dp_fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_dynamic_profile"
    )
    dp_ns: dict = {"os": os}
    _exec_stmts([dp_fn], dp_ns, str(TASKS))
    dynamic_profile = dp_ns["_dynamic_profile"]

    class _Self:
        pass

    class _Session:
        def __init__(self, twoline):
            self.twoline = twoline

    SESSIONS = (
        ("two-line", _Session(True)),
        ("shared-station", _Session(False)),
        ("single-arm", None),
    )

    def resolved(session, env_state):
        fake = _Self()
        fake._active_session = session
        fake._dynamic_profile = dynamic_profile.__get__(fake)
        prev = os.environ.get(KNOB[0])
        if env_state is None:
            os.environ.pop(KNOB[0], None)
        else:
            os.environ[KNOB[0]] = env_state
        try:
            ns = {"self": fake}
            _exec_stmts([res_stmts[0]], ns, str(TASKS))
        finally:
            if prev is None:
                os.environ.pop(KNOB[0], None)
            else:
                os.environ[KNOB[0]] = prev
        return bool(ns["regrasp_from_open"])

    def reference(session, env_state):
        """Independent reference: env wins; else the two-line value in a
        two-line session; else the shipped default."""
        if env_state is not None:
            raw = env_state
        else:
            twoline = session is not None and getattr(session, "twoline", False)
            raw = KNOB[2] if twoline else KNOB[1]
        return raw == "1"

    STATES = (None, "0", "1", "true", "TRUE", "auto")
    rows = bad = 0
    for skey, session in SESSIONS:
        for state in STATES:
            rows += 1
            got, want = resolved(session, state), reference(session, state)
            if got != want:
                bad += 1
                failures.append(
                    f"resolution mismatch: session={skey} env={state!r}: "
                    f"live={got} reference={want}"
                )
    check(f"full sweep ({rows} rows) vs the independent reference", bad == 0)
    check(
        "knob-off rows (env unset) resolve False on every session "
        "(the shipped branch is taken; byte-inert)",
        all(resolved(session, None) is False for _, session in SESSIONS),
    )
    check(
        'named: two-line unset -> False; env "1" -> True on every session; '
        '"true" -> False (the parse is `== "1"`)',
        resolved(SESSIONS[0][1], None) is False
        and all(resolved(s, "1") is True for _, s in SESSIONS)
        and all(resolved(s, "true") is False for _, s in SESSIONS),
    )

    # ---- 3. the approach branch (real statements, exec'd end-to-end) ---------
    print("== 3. the approach branch (real statements, exec'd) ==")
    mtree = ast.parse(MOTION.read_text(encoding="utf-8"))
    ramp_fn = next(
        n for n in ast.walk(mtree)
        if isinstance(n, ast.FunctionDef) and n.name == "min_jerk_ramp"
    )
    ramp_ns: dict = {"np": np}
    _exec_stmts([ramp_fn], ramp_ns, str(MOTION))
    min_jerk_ramp = ramp_ns["min_jerk_ramp"]

    gap_stmts = [
        st for st in ast.walk(impl)
        if isinstance(st, ast.Assign)
        and len(st.targets) == 1
        and isinstance(st.targets[0], ast.Name)
        and st.targets[0].id == "gap_open"
        and isinstance(st.value, ast.Call)
        and isinstance(st.value.func, ast.Name)
        and st.value.func.id == "float"
    ]
    check("the real `gap_open` read is extracted (the pre-close open gap)",
          len(gap_stmts) == 1)
    gap_ns: dict = {"os": os}
    _exec_stmts(gap_stmts, gap_ns, str(TASKS))
    check(
        f"the real `gap_open` default (env unset) is {gap_ns['gap_open']:.3f} m",
        gap_ns["gap_open"] == 0.09,
    )

    class _Recorder:
        def __init__(self):
            self.gaps = []

        def follow_centre(self, centre, quat, gap):
            self.gaps.append(float(gap))
            return np.asarray(centre, dtype=float)

    class _Arm:
        def ik_step(self, target):
            return None

        def tcp_target_for_jaw(self, target):
            return target

    class _Spawner:
        def position(self, sample):
            return np.array([0.30, 0.00, 0.12])

        def velocity(self, sample):
            return np.array([0.0, 0.12, 0.0])

    class _Self2:
        def __init__(self, recorder):
            self.spawner = _Spawner()
            self.grippers = {"left": recorder}
            self.steps = 0

        def _pad_standoff(self, dynamic, sample):
            return 0.07

        def _step_sim(self, n):
            self.steps += 1

    def run_reseat(regrasp_from_open, squeeze_gap, gap_open):
        """Exec the REAL keep_gap + descent_gap + descent loop + close block."""
        recorder = _Recorder()
        fake = _Self2(recorder)
        ns = {
            "np": np,
            "min_jerk_ramp": min_jerk_ramp,
            "self": fake,
            "arm": _Arm(),
            "sample": object(),
            "quat_now": np.array([1.0, 0.0, 0.0, 0.0]),
            "dynamic_lead_s": 0.18,
            "arm_name": "left",
            "squeeze_gap": squeeze_gap,
            "grip_gap": 0.036,
            "gap_open": gap_open,
            "wide": 0.052,
            "fast_ticks": 24,
            "load_ticks": 60,
            "regrasp_from_open": regrasp_from_open,
        }
        _exec_stmts(
            [keep_stmts[0], descent_stmts[0], desc_loops[0], close_ifs[0]],
            ns,
            str(TASKS),
        )
        return ns["keep_gap"], ns["descent_gap"], recorder.gaps, fake.steps

    chased = 0.0519  # a P10-E chased keep-gap: 51.9 mm on a 68.3 mm orange
    extent = 0.0683
    keep_off, descent_off, gaps_off, steps_off = run_reseat(
        False, chased, gap_ns["gap_open"]
    )
    keep_on, descent_on, gaps_on, steps_on = run_reseat(
        True, chased, gap_ns["gap_open"]
    )
    check(
        "knob off: `keep_gap` is the chased depth and `descent_gap` == "
        "`keep_gap` (the shipped descend-at-the-chased-gap)",
        keep_off == chased and descent_off == keep_off,
    )
    check(
        "knob off: the gap sequence is `[keep_gap] * 40` - the shipped "
        "descent loop and no close block (the no-harm replay)",
        gaps_off == [chased] * 40 and steps_off == 40,
    )
    check(
        "knob off: the shipped descent gap is below the fruit's extent "
        "(the P11-B `plow` condition reproduced)",
        descent_off < extent,
    )
    check(
        "knob on: `descent_gap` == `gap_open` (the open-gap descent)",
        descent_on == gap_ns["gap_open"],
    )
    expected_ramp = np.concatenate(
        [
            min_jerk_ramp(gap_ns["gap_open"], 0.052, 24),
            min_jerk_ramp(0.052, chased, 60),
        ]
    )
    ramp = np.asarray(gaps_on[40:], dtype=float)
    check(
        "knob on: the sequence is `[gap_open] * 40` + the two-phase close "
        "ramp (40 descent ticks + 24 + 60 close ticks)",
        len(gaps_on) == 40 + 24 + 60
        and gaps_on[:40] == [gap_ns["gap_open"]] * 40
        and np.allclose(ramp, expected_ramp, rtol=0.0, atol=1e-12)
        and steps_on == 40 + 84,
    )
    check(
        "knob on: the close starts at ~gap_open (still wider than the "
        "blocking span at the first close tick)",
        abs(float(ramp[0]) - gap_ns["gap_open"]) < 1e-3,
    )
    check(
        "knob on: the close ramp is monotone non-increasing",
        bool(np.all(np.diff(ramp) <= 1e-12)),
    )
    check(
        "knob on: the close ramp ends exactly at `keep_gap` (the same "
        "re-seat depth the shipped form kept)",
        float(ramp[-1]) == chased,
    )
    check(
        f"the geometry invariant: gap_open {gap_ns['gap_open']:.3f} > the "
        f"largest pool extent {MAX_POOL_EXTENT:.3f} + the probe's measured "
        f"link-span offset {BLOCKING_OFFSET:.4f}",
        gap_ns["gap_open"] > MAX_POOL_EXTENT + BLOCKING_OFFSET,
    )

    say_calls = []
    for st in keep_body:
        for n in ast.walk(st):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "say"
            ):
                say_calls.append(n)
    check("the keep branch's single say row is present", len(say_calls) == 1)
    if len(say_calls) == 1:
        say_expr = say_calls[0].args[0]

        def eval_say(regrasp_from_open, keep_gap):
            return eval(
                compile(ast.Expression(body=say_expr), str(TASKS), "eval"),
                {"keep_gap": keep_gap, "regrasp_from_open": regrasp_from_open},
            )

        shipped_say = (
            "[task]   dynamic regrasp: re-seated in place "
            "(gap 51.9 mm kept)"
        )
        check(
            "knob off: the say row is the byte-identical shipped string",
            eval_say(False, chased) == shipped_say,
        )
        check(
            "knob on: the say row gains exactly the ` [from-open]` suffix "
            "(the battery's geometry marker)",
            eval_say(True, chased) == shipped_say + " [from-open]",
        )

    # ---- 4. rl_env pin -------------------------------------------------------
    print("== 4. rl_env pin ==")
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
        "RESULT: PASS (the knob resolves through the pre-registered "
        "`_dynamic_profile` triple with default 0 = the shipped branch on "
        "every session; the real statements exec'd end-to-end give "
        "`[keep_gap] * 40` with the knob off - the byte-inert no-harm replay - "
        "and `[gap_open] * 40` + the two-phase close to the same keep depth "
        "with it on; the open gap is wider than the measured blocking span; "
        "the say row is byte-identical off and gains ` [from-open]` on; the "
        "pin matches)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
