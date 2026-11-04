# P111 results - the compliant closure: a gentler jam, not a self-centring chuck

Owner's item: P110's **item 1**, the only term its arithmetic left standing. The
hypothesis, as the owner stated it: *a force-capped position pad is a rigid
finger; make it a spring and the ring's four pads will push an off-centre payload
to the ring's centre instead of gripping it where it sits.*  Registered in
`logs/p111/PREREG.md` (md5 **`e641d074`**, pinned before any cell) + `PREREG_A1.md`
(md5 **`c2d263e4`**, pinned before any treatment cell). **Nothing adopted, no
default changed, `configs/` untouched.**

**The one-sentence answer.**  **Compliance does not centre the ring, at any
stiffness, and it does not enclose it**: the offset at the close's end *grows*
(+0.2 to +2.3 mm on the rows that stayed in the ring), the clean enclosure stays
**0-3 rows per arm** (0/73 at `k = 1e3` against the rigid ring's 3/76) and the
placed count stays the cage family's ~16-23 % against the rigid ring's 25 %
(n.s. at n = 76).  **The reason is the algebra's own**: the aperture is set by the
fruit's *widest* extent, so the perpendicular pair never loads - the ring is a
**two-pad V-block at every stiffness** (the modal pad count is 2 in every arm,
including the rigid one) and a V-block has no centring symmetry to exploit.  A
compliant pad buys a **gentler contact** (the force at the freeze falls 4.90 ->
0.6-1.8 N) and nothing else.

## 0. Admissibility: the controls are replayed, not assumed

| check | result |
|---|---|
| `logs/p111/C_s5.log` vs `logs/p108/S_s5.log` | **621/621 `[fruit]` lines identical** (the phase's rows dropped) |
| `logs/p111/R_s5.log` vs `logs/p108/E_s5.log` | **531/531 identical**; the **19 `[cage]` rows identical** with `off0`/`off` stripped |
| `scripts/selfcheck.sh` | **PASS (0 failures, 1 skipped)** |
| `scripts/accept.sh` (every knob unset) | **8/10, 9.0 s/attempt, `fingerprint: matches`, `190: PASS`, `[fruit]` stream byte-identical to `logs/p110/accept_noharm.log`** |
| `scripts/106_index_audit.py` / `107_collect_merge_test.py` | **OK** / **PASS (21 checks)** |

So the new `[cage] off0`/`off` fields and the `close_done`/`close_begin` call
sites are **inert on both controls** - which is what licenses reusing P108's
`S`/`E` cells for the other seeds instead of six more cells (P95's rule: prove the
replay, then reuse).

## 1. The algebra: the centring condition is an inequality that `mu > 1` fails

`logs/p111/algebra.py` -> `algebra.txt`.  The ring is one radial synergy on four
force-capped position pads.  At an offset `delta` along a jaw axis the
penetrations are `s + delta` (near), `s - delta` (far, contact only while
`delta < s`) and `s - roundness` (the perpendicular pair), with
`s = 0.01 d` (the shipped 1 % per face) and `roundness = (wide - narrow)/2`.

**The payload's motion is normal to the near/far faces** (Coulomb friction is
zero there) **and tangential to the perpendicular pair** (friction `mu N`), so

```
drive = near - far            fric = 2 mu perp + mu_belt m g
terminal offset  delta_inf = (2 mu - 1) * min(s, cap / (2 mu k))
```

* **`mu > 1` is the term, not the stiffness.**  The residual is `(2mu - 2) s`, so a
  four-jaw lands at 1.1-1.9 s where the 4-contact state needs `< s`.  The measured
  pad-payload friction is **`mu_pair = (2.0 + mu_fruit)/2 = 1.25-1.46`** (P104's
  `mu_app` 1.05-1.45, and PhysX averages the pair), and the ratio is **k- and
  cap-free** - which is why the ladder below has a *knee* and no slope.
* **A three-jaw would centre**: `delta_inf = 2 mu s/(1.5 + mu)` = **0.82 s < s**.
  The number of *tangential* contacts is the lever, not the stiffness.
* **The knee at `k* = cap/(2 mu s)` ~ 2.2e3 N/m**: above it the perpendicular pair
  is at the cap, `fric = 2 mu cap = 12.8 N > cap`, and nothing slides at all -
  that is exactly the shipped ring (`k = 1e5`, `cap/k = 0.049 mm`).  Below it the
  payload slides to `(2mu-1) s`, a 5-8x centring from P108's 8.8 mm aim.
* **The geometric branch is the one that decides this cell**: because the
  aperture is `0.98 x` the **widest** extent, a fruit with any roundness leaves the
  perpendicular pair short by `roundness - s`.  The pool's roundness is 0.02-0.20 d
  and `s` is 0.005-0.015 d, so **the pair is short on most of the pool** - and then
  the friction term collapses to the belt's, the ring *would* centre, **but the
  pad count cannot reach 3** (a pad counts at 0.5 N).  That is the structural
  tension the phase measured: **a ring that centres cannot read `pads >= 3`, and a
  ring that reads `pads >= 3` is a jammed one.**

Predicted (registered as F1-F5): centring yes (~1.1-1.9 s), the clean enclosure
**no**, the bat down, the count the rigid ring's, no crush.

## 2. The build: three windows, one knob each

`cage_hand.py` already owned its drive (`k`, `c`, `maxForce` per pad).  P111 adds
the two **windows** a compliant closure needs and one instrument:

| profile | knob | when |
|---|---|---|
| **approach** | `FRUIT_CAGE_PAD_STIFFNESS` / `_DAMPING` | always the base; the shipped cage is `k = 1e5`, `c = 100` |
| **close** | **`FRUIT_CAGE_CLOSE_STIFFNESS`** / `_DAMPING` (new) | between `close_begin` and `close_done` - the compliance is **scoped to the closure** |
| **hold** | **`FRUIT_CAGE_HOLD_STIFFNESS`** / `_DAMPING` (new) | after `close_done` - the **hard stop**, a spring-loaded pad bottoming out |

`close_done` re-writes the four drives **with their target unchanged**, so the pad
re-loads to `min(k_hold * penetration, cap)` = the cap **at the aperture it
found**: the stop loads the grip and does not move the payload.  An open command
reverts to the approach profile, so no second call site is needed for the revert.
At the shipped defaults both windows are dead writes (the selfcheck executes that:
"with both window knobs unset the two calls write nothing").

**The instrument**: `[cage] off0= off=`, the payload's radial distance from the
ring's **axis** (the cage base's xy; the four pads are symmetric about it) at the
close's start and at the flush.  Two reads per attempt, both already taken every
tick, no control input.  It is what makes "centring" measurable at all - and it
also cleanly separates the arm-never-arrived class (85-1336 mm) from the rows that
can say anything about centring (`off0` p50 **2.9-3.1 mm**, p90 3.7-4.2).

## 3. The cells, and the six arms

`logs/p111/cells.sh ARM:seed`, the scripted single arm (`FRUIT_BIARM=0`; the
two-line scheduler still refuses a non-`openarm` hand, `tasks.py:9543`),
`ATTEMPTS=20`, one claim per run, P108's instrumentation verbatim on every arm:

| arm | hand | close | hold | seeds |
|---|---|---|---|---|
| **C** | shipped `openarm` | - | - | 5, 6 |
| **R** | cage 200 mm, `k = 1e5` | rigid | - | 5, 6, 101, 202 |
| **T1** | cage 200 mm, `k = 1e3` *(always soft)* | 1e3 | 1e5 | 5, 6, 101, 202 |
| **T2** | cage 200 mm, `k = 5e3` *(always soft)* | 5e3 | 1e5 | 5, 6, 101, 202 |
| **T4** | cage 200 mm, **rigid approach** | 1e3 | 1e5 | 5, 6, 101, 202 |
| **S1** | cage 200 mm, `k = 1e3`, **no stop** | 1e3 | - | 5, 6 |

T1/T2 are the registered always-soft forms; **T4 is the scoped form** (soft only
inside the closure) and was added after T1's first cell showed the always-soft
pad is a poor *position source* during the approach; S1 is the pure-soft screen.

## 4. The endpoints

### 4.1 The clean enclosure does not rise (F2 confirmed)

P110's split of `pads >= 3` (`jam` = the descent's `end > 15 mm`, `over-closure` =
`aper < dia - 4 mm` or `F > 4 cap 1.5`, `clean` = the rest):

| arm | cage rows | pads `0:1:2:3:4` | raw `>=3` | **clean** | jam | over |
|---|---|---|---|---|---|---|
| **R** rigid `k=1e5` | 76 | 17:27:19: 6: 7 | 13 (17.1 %) | **3 (3.9 %)** | 6 | 4 |
| **T1** soft 1e3 + stop | 73 | 10:24:28: 3: 8 | 11 (15.1 %) | **0 (0 %)** | 11 | 0 |
| **T2** soft 5e3 + stop | 77 | 14:29:30: 3: 1 | 4 (5.2 %) | **1 (1.3 %)** | 0 | 3 |
| **T4** scoped 1e3 + stop | 75 | 20:20:30: 2: 3 | 5 (6.7 %) | **2 (2.7 %)** | 2 | 1 |
| **S1** pure soft | 37 | 3: 9:19: 2: 4 | 6 (16.2 %) | **0 (0 %)** | 1 | 5 |

**The modal pad count is 2 in every arm** - the V-block - and 0/1 are common: the
ring is *not* enclosing at any stiffness.  Two things follow.

* **The endpoint is force-thresholded, so it is not stiffness-invariant.**  A pad
  counts at 0.5 N, which a soft drive reaches only at `0.5/k` of penetration
  (0.5 mm at `k = 1e3`, 0.005 mm at `k = 1e5`).  The raw `>=3` share therefore
  *falls* with compliance (17.1 -> 5.2 %) at the same aperture - part of that is a
  **measurement bias against the compliant arm**, and it is stated rather than
  read as a result.  The bias does not rescue the hypothesis: the *clean* count is
  3/76 in the best arm either way.
* **Why the pair never loads** is the geometry of §1: the aperture is
  `0.98 x` the widest extent, so a fruit with 2-20 % roundness leaves the
  perpendicular pair 1-6 mm short.  The clean enclosure is not something the
  closure can win at this aperture; P108's 200 mm already pays the approach.

### 4.2 The centring does not happen (F1 fires)

`off0 -> off` on the **in-ring** rows (`off0 < 20 mm`), i.e. the rows where the
ring was on the payload at all:

| arm | in-ring rows | `off0` p50 | **median `off - off0`** | p90 | > 5 mm | < -2 mm |
|---|---|---|---|---|---|---|
| R rigid | 25 | 2.9 mm | **+0.2 mm** | +10.0 | 4 | 2 |
| T1 soft 1e3 | 46 | 3.1 mm | **+1.9 mm** | +5.6 | 8 | 2 |
| T2 soft 5e3 | 56 | 2.9 mm | **+0.7 mm** | +3.6 | 5 | 2 |
| T4 scoped 1e3 | 50 | 3.0 mm | **+2.0 mm** | +12.1 | 7 | 1 |
| S1 pure soft | 30 | 3.1 mm | **+1.3 mm** | +3.3 | 1 | 1 |

**No compliant arm pulls the payload in**; the median change is *positive* in all
of them, i.e. the payload is carried slightly *away* from the ring's axis during
the close, and `T1`/`T4` do it more than the rigid ring.  F1 (a 1.5x fall in
`off`) **fires**.

The offset is also **not the 8.8 mm the registration assumed** (`PREREG_A1`
records this): 8.8 mm is P108's *aim* offset, and the catch-up has already
removed it - the close-time offset is **2.9-3.1 mm p50**.  That makes the
falsifier *stronger* than registered, and it fires anyway.

### 4.3 The count does not rise (F4's clause)

| arm | s5 | s6 | s101 | s202 | pooled | rate |
|---|---|---|---|---|---|---|
| **C** shipped hand | 12/19 | 13/19 | - | - | **25/38** | **65.8 %** |
| **R** rigid cage | 7/19 | 6/18 | 3/20 | 3/19 | **19/76** | **25.0 %** |
| **T1** soft 1e3 + stop | 1/20 | 1/15 | 5/19 | 5/19 | **12/73** | **16.4 %** |
| **T2** soft 5e3 + stop | 3/20 | 5/20 | 4/18 | 6/19 | **18/77** | **23.4 %** |
| **T4** scoped 1e3 + stop | 3/19 | 4/19 | 3/18 | 3/19 | **13/75** | **17.3 %** |
| **S1** pure soft | 2/18 | 3/19 | - | - | **5/37** | **13.5 %** |

Exact two-sided Fisher, pooled: **R vs T1 p = 0.229**, **R vs T2 p = 0.852**,
**R vs T4 p = 0.320**, C vs R **p = 0.000**; T2 vs T4 p = 0.423, T1 vs T4 p = 1.0.

**Read it as the tree says to.**  (a) The *sign* is the registered one - no
compliant arm beats the rigid ring - but **none of the differences is
significant at n = 75**, so the phase claims **no count loss**, not a loss.  (b)
The *seed-5 pair alone* reads R 7/19 vs T1 1/20 (p = 0.020) and would have
over-stated the effect 5x: seeds 101/202 read T1 5/19 **twice**, i.e. the same
branch class as the rigid control.  This is P93's rule again and it is the reason
the battery is four seeds.  (c) The cage family is at **13-25 %** against the
shipped hand's **65.8 %** (p < 1e-4): the phase's comparison is *within* the cage,
and the cage's own deficit is P107/P108's (the arm-never-arrived class, §4.4).

### 4.4 The class: the ring is a V-block, and the arm-never-arrived class is the cage's

`off0` splits every cage attempt in two: **in-ring** (`off0 < 20 mm`, the ring was
on the payload) and **off-ring** (85-1336 mm - the pads and the payload are not in
the same place, which is the cage's acquisition class).  The off-ring share is
**13/38 (34 %) R**, 27/73 (37 %) T1, 21/77 (27 %) T2, 25/75 (33 %) T4, 7/37 (19 %)
S1 - statistically the same everywhere, and *pre-existing*: it is the class P107
measured as "M2b's mechanism fails" and P108 as the blocked-descent jam.

The grip, on the `grasp_lift` legs (`[carry]`): 64/74 seated on R, 61/71 T1,
64/77 T2, 59/75 T4, 28/37 S1 - again the same.  The seated legs' `force_min`
median is **0.00 N** on every compliant arm against R's 0.00 and the shipped
hand's 9.02: the cage's pinch is *intermittent* in every arm, and compliance does
not change that.  The hard stop **does** work when the payload is seated: the
seated legs' `fmax` reaches the cap (9.3-9.9 N) on T1/T2/T4 exactly as on R.

### 4.5 The force at the freeze: the one thing compliance changes

| arm | force at the close's flush (two loaded pads) | note |
|---|---|---|
| R `k = 1e5` | **9.74 / 9.78 / 8.74 / 9.83 N** (the cap) | the shipped launch |
| T1 `k = 1e3` | **4.42 / 6.63 / 3.54 / 3.80 N** | `min(k*s, cap)` = a spring |
| T2 `k = 5e3` | 9.76 / 6.84 / 4.24 N | in between |
| T4 scoped | 7.31 / 4.74 / 3.87 / 5.62 N | the close window |

So compliance *is* a gentler contact - the mechanism the phase wanted - and it is
**not enough to convert anything**, because the contact is already a V-block and
the payload is not between four springs.

## 5. The decision rule, clause by clause

| clause | registered | measured | verdict |
|---|---|---|---|
| **1** the clean enclosure rises | > 0 on a compliant arm | 0/73, 1/77, 2/75 against R's 3/76 | **fails** |
| **2** the count does not fall | >= R | 16.4 / 23.4 / 17.3 % against 25.0 % (all n.s.) | **passes literally, no rise** |
| **3** no new failure form | the baseline set | `fruit did not follow the gripper` + the pick-station note in every arm, **no new key** | **passes** |
| **4** no crush | `sep@loss - dia >= -15 mm` | **0 legs** on every arm; the cap bounds the force by construction | **passes** |
| G1 landing | `on_belt` on every payload-present release | R 16/28, T1 12/40, T2 18/39, T4 7/15 (the misses are the `release_bottom = -184 mm` upstream-lost class, reported separately) | fails by the letter on the upstream class, as P86/P87 record |
| G2 crush | as clause 4 | 0 | passes |
| G3 budgets | the descent's `|v|max` | **fails on the cage arms, the rigid control included** (0-4 legs per cell; T1_s5 3, T4_s5 2, R_s202 4, R_s5/T2_s5/S1_s5 0) - the plates block the descent (P108), the budget was **not** re-tuned | fails, arm-independent |
| G4 slots | no lost slot | cells read 15-20 attempts: the off-ring class costs slots in every cage arm (the 15-attempt T1_s6 is one) | fails, arm-independent |

**VERDICT: NOT ADOPTED.**  The registered win needs the clean enclosure to rise
**and** the count to rise; neither does.  The honest form of the result is the
*middle case the registration named*: compliance is a **real, gentle** activation
of the contact (the force at the freeze 4.90 -> 0.6-1.8 N) and **not** a centring
mechanism - and the reason is measurable, not speculative.

## 6. Why it cannot centre - three measured statements

1. **The ring is a two-pad V-block at every stiffness.**  The modal pad count is
   **2** in all six arms (19-30 rows of 37-77), including the rigid one, and the
   clean 4-contact state is 0-3 rows.  The four-spring balance the hypothesis
   needs **never forms**; what is left is a single loaded pair, and a pair has no
   centring symmetry - the near pad pushes, the far pad is not there, and the
   payload leaves along the free direction.
2. **The perpendicular pair cannot load at this squeeze.**  The aperture is
   `0.98 x` the *widest* extent, so any roundness `> s` (i.e. most of the pool:
   0.02-0.20 d against `s` = 0.005-0.015 d) leaves that pair short.  Loading it
   needs a deeper close, and the deeper close is the one P108 measured as the
   over-closure/crush class.
3. **At `mu > 1` even a loaded pair jams.**  `delta_inf = (2mu-1)s` with the
   measured `mu_pair` 1.25-1.46 is 1.1-1.9 s: the far pad stays short by
   `(2mu-2)s` = 0.2-0.6 mm *forever*, at any `k` and any cap.  A 3-jaw ring would
   close it (0.82 s); a 4-jaw ring cannot, and that is a statement about the
   *contact count*, not the drive.

The phase's by-product is the **instrument**: `off0` shows the close-time offset
is **2.9-3.1 mm p50**, not P108's 8.8 mm aim, and it separates the cage's
arm-never-arrived class (85-1336 mm) from the rows that can say anything.  Both
are now cheap (two reads per attempt) and permanent.

## 7. Deviations

* **D1 - the registered reference was the aim, not the close.**  `PREREG.md` §1/§5
  use P108's **8.8 mm** as the arrival; `PREREG_A1.md` (pinned before any
  treatment cell) corrects it to the phase's own `off0` (**2.9-3.1 mm p50**) and
  keeps every rule.  The falsifier is therefore *stronger* than registered, and it
  still fires.
* **D2 - `off` carries the ring's own tracking lead.**  The task commands the jaw
  centre at `payload + v*lead` (`FRUIT_DYNAMIC_TRACK_LEAD` 0.18 s), so `off`
  includes a ~21 mm commanded lead achieved to a few mm; it is a **relative** read
  across arms under the same law, not an absolute payload-to-pad guarantee.  The
  `off - off0` change is the cleaner form and is what §4.2 reads.  F5 (the
  model's absolute 0.8-1.3 mm) is **not evaluable** on this instrument and is
  recorded as such, not passed.
* **D3 - T2's damping is 0.7x the registered value.**  `PREREG.md` §2 states
  `c = 2 sqrt(k m)` and gives 14.1 Ns/m for `k = 5e3`; the correct value is
  **20.0**.  The arm ran at 14.1 (ζ = 0.70).  T2 is the *dose check*, not the
  registered point, and its numbers are reported, not gated - but the arm as run
  is under-damped against its own registration.
* **D4 - the clean-enclosure endpoint is force-thresholded.**  A pad counts at
  0.5 N, which a soft drive reaches at `0.5/k` of penetration, so the raw `>=3`
  share is biased *against* the compliant arms (17.1 -> 5.2 % at equal aperture).
  The phase states the bias and does not read the raw count as a result; the clean
  subset is 0-3 rows either way, so the bias does not decide anything.
* **D5 - the descent budget fails on the cage arms including the control** (0-4
  legs per cell, `R_s202` the worst at 4) and the grader's rate clause fails with
  it.  Not re-tuned (AGENTS §2): it is the cage's blocked-descent class (P108's
  `end` p50 57.9 mm on one seed), and it is identical in the arms the phase
  compares.
* **D6 - the battery is 4 seeds but the controls' `S` is 2.**  P108's `S` cells
  are 5/6 only and `E` is 5/6/101; the phase re-ran `R_s202` to close the rigid
  arm at 4 seeds, and the shipped hand stays at 2 (it is the *reference*, not an
  arm in the comparison).

## 8. What shipping a compliant hand would owe (it is not licensed)

**A compliant pad is a hardware change, and the phase's answer is what it would
have to be.**  The sim's drive is a spring; a real gripper would need either

* a **spring-loaded pad with a hard stop** - a die spring behind the pad face and a
  shoulder that bottoms it out: the form modelled here, which delivers the gentler
  close *and* the shipped hold, and which by itself converts nothing, or
* a **force-controlled finger** - a load cell and a current loop, so the pad tracks
  a position command until the force exceeds a threshold and then holds a force.
  That is the only form that can be **stiff during the approach and compliant only
  inside the closure**, which is what §4.4 shows is required (the always-soft pad
  is a poor position source: T1's first cell read 1/20 and the off-ring class grew).

Neither is worth it for **this** ring, and the phase's numbers say why: 0-3 clean
enclosures in 76 attempts, a V-block at every stiffness, and a count that does not
move.  The levers below the ring, in the order the algebra prices them:

1. **A pad material with `mu < 1`** - then `delta_inf = mu s < s` and the *four*
   jaw would centre.  The sim's pad is `mu = 2.0` because the shipped finger
   material is; a low-friction pad is a *material* change and would cost the axial
   capacity (`F_crit = n mu N`).
2. **A three-jaw ring** - `delta_inf = 0.82 s`, i.e. it centres at the measured
   `mu`; it is a *different hand*, and P104's four-contact capacity argument is
   what pointed at four in the first place.
3. **A positioning change** - P110's 0.6 mm, which no passive element on this line
   delivers (its own best is 1.8 mm within a fruit / 17.5 mm across the pool).

`configs/` is untouched: `configs/motion_reference.json` = `..._twoline.json` =
**`30fb99f8`** and `..._single.json` = **`8952c320`** all stand, and nothing in
`src/` changes the shipped path (`FRUIT_GRIPPER_KIND` unset is byte-identical, §0).

## 9. Files and pins

`logs/p111/{METHOD.md,PREREG.md,PREREG_A1.md,PREREG.md5,RESULTS.md,algebra.py,
algebra.txt,census.py,census.txt,enclosure.txt,cells.sh,p111_report.py,
run_p111.sh,stream_{a,b,c,d}.log}` and the cells
`{C,R}_s5`, `R_s202`, `{T1,T2,T4,S1}_s*` (+ their `.tmp` drivers removed).

Pins: `cage_hand.py` (the two windows + the calibrated `_profile` guard),
`tasks.py` **`a587cd21`** (the two call sites + the `[cage] off0/off` fields),
`cage_hand.py` **`ac7c7c0f`**, `rl_env.py` (the metadata-only follow),
`scripts/257_p111_cage_compliance_selftest.py` (the selfcheck leg),
`scripts/selfcheck.sh`; references **`30fb99f8`** / **`30fb99f8`** / `8952c320`;
ckpt `moe_v13s` `61da390a`.  Evidence `logs/p111/`.
