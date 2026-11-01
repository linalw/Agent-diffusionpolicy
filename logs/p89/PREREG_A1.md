# P89 amendment A1 - the G0 replay targets are P88's **C5/C6**, not its T5/T6

Written 2026-11-01 ~18:47, **while the first cell (C5) was still running** and
before any P89 log was compared with anything. Pinned in
`logs/p89/PREREG_A1.md5`. This is a clause-target correction (which file the
control replays), not an outcome-dependent change: no P89 outcome had been read
when it was written, and the gate's endpoints, bands and verdict rule are
untouched.

## What was wrong

`PREREG.md` §4 G0 says *"`C5` must be byte-identical to `logs/p88/T5.log` and
`C6` to `logs/p88/T6.log`"*. That is the wrong **pair of cells**: P88's `T5`/`T6`
were that phase's **treatments** - they ran the place raise (`FRUIT_SPEED_PLACE`
unset, which resolved **0.52** on P88's battery tree; their own rows read
`FRUIT_SPEED_PLACE=0.52(default)`). P88's controls (`C5`/`C6`) are the cells that
ran the **shipped** place cap (`0.35(explicit)`), i.e. exactly the tree P89's
controls run: release trim on (its own two-line default), place cell off (its
default is off), lift cell off (`FRUIT_SPEED_LIFT=0`).

## The correction

* **G0 (corrected)**: `C5` replays `logs/p88/C5.log` and `C6` replays
  `logs/p88/C6.log` on the `[fruit]` stream with the diag rows and the three
  profile rows dropped (`logs/p89/p89_report.py --same`). Those are the
  place-0.35 cells, so a lift-only difference is the only difference the
  comparison can carry.
* **Recorded, not gated**: `C5` against `logs/p88/T5.log` (and `C6` vs `T6`)
  **must differ**, and the first difference must be a `place` leg/row - that is
  what proves the replay is sensitive to the place cell rather than a coincidence
  of a filter that hides everything. It is a diagnostic, not a clause.

## Nothing else moves

P1-P6, the admissibility of the two-line arms (the pre-P87-clock references are
recorded, the budgets are the gate), the verdict rule, the band (±0.08 s on the
block mean) and the stated expectation (a null or marginal read is the likely and
acceptable answer) all stand as pinned in `PREREG.md` (`30d8941c`).
