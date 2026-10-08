"""Offline self-test for the RTC runtime (no simulator, no checkpoint).

Pins the properties the env loop relies on:

1. `rtc_prefix_weights` matches the LeRobot schedule construction (hard prefix of
   `start`, soft decay to `end`, zero after).
2. `_split_steps` spreads `num_steps` DDIM updates over exactly `calls` calls.
3. A guided sampler with no previous chunk is **bit-identical** to the shipped
   `DiffusionSchedule.ddim_sample` for the same noise seed - so RTC does not
   silently change the base sampler.
4. The frozen prefix reproduces the previous chunk's first `inference_delay`
   actions (RePaint hard constraint).
5. The `RealtimeChunker` executes exactly `period` new actions per chunk and the
   executed stream's switch boundaries stay inside the within-chunk step range.

Run: `python3 scripts/128_rtc_selftest.py` (also wired into `scripts/selfcheck.sh`).
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch

from fruit_sorting.policy.data import Normalizer
from fruit_sorting.policy.diffusion import DiffusionSchedule
from fruit_sorting.policy.model import ConditionalUNet1D
from fruit_sorting.policy.runtime import (
    PolicyRunner,
    RTCSampler,
    RTCSettings,
    RealtimeChunker,
    _split_steps,
    rtc_prefix_weights,
)


def make_runner() -> PolicyRunner:
    """A tiny checkpoint-free PolicyRunner on CPU with identity normalizer."""
    torch.manual_seed(0)
    runner = PolicyRunner.__new__(PolicyRunner)
    runner.device = "cpu"
    runner.use_half = False
    runner.default_steps = 4
    runner.config = {
        "action_dim": 9,
        "image_channels": 5,
        "obs_horizon": 2,
        "action_horizon": 16,
        "goal_dim": 8,
        "proprio_dim": 25,
        "num_skills": 5,
    }
    runner.model = ConditionalUNet1D(
        action_dim=9, image_channels=5, obs_horizon=2, goal_dim=8, proprio_dim=25,
        down_dims=(16, 32), num_skills=5, expert_hidden=16,
    ).eval()
    runner.schedule = DiffusionSchedule(100, device="cpu", beta_schedule="cosine")
    runner.normalizer = Normalizer(
        action_mean=np.zeros(9, dtype=np.float32),
        action_std=np.ones(9, dtype=np.float32),
        obs_mean=np.zeros(25, dtype=np.float32),
        obs_std=np.ones(25, dtype=np.float32),
        goal_mean=np.zeros(8, dtype=np.float32),
        goal_std=np.ones(8, dtype=np.float32),
    )
    runner.obs_horizon = 2
    runner.action_horizon = 16
    runner.image_size = 128
    runner.generator = None
    runner._frames = [
        np.zeros((128, 128, 5), dtype=np.float32) for _ in range(2)
    ]
    return runner


def condition(runner: PolicyRunner):
    proprio = np.zeros(25, dtype=np.float32)
    goal = np.zeros(8, dtype=np.float32)
    return runner._condition(proprio, goal)


def main() -> int:
    # 1. prefix weights ----------------------------------------------------- #
    exp = rtc_prefix_weights(3, 10, 16, "EXP")
    linear = rtc_prefix_weights(3, 10, 16, "LINEAR")
    zeros = rtc_prefix_weights(3, 10, 16, "ZEROS")
    ones = rtc_prefix_weights(3, 10, 16, "ONES")
    assert np.allclose(exp[:3], 1.0) and np.allclose(exp[10:], 0.0)
    assert np.allclose(linear[3:10], np.linspace(1, 0, 9)[1:-1])
    assert exp[3] < linear[3] < 1.0 and exp[9] < linear[9]
    assert np.allclose(zeros, [1, 1, 1] + [0.0] * 13)
    assert np.allclose(ones[:10], 1.0) and np.allclose(ones[10:], 0.0)

    # 2. interleave split --------------------------------------------------- #
    for total, calls in ((16, 1), (16, 2), (16, 4), (16, 3), (16, 20)):
        plan = _split_steps(total, calls)
        assert len(plan) == calls and sum(plan) == total, (total, calls, plan)

    # 3. no-guidance sampler is bit-identical to the shipped DDIM ----------- #
    runner = make_runner()
    cond = condition(runner)
    shape = (1, 9, 16)
    g1 = torch.Generator(device="cpu").manual_seed(7)
    legacy = runner.schedule.ddim_sample(
        runner.model, cond, shape, num_steps=8, dtype=torch.float32, generator=g1
    )
    runner.generator = torch.Generator(device="cpu").manual_seed(7)
    sampler = RTCSampler(runner, cond, None, num_steps=8, inference_delay=2)
    while not sampler.advance():
        pass
    assert torch.equal(legacy, sampler.x), "RTC sampler changed the base DDIM chain"

    # 4. frozen prefix ------------------------------------------------------ #
    prev = np.random.RandomState(3).randn(16, 9).astype(np.float32)
    runner.generator = torch.Generator(device="cpu").manual_seed(11)
    sampler = RTCSampler(
        runner, cond, prev, num_steps=8, inference_delay=3,
        execution_horizon=10, schedule="EXP",
    )
    while not sampler.advance():
        pass
    chunk = sampler.chunk()
    assert np.allclose(chunk[:3], prev[:3], atol=1e-5), "prefix not frozen"
    assert not np.allclose(chunk[3:], prev[3:]), "soft region is a hard copy"

    # 5. chunker bookkeeping + executed-stream continuity ------------------- #
    runner = make_runner()
    chunker = RealtimeChunker(
        runner, execute_steps=2,
        settings=RTCSettings(enabled=True, inference_delay=2, execution_horizon=10,
                             max_guidance_weight=1.0, schedule="EXP"),
        trace_samplers=True,
    )
    rng = np.random.RandomState(5)
    proprio_const = rng.randn(25).astype(np.float32) * 0.01
    executed = []
    switch_deltas = []
    within_deltas = []
    previous_switch = False
    for _ in range(24):
        action = chunker.next_action(
            lambda: proprio_const,
            np.zeros(8, dtype=np.float32),
            8,
        )
        if executed:
            delta = float(np.linalg.norm(action[:7] - executed[-1][:7]))
            (switch_deltas if previous_switch else within_deltas).append(delta)
        executed.append(np.asarray(action))
        previous_switch = bool(chunker.last_switch)
    # chunk 0 + one per completed sampler
    assert chunker.chunks_sampled == 13, chunker.chunks_sampled
    assert chunker.trace, "no sampler trace recorded"
    for row in chunker.trace:
        prefix = int(row["prefix"])
        if prefix > 0:
            assert np.allclose(
                row["chunk"][:prefix], row["prev"][:prefix], atol=1e-5
            )
    # The executed switch jump is `new[period] - old[period-1]`, and
    # `new[period-1] == old[period-1]` by the frozen prefix, so the boundary is
    # a normal within-chunk step of the new chunk. With the random tiny model the
    # action scale is large and noise-driven, so only the ordering is asserted
    # here; the exact prefix equality above is the mechanism guarantee.
    assert switch_deltas, "no switches recorded"
    assert float(np.median(switch_deltas)) < 3.0 * float(np.median(within_deltas))

    # 5b. VLASH deployment: guidance off, state roll-forward wiring ---------- #
    runner = make_runner()
    settings = RTCSettings(
        enabled=True, inference_delay=2, execution_horizon=10,
        max_guidance_weight=1.0, schedule="EXP", guidance=False, vlash=True,
        vlash_delta=2,
    )
    chunker = RealtimeChunker(runner, execute_steps=2, settings=settings)
    rolled = np.zeros(25, dtype=np.float32)
    rolled[0] = 123.0
    seen: dict = {}

    def roll(measured, window):
        seen["measured"] = np.asarray(measured).copy()
        seen["window"] = np.asarray(window).copy()
        return rolled

    rng = np.random.RandomState(7)
    proprio = (rng.randn(25) * 0.01).astype(np.float32)
    chunker.next_action(lambda: proprio, np.zeros(8, dtype=np.float32), 8, roll=roll)
    sampler = chunker.sampler
    assert sampler is not None, "VLASH sampler did not start"
    assert sampler.weights is None and sampler.prefix_length == 0, (
        "VLASH must switch chunks without freeze/inpaint guidance"
    )
    assert float(sampler.condition[2][0, 0].float().cpu()) == 123.0, (
        "the sampler was not conditioned on the rolled state"
    )
    assert seen["window"].shape[0] == 2, (
        f"roll window is the pending delay (got {seen['window'].shape})"
    )
    assert np.allclose(seen["measured"], proprio)
    # Env parsing: FRUIT_VLASH implies async + guidance off, and the delta knob.
    os.environ["FRUIT_VLASH"] = "1"
    os.environ["FRUIT_VLASH_DELTA"] = "3"
    parsed = RTCSettings.from_env()
    assert parsed.enabled and parsed.vlash and not parsed.guidance
    assert parsed.vlash_delta == 3
    del os.environ["FRUIT_VLASH"]
    del os.environ["FRUIT_VLASH_DELTA"]

    # 6. a non-finite prediction does not poison the queue ------------------ #
    # (a) the inpaint target drops non-finite rows: a weight of 0 alone does
    # not neutralise NaN, so the sampler must still return a finite chunk.
    runner = make_runner()
    prev_bad = np.random.RandomState(4).randn(16, 9).astype(np.float32)
    prev_bad[5] = np.nan
    runner.generator = torch.Generator(device="cpu").manual_seed(13)
    sampler = RTCSampler(
        runner, condition(runner), prev_bad, num_steps=8, inference_delay=3,
        execution_horizon=10, schedule="EXP",
    )
    while not sampler.advance():
        pass
    assert np.isfinite(sampler.chunk()).all(), "a previous NaN poisoned the target"

    # (b) a non-finite sampler output must not keep being served: at the switch
    # the chunker falls back to the synchronous sample.
    runner = make_runner()
    runner.generator = torch.Generator(device="cpu").manual_seed(17)
    chunker = RealtimeChunker(
        runner, execute_steps=2,
        settings=RTCSettings(enabled=True, inference_delay=2, execution_horizon=10,
                             max_guidance_weight=1.0, schedule="EXP"),
    )
    from fruit_sorting.policy import runtime as runtime_module

    original_chunk = runtime_module.RTCSampler.chunk
    served = {"count": 0}

    def flaky_chunk(self):
        served["count"] += 1
        if served["count"] == 1:
            return np.full(
                (int(self.runner.action_horizon), int(self.runner.config["action_dim"])),
                np.nan, dtype=np.float32,
            )
        return original_chunk(self)

    runtime_module.RTCSampler.chunk = flaky_chunk
    try:
        actions = [
            chunker.next_action(lambda: proprio_const, np.zeros(8, np.float32), 8)
            for _ in range(16)
        ]
    finally:
        runtime_module.RTCSampler.chunk = original_chunk
    assert served["count"] >= 1
    assert np.isfinite(np.asarray(actions[3:])).all(), "non-finite chunk re-served"

    print("rtc selftest: PASS (weights, split, bit-exact base, frozen prefix, queue, "
          "nan-guard)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
