#!/usr/bin/env python3
"""P64 pre-compensated left carry attitude selftest (offline; a selfcheck leg).

Pins the **direct + left only, default off** pre-compensation
(`FRUIT_GRASP_LEFT_PRECOMP`) that P64 phase 1 builds:

1. the resolver is **off by default** (`None`), an explicit `=1` on the direct
   presentation returns `{"left": q_cmd}`, and every other combination (unset,
   `=0`, `handoff`) returns `None` - so the scripted line, the collector, the
   two-line scheduler and the hybrid canary cannot see it;
2. the **composition** is the registered one: `q_cmd = q_drift^-1 (x) q_T0`,
   normalized, `[w, x, y, z]`, built from the measured axis/angle constants -
   and `q_drift (x) q_cmd == q_T0` (the world-frame residual model), which the
   other composition does **not** satisfy;
3. `None` = the **shipped path**: `tasks.carry_hold_override_for` (the real body,
   extracted with `ast`, so no `pxr`/Isaac import) returns `None` for `None`, an
   empty dict, a missing side and every leg but `grasp_lift`, and returns a
   **copy** for the armed side - so a knob-off task writes no hold at all;
4. the **scope**: the env var is read once (in the resolver, with no default
   read elsewhere), the kwarg is the only channel (no `os.environ` write, no
   `configs/` edit), `rl_env` passes it at its single construction site, the
   scripted entry point never constructs this env, and the hold write is the
   one guarded site in `_carry`;
5. the **row**: printed only when armed, names `q_cmd`, the axis, the angle, the
   command's belt projection (upstream) and the **computed** predicted achieved
   projection (0.0000 - the drift applied to the command);
6. the drift constant is the **measured** one: applying the inverse of the
   measured drift to the new command's tool axis reproduces `(0, 0, -1)`.

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import ast
import hashlib
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def qmat(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    n = (w * w + x * x + y * y + z * z) ** 0.5
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def qmul(a, b) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return np.array(
        [
            a[0] * b[0] - float(a[1:] @ b[1:]),
            *(a[0] * b[1:] + b[0] * a[1:] + np.cross(a[1:], b[1:])),
        ]
    )


def tool_axis(q) -> np.ndarray:
    return qmat(q)[:, 2]


def load_carry_hold_override_for():
    """Compile `carry_hold_override_for` from source (tasks.py imports pxr)."""
    src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")
    node = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == "carry_hold_override_for"
    )
    ns: dict = {"np": np}
    exec(  # noqa: S102 - a pinned, self-owned source file
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            "<carry_hold_override_for>",
            "exec",
        ),
        ns,
    )
    return ns["carry_hold_override_for"], src


def main() -> int:
    from fruit_sorting.rl_env import (
        GRASP_LEFT_PRECOMP,
        GRASP_LEFT_TOPDOWN,
        P64_LEFT_DRIFT_ANGLE_DEG,
        P64_LEFT_DRIFT_AXIS,
        SortingRLEnv,
        _quat_from_axis_angle,
        _quat_mul,
        left_precomp_quat,
        resolve_carry_hold_override,
    )

    saved = dict(os.environ)
    try:
        # ---------------------------------------------------------------- 1
        os.environ.pop("FRUIT_GRASP_LEFT_PRECOMP", None)
        check(resolve_carry_hold_override("direct", None) is None,
              "the knob is off by default (unset -> None, the shipped path)")
        check(resolve_carry_hold_override("direct", "0") is None,
              "an explicit =0 is the shipped path")
        os.environ["FRUIT_GRASP_LEFT_PRECOMP"] = "1"
        direct = resolve_carry_hold_override(
            "direct", os.environ.get("FRUIT_GRASP_LEFT_PRECOMP")
        )
        check(direct is not None and set(direct) == {"left"},
              "=1 on `direct` arms the LEFT arm only")
        check(np.allclose(direct["left"], np.asarray(GRASP_LEFT_PRECOMP)),
              "the armed override is the constant q_cmd")
        for other in ("handoff", "scripted", "two_line", ""):
            check(resolve_carry_hold_override(other, "1") is None,
                  f"=1 on `{other or 'empty'}` is inert (direct-scoped)")
        check(resolve_carry_hold_override("direct", "true") is None,
              "only the literal `1` arms it")

        # ---------------------------------------------------------------- 2
        q_cmd = np.asarray(GRASP_LEFT_PRECOMP, dtype=float)
        t0 = np.asarray(GRASP_LEFT_TOPDOWN, dtype=float)
        check(abs(float(np.linalg.norm(q_cmd)) - 1.0) < 1e-12,
              "q_cmd is a unit quaternion")
        q_drift = _quat_from_axis_angle(P64_LEFT_DRIFT_AXIS, P64_LEFT_DRIFT_ANGLE_DEG)
        check(abs(float(np.linalg.norm(q_drift)) - 1.0) < 1e-12,
              "q_drift is a unit quaternion (axis-angle)")
        check(np.allclose(q_cmd, left_precomp_quat(
            P64_LEFT_DRIFT_AXIS, P64_LEFT_DRIFT_ANGLE_DEG, GRASP_LEFT_TOPDOWN)),
            "the constant is left_precomp_quat(axis, angle, T0)")
        # the composition: conj(q_drift) (x) T0, NOT T0 (x) conj(q_drift)
        conj = np.array([q_drift[0], -q_drift[1], -q_drift[2], -q_drift[3]])
        registered = _quat_mul(conj, t0)
        registered = registered / float(np.linalg.norm(registered))
        check(float(np.max(np.abs(registered - q_cmd))) < 1e-12,
              "q_cmd == q_drift^-1 (x) q_T0 (left-multiplied, [w,x,y,z])")
        alt = _quat_mul(t0, conj)
        alt = alt / float(np.linalg.norm(alt))
        check(float(np.max(np.abs(alt - q_cmd))) > 0.1,
              "the tool-frame alternative q_T0 (x) q_drift^-1 is a different command")
        achieved = _quat_mul(q_drift, q_cmd)   # the world-frame residual model
        check(float(np.max(np.abs(achieved - t0))) < 1e-9,
              "q_drift (x) q_cmd == q_T0: the predicted achieved attitude is T0")
        check(abs(float(-tool_axis(achieved)[1])) < 1e-9,
              "the predicted achieved belt projection is 0.000")
        # the command itself is tilted upstream by ~the drift angle
        proj = float(-tool_axis(q_cmd)[1])
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, -float(tool_axis(q_cmd)[2])))))
        check(proj < -0.30 and abs(tilt - P64_LEFT_DRIFT_ANGLE_DEG) < 1e-6,
              f"the command is tilted ~{P64_LEFT_DRIFT_ANGLE_DEG:.2f} deg the other "
              f"way (proj {proj:+.4f})")
        # the drift is the *measured* one: applying q_drift to the command's tool
        # axis returns (0, 0, -1) (a rotation preserves the angle, so this is the
        # definition of the minimal rotation the constant was built from)
        back = qmat(q_drift) @ tool_axis(q_cmd)
        check(float(np.max(np.abs(back - np.array([0.0, 0.0, -1.0])))) < 1e-9,
              "q_drift maps the command's tool axis back to (0,0,-1)")
        check(25.0 < P64_LEFT_DRIFT_ANGLE_DEG < 29.0,
              "the drift constant sits inside the measured per-leg range 25.1..28.7")
        check(abs(float(np.linalg.norm(P64_LEFT_DRIFT_AXIS)) - 1.0) < 1e-9
              and abs(float(P64_LEFT_DRIFT_AXIS[2])) < 1e-12,
              "the drift axis is unit and in the belt plane (z = 0)")

        # ---------------------------------------------------------------- 3
        override_for, tasks_src = load_carry_hold_override_for()
        q = np.asarray(GRASP_LEFT_PRECOMP, dtype=float)
        check(override_for(None, "left", "grasp_lift") is None,
              "None -> no hold written (the shipped default)")
        check(override_for({}, "left", "grasp_lift") is None,
              "an empty override -> no hold written")
        check(override_for({"left": q}, "right", "grasp_lift") is None,
              "a side not named by the override gets no hold (per-arm)")
        for leg in ("place0", "place1", "approach", ""):
            check(override_for({"left": q}, "left", leg) is None,
                  f"`{leg or 'empty'}` is out of scope (grasp_lift only)")
        got = override_for({"left": q}, "left", "grasp_lift")
        check(got is not None and np.array_equal(got, q),
              "the armed left `grasp_lift` leg gets the pre-compensated hold")
        got[0] = 9.0
        check(np.allclose(override_for({"left": q}, "left", "grasp_lift"), q),
              "the returned hold is a copy (a caller cannot corrupt the override)")
        check("carry_hold_override: dict | None = None" in tasks_src,
              "PickAndPlaceTask takes carry_hold_override (None = shipped)")
        check(tasks_src.count("carry_hold_override_for(") == 2,
              "the resolver is defined once and called once (the `_carry` site)")
        check("_hold_override = carry_hold_override_for(self._carry_hold_override, side, name)" in tasks_src,
              "`_carry` resolves the override for its own side/leg")
        idx = tasks_src.index("_hold_override = carry_hold_override_for(")
        after = tasks_src[idx: idx + 400]
        check("if _hold_override is not None:\n            arm.hold_quaternion = _hold_override" in after,
              "the hold is written only when the override is not None")
        check(_carry_hold_override_is_not_grasp_quat(tasks_src),
              "the carry hold is a separate channel from `grasp_quat_override`")

        # ---------------------------------------------------------------- 4
        env_src = (ROOT / "src/fruit_sorting/rl_env.py").read_text(encoding="utf-8")
        check('os.environ.get("FRUIT_GRASP_LEFT_PRECOMP")' in env_src
              and 'os.environ.get("FRUIT_GRASP_LEFT_PRECOMP", "0")' not in env_src,
              "the env var is read once, in the resolver (no default read elsewhere)")
        check(env_src.count("carry_hold_override=self._carry_hold_override,") == 1,
              "rl_env passes it at its single construction site")
        check('os.environ["FRUIT_GRASP_LEFT_PRECOMP"]' not in env_src,
              "the env is never written (no process-wide attitude switch)")
        check("if self._carry_hold_override:" in env_src
              and env_src.count("self._precomp_row(self._carry_hold_override)") == 1,
              "the row is printed only when the knob is armed")
        entry = (ROOT / "scripts/20_pick_place.py").read_text(encoding="utf-8")
        check("SortingRLEnv" not in entry,
              "the scripted entry point never constructs the RL env")
        check('"carry_hold_precomp"' in env_src,
              "the manifest names the armed scenario (null = off)")
        # the constants and the config files this phase must not move
        check(md5(ROOT / "configs/waypoints.json") ==
              "d81c6f1ccad96254264b62331968716b",
              "configs/waypoints.json is byte-untouched (d81c6f1c)")
        check(md5(ROOT / "configs/waypoints_oriented.json") ==
              "0ea08ebb6bdbd1e78a2402ca263ded01",
              "configs/waypoints_oriented.json is byte-untouched (0ea08ebb)")
        # P85 (the flip): `configs/motion_reference.json` is now the shipped
        # (bimanual two-line) acceptance record - which is the two-line
        # scenario's own reference, so the two files legitimately carry the
        # same bytes; the pre-P85 single-arm record is archived
        # (`logs/p85/motion_reference_single_pre_p85.json`) and shipped as
        # `configs/motion_reference_single.json` for the `FRUIT_BIARM=0` restore.
        check(md5(ROOT / "configs/motion_reference.json") ==
              "eb697f23adb5d6b9ef8656f3319d3ce8"
              and md5(ROOT / "configs/motion_reference_twoline.json") ==
              "eb697f23adb5d6b9ef8656f3319d3ce8"
              and md5(ROOT / "configs/motion_reference_single.json") ==
              "8952c320d798ef42e03ba815c9e96b23",
              "the shipped acceptance reference is the two-line record "
              "(eb697f23), the single-arm restore keeps 8952c320")
        env_pin = env_src.split('TASKS_MD5 = "', 1)[1].split('"', 1)[0]
        check(env_pin == md5(ROOT / "src/fruit_sorting/tasks.py"),
              f"TASKS_MD5 follows tasks.py ({env_pin[:8]})")

        # ---------------------------------------------------------------- 5
        row = SortingRLEnv._precomp_row({"left": q})
        check(row.startswith("[grasp] left precomp:"),
              "the armed row starts with the `[grasp] left precomp:` tag")
        check("q_cmd=[+0.016754,-0.687859,+0.687859,+0.231126]" in row,
              "the row prints q_cmd in [w,x,y,z]")
        check("axis=(-0.756380,-0.654132,+0.000000)" in row
              and "angle=26.798deg" in row,
              "the row prints the measured drift axis and angle")
        check("cmd_belt_proj=-0.3410" in row,
              "the row prints the command's (upstream) belt projection")
        check("predicted_proj=+0.0000" in row,
              "the row prints the computed predicted achieved projection (0.0000)")
        check("right=shipped" in row and "leg=grasp_lift" in row,
              "the row names the scope (left `grasp_lift`, right shipped)")
        fake = SimpleNamespace(_carry_hold_override={})
        check(not fake._carry_hold_override,
              "an unarmed env has an empty override (nothing printed, nothing written)")
    finally:
        os.environ.clear()
        os.environ.update(saved)

    print("PASS: P64 left carry pre-compensation")
    return 0


def _carry_hold_override_is_not_grasp_quat(tasks_src: str) -> bool:
    """The carry hold never flows through `_grasp_quat` (P62 measured it inert)."""
    idx = tasks_src.index("def _grasp_quat(")
    body = tasks_src[idx: tasks_src.index("\n    def ", idx + 10)]
    return ("_carry_hold_override" not in body
            and "_grasp_quat_override.get(side)" in body)


if __name__ == "__main__":
    raise SystemExit(main())
