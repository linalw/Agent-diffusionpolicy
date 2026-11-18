#!/usr/bin/env python3
"""P208 self-test: a servo hand-back drops the stale policy chunk.

The measured defect (`logs/p207/C_s303.log`, t=996): after the place servo
declined, the next `[cmd]` row commands j1 -1.066 against measured +0.684 (1.75
rad) - the chunk was generated before the servo and sends the arm back to its
pre-place pose. The P207 rate cap turns that into a ~1 s sweep; it cannot remove
it. With `FRUIT_REPLAN_ON_SERVO_END=1` the hand-back sets a flag, `_apply` does
not write the stale target, and `act` breaks out so the next observation plans a
fresh chunk.

This leg is source-shape plus the resolver's strictness, no simulator:
  [1] the flag is off when unset and direct-only when armed
  [2] the servo ownership flags are initialised and reset per attempt
  [3] `_apply` marks the hand-back after a servo returns False, then returns
      before the A2C2 / tracking / joint-target path
  [4] `act` breaks on the flag and clears it
  [5] the shipped path (flag off) still reaches the joint write
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

CHECKS = {"passed": 0, "failed": 0}


def check(condition, message):
    if condition:
        CHECKS["passed"] += 1
        print(f"  ok: {message}")
    else:
        CHECKS["failed"] += 1
        print(f"  FAIL: {message}")


def source(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def main():
    print("P208: the servo hand-back discards the stale chunk")
    env = source("src", "fruit_sorting", "rl_env.py")

    print("[1] the knob")
    check('os.environ.get("FRUIT_REPLAN_ON_SERVO_END", "0").strip() == "1"' in env,
          "the knob is resolved once with the shipped off default")
    check("FRUIT_REPLAN_ON_SERVO_END is only defined for " in env,
          "the non-direct presentation is refused")

    print("[2] the per-attempt state")
    check(env.count("self._servo_contact_active = False") >= 2,
          "the contact ownership flag is initialised and reset")
    check(env.count("self._servo_place_active = False") >= 2,
          "the place ownership flag is initialised and reset")
    check(env.count("self._servo_handback = False") >= 2,
          "the hand-back flag is initialised and reset")

    print("[3] _apply")
    start = env.index("    def _apply(self, action")
    end = env.index("\n    def ", start + 10)
    apply = env[start:end]
    check("if self._servo_contact_active:" in apply
          and "self._servo_contact_active = False" in apply,
          "the contact hand-back is detected")
    check("if self._servo_place_active:" in apply
          and "self._servo_place_active = False" in apply,
          "the place hand-back is detected")
    check("if self._servo_handback:" in apply
          and "return" in apply[apply.index("if self._servo_handback:"):],
          "a hand-back returns before writing the stale target")
    hand = apply.index("if self._servo_handback:")
    a2c2 = apply.index("self._a2c2 is not None")
    check(hand < a2c2, "the hand-back sits before A2C2/tracking/joint shaping")
    check("self._rate_prev.pop(self._active, None)" in apply,
          "the rate limiter re-seeds on the servo hand-back")
    check("source=contact" in apply and "source=place" in apply,
          "each hand-back prints its source in a [replan] row")

    print("[4] act")
    act = env[env.index("    def act("):env.index("\n    def ", env.index("    def act(") + 10)]
    check("and self._servo_handback" in act
          or "or (self._replan_on_servo_end" in act,
          "the chunk loop breaks on the hand-back")
    check("self._servo_handback = False" in act,
          "the flag is cleared when the break is taken")
    check("executed = index + 1" in act,
          "the break reports the executed prefix")
    check("self._force_observe = True" in act,
          "the hand-back forces a fresh observation for the next chunk")
    check('self._step % 4 == 0 or getattr(self, "_force_observe", False)' in env,
          "sample_chunk observes on the forced flag, not only at the 4-tick phase")
    check("self._force_observe = False" in env,
          "the forced observation is one-shot")

    print("[5] the off path")
    # With the flag off, `_servo_handback` is never set; the joint path is
    # untouched and the rate limiter's own off path is unchanged.
    check("if self._replan_on_servo_end:" in apply,
          "the hand-back is gated on the knob")
    check('"FRUIT_POLICY_TARGET_RATE"' in env,
          "the P207 rate knob remains independent")

    failed = CHECKS["failed"]
    total = CHECKS["passed"] + failed
    print(f"\n{CHECKS['passed']}/{total} checks passed")
    if failed:
        print(f"FAIL: {failed} check(s)")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
