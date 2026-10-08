"""Offline self-test for the consistency-distillation module (no simulator, no checkpoint).

Pins the properties the deployable-student claim rests on:

1. `implied_x0` matches the sampler's `predicted_clean` conversion.
2. A 1-step `DiffusionSchedule.ddim_sample` on any epsilon network returns
   exactly the implied x0 at t = T-1 - so the shipped DDIM chain *is* the
   1-step consistency sampler and no runtime change is needed.
3. The EMA target moves toward the student.
4. One `_cd_step` produces finite `cd`/`x0`/router losses and gradients.
5. A teacher clone reproduces every interval of the deployment chain exactly
   when the fine chain *is* the deployment chain, and one cross-chain
   `_deploy_step` (the v6 re-attempt recipe) is finite and differentiable.
6. `endpoint_probe` returns finite paired medians on a synthetic window set.

Run: `python3 scripts/131_distill_selftest.py` (also wired into `scripts/selfcheck.sh`).
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch

from fruit_sorting.policy.diffusion import DiffusionSchedule
from fruit_sorting.policy.distill import (
    EMAModel,
    _cd_step,
    endpoint_probe,
    implied_x0,
)
from fruit_sorting.policy.model import ConditionalUNet1D


def make_config() -> dict:
    return {
        "action_dim": 9,
        "image_channels": 5,
        "obs_horizon": 2,
        "goal_dim": 8,
        "proprio_dim": 25,
        "num_skills": 5,
        "num_diffusion_steps": 100,
        "beta_schedule": "cosine",
    }


def make_model(config: dict) -> ConditionalUNet1D:
    return ConditionalUNet1D(
        action_dim=config["action_dim"],
        image_channels=config["image_channels"],
        obs_horizon=config["obs_horizon"],
        goal_dim=config["goal_dim"],
        proprio_dim=config["proprio_dim"],
        down_dims=(16, 32),
        num_skills=config["num_skills"],
        expert_hidden=16,
    ).eval()


def make_batch(batch_size: int) -> dict:
    generator = torch.Generator().manual_seed(0)
    return {
        "action": torch.randn(batch_size, 9, 16, generator=generator),
        "image": torch.randn(batch_size, 2, 5, 32, 32, generator=generator),
        "goal": torch.randn(batch_size, 8, generator=generator),
        "proprio": torch.randn(batch_size, 25, generator=generator),
        "skill": torch.randint(0, 5, (batch_size,), generator=generator),
    }


class WindowStub:
    """Minimal `WindowDataset`-shaped accessor for `endpoint_probe`."""

    def __init__(self, windows: list[dict]):
        self.windows = windows

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, index: int) -> dict:
        return self.windows[index]


def main() -> int:
    torch.manual_seed(0)
    config = make_config()
    schedule = DiffusionSchedule(100, device="cpu", beta_schedule="cosine")
    model = make_model(config)
    condition = (
        torch.randn(1, 2, 5, 32, 32),
        torch.randn(1, 8),
        torch.randn(1, 25),
    )
    shape = (1, 9, 16)

    # 1. implied_x0 equals the sampler's clean conversion.
    sample = torch.randn(shape, generator=torch.Generator().manual_seed(3))
    t = torch.full((1,), 42, dtype=torch.long)
    x0, eps = implied_x0(schedule, model, sample, condition, t)
    alpha = schedule.alphas_cumprod[t]
    expected = torch.clamp(
        (sample - torch.sqrt(1 - alpha)[:, None, None] * eps)
        / torch.sqrt(alpha)[:, None, None],
        -4.0, 4.0,
    )
    assert torch.allclose(x0, expected), "implied_x0 does not match the clean conversion"

    # 2. DDIM-1 == the implied x0 at t = T-1 (the deployed 1-step sampler).
    g1 = torch.Generator().manual_seed(7)
    one_step = schedule.ddim_sample(
        model, condition, shape, num_steps=1, dtype=torch.float32, generator=g1
    )
    g2 = torch.Generator().manual_seed(7)
    noise = torch.randn(shape, generator=g2)
    timestep = torch.full((1,), 99, dtype=torch.long)
    one_step_x0, _ = implied_x0(schedule, model, noise, condition, timestep)
    assert torch.allclose(one_step, one_step_x0, atol=1e-5), (
        "the shipped DDIM-1 chain is not the implied-x0 sampler"
    )

    # 3. EMA update moves the target toward the student.
    ema = EMAModel(model, decay=0.5)
    before = [p.detach().clone() for p in ema.model.parameters()]
    with torch.no_grad():
        for p in model.parameters():
            p.add_(0.1)
    ema.update(model)
    moved = [
        float((b - a).abs().sum()) for b, a in zip(before, ema.model.parameters())
    ]
    assert max(moved) > 0, "EMA did not move"

    # 4. one CD step is finite and differentiable.
    student = make_model(config)
    student.train()
    teacher = make_model(config)
    ema2 = EMAModel(student, decay=0.9)
    batch = make_batch(4)
    loss, cd, x0, router, router_acc, count = _cd_step(
        schedule, student, teacher, ema2, batch, "cpu",
        loss_kind="both", x0_weight=1.0, stride=1, max_timestep=99, clamp=4.0,
    )
    assert count == 4
    for name, value in (("loss", loss), ("cd", cd), ("x0", x0), ("router", router)):
        assert torch.isfinite(value), f"{name} is not finite"
    (loss + router).backward()
    grad_norm = sum(
        float(p.grad.abs().sum()) for p in student.parameters() if p.grad is not None
    )
    assert grad_norm > 0, "no gradients flowed through the CD objective"
    assert 0.0 <= router_acc <= 1.0

    # 5. endpoint objective: teacher chain + a supervised student step.
    from fruit_sorting.policy.distill import _endpoint_step, teacher_endpoint

    student.eval()
    batch = make_batch(4)
    endpoint, (samples, times) = teacher_endpoint(
        schedule, teacher, batch["action"], (
            batch["image"], batch["goal"], batch["proprio"],
        ), torch.randn_like(batch["action"]), num_steps=16, clamp=4.0,
    )
    assert endpoint.shape == batch["action"].shape
    assert len(samples) == 16 and len(times) == 16
    student.train()
    loss, cd, x0, router, router_acc, count = _endpoint_step(
        schedule, student, teacher, batch, "cpu", teacher_steps=16, clamp=4.0
    )
    assert count == 4 and torch.isfinite(loss) and torch.isfinite(router)
    (loss + router).backward()

    # 5b. progressive step: the student's one DDIM step matches the teacher's
    # two steps on the target chain.
    from fruit_sorting.policy.distill import _progressive_step

    loss, cd, x0, router, router_acc, count = _progressive_step(
        schedule, student, teacher, batch, "cpu", target_steps=2, clamp=4.0
    )
    assert torch.isfinite(loss) and count == 4
    (loss + router).backward()

    # 5c. deploy step (the v6 re-attempt recipe): deployment levels of the fine
    # chain; a clone of the teacher reproduces every interval exactly when the
    # fine chain IS the deployment chain (teacher_steps == chain_steps), and the
    # cross-chain objective is finite and differentiable with gradients.
    from fruit_sorting.policy.distill import _deploy_levels, _deploy_step

    assert _deploy_levels(16, 4) == [0, 5, 10, 15]
    assert _deploy_levels(4, 4) == [0, 1, 2, 3]
    student.load_state_dict(teacher.state_dict())
    student.train()
    clone_loss, _cd, _x0, router, _acc, count = _deploy_step(
        schedule, student, teacher, batch, "cpu",
        teacher_steps=4, chain_steps=4, clamp=4.0, student_clamp=4.0,
    )
    assert count == 4 and torch.isfinite(clone_loss)
    assert float(clone_loss) < 1e-6, (
        f"a teacher clone must reproduce the deployment chain, got {float(clone_loss)}"
    )
    cross_loss, _cd, _x0, router, _acc, count = _deploy_step(
        schedule, student, teacher, batch, "cpu",
        teacher_steps=16, chain_steps=4, clamp=4.0, student_clamp=4.0,
        eps_weight=0.5,
    )
    assert count == 4 and torch.isfinite(cross_loss)
    (cross_loss + router).backward()
    grad_norm = sum(
        float(p.grad.abs().sum()) for p in student.parameters() if p.grad is not None
    )
    assert grad_norm > 0, "no gradients flowed through the deploy objective"
    for mode in ("mixed", "student"):
        mixed_loss, _cd, _x0, router, _acc, count = _deploy_step(
            schedule, student, teacher, batch, "cpu",
            teacher_steps=16, chain_steps=4, clamp=4.0, student_clamp=4.0,
            input_mode=mode, mix_prob=0.5, input_noise=0.01,
        )
        assert count == 4 and torch.isfinite(mixed_loss), f"{mode} loss not finite"

    # 6. endpoint probe on a synthetic window set.
    probe = WindowStub(
        [
            {
                "action": torch.randn(9, 16),
                "image": torch.randn(2, 5, 32, 32),
                "goal": torch.randn(8),
                "proprio": torch.randn(25),
            }
            for _ in range(3)
        ]
    )
    result = endpoint_probe(
        student, teacher, schedule, probe, [0, 1, 2], "cpu", limit=3, seed=7
    )
    assert result["n"] == 3
    assert np.isfinite(result["student_teacher_median"])
    assert np.isfinite(result["student_rec_median"])
    assert np.isfinite(result["teacher_rec_median"])

    print("distill selftest: PASS (implied x0, DDIM-1 identity, EMA, CD step, "
          "deploy step, probe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
