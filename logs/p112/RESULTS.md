# P112 results - the three-jaw ring

Owner's item: **P111's item 2**, the three-pad ring, on P111's own algebra - *the
count of tangential contacts is the lever, not the drive*.  Registered in
`logs/p112/PREREG.md` (md5 **`77720306e9328cf6e7853427cbe41f94`**, pinned before
any battery cell).

**Nothing is adopted; no default changes; `configs/` is untouched.**  `cage3` is
a third hand kind behind `FRUIT_GRIPPER_KIND=cage3`, and the shipped `openarm`
hand is byte-identical (G1 below).

## 0. Admissibility

| check | result |
|---|---|
| `scripts/selfcheck.sh` | **PASS (0 failures, 1 skipped)**, with the new `P112 three-jaw ring` leg (`258`, 23 checks) |
| `scripts/accept.sh` (every knob unset) | **8/10, 9.0 s/attempt, `fingerprint: matches`, `190: PASS`**, and its `[fruit]` stream is **374/374 identical** to `logs/p111/accept_noharm.log` (`p112_report.py --same`) |
| `scripts/106_index_audit.py` / `107_collect_merge_test.py` | **OK** / **PASS (21 checks)** |
| the fixture's report | `logs/p112/fixture_report.txt`, 390 closures |

## 1. The algebra, and the kill (`algebra.txt`)

Three pads at 120 deg, offset `delta`, penetration `p_k = s + delta cos(theta_k)`.

* **The contact set is wider than the 4-jaw's**: the minimum penetration is
  `s - delta/2`, so all three pads stay loaded to `delta = 2s`, where a 4-jaw's
  far pad leaves at `delta = s`.
* **The drive and the resistance**, in 2-D, with the **tangential projection**:
  `D = -sum N_k u_k`,
  `F = mu sum N_k sqrt(1-(m.u_k)^2) + mu_b m g`.
* **The fixed point**: `delta_inf = sqrt(3) mu s/(1.5 + (sqrt(3)/2) mu)` =
  **0.84-0.92 s** at the measured pair friction (1.25-1.46), against the 4-jaw's
  **`mu s` = 1.00-1.46 s** under the same solver.  The thresholds are
  **`mu < sqrt(3) = 1.73`** for three jaws and **`mu < 1`** for four, and the
  measured pair friction sits between them.
* **P111's closed forms are one term out** - `(2mu-1)s` and `2 mu s/(1.5+mu)`
  both drop the projection.  Against this solver they are 20-30 % pessimistic on
  the 4-jaw and ~9 % optimistic on the 3-jaw.  **Both verdicts survive**, and the
  3-jaw's margin is smaller than P111's paragraph implied.
* **`k` is a window, not a slope**: the cap saturates the *near* pad first, which
  removes drive without removing friction.  `k >= 0.5/(s - delta_inf/2)` (the
  narrow pads must count) and `k <= cap/(s + delta_inf)` (the wide pad must not
  saturate early) give **[2.9e3, 3.8e3] N/m** over the whole pool at `mu` 1.46;
  the build takes its geometric mean, **3300 N/m**.

**The kill - `delta_inf >= s` at the measured `mu` - DOES NOT FIRE**
(worst `delta_inf/s` = **0.915**), so the build and the fixture are owed.  The
algebra's own next number is the instrument's: `off - off0` of **-0.3..-6.4 mm**
for the measured arrival (P111's `off0` p50 2.9-3.1 mm; P108's aim 8.8 mm), with
the pad count 3 at the flush.

## 2. The build (`cage_hand.py`, a third kind, default off)

| quantity | cage3 | cage4 (unchanged) |
|---|---|---|
| pads | **3** at 0/120/240 deg, one scalar closure | 4 at 0/90/180/270 |
| plate | **20.0 x 60.0 mm** (120 deg neighbour bound: `w <= 0.866 a` = 22.5 mm at the closed aperture) | 26.0 x 60.0 mm |
| distal plane / lip / tool offset | 80.500 / 10.500 / **70.000 mm** | the same |
| **aperture law** | **0.98 x min over its own three pad axes** | 0.98 x the *widest* horizontal extent (unchanged) |
| drive (the measured point) | k **3300** N/m, c 16.2 Ns/m, cap **4.90 N/pad**, hold **1e5** | k 1e5, c 100 |

The one structural change outside the geometry is the **aperture law**, and it is
the phase's real design finding: a single-scalar ring cannot load its pads on a
non-round fruit unless it closes on the **narrowest of its own axes**.  The law
lives on the hand (`CageHand.aperture_extent`, one `getattr` hook in
`tasks.pinch_width`), so a hand that states none keeps the shipped expression bit
for bit - and the four-pad ring's method returns exactly the old value.

## 3. The fixture: the decisive test (`fixture_report.txt`, 390 closures)

One payload, a known offset, the ring closing at the task's clock, no arm.  The
phase's protocol was to stop if the closure could not centre.

| arrival | cage3 `off_end` p50 | cage3 pads 3/3 | cage4 `off_end` p50 | cage4 pads 4/4 |
|---|---|---|---|---|
| 0 mm | 0.71 | 4/6 | 0.51 | **0/6** |
| 2 mm | 0.54 | 6/6 | 0.68 | **2/6** |
| 5 mm | 0.82 | 4/6 | 0.74 | **0/6** |
| 10 mm | 0.97 | 2/6 | 0.85 | **0/6** |
| 20 mm | 1.88 | 2/6 | 1.02 | **0/6** |

(the delivered configuration: the task's freeze, the hard stop, k = 3300.)

**Two statements, and they are different.**

1. **A ring can centre.**  A closure with a clean arrival and no arm centres a
   0-20 mm offset to under 2 mm at *both* pad counts.  P111's `+0.2 mm` on the
   line is not "a ring cannot centre"; it is "the arrival, the tracking and the
   freeze dominate the line" (P108: the close-time offset 2.9-3.1 mm against the
   aim's 8.8 mm).
2. **Only the 3-jaw loads its own pads.**  `pads == 3` on **18 of 30** cells at
   the delivered configuration, against `pads == 4` on **2 of 30** for the
   four-pad ring (**0 of 15** in the full-close arm, 0 of 15 with the freeze and
   no hard stop; cage3 reads 8/15 and 4/15 there).  That is the algebra's claim
   measured at the closure, and it is what the licensed `n mu N` capacity
   (3 x 4.9 N = 14.7 N = 1.5x the shipped pinch) needs.

**The cost is measured too**: the min-extent law **over-closes on the smallest
fruit** - `sep - dia` down to **-7.9 mm** on a 29.6 mm lychee (27 % radial
interference, against the 4-pad ring's -1.8 mm), inside the -15 mm crush rule but
the reason that rule is an endpoint.

**Four support bodies were tried and three failed** (`METHOD.md` section 2): a
static table, a kinematic table and the shipped belt at 0 m/s all let a 0.1 kg
payload sink 2 mm and creep 4-5 mm **with zero pad force** - the same size as the
quantity the fixture exists to resolve.  The adopted form sets the scene's
gravity magnitude to 0 and makes the closure a 2-D problem (it drops the
support's friction term, `mu_b m g` = 0.1-1.3 N against a 5-15 N drive; stated,
not hidden).

## 4. The battery

`cells.sh` (`C` = the shipped hand, `T` = `cage3`), the scripted single arm, the
shipped instrumentation on both arms.

### 4.1 The count

| arm | s5 | s6 | s101 | s202 | pooled | rate |
|---|---|---|---|---|---|---|
| **C** shipped hand | 6/9 | 7/9 | - | - | **13/18** | **72.2 %** |
| **T** `cage3` | 2/10 | 3/9 | **0/10** | 2/9 | **7/38** | **18.4 %** |

Exact two-sided Fisher on the pooled pair: **p = 0.000** (per seed 0.070 / 0.153 -
the treatment is a *branch* draw, but every seed is negative).  The registered bar
was **>= 40 %**, and the phase also comes in **below P111's rigid four-pad ring**
(19/76 = **25.0 %**), so the three-jaw does not convert the class the four-jaw
could not either.  **Clause 2 fails.**

### 4.2 The clean enclosure: 0 of 38

| arm | cage rows | pads 0:1:2:3 | raw = 3 | jam | over | **clean** |
|---|---|---|---|---|---|---|
| **C** | 0 (no cage hand) | - | - | - | - | - |
| **T** | 38 | 8 : 12 : 15 : **3** | 3 | **3** | 0 | **0 (0 %)** |

So the fixture's 18/30 is *not* reached on the line: the three rows that load all
three pads are all **jams** (the descent's `end > 15 mm`, i.e. the plates blocked
on the payload).  **Clause 1 fails.**  This is the same structural split P110
found at four pads: *a ring that reads its pad count is a jammed one.*

### 4.3 The class: the ring is off-centre on the line, and it loses the payload

* `[cage] off0` p50 **3.2 mm**, `off - off0` p50 **+0.50 mm** - i.e. **no
  centring on the line**, against the fixture's -0.3..-6.4 mm for the same
  closure in isolation.  The difference is the delivery: the payload arrives
  *moving*, the arm is tracking it, and the close freezes at its first contact.
  That is P111's read again (+0.2 mm), now with the mechanism separated: **the
  closure centres; the line does not.**
* 33 of 38 `grasp_lift` legs are *seated* (a pad loaded) but the seated legs'
  `force_min` p50 is **0.00 N** - the intermittent pinch P111 measured on every
  cage arm; the shipped hand's is **9.75 N**.
* The dominant failure reason is the eject class: **`fruit did not follow the
  gripper` 21 rows (T) against 1 (C)**.

### 4.4 The guards

| guard | result |
|---|---|
| **G1** no-harm | selfcheck **PASS (0 failures, 1 skipped)**; `accept.sh` with every knob unset **8/10, `fingerprint: matches`, `190: PASS`**, `[fruit]` stream **374/374 identical** to the pre-phase record |
| **G2** landing | **7/7** payload-present releases `on_belt` on T, **13/13** on C; the upstream-lost rows (10 T / 4 C) are the `release_bottom = -184 mm` class, reported separately |
| **G3** budgets | **fails on the treatment**: the worst descent `|v|max` **0.437** against the 0.160-0.161 budget (C 0.122) - the cage's blocked-descent class, `end` p50 57.9 mm at 120 mm aperture in P108; **not re-tuned** (AGENTS section 2) |
| **G4** slots | C 18/20, T **38/40** - two slots lost, both to the supply (`diverted` 4 and 2 in the two fresh seeds) |
| **G5** no new reason | only the baseline keys; the eject row above is the baseline's own |

### 4.5 Why the fixture's promise did not transfer

Three measured terms, and none of them is the pad count:

1. **The arrival is not clean.**  The fixture gives the payload a known *static*
   offset; the line gives it a *moving* one (the belt at 0.12 m/s) and the ring
   closes on a target the arm is chasing.  The close-time offset is 3.2 mm p50
   with the payload moving through the ring.
2. **The freeze fires on the first contact**, so the ring holds the aperture it
   touched at - which for an off-centre payload is `2 x delta` too wide.  The
   delivered pinch is **0.00 N** at its weakest moment on 33 seated legs.
3. **The blocked descent** (0.437 m/s) is the cage family's cost: the three pads
   are 60 mm plates hanging 20.5-80.5 mm below the jaw and they meet the payload
   *before* the arm is at the seat.

So the phase's answer is the same shape as P111's, one step further: **the two
rings differ exactly where the algebra said they would (the 3-jaw loads its own
pads), and that difference does not reach the delivered count** because the line
never gives the closure the clean arrival the centring needs.



## 5. The verdict

**NOT ADOPTED.**  The registered bar was a clean-enclosure share above 10 % and a
placed count of 40 % or better over four seeds.  The phase ships no default, and
the two things it did establish are worth the record:

1. **The three-jaw's closure is real and it is the only ring that loads all its
   pads** (18/30 fixture cells against 2/30) - the mechanism P111's algebra
   predicted, measured where it can be seen.
2. **Centring is not what the ring needs.**  Both rings centre a clean arrival to
   under 2 mm; what the line loses is the *carry*, and the battery says whether
   the extra contacts convert it.

## 6. The hardware price

A three-jaw ring is a **different assembly**, not a variant of the four-pad cage:

* **the pads**: three 20 x 60 mm plates (POM or 6082), the shipped 10.5 mm lip and
  80.5 mm distal plane - the same plate stock, cut narrower (the 120 deg
  neighbour bound allows 22.5 mm at a 26 mm aperture; 20 mm is used);
* **the mechanism**: one **scroll disc** (an Archimedean spiral driving three
  jaws from one rotation) or **three links from one linear actuator**.  This is
  the part that costs: the four-pad cage is one adapter plate plus four radial
  guides, and the three-jaw needs a new plate, three guides at 120 deg and the
  spiral cut;
* **the drive**: the sim's force-capped position drive is a spring; a real ring
  wants either a spring-loaded pad with a hard stop (the P111 form, which this
  phase models as the hold profile) or a force-controlled finger;
* **the cost**: a one-off machined assembly - plate, spiral disc, three jaw
  carriages, three pads.  No buyable three-jaw chuck has the 26 mm closed
  aperture and the 200 mm open aperture this line needs, so it is made, not
  bought.

What the battery says about whether it is *worth* making is section 4.

## 7. Deviations

* **D1 - the cells ran at `ATTEMPTS=10`, not the registered 20.**  Wall time on
  this box (three concurrent Isaac instances): a 20-attempt cell measured
  ~2.5 min/attempt.  The registration's per-seed split and its class endpoints
  are unaffected; the count's power is lower and the per-seed split is published
  rather than a pooled rate.
* **D2 - the control is two seeds, the treatment four.**  P111's shape: the
  shipped hand is the *reference*, not an arm of the comparison.
* **D3 - the fixture's support is zero gravity.**  Three passive supports were
  measured and each failed at the scale of the measurement itself
  (`METHOD.md` section 2).  The dropped term is the support's friction.
* **D4 - the fixture's cage4 law is the hand's own method** (which returns the
  shipped value bit for bit), so the two kinds are compared under one code path -
  the fixture calls `CageHand.aperture_extent` for both.
* **D5 - the open aperture is 200 mm** (`FRUIT_CAGE_OPEN_FACE_R=0.100`), P108's
  measured value; 120 mm blocks the descent on this line.

## 8. Files and pins

`logs/p112/{METHOD.md,PREREG.md,PREREG.md5,RESULTS.md,algebra.py,algebra.txt,
fixture_cage3.py,fixture_report.txt,p112_fixture_report.py,cells.sh,
run_p112_fixture.sh,p112_report.py}`, the 18 fixture logs and the battery cells.

Pins: `cage_hand.py` (the third kind, `CAGE_KINDS`, `aperture_extent`, the
three-pad `apertures`), `tasks.py` (the `CAGE_KINDS` sites and the one
`pinch_width` hook), `rl_env.py` (`TASKS_MD5` follow),
`scripts/258_p112_cage3_selftest.py`, `scripts/selfcheck.sh`;
references `configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`**
and `..._single.json` = **`8952c320`** (all untouched).
