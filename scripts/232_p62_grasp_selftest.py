#!/usr/bin/env python3
"""P62 grasp-attitude selftest (offline; a `scripts/selfcheck.sh` leg).

Pins the **left-only, direct-scoped grasp attitude override**
(`FRUIT_GRASP_LEFT_TOPDOWN`, default **off**) that P62 phase 2 measures:

1. the resolver is **off by default** (`None`), an explicit `=1` on the direct
   presentation returns `{"left": T0}`, and every other combination (unset, `=0`,
   `handoff`) returns `None` - so the scripted line, the collector, the two-line
   scheduler and the hybrid canary cannot see it;
2. `PickAndPlaceTask._grasp_quat` is **honoured per arm**: the overridden side
   returns the override, the other side returns the file's value, and an empty
   override returns the file exactly (the `None` = shipped contract). The real
   method body is executed (extracted with `ast`, so no `pxr`/Isaac import);
3. the shipped quaternion is **untouched on every other path**: the file branch
   survives in `_grasp_quat`, the env read defaults to `"0"`, the caller-owned
   kwarg is the only channel (no `os.environ` write, no `configs/` edit),
   `rl_env` passes it at the single construction site, and the scripted entry
   point never constructs this env;
4. the **P62 finding** is pinned as a property of the tree, because it decides
   whether the knob can move anything: the file the direct env actually loads
   (`configs/waypoints.json`, since `FRUIT_WAYPOINTS` is unset everywhere)
   already carries **T0 for both arms**, and the never-stop catch's own installed
   hold (`mirror_across_xz(top_down_quaternion("x"))`, `tasks._run_impl`)
   **is** that same left value. `configs/waypoints_oriented.json` - the file
   `logs/p62/CANDIDATES.md` analysed - is **not** the attitude this env runs and
   is byte-untouched;
5. the `[grasp]` row names the override, the file's value and the dynamic hold,
   and is printed **only when armed** (so every knob-off log is unchanged).

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import ast
import hashlib
import json
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


def tool_axis(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    n = (w * w + x * x + y * y + z * z) ** 0.5
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)])


def load_grasp_quat_method():
    """Compile `PickAndPlaceTask._grasp_quat` from source (it imports pxr)."""
    src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    node = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_grasp_quat"
    )
    ns: dict = {"np": np}
    code = compile(
        ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
        "<_grasp_quat>",
        "exec",
    )
    exec(code, ns)  # noqa: S102 - a pinned, self-owned source file
    return ns["_grasp_quat"], src


def main() -> int:
    from fruit_sorting.motion import mirror_across_xz, top_down_quaternion
    from fruit_sorting.rl_env import (
        GRASP_LEFT_TOPDOWN,
        SortingRLEnv,
        resolve_grasp_quat_override,
    )

    saved = dict(os.environ)
    try:
        # ---------------------------------------------------------------- 1
        os.environ.pop("FRUIT_GRASP_LEFT_TOPDOWN", None)
        check(resolve_grasp_quat_override("direct", None) is None,
              "the knob is off by default (unset -> None, the shipped path)")
        check(resolve_grasp_quat_override("direct", "0") is None,
              "an explicit =0 is the shipped path")
        os.environ["FRUIT_GRASP_LEFT_TOPDOWN"] = "1"
        direct = resolve_grasp_quat_override(
            "direct", os.environ.get("FRUIT_GRASP_LEFT_TOPDOWN")
        )
        check(direct is not None and set(direct) == {"left"},
              "=1 on `direct` arms the LEFT arm only")
        check(np.allclose(direct["left"], np.asarray(GRASP_LEFT_TOPDOWN)),
              "the armed override is the registered T0 quaternion")
        check(resolve_grasp_quat_override("handoff", "1") is None,
              "=1 on `handoff` is inert (direct-scoped, so the canary keeps the file)")
        check(abs(np.linalg.norm(np.asarray(GRASP_LEFT_TOPDOWN)) - 1.0) < 1e-9,
              "T0 is a unit quaternion")
        axis = tool_axis(GRASP_LEFT_TOPDOWN)
        check(float(np.max(np.abs(axis - np.array([0.0, 0.0, -1.0])))) < 1e-9
              and abs(float(-axis[1])) < 1e-9,
              "T0's tool axis is (0,0,-1): the belt's -y drag has projection 0.000")

        # ---------------------------------------------------------------- 2
        grasp_quat, tasks_src = load_grasp_quat_method()
        oriented = json.loads(
            (ROOT / "configs/waypoints_oriented.json").read_text(encoding="utf-8")
        )
        shipped = json.loads(
            (ROOT / "configs/waypoints.json").read_text(encoding="utf-8")
        )
        # 2a: None = the file, on both arms, exactly.
        fake = SimpleNamespace(waypoints=oriented, _grasp_quat_override={})
        check(np.array_equal(grasp_quat(fake, "left"), np.asarray(
            oriented["grasp_quaternion"]["left"], dtype=float)),
            "empty override -> the file's left value, exactly (None = shipped)")
        check(np.array_equal(grasp_quat(fake, "right"), np.asarray(
            oriented["grasp_quaternion"]["right"], dtype=float)),
            "empty override -> the file's right value, exactly")
        # 2b: the override is honoured per arm and only for that arm.
        t0 = np.asarray(GRASP_LEFT_TOPDOWN, dtype=float)
        fake = SimpleNamespace(waypoints=oriented, _grasp_quat_override={"left": t0})
        check(np.array_equal(grasp_quat(fake, "left"), t0),
              "the overridden arm returns the override")
        check(np.array_equal(grasp_quat(fake, "right"), np.asarray(
            oriented["grasp_quaternion"]["right"], dtype=float)),
              "the un-named arm still returns the file (per-arm, not global)")
        # 2c: an override for a file arm is not required to exist in the file.
        fake = SimpleNamespace(waypoints={}, _grasp_quat_override={"left": t0})
        check(np.array_equal(grasp_quat(fake, "left"), t0),
              "an override wins even when the file has no entry")
        check(grasp_quat(fake, "right") is None,
              "an arm with neither override nor file entry is still None")
        fake = SimpleNamespace(waypoints=oriented, _grasp_quat_override={"left": t0})
        out = grasp_quat(fake, "left")
        out[0] = 9.0
        check(np.allclose(grasp_quat(fake, "left"), t0),
              "the returned array is a copy (a caller cannot corrupt the override)")

        # ---------------------------------------------------------------- 3
        check("grasp_quat_override: dict | None = None" in tasks_src,
              "PickAndPlaceTask takes grasp_quat_override (None = the file)")
        check("self._grasp_quat_override.get(side)" in tasks_src,
              "the override is the only new branch in _grasp_quat")
        check('(self.waypoints.get("grasp_quaternion") or {}).get(side)' in tasks_src,
              "the shipped file branch survives under it")
        env_src = (ROOT / "src/fruit_sorting/rl_env.py").read_text(encoding="utf-8")
        check('os.environ.get("FRUIT_GRASP_LEFT_TOPDOWN")' in env_src
              and 'os.environ.get("FRUIT_GRASP_LEFT_TOPDOWN", "0")' not in env_src,
              "the env var is read once, in the resolver (no default read elsewhere)")
        check("grasp_quat_override=self._grasp_quat_override," in env_src,
              "rl_env passes it at the construction site (the only channel)")
        check(env_src.count("grasp_quat_override=self._grasp_quat_override,") == 1,
              "exactly one construction site carries the kwarg")
        check("os.environ[\"FRUIT_GRASP_LEFT_TOPDOWN\"]" not in env_src,
              "the env is never written (no process-wide attitude switch)")
        entry = (ROOT / "scripts/20_pick_place.py").read_text(encoding="utf-8")
        check("SortingRLEnv" not in entry,
              "the scripted entry point never constructs the RL env")
        # the attitude is a config, and this phase does not edit it
        check(md5(ROOT / "configs/waypoints_oriented.json") ==
              "0ea08ebb6bdbd1e78a2402ca263ded01",
              "configs/waypoints_oriented.json is byte-untouched (0ea08ebb)")
        # the TASKS_MD5 provenance guard follows the shipped tasks.py
        env_pin = env_src.split('TASKS_MD5 = "', 1)[1].split('"', 1)[0]
        check(env_pin == md5(ROOT / "src/fruit_sorting/tasks.py"),
              f"TASKS_MD5 follows tasks.py ({env_pin[:8]})")

        # ---------------------------------------------------------------- 4
        hold_left = mirror_across_xz(top_down_quaternion("x"))
        hold_right = top_down_quaternion("x")
        file_left = np.asarray(shipped["grasp_quaternion"]["left"], dtype=float)
        file_right = np.asarray(shipped["grasp_quaternion"]["right"], dtype=float)
        check(float(np.max(np.abs(hold_left - file_left))) < 1e-9,
              "the dynamic catch's left hold IS configs/waypoints.json's left value")
        check(float(np.max(np.abs(hold_right - file_right))) < 1e-9,
              "the dynamic catch's right hold IS configs/waypoints.json's right value")
        check(float(np.max(np.abs(file_left - t0))) < 1e-6,
              "configs/waypoints.json's left value IS T0 (so the override equals it)")
        check(abs(float(-tool_axis(file_left)[1])) < 1e-9,
              "the file the direct env loads already has belt_proj 0.000 on the left")
        check(abs(float(-tool_axis(np.asarray(
            oriented["grasp_quaternion"]["left"], dtype=float))[1]) - 0.513236) < 1e-4,
              "configs/waypoints_oriented.json's left is the +0.513 file (NOT loaded "
              "by this env: FRUIT_WAYPOINTS is unset everywhere)")
        # P227m: the default follows the arm asset - the OpenArm's file when the
        # knob is unset on the OpenArm (the shipped path, byte for byte), and the
        # Panda's own calibrated file on `FRUIT_ARM_KIND=franka` (an OpenArm joint
        # vector teleported onto the Panda is a nonsense configuration).
        check('"FRUIT_WAYPOINTS", ""' in tasks_src
              and '"configs/waypoints_franka.json"' in tasks_src
              and 'if robot_kind() == "franka"' in tasks_src
              and '"configs/waypoints.json"' in tasks_src,
              "the task's default waypoint file follows the arm (OpenArm file when "
              "unset, waypoints_franka.json on the Panda)")

        # ---------------------------------------------------------------- 5
        row = SortingRLEnv._grasp_override_row(
            {"left": t0}, shipped, "x"
        )
        check(row.startswith("[grasp] left attitude override:"),
              "the armed row starts with the `[grasp]` tag F2 greps for")
        check("file_same=1" in row and "hold_same=1" in row,
              "the row reports file_same=1 and hold_same=1 on this tree")
        check("belt_proj=+0.0000" in row.split("|")[0],
              "the row prints the override's belt projection")
        check("right=file" in row,
              "the row prints the right arm (unchanged) too")
        row_o = SortingRLEnv._grasp_override_row(
            {"left": np.asarray(oriented["grasp_quaternion"]["left"], dtype=float)},
            shipped, "x",
        )
        check("file_same=0" in row_o and "hold_same=0" in row_o,
              "the row's equality flags actually discriminate (the oriented attitude)")
        check(env_src.count("say(\n                self._grasp_override_row") == 1
              and "if self._grasp_quat_override:" in env_src,
              "the row is printed only when the knob is armed (knob-off logs unchanged)")
    finally:
        os.environ.clear()
        os.environ.update(saved)

    print("PASS: P62 grasp attitude override")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
