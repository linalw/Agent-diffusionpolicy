"""Episode recording for imitation learning.

Each episode is one pick-and-place cycle, saved as a compressed ``.npz`` plus a
line in a JSON index. The recorded fields follow the schema agreed in the design
document: head-camera observations, the goal conditioning vector, proprioception,
tactile, and the action the scripted controller issued.
"""

from __future__ import annotations

import json
import os
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


class EpisodeRecorder:
    """Samples observations and actions at a fixed decimation of the physics rate."""

    def __init__(self, out_dir: str = "datasets/demos", decimation: int | None = None):
        self.out_dir = out_dir
        if decimation is None:
            decimation = int(os.environ.get("FRUIT_DECIMATION", "4"))
        self.decimation = max(1, int(decimation))
        self._counter = 0
        self._frames: list[dict] = []
        self.meta: EpisodeMeta | None = None
        os.makedirs(out_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    def begin(self, meta: EpisodeMeta) -> None:
        self.meta = meta
        self._frames = []
        self._counter = 0

    @property
    def recording(self) -> bool:
        return self.meta is not None

    def tick(self) -> bool:
        """Advance the decimation counter; returns True when this step is sampled."""
        self._counter += 1
        return self._counter % self.decimation == 0

    def add(self, observation: dict, action: np.ndarray | None = None) -> None:
        frame = {k: np.asarray(v) for k, v in observation.items() if v is not None}
        if action is not None:
            frame["action"] = np.asarray(action, dtype=np.float32)
        self._frames.append(frame)

    # ------------------------------------------------------------------ #
    def save(self, success: bool, notes: list[str] | None = None) -> str | None:
        if self.meta is None:
            return None
        if not self._frames:
            self.meta = None
            return None
        if not success:
            # Failed attempts would otherwise overwrite the previous attempt's
            # file, since the index is the success count.
            self.meta = None
            self._frames = []
            return None
        if not self._frames:
            self.meta = None
            return None

        self.meta.success = success
        self.meta.notes = list(notes or [])
        arrays = {
            key: np.stack([f[key] for f in self._frames])
            for key in self._frames[0]
        }
        path = os.path.join(self.out_dir, f"episode_{self.meta.index:05d}.npz")
        np.savez_compressed(path, **arrays)
        self._append_index(path, arrays)
        say(f"saved {path} ({len(self._frames)} frames, success={success})")
        self.meta = None
        self._frames = []
        return path

    def _append_index(self, path: str, arrays: dict) -> None:
        index_path = os.path.join(self.out_dir, "index.json")
        entries = []
        if os.path.exists(index_path):
            with open(index_path, encoding="utf-8") as fh:
                entries = json.load(fh)
        entries.append(
            {
                "file": os.path.basename(path),
                "index": self.meta.index,
                "category": self.meta.category,
                "grade": self.meta.grade,
                "arm": self.meta.arm,
                "bin_index": self.meta.bin_index,
                "diameter": self.meta.diameter,
                "success": self.meta.success,
                "notes": self.meta.notes,
                "frames": int(arrays["action"].shape[0]) if "action" in arrays else 0,
            }
        )
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
