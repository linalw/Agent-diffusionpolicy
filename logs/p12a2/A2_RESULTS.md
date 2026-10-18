# P12-A.2 RESULTS (2026-10-18): the component decomposition - the mass is the winner (+6), the restitution is neutral, the compliance is strongly negative (-9)

Under the owner's directive; the sub-knobs (MASS/REST/COMPLIANCE) from `logs/p12a2/IMPLEMENTATION.md`
(78/78 stub + the executed identity). The anchor = the shipped two-line (the P10-C.3 flip
records / the P11-C A runs).

## The decomposition (pooled over seeds 11/5/23)

| arm | seed 11 | seed 5 | seed 23 | pooled | falls |
| --- | --- | --- | --- | --- | --- |
| A (the anchor) | 10 | 13 | 16 | 39 | 14 |
| the full batch (mass+rest+compliance) | 11 | 9 | 15 | 35 | 7 |
| **mass-only** | 11 | **17** | **17** | **45 (+6)** | 6 (rows; 5 attempts) |
| rest-only | 13 | 13 | 12 | 38 (-1, neutral) | **5** |
| compliance-only | 7 | 10 | 13 | 30 (-9) | 6 |

**The readings:**
1. **The mass carries the win**: +6 pooled (the controls +4/+1), the falls 14 -> 6 (rows;
   10 -> 5 attempts). **The mechanism is NOT identified**: the +6 is right-arm-dominated
   (+5 right / +1 left) and per class sits on the **apple (5/10 -> 10/10, the class the flip
   makes ~1 % LIGHTER)** while the **tomato (+23 % heavier) falls 4/9 -> 2/8** - a branch
   re-draw the named decomposition should separate, not a mass-resists-the-wedge mechanism.
2. **The falls reduction is GENERIC** (all three components roughly halve them: mass 6,
   rest 5, compliance 6, full 7 - rows), not compliance-specific; the compliance **destroys the
   outcomes**
   (-9): the softened fruit contact changes the marginal-grip behavior (the class re-draws
   against it) - the full batch's -4 is the compliance dragging the mass's +6.
3. **The restitution is neutral on the outcomes** (38 vs 39) **but also reduces the falls
   (14 -> 5, the fewest of any single component)** - the falls' per-component values are NOT
   additive (mass 10, rest 5, compliance 7, full 7): the components interact. A
   restitution-on base is a named alternative if the falls (safety) ever outweigh the
   outcome-neutrality (recorded, not adopted).
4. **The refinement: `FRUIT_PHYSICS_REAL_MASS=1` only** - the mass base for the next
   iterations. The compliance stays available as a falls-suppressing option for a context
   where the outcomes are not the binding metric (recorded, not adopted).
5. The severe-event/105 accounting: **the mass-only base is motion-clean at all three seeds
   (worst descents 0.118/0.112/0.110)**; **the rest-only's own 105 FAILS at seed 11** (descent
   14: 0.808 m/s + a lurch) - a named side effect of the rest component. The falls convention:
   the `lowest payload point` rows -1..-20 m (blowups excluded); **one fallen payload can emit
   TWO rows** (the lift + the following place leg), so the anchor's 14 rows = 10 attempts.

## The next steps

* **P12-B.1 (the compound)**: the mass base + the from-open arrival (the two measured
  mechanism wins - the mass's +6 and the arrival's falls/intervals) - the battery queued.
* **P12-B.2 (the scene-side)**: the P11-C's named remaining path (a pick-station / approach
  geometry that never needs the descend-onto-the-fruit re-seat) - the owner's directive
  sanctions scene changes; a Tier-C scoping lane launched.

## P12-B.1 (the compound: the mass base + the from-open) - negative interaction

| seed | the anchor | the mass-only | the from-open alone | **the compound** |
| --- | --- | --- | --- | --- |
| 11 | 10 | 11 | 13 | 10 |
| 5 | 13 | **17** | 10 | 15 |
| 23 | 16 | **17** | 12 | 10 |
| pooled | 39 | **45** | 35 | **35** |

**The compound loses the mass's gain** (45 -> 35; the seed-23 branch collapses 17 -> 10 with 6
falls; the compound's own falls are 11 rows, tabulated here for the record): the from-open arrival's class disturbance (the P11-C reading) outweighs its falls
benefit on the heavier-fruit base. **The verdict: the mass-only base stands; the from-open is
not additive on it.** The named next: the scene-side (P12-B.2, `logs/p12b/SCENE_OPTIONS.md`).
