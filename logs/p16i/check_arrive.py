#!/usr/bin/env python3
"""P16-I stub check: the completed-descent arrival (pick (a)), offline.

Tier-C-level implementation evidence - NOT a substitute for the pre-registered
Stage-M screen (`logs/p16/BOUNDARY_DESIGN.md` section 4; the screen is a
separate lane and needs the simulator). Layers:

1. Source checks: the three knobs are read exactly once each with the shipped
   defaults (`"0.0"` / `"0"` / `"0"`); the `_approach` signature gains the three
   default-off parameters (AST defaults pinned); the moving-catch call passes
   the knobs only under `dynamic_capture`; the pre-grasp call passes no arrival
   keywords; the `[arrive]`/`[boundary]` row block is gated on
   `self._dynamic_arrive_diag and dynamic_capture and (not skip_approach)` and
   contains no control-side writes; the `_arrive_hold` call precedes the
   monitor's `end=` computation in `_approach` (the settled gap is what the
   motion row reports).
2. The knob resolution: the REAL `__init__` assignment statements are exec'd
   under env values (unset / the battery values / off / negative clamping).
3. Default-off byte-identity: `_arrive_hold` with tol=0 or max=0 returns None
   without touching the arm or the stepping hook (a raising operand proves no
   call is made); the row block prints nothing with the diag off.
4. The arrival loop on synthetic residuals: the REAL `_arrive_hold` is exec'd
   against a synthetic first-order arm (converges, never converges, already
   arrived, edge equality, overshoot) and compared against an independent
   reference; the `ik_step(target)` + one-`_step_sim`-per-tick structure is
   pinned (one command and one tick per used tick, target passed unchanged).
5. The rows' format: the REAL `[arrive]`/`[boundary]` statements are exec'd
   with synthetic bindings; the exact strings and the margin arithmetic
   (reach_dn/reach_up/belt_margin) are checked against independent references;
   `[arrive]` only prints when the loop ran (`arrive_info is not None`).
6. `rl_env.TASKS_MD5 == md5(tasks.py)`.

Run:  python3 logs/p16i/check_arrive.py
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


def _assign_to(stmts: list, attr: str) -> ast.stmt | None:
    out = []
    for st in stmts:
        if (
            isinstance(st, ast.Assign)
            and len(st.targets) == 1
            and isinstance(st.targets[0], ast.Attribute)
            and st.targets[0].attr == attr
        ):
            out.append(st)
    if len(out) != 1:
        return None
    return out[0]


def main() -> int:
    source = TASKS.read_text(encoding="utf-8")
    tree = ast.parse(source)

    init = _method(tree, "PickAndPlaceTask", "__init__")
    impl = _method(tree, "PickAndPlaceTask", "_grasp_carry_place_impl")
    approach = _method(tree, "PickAndPlaceTask", "_approach")
    hold_fn = _method(tree, "PickAndPlaceTask", "_arrive_hold")

    # ---- 1. source checks ----------------------------------------------------
    print("== 1. source checks ==")
    check(
        "`FRUIT_DYNAMIC_ARRIVE_TOL` is read exactly once, default \"0.0\"",
        source.count('os.environ.get("FRUIT_DYNAMIC_ARRIVE_TOL"') == 1
        and 'os.environ.get("FRUIT_DYNAMIC_ARRIVE_TOL", "0.0")' in source,
    )
    check(
        "`FRUIT_DYNAMIC_ARRIVE_MAX` is read exactly once, default \"0\"",
        source.count('os.environ.get("FRUIT_DYNAMIC_ARRIVE_MAX"') == 1
        and 'os.environ.get("FRUIT_DYNAMIC_ARRIVE_MAX", "0")' in source,
    )
    check(
        "`FRUIT_DYNAMIC_ARRIVE_DIAG` is read exactly once, default \"0\"",
        source.count('os.environ.get("FRUIT_DYNAMIC_ARRIVE_DIAG"') == 1
        and 'os.environ.get("FRUIT_DYNAMIC_ARRIVE_DIAG", "0")' in source,
    )
    tol_stmt = _assign_to(init.body, "_dynamic_arrive_tol")
    max_stmt = _assign_to(init.body, "_dynamic_arrive_max")
    diag_stmt = _assign_to(init.body, "_dynamic_arrive_diag")
    check(
        "the three attributes are assigned exactly once each in __init__ (AST)",
        tol_stmt is not None and max_stmt is not None and diag_stmt is not None,
    )

    # `_approach` signature: the three new params, default-off.
    arg_names = [a.arg for a in approach.args.args]
    arg_defaults = dict(zip(arg_names[-len(approach.args.defaults):],
                            approach.args.defaults))
    check(
        "`_approach` gains arrive_tol=0.0, arrive_max=0, report_end=False "
        "(AST defaults; every caller that passes nothing is byte-unchanged)",
        set(arg_defaults) >= {"arrive_tol", "arrive_max", "report_end"}
        and ast.literal_eval(arg_defaults["arrive_tol"]) == 0.0
        and ast.literal_eval(arg_defaults["arrive_max"]) == 0
        and ast.literal_eval(arg_defaults["report_end"]) is False,
    )
    check(
        "`_approach` calls `_arrive_hold(arm, target, arrive_tol, arrive_max)` "
        "exactly once, no keywords (the gate lives in the helper)",
        source.count("self._arrive_hold(") == 1
        and [
            ast.unparse(c)
            for c in ast.walk(approach)
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "_arrive_hold"
        ] == ["self._arrive_hold(arm, target, arrive_tol, arrive_max)"],
    )
    check(
        "the `_arrive_hold` call precedes the monitor's `end=` block in "
        "`_approach` (the motion row's `end=` is the settled gap when the "
        "loop ran)",
        next(i for i, st in enumerate(approach.body)
             if "_arrive_hold" in ast.unparse(st))
        < next(i for i, st in enumerate(approach.body)
               if "end_gap_mm" in ast.unparse(st)),
    )
    check(
        "`_approach` returns `(end_gap_m, arrive_info)`",
        isinstance(approach.body[-1], ast.Return)
        and isinstance(approach.body[-1].value, ast.Tuple)
        and [ast.unparse(e) for e in approach.body[-1].value.elts]
        == ["end_gap_m", "arrive_info"],
    )
    check(
        "the monitor's `end=` recipe is unchanged (one site)",
        source.count('summary["end_gap_mm"] = float(') == 1,
    )

    # The two `_approach` call sites: the moving catch passes the knobs
    # (scoped), the pre-grasp call passes nothing.
    calls = [
        c for c in ast.walk(impl)
        if isinstance(c, ast.Call)
        and isinstance(c.func, ast.Attribute)
        and c.func.attr == "_approach"
    ]
    check("exactly two `_approach` call sites in `_grasp_carry_place_impl`",
          len(calls) == 2)
    moving = [c for c in calls if ast.unparse(c.args[1]) == "grip"]
    pregrasp = [c for c in calls if ast.unparse(c.args[1]) == "free"]
    check("the moving catch is the `grip` call and the pre-grasp is `free`",
          len(moving) == 1 and len(pregrasp) == 1)
    if len(moving) != 1 or len(pregrasp) != 1:
        print("cannot continue without both call sites")
        return 1
    kw = {k.arg: ast.unparse(k.value) for k in moving[0].keywords}
    check(
        "the moving-catch call passes the knobs under `dynamic_capture` "
        "(0.0 / 0 on every other dynamic state) and `report_end` on the diag",
        kw.get("arrive_tol") == "self._dynamic_arrive_tol if dynamic_capture else 0.0"
        and kw.get("arrive_max") == "self._dynamic_arrive_max if dynamic_capture else 0"
        and kw.get("report_end") == "bool(self._dynamic_arrive_diag and dynamic_capture)",
    )
    pre_kw = {k.arg for k in pregrasp[0].keywords}
    check("the pre-grasp call passes no arrival keywords (byte-unchanged)",
          pre_kw == {"verbose"})

    # The row block: gated on the diag + the dynamic capture + a descent.
    row_blocks = [
        n for n in ast.walk(impl)
        if isinstance(n, ast.If)
        and "_dynamic_arrive_diag" in ast.unparse(n.test)
        and any(
            isinstance(st, ast.Expr)
            and isinstance(st.value, ast.Call)
            and isinstance(st.value.func, ast.Name)
            and st.value.func.id == "say"
            for st in n.body
        )
    ]
    check("exactly one `[arrive]`/`[boundary]` row block in the impl (AST)",
          len(row_blocks) == 1)
    if len(row_blocks) != 1:
        print("cannot continue without the row block")
        return 1
    row_block = row_blocks[0]
    check(
        "the row block is gated exactly on "
        "`self._dynamic_arrive_diag and dynamic_capture and (not skip_approach)`",
        ast.unparse(row_block.test)
        == "self._dynamic_arrive_diag and dynamic_capture and (not skip_approach)",
    )
    row_src = ast.unparse(row_block)
    check(
        "the row block is pure reporting (no control-side writes, no "
        "stepping/IK calls, no `self.<attr> =` assignments)",
        not any(
            isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) for t in n.targets)
            for n in ast.walk(row_block)
        )
        and "ik_step" not in row_src
        and "_step_sim" not in row_src
        and "set_dof" not in row_src,
    )
    arrive_says = [
        n for n in ast.walk(row_block)
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name) and n.value.func.id == "say"
        and "[arrive]" in ast.unparse(n)
    ]
    boundary_says = [
        n for n in ast.walk(row_block)
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name) and n.value.func.id == "say"
        and "[boundary]" in ast.unparse(n)
    ]
    check("one `[arrive]` say and one `[boundary]` say",
          len(arrive_says) == 1 and len(boundary_says) == 1)
    check(
        "the `[arrive]` say sits inside `if arrive_info is not None:` "
        "(only printed when the loop ran)",
        any(
            isinstance(st, ast.If)
            and ast.unparse(st.test) == "arrive_info is not None"
            and any(
                "[arrive]" in ast.unparse(inner) for inner in ast.walk(st)
            )
            for st in row_block.body
        ),
    )

    # The arrival loop: one ik_step + one step per tick, target passed through.
    hold_src = ast.unparse(hold_fn)
    check(
        "`_arrive_hold` commands `arm.ik_step(target)` and steps once per "
        "iteration (the design's primitive pair)",
        "arm.ik_step(target)" in hold_src
        and "self._step_sim(1)" in hold_src
        and len([
            n for n in ast.walk(hold_fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "ik_step"
        ]) == 1
        and len([
            n for n in ast.walk(hold_fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "_step_sim"
        ]) == 1,
    )
    off_gate = next(
        st for st in hold_fn.body
        if isinstance(st, ast.If) and "tol <= 0.0" in ast.unparse(st.test)
    )
    check(
        "the off gate is `if tol <= 0.0 or max_ticks <= 0: return None`",
        " ".join(ast.unparse(off_gate).split())
        == "if tol <= 0.0 or max_ticks <= 0: return None",
    )

    # ---- 2. the knob resolution (real statements, exec'd) --------------------
    print("== 2. knob resolution (real statements, exec'd) ==")

    class _Self:
        pass

    def read_knob(stmt, env_name, env_value):
        ns = {"os": os, "self": _Self()}
        prev = os.environ.get(env_name)
        if env_value is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = env_value
        try:
            _exec_stmts([stmt], ns, str(TASKS))
        finally:
            if prev is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = prev
        return ns["self"]

    tol_cases = [(None, 0.0), ("0.006", 0.006), ("0", 0.0), ("-1", 0.0)]
    ok = True
    for env_value, expected in tol_cases:
        got = read_knob(tol_stmt, "FRUIT_DYNAMIC_ARRIVE_TOL", env_value)
        ok = ok and got._dynamic_arrive_tol == expected
    check("tol: unset -> 0.0; 0.006 -> 0.006; 0 -> 0.0; -1 -> 0.0 (clamped)",
          ok)
    max_cases = [(None, 0), ("24", 24), ("0", 0), ("-3", 0)]
    ok = True
    for env_value, expected in max_cases:
        got = read_knob(max_stmt, "FRUIT_DYNAMIC_ARRIVE_MAX", env_value)
        ok = ok and got._dynamic_arrive_max == expected
    check("max: unset -> 0; 24 -> 24; 0 -> 0; -3 -> 0 (clamped)", ok)
    diag_cases = [(None, False), ("1", True), ("true", False), ("0", False)]
    ok = True
    for env_value, expected in diag_cases:
        got = read_knob(diag_stmt, "FRUIT_DYNAMIC_ARRIVE_DIAG", env_value)
        ok = ok and got._dynamic_arrive_diag == expected
    check("diag: unset -> False; 1 -> True; true -> False; 0 -> False", ok)

    # ---- 3. default-off byte-identity ---------------------------------------
    print("== 3. default-off byte-identity ==")
    hold_ns: dict = {"np": np}
    _exec_stmts([hold_fn], hold_ns, str(TASKS))
    arrive_hold = hold_ns["_arrive_hold"]

    class _Boom:
        def __getattr__(self, name):
            raise AssertionError(f"touched {name} while the loop is off")

    off_ok = True
    for tol, max_ticks in [(0.0, 24), (0.006, 0), (0.0, 0), (-1.0, 24), (0.006, -3)]:
        try:
            off_ok = off_ok and arrive_hold(
                _Boom(), _Boom(), _Boom(), tol, max_ticks
            ) is None
        except AssertionError:
            off_ok = False
    check("`_arrive_hold` returns None for every off combination without "
          "touching the arm or the stepping hook (a raising operand proves no "
          "call is made)", off_ok)

    class _StepSelf:
        def __init__(self):
            self.ticks = 0

        def _step_sim(self, steps: int = 1):
            self.ticks += steps

    # ---- 4. the arrival loop on synthetic residuals --------------------------
    print("== 4. the arrival loop (real method, exec'd) ==")

    class _Arm:
        """First-order arm: each command closes `step` metres, floored at 0."""

        def __init__(self, start, step):
            self.pos = np.asarray(start, dtype=float)
            self.step = float(step)
            self.commands: list[np.ndarray] = []

        def tcp_position(self):
            return self.pos.copy()

        def ik_step(self, target):
            target = np.asarray(target, dtype=float)
            self.commands.append(target.copy())
            delta = target - self.pos
            distance = float(np.linalg.norm(delta))
            if distance > 0.0:
                move = min(self.step, distance)
                self.pos = self.pos + delta / distance * move
            return float(np.linalg.norm(target - self.pos))

    def reference(start_gap, step, tol, max_ticks):
        """Independent reference: check-then-command, one `step` per tick."""
        gap = float(start_gap)
        ticks = 0
        for _ in range(int(max_ticks)):
            if gap <= tol:
                break
            ticks += 1
            gap = max(gap - step, 0.0)
        return ticks, gap

    def run_hold(start, step, tol, max_ticks):
        fake = _StepSelf()
        arm = _Arm(start, step)
        result = arrive_hold(fake, arm, np.zeros(3), tol, max_ticks)
        return result, arm, fake

    cases = [
        ("converges inside the cap (10 mm, 2 mm/tick, tol 6): stops at the tol",
         (0.010, 0.0, 0.0), 0.002, 0.006, 24),
        ("already arrived (3 mm <= tol 6): zero ticks commanded",
         (0.003, 0.0, 0.0), 0.001, 0.006, 24),
        ("edge equality (6 mm == tol 6): zero ticks",
         (0.006, 0.0, 0.0), 0.001, 0.006, 24),
        ("never converges inside the cap (100 mm, 1 mm/tick, tol 6, max 24)",
         (0.100, 0.0, 0.0), 0.001, 0.006, 24),
        ("single-tick overshoot (10 mm, 50 mm/tick): lands on the aim",
         (0.010, 0.0, 0.0), 0.050, 0.006, 24),
        ("off-diagonal residual keeps its direction",
         (0.010, 0.010, 0.0), 0.004, 0.006, 24),
    ]
    for label, start, step, tol, max_ticks in cases:
        start_gap = float(np.linalg.norm(np.asarray(start, dtype=float)))
        want_ticks, want_gap = reference(start_gap, step, tol, max_ticks)
        result, arm, fake = run_hold(start, step, tol, max_ticks)
        got_ticks, got_gap = int(result[2]), float(result[1])
        check(
            f"{label}: ticks={got_ticks} (ref {want_ticks}), "
            f"settled={got_gap * 1000:.2f}mm (ref {want_gap * 1000:.2f}mm)",
            got_ticks == want_ticks and abs(got_gap - want_gap) < 1e-12,
        )
        check(
            f"  the same case commands exactly {got_ticks} ik_step(s) + "
            f"{got_ticks} physics tick(s), all at the aim",
            len(arm.commands) == got_ticks
            and fake.ticks == got_ticks
            and all(np.allclose(c, 0.0) for c in arm.commands),
        )

    # The returned start/settled/residual bookkeeping.
    result, _, _ = run_hold((0.010, 0.0, 0.0), 0.002, 0.006, 24)
    start_gap, settled_gap, ticks, residual = result
    check(
        "the tuple is (start_gap, settled_gap, ticks, residual): "
        "10.0 -> 6.0 mm in 2 ticks, residual = +6.0 mm on x",
        abs(start_gap - 0.010) < 1e-12 and abs(settled_gap - 0.006) < 1e-12
        and ticks == 2 and np.allclose(residual, [0.006, 0.0, 0.0]),
    )
    result, _, _ = run_hold((0.003, 0.0, 0.0), 0.001, 0.006, 24)
    check(
        "an already-arrived descent returns the initial residual as the "
        "settled one (ticks=0)",
        result[2] == 0 and abs(result[0] - 0.003) < 1e-12
        and abs(result[1] - 0.003) < 1e-12,
    )

    # ---- 5. the rows' format (real statements, exec'd) -----------------------
    print("== 5. the rows' format (real statements, exec'd) ==")

    class _Sample:
        index = 3

    class _Spawner:
        def __init__(self, x):
            self._x = x

        def position(self, sample):
            return np.array([self._x, 0.0, 1.19])

    class _RowSelf:
        def __init__(self, diag, band, belt_top, fruit_x):
            self._dynamic_arrive_diag = diag
            self._reach_band_for = lambda arm, x: band
            self.belt_top = belt_top
            self.spawner = _Spawner(fruit_x)

    def run_rows(diag=True, dynamic_capture=True, skip_approach=False,
                 arrive_info=(0.0094, 0.0031, 7, np.array([0.0012, -0.0025, 0.0015])),
                 end_gap_m=0.0031, grip=(0.28, 0.0175, 1.265), station_y=0.0,
                 finger_len=0.060, belt_top=1.170, band=(-0.05, 0.10),
                 fruit_x=0.28):
        out: list[str] = []
        ns = {
            "self": _RowSelf(diag, band, belt_top, fruit_x),
            "say": out.append,
            "np": np,
            "arm_name": "left",
            "sample": _Sample(),
            "grip": np.asarray(grip, dtype=float),
            "station_y": float(station_y),
            "finger_len": float(finger_len),
            "end_gap_m": end_gap_m,
            "arrive_info": arrive_info,
            "dynamic_capture": bool(dynamic_capture),
            "skip_approach": bool(skip_approach),
        }
        _exec_stmts([row_block], ns, str(TASKS))
        return out

    def reference_rows(arrive_info, end_gap_m, grip, station_y, finger_len,
                       belt_top, band):
        """Independent reference strings for the two rows."""
        rows = []
        if arrive_info is not None:
            start, settled, ticks, res = arrive_info
            rows.append(
                f"[arrive] left idx=3 start={start * 1000:.1f}mm "
                f"settled={settled * 1000:.1f}mm ticks={int(ticks)} "
                f"dx={float(res[0]) * 1000:+.1f}mm "
                f"dy={float(res[1]) * 1000:+.1f}mm "
                f"dz={float(res[2]) * 1000:+.1f}mm"
            )
        aim_rel = float(grip[1]) - float(station_y)
        rows.append(
            f"[boundary] left idx=3 end={float(end_gap_m) * 1000:.1f}mm "
            f"reach_dn={(aim_rel - band[0]) * 1000:+.1f}mm "
            f"reach_up={(band[1] - aim_rel) * 1000:+.1f}mm "
            f"belt_margin="
            f"{(float(grip[2]) - float(belt_top) - float(finger_len)) * 1000:+.1f}mm"
        )
        return rows

    default_rows = run_rows()
    want = reference_rows(
        (0.0094, 0.0031, 7, np.array([0.0012, -0.0025, 0.0015])),
        0.0031, (0.28, 0.0175, 1.265), 0.0, 0.060, 1.170, (-0.05, 0.10),
    )
    check(
        "the treatment pair matches the independent reference exactly: "
        f"{default_rows}",
        default_rows == want,
    )
    check(
        "the `[arrive]` row carries start/settled/ticks and the signed "
        "direction in mm",
        default_rows[0] == (
            "[arrive] left idx=3 start=9.4mm settled=3.1mm ticks=7 "
            "dx=+1.2mm dy=-2.5mm dz=+1.5mm"
        ),
    )
    check(
        "the `[boundary]` row carries the end= shortfall and the three "
        "margins in mm",
        default_rows[1] == (
            "[boundary] left idx=3 end=3.1mm reach_dn=+67.5mm "
            "reach_up=+82.5mm belt_margin=+35.0mm"
        ),
    )

    # Margins can be negative (outside the band / below the belt margin).
    outside = run_rows(grip=(0.28, 0.13, 1.20))
    check(
        "outside the band / below the belt: the margins go negative "
        f"({outside[1]})",
        outside[1] == (
            "[boundary] left idx=3 end=3.1mm reach_dn=+180.0mm "
            "reach_up=-30.0mm belt_margin=-30.0mm"
        ),
    )

    # The control form: the arrival off (arrive_info None) prints only the
    # boundary row, with the end= it was given.
    control = run_rows(arrive_info=None, end_gap_m=0.0094)
    check(
        "arrival off: only the `[boundary]` row, end= = the shipped shortfall",
        control == [
            "[boundary] left idx=3 end=9.4mm reach_dn=+67.5mm "
            "reach_up=+82.5mm belt_margin=+35.0mm"
        ],
    )

    # Gating: diag off, non-dynamic capture, or a skipped descent print nothing.
    check("diag off: no rows", run_rows(diag=False) == [])
    check("non-dynamic capture: no rows",
          run_rows(dynamic_capture=False) == [])
    check("skipped descent (the direct hold): no rows",
          run_rows(skip_approach=True) == [])

    # ---- 6. rl_env pin -------------------------------------------------------
    print("== 6. rl_env pin ==")
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
    print("RESULT: PASS (the knobs resolve default-off and clamp negatives; "
          "the off gate returns None without touching the arm - the shipped "
          "path is byte-unchanged; the real arrival loop matches the "
          "independent reference on synthetic residuals, stops at the tol and "
          "caps at the max with one command + one tick per used tick; the real "
          "[arrive]/[boundary] rows match the reference format and arithmetic "
          "and print only under the diag on a dynamic descent; the pin "
          "matches)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
