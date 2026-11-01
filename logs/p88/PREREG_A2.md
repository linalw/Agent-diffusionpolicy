# P88 PREREG amendment A2 - G1's fingerprint clause, corrected after the gate ran

**Written 2026-11-01 18:17, after the four cells and before the final
`accept.sh`.** Pinned as `logs/p88/PREREG_A2.md`. The four cells are unaffected
and no verdict changes on this: the gate already fails on P1a (seed 5), P2 (both
seeds) and P4a (seed 5); A2 is about an **admissibility** clause, not a verdict
clause.

## What was wrong

`PREREG.md` §4 G1 said `190` on **C5/C6** "against the same seed's 20-attempt
two-line reference must **PASS** (they are the shipped clock)". That is wrong on
this tree, and P87's own evidence says so:

* the seed-5 20-attempt reference (`logs/p80/motion_reference_twoline_p80_20.json`,
  from P80's `T20`) and the seed-6 one
  (`logs/p86/motion_reference_twoline_C6_20.json`, from P86's `C6`) were both
  recorded on the **pre-P87 release clock** (20/3/3);
* P88's cells all run the **shipped post-P87 clock** (the release trim is the
  two-line default and was left unset on all four cells), and the trim re-times
  every attempt boundary - which is precisely why P87's **T5/T6** DIFFERED from
  these same files while P87's **C5/C6** (`FRUIT_SPEED_RELEASE=0`, the old
  clock) PASSED.

So no post-P87 20-attempt run of this scenario can match those files, and
"the controls must PASS the fingerprint" is unsatisfiable by construction. The
gate run confirms it: C5 and C6 both read `fingerprint: DIFFERS ... different
attractor`, with the leg-level differences on **duration only** (leg 5 `[89,
0.109]` vs `[88, 0.11]`, etc.) - P86 §3's own signature of a re-timed clock.

## The corrected G1

* **G0 remains the control's identity proof** (it is stronger than a
  fingerprint): C5 and C6 are **byte-identical to P87's T5/T6** on the `[fruit]`
  stream (868/868 and 821/821), so the control *is* the shipped behaviour on a
  record made on a different tree, and the place cell is the only difference
  between a control and its treatment.
* **`190` is recorded for every cell and its fingerprint read is reported, never
  gated**: all four DIFFER from the pre-P87 20-attempt files, C5/C6 by the
  clock (A2) and T5/T6 by the clock *and* the place cell.
* **The substance is the motion budget**, which is P6's clause: `105
  --min-success-rate 0.0` on all four cells, judged per leg by `105`'s own
  parser and budget. Measured: **C5 0/20, T5 0/20, C6 1/20** (leg 12, 5.9 cm,
  0.164 vs 0.160 - the same seed-6 leg P86's `R6` and P87's `T6` recorded),
  **T6 0/20**. P6's registered tiering therefore reads **clean for the cell**
  (both treatments 0 legs over); the control's single leg is that branch's
  known property.

## Why this is not a loosened gate

The corrected form is stricter where it matters: it removes a fingerprint
comparison that a trim-clocked run could never satisfy (a false failure), and it
keeps the per-leg speed/lurch budget as a hard check on every leg of every cell.
`105`'s exit code is still recorded per cell, and the one over-budget leg is
named as a leg, not averaged away.
