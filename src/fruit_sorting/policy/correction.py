"""A2C2-style per-step correction head (arXiv 2509.23224), default off.

A small residual head runs *every control step* on the latest low-dimensional
observation, the base chunk's action and the chunk index, and shifts the 7 arm
channels of the action the frozen base policy proposed. The base checkpoint is
never modified. This is the survey's rank-2 reactivity mechanism
(`docs/research_dynamic_grasp_methods.md` section 5): it adds 120 Hz correction
without touching the DDIM sampler, orthogonal to any chunk-continuity scheme.

Training data and target are fixed in `logs/path3/PREREGISTRATION.md`: fresh
DAgger rollouts of the base arm (expert label in ``action``, base proposal in
``policy_action``), target ``clamp(expert[:7] - proposal[:7], -0.2, 0.2)`` rad.
The trainer is `scripts/146_train_correction.py`.

Environment knobs (all read by `rl_env.SortingRLEnv`, default off):

    FRUIT_A2C2          path to a `correction.pt` written by the trainer;
                        unset = the shipped loop is byte-identical
    FRUIT_A2C2_GAIN     scale on the correction (default 1.0)
    FRUIT_A2C2_CLAMP    per-step per-joint cap in rad (default 0.2)

The head is applied only while the scripted primitive has **not** been triggered
(once `grasp_carry_place` owns the arm the base action is no longer executed),
and only to the arm channels - the finger channel stays the policy's own, so the
trigger timing is untouched by the correction.
"""

from __future__ import annotations

import os

import numpy as np
import torch
import torch.nn as nn

from .data import Normalizer

#: Model input layout *defaults* (the head's own `config` is authoritative when
#: it is loaded - see `CorrectionController.correct`; P28-B: a 26-D proprio head
#: must slice with its config, not with this constant).
OBS_DIM = 25
GOAL_DIM = 8
ACTION_DIM = 9
OUT_DIM = 7
HIDDEN = 256
#: Chunk-index normaliser (the base action horizon; index 0..15 -> 0..1).
INDEX_SCALE = 16.0


class CorrectionHead(nn.Module):
    """MLP (proprio, goal, base action, chunk index) -> 7-D arm correction."""

    def __init__(
        self,
        obs_dim: int = OBS_DIM,
        goal_dim: int = GOAL_DIM,
        action_dim: int = ACTION_DIM,
        out_dim: int = OUT_DIM,
        hidden: int = HIDDEN,
    ) -> None:
        super().__init__()
        self.config = {
            "obs_dim": int(obs_dim),
            "goal_dim": int(goal_dim),
            "action_dim": int(action_dim),
            "out_dim": int(out_dim),
            "hidden": int(hidden),
        }
        self.net = nn.Sequential(
            nn.Linear(obs_dim + goal_dim + action_dim + 1, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, out_dim),
        )

    def forward(
        self,
        obs: torch.Tensor,
        goal: torch.Tensor,
        action: torch.Tensor,
        index: torch.Tensor,
    ) -> torch.Tensor:
        x = torch.cat([obs, goal, action, index], dim=-1)
        return self.net(x)


class CorrectionController:
    """Loads a trained head and applies it to a 9-D base action each step."""

    def __init__(
        self,
        path: str,
        *,
        gain: float | None = None,
        clamp: float | None = None,
        device: str = "cpu",
    ) -> None:
        payload = torch.load(path, map_location=device, weights_only=False)
        cfg = payload.get("config", {})
        norm = payload["normalizer"]
        # P28-B (P28 Gate A): the widths come from the **payload**, not from the
        # module constants. The normaliser is the payload's own statement of the
        # observation width (`obs_mean`, `goal_mean`), so a config that predates
        # the field still loads at the right width, and the two must agree - a
        # 26-D head fed 25 dims is a silent shift, not an error.
        obs_dim = int(cfg.get("obs_dim", len(norm["obs_mean"])))
        goal_dim = int(cfg.get("goal_dim", len(norm["goal_mean"])))
        if int(len(norm["obs_mean"])) != obs_dim or int(len(norm["goal_mean"])) != goal_dim:
            raise ValueError(
                f"{path}: head config obs_dim={obs_dim}/goal_dim={goal_dim} "
                f"disagrees with its normaliser "
                f"({len(norm['obs_mean'])}/{len(norm['goal_mean'])})"
            )
        self.obs_dim = obs_dim
        self.goal_dim = goal_dim
        self.head = CorrectionHead(
            obs_dim=obs_dim,
            goal_dim=goal_dim,
            action_dim=int(cfg.get("action_dim", ACTION_DIM)),
            out_dim=int(cfg.get("out_dim", OUT_DIM)),
            hidden=int(cfg.get("hidden", HIDDEN)),
        ).to(device)
        self.head.load_state_dict(payload["model"])
        self.head.eval()
        self.normalizer = Normalizer(
            action_mean=np.asarray(norm["action_mean"], dtype=np.float32),
            action_std=np.asarray(norm["action_std"], dtype=np.float32),
            obs_mean=np.asarray(norm["obs_mean"], dtype=np.float32),
            obs_std=np.asarray(norm["obs_std"], dtype=np.float32),
            goal_mean=np.asarray(norm["goal_mean"], dtype=np.float32),
            goal_std=np.asarray(norm["goal_std"], dtype=np.float32),
        )
        self.device = device
        self.gain = float(
            gain if gain is not None else os.environ.get("FRUIT_A2C2_GAIN", "1.0")
        )
        self.clamp = float(
            clamp if clamp is not None else os.environ.get("FRUIT_A2C2_CLAMP", "0.2")
        )
        self.steps = 0

    @torch.no_grad()
    def correct(
        self,
        action: np.ndarray,
        proprio: np.ndarray,
        goal: np.ndarray,
        index: int,
    ) -> np.ndarray:
        """Return the corrected action (copy); the input is not modified."""
        a = np.asarray(action, dtype=np.float32)
        obs = np.asarray(proprio, dtype=np.float32)
        goal_v = np.asarray(goal, dtype=np.float32)
        # The head's width is fixed by its payload; a mismatched observation is
        # refused instead of being concatenated into a shifted vector.
        if obs.shape[0] != self.obs_dim or goal_v.shape[0] != self.goal_dim:
            raise ValueError(
                f"correction head expects obs/goal width "
                f"{self.obs_dim}/{self.goal_dim}, got "
                f"{obs.shape[0]}/{goal_v.shape[0]} "
                f"(P28-B: a 26-D proprio needs a head trained at 26)"
            )
        obs_n = self.normalizer.normalize_obs(obs).astype(np.float32)
        goal_n = self.normalizer.normalize_goal(goal_v).astype(np.float32)
        act_n = self.normalizer.normalize_action(
            np.asarray(a[:ACTION_DIM], dtype=np.float32)
        ).astype(np.float32)
        index_n = np.array(
            [float(index) / INDEX_SCALE], dtype=np.float32
        )
        x = torch.from_numpy(
            np.concatenate([obs_n, goal_n, act_n, index_n])[None]
        ).to(self.device)
        # Slice with the width the payload declared (the head's own `config` we
        # built it from), not with the module constants: a head trained on a
        # different obs/goal width (e.g. the P28-B 26-D proprio) would otherwise
        # be fed a silently shifted vector - same concatenation, wrong split.
        obs_dim = int(self.head.config["obs_dim"])
        goal_dim = int(self.head.config["goal_dim"])
        action_dim = int(self.head.config["action_dim"])
        delta = self.head(x[:, :obs_dim],
                          x[:, obs_dim:obs_dim + goal_dim],
                          x[:, obs_dim + goal_dim:obs_dim + goal_dim + action_dim],
                          x[:, -1:]).cpu().numpy()[0]
        delta = np.clip(np.asarray(delta, dtype=np.float32), -self.clamp, self.clamp)
        out = a.copy()
        out[:OUT_DIM] += self.gain * delta
        self.steps += 1
        return out
