# P120 pre-registration - the 60 N jaw: a replication at two fresh seeds

**Written and md5-pinned at 06:46Z, 2026-11-06, after the four-seed screen
(seeds 5/6/101/202) was read and while the replication cells (303/404, 20
attempts each, treatment 60 N and its own same-seed control) are running.** It
is therefore a **replication**, not a blind pre-registration - the first four
seeds' counts are known, and that is stated rather than hidden.

## What the screen read (4 seeds, 20 attempts each)

| seed | control (10 N) | treatment (60 N) | delta |
| --- | --- | --- | --- |
| 5 | 16/20 | 18/20 | +2 |
| 6 | 12/20 | 15/20 | +3 |
| 101 | 15/20 | 14/20 | -1 |
| 202 | 15/20 | 19/20 | +4 |
| pooled | **58/80 = 72.5 %** | **66/80 = 82.5 %** | **+10.0 pts**, Fisher **p = 0.1846** |

The escape census (carry legs with `clean_slip_max > 100 mm`) falls **22 -> 12
legs**, and the pooled interval **11.34 -> 10.63 s** (-6.3 %), both in the
treatment's favour; the class is **not deleted** (12 legs still escape, one
landing miss at seed 101 - `final=(0.472, +0.803, 1.199)`, `on_belt=False`,
`roll=-15 / skid=-215 mm`). The `dnf` note count is not the failure count (a
failure can log several notes); the placed count is the number.

## The replication's decision rule (pinned before the cells finish)

Cells: `SEED=303` and `SEED=404`, 20 attempts each, the **treatment**
(`FRUIT_FINGER_MAXFORCE=60`) and its **own same-seed control** (unset), the
shipped scripted two-line, `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1`.

The direction is **credible** only if **both** hold:

1. **the two new seeds are not both negative** (each delta > 0, or one > 0 and
   one = 0); and
2. the **pooled six-seed** Fisher exact p <= **0.10** (treatment vs control,
   placed out of 120).

Otherwise the effect is a **branch draw** and the 60 N jaw is **not adopted**.

## The guards (read on all six seeds)

* **Crush**: `sep@loss - dia >= -15 mm` on every carry leg where the payload is
  present at the loss. The 60 N cells print `sep@loss=n/a` when the payload
  never leaves, so the readable subset is reported; P76's own 60 N strawberry
  row (`sep@loss - dia = +0.5 mm` at a 36.1 mm span) is the precedent.
* **Landing**: `FRUIT_PLACE_TRACE` `on_belt` on every payload-present release;
  the `release_bottom = -184 mm` rows are the upstream-lost class, reported
  separately.
* **Descent budgets** (not re-tuned) and the **no-harm acceptance** with the
  knob unset (8/10 + `fingerprint: matches` + `190: PASS`).

## The price if it is adopted (named, not executed)

A jaw that delivers **60 N per joint** (hardware; the sim's `[drive]` readback
confirms 60.00 N), **both motion references re-recorded**, the acceptance
re-baselined, **every store** re-baselined, and the bruise question answered on
a real jaw (this sim has no bruise model, so a clean sim is geometry and
retention only).
