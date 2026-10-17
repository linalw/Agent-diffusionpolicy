# P11-C DECISION (2026-10-18): the control-side path for the ejection - and what it can and cannot fix

**Decision: implement and test the control-side fix (the re-seat arrival geometry + the
chase/ratchet stops), two-line-scoped, default-off. Do NOT change the contact physics.**

## Why (the complete evidence chain)

1. **P11-A (the audit)**: the fruit is rigid; the contact is 30 kN/m (8x a tomato); the control
   commands a sub-width keep-gap under a saturated drive; the interference's energy (0.164 J)
   is 3-27x the real bruise thresholds. The control-side and physics-side options both sketched.
2. **P11-B (the probe)**: the ejection is a **kinematic wedge of the descending jaws** - the
   commanded interference beyond the surface is NOT realized (the pads stop at the blocking
   span, extent + ~11 mm of link span; 20 mm of commanded interference gives bit-identical
   responses); the escape (0.202 m/s in the plow geometry) is **insensitive to the contact
   stiffness, the fruit-side compliance, the restitution and the substeps (+/-3 %)**; the pad
   standoff is the only lever that removes it. **Therefore the physics-side changes do not fix
   the ejection** (they remain a realism option with a full lineage re-baseline cost).
3. **P10-E (the diagnosis)**: the no-grasp class is 52.7 % of the failure count / 51.4 % of the
   mass; the B1 chain (60 % of the class) runs: the marginal close -> the failed probe -> the
   force-servo chase (F_min = 0, 15-26 mm closed) -> the re-seat at the chased (sub-width)
   gap -> the ejection (13/18 fall to the floor).

## The fix (the bounded, two-line-scoped change; all default-off)

1. **The re-seat approach geometry** (the measured lever; sharpened by the probe's groups):
   the probe shows the **close-from-open** geometry never ejects (`belt` 0/3, `air` 0/3 at every
   delta) while the **descend-at-the-contact-gap** geometry always does (`plow` 3/3 at every
   commanded gap that contacts). The fix: the re-seat must reproduce the close-from-open
   approach - approach/descend with the jaws **wider than the blocking span** (no contact on
   the descent), then close to the grip depth horizontally - e.g. a new
   `FRUIT_DYNAMIC_REGRASP_FROM_OPEN` knob (or an equivalent arrival-standoff form).
2. **Stop the chase**: `FRUIT_FORCE_REENTRY=1` (the existing knob; the contact-gated force
   mode holds the gap when the contact estimate is gone) or a cut `FRUIT_DYNAMIC_FORCE_RANGE`
   (15 mm -> ~1-2 mm), so `squeeze_gap` cannot walk sub-width before the re-seat.
3. **Cap the ratchet**: the 3 mm/cycle `FRUIT_DYNAMIC_REGRASP_STEP` ratchet adds interference
   per cycle; bound it with the arrival floor.

## The honest expectation (recorded before the battery)

* The **ejection stops** (the falls, the 1.3 m drops and the solver blowups are artifacts of
  the wedge; removing the arrival interference removes them - the probe's `-15` anchors and the
  `padm10` geometry show the no-shove states).
* The **marginal grip remains marginal**: a re-seat that does not press in cannot restore a
  lost grip - the class is expected to shift toward the B2/C slip classes and **the rate may
  not improve**. The safety/realism win (no falls, no blowups) is the primary expected outcome;
  a rate gain is a possible bonus, not the claim.
* The physics-side realism gaps (the rigid fruit, the stiff contact, the light masses) remain
  documented in P11-A and are NOT addressed here (owner-gated, full re-baseline).

## The next step

The pre-registration `logs/p11c/PREREG_REGRASP_ARRIVAL.md` (frozen before the battery): the
two-line patch battery, seed 11 primary (the hard seed) with seeds 5/23 as controls; the
mechanism endpoint = the first keep-gaps / the arrival spans (the P10-E falsifier: every B1
attempt's arrival at/above the blocking span); the outcome endpoints = the no-grasp class,
the falls, the carried class; the kills = no new reasons, the motion budgets, the no-harm
(the shipped acceptance byte-identical; the knob-off two-line pair byte-identical).
