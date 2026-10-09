"""Bimanual scheduling for the scripted sorting line.

Two schedulers live here. **`FRUIT_BIARM=1` runs the F2 shared-station pipeline
by default** (below). `FRUIT_BIARM_TWOLINE=1` opts into the v9/V2 two-line
scheduler: each arm owns one pick station on the shared belt (left upstream
at y = 0, right downstream at y = -0.10, `tasks.py::run_bimanual`), the shared
`StationLock` is not used, and the two attempts overlap from the descent
onwards. Each off-centre station gets a station-specific pre-pose configuration
solved once per batch (so the two approaches stay on their own sides); the
second `StationLock` (`CoopSession.prepose`) serializes the approaches only if
such a solve failed. The two-line's placed/min gain missed the pre-registered
1.25x replacement bar (`logs/v2/RESULT.md`), so it stays opt-in.

F2 shared-station scheme (kept for the A/B): **pipelined two-arm operation at
the shared pick station**. The cell has one main belt, one pick station and two
arms whose workspaces both cover that station (measured, ``scripts/97_reach_probe.py``:
a 2.1 mm residual for either arm at the station). One arm owns the station from
its pre-pose until its payload has cleared the station box; while it carries and
places, the other arm pre-poses, waits for the next fruit and catches it. The
two attempts therefore overlap in simulated time, which is the only way to gain
throughput - re-ordering two blocking attempts cannot.

Concurrency without rewriting the 2 000-line blocking attempt: the two attempts
run in two threads and a **main-thread scheduler** (`TickRelay`) arbitrates.
Workers never run at the same time and never step physics themselves:

* `TickRelay.request` (called from the patched `SimulationManager.step`) parks
  the worker and files a request for N physics ticks;
* the scheduler (`schedule`, driven by the bridge loop on the main thread)
  executes one tick when every live attempt has an outstanding request - a
  **shared** tick, because the world advances for both arms - or alone when the
  other attempt is paused/absent; each arm's control loop therefore stays at
  120 Hz in simulated time (two independent ticks per round halved it and broke
  the catch calibration);
* after ticking, the scheduler grants a single **run permit**: exactly one
  worker executes its segment (arm reads, IK - the PhysX-incompatible class)
  while the other stays parked, so the token is never held by a sleeping thread.

This replaces a first version with a distributed "pass the token" protocol,
whose `arm`/`pause`/`resume` interleavings could deadlock (thread dumps showed
the permits lost in a two-way wait). One arbiter, one lock, no races.

The step itself runs on the main thread: `omni.kit.app.update` /
`RenderingManager.render` (the recorder's per-tick capture) are
main-thread-only, and keeping the physics there removes the
"articulation read during `simulate()`" class of errors entirely.
"""

from __future__ import annotations

import os
import queue
import threading
import time


class MainBridge:
    """Run main-thread-only calls issued by attempt threads on the main thread.

    `call` blocks the worker until the main thread has executed the job; calls
    made *on* the main thread (a recorder running inside a bridged step, the
    driver between attempts) run inline so a bridged call can never deadlock
    against itself.
    """

    class _Job:
        __slots__ = ("fn", "args", "kwargs", "done", "result", "error")

        def __init__(self, fn, args, kwargs):
            self.fn = fn
            self.args = args
            self.kwargs = kwargs
            self.done = threading.Event()
            self.result = None
            self.error = None

    def __init__(self):
        self._jobs: "queue.Queue[MainBridge._Job]" = queue.Queue()
        self._serving = False

    @property
    def serving(self) -> bool:
        return self._serving

    def call(self, fn, *args, **kwargs):
        """Execute `fn(*args, **kwargs)` on the main thread (or inline there)."""
        if threading.current_thread() is threading.main_thread() or not self._serving:
            return fn(*args, **kwargs)
        job = self._Job(fn, args, kwargs)
        self._jobs.put(job)
        job.done.wait()
        if job.error is not None:
            raise job.error
        return job.result

    def pump(self, timeout: float = 0.01) -> None:
        """Execute one pending job (must be called on the main thread)."""
        try:
            job = self._jobs.get(timeout=timeout)
        except queue.Empty:
            return
        try:
            job.result = job.fn(*job.args, **job.kwargs)
        except BaseException as exc:  # noqa: BLE001 - re-raised in the worker
            job.error = exc
        finally:
            job.done.set()

    def serve_while(self, predicate) -> None:
        """Pump jobs while `predicate()` is true; `_serving` is on throughout.

        The predicate runs on the main thread and is where the bimanual
        scheduler gets its cycles (`CoopSession` calls `TickRelay.schedule` from
        it), so it must stay cheap and non-blocking.
        """
        self._serving = True
        try:
            while self._serving and predicate():
                self.pump(0.005)
            while not self._jobs.empty():
                self.pump(0.0)
        finally:
            self._serving = False


class StationLock:
    """One attempt owns the shared pick station at a time.

    The owner releases when its payload has cleared the station box (the task
    checks this every tick through the session's `after_step` hook) or when the
    attempt ends and its arm has parked clear. A waiting attempt yields the run
    permit while it blocks, so the holder keeps executing alone.
    """

    def __init__(self):
        self._cond = threading.Condition()
        self._owner: int | None = None

    @property
    def owner(self):
        return self._owner

    def held_by_current(self) -> bool:
        return self._owner == threading.get_ident()

    def acquire(self, relay: "TickRelay") -> None:
        me = threading.get_ident()
        relay.pause()
        with self._cond:
            while self._owner is not None and self._owner != me:
                self._cond.wait()
            self._owner = me
        relay.resume()

    def release(self) -> None:
        with self._cond:
            if self._owner == threading.get_ident():
                self._owner = None
                self._cond.notify_all()


class TickRelay:
    """Main-thread arbiter for two concurrent scripted attempts.

    State (guarded by `_cv`): which attempts are live/parked/done, how many
    ticks each has requested, and which one holds the run permit. All
    transitions happen in `request`/`pause`/`resume`/`release` (worker side) or
    `schedule` (main thread), so there is no distributed token to lose.
    """

    def __init__(self, bridge: MainBridge):
        self._cv = threading.Condition()
        self.bridge = bridge
        #: The original `SimulationManager.step` (installed by `CoopSession`).
        self.step_fn = None
        self.step_count = 0
        self._keys: dict[int, str] = {}
        self._order: list[int] = []
        self._live: set[int] = set()
        self._done: set[int] = set()
        #: Registered attempts waiting for the run permit.
        self._parked: set[int] = set()
        #: ident -> [ticks still owed, callback, update_fabric]
        self._pending: dict[int, list] = {}
        self._running: int | None = None
        self._last_run: int | None = None
        self._debug = None
        self._t0 = time.monotonic()

    # -- registration / arming -------------------------------------------- #
    def expect(self, keys) -> None:
        self._key_order = [str(key) for key in keys]

    def register(self, key: str) -> None:
        me = threading.get_ident()
        with self._cv:
            self._keys[me] = str(key)
            if me not in self._order:
                self._order.append(me)
                rank = {name: i for i, name in enumerate(self._key_order)}
                self._order.sort(key=lambda t: rank.get(self._keys.get(t, ""), 99))
            self._live.add(me)
            self._cv.notify_all()

    def participant(self) -> bool:
        """Whether the calling thread is one of this run's attempt threads."""
        return threading.get_ident() in self._keys

    def arm(self) -> None:
        """Return once every expected attempt has registered (kept for symmetry)."""
        with self._cv:
            while len(self._order) < len(self._key_order):
                self._cv.wait()

    # -- worker side ------------------------------------------------------- #
    def enter(self) -> None:
        """First wait for the run permit (the scheduler picks the order)."""
        me = threading.get_ident()
        with self._cv:
            self._parked.add(me)
            self._cv.notify_all()
        self._wait_permit()

    def request(self, *, steps: int, callback, update_fabric: bool) -> None:
        """File a request for `steps` physics ticks and block until granted."""
        me = threading.get_ident()
        with self._cv:
            self._pending[me] = [max(1, int(steps)), callback, update_fabric]
            if self._running == me:
                self._running = None
            self._parked.add(me)
            self._cv.notify_all()
            while self._running != me and me not in self._done:
                self._cv.wait()
            self._parked.discard(me)

    def pause(self) -> None:
        """Yield the permit and leave the runnable set (the station wait)."""
        me = threading.get_ident()
        with self._cv:
            self._live.discard(me)
            self._parked.discard(me)
            self._pending.pop(me, None)
            if self._running == me:
                self._running = None
            self._cv.notify_all()

    def resume(self) -> None:
        """Rejoin the runnable set and wait for the permit."""
        me = threading.get_ident()
        with self._cv:
            self._live.add(me)
            self._parked.add(me)
            self._cv.notify_all()
        self._wait_permit()

    def release(self) -> None:
        """Leave the run entirely."""
        me = threading.get_ident()
        with self._cv:
            self._done.add(me)
            self._live.discard(me)
            self._parked.discard(me)
            self._pending.pop(me, None)
            if self._running == me:
                self._running = None
            self._cv.notify_all()

    def _wait_permit(self) -> None:
        me = threading.get_ident()
        with self._cv:
            while self._running != me and me not in self._done:
                self._cv.wait()
            self._parked.discard(me)

    # -- main-thread side -------------------------------------------------- #
    def schedule(self) -> None:
        """Execute owed ticks and grant one run permit (call on the main thread)."""
        with self._cv:
            live = [t for t in self._order if t in self._live and t not in self._done]
            owed = [self._pending.get(t, (0,))[0] for t in live]
            if live and all(value > 0 for value in owed):
                # Every live attempt is resting on a request: one physics tick
                # is shared by all of them (the world advances for both arms).
                ticks = min(owed)
                for _ in range(ticks):
                    callback = None
                    update_fabric = False
                    for t in live:
                        if self._pending.get(t, (0,))[0] > 0:
                            callback = self._pending[t][1]
                            update_fabric = bool(self._pending[t][2])
                            break
                    self.step_count += 1
                    self._log("step")
                    self.step_fn(
                        steps=1, callback=callback, update_fabric=update_fabric
                    )
                for t in live:
                    self._pending[t][0] -= ticks
                self._log(f"granted x{ticks}")
            if self._running is None:
                candidates = [
                    t
                    for t in self._order
                    if t in self._parked
                    and t not in self._done
                    and self._pending.get(t, (0,))[0] == 0
                ]
                if candidates:
                    if self._last_run in candidates:
                        index = (candidates.index(self._last_run) + 1) % len(candidates)
                    else:
                        index = 0
                    self._running = candidates[index]
                    self._last_run = self._running
                    self._log("permit")
            self._cv.notify_all()

    def _log(self, event: str) -> None:
        handle = self._debug
        if handle is None:
            return
        active = self._keys.get(self._running, "-")
        live = [self._keys.get(t) for t in self._order if t in self._live]
        parked = [self._keys.get(t) for t in self._order if t in self._parked]
        pending = {
            self._keys.get(t): self._pending[t][0]
            for t in self._order
            if t in self._pending
        }
        handle.write(
            f"{time.monotonic() - self._t0:9.4f} {event:14s} "
            f"permit={active} live={live} parked={parked} pending={pending}\n"
        )
        handle.flush()


class CoopSession:
    """Owns the relay/bridge/station and the temporary step/update patches.

    Patches `SimulationManager.step` so that a step call made by a registered
    attempt thread files a request with the relay (and blocks until granted),
    while step calls from the driver/main thread pass straight through.
    `app_utils.update_app` from a worker is bridged to the main thread.
    """

    def __init__(self, keys, trace: bool = False):
        self.bridge = MainBridge()
        self.relay = TickRelay(self.bridge)
        self.relay.expect(keys)
        self.station = StationLock()
        #: Two-line scheduler (v9/V2): each arm owns its own station, so
        #: `station` is unused; `prepose` serializes only the approach phase,
        #: because the two pre-poses converge on the shipped *shared* grasp
        #: configuration (both jaws near y ~ 0) before separating to their own
        #: stations. Same pause/resume protocol as `StationLock`.
        self.prepose = StationLock()
        #: W3 capture token (wave two-line scenario; `run_bimanual` sets
        #: `capture_enabled`): at most one arm may be in its *capture window*
        #: (pre-pose -> close -> until its payload clears its station box) at a
        #: time. The wave supply sends both arms at the same burst; without the
        #: token the trace measured min 1.9 mm link-origin separation and 710
        #: samples <30 mm (both hands in the shared y band). The holder releases
        #: the token from `tasks._biarm_after_step` when its payload has cleared
        #: the station, or in its worker's finally.
        self.capture = StationLock()
        self.capture_enabled = False
        #: True when this session runs the two-line scheduler (`run_bimanual`).
        self.twoline = False
        self.results: list = []
        self.errors: list[BaseException] = []
        self.trace = bool(trace)
        self.trace_rows: list[tuple] = []
        #: Per-tick hook installed by the task (`PickAndPlaceTask._biarm_after_step`).
        self.after_step = None
        self._patched = False
        self._sm = None
        self._app = None
        self._step_descriptor = None
        self._orig_update = None
        self._debug_handle = None
        relay_log = os.environ.get("FRUIT_BIARM_RELAY_LOG")
        if relay_log:
            directory = os.path.dirname(relay_log)
            if directory:
                os.makedirs(directory, exist_ok=True)
            self._debug_handle = open(relay_log, "w", encoding="utf-8")
            self.relay._debug = self._debug_handle

    # -- patches ----------------------------------------------------------- #
    def install(self) -> None:
        from isaacsim.core.simulation_manager import SimulationManager

        import isaacsim.core.experimental.utils.app as app_utils

        self._sm = SimulationManager
        self._app = app_utils
        self._step_descriptor = SimulationManager.__dict__["step"]
        self._orig_update = app_utils.update_app
        original_step = SimulationManager.step  # bound classmethod
        original_update = app_utils.update_app
        self.relay.step_fn = original_step

        def step_patch(*, steps=1, callback=None, update_fabric=False):
            if self.relay.participant():
                self.relay.request(
                    steps=steps, callback=callback, update_fabric=update_fabric
                )
            else:
                original_step(
                    steps=steps, callback=callback, update_fabric=update_fabric
                )

        def update_patch(*, steps=1, callback=None):
            if self.relay.participant():
                self.bridge.call(original_update, steps=steps, callback=callback)
            else:
                original_update(steps=steps, callback=callback)

        SimulationManager.step = staticmethod(step_patch)
        app_utils.update_app = update_patch
        self._patched = True

    def uninstall(self) -> None:
        if not self._patched:
            return
        # Restore the exact class attribute (a `classmethod` descriptor), not
        # the bound method the calls used, so later patches keep working.
        self._sm.step = self._step_descriptor
        self._app.update_app = self._orig_update
        self._patched = False

    def __enter__(self) -> "CoopSession":
        self.install()
        return self

    def __exit__(self, *exc) -> bool:
        self.uninstall()
        return False

    # -- main-thread driver ------------------------------------------------ #
    def run(self, threads: list[threading.Thread]) -> None:
        """Start the attempts, schedule physics/permits, join."""
        stall_s = float(os.environ.get("FRUIT_BIARM_STALL_S", "600"))
        last_steps = self.relay.step_count
        last_change = time.monotonic()

        def alive() -> bool:
            nonlocal last_steps, last_change
            self.relay.schedule()
            now = time.monotonic()
            if self.relay.step_count != last_steps:
                last_steps = self.relay.step_count
                last_change = now
            elif (
                stall_s > 0
                and any(thread.is_alive() for thread in threads)
                and now - last_change > stall_s
            ):
                # The scheduler is wedged: dump every thread's stack (the
                # log shows exactly where) and stop the process - the outer
                # stall guard would kill it anyway, without the stacks.
                import faulthandler

                print(
                    f"[biarm] STALL: no physics step for {now - last_change:.0f}s; "
                    "dumping thread stacks",
                    flush=True,
                )
                faulthandler.dump_traceback()
                os._exit(3)
            return any(thread.is_alive() for thread in threads)

        try:
            for thread in threads:
                thread.start()
            self.relay.arm()
            self.bridge.serve_while(alive)
        finally:
            self.bridge._serving = False
        for thread in threads:
            thread.join()
        if self._debug_handle is not None:
            self._debug_handle.close()
            self.relay._debug = None
            self._debug_handle = None
        if self.errors:
            raise self.errors[0]
