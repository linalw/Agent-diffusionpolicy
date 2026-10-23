# P33 phase 2 — the acceptance's red rate: the carried-not-placed census, the mechanism, and the closed lever register

Measured **offline** 2026-10-23 on the P32/P33 tree (P32 phase E `adbea18` + the
P33 phase-1 working tree, whose acceptance is byte-identical to `D1`). No
simulator run, no shipped default changed, no commit.

Re-derivation: `python3 logs/p33/carry_census.py` -> `logs/p33/50_carry_census.txt`
(reads only; the population and its identities are listed in §1.1).

---

## 1. The census

### 1.1 The corpus (the current tree only)

The **acceptance/battery logs of this tree**, deduplicated to distinct branches.
The P33 pump arms (`logs/p33/11`, `21`) are **excluded** by instruction (a
different branch *and* cadence); the P33 controls (`10`, `20`, `00`, `40`) are
included and turn out to be replays, so they add no episodes.

| family | distinct logs | attempts | placed | carried-not-placed | no-grasp |
| --- | --- | --- | --- | --- | --- |
| acceptance, pear-on (shipped scatter) | `80`=`89`=`93`=`D1`=`00`=`40` | 10 | 6 | **3** | 1 |
| acceptance, pear-off control | `92`=`81` | 10 | 7 | **3** | 0 |
| pear battery, species-locked | `90` (new) + `91` (old profile) | 18 | 12 | **6** | 0 |
| bed battery, single arm | `72`, `77`, `79`, `87`=`20`, `88` | 70 | 37 | **21** | 12 |
| bed battery, two-line | `A0`=`A1`=`A3`=`10` | 20 | 12 | **1** | 7 |
| shared-station bimanual acceptance | `E1` | 10 | 8 | **2** | 0 |
| **distinct carried-not-placed episodes** | | | | **36** | |

The acceptance's red rate is exactly its left-lane attempts: pear-on per arm
**left 1/5** (3 carried-not-placed + 1 no-grasp) and **right 5/5**; pear-off
**left 0/3**, **right 7/7**.

The pear-on branch's four failures are attempts 0-3, all `left` and all before
its first right-arm attempt - an **arrival/seed artifact of that branch, not an
ordering effect**, so do not read it as "the left fails cold". Anchor on the
branches where the arms are interleaved instead: pear-off **ep0/4/6** (kiwi
failures with right placements on either side) and the pear battery's
**ep4/5/6/8**, where the same class recurs between right placements.

The census's `[identical to ...]` labels are **episode-level** - the key is
`(episode, species, grasped, placed, lift, force)` per attempt
(`carry_census.py` `main`) - not whole-file hashes. The byte-level identity
claims are the separate `[fruit]`-line proofs: P33 phase 1's acceptance
**374/374** to `D1`, two-line control **826/826** to `A0` and single-arm
**436/436** to `87`, plus P32's **376/376** `93`-vs-`D1` and **381/381**
`81`-vs-`92`. The remaining replays above are episode-identical only.

### 1.2 The class is the lane-0 (left) configuration - 33/33 of the carried-not-placed episodes

`scripts/20_pick_place.py` maps grade A -> lane 0 -> the **left** arm and every
other grade -> lane 1 -> the **right** arm (`tasks.py:4453`,
`_prepared_lane`), and the **grade is a label, not a property of the fruit**
(`fruits.py:3`: "Fruit quality attributes (grade, ripeness, defects) are NOT
perceived"; the grade vector is allocated then shuffled over the pool,
`fruits.py:844-852`). Arm, **mount** and output lane move **together** in this
corpus (the left places onto output belt 0 at `y ~ +0.50`, the right onto belt 1
at `y ~ -0.50`, each from its own mount), so the census measures the *bundled*
left configuration and cannot say which of the three is the term. What it can
say is that the **fruit** is not
the term (the pear battery holds species and size fixed across the arms).

Per family (distinct logs; `att/placed/cnp/no-grasp`):

| family | left | right |
| --- | --- | --- |
| acceptance, pear-on | 5 / 1 / **3** / 1 | 5 / 5 / 0 / 0 |
| acceptance, pear-off | 3 / 0 / **3** / 0 | 7 / 7 / 0 / 0 |
| pear battery | 8 / 2 / **6** / 0 | 10 / 10 / 0 / 0 |
| bed battery, single arm | 44 / 11 / **21** / 12 | 26 / 26 / 0 / 0 |
| **single-arm line total** | **60 / 14 / 33 / 13** | **48 / 48 / 0 / 0** |
| bed battery, two-line | 10 / 6 / **0** / 4 | 10 / 6 / 1 / 3 |
| shared-station bimanual | 5 / 3 / **2** / 0 | 5 / 5 / 0 / 0 |

**Quote the incidence, not the totals as rates.** The 60/48 columns pool five
single-arm branches over **two supply schedules** (the bed battery alone supplies
44 of the 60 left attempts) and the bed branches are **near-replays** of one
another (their shared attempts repeat episode-for-episode), so "14/60 = 23 %" and
"48/48 = 100 %" are not rates. The census statement is **33 of 33
carried-not-placed episodes on the left, 0 of 48 on the right**, with the
per-family counts above.

The pear battery is the species- and size-controlled cross-check (one species,
the two arms' picks interleaved at 5.8-6.9 cm): **left 2/8, right 10/10**
(`90`: left 1/4 - a 6.1 cm pear placed, 6.1/6.0/5.9 lost; `91`: left 1/4 - a
6.0 cm pear placed, 6.0/6.3/6.4 lost, i.e. the *same 6.0 cm* fails on one
attempt and places on the next, and the right places 5.8-6.9). The
mixed-corpus diameter split is *not* a separation -
left `<=4.0 cm` 7/8 but `4.1-5.9` 0/10 while `5.9-6.4` 7/25 - so the class is
not "big fruit" or a species; it is the left lane's configuration.

The two-line is a different station: its left (`y=0.00`, station-specific
pre-pose - **same arm, same hand, a different grasp/transfer configuration**)
reads **0/10 carried-not-placed but 4/10 no-follow**, i.e. **6/10 placed with 0
cnp**, against the single-arm bed's left **11/44 placed with 21 cnp** on the
same bed supply (counts, not a rate comparison - two different configurations
and two different branches). The class *moved* (cnp -> no-grasp) while the rate
did not improve, and a cnp-only endpoint would have scored this as a win: quote
it as a lead, not a fix. Its one carried-not-placed (right pear, lift +0.089 m)
has a **10.9 s** span, the shortest of all 20 attempts (its placements run
12.8-17.2 s) - the adopted two-line monitor's fast-skip signature, not
confirmable here (its diag was off).

### 1.3 The long-standing record

The class is not new and not the pear's. Every 9/10 acceptance record's **single**
failure is the same left-lane attempt-0 kiwi (`logs/v1/20_rate_supply_1.log`,
`logs/w3/62_accept_single_dense_tree.log`, `logs/w6/60_accept_w6c.log`,
`logs/r8/A_accept.log`: kiwi A 5.4 cm, lift +0.221 m, force 4.26 N - the same attempt
lines). What moves the acceptance's count is **how many of the left's attempts
escape on that branch**: 1 in the 9/10 records, 3 in the pear-off control
(`92`, the pre-P32 branch), 3+1 in the pear-on branch. Per AGENTS §2 these are
different attractors, so the count is a branch label - the *class* is the object.

---

## 2. The mechanism

### 2.1 Per-episode evidence (the acceptance, pear-on; `logs/p32/93_accept_raw_pear_on.log`)

| ep | fruit | dia | arm | lift | close force | fruit at release `(y,z)` | outcome |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | peach A | 6.5 | left | +0.135 | 4.51 N | `(-0.903, 0.044)` | carried-not-placed |
| 1 | peach A | 6.9 | left | +0.278 | 4.41 N | `(-0.820, 1.196)` | carried-not-placed |
| 2 | kiwi A | 5.6 | left | +0.175 | 4.45 N | `(-0.922, 0.030)` | carried-not-placed |
| 3 | orange A | 6.4 | left | +0.001 | 0.00 N | - | no-grasp ("fruit did not follow the gripper") |
| 4-8 | lychee/strawberry/pear/orange/apple B-C | 3.4-7.0 | right | +0.312..+0.442 | 4.43-6.46 N | lane 1, `z=1.36-1.38` | placed |
| 9 | lychee A | 3.0 | left | +0.318 | 21.25 N | `(+0.577, 1.364)` | placed |

The three carried-not-placed episodes leave the payload **on the main belt or on
the floor beside its end**, not at the place pose: at the place-leg end the log
reads `fruit=[0.22,-0.60,1.197]` (ep0) against `jaw=[0.427,0.495,1.513]`, and the
per-leg clearance row reads **`lowest payload point -215..-219 mm to the output
rail`** (the rail top is 1.35) on **11 of the 12** instrumented left failures,
`-11 mm to the main belt` on the twelfth (`91` ep3) - **12/12 the payload is on
the main belt at the place leg's end**, the row's reference object being the
output rail in 11 and the main belt in 1 - and on **none of the 25**
instrumented placements (`+24..+89 mm`).

The printed `released at [x,y,z]` is the **fruit's world position** at the
release tick, not the hand's commanded release pose: `z = 0.030-0.051` is the
floor beside the belt and `z = 1.196` a fruit resting on the main belt, i.e. the
jaws open on a payload that is already down.

The left-lane success (ep9) and the pear battery's two left successes carry the
same signature inverted (`-217` -> **`+24..+59 mm`**).

### 2.2 The frame-free leg read (no diag needed)

`in-hand |v|max` (the payload's relative motion; frame-free by construction,
AGENTS §2) separates the legs, and the `slip_max` column must **not** be quoted
(W8-B §1: frame-contaminated, 25.6-104.7 mm of ghost slip on placed carries):

| leg | placed legs (n) | carried-not-placed legs (n) |
| --- | --- | --- |
| `grasp_lift` | 0.041-0.300 m/s (25) | **0.343-2.022 m/s** (12) |
| `place0/1` | 0.069-0.182 m/s (25) | **0.447-2.035 m/s** (12) |

The one instrumented no-grasp leg (no payload ever) reads 4.760 m/s and is a
separate class. The escape is therefore a **loaded slide of the payload in the
pinch**, started on the lift in 12/12 instrumented cases (the lift value alone
is outside the placed band) and converted on the place leg in the ones that
survive the lift.

### 2.3 The consequences the recipe does not handle

* the scripted carry **never re-seats or aborts**: `recoveries=0` on all 24
  instrumented failure legs, and the arm completes the full profile;
* the force servo (on, `ref=4.00 N`) chases the empty jaw to its minimum -
  `F[0.00, x]`, `gap == sep`, `closed=15.00-17.80 mm`, `trips=38-52` on every
  failure, against `F[3.02,4.98]`, `closed=0.00`, `trips=0` on every placement.
  This is the R11-A.1 `F_min = 0` signature - a **consequence**, printed after
  the release, not the cause;
* the close geometry is **not** the discriminator: `kinematic grip closed to X cm
  around a Y cm fruit` gives a median closed-span-minus-diameter of **+0.20 mm**
  on the placed left legs (n=14, +0.06..+0.30), **+0.12 mm** on the
  carried-not-placed legs (n=33, -0.55..+0.63) and **+0.14 mm** on the placed
  right legs (n=48, -0.46..+0.73) - the ranges overlap completely, so the grip
  is *not* being closed looser on the failures (the R6-B "the commanded
  interference is physically inert" conclusion reproduces; its 11.9 mm median
  is the *commanded* pad centre vs the measured span, a different quantity,
  not comparable to these numbers). The close force is normal (4.02-4.53 N) on
  every failure.

### 2.4 The arm correlate: the left's transfer is longer and its wrist is the extreme one

The two arms do **not** execute the same transfer on the same symmetric target
pair (`jaw_target` place0/1 = `(0.43, +-0.50)`). Split **within** the left, and
mark the right as placements-only (it has no failure to split against); the four
acceptance/pear-battery logs:

| leg | left placements (n=3) | left carried-not-placed (n=12) | right placements (n=22) |
| --- | --- | --- | --- |
| `place` distance | 53-58 cm | **50-63 cm** | 32-41 cm |
| `place` ticks | 349-384 | **329-413** | 209-272 |
| `grasp_lift` | 21-22 cm / 161-173 t | 20-21 cm / 157-166 t | 21-23 cm / 160-178 t |

(The one no-grasp leg - 28 cm / 217 ticks on its lift, no place leg - sits
outside all three columns.)

The place leg is `distance = ||jaw_target - pad_centre||` and both arms' targets
are symmetric, so the difference is in the arms' own transfer solution - the
documented left-arm behaviour in exactly this pose: "over the output line the
left arm's solve swings the tool to **93.6 deg from vertical** - the flattest
posture in the cycle" (`tasks.py:2765`, `logs/428`), with the place point sitting
at the reach boundary (0.4065 m from the shoulder vs the measured ~0.41 m,
`assets.py:365-375`). **Correlate, not an isolated cause**: within the left the
placements run 53-58 cm and the failures 50-63 cm - the ranges **overlap**, and
the failures include both the longest and the shortest left legs, so length
alone does not separate.

### 2.5 What the acceptance logs do not carry (the one named missing datum)

No `[carry]` rows in **any** of the corpus logs (`FRUIT_CARRY_DIAG` was never
set; the two-line's adopted monitor prints counts only behind its own diag) and
no `[acq]` rows (direct-path only): the **onset row / force@onset / single-sided contact / contact-loss delay**
are not in these logs. The mechanism's onset facet is therefore quoted from the
W8-B trace corpus on the same OpenArm hand (`logs/w8/B_RESULTS.md` §2: onset
force 0.45-12.9 N, median **4.90 N**; **single-sided** contact at the onset;
`sep` pried to **98-99 mm** in **17/31** escapes; contact loss **2-132 ticks**
after the 2 mm crossing, median **25**). One acceptance re-run with
`FRUIT_CARRY_DIAG=1` would put the onset tick on the shipped branch; it is a
*diagnostic*, not a lever, and it cannot change the verdict, so it was not run
(the diag takes a per-tick payload/jaw read, so it is not proven run-neutral).

---

## 3. The register: the carry-class levers on the scripted single-arm line, and their measured verdicts

**Scope.** The rows below are the carry-class lever families read against the
carry class, on the scripted single-arm line where they apply (the direct-only
and policy-side rows are quoted for the record). Three families measured in
other scopes are named in §3.1 rather than tabulated: the **close-side P15-M2**,
the **trigger-side M1/M1c**, and the **R3 §4 belt-speed screen**.

| # | lever (env) | scope | verdict | citation |
| --- | --- | --- | --- | --- |
| 1 | **W8-B carry guard** `FRUIT_CARRY_GUARD` (hold + 20 mm re-seat + derate) | **direct only** (`_carry_guard_active` needs `direct_capture`) | carried 50 -> 42, paired 5-1, sign **p = 0.109**, cycle **+5.4 %** (1856 -> 1957 t) -> **not adopted**; R6-B retune (`HOLD=8,RESEAT=60,DERATE=0.8`) 46 -> 44, **3-1, p = 0.3125, +4.5 %** -> **not adopted**; the 100-400 mm band converts **0/37** | `logs/w8/B_RESULTS.md` §3, `logs/r6/B_RESULTS.md` §3 |
| 2 | **R6-B carry relief** `FRUIT_CARRY_RELIEF` (interference cap) | direct only | command released to 0.5 mm interference, **force unchanged (Fmin 4.15-4.47 N)** - the squeeze-side family closed by measurement | `logs/r6/B_RESULTS.md` §2 |
| 3 | **R8-A D2a lower grip plane** `FRUIT_GRIP_PLANE_DROP` (-8 / -4 mm) | scripted | escape persists, population **moves up** (10 legs >400 mm), flails 1 -> 14, battery **12/20 -> 5/20** x2, one descent out of budget -> **FAIL** | `logs/r8/A_RESULTS.md` §2 |
| 4 | **R8-A D2b cradle/scoop** `FRUIT_FINGER_SCOOP` | scripted | the ledges **bat the payload** (no-contact 2 -> 9), slide events to 3972 mm, **12/20 -> 6/20** -> **FAIL** | `logs/r8/A_RESULTS.md` §3 |
| 5 | **R8-A D3 nest** `FRUIT_NEST=0.02` | scripted | the platform obstructs the moving supply, `recirculated` 0 -> 13, a new "never settled" note, **12/20 -> 1/20** -> **FAIL**; D3-proper (station + self-centring feeder) stays the owner-gated scenario redesign | `logs/r8/A_RESULTS.md` §4 |
| 6 | **R9 AWR post-training** (`rl_awr1`) | direct/policy | **25/75 vs 18/75**, carried-class paired **5-4, p = 0.500**, cycle +1.5 % -> **negative, published**; the carry window is branch-invariant (onset force 4.9/5.4 N), the post-training moved the *handover* instead (6 vs 1 flails) | `logs/r9/RESULTS.md` |
| 7 | **P3 place shortening** `FRUIT_PLACE_INNER_SHIFT` | scripted | the kinematics work (-9 cm, -60 ticks) and the rate **collapses 18/20 -> 6/20**: the release already sits 35 mm inside the belt's inner edge, so the max safe shift is ~30 mm = **~0.2 s, 1.3 %** of the span -> **geometry-closed** | `logs/p3/RESULTS.md` |
| 8 | **R11-B C1 close-load rate** `FRUIT_CLOSE_LOAD_RATE=0.04` (dynamic-capture scoped: the acceptance *does* reach it) | scripted + direct | **converts on the direct interface (class-stratified exact p = 0.0026); scripted negative; the class-matched direct re-run is open** (`B_RESULTS` §5). Scripted: patch stage-P **12/20 vs 13/18** (never-grasped 0 -> 5) and two-line **28/60 vs 45/60** (nc 8 -> 25) -> does not transfer to this line. Direct: carried **48 -> 27**, ok 22 -> 39, MH OR 1.79, CMH chi2 8.68, all 5 B runs beat all 5 A runs; the pooled 22/75-vs-39/74 **p = 0.500** was the *episode-pairing* endpoint (58/74 unpairable), which Gate 3 names a **protocol weakness**, not the lever's verdict | `logs/r11/B_RESULTS.md` §5/§7, `logs/p18b/B_RESULTS.md` §4/§5, `logs/p20/ORACLE_GATE3.md`, `.slim/deepwork/sorting-pipeline-v3.md` "P20 BATCH ORACLE GATE 3" |
| 9 | **C-3 carry monitor** `FRUIT_CARRY_MONITOR` (the fast-skip) | direct; two-line behind `_TWOLINE` | direct: interval **-21.8 %** and 43/43 fires on escaping legs, but **B2 lock-on +8.8 % > +5 %** -> not adopted; two-line: **adopted** with `CONFIRM_MM=8` (P10-C.3), multi-seed mixed on outcomes. **The single-arm scripted catch never arms it** (`_carry_monitor_active = monitor and (direct_capture or (two_line and _TWOLINE))`, `tasks.py:8093`) and its action is a *fast-skip* (throughput), not a conversion | `logs/p7c/B_RESULTS.md`, `logs/p8`, `logs/p10c/PREREG_CONFIRM_GATE.md`, `logs/p10c` |
| 10 | **P17-B slide gate** `FRUIT_DYNAMIC_SLIDE_GATE` (hold/pry-1 re-centre) + the two-sided freeze gate | direct | mechanism win (the s11 arrest/walk read) / outcome **negative**: pooled **45/60 -> 37/60** ok, carried **7 -> 13**, 3/3 seeds worse -> **not adopted** | `logs/p17i/P_RESULTS.md`, `logs/p17i/SCREEN_RESULTS.md` |
| 11 | the **short-tip finger / new pad form** | hardware | **not built, owner-gated**. The mechanism (a loaded slide out of the pinch, jaws pried to the jaw limit) is a form-closure problem, so a passive lip / a shorter tip the payload cannot walk past is the only unmeasured *form*; it needs an asset + a battery + its own reference | `logs/r7/FRONTIER_R7.md` §4 (D1/D2), README "Known limit" |
| 12 | **D3-proper** (a reachable station clear of the belt + a self-centring feeder + a descent that respects the boundary) | scenario/hardware | **owner-gated**, out of scope for this phase; the naive raise is closed (#5) | `logs/r7/FRONTIER_R7.md` §4 (D3), README "Known limit" |

**The one doc fix owed, and the only one:** the `AGENTS.md` R11-B paragraph - the
"stage-N stopped incomplete / C1 unconfirmed" text - predates the Gate-3
re-analysis and is rewritten in this remediation to the `B_RESULTS` §4 verdict.
The W8-B/R6-B cycle-cost attribution the first pass listed here needs no fix:
`AGENTS.md` already reads **+5.4 %** for W8-B (line 761) and **+4.5 %** for
R6-B's retuned guard (line 876).

### 3.1 What is *not* in the register, and why

* **The other actuator families, measured in their own scopes**: the close-side
  **P15-M2** lead (`logs/p17i/P_RESULTS.md` §1) and the trigger-side
  **M1 / M1c** gates (`logs/p17i/P_M1C_RESULTS.md`; the gate fired on 9 attempts
  and converted 0 - a loss detector, not a recoverable-state detector, and M1c is
  M1's *threshold variant*, not a new family: `logs/p20/ORACLE_GATE3.md`). They
  are carry-adjacent rather than carry-class levers on this line, and both are
  negatives of the same shape (the mechanism moves, the outcome does not).
* **The belt-speed screen** (`logs/w8/R3_RESULTS.md` §4: 0.12/0.15/0.18 m/s, the
  two-line patch battery): it moves the arrival structure and the interval
  (3.63 -> 4.69 -> 3.82 placed/min), not the carry class, and it is two-line
  scoped and owner-gated.
* **`FRUIT_CARRY_HOLD_QUAT=1`** - built but **never measured** (`tasks.py:2763-2772`:
  the wrist is held at the attitude the grip was taken with through the carry,
  "off by default until measured"; the unheld solve is the left's 93.6 deg
  over-the-line posture). It is a bounded wrist-attitude lever on the §2.4
  correlate and belongs in (C)'s pre-registration, either as its own arm or as
  the same candidate's second term.
* **A lane swap / routing change** (send grade A to the right arm) would test
  arm-vs-fruit directly, but it changes the line's output semantics (which
  physical belt carries which grade) - an owner decision, not a lever, and it
  moves the problem to the other arm rather than removing the class.
* **A lane-0-specific pre-pose / grasp configuration** (the two-line's own
  mechanism: station-specific pre-poses, `tasks.py:_prepare_two_line_stations`)
  is the **only unmeasured bounded candidate this census surfaces**: the
  single-arm left's transfer is the long one (50-63 cm / 329-413 ticks on the
  carried-not-placed legs, 53-58 cm / 349-384 t on its placements) and its
  over-the-line solve is the documented 93.6 deg. It is a pose/IK change on the
  scripted single arm, offline-auditable, and it would need its **own
  pre-registration, its own acceptance re-record and a no-harm proof** that the
  right lane and the two-line are byte-unchanged.

---

## 4. Verdict

**The class is closed negative on the scripted single-arm interface, with one
measured exception the scripted line does not reproduce.** Ten lever families
have been measured against pre-registered gates - four scripted-applicable (R8-A
D2a/D2b/D3, P3), three dynamic-capture-scoped (the R11-B C1, the C-3 monitor, the
P17-B slide gate), two direct-only (the W8-B guard, the R6-B relief) and one
policy-side (R9 AWR). Nine do not remove the class on any interface measured (the
C-3 monitor is *adopted* on the two-line, but as a throughput fast-skip, not a
conversion). The tenth -
the **C1 load-side lever** - is **negative on all three scripted measurements**
(the decisive read for this line: 12/20 vs 13/18, 28/60 vs 45/60) and
**positive on the direct interface**: carried **48 -> 27**, ok 22 -> 39,
class-stratified exact **p = 0.0026**, all 5 B runs beating all 5 A runs
(`logs/p18b/B_RESULTS.md` §4; the pooled 22/75-vs-39/74 sign test was the
*episode-pairing* endpoint, which Gate 3 names a protocol weakness). So: the
scripted line's closure stands, the direct interface has a lever, and its
class-matched direct re-run is **open** (§4.1).

The measured mechanism is the W8-B loaded slide (a form-closure failure of the
fingertip pinch on this hand); the census adds that on **this line** the slide
is the **lane-0/left** transfer's, that it is **not** a pear, species, size or
close-force effect, and that the transfer geometry is the one measured
asymmetry left in the frame. The acceptance's 6/10 is that class on that branch;
the right lane places 12/12 across the two acceptance branches and 48/48 across
the single-arm corpus, **zero carried-not-placed in either**.

### 4.1 The recommendation (the owner's decision)

**(A) Accept the 6/10 as a documented owner exception - recommended.** The
acceptance is **rate-only red**: every **gated** budget passes (`D1`'s driver
reads `worst |v|max` 0.1100 against a 0.160-0.161 budget, lurch 0.017 against
0.291), the **reported** - not gated - held-grip cone is **1.27x**, the
fingerprint matches (`25ade92b`), the pear is not the cause (its own grasp/place
is 3/3), and the class predates P32 by months (the same attempt-0 kiwi in every
9/10 record).

This is an **exception, not a floor change**:
`scripts/105_motion_regression.py:205-208` sets the dynamic floor at **7.5/10**
and states that a 7/10 ship needs an owner exception rather than a lower floor.
**The floor is unchanged and the exception is granted explicitly**: 6/10 here,
and the **pre-existing 7/10 pear-off branch** (`logs/p32/92`) - which is also
below 7.5/10 and has been shipping as a control - are both accepted under it.
What the owner accepts with it: the shipped line sits below the floor **on this
scenario**, and `demo_2min.sh`'s 0/3 is the same branch's first three attempts.
Documenting it costs nothing and is honest; the reference is already the
branch's own (`configs/motion_reference.json`).

**(C) A bounded lane-0 transfer candidate - first, because it is lane-0-only.**
The lane-0 transfer configuration (§3.1): a lane-0-specific pre-pose/grasp
configuration taken from the two-line's own solved pre-poses, plus - if an
offline audit says it is the same term - the unmeasured wrist hold
`FRUIT_CARRY_HOLD_QUAT`. Measured as a paired scripted battery + the acceptance.
Its pre-registration must fix, before any asset is touched:

* **primary endpoint = the left's *placed* count on the same scenario**
  (equivalently the composite failure mass, carried-not-placed **+** no-grasp).
  Not the cnp count alone and not the in-hand band: the two-line lead shows why -
  it reads **0/10 cnp and still places only 6/10**, because 4/10 became
  no-grasp, so a cnp-only endpoint would pass a **class relocation**;
* **secondary**: the cnp count and the frame-free `in-hand |v|max` band (they say
  *which* mechanism moved, not whether the class shrank);
* **the offline kill first**: the candidate must demonstrably change the
  **pad-centre-to-fruit offset and/or the tool attitude at the close** (an
  offline IK/pose audit against the shipped pre-pose). If it does not, it is a
  null before any simulator time;
* fail conditions: a new failure reason, a gated motion budget, the right lane or
  the two-line stream moving; and its own acceptance reference.

**(B) The hardware form change - the global lever, second.** The right arm
places **48/48 at the same station with the same hand**, so the **hand form sets
the margin**; the two-line's left - **same hand**, `y=0.00`, a different
pre-pose - reads **0/10 cnp** while placing 6/10, so the **left's arm-specific
grasp/transfer configuration sets the incidence**. A form change (a passive lip
/ a shorter tip plate) removes the class mechanically - force (R6-B), the grip
plane, a scoop and a raised station are all measured closed - but it is
**global**: it re-opens the margin on the arm that is currently 48/48, so its
no-harm burden is the right's **48/48** and the two-line's **12/20** (6/10 left
with 0 cnp) on top of the asset change, the grasp battery, the re-record and the
owner's sign-off. That burden is why it is second, not because its mechanism is
weaker. **Any new option needs that pre-registration and its own re-recorded
`configs/motion_reference.json`; the shipped reference is per-scenario and
cannot certify a new branch.**

**Do not** re-run the closed levers as if they were untested. The one named
**open** item is the C1's **class-matched direct re-run** (`B_RESULTS` §5: the
tomato single-species pool collapsed to carried 13/15, a scenario artifact, and
the strawberry/apple probes are on disk) - a direct-interface item with no
scripted route on this line. And **do not** read a different branch's rate as an
improvement: the outcome is quantized, so the only test of any new option is the
class readout on the same scenario.

---

## 5. Provenance

* Tree: the P33 phase-1 working tree on `p-supply` (P32 phase E `adbea18`); the
  acceptance logs it reads are `logs/p32/{80,89,93,D1}`, `{81,92}`,
  `{90,91}`, `{72,77,79,87,88}`, `{A0,A1,A3}`, `E1` and the P33 controls
  `logs/p33/{00,10,20,40}` (all identified as replays by `carry_census.py`).
* Re-derivation: `logs/p33/carry_census.py` -> `logs/p33/50_carry_census.txt`.
* No shipped default changed; no commit; no simulator run.
* The Gate-2 remediation is **documentation-only** - the same logs, no re-run;
  `50_carry_census.txt` is the generator's own output and is unchanged.
