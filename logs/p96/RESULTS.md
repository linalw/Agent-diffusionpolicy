# P96 RESULTS - the clearance pre-pose restores the invariant; the count is a draw

Registrations: `logs/p96/PREREG.md` (md5 `bb057405aa020378739b4b8e21f5cdcb`),
`PREREG_A1.md` (`a2e63f604ef479afaaa4f7516e3bff5f`, the attitude extension) and
`PREREG_A2.md` (`724009a0a1b50ac4d86531a3daf44b79`, the control cells' reference),
all pinned before the runs they govern. Battery `logs/p96/run_p96.sh` →
`logs/p96/*.driver`; the map `prepose_map.py` / `prepose_check.py`; the readouts
`python3 logs/p96/pg_census.py` (→ `pg_census.txt`) and
`python3 logs/p96/p96_report.py` (→ `p96_report.txt`); gates
`bash logs/p96/gates.sh`.

**Verdict in one line: the left station **does** admit a clearance pre-pose
(jaw `belt_top + 0.160`, 0.020 rad of joint margin against the shipped pose's
**0.000**), the pre-leg pad
census goes from **4/40 within 6 mm and 1 contact to 1/40 and 0 contacts**, the
delivered count is a **draw** (17 -> 12 and 12 -> 15, pooled 29 -> 27 of 40; per
arm -1/-1), and the registered G3 clause - *no seed lower by more than one
placement* - **fails by its letter at seed 5**, so **nothing is shipped**: the
default stays off and the measured arm is `FRUIT_BIARM_PREPOSE_CLEAR=1`.**

## 0. The question, and the answer in the record's own numbers

P95 measured the defect (`logs/p95/RESULTS.md` §2-§6): the two-line pre-pose is
the **calibrated grasp configuration** at the arm's own station, its pads end
**29 mm below a fruit's top**, the pre-pose blend dives there on **every**
attempt, and the stations are ordered (`left y=+0.000` upstream, `right
y=-0.100` downstream on a `-y` belt) so a **right**-arm fruit must cross the
**left** station: 19 right-arm attempts read median pad approach 31.6 mm, min
0.0, 5/19 <= 6.4 mm, and **1 of 40 attempts was displaced** (`+0.402 m/s`,
21.6 rad/s of spin, the left jaw span knocked 98.0 -> 59.8 mm and springing
back) into a `never_held` close.

P96 asked the prior question: **can the station hold a pose that clears the
band?** The registration's criterion is P95's own (`jaw_z >= belt_top + 0.155`,
i.e. the pad point at `belt_top + 0.0745`), and its falsifier F1 was "if no cell
reaches it, the answer is the transit path or the station geometry, and no
battery is spent".

**F1 does not fire.** Both stations admit a clearance pose, and the pose that
admits it is the shipped attitude raised - see §1.

## 1. Phase 0 - the offline map: the station admits the pose, in two of four forms

`logs/p96/prepose_map.py` (36 grid cells per arm: `x` 0.32/0.34/0.36, depth
0.095-0.20, two modes) and `prepose_check.py` (the attitude, the static pad
witness, `restarts = 3`). The seed matters and the registration's `A1` says why:
`configs/waypoints_oriented.json`'s `arms.<side>.grasp` (P66's recipe) is a
**different pose** from the shipped `configs/waypoints.json` one, so both were
run.

**The shipped pre-pose, measured statically for the first time**
(`prepose_check_shipseed_rows.json`, the shipped seed):

| pose | jaw above belt | pad-point proxy | authored pad bodies' lowest point | tilt | joint margin |
| --- | --- | --- | --- | --- | --- |
| **the shipped left pre-pose** (`CFG`, teleported) | **+92.6 mm** | **+12.1** | +67.4 | 0.7 deg | **+0.000 @ j3** |
| the calibrated `grasp` config, right arm (`CFG`) | +82.5 | +2.0 | +38.4 | 1.3 | +0.003 @ j3 |
| the shipped **right** pre-pose (its own `T0` solve at depth 0.095) | +92.4 | +11.9 | - | 0.7 | +0.007 @ j3 |

So the pose the line has always held is **on the j3 limit** (0.000 rad) and its
pad *point* is **46 mm below the tallest fruit's top** (`belt_top + 0.0585`) -
P95's live `belt_top + 0.029` is the same structure one blend-lag above it. That
is the defect stated as geometry, without a run.

**The clearance forms**, at `z = 0.165` above the belt top (the registered
target), one row per form and arm (`prepose_check_shipseed_rows.json`):

| hold | left: jaw / margin | right: jaw / margin | verdict |
| --- | --- | --- | --- |
| **`calib`** (the arm's own calibrated attitude, `capture_hold_pose`) | **+159.7 / +0.025 @ j7** | **+155.2 / +0.035 @ j6** | **selected** |
| `nat` (position-only, the place leg's form) | +160.2 / +0.029 @ j6 | +160.1 / **+0.000 @ j3** | equivalent for the left, worse-conditioned on the right |
| `T0` (top-down hold, the shipped *right*-station solve) | +159.7 / +0.025 @ j7 | +155.2 / +0.035 @ j6 | same as `calib` - the shipped seed is already top-down |
| `0.155` target (any form) | +149.1..+151.7 | +145.2..+150.2 | **below the invariant**: the 6 mm residual lands *low*, so the target must be the invariant **plus** the tolerance |
| `0.18` target | +174.6 / +0.017 @ j7 | +179.4 / **+0.000 @ j1** | clears more, conditioned worse |

Two findings worth the record. First, **the height arithmetic is
`jaw_achieved = target - residual`**, so a target of exactly 0.155 achieves 0.149
and *does not* meet P95's clause - which is why the registered target is 0.165.
Second, **the "attitude" file is not the pose**: `configs/waypoints.json`'s
declared `grasp_quaternion` for the left is `[0, -0.7071, +0.7071, 0]` (the
top-down `T0`), `configs/waypoints_oriented.json`'s is 85 deg from vertical, and
the *calibrated joint config* the pre-pose actually blends to stands at
**0.7 deg** - so the staging pose's attitude has never been the declared one.
`calib` therefore *measures* the calibrated pose's attitude rather than reading a
file, and the static witness (the authored pad bodies) confirms the result: their
lowest point goes **+67.4 -> +134.6 mm** above the belt top on the left and
**+38.4 -> +110.8** on the right.

## 2. The change, and how the pre-P96 path stays reachable

One resolver, `tasks.prepose_clear_resolution(two_line)` (the P87/P88/P89/P91
pattern: one resolution, one `[biarm] pre-pose` row, one manifest block), and one
modified site, `_prepare_two_line_stations`:

* `FRUIT_BIARM_PREPOSE_CLEAR` unset -> `PREPOSE_CLEAR_TWO_LINE_DEFAULT` (**False
  after this phase**: the pre-P96 path, bit for bit); `=0` explicit -> the same;
  `=1` -> on.
* `FRUIT_BIARM_PREPOSE_CLEAR_Z` (default **0.165** m above the belt top; the band
  `[0.155, 0.25]` raises outside itself - a "clearance" pose below the invariant
  is a knob that only looks configured).
* `FRUIT_BIARM_PREPOSE_CLEAR_HOLD` (`calib` shipped, `nat` the place leg's
  form), the phase's attitude cell.
* **The pick-point skip is bypassed when the cell is on** - that skip is why the
  left station had no solve at all (P39: *"the left station is the calibrated
  pick point, so `_prepare_two_line_stations` skips its solve"*), and it is the
  whole point of the phase.
* The solve cache carries the resolution, so a phase's A/B re-solves in one
  process; the print is **inside** `if clear["on"]:`, so the pre-P96 path adds no
  line (`gates.sh` G0, §4).
* Provenance: the collector's shard manifest gains
  `collection.prepose_clear` / `prepose_clear_defaulted` / `prepose_clear_z`.
  **The pre-pose is held 65 ticks at the start of every attempt, so a store
  without `prepose_clear` predates P96** - the stations were already carried
  (`station_l`/`station_r`), the *pose* was not, and now is.

`scripts/253_p96_prepose_selftest.py` (selfcheck leg, 39 checks) pins the
resolver table, the height arithmetic, the single solve site with the skip
bypassed, both hold forms, the gated print and the three manifest keys.

## 3. Phase 2 - the census: the invariant is restored

`pg_census.py` implements P95's criterion verbatim (a **contact** = `pad gap <=
6 mm` **and** that hand's measured span swing `>= 2 mm` within +-4 ticks; the
span is the verdict, the gap ranks). Four cells, 20 attempts each, the same
instrumentation in all four (`FRUIT_FRUIT_TRACE=2500 FRUIT_FRUIT_TRACE_ARM=1
FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1 FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1`), control `=0`, treatment `=1`.

**The control reproduces P95's census to the digit**, which is the first
admissibility of the phase: the pooled control reads **min 0.0 mm, `<= 6 mm`
4/40, 1 contact/40**, and the contact is **seed 6 attempt 0's right kiwi at
`t = 16.99 s`, pad gap +1.8 mm, span swing 26.4 mm** - the witness of
`logs/p95/RESULTS.md` §2.

| cell | set | seed | n | min gap | median | `<= 6 mm` | **contacts** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `C5` | shipped | 5 | 20 | **+0.0 mm** | +118.9 | 3 | 0 |
| `T5` | clearance | 5 | 20 | **+5.9** | +165.1 | 1 | **0** |
| `C6` | shipped | 6 | 20 | **+1.8** | +156.2 | 1 | **1** |
| `T6` | clearance | 6 | 20 | **+25.0** | +115.6 | 0 | **0** |
| **pooled** | **shipped** | | 40 | **+0.0** | +156.2 | **4/40** | **1/40** |
| **pooled** | **clearance** | | 40 | **+5.9** | +154.6 | **1/40** | **0/40** |

Per arm, pooled: **right** (the exposed lane) shipped n=19 min **+0.0** median
+31.6 `<= 6 mm` **4**, contacts **1** -> clearance n=20 min **+5.9** median
+33.9 `<= 6 mm` **1**, contacts **0**; **left** (the hand that strikes) is
unexposed by construction and reads min +126.3 -> +153.8, contacts 0 -> 0.

**The one remaining `<= 6 mm` row is the proxy's own floor, not a near-miss.**
It is `T5` attempt 2, a **6.9 cm pear**, pad gap **+5.9 mm** with a **0.1 mm**
span swing. The pad point sits 36.9 mm above that fruit's centre and the proxy's
radius is a fixed 31 mm, so `36.9 - 31.0 = 5.9 mm` **is** the smallest gap the
instrument can report for that fruit once the pads are clear - a tangency of the
proxy sphere, with no pad contact. The same arithmetic explains why the count
cannot reach 0 for the biggest fruit at this height: it is the measurement floor,
not the geometry's.

**G1 PASS; G2 PASS.** The pose rows (identical at both seeds, one per station per
batch):

```
[biarm] pre-pose left:  FRUIT_BIARM_PREPOSE_CLEAR=1(explicit), z=+0.165, hold=calib
        target belt_top+0.165 achieved jaw belt_top+0.160 (pad point belt_top+0.079)
        tilt 1.2deg margin +0.020@j7 residual 6.0 mm -> CLEARS (jaw >= belt_top+0.155)
[biarm] pre-pose right: ... achieved jaw belt_top+0.155 (pad point belt_top+0.075)
        tilt 2.8deg margin +0.013@j7 residual 6.2 mm -> CLEARS
```

Both stations clear P95's clause on the **achieved** pose (+0.160 / +0.155), the
left (the exposed hand) with 5 mm of headroom, and **both margins are better than
the shipped pre-pose's own +0.000 @ j3** - the clearance pose is not a
conditioning regression (it is the opposite), which is what `PREREG_A1`'s 0.02
selection floor was protecting and why `calib` was chosen over `nat` (the right
reads +0.000 @ j3 under `nat`).

One correction to §1 that the live rows make: the **oriented-seed** cells read
0.27-0.32 rad of margin (the `C0`/`NAT` rows of `prepose_check_rows.json`), but
those solves start from `waypoints_oriented.json`'s *tilted* seed, which is not
the shipped pose. From the shipped seed the clearance solve lands **top-down**
(1.2 deg) with **0.020 / 0.013 rad** - the numbers above - and that is the arm
this phase measured.

## 4. The count is a draw; the registered clause fails by its letter

| seed | placed C -> T | left C -> T | right C -> T | never-grasped C -> T | `cnp` C -> T |
| --- | --- | --- | --- | --- | --- |
| 5 | **17/20 -> 12/20** | 9/10 -> 5/10 | 8/10 -> 7/10 | 3 -> 4 | 0 -> 4 |
| 6 | **12/20 -> 15/20** | 6/11 -> 9/10 | 6/9 -> 6/10 | 1 -> 2 | 7 -> 3 |
| pooled | **29/40 -> 27/40 (72.5 -> 67.5 %)** | 15/21 -> 14/20 | 14/19 -> 13/20 | 4 -> 6 | 7 -> 7 |

**G3 FAILS** by the registered rule (*pooled >= control and neither seed lower by
more than one*): seed 5 is **-5**, seed 6 **+3**, pooled **-2**. The per-arm
pooled read is **-1 and -1** - flat - and the seed-5 treatment is where the whole
movement is (its left arm draws 5/10 against 9/10, and its four `cnp` are the
closed loaded-slide class the record calls unavoidable, `logs/p42/SIM_LIMIT.md`).
This is P93's own lesson at n=40: **a 20-attempt two-line count is a branch
draw**, its own control moves 16 -> 12 between seeds in that phase, and the
power statement for a 5-point difference is hundreds of attempts per arm.

**G4 PASS**: no new failure-reason key - both arms carry exactly `fruit did not
follow the gripper` and `grasped, not placed (no note)` at both seeds.

## 5. The delivered side (report, never the argument)

| seed | set | `s/attempt` | interval mean | p90 | window placed/min | batch | wall | `placed/min wall` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | shipped | 9.10 | **9.37** | 18.20 | **6.40** | 5.63 | 420.7 s | **2.42** |
| 5 | clearance | 9.70 | 16.02 | 21.30 | 3.75 | 3.72 | 428.9 s | 1.68 |
| 6 | shipped | 9.10 | 11.08 | 17.60 | 5.41 | 3.94 | 397.8 s | 1.81 |
| 6 | clearance | 9.00 | 11.46 | 20.70 | 5.24 | 5.01 | 399.2 s | **2.25** |

**The clock is unchanged and the pre-pose is not a time cost**: the `[cycle]`
`prepose` block is **0.71 s in every cell** (the blend is a fixed 45 + 20 ticks),
`release` p50 1.69 -> 1.68 s, and the **`hover` block falls 0.78 -> 0.61 s**
(the hand starts at the hover height instead of diving 56 mm below it, so the
hover move is shorter). The interval movement is the count's (seed 5 places 5
fewer), and the wall is flat (819 -> 828 s over 40 attempts).

**G5 landing**: **29/29** and **27/27** payload-present releases land `on_belt`
(no off-belt traces in either arm); the motion gate reads **0/20 over-budget
descent legs** in both treatment cells, and the one over-budget leg in `C6`
(leg 12, 0.164 vs 0.160) is **its record's own** - `logs/p94/T6.log` carries the
same row, so it is the P86/P87 documented branch leg, not the phase's.

## 6. The decision

**Not adopted.** G1 and G2 pass - the invariant is restored, with a static
witness, a census, and no conditioning cost - and **G3 fails at seed 5**. The
registration's rule is explicit: *a fix that restores the invariant without
losing a placement ships; one that trades placements for clearance is the
owner's decision*. This is the second case, and the trade is **-5 / +3 on two
seed draws with a flat per-arm pooled read** - i.e. the phase cannot
distinguish "the clearance pose costs placements" from "seed 5 drew harder
fruit", and it must not claim either.

**What the owner is deciding, priced**: the invariant (a hand inside another
lane's fruit band) against a count difference the phase cannot measure. The
re-entry is a **4-seed** cell (P93's power rule) at **`FRUIT_BIARM_PREPOSE_CLEAR=1`**,
reading the **contact census as the endpoint** and the count as a report - and,
if more margin on the biggest fruit is wanted, `FRUIT_BIARM_PREPOSE_CLEAR_Z=0.18`
(clears to +174.6 / +179.4, at the right arm's j1 margin 0.000; the map's rows
are the price list).

Nothing was re-recorded and nothing moved: `configs/motion_reference.json` /
`..._twoline.json` = **`30fb99f8`**, `..._single.json` = **`8952c320`**, ckpt
`moe_v13s` `61da390a`.

## 7. No-harm, and the phase identity expectation

* **G0 (admissibility)**: with the phase's own `[ftrace]` arming row and the
  P84/P85 sealed diag rows dropped, **`C5` is byte-identical to
  `logs/p94/T5.log` (808/808 `[fruit]` lines) and `C6` to `logs/p94/T6.log`
  (825/825)**. So the trace stack (fruit + both arms' link reads, the carry
  tracker, the place trace) is **branch-neutral on this cell** - P95's result
  reproduced - and the treatment differs by the lever alone.
  (`PREREG_A2` records why the reference is `p94`, not `p92`: `p92/{C5,C6}` are
  **pre-P94**, and the live cell diverges from them at P94's own guarded row,
  `|v|max` 1.108 -> 0.270.)
* **The phase identity expectation, as registered**: **no** treatment cell
  replays any record. `T5`/`T6` are moved branches by construction (the pre-pose
  is held 65 ticks on every attempt), their fingerprints read `DIFFERS` against
  the pre-P87 20-attempt references exactly like every post-P87 cell, and they
  are gated on **budgets only**. The control cells are the ones that had to
  replay, and they do.
* **The shipped acceptance is inert**: `scripts/accept.sh` (the two-line default,
  the knob unset) reads **8/10 = 80 %, 9.0 s/attempt, `fingerprint: matches
  configs/motion_reference.json`, `190: PASS`**, and its **419 physics `[fruit]`
  lines are byte-identical (419/419)** to `logs/p94/accept_final.log`
  (`logs/p96/accept_noharm.log`).
* `scripts/selfcheck.sh` **PASS, 0 failures, 1 skipped** (`logs/p96/selfcheck.log`,
  the new **P96 pre-pose clearance** leg, 33 checks).
  `scripts/106_index_audit.py` **OK**, `scripts/107_collect_merge_test.py`
  **PASS (21 checks)**.
* `src/` change: the resolver + the station solve + `_tilt_deg`, the collector's
  three manifest keys, `rl_env.py`'s metadata-only `TASKS_MD5` follow, the new
  selfcheck leg. `configs/` untouched.

### Pins

| file | md5 |
| --- | --- |
| `src/fruit_sorting/tasks.py` | **`e1095446e671a688575c604650ec8b4e`** |
| `src/fruit_sorting/rl_env.py` | `TASKS_MD5` follow -> `e1095446` |
| `scripts/253_p96_prepose_selftest.py` | **`159f1c4c`** (the new selfcheck leg) |
| `logs/p96/PREREG.md` / `PREREG_A1.md` / `PREREG_A2.md` | `bb057405` / `a2e63f60` / `724009a0` (pre-run) |
| `logs/p96/prepose_map.py` / `prepose_check.py` | `49201ac3` / `38967f0e` |
| `logs/p96/pg_census.py` / `p96_report.py` | `a86d3e3a` / `a3be9257` |
| `logs/p96/gates.sh` / `run_p96.sh` | `0c2bf9cc` / `0ddb8fd9` |
| `configs/motion_reference{.json,_twoline.json}` | **`30fb99f8`** (untouched) |
| `configs/motion_reference_single.json` | **`8952c320`** (untouched) |
| checkpoint | `moe_v13s` `61da390a` (untouched) |
