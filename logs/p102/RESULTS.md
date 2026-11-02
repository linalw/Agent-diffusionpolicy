# P102 results — the patch channel sees the loaded slide **0.17-0.94 s** before the pinch is lost, and the **force channel is the late one**

**Instrument-only phase, and the survey's stage (i) does NOT die here.** One
default-off diagnostic (`FRUIT_TACTILE_PATCH`, **0 = off**, the shipped path), one
census script; no command change, no `src/` control-path change, **no `configs/`
change, no reference re-recorded and none owed**. The method, the statistic and
the census rules were written before the runs (`logs/p102/METHOD.md`).

---

## 0. Verdict

`docs/PLATFORM_SURVEY.md` §5.1's stage (i) asked one question — *can a
PATCH-based tactile see the loaded slide early enough to act?* — and its own
kill criterion is "slip visible >= 10 ticks early, or `cnp` does not fall
>= 30 % -> kill". Measured on the shipped cell, 40 attempts, 2 seeds:

| read | value | verdict |
|---|---|---|
| **the lead over the pinch loss** | **6/6 escapes, median 60 ticks = 0.50 s, min 21 = 0.17 s, max 113 = 0.94 s** | **>= 10 ticks on 6 of 6** |
| the patch's state when the slide starts | `frac` 0.52-0.79, `edge` +4.0 .. +17.2 mm - the patch is **on the pad** | a pad sensor has it |
| the slide's rate | 7-189 mm/s (a 30 Hz pad sees 0.2-6.3 mm/frame) | resolvable |
| **how far out the payload is when the FORCE collapses** | **4.5 / 31.3 / 35.2 / 43.9 / 44.4 / 46.4 mm** | the force is 21-113 ticks **late** |
| false positives (60 held legs) | 2 trip at 2.12 mm (3.3 %), **both placed**; `frac` thresholds 0/60 | a wide margin |

**So the mechanism claim is CONFIRMED, and the survey's §2.4 conclusion is
corrected.** W5-C's "where force collapses the payload is out within 0-3 ticks"
is true and it is the *last* moment, not the first: the relative motion that a
pad images precedes it by **0.17-0.94 s**. The survey read that 0-3 tick number
as the *slip's* clock and concluded a 30 Hz GelSight "can label the slip, it
cannot catch it". On this cell's own timing a 30 Hz pad gets **5-15 frames** of
the slide before the pinch is lost. The 25 ms budget is the *force sensor's*
budget, not the cell's.

**What is NOT established, and must be said in the same breath**: the sim's
patch centroid is derived from the payload's **ground-truth pose**, not from a
rendered elastomer (`logs/p42/SIM_LIMIT.md` §3: the pads are rigid and
adhesion-free; there is no visuotactile renderer in the loop). So this phase
measures **how long and how fast the relative motion is**, which is physics and
transfers, and it does **not** measure **whether a soft pad images it** - which
is the survey's T2 bench (§3.3) and is the only thing left to buy. §5 gives the
exact scope.

---

## 1. The instrument (default off, reporting only, proven inert)

`FRUIT_TACTILE_PATCH=<ticks>` -> one `[tactile]` row **per pad per tick** on
every carry leg, from geometry the sim already has: the payload's centre
projected on each pad's face in a frame built from the **measured** jaw axis and
the tool axis (`u` across the finger, `v` down it), its displacement since the
leg's first **seated** tick (`dc`), the patch's occupancy of the pad's face
rectangle (`frac`, from the equatorial disc of the payload against the measured
`61.000 x 84.902 mm` plate), and the signed distance from the centroid to the
nearest face border (`edge`). Method §2 derives each term and says what is exact
and what is modelled.

**Neutrality, proved line for line against a same-batch control** (the P87/P88/
P95 shape - the same cell, the knob the only difference):

```
python3 logs/p102/census.py --same logs/p102/T5.log logs/p102/C5.log
  SAME: 975/975 `[fruit]` lines identical with `[tactile]` dropped
python3 logs/p102/census.py --same logs/p102/T6.log logs/p102/C6.log
  SAME: 971/971 `[fruit]` lines identical with `[tactile]` dropped
```

The `[fruit]` stream *is* the scripted line's own report (`say()` prefixes every
row), so that covers the `[carry]` diag, the `[place-trace]` rows and every
motion/cycle row - i.e. the instrument moved **no** physics and no outcome.

**And the instrument is deterministic, row for row.** `N5` is `T5` re-run on the
**final** tree (`tasks.py b257687d`; the measured tree was `42592b5d`, the only
difference being the P102 block moved out of `_clearance_field`'s tail so the
`236` leg's "the formatter adds no read" assertion keeps its scope):

```
python3 logs/p102/census.py --same ...   # G1/G2, [tactile] dropped
[fruit] streams with the [tactile] rows KEPT:
  17071/17071 lines identical  (16 096 of them are the instrument's own rows)
```

So the relocation is inert, the instrument is reproducible, and the census's
population is stable across runs.

**Why a same-batch control and not `logs/p91/C5.log`.** P91 predates P94's
`_gripper_offset` guard, so it diverges at its own guarded row: attempt 0's left
`grasp_lift` `[diag] carry-assist ... jaw_target=` reads `[0.4053, 0.0...]` here
(the guard's `centre`) against `[0.3997, 0.4...]` there (the pre-P94
`centre - rot @ offset`), the same divergence P96's `PREREG_A2` recorded for the
p92 corpus. P100's cells add `FRUIT_BIARM_PARK_TRACE`/`FRUIT_READY_DIAG` rows, so
they are not the same instrumentation either. The same-batch pair is the only
valid proof, and it passes.

**The selfcheck leg** (`scripts/255_p102_tactile_selftest.py`, 45 checks) pins the
resolver, the `guard_armed` term, that the row block adds **no `ik_step` work
and no articulation read**, the geometry's invariances, the occupancy arithmetic,
the pad rectangle's long-axis origin, and that the row parses back through the
census's own reader.

---

## 2. The population, and the class that owns the failures

40 attempts, the shipped two-line, seeds 5 and 6, `ATTEMPTS=20`:
**29 placed, 7 `cnp`, 4 no-grasp**. 70 carry legs: **60 held, 6 seated escapes,
4 never-held**.

**The attempt join is exact and it is the phase's sharpest result** (census §0b):
the k-th `grasp_lift` a side takes *is* that side's k-th attempt (an attempt that
loses the payload at the lift takes no place leg), so each leg maps to its
attempt and its `[run]` outcome row:

| | attempts | carry a seated escape leg | carry a never-held leg |
|---|---|---|---|
| **placed** | 29 | **0** | 0 |
| **`cnp`** | 7 | **6** | 0 |
| **no-grasp** | 4 | 0 | **4** |

So this cell's 11 failures split into **two disjoint classes that no single lever
touches**: **4 acquisition failures** (the hand closes on air - one reads a
318 mm pad-to-payload offset under a 21.8 mm span, i.e. the pads met each other
beside a 68.9 mm fruit) and **7 `cnp`, of which 6 are a seated loaded slide**.
**Zero of the 29 placed attempts carry a seated escape**, and a held leg's patch
is motionless (`dc_max` median **0.02 mm**, 60 legs).

That matters for the survey's P2: the class a pad sensor could fix is **6 of 40
attempts = 15 %, and 6 of the 11 failures = 55 %**. A perfect tactile cannot
reach the 4 no-grasp attempts, so the most a stage-(i) reaction could buy on this
cell is **+6 placements of 40 = +15 points** (29 -> 35 of 40 = 72.5 -> 87.5 %)
against the survey's +8-point bar - *if* every escape converts.

---

## 3. The lead, and the ordering of the symptoms

Per escape leg, ticks from the leg's **seat** (census §2/§3):

| arm / leg | `t_2mm` | `t_force` | `t_left` | notice (ticks) | notice (s) | `dc` at the loss |
|---|---|---|---|---|---|---|
| left `grasp_lift` | 58 | 79 | 91 | 21 | 0.17 | 35.2 mm |
| left `grasp_lift` | 42 | 110 | 120 | 68 | 0.57 | 44.0 |
| right `grasp_lift` | 13 | 53 | 101 | 40 | 0.33 | 4.5 |
| left `place0` | 6 | 119 | 132 | **113** | **0.94** | 46.4 |
| right `grasp_lift` | 8 | 92 | 103 | 84 | 0.70 | 44.4 |
| left `grasp_lift` | 59 | 111 | 124 | 52 | 0.43 | 31.3 |

* `t_2mm` = `clean_slip > 2 mm` (the survey's P1 reference);
* `t_force` = the strong face **stays** below 1 N for >= 5 ticks (the pinch loss);
* `t_left` = `clean_slip > 100 mm` (P74's "the payload has left").

**The threshold barely matters** (census §3): `dc` at 1 / 2.12 / 4.25 / 8.49 /
10 mm gives a median lead of 61 / 60 / 53 / 46 / 44 ticks and **all six** escapes
clear 10 ticks at every one of the five defensive thresholds (>= 1 mm). The
motion is a **ramp**, not a step, so the detector's exact threshold is not the
design variable. The occupancy channel (`frac < 0.75 frac0`) leads by 34 ticks
median (5/6 >= 10) and the centroid-off-pad (`edge < 0`) by 29 (5/6).

**The money table** (census §6, the `left place0` leg, every 6th tick of 113):

```
   t     dc      du      dv   frac    edge  f_pad0  f_pad1    sep   clean
   6   1.84   -0.80   -1.60  0.521     4.0    8.28    0.00   87.1     2.3
  16   4.19   -2.00   -3.70  0.583     6.1    9.46    0.00   82.6     5.1
  40   6.71   -3.80   -5.50  0.646     7.9    9.63    0.00   80.5     7.6
  64   8.05   -6.70   -4.40  0.562     6.8    9.99    0.00   91.1     8.1
  88  18.48  -18.50    0.90  0.417     1.5   12.66    0.00   98.0    18.9
 112  40.42  -39.90    6.50  0.188    -4.6    8.03    0.00   96.9    43.1
 118  45.89  -45.30    7.10  0.125   -10.0   10.36    0.00   83.7    48.8
 119  46.44  -45.60    8.60  0.125   -10.3    0.00    0.00   79.1    50.0
 131  79.54  -29.30   73.90  0.000   -71.5    0.00    0.00   67.2    98.5
```

The payload walks **45.6 mm across the finger** over 113 ticks while one pad
still carries **8-10 N** (`f_pad1` is 0.00 N for the whole leg - the one-sided
contact P75 recorded), and the force only reaches 0.00 N **one tick before** the
payload's own `clean_slip` passes 50 mm. There is nothing subtle here: **the
payload is 46 mm out of position when the normal force finally collapses.**

**The one control that matters**: on the 60 held legs the patch does not move at
all (`dc_max` median 0.02 mm, p90 0.10). Only 2 held legs move >= 2.12 mm (5.8 and
10.4 mm), and **both of those attempts placed**. So the trigger's false-positive
cost on this population is 2 late-looking re-grips over 40 attempts, not a
systematic misfire.

---

## 4. The two readings of the survey's P1, and why one of them is a category error

`docs/PLATFORM_SURVEY.md` §5.1's P1 reads: *"slip onset is detectable >= 10 ticks
before `clean_slip > 2 mm`"*. **On this cell that clause is not evaluable**: the
patch centroid's displacement **is** the payload's relative displacement
(`dc/clean` median **0.77-1.00** on the six escapes, census §8), so it crosses
the 2 mm line on the same tick (measured: 0-1). The clause compares a signal with
itself.

The decision-relevant reference is **"before the pinch is lost"**, because that
is the moment the attempt is decided. Against it the answer is 21-113 ticks.
Both are reported; only the second is a measurement about the cell. This is the
same class of defect P100 recorded against two of its own registered clauses
(a literal clause that no configuration can satisfy) - **recorded, not
re-read**.

**And the same fact is the phase's most useful caution**: the patch centroid is
*not* an independent channel in sim. It is the pose, re-projected. A raise from
"a tactile leads" to "buy a tactile" needs the one step sim cannot do: show that
a **soft** pad's imaged patch tracks this relative motion. That is the survey's
T2 bench.

---

## 5. Scope: what transfers, and what does not

**Transfers (measured, physics).** The relative motion's **duration and
magnitude**: 0.17-0.94 s, 2 mm at the start of the walk and 31-46 mm by the time
the force collapses, at 7-189 mm/s. Also the **class decomposition** (§2), which
is a property of the cell and decides the business case: the seated slide owns
6 of the 11 failures and none of the successes, and **4 failures are unreachable
by any tactile** (no grip at all).

**Does not transfer (needs hardware).** Whether a GelSight/9DTact patch actually
images that motion at 30 Hz with enough centroid resolution; the sim has rigid,
adhesion-free pads and no visuotactile renderer (survey §2.4, §6). The one soft
pad the tree can author (`FRUIT_FINGER_SOFT_PAD`) is a *force* device, not an
imager.

**Does not cover.** The 4 acquisition failures: they have no seated patch to
image. They are the `never-held` class P54/W5-C measured and are a *hand-over
timing* object, not a tactile one.

---

## 6. The reaction this licenses, and its price (registered, not built)

The brief asks: *if it does lead, say what the reaction could be and price it.*
Four candidates, and only one survives the record's own negatives:

1. **A re-grip** (release, re-centre, close) at `dc >= ~2 mm`. The payload is
   2 mm out at the trigger, so mechanically it works; the tree already has a
   re-seat path (`FRUIT_REGRASPS`, the W1 two-line re-seat) and P40 measured a
   failed probe at **1.24 s (two-line) / 1.50 s (single arm)**. Cost on this
   cell: it would fire on 6 escapes + 2 benign held legs = **8 / 70 legs**;
   at 1.24 s that is **0.25 s per attempt** of worst-case added cycle if every
   trigger is acted on, against a 9.7 s attempt - **2.6 %**, inside P3's +5 %.
   **This is the one to measure.**
2. **A gentler place profile** at the trigger: **measured negative twice**
   (P88's `place` cap and P73's `=0.20` slow place both raised the interval and
   did not convert the class). Do not spend it again.
3. **A pose-follow correction** (the existing `FRUIT_OPENARM_REACT_*` clipped
   chase): it servos the pads to the payload and cannot restore a relation the
   suction-free pinch has already lost; P83/P74's corpus has `recoveries=0` on
   every escape leg. Not a lever.
4. **An early abort** (`FRUIT_FAIL_FAST` at 150 mm): a 2 mm trigger aborts
   0.17-0.94 s earlier than the 150 mm threshold would, which is a **clock**
   win of ~0.2-0.5 s per failed attempt, **not** a class fix. Priced already
   (P83: failed-attempt span -5.14 s at 150 mm; P84: -1.2 to -3.3 s on the
   two-line).

**The next cell to register** (not run here): a **sim-only perfect-detector
re-grip** - trigger on the tree's existing `clean_slip >= 2 mm`, run the re-grip,
and score the survey's **P2** (`cnp` 6 -> <= 4 of 40, placed +8 points) with P3
(interval <= +5 %) on the two seeds. That cell prices the **reaction** and is
free. If it converts, the hardware question reduces to "can a pad image 2 mm",
which is a 20-minute bench with one GelSight and the same fruit (§3.3's T2). If
it does not convert, stage (i) dies on P2 - **not** on the mechanism, which is
what this phase settles.

---

## 7. The measured facts the documents must carry from here

* **The force channel's 0-3 ticks is a *last-moment* number.** `logs/w5/
  C_RESULTS.md` and `logs/p42/SIM_LIMIT.md` §1 stay correct as statements about
  the **normal force**; they are not statements about when the **slip** starts.
  Quote them with that qualifier.
* **The relative motion has 0.17-0.94 s of notice on this cell** (6 escapes,
  2 seeds). Any "the tactile is too slow" argument must now beat that number,
  not the 25 ms force budget.
* **`dc/clean` 0.77-1.00**: the in-plane centroid displacement is the W8-B
  `clean_slip`, so a *sim* patch channel cannot be tested for independence from
  the pose. The independence claim belongs to hardware.
* **The failure split is 4 acquisition + 7 `cnp`, and 6 of the 7 `cnp` are a
  seated slide** - the two classes need different levers, and a tactile only
  touches the second.
* **The F1 max-force family is unaffected**: this phase measured the *sentinel*,
  not the grip.

---

## 8. Reproduction

```bash
bash logs/p102/run_p102.sh            # T5, T6  (the instrument, ~12 min)
bash logs/p102/run_p102_control.sh    # C5, C6  (the same cells, no knob)
python3 logs/p102/census.py --check logs/p102/T5.log logs/p102/T6.log
python3 logs/p102/census.py logs/p102/T5.log logs/p102/T6.log > logs/p102/census.txt
python3 logs/p102/census.py --same logs/p102/T5.log logs/p102/C5.log
python3 logs/p102/census.py --same logs/p102/T6.log logs/p102/C6.log
bash logs/p102/gates.sh               # G1/G2 neutrality, G3 relocation, G4 reader
python3 scripts/255_p102_tactile_selftest.py
scripts/selfcheck.sh
```

Pins: `tasks.py` **`b257687d`** (the measured tree was **`42592b5d`**; the
close-out move is a relocation of the same block, proved inert by G3),
`rl_env.py` `TASKS_MD5` follow `bfe29961` -> `b257687d`, `tactile.py` `dee9121a`,
`scene.py` `472bfb6c`
(`_park_provenance`), `assets.py` `eb30c77a`, `control.py` `9384ff4f`,
`bimanual.py` `9b7fc33f`, `scripts/20_pick_place.py` `3d34342b`,
`logs/p102/census.py` **`697096ed`**, `scripts/255_p102_tactile_selftest.py`
**`21254f16`**, `scripts/selfcheck.sh` **`70b22e42`**, `logs/p102/gates.sh`;
references
`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`**,
`..._single.json` = **`8952c320`**, all **untouched**; ckpt `moe_v13s`
`61da390a`. Evidence `logs/p102/{METHOD.md,RESULTS.md,census.py,census.txt,
run_p102.sh,run_p102_control.sh,header.txt,battery_driver.log,control_driver.log,N5_driver.log,
T5,T6,C5,C6,N5}.{log,stamps,driver}`, `gates.sh`, `smoke.log`, `smoke2.log`,
`selfcheck.log`.
