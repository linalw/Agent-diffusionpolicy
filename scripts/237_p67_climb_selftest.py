#!/usr/bin/env python3
"""P67 selftest: the place-leg **climb** re-shape (a selfcheck leg).

P66 phase 4 closed gate (a) negative: on the 0.20 m lift rung the place transit
crosses the output rail's centreline at **+5 mm** against the **+33 mm** access
floor, and the rung ladder cannot buy it back because the crossing sits
**82.5 %** of the way along the leg's `y` span (`0.175:1` with the lift height).
The lever that is 1:1 with the crossing is the height the transit **starts** at,
so P67 prepends a short vertical climb at the place leg's start.

Pinned here (no simulator, no file writes):

1. **The knob** `FRUIT_LIFT_CLIMB` (metres, `direct` + left only, default
   **off**): `rl_env.resolve_lift_climb` is strict (a non-number, a non-finite
   and any value `<= 0` raise - the off state is *unset*, not `0`), resolves to
   `None` for every other presentation, and `None` means **no arithmetic at
   all** rather than "a climb of zero".
2. **The scope**: `tasks.lift_climb_for` returns `None` for `None`, an empty
   dict, an unnamed side and every leg but a `place*` one - so a `grasp_lift`
   leg's end pose (the P66 lever) cannot be touched by this knob.
3. **The insertion**: `_carry` keeps `transit_start = start` (the shipped
   expression, byte-identical) and only rebinds it when a climb is armed, and
   the climb's own commands come from `tasks.lift_climb_commands` - whose **last
   sample is exactly the waypoint** `start + climb*z_hat` (x/y unchanged on every
   sample, z monotone). The prepended list is concatenated in front of the
   shipped transit commands, so the leg's **end** pose - and therefore the
   release geometry - is unchanged.
4. **The arithmetic** the cell's climb is derived from: the crossing fraction
   `f = rail centreline / |place y|` (0.825 shipped, re-derived here from the
   scene config, cross-checked against `tasks._output_rail_y`), the
   `z_crossing = transfer - (1 - f) * (transfer - lift_end - climb)` identity, and
   the solved climb for a target crossing height (0.177 m for the +33 mm floor
   from P66's own measured pair, i.e. the cell's 0.18 m).
5. **The printed row** (`[grasp] lift_climb:`), its absence when the knob is
   unset, and the manifest block.
6. **The scripted line cannot reach it**: the collector constructs the task
   without the kwarg, and the three scripted entry scripts never construct
   `SortingRLEnv`.

Exit 0 on pass, 1 on the first failure.
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
    """True when `needle` (a character offset) lies in `header`'s indented body."""
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


def load_function(name: str, path: Path, extra: dict | None = None) -> tuple:
    """Compile one module-level function from source (tasks.py imports pxr)."""
    src = path.read_text(encoding="utf-8")
    node = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    ns: dict = {"np": np}
    if extra:
        ns.update(extra)
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
    from fruit_sorting.assets import SceneConfig
    from fruit_sorting.motion import TrajectoryLimits, jerk_limited
    from fruit_sorting.rl_env import SortingRLEnv, resolve_lift_climb

    saved = dict(os.environ)
    try:
        tasks_py = ROOT / "src/fruit_sorting/tasks.py"
        env_py = ROOT / "src/fruit_sorting/rl_env.py"
        climb_for, src = load_function("lift_climb_for", tasks_py)
        climb_cmd, _ = load_function(
            "lift_climb_commands", tasks_py, {"jerk_limited": jerk_limited}
        )
        env_src = env_py.read_text(encoding="utf-8")

        # ---------------------------------------------------------------- 1
        # the knob: direct + left only, default OFF (`None`, not a zero climb)
        check(resolve_lift_climb("direct", None) is None,
              "an unset FRUIT_LIFT_CLIMB is None (the shipped place leg)")
        check(resolve_lift_climb("direct", "") is None,
              "an empty value is the same shipped path (the explicit restore)")
        check(resolve_lift_climb("direct", "  ") is None,
              "whitespace only is the shipped path too")
        for other in ("handoff", "scripted", "two_line", ""):
            check(resolve_lift_climb(other, None) is None
                  and resolve_lift_climb(other, "0.18") is None,
                  f"`{other or 'empty'}` is inert even with a value (direct-scoped)")
        check(resolve_lift_climb("direct", "0.18") == {"left": 0.18},
              "the armed value resolves to the left arm in metres")
        check(resolve_lift_climb("direct", " 0.18 ") == {"left": 0.18},
              "surrounding whitespace is stripped")
        check(resolve_lift_climb("direct", "+0.18") == {"left": 0.18},
              "an explicit + sign parses")
        for bad in ("abc", "1,0", "nan", "inf", "-inf"):
            try:
                resolve_lift_climb("direct", bad)
            except ValueError:
                check(True, f"{bad!r} is a hard error (not a silent shipped run)")
            else:
                check(False, f"{bad!r} was accepted")
        for zero in ("0", "0.0", "-0.08"):
            try:
                resolve_lift_climb("direct", zero)
            except ValueError:
                check(True, f"{zero!r} raises (the off state is unset, not 0)")
            else:
                check(False, f"{zero!r} was accepted as a climb")

        # ---------------------------------------------------------------- 2
        # the scope: place legs only (the lift's own end pose is NOT this knob)
        check(climb_for(None, "left", "place0") is None,
              "None -> no arithmetic (the shipped command list)")
        check(climb_for({}, "left", "place0") is None,
              "an empty dict -> no arithmetic")
        check(climb_for({"left": 0.18}, "right", "place0") is None,
              "a side not named by the dict is untouched (per-arm)")
        for leg in ("grasp_lift", "grasp", "approach", "hub_place", ""):
            check(climb_for({"left": 0.18}, "left", leg) is None,
                  f"`{leg or 'empty'}` is out of scope (place legs only)")
        for leg in ("place0", "place1"):
            got = climb_for({"left": 0.18}, "left", leg)
            check(isinstance(got, float) and abs(got - 0.18) < 1e-12,
                  f"`{leg}` resolves to the climb in metres (a float)")
        check(src.count("lift_climb_for(") == 2,
              "lift_climb_for is the only resolver (its def + the one call site)")

        # ---------------------------------------------------------------- 3
        # the insertion: the waypoint's own z, x/y untouched, monotone
        lim = TrajectoryLimits.from_env(1.0 / 120.0)
        lim.v_max, lim.a_max = 0.35, 1.089  # the dynamic place caps
        lim = lim.limited_by_cone(np.array([0.0, 0.0, 1.0]), 0.6 * 1.0)
        start = np.array([0.30, 0.00, 1.370])
        for climb in (0.16, 0.18):
            cmd, vel, acc = climb_cmd(start, climb, lim)
            check(len(cmd) > 1, f"the {climb} m climb is a real segment ({len(cmd)} ticks)")
            check(np.allclose(cmd[0], start),
                  "the climb starts at the leg's start (the pads' position)")
            check(np.allclose(cmd[-1], start + np.array([0.0, 0.0, climb])),
                  "the climb's LAST sample is exactly the waypoint start + climb*z")
            check(float(np.abs(cmd[:, :2] - start[None, :2]).max()) == 0.0,
                  "the climb moves z only (x/y of the lift's end untouched)")
            check(bool(np.all(np.diff(cmd[:, 2]) >= 0.0)), "the climb's z is monotone")
            check(float(np.abs(vel).max()) <= lim.v_max + 1e-9
                  and float(np.abs(acc).max()) <= lim.a_max + 1e-9,
                  "the climb respects the place profile's v/a caps")
        # short climb -> fewer ticks (the cost is the distance, not a constant)
        n_short = len(climb_cmd(start, 0.02, lim)[0])
        n_long = len(climb_cmd(start, 0.18, lim)[0])
        check(n_short < n_long, "the tick cost grows with the climb")

        # `_carry`: shipped expression first, rebinding only when armed, and the
        # climb prepended (so the leg's end pose is the shipped one)
        body_start = src.index("    def _carry(")
        nxt = src.find("\n    def ", body_start + 10)
        body = src[body_start:nxt]
        check("_climb = lift_climb_for(self._lift_climb, side, name)" in body,
              "_carry resolves the caller-owned climb (the only application site)")
        check("climb_m = 0.0 if _climb is None else float(_climb)" in body,
              "None becomes 0.0, which is the no-climb gate's own value")
        check("transit_start = start\n" in body,
              "the shipped path starts from `start` (byte-identical expression)")
        check("if climb_m > 0.0:\n                transit_start = start + "
              "np.array([0.0, 0.0, climb_m])" in body,
              "only an armed climb rebinds the transit's start (z only)")
        check("delta = finish - transit_start" in body
              and "commands = transit_start[None, :] + positions[:, None] * "
              "direction[None, :]" in body,
              "the transit is built from transit_start (is `start` when off)")
        check("ccmd, cvel, cacc = lift_climb_commands(start, climb_m, climb_limits)"
              in body,
              "the climb segment is the pinned pure `lift_climb_commands`")
        check("commands = np.concatenate([ccmd, commands])" in body,
              "the climb is PREPENDED to the shipped transit commands")
        check("finish = np.asarray(goal, dtype=float)" in body
              and not any("climb" in ln for ln in body.splitlines()
                          if ln.strip().startswith("finish")),
              "the leg's target (`finish`) is untouched by the climb")
        check(body.count("np.concatenate(") == 3,
              "one concatenate site for commands/velocities/accelerations")
        check("and not (climb_m > 0.0)" in body,
              "the pad-hand slip rebase declines a two-segment command list")
        check('f"{climb_note}"' in body and 'else:\n                climb_note = ""' in body,
              "the motion label's climb note is empty when the knob is off")
        check("climb_m > 0.0" in body and body.index("climb_m > 0.0") <
              body.index("np.concatenate([ccmd, commands])"),
              "the prepend is gated (no concatenate on the shipped path)")

        # ---------------------------------------------------------------- 4
        # the arithmetic: f, the 0.175 leverage, and the solved climb
        cfg = SceneConfig()
        belt_top = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0
        check(abs(belt_top - 1.17) < 1e-12, "belt_top is 1.170 m (the P66 rows)")
        hand = float(os.environ.get("FRUIT_OPENARM_TRANSFER_LIFT", "0.08"))
        transfer = float(cfg.output_place_z) + hand
        check(abs(transfer - 1.53) < 1e-12,
              "the transfer pose is 1.530 m (output_place_z 1.45 + the hand's 0.08)")
        start_cls = load_function("_output_rail_y", tasks_py)[0]

        class _Fake:
            pass

        fake = _Fake()
        fake.cfg = cfg
        rail_inner, rail_centre = start_cls(fake)
        place_y = abs(float(cfg.output_belt_drop_points[0][1]))
        f = rail_centre / place_y
        check(abs(rail_centre - 0.4125) < 1e-12 and abs(place_y - 0.50) < 1e-12,
              "the crossing is 0.4125 m of a 0.50 m place span")
        check(abs(f - 0.825) < 1e-12,
              "f = 0.825 (the P66 phase-4 crossing fraction)")
        # z_crossing = transfer - (1 - f) * (transfer - lift_end - climb)
        lift_end = 1.370  # the 0.20 m rung, P66's L2 arm

        def z_cross(lift: float, climb: float) -> float:
            return transfer - (1.0 - f) * (transfer - lift - climb)

        z0 = z_cross(lift_end, 0.0)
        check(abs(z0 - 1.502) < 1e-3,
              "P66's L2 arm crosses at 1.502 m (its own derived number)")
        check(abs(z_cross(lift_end, 0.16) - transfer) < 1e-12,
              "a 0.16 m climb makes the transit level at the transfer (1.530 m)")
        z_lift = z_cross(1.530, 0.0)
        check(abs(z_lift - z_cross(lift_end, 0.16)) < 1e-12,
              "the climb is the SAME crossing height as the shipped lift "
              "(that is the re-shape's whole point)")
        check(abs((z_cross(lift_end, 0.02) - z0) / 0.02 - (1.0 - f)) < 1e-12,
              "the climb buys (1 - f) = 0.175 m per metre at the crossing")
        # solved for the +33 mm floor, from P66's measured pair (L2 +5 mm at
        # z 1.502, control +30 mm at 1.530 -> ~0.89 mm of clearance per mm of z)
        slope = (30.0 - 5.0) / ((1.530 - 0.0) - z0) / 1000.0
        z_need = z0 + (33.0 - 5.0) / 1000.0 / slope
        climb_need = (z_need - z0) / (1.0 - f)
        check(0.17 < climb_need < 0.19,
              f"the solved climb for +33 mm is {climb_need:.4f} m -> the cell's 0.18")
        check(abs(z_cross(lift_end, 0.18) - 1.5335) < 1e-4,
              "0.18 m puts the crossing at 1.5335 m (+31.5 mm over no climb)")
        check(abs(0.18 - climb_need) < 0.005,
              "the cell's 0.18 is the solved value rounded up (not tuned)")

        # ---------------------------------------------------------------- 5
        # the row: the resolved climb, the scope, both heights, the restore
        os.environ.pop("FRUIT_OPENARM_TRANSFER_LIFT", None)
        row = SortingRLEnv._lift_climb_row({"left": 0.18}, belt_top, cfg, {"left": -0.08})
        check("[grasp] lift_climb:" in row and "climb=+0.1800(explicit) m" in row,
              "the row names the resolved climb")
        check("arm=left" in row and "place0,place1" in row and "right" not in row,
              "the row names the scope (left place legs only)")
        check("lift end 1.3700 -> transit start 1.5500 m" in row,
              "the row prints the lift's end and the transit's start (1:1)")
        check("transfer 1.5300 m" in row, "the row prints the transfer pose")
        check("crossing |y|=0.4125 of the 0.5000 m span (f=0.825)" in row,
              "the row derives the crossing fraction from the scene config")
        check("z_crossing 1.5335 m (+31.5 mm vs no climb)" in row,
              "the row's crossing is the formula's own value")
        check("leaving FRUIT_LIFT_CLIMB unset" in row,
              "the row names the restore (unset = the shipped place leg)")
        # no row is printed when the knob is unset (the print site is gated)
        check("if self._lift_climb is not None:" in env_src,
              "the row prints only when the knob is armed (no default to report)")
        check(env_src.count('os.environ.get("FRUIT_LIFT_CLIMB")') == 1,
              "the env var is read exactly once (the resolver call site)")
        check("self._lift_climb = resolve_lift_climb(" in env_src,
              "the env resolves it once in __init__")
        check(env_src.count("lift_climb=self._lift_climb,") == 1,
              "it is passed to PickAndPlaceTask at the one construction site")
        check('"lift_climb": (' in env_src,
              "the manifest records the run's climb (a climbed leg is a scenario)")
        for field in (
            '"legs": "place0,place1"',
            '"climb_m": float(self._lift_climb.get("left", 0.0))',
        ):
            check(field in env_src, f"the manifest carries {field.split(':')[0]}")

        # ---------------------------------------------------------------- 6
        # the scripted line cannot reach it
        for rel in (
            "scripts/20_pick_place.py",
            "scripts/40_collect_demos.py",
            "scripts/60_eval_policy.py",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            check("SortingRLEnv" not in text,
                  f"{rel} never constructs SortingRLEnv (the knob's scope)")
        collector = (ROOT / "scripts/40_collect_demos.py").read_text(encoding="utf-8")
        check("PickAndPlaceTask(" in collector and "lift_climb" not in collector,
              "the collector constructs the task without the kwarg (default None)")
    finally:
        os.environ.clear()
        os.environ.update(saved)

    print("PASS: P67 place-leg climb (the re-shape of P66's rail-crossing gate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
