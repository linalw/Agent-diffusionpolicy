# P18-B.1 PRE-REGISTRATION (frozen 2026-10-19): the class-matched L3 re-run (single-species supply)

**Why.** The v2 stage-N battery (`logs/p18b/B_RESULTS.md`) read A 22/75 (29 %) vs B 39/74 (53 %)
raw, but the pre-registered paired endpoint did not resolve: 58/74 episodes had no pair because
the two arms' fruit streams diverge (the presentation is behavior-dependent), and the class mix
differed by arm. The class-standardized deltas were positive on 6/8 classes (tomato +56 %,
strawberry +42 %, apple +28 %; lychee -25 % at n=8/8). This re-run holds the class fixed by
construction.

**Design.** `FRUIT_SUPPLY_SPECIES=tomato` (the P1c tool, default off; restricts the pool to one
species) + the rest of the stage-N env byte-identical to the v2 battery; the same two arms (A =
`moe_v13s`, B = `moe_v13s` + `FRUIT_CLOSE_LOAD_RATE=0.04`), N = 5 runs x 15 episodes, seeds
[77,101,202,303,404], sampler seed 11, interleaved A,B; the precondition check after A run 1
(`check_preconditions.py`: trigger.mode=arrival, acq=True, `[carry]` > 0, "intercept trigger"
notes; the rate floor 4/15).

**The endpoint.** The paired sign test on the episode pairs (now complete by construction: the
class always matches) at p <= 0.05 one-sided (a 6-0 discordant split is the N=5 edge) **and** the
pooled rate not below the control's **and** no new failure reason. Reported alongside: the
class-confusion matrix (the per-episode outcome pairs), the cycle, the interval.

**Kills.** K3-style double not applicable (the direct loop is frame-conditioned; N=5 per arm is
the sample); a run wedge (the known renderer freeze) is discarded and re-run once; a precondition
failure voids the battery; a broken claim or a concurrent simulator run voids the block.

**The interpretation rule.** A pass is **not adoption** (the shipped default stays; adoption needs
the no-harm + the flip check). A fail closes the C1 on the direct interface; the pooled v2 delta
is then attributed to the mix.

**Pins.** `checkpoints/moe_v13s/policy_best.pt` `61da390a`; `tasks.py` `3d88408d`; the manifests
per run under `logs/p18b/N5_tomato/raw/`.
