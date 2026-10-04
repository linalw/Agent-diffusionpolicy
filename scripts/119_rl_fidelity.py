"""Offline action fidelity of one or two checkpoints on a window set (P4).

No simulator. The metric is the one the P4 diagnosis used: for the first action
of a DDIM-16 sample, ``||pred[0,:7] - rec[0,:7]||`` against the recorded
command, plus the finger channel ``|pred[0,7] - rec[0,7]|`` and the open/close
phase agreement. Each window gets a fixed noise seed, so when a candidate is
given the two checkpoints are compared on identical windows *and* identical
sampler noise (paired).

Windows come from any directory with the training schema (`datasets/demos_v8`,
or a `--record` rollout directory); rollouts are read with successes *and*
failures so the table can show where the fine-tune changed what.

    <lingbot-python> scripts/119_rl_fidelity.py \
        --base checkpoints/moe_v9/policy_best.pt \
        --candidate checkpoints/rl_rwr1/policy_best.pt \
        --data datasets/rl_rollouts/rwr1/direct_none_seed101 \
        --data datasets/demos_v8 --windows 192 --out logs/761_rl_fidelity.txt
"""

from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch

from fruit_sorting.policy.data import EpisodeStore
from fruit_sorting.policy.runtime import PolicyRunner
from fruit_sorting.policy.skills import SKILLS

CLOSE = 0.030


def sample_action(policy: PolicyRunner, obs: dict, seed: int, steps: int) -> np.ndarray:
    """One DDIM sample for this window with a fixed noise seed (harness order)."""
    policy.reset()
    policy.generator = torch.Generator(device=policy.device).manual_seed(int(seed))
    policy._frames = [
        np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])
    ]
    return policy.act(obs["proprio"], obs["goal"], num_steps=int(steps))


def sign_p(better: int, worse: int) -> float:
    """One-sided binomial p = P(X >= better), X ~ Bin(better + worse, 0.5)."""
    n = better + worse
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(better, n + 1)) / (2.0 ** n)


def collect(data: str, args, policies: dict) -> list[dict]:
    store = EpisodeStore(data, obs_horizon=2, action_horizon=16, image_size=128,
                         only_successful=False)
    rng = np.random.RandomState(int(args.seed))
    count = min(int(args.windows), len(store))
    indices = np.sort(rng.choice(len(store), count, replace=False))
    rows = []
    for i in indices:
        obs = store[int(i)]
        ep, _t = store.windows[int(i)]
        meta = store.episodes[ep]["meta"]
        row = {
            "skill": SKILLS[int(obs["skill"])],
            "success": bool(meta.get("success", True)),
            "category": str(meta.get("category", "")),
            "rec": np.asarray(obs["action"][0], dtype=np.float64),
        }
        for name, policy in policies.items():
            row[name] = np.asarray(
                sample_action(policy, obs, int(args.seed) * 100003 + int(i), args.ddim)[0],
                dtype=np.float64,
            )
        rows.append(row)
    return store, rows


def _med(values) -> float:
    return float(np.median(values)) if len(values) else float("nan")


def _subset_line(label: str, rows: list[dict], names: list[str]) -> str:
    parts = []
    for name in names:
        errs = [np.linalg.norm(r[name][:7] - r["rec"][:7]) for r in rows]
        finger = [abs(r[name][7] - r["rec"][7]) for r in rows]
        agree = [
            (r[name][7] < CLOSE) == (r["rec"][7] < CLOSE) for r in rows
        ]
        parts.append(
            f"{name}: {_med(errs):.3f} rad / fing {_med(finger):.4f} / phase "
            f"{100.0 * float(np.mean(agree)):.0f}%"
        )
    return f"  {label:<22s} n={len(rows):3d}  " + " | ".join(parts)


def report_dataset(out, data: str, args, policies: dict) -> None:
    names = list(policies)
    store, rows = collect(data, args, policies)
    out.append(f"=== fidelity on {data}")
    out.append(f"    windows: {len(rows)} sampled of {len(store)} "
               f"(ddim={args.ddim}, seed={args.seed})")
    for name, path in zip(names, [args.base, args.candidate][: len(names)]):
        out.append(f"    {name:8s} {path or '(none)'}")
    out.append(_subset_line("overall", rows, names))
    for skill in SKILLS:
        sel = [r for r in rows if r["skill"] == skill]
        if sel:
            out.append(_subset_line(f"skill {skill}", sel, names))
    outcomes = sorted({r["success"] for r in rows})
    for value in outcomes:
        sel = [r for r in rows if r["success"] == value]
        out.append(_subset_line(f"success={value}", sel, names))
    if len(names) == 2:
        base, cand = names
        err_b = np.array([np.linalg.norm(r[base][:7] - r["rec"][:7]) for r in rows])
        err_c = np.array([np.linalg.norm(r[cand][:7] - r["rec"][:7]) for r in rows])
        delta = err_c - err_b
        better = int((delta < 0).sum())
        worse = int((delta > 0).sum())
        out.append(
            f"  paired delta ({cand} - {base}): median {_med(delta):+.4f} rad, "
            f"{better} improved / {worse} worse / {len(delta) - better - worse} ties, "
            f"sign p={sign_p(better, worse):.4f}"
        )
        fb = [abs(r[base][7] - r["rec"][7]) for r in rows]
        fc = [abs(r[cand][7] - r["rec"][7]) for r in rows]
        out.append(
            f"  paired finger median |d|: {base} {_med(fb):.4f} -> {cand} "
            f"{_med(fc):.4f}"
        )
    out.append("")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="checkpoint to measure (arm A)")
    parser.add_argument("--candidate", default="", help="optional second checkpoint (arm B)")
    parser.add_argument("--data", action="append", default=[],
                        help="window directory; repeatable (default datasets/demos_v8)")
    parser.add_argument("--windows", type=int, default=192)
    parser.add_argument("--ddim", type=int, default=16)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default="")
    parser.add_argument("--out", default="logs/rl_fidelity.txt")
    args = parser.parse_args()
    if not args.data:
        args.data = ["datasets/demos_v8"]

    device = args.device or None
    policies: dict[str, PolicyRunner] = {"base": PolicyRunner(args.base, device=device)}
    if args.candidate:
        policies["cand"] = PolicyRunner(args.candidate, device=device)

    out: list[str] = []
    for data in args.data:
        if not os.path.exists(os.path.join(data, "index.json")):
            out.append(f"=== {data}: no index.json, skipped")
            continue
        report_dataset(out, data, args, policies)

    text = "\n".join(out) + "\n"
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
