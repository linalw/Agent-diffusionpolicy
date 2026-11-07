# P126 pre-registration - the third lane ships on the corrected evidence

**Pinned before the flip's acceptance runs.** The owner's decision is to adopt
the third output lane; P124 executed and reverted a flip because the hybrid
canary read 4/10 twice on three lanes against 8/10 on two, and P125 then showed
that reading was the canary's own spread: with the same checkpoint, **A (three
lanes) 17/30 = 56.7 %** against **C (two lanes) 11/20 = 55.0 %** - a +1.7-point
scene effect inside the loop's 5-8/10 band. The blocker P124 named is therefore
**refuted**, and the P124 rule ("the canary is the second leg") cannot carry a
decision at N=1 or N=2 for a loop that reads 55-60 % on **both** scenes.

## The decision rule (pinned)

The flip ships if **all** of:

1. **the scripted two-line acceptance** (10 attempts, the shipped scenario) reads
   **at or above the 0.60 floor** and its motion budgets are clean (no `105`
   motion failure, only a rate clause may fail);
2. **the P123 tray census stands** - the destination is the product, and P123's
   three-lane cell joined **25/25** releases to their instructed tray with 0
   mis-sorts (the lane is correct at the place point);
3. **the single-arm acceptance** stays at its standing branch (a rate-only FAIL
   is accepted - it is the tree's pre-existing single-arm branch - but no motion
   failure);
4. **the policy canary is reported, not gated**: one sample per scene with the
   same checkpoint, and the two-lane control, quoted with its N.

If (1) or (3) shows a **motion** failure, the flip is reverted and the scene is
re-examined. A count is not gated: P123/P124 measured the same branch at 7-8/10.

## The price (named, and paid in this phase)

Both two-line references and the single-arm reference are **re-recorded from
this phase's same-batch runs**, the acceptance is re-based, **every store is
re-baselined** (a store's `scene.output_lanes` names its scene: 2 entries = pre-
P126, 3 = the shipped one), and the `234`/`264`/`259`/`260` pins move.

## The read rule

**A scene flip is carried by the scripted line and the tray census; the policy
canary is reported with its N.** P124's mistake was to give a single 8/10
sample the power of a gate; P125 priced that mistake (a 196-episode store and a
fine-tune for a +1-episode point estimate).
