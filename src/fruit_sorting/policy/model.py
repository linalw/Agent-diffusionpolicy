"""Conditional 1-D UNet diffusion policy over action chunks."""

from __future__ import annotations

import math

import torch
import torch.nn as nn


def sinusoidal_embedding(timesteps: torch.Tensor, dim: int) -> torch.Tensor:
    half = dim // 2
    freqs = torch.exp(
        -math.log(10000.0) * torch.arange(half, device=timesteps.device) / max(half - 1, 1)
    )
    args = timesteps[:, None].float() * freqs[None]
    return torch.cat([torch.sin(args), torch.cos(args)], dim=-1)


class VisualEncoder(nn.Module):
    """Small CNN over the stacked head-camera frames (RGB + depth)."""

    def __init__(self, in_channels: int, out_dim: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, 32, 5, stride=2, padding=2), nn.GroupNorm(8, 32), nn.SiLU(),
            nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.GroupNorm(8, 64), nn.SiLU(),
            nn.Conv2d(64, 128, 3, stride=2, padding=1), nn.GroupNorm(8, 128), nn.SiLU(),
            nn.Conv2d(128, 128, 3, stride=2, padding=1), nn.GroupNorm(8, 128), nn.SiLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.proj = nn.Linear(128, out_dim)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        features = self.net(image).flatten(1)
        return self.proj(features)


class ConditionEncoder(nn.Module):
    """Encodes goal + proprioception into the global conditioning vector."""

    def __init__(self, goal_dim: int, proprio_dim: int, out_dim: int = 128):
        super().__init__()
        self.goal = nn.Sequential(
            nn.Linear(goal_dim, 128), nn.SiLU(), nn.Linear(128, out_dim)
        )
        self.proprio = nn.Sequential(
            nn.Linear(proprio_dim, 128), nn.SiLU(), nn.Linear(128, out_dim)
        )

    def forward(self, goal: torch.Tensor, proprio: torch.Tensor) -> torch.Tensor:
        return self.goal(goal) + self.proprio(proprio)


class ConditionalBlock(nn.Module):
    """Residual 1-D convolution block modulated by FiLM conditioning."""

    def __init__(self, in_channels: int, out_channels: int, cond_dim: int, kernel: int = 5):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel, padding=kernel // 2)
        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel, padding=kernel // 2)
        self.norm1 = nn.GroupNorm(8, out_channels)
        self.norm2 = nn.GroupNorm(8, out_channels)
        self.film = nn.Linear(cond_dim, out_channels * 2)
        self.residual = (
            nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else nn.Identity()
        )
        self.act = nn.SiLU()

    def forward(self, x: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        h = self.act(self.norm1(self.conv1(x)))
        scale, bias = self.film(cond).chunk(2, dim=-1)
        h = h * (1.0 + scale[..., None]) + bias[..., None]
        h = self.act(self.norm2(self.conv2(h)))
        return h + self.residual(x)


class ConditionalUNet1D(nn.Module):
    """Denoises an action chunk conditioned on images, goal and proprioception."""

    def __init__(self, action_dim: int = 9, image_channels: int = 4, obs_horizon: int = 2,
                 goal_dim: int = 8, proprio_dim: int = 25, cond_dim: int = 128,
                 down_dims: tuple[int, ...] = (128, 256, 256)):
        super().__init__()
        self.visual = VisualEncoder(image_channels * obs_horizon, cond_dim)
        self.condition = ConditionEncoder(goal_dim, proprio_dim, cond_dim)
        self.time = nn.Sequential(
            nn.Linear(cond_dim, cond_dim), nn.SiLU(), nn.Linear(cond_dim, cond_dim)
        )
        self.action_in = nn.Conv1d(action_dim, down_dims[0], 1)

        blocks = []
        prev = down_dims[0]
        for dim in down_dims:
            blocks.append(ConditionalBlock(prev, dim, cond_dim))
            blocks.append(ConditionalBlock(dim, dim, cond_dim))
            prev = dim
        self.blocks = nn.ModuleList(blocks)
        self.head = nn.Sequential(
            nn.Conv1d(prev, 128, 3, padding=1), nn.SiLU(), nn.Conv1d(128, action_dim, 1)
        )

    def forward(self, sample: torch.Tensor, image: torch.Tensor, goal: torch.Tensor,
                proprio: torch.Tensor, timesteps: torch.Tensor) -> torch.Tensor:
        # image arrives as (batch, obs_horizon, channels, H, W); fold the horizon
        # into the channel dimension for the 2-D visual encoder.
        if image.dim() == 5:
            batch, horizon, channels, height, width = image.shape
            image = image.reshape(batch, horizon * channels, height, width)
        cond = (
            self.condition(goal, proprio)
            + self.visual(image)
            + self.time(sinusoidal_embedding(timesteps, 128))
        )
        h = self.action_in(sample)
        for block in self.blocks:
            h = block(h, cond)
        return self.head(h)

    # Convenience wrapper matching what the diffusion schedule expects.
    def denoise(self, sample, condition, timesteps):
        image, goal, proprio = condition
        return self.forward(sample, image, goal, proprio, timesteps)
