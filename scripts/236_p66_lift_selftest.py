#!/usr/bin/env python3
"""P66 phase 2/3 selftest: the lift-end instrument and the lift-height knob (a selfcheck leg).

Pins what is **off or inert by default**, and since phase 3 the one thing that is
**on** for the `direct` presentation:

1. **The instrument** (`[carry]` row, under the existing `FRUIT_CARRY_DIAG`,
   default "0"): `drift_end=` (the **last** guarded tick's hold drift, *not* the
   leg's max - a transient can set a max, and the registered mediator test needs
   the end), `res_end=` / `dz_end=` (the achieved TCP position error at the leg's
   end against the target the same tick issued: its norm in mm and its world-z
   component, signed). The target is the array `ik_step` was handed and
   `tcp_pose()` already returns the position, so the fields add **no pose read**:
   the old `np.asarray(arm.tcp_pose()[1], ...)` form (quaternion only) is gone.
   Phase 3 adds `clr=` - the leg's **minimum** payload clearance to the highest
   surface under it (P2-3's `_payload_clearance`, already measured every tick in
   the slip bookkeeping - again no new read) with the surface code the +33 mm
   access floor of record needs (`@belt/@obelt/@rail`).
2. **The knob** `FRUIT_LIFT_DZ` (metres above the `0.28` base, left arm,
   `grasp_lift` only): `rl_env.resolve_lift_dz` parses it strictly, `tasks.lift_dz_for`
   is the only resolver (None / empty / another side / any leg but `grasp_lift`
   -> `None`), and `jaw_target`'s `grasp_lift` branch - the single site that
   builds the target height - applies it, replacing the hand's clearance add.
   `None` (every caller but the direct env) runs the shipped expression
   byte-for-byte, and the dynamic catch's own goal inherits the target's z
   (`float(goal[2])`), so the ladder reads +0.08 = the shipped 0.36 m,
   0.00 = 0.28 m, -0.08 = 0.20 m. **Phase 3 flips the `direct` default to the
   0.20 m rung** (`LIFT_DZ_DIRECT_DEFAULT`) with `+0.08` as the documented
   restore, and records the origin (`default`/`explicit`) in the row and the
   manifest; every other presentation still resolves to `None`.

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def indented_body_contains(src: str, header: str, needle: int) -> bool:
    """True when `needle` (a character offset) lies in `header`'s indented body.

    The enclosing block is found by indentation, not by a character budget (the
    `235` helper, unchanged): the first later line indented **at or below** the
    header's own indentation ends it.
    """
    start = src.rfind(header, 0, needle)
    if start == -1:
        return False
    line_start = src.rfind("\n", 0, start) + 1
    indent = start - line_start
    for line in src[start:].splitlines()[1:]:
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            end = start + src[start:].index(line)
            return needle < end
    return True


def load_function(name: str, path: Path) -> tuple:
    """Compile one module-level function from source (tasks.py imports pxr)."""
    src = path.read_text(encoding="utf-8")
    node = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    ns: dict = {"np": np}
    exec(  # noqa: S102 - a pinned, self-owned source file
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            f"<{name}>",
            "exec",
        ),
        ns,
    )
    return ns[name], src


def main() -> int:
    from fruit_sorting.rl_env import (
        LIFT_DZ_DIRECT_DEFAULT,
        LIFT_DZ_HAND_ADD,
        SortingRLEnv,
        resolve_lift_dz,
    )

    saved = dict(os.environ)
    try:
        tasks_py = ROOT / "src/fruit_sorting/tasks.py"
        env_py = ROOT / "src/fruit_sorting/rl_env.py"
        lift_dz_for, src = load_function("lift_dz_for", tasks_py)
        env_src = env_py.read_text(encoding="utf-8")

        # ---------------------------------------------------------------- 1
        # the row's four fields, in place and in order
        for token in (
            'f"drift_end={_drift_end} "',
            'f"res_end={_res_end}mm dz_end={_dz_end}mm "',
            'f"clr={_clr} "',
        ):
            check(token in src, f"the [carry] row prints {token[2:].split('=')[0]}")
        order = [
            src.index('f"hold_drift={guard_drift_max:.1f}deg"'),
            src.index('f"drift_end={_drift_end} "'),
            src.index('f"res_end={_res_end}mm dz_end={_dz_end}mm "'),
            src.index('f"clr={_clr} "'),
            src.index('f"q_margin={_qm} q_cmd_margin={_qcm} "'),
            src.index('f"in-hand_vmax={guard_vmax:.3f} "'),
        ]
        check(order == sorted(order),
              "drift_end/res_end/dz_end/clr sit next to hold_drift= (before q_margin=)")

        # ---------------------------------------------------------------- 1b
        # `clr` is P2-3's own per-leg minimum, already measured every tick: the
        # field must not take a new read and must carry its surface code
        check(
            'clearance, where = self._payload_clearance(sample, fruit)' in src,
            "the clearance is the existing per-tick `_payload_clearance` read",
        )
        clr_block = src[src.index("if clearance_min == float(\"inf\"):"):]
        clr_block = clr_block[: clr_block.index('f"q_margin=')]
        for banned in ("position(", "tcp_pose(", "_shape_support(", "pad_centre("):
            check(banned not in clr_block, f"the clr field adds no read ({banned})")
        check(
            "clearance_min = float(\"inf\")" in src
            and "clearance_min, clearance_where = clearance, where" in src,
            "the field reads the leg's min and the surface it was taken against",
        )
        for surface, code in (("main belt", "belt"), ("output belt", "obelt"),
                             ("output rail", "rail")):
            check(f'"{surface}": "{code}"' in src,
                  f"the surface code table maps {surface!r} -> @{code}")
        check(
            indented_body_contains(src, "if guard_armed or relief_acts:",
                                   src.index('f"clr={_clr} "')),
            "clr prints inside the `guard_armed or relief_acts` block (carry diag)",
        )

        # ---------------------------------------------------------------- 2
        # inertness: every P66 tracker sits inside the `guard_armed` branch,
        # whose first condition is `_carry_guard_active or _carry_diag`
        check(
            "(self._carry_guard_active or self._carry_diag)" in src,
            "guard_armed is gated on _carry_guard_active or _carry_diag",
        )
        check(
            'self._carry_diag = os.environ.get("FRUIT_CARRY_DIAG", "0") == "1"' in src,
            "FRUIT_CARRY_DIAG defaults to off",
        )
        for needle in (
            "guard_drift_end = _drift_now",
            "guard_tcp_end = _tcp_pos",
            "guard_tcp_target = _tcp_tgt_issued",
        ):
            check(
                indented_body_contains(src, "if guard_armed:", src.index(needle)),
                f"`{needle}` is inside `if guard_armed:`",
            )
        ridx = src.index('f"res_end={_res_end}mm dz_end={_dz_end}mm "')
        rbranch = src.rfind("if guard_armed or relief_acts:", 0, ridx)
        check(
            rbranch != -1 and ridx - rbranch < 5000,
            "the fields print inside the `guard_armed or relief_acts` block",
        )
        for name in (
            'guard_drift_end = None',
            'guard_tcp_end = None',
            'guard_tcp_target = None',
        ):
            check(name in src, f"the tracker inits: {name.split(' =')[0]}")

        # ---------------------------------------------------------------- 3
        # drift_end is the LAST tick, not an extreme: it is assigned from the
        # same `_drift_now` the max reads, and that assignment is not wrapped in
        # a max()/min() - the whole point of the field.
        check(
            indented_body_contains(src, "if _hold is not None:", src.index("guard_drift_end = _drift_now")),
            "drift_end is written only on a tick with a live hold",
        )
        check(
            "guard_drift_end = max(" not in src and "guard_drift_end = min(" not in src,
            "drift_end is not an extreme of the leg",
        )
        seq = [4.0, 12.0, 24.6, 9.0]
        end = None
        for d in seq:
            end = d
        check(end == 9.0 and max(seq) == 24.6,
              "the sequence's last tick differs from its max (the field's reason)")

        # ---------------------------------------------------------------- 4
        # res_end/dz_end: the shipped expressions, on a worked example
        target = np.array([0.30, -0.05, 1.55])
        achieved = np.array([0.302, -0.048, 1.520])
        err = achieved - target
        check(abs(float(np.linalg.norm(err)) * 1000.0 - 30.13) < 0.02,
              "res_end = |achieved - target| in mm (z-dominated worked example)")
        check(abs(float(err[2]) * 1000.0 + 30.0) < 1e-6,
              "dz_end = the error's world-z component, signed (negative = short)")
        for expr in (
            "float(np.linalg.norm(_err_end)) * 1000.0",
            "float(_err_end[2]) * 1000.0",
        ):
            check(expr in src, f"the shipped expression is the one tested: {expr}")
        check("_err_end = np.asarray(guard_tcp_end, dtype=float) - np.asarray(\n                        guard_tcp_target, dtype=float\n                    )" in src
              or "_err_end = np.asarray(guard_tcp_end" in src,
              "the error is achieved TCP minus the issued target")
        # no new pose read: one tcp_pose() call, both outputs used, and the
        # target is the array ik_step was handed
        check(
            "_tcp_pos, _tcp_quat = arm.tcp_pose()" in src,
            "the guard reads tcp_pose() once and keeps the position too",
        )
        gstart = src.index("if guard_armed:", src.index("for i in range(n_ticks)"))
        gend = src.index("elif mon_leg is not None:", gstart)
        check(
            "np.asarray(arm.tcp_pose()[1], dtype=float)" not in src[gstart:gend],
            "the guarded branch's quaternion-only form is gone (no second read)",
        )
        check(
            "_tcp_tgt_issued = arm.tcp_target_for_jaw(centre)\n"
            "                        arm.ik_step(_tcp_tgt_issued)" in src,
            "the coherent jaw branch records the exact array ik_step was handed",
        )
        check(
            "_tcp_tgt_issued = arm.tcp_target_for_jaw(\n"
            "                        centre - rot @ offset_tool\n"
            "                    )\n"
            "                    arm.ik_step(_tcp_tgt_issued)" in src,
            "the assist branch records its own issued target",
        )
        check("_tcp_tgt_issued = None" in src,
              "the per-tick capture is initialised (a leg with no command reads None)")

        # ---------------------------------------------------------------- 5
        # the knob's resolver in tasks: None = the shipped target
        check(lift_dz_for(None, "left", "grasp_lift") is None,
              "None -> no arithmetic (the shipped lift height)")
        check(lift_dz_for({}, "left", "grasp_lift") is None,
              "an empty dict -> no arithmetic")
        check(lift_dz_for({"left": -0.08}, "right", "grasp_lift") is None,
              "a side not named by the offset is untouched (per-arm)")
        for leg in ("place0", "place1", "grasp", "approach", ""):
            check(lift_dz_for({"left": -0.08}, "left", leg) is None,
                  f"`{leg or 'empty'}` is out of scope (grasp_lift only)")
        got = lift_dz_for({"left": -0.08}, "left", "grasp_lift")
        check(isinstance(got, float) and abs(got + 0.08) < 1e-12,
              "the armed side resolves to the offset in metres (a float)")
        check(lift_dz_for({"left": 0.0}, "left", "grasp_lift") == 0.0,
              "=0.00 is an armed rung (and adds exactly zero)")
        check(src.count("lift_dz_for(") == 2,
              "lift_dz_for is the only resolver (its def + the one call site)")

        # ---------------------------------------------------------------- 6
        # the env-side resolver: direct-scoped, left-only, strict parsing, and
        # since phase 3 a **direct default** with `+0.08` as its documented restore
        os.environ.pop("FRUIT_LIFT_DZ", None)
        got, defaulted = resolve_lift_dz("direct", None)
        check(got == {"left": -0.08} and defaulted is True,
              "the direct default is the 0.20 m rung (dz=-0.08), and it says so")
        check(LIFT_DZ_DIRECT_DEFAULT == -0.08 and LIFT_DZ_HAND_ADD == 0.08,
              "the two constants are the 0.20 m rung and the hand's own add")
        for other in ("handoff", "scripted", "two_line", ""):
            check(resolve_lift_dz(other, None) == (None, False),
                  f"`{other or 'empty'}` is inert even with the default (direct-scoped)")
            check(resolve_lift_dz(other, "-0.08") == (None, False),
                  f"`{other or 'empty'}` is inert even with a value (direct-scoped)")
        check(resolve_lift_dz("direct", "") == ({"left": 0.08}, False),
              "an empty value is the explicit restore of the shipped height")
        check(resolve_lift_dz("direct", "+0.08") == ({"left": 0.08}, False),
              "= +0.08 is the documented restore, and it is `explicit`")
        check(resolve_lift_dz("direct", "-0.04") == ({"left": -0.04}, False),
              "= -0.04 arms the 0.24 m rung explicitly")
        check(resolve_lift_dz("direct", "-0.08") == ({"left": -0.08}, False),
              "= -0.08 on `direct` arms the LEFT arm at the default's value")
        check(resolve_lift_dz("direct", "0.00") == ({"left": 0.0}, False),
              "= 0.00 arms the middle rung (a distinct arm, 0.28 m)")
        check(resolve_lift_dz("direct", " -0.08 ") == ({"left": -0.08}, False),
              "surrounding whitespace is stripped")
        for bad in ("abc", "1,0", "nan", "inf", "-inf"):
            try:
                resolve_lift_dz("direct", bad)
            except ValueError:
                check(True, f"{bad!r} is a hard error (not a silent shipped run)")
            else:
                check(False, f"{bad!r} was accepted")
        # the env wires it the P64 way: resolved once, one construction site, one row
        check("self._lift_dz, self._lift_dz_defaulted = resolve_lift_dz(" in env_src,
              "the env resolves both the offset and its origin once in __init__")
        check(env_src.count("lift_dz=self._lift_dz,") == 1,
              "it is passed to PickAndPlaceTask at the one construction site")
        check(env_src.count('os.environ.get("FRUIT_LIFT_DZ")') == 1,
              "the env var is read exactly once (the resolver call site)")
        check('"lift_dz": (' in env_src,
              "the manifest records the run's rung (a lifted arm is a scenario)")
        for field in (
            '"defaulted": bool(self._lift_dz_defaulted)',
            '"target_m_above_belt": 0.28',
            '"default_dz_m_above_0p28": LIFT_DZ_DIRECT_DEFAULT',
            '"default_target_m_above_belt": 0.28 + LIFT_DZ_DIRECT_DEFAULT',
            '"hand_target_m_above_belt": 0.28',
            '"left": float(self._lift_dz.get("left", 0.0)),',
            '"right": "shipped",',
        ):
            check(field in env_src, f"the manifest carries {field.split(':')[0]}")
        check("shipped_target_m_above_belt" not in env_src,
              "the P43 defect is closed: no field claims the shipped height is the run's")

        # ---------------------------------------------------------------- 7
        # the application site: `jaw_target`'s grasp_lift branch (the pose builder),
        # which the dynamic catch's pad-x/y goal inherits through goal[2]
        body = src[src.index("    def jaw_target("):src.index("    def _goto(")]
        check("if name == \"grasp_lift\":" in body, "the site is jaw_target's grasp_lift branch")
        check("_lift_dz = lift_dz_for(self._lift_dz, side, name)" in body,
              "the branch resolves the caller-owned offset")
        check("if _lift_dz is not None:\n                z += _lift_dz" in body,
              "the armed offset replaces the hand's clearance add (the registered ladder)")
        check("elif getattr(self.grippers.get(side), \"kind\", \"\") == \"openarm\":" in body,
              "unset falls through to the shipped openarm add byte-for-byte")
        check("return np.array([cfg.pick_x, cfg.pick_y + sign * 0.05, z])" in body,
              "one return: the shipped x/y and the (possibly moved) z")
        dyn = src.index("goal = np.array([float(pad[0]), float(pad[1]), float(goal[2])])")
        check(dyn > src.index("def jaw_target("),
              "the dynamic catch's goal keeps the yaw_target z (so it inherits the rung)")
        check("float(goal[2]) + _lift_dz" not in src,
              "no second application site (one knob, one pose builder)")

        # ---------------------------------------------------------------- 8
        # the printed row: the offset **and its origin**, both heights, the
        # default and the restore - rebuilt from jaw_target's own numbers
        os.environ.pop("FRUIT_OPENARM_TRANSFER_LIFT", None)
        row = SortingRLEnv._lift_dz_row({"left": -0.08}, 1.01, True)
        check("[grasp] lift_dz:" in row and "dz=-0.0800(default)" in row,
              "the row names the resolved offset and that it is the default")
        check("-> 1.2100 m above floor" in row and "belt_top 1.0100 + 0.2000" in row,
              "the row prints the height the lift ends at (belt_top + 0.20)")
        check("default dz=-0.0800 = 0.2000 m" in row,
              "the row names the presentation's default rung")
        check("restore the shipped 1.3700 m with FRUIT_LIFT_DZ=+0.0800" in row,
              "the row names the documented restore and its height")
        check("arm=left leg=grasp_lift" in row and "right=shipped" in row
              and "place legs=shipped" in row,
              "the row names the scope (left lift only)")
        row_e = SortingRLEnv._lift_dz_row({"left": 0.08}, 1.01, False)
        check("dz=+0.0800(explicit)" in row_e and "-> 1.3700 m above floor" in row_e,
              "the explicit restore reads (explicit) at the shipped height")
        row1 = SortingRLEnv._lift_dz_row({"left": 0.00}, 1.01, False)
        check("-> 1.2900 m above floor" in row1,
              "the middle rung is belt_top + 0.28 (the phase-2 L1)")
        row24 = SortingRLEnv._lift_dz_row({"left": -0.04}, 1.01, False)
        check("-> 1.2500 m above floor" in row24,
              "the phase-3 candidate rung is belt_top + 0.24")
        check('if self._lift_dz is not None:' in env_src,
              "the row prints for every direct run (the flip) and never elsewhere")

        # ---------------------------------------------------------------- 9
        # the scripted line cannot reach either half
        for rel in (
            "scripts/20_pick_place.py",
            "scripts/40_collect_demos.py",
            "scripts/60_eval_policy.py",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            check("SortingRLEnv" not in text,
                  f"{rel} never constructs SortingRLEnv (the knob's scope)")
        check("PickAndPlaceTask(" in (ROOT / "scripts/40_collect_demos.py").read_text(
            encoding="utf-8") and "lift_dz" not in (ROOT / "scripts/40_collect_demos.py").read_text(
            encoding="utf-8"),
            "the collector constructs the task without the kwarg (default None)")
    finally:
        os.environ.clear()
        os.environ.update(saved)

    print("PASS: P66 lift-end instrument + lift-height knob")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
