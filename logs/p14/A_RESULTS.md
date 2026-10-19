# P14-A RESULTS (2026-10-19): the canary tree-separation is NOT established - the earlier anomaly was the run-state/time artifact, not the P13's code

## The complete sample set (10 runs, two blocks)

| block | the P13 tree (a4de9cb1) | the pre/reverted tree (89000266) |
| --- | --- | --- |
| the P13 no-harm block (interleaved P13->pre; the P13 tree first in every pair) | 20 %, 20 %, 40 % | 80 %, 60 %, 70 % |
| the P14-A alternating block (P13, pre, P13, pre) | **50 %, 40 %** | **40 %, 70 %** |
| **pooled (5 each)** | {20, 20, 40, 40, 50} mean 34 % | {40, 60, 70, 70, 80} mean 64 % (excluding the raced sample 76: {40,60,70,80} mean 62.5 %, direction unchanged) |

**The verdict: not a code effect; the sample difference is NOT dissolved.** (a) Within the
new block the two pairs disagree (50 vs 40; 40 vs 70; n=2 - underpowered), but across all five
time-adjacent pairs the pre tree is higher **4/5** (sign p = 0.375, n=5); (b) **the pooled
5-vs-5 still separates**: P13 {20,20,40,40,50} mean 34 % vs pre {40,60,70,70,80} mean 64 %
(exact Mann-Whitney U = 23/25, **one-sided p = 0.0159**, two-sided p = 0.0317; robust to
dropping sample 76, one-sided p = 0.0317) - so "not established" holds for the **code
attribution**, not for the sample difference; (c) the code is proven forward-bit-identical
(the moe_v12 forward md5 equal through both model.py versions; the finetune/111 outside the
canary's import graph). **The P13-block runs were themselves interleaved** (P13 at
03:25/08:34/09:31 vs pre at 05:43/08:54/10:15; the drivers 93-98), so the separation is NOT a
time-clustering artifact; **the structural confound is that the P13 tree ran first in every
pair (never counterbalanced)**, and the recorded state candidates are sample 71 running ~5 min
after the N=5 battery (03:20 -> 03:25) vs 72 after ~2 h idle, and sample 76 overlapping the
aborted first chain's orphan sim (10:18-10:29; the deepwork INCIDENT) - neither tested.

**The instrument reading**: the hybrid canary spans **20-80 % across 10 runs** at the same
scenario/env - a high-variance instrument; **a single canary run (or a small block) cannot
adjudicate a tree difference**; the acceptance (the scripted line) remains the reliable
no-harm gate (the P13 acceptance: 9/10 + fingerprint matches + 385/385).

**The standing actions**: the precautionary revert stays (the code is inert either way; the
ev1 + the records intact; the code at e078f43); the P13 no-harm's canary item closes as an
**instrument-variance artifact** (not a code regression); any future policy-side no-harm must
budget >= 5 canary runs per side (or use a lower-variance gate - the acceptance + the direct
A/B mechanism endpoints).
