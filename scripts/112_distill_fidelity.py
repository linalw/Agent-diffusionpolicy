"""Offline fidelity of a distilled consistency student vs its DDIM-16 teacher.

No simulator. The teacher (`checkpoints/moe_v10`) runs its shipped DDIM-16; the
student runs the same stock DDIM chain with 1/2/4 steps (which is the k-step
consistency sampler, `distill.py`). Both sample on identical held-out windows
with identical per-window noise seeds, so every comparison is paired.

Metrics (the ones the P4/B1 diagnosis used):

* per-chunk **first-action error**: ``||pred[0, :7] - rec[0, :7]||`` against the
  recorded command (rad; the teacher reads ~0.083 rad);
* per-skill and per-category versions of the same, plus the full-chunk mean;
* the finger channel: median ``|pred[0, 7] - rec[0, 7]|`` and the open/close
  phase agreement (``< 0.030`` is "closing");
* student-vs-teacher: the paired first-action deviation on the same windows.

Held-out means the `val_episodes` split recorded by `scripts/111_distill_policy.py`
in the candidate's `history.json`: no training window from those episodes was
ever seen. With ``--history`` missing, all episodes are used (teacher-only runs).

    python3 scripts/112_distill_fidelity.py \
        --teacher checkpoints/moe_v10/policy_best.pt \
        --candidate checkpoints/distill_v1/policy_best.pt \
        --data datasets/demos_v9 --windows 192 --steps 1,2,4 \
        --out logs/distill/112_fidelity.txt
"""

from __future__ import annotations

import argparse
import json
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


def sign_p(better: int, worse: int) -> float:
    """One-sided binomial p = P(X >= better), X ~ Bin(better + worse, 0.5)."""
    n = better + worse
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(better, n + 1)) / (2.0 ** n)


def sample_action(policy: PolicyRunner, obs: dict, seed: int, steps: int) -> np.ndarray:
    """One sample for this window with a fixed noise seed (paired across arms)."""
    policy.reset()
    policy.generator = torch.Generator(device=policy.device).manual_seed(int(seed))
    policy._frames = [
        np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])
    ]
    return policy.act(obs["proprio"], obs["goal"], num_steps=int(steps))


def med(values) -> float:
    return float(np.median(values)) if len(values) else float("nan")


def load_val_episodes(history_path: str, episodes: int | None) -> list[int] | None:
    """The recorded held-out episodes, or None when the history has no split.

    `episodes` is only the fallback episode count (``None`` = the caller does
    not have it yet and must build the store to learn it); the demos_v10 store
    is ~59 GB, so the split is never probed redundantly when the history
    already carries `val_episodes`.
    """
    if history_path and os.path.exists(history_path):
        with open(history_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        data = payload.get("data", payload)
        values = data.get("val_episodes")
        if values:
            return [int(v) for v in values]
    if episodes is None:
        return None
    return list(range(episodes))


def collect(data: str, args, policies: dict, val_episodes: list[int]) -> tuple:
    store = EpisodeStore(data, obs_horizon=2, action_horizon=16, image_size=128,
                         only_successful=True)
    val_set = set(int(v) for v in val_episodes)
    candidates = [
        i for i, (ep, _start) in enumerate(store.windows) if ep in val_set
    ]
    if not candidates:
        raise SystemExit(f"no windows in val episodes {sorted(val_set)}")
    rng = np.random.RandomState(int(args.seed))
    count = min(int(args.windows), len(candidates))
    indices = np.sort(rng.choice(np.asarray(candidates), count, replace=False))
    rows = []
    for i in indices:
        obs = store[int(i)]
        ep, _t = store.windows[int(i)]
        meta = store.episodes[ep]["meta"]
        row = {
            "skill": SKILLS[int(obs["skill"])],
            "category": str(meta.get("category", "")),
            "rec": np.asarray(obs["action"], dtype=np.float64),
        }
        for name, (policy, steps) in policies.items():
            seed = int(args.seed) * 100003 + int(i)
            row[name] = np.asarray(
                sample_action(policy, obs, seed, steps), dtype=np.float64
            )  # (horizon, action_dim), the EpisodeStore orientation
        rows.append(row)
    return store, rows


def _arm_metrics(rows: list[dict], name: str) -> dict:
    first = [np.linalg.norm(r[name][0, :7] - r["rec"][0, :7]) for r in rows]
    chunk = [
        float(np.mean([np.linalg.norm(r[name][t, :7] - r["rec"][t, :7])
                       for t in range(r["rec"].shape[0])]))
        for r in rows
    ]
    finger = [abs(r[name][0, 7] - r["rec"][0, 7]) for r in rows]
    phase = [
        (r[name][0, 7] < CLOSE) == (r["rec"][0, 7] < CLOSE) for r in rows
    ]
    return {
        "name": name,
        "first": med(first),
        "chunk": med(chunk),
        "finger": med(finger),
        "phase": 100.0 * float(np.mean(phase)) if phase else float("nan"),
        "n": len(rows),
    }


def _line(label: str, rows: list[dict], names: list[str]) -> str:
    parts = []
    for name in names:
        m = _arm_metrics(rows, name)
        parts.append(
            f"{name}: {m['first']:.3f}/{m['chunk']:.3f} rad, "
            f"fing {m['finger']:.4f}, phase {m['phase']:.0f}%"
        )
    return f"  {label:<20s} n={len(rows):3d}  " + " | ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teacher", default="checkpoints/moe_v10/policy_best.pt")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--data", action="append", default=[],
                        help="window directory; repeatable (default datasets/demos_v9)")
    parser.add_argument("--history", default="",
                        help="history.json with val_episodes (default: candidate dir)")
    parser.add_argument("--windows", type=int, default=192)
    parser.add_argument("--teacher-steps", type=int, default=16)
    parser.add_argument("--steps", default="1,2,4")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default="")
    parser.add_argument("--out", default="logs/distill/112_fidelity.txt")
    args = parser.parse_args()
    if not args.data:
        args.data = ["datasets/demos_v9"]
    student_steps = [int(v) for v in str(args.steps).split(",") if v.strip()]

    device = args.device or None
    policies: dict[str, tuple[PolicyRunner, int]] = {
        "teacher": (PolicyRunner(args.teacher, device=device), int(args.teacher_steps)),
    }
    for steps in student_steps:
        policies[f"student{steps}"] = (
            PolicyRunner(args.candidate, device=device), steps,
        )
    names = list(policies)

    out_lines: list[str] = [
        f"teacher {args.teacher} (DDIM-{args.teacher_steps})",
        f"student {args.candidate} (DDIM-{','.join(str(s) for s in student_steps)})",
        "paired windows, fixed per-window noise seed; first/chunk = 7-D arm error in",
        "rad against the recorded command; phase = open/close agreement at < 0.030",
        "",
    ]
    for data in args.data:
        if not os.path.exists(os.path.join(data, "index.json")):
            out_lines.append(f"=== {data}: no index.json, skipped")
            continue
        history = args.history or os.path.join(os.path.dirname(args.candidate),
                                               "history.json")
        val_episodes = load_val_episodes(history, None)
        if val_episodes is None:
            # No recorded split: fall back to every episode. The store is built
            # only here (and rebuilt once by `collect`); with demos_v10's ~59 GB
            # it must not be held twice in one process.
            store_probe = EpisodeStore(data, obs_horizon=2, action_horizon=16,
                                       image_size=128, only_successful=True)
            val_episodes = list(range(len(store_probe.episodes)))
            del store_probe
        store, rows = collect(data, args, policies, val_episodes)
        out_lines.append(f"=== fidelity on {data}")
        out_lines.append(
            f"    held-out episodes: {len(val_episodes)}/{len(store.episodes)} "
            f"({','.join(str(v) for v in val_episodes)})"
        )
        out_lines.append(
            f"    windows: {len(rows)} sampled of {len(store)} "
            f"(seed={args.seed}, split from {history if os.path.exists(history) else 'none'})"
        )
        out_lines.append(_line("overall", rows, names))
        for skill in SKILLS:
            sel = [r for r in rows if r["skill"] == skill]
            if sel:
                out_lines.append(_line(f"skill {skill}", sel, names))
        categories = sorted({r["category"] for r in rows})
        for category in categories:
            sel = [r for r in rows if r["category"] == category]
            if sel:
                out_lines.append(_line(f"fruit {category}", sel, names))
        for name in names[1:]:
            delta = np.asarray(
                [np.linalg.norm(r[name][0, :7] - r["rec"][0, :7])
                 - np.linalg.norm(r["teacher"][0, :7] - r["rec"][0, :7]) for r in rows]
            )
            better = int((delta < 0).sum())
            worse = int((delta > 0).sum())
            dev = [
                np.linalg.norm(r[name][0, :7] - r["teacher"][0, :7]) for r in rows
            ]
            out_lines.append(
                f"  {name} vs teacher: first-action deviation median {med(dev):.4f} rad; "
                f"paired vs teacher error {better} better / {worse} worse "
                f"(median {med(delta):+.4f}, sign p={sign_p(better, worse):.4f})"
            )
        out_lines.append("")

    text = "\n".join(out_lines) + "\n"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
