#!/usr/bin/env python3
"""P82: apply the one optimization — the arbiter's wake-on-request — to bimanual.py.

Run from the repo root:  python3 logs/p82/apply_wake_patch.py
Dry run:                 python3 logs/p82/apply_wake_patch.py --check

Every edit asserts its anchor, so a stale tree fails loudly instead of half-editing.
The knob is **default off** (`FRUIT_BIARM_WAKE_ON_REQUEST=1`), so the shipped path
is unchanged and every recorded wall baseline still reproduces; the A/B, its
bit-identity proof and the wall delta are in `logs/p82/RESULTS.md`.
"""

from __future__ import annotations

import sys

PATH = "src/fruit_sorting/bimanual.py"

EDITS: list[tuple[str, str]] = [
    # ---- 1. module docstring: name the poll and the knob ------------------
    (
        """This replaces a first version with a distributed "pass the token" protocol,
whose `arm`/`pause`/`resume` interleavings could deadlock (thread dumps showed
the permits lost in a two-way wait). One arbiter, one lock, no races.
""",
        """This replaces a first version with a distributed "pass the token" protocol,
whose `arm`/`pause`/`resume` interleavings could deadlock (thread dumps showed
the permits lost in a two-way wait). One arbiter, one lock, no races.

**The main thread's poll (P82).** `CoopSession.run` drives `bridge.serve_while`:
`TickRelay.schedule()` and then `MainBridge.pump(0.005)`. `pump`'s queue only ever
receives *bridged main-thread jobs* (a render, an `update_app`), never the tick
requests that `TickRelay.request` files, so a granted worker used to run with the
main thread asleep for the rest of the 5 ms timeout. Measured on the two-line
(20 attempts, seed 5): 5.03 ms of `pump` wait per round, 99.2 % of them timeouts,
2.03 rounds per shared tick - **~33 % of the run's wall in pure poll latency**, while
the worker's own segment is 1.70 ms (`logs/p82/R1.timers.json`).
`FRUIT_BIARM_WAKE_ON_REQUEST=1` makes `request`/`pause`/`resume`/`release` wake the
main thread, so `schedule` runs again as soon as the arbiter's state changes. It
moves *when* `schedule` is called, never which tick is stepped or which attempt
holds the permit, so the run is bit-identical (proved: 865/865 `[fruit]` lines,
`logs/p82/RESULTS.md`). **Default off**, like every other measured lever here.
""",
    ),
    # ---- 2. MainBridge state -------------------------------------------
    (
        """    def __init__(self):
        self._jobs: "queue.Queue[MainBridge._Job]" = queue.Queue()
        self._serving = False
""",
        """    def __init__(self):
        self._jobs: "queue.Queue[MainBridge._Job]" = queue.Queue()
        self._serving = False
        #: P82 (`FRUIT_BIARM_WAKE_ON_REQUEST=1`, **default off**): return from
        #: `pump` as soon as a worker files a tick request, instead of waiting out
        #: the poll timeout. Off = one attribute test per `wake()`, i.e. the
        #: shipped path (the timeout is the wake-up and it is 5 ms).
        self.wake_on_request = False
        self._wake = threading.Event()
""",
    ),
    # ---- 3. MainBridge.call: a queued job also wakes the pump ----------
    (
        """        job = self._Job(fn, args, kwargs)
        self._jobs.put(job)
        job.done.wait()
""",
        """        job = self._Job(fn, args, kwargs)
        self._jobs.put(job)
        self.wake()
        job.done.wait()
""",
    ),
    # ---- 4. MainBridge: wake() + the waiting pump ----------------------
    (
        """    def pump(self, timeout: float = 0.01) -> None:
        \"\"\"Execute one pending job (must be called on the main thread).\"\"\"
        try:
            job = self._jobs.get(timeout=timeout)
        except queue.Empty:
            return
        try:
""",
        """    def wake(self) -> None:
        \"\"\"Let a `pump` that is waiting return now (P82; a no-op when off).

        Called by `TickRelay` whenever the arbiter's state changes - a worker
        files a tick request, or it pauses/resumes/leaves - because those are the
        transitions `schedule` acts on and the queue never carries them.
        \"\"\"
        if self.wake_on_request:
            self._wake.set()

    def _next_job_waiting(self, timeout: float):
        \"\"\"Return a queued job, or `None` after a wake/timeout (P82).

        `pump`'s queue only receives *bridged main-thread jobs* (a render, an
        `update_app`), so waiting on it alone left the main thread asleep for the
        rest of the timeout while the granted worker ran: measured 5.03 ms per
        round, 99.2 % timeouts, ~2 rounds per shared tick
        (`logs/p82/R1.timers.json`). Waiting on the wake costs the same when
        nobody is ready and returns in microseconds when somebody is; the timeout
        stays as the safety net, so a lost wake costs latency, never a stall.
        \"\"\"
        try:
            return self._jobs.get_nowait()
        except queue.Empty:
            pass
        if self._wake.is_set():
            # A wake that arrived before this call: hand control back so the
            # caller runs `schedule` again. No clear-without-wait, so a wake that
            # lands between the test and the wait below is not swallowed.
            self._wake.clear()
            return None
        self._wake.wait(timeout)
        self._wake.clear()
        return None

    def pump(self, timeout: float = 0.01) -> None:
        \"\"\"Execute one pending job (must be called on the main thread).\"\"\"
        if self.wake_on_request:
            job = self._next_job_waiting(timeout)
            if job is None:
                return
        else:
            try:
                job = self._jobs.get(timeout=timeout)
            except queue.Empty:
                return
        try:
""",
    ),
    # ---- 5. TickRelay: notify helper -----------------------------------
    (
        """    def _log(self, event: str) -> None:
""",
        """    def _notify(self) -> None:
        \"\"\"Wake the parked attempts **and** the serving main thread (P82).

        `schedule`'s own `notify_all` is deliberately left alone: waking the main
        thread from inside `schedule` would make the next `pump` return without
        waiting and turn the driver loop into a spin.
        \"\"\"
        self._cv.notify_all()
        self.bridge.wake()

    def _log(self, event: str) -> None:
""",
    ),
    # ---- 6. TickRelay.register ----------------------------------------
    (
        """            self._live.add(me)
            self._cv.notify_all()

    def participant(self) -> bool:
""",
        """            self._live.add(me)
            self._notify()

    def participant(self) -> bool:
""",
    ),
    # ---- 7. TickRelay.enter -------------------------------------------
    (
        """            self._parked.add(me)
            self._cv.notify_all()
        self._wait_permit()

    def request(self, *, steps: int, callback, update_fabric: bool) -> None:
""",
        """            self._parked.add(me)
            self._notify()
        self._wait_permit()

    def request(self, *, steps: int, callback, update_fabric: bool) -> None:
""",
    ),
    # ---- 8. TickRelay.request: the hot path ---------------------------
    (
        """            self._parked.add(me)
            self._cv.notify_all()
            while self._running != me and me not in self._done:
""",
        """            self._parked.add(me)
            self._notify()
            while self._running != me and me not in self._done:
""",
    ),
    # ---- 9. TickRelay.pause -------------------------------------------
    (
        """            self._pending.pop(me, None)
            if self._running == me:
                self._running = None
            self._cv.notify_all()

    def resume(self) -> None:
""",
        """            self._pending.pop(me, None)
            if self._running == me:
                self._running = None
            self._notify()

    def resume(self) -> None:
""",
    ),
    # ---- 10. TickRelay.resume -----------------------------------------
    (
        """            self._live.add(me)
            self._parked.add(me)
            self._cv.notify_all()
        self._wait_permit()

    def release(self) -> None:
""",
        """            self._live.add(me)
            self._parked.add(me)
            self._notify()
        self._wait_permit()

    def release(self) -> None:
""",
    ),
    # ---- 11. TickRelay.release ----------------------------------------
    (
        """            self._done.add(me)
            self._live.discard(me)
            self._parked.discard(me)
            self._pending.pop(me, None)
            if self._running == me:
                self._running = None
            self._cv.notify_all()

    def _wait_permit(self) -> None:
""",
        """            self._done.add(me)
            self._live.discard(me)
            self._parked.discard(me)
            self._pending.pop(me, None)
            if self._running == me:
                self._running = None
            self._notify()

    def _wait_permit(self) -> None:
""",
    ),
    # ---- 12. CoopSession: the knob ------------------------------------
    (
        """        self._debug_handle = None
        relay_log = os.environ.get("FRUIT_BIARM_RELAY_LOG")
""",
        """        self._debug_handle = None
        #: P82: the arbiter's wake-on-request (default off - see the module
        #: docstring). One env read per session, so an unset knob costs nothing
        #: on any path.
        self.bridge.wake_on_request = (
            os.environ.get("FRUIT_BIARM_WAKE_ON_REQUEST", "0") == "1"
        )
        relay_log = os.environ.get("FRUIT_BIARM_RELAY_LOG")
""",
    ),
]


def main(argv: list[str]) -> int:
    check = "--check" in argv
    with open(PATH, encoding="utf-8") as handle:
        text = handle.read()
    original = text
    for index, (old, new) in enumerate(EDITS, 1):
        count = text.count(old)
        if count != 1:
            print(f"FAIL edit {index}: anchor found {count} times (want 1)")
            return 1
        text = text.replace(old, new)
    if check:
        print(f"OK: all {len(EDITS)} anchors found exactly once; nothing written")
        return 0
    with open(PATH, "w", encoding="utf-8") as handle:
        handle.write(text)
    import ast

    ast.parse(text)
    print(f"OK: {len(EDITS)} edits applied to {PATH} "
          f"({len(original)} -> {len(text)} bytes), syntax valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
