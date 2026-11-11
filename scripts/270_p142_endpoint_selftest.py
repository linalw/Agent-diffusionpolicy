#!/usr/bin/env python3
"""P142 self-test: the two ways the direct lane lost an episode to the park slot.

1. **The handover guard is outside the diagnostic gate.** P139 wrote the guard
   inside `if FRUIT_SAMPLE_DIAG == "1"`, so the shipped loop never ran it - the
   live rollout printed `openarm fingertips 103342 mm from the fruit` with the
   guard present. The check is on the source order: the `if _parked or _foreign
   or pad_error > _pad_limit:` block must come **before** the diag row, inside
   the same `if openarm:` arm.
2. **`_recycle_end` never parks a body an attempt owns.** It is the despawn scan
   (`update`), and its only guard was `sample.parked`; a target that fell off the
   line was teleported to `(60 + 3i, 0, -50)` while the attempt still read
   `position(sample)`. The defers here are executed on a stub, both directions.
3. **The score endpoint is a declared metric.** `final` (shipped) reads the
   payload's position at finalize; `release` reads the task's own `placed`.
"""
from __future__ import annotations

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

# `fruits.py` imports `pxr` and the Isaac Sim core at module level. The one
# method under test (`_recycle_end`) touches neither, so they are stubbed the way
# the P131 leg stubs `pxr` for `meshes.axis_extent` - the pure body is executed,
# nothing constructs a stage.
import unittest.mock as mock  # noqa: E402

for _name in ("pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental",
              "isaacsim.core.experimental.utils",
              "isaacsim.core.experimental.utils.app",
              "isaacsim.core.experimental.prims"):
    sys.modules.setdefault(_name, mock.MagicMock())

from fruit_sorting.fruits import FruitSpawner  # noqa: E402
from fruit_sorting.rl_env import score_endpoint  # noqa: E402

CHECKS = {"passed": 0, "failed": 0}


def check(condition, message):
    if condition:
        CHECKS["passed"] += 1
        print(f"  ok: {message}")
    else:
        CHECKS["failed"] += 1
        print(f"  FAIL: {message}")


def source(*parts) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
def test_endpoint():
    print("[1] the score endpoint")
    old = os.environ.pop("FRUIT_SCORE_ENDPOINT", None)
    try:
        check(score_endpoint() == "final", "unset -> the shipped metric")
        os.environ["FRUIT_SCORE_ENDPOINT"] = "release"
        check(score_endpoint() == "release", "=release -> the task's own placed")
        os.environ["FRUIT_SCORE_ENDPOINT"] = " RELEASE "
        check(score_endpoint() == "release", "case and whitespace are tolerated")
        os.environ["FRUIT_SCORE_ENDPOINT"] = "final"
        check(score_endpoint() == "final", "=final -> the shipped metric")
        os.environ["FRUIT_SCORE_ENDPOINT"] = "best"
        try:
            score_endpoint()
            check(False, "a typo raises")
        except ValueError:
            check(True, "a typo raises instead of silently changing the metric")
    finally:
        os.environ.pop("FRUIT_SCORE_ENDPOINT", None)
        if old is not None:
            os.environ["FRUIT_SCORE_ENDPOINT"] = old


def test_guard_order():
    print("[2] the handover guard runs on every close")
    tasks = source("src", "fruit_sorting", "tasks.py")
    start = tasks.index("if openarm:\n", tasks.index("pad_error > float(os.environ"))
    arm = tasks[start:]
    guard = arm.index("if _parked or pad_error > _pad_limit:")
    diag = arm.index('if os.environ.get("FRUIT_SAMPLE_DIAG", "0") == "1":', start * 0)
    check(guard < diag, "the abort is evaluated before the diagnostic row")
    check(
        'os.environ.get("FRUIT_HANDOVER_PAD_ERROR_MAX", "1.0")' in arm,
        "the physical term's bound is an env knob with a 1 m default",
    )
    check(
        '"sample swapped or recycled before the close"' in arm,
        "its note key is the P139 one (declared, already in the ledger)",
    )
    # The diag row still exists and still prints the five fields.
    for field in ("idx=", "parked=", "protected=", "is_protected=", "pos=("):
        check(field in arm, f"the [sample] row still carries {field}")


def test_recycle_defer():
    print("[3] the despawn scan defers an owned body")
    fruits = source("src", "fruit_sorting", "fruits.py")
    check(
        "if sample.held or self.is_protected(sample):" in fruits,
        "_recycle_end has the owned-body branch",
    )
    check(
        "_pending_recycle.append(sample)" in fruits,
        "and it defers instead of parking",
    )
    check(
        "if self._pending_recycle:" in fruits,
        "update() drains the deferred list",
    )
    check(
        "self._pending_recycle: list[FruitSample] = []" in fruits,
        "the list is initialised once",
    )

    # Execute both directions of `_recycle_end` on a stub.
    class Stub:
        _recycle_end = FruitSpawner._recycle_end

        def __init__(self):
            self.stats = {"fell_off": 0, "reached_end": 0}
            self._bed_diag = False
            self.active = []
            self._pending_recycle = []
            self.protected = None
            self.parked = []

        def is_protected(self, sample):
            return self.protected is not None and sample.index == self.protected

        def park(self, sample):
            self.parked.append(int(sample.index))

    def sample(index, held=False):
        return types.SimpleNamespace(
            index=index, held=held, parked=False, category="apple"
        )

    stub = Stub()
    owned = sample(3, held=True)
    stub.active.append(owned)
    stub._recycle_end(owned, "fell_off", [0.3, 0.2, 0.9], 0.2)
    check(stub.parked == [], "an owned body is not parked")
    check(owned in stub._pending_recycle, "it is deferred")
    check(owned not in stub.active, "and taken off the line")
    check(stub.stats["fell_off"] == 1, "the statistic is still counted")

    stub2 = Stub()
    free = sample(4)
    stub2.active.append(free)
    stub2._recycle_end(free, "reached_end", [0.3, -0.8, 1.2], -0.8)
    check(stub2.parked == [4], "an unowned body is parked as before")
    check(not stub2._pending_recycle, "nothing is deferred for it")

    stub3 = Stub()
    protected = sample(5)
    stub3.active.append(protected)
    stub3.protected = 5
    stub3._recycle_end(protected, "fell_off", [0.0, 0.0, 0.5], 0.0)
    check(stub3.parked == [], "a `protected` body is deferred too")
    # The drain: still held -> kept; released -> parked.
    stub3.held = True
    for pending in list(stub3._pending_recycle):
        if pending.held or stub3.is_protected(pending):
            continue
        stub3.park(pending)
    check(stub3.parked == [], "the drain keeps a still-owned body")
    protected.held = False
    stub3.protected = None
    for pending in list(stub3._pending_recycle):
        if pending.held or stub3.is_protected(pending):
            continue
        stub3.park(pending)
    check(stub3.parked == [5], "and parks it once the attempt releases it")


def main():
    print("P142 endpoint / handover self-test")
    test_endpoint()
    test_guard_order()
    test_recycle_defer()
    print(
        f"\n{'PASS' if CHECKS['failed'] == 0 else 'FAIL'}: "
        f"{CHECKS['passed']} checks, {CHECKS['failed']} failed"
    )
    return 0 if CHECKS["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
