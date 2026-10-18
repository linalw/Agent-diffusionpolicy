# P13-B RESULTS (2026-10-19): the event-structure heads (ev1) - a positive mechanism read + a +3 outcome, awaiting the confirmatory N=5

The A/B: **the W7-B battery boundary (the env pins) on the CURRENT tree** (tasks.py 810658b8, rl_env.py 9a2c3872, trigger.py d7ec85fc, runtime.py 379ac706; the per-run manifests), N=3x15, seeds 77/101/202, policy seed 11. **W7-B's own A/B ran on e98d9836/9318fe3e/d35fba2c with its arm B an env knob (ACQ=1); here arm B is a checkpoint swap** - all readouts are within-batch only; A = `moe_v13s`,
B = `ev1` (the 6-epoch fine-tune with the event heads + the transition-weighted loss;
`checkpoints/ev1/policy_best.pt` c2656cc2). Both arms `FRUIT_ACQ_DIAG=1`.

## The endpoints (the menu #6's form)

| endpoint | A (moe_v13s) | **B (ev1)** | reading |
| --- | --- | --- | --- |
| the outcomes | 27/45 (60 %) | **30/45 (67 %)** | +3; paired 25/13/5 B-only/2 A-only; sign **p = 0.2266** (N=3 - not significant) |
| **the left close-start \|y\|** (the acquisition error) | median **178.5** mm, p90 267.7 | **median 3.5 mm, p90 5.8** | **the known left deficit class nearly eliminated** |
| the right close-start | median 4.8, p90 5.6 | median 3.4, p90 5.3 | slightly better |
| **the 200-tick catch-up chases** | **11** (4+3+4) | **2** (1+1+0) | **-82 %** - the R9-style degradation signature, here reversed |
| the re-seat markers | 0 | 0 | as expected (the class is scripted-line only; the direct interface never emits it) |
| the cycle | median 1826 ticks | median 1836 | +0.5 % (non-inferior) |
| the class cells | - | lychee 3/6 -> 6/6 (+50 %), kiwi +17 %, orange -33 %, the rest flat | the strawberry 4/6 -> 4/6 (the known hard class, unchanged) |
| **the fire-path classification** | left no-contact 12 = 11 trigger-path + 0 gate + 1 no-stamp; left carried 4 | **left no-contact 1 = 1 + 0 + 0; left carried 13** | the total no-contact 13 -> 2; the carried 5 -> 13 |
| the tails | A left max 317.7 (the reach-cliff slot = a 1500-tick timeout, no close) | **B's single 853.2 tail** (the same reach-cliff slot; W7-B's residual flail) | quote the tail, not just the median |

## The reading

**The conditioning-side movement is measured; attribution is not single-factor**: the event-structure supervision (the phase + TtT
heads, training-only; the transition-weighted loss) moved exactly the channels the W7-B/P10-D
diagnostics named as the policy's deficit - the **pre-contact acquisition** (the left
close-start 178 mm -> 3.5 mm) and the **catch-up chases** (11 -> 2) - with the outcomes +3 and
the cycle flat. The sign test is not significant at N=3 (p = 0.2266); **the menu's N=5 paired
form is the confirmatory step** (the pre-registered follow-on, unchanged endpoints).

**Caveats (the Oracle's three-way confound)**: ev1 differs from moe_v13s in the heads
(training-only; the movement is weight-mediated), the transition-weighted loss + gamma, and
the 6 extra epochs; the mechanism endpoints (the acquisition/chases) are the ones the heads
were built to move, which is supportive but not a single-factor attribution. The named
controls if the N=5 confirms: the knob-off 6-epoch re-run + the single-factor ablations.
