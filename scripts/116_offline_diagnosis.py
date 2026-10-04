"""Offline diagnosis: (A) what moe_v8's DDIM-16 sample is on hold windows,
(B) how the direct env's observations compare to the training distribution.

No simulator. Writes logs/737_offline_fit_diagnosis.txt.
"""

from __future__ import annotations

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
DEMOS = os.path.join(REPO, "datasets", "demos_v8")
CKPT = os.path.join(REPO, "checkpoints", "moe_v8", "policy_best.pt")
REC = os.path.join(REPO, "datasets", "rl_rollouts", "moe_v8_rec", "direct_none_seed77")


ARM_JOINTS = {"left": [0, 2, 4, 6, 8, 10, 12], "right": [1, 3, 5, 7, 9, 11, 13]}


def policy_act(policy: PolicyRunner, obs: dict, seed: int = 1234, steps: int = 16):
    policy.reset()
    policy.generator = torch.Generator(device=policy.device).manual_seed(seed)
    policy._frames = [
        np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])
    ]
    return policy.act(obs["proprio"], obs["goal"], num_steps=steps)


def main() -> int:
    lines: list[str] = []
    put = lines.append

    store = EpisodeStore(DEMOS, obs_horizon=2, action_horizon=16, image_size=128)
    policy = PolicyRunner(CKPT)
    put(f"[A] OFFLINE FIT - moe_v8 on {DEMOS} ({len(store)} windows)")
    put(f"    checkpoint {CKPT}")
    put("")

    # Global action statistics (raw units, first action of each window).
    all_actions = np.stack([store[i]["action"] for i in range(0, len(store), 7)])
    global_mean = all_actions[:, 0, :7].mean(axis=0)
    global_std = all_actions[:, 0, :7].std(axis=0)
    put(f"    global mean action[:7] = {np.round(global_mean, 3).tolist()}")
    put(f"    global std  action[:7] = {np.round(global_std, 3).tolist()}")
    put("")

    rng = np.random.RandomState(7)
    sample = rng.choice(len(store), 240, replace=False)
    rows = []
    for i in sample:
        obs = store[int(i)]
        pred = policy_act(policy, obs)
        rec = obs["action"]
        ep, t = store.windows[int(i)]
        arm = store.episodes[ep]["meta"].get("arm", "left")
        q = obs["proprio"][:22][ARM_JOINTS[arm]]
        rows.append(
            {
                "skill": SKILLS[int(obs["skill"])],
                "t": int(t),
                "arm": arm,
                "pred": pred,
                "rec": rec,
                "q": q,
            }
        )

    put("    per skill: n, ||pred[0]-rec[0]||, ||pred[0]-q||, ||rec[0]-q||, "
        "||pred[0]-global mean||, ||rec[0]-global mean|| [rad]")
    for name in SKILLS:
        sel = [r for r in rows if r["skill"] == name]
        if not sel:
            continue
        e1 = np.median([np.linalg.norm(r["pred"][0, :7] - r["rec"][0, :7]) for r in sel])
        e2 = np.median([np.linalg.norm(r["pred"][0, :7] - r["q"][:7]) for r in sel])
        e3 = np.median([np.linalg.norm(r["rec"][0, :7] - r["q"][:7]) for r in sel])
        e4 = np.median([np.linalg.norm(r["pred"][0, :7] - global_mean) for r in sel])
        e5 = np.median([np.linalg.norm(r["rec"][0, :7] - global_mean) for r in sel])
        put(f"    {name:10s} n={len(sel):3d}  e(pred,rec)={e1:.3f}  e(pred,q)={e2:.3f}  "
            f"e(rec,q)={e3:.3f}  e(pred,mean)={e4:.3f}  e(rec,mean)={e5:.3f}")
    put("")

    # Horizon profile: the recorded chunk on approach windows is constant; where
    # is the sample's error along the 16-step horizon?
    put("    error ||pred[k]-rec[k]|| by chunk index k (approach / lift / place):")
    for name in ("approach", "lift", "place"):
        sel = [r for r in rows if r["skill"] == name]
        if not sel:
            continue
        prof = [
            np.median([np.linalg.norm(r["pred"][k, :7] - r["rec"][k, :7]) for r in sel])
            for k in range(16)
        ]
        put(f"      {name:10s} " + " ".join(f"{v:.2f}" for v in prof))
    put("")

    # Constant-target subset: where the recorded chunk is a hold, what does the
    # sample do?  (approach windows, |rec[k]-rec[0]| < 0.02 rad for all k)
    const, moving = [], []
    for r in rows:
        spread = float(np.abs(r["rec"][:, :7] - r["rec"][0, :7]).max())
        (const if spread < 0.02 else moving).append(r)
    put(f"    approach windows: constant-chunk {sum(1 for r in const if r['skill']=='approach')}"
        f" / moving-chunk {sum(1 for r in moving if r['skill']=='approach')}")
    for label, sel in (("constant", [r for r in const if r["skill"] == "approach"]),
                       ("moving", [r for r in moving if r["skill"] == "approach"])):
        if not sel:
            continue
        e1 = np.median([np.linalg.norm(r["pred"][0, :7] - r["rec"][0, :7]) for r in sel])
        e2 = np.median([np.linalg.norm(r["pred"][0, :7] - r["q"][:7]) for r in sel])
        put(f"      {label:9s} n={len(sel):3d}  ||pred-rec||={e1:.3f}  ||pred-q||={e2:.3f}")
    put("")

    # Per-joint behaviour on approach windows: recorded vs predicted medians and
    # cross-window correlation.  A model that regressed to the mean shows a
    # near-constant prediction with low correlation to the target.
    appr = [r for r in rows if r["skill"] == "approach"]
    rec = np.stack([r["rec"][0, :7] for r in appr])
    prd = np.stack([r["pred"][0, :7] for r in appr])
    put("    approach windows, per joint: median recorded | median predicted | "
        "pred std | corr(pred, rec)")
    for j in range(7):
        c = float(np.corrcoef(prd[:, j], rec[:, j])[0, 1]) if prd[:, j].std() > 1e-9 else 0.0
        put(f"      j{j+1}: {np.median(rec[:, j]):+.3f} | {np.median(prd[:, j]):+.3f} | "
            f"{prd[:, j].std():.3f} | {c:+.2f}")
    bias = np.median(prd - rec, axis=0)
    put(f"    median bias (pred-rec) per joint = {np.round(bias, 3).tolist()}")
    put(f"    ||median bias|| = {np.linalg.norm(bias):.3f} rad; "
        f"median ||pred-rec|| = {np.median(np.linalg.norm(prd-rec, axis=1)):.3f} rad")
    put("")

    put("    shrinkage fit pred = a*rec + b per joint (approach windows):")
    for j in range(7):
        a, b = np.polyfit(rec[:, j], prd[:, j], 1)
        put(f"      j{j+1}: slope {a:+.2f}  intercept {b:+.3f}  (global mean {global_mean[j]:+.3f})")
    put("")

    # Sampler budget: if the bias is the diffusion sample not converging, more
    # DDIM steps (or averaging samples) should shrink it.  The deployed speed of
    # record is DDIM-16.
    pick_steps = [
        int(i)
        for i in rng.choice(len(store), 400, replace=False)
        if SKILLS[int(store[int(i)]["skill"])] == "approach"
    ][:48]
    put(f"    DDIM-step sweep on {len(pick_steps)} approach windows "
        f"(median ||pred[0]-rec[0]||):")
    for steps in (4, 8, 16, 50, 100):
        errs = [
            np.linalg.norm(
                policy_act(policy, store[i], steps=steps)[0, :7] - store[i]["action"][0, :7]
            )
            for i in pick_steps
        ]
        put(f"      steps={steps:3d}: {np.median(errs):.3f} rad")
    for n in (2, 4):
        errs = []
        for i in pick_steps:
            obs = store[i]
            preds = [policy_act(policy, obs, seed=1000 + k) for k in range(n)]
            mean = np.mean([p[0, :7] for p in preds], axis=0)
            errs.append(np.linalg.norm(mean - obs["action"][0, :7]))
        put(f"      {n}x averaged DDIM-16 samples: {np.median(errs):.3f} rad")
    put("")

    # Conditioning sensitivity: swap proprio / goal / images with another
    # window's, same noise seed (paired).  Deterministic selection: the first
    # 40 approach windows in store order, partner shifted by 7000 windows
    # (~14 episodes later, a different phase/arm).
    put("    conditioning sensitivity (first 40 approach windows, paired seed 1234; "
        "median ||pred_variant - pred_base|| [rad], finger delta):")
    pick = [i for i in range(len(store)) if SKILLS[int(store[i]["skill"])] == "approach"][:40]
    base, swap_prop, swap_goal, swap_img, blank_img = [], [], [], [], []
    pprop, pgoal = [], []
    for i in pick:
        obs = store[i]
        j = (i + 7000) % len(store)
        other = store[j]
        pprop.append(float(np.abs(other["proprio"] - obs["proprio"]).max()))
        pgoal.append(float(np.linalg.norm(other["goal"] - obs["goal"])))
        pb = policy_act(policy, obs)
        obs_p = dict(obs); obs_p["proprio"] = other["proprio"]
        obs_g = dict(obs); obs_g["goal"] = other["goal"]
        obs_i = dict(obs); obs_i["image"] = other["image"]
        obs_b = dict(obs); obs_b["image"] = np.zeros_like(obs["image"])
        base.append(pb); swap_prop.append(policy_act(policy, obs_p))
        swap_goal.append(policy_act(policy, obs_g))
        swap_img.append(policy_act(policy, obs_i))
        blank_img.append(policy_act(policy, obs_b))
    for label, arr in (("swap proprio", swap_prop), ("swap goal", swap_goal),
                       ("swap images", swap_img), ("zero images", blank_img)):
        dp = np.median([np.linalg.norm(a[0, :7] - b[0, :7]) for a, b in zip(arr, base)])
        df = np.median([abs(a[0, 7] - b[0, 7]) for a, b in zip(arr, base)])
        put(f"      {label:13s} d_arm={dp:.3f}  d_finger={df:.4f}")
    put(f"      (swap partner differs by median max|d proprio|={np.median(pprop):.3f} rad, "
        f"|d goal|={np.median(pgoal):.3f})")
    put(f"      (baseline ||pred-rec|| on these windows = "
        f"{np.median([np.linalg.norm(a[0,:7]-store[i]['action'][0,:7]) for a,i in zip(base,pick)]):.3f}; "
        f"same-seed repeat noise floor 0.000)")
    put("")

    # ------------------------------------------------------------- env match --
    put("[B] DIRECT ENV vs TRAINING DISTRIBUTION")
    with open(os.path.join(REC, "index.json"), encoding="utf-8") as fh:
        entry = json.load(fh)[0]
    with np.load(os.path.join(REC, entry["file"])) as z:
        env_q = np.asarray(z["joint_positions"], dtype=np.float32)
        env_goal = np.asarray(z["goal"], dtype=np.float32)
        env_finger = np.asarray(z["finger_opening"], dtype=np.float32)
        env_act = np.asarray(z["action"], dtype=np.float32)
        env_rgb0 = np.asarray(z["image_rgb"][0])
        env_depth0 = np.asarray(z["image_distance_to_image_plane"][0])
        env_mask0 = (np.asarray(z["target_mask"][0]) > 0).astype(np.float32)
    if env_depth0.ndim == 3:
        env_depth0 = env_depth0[..., 0]
    put(f"    recorded direct rollout: {entry['file']} ({env_q.shape[0]} frames, "
        f"seed {entry['seed']}, success={entry['success']})")
    put("")

    # Demo manifold: nearest-neighbour distance between demo windows in the 25-D
    # proprio and the 8-D goal (subsample: every 4th window, full-store distances
    # on a subsample).
    demo_q = np.stack([store[i]["proprio"] for i in range(0, len(store), 4)])
    demo_g = np.stack([store[i]["goal"] for i in range(0, len(store), 4)])
    put(f"    demo windows subsampled {len(demo_q)}")
    for name, vec_demo, vec_env in (("proprio(22 q)", demo_q[:, :22], env_q),
                                    ("goal(8)", demo_g, env_goal)):
        # demo -> demo nearest neighbour baseline (leave-one-out, subsampled)
        d2 = ((vec_demo[:, None, :] - vec_demo[None, :, :]) ** 2).sum(-1)
        np.fill_diagonal(d2, np.inf)
        nn_demo = np.sqrt(d2.min(axis=1))
        d_env = np.sqrt(((vec_env[:, None, :] - vec_demo[None, :, :]) ** 2).sum(-1))
        nn_env = d_env.min(axis=1)
        put(f"    {name:11s} demo->demo NN: median {np.median(nn_demo):.3f} p95 "
            f"{np.percentile(nn_demo,95):.3f} | env->demo NN: frame0 {nn_env[0]:.3f}, "
            f"frames<4 {np.round(nn_env[:4],3).tolist()}, all-frames median "
            f"{np.median(nn_env):.3f} p95 {np.percentile(nn_env,95):.3f}")
    put("")
    # Visual-input content.  Pre-existing (the observation arrays are identical
    # in demos_v7): the policy crop is the top-left 128x128 of the 240x424
    # frame and the target mask is absent in most frames.
    empty = mid = clipped = 0
    for ep in store.episodes:
        if ep["mask"] is None:
            continue
        m = ep["mask"] >= 0.5
        f = m.mean(axis=(1, 2))
        empty += int((f < 0.0005).sum())
        for i in np.flatnonzero((f >= 0.0005) & (f <= 0.2)):
            ys, xs = np.nonzero(m[i])
            mid += 1
            clipped += int(ys.max() > 127 or xs.max() > 383)
    put(f"    target mask: near-empty {empty} frames, fruit blob {mid} frames; "
        f"fruit blob clipped by the policy crop (rows 0..127, cols 0..383): "
        f"{clipped}/{mid} = {100*clipped/max(mid,1):.0f}%")
    put("")

    # The first observation is the one that decides the first chunk.
    put("    first observation, per-field: env frame 0 vs the nearest demo window")
    nearest = int(np.argmin(((demo_q[:, :22] - env_q[0]) ** 2).sum(-1)))
    # map demo subsample index -> store index
    demos_idx = list(range(0, len(store), 4))[nearest]
    obs = store[demos_idx]
    put(f"      demo window store index {demos_idx} (episode {store.windows[demos_idx][0]}, "
        f"t={store.windows[demos_idx][1]}, skill={SKILLS[int(obs['skill'])]})")
    pq = np.concatenate([env_q[0], env_finger[0], np.zeros(2, dtype=np.float32)])
    d = np.abs(pq - obs["proprio"])
    put(f"      proprio max|diff|={float(d.max()):.4f} rad, mean|diff|={float(d.mean()):.4f}")
    put(f"      env  proprio[:14]={np.round(env_q[0][:14],3).tolist()}")
    put(f"      demo proprio[:14]={np.round(obs['proprio'][:14],3).tolist()}")
    put(f"      env  goal={np.round(env_goal[0],3).tolist()}")
    put(f"      demo goal={np.round(obs['goal'],3).tolist()}")
    # image channels through the runtime's own preprocessing, with the env's
    # actual depth/mask frames (loaded above).
    policy.push_frame(env_rgb0, env_depth0, env_mask0)
    env_frame = policy._frames[-1].copy()
    demo_frame = np.transpose(obs["image"][-1], (1, 2, 0))
    for c, label in enumerate(("rgb", "depth", "mask")):
        # `image` is 5-channel (3 rgb + depth + mask); compare like with like.
        a = env_frame[..., :3] if label == "rgb" else env_frame[..., c + 2]
        b = demo_frame[..., :3] if label == "rgb" else demo_frame[..., c + 2]
        put(f"      image {label}: env mean {a.mean():.4f} std "
            f"{a.std():.4f} | demo mean {b.mean():.4f} "
            f"std {b.std():.4f} | mean|diff| "
            f"{np.abs(a-b).mean():.4f}")
    put("")
    put(f"    env first applied actions[0:4] finger = {np.round(env_act[:4,7],4).tolist()}")
    put(f"    demo action[0:4] finger at the nearest window = "
        f"{np.round(obs['action'][:4,7],4).tolist()}")

    with open(os.path.join(REPO, "logs", "737_offline_fit_diagnosis.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
