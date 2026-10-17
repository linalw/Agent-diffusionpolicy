#!/usr/bin/env python3
"""P10-C.2 stub check: the slip-magnitude confirmation gate, offline.

Tier-C-level implementation evidence - NOT a substitute for the pre-registered
Tier-A battery (`logs/p10c/PREREG_CONFIRM_GATE.md`; the battery starts only
after the Oracle gate and is a separate lane). Layers:

1. Source checks: `FRUIT_CARRY_MONITOR_CONFIRM_MM` is read exactly once with
   default "0.0"; the P10-C knobs are unchanged (one read each); the trip tick
   is a bare `mon_leg.step(...)` - the fire bookkeeping (`fires += 1`,
   `skip = True`, the single `[monitor] fire` print) sits inside the boundary
   decision block only; the two fast-skip sites in `_grasp_carry_place_impl`
   are unchanged and never read the confirm knob; the fire row still carries
   `asym@fire` and gains the leg's `clean_slip_max`; the `[monitor] cancel`
   row exists once; the decision block runs after the per-tick loop.
2. The gate expression: the REAL `if (... <= 0.0 or ... >= ...)` test is
   extracted from `_carry` by AST and exec'd over a truth table against an
   independent reference (`confirm <= 0 or slip_mm >= confirm`). The knob-off
   rows confirm every trip regardless of slip, and the short-circuit is
   *proven* by evaluating with a slip operand that raises if touched (the
   knob-on form does evaluate it).
3. The decision block end-to-end: the REAL boundary `if` statement is exec'd
   with synthetic bindings. Confirmed trips (>= threshold; and every trip at
   the default 0.0) count the fire, set the latch and print the fire row with
   the slip; cancelled trips (< threshold) print exactly the cancel row and
   leave the latch clear; a no-trip leg and an absent `mon_leg` do nothing
   (a cancelled trip is not a no-trip leg); the operand selection
   (`guard_slip_max` when `guard_armed`, else `mon_slip_max`) is pinned by a
   discriminating pair.
4. The monitor-path accumulator: the REAL per-tick `elif mon_leg is not None:`
   block is extracted, its liveness pinned (attached to `if guard_armed:` -
   live exactly when the guard/diag tracker is off; not gated on
   `FRUIT_CARRY_DIAG` or the confirm knob; live after a trip), and its
   arithmetic replayed over synthetic ticks against an independent reference
   of the running clean slip (`max_t ||d_t - d_0||`, rotation-invariant).
5. `rl_env.TASKS_MD5 == md5(tasks.py)`.

Run:  python3 logs/p10c2/check_confirm_gate.py
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


def _exec_stmts(stmts, ns: dict, filename: str) -> None:
    exec(compile(ast.Module(body=stmts, type_ignores=[]), filename, "exec"), ns)


def _exec_expr(expr, ns: dict, filename: str):
    return eval(compile(ast.Expression(body=expr), filename, "eval"), ns)


def main() -> int:
    source = TASKS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    init = _method(tree, "PickAndPlaceTask", "__init__")
    carry = _method(tree, "PickAndPlaceTask", "_carry")
    impl = _method(tree, "PickAndPlaceTask", "_grasp_carry_place_impl")

    # ---- 1. source checks ----------------------------------------------------
    print("== 1. source checks ==")
    knob_stmts = [
        st for st in init.body
        if isinstance(st, ast.Assign) and len(st.targets) == 1
        and isinstance(st.targets[0], ast.Attribute)
        and st.targets[0].attr == "_carry_monitor_confirm_mm"
    ]
    check("`self._carry_monitor_confirm_mm` is assigned exactly once in "
          "__init__ (AST)", len(knob_stmts) == 1)
    knob_stmt = knob_stmts[0] if knob_stmts else None
    check("`FRUIT_CARRY_MONITOR_CONFIRM_MM` is read exactly once in the file, "
          "default \"0.0\"",
          source.count('os.environ.get("FRUIT_CARRY_MONITOR_CONFIRM_MM"') == 1
          and 'os.environ.get("FRUIT_CARRY_MONITOR_CONFIRM_MM", "0.0")' in source)
    check("the P10-C knobs are unchanged (one read each)",
          source.count('os.environ.get("FRUIT_CARRY_MONITOR"') == 1
          and source.count('os.environ.get("FRUIT_CARRY_MONITOR_DIAG"') == 1
          and source.count('os.environ.get("FRUIT_CARRY_MONITOR_LOAD_FLOOR"') == 1
          and source.count('os.environ.get("FRUIT_CARRY_MONITOR_TWOLINE"') == 1)
    check("`_carry` has exactly one fire bookkeeping site (`fires += 1`, "
          "`skip = True`) and one fire print",
          source.count("self._carry_monitor_fires += 1") == 1
          and source.count("self._carry_monitor_skip = True") == 1
          and source.count('f"[monitor] fire ') == 1)
    check("the two fast-skip sites are unchanged (read only the latch) and the "
          "impl never reads the confirm knob",
          source.count("if self._carry_monitor_skip:") == 2
          and "_carry_monitor_confirm_mm" not in ast.unparse(impl))
    check("the cancel row exists exactly once, with the slip and the threshold",
          source.count('f"[monitor] cancel ') == 1
          and "clean_slip={leg_slip_max * 1000:.1f}mm" in source
          and "< {self._carry_monitor_confirm_mm:.1f}mm" in source)
    check("the fire row still carries `asym@fire` and gains `clean_slip_max`",
          "asym@fire={mon_leg.fire_asym:.2f}" in source
          and "clean_slip_max={leg_slip_max * 1000:.1f}mm" in source)
    check("the accumulator state is initialized once per leg",
          source.count("mon_slip_ref = None") == 1
          and source.count("mon_slip_max = 0.0") == 1)
    check("the operand is the guard tracker when it is live, else the "
          "monitor-path accumulator",
          "leg_slip_max = guard_slip_max if guard_armed else mon_slip_max"
          in source)

    # The boundary decision block: the `if mon_leg is not None and
    # mon_leg.fire is not None:` whose body holds the confirm gate.
    gate_stmts = [
        n for n in ast.walk(carry)
        if isinstance(n, ast.If)
        and "_carry_monitor_confirm_mm" in ast.unparse(n.test)
    ]
    check("exactly one confirm-gate `if` in `_carry` (AST)",
          len(gate_stmts) == 1)
    if len(gate_stmts) != 1 or knob_stmt is None:
        print("cannot continue without the gate / knob statements")
        return 1
    gate_stmt = gate_stmts[0]
    rel: dict = {}
    for n in ast.walk(carry):
        for c in ast.iter_child_nodes(n):
            rel[c] = n
    decision_stmt = rel.get(gate_stmt)
    check("the gate sits inside the boundary block "
          "(`mon_leg is not None and mon_leg.fire is not None`)",
          isinstance(decision_stmt, ast.If)
          and "mon_leg.fire is not None" in ast.unparse(decision_stmt.test))
    if not isinstance(decision_stmt, ast.If):
        print("cannot continue without the decision block")
        return 1
    decision_src = ast.unparse(decision_stmt)
    check("the fire bookkeeping sits inside the decision block, not the trip "
          "tick",
          "self._carry_monitor_fires += 1" in decision_src
          and "self._carry_monitor_skip = True" in decision_src)
    bare_steps = [
        n for n in ast.walk(carry)
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Attribute)
        and n.value.func.attr == "step"
        and isinstance(n.value.func.value, ast.Name)
        and n.value.func.value.id == "mon_leg"
    ]
    check("the trip tick is a bare `mon_leg.step(...)` (the trip is a "
          "candidate only)", len(bare_steps) == 1)

    outer = rel.get(decision_stmt)
    check("the decision block is a top-level statement of the gripper-led "
          "carry path",
          isinstance(outer, ast.If)
          and "grippers[side].enabled" in ast.unparse(outer.test))
    if isinstance(outer, ast.If):
        body = outer.body
        for_idx = next(
            (k for k, st in enumerate(body)
             if isinstance(st, ast.For) and "range(n_ticks)" in ast.unparse(st.iter)),
            None,
        )
        dec_idx = body.index(decision_stmt)
        check("the decision block runs after the per-tick loop (the leg "
              "boundary)", for_idx is not None and dec_idx > for_idx)

    # ---- the knob read (real statement, exec'd) ------------------------------
    class _Self:
        pass

    def read_knob(env_value):
        ns = {"os": os, "self": _Self()}
        prev = os.environ.get("FRUIT_CARRY_MONITOR_CONFIRM_MM")
        if env_value is None:
            os.environ.pop("FRUIT_CARRY_MONITOR_CONFIRM_MM", None)
        else:
            os.environ["FRUIT_CARRY_MONITOR_CONFIRM_MM"] = env_value
        try:
            _exec_stmts([knob_stmt], ns, str(TASKS))
        finally:
            if prev is None:
                os.environ.pop("FRUIT_CARRY_MONITOR_CONFIRM_MM", None)
            else:
                os.environ["FRUIT_CARRY_MONITOR_CONFIRM_MM"] = prev
        return ns["self"]._carry_monitor_confirm_mm

    check("knob default (unset) -> 0.0", read_knob(None) == 0.0)
    check("knob `=8.0` -> 8.0 (the battery value)", read_knob("8.0") == 8.0)
    check("knob `=0` -> 0.0 (the shipped form)", read_knob("0") == 0.0)

    # ---- 2. the gate expression (real AST, exec'd) ---------------------------
    print("== 2. gate truth table (real expression, exec'd) ==")

    class _Knob:
        def __init__(self, confirm_mm):
            self._carry_monitor_confirm_mm = confirm_mm

    def eval_gate(confirm_mm, slip_m):
        ns = {"self": _Knob(confirm_mm), "leg_slip_max": slip_m}
        return bool(_exec_expr(gate_stmt.test, ns, str(TASKS)))

    def reference(confirm_mm, slip_m):
        """Independent reference: `confirm <= 0 or slip_mm >= confirm`."""
        return confirm_mm <= 0.0 or slip_m * 1000.0 >= confirm_mm

    grid_confirm = [0.0, -1.0, 0.5, 2.0, 8.0, 100.0]
    grid_slip = [
        0.0, 0.0004, 0.002, 0.0063, 0.007999, 0.008, 0.008001,
        0.0131, 0.019, 0.053, 0.253, 1.6461,
    ]
    rows = 0
    bad = 0
    for c in grid_confirm:
        for s in grid_slip:
            rows += 1
            got = eval_gate(c, s)
            want = reference(c, s)
            if got != want:
                bad += 1
                failures.append(
                    f"gate mismatch: confirm={c} slip={s * 1000:.4f}mm "
                    f"live={got} reference={want}"
                )
    check(f"full truth table ({rows} rows: 6 confirm values x 12 slip values) "
          "vs the independent reference", bad == 0)

    class _Boom:
        def __mul__(self, other):
            raise AssertionError("the slip operand was evaluated")

    def eval_gate_boom(confirm_mm):
        ns = {"self": _Knob(confirm_mm), "leg_slip_max": _Boom()}
        return bool(_exec_expr(gate_stmt.test, ns, str(TASKS)))

    short_ok = False
    try:
        short_ok = eval_gate_boom(0.0) is True
    except AssertionError:
        short_ok = False
    check("knob 0.0 short-circuits: a slip operand that raises if touched is "
          "never evaluated and the trip confirms (byte-inert)", short_ok)
    raised = False
    try:
        eval_gate_boom(8.0)
    except AssertionError:
        raised = True
    check("knob 8.0 does evaluate the slip operand (the first operand does not "
          "swallow it)", raised)

    named = [
        ("the battery's ground-truth false positive (0.4 mm) at 8.0",
         8.0, 0.0004, False),
        ("the battery's control-placed pear (6.3 mm) at 8.0",
         8.0, 0.0063, False),
        ("the battery's lowest correct fire (13.1 mm) at 8.0",
         8.0, 0.0131, True),
        ("the late 19.0 mm slide at 8.0", 8.0, 0.019, True),
        ("the 1646.1 mm escape at 8.0", 8.0, 1.6461, True),
        ("the inclusive edge (8.000 mm) at 8.0", 8.0, 0.008, True),
        ("one tick below the edge (7.999 mm) at 8.0", 8.0, 0.007999, False),
        ("knob off (0.0): every trip confirms, even a 0.4 mm slip",
         0.0, 0.0004, True),
        ("knob off (0.0) with a zero slip", 0.0, 0.0, True),
        ("knob negative: the shipped form", -1.0, 0.0, True),
    ]
    for label, c, s, expected in named:
        got = eval_gate(c, s)
        check(f"{label}: confirm={got} (expected {expected})", got == expected)

    # ---- 3. the decision block end-to-end (real AST, exec'd) -----------------
    print("== 3. decision block end-to-end (real statement, exec'd) ==")

    class _DecisionSelf:
        def __init__(self, confirm_mm, diag):
            self._carry_monitor_confirm_mm = confirm_mm
            self._carry_monitor_diag = diag
            self._carry_monitor_fires = 0
            self._carry_monitor_skip = False
            self._carry_monitor_fired = []

    class _Leg:
        def __init__(self, fire):
            self.fire = fire
            self.fire_z = 1.80
            self.fire_asym = 4.71
            self.hot = 2
            self.blocked = 0
            self.min_contacts = 2

    def run_decision(confirm_mm, diag, guard_armed, guard_slip_m, mon_slip_m,
                     fire=138, leg_present=True):
        fake = _DecisionSelf(confirm_mm, diag)
        out: list[str] = []
        ns = {
            "self": fake,
            "mon_leg": _Leg(fire) if leg_present else None,
            "guard_armed": guard_armed,
            "guard_slip_max": guard_slip_m,
            "mon_slip_max": mon_slip_m,
            "name": "grasp_lift",
            "side": "left",
            "commands": [0.0] * 160,
            "say": out.append,
        }
        _exec_stmts([decision_stmt], ns, str(TASKS))
        return fake, out

    fake, out = run_decision(8.0, True, True, 0.019, 0.9)
    check("confirmed trip (19.0 mm >= 8.0): fire counted, latch set, fired "
          "list appended",
          fake._carry_monitor_fires == 1 and fake._carry_monitor_skip is True
          and fake._carry_monitor_fired == ["grasp_lift@138/160"])
    check("confirmed trip prints the fire row with the slip",
          len(out) == 1
          and out[0].startswith(
              "[monitor] fire left grasp_lift: tick=138/160")
          and "z=+1.80" in out[0] and "asym@fire=4.71" in out[0]
          and "clean_slip_max=19.0mm" in out[0])

    fake, out = run_decision(8.0, True, True, 0.0063, 0.9)
    check("cancelled trip (6.3 mm < 8.0): nothing counted, latch clear, fired "
          "list empty",
          fake._carry_monitor_fires == 0 and fake._carry_monitor_skip is False
          and fake._carry_monitor_fired == [])
    check("cancelled trip prints exactly the cancel row",
          out == ["[monitor] cancel left grasp_lift: tick=138/160 "
                  "clean_slip=6.3mm < 8.0mm"])

    fake, out = run_decision(8.0, True, True, 0.0004, 0.9)
    check("the frozen K2 false positive (0.4 mm) cancels",
          fake._carry_monitor_fires == 0
          and fake._carry_monitor_skip is False
          and out and out[0].startswith("[monitor] cancel")
          and "clean_slip=0.4mm" in out[0])

    fake, out = run_decision(8.0, True, True, 0.008, 0.9)
    check("the inclusive edge (8.000 mm) confirms",
          fake._carry_monitor_fires == 1
          and fake._carry_monitor_skip is True
          and out and "clean_slip_max=8.0mm" in out[0])

    fake, out = run_decision(0.0, True, True, 0.0004, 0.9)
    check("knob off (0.0): every trip confirms (a 0.4 mm slip still fires - "
          "the P10-C form)",
          fake._carry_monitor_fires == 1 and fake._carry_monitor_skip is True
          and fake._carry_monitor_fired == ["grasp_lift@138/160"]
          and out and out[0].startswith("[monitor] fire"))

    fake, out = run_decision(0.0, False, False, 0.0, 0.0)
    check("knob off + diag off: latch set and counters updated, no diag "
          "traffic",
          fake._carry_monitor_fires == 1
          and fake._carry_monitor_skip is True and out == [])

    fake, out = run_decision(8.0, False, False, 0.9, 0.0063)
    check("cancelled trip with the diag off: latch stays clear, no output",
          fake._carry_monitor_fires == 0
          and fake._carry_monitor_skip is False and out == [])

    fake, out = run_decision(8.0, True, False, 0.9, 0.0063)
    check("operand selection: diag/guard off -> the accumulator's 6.3 mm "
          "cancels (the guard value is a decoy)",
          fake._carry_monitor_fires == 0
          and out and out[0].startswith("[monitor] cancel"))

    fake, out = run_decision(8.0, True, True, 0.0063, 0.9)
    check("operand selection: guard tracker live -> its 6.3 mm cancels (the "
          "accumulator value is a decoy)",
          fake._carry_monitor_fires == 0
          and out and out[0].startswith("[monitor] cancel"))

    fake, out = run_decision(8.0, True, False, 0.9, 0.019)
    check("operand selection: diag off -> the accumulator's 19.0 mm confirms",
          fake._carry_monitor_fires == 1
          and "clean_slip_max=19.0mm" in out[0])

    fake, out = run_decision(8.0, True, True, 0.019, 0.9)
    check("operand selection: guard tracker live -> its 19.0 mm confirms",
          fake._carry_monitor_fires == 1
          and "clean_slip_max=19.0mm" in out[0])

    fake, out = run_decision(8.0, True, True, 0.019, 0.9, fire=None)
    check("a leg that never tripped: nothing happens (no-trip != cancelled "
          "trip)",
          fake._carry_monitor_fires == 0
          and fake._carry_monitor_skip is False
          and fake._carry_monitor_fired == [] and out == [])

    fake, out = run_decision(8.0, True, True, 0.019, 0.9, leg_present=False)
    check("an unmonitored leg (`mon_leg is None`): nothing happens",
          fake._carry_monitor_fires == 0 and out == [])

    # ---- 4. the monitor-path accumulator (real AST, exec'd) ------------------
    print("== 4. monitor-path accumulator (real block, exec'd) ==")
    acc_stmts = [
        n for n in ast.walk(carry)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "mon_leg is not None"
        and isinstance(rel.get(n), ast.If)
        and ast.unparse(rel[n].test) == "guard_armed"
    ]
    check("one accumulator `elif mon_leg is not None:` attached to "
          "`if guard_armed:` (AST)", len(acc_stmts) == 1)
    if len(acc_stmts) != 1:
        print("cannot continue without the accumulator")
        return 1
    acc = acc_stmts[0]
    acc_test = ast.unparse(acc.test)
    check("the accumulator is not gated on the diag or the confirm knob (live "
          "on the monitor path with `FRUIT_CARRY_DIAG` off)",
          "_carry_diag" not in acc_test and "confirm" not in acc_test)
    check("the accumulator stays live after a trip (no `done` in its guard)",
          "done" not in acc_test)
    acc_src = ast.unparse(acc)
    check("the accumulator takes the same reads as the guard tracker",
          "arm.tcp_pose()" in acc_src and "_quat_matrix" in acc_src
          and "rot_now.T @ (fruit - pads)" in acc_src)
    check("the reference is set on the leg's first tick and the max "
          "accumulates from later ticks",
          "mon_slip_ref is None" in acc_src
          and "mon_slip_ref = rel_frame.copy()" in acc_src
          and "mon_slip_max = max(" in acc_src
          and "np.linalg.norm(rel_frame - mon_slip_ref)" in acc_src)

    qm_nodes = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_quat_matrix"
    ]
    if len(qm_nodes) != 1:
        raise SystemExit("STUB FAIL: module-level `_quat_matrix` not found")
    qm_ns: dict = {"np": np}
    _exec_stmts([qm_nodes[0]], qm_ns, str(TASKS))
    quat_matrix = qm_ns["_quat_matrix"]

    class _Arm:
        def __init__(self, quat):
            self._quat = quat

        def tcp_pose(self):
            return np.zeros(3), self._quat

    def run_accum(ticks, quat):
        """Replay the real accumulator body; `quat` fixed for the leg."""
        ns = {
            "mon_slip_ref": None, "mon_slip_max": 0.0, "np": np,
            "_quat_matrix": quat_matrix, "arm": _Arm(quat),
        }
        for fruit, pads in ticks:
            ns["fruit"] = np.asarray(fruit, dtype=float)
            ns["pads"] = np.asarray(pads, dtype=float)
            _exec_stmts(acc.body, ns, str(TASKS))
        return float(ns["mon_slip_max"])

    def reference_accum(ticks):
        """Independent reference: the max displacement from tick 0 in world
        units (a fixed leg rotation preserves the norm)."""
        d = [np.asarray(f, float) - np.asarray(p, float) for f, p in ticks]
        return max(
            [float(np.linalg.norm(x - d[0])) for x in d[1:]] or [0.0]
        )

    ticks = [
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((0.003, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((0.003, 0.004, 0.0), (0.0, 0.0, 0.0)),
        ((0.004, 0.004, 0.001), (0.001, 0.0, 0.0)),
    ]
    exp = reference_accum(ticks)
    got_id = run_accum(ticks, (1.0, 0.0, 0.0, 0.0))
    got_rot = run_accum(ticks, (0.70710678, 0.0, 0.0, 0.70710678))
    check(f"accumulator replay (identity quat): {got_id * 1000:.4f} mm == "
          f"reference {exp * 1000:.4f} mm", abs(got_id - exp) < 1e-12)
    check(f"accumulator replay (fixed 90-deg quat): {got_rot * 1000:.4f} mm == "
          f"reference {exp * 1000:.4f} mm (rotation-invariant)",
          abs(got_rot - exp) < 1e-12)
    check("the leg's first tick contributes zero slip",
          run_accum(ticks[:1], (1.0, 0.0, 0.0, 0.0)) == 0.0)

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
    print("RESULT: PASS (the knob read is default 0.0/byte-inert; the real "
          "gate expression's truth table matches the independent reference and "
          "the knob-off short-circuit is proven with a raising operand; the "
          "real decision block confirms at/above the threshold and cancels "
          "below it with the exact cancel row, on the correct operand; the "
          "monitor-path accumulator is live exactly where the gate needs it "
          "and reproduces the clean-slip reference; the fire/cancel rows carry "
          "the slip; the pin matches)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
