# P28-E results: the speed-aware vs blind A/B (2026-10-21)

## 1. The first pass (TRIGGER=off) - the interface autonomy gap

All six cells (A/B x 0.08/0.12/0.15) read **0/15** with 'timeout: no grasp' / 'policy closed on the
fruit' / 'fruit fell off the line': with the scripted arrival trigger disabled the learned close
gate almost never fires (the Gate-A census: 2/60) - **the model's own close is not a viable fire
path**. Recorded `logs/p28/E_TRIGGER_OFF.md`.

## 2. The re-scoped pass (TRIGGER=arrival + the ACQ env; both fire paths present)

| speed | arm | ok | nc | carried | close-start \|y\| p50 |
| --- | --- | --- | --- | --- | --- |
| 0.12 (anchor) | A blind 25-D | 4/15 | 2 | 9 | 4.0 mm |
| 0.12 (anchor) | B speed-aware 26-D | 3/15 | 0 | 12 | **3.7 mm** |
| 0.08 | A | 7/15 | 0 | 8 | 4.1 mm |
| 0.08 | B | 7/15 | 2 | 6 | **3.6 mm** |
| 0.15 | A | 5/15 | 1 | 9 | 2.8 mm |
| 0.15 | B | **8/15** | 0 | 7 | **2.4 mm** |
| pooled | A | 16/45 | 3 | 26 | - |
| pooled | B | **18/45** | 2 | 25 | - |

**The mechanism moves and it moves in the channel's direction: the speed-aware arm closes
0.3-0.5 mm tighter at EVERY speed** (3.7/3.6/2.4 vs 4.0/4.1/2.8) - the fine-tune learned to use the
speed scalar. **The outcome**: the fast end (0.15, outside the training speeds) reads **+3** (8 vs
5), the in-distribution anchor -1 (within the ~15 pt MDE at N=1x15), the slow end 0. Pooled +2
(18 vs 16 of 45). **The carried-not-placed class still dominates every cell** (6-12/15) - the P27
audit's hand-frame-escape mechanism, untouched by the speed.

**Read**: a screen, not a verdict (N=1x15 per cell; the MDE ~15 pt). The promising cell is the
**fast end** - the premise's shape ("faster may fail, slower holds") is why the channel matters
where the distribution ends; the full battery at 0.15 (and the 0.12 anchor's non-inferiority at
the B4 margin) is the deciding spend.

## 3. Provenance

* The v3 runs: `logs/p28e/spd{012,008,015}_n1v3/{A,B}_1.log` (the chain
  `logs/p28/run_ab_speed3.sh`, the driver `96_driver_ab4.log`); the trigger-off cells
  `logs/p28e/spd*_n1/` (moved under `_stale/` where superseded) + `E_TRIGGER_OFF.md`.
* The model: `checkpoints/spd_v1/policy_best.pt` (the widen 25->26; the counterfactual read
  `logs/p29/counterfactual_speed.py`: 0.12->0.08 max|delta| 2.42e-2, ->0.15 1.81e-2).
* The baseline: `checkpoints/moe_v13s/policy_best.pt` (the 25-D blind arm).
