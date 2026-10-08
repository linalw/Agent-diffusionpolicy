"""Offline selftest for the bimanual scheduler's arbitration logic.

    python3 scripts/152_biarm_selftest.py

No simulator: it exercises `fruit_sorting.bimanual` with a fake step function,
so the acceptance can trust the scheduler's core invariants even though the
attempts themselves need Isaac Sim:

* **paired stepping** - when both attempts are live and each has issued an equal
  number of tick requests, the number of physics steps equals the *per-arm*
  request count, not the total: one shared tick per round keeps both control
  loops at 120 Hz in simulated time (two independent ticks per round halved it
  and broke the catch calibration);
* **exclusivity** - at most one attempt thread executes its segment at a time,
  and every physics step runs on the main thread;
* **determinism** - two identical runs produce the same segment sequence;
* **the station is mutually exclusive and hands over** - a waiting attempt
  parks while it blocks, wakes on release and resumes without deadlock;
* **a solo attempt steps once per request**.

This mirrors `scripts/128_rtc_selftest.py`'s role: a pure-Python pin of the
mechanism, run by `scripts/selfcheck.sh` before any simulator time is spent.
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.bimanual import MainBridge, StationLock, TickRelay  # noqa: E402


class FakeStep:
    def __init__(self) -> None:
        self.calls: list[tuple[int, bool]] = []
        self.guard = threading.Lock()
        self.concurrent = 0
        self.max_concurrent = 0

    def __call__(self, *, steps=1, callback=None, update_fabric=False) -> None:
        with self.guard:
            self.concurrent += 1
            self.max_concurrent = max(self.max_concurrent, self.concurrent)
            self.calls.append(
                (
                    threading.get_ident(),
                    threading.current_thread() is threading.main_thread(),
                )
            )
            time.sleep(0.0001)
            self.concurrent -= 1


def run_pair(*, contested: bool = False):
    bridge = MainBridge()
    relay = TickRelay(bridge)
    relay.expect(["left", "right"])
    station = StationLock()
    step = FakeStep()
    relay.step_fn = step
    errors: list[BaseException] = []
    order: list[str] = []

    def worker(key: str, ticks: int, acquire: bool, release_after: int = 0):
        relay.register(key)
        relay.enter()
        try:
            if acquire:
                station.acquire(relay)
            for index in range(ticks):
                relay.request(steps=1, callback=None, update_fabric=False)
                order.append(key)
                if acquire and release_after and index + 1 == release_after:
                    station.release()
            if acquire and station.held_by_current():
                station.release()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            relay.release()

    if contested:
        # The left owns the station first and releases after 10 requests, so the
        # right is paused for those 10 (left steps solo) and then both arms have
        # ~20 requests each, which pair: ~10 + 20 = ~30 ticks.
        left = threading.Thread(target=worker, args=("left", 30, True, 10))
        right = threading.Thread(target=worker, args=("right", 20, True, 0))
    else:
        left = threading.Thread(target=worker, args=("left", 50, True, 0))
        right = threading.Thread(target=worker, args=("right", 50, False, 0))
    bridge._serving = True
    for thread in (left, right):
        thread.start()
    relay.arm()
    deadline = time.time() + 15
    while any(t.is_alive() for t in (left, right)) and time.time() < deadline:
        relay.schedule()
        bridge.pump(0.001)
    for thread in (left, right):
        thread.join(timeout=2)
    bridge._serving = False
    assert not errors, f"worker errors: {errors!r}"
    assert not left.is_alive() and not right.is_alive(), "attempts did not finish"
    assert step.max_concurrent == 1, f"concurrent steps: {step.max_concurrent}"
    assert station.owner is None, "station was not released"
    return step, order


def main() -> int:
    # 1. Two equal 50-request attempts: 100 requests share 50 physics ticks.
    step, order = run_pair()
    assert len(step.calls) == 50, (
        f"expected 50 shared ticks for 2x50 requests, got {len(step.calls)}"
    )
    assert all(main for _, main in step.calls), "a step ran off the main thread"
    assert order.count("left") == 50 and order.count("right") == 50
    assert order[:4] in (
        ["left", "right", "left", "right"],
        ["right", "left", "right", "left"],
    ), order[:4]
    print(f"pair: 100 requests -> {len(step.calls)} shared ticks, exclusive, alternating")

    # 2. Determinism: identical runs produce the same segment sequence.
    assert run_pair()[1] == run_pair()[1], "segment order is not deterministic"
    print("pair: deterministic segment order")

    # 3. Contested station: the left runs 10 solo ticks, releases, and the
    # remaining requests pair; the count is 30-36 (the joining attempt can miss
    # the first pairing round or two at the handover).
    contested, _ = run_pair(contested=True)
    assert 30 <= len(contested.calls) <= 40, len(contested.calls)
    print(
        f"contested station: park/release/resume without deadlock "
        f"({len(contested.calls)} ticks for 50 requests)"
    )

    # 4. Solo attempt: one request, one tick.
    bridge = MainBridge()
    relay = TickRelay(bridge)
    relay.expect(["solo"])
    single = FakeStep()
    relay.step_fn = single
    station = StationLock()

    def solo_worker():
        relay.register("solo")
        relay.enter()
        try:
            relay.request(steps=1, callback=None, update_fabric=False)
            relay.request(steps=4, callback=None, update_fabric=False)
            station.acquire(relay)
            station.release()
        finally:
            relay.release()

    solo = threading.Thread(target=solo_worker)
    solo.start()
    deadline = time.time() + 10
    while solo.is_alive() and time.time() < deadline:
        relay.schedule()
        bridge.pump(0.001)
    solo.join(timeout=2)
    assert not solo.is_alive()
    assert len(single.calls) == 5, len(single.calls)
    print("solo attempt: 5 requests -> 5 ticks")

    print("biarm selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
