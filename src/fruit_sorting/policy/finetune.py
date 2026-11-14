"""Reward-weighted fine-tuning (RWR/AWR) of the diffusion policy on rollouts.

The Oracle's P4 recipe: no critic, no PPO - the diffusion sampler supplies the
exploration, and fresh rollouts in the *direct* environment supply the reward.
This module takes a checkpoint and a rollout directory (written by
`RolloutRecorder`), and continues training with a per-window weight:

* ``weight_mode=success`` - the first iteration's weights: 1.0 on a successful
  rollout, ``failure_weight`` (default 0.05) on a failed one;
* ``weight_mode=awr`` - iteration 2: ``clip(exp(beta * (R - Vbar)), 0.05, 4)``
  over the rollout episodes, with ``Vbar`` the mean rollout reward;
* ``weight_mode=ones`` - plain behaviour cloning (an ablation, not a candidate).

The weight enters as ``sum(w * MSE) / sum(w)`` per batch. The base
demonstrations (``base_weight``, default 1.0) are mixed in to keep the policy on
the demonstration manifold; they are always available and large, so a rollout
batch cannot drown them out. The existing router terms (cross-entropy on the
skill label, load balancing in the soft-routing phase) are kept unchanged.

Two rules from the Oracle plan are enforced here:

* the model **and the normalizer** come from the checkpoint - the normalizer is
  never recomputed on the new data (that would make the fine-tune a different
  input transform than the evaluation's);
* the **last** epoch is saved, not the best validation loss on the demos - the
  demos are the old behaviour, and selecting on them selects against the new
  reward. The demo val loss is still printed for monitoring.

The saved ``policy_best.pt`` has the same structure the runtime loads (model /
normalizer / config), plus a ``provenance`` block naming the base checkpoint,
its md5, the rollout data, every weight knob and the frozen `tasks.py` md5.

P28-B (the belt-speed channel, `logs/p28/SPEED_CHANNEL_DESIGN.md` 2.2): with the
``FRUIT_OBS_SPEED=1`` gate on, the input is 26-D and a 25-D checkpoint is
**widened here**, before anything is trained - one zero column appended to
``condition.proprio.0.weight`` and the fixed ``(0.12, 0.05)`` normaliser entry
appended to the checkpoint's ``obs_mean``/``obs_std``. A zero column times any
input is exactly 0, so the widened model *is* the anchor at step 0: the channel
has exactly zero influence, and the batch-1 (deployed) forward pass and the
sampled action chunk are byte-identical to the base artifact - the B0 identity
control, measured in `logs/p28i/check_speed_channel.py`. The surgery is
idempotent: a checkpoint that is already 26-D passes through unchanged, which is
what makes ``spd_init -> spd_v1`` a plain fine-tune.
``rollout_speed``/``base_speed`` are the per-store pins for stores that predate
the collector's ``supply.belt_speed`` field; both are recorded in the provenance
block.

``vlash_offset_max > 0`` switches the sample construction to the VLASH
temporal-offset augmentation (`_OffsetWindows`, arXiv 2512.01031): the image
stays at ``t`` and both the robot state and the action chunk move to
``t + delta``, ``delta ~ U{0..vlash_offset_max}``. That is a data-side change
only - the loop, the model and the deployment path are untouched.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

import numpy as np
import torch
from torch.utils.data import ConcatDataset, DataLoader, Dataset

from ..rl_env import TASKS_MD5
from .data import (
    GOAL_AUX_MEAN,
    GOAL_AUX_STD,
    GOAL_DIM,
    PROPRIO_DIM,
    SPEED_CHANNEL_MEAN,
    SPEED_CHANNEL_STD,
    EpisodeStore,
    Normalizer,
    goal_aux_enabled,
    speed_channel_enabled,
)
from .diffusion import DiffusionSchedule
from .model import ConditionalUNet1D


def _md5(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.md5(handle.read()).hexdigest()
    except OSError:
        return ""


#: The belt-speed-channel width (P28-B): 25 shipped + one dedicated scalar.
SPEED_PROPRIO_DIM = PROPRIO_DIM + 1
#: P145d.4: the commanded-finger channel's normalisation, measured on
#: `demos_v11`'s action stream (mean 0.028643, std 0.012109, 0.0060-0.0440).
CMD_CHANNEL_MEAN = 0.028643
CMD_CHANNEL_STD = 0.012109


def widen_proprio(
    model_state: dict,
    normalizer: dict,
    config: dict,
    *,
    new_dim: int = SPEED_PROPRIO_DIM,
    mean: float = SPEED_CHANNEL_MEAN,
    std: float = SPEED_CHANNEL_STD,
) -> bool:
    """Splice the belt-speed column into a 25-D checkpoint payload, in place.

    Appends **one zero column** to the condition encoder's proprio input layer
    (``condition.proprio.0.weight``, shape ``(128, proprio_dim)``) and the fixed
    ``(SPEED_CHANNEL_MEAN, SPEED_CHANNEL_STD)`` entries to the checkpoint's
    ``obs_mean``/``obs_std``, then sets ``config["proprio_dim"]``. The bias is
    untouched: the new input contributes ``0 * x`` to every unit, so the model's
    **function** is unchanged - the channel has exactly zero influence at step 0
    (proven bit-identical for any input in `logs/p28i/check_speed_channel.py`).
    The deployed batch-1 forward pass and `PolicyRunner.act`'s chunk are
    byte-identical to the base artifact; a *batched* forward differs only by
    float32 summation order (measured <= 3e-6 on the denoiser output, 0.0 in a
    float64 reference of the same layer) because K grows 25 -> 26. That is the
    B0 identity control, and it is why the A/B can attribute a difference to
    what the fine-tune learned rather than to the interface.

    Returns True when it widened, False when the payload was already at (or past)
    ``new_dim``. Idempotent, so a widened checkpoint fine-tunes normally.
    """
    old_dim = int(config.get("proprio_dim", PROPRIO_DIM))
    if old_dim >= int(new_dim):
        return False
    key = "condition.proprio.0.weight"
    if key not in model_state:  # pragma: no cover - malformed checkpoint
        raise KeyError(f"{key} not in the checkpoint's model state")
    weight = model_state[key]
    if int(weight.shape[-1]) != old_dim:
        raise ValueError(
            f"{key} is {tuple(weight.shape)} but config proprio_dim={old_dim}"
        )
    grown = torch.zeros(
        (int(weight.shape[0]), int(new_dim)), dtype=weight.dtype, device=weight.device
    )
    grown[:, :old_dim] = weight
    model_state[key] = grown
    pad = int(new_dim) - old_dim
    normalizer["obs_mean"] = np.concatenate(
        [
            np.asarray(normalizer["obs_mean"], dtype=np.float32),
            np.full(pad, float(mean), dtype=np.float32),
        ]
    ).tolist()
    normalizer["obs_std"] = np.concatenate(
        [
            np.asarray(normalizer["obs_std"], dtype=np.float32),
            np.full(pad, float(std), dtype=np.float32),
        ]
    ).tolist()
    config["proprio_dim"] = int(new_dim)
    return True


def widen_goal(
    model_state: dict,
    normalizer: dict,
    config: dict,
    *,
    new_dim: int = GOAL_DIM + 2,
) -> bool:
    """Splice P141's ``(v_belt, a_belt)`` pair into an 8-D checkpoint payload.

    Appends **two zero columns** to ``condition.goal.0.weight`` and the fixed
    ``(GOAL_AUX_MEAN, GOAL_AUX_STD)`` pair to the checkpoint's
    ``goal_mean``/``goal_std``, then sets ``config["goal_dim"]``. The zero
    columns mean the pair has exactly zero influence at step 0 - the same B0
    identity `widen_proprio` uses - so a difference in the fine-tuned A/B is
    what the training learned, not the interface.

    The units are **fixed**, never a store statistic: on a constant belt every
    training frame has ``a = 0``, so a derived std would divide by ~1e-6.

    Returns True when it widened; idempotent like `widen_proprio`.
    """
    old_dim = int(config.get("goal_dim", GOAL_DIM))
    if old_dim >= int(new_dim):
        return False
    key = "condition.goal.0.weight"
    if key not in model_state:  # pragma: no cover - malformed checkpoint
        raise KeyError(f"{key} not in the checkpoint's model state")
    weight = model_state[key]
    if int(weight.shape[-1]) != old_dim:
        raise ValueError(
            f"{key} is {tuple(weight.shape)} but config goal_dim={old_dim}"
        )
    if int(new_dim) - old_dim != 2:  # pragma: no cover - only the 8 -> 10 rung
        raise NotImplementedError("widen_goal only knows the 8 -> 10 rung")
    grown = torch.zeros(
        (int(weight.shape[0]), int(new_dim)), dtype=weight.dtype, device=weight.device
    )
    grown[:, :old_dim] = weight
    model_state[key] = grown
    normalizer["goal_mean"] = np.concatenate(
        [
            np.asarray(normalizer["goal_mean"], dtype=np.float32),
            np.asarray(GOAL_AUX_MEAN, dtype=np.float32),
        ]
    ).tolist()
    normalizer["goal_std"] = np.concatenate(
        [
            np.asarray(normalizer["goal_std"], dtype=np.float32),
            np.asarray(GOAL_AUX_STD, dtype=np.float32),
        ]
    ).tolist()
    config["goal_dim"] = int(new_dim)
    return True


def widen_horizon(model_state: dict, config: dict, *, new_horizon: int) -> bool:
    """Lengthen the observation horizon of a trained visual encoder.

    The visual encoder folds the horizon into its input channels, so its first
    convolution is ``(32, image_channels * obs_horizon, 5, 5)``. Widening
    ``H -> 2H`` repeats the kernel across both halves and **halves** it, i.e.
    ``new_w = 0.5 * [old_w, old_w]``: on a static scene (where the last H frames
    repeat the first H) the conv output is *identical*, and under motion it is
    the temporal average of two H-frame windows - the natural warm start for a
    slower, longer window. The bias is untouched.

    Returns True when it widened; idempotent.
    """
    old_horizon = int(config.get("obs_horizon", 2))
    if old_horizon >= int(new_horizon):
        return False
    if int(new_horizon) != 2 * old_horizon:  # pragma: no cover - the 2 -> 4 rung
        raise NotImplementedError(
            f"widen_horizon only doubles (2 -> 4), got {old_horizon} -> {new_horizon}"
        )
    key = "visual.net.0.weight"
    if key not in model_state:  # pragma: no cover - malformed checkpoint
        raise KeyError(f"{key} not in the checkpoint's model state")
    weight = model_state[key]
    channels = int(config.get("image_channels", 5))
    if int(weight.shape[1]) != channels * old_horizon:
        raise ValueError(
            f"{key} is {tuple(weight.shape)} but the config says "
            f"{channels} channels x horizon {old_horizon}"
        )
    model_state[key] = torch.cat([weight, weight], dim=1) * 0.5
    config["obs_horizon"] = int(new_horizon)
    return True


def _weight_for_meta(meta: dict, *, mode: str, beta: float, vbar: float,
                     failure_weight: float, base_weight: float) -> float:
    """One episode's window weight. Entries without a reward are base demos."""
    if "reward" not in meta:
        return float(base_weight)
    if mode == "ones":
        return 1.0
    if mode == "success":
        return 1.0 if meta.get("success") else float(failure_weight)
    if mode == "awr":
        reward = float(meta.get("reward", 0.0))
        return float(np.clip(np.exp(beta * (reward - vbar)), 0.05, 4.0))
    raise ValueError(f"unknown weight_mode {mode!r}")


#: First recorded finger command this far below the open value marks the start
#: of the scripted close ramp (the demos hold 0.044 until the ramp's first step
#: is 0.040). Used by the timing-aware fine-tune to locate the close window.
CLOSE_FINGER = 0.0435


def close_start_frames(store: EpisodeStore) -> list[int | None]:
    """Per-episode frame where the recorded close command begins, or None.

    Read off the recorded action's finger channel (the commanded ramp, the P4
    recorder semantics), so it needs no simulator state and is identical for
    every run over the same data.
    """
    starts: list[int | None] = []
    for episode in store.episodes:
        action = np.asarray(episode["action"], dtype=np.float32)
        if action.ndim != 2 or action.shape[1] < 8:
            starts.append(None)
            continue
        index = np.flatnonzero(action[:, 7] < CLOSE_FINGER)
        starts.append(int(index[0]) if index.size else None)
    return starts


class _WeightedWindows(Dataset):
    """`EpisodeStore` windows plus one weight per window (from its episode)."""

    def __init__(self, store: EpisodeStore, normalizer: Normalizer, weights: list[float]):
        self.store = store
        self.normalizer = normalizer
        self.weights = weights

    def __len__(self) -> int:
        return len(self.store)

    def __getitem__(self, index: int) -> dict:
        sample = self.store[index]
        action = self.normalizer.normalize_action(sample["action"])
        return {
            "image": torch.from_numpy(sample["image"]),
            "proprio": torch.from_numpy(self.normalizer.normalize_obs(sample["proprio"])),
            "goal": torch.from_numpy(self.normalizer.normalize_goal(sample["goal"])),
            "action": torch.from_numpy(action.T.copy()),  # (action_dim, horizon)
            "skill": torch.tensor(int(sample["skill"]), dtype=torch.long),
            "weight": torch.tensor(float(self.weights[index]), dtype=torch.float32),
        }


class _OffsetWindows(Dataset):
    """VLASH temporal-offset augmentation over `_WeightedWindows`.

    arXiv 2512.01031 ("VLASH: Real-Time VLAs via Future-State-Aware
    Asynchronous Inference") fine-tunes with temporal offsets: for a window
    ``(o_t, s_t, A_t)`` draw ``delta ~ U{0..delta_max}`` and train on
    ``(o_t, s_{t+delta}, A_{t+delta})`` - the **environment observation stays at
    t**, while the robot state and the action chunk are taken ``delta`` steps
    later. At deployment the state is rolled forward under the previous chunk
    by the measured inference delay (the last action to execute is the
    estimated future state for absolute actions), so the model has seen the
    exact ``(current image, future state) -> future action`` pairing. ``delta=0``
    is the standard synchronous sample, so the augmentation is a strict
    superset of the unmodified data.

    ``delta`` is in recorded (30 Hz) frames - the store's window unit and the
    policy's action-chunk index unit - and the sample is clamped so the shifted
    action window still fits the episode.
    """

    def __init__(self, inner: _WeightedWindows, store: EpisodeStore,
                 normalizer: Normalizer, delta_max: int, seed: int = 0):
        self.inner = inner
        self.store = store
        self.normalizer = normalizer
        self.delta_max = max(0, int(delta_max))
        self.rng = np.random.default_rng(int(seed))

    def __len__(self) -> int:
        return len(self.inner)

    def __getitem__(self, index: int) -> dict:
        sample = self.inner[index]
        if self.delta_max <= 0:
            return sample
        ep_index, t = self.store.windows[index]
        episode = self.store.episodes[ep_index]
        horizon = int(self.store.action_horizon)
        length = int(episode["action"].shape[0])
        # Only windows whose shifted action chunk still fits the episode.
        limit = max(length - horizon - t, 0)
        delta = int(self.rng.integers(0, self.delta_max + 1))
        delta = min(delta, limit)
        if delta == 0:
            return sample
        s = t + delta
        # The store owns the assembly (P28-B: it appends the belt-speed scalar
        # when the channel is armed); duplicating the concatenation here would
        # silently drop the new dimension.
        proprio = self.store.proprio(ep_index, s)
        action = episode["action"][s : s + horizon].astype(np.float32)
        skills = episode["skills"]
        skill = int(skills[s]) if skills is not None else int(sample["skill"])
        sample["proprio"] = torch.from_numpy(self.normalizer.normalize_obs(proprio))
        sample["action"] = torch.from_numpy(
            self.normalizer.normalize_action(action).T.copy()
        )
        sample["skill"] = torch.tensor(skill, dtype=torch.long)
        return sample


def _window_weights(store: EpisodeStore, *, mode: str, beta: float, vbar: float,
                    failure_weight: float, base_weight: float,
                    close_weight: float = 1.0, close_lead: int = 10,
                    close_tail: int = 10) -> list[float]:
    """One weight per training window, from the window's episode metadata.

    ``close_weight`` > 1 upweights the windows *starting* within
    ``[close_start - close_lead, close_start + close_tail]`` of the episode's
    recorded close command - the timing-aware objective (P4b1). With the
    default 1.0 the weight is the episode weight only, exactly as before.
    """
    episode_weight = [
        _weight_for_meta(ep["meta"], mode=mode, beta=beta, vbar=vbar,
                         failure_weight=failure_weight, base_weight=base_weight)
        for ep in store.episodes
    ]
    starts = close_start_frames(store) if close_weight != 1.0 else []
    weights: list[float] = []
    for ep, start in store.windows:
        weight = episode_weight[ep]
        if starts:
            close = starts[ep]
            if close is not None and (close - close_lead) <= start <= (close + close_tail):
                weight *= float(close_weight)
        weights.append(weight)
    return weights


def _demo_val_loss(model, dataset, device, limit: int = 64) -> float:
    """Unweighted diffusion loss on a fixed slice of the base demos."""
    if dataset is None or len(dataset) == 0:
        return float("nan")
    indices = np.linspace(0, len(dataset) - 1, min(limit, len(dataset))).astype(int)
    schedule = DiffusionSchedule(int(model.num_diffusion_steps) if hasattr(model, "num_diffusion_steps")
                                 else 100, device=device,
                                 beta_schedule=getattr(model, "beta_schedule", "linear"))
    total, count = 0.0, 0
    model.eval()
    with torch.no_grad():
        for index in indices:
            sample = dataset[int(index)]
            action = sample["action"].to(device)[None]
            noise = torch.randn_like(action)
            timesteps = schedule.sample_timesteps(1)
            noisy = schedule.add_noise(action, noise, timesteps)
            condition = (
                sample["image"].to(device)[None],
                sample["goal"].to(device)[None],
                sample["proprio"].to(device)[None],
            )
            predicted = model.denoise(noisy, condition, timesteps)
            total += float(torch.nn.functional.mse_loss(predicted, noise).item())
            count += 1
    return total / max(count, 1)


def finetune(
    checkpoint: str,
    rollouts: str,
    base: str | None = "datasets/demos_v7",
    out_dir: str = "checkpoints/rl_iter1",
    epochs: int = 4,
    lr: float = 5e-5,
    batch_size: int = 32,
    weight_mode: str = "success",
    beta: float = 4.0,
    failure_weight: float = 0.05,
    base_weight: float = 1.0,
    device: str | None = None,
    seed: int = 0,
    hard_epochs: int = 0,
    router_loss_weight: float = 0.1,
    balance_loss_weight: float = 0.01,
    close_weight: float = 1.0,
    close_lead: int = 10,
    close_tail: int = 10,
    first_steps: int = 0,
    action_horizon: int | None = None,
    vlash_offset_max: int = 0,
    rollout_speed: float | None = None,
    base_speed: float | None = None,
    goal_aux: bool | None = None,
    cmd_channel: bool | None = None,
    obs_horizon: int | None = None,
    verbose: bool = True,
) -> str:
    """Continue-train `checkpoint` on `rollouts` (+ `base` demos). Returns the path.

    ``vlash_offset_max > 0`` enables the VLASH temporal-offset augmentation
    (`_OffsetWindows`): observation at t, state and action chunk at t+delta,
    ``delta ~ U{0..vlash_offset_max}``. With an empty ``rollouts`` the fine-tune
    runs on the base demonstrations alone, which is the VLASH configuration.

    P28-B: the belt-speed channel is armed by ``FRUIT_OBS_SPEED=1`` (or by a
    checkpoint that is already 26-D). ``rollout_speed``/``base_speed`` declare
    the per-store pin for stores without a ``supply.belt_speed`` manifest; a
    declaration that contradicts a manifest raises in `EpisodeStore`.
    """
    if weight_mode not in ("ones", "success", "awr"):
        raise ValueError(f"weight_mode must be ones|success|awr, got {weight_mode!r}")
    if close_weight < 1.0:
        raise ValueError(f"close_weight must be >= 1.0, got {close_weight!r}")
    torch.manual_seed(seed)
    np.random.seed(seed)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(out_dir, exist_ok=True)

    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)
    config = dict(ckpt["config"])
    # P145d.8: the action representation is part of the artifact. A store built
    # under `FRUIT_ACTION=dq` carries deltas; a checkpoint trained on them must
    # be loaded by an env in the same mode (the env refuses a mismatch).
    from .data import action_mode_from_env as _mode_from_env

    config["action_mode"] = _mode_from_env()
    # P28-B: the channel is on when the gate is, or when the checkpoint already
    # carries it (a 26-D artifact must be trained on 26-D windows - a mismatch
    # is a loud shape error, not a silent one).
    speed_channel = bool(
        int(config.get("proprio_dim", PROPRIO_DIM)) > PROPRIO_DIM
        or speed_channel_enabled()
    )
    if not speed_channel and (rollout_speed is not None or base_speed is not None):
        # A declared pin with the channel off would be silently dropped - the
        # exact class of failure the pin chain exists to remove (Gate A B2).
        raise ValueError(
            "a belt-speed pin was declared (--store-speed/--base-speed) but the "
            "speed channel is off: set FRUIT_OBS_SPEED=1, or drop the pin"
        )
    if speed_channel:
        widened = widen_proprio(ckpt["model"], ckpt["normalizer"], config)
        if verbose and widened:
            print(
                f"[finetune] P28-B speed channel: widened the checkpoint's "
                f"proprio {PROPRIO_DIM} -> {int(config['proprio_dim'])} "
                f"(zero column, normaliser entry "
                f"({SPEED_CHANNEL_MEAN}, {SPEED_CHANNEL_STD}))",
                flush=True,
            )
    # P145d.4: the commanded-finger column (the measured finger aliases the
    # loaded close). Spliced after the speed column; the store and the
    # checkpoint must agree on the width.
    _cmd = (
        bool(cmd_channel)
        if cmd_channel is not None
        else os.environ.get("FRUIT_OBS_CMD", "0") == "1"
    )
    if _cmd:
        _target = PROPRIO_DIM + (1 if speed_channel else 0) + 1
        if int(config.get("proprio_dim", PROPRIO_DIM)) < _target:
            widen_proprio(
                ckpt["model"], ckpt["normalizer"], config,
                new_dim=_target, mean=CMD_CHANNEL_MEAN, std=CMD_CHANNEL_STD,
            )
            if verbose:
                print(
                    f"[finetune] P145d.4 command-finger channel: proprio "
                    f"-> {int(config['proprio_dim'])} (zero column, "
                    f"normaliser ({CMD_CHANNEL_MEAN}, {CMD_CHANNEL_STD}))",
                    flush=True,
                )
    cmd_channel = _cmd
    # P141: the goal's belt pair. Armed by the gate or by the artifact (a 10-D
    # checkpoint must be trained on 10-D goals, exactly like proprio).
    if goal_aux is None:
        goal_aux = bool(
            int(config.get("goal_dim", GOAL_DIM)) > GOAL_DIM or goal_aux_enabled()
        )
    if goal_aux:
        widened_goal = widen_goal(ckpt["model"], ckpt["normalizer"], config)
        if verbose and widened_goal:
            print(
                f"[finetune] P141 goal: widened {GOAL_DIM} -> "
                f"{int(config['goal_dim'])} with (v_belt, a_belt), zero columns, "
                f"normaliser {GOAL_AUX_MEAN} / {GOAL_AUX_STD}",
                flush=True,
            )
    normalizer = Normalizer(
        action_mean=np.asarray(ckpt["normalizer"]["action_mean"], dtype=np.float32),
        action_std=np.asarray(ckpt["normalizer"]["action_std"], dtype=np.float32),
        obs_mean=np.asarray(ckpt["normalizer"]["obs_mean"], dtype=np.float32),
        obs_std=np.asarray(ckpt["normalizer"]["obs_std"], dtype=np.float32),
        goal_mean=np.asarray(ckpt["normalizer"]["goal_mean"], dtype=np.float32),
        goal_std=np.asarray(ckpt["normalizer"]["goal_std"], dtype=np.float32),
    )
    # P141: the horizon is a *window* property, not a weights property, so it is
    # an explicit widening rung (2 -> 4) with a warm start rather than a new
    # architecture. Unset keeps the checkpoint's own value.
    if obs_horizon is not None and int(obs_horizon) != int(config["obs_horizon"]):
        if widen_horizon(ckpt["model"], config, new_horizon=int(obs_horizon)):
            if verbose:
                print(
                    f"[finetune] P141 horizon: visual encoder "
                    f"{int(config['obs_horizon']) // 2} -> {int(config['obs_horizon'])} "
                    "frames (kernel repeated, halved)",
                    flush=True,
                )
    obs_horizon = int(config["obs_horizon"])
    # P145: the denoiser is fully convolutional over the action axis, so the
    # **action horizon** is a window property like `obs_horizon` - no weights
    # change. A feedback-shaped policy (execute one chunk of `h` steps and
    # re-plan) is therefore a fine-tune flag, not a new architecture.
    if action_horizon is not None and int(action_horizon) != int(
        config["action_horizon"]
    ):
        if verbose:
            print(
                f"[finetune] P145 action horizon: "
                f"{int(config['action_horizon'])} -> {int(action_horizon)} steps",
                flush=True,
            )
        config["action_horizon"] = int(action_horizon)
    action_horizon = int(config["action_horizon"])
    image_size = int(config["image_size"])

    # -------------------------------------------------------------- data --- #
    rollout_store = None
    if rollouts:
        rollout_store = EpisodeStore(
            rollouts, obs_horizon=obs_horizon, action_horizon=action_horizon,
            image_size=image_size, only_successful=False,
            belt_speed=rollout_speed, speed_channel=speed_channel,
            cmd_channel=cmd_channel,
            goal_aux=goal_aux,
        )
    base_store = None
    if base and os.path.exists(os.path.join(base, "index.json")):
        base_store = EpisodeStore(
            base, obs_horizon=obs_horizon, action_horizon=action_horizon,
            image_size=image_size, only_successful=True,
            belt_speed=base_speed, speed_channel=speed_channel,
            cmd_channel=cmd_channel,
            goal_aux=goal_aux,
        )
    # The training input and the deployed input must be the same width; this is
    # the only place both sides are known.
    want_dim = int(config["proprio_dim"])
    for store, label in ((rollout_store, "rollouts"), (base_store, "base")):
        if store is not None and int(store.proprio_dim) != want_dim:
            raise ValueError(
                f"{label} store proprio_dim={store.proprio_dim} but the "
                f"checkpoint expects {want_dim}: arm the channel on both sides "
                f"(--store-speed/FRUIT_OBS_SPEED) or on neither"
            )
        if store is not None and int(store.goal_dim) != int(config["goal_dim"]):
            raise ValueError(
                f"{label} store goal_dim={store.goal_dim} but the checkpoint "
                f"expects {int(config['goal_dim'])}: arm the goal pair on both "
                f"sides (FRUIT_OBS_GOAL_AUX=1) or on neither"
            )

    rewards = (
        [float(ep["meta"].get("reward", 0.0)) for ep in rollout_store.episodes]
        if rollout_store is not None else []
    )
    vbar = float(np.mean(rewards)) if rewards else 0.0
    datasets: list[Dataset] = []
    weight_stats: dict[str, float] = {}
    for store, label in ((rollout_store, "rollout"), (base_store, "base")):
        if store is None:
            continue
        weights = _window_weights(
            store, mode=weight_mode, beta=beta, vbar=vbar,
            failure_weight=failure_weight, base_weight=base_weight,
            close_weight=close_weight, close_lead=close_lead,
            close_tail=close_tail,
        )
        stats = np.asarray(sorted(set(round(w, 6) for w in weights)))
        weight_stats[label] = {
            "episodes": len(store.episodes),
            "windows": len(store),
            "weight_values": stats[:8].tolist(),
            "mean_weight": float(np.mean(weights)) if weights else 0.0,
        }
        if close_weight != 1.0:
            starts = close_start_frames(store)
            boosted = sum(
                1
                for (ep, start) in store.windows
                if starts[ep] is not None
                and (starts[ep] - close_lead) <= start <= (starts[ep] + close_tail)
            )
            weight_stats[label]["close_windows"] = int(boosted)
            weight_stats[label]["close_episodes"] = int(
                sum(1 for value in starts if value is not None)
            )
        dataset: Dataset = _WeightedWindows(store, normalizer, weights)
        if vlash_offset_max > 0:
            dataset = _OffsetWindows(
                dataset, store, normalizer, vlash_offset_max,
                seed=seed + (0 if label == "rollout" else 1),
            )
            weight_stats[label]["vlash_offset_max"] = int(vlash_offset_max)
        datasets.append(dataset)
    if not datasets:
        raise RuntimeError(f"no usable windows in {rollouts} (or base {base})")
    dataset = datasets[0] if len(datasets) == 1 else ConcatDataset(datasets)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=False)

    if verbose:
        if rollout_store is not None:
            print(f"[finetune] rollouts={rollouts} ({len(rollout_store.episodes)} "
                  f"episodes, success "
                  f"{sum(1 for e in rollout_store.episodes if e['meta'].get('success'))})")
        else:
            print("[finetune] rollouts=(none)")
        if base_store is not None:
            print(f"[finetune] base={base} ({len(base_store.episodes)} episodes)")
        print(f"[finetune] windows={len(dataset)} weight_mode={weight_mode} "
              f"vbar={vbar:.4f} beta={beta} failure_weight={failure_weight} "
              f"base_weight={base_weight} vlash_offset_max={vlash_offset_max}")
        if speed_channel:
            print(f"[finetune] speed channel: proprio_dim={want_dim} "
                  f"normaliser=({SPEED_CHANNEL_MEAN}, {SPEED_CHANNEL_STD})")
            for store, label in ((rollout_store, "rollouts"), (base_store, "base")):
                if store is not None:
                    print(f"[finetune]   {label} pins: {store.speed_pin_summary()}")
        for label, stats in weight_stats.items():
            print(f"[finetune]   {label}: {stats}")

    # ------------------------------------------------------------- model --- #
    model = ConditionalUNet1D(
        action_dim=int(config["action_dim"]),
        image_channels=int(config["image_channels"]),
        obs_horizon=obs_horizon,
        goal_dim=int(config["goal_dim"]),
        proprio_dim=int(config["proprio_dim"]),
        num_skills=int(config.get("num_skills", 5)),
    ).to(device)
    model.load_state_dict(ckpt["model"])
    model.num_diffusion_steps = int(config["num_diffusion_steps"])
    model.beta_schedule = str(config.get("beta_schedule", "linear"))
    schedule = DiffusionSchedule(int(config["num_diffusion_steps"]), device=device,
                                 beta_schedule=model.beta_schedule)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-6)

    history = []
    last_loss = float("nan")
    for epoch in range(int(epochs)):
        model.train()
        running, weighted_running, router_running, correct, seen = 0.0, 0.0, 0.0, 0.0, 0
        start = time.time()
        hard = epoch < int(hard_epochs)
        for batch in loader:
            action = batch["action"].to(device)
            skill = batch["skill"].to(device)
            weight = batch["weight"].to(device)
            noise = torch.randn_like(action)
            timesteps = schedule.sample_timesteps(action.shape[0])
            noisy = schedule.add_noise(action, noise, timesteps)
            condition = (
                batch["image"].to(device),
                batch["goal"].to(device),
                batch["proprio"].to(device),
            )
            predicted = model.denoise(
                noisy, condition, timesteps, skill_labels=skill if hard else None
            )
            raw = torch.nn.functional.mse_loss(
                predicted, noise, reduction="none"
            )
            if first_steps > 0 and raw.shape[1] > first_steps:
                # P145: the env executes only the first `execute_steps` actions of
                # a chunk before it re-plans, and a DAgger label is a *feedback*
                # command for the state it was recorded at - the later steps of
                # the chunk are conditioned on states the policy may never visit.
                # Train the part that is executed.
                # The denoiser works in (batch, action_dim, horizon) - a Conv1d
                # over the horizon - so the *executed steps* are the last axis.
                mask = torch.zeros_like(raw)
                mask[:, :, : int(first_steps)] = 1.0
                per_window = (raw * mask).flatten(1).sum(1) / mask.flatten(1).sum(
                    1
                ).clamp_min(1.0)
            else:
                per_window = raw.flatten(1).mean(1)
            loss = (weight * per_window).sum() / weight.sum().clamp_min(1e-8)
            logits = model.last_router_logits
            router_loss = torch.nn.functional.cross_entropy(logits, skill)
            balance = model.load_balancing_loss(model.last_router_weights)
            total = loss + router_loss_weight * router_loss
            if not hard:
                total = total + balance_loss_weight * balance
            optimizer.zero_grad(set_to_none=True)
            total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            count = action.shape[0]
            running += float(per_window.mean().item()) * count
            weighted_running += float(loss.item()) * count
            router_running += float(router_loss.item()) * count
            with torch.no_grad():
                correct += float((logits.argmax(dim=-1) == skill).float().sum().item())
            seen += count
        last_loss = weighted_running / max(seen, 1)
        val = _demo_val_loss(model, datasets[-1] if base_store is not None else None,
                             device)
        history.append({
            "epoch": epoch,
            "routing": "hard" if hard else "soft",
            "mse": running / max(seen, 1),
            "weighted_loss": last_loss,
            "router_ce": router_running / max(seen, 1),
            "router_acc": correct / max(seen, 1),
            "demo_val": val,
        })
        print(
            f"[finetune] epoch {epoch + 1}/{epochs} {'HARD' if hard else 'SOFT'} "
            f"mse={running / max(seen, 1):.4f} weighted={last_loss:.4f} "
            f"router_ce={router_running / max(seen, 1):.3f} "
            f"router_acc={correct / max(seen, 1):.3f} demo_val={val:.4f} "
            f"({time.time() - start:.1f}s)",
            flush=True,
        )

    # Last epoch, deliberately not the best demo val (see module docstring).
    provenance = {
        "kind": "rl_finetune",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base_checkpoint": os.path.abspath(checkpoint),
        "base_checkpoint_md5": _md5(checkpoint),
        "rollouts": os.path.abspath(rollouts) if rollouts else "",
        "rollout_episodes": len(rollout_store.episodes) if rollout_store is not None else 0,
        "rollout_windows": len(rollout_store) if rollout_store is not None else 0,
        "rollout_successes": int(
            sum(1 for e in rollout_store.episodes if e["meta"].get("success"))
        ) if rollout_store is not None else 0,
        "base": os.path.abspath(base) if base else "",
        "base_episodes": len(base_store.episodes) if base_store is not None else 0,
        "base_windows": len(base_store) if base_store is not None else 0,
        "weight_mode": weight_mode,
        "beta": beta,
        "vbar": vbar,
        "failure_weight": failure_weight,
        "base_weight": base_weight,
        "close_weight": float(close_weight),
        "close_lead": int(close_lead),
        "close_tail": int(close_tail),
        "vlash_offset_max": int(vlash_offset_max),
        # P28-B: the belt-speed channel's provenance. `declared` is what the
        # caller pinned (design 4.3's table, for stores that predate the
        # collector's `supply.belt_speed` field); `pins` is what the loader
        # actually resolved, per store, including which manifests it trusted.
        "speed_channel": {
            "enabled": bool(speed_channel),
            "proprio_dim": int(config.get("proprio_dim", PROPRIO_DIM)),
            "gate": os.environ.get("FRUIT_OBS_SPEED", ""),
            "normaliser": (
                [SPEED_CHANNEL_MEAN, SPEED_CHANNEL_STD] if speed_channel else None
            ),
            "rollout_declared": rollout_speed,
            "base_declared": base_speed,
            "pins": {
                label: store.speed_pin_summary()
                for store, label in ((rollout_store, "rollouts"), (base_store, "base"))
                if store is not None
            },
        },
        "weight_stats": weight_stats,
        "epochs": int(epochs),
        "lr": lr,
        "batch_size": int(batch_size),
        "hard_epochs": int(hard_epochs),
        "router_loss_weight": router_loss_weight,
        "balance_loss_weight": balance_loss_weight,
        "seed": int(seed),
        "device": str(device),
        "final_weighted_loss": last_loss,
        "tasks_md5": TASKS_MD5,
        "history": history,
    }
    payload = {
        "model": model.state_dict(),
        "normalizer": ckpt["normalizer"],
        "config": config,
        "val_loss": ckpt.get("val_loss", float("nan")),
        "provenance": provenance,
    }
    out_path = os.path.join(out_dir, "policy_best.pt")
    torch.save(payload, out_path)
    with open(os.path.join(out_dir, "finetune_history.json"), "w", encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=2)
    print(f"[finetune] saved {out_path} (last epoch, weighted loss {last_loss:.4f})",
          flush=True)
    return out_path
