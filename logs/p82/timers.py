"""P82 profile instrumentation I2: per-**round** wall timers for the bimanual arbiter.

Loaded only by `logs/p82/profile_20.py`, which is fed to `scripts/20_pick_place.py`
through `runpy` — never by a shipped entry point. Nothing here is imported by
`src/` and nothing is written to stdout, so a profiled run's log stays
byte-comparable with the canonical record (`logs/p80/T20.log` /
`logs/p80/S20.log`). The summary goes to `$P82_TIMERS` as JSON.

What is timed, and why exactly these boundaries (METHOD §3):

* **per round** (`TickRelay.schedule`): entry/exit timestamps, so the round's own
  wall and the gap to the next round are known;
* **per step** (`relay.step_fn`, i.e. the physics step the arbiter executes):
  wall + count. `schedule_s - step_s` is the arbiter's own Python cost;
* **per worker segment** (`permit -> next TickRelay.request`): the arm's own
  control work (arm reads, IK, fruit state) — one sample per round, **not** a
  per-`ik_step` hook, because AGENTS §2 forbids instrumentation inside the
  control loop;
* **per pump** (`MainBridge.pump`): the main thread's `queue.get` wall and
  whether it was a job or the 5 ms timeout. This is the bucket the dead wall
  would live in;
* **`_tick_frame`** (render/camera) call count + wall — expected 0 because the
  scripted battery has no frame callback and no recorder;
* **StationLock.acquire/pause/resume** counts, so a station wait is not
  mistaken for arbiter cost.

The per-round series are summarised (count/sum/mean/p90/max + a log histogram),
not dumped: the artifact is a text-sized JSON, not a raw sample log.
"""

from __future__ import annotations

import atexit
import json
import os
import threading
import time

from fruit_sorting.bimanual import CoopSession, MainBridge, StationLock, TickRelay

JSON_PATH = os.environ.get("P82_TIMERS", "")
BINS = [0.00005, 0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.5, 1.0]


class _Series:
    """Count/sum/mean/p90/max plus a coarse log histogram (artifacts stay small)."""

    __slots__ = ("n", "total", "values", "bins")

    def __init__(self):
        self.n = 0
        self.total = 0.0
        self.values: list[float] = []
        self.bins = [0] * (len(BINS) + 1)

    def add(self, value: float) -> None:
        self.n += 1
        self.total += value
        if len(self.values) < 400000:
            self.values.append(value)
        for index, edge in enumerate(BINS):
            if value < edge:
                self.bins[index] += 1
                return
        self.bins[-1] += 1

    def summary(self) -> dict:
        if not self.values:
            return {"n": self.n, "sum_s": round(self.total, 4)}
        ordered = sorted(self.values)
        pick = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]  # noqa: E731
        return {
            "n": self.n,
            "sum_s": round(self.total, 4),
            "mean_ms": round(1000.0 * self.total / max(1, self.n), 4),
            "p50_ms": round(1000.0 * pick(0.50), 4),
            "p90_ms": round(1000.0 * pick(0.90), 4),
            "max_ms": round(1000.0 * ordered[-1], 4),
            "hist": {("%g" % edge): count for edge, count in zip(BINS, self.bins)},
            "hist_overflow": self.bins[-1],
        }


T: dict[str, object] = {
    "started": time.time(),
    "schedule_calls": 0,
    "schedule_s": 0.0,
    "tick_calls": 0,
    "step_s": 0.0,
    "pump_calls": 0,
    "pump_jobs": 0,
    "pump_timeouts": 0,
    "pump_s": 0.0,
    "request_calls": 0,
    "segment_calls": 0,
    "segment_s": 0.0,
    "tick_frame_calls": 0,
    "tick_frame_s": 0.0,
    "station_acquire_calls": 0,
    "station_acquire_s": 0.0,
    "round_gap": _Series(),
    "pump_gap": _Series(),
    "segment_gap": _Series(),
    "step_gap": _Series(),
    "round_self": _Series(),
    "permit_grants": 0,
    "schedule_stepped": 0,
    "batch_wall_s": 0.0,
    "main_s": 0.0,
}
_first_entry: list[float | None] = [None]
_last_entry: list[float | None] = [None]
_prev_exit: list[float | None] = [None]
_grant_time: dict[int, float] = {}
_written: list[bool] = [False]

_orig_schedule = TickRelay.schedule
_orig_request = TickRelay.request
_orig_pump = MainBridge.pump
_orig_install = CoopSession.install
_orig_acquire = StationLock.acquire


def _schedule(self):  # noqa: ANN001
    t0 = time.perf_counter()
    if _first_entry[0] is None:
        _first_entry[0] = t0
    if _prev_exit[0] is not None:
        T["round_gap"].add(t0 - _prev_exit[0])
    T["schedule_calls"] = int(T["schedule_calls"]) + 1
    before = self.step_count
    running_before = self._running
    try:
        return _orig_schedule(self)
    finally:
        t1 = time.perf_counter()
        _prev_exit[0] = t1
        _last_entry[0] = t0
        T["schedule_s"] = float(T["schedule_s"]) + (t1 - t0)
        T["round_self"].add(t1 - t0)
        if self.step_count != before:
            T["schedule_stepped"] = int(T["schedule_stepped"]) + 1
        running_now = self._running
        if running_now is not None and running_now != running_before:
            T["permit_grants"] = int(T["permit_grants"]) + 1
            # The permit is granted inside `schedule`; timestamp it here, ~µs
            # after the `with self._cv` block exits.
            _grant_time[running_now] = t1


def _request(self, *, steps, callback, update_fabric):  # noqa: ANN001
    me = threading.get_ident()
    now = time.perf_counter()
    granted = _grant_time.pop(me, None)
    if granted is not None:
        T["segment_calls"] = int(T["segment_calls"]) + 1
        T["segment_s"] = float(T["segment_s"]) + (now - granted)
        T["segment_gap"].add(now - granted)
    T["request_calls"] = int(T["request_calls"]) + 1
    return _orig_request(
        self, steps=steps, callback=callback, update_fabric=update_fabric
    )


def _pump(self, timeout: float = 0.01):
    t0 = time.perf_counter()
    empty_before = self._jobs.empty()
    result = _orig_pump(self, timeout)
    spent = time.perf_counter() - t0
    T["pump_calls"] = int(T["pump_calls"]) + 1
    T["pump_s"] = float(T["pump_s"]) + spent
    T["pump_gap"].add(spent)
    if empty_before and spent >= 0.8 * float(timeout):
        T["pump_timeouts"] = int(T["pump_timeouts"]) + 1
    else:
        T["pump_jobs"] = int(T["pump_jobs"]) + 1
    return result


def _install(self):  # noqa: ANN001
    result = _orig_install(self)
    # `fruit_sorting.tasks` is imported by the entry script after the app is up,
    # so the task class can only be wrapped from here on (the wrappers below are
    # declared profile-build instrumentation: one call + two `perf_counter`s per
    # `_tick_frame`, which is a no-op render on this battery, and never inside
    # `ik_step`).
    _wrap_task_class()
    step_fn = self.relay.step_fn
    if step_fn is not None and not getattr(step_fn, "_p82_timed", False):

        def timed_step(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return step_fn(*args, **kwargs)
            finally:
                spent = time.perf_counter() - t0
                T["tick_calls"] = int(T["tick_calls"]) + 1
                T["step_s"] = float(T["step_s"]) + spent
                T["step_gap"].add(spent)

        timed_step._p82_timed = True  # type: ignore[attr-defined]
        self.relay.step_fn = timed_step
    return result


def _acquire(self, relay):  # noqa: ANN001
    t0 = time.perf_counter()
    T["station_acquire_calls"] = int(T["station_acquire_calls"]) + 1
    try:
        return _orig_acquire(self, relay)
    finally:
        T["station_acquire_s"] = float(T["station_acquire_s"]) + (
            time.perf_counter() - t0
        )


def _wrap_task_class() -> None:
    """Time `_tick_frame` (render/camera). The class is imported after the app."""
    try:
        from fruit_sorting import tasks
    except Exception:  # noqa: BLE001 - app not up yet; retried on first use
        return
    original = getattr(tasks.PickAndPlaceTask, "_tick_frame", None)
    if original is None or getattr(original, "_p82_timed", False):
        return

    def timed_tick_frame(self):
        t0 = time.perf_counter()
        try:
            return original(self)
        finally:
            T["tick_frame_calls"] = int(T["tick_frame_calls"]) + 1
            T["tick_frame_s"] = float(T["tick_frame_s"]) + (
                time.perf_counter() - t0
            )

    timed_tick_frame._p82_timed = True  # type: ignore[attr-defined]
    tasks.PickAndPlaceTask._tick_frame = timed_tick_frame


def mark_main_start() -> None:
    T["main_t0"] = time.perf_counter()


def mark_main_end() -> None:
    t0 = T.get("main_t0")
    if t0 is not None:
        T["main_s"] = time.perf_counter() - float(t0)


def install() -> None:
    TickRelay.schedule = _schedule
    TickRelay.request = _request
    MainBridge.pump = _pump
    CoopSession.install = _install
    StationLock.acquire = _acquire
    atexit.register(write)


def _round(x: float, nd: int = 4) -> float:
    return float(f"%.{nd}f" % x)


def write() -> None:
    if not JSON_PATH:
        return
    if _written[0]:
        return
    _written[0] = True
    _wrap_task_class()
    now = time.perf_counter()
    if _first_entry[0] is not None and _last_entry[0] is not None:
        T["batch_wall_s"] = _round(now - float(_first_entry[0]), 3)
    payload = {
        "instrument": "P82-I2 arbiter timers (per round, per step, never per ik_step)",
        "json": JSON_PATH,
        "wall_main_s": _round(float(T["main_s"]), 3),
        "wall_from_first_round_s": T.get("batch_wall_s"),
        "sched": {
            "rounds": T["schedule_calls"],
            "rounds_that_stepped": T["schedule_stepped"],
            "permit_grants": T["permit_grants"],
            "schedule_total_s": _round(float(T["schedule_s"]), 3),
            "round_self": T["round_self"].summary(),
            "round_gap": T["round_gap"].summary(),
        },
        "steps": {
            "ticks": T["tick_calls"],
            "step_total_s": _round(float(T["step_s"]), 3),
            "per_step": T["step_gap"].summary(),
        },
        "arbiter_overhead_s": _round(
            max(0.0, float(T["schedule_s"]) - float(T["step_s"])), 3
        ),
        "pump": {
            "calls": T["pump_calls"],
            "jobs": T["pump_jobs"],
            "timeouts": T["pump_timeouts"],
            "total_s": _round(float(T["pump_s"]), 3),
            "wait": T["pump_gap"].summary(),
        },
        "segments": {
            "samples": T["segment_calls"],
            "total_s": _round(float(T["segment_s"]), 3),
            "per_segment": T["segment_gap"].summary(),
        },
        "requests": T["request_calls"],
        "tick_frame": {
            "calls": T["tick_frame_calls"],
            "total_s": _round(float(T["tick_frame_s"]), 4),
        },
        "station": {
            "acquires": T["station_acquire_calls"],
            "total_s": _round(float(T["station_acquire_s"]), 3),
        },
        "rounds_per_tick": _round(
            T["schedule_calls"] / max(1, int(T["tick_calls"])), 3
        ),
        "mean_per_tick_wall_ms": _round(
            1000.0 * float(T["batch_wall_s"]) / max(1, int(T["tick_calls"])), 4
        ),
    }
    try:
        with open(JSON_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)
            handle.write("\n")
    except Exception as exc:  # noqa: BLE001 - never fail the run for the profile
        print(f"[p82] timer write failed: {exc}", flush=True)
