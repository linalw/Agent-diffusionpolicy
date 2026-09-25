"""Training loop for the conditional diffusion policy."""

from __future__ import annotations

import json
import os
import time

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from .data import EpisodeStore, Normalizer
from .diffusion import DiffusionSchedule
from .model import ConditionalUNet1D


class WindowDataset(Dataset):
    def __init__(self, store: EpisodeStore, normalizer: Normalizer):
        self.store = store
        self.normalizer = normalizer

    def __len__(self) -> int:
        return len(self.store)

    def __getitem__(self, index: int) -> dict:
        sample = self.store[index]
        return {
            "image": torch.from_numpy(sample["image"]),
            "proprio": torch.from_numpy(
                self.normalizer.normalize_obs(sample["proprio"])
            ),
            "goal": torch.from_numpy(self.normalizer.normalize_goal(sample["goal"])),
            "action": torch.from_numpy(
                self.normalizer.normalize_action(sample["action"]).T.copy()
            ),  # (action_dim, horizon)
        }


def train(
    data_dir: str,
    out_dir: str = "checkpoints/policy",
    epochs: int = 4,
    batch_size: int = 32,
    learning_rate: float = 1e-4,
    obs_horizon: int = 2,
    action_horizon: int = 16,
    image_size: int = 128,
    num_diffusion_steps: int = 100,
    val_fraction: float = 0.15,
    seed: int = 0,
    device: str | None = None,
) -> str:
    torch.manual_seed(seed)
    np.random.seed(seed)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(out_dir, exist_ok=True)

    store = EpisodeStore(
        data_dir,
        obs_horizon=obs_horizon,
        action_horizon=action_horizon,
        image_size=image_size,
    )
    normalizer = store.compute_normalizer()
    print(f"[train] {store.summary()}", flush=True)

    # Split by window for now; with more data this should split by episode.
    total = len(store)
    indices = np.random.permutation(total)
    val_count = max(1, int(total * val_fraction))
    val_indices = set(indices[:val_count].tolist())

    full = WindowDataset(store, normalizer)
    train_set = torch.utils.data.Subset(full, [i for i in range(total) if i not in val_indices])
    val_set = torch.utils.data.Subset(full, sorted(val_indices))
    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False)

    sample = full[0]
    model = ConditionalUNet1D(
        action_dim=sample["action"].shape[0],
        image_channels=4,
        obs_horizon=obs_horizon,
        goal_dim=sample["goal"].shape[0],
        proprio_dim=sample["proprio"].shape[0],
    ).to(device)
    schedule = DiffusionSchedule(num_diffusion_steps, device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-6)
    parameters = sum(p.numel() for p in model.parameters())
    print(f"[train] device={device} parameters={parameters/1e6:.2f}M", flush=True)

    best_val = float("inf")
    history = []
    for epoch in range(epochs):
        model.train()
        running, count = 0.0, 0
        start = time.time()
        for batch in train_loader:
            action = batch["action"].to(device)
            noise = torch.randn_like(action)
            timesteps = schedule.sample_timesteps(action.shape[0])
            noisy = schedule.add_noise(action, noise, timesteps)
            condition = (
                batch["image"].to(device),
                batch["goal"].to(device),
                batch["proprio"].to(device),
            )
            predicted = model.denoise(noisy, condition, timesteps)
            loss = torch.nn.functional.mse_loss(predicted, noise)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            running += float(loss.item()) * action.shape[0]
            count += action.shape[0]

        model.eval()
        val_running, val_count = 0.0, 0
        with torch.no_grad():
            for batch in val_loader:
                action = batch["action"].to(device)
                noise = torch.randn_like(action)
                timesteps = schedule.sample_timesteps(action.shape[0])
                noisy = schedule.add_noise(action, noise, timesteps)
                condition = (
                    batch["image"].to(device),
                    batch["goal"].to(device),
                    batch["proprio"].to(device),
                )
                predicted = model.denoise(noisy, condition, timesteps)
                val_running += float(torch.nn.functional.mse_loss(predicted, noise).item()) * action.shape[0]
                val_count += action.shape[0]

        train_loss = running / max(count, 1)
        val_loss = val_running / max(val_count, 1)
        history.append({"epoch": epoch, "train": train_loss, "val": val_loss})
        print(
            f"[train] epoch {epoch + 1}/{epochs} train={train_loss:.4f} val={val_loss:.4f} "
            f"({time.time() - start:.1f}s)",
            flush=True,
        )
        if val_loss < best_val:
            best_val = val_loss
            torch.save(
                {
                    "model": model.state_dict(),
                    "normalizer": normalizer.as_dict(),
                    "config": {
                        "action_dim": int(sample["action"].shape[0]),
                        "image_channels": 4,
                        "obs_horizon": obs_horizon,
                        "action_horizon": action_horizon,
                        "goal_dim": int(sample["goal"].shape[0]),
                        "proprio_dim": int(sample["proprio"].shape[0]),
                        "num_diffusion_steps": num_diffusion_steps,
                        "image_size": image_size,
                    },
                    "val_loss": val_loss,
                },
                os.path.join(out_dir, "policy_best.pt"),
            )

    with open(os.path.join(out_dir, "history.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "history": history,
                "episodes": len(store.episodes),
                "windows": len(store),
                "parameters": parameters,
                "best_val": best_val,
            },
            fh,
            indent=2,
        )
    print(f"[train] best val loss {best_val:.4f}; checkpoint in {out_dir}", flush=True)
    return os.path.join(out_dir, "policy_best.pt")
