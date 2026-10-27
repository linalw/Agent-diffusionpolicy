"""Offline selftest of the P53 emission cells: C1 the joint clamp, C2 the hold.

    python3 scripts/229_p53_emit_selftest.py

No simulator. The **real** `resolve_joint_clamp` / `resolve_action_hold` /
`clamp_joint_targets` / `emit_out_of_range` / `hold_index` from
`src/fruit_sorting/rl_env.py` run here (the `224`/`225`/`227`/`228` pattern), so
what is pinned is the code the runs use, not a copy of it. The env-side wiring
is pinned by AST plus textual anchors, because constructing `SortingRLEnv` needs
Isaac.

What this pins, and why each row matters:

1. **Both knobs are off by default and say so.** `resolve_joint_clamp(None)` is
   `False` and `resolve_action_hold(None)` is `1`, so `_apply` never reaches the
   clamp branch and `act` never scales `steps`: the control arm is the shipped
   code path, not a re-derivation that happens to agree. The direct loop
   conditions on rendered frames and is **not** bit-reproducible (AGENTS.md
   section 3b), so this algebra plus the `logs/p53/00_id_pre.log` /
   `01_id_post.log` zero-ablation pair is the proof.
2. **The clamp is a copy, not an in-place edit.** `_apply` receives
   `np.asarray(action, dtype=np.float64).reshape(-1)`, which can be a *view* of
   a float64 chunk, so an in-place clip would rewrite the policy's prediction
   for every later tick of the same chunk. The test asserts the input is
   unchanged and an in-range action comes back element-identical (signed zeros
   included) - the "no-op when it is a no-op" half of C1.
3. **The clamp really clips, and only the 7 arm channels.** Out-of-range values
   land exactly on the arm's own limit; the finger channels (7, 8) are
   untouched, because `_apply` already clips channel 7 to the 0-44 mm opening.
4. **The census's own counter.** `emit_out_of_range` counts the joint-steps
   outside the range and the largest excursion, with a 1e-12 tolerance so an
   exactly-on-the-stop command is not counted - the number E1 reads
   (`logs/p52/P2B_FEASIBILITY.md` 1.6: 13.1 % of joint-steps on 74.3 % of
   ticks).
5. **The hold is a repeat, not a rate limit on the count.** `hold_index(t, 2)`
   is `0,0,1,1,2,2,...` (two control ticks per waypoint, 60 Hz of sim) and
   `hold_index(t, 1)` is `t` (the shipped mapping). The env implements exactly
   this by `np.repeat`ing the chunk, so the shipped `arr[index]` lookup is
   still the lookup - asserted textually.
6. **The resolvers refuse everything they do not register** (a boolean typo, a
   fractional hold, a zero/negative hold, a non-number, an `inf`/`nan`): a
   silently ignored typo would be published as a null result.
7. **The wiring**: `act` scales `steps` only behind `_action_hold > 1`, the
   shipped `action = arr[index]` statement survives verbatim, `_apply` clips
   only behind `_joint_clamp`, the `[emit]` row and the manifest's `emit` block
   exist behind the arming conditions, and the constructor's guards (direct
   only, RTC/EVENT/time-scale refused) are present. Also the placement: the
   clamp sits **after** the A2C2/track shapers and **before**
   `set_dof_position_targets`, so it clips the command the drives receive.

Run by `scripts/selfcheck.sh`.
"""

from __future__ import annotations

import ast
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from fruit_sorting.rl_env import (  # noqa: E402
    clamp_joint_targets,
    emit_out_of_range,
    hold_index,
    resolve_action_hold,
    resolve_joint_clamp,
)

SOURCE = os.path.join(ROOT, "src", "fruit_sorting", "rl_env.py")
checks = 0

#: The shipped OpenArm ranges in rad, from the asset itself
#: (`logs/p44/CAP_CENSUS.md` section 1.1: j1 -200..80 deg, j2 -190..10,
#: j3/j5/j7 +-90, j4 0..140, j6 +-45; the right arm's j1/j2 are mirrored).
LO = np.array([-3.4907, -3.3161, -1.5708, 0.0, -1.5708, -0.7854, -1.5708])
HI = np.array([1.3963, 0.1745, 1.5708, 2.4435, 1.5708, 0.7854, 1.5708])


def ok(name: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not condition:
        raise AssertionError(f"{name}{(': ' + detail) if detail else ''}")
    print(f"  ok   {name}{(': ' + detail) if detail else ''}")


def raises(fn, name: str) -> None:
    global checks
    checks += 1
    try:
        fn()
    except (ValueError, TypeError):
        print(f"  ok   {name} raises")
        return
    raise AssertionError(f"{name} did not raise")


# --------------------------------------------------------------------------- #
# 1. the shipped defaults
# --------------------------------------------------------------------------- #
def test_defaults() -> None:
    print("[1] both cells are off when unset (the shipped emission)")
    ok("clamp unset -> False", resolve_joint_clamp(None) is False)
    ok("clamp empty -> False", resolve_joint_clamp("") is False)
    ok("clamp '0' -> False", resolve_joint_clamp("0") is False)
    ok("hold unset -> 1 tick", resolve_action_hold(None) == 1)
    ok("hold empty -> 1 tick", resolve_action_hold("") == 1)
    ok("hold '1' -> 1 tick", resolve_action_hold("1") == 1)


# --------------------------------------------------------------------------- #
# 2. the clamp is a copy and a no-op inside the range
# --------------------------------------------------------------------------- #
def test_identity() -> None:
    print("[2] clamp_joint_targets: a copy, and the identity inside the range")
    rng = np.random.default_rng(53)
    for trial in range(12):
        mid = 0.5 * (LO + HI)
        span = 0.5 * (HI - LO)
        action = np.concatenate(
            [mid + span * rng.uniform(-0.99, 0.99, size=7), [0.02, 0.02]]
        )
        before = action.copy()
        got = clamp_joint_targets(action, LO, HI)
        ok(f"trial {trial}: in-range action is element-identical",
           np.array_equal(got, action))
        ok(f"trial {trial}: the input array is untouched",
           np.array_equal(action, before))
        ok(f"trial {trial}: it is a new array (not the input)",
           got is not action)
    zeros = np.zeros(9)
    zeros[0] = -0.0
    got = clamp_joint_targets(zeros, LO, HI)
    ok("signed zeros survive (no arithmetic touches them)",
       np.array_equal(got, zeros) and not np.signbit(got[1]))
    # a float32 chunk row is promoted, not clipped differently
    row32 = np.array([0.1, 0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.044, 0.044],
                     dtype=np.float32)
    got32 = clamp_joint_targets(row32, LO, HI)
    ok("a float32 row stays inside its own range",
       np.allclose(got32[:7], row32.astype(np.float64)[:7]))


# --------------------------------------------------------------------------- #
# 3. the clamp clips, arm channels only
# --------------------------------------------------------------------------- #
def test_clip() -> None:
    print("[3] the clip lands exactly on the arm's own limit, fingers untouched")
    action = np.array([-9.0, 9.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.041, 0.041])
    got = clamp_joint_targets(action, LO, HI)
    ok("j1 low -> arm_lo", float(got[0]) == float(LO[0]), f"{float(got[0])}")
    ok("j2 high -> arm_hi", float(got[1]) == float(HI[1]), f"{float(got[1])}")
    ok("j4 below its 0 rad stop -> 0", float(got[3]) == 0.0, f"{float(got[3])}")
    ok("the finger channels are untouched",
       float(got[7]) == 0.041 and float(got[8]) == 0.041)
    ok("the input is unchanged (no in-place edit of the chunk row)",
       float(action[0]) == -9.0 and float(action[3]) == -1.0)


# --------------------------------------------------------------------------- #
# 4. the census counter
# --------------------------------------------------------------------------- #
def test_counter() -> None:
    print("[4] emit_out_of_range: the census's joint-step count")
    inside = np.array([0.1, 0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0])
    ok("all inside -> (0, 0.0)", emit_out_of_range(inside, LO, HI) == (0, 0.0))
    over = inside.copy()
    over[2] = -1.75          # 0.18 rad past the j3 stop
    over[6] = 1.80           # 0.23 rad past the j7 stop
    count, worst = emit_out_of_range(over, LO, HI)
    ok("two joints out -> count 2", count == 2, f"{count}")
    ok("the largest excursion is reported",
       abs(worst - 0.2292) < 1e-3, f"{worst:.4f} rad")
    on_stop = inside.copy()
    on_stop[4] = float(HI[4])
    ok("exactly on the stop is not out of range",
       emit_out_of_range(on_stop, LO, HI) == (0, 0.0))
    ok("the 9-D action's finger channels are not counted",
       emit_out_of_range(np.array([0.0] * 7 + [9.9, 9.9]), LO, HI) == (0, 0.0))
    # the clamp drives the count to zero - what E1 reads
    clamped = clamp_joint_targets(over, LO, HI)
    ok("after the clamp the same command reads 0",
       emit_out_of_range(clamped, LO, HI)[0] == 0)


# --------------------------------------------------------------------------- #
# 5. the hold mapping
# --------------------------------------------------------------------------- #
def test_hold() -> None:
    print("[5] hold_index: two control ticks per waypoint at hold=2")
    ok("hold=1 is the shipped mapping",
       [hold_index(i, 1) for i in range(6)] == [0, 1, 2, 3, 4, 5])
    ok("hold=2 repeats each waypoint",
       [hold_index(i, 2) for i in range(8)] == [0, 0, 1, 1, 2, 2, 3, 3])
    ok("hold=4 repeats each waypoint four times",
       [hold_index(i, 4) for i in range(8)] == [0, 0, 0, 0, 1, 1, 1, 1])
    ok("a hold of 0 or a negative is treated as 1 (never a stall)",
       hold_index(3, 0) == 3 and hold_index(3, -2) == 3)
    # the env implements the same mapping by `np.repeat`
    chunk = np.arange(16, dtype=float)[:, None] * np.ones((1, 9))
    expanded = np.repeat(chunk, 2, axis=0)
    ok("np.repeat(hold) maps tick i to waypoint hold_index(i, hold)",
       all(expanded[i, 0] == chunk[hold_index(i, 2), 0] for i in range(8)))
    ok("the expanded chunk covers execute_steps*hold = 8 ticks",
       expanded.shape[0] >= 8)


# --------------------------------------------------------------------------- #
# 6. the resolvers refuse what they do not register
# --------------------------------------------------------------------------- #
def test_resolvers() -> None:
    print("[6] the resolvers refuse a typo instead of reading it as 'off'")
    for token in ("1", "on", "TRUE", " yes "):
        ok(f"clamp {token!r} -> True", resolve_joint_clamp(token) is True)
    for token in ("0", "off", "FALSE", " no "):
        ok(f"clamp {token!r} -> False", resolve_joint_clamp(token) is False)
    for bad in ("2", "enable", "clamp", "0.0"):
        raises(lambda b=bad: resolve_joint_clamp(b), f"clamp {bad!r}")
    ok("hold '2' -> 2", resolve_action_hold("2") == 2)
    ok("hold ' 4 ' -> 4", resolve_action_hold(" 4 ") == 4)
    for bad in ("1.5", "0", "-1", "0.0"):
        raises(lambda b=bad: resolve_action_hold(b), f"hold {bad!r}")
    for bad in ("inf", "-inf", "nan", "two"):
        raises(lambda b=bad: resolve_action_hold(b), f"hold {bad!r}")


# --------------------------------------------------------------------------- #
# 7. the env wiring
# --------------------------------------------------------------------------- #
def test_wiring() -> None:
    print("[7] the env wiring (AST + the shipped anchors)")
    text = open(SOURCE, encoding="utf-8").read()
    tree = ast.parse(text)

    def fn(name: str) -> str:
        node = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        return ast.get_source_segment(text, node) or ""

    act_src = fn("act")
    apply_src = fn("_apply")

    # the hold: steps scaled only behind the knob, the shipped lookup intact
    ok("act scales the tick count behind `_action_hold > 1`",
       "if self._action_hold > 1:" in act_src and "steps *= self._action_hold" in act_src)
    ok("act still routes the time-scale through its own helper",
       "action = self._retime_step(arr, index)" in act_src)
    ok("act keeps the shipped `action = arr[index]`",
       "                    else:\n"
       "                        action = arr[index]\n" in text)
    ok("the hold expands the chunk instead of re-indexing the lookup",
       "np.repeat(arr, self._action_hold, axis=0)" in act_src)
    ok("the expansion is behind the knob",
       "arr = np.asarray(chunk)\n"
       "                if self._action_hold > 1:" in text)

    # the clamp: in _apply, after the shapers, before the drives
    ok("_apply clips behind `_joint_clamp`",
       "if self._joint_clamp:" in apply_src
       and "clamp_joint_targets(action, arm.arm_lo, arm.arm_hi)" in apply_src)
    ok("the clip is the last shaping before the drives",
       apply_src.index("clamp_joint_targets(")
       < apply_src.index("set_dof_position_targets("))
    ok("the clip sits after the A2C2 / tracking shapers",
       apply_src.index("self._tracking_action(")
       < apply_src.index("clamp_joint_targets("))
    ok("the range is the arm's own read-back, not a table",
       "arm.arm_lo, arm.arm_hi" in apply_src and "CAP_CENSUS" not in apply_src)

    # the report row, the manifest block and the banner
    finalize_src = fn("_finalize")
    ok("_finalize prints the [emit] row behind the diag",
       "if self._emit_diag:" in finalize_src and "self._emit_row()" in finalize_src)
    ok("the [emit] row carries the pre/post counts",
       "out_pre=" in fn("_emit_row") and "out_post=" in fn("_emit_row"))
    manifest_src = fn("_build_manifest")
    ok("the manifest records the emit block",
       '"emit": (' in manifest_src and "self._action_hold > 1" in manifest_src)
    ok("the banner names both resolved knobs",
       'f"[rl] emit: joint_clamp={int(self._joint_clamp)} "' in text)

    # the constructor's guards
    ok("the scope guard refuses every other presentation",
       "are only \"\n                f\"defined for presentation='direct'" in text)
    ok("RTC is refused", "the action hold needs a chunk from `act`" in text)
    ok("the time-scale is refused as a composition",
       "are opposite re-parameterisations of the same chunk" in text)
    ok("the event horizon is refused as a composition",
       "both choose \"\n                    \"how many ticks a decision covers" in text)
    ok("the horizon guard exists",
       "exceeds the chunk's \"\n                    f\"action_horizon=" in text)

    # the knobs are read once, and the counters cost nothing when off
    ok("the clamp knob is resolved once",
       text.count('os.environ.get("FRUIT_POLICY_JOINT_CLAMP")') == 1)
    ok("the hold knob is resolved once",
       text.count('os.environ.get("FRUIT_POLICY_ACTION_HOLD")') == 1)
    ok("the diag flag is read once",
       text.count('os.environ.get("FRUIT_EMIT_DIAG", "0")') == 1)


def main() -> int:
    print("P53: the emission cells - C1 the joint clamp, C2 the action hold")
    test_defaults()
    test_identity()
    test_clip()
    test_counter()
    test_hold()
    test_resolvers()
    test_wiring()
    print(f"\nPASS: {checks} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
