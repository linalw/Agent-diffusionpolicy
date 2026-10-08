"""Load a trained checkpoint and run closed-loop inference inside Isaac Sim.

P4 adds an RTC-style asynchronous chunk runner (`RTCSettings`, `RTCSampler`,
`RealtimeChunker`). The reference is Physical Intelligence's Real-Time Chunking
(arXiv 2506.07339; LeRobot `RTCConfig`/`RTCProcessor`): generate the next action
chunk while the current one executes, freeze the actions that are guaranteed to
be executed during inference (the *inference delay*), and soft-inpaint the rest
so the new chunk continues the old one. The implementation here is
**interleaved**, not threaded: the DDIM chain is split across the control steps
of the inference window, because one simulator process steps physics on the same
GPU thread and a background sampling thread would contend with it (and the env
loop is tick-exact by construction). Everything is inference-time only - no
retraining, no checkpoint change.

    import os
    os.environ["FRUIT_RTC"] = "1"          # default off; shipped path unchanged

Knobs (all read from the environment, `RTCSettings.from_env`):

    FRUIT_RTC                    0|1 master switch (default 0)
    FRUIT_RTC_INFERENCE_DELAY    control steps the sampler is spread over and
                                 the number of old actions that execute during
                                 it (default: the env's execute_steps)
    FRUIT_RTC_EXECUTION_HORIZON  length of the soft-inpaint window, positions
                                 (LeRobot default 10)
    FRUIT_RTC_MAX_GUIDANCE_WEIGHT cap on the soft blend weight in [0,1]
                                 (LeRobot's guided default is 10.0; the inpaint
                                 formulation here needs no >1 gain)
    FRUIT_RTC_SCHEDULE           EXP|LINEAR|ONES|ZEROS (EXP is the reference
                                 default; LeRobot ships LINEAR)
    FRUIT_RTC_GUIDANCE           1|0: freeze + soft inpaint (default 1; the
                                 VLASH deployment sets 0)
    FRUIT_VLASH                  0|1 master switch for the VLASH deployment
                                 (default 0): enables the interleaved async
                                 chunker with guidance off and conditions the
                                 new chunk on the state rolled forward under
                                 the previous chunk's pending actions. The
                                 matching fine-tune is scripts/133_vlash_finetune.py.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np
import torch

from .data import Normalizer, downsample_frame
from .diffusion import DiffusionSchedule
from .model import ConditionalUNet1D

#: Prefix-weight schedules, the LeRobot `RTCAttentionSchedule` names.
RTC_SCHEDULES = ("EXP", "LINEAR", "ONES", "ZEROS")


@dataclass
class RTCSettings:
    """Environment-driven RTC configuration. Disabled by default."""

    enabled: bool = False
    #: 0 means "use the env's execute_steps" (filled in by the caller).
    inference_delay: int = 0
    execution_horizon: int = 10
    max_guidance_weight: float = 1.0
    schedule: str = "EXP"
    #: RTC prefix guidance (freeze + EXP soft inpaint). The VLASH-style
    #: deployment runs the same interleaved async chunker with guidance off
    #: (a plain chunk switch, no freeze/inpaint), so `FRUIT_VLASH=1` implies
    #: guidance off unless `FRUIT_RTC_GUIDANCE=1` is set explicitly.
    guidance: bool = True
    #: VLASH-style state roll-forward (arXiv 2512.01031), default off. The env
    #: conditions the new chunk on the execution-time state estimated by
    #: rolling the measured state forward under the previous chunk's pending
    #: actions; needs the env's `roll` callback (see `RealtimeChunker`).
    vlash: bool = False
    #: Roll-forward offset in chunk steps; 0 = the inference delay (the
    #: VLASH paper's rule: the smallest offset covering the measured latency).
    vlash_delta: int = 0

    @classmethod
    def from_env(cls) -> "RTCSettings":
        vlash = os.environ.get("FRUIT_VLASH", "0").strip() == "1"
        enabled = os.environ.get("FRUIT_RTC", "0").strip() == "1" or vlash
        schedule = os.environ.get("FRUIT_RTC_SCHEDULE", "EXP").strip().upper()
        if schedule not in RTC_SCHEDULES:
            raise ValueError(
                f"FRUIT_RTC_SCHEDULE must be one of {RTC_SCHEDULES}, got {schedule!r}"
            )
        guidance = os.environ.get("FRUIT_RTC_GUIDANCE", "").strip()
        if guidance == "":
            guidance = "0" if vlash else "1"
        return cls(
            enabled=enabled,
            inference_delay=int(os.environ.get("FRUIT_RTC_INFERENCE_DELAY", "0") or 0),
            execution_horizon=int(
                os.environ.get("FRUIT_RTC_EXECUTION_HORIZON", "10")
            ),
            max_guidance_weight=float(
                os.environ.get("FRUIT_RTC_MAX_GUIDANCE_WEIGHT", "1.0")
            ),
            schedule=schedule,
            guidance=guidance.strip() != "0",
            vlash=vlash,
            vlash_delta=int(os.environ.get("FRUIT_VLASH_DELTA", "0") or 0),
        )

    def summary(self) -> str:
        return (
            f"rtc={'on' if self.enabled else 'off'} delay={self.inference_delay} "
            f"horizon={self.execution_horizon} maxw={self.max_guidance_weight} "
            f"schedule={self.schedule} guidance={'on' if self.guidance else 'off'} "
            f"vlash={'on' if self.vlash else 'off'} vlash_delta={self.vlash_delta}"
        )


def rtc_prefix_weights(
    start: int, end: int, total: int, schedule: str = "EXP"
) -> np.ndarray:
    """LeRobot's `get_prefix_weights`, ported (positions × weight in [0,1]).

    ``start`` is the inference delay (hard-frozen prefix, weight 1), ``end`` the
    execution horizon (soft decay region ``[start, end)``), ``total`` the action
    horizon. ``EXP`` is the reference default: the linear ramp is warped by
    ``x * expm1(x) / (e - 1)`` so the far end of the window decays faster than
    linearly. Positions >= end get 0; positions < min(start, total) get 1.
    """
    start = min(int(start), int(end))
    if schedule == "ZEROS":
        weights = np.zeros(total, dtype=np.float32)
        weights[:start] = 1.0
        return weights
    if schedule == "ONES":
        weights = np.ones(total, dtype=np.float32)
        weights[int(end):] = 0.0
        return weights
    lin_len = max(int(end) - start, 0)
    if lin_len > 0:
        lin = np.linspace(1.0, 0.0, lin_len + 2, dtype=np.float32)[1:-1]
    else:
        lin = np.zeros(0, dtype=np.float32)
    if schedule == "EXP" and lin_len > 0:
        lin = lin * np.expm1(lin) / (math.e - 1.0)
    weights = np.concatenate(
        [lin, np.zeros(max(total - int(end), 0), dtype=np.float32)]
    )
    if start > 0:
        weights = np.concatenate([np.ones(start, dtype=np.float32), weights])
    return weights[:total]


def _split_steps(num_steps: int, calls: int) -> list[int]:
    """Split `num_steps` denoising updates across exactly `calls` calls.

    ``sum(split(S, C)) == S`` and ``len(split) == C`` for any C >= 1. With
    C > S some calls carry zero updates and the sampler finishes before the
    planned window - the chunker then switches on the actual completion count.
    """
    if calls <= 0:
        raise ValueError("calls must be positive")
    return [
        int((i + 1) * num_steps // calls) - int(i * num_steps // calls)
        for i in range(calls)
    ]


class RTCSampler:
    """One interleaved DDIM chain with RTC freeze + soft inpaint guidance.

    The sample tensor is the model layout ``(1, action_dim, action_horizon)`` in
    normalised action units. At every denoising step the predicted clean sample
    is blended toward the previous chunk's leftover,

        ``x0 <- x0 + w * (target - x0)``

    with ``w`` from ``rtc_prefix_weights`` (1 on the frozen prefix - RePaint-style
    inpainting, re-noised with the model's own predicted noise - and an
    exponential soft mask over ``[inference_delay, execution_horizon)``). This is
    the inpainting form of RTC's prefix guidance; the autograd-guided velocity
    formulation needs a backward pass per denoising step (~3x the cost) and is
    documented as the alternative not taken.
    """

    def __init__(
        self,
        runner: "PolicyRunner",
        condition: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        prev_leftover: np.ndarray | None,
        *,
        num_steps: int,
        inference_delay: int,
        execution_horizon: int = 10,
        max_guidance_weight: float = 1.0,
        schedule: str = "EXP",
    ):
        if schedule not in RTC_SCHEDULES:
            raise ValueError(f"unknown RTC schedule {schedule!r}")
        self.runner = runner
        self.condition = condition
        self.schedule = runner.schedule
        self.num_steps = int(num_steps)
        self.inference_delay = max(1, int(inference_delay))
        self.execution_horizon = int(execution_horizon)

        dtype = torch.float16 if runner.use_half else torch.float32
        shape = (1, int(runner.config["action_dim"]), int(runner.config["action_horizon"]))
        self.x = torch.randn(
            shape, device=runner.device, dtype=dtype, generator=runner.generator
        )
        self.times = torch.linspace(
            self.schedule.num_train_steps - 1, 0, self.num_steps,
            dtype=torch.long, device=runner.device,
        )
        self.step_index = 0
        self.calls = 0
        self.call_plan = _split_steps(self.num_steps, self.inference_delay)

        horizon = int(runner.config["action_horizon"])
        self.target = None
        self.weights = None
        self.prefix_length = 0
        if prev_leftover is not None and len(prev_leftover) > 0:
            prev = np.asarray(prev_leftover, dtype=np.float32)[:horizon]
            start = min(self.inference_delay, len(prev))
            end = min(self.execution_horizon, len(prev))
            weights = rtc_prefix_weights(start, end, horizon, schedule)
            weights[start : end] = np.minimum(
                weights[start : end], float(max_guidance_weight)
            )
            normalized = runner.normalizer.normalize_action(prev)
            padded = np.zeros((horizon, normalized.shape[1]), dtype=np.float32)
            padded[: len(prev)] = normalized
            # A non-finite previous action must not enter the inpaint target:
            # a zero weight does not neutralise it (`0 * NaN` is still NaN), so
            # zero both the weight and the target row at those positions. The
            # env drops non-finite predictions, but the queue would otherwise
            # carry one for a whole horizon and poison every later chunk.
            bad = ~np.isfinite(padded).all(axis=1)
            if bad.any():
                weights[bad] = 0.0
                padded[bad] = 0.0
            self.target = torch.from_numpy(padded.T[None]).to(
                runner.device, dtype
            )
            self.weights = torch.from_numpy(weights[None, None, :]).to(
                runner.device, dtype
            )
            self.prefix_length = start

    # ------------------------------------------------------------------ #
    def advance(self) -> bool:
        """Run this call's share of denoising updates; True when finished."""
        if self.step_index >= self.num_steps:
            return True
        count = self.call_plan[min(self.calls, len(self.call_plan) - 1)]
        self.calls += 1
        with torch.no_grad():
            for _ in range(count):
                self._denoise_step()
        return self.step_index >= self.num_steps

    @torch.no_grad()
    def _denoise_step(self) -> None:
        if self.step_index >= self.num_steps:
            return
        i = self.step_index
        t = self.times[i]
        alpha = self.schedule.alphas_cumprod[t]
        alpha_prev = (
            self.schedule.alphas_cumprod[self.times[i + 1]]
            if i + 1 < self.num_steps
            else torch.tensor(1.0, device=self.runner.device)
        )
        predicted_noise = self.runner.model.denoise(
            self.x, self.condition, t.expand(self.x.shape[0])
        )
        predicted_clean = (
            self.x - torch.sqrt(1 - alpha) * predicted_noise
        ) / torch.sqrt(alpha)
        predicted_clean = predicted_clean.clamp(-4.0, 4.0)
        if self.weights is not None:
            predicted_clean = predicted_clean + self.weights * (
                self.target - predicted_clean
            )
        self.x = torch.sqrt(alpha_prev) * predicted_clean + torch.sqrt(
            1 - alpha_prev
        ) * predicted_noise
        self.step_index += 1

    def chunk(self) -> np.ndarray:
        """The sampled chunk in raw action units, ``(action_horizon, action_dim)``."""
        action = self.x[0].float().transpose(0, 1).cpu().numpy()
        return self.runner.normalizer.denormalize_action(action)


class RealtimeChunker:
    """Env-facing RTC queue: one action per control step, async next chunk.

    The env consumes one action per physics control step; the chunker keeps the
    current chunk and an interleaved sampler for the next one. A new sampler
    starts whenever the current chunk's unexecuted tail is about to be consumed,
    is spread over ``inference_delay`` control steps, and its first
    ``inference_delay`` positions are frozen to the old actions executed while it
    runs (the same actions the robot is committed to); positions
    ``[inference_delay, execution_horizon)`` are soft-inpainted toward the old
    chunk's tail. On completion the new chunk replaces the old one at its index
    ``elapsed`` - the next action the robot should take - so the executed stream
    is continuous by construction.

    ``period`` (the env's ``execute_steps``) is how many control steps each
    chunk contributes before the next one takes over; it equals
    ``inference_delay`` for the default configuration, so
    ``execute_steps=1/2/4`` is the same tight-loop knob as in the synchronous
    path. The first chunk of an episode is sampled synchronously (nothing to
    continue from).

    Two deployment variants share the queue. RTC (default) freezes the first
    ``inference_delay`` actions to the old chunk and soft-inpaints the rest
    (``guidance``). VLASH (``vlash``, guidance off) conditions each new chunk on
    the state the caller rolls forward under the pending actions instead
    (``next_action(..., roll=...)``); it needs a checkpoint fine-tuned with
    temporal offsets (``scripts/133_vlash_finetune.py``).
    """

    def __init__(
        self,
        runner: "PolicyRunner",
        *,
        execute_steps: int = 4,
        settings: RTCSettings | None = None,
        trace_samplers: bool = False,
    ):
        settings = settings or RTCSettings.from_env()
        self.runner = runner
        self.execute_steps = max(1, int(execute_steps))
        self.settings = settings
        delay = int(settings.inference_delay) or self.execute_steps
        self.inference_delay = max(1, min(delay, runner.action_horizon))
        self.execution_horizon = max(1, int(settings.execution_horizon))
        #: RTC prefix guidance (freeze + soft inpaint); off for VLASH.
        self.guidance = bool(settings.guidance)
        #: VLASH state roll-forward; needs the caller's `roll(measured, window)`
        #: callback on each `next_action`.
        self.vlash = bool(settings.vlash)
        self.vlash_delta = int(settings.vlash_delta) or self.inference_delay
        #: Offline diagnostics only (`scripts/124_rtc_boundary.py`): one row per
        #: completed sampler with the previous leftover and the new chunk. Never
        #: enabled in the env loop.
        self.trace_samplers = bool(trace_samplers)
        self.trace: list[dict] = []
        self.reset()

    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        self.actions: np.ndarray | None = None
        self.pos = 0
        self.sampler: RTCSampler | None = None
        self.start_pos = 0
        self.last_switch = False
        self.chunks_sampled = 0
        #: Actions of the new chunk that executed during inference (frozen prefix).
        self.last_prefix = 0
        self.trace = []

    def _observe(self, observe) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.runner._condition(
            np.asarray(observe(), dtype=np.float32), self._goal
        )

    def next_action(self, observe, goal: np.ndarray, num_steps: int,
                    roll=None) -> np.ndarray:
        """One action for this control step. ``observe`` returns the 25-D proprio.

        ``observe`` is called only when a chunk sample starts, in the same order
        the synchronous path reads proprio (once per act call), so the extra
        read cost stays out of the control loop.

        ``roll(measured_proprio, pending_actions)`` (VLASH only, optional) maps
        the measured proprio and the slice of the current chunk that will
        execute during the inference delay to the estimated execution-time
        proprio; the sampler is then conditioned on it. Without the callback
        the measured proprio is used, exactly as the RTC path.
        """
        self._goal = np.asarray(goal, dtype=np.float32)
        self.last_switch = False
        if self.actions is None:
            # First chunk of the episode: nothing to continue from.
            self.actions = self.runner.act(
                np.asarray(observe(), dtype=np.float32), self._goal,
                num_steps=int(num_steps),
            )
            self.pos = 0
            self.chunks_sampled += 1
        if self.sampler is None:
            if self.pos >= len(self.actions):
                # Queue exhausted with no sampler running (only possible when
                # `num_steps < inference_delay` so the sampler finished before
                # the chunk did): sample synchronously and restart the queue.
                self.actions = self.runner.act(
                    np.asarray(observe(), dtype=np.float32), self._goal,
                    num_steps=int(num_steps),
                )
                self.pos = 0
                self.chunks_sampled += 1
            else:
                self.start_pos = self.pos
                previous = self.actions[self.pos :] if self.guidance else None
                if self.vlash and roll is not None:
                    measured = np.asarray(observe(), dtype=np.float32)
                    window = self.actions[
                        self.pos : self.pos + self.vlash_delta
                    ]
                    condition = self.runner._condition(
                        roll(measured, window), self._goal
                    )
                else:
                    condition = self._observe(observe)
                self.sampler = RTCSampler(
                    self.runner,
                    condition,
                    previous,
                    num_steps=int(num_steps),
                    inference_delay=self.inference_delay,
                    execution_horizon=self.execution_horizon,
                    max_guidance_weight=self.settings.max_guidance_weight,
                    schedule=self.settings.schedule,
                )
        action = np.asarray(self.actions[self.pos], dtype=np.float32).copy()
        self.pos += 1
        if self.sampler is not None:
            finished = self.sampler.advance()
            if finished:
                new_chunk = self.sampler.chunk()
                if not np.isfinite(new_chunk).all():
                    # A non-finite chunk would execute for `horizon` steps and
                    # then keep contaminating the inpaint target. Recover with
                    # the synchronous sampler (the legacy behaviour), which is
                    # clean as soon as the condition is finite again.
                    new_chunk = self.runner.act(
                        np.asarray(observe(), dtype=np.float32),
                        self._goal,
                        num_steps=int(num_steps),
                    )
                if self.trace_samplers:
                    previous = (
                        np.asarray(self.actions[self.start_pos :], dtype=np.float64).copy()
                        if self.actions is not None
                        else None
                    )
                    self.trace.append(
                        {
                            "start_pos": int(self.start_pos),
                            "prefix": int(self.sampler.prefix_length),
                            "delay": int(self.sampler.inference_delay),
                            "prev": previous,
                            "chunk": np.asarray(new_chunk, dtype=np.float64).copy(),
                        }
                    )
                self.actions = new_chunk
                self.last_prefix = self.sampler.prefix_length
                self.pos = self.pos - self.start_pos
                self.sampler = None
                self.last_switch = True
                self.chunks_sampled += 1
        return action

    def boundary_action(self) -> np.ndarray | None:
        """The action executed just before the pending switch (diagnostics)."""
        if self.actions is None or self.pos <= 0:
            return None
        return np.asarray(self.actions[self.pos - 1], dtype=np.float32)


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

        self.schedule = DiffusionSchedule(
            config["num_diffusion_steps"], device=device,
            beta_schedule=config.get("beta_schedule", "linear"),
        )
        #: Seed for the diffusion sampling noise. Unset (the default) gives fresh
        #: noise per inference, which leaves a closed-loop evaluation outcome-stable
        #: but not bit-reproducible; set `FRUIT_POLICY_SEED` to make runs comparable
        #: (see the note in `diffusion.ddim_sample` and the WORKLOG).
        seed = os.environ.get("FRUIT_POLICY_SEED", "").strip()
        self.generator = None
        if seed:
            self.generator = torch.Generator(device=device).manual_seed(int(seed))
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
        return downsample_frame(image, self.image_size)

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
    def _condition(self, proprio: np.ndarray, goal: np.ndarray):
        """The model condition tuple for the current frame buffer (shared path).

        Extracted from `act` so the interleaved sampler can snapshot a condition
        at the start of an inference window and reuse it across control steps.
        """
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
        return (image_t, goal_t, proprio_t)

    @torch.no_grad()
    def act(self, proprio: np.ndarray, goal: np.ndarray, num_steps: int | None = None) -> np.ndarray:
        """Sample an action chunk. Returns (action_horizon, action_dim) in raw units."""
        num_steps = self.default_steps if num_steps is None else num_steps
        dtype = torch.float16 if self.use_half else torch.float32
        condition = self._condition(proprio, goal)

        sample = self.schedule.ddim_sample(
            self.model,
            condition,
            (1, self.config["action_dim"], self.action_horizon),
            num_steps=num_steps,
            dtype=dtype,
            generator=self.generator,
        )
        action = sample[0].float().transpose(0, 1).cpu().numpy()  # (horizon, action_dim)
        return self.normalizer.denormalize_action(action)
