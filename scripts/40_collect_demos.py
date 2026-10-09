"""Collect scripted demonstrations into datasets/demos.

    FRUIT_EPISODES=20 scripts/run.sh scripts/40_collect_demos.py

Two modes, selected by the environment:

* **single arm (shipped default)**: the collector feeds the line between
  attempts and records one episode per successful `task.run`;
* **two-line (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`)**: the whole collection runs
  through `task.run_bimanual`, which drives both arms on their own stations.
  Each attempt is recorded as its own episode with a per-episode arm/station
  label (`EpisodeMeta.station_y`), and the recorder allocates unique episode
  indices itself because the process-wide `FRUIT_EPISODE_INDEX` cannot label two
  concurrent attempts.

A **stall guard** is armed for both modes, and it is a **collector-side
per-episode watchdog - never a belt stop**. Two layers:

* **soft per-episode timeout (`FRUIT_COLLECT_EPISODE_S`, default 600 s)**:
  the collector sets `task.episode_timeout_s`, and `_step_sim` raises
  `AttemptTimeout` when one attempt runs past its wall budget. The collector
  **skips** that attempt (the recorder discards its partial frames, the fruit
  recycles and is retryable) and carries on with the next fruit. In two-line
  mode the worker catches it, logs the skip and keeps the session alive. The
  line keeps running: the belt is never stopped and the catch stays the
  never-stop dynamic one (`gate_open=0.0`, zero `indexed:` is checked and
  reported at the end);
* **hard progress window (`FRUIT_COLLECT_STALL_S`, default 600 s)** as a last
  resort for a fully blocked C++ call that the soft deadline cannot interrupt
  (the 2026-10-10 wedges were a blocking `RenderingManager.render()` under the
  bimanual bridge): if the physics clock advances less than
  `FRUIT_COLLECT_MIN_PROGRESS_S` (default 5 s) over the window, the shard
  exits with a thread-stack dump (`FRUIT_COLLECT_HARD_EPISODE_S`, default 0 =
  off, can additionally cap a chunk). A shard is restartable and its log
  names the wedge; the shard loop then advances the seed.
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

# Set HEADLESS=0 to watch the run in the Isaac Sim GUI.
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

# Raise the fd limit before Isaac Sim starts: this build opens ~2100
# `/dev/nvidiactl` descriptors on the first camera read and dies with
# `dup failed ... Too many open files` at the default limit.
raise_fd_limit()

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import faulthandler

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils

try:  # pragma: no cover - import guard mirrors the other entry scripts
    from isaacsim.core.simulation_manager import SimulationManager
except ImportError:  # pragma: no cover
    SimulationManager = None

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.dataset import EpisodeRecorder
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.tasks import AttemptTimeout, PickAndPlaceTask

install_failure_handler("40_collect_demos")

DT = 1.0 / 120.0
EPISODES = int(os.environ.get("FRUIT_EPISODES", "10"))
OUT_DIR = os.environ.get("FRUIT_DEMO_DIR", "datasets/demos")
FIXED_STEPPING = os.environ.get("FRUIT_FIXED_STEPPING", "1") == "1"
#: Stall-guard knobs (see the module docstring). Defaults are on.
#: `GUARD_STALL_S` is the length of the hard progress window; `GUARD_MIN_PROGRESS_S`
#: is how much simulated time that window must advance at minimum (a healthy
#: run is 0.2-0.5x real time, so 600 s of wall should advance >= 100 s of sim;
#: the contact-grind wedge measured at ~0 s of sim per 600 s wall).
#: `EPISODE_TIMEOUT_S` is the **soft per-episode wall budget** the collector
#: arms on the task: when one attempt exceeds it, the attempt is skipped and
#: retried; the belt is never stopped. `HARD_EPISODE_S` (0 = off) caps a whole
#: chunk in the hard guard.
GUARD_STALL_S = float(os.environ.get("FRUIT_COLLECT_STALL_S", "600"))
GUARD_MIN_PROGRESS_S = float(os.environ.get("FRUIT_COLLECT_MIN_PROGRESS_S", "5"))
EPISODE_TIMEOUT_S = float(os.environ.get("FRUIT_COLLECT_EPISODE_S", "600"))
HARD_EPISODE_S = float(os.environ.get("FRUIT_COLLECT_HARD_EPISODE_S", "0"))
GUARD_INTERVAL_S = float(os.environ.get("FRUIT_COLLECT_GUARD_INTERVAL_S", "20"))
#: Two-line collection: max attempts per `run_bimanual` call. Chunking lets the
#: loop stop once `FRUIT_EPISODES` successes are recorded instead of spending
#: the whole attempt budget.
TWO_LINE_CHUNK = int(os.environ.get("FRUIT_COLLECT_CHUNK", "24"))
TWO_LINE = (
    os.environ.get("FRUIT_BIARM", "0") == "1"
    and os.environ.get("FRUIT_BIARM_TWOLINE", "0") == "1"
)


def advance(steps: int) -> None:
    """Advance the feeder exactly, then pump the camera/sensor callbacks.

    `update_app(steps=N)` is not a fixed step (WORKLOG: sixty calls advanced 118
    ticks on one run and 120 on the next) and the collector's inter-episode feed
    is a scripted path, so route it through `SimulationManager.step` and keep the
    pump-only `update_app(steps=0)` - the sensors starve without it.
    """
    if FIXED_STEPPING and SimulationManager is not None:
        SimulationManager.step(steps=steps)
        app_utils.update_app(steps=0)
    else:
        app_utils.update_app(steps=steps)


def _md5(path: str) -> str:
    import hashlib

    try:
        with open(path, "rb") as handle:
            return hashlib.md5(handle.read()).hexdigest()
    except OSError:
        return ""


def write_manifest(out_dir: str, cfg: SceneConfig) -> None:
    """Record what produced this shard: sources, configs, seed, knobs.

    The index alone cannot tell two datasets apart; a policy number is only
    quotable with the tree that collected it (AGENTS: a run is one sample of a
    configuration). Written before the first episode, so even a failed shard is
    identifiable afterwards. The `supply` block pins the scattered-supply
    parameters (v9/V1) next to the seed they were drawn with: a shard's class
    mix and gap distribution are part of its provenance. The `collection`
    block pins the W3 two-line/wave/routing/stall-guard knobs.
    """
    import json
    import time

    from fruit_sorting.fruits import SupplyPlan

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    sources = [
        "src/fruit_sorting/tasks.py",
        "src/fruit_sorting/assets.py",
        "src/fruit_sorting/conveyor.py",
        "src/fruit_sorting/scene.py",
        "src/fruit_sorting/fruits.py",
        "src/fruit_sorting/dataset.py",
        "src/fruit_sorting/bimanual.py",
        "scripts/40_collect_demos.py",
        "configs/waypoints.json",
        "configs/motion_reference.json",
    ]
    supply = SupplyPlan.from_env(cfg)
    manifest = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "episodes": EPISODES,
        "seed": os.environ.get("SEED", "21"),
        "camera_res": os.environ.get("FRUIT_CAMERA_RES", ""),
        "fixed_stepping": FIXED_STEPPING,
        "collection": {
            "mode": "two_line" if TWO_LINE else "single_arm",
            "biarm": os.environ.get("FRUIT_BIARM", "0"),
            "biarm_twoline": os.environ.get("FRUIT_BIARM_TWOLINE", "0"),
            "grade_routing": os.environ.get("FRUIT_GRADE_ROUTING", "auto"),
            "station_l": os.environ.get("FRUIT_BIARM_STATION_L", "0.0"),
            "station_r": os.environ.get("FRUIT_BIARM_STATION_R", "-0.10"),
            "capture_token": os.environ.get("FRUIT_BIARM_CAPTURE_TOKEN", "auto"),
            "catch_lead_l": os.environ.get("FRUIT_BIARM_CATCH_LEAD_L", "0.0"),
            "park_bias": os.environ.get("FRUIT_BIARM_PARK_BIAS", "0.0"),
            "start_gap": os.environ.get("FRUIT_BIARM_START_GAP", "0.0"),
            "chunk": TWO_LINE_CHUNK,
            "stall_guard_s": GUARD_STALL_S,
            "min_progress_s": GUARD_MIN_PROGRESS_S,
            "episode_timeout_s": EPISODE_TIMEOUT_S,
            "hard_episode_s": HARD_EPISODE_S,
        },
        "supply": {
            "scatter": supply.scatter,
            "pool": supply.pool,
            "gap_min": supply.gap_min,
            "gap_max": supply.gap_max,
            "x_min": supply.x_min,
            "x_max": supply.x_max,
            "stream": supply.stream,
            "target": supply.target,
            "target_from": supply.target_from,
            "wave": supply.wave,
            "wave_size": supply.wave_size,
            "wave_gap_min": supply.wave_gap_min,
            "wave_gap_max": supply.wave_gap_max,
            "wave_sep_min": supply.wave_sep_min,
            "wave_sep_max": supply.wave_sep_max,
            "grades": {key: weight for key, weight in supply.grades},
            "classes": {key: weight for key, weight in supply.classes},
        },
        "md5": {name: _md5(os.path.join(root, name)) for name in sources},
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    say(f"[collect] manifest -> {os.path.join(out_dir, 'manifest.json')}")


def _stall_dump(trigger: str, detail: str) -> None:
    """Log the wedge, dump thread stacks, exit non-zero (the shard restarts)."""
    message = f"[collect] STALL ({trigger}): {detail}"
    print(message, flush=True)
    try:
        say(message)
    except Exception:  # noqa: BLE001
        pass
    try:
        faulthandler.dump_traceback()
    except Exception:  # noqa: BLE001
        pass
    os._exit(3)


class StallGuard(threading.Thread):
    """Hard-fallback watchdog for a fully wedged collection shard.

    The primary guard is the soft per-episode timeout (`attempt.episode_timeout_s`,
    enforced in `tasks._step_sim`): it skips and retries an over-budget attempt
    without touching the belt. This thread is the last resort for a **blocked
    C++ call** the Python deadline cannot interrupt (the 2026-10-10 wedges were
    a blocking `RenderingManager.render()` under the bimanual bridge):

    * **progress window**: over the last `stall_s` seconds of wall time the
      physics clock (`task._sim_time`) must have advanced by at least
      `min_progress_s` seconds of simulated time. A healthy run advances
      0.2-0.5 s of sim per second of wall (>= 100 s per 600 s window); the
      wedge measured ~0 s of sim per 600 s of wall while burning CPU, so a
      plain "clock unchanged" test misses it (the clock can creep by one
      tick). `min_progress_s=5` is a wide margin (20x below a healthy window);
    * **optional chunk cap**: with `episode_s > 0`, a chunk running longer
      than that exits too (default 0 = off; the soft timeout covers livelocks).

    On either trigger the shard exits with a thread-stack dump
    (`os._exit(3)`), so the driver can restart it; it never touches the belt.
    """

    def __init__(self, sim_time_fn, stall_s: float, episode_s: float,
                 interval_s: float = 20.0, min_progress_s: float = 5.0):
        super().__init__(name="collect-stall-guard", daemon=True)
        self.sim_time_fn = sim_time_fn
        self.stall_s = float(stall_s)
        self.episode_s = float(episode_s)
        self.interval_s = max(1.0, float(interval_s))
        self.min_progress_s = float(min_progress_s)
        self._window_start = time.monotonic()
        self._window_sim: float | None = None
        self._episode_start = time.monotonic()
        self._label = "startup"
        self._lock = threading.Lock()

    def episode_started(self, label: str) -> None:
        with self._lock:
            self._episode_start = time.monotonic()
            self._label = label

    def run(self) -> None:
        while True:
            time.sleep(self.interval_s)
            now = time.monotonic()
            try:
                sim = float(self.sim_time_fn())
            except Exception:  # noqa: BLE001 - a read failure disables that check
                sim = None
            if sim is not None:
                if self._window_sim is None:
                    self._window_sim = sim
                    self._window_start = now
                elif self.stall_s > 0 and now - self._window_start >= self.stall_s:
                    advanced = sim - self._window_sim
                    if advanced < self.min_progress_s:
                        _stall_dump(
                            "physics progress",
                            f"sim clock advanced {advanced:.2f}s in "
                            f"{now - self._window_start:.0f}s wall "
                            f"(minimum {self.min_progress_s:.1f}s) during "
                            f"{self._label}",
                        )
                    self._window_sim = sim
                    self._window_start = now
            if self.episode_s > 0 and now - self._episode_start > self.episode_s:
                _stall_dump(
                    "episode timeout",
                    f"{self._label} has run for "
                    f"{now - self._episode_start:.0f}s (cap {self.episode_s:.0f}s)",
                )


def collect_two_line(task: PickAndPlaceTask, spawner: FruitSpawner,
                     guard: StallGuard) -> tuple[int, int]:
    """Two-line collection: chunked `run_bimanual`, per-arm episodes recorded.

    Returns `(successes, attempts)`. Each attempt records its own episode
    (recorder auto-index); the chunking stops as soon as `EPISODES` successful
    episodes exist, so the attempt budget is a cap rather than a quota.
    """
    stations = {
        "left": float(os.environ.get("FRUIT_BIARM_STATION_L", "0.0")),
        "right": float(os.environ.get("FRUIT_BIARM_STATION_R", "-0.10")),
    }
    saved = 0
    attempts = 0
    timed_out = 0
    while saved < EPISODES and attempts < EPISODES * 3:
        take = min(max(1, TWO_LINE_CHUNK), EPISODES * 3 - attempts)
        # A collection "shift": clear the per-fruit reject counters so a hard
        # fruit is retried after a chunk. Without this a permanently diverted
        # fruit could empty one arm's grade out of the pool (the pool is
        # finite and recycled), and one arm would starve for the rest of the
        # shard.
        task.failures.clear()
        guard.episode_started(f"two-line chunk after {attempts} attempts")
        made = task.run_bimanual(take)
        if not made:
            say("[collect] two-line batch launched no attempt; stopping")
            break
        for offset, result in enumerate(made, start=1):
            if any("timed out" in str(note) for note in result.notes):
                timed_out += 1
            say(
                f"[collect] two-line attempt {attempts + offset}: "
                f"{result.category} grade={result.grade} arm={result.arm} "
                f"station_y={stations.get(result.arm, 0.0):+.3f} "
                f"grasped={result.grasped} placed={result.placed} lift="
                f"{result.peak_lift:+.3f} notes={result.notes}"
            )
            if result.success:
                saved += 1
        attempts += len(made)
        guard.episode_started("two-line inter-chunk feed")
        task.go_ready()
        for _ in range(40):
            advance(1)
            spawner.update(task._sim_time())
            spawner.enforce_transport()
    if timed_out:
        say(
            f"[collect] {timed_out} attempt(s) skipped by the per-episode "
            "watchdog (retryable, line never stopped)"
        )
    return saved, attempts


def main() -> int:
    cfg = SceneConfig()
    write_manifest(OUT_DIR, cfg)
    scene = SortingScene(cfg).build()

    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "21")))
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    spawner.prime(count=6)

    task = PickAndPlaceTask(scene, spawner, tactile, cfg)
    task.recorder = EpisodeRecorder(OUT_DIR, decimation=4, auto_index=TWO_LINE)
    #: Soft per-episode watchdog: `_step_sim` aborts an attempt that runs past
    #: this wall budget; the collector skips it and retries. The belt is never
    #: stopped and the catch stays the never-stop dynamic one.
    task.episode_timeout_s = EPISODE_TIMEOUT_S
    task.go_ready()

    guard = StallGuard(
        task._sim_time, GUARD_STALL_S, HARD_EPISODE_S, GUARD_INTERVAL_S,
        GUARD_MIN_PROGRESS_S,
    )
    guard.start()
    dynamic = task._dynamic_pick_mode(openarm=True, scripted=True)
    say(
        f"[collect] mode={'two_line' if TWO_LINE else 'single_arm'} "
        f"episodes={EPISODES} soft_timeout={EPISODE_TIMEOUT_S:.0f}s "
        f"hard_window={GUARD_STALL_S:.0f}s dynamic={dynamic} "
        f"FRUIT_DYNAMIC_PICK={os.environ.get('FRUIT_DYNAMIC_PICK', 'unset')} "
        f"sheet={'on' if spawner.supply.wave else 'off'}"
    )
    if not dynamic:
        say(
            "[collect] ERROR: the collector refuses the indexed line "
            "(FRUIT_DYNAMIC_PICK=0): the pick must stay the never-stop catch"
        )
        app_utils.pause()
        return 2

    if TWO_LINE:
        # Fail loudly before spending the batch instead of silently collecting
        # the wrong scenario (the check also covers the recorder hand).
        if not task.bimanual_enabled():
            say("[collect] ERROR: two-line requested but bimanual_enabled() is False")
            app_utils.pause()
            return 2
        saved, attempts = collect_two_line(task, spawner, guard)
    else:
        attempts = 0
        saved = 0
        while saved < EPISODES and attempts < EPISODES * 3:
            attempts += 1
            for _ in range(40):
                advance(1)
                spawner.update(task._sim_time())
                spawner.enforce_transport()
            target = task.select_target(spawner.state())
            if target is None:
                continue
            bin_index = 0 if target["grade"] == "A" else 1
            os.environ["FRUIT_EPISODE_INDEX"] = str(saved)
            guard.episode_started(f"single-arm attempt {attempts}")
            try:
                result = task.run(
                    target, bin_index, verbose=os.environ.get("FRUIT_VERBOSE", "0") == "1"
                )
            except AttemptTimeout as exc:
                say(
                    f"[collect] attempt {attempts}: timed out ({exc}); skipped, "
                    "retrying (line still running)"
                )
                task.go_ready()
                continue
            except Exception as exc:  # noqa: BLE001
                say(f"episode failed: {exc}")
                continue
            say(
                f"episode {saved}: {result.category} grade={result.grade} arm={result.arm} "
                f"grasped={result.grasped} placed={result.placed} notes={result.notes}"
            )
            if result.success:
                saved += 1
            task.go_ready()

    guard.episode_started("shutdown")
    gate_open = float(task.stats.get("gate_open_ticks", 0.0)) * DT
    say(
        f"collected {saved} successful episodes into {OUT_DIR} "
        f"(attempts={attempts}) dynamic_check: gate_open={gate_open:.2f}s "
        "total (0.0 = never stopped; FRUIT_DYNAMIC_PICK unset never indexes)"
    )
    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
