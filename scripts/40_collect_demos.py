"""Collect scripted demonstrations into datasets/demos.

    FRUIT_EPISODES=20 scripts/run.sh scripts/40_collect_demos.py

Two modes, selected by the P85 scheduler resolution
(`fruit_sorting.bimanual.biarm_resolution`, the same call the pick-and-place
entry uses):

* **two-line (P85 shipped default: `FRUIT_BIARM` and `FRUIT_BIARM_TWOLINE` both
  default `1`)**: the whole collection runs
  through `task.run_bimanual`, which drives both arms on their own stations.
  Each attempt is recorded as its own episode with a per-episode arm/station
  label (`EpisodeMeta.station_y`), and the recorder allocates unique episode
  indices itself because the process-wide `FRUIT_EPISODE_INDEX` cannot label two
  concurrent attempts.
* **single arm (`FRUIT_BIARM=0`)**: the collector feeds the line between
  attempts and records one episode per successful `task.run` - the pre-P85
  shipped mode, byte-unchanged.

The shard manifest records **both** the raw environment values and the
resolved pair with its origin (`collection.biarm_resolved`,
`collection.biarm_twoline_resolved`, `collection.biarm_defaulted`,
`collection.biarm_twoline_defaulted`), because after P85 an unset
`FRUIT_BIARM` means "on" - the raw `biarm: "0"` field alone would make a
post-flip shard look exactly like a pre-flip single-arm one. A manifest
without those keys predates P85.

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
from fruit_sorting.bimanual import biarm_resolution
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.dataset import EpisodeRecorder
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.tasks import (
    AttemptTimeout,
    PickAndPlaceTask,
    prepose_clear_resolution,
)

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
#: P85: the scheduler pair resolves through `fruit_sorting.bimanual` - the same
#: single-sited call the pick-and-place entry uses - so an unset `FRUIT_BIARM`
#: now means the bimanual two-line (the owner's sign-off). `FRUIT_BIARM=0`
#: restores the pre-P85 single arm and `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`
#: the F2 shared-station pipeline (which this collector drives through the same
#: `run_bimanual` call).
SCHEDULER = biarm_resolution()
TWO_LINE = bool(SCHEDULER["twoline"])
#: P96: the pre-pose clearance resolution this shard runs (`prepose_clear`
#: below). Resolved here, not read back off the task, so the manifest is
#: written before the first episode exactly like the other collection keys.
PREPOSE = prepose_clear_resolution(TWO_LINE)
BIARM = bool(SCHEDULER["biarm"])


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


def _physics_provenance() -> dict:
    """The resolved physics that sets the grip (P41 phase 2).

    A store is reusable only if its *contact forces* are identifiable: P41's
    finger-drive profile moves the delivered pinch 2.2x (4.4 -> 9.8 N per
    pinch) without touching a single trajectory, and `FRUIT_SUBSTEPS` reaches
    the same force at 3.08x wall. Neither left a trace in a pre-P41 manifest,
    so a pre/post-profile shard was indistinguishable by its own metadata
    (`logs/p41/FIDELITY_SWEEP.md` section 6.6). This block names the profile,
    the physics rate and the contact *pair*.

    The block itself lives in `fruit_sorting.scene.finger_physics_provenance`,
    so the collector's shards and the direct env's rollout manifests cannot
    drift apart (P41 phase 4 A2). `finger_drive` is written here as the
    env-resolved pair and **replaced at task start** by
    `update_manifest_physics`, which reads the articulations' real gains and
    caps back (`get_dof_gains` / `get_dof_max_efforts`); `joint2`'s 0.0 N cap is
    why the second jaw face cannot push (phase 1: the byte-identical
    `rho_asset` cell).

    `two_line` (P87) is this shard's scheduler mode: the release clock is a
    **two-line-scoped** default (`tasks.release_speed_resolution`), so a shard's
    `physics.release` must name the scope it was recorded under or a post-P87
    two-line store and a single-arm one would carry the same block while running
    76 ticks apart per placed attempt.
    """
    from fruit_sorting.scene import finger_physics_provenance

    return finger_physics_provenance(control_dt=DT, two_line=TWO_LINE, scripted=True)


def _scene_provenance(cfg) -> dict:
    """The scene's collider set (P72), so a shard names its rail/lift geometry.

    The block itself lives in `fruit_sorting.assets.scene_provenance` (pure
    `SceneConfig` arithmetic, so it imports without the simulator and the
    offline selfcheck leg executes it), shared with the direct env's rollout
    manifest so the two writers cannot drift apart (the P41 `physics` rule).
    The collector is a scripted path: `lift` is written `None` there by
    construction (the lift rung is the direct env's alone - this script never
    constructs it), and the fields that
    matter are the rail mode/proud and the output slab's top z and inboard edge
    - the surface a post-P71 store was recorded across.
    """
    from fruit_sorting.assets import scene_provenance

    return scene_provenance(cfg)


def _supply_band_provenance(plan) -> dict:
    """The supply band and mix (P93), so a shard names what the pool was built from.

    Same builder the direct env's rollout manifest calls
    (`fruit_sorting.assets.supply_provenance`): one function, both writers, so a
    collection store and a direct store name their band the same way. Pure
    `SupplyPlan` arithmetic - no simulator, no state.
    """
    from fruit_sorting.assets import supply_provenance

    return supply_provenance(plan)


def update_manifest_physics(out_dir: str, task) -> None:
    """Replace the manifest's env-resolved finger drive with the runtime read-back.

    Called once the task (and therefore both articulations) exist, before the
    first episode. The manifest is already on disk, so a build that fails
    before this point still leaves the env-resolved block rather than nothing.
    Gains **and caps** are read per finger joint on **both** arms: the profile
    is programmed in `ArmController.__init__`, and the read-back is what shows
    `joint2`'s cap staying at 0.0. `readback_matches` compares the caps too, so
    a `nan`/absent cap cannot read like an `mf10` shard (P41 phase 4 A4).
    """
    import json

    from fruit_sorting.scene import finger_physics_provenance

    path = os.path.join(out_dir, "manifest.json")
    try:
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError):
        say(f"[collect] physics read-back skipped: no manifest at {path}")
        return
    block = finger_physics_provenance(arms=task.arms, control_dt=DT, two_line=TWO_LINE, scripted=True)
    physics = manifest.setdefault("physics", {})
    physics.update(block)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    drive = physics.get("finger_drive", {})
    rows = drive.get("joints") or {}
    #: P227t: the read-back's own first row - the joint *names* are the arm's
    #: (the OpenArm's `openarm_left_finger_joint1`, the Panda's
    #: `panda_finger_joint1`), so looking up the OpenArm key made every other
    #: arm's shard print "no finger joints found" while its manifest carried the
    #: rows.
    first = next(iter(rows.values()), None)
    if first is None:
        say(
            "[collect] physics read-back: no finger joints found "
            f"({drive.get('why', 'no rows')})"
        )
        return
    say(
        "[collect] physics read-back: "
        f"profile={physics.get('profile')} "
        f"k={first['k']:.0f} N/m c={first['c']:.0f} Ns/m "
        f"maxForce={first['maxForce']:.1f}N "
        f"matches={drive.get('readback_matches')} "
        f"c/k={physics.get('c_over_k')}"
    )


def write_manifest(out_dir: str, cfg: SceneConfig) -> None:
    """Record what produced this shard: sources, configs, seed, knobs.

    The index alone cannot tell two datasets apart; a policy number is only
    quotable with the tree that collected it (AGENTS: a run is one sample of a
    configuration). Written before the first episode, so even a failed shard is
    identifiable afterwards. `episodes_target` is the collection *quota*, not
    the recorded count: the two-line collector records every success in its
    last chunk, so the shard's `index.json` can hold more than the target (the
    dense W3 shard recorded 158 against a 150 target). Read the actual count
    from `index.json`. The `supply` block pins the scattered-supply
    parameters (v9/V1) next to the seed they were drawn with: a shard's class
    mix and gap distribution are part of its provenance. The `collection`
    block pins the W3 two-line/wave/routing/stall-guard knobs.
    `src/fruit_sorting/meshes.py` is a source since P32 phase B: the fruit
    profile decides the number of per-instance RNG draws, so it moves the
    supply stream and every authored mesh - a shard's md5 pin is what tells a
    post-pear collection from a pre-pear one (a manifest without the key is
    pre-pear).
    `src/fruit_sorting/bed.py` is a source since the P32 phase-D remediation:
    its `BedSchedule` owns the bed's row/pitch draws, so a `FRUIT_SUPPLY_BED=1`
    shard without the pin was indistinguishable from a scatter shard and a
    `bed.py` edit moved no md5 (Gate D condition C1). The `supply` block gains
    a `bed` geometry record only when the bed is on, so every pre-bed manifest
    keeps its meaning.
    P41 phase 2 adds the `physics` block (see `_physics_provenance`): the finger
    drive, the physics rate and the contact pair. A profile flip moves the
    delivered pinch 2.2x without moving a trajectory, so a store recorded under
    it is identified by this block, not by its md5 pins alone.
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
        "src/fruit_sorting/bed.py",
        "src/fruit_sorting/meshes.py",
        "src/fruit_sorting/dataset.py",
        "src/fruit_sorting/bimanual.py",
        # P41 phase 2: the finger drive decides the grip force, and the profile
        # is programmed here - `control.py` / `common.py` were unpinned, so no
        # manifest could tell a pre-profile shard from a post-profile one.
        "src/fruit_sorting/control.py",
        "src/fruit_sorting/common.py",
        "scripts/40_collect_demos.py",
        "configs/waypoints.json",
        "configs/motion_reference.json",
    ]
    # P85: the manifest must describe the **plan the spawner runs**, so it takes
    # the same resolved scheduler the spawner gets (`two_line=TWO_LINE`). Without
    # it a defaulted two-line shard recorded `wave=false` and the 50/30/20 mix
    # while running the dense sheet and the balanced mix - the provenance would
    # contradict the run.
    supply = SupplyPlan.from_env(cfg, TWO_LINE)
    manifest = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        # The collection quota, not the recorded count: the collector records
        # every success in its last chunk, so `index.json` can hold more (the
        # dense W3 shard: 158 recorded against this 150 target).
        "episodes_target": EPISODES,
        "seed": os.environ.get("SEED", "21"),
        "camera_res": os.environ.get("FRUIT_CAMERA_RES", ""),
        "fixed_stepping": FIXED_STEPPING,
        "collection": {
            "mode": "two_line" if TWO_LINE else "single_arm",
            "biarm": os.environ.get("FRUIT_BIARM", "0"),
            "biarm_twoline": os.environ.get("FRUIT_BIARM_TWOLINE", "0"),
            # P85: the **resolved** pair and its origin. After the flip an
            # unset `FRUIT_BIARM` means "on", so the two raw fields above
            # (`"0"` when unset) would make a post-flip defaulted shard
            # indistinguishable from a pre-flip single-arm one. A manifest
            # without these four keys predates P85; `*_defaulted` follows the
            # P43 `arm_park.defaulted` rule (`true` = the shipped default,
            # `false` = an explicit environment value).
            "biarm_resolved": int(BIARM),
            "biarm_twoline_resolved": int(TWO_LINE),
            "biarm_defaulted": bool(SCHEDULER["biarm_defaulted"]),
            "biarm_twoline_defaulted": bool(SCHEDULER["twoline_defaulted"]),
            "grade_routing": os.environ.get("FRUIT_GRADE_ROUTING", "auto"),
            "station_l": os.environ.get("FRUIT_BIARM_STATION_L", "0.0"),
            "station_r": os.environ.get("FRUIT_BIARM_STATION_R", "-0.10"),
            "capture_token": os.environ.get("FRUIT_BIARM_CAPTURE_TOKEN", "auto"),
            "catch_lead_l": os.environ.get("FRUIT_BIARM_CATCH_LEAD_L", "0.0"),
            # W7-A: the park-gate lever resolves through `_dynamic_profile`, so
            # an unset env means **on for a two-line session** (`auto` here
            # records that; `0`/`1` record an explicit override). Without this
            # field a post-W7-A two-line shard is identified only by its
            # `tasks.py` md5 pin (`logs/w7/A_RESULTS.md` section 6).
            "park_early": os.environ.get("FRUIT_BIARM_PARK_EARLY", "auto"),
            # P10-C.3: the two-line carry-monitor default flip resolves through
            # `_dynamic_profile` (tasks.py `_resolve_carry_monitor_knobs`), so
            # an unset env means **on for a two-line session** (`auto` records
            # that; an explicit `0`/`1` records the override). The W7-C.1
            # `park_early` pattern; a post-flip two-line recollection is a new
            # branch and this field identifies it next to the `tasks.py` md5
            # pin (`logs/p10c2/PREREG_ADOPT_FLIP.md`, the collector guardrail).
            "carry_monitor": os.environ.get("FRUIT_CARRY_MONITOR", "auto"),
            # P33 phase 3 (Gate 3, L3): the two-line mid-attempt feeder cadence
            # (`FRUIT_FEED_CADENCE=1` arms the same `_feed_tick` as a shared-tick
            # pump; default off). Recorded like `park_early`: the raw env value,
            # so an unset env reads `0` - the default. A manifest without this
            # key (every store up to `datasets/p33_pear`) predates the field and
            # means the same default (`0`); it is not evidence that the pump ran.
            "feed_cadence": os.environ.get("FRUIT_FEED_CADENCE", "0"),
            "park_bias": os.environ.get("FRUIT_BIARM_PARK_BIAS", "0.0"),
            # P96: the **pre-pose clearance pose** this shard runs. The two-line
            # pre-pose is held for 65 ticks at the start of every attempt, so a
            # store recorded under the clearance pose is a different branch from
            # one recorded under the grasp-plane pre-pose - and the stations above
            # (`station_l`/`station_r`) name *where*, not *how high*. A manifest
            # **without** `prepose_clear` predates P96 (the `arm_park.defaulted`
            # convention); `prepose_clear_defaulted` is true when no env value
            # decided it, and `prepose_clear_z` is the solve height above the belt
            # top (0.0 when the cell is off, i.e. the grasp-plane pre-pose).
            "prepose_clear": int(PREPOSE["on"]),
            "prepose_clear_defaulted": bool(PREPOSE["origin"] != "explicit"),
            "prepose_clear_z": float(PREPOSE["z"]) if PREPOSE["on"] else 0.0,
            "start_gap": os.environ.get("FRUIT_BIARM_START_GAP", "0.0"),
            "chunk": TWO_LINE_CHUNK,
            "stall_guard_s": GUARD_STALL_S,
            "min_progress_s": GUARD_MIN_PROGRESS_S,
            "episode_timeout_s": EPISODE_TIMEOUT_S,
            "hard_episode_s": HARD_EPISODE_S,
            # P225d: the collector's right-arm lift target (metres above
            # `jaw_target("grasp_lift")`'s `belt_top + 0.28` base). Empty = the
            # shipped 0.28 m; "-0.08" = the 0.20 m rung. A manifest without this
            # key predates the phase; the direct env's left-only `FRUIT_LIFT_DZ`
            # never reached the collector (`resolve_lift_dz` is `direct`-scoped).
            "lift_dz_right": os.environ.get("FRUIT_COLLECT_LIFT_DZ_RIGHT", ""),
        },
        "supply": {
            #: P27/P28 provenance fix: the belt speed the shard ran at. The P27 audit found no
            #: manifest recorded it (the goal's `vy` was the only witness); the value is the
            #: configured one (`FRUIT_BELT_SPEED`, the assets.py default when unset - the same
            #: expression the SceneConfig's default_factory uses).
            "belt_speed": float(os.environ.get("FRUIT_BELT_SPEED", "0.12")),
            "scatter": supply.scatter,
            "pool": supply.pool,
            "gap_min": supply.gap_min,
            "gap_max": supply.gap_max,
            "x_min": supply.x_min,
            "x_max": supply.x_max,
            "stream": supply.stream,
            "target": supply.target,
            "target_from": supply.target_from,
            # P33 phase 3 (Gate 3, L3): these are the **env flags**, not the
            # branch the spawner ran. With both `wave` and `patch` true (the
            # two-line scenario defaults wave on, and its patch arm sets
            # patch=1) the resolved schedule is the **PATCH** - the branch
            # order is bed > patch > wave > scatter - and the `[supply]` banner
            # prints both blocks. Read the patch block for such a store; the
            # wave block is inert.
            "wave": supply.wave,
            "wave_size": supply.wave_size,
            "wave_gap_min": supply.wave_gap_min,
            "wave_gap_max": supply.wave_gap_max,
            "wave_sep_min": supply.wave_sep_min,
            "wave_sep_max": supply.wave_sep_max,
            # W7-C.1: the 2D patch sheet (W6-A) is now part of the supply
            # provenance. A patch shard's class mix, abreast-pair probability
            # and separation are set by these draws; without them two shards
            # whose `wave`/slice blocks differ only in the patch draws are
            # indistinguishable from the manifest. `patch` is false unless
            # `FRUIT_SUPPLY_PATCH=1` (and scatter on), so pre-patch shards keep
            # their meaning and no existing manifest is rewritten.
            "patch": supply.patch,
            "patch_slice_min": supply.patch_slice_min,
            "patch_slice_max": supply.patch_slice_max,
            "patch_pair": supply.patch_pair,
            "patch_sep_min": supply.patch_sep_min,
            "patch_sep_max": supply.patch_sep_max,
            "grades": {key: weight for key, weight in supply.grades},
            "classes": {key: weight for key, weight in supply.classes},
            #: P93: the same `supply.band` object the direct env's rollout
            #: manifest writes (`assets.supply_provenance`), so the two store
            #: types name their band and mix identically. The flat
            #: `x_min`/`x_max`/`grades`/`classes` above are the pre-P93 form and
            #: are kept: an existing shard is not rewritten, and a reader that
            #: predates this block still finds them.
            "band": _supply_band_provenance(supply),
        },
        "md5": {name: _md5(os.path.join(root, name)) for name in sources},
        # P41 phase 2: the grip's physics, not just the tree that ran it. See
        # `_physics_provenance` (the runtime read-back lands here after the
        # task exists).
        "physics": _physics_provenance(),
        # P72: the scene's collider set (the rail pair, the output slab's top z
        # and inboard edge, the lift rung). P71's two flips move the `[fruit]`
        # stream (8 mm release y at the same attempt) and no manifest named the
        # geometry, so a pre-P71 shard was distinguishable only by an `assets.py`
        # md5 that also moves for unrelated edits. `lift` is `None` on this
        # scripted path (the knob belongs to the direct env alone). A manifest without
        # this key predates P72.
        "scene": _scene_provenance(cfg),
    }
    # P32 phase-D remediation (Gate D C1): the bed's resolved geometry is
    # provenance too. `BedSchedule` draws the row pitch, the middle-column
    # decision and the upstream shift from its own stream, so a bed shard's
    # delivered density is not reproducible from `bed=True` alone. Recorded
    # only when the bed is on (`FRUIT_SUPPLY_BED=1`), which keeps every
    # pre-bed manifest byte-identical in meaning; a manifest without the key
    # is a non-bed shard.
    bed_plan = supply.bed_plan
    if supply.bed and bed_plan is not None:
        manifest["supply"].update({"bed": True, **bed_plan.manifest_block()})
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    say(f"[collect] manifest -> {os.path.join(out_dir, 'manifest.json')}")


def _stall_dump(trigger: str, detail: str, stats=None) -> None:
    """Log the wedge, dump thread stacks, exit non-zero (the shard restarts).

    `stats` (optional callable) flushes the collector's own physics summary
    before the exit. The guard's `os._exit(3)` skips `main`'s final line, so
    without this a wedged shard's log never carries the `gate_open=0.0 s`
    never-stop invariant the collector is built around; the W7-C
    recollection's nine shard runs all exited here (nothing adversarial, just
    missing evidence).
    """
    message = f"[collect] STALL ({trigger}): {detail}"
    print(message, flush=True)
    try:
        say(message)
    except Exception:  # noqa: BLE001
        pass

    if stats is not None:
        try:
            summary = stats()
        except Exception:  # noqa: BLE001 - a stats read must not mask the wedge
            summary = None
        if summary:
            print(summary, flush=True)
            try:
                say(summary)
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
                 interval_s: float = 20.0, min_progress_s: float = 5.0,
                 stats_fn=None):
        super().__init__(name="collect-stall-guard", daemon=True)
        self.sim_time_fn = sim_time_fn
        self.stall_s = float(stall_s)
        self.episode_s = float(episode_s)
        self.interval_s = max(1.0, float(interval_s))
        self.min_progress_s = float(min_progress_s)
        self.stats_fn = stats_fn
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
                            self.stats_fn,
                        )
                    self._window_sim = sim
                    self._window_start = now
            if self.episode_s > 0 and now - self._episode_start > self.episode_s:
                _stall_dump(
                    "episode timeout",
                    f"{self._label} has run for "
                    f"{now - self._episode_start:.0f}s (cap {self.episode_s:.0f}s)",
                    self.stats_fn,
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

    spawner = FruitSpawner(
        scene.stage,
        cfg,
        seed=int(os.environ.get("SEED", "21")),
        # P85: the collector's supply follows the resolved scheduler, exactly as
        # `20_pick_place.py`'s does, so a defaulted shard is the two-line
        # scenario end to end.
        two_line=TWO_LINE,
    )
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    spawner.prime(count=6)

    # P225d: the collector-only right low-lift rung. `resolve_lift_dz` is
    # `direct`-scoped (the direct env's left-only `FRUIT_LIFT_DZ`), so the
    # collector never read it; a right low-lift recollection needs this task
    # kwarg. Unset = `None` = the shipped `belt_top + 0.28` m, byte-inert.
    _right_lift = os.environ.get("FRUIT_COLLECT_LIFT_DZ_RIGHT", "").strip()
    _collect_lift_dz = {"right": float(_right_lift)} if _right_lift else None
    task = PickAndPlaceTask(scene, spawner, tactile, cfg, lift_dz=_collect_lift_dz)
    # P41 phase 2: the finger drive now exists on both articulations - replace
    # the manifest's env-resolved pair with the runtime read-back.
    update_manifest_physics(OUT_DIR, task)
    task.recorder = EpisodeRecorder(OUT_DIR, decimation=4, auto_index=TWO_LINE)
    #: Soft per-episode watchdog: `_step_sim` aborts an attempt that runs past
    #: this wall budget; the collector skips it and retries. The belt is never
    #: stopped and the catch stays the never-stop dynamic one.
    task.episode_timeout_s = EPISODE_TIMEOUT_S
    task.go_ready()

    def collect_stats() -> str:
        """The physics invariant, safe to call from the guard thread.

        The guard's `os._exit(3)` skips `main`'s clean-path line, so a wedged
        shard would otherwise carry no `gate_open` reading even though the
        collector never stops the belt. `gate_open_ticks` is the task's own
        counter (float, incremented on the control thread; a plain read is
        safe) and the collector already refuses the indexed line that would
        open the gate, so zero is the enforced value, not an artefact.
        """
        gate_open = float(task.stats.get("gate_open_ticks", 0.0)) * DT
        return (
            f"[collect] stats: attempts={int(task.stats['attempts'])} "
            f"successes={int(task.stats['successes'])} "
            f"gate_open={gate_open:.2f}s "
            "(0.0 = the never-stop dynamic catch throughout; "
            "the indexed line is refused at startup)"
        )

    guard = StallGuard(
        task._sim_time, GUARD_STALL_S, HARD_EPISODE_S, GUARD_INTERVAL_S,
        GUARD_MIN_PROGRESS_S, stats_fn=collect_stats,
    )
    guard.start()
    dynamic = task._dynamic_pick_mode(openarm=True, scripted=True)
    say(
        f"[collect] mode={'two_line' if TWO_LINE else 'single_arm'} "
        f"scheduler[{SCHEDULER['label']}] "
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
            # P114: the instruction's destination when one is armed, else the
            # shipped grade lane (sort_destination returns None with no
            # instruction).
            instructed = task.sort_destination(target)
            if isinstance(instructed, int):
                bin_index = int(instructed)
            else:
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
