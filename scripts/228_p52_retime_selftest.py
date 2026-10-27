"""Offline selftest of the P52 phase-2 action time-scale and its contact gate.

    python3 scripts/228_p52_retime_selftest.py

No simulator. The **real** `retime_action` / `retime_contact` /
`resolve_time_scale` from `src/fruit_sorting/rl_env.py` run here (the `224` /
`225` / `198` pattern), so what is pinned is the code the runs use, not a copy
of it; the env-side wiring (which branch `act` takes, what `proprio` caches,
what the manifest records) is pinned by AST and by textual anchors, because
constructing `SortingRLEnv` needs Isaac.

What this pins, and why each row matters:

1. **`s == 1.0` is the shipped action, exactly.** `np.array_equal` over random
   9-D chunks (and a chunk seeded with `-0.0` and repeated waypoints) for every
   executed index: the returned row is `chunk[index]`, not an interpolation
   that happens to be close. The direct loop conditions on rendered frames and
   is **not** bit-reproducible (AGENTS.md section 3b), so no run can prove this
   - the algebra is the proof, and this is the algebra.
2. **The rate is real.** At `s` the executed path advances `s*(steps-1)`
   waypoints over `steps` ticks, so the sampled path positions are
   `0, s, 2s, ...`; the test asserts those indices and that the arc length of
   the sampled polyline is `s` times the `s = 1` one on a straight-line chunk.
   A `s` that silently did nothing would read as a null result, so it is pinned.
3. **Nothing is extrapolated.** Past the last waypoint the return is that
   waypoint (a terminal hold), never a linear extension of the final segment.
4. **The finger channels are interpolated by the same `i`** (channels 7 and 8),
   so the close ramp is re-timed with the arm and cannot drift out of step.
5. **The gate is the conservative union of the two already-sampled channels** -
   force `> threshold` (strict, so an exactly-1.0 N read is not contact) or
   finger `< threshold` - and it is `False` on an open, unloaded hand. The
   full truth table, including the two boundaries.
6. **The resolver refuses everything it does not register**: `1.0` when unset
   or empty, the value when given, a hard error for a slow-down, a zero, a
   negative, an `inf`/`nan` and a non-number (a silently ignored typo would be
   published as a null result).
7. **The wiring**: `act` keeps the shipped `action = arr[index]` statement as
   the `_retime_on` else-branch (so the default never reaches the
   interpolation), `_apply` carries no retime code at all (the re-timing is in
   the chunk lookup, not in the command path), the gate's two channels are
   cached in `proprio()` (no extra sensor read in the control loop), the
   per-episode `[retime]` row and the manifest's `retime` block exist behind
   `_retime_on`, and the constructor's scope guards (direct only, RTC refused,
   `s * execute_steps <= action_horizon`) are present.

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
    resolve_time_scale,
    retime_action,
    retime_contact,
)

SOURCE = os.path.join(ROOT, "src", "fruit_sorting", "rl_env.py")
checks = 0


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
# 1. s == 1.0 is the shipped action, exactly
# --------------------------------------------------------------------------- #
def test_identity() -> None:
    rng = np.random.default_rng(2026)
    print("[1] retime_action at s=1.0 is chunk[index] exactly")
    for trial in range(24):
        horizon = int(rng.integers(2, 20))
        chunk = rng.normal(0.0, 0.4, size=(horizon, 9)).astype(np.float32)
        # poison a few values that a naive lerp would move: signed zeros,
        # repeated waypoints, an exactly representable dyadic.
        chunk[0, :] = -0.0
        if horizon > 3:
            chunk[2, :] = chunk[1, :]
        chunk[-1, 7] = 0.044
        for index in range(min(4, horizon)):
            got = retime_action(chunk, index, 1.0)
            want = np.asarray(chunk)[index]
            ok(
                f"identity trial {trial} index {index}",
                np.array_equal(got, want.astype(np.float64)),
                f"{got[:2]} vs {want[:2]}",
            )
            # the shipped expression, computed the way `act` computes it
            ok(
                f"identity trial {trial} index {index} is arr[index]",
                np.array_equal(np.asarray(got, dtype=np.float64), np.asarray(chunk[index], dtype=np.float64)),
            )


# --------------------------------------------------------------------------- #
# 2. the rate is real
# --------------------------------------------------------------------------- #
def test_rate() -> None:
    print("[2] the executed path advances s waypoints per tick")
    steps = 4
    ramp = np.zeros((16, 9), dtype=np.float64)
    ramp[:, :7] = np.arange(16, dtype=np.float64)[:, None] * 0.01
    for scale in (1.0, 1.25, 1.5, 2.0):
        rows = [retime_action(ramp, i, scale) for i in range(steps)]
        # a straight-line chunk: the joint value is proportional to the path
        # position, so the first joint reads back `i * 0.01` exactly.
        positions = [float(row[0]) / 0.01 for row in rows]
        want = [scale * i for i in range(steps)]
        ok(
            f"s={scale}: sampled path positions",
            np.allclose(positions, want, atol=1e-9),
            f"{positions} vs {want}",
        )
        # arc length of the sampled polyline: (steps - 1) intervals x scale
        arc = float(np.sum(np.abs(np.diff(np.asarray(positions)))))
        ok(
            f"s={scale}: arc length is s*(steps-1) waypoints",
            abs(arc - scale * (steps - 1)) < 1e-9,
            f"{arc:.6f}",
        )


# --------------------------------------------------------------------------- #
# 3. no extrapolation past the last waypoint
# --------------------------------------------------------------------------- #
def test_terminal_hold() -> None:
    print("[3] past the last waypoint the chunk holds its final value")
    ramp = np.zeros((5, 9), dtype=np.float64)
    ramp[:, 0] = np.arange(5, dtype=np.float64)
    for index, scale in ((1, 4.0), (3, 1.5), (10, 1.0)):
        got = retime_action(ramp, index, scale)
        ok(
            f"index={index} s={scale} holds the last waypoint",
            float(got[0]) == 4.0,
            f"{float(got[0])}",
        )
    one = np.arange(9, dtype=np.float64)[None, :]
    ok(
        "a single-waypoint chunk returns that waypoint",
        np.array_equal(retime_action(one, 7, 2.0), one[0]),
    )
    raises(lambda: retime_action(np.zeros((0, 9)), 0, 1.5), "an empty chunk")


# --------------------------------------------------------------------------- #
# 4. the finger channels ride the same i
# --------------------------------------------------------------------------- #
def test_finger() -> None:
    print("[4] the finger channels (7 and 8) are interpolated by the same i")
    chunk = np.zeros((16, 9), dtype=np.float64)
    chunk[:, 7] = np.linspace(0.0, 0.044, 16)
    chunk[:, 8] = chunk[:, 7]
    got = retime_action(chunk, 1, 1.5)
    want = 0.044 * 1.5 / 15.0
    ok("finger at i=1.5", abs(float(got[7]) - want) < 1e-12, f"{float(got[7])}")
    ok("the record channel mirrors it", float(got[8]) == float(got[7]))
    ok(
        "the arm channels are untouched by the finger value",
        float(np.max(np.abs(got[:7]))) == 0.0,
    )


# --------------------------------------------------------------------------- #
# 5. the gate's truth table
# --------------------------------------------------------------------------- #
def test_gate() -> None:
    print("[5] retime_contact: the conservative union of force and finger state")
    f_th, o_th = 1.0, 0.030
    table = [
        # force, finger, expected
        (0.00, 0.044, False),   # open, unloaded -> free space, the scale applies
        (0.00, 0.030, False),   # exactly at the open threshold: not closed yet
        (0.00, 0.029, True),    # below it -> not free space
        (1.00, 0.044, False),   # exactly at the force threshold: strict `>`
        (1.01, 0.044, True),    # loaded
        (12.0, 0.044, True),    # a crushed grip
        (12.0, 0.000, True),    # both channels agree
    ]
    for force, finger, expected in table:
        got = retime_contact(force, finger, f_th, o_th)
        ok(
            f"force={force} finger={finger} -> {expected}",
            got is expected,
            f"got {got}",
        )


# --------------------------------------------------------------------------- #
# 6. the resolver
# --------------------------------------------------------------------------- #
def test_resolver() -> None:
    print("[6] resolve_time_scale: only s >= 1 is registered")
    ok("unset -> 1.0", resolve_time_scale(None) == 1.0)
    ok("empty -> 1.0", resolve_time_scale("") == 1.0)
    ok("whitespace -> 1.0", resolve_time_scale("   ") == 1.0)
    ok("'1' -> 1.0", resolve_time_scale("1") == 1.0)
    ok("'1.25' -> 1.25", resolve_time_scale("1.25") == 1.25)
    ok("'1.5' -> 1.5", resolve_time_scale(" 1.5 ") == 1.5)
    ok("'2.0' -> 2.0", resolve_time_scale("2.0") == 2.0)
    for bad in ("0.5", "0", "0.0", "-1", "-1.5"):
        raises(lambda b=bad: resolve_time_scale(b), f"a slow-down {bad!r}")
    for bad in ("inf", "-inf", "nan"):
        raises(lambda b=bad: resolve_time_scale(b), f"a non-finite {bad!r}")
    raises(lambda: resolve_time_scale("fast"), "a non-number")


# --------------------------------------------------------------------------- #
# 7. the env wiring
# --------------------------------------------------------------------------- #
def test_wiring() -> None:
    print("[7] the env wiring (AST + the shipped anchors)")
    text = open(SOURCE, encoding="utf-8").read()
    tree = ast.parse(text)

    # the shipped chunk lookup survives as the retime-off branch
    ok(
        "act keeps `action = arr[index]`",
        "                    else:\n"
        "                        action = arr[index]\n" in text,
    )
    ok(
        "act routes through the gate helper",
        "action = self._retime_step(arr, index)" in text,
    )
    ok(
        "the chunk lookup is the only retime site in act",
        text.count("self._retime_step(arr, index)") == 1,
    )

    # `_apply` carries no retime code: the re-timing is a chunk lookup, not a
    # command-path shaper (so a future reader cannot move it by accident).
    apply_fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_apply"
    )
    apply_src = ast.get_source_segment(text, apply_fn) or ""
    ok("_apply is retime-free", "retime" not in apply_src)
    ok(
        "_apply still writes the 7 arm targets + the clipped finger",
        "set_dof_position_targets" in apply_src and "np.clip(action[7], 0.0, 0.044)" in apply_src,
    )

    # the gate's channels are cached in proprio() (no new sensor read)
    proprio_fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "proprio"
    )
    proprio_src = ast.get_source_segment(text, proprio_fn) or ""
    ok(
        "proprio caches the force and the finger opening",
        "self._retime_force_live = " in proprio_src
        and "self._retime_finger_live = finger" in proprio_src,
    )
    ok(
        "the cache sits behind the knob",
        "if self._retime_on:" in proprio_src,
    )
    ok(
        "the gate reads no sensor itself",
        "tactile" not in (ast.get_source_segment(text, next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_retime_step"
        )) or ""),
    )

    # the per-episode row and the manifest block
    finalize_src = ast.get_source_segment(text, next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_finalize"
    )) or ""
    ok("_finalize prints the [retime] summary behind the knob",
       "if self._retime_on:" in finalize_src and "self._retime_row()" in finalize_src)
    manifest_src = ast.get_source_segment(text, next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_build_manifest"
    )) or ""
    ok("the manifest records the retime block",
       '"retime": (' in manifest_src and 'if self._retime_on' in manifest_src)

    # the constructor's guards
    ok(
        "the scope guard refuses every other presentation",
        "are only \"\n                    f\"defined for presentation='direct'" in text,
    )
    ok("RTC is refused", "the action time-scale needs a chunk from `act`" in text)
    ok(
        "the horizon guard exists",
        "exceeds the chunk's \"\n                    f\"action_horizon=" in text,
    )
    ok(
        "the env banner names the armed state",
        'f"[rl] retime: scale={self._time_scale:.2f} "' in text,
    )
    # every read of the runtime knob is behind `_retime_on` or in the resolver
    ok(
        "the knob is resolved once",
        text.count('os.environ.get("FRUIT_POLICY_TIME_SCALE")') == 1,
    )
    ok(
        "the gate flag is read once",
        text.count('os.environ.get("FRUIT_POLICY_RETIME_GATE", "0")') == 1,
    )


def main() -> int:
    print("P52 phase 2: the contact-gated action time-scale (offline)")
    test_identity()
    test_rate()
    test_terminal_hold()
    test_finger()
    test_gate()
    test_resolver()
    test_wiring()
    print(f"\nPASS: {checks} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
