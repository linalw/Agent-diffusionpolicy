# P125 amendment A2 - a same-batch two-lane control, **report only**

Pinned 2026-11-07 13:12, **after** the three-lane A/B's first four samples and
**before** the two cells it governs. It does not touch the verdict.

## Why

The registered A/B is same-scene (three lanes, A = `moe_v12` vs B =
`p125_three_lane`). By sample four the pooled rates are A 12/20 and B 12/20,
and **P1 is already unreachable** (B's ceiling is 22/30 = 73.3 % < 24/30), so
the flip will not happen. But the negative has two very different readings:

1. the recollection did not remove the three-lane input cost (60 % on three
   lanes against the P124 two-lane 8/10), or
2. **this batch's loop is at ~60 % on any scene**, and P124's single 8/10
   two-lane sample was the top of the recorded 5-8/10 spread (the canary is a
   sample, not a rate).

P124 has **one** two-lane sample (8/10). A same-batch two-lane cell separates
the two readings without touching the registered verdict.

## The cell

* **two samples**, `FRUIT_OUTPUT_LANES=2 FRUIT_CKPT=checkpoints/moe_v12/policy_best.pt`
  - the pre-P125 **pairing** (scene + checkpoint), i.e. exactly what the
  two-lane control is;
* the same evaluator defaults as the A/B (`FRUIT_SUPPLY_SCATTER=0`, camera
  240,424, `SEED=77`, 10 episodes); logs `logs/p125/canary_C_{1,2}.log`;
* **report only**: it cannot change P1/P2/P3, the verdict, or the flip. It is
  read beside the A/B and quoted with its per-sample rates and classes.

No other clause moves; `PREREG.md` sections 1-4 and `PREREG_A1.md` stand.
