"""Consistency distillation of a trained diffusion policy (offline, no Isaac).

The v5 directive's ranked lever 3: the shipped DDIM-16 sampler costs ~26 ms per
chunk (~78 % of the 33.3 ms control period at 120 Hz physics), so the decision
rate is capped at 30 Hz. This module turns a frozen teacher (`checkpoints/
moe_v10`) into a consistency model on the *same* `ConditionalUNet1D` backbone:
one network evaluation maps any point on the teacher's diffusion trajectory
straight to the clean action chunk, so the stock `DiffusionSchedule.ddim_sample`
with `num_steps` in 1..4 becomes the deployed sampler.

Why the stock DDIM chain *is* the consistency sampler here
----------------------------------------------------------
The student is epsilon-parameterized exactly like the teacher, and consistency
distillation trains the implied clean action

    f(x_t, t) = clamp((x_t - sqrt(1-a_t) * eps_theta(x_t, t)) / sqrt(a_t))

to be constant along the teacher's DDIM trajectory. The shipped DDIM update
between two chain timesteps is

    x_{t'} = sqrt(a_{t'}) * predicted_clean + sqrt(1-a_{t'}) * predicted_noise

which is the same deterministic re-noise the consistency sampler uses. The
timesteps of `ddim_sample(num_steps=k)` are `linspace(T-1, 0, k)`, so calling
the existing `PolicyRunner.act(..., num_steps=k)` on the student evaluates
f at k points of the chain and returns f's endpoint. Nothing in the runtime
needs to change, and RTC's interleaved DDIM sampler applies unchanged.

Objective (Consistency Policy / consistency distillation recipe):

    cd:    f_theta(x_t, t)  <-  stop_grad f_ema(x_{t-dt'}, t - dt')
           where x_{t-dt'} is one teacher DDIM step from x_t
    x0:    f_theta(x_t, t)  <-  stop_grad f_teacher(x_t, t)
           (the local denoiser anchor that keeps the student on the teacher's
           manifold; the Consistency Policy paper keeps the diffusion loss)

with `x_t` built by adding noise to a recorded action chunk from the dataset.
The EMA target makes the recursion stable; at the chain end (t' = 0) the EMA
student's own output at t=0 is the target, whose value is x_0 by construction
(alpha_0 ~ 1).

Provenance: teacher checkpoint md5, dataset index/manifest md5, the split, the
loss and every knob are written into the checkpoint and `history.json`.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset

from ..rl_env import TASKS_MD5
from .data import EpisodeStore, Normalizer
from .diffusion import DiffusionSchedule
from .model import ConditionalUNet1D
from .train import WindowDataset

#: Loss variants: `cd` = consistency distillation only, `x0` = local denoiser
#: anchor only, `both` = cd + x0_weight * x0, `endpoint` = the student's implied
#: x0 is regressed directly onto the frozen teacher's full DDIM endpoint from
#: the same noise (sampling distillation), `progressive` = round-by-round
#: halving of the sampler budget (16 -> 8 -> 4 -> 2 -> 1), each round's student
#: replacing two teacher steps with one, `deploy` = consistency distillation
#: along the teacher's fine chain restricted to the deployment levels (the
#: v5-C2 re-attempt recipe; see `_deploy_step`); every variant deploys through
#: the stock `ddim_sample`, so no runtime change is needed.
DISTILL_LOSSES = ("cd", "x0", "both", "endpoint", "progressive", "deploy")


def teacher_endpoint(
    schedule: DiffusionSchedule,
    teacher: ConditionalUNet1D,
    action: torch.Tensor,
    condition: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    noise: torch.Tensor,
    *,
    num_steps: int = 16,
    clamp: float = 4.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """The teacher's DDIM-`num_steps` endpoint and one trajectory point per step.

    Runs the shipped sampler chain (the same `linspace(T-1,0,num_steps)` times)
    from ``noise`` and returns ``(endpoint, (samples, timesteps))`` where
    `samples` is the list of chain inputs; every point shares `endpoint` as its
    consistency target. No gradients (teacher target construction).
    """
    device = schedule.device
    times = torch.linspace(
        schedule.num_train_steps - 1, 0, int(num_steps), dtype=torch.long,
        device=device,
    )
    x = schedule.add_noise(action, noise, times[0].expand(action.shape[0]))
    samples: list[torch.Tensor] = []
    x0 = x
    eps = noise
    for index, t in enumerate(times):
        t_batch = t.expand(action.shape[0])
        samples.append(x)
        x0, eps = implied_x0(schedule, teacher, x, condition, t_batch, clamp=clamp)
        if index + 1 < len(times):
            alpha_next = schedule.alphas_cumprod[times[index + 1]]
            x = torch.sqrt(alpha_next) * x0 + torch.sqrt(1.0 - alpha_next) * eps
    return x0, (samples, times)


def _md5(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.md5(handle.read()).hexdigest()
    except OSError:
        return ""


def _clone_module(model: ConditionalUNet1D) -> ConditionalUNet1D:
    """A parameter copy of `model` (deepcopy-safe).

    `ConditionalUNet1D.forward` stores `last_router_weights/logits` on the module;
    those tensors are graph-connected and `copy.deepcopy` refuses non-leaf
    tensors, so they are dropped around the copy and restored afterwards.
    """
    weights = getattr(model, "last_router_weights", None)
    logits = getattr(model, "last_router_logits", None)
    model.last_router_weights = None
    model.last_router_logits = None
    try:
        clone = copy.deepcopy(model)
    finally:
        model.last_router_weights = weights
        model.last_router_logits = logits
    return clone


def implied_x0(
    schedule: DiffusionSchedule,
    model: ConditionalUNet1D,
    sample: torch.Tensor,
    condition: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    timesteps: torch.Tensor,
    clamp: float = 4.0,
    skill_labels: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """The clean action implied by the model's noise prediction at `sample`.

    Returns ``(x0, eps)``; `x0` is clamped like the DDIM sampler clamps
    `predicted_clean`, `eps` stays raw so the re-noise step matches DDIM.
    """
    predicted_noise = model.denoise(
        sample, condition, timesteps, skill_labels=skill_labels
    )
    alpha = schedule.alphas_cumprod[timesteps]
    sqrt_alpha = torch.sqrt(alpha)[:, None, None]
    sqrt_one_minus = torch.sqrt(1.0 - alpha)[:, None, None]
    x0 = (sample - sqrt_one_minus * predicted_noise) / sqrt_alpha
    return torch.clamp(x0, -float(clamp), float(clamp)), predicted_noise


class EMAModel:
    """Exponential moving average of the student - the CD target network."""

    def __init__(self, model: ConditionalUNet1D, decay: float = 0.999):
        self.decay = float(decay)
        self.model = _clone_module(model).eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)

    @torch.no_grad()
    def update(self, model: ConditionalUNet1D) -> None:
        for ema_p, p in zip(self.model.parameters(), model.parameters()):
            ema_p.mul_(self.decay).add_(p.detach(), alpha=1.0 - self.decay)
        for ema_b, b in zip(self.model.buffers(), model.buffers()):
            ema_b.copy_(b)


def build_model(config: dict, device: str) -> ConditionalUNet1D:
    return ConditionalUNet1D(
        action_dim=int(config["action_dim"]),
        image_channels=int(config["image_channels"]),
        obs_horizon=int(config["obs_horizon"]),
        goal_dim=int(config["goal_dim"]),
        proprio_dim=int(config["proprio_dim"]),
        num_skills=int(config.get("num_skills", 5)),
    ).to(device)


def _normalizer_from_checkpoint(payload: dict) -> Normalizer:
    norm = payload["normalizer"]
    return Normalizer(
        action_mean=np.asarray(norm["action_mean"], dtype=np.float32),
        action_std=np.asarray(norm["action_std"], dtype=np.float32),
        obs_mean=np.asarray(norm["obs_mean"], dtype=np.float32),
        obs_std=np.asarray(norm["obs_std"], dtype=np.float32),
        goal_mean=np.asarray(norm["goal_mean"], dtype=np.float32),
        goal_std=np.asarray(norm["goal_std"], dtype=np.float32),
    )


def _batch_tensors(batch: dict, device: str):
    action = batch["action"].to(device)
    condition = (
        batch["image"].to(device),
        batch["goal"].to(device),
        batch["proprio"].to(device),
    )
    return action, condition, batch["skill"].to(device)


def _cd_step(
    schedule: DiffusionSchedule,
    student: ConditionalUNet1D,
    teacher: ConditionalUNet1D,
    ema: EMAModel,
    batch: dict,
    device: str,
    *,
    loss_kind: str,
    x0_weight: float,
    stride: int,
    max_timestep: int,
    clamp: float,
):
    """One distillation step's losses (student forward + teacher/EMA targets)."""
    action, condition, skill = _batch_tensors(batch, device)
    batch_size = action.shape[0]
    timesteps = torch.randint(
        int(stride), int(max_timestep) + 1, (batch_size,), device=device,
        dtype=torch.long,
    )
    noise = torch.randn_like(action)
    noisy = schedule.add_noise(action, noise, timesteps)

    with torch.no_grad():
        x0_teacher, eps_teacher = implied_x0(
            schedule, teacher, noisy, condition, timesteps, clamp=clamp
        )
        alpha_prev = schedule.alphas_cumprod[timesteps - int(stride)]
        x_prev = (
            torch.sqrt(alpha_prev)[:, None, None] * x0_teacher
            + torch.sqrt(1.0 - alpha_prev)[:, None, None] * eps_teacher
        )
        x0_target, _ = implied_x0(
            schedule, ema.model, x_prev, condition, timesteps - int(stride),
            clamp=clamp,
        )

    x0_student, _ = implied_x0(schedule, student, noisy, condition, timesteps,
                               clamp=clamp)
    cd_loss = F.mse_loss(x0_student, x0_target)
    x0_loss = F.mse_loss(x0_student, x0_teacher)
    if loss_kind == "cd":
        loss = cd_loss
    elif loss_kind == "x0":
        loss = x0_loss
    else:
        loss = cd_loss + float(x0_weight) * x0_loss
    router_loss = F.cross_entropy(student.last_router_logits, skill)
    with torch.no_grad():
        router_acc = float(
            (student.last_router_logits.argmax(dim=-1) == skill).float().mean().item()
        )
    return loss, cd_loss, x0_loss, router_loss, router_acc, int(batch_size)


def _endpoint_step(
    schedule: DiffusionSchedule,
    student: ConditionalUNet1D,
    teacher: ConditionalUNet1D,
    batch: dict,
    device: str,
    *,
    teacher_steps: int = 16,
    clamp: float = 4.0,
    level_probs: torch.Tensor | None = None,
):
    """Sampling distillation: student x0 at a trajectory point -> endpoint.

    The frozen teacher runs its full DDIM chain from one noise draw; one chain
    level is chosen per *sample* (uniformly, or from `level_probs` - the v5
    runs focus the deployment levels, because a uniform draw spends 15/16 of
    the budget on levels the deployed sampler never evaluates), and the
    student's implied x0 there is regressed onto the chain endpoint. Every
    level shares the same target, so the resulting map is constant along the
    trajectory - the consistency property that makes the stock k-step chain a
    usable sampler.
    """
    action, condition, skill = _batch_tensors(batch, device)
    batch_size = action.shape[0]
    noise = torch.randn_like(action)
    with torch.no_grad():
        endpoint, (samples, times) = teacher_endpoint(
            schedule, teacher, action, condition, noise,
            num_steps=int(teacher_steps), clamp=clamp,
        )
        level_count = len(times)
        if level_probs is None:
            indices = torch.randint(
                0, level_count, (batch_size,), device=device
            )
        else:
            probabilities = level_probs.to(device)
            indices = torch.multinomial(
                probabilities, batch_size, replacement=True
            )
        stacked = torch.stack(samples)  # (levels, batch, action_dim, horizon)
        x_level = stacked[indices, torch.arange(batch_size, device=device)]
        t_level = times[indices]
    x0_student, _ = implied_x0(schedule, student, x_level, condition, t_level,
                               clamp=clamp)
    loss = F.mse_loss(x0_student, endpoint)
    router_loss = F.cross_entropy(student.last_router_logits, skill)
    with torch.no_grad():
        router_acc = float(
            (student.last_router_logits.argmax(dim=-1) == skill).float().mean().item()
        )
    return loss, loss, torch.zeros_like(loss), router_loss, router_acc, int(batch_size)


def parse_level_focus(focus: str, num_steps: int, schedule: DiffusionSchedule) -> torch.Tensor:
    """Level probability vector from a ``"99:0.5,66:0.15"`` focus string.

    The stated timesteps carry their weight; the remaining mass is spread
    uniformly over all `num_steps` chain levels. An empty string is uniform.
    """
    times = torch.linspace(
        schedule.num_train_steps - 1, 0, int(num_steps), dtype=torch.long,
    )
    weights = torch.zeros(int(num_steps), dtype=torch.float64)
    focus = (focus or "").strip()
    if not focus:
        return torch.full((int(num_steps),), 1.0 / int(num_steps), dtype=torch.float32)
    named: dict[int, float] = {}
    for part in focus.split(","):
        if not part.strip():
            continue
        key, value = part.split(":")
        named[int(key)] = float(value)
    stated = sum(named.values())
    if stated > 1.0 + 1e-9:
        raise ValueError(f"focus weights sum to {stated} > 1")
    remaining = max(0.0, 1.0 - stated) / int(num_steps)
    for index, timestep in enumerate(times.tolist()):
        weights[index] = remaining + named.get(int(timestep), 0.0)
    if float(weights.sum()) <= 0:
        raise ValueError("empty level focus distribution")
    return (weights / weights.sum()).to(torch.float32)


def _progressive_teacher_steps(teacher_steps: int) -> list[int]:
    """Round start counts for progressive distillation: [16, 8, 4, 2] for 16."""
    rounds: list[int] = []
    base = int(teacher_steps)
    while base > 1:
        rounds.append(base)
        base = max(1, base // 2)
    return rounds


def _ddim_two_steps(
    schedule: DiffusionSchedule,
    model: ConditionalUNet1D,
    x: torch.Tensor,
    condition: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    t_a: torch.Tensor,
    t_b: torch.Tensor,
    batch: int,
    clamp: float,
) -> torch.Tensor:
    """Two deterministic DDIM steps from ``x`` at `t_a` to `t_b` (midpoint)."""
    midpoint = (t_a + t_b) // 2
    x0, eps = implied_x0(schedule, model, x, condition, t_a.expand(batch), clamp=clamp)
    alpha_mid = schedule.alphas_cumprod[midpoint]
    x_mid = (
        torch.sqrt(alpha_mid) * x0 + torch.sqrt(1.0 - alpha_mid) * eps
    )
    x0_mid, eps_mid = implied_x0(
        schedule, model, x_mid, condition, midpoint.expand(batch), clamp=clamp
    )
    alpha_b = schedule.alphas_cumprod[t_b]
    return torch.sqrt(alpha_b) * x0_mid + torch.sqrt(1.0 - alpha_b) * eps_mid


def _progressive_step_chain(
    schedule: DiffusionSchedule,
    student: ConditionalUNet1D,
    teacher: ConditionalUNet1D,
    batch: dict,
    device: str,
    *,
    target_steps: int,
    clamp: float = 4.0,
):
    """The chain-scheme progressive step (the shipped student's recipe).

    One coarse interval ``[t_a, t_b]`` of the target sampler's chain is chosen
    per batch (times of ``linspace(T-1, 0, target_steps)``); the teacher walks
    from the chain start to `t_a` in two DDIM steps per earlier interval, then
    takes the two steps of the chosen interval. The student takes that interval
    in *one* DDIM step, and the loss matches the resulting sample ``x_b`` in
    x-space. This is the scheme whose round-1/round-2 checkpoints are shipped;
    it fails from round 3 on because the interval midpoint is a timestep the
    previous student never trained on (see the module docstring / WORKLOG).
    """
    action, condition, skill = _batch_tensors(batch, device)
    batch_size = action.shape[0]
    steps = int(target_steps)
    if steps > 1:
        edges = torch.linspace(
            schedule.num_train_steps - 1, 0, steps, dtype=torch.long, device=device,
        )
    else:
        edges = torch.tensor(
            [schedule.num_train_steps - 1, 0], device=device, dtype=torch.long,
        )
    intervals = len(edges) - 1
    interval = int(torch.randint(0, intervals, (1,)).item())
    t_a, t_b = edges[interval], edges[interval + 1]

    noise = torch.randn_like(action)
    with torch.no_grad():
        x = schedule.add_noise(action, noise, edges[0].expand(batch_size))
        for index in range(interval):
            x = _ddim_two_steps(
                schedule, teacher, x, condition, edges[index], edges[index + 1],
                batch_size, clamp,
            )
        x_b_teacher = _ddim_two_steps(
            schedule, teacher, x, condition, t_a, t_b, batch_size, clamp,
        )

    x0_student, eps_student = implied_x0(
        schedule, student, x, condition, t_a.expand(batch_size), clamp=clamp
    )
    alpha_b = schedule.alphas_cumprod[t_b]
    x_b_student = (
        torch.sqrt(alpha_b) * x0_student + torch.sqrt(1.0 - alpha_b) * eps_student
    )
    loss = F.mse_loss(x_b_student, x_b_teacher)
    router_loss = F.cross_entropy(student.last_router_logits, skill)
    with torch.no_grad():
        router_acc = float(
            (student.last_router_logits.argmax(dim=-1) == skill).float().mean().item()
        )
    return loss, loss, torch.zeros_like(loss), router_loss, router_acc, int(batch_size)


def _progressive_step_continuous(
    schedule: DiffusionSchedule,
    student: ConditionalUNet1D,
    teacher: ConditionalUNet1D,
    batch: dict,
    device: str,
    *,
    target_steps: int,
    clamp: float = 4.0,
):
    """One progressive-distillation step (Salimans & Ho 2022, continuous time).

    The round target sampler has `target_steps` evals; one student step must
    cover two teacher steps. A random integer time ``t`` is drawn from the
    range the step can cover, ``x_t`` is built by noising the recorded action,
    and the frozen round teacher takes two half-steps ``t -> mid -> end`` while
    the student takes one full step ``t -> end``; the loss matches the two
    resulting samples in x-space.

    Training at *arbitrary* ``t`` (not just the deployment grid) is what makes
    each intermediate round a valid denoiser everywhere, so the next round can
    query it at its own midpoints - the v5 bug was querying a student at
    timesteps it had never trained on, which produced NaN chunks.
    """
    action, condition, skill = _batch_tensors(batch, device)
    batch_size = action.shape[0]
    steps = int(target_steps)
    num_steps = int(schedule.num_train_steps)
    full = num_steps - 1
    if steps > 1:
        # Interval of the deployment chain `linspace(full, 0, steps)`.
        stride = full / float(steps - 1)
    else:
        stride = float(full)
    if steps == 1:
        # The 1-step sampler only ever evaluates at the chain start; the
        # teacher's midpoint query (full/2) was trained by the previous round
        # (steps == 2 trains both full and full//2).
        time = full
        step = float(full)
    elif steps == 2:
        # Cover the first eval (t = full) and its midpoint (t = full//2) so the
        # next round can query the teacher at the midpoint (the v5 NaN bug).
        time = full if bool(torch.rand(()) < 0.5) else full // 2
        step = float(time)
    else:
        # Uniform over the whole range; low times take a proportionally shorter
        # step that lands at 0, so every timestep is trained and later rounds
        # never query an out-of-distribution time.
        time = int(torch.randint(1, full + 1, (1,), device=device).item())
        step = min(stride, float(time))
    midpoint = int(round(time - step / 2.0))
    endpoint = int(round(time - step))
    midpoint = max(0, min(full, midpoint))
    endpoint = max(0, min(full, endpoint))
    t_batch = torch.full((batch_size,), time, device=device, dtype=torch.long)

    noise = torch.randn_like(action)
    x = schedule.add_noise(action, noise, t_batch)
    with torch.no_grad():
        x0_mid, eps_mid = implied_x0(
            schedule, teacher, x, condition, t_batch, clamp=clamp
        )
        alpha_mid = schedule.alphas_cumprod[midpoint]
        x_mid = torch.sqrt(alpha_mid) * x0_mid + torch.sqrt(1.0 - alpha_mid) * eps_mid
        mid_batch = torch.full(
            (batch_size,), midpoint, device=device, dtype=torch.long
        )
        x0_end, eps_end = implied_x0(
            schedule, teacher, x_mid, condition, mid_batch, clamp=clamp
        )
        alpha_end = schedule.alphas_cumprod[endpoint]
        x_end_teacher = (
            torch.sqrt(alpha_end) * x0_end + torch.sqrt(1.0 - alpha_end) * eps_end
        )

    x0_student, eps_student = implied_x0(
        schedule, student, x, condition, t_batch, clamp=clamp
    )
    x_end_student = (
        torch.sqrt(alpha_end) * x0_student + torch.sqrt(1.0 - alpha_end) * eps_student
    )
    loss = F.mse_loss(x_end_student, x_end_teacher)
    router_loss = F.cross_entropy(student.last_router_logits, skill)
    with torch.no_grad():
        router_acc = float(
            (student.last_router_logits.argmax(dim=-1) == skill).float().mean().item()
        )
    return loss, loss, torch.zeros_like(loss), router_loss, router_acc, int(batch_size)


def _deploy_levels(level_count: int, chain_steps: int) -> list[int]:
    """Indices of the deployment chain levels inside the teacher's fine chain.

    The deployment sampler of ``k = chain_steps`` queries the model at the
    timesteps ``linspace(T-1, 0, k)``; the teacher's fine chain visits
    ``linspace(T-1, 0, teacher_steps)``. Returns the fine-chain indices of the
    ``k`` deployment levels, endpoints included and deduplicated.
    """
    k = max(2, int(chain_steps))
    n = max(2, int(level_count))
    indices = [int(round(i * (n - 1) / (k - 1))) for i in range(k)]
    unique: list[int] = []
    for index in indices:
        if not unique or unique[-1] != index:
            unique.append(index)
    return unique


def _deploy_step(
    schedule: DiffusionSchedule,
    student: ConditionalUNet1D,
    teacher: ConditionalUNet1D,
    batch: dict,
    device: str,
    *,
    teacher_steps: int = 16,
    chain_steps: int = 4,
    clamp: float = 4.0,
    student_clamp: float = 100.0,
    endpoint_weight: float = 0.0,
    eps_weight: float = 0.0,
    input_mode: str = "teacher",
    mix_prob: float = 0.5,
    input_noise: float = 0.0,
):
    """Deployment-chain consistency: one student step per deployment interval.

    The v6 re-attempt recipe. The frozen teacher walks its full DDIM-16 chain
    from one noise draw (`teacher_endpoint`), and the deployment levels of the
    stock ``ddim_sample(k=chain_steps)`` sampler are read off that chain. The
    student is teacher-forced at deployment level ``i`` (the teacher's own fine
    chain point) and must reproduce the fine chain point of level ``i + 1`` in
    *one* evaluation, in x-space:

        x_next_student = sqrt(a_{i+1}) * implied_x0(x_i, t_i)
                         + sqrt(1 - a_{i+1}) * eps(x_i, t_i)

    ``mse(x_next_student, x_{i+1}_teacher)`` is bounded (targets carry the
    sampler's noise scale), which is what the round-2 students lacked at
    ``t = T-1``. ``student_clamp`` is the *training-time* clamp for the
    student's implied x0; the deployment sampler's +/-4 clamp is the default
    and keeps the forward identical to deployment (the eps term still carries a
    gradient through the saturating first interval). ``eps_weight`` adds a
    direct noise-prediction distillation term against the teacher's eps at the
    same forced points (well-conditioned at every level).

    ``endpoint_weight`` optionally adds the last level's implied x0 against the
    teacher's final clean output.

    ``input_mode`` controls the input at levels after the first: ``teacher``
    always uses the teacher's fine-chain point (pure teacher forcing, which
    overfits the forced distribution - measured on the v5 pilot: the deployed
    DDIM-4 error rose from 0.154 rad at 900 batches to 0.203 rad at 5.3k
    batches), ``mixed`` uses the student's own previous output for a random
    ``mix_prob`` fraction of each batch, ``student`` always does. The targets
    stay the teacher's fine-chain points, so the student additionally learns to
    recover from its own drift (the exposure-bias fix). ``input_noise`` adds
    zero-mean Gaussian noise of that absolute std to the forced inputs.
    """
    action, condition, skill = _batch_tensors(batch, device)
    batch_size = action.shape[0]
    noise = torch.randn_like(action)
    with torch.no_grad():
        endpoint, (samples, times) = teacher_endpoint(
            schedule, teacher, action, condition, noise,
            num_steps=int(teacher_steps), clamp=clamp,
        )
        indices = _deploy_levels(len(times), int(chain_steps))
        inputs = [samples[index] for index in indices[:-1]]
        t_cur = [times[index] for index in indices[:-1]]
        t_next = [times[index] for index in indices[1:]]
        targets = [samples[index] for index in indices[1:]]
        eps_teacher = []
        if eps_weight:
            for x_in, t_a in zip(inputs, t_cur):
                _, eps_t = implied_x0(
                    schedule, teacher, x_in, condition, t_a.expand(batch_size),
                    clamp=clamp,
                )
                eps_teacher.append(eps_t)
        else:
            eps_teacher = [None] * len(inputs)
    terms = []
    eps_terms = []
    x0_last = None
    previous_student = None
    for index, (x_in, t_a, t_b, target, eps_t) in enumerate(
        zip(inputs, t_cur, t_next, targets, eps_teacher)
    ):
        mixed = x_in
        if index > 0 and input_mode != "teacher" and previous_student is not None:
            if input_mode == "student":
                mixed = previous_student
            else:  # mixed: per-sample teacher/student choice
                mask = (
                    torch.rand(batch_size, 1, 1, device=device) < float(mix_prob)
                )
                mixed = torch.where(mask, previous_student, x_in)
        if input_noise:
            mixed = mixed + float(input_noise) * torch.randn_like(mixed)
        x0_student, eps_student = implied_x0(
            schedule, student, mixed, condition, t_a.expand(batch_size),
            clamp=student_clamp,
        )
        alpha_next = schedule.alphas_cumprod[t_b]
        x_next = (
            torch.sqrt(alpha_next) * x0_student
            + torch.sqrt(1.0 - alpha_next) * eps_student
        )
        terms.append(F.mse_loss(x_next, target))
        if eps_t is not None:
            eps_terms.append(F.mse_loss(eps_student, eps_t))
        x0_last = x0_student
        previous_student = x_next.detach()
    loss = torch.stack(terms).mean()
    if eps_weight:
        loss = loss + float(eps_weight) * torch.stack(eps_terms).mean()
    if endpoint_weight:
        # `x0_last` is the implied x0 entering the last interval; anchoring it
        # on the teacher's final clean output adds the sampling-distillation
        # term on top of the x-space chain match (well-conditioned at t=33).
        loss = loss + float(endpoint_weight) * F.mse_loss(x0_last, endpoint)
    router_loss = F.cross_entropy(student.last_router_logits, skill)
    with torch.no_grad():
        router_acc = float(
            (student.last_router_logits.argmax(dim=-1) == skill).float().mean().item()
        )
    return loss, loss, torch.zeros_like(loss), router_loss, router_acc, int(batch_size)


def _progressive_step(
    schedule: DiffusionSchedule,
    student: ConditionalUNet1D,
    teacher: ConditionalUNet1D,
    batch: dict,
    device: str,
    *,
    target_steps: int,
    scheme: str = "chain",
    clamp: float = 4.0,
):
    """Dispatch to the selected progressive scheme (see both docstrings)."""
    if scheme == "chain":
        return _progressive_step_chain(
            schedule, student, teacher, batch, device,
            target_steps=target_steps, clamp=clamp,
        )
    if scheme == "continuous":
        return _progressive_step_continuous(
            schedule, student, teacher, batch, device,
            target_steps=target_steps, clamp=clamp,
        )
    raise ValueError(f"progressive scheme must be chain|continuous, got {scheme!r}")


@torch.no_grad()
def endpoint_probe(
    student: ConditionalUNet1D,
    teacher: ConditionalUNet1D,
    schedule: DiffusionSchedule,
    dataset,
    indices: list[int],
    device: str,
    *,
    teacher_steps: int = 16,
    student_steps: int = 1,
    limit: int = 32,
    seed: int = 7,
    clamp: float = 4.0,
) -> dict:
    """Paired endpoint deviation on a window slice (normalized action units).

    The teacher runs its shipped DDIM-16, the student the stock DDIM chain with
    `student_steps` steps; both start from the same noise seed and see the same
    condition. Returns the median first-action L2 between student and teacher
    (the metric that decides 1-step deployability offline) and each arm against
    the recorded action.
    """
    dtype = torch.float32
    count = min(int(limit), len(indices))
    if count == 0:
        return {"n": 0}
    rows = []
    for step_index in range(count):
        index = int(indices[step_index])
        sample = dataset[index]
        action = sample["action"][None].to(device)
        condition = (
            sample["image"][None].to(device),
            sample["goal"][None].to(device),
            sample["proprio"][None].to(device),
        )
        shape = (1, action.shape[1], action.shape[2])
        generator = torch.Generator(device=device).manual_seed(
            int(seed) * 100003 + index
        )
        target = schedule.ddim_sample(
            teacher, condition, shape, num_steps=int(teacher_steps), dtype=dtype,
            generator=generator,
        )
        generator = torch.Generator(device=device).manual_seed(
            int(seed) * 100003 + index
        )
        candidate = schedule.ddim_sample(
            student, condition, shape, num_steps=int(student_steps), dtype=dtype,
            generator=generator,
        )
        rec = action[0]
        target = target[0].float()
        candidate = candidate[0].float()
        rows.append(
            {
                "student_teacher": float(
                    torch.linalg.norm(candidate[:7, 0] - target[:7, 0])
                ),
                "student_rec": float(
                    torch.linalg.norm(candidate[:7, 0] - rec[:7, 0])
                ),
                "teacher_rec": float(
                    torch.linalg.norm(target[:7, 0] - rec[:7, 0])
                ),
            }
        )
    return {
        "n": count,
        "student_teacher_median": float(
            np.median([r["student_teacher"] for r in rows])
        ),
        "student_rec_median": float(np.median([r["student_rec"] for r in rows])),
        "teacher_rec_median": float(np.median([r["teacher_rec"] for r in rows])),
        "teacher_steps": int(teacher_steps),
        "student_steps": int(student_steps),
    }


def distill(
    teacher: str,
    data_dir: str = "datasets/demos_v9",
    out_dir: str = "checkpoints/distill_v1",
    epochs: int = 8,
    batch_size: int = 32,
    lr: float = 5e-5,
    loss: str = "both",
    x0_weight: float = 1.0,
    ema_decay: float = 0.999,
    clamp: float = 4.0,
    val_fraction: float = 0.15,
    seed: int = 0,
    device: str | None = None,
    workers: int = 2,
    router_loss_weight: float = 0.1,
    stride: int = 1,
    max_timestep: int = 0,
    max_batches: int = 0,
    save: str = "better",
    teacher_steps: int = 16,
    level_focus: str = "",
    progressive_scheme: str = "chain",
    chain_steps: int = 4,
    student_clamp: float = 100.0,
    endpoint_weight: float = 0.0,
    eps_weight: float = 0.0,
    input_mode: str = "teacher",
    mix_prob: float = 0.5,
    input_noise: float = 0.0,
    save_epochs: bool = False,
    probe_steps: int = 1,
    probe_every: int = 0,
    verbose: bool = True,
) -> str:
    """Distill `teacher` into a consistency student; returns the checkpoint path.

    ``save`` picks the network written to `policy_best.pt`: `online`, `ema`, or
    `better` (the smaller paired endpoint deviation from the teacher on the
    held-out windows). ``stride`` is the teacher DDIM step size the CD target
    uses (1 = adjacent chain points). ``max_batches`` > 0 truncates each epoch
    (smoke tests). ``max_timestep`` 0 means `T-1`.
    """
    if loss not in DISTILL_LOSSES:
        raise ValueError(f"loss must be one of {DISTILL_LOSSES}, got {loss!r}")
    if save not in ("online", "ema", "better", "best_probe"):
        raise ValueError(
            f"save must be online|ema|better|best_probe, got {save!r}"
        )
    torch.manual_seed(seed)
    np.random.seed(seed)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(out_dir, exist_ok=True)

    payload = torch.load(teacher, map_location="cpu", weights_only=False)
    config = dict(payload["config"])
    normalizer = _normalizer_from_checkpoint(payload)
    obs_horizon = int(config["obs_horizon"])
    action_horizon = int(config["action_horizon"])
    image_size = int(config["image_size"])
    num_train_steps = int(config["num_diffusion_steps"])
    max_timestep = int(max_timestep) or (num_train_steps - 1)

    store = EpisodeStore(
        data_dir, obs_horizon=obs_horizon, action_horizon=action_horizon,
        image_size=image_size,
    )
    if verbose:
        print(f"[distill] {store.summary()}", flush=True)
        print(f"[distill] skill histogram: {store.skill_histogram()}", flush=True)

    # Episode-level held-out split: a window from a held-out episode was never
    # seen in training, which is what the offline fidelity table needs.
    episode_count = len(store.episodes)
    order = np.random.RandomState(int(seed)).permutation(episode_count)
    val_count = max(1, int(round(episode_count * float(val_fraction))))
    val_episodes = sorted(int(v) for v in order[:val_count])
    val_set = set(val_episodes)
    train_indices = [
        i for i, (ep, _) in enumerate(store.windows) if ep not in val_set
    ]
    val_indices = [i for i, (ep, _) in enumerate(store.windows) if ep in val_set]
    if not train_indices or not val_indices:
        raise RuntimeError("empty train/val window split")

    window_dataset = WindowDataset(store, normalizer)
    loader_kwargs: dict = {
        "batch_size": batch_size, "shuffle": True, "drop_last": False,
        "num_workers": int(workers),
    }
    if int(workers) > 0:
        # Python 3.14 defaults to the forkserver start method, which pickles the
        # whole EpisodeStore (tens of GB of frames) to every worker and fails;
        # fork lets the workers inherit the arrays copy-on-write.
        loader_kwargs["multiprocessing_context"] = "fork"
        loader_kwargs["persistent_workers"] = True
    train_loader = DataLoader(Subset(window_dataset, train_indices), **loader_kwargs)
    if verbose:
        print(
            f"[distill] split: {episode_count - val_count} train / {val_count} val "
            f"episodes; {len(train_indices)} train / {len(val_indices)} val windows",
            flush=True,
        )

    schedule = DiffusionSchedule(
        num_train_steps, device=device, beta_schedule=config.get("beta_schedule", "linear")
    )
    level_probs = (
        parse_level_focus(level_focus, int(teacher_steps), schedule)
        if loss == "endpoint" else None
    )
    teacher_model = build_model(config, device)
    teacher_model.load_state_dict(payload["model"])
    teacher_model.eval()
    for parameter in teacher_model.parameters():
        parameter.requires_grad_(False)
    #: The original teacher, kept for the endpoint probes (progressive rounds
    #: overwrite `teacher_model` with the previous round's student).
    reference_teacher = _clone_module(teacher_model)
    reference_teacher.eval()
    for parameter in reference_teacher.parameters():
        parameter.requires_grad_(False)

    student = _clone_module(teacher_model).to(device).train()
    # `teacher_model` was frozen before the clone, so the copy inherits
    # requires_grad=False; the student must be trainable.
    for parameter in student.parameters():
        parameter.requires_grad_(True)
    ema = EMAModel(student, decay=ema_decay)
    optimizer = torch.optim.AdamW(student.parameters(), lr=lr, weight_decay=1e-6)
    parameters = sum(p.numel() for p in student.parameters())
    if verbose:
        print(
            f"[distill] device={device} parameters={parameters / 1e6:.2f}M "
            f"loss={loss} x0_weight={x0_weight} stride={stride} "
            f"max_t={max_timestep} ema={ema_decay}",
            flush=True,
        )

    history: list[dict] = []
    #: The epoch/network with the smallest held-out deployed probe (only used
    #: when ``save == "best_probe"``.) Teacher-forced training overfits the
    #: forced input distribution, so the *final* epoch is not necessarily the
    #: most deployable; this keeps the state that minimizes the probe metric the
    #: deployment uses (the stock DDIM chain at ``probe_steps``).
    best_probe: dict = {"score": float("inf"), "name": "", "state": None, "epoch": -1}
    if loss == "progressive":
        stages = _progressive_teacher_steps(int(teacher_steps))
    else:
        stages = [None]
    total_epochs = len(stages) * int(epochs)
    stage_target_steps = 0
    for global_epoch in range(total_epochs):
        stage_index = global_epoch // int(epochs)
        epoch = global_epoch % int(epochs)
        stage = stages[stage_index]
        if loss == "progressive" and epoch == 0:
            # Freeze the previous round's student as this round's teacher and
            # restart the EMA on the new student.
            teacher_model.load_state_dict(student.state_dict())
            teacher_model.eval()
            for parameter in teacher_model.parameters():
                parameter.requires_grad_(False)
            ema = EMAModel(student, decay=ema_decay)
            stage_target_steps = max(1, int(stage) // 2)
            if verbose:
                print(
                    f"[distill] progressive round {stage_index + 1}/{len(stages)}: "
                    f"{stage} -> {stage_target_steps} steps",
                    flush=True,
                )
        student.train()
        totals = np.zeros(4, dtype=np.float64)
        seen = 0
        start = time.time()
        for batch_index, batch in enumerate(train_loader):
            if max_batches and batch_index >= int(max_batches):
                break
            if loss == "endpoint":
                loss_value, cd_value, x0_value, router_value, router_acc, count = (
                    _endpoint_step(
                        schedule, student, teacher_model, batch, device,
                        teacher_steps=int(teacher_steps), clamp=clamp,
                        level_probs=level_probs,
                    )
                )
            elif loss == "deploy":
                loss_value, cd_value, x0_value, router_value, router_acc, count = (
                    _deploy_step(
                        schedule, student, teacher_model, batch, device,
                        teacher_steps=int(teacher_steps),
                        chain_steps=int(chain_steps), clamp=clamp,
                        student_clamp=float(student_clamp),
                        endpoint_weight=float(endpoint_weight),
                        eps_weight=float(eps_weight),
                        input_mode=input_mode, mix_prob=float(mix_prob),
                        input_noise=float(input_noise),
                    )
                )
            elif loss == "progressive":
                loss_value, cd_value, x0_value, router_value, router_acc, count = (
                    _progressive_step(
                        schedule, student, teacher_model, batch, device,
                        target_steps=int(stage_target_steps),
                        scheme=progressive_scheme, clamp=clamp,
                    )
                )
            else:
                loss_value, cd_value, x0_value, router_value, router_acc, count = (
                    _cd_step(
                        schedule, student, teacher_model, ema, batch, device,
                        loss_kind=loss, x0_weight=x0_weight, stride=stride,
                        max_timestep=max_timestep, clamp=clamp,
                    )
                )
            total = loss_value + float(router_loss_weight) * router_value
            optimizer.zero_grad(set_to_none=True)
            total.backward()
            torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
            optimizer.step()
            ema.update(student)
            totals += np.array(
                [
                    float(loss_value.item()),
                    float(cd_value.item()),
                    float(x0_value.item()),
                    router_acc,
                ]
            ) * count
            seen += count
        train_row = (totals / max(seen, 1)).tolist()

        # Fixed-seed validation slice (no EMA target; the same objective terms).
        student.eval()
        val_totals = np.zeros(3, dtype=np.float64)
        val_seen = 0
        with torch.no_grad():
            for batch_index, batch in enumerate(
                DataLoader(Subset(window_dataset, val_indices), batch_size=batch_size,
                           shuffle=False, num_workers=0)
            ):
                if max_batches and batch_index >= int(max_batches):
                    break
                if loss == "endpoint":
                    loss_value, _cd, _x0, _router, _acc, count = _endpoint_step(
                        schedule, student, teacher_model, batch, device,
                        teacher_steps=int(teacher_steps), clamp=clamp,
                        level_probs=None,
                    )
                    value = float(loss_value.item())
                    val_totals += np.array([value, value, value]) * count
                    val_seen += count
                    continue
                if loss == "deploy":
                    loss_value, _cd, _x0, _router, _acc, count = _deploy_step(
                        schedule, student, teacher_model, batch, device,
                        teacher_steps=int(teacher_steps),
                        chain_steps=int(chain_steps), clamp=clamp,
                        student_clamp=float(student_clamp),
                        endpoint_weight=float(endpoint_weight),
                        eps_weight=float(eps_weight),
                        input_mode=input_mode, mix_prob=float(mix_prob),
                        input_noise=float(input_noise),
                    )
                    value = float(loss_value.item())
                    val_totals += np.array([value, value, value]) * count
                    val_seen += count
                    continue
                if loss == "progressive":
                    loss_value, _cd, _x0, _router, _acc, count = _progressive_step(
                        schedule, student, teacher_model, batch, device,
                        target_steps=int(stage_target_steps),
                        scheme=progressive_scheme, clamp=clamp,
                    )
                    value = float(loss_value.item())
                    val_totals += np.array([value, value, value]) * count
                    val_seen += count
                    continue
                action, condition, _skill = _batch_tensors(batch, device)
                b = action.shape[0]
                val_generator = torch.Generator(device=device).manual_seed(
                    int(seed) * 7919 + global_epoch * 131 + batch_index
                )
                timesteps = torch.randint(
                    int(stride), int(max_timestep) + 1, (b,), generator=val_generator,
                    device=device, dtype=torch.long,
                )
                noise = torch.randn(
                    action.shape, generator=val_generator, device=device
                )
                noisy = schedule.add_noise(action, noise, timesteps)
                x0_teacher, eps_teacher = implied_x0(
                    schedule, teacher_model, noisy, condition, timesteps, clamp=clamp
                )
                alpha_prev = schedule.alphas_cumprod[timesteps - int(stride)]
                x_prev = (
                    torch.sqrt(alpha_prev)[:, None, None] * x0_teacher
                    + torch.sqrt(1.0 - alpha_prev)[:, None, None] * eps_teacher
                )
                x0_target, _ = implied_x0(
                    schedule, ema.model, x_prev, condition,
                    timesteps - int(stride), clamp=clamp,
                )
                x0_student, _ = implied_x0(
                    schedule, student, noisy, condition, timesteps, clamp=clamp
                )
                val_totals += np.array(
                    [
                        float(F.mse_loss(x0_student, x0_target).item()),
                        float(F.mse_loss(x0_student, x0_teacher).item()),
                        float(F.mse_loss(x0_student, x0_target).item())
                        + float(x0_weight)
                        * float(F.mse_loss(x0_student, x0_teacher).item()),
                    ]
                ) * b
                val_seen += b
        val_row = (val_totals / max(val_seen, 1)).tolist()
        student.train()
        probe_epoch = None
        if probe_every and (global_epoch + 1) % int(probe_every) == 0:
            student.eval()
            ema.model.eval()
            slice_indices = val_indices[: max(1, min(16, len(val_indices)))]
            online_probe = endpoint_probe(
                student, reference_teacher, schedule, window_dataset, slice_indices,
                device, student_steps=int(probe_steps), seed=int(seed), limit=16,
                clamp=clamp,
            )
            ema_probe = endpoint_probe(
                ema.model, reference_teacher, schedule, window_dataset, slice_indices,
                device, student_steps=int(probe_steps), seed=int(seed), limit=16,
                clamp=clamp,
            )
            probe_epoch = {
                "online": online_probe.get("student_teacher_median"),
                "ema": ema_probe.get("student_teacher_median"),
                "online_rec": online_probe.get("student_rec_median"),
                "teacher_rec": online_probe.get("teacher_rec_median"),
            }
            if save == "best_probe":
                for probe_name, probe_model, probe_result in (
                    ("online", student, online_probe),
                    ("ema", ema.model, ema_probe),
                ):
                    score = probe_result.get("student_teacher_median", float("inf"))
                    if score < best_probe["score"]:
                        best_probe = {
                            "score": float(score),
                            "name": probe_name,
                            "state": {
                                key: value.detach().clone()
                                for key, value in probe_model.state_dict().items()
                            },
                            "epoch": global_epoch + 1,
                        }
            student.train()
            if verbose:
                print(
                    f"[distill]   probe {probe_steps}-step vs DDIM-{16}: "
                    f"online {probe_epoch['online']:.4f} ema {probe_epoch['ema']:.4f} "
                    f"(rec: student {probe_epoch['online_rec']:.4f} "
                    f"teacher {probe_epoch['teacher_rec']:.4f})",
                    flush=True,
                )
        history.append(
            {
                "epoch": global_epoch,
                "stage": stage_index if stage is not None else 0,
                "target_steps": int(stage_target_steps),
                "train_loss": train_row[0],
                "train_cd": train_row[1],
                "train_x0": train_row[2],
                "router_acc": train_row[3],
                "val_cd": val_row[0],
                "val_x0": val_row[1],
                "val_objective": val_row[2],
                "endpoint_probe": probe_epoch,
                "seconds": time.time() - start,
                "windows": seen,
            }
        )
        if save_epochs:
            torch.save(
                {
                    "model": student.state_dict(),
                    "normalizer": payload["normalizer"],
                    "config": dict(config, sampler="consistency"),
                    "val_loss": val_row[2],
                    "provenance": {
                        "kind": "consistency_distill_epoch",
                        "epoch": global_epoch + 1,
                        "stage": stage_index if stage is not None else 0,
                        "target_steps": int(stage_target_steps),
                        "loss": loss,
                        "level_focus": level_focus,
                    },
                },
                os.path.join(out_dir, f"policy_epoch{global_epoch + 1}.pt"),
            )
        if verbose:
            print(
                f"[distill] epoch {global_epoch + 1}/{total_epochs} "
                f"stage={stage_index + 1}/{len(stages)} "
                f"loss={train_row[0]:.4f} cd={train_row[1]:.4f} "
                f"x0={train_row[2]:.4f} router_acc={train_row[3]:.3f} "
                f"val_cd={val_row[0]:.4f} val_x0={val_row[1]:.4f} "
                f"({time.time() - start:.1f}s)",
                flush=True,
            )

    # ---- choose the saved network (online vs EMA) ---------------------------- #
    student.eval()
    ema.model.eval()
    probe_indices = val_indices[: max(1, min(32, len(val_indices)))]
    probe_online = endpoint_probe(
        student, reference_teacher, schedule, window_dataset, probe_indices, device,
        student_steps=int(probe_steps), seed=int(seed), clamp=clamp,
    )
    probe_ema = endpoint_probe(
        ema.model, reference_teacher, schedule, window_dataset, probe_indices, device,
        student_steps=int(probe_steps), seed=int(seed), clamp=clamp,
    )
    if save == "ema":
        chosen, chosen_name = ema.model, "ema"
    elif save == "online":
        chosen, chosen_name = student, "online"
    elif save == "best_probe" and best_probe["state"] is not None:
        chosen = build_model(config, device)
        chosen.load_state_dict(best_probe["state"])
        chosen.eval()
        chosen_name = (
            f"best_probe:{best_probe['name']}@epoch{best_probe['epoch']}"
            f"({best_probe['score']:.4f})"
        )
    else:
        online_error = probe_online.get("student_teacher_median", float("inf"))
        ema_error = probe_ema.get("student_teacher_median", float("inf"))
        if ema_error < online_error:
            chosen, chosen_name = ema.model, "ema"
        else:
            chosen, chosen_name = student, "online"
    if verbose:
        print(
            f"[distill] endpoint probe ({probe_steps}-step vs teacher DDIM-16, "
            f"n={probe_online.get('n', 0)}): online {probe_online.get('student_teacher_median', float('nan')):.4f} "
            f"ema {probe_ema.get('student_teacher_median', float('nan')):.4f} "
            f"-> saved {chosen_name}",
            flush=True,
        )

    dataset_provenance = {
        "dir": os.path.abspath(data_dir),
        "index_md5": _md5(os.path.join(data_dir, "index.json")),
        "manifest_md5": _md5(os.path.join(data_dir, "manifest.json")),
        "episodes": episode_count,
        "windows": len(store),
        "train_windows": len(train_indices),
        "val_windows": len(val_indices),
        "val_episodes": val_episodes,
        "train_episodes": sorted(
            int(ep) for ep in range(episode_count) if ep not in val_set
        ),
    }
    provenance = {
        "kind": "consistency_distill",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "teacher_checkpoint": os.path.abspath(teacher),
        "teacher_checkpoint_md5": _md5(teacher),
        "teacher_val_loss": payload.get("val_loss", float("nan")),
        "teacher_config": config,
        "data": dataset_provenance,
        "loss": {
            "kind": loss,
            "x0_weight": float(x0_weight),
            "ema_decay": float(ema_decay),
            "stride": int(stride),
            "max_timestep": int(max_timestep),
            "clamp": float(clamp),
            "router_loss_weight": float(router_loss_weight),
            "teacher_steps": int(teacher_steps),
            "level_focus": level_focus,
            "progressive_scheme": progressive_scheme,
            "chain_steps": int(chain_steps),
            "student_clamp": float(student_clamp),
            "endpoint_weight": float(endpoint_weight),
            "eps_weight": float(eps_weight),
            "input_mode": str(input_mode),
            "mix_prob": float(mix_prob),
            "input_noise": float(input_noise),
        },
        "sampler": {
            "kind": "consistency",
            "note": (
                "deployed through the stock DDIM chain: ddim_sample(num_steps=k) "
                "evaluates the implied x0 at k chain points and re-noises between "
                "them, which is the consistency sampler at the same timesteps"
            ),
            "student_steps_probe": int(probe_steps),
            "deployable_steps": [1, 2, 4],
        },
        "epochs": int(epochs),
        "lr": float(lr),
        "batch_size": int(batch_size),
        "seed": int(seed),
        "device": str(device),
        "parameters": int(parameters),
        "saved_network": chosen_name,
        "endpoint_probe": {"online": probe_online, "ema": probe_ema},
        "tasks_md5": TASKS_MD5,
        "history": history,
    }
    out_config = dict(config)
    out_config["sampler"] = "consistency"
    out_config["consistency_distill"] = {
        "teacher": os.path.abspath(teacher),
        "teacher_md5": provenance["teacher_checkpoint_md5"],
        "loss": loss,
        "x0_weight": float(x0_weight),
        "stride": int(stride),
        "ema_decay": float(ema_decay),
        "saved_network": chosen_name,
    }
    out_payload = {
        "model": chosen.state_dict(),
        "normalizer": payload["normalizer"],
        "config": out_config,
        "val_loss": history[-1]["val_objective"] if history else float("nan"),
        "provenance": provenance,
    }
    out_path = os.path.join(out_dir, "policy_best.pt")
    torch.save(out_payload, out_path)
    with open(os.path.join(out_dir, "history.json"), "w", encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=2)
    if verbose:
        print(f"[distill] saved {out_path} ({chosen_name})", flush=True)
    return out_path
