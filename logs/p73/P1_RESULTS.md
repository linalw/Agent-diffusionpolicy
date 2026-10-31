# P73 phase 1 results — the place-transfer height is **not** a lever on the left arm's place-leg slide

Registration: `logs/p73/PREREG.md`, md5 **`81b70bb3`**, written and pinned
**before any run of this phase** (`logs/p73/PREREG.md5`, 2026-10-31T03:28:54Z;
the first simulator run is the pre-batch fixture at 11:32, the registered batch
at 11:34). Tree at registration: HEAD `c9a129b`, `tasks.py` `f61323f2`; the only
`src/` change is the reporting-only instrument of PREREG §3 (`tasks.py`
**`adcfd348`**, `rl_env.TASKS_MD5` followed).

---

## 0. Verdict

**The transfer height is not a lever on the left's place-leg loaded slide, and
the rotation is not the actuator. The hypothesis fails on its own second link,
and its first link has the wrong sign.**

* **The mechanism moves, monotonically, the wrong way.** The left's achieved
  place-leg rotation rises with the transfer height:
  `tilt_end` **78.7 -> 93.8 -> 105.2 deg** (C -> T1 -> T2, all left place legs) and
  the rotation starts **earlier** (`t45` 313 -> 303 -> 299 ticks), so "raise the
  transfer => less required rotation" is **backwards**: a higher transfer
  *demands more* wrist rotation, not less (**+26.5 deg** over the registered
  ladder; falsifier **A does not fire**).
* **The slide does not move at all**: **1 / 1 / 1** loaded-slide legs
  (1 of 5, 1 of 4, 1 of 5 left place legs) across the same ladder, with the three
  escapes at 995 / 983 / 887 mm — i.e. **the same event, not a smaller one**. With
  the rotation moving 26.5 deg and the count flat, falsifier **B fires**: the
  rotation is not the actuator.
* **And the causal order is visibly wrong**: in **every** payload loss across the
  four arms (**8 of 8** - the 7 registered slides plus C's sub-threshold one) the
  onset row is **before** the leg's 45-deg crossing (onsets 4, 133, 103, 136, 3,
  4, 157, 265 against `t45` 313, 322, 303, 489-561).
  The payload leaves at **1-40 %** of the leg, at a tilt **below 45 deg**, while
  the wrist's final 90-105 deg sweep happens at **70-75 %** of the leg. The
  rotation happens *after* the failure.
* **It is not inertial either** (the registered discriminator, run because rule
  B's literal trigger fired): the **slowed** place leg (`FRUIT_SPEED_PLACE=0.20`)
  reads **4 slides in 8 legs (50 %)** against C's 1 in 5, with the same early
  onset and the same ~85 deg end attitude — a **67 % longer leg** makes the class
  *worse*, so it is a **time-accumulating loaded creep** during the lateral
  transit at near-top-down attitude, not an acceleration response.
* **No landing regression** (falsifier C does not fire): 1 `did not land` in each
  T arm against C's 2, no `fell off the line` row, every release still reaches
  the belt (`need` 248 mm at T2 against the 300 mm `FRUIT_PLACE_LOW_MAX_DROP`
  ceiling), and the fruit bottoms land at 39-47 mm as shipped.
* **What the lever does buy, exactly as predicted**: the crossing rises
  `clr` **34 -> 88 -> 142.5 mm** and `clr_edge` **38 -> 94 -> 151.5 mm** (left
  held legs), i.e. **+54 / +108.5 mm** against PREREG P1's predicted **+49 / +99**
  — P69-B's 0.825:1 is confirmed on a second, independent axis, and no leg goes
  negative.

**Nothing is adopted.** No shipped default moved, `configs/` untouched, no commit.
The tree's only change is a default-off reporting instrument, proven inert on the
scripted line (§5).

---

## 1. The arms (seed 77, one claim each, 15 picks, `moe_v13s` `61da390a`)

The registered cell (PREREG §2), unchanged; `FRUIT_CARRY_DIAG=1
FRUIT_MOTION_REPORT=1 FRUIT_CARRY_ATTITUDE=1` in every arm, so all four carry the
identical instrumentation. The knob is in effect **in-log** (`place low` `need`,
the only print that follows the transfer z).

| arm | `FRUIT_OPENARM_TRANSFER_LIFT` | place z (left) | `place low` need (median / range) | `place low` bottom |
|---|---|---|---|---|
| **C** | 0.08 (shipped, explicit) | 1.530 | **95** [83..144] | 1470 [1458..1519] |
| **T1** | 0.14 | 1.590 | **177** [158..204] | 1552 [1533..1579] |
| **T2** | 0.20 | 1.650 | **248** [235..262] | 1623 [1610..1637] |
| **SLOW** | 0.08 + `FRUIT_SPEED_PLACE=0.20` | 1.530 | **114** [98..139] | 1489 [1473..1514] |

The `--check` manipulation gate passes (`logs/p73/p1_report.txt`): every left
place leg carries the six schedule fields, and `need` steps **+82 / +71 mm** for
the nominal **+60 / +60 mm** raises. *Read that +82 as 60 mm of raise plus the
payload's own hang*: at a fixed arm the same row spans 61 mm (C's 83..144), so
`need` is the right **ordering** proof, not a millimetre ruler.

---

## 2. The endpoints

### 2.1 Primary — the class is flat

| arm | left placed | left attempts | left place legs | **loaded slides > 800 mm** | per-leg | blow-ups | near-miss |
|---|---|---|---|---|---|---|---|
| **C** | 3 | 7 | 5 | **1** | 20 % | 0 | 1 at **793.3 mm** (loss row 166) |
| **T1** | 3 | 4 | 4 | **1** | 25 % | 0 | — |
| **T2** | 4 | 5 | 5 | **1** | 20 % | 0 | 1 at 8.2 mm (placed) |
| **SLOW** | 4 | 8 | 8 | **4** | 50 % | 0 | — |

* **The registered primary is flat to the leg**: 1/5, 1/4, 1/5. The three slides
  are the same event at the same magnitude (995.1 / 982.7 / 887.2 mm).
* **No blow-up** this batch (the PREREG's exclusion rule — `>10 m` slip or
  `>5 m/s` `in-hand_vmax` — caught none; the shipped corpus's 117 m row was the
  reason it exists).
* **The placed counts are not comparable** (3/7, 3/4, 4/5): the left's **attempt
  count itself moves** (7 vs 4 vs 5) - the direct loop is not reproducible, and a
  different left cadence re-times the shared feeder. That is why the class is
  reported **per place leg**, which is the denominator that does not move.
* One C leg loses the payload at **793.3 mm** — under the 800 threshold, so it
  counts as held by the registered rule. Stated, not hidden: C is 2 payload
  losses in 5 place legs by mechanism, 1 by threshold. T1/T2 have no such leg, so
  the threshold does not create the flatness (C 2/5 vs T2 1/5 is still not a
  signal at this n).
* **Every attempt that reached a place leg is classified**, so the differing
  attempt counts cannot hide the class: C 7 attempts = 5 place legs + 2
  `fruit did not follow the gripper` (the known **pre-contact acquisition** class,
  never grasped, no place leg); T1 4 = 4 + 0; T2 5 = 5 + 0; SLOW 8 = 8 + 0. The
  left's failures are therefore **two distinct classes** and only one is this
  screen's endpoint: **`cnp` 2 / 1 / 1 / 4** (all of them loaded slides) against
  **acquisition 2 / 0 / 0 / 0**.

### 2.2 Secondary — the rotation schedule (the mechanism read)

Left place legs, all of them (held and lost):

| arm | `tilt0` | `tilt_end` | `t45` | `t75` | max \|rate\| |
|---|---|---|---|---|---|
| **C** (n=5) | 0.8-1.3 | **78.7** [71.9..83.3] | 313 [307..319] | 393.5 | 0.42 deg/tick |
| **T1** (n=4) | 0.8-1.1 | **93.8** [79.0..98.0] | 303 [255..322] | 365 | 0.44 |
| **T2** (n=5) | 0.8-1.1 | **105.2** [100.5..105.5] | 299 [250..303] | 356 | 0.49 |
| **SLOW** (n=8) | 0.8-1.7 | **85.6** [70.1..92.4] | 524.5 [463..561] | 556 | 0.29 |

**This is a monotone lever on the achieved rotation** (+13.8 deg then +11.4 deg,
**+26.5 deg** from C to T2; `t45` **-14 ticks**) and it is **blind to the slide**.
Both directions of H1 are therefore measured, not inferred:

* *"height -> less rotation"* is **false**: the sign is **+**, not -.
* *"rotation -> slide"* is **false**: 26.5 deg of extra achieved rotation and a
  14-tick-earlier rotation change the slide count by **zero**.

The SLOW arm separates the remaining explanations, and the statistic that
separates them is **time, not fraction**: the slow leg's rotation starts at the
*same* share of the leg (`t45`/ticks **73-78 %**, C's **73-79 %**) but that share
is **+211 ticks = +1.76 s of absolute dwell at near-top-down** (524.5 on a
680-tick median leg against 313 on C's 408) - and its slide count **quadruples**.
So the class tracks **how long the payload hangs in a top-down pinch under
lateral load**, and a gentler profile (the S1 knob scales `a_max` with `v_max`)
makes it worse. Nothing about that is inertial.

### 2.3 The slide's own signature (all four arms, the 8 payload losses)

| arm | slip | onset | loss | leg ticks | leg fraction at loss | tilt at loss | `force@onset` | `sep@onset` | `sep@loss` | `sep_end` | `contacts@onset` | `fmin` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C | 995.1 | 4 | 88 | 398 | 22 % | **< 45 deg** | 7.94 N | 68.1 | 67.7 | 51.6 | 1 | 0.00 |
| C | 793.3\* | 133 | 166 | 416 | 40 % | **< 45 deg** | 10.23 N | — | — | 45.1 | 1 | 0.00 |
| T1 | 982.7 | 103 | 146 | 428 | 34 % | **< 45 deg** | 9.49 N | 68.7 | 61.1 | 42.1 | 1 | 0.00 |
| T2 | 887.2 | 136 | 182 | 449 | 41 % | **< 45 deg** | 10.63 N | 72.0 | 68.0 | 45.1 | 1 | 0.00 |
| SLOW | 1199.6 | 4 | 161 | 671 | 24 % | **< 45 deg** | 8.78 N | 69.2 | 60.1 | 42.0 | 1 | 0.00 |
| SLOW | 1134.8 | 3 | 144 | 671 | 21 % | **< 45 deg** | 9.97 N | 83.1 | 71.3 | 52.9 | 1 | 0.00 |
| SLOW | 1124.2 | 157 | 176 | 709 | 25 % | **< 45 deg** | 11.21 N | 62.7 | 60.1 | 42.1 | 1 | 0.00 |
| SLOW | 971.2 | 265 | 314 | 763 | 41 % | **< 45 deg** | 10.32 N | 80.3 | 67.0 | 51.9 | 1 | 0.00 |

\* the sub-threshold payload loss (§2.1): a slide by mechanism, held by the
800 mm rule. It is in the table because it is the *same* event with a shorter
walk; the arm comparison uses the registered threshold.

(`tilt at loss` is a **bound**, not a sample: `loss < t45` means the achieved tilt
was below 45 deg on that tick. The instrument reports `t45`, so this needs no
extra read.)

The class is the **W8-B single-sided loaded slide** with a place-leg twist: at the
onset, **one** pad is in contact at the pinch's own force (7.9-11.2 N against the
9.8 N drive), then contact is lost (`fmin 0.00`, `min_contacts 0`) and the jaws
close to **42-53 mm** by the leg's end — i.e. **the payload exits the pinch
without prying the pads** (the lift-leg form reads `sep_end` **98 mm**, the open
stop). So the place-leg escape is a **clean, low-force exit**, not a force
deficit and not a pry. `in-hand_vmax` 0.94-1.60 m/s on every one.

### 2.4 The right (registered as "no new class", never as "unchanged")

| arm | right placed | right place legs | right slides | right `tilt_end` | right `clr` |
|---|---|---|---|---|---|
| C | 7/8 | 7 | **0** | 75.0 [60.7..99.4] | 73-98 |
| T1 | 10/11 | 10 | **0** | 84.9 [73.4..106.2] | 141-185 |
| T2 | 10/10 | 10 | **0** | **107.3 [92.0..109.7]** | 237-264 |
| SLOW | 7/7 | 7 | **0** | — | — |

**The strongest single argument in this document**: the right arm reaches a
median **107.3 deg** of place-leg rotation (max 109.7) - *more* than the left ever
does - and slips **0.0-0.1 mm on 10 of 10 legs**. Whatever the left's ~90-105 deg is, the right
demonstrates it is not by itself a slide. And no new right failure class appears
(the T arms place 10/11 and 10/10; the one T1 miss is a `fruit did not follow the
gripper` acquisition row on the right, not a place-leg loss). **P5 holds.**

### 2.5 Cost and landing

| arm | place-leg ticks (median) | `place low` descent ticks | episode ticks (median / sum) | `did not land` | `fell off` rows | discharged |
|---|---|---|---|---|---|---|
| C | 408 | 78 [74..91] | 1805 / 26 569 | 2 | 0 | 9 |
| T1 | 430 | 119 [108..145] | 1886 / 28 379 | 1 | 0 | 12 |
| T2 | 425 | 168 [145..185] | 1931 / 28 989 | 1 | 0 | 13 |
| SLOW | 680 | 82 | 2039 / 30 373 | 4 | 0 | 10 |

**PREREG P2 partially missed and the miss is the interesting half.** I predicted
the *place leg* would grow +55..+140 ticks; it grew **+22 / +17** because the
transit got *cheaper* as the descent got dearer. The descent itself held the
prediction: **+41 / +90 ticks** (0.68 ticks/mm against the predicted 0.9). The
episode grew **+81 / +126 ticks (+4.5 % / +7.0 %)**. So the lever's cost is real
but modest — and irrelevant, since it buys nothing on the class.

---

## 3. The pre-registered predictions, scored

| # | prediction | outcome |
|---|---|---|
| **P1** | `clr` +49 / +99 mm (0.825 x the raise) | **HIT**: +54 / +108.5 mm on the left held legs, and 0 legs below 0 |
| **P2** | place leg +55..+140 ticks | **PARTIAL MISS**: the leg total is +22 / +17 (the transit shrank as the descent grew); the descent half is +41 / +90, and the episode +81 / +126 |
| **P3** | `tilt_end` stays ~85-95 deg in all arms (the endpoint is saturated by the place pose) | **MISS, and this is the phase's finding**: it went 78.7 -> 93.8 -> **105.2**, a monotone **+26.5 deg**. The endpoint is *not* saturated - the height *is* a rotation lever, just not in the promised direction |
| **P4** | no monotone fall in the slide count | **HIT**: 1 / 1 / 1 |
| **P5** | no new right class, no placed regression | **HIT**: 0 slides in every arm, 7/8 -> 10/11 -> 10/10 |

P3's miss is what makes the negative worth publishing: had I not instrumented the
schedule I would have concluded "the height does not move the rotation" from a
single saturated endpoint sample, and that would have been **wrong** - it moves
it, upward, and the class does not follow.

---

## 4. What the phase establishes, and what it closes

**Established (within one seed, one draw per arm):**

1. `FRUIT_OPENARM_TRANSFER_LIFT` is a **real, monotone lever on the place leg's
   achieved rotation** (+26.5 deg C -> T2) and on the **crossing clearance**
   (+108.5 mm), and it is **inert on the place-leg loaded slide** (1/1/1).
2. **The rotation is not the actuator** of the slide, on two independent reads:
   the count is flat while the rotation moves 26.5 deg, and **every** payload
   loss's onset precedes the 45-deg crossing (8/8) - the payload leaves before the
   wrist turns.
3. **The slide is not inertial**: slowing the place profile 0.35 -> 0.20 m/s (with
   its `a_max` on the shipped shape) makes it **worse** (4/8 vs 1/5), so the
   mechanism is a **time-accumulating loaded creep** under the lateral transit at
   near-top-down attitude.
4. The place-leg escape's signature is a **clean single-sided exit** at the
   pinch's own force, ending with the jaws **closed** to 42-53 mm (the lift-leg
   form ends at the 98 mm open stop). It is neither a force deficit nor a pry.
5. The lever's only measured benefit is the **crossing** - which P71 already
   solved a different way (the rails are gone) - at **+4.5..7.0 % of episode
   ticks**.

**Changes what we would do next (registered as the named consequence, not run):**

* **Do not spend another transfer-height rung.** The ladder's own mechanism
  (rotation, crossing) moves monotonically and the class does not; a fourth point
  cannot add information about the class.
* **Do not spend another rotation lever** (`FRUIT_GRASP_LEFT_TOPDOWN`, P62's T0
  family, P64's pre-compensation): the causal link they act on is measured to be
  off the failure's path.
* **Do not slow the place leg** (it doubles the class). The *speed-up* direction
  is the one with a measured contrast, but its cost is already registered
  (P44/P46: the placement cost is the closed grip class), so it stays a
  **time-for-placements trade**, not a class fix.
* The residual is the **closed `SIM_LIMIT.md` loaded slide** on a leg where the
  payload is held top-down and translated laterally for ~0.5 m. The only levers
  that touch that are the ones `SIM_LIMIT.md` already sanctions (**a new pad
  asset**, or **a real-jaw clamp-force anchor**) or a **workstation change that
  shortens the lateral transit at top-down** - and the cheapest such change,
  `FRUIT_PLACE_INNER_SHIFT`, is **measured negative** (P3: 90 % -> 30 % placed),
  so the remaining form is a place-point/station move with its own
  pre-registration.

---

## 5. The instrument, and the no-harm gate

**The instrument** (`tasks.py` `adcfd348`, `rl_env.TASKS_MD5` followed;
reporting only, `FRUIT_CARRY_DIAG=1`): six fields on the `[carry]` row -
`tilt0`, `tilt_end`, `tilt_max`, `t45`, `t75`, `tilt_rate` - the achieved tilt
from world `-Z` (`[attitude]`'s own `acos(-rot[2,2])`) accumulated **per guarded
tick**. **It adds no articulation read**: `rot_now` is the block's own read for
`clean_slip`. Pinned by the new selfcheck leg
`scripts/240_p73_tilt_selftest.py` (containment in `if guard_armed:`, the
`[attitude]` identity, the no-new-read property, the first-crossing / max /
signed-step arithmetic, and the row parsing back); `scripts/235` re-pinned for
the inserted fields with its meaning kept.

**Why it was necessary**: the pre-existing per-leg read (the `[attitude]` line) is
printed **once, at the leg's end**, and on the shipped corpus it reads 80.8-94.6
deg on **both** the lost and the placed left legs, and the right reaches it too.
A screen that reported only that endpoint would have been structurally blind - and
on P3 it would have been **wrong** (the endpoint does move; it moves up).

**No-harm (the tree changed, so this is verified, not assumed):**

| check | result |
|---|---|
| `scripts/accept.sh` (`SKIP_SELFCHECK=1`, `FRUIT_MOTION_REPORT=1`) | **6/9 = 67 %**, `fingerprint: matches configs/motion_reference.json`; the FAIL is the standing 75 % rate floor (the tree's recorded branch since P32) |
| `[fruit]` stream vs `logs/p71/accept_rails_none.log` | **346/346 byte-identical** - the instrument is inert on the scripted path |
| `configs/` | untouched (`motion_reference.json` `8952c320`, `..._twoline.json` `eb697f23`); **no re-record** |
| `scripts/selfcheck.sh` | **PASS, 0 failures**, 1 skip (the motion-budget leg, which needs a logged run) - now including the P73 leg |
| shipped defaults | none moved; `FRUIT_OPENARM_TRANSFER_LIFT` is read per call from the environment and its default is still `"0.08"` |

---

## 6. Limits, and two measured defects worth naming

* **One seed, one claim per arm.** 4-8 left place legs per arm; the class is
  1-4 events. Every count here is a **branch**, not a rate - the direct loop is
  not reproducible (rendered frames). The **registered expansion rule did not
  fire** (`|Δ slides| >= 2` or `|Δ placed| >= 2` at seed 77), so seeds 101/202
  were **not** run: the read is mechanism, and the mechanism is flat.
* **The SLOW arm is a directional mechanism read, not a rate** (4/8 vs 1/5,
  Fisher two-sided **p = 0.56**). Its value is the *sign* and the mechanism, both
  of which the schedule corroborates.
* **The arm-mix moves** (left attempts 7/4/5/8), so no placed-count delta is a
  rate. The per-place-leg denominator is the honest one and it is flat.
* **The knob is not side-scoped** (PREREG §1): the right's **lift end** rises with
  the transfer, so the right is read as "no new class", never as "unchanged". It
  showed no new class at 107 deg, which is the useful part.
* **`need` is not a millimetre ruler** for the raise: it carries the payload's own
  hang, which spans 61 mm at a fixed arm. The `--check` gate uses it for
  **ordering** (+82/+71 for +60/+60) and says so.
* **Provenance gap (named, not fixed)**: the manifest records `lift_dz`,
  `lift_climb`, `scene` and `physics`, but **not** `FRUIT_OPENARM_TRANSFER_LIFT` -
  a store recorded under a different transfer height would be indistinguishable
  from the shipped one. No store was recorded here, so no manifest is contaminated;
  if this knob is ever used in a recollection, the field must go into
  `assets.scene_provenance` first (the P41/P72 rule).
* **The `[carry]` row grew**, so a pre-P73 row and a post-P73 row differ by six
  fields. Every parser in this tree tokenises (no positional reads), and the
  archives are unchanged on disk.

---

## 7. Reproduce

```bash
bash logs/p73/run_p73.sh                        # C, T1, T2 at seed 77 (one claim each)
SEEDS=77 ARMS=SLOW bash logs/p73/run_p73.sh     # the conditional discriminator
python3 logs/p73/p1_report.py --check \
    logs/p73/direct/{C,T1,T2}_77.log > logs/p73/p1_report.txt
python3 logs/p73/p1_report.py logs/p73/direct/SLOW_77.log
python3 logs/p73/p0_census.py logs/p71/direct/treat_*.log   # the shipped baseline
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p73/accept_noharm.log scripts/accept.sh
scripts/selfcheck.sh
```

**Pins** (md5 first 6; `logs/` is gitignored - `git add -f` at a close-out):
`logs/p73/PREREG.md` **`81b70b`**, `PREREG.md5` `21049b`, `header.txt`
**`866e93`**; `direct/C_77.log` **`ea2396`**, `T1_77.log` **`2aef7b`**,
`T2_77.log` **`34d331`**, `SLOW_77.log` **`adee6b`**, `smoke_T1.log` `572b0c`
(pre-batch fixture, 2 picks, **not** part of any count); `p0_census.py`
`b38bd1`, `p0_census.txt` `a4f7db`, `p1_report.py` `6e9918`, `p1_report.txt`
`f17de2`, `run_p73.sh` `131d2c`, `accept_noharm.log` `3c6f33`,
`accept_noharm.driver` `8f1b98`, `logs/selfcheck.log` `2dd81c`;
`src/fruit_sorting/tasks.py` **`adcfd348`**, `rl_env.py` **`157e6d`**
(the `TASKS_MD5` follow), `scripts/235_p65_lift_selftest.py` **`bdcbb4`**,
`scripts/240_p73_tilt_selftest.py` **`28cd1f`**, `scripts/selfcheck.sh`
**`d8ed6a`**; `configs/motion_reference.json` `8952c320` and
`configs/motion_reference_twoline.json` `eb697f23` **untouched**; checkpoint
`moe_v13s` `61da390a`.
