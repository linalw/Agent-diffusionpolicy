#!/usr/bin/env python3
"""P28-D: the counterfactual-channel read on the trained spd_v1 (the Oracle's inertness kill).

Loads the fine-tuned 26-D model and evaluates the SAME inputs with the speed column at the
normalised values of 0.08/0.12/0.15 (the fixed (0.12, 0.05) normaliser). A model that learned no
speed dependence returns bit-identical outputs (the step-0 behaviour); a learned dependence shows
a delta. The synthetic batch is deterministic (seed 1000).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import torch
from fruit_sorting.policy.model import ConditionalUNet1D  # noqa: E402

ck = torch.load("checkpoints/spd_v1/policy_best.pt", map_location="cpu", weights_only=False)
cfg, norm = ck["config"], ck["normalizer"]
model = ConditionalUNet1D(
    action_dim=9, image_channels=5, obs_horizon=2, goal_dim=8,
    proprio_dim=cfg["proprio_dim"],
).eval()
model.load_state_dict(ck["model"])
print("config:", {k: cfg[k] for k in ("proprio_dim", "goal_dim", "action_dim")})

g = torch.Generator().manual_seed(1000)
B = 32
goal = torch.randn(B, 8, generator=g)
p25 = torch.randn(B, 25, generator=g)
img = torch.randn(B, 2, 5, 128, 128, generator=g) * 0.1
sample = torch.randn(B, 9, 16, generator=g)
steps = torch.randint(0, 100, (B,), generator=g)

mean, std = 0.12, 0.05
outs = {}
with torch.no_grad():
    for raw in (0.08, 0.12, 0.15):
        z = (raw - mean) / std
        p26 = torch.cat([p25, torch.full((B, 1), z)], dim=-1)
        outs[raw] = model(sample, img, goal, p26, steps)
for a in (0.08, 0.15):
    d = outs[a] - outs[0.12]
    print(f"0.12 -> {a}: max|delta| = {float(d.abs().max()):.4e}  mean|delta| = {float(d.abs().mean()):.4e}")
