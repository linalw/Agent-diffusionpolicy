# P14-A RESULTS (2026-10-19): the canary tree-separation is NOT established - the earlier anomaly was the run-state/time artifact, not the P13's code

## The complete sample set (10 runs, two blocks)

| block | the P13 tree (a4de9cb1) | the pre/reverted tree (89000266) |
| --- | --- | --- |
| the P13 no-harm block (sequential, the P13 first) | 20 %, 20 %, 40 % | 80 %, 60 %, 70 % |
| the P14-A alternating block (P13, pre, P13, pre) | **50 %, 40 %** | **40 %, 70 %** |
| **pooled (5 each)** | {20, 20, 40, 40, 50} mean 34 % | {40, 60, 70, 70, 80} mean 64 % |

**The verdict: not established.** (a) The alternating pairs disagree in direction (pair 1
P13 50 vs pre 40; pair 2 P13 40 vs pre 70) - the time-adjacent comparison shows no consistent
tree effect; (b) the pooled ranges overlap (the P13's 40-50 vs the pre's 40); (c) the code is
proven forward-bit-identical (the moe_v12 forward md5 equal through both model.py versions;
the finetune/111 outside the canary's import graph). The earlier 3-vs-3 "20-40 % vs 60-80 %"
separation was (at least partly) the run-state/time ordering - the P13's runs clustered in
one period, the pre's in another.

**The instrument reading**: the hybrid canary spans **20-80 % across 10 runs** at the same
scenario/env - a high-variance instrument; **a single canary run (or a small block) cannot
adjudicate a tree difference**; the acceptance (the scripted line) remains the reliable
no-harm gate (the P13 acceptance: 9/10 + fingerprint matches + 385/385).

**The standing actions**: the precautionary revert stays (the code is inert either way; the
ev1 + the records intact; the code at e078f43); the P13 no-harm's canary item closes as an
**instrument-variance artifact** (not a code regression); any future policy-side no-harm must
budget >= 5 canary runs per side (or use a lower-variance gate - the acceptance + the direct
A/B mechanism endpoints).
