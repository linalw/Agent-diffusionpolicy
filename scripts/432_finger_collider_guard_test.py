"""Offline negative test for the openarm finger-collider guard.

    python3 scripts/432_finger_collider_guard_test.py

`FRUIT_GRIPPER_KIND=openarm` (the shipped default) holds the fruit only through
colliders authored onto the robot's own finger meshes. On a fresh checkout the
1.1 GB de-instanced asset (`assets/openarm_flat/openarm_flat_deinst.usda`, not in
git) is missing, the instanced fallback is selected instead, and its finger
subtree is an instance proxy the authoring API refuses - so before the P1 gate
the default silently ran the old "fruit floats" configuration. `scene.build` now
asserts on the verdict; this test pins the verdict -> exception decision without
a simulator, including the message naming the expected asset and both escapes.

The simulator path that *produces* the verdict is exercised with a short bad
run (see WORKLOG "P1 gate remediation"):

    FRUIT_SCENE_PARTS=robot FRUIT_ROBOT_USD=/nonexistent.usda \
      ATTEMPTS=1 scripts/run.sh scripts/20_pick_place.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.assets import (  # noqa: E402
    OPENARM_FLAT_USD,
    FingerColliderError,
    FingerColliderVerdict,
    assert_finger_colliders,
    finger_collider_failure,
)

#: Stand-in for whatever USD the run actually selected (remote instanced fallback).
USED_ASSET = "https://example.invalid/Robots/OpenArm/openarm_bimanual.usd"


def expect_raise(verdict: FingerColliderVerdict, label: str) -> str:
    """Return the guard message, asserting that it fired and names the escapes."""
    message = finger_collider_failure(verdict, USED_ASSET)
    assert message is not None, f"{label}: guard returned no failure message"
    try:
        assert_finger_colliders(verdict, USED_ASSET)
    except FingerColliderError as exc:
        if str(exc) != message:
            raise AssertionError(f"{label}: exception text differs from message")
        for needle in (
            "FRUIT_GRIPPER_KIND=openarm",
            USED_ASSET,
            OPENARM_FLAT_USD,
            "FRUIT_ROBOT_USD",
            "FRUIT_GRIPPER_KIND=kinematic",
        ):
            if needle not in message:
                raise AssertionError(f"{label}: message lacks {needle!r}:\n{message}")
        return message
    raise AssertionError(f"{label}: guard did not raise")


def main() -> int:
    # De-instanced asset: all four finger visual roots got enabled colliders.
    assert_finger_colliders(FingerColliderVerdict(enabled=4, skipped=0, roots=4), USED_ASSET)
    assert finger_collider_failure(
        FingerColliderVerdict(enabled=4, skipped=0, roots=4), USED_ASSET
    ) is None

    # Instanced fallback: instance proxies refuse authoring, everything skipped.
    msg = expect_raise(
        FingerColliderVerdict(enabled=0, skipped=4, roots=4), "all skipped"
    )
    # Missing/other asset: no finger visual roots at all.
    expect_raise(FingerColliderVerdict(enabled=0, skipped=0, roots=0), "no roots")
    # A partially authored hand is still a broken hand.
    expect_raise(FingerColliderVerdict(enabled=3, skipped=1, roots=4), "partial")

    print("finger collider guard: PASS (3 failing verdicts raise, 1 valid passes)")
    print("sample fail-fast message:")
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
