"""Action-head forensics for the P4 shrinkage: where does `pred ~ 0.85*rec` come from?

Offline, no simulator. Consumes the same checkpoints/datasets as
`116_offline_diagnosis.py`, but instead of only reporting the sampled chunk it
decomposes the error by diffusion timestep:

  [1] normalizer audit - saved stats vs stats recomputed from the dataset;
  [2] the model's direct x0 prediction: for each training-timestep bucket, add
      noise to the recorded action, run the denoiser, and reconstruct x0_hat in
      raw units; report the error and the paired-average (over noise seeds)
      slope `x0_hat ~ a*rec + b` per joint;
  [3] the epsilon residual in normalized units per timestep (the actual training
      quantity) and its implied x0 error;
  [4] the DDIM chain at 4/16/100 steps, plus the x0_hat along the chain, to say
      whether the shrink appears before the sampler or is produced by it;
  [5] the same decomposition per arm (left/right) and for the six moving
      (close-tracking) approach windows.

Writes `logs/742_action_forensics.txt`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch

from fruit_sorting.policy.data import EpisodeStore
from fruit_sorting.policy.runtime import PolicyRunner
from fruit_sorting.policy.skills import SKILLS

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DEFAULT_DEMOS = os.path.join(REPO, "datasets", "demos_v8")
DEFAULT_CKPT = os.path.join(REPO, "checkpoints", "moe_v8", "policy_best.pt")
DEFAULT_OUT = os.path.join(REPO, "logs", "742_action_forensics.txt")

ARM_JOINTS = {"left": [0, 2, 4, 6, 8, 10, 12], "right": [1, 3, 5, 7, 9, 11, 13]}


def condition_of(policy: PolicyRunner, obs: dict, dtype=torch.float32):
    """The (image, goal, proprio) tensors the model conditions on, from a store item."""
    image = np.asarray(obs["image"])
    image_t = torch.from_numpy(image[None]).to(policy.device, dtype)
    goal_t = torch.from_numpy(
        policy.normalizer.normalize_goal(np.asarray(obs["goal"], dtype=np.float32))[None]
    ).to(policy.device, dtype)
    proprio_t = torch.from_numpy(
        policy.normalizer.normalize_obs(np.asarray(obs["proprio"], dtype=np.float32))[None]
    ).to(policy.device, dtype)
    return image_t, goal_t, proprio_t


@torch.no_grad()
def x0_hat_at(policy: PolicyRunner, obs: dict, t: int, noise: torch.Tensor) -> np.ndarray:
    """One-step x0 reconstruction in raw units at a single timestep."""
    action_n = policy.normalizer.normalize_action(obs["action"].astype(np.float32)).T
    action_n = torch.from_numpy(action_n[None].copy()).to(policy.device)
    ts = torch.full((1,), int(t), dtype=torch.long, device=policy.device)
    noisy = policy.schedule.add_noise(action_n, noise, ts)
    eps_hat = policy.model.denoise(noisy, condition_of(policy, obs), ts)
    alpha = policy.schedule.alphas_cumprod[int(t)]
    clean = (noisy - torch.sqrt(1 - alpha) * eps_hat) / torch.sqrt(alpha)
    clean = clean.clamp(-4.0, 4.0)
    raw = policy.normalizer.denormalize_action(
        clean[0].transpose(0, 1).cpu().numpy().astype(np.float32)
    )
    return raw


@torch.no_grad()
def eps_residual(policy: PolicyRunner, obs: dict, t: int, noise: torch.Tensor):
    """The training quantity: ||eps_hat - eps|| in normalized units."""
    action_n = policy.normalizer.normalize_action(obs["action"].astype(np.float32)).T
    action_n = torch.from_numpy(action_n[None].copy()).to(policy.device)
    ts = torch.full((1,), int(t), dtype=torch.long, device=policy.device)
    noisy = policy.schedule.add_noise(action_n, noise, ts)
    eps_hat = policy.model.denoise(noisy, condition_of(policy, obs), ts)
    return float(torch.linalg.vector_norm(eps_hat - noise).item() / np.sqrt(noise.numel()))


@torch.no_grad()
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", default=DEFAULT_CKPT)
    parser.add_argument("--demos", default=DEFAULT_DEMOS)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    DEMOS, CKPT, OUT = args.demos, args.ckpt, args.out

    lines: list[str] = []
    put = lines.append
    policy = PolicyRunner(CKPT)
    policy.set_precision(False)  # forensics in fp32; fp16 halves precision of the probe
    put(f"# Action forensics: {CKPT}")
    put(f"# device={policy.device} image_size={policy.image_size} "
        f"cfg={json.dumps({k: policy.config[k] for k in ('action_dim','image_channels','image_size','num_diffusion_steps')})}")
    put("")

    # ---------------------------------------------------------------- [1] --
    ck = torch.load(CKPT, map_location="cpu", weights_only=False)
    norm = ck["normalizer"]
    store = EpisodeStore(DEMOS, obs_horizon=2, action_horizon=16, image_size=128)
    recomputed = store.compute_normalizer()
    am = np.array(norm["action_mean"], dtype=np.float64)
    asd = np.array(norm["action_std"], dtype=np.float64)
    rm = recomputed.action_mean.astype(np.float64)
    rs = recomputed.action_std.astype(np.float64)
    put("[1] NORMALIZER AUDIT (checkpoint vs recomputed from demos_v8)")
    put(f"    max |mean diff| = {np.abs(am - rm).max():.2e}   "
        f"max |std ratio - 1| = {np.abs(asd / rs - 1).max():.2e}")
    put(f"    std ratio ckpt/recomputed per action dim = {np.round(asd / rs, 4).tolist()}")
    put("")

    # approach windows: all of them, plus a deterministic subsample for the sweeps
    appr_all = [i for i in range(len(store)) if SKILLS[int(store[i]["skill"])] == "approach"]
    rng = np.random.RandomState(7)
    sub = sorted(rng.choice(appr_all, min(64, len(appr_all)), replace=False).tolist())
    put(f"    approach windows total {len(appr_all)}, used {len(sub)}")
    arms = np.array([store.episodes[store.windows[i][0]]["meta"].get("arm", "left") for i in sub])
    moving = np.array([
        float(np.abs(store[i]["action"][:, :7] - store[i]["action"][0, :7]).max()) >= 0.02
        for i in sub
    ])
    put(f"    used subsample: left {int((arms == 'left').sum())} / right "
        f"{int((arms == 'right').sum())}; moving chunks {int(moving.sum())}")
    put("")

    # ---------------------------------------------------------------- [2] --
    # Direct x0 reconstruction at the training timestep distribution.
    put("[2] DIRECT x0_hat (one-step, raw units): per-timestep error and paired-mean slope")
    put("    t   alpha   eps_resid  ||x0-rec|| med   x0 err mean   slope(j1..j7)")
    seeds = [11, 22, 33, 44, 55, 66]
    ts = [0, 2, 5, 10, 20, 40, 60, 80, 95, 99]
    paired_means: dict[int, np.ndarray] = {}
    for t in ts:
        alpha = float(policy.schedule.alphas_cumprod[t])
        x0_err, eps_res = [], []
        means = []
        for i in sub:
            obs = store[i]
            raws = []
            for s in seeds:
                noise = torch.randn(
                    (1, policy.config["action_dim"], policy.config["action_horizon"]),
                    device=policy.device, generator=torch.Generator(device=policy.device).manual_seed(s * 1000 + int(t)),
                )
                raw = x0_hat_at(policy, obs, t, noise)
                raws.append(raw[0, :7])
                eps_res.append(eps_residual(policy, obs, t, noise))
            raws = np.stack(raws)  # (seeds, 7)
            mean = raws.mean(0)
            means.append(mean)
            rec = obs["action"][0, :7]
            x0_err.append(np.linalg.norm(mean - rec))
        means = np.stack(means)
        recs = np.stack([store[i]["action"][0, :7] for i in sub])
        slopes = []
        for j in range(7):
            if means[:, j].std() > 1e-9 and recs[:, j].std() > 1e-9:
                a, _ = np.polyfit(recs[:, j], means[:, j], 1)
                slopes.append(a)
            else:
                slopes.append(float("nan"))
        paired_means[t] = means
        put(f"    {t:3d}  {alpha:.3f}   {np.median(eps_res):.4f}      "
            f"{np.median(x0_err):.3f}        {np.mean(x0_err):.3f}      "
            + " ".join(f"{s:+.2f}" for s in slopes))
    put("    (error is ||E[x0_hat over 6 noise seeds] - rec[0]||; slope is the per-joint")
    put("     regression of that paired mean on the recorded action)")
    put("")

    # ---------------------------------------------------------------- [3] --
    put("[3] EPSILON RESIDUAL by timestep (normalized units) and implied x0-scale")
    put("    t    median ||eps_hat-eps||   sqrt((1-a)/a)*resid (raw-down-scaled)")
    for t in ts:
        alpha = float(policy.schedule.alphas_cumprod[t])
        res = []
        for i in sub:
            for s in seeds:
                noise = torch.randn(
                    (1, policy.config["action_dim"], policy.config["action_horizon"]),
                    device=policy.device,
                    generator=torch.Generator(device=policy.device).manual_seed(s * 1000 + int(t)),
                )
                res.append(eps_residual(policy, store[i], t, noise))
        put(f"    {t:3d}       {np.median(res):.4f}                 "
            f"{np.sqrt((1 - alpha) / alpha) * np.median(res):.4f}")
    put("")

    # ---------------------------------------------------------------- [4] --
    put("[4] DDIM CHAIN: final error (raw units, ||pred[0]-rec[0]||) at 4/16/100 steps")
    put("    steps   median err   slope(j1..j7)")
    for steps in (4, 16, 100):
        errs, preds = [], []
        for i in sub:
            policy.reset()
            policy._frames = [
                np.transpose(store[i]["image"][k], (1, 2, 0))
                for k in range(store[i]["image"].shape[0])
            ]
            policy.generator = torch.Generator(device=policy.device).manual_seed(1234)
            pred = policy.act(store[i]["proprio"], store[i]["goal"], num_steps=steps)
            errs.append(np.linalg.norm(pred[0, :7] - store[i]["action"][0, :7]))
            preds.append(pred[0, :7])
        preds = np.stack(preds)
        recs = np.stack([store[i]["action"][0, :7] for i in sub])
        slopes = []
        for j in range(7):
            a, _ = np.polyfit(recs[:, j], preds[:, j], 1)
            slopes.append(a)
        put(f"    {steps:5d}   {np.median(errs):.3f}        "
            + " ".join(f"{s:+.2f}" for s in slopes))
    put("")

    # x0_hat trajectory along the 16-step chain: does the shrink grow during sampling?
    put("    x0_hat shown by the chain (denoised prediction at each visited t):")
    steps = 16
    times = torch.linspace(
        policy.schedule.num_train_steps - 1, 0, steps, dtype=torch.long, device=policy.device
    )
    traj, recs = [], []
    for i in sub:
        obs = store[i]
        image_t, goal_t, proprio_t = condition_of(policy, obs)
        seed = 1234
        sample = torch.randn(
            (1, policy.config["action_dim"], policy.config["action_horizon"]),
            device=policy.device,
            generator=torch.Generator(device=policy.device).manual_seed(seed),
        )
        row = []
        for k, t in enumerate(times):
            t_batch = t.expand(1)
            eps_hat = policy.model.denoise(sample, (image_t, goal_t, proprio_t), t_batch)
            alpha = policy.schedule.alphas_cumprod[t]
            alpha_prev = (
                policy.schedule.alphas_cumprod[times[k + 1]] if k + 1 < steps
                else torch.tensor(1.0, device=policy.device)
            )
            clean = ((sample - torch.sqrt(1 - alpha) * eps_hat) / torch.sqrt(alpha)).clamp(-4.0, 4.0)
            raw = policy.normalizer.denormalize_action(
                clean[0].transpose(0, 1).cpu().numpy().astype(np.float32)
            )
            row.append(raw[0, :7])
            sample = torch.sqrt(alpha_prev) * clean + torch.sqrt(1 - alpha_prev) * eps_hat
        traj.append(np.stack(row))
        recs.append(obs["action"][0, :7])
    traj = np.stack(traj)  # (n, steps, 7)
    recs = np.stack(recs)
    for k, t in enumerate(times.tolist()):
        slopes = []
        for j in range(7):
            a, _ = np.polyfit(recs[:, j], traj[:, k, j], 1)
            slopes.append(a)
        err = np.median([np.linalg.norm(traj[n, k] - recs[n]) for n in range(len(sub))])
        put(f"      step {k:2d} t={t:3d}: err={err:.3f}  slopes "
            + " ".join(f"{s:+.2f}" for s in slopes))
    put("")

    # ---------------------------------------------------------------- [5] --
    put("[5] PER-ARM / moving-chunk split (DDIM-16, raw units)")
    for label, sel in (
        ("left", arms == "left"), ("right", arms == "right"),
        ("wait(const chunk)", ~moving), ("moving chunk", moving),
    ):
        idx = [sub[k] for k in np.flatnonzero(sel)]
        if not idx:
            put(f"    {label:18s} n=0")
            continue
        errs, preds = [], []
        for i in idx:
            policy.reset()
            policy._frames = [
                np.transpose(store[i]["image"][k], (1, 2, 0))
                for k in range(store[i]["image"].shape[0])
            ]
            policy.generator = torch.Generator(device=policy.device).manual_seed(1234)
            pred = policy.act(store[i]["proprio"], store[i]["goal"], num_steps=16)
            errs.append(np.linalg.norm(pred[0, :7] - store[i]["action"][0, :7]))
            preds.append(pred[0, :7])
        preds = np.stack(preds)
        recs = np.stack([store[i]["action"][0, :7] for i in idx])
        slopes = []
        for j in range(7):
            if preds[:, j].std() > 1e-9 and recs[:, j].std() > 1e-9:
                a, _ = np.polyfit(recs[:, j], preds[:, j], 1)
                slopes.append(a)
            else:
                slopes.append(float("nan"))
        bias = np.median(preds - recs, axis=0)
        put(f"    {label:18s} n={len(idx):3d}  ||pred-rec||={np.median(errs):.3f}  "
            f"||median bias||={np.linalg.norm(bias):.3f}  slopes "
            + " ".join(f"{s:+.2f}" for s in slopes))
    put("")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
