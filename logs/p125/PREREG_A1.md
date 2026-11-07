# P125 amendment A1 - the flip ships the **pair** (scene 3 + the recollected checkpoint)

Pinned 2026-11-07 **before the first canary sample of this batch** (P124's two
three-lane samples are prior context and were not run by this driver). It
amends `PREREG.md` section 5 only; sections 1-4 - the store protocol, the
fine-tune recipe, the A/B design and the P1/P2/P3 verdict - are untouched, and
the amendment cannot move the verdict.

## Why

`PREREG.md` section 5 wrote that `scripts/accept_policy.sh` would keep
`moe_v12` "unless a separate decision moves it". That is **incoherent with the
bar this phase measures**: the bar is arm **B** (`checkpoints/p125_three_lane`)
on the three-lane scene, and the failure P124 reverted was the **interface of
record** - the canary's default checkpoint on the shipped scene - reading 4/10.
A scene-only flip would ship a default pairing whose canary still reads 4/10,
i.e. the same regression P124 refused, just labelled differently.

The owner's decision (the brief) is "recollect the policy on the three-lane
scene **so the third destination can ship**". The recollection is the point;
shipping the scene without it is the incoherent half. So the flip ships the
**pair**.

## What the amendment changes

* `scripts/accept_policy.sh`'s default checkpoint becomes
  `checkpoints/p125_three_lane/policy_best.pt` (still overridable with
  `FRUIT_CKPT=...`; the header names the restore);
* the **2-lane restore** becomes a named pair:
  `FRUIT_OUTPUT_LANES=2 FRUIT_CKPT=checkpoints/moe_v12/policy_best.pt`
  (the pre-P125 scene **and** its checkpoint);
* the canary floor stays **0.60**, the failure-reason baseline stays
  `logs/336_hybrid_v3all.log`, and nothing else in the evaluator moves.

## What it does not change

* the A/B: both arms still run the **same** three-lane scene, the same
  evaluator defaults and `SEED=77`, interleaved `A B A B A B`, N=3 per arm;
* the verdict: pooled B >= 24/30, pooled B > pooled A, no unexpected reason in
  B, N=3 per arm;
* the post-flip no-harm: arm B's three samples **are** the deployed pair's
  samples, so the shipped `accept_policy.sh` is gated by the same numbers.

If the verdict is DO NOT FLIP, this amendment is moot: the scene stays at 2 and
`accept_policy.sh` keeps `moe_v12`.
