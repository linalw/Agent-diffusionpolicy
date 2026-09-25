"""Load a trained checkpoint and run closed-loop inference inside Isaac Sim."""

from __future__ import annotations

import numpy as np
import torch

from .data import Normalizer
from .diffusion import DiffusionSchedule
from .model import ConditionalUNet1D


class PolicyRunner:
    """Wraps a trained diffusion policy for use by the simulation."""

    def __init__(self, checkpoint_path: str, device: str | None = None,
                 default_steps: int = 8, use_half: bool = True):
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.device = device
        self.default_steps = default_steps
        #: fp16 roughly halves UNet time on GPU; inputs must be cast to match.
        self.use_half = bool(use_half and device == "cuda")
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        config = checkpoint["config"]
        self.config = config

        self.model = ConditionalUNet1D(
            action_dim=config["action_dim"],
            image_channels=config["image_channels"],
            obs_horizon=config["obs_horizon"],
            goal_dim=config["goal_dim"],
            proprio_dim=config["proprio_dim"],
            num_skills=int(config.get("num_skills", 5)),
        ).to(device)
        self.model.load_state_dict(checkpoint["model"])
        self.model.eval()
        if self.use_half:
            self.model.half()

        self.schedule = DiffusionSchedule(config["num_diffusion_steps"], device=device)
        norm = checkpoint["normalizer"]
        self.normalizer = Normalizer(
            action_mean=np.array(norm["action_mean"], dtype=np.float32),
            action_std=np.array(norm["action_std"], dtype=np.float32),
            obs_mean=np.array(norm["obs_mean"], dtype=np.float32),
            obs_std=np.array(norm["obs_std"], dtype=np.float32),
            goal_mean=np.array(norm["goal_mean"], dtype=np.float32),
            goal_std=np.array(norm["goal_std"], dtype=np.float32),
        )
        self.obs_horizon = int(config["obs_horizon"])
        self.action_horizon = int(config["action_horizon"])
        self.image_size = int(config["image_size"])
        self._frames: list[np.ndarray] = []

    def set_precision(self, use_half: bool) -> None:
        """Switch between fp32 and fp16 inference."""
        self.use_half = bool(use_half and self.device == "cuda")
        self.model.half() if self.use_half else self.model.float()

    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        self._frames = []

    def _downsample(self, image: np.ndarray) -> np.ndarray:
        if image.shape[0] == self.image_size and image.shape[1] == self.image_size:
            return image
        stride_y = max(1, image.shape[0] // self.image_size)
        stride_x = max(1, image.shape[1] // self.image_size)
        cropped = image[: self.image_size * stride_y, : self.image_size * stride_x]
        return cropped[::stride_y, ::stride_x]

    def push_frame(self, rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray | None = None) -> None:
        """Append a head-camera frame to the observation horizon buffer."""
        rgb = np.asarray(rgb)
        depth = np.asarray(depth)
        if depth.ndim == 3 and depth.shape[-1] == 1:
            depth = depth[..., 0]
        if rgb.ndim == 3 and rgb.shape[-1] == 4:
            rgb = rgb[..., :3]
        rgb_f = self._downsample(np.asarray(rgb)).astype(np.float32) / 255.0
        depth_f = self._downsample(np.asarray(depth)).astype(np.float32)
        depth_f = np.clip(depth_f, 0.0, 3.0) / 3.0
        channels = [rgb_f, depth_f[..., None]]
        if self.config["image_channels"] == 5:
            if mask is None:
                mask = np.zeros_like(depth_f)
            mask_f = self._downsample(np.asarray(mask)).astype(np.float32)
            channels.append(mask_f[..., None])
        self._frames.append(np.concatenate(channels, axis=-1))
        if len(self._frames) > self.obs_horizon:
            self._frames.pop(0)

    @property
    def ready(self) -> bool:
        return len(self._frames) >= self.obs_horizon

    # ------------------------------------------------------------------ #
    @torch.no_grad()
    def act(self, proprio: np.ndarray, goal: np.ndarray, num_steps: int | None = None) -> np.ndarray:
        """Sample an action chunk. Returns (action_horizon, action_dim) in raw units."""
        num_steps = self.default_steps if num_steps is None else num_steps
        dtype = torch.float16 if self.use_half else torch.float32
        frames = self._frames[-self.obs_horizon :]
        image = np.stack(frames, axis=0)  # (obs_horizon, H, W, C)
        image = np.transpose(image, (0, 3, 1, 2))
        image_t = torch.from_numpy(image[None]).to(self.device, dtype)
        goal_t = torch.from_numpy(
            self.normalizer.normalize_goal(np.asarray(goal, dtype=np.float32))[None]
        ).to(self.device, dtype)
        proprio_t = torch.from_numpy(
            self.normalizer.normalize_obs(np.asarray(proprio, dtype=np.float32))[None]
        ).to(self.device, dtype)

        sample = self.schedule.ddim_sample(
            self.model,
            (image_t, goal_t, proprio_t),
            (1, self.config["action_dim"], self.action_horizon),
            num_steps=num_steps,
            dtype=dtype,
        )
        action = sample[0].float().transpose(0, 1).cpu().numpy()  # (horizon, action_dim)
        return self.normalizer.denormalize_action(action)
