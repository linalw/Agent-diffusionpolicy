# P88 PREREG amendment A1 - P1b's command-peak clause, corrected before T5 ran

**Written 2026-11-01 17:34, before the first treatment cell (T5) started** (C5,
the seed-5 control, was still running; `logs/p88/battery_driver.log`'s T5
`START` line is later than this file's mtime). Pinned as
`logs/p88/PREREG_A1.md`; `PREREG.md` itself is unchanged (`31e40b60...`).

## What was wrong

`PREREG.md` §3 P1b said "the commanded peak `|v|cmd` on each treatment
`place0/1` transit is **>= 0.48 m/s** (control 0.34-0.36)". That is only true on
the **long** legs. The profile's peak is `1.875 * d / T` and `T` is the largest
of three terms, so:

* a long leg (v-limited, `d >= 0.408 m` at 0.52) cruises at 0.51-0.52;
* a short leg is **acceleration-limited** (0.30 m -> peak 0.44) or even
  **jerk-limited** (0.14 m -> peak 0.28, and at that distance the raised cap
  changes nothing at all, because the jerk term binds at both caps).

The shipped record contains legs at 0.14-0.62 m (`PREREG` §1), so "every leg
>= 0.48" would fail on a cell that worked perfectly. The error is in the
clause's arithmetic, not in the cell or the prediction.

## The corrected clause (replaces PREREG §3 P1b verbatim)

**P1b - the cell materialised on every treatment place leg.** With the leg's own
printed distance `d` (`[motion] carry placeX: NN cm`) and the raised cap:

* **(i) ticks.** `place_ticks(d; 0.52, 1.089)` from `motion.jerk_limited` (the
  leg's own generator) agrees with the printed tick count to a **median of
  <= 3 ticks** over the treatment legs (the printed centimetre quantises `d`;
  the same read at the shipped cap reproduces the control to <= 2 ticks, §1).
* **(ii) peak.** `|v|cmd` equals `1.875 * d / (ticks/120)` - the profile's own
  peak for that leg - to **<= 0.02 m/s** on every treatment leg, and the
  **median** treatment leg's `|v|cmd` is **>= 0.48 m/s** (the median leg is
  long, so the cell is demonstrably cruising at the raised cap; the short legs
  are then explained by the profile, not excused).
* **(iii) contrast.** On every treatment leg whose raised prediction is
  `>= 0.45 m/s`, the measured `|v|cmd` is `>= 0.45` (control: 0.34-0.36 on the
  same legs).

## Why this does not weaken the gate

The mechanism claim is unchanged: a treatment cell that failed to reach the cap
would show the control's 0.34-0.36 on its long legs and its tick count would
match the shipped profile, not the raised one. The corrected clause is
*stricter* than the original on the legs where the original was meaningful
(it now also checks the per-leg equality in both regimes), and it is
implementable on the short legs the scenario actually contains.

## Reported, not gated

The per-regime table (long / acceleration-limited / jerk-limited) with each
leg's `d`, printed ticks, predicted ticks at both caps and `|v|cmd` - so the
reader can see which regime each leg was in.
