"""Episode recording for imitation learning.

Each episode is one pick-and-place cycle, saved as a compressed ``.npz`` plus a
line in a JSON index. The recorded fields follow the schema agreed in the design
document: head-camera observations, the goal conditioning vector, proprioception,
tactile, and the action the scripted controller issued.

W3 (two-line collection): the two arms run in concurrent attempt threads, so the
recorder keeps its episode buffer **per thread** and writes the index under a
lock. A new index field (``station_y``) labels which pick station the episode's
arm worked; it is additive - old entries and readers that do not know it are
unaffected. ``auto_index=True`` makes the recorder allocate unique episode
indices itself, which the two-line collector needs because a process-wide
``FRUIT_EPISODE_INDEX`` cannot label two concurrent attempts.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field

import numpy as np

from .common import say, to_numpy


@dataclass
class EpisodeMeta:
    index: int
    category: str
    grade: str
    arm: str
    bin_index: int
    diameter: float = 0.0
    success: bool = False
    notes: list[str] = field(default_factory=list)
    #: Pick-station Y [m] of the arm that ran this episode (W3 two-line schema
    #: addition). 0.0 for every single-arm episode; readers that predate it
    #: simply ignore it.
    station_y: float = 0.0


class _RecorderState:
    """One attempt thread's in-flight episode."""

    __slots__ = ("meta", "frames", "counter")

    def __init__(self):
        self.meta: EpisodeMeta | None = None
        self.frames: list[dict] = []
        self.counter: int = 0


class EpisodeRecorder:
    """Samples observations and actions at a fixed decimation of the physics rate."""

    def __init__(self, out_dir: str = "datasets/demos", decimation: int | None = None,
                 auto_index: bool = False):
        self.out_dir = out_dir
        if decimation is None:
            decimation = int(os.environ.get("FRUIT_DECIMATION", "4"))
        self.decimation = max(1, int(decimation))
        #: Allocate the episode index inside the recorder (unique even when two
        #: attempt threads record at once). Off keeps the caller's `meta.index`
        #: (the single-arm collector's `FRUIT_EPISODE_INDEX` contract).
        self.auto_index = bool(auto_index)
        self._local = threading.local()
        #: Guards index allocation and the `index.json` read-modify-write, which
        #: two attempt threads can otherwise interleave.
        self._lock = threading.Lock()
        self._next_index = 0
        os.makedirs(out_dir, exist_ok=True)

    def _state(self) -> _RecorderState:
        state = getattr(self._local, "state", None)
        if state is None:
            state = _RecorderState()
            self._local.state = state
        return state

    @property
    def meta(self) -> EpisodeMeta | None:
        return self._state().meta

    @meta.setter
    def meta(self, value: EpisodeMeta | None) -> None:
        self._state().meta = value

    @property
    def _frames(self) -> list[dict]:
        return self._state().frames

    @_frames.setter
    def _frames(self, value: list[dict]) -> None:
        self._state().frames = value

    @property
    def _counter(self) -> int:
        return self._state().counter

    @_counter.setter
    def _counter(self, value: int) -> None:
        self._state().counter = value

    def _allocate_index(self) -> int:
        with self._lock:
            index = self._next_index
            self._next_index += 1
            return index

    # ------------------------------------------------------------------ #
    def begin(self, meta: EpisodeMeta) -> None:
        if self.auto_index:
            meta.index = self._allocate_index()
        state = self._state()
        state.meta = meta
        state.frames = []
        state.counter = 0

    @property
    def recording(self) -> bool:
        return self._state().meta is not None

    def tick(self) -> bool:
        """Advance the decimation counter; returns True when this step is sampled."""
        state = self._state()
        state.counter += 1
        return state.counter % self.decimation == 0

    def add(self, observation: dict, action: np.ndarray | None = None) -> None:
        frame = {k: np.asarray(v) for k, v in observation.items() if v is not None}
        if action is not None:
            frame["action"] = np.asarray(action, dtype=np.float32)
        self._state().frames.append(frame)

    # ------------------------------------------------------------------ #
    def save(self, success: bool, notes: list[str] | None = None) -> str | None:
        state = self._state()
        meta = state.meta
        if meta is None:
            return None
        if not state.frames:
            state.meta = None
            return None
        if not success:
            # Failed attempts would otherwise overwrite the previous attempt's
            # file, since the index is the success count.
            state.meta = None
            state.frames = []
            return None

        meta.success = success
        meta.notes = list(notes or [])
        arrays = {
            key: np.stack([f[key] for f in state.frames])
            for key in state.frames[0]
        }
        path = os.path.join(self.out_dir, f"episode_{meta.index:05d}.npz")
        np.savez_compressed(path, **arrays)
        self._append_index(path, arrays, meta)
        say(f"saved {path} ({len(state.frames)} frames, success={success})")
        state.meta = None
        state.frames = []
        return path

    def _append_index(self, path: str, arrays: dict, meta: EpisodeMeta) -> None:
        index_path = os.path.join(self.out_dir, "index.json")
        name = os.path.basename(path)
        record = {
            "file": name,
            "index": meta.index,
            "category": meta.category,
            "grade": meta.grade,
            "arm": meta.arm,
            "bin_index": meta.bin_index,
            "diameter": meta.diameter,
            "success": meta.success,
            "notes": meta.notes,
            "frames": int(arrays["action"].shape[0]) if "action" in arrays else 0,
            #: W3 schema addition (see `EpisodeMeta.station_y`).
            "station_y": float(meta.station_y),
        }
        # A collector restarted onto an existing output directory re-uses the
        # episode filenames, so this file name may already have an entry that
        # describes the *previous* content (and its frame count). Replace it
        # instead of appending a second, stale row: two rows for one file made the
        # merge copy the same episode twice and carry the old frame count into the
        # dataset (WORKLOG "the dataset index did not match the dataset").
        # The lock covers the whole read-modify-write: the two-line collector
        # saves from two attempt threads concurrently.
        with self._lock:
            entries = []
            if os.path.exists(index_path):
                with open(index_path, encoding="utf-8") as fh:
                    entries = json.load(fh)
            for position, existing in enumerate(entries):
                if existing.get("file") == name:
                    entries[position] = record
                    break
            else:
                entries.append(record)
            with open(index_path, "w", encoding="utf-8") as fh:
                json.dump(entries, fh, indent=2)


def camera_observation(camera_sensor, annotators: tuple[str, ...]) -> dict:
    """Pull the head-camera frames the policy conditions on."""
    observation: dict = {}
    for name in annotators:
        data = camera_sensor.get_data(name)
        array = to_numpy(data)
        if array is None:
            continue
        observation[f"image_{name}"] = array
    return observation
