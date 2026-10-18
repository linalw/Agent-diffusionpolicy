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

``vlash_offset_max > 0`` switches the sample construction to the VLASH
temporal-offset augmentation (`_OffsetWindows`, arXiv 2512.01031): the image
stays at ``t`` and both the robot state and the action chunk move to
``t + delta``, ``delta ~ U{0..vlash_offset_max}``. That is a data-side change
only - the loop, the model and the deployment path are untouched.

P13-A adds the **event-structure supervision** lane (mechanism-menu item #6;
ForeTime-VLA #50 + DAM-VLA #42), default off:

* ``FRUIT_POLICY_EVENT_HEADS=1`` attaches the two auxiliary heads
  (`model.EventHeads`) - 4-class phase + normalized time-to-transition, on an
  8-step causal proprio history - and trains them with ForeTime's auxiliary
  weights (0.20 phase CE / 0.02 TtT MSE) through the **shared** conditioning
  encoder. The heads are read-only: the action output and the shipped
  inference path are unchanged, the heads' parameters are saved under
  ``payload["event_heads"]`` and the ``model`` entry stays strict-loadable by
  the shipped ``PolicyRunner``.
* ``FRUIT_POLICY_EVENT_TRANSITION_WEIGHT`` (float, 0 = off) enables DAM-VLA's
  transition-weighted loss: each window's weight is multiplied by
  ``1 + alpha * g(d)`` with ``g`` the asymmetric Gaussian (sigma 6 leading /
  2 trailing, frames) on the signed distance ``d`` to the nearest transition,
  and the per-chunk MSE gets the ``gamma^j`` position decay (gamma 0.8).

Labels are free: the close transition comes from the recorded finger channel
(the existing `CLOSE_FINGER` rule) and the carry/place boundaries from the
skill labels (`episode_event_labels`). With both knobs off, every path -
dataset, weights, loss, saved payload keys - is exactly the pre-P13-A one.
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
from .data import EpisodeStore, Normalizer
from .diffusion import DiffusionSchedule
from .model import ConditionalUNet1D


def _md5(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.md5(handle.read()).hexdigest()
    except OSError:
        return ""


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


# --------------------------------------------------------------------------- #
# P13-A: event-structure supervision (mechanism-menu #6; ForeTime #50 + DAM-VLA
# #42). All default off; the knobs are read by `event_settings_from_env`.
# --------------------------------------------------------------------------- #

#: Phase classes: 0 approach, 1 close/grasp transition, 2 carry, 3 place.
EVENT_PHASES = 4
#: Causal proprio-history length (ForeTime's 8-step student history).
EVENT_HISTORY = 8
#: TtT normalization horizon in frames (4.0 s at 30 Hz). Measured over the
#: 208-episode store (demos_v11+v12): distance-to-next-transition p50 28,
#: p90 66, p99 95, max 111 - so 120 is the smallest round horizon with no
#: clipping except after the final transition (label 1.0 by construction).
EVENT_TTT_HORIZON = 120
#: DAM-VLA's asymmetric Gaussian on the signed distance to the nearest
#: transition: sigma_l = 6 frames on the leading side (before), sigma_r = 2 on
#: the trailing side (after) (`logs/p6/B3a_reread.md` section 3).
EVENT_SIGMA_LEAD = 6.0
EVENT_SIGMA_TRAIL = 2.0
#: DAM-VLA's chunk decay: weight ``gamma**j`` on action-chunk position j.
EVENT_CHUNK_GAMMA = 0.8


def event_settings_from_env() -> dict:
    """The P13-A knobs, both default off.

    ``FRUIT_POLICY_EVENT_HEADS`` 0|1 - attach + train the phase/TtT heads.
    ``FRUIT_POLICY_EVENT_TRANSITION_WEIGHT`` float - the transition-weighted
    loss' boost alpha (0 = off). Unset: the shipped training path, byte for
    byte.
    """
    return {
        "event_heads": os.environ.get("FRUIT_POLICY_EVENT_HEADS", "0").strip() == "1",
        "transition_weight": float(
            os.environ.get("FRUIT_POLICY_EVENT_TRANSITION_WEIGHT", "0.0")
        ),
    }


def episode_event_labels(episode: dict, *,
                         ttt_horizon: int = EVENT_TTT_HORIZON,
                         close_finger: float = CLOSE_FINGER) -> dict:
    """Phase + normalized-TtT labels for one episode, from free signals only.

    * the **close transition** is the first frame whose recorded finger command
      drops below `close_finger` (the same rule `close_start_frames` uses);
    * the **carry** and **place** boundaries are the first frames of the
      ``lift`` (skill 2) and ``place`` (skill 3) legs of the free skill labels
      (`EpisodeStore` derives them from fruit position + finger + goal).

    Phase: 0 before the close, 1 in the close/grasp window, 2 while carried,
    3 from the place boundary on. A missing boundary simply leaves its phase
    without frames (3 of 208 store episodes have no ``grasp`` leg frame and so
    no carry split - the close window extends to the place). TtT is
    ``min((next_transition - t) / ttt_horizon, 1)``, 1.0 after the last
    transition.
    """
    finger = np.asarray(episode["finger"], dtype=np.float64).reshape(-1)
    length = int(finger.shape[0])
    close: int | None = None
    below = np.flatnonzero(finger < close_finger)
    if below.size:
        close = int(below[0])
    carry: int | None = None
    place: int | None = None
    skills = episode.get("skills")
    if skills is not None:
        skills = np.asarray(skills)
        lift = np.flatnonzero(skills == 2)
        carry = int(lift[0]) if lift.size else None
        over = np.flatnonzero(skills == 3)
        place = int(over[0]) if over.size else None

    phase = np.zeros(length, dtype=np.int64)
    if close is not None:
        phase[close:] = 1
    if carry is not None:
        phase[carry:] = 2
    if place is not None:
        phase[place:] = 3

    transitions = sorted({v for v in (close, carry, place) if v is not None})
    ttt = np.ones(length, dtype=np.float32)
    for t in range(length):
        upcoming = [tau for tau in transitions if tau > t]
        if upcoming:
            ttt[t] = min((min(upcoming) - t) / ttt_horizon, 1.0)
    return {
        "close": close,
        "carry": carry,
        "place": place,
        "transitions": transitions,
        "phase": phase,
        "ttt": ttt,
    }


def episode_event_data(episode: dict, normalizer: Normalizer, *,
                       history: int = EVENT_HISTORY,
                       ttt_horizon: int = EVENT_TTT_HORIZON) -> dict:
    """Per-frame labels + normalized causal proprio histories for one episode.

    ``history[t]`` is ``[proprio[t-history+1], ..., proprio[t]]`` (oldest
    first, edge-padded with frame 0) in the same layout and normalization the
    model's proprio input uses (joint + finger + tactile through `normalizer`).
    """
    raw = np.concatenate(
        [
            np.asarray(episode["joint"], dtype=np.float32),
            np.asarray(episode["finger"], dtype=np.float32),
            np.asarray(episode["tactile"], dtype=np.float32),
        ],
        axis=-1,
    )
    normalized = ((raw - normalizer.obs_mean) / normalizer.obs_std).astype(np.float32)
    length = normalized.shape[0]
    padded = np.concatenate(
        [np.repeat(normalized[:1], history - 1, axis=0), normalized], axis=0
    )
    histories = np.stack(
        [padded[t : t + history] for t in range(length)], axis=0
    ).astype(np.float32)
    labels = episode_event_labels(episode, ttt_horizon=ttt_horizon)
    labels["history"] = histories
    return labels


def transition_gauss(frame: int, transitions, *,
                     sigma_lead: float = EVENT_SIGMA_LEAD,
                     sigma_trail: float = EVENT_SIGMA_TRAIL) -> float:
    """DAM-VLA's asymmetric Gaussian on the distance to the nearest transition.

    ``d = frame - tau*`` with ``tau*`` the nearest transition; sigma is
    ``sigma_lead`` for ``d < 0`` (before the transition) and ``sigma_trail``
    after it. Peak 1.0 at the transition, 0.0 when there is no transition.
    """
    if not transitions:
        return 0.0
    tau = min(transitions, key=lambda value: abs(frame - value))
    distance = frame - tau
    sigma = sigma_lead if distance < 0 else sigma_trail
    return float(np.exp(-0.5 * (distance / sigma) ** 2))


def window_loss_terms(predicted: torch.Tensor, noise: torch.Tensor,
                      weight: torch.Tensor,
                      chunk_gamma: float | None = None):
    """Per-window MSE + the weighted mean loss (P13-A adds the optional gamma^j).

    ``chunk_gamma=None`` is the shipped arithmetic - ``mse.flatten(1).mean(1)``
    over the whole chunk, then ``sum(w * mse) / sum(w)`` - bit for bit. With a
    gamma the per-position MSE is averaged with ``gamma**j`` weights over the
    chunk positions (DAM-VLA's chunk decay).
    """
    per_position = torch.nn.functional.mse_loss(predicted, noise, reduction="none")
    if chunk_gamma is not None and chunk_gamma != 1.0:
        positions = torch.arange(
            per_position.shape[-1], device=per_position.device, dtype=per_position.dtype
        )
        position_weights = chunk_gamma ** positions
        per_window = (per_position * position_weights[None, None, :]).sum(
            dim=(1, 2)
        ) / (position_weights.sum() * per_position.shape[1])
    else:
        per_window = per_position.flatten(1).mean(1)
    loss = (weight * per_window).sum() / weight.sum().clamp_min(1e-8)
    return loss, per_window


def event_state_split(state: dict) -> tuple[dict, dict]:
    """Split a model ``state_dict`` into (shipped base keys, event-head state).

    The trained checkpoint must load strictly into the shipped `PolicyRunner`
    (`runtime.PolicyRunner.__init__` constructs the base model), so the
    ``model`` entry holds the base keys only and the heads travel under
    ``payload["event_heads"]``. The event half is the `EventHeads` module's own
    state dict (the ``event.`` prefix stripped), so it re-attaches directly
    with ``model.event.load_state_dict(event_state)``.
    """
    base = {k: v for k, v in state.items() if not k.startswith("event.")}
    event = {
        k[len("event."):]: v for k, v in state.items() if k.startswith("event.")
    }
    return base, event


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

    ``event_labels`` (P13-A, optional): when the P13-A event fields are present
    the shifted history/phase/TtT labels move with the offset too, so the
    auxiliary supervision stays consistent with the shifted state. ``None``
    (the default) leaves the shipped behaviour untouched.
    """

    def __init__(self, inner: Dataset, store: EpisodeStore,
                 normalizer: Normalizer, delta_max: int, seed: int = 0,
                 event_labels: list[dict] | None = None):
        self.inner = inner
        self.store = store
        self.normalizer = normalizer
        self.delta_max = max(0, int(delta_max))
        self.rng = np.random.default_rng(int(seed))
        self.event_labels = event_labels

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
        proprio = np.concatenate(
            [
                episode["joint"][s].astype(np.float32),
                episode["finger"][s].astype(np.float32),
                episode["tactile"][s].astype(np.float32),
            ]
        )
        action = episode["action"][s : s + horizon].astype(np.float32)
        skills = episode["skills"]
        skill = int(skills[s]) if skills is not None else int(sample["skill"])
        sample["proprio"] = torch.from_numpy(self.normalizer.normalize_obs(proprio))
        sample["action"] = torch.from_numpy(
            self.normalizer.normalize_action(action).T.copy()
        )
        sample["skill"] = torch.tensor(skill, dtype=torch.long)
        if self.event_labels is not None:
            labels = self.event_labels[ep_index]
            sample["history"] = torch.from_numpy(labels["history"][s])
            sample["phase"] = torch.tensor(int(labels["phase"][s]), dtype=torch.long)
            sample["ttt"] = torch.tensor(float(labels["ttt"][s]), dtype=torch.float32)
        return sample


class _EventWindows(Dataset):
    """Adds the P13-A event fields to a window: 8-step history + phase + TtT.

    Labels are precomputed per episode by `episode_event_data` (normalized
    history, phase index, normalized TtT). This wrapper only attaches them at
    the window's frame; the training loop consumes ``history``/``phase``/``ttt``
    when ``event_heads`` is on.
    """

    def __init__(self, inner: Dataset, store: EpisodeStore, labels: list[dict]):
        self.inner = inner
        self.store = store
        self.labels = labels

    def __len__(self) -> int:
        return len(self.inner)

    def __getitem__(self, index: int) -> dict:
        sample = self.inner[index]
        ep_index, t = self.store.windows[index]
        labels = self.labels[ep_index]
        sample["history"] = torch.from_numpy(labels["history"][t])
        sample["phase"] = torch.tensor(int(labels["phase"][t]), dtype=torch.long)
        sample["ttt"] = torch.tensor(float(labels["ttt"][t]), dtype=torch.float32)
        return sample


def _window_weights(store: EpisodeStore, *, mode: str, beta: float, vbar: float,
                    failure_weight: float, base_weight: float,
                    close_weight: float = 1.0, close_lead: int = 10,
                    close_tail: int = 10,
                    transitions: list[list[int]] | None = None,
                    transition_weight: float = 0.0,
                    sigma_lead: float = EVENT_SIGMA_LEAD,
                    sigma_trail: float = EVENT_SIGMA_TRAIL) -> list[float]:
    """One weight per training window, from the window's episode metadata.

    ``close_weight`` > 1 upweights the windows *starting* within
    ``[close_start - close_lead, close_start + close_tail]`` of the episode's
    recorded close command - the timing-aware objective (P4b1). With the
    default 1.0 the weight is the episode weight only, exactly as before.

    ``transition_weight`` (P13-A, default 0 = off) multiplies each window's
    weight by ``1 + alpha * transition_gauss(t, transitions[ep])`` - DAM-VLA's
    near-transition up-weighting. The weighted mean divides by ``sum(w)``, so
    a global rescale is a no-op and no normalization step is needed.
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
        if transition_weight > 0 and transitions is not None:
            weight *= 1.0 + float(transition_weight) * transition_gauss(
                start, transitions[ep], sigma_lead=sigma_lead, sigma_trail=sigma_trail
            )
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
    vlash_offset_max: int = 0,
    event_heads: bool | None = None,
    event_transition_weight: float | None = None,
    event_aux_weight: float = 0.20,
    event_ttt_weight: float = 0.02,
    event_chunk_gamma: float = EVENT_CHUNK_GAMMA,
    event_history: int = EVENT_HISTORY,
    event_ttt_horizon: int = EVENT_TTT_HORIZON,
    verbose: bool = True,
) -> str:
    """Continue-train `checkpoint` on `rollouts` (+ `base` demos). Returns the path.

    ``vlash_offset_max > 0`` enables the VLASH temporal-offset augmentation
    (`_OffsetWindows`): observation at t, state and action chunk at t+delta,
    ``delta ~ U{0..vlash_offset_max}``. With an empty ``rollouts`` the fine-tune
    runs on the base demonstrations alone, which is the VLASH configuration.

    P13-A (both default off; ``None`` resolves from the environment):

    * ``event_heads`` - ``FRUIT_POLICY_EVENT_HEADS``: attach the phase/TtT
      heads to the model, train them through the shared proprio encoder with
      ``event_aux_weight`` * phase CE + ``event_ttt_weight`` * TtT MSE
      (ForeTime's 0.20 / 0.02), and save their parameters under
      ``payload["event_heads"]`` (the ``model`` entry stays strict-loadable by
      the shipped `PolicyRunner`);
    * ``event_transition_weight`` - ``FRUIT_POLICY_EVENT_TRANSITION_WEIGHT``:
      DAM-VLA's transition-weighted loss, ``1 + alpha * g(d)`` per window plus
      the ``gamma**j`` chunk decay (``event_chunk_gamma``).
    """
    if weight_mode not in ("ones", "success", "awr"):
        raise ValueError(f"weight_mode must be ones|success|awr, got {weight_mode!r}")
    if close_weight < 1.0:
        raise ValueError(f"close_weight must be >= 1.0, got {close_weight!r}")
    settings = event_settings_from_env()
    if event_heads is None:
        event_heads = settings["event_heads"]
    if event_transition_weight is None:
        event_transition_weight = settings["transition_weight"]
    event_heads = bool(event_heads)
    event_transition_weight = float(event_transition_weight)
    if event_transition_weight < 0.0:
        raise ValueError(
            f"event_transition_weight must be >= 0, got {event_transition_weight!r}"
        )
    torch.manual_seed(seed)
    np.random.seed(seed)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(out_dir, exist_ok=True)

    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)
    config = dict(ckpt["config"])
    normalizer = Normalizer(
        action_mean=np.asarray(ckpt["normalizer"]["action_mean"], dtype=np.float32),
        action_std=np.asarray(ckpt["normalizer"]["action_std"], dtype=np.float32),
        obs_mean=np.asarray(ckpt["normalizer"]["obs_mean"], dtype=np.float32),
        obs_std=np.asarray(ckpt["normalizer"]["obs_std"], dtype=np.float32),
        goal_mean=np.asarray(ckpt["normalizer"]["goal_mean"], dtype=np.float32),
        goal_std=np.asarray(ckpt["normalizer"]["goal_std"], dtype=np.float32),
    )
    obs_horizon = int(config["obs_horizon"])
    action_horizon = int(config["action_horizon"])
    image_size = int(config["image_size"])

    # -------------------------------------------------------------- data --- #
    rollout_store = None
    if rollouts:
        rollout_store = EpisodeStore(
            rollouts, obs_horizon=obs_horizon, action_horizon=action_horizon,
            image_size=image_size, only_successful=False,
        )
    base_store = None
    if base and os.path.exists(os.path.join(base, "index.json")):
        base_store = EpisodeStore(
            base, obs_horizon=obs_horizon, action_horizon=action_horizon,
            image_size=image_size, only_successful=True,
        )

    rewards = (
        [float(ep["meta"].get("reward", 0.0)) for ep in rollout_store.episodes]
        if rollout_store is not None else []
    )
    vbar = float(np.mean(rewards)) if rewards else 0.0
    datasets: list[Dataset] = []
    weight_stats: dict[str, float] = {}
    event_stats: dict[str, float] = {}
    event_labels_needed = event_heads or event_transition_weight > 0.0
    for store, label in ((rollout_store, "rollout"), (base_store, "base")):
        if store is None:
            continue
        # P13-A labels: needed by the heads and/or by the transition weighting.
        labels = None
        if event_labels_needed:
            labels = [
                episode_event_data(
                    episode, normalizer, history=event_history,
                    ttt_horizon=event_ttt_horizon,
                )
                for episode in store.episodes
            ]
            phases, counts = np.unique(
                np.concatenate([lab["phase"] for lab in labels]), return_counts=True
            )
            event_stats[label] = {
                "episodes": len(labels),
                "phase_frames": {
                    int(p): int(c) for p, c in zip(phases.tolist(), counts.tolist())
                },
                "close_found": int(sum(1 for lab in labels if lab["close"] is not None)),
                "carry_found": int(sum(1 for lab in labels if lab["carry"] is not None)),
                "place_found": int(sum(1 for lab in labels if lab["place"] is not None)),
            }
        weights = _window_weights(
            store, mode=weight_mode, beta=beta, vbar=vbar,
            failure_weight=failure_weight, base_weight=base_weight,
            close_weight=close_weight, close_lead=close_lead,
            close_tail=close_tail,
            transitions=(
                [lab["transitions"] for lab in labels]
                if event_transition_weight > 0.0 else None
            ),
            transition_weight=event_transition_weight,
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
        if event_transition_weight > 0.0:
            # Windows at half the Gaussian's peak or more (within ~1.18 sigma of
            # a transition): the up-weighted population.
            threshold = 1.0 + 0.5 * float(event_transition_weight)
            weight_stats[label]["transition_weight"] = float(event_transition_weight)
            weight_stats[label]["transition_windows"] = int(
                sum(1 for w in weights if w >= threshold)
            )
        dataset: Dataset = _WeightedWindows(store, normalizer, weights)
        if event_heads:
            dataset = _EventWindows(dataset, store, labels)
        if vlash_offset_max > 0:
            dataset = _OffsetWindows(
                dataset, store, normalizer, vlash_offset_max,
                seed=seed + (0 if label == "rollout" else 1),
                event_labels=labels if event_heads else None,
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
        for label, stats in weight_stats.items():
            print(f"[finetune]   {label}: {stats}")
        if event_labels_needed:
            print(f"[finetune] event_heads={int(event_heads)} "
                  f"transition_weight={event_transition_weight} "
                  f"history={event_history} ttt_horizon={event_ttt_horizon} "
                  f"aux_weight={event_aux_weight} ttt_weight={event_ttt_weight} "
                  f"chunk_gamma={event_chunk_gamma}")
            for label, stats in event_stats.items():
                print(f"[finetune]   {label} labels: {stats}")

    # ------------------------------------------------------------- model --- #
    model = ConditionalUNet1D(
        action_dim=int(config["action_dim"]),
        image_channels=int(config["image_channels"]),
        obs_horizon=obs_horizon,
        goal_dim=int(config["goal_dim"]),
        proprio_dim=int(config["proprio_dim"]),
        num_skills=int(config.get("num_skills", 5)),
        event_heads=event_heads,
    ).to(device)
    if event_heads:
        # The base checkpoint carries no event keys; only they may be missing.
        missing, unexpected = model.load_state_dict(ckpt["model"], strict=False)
        if unexpected or not all(key.startswith("event.") for key in missing):
            raise RuntimeError(
                f"event-head load is not clean: unexpected={list(unexpected)}, "
                f"missing={list(missing)}"
            )
    else:
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
        phase_correct, phase_seen, ttt_abs, ttt_seen = 0.0, 0, 0.0, 0
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
                noisy, condition, timesteps, skill_labels=skill if hard else None,
                proprio_history=batch["history"].to(device) if event_heads else None,
            )
            loss, per_window = window_loss_terms(
                predicted, noise, weight,
                chunk_gamma=(
                    event_chunk_gamma if event_transition_weight > 0.0 else None
                ),
            )
            logits = model.last_router_logits
            router_loss = torch.nn.functional.cross_entropy(logits, skill)
            balance = model.load_balancing_loss(model.last_router_weights)
            total = loss + router_loss_weight * router_loss
            if not hard:
                total = total + balance_loss_weight * balance
            if event_heads:
                phase_logits, ttt_pred = model.last_event
                phase_label = batch["phase"].to(device)
                ttt_label = batch["ttt"].to(device)
                phase_loss = torch.nn.functional.cross_entropy(phase_logits, phase_label)
                ttt_loss = torch.nn.functional.mse_loss(ttt_pred, ttt_label)
                total = total + event_aux_weight * phase_loss + event_ttt_weight * ttt_loss
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
                if event_heads:
                    phase_correct += float(
                        (phase_logits.argmax(dim=-1) == phase_label).float().sum().item()
                    )
                    phase_seen += count
                    ttt_abs += float((ttt_pred - ttt_label).abs().sum().item())
                    ttt_seen += count
            seen += count
        last_loss = weighted_running / max(seen, 1)
        val = _demo_val_loss(model, datasets[-1] if base_store is not None else None,
                             device)
        epoch_record = {
            "epoch": epoch,
            "routing": "hard" if hard else "soft",
            "mse": running / max(seen, 1),
            "weighted_loss": last_loss,
            "router_ce": router_running / max(seen, 1),
            "router_acc": correct / max(seen, 1),
            "demo_val": val,
        }
        if event_heads:
            epoch_record["event_phase_acc"] = phase_correct / max(phase_seen, 1)
            epoch_record["event_ttt_mae"] = ttt_abs / max(ttt_seen, 1)
        history.append(epoch_record)
        event_text = (
            f" phase_acc={epoch_record['event_phase_acc']:.3f} "
            f"ttt_mae={epoch_record['event_ttt_mae']:.4f}"
            if event_heads else ""
        )
        print(
            f"[finetune] epoch {epoch + 1}/{epochs} {'HARD' if hard else 'SOFT'} "
            f"mse={running / max(seen, 1):.4f} weighted={last_loss:.4f} "
            f"router_ce={router_running / max(seen, 1):.3f} "
            f"router_acc={correct / max(seen, 1):.3f} demo_val={val:.4f}{event_text} "
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
    if event_heads or event_transition_weight > 0.0:
        provenance["event_heads"] = bool(event_heads)
        provenance["event_history"] = int(event_history)
        provenance["event_aux_weight"] = float(event_aux_weight)
        provenance["event_ttt_weight"] = float(event_ttt_weight)
        provenance["event_transition_weight"] = float(event_transition_weight)
        provenance["event_chunk_gamma"] = float(event_chunk_gamma)
        provenance["event_ttt_horizon"] = int(event_ttt_horizon)
        provenance["event_sigma_lead"] = float(EVENT_SIGMA_LEAD)
        provenance["event_sigma_trail"] = float(EVENT_SIGMA_TRAIL)
        provenance["event_label_stats"] = event_stats
    payload = {
        "model": model.state_dict(),
        "normalizer": ckpt["normalizer"],
        "config": config,
        "val_loss": ckpt.get("val_loss", float("nan")),
        "provenance": provenance,
    }
    if event_heads:
        # Keep the shipped runtime's strict load intact: `model` carries the
        # base keys only (the shared conditioning encoder holds the trained
        # event-structure change); the heads travel separately.
        base_state, event_state = event_state_split(payload["model"])
        payload["model"] = base_state
        payload["event_heads"] = {
            "state": event_state,
            "history": int(event_history),
            "num_phases": EVENT_PHASES,
            "aux_weight": float(event_aux_weight),
            "ttt_weight": float(event_ttt_weight),
            "ttt_horizon": int(event_ttt_horizon),
            "note": (
                "auxiliary phase/TtT heads (P13-A), read-only: dropped at "
                "inference; `model` is strict-loadable by the shipped "
                "PolicyRunner. Reattach with ConditionalUNet1D(event_heads=True) "
                "+ model.event.load_state_dict(payload['event_heads']['state'])"
            ),
        }
    out_path = os.path.join(out_dir, "policy_best.pt")
    torch.save(payload, out_path)
    with open(os.path.join(out_dir, "finetune_history.json"), "w", encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=2)
    print(f"[finetune] saved {out_path} (last epoch, weighted loss {last_loss:.4f})",
          flush=True)
    return out_path
