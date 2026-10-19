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
    vlash_offset_max: int = 0,
    verbose: bool = True,
) -> str:
    """Continue-train `checkpoint` on `rollouts` (+ `base` demos). Returns the path.

    ``vlash_offset_max > 0`` enables the VLASH temporal-offset augmentation
    (`_OffsetWindows`): observation at t, state and action chunk at t+delta,
    ``delta ~ U{0..vlash_offset_max}``. With an empty ``rollouts`` the fine-tune
    runs on the base demonstrations alone, which is the VLASH configuration.
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
            per_window = torch.nn.functional.mse_loss(
                predicted, noise, reduction="none"
            ).flatten(1).mean(1)
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
