"""Dataset for the recorded pick-and-place episodes."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np

from .skills import label_episode


@dataclass
class Normalizer:
    """Per-channel mean/std for the low-dimensional inputs and the actions."""

    action_mean: np.ndarray
    action_std: np.ndarray
    obs_mean: np.ndarray
    obs_std: np.ndarray
    goal_mean: np.ndarray
    goal_std: np.ndarray

    def normalize_action(self, action: np.ndarray) -> np.ndarray:
        return (action - self.action_mean) / self.action_std

    def denormalize_action(self, action: np.ndarray) -> np.ndarray:
        return action * self.action_std + self.action_mean

    def normalize_obs(self, obs: np.ndarray) -> np.ndarray:
        return (obs - self.obs_mean) / self.obs_std

    def normalize_goal(self, goal: np.ndarray) -> np.ndarray:
        return (goal - self.goal_mean) / self.goal_std

    def as_dict(self) -> dict:
        return {
            "action_mean": self.action_mean.tolist(),
            "action_std": self.action_std.tolist(),
            "obs_mean": self.obs_mean.tolist(),
            "obs_std": self.obs_std.tolist(),
            "goal_mean": self.goal_mean.tolist(),
            "goal_std": self.goal_std.tolist(),
        }


class EpisodeStore:
    """Loads recorded ``.npz`` episodes and slices observation/action windows."""

    #: Channels fed to the visual encoder: RGB (3) + depth (1) [+ target mask (1)].
    IMAGE_CHANNELS = 5

    def __init__(
        self,
        root: str,
        obs_horizon: int = 2,
        action_horizon: int = 16,
        image_size: int = 128,
        only_successful: bool = True,
    ):
        self.root = root
        self.obs_horizon = obs_horizon
        self.action_horizon = action_horizon
        self.image_size = image_size

        index_path = os.path.join(root, "index.json")
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"{index_path} not found - collect demonstrations first")
        with open(index_path, encoding="utf-8") as fh:
            entries = json.load(fh)
        if only_successful:
            entries = [e for e in entries if e.get("success")]
        if not entries:
            raise ValueError(f"no usable episodes in {root}")

        self.episodes: list[dict] = []
        for entry in entries:
            data = np.load(os.path.join(root, entry["file"]))
            has_mask = "target_mask" in data.files
            skills = None
            if all(k in data.files for k in ("fruit_position", "finger_opening", "goal")):
                skills = label_episode(
                    data["fruit_position"], data["finger_opening"], data["goal"]
                )
            self.episodes.append(
                {
                    "mask": (
                        (data["target_mask"].astype(np.float32) / 255.0)
                        if has_mask else None
                    ),
                    "skills": skills,
                    "rgb": data["image_rgb"],
                    "depth": data["image_distance_to_image_plane"],
                    "joint": data["joint_positions"],
                    "finger": data["finger_opening"],
                    "tactile": data["tactile"],
                    "goal": data["goal"],
                    "action": data["action"],
                    "meta": entry,
                }
            )

        # Windows must fit inside each episode.
        self.windows: list[tuple[int, int]] = []
        for ep_index, episode in enumerate(self.episodes):
            length = episode["action"].shape[0]
            last = length - self.action_horizon
            for start in range(self.obs_horizon - 1, last):
                self.windows.append((ep_index, start))
        if not self.windows:
            raise ValueError(
                f"episodes are shorter than obs_horizon + action_horizon "
                f"({self.obs_horizon} + {self.action_horizon})"
            )

    # ------------------------------------------------------------------ #
    def __len__(self) -> int:
        return len(self.windows)

    def _downsample(self, image: np.ndarray) -> np.ndarray:
        """Nearest-neighbour downsample (avoids a scipy/torchvision dependency)."""
        if image.shape[0] == self.image_size and image.shape[1] == self.image_size:
            return image
        stride_y = max(1, image.shape[0] // self.image_size)
        stride_x = max(1, image.shape[1] // self.image_size)
        cropped = image[: self.image_size * stride_y, : self.image_size * stride_x]
        return cropped[::stride_y, ::stride_x]

    def __getitem__(self, index: int) -> dict:
        ep_index, t = self.windows[index]
        episode = self.episodes[ep_index]

        # Image stack over the observation horizon, oldest first.
        frames = []
        for k in range(self.obs_horizon - 1, -1, -1):
            rgb = self._downsample(episode["rgb"][t - k]).astype(np.float32) / 255.0
            depth = self._downsample(episode["depth"][t - k][..., 0]).astype(np.float32)
            # Depth is metres; clip and normalise into a sane range for the CNN.
            depth = np.clip(depth, 0.0, 3.0) / 3.0
            channels = [rgb, depth[..., None]]
            if episode["mask"] is not None:
                # Target mask channel isolates the fruit the slow loop selected.
                mask = self._downsample(episode["mask"][t - k]).astype(np.float32)
                channels.append(mask[..., None])
            frames.append(np.concatenate(channels, axis=-1))
        image = np.stack(frames, axis=0)  # (obs_horizon, H, W, C)
        image = np.transpose(image, (0, 3, 1, 2))  # (obs_horizon, C, H, W)

        proprio = np.concatenate(
            [
                episode["joint"][t].astype(np.float32),
                episode["finger"][t].astype(np.float32),
                episode["tactile"][t].astype(np.float32),
            ]
        )
        goal = episode["goal"][t].astype(np.float32)
        action = episode["action"][t : t + self.action_horizon].astype(np.float32)
        skills = episode["skills"]
        skill = int(skills[t]) if skills is not None else 0
        return {
            "image": image,
            "proprio": proprio,
            "goal": goal,
            "action": action,
            "skill": np.int64(skill),
        }

    # ------------------------------------------------------------------ #
    def compute_normalizer(self) -> Normalizer:
        actions, obs, goals = [], [], []
        for episode in self.episodes:
            actions.append(episode["action"])
            obs.append(
                np.concatenate(
                    [episode["joint"], episode["finger"], episode["tactile"]], axis=-1
                )
            )
            goals.append(episode["goal"])
        actions = np.concatenate(actions, axis=0)
        obs = np.concatenate(obs, axis=0)
        goals = np.concatenate(goals, axis=0)
        return Normalizer(
            action_mean=actions.mean(0).astype(np.float32),
            action_std=(actions.std(0) + 1e-6).astype(np.float32),
            obs_mean=obs.mean(0).astype(np.float32),
            obs_std=(obs.std(0) + 1e-6).astype(np.float32),
            goal_mean=goals.mean(0).astype(np.float32),
            goal_std=(goals.std(0) + 1e-6).astype(np.float32),
        )

    def skill_histogram(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        from .skills import SKILLS

        for episode in self.episodes:
            if episode["skills"] is None:
                continue
            for value in np.unique(episode["skills"]):
                name = SKILLS[int(value)]
                counts[name] = counts.get(name, 0) + int((episode["skills"] == value).sum())
        return counts

    def summary(self) -> str:
        categories: dict[str, int] = {}
        arms: dict[str, int] = {}
        for episode in self.episodes:
            categories[episode["meta"]["category"]] = (
                categories.get(episode["meta"]["category"], 0) + 1
            )
            arms[episode["meta"]["arm"]] = arms.get(episode["meta"]["arm"], 0) + 1
        return (
            f"{len(self.episodes)} episodes, {len(self.windows)} windows; "
            f"categories={categories}; arms={arms}"
        )
