#!/usr/bin/env python3
"""P141 self-test: the belt state reaches the model as an observation.

The phase's claim is narrow and each clause is checked here:

1. **The gate is off by default** - the 8-D goal and the 25-D proprio are what
   an unset environment builds, and every existing store loads unchanged.
2. **The 26th proprio column is per frame** when the store carries the trace
   (`belt_speed`, written by the collector under `FRUIT_OBS_SPEED=1`), and the
   per-episode pin still answers for a pre-P141 store.
3. **The goal pair is `(v_belt, a_belt)`**, fixed units, and `a_belt` is the
   same low-passed derivative the live loop runs.
4. **The warm starts preserve the function at step 0**: the goal's two new
   columns are zeros (no influence), and the horizon widening is
   `0.5 * [w, w]` - which reproduces the 2-frame embedding exactly when the
   last two frames repeat the first two.
5. **A real checkpoint loads and forwards** after all three wideners.
6. **The latency knobs resolve** (`FRUIT_POLICY_EXEC_STEPS`,
   `FRUIT_POLICY_DDIM`) with the shipped defaults.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fruit_sorting.policy import data as data_mod  # noqa: E402
from fruit_sorting.policy.data import (  # noqa: E402
    GOAL_AUX_MEAN,
    GOAL_AUX_STD,
    GOAL_DIM,
    PROPRIO_DIM,
    EpisodeStore,
    belt_accel_trace,
    goal_aux_enabled,
)

CHECKS = {"passed": 0, "failed": 0}


def check(condition, message):
    if condition:
        CHECKS["passed"] += 1
        print(f"  ok: {message}")
    else:
        CHECKS["failed"] += 1
        print(f"  FAIL: {message}")


def source(*parts) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
# 1. the gate
# --------------------------------------------------------------------------- #
def test_gate():
    print("[1] the gate is off by default")
    old = os.environ.pop("FRUIT_OBS_GOAL_AUX", None)
    try:
        check(not goal_aux_enabled(), "unset -> the 8-D goal")
        os.environ["FRUIT_OBS_GOAL_AUX"] = "1"
        check(goal_aux_enabled(), "=1 -> the pair is armed")
        os.environ["FRUIT_OBS_GOAL_AUX"] = "0"
        check(not goal_aux_enabled(), "=0 -> off")
        os.environ["FRUIT_OBS_GOAL_AUX"] = "yes"
        check(not goal_aux_enabled(), "anything but '1' stays off (strict)")
    finally:
        os.environ.pop("FRUIT_OBS_GOAL_AUX", None)
        if old is not None:
            os.environ["FRUIT_OBS_GOAL_AUX"] = old
    check(GOAL_DIM == 8 and PROPRIO_DIM == 25, "the shipped widths are 8 and 25")
    check(
        len(GOAL_AUX_MEAN) == 2 and len(GOAL_AUX_STD) == 2,
        "the pair has two fixed normaliser entries",
    )
    check(GOAL_AUX_MEAN[0] == 0.12 and GOAL_AUX_STD[0] == 0.05,
          "v_belt reuses the proprio channel's (0.12, 0.05) units")


# --------------------------------------------------------------------------- #
# 2. the acceleration filter is a derivative
# --------------------------------------------------------------------------- #
def test_accel():
    print("[2] a_belt is a low-passed derivative")
    dt = 1.0 / 120.0
    t = np.arange(240) * dt
    amp, hz = 0.04, 0.5
    speed = 0.12 + amp * np.sin(2.0 * np.pi * hz * t)
    accel = belt_accel_trace(speed, dt=dt, tau=0.002)
    analytic = amp * 2.0 * np.pi * hz * np.cos(2.0 * np.pi * hz * t)
    lo, hi = 20, 220
    err = float(np.sqrt(np.mean((accel[lo:hi] - analytic[lo:hi]) ** 2)))
    rms = float(np.sqrt(np.mean(analytic[lo:hi] ** 2)))
    check(err / rms < 0.05,
          f"a 0.04 m/s x 0.5 Hz wave reads its derivative (rel rms "
          f"{err / rms:.3f} < 0.05)")
    check(abs(float(accel[0])) < 1e-9, "the first frame has no derivative")
    check(np.all(np.isfinite(accel)), "the filter is finite everywhere")


# --------------------------------------------------------------------------- #
# 3. a synthetic store: per-frame column and the 10-D goal
# --------------------------------------------------------------------------- #
def _write_store(root: str, frames: int = 40, trace: bool = True) -> None:
    rng = np.random.default_rng(0)
    os.makedirs(root, exist_ok=True)
    dt = 1.0 / 120.0
    t = np.arange(frames) * dt
    speed = 0.12 + 0.04 * np.sin(2.0 * np.pi * 0.5 * t)
    joint = rng.normal(0.0, 0.1, size=(frames, 22)).astype(np.float32)
    finger = np.full((frames, 1), 0.044, dtype=np.float32)
    tactile = np.zeros((frames, 2), dtype=np.float32)
    goal = np.zeros((frames, 8), dtype=np.float32)
    goal[:, 3:6] = [0.0, -0.12, 0.0]
    goal[:, 6] = 0.06
    action = rng.normal(0.0, 0.1, size=(frames, 9)).astype(np.float32)
    arrays = {
        "image_rgb": np.zeros((frames, 8, 8, 3), dtype=np.uint8),
        "image_distance_to_image_plane": np.full(
            (frames, 8, 8, 1), 0.8, dtype=np.float32
        ),
        "joint_positions": joint,
        "finger_opening": finger,
        "tactile": tactile,
        "goal": goal,
        "action": action,
        "fruit_position": np.zeros((frames, 3), dtype=np.float32),
    }
    if trace:
        arrays["belt_speed"] = speed.astype(np.float32)
    np.savez_compressed(os.path.join(root, "episode_00000.npz"), **arrays)
    with open(os.path.join(root, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(
            [
                {
                    "file": "episode_00000.npz",
                    "success": True,
                    "category": "apple",
                    "arm": "left",
                    "grade": "A",
                    "bin_index": 0,
                    "frames": frames,
                }
            ],
            fh,
        )
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({"supply": {"belt_speed": 0.12}}, fh)


def test_store():
    print("[3] the store: per-frame column, 10-D goal")
    tmp = tempfile.mkdtemp(prefix="p141_store_")
    try:
        _write_store(tmp)
        store = EpisodeStore(
            tmp, obs_horizon=2, action_horizon=4, image_size=8,
            belt_speed=0.12, speed_channel=True, goal_aux=True,
        )
        check(store.proprio_dim == 26, "proprio is 26-D with the channel on")
        check(store.goal_dim == 10, "goal is 10-D with the pair on")
        trace = store.speed_traces[0]
        check(trace is not None and trace.size == 40, "the trace is loaded")
        frame = 7
        proprio = store.proprio(0, frame)
        check(
            abs(float(proprio[-1]) - float(trace[frame])) < 1e-6,
            f"the 26th proprio column is the trace at t={frame} "
            f"({float(proprio[-1]):.4f})",
        )
        check(
            float(np.ptp(store.proprio(0)[:, -1])) > 1e-3,
            "the column **varies within the episode** (a pin would be constant)",
        )
        item = store[frame - 1]
        check(item["goal"].shape == (10,), "an item's goal is 10-D")
        check(
            abs(float(item["goal"][-2]) - float(trace[frame])) < 1e-6,
            "goal[-2] is v_belt at the frame",
        )
        check(
            abs(float(item["goal"][-1]) - float(store.belt_accels[0][frame])) < 1e-6,
            "goal[-1] is a_belt at the frame",
        )
        norm = store.compute_normalizer()
        check(
            list(norm.goal_mean[-2:]) == list(GOAL_AUX_MEAN)
            and list(norm.goal_std[-2:]) == list(GOAL_AUX_STD),
            "the pair's normaliser is the fixed pair, not a store statistic",
        )
        # The pair off: the store is 8-D even though its frames carry a trace.
        plain = EpisodeStore(
            tmp, obs_horizon=2, action_horizon=4, image_size=8,
            belt_speed=0.12, speed_channel=True, goal_aux=False,
        )
        check(plain.goal_dim == 8, "an 8-D store with the pair off")
        # A pre-P141 store: the same episode with no `belt_speed` array.
        tmp2 = tempfile.mkdtemp(prefix="p141_pin_")
        try:
            _write_store(tmp2, trace=False)
            pinned = EpisodeStore(
                tmp2, obs_horizon=2, action_horizon=4, image_size=8,
                belt_speed=0.12, speed_channel=True, goal_aux=True,
            )
            check(pinned.speed_traces[0] is None, "a store without the trace loads")
            check(
                float(np.ptp(pinned.proprio(0)[:, -1])) < 1e-9,
                "without the trace the column is still the constant pin",
            )
            item = pinned[5]
            check(
                abs(float(item["goal"][-2]) - 0.12) < 1e-6
                and abs(float(item["goal"][-1])) < 1e-9,
                "and the goal pair degrades to (pin, 0) - a steady belt",
            )
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)
        bare = EpisodeStore(
            tmp, obs_horizon=2, action_horizon=4, image_size=8,
            speed_channel=False, goal_aux=False,
        )
        check(bare.proprio_dim == 25, "the channel off is the shipped 25-D")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 4. the warm starts
# --------------------------------------------------------------------------- #
def test_wideners():
    print("[4] the warm starts preserve the function at step 0")
    import torch

    from fruit_sorting.policy.finetune import widen_goal, widen_horizon
    from fruit_sorting.policy.model import VisualEncoder

    state = {"condition.goal.0.weight": torch.randn(128, 8)}
    norm = {"goal_mean": [0.0] * 8, "goal_std": [1.0] * 8}
    config = {"goal_dim": 8}
    check(widen_goal(state, norm, config), "the goal widens 8 -> 10")
    weight = state["condition.goal.0.weight"]
    check(tuple(weight.shape) == (128, 10), "the layer is (128, 10)")
    check(
        float(weight[:, 8:].abs().sum()) == 0.0,
        "the two new columns are **zero** - no influence at step 0",
    )
    check(len(norm["goal_mean"]) == 10, "goal_mean grew to 10")
    check(
        np.allclose(np.asarray(norm["goal_std"][-2:], dtype=np.float64), GOAL_AUX_STD)
        and np.allclose(np.asarray(norm["goal_mean"][-2:], dtype=np.float64),
                        GOAL_AUX_MEAN),
        "goal_std's pair is the fixed pair",
    )
    check(not widen_goal(state, norm, config), "idempotent")

    state = {"visual.net.0.weight": torch.randn(32, 10, 5, 5)}
    original = state["visual.net.0.weight"].clone()
    config = {"obs_horizon": 2, "image_channels": 5}
    check(widen_horizon(state, config, new_horizon=4), "the horizon widens 2 -> 4")
    weight = state["visual.net.0.weight"]
    check(tuple(weight.shape) == (32, 20, 5, 5), "the kernel is (32, 20, 5, 5)")
    check(
        torch.equal(weight[:, :10], weight[:, 10:])
        and torch.equal(weight[:, :10] * 2.0, original),
        "new_w == 0.5 * [old_w, old_w] (both halves equal, half the original)",
    )
    check(config["obs_horizon"] == 4, "the config records 4")
    check(not widen_horizon(state, config, new_horizon=4), "idempotent")

    # The identity the warm start claims: a static scene embeds the same.
    torch.manual_seed(0)
    two = VisualEncoder(10, 128).eval()
    four_state = {"visual.net.0.weight": two.net[0].weight.detach().clone()}
    cfg = {"obs_horizon": 2, "image_channels": 5}
    widen_horizon(four_state, cfg, new_horizon=4)
    four = VisualEncoder(20, 128).eval()
    shared = {
        key: value
        for key, value in two.state_dict().items()
        if key != "net.0.weight"
    }
    four.load_state_dict(shared, strict=False)
    four.net[0].weight.data = four_state["visual.net.0.weight"]
    rng = np.random.default_rng(1)
    f0 = rng.normal(size=(1, 5, 8, 8)).astype(np.float32)
    f1 = rng.normal(size=(1, 5, 8, 8)).astype(np.float32)
    with torch.no_grad():
        a = two(torch.from_numpy(np.concatenate([f0, f1], axis=1)))
        b = four(torch.from_numpy(np.concatenate([f0, f1, f0, f1], axis=1)))
    check(
        float((a - b).abs().max()) < 1e-5,
        f"a static 4-frame window reproduces the 2-frame embedding "
        f"(max |d| {float((a - b).abs().max()):.2e})",
    )


# --------------------------------------------------------------------------- #
# 5. a real checkpoint loads and forwards at the widened shapes
# --------------------------------------------------------------------------- #
def test_checkpoint():
    print("[5] a real checkpoint loads at the widened shapes")
    import torch

    from fruit_sorting.policy.finetune import widen_goal, widen_horizon, widen_proprio
    from fruit_sorting.policy.model import ConditionalUNet1D

    path = os.path.join(ROOT, "checkpoints/moe_v13s/policy_best.pt")
    if not os.path.exists(path):
        print("  skip: no checkpoint on this tree")
        return
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    config = dict(ckpt["config"])
    widen_proprio(ckpt["model"], ckpt["normalizer"], config)
    widen_goal(ckpt["model"], ckpt["normalizer"], config)
    widen_horizon(ckpt["model"], config, new_horizon=4)
    model = ConditionalUNet1D(
        action_dim=int(config["action_dim"]),
        image_channels=int(config["image_channels"]),
        obs_horizon=int(config["obs_horizon"]),
        goal_dim=int(config["goal_dim"]),
        proprio_dim=int(config["proprio_dim"]),
        num_skills=int(config.get("num_skills", 5)),
    )
    model.load_state_dict(ckpt["model"])
    check(True, "all three wideners' state loads into the built model")
    with torch.no_grad():
        out = model(
            torch.zeros(1, 9, 16),
            torch.zeros(1, 4, 5, 128, 128),
            torch.zeros(1, 10),
            torch.zeros(1, 26),
            torch.zeros(1, dtype=torch.long),
        )
    check(tuple(out.shape) == (1, 9, 16), "it forwards a 10-D goal / 26-D proprio / 4 frames")
    check(int(config["goal_dim"]) == 10 and int(config["proprio_dim"]) == 26,
          "the config records the new widths - the runner's guards read them")
    widths = (len(ckpt["normalizer"]["goal_mean"]),
              len(ckpt["normalizer"]["obs_mean"]))
    check(widths == (10, 26), f"the normaliser follows ({widths[0]}/{widths[1]})")


# --------------------------------------------------------------------------- #
# 6. the wiring is single-sited and gated
# --------------------------------------------------------------------------- #
def test_wiring():
    print("[6] the wiring is single-sited and gated")
    tasks = source("src", "fruit_sorting", "tasks.py")
    env = source("src", "fruit_sorting", "rl_env.py")
    check(
        'os.environ.get("FRUIT_OBS_SPEED", "0")' in tasks,
        "the recorder's gate is FRUIT_OBS_SPEED (the same string data.py owns)",
    )
    check(
        'observation["belt_speed"] = np.float32(' in tasks,
        "the recorder writes the per-frame belt_speed array",
    )
    check(
        tasks.count('observation["belt_speed"]') == 1,
        "one write site",
    )
    check(env.count("self._goal = self._goal_vector(") == 3,
          "all three goal assembly sites go through _goal_vector")
    check("want_goal = 8 + (2 if self._goal_aux else 0)" in env,
          "the runner refuses a goal-width mismatch instead of feeding garbage")
    check('os.environ.get("FRUIT_POLICY_EXEC_STEPS"' in env
          and 'os.environ.get("FRUIT_POLICY_DDIM"' in env,
          "both latency knobs resolve from the environment")
    check("self._refresh_goal_aux()" in env, "the belt dims refresh per call")


def test_env_assembly():
    """Execute the env's goal assembly and its belt filter on a stub."""
    print("[7] the env assembles the pair (executed, not just grepped)")
    import types

    from fruit_sorting import rl_env as env_mod

    class Belt:
        def __init__(self, speed):
            self.surface_speed = speed

    class Spawner:
        def __init__(self, speed, position):
            self.belt = Belt(speed)
            self._position = position

        def position(self, sample):
            return self._position

    class Stub:
        """Borrows the two methods under test, nothing else."""

        _goal_vector = env_mod.SortingRLEnv._goal_vector
        _belt_state = env_mod.SortingRLEnv._belt_state

    stub = Stub()
    stub.__dict__.update(
        _goal_aux=True,
        _belt_t=None,
        _belt_v=0.0,
        _belt_a=0.0,
        _sample=None,
        _goal=None,
        spawner=Spawner(-0.12, [0.3, 0.2, 1.25]),
        cfg=types.SimpleNamespace(belt_speed=-0.12),
        _sim_time=lambda: 0.0,
    )
    goal = env_mod.SortingRLEnv._goal_vector(
        stub, [0.3, 0.2, 1.25], [0.0, -0.12, 0.0], 0.06, 0
    )
    check(goal.shape == (10,), "the live goal is 10-D with the gate on")
    check(abs(float(goal[-2]) - 0.12) < 1e-6,
          "goal[-2] is |v_belt| from the belt's applied speed")
    check(abs(float(goal[-1])) < 1e-9, "the first frame's a_belt is 0")

    # A speed step: the filter must answer the derivative.
    stub._sim_time = lambda: 0.1
    stub.spawner.belt.surface_speed = -0.16
    _v, accel = env_mod.SortingRLEnv._belt_state(stub)
    check(accel > 0.0, f"a 0.04 m/s step in one tick reads a > 0 acceleration "
                       f"({accel:.2f} m/s^2)")
    stub._sim_time = lambda: 0.2
    stub.spawner.belt.surface_speed = -0.12
    _v, accel2 = env_mod.SortingRLEnv._belt_state(stub)
    check(accel2 < accel, "and it decays when the speed returns - a filter, not a latch")

    # With the gate off the vector is the shipped 8-D one and the belt is not read.
    off = Stub()
    off.__dict__.update(
        _goal_aux=False,
        spawner=Spawner(-0.12, [0.0, 0.0, 0.0]),
        cfg=types.SimpleNamespace(belt_speed=-0.12),
    )
    bare = env_mod.SortingRLEnv._goal_vector(off, [0, 0, 0], [0, 0, 0], 0.05, 1)
    check(bare.shape == (8,), "the gate off is the shipped 8-D goal")


def main():
    print("P141 observation-aux self-test")
    test_gate()
    test_accel()
    test_store()
    test_wideners()
    test_checkpoint()
    test_wiring()
    test_env_assembly()
    print(
        f"\n{'PASS' if CHECKS['failed'] == 0 else 'FAIL'}: "
        f"{CHECKS['passed']} checks, {CHECKS['failed']} failed"
    )
    return 0 if CHECKS["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
