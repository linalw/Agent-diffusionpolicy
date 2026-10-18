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


class Expert(nn.Module):
    """Lightweight residual adapter. Gate-free: the router supplies the weight.

    Initialised so the expert starts as a no-op, which keeps the routed model
    identical to the shared backbone at step 0.
    """

    def __init__(self, channels: int, hidden: int, depth: int = 2):
        super().__init__()
        layers: list[nn.Module] = [nn.Conv1d(channels, hidden, 3, padding=1), nn.SiLU()]
        for _ in range(depth - 2):
            layers += [nn.Conv1d(hidden, hidden, 3, padding=1), nn.SiLU()]
        layers.append(nn.Conv1d(hidden, channels, 3, padding=1))
        self.net = nn.Sequential(*layers)
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        return self.net(h)


class EventHeads(nn.Module):
    """Event-structure heads over a causal proprio history (P13-A, default off).

    The mechanism-menu item #6 (``docs/papers/MECHANISMS.md``): ForeTime-VLA's
    phase + time-to-transition subset (#50) reinforced by DAM-VLA's transition
    supervision (#42). The heads read the **shared** conditioning encoder's
    proprio embeddings over an 8-step causal history and predict

    * ``phase_logits`` - 4 classes (approach / close transition / carry / place)
      whose labels are free: the recorded finger channel's close transition plus
      the skill labels' lift/place leg boundaries (`finetune.episode_event_labels`);
    * ``ttt`` - the normalized time to the next transition, ``min(d / H, 1)``
      with ``d`` the frame distance to the nearest upcoming transition.

    They are **read-only auxiliary branches**: the denoiser's action output is
    identical with or without them, so the shipped inference path is unchanged
    and the trained checkpoint's base ``state_dict`` (the shared encoder carries
    the supervision) loads strictly into the shipped ``PolicyRunner``; the head
    parameters are saved separately (`finetune`). The menu's two deployment
    forms - a near-zero-init gated injection into ``cond`` (ForeTime) or the
    trigger input (`policy/trigger.py`) - both need a runtime-side proprio
    history and are recorded as the enable paths, not built here (P13-A
    IMPLEMENTATION.md).
    """

    #: Phase classes: approach, close/grasp transition, carry, place.
    NUM_PHASES = 4

    def __init__(self, cond_dim: int = 128, hidden: int = 64,
                 num_phases: int = NUM_PHASES):
        super().__init__()
        self.num_phases = int(num_phases)
        self.gru = nn.GRU(cond_dim, hidden, batch_first=True)
        self.phase = nn.Linear(hidden, self.num_phases)
        self.ttt = nn.Linear(hidden, 1)

    def forward(self, embeddings: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """``(batch, history, cond_dim)`` embeddings -> phase logits + TtT."""
        features, _ = self.gru(embeddings)
        last = features[:, -1]
        return self.phase(last), torch.sigmoid(self.ttt(last)).squeeze(-1)


class ConditionalUNet1D(nn.Module):
    """Skill-routed denoiser.

    A shared visual encoder, condition encoder and 1-D UNet backbone produce a
    feature map; a router then mixes `num_experts` lightweight residual experts
    into it. This is the architecture from the design discussion: one shared
    diffusion decoder, with phase-specific capacity selected by a Skill Router.

    Training starts with hard routing (the expert is forced from the skill label)
    and switches to soft routing (router weights) in the later epochs.

    ``event_heads=True`` attaches the default-off ``EventHeads`` (P13-A): the
    heads run only when a ``proprio_history`` is passed to ``forward``/
    ``denoise`` (training), never in the shipped inference path, and they do not
    touch the action output. With the default ``False`` the module is absent -
    the ``state_dict``, the RNG stream and the forward arithmetic are exactly
    the shipped ones.
    """

    def __init__(self, action_dim: int = 9, image_channels: int = 4, obs_horizon: int = 2,
                 goal_dim: int = 8, proprio_dim: int = 25, cond_dim: int = 128,
                 down_dims: tuple[int, ...] = (128, 256, 256), num_skills: int = 5,
                 expert_hidden: int = 128, expert_depth: int = 2,
                 event_heads: bool = False):
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

        # ---- Skill Router + experts (mixture of experts) ----
        self.num_skills = num_skills
        self.router = nn.Sequential(
            nn.Linear(cond_dim, cond_dim), nn.SiLU(), nn.Linear(cond_dim, num_skills)
        )
        self.experts = nn.ModuleList(
            [Expert(prev, expert_hidden, depth=expert_depth) for _ in range(num_skills)]
        )
        #: Soft-routing weights from the most recent forward pass (for logging).
        self.last_router_weights: torch.Tensor | None = None
        #: P13-A event-structure heads (default off; auxiliary, read-only).
        #: Constructed only when asked, so the off path adds no parameters and
        #: consumes no RNG draws - the shipped construction is bit-identical.
        self.event: EventHeads | None = (
            EventHeads(cond_dim) if event_heads else None
        )
        #: Phase logits + TtT from the most recent forward pass that carried a
        #: proprio history (None otherwise; consumed by the fine-tune loss).
        self.last_event: tuple[torch.Tensor, torch.Tensor] | None = None

    # ------------------------------------------------------------------ #
    def route(self, cond: torch.Tensor, hard_labels: torch.Tensor | None = None) -> torch.Tensor:
        """Router weights; one-hot when `hard_labels` is given."""
        logits = self.router(cond)
        if hard_labels is not None:
            weights = torch.nn.functional.one_hot(
                hard_labels, num_classes=self.num_skills
            ).to(logits.dtype)
            return weights, logits
        return torch.softmax(logits, dim=-1), logits

    def _mix_experts(self, h: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
        """Weighted sum of expert residuals. Only experts with non-zero weight run."""
        out = torch.zeros_like(h)
        for k, expert in enumerate(self.experts):
            wk = weights[:, k]
            if float(wk.abs().max()) < 1e-6:
                continue
            out = out + wk[:, None, None] * expert(h)
        return out

    def load_balancing_loss(self, weights: torch.Tensor) -> torch.Tensor:
        """Switch-Transformer style load balance: penalise collapse onto one expert."""
        frac = weights.mean(dim=0)
        importance = weights.mean(dim=0)
        return self.num_skills * torch.sum(frac * importance)

    def forward(self, sample: torch.Tensor, image: torch.Tensor, goal: torch.Tensor,
                proprio: torch.Tensor, timesteps: torch.Tensor,
                skill_labels: torch.Tensor | None = None,
                proprio_history: torch.Tensor | None = None) -> torch.Tensor:
        # image arrives as (batch, obs_horizon, channels, H, W); fold the horizon
        # into the channel dimension for the 2-D visual encoder.
        if image.dim() == 5:
            batch, horizon, channels, height, width = image.shape
            image = image.reshape(batch, horizon * channels, height, width)
        # Cast the embedding *before* the MLP: `sinusoidal_embedding` always
        # builds float32, which would clash with fp16 weights.
        time_input = sinusoidal_embedding(timesteps, 128).to(image.dtype)
        time_embed = self.time(time_input)
        cond = self.condition(goal, proprio) + self.visual(image) + time_embed
        # P13-A: the auxiliary event heads read the *shared* proprio encoder
        # over the causal history. Read-only: `cond` and the action output are
        # untouched, so the shipped inference path (no history passed) and the
        # action output with a history are both bit-identical to the base model.
        self.last_event = None
        if self.event is not None and proprio_history is not None:
            batch, steps, dim = proprio_history.shape
            embeddings = self.condition.proprio(
                proprio_history.reshape(batch * steps, dim)
            ).reshape(batch, steps, -1)
            self.last_event = self.event(embeddings)
        h = self.action_in(sample)
        for block in self.blocks:
            h = block(h, cond)
        weights, logits = self.route(cond, hard_labels=skill_labels)
        self.last_router_weights = weights.detach()
        self.last_router_logits = logits
        h = h + self._mix_experts(h, weights)
        return self.head(h)

    # Convenience wrapper matching what the diffusion schedule expects.
    def denoise(self, sample, condition, timesteps, skill_labels=None,
                proprio_history=None):
        image, goal, proprio = condition
        return self.forward(sample, image, goal, proprio, timesteps,
                            skill_labels=skill_labels, proprio_history=proprio_history)
