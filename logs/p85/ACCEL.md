# P85 acceleration - the P44 speed union on the shipped two-line

Parent pre-registration: `logs/p85/PREREG_ACCEL.md` (`50b02576`, pinned before
the runs). Cells: `logs/p85/{base20_s5,speed20_s5,base20_s6,speed20_s6}.log`
(+ `.stamps`), read with `logs/p85/p85_report.py --accel`. One claim per run,
`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1`, seeds 5 and 6.

## 0. Which item, and the choice's arithmetic

The flip's own numbers (P85 §1) put the **park/lock-on family** ahead in wall
terms - P84's two-line reads a 7.1-21.8 s park-gate wait and 4.19-5.04 s
lock-on, and the per-arm idle is 18-21 % of the batch span - but every lever on
it is spent: the W7-A park gate is **already default-on** (what remains is the
other arm's carry, i.e. the overlap), and W2's start gap / station widening,
W3's capture token, W6-C's prefetch (0/40 reservations) and R3's L2/L3
lead/residency are all measured negative or bit-identical. The only knob that
removes **profile** time the primitive actually spends is the P44 union
(`FRUIT_SPEED_ALL=1`: `place` 0.52, the release clock floor, `lift` 0.36), whose
two-line read was taken on the **opt-in** arm before the flip. So the cell is
the union re-priced on the now-default line.

## 1. The mechanism transfers and is exactly the profile arithmetic (E1 PASS)

| | base (C) | union (U) | delta |
| --- | --- | --- | --- |
| `place` block (mean over 20 attempts) | 3.19 s | 2.35 s | **-0.84 s** |
| `release` block | 2.35 s | 1.63 s | **-0.72 s** |
| `lift` block | 1.65 s | 1.52 s | -0.13 s |
| `s/attempt` (sim span / 20) | 9.70 s | 8.70 s | **-1.00 s** |
| sim total | 193.3 s | 174.2 s | -19.1 s |

Both seeds read **-1.00 s/attempt** and 8.70 s. The registered E1 sub-clause
(`lift` -0.2..-0.3 s) is **partially missed** at -0.13 s - the lift leg's own
span is the shortest of the three cells and the two-line schedules it behind the
other arm's segment - while the primary clause (>= 0.80 s/attempt) passes
exactly. The acquisition blocks (`prepose`/`hover`/`descent`/`close`/`grip`) are
flat (0.71/0.76→0.71/3.39→3.32/1.37/2.45→2.48), so nothing but the three named
profiles moved.

## 2. The delivered side is a branch draw, and its sign flips by seed (E2)

| seed | C | U | Δ placed | Δ window rate |
| --- | --- | --- | --- | --- |
| 5 | 16/20, 5.57 placed/min | 13/20, 5.36 | **-3** | -3.7 % |
| 6 | 10/20, 3.10 | 14/20, 4.97 | **+4** | +60.3 % |
| pooled | 26/40 | **27/40** | +1 | - |

**E2 fails at seed 5** (13 < 16 - 1) and passes at seed 6. Two readings that keep
this honest:

* the **interval** moved +3.9 % at seed 5 (10.77 -> 11.19 s) and **-37.6 %** at
  seed 6 (19.34 -> 12.07 s), i.e. the count moved *less than one interval* in
  both directions: on this line the count is a re-draw, not a lever response;
* the **pooled** count is 26/40 -> 27/40 - a wash - which is the same conclusion
  P46 reached at a fresh seed (9 -> 7) and P80 at seed 5 (16 -> 13). Three
  independent samples, three different signs: **the count is not attributable to
  the union.**

## 3. The class the union touches (E3: FAIL at seed 5, PASS at seed 6)

* seed 5: **2 new `grasped, not placed (no note)`** rows - the closed `cnp`
  class of `logs/p42/SIM_LIMIT.md` - and `force_min == 0.00 N` legs **4 -> 7**;
* seed 6: no new reason, and the zero-force legs **11 -> 8** (better);
* the held-leg slip guard is clean in all four cells (`clean_slip_max > 50 mm`:
  0 -> 0).

So the union does not create a *new* mechanism; it re-times which fruit is
presented and the closed grip class absorbs the difference (P51's finding,
reproduced on the shipped cell).

## 4. Wall (report only)

| cell | wall | wall/pick | wall/sim | placed/min wall |
| --- | --- | --- | --- | --- |
| base20_s5 | 331.4 s | 16.57 s | 1.71x | 2.90 |
| speed20_s5 | 288.9 s | 14.44 s | 1.66x | 2.70 |
| base20_s6 | 311.7 s | 15.58 s | 1.61x | 1.93 |
| speed20_s6 | 286.0 s | 14.30 s | 1.64x | 2.94 |

The union is **-12.8 % / -8.2 % wall** and **-1.1 % / +52 % placed/min wall**:
on this machine the wall follows the sim clock (the arbiter's cost per tick is
flat), so a shorter sim span is a shorter run, and whether that is a rate gain
is the count again.

## 5. Verdict

**E1 PASS (both seeds), E2 FAIL (seed 5), E3 FAIL (seed 5) -> measured, NOT
adopted.** The union's *time* is real and reproducible (-1.00 s/attempt at both
seeds, exactly the three profile cells); its *delivered* side has no stable sign
across three samples (P80 -3, P46 -2, P85 +4) and the class that moves is the one
`logs/p42/SIM_LIMIT.md` closed. No default changed. The named next step, if the
speed is ever wanted, is to argue it on the **time** with the placement cost
named as the documented class - and to take it with the two references and every
store re-recorded, which the P85 flip just showed is a full phase in itself.

## 6. Cross-references that make the cells trustworthy

* `speed20_s5` is **799/799 identical to `logs/p80/V20.log`** - the union's
  pre-flip opt-in two-line arm. The flip is resolution-only for the treatment
  arm too, not just the control.
* `base20_s5`/`base20_s6` are **865/865** and **814/814** identical to
  `logs/p80/T20`/`T6`.
* The control cells carry the phase's `[carry]` tracker; P84 proved it neutral
  on this line (`D5`/`D6` replay T20/T6 at 865/865 and 814/814 with those rows
  dropped), and the same filter is what the comparisons above use.
