"""Minimal DDPM training / DDIM sampling schedule."""

from __future__ import annotations

import math

import torch


def _cosine_betas(num_train_steps: int, s: float = 0.008) -> torch.Tensor:
    """Nichol & Dhariwal cosine schedule; `alphas_cumprod[-1]` is ~0.

    The linear 100-step schedule below stops at `alphas_cumprod[99] = 0.364`,
    so its last training timestep still carries 60 % of the action signal.
    Sampling starts from N(0, I) (standard DDIM), which is *not* the training
    distribution there, and the chain converges to a biased sample (0.85x the
    recorded action; measured in `logs/742_action_forensics.txt`, WORKLOG
    "P4 follow-up diagnosis").  A cosine schedule reaches alpha ~ 2e-4 at
    t=99, which is what standard samplers assume.
    """
    steps = num_train_steps + 1
    x = torch.linspace(0, num_train_steps, steps, dtype=torch.float64)
    alpha_bar = torch.cos(((x / num_train_steps) + s) / (1 + s) * math.pi * 0.5) ** 2
    alpha_bar = alpha_bar / alpha_bar[0]
    betas = 1.0 - (alpha_bar[1:] / alpha_bar[:-1])
    return torch.clip(betas, 1e-4, 0.999).to(torch.float32)


class DiffusionSchedule:
    """Linear or cosine beta schedule with DDPM training and DDIM sampling.

    `beta_schedule` is part of the checkpoint contract: new checkpoints record
    it in their config (`train.DiffusionSchedule` call site), old checkpoints
    have no such key and keep the linear schedule they were trained with.
    """

    def __init__(self, num_train_steps: int = 100, device: str = "cpu",
                 beta_schedule: str = "linear"):
        self.num_train_steps = num_train_steps
        self.beta_schedule = str(beta_schedule)
        if self.beta_schedule == "cosine":
            betas = _cosine_betas(num_train_steps)
        elif self.beta_schedule == "linear":
            betas = torch.linspace(1e-4, 0.02, num_train_steps, dtype=torch.float32)
        else:
            raise ValueError(
                f"beta_schedule must be 'linear' or 'cosine', got {beta_schedule!r}"
            )
        alphas = 1.0 - betas
        self.betas = betas.to(device)
        self.alphas_cumprod = torch.cumprod(alphas, dim=0).to(device)
        self.sqrt_alphas_cumprod = torch.sqrt(self.alphas_cumprod)
        self.sqrt_one_minus_alphas_cumprod = torch.sqrt(1.0 - self.alphas_cumprod)
        self.device = device

    # ------------------------------------------------------------------ #
    def add_noise(self, clean: torch.Tensor, noise: torch.Tensor, timesteps: torch.Tensor) -> torch.Tensor:
        a = self.sqrt_alphas_cumprod[timesteps][:, None, None]
        b = self.sqrt_one_minus_alphas_cumprod[timesteps][:, None, None]
        return a * clean + b * noise

    def sample_timesteps(self, batch: int) -> torch.Tensor:
        return torch.randint(
            0, self.num_train_steps, (batch,), device=self.device, dtype=torch.long
        )

    # ------------------------------------------------------------------ #
    @torch.no_grad()
    def ddim_sample(self, model, condition, shape: tuple[int, ...],
                    num_steps: int = 16, eta: float = 0.0,
                    dtype: torch.dtype = torch.float32,
                    generator: torch.Generator | None = None) -> torch.Tensor:
        """Deterministic DDIM sampling; 8 steps is plenty for smooth actions.

        `generator` seeds the initial noise. Without it every inference draws fresh
        noise, which makes a closed-loop evaluation outcome-stable but not
        bit-reproducible - the same six episodes came out 6/6 twice with peak lifts
        differing by up to 1 cm (WORKLOG). Passing a seeded generator is what makes
        a policy A/B comparable; `PolicyRunner` wires one up from
        `FRUIT_POLICY_SEED`.
        """
        device = self.device
        sample = torch.randn(shape, device=device, dtype=dtype, generator=generator)
        times = torch.linspace(
            self.num_train_steps - 1, 0, num_steps, dtype=torch.long, device=device
        )
        for i, t in enumerate(times):
            t_batch = t.expand(shape[0])
            predicted_noise = model.denoise(sample, condition, t_batch)
            alpha = self.alphas_cumprod[t]
            alpha_prev = (
                self.alphas_cumprod[times[i + 1]] if i + 1 < num_steps else torch.tensor(1.0, device=device)
            )
            predicted_clean = (sample - torch.sqrt(1 - alpha) * predicted_noise) / torch.sqrt(alpha)
            predicted_clean = predicted_clean.clamp(-4.0, 4.0)
            sigma = eta * torch.sqrt(
                (1 - alpha_prev) / (1 - alpha) * (1 - alpha / alpha_prev)
            )
            direction = torch.sqrt(1 - alpha_prev - sigma**2) * predicted_noise
            sample = torch.sqrt(alpha_prev) * predicted_clean + direction
            if eta > 0:
                sample = sample + sigma * torch.randn(
                    sample.shape, device=device, dtype=sample.dtype, generator=generator
                )
        return sample
