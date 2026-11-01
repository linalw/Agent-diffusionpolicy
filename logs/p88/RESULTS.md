# P88 - the place raise: the mechanism is exact, the delivery is not improved, so the cell stays off

Measured 2026-11-01. **Nothing adopted, no default changed** - `FRUIT_SPEED_PLACE`
stays an **off-by-default** cell (P44's S1); the phase's gate **failed**, so
`PLACE_TWO_LINE_DEFAULT` is `False` and the shipped tree resolves the 0.35 cap on
**every** path. What the phase ships is the **instrument**: one resolver
(`tasks.place_speed_resolution`), the `[biarm] place profile:` row, the
`physics.place` manifest block, the `248` selfcheck leg, and the measured arm
reproducible as `FRUIT_SPEED_PLACE=0.52`.

PREREG `logs/p88/PREREG.md` (**`31e40b60...`**) + amendment
`logs/p88/PREREG_A1.md` (**`2331d706...`**, pinned 17:34, before the first
treatment cell ran: P1b's command-peak clause was corrected for the
acceleration/jerk-limited short legs). Cells `logs/p88/{C5,T5,C6,T6}.{log,stamps,
driver}` (one claim each, `logs/p88/run_p88.sh`), read by
`logs/p88/p88_report.py` -> `p88_report.txt`; gates in `logs/p88/gates.sh`.

---

## 0. The change, and what did not ship

| | PREREG's scoped form | **shipped after the gate** |
| --- | --- | --- |
| `FRUIT_SPEED_PLACE` unset, two-line session | 0.52 (`origin=default`) | **0.35** (`origin=scope-off`) |
| unset, every other path | 0.35 | 0.35 (unchanged) |
| `=0` / `off` | 0.35 | 0.35 |
| a speed / `1` / `on`, `FRUIT_SPEED_ALL=1` | that speed / 0.52 | **same** (global, explicit) |
| manifest `physics.place` | written | **written** (records the shipped 0.35 today) |
| `[biarm] place profile:` row | prints in a bimanual session | **prints** (says which cap ran) |

The resolver, the scope plumbing and the provenance stay because they are the
measurement's own instruments and the re-entry is one constant
(`PLACE_TWO_LINE_DEFAULT`) plus this gate; the shipped physics is
**byte-identical** to P87's (proven in §6).

## 1. The mechanism: exact, and the block decomposes

The place transit is one `jerk_limited` profile per leg. At 0.52 with the
shipped `a_max` 1.089, `j = min(25, 10a) = 10.89` and `v = min(0.52, 2a)`; the
duration is the largest of `1.875 d/v`, `sqrt(5.774 d/a)` and `(60 d/j)^(1/3)`,
plus the 2 % margin, rounded up to whole ticks. Predicted from **each control
attempt's own printed distance** (`logs/p88/p88_report.py --predict`):

| seed | place block median | predicted | **measured** | median delta vs predicted | mean delta vs predicted |
| --- | --- | --- | --- | --- | --- |
| 5 | 3.320 s | 2.416 s | **2.550 s** | -0.770 s vs **-0.904 s** = **0.134 s off** | -0.774 vs **-0.776** |
| 6 | 3.370 s | 2.478 s | **2.455 s** | -0.915 s vs **-0.892 s** = 0.023 s off | -0.767 vs **-0.801** |

**The block is exactly `transit(0.52, d) + rest`, and the rest is a constant**:
the `place low` descent is untouched, so `block - transit/120` reads
**0.583 s** (range 0.578-0.588) in **all four cells** (16/11/13/16 legs).
Consequently the treatment's own block median is predicted from **its own** leg
distances to **-0.008 s (seed 5)** and **+0.014 s (seed 6)** - i.e. the cell
delivers the arithmetic to ~10 ms.

**P1b is exact on every leg** (PREREG A1): the treatment's per-leg tick count
agrees with the profile re-generated at 0.52 from that leg's own printed
distance to a **median of 0.0 / +0.5 ticks (max |2|)**, its `|v|cmd` equals the
profile's own peak to **<= 0.009 m/s**, and the median leg cruises at
**0.508 m/s** (control 0.341-0.343; the 15-16 legs whose raised prediction is
`>= 0.45` all read `>= 0.482`). The short legs read 0.42-0.47 because the
acceleration term binds there - the amendment's point.

**P1a fails at seed 5 by 0.014 s, and the miss is the leg mix, not the cell.**
The prediction of §1 is built from the *control's* attempts; the treatment drew
a longer median leg (0.53 m against the control's 0.50 m), and the block is a
distance-dependent quantity, so a median is **not** the branch-free statistic
here. This is P86 §3's lesson in a new place: for a **fixed clock** the median
is exact; for a **transit** the estimable quantity is the mean (which matches to
0.002 s at seed 5) or the per-leg read (which is exact). The registered clause
is judged on its letter - **FAIL** - and the reading above is the *finding*, not
a pass.

## 2. The gate, seed by seed

`ATTEMPTS=20`, seeds 5/6, the shipped scenario; controls explicit
`FRUIT_SPEED_PLACE=0`, treatments unset (which resolved 0.52 in this battery);
the release cell unset everywhere.

| clause | seed 5 (C5 -> T5) | seed 6 (C6 -> T6) | verdict |
| --- | --- | --- | --- |
| **P1a** block median | 3.320 -> 2.550 = **-0.770 s** (pred. -0.904) | 3.370 -> 2.455 = **-0.915 s** (pred. -0.892) | **FAIL** (5: 0.134 > 0.12 band) |
| **P1b** materialised | median tick err 0.0, peak err <= 0.009, `\|v\|cmd` median 0.508 | 0.5, <= 0.007, 0.508 | **PASS** |
| **P2** pooled interval | 10.59 -> **13.23 s (+2.64)** | 11.08 -> **12.11 s (+1.03)** | **FAIL** both |
| **P3** landing | 16/16 -> **11/11** on belt | 12/12 -> **15/15** | **PASS** |
| **P4a** new reason key | `grasped, not placed (no note)` x1 | none | **FAIL** (5) |
| **P4b** place-leg escapes | 0 -> **0** (left 0 -> 0) | 1 -> **0** | **PASS** |
| **P4c** all-leg escapes | 2 -> 3 (+1) | 6 -> 2 (-4) | **PASS** |
| **P6** descent budgets | 0/20 over -> **0/20** | 1/20 over (leg 12) -> **0/20** | **PASS** (the C6 leg is the standing seed-6 branch property P86/P87 recorded) |
| P5 (reported) | 16 -> **11** placed; window 5.66 -> 4.54; batch 5.05 -> 3.71; **wall rate 2.95 -> 2.27** | 12 -> **15**; 5.41 -> 4.96; 3.94 -> **4.81**; **2.34 -> 2.93** | one draw, never gated |

**The verdict is the letter: FAIL** - P1a at seed 5, P2 at both seeds, P4a at
seed 5. The class guard's *substance* is negative (the treatment's place legs
are **0 escapes in 27**, the control's **1 in 29**, and the all-leg count falls
5 vs 8), but a registered clause is a clause.

## 3. Why the delivered side did not follow

**P2 and P5's window rate are one statistic** - the interval is
`(t_last - t_first)/(n-1)`, i.e. the window rate inverted (AGENTS §2's density
census). So the honest statement is a **window-density fall at both seeds**,
with the batch denominator moving the other way at seed 6:

| seed | placed | window span | window rate | batch rate | wall |
| --- | --- | --- | --- | --- | --- |
| 5 | 16 -> **11** | 158.9 -> 132.3 s | 5.66 -> **4.54** | 5.05 -> **3.71** | 325.4 -> **290.6 s** |
| 6 | 12 -> **15** | 121.9 -> **169.5 s** | 5.41 -> **4.96** | 3.94 -> **4.81** | 307.6 -> 307.0 s |

At **seed 5 the count is the story**: five fewer placements, and the left's
**never-held** legs go **1 -> 4** (`force@onset = 0.00 N`, `contacts@onset = 0`,
`sep@onset` 59-63 mm on three of the four - the pads closing on air, the
pre-contact acquisition class of P54/W4, not the place transfer). The faster
place re-times which fruit the close is offered; that is the same class P51
named as the speed cells' cost.

At **seed 6 the count is *up* (12 -> 15) and the interval still rises** because
the placements spread over a **wider window** (121.9 -> 169.5 s): the interval is
window/(n-1), so `11.08 -> 12.11` with `+3` placements. The batch rate rises
(3.94 -> 4.81). That is not a mechanism regression - it is the interval endpoint
measuring the window's ends, which is why the read rules demand both
denominators.

**Pooled: 28 -> 26 placed (of 40), batch 4.51 -> 4.28 placed/min, wall
633.0 -> 597.6 s -> `placed/min wall` 2.65 -> 2.61 (-1.6 %).** The wall does
fall (the cell saves its ticks: 9.5 -> 8.9 and 9.1 -> 9.4 s/attempt), but the
count falls with it, so the throughput is **flat at best and worse on the
window**.

## 4. The class guard (P4) in full

`escaped` = `clean_slip_max > 100 mm` with a pinch (`fmax > 0`), per arm and
carry-leg class; `never-held` = `fmax == 0`; `force_min == 0` is the W8-B guard
row.

| cell | escaped (all) | left | **place-legs** | never-held | `force_min == 0` |
| --- | --- | --- | --- | --- | --- |
| C5 | 2 | 0 | 0 / 16 | 2 | 2 |
| T5 | 3 | 0 | **0 / 11** | 5 | 4 |
| C6 | 6 | 4 | 1 / 13 | 1 | 6 |
| T6 | 2 | 2 | **0 / 16** | 2 | 2 |

The **place transfer never escapes in the treatment** (0 of 27 place legs) and
the all-leg count falls (5 vs 8); the extra `force_min == 0` rows at seed 5 are
the left's never-held legs, not a loaded slide. P74's prediction - speeding the
place does not move the class - **holds**, and it holds on the shipped cell.

**P4a's one failure is a ledger bucket, not a mechanism**: `grasped, not placed
(no note)` exists in **three of the four cells** (C6 7, T5 1, T6 2) and not in
C5; it is the attempt that was grasped and then lost without its own note. The
clause is key-based and fires by its letter.

## 5. The budgets (P6)

Every descent leg is judged by `105`'s own parser and per-leg budget (the
shipped profile's 1.10x peak), not re-derived. Controls: **C5 0/20**,
**C6 1/20** - leg 12, 5.9 cm, `|v|max` **0.164 vs 0.160**, the same seed-6 leg
P86's R6 and P87's T6 recorded (a branch property). Treatments: **T5 0/20,
T6 0/20** (worst 0.111 / 0.115). The place cell did not cost a descent budget.

## 6. The scope and the tree's inertness

**G0 - the control is the shipped cell, and the off path is inert.** `C5`/`C6`
(explicit `FRUIT_SPEED_PLACE=0`) replay **P87's `T5`/`T6`** on the `[fruit]`
stream with the diag rows and both profile rows dropped - `logs/p88/gates.sh`
G0, `p88_report.py --same`; the one line that differs is the new
`[biarm] place profile:` row's label (`=0.35(explicit)`), which is dropped.

**G1 - the motion gate, as corrected by PREREG amendment A2.** All four cells
**DIFFER** from the seed's 20-attempt reference, and for the **controls** that is
not a motion finding: those files (`logs/p80/motion_reference_twoline_p80_20.json`
from P80's `T20`, `logs/p86/motion_reference_twoline_C6_20.json` from P86's
`C6`) were recorded on the **pre-P87 release clock**, while every P88 cell runs
the shipped post-P87 clock (the trim re-times every attempt boundary - exactly
why P87's own T5/T6 DIFFERED while its `FRUIT_SPEED_RELEASE=0` controls matched).
G1's fingerprint clause was unsatisfiable as written and is recorded as
**A2**; the substantive check is `105`'s **per-leg budget** on every cell:
**C5 0/20, T5 0/20, C6 1/20** (leg 12, 5.9 cm, **0.164 vs 0.160** - the standing
seed-6 leg P86's `R6` and P87's `T6` recorded), **T6 0/20**. P6's registered
tiering therefore reads **clean for the cell** (both treatments 0 legs over).

**G2a - the single arm, end to end.** `FRUIT_BIARM=0 scripts/accept.sh` (ten
attempts) is **raw `[fruit]` 346/346 byte-identical** to
`logs/p71/accept_rails_none.log` with `fingerprint: matches
configs/motion_reference_single.json`, and **zero** profile rows in its log (the
rows print only in a bimanual session).

**G2b - the shared station.** `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`, 4 attempts,
unset vs `FRUIT_SPEED_PLACE=0`: **218/218 identical** on the `[fruit]` stream with
the rows dropped, and both record the **shipped clock** (`v_max=0.35
a_max=1.089`, 362 ticks at 0.55 m). The place row's `origin` field is the only
difference (`scope-off` vs `explicit`), which is what the label is for.

**N5 - the final tree replays the control.** After the default was left **off**,
a fresh 20-attempt seed-5 run (`logs/p88/N5.log`, seed 5, unset) is
**868/868 byte-identical to `C5`** on the `[fruit]` stream with the rows
dropped: the shipped tree is the shipped behaviour, and the cell is reachable
only by asking for it. The final `scripts/accept.sh` on that tree reads **7/10,
9.4 s/attempt, `fingerprint: matches configs/motion_reference.json`,
`190: PASS`**, and a second acceptance on the final tree is **444/444 identical**
on the `[fruit]` stream (`logs/p88/accept_final_a.log`).

## 7. Verdict, re-entry, and the re-baseline

**Not adopted.** Three independent clauses fail: P1a at seed 5 (by 0.014 s, and
the miss is the leg mix - the block itself is exact), P2 at both seeds, P4a at
seed 5 (a ledger bucket). The mechanism is **not** the problem; the delivered
throughput is.

**What would reopen it**: a scenario where the place block is a *binding* term
of the interval rather than the acquisition/failure terms - i.e. one where the
placement count does not re-draw (P51's and P80's rule), or a **class-first**
registration that accepts the same count and argues the -0.77/-0.89 s on the
wall alone. The arithmetic for that is already measured: mean block
**-0.774 / -0.767 s** per placed attempt, wall -10.7 % / -0.2 %, at a count of
-5 / +3 (a branch draw of a rendered-frame loop).

**Every number recorded before P88 stands unchanged** (nothing was re-recorded:
`configs/motion_reference.json` = `423896f7`, `..._twoline.json` = `423896f7`,
`..._single.json` = `8952c320`), because the flip did not happen. The
measurement is reproducible with `FRUIT_SPEED_PLACE=0.52`; the provenance
block says `explicit` when it is, and `scope-off` on the shipped tree.

## 8. Pins and evidence

Battery tree (the measured cells): `tasks.py` **`618e7822`**,
`scene.py` `3fac75c2`, `rl_env.py` `f33c7e04`. Final shipped tree: `tasks.py`
**`23430d50`** (`PLACE_TWO_LINE_DEFAULT = False`), `scene.py` **`1ec3b8f8`**
(the `physics.place` builder; battery-time `3fac75c2`, the close-out edits are
docstring-only), `rl_env.py` **`3ac60be8`** (the `TASKS_MD5`
follow), `scripts/248_p88_place_scope_selftest.py` **`68758d48`** (the new
selfcheck leg), `scripts/225` **`6bb08c8b`** (both scoped consumers),
`scripts/247` **`4e570e6d`** ("only the release keys move" re-asserted),
`scripts/selfcheck.sh` **`303d1c32`** (the `P88 place scope` leg),
`logs/p88/p88_report.py` **`8bdb74bb`** (battery-time `4d2e99b2`; extended before
T5 for A1's per-leg read and the P1b verdict - read-only changes).
`configs/*` untouched (`423896f7` / `423896f7` / `8952c320`); checkpoint
`moe_v13s` `61da390a`. `scripts/189_w7a_chain.sh` not run.

Evidence: `logs/p88/{PREREG.md,PREREG.md5,PREREG_A1.md,PREREG_A1.md5,
RESULTS.md,p88_report.py,p88_report.txt,run_p88.sh,run_p88_extra.sh,gates.sh,
header.txt,battery_driver.log}`, the cells `{C5,T5,C6,T6}.{log,stamps,driver}`,
`N5.{log,stamps,driver}`, `{C5,C6}.gate`, `{C5,T5,C6,T6}.budgets`,
`single_accept.{log,gate,same}`, `shared_{unset,zero}.{log,stamps,driver}`,
`shared_raw_same.txt`, `accept_final{,_a}.{log,out}`; `scripts/selfcheck.sh`
PASS (0 failures, 1 skipped),
`scripts/106_index_audit.py` and `scripts/107_collect_merge_test.py` PASS.
