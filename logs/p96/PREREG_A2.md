# PREREG A2 - the control cells' admissibility reference is the **post-P94** record

Pinned while the battery was still running and **before any analysis**.
`logs/p96/PREREG.md` (`bb057405aa020378739b4b8e21f5cdcb`) and `PREREG_A1.md`
(`a2e63f604ef479afaaa4f7516e3bff5f`) are unchanged; this amendment corrects one
**reference name** in PREREG §4/§5-G0 and moves no criterion, no cell, no guard.

## What was wrong

PREREG §4 named `logs/p92/{C5,C6}.log` as the control cells' replay target. Those
records are **pre-P94**: P94 shipped the `_gripper_offset` command bound
(`FRUIT_CARRY_OFFSET_MAX`, default 0.20 m) *after* P92 ran, and it changes a carry
leg's issued target on exactly the legs whose offset reading exceeds the bound.
Measured on the live `C5` cell (`logs/p96/C5.log`, the first 10 attempts, 443
`[fruit]` lines with the phase's own `[ftrace]` arming row and diag rows dropped
by the P84/P85 sealed filter):

```
common prefix 108 of 872 (p92/C5) vs 443 (p96/C5)
  p92/C5 : [fruit] [motion] carry grasp_lift: 22 cm, 169 ticks, ... slip_max=112673.2 mm,
           in-hand |v|max=13270.608 m/s, recoveries=0: steps=170, |v|max=1.108
  p96/C5 : [fruit] [motion] carry grasp_lift: 22 cm, 169 ticks, ... slip_max=112645.2 mm,
           in-hand |v|max=13270.483 m/s, recoveries=0: steps=170, |v|max=0.270
```

That is **P94's own guarded row** (`|v|max` 1.108 -> 0.270, the 350 mm-offset leg
of P94 §1), i.e. the divergence is the shipped guard, not this phase.

## The correction

The control cells are gated against **`logs/p94/{T5,T6}.log`** - the post-P94
record of the *same* scenario and seeds, and the record P95 itself used
(`logs/p95/RESULTS.md` §0: `F6` 970/970 and `A5` 974/974 against
`logs/p94/T6`/`T5`). Against that reference the live `C5` cell is **identical on
every line it has printed so far** (448/448 `[fruit]` lines at the time of this
pin, the run still in flight), which is the admissibility PREREG §4 asks for.

Everything else stands: the four cells, the instrumentation, the criteria, the
guards G1-G7 and the decision rule. `pg_census.py` and `p96_report.py` carry the
corrected `record` column.
