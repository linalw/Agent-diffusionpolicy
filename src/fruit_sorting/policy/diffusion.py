"""Minimal DDPM training / DDIM sampling schedule."""

from __future__ import annotations

import torch


class DiffusionSchedule:
    """Cosine-free linear beta schedule with DDPM training and DDIM sampling."""

    def __init__(self, num_train_steps: int = 100, device: str = "cpu"):
        self.num_train_steps = num_train_steps
        betas = torch.linspace(1e-4, 0.02, num_train_steps, dtype=torch.float32)
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
                    dtype: torch.dtype = torch.float32) -> torch.Tensor:
        """Deterministic DDIM sampling; 8 steps is plenty for smooth actions."""
        device = self.device
        sample = torch.randn(shape, device=device, dtype=dtype)
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
                sample = sample + sigma * torch.randn_like(sample)
        return sample
