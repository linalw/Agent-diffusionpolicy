# P100 RESULTS - the park return: 36 % slack, and it does not transfer

Registration: `logs/p100/PREREG.md` (md5 `05ff2aab04f21bd05e38789c4a95b06c`,
pinned 00:42:00, before any claimed cell). Battery driver
`logs/p100/battery_driver.log` (00:43:15 → 01:44:50, 10 cells, `failures=0`).
Report `python3 logs/p100/p100_report.py [--check|--blocks|--clearance|--same]`
→ `p100_report.txt`; gates `bash logs/p100/gates.sh`.

## 0. The verdict, in one paragraph

**Not adopted.** The park return's fixed clock was **36 % slack** and the cell
removes it exactly - **-75 of 210 ticks = -0.625 s on every park of every
treatment cell at all four seeds** - with the achieved post-park pose in the
shipped class (`post_err` median 0.0131 → 0.0170-0.0282 rad), a peak commanded
joint step of **0.0978 rad/tick** against the posture gate's 0.15 (that is
11.7 rad/s, **2.2x** the arm's 5.45 rad/s `maxJointVelocity` - the far-seed parks
saturate, and the shipped 90-tick ramp already reads 1.4x on the same park, so
the trim lengthens a saturation rather than creating one), and **zero**
`_recover_ready` events in 80 treatment parks beyond the one jammed transit
seed 6 also has in its **control**. The measured park block falls
**2.53 → 1.91 s (-24.6 %)** pooled. And the delivered clause fails: the
inter-placement interval falls at **2 of 4 seeds** (-2.8 %, -5.4 %), is flat at
one (+0.2 %) and rises at one (+9.8 %), so the **pooled interval is flat**
(11.04 → 11.09 s, +0.5 %; the pooled window rate 60/interval therefore reads
5.44 → 5.41 while the batch rate reads 4.86 → 5.17) while the count moves
**59 → 63 of 80**. The reason is
measurable and is the phase's finding: **the park saving is re-absorbed inside
the slot loop** - by the park gate at seed 5 (+0.38 s) and by starved polls at
seed 6 (+1.27 s) - so the **slot dead time** converts at only 2 of 4 seeds
(-0.02 / +0.39 / -0.76 / -0.32 s). The return is a motion *inside* the slot
loop, and the slot loop is not the interval's binding term either. With P99
(candidate planning) and P88/P89 (the place and lift caps) this **closes the
non-semantic throughput lane on this tree**; the owner's next decision is the
hardware path.

## 1. The lever, and the code it moves

The return is the worker's `finally` (`tasks.py:9763`):

```
_biarm_park(arm)                       # the gate: station owner + other arm's grip/payload
  -> go_ready(arm)                     # :10240
  -> _ready_move(side)                 # :7110   (scope = no session and not two_line -> skip off)
  -> _transit_to("ready")              # :3244   _catch_up_drive (20 ticks)
  -> _ready_transit(ticks=90, settle=120)
       _lift_clear                     # step cap 0.04 rad/tick (the leg-boundary 0.05 bound)
       _catch_up_drive (20/40)
       _blend_to(ready, ticks, settle) # min-jerk ramp + convergence hold
  -> _recover_ready                    # only if err > TRANSIT_TOL (0.08)
```

So the block is `catch_up + lift + blend + settle` and only the last two are
fixed: they tick-clock it. P100 gives them a name -
`tasks.park_profile_resolution(two_line)`, `FRUIT_BIARM_PARK_BLEND` /
`FRUIT_BIARM_PARK_SETTLE`, shipped **90/120**, `PARK_TWO_LINE_DEFAULT = False` -
and the cell is **60/75 = 135 ticks**. The knobs that already existed on this
path and their status: `FRUIT_READY_SKIP`/`_SETTLE`/`_DIAG` are P9-A's and are
**single-arm scoped**, so on the two-line the settle was the hardcoded 120 and
`_ready_settle()` was never read; `FRUIT_ARM_PARK` (P43, shipped, direct only)
moves the *reset* pose, not the return; `FRUIT_BIARM_PARK_EARLY` (W6-C, shipped
W7-A) opens the **gate** earlier and P99 measures that gate at 0.03/0.82 s;
`FRUIT_BIARM_HOT_ARM` (R3 L3) replaces the park with a station-side hold and is
**measured negative**; `FRUIT_BIARM_PREFETCH` (W6-C L1) reserves across the park
and is a **measured null** (0/40).

**The same path, only re-timed.** `_blend_to` interpolates the joint-space line
in a time-warped min-jerk ramp, so a shorter ramp visits the same
configurations in the same order; the settle is a hold at the target. What moves
is *when* the arm is where, not *where* it goes - which is why the clearance
census in §5 can only move by timing.

## 2. The mechanism (P1, P1b) - exact at all four seeds

`[ready]` rows (`FRUIT_READY_DIAG=1`), parks only (the pairing is sequential: a
`[ready]` row belongs to a park iff its arm has an open `park moving` marker, so
the driver's pre-session prime transit is excluded). 20 parks per cell.

| seed | cell | fixed clock | park block (s) | trace blocks (s) | `q_step` max | `post_err` max / median | `rec` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | C5 | 210 | 2.48 | 2.2-2.6 | 0.0642 | 0.0156 / 0.0131 | 0 |
| 5 | **T5** | **135** | **1.87** | 1.6-2.0 | 0.0978 | 0.0423 / 0.0282 | 0 |
| 6 | C6 | 210 | 2.67 | 2.3-6.2 | 0.0632 | **1.2047** / 0.0130 | **1** |
| 6 | **T6** | **135** | **2.07** | 1.7-5.6 | 0.0948 | **1.3306** / 0.0173 | **1** |
| 101 | C101 | 210 | 2.47 | 2.3-2.6 | 0.0642 | 0.0135 / 0.0129 | 0 |
| 101 | **T101** | **135** | **1.85** | 1.7-2.0 | 0.0963 | 0.0424 / 0.0170 | 0 |
| 202 | C202 | 210 | 2.50 | 2.3-2.7 | 0.0652 | 0.0162 / 0.0131 | 0 |
| 202 | **T202** | **135** | **1.84** | 1.7-1.9 | 0.0978 | **0.0795** / 0.0277 | 0 |

**P1 PASS**: the fixed clock is -75 ticks on every park and the measured block
falls **-0.61 / -0.60 / -0.62 / -0.66 s** - inside the registered
`[-0.69, -0.56]` band at every seed and on both arms. **P1b's `q_step` PASS**
(0.0978 worst, 65 % of the posture gate; 11.7 rad/s against the arm's 5.45, i.e.
the drive saturates on the far-seed parks - the shipped ramp reads 0.0652 = 7.8
rad/s = 1.4x on the same park, so the difference is *how long* it saturates).
**P1b's pose clause is the honest cost**: the arm now ends the park a median
**0.0170-0.0282 rad** from ready instead of 0.0131, and the worst park of the
battery reads **0.0795 rad** - 0.6 % under the 0.08 `TRANSIT_TOL` that fires
`_recover_ready`. **Zero** treatment parks beyond that fired a recovery, but the
**margin is gone**: the shipped park arrives ~5x inside the bound, the trim ~1x.
The registered `post_err <= 0.05` bar therefore **FAILS at seed 202** by its
letter, and at seed 6 for a reason that is not the lever (see §6).

## 3. The delivered side (P2, P3) - the saving is absorbed

| seed | placed | interval (s) | Δ | window | batch | wall/pick (s) | `attempts/placement` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 17 → 17 | 9.37 → **9.11** | **-2.8 %** | 6.40 → 6.59 | 5.63 → 5.79 | 16.07 → 15.53 | 1.18 → 1.18 |
| 6 | 12 → 16 | 11.08 → **12.17** | **+9.8 %** | 5.41 → 4.93 | 3.94 → 4.77 | 15.17 → 16.76 | 1.67 → 1.25 |
| 101 | 15 → 14 | 12.16 → **12.18** | **+0.2 %** | 4.93 → 4.92 | 4.87 → 4.86 | 16.49 → 14.92 | 1.33 → 1.43 |
| 202 | 15 → 16 | 11.53 → **10.91** | **-5.4 %** | 5.20 → 5.50 | 4.98 → 5.25 | 15.56 → 15.95 | 1.33 → 1.25 |
| pooled | **59 → 63** / 80 | **11.04 → 11.09** | **+0.5 %** | 5.44 → 5.41 | 4.86 → 5.17 | 15.82 → 15.79 | 1.38 → 1.28 |

**P2 FAILS** (it was registered as "falls at every seed"; it falls at 2 of 4).
**P3's soft clause passes** (`placed/min wall` at the two seeds whose interval
improves: 3.73 → 3.86 and 3.86 → 3.76, i.e. -2.6 %, inside the 3 % bar).

**Where the -0.62 s goes** - the slot loop, which is the phase's answer:

| seed | park | gate | feed | polls | **dead time** | polls (count) |
| --- | --- | --- | --- | --- | --- | --- |
| 5 C → T | 2.48 → **1.87** | 0.03 → 0.41 | 0.25 → 0.23 | 0.15 → 0.38 | 2.91 → **2.89 (-0.02)** | 6 → 15 |
| 6 C → T | 2.67 → **2.07** | 0.76 → 0.49 | 0.23 → 0.22 | 0.78 → **2.05** | 4.43 → **4.82 (+0.39)** | 31 → 82 |
| 101 C → T | 2.47 → **1.85** | 0.36 → 0.59 | 0.22 → 0.23 | 0.60 → 0.23 | 3.66 → **2.90 (-0.76)** | 24 → 9 |
| 202 C → T | 2.50 → **1.84** | 0.81 → 0.67 | 0.22 → 0.23 | 0.50 → 0.97 | 4.03 → **3.71 (-0.32)** | 20 → 39 |

At seeds 5 and 6 the arm returns **earlier and then waits** - for the other arm
(the gate absorbs +0.38 s) or for fruit (the starved-poll count nearly triples,
6 → 15 and 31 → 82). At seed 101 the dead time **does** convert (-21 %) and the
interval still does not move, because the interval is the *placement* sequencing
of two overlapped arms, not the slot loop. That is P99's sentence, one level
down: **a motion is not the interval either.** The seed-6 rise is not a tail
artefact: T6's *first* 11 intervals also average 12.98 s against C6's 11.08 (its
placements are genuinely more spread out; it places 4 more in a 60 s longer
batch, so the batch rate is better while the interval is worse - two readings of
the same branch, which is why a count is never the gate).

## 4. Landing (P5), the class ledger (P4)

**P5 PASS** on every payload-present release: **17/17, 16/16, 14/14, 16/16**
`on_belt=True`; C101 carries one upstream-lost trace (`release_bottom = -184 mm`,
P86/P87's own class), reported separately, and T5's control draws 3
`never-grasped` against the treatment's 2.

**P4 by the letter FAILS at seeds 5 and 202**: each treatment cell carries one
`grasped, not placed (no note)` row that its same-seed control does not. The
**substance does not**: that key is the closed `cnp` class (`logs/p42/SIM_LIMIT.md`)
and is present in **two controls of this same battery** (C6 7/20, C101 4/20), so
the clause as written cannot separate "a new failure mode" from "a standing
bucket that this 20-attempt draw happened to populate". The counts are a wash
anyway: 17/20 → 17/20 and 15/20 → 16/20, with 12/20 → 16/20 at seed 6.

## 5. Clearance (P7) - the minimum *rises*, and the historical band does not reproduce

`FRUIT_BIARM_TRACE=1` pair at seed 5 (invasive link read: **no rate comes from
these cells**), the W2/W7-A convention:

| cell | samples | min | at | < 30 mm | < 10 mm | bands < 30 mm |
| --- | --- | --- | --- | --- | --- | --- |
| X5C (control) | 20 689 | **48.0 mm** | t=187.85 s | **0 (0.0 %)** | 0 | 0 |
| X5T (treatment) | 20 007 | **57.7 mm** | t=91.47 s | **0 (0.0 %)** | 0 | 0 |

The closest pair in both cells is `openarm_left_right_finger vs
openarm_right_right_finger` during the other arm's `grip`/`close`
(`scripts/179_w2_bands.py`: 0 bands, 0 samples < 30 mm in 191 phase windows).
So the registered stop clause does **not** fire - the treatment's minimum is
*above* the control's. **The record's 1.9-2.6 mm (`logs/w6`, `logs/w7`) is not
reproduced on this tree at all**: those traces predate P32's pear, P43's park,
P71's rail removal and low lift, and P96's clearance pose; the shipped line now
keeps its two hands > 48 mm apart for the whole batch. Quote the number for
*this* tree, not the historical one.

## 6. The clauses that failed, and which of them are the lever

**P2 is the one that decides it** (registered: the interval falls at every seed;
it falls at 2 of 4, one tie, one rise).

**P6 (budgets) FAILS at T6 and T101** and at **C6 and C101 too** - the descent
`|v|max` excursions are 0.164/0.160 (C6, +2.5 %), 0.177/0.161 (T6, +10 %),
**0.224/0.160 (C101, +40 %)** and 0.165/0.160 (T101, +3 %). The largest
excursion in the battery is in a **control**, and C101's is the *same leg P93
already recorded* (`logs/p93/RESULTS.md` §2: "`C101` leg 9 `0.224/0.160` =
+40 %"). The budget was **not** re-tuned (AGENTS §2). P6's letter fails on 2 of
4 treatment cells; the instrument cannot separate the lever, and it is not
re-read as a pass.

**Two registered clauses were badly designed, recorded as such rather than
re-read**:

* **P1b's "zero `rec`"** is not discriminating. Seed 6's **control** carries
  one park with `post_err = 1.2047` and `rec = 1` (a 6.2 s block: the ready
  blend ends 1.2 rad short and `_recover_ready` pays a second lift + blend), and
  the treatment carries the same event at 1.3306 / 5.6 s. A jammed ready transit
  is a **scenario property** of that seed's post-place pose, not the cell - so
  the discriminating form is "the treatment's `rec` count is not above its
  same-seed control's" (0 vs 0, 1 vs 1, 0 vs 0, 0 vs 0).
* **P4's key-level reading** cannot tell a standing bucket from a new class
  (§4).

Both are recorded in this section, not used to rescue the verdict.

## 7. Admissibility (P8, and the two proofs)

**The tree is inert and the instrument is neutral, in one comparison.**
`C5` = `logs/p99/C5.log` **1034/1034** and `C6` = `logs/p99/C6.log`
**1030/1030** `[fruit]` lines, identical, dropping only three reporting classes
(P100's `[ready]` and `[biarm] park profile:` rows, and P99's `[bed-sel]` block,
which that cell ran at `FRUIT_BED_DIAG=2` and this one at the shipped `0`; P99
proved its own block neutral by replaying `logs/p94/{T5,T6}` at 974/974 and
970/970). So the unset tree, the new instrument (`FRUIT_READY_DIAG` + the
`q_step` field) and the control are all the shipped branch.

**The shipped acceptance is inert**: `scripts/accept.sh` with the knob unset
reads **8/10, 9.2 s/attempt, `fingerprint: matches
configs/motion_reference.json` (`30fb99f8`), `190: PASS`**, and its `[fruit]`
stream is **420/420 identical** to `logs/p94/accept_final.log` once P100's own
`[biarm] park profile:` row is dropped (`logs/p100/accept_noharm.log`). P98's
"419/419" is the same comparison under P96's sealed filter, which also drops the
pre-pose rows.

**Every treatment cell names itself**: `[biarm] park profile:
FRUIT_BIARM_PARK=(1)(explicit) scope=two-line blend=60 settle=75 (135 ticks;
shipped 210, saved 75)`, and every control `(0)(scope-off) … 90/120 (210 …)`.

## 8. What this phase leaves behind

1. **The park's fixed clock was 36 % slack, measured**: 210 → 135 ticks reaches
   the shipped pose class with `rec = 0` on 79 of 80 treatment parks. The
   `[ready]` decomposition, the `[biarm] park profile:` row and the
   `physics.park` manifest block make any future claim on this block checkable
   from one log.
2. **The scoped lever exists and is default-off**: `FRUIT_BIARM_PARK_BLEND` /
   `FRUIT_BIARM_PARK_SETTLE`, two-line-session only (the driver's pre-session
   prime transit is *not* affected - the scope is enforced in the resolver, not
   argued), with `PARK_TWO_LINE_DEFAULT = False`. Its re-entry is one constant
   plus the acceptance and a reference re-record.
3. **The transfer result**: a 0.62 s/slot motion reduction moves the slot dead
   time at 2 of 4 seeds and the pooled interval not at all (+0.5 %). With P99's
   candidate planning (a cross-lane second is a sort error) and P88/P89 (the
   place and lift caps), **every remaining non-semantic time term on this cell
   is now measured, and none of them is the interval**. The interval is the
   *sequencing* of two overlapped arms plus the closed grip class.
4. **The clearance is not the constraint it was**: 48.0 mm minimum over 20 689
   samples, 0 samples < 30 mm - and the trim raises it.
5. **The margin statement for any future return lever**: the shipped park
   arrives ~5x inside `TRANSIT_TOL`; a 0.62 s trim spends that to ~1.3x. If a
   later phase wants more than 0.625 s it must move the pose requirement, not
   the clock.

## 9. Pins

`tasks.py` **`bfe29961ff82419fbaa5c85480cf1b49`**, `scene.py`
**`472bfb6c1912ec08bcff1c35aa3af4a9`**, `rl_env.py`
**`fa1b0d0b15f72e19758f453fabb74cae`** (the `TASKS_MD5` metadata-only follow),
`scripts/254_p100_park_selftest.py` **`411b6415`**, `scripts/selfcheck.sh`
**`763dbb5a`**, `logs/p100/p100_report.py` **`8d7f5588`**, `run_p100.sh`
**`8bdf4974`**, `gates.sh` **`aa129c4f`**;
`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`**,
`..._single.json` = **`8952c320`** (all untouched); checkpoint `moe_v13s`
`61da390a`. Tree md5s and the PREREG pin: `logs/p100/{tree_pins.txt,PREREG.md5}`;
the launch record `logs/p100/header.txt`.
