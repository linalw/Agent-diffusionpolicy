# Working on this repository

Bimanual fruit sorting: a scripted sorting cell in Isaac Sim, a skill-routed
diffusion policy trained on demonstrations from it, and the measurement code that
keeps both honest. Read this before changing anything - the second section is not
style advice, it is what makes the numbers in the documents mean what they say.

## 1. Run before you finish

```bash
scripts/selfcheck.sh        # offline: motion kinematics, dataset index, collect/merge, ~7 s
scripts/accept.sh           # ten pick-and-place attempts + the motion gate + the baseline fingerprint
scripts/accept_policy.sh    # ten hybrid policy episodes + the policy floor and failure-reason gate
scripts/demo_2min.sh        # a few picks, a video clip, then the motion gate
```

`selfcheck.sh`, `accept.sh` and `accept_policy.sh` need no arguments;
`demo_2min.sh` takes `HEADLESS=0` to open the Isaac window. The three simulator
scripts call `selfcheck.sh` themselves, so a broken tree fails in seconds instead
of after a simulator run; `SKIP_SELFCHECK=1` bypasses that gate when you are
iterating on the simulator scripts. Every script with a simulator runs through `scripts/run.sh`,
which raises the file-descriptor limit - this Isaac build dies about 40 s into the
first camera read without it (`dup failed ... Too many open files`, then a wedged
crash reporter, so the window looks frozen rather than crashing). The four entry
scripts (`20_pick_place`, `40_collect_demos`, `60_eval_policy`, `70_record_video`)
also call `fruit_sorting.fdlimit.raise_fd_limit()` before creating `SimulationApp`,
so invoking `$ISAAC_SIM_DIR/python.sh` directly no longer dies that way; the wrapper
is still the supported path.

**P98 (2026-11-02) reverts P97: the clearance pre-pose is opt-in again and the
acceptance returns to 8/10 with `configs/motion_reference.json` = `30fb99f8`.**
The owner's decision: P97 shipped P96's pose as the two-line default on the
invariant argument, but the *shipped* acceptance then read **6/10 against its
0.60 floor** (pre-flip 8/10), the seed-5 sanity cell **12/20 against 17/20** and
the interval **16.02 s against 10.59 s** - and the gain was never a rate (P96's
draw 29/40 -> 27/40). A zero-margin gate cannot separate the shipped line from a
regression, so `PREPOSE_CLEAR_TWO_LINE_DEFAULT` is **False** again: unset +
two-line resolves off (the pre-P96 path, bit for bit), and
**`FRUIT_BIARM_PREPOSE_CLEAR=1` still arms P96's measured pose** (z=0.165,
hold=calib, band `[0.155, 0.25]`) - the resolver/arithmetic, P97's `(two_line)`
solve wiring and the `253` leg (re-pinned to the reverted table) are unchanged.
Both two-line-side references are **restored byte-for-byte from the P97
archives** to **`30fb99f8`** (`configs/motion_reference_single.json` `8952c320`
untouched). The same-batch acceptance on the reverted tree reads **8/10, 9.0
s/attempt, `fingerprint: matches` + `190: PASS`** with **419/419** physics lines
identical to `logs/p94/accept_final.log`, and the `=1` A/B reproduces P97's
shipped-default arm (**6/10, 9.6 s/attempt**, budgets pass; **457/457** physics
lines identical to `logs/p97/accept_final.log` with the two pose rows dropped -
their only change is the origin label; fingerprint **DIFFERS** by construction,
so it is gated on budgets only). **Nothing else moves.** **Re-baseline: the
two-line numbers are P97's pre-clearance values again; the P97 paragraph below
and every P97 store (`collection.prepose_clear=1 / defaulted=true`) are that
phase's record, and `FRUIT_BIARM_PREPOSE_CLEAR=1` reproduces the arm.** Gates:
`190` PASS, selfcheck PASS (0 failures, 1 skipped), `211` ok (115 checks),
`106` OK, `107` PASS (21 checks), `bash logs/p98/gates.sh` rc=0. Pins:
`tasks.py` **`6ce29b56`**, `rl_env.py` **`82a120fc`**, `scripts/253`
**`a6d4add1`**, `scripts/selfcheck.sh` **`5937b461`**; refs **`30fb99f8`** /
**`30fb99f8`** / `8952c320`; ckpt `moe_v13s` `61da390a`. Evidence `logs/p98/`.

**P99 (2026-11-02) answers the owner's candidate-planning question with a census
and builds nothing: the wait is not the interval, and the one mechanism above
the 0.5 s/placement bar is cross-lane, i.e. a sort error.** The owner asked
whether the fruit planning between the feeder and the arms can raise efficiency,
because the interval looks long; the record's priors (R3's arrival-bound lead,
P58/P59's 0/42 starved rounds, P80's 44 starved polls with 0 lost slots) said no,
so the phase pre-registered its decision rule (`logs/p99/PREREG.md` md5
`0acc5692`, pinned before any cell was read) and censused first. **The
instrument is one reporting block** - `FRUIT_BED_DIAG=2` adds, from the same
`diag` list `select_target` already fills, the decision's **selector floor** and
**one row per live fruit** (`idx/grade/along/x/z/r` + the first refusing
predicate); `=1`/unset are byte-unchanged and no control path gains a read. The
attempt end and the park split are P84's `FRUIT_BIARM_PARK_TRACE=1`. **Both
census cells replay their same-seed P94 record byte for byte** (`C5` =
`logs/p94/T5.log` **974/974**, `C6` = `T6` **970/970** `[fruit]` lines, the
instrument's rows dropped), so the P98 revert resolves off here *and* the
instrument moves nothing; the derived interval reproduces **9.37 / 11.08 /
10.59** (P94 §5) and **10.77** (`logs/p84/D5.log`) to the digit. **The wait
split per attempt slot**: seed 5 park-gate **0.03**, park-motion **2.47**, feed
**0.27**, starved polls **0.17** (dead 2.94, span 15.08, interval **9.38**);
seed 6 0.82 / 2.69 / 0.25 / **0.86** (dead 4.62, span 13.72, **11.08**) - so the
slot-loop wait is the **park return and the feed gap, not fruit** (starvation
0.9 % and 3.9 % of the interval; the 6-poll **batch prime** is a separate 0.17
s/placement). **The candidate read is the answer**: the belt is stocked (**7
live** fruits at the decision instant) and the arm still has nothing its own
grade can catch in **12/32** and **37/57** decisions, with ~2.5 of those fruits
already *inside* the catch floor; `window <= 1` on **37 of 40** selections, so
the pick is a **forced choice**; own lane empty while a cross-lane fruit was
at/above the floor on **10/32** and **35/57**; and the **delay-aware headroom is
0.000 s on 40/40** (the shipped rule already takes the nearest own-grade fruit,
`tasks.py:8111-8115`). **Convertible seconds**, pooled over 29 placements and a
10.2 s mean interval: **(i) cross-lane in-attempt arrival 1.258 s/placement
(12.3 %)**, **(i') cross-lane in-chain polls 0.603 (5.9 %)**, **(ii)
delay-aware 0.000**, **(iii) joint/park-gate 0.531 (5.2 %)** - candidate
planning **(i)+(i') = 1.862 s/placement = 18.2 %**, and the whole of it is
cross-lane, which the PREREG had registered as the special case because **left =
lane 0 = grade A and right = lane 1 = grade B**: the place is
`run(state, bin_index)` with the arm's own lane, so a cross-lane pick is a sort
error (`tasks.py:11688`), not a semantics switch. **Priced anyway with the
shipped `FRUIT_GRADE_ROUTING=0`** at both seeds: **starvation 37 -> 0** polls,
**arrival wait 1.62 -> 0.67 s**, `window <= 1` 19/20 -> 5/20, **park gate 0.03
-> 0.62 s/attempt** (both arms never idle, so the station dwells collide - the
constraint the starvation was absorbing), **interval 9.38 -> 10.01 (+6.8 %) and
11.08 -> 11.66 (+5.3 %)**, **window rate worse at both** (6.40 -> 5.99, 5.42 ->
5.15) while the **batch span is better at both** (181.1 -> 174.3, 182.6 ->
166.9), the count a draw (29 -> 30 of 40), **17/40 fruit mis-sorted**, and seed 6
loses 2 payloads upstream (`release_bottom = -184 mm`). **The transferable
sentence: the wait is not the interval** - ~1.1 s/attempt of pure fruit wait
removed (0.95 s arrival + 0.17 s polls) took **0.57 s off the cycle (18.02 ->
17.45 s) and 0.64 s onto the interval**, because the
interval is the *sequencing* of two overlapped arms (seed 5 bunches placements in
pairs, 4.5/1.8/0.4 s apart then 16-18 s; the fallback spreads them, p50 13.00 ->
11.70, mean 9.38 -> 10.01) - one arm's wait is often the slack the other arm's
sweep needs. **No lever, no default change, `configs/` untouched** (`30fb99f8` /
`30fb99f8` / `8952c320` stand): the 18.2 % is the **price of grade-pure
routing**, spendable only by a workstation change (a diverter or a second bin per
arm), and if it is ever wanted its price is measured here. The named open item is
the **park return** (2.5 s/attempt, ~13 % of the interval), a return-path object.
Guards: landing **17/17**, **12/12**, G5 **17/17**, G6 **13/13** payload-present (15
rows, 2 upstream losses); grade ledger 0/40 vs 17/40; budgets are P94's own (census cells
byte-identical) and `105 --min-success-rate 0.0` **PASS** on the moved pricing
branch; `selfcheck.sh` **PASS (0 failures, 1 skipped)**; the acceptance is
**inert** (`8/10`, `fingerprint: matches`, stream identical to
`logs/p98/accept_revert.log`). Pins: `tasks.py` **`7c1386e9`**,
`rl_env.py` `TASKS_MD5` follow, `logs/p99/{census.py,p99_report.py,run_p99.sh,
run_p99_grade.sh}`; ckpt `moe_v13s` `61da390a`. Evidence `logs/p99/`.

**P100 (2026-11-03, `logs/p100/`; no default change, **not adopted**): the park
return is **36 % slack** and removing it does not transfer - so the
non-semantic throughput lane closes, and the named next decision is the hardware
path.** The owner's item is P99's: **2.47 / 2.69 s of park motion per attempt
slot** (~13 % of the interval, halved over two arms). **The path, quoted** (all
of it `tasks.py`): the worker's `finally` calls `_biarm_park` (`:9763`), which
gates on the other arm and then `go_ready` (`:10240`) -> `_ready_move` (`:7110`)
-> `_transit_to("ready")` (`:3244`) -> `_ready_transit`, i.e.
`_catch_up_drive` (20 ticks) + `_lift_clear` (step cap `FRUIT_READY_LIFT_STEP`
0.04 rad/tick) + `_blend_to`'s min-jerk **ramp** (90) + its **settle** hold
(120), with `_recover_ready` above `TRANSIT_TOL` 0.08. Only the last two are
fixed, and the arm carries nothing. **The knobs that already existed are all
either single-arm-scoped or measured out**: P9-A's `FRUIT_READY_SKIP/_SETTLE`
are gated on `scope = self._active_session is None and not
self.two_line_enabled()` (so on the two-line the settle was the hardcoded 120),
`FRUIT_ARM_PARK` (P43) moves the *reset* pose on the direct path only,
`FRUIT_BIARM_PARK_EARLY` (W6-C/W7-A) opens the **gate** earlier (P99 measures
that gate at 0.03/0.82 s), `FRUIT_BIARM_HOT_ARM` (R3 L3) is measured negative and
`FRUIT_BIARM_PREFETCH` (W6-C L1) is a measured null (0/40 reservations). **The
cell** is a new two-line-scoped pair, `FRUIT_BIARM_PARK_BLEND=60` /
`FRUIT_BIARM_PARK_SETTLE=75` = **135 of the shipped 210 ticks (-0.625 s)**,
resolved by one function `tasks.park_profile_resolution(two_line)` with
`PARK_TWO_LINE_DEFAULT = False`; **the scope is enforced in the resolver**, so
an explicit value is *not read* without a two-line session - which is what keeps
the driver's own **pre-session prime transit** (it prints the same `[ready]` row
before `run_bimanual` installs the session) on the shipped clock.
**The mechanism is exact at all four seeds** (5, 6, 101, 202; 20 attempts each;
`[ready]` parks paired to their `park moving` marker, so the prime rows are
excluded): the fixed clock is -75 ticks on every park, the measured block falls
**2.53 -> 1.91 s pooled (-24.6 %; -0.61/-0.60/-0.62/-0.66 s)**, `q_step` peaks
at **0.0978 rad/tick** (65 % of the posture gate 0.15 = 11.7 rad/s, **2.2x** the
arm's 5.45 rad/s limit: the far-seed parks saturate, and the shipped 0.0652 =
7.8 rad/s = 1.4x ramp already does, so the trim lengthens a saturation) and the achieved `post_err` moves 0.0131 (median) -> 0.0170-0.0282.
**The price is the readiness margin**: the shipped park arrives ~5x inside
`TRANSIT_TOL`, the trim ~1x (worst park 0.0795 rad, 0.6 % under it), with 0
`_recover_ready` events in 80 treatment parks beyond the one jammed 6.2 s
transit **seed 6's control also has** (post_err 1.2047, rec=1). **The delivered
side fails**: interval **-2.8 % / +9.8 % / +0.2 % / -5.4 %** at seeds 5/6/101/202
- **pooled 11.04 -> 11.09 s (+0.5 %)** - while placed moves **59 -> 63 of 80**;
and the reason is measured: **the saving is re-absorbed inside the slot loop** -
dead time (park+gate+feed+polls) **2.91->2.89, 4.43->4.82, 3.66->2.90,
4.03->3.71 s**, because the arm that returns earlier **waits** (gate +0.38 s at
seed 5; starved polls 0.78 -> 2.05 s/slot and 31 -> 82 polls at seed 6). Seed 101
converts the dead time (-21 %) and the interval still does not move, because the
interval is the *placement* sequencing, not the slot loop: **a motion is not the
interval either** (P99's sentence, one level down). The seed-6 rise is not a tail
artefact (its first 11 intervals average 12.98 s against the control's 11.08).
**Guards**: landing **17/17, 16/16, 14/14, 16/16** payload-present `on_belt`
(one upstream-lost `-184 mm` at seed 101, P86/P87's own class, reported
separately); the descent budgets **fail on both arms** (the largest excursion is
the **control** C101's 0.224/0.160 = +40 %, the *same leg P93 recorded*; T6
+10 %, T101 +3 %, C6 +2.5 %) and were **not** re-tuned; **the clearance
census** (trace pair at seed 5, invasive: no rate from those cells) reads min
**48.0 -> 57.7 mm**, **0 of 20 689 and 0 of 20 007 samples < 30 mm**, 0 bands
(closest pair `left_right_finger vs right_right_finger` at the other arm's
`grip`/`close`) - so **the record's 1.9-2.6 mm is a pre-P32/P43/P71/P96
artefact** and this tree keeps its hands > 48 mm apart; the pose guard **fails
its letter at seed 202** (0.0795 > the registered 0.05) and at seed 6 for a
reason the control shares. Two **registered clauses were badly designed and are
recorded, not re-read**: P1b's "zero rec" (the control carries one) and P4's
key-level reading (the `grasped, not placed (no note)` bucket is present in two
*controls* of the same battery). **Inertness proved in one comparison**: `C5` =
`logs/p99/C5.log` **1034/1034** and `C6` = `C6.log` **1030/1030** `[fruit]` lines
(P100's `[ready]` + park rows and P99's `[bed-sel]` block dropped), and
`scripts/accept.sh` with the knob unset is **8/10, 9.2 s/attempt, `fingerprint:
matches` `30fb99f8`, `190: PASS`** with its `[fruit]` stream **420/420**
identical to `logs/p94/accept_final.log` (P98's "419" is the same comparison
under P96's seal, which also drops the pre-pose rows). **No default change, no
reference re-recorded, `configs/` untouched** (`30fb99f8` / `30fb99f8` /
`8952c320` stand); the lever is the opt-in pair, and its re-entry is one
constant (`PARK_TWO_LINE_DEFAULT`) plus the acceptance and a reference re-record.
**Re-baseline: none** - nothing shipped. Pins: `tasks.py`
**`bfe29961`**, `scene.py` **`472bfb6c`** (`_park_provenance` ->
`physics.park`), `rl_env.py` `TASKS_MD5` follow, `scripts/254_p100_park_selftest.py`,
`scripts/selfcheck.sh`, `logs/p100/{p100_report.py,run_p100.sh,gates.sh}`;
ckpt `moe_v13s` `61da390a`. Evidence `logs/p100/`.

**P102 (2026-11-03, `logs/p102/`; default off, **nothing adopted**, no `configs/`
change, no reference re-recorded): the platform survey's stage (i) is answered by
measurement - a **patch** tactile sees the loaded slide **0.17-0.94 s** before the
pinch is lost, and the **2-scalar force channel is the late one**, so the survey's
§2.4 "30 Hz can label the slip, it cannot catch it" is corrected.** The survey
`docs/PLATFORM_SURVEY.md` §5.1 asked `can a PATCH-based tactile see the loaded
slide early enough to act?` with the kill criterion "slip visible >= 10 ticks
early, or `cnp` does not fall >= 30 % -> kill". The instrument is
**`FRUIT_TACTILE_PATCH=<ticks>`** (`0` = off): one `[tactile]` row **per pad per
tick** on every carry leg - `u`/`v` the payload centre's projection on the pad's
face in a frame built from the **measured** jaw axis and the **tool axis** (`u`
across the finger, the plate's 61 mm side; `v` down it, the 84.9 mm side), `dc`
its displacement since the leg's first **seated** tick, `h` the signed distance to
each pad's own plane (the two sum to the measured span), `frac` the patch's
occupancy of the pad's face rectangle, `edge` the signed distance from the
centroid to the nearest border, `f` **this pad's** force. The patch is the
payload's **equatorial disc** (`diameter/2`), the pad is the measured plate
(`61.000 x 84.902 mm`, `logs/p66/COLLIDER_READ.md`) centred
`TACTILE_PAD_LONG_ORIGIN = finger_length - half_long = 0.033549 m` from the link
origin - that offset is load-bearing: the shipped `_pad_standoff` seats the
payload at `v = +66.2 mm`, so a rectangle centred on the link origin scores every
good seat as off the pad (`frac` 0.062 / `edge` -23.8 mm, measured in
`logs/p102/smoke.log`, against 0.646 / +9.8 with the face centre). The equatorial
disc is the **generous** model (a smaller, realistic patch clips off the pad
later), so a negative would have been decisive; `TACTILE_PAD_LONG_ORIGIN`'s sign
must come from the **tool axis**, not `n x rot[:,0]` - the sign of the jaw axis
depends on which finger link is on which side (measured: `v = -66 mm` on one
grasp, `+66` on another, before the fix). Reporting only and **proved inert**:
`guard_armed` gains one term so the block arms itself, the row adds **one tactile
set + one `jaw_positions()` per tick and no `ik_step` work and no articulation
read** (AGENTS §2), and three replays pass - `T5`/`C5` **975/975** and `T6`/`C6`
**971/971** `[fruit]` lines identical to the **same-batch no-knob control** with
`[tactile]` dropped (`python3 logs/p102/census.py --same`), and `N5` (a re-run on
the final tree) **17071/17071 `[fruit]` lines identical with the `[tactile]` rows
KEPT**. **`logs/p91/C5.log` is NOT an admissible control on this tree**: it
predates P94's `_gripper_offset` guard and diverges at its own guarded row
(attempt 0's left `grasp_lift` `jaw_target` `[0.4053,0.0...]` here vs
`[0.3997,0.4...]` there) - the divergence P96's `PREREG_A2` recorded for the p92
corpus; P100's cells add `FRUIT_BIARM_PARK_TRACE`/`FRUIT_READY_DIAG` rows, so the
same-batch pair is the only valid proof. **The population** (40 attempts, seeds
5/6, the shipped two-line): **29 placed / 7 `cnp` / 4 no-grasp**; 70 carry legs ->
**60 held, 6 seated escapes, 4 never-held**. **The attempt join is exact** (the
k-th `grasp_lift` a side takes is that side's k-th attempt, so a leg maps to its
`[run]` outcome): **all 6 seated escapes are on `cnp` attempts, 0 of the 29
placed attempts carry one**, and all 4 no-grasp attempts carry a never-held leg -
so a tactile can only reach **6 of the 11 failures (55 %)** and the acquisition
class (4) is unreachable by any pad. **The lead**: `dc >= 2.12 mm` (5 % of the
pad's half-length) fires **21-113 ticks before the sustained pinch loss** (the
strong face staying < 1 N for >= 5 ticks), **median 60 ticks = 0.50 s, min 21 =
0.17 s, 6/6 >= 10 ticks**, and the threshold does not matter (1 / 2.12 / 4.25 /
8.49 / 10 mm -> median 61 / 60 / 53 / 46 / 44, all 6 >= 10 on every one);
`frac < 0.75 frac0` 34 median (5/6), `edge < 0` 29 (5/6). **The false-positive
read**: 2 of 60 held legs trip at 2.12 mm (5.8 and 10.4 mm) and **both placed**,
`frac` thresholds 0/60, and a held leg's patch is motionless (`dc_max` median
**0.02 mm**, p90 0.10). **The ordering is the finding**: at the seat the patch is
**on the pad** (`frac` 0.52-0.79, `edge` +4.0..+17.2 mm); the payload then walks
**7-189 mm/s** while one pad still carries **8-10 N** (the other face 0.00 N for
the whole leg - P75's one-sided pry), and **when the force finally collapses the
payload is already 4.5 / 31.3 / 35.2 / 43.9 / 44.4 / 46.4 mm out** - so W5-C's
"where force collapses the payload is out within 0-3 ticks" stands as a statement
about the **normal force** and is the **last** moment, not the first: a 30 Hz
GelSight gets **5-28 frames** (median 15) of the slide, a 60 Hz pad 10-56. **The survey's P1
clause is not evaluable as written** ("detectable >= 10 ticks before
`clean_slip > 2 mm`"): the patch centroid's displacement **is** the payload's
relative displacement (`dc/clean` median **0.77-1.00** on the six escapes), so it
crosses the 2 mm line on the same tick (0-1) - a clause that compares a signal
with itself; the decision-relevant reference is "before the pinch is lost", and
that is the 21-113 ticks. **Recorded, not re-read** (P100's precedent). **Scope,
stated so the next reader does not over-read it**: the sim measures the
**duration and magnitude** of the relative motion - physics, and it transfers -
and it does **not** measure whether a **soft** pad images it, because the pads are
rigid and adhesion-free (`logs/p42/SIM_LIMIT.md` §3) and there is no visuotactile
renderer in the loop; that is the survey's T2 bench. So **stage (i)'s kill does
NOT fire** and the next spend is the reaction, not the sensor: **registered, not
built** - a re-grip at `dc >= 2 mm` (the tree's own `clean_slip`), which fires on
8 of 70 legs (6 escapes + 2 benign) at P40's **1.24 s** two-line failed probe =
**0.25 s/attempt worst case = 2.6 %** of a 9.7 s attempt against P3's +5 %, with
the sim-only perfect-detector cell scored on the survey's **P2** (`cnp` 6 -> <= 4
of 40, placed +8 points) and P3. Also measured, and it narrows the class: the two
"never seated" legs that read 22.2 N and 119.4 N are the **failed catch** - one
carries a **318 mm** pad-to-payload offset under a **21.8 mm** span on a 68.9 mm
fruit (the hand closed on air), which is why `is_escape` needs the **seat**
(loaded pinch **and** the patch on the pad), not `slip_max > 100 mm` alone - P76
A3's rule applied to `clean_slip` picks up the arm carrying an empty hand.
Re-baseline: **none** - nothing shipped, `configs/motion_reference.json` =
`configs/motion_reference_twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`** stand. Pins: `tasks.py` **`b257687d`** (the
measured tree was **`42592b5d`**; the close-out move relocates the same block out
of `_clearance_field`'s tail so the `236` leg's "the formatter adds no read"
assertion keeps its scope, and G3's 17071/17071 replay proves it inert),
`rl_env.py` `TASKS_MD5` follow, `tactile.py` `dee9121a`, `scene.py` `472bfb6c`,
`assets.py` `eb30c77a`, `control.py` `9384ff4f`, `bimanual.py` `9b7fc33f`,
`logs/p102/{census.py,gates.sh,run_p102.sh,run_p102_control.sh,METHOD.md,RESULTS.md}`,
`scripts/255_p102_tactile_selftest.py`, `scripts/selfcheck.sh`; ckpt `moe_v13s`
`61da390a`. `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new
`P102 tactile patch` leg (45 checks). Evidence `logs/p102/`.

**P103 (2026-11-03, `logs/p103/`; default off, **nothing adopted**, no
`configs/` change, no reference re-recorded): P102's registered next cell is
built and it is a **null with a harm** - the sim-only **perfect-detector
re-grip** converts **nothing** and the survey's stage (i) closes as *detected
but not convertible*.** `FRUIT_SLIP_REGRIP=<mm>` (unset/`0` = the shipped path
bit for bit; `0 < mm < 1` raises, because a held leg's patch moves 0.02 mm median
over 60 legs) takes the **trigger** from P102's channel - the patch centroid's
`dc` since the leg's first tick, gated on **P102's own seat** (`max(f0,f1) > 1 N`
**and** `edge > -TACTILE_PAD_HALF_LONG`, so the empty hand cannot trip it) plus
the shipped abort ceiling `slip <= FRUIT_SLIP_REACT_MAX` - and the **action**
from the tree's **shipped** slip re-seat: `_carry_leg` already carries one behind
`FRUIT_SLIP_RECOVERY` (`target = fruit - rot @ slip_ref`, the pad centre that
restores the leg-start relation, applied in one go and re-based into the
remaining command list), gated `not hand_is_jaw` only because it was written for
the kinematic pad hand - on the OpenArm hand the pads *are* the fingers, so the
relation is restored by re-basing the arm's own path, which is what it does. **No
new control law and no extra tick**; the scope is a two-line session
(`two_line_enabled()`). **Cells**: four seeds x 20 attempts (5/6 plus the fresh
**101/202**, per P93's rule), the shipped scenario, `FRUIT_CARRY_DIAG=1`
**and** `FRUIT_PLACE_TRACE=1` on **both** arms; `PREREG.md` **`73bdf35e`** pinned
before any 20-attempt cell (the only earlier run is a 6-attempt build smoke that
set the action's temporal form: a 40-tick cooldown let the payload walk
3.07 -> 30.41 mm **inside** the window, so the registered form is the shipped
block's **per-tick** shape). **The ledger**: 137 carry legs, **12 re-seated**
(801 ticks), first fire `dc` **2.14-5.74 mm** (median 2.38) at 5-163 ticks into
the leg, and **1 of 12 placed**. Joined to the same seed's control at the same
attempt index, **7 of the 12 are same-instance pairs: 0 of 5 control `cnp`s
converted and 2 of 2 control placements destroyed**; the other 5 diverged (the
branches re-draw as soon as the action moves a command). **The harm, one
witness** - seed 5 attempt 17, the same lychee in the same slot: control `slip`
**5.8 mm**, `force_min` 6.17 N, `sep_max` 41.9 mm -> **PLACED**; treatment
**153.1 mm**, `force_min` **0.00 N**, `sep_max` **98.4 mm** (the pads at their
open stop) under `fmax` **117.87 N** on a 29.6 mm fruit -> fail. P102 priced
`dc >= 2.12 mm` at "2 of 60 held legs, both placed" **without acting**; acting on
that class is what costs the placement. **Why it cannot convert, and it is the
phase's most useful sentence: the reaction's ceiling here is 8 mm, not 100 mm.**
The two-line session's own **P10-C carry monitor** is armed with
`FRUIT_CARRY_MONITOR_CONFIRM_MM = 8.0`, so an attempt whose lift leg reads
`clean_slip >= 8.0 mm` is truncated at the leg boundary and never takes its place
leg. The re-seat **did** hold the payload on 7 of 12 legs (5.7-22.7 mm against
the controls' 100-2372 mm) - **but only 1 stayed under 8 mm and that one
placed**; six at 8.3-22.7 mm were truncated anyway. **Endpoints**: P2 fails both
ways - **P2a** (`cnp` 7 -> 3, inside the "<= 4" bar) but placed **29/40 ->
29/40 = +0.0 points**, because **4 of those `cnp`s became never-grasped** (lost
*before* the lift's peak); **P2b** `cnp` **11 -> 9 (-18 %)** and placed
**59/80 -> 54/80 (-6.2 points)**, Fisher **p = 0.49** (never-grasped 10 -> 17,
p = 0.20 - not significant at n = 80, and mostly branch: 12 legs touched).
**P3 fails at every seed**: interval **9.37/11.08/12.16/11.53 -> 9.85/12.92/
12.92/15.19 s** (+5.1/+16.6/+6.2/+31.8 %, **+15.3 %** on the mean), window
5.49 -> 4.83, batch 4.86 -> 4.33, `placed/min` wall 3.77 -> 3.71, `s/attempt`
9.10 -> 9.40 (+3.3 %) - the action costs no tick by construction, so the
interval is the **branch** (a failed attempt re-draws the slot loop).
**Guards**: G1 **PASS** (acceptance **8/10**, `fingerprint: matches`,
`190: PASS`, **419/419** identical to `logs/p98/accept_revert.log`), G2 **PASS**
(the batch's controls replay `logs/p102/{C5,C6}.log` **825/825** and **837/837**),
G3 **PASS** (**113/113** payload-present releases `on_belt`, 0 off; 2
upstream-lost rows apart), G4 **4 named legs of 160 and arm-symmetric - 2
controls, 2 treatments** (`C6` 12th 0.164/0.160 the standing branch leg, `C101`
9th 0.224/0.160, `T101` 9th 0.261/0.160, `T202` 11th 0.226/0.161), **not
re-tuned** (P93's ~2.5 %/leg branch property), G5 **fails by its letter at seeds
5/202** (the `grasped, not placed (no note)` key, which P100's A4 already found
in two *controls* - recorded, not re-read), G6 **PASS** (20/20 x 8, no lost
slot). `logs/p103/gates.sh` exits 1 on G4's four legs only (the script's own
"any over-budget leg fails" is stricter than the registered "name it").
**Verdict: stage (i) closes - DETECTED BUT NOT CONVERTIBLE, and the sensor is
not justified by it** (a perfect detector was free and the reaction still lost
placements, so a real pad can only do worse on the trigger; what remains of
stage (i) is P102's *supervision/labelling* case, which is the owner's call).
**Named, not registered**: the **8 mm monitor gate** is the binding term a future
reaction would have to beat, and any such reaction must first **separate the
false-positive class** (a slide the pinch survives) - which P102's channel cannot
do at 2 mm. Re-baseline: **none** - nothing shipped,
`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`** stand. Pins: `tasks.py` **`9e3e657b`** (the
cells ran on **`73a90461`**; the close-out is docstring-only and the final
tree's acceptance is 419/419), `rl_env.py` `TASKS_MD5` follow,
`tactile.py` `dee9121a`, `scene.py` `472bfb6c`, `assets.py` `eb30c77a`,
`control.py` `9384ff4f`, `bimanual.py` `9b7fc33f`, `fruits.py` `dcabe16b`,
`logs/p103/PREREG.md` **`73bdf35e`**,
`logs/p103/{p103_report.py,gates.sh,run_p103.sh}`,
`scripts/256_p103_regrip_selftest.py`, `scripts/selfcheck.sh`; ckpt `moe_v13s`
`61da390a`. `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new
`P103 slip re-grip` leg. Evidence `logs/p103/`.

**P104 (2026-11-03, `logs/p104/`; a fixture in `logs/` - **no `src/` or
`configs/` change, nothing adopted, no commit, both references untouched**):
stage (ii)'s free half, `docs/PLATFORM_SURVEY.md` §3.3 **T1**, is measured, and
**it passes for a 4-contact hand while failing the survey's own 2 mm criterion
for a 3-contact one.** The instrument is a **fixture**, not a policy run
(`fixture_probe.py`, `run_p104.sh` -> `fixture.txt`): one payload, `n` pad bodies
on **force-capped position drives** (k = 1e5 N/m = `finger_damp02`, cap **4.90 N
= the measured per-face pinch**, P41's 9.75-9.9 N over two faces), the measured
plate **61.000 x 84.902 mm** with its distal plane 80.5 mm below the jaw centre
(`logs/p66/COLLIDER_READ.md`, `tasks.FINGER_TIP_BELOW_JAW`) so the shipped
**10.5 mm lip** is reproduced, the pool's own mesh/mass/friction draw, a
150-tick close on a **pinned** payload, 90-tick settle, then a **5 N/s** axial
ramp **with gravity** to a 40 N cap; seven forms (`pinch_plate` = the shipped
pinch, `pinch_tip` = a 16 mm matched control, `tripod` 3 x 120 deg, `quad`
4 x 90 deg, `lip` = + a static distal ledge, and two **moment** cells that pull
20 mm off-axis), 3 fruits x 3 repeats = **63 cells, 2 m 51 s, no wedge**. **The
analytic frame** (`analytic.py`) is Coulomb with independent point contacts and
no peel; because the seat is equatorial (`logs/p42/SEAT_CENSUS.md` §0: the pads'
midpoint 1.4-4.7 mm off the payload's centre) every normal is perpendicular to
the pull, so `F_crit = n·mu·N_c` and the ratio is **mu-free**: 3 contacts =
**1.50**, 4 = **2.00**, a distal lip a *different* mode (a normal, not friction,
so unbounded in the ideal). **The measurement (sustained break-away = applied +
weight, mean of 3)** reproduces that within 10 % at every cell: the shipped pinch
**11.03 / 14.21 / 12.69 N** (pear 60.6 mm / orange 65.8 / strawberry 37.2),
`pinch_tip` 11.19 / 13.04 / 13.07, **`tripod` 18.11 / 18.90 / 19.74 (1.64 /
1.33 / 1.56x)**, **`quad` 21.81 / 26.59 / 25.97 (1.98 / 1.87 / 2.05x)**, `lip`
**no break inside 40 N** (`>3.63 / >2.82 / >3.15x`), and the pads **do not pry**
(radial travel at break 0.06-1.52 mm on the friction forms, of an 80 mm stroke) - so the friction count
survives contact, which is all a fixture can add to arithmetic. **Three measured
caveats decide how far the pass goes**: (1) **the survey's registered criterion
fails the 3-contact form** - break at `clean_slip > 2 mm` reads **1.05 / 0.94 /
1.48x** because a 3-contact grasp **re-seats** after 2 mm and carries on to
18-20 N while the pinch's 2 mm is terminal (11.11 -> 11.19 N); the 4-contact
passes both (1.75-2.10x at 2 mm, 1.87-2.05x sustained), so the **sustained**
number is the one that means "critical wrench"; (2) **the bar tests a quantity
that is not the binding term** - at the load the cell applies (`m(g+a)` =
0.17-1.20 N) the two-pad pinch **slips 3.20-3.84 mm on the pear** (1.6-1.9x the
2 mm escape threshold, 30-36 % of the lip) against the tripod's 0.36-0.44 and
the 4-pad's 0.15-0.25 mm, i.e. **9-15x, not 1.5x**, while the static capacity is
10-20x the demand and the cell still loses 17 of 80 attempts - so a 1.5-2x
capacity gain **does not predict a `cnp` conversion** and the gate a purchase
deserves is a **creep** endpoint, not a break; (3) **under a 20 mm off-axis pull
the 3-contact advantage falls to 1.15 / 1.33 / 1.47x** (the slipping payload tips
and unloads a contact: 3.57 / 5.06 / 3.64 N at break), so the win is
**axial-specific** - and the **lip** wins the fixture unboundedly while the tree
has **already measured that geometry as a pipeline negative**
(`logs/r8/A_RESULTS.md` §3: the ledges bat the payload, no-contact 2 -> 9 of 15),
which is the "necessary, not sufficient" clause measured rather than asserted.
**Verdict: stage (ii)'s kill does not fire** - the 4-contact form clears 1.5x at
every size and both controls, and 4+ contacts is what every candidate hand has
(ORCA 17 DoF, LEAP 16 DoF/4 fingers, Allegro 16 DoF/4 fingers, DexHand 19 DoF) -
the 3-contact form sits **on** the bar (mean 1.51, 2 of 3 fruits, fails the 2 mm
criterion) so a three-finger hand is not a purchase, and the priced number is
**1.5-2.0x static axial**. **Two by-products, recorded not acted on**: the implied
pair friction `mu_app = Fexit/(n·N)` is **1.05-1.45** on every form, i.e.
PhysX's default combine is the **average** of the pad's 2.0 and the fruit's draw
(1.26-1.41), **not** the *minimum* that `scene._add_physics_material`'s comment
assumes - so `mu_eff` 0.45 is 2.3-3.2x pessimistic and the measured pinch is
11-14 N against the analytic 4.41 N (no comment or constant was edited; that is
a cone re-measurement's work); and **the third contact pays only when it is
loaded** - at a 3 mm commanded interference one tripod pad carried **3.09 N of
4.9** and the tripod was worth **1.01x**, which is why the registered
manipulation check forced the 5 mm setting (`METHOD.md` A1). Pins: `tasks.py`
**`9e3e657b`**, `scene.py` `472bfb6c`, `control.py` `9384ff4f`, `fruits.py`
`dcabe16b`, `assets.py` `540406fa`; references **`30fb99f8` / `30fb99f8` /
`8952c320`** untouched; ckpt `moe_v13s` `61da390a`;
`logs/p104/fixture_probe.py` **`3f18b908`**, `logs/p104/fixture.txt`
**`3fbb48f5`** (63 rows), `logs/p104/analytic.txt` **`56a7e260`**,
`logs/p104/{METHOD.md,RESULTS.md,p104_report.py,run_p104.sh}`.
`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** - the phase adds no
`src/` code and no leg. Evidence `logs/p104/`.


> **Reverted by P98 (2026-11-02).** The paragraph below is the record of the
> phase that shipped this flip for one phase; `logs/p98/` takes it back out and
> `FRUIT_BIARM_PREPOSE_CLEAR=1` restores the arm it describes. Its numbers stand
> as that phase's record, not as the shipped tree's.

**P97 (2026-11-02) ships P96's clearance pre-pose as the two-line session's
default and re-baselines the acceptance a fourth time** (the owner's decision:
the **invariant** ships, the count is not claimed - it removes an impossible
geometry, a hand sweeping another lane's fruit band):
`FRUIT_BIARM_PREPOSE_CLEAR` resolves **on for a two-line session** with the env
unset, off on every other path, `=0` restores the pre-P96 path; the measured arm
is unchanged (`belt_top + 0.165`, `hold=calib`, achieved jaw **+0.160 left /
+0.155 right**, pad points +0.079/+0.075, joint margins +0.020/+0.013 rad). The
acceptance moves to **6/10, 9.6 s/attempt** with `configs/motion_reference.json`
= **`1490b63e`** (re-recorded from `logs/p97/accept_default.log`; the pre-P97
pair `30fb99f8` is archived at `logs/p97/motion_reference{,_twoline}_pre_p97.json`,
and `configs/motion_reference_single.json` `8952c320` is **untouched**). Its own
`=0` A/B reproduces **8/10 + `fingerprint: matches 30fb99f8`** with **419/419**
physics lines identical to `logs/p94/accept_final.log`, and the single arm is
**346/346** raw identical to `logs/p71/accept_rails_none.log` with the single
reference - so the flip is resolution-only.
**Re-baseline: every two-line rate, interval, acceptance and store recorded
before P97 is a pre-clearance-pre-pose number; `FRUIT_BIARM_PREPOSE_CLEAR=0`
restores it** (compose with the earlier restores: `FRUIT_ARM_PARK=ready` for
pre-P43, `FRUIT_POLICY_TRIGGER_ACQ=0` for pre-P54, the P58 burst profile for
pre-P58, `FRUIT_SPEED_RELEASE=0` for pre-P87, `FRUIT_CARRY_OFFSET_MAX=0` for
pre-P94).

**P94 (2026-11-02) fixes a state-integrity defect on the carry and re-baselines
the acceptance a third time: the `_gripper_offset` command jump is bounded, the
acceptance reads **8/10, `fingerprint: matches`** with
`configs/motion_reference.json` = **`30fb99f8`** (re-recorded from
`logs/p94/accept_p94.log`; the pre-P94 pair `423896f7` is archived at
`logs/p94/motion_reference{,_twoline}_pre_p94.json`, and
`configs/motion_reference_single.json` `8952c320` is **untouched**).**
`_gripper_offset[side]` is written once per grasp as
`rot.T @ (payload - tcp_position())`, which is a **tool** offset only while the
pads are on the payload; `_carry`'s **assisted** branch applied it unguarded
(`centre - rot @ offset_tool`) while the coherent branch, the `_carry` tail and
`_place_low` all guard it with `hand_is_jaw` - so a fruit that was far out at the
grasp's entry turned the payload's *distance* into a commanded jump (P93: 1313 mm
= 18.8x the hand's own 70 mm `_pad_standoff`, 419 N / 1.545 m/s / 2361 mm slip).
The fix is one ternary: past `FRUIT_CARRY_OFFSET_MAX` (**0.20 m shipped**;
`=0` restores the pre-P94 path bit for bit) the jaw hand is commanded the pads,
and the 0.20 m is `FRUIT_RELEASE_ARM_TRACK`'s own pad/arm-relation threshold, not
a new constant. Measured on four seeds (5/6 = P92's records, 101/202 = P93's
fresh pair) plus a tree-check replay: **one guarded leg in 142 control reads**
(350 mm at seed 5) and, on the moved branch, **a second at 1211 mm** - both
commanded jump **0** after the fix, their arm motion `|v|max 1.108 -> 0.270`,
`|a|max 9.47 -> 1.99`; **every leg below the bound is unchanged** (F1: 0 legs
moved) and **seeds 6/101/202 replay their pre-fix records line for line**
(970/970, 1001/1001, 986/986), with seed 5 + the acceptance differing **first at
the guarded row** (111/111 and 110/110 prefix). **No seed loses a placement**
(16->17, 12->12, 15->15, 15->15) and the acceptance goes 7/10 -> 8/10 with its own
`=0` A/B reproducing 7/10 + `matches 423896f7`, i.e. the movement is the flip's.
**The fix converts nothing** (both guarded legs stay `never_held`/`cnp`) - it
removes an impossible command; the +1s are downstream branch draws and are not
claimed. The guard is jaw-hand only, so the kinematic-pad hand is untouched;
the scripted **single arm is 346/346 byte-identical** to
`logs/p71/accept_rails_none.log` with `fingerprint: matches`. Selfcheck PASS
(new `251` leg), `106` OK, `107` PASS. Pins: `tasks.py` **`19cd4028`**,
`rl_env.py` `TASKS_MD5` follow; `configs/motion_reference.json` /
`..._twoline.json` **`30fb99f8`**, `..._single.json` `8952c320`.
**Re-baseline: every direct/policy number and every carry-touching store recorded
before P94 is a pre-P94 carry-command number; `FRUIT_CARRY_OFFSET_MAX=0` restores
it** (compose with `FRUIT_ARM_PARK=ready` for pre-P43, `FRUIT_POLICY_TRIGGER_ACQ=0`
for pre-P54, the P58 burst profile for pre-P58 and `FRUIT_SPEED_RELEASE=0` for
pre-P87).

**P95 (2026-11-02, `logs/p95/`; the instrument ships default off, **nothing
adopted**): P93's open item is closed and the answer is **(a) the other arm** -
the incoming fruit is struck by the **upstream station's** hand while that hand
blends to its own pre-pose, 2 mm from the fruit's surface, and the class is
**structural**: the downstream lane's fruit must cross the upstream station.**
The instrument is `FRUIT_FRUIT_TRACE=<max rows>` (`tasks.py`): **one row per
control tick for the selected fruit** through its whole attempt - position,
linear **and angular** velocity, the belt's encoder speed, and every live fruit
within 0.15 m (offset, velocity, mass, diameter, carried flag) - armed before the
pre-pose blend and flushed from `note_result`, one JSON per attempt. It covers the
window P93 could not see, and it also settles a documentation detail the record
must carry: **`_cycle_mark("descent")` fires *after* `_approach`**, so the rows
labelled `descent` are the leg's **end** - a leg's start is
`first_descent_tick - steps` from that leg's own `[motion] approach … steps=`.
**Neutrality is measured, not assumed**: the `[fruit]` streams are **970/970**
identical to `logs/p94/T6.log` for the fruit-only cell **and 970/970** for the
cell that also reads **both arms' link prims**, and **974/974** for seed 5's arm
cell - so the two-arm read (3 prims/arm, on a baseline that already reads the
active hand's TCP and both fingers every tick) did **not** reproduce AGENTS §2's
7-10-prim link-read shift on this cell; the rule is unchanged, this read set is
just inside it. **The witness is reproduced to the digit** on the unmodified
branch: the seed-6 attempt-0 right kiwi reads `v = (-0.2529, -0.1254, +0.0338)`
with `w = (0.1955, -8.3608, -0.1637)` at the leg's start (tick 339, t=17.225 s) -
P93's own `descent` row and its `0.284 m/s / 8.36 rad/s`, i.e. **2.37x belt**. The
departure is at **t=16.98, 0.25 s before the leg**, inside the descent's hover
wait: the fruit takes `+0.402 x` and `21.6 rad/s` of spin at the tick the **left**
hand's measured jaw span collapses **98.0 -> 59.8 mm and springs back to 98.0 by
t=17.25**, with that hand's pad point **+2 mm** from the fruit's surface and the
pad **-16 mm** along-belt away. A commanded close cannot do that (the finger drive
is stiffness-limited to **0.1 mm** at P41's `k=1e5 N/m` and the 10 N/joint cap; the
left arm's own close on its own pear is at 20.475 s), so it is a **contact
displacing the pads**. The other arm's state is in the log: `[biarm] left: station
acquired at t=16.4s`, `[task] target pear … with left arm` at 16.45, `at pick pose
after 0.71 s … jaw=[0.3429, 0.0122, 1.2795]` at ~17.16 - i.e. the strike is 0.53 s
into **its own pre-pose blend**, whose pad plane sweeps from `belt_top + 0.107` down
to **`belt_top + 0.029`**, through the fruit band (the kiwi's top is
`belt_top + 0.058`) and **29 mm below** it. The other four classes are excluded by
measurement: **(b)** no teleport and no velocity zeroing (the release *is* a
departure class - airborne at `z=1.230`, `|v|` to 0.665 m/s - but only **2/40**
attempts start that way and both settle in 8 ticks ~4 s before the leg; P38/P50's
release offset is the *static* shift, mechanism closed); **(c)** the kick is
`+x`/`+z` with 21.6 rad/s of spin and the belt drives `-y` only (P38: lateral
contribution exactly **0.000 mm** over 475 transits; no cleats on this line);
**(d)** the nearest neighbour (the left pear) is 125 mm away at 0.1201-0.1205 m/s
with **nb swing 0.0004/0.0001/0.0/0.0 m/s** on the strike ticks and mass-weighted
momentum closes on nothing; **(e)** the active (right) hand is 160-190 mm away at
its hover (`sep` 98.0, no descent for another 0.25 s). **The census** (2 seeds x 20
attempts, `probe.txt` §3-§5): departures before the leg are **3 arm-other clusters
in 1 attempt + 2 release + 4 upstream rolling transients**, nothing else; **every**
other leg starts at **1.00x belt** (19/20 at seed 6, 20/20 at seed 5 - so an
overspeeding payload at the grasp entry is **not** a general property of the
line); and the exposure is one-directional because the stations are
`left y=+0.000 / right y=-0.100` on a `-y` belt - a **right**-arm fruit must cross
the left station and a **left**-arm fruit stops at its own, measured as the other
hand's closest pad approach: **right 19 attempts median 31.6 mm, min 0.0, 5/19
<= 6.4 mm** against **left 21 attempts median 217.2 mm, min 126.3, 0/21**; of the
four within 6 mm exactly **one** displaces the pads (**1 contact / 40**, inside a
4-5/40 contact band; the other three are zero-impulse grazes - seed-5 attempt 16
passes at 0.0 mm with `|v|` exactly 0.120, spin 0.0, `sep` 98.0 throughout). **Why
it costs the attempt**: the hover latches the grip point (`_dynamic_grip_target`)
and the descent is static and open-loop, so the strike's **28 mm** lateral offset
at the leg's start (43 mm of drift during the leg) against a **6 mm** catch-up
tolerance puts the pads *on* the fruit (`58.15 N` after 5 ticks, span 99.1 mm
frozen at 88.3), drives it down through the belt
(`z 1.198 -> 0.818`) and the class ends `never_held`
(`force@onset = 0.00 N`, `contacts@onset = 0`). **The fix is a clearance pre-pose**
(pads clear the band, `jaw_z >= belt_top + 0.155`; the left station has no such
pose because - P39 - *"the left station is the calibrated pick point … so
`_prepare_two_line_stations` skips its solve"*), and it is **priced, not built**
(§6: a second station solve at hover height, using the right station's own
machinery; it owes **both references**, the acceptance re-base and every two-line
store, because it moves **every** attempt - unlike P94's bounded ternary). The
rate cannot be the argument (1/40 = 2.5 points against P93's **364 attempts/arm**
for 8.75 points at 80 % power); the argument is the **invariant**: a hand inside
another lane's fruit band is a defect. **Registered as P96** with this report's
pre-leg contact census as its primary endpoint, which is now one command
(`FRUIT_FRUIT_TRACE=... FRUIT_FRUIT_TRACE_ARM=1` + `python3 logs/p95/probe.py`
section 5, criterion `pad gap <= 6 mm` **and** `other-hand span swing >= 2 mm`
within ±4 ticks - the span is the verdict, the gap ranks ±5 mm because the finger
plates are angled at a 98 mm span). No `configs/` change, no reference
re-recorded (none owed: the instrument is inert - **3,334 `[fruit]` lines across 4
cells**, of which the shipped acceptance is **420/420** byte-identical to
`logs/p94/accept_final.log` at 8/10 + `fingerprint: matches`), `selfcheck.sh`
**PASS** with the new `252` leg (67 checks). Pins: `tasks.py` **`cc4eea66`**, `rl_env.py` **`41608912`** (metadata-only
`TASKS_MD5` follow `19cd4028` -> `cc4eea66`), `scripts/252_p95_ftrace_selftest.py`
**`880ce131`**, `scripts/selfcheck.sh` **`ed646df6`**, `logs/p95/probe.py`
**`a78f0924`**, `METHOD.md` **`b79e9a08`**; refs `30fb99f8` / `30fb99f8` /
`8952c320` untouched; ckpt `moe_v13s` `61da390a`.

**P96 (2026-11-02, `logs/p96/`; **nothing shipped** - `PREPOSE_CLEAR_TWO_LINE_DEFAULT
= False`, the measured arm is `FRUIT_BIARM_PREPOSE_CLEAR=1**): P95's clearance
pre-pose was built and measured: the left station **does** admit it, the pre-leg
pad census goes **4/40 within 6 mm and 1 contact -> 1/40 and 0 contacts**, the
delivered count is a **draw**, and the registered "no lost placement" clause
fails by its letter at seed 5, so the owner decides. **The prior question
answered**: both stations hold a clearing pose, and the shipped pose was measured
statically for the first time - the calibrated left pre-pose sits **on the j3
limit (`+0.000 rad`)** with its **pad point 46 mm below the tallest fruit's top**
(0.0585 above the belt), and the shipped *right* pre-pose (its own `T0` solve at
depth 0.095) at +0.007 rad; that is P95's live `belt_top + 0.029` as geometry,
with no run. **`jaw_achieved = target - residual`**, so a target of exactly
P95's 0.155 achieves 0.149-0.152 and **does not clear** - the registered target
is **0.165** (achieved **0.160 left / 0.155 right**, pad points 0.079/0.075),
`FRUIT_BIARM_PREPOSE_CLEAR_Z` raising outside `[0.155, 0.25]`. **The attitude is
not the file**: `configs/waypoints.json`'s declared left `grasp_quaternion` is
top-down (`T0`), `waypoints_oriented.json`'s is 85 deg off vertical, and the
calibrated joint config the pre-pose actually blends to stands at **0.7 deg** -
so the hold is the pose's **own measured attitude** (`capture_hold_pose`,
`..._CLEAR_HOLD=calib`), with `nat` (position-only) reproducible and rejected on
the right arm (`+0.000 @ j3` live, 0.013 for `calib`). The map's oriented-seed
cells read 0.31 rad of margin and look equivalent; **the shipped seed decides**
(0.020/0.013 against the shipped pose's **0.000**). **The census** (4 cells, 20
attempts each, identical instrumentation `FRUIT_FRUIT_TRACE=2500
FRUIT_FRUIT_TRACE_ARM=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1` + the P80
reports, control `=0` / treatment `=1`): the **control reproduces P95 to the
digit** - min gap **0.0 mm**, `<= 6 mm` **4/40**, **1 contact/40** (seed-6
attempt 0's right kiwi, t = 16.99 s, gap +1.8 mm, span swing 26.4 mm) - and the
**treatment reads min +5.9 mm, `<= 6 mm` 1/40, 0 contacts**, the one row being
the instrument's own floor (a 6.9 cm pear 36.9 mm above a **fixed** 31 mm proxy
radius, 0.1 mm span swing). Per arm the exposed lane moves most: right **0.0 ->
+5.9**, **4 -> 1**, **1 -> 0**. **The count**: seed 5 **17/20 -> 12/20**, seed 6
**12/20 -> 15/20**, pooled **29/40 -> 27/40**, per arm pooled **-1 / -1** (left
15/21 -> 14/20, right 14/19 -> 13/20) - so G3 (*pooled >= control and neither
seed lower by more than one*) **fails at seed 5** and the movement is one seed's
left arm (9/10 -> 5/10, four `cnp`), i.e. P93's branch draw at n = 40.
**The cost is zero, slightly negative**: `[cycle]` `prepose` **0.71 s in every
cell** (a fixed 45 + 20 ticks), `release` p50 1.69 -> 1.68, and the **`hover`
block 0.78 -> 0.61 s** because the hand starts at the hover height instead of
diving 56 mm below it; wall 819 -> 828 s, landing **29/29** and **27/27**
`on_belt`, **0/20** over-budget descents in both treatment cells (C6's one is its
record's own leg 12, identical in `logs/p94/T6.log`). **No-harm proven**: G0 with
the phase's `[ftrace]` row + the P84/P85 sealed diag rows dropped reads **`C5` =
`logs/p94/T5.log` 808/808 and `C6` = `logs/p94/T6.log` 825/825** (so the trace
stack is branch-neutral on this cell, P95 reproduced and the treatment differs by
the lever alone - and `PREREG_A2` records why the reference is `p94` and not
`p92`: the latter predates P94's guard and diverges at its own row, `|v|max`
1.108 -> 0.270); the shipped acceptance is **8/10, 9.0 s/attempt,
`fingerprint: matches`, `190: PASS`** with **419/419** physics `[fruit]` lines
byte-identical to `logs/p94/accept_final.log`; `selfcheck.sh` PASS (0 failures, 1
skipped) with the new **`253`** leg (39 checks); `106` OK, `107` PASS. **No
reference re-recorded and none owed** (the knob is off by default), and the
collector's manifest gained **`collection.prepose_clear` /
`prepose_clear_defaulted` / `prepose_clear_z`** - **a shard without
`prepose_clear` predates P96** (the stations were already carried via
`station_l`/`station_r`; the *pose* was not). **Re-entry priced**: a **4-seed**
cell at `FRUIT_BIARM_PREPOSE_CLEAR=1` with the contact census as the endpoint
(P93's 364/arm power rule), and more margin on the biggest fruit is
`..._CLEAR_Z=0.18` (+174.6/+179.4, at the right arm's j1 margin 0.000). Pins:
`tasks.py` **`e1095446`**, `rl_env.py` `TASKS_MD5` follow,
`scripts/253_p96_prepose_selftest.py`, `logs/p96/{PREREG,PREREG_A1,PREREG_A2}.md`
`bb057405`/`a2e63f60`/`724009a0`; refs `30fb99f8` / `30fb99f8` / `8952c320`;
ckpt `moe_v13s` `61da390a`.

> **Reverted by P98 (2026-11-02).** The paragraph below is P97's record, not the
> shipped tree: `logs/p98/` reverts the flip (the shipped acceptance sat on its
> 0.60 floor), and `FRUIT_BIARM_PREPOSE_CLEAR=1` restores the arm measured here.

**P97 (2026-11-02, `logs/p97/`; the owner's adoption of P96): the clearance
pre-pose is the two-line session's default - the invariant ships, the count does
not.** `PREPOSE_CLEAR_TWO_LINE_DEFAULT` flips to **True** (unset + two-line ->
on `default`, no session -> `scope-off`, `=0` -> off `explicit`, `=1` -> on), at
P96's measured arm unchanged (`belt_top + 0.165`, `hold=calib`, achieved jaw
**+0.160/+0.155**, pad points **+0.079/+0.075**, margins **+0.020/+0.013 rad**,
band `[0.155, 0.25]`), and the pose rows read
`FRUIT_BIARM_PREPOSE_CLEAR=1(default) ... CLEARS` at both stations. **The
inertness pass found a real integration defect**: `_prepare_two_line_stations`
ran *before* `CoopSession` existed and resolved
`prepose_clear_resolution(self.two_line_enabled())`, a **session** predicate that
reads False on the first batch - so the first post-flip acceptance was
**8/10 + `matches 30fb99f8` with 419/419 lines identical to P94**
(`logs/p97/accept_inert_pre_fix.log`), i.e. the flip was inert, and P96 could not
see it because an explicit `=1` bypasses the predicate. The fix passes
`run_bimanual`'s resolved `two_line` into the solve
(`_prepare_two_line_stations(two_line)`; one call site, pinned by the `253`
leg). **The flip is resolution-only, three ways**: the `=0` acceptance is
**8/10 + `matches 30fb99f8`** with **419/419** physics lines identical to
`logs/p94/accept_final.log`; the single arm is **6/9, 14.8 s/attempt,
`matches 8952c320`** with **346/346** raw lines identical to
`logs/p71/accept_rails_none.log` (the exit=1 is the standing rate-only floor);
and the default's own 20-attempt seed-5 cell is **924/924** identical to P96's
`T5` once the two `[biarm] pre-pose` rows are dropped - their only changed text
is the registered origin label (`1(explicit)` -> `1(default)`). **The shipped
default's census is 0 contacts** (min **+5.9 mm**, `<= 6 mm` **1/20** - the
proxy's own floor on the 6.9 cm pear, 0.1 mm span swing; left min +155.4, right
min +5.9), so P96's pooled **1/40 -> 0/40** transfers. The sanity cell is
**report only**: **12/20 (60 %), 9.70 s/attempt, interval 16.02 s mean / 21.30
p90, window 3.75 / batch 3.72 placed/min, wall 432.4 s, placed/min wall 1.66**,
left 5/10 right 7/10, classes 4 never-grasped + 4 carried-not-placed, **12/12**
payload-present releases `on_belt`, **0/20** descents over budget, `[cycle]`
`prepose` **0.71 s** and `hover` 0.78 -> **0.63 s**. **No rate is claimed**
(P96's count is the draw 29/40 -> 27/40). Both two-line-side references were
re-recorded from same-batch 10-attempt runs: `configs/motion_reference.json` and
`..._twoline.json` `30fb99f8` -> **`1490b63e`** (archives
`logs/p97/motion_reference{,_twoline}_pre_p97.json`); the single reference
`8952c320` is untouched; the final `accept.sh` is **6/10, 9.6 s/attempt,
`fingerprint: matches`, `190: PASS`** and byte-identical to the reference-source
run (459/459). A fresh shard carries `collection.prepose_clear=1 /
_defaulted=true / _z=0.165` (a manifest without `prepose_clear` predates P96);
the `scene` block gains nothing - the pre-pose is a control pose owned by the
`collection` block, not a collider. `selfcheck.sh` PASS (0 failures, 1 skipped;
the `253` leg now reads the flipped table, 42 checks), `211` ok (115 checks),
`106` OK, `107` PASS, `bash logs/p97/gates.sh` rc=0. Pins: `tasks.py`
**`e5087263`**, `rl_env.py` **`eb545c86`** (`TASKS_MD5` follow),
`scripts/253_p96_prepose_selftest.py` **`4c2ffcf2`**, `scripts/selfcheck.sh`
**`bb1f5b53`**, `logs/p97/PREREG.md` **`fecf1a28`**; refs **`1490b63e`** /
**`1490b63e`** / `8952c320`; ckpt `moe_v13s` `61da390a`.

**P87 (2026-11-01) re-baselines the acceptance: the shipped two-line cell
now runs the release trim** (P86's S2 cell, `FRUIT_SPEED_RELEASE`, as a
**two-line-scoped** default), so the acceptance read **7/10, 9.4 s/attempt**
with `configs/motion_reference.json` = **`423896f7`** at the time (re-recorded from
`logs/p87/accept10.log`; the pre-P87 file `eb697f23` is archived at
`logs/p87/motion_reference_pre_p87.json`, and `configs/motion_reference_single.json`
`8952c320` is **untouched**) - **P94 supersedes the count and the reference**
(8/10, `30fb99f8`). **Every two-line rate, span or interval recorded
before P87 is a 2.35 s-release number; `FRUIT_SPEED_RELEASE=0` restores it.**
**P88 (2026-11-01) measured the next lever - the `place` cap - and shipped
nothing**, so every acceptance, reference and store above stands unchanged:
`FRUIT_SPEED_PLACE` stays **off by default** (`PLACE_TWO_LINE_DEFAULT = False`)
because, although the block's mechanism was exact at **-0.77 / -0.92 s** per
placed attempt, the delivered interval rose at **both** seeds
(`logs/p88/RESULTS.md`).

**P89 (2026-11-01) measured the last profile block - the `lift` cap - and shipped
nothing either**, so every acceptance, reference and store above still stands:
`FRUIT_SPEED_LIFT` stays **off by default** (`LIFT_TWO_LINE_DEFAULT = False`)
because, although the block fell to the profile's own arithmetic
(**-0.175 / -0.173 s** against the predicted -0.177 / -0.193, per leg exact,
remainder constant), the delivered interval rose at **both** seeds
(10.59 -> 13.43 and 11.08 -> 12.38 s), the pooled count fell **28 -> 26 of 40**,
and the class did not improve (lift-leg escapes **7/40 -> 10/40**). **Every
profile block of the shipped cell is now measured**: release shipped (P87),
place negative (P88), lift negative (P89) - `docs/THROUGHPUT.md` "Lever 3/4/5".

**P85 (2026-11-01) superseded every acceptance number below in this section: the
shipped scripted cell became the bimanual two-line**, so `scripts/accept.sh` runs
a *different scenario* (7/10, `configs/motion_reference.json` = `eb697f23` at the
time, the two-line floor 0.60) and `FRUIT_BIARM=0` restores the single-arm record
archived at `logs/p85/motion_reference_single_pre_p85.json` (`8952c320`, 6/9).
Read §2's "P85" and "P87" paragraphs before quoting any acceptance, rate or store
from here.

**On this tree (P32, 2026-10-22) the acceptance reads 6/10 with the pear and
7/10 with only the pear profile reverted - both below the 75 % dynamic floor -
and the fingerprint reference was re-recorded from the pear-on run**
(`configs/motion_reference.json` md5 406745c5 -> 25ade92b; the pre-pear file is
`logs/p32/motion_reference_pre_pear.json`). **The 7/10 is not this tree's
rating of the pear**: it predates P32 - it is the pre-session acceptance's own
count on the pre-pear tree (`logs/p30a/05_accept_rails_outer_lift040.log`, which
the pear-off run `logs/p32/92` reproduces on its 381/381 `[fruit]` lines byte-identically) - and the pear-on
run is a *different attractor with a different fruit sequence*, so the two
counts differ by one attempt in one sample and no per-class pear cost is
measured; the pear's own grasp/place is 1/1 with the new pear in the pear-on run (0.312 m, 4.43 N) plus 2/2 old-profile pears in the pear-off control, and the
pear-on losses are the peach/kiwi/orange carry class. Do not read 7 -> 6 as a
pear regression. Because the pear changes the per-instance RNG draw count, a
pear-reverted tree is a *different scenario* and reads `fingerprint: DIFFERS`
against the shipped reference - gate it against the archive with
`python3 scripts/105_motion_regression.py <log> --fingerprint
logs/p32/motion_reference_pre_pear.json`. Evidence WORKLOG "P32 phase B",
`logs/p32/92..94`. The final-tree re-run `logs/p32/D1_accept_pear.log` (P32
phase D) reproduces the pear-on record: **6/10 + `fingerprint: matches`**, its
376 `[fruit]` lines identical to `93_accept_raw_pear_on.log` except the two
print-only output-belt clearance message lines (the Gate-B R5/R6 read).

**P32 phase C (2026-10-22) measured the bed on the two-line (still opt-in) and
found the prepared-next lever a zero-actuation null.** The 20-attempt bed
battery (SEED=5) reads **12/20 = 60 %**, 4.19 batch / 4.22 window placed/min,
pooled interval **14.23/15.50/19.00 s**, idle 15 %/15 %, lock-on 2.77/2.92 s,
with its **own** per-scenario reference
`configs/motion_reference_twoline_bed.json` (md5 dcd19758;
`scripts/190_twoline_gate.sh -m 0.5` PASS; any different bed battery needs its
own re-record). **The bed's cost and delivered density are measured, not
implied:** the phase-A same-sim-seconds pair reads **+24 % wall (285 ->
352-356 s)**, the physics of 21 vs 6.6 live bodies plus the pump's
2.71 ms/sim-s; and on the two-line battery the delivered approach band is
**2-8/10 at the 20 pump instants** with `late_dropped=139.6 s` (the
once-per-boundary pump re-bases the backlog instead of delivering below the
catch floor) - quote those, not the lattice's 19.1 fruit/m. The prepared arm
(`FRUIT_PREPARED_NEXT=1`, default off) is
**byte-identical to the control** (`built=0 empty=19`): the build->consume gaps
are **left 7.5-15.1 s / right 2.7-11.1 s**, while a row released at the maximum
along 0.668 m can drift only `(0.668-0.389)/0.12 = 2.3 s` before the
consumption re-check drops it - so even a stocked belt would build rows it
drops. **The two-line's dispatch cost is the pre-pose transit (lock-on
2.77/2.92 s = the 15 % idle), not the selection; the prepared set has no room
on this line at the shipped cadence.** The bed stays default off. Evidence
WORKLOG "P32 phase C", `logs/p32/A0..A3` + `A_phase_c_metrics.txt`.

**P33 phase 1 (2026-10-23) measured the two-line mid-attempt pump: the band
fills, the catchable window does not, and the wall cost stands.**
`FRUIT_FEED_CADENCE=1` now arms on the two-line scheduler: the same
`_feed_tick` is installed as `CoopSession.feed_pump` and `TickRelay.schedule`
calls it on the main thread once per **shared physics tick** (stride 4 = 4 mm
of belt travel, `advance_furniture=False`); default off, and the shipped /
F2 / single-arm paths are byte-unchanged (the two-line control replays A0
**826/826** `[fruit]` lines after its 20 new census rows and the two static
scene prints; the single-arm control replays `87` **436/436**). The A/B (A0's
scenario, 20 attempts, pump vs control): the delivered band at the pump
instants **4.2 -> 8.3 / 10** (2-8 -> 2-11, 14/157 at the cap) and
`late_dropped` **139.6 -> 7.9 s** (the batch-start prime residual; rebased
16 -> 1, holds 0 -> 14) - but quote the **same-instant census, 5.5/6.9 ->
8.4/8.8** (left/right means at the selection instant; 4.2 -> 8.3 puts 20
boundary samples against 157 continuous ones). The catchable per-arm window at
the selection instant **does not rise** (left 1.5 -> 0.9, right 2.4 -> 2.2)
because the aperture is a **stock-depth ceiling**: the bed caps at 10 bodies
over a 0.58 m stocked depth (4.1 rows x 2.4) and only **0.28 m ~= 2 rows ~= 4.8
bodies ~= 1.8 per grade-pure lane** sits above the ~0.40 m catch floor - so
8.3/10 = 83 % of the band's capacity is already delivered, the right's 2.2 is
about the ceiling and the left's 0.9 is the grade-mix shortfall.
**Starvation is worse per slot, not flat**: left **0/10 -> 5/15 = 33.3 %**
steady-state (37.5 % of all slots vs 9.1 %; Fisher two-sided ~0.057 on the
steady-state pair, 5/15 vs 0/10), right 0/10 -> 2/12, and the census names a
**grade drought, not a stock shortage** - at every
starved instant the band is full (7-10/10) with nothing admitted (`admitted=0`;
6 of the 8 starve episodes are `admitted=0`, 1 is `admitted=2 window=0` at the
floor, 1 the empty-belt prime). The interval reads 14.23 -> 13.68 s pooled mean
on a **different branch** (13/20 left 9/right 4 vs 12/20 6/6; right idle
15 -> 22 %, lock-on 2.92 -> 4.14 s, three retry episodes), and the wall is
**+20.9 % (484 -> 585 s) = +4.4 % sim span (171.8 -> 179.4 s) x +15.7 % per
sim-second (2.82 -> 3.26 s)** with a supply burn of **432 releases / 348 bed
placements for 13 arm placements** (444 draws, `reached_end=320`) against the
control's 126/107 for 12. The single-arm pair reproduces the phase-A read -
selector window **4.6 -> 3.9**, live 6.6 -> 20.4, band 2.6 -> 7.9, **+30.1 %
wall at equal sim span (149.7 vs 148.7 s)**; the recorded phase-A pair +24 % -
so the knob stays default off: **the density is a physics lever, not a free
win**, and more stock is not the lever (a lower floor is closed by R3/R11-A; a
higher station is bounded at <= 0.10 m by the R10-A intercept map; the row
composition is a drought/variance lever with the mean ~1.8 eligible/lane
unchanged, needing its own pre-registration, reference and clearance report).
Evidence WORKLOG "P33 phase 1", `logs/p33/`.

**P109 (2026-11-03, `logs/p109/`; default off, **nothing adopted**, no `configs/`
change, no reference re-recorded): P108's ① is measured and **it reverses one term
of P108's "cheapest complete package"** - the descent margin is **load-bearing,
not a cushion**.`FRUIT_DYNAMIC_DESCEND_MARGIN` 0.15 -> 0 moves the descent-start
gap to the aim **exactly 18 mm** and flips **every** attempt's end-of-descent
arrival from upstream to past the aim (`past_aim` **0/76 -> 79/79**), which puts
the catch-up on the wrong side of its own 30 mm feed-forward and opens a
**bistable** failure (converge to the 6 mm tolerance, or run away to
**233-269 mm**) that costs **5 of 79** battery attempts against **0 of 76** and
the placed count at **4 of 4 seeds**. **The instrument correction comes first,
because P108's 18 mm was measured on the wrong gap**: `[task] dynamic descent`'s
**`fruit dy` is algebraically invariant** to the knob (`intercept = fruit -
speed*t_desc`, so `dy == speed*t_desc`; measured p50 **83.0 / 82.0 / 83.0** at
margins 0.15 / 0.075 / 0 across twelve cells), and the gap it sets is
**`g0 = fruit dy + shift = deadline = speed*(t_desc + margin)`** - p50
**99.9-100.4 -> 90.8-91.0 -> 82.1-82.3 mm**, i.e. **+17.6 / +18.3 / +17.6 /
+17.7 mm** M0->M1 at seeds 5/6/101/202 with the half rung exactly mid-ladder;
the **selector floor** (`_dynamic_pick_lead() + speed*select_s + margin`) moves
with it, so the **selected sequence differs at every seed** and a count delta
across arms is partly a branch (E0). **The arrival** is `g0 - 0.12 m/s * steps`
(steps 88-94 printed, belt measured 1.00x): **M0 +10.6 mm (0/76 past the aim),
M0.5 +1.3 (9/75), M1 -7.3 (79/79)** - and the catch-up commands
`fruit + v*0.25 s`, i.e. **30 mm further downstream**, so a fruit already 5-8 mm
past the aim is a race the arm loses at 1 mm/tick. **The failure is bimodal, not
graded**: the residual's p50 is 5.8-5.9 mm (the tolerance itself) in every arm
and the runaways are 233.2-269.4 mm; **all five battery runaways are M1 at seed 5**
(5/20 vs 0/19, Fisher **p = 0.047**; the other three seeds 0/60), pooled with the
acceptance **8/89 = 9.0 % vs 1/86 = 1.2 %, p = 0.035** - the shipped arm draws
the class too (1 of its 10 acceptance attempts), so the margin depresses the
rate ~7x, it does not delete it. **The other no-grasp events are a different
class** (M0's one and all three of M0.5's read a converged 5.8-6.0 mm residual
then lose the payload at the close, `logs/p42/SIM_LIMIT.md`); only M1 produces
the >200 mm timing runaways. **Counts**: M0 **49/76 = 64.5 %**, M0.5
**49/75 = 65.3 %** (a draw, p = 1.0), M1 **41/79 = 51.9 %** (**down at 4/4
seeds**, -2/-3/-2/-1, pooled p = 0.143). **The acceptance A/B** (ten attempts,
the shipped two-line - so the two-line **does** read the knob, both stations'
shifts go to ~0 and the runaways rise): unset **8/10, `fingerprint: matches
30fb99f8`, `190: PASS`, 419/419 identical** to `logs/p108/accept_noharm.log`;
M1 **4/10 = 40 %** (below the 0.60 floor), no-grasp 2 -> **5**, runaways 1 -> **3**,
budgets clean, fingerprint DIFFERS by construction. **Verdict: not a lever** -
E1b passes (+17.6..18.3 mm >= the registered 12) and **E3 / E4 / the acceptance
gate all fail**; **the dose axis says it from the other side**: half the margin
keeps the arrival on the correct side (+1.3 mm, 0 runaways in 75) and **buys
nothing** (a count draw), so there is no throughput on the far side of the
boundary. **Read rule: on this line the arrival offset is not an error to
minimise** - a static descent under a moving belt *is* the lead, and the margin's
job is to make the catch-up's residual **positive**; a shorter descent
(jerk-bound, P91 §3) or a smaller margin both spend the catch. The remaining
lever on that term is P108's **aperture precondition** (`clr < 0` 32/51 -> 4/57)
or a **centring guide / workstation**, never another margin rung. No-harm:
`M0` replays P108's S cells **860/860** and **853/853** (`[cycle]` dropped) and
the acceptance **419/419**, `selfcheck.sh` **PASS (0 failures, 1 skipped)**,
`106` OK, `107` PASS (21 checks), all twelve cells' descents inside budget (worst
`|v|max` **0.1230** vs 0.160-0.162, lurch 0.039 vs 0.291), landing
**49/51 / 49/49 / 41/44** payload-present `on_belt`. Pins: `tasks.py`
**`d341b0da`**, `rl_env.py` **`bf4c56fa`**, `bimanual.py` `9b7fc33f`,
`fruits.py` `dcabe16b`, `assets.py` `eb30c77a`, `scene.py` `a0199097`; refs
**`30fb99f8`** / **`30fb99f8`** / `8952c320` untouched; ckpt `moe_v13s`
`61da390a`; `logs/p109/PREREG.md` **`192a0c1b`**. Evidence `logs/p109/`.

**P110 (2026-11-03, `logs/p110/`; a census + a fixture in `logs/` - **no `src/`
or `configs/` change, nothing adopted, no commit, every reference untouched**):
the presentation lane - P108's routes 1 and 2's gate, the last unspent term - is
**measured and closed: a metering gate is a real, cheap, non-crushing mechanism
and it cannot centre the cage's ring.** The **census** first (offline,
`logs/p110/census.py`): the **split at the band entry** is **55.8 mm along-belt /
2.6 mm lateral** p50 (the 11.8 mm the record quotes is the **max over the
window**, the arm's x-tracking lag), a **92.5 %** along-belt share; the term is
**`fruit dy = speed * t_desc` = 83.0 mm** (114 descents) - the belt travels 83 mm
while the hand descends 56-60 mm - and the entry offset is that clock minus the
leg's first `s_enter = 0.095 + 0.060 - (0.0805 + 2r)` = 4.5-38.5 mm, i.e.
**29.7-76.6 mm by radius** with `A_y = 2(dy + r)` **182 mm** p50. The measured
55.8 sits **below** the 62.8 mm a 6 cm fruit predicts **because the plates arrest
the payload** - **25 % of the band window's ticks run below half the belt speed**
(p90 58 %) - so the belt is already slipping under the payload for part of the
descent. **Form (a), a lateral guide, is dropped by arithmetic**: `dx -> 0`
leaves `A_y` **182 -> 182** (the aperture need is per axis and along-belt
dominates), so P108's screen (120 mm 0/8, 160 5/8, 210 7/8) is unchanged, and its
only purchase is 39 % of the *close-time* radial (8.8 of 22.7 mm). The tree's own
lateral guides prove it geometrically: `conveyor.containment_parts`' side fences
are a **0.300 m channel against a 0.160 m delivered band**, so they never touch a
fruit; a guide that did would have to be narrower than the band, and the open
hand already needs 0.132 m of it. **Not built, not measured.** **Form (b) is
built as a fixture** (`logs/p110/fixture_gate.py`: the real kinematic belt +
`PhysxSurfaceVelocityAPI`, the real 16-fruit pool 29.6-69.6 mm / 9.5-122.8 g /
mu 0.51-0.92, a kinematic kerb across the belt 20 mm downstream of the station)
and it **works**: **16/16 fruits held at every height 8 / 10 / 12 / 14 / 20 / 30 /
45 mm**, **0 escaped**, **no climb**, the **belt at -0.120 m/s in every cell**
(never stopped), the **steady drag 0.11-1.05 N** (the 1.27-2.52 N peak p50 is the impact),
the **hold's span 0.85-1.83 mm** p50 (max 3.7-6.6) and the **parking position
13.1-21.7 mm across the pool**; a **taller gate parks further upstream**
(`y_park` +0.0024 at 8 mm -> +0.0115 at 45 mm), and the shipped line's own
`enforce_transport` nudge is **inert** against it (`wake=0` == `wake=1`).
**The queue is where it breaks**: the next fruit arrives **inside the same
attempt** (the shipped 0.83-2.9 s cadence against a 15.1 s pick), which costs the
hold **1.8 -> 4.3 mm** with one behind and **4.9 mm** (max 30.8) with three - and
**1 of 16 is expelled past the gate** (a 65.1 mm peach, parked 501 ticks then pushed 62 mm
through) - the 8.1-fruit-per-cycle rate arithmetic (1.81 m of queue into a 1.60 m
belt) measured as a load. **The release is not the problem**:
`mu_pair * steady` = **0.16-1.32 N = 1.3-10.4 %** (median 6 %) of the pinch's 12.7 N.
**The phase's other half is a correction to the record**: P107/P108's "enclosure
at >= 3 pads" is **11/74 raw** but joined to the descent's own `end=` and the
ring's aperture it is **5 blocked-descent jams** (`end` p50 79.8 mm, `F` up to
**2920 N**), **4 over-closures** (`aper` 32.5 mm on 31-37 mm fruit, `F` 119 N)
and **2 clean enclosures = 2.7 %** - and the two clean rows read `clr` **-9.5**
and **+31.7 mm**, so the approach clearance does **not** order them (the jams are
the large-`clr` class, +32.9). The modal grasp is **2 pads at the cap** (22/74,
`F` 9.74 N = 1.99 cap-pairs): a V-block, `n = 2`, the **same** axial capacity as
the shipped pinch. **And the closure's algebra explains it**: one radial synergy,
four force-capped position pads, `a = 0.49 d`, cap 4.90 N, `k = 1e5 N/m` -> the
elastic allowance is **0.049 mm**, the near pad is commanded `delta + 0.01 d`
inside the surface and the far pad `0.01 d - delta` short, so **the far pads
reach only when `delta < 0.01 d = 0.6 mm`**; above that the payload sticks and is
*launched* (`bat` 27-82 mm, `bat_rel` 9-330 mm). **The line cannot deliver
0.6 mm**: the catch-up's tolerance is **6 mm** (`FRUIT_DYNAMIC_CATCH_TOL`), the
measured close offset **8.8 / 20.2 mm** (P108), and the gate's own hold **1.8 mm
within a fruit / 17.5 mm across the pool** - **3-29x** too coarse. **Verdict: the
presentation lane closes - DETECTED BUT NOT CONVERTIBLE**; the levers the record
now leaves are a **compliant closure** (per-pad compliance, the only term the
algebra leaves standing, a `cage_hand.py` change), a **sub-mm catch tolerance**
(0.5 mm; only coherent with a stationary fruit, i.e. on the gate + magazine), and
`docs/LEFT_ARM.md`'s two sanctions (**a new pad asset**, **a real-jaw clamp-force
anchor**). **Not a lever, and now measured as such**: a bigger aperture (P108), a
lateral guide (0 % of `A_y`), a metering gate (3-29x too coarse), the descent
margin (P109), the seat (P42), the force cap (P76/P77), the closure depth (P108),
the profile blocks (P87/P88/P89/P91). No-harm is the acceptance itself (no `src/`
file changed): **8/10, 9.0 s/attempt, `fingerprint: matches`, `190: PASS`**, its
**`[fruit]` stream byte-identical** to `logs/p109/accept_final.log` (420 lines, same md5);
`selfcheck.sh` **PASS (0 failures, 1 skipped)**; `211` **ok (115 checks)**;
`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`** stand. Pins unchanged: `tasks.py` `d341b0da`,
`rl_env.py` `bf4c56fa`, `bimanual.py` `9b7fc33f`, `fruits.py` `dcabe16b`,
`conveyor.py` `fb2c58c6`, `assets.py` `eb30c77a`, `scene.py` `a0199097`;
`logs/p110/PREREG.md` **`cce8838c`**; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p110/`.

**P111 (2026-11-04, `logs/p111/`; default off, **nothing adopted**, no `configs/`
change, no reference re-recorded): P110's item 1 - the **compliant closure** - is
built and measured, and the answer is **a gentler jam, not a self-centring
chuck**: the offset at the close's end *grows* (median `off - off0` **+0.2 mm**
on the rigid ring and **+0.7 / +1.9 / +2.0 / +1.3 mm** on the compliant arms),
the **clean enclosure stays 0-3 rows per arm** (0/73 at `k = 1e3` against the
rigid ring's **3/76**) and the placed count does not rise (**T1 16.4 % / T2
23.4 % / T4 17.3 % / S1 13.5 % against R 25.0 %**, all Fisher **n.s.** at
n = 73-77; the shipped hand is **65.8 %**). **The algebra is why**:
`drive = near - far`, `fric = 2 mu perp + mu_belt m g` (the payload's motion is
*normal* to the near/far faces and *tangential* to the perpendicular pair), so
`delta_inf = (2 mu - 1) * min(s, cap/(2 mu k))` and the 4-contact state needs
`delta < s - 0.5/k` - **`mu > 1` denies the last millimetre at every `k` and
every cap** (the measured `mu_pair` is **1.25-1.46**, P104's `mu_app` averaged
with the pad's 2.0). The ladder has a **knee at `k* = cap/(2 mu s)` ~ 2.2e3 N/m**:
above it the perpendicular pair is at the cap (`fric = 2 mu cap = 12.8 N > cap`)
and nothing slides (the shipped ring); below it the payload slides to
`(2mu-1)s` = 1.1-1.9 s. A **3-jaw** would close it (`2 mu s/(1.5+mu)` = **0.82 s
< s**) - the *count of tangential contacts* is the lever, not the drive. **The
build** is three windows, one knob each (`FRUIT_CAGE_PAD_STIFFNESS` = the
approach, **`FRUIT_CAGE_CLOSE_STIFFNESS`** = the close, **`FRUIT_CAGE_HOLD_STIFFNESS`**
= the carry's **hard stop**, both new and default off): `close_begin` puts the
drives on the close profile, `close_done` re-writes them **with the target
unchanged** so a soft close re-loads to `min(k_hold * pen, cap)` **at the
aperture it found**, and an open command reverts - so the shipped cage issues no
drive write at all. **The instrument** is `[cage] off0= off=`: the payload's
radial distance from the ring's **axis** (the cage base's xy) at the close's
start and flush, two reads per attempt and no control input - it is what makes
"centring" measurable, and it shows the close-time offset is **2.9-3.1 mm p50**,
not P108's **8.8 mm** *aim* (`PREREG_A1` records that correction), and it
separates the cage's arm-never-arrived class (85-1336 mm, **19-37 %** of rows,
identical in every arm) from the rows that can say anything. **Why it cannot
centre, measured three ways**: the ring is a **two-pad V-block at every
stiffness** (the modal `pads` count is **2** in all six arms, 19-30 rows of
37-77, including the rigid one; the clean 4-contact set is 0-3 rows), the
perpendicular pair **cannot load** at this squeeze (the aperture is
`0.98 x` the *widest* extent, so any roundness `> s` leaves it 1-6 mm short - the
pool is 0.02-0.20 d against `s` = 0.005-0.015 d), and at `mu > 1` even a loaded
pair jams. **What compliance does buy** is the *force at the freeze*: **4.90 ->
0.6-1.8 N** (T1's flush rows read 3.5-6.6 N over two pads against R's 8.7-9.8),
i.e. a genuinely gentler contact that converts nothing. **The scoped form was
added because the always-soft pad is a poor position *source***: T1's first cell
read **1/20** (off-ring 37 %, jam 11/73) against the rigid ring's 7/19, so T4
(rigid approach + soft close + stop) is the form a real spring-loaded pad has -
it recovers nothing either (17.3 %, clean 2/75). **The count is a dose, not a
rate claim**: R 25.0 % / T2 23.4 / T4 17.3 / T1 16.4 / S1 13.5, *monotone in
compliance* but **not significant at n = 75**, and the **seed-5 pair alone**
(R 7/19 vs T1 1/20, p = 0.020) would have over-stated it 5x - the fresh seeds
read T1 **5/19 twice** (P93's rule again). **The endpoint itself is
force-thresholded** (a pad counts at 0.5 N, which a soft drive reaches at `0.5/k`
of penetration), so the raw `>=3` share *falls* with compliance
(17.1 -> 5.2 %) - a bias **against** the compliant arm, stated and not read as a
result; the clean subset is 0-3 rows either way. **Guards**: **no crush** on any
arm (`sep@loss - dia >= -15 mm`, 0 legs; the cap bounds the force by
construction), no new failure key, the landing misses are the
`release_bottom = -184 mm` upstream-lost class (P86/P87), and the **descent
budget fails on the cage arms *including the rigid control*** (0-4 legs per cell,
`R_s202` the worst at 4 - P108's blocked-descent class, **not re-tuned**).
**No-harm**: `scripts/accept.sh` with every knob unset is **8/10, 9.0 s/attempt,
`fingerprint: matches`, `190: PASS`**, its **421 `[fruit]` lines 421/421
byte-identical** to `logs/p110/accept_noharm.log`, and the two controls are
[`[fruit]`-stream replays] **C_s5 = `logs/p108/S_s5.log` 621/621** and **R_s5 =
`E_s5` 531/531** (the 19 `[cage]` rows identical with `off0`/`off` stripped), so
the new fields and call sites are inert and P108's cells are admissible. **A
compliant pad is a hardware change** and the phase prices it: a **spring-loaded
pad with a hard stop** (the form built here - gentle close, shipped hold,
converts nothing) or a **force-controlled finger** (the only form that can be
stiff during the approach and compliant only inside the closure, which §4.4
shows is required). The levers below the ring, priced: a pad material with
**`mu < 1`**, a **3-jaw ring**, or P110's **0.6 mm** positioning (no passive
element delivers it). Selfcheck **PASS (0 failures, 1 skipped)** with the new
`P111 cage compliance` leg, `106` **OK**, `107` **PASS (21 checks)**. Pins:
`cage_hand.py` **`ac7c7c0f`**, `tasks.py` **`a587cd21`**, `rl_env.py`
`TASKS_MD5` follow, `scripts/257_p111_cage_compliance_selftest.py`,
`scripts/selfcheck.sh`; references **`30fb99f8`** / **`30fb99f8`** / `8952c320`
untouched; ckpt `moe_v13s` `61da390a`. Evidence `logs/p111/`.

**P112 (2026-11-04, `logs/p112/`; the third hand kind `cage3` ships **default
off**, nothing adopted, no `configs/` change, no reference re-recorded): the owner
chose P111's item 2, the **three-jaw ring**, and the phase answers it in the
algebra's own terms - the closure **does** centre and the 3-jaw **is** the only
ring that loads its own pads, and **neither reaches the delivered count**.**  The
**algebra** (`algebra.py`, 2-D, with the **tangential projection** P111's closed
forms dropped): `delta_inf = sqrt(3) mu s/(1.5 + (sqrt(3)/2) mu)` = **0.84-0.92
s** for three pads against **`mu s` = 1.00-1.46 s** for four at the measured pair
friction 1.25-1.46 (thresholds `mu < sqrt(3) = 1.73` and `mu < 1`), so P111's
`(2mu-1)s` / `2 mu s/(1.5+mu)` are 20-30 % pessimistic on the 4-jaw and ~9 %
optimistic on the 3-jaw and **both verdicts survive**.  The registered **kill does
not fire** (worst `delta_inf/s` 0.915), and `k` is a **window** - the cap
saturates the near pad first - **[2.9e3, 3.8e3] N/m** over the pool, build 3300.
**The build** is `CAGE_KINDS = (cage4, cage3)`, three azimuths at 120 deg, a
**20 mm plate** (the 120 deg neighbour bound is 22.5 mm at the closed aperture;
the length stays 60 mm, the tool offset 70 mm), and the phase's one structural
change: a hand-owned **aperture law** (`CageHand.aperture_extent`, one `getattr`
hook in `tasks.pinch_width`, no law = the shipped expression bit for bit).  A
ring closes on one scalar and the *width* decides whether its pads can load: the
four-pad ring takes the **widest** horizontal extent (which is why its opposed
pair never loads - P111's V-block), a three-pad ring must take the **narrowest of
its own three pad axes**.  **The fixture** (`fixture_cage3.py`, 390 closures) is
the decisive test and the expensive lesson: **three passive supports failed at the
scale of the measurement** - a static table, a kinematic table and the shipped
belt at 0 m/s all let a 0.1 kg payload sink 2 mm and creep 4-5 mm **with zero pad
force**, because `meshes.axis_extent` is the *undeformed* profile and the **mesh
is 2-6 % bigger** - so the adopted form sets the scene's gravity to 0 (it drops
the support's `mu_b m g`; stated).  Result: **both rings centre** a 0-20 mm
arrival to 0.5-1.9 mm (P111's line read of +0.2 mm was about the *delivery*), and
**only the 3-jaw loads its pads**: `pads == 3` on **18/30** cells against
`pads == 4` on **2/30**; the min-extent law over-closes on the smallest fruit
(`sep - dia` **-7.9 mm** against the 4-pad's -1.8).  **The battery**
(`PREREG.md` `77720306e9328cf6e7853427cbe41f94`, 10 attempts, T at 4 seeds / C at
2): **C 13/18 = 72.2 % vs T 7/38 = 18.4 %** (Fisher p = 0.000, every seed
negative), **below even the rigid 4-pad ring's 25.0 %**, and the **clean enclosure
is 0 of 38** - the three `pads == 3` rows are all **jams** (`end > 15 mm`), P110's
split again.  The mechanism is separated: `[cage] off0` p50 3.2 mm with `off -
off0` **+0.50 mm**, i.e. **the closure centres and the line does not** - the
payload arrives *moving*, the close **freezes at its first contact** (holding an
aperture `2 delta` too wide; seated legs' `force_min` p50 **0.00 N**), and the
60 mm plates **block the descent** (`|v|max` **0.437** against 0.160, C 0.122).
**Verdict: NOT ADOPTED** - the two rings differ exactly where the algebra said
they would, and the difference does not reach the count; the hardware price is a
**different assembly** (a scroll disc or three links driving three jaws on one
scalar, a new plate, three 120 deg guides, the same 20 x 60 mm pads) and the
battery prices it at a 4x deficit.  Guards: selfcheck **PASS** (the new `P112
three-jaw ring` leg, 23 checks), acceptance **8/10, `fingerprint: matches`,
`190: PASS`**, landing **7/7 T + 13/13 C** payload-present `on_belt`, budgets
**fail on the treatment and were not re-tuned**.  **Read rules**: a ring's pad
count is an endpoint *only* joined to the descent's `end` and the aperture (a
jammed ring reads its count); a fixture must first prove its support (a sinking
payload and a creeping one look identical in `off`); and `delta_inf` is a
*tangential-contact* number - quote the projection with it.  Pins:
`cage_hand.py`, `tasks.py`, `rl_env.py` (`TASKS_MD5` follow),
`scripts/258_p112_cage3_selftest.py`, `scripts/selfcheck.sh`; references
**`30fb99f8`** / **`30fb99f8`** / `8952c320` untouched; ckpt `moe_v13s`
`61da390a`.  Evidence `logs/p112/`.

**P114 (2026-11-05, `logs/p114/`; default off, **nothing adopted**, no `configs/`
reference moved, no commit): the owner's system requirement - the cell must be
portable to other pipeline scenarios and must decide **where** to put each fruit
from an instruction - is answered with a **scenario descriptor**, an
**instruction resolver** and a **capability map**; the physics lane stays closed
(`docs/END_EFFECTOR_DECISION.md`). The phase's audit
(`logs/p114/COUPLING.md`, every site read with its file:line, four groups:
geometry, the fruit->destination rule, the supply, the calibration) names the
two hardest couplings: **arm = grade = lane** is one object written in four
places (`rl_env.py:3529`, `tasks.py:11947`, the worker's `bin_index`, the
grade-pure selector `:9251-9290`), so the arm is chosen before the fruit is
seen; and **the place target is derived from the place leg's *name***
(`tasks.py:5032-5033`, `index = 0 if "0" in name else 1`), so there is nowhere a
"destination with its own target" can exist. The build: `scenario.py` (new,
pure data) - a **strict descriptor loader** (`FRUIT_SCENARIO=<path>`; unknown
keys, duplicate ids, a side/target contradiction, an unknown reach status or
schedule raise) with stations/pick/place/belt/destinations/supply, and an
**instruction parser/resolver** (`FRUIT_SORT_INSTRUCTION=<path|inline>`) of
ordered `condition => destination` rules (`grade=A => 0`, `size<40 => 1`,
`default => 0`, `skip`; sizes in mm; first match wins; `default` last) with
every refusal naming file and line; `tasks.py` gains `_place_xy_for` (replaces
the name->lane read), `_calibrate_sort_destinations` (an `auto` destination is
solved with the place leg's own position-only IK, 25 mm bar), `_sort_admits`
(destination in the carrying arm's capability set), the fruit's own destination
at dispatch, `_arm_for_destination` (the map back to the one arm that can serve
it) and the `[sort]` per-destination ledger; `SceneConfig`/`SupplyPlan` apply the
descriptor as **defaults** (an explicit env knob wins). The capability map is
the physics the audit found: **left serves +Y, right serves -Y**, so the
instruction resolver **refuses** a mapping no arm can reach rather than placing
it wrongly. **Validation** (endpoint = the ledger's assignment accuracy, never a
rate): **(i) default off** is 8/10, 9.0 s/attempt, `fingerprint: matches
30fb99f8`, `190: PASS`, and its **421 `[fruit]` lines are 421/421
byte-identical** to `logs/p110/accept_noharm.log` with no `[sort]`/`[scenario]`
row at all; **(ii) today's routing as an instruction** (A->0, B->1, C->skip)
replays the **same 421/421 stream with the `[sort]` rows dropped**, same 8/10,
`fingerprint: matches` - the compiled predicate *is* the shipped one; **(iii-b)
a size-class rule** (`size<40 => 1`) routes 12 fruit left / 4 right, **7/7
releases in the instructed destination**, 0 mis-sorted, a grade-C 3.6 cm
strawberry on the right and a grade-A kiwi on the left (fingerprint DIFFERS by
construction; budgets pass `|v|max` 0.114/0.160); **(iii-a) the 3-destination
cell** adds `dest 2 = (0.38, +0.55)` on the +Y belt with `reach: auto`, the
startup solve reads **6.0 mm**, the map is `left=[0,2] right=[1]`, the 4
grade-C fruit are **unassigned and never selected** (no default), 20 attempts
split 10/10 and **13/13 releases land in the instructed destination** (dest 1
7/7, dest 2 6/6; targets 71 mm apart, release clouds ~78 mm apart); **(iv) the
refusal**: the tray target `(1.65, +0.50)` solves to **1138.3 mm**, prints
`UNREACHABLE`, and the run aborts with `ScenarioError("[sort] REFUSED: ... no
arm can deliver there")` **before the first attempt** - zero attempts, zero
mis-sorts. **Verdict: portable as data, the instruction layer works, nothing
ships**; the price of a new pipeline is **a JSON + a solve + the gate** (before:
6-8 code sites across four drivers and the task). **Still not portable** and
named: a third **physical** lane/tray (a scene build; the descriptor can only
add a target on an existing lane), a place destination at a different height,
the tactile/force channels and the hand's limits, and **perception** - colour is
not a per-instance attribute in the sim and grade/ripeness/defective are drawn
labels, so the layer is exact for species/size and a *labelling interface* for
the rest until a classifier feeds it. Named next: the vision attribute source,
a per-destination height / third belt, the policy-side dispatcher, an overlap
station. No motion reference moved or was re-recorded (`30fb99f8` / `30fb99f8` /
`8952c320` stand). Pins: `scenario.py` **`674194fe`**, `tasks.py`
**`15d2348a`**, `assets.py` **`165328af`**, `fruits.py` **`e807216c`**,
`rl_env.py` **`476d5782`** (`TASKS_MD5` follow), `20_pick_place.py`
**`986d726d`**, `40_collect_demos.py` **`65683b8f`**, `60_eval_policy.py`
**`22ca84f2`**, `selfcheck.sh` **`c833520f`**, `259_p114_scenario_selftest.py`
**`fd6afd02`** (39 checks), `260_p114_instruction_selftest.py` **`a537cf09`**
(19 checks), `configs/scenarios/shipped_twoline.json`
**`290b8a0a`**, evidence descriptors **`35707bf3`** / **`2ebb722e`**;
`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**, `106` OK, `107` PASS
(21 checks). Evidence `logs/p114/`.

**P115 (2026-11-05, `logs/p115/`; default off, **nothing adopted**, no
reference moved, no `configs/` reference touched): the instruction becomes a
sorting **spec** an operator can write and trust.** Three additions, all inside
the armed path: **(1) `and`** conjoins up to three attribute terms in one rule
(`species=apple and size>=66 => 1`; **every** term must match; `or` stays
written as more rules because the first match wins), carried in a new
`Rule.terms` while the P114 `key`/`op`/`value` stay the **first** term (the
`260` leg's assertions are unchanged); **(2) the decision is legible** - an
armed run prints one `[sort] rule N: <text> (arm X)` row per rule, and every
`[sort] attempt` row gains **`rule=<n>`** (the 1-based firing rule, `default`
counts), which is what makes an `and` rule auditable; **(3)
`FRUIT_SORT_STRICT=1`** (default off) turns an instruction that leaves fruit
**unmatched** into a **startup refusal before the first attempt**, naming what
it dropped, while a deliberate `skip` stays allowed (a decision is not an
oversight). Four canonical files ship in `configs/instructions/`:
`shipped_grade.txt` (today's routing), `by_size.txt`, `species_split.txt`,
`compound.txt`. **Measured** (the shipped scripted two-line, `SKIP_SELFCHECK=1`,
one claim per run; the endpoint is the ledger's **assignment accuracy**, never a
rate): **unset** is **8/10, `fingerprint: matches`, `190: PASS`**, and its **421
`[fruit]` lines are 421/421 byte-identical** to `logs/p110/accept_noharm.log`
(`logs/p115/compare_unset.txt`) - every new print and read is inside
`if self._instruction is not None`; the **compound cell**
(`species=apple and size>=66 => 1`, `size<45 => 1`, `default => 0`, 20 attempts)
covers `pool=16 mapped=16 unassigned=0`, releases 12 and lands **12/12 = 100 %
in the instructed destination, 0 mis-sorted**, with the per-rule ledger reading
**rule 1 1/1/1, rule 2 8/6/6, rule 3 11/5/5** - the witness is attempt 16,
`apple 7.0cm grade=C arm=right rule=1 dest=1 in_dest=1`: a **grade-C apple on
the right belt**, which the shipped grade routing can never produce; the
**strict cell** (`"grade=A => 0"` + `=1`) raises
`ScenarioError("[sort] REFUSED: FRUIT_SORT_STRICT=1 but the instruction leaves
10 of 16 fruit unassigned (lychee 34mm grade C, strawberry 37mm grade B, apple
65mm grade B, pear 61mm grade B, ...)")` from
`PickAndPlaceTask.__init__` **before `go_ready`** - zero attempts, zero
placements. **No rate is claimed**: 12/20 is a branch draw (the family's own
seed-6 controls read 12/20 in `logs/p92/C6.log` and 10/20 in `logs/p80/T6.log`)
and the routing changes which arm sees which fruit, not a grasp parameter; the
compound branch's budgets **PASS** (worst descent `|v|max` 0.1210 against
0.160-0.161, lurch 0.036 against 0.291; the carry cones are reported, not
gated). Selfcheck **PASS (0 failures, 1 skipped)** with the new `261` leg (54
checks: the grammar, precedence, every refusal, the four files, and the
`tasks.py` shape of the table + the guard), `106` OK, `107` PASS (21 checks).
Pins: `scenario.py` **`fb1bb9bc`**, `tasks.py` **`0a703d1b`**, `rl_env.py`
**`df148d84`** (`TASKS_MD5` follow), `261_p115_instruction_selftest.py`
**`5e8a5429`**, `selfcheck.sh` **`18d04455`**, `p114_report.py` **`6e2bf3af`**
(the attempt regex gained an optional `rule=` group; P114 logs still parse),
`configs/instructions/{shipped_grade,by_size,species_split,compound}.txt`
**`71504e3d` / `b6367de8` / `2764500a` / `98d0bc49`**; references
**`30fb99f8` / `30fb99f8` / `8952c320`** untouched. Evidence `logs/p115/`.

**P116 (2026-11-06, `logs/p116/`; default off, **nothing adopted**, no
reference moved): the instruction is planned and linted before it runs, and the
owner's two-rule example is measured.** The owner's sentence *"把 A 级果放在左边
盒子里，把苹果放在右边盒子里"* contains a real **overlap** - an A-grade apple
matches both rules - which the runtime resolves by **precedence** (first match
wins) and which the ledger could not show. `scripts/262_sort_plan.py` now
evaluates an instruction **offline** over the cell's own attribute space
(species x 5 diameters x 3 grades = **120 cells** from `SceneConfig`;
`ripeness`/`defective` only when a rule names them) and prints the rule table
with each destination's arm, every **overlap pair** (the earlier rule wins, with
the count and an example fruit), the **partition** per destination and the
cells that match no rule; `--strict-overlap` exits 1 on any overlap, so an
instruction library can be linted in CI. New operator **`!=`**
(`grade!=A`, `species!=apple`) makes *"the rest of the apples"* expressible
without relying on order: `grade=A => 0` + `species=apple and grade!=A => 1`
reads **OVERLAP: none** and the **same** partition as the ordered form
(dest0 **40** / dest1 **10** / skip **70** of 120). Three example files ship
(`owner_a_left_apples_right`, `owner_apples_first`, `owner_precise`); the two
ordered forms report the same pair with the winner flipped - dest0/dest1
**40/10** against **35/15**. **Measured live** (the shipped scripted two-line,
`FRUIT_SUPPLY_SPECIES=apple` so the overlap actually occurs, 10 attempts):
**8/10 placed, 8/8 released payloads in the instructed destination (100 %),
0 mis-sorted**, per rule **1 = 5/5/5** and **2 = 5/3/3**; the witness is **five
A-grade apples sent LEFT** (`rule=1 dest=0`, e.g. `apple d=6.3cm grade=A
arm=left ... in_dest=1`) with non-A apples right (`rule=2 dest=1`) - the
overlap resolved by order, exactly as the linter printed. **No rate is
claimed** (8/10 is one branch of the apple-only cell; the mixed pool reads
28-29/40 at the same seeds). **No language model is added**: the DSL is what a
front-end would emit and the **linter is its gate** (overlap, unreachable
destination, unknown attribute/species/grade, uncovered fruit), so an LLM can
propose rules but cannot bypass refusal - the executor stays deterministic and
replayable. Selfcheck **PASS (0 failures, 1 skipped)** with the `P116 sort plan`
leg, `106` OK, `107` PASS (21 checks). Pins: `scenario.py` **`662369aa`** (the
`!=` operator + public `rule_matches`), `262_sort_plan.py` **`d510cb1e`**,
`261_p115_instruction_selftest.py` **`10bd9faa`** (63 checks), `selfcheck.sh`
**`92e65259`**, the three files **`1ad67958` / `5ffbfdb2` / `0d4df6a2`**;
references **`30fb99f8` / `30fb99f8` / `8952c320`** untouched. Evidence
`logs/p116/`.

**P117 (2026-11-06, `logs/p117/`; **nothing adopted**, no `src/` or `configs/` change,
no default moved, no reference re-recorded, no commit): the owner's new
authorisation - *change the scene* - is asked of the record's three unspent scene
candidates with **fixtures** (P104's rig, P110's method), and **the pad face and the
pad friction close while the station pocket promotes.**  `PREREG.md`
**`5caae5d2`**, pinned before any cell.  **The record's contradiction, first**: the
brief's "a concave/V face has never been tested" is **false** - `FRUIT_FINGER_FACE`
(`v`/`h`/`x`/`c` additive, `v2`/`h2`/`x2` recessed, `p` plate) and `FRUIT_FINGER_MU`
exist and the `logs/p3face` phase measured both; matched to its **own** flat control
the recessed `h2` is a **draw** (6/10 vs 6/10) and `v2`/`x2` worse (3, 1), and the
phase never measured the **creep** and ran at the **pre-P41 force** (4.42 N).  So
this is a re-test with a different endpoint, not a first test.  **Fixture 1**
(`fixture.py`, one session, 28 pad pairs on one bench, 84 cells, **182 s**): the
shipped 61 x 84.9 mm plate, 4.90 N/face, k 1e5, the pool's own mesh/mass/friction,
profiles `flat` (control), `arc06`/`arc09` (a semicircular groove of **0.6 r / 0.9 r
of that fruit** - 2 rims/pad at 36.9 / 64.1 deg), `v90` (90 deg V, 45 deg), `cradle90`
(the only face with an **axial** normal, 44.9 deg) and the mu cells; **A1 support**
(uncompensated falls 613 mm; compensated + velocity-pinned reads **0.0000 mm** over
200 ticks - a *free* compensated body drifts 27.25 mm/40 t from a 1-tick apply lag,
`RESULTS` A1), **A2 manipulation** (2 pads at 4.54-4.99 N of the 4.90 cap in all 28
pairs).  **The pad table** (medians of 3; `creep_op` = the total walk from the release
through the 0.75 s `m(g+5.83)` hold, `Fexit` = the sustained break-away): flat
**8.62 / 9.07 / 0.98 / 12.42 mm** and **9.78 / 13.33 / 13.24 / 11.06 N** (pear /
orange / strawberry / lychee), and **no groove reduces the creep on the pear** - it
is **1.58x (arc06) / 1.93x (arc09) / 2.89x (v90) / 1.56x (cradle90)** *worse*, and
every groove is **0.62-0.76x worse on the pear's break-away** (the opposite of the
`n mu N` prediction; the grooves do help the round fruit, 1.22-2.20x, so the effect
is fruit-shape-dependent and the pear's lobes make a groove a wedge *out*); the one
cell that beats flat anywhere is `cradle90` on the orange (**0.72x**) and it is
1.56x worse on the pear, so **A3 fails**; the strawberry is unreadable as a ratio
(its flat base is **0.98 mm**) and the small fruit's grooves are bistable
(`cradle90` strawberry 4.72-16.81 mm).  **A groove is not a drop-in pad**: the pads
must close `r - sqrt(r^2-R^2)` deeper per pad (6.1 mm at `arc06`, 17.1 mm at `arc09`
on the pear) or the face never reaches the fruit - `contact_travel` computes it from
the fixture's own polyline, so every profile is measured at the **same delivered
normal force**, not the same span.  **The mu ladder raises the capacity and not the
creep**: pear `Fexit` 9.78 -> **14.32** (mu3) -> **14.20** (mu4) = **1.45-1.46x**,
orange 13.33 -> **17.96** -> **23.33** = **1.35-1.75x**, while the pear creep goes
8.62 -> 8.38 -> **8.21 mm** (**-2.8 % / -4.8 %**) - so **A6 fires: the creep is not
friction-limited and the friction lane is dead.**  **The phase's correction, and its
most transferable sentence**: P104's "creep at the operating load" is **lateral** -
its own row reads `settle 3.20mm (dx=-3.20 dy=-0.02 dz=+0.02)` and its pads close
along x, so the 3.20 mm is a **seat shift along the jaw axis, not a slide along the
load** - and this fixture reproduces the shape with the load axis `dz = -0.05..+0.28
mm` in **all 28 cells**: **at 1.66 N the shipped pinch does not creep along the load,
it re-seats across it**, so the `cnp` class is not a static-creep deficit and no face
or mu can reach it (which is why P76/P78 bought 1.45-2x of capacity and 2x of creep
*ratio* without converting one `cnp`).  **Fixture 2** (`fixture_station.py`): a
**drop-out pocket under the line**, because the delivered x (0.188-0.397) and the
top-down grip band (<= 0.320 clean, 0.398 fails at 32.8 mm/17.0 deg, P66's 150-cell
sweep) have an **empty intersection** outside the line - a diverter-siding beside the
belt is refuted by that arithmetic, not built.  Build: the shipped belt's own
authoring split into two segments with a **0.148 m** gap, a **belt-like** shutter
filling it (a static plate drags a fruit to a stop in 0.6 mm), and a **100 mm** deep
pocket - the depth is **forced** (`>= shutter 0.020 + the 69.6 mm thickest fruit =
89.6`), and it is also exactly the 40-90 mm the descent loses to the conveyor.  Three
build lessons measured and kept: **`PhysxSurfaceVelocityAPI` is in the collider's
scaled local frame** (an un-divided command carried a 0.726 m segment at 0.087 m/s
and the 0.148 m shutter at 0.018 m/s; `speed / y_length` gives **0.120 = 1.00x**);
**a flush shutter is not optional** (`z = bz` put its top 20 mm low and stopped the
stream dead); and the close predicate must be geometric, not a radius (the occupant
sits 70-90 mm down, *inside* a 0.09 m radius).  **B1's deviation**: the registered
0.05 mm support bar is **below this sim's contact-jitter floor** - the pocket-floor
drift is **0.364 / 0.261 / 0.518 / 0.635 mm at 200/400/800/1200 ticks** (non-monotone
= jitter, not creep) while a fruit **riding the driven belt** deviates 0.018-0.382 mm
from a straight line over the same window, so the pocket is judged against the belt
it sits beside (P107/P112's failure was 2 mm + 4-5 mm *monotone*, 5-8x this floor).
**The station table**: **16/16** in the pocket, **0/16 expelled**, hold
**0.000-0.024 mm**; the closed shutter passes **4/4 at 1.875 s AND 4/4 at 0.833 s**
at **1.00x** the belt; one drop + **3/3 followers** at both cadences with the
occupant holding **0.019 / 0.008 mm**; the shutter's **open window 0.54-0.64 s**
against the 0.833 s cadence (a 0.19-0.29 s margin); the landing x spans
**-58.7..+29.5 mm (88 mm)** and the 0.352 m mouth **does not centre** it, so the
pocket removes the moving handover and the descent's blocked boundary but **not**
P48/P49's delivered-x tail.  **The pocket promotes to a station build** (a scenario
change, not a knob) on two **named, unspent** gates: a **static IK probe at the
100 mm-lower pick pose** (the jaw lands at ~`belt_top`, the pads' distal plane at
`floor + 0.5 mm` - unmeasured), and the shutter's **actuation path** (the fixture
teleports it; only its timing is measured).  **Nothing is adopted**: the shipped
`FRUIT_FINGER_FACE`/`FRUIT_FINGER_MU` stay as they are and no `FRUIT_PAD_PROFILE`
was added (the fixture says neither is the lever).  No-harm: `scripts/accept.sh`
with every knob unset reads **8/10, 9.0 s/attempt, `fingerprint: matches`,
`190: PASS`** (`logs/p117/accept_final.log`), its **421 `[fruit]` lines 421/421
byte-identical** to `logs/p110/accept_noharm.log`, `scripts/selfcheck.sh` **PASS (0
failures, 1 skipped)**, `106` **OK**, `107` **PASS (21 checks)**.  Pins unchanged:
`tasks.py` `9e3e657b`, `rl_env.py` `bf4c56fa`, `bimanual.py` `9b7fc33f`, `fruits.py`
`dcabe16b`, `scene.py` `a0199097`, `cage_hand.py` `ac7c7c0f`; references
**`30fb99f8` / `30fb99f8` / `8952c320`**; ckpt `moe_v13s` `61da390a`.  Evidence
`logs/p117/`.

**P117 amendment + P119 (2026-11-06, owner decision; `logs/p119/`): the pocket is
VOID and the belt 0.15 is a measured negative - under the owner's constraint the
dynamic-only scene lane is closed.** The owner constrained the scene change: the
**dynamic scattered fruit pipeline must be preserved** - **no diverter, stop gate,
guide/limit or pause**. That **withdraws P117's promotion**: the pocket stops the
fruit. The build begun as P118 was **reverted** (`logs/p118/pocket_build.patch`,
`src/` and `configs/` clean; only its reach probe is kept as evidence), and the
shutter/actuator work is void with it. The one scene lever with a measured,
dynamic-compatible prior was the **belt speed** (R3 §4: 0.12 -&gt; 0.15 = 3.63 -&gt;
4.69 window placed/min, **+29 %**, but measured on the **single-arm patch battery
on the pre-P85 tree**); re-tested on the shipped two-line at seed 5 it reads
**9/20 = 45 % against the same-seed control's 16/20 = 80 %**, grip losses **20
against 8**, `no eligible` flat (47 vs 45), interval **16.85 against 10.59 s**
mean (p50 13.55 vs 13.30, p90 33.50 vs 17.40), encoder -0.150 (the command took).
**The mechanism** is the grip class, not the schedule: the same lead is **25 % more
belt travel** at 0.15, so the pads close on a fruit further through the catch-up,
and the descent wait the speed shortens is the slack the *other* arm uses (P99).
**So the scene lane closes by measurement**: the pad face and friction were closed
by P117, the pocket is forbidden, the belt is negative, and the pick/output
station and the supply band were measured (P66's 150-cell sweep, P90's 588-cell
map: 0 pass; P92/P93's band: seed-dependent). The remaining success levers are
**not scene**: P50's release-offset compensation (the delivered-x tail, the 25 %
acquisition class, opt-in per-pool tables) and `docs/END_EFFECTOR_DECISION.md`'s
two hardware sanctions. Evidence `logs/p119/`.

**P120 (2026-11-06, `logs/p120/`; a **measured draw**, nothing adopted, no
`src/`/`configs/` change, the shipped **10 N** stays): the clamp force - the one
hardware lever with a **success** prior (P77's direct line, left 11/21 -&gt; 17/20
at 60 N) - was taken to the shipped scripted two-line and **it does not
replicate**.** The owner opened the hardware ("可以动场景和硬件啊 只是不改那些基本要求"),
so a **four-seed screen** (5/6/101/202, 20 attempts each, same-seed controls)
ran `FRUIT_FINGER_MAXFORCE=60`: **66/80 = 82.5 % against 58/80 = 72.5 %
(+10.0 pts, Fisher p = 0.1846, 3/4 seeds)**, escapes **22 -&gt; 12 legs**, interval
**11.34 -&gt; 10.63 s** (-6.3 %), the `[drive]` readback **60.00 N**, the class **not
deleted** (one landing miss at seed 101: `final=(0.472, +0.803, 1.199)`,
`on_belt=False`, `roll=-15 / skid=-215 mm`). A **replication** at two fresh seeds
with their own controls was **pre-registered** (`logs/p120/PREREG.md` md5
**`b9b7ec5c`**, pinned before those cells finished; stated as a replication, not
a blind test): **303 14/20 against its control's 16/20 (-2), 404 17/20 against
16/20 (+1)** - **31/40 against 32/40, Fisher p = 1.0** - and the pooled **six-seed
cells read 97/120 = 80.8 % against 90/120 = 75.0 %, p = 0.3505**; the escapes stop
moving the right way at 303 (6 against 3). **So the +10 points was one branch
draw** - the same shape P93's four-seed rule exists to catch, and the same shape
the *scoped* 60 N arms already had (P78 `place-left` p = 0.50, P79 `grasp-left`
p = 0.16); P77's direct-line +6 stays that interface's own number. **Recorded
costs**: the seed-101 landing miss (the release block would need its own cell if
60 N were ever revisited) and the **crush guard is not readable here**
(`sep@loss=n/a` on legs that did not lose the payload; the precedent is P76's
60 N strawberry row, `sep@loss - dia = +0.5 mm` at a 36.1 mm span - and this sim
has no bruise model at all). **Owner decision: stay at 10 N**; the remaining
success levers are not force or scene - P50's delivered-x compensation (the 25 %
acquisition class) and the policy/interface lane. Evidence `logs/p120/`.

**P121 (2026-11-06, `logs/p121/`; the direct/policy env's instruction route
ships **default off**, **nothing adopted**, no `configs/` change, no reference
re-recorded): the owner's second half - the DIRECT/POLICY line must decide where
a fruit goes from an instruction - is built and measured, and on the shipped two
lanes the assignment is exact.** P114/P115/P116 had wired the scripted cell
(descriptor, `and` rules, plan/lint, capability map, ledger); `rl_env.__init__`
**refused** `FRUIT_SORT_INSTRUCTION` because the policy interface was
`arm = grade = lane` (`bin_index = 0 if grade == "A" else 1`, fixed before the
fruit is seen) and its action has no destination channel (7 joints + 1 finger).
The build is one pure dispatcher plus the wiring around it: `direct_dispatch`
(unset = the shipped expression byte for byte; armed = the fruit's
`task.sort_destination` and the capability map's `task.arm_for_destination`),
`_begin_pick`'s goal keeps `[xyz, velocity, diameter, bin_index]` (0/1 are the
trained values, 2 is declared OOD), `_run_primitive` sets the thread-local
`tasks.dispatch_destination` (the `place_xy` override `_place_xy_for` reads),
clears it in a `finally`, and calls `sort_ledger_attempt` - P114's `[sort]
attempt` row + per-destination table, `in_dest` from the payload's measured
release position; the reseed retry and the presented-fruit adoption check the
capability **arm**, not the grade lane. A destination beyond the two shipped
lanes raises before the first attempt unless `FRUIT_SORT_THIRD_DEST=1`; an
unreachable destination is refused by P114's map; the handoff presentation still
refuses (no dispatcher). `scripts/263_p121_env_sort_selftest.py` is the offline
leg (31 checks: the dispatch table, OOD gate, capability map incl. the tray, the
goal channel, the place target/cleanup/ledger, the 7+1 action, the manifest
`sort` block, `TASKS_MD5`). **Cells** (3 seeds 77/101/202 x 10 episodes, the
shipped direct config, one session each; the direct loop is not reproducible, so
every count is a branch draw and no rate is claimed): **C unset 19/30** (cnp 6,
fell_off 2, never_held 3), **T1 `today.txt` 18/30** (cnp 9, never_held 3 - its
grade-C `skip` is the *scripted* pure routing, so C is never selected), **T1b
`grade=A => 0; default => 1` 22/30** (the true direct-routing reproduction: A->0
13 attempts, B->1 8, C->1 8), **T2 `size<40 => 1; default => 0` 20/30** (7
grade-B + 4 grade-C decisions on the **left**, 6 B + 2 C on the right - a
destination today's grade rule cannot produce; P3a's grade-A-to-dest-1 witness
was not evaluable on this draw, no A-grade small fruit, recorded), **T3
three_dest 23/30** (A=>2, B=>1, `FRUIT_SORT_THIRD_DEST=1`, the startup solve
reads **6.0 mm**, capability left=[0,2] right=[1], leg `place2`, coverage
dest1=6 dest2=6). **The ledger is the endpoint**: **T1 18/18, T1b 22/22, T2
20/20, T3 22/23** - **0 mis-sorts on the two lanes**, and **1 on dest 2**:
attempt 13's orange was commanded to `(0.38,+0.55)` and released at
`(0.45,+0.53)`, 34 mm from lane 0; the targets are **71 mm apart** and this
line's release scatter on that leg is **40-70 mm** (the other eight dest-2
releases sit at `(0.41-0.42, +0.59-0.60)`). So the third destination is
**reachable and correctly commanded but not separable at 71 mm** - a separation
limit (widen it, give dest 2 its own side/height, or P50's release-offset
compensation), not an env limit. No new failure reason key appears in any cell;
C prints **zero** `[sort]`/`[scenario]` rows (the unset path is untouched).
No-harm: `scripts/accept.sh` reads **8/10 = 80 %, `fingerprint: matches
configs/motion_reference.json`, `190: PASS`** and its **421 `[fruit]` lines are
421/421 byte-identical** to `logs/p110/accept_noharm.log` (and the P114/P117
records) - the scripted path never reads `direct_dispatch`; `selfcheck.sh` PASS
(0 failures, 1 skipped) with the new `263` leg; `106` OK, `107` PASS (21
checks). **Re-baseline: none** - nothing shipped, `configs/motion_reference.json`
= `..._twoline.json` = **`30fb99f8`** and `..._single.json` = **`8952c320`**
stand; the direct cells' counts are not rates (P37/P43/P54). Pins: `tasks.py`
**`78cce1ef`**, `rl_env.py` **`91e0a4ad`**, `scenario.py` `662369aa`,
`assets.py` `165328af`, `fruits.py` `e807216c`, `scene.py` `a0199097`,
`control.py` `9384ff4f`, `conveyor.py` `fb2c58c6`,
`scripts/263_p121_env_sort_selftest.py` **`ce290037`**, `scripts/selfcheck.sh`
**`c071242f`**, `logs/p121/PREREG.md` **`c22e40fc`**,
`logs/p121/p121_report.py` **`826ff730`**; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p121/`.

**P122 (2026-11-06, `logs/p122/`; an offline spec, **nothing adopted**, no
`src/`/`configs/` change): the destination-separation question is answered by
measurement, and the answer corrects the record - **a destination is a physical
output body, not a target coordinate**.** From **133 measured releases**
(P114/P115/P116/P121): the release offset `release - commanded jaw target` is
**systematic** - **+48 mm in x, +-35..37 mm in y**, the payload hanging from the
jaw along the tool axis - plus a **random** part of sd **6-9 mm in x** and
**6-17 mm in y**. Calibrated, an **x separation of 50 mm** is **0/20 000**
(30-40 mm is 1.5 %); **uncalibrated**, 50 mm is **33 %** wrong (the payload lands
2 mm from the downstream neighbour's target, because the systematic nearly equals
the spacing); a **(50, 50) diagonal is the worst shape** - **2.11 %** calibrated,
matching P121's observed **1/23 = 4.3 %** - because the y axis carries the 17 mm
spread. **The physical half is the correction**: `conveyor._build_discharge`
builds **one tray per belt** (`center=(tx, by, ...)`), so the P114/P121
`three_dest` target `(0.38, +0.55)` is on the **same +y belt and the same tray**
as lane 0 - it is an **attribution demo, not a third destination**, and the cell
physically has **two** destinations (the two belts/trays). The binding term for a
real third is the **place reach**, not the spacing: P90's 588-cell map solves
`NAT` only in **x 0.38-0.48, |y| 0.35-0.55** and the slab is `|y| 0.425-0.675`, so
a third belt (~`|y| 0.75`) is outside it and needs a **station solve** (a scene
build, which the owner's "dynamic only" constraint permits - a third belt
downstream stops nothing). The ledger's `nearest` is **uncalibrated** (it compares
the payload to the jaw target), which *is* the three-dest mis-sort; the named
software half is a **calibrated ledger** (report `release - target - mean`, classify
against `target + mean`), which turns P121's 2 % into ~0 %. Evidence `logs/p122/`.

**P173-P190 (2026-11-16/17, `logs/p145/` sections 51-64; the direct policy lane, every
knob opt-in, no default flipped, `configs/` and the references untouched): one learned
diffusion policy on the moving-belt cell with no truth goal, no external trigger and no
scripted primitive handover goes from **6.3 % to 68.8 % placed** (22/32, four seeds, two
of them fresh) against the scripted two-line's 58/80 (72.5 %) - and it is a **hierarchical**
policy, stated as such: the model owns the approach, *when* the contact phase begins, the
finger's close and the bin; two **measured-target servos** own the last centimetres of the
two contact events (`FRUIT_CONTACT_SERVO`: the aim re-derived every tick from the perceived
fruit; `FRUIT_PLACE_SERVO`: lift clear, transit to `task.jaw_target("place{bin}")`, lower,
release), each advancing on measured error rather than a clock. **The order of what each
phase cost, one number per fix**: 2/32 = 6.3 % (shipped 10 N, single lead, direct aim) ->
8/32 = 25.0 % with the **real-jaw clamp 60 N** (`FRUIT_FINGER_MAXFORCE_DIRECT`, a runtime
spec written by the *task*, not the env - the P78/P79 pin holds) -> 8/16 = 50 % with the
**per-arm contact lead** (left 0.10 s, right 0.20 s) -> 25/40 = 62.5 % with the place
transit at 0.15 m/s -> **22/32 = 68.8 % at 0.20 m/s**, a **measured peak** (the same two
seeds read 8/16 at 0.15, **14/16 at 0.20**, 7/16 at 0.25 - both neighbours at half, which
is what an optimum looks like and a branch draw does not). **The right arm's mystery is
solved and it was the servo's lead**: R10-A's map puts the right's usable band at
y in [-0.10, 0.00] and the left's at [0.00, +0.10], so the right meets every fruit later;
a new row resolved the payload's offset **in the tool axis** against the plate's 61 mm
width - right `dlat` **33.5 mm** (past the trailing edge, F = 0.00 N, n = 0) against the
left's **1.8 mm** (57 N, n = 2) - and the lead moves `dlat` monotonically (0.10 -> 33.5,
0.15 -> 19.1, 0.20 -> 6.6), so the all-right arm reads 0/4 -> **10/12** at three seeds and
the *global* lead is a wash (6/16 either way) precisely because the two arms need different
values. **Two harness/data defects the lane found, both project-wide**: (a) **no
demonstration store in the project contains a release** - 0 of **366** stored episodes end
with the finger open, and 0 of them cover the whole attempt, because `_record` is never
sampled inside the release block (the stores end 0.9-1.0 s before the attempt does); one
guarded `_record` fixes it and `datasets/p174_all` (60 episodes) now ends open on every
episode, so **every store recorded before P173c is a no-release store**; (b) the direct
episode's budget was shorter than a pick-and-place (`--horizon 900` = 7.5 s against
12-15 s), so every grasp timed out mid-carry and the timeout note claimed "no grasp" on
episodes that had grasped - the note now says `timeout: horizon reached while carrying`
and the recipe runs 2600 ticks; and (c) the place was **scored at the wrong moment** (a
released payload is carried off and despawned before `_finalize`, so `on_output_belt(final)`
read the spawner's park slot `(+63, 0, -50)`) - `FRUIT_SCORE_ENDPOINT=release` scores the
finger's closed -> open transition from a read the loop already takes. **Everything
measured and NOT adopted, so it is not re-derived**: the action forms `posvel`/`rel`/`dq`/
`jaw`/`tcp`/`hybrid` and the two-model hybrid; GDP selection and K-sample averaging (nulls);
a horizon-1 policy; the phase-dependent view (the place error rose 48.4 -> 68.7 mm); the
900-tick horizon; the demos' right station (y = -0.10 against the env's 0.00: 0/6 either
way); the squeeze scale 0.90/0.92 and the latch window 0.03/0.05 (directions at 1/4); the
45-tick close ramp (a wash, worse for the left); the transit clearance 0.20 m (0/8); the
**pad width 78 mm** (4/8 against the 61 mm box control's 5/8 - the second negative hardware
item after P132's shapes, and it is authored **at build time** so the USD asset is never
edited, with `assets.scene_provenance`'s new `finger = {pad_wide, tip_delta}` naming it);
and the pad *face*/friction family (P117/P129/P132). `docs/DIRECT_POLICY.md` is the lane's
authoritative page (recipe, per-term mechanism and instrument, the read rules - `grasped`
is a *lift* test on the policy path, `final` is a park slot after a despawn,
`jaw_separation()` is the finger link origins which `OpenArmHand` declares to be the pad
faces - and the open items: the right arm at 48 % whose remaining directions are a new pad
**shape** or a **force-controlled finger**, the throughput price of the transit limit
(~2.1-2.4 k ticks/attempt), and a rate certificate beyond n = 32 needing P93's ~364
attempts/arm). Gates on the final tree: `selfcheck.sh` **PASS (0 failures, 1 skipped)**,
`accept.sh` **7/10 = 70 % + `fingerprint: matches` + `190: PASS`**, `106` **OK**, `107`
**PASS (21 checks)**. References `61fb5202` / `61fb5202` / `18b101bf` stand; ckpt
`moe_v13s` `61da390a`, adopted `checkpoints/p177_full`. Evidence `logs/p145/` sections
51-64, `docs/DIRECT_POLICY.md`.

**P207/P208 (2026-11-18, `logs/p207/`; recipe settings only, no default flip): the
direct policy's visible "weird pose" is a single emitted waypoint step of 0.66-2.63 rad
(p95 0.136-0.198), which the arm cannot follow. `FRUIT_POLICY_TARGET_RATE=5.45` (rad/s,
default 0) ramps the emitted 7-joint target at the arm's own `maxJointVelocity`; pooled
over seeds 303/808 (6 episodes each) it is **7/12 placed against the control's 7/12**,
the emitted max **2.633 -> 0.182** / **0.660 -> 0.182 rad**, p95 **0.198 -> 0.181** /
**0.136 -> 0.093**, and it binds only 16-24 % of waypoints. R4 (4.0) smooths harder but
is a speed limit on some branches (6/12); R2 (2.0) binds 76.6 % and is out. The cap
exposed a **state bug**: after a servo the chunk generated before it is stale by the
servo's displacement (1.75 rad), so `FRUIT_REPLAN_ON_SERVO_END=1` drops it and forces one
fresh observation; the residual p95 falls 1.289 -> 0.344 rad but the count is 3/6 against
4/6 on a different branch, so it is **smoothness-only, not in the ship recipe**. **The
instrumentation defect that matters for every earlier clip**: the recipes exported
`FRUIT_JOINT_CLAMP=1`, but the canonical knob is `FRUIT_POLICY_JOINT_CLAMP`; the short
spelling was silently inert, so P202/P204 ran **unclamped**. It is now a direct-only
alias. **P209/P210 closed the chunk-length lane**: executing 2 of the 4 waypoints is
negative on a stochastic policy (2/6 against 4/6, p95 0.182 against 0.101, residual 0.409
against 0.110), and ACT-style temporal ensembling 0.5 rescues it (4/6, residual 0.153)
but does not beat the full chunk (p95 0.122 against 0.101, equal count). The full chunk is
the ship. **P211** closed the size-conditioned selector floor: `FRUIT_SELECT_SMALL_EXTRA`
0.15 reads 5/6 at seed 808 but 3/6 at 303, 0.25 reads 3/6, and a 3.3 cm strawberry at
+0.673 m above the normal floor still fails - the small class is not selection timing. It
is default-off and not adopted. **P212** closed the right-only place transit speed: 0.15
reads 2/6 against 0.20's 2/6 on a B-heavy cell and doubles the place-servo ticks while
`hold=` is already 115-120 mm before the place - the right residual is the lift/carry
grip, not the transit. **P213** found the two-camera blocker is the second **instance
annotator**, not the camera (an RGB+depth wrist leaves the head's mask alive); **P214**
then measured that a mask-free wrist depth window fits the hand (44-62 mm centre error
against the head's 1.7-2.1 mm), so the second view needs a colour segmenter or a learned
detector. **P215** measured 20 N and 60 N both 1/6 on a lychee-only pool, but **P216
corrected the cause**: the phase close's one-sided `dy <= hi` trigger fired with the fruit
**behind** the hand (`[close] xy=442 mm`, `[fire] dy=-442 mm`). With a two-sided
`FRUIT_CLOSE_RAMP_DY_LO=-0.02` the small fruit read **`fired=0` at 0.65-1.18 m behind** -
the policy never approaches them; the 3.7 cm lychee closes at 25 mm and places. The
small-fruit residual is the **policy approach/phase**, not force and not the hand; the
P215 geometry sentence is withdrawn. **P217's control is decisive**: the shipped scripted
dynamic catch places **5/6 lychees at 9.65-10.61 N** on the same hand/pool, against the
learned 1/6 (60 N), 1/6 (20 N) and 0/4 (`fired=0`). The hand is fine; the policy approach
is the bottleneck. **P218/P219** deliver the class fix: `FRUIT_SMALL_HANDOVER=1` routes
<= 4 cm fruit to the scripted `task.run` skill (5/6 lychees; mixed seed 303 **5/6** with
the learned large path 4/4 and the scripted small 1/1, against the learned control's
3/6/4/6; seed 808 4/6, equal, small 2/2). It is a **hybrid**, not a learned small-fruit
policy; the mixed count is a branch, the class is the result. **P220**: the handover is
continuous-ready - a lychee-only 6-pick continuous episode places **5/6** (10,290 ticks,
15.3 s/pick) against the learned continuous 2/6; the mixed continuous seed-303 cell
completes **4/6** (equal to its learned control, no small fruit in the sequence), seed 505
still wedges in the learned large-fruit post-close path. **P222**: the scripted B-heavy
right control places **6/6**; `FRUIT_HANDOVER_SIDE=right` places the right 3/3 at seed 303
but the learned left is 1/3 (loaded slide), so the mixed cell is 3/6 against P219's 5/6 -
the learned left large fruit is the residual, and the side route is a mechanism, not a
mixed success. **P223**: the scripted A-heavy (left) control is **1/6** against the
B-heavy (right) **6/6** - the left is weak in the scripted line too, so it is the left
pad/hand, not a learned-policy deficit; the learned left ~70 % is the best left and the
system cap. New legs `271`-`281`; references `30fb99f8` / `30fb99f8` / `8952c320` stand.

## 2. Two constraints that decide how to measure

**The outcome is quantized; do not compare success rates across configurations.**
The *scripted* line is deterministic per configuration **per mode** - nine runs of
the shipped **v1 (stop-and-wait)** configuration are bit-identical in every
statistic and every per-leg metric, and every other arm in this file that has a
same-configuration pair reproduced bit-identically *within its mode* - but it
lands in one of a small number of discrete *attractors*, and which one depends on
instrumentation as much as on physics. **A configuration can also be multi-modal
run-to-run: P39's `F1` is the first measured arm that is** (five
same-configuration runs on the acceptance scenario land in two bit-identical
modes - 348 filtered `[fruit]` lines / 8-of-9 and 382 / 7-of-10, first-attempt
settle 0.88 vs 0.87 s - so a byte-identity test cannot be run *on* it and its
counts are one draw; AGENTS §2's P39 paragraph). Two configurations in different
attractors are different
scenarios, so a success-rate delta between them measures the attractor. Compare
per-leg motion metrics instead - for a descent, peak speed against the reference plus
the single-tick lurch bound; for a carry, the friction cone; `a_win5` on a descent is
a reported roughness warning, not a budget, because it is a *carrying* number being
applied to a leg that carries nothing - and state which attractor a run is in.

**Since the v7/F1 directive (2026-10-06) the shipped scripted default is the
dynamic never-stop line; the Gate-19 place sweep (2026-10-07) raised the place
profile to 0.35/1.089; the v9/V1 supply change (2026-10-08) replaced the
fixed-spacing feed with the scattered one (the supply paragraph below).**
With `FRUIT_DYNAMIC_PICK` unset the OpenArm scripted line takes the fruit on the
fly (on the pre-v9 fixed supply measured **9/10, 15.8 s/attempt**, the one
failure the A6 kiwi catch-window miss; on the shipped scattered supply measured
**9/10 x5 bit-identical, 15.2 s/attempt**, the one failure a left-arm
place/carry escape, `logs/v1/20_rate_supply_1..5.log`);
`FRUIT_DYNAMIC_PICK=0` restores the indexed *pick* (the P1 primitive - note the
scenario defaults are now the v7 ones: 0.12 m/s belt, the compliant finger
material, and the shared `FRUIT_APPROACH_AMAX` 0.4 -> 0.8 that the indexed
`_approach` reads too, so it is not bit-identical to the P1 logs; its v7-default
acceptance is `logs/fast/16_accept_indexed_v7.log`). The OpenArm policy
handover runs the P1 primitive by default and the **dynamic never-stop catch
with `FRUIT_DYNAMIC_PICK=1`** (v8/P1 directive). At belt 0.12 the dynamic
handover measured **27/45 = 60 %** before the P2b left-handover fix and
**32/45 = 71.1 %** after it (`moe_v12`, left 0/17 -> 6/17, one attempt short of
the scripted ceiling 33/45 = 73.3 %), against the indexed handover's
**16/45 = 36 %** (`logs/p1/`, `logs/p2b/ab012/`). The 0.15 ladder is a wash
(`moe_v12` 31/45 unfine-tuned, fine-tuned `moe_v13` 30/45) and 0.18 was not
run. **The policy's dynamic handover stays opt-in** - with the env unset the
handover keeps the P1 indexed primitive; `scripts/130_policy_demo.sh` enables
it for the visible demo (`FRUIT_DYNAMIC_PICK=0` there restores the indexed
handover). The motion gate derives the descent speed
budget from the shipped profile (per-leg distance; the budget is 1.10x the
*profile peak*, and the fast-profile clean legs achieve ~0.75 of that peak
because the conveyor boundary ends every descent 40-90 mm short, so the
effective slack is ~1.47x, not 1.10x), the
dynamic line's carry cone is *reported* rather than gated (its escapes are the
failure mechanism; `--strict-cone` re-imposes the old rule), and the dynamic
success floor is 0.75 of ten attempts while the indexed floor stays 0.9. Treat a
dynamic rate the way the v2 paragraph below says: one configuration is one
sample of a deterministic branch, so quote the per-leg cone/slip and the
mechanism, not cross-configuration rate deltas.

**The supply is scattered and mixed (v9/V1, 2026-10-08).** `FRUIT_SUPPLY_SCATTER=1`
(shipped) builds a 16-fruit pool with the designed mix (8 A / 5 B / 3 C grades -
the lane rule splits A vs the rest, so 50/30/20 keeps both lanes fed - and two
of each class), a seeded shuffle of the arrival order, gaps sampled in
0.10-0.35 m of belt travel, and a lateral band x = 0.20-0.36 m (not the belt
width: the top-down catch's measured reach band is x = 0.18-0.39 with a hard
cliff at 0.42 - `scripts/174_station_reach.py`,
`logs/v1/61_station_reach_seeded.log`). The feeder keeps an absolute schedule
and releases the backlog at the positions the fruit would have reached when the
drivers' sparse `update` calls leave it behind, so the approach segment is
stocked ("several at once") instead of the old one-fruit-per-attempt
(`queue_peak=0`) line. `FRUIT_SUPPLY_SCATTER=0` restores the fixed line
**line-identical** (`logs/v1/00_accept_scatter_off.log` matches
`logs/g/40_accept_default.log` on every line). The moving catch's selector
refuses candidates inside `_dynamic_select_floor()` (~0.40 m at 0.12 m/s: the
selection-to-handover setup consumes ~1.5 s of belt travel) and takes the
farthest-upstream eligible fruit (a lane takes the nearest usable one); without
that floor the stocked belt hands the catch a 0.10-0.18 m fruit and the rate
collapses to 1/10 (`logs/v1/pre_fix/`). Delivered on the shipped scenario:
single-arm **9/10 x5 bit-identical, 15.2 s/attempt**; the bimanual (opt-in)
stays structurally starved (74 % of its station slots report no eligible fruit)
- the two-line rework (V2) owns that. The reference is per-scenario and has been
re-recorded since: **the v9/V1 file was re-recorded from the identical
`logs/v1/30_accept_supply.log`** (the re-verified
`logs/v1/31_accept_supply_verified.log` read PASS against it at the time; 30's
own gate read FAIL only because that reference did not exist yet), **and since
P32 phase B the shipped `configs/motion_reference.json` is the pear-on 6/10
branch's re-record from `logs/p32/93_accept_pear_on.log`** (md5 25ade92b; the
pre-P32 file is archived at `logs/p32/motion_reference_pre_pear.json`, md5
406745c5, and the pre-v9 one at `logs/v1/motion_reference_pre_supply.json`).
So the v9/V1 run matches **no** current file - a re-run of that scenario needs
its own re-record. The policy path is **OOD** on this
supply (the demos carry one candidate per attempt, and the trigger's
`|dx| <= 0.06` gate (pre-W4; now 0.16) refuses the outer half of the new band); do not quote the
71.1 % direct number as the current-scenario rate - one hybrid canary on the
new supply scored **1/10** (8 grip losses + 1 handoff miss,
`logs/v1/80_accept_policy.log`), an OOD warning the V3 phase owns.

**P32 phase D (2026-10-22): the pear OOD closure.** The hybrid canary's
shipped scenario is the pre-v9 *fixed* supply (`scripts/accept_policy.sh`
defaults `FRUIT_SUPPLY_SCATTER=0`), so it isolates the pear from the v9 supply
change: one sample on this tree reads **5/10 = 50 %**
(`logs/p32/D0_accept_policy_pear.log`; 5 grip losses, 0 grasped-not-placed, the
gate FAILs on the rate only) against the **recorded pre-pear spread 5-8/10**
(floor 0.60). One canary is one sample of a non-bit-identical loop, so it is
recorded as a **smoke**, not a rate. Every checkpoint and rollout store on this
tree is **pre-pear** (the pear changes the per-instance RNG draw count and every
authored mesh); the `meshes.py` md5 pins are in the collector manifest and
`rl_env._MANIFEST_SOURCES`, so a post-pear store is identifiable. The
**owner-accepted OOD note is the closure**: a policy rate measured before P32
is not this tree's rate.

**P33 phase 3 (2026-10-23) added the first post-pear store and checkpoint, and
the direct A/B reads no measured improvement (not adopted).** `datasets/p33_pear`
(180 episodes, left 92 / right 88, 32,670 windows, `index_md5 01626590`, every
shard pinning `meshes.py` `41efc522`) and `checkpoints/p33_pear` (md5
`31751eaa`, fine-tuned from `moe_v13s`) exist, so the sentence above now means
*every other* store/checkpoint. On the direct interface (**W8-A protocol,
`FRUIT_POLICY_TRIGGER_ACQ=1`, a sample**) the new checkpoint reads **8/45 vs
`moe_v13s`'s 16/45 overall; the deficit is the same class (cnp 33 vs 26 of
45)** - pooled p = 0.094, A better in 2/3 seeds at run level (exact permutation
~0.20), the class-matched paired carry 3-1 B (the 2 exact-instance pairs 2-0 -
*inferred*: run + episode + species + diameter + arm, no stored instance id),
29/45 unpairable; no new failure reason, cycle flat. **Store-transfer vs
overwrite is unseparated**, and the attribution gaps keep this to *this
checkpoint on this interface*: the store's right station is `y = -0.10` (the
direct env's is `0.00`) with its own station-specific pre-pose - the right is
the arm where B lost, 14/29 -> 7/24; the store is **successes-only** (52
carried-not-placed + 56 no-grasp attempts discarded - no example of the class
the deficit is in); and the 6-epoch/lr 5e-5 schedule cannot be separated from an
overwrite. The hybrid canary smoke (fixed supply) reads **5/10**, matching the
shipped checkpoint's post-pear P32 D0 count - not broken, not discriminating (a
sample, not a rate). Nothing was adopted (`accept_policy.sh` still defaults to
`moe_v12`). **The two-line has no policy eval harness** (`60_eval_policy.py` /
`accept_policy.sh` drive the single-arm presentation), so `p33_pear` is not
evaluated on the two-line interface - out of scope for the direct OOD closure.

**W4 (Gate 30, 2026-10-10, `logs/w4/`): the dense direct collapse is the
trigger's lateral gate, and the two-line recollection is the wrong anchor for
the single-arm direct interface.** Direct 2x2 + gate cell (N=3x15, seeds
77/101/202): `moe_v13s` dense 0.06 **7/45** (left 0/20, 21/45 no-fire);
`moe_v12` dense 0.06 **14/45**; `moe_v13s` pinned 0.06 **28/45** (left 2/18,
45/45 fires); **`moe_v12` pinned 0.06 33/45 (left 8/18)** - reproducing the
P2b 32/45 / left 6/17 on the current tree, so the single-arm direct path is
unchanged by W1/W2/W3 (their additions are two-line-scoped); `moe_v13s` dense
0.16 **19/45** and the shipped-default re-run **17/45** (1/45 then 0/45
no-fire). The `|dx| <= 0.06` gate was calibrated to the fixed line's ~5 mm
spread and refuses the outer half of the x = 0.20-0.36 band (debug: no-fire
fruit x = 0.20-0.24 vs the ~0.34 station line, |dx| ~ 0.10-0.14), so
**`FRUIT_POLICY_TRIGGER_LATERAL` defaults to 0.16 now** (still inside the
measured reach band x = 0.18-0.39; `=0.06` reproduces the old gate). The
residual left-arm failures are the carry/grip class on every supply. Pinned
canary samples with `moe_v13s`: 7/10 (one novel reason, unattributed), 6/10
PASS (gate of record), 8/10 PASS; the hybrid loop never runs the direct
trigger, so the gate of record does not depend on 0.06 vs 0.16. The
final-tree acceptance `logs/w4/70_accept_w4_tree.log` (9/10, fingerprint
matches) ran with `SKIP_SELFCHECK=1`; the final-tree selfcheck is
`logs/selfcheck.log` (failed=0).

**The v2 dynamic line is weaker than that.** It takes the fruit *on the fly*, so
the tick the tracking window opens on depends on the fruit's continuously evolving
position; two runs of the identical default scored **10/10 and 9/10** with all ten
legs' `samples` and `|v|max` identical (v2 evidence: `logs/370` and the preserved
gate output `logs/accept_v2.out`; `logs/461_posture_transit.log` is a v2-era trace
and `logs/accept.log` is now the v3 run). Read a v2
scripted count as one sample too - five runs, quote the distribution - and note that
the per-leg *fingerprint* now uses `[samples, |v|max]` only, because the old third
field was the jitter-sensitive `a_max` and produced false "different attractor"
verdicts. The
*policy* loop is
weaker still: two runs at the same spawn seed pick the same ten fruits in the same
order but do not agree on the outcomes (10/10 vs 9/10, see the WORKLOG), so a
single policy run is one sample and any published rate needs several. Five runs
span 70-100 % (mean 88 %) and the failures concentrate on the 3.4 cm strawberry -
read the per-episode table the gate prints, not just the rate.

**A conveyor's collider has to belong to a body.** The belt slab was a static
collider, so `PhysxSurfaceVelocityAPI` did not drag the fruit: they travelled at 18 %
of the commanded speed and spun (measured, `logs/170/171`), which is what
`transport_efficiency = 0.40` was hiding. As a kinematic rigid body they ride at
1.01-1.14x (`logs/173`). `scripts/170_transport_probe.py` is the regression check: it
reports the encoder (cleat travel), the fruit/belt speed ratio, the spin ratio and the
stalled ticks. Any change to the belt or the fruit has to be re-measured there.

**The descent's speed excursions are the workspace boundary, not a push.** Every
approach line reports `end=` - where the leg ended against the point it was sent to -
and on both shipped and candidate configurations *every* descent ends **40-90 mm
short** (`logs/160/161`): the pick pose is outside the arm's reachable band (see the
README's "Known limit"), so the arm runs to its boundary and stays there while the
profile carries on, and the post-descent solver finishes the approach. In an isolated
cell with no fruit the achieved/commanded speed ratio is 0.92-0.96 on 16/16 descents
(`logs/155`), and the anomaly trace shows nothing near the arm at the jitter ticks
(nearest fruit 95-134 mm, lowest link 36 mm above the belt, `logs/158`). The stop is a
**collision with the conveyor**: `scripts/47_robot_collision.py` drives the jaw 23 cm
when the belt is removed and 3.8 cm - stopping 8 cm above the belt top, with the finger
geometry inside the belt - when it is there (`logs/166` vs `logs/167`). Gains
(`logs/165`) and integral action on the drive target (`logs/163`, which also doubled
`|v|max`) both leave the shortfall unchanged. Do not re-tune the descent's `|v|max`
budget to admit a configuration - the ratio has no clean gap and the budget cannot tell
a boundary strain from a real push - and do not "fix" it by capping the hand. Fix the
boundary (a pick station clear of the belt, or a descent command that respects it), or
settle what the criterion should mean with the owner (the options are listed in the
WORKLOG entry "the descent is blocked by the conveyor").

**A carry leg's `|v|max` is the hand, not the payload.** Every `[motion] carry` line
reports the kinematic pads' own speed right after `recoveries=`; `in-hand |v|max` is
the payload's *relative* motion and on a rescued leg the two are the same number to
three digits, because the reaction re-seats the pads 25-40 mm in one tick. Clean legs
sit at the commanded 0.176-0.371 m/s. The checker prints this and how many legs exceed
0.45 m/s as a report; do not "fix" it by capping the hand (`FRUIT_HAND_VMAX`) - that
was measured and makes the escape worse (`logs/150`).

**Instrumentation that runs in the control loop changes the result, so it must be
off by default.** Reading the articulation's link world poses every tick shifts
the run by 3-14 s of simulated time and one or two picks; so does adding per-tick
work *inside* `ik_step`, even two small array copies. Fruit-pose reads, camera
reads and pure reporting do not. Hence every diagnostic knob defaults to off,
`ik_step` carries a comment saying so, and traces are used for mechanism rather
than for the numbers quoted in the documents. **P95 measured the boundary on a
second axis** (`logs/p95/RESULTS.md` §0): the *fruit* read set now includes
**linear and angular velocity** plus "every live fruit within 0.15 m", and a
per-tick read of **three prims on each arm** (jaw centre from the two fingers,
TCP, jaw span) also replayed its record **970/970 / 974/974** on the two-line at
two seeds - so what the rule forbids is the *wide* link sweep (7-10 prims across
many links), not any link read at all. The safe rule for a new instrument is still
"fruit reads first, prove it by the `[fruit]`-stream replay, and only then add the
geometry you need, in its own cell".

**The bimanual line is opt-in and shares one station.** `FRUIT_BIARM=1` runs the
pipelined two-arm scheduler (`src/fruit_sorting/bimanual.py`): one arm owns the
pick station from its pre-pose until its carried payload clears a box around it,
the other pre-poses while the first carries and places, and a **main-thread
arbiter** executes one *shared* physics tick per round (so both control loops
stay at 120 Hz in simulated time - one tick per arm per round doubles every
phase and breaks the catch calibration) and grants a single run permit (exactly
one attempt thread executes at a time). Measured on the frozen F2 tree: 9/10 x5
bit-identical (left 4/4, right 5/6), 16.0 s/attempt, 3.38 placed fruit/min
against the then-shipped single-arm 8/10, 18.4 s/attempt, 2.61 placed/min - a
1.30x placed-fruit rate (`logs/biarm/`, WORKLOG "F2"). **G re-derived it on the
Gate-19 place-0.35 default (2026-10-07, `logs/g/`): the bimanual is 9/10 x5
bit-identical, 15.0 s/attempt, 3.59 placed/min (left 3/4, right 6/6; the failure
is a left apple first-lift escape) against the single arm 9/10, 15.8 s/attempt,
3.42 placed/min - 1.05x, because the faster place shortened the single arm's
cycle more than the pipeline's.** Per the pre-registered reading (non-inferior
rate and placed/min clearly higher) the default was **not** flipped:
`FRUIT_BIARM=1` stays opt-in, `FRUIT_BIARM=0` is explicit, and the shipped
default remains the single-arm dynamic line. The new default's clearance trace
reads **6.2 mm** minimum inter-arm link-origin separation with 257/15024 samples
under 30 mm (the F2 45 mm / zero-under-30 figure is pre-Gate-19 timing; no
attempt failed by arm-arm contact) - quote the clearance per configuration.
A bimanual log is a *different scenario*: compare its budgets
and rate, and give it its own fingerprint via `105_motion_regression.py
--write-fingerprint` (preserve the single-arm reference) - do not read a
fingerprint mismatch as a break. Its scheduler invariants are pinned offline by
`scripts/152_biarm_selftest.py` (a selfcheck leg); rates come from
`scripts/153_biarm_rates.sh` (the F2 shape; it skips existing logs) or
`logs/g/run_g_rates.sh` (the Gate-19-default batch, interleaved with the single
arm), the per-attempt table from `scripts/151_biarm_report.py`.

**The v9/V2 two-line scheduler is the explicit opt-in `FRUIT_BIARM_TWOLINE=1`;
`FRUIT_BIARM=1` keeps the shared-station meaning above.** The V2
pre-registration's decision rule (`logs/v2/PREREGISTRATION.md`) kept the
shared-station pipeline because the two-line's placed/min gain missed the 1.25x
replacement bar; the shipped code briefly defaulted it on, and the V3
integration reverted that to 0 (`logs/v3/`, WORKLOG "V3 integration"). Each arm
owns a station on the shared belt: left y = 0.00 (the shipped pick point),
right y = -0.10 (the deepest station the right arm's top-down reach holds <= 6 mm
across the supplied band; the left cannot cross the body), solved from the same
calibrated grasp seed with a station-specific pre-pose configuration so the two
approaches stay on their own sides. Selection is **grade-preferring with an
any-grade fallback** - eligibility is not grade-filtered (that was the V1
starvation), the +Y lane carries the left arm's stream (mostly A) and the -Y
lane the right's (mostly B/C), and the fallback produces measured crossovers
(3/10 on the frozen tree, 5/10 in the V2 sample). Replacing the meaning of
`FRUIT_BIARM=1` would need the owner's sign-off on that grade-biased output
semantics (`logs/v2/PREREGISTRATION.md` "Routing semantics"); the
**2026-10-13 R5 decision kept it opt-in** (flip: **no**; the 1.25x placed/min
bar unchanged - the park-on 3.63/2.17 = 1.67x is a cross-branch reference
only). Measured on the
frozen tree (`logs/v3/10_rate_twoline_1.log` + the bit-identical double-run,
`15_rate_twoline_1b.log`): **6/10 placed, 9.8 s/attempt, 3.66 placed/min
(left 3/5, right 3/5, `gate_open=0.0 s`, zero `indexed:`)** against the
single-arm 9/10, 15.2 s, 3.55 placed/min - **1.55x per attempt but 1.03x
placed/min** (the contact-grip class costs it the placements, so the named path
to a dual-arm default is the grip class, not more supply). **W1 (2026-10-09,
`logs/w1/`) shipped the grip profile on the two-line path: after a failed
probe lift the regrasp re-seats in place (no open phase around a walking
fruit) and the probe is gentler (6 mm/60 ticks, step 0.01); scoped to the
two-line by `_dynamic_profile` because the same values as global defaults
drop the single arm 9/10 -> 6/10.** On the shipped profile: **7/10 x5
bit-identical plus a bit-identical no-env double-run, 9.2 s/attempt, 4.59
placed/min = 1.29x** against the single arm 3.55 (1.25x bar met); the
single-arm default is byte-unchanged and its acceptance fingerprint matches
(`logs/w1/50_accept_single.log`). Per-tick
availability on the free-cadence scattered supply is **left 3.06 % / right
0.00 % None** (the old lane filter on the same line: 38.5/42.4 %); the
delivered per-slot starvation is **4/9 left but all four are the batch-start
belt-prime at t = 13.4-14.9 s, steady-state 0/5 for both arms** (the report
prints both; `scripts/175_twoline_report.py`); per-arm idle between turns
**42 % -> 17 %/18 %**. The W1 branch's clearance (re-measured in W2,
`logs/w2/10_trace_before.log`; that run is bit-identical to the trace-off W1
rate run) reads **min 13.9 mm** (`openarm_left_left_finger` vs
`openarm_right_hand`, t=95.8-96.3 s, left=grip/right=close), **62/10672
samples < 30 mm** - the pre-W1 **6.8 mm** figure (`left_link7` vs
`right_link6`, t=106.4 s) was the old 6/10 branch's 10 s post-attempt freeze,
which the W1 profile removed. The W2 park/handover redesign could **not** meet
the F2 **45 mm / zero-under-30 mm** convention at the rate floor: the moving
catch rides the belt ~0.22 m through its dwell (longer than the reachable
station separation; the left's upstream catch is reach-clean only to +0.10 and
the right's downstream to about -0.13), the best measured clearance state
(38.9 mm, zero<30) landed 6/10 at 9.8 s/attempt, and time-separating the
dwells (a start gap) costs the span ~1:1 (4 s gap -> 11.2 s/attempt). All W2
levers are default-off; the two-line stays opt-in and the shipped W1 branch is
unchanged (`logs/w2/RESULT.md`). No attempt failed by arm-arm contact; the
**2026-10-13 R5 decision accepted the clearance as a documented per-config
report** (the F2 45 mm / zero-under-30 convention is unmet and not re-imposed
as a gate; no arm-arm contact is possible in this build). A
two-line log is a different scenario: compare its budgets and rate, and give it
its own fingerprint.

**W3 (2026-10-10, owner): the grade routing is per-arm and pure, the supply is
a continuous dense sheet, and the two-line collects.** With the **W3 pure
routing** (`FRUIT_GRADE_ROUTING`, default pure on the two-line selector) the
left arm takes **grade A only**, the right **grade B only**, and **grade C is
never selected** - it rides past both stations to the main belt's end
(`despawn_y = -0.70`), is counted `reached_end` and recycled by the feeder;
`FRUIT_GRADE_ROUTING=0` restores the V2 grade-preference-with-fallback. The
single-arm selector passes no `prefer_lane`, so the shipped line is
byte-unchanged (its acceptance still reads 9/10 + fingerprint matches);
**R5-decisions (2026-10-13): this stays two-line-only** - the single arm keeps
selecting C -> lane 1 (byte-unchanged), and the two-line accounts C as
`reached_end`/recycled.
The **dense-sheet supply** (`FRUIT_SUPPLY_WAVE`, default on when
`FRUIT_BIARM_TWOLINE=1`, off otherwise; owner correction 2026-10-10: the first
pass's spaced bursts with 0.70-1.00 m empty gaps are superseded) releases
clusters of `SIZE=5` at 0.10-0.16 m with cluster-boundary gaps of only
0.09-0.12 m, so the clusters run **back-to-back as one continuous sheet - no
empty stretch anywhere**; the same seeded RNG stream drives it. The
two-line scenario defaults the pool mix to balanced **A:B:C 0.375/0.375/0.25**
because pure routing starves the B arm under the shipped 50/30/20. Measured on
the dense sheet (`logs/w3/30_dense_trace.log`, trace on): **8/10, 11.2
s/attempt, 4.27 placed/min, per arm left 4/6 right 4/4, `gate_open=0.0 s`,
zero `indexed:`** (the pick is the never-stop dynamic catch); clearance
**min 2.6 mm / 618 samples <30 mm** - the W1/W2 belt-riding-dwell + idle-hand
classes. **W4 (2026-10-10)**: the trace-off repeat is **bit-identical** to the
trace-on run on all 476 physics `[fruit]` lines (`logs/w4/20_dense_repeat.log`:
8/10, `diverted=1` orange index 10, 11.2 s/attempt, 4.27 placed/min); the
same-scenario single-arm baseline (dense sheet + balanced mix) is **9/10,
15.1 s/attempt, 3.59 placed/min** -> the W1 1.29x does **not** carry to the
dense supply (**1.19x** < the 1.25x bar), so the default-flip recommendation
is **no**. **No arm-arm contact is possible in this build**
(`openarm_flat_deinst.usda` `enabledSelfCollisions=0`) and no attempt has ever
failed by contact. Every measured no-overlap lever trades the rate away (start
gap, station widening, catch lead + park bias, the opt-in capture token
`FRUIT_BIARM_CAPTURE_TOKEN=1`); the full screen table is in `logs/w3/` and the
WORKLOG W3 entry. All W2/W3 levers stay default-off. The **collector** runs
the two-line branch (`40_collect_demos.py` chunks through `run_bimanual`),
records both arms with a per-episode `station_y` label (new,
backwards-compatible index field; the recorder is thread-local and allocates
unique indices itself) and its **stall guard is a per-episode watchdog, never
a belt stop**: `FRUIT_COLLECT_EPISODE_S` (default 600 s) arms
`task.episode_timeout_s`, `_step_sim` raises `AttemptTimeout` on an
over-budget attempt, and the collector **skips and retries** it (partial
recording discarded, fruit recycled, line still running; verified with a 6 s
budget smoke where 6/6 attempts were skipped and `gate_open` stayed 0.0,
`logs/w3/100_timeout_smoke.log`). A hard progress window
(`FRUIT_COLLECT_STALL_S`, 600 s) remains only for a fully blocked C++ call the
soft deadline cannot interrupt (the wedges were a blocking
`RenderingManager.render()` under the bimanual bridge); it exits the shard
with a stack dump and the shard loop advances the seed. The spaced-burst
recollection is archived (`datasets/demos_v12_spaced`, `checkpoints/moe_v13s_spaced`
with its own 8/10 pinned canary); the corrected dense-sheet recollection
finished as **158 episodes in one shard with no wedge** (`datasets/v12d_s02`,
2 h 6 min; merged to `datasets/demos_v12`, arms 80/78) and fine-tuned
`moe_v12` -> `checkpoints/moe_v13s` (6 epochs, loss 0.0261, router 0.981;
anchor `demos_v11` because the v12+v10 stores exceed this 125 GB machine).
The dense checkpoint's **pinned canary is 6/10 PASS** on the gate of record
(`logs/w3/81b_canary_v13s_pinned_dense.log`; a first sample read 7/10 but
carried one novel reason, recorded in the WORKLOG), and its direct eval on the
dense supply is **7/45 = 15.6 %** (single-arm presentation, no-trigger
fruit-off-line; `logs/w3/70_direct_v13s_dense.log`). The corrected tree's
acceptance is **9/10 + fingerprint matches** with `gate_open=0.0 s`
(`logs/w3/62_accept_single_dense_tree.log`). **The W3-supply hybrid canary is
closed by R5-open (2026-10-13): FAIL 1/10 = 10 % (floor 60 %)** on the W3
hand-off command (`moe_v13s`, `FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_WAVE=1`, the
balanced A:B:C 0.375/0.375/0.25 mix, current tree `tasks.py` `0c51cfa5`) - 8
grip losses + 1 non-hybrid scoring row (**row 7, ep7 pear: it lies outside the
failure-reason parser and counts in the rate only - the FAIL is rate-only, no
new reason**; the gate's parsed reasons are all baseline), 17.5 min for the ten
episodes (~1.7 min/episode; the old ~15-20 min/episode does not reproduce on
the dense sheet, and this run does not diagnose that old slowness). The hybrid
interface is inert by construction, so this is
scenario coverage; the checkpoint's direct dense measurement is 7/45 = 15.6 %
(`logs/r5/RESULTS.md` section 1).

**W5 (Gate W5-C, 2026-10-10, `logs/w5/`): the existing-knob mechanism screens
are all negative - H1 is falsified as the cause, not repaired; the watcher is
not built; the policy's left deficit is acquisition, not takeoff.** On the
dense two-line (SEED=5, `ATTEMPTS=10`, Tier A solo, `logs/w5/run_screens.sh`)
five configurations were screened - cfg0 shipped, cfg1
`FRUIT_DYNAMIC_FORCE_SERVO=0`, cfg2 `+FRUIT_DYNAMIC_TAKEOFF_SQUEEZE=0`, cfg3
`FRUIT_DYNAMIC_TAKEOFF_TRACK=0.2`, cfg4 `FRUIT_DYNAMIC_TAKEOFF_LOCK_X=1` -
each a trace-off double-run plus one trace-on run; every config is
bit-identical within itself (cfg1 476, cfg2 474, cfg3 453, cfg4 484 physics
`[fruit]` lines) and cfg0 is a byte-no-harm replay of the W4 record
(`logs/w4/20_dense_repeat.log`, 476 lines). **Every screened configuration
leaves the left class alive** (cfg1 6/10, 3/5+3/5; cfg2 8/10, 3/5+5/5; cfg3
6/10, 2/5+4/5; cfg4 7/10, 3/5+4/5). **H1 (takeoff squeeze-out as the cause)
is not supported**: cfg2's `trace_05` attempt 4 is byte-identical through the
loss with the squeeze and the servo off (first difference carry row 2,
t=59.925), so the named actuators are not its actuator; removing them (cfg2
attempt 7) or pinning x (cfg4) only moves the loss to carry with the same
failed outcome. **H2 is closed as a recovery lever** - the pre-registered
"inert" closure did not obtain (the failure set changes: 4 failures, both
arms) and the "amplifier" reading is equally unsupported (the servo's removal
is inert on the replicated attempt 4, bit-identical, and recovers nothing on
its own branch, 6/10). **TRACK and LOCK_X are negative**: cfg3 destroys the
signature's specificity (the composite fires on a success), and cfg4's own
branch is not a controlled replay (it first diverges inside attempt 1's
probe, row 120, t=18.64) - on it the probe/takeoff stays clean and the loss
moves to carry, consistent with, not proof of, the x-tracking hosting the
escape. **The watcher is not built**: with the sanctioned both-finger force
AND relative-pose key there is no detection/react window (carry losses keep
2-8 N on one finger, cfg1's right pear 32-46 N; where force collapses the
payload is out within 0-3 ticks), a pose-only key fires on successes, and
there is no drop-at-output phenomenon to contain. **H5, scoped to the
W4-pinned `0.06` branch: the policy's left failures differ from the scripted
takeoff squeeze-out** - one direct-path trace (`moe_v13s`, pinned supply,
`FRUIT_POLICY_TRIGGER_LATERAL=0.06`, seed 77; 11 complete + 1 started of 15,
7 success, left 0/3) shows 2/3 traced left failures never make contact
(pre-contact acquisition; one catch-up diverges at the +5.2 cm lateral
trigger edge; ep8's automated `takeoff`/`span_open` label is a no-contact
pad-clamp artifact) and the third is a healthy close/probe lost ~1 s into
carry (the carry-escape class shared with the scripted line); do not quote it
as the current-scenario mechanism outside that branch. The surviving
directions: the **policy acquisition knob first**, then the
**second-seed/size-pinned scripted control**, then the **scripted grip-margin
lever only if the wedge recurs**. No-harm (knobs off, single arm):
`scripts/selfcheck.sh` PASS 0 failures; acceptance **9/10, 15.2 s/attempt,
`diverted=0`**, motion gate PASS and `fingerprint: matches
configs/motion_reference.json`; the acceptance's **385/385** physics
`[fruit]` lines are IDENTICAL to the W4 record. Final tree: `tasks.py
69823dc1` (the whole diff is the default-off `FRUIT_DYNAMIC_TAKEOFF_LOCK_X`
knob + comments) and the metadata-only `rl_env.py` `TASKS_MD5` pin 280d0951
-> 69823dc1.

**W6 (Gates W6-A/B/C, 2026-10-10/11, `logs/w6/`): the throughput metrics are
the inter-placement interval and the lock-on; the supply is the designed 2D
patch sheet; the park-gate lever is the measured win and L1 prefetch is a
measured null.** The tree pin: `tasks.py` **fa9594fb** (the two default-off,
two-line-only knobs `FRUIT_BIARM_PARK_EARLY` and `FRUIT_BIARM_PREFETCH` + the
prefetch-gated handover line), `fruits.py` **a0ea1f54** (`FRUIT_SUPPLY_PATCH=1`
- 0.14-0.22 m along-slices of 1-2 fruit abreast, pair probability 0.6,
0.085-0.12 m separation, shipped x band; default off and every pre-patch supply
stays byte-reproducible), `scripts/186_w6_report.py` **49242875** (the
interval/lock-on/idle/park-split report - the `41`/`45` artifacts are from this
pin), `scripts/188_w6c_levers.sh` **b4308c66** (the lever driver), `rl_env.py`
`TASKS_MD5` metadata-only follow `69823dc1` -> `fa9594fb`. The battery is the
two-line (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) on the patch sheet,
`ATTEMPTS=20`, SEED=5, balanced mix, Tier A solo, plus the same-scenario
single-arm run; the metrics are the per-arm + pooled **inter-placement
interval** (t1 of consecutive placements), the **lock-on** latency (previous
attempt end -> station acquired = selection time), the idle fraction and the
`[cycle]`-mark decomposition (SPEC section 2). **Baseline** (`BASELINE.md`):
two-line **10/20**, batch 2.78 / placement-window **2.70 placed/min**, pooled
interval **22.20 s mean / 45.50 s p90**, idle 26 %/29 %; single arm **13/18**,
2.12/2.17 placed/min -> the same-scenario **window ratio 1.24x** (1.31x by
batch span is the boundary-inclusive variant; do not mix the two
denominators). The delivered 2D-ness is the worker-cadence per-selection read
**7/9 = 77.8 %** of selection instants facing an abreast slice; the free-
cadence design number (93.5 %) must never be quoted as delivered. **W6-C
(`C_RESULTS.md`)**: the **park-gate lever** (`FRUIT_BIARM_PARK_EARLY=1`, opens
the park gate as soon as the other arm's payload clears its station box)
moves the pre-registered pair - pooled interval **22.20 -> 16.53 s** mean,
**45.50 -> 19.90 s** p90, left gate-blocked idle **25.2 -> 0.2 s**, placement
window **2.70 -> 3.63 placed/min** - but it is a **different branch** (12/20
vs 10/20; 7 placed-False + 1 takeoff vs 6 + 4), so quote the timing-only
**+10 %** and the residual **x1.22** factor, not the raw +34 %.
**L1 prefetch (`FRUIT_BIARM_PREFETCH=1`) is a measured null: 0/40
attempt-ends reserved** (0 reservations in each of the two prefetch runs; the
combined pair 1/40, which went stale at slot start - 0.22 m past the right
station, below the +0.30 m floor): the feeder's release cadence runs at the
attempt boundary **after** the park and `state()` reads live positions, so the
attempt-end lane is empty; the consume path was never exercised. L1 stays a
default-off **hook** (re-fire gate: reservations > 0 AND a consumption) and
**R3 measured L2/L3: neither is adopted** - the adaptive lead is bit-identical
(the shipped 1.5 s floor *is* the measured setup), the tight override binds but
its branch is worse, and the interval is arrival-bound (see the R3 paragraph
below and `logs/w8/R3_RESULTS.md`). Clearance is unchanged by both levers: **1.9 mm min, 4.7 %
< 30 mm** (`37`/`38`/`39` JSONLs - the two scripted hover poses; no arm-arm
contact is possible in this build, `enabledSelfCollisions=0`). **No-harm:**
every config pair bit-identical (821/850/843 physics lines), knobs-off
two-line 830/830 vs the W6-B record and single-arm 643/643 vs the W5-C record,
`selfcheck.sh` PASS, acceptance **9/10 + `fingerprint: matches`**
(`logs/w6/60_accept_w6c.log`) - the single-arm default is byte-unchanged. Both
W6-C knobs were default **OFF** and two-line-only; the owner decision then
promoted the park-gate lever (**W7-A below**), while `FRUIT_BIARM_PREFETCH`
stays a default-off hook; the
placed-False and takeoff grip failure classes are W6-E's recollection +
fine-tune territory (`logs/w6/C_RESULTS.md` section 5).

**W7-A (2026-10-12, `logs/w7/`): the park-gate lever is the two-line default
(the W6-D owner decision).** `FRUIT_BIARM_PARK_EARLY` now resolves through
`_dynamic_profile("FRUIT_BIARM_PARK_EARLY", "0", "1")` at both gate sites, so a
two-line session opens the gate at payload-clear with the env unset and an
explicit `=0` restores the pre-W7 rule; `FRUIT_BIARM_PARK_GATE` stays off and
`FRUIT_BIARM_PREFETCH` stays the default-off hook. Pins: `tasks.py`
**bf822c09**, `rl_env.py` `TASKS_MD5` metadata-only follow `fa9594fb ->
bf822c09`. The W6-B patch battery with the default on replays the W6-C park
pair **bit-identically** (861/861 physics lines vs `logs/w6/31` and `32`):
**12/20, 3.64 batch / 3.63 window placed/min, pooled interval 16.53 / 17.30 /
19.90 s, idle 18 %/24 %** - the W6-C numbers and the timing-only **+10 %** /
residual **x1.22** reading stand. The dense W3/W4 wave-sheet re-record is a
**moved branch** (the pair is bit-identical 442/442): **7/10, 9.1 s/attempt,
4.60 placed/min** (left 2/5, right 5/5, `diverted=0`, first divergence at the
left station acquisition t=30.4 vs 31.4) against the pre-flip 8/10, 11.2 s,
4.27/min - a quantized-outcome count, so quote the fingerprint and the per-leg
motion (all 10 descents inside budget; worst `|v|max` 0.111/0.161, lurch
0.023/0.291), not the delta. The **dense 10-attempt** two-line fingerprint is
`configs/motion_reference_twoline.json`; references are per-scenario - the
multi-scenario battery would need its own. **That file was `181c9151`, written
from `logs/w7/10` and matched by `11`, until P39: a pre-pear W7-A record that no
post-P32 tree can reproduce (the first physics difference is `target peach` vs
`target pear` at attempt 0), so P39 archived it to
`logs/p39/motion_reference_twoline_pre_p39.json` and re-recorded the shipped
file from its own same-batch control `logs/p39/p3/twoline_C.log` (**d0326030**,
6/10 at the 0.60 floor, `190` PASS). A W7-A-era two-line log now matches **no**
current file - re-record it from its own control, and never gate a post-P32
two-line log against `181c9151`.** The single-arm
`configs/motion_reference.json`
is byte-untouched by W7-A (`b9e72ca7` is the W7-A-era value; since P32 phase B
the shipped file is **25ade92b**, §1). No-harm: the single-arm patch run is 643/643
identical to the W6-C record (681/681 on the full stream), the acceptance
stream is 385/385 identical to `logs/w6/60_accept_w6c.log`, `accept.sh` reads
**9/10 + `fingerprint: matches`**, `selfcheck.sh` PASS, `172` 52 checks. The
W7-A.1 attribution control - the same dense run with `FRUIT_BIARM_PARK_EARLY=0`
(`logs/w7/15_dense_control_park_off.log`) - replays the W4 record
**bit-for-bit** (476/476 full, 456/456 physics-only; 8/10, 11.2 s/attempt,
`diverted=1`), so the flip is the only cause of the moved branch; the moved
branch's clearance (its trace run is bit-identical to the pair) reads
min **2.59 mm**, 863/10042 = 8.6 % of samples < 30 mm - the W1/W2/W3 carry-past
class, no arm-arm contact possible in this build.
Tooling note: gating a two-line log with `105_motion_regression.py` directly
trips its *single-arm* 0.75 success floor even when the motion budgets pass -
use `scripts/190_twoline_gate.sh`: it pins the two-line scenario (the
`[biarm] two-line scheduler:` banner), the per-scenario reference (default the
dense 10-attempt `configs/motion_reference_twoline.json`) and an explicit
two-line floor (default 0.60 - the 7/10 branch of record; the 20-attempt W6-B
patch battery takes `-m 0.5` and its own reference, and so does the P32 bed
two-line battery with `configs/motion_reference_twoline_bed.json`). 105's own
floor stays the single-arm 0.75, and `--write-fingerprint` now refuses a
motion-budget-failing run (a rate-only failure still writes). The chain's
compares are assertions now (`scripts/189_w7a_chain.sh`, `W7A_OFFLINE=1`
re-asserts them offline).

**W7-B guardrail (the flip's other consumers).** The two-line *collector*
(`40_collect_demos.py` with `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) drives the
same `run_bimanual` session, so a post-W7-A two-line collection gets the
park-gate lever with no env set - the flip silently changes that path too.
`datasets/demos_v12` (shard `v12d_s02`; its manifest pins `tasks.py`
`c8854d6c`) is **pre-flip**, so a post-W7-A two-line recollection is a **new
branch**: the shard manifest's `src/fruit_sorting/tasks.py` md5 pin
(`e98d9836` on the W7-B/W7-C tree; `bf822c09` after W7-A) identifies it, and
since W7-C the manifest's `collection.park_early` field names the lever
(`"auto"` = the flip's on-for-two-line default). Do not mix the two; gate a
re-collected two-line arm with `scripts/190_twoline_gate.sh` (its own reference
if the supply differs) plus the scenario's floor.

**W7-B (2026-10-12, `logs/w7/`): the policy's left deficit is pre-contact
acquisition, not the lateral off-band; the adaptive trigger lead is the
default-off acquisition knob.** The direct-path mechanism run on the W4-pinned
branch (`moe_v13s`, pinned supply, `FRUIT_POLICY_TRIGGER_LATERAL=0.06`, lead
0.9 s, seed 77, `FRUIT_DYNAMIC_TRACE=1`) reads left 0/6 as 3 no-contact + 3
carry escapes (right 9/9), and the W4 pinned population is left 2/18 with 13
`grasped=False` + 3 carried: the no-contact acquisition class is the left's
majority failure. Its measured actuator is the scripted handover's setup
(0.60-0.93 s on successes/carry escapes, **1.36-7.68 s on every traced
no-contact failure**) against the fixed 0.9 s lead - the fruit is 171-2119 mm
downstream of the fingertips when the close starts, past the left's ~4.5 cm
downstream reach, so the 200-tick catch-up expires and the pads clamp each
other at take-off. The off-band reading is refuted on the population (the
close-start offset is a downstream overshoot - the fruit sits `+171...+501 mm`
past the fingertips against `<= 5.7 mm` on the successes/carry escapes; W4's 13
left no-contact split 10 trigger-path + 3 policy-gate, and the trigger-path
`|dx|` no-contact median 0.8 cm vs ok 2.5 cm sits inside the 0.06 gate; every
first-close-tick `vx0` ~ 0, `latch=centring`; no probe/takeoff squeeze-out
signature), so the W5 FRONTIER Lever 1's close-phase x-seek / ramp-start form
is not built. The shipped knob is `FRUIT_POLICY_TRIGGER_ACQ`
(default off, direct-path trigger only): `lead_eff = lead + 0.6 s +
|jaw-station| / 0.20 m/s` (cap 4.5 s) with the reach gate raised with it
(`..._ACQ_SPEED/MARGIN/CAP/REACH` override); `FRUIT_ACQ_DIAG=1` adds one
`[acq]` line per direct attempt (setup stage times, close-start tip-fruit
offset, walk latch, first contact, freeze, joint-limit margin). The A/B
(`scripts/112_rl_ab.sh`, N=3x15, seeds 77/101/202, interleaved, both arms
instrumented, `logs/w7/B_ab/`): **left no-contact 9 -> 1** (of A's 9, 8 are
trigger-path - the knob's reach, 8 -> 1 - and 1 is policy-gate; B has zero gate
attempts; the residual 1 is the measured **trigger-fired** arm flail, both
`move_to` caps 3.33+4.17 s with the joint at its limit), left close-start median
**88.8 -> 1.4 mm**, 10/18 left episodes improve class with zero left
regressions; pooled
**26/45 (58 %) -> 31/45 (69 %)**, left **2/18 -> 8/18**, paired 7 B-only / 2
A-only (both right-arm carry escapes - the branch shift), sign p = 0.0898
(N=3; the P4 p<=0.05 criterion was for 5 runs/arm - the W7-B pre-registered
endpoint is the mechanism readout); strawberry 3/6 -> 5/6; median cycle
1851 -> 1826 ticks (successes +1.8 %); no new failure reason once the note
suffix is normalized out. The knob **stays default off** (W7-B spec, no
shipped-default change). No-harm: selfcheck PASS, acceptance **9/10 + gate
PASS + fingerprint matches**, stream **385/385 identical** to the W7-A
acceptance; pins `tasks.py` **e98d9836**, `rl_env.py` **9318fe3e**,
`policy/trigger.py` **d35fba2c** (the A/B manifests pin all three per run).
W7-C implication: the remaining left deficit is the carry/grip-margin class
(7 -> 9 carried) plus the reach-cliff flail and the policy-gate fire path
(`finger < 0.030 and |jaw-fruit|xy < 0.06`, 4/18 of the W4 left attempts,
which bypasses the trigger); the collector is unaffected (the scripted
primitive never uses the trigger), so the W7-C recollection targets the carry
class. W7-C (above) ran it: at N=3 the fine-tune converted right-arm carry escapes
(carried 32 -> 29, carried-class 3-0 paired; **not confirmed - the W8-A N=5
batch below reads 0 B-only / 2 A-only**) and left the left carry class
untouched (3/16 -> 3/18) - the recollection *did* target the carry class, but
the left residue needs a lever aimed at the scripted branch's own open item,
not another behaviour-cloning pass.

**W7-C (2026-10-12, `logs/w7/`, `logs/w7/C_RESULTS.md`): the patch-sheet
direct interface - the acquisition knob is pinned in-scenario, the
recollection moves the carry class, the rate verdict is underpowered and
`moe_v13p` is not adopted; the two-line collector's manifest and stall-guard
gaps are closed.** The `collection.park_early` field above is operative
(every W7-C shard manifest records `"auto"`); the W7-C.1 additions are the
`supply.patch` block and the guard's stats flush. The scenario is the W6-A 2D
patch sheet
(`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`, balanced A:B:C
0.375/0.375/0.25, lateral 0.16, lead 0.9); the two-line collection
(`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, camera 240,424, post-W7-A branch with
the park-gate lever on) records **173 episodes** into `datasets/demos_v13p`
(nine shard dirs, left 89 / right 84, `106_index_audit` OK; **nine renderer
wedges across the nine shard-runs** with **14 soft-watchdog attempt skips** -
the union is the store, the shard dirs are the provenance unit, and
`gate_open=0.0 s` / zero `indexed:` hold as the collector's *enforced*
never-stop invariant). Fine-tune `moe_v12 -> moe_v13p`
(`checkpoints/moe_v13p/policy_best.pt` md5 **fed54993b4aebdaf2c779bf09a18698e**;
`demos_v13p` rollouts + the single-arm base `demos_v11`, the `moe_v13s` recipe;
both checkpoints sit on the single-arm lineage - v13s also used the `demos_v11`
base). **Pins.** The W7-C direct evaluation runs with
`FRUIT_POLICY_TRIGGER_ACQ=1` in-scenario because the A/B on this supply
measures the knob's mechanism endpoint (left no-contact 15 -> 0, close-start
median 120.1 -> 2.5 mm) while the recollection targets the carry class; the
knob stays default **off** and the shipped hybrid canary never runs the trigger
(the canary of record reads **8/10 PASS** and matches the v13s sample). The
class split (C_ab): with the knob on **32 of 45 attempts (32 of 33 failures)
are carried-not-placed** - the single failure mode of this interface - and the
per-arm n shifts with the fire timing, so compare per-arm *classes*, not
per-arm rates (the direct env sets the arm from the fruit grade). **The
evaluation:** paired direct A/B `moe_v13s` vs `moe_v13p` (both ACQ=1, N=3x15,
interleaved): 10/45 (22 %) -> 13/45 (29 %), **carried-class 3 B-only / 0
A-only** (the overall rate pairing is 1 B-only / 2 A-only), carried 32 -> 29,
right ok 7/29 -> 10/27, left unchanged 3/16 -> 3/18, sign **p = 0.125** at
N=3; the one new reason (`timeout: no grasp within 1500 ticks`, one episode) is
a no-fire/horizon timeout, *not* the policy-gate class (B has zero gate fires).
**Verdict: no measured improvement by the P4 criteria - no adoption**
(`accept_policy.sh` keeps the shipped default `moe_v12`). **W8-A superseded
the N=3 read with the confirmatory N=5 batch** (`logs/w8/A_RESULTS.md`):
pooled **21/75 (28 %) vs 22/75 (29 %)**, sign **p = 1.0000**, carried-class
pairing **0 B-only / 2 A-only** (carried 49 -> 47, right ok flat
20/52 -> 19/49) - the 3-0 pairing and the 32 -> 29 movement did **not**
confirm, so only the negative is published. The two-line rollout-store ->
direct-interface transfer stays an open W4 risk the W7-C A/B tested only
weakly. **Collector (W7-C.1, `scripts/40_collect_demos.py`):** the shard
manifest now records the patch sheet (`supply.patch` + slice/pair/sep), and
`_stall_dump` flushes a `[collect] stats:` line before its `os._exit(3)`, so a
wedged shard carries the gate-open invariant instead of implying it; existing
shard manifests are not rewritten (their md5 pins are the provenance record).
Tooling: `logs/w7/C_class_split.py` / `C_acq_forces.py` are the read-only
re-derivations; `logs/w7/C_acq_forces.py` is what withdrew the first pass's
Fmax force split (close-phase `Fmax` does not separate the classes - the
grip-margin reading is a hypothesis, not a measured force split).

**W8-B (2026-10-13, branch `w8-carry`, `logs/w8/`): the carry-window metric
exists and separates; the one bounded guard lever is measured and NOT adopted;
the legacy `[motion] carry slip_max` must not be quoted for the OpenArm hand.**
The metric is the frame-free `clean_slip` (payload displacement in the leg's own
frame, reference = the leg's first tick): over four trace corpora (55 attempts)
the clean leg-outs read **0.02-1.43 mm** (median 0.04, n=33) and the carry
escapes **17.9-957 mm** (median 278, n=31) with **no overlap**; 25 never-held
legs (reach-cliff class) are excluded. It is live in the default-off
`FRUIT_CARRY_DIAG=1` `[carry]` line and offline in `logs/w8/B_metric.py`
(agreement <= 0.06 mm on 29/29 legs; the live onset bookkeeping is
contact-agnostic and includes no-contact legs - onset rows 1-3, `F=0` - unlike
the offline classes). The mechanism is a **loaded slide** (force at its carry
level at onset, median 4.90 N; single-sided contact; jaws pried to their
98-99 mm limit in 17/31 escapes; contact loss 2-132 ticks after the 2 mm
crossing, median 25). The lever `FRUIT_CARRY_GUARD` stays **default off**
(direct-scoped: `_carry_guard_active` needs `direct_capture`, so a scripted call
never reaches it; `FRUIT_CARRY_GUARD_LEGS` is an exact per-leg-name match, so a
place scope reads `place0,place1`): it moved the paired carried class 5-1 and
carried-not-placed 50 -> 42, but sign p = 0.1094 and +5.4 % cycle -> **not
adopted**; the R1 lever slot is closed with the named residuals
(`logs/w8/B_RESULTS.md`). No-harm: acceptance **9/10 + motion gate PASS +
`fingerprint: matches`**, its 385/385 `[fruit]` lines byte-identical to
`logs/w7/50_accept_w7a.log`; the two-line half is gated by
`scripts/190_twoline_gate.sh` (PASS on the frozen-tree re-record
`logs/w8/70_w8b1_twoline.log`, whose 442/442 `[fruit]` lines are identical to
the W7-A dense record). **Do not quote the
legacy `slip_max` for the OpenArm hand**: it is frame-contaminated
(25.6-104.7 mm of ghost slip on the acceptance's placed carries) - use
`clean_slip`; `README.md`'s grip-quality paragraph carries the same correction.

**R2 (2026-10-13, branch `w8-residuals`, `logs/w8/R2_RESULTS.md`): the C note,
the cross-lane label is real, and the flail class has three terms.** The
two-line patch store's zero-C is by construction (W3 pure routing never
selects C); the direct interface presents C and measures it as its best grade
(W8-A 43 %, W8-B 46 %; confounded with the arm - A->left, B/C->right), and the
C windows train from the single-arm base `demos_v11` (C 21/50). A top-up, if a
C-specific need ever appears, is a single-arm collection
(`FRUIT_SUPPLY_GRADES=C:1`), never a two-line store. The patch canary's
`cross-lane station fruit ... placed on lane M` note is **a real event emitted
by the primitive** when the station-presented fruit (patch pair / queue)
belongs to the other lane: the arm takes it onto its own lane and records the
sort error (`canary_patch` 6/10 - the W7-C text's 5/10 is corrected - and the
reproduction 4/10; not failure-specific). The direct path's **flail** class
(18/390 `[acq]` attempts, close starting 0.17-0.92 m downstream, joint at its
limit) decomposes into a **premove/configuration term** (the policy's incoming
pose; removed by the default-off `FRUIT_DIRECT_RESEED=1` re-seed: capped
premoves 9/15 -> 0/15, median error 43 -> 21 mm, flails 10/15 -> 13/30 pooled),
a **hover/reach-edge term** (the 8 mm hover tolerance is unattainable at
x >~ 0.39; the default-off `FRUIT_POLICY_TRIGGER_X_MAX=0.39` refuses those
would-fire ticks - 7 recorded refusals, 0 refusals/0 flails on the shipped band
- but sub-cap fires still flail and the **policy-gate path bypasses the
trigger**: 4 of 7 refusals were attempted anyway, WS-4.6), and a **catch-up
stall term** (fast setup, 28-181 mm residuals; the R2.1 re-derivation in
`logs/w8/R2_flail_analysis.txt` / `R2_probe_report.txt`). Neither knob is adopted; both
are default off and direct-path-only. Do not read a catch-up timeout as a
fire-time miss: the fire-time dx spans -4.1..+8.3 cm across the class.

**R3 (2026-10-13, branch `w8-speed`, `logs/w8/R3_RESULTS.md`): no WS-3 speed
lever is adopted, and the reason is measured, not assumed - the two-line patch
interval is arrival-bound (revised by the P1/P2 paragraph below: the cadence is
flat across the density ladder, so the wait is not where the time goes).** The L2 plumbing is delivered
(`_dynamic_select_floor` takes a `lead_override_s` that *replaces* the shipped
1.5 s setup, so `FRUIT_BIARM_SELECT_LEAD_S` is no longer inert on the two-line
path (the shared-station worker keeps it max'd under the 1.5 s floor), the
adaptive form (`FRUIT_BIARM_SELECT_LEAD_ADAPT=1`, a per-arm EWMA of the measured
selection -> wait-loop-entry setup, clamped 0.9/1.5 s) is **bit-identical to
the control (821/821 physics lines)** because the shipped floor *is* the
measured setup (**left 1.467 s, right 1.516 s**) and **0/20 selections are
floor-bound** (38-316 mm of slack). The explicit tight probe
(`FRUIT_BIARM_SELECT_LEAD_S=1.0`, floor 0.339 m) **binds** (1/10 per arm) and
moves the branch (first divergence: the left slot-10 peach-vs-lychee) with
**zero new failure reasons** - the v9 under-lead miss does not appear - but the
pooled interval/rate on that branch are worse (8/20, window 2.59 vs 3.63
placed/min, pooled 23.16 vs 16.53 s; the shared placed-False class 11 vs 7).
The L3 hot-arm residency (`FRUIT_BIARM_HOT_ARM=1`: the park decision deferred
to after the attempt-boundary feed, a station-side hold when a target is
imminent and the other arm grips nothing, the next attempt's pre-pose blend
skipped behind a 0.08 rad guard; the hover move stays - it is the calibrated
descent entry) fires **4/18 non-final turns** (starvation 7, clearance 7, 2
survive to the next attempt, 1 of 4 jams at 1.55 rad and recovers through the
park) and does **not** move the interval: the hold's measured-convergence blend
(140+80 ticks) costs the same order as the park return (2.4/2.9 s), the pooled
attempt span is identical (15.08 s), the window rate is 3.41 vs 3.63, the
idle/starvation rise (27 %/27 %, starved slots 51/37 vs 19/22), and the
clearance convention moves per config (min **1.9 -> 4.7 mm**, < 30 mm
**4.7 -> 5.6 %**, the W2/W3 carry-past class; no contact possible). L4
(place/return re-timing) is **not run** - the control's return block is 0.59/
0.64 s per attempt (~4 %), not dominant, and W1/W2's place/carry negatives
stand. The belt-speed screen (0.12/0.15/0.18 m/s) is in R3 section 4. All R3
knobs default off and two-line-scoped; the single-arm acceptance is
byte-unchanged (385/385 identical to `logs/w8/R2_accept.log`), selfcheck PASS.
Pins: `tasks.py` `0c51cfa5`, `rl_env.py` `TASKS_MD5` follow, `176` selftest
extended with the plumbing pins.

**R5-decisions (2026-10-13, branch `r5-open`; `.slim/deepwork/sorting-pipeline-v3.md`
"R5-DECISIONS"): the owner closed the register per the recommendation - no
shipped default changes.** (1) The two-line flip stays **no**
(`FRUIT_BIARM_TWOLINE=1` opt-in; the 1.25x placed/min bar unchanged; the
park-on 3.63/2.17 = 1.67x is a cross-branch reference only). (2) The clearance
stays a **per-config report** (the F2 45 mm / zero-under-30 convention is unmet
and not re-imposed as a gate; no arm-arm contact is possible in this build).
(3) The pure C routing stays **two-line-only** (the single arm keeps C ->
lane 1). (4) `FRUIT_POLICY_TRIGGER_ACQ` is **not shipped** - it stays default
off, a measurement interface (the ACQ=0 mirror is mechanism-only). (5) The
**hybrid pinned canary stays the interface of record**; the direct loop stays
the mechanism-research interface, and the WS-4.2 N=5 protocol governs any
direct claim. The non-blocked R5 items (the W3-supply canary FAIL 1/10, the
patch scenario's own reference) are in `logs/r5/RESULTS.md`.

**R6-B (2026-10-13/14, branch `r6-carry`, `logs/r6/B_RESULTS.md` + WORKLOG
"R6-B"/"R6-B.1"): the WS-4.7 combination screen and the carry-class lever are
both measured and NOT adopted; the direct grip is a drive-saturated pinch.**
On the forced edge band (x = 0.36-0.42, N = 1x15 per config) the combination
(`FRUIT_DIRECT_RESEED=1` + `FRUIT_POLICY_TRIGGER_X_MAX=0.39`) **roughly
halves** the no-lever control's flails (5/15 vs 10/15; the reseed-only P3/P4
controls pool 13/30; C1's 4/15 sits inside the same spread) but does not zero
the class: the three premove caps are exactly the three attempted-anyway
refusals (premove targets x = 0.4086/0.4201/0.4212, err 34-41 mm, while the
fired targets 0.329-0.386 converge in 12-21 mm) - the cap is the WS-4.6
policy-gate bypass's mechanism - and every attempted-anyway refusal flails
(3/3). The two new hover knobs (`FRUIT_DIRECT_HOVER_TOL`/`_STEPS`, default
off, direct-path only) are measured and rejected: the tolerance is inert at
the edge (the hand cannot hold 20 mm either; 4/15) and the step bound trades
the term (6/15: 5 fast-stall + 1 premove-cap; the fast-stall residuals
23-331 mm). The direct carry mechanism is a **drive-saturated pinch**: the
`grasp_lift` command sits a median 11.9 mm inside the payload's measured span
at the leg start (n = 46 contact legs) while the contact force reads 4.1-4.5 N,
and the new default-off `FRUIT_CARRY_RELIEF` cap releases the command to
0.5 mm of allowed interference with the force **unchanged** (Fmin 4.15-4.47 N)
- the squeeze-side family is closed by measurement. The retuned guard
(`HOLD_TICKS=8`, `RESEAT_MAX=0.060`, `DERATE=0.8`; trigger and the 72-tick
budget fixed), N = 5 paired x 15 episodes: pooled **24/75 vs 25/75**, carried
46 -> 44, paired same-fruit **3 B-only / 1 A-only** (sign p = 0.3125), cycle
+4.5 %, no new reasons - **not adopted**; the W8-B 5-1 directional read
(carried 50 -> 42) did not reproduce (46 -> 44, 3-1) and the 100-400 mm band
converts 0/37. No-harm: acceptance **9/10 + motion gate PASS +
`fingerprint: matches`** and 385/385 `[fruit]` identical; the two-line dense
re-record 442/442 identical + `190` PASS. Pins: batch tree `tasks.py`
`1d6e9662` (final `b2c79938`, comment-only - unverifiable now), `rl_env.py`
`5940a7c8`, checkpoint `moe_v13s` `61da390a`.

**R8-A (2026-10-14, branch `r8-dscreen`, `logs/r8/A_RESULTS.md` + WORKLOG
"R8-A"/"R8-A.1"): the pre-registered D screen - the lower grip plane, the
cradle/scoop and the raised station all FAIL; the bounded grip-geometry lever
space is measured closed around the carry class.** The screen (Tier A solo;
the candidates and the conversion criterion fixed in `logs/r7/FRONTIER_R7.md`
section 4 before any asset was touched) ran the patch battery x2 per config
(four double-run pairs, all IDENTICAL) plus the direct probe (patch sheet,
ACQ=1, seed 77, 15 episodes, checkpoint `moe_v13s` `61da390a`). **D2a**
(`FRUIT_GRIP_PLANE_DROP=0.008`, default-off): the escape signature persists
and the lift-leg population moves up into the >400 mm band (11 -> 2 vs
2 -> 10), flails 1 -> 14, battery 5/20 x2 with a new station-close note, and
one descent leaves the speed budget (`|v|max` 0.172 vs 0.161) - and the reach
reading is the **leading hypothesis, not isolated**: the drop moves the
*commanded* catch target (`catch_target` uses `_pad_standoff`,
`tasks.py:6112-6114`) but not the catch-up break test (`desired_tip` uses
`_dynamic_pad_lift`, `tasks.py:6094`), so the -8 mm caps are expected even
with a reachable target (the missing control: the drop + a drop-adjusted
break test + a -2 mm magnitude; the -4 mm sample also fails). **D2b**
(`FRUIT_FINGER_SCOOP=1`): the ledges **bat the payload** (the P3/D
additive-face class the pre-registration warned about; 7 `grasp_lift` rows
with onset in the first 1-2 ticks and `sep@onset` <= 22 mm) - no-contact
2 -> 9, battery 6/20 x2 (the 12 gripper-loss notes are the control's class).
**D3** (`FRUIT_NEST=0.02 FRUIT_NEST_WIDTH=0.05`, the bounded proxy): the
platform's 100 mm x-span is narrower than the supplied band, so its side
faces obstruct the moving supply - battery 1/20 x2, `recirculated` 0 -> 13,
a new "fruit never settled at the pick point" note; the full D3 form (station
+ self-centring feeder + boundary-respecting descent) stays the named
scenario redesign, out of scope for the next phase. **No shipped default
changed**: acceptance **9/10 + motion gate PASS + `fingerprint: matches`**,
385/385 `[fruit]` identical to `logs/r7/A_accept.log`, and the screen's own
control battery replays the W7-A record **861/861 bit-identical**; both new
levers are default-off env knobs. Pins: `tasks.py` `27d0fabd`, `scene.py`
`ab85dca2`, `rl_env.py` `72d55574` (metadata-only `TASKS_MD5` follow),
`trigger.py` `d7ec85fc`, `runtime.py` `ffb76bfd`, checkpoint `moe_v13s`
`61da390a`. **No R8-B is triggered** (all three forms fail); the **fallback
is direction B, the RL/DAgger lane, pre-registered as the next phase**
(ACQ=1 + R7-A pinned; the N=5 paired carried-class endpoint with the cycle
non-inferiority margin and the kill criteria; the no-harm + adoption gates;
D3-proper out of scope - `.slim/deepwork/sorting-pipeline-v3.md` "R9 PLAN",
`logs/r8/A_RESULTS.md` section 7).

**R9 (2026-10-14, branch `r9-rl`, `logs/r9/RESULTS.md` + WORKLOG "R9"): the
bounded RL/DAgger lane (direction B) was executed as the pre-registered
AWR-clipped RWR iteration 2 and closes negative and published - the carry class
does not convert, and the lane degrades the one channel it can touch.** The
lane is not the two behaviour-cloning nulls (W7-C/W8-A are off-policy
`weight_mode=ones` on scripted recollection stores; this one weights the
policy's **own** fresh direct-interface rollouts by the terminal outcome) and
it is the RWR-2 fresh-rollout design: `w = clip(exp(4*(R-Vbar)), 0.05, 4)`,
`Vbar = 0.3103`, fine-tuning `moe_v13s` (`61da390a`) on 56 fresh on-policy
rollouts (`datasets/rl_rollouts/r9_awr`, 18 successes; the pre-registration's
`demos_v12` rollout-store pin is the success-only *scripted* store and would
have been a behaviour-cloning replay). The N=5 interleaved endpoint
(`logs/r9/A_direct_ab/`): **A `moe_v13s` 25/75 = 33 % vs B `rl_awr1` 18/75 =
24 %**; the primary **paired carried-class conversion 5 B-only / 4 A-only,
p = 0.500** (6-0 is the p <= 0.05 edge at N=5); strawberry **1/9 vs 6/10**;
**no new failure reasons**; cycle **+1.5 %** -> primary FAIL, secondary FAIL,
no adoption and no shipped default change. The mechanism: the `[carry]` window
is **branch-invariant** (74/74 `grasp_lift` legs per arm; onset-row median
94/94; `force@onset` 4.93/5.38 N; onset -> loss 29/26 ticks; single-sided
contact) - the scripted primitive owns the pre-onset facet - while the
**handover state degraded** (B **6 reach-cliff flails** vs A's 1, five of them
with the premove `move_to` at its 3.33 s cap; the fidelity readout
`0.087 -> 0.174 rad` away from its own rollouts predicts exactly this), so the
post-training moved the wrong channel. No-harm: acceptance **9/10 + motion gate
PASS + `fingerprint: matches`** with 385/385 `[fruit]` identical; two-line
dense 442/442 identical + `190` PASS; selfcheck PASS; env-only (no `src/`
change, no shipped default). Pins: `tasks.py` `27d0fabd`, `rl_env.py`
`72d55574`, `trigger.py` `d7ec85fc`, `runtime.py` `ffb76bfd`, candidate
`checkpoints/rl_awr1/policy_best.pt` `a1766ecd`, base store `demos_v11`
`922ca995`. The named next items are the **primitive-side pre-onset load
path** (a `tasks.py` item with its own pre-registration), **D3-proper**
(owner-gated), and the **WS-7.1 sim-to-real prep**; another post-training pass
on this interface re-measures the null.

**R10-A (2026-10-15, branch `r10-reach`, `logs/r10/A_RESULTS.md` +
`PREREGISTRATION.md` + WORKLOG "R10-A"): the reach-anywhere dynamic catch
delivers the coverage and the per-attempt interval, but the success and
no-new-class criteria fail and `FRUIT_REACH_ANYWHERE` stays default off.** The
owner correction (binding) removed the station-fixed limitation: the moving
catch must meet fruit at any reachable (x, y). The measured reachable-intercept
map (`scripts/183_reach_intercept.py`, extends `174` to the y dimension; raw
rows `logs/r10/reach_intercept_{left,right}.json`): clean grip bands left
x=0.20 `-0.10..+0.15`, x=0.28 `-0.05..+0.10`, x=0.36 `0.00..+0.10`; right
x=0.20 `-0.10..+0.10`, x=0.28 `-0.10..+0.05`, x=0.36 `-0.10..0.00` (6 mm
tolerance; the cliffs are sharp; the ranges nest, so a fruit between measured
columns takes the next column's band - the first read of +0.20 at the left
x=0.28 cell came off the 6.5 mm row and was corrected in place by the A1
pass). The hover move costs 0.57-0.78 s (68-94
ticks) at every reachable offset (the R2 cap class outside). The design
(`tasks.py` `7e20255c`): `_reach_predict` = the interception point (a bounded
fixed point, `y_f + vy*(t_setup(y) + t_desc + margin)`, clipped into the arm's
x-columned band); `_reach_prepare_aim` caches it at the pre-pose end and
`_dynamic_aim` returns it (the hover move, both wait loops and `_approach`
are unchanged); `_reach_anywhere_select` replaces the station floor with the
band-relative floor and takes the minimum fruit travel to the clipped
intercept (ties to the nearest); the shipped station-fixed rule is the
fallback (it never fired - a strict subset on the measured bands). Scoped to
the scripted OpenArm moving-catch line; the two-line and direct/policy paths
keep their rules (a `FRUIT_BIARM=1` shared-station session runs the same
scripted catch and would inherit the knob - opt-in; only the two-line
scheduler is excluded, its stations are its clearance mechanism); off =
byte-unchanged. Measured (W6-A patch sheet, single
arm, 20 attempts, seed 5; `logs/r10/30_control.log` vs `31_reach.log`):
coverage **73 vs 45 candidate-fruit across the same 20 selection instants
(+62 %)**, 20/20 vs 19/20 instants with a catchable candidate, 20 vs 18
attempts; per-attempt span **15.24 -> 13.98 s (-8 %;** the wait segment 3.06 ->
1.68 s) but the inter-placement interval 27.62 -> 45.14 s and throughput
2.17 -> 1.33 placed/min; success **13/18 = 72 % -> 8/20 = 40 %**; the carry
class **"fruit did not follow the gripper" 0/18 -> 5/20** (3 carry escapes
after contact + 2 timing chases); one descent over
budget (0.165 vs 0.162, the attempt-15 fallback leg; the attempt-19 chase
leg itself is inside budget; the re-seat count is 13 vs 0). The mechanism:
intercepts p50 +0.011 m
(early), the descent-end error p50 +3.4 mm, catch-up p50 14 ticks, and **the
descent wait is 0 ticks in 16/20 treatment attempts vs 59-89 in the control**
- the just-in-time handover removes the shipped line's hover settling (the
leading hypothesis; its named test is the default-off `FRUIT_REACH_HOVER_SETTLE`
A/B) and the
grip phase grows 1.60 -> 2.52 s. Named residuals: the hover settling (its
measured test is `logs/r10/A1_RESULTS.md`), the band cap + the capped-hover
fallback (the old +0.20 cap, the 661 mm chase; the R2 knobs are
direct/trigger-scoped and do not apply to the scripted catch), the setup
model's missing x-term (its own pre-registration), and setup-time variance
breaking the just-in-time feasibility (one fallback chase). No-harm: the control patch run
is **643/643 physics lines identical** to the W6-B single-arm record; the
acceptance **9/10 + motion gate PASS + `fingerprint: matches`** with 365/365
physics lines identical to the R9 acceptance; the two-line dense re-record
**442/442 identical** to the W7-A record + `190` PASS; both double-runs
bit-identical up to a wedge (run 32 through 288 lines, run 33 through 297 -
each then wedged, a known renderer freeze); selfcheck PASS. Pins: `tasks.py`
`7e20255cd32e4d438cfa9ffc5f4dc5e7`, `rl_env.py` `TASKS_MD5` metadata-only
follow; branch `r10-reach` from `7f9eb34`.

**R10-A.1 (2026-10-15, branch `r10-reach`, `logs/r10/A1_RESULTS.md`): the
gate-ordered fixes land, the corrected band removes the band-cap chase, and
the hover-settle A/B reads its pre-registered primary positive with the knob
still default-off.** The fixes: the left x=0.28 band cell corrects to
`-0.05..+0.10` (the +0.15/+0.20 rows are 8.2/6.5 mm, outside the 6 mm
tolerance; also the "at least as narrow" wording and the left `else` inset
cell `[+0.02,+0.08]`), the over-budget descent is the **attempt-15 fallback**
(M4), the coverage recounts to **73 / +62 %** (`43_r10_report.txt`; the
31-vs-32 288-line identity is `40_compare_treatment.txt`), and the mechanism
wording carries the 3-carry-escape + 2-timing-chase split, the 13-vs-0
re-seat and 3.48x/1.22x cone contrasts, the R2-knobs-are-direct-scoped
correction and the `FRUIT_BIARM=1` shared-station scope note. The
corrected-band re-measure (34; the same battery, behaviorally identical to
R10-A through attempt 15 - first divergence attempt 16's handover, aim +0.141
-> +0.08): **9/20, carry 4, re-seats 10, coverage 74 vs 46 (+61 %), span
13.55 s** - the band-cap chase is gone, the attempt-15 fallback leg the only
motion over-budget. The **hover-settle A/B** (35;
`FRUIT_REACH_HOVER_SETTLE=60`, priced into `t_setup` as
`vy*S/(1-vy/v_hover)`): **carry 4 -> 2 and re-seats 10 -> 7 (both
pre-registered endpoints fall), success 13/20 >= 9-1, span 13.55 s (identical;
the park priced), window 2.18 vs 1.43 placed/min (the control's 2.17), the
park actuated in 19/20 (60-78 ticks; A read 0 in 14/20)**, the motion gate
failing on the rate only (all descents inside; worst cone 1.84x vs A's
reported 6.02x), with the **branch caveat** (the settle moves `t_c`, so the
runs diverge from attempt 0 - quote the park's actuation and the within-B
non-parked escape (attempt 18), not a rate delta) and the residual the two
W8-B loaded-slide escapes (both re-seated 3x; one with the park). The knob
stays default-off (a pass is not adoption) - **and by the R11-A adoption
attempt below it stays default-off for the shipped tree too**: the flip is
exactly this arm B (bit-for-bit), but the shipped acceptance collapses
9/10 -> 4/10 under it, so the enable path is the explicit
`FRUIT_REACH_ANYWHERE=1 FRUIT_REACH_HOVER_SETTLE=60`; the escalation stays
R10-C. The
default-off capped-hover fallback (`FRUIT_REACH_HOVER_FALLBACK` +
`FRUIT_REACH_DELIVER_MARGIN`) is a measured no-op on the corrected band
(**run 36 byte-identical to 34, 651/651 physics lines, 0 fires** - no reach
hover caps exist there); the setup model's x-term is a named design item
with its own pre-registration. No-harm: the knob-off acceptance 9/10 + motion
gate PASS + `fingerprint: matches`, byte-identical to the R10-A acceptance
(385/385), and `scripts/selfcheck.sh` PASS with the extended `198` leg.

**R11-A (2026-10-15, branch `r11-adopt`, `logs/r11/A_RESULTS.md` + WORKLOG
"R11-A"): the adoption attempt - the flipped default is exactly the measured
R10-A.1 arm B (bit-for-bit on the patch battery), but the shipped scattered
acceptance collapses 9/10 -> 4/10 (deterministic) and the R11-A gate's
acceptance-floor item FAILS; the shipped default stays the pre-adoption
`0`/`0` and the re-baseline + the mechanism are published.** The candidate =
`FRUIT_REACH_ANYWHERE=1 FRUIT_REACH_HOVER_SETTLE=60`: the patch battery
replays `logs/r10/35_reach_settle60.log` **685/685 physics lines identical**
(13/20 = 65 %, 13.5 s/attempt; the `199` section identical; the no-diag rerun
606/606 identical modulo the diag rows - `FRUIT_REACH_DIAG` itself is
run-neutral). The acceptance (`accept.sh`'s scenario): **4/10, 14.6 s/attempt,
1.17 placed/min, 10 re-seats, cone 6.74x** against the pre-adoption **9/10,
15.2 s/attempt, 2.90 placed/min, 0 re-seats** - the candidate double is
bit-identical (343/343) and the knob-off control replays the pre-adoption
record **byte-identically** (385/385; the patch control 643/643), so the
regression is the default, not the tree. **Mechanism:** the reach rule's
band-relative floor (~0.20 m) removes the shipped 0.40 m window - exactly the
v9 pre-fix collapse condition on the *stocked* scattered belt ("a 0.10-0.18 m
fruit ... 1/10", `logs/v1/pre_fix/`), which the shipped floor was calibrated
for; the patch sheet's clip-to-`up` slack masked it. Failures: two catch-up
chases (236.2 mm after the 2.02 s pre-pose recovery; 167.7 mm nominal) + four
carry/place escapes; the W8-B escape signature (re-seats 0 -> 10). No-harm
byte-for-byte on every untouched path: two-line dense **442/442** + `190`
PASS; two-line patch **821/821** + `190 -m 0.5`; the direct/policy selection
pinned by the new `select_target(reach_anywhere=False)` (`rl_env.py`; closes a
latent R10-A leak - with the knob on, the direct env's episode-reset
selection would have taken the reach branch); `configs/*` untouched; selfcheck
PASS (`198`/`199`). Also fixed here: main's `rl_env.py` `TASKS_MD5` did not
match the R10-A.1 `tasks.py` (the A1 follow was missed, so the RL env refused
to start) - the pin now follows the final tree. Named next: a **floored reach
variant** (`max(band-relative, shipped lead)`) with its own pre-registration,
or the **owner exception** on the documented numbers; the flip's re-entry is
one line + the acceptance + the reference re-record.

**R11-A.1 (2026-10-15, branch `r11-adopt`, `logs/r11/A1_RESULTS.md` + WORKLOG
"R11-A.1"): the floored reach variant - the floor closes the candidate-set gap
(gain +0 on both scenarios, no chosen fruit inside it) and the shipped
acceptance still collapses 9/10 -> 4/9 = 44 %, so the floor was necessary but
not sufficient; the defaults stay `0`/`0`.** The variant (one term): the reach
selector's candidate floor becomes `max(band-relative, the shipped lead)`
(`_dynamic_select_floor()`; new `FRUIT_REACH_SHIPPED_FLOOR`, default `1` in
the reach branch, `=0` restores the R10-A.1 rule - so **the R10-A.1/R11-A
enable-path pair above now resolves to the floored selector; the measured arm
B replays as that pair plus `FRUIT_REACH_SHIPPED_FLOOR=0`**); read only under
`_reach_anywhere_active()`, so the knob-off tree is byte-unchanged (proven by
the controls). The battery (Tier A solo, `logs/r11/A1_00_battery_driver.log`):
acceptance **4/9 = 44 %** (deterministic 329/329; the pre-adoption record
9/10 = 90 %; the control replays it **byte-identically**, 385/385, the patch
control 643/643) against the same-battery control 9/10, with **all five
lane-0/left attempts lost and the right 4/4**; the motion gate is **rate-only**
(all 9 descents inside the budgets; worst cone 1.22x reported). Patch battery
**10/17 = 59 %** vs the control 13/18 and arm B 13/20. **The floor invariant:**
`eligible == shipped` (12/12 and 40/40; `feasible` 16/58) and **0 chosen
inside the floor** (arm B 13/20) - the R11-A coverage mechanism (the below-
0.40 m window) is fully closed, and with it the reach rule's whole candidate
gain on both scenarios; what remains different from the shipped rule is *which*
floored fruit is chosen (min-travel vs farthest-upstream) and *where* the
catch aims (intercepts +0.03..+0.13 on the acceptance vs the station).
**Mechanism:** the interception is clean (`aims=9 feasible=9 fallback=0`; the
descent ends with the fruit +10.9..+14.4 mm short of the aim and the catch-up
closes it at the 6 mm tolerance in 11-53 ticks; **zero re-seats, zero chases -
the R11-A chase/re-seat signature does not reproduce**; the `SETTLE=0` probe
reads the same 4/9). The failures are the **post-catch hold**: every left
failure carries the force-servo signature `F_min = 0.00 N` / `gap == sep` /
`closed = 15.00 mm` / 38 trips (the servo chased the payload down its full
range onto air; the right's successes: `F_min` 3.4-3.8 N, 0 trips), the left's
lift carries 0.42-1.95 m/s of relative motion (the right's <= 0.18) and the
place0 legs slip 859-1582 mm - the **W8-B loaded-slide / carried-not-placed
class** the control carries once (its attempt-0 kiwi). The patch cross-check:
**lane 0 is 1/6 in the floored run and 1/6 in the control (arm B 1/5)** - the
patch's left is at its grip limit in every configuration - so the floored
patch delta sits on lane 1 (12/12 -> 9/11; arm B 12/15); the loss tracks the
scenario's fragile lane. **The sub-lever (choice vs aim) is not separated by
this battery**; the named discriminators are a choice-pinned pair (the shipped
farthest-upstream with the reach aim on, and vice versa) and
`FRUIT_CARRY_DIAG=1` (`clean_slip`) on the same battery. **Verdict:** the
pre-registered gate item FAILS; **no shipped default change** (`0`/`0`; the
floored selector is the reach branch's default, `=0` the arm-B reproduction);
the **owner exception** on the documented numbers remains the only shipping
path, and R11-B (the pre-onset load path) is unaffected. No-harm: the controls
byte-identical, `configs/*` untouched, `selfcheck.sh` PASS (extended `198`),
`199 --self-test` PASS, `96` PASS; a post-battery **print-only** fix corrected
the `199` met-error annotation (the sign is the wait loop's own: positive =
the fruit still upstream; `199` md5 `00fd74df` -> `26fb9be6`; committed
evidence files are not rewritten). Pins: `tasks.py`
`c2c7a626c4443592e7533eb92eea5bfe`, `rl_env.py` `48944d9c...` (unchanged),
`198` `fb4a2f7a...`, `199` `26fb9be6...` (battery-time `00fd74df...`);
`fruits.py` `a0ea1f54` unchanged.

**R11-B (2026-10-15, branch `r11-loadpath`, local, not pushed; the R11-C
close-out is `docs/CLOSEOUT.md`): the pre-onset load path is not the
discriminator - the payload is held to 0.5 mm through the window and the
escape is a mid-lift one-sided loaded slide; the screen's C1 (the close's
face speed capped at 0.04 m/s) converts on the direct interface (carried
48 -> 27, class-stratified exact p = 0.0026, `logs/p18b/B_RESULTS.md` section 4)
while the stage-P scripted battery is a bounded-attempt negative and the
scripted two-line does not transfer, so the phase closes not adopted:
scripted negative, direct positive, the class-matched direct re-run open
(`logs/p18b/B_RESULTS.md` section 5).** The three default-off,
dynamic-capture-scoped knobs (`FRUIT_CLOSE_LOAD_RATE`,
`FRUIT_CLOSE_CONTACT_LEAD`, `FRUIT_PLUCK_DWELL`) are byte-inert at default;
the M screen (direct, N=1x15) promoted C1 on the strongest readout of the
three - freeze row 18.0 -> 55.5, freeze-zone face speed 188.7 -> 39.9 mm/s,
cnp -6/-6 - while C2's lead does not move the contact-window geometry (the
close is entered with the fruit already arrested; lead 0.26 *punts* it
downstream up to 582 mm/s: the longitudinal variable is a velocity/shear one)
and M2 fails (a). The stage-P read is **12/20 = 60 % vs the control's
13/18 = 72 %**: the cnp item clears only exactly at the bar (3 = 5-2) and the
never-grasped class 0 -> 5 (late-freeze 40 mm/s closes; the fruit rides the
faces >1 s and the marginal grip slips at the pluck) fails the same-battery
item (iii) - the honest stage-P read is not positive. The stage-N direct
battery stopped incomplete on the day (A run 1 = 6/15; B run 1 partial;
`logs/r11/B_N/STOPPED.md`) and was **completed as the P18b N=5 batch; its
Oracle Gate-3 re-analysis is the verdict above** - A ok 22 / nc 5 / carried
**48** against B ok 39 / nc 9 / carried **27**, class-stratified exact
**p = 0.0026** (MH OR 1.79, CMH chi2 8.68) with **all 5 B runs beating all 5 A
runs**, and the pooled 22/75-vs-39/74 sign test **p = 0.500** reduced to the
*episode-pairing* endpoint (58/74 unpairable - a protocol weakness, not the
lever's read; `logs/p20/ORACLE_GATE3.md`). So C1 is **not "unconfirmed" on the
direct interface**: it moves the carried class there, and it is **negative on
all three scripted measurements** (this stage-P and the two-line **28/60 vs
45/60**, nc 8 -> 25 in `logs/p21/RESULTS.md` - the slow close is incompatible
with the never-stop dynamic catch). The knob stays **default off and not
shipped**. **P60 re-read that batch by arm and the "one open item" is answered:
it is not a left lever** - joining each episode's opening `arm=` to its closing
triple, the 48 -> 27 carried conversion is the **right's 28/51 -> 5/48** (Fisher
~2e-6) with the **left flat at 20/24 -> 22/27** (placed 2/24 vs 2/27, p = 1.0);
pre-P41 and pre-park, i.e. exactly the arm P43's park already fixed, so **no
direct carried-class lever for the left remains unspent**.
No-harm: acceptance **9/10 + motion gate
PASS + `fingerprint: matches`**, 385/385 `[fruit]` identical to the pre-phase
control; the scripted control 681/681 == `A1_25_patch_control.log`; the
two-line dense re-record **442/442 byte-identical to the W7-A record + `190`
PASS** (the branch probe reads 6.0 cm / 95 samples as before);
`selfcheck.sh` PASS. Pins: `tasks.py`
`3b15f3ff59e8923fea2b245adc7824b4`, `rl_env.py`
`874349039e16ef75e68f75eeffa8b850` (the `TASKS_MD5` follow also repairs the
stale pin inherited from `fd2e39e`: main's `rl_env.py` pin `b7d6f849...` did
not match its own `tasks.py` `c2c7a626...`, so the direct env refused to
start), checkpoint `moe_v13s` `61da390a85fa209496b54477a8255d23`.

**P1/P2/P1c/P3 (2026-10-15/16, owner directive "为什么会要等那么长时间的果？你增加流水
线上果蔬数量不行吗", branch `p-supply`): the supply-density knob exists and is
sound, its adoption recommendation is WITHDRAWN, and the place leg is closed by
geometry.** `FRUIT_SUPPLY_PATCH_DENSITY` (D, default 1.0, `fruits.py`) divides
the patch sheet's along-slice gaps by D (floor 0.085 m) and raises the abreast
probability toward 1; P2 extended it to the wave schedule's two gap bands. Raw
ladder on the two-line patch battery (ATTEMPTS=20, SEED=5): success
60/55/80/75/**90**/75/25 % and placed/min 3.64/3.36/4.48/4.48/**5.27**/4.20/1.53
for D = 1.00/1.25/1.40/1.50/1.60/1.75/2.00.

**Do not quote the ladder as a throughput result.** Two independent checks say why
(`logs/p3/ORACLE_REVIEW.md`, re-derived by `scripts/200_composition_audit.py` ->
`logs/p2d/82_standardised.txt`): (1) `186`'s two headline endpoints are **one
statistic** - the placement-window throughput *is* `60 / pooled_interval_mean` -
and the batch throughput is `success / s_per_attempt`, so with a fixed attempt
count and a flat cadence every headline is a monotone transform of the success
count; (2) **the density changes which fruit each arm is presented** (it changes
the release geometry) and the placement rate is class-dominated (0.44-1.00 per
arm/species), so **class-standardised the ladder is flat** (13.89/13.92/14.05/
14.68/14.43/15.12 adjusted vs 12/15/11/16/18/15 observed). The decisive test is
pre-registered at `logs/p1c/PREREGISTRATION.md`: a **single-grade supply** holds
the mix fixed by construction, so D is the only variable.

**What does hold, and it revises the R3 "arrival-bound" language in this file:**
the per-attempt **cadence is flat (~15 s)** and the **lock-on does not fall**
across the whole ladder, so the density does not shorten the wait or the cycle -
and the **binding term is the per-attempt span**, not the supply. Two other
measured facts: **D=2.0's collapse is a real density effect** (crowding breaks the
acquisition; -7.3 slots class-adjusted), and the single arm is **not** a
like-for-like transfer (at D=1.5 it starved on half its slots: 10 "no eligible
fruit" vs the control's 0, 10 picks in 19 slots vs 20 in 20 - the two-line's
worker parks and waits, the single arm's selector polls and gives up).

**P1c (2026-10-16) CLOSES the density as a positive lever: on a composition-free
single-species pool it is strongly NEGATIVE on the single-arm line** (65 % -> 17-30 % per
attempt, **0/20 -> 14/20 (and 30/40) empty slots**, 2.54 -> 0.63 placed/min; the D=1.60 double is
physics-identical). Mechanism: the denser sheet delivers the pool as **one burst** that drains
below the selection floor while the single arm's 15.4 s cycle is slower - at attempt 3 the
most-upstream live fruit is at y = +0.375 against a ~+0.40 m floor. **The two-line hides it**
(its worker parks and waits, two arms drain the pool), which is why the ladder looked positive
there. So: the knob stays default-off and is a **measurement instrument**, not a candidate
default; the surviving density effects are both negative (D=2.0's crowding collapse, and the
D>=1.5 single-arm starvation). `FRUIT_SUPPLY_SPECIES` (default off) was added for this test -
`_mix_env` rejects a zero weight, so a one-species pool was otherwise inexpressible.

**P3: the place leg is closed by geometry.** `FRUIT_PLACE_INNER_SHIFT` (default
off) shortens the place carry as designed (45.1 -> 36.1 cm, 297 -> 237 ticks,
~1.0 s) and the success rate **collapses 90 % -> 30 %**, because the payload
releases at |y| 0.21-0.41 while the belt's inner edge is at 0.375. The control's
release already sits ~35 mm inside the belt, so the maximum safe shift is ~30 mm
= **~0.2 s, 1.3 % of the span**, against a 4 % bar. The next span target is the
**descent's documented boundary shortfall** (40-90 mm short on every leg), not
the place. No default is flipped in either phase; if P1c confirms, adoption needs
both `motion_reference_patch.json` **and** `motion_reference_twoline.json`
re-recorded plus a `collection.patch_density` manifest field.

**P35 (2026-10-24, `logs/p35/`, default off, not adopted): the park is a measured
interface lever, its mediator is not identified, and the check is a separate object
from the outcome.** `FRUIT_ARM_PARK=<name>` (`rl_env.py`, direct presentation only;
`configs/arm_parks.json`, only the left arm has a park) teleports the **inactive**
arm to a named pose at reset instead of the shipped `ready`; unset it is one dict
lookup per arm and byte-inert. Phase 1 measured the geometric lever offline: the
inactive left arm at `ready` covers **98 %** of a 58 mm fruit's disc at along
+0.35 / 57 % at +0.40 (mean 0.382 of the stream), and `back` takes the marginal
cover to **0.002** with the hand 0.287 m above the belt (the right arm covers 0.00
and its park does not hold, so the lever is left-only and its population is the
**right-arm** episodes - the direct env sets the arm from the grade). The record
A/B (`logs/p35/C_ab/`, the Gate-1 P0-revised check, N = 5 runs x 15 episodes per
arm, seeds 77/101/202/303/404, interleaved, `moe_v13s` `61da390a` on both arms,
P33/W8-A scenario verbatim): **right 23/51 (45 %) -> 47/50 (94 %)** with the
**carried-not-placed class 25 -> 0** (composite 28 -> 3, no-grasp 3 -> 3), the
**left** no-op guard flat 1/24 -> 2/25, pooled **24/75 -> 49/75**, **B > A in 5/5
runs, all strict (one-sided p = 0.031)**. **The design-valid leg is the run level
plus the standardised counts** (right 94.9 % class- / 94.1 % size-standardised
against 52.3 %/45.2 %; the per-class deltas carry different denominators); the
**exact-instance pairing is conditioned on a post-treatment variable** - the streams
diverge with the outcomes, so only 22 of 75 slots stay pairable - and it reads
8 B-only / 0 A-only (p = 0.0039), carried 7-0; `C_pairs.txt` is the looser
same-species set (24 pairs, 8/1, the extra A-only being a different fruit). **The
check** (Gate-1 P0): M1 the pose held vs the pose the reset **achieved** (50/50;
the achieved-vs-commanded residual is reported, 0.088 rad - the shipped `ready` sits
0.037 from its own command, so a command bar cannot be the gate), M2a the arm term
at the +0.30..+0.40 band's **worst** call (50/50; control 0/51), and the census:
the band's **fully-hidden target calls 856/1257 = 68.1 % -> 0/1236 = 0 %**, calls
with any inactive-arm pixel inside the fruit's **projected-disc bbox** **100 % ->
0 %**. **The gate of record is M1 + M2a**; M2b (the episode-relative `rel >= 0.85`)
is a **recorded report at 36/50 = 72 %**, not the gate, and its misses are
`arm_px = 0` on 22-47 px masks (the running `px*d^2` normalisation + raster drift,
the belt as the largest instance). **What it does not show:** the park is a static
scene change on the image (3497 -> 4155 px of silhouette) *and* the **7
inactive-arm joints of the 25-D proprio**, and this A/B does not separate them;
the control **succeeds with the fruit invisible** (9 of its 23 right successes read
`px=0` at every band call; successes' median fully-hidden share 0.84 vs the
failures' 0.60), which argues against a simple perception bottleneck. So: **the
park is a measured interface lever; the check shows it removes the fruit's band
occlusion; the mediator (image vs the 7 proprio channels) is not identified.** It
ships **default off** (no shipped default changed) - the adoption gate is a
**recollection's own A/B**, which fixes both channels at once and can erase a
checkpoint-specific input-shift win, so it should not be the first spend on the
mechanism; the named discriminator is a small-N 2x2 **proprio-spoof x
image-spoof** (the park's joints in the obs with the arm unmoved, and the arm moved
with the `ready` proprio). `PREREG.md` section 5's literal arm-pose block
(> 0.02 rad) is **failed** by the 0.088 command residual (a `teleport_joints`
settle property); not adopted either way. No-harm: selfcheck PASS; acceptance with
both knobs unset **6/10 + `fingerprint: matches`** (the exit=1 is the expected
rate-only result) with **376/376 `[fruit]` lines identical** to
`logs/p34/73_accept_no_harm.log`; tree md5s identical before/after. Pins:
`rl_env.py` `fd18bb1b` (+424/-1), `arm_parks.json` `42ab4fb7`,
`scripts/217_arm_park_map.py` `d73618f9`, `logs/p35/park_ab_report.py`
`a796db0b`, `logs/p35/C_attribution.py` `b3311523` (batch-time
`cce04b95`/`c15c03ca`, Gate-2 docs/`frac` fixed).

**P36 (2026-10-24, `logs/p36/`, default off, not adopted): the park's mediator,
tested 2x2 - the image channel carries the win, the 7 proprio channels do not,
the probes are inconsistent input pairs and do not ship.** `FRUIT_ARM_PARK` moves
the arm (the image); the new default-off **`FRUIT_PROPRIO_SPOOF=<pose>`**
(`rl_env.py`, direct presentation only, vectors from `configs/proprio_spoof.json`
- the P35 measured `q_settled` poses, *not* the commanded ones) writes only the
**inactive** arm's 7 joints into the observation, leaving the active arm, the
image, the fingers and the tactile channels live, so the park's two channels can
be crossed. The batch (**4 cells x 3 runs x 15 = 180 episodes**, seeds
77/101/202, policy seed 11, one claim `RUN_LIMIT=25200`, wall 5146 s, randomised
cell rotation) passes its manipulation check from its own rows - the image
follows the **arm**, not the spoof: 670/670 and 724/724 band calls with
inactive-arm pixels in the ready cells vs 0/741 and 0/680 in the parked ones,
`rest_same=1` 180/180, the written vector within 0.0020/0.0040 rad of the
physical counterpart's live pose. Right-arm **carried-not-placed** (the primary):
cell 1 control **18/27 = 0.667**, cell 2 park/park **0/30**, **cell 3
park-image/ready-proprio 0/28**, cell 4 ready-image/park-proprio **17/30 =
0.567**; **image 0/58 vs 35/57, p = 8.8e-15**, **proprio 17/60 vs 18/55, p =
0.687**, interaction +0.100 (permutation p = 0.581 - the pre-registered
**descriptor only**: "adds nothing measurable under the ceiling", since the image
cell is already at 0/28). **The reading is the image channel** - *which* image
statistic carries it is **not separated**, with the fruit's **sightline** (the
P35 68.1 % -> 0 % occlusion census) the leading **unseparated** candidate (the
probe moves the parked silhouette as well as the fruit's pixels). **The probes do
not ship**: they are input pairs the checkpoint never saw, so the shipping path
stays a **recollection's own A/B** - which this read is *consistent with* - run at
the **WS-4.2 N = 5** convention (this 2x2 is a probe at N = 3), with the park
collected in. The cell-4 null is the **weaker** read (the parked proprio's j2 =
-0.978 rad is outside both reference stores' observed ranges - the only channel
that is; the 4-5 sigma summary is a mixed-population statistic) and it also sits
inside the batch's own left-arm no-op noise (0.050 vs 0.119), so the honest
statement is "no proprio contribution measurable at this n". A recording rollout
under the spoof is **refused** (a spoofed store would carry a pose the arm never
held); the park is not. No-harm: selfcheck PASS; acceptance **6/10 +
`fingerprint: matches`** with **376/376 `[fruit]` lines identical** to the P35
record. Pins: `rl_env.py` `aa54b022`, `configs/proprio_spoof.json` `374b88a7`,
`scripts/218_proprio_spoof_check.py` `95a3fe28`, `scripts/219_p36_cells.sh`
`2fe202d7` (batch `e19fa36d`), `scripts/220_p36_report.py` `42dd8339` (batch
`72f22dd5`).

**P37 (2026-10-25, `logs/p37/`, default off, not adopted): the park-collected
recollection preserves the park's win and the pre-registered S3 gate fails on a
scenario tail; the checkpoint adds no gain over the shipped `moe_v13s` + park.**
The question P36 left: a fine-tune on rollouts **collected under the park** (both
channels fixed) - the shipping path, since the spoof probes do not ship. The
store is the **direct-rollout** store (`110_rl_rollout --record` under
`FRUIT_ARM_PARK=back`; the collector parks through `tasks.go_ready` and has no
park): **90 episodes / 3,698 windows**, right 54/58 ok / **0 carried**, left 3/32
ok (`datasets/rl_rollouts/p37_park`, gitignored); fine-tune `moe_v13s`
`61da390a` -> `checkpoints/p37_park` `3fa45c96` (`ones`, 6 epochs, lr 5e-5, base
`demos_v11`, **28.3 % rollout window share** - the declared confound). The
adoption A/B (**N = 5 x 15 per arm**, seeds 77/101/202/303/404, one claim, **both
arms parked**, the W6-A patch sheet + the ACQ interface, A then B): the H2
manipulation gate PASSES 100 % per arm (44/44, 49/49); right-arm placed **A 43/44
= 0.977 vs B 47/49 = 0.959** (delta **-0.018** against the -0.10 margin),
**carried 0 vs 0**, S2 consistent, S4 -0.8 % (PASS), and **S3 FAIL** on one novel
`timeout: no grasp within 1500 ticks` (1/92 right). **The S3 fail is a scenario
tail, not a candidate result**: the trigger's lateral gate is a pure function of
the fruit's x (`dx = x - 0.333`, gate 0.16 -> only `x >= 0.173 m` is admitted)
and the delivered supply's x is **0.148-0.364 m**
(`logs/v1/12b_supply_after_free.log` line 409), so ~2.5 cm of the stream is
systematically unfirable; the event (x = **+0.159**, **below the band's 0.20 m
floor**) runs at ~1 %/episode, so at n ~ 45 per arm which arm sees it is ~a coin
flip. The formal rule fires (not an adoption candidate) but **the preservation
read stands and the event carries essentially no evidence about the checkpoint**;
**do not widen the gate** (the reach residual at x = 0.16 is **8.3 mm** -
marginal, not a flail - and a wider gate trades a no-fire for a grip-quality
failure). The **adoption recommendation is the no-gain**: the base sits at ~0.98
of its ceiling and the shipped `moe_v13s` already delivers the park's P35 **94 %**,
so a park-trained checkpoint adds nothing and is **not needed to ship the park**.
The pooled rate is an **arm-mix artifact** (right -1.8 / left +0.6 points;
standardised ~ -1; the right share moves 58.7 -> 65.3 %) - the right-arm primary
is the read - and the interval has **~no power** (-0.0885 at 47/50 equality,
-0.1045 one margin-step in), so the pre-registered **point rule** is the only
gate that passes (realized n 44/49 = the power table's n = 40 row, 98.2 %). The
fidelity direction is a **diagnostic, not a measurement**. No-harm: selfcheck
PASS; acceptance **6/10 + `fingerprint: matches`** with **376/376 `[fruit]` lines
identical** to the P36 record; no `src/`/`configs/` change, no shipped default.
The checkpoint and the store are **gitignored** (provenance in `logs/p37/`); the
next spend is the **supply/transport drift tail** and the **harness's
no-re-selection on a lateral refusal** (the 1500-tick timeout class), each with
its own pre-registration. Pins: `logs/p37/p37_report.py` `50dae91d` (batch
`e17aef37`), `scripts/221_p37_collect.sh` `115f2e25`,
`scripts/222_p37_finetune.sh` `c0509407`, `scripts/223_p37_ab.sh` `49febf5a`.

**P38 phase 1 (2026-10-25, `logs/p38/`, default off, not adopted): the
delivered-x drift is the *release*, not the transport - the transport
contributes exactly 0.000 mm - and the S3 class is too rare (2/3103 = 0.06 %)
for any A/B at this project's N, so phase 2 pre-registers a forced-band
mechanism endpoint.** No `src/` or `configs/` change (pins `rl_env.py`
`aa54b022`, `trigger.py` `d7ec85fc`, `tasks.py` `cdde6bd2`, HEAD `dd53d15`;
`logs/p38/MD5.txt`). The measurement (`P1_RESULTS.md`, `drift_census.py` ->
`drift_census.txt`, `probe_drift.py` + five claimed runs):

* **The delivered x per scenario** (deduped: a bit-identical replay reproduces
  an attempt's `(x, along)` to 4 dp, and the scripted buckets carry 3-6x more
  raw rows than unique attempts): scripted single scatter n=209 p50 0.272, min
  0.177, **0 below 0.173**, 3.8 % below the spawn floor 0.20; single patch
  n=272 p50 0.270, **min 0.158**, 0.37 % below 0.173, 6.6 % below 0.20;
  two-line wave n=682 p50 0.276, 0.29 % below 0.173; two-line patch n=2016 p50
  0.280, **min 0.143**, 0.45 % below 0.173; two-line bed n=38 (15.8 % below
  0.20, the 0.36 column drifting up). The **direct** population (the P35/P36/P37
  `[park] call ... x=` band census, n=653 episodes) reads p1 0.187, p50 0.264,
  p90 0.341, **min 0.159**, max 0.376, **2/653 = 0.31 % below 0.173**, 0.77 %
  below 0.180, 3.5 % below 0.20 (kiwi 8, orange 7, strawberry 5, lychee 2,
  apple 1), 1.7 % above 0.36. The on-belt design reading is `v1/12b`'s min
  0.148 / p50 0.279 / max 0.364 and the **pre-v9 fixed line** is the control:
  0.308-0.365 with no low tail. Within an episode the band census's `along`
  spans a median 0.096 m while x does not move.
* **The mechanism, measured**: over **475 full transits in five
  configurations** the transport's lateral contribution is **exactly 0.000 mm**
  (`probe_drift.py`; a sphere rolling on a plane whose surface velocity is
  along -y has no lateral force term, and the cleats are off by default) - the
  belt/cleat/friction/rolling drift hypothesis is **falsified**. The only
  stage that moves x is the release/settle, and its displacement is a **fixed
  per-instance offset** (same to 0.2 mm across the schedule and the arm pose at
  a fixed seed; -20.20/+15.04 for the seed-77 kiwis, -35.89 for a seed-5
  strawberry, up to +69.2 for a seed-77 kiwi drawn at 0.343 and delivered at
  0.413). So **delivered x = spawn x + offset(instance)**, the low tail is the
  negative offsets meeting a draw near the 0.20 floor, and the §1 class order
  (kiwi, orange) is the offset order. The corollary names the real supply
  lever: the offset is measurable once and **compensable at `respawn`**. The
  **open residual** is 5-20 mm: the attempt loop's deepest low-side x
  (0.143-0.159 = -41..-57 mm) exceeds the probe's worst instance offset
  (-35.9 mm), with the active arm's fly-by sweep, a re-release under a moving
  arm and a pair depenetration as the named candidates.
* **The S3 census** (549 direct-loop logs, grouped by each log's own
  `[rl] trigger=... lateral=...` + the guard flag): the **shipped interface
  (gate 0.16, guard off) is 3103 episodes with 2 never-fired = 0.06 %** -
  `logs/p37/B_ab/B_1.log` ep 6 (kiwi, right, **x=+0.159**) and
  `logs/w7/C_eval/direct_ab/B_3.log` ep 12 (peach, left, x unrecorded) - and a
  third low-x episode ended as `fruit fell off the line`
  (`logs/p35/B_ab/A_4.log` ep 14, orange, right, **x=+0.162**, tick 1298). The
  opt-in reach-cliff guard's 2/120 never-fired are **high-x** refusals
  (x=0.398/0.412) and are not this class; the pre-W4 gate 0.06 is 180/3195 =
  5.6 % (the documented W4 class) and the pre-trigger logs are 414/864 =
  47.9 %. **The admission floor is per arm**: right station x 0.3330 (n=431)
  -> **x >= 0.1730**, left 0.3400 (n=219) -> **x >= 0.1800** (the P37 text's
  0.173 is the right arm's number). At 0.06 %/episode a 75-episode arm expects
  0.05 events, so **no A/B at this N can measure the class** - the P37 batch's
  1/150 is batch clustering, not a rate.
* **The harness path**: the candidate is chosen **once per episode**
  (`rl_env.py:1538-1560`) and `should_fire`'s `|dx| > lateral` refusal returns
  `False` **with no marker**, so nothing re-selects and the attempt burns the
  whole 1500-tick *policy* horizon (`rl_env.py:2668-2674`; the primitive's own
  steps are after the cap) with the note `timeout: no grasp within 1500 ticks`.
  The phase-2 options are (a) a bounded re-selection in the same grade lane at
  the *provable* refusal, (b) an explicit `no firable fruit` terminal class,
  (c) both; and because `113_rl_report.py`'s `reasons()` digit-normalises every
  note, **any new note is a new failure reason** - so the attribution note is a
  run-neutral diagnostic ON in every arm and only the terminal behaviour
  differs.
* **The supply lever is a margin purchase**: to hold the delivered x above
  0.180 against the worst -0.057 m excursion the release floor must be
  **>= 0.237**, and the pair rule then needs the ceiling at >= 0.38 (a
  0.24-0.36 band degenerates `x0 ~ U(x_min, x_max - sep)`). Cost: three motion
  references + the scripted acceptance + both two-line gates + every store ->
  registered as **P38b**, not phase 2. `PREREG.md` instead registers four
  default-off direct-only knobs (`FRUIT_POLICY_REFUSE_DIAG`,
  `FRUIT_POLICY_REFUSE_END`, `FRUIT_POLICY_RESEED`, `..._MAX` = 2), three arms
  (control / END / RESEED+END) and four scenarios: **M1 the forced band**
  (0.10-0.17, 100 % refused), **M2 the mixed band** (0.10-0.36, 28 % refused,
  the conversion endpoint), **M3 the shipped patch band** (five supply seeds,
  the right-arm placed non-inferiority > -0.10, the no-new-reason set after
  mapping the notes to `lateral-refuse`, the fired-only cycle <= +5 %) and
  **M4 the scripted no-harm** (byte-identical `[fruit]` stream +
  `fingerprint: matches`), with six falsifiers and the rule that
  `no firable fruit` is still a failure in the rate denominator - the endpoint
  is *attribution*, never "the failure is fixed".

**P38 phase 2 (2026-10-25, `logs/p38/`, default off, **not adopted**): the
lateral-refusal harness names the class and halves its cycle, but the
re-selection cannot act in this harness, and on the shipped band the single
refusal landed in the control arm.** Four knobs, all default off and
`presentation == "direct"` only (`policy/trigger.py` `b09d3cb2`, `rl_env.py`
`f25f6b61`; `tasks.py` untouched): `FRUIT_POLICY_REFUSE_DIAG` (one
`lateral refuse: fruit x=... |dx|=... > lateral ...` note at the first
*provable* refusal - every other trigger gate passed, only the lateral one
failed, marked just before `x_edge_refusal` so the shipped fire decision is
identical), `..._END` (ends at the fruit's **departure** with
`no firable fruit: the trigger refuses (...) and the learned close never fired
(...)`, `outcome="no_firable"`), `..._RESEED` + `..._MAX` = 2 (bounded
same-lane re-selection, 4 scans/refusal, 1 per 60 ticks). **The Gate-1
condition H1 is the reason the END is defined this way**: the lateral gate has
never bound the learned close (`direct_fire = intercept or (policy_close and
gate_refuse is None)`; `gate_refuse` is only the opt-in `X_MAX` guard), so a
refused candidate can be picked anyway - on the forced band **5/15 (B) and 6/15
(C) episodes closed and 3 placed**. The class is therefore a *measured joint
closure* (trigger refuses + `x` frozen + no close through the fruit's
departure), and the END declines exactly those episodes (10/15, 9/15).
**H2 dissolved the registered supply bands**: a 4 cm lane is not a band - the
delivered x at 0.13-0.17 spans **0.117-0.191 (12 % above** the 0.173 floor) and
the free-cadence envelope 0.080-0.529 (depenetration kicks push fruit off the
**low** belt edge only - 0.080 against the 0.110 edge; the 0.529 maximum is
inside the 0.570 edge), so M1/M2 force the refusal with the **gate** on the
shipped supply (`TRIGGER_LATERAL=0` and `0.06`, the P2b-era gate). **H3** made
P4/P6 run-level unanimity gates (all five seed pairs negative **and** pooled
<= -0.10; the mirror for +5 %), because 47 right-arm episodes/arm at a ~40 %
base is a 1-sd ~0.10 point rule that false-fails ~1 in 6. **Measured**: M1
**15/15 refused in A, B and C** (P1 deterministic), **0 timeouts** and the named
class at median **562/510 ticks against A's 1335** (P3), A's terminals
`fell off the line` 12/15 + close 3/15 - **a registered deviation recorded as a
finding** (A1 predicted "ends at the horizon"; a refused fruit rides off the
belt end first), and the END's strength is that it collapses *both* terminals
(the horizon timeout and the lost episode) into one named class at the
departure; M2 refused **62 % (A) / 47 % (C)** with **83 scans and 0
candidates** - the re-selection is **structurally inert** because the direct env
calls `spawner.update` only in the reset's feed loop, so no fruit enters during
an episode (the amendment's "46 % lane starvation" is superseded: that number is
the free/driver cadence); M3 (the patch band, the shipped gate) had **1 refused
episode in 150 (0.67 %**, the phase-1 0.31-0.77 %, **not** the pooled 0.06 %),
and it landed in **A** (x = 0.157 - the drift tail, named by the diag where the
shipped note reads only `fruit fell off the line`), so C executed nothing: P4
right-arm placed **A 20/51 vs C 25/58, delta +0.039 [-0.138, +0.220]** with
per-pair +0.050/-0.111/-0.292/+0.179/+0.269 (PASS), P6 fired-only cycle **-2.0 %**
(PASS), **P5 FAIL** on both A-only keys coming from that one episode - the
pre-registered rule therefore reads **not adopted**, and that verdict carries no
harm evidence. **P5 is structurally a false-fail**: an arm-only key with a
0.5-1.2 event expectation per 150 is *necessarily* arm-unique, and the DIAG's
own `lateral-refuse` key is what fires it; a power-controlled form belongs in
the next registration (the literal read stands). The A/C arm-mix differs because
**the direct loop is not reproducible** (rendered frames; ep 0 is the same fruit
in both arms, ep 1 already differs, C executed zero actions), and the un-parked
**right-arm** base is **39.2 %** (20/51), not 45 % - the P35 mechanism is the
inactive left occluding the right arm's fruit, so the un-parked right rate is
the depressed one; the left's own 2/24 drags the *pooled* total, not that base.
M4: the scripted acceptance pair is **6/10 + `fingerprint: matches` in both arms
with the 376 `[fruit]` lines byte-identical** (md5 `bc7ca8f0`) and selfcheck
PASS - but the knobs are **unset by default and the scripted line never reads
them**, so that is near-tautological for this change; the `trigger.py` edit is
pinned by `811`'s lateral truth table + the analytic reorder equivalence, and
`accept_policy.sh` was **not** run (the knobs raise on any presentation but
`direct`, so the hybrid canary cannot read them). The DIAG's neutrality is read
by a same-batch **DIAG=0/1 pair** (`logs/p38/G2/`, 15 episodes each, one seed):
it agrees on **9/15** outcome classes (6/15 fruit) against the DIAG=1 repeat's
**14/15** (12/15), so the pair cannot carry neutrality at n=15 - the claim rests
on the construction argument (with `END`/`RESEED` off the harness writes notes,
bookkeeping and one fruit-pose read per refusal; none of it is a control input).
**The END's closure is scoped to "no close fired before the fruit's departure",
and the scope is a measured limit: `PREREG_A1` falsifier #1 FIRED** - 1 of 3
closes latched at `dy = -0.074 m` (7.4 cm past the station), so C3 is **not** a
total closure, `no firable fruit` over-claims on 1/15 of the forced band (a
failure either way: close-chase -> `no firable fruit`), and any flip needs a
re-registered definition (the post-departure rate quoted with the name) or a
post-departure grace window; the shipped-band readout of the close tick is owed
in the B-arm batch's report. **Recommendation**:
DIAG as the direct loop's diagnostic (owner sign-off), END as the measurement
interface with that B-arm shipped-band safety batch as its precondition, RESEED
not adopted (137 scans, 0 candidates) until the feeder is live inside an episode
(its own phase). Three **latent defects** are recorded as follow-ups, not fixed
(all direct-only, inert at the shipped defaults): `_reseed_step`'s
`spawner.protect` leaks into `protected_indices` (no unprotect; the
scripted/bimanual callers read that set); the END's `dy` is station-framed while
`should_fire`'s is `TRIGGER_FRAME`-framed; and the END runs before the fire
decision, ignoring `intercept`/`present`, with a per-episode `_policy_best_gap`.
Record `logs/p38/P2_RESULTS.md`; evidence `logs/p38/P2`, `P3`, `G2`, `M4`,
`P2_report.txt`, WORKLOG "P38 phase 2".

**P39 (2026-10-25, `logs/p39/`, default off, **not adopted**): the finger-tip
lane closes negative - the left's composite does not move at -4 mm in any
**evaluable** comparison, the
registered primary is not evaluable, the `47` probe's jam leaves the
belt-clearance claim untested, and `F1` is the tree's first **bimodal** arm, so
the lane has no arm it can certify.** Two levers were registered and only one
ran: **L1** `FRUIT_FINGER_TIP_DELTA` (`scene.py`, signed, **presence-gated** -
unset = the shipped mesh colliders byte-identically, `=0` re-authors the plate as
an AABB of the same mesh (arm **S**, the control), `=-0.004` shortens it (arm
**F1**)); **L2** the lift-only wrist hold closed as a **code fact before any
run** (the shipped `grasp_lift` already holds the commanded attitude - `_carry`
clears `arm.hold_quaternion` only for `name != "grasp_lift"` - so the knob only
swaps the hold *target*; `logs/444`'s negative is the place leg), and no W arm
exists. The batch is one claim with the arms **interleaved C -> S -> F1**
(same-tree control C; `scene.py` **988985ef**, `tasks.py` **112d2cb1**,
`rl_env.py` **238e90a4** - the `TASKS_MD5` metadata-only follow,
`configs/motion_reference.json` **25ade92b** untouched): C is a valid control
(pear **345/345** physics lines identical to `logs/p32/90_pear_battery_new.log`,
acceptance **374/374** to `D1_accept_pear.log` modulo the two print-only belt
messages; acceptance **6/10 + `fingerprint: matches`**). **The primary (the
species-locked pear battery) is not evaluable** - the left takes **2** attempts
in S and **4** in F1, so A1.3's count invariance fails - and **no arm improves**
in it (left placed/composite C **1/3**, S **0/2**, F1 **1/3**). **The acceptance
is inadmissible for the arm**: C's left takes 5 attempts and S/F1 take 6, the
left's fruit diverge from the third left attempt, and **inside S the same 5.4 cm
kiwi at the same read interference (grip-dia `+5.60` mm, close 22 ticks) cnp's
at attempt 3 and places at attempt 9** - so the acceptance's 5/6 left is not
evidence for the arm, and the matched-count "no fall" statement holds for F1's
**mode A only** (mode B: left 1 placed / 3 cnp). **The secondary band does not
fall** (pear left carry legs > 0.34 m/s: S 4 -> F1 5; acceptance 3 -> 3), there
is **no new failure reason** in any arm, and **F-1 is not adjudicable on F1** (a
byte-identity falsifier cannot be run on an arm that is not self-identical), so
the "contact-neutral" algebra is untested - **not** confirmed. **F1 is bimodal**:
five same-configuration acceptance runs land in two **bit-identical** modes -
**348 filtered `[fruit]` lines / 8-of-9** (x2) and **382 / 7-of-10** (x3), whose
first-attempt settle differs by one tick (0.88 vs 0.87 s); C (3 pairs) and S (1)
are single-mode, so the shipped line's determinism is not contradicted, but
**configuration vs harness is not separated** (the separators are more C/S
repeats and a fixed-pose contact read) and F1's numbers are **one draw**. **The
`47` probe does not measure belt clearance**: registered as a `-0.35 m` z
descent, it **jams laterally** - the jaw travels 0.13-0.17 m in x and 0.16-0.18 m
in y for 0.03-0.06 m of z, and C ends 90 deg rotated against S/F1 - and it prints
**no tool axis**, so N4 is **not computable as registered**; the belt-clearance
claim is therefore **untested, not measured-zero**, and PREREG **A3** withdraws
§6's "adoptable as a hardware/clearance change". What *is* proven: the box is
**authored** (build print long `84.9 -> 80.9 mm`, distal `80.5 -> 76.5 mm` at
`delta = -4 mm`), and the valid instrument for the clearance bit, if it is ever
wanted, is a **static-pose read of the authored collider prims** (`S - F1` must
differ by `4*cos(theta)`). **The pre-pose lever does not exist**: the station
pre-pose this tree's earlier record treats as a lane-0 mechanism
(`logs/p33/51_phase2_read.md` §3.1) is solved for the two-line's **right**
station only - the left station *is* the calibrated pick point
(`y = 0.00 = cfg.pick_y`), so `_prepare_two_line_stations` **skips its solve** and
the two-line left runs the same `grasp` config as the single arm
(`logs/p39/03_prepose_audit.txt`, whose annotation in the P33 read supersedes the
phrase). **The two-line reference is re-recorded**: `181c9151` was a pre-pear
W7-A record no post-P32 tree can reproduce (first physics difference `target
peach` vs `target pear` at attempt 0), archived to
`logs/p39/motion_reference_twoline_pre_p39.json`; the shipped
`configs/motion_reference_twoline.json` is now **d0326030** from the same-batch
control `logs/p39/p3/twoline_C.log` (6/10 at the 0.60 floor, `190` **PASS**),
while a W7-A-era two-line log now matches **no** current file - and
`scripts/189_w7a_chain.sh` re-writes the file from `logs/w7/10` before gating, so
it must not be run casually. Nothing was adopted: both knobs are **default off**
(`FRUIT_FINGER_TIP_DELTA`, `FRUIT_CARRY_ATTITUDE` - the latter a reporting-only
`[attitude]` line, one TCP-pose read per carry leg, whose `lip`/`tip=` constant
`FINGER_TIP_BELOW_JAW` is **80.5 mm** geometry, not the `logs/166` 76.8 mm
contact stop), F2 (the +4 mm extension) stays withheld/owner-gated (it is not the
authorized form), and the authorized P30-C hardware magnitude (24-45 mm) is not
tested here. Evidence `logs/p39/P1_READ.md`, `PREREG.md` (+A1/A2/**A3**),
`p2/NOTES.md`, `p3/RESULT.md` (§10 = the gate-3 close-out), `p3/P3_report.txt`,
`selfcheck.log`; WORKLOG "P39".

**P40 (2026-10-26, `logs/p40/`; **one** shipped change - the regrasp cap becomes
path-scoped - and nothing else adopted): the grip chain is measured end to end,
the carry class is **not** converted, and the only free rate on the tree was one
probe.** The default-off `FRUIT_GRIP_EFFORT=1` readout (reporting only: one
5-tick median per event, the finger drive's own numbers beside the tactile `N`)
ran two claimed acceptances (`logs/p40/p2/`, `effort_table.txt`): **the tactile
is not a scaled read** - the same-tick projected joint reaction agrees to
0.1 % / 0.5 % in both runs, so `GRIP_CENSUS` §3/§4's capacities and margins stand
and **nothing is multiplied by 2.2**; **the *command* is at its 10 N/joint cap on
40/40 contact rows** (the authored `k*err` is 4-8 kN, so `Fsat` clips every
time) **while the *delivered reaction* is 22 % of it** (2.21 N/joint = 4.42 N per
pinch) - the "2.2x discrepancy" compared the tactile to a cap the drive never
reaches, and the `F/err` ratio (**377 N/m at 120 Hz, 1045 N/m at 480 Hz**) is an
**operating-point timestep signature, not a stiffness** (the law is
unidentified). **`FRUIT_SUBSTEPS=4` doubles the force** - 4.42 -> 9.95 N
(**2.25x**, verified by both instruments) - at **3.08x wall** (266 -> 819 s) and
**+0.66 s/attempt** of span (`[stats]` 150.2 -> 156.8 over 10; *not* "+0.90 s",
*not* "+4 %"), which puts the **worst-case fruit's friction margin at
1.20x -> 2.70x** (`mu_eff` 0.45 against the 1.66 N following-error transient;
`mu_eff` 1.20 reads 3.20x -> 7.19x). Its **8/10 is a different attractor, not a
class gain**, and the left still carries-not-places **2/7** (orange attempt 3,
tomato attempt 9), so the class is **not deleted**. It ships as a **finding, not
a setting**: a store's **`write_manifest` `substeps` field is the unconditional
precondition** (the controller stays 120 Hz, `common.py:13-20`, so
*consumability* is not the issue) and a **real-jaw clamp-force anchor** gates
only a *fidelity* claim; the 2.25x-force / 3.08x-wall pair is **one pair** and
the scaling law is unidentified.

**The one adoption: `FRUIT_REGRASPS` is path-scoped** - **2 when
`_dynamic_capture_active`, 3 otherwise**, with an explicit env value winning on
both (`tasks.py`, `regrasp_cap`; the `FRUIT_REGRASP_REOPEN` slot reads the same
resolved value). Over 109 attempts a **third probe has produced nothing**: the
**17/17** attempts that burned all three never closed on the fruit at all
(`grasped 0/17`, `lift <= 0.004 m`), while the only conversion in the corpus came
on the **second** probe (`k=1`: 2/3 grasped, 1/3 placed) - which `=2` keeps - at
1.24 s (two-line) / 1.50 s (single arm) per failed probe. Measured with the knob
**unset** (the flip *is* the arm under test): the acceptance reads **5/9,
133.0 s, 14.8 s/attempt, 2 re-seat rows** against the control's **6/10, 150.2 s,
15.0 s/attempt, 3 rows**, and the two-line **7/10, 88.2 s, 8.8 s/attempt, 5 rows**
against **6/10, 90.2 s, 9.0 s, 13 rows**; the same-attempt read is the **k=3 tax
5.45 -> 3.93 s and 5.42 -> 4.00 s** with otherwise identical terminals, and both
runs are **byte-identical to the phase-3 `FRUIT_REGRASPS=2` battery** (339/339 and
430/430 filtered `[fruit]` lines), so the flip is exactly the measured arm. Both
counts are in **moved attractors** (`diverted` 0 -> 1; `no eligible fruit` from
attempt 4 on the single arm) and are therefore **not rate claims** - the
two-line throughput columns in `logs/p40/P3_RESULTS.md` are captioned as such and
stay out of this file. The indexed / policy-handover path keeps **3** by
construction: every re-seat row is `dynamic_capture`-and-`verbose`-gated and
`DirectSortEnv` is neither, so **no published number covers that retry** (and
`grasp.py`'s separate `GraspPrimitive` loop is untouched). **Both references were
re-recorded from these same-batch runs** because the flip moves both:
`configs/motion_reference.json` `25ade92b` -> **`adef05c9`** (pre-P40 file
archived to `logs/p40/motion_reference_single_pre_p40.json`) and
`configs/motion_reference_twoline.json` `d0326030` -> **`d87c3cdf`** (archived to
`logs/p40/motion_reference_twoline_pre_p40.json`); the gates then read
**`fingerprint: matches`** (rate-only FAIL, 5/9 < the 75 % single-arm floor) and
**`190` PASS** (7/10 at the 0.60 two-line floor). `scripts/189_w7a_chain.sh` was
**not** run.

**Two opt-ins, no flip.** `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` stays **off**: its
single-arm rule is also the **direct loop's** episode rule
(`select_target(..., reach_anywhere=False)` with no lane, `rl_env.py:1656`), so a
flip would silently move every direct baseline that has been measured, and the
measured gain is the arrival wait **1.41 -> 0.97 s** mean (1.20 -> 0.63 median) =
**0.4 s of a 15.0 s attempt (2.7 %)** on one branch, with +1 discharge; its
commit still sits **~0.15 / ~0.10 m above** the selector floor once the ~0.76 s
hover (0.09 m) is counted - the naive 0.463 -> 0.411 m read is a **lower bound**,
not a commit distance - so it does **not** spend the floor's margin.
`FRUIT_SUBSTEPS` keeps its shipped value (above). Pins: `tasks.py`
**`ec991e5c`**, `rl_env.py` **`8ebb8d87`** (the `TASKS_MD5` metadata-only
follow; HEAD `1790b87`), `scene.py` `988985ef`. Evidence
`logs/p40/{GRIP_CENSUS,RATE_CENSUS,LIT_REVIEW,PREREG,EFFORT_READ,REGRASP_YIELD,ARRIVAL_SPLIT,P3_RESULTS,P4_RESULTS}.md`,
`p2/`, `p3/`, `p4/`, `selfcheck.log`; WORKLOG "P40".

**P41 (2026-10-26, `logs/p41/`; **one** shipped change - the finger-drive
profile becomes the shipped default - and one **recorded deviation** from the
pre-registered F2): the grip force was a parameterization defect, the force
family is closed with a mechanism, and the carried-not-placed class does not
convert.** `control.finger_drive_profile()` ships **`finger_damp02`** —
**k = 1e5 N/m, c = 2000 Ns/m, pinned explicitly** (`c` is *not* derived from
`k`: the **ratio c/k = 0.02** is the mechanism) — with
`FRUIT_FINGER_STIFFNESS=0` as the pre-P41 path (the asset's own k = 1e6 /
c = 100, the 22 % delivery) and both env knobs still winning.
**Caption:** the delivered pinch goes **4.38-4.42 → 9.75-9.9 N (2.2x)** at
**1.00-1.01x wall per attempt** (14.8 → 15.0 s; the totals differ because the
branches take 9 vs 10 attempts), and 9.8 N is **50 % of the per-face cap** — 5.0 N
per face of the `Fsat` 10.0 N per joint (the tactile pinch sums both faces, i.e.
9.8-9.9 N of the 20 N the two caps could apply) — **the same ceiling
`FRUIT_SUBSTEPS=4` reaches at 480 Hz (9.95 N, P40)** for a third of the wall. The
plateau is reached at **c/k >= ~3e-3** (bracketed 0.002 → 7.2 N, 0.0033 →
10.0 N); the mechanism behind the ratio is **not identified**, so no threshold
number travels into the documents. **The pre-registered F2 fired**
(`logs/p41/DEVIATION.md`): the force rises and the class does not move, and the
profile ships *anyway* because the shipped 4.4 N is **44 % of what the same drive
delivers at 480 Hz** — the 120 Hz setting contradicts the asset's own authored
drive, i.e. a **parameterization defect, not a lever** — so the default flips and
**both references are re-recorded** although F2's clause says neither happens.
**Mechanism-positive, class-negative.**

The **census that decides it** (`logs/p41/P2_RESULTS.md` §4; `sep_max` from the
trace twins, which are byte-identical to the claimed runs, against the
`0.010 + 2·0.044 = 98 mm` mechanical stop): on the profile's escape legs
`sep_max` reads **98.5 / 76.0 / 77.4 / 64.2 mm** against the control's
**98.3 / 98.2 / 77.9**, so the pads **still reach their own open stop** while the
payload walks out along the tool axis (contact loss 12-63 ticks after the onset,
single-sided contact, `F → 0.00 N`, 38-54 servo trips) — **the pads hold and the
payload slides**, the W8-B loaded-slide class. The carried class is **not
force-starved** on this scenario. **`FRUIT_FINGER_MAXFORCE`** (default **off**,
**not adopted**) then takes the force family to its top end: the **cap** deletes
the pry — `sep_max` **98.5 → 43.5 → 31.2 mm** at **10 → 30 → 60 N** (that ladder
is why the default-off `[carry]` row carries `sep@loss`/`sep_end`) — and the
class does not convert: the acceptance **6/10 → 8/9 → 9/10** are **three
attractors** (not a rate), the pear **6/10 → 4/10**, the two-line **8/10 →
6/10**, and **60 N crushes a 3.7 cm strawberry** out of the hand (`clean_slip`
641 mm at `F@onset` 62.3 N). The pear control is **P41's same-tree 6/10**, *not*
P39's 6/9 (a different tree). **The sim's hold limit is geometry/hardware, not
force** — nothing here says the sim now holds the fruit (the acceptance still
reads 6/10 and the pear 6/10 under the profile).

**Provenance was the other half, and it is now unconditional.** `control.py` and
`common.py` were **absent from the collector's `sources`**, so no manifest could
tell a pre-profile shard from a post-profile one; both are pinned, and one
builder (`scene.finger_physics_provenance`) now writes the **`physics` block**
for **both** the collector's shards and the direct env's rollout manifests:
`profile`, `substeps`, `control_dt`, `dt`, `c_over_k`, the intent level
`FRUIT_FINGER_MAXFORCE` (null when unset), the contact pair, and the **per-joint
runtime read-back of k / c / `maxForce`** (`joint2`'s 0.0 N is the drive-less
mimic; `readback_matches` compares the **caps too**, so a `nan`/absent cap cannot
read like an `mf10` shard). The build print names the drive
(`profile=finger_damp02 k=100000 N/m c=2000 Ns/m maxForce=10.0/0.0N`), and the
drive-cap readers read the raw attribute **`drive:linear:physics:maxForce`**
instead of `UsdPhysics.DriveAPI.Get` (the call that constructs a schema object on
the mimic it describes; measured **inert** on this USD/lib, so the pre-fix builds
were sound, and the post-fix one-attempt run is **65/65 physics lines identical**
to the pre-fix control, `logs/p41/p4/a4_*`). Both references moved and were
re-recorded from the same-batch profile runs: `configs/motion_reference.json`
`adef05c9` → **`8a399626`** (the control arm matches the archive, so the move is
the flip's; gate `fingerprint: matches`, rate-only FAIL at 6/10 < the 0.75 floor)
and `configs/motion_reference_twoline.json` `d87c3cdf` → **`2246f83c`** (`190`
**PASS**, 8/10 at the 0.60 floor); the pre-P41 archives are
`logs/p41/motion_reference_{single,twoline}_pre_p41.json` and
`scripts/189_w7a_chain.sh` was **not** run. Pins: `control.py` **`9384ff4f`**,
`scene.py` **`27e3d64a`**, `tasks.py` **`54644916`** (the `[carry]
sep@loss`/`sep_end` diag), `rl_env.py` **`afe2c49b`**,
`scripts/40_collect_demos.py` **`cfcc6394`** (measurement-time
`8fae708f` / `6f9eba0b` / `1542ab4d`, before the phase-4 read-path and
manifest-sharing edits). Evidence `logs/p41/{FIDELITY_SWEEP,P2_RESULTS,P3_RESULTS,DEVIATION}.md`,
`p2/`, `p3/`, `p4/`, `selfcheck.log`; WORKLOG "P41".

**The phase-4 canary is a smoke, and it is inside the recorded spread.** The
hybrid policy canary (`SKIP_SELFCHECK=1 scripts/accept_policy.sh`, the shipped
`moe_v12`, the fixed pre-v9 supply, ten episodes,
`logs/p41/p4/accept_policy_profile.log`) reads **7/10 = 70 %** at the 0.60 floor
with **2 grip losses + 1 pick-station escape**
(`fruit left the pick station during the close (1416 mm)`, after the close had
already drifted the apple 283 mm - the policy's hand, not the drive: on the
preceding kiwi the fingertips were **575 mm** from the fruit when the close
started). The gate **FAILs on its reason clause only** (that note is outside the
recorded baseline set `logs/336_hybrid_v3all.log`; the verdict is printed in
`logs/p41/p4/accept_policy_claim.log`). This interface's recorded history is
**5-8/10** (`moe_v11` 8, `moe_v12` 6, P2b 5 and 6, P32 D0 5), so 7/10 is a
sample of the *p33-era* grip/station class, **not a rate** and not a profile
effect in either direction; the **direct** interface (where the profile is the
default presentation's drive) stays **unmeasured under it** and is the named
residual. No wedge, so no retry (the single retry was registered for a wedge
only); `189_w7a_chain.sh` not run.

**P42 (2026-10-26, `logs/p42/`; default off, **not adopted**): the seat is
centred and the seat family is closed in this parameter space - the pads are on
the payload at the close freeze and the payload leaves anyway.** The default-off
seat instrument (`FRUIT_SEAT_DIAG=1`, `[seat]` rows, 5 samples per grip) reads, on
two corpora (the acceptance and the species-locked pear battery, 10 grips each):
the pads' midpoint is **1.36-4.65 mm** from the fruit's centre in x/y on **20/20
grips** (median 1.7-2.4), **two-sided on 20/20** (per-pad `asym` 0.01-0.35, median
0.06-0.17), and the escapes are **not** the off-centre ones - on the pear the four
escapes are the *tightest* cluster (1.36-2.06 mm) while the corpus's largest
offset (4.65 mm) **placed**. That rank inversion is **noise at n = 4/6**; the
claim is carried by the **magnitude**: the entire available correction is ~3-4.6 mm
against a **104-276 mm** mid-lift walk - a factor of **30-60**. The only systematic
axis is **z** (+69.3..+71.7 mm = `_pad_standoff(True, sample)`, the *commanded*
standoff, i.e. the grip-plane question whose D2a form is measured negative),
not an error. What separates the classes is the **walk**, and it separates late:
the payload's hand-frame displacement by the lift's 99 % sample is **104-276 mm on
escapes vs 28-58 mm on placed legs**, with one pad out of contact on **18/32 escape
carry samples vs 0/48 placed** (at the first lift sample both classes read the
same 2.8-9.9 mm). **The bounded centring lever
(`FRUIT_SEAT_CENTRE=0.010`) acted and was absorbed**: it issued one `ik_step` per
grip (**|c| median 2.99 mm**, the 10 mm clamp never binding) and the freeze seat
was back at the control's value to **+0.00 mm** (pear, n = 6 pairs) / **+0.01 mm**
(acceptance, n = 10), because **the close owns the pose** - its own `coherent` flag
is **True on 20/20** grip closes and it issues an **absolute** `ik_step` every close
tick (`aim = [frozen_x, fruit_y + vy*lead, z = _pad_standoff]`; x **pinned** at the
first close tick by the shipped P2b x-lock, **y live**, **z commanded**), so a
one-shot pre-close correction cannot persist and the residual 1.4-4.6 mm is **servo
following error, not seating error**. The pre-registration's premise was a
**variable confusion** (`self._coherent[side]`, the carry bookkeeping's flag, False
60/60 - not the close's), so P1/P2/P3 are **not evaluable** and F2 fired by its
letter, not its named mechanism (`logs/p42/PREREG.md` amendment A1); the docstring
that repeated the false premise was corrected in **comment only**. **No count here
is a rate and there is no bare 6/10 -> 7/10**: the pear's moved branch changes the
**left attempt count 6 -> 4** (F5), and the acceptance is 6/10 in both arms on two
**different attractors** (the lever arm's fingerprint DIFFERS at leg 3,
0.109 vs 0.108 m/s). Verdict: the seat family is **closed in this parameter space** -
**reopen only via a new pad asset or a real-jaw clamp-force anchor**, never by
re-running "seat it better", and never read this as "the sim cannot hold the fruit"
or as "unfixable": `logs/p42/SIM_LIMIT.md` is **the canonical record** of the
loaded-slide limit (the mechanism, the closed force family, the reading rules - any
rate on this tree carries the `cnp` class). Scope: the **scripted single arm**; the
close is shared code but the two-line and direct paths were not run with the
instrument. Pins: `tasks.py` **`e2d0f12a`** (the measured tree was `3e6ea4cf`; the
close-out edit is the docstring only), `rl_env.py` **`50980bf5`** (`TASKS_MD5`
follow), **no `configs/` file moved** (`8a399626` / `2246f83c`). Evidence
`logs/p42/{SEAT_CENSUS,PREREG,P2_RESULTS,SIM_LIMIT}.md`, `p2/`, `p3/`,
`selfcheck.log`; WORKLOG "P42".

**P43 (2026-10-26, `logs/p43/`; **one shipped change - the arm park becomes the
direct env's default** - plus the phase-2 selector machinery at "0"): the park's
win reproduces at the P41 grip profile and it ships, scoped to the direct
presentation.** `FRUIT_ARM_PARK=back` is now the `direct` presentation's default
(`_park_default = "back" if presentation == "direct" else ""`, resolution owned
by `resolve_arm_park`): **`FRUIT_ARM_PARK=ready` restores the shipped pose** and
an explicit value wins everywhere; `handoff` resolves to no park, so it does not
raise. The phase-3 A/B (N = 5 runs x 15 episodes per arm, seeds 77/101/202/303/404,
policy seed 11, interleaved, one claim, `moe_v13s` `61da390a` on **both** arms,
the P35/P36/P37 patch scenario verbatim, four diagnostics on both arms) reads
right-arm carried **20/54 = 0.370 -> 0/56 = 0.000** (Fisher **7.31e-08**),
right placed **32/54 = 0.593 -> 53/56 = 0.946** (**+0.354**, Fisher 7.75e-06,
Newcombe one-sided 95 % lower **+0.228**), run level **5/5** (sign p = 0.031),
pooled **33/75 = 44.0 % -> 53/75 = 70.7 %** (**report only**; the
arm-standardised read is **0.320 -> 0.473** at 50/50 and 0.440 -> 0.707 at A's
mix), left **1/21 -> 0/19**, cycle **+0.2 %**. **Read it as one count, not five
legs**: **P1 and P2 are one 3-way outcome counted twice** (`placed = n - carried
- no-grasp`), so "+0.354 placed, p = 7e-8 carried" is a single contrast - the
independent legs are **P7 (the run level), P8 (the check), P5 (reasons), P6
(the cycle)**, and because 5/5 at five runs has **p = 0.031 as its minimum
attainable**, **P7 is the design's ceiling**, not a strong result on its own.
The left guard is **"not failed", not "PASS"**: 1/21 -> 0/19 clears the -0.05 bar
by **0.0024 = one episode**, and the informative read is its **carried 20 -> 18**
(the built-in no-op - `configs/arm_parks.json` lists a left-only vector, so the
left-arm episodes never move). **"0 carried" is 0/56, i.e. <= ~5 % at 95 % by the
rule of three, and 2 residual `force_min = 0` legs survive** (16 -> 2, roughly
8x reduced, **not deleted**); **"94.6 %" is one draw of a non-reproducible loop**
(rendered frames, CI ~0.85-0.99), not a rate. **The check** (read before any
outcome): the park arm holds the pose the reset **achieved** 56/56 on both reads
(M1-held/M1-applied), M2a 56/56, and the band census **0/1364 fully hidden** -
which is **"0 in 56 episodes"**, since those 1364 calls are ~56 clustered
episodes - against the control's 903/1340 = **67.4 %**; the 0.088 rad
achieved-vs-commanded residual is the `teleport_joints` settle property (the
shipped `ready` reset sits 0.037 from *its* command), which is why the gate is
written against the achieved pose. **The mechanism** is the W8-B loaded slide on
the right: `force_min = 0` **16/53 -> 2/55**, `clean_slip > 50 mm` **15/53 ->
2/55**, the retained pinch **9.31 N (A) / 9.74 N (B)** against the pre-P41 direct
corpus's **3.57 N**, and the left (no vector) unchanged (16/21 -> 15/19 lost legs,
`clean_slip` median 268.5 -> 253.8 mm) - the image channel, which P36's 2x2
separated (`which` image statistic remains unseparated). **Scope and the
re-baseline rule**: the flip is **direct-presentation only** (the canary
`60_eval_policy.py` never constructs `SortingRLEnv`, so `moe_v12` + park is
**untested** and has no deployment path), it **re-baselines the direct
interface** - every direct/policy number before P43 is a **pre-park** number, so
**to reproduce any of them set `FRUIT_ARM_PARK=ready`**, and park/no-park stores
must not be mixed (P37's transfer confound) - and **no motion reference was
re-recorded**: the scripted gate never imports `rl_env`, so `fingerprint:
matches` is an **import guard** on this change (the P38-M4-style near-tautology,
stated as such). `121`/`136`/`127`/`130`/`195` and the `110`-driven workflows
**silently re-baseline** to park-default. The A1 naming makes every log say it:
`[rl] env ready: ... park=back(default)` (`ready(explicit)` when set), the
`[park]` row `park=back(default)[left:back,right:ready]` (name, origin **and the
per-arm resolution** - the P43 B logs read `park=back` while the right arm sat at
`ready`), and the manifest's `arm_park.defaulted` (`true` = the default,
`false` = explicit, absent = pre-P43). The pinned pre-flip reproductions are
`logs/p43/p3/run_batch.sh`, `logs/p35/run_p35{b,c}_ab.sh` and
`scripts/219_p36_cells.sh` cells 1/4, whose A arms now pass
`FRUIT_ARM_PARK=ready` **explicitly**. **Two measured negatives ride the same
commit.** (1) **L1**: the nearest-above-floor selector is scoped
(`direct=True` -> always "0"; the scripted constant `NEAREST_ABOVE_FLOOR_SCRIPTED`
ships **"0"**) - the wait fell **0.32-0.73 s** in 4/4 pairs with a 2 ms mechanism
(1.958 s predicted vs 1.960 s measured on the seeded attempt), but `placed` fell
on **3/4** pairs, both treatment acceptance runs lost a slot to `no eligible
fruit`, and the mechanism's **prevalence is 20 %** of attempts against the 50 %
bar, so E3/E5 fail and the flip is **not** adopted - the machinery ships, so
`FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1` reproduces it with no code change. (2)
**L2**: the loop's pause is **10.7 %** of the episode wall (model 47.4 ms,
render 20.0 ms, camera 3.6 ms per decision) and **84 %** is the scripted primitive
plus physics stepping, so F4 fired and **no RTC/VLASH cell was run** - there is
no loop lever here. Pins: `tasks.py` **`a1b3d673`**, `rl_env.py`
**`0cefb13d`**, `control.py` `9384ff4f`, `scene.py` `27e3d64a`,
`policy/trigger.py` `b09d3cb2`, `policy/runtime.py` `379ac706`,
`scripts/224_p43_selftest.py` **`2edd81de`** (selfcheck: the selector scope + the
park default/scope), `configs/arm_parks.json` `42ab4fb7`,
`motion_reference.json` **`8a399626`** and `..._twoline.json` **`2246f83c`**
both untouched, checkpoint `moe_v13s` `61da390a`. Evidence
`logs/p43/{RATE_LEDGER,PARK_STATUS,POLICY_STATUS,PREREG,P2_RESULTS,P3_RESULTS}.md`,
`p2/`, `p3/`, `p4/`; WORKLOG "P43".

**P44 (2026-10-27, `logs/p44/`; default off, **nothing adopted**): the "don't cap
the arm" question is answered by arithmetic, and the speed cells buy 7-14 % at a
branch-dependent class cost.** The census (`logs/p44/CAP_CENSUS.md`) measures
every cap: **the joint velocity limits carry 2.1x** (`maxJointVelocity`
312 deg/s = 5.45 rad/s against the fastest reference), **the effort limits 2.4x**
(`maxForce` 7 N·m), and **the drive gains cannot change duration** - every leg is
**tick-clocked by its profile** (the model reproduces each leg to +-1.4 %, and
the gains were already measured null on the descent, `logs/165`). **The friction
cone does not bind on `lift` (a = 1.0 of 1.962) or `place` (1.089 of 4.273)** -
so what looks like a speed lock is a **profile choice**, and **48 % of the
15.05 s cycle sits in three blocks**: `place` **3.35 -> 2.49 s** (one
jerk-limited profile at `v_max` 0.35), `release` **2.04 -> 1.48 s** (1.57 s of
three open-loop holds), `lift` **1.82 -> 1.59 s** (the profile at `v_max` 0.30).
Three default-off cells (`FRUIT_SPEED_PLACE=0.52`, `FRUIT_SPEED_RELEASE=1`,
`FRUIT_SPEED_LIFT=0.36`) and their union (`FRUIT_SPEED_ALL=1`) are implemented
**on the existing per-leg overrides** (the `_SPEED_SHIPPED` block, `tasks.py`),
with a byte-identical unset path and a new selfcheck leg
(`scripts/225_p44_speed_selftest.py`) pinning the resolver and the seven caps /
ten read sites. **The union is real**: **-1.45 s/attempt** (median of two seeds:
15.00 -> 13.50, 14.60 -> 13.20), **-1.90 s** on the pear, **-1.10 s** on the
two-line (**+12 % placed/min, 4.90 -> 5.49, same 8/10**). **Nothing is adopted.**
S1/S2/S3 each fail the registered E4 **on the letter** (one new
`fruit did not follow the gripper` row apiece), and that class is the
**pre-contact acquisition** signature - the **pad span at onset** is 59-63 mm
(`sep@onset`; the *miss* is **219-481 mm**, `dynamic catch-up: residual` - P47's
correction), so the payload never sits between the pads; **the
control draws the same signature on seed 6 (59.4 mm) and 3/147 = 2.0 % of the
shipped single-arm corpus does**. The union passes E4 on all four batteries but
**fails E2 on the acceptance seed 6 - 5/10 vs 8/10** (Fisher **p = 0.30**; the
shipped line's own two seeds read 4 and 1 load losses), so the branch, not a
cell, decides. **On the held legs the cells read *lower* in-hand motion
(0.08-0.13 vs 0.07-0.18 m/s) and a *lower* place cone (median 0.87-0.88x vs
0.97/0.89x)**, i.e. the carried class is not implicated; the E4 failures are
acquisition. **The one positive worth a follow-up is the two-line**, where the
union is class-identical to the control and **11 % faster** - a two-line-only
adoption needs its own pre-registration and reference re-record. **A real defect
was found and fixed**: `FRUIT_DYNAMIC_PLACE_VMAX` was `min()`'d against the base
`FRUIT_CARRY_VMAX` (0.38), so a 0.52 cell silently resolved to **0.38** (-0.42 s,
not -1.09 s); the place branch now **assigns** its own cap, with byte-identity
proven on every recorded configuration (the shipped 0.35 is already below 0.38
and nothing sets `FRUIT_CARRY_VMAX`). **The ForceDelta half is scoped out with a
reason, not skipped**: it corrects a force/pose residual on a contact-rich
segment, and this tree's only such segment is the carry, whose class is closed
(`SIM_LIMIT.md`) with the cone not binding - and the guard family already
measured negative (`FRUIT_CARRY_GUARD` +5.4 % cycle, R6-B +4.5 %). The S13/E2
finding **justifies it as the named remedy** if the speed is ever adopted; it
would need its own pre-registration. **The 2026 frontier survey could not be
fetched** (a TLS `UNKNOWN_CERTIFICATE_VERIFICATION_ERROR`, then an `ECONNRESET`),
so `logs/p44/FRONTIER.md` records only what the local record already fixes and
says so. Pins: `tasks.py` **`b6de439c`**, `rl_env.py` **`93e35ef7`**,
`scripts/225_p44_speed_selftest.py` **`6b2e1945`**, `scripts/selfcheck.sh`
**`d82aa3af`**; `configs/motion_reference.json` **`8a399626`** and
`..._twoline.json` **`2246f83c`** untouched; `scripts/189_w7a_chain.sh` not run.
Evidence `logs/p44/{CAP_CENSUS,FRONTIER,PREREG,P2_RESULTS}.md`, `p2/`; WORKLOG
"P44".

**P44 amend (2026-10-27, `logs/p44/P2_RESULTS.md` §9) - the per-leg attribution,
with the existing knobs only (no `src/` edit) and the diagnostics proven
row-identical.** **S1** (`place` 0.52) moves `place0` **-135.4 ticks** and
`place1` **-64.2** (-1.13/-0.53 s) to **14.20 s/attempt, 6/10**, and is clean at
**both seeds** (the seed-6 pair 6/10 at 14.20 vs the control's 15.00).
**S3-v** (`lift` 0.37, `a` kept at **1.0**) moves the lift **-29.4 ticks
(-0.245 s)** with **no new failure row** and drops the `force_min == 0` legs
**5 vs the control's 7** - **the cleanest single cell**. **S2** at the clock floor
(dwell 0/pad 1/finger 1) takes the release block **2.04 -> 1.08 s** (130 ticks;
this confirms the **132-tick / 1.10 s** floor to two ticks, so the census's
"3 -> 1 = -1.02 s" was optimistic), reads **-0.96 s, 7/10**, and the release
landing is verified on every payload that reached it (**C 6/6, S2 7/7**; the
off-belt traces are lost *upstream*, never at the release). **The acceleration
half is not the lever**: the `a` 1.9 cell reads 1.59 s against S3-v's 1.57 s -
**0.00 s bought** - while spending transient (cone 1.42x vs 1.19x). `--strict-cone`
fails on the **control** too, so it is a relative report (C 5 legs/1.53x,
S1 3/1.53x, S3-v 7/1.19x, S2 4). **The pre-registered decision stands: nothing is
adopted.** The named adoption candidates, each needing its own pre-registration
and the two reference re-records, are **S1** (the largest clean single cell,
5.3 %) and the **two-line union** (class-identical, 11 %); the union's seed-6
5/10 stands as the reason it is not shipped as-is. Pins: `tasks.py` `b6de439c`,
`rl_env.py` `93e35ef7` (unchanged by the amend), the evidence as above.

**P45 (2026-10-27, `logs/p45/`; **default off, nothing adopted**): a lighter fruit
does not make the cell fast - it makes the walk worse and leaves the fling
alone.** The knob `FRUIT_MASS_SCALE=<x>` (a **physics change**, named as one;
`meshes.mass_scale()` parsed once at import, hard-erroring on `0`/negative/`inf`/
`nan`; applied at the **two** mass sites in `fruits.py` - the pool build and the
recycle `rescale`, which is the site that silently returns a respawned fruit to
full mass if missed - behind `if scale != 1.0`, so unset skips the multiply; the
inertia needs no second attribute because no fruit authors `diagonalInertia` and
PhysX derives the tensor at the authored mass; the sizes/meshes/colliders are
untouched; one build banner). The battery (5 arms x the acceptance + the pear,
every arm with `CARRY_DIAG`/`RELEASE_DEBUG`/`CYCLE_REPORT`): acceptance **C 6,
M50 6/9, M25 4/10, M50S 5, M25S 5**; pear **C 6, M50 7, M25 7, M50S 7, M25S 6**
- and the **speed is entirely the P44 cells** (15.0 -> 13.4-13.5 s/attempt with
the mass contributing **0.0-0.1 s**), so the mass buys nothing. **The census's
fling prediction was wrong and the measurement says why**: the release is a
**displacement-controlled pad ramp** (the exit speed is set by the pad-face
motion and the 47-68 mm drop), not a fixed impulse, so `v = J/m` never applies -
the in-hand release peak is **0.93-1.08x** of the control at 0.25x mass. What
*worsens* is the **walk**, on the mixed pool only: at 0.25x the acceptance's
escape legs go **7/20 -> 12/20**, its zero-force (loaded-slide) legs **7/20 ->
13/20**, and `clean_slip_max` p50 **0.1 mm -> 228 mm** - the loaded slide is not
mass-starved (it holds 4-5 N on one face while the payload walks), so taking mass
away gives the contact **less to resist**; on the single-class pear the same cell
reads *better* than a control that lost 8/20 legs, which is the branch, not the
mass. **At a fixed size 0.25x is 205-225 kg/m^3 (cork), so the cell can never
ship**; a physical equivalent would be a **smaller real fruit** - a new scenario
with new pinch spans, not a density change. **The frontier is in
`logs/p45/FRONTIER.md`** (the live survey succeeded on the third attempt, done
directly after the tool failed twice): **ForceDelta-VLA verified against the
abstract** - a *correction-distillation* from a frozen teacher's paired
force-conditioned/force-agnostic predictions, a separate **delay-correction**
target, asynchronous schedule replay with cached context, and a lightweight
policy that adjusts the reference from recent force history **without
regenerating chunks**: **82.2 % vs 54.4 %**, the Stage-1 teacher alone 70.6 %,
**~26 % lower peak contact force**; the ICLR 2026 *time-optimal execution of
action-chunk policies* (beyond demonstration speed) is the policy-loop pointer;
the delta robots' >100-200 picks/min are vendor **claims** on a different
kinematics; and **no measured study of a light payload being flung out of a
parallel jaw** was found. The transferable shape is the **bounded force-derived
pose residual between reference updates** (the named remedy for the P44 speed
cells), **not** the distillation (it needs a paired-teacher retrain, and this
project's three recollections read no-gain). Pins: `fruits.py` `b6de...`-era tree
+ the P45 faces (`meshes.py`, `fruits.py`), the cells default off, `configs/`
untouched.

**P46 (2026-10-27, `logs/p46/`; nothing adopted): the two-line union's +12 %
did not replicate at a fresh seed, and the class that moves is the pre-contact
acquisition, not the grip.** The P44 two-line positive was one seed; P46
pre-registered a **2-seed** confirmation **before** the run (`logs/p46/PREREG.md`)
and ran it with the existing knobs only (`FRUIT_SPEED_ALL=1`, no `src/`, no
`configs/`; the C arm is **453/453 rows identical** to P44's
`twoline_s5_C.log` and the U arm **446/446** to its S13 arm, so the instruments
are neutral and the default-off path is proven). **Seed 5 (a P44 replay)**:
placed **8 -> 8**, `s/attempt` **9.80 -> 8.75 (-1.05)**, interval 9.13 -> 8.27,
**4.90 -> 5.49 placed/min**. **Seed 6 (the fresh draw)**: placed **9 -> 7 (-2)**,
`s/attempt` 9.98 -> 9.51 (-0.47), interval 10.09 -> 10.88, **5.41 -> 4.42
placed/min**. **The guard is clean**: 0 held-then-lost rows in all four logs, the
held legs' >50 mm slip 0/0, `clean_slip` p50 0.00-0.05 mm; the s6 `force_min==0`
legs (1 -> 3) are **never-held** (contacts@onset 0, force@onset 0.00 N, the pads
closing on air; **52-65 mm is the pad span at onset, not the miss** - the miss
is 219-481 mm, P47's correction) - the **acquisition** class, not the loaded
slide. The
landing is clean too (**32/32 release-reached traces `on_belt=True`**). E1/E2
fail on seed 6, E3 fails by its letter only, E4/E6 pass; **F2 fires -> no flip,
no Phase 2** - the union stays **opt-in** and the single-arm cells stay opt-in.
**The lesson, stated for the next lane**: the speed is **real and reproducible**
(-10.7 % `s/attempt` on the seed-5 branch; the blocks move by the profile
arithmetic), but the **placement count is not stable across branches**, and what
moves is the **acquisition** class (a faster leg re-times which fruit is offered
at the close), **not** the grip - so a speed adoption must be gated on an
acquisition-class fix (a supply/station change) and not on the carried class.
Pins: no `src/` or `configs/` change (refs `8a399626` / `2246f83c` untouched);
evidence `logs/p46/{PREREG,P1_RESULTS}.md`, `p1/`.

**P47 (2026-10-27, `logs/p47/`; **not run - the census refuted the lever before
it was built**, nothing adopted): the "close on air" row is a standing property,
not an event, and the real pre-close discriminator is the catch-up residual.** A
census of 317 closes across the shipped / P44 / P45 / P46 corpora settles it: the
`... mm from the fruit; closing anyway` row fires on **317/317** closes with a
**7 mm-wide band** that is the **hover clearance** (70 mm nominal = `hover +
pad_lift`) measured **against the station, before the hover and the descent** -
its value carries **no** outcome information (Fisher **p = 0.61**), and the axis
sibling is **dead** (0/317). The fallback the row names is **unreachable**:
`pad_error > 20 mm` is always true, so `self._coherent[arm]` is **never set**
(0/317) - a dead code path, the P42 note's mechanism generalised. **The live
pre-close error is what separates the classes, and it is already printed**:
`[task] dynamic catch-up: residual` above its 6 mm tolerance reads **8/8
no-grasp** against **11/309 = 3.6 %** below it (**p = 3.3e-11**) - but it
explains only **42 %** of the no-grasp class, and its failing values are
**220-481 mm**, i.e. a **hand-over-timing** failure, not a distance-to-close. The
registered `35 mm / 40 tick` guard was therefore **predicted to fire on 8/317 =
2.5 % of closes and convert ~0** (the convertible 35-75 mm band is empty in the
corpus), so the battery was **not spent** - the PREREG is kept with its own
pre-run prediction as the record (`logs/p47/PREREG.md` §prediction). **The named
next lever is the hand-over timing/selection** (a target **2.4x** the catch-up's
reach budget away) plus the **11 converged close losses**, not a distance wait.
Pins: no `src/` or `configs/` change; evidence `logs/p47/{ACQ_CENSUS,PREREG}.md`,
`census.py`/`census_out.txt`.

**P48 (2026-10-27, `logs/p48/`; **not run - the census refuted both registered
levers**, nothing adopted): the acquisition misses are the **delivered-x tail**,
not the hand-over timing.** Across 317 closes the catch-up residual's >6 mm band
is **8/8 no-grasp** against 3.6 % below (Fisher **p = 3.3e-11**), and the band
6.0 -> 219.6 mm is **empty** - so the split is categorical. **The four events
share the x tail, not a timing**: **|x| >= 0.390 is 6/6 failed** (p = 2.1e-11
against 2/311), `>= 0.38` is 8 rows with **0 placed**, and within kiwi 8/8 vs
2/27 (p = 1.9e-06) - 3/4 are kiwis at **x 0.391-0.397**, i.e. **0.8-6.9 mm past
the 0.39 m clean lateral band**, while the arm recovered only 20-51 mm of the
200 mm the fruit moved; the fourth (480.6 mm) is the corpus's **only cross-belt
displacement** (a 379 mm drift, a 58.15 N / 99.1 mm-span close in 5 ticks) - a
supply event, not a timing miss. **The hand-over lead is a constant 0.189 m on
all 317 attempts**, so it cannot discriminate, and `dy0` ranks mid-population.
The reach budget is 200 ticks x 1.0 mm/tick = **200 mm**, and the residuals are
**1.10 / 1.23 / 1.26 / 2.40x** it - P47's "2.4x" was the **maximum and belongs
to the non-timing event**. **Both registered levers catch 0/4**: the lead
(`FRUIT_DYNAMIC_LEAD_MARGIN` 0.03 -> 0.20) moves the lead to 0.359 m but the
selector floor to **0.569 m** (against a measured dy0 max 0.570) for **+1.42 s
per attempt**, and the longer catch-up (200 -> 400 ticks) helps only the
displaced fruit while making the other three **~200 mm worse** - so the battery
was **not spent** (the PREREG keeps both predictions). The **11 converged close
losses** are the closed **grip/hold** class (the W8-B loaded slide: `contacts@
onset = 0`, `force_min = 0.00 N`, 2 re-seat rows on every single-arm one), not
acquisition. **The named next lever is a scripted selector x-ceiling** (refuse or
re-select fruit with x > 0.39 - the P38-style refusal on the scripted line, whose
selector polls, unlike the direct env's frozen feeder) plus the **supply
displacement** event. Pins: no `src/` or `configs/` change; evidence
`logs/p48/{HANDOVER_CENSUS,PREREG}.md`, `handover_census.py`/`_out.txt`.

**P49 (2026-10-27, `logs/p49/`; **not run - the ceiling refuses nothing**, nothing
adopted): there are **two x populations**, and the ceiling only sees the first.**
The census (`logs/p49/SELECT_CENSUS.md`) separates them: the **selection-time x**
(the `[bed-sel]` live set, 40 selections) has max **0.369**, so a ceiling at 0.39,
0.40 or 0.42 refuses **0 of 40**; the **delivered x** (174 unique attempts of 346
raw rows) reads p50 **0.276**, p90 **0.347**, max **0.3969**, with **> 0.39 =
3 (1.7 %)** - shipped 0/33, P44 2/73, P45 0/33, two-line 1/35. **The post-selection
x is not an identity**: 34/39 selections agree to <= 2.7 mm but **5/39 move
outward 5.3-19.2 mm** (P38's depenetration residual), so the failing x is bounded
to **[0.378, 0.397]** and the ceiling cannot catch it - the lever is **inert for
this class** (an earlier draft of this paragraph overstated it as "never exceeds
0.38" by reading one arm's range). A binding ceiling would also be expensive: a
usable set of **1** in **25/40** selections means a **skip** (no substitute), and
the 14/40 with two would substitute at **+0.9 to +2.1 s** (the next fruit arrives
sooner). **The named next lever is therefore P38b's per-instance release-offset
compensation at `respawn`** (P50) - the one thing that puts the *delivered* x back
inside the band - not a selection rule. Pins: no `src/` or `configs/` change;
evidence `logs/p49/{SELECT_CENSUS,PREREG}.md`, `select_census.py`/`_out.txt`.

**P50 (2026-10-27, `logs/p50/`; **the mechanism lands, the count gate fails, not
adopted**; the compensation ships **opt-in** with its per-pool tables).** The
per-instance release offset P38 left as a corollary is now measured: it is a
**per-instance constant to 0.00 mm** (two passes over 48 cells **bit-identical**, a
3-repeat cell `-2.90 x3`, settle -> station **0.09 mm** over 215-224 ticks,
cross-process <= 0.15 mm), **13/16 are x-independent** and the three rollers are
**1-3 discrete modes 11-20 mm apart** (not a slope), and a **(species, diameter)
table cannot carry it** - two strawberries **0.9 mm** apart in diameter differ
**44.3 mm** (pooled fit R^2 0.74, residual sd 10.2, max 31.0) - so the table is
**per pool**. `FRUIT_RELEASE_OFFSET=1` + `FRUIT_RELEASE_OFFSET_TABLE=<path>` shift
the already-drawn spawn x by `-offset(instance)` at `respawn` (no band clamp; the
measured excursion **0.155-0.389 m** stays inside the belt 0.11-0.57), default
**off**, and the tables are `configs/release_offsets_{accept_s5,pear_s5}.json`
(16 instances each, the two rollers at the pre-registered **minimax midpoint**,
the pear **identity**). **The mechanism is proven**: the isolated table goes
**8/96 -> 0/96** cells outside `[0.180, 0.390]` (0.1730-0.4131 -> 0.1932-0.3785,
pass spread 0.00 mm) and the live line's residual collapses **-35.73..+54.63 ->
-9.84..+9.83 mm** with the **planned draws untouched (65/65)**; the pear is
**inert** (378/378 physics lines identical, 6/10 both) and the no-harm arm is
**377/377 identical** to the reference with `fingerprint: matches`. **The
pre-registered count gate fails**: the acceptance reads **6/10 -> 4/10** on a
**moved branch** (the fruit sequence diverges at attempt 1; attempts 5/7 are apples
in O vs strawberries in C; every failure is `cnp`, the closed grip class), while
**both arms read 0/10 outside the registered band** - the PREREG's own power
statement says a 10-attempt count **cannot resolve** a 1.5-3 % tail. **Verdict:
P1/P2/P4/P5/P6 pass, P3 fails -> not adopted** (PREREG §5); the mechanism and its
tables stay opt-in for a scenario whose endpoint is the tail (the powered M1b form)
rather than a count. Named residuals: the mode rule is a **bound, not a
prediction** (the strawberry collapsed to one mode, the tomato became bimodal - both
inside the 20 mm margin); the **patch/bed** schedules are scope-gated and
unmeasured; the **direct/policy** interface reads the *delivered* x, so it would
benefit for free, but its A/B is its own pre-registration. Pins: `fruits.py`
**`e81051c1`** (+188/-0), `tasks.py` `b6de439c` unchanged, the two existing refs
untouched (`8a399626` / `2246f83c`); evidence
`logs/p50/{OFFSET_TABLE,PREREG,P2_RESULTS}.md`, `p1/`, `p2/`.

**P51 (2026-10-27, `logs/p51/`; **not run - the map refuted the hypothesis**,
nothing adopted): the speed cells' cost is the closed grip class, not the
release-x tail - and the speed arc closes.** The hypothesis was that the P44/P46
speed cells' only cost was the **pre-contact acquisition** and that P48's x tail
is that class, so `O + U` (P50's compensation + the speed) would be class-clean.
The offline map (`logs/p51/COMBO_MAP.md`) says **F1 fires**: of the **5
cell-attributable events, 1 is tail and 4 are mid-band** (x 0.22-0.38) **with a
converged close** (`dynamic catch-up: residual` 5.5-6.0 mm, i.e. **inside** the
6 mm tolerance) - the **closed grip/hold class**, not a supply-x object. So
`O + U` **cannot** be class-clean and the phase-2 battery was **not spent** (the
PREREG keeps its pre-run prediction). **The speed gain stands separately** (P44's
union -1.45 s/attempt; P46's two-line -0.76 pooled, -10.7 % on the seed-5 branch),
and its count cost is measured as **branch-draw `cnp`** on the single arm and
**converged closes** on the two-line - the same class `logs/p42/SIM_LIMIT.md`
documents as closed. This does **not** say the P50 tables are wrong (their object,
the release x, is simply not this corpus's cost), and it claims no rate (the same
cell draws 0 rows at seed 5 and the shared strawberry at seed 6 - one branch's
count). **What closes with it**: there is no remaining lever on the
acquisition/tail side of the speed question - the acquisition family is exhausted
(the distance guard, the hand-over timing, the x-ceiling and now the combination
all refuted by measurement), the speed is real, and **its cost is the closed grip
class**. A future speed adoption therefore has to be argued on the **time**
(-1.45 s/attempt at 10-14 %) with the placement cost named as the documented
class, not on a class fix. Pins: no `src/` or `configs/` change; evidence
`logs/p51/{COMBO_MAP,PREREG}.md`, `combo_map.py`/`_out.txt`.

**P52 (2026-10-28, `logs/p52/`; the model lane: **the policy-side speed has a
structural ceiling**, the two success hypotheses die offline; nothing adopted).**
The frontier's gate is RoboPace's ladder (arXiv 2610.09696, on a **dual-arm
OpenArm**): the same chunks at 10/30/50 Hz read **22/50 / ref / 4/50**, the
kinematic-only RACE-style retiming **1/50**, and the **contact-gated 32/50** at
half the slow arm's time - **the trade-off is speed *at contact***, and 1.67x
uniform costs 84 % of the success. This tree's policy does not own the cycle, so
the frontier's "beat the demo speed" framing does not transfer: the **policy phase
is 14.2 % of a placed episode** (256 of 1800 ticks, `logs/p52/P2A_RESULTS.md`), a
1.5x re-timing of the whole phase is worth at most **4.8 %**, and with the contact
gate firing on **44.1 % of the decisions** (4492 of 10202 ticks; peak force
216.4 N - RoboPace's "mostly free space" premise does **not** hold here, since
touch alone is 21.8 %) the measured gain is **-2.9 %** (median 1800 -> 1748 ticks;
paired -48.1, n = 23, 17/23 negative; **-5.0 % on the clean tree**) against a
**<= 4.8 % ceiling** - the registered -8 % bar was **unreachable by construction**,
and the paired/tick coincidence is **partly an unmatched initial condition** (the
treatment's fruit starts 21 mm closer at the reset, a feedback from shorter
episodes), so it is **not** a validation of the arithmetic. **The right arm - the
one the lever acts on - is unchanged**: 30/31 -> 28/29 placed (**delta -0.002**,
P2 PASS), and the pooled 32/45 -> 28/45 is entirely the **left's closed-`cnp`
draw**; no new failure reason (P3). `FRUIT_POLICY_TIME_SCALE` /
`FRUIT_POLICY_RETIME_GATE` stay **default off** (the 85 % scripted primitive is
untouchable by any policy-side execution lever). **Two success hypotheses died
offline** (`logs/p52/P2B_FEASIBILITY.md`): (1) the **reached-state supervision**
is not a defect - the labels are **0/581 455** out-of-range and the HOLD-frame
residual is 0.84/0.01 mm; the real defect is the **policy's own emissions**
(**13.1 % of joint steps out-of-range on 74.3 % of ticks**, 3-9 deg overshoot, no
clamp, a **19.3 mm p50 task-space dither**); (2) **PACE** (NeurIPS 2026, the
phase-aware execution horizon) dies structurally - the policy's chunks are **noise,
not a trajectory** (within-chunk min p50 2.44 rad/s, 0/60 below 0.30 rad/s,
|2nd|/|1st| 1.16), so the horizon rule returns h = 16 everywhere (64 -> 16
decisions, wall -12 %, **sim and placements unchanged**), and the policy's "phase"
is the belt-arrival wait, which the floor already covers. **Corrections the lane
made to its own census**: the decisions/episode is **53-84** (not 246-259 - that
was a tick count), the latency bound is **h <= 7** (71 ms = 8.5 actions, not 13),
and the intra-chunk rates were **4x understated** (the p99 headroom 2.35x/3.34x ->
**0.83x**). The named next lever is the **opposite** direction: an **action-hold**
(more ticks per action, to fix the dither/overshoot) plus a **joint clamp** on the
emissions - a success-first cell with the ticks as a reported cost. Pins: no
`src/`/`configs/` change shipped (both knobs default off); evidence
`logs/p52/{FRONTIER,MODEL_CENSUS,P2A_RESULTS,P2B_FEASIBILITY}.md`, `p2/`.

**P53 (2026-10-28, `logs/p53/`; nothing adopted): the policy's own emission defect
is not the success bottleneck.** The direct path emits **10.9-11.0 % of its joint
steps out of range** (8341 of 76587 ticks; 65.0 % of ticks carry one; 3-9 deg
overshoot, no clamp) - the earlier "4.8 %" was **one episode**, not the corpus.
Two default-off cells on the P43 protocol (N = 3 x 15, seeds 77/101/202): **C1 the
joint clamp** (the targets clipped to the arm's own `get_dof_limits()`, a copy,
after the shapers) removes the defect **completely** (`out 11.0 % -> 0/70938`, zero
time cost) yet reads **30/45 -> 29/45 placed** (per seed +1/-1/-1; the right arm
**29/30 vs 28/28**) - a **null** on the class, so the overshoot was **not** the
binding term; **C2 the action hold** (`action_hold=2`, 8 ticks/decision, 60 Hz of
decisions) reads **26/45** (0/-1/-3) - but that is a **pooled/arm-mix** statement:
the right arm is **26/26 = 100 %** and arm-standardised at T0's mix it is **30.0 vs
30.0**, the pooled drop being the left's closed-`cnp` draw, while the hold's real
win is the **wall** (**-7.1 %**, decisions **61 -> 29**, the 32 fewer model calls at
71 ms; the sim time is flat). **The dither story is corrected too**: the
same-tick dither falls 21.8 -> 17.1 mm but the **achieved arm rate falls 0.87 ->
0.73 rad/s** (-16 % of real motion), so the dither was buying motion, not waste. So
the policy's own emission path is exhausted as a success lever: the right arm's
remaining ~5 % sits in the **scripted close/handover/grip** class (P35-P43), not in
the policy's targets. With
P52 this closes the **model lane**: the policy owns **14.2 %** of the episode (its
speed lever is bounded at 4.8 %, measured -2.9 %/-5.0 %), its supervision is
sound, its chunks carry no phase structure, and clamping its emissions is free
but gains nothing. The model-side levers that remain are the **interface** ones
already measured (the park default; `FRUIT_POLICY_EVENT=1` at +6.7 pt on N = 3,
never at N = 5; the ACQ question that the shipped direct config leaves untested).
Pins: `rl_env.py` **`a1ae217a`** (both knobs default off), a new selfcheck leg
`scripts/229_p53_emit_selftest.py`; no `configs/` change; evidence
`logs/p53/{PREREG,P53_RESULTS}.md`, `p3/`.

**P54 (2026-10-28, `logs/p54/`; **one shipped change, a recorded deviation from
R5: the adaptive acquisition lead is now the direct presentation's default**): the
shipped direct config was **not** the configuration on record.** Every "direct
94.6 % / 4.8 %" number in this file was measured at `FRUIT_POLICY_TRIGGER_ACQ=1`,
while the shipped default left `acq` **off** (W7-B/R5 kept the knob a *measurement
interface*). P54 ran the A/B the record never did (N = 3 x 15, seeds 77/101/202,
the P43 protocol, the park default, `moe_v13s` `61da390a`): **A (shipped, ACQ
unset) 16/45 = 35.6 %** - right **15/28 = 53.6 %**, the **never-held class 26/45 =
57.8 %**, the catch-up residual p50 **90.6 mm** (p90 391.6, max 1212.6; 24/45 over
the 6 mm tolerance) - against **B (ACQ=1) 34/45 = 75.6 %**, right **34/35 =
97.1 %**, never-held **2/45 = 4.4 %** (Fisher **p = 3.2e-8**; right 12/28 -> 1/35,
left 14/17 -> 1/10), the residual p50 **5.7 mm**. **The mechanism is the fire
budget**: the fixed 0.90 s lead fires at `t_arrive` 0.89-0.90 s on 45/45 against
the handover's own **1.17 s** `wait` setup, so the close happens **72-566 mm past
the fruit**; the ACQ lead (p50 2.11 s, cap 4.50) holds 0.75 s and closes at
**3.6-3.9 mm**. **The left arm does not move** (1/17 -> 0/10; its class shifts
14 never-held -> 9 cnp but not its rate - the closed grip class, not an ACQ
effect). One B-only `fruit fell off the line` (a left kiwi at x = 0.176, below the
left's 0.180 m floor - the P38 x-tail, not the knob). **The change**:
`FRUIT_POLICY_TRIGGER_ACQ` resolves **on when `presentation == "direct"`**, an
explicit `=0` restores, and the scripted / hybrid / two-line paths are untouched
(the env-only knob is read in `rl_env.__init__`, verified by a 2-episode smoke
that prints `acq=on` with the env unset). **The re-baseline rule**: every direct
number from here is **ACQ-on**; the pre-P54 direct corpus is **ACQ-off** (35.6 %
pooled / 53.6 % right) and must be labelled so. The root-cause alternative is
named: a default lead **>= 1.17 s** would fix the timing without the ACQ formula
(the lead is a plain env default) - its own pre-registration. Pins: `rl_env.py`
**`5bc084d3`**, `policy/trigger.py` `b09d3cb2` unchanged; no `configs/` change;
evidence `logs/p54/{PREREG,P54_RESULTS}.md`, `p1/`, `flip_smoke.log`.

**P55/P56 (2026-10-28, `logs/p54/`, `logs/p56/`; both **default off**, nothing
adopted): the direct line's supply is continuous **once fed**, and the multi-pick
episode buys 2.7 % of a pick - because the 30-tick feed round it removes is
**load-bearing for the supply**. The owner's "the fruit comes in waves" is
structural: the direct env's only `spawner.update` site was the reset's
selection loop, so the supply was built at `reset` and frozen - the belt is
**not** rebuilt (`create_pool`/`prime` are `__init__`-only) and it is **already
stocked** at selection (farthest-upstream `y` = **0.491-0.675 m against
`spawn_y` 0.68 = 72-99 %**), so the wave is the **episode boundary**. `FRUIT_DIRECT_FEED=1`
(P55, `rl_env.py`) runs the spawner's schedule every `advance` (+11.1 % wall,
belt stock +11 mm median - it does not buy supply); `FRUIT_DIRECT_CONTINUOUS=<n>`
(P56) is the multi-pick episode (one reset, n picks, the recorder's npz index
increments, the reward/outcome accumulated, `[cont]` rows, `[bed-sel]`/`[grasp]`
now wired into the direct env), raising unless `presentation == "direct"` and
`ablate == "none"`, and **implying** the feeder. The census: the inter-attempt
gap is **exactly 140 ticks = 1.167 s** (30 feed + 3x30 teleport + 20 settle) =
**6.4-6.7 %** of the span, starvation 0/11, and the mode's sim ceiling is
**2.97-4.45 %** of a pick (arm switch 55-64 %); the larger wait is the
**arrival** (2.07-2.13 s = 13.5-14.4 %), which continuity does not touch. The
measured battery (seed 77, A 15 single-pick episodes vs B one 15-pick episode):
gap A **140x14** vs B **[50, 80x9, 110x4] (med 80, max 110)** = **-53.6 ticks
(-0.45 s, 2.7 %)** with **8/14 transitions starved** - the removed feed round is
**supply-load-bearing**: the catch floor **0.399 m** against the queue interlock's
edge `pick_y+0.45` with `FRUIT_QUEUE_MAX=6` leaves a **5 cm** catchable sliver,
so a 15 s pick drains it and the next selection reads `window=0` with
`on_belt=8` (P33's aperture class, direct line). Placed **A 11/15 (2.67/min) vs
B 8/15 (2.00/min)** is a **different branch** (right 10/10 vs 8/9, left 1/5 vs
0/6) and carries no rate claim; P1 FAIL on its max (median at the 80 bar),
P3 FAIL (73.3 % < 90 %, the control itself 80 %), **P6 FAIL as registered** but
the **shipped** line's own start pose is outside the same 0.011 rad bar on
14/15, so the bar - not the mode - is the finding; P4/P5 PASS (no new reason;
15 distinct indices/npz in both stores, `ticks_total == sum`). No-harm:
`--ablate scripted` **44/44 lines byte-identical** across the pre-edit, measured
and final trees; selfcheck PASS. Pins: measured `rl_env.py` **`cfbce71d`**,
final **`1845c2c4`** (docstring-only close-out, reconstructed-and-matched);
`tasks.py` `b6de439c`, `fruits.py` `e81051c1`, `policy/trigger.py` `b09d3cb2`
unchanged; `configs/*` untouched; checkpoint `moe_v13s` `61da390a`. Evidence
`logs/p56/{DESIGN,PREREG,PREREG_A1,CENSUS,P56_RESULTS}.md`, `p0/`, `p2/`.

**P58 (2026-10-28, `logs/p58/`; **one shipped change** - the direct presentation's
supply profile - and nothing else flipped): the shipped direct supply was a
per-episode burst with a timed refresh, and the profile that replaces it is the
**clock pair plus the band interlock at `FRUIT_SUPPLY_BAND_MAX=4`**, all resolved
on for `presentation == "direct"` only, an explicit environment value winning.
Four arms, 3 seeds x 15 picks, the shipped per-pick interface
(`FRUIT_DIRECT_CONTINUOUS` never set): **control** `window` **2.60** (2.57 on the
pooled-with-abort read), `==1` **4/45**, `on_belt` 5, `skipped` **104/107/105**,
starves **0/42** (bought by the reset's re-stock), wall **29.66** s/pick;
**A' (cap 3)** 2.02, 12/45, 9, 41/36/39, **1/42**, 34.07; **A'' (cap 4)**
**2.38**, **9/45**, **11**, **8/4/9**, **0/42**, **35.40**; **A''' (interlock
off)** 2.20, 12/45, 11, **2/0/2**, **5/42 (169/380/170/289/291 - 11.9 %)**,
35.43. The registrations' branches read: **B1 does not fire** (A''' fails E1
*and* E3), **B2 fires** (A''' starves 5/42 against A' 's 1/42 and A''s 0/42),
**B3 is unreached** - so the unit is the triple at **cap 4**, and **cap 3 is a
measured regression** (its cap binds and refuses ~2.5 patch partners per pick).
**Read the two counters together:** `supply_skipped` is *not* the slot-loss
counter on the non-bed path - a depth-capped release re-bases `_next_release` in
`_pump_supply` without incrementing it, so the loss appears as a **starved feed
round** (`sel_gap >= 169`), not a skip; that is exactly A'''s 2/0/2-with-5/42,
its pacing counting the station window `[-0.05,+0.45]` at `queue_max=6` (mostly
past-station bodies, P56's aperture) while A'' paces on the approach band at 4.
**`on_belt` is not a catch metric:** the identity `on_belt = admitted +
below_window` holds on all 45 blocks, and at cap 4 the below-station share is
**6.24/block = 54 % of candidate rows** (control 0.20 = 3.4 %), so `on_belt` 11
must never be read as "11 fruit available"; the catchable read is the `window`
distribution. The control's 2.60 is a **post-reset-burst** instant (one feed per
episode, ~7 stale slots dropped per reset - the timed refresh the owner
rejected), so it is quoted as the rejected baseline, never as the composition
bar. **Wall:** +19.3 % (29.66 -> 35.40 s/pick) at a **flat sim span** (1827 ->
1824 ticks/pick), i.e. 0.01623 -> 0.01941 s/tick with 6 -> 12 live bodies - a
harness cost, reported, never gated and never attributed to the policy (P55
measured the feeder alone at +11.1 %; P33 phase A the body physics at +24 % for
21 vs 6.6). **`FRUIT_DIRECT_CONTINUOUS` must not be defaulted:** it is a
run-length parameter (it rescales `--episodes` in `110/121/136`) and it
corrupted the printed summary (`[rl] rollout success 0/1` on a 10-placed run -
parsed by `113_rl_report.py:41` and `129_rtc_report.py:34`); it is
`--continuous N`, opt-in, and the summary is pick-level in that mode.
**Re-baseline:** every direct number before P58 is a **pre-profile (burst)
number** - `FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0
FRUIT_DIRECT_FEED=0` restores it, composed with `FRUIT_ARM_PARK=ready`
(pre-P43) and `FRUIT_POLICY_TRIGGER_ACQ=0` (pre-P54). No motion reference moved
and none is re-recorded: the scripted path never constructs `SortingRLEnv`, so
`accept.sh`'s `fingerprint: matches` is an **import guard** (its `[fruit]`
stream is 377/377 identical to `logs/p41/p2/accept_profile.log`), and the hybrid
canary is **out of reach of** this profile, not untested on it:
`_resolve_supply_profile` is `SortingRLEnv`-only (`rl_env.py:2259`) and
`60_eval_policy.py` builds its own `FruitSpawner` (`:142`) and
`PickAndPlaceTask` (`:238`) with no profile kwargs, so they fall back to the raw
reads whose defaults are interlock `0` / cap `3` (`fruits.py:951-960`) and
`FRUIT_FEED_CADENCE=0` (`tasks.py:1150-1154`); `FRUIT_DIRECT_FEED` has **no
fallback outside `rl_env`**, and `accept_policy.sh:80` fixes
`FRUIT_SUPPLY_SCATTER=0`. Every canary number, before and after P58, is the
**pre-v9 fixed supply** - the re-baseline statement owed for `moe_v12` is
**"no path"**. Not covered: `BAND_MAX` 6 (`5` and
`FRUIT_SUPPLY_TARGET_FROM=0.40` are measured and rejected, P59 P2/P3), the
two-line (its own `feed_pump`; `_feed_scope`
excludes it), the handoff presentation, and any store recorded under the
profile. Pins: `rl_env.py` **`6d7cb329`** (*the file P58 shipped*; P59 gate 1
then moved it to **`1b1e5cdf`** with a provenance-only edit, `be5e41c` - row
provenance + `target_from` in the manifest, the shipped path byte-unchanged),
`tasks.py` **`8ad8ddc8`**,
`fruits.py` **`c7461d41`**, `scripts/230_p58_supply_selftest.py`; `configs/*`
untouched (`8a399626` / `2246f83c` both stand); checkpoint `moe_v13s`
`61da390a`. Evidence
`logs/p58/{PREREG,PREREG_A_APRIME,PREREG_A_APRIME2,PREREG_A_APRIME3,A_RESULTS,A_APRIME_RESULTS,A_APRIME2_RESULTS,A_APRIME3_RESULTS,P58_RESULTS}.md`,
`A{2,3}_report.txt`, `p1/`, `p3a/`, `p3b/`, `p3c/`, `v_*.log`; WORKLOG "P58".

**P59 phase 2 (2026-10-28, `logs/p59/p2/`; **no shipped change** - the
catch-margin arms both fail E1 and the bar is not adjudicable, so the lane closes
as **non-binding** rather than as a loss).** With the shipped profile as the
control (`window` **2.378**, `==1` 9/45), **A (`FRUIT_SUPPLY_BAND_MAX=5`)** reads
**2.533**, `==1` **4/45** (**non-worse in 3/3 seeds against the cross-tree P58 phase-3b cell A2, 2/3 against P59 phase 3's same-tree control** - on seed 101 the control draws **0/15** `window==1` to cap 5's 2/15; per-seed sums 39/39/36 vs A2's 36/39/32, ties-dropped p = 0.25, pooled p = 0.50) and
**B (`FRUIT_SUPPLY_TARGET_FROM=0.40`)** 2.267, 10/45; both have **0/42 starved
rounds**. E1's `2.57` bar is the **pre-P58 burst** cell pooled over **51** blocks
- it includes the 5-pick aborted run while every other cell is 45 (same foot:
**2.600**) - so it matches no row, and A's mean 95 % CI is **[2.282, 2.784]**
(two arms need |delta| >= 0.50 to separate at n=45): **no depth mean ranks the
arms**. What decides it is that **no behavioural invariant moves** - `window==0` 0/45
and starves 0/42 in all four cells, `sel_gap` the **same support and total**
(`{139,140,141}` x 42 - one ~140-tick gap split by the 1-tick print rounding; the
*multiset* equality {139x8, 140x25, 141x9} holds only against the cross-tree A2
cell) - and that **the counters which do move sit at the same-configuration
cell-to-cell spread, so none is attributable to the cap**: `skipped` **21 = 21
against A2 but 24 vs 21 against the same-tree control**, exactly the 3 the two
cap-4 cells differ by; `placed` 26 vs 27, *less* than the cap-4 cells' own 26 vs
28; wall 34.49 vs 35.35 s/pick (inside the live-body confound). **cap 4 stays.** **`TARGET_FROM=0.40` is rejected mechanically**: `window` counts
only `usable`/`chosen` (`tasks.py:5515`), so its "dead sliver" rationale targeted
a re-derived occupancy, and on the real counter it reads 2.244 vs 2.711 while
`below catch floor` **rises 2.31 -> 2.82/block** - it feeds the sliver it meant
to delete (its `skipped` 8 vs 21 at zero starvation is the recorded trade).
**Reopening** needs a **same-tree 45-block control** (this registration's named
control does not exist - phase 1 never ran one; the substitute was the cross-tree
P58 phase-3b cell, `rl_env` `ddcb7816` vs `1b1e5cdf`) **and a behavioural
endpoint**, not a depth mean; cap 6 is predicted flat by the saturated
dose-response and the 0.399 m catch floor. Artifact: `logs/p59/p2_report.py`
exits **0** (the arm check matches the `[supply] direct profile` row) ->
`p2_report.txt`. Pins unchanged (`rl_env.py` `1b1e5cdf` / `tasks.py` `8ad8ddc8` /
`fruits.py` `c7461d41`); no `configs/` change. Evidence
`logs/p59/{PREREG_P2,P2_RESULTS}.md`, `p2/`, `p2_report.{py,txt}`; WORKLOG
"P59 P2".

**P59 phase 3 (2026-10-29, `logs/p59/p3/`; **no shipped default change** - and the
same-tree control this paragraph's P2 section names does **not** reopen the cap).**
The control now exists **on cap 5's own tree** (`logs/p59/p3/header.txt` matches
`logs/p59/p2/header.txt` on **14/14** pins, `git diff ee522c1..HEAD -- src configs
scripts` empty): 45 `[bed-sel]` blocks, `window` mean **2.311** (2.07/2.40/2.47),
`==1` **8/45**, `==0` **0/45**, starved **0/42**, `skipped` **24** (7/6/11),
`on_belt` 11.24, wall **34.49 s/pick**, placed **26/45 = 57.8 %** (right
**24/25**, left **2/20**; **17 of the 19 failures are the left `cnp`** class of
`logs/p42/SIM_LIMIT.md`, which the P43 park removes on the right and cannot touch
on the left). On that foot **cap 5 reads 2.533** - **+0.222 against the 0.371 a
95 % separation of two 45-block arms needs** (overlapping CIs [2.041, 2.581] /
[2.280, 2.787]), so it **does not separate**; `==1` 4/45 (Fisher p = 0.353),
0/42 starves. The two cap-4 cells' own spread is **0.067** (2.311 same-tree vs
2.378 cross-tree - the same configuration, **four pins apart**) = **30 % of the
arm effect: a corroborating floor, not the reason the delta fails** (the
threshold is). **The behavioural endpoint still does not differ, and now cannot**:
`window==0` 0/45 = 0/45, `window>=1` 45/45 = 45/45, starved 0/42 = 0/42 and
`sel_gap` the **same support and total** (`{139,140,141}` x 42, max 141 < the
169-tick starve threshold) are all **saturated**, so **no cap 3-6 can satisfy the
reopening criterion** - **cap 6 is retired, not "predicted flat"**. The counters
that do move sit at the same-configuration cell-to-cell spread and attribute to
nothing: `skipped` **24 vs 21** is the same 3 the two cap-4 cells differ by,
`placed` **26 vs 27** is *less* than the cap-4 cells' own 26 vs 28, and `on_belt`
11.24 vs 11.82 is a body count, not a catch metric. **Two phase-2 readings are
downgraded**: "non-worse in 3/3 seeds" is **2/3** against this control (seed 101
draws 0/15 `window==1` to cap 5's 2/15) and "`sel_gap` the identical multiset"
held only against A2 (this control reads `{139:4, 140:32, 141:6}` vs cap 5's
`{139:8, 140:25, 141:9}` - the same **support**, not the same counts). **The
post-profile direct number is 26/45 = 57.8 %** (11/6/9 per seed - a **branch, not
a rate**: the loop conditions on rendered frames) and it is the **post-profile
"pre"** every later direct comparison starts from. Phase 1's four checks are PASS
(`logs/p59/DEMO.md`) and its film **stands** (no cap default moved, so
`PREREG_P2` rule 5 was not triggered). Artifact: `logs/p59/p3_report.py` exits
**0** - it asserts every arm's `[supply] direct profile` row before reading and
the `on_belt` identity on 45/45 blocks -> `p3_report.txt`. Pins: `rl_env.py`
**`1b1e5cdf`**, `tasks.py` `8ad8ddc8`, `fruits.py` `c7461d41`; `configs/*`
untouched, **no reference re-recorded**; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p59/{P3_RESULTS.md,p3/,p3_report.{py,txt},run_p3.sh}`; WORKLOG "P59 P3".

**P60 (2026-10-29, `logs/p60/`; offline + one measurement cell, **no shipped change,
no new lever**): the left-arm deficit is the **closed loaded-slide class at a higher
rate** - not a seat, an occlusion, a trigger object or the lateral offset.** 180
episodes across four post-P58 corpora (two are P59 supply arms, one sits four pins
apart; the class share reproduces in each, left cnp 79-93 % of attempts vs right
0-4 %) read **left 7 placed / 58 carried-not-placed / 4 never-held (n=69)** against
**right 103 / 2 / 6 (n=111)**, and it is not one species (left kiwi 4/25 vs right
kiwi 4/4). The payload-absence proxy is sound: the `place low` row (printed only
when the fingertip floor binds, `tasks.py:12346`; `need` read 82-144 mm on all 110
placed) is present on **0/58 cnps vs 110/110 placed**, p = 6.7e-13; only **5/58**
cnps carry positional evidence (`[bed-fall] held=True`: x ~ 0.00 +- 0.05,
y = -0.15..-0.42, the source-belt side, not the +y bin at `(0.43, +0.50)` - a
feed-tick snapshot, so quote the direction). **The `FRUIT_CARRY_DIAG=1` cell
settles what the census could not**: **19/19** of the left's cnps are
**`seated_then_slid`** on their first escaping leg (always `grasp_lift`) -
`onset_row` p50 **104/160**, `force@onset` p50 **10.06 N [2.44-22.58]** (a one-tick
sample), `contacts@onset` 1 (14) / 2 (5), `clean_slip` p50 **171 mm**,
`force_min = 0.00` + `loss_row` on **17/19**, **`never_seated` 0/19**, and
threshold-insensitive (19/19 at 1 and 2 N, 18/19 at 3 and 5). It is not the offset:
**4 of the 19 sit inside 66 mm**, and the cell's one left placement is at
**|dx| = 117 mm** - outside the "ceiling" the census's n = 7 suggested. The
scripted left reads the same (24/24 lift rows `seated_then_slid`, 4/4 escapes at
onset 93-149, 7.68-18.19 N; its one placement a 20 mm transient, left lane 1/5)
and P43's direct left is 38/38 (context: different supply profile) - so
**`logs/p42/SIM_LIMIT.md`'s closure transfers and "seat it better" stays closed**.
**Read `[carry]` rows by leg**: a `place0` row's `contacts@onset = 0` is the
downstream view of a payload already gone (18/19 here), never the seat. **The
right-arm occluder is closed at 0.000** (the inactive right at `ready` covers 0.000
of a 58 mm disc across the delivered band, sits at the floor of the 53-pose sweep,
and the scorer reproduces P35 to the rounding), so no right park vector exists or is
wanted (`configs/arm_parks.json` untouched). **The delivered x overlaps** (p50
0.274 vs 0.295 m; `x >= 0.30` 28/69 vs 51/111, p = 0.54; the fire-time jaw
reference agrees to 7 mm), so the arm is not at a different part of the band.
**Nothing decouples arm from lane from grade** (`rl_env.py:2516`: grade A -> bin 0
-> left) and **the direct left's signature is the scripted left's**, so the class is
not an interface artefact; why the left reaches it at **47x** the right's rate on the
same pad asset is **not attributable on this interface** (`rl_env.py:2516`:
arm = grade = lane); P61 measures *where* the payload goes - out along the finger
axis, off the distal lip (`logs/p61/P2_RESULTS.md`). **No lever is left unspent**: the record's one
direct carried-class lever, `FRUIT_CLOSE_LOAD_RATE` (R11-B, default off), re-read
**by arm** in its own batch converts the **right** (cnps 28 -> 5) and not the left
(**20 -> 22**, placed 2/24 vs 2/27, p = 1.0) - pre-P41 and pre-park, i.e. exactly
the arm P43's park already fixed. The left's own `grasp` reset pose covers a 58 mm
disc on the decision band (mean **0.592**; fully hidden over along +0.18..+0.28, the
last ~0.8 s of belt travel before the fire) while the right's covers 0.000 -
recorded **open, no measured pathway** (the trigger is geometry-only, the close is
scripted, and the left's pre-close pad error is *better* centred). F3 fired formally
(a 1-2 episode difference against the P59-p3 control, recorded as
instrumentation-or-branch; P4's note keys are the control's) and the diag's own
`guard/events/holds/reseat/relief` counters are 0 on **88/88** rows. Pins:
`rl_env.py` `1b1e5cdf`, `tasks.py` `8ad8ddc8`, `fruits.py` `c7461d41`; `configs/*`
untouched; ckpt `moe_v13s` `61da390a`; `FRUIT_CARRY_DIAG` default off. Evidence
`logs/p60/**`; WORKLOG "P60".

**P61 (2026-10-29, `logs/p61/`; default off, **nothing adopted**): the left's
payload leaves **out along the finger axis, off the pads' distal lip** - not along
the belt - and the follow-up the brief named is a **commanded constant**. The
default-off `[carry]` field `slip_xyz=(x,y,z)mm` (`tasks.py` **`9a5e0459`**, the
payload-minus-pads displacement **at the running maximum**, leg (TCP) frame,
reporting-only under `FRUIT_CARRY_DIAG`, pinned by `scripts/231_p61_slip_selftest.py`
`202b40c7`) holds its identity on **88/88** rows, max `abs(|slip_xyz| -
clean_slip_max)` **0.072 mm** against the print's **0.137 mm** bound; the *frame*
is carried **not** by that identity (a rotation preserves the norm) but by the
held-payload corpus - **right `grasp_lift` 25/26 legs <= 2.3 mm** against the
code's measured 34-88 mm pre/post-step artifact - and by P42's attitude-free
`[seat] drift`, which agrees with the mapped world vector on all three signs. The
cell (3 seeds x 15 picks, `moe_v13s` `61da390a`, the shipped direct profile, no
wedge) reads **left n = 14 in-hand slides**: leg-frame mean unit **(-0.351,
+0.240, +0.905)** = **25.2 deg from the tool axis**, 76.1 deg from the
jaw-opening axis, **48.9 deg from belt -y** (a pure drag's triple is (+0.034,
+0.858, +0.513)); world mean **(+0.623, -0.658, -0.422)** with **belt -y the
largest single component (0.658), y < 0 on 14/14**, but **+x 0.623 and -z 0.422
are predicted by no registered hypothesis** - a **downward, distal, cross-belt
walk**, and only the tool-axis half is **frame-free** (leg z *is* the finger axis
by construction; the world split is a `grasp_quaternion` approximation whose
threat is measured - P42's `tilt` reaches **38.2 deg** on an escape leg against
the 25.2 deg the reading uses). **The motion candidate is refuted** (achieved
`|v|max` **0.987x**, the 1.637x `|a|max` entirely on the loss tick). **The 47x is
not attributable on this interface**: `rl_env.py:2516` makes `active = left if
grade == "A"`, so **arm = grade = lane**; the contrast is unmeasurable on
*escapes* (**right 1 in 27**) but complete on *magnitudes* (**left 18/18 legs >=
11.3 mm vs right 25/26 <= 2.3 mm, zero overlap**), and that one right leg is
**sign-opposite** (world-y **+224.8** upstream, leg y **-0.404**) to what a belt
drag (+0.858) requires - the observation a belt-drag mechanism cannot produce.
**The named next instrument is already measured and is a constant**: the
along-tool seat is `_pad_standoff(True)` = `FRUIT_FINGER_LEN` 0.060 + `PAD_LIFT`
0.010 = **70.0 mm for both arms and every fruit**, P42's `[seat] tool=` reads
**-69.3..-71.7 mm** without separating escape from placed, and both levers that
move it (`FRUIT_GRIP_PLANE_DROP` D2a 4/8 mm; `..._PAD_LIFT_FRAC` 0.15) are
**measured negative** - so the seat family closes on the direction side too and
**no batch was spent on it**. The tactile carries no contact geometry
(`normal_force`/`contact_count`/per-link scalars only), so a contact-patch read is
not buildable. Refs untouched (`8a399626` / `2246f83c`), `configs/*` untouched,
`selfcheck.sh` PASS. Evidence `logs/p61/{PREREG,PREREG_AMENDMENTS,P2_RESULTS}.md`,
`p2_report.{py,txt}`, `p2/`; WORKLOG "P61".

**P62 (2026-10-29, `logs/p62/`; default off, **nothing adopted**): the left is
**already commanded the top-down attitude** - the gap is that it cannot **hold**
it, and the resulting 26-29 deg tilt *is* the belt-aligned projection that feeds
the slip.** Phase 1 computed the attitude family from
`configs/waypoints_oriented.json` (`q[w,x,y,z]` order verified through
`_grasp_quat` -> `hold_quaternion` -> `quaternion_error`): the tool axis is
**(+0.8543, -0.5132, -0.0819)** with a **belt (-y) projection of +0.5132**, and
re-projecting P61's measured slip gives **0.9045** against its published
**0.905** - the same frame. **The world-z yaw family is infeasible, monotonically
measured**: yaw +15.5/21/31/46.5/62 deg gives projections 0.266/0.161/**0.000**/
-0.266/-0.513 against IK residuals **10.6/13.6/19.9/48.9/118.0 mm**, j2 margins
0.182 -> 0.001 rad, and pad-to-belt clearance **+20.2 -> +3.0 -> -14.2 mm** - i.e.
the left's station reach is **azimuth-limited**, so no yaw removes the projection
without removing the station (the same constraint `motion.py` records from the
other side). **Rolls about the tool axis cannot change it** (a rotation fixes its
own axis: delta 0.0e+00). The one attitude that reaches projection **0.000** *and*
solves is the harness **T0** (`[+0.0, -0.7071, +0.7071, +0.0]`, fingers straight
down, jaws 90 deg across the belt): **2/3** solves at the control's own residual
(**6.0/5.8** vs 5.9/5.7 mm), a **0.8 deg** attitude error, **+15..26 mm more** pad
clearance, and **100.7 deg away from the right's** attitude - but with a j3 margin
of **+0.007 rad** and **32.8 mm** at the x = 0.398 cliff (control 8.3).
**Phase 2 then found the knob is a no-op: `configs/waypoints.json`'s left grasp is
already `mirror_across_xz(top_down_quaternion("x"))` - bit-identical to T0 - and
`_run_impl` discards `_grasp_quat` before the descent (the OpenArm hand skips the
only `solve_to` that reads it)**, so the armed override prints `file_same=1
hold_same=1` and moves the achieved belt projection by **-0.0018 / +0.0001**
against the pre-registered 0.05 gate (the right's own noise floor is **0.0675 /
0.0174**, 37x/174x larger). **The finding that matters**: the left is *commanded*
T0 but **achieves 26.3-28.7 deg of tilt (+0.32..+0.36 belt projection)** on every
carry leg, so the residual is **the attitude the arm can hold at this station, not
the attitude it is told to hold** - which is the mechanism P61 measured and the
owner's hypothesis confirmed. The remaining levers are the **re-solved grasp seed**
(T0 solves from the shipped seed, j3 +0.007 rad) and the **hold stiffness**, each
needing its own pre-registration; the commanded-attitude family is exhausted. The
scripted line is untouched by construction and **proven**: `accept.sh` with all
knobs unset is **377/377 identical** to `logs/p41/p2/accept_profile.log` +
`fingerprint: matches` (6/10, the recorded branch). Pins: `tasks.py` **`fe11910a`**,
`rl_env.py` **`921972a3`**, `scripts/232_p62_grasp_selftest.py` **`e1f86725`**;
`configs/*` untouched (`8a399626` / `2246f83c` / `0ea08ebb` / `d81c6f1c`), no
reference re-recorded; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p62/{CANDIDATES.md,IK_PROBE.txt,PREREG_P2.md,P2_RESULTS.md,p2/}`; WORKLOG
"P62".

**P63 (2026-10-29, `logs/p63/`; default off, **nothing adopted**): the 26-29 deg is
an **arm-common hold/IK residual**, and the **arm-specific part is its azimuth -
along the belt on the left, across it on the right.** The default-off `[carry]`
field `hold_drift=<deg>` (`tasks.py` **`1d27566c`**, `2*acos(|dot(hold_quaternion,
tcp_quat)|)`, pinned by `scripts/233_p63_attitude_selftest.py`) reads on **87/87**
rows (0/45 `grasp_lift` legs are `(no-hold)`; the 42 `(no-hold)` rows are exactly
the **place** legs). The cell (3 seeds x 15, both arms): the left's **failing** legs
carry a median drift of **24.6 deg** (n = 11, 22.4-29.4) while the command is T0
(projection **0.0000**, verified three ways, the independent `[attitude] tilt`
agreeing to <= 4.6 deg on 9/9 legs), so **the command is right and the arm cannot
hold it**; the command path is **closed by construction** (`tasks.py:3488` is gated
on `FRUIT_CARRY_HOLD_QUAT`, unset here). **But the magnitude does not split the
class**: the right places **29/30** `grasp_lift` legs at a median drift of **25.8
deg** (20.9-52.3), the same distribution as the left's failing legs (Spearman
-0.36 left / +0.20 right / -0.15 pooled). **What is arm-specific is the azimuth,
and it is sign-consistent**: the left's achieved tool axis is **downstream on 3/3**
legs (tool_y -0.326..-0.366, **77 % of the tilt on the belt axis**) against the
right's **0/6** (3 upstream, 3 across; median share 0.23) - so the ~25 deg lands
**along** the belt on the left, which is the +/-0.513 the P61 slip was projected
onto. **The chain is closed at every link**: command T0 -> an arm-common ~25 deg
tracking residual -> belt-aligned azimuth on the left -> the drag walks the payload
out along the tool axis (P61) -> the `cnp` class at 47x. **The lever this hands on
is a pre-compensated command** (command T0 rotated by the residual's inverse so the
*achieved* attitude sits at projection ~0, with no arm/kinematics change), and it
needs its own pre-registration. Pins: `tasks.py` **`1d27566c`**, `rl_env.py`
(metadata-only `TASKS_MD5` follow), `scripts/233_p63_attitude_selftest.py`;
`configs/*` untouched, no reference re-recorded. Evidence
`logs/p63/{PREREG.md,P2_RESULTS.md,p2_report.{py,txt},p2/}`; WORKLOG "P63".

**P64 (2026-10-29, `logs/p64/`; default off, **nothing adopted**; **its own
headline was retracted by its screen**): the pre-compensated command was
**inadmissible**, and the corrected finding is that **the lift - not the station -
creates the drift.** The live site is real and it is **`arm.hold_quaternion`**
(not P62's inert `_grasp_quat`): the never-stop catch installs the top-down hold
before the hover and `grasp_lift` **inherits** it (the `_carry` clear is `name !=
"grasp_lift"`), so writing it at the lift's start moves the achieved attitude. The
drift derived from 7 left `grasp_lift` legs is `axis (-0.7564, -0.6541, 0)`,
`angle 26.798 deg`; commanding its inverse (`q_cmd = [+0.01675, -0.68786,
+0.68786, +0.23113]`, command projection **-0.3410**) moved the achieved projection
the wrong way (+0.35 -> **+0.673 median, tilt 47.0 deg**, `hold_drift` 54.9-107.4,
the loaded slide starting **60 ticks vs the control's 104.5**, left **1/16** vs
2/15). **The screen then showed the command was never admissible**: P62's own probe
reads `q_cmd` at **0/3 solves, residual 42.6-72.9 mm (7-12x tolerance), joint
margin 0.000/-0.000 at j6-j7** and a **28.9 mm pad-height difference across the 98 mm
jaw** (`jaw_z = +0.2949`) - so *"the response is inverted"* is an **inadmissible
command, not a mechanism**, and that reading is withdrawn. The two reachable
directions were screened instead: **`q_drift (x) q_T0` (+0.341) solves 3/3**
(better conditioned than T0's 2/3 at `+0.007 @j3`) but carries the same 28.2-28.6 mm
jaw twist and **is the attitude already achieved**; the `waypoints_oriented` left
quaternion (+0.513) is **exactly the shipped control**. **The new by-product is the
finding that matters**: at the station the static solve tracks its command to
**<= 1 deg at both projection 0 (T0: 0.77 deg) and +0.35 (`q_drift`: 0.78-0.93
deg)**, while the failing **carry** legs read **24.6 deg** - so **the drift is
created in the lift**, not by the station's reach, and `hold_quaternion`
pre-compensation has **no station-level target in either sign**. The two-point
"never" claim is withdrawn with it (the slope was not identifiable, P64's own
prereg §6). What is *not* yet measured: why the lift drifts when the station
tracks (`control.py:423` `max_step` and `:494`'s hard joint clip are the named
suspects), and the pads' line (the jaw axis was never printed; `tasks.py:3237`'s
`rot[:,1]` is free). Prior citations corrected: `logs/p58/GEOMETRY.md` prices the
**station y** for the *catchable-segment* question (R10), **not** a general station
NO-GO. Pins: `tasks.py` **`7a8a163a`**, `rl_env.py` **`7c137553`**,
`scripts/234_p64_precomp_selftest.py`; `configs/*` untouched, no reference
re-recorded. Evidence `logs/p64/{SCREEN.md,ik_screen.*,PREREG_P2.md,P2_RESULTS.md,p1/,p2/}`;
WORKLOG "P64".

**P65 (2026-10-29, `logs/p65/`; default off, **nothing adopted**): the two IK
suspects for the lift's ~25 deg drift are **measured out**, and the drift's cause
is **still open**. The instrument (`q_margin=<rad>@jN/t<tick>`,
`q_cmd_margin=`, `q_step_max=`, `jaw_z=`, `drift_on=` on the `[carry]` row,
reporting-only under `FRUIT_CARRY_DIAG`, 44/44 `grasp_lift` legs carrying all five
fields, pinned by `scripts/235_p65_lift_selftest.py`). **`max_step` is refuted by
measurement**: the largest per-tick command step on any leg is **0.0300 rad**
against the **0.5 rad** `FRUIT_IK_MAX_STEP` cap (**6 %**, never binding). **The
joint-limit clip is refuted by discrimination**: the measured margin is **0.000 rad
on 86/86 legs** (the left's 20 lifts, the right's 24 lifts **and all 42 place
legs**), so "a joint at its limit" is a **standing condition of this workspace**,
not a lift-specific cause - and on the left's 18 failing legs the drift's onset
(median tick **106 of ~160, 65 %** of the leg) **precedes** the tick of the leg's
smallest margin by a median of **-41 ticks** (inside the registered +-20 on only
3/18). **The pads' line points the other way**: at the lift's first tick both arms
are flat (|jaw_z| 0.0084 left / 0.0104 right) and over the leg the **right** twists
more (max 0.371 vs the left's 0.239) yet places **23/24** - so the left does not
tip its pads more. **What the phase adds is a discrimination, not a cause**: the
joint saturation is real but arm-common and pre-dates the drift, so the ~25 deg
remains **unexplained** at the code level measured so far. The class counts are the
P63 shape at a moved branch (left 1/18/1, right 23/0/2 against P63's 2/11/2 and
29/0/1; attempt split 20/25 vs 15/30, so F3 = instrumentation-or-branch). Named and
**not** measured: the payload-induced wrist deflection (a load path, not a command),
`ik_step`'s `gain` term, and how often the hold is re-applied. Pins:
`tasks.py` **`309e5a38`**, `rl_env.py` **`a10e753a`** (`TASKS_MD5` follow),
`scripts/235_p65_lift_selftest.py`; `control.py`
**untouched**, `configs/*` untouched, no reference re-recorded. Evidence
`logs/p65/{PREREG.md,P2_RESULTS.md,p2_report.{py,txt},p2/}`; WORKLOG "P65".

**P66 (2026-10-30, `logs/p66/`; **nothing adopted - and a flip that the phase-3
lane made early was REVERTED** when its gate failed): the left's 25 deg carry
rotation is a **height** problem, and lowering the lift's end fixes most of the
left.** `FRUIT_LIFT_DZ` (`direct` + `left` only; it shifts the `grasp_lift`
target height above the shipped `belt_top + 0.28` base, `+0.08` = the shipped
0.36) **defaults to `+0.08`, i.e. the shipped lift**: the phase-3 lane had flipped
the default to the 0.20 rung (`-0.08`) as part of its adoption package, and P66 P4
**reverted it** (`LIFT_DZ_DIRECT_DEFAULT` back to `+0.08`, the `236` pins updated)
because gate (a) below **failed** - the rung is opt-in. Measured (explicit rungs,
so the table is unaffected by the flip) moves the left's `drift_end` **23.8-25.7 -> 9.7 ->
0.7 deg** over the ladder 0.36/0.28/0.20 and the left's placed count
**1/34 -> 1/18 -> 10/16** (phase 2, 3 seeds interleaved); the **N=5** rung batch
(`logs/p66/p3/`, seeds 77/101/202/303/404) reads **control 0/25 (0 %), C24 12/30
(40.0 %), C20 14/25 (56.0 %)** with `drift_end` **25.1 / 3.4 / 0.7** - the control
is **0 in every seed** and each treatment beats it in **5/5** (the run-level sign
test's ceiling, p = 0.031; Fisher ~2e-4 for C24), while **the two rungs are not
separable** (40.0 vs 56.0 %, Fisher p ~ 0.28) so **0.24 is the economical one**
(same class, half the place cost) and 0.20 reads the deeper mediator.
**The mechanism is settled by three independent instruments**: the mediator has
zero overlap; the achieved position error collapses with it (`res_end` 80.6 ->
33.7 -> 13.3 mm); and the **static sweep** (`logs/p66/STATION_SWEEP.md`) predicts
it with no payload, no controller and no profile - `T0` at `belt_top + 0.36` is
**24.27-60.00 deg off with `margin +0.000` on 25/25 cells** (0/75 of the delivered
band passes the 0.05 rad margin clause at any x/y/depth, while the shipped `C0`
passes 31/75), so P63's live 24.6 deg **is** the static number and the drift was
never a controller defect. **Gate (a) is measured and FAILED; gate (b) is structural but not flat**:
(a) the **place-transit clearance: MEASURED AND FAILED at the +33 mm floor.**
With the reduction fixed to the rail-crossing form (`clr_x` at the crossing,
`clr_win` over the transfer window; `logs/p66/P4_RESULTS.md`, one seed, 2 runs,
`p4_report.py --check` PASS), the **0.20 m rung enters the rail's footprint level
with the rail top (window minimum `+0 mm`, tick 333) and crosses the centreline at
`+5 mm`** against the shipped rung's own left leg at **`+30 / +29 mm`** - **no held
leg goes negative in either arm (0/16)**, so there is **no contact**, but the rung
**spends 25 of the 30 mm** the shipped lift had. **The rung ladder cannot buy it
back**: the crossing sits at 82.5 % of the place leg's `y` span, so
`dz_crossing = 0.175 x dz_lift` and the 0.24 rung buys **+7 mm**, not +40 - only
the **transfer height** is 1:1 with the crossing, and the lift lever does not touch
it. **The re-shape is therefore named, not guessed**: keep the low lift (the
attitude holds) and re-establish the crossing height on the place leg's first
segment (a transfer-height change, 1:1 with the crossing, its own registration); (b) the **right-arm no-op** is structural (`resolve_lift_dz` emits only
`{"left": dz}`; `lift_dz_for` returns `None` for the right) but reads
**100 / 97.8 / 88.0 %** across the arms, i.e. inside its own branch spread
(88.9-95.8 % in phase 2) rather than cleanly flat. **The residual is not the
lift**: the remaining left `cnp`s are **place-leg** losses (P66 phase 2: 6/16 at
0.20, `clean_slip` 833-931 mm, tilt 75-91 deg, `tool_y +0.65..+0.70`) - the place
leg reinstates the belt-aligned attitude by reach and the lift's height cannot
touch it, and the **control has no loaded left place legs at all**
(`contacts@onset = 0`), so that class's baseline is the right arm's. **Nothing was
re-recorded** (the knob is direct-scoped; the scripted line never constructs
`SortingRLEnv`, so `configs/motion_reference*.json` `8a399626`/`2246f83c` stand);
**every pre-P66 direct number is a 0.36-lift number and the default IS that
height again** (the rungs are opt-in; compose with `FRUIT_ARM_PARK=ready` for the
pre-P43, `FRUIT_POLICY_TRIGGER_ACQ=0` for the pre-P54 and the P58 burst profile for
the pre-P58 baselines); the hybrid canary has **no path** to the knob. Also
recorded: the **finger-tip identity holds** (`S` 84.902 -> `F1` 80.902 mm =
`4*cos(0)` on all four links, <0.001 mm) but at the descent's vertical fingers it
buys **4.00 mm** of clearance, i.e. 4.4-10 % of the 40-90 mm descent shortfall -
the pad lane stays closed on P39's measurement and on scale; P30-C's 24-45 mm
stays owner-gated. Pins: `tasks.py` **`40e196e8`**, `rl_env.py` **`3fab4733`**,
`scripts/236_p66_lift_selftest.py`; `configs/*` untouched. Evidence
`logs/p66/{STATION_SWEEP.md,COLLIDER_READ.md,P2_RESULTS.md,DEVIATION.md,P3_RESULTS.md,p2/,p3/}`;
WORKLOG "P66".

**P66 P4/P67/P68 (2026-10-30, `logs/p66/p4/`, `logs/p67/`, `logs/p68/`; **nothing
adopted**): the lift-height lever fixes the *carry* class, and **every shippable
form trades it for the place leg's closed class - the two meet, and no net gain
ships today.** The rail-crossing gate is **measured and failed** by the lift-only
form: the 0.20 rung enters the output rail's footprint level with its top
(window min `+0 mm`, t333) and crosses the centreline at **+5 mm** against the
**+33 mm** floor (shipped `+30/+29`; no contact, 0/16 legs negative, but 25 of the
30 mm spent), and **the rung ladder cannot buy it back** (`dz_cross = 0.175 x
dz_lift`; only the transfer height is 1:1). The re-shape (`FRUIT_LIFT_CLIMB`, a
prepended vertical waypoint at the place leg's start; derived `0.18 m` from
`z_cross = transfer - 0.175*(transfer - lift_end - climb)` and re-derived by
`scripts/237_p67_climb_selftest.py`) **clears the crossing** (`+51/+50, +37/+37,
+33/+33, +54/+53, +36/+35`, median +37, worst +33) with the attitude held
(`drift_end` 1.1 deg) - **but drops the payload on 3 of 8 climbed place legs**
(`clean_slip` 0.92-1.00 m, onset 113-152 = the climb's exit; the W8-B loaded
slide, the leg runs with no wrist hold), and `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0`
makes it **worse** (**0/18** against the pair's 3/18; the payload is gone before the
crossing, `clr -216..-218`). The full trade: shipped **0/25** / low lift **14/25**
(crossing +5 mm) / low lift + climb **3/18** (crossing +33..+54) / + the hold
**0/18**. **So the lift's height explains and fixes the carry rotation, and the
place transfer - `SIM_LIMIT.md`'s loaded slide - is what charges for it.** The
remaining levers are the two `SIM_LIMIT.md` sanctions (**a new pad asset** -
P30-C's 24-45 mm stays owner-gated - or **a real-jaw clamp-force anchor**) or a
**workstation/transfer change** (a lower output rail or a shorter transit, both
references re-recorded); **a recollection/retrain is not indicated** (the policy is
not where the loss is). **Nothing was re-recorded** and **nothing is flipped**:
`FRUIT_LIFT_DZ` defaults to `+0.08` (the shipped 0.36; the phase-3 lane's premature
flip to `-0.08` was **reverted** at P4 when gate (a) failed, the `236` pins updated
and a smoke confirming `dz=+0.0800(default) -> belt_top + 0.3600`), and
`FRUIT_LIFT_CLIMB` is default off. Selfcheck PASS; the acceptance is
**6/10 + `fingerprint: matches`** with **377/377** `[fruit]` lines identical to
`logs/p66/p2/accept_noharm.log`. Pins: `tasks.py` **`e5168578`**, `rl_env.py` **`d88c3729`**
(the `TASKS_MD5` follow), `scripts/237_p67_climb_selftest.py`; `configs/*`
untouched. Evidence
`logs/p66/P4_RESULTS.md`, `logs/p67/{RESULTS.md,p67_report.*,A,B,A2,B2_77.log}`,
`logs/p68/{RESULTS.md,pop2/}`; WORKLOG "P66"/"P67"/"P68".

**P69 (2026-10-30/31, `logs/p69/`, default off, **nothing adopted**): the pad-asset
lane closes **by contact geometry**, and the rail-crossing floor - the project's
+33 mm convention - is **measured at `(+7, +14] mm`, so the low lift's crossing is a
real contact on ~40 % of its legs but does not cost the placement (5/5).** Phase A
(the pad asset): the authored boxes go **84.902 -> 80.902 / 60.902 / 49.902 / 39.902
mm** at `0 / -4 / -24 / -35 / -45 mm`, the distal plane rises by
`|delta|*cos(theta)` (identity to **9.7e-7 mm**) and the proximal plane does not
move; **the authorized magnitude cannot grip** - at the shipped aim
(standoff 0.070 m) the plates at -24/-35/-45 sit **+13.5/+24.5/+34.5 mm above the
fruit's equator** and close **without touching any of the 8 pool classes** (closest
+2.6 mm; +0.3 mm even under D2a's -8 mm seat), so the admissible band is
**+3.5..-7.9 mm** (patch intact) / **-13.1 mm** (any contact) and the authorized
magnitudes are **1.8-3.4x past the last that touches**; what a cut would buy is
**descent +24/35/45 mm unconsumed** (the tip already clears by 3.5-24.5 mm and the
residual is a **jaw-plane** 8.1-10.3 mm), **carry +21.8/31.8/40.9 mm = the lip lost
1:1**, and **rail +0.0 mm** (`clr` is a payload clearance), so the whole band is
**4.1-10.9 %** (intact) / **6.0-16.0 %** (any contact) of the 104-276 mm walk; the
one probe is categorical (`C` grasped, lift +0.2894, force 10.00 N; `-24 mm`
lift 0.0000, force 0.00, `sep_end` 32.3 vs 70.6 mm, with `end=8.1 mm` and
`belt_margin=+37.4 mm` identical in both arms) and the **matched pair is a null**
(shorten by `d` and lower the aim by `d` leaves the lip *and* the belt clearance
unchanged, 4/4). Reopen = a **real-jaw clamp-force anchor** or a **new pad asset**,
not another magnitude. Phase B (the workstation) ranks the levers by
crossing-gain: **the inner rail 1.00** (the obstacle moves 1:1), a **place-only
transfer raise 0.825**, a **place `y` shift 0.264**, and **the shipped transfer
lift excluded** (read at both sites, `tasks.py:3269`/`:3308`). **G0 then measured
the floor** (scripted runs, no code): the payload touches at **`clr <= +7 mm`** and
not at **`>= +14`** (15 legs at `>= +14` read **2.6-5.7 m/s2** and 0.0-0.1 mm slip;
5 legs at `-2..+7` read **14.9-32.7 m/s2**, **27-76 mm** of displacement, `sep_end`
97.5-98.3 = the pads at their open stop - **the populations do not overlap, a 2.6x
gap**), so `-1 mm` is a **contact, not a graze** and P66's "non-contacting graze" is
falsified; **the low lift straddles the boundary** (+3..+17 crossing: 3 of 5 legs at
or below the band) - **but 5/5 of its contacting legs still placed.** So the
**cheapest honest package is the low lift + a floor re-signed at the measured
boundary** (0 h, 0 references, 0 stores, the contact accepted and documented on
~40 % of the crossing legs), while a contact-free crossing needs **~+11 mm** of dose
(`FRUIT_OUTPUT_RAIL_HEIGHT 0.05 -> 0.039`, 24 of the 35 mm of lip kept) at a
**binary** blast radius (any rail value moves the scene branch, **both** references
and **every** store) - the 34 mm flush is over-dosed and its flush shelf is the
ledge class's worst case. Nothing adopted; the low lift, the climb and the rail are
all opt-in/default. Pins: `tasks.py` `e5168578`, `conveyor.py` `b0d95a08`, `assets.py`
`61baf52b`, `rl_env.py` `d88c3729`; `configs/motion_reference.json` `8a399626`,
`..._twoline.json` `2246f83c`, `..._patch.json` `7b028049`, `..._twoline_bed.json`
`dcd19758`; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p69/{A_PREREG,B_PREREG,G0_RESULTS}.md`, `tip_geometry.{py,txt}`,
`collider_*.log` + JSONs, `probe_{C,T}.log`, `g0/t0{25,35,45,50,80}.log`; the
delivery page `docs/LEFT_ARM.md` + the README block + the `项目总结报告.md` section.

**P71 (2026-10-31, `logs/p71/`): the adoption package - the output belts' side
rails are gone and the low direct lift is the shipped default; the left's carry
class converts, and the crossing clears the surface that remains (median +35 mm)
while failing the +33 clause *at the rail top* on 0/10 legs, as it must, because
that surface no longer exists.** Two flips, both the measured values:
**`FRUIT_OUTPUT_RAILS` default `both` -> `none`** (`assets.py`; `=both`
restores) and **`FRUIT_LIFT_DZ`'s direct default `+0.08` -> `-0.08`**
(`rl_env.LIFT_DZ_DIRECT_DEFAULT`, i.e. 0.20 m; `=+0.08` restores the 0.36 m):
the rail is **1:1** with the crossing and the height only **0.175:1** and it
costs placements (`logs/p70/RESULTS.md`), while the height is the only measured
fix for the left's 25 deg carry rotation (`logs/p66/P3_RESULTS.md`) - so P66 P4's
reverted rung ships now that its gate's *obstacle* is gone (P67/P68 measured the
re-shape lane closed: the climb clears the crossing and drops 8/16 payloads).
`236`/`238` re-pinned (the rung is the default; the rails' env-read
`default_factory` reads `none`, `=both` restores, an unset config reads exactly
like an explicit `none`), selfcheck PASS.

**The scripted line.** The two arms are same-batch and same-tree and the
**control restores the pre-P71 geometry explicitly** (`RAILS=both`): acceptance
**6/10, 377 `[fruit]` lines, `fingerprint: matches`, and 377/377 byte-identical
to the pre-P71 archive `logs/p66/p2/accept_noharm.log`** - so the tree is inert
with the old scene, and the treatment's move is the flip's. The treatment (the
new default) reads **6/9 = 67 % (one slot starved), 346 `[fruit]` lines** (344 +
two new `output belt rails ... authors 0/2` build prints) with the fingerprint
**moved**: first difference is the print, then a **release y 0.595 -> 0.603 (8
mm)** at stripped line 121, 171/326 lines identical at the same index - the
scene's collider set moving the solver ordering (P30-A's precedent), and every
report-only clearance row shifts by exactly the rail's **+35 mm**. Motion is
identical in both arms (worst `|v|max` 0.1100 against 0.160-0.161, lurch 0.017
against 0.291), the FAIL is the standing rate floor. The **two-line** reads
**8/10 (left 4/5, right 4/5, 9.8 s/attempt) with `190` PASS + `matches`** as the
control, **7/10 (4/5, 3/5, 9.2 s/attempt) with `190` PASS after its re-record**
(the reference moved on legs 3/4/5/7/8/10 by 1-3 ticks); the two are different
attractors (no rate claim) and the ctrl's own tightest place leg reads
**`+32 mm output rail`** against the treat's `+63..+101 mm output belt`.

**The direct line** (the P66 phase-3 cell verbatim, seeds 77/101/202 x 15,
interleaved, `moe_v13s` `61da390a`, `FRUIT_MOTION_REPORT=1` on both arms): the
flip is proven in-log (`dz=-0.0800(default) -> 1.3700 m` vs `+0.0800(explicit) ->
1.5300 m`). **Left placed 4/20 -> 10/17** (one-sided Fisher p = 0.018), **left
loaded-slide legs 15 -> 7** (p = 0.039), overall 26/45 -> 32/45 (p = 0.135);
per seed 2/8->4/5, 2/6->2/6, 0/6->4/6 (2/3 improved, 1 tie). **The right's
placed count is unchanged (22 in both)**, its 3 extra attempts in the treat arm
all `fruit fell off the line` (kiwi 6.3 x2, strawberry 4.0 - never grasped, the
recorded supply tail, already in `logs/p66/p3/C20_77.log`), i.e. a cadence
artefact of the left's extra placements, not a new class. The treat's surviving
6 loaded slides sit at `loss_row` 103-150 (held through the transit, lost in the
place leg) against the control's mostly `loss_row` 1-4 (never seated). **The
crossing, against the surface that remains** (belt top; `logs/p71/p71_report.txt`):
held **left `clr` +14..+50, median +35, 8/10 >= +33** (`clr_win` +10..+45,
median +30.5, 4/10) against the ctrl's **+24..+45, 2/4** at *its* rail top; the **right is
22/22 in both** (+69..+138 vs +36..+58). At the rail top the package reads
**0/10** - the payload passes 35 mm *below* where the rail top was, which is
exactly P66 P4's `+5 / +0` and P70 D0's `+7..+17`, so **the clause as written can
never be met by a lower lift; only the obstacle's removal makes the crossing
physically safe**, and it is: held-leg `|a|max` **0.31-8.69** against G0's
measured contact population **14.9-32.7 m/s²** (max held slip 20.3 mm). The
P70 D0/D1 pair - the **rails isolated** at the low lift, all-A, seed 77 -
reads **6/15 -> 10/15 left placed** and **6 -> 3 loaded slides**. Both motion
references were **re-recorded from this batch's shipped-scenario runs**:
`configs/motion_reference.json` `8a399626` -> **`8952c320`** (from the 6/9
treatment; 9 legs now, so a pre-P71 10-attempt log needs the archive
`logs/p71/motion_reference_single_pre_p71.json`) and
`..._twoline.json` `2246f83c` -> **`eb697f23`** (from the 7/10 run; archive
`logs/p71/motion_reference_twoline_pre_p71.json`); `189_w7a_chain.sh` not run.
**Re-baseline: every pre-P71 number is a `both`-rails + 0.36 m-lift number** -
restore with `FRUIT_OUTPUT_RAILS=both` (all paths) **and** `FRUIT_LIFT_DZ=+0.08`
(direct only), composed with the pre-P43/P54/P58 restores. The **hybrid canary
inherits the rail flip** (it builds its own `SceneConfig`) and **not** the lift
flip (it never constructs `SortingRLEnv`): it was **not re-run** - a smoke owed,
not a measurement made. Residuals: the +33 clause has **no contact boundary in
the new frame** (G0's is at the rail top; the named instrument is a
`clr_edge` sample at `|y| = 0.425`); the ledge class stays **untested, not
zero** (the G2 fixture was again not run, no release in either batch lands in
`0.400-0.425`); the belt height stays 1.35 by P70; the scenes' collider set has
**no manifest field** (the direct lift does), so stores must not be mixed
across P71. Pins: `assets.py` **`e9fd74`**, `rl_env.py` **`cb686f5`**,
`tasks.py` `7c00e5`, `conveyor.py` `fb2c58`; `236` **`e6547e`**, `238`
**`2ccceb`**; ckpt `moe_v13s` `61da390a`. Evidence `logs/p71/RESULTS.md`,
`{header,twoline/,direct/,p71_report.txt,run_p71.sh,accept_diff.py}`; WORKLOG
"P71".

**P72 (2026-10-31, `logs/p72/`; **one** shipped change - the `scene` manifest
block - plus the corner instrument and the canary's owed smoke; no default
moved): the canary is inside its spread, the crossing is
measured at the surface that remains, and the new-frame floor is a
**bracket**.** (1) **The hybrid canary smoke** (`SKIP_SELFCHECK=1
scripts/accept_policy.sh`, the interface of record, `moe_v12`, the pre-v9 fixed
supply) reads **8/10 = 80 % PASS** with **2 grip losses** (`fruit did not follow
the gripper`), 0 grasped-not-placed and **no reason outside the recorded
baseline** - the **top of the 5-8/10 spread**, so one draw, not a rate. It
**does** inherit the rail flip (its build print reads `FRUIT_OUTPUT_RAILS=none
authors 0/2 (inner y=+0.4125 REMOVED)`) and **cannot** see the lift flip (no
`[grasp] lift_dz:`/`[rl] env ready` row); both failures are pick-side grip
losses, upstream of the output line, so **the rail flip is not implicated**.
(2) **`clr_edge`/`clr_edge_min`** on the `[carry]` row (reporting only, same
`FRUIT_CARRY_DIAG` gate, inside `if guard_armed:`, **no new read** - the
`(clearance, where, i)` triple the leg already has): the **first** tick the
payload's `|y|` reaches the output slab's **own** inboard edge and the minimum
over that band, through the existing `_clearance_field`. **The threshold is
0.425 m, not the 0.400 m surface switch**: `_payload_clearance` switches at the
literal 0.40, which is the **removed inner rail's inner face** - the rail box
spanned 0.400..0.425 with its outer face flush with the slab (`assets
output_rail_keep`'s own docstring), so the band 0.400-0.425 is **inboard of the
surface** and the plane charge there is conservative (the `clr_win = -6 mm` leg
that placed with 0.4 mm slip). Derived in `tasks._output_belt_edge_y` =
`|output_belt_y| - size[1]/2`, pinned by the new **`239`** leg (which also
executes the body on stub configs and asserts no rail constant in it) and run by
`selfcheck.sh` as "P72 clr_edge + scene". **Read on one direct run** (seed 77,
15 episodes, the P66/P71 cell verbatim): **`clr_edge` n=10, min +26, median
+77.5, max +109 mm; `clr_edge_min` min +26, median +77.5, max +104; `<= 0` on
0/10**, every value `@obelt`, every held leg's `|a|max` **<= 4.49** (G0's
contact floor is 14.9) and no slip above 0.1 mm. The draw is right-heavy (8
held right / **2 left**, the left being the arm the package targets), the
left's corner sits **+4..+5 mm above its centreline sample** while the right's
is flat, and on the leg P70 and P72 share (ep0: same `clr=+33@t329`, 430 ticks)
P70's hand estimate `edge~+37` reads **+38** measured. (3) **The boundary:
`clr_edge > 0`, and it is a bracket, not a calibrated floor.** With
`output_rail_keep = (False, False)` the rail branch of `_payload_clearance` is
never entered, so the only surface a transit can clip is the slab - its top
plane (1.35) **and** its inboard edge (0.425) - and contact requires the
payload's lowest point below the plane **while over the slab**, i.e.
`clr_edge <= 0`. The record's only sub-zero *plane* sample is P70 D1 ep8's
**`clr = -1 mm @obelt / t247`**, taken 25 mm inboard of the surface, with **no
contact signature** (`|a|max` 0.98, `sep_end` 69.9 mm, slip 0.4 mm) against
G0's measured contact population of **14.9-32.7 m/s²**; the **+33 convention was
calibrated against a raised rail top and has no counterpart surface now**. **No
dose ladder was spent and none can close a gap**: `z_cross = f*z_transfer +
(1-f)*z_lift_end` with `f = 0.825` (0.85 at the edge), the transfer follows the
belt **1:1** while the lift end is anchored to the **main** belt, so
`d clr/d(lift) = +0.175` and `d clr/d(belt top) = -0.175` (0.15 at the edge) -
the lift lever buys 17.5 % of its travel at the crossing and the belt-height
lever spends the 40 mm under-slab audit for +7 mm (P66 P4 / P70, both negative
on the count). (4) **The `scene` provenance block** - `assets.scene_provenance(
cfg, lift_dz=None, lift_dz_defaulted=False)`, pure config arithmetic, the one
builder **both** manifest writers call (the P41 `physics` rule):
`output_rails` + the resolved `rail_keep` pair, `rail_height` / `rail_proud` /
`rail_inset`, `output_belt.{top_z,y,size,inboard_edge_y}`, and
`lift = {dz, defaulted}` on the direct env / **`null`** on a scripted shard (no
lift rung there). Shipped: `none`, proud 0.035, inset 0.015, top 1.35, edge
0.425, `dz.left -0.08 defaulted`. **Metadata only** (nothing reads it; both
callers wrap it in `try/except`); a store **without** the key predates P72
(`arm_park.defaulted`'s convention), and the collector's `write_manifest` was
exercised end-to-end under the simulator python (`manifest_probe.log`:
`none` → both false, `=both` → both true, `lift` null in both), while the direct
env's own manifest from the phase's run carries the block live. **Re-pins the
work forced** (each test's meaning kept): `236`'s tracker-init list / its
`inf` assertions (the line grew `edge_y`), its print-containment check (a
character budget → the file's own `indented_body_contains`), its "one
construction site" count (now scoped to the `PickAndPlaceTask(` call, because
the `scene` call also passes `lift_dz=`), and `238`'s read census, which
**declared** the new consumer `assets.py:scene_provenance`. `rl_env.py`'s
`TASKS_MD5` follows (`7c00e555` -> **`f61323f2`**, metadata only). No `configs/`
edit, no default change, both references untouched (`8952c320` / `eb697f23`),
`selfcheck.sh` PASS. Pins: `tasks.py` **`f61323f2`**, `assets.py`
**`540406fa`**, `rl_env.py` **`92a25c8e`**, `scripts/40_collect_demos.py`
**`86b3d6ba`**, `scripts/239_p72_clr_edge_selftest.py` **`c3027c4f`**; ckpt
`moe_v13s` `61da390a`. Evidence `logs/p72/{RESULTS.md,p72_report.py,
p72_report.txt,p72_scope.py,p72_scope.txt,manifest_probe.py,
manifest_probe.log,canary_rails_none.log,direct/treat_77.log}`; WORKLOG "P72".

**P73 (2026-10-31, `logs/p73/`; default off, **nothing adopted**): the place
transfer's **height is not a lever** on the left's place-leg loaded slide, and the
rotation is **not the actuator** - the hypothesis fails on its own second link and
its first link has the **wrong sign**.** The registered screen
(`PREREG.md` md5 **`81b70bb3`**, pinned before any run) raised
`FRUIT_OPENARM_TRANSFER_LIFT` 0.08 -> 0.14 -> 0.20 (**C / T1 / T2**, the
P66-phase-3 cell verbatim, seed 77, 15 picks, `moe_v13s` `61da390a`, one claim
each; the conditional `SLOW` arm was run because the registered rule B trigger
fired). **On the direct line the knob is place-only on the left**: P71's
`FRUIT_LIFT_DZ` override takes the `grasp_lift` site (`tasks.py:3261-3263`
bypasses the env read), so only `jaw_target("place*")` moves - but the **right's
lift end moves with it** (its `lift_dz_for` is `None`), so the right is read as
"no new class", never as "unchanged". **The class is flat to the leg: 1 / 1 / 1**
loaded slides (1 of 5, 1 of 4, 1 of 5 left place legs; 995 / 983 / 887 mm), with
**`cnp` 2 / 1 / 1** and the acquisition class 2 / 0 / 0. **The mechanism moves
monotonically the other way**: the achieved place-leg rotation `tilt_end`
**78.7 -> 93.8 -> 105.2 deg** (+26.5) and `t45` **313 -> 303 -> 299** ticks, so a
higher transfer *demands more* wrist rotation, not less (falsifier **A does not
fire**); with the rotation moving 26.5 deg and the count flat, falsifier **B
fires**. **The causal order is visibly wrong**: in **8 of 8** payload losses the
onset row is **before** the leg's 45-deg crossing (onsets 4, 133, 103, 136, 3, 4,
157, 265 against `t45` 313-561) - the payload leaves at **1-41 %** of the leg at a
tilt **below 45 deg**, while the 90-105 deg sweep happens at **73-79 %**, i.e.
*after* the failure. **Not inertial either**: the slowed place leg
(`FRUIT_SPEED_PLACE=0.20`) reads **4 slides in 8 legs** against C's 1 in 5, with
the rotation starting at the *same fraction* of the leg (73-78 % vs 73-79 %) but
**+211 ticks = +1.76 s of absolute dwell at near-top-down** - so the class tracks
**time spent hanging in a top-down pinch under lateral load**, and the P44
speed-up is the direction with a measured contrast (its cost stays the closed grip
class, P44/P46). **The escape's signature**: `contacts@onset` **1**, `force@onset`
7.9-11.2 N (the pinch's own 9.8 N), then `fmin 0.00` and the jaws end **closed**
at 42-53 mm (the lift-leg form ends at the **98 mm** open stop) - a **clean
single-sided exit**, neither a force deficit nor a pry. **What the lever does
buy, as predicted**: `clr` **34 -> 88 -> 142.5 mm** and `clr_edge` **38 -> 94 ->
151.5** (+54 / +108.5 against PREREG P1's +49 / +99, so P69-B's 0.825:1 is
confirmed on a second axis; no leg negative), at **+4.5 / +7.0 % episode ticks**
(the descent +41 / +90 ticks; the *leg* total only +22 / +17 because the transit
shrank - **P2 partially missed, P3 missed informatively**: the endpoint was
predicted to stay 85-95 deg and went to 105.2, which is *why* A does not fire).
**The right reaches a median 107.3 deg (max 109.7) and slips 0.0-0.1 mm on 10 of
10 legs** - the strongest single argument that the rotation is not the cause;
right placed 7/8 -> 10/11 -> 10/10, no new class (P5). **No landing regression**:
1 `did not land` per T arm vs C's 2, no `fell off` row, `need` 248 mm against the
300 mm `FRUIT_PLACE_LOW_MAX_DROP` ceiling. **The instrument is the reason the
negative is readable**: the pre-existing per-leg read (`[attitude]`) is printed
once at the leg's end and reads 80.8-94.6 deg on **both** the lost and the placed
legs of the shipped corpus, so a screen using it alone would have concluded "the
height does not move the rotation" - and been **wrong**. The default-off
`[carry]` fields `tilt0`/`tilt_end`/`tilt_max`/`t45`/`t75`/`tilt_rate`
(`tasks.py` **`adcfd348`**, inside the existing `if guard_armed:` block,
**pure arithmetic on `rot_now`** - no new articulation read) make the schedule
visible; pinned by `scripts/240_p73_tilt_selftest.py`, `235` re-pinned for the
inserted fields. **Named consequence**: do not spend another transfer rung,
another rotation lever (`FRUIT_GRASP_LEFT_TOPDOWN`/P64's pre-compensation act on a
link measured off the failure's path), or a *slower* place leg; the residual is
the closed `SIM_LIMIT.md` loaded slide on a leg that carries the payload top-down
for ~0.5 m, so the levers that touch it are the ones `SIM_LIMIT.md` sanctions (a
new pad asset, a real-jaw clamp-force anchor) or a workstation move that shortens
that transit at top-down (`FRUIT_PLACE_INNER_SHIFT` is already measured negative,
P3). **Provenance gap named, not fixed**: the manifest records `lift_dz`,
`lift_climb`, `scene`, `physics` but **not** the transfer height - a store under a
different value would be indistinguishable, so the field must go into
`assets.scene_provenance` before any recollection uses the knob. No-harm:
`accept.sh` **6/9 + `fingerprint: matches`** with its **346/346 `[fruit]` lines
byte-identical** to `logs/p71/accept_rails_none.log` (the instrument is inert on
the scripted path), `configs/` untouched (`8952c320` / `eb697f23`, no re-record),
`selfcheck.sh` PASS (the new leg included). Pins: `tasks.py` **`adcfd348`**,
`rl_env.py` **`157e6d`** (the `TASKS_MD5` metadata-only follow),
`scripts/235_p65_lift_selftest.py` **`bdcbb4`**, `scripts/240_p73_tilt_selftest.py`
**`28cd1f`**; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p73/{PREREG.md,PREREG.md5,P1_RESULTS.md,header.txt,p0_census.py,
p0_census.txt,p1_report.py,p1_report.txt,run_p73.sh,batch_s77.out,
batch_slow.out,direct/,smoke_T1.log,accept_noharm.log,accept_noharm.driver}`;
WORKLOG "P73".

**P74 (2026-10-31, `logs/p74/`; nothing adopted, no default change, **no `src/`
or `configs/` edit**): the place profile's **speed does not move the left's
place-leg loaded slide**, and the **`clean_slip_max > 800 mm` threshold is not
speed-invariant** — so the class's rate is flat over a **2.6x** dwell range and
is **stochastic given the pinch**. The knob is **`FRUIT_SPEED_PLACE=0.52`** (the
P44 **S1** cell, the mirror of the `=0.20` arm P73 inferred the mechanism from;
it supplies the **default** of `FRUIT_DYNAMIC_PLACE_VMAX` read at
`tasks.py:3853` inside `elif self._dynamic_capture_active:`, which the direct
presentation arms — and it is **not direct-scoped**, the same site runs on the
scripted dynamic line, which is why P44 could measure it there). The manipulation
gate (`logs/p74/p1_report.py --check`) passes **every clause on all three seeds**:
`|v|cmd` **0.343 -> 0.509** on the left place legs, the per-leg tick count
matching `motion.jerk_limited` at the printed distance to **<= 1 % on 33/33
legs**, **S/C ticks 0.676-0.678** on the distance-matched pairs (predicted 0.673),
and the `place low` descent in its ±20 % band. Cell: the P66-phase-3 / P73
scenario verbatim, `moe_v13s` `61da390a`, 15 picks, one claim per run, **seeds
77/101/202** — and the expansion is what saved the phase: **seed 77 read 2/4 ->
1/6 in the predicted direction and fired the registered rule, seed 101 read 4/7
-> 4/5 and seed 202 2/8 -> 2/3**, the opposite way at both. Pooled left place
legs: the registered primary **`> 800 mm` 7/19 = 37 % -> 3/14 = 21 %**
(Fisher **p = 0.455**) while the **mechanism count** (`clean_slip_max > 100 mm`,
a payload that left the pinch) is **8/19 = 42 % -> 7/14 = 50 %** (**p = 0.733**),
left placed 11/20 -> 6/15 (p = 0.5), the **failure ledger identical in count**
(left `cnp` 8 vs 8, left `never-grasped` 1 vs 1, right 2 vs 2, `did not land`
8 vs 8, `fell off` 0 vs 0, blow-ups 0 vs 0) and the **right flat** (23/25 vs
28/30 placed, **0 loaded slides in both**, its place legs also shorten, 356 ->
258 ticks). **The primary fell for a measurement reason, and that is the
phase's transferable finding**: after the escape the reported slip is
`rate x (ticks - loss_row)`, the rate rises **3.13-3.25 -> 3.93-4.00 mm/tick
(+25 %)** with the pads' speed and the remaining leg falls **-38 %**, so events
migrate from the `> 800` band into `100-800` (S draws **4 near-misses at 659.6 /
740.9 / 798.8 / 799.1 mm** against C's one at 617.1). **Quote the escape count,
not the threshold, for any speed change**; the threshold stays usable for
height/rotation/retiming, where the remaining leg is constant (P73's own
793.3 mm "held" leg was already named a payload loss). **The dwell is not the
actuator**: with P73's slow arm the rate is **50 % (680-tick legs) / 42 %
(405) / 50 % (262)** across a 2.6x range, so P73's `4/8` is a draw of the same
~45 % rate and its "time-accumulating loaded creep" reading is **withdrawn** —
what survives is its positive half (the escape's **onset precedes the wrist's
45-deg crossing on 15/15** losses here too, `loss_row/ticks` 0.01-0.44 against
`t45/ticks` 0.71-0.86; the right reaches the same attitude and slips 0.0-0.1 mm
on 28/28 place legs). The escape's **signature is speed-invariant** (both arms
`force_min = 0.00 N` on every loss, `contacts@onset` 1 on 6/8 and 6/7, jaws
ending at the **17.3-53.7 mm** closed form, never the 98 mm open stop; one S leg
is a `27.09 N` / `sep@onset 98.2 mm` squeeze-out at the open stop rather than a
slip, and both arms carry exactly one `0.00 N / contacts 0` never-held leg). `clr`/`clr_edge`
are **leg-determined, not profile-determined**: on distance-matched legs they
read **-1 / -3 / -9 mm** (65/61 cm), and the arm-median drop is leg mix (S drew a
53 cm leg at +4 mm; C's own four 58 cm legs span 18-49 mm); the **achieved**
rotation lags ~4 % of the leg later at 0.46 m/s (`t45/ticks` 0.75-0.86 vs
0.71-0.81, `tilt_end` 61-79 vs 68-88 deg) while the commanded path is identical.
The speed's **time** saving is real and reproducible (left place leg **405 ->
262 ticks = -35 %**, episode median **-5..-7 %**, `|a|cmd` 0.30 -> 0.72 with the
`place` cone still **0.84-0.90x** of budget) but it is a **throughput** candidate,
not a class fix, and P44/P46 already priced that direction's placement cost; the
`place low` descent also loses **5 %** because the faster leg ends **12 mm** lower
in achieved z (the release re-measures its clearance, so the landing class is
unchanged). One S `cnp` is **not** the class — a **place-reach/landing shortfall**
with the payload held (`clean_slip 0.0`, `clr +23 mm`, `res_end 50.2 mm` against
29-31 on healthy legs) — and one note text is new to the batch on a
**`grasped=False`** leg (`fruit left the pick station during the close
(27454 mm)`, a recycle artifact upstream of any carry leg). **Verdict: falsifier
F1 fires -> no adoption, no phase 2**; the named consequence is that **this
class needs >= 3 seeds before a direction is called** (a 15-pick single-seed cell
produced a 15-point false positive), and that with P73 the place-leg lever space
is exhausted for **pose, rotation and clock** — what remains is
`logs/p42/SIM_LIMIT.md`'s two sanctions (a new pad asset, a real-jaw clamp-force
anchor) or a workstation change that shortens the lateral transit at top-down.
No motion reference moved (`8952c320` / `eb697f23` stand — nothing was flipped,
so no re-record was owed). Provenance: the batch spans two commits
(`75e980a` seed 77, `90f31a6` seeds 101/202) whose diff is **two `logs/` files**
and **no `src/`/`configs/`/`scripts/` change**. Pins: `tasks.py` `adcfd348`,
`rl_env.py` `157e6d85`, the batch's `header.txt` `0d246950`,
`PREREG.md` **`1c3546de`**, ckpt `moe_v13s` `61da390a`; evidence
`logs/p74/{PREREG.md,PREREG.md5,P1_RESULTS.md,header.txt,p1_report.py,
p1_report.txt,p1_aggregate.py,p1_aggregate.txt,run_p74.sh,batch_s77.out,
batch_s101_202.out,direct/}`; WORKLOG "P74".

**P75 (2026-10-31, `logs/p75/`; **one default-off diagnostic, nothing adopted, no
default moved, `configs/*` untouched**): the place leg's escape is an
**expulsion - a wedge/pry runaway**, not a slide at constant `sep` and not a
command transient, and the trace settles it at one tick.** The instrument is
`FRUIT_PLACE_ONSET_TRACE=<ticks>` (`tasks.py`, **0 = off = the shipped path**;
`place*` legs only, one `[place-trace]` row per tick, post-step, inside the
existing W8-B carry block **which it also arms** so it is self-sufficient):
`t`, `|d|` and `d=(x,y,z)` (the hand-frame displacement and its components, P61's
axis), `sep` (measured) beside `gap` (commanded), `f=(f0,f1)`, `n`, `tcp_err`,
`v_cmd`, `v_ach` and this tick's `q_margin=…@jN`. **No articulation read is
added** (`rot_now`/`pads`/`_tcp_pos`/`_marg`/`gap_command` are the block's own;
the two additions are `jaw_separation()` and one tactile set per traced tick);
pinned by `scripts/241_p75_place_trace_selftest.py` (selfcheck leg) and read by
`scripts/242_p75_classify.py`, whose **rule was pinned before the runs**
(`logs/p75/METHOD.md`, `PREREG.md5` **`479bb896`**): `t_d` = the first `|d| >= 2 mm`
(the diag's own trigger), `t_sep`/`t_f` = the first measured-separation drop
`>= 1 mm` / the strong face below half its leg-start value, `t_err` = the first
`tcp_err` 20 mm above the leg's **own steady state** (median of the last third),
`t_cmd` = `t_err` or a `|Δv_cmd| >= 0.10 m/s` step; **(c)** if `t_cmd <= t_d - 2`,
else **(a)** if `t_sep`/`t_f <= t_d`, else **(b)**. Two registered cells
(`A_77`, `A_101`: 15 picks, seed 77/101, `moe_v13s` `61da390a`, the
P66-phase-3/P71-phase-2/P73/P74 cell verbatim, `FRUIT_CARRY_DIAG=1` +
`FRUIT_MOTION_REPORT=1`) trace **26 place legs** (12 left) at 60 ticks and draw
**6 left place-leg escapes** (832.5/833.6/806.8 mm in s77, 895.7/844.8/851.9 in
s101; **all `cnp`**, and `escape <=> cnp` on **12/12** left legs), plus one
**declared extension** (`B_101_t200`, 8 of 15 episodes, `=200` ticks) that
resolves one of them end-to-end. **The finding is the ordering**: that leg holds
the payload with `|d| = 0.0 mm for 110 ticks` and `sep` constant to the print;
at **t=111** `|d|` reads 0.3 mm while `f` falls 5.03 → 4.11 N and `sep` starts
**rising**; at **t=112** `f = 0.00 N`, `n = 0`, `sep +1.0 mm`; at **t=121** the
pads sit at their **98.1 mm mechanical open stop** with `|d| = 12.6 mm` **while
the force servo closes the command 68.7 → 66.7 mm** - i.e. the payload is pried
out through a widening gap, so **(b) is refuted** (`sep` does not hold) and the
`SIM_LIMIT.md` sentence "the pads hold and the payload slides" is *not* this
interface's mechanism (**it refines, not contradicts, the class**: the pry is
force-sensitive - P41's ladder deleted `sep_max` 98.5 → 43.5 → 31.2 at 10/30/60 N
- while the class did not convert, so the residue is pad **face geometry**, the
`SIM_LIMIT` new-pad-asset sanction, not more force). **(c) is refuted by
measurement**: **0 of 26** traced legs show a `|Δv_cmd| >= 0.10 m/s` step, and at
the escape tick every commanded quantity is smooth (`v_cmd` 0.202 → 0.205 → 0.207
→ 0.210 over t = 110..113; `tcp_err` on a straight +0.6 mm/tick ramp) while a
**held** leg carries the same ramp (25.1 → 46+ mm) and holds - so **there is no
profile-continuity lever at the leg boundary** and none is registered. **The
wedge fires at two sites, one mechanism**: 2 of 6 escapes at the **end of the
lift** (the place leg then *starts* with `n = 1`, one face at **0.00 N**, and
`sep - gap` **+25.3/+28.5 mm** against **+8.5..+14.7** on the 23 normal legs - no
overlap - and their preceding lift legs are the three that slipped 7.9-11.3 mm,
though that second separator is **not clean** (eight of the other nine left lifts
read 0.0-3.2 mm and the ninth 7.5 mm, and *its* place leg still started normal -
so the first-tick pinch state is the discriminator, not the lift's slip), and 4 of 6 **inside** the place leg at
`onset_row` **105 / 140 / 142 / 159** with the leg starting clean (`n=2`,
4.28-4.95 / 4.89-5.07 N) and **`|d| = 0.0 mm for the whole 60-tick window** -
which is itself the answer to "the first ~40 ticks": for that family the payload
does not begin to go there. **Named next (post-hoc, not a result)**:
the 4 late escapes' *preceding lift* ended **27.6-58.9 mm behind its command**
(`res_end`) against **8.6-14.6 mm** on the 8 held-or-pried legs (no overlap,
n = 12 left legs, 4-vs-8) - "does the lift leg's tracking deficit predict the
place leg's escape?" is a phase that needs its own PREREG, and it does **not**
fit a "the catch-up feeds the slip" story (`|d|` is 0.0 mm through the fastest
part of the catch-up, t = 1-60, and the wedge fires at t = 111 with `v_cmd`
already 0.20 m/s). Deviations, all recorded in `METHOD.md`: **A1** withdrew a
`v_ach >= 1.5*v_cmd + 0.05` clause (it fires on every *clean* leg - `v_ach`
0.095-0.099 m/s while `v_cmd` is 0.000, the arm closing the previous leg's
19.4 mm residual); **A2** took the force reference from the **stronger** face at
t = 0; **A3** labels a leg that is **already** single-sided with
`sep - gap >= 20 mm` at t = 0 **`a0`** (inherited expulsion) because on such a
leg `sep` *cannot* fall further - it is at the stop - so the literal in-window
test would fall through to (b) (pre-A3 seed 77 read `a=2 b=1`, the b being that
artefact; the **mechanism** verdict is unchanged); **A4** marks the 200-tick cell
as an extension, not a registered cell, and no rate comes from any of them (the
trace arms the carry block and adds two reads per traced tick - the 60-tick
cells ran at **35.5/35.3 s/pick**, inside the untraced P74 range 29.7-35.4, and
at 200 ticks the cost is **~3.5 min/episode**, so 200 is a batch-lane setting).
No-harm: `scripts/accept.sh` with the knob unset reads **6/9,
`fingerprint: matches`, and its 346 `[fruit]` lines are byte-identical to
`logs/p73/accept_noharm.log`** (both streams md5 **`d0079a23`**; the exit=1 is
the standing rate floor, this tree's branch since P32); `scripts/selfcheck.sh`
**PASS, 0 failures**. Pins: `tasks.py` **`303d025d`**, `rl_env.py` (the
`TASKS_MD5` metadata-only follow), `scripts/241_p75_place_trace_selftest.py`
**`14be55ea`**, `scripts/242_p75_classify.py` **`4f41d983`**,
`logs/p75/p75_report.py`; `configs/*` untouched (`8952c320` / `eb697f23`), no
reference re-recorded, ckpt `moe_v13s` `61da390a`. Evidence
`logs/p75/{METHOD.md,PREREG.md5,RESULTS.md,header.txt,p75_report.py,
p75_report.txt,direct/,smoke.log,accept_noharm.log}`; WORKLOG "P75".

**P76 (2026-10-31, `logs/p76/`; **nothing adopted, no default changed, `configs/*`
untouched**): the pad pry needs **> 30 N**, the payload **> 45 N**, and the
smallest fruit is **not crushed at 60 N** on the direct line - so P76's two
numbers are `60 N` (pry deleted) and "no crush at 60 N", and P41's "60 N crushes
a 3.7 cm strawberry" is a **seating** event, not a force threshold.** One
default-off `[carry]` field group (`dia=`, `sep_max=…@t<tick>`, `gap@sep_max=`,
`sep_min=`, `fmax=`, reporting only inside the existing `if guard_armed:` block,
`FRUIT_CARRY_DIAG`-gated) exists because `sep@loss` is sampled at the loss while
P75 measured the pads reaching their **98.1 mm stop 9 ticks later**. The ladder is
`FRUIT_FINGER_MAXFORCE` **10 (unset) / 15 / 20 / 30 N**, seeds **77 and 101**, one
claim per cell, the P66-phase-3/P71-phase-2/P73/P74/P75 scenario verbatim, plus
**two declared extension cells** (45 and 60 N) registered before they ran
(`PREREG.md` `62567d8b` → A1 `0397a929` → A2 `5e51d95b` → A3 `af7da4e5` → A4
`1991c5fa`). **The manipulation check is two independent confirmations per rung**
(the build print's `maxForce=<cap>/0.0N` and the **live articulation** read-back
`[drive] … joint1/joint2=15.00/0.00 N`) with the behavioural third leg the held-leg
`force_min` median **9.6-9.7 / 14.2-14.7 / 18.2-19.3 / 25.3-29.2 / 39.9 / 53.9 N**
(85-99 % of the cap) - the rung *is* the
delivered force (P41's law), and `F10` is evaluable as the unset path (no
`[drive]` row by construction). **The pry does not stop in 10-30 N**: the pads
reach their stop on **5 / 1 / 2 / 2** legs of 55/54/55/54, and the **same 6.8 cm
pear** (left, seed 77, the phase's cleanest control - only the cap differs) reads
`place0 sep_max` **98.1 / 98.1 / 98.1 / 98.3 mm at 10/15/20/30 N** with
`gap@sep_max` 66.9-69.9 mm, i.e. the pads are **25.7-31.2 mm wider than the
command** at every low rung, exactly P75's wedge - so **30 N does not relieve the
travel limit here**, which is where this interface departs from P41's scripted
ladder (98.5 → 43.5 → 31.2 there). The two thresholds are **separated**:
**the pads' stop is relieved between 30 and 45 N** (45 N: **0/26** legs past
95 mm, corpus max **90.4 mm**) **and the payload is not saved by it** (the same
pear still leaves, **829.5 mm**, force 0.00 N) - only **60 N** gives **0/26 pried**
(corpus max **76.7 mm**) and **0/26 escapes**, with the pear at 75.2-75.8 mm and
**0.0 mm** slip. Retention is **not monotone** (20 N keeps it at 11.0/13.6 mm,
30 N ejects it 96.8 m, 45 N loses it) and every cell is **one draw** - those rows
are a per-instance dose-response, **not a rate**; what is monotone is the pad
travel, which is what the phase asked. **The crush guard reads 0 legs at the
registered C1/C2 in all six cells**: C1 was sharpened **before the extensions** to
the **loss tick** (`sep@loss - dia`, the only tick the payload is provably between
the pads, because a loaded `sep_min` also catches the pads pressing **each
other** after a small fruit has gone - two 3.9 cm strawberry legs at seed 101
read a 148 m / 223 m `clean_slip`, i.e. recycled payloads, with the pads at their
10.0 mm closed limit). The **strawberry** (3.6 cm, the binding class) reads
`sep@loss - dia` **+0.5 mm** at a **36.1 mm** span under a **60.16 N** pinch,
`force_min` 55.40 N, **placed** - and the closest low-rung number is **-14.8 mm**
(one 3.9 cm instance at 15 N, `fmax` 24.26 N, 496 mm) which sits **0.2 mm inside**
the -15 mm rule, so the rule does not fire: that is a **seating** event (the close
landed 24.7 mm inside the fruit) whose depth the cap amplifies, which is why P41's
scripted 60 N crush (pads to 10.0 mm around 37 mm) does **not** reproduce here.
**Counts are reported, never gated** (20/30, 23/30, 24/30, 24/30, 12/15, 13/15
placed; left 6/14 → 6/9 → 7/10 → 7/10 → 4/5 → 6/6; held `force_min` medians
9.58-9.66 / 14.19-14.67 / 18.22-19.27 / 25.32-29.19 / 39.9 / 53.9 N) - a count across rungs **compares attractors**, and the only rate-shaped
claim is per-leg (**0/26 pried at 60 N vs 5/55 at 10 N**). **Deviations, all
pinned before the runs they govern**: **A1** `sep_min` is the **loaded** span (the
unconditional minimum fires on every escape leg - a lost payload lets the servo
close the pads onto nothing, `sep_end` 51.9 mm inside a 68.3 mm fruit; the
discarded pre-A1 cell is kept as `DISCARDED_F10_pre_a1.log`); **A2** the 45/60 N
cells are **declared extensions, not rungs** (P75's A4 convention); **A3** an
escape leg must have had a **pinch** (`fmax > 0` - one leg's `clean_slip_max` is
**308 215 mm** with `fmax = 0.00 N`, a recycled payload, listed separately as
never-held); **A4** the bisection ran because F60 came back clean on **both**
endpoints. **No phase-2 cell is run**: the §5.1 condition is met only at a
**declared extension** (F60), so it licenses a plan - **3 seeds x 15** at 60 N
with the paired carried-class endpoint, the **two-line and scripted no-harm**
(three references and every store re-recorded, the expensive item), and the
**sanction**: the cap is not physical until a real jaw is anchored to it, i.e.
"the sim needs 60 N; a real jaw would have to deliver 60 N" - the owner decides.
No-harm: `accept.sh` **6/9 + `fingerprint: matches`** with its **346 `[fruit]`
lines byte-identical** (stream md5 `d0079a23`) to `logs/p73/accept_noharm.log`
(`logs/p76/accept_noharm_full.log`; the new fields need
`FRUIT_CARRY_DIAG=1`, so they cannot run on the scripted path), `selfcheck.sh`
**PASS, 0 failures** (the new leg). Pins: `tasks.py` **`9d5824ef`**, `rl_env.py`
(the `TASKS_MD5` metadata-only follow), `scripts/243_p76_sep_selftest.py`
**`fc0e738e`**, `scripts/selfcheck.sh` **`84f77dcb`**, `logs/p76/p76_report.py` **`544fc6f2`**;
references **`8952c320` / `eb697f23`** both untouched, no reference re-recorded,
ckpt `moe_v13s` `61da390a`. Evidence
`logs/p76/{PREREG.md,PREREG.md5,RESULTS.md,header.txt,run_p76.sh,p76_report.py,
p76_report.txt,direct/,smoke_a1.log,accept_noharm.log,accept_noharm_full.log}`;
WORKLOG "P76".

**P77 (2026-10-31, `logs/p77/`; **evidence only - nothing adopted, no default
changed, no `src/` or `configs/` edit**): the owner's 3-seed cell at 60 N -
**the count converts, the escape class does not.** The honesty frame first: 60 N
per joint is **jaw-feasible** (a 2F-85-class jaw covers 20-235 N) but it **would
bruise a 3.6 cm berry in reality** and **this sim has no bruise model**, so a
clean read here is about **geometry and retention**, never fruit quality. Arms
**C** = the shipped 10 N (`FRUIT_FINGER_MAXFORCE` unset) and **T** = `=60`,
interleaved by seed (77 C->T, 101 T->C, 202 C->T), **seeds 77/101/202 x 15**, one
claim per cell, the P66-phase-3/P71-phase-2/P73/P74/P75/P76 scenario verbatim,
`moe_v13s` `61da390a`, `PREREG.md` **`d31c3e4a`** pinned before any run. **The
primary: left placed 11/21 -> 17/20** (Fisher **p = 0.043**; **3/3 seeds**
improve by +3/+1/+2, so the run level's one-sided sign p = 0.125 **is its
minimum attainable at N=3 and is quoted as a ceiling**; class-standardised
**0.524 -> 0.927** at C's species mix), **left `cnp` 7 -> 3**, left never-held
3 -> 0, and the **right is not worse** (21/24 -> 22/25, 0 cnp, 0 escapes, no new
reason). The **pairing** is `(seed, arm=left, species, diameter to 0.1 cm)`,
greedy 1:1: only **11 of 21** pair (10 **unpairable** - a fruit the other arm
never drew), both placed 5 / C-only 0 / T-only 6, McNemar **p = 0.031**, and it
is a **descriptor, not the primary**, because the fruit presented is a
post-treatment variable - a same-configuration replay (C_77 against P76's F10_77)
agrees on **2 of 15 episodes and diverges at episode 2**, so no instance-level
pairing exists on this interface. **The pre-registered mechanism bar fails**:
left escape legs (`clean_slip_max > 100 mm`, pinched) fall **7 -> 3** = 43 %, not
<= 1/3 (M1 FAIL), while the pries fall **4/38 -> 1/40** (M2 PASS, 25 %) and the
crush guard stays **0/6 cells** (M3). **The residue is a different mode**:
**2 of the 3** T escapes leave through a **3.4 / 7.9 mm** pad opening (the pads
essentially closed on the fruit - P61's **axial** walk off the distal lip)
against the control's **13.5-39.9 mm** radial pry, and **1 of 40** T legs still
**pries fully** to the 98.1 mm stop (peach 6.2 cm, `fmax` **64.52 N**, 782.9 mm).
Every escape and every pry in **both** arms is a left `place0` leg: the site is
invariant, the mode is not. **P76's single draw does not reproduce**: its
**0/26 pried, 0/26 escaped** at seed 77 becomes **1 pried / 3 escaped of 40 left
legs**, and the same 6.8 cm pear P76 saw held (`place0 sep_max` 75.2, slip 0.0)
**escapes here** (76.2, 834.7 mm) - so 60 N **reduces the class by more than half
and changes its mode; it does not delete it.** **The strawberry** (the binding
class) is held in both arms - C **5/5**, T **6/6 real legs**, `sep_max - dia`
**-0.7..+6.2 mm**, the 3.6 cm fruit at a **36.7 mm** span under **52.6-54.2 N** -
and **no crush leg fires**; the one T_101 strawberry "loss" is the **recycled
payload** artifact (`fmax` **0.00 N**, `clean_slip_max` **160 769 mm**), excluded
by P76 A3 and named, not hidden. **The manipulation check is three-fold per
cell**: build print `maxForce=10.0/60.0`, env derev, **live `[drive]` read-back
60.00/0.00 on both arms**, the manifest's `physics.finger_maxforce` + the
drive-`readback_matches`, and the behavioural **held `force_min` median 9.72 ->
53.41 N** (per seed 9.72/9.96/9.71 against 56.31/53.41/52.08). **The price
(report only, nothing re-recorded)**: at 60 N the scripted acceptance reads
**6/10** against the archive's **6/9**, with the **branch moving at attempt 0**
(60 N places it: lift +0.411 m / 60.05 N; 10 N fails it: +0.138 / 9.98 N),
**378 vs 346 `[fruit]` lines** (md5 `4d89c743` vs `d0079a23`, 57 identical with
the print rows dropped) and **`fingerprint: DIFFERS`** from `8952c320`; the
two-line reads **8/10** at its own 0.60 floor with all ten descents inside budget
and **`190` FAIL on the fingerprint alone** against `eb697f23` - and 2/18 carry
legs still slip >400 mm, of which the shipped-cap P71 two-line has **three of its
own**, so that is not a cap effect. A flip therefore owes **both motion
references, a scripted re-baseline and every store's provenance** - for a class
that shrinks rather than closes. Pins unchanged (env-only phase): `tasks.py`
**`9d5824ef`**, `rl_env.py` `7ca5aa70`, refs **`8952c320` / `eb697f23`**, ckpt
`61da390a`; `scripts/selfcheck.sh` **PASS, 0 failures**. Evidence
`logs/p77/{PREREG.md,PREREG.md5,RESULTS.md,header.txt,run_p77.sh,p77_report.py,
p77_report.txt,direct/,rollouts/,p1_accept_mf60.log,p1_accept_mf60.driver,
p2_twoline_mf60.log,p2_twoline_mf60.gate,selfcheck.log}`; WORKLOG "P77".

**P78 (2026-10-31, `logs/p78/`; **default off, nothing adopted** - one new knob
and its runtime write): the clamp can be **scoped to the site**, the runtime
write works, the containment is total - and the dose reproduces P77's
mechanism without the grasp half, at a count that is a direction, not a rate.**
P77's win was measured on a **global** cap, which is a per-joint drive property
written at build time on **both arms of every presentation** - so a flip moves
the scripted acceptance at attempt 0 and the two-line's fingerprint, and owes
both motion references, a scripted re-baseline and every store. But P77 §2 also
measured the class's **site**: every escape and every pry, in both arms, is a
left `place0` leg. So the lever is a **runtime** cap on one arm's `place*` legs:
`FRUIT_FINGER_MAXFORCE_SCOPE=place-left` (+ `..._SCOPED=<N>`, default 60), the
only token at P78 - **the P79 paragraph below adds `grasp-left` for the pick half,
and the scope dict is now keyed `"<side>:<legs>"` so the two classes cannot
overlap**; an **explicit `FRUIT_FINGER_MAXFORCE` still wins** (the global path
keeps its meaning, the two cannot stack) and **every non-`direct` presentation
resolves `(None, None)` before reading a value** (`rl_env.resolve_finger_cap_scope`,
strict: unknown token / non-number / non-finite / `<= 0` raise). The task takes
it as a caller-owned kwarg and `tasks.finger_cap_scope_for` is the **only** site
resolver (one carry-leg class per key, per side; from P79 one key is `place*` and
the other `grasp_lift`, so neither can arm the other's legs); `_carry`
is now a **wrapper** that raises the left drive's `joint1` cap via
`set_dof_max_efforts` and restores **the cap the leg found** in a **`finally`**
(the leg body is `_carry_leg`; `237`'s locator follows it, assertions unchanged).
**The runtime write is real and proven three ways**: the API is the tensor
backend's `set_dof_max_forces` -> live `joint_effort_limit` + a
`JOINT_DOF_PROPERTIES` notify (the one `scene.apply_finger_maxforce`'s docstring
names as acting on a live view); the per-leg `[drive]` read-back follows
(`10.00 -> 60.00`, readback `60.00`, restore `-> 10.00`); and the **physics**
follows - `place*` **peak** force **29.75 / 44.99 / 56.08 N at caps 30 / 45 / 60**
(99 / 100 / 93 %) against a control of 10.69 N, while **`grasp_lift` stays at
9.10-9.97 N in the same runs** (the pick is untouched by construction *and* by
measurement). **The blast radius with the scope armed is zero**: the scripted
acceptance is **346/346 `[fruit]` lines, md5 `d0079a23` - byte-identical** to
`logs/p76/accept_noharm_full.log` - with `fingerprint: matches` (the only failing
clause is the standing 6/9 rate), the two-line is **7/10 + `190: PASS`** against
`eb697f23`, neither prints a scope row, and **no reference was re-recorded**;
B1/B2 are **import/structure guards** (the scripted entries never construct
`SortingRLEnv`) and the substantive proof is the direct line's own read-back.
**The dose** (seed 77 screen, then three seeds): the screen passed S30 and S60
and the economical rule sent **S30** to seeds 101/202 - where its 6-leg "0
escapes" became 4/32, **P74's lesson again**. Three-seed pooled **C / S30 / S60**:
left placed **10/18 · 12/17 (p = 0.49) · 11/16 (p = 0.50)**, left escapes
**8/36 · 4/32 · 4/31 (both 50 % of C, not <= 1/3)**, left pried **3/36 · 0/32 ·
1/31**, right **25/27 · 22/28 · 25/29**, cycle **1774 · 1804 · 1789**. **No rung
meets its bar** (S30 fails D2 and D4; S60 fails D2 and the per-cell crush guard),
so nothing is adopted - but the **mechanism is P77's without the grasp half**
(pries essentially deleted, escapes halved rather than closed - P77's T was
4/38 -> 1/40 and 7 -> 3 = 43 %) and the **mode migrates**: the control's escapes
are **0/8 axial**, both doses are **2/4 axial** (`sep_max - dia` +2.7 .. +9.9),
i.e. **force removes the radial pry and leaves the axial walk**
(`logs/p42/SIM_LIMIT.md`, P61). The extension's **P5 did not fire**: a
place-leg-only cap that cannot touch the pick still moves the left count in
P77's direction, so the **place leg carries the direction** and only the
magnitude is unresolved. Two negatives are recorded, not smoothed: **S45's
6.8 cm pear pries at a delivered 46.05 N** (`sep_max` 95.6 mm - force reduces,
does not delete), and **the one crush-guard leg is a RIGHT `grasp_lift` at the
shipped 10 N cap** (S60/101, a 3.88 cm strawberry, `sep@loss - dia` **-15.9 mm**,
`grasped=False` - the shipped close's squeeze-out, one event in ten cells, **not
dose-attributable**; it fails the registered per-cell D3/G7 as written). **A
recorded PREREG correction**: `force_min` is a leg *minimum* (a contact
transient), not a clamp read under a leg-scoped cap - it reads 80 / 78 % at
45 / 60 N while the leg *maximum* tracks the cap at 99 / 100 / 93 %; the report
prints both and gates on `fmin >= 75 % AND fmax <= 110 %`. No-harm:
`scripts/selfcheck.sh` **PASS, 0 failures** (new leg `scripts/244_p78_scope_selftest.py`
`aadea2d3`, 45 checks), `TASKS_MD5` metadata-only follow `9d5824ef ->
b1464c43`, `logs/p36/offline_obs_diff.txt` regenerated by the `218` leg (a
generated index, not a claim). Pins: `tasks.py` **`b1464c43`**, `rl_env.py`
**`5c7322d2`**, `scene.py` **`fbd7e2bb`**, `control.py` `9384ff4f`,
`assets.py` `540406fa`, `fruits.py` `c7461d41`, `policy/trigger.py` `b09d3cb2`,
`scripts/selfcheck.sh` `ce338611`, `scripts/237_p67_climb_selftest.py`
`6a6b18bf`, `configs/motion_reference.json` **`8952c320`**, `..._twoline.json`
**`eb697f23`** (both untouched), ckpt `moe_v13s` `61da390a`. Evidence
`logs/p78/{PREREG.md,PREREG.md5,PREREG_EXT.md,PREREG_EXT.md5,RESULTS.md,
header.txt,run_p78.sh,p78_report.py,p78_report.txt,direct/,rollouts/,smoke_60.log,
b1_accept_armed.log,b1_accept_armed.driver,b2_twoline_armed.log,
b2_twoline_armed.gate,p1_driver.log,p32_driver.log,p4_ext_driver.log,
selfcheck.log}`; WORKLOG "P78".

**P79 (2026-10-31, `logs/p79/`, default off, **nothing adopted**): the pick half of
the clamp - `grasp-left` - is a measured **null on the count** and a measured **win on
the leg state**, and neither scoped 60 N arm reproduces P77's global count.** The token
`FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left` arms P78's runtime cap on the left arm's single
`grasp_lift` leg only (keyed `"<side>:<legs>"` -> `{"left:grasp"}`, disjoint from
`{"left:place"}`, so neither token can arm the other's legs), default off, `direct`
only, an explicit `FRUIT_FINGER_MAXFORCE` wins, strict parsing, `_carry`'s `try`/`finally`
restore. **The site proof is exact**: one raise+restore per left lift leg (15/15 at
30 N, 17/17 at 60 N), **zero** rows on any `place*` leg or the right arm across six
armed cells, delivered lift pinch **10.02 -> 30.09 -> 57.48 N** (`fmax` medians; `fmin`
9.75 -> 29.43 -> 49.14) while the **place stays at 10.02/10.05 N** against the control's
10.07, and the manifest's `sites`/`readback_matches` agree in every cell. **The count is
flat at the recorded dose**: left placed **C 11/20 = 0.550 -> G60 9/17 = 0.529**
(Fisher **p = 1.0000**, per-seed **0/-4/+2**), `cnp` **7 = 7**, `never-held` 1 vs 2 (one
episode). **What does move is the lift leg's pinch integrity**: legs that **lose a pad**
**6/20 -> 2/15 (30 N) -> 1/17 (60 N)** (p = 0.0975), `sep_end - gap_start` 10.5 -> 9.2 mm -
i.e. P75's inherited-state mechanism works and the class it should feed does not
convert. **30 N is where the direction is and it is a dose, not a result**: **12/15 =
0.800** (p = 0.163, +3/-1/+1), `cnp` 2, lost-a-face 2, place escapes 2/14, but it misses
the registered `+3` bar and sits **below** P77's dose - and P78's place arm at 30 N read
the same shape (0.706). **The dose is not monotone** (30 N 0.706/0.800 vs 60 N 0.688/0.529),
so at n ~ 15-20 per arm no force above the control's own 10 N is identified as the
actuator. **The register's answer**: the three controls agree tightly (0.524/0.556/0.550,
pooled 32/59 = 0.542) and the two scoped 60 N arms bracket them (pooled 20/33 = 0.606),
while the global arm alone reads 0.85 - and the one leg class the global cap touched that
**no `_carry` token can reach is the close** (`_carry` is only ever called with `place{i}`
and `grasp_lift`), which is also where P77's `never-held` 3 -> 0 must have happened (a
never-held carry leg has `fmax == 0`; no lift-phase force can create contact the close did
not make). **The named next spend is a `close-left` scope at the close's own site** (not a
carry leg, its own registration), not another lift or place dose. **Guards**: right
**21/25 -> 26/30 -> 25/28** (p = 0.69), cycle **1751/1773/1772** ticks, crush guards 0 in
nine cells, and **every one of the batch's 30 strawberry legs was presented to the right
arm** (all grade B/C - the direct env sets arm from grade), so a 60 N pick on a berry is
**not exposed here, not measured safe**. **Blast radius re-proved with the scope armed**:
`accept.sh` **346/346 `[fruit]` lines byte-identical** to `logs/p76/accept_noharm_full.log`
(md5 **`d0079a23`**) + `fingerprint: matches` + **0** scope rows, and the two-line **7/10 +
`190` PASS** against `eb697f23`; no reference re-recorded. One **recorded deviation**
(`PREREG.md` §9 **A1**, pin `0cdfd227` pre-run / `afde5127` amended): the registered
per-cell `place* fmax <= 11.25 N` band is a **transient** test - it fired in 1/6 cells on
an **escaping** leg (12.13 N, `force_min` 0.00, slip 940 mm) at the shipped cap, and `fmax`
exceeds the cap on single legs even at 10 N (this batch's control reads 35.53 N; P78's
79.43/134.29/155.12) - so P3 is gated on the **structural** rows + the pooled force and
the band is reported; **no verdict moves** (P1 fails independently). Pins: `tasks.py`
**`e8dfa6d8`**, `rl_env.py` **`7d26eb5b`** (`TASKS_MD5` metadata-only follow),
`scene.py` **`07d6fdad`**, `scripts/244_p78_scope_selftest.py` **`50fde0fa`** (72 checks),
`scripts/selfcheck.sh` **`dd4bf41a`**; `configs/*` untouched (`8952c320` / `eb697f23`),
ckpt `moe_v13s` `61da390a`. Evidence `logs/p79/{PREREG.md,PREREG.md5,RESULTS.md,
header.txt,header_phase3.txt,batch_driver.log,run_p79.sh,p79_report.py,p79_report.txt,direct/,rollouts/,
smoke_grasp_left_60.log,smoke_site_proof.txt,b1_accept_armed.log,
b1_accept_armed.driver,b2_twoline_armed.log,b2_twoline_armed.gate,selfcheck.log}`;
WORKLOG "P79".

**P80 (2026-11-01, `logs/p80/`; measurement only - nothing adopted, no default changed,
no commit, `configs/` untouched): the cell's throughput on the shipped tree, and the two
levers priced against it - the two-line is a **1.87x sim clock and a 1.02x wall wash**,
the speed union a **cycle-time lever**. Today's cell (shipped single arm, 20
slots, seed 5): **12/19, 15.10 s/attempt, inter-placement interval 26.72 s mean / 36.90 s
p90, 2.25 placed/min on the placement window and 2.08 on the batch span, 25.2 s
wall/pick**; the interval is **bimodal** (17.5-19.6 s between two placements, 35.6-38.2 s
across a failure, i.e. `26.7 = 4.8 idle + 1.45 x 15.1 s attempts`) and **all seven
failures are `cnp`**, left 1/7 vs right 11/12 (not the lateral tail: the failed
`fruit_x` span 0.215-0.365 around a 0.305 placement, and the pick-pose jaw is identical
on every left attempt). Two 10-attempt gate arms prove the branch: **G-S10
`fingerprint: matches` `8952c320` with 346/346 `[fruit]` lines byte-identical to
`logs/p71/accept_rails_none.log`**, and **G-T10 `190: PASS` + `matches` `eb697f23` with
423/423 non-camera lines byte-identical to `logs/p71/twoline/none.log`** (so the P71
two-line record was one draw and today's tree reproduces it). **The two-line, first
measured on the shipped tree**: 16/20, 9.70 s/attempt, interval 10.77 / 18.00 s, **5.57
window / 4.96 batch = 2.48x / 2.38x**, lock-on 3.83 s left / 4.54 s right (19 retry polls
each), idle 18 %/21 %, 44 starved polls and **zero lost slots** - and its per-arm attempt
span **15.0-15.6 s is the single arm's 15.09**, so it *overlaps* attempts rather than
shortening one: **2.38x = 1.88x clock x 1.27x count**, the count half being the
*package* (its own W3 dense-sheet supply `wave=on grades A:0.375,B:0.375,C:0.25` + pure
grade routing) and the left arm's 1/7 -> 9/10. **The seed-6 pair (`S6` + `T6`) keeps the
clock and reverses the count**: 1.88x / **1.87x** clock, count 16 vs 12 then 10 vs 13,
**pooled 26/40 vs 25/38 - equal**, so pooled **sim 1.86x**. **Wall is measured, not
inferred** (`logs/p80/stamp.py` stamps every line through a `tee`): wall/sim **1.38 (S)
vs 2.57 (T) = 1.86x**, so **wall/pick is flat** (1.01x / 1.06x, pooled 1.03x) and the
**wall placed rate is 1.28x then 0.77x = 1.02x pooled**; the 1.86x is the *scheduler's*
per-tick cost, discriminated on the W6-B pair (both lines on the same dense sheet: single
1.25x, two-line 2.32x), not the supply's. **The union** (`FRUIT_SPEED_ALL=1`) **pays on
the clock** (-1.70 s single / -1.00 s two-line, -12 % wall/pick, exactly P44's place
-0.75 / release -0.84 / lift -0.24) **and not on throughput** (interval +4.9 %, window
-4.9 %, batch -12.6 %), its count fall being P51's acquisition class plus the grade draw
(arm-standardised it is +6 pt better, 69.3 % vs 63.2 %). So **a two-line default is a
simulated-time decision (1.87x) and a wash on this machine's wall (1.02x)**, and the union
is a cycle-time lever rather than a throughput lever. **Read rules for this tree from
here: quote both denominators (window and batch) and the wall column; never read a count
difference as the lever's (the closed `cnp` class owns it); and any throughput claim
needs >= 2 seeds** - the two-line's count advantage reversed at seed 6. No `src/` or
`configs/` change; the 20-attempt two-line reference is
`logs/p80/motion_reference_twoline_p80_20.json` and never `configs/`.

**P81 (2026-11-01, `logs/p81/`; measurement only - nothing adopted, no default changed,
no commit, `configs/` untouched).** The two-line's **scheduler** is separated from its
**supply package**: the **net 1.88x clock is the scheduler's own** (1.80x / 1.82x on
the single arm's shipped scattered supply, **96-97 %** of the package-on clock, at both
seeds), while the **feed and the overlap strength are the package's**: without it the
right arm reports no eligible fruit on **93.3 % / 82.0 %** of its polls (package-on
65.5 % / 63.0 %), the mean concurrency falls **1.58 -> 1.30 arms** at seed 5 (1.44 ->
1.42 at seed 6), and the delivered sim window rate falls 5.57 -> 3.08 at seed 5 while
the **count stays a seed draw** (10 vs 16 then 13 vs 10; pooled **23/40 vs 26/40**). The
cell is `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_WAVE=0` at `ATTEMPTS=20`,
seeds 5/6, with the 50/30/20 mix from the **code default** (`balanced = (wave or patch
or bed) and FRUIT_BIARM_TWOLINE == "1"` is False; runtime row `wave=off
grades=A:0.5,B:0.3,C:0.2`, **0** `A:0.375` rows) and **pure routing unchanged**; the
controls are P80's `S20/T20/S6/T6` on the identical tree md5s (no re-runs). **The
registered rule returns D2 (package required)** on its *delivered* clauses - seed 5
interval **19.47 s** vs 12 / 10.77, S-poll **6.30 vs 2.20** polls/attempt, S-idle right
**43 % vs 21 %**; seed 6 S-poll **3.35 vs 1.65** - while its four clock/count clauses
pass at seed 6 and three of four at seed 5: **the net clock is scheduler-only, the
delivered interval/rate is package-required.** Per-seed `s/attempt` 10.10 / 9.90 vs the
single arm's 15.10 / 15.00; clock ratio **1.80x / 1.82x** (control 1.88x / 1.87x);
interval **19.47 / 14.43 s**; sim window **3.08 / 4.16** and batch **2.96 / 3.92**
placed/min vs the single arm's 2.25/2.30 and 2.08/2.27; **wall 1.20 / 1.57 vs 1.51 /
1.63 (pooled 1.38 vs 1.57 = 0.88x)** - on this machine the package-off line is *below*
the single arm on the wall because the two-line pays 2.48-2.51x wall/sim (P80 section 6),
so the sim rate (pooled batch 3.44 vs 2.18 = **1.58x**) is the transferable number.
**The overlap-only read**: mean arms busy 1.30 / 1.42 vs the single arm's 0.83 and the
package-on 1.58 / 1.44; the seed-5 clock keeps 1.80x partly because its failed attempts
are shorter (10.79 s vs the control's 13.35) - holding that fixed the seed-5 clock would
be **~1.55x**. Tp5/Tp6 motion budgets **PASS** (worst `|v|max` 0.137 / 0.121 vs
0.160-0.161, lurch 0.050 / 0.028 vs 0.291, carry cone reported 1.89x / 1.62x);
`190` against P80's 20-attempt reference records **DIFFERS by construction** (the
supply changes the fruit sequence; no reference written, `configs/` untouched
`8952c320` / `eb697f23`); the accept probe is **6/9 + `fingerprint: matches`**; selfcheck
PASS. Pins unchanged from P80's tree: `tasks.py` **`e8dfa6d8`**, `bimanual.py`
`980923a6`, `fruits.py` `c7461d41`, `rl_env.py` `7d26eb5b`, `scene.py` `07d6fdad`,
`assets.py` `540406fa`, `control.py` `9384ff4f`, `conveyor.py` `fb2c58c6`. Evidence
`logs/p81/{PREREG.md,PREREG.md5,RESULTS.md,header.txt,battery_driver.log,
p81_report.py,p81_report.txt,supply_proof.txt,stamp.py,one_run.sh,run_p81.sh,
Tp5.log,Tp5.stamps,Tp5.budgets,Tp5.gate,Tp6.log,Tp6.stamps,Tp6.budgets,Tp6.gate,
accept_noharm.log,accept.gate,selfcheck.log}`; WORKLOG "P81".

**P82 (2026-11-01, `logs/p82/`; one behaviour-neutral optimization behind a
default-off knob, **nothing adopted, no default change, no commit**): the two-line's
61 % harness wall is 51 % physics and **32 % a 5 ms poll timeout** - the poll is
removable, and removing it turns P80's 1.02x wall wash into **1.55x**.** The
question was P80/P81's own: the two-line pays wall/sim **2.57** against the single
arm's 1.38, so its 1.88x simulated clock was 1.02x of wall. The split was measured,
not guessed, with two instruments on **separate profile builds whose `[fruit]` streams
are byte-identical to the record** (that is the admissibility test: a profile that
moves the branch is not a profile of the branch): **I2** = per-round timers at the
arbiter boundary only, never inside `ik_step` (`logs/p82/timers.py` +
`profile_20.py`, 47,795 rounds; R1 = 865/865 vs `logs/p80/T20.log`), and **I1** =
py-spy at 100 Hz with `--idle` (56,473 main-thread samples; R3 = 865/865). Both cost
wall (+1.0 % / +5.9 %) and neither moved a line. **The four hypotheses:**
**H1 holds, and as a *wait*, not as Python** - `TickRelay.schedule`'s own cost is
**0.024 ms/round = 0.2 % of wall**, while `MainBridge.pump`'s fixed 5 ms timeout is
**5.03 ms/round, 99.2 % of them timeouts, ~2.03 rounds per shared tick** (`CoopSession.run`
drives `schedule()` then `pump(0.005)`, and `pump`'s queue only receives *bridged
main-thread jobs* - the tick requests `TickRelay.request` files never reach it);
**H2 (render) is 0.0 %** - `_tick_frame` is 21,544 calls costing **0.059 s** on the
whole batch, because the scripted battery has no `frame_callback` and no recorder
(the *single* arm does pay a render: `update_app(steps=20)` in its pre-pose/feed, **12.7 %
of its wall**, py-spy); its stack inside `step` is **71.3 %** of its wall (and py-spy's
52.5 % vs I2's 51.0 % agree on the two-line's share); **H3 (physics) is the largest
single term and is not removable** - one shared `SimulationManager.step` = one PhysX `simulate(dt)` per
tick, **10.87 ms = 51.0 %**; **H4 (the second arm) is 15.7 %** (the arms' segments,
1.70 ms each, 1.97 per tick, serialized by the single permit). The dead wall is the
same number three ways: `pump` total 240.5 s minus the 78.9 s of segments it covers =
**161.6 s = 32.2 %**, the residual, and a wait histogram that is **one spike at
5.07-5.08 ms**. **The one optimization** (`logs/p82/apply_wake_patch.py`, 12 asserted
anchors; `bimanual.py` `980923a6` -> **`146e6252`**, +87/-10): `MainBridge` gains
`wake_on_request` + a `threading.Event`, `pump` waits on the event instead of the
timeout (the timeout stays as the safety net: a lost wake costs latency, never a
stall), and `TickRelay.register/enter/request/pause/resume/release` call `_notify()` =
`_cv.notify_all()` + `bridge.wake()`. **`schedule`'s own notify is deliberately left
alone** - waking from inside `schedule` makes the next `pump` return without waiting
and spins the driver loop. The knob is **`FRUIT_BIARM_WAKE_ON_REQUEST`, default ON since this phase**
(`=0` restores the pre-P82 timeout), read once per `CoopSession` - the flip is a
**latency fix, not a physics change**, and it shipped on the phase's own evidence
plus a post-flip check: two 4-attempt two-line cells, env unset vs `=0`, read
**85.9 s against 119.0 s of `[fruit]` span (-27.8 %)** with their 179-line
streams **byte-identical** (`p82_report.py --same`), so every recorded wall number
before this phase is a **timeout-path** number and `=0` restores it. **The proof is bit-identity at two seeds
and in four profile configurations**: W1/W2/W3 (seed 5, knob on, with and without the
timers) are **865/865** identical to `T20`, W4 (seed 6) **814/814** to `T6`, the
single-arm cells **710/710** to `S20` and the accept cell **346/346** to
`logs/p71/accept_rails_none.log`; the shared-station scheduler (`bimanual.py`'s other
consumer) **499/499** off-vs-on. **The numbers**: wall **497.2 / 501.1 -> 327.1 /
327.8 s** at seed 5 and **476.8 -> 312.9 s** at seed 6 (**-34.5 %**), wall/sim **2.59
-> 1.69**, wall/pick **25.1 -> 16.4 s**, placed/min wall **1.92 -> 2.93**, with the
count (16/20, 10/20), the sim span (193.3 s) and every per-leg metric unchanged; the
shared-station pair reads **317.6 -> 201.8 s** (2.22 -> 1.41). **The arithmetic**, to
quote in this order: the sim clock is **1.88x** and the lever cannot move it; the
harness factor (wall/sim) was **1.81x** the single arm's, so the wall gain was
`1.88 / 1.81 = 1.03x`; the lever takes it to **1.19x**, so the wall gain is `1.88 /
1.19 = **1.57x**` per pick; the placed **rate** multiplies that by the count, which is
a seed draw and **not** the lever's (pooled placed per attempt **0.650 vs 0.658**),
giving **1.55x pooled** (1.95x at seed 5, 1.18x at seed 6) - **so the two-line now
meets P80's disowned 1.02x bar and the standing 1.25x bar on the wall denominator,
not only on the sim denominator.** What is left (1.19x) is measured and is **not** a
poll: the two arms' control plus the permit handoff, with the shared physics step
(10.65 ms/tick = **75 % of the remaining wall**) the floor no arbiter change can
move. **Read it as a latency win, not a cheaper run**: the idle wall is denser, the
CPU *work* is unchanged (physics 51 -> 75 %, segments 15.7 -> 23.0 % of a shorter
wall) and the loop rate is unchanged (48,021 vs 47,795 rounds - **no spin**); this box
runs the cell at ~3 of 32 cores, so a saturated machine would show much less.
**P80/P81's two-line wall column (1.93 placed/min, 24.9 s/pick) is the *shipped*
behaviour and stays valid for the tree as it stands** - the knob is off - and the
knob-on numbers are the same scenario with the wait removed. **No motion reference is
re-recorded and none is owed** (`8952c320` / `eb697f23` stand: the physics cannot
move), the two-line gate `190` **PASSes** on the knob-on log against P80's own
20-attempt reference, `accept.sh` with the knob **set** reads **6/9 + `fingerprint:
matches`** (the standing rate-only FAIL), and `selfcheck.sh` is **PASS, 0 failures**.
Not measured: a saturated machine, the collector's `run_bimanual` path (it inherits
the knob), a concurrent-arm scheduler (a different design - the single permit exists
because PhysX reads are not thread-safe). Pins: `tasks.py` `e8dfa6d8`,
`bimanual.py` **`146e6252`**, `configs/*` untouched; ckpt `moe_v13s` `61da390a`.
Evidence `logs/p82/{METHOD.md,RESULTS.md,header.txt,timers.py,profile_20.py,
run_pyspy.sh,ps_agg.py,one_run.sh,run_p82.sh,run_p82_stage2.sh,apply_wake_patch.py,
p82_report.py,p82_ab.py}`, the cells `{R1,R2,R3,R4,W0,W1,W2,W3,W4,F0,F1,A1}` with
`.stamps`/`.driver`, `R3/R4.speedscope.json.gz` + `.profile.txt`, `W1.gate`,
`selfcheck.log`; WORKLOG "P82".

**P83 (2026-11-01, `logs/p83/`; default off, **nothing adopted**, no default
change, no commit, `configs/` untouched): the cell pays a full attempt for every
failure, and ending it the tick the payload is provably gone **halves the failed
attempt - by exactly 5.14 s / 617 ticks at both seeds - and the throughput does
not follow**, because the interval's other two terms absorb it.** The knob is
`FRUIT_FAIL_FAST=<mm>` (`tasks.py` `parse_fail_fast`, **unset/0 = off**): one
compare per guarded tick on the W8-B tracker's own `clean_slip_max` (the payload's
displacement in the leg's frame, the number the `[carry]` row already prints)
against the threshold, and on a trip the leg **breaks at that tick** plus the
**two early-exit sites the P7-2b monitor already uses** (the lift boundary, and
the place boundary which is *before* the release/retreat block) through one
predicate `_attempt_ended_early() = _carry_monitor_skip or _fail_fast_trip`. It
adds **no `notes` entry**, so the class is unchanged (`grasped` still comes from
the shipped peak-lift predicate, `placed` stays False → `cnp`); the payload is
recycled by `run()`'s own `finally`; the next pre-pose is the driver's
`go_ready` → `_goto` teleport, the path every shipped failure takes; **no new
exception type**, so the entry script, the collector and the two-line worker
handle it as a `not grasped` return; and the scope is **`scripted` only**
(`_fail_fast_active = threshold > 0 and scripted`), so the direct/policy handover
and the hybrid canary cannot reach it (they keep the P10-C *leg-boundary*
classifier skip, which cannot save the leg's remainder). **The floor is 100 mm and
anything `0 < mm < 100` raises at task construction**: the pre-run corpus census
(`logs/p83/census.py`, 43 scripted logs that already print `[carry]` rows, **249
placed / 165 failed** attempts joined to their own outcome rows) reads the worst
**placed** leg at **76.3 mm** (p99 62.1) and **164/165 failed** at `>= 150 mm`, so
the registered arm is **150 mm** - a 1.97x margin over the worst placed leg - and
**0/249** placed attempts ever reach it. **The A/B** (`ATTEMPTS=20`, shipped
scenario, `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`, one claim per run;
**C5** control replay, **D5/D6** tracker-only, **F5/F6** `=150` + the tracker):
**G1** C5 is **710/710 `[fruit]` lines byte-identical to P80's `S20.log`** (the
off path is inert), **G2** D5 = C5 and D6 = **S6** on **710/710** and **708/708**
physics lines - **the W8-B tracker is run-neutral on the scripted line**, so
`F` vs `C` differs by the abort alone (unlike the link-world-pose reads AGENTS
§2 forbids: `tcp_pose`, `jaw_separation`, `joint_positions` and one tactile set
per tick do not move the branch), **G3** F5/F6's first 57/59 physics lines equal
the control's with the first trip exactly at the boundary, **G4** **15/15 trips**
fire with `force = 0.00 N` *and* `contacts = 0` (and `force_min = 0.00 N`) - the
pads are empty when the displacement reaches 1.97x the worst placed leg - **G5**
**34/34 carry legs of the 17 placed attempts read `ticks = X/X`** (not one
shortened; worst placed-leg `clean_slip` 0.1 / 19.8 mm), **G7** the 20-attempt
motion budgets pass (worst descent `|v|max` 0.110-0.120 against 0.160-0.161, lurch
0.017-0.027 against 0.291; the only `105` FAIL is the standing 0.75 *rate* floor),
**G8** every run accounts and no slot is lost to the abort, and **G6 fails by its
letter only**: one new reason text (`fruit did not follow the gripper`) in each
treatment arm, from **one never-held attempt** (`sep = gap = 22.2 mm` on a 53.8 mm
fruit, `onset_row = 1`, `stored pad centre 415 mm from the measured pads`,
`force servo: gap=22.2 sep=22.2 closed=15.00 trips=38` = the R11-A.1 left
acquisition signature) whose `grasped = False` the **shipped** predicate decides -
and **the seed-6 control carries the same text** (S6/D6 1/19). **The numbers:
the failed attempt's mean span falls 15.157 → 10.013 s (seed 5) and 14.567 →
9.422 s (seed 6) = the same -5.144 s = -617 ticks**, `s/attempt` -2.80 / -2.20 s,
wall/pick -14.6 / -11.5 %; and **the interval gets worse, 26.72 → 35.26 s
(+32.0 %) and 26.12 → 27.38 s (+4.8 %)**, placed/min falls on **both**
denominators (window 2.25 → 1.70 / 2.30 → 2.19; batch 2.08 → 1.68 / 2.27 → 2.08),
`placed/min wall` 1.50 → 1.19 / 1.61 → 1.48, and the count 12 → 6 / 13 → 11.
**The decomposition is the finding**: `interval = attempts/placement × attempt
span + idle`; the span term fell and **attempts/placement rose 1.583 → 2.333
(seed 5) and 1.462 → 1.818 (seed 6)**, with idle 2.81 → 6.56 s at seed 5 (**6
starved slots**) against 4.19 → 4.11 s at seed 6 (**0 starved**) - so the abort
**is** worth -16 / -12 % of the interval *at the control's own failure rate* and
it cannot set that rate. **The seed-5 starvation is a pool state, not a trip
effect**: the post-hoc probe (`logs/p83/probe_bed.sh`, `FRUIT_BED_DIAG=1`,
reproducing F5 exactly - 14 attempts, 6 placed, 7 trips, `sim = 172.8 s`) names
every refusal at those six slots - the only body above the **0.399 m** catch floor
(the peach at 0.626) is **`diverted (max_retries)`**, the apple (0.105) and pear
(0.339) are **inside** the floor and only creep downstream 0.06 m per starved slot,
a strawberry sits on the output conveyor (`x = 1.08`), and the feeder has nothing
to release (`admitted 2 → 0`, `skipped = 85`, `pump_next` within 0.01 s of `t`) -
while the seed-6 arm starves **0/20** with the same saving. The 43 `[bed-fall]`
rows are all at `y = -0.63..-1.41, z ≈ 0.02, held = False`, i.e. P32's
unattended-belt-loss cadence artifact, **not** payloads dropped by the abort.
**Read rules from here**: quote **`placed/min wall`, not `wall/pick`** (a run that
places less divides a much smaller wall by a smaller count: 25.33 → 21.62 s/pick
with 1.50 → 1.19 placed/min); **quote the pair `clean_slip >= 150 mm` *and*
`force = 0.00 N / contacts = 0`** for a trip (the slip alone is a norm); read the
cut off the leg's own row (`[carry] ticks=<trip>/<total>`, `[motion] steps=<trip+1>`);
and treat a count difference as a **branch draw** (pooled 25/38 vs 17/34: two seeds
cannot separate "the re-timed presentation is harder" from "the branch is
harder"). **Verdict: M1/M2 PASS, M3 fails on G6's letter, T1/T2/T3 fail at both
seeds → not adopted; `FRUIT_FAIL_FAST` stays default off.** The named re-entry is a
scenario where the presentation is not the binding term - the **two-line**, whose
scheduler parks an arm on the *other arm* rather than on the belt (P80/P81), where
5.14 s per failure is a duty-cycle gain rather than re-drawn fruit. No motion
reference is re-recorded and none is owed (`8952c320` / `eb697f23` stand: C5 proves
the scripted line does not move); `scripts/selfcheck.sh` **PASS, 0 failures** with
the new leg `scripts/245_p83_failfast_selftest.py` (65 checks: the resolver table,
the 100 mm floor, the single trip site, the attempt-local latch, the `scripted`
scope, the `guard_armed` arming clause, the one-predicate early exit, no `notes`
entry, the restored step cap, the one call site). Pins: `tasks.py` `f1e44af6`,
`rl_env.py` `d786279c` (the metadata-only `TASKS_MD5` follow),
`scripts/245_p83_failfast_selftest.py` `086c6022`, `scripts/selfcheck.sh`
`39b8916f`; `configs/motion_reference.json` `8952c320` and
`..._twoline.json` `eb697f23` both **untouched**; ckpt `moe_v13s` `61da390a`.
Evidence `logs/p83/{PREREG.md,PREREG.md5,RESULTS.md,census.py,census.txt,
p83_report.py,p83_report.txt,run_p83.sh,one_run.sh,probe_bed.sh,battery_driver.log}`,
the cells `{C5,D5,F5,D6,F6}.{log,stamps,driver.log}`, `{C5,F5,F6}.gate`, the probe
`probe_bed.log`, `accept_noharm.log`; WORKLOG "P83".

**P84 (2026-11-01, `logs/p84/`; measurement only - nothing adopted, no default
change, no commit, no `src/` edit, `configs/` untouched): P83's re-entry on the
two-line. The abort is clean there, the line had already spent most of the saving,
and whether the overlap absorbs it flips sign between the two registered seeds.**
P83's named re-entry was a scenario where the presentation is not the binding term -
the two-line, whose scheduler parks an arm on the *other arm*. Cells
(`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, 20 attempts, seeds 5/6, the P80
instrumentation plus **`FRUIT_CARRY_DIAG=1 FRUIT_BIARM_PARK_TRACE=1` on both arms**,
`FRUIT_FAIL_FAST=150` on the treatment only, one claim per run): **D5 16/20,
interval 10.77 s, 2.85 placed/min wall; F5 10/20, 14.39 s, 2.01; D6 10/20, 19.34 s,
1.92; F6 15/20, 12.21 s, 2.83**. **Both controls are the P80 records again**:
`D5` = `logs/p80/T20.log` **865/865** and `D6` = `logs/p80/T6.log` **814/814**
physics `[fruit]` lines, the phase's diag rows dropped - so **the tracker and the
park trace are neutral on this line** and the A/B is the abort alone (P83 had only
proved the tracker neutral on the single arm). **The mechanism transfers, the
arithmetic does not**: 12 trips, **11/12** at `force = 0.00 N` *and* `contacts = 0`
(the 12th is F5's never-held payload, `clean_slip 354.4 mm` on tick 1, and F5's one
letter-failure is `force 9.33 N / contacts 1` at a **measured `sep 9.9 mm` with
`gap = -2.2 mm`** - the pads pressing each other, the payload **138.8 mm above**
them), **45/45 carry legs of the 25 placed attempts read `ticks = X/X`**, and a
placement is not slower (`15.51 -> 15.62 s`). The saving is **-1.48 / -1.20 s on a
never-grasped attempt** and **-3.34 s on a `cnp`** (seed 6, whose control is the
only one that drew `cnp`), against P83's **-5.14 s**: the shipped two-line **already
truncates a lost attempt twice** - `tasks.py` returns right after the lift when the
peak lift is absent (`if not result.grasped: … return result`) and the **P10-C carry
monitor is armed by default in a two-line session** (`_resolve_carry_monitor_knobs`,
confirm 8.0 mm, floor 3.5), which ends the *next* leg at its boundary (measured: **3
of D6's 5 `cnp` attempts have no `place` segment**, 9.1-10.3 s). So the fail-fast's
increment is only the rest of the tripping leg (mean remainder + 50-tick tail
**1.70 s / 1.52 s**). **The delivered side is a seed flip**: interval **+33.6 %** at
seed 5 and **-36.9 %** at seed 6 (pooled **-11.7 %**), count **26/40 -> 25/40**
(equal), and the three waiting terms move the same way as the interval - idle
19.8 -> **23.5 %** (s5, rises) but 24.4 -> **21.7 %** (s6, falls), lock-on 4.19 ->
**4.58** / 5.04 -> **4.39 s**, the right arm's **park-gate wait** 7.1 -> **9.1** /
21.8 -> **13.6 s**, starved polls 44 -> **53** / 33 -> 33. **Verdict: NOT ADOPTED** -
M1 fails on G4's letter (11/12), M2 fails at both seeds (-1.77 / -2.62 s against
P83's 3.0 s bar, because the class mix and the monitor differ), T1 and T2 fail at
seed 5, T3 passes (window 4.34 -> 4.54, batch 4.03 -> 4.05, wall 2.39 -> 2.42);
G1/G2/G5/G6/G7/G8 pass and G3 passes pooled but fails its seed-5 letter (the
`grasped, not placed` label is a class **D5 drew zero of**). **Read rules from here:**
quote the fail-fast's increment **by class** on a line with the monitor on (never
~1.2-1.5 s, `cnp` ~3.3 s), never P83's 5.14 s; a **seed is a scenario**, so a
20-attempt two-line arm needs its own reference (P80's file is seed 5 - `D6`'s is
written from P80's own `T6.log` into `logs/p84/`, never `configs/`) and the treatment
is a **DIFFERS-by-construction** arm gated on **budgets only**; and a 20-attempt
two-line A/B whose **own control swings 16 -> 10 placed between seeds** cannot
attribute a count - the branch-free read is the per-class failed-attempt span. No
motion reference moved (`8952c320` / `eb697f23` stand), no reference re-recorded,
`scripts/selfcheck.sh` **PASS, 0 failures** (no new leg: the phase adds no `src/`
code). Pins: `tasks.py` `f1e44af6`, `bimanual.py` `7e2b7d7e`, `rl_env.py`
`d786279c`, `fruits.py` `c7461d41`; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p84/{PREREG.md,PREREG.md5,RESULTS.md,p84_report.py,p84_report.txt,timeline.py,
run_p84.sh,gates.sh,one_run.sh,stamp.py,battery_driver.log}`, the cells
`{D5,F5,D6,F6}.{log,stamps,driver.log}`, `{D5,D6,F5,F6}.gate` + `D6.gate_t6`,
`{D5,D6,F5,F6}.budgets`, `motion_reference_twoline_T6_20.json`; WORKLOG "P84".

**P85 (2026-11-01, `logs/p85/`; **the shipped default changes: the scripted cell
is the bimanual two-line**) - the owner signed off the grade-pure routing
semantics the W3/R5 register held back, so `FRUIT_BIARM` and
`FRUIT_BIARM_TWOLINE` both default **1**.** Resolvers are single-sited
(`bimanual.resolve_biarm` / `resolve_twoline` / `biarm_resolution`, one per knob,
with the P43 `defaulted` origin flag) and the log names the cell:
`[biarm] scheduler: FRUIT_BIARM=1(default) FRUIT_BIARM_TWOLINE=1(default)`. The
restores are **`FRUIT_BIARM=0`** (the pre-P85 single arm) and
**`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`** (the unchanged F2 shared-station
pipeline); `tasks.two_line_enabled()` became the **session** predicate
(`session.twoline`, False outside a session) and `two_line_resolved()` is the
ambient form `run_bimanual` reads, so the single-arm and shared-station paths
cannot move. The two-line's supply package (`fruits.SupplyPlan.from_env(cfg,
two_line=...)`: dense wave sheet + balanced A:B:C) follows the same resolution
and is passed by the three scripted entries only - `SortingRLEnv` and
`scripts/60_eval_policy.py` pin `two_line=False` (neither is the scripted cell),
so no direct/policy number moves, and `scripts/accept_policy.sh` has **no path**
to the flip (it builds its own `FruitSpawner`/`PickAndPlaceTask`, never a
`CoopSession`).

**The flip is resolution-only, proved three ways.** The default 20-attempt runs
replay the pre-flip *explicit* two-line records line for line modulo the phase's
instrumentation rows: seed 5 **865/865** vs `logs/p80/T20.log`, seed 6
**814/814** vs `T6.log`, and the accel treatment **799/799** vs `V20.log` (the
union's opt-in two-line arm). Delivered (seed 5): **16/20, 9.70 s/attempt,
interval 10.77 s, 5.57 / 4.96 placed/min, wall/pick 16.57 s, 2.90 placed/min
wall** - P80's numbers with P82's wall (331.4 s against T20's 497.2 s). The
single-arm control (`FRUIT_BIARM=0`, same batch) is **346/346 identical to
`logs/p71/accept_rails_none.log`** with `fingerprint: matches` the archive, so
the restore is byte-exact; its rate-only FAIL (6/9 < 0.75) is this tree's
standing branch, not a P85 effect.

**The acceptance moves scenario and its gate becomes honest.** `scripts/accept.sh`
now reads the session from its own log: a two-line session is gated by
`scripts/190_twoline_gate.sh -r configs/motion_reference.json -m 0.60` (the
scenario pin, the two-line floor and the per-scenario reference - one definition
of "a two-line gate", never a second floor inside 105), anything else by 105 with
`configs/motion_reference_single.json`; `selfcheck.sh`'s optional motion leg takes
the same branch. The acceptance reads **7/10, 9.2 s/attempt**, is **424/424
identical to `logs/p80/T10.log`** and **matches `configs/motion_reference_twoline.json`**
- i.e. the flip's acceptance scenario *is* the two-line dense scenario the repo
already had a reference for. Re-recorded: `configs/motion_reference.json`
`8952c320` -> **`eb697f23`** from `logs/p85/accept10.log` (archive
`logs/p85/motion_reference_single_pre_p85.json`, also shipped as
`configs/motion_reference_single.json` for the restore path);
`configs/motion_reference_twoline.json` is **untouched** (same scenario, same
bytes). The collector inherits the flip and its shard manifest gains
`collection.{biarm_resolved,biarm_twoline_resolved,biarm_defaulted,biarm_twoline_defaulted}`
next to the raw strings (which read `"0"` when unset) - **a manifest without
those four keys predates P85** - and `scripts/153_biarm_rates.sh` now names its
modes explicitly (`two-line` = shipped, `shared` = the pre-P85 `FRUIT_BIARM=1`,
`single`), while `scripts/126_branch_probe.sh` pins `FRUIT_BIARM=0` (it probes
the legacy single-arm branch it was written for). `scripts/demo_2min.sh` runs the
shipped cell (3-pick smoke **1/3**, clip `logs/video_demo/` 1705 frames / 56.8 s,
motion gate **PASS** with the scenario's own 0.33 three-pick floor).

**The acceleration cell (P85-ACC, `logs/p85/ACCEL.md`)**: the P44 speed union
re-priced on the now-default line (the park/lock-on family is the larger wall
term - 18-21 % per-arm idle, a 7.1-21.8 s park-gate wait, 4.19-5.04 s lock-on -
but every lever on it is already spent or measured negative, so the union is the
only unspent knob). **The mechanism transfers exactly** - `place` 3.19 -> 2.35,
`release` 2.35 -> 1.63, `lift` 1.65 -> 1.52, **-1.00 s/attempt at both seeds** -
and **the delivered side is a branch draw whose sign flips**: seed 5 16 -> 13
placed (window -3.7 %, 2 new `grasped, not placed`, zero-force legs 4 -> 7),
seed 6 10 -> 14 (window +60 %, guard better), pooled 26 -> 27 of 40. Not adopted
(E2/E3 fail at seed 5); the count moved less than one interval in both
directions, and the class that moves is `logs/p42/SIM_LIMIT.md`'s closed one.
No default changed. Pins: `tasks.py` `f07a865a`, `bimanual.py` `9b7fc33f`,
`fruits.py` `dcabe16b`, `rl_env.py` `TASKS_MD5` follow, `scripts/246_p85_selftest.py`
(new selfcheck leg), `scripts/accept.sh`, `scripts/selfcheck.sh`; references
`8952c320` (single) / `eb697f23` (two-line, and now also the shipped acceptance
reference). **Re-baseline: every rate, acceptance, collector shard and store
recorded before P85 is a single-arm (or explicitly opt-in two-line) number.**

**P86 (2026-11-01, `logs/p86/`; measurement only - **nothing adopted, no default
changed, no commit, `configs/` untouched**): the release block is `-0.64 s` of
pure dwell and it is **exact at both seeds**, but the phase's own pinned span
clause and one motion leg keep it out of the tree.** The cell is P44's S2 knob
(`FRUIT_SPEED_RELEASE=1`: dwell **20 -> 0**, pad ramp **40 x (3 -> 2)**, finger
ramp **16 x (3 -> 2)** = **-76 ticks = -0.633 s** at 120 Hz,
`FRUIT_RELEASE_RESYNC` off), run on the **shipped two-line** at `ATTEMPTS=20`,
seeds 5/6, with the same instrumentation on all four cells (`FRUIT_PLACE_TRACE`
included). **Admissibility: both controls replay P85's records line for line
(C5 **865/865** = `logs/p85/base20_s5.log`, C6 **814/814** = `base20_s6`), so the
tree is unchanged *and* the per-place landing trace is inert.** **The mechanism
(P1a, PASS):** the `[cycle] release=` segment - 2.33 s of a 15.78 s per-arm span,
the second of the three profile blocks - falls **-0.615..-0.640 s = 74-77 ticks
in all four arm-seed cells** by median (means -0.65 / -0.56; pooled mean
2.324 -> 1.714 = -0.611 s, median 2.325 -> 1.680 = -0.645 s), against the
arithmetic's -0.633 s. The two extreme means are one 1.63 s control leg (C6) and
one 1.92 s treatment leg (R6), both `place low` descents inside the segment.
**The delivered side (P2, PASS):** the pooled interval falls at **both** seeds
(10.77 -> **10.59** and 19.34 -> **11.08** s) and on **both arms at both seeds**;
the seed-5 pair is the clean one (identical 16/20 and identical 9/10 + 7/10 arm
split, so -0.18 s pooled / -0.48 s arm span is the lever alone) while seed 6's
-8.26 s is **confounded with a +2 count draw** (`interval = attempts/placement x
span + idle`). `s/attempt` 9.70 -> 9.50 / 9.10; window 5.57 -> 5.66 and 3.10 ->
5.41 placed/min; batch 4.96 -> 5.05 and 3.11 -> 3.94; `placed/min wall`
**2.88 -> 2.95** and **1.91 -> 2.34** (wall -2.2 % / -1.9 % - the arbiter's
per-tick cost is flat, so the wall follows the sim clock). **The landing is clean
(P3, PASS)** - **28/28** payload-present releases land `on_belt` (16/16, 16/16,
10/10, 12/12) in the control's own height/impact/bounce band
(31.8-64.3 mm, -0.93..-0.45 m/s, bounce <= 5.6 mm), the upstream-lost traces read
`release_bottom = -184 mm` and are reported separately (C6 has one, the control's
own `SIM_LIMIT` class) - i.e. P44 §9.4 reproduced on the two-line and P45's
displacement-controlled ramp confirmed. **The ledger gains no class (P4, PASS)**
at either seed; the counts shift at seed 6 (never-grasped 5 -> 1, `cnp` 5 -> 7),
the re-timed presentation drawing a different fruit, and the `force_min == 0.00`
loaded-slide guard is flat at seed 5 (4 -> 4) and **better** at seed 6 (11 -> 7).
**What fails, and why it matters:** **(1) P1b, the attempt-span instance of the
same claim** - registered at `-0.633 +- 0.12 s` per seed and per arm, it reads
**-0.41 / -0.57** (seed 5) and **-0.27 / -0.96** (seed 6) and fails its band at
both seeds. **The miss is not the lever**: the residual ("span - block") is
**+0.17 / -0.12 s**, sign-flipping - the acquisition blocks re-draw with the
shifted attempt boundary (`descent` +0.24 at seed 5, `grip` -0.35 and `place`
-0.17 at seed 6) - and over two seeds the span saving (-0.575) tracks the block
to 0.04-0.07 s. **A per-seed attempt span is not branch-free**, so it is not a
valid second leg for a profile cell (P44 §3's caveat, which this phase's PREREG
§7 wrongly denied); the branch-free instance is the block itself and it passes
exactly. The named re-entry registers the block + the interval and reads the span
as a report. **(2) G2, the motion guard, FAILS at R6 on one leg** - the log's
12th descent (cycle attempt 12: **right** arm, kiwi, **placed**, lift +0.559 m)
reads `|v|max` **0.164** against the 0.160/0.161 budget (**2.5 % over**,
`a_med` 0.57 peaking at 0.68 of the leg, `end = 12.6 mm` short, lurch 0.036 of
the 0.291 bound); C5 0.112, R5 0.111, C6 0.132. The descent profile is **not
touched by this cell** and AGENTS §2 forbids re-tuning the budget to admit a
configuration, so it is recorded as a failed guard: the trim shifts the attempt
boundary, the catch is presented a different fruit at a different belt offset,
and one leg of one seed pays it. **Gates:** C5 `190` **PASS** vs
`logs/p80/motion_reference_twoline_p80_20.json`; C6 `190` **PASS** vs the seed-6
reference written **from C6 itself** into `logs/p86/` (a seed is a scenario -
never `configs/`); R5/R6 recorded **DIFFERS by construction** (the fingerprint
carries each leg's duration) and gated on budgets only. **Verdict: PREREG §5's
letter = NOT a win (no default change); the sponsor's four-clause rule (block,
interval, landing, ledger) passes at both seeds**, so the cell is a measured
positive whose adoption package is **priced and not executed** (RESULTS §9): a
**two-line scope first** (the knob is read at a shared site, so a global default
would also move the single arm, the hybrid canary and the scripted collector),
three references re-recorded from same-batch runs if the flip is global,
`physics.release={dwell,pad_hold,finger_hold}` in both manifests **before** any
recollection, and a 2-seed 40-attempt budget run of the trimmed branch. Pins:
`tasks.py` `f07a865a`, `bimanual.py` `9b7fc33f`, refs `eb697f23` / `8952c320` /
`eb697f23` **untouched**, ckpt `moe_v13s` `61da390a`; no new selfcheck leg (env
only). Evidence `logs/p86/{PREREG.md,PREREG.md5,RESULTS.md,p86_report.py,
p86_report.txt,run_p86.sh,gates.sh,header.txt,battery_driver.log}`,
`{C5,R5,C6,R6}.{log,stamps,driver}`, `{C5,C6}.gate`, `{R5,R6}.gate`,
`{C5,R5,C6,R6}.budgets`, `motion_reference_twoline_C6_20.json`; WORKLOG "P86".

**P87 (2026-11-01, `logs/p87/`; **one shipped change: the release trim is the
two-line session's default** - scoped, not global - and nothing else moved): the
gap displays **-0.64 s of pure dwell at both seeds**, the scope is proven
**bit-for-bit**, and one descent leg on one seed keeps the flip in the
"considered trade" tier rather than a clean pass.** P86 measured the S2 cell and
priced it; the blocker to shipping it was that the release block is read at a
site **every** presentation shares (`_grasp_carry_place_impl`), so a *global*
default would also move the single arm, the shared-station pipeline, the hybrid
canary (`60_eval_policy.py` builds its own `PickAndPlaceTask`) and the scripted
collector - none of which P86 measured. P87 ships it **two-line-scoped**, the
`_dynamic_profile` pattern: **`FRUIT_SPEED_RELEASE` now resolves ON for a
two-line session** (`dwell` **20 -> 0**, the pad/finger settles **3 -> 2** =
**-76 ticks = -0.633 s** at 120 Hz, `origin=default`) and **off everywhere else**
(`origin=scope-off`, the shipped 20/3/3). **`FRUIT_SPEED_RELEASE=0` restores** on
the two-line too, an explicit **`=1` still wins globally** (as does
`FRUIT_SPEED_ALL=1`, the S13 union; an explicit `=0` beats the union), and
`FRUIT_SPEED_RELEASE_SETTLE` still moves the settle, read only when the cell is
on. One resolver (`tasks.release_speed_resolution`) feeds the per-attempt holds,
the new **`[fruit] [biarm] release profile:`** row and the store manifest's
**`physics.release`** block; the scope argument is
**`Task.two_line_enabled()`** (the `CoopSession` predicate), so a path with no
session cannot arm it. **The gate (PREREG `738c1b54`, pinned before the runs;
`ATTEMPTS=20`, seeds 5/6, arms = `FRUIT_SPEED_RELEASE=0` vs unset, P86's
instrumentation on both):** **G0 - the flip is resolution-only, proved by
replay**: the four cells are **byte-identical to P86's own four** on the
`[fruit]` stream (`C5` **865/865** = `logs/p86/C5.log`, `T5` **868/868** =
`R5`, `C6` **814/814** = `C6`, `T6` **821/821** = `R6`, dropping the diag rows
**and the one new row**, which reads `=1(default)` where P86's treatment read
`=1(explicit)`) - **so the shipped default *is* the measured arm, bit for bit**,
and P86's whole measurement transfers. **P1a PASS both seeds**: the `[cycle]
release=` **median** falls **-0.645 / -0.640 s** (**77 / 77 ticks**) against the
registered -0.633 +- 0.03, and in **all four arm-seed cells** (-0.640/-0.640 at
seed 5, -0.635/-0.615 at seed 6). **P2 PASS both seeds** - the pooled interval
**10.77 -> 10.59** and **19.34 -> 11.08 s**, and on **both arms at both seeds**;
the seed-5 pair is the clean read (16/20 identical, same 9/10 + 7/10 split, so
the -0.18 s is the lever), seed 6's -8.26 s carries a +2 count draw. **P3 PASS**
(**28/28** payload-present releases `on_belt`, in the control's own
height/impact/bounce band: 32.1-64.3 mm, -0.93..-0.61 m/s, bounce <= 4.9 mm);
**P4 PASS** (no new reason key at either seed; the `force_min == 0` loaded-slide
guard flat at seed 5 (4 -> 4) and better at seed 6 (11 -> 7)); **P5 (reported,
never gated)** window **5.57 -> 5.66 / 3.10 -> 5.41** placed/min, batch **4.96 ->
5.05 / 3.11 -> 3.94**, wall **328.4 -> 325.4 / 308.2 -> 306.3 s**,
**`placed/min wall` 2.92 -> 2.95 / 1.95 -> 2.35**. **P6 is the one clause that
misses its clean-pass form**: **seed 5 is clean (0/20 legs)** and **seed 6 has
exactly one leg over budget** - leg 12, a 5.9 cm descent, `|v|max` **0.164**
against its **0.160** per-leg budget (2.5 % over, lurch 0.036 of 0.291) - which
is **the same leg P86's R6 recorded**, so the 40-attempt sample answers P86's
open question the only way it could: the excursion is a **deterministic property
of that seed's branch**, not a random draw and not a systematic cost (T5's worst
is 0.111). By PREREG §5's pre-registered tier that is a **CONSIDERED TRADE -
ship, P6 documented**, not a clean pass; the budget was **not** re-tuned (AGENTS
§2) and the named next spend is a third seed if the owner wants it priced
further. **The inertness is proven, not argued**: `FRUIT_BIARM=0
scripts/accept.sh` is **346/346 raw byte-identical** to
`logs/p71/accept_rails_none.log` (**the new row does not print on the single
arm at all** - 0 occurrences) with `fingerprint: matches
configs/motion_reference_single.json`, and the shared-station pair (`=1
FRUIT_BIARM_TWOLINE=0`, 4 attempts, unset vs `=0`) is **identical on all 218
other `[fruit]` lines** with the **same resolved clock** (20/3/3, 188 ticks) -
the one difference is the row's `origin` field (`scope-off` vs `explicit`),
which is what the label is for; that is **PREREG deviation A1**, recorded in
`logs/p87/RESULTS.md`. **`190`**: C5 **PASS** vs P80's seed-5
20-attempt reference, C6 **PASS** vs P86's seed-6 record; T5/T6 **DIFFER by
construction** and were gated on budgets only. **Re-recorded, two-line side
only**: `configs/motion_reference.json` `eb697f23` -> **`423896f7`** and
`configs/motion_reference_twoline.json` `eb697f23` -> **`423896f7`** (both from
`logs/p87/accept10.log`; the pre-flip pair is archived at
`logs/p87/motion_reference_pre_p87.json` /
`..._twoline_pre_p87.json`); **`configs/motion_reference_single.json`
`8952c320` is untouched**. `scripts/234` (P64) pinned the P85 *value*; it now
pins the *arrangement* (acceptance == two-line record, single-arm = `8952c320`),
which is the invariant that can break. **Provenance before any recollection**:
`scene._release_provenance` writes `physics.release={dwell, pad_hold,
finger_hold, ticks, shipped_ticks, saved_ticks, profile, origin, two_line,
label}` in **both** manifest writers (the collector passes its own `TWO_LINE`,
the direct env `False`), so a store **without** the key predates P87. The
acceptance on the final tree reads **7/10 = 70 %, 9.4 s/attempt,
`fingerprint: matches`, `190: PASS`** (`logs/p87/accept_final.log`, byte-identical
to the reference-source run); selfcheck **PASS (0 failures)** with the new `247`
leg. **Re-baseline: every two-line rate, span or interval recorded before P87 is
a 2.35 s-release number; `FRUIT_SPEED_RELEASE=0` restores it** (compose with
`FRUIT_ARM_PARK=ready` for pre-P43, `FRUIT_POLICY_TRIGGER_ACQ=0` for pre-P54 and
`FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0` for the
pre-P58 **direct** profile - which this flip never reaches). Pins: `tasks.py`
**`6b267ecc`**, `scene.py` **`047d9e7b`**, `rl_env.py` **`96076c8b`**
(metadata-only `TASKS_MD5` follow), `scripts/40_collect_demos.py` **`77e0331f`**,
`scripts/247_p87_release_scope_selftest.py` **`a4aa4756`**, `scripts/225`
**`395d3cd3`** (the scoped-call census), `scripts/234` **`ec1118be`**;
`configs/motion_reference.json` `423896f7` / `..._twoline.json` `423896f7` /
`..._single.json` `8952c320`; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p87/{PREREG.md,PREREG.md5,RESULTS.md,p87_report.py,p87_report.txt,
run_p87.sh,run_p87_extra.sh,gates.sh,gates.out,header.txt}`, `{C5,T5,C6,T6}.{log,
stamps,driver}`, `{C5,T5,C6,T6}.gate`, `{C5,T5,C6,T6}.budgets`,
`single_accept.*`, `shared_{unset,zero}.*`, `accept10.*`, `accept_final.*`;
WORKLOG "P87".

**P88 (2026-11-01, `logs/p88/`, default off, **nothing adopted**): the place
block is the largest remaining one and the cell's mechanism is exact - but the
delivered interval rises at both seeds, so `FRUIT_SPEED_PLACE` stays off.** The
shipped cell (two-line + P87's release trim) has `place` as its largest block
(**3.14-3.19 s** against `release` 1.70 and `lift` 1.65), and P44's S1
(`v_max` 0.35 -> **0.52** at the shipped `a_max` 1.089, inside the 0.61 m/s
ceiling) is the only unspent one of the three. The phase built the same
**two-line-scoped** form as P87 - one resolver (`tasks.place_speed_resolution`),
the consumer `speed_cell_defaults(self.two_line_enabled())` at `_carry_leg`, the
`[biarm] place profile:` row and the manifest's `physics.place` - and measured
it with the controls at `FRUIT_SPEED_PLACE=0` and the treatments unset:
**P1b is exact on every leg** (the per-leg tick count against the profile
re-generated at 0.52 from that leg's own printed distance: median **0.0 / +0.5
ticks, max |2|**; `|v|cmd` equals the profile's own peak to **<= 0.009 m/s**;
median leg **0.508 m/s** against the control's 0.341-0.343), and **the block is
exactly `transit(0.52, d) + 0.583 s`** - the `place low` rest is **0.583 s
(0.578-0.588) in all four cells**, so the treatment's own median is predicted
from its own legs to **-0.008 / +0.014 s**. **The registered gate fails
anyway**: **P1a** at seed 5 (**-0.770 s** against the predicted -0.904 = **0.134 s**
against a +-0.12 band - the miss is the **leg mix**, because the block is
distance-dependent and a median is not branch-free for a transit; the mean
matches to **0.002 s**), **P2 at both seeds** (10.59 -> **13.23** and 11.08 ->
**12.11 s**), and **P4a at seed 5** (one `grasped, not placed (no note)` row, a
ledger bucket present in **3 of the 4** cells). **The class guard's substance is
negative**: place-leg escapes **0/27** in the treatment against **1/29** in the
control, all-leg escapes **5 vs 8**, `force_min == 0` **6 vs 8**; the landing is
clean (**16/16, 11/11, 12/12, 15/15**); both treatments' descent budgets are
clean (0/20 each; the control's seed-6 leg 12 at **0.164 vs 0.160** is
P86/P87's standing branch leg). The delivered read: seed 5 places **16 -> 11**
(the left's never-held **1 -> 4**, `force@onset = 0.00 N`, `sep@onset` 59-63 mm -
the pre-contact acquisition class, not the place transfer), seed 6 places
**12 -> 15** over a **wider** window, so **pooled 28 -> 26 of 40** and
**`placed/min wall` 2.65 -> 2.61 (-1.6 %)** while the wall itself falls 5.6 %.
**Nothing moved**: `configs/motion_reference.json` / `..._twoline.json` =
`423896f7` and `..._single.json` = `8952c320` are untouched, the final
acceptance reads **7/10, 9.4 s/attempt, `fingerprint: matches`, `190: PASS`**,
and the shipped tree is inert three ways - C5/C6 replay P87's T5/T6 **868/868**
and **821/821** on the `[fruit]` stream, a fresh unset 20-attempt run (`N5`)
replays C5 **868/868**, and the single arm is **346/346 raw** identical with the
profile rows absent (the shared station's clock is unchanged, `--profile`). The
measured arm is reproducible as `FRUIT_SPEED_PLACE=0.52`; the re-entry is a
scenario where the place block **binds** the interval (not the count) or a
class-first registration argued on the wall alone. Pins: `tasks.py`
**`9e1aeef9`** (`PLACE_TWO_LINE_DEFAULT = False`), `scene.py` **`1ec3b8f8`**,
`rl_env.py` **`1900fb26`** (the `TASKS_MD5` follow),
`scripts/248_p88_place_scope_selftest.py` (new selfcheck leg),
`scripts/225`/`247` re-pinned for the second scoped consumer. Evidence
`logs/p88/{PREREG.md,PREREG_A1.md,PREREG_A2.md,RESULTS.md,p88_report.py,
p88_report.txt,gates.out,accept_final.*}`, `{C5,T5,C6,T6}.log`, `N5.log`,
`single_accept.*`, `shared_*`; WORKLOG "P88".

**P89 (2026-11-01, `logs/p89/`, default off, **nothing adopted** - the third and
last profile block, and with it the **profile table is closed**): the `lift`
block's mechanism is **exact to the profile's own arithmetic** and the delivered
side still does not follow - the same shape as P88, on the smallest block.** The
cell is P44's **S3-v** (`logs/p44/P2_RESULTS.md` §9: `grasp_lift` `v_max` 0.30 ->
**0.37** with the shipped **`a_max` 1.0**; the acceleration raise was measured at
**0.00 s** for transient spent, so it is *not* part of the cell and
`FRUIT_SPEED_LIFT=0.37` resolves 1.0 while `=1`/`FRUIT_SPEED_ALL` keep S3/S13's
measured **0.36 / 1.9**). The scoped plumbing is P87/P88's third instance -
`tasks.lift_speed_resolution` + `LIFT_TWO_LINE_DEFAULT`, the consumer
`speed_cell_defaults(self.two_line_enabled())` at `_carry_leg`'s `grasp_lift`
branch, the `[biarm] lift profile:` row and `physics.lift={v_max,a_max,ticks,
shipped_ticks,saved_ticks,reference_distance_m,profile,origin,two_line,label}` in
both manifest writers, pinned by the new `249` selfcheck leg. **The mechanism**
(`ATTEMPTS=20`, seeds 5/6, controls explicit `FRUIT_SPEED_LIFT=0`, treatments
unset; `PREREG.md` **`30d8941c`** + `PREREG_A1.md` **`14c73afd`** - the amendment
corrects G0's replay target to P88's **C5/C6** and was pinned **while the first
cell was still running**): `[cycle] lift=` is the leg plus a **constant remainder
0.412-0.422 s** in both arms, so the block **mean** falls **-0.175 / -0.173 s**
against the predicted **-0.177 / -0.193** (**P1a PASS**, band ±0.08), the per-leg
tick count matches the profile re-generated at 0.37/1.0 from that leg's own
printed distance to **median 0.0 (max |5|)**, the leg's `|v|cmd` to **0.013 m/s**
of its own peak (median **0.350** against the control's 0.293), and the reference
clock is **162 -> 136 ticks = -0.217 s** at 0.21 m. **The two regimes switch at
`d = 5.774 v^2/(1.875^2 a)` = 0.225 m** (0.148 shipped), which is *why* the cell
is small: above the switch the raised leg is acceleration-bound, so a 0.20 m leg
saves 21 ticks, not the 1.233x speed ratio. **The delivery fails at both seeds
for two different terms**: the pooled interval **rises** 10.59 -> **13.43**
(seed 5: the count, 16 -> **12** placed, `attempts/placement` 1.25 -> 1.67, left
**9/10 -> 5/10**) and 11.08 -> **12.38 s** (seed 6: the count rises 12 -> 14 over
a **wider** window, 121.9 -> 160.9 s - P88's seed-6 pattern), pooled **28 -> 26
of 40** and **`placed/min wall` 2.67 -> 2.60**. **The class answers the phase's
own question - neither P44's improvement nor P75's site**: lift-leg escapes
**7/40 -> 10/40** (seed 5 **2 -> 6**, seed 6 **5 -> 4** - a draw at n=20 per arm)
and `force_min == 0` legs **8 -> 10**, so P44's single-arm "S3-v drops them 5 vs
7, no new failure row" does **not** transfer; every escape's `onset_row` is
**early in its leg** (median share **0.05** - the **take-off** loaded slide),
the treatment's **place-leg escapes are 0/27** against the control's 1/29, so no
place leg inherited a broken pinch and P75's "starts with one face at 0.00 N"
signature is absent; one new reason key (`grasped, not placed (no note)` x1) and
P4a/P4b fail at seed 5 while P4c passes (2 -> 6 < +5). Landing **12/12, 14/14**;
descent budgets **0/20** in C5/T5/T6 and the standing seed-6 leg 12 (0.164 vs
0.160) in C6, not re-tuned. **Nothing moved**: `LIFT_TWO_LINE_DEFAULT = False`,
`configs/motion_reference.json` / `..._twoline.json` = **`423896f7`** and
`..._single.json` = **`8952c320`** untouched, the measured arm is
`FRUIT_SPEED_LIFT=0.37`, and the shipped tree is inert three ways - C5/C6 replay
P88's **C5/C6** **868/868** and **821/821** (and *differ* from P88's T cells at
line 160, a `place1` row, so the filter hides only this phase's own rows), a
fresh unset `N5` replays C5, and the single arm is **346/346 raw** identical with
**0** profile rows printed. Pins: `tasks.py` **`32efa98c`** (`LIFT_TWO_LINE_DEFAULT
= False`), `scene.py` **`fb6d9d33`**, `rl_env.py` **`b81d59b6`** (the `TASKS_MD5`
follow), `scripts/249_p89_lift_scope_selftest.py`, `scripts/selfcheck.sh`. The
final tree's own checks: `selfcheck.sh` **PASS** (the `P89 lift scope` leg),
`106`/`107` **OK/PASS**, and `scripts/accept.sh` **7/10, `fingerprint: matches
configs/motion_reference.json`, `190: PASS`** (`logs/p89/accept_final.log`) - the
shipped branch, unchanged.
Evidence `logs/p89/{PREREG.md,PREREG_A1.md,RESULTS.md,p89_report.py,
p89_report.txt,gates.out}`, `{C5,T5,C6,T6}.log`, `N5.log`, `single_accept.*`,
`shared_*`; WORKLOG "P89". **Re-baseline: none** - nothing shipped, and the
profile blocks are all measured (release shipped P87, place negative P88, lift
negative P89).

**P90 (2026-11-01, `logs/p90/`; offline geometry only - no `src/` or `configs/`
edit, no default change, no commit, no reference re-recorded): the owner's
workstation path - the output **place-station** map - closes **negative**, and with
it the last of `docs/LEFT_ARM.md`'s three named levers that had not been measured.
The instrument is P66's 150-cell pick-band sweep copied and retargeted
(`logs/p90/station_map.py`), so the two maps read the same way: the target is the
pose the code commands (`(x, y, output_place_z [ + the OpenArm 0.08])`), the grid
is **+-0.15 m in `x` and `y`** at **z = 1.450** (the place height) and **z = 1.530**
(the transfer), **both arms**, and the criterion was pinned in `logs/p90/METHOD.md`
(md5 **`42bec0f8`**, mtime **22:31:42** - before the probe existed at 22:32:17 and
before the sweep at 22:33:39): `residual <= 6 mm AND qerr <= 2 deg AND margin >=
0.05 rad AND pad >= 2 mm` (P66's three clauses plus the residual tolerance), with
`NAT`'s `qerr` clause replaced by `tilt <= 5 deg` (the `drift_end` scale: P66's rungs
read 25.1 / 3.4 / 0.7 deg). **Three modes, and the split is the design**: `T0` =
hold top-down (a survivor needs a place-leg wrist hold, which P68 measured **0/16**),
`NAT` = `hold_quaternion = None`, the position-only solve the shipped place leg
**actually runs** - a survivor here is shippable **by a station move alone** - and
`C0` = the arm's own calibrated belt-aligned `grasp_quaternion`, P66's "which
attitude does the workspace offer" control. **Result: 0 of 588 cells pass, in every
mode, at both heights, on both arms** (`station_map.txt`, `cost_map.txt` §5). `T0`:
**0/98 per arm**, and **at the transfer height the best margin over the whole
49-cell grid is `+0.000153 rad` (0.15 mrad)** - not one cell has a milliradian of headroom; the
smallest tilts (7.46 deg at 1.450, 15.16 at 1.530) cost **172-192 mm** of position.
`NAT`: only **7-8 of 49** cells even solve to 6 mm (the box `x 0.38..0.48`,
`|y| 0.35..0.55`) and **every one reads 77.8-108.4 deg of tilt** - the best *solved*
attitude in the entire envelope is **77.75 deg, at the shipped station itself**
(`x 0.43, |y| 0.50, z 1.450`: res **5.9 mm**, margin **+0.185 @ j4**, `tool_y`
**+0.628**). `C0`: **also 0/98** - best margin **+0.037 rad @ j6** (1.450) /
**+0.041 @ j7** (1.530) against the 0.05 bar, and it does **not** solve at the
shipped cell at all (**res 83.2 / 105.3 mm, qerr 45.65 / 45.86 deg, margin -0.000 @
j3**). The distinction that matters: `T0` and `C0` are **6-DoF** solves (position +
orientation) and **both fail at the shipped cell**, while `NAT` is the **3-DoF
position-only** solve the leg actually runs and it arrives with 5.9 mm - so the place
station is at the **reach boundary** and the leg **buys position with attitude**,
which is what `assets.py`'s own note says (`y_off = 0.41` from the shoulder, i.e.
`|y| = 0.50`). **The instrument reproduces the live record statically**: `NAT` reads
**77.75 deg** against P73's live `tilt_end` **78.7 deg** and the release-time
payload offset's implied **87.9 / 91.1 deg**, and `NAT` at the transfer does not
solve to 6 mm (**14.9 mm**), which is the live leg's own `res_end` **13.3-34 mm**.
**The cliff is one 10 mm step and the shipped point is on it**: along `x = 0.43`,
`|y|` 0.50 -> 0.51 takes the residual **6 -> 19 mm** and the margin **+0.185 ->
-0.0000** at the place height, and the cliff sits between **0.49 and 0.50** at the
transfer (so the shipped station is already one step *past* it there); along
`|y| = 0.50`, `x` 0.43 -> 0.48 takes it **6 -> 46 mm**. **Robustness, three ways**:
re-seeded from the calibrated place pose (`bin0_above`/`bin1_above`, `restarts = 3`)
`T0` is **0/14 per arm with `|margin| <= 0.060 mrad` on every cell**, and `NAT` finds
**28 deg** - but only on the **left**, only at `|y| = 0.35` (**75 mm inboard of the
slab's 0.425 edge**, the band that has had **no surface** since P71 removed the inner
rail), and 28 deg is **5.6x** the bar, **inside** the pre-P66 0.36 m rung's own carry-drift
range (20.8-28.3 deg) and **40x** the shipped 0.20 m rung's `drift_end` (0.7 deg). **The costs all came back cheap - the gain is what is zero**
(`COST.md`): the crossing is **exactly 0 mm** for any `y` on the shipped *horizontal*
transit and **+0.30 mm/mm** inboard on the direct low lift (bounded to +5 mm by the
release band); the release is the one binding column and it *constrains* rather than
costs (commanded `|y|` **0.378..0.633**, which the shipped 0.500 sits inside); the
chute and tray are **downstream in `+x` and absolute** (0.92 / 1.12 / 1.35, and
`on_output_discharge` starts at `output_belt_end_x - 0.05` = 1.15); the two-line's
stations, its pre-poses, the park gate (`_biarm_payload_clear` fires at `|y| = 0.28`
mid-transit) and the supply read no place field. **One correction to the record**:
a census of **43 held releases** across 7 logs (`logs/p70/{C,A,B}.log`,
`p71/{both,none}.log`, the acceptances) reads **jaw - target = (-1..-4, -6.5..+1)
mm** - the jaw lands **on** the commanded point - and **payload - jaw = (+52,
+-42..46, ~0) mm**, `|.|` **72.6 / 66.4 mm**, implying the tool axis
**(+0.775, +-0.631, -0.04)** i.e. **tilt 87.9 / 91.1 deg**. So P70 §4's "the arm's
outward overshoot at its reach boundary" is **wrong**: the +45 mm is the payload
hanging **`_pad_standoff`'s 70 mm along a horizontal tool axis** (`FRUIT_FINGER_LEN`
0.060 + `PAD_LIFT` 0.010), and a top-down station would remove it for free. **Verdict:
the workstation path closes** - the negative is not a siting choice, and P73's
falsifier B already says the rotation is not the class's actuator (all 8 losses
start **before** the 45 deg crossing at a tilt **below 45 deg**; the right reaches
**107.3 deg** and slips **0.0-0.1 mm on 10/10**), so `docs/LEFT_ARM.md`'s remaining
two sanctions (**a new pad asset**, **a real-jaw clamp-force anchor**) are the whole
list. **No `PREREG.md` is written**: METHOD's rank-1 form (a `NAT` survivor) has an
empty candidate set and rank 3 is the outcome. Pins: `station_map.py` **`edf6f3e8`**,
`cost_map.py` **`194880a2`**, `station_rows.json` **`bb666852`** (588 rows),
`..._refine` **`ec20d89b`** (104), `..._seed_{left,right}` `540d0cb7` / `6094d7d1`
(28 each); tree `assets.py` **`540406fa`**, `tasks.py` **`32efa98c`**, `control.py`
`9384ff4f`, `motion.py` `7f2443c1`; `configs/*` **untouched**
(`0ea08ebb` / `8d50fdeb` / `423896f7` / `423896f7` / `8952c320`);
`scripts/selfcheck.sh` **PASS, 0 failures**. **Re-baseline: none** - nothing was
shipped and the scripted line never reads a place-station field.

**P91 (2026-11-02, `logs/p91/`; the take-off validation ramp as a two-line-scoped
tick cell, **default off, NOT adopted**): the audit of the five never-profiled
`[cycle]` blocks, and the phase's own product, is that they hold **1.08 s = 7.0 %
of the 15.34 s**, not 57 %.** The owner's question was the **single-pick cycle
excluding the fruit wait** ("不包含等果时间"), and the five blocks `descent 3.64`,
`grip 2.36`, `close 1.36`, `hover 0.75`, `prepose 0.71` (**8.82 s**) had never
been profiled. `logs/p91/AUDIT.md` defines each by its own marks (quoted from
`_cycle_begin`/`_cycle_mark`, with the emitting code line) and decomposes
`logs/p87/T5.log`, `logs/p86/C5.log`, `logs/p89/C5.log` into **wait 4.09 s +
failure tax 0.76 s + arm motion 3.63 s**, leaving **1.08 s speedable**: * **the
descent is not a descent.** Its block is the **fruit-arrival wait** (2.17 s) plus
a **scheduled** wait (0.59 s) plus the profiled leg (0.74 s), and the schedule
makes the block **invariant**: the wait exits when the fruit is
`speed*(t_desc + FRUIT_DYNAMIC_DESCEND_MARGIN)` away, so
`block = lead/speed − margin` and **a faster leg just waits longer**. The
arithmetic agrees from the other side (the 5.5 cm leg is **jerk-bound**: 86 ticks
at `a_max` 0.8 *and* 1.6; 64 only at `v_max` 0.25 **and** `a_max` 1.6), and the
measurement agrees from the third (`--schedule`: `t_desc` spans **0.03 s** while
the block's sd is **8.9 ticks**, so within this cell the leg is not an available
variable at all). * **the grip is 1.75 s clean / 2.36 s mean**, and its
bimodality is **P40's tax**: a failed probe costs **+1.53 s**, a burnt cap
**+2.29 s**, and the mean carries **0.61 s** of it - measured, not sped. Inside
the clean 210 ticks the **60-tick validation ramp** is the only profile (the
54-tick belt-break beside it is the P3 anti-shear constant), and it is a **1:1**
lever: the single-arm 40-tick probe's clean block is **190 ticks** against the
two-line's **210**, Δ 20 with an identical 150-tick remainder. * **the close is
catch-up (0.63) + a 22-tick ramp + a 48-tick hold** (direction contested:
R11-B/P18b measured a *slower* close converting the direct carried class), **the
hover is `move_to` at the IK step cap** (no profile; R3's residency negative) and
**the prepose is a tuned 45-tick blend + a 20-tick pump**. So the pick was the
grip's probe ramp - and **the cell measured the lever exactly and lost anyway**:
clean `grip` **1.75 → 1.44 s (210 → 173 ticks, −0.31 s against the registered
−0.300)** at **both** seeds and in both modes (seed 6's cheap re-seat 1.95 →
1.65), while the **block** mean **rose** (2.36 → 2.58 / 1.98 → 2.37) because the
**mode mix moved**: first-probe success **14/20 → 5/20** and **18/20 → 9/20**,
i.e. **the ramp's duration *is* the validation's detection margin** (the grasp
test is `fruit_z − z_before > 4 mm`; 6 mm/60 ticks leaves 2 mm of slack, 6 mm/24
ticks does not) **and the force servo's squeeze window** (`..._SQUEEZE_S` = 0.10
s lives inside the probe). The class moved with it at both seeds -
`never-grasped` **4 → 6** and **1 → 4**, a new `carried-not-placed` 0 → 3, the
loaded-slide guard (`force_min == 0`) **4 → 9** and **7 → 11**, and the delivered
pinch **9.65 → 7.77 N** at seed 6 (**10/18 held legs under the 9.0 N floor**,
against P41's 9.7-9.9 plateau) - and the delivered side rose at both seeds
(interval **10.59 → 13.01** and **11.08 → 12.20 s**, window 5.66 → 4.61 / 5.41 →
4.92 placed/min, `placed/min wall` 2.95 → 2.32 / 2.34 → 2.33), which is
**P88/P89/the union/the fail-fast for the fourth time**: a 0.30 s block delta is
not deliverable on this cell. **Nothing shipped**: `PROBE_TWO_LINE_DEFAULT =
False`, so unset resolves the shipped 60-tick probe on every path; the measured
arm is `FRUIT_DYNAMIC_PROBE_TICKS=24`; the machinery is the fourth of the
scoped-resolver family (`tasks.probe_ticks_resolution`, the `[biarm] take-off
profile:` row, `scene._takeoff_provenance` → `physics.takeoff`, the `250`
selfcheck leg). Guards that passed (they make the negative readable): **landing
16/16, 11/11, 12/12, 12/12 `on_belt`**, **catch window** residual median 5.9 mm
in all four cells / `end=` max 10.6-12.7 mm (bar 25) / grasp 16, 14, 19, 16
against the 14/20 bar, and the motion budgets clean in all four cells.
**Recorded deviations**: the `T5` driver-window pairing slipped on 6 adjacent
rows (|`total − window`| to 6.79 s, arm labels swapping) so the **span is read
from the cycle `total`**, never from the window; and the **mode-mix change is not
attributed** (the treatment's descent block is 0.6-0.8 s shorter, i.e. a
different selection cadence - "the shorter ramp failed more validations" and
"the re-timed presentation drew harder fruit" are not separated at this N; the
verdict does not need the separation, P2/P4/P7 fail on the delivered side on
their own). No reference was re-recorded and none is owed (`423896f7` /
`8952c320` / `423896f7` untouched). **The shipped tree after the phase**: the
acceptance reads **7/10, `fingerprint: matches`, `190: PASS`** (the standing
branch) and `selfcheck.sh` is **PASS (0 failures)** with the new `P91 probe
scope` leg; `logs/p91/gates.sh` exits **0** (G0 replays the shipped cell
868/868 and 821/821, the single arm 346/346 raw + `fingerprint: matches`, the
shared station resolving the shipped 40 with the raw difference only on the
row's `origin`, and `N5` replaying the pre-change record) — with one **report
deviation (PREREG A1)**: P8's clause named `logs/p89/T5.log` as the pre-change
record, but that file is P89's **lift-raise** arm (its battery ran
`LIFT_TWO_LINE_DEFAULT = True`), so the target used is `logs/p87/T5.log`, the
record of the shipped cell (byte-identical to `p88/C5` and `p89/C5`); the `190`
fingerprints DIFFER on all four cells against the pre-P87-clock 20-attempt
references, the registered recorded-not-gated read. Pins: `tasks.py`
**`7ba4bb58`**, `rl_env.py` `TASKS_MD5` follow,
`scripts/250_p91_probe_scope_selftest.py`, `scripts/selfcheck.sh`; ckpt
`moe_v13s` `61da390a`. Evidence
`logs/p91/{AUDIT.md,audit.py,audit.txt,PREREG.md,PREREG.md5,RESULTS.md,
p91_report.py,p91_report.txt,run_p91.sh,run_p91_extra.sh,gates.sh,gates.out,
accept_final.log,selfcheck.log}`, the cells `{C5,T5,C6,T6}.{log,stamps,driver,
gate,budgets}`, `N5`, `single_accept.*`, `shared_{unset,zero,forty}.*`,
`shared_raw_same.txt`, `smoke.log`; WORKLOG "P91".

**P92 (2026-11-02, `logs/p92/`; **nothing adopted, no `src/` or `configs/` change,
no reference re-recorded** - and the scenario lane the record had closed is
re-opened with a measured mechanism): the shipped cell's 12 failures are **9
`cnp` + 3 never-held** (0 `fell off the line`, 0 lost slots, 1-2 `diverted`), the
never-held class is **not an acquisition loss** but the same close collapse one
phase earlier, the supply band's **top** converts **8 of the 12** at *both* seeds
(28/40 -> 36/40) and the pre-registered rule still refuses to ship it on **one
descent leg**, and the force servo's chase - which is the **signature of every
failure** on the tree (11/11, `p = 5.2e-09`; 14/14 on the pre-P87 block) - is
**not the cause**: gating it removes the chase and moves the failures between
labels without converting one.** The census (`logs/p92/CENSUS.md` +
`census.py`/`chase.py`, offline) reads the **two distinct cells** (`p87/{T5,T6}`,
seeds 5/6, 40 attempts) and drops the **byte-identical replays** (`p88/{C5,C6,N5}`,
`p89/{C5,C6}`, `p91/{C5,C6,N5}`) rather than inflating n; the pre-P87 clock
(`p84/{D5,D6}`, 26/40) is a **separate block**, never pooled (and `p80/{T20,T6}`
carry no `[carry]` diag, so 4-5 of their rows are unclassifiable - said, not
guessed). Three reads matter. (1) **The class split**: `cnp` 9 (75 % of failures,
the closed loaded slide) + never-held 3 (25 %), the latter **exactly** the
attempts whose `catch-up residual` exceeds 6 mm (3/3 vs 0/37). (2) **The close's
seat**: `gap_start - dia <= -14 mm` (the pads commanded *inside* the fruit) is
**5/5 failed** against 7/35 otherwise (**p = 0.0012**) - the 3 never-held and the
2 seed-5 `cnp` are one event seen at the leg start, and the T5 peach is the
plainest (close froze at 66.3 mm around a 68.9 mm fruit, the lift leg then started
at **54.5 mm**). (3) **The servo's own travel**: `closed > 0` on the `[task] force
servo:` row is **11/11 failed** vs **1/29** without it - i.e. the whole failure
set is one mechanism, the servo's chase to `FRUIT_DYNAMIC_FORCE_RANGE` (15 mm)
when the force sits under `max(2 N, 0.8*ref)` and `ref` reads **0.00 N**.
**Non-classes, measured so they are not re-derived**: starvation is a *wait*
(20/20 attempts ran in every cell; the failures' `descent` blocks are *longer*
than the successes'; the handover `queue` is 3.25 on successes vs 3.17 on
failures); the **diversion** is a *pool slot*, and its second attempt is a
**different instance** at seed 6 (`x` 0.299 -> 0.343) and the *same* one at seed 5
(0.239/0.241); and **P38b's low-tail margin purchase has no events** (delivered x
min **0.1998**, 20 mm above the left's 0.180 floor) - the tail that exists is at
the **top**. **Arm 1 (`PREREG.md` `07c54712`, cells `T5`/`T6`): the supply band's
top, `FRUIT_SUPPLY_X_MAX=0.36 -> 0.33`** - one RNG draw re-mapped by the band, so the release
schedule is the *same stream* and the treatment is the identical scenario with the
lateral position compressed by 0.8125 (the build row prints `lateral x=0.20-0.33`
in both cells). **Placed 16 -> 18 and 12 -> 18 (pooled 28 -> 36), `cnp` 9 -> 3,
never-held 3 -> 1, the chase 11 -> 5, the interval better at both seeds**
(10.59 -> 10.13, 11.08 -> 9.84; window 5.66 -> 5.92 / 5.41 -> 6.10; wall
2.91 -> 3.15 / 2.37 -> 3.35 placed/min), and the cleanest single read is the
**first attempt at seed 5**: the same slot, fruit, release time and
instrumentation, `x = 0.3908` -> never-held in the control and `x = 0.3616` ->
placed in the treatment. **Verdict NOT ADOPTED**: the pre-registered G3 fails -
T6's leg 1 reads `|v|max` **0.222 against 0.161 (38 % over)**, a different leg and
15x the excursion of the control's own standing branch leg (C6 leg 12,
0.164/0.160, +2.5 %), and the same seed's branch carries a **419 N** carry leg
with a **1313 mm** pad-centre bookkeeping offset - so the number is not the
argument (the same control swings 16 -> 12 between seeds). The mechanism claim is
the class set, not the rate: **the presentation column moves the closed class**
(the stations sit at a **band edge** of R10-A's top-down reach at x = 0.36 - left
`y 0.00..+0.10` with the station at 0.00, right `y -0.10..0.00` with the station
at **-0.10** - and at x <= 0.33 both are inside the x = 0.28 column's band).
**Arm 2 (`PREREG_A1.md` `e5150253`, cells `R5`/`R6`): `FRUIT_FORCE_REENTRY=1`**
(the documented default-off contact gate: run the servo only while the contact
estimate is confident, otherwise **hold** the gap) - the gate engages exactly where
the chase was (**31/29 mode entries, 890/1730 withheld chase ticks**, held-leg
`force_min` medians **9.42/9.36/9.72/9.10 N**, the P41 plateau intact), the chase
falls **11 -> 3**, and **the count does not move at all** (16 -> 16, 12 -> 12;
pooled 28 -> 28) while the classes **re-distribute** (`cnp` 9 -> 8, never-held
3 -> 4, five `grasped, not placed (no note)` rows) and the interval gets *worse*
at both seeds (10.59 -> 11.59, 11.08 -> 13.48). **G2 fails at seed 5** (`cnp`
3 > 2) -> **NOT ADOPTED**, and the finding is the phase's most transferable one:
**the chase is the signature, not the cause** - with the chase withheld the
payload still leaves, and the attempt then presents as never-held. The gates-on
branch also **re-draws into the high-x tail** (R5 x = **0.405**, R6 **0.388 /
0.364**), which is what arm 1 bounds. **No-harm** (the tree is inert): the
controls replay `logs/p91/{C5,C6}.log` **1033/1033** and **970/970** modulo one
profile row's `origin` label (`(explicit)` vs `(two-line)`; the resolved clock is
identical - P87's A1 convention), `scripts/selfcheck.sh` **PASS (0 failures)**,
`scripts/accept.sh` **7/10 + `fingerprint: matches configs/motion_reference.json`
+ `190: PASS`** (this tree's standing branch), `python3 scripts/211_bed_audit.py`
**ok (115 checks)**, and every landing is clean (**64/64** payload-present
releases `on_belt`). **The named re-entry, priced and not executed**: diagnose
T6's leg 1 and the 419 N leg, run a **third seed** (two seeds at 18/20 is
suspiciously tight), and if clean, land the full package - both motion references
re-recorded from same-batch runs, the acceptance/two-line gate re-based, every
store re-baselined, the **`supply.x_min/x_max` manifest field** added first
(`assets.scene_provenance` does not carry the supply band today, so a store under
0.20-0.33 and one under 0.20-0.36 are indistinguishable), and the direct/policy
interface measured (it builds its own profile from the same
`SupplyPlan.from_env`). **Re-baseline: none** - nothing shipped, so every rate,
acceptance, reference and store on the tree stands unchanged. Pins: `tasks.py`
**`7ba4bb58`**, `bimanual.py` `9b7fc33f`, `fruits.py` `dcabe16b`, `scene.py`
`3681aad3`, `assets.py` `540406fa`, `control.py` `9384ff4f`, `conveyor.py`
`fb2c58c6`, `rl_env.py` `e618ae67`; `configs/motion_reference.json` =
`..._twoline.json` = **`423896f7`**, `..._single.json` = **`8952c320`** (all
untouched); ckpt `moe_v13s` `61da390a`; new instruments `census.py` `2a59e74d`
and `chase.py` `b36a1c75`, reports `p92_report.py` `aebc0a3b` /
`p92_a1_report.py` `2d39924c`. Evidence `logs/p92/{CENSUS,RESULTS}.md`,
`{PREREG,PREREG_A1}.md` + their `.md5`, `census.txt`, `chase.txt`,
`p92_report.txt`, `p92_a1_report.txt`, `header{,_r}.txt`, `run_p92.sh`,
`run_p92_a1.sh`, `gates.sh`, the cells `{C5,T5,C6,T6,R5,R6}.{log,stamps,driver,
budgets}`, `accept_noharm.log`, `selfcheck.log`; WORKLOG "P92".

**P93 (2026-11-02, `logs/p93/`; the re-entry, and the band still does not ship -
the **third and fourth seeds refute P92's count**, while both of P92's red flags
are **branch artifacts** and the only shipped change is metadata): the phase
diagnosed the two guard failures, added seeds **101** and **202**, and applied
P92's rule to four seeds. Nothing about the criterion moved:
`FRUIT_SUPPLY_X_MAX` stays **0.36**.

**The two red flags (PREREG §1, `logs/p93/diag.py` → `diag.txt`).** Both are on
**one attempt** (seed 6, attempt 0, the right arm's first kiwi), read from a
`FRUIT_DYNAMIC_TRACE=1` per-tick trace of `descent`/`catchup`/`close`/`carry`
(`logs/p93/p1/{D6C,D6T}/trace/`; the two cells reproduce the untraced P92 cells
**to the number** - `0.108/10.6 mm` and `0.222/58.9 mm`, `480.6` and `1169.1 mm`
- and were each run twice, so the event is deterministic and the trace is
run-neutral at that attempt). **(a) `T6`'s leg 1 is a *jam onset*, not a chase.**
The leg's target is fixed and open-loop (`intercept=-0.0831`, the same 88
commanded samples in both cells), so a chase is excluded **by construction**;
over the leg the payload moves `90 mm` at **exactly the belt speed** (0.123 m/s)
and `~0 mm` in `z`, so the leg does not displace it; at the **first tick after**
the leg the pads read **71.1 N over 2 contacts** with the jaw span closing
97 -> 76 mm around a 62 mm kiwi, and the payload is then driven **down through
the belt** (`z` 1.197 -> 0.005, peak `|vz|` 4.6 m/s; the control does the same,
41.8 N and `z` -> 0.818). Both payloads are **already at 2.4x belt speed when the
leg starts** (`0.284 / 0.286 m/s`, ~4.2-4.7 rad/s of spin), so the disturbance
**predates the leg and is present in both arms**; its source is **open** (no
trace covers the wait/pre-pose window; the leading candidate is the other arm's
pre-pose transit, whose 1.9-2.6 mm minimum separation the record already
measures). `PREREG` §1a's binary reading is **not applicable as written**: the
`descent` phase is traced **once**, at the leg's start (`tasks.py:11509` emits
before the profiled descent), so there is no per-tick contact read inside the
leg - recorded as deviation **D2**. **(b) the 419 N / 1313 mm leg is a
*bookkeeping artifact with a physical consequence***: all three registered
clauses pass. `|offset| = 1313 mm` against the hand's own tool scale of **70 mm**
(`_pad_standoff`) and **20-62 mm on every other leg of the batch**, and the
payload sits **1180 mm** from the fingertip (1132 mm of it in `-z`); the
commanded `jaw_target` is **1313 mm** from the measured pads
(`centre=[0.1986,-0.518,1.2467]` -> `[-0.2838,-1.0006,2.3689]`); and the pads
*are* on the payload (`contacts@onset=1`, `sep@onset 46.6 mm` inside a 61.6 mm
fruit). The path: `_gripper_offset[side]` is set to
`rot.T @ (payload - tcp_position())` at the grasp routine's start
(`tasks.py:11047`) - a *tool* offset only while the pads are on the payload -
and it is applied **only** in `_carry`'s **incoherent** branch
(`centre - rot @ offset_tool`, `:5361-5366`), which - unlike the coherent branch
(`:5331`) and the place loop (`:6079`) - **does not consult `hand_is_jaw`**, so
the payload's distance becomes a commanded 1.3 m jump (the 419 N, the 1.545 m/s
in-hand peak and the 2361 mm `clean_slip_max` are that arm flight). **The
control carries the same defect at a smaller amplitude** (116 mm, `fmax 0.00 N`,
a 380-tick lift leg). **Per PREREG §1c both are branch artifacts** (present in
the same-seed control; the monotonicity route needs two seeds carrying the
event and only seed 6 does - seeds 5's attempt 0 reads `5.9 mm` in **both**
arms), and the per-instance witness is the direction: that attempt delivered
**`x = 0.2507` (T) against `0.2447` (C)**, i.e. 6 mm *further out*, the wrong
way for the band's own 0.8125 mapping.

**The seeds (PREREG §2, one claim per cell, 20 attempts, P92's instrumentation
verbatim).** Controls read **16, 12, 15, 15** and treatments **18, 18, 14, 15**
of 20; the class ledger is never-held **`2->0 / 1->1 / 0->0 / 2->1`** (pooled
**5 -> 2**, Fisher **p = 0.4426**) and `cnp` **`2->2 / 7->1 / 5->6 / 3->4`**
(pooled `17 -> 13`, p = 0.544). **So the class clause passes at every seed and
the count does not**: pooled placed **58/80 (72.5 %) -> 65/80 (81.3 %)**,
two-sided Fisher **p = 0.2604**, and **the whole pooled gain is seed 6's +6** -
the two fresh seeds read `15 -> 14` and `15 -> 15`. **The two fresh controls are
`15/20` twice against seed 6's `12/20`**, so P92's `28 -> 36` was measured
against the *worst* of the four control branches the tree has. The delivered
side follows the count, not the band (interval `10.59->10.13` and `11.08->9.84`
but `12.16->13.28` and `11.53->12.51`; `placed/min wall` `+/-`, the wall column
being the harness). **Verdict: NOT ADOPTED**, on three named clauses: rule 2
(seed 101's placed count falls `15 -> 14`), **G1** (`cnp` rises at both fresh
seeds), and **G3** (`T202` leg 14 `0.183/0.161`, +14 %). **G3's reading is the
phase's most transferable one**: the four over-budget legs of **160** sit **two
in controls** (`C6` leg 12 +2.5 %, `C101` leg 9 `0.224/0.160` = +40 %) **and two
in treatments** (`T6` leg 1 +38 %, `T202` leg 14 +14 %); they are **uncorrelated
with the catch-up** (`C101` leg 9 and `T202` leg 14 run clean catch-ups; `C5`'s
two missed catch-ups `251.0 / 87.6 mm` run descents **inside** budget), so the
over-budget descent is a **stochastic branch property at 2.5 % of legs in either
arm** - which is what AGENTS §2 means by "the ratio has no clean gap". The budget
was **not** re-tuned. **The power statement, for whoever wants it certified**:
at the observed 8.75-point pooled difference the two-sided 0.05 / 80 %-power
sample is **364 attempts per arm**, with the **never-held class** as the
endpoint and the count as a report - not another two-seed batch.

**What shipped is metadata only, and it was PREREG §6's precondition for any
recollection**: `assets.supply_provenance(plan)` - the resolved **band**
(`x_min`/`x_max`), the along draws, the two **mixes** and the **resolved schedule
name** (`bed > patch > wave > scatter`, else `fixed`) - called by **both**
manifest writers under the same key **`supply.band`**
(`scripts/40_collect_demos.py` and `SortingRLEnv._supply_band_provenance`), so a
collection store and a direct/rollout store name their band identically. **The
gap it closes is specific**: the *collector's* shard manifest already carried
`supply.x_min`/`x_max` and both mixes (`datasets/v12d_s02/manifest.json` reads
`x_max: 0.36`), while the **direct env's** rollout manifest carried only its P58
profile block - no band, no mix. A store without `supply.band` predates P93.
Pinned in the existing provenance leg (`scripts/239_p72_clr_edge_selftest.py`
gained a section 6: the signature, the arithmetic, all four branch orders, the
`SupplyPlan` field set read from the dataclass's own AST, one call site per
writer). **No stream effect**: `scripts/selfcheck.sh` **PASS (0 failures, 1
skipped)**, `scripts/accept.sh` **7/10, 9.4 s/attempt, `fingerprint: matches` + `190: PASS`**
with its **449 `[fruit]` lines byte-identical (449/449)** to
`logs/p91/accept_final.log` (`logs/p93/accept_noharm.log`), `211` **ok (115 checks)**,
`106` OK, `107` **PASS (21 checks)**; the landing guard is **123/123**
payload-present releases `on_belt=True` across the eight cells and G6 is 8/8 at
20 attempts with **no lost slot**. **No motion reference was re-recorded and
none is owed** (`423896f7` / `423896f7` / `8952c320` all stand). Pins: `tasks.py`
`7ba4bb58` **untouched** (so `rl_env.TASKS_MD5` stands), `assets.py`, `rl_env.py`
and `scripts/40_collect_demos.py` each carry only the new builder and its one
call site. Evidence `logs/p93/{PREREG.md,PREREG.md5,RESULTS.md,diag.py,diag.txt,
p93_report.py,p93_report.txt,run_p93.sh,gates.sh,header.txt}`, the cells
`{D6C,D6T,C101,T101,C202,T202}.{log,stamps,driver}`, `{C101,T101,C202,T202}.budgets`,
`p1/{D6C,D6T}/`, `accept_noharm.{log,driver}`, `selfcheck.log`; WORKLOG "P93".

**P106 (2026-11-03, `logs/p106/`; a probe in `logs/` - **no `src/` or `configs/`
change, nothing adopted, no commit, all three references untouched**): the hand
stage's **M1 and M2a**. The **Allegro 16-DoF USD mounts in this scene and the
close+lift gate fails as a rate (1 of 4 cells)**, and **M2a's kill does not fire**
because the **4-pad radial surrogate clears 1.5x on both legs on every fruit**
(sustained **1.98 / 1.87 / 2.05x**, 2 mm **1.82 / 1.80 / 2.10x**, creep
**0.25 / 0.15 / 0.11 mm** against the pinch's **3.20 / 0.85 / 2.68**), while the
**Allegro is not evaluable**: one of four draws held, three dropped the payload at
the first release, and its drive cannot be brought to the pinch's 4.90 N per
contact. **The mount, structurally, passes**: the asset references under
`/World/OpenArm/openarm_left_ee_tcp` and welds with a `PhysicsFixedJoint`, the
merged articulation reads **38 DOF = 22 arm + 16 hand** with the hand half pinned
by name/order (`index/middle/ring/thumb _joint_0..3`) and its limits in radians
(`index_joint_1` `[-0.279,+1.728]`), a `+0.300` command reads `+0.2894`, the hand
is **2.135 kg** over 21 bodies (the plan carried ~1.1 kg), and the **tool offset
that replaces `_pad_standoff`'s 70 mm is 170.7 mm** along the tool axis at the
sweep's mid posture (**100-216 mm** across it) - so it must be re-derived per
posture, not copied. **Two defects cost the phase and are recorded, not
worked around**: the asset's `root_joint` is a **world** anchor and
`stage.RemovePrim` does **not** defeat a prim that comes from a reference - it
survived, pinned the hand to the origin, and destroyed the articulation (arm joint
1 read **-82.19 rad** against a -3.49 limit and a `+0.3` command moved it
**-34.39**); `prim.SetActive(False)` is the fix. And **`ArmController.move_to`
stalls 186-326 mm short** from the hanging rest pose (measured twice, direct and
through a 40-waypoint line, with the tool axis tilted up to 30 deg), so the probe
**teleports to the shipped `ready` waypoint** and the phase does not claim a
station. **The close+lift gate**: 1 of 4 draws - the pear held once (**+59.7 mm**,
read by the primitive's own `>4 mm` test) and the recorded re-run of that same
configuration did **not** reproduce it; that one hold had already **crept
39.75 mm** under 0.82 N (**12x the pinch's 3.20 mm, 40x the plan's 1.0 mm**); the
other three dropped to
the floor (creep 1.07-1.09 m), and the mechanism is visible in the read - the
fingers **knock the payload out of the seat as they close**. **The drive tune the
plan asks for is not achievable through a torque cap**: at the asset's `k=1e7` the
pear reads **no contact at 0.46 N.m and 10.5 N per contact at 0.48** - a step
function, i.e. §1.4's warning measured; a softer drive (`k=20`, `c=0.4`) gives
2-6 N but no trustworthy force instrument on this asset (a per-link contact view
reads `Physics contact view is not valid` or reports 60-90 mm-away fingers, and
`get_dof_gains()` returns **5.73e8** against an authored `1e7`). **The phase's
central measurement is topological**: the three fingers span **116-123 mm** and
the thumb sits **43-208 mm** from their centroid, so **at most 3 of the 4
fingertips can touch one 37-66 mm payload at any posture in a 4 x 4 sweep** (2 for
the 60.6 mm pear at most postures, 2 for the 37 mm strawberry) - a 60 mm fruit is
smaller than the hand's own tip spread, which is the mechanism the plan's §1.7
"`n_eff ≈ 2`" arithmetic was reaching for. **The predicted 1.2-1.6x is therefore
neither confirmed nor refuted**; the one holding draw reads **1.24x at 2 mm** (in
band) and **>3.63x sustained** (bounded, out of band, at an unmatched force).
**So M1 passes on the mount and fails on the grasp, M2a's kill does not fire on
the surrogate, and the licence is for a *shape* - radial/enveloping, not
anthropomorphic 3+1 - not for a product**: no buyable hand was measured, the
surrogate cannot approach or run a precision grasp, and the purchase itself stays
the owner's (the plan's M3 gate is untouched). **M2b (approach) and M3 (scripted
hand) are unspent**, and the Allegro's own failure mode here - batting the payload
out of the seat during the close - is exactly the class M2b would have to score.
`configs/` untouched (`30fb99f8` / `30fb99f8` / `8952c320` stand), no reference
re-recorded (the scripted line never runs this code), `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)** - the phase adds no `src/` code and no leg.
Pins: `docs/HAND_STAGE_PLAN.md` carries the measured M1/M2a rows;
`logs/p106/{METHOD.md,RESULTS.md,m1_mount_probe.py,run_p106.sh,mount_census.txt,
m2a_allegro.txt,m2a_control.txt,inspect_allegro.py,units_probe.py}`; ckpt
`moe_v13s` `61da390a`. Evidence `logs/p106/`.

**P107 (2026-11-03, `logs/p107/`; one **default-off** fifth hand kind
(`FRUIT_GRIPPER_KIND=cage4`), no shipped default moved, `configs/` untouched):
the owner's decision to build the radial shape rather than buy a product; the
retrofit is built and measured, **M2b's letter passes and its mechanism fails, and
M3's kill fires.** The asset is exact (`logs/p107/m1_cage.txt`): **4 pads** at
0/90/180/270 deg, **one scalar closure**, **aperture 120.0 -> 26.0 mm measured =
commanded** (0.0 mm error on both axes at every rung), the **tool offset that
replaces `_pad_standoff` is 70.00 mm with a spread of 0.00 mm over nine
apertures** - derived, not copied (`DISTAL_Z` 80.5 - `LIP` 10.5), and constant
because the synergy is radial only; the shipped **lip 10.5 mm** and **distal plane
80.5 mm** are unchanged; the drive is k 1e5 / c **100** Ns/m at a **4.90 N/pad**
cap and the delivered per-pad force median is **4.90 N** (max 87.85 N, only where
the fruit does not fit the closed ring); the pad-pad corner gap is **+66.5 mm
open -> +2.8 mm at a 30 mm aperture** (no self-intersection). **M2b** (15 attempts,
seed 5, `FRUIT_CAGE_PROBE=1`): **no-contact 1/15** - the plan's `<= 1/15`, so the
kill does **not** fire - but the **enclosure is 2/15 at >= 3 pads**, the payload is
displaced **15-107 mm relative to the belt on 7/15 closes** and the
**cage-vs-payload clearance on the descent is `-0.3..-33.4 mm` on 7/15** (the face
planes go *through* the fruit). **The registered endpoint cannot see a cage that
misses**: a close that arrives beside the fruit still loads a pad; the endpoint to
register next time is the enclosure + the relative displacement. **M3** (10
attempts at the acceptance's two seeds): **2/10 at seed 5 and 1/7 at seed 6**
against the **same-tree, same-seed shipped-hand controls' 6/9 and 7/9** (pooled
**3/17 = 17.6 % vs 13/18 = 72.2 %**), the carry legs in the **no-contact/ejection**
class (`force_min == 0` and `clean_slip > 100 mm` on **29 of 43**, median 407-614
mm) rather than the closed loaded slide, budgets **4 of 43 descents at 1.1x** (P93's
stochastic branch property, not re-tuned), `s/attempt` 15.3/15.9 vs 14.8/14.3, and
the **landing guard not measured** (no `FRUIT_PLACE_TRACE` in those cells - a named
gap, not a pass). **The blocker is the aim, quantified**: the fruit can enter the
descent **24 mm** off the cage's axis (a point hand's aim; the shipped jaws' 98 mm
gives ~14 mm of slack), so the open cage needs **>= 118 mm** of aperture, while the
supply's along-belt spacing is **85-120 mm** - a wider cage fouls its neighbours;
and four 61 mm plates at 4x90 deg **cannot close below a 61 mm aperture**
(`pad width <= aperture`), so the plate's width was cut to 26 mm
(capacity-neutral: `F_crit = n mu N` is area-independent) and its length to 60 mm
(the shipped 84.9 mm puts its proximal end **4.4 mm above** the jaw centre, inside
the OpenArm's palm). **Seven measured iterations** are in `logs/p107/METHOD.md` §2
(the 61 mm plates jam, **69-100 N/pad**; the plate-inside-the-palm contact thrashes
the arm, `|a|max` 2421 m/s2; the OpenArm's fingers keep their **asset** colliders
even with `FRUIT_FINGER_COLLIDERS=0`, freezing the aperture at 89 mm - disabling
them is the fix that first produced a hold; `c = 2000` is numerically unstable for
a 0.020 kg pad on a standalone joint, `c = 100` is P104's own near-critical pair; a
hand on the tool must ride the arm **every tick** or it parks in the supply's path;
the open aperture must swallow the pursuit error; a radial close must use the
fruit's widest horizontal extent). **The next spend is a centring step or a
workstation, not a hand and not a policy.** No-harm: `scripts/accept.sh` reads
**8/10, 9.0 s/attempt, `fingerprint: matches`** with its **421 `[fruit]` lines
421/421 byte-identical** to `logs/p103/accept_final.log`; `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**. Re-baseline: **none** - every number above is
opt-in, `configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`** stand. Pins: `cage_hand.py` (new), `tasks.py`
(`RIGID_TOOL_HANDS`, `_pad_standoff`, `_fingertip_offset`, `_hand_separation`,
`pinch_width`'s radial branch, `track_arm`, the `[cage]` census), `scene.py`,
`tactile.py`; ckpt `moe_v13s` `61da390a`. Evidence `logs/p107/`.

**P108 (2026-11-03, `logs/p108/`; the owner's **option 2** - widen the cage's
aperture AND the supply's along-belt spacing - **built with the two knobs that
already existed** (`FRUIT_CAGE_OPEN_FACE_R`, `FRUIT_SUPPLY_GAP_MIN`), so **no
`src/` or `configs/` change, nothing adopted, no reference re-recorded**): **the
phase is refuted as stated.**  The aperture is a **robust actuator for exactly one
class - the approach collision - and a draw for every outcome the registration
names**: the **enclosure at >= 3 pads** reads **5/51 = 9.8 % -> 10/57 = 17.5 %**
(Fisher **p = 0.28**; it doubles, but the registered **+30 point** bar is not met)
and the **placed count 10/51 = 19.6 % -> 16/57 = 28.1 %** (**p = 0.37** - better at
seeds 5 and 6, **worse at the fresh seed 101**: 3/18 -> 7/19, 3/14 -> 6/18,
**4/19 -> 3/20**, which is exactly why P93's fresh-seed rule exists).  Decisive is
only **`clr < 0` 32/51 -> 4/57, Fisher p = 1.4e-8**.  **The spacing half fails its
density guard** (`GAP_MIN` 0.10 -> 0.15 costs **5 starved slots of 20 against 1** at
seed 5, 3 vs 2 at seed 6) and the placements fall to **6/35 = 17.1 %**.  **The
census rewrites P107's "24 mm".**  It is **not** a grasp-time figure and **not** a
lateral one: the **close-time** aim is `|dx|` **3.4 mm** / `|dy|` **1.1 mm** /
radial **4.5 mm** (p50, **726** `FRUIT_DYNAMIC_TRACE` attempts already on disk,
`logs/p108/close_aim.py`), while the payload sits **83 mm upstream** (p50; p5 82 /
p90 85, **3963** `[task] dynamic descent: fruit dy` rows) when the descent starts -
the line's own lead, of which **18 mm is `FRUIT_DYNAMIC_DESCEND_MARGIN`'s 0.15 s**
at 0.12 m/s.  The **binding window** is the descent, because the plate (60 mm long,
**20.5-80.5 mm below the jaw**) and a 60-70 mm payload's sphere overlap over
**~130 mm of `dz`**, i.e. almost the whole 55-60 mm leg: the pads enter the
payload's band **14.5 mm in**, when the payload is still **55.8 mm upstream** (p50,
max 61.7) and only **11.8 mm lateral** - an **83-89 % along-belt** split (the
lateral tail, 60-70 mm, belongs to the attempts whose x-tracking lagged).  Measured
per tick by **`FRUIT_FRUIT_TRACE=2000 FRUIT_FRUIT_TRACE_ARM=1`** on the cage cell
(`logs/p108/tr_cage_s5/`, `census.py`), and **the instrument is inert**: the cell's
**502 `[fruit]` lines are 502/502 byte-identical** to P107's own `m2b_s5.log` with
the trace/cycle/`[cage]` rows dropped.  **The geometry**: `A = 2 (offset + r +
4 mm)` gives **`A_y` 181.6 (p50) / 216.6 (p90) mm** with the pool's 35 mm `r_max`
and `A_x` 83.7 (p50); the offline per-tick screen reproduces P107 exactly - **120 mm
passes 0/8 windows, 160 5/8, 210 7/8** - and **the oblong does not pay**: a narrow
86 mm lateral axis fails the 60-70 mm tail (`oblong 86x210` 5/8 against
`round210` 7/8), so a genuinely narrow lateral needs a centring step first.  **The
spacing** the 200 mm aperture demands is `A/2 + 10 (plate) + 35 (r_max) + 4 =
**149 mm**` against the scatter's planned **0.10-0.35 m**, but the delivered line
met it in **every** census window (**0 neighbours inside the 0.15 m filter, 0/8**):
the spacing is a margin purchase against a collision never observed.  **The
battery** (scripted single arm, `ATTEMPTS=20`, every arm carrying
`FRUIT_CAGE_PROBE`+`MOTION_REPORT`+`CARRY_DIAG`+**`PLACE_TRACE`** - P107's M3 cells
had no landing trace): **S** (shipped hand) **25/38 = 65.8 %**, **B** (cage120)
**10/51 = 19.6 %**, **E** (cage200) **16/57 = 28.1 %**, **C** (cage200 +
`GAP_MIN=0.15`) **6/35 = 17.1 %**, at seeds 5/6/101 (S and C at 5/6).  The cage's
descent `end=` is **57.9 mm (p50) at B s5** against the shipped hand's 8.9-9.1 mm -
the 120 mm pads **block the leg** on half of *that* seed - and **9.3-10.5 mm** at
E's three seeds; B s6/s101 already read 10.1/10.3, so the blocked-descent class is
a **seed-5 branch property**, not a general cost of 120 mm.  **The enclosure's
histogram is bimodal - 4 pads or 1-2, never 3** (`{0:2, 1:6, 2:8, 4:3}` at 200 mm):
the payload is or is not centred when the ring closes, and **the closure depth is
not its actuator either** (a post-hoc `FRUIT_GRIPPER_SQUEEZE=0.94` cell, a 6 %
interference instead of 2 %, reads **1/17**), because the shipped target is
`pinch_width * 0.98` on the payload's **widest horizontal extent** (P107 iteration
7) - the two pads on that axis touch at the 4.9 N cap while the two on the narrow
axis stand off by `(widest - narrow)/2 + 2 %`, and a deeper command only pushes an
off-centre payload further off.  **Verdict: not adopted.**  The aperture is worth
having as a **precondition** (the approach clears, p = 1.4e-8); the spacing is not
affordable; and **the term that holds the placed count at 28 % is the centring**,
i.e. P107's other fork.  **Option 1 is therefore the cheaper route for the
enclosure but not sufficient alone** (it cannot remove the 56 mm along-belt
arrival): the cheapest *complete* package this phase prices is
**`FRUIT_DYNAMIC_DESCEND_MARGIN` 0.15 -> 0** (an existing knob; it is 18 of the
83 mm, so `A_y` p50 falls **181.6 -> 145.6 mm**, which the **160 mm** cage already
half-passes) **+ a 160 mm cage + a centring guide at the station**, and that is a
registration of its own.  No-harm: `scripts/accept.sh` with every knob unset reads
**8/10, 9.0 s/attempt, `fingerprint: matches`, `190: PASS`** with its **421
`[fruit]` lines 421/421 byte-identical** to `logs/p107/accept_noharm.log`;
`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**;
`python3 scripts/211_bed_audit.py` **ok (115 checks)**.  Landing guards:
payload-present releases land `on_belt` on **S 25/37, B 10/21, E 16/28, C 6/15**
(the misses are the upstream-lost `release_bottom = -184 mm` class); descent
budgets clean on S, and the cage arms carry P107's ~2.5 %-of-legs 1.1x plus the
blocked-descent `end/len` 1.02-1.27, **not re-tuned** (AGENTS §2).  Re-baseline:
**none** - every number above is opt-in, `configs/motion_reference.json` =
`..._twoline.json` = **`30fb99f8`** and `..._single.json` = **`8952c320`** stand.
Pins: **`tasks.py` `9e3e657b`, `cage_hand.py`, `scene.py` `472bfb6c`, `assets.py`
`540406fa`, `fruits.py` `dcabe16b` all unchanged by this phase**;
`logs/p108/{PREREG.md (md5 7ea6662054fa2acdf490042c0737e662),CENSUS.md,
RESULTS.md,census.py,close_aim.py,census.txt,p108_report.py,p108_report.txt,
run_p108.sh,cells.sh}`, the cells `{S,B,E}_{5,6,101}`, `{C}_{5,6}`, `E_sq94_s5`
and the traced `tr_cage_s5/`; ckpt `moe_v13s` `61da390a`.  Evidence `logs/p108/`.

**P123 (2026-11-06, `logs/p123/`; default off, **nothing adopted**, no `configs/`
reference moved, no commit): the owner's item 2 - a real **third output destination** -
is built, measured and **works**: a third belt + chute + **own tray** inboard on -Y,
whose place point passes the reach solve and whose payloads land in tray 2, while the
shipped two-lane scene does not move.** P122 fixed the frame (`logs/p122/SPEC.md` R0/R2):
a destination is a **physical output body**, the cell had **two**, and the binding term
for a third is the **place reach** (P90's `NAT`: x 0.38-0.48, |y| 0.35-0.55). The
owner's constraint still holds - the dynamic scattered pick pipeline is not stopped,
diverted, gated or paused, and a belt downstream adds no such element.

**The survey first** (static, stage bounds, `logs/p123/survey.txt`): pedestal `x
-0.300..+0.100, y +-0.350, top 0.790`; main belt `x 0.085..0.595, y +-0.864, z..1.215`;
each output body `x 0.025..1.950` with its **slab** `x 0.100..1.200, |y| 0.425..0.675,
z 1.300..1.350`, legs at `x 0.0255..0.0755 / 1.100..1.150`, chute `x 1.196..1.388,
|y| 0.418..0.682`, tray `x 1.350..1.950, |y| 0.380..0.720, floor 0.900..0.920, rim
1.060`; robot at rest `x -0.155..+0.095, y +-0.238, z..1.563`. **The free space at the
output deck is `|y| 0.000..0.425` inboard (in reach) and `|y| > 0.675` outboard (outside
P90's box)** - and of the inboard band only `|y| 0.28-0.40 at x >= 0.48` is both
reachable and clear of the place transits.

**The three candidates, priced offline before any body was authored**
(`logs/p123/layout.py` -> `layout.txt`; place point, release = commanded + P122's
measured offset, the crossing of every *other* lane's inboard edge as a **delta from the
shipped crossing**, the bodies and the camera). **A** - a third parallel belt **inboard
on -Y**, `|y| 0.280..0.395`, **x-offset downstream** (0.480..1.200): **PASSES** (place
in the reach box; delivered 48/59 mm inside the 0.115 m slab = 7-8 sd; **no transit
crosses it** - the payload, radius included, is at x 0.469 where a transit passes its
band, 11 mm upstream of the belt; 0 cm^2 of new camera occlusion because it is
downstream of the supplied fruit's x band 0.148..0.413). **B** - **split the -Y belt
into two** narrow belts (full x) with places (0.48,-0.35) and (0.38,-0.55): the reach
passes at both but the **transits cross**: lane 2's over lane 1's edge is **-9 mm** of
predicted direct-low `clr` -> **KILL**. **C** - outboard, `|y| ~0.70`: P90 `NAT` is
41-108 mm at |y| 0.65, the slabs overlap and it covers the arrival band -> **KILL**.
The x-offset is the design's load-bearing move: inboard bodies lose `0.30 mm/mm` of
direct-low-lift clearance (P90 `COST.md` section 1), 44 mm for this band, and only the
x-offset avoids paying it.

**The reach solve is measured, not inferred** (`logs/p123/probe.txt`,
`probe_rows.json`; P90's `NAT` mode, seed `grasp_lift`, restarts 1, 160 cells at x
0.38-0.48 x |y| 0.30-0.55 x z 1.450/1.530 x 2 arms; gate `res <= 6 mm`, `margin >= 0.05
rad`, `pad >= 2 mm` over the surface actually under the pads, `tilt` 60-110 deg):
**93/160 pass**, the inboard band at **x 0.43-0.48** (res 5.6-6.0 mm, pads +49..+56 mm
left / +63..+70 mm right over the new slab, margins 0.42-0.49 rad) and **x = 0.38
fails** (8.2-8.4 mm) - a hard inboard-x edge, which is why the place x is 0.48. The
chosen cell `(0.48, -0.30)`: **6.0 mm / +0.457 rad / +70.2 mm / 92.7 deg** at the place
height, **6.0 mm / +143 mm / 100.5 deg** at the transfer; the live startup solve reads
**11.5 mm** against the descriptor's 25 mm bar (the shipped lanes' `verified` is
14.9 mm).

**The build is one table, default off**: `FRUIT_OUTPUT_LANES=3` (default **2** = no body
authored, byte for byte). `SceneConfig.output_lane_layout()` is the single reader - the
builder (`conveyor.OutputBelt` takes a lane), the scene (`scene._add_output_belts`
iterates it), the belt/tray/discharge tests, the arms' drop points and
`assets.scene_provenance` - so a lane cannot be half-added. With 3 lanes the -Y side
gets a belt `x 0.480..1.200, |y| 0.280..0.395`, top 1.350, the same plate/speed 0.12/
friction/`PhysxSurfaceVelocityAPI`/discharge as the other two, **its own chute (0.10 m
wide) and its own tray (0.60 x 0.14 m, |y| 0.260..0.400)**, and the shipped -Y tray
narrows 0.34 -> 0.20 m (50 mm of air between trays); 30 mm of air to the -Y belt, 16 mm
between chutes. `scene.output_lanes` in the manifest has 2 entries shipped and 3 with
the body (`logs/p123/manifest_scene_{two,three}_lane.json`), the only change in the
first two being the -Y tray's width. The destination is a P114 descriptor entry
(`logs/p123/three_dest.json`, id 2, `reach: auto`) and the capability map keeps its
physical meaning: `-y` -> **right** arm (`left=[0] right=[1, 2]`). Tests, per lane and
generalised only in the sense that matters: `on_output_belt`/`on_output_tray`/
`on_output_discharge` agree with the pre-P123 expressions on a dense grid for two
lanes, and the new `output_tray_of` names the tray (the census). `tasks._payload_clearance`
now walks the lane list **signed and x-gated** (a lane charges only a sample over its
own x span and on its own side) - which is what keeps the shipped numbers identical and
what makes the third lane honest, because the payload crosses its |y| band *upstream of
its x span* and is over the main belt there; `_output_belt_edge_y` is per **side**.

**The cell** (20 attempts, the shipped scripted two-line, P92's four instruments in
every arm, one claim per run; instruction `grade=A => 0`, `grade=B and size<66 => 2`,
`grade=B => 1`, `grade=C => skip`, linted first by `262` - 120 cells, dest0 40 / dest1
11 / dest2 29 / skip 40): **seed 5 17 -> 11, seed 6 12 -> 14** (pooled **29/40 ->
25/40**, Fisher **p = 0.19** - the sign flips between seeds, so nothing about the count
is claimed; per seed 0.06 and 0.33). **The endpoints are the tray and the ledger**: T5's
`[sort] coverage: pool=16 mapped=12 unassigned=0 skip=4 (dest0=6, dest1=2, dest2=4)` -
every destination gets traffic - and the ledger reads **`attempts=20 assigned=20
released=11 in_destination=11 mis_sorted=0 not_placed=9`**, per destination 4/5/**2**
placed (T6 reads `attempts=20 released=14 in_destination=14 mis_sorted=0 not_placed=6`,
dest 0 9 / **dest 2 5**, its pool drawing no B fruit above 66 mm so destination 1 gets
that seed's zero - the rule decides, not the lane), while the **tray census joins 25/25
with 25 agreements over the two cells** (dest 0 -> tray 0 x13, dest 1 -> tray 1 x5,
**dest 2 -> tray 2 x7**) and the settled-position read names the same belts (T5 lane 0 4
/ lane 1 5 / **lane 2 2**; T6 lane 0 9 / **lane 2 5**). **The new lane's two failures are not
at its place point**: they are truncated at the **lift** (`grasped=1 placed=0`,
`lift=+0.088/+0.077`, `clean_slip_max >= 8 mm` = the P10-C monitor), i.e. the closed
loaded-slide class (`logs/p42/SIM_LIMIT.md`), and the two attempts that reached the
place leg both landed in tray 2 at `(0.50,-0.32)` and `(0.51,-0.31)`. **A measured
correction to the release offset**: on the shipped lanes T5 reads `(+50..60, +-30) mm`
(P122's `+48, +-35..37`), but on the new lane **`(+20..30, -10..-20) mm`** - the offset
is `0.070 x tool_axis` and the new pose's attitude differs (tilt 90 vs 78 deg), so the
delivered point sits 20-30 mm inside the slab's upstream edge (**2.5-4 sd, not 8**);
that is the one number a future form should widen (belt upstream end to x 0.46), with
n = 2 releases here. **Guards**: 11/11 payload-present releases on a belt; the descent
budgets PASS (20 legs, not re-tuned); the **arm-to-body clearance** on the 11 held place
legs is `clr` min **+76 mm** and `clr_edge` min **+75 mm** (C5 +57) - the new body is
never the binding surface; **no new failure-reason key** (`fruit did not follow the
gripper` only, in both arms); the loaded-slide census is 9/31 and 5/44 carry legs
against the controls' 3/37 and 6/44, and the **crush proxy fails its -15 mm letter in
both arms** (-20.4 vs -28.4 mm on held-loss legs - the pads closing past the fruit after the payload left,
P76's A1/A3 caveat and P100's A4 precedent: recorded, not re-read). **No-harm**: the
acceptance with the knob unset is **8/10, `fingerprint: matches`, `190: PASS`** with its
**421 `[fruit]` lines 421/421 byte-identical** to `logs/p121/accept_final.log`, which
also fixes the loop's first ten attempts (the substitute for the PREREG's "C5 replays
`logs/p92/C5.log`" clause - that record is 31 phases old and predates P100's park
profile / P102's tactile / P115's `rule=` field, recorded as a deviation).
**Adoption is the owner's call** and owes both motion references, a re-based
acceptance, every store re-baselined (a 3-lane store is a different collider set - its
manifest says so) and the direct/policy interface measured. **Read rules**: a
destination is a tray, so quote the **tray census and the ledger**, never a target
proximity; the place reach is the gate and it is **per-side** (a new body on -Y does not
move +Y); an x-offset body is not a carry obstacle only while the payload's
`+48 mm`-downstream offset plus its radius stays upstream of the body's edge (quote
both); and a 20-attempt two-line count is a branch (**17 -> 11 and 12 -> 14** here - the
sign flips, so quote the tray census and the ledger, never the count). Pins: `assets.py` **`072a2f11`**, `conveyor.py` **`2f7e6710`**, `scene.py`
**`b3bf8067`**, `tasks.py` **`50fd799d`**, `fruits.py` **`c8f19228`**,
`rl_env.py` **`3aed67b9`** (the metadata-only `TASKS_MD5` follow `78cce1ef` ->
`50fd799d`), `scripts/264_p123_output_lanes_selftest.py` **`8c400cc2`**,
`scripts/selfcheck.sh` **`8bdca9f1`** (the new leg), `238` **`4f40d093`** / `239`
**`9af1d6b5`** (re-pins),
`logs/p123/METHOD.md` **`35188439`**, `logs/p123/PREREG.md` **`07ae3c90`**,
`layout.py` **`6268881b`**, `probe.py`
**`3ae023d8`**, `three_dest.json` **`763968cc`**, `three_dest.txt` **`510719a8`**,
`p123_report.py` **`683e7a06`**; references **`30fb99f8` / `30fb99f8` / `8952c320`**
untouched; ckpt `moe_v13s` `61da390a`. Evidence `logs/p123/`.

**P124 (2026-11-07, `logs/p124/`; the owner asked to adopt the third lane, it was
**measured and reverted** - the default stays **2**, the third lane is opt-in,
and the references are restored to **`30fb99f8` / `30fb99f8` / `8952c320`**): the
**scripted** line takes the flip - the three-lane acceptance reads **7/10 = 70 %**
(bit-identical on a repeat), `190: PASS` after re-recording both references, the
single arm 6/10 (its standing rate-only branch) - but the **hybrid policy canary
collapses from 8/10 on two lanes to 4/10 twice on three**. The canary's failures
are the **pick-station** grip class (5 and 6 grip losses, one "fruit left the
pick station during the close", the P41 class), i.e. *upstream* of the new lane;
the mechanism is that the new body is in the **head camera's view** and changes
the stage's collider set - a scene change is an **input** change for a policy
trained on the old scene (P36's image channel, P71's collider-ordering shift).
A default that halves the interface of record cannot ship: the revert's
acceptance is **8/10 + `fingerprint: matches` + `190: PASS` with its 421
`[fruit]` lines 421/421 byte-identical** to `logs/p123/accept_final.log`.
**`FRUIT_OUTPUT_LANES=3` stays opt-in**, and the precondition for the flip is a
**policy recollection on the three-lane scene** (collect with `=3`, fine-tune,
then the same canary must read at or above the 2-lane control). **Read rule: a
scene flip is not proved by the scripted acceptance alone - the canary is the
second leg and it is the one that binds here; two samples of the
non-reproducible loop are the minimum, and they were taken.** Evidence
`logs/p124/`.

**P125 (2026-11-07, `logs/p125/`; the owner's recollection - **built and
measured, and it is a null with a correction**: the default stays **2**,
`FRUIT_OUTPUT_LANES=3` stays opt-in, no `src/` or `configs/` change, no
reference re-recorded): the three-lane recollection P124 named as the
precondition was built (store + fine-tune) and **does not reach the bar** - B
(`p125_three_lane`) **18/30 = 60.0 %** against A (`moe_v12`) **17/30 = 56.7 %**
on the same three-lane scene (3 samples each, interleaved), P1 fails (needs
>= 24/30) and P2 fails its letter (2 `unexpected` station escapes in B) - **and
the phase's product is what the same-batch two-lane control (report-only,
`PREREG_A2`) shows: C (`moe_v12`, **2 lanes**) reads 11/20 = 55.0 %, so
P124's "8/10 -> 4/10 twice is not a draw" was the canary's own 5-8/10 spread,
not a three-lane collapse** (A 56.7 % vs C 55.0 % = **+1.7 points**, inside
that spread at N=3). **The store** (`datasets/p125_three_lane`, local):
**196 episodes from 8 shard directories** (s0 19/30/28 seeds 501/502/503, s1
20/35 seeds 601/602, s2 28/17/19 seeds 701/702/703; 288 attempts, 96 left / 100
right, grades A 96 / B 100 - C skipped by the pure routing - **36,414 windows**,
`index_md5` **`38ec3a12`**), collected by the shipped two-line collector with
`FRUIT_OUTPUT_LANES=3` as the only scene change (`FRUIT_CAMERA_RES=240,424`,
wave + balanced mix, 17-success processes); **every shard's `scene.output_lanes`
has 3 entries** (lane 2 `/World/OutputBelt2`, place `(0.48,-0.30)`, tray
`(1.65,-0.33)`), **no wedge and no soft-watchdog skip**, all 8 runs exit 0. **The
fine-tune**: `moe_v12` (`3a9ccfc0`) -> **`checkpoints/p125_three_lane`**
(`69a468d0`), 6 epochs, lr 5e-5, `ones`, base `demos_v11`, 196 + 50 episodes,
**final weighted loss 0.025210, router 0.9833** (epoch 0 0.8234), demo_val
0.018226 - the candidate learned the store, so the null is not undertraining.
**The canary** (`accept_policy.sh`, same scene, `SEED=77`, 10 episodes/sample):
A 6/6/5, B 7/5/6, C 5/6; classes A 12 grip loss + 1 station escape, B 10 + 2, C
8 + 1 grasped-not-placed - **every failure is the pick-station grip class
(P41/`SIM_LIMIT`), upstream of the third lane; no failure is at the lane**.
**Read rules**: a non-reproducible loop at N=2 (P124) can call a scene
"collapse" that a same-batch control shows to be a draw - **a scene decision
needs the scripted line + the P123 tray census as its carrier, with the canary
reported (or a WS-4.2-scale N), never a 8/10 single sample**; and the binding
success term here is the closed pick-station grip class, not the scene. **No
harm**: the acceptance is **8/10, `fingerprint: matches`, `190: PASS`** with its
**421 `[fruit]` lines 421/421 byte-identical** to `logs/p124/accept_restored.log`;
`selfcheck.sh` **PASS (0 failures, 1 skipped)**, `106` OK (the store audits
`entries=196 files=196 windows=36414 OK`), `107` PASS (21 checks); the
references are **`30fb99f8` / `30fb99f8` / `8952c320`** untouched and the tree's
pinned md5s are unchanged before/after (`logs/p125/tree_md5_{before,after}.txt`).
Pins: `logs/p125/PREREG.md` **`6b236694`**, `PREREG_A1.md` **`bf98b7d6`**,
`PREREG_A2.md` **`badeea48`**, `p125_report.py` **`f20b99ae`**, the collector /
fine-tune / canary / control drivers
**`fab85b0e` / `007531a7` / `9a6f2cbb` / `2f35e7e1`**, `run_p125_flip.sh`
**`4f00ecb1`** (the flip recipe, **not run**); store `38ec3a12`, checkpoint
**`69a468d0`**, init `moe_v12` `3a9ccfc0`; ckpt `moe_v13s` `61da390a`
untouched. Evidence `logs/p125/`.

**P126 (2026-11-07, `logs/p126/`; **the third output lane ships - the default is
now 3**, `FRUIT_OUTPUT_LANES=2` restores the two-lane scene, and the references
are **`d258db1a` / `d258db1a` / `d15972cc`**): P124's revert rested on a canary
draw that P125 refuted (same checkpoint, three lanes **56.7 %** against two lanes
**55.0 %**), so the decision was **re-registered on the corrected evidence**
(`PREREG.md` **`fba4b9d4`**, pinned before the acceptance): the **scripted
acceptance at or above the 0.60 floor with clean motion budgets**, the **P123 tray
census (25/25)**, the single arm at its standing branch, and **the canary
reported, not gated** - a 55-60 % loop cannot carry a scene decision at N=1.
Measured: the three-lane acceptance **7/10 = 70 %**, budgets clean, **`190:
PASS`** after re-recording (a repeat is **423/423 `[fruit]` lines identical**);
the single arm **6/10** (rate-only, its fingerprint matching the re-recorded
reference); the canary **7/10 = 70 % PASS** (3 grip losses, no new reason) - the
top of P125's band, so the interface is not degraded by the scene. The `=2`
restore keeps every shipped scalar (the `264` leg's dense-grid equality) and the
pre-P126 records are archived at `logs/p126/motion_reference*_pre_p126.json`
(`30fb99f8` / `30fb99f8` / `8952c320`). **Re-baseline: every store recorded
before P126 is a two-lane store** - `scene.output_lanes` 2 (or absent, pre-P123)
= pre-P126, **3 = the shipped scene** - and the one existing three-lane store
`datasets/p125_three_lane` (196 episodes, all eight shards at 3 lanes) is now
**the shipped cell's store**; any pre-P126 two-line rate, interval, acceptance or
store is a **pre-three-lane number**, `FRUIT_OUTPUT_LANES=2` restores the scene,
and the old records are archived rather than deleted. The **per-scenario** references of the non-shipped batteries (`motion_reference_patch*.json`, `..._twoline_bed.json`) are **pre-P126** too and are re-recorded from their own same-batch runs when those scenarios are next used - they were not owed by this flip because they are not the shipped path. No rate is claimed in
either direction (P123/P124/P126 read 7/10 on this scene; the two-lane branch
read 8/10). Pins: `assets.py` **`3c8d2513`** (the default), `264` **`80f6b14d`**,
`259` **`5acefca6`**, `260` **`7f098ff6`**, `234` **`760be54b`**,
`selfcheck.sh` **`8bdca9f1`**; references **`d258db1a` / `d258db1a` /
`d15972cc`**; ckpt `moe_v13s` `61da390a`. Evidence `logs/p126/`.

**P127 (2026-11-07, `logs/p127/`; **the third lane's flip is reverted a second
time - on the right instrument**: **44/80 against 58/80, 4/4 seeds worse**, the
default is back at **2** and the references are restored to `30fb99f8` /
`30fb99f8` / `8952c320`): P126 shipped on the acceptance (7/10), the tray census
and the canary, and never ran a **20-attempt battery**. This phase ran it - four
seeds, the shipped two-line, no instruction, the third lane the only difference -
and the scene reads **12/8/11/13 = 44/80 = 55.0 %** against the pre-P126
controls' **16/12/15/15 = 58/80 = 72.5 %**: **-17.5 points, worse at every
seed**, with the class moving too (seed 6's grip losses **2 -> 10**). The
three-destination cell still works on the same tree (**11/20, ledger 11/11, 0
mis-sorted**): **the destination is fine, the scene's physics is the cost** - the
P71 lesson (a collider-set change re-draws the release geometry and the solver
order, so every grasp moves) applies to a body 140 mm from the pick station. The
restore's acceptance is **8/10, `fingerprint: matches`, `190: PASS`** (421
`[fruit]` lines, the two-lane scene). **The read rule is corrected**: a scene flip
is carried by a **20-attempt battery at >= 2 seeds with same-seed controls**; the
**acceptance is a smoke** (one attempt's 7 vs 8 hid -17.5 points), the **tray
census proves the destination** (not the cell), and the **canary is an interface
check** (flat here: 56.7 % vs 55.0 %). P126's carrier was the wrong instrument;
the third lane stays opt-in and the P125 store stays the three-lane candidate.
Evidence `logs/p127/`.

**P128 (2026-11-07, `docs/PORTABILITY_AND_INSTRUCTIONS.md`; design/handover only,
no `src/` or `configs/` change): the portability/instruction arc (P114-P127) is
closed out in one document for a reader who has not followed it.** It states the
two answers the owner asked for - a new pipeline is **a JSON + a solve + one
gate** (copy `configs/scenarios/shipped_twoline.json`, edit the fields, the
`auto` destinations solve at the 25 mm bar), and an instruction is **a text
file** (`grade=A => 0`, `size<40 => 1`, `species=apple and size>=66 => 2`,
`default`, `skip`, `!=`; first match wins; every refusal names file and line) -
with the **capability map** (left `+y`, right `-y`; an unreachable mapping is
refused), the **ledger** (`in_dest` from the payload's measured release; the
assignment accuracy is the endpoint, never the placed count), the
**direct/policy dispatcher** (goal channel, thread-local place target, 7+1
action untouched), and the **third destination** (a physical body; 25/25 tray
agreements; **-17.5 points** on the shipped cell, so opt-in). It records the read
rules that bite (a destination is a physical body; a scene flip needs a
**20-attempt battery**, the acceptance is a smoke and the canary is an interface
check; `FRUIT_SORT_STRICT=1` vs `skip`; overlaps are precedence; an `and` rule is
read by the **per-rule histogram**), what is **not** portable (colour/perception,
the tactile/force channels, the hand's limits, a third physical lane, a policy
destination channel), and the five-step migration recipe. Every number traces to
`logs/p114`-`logs/p127`; `106` OK. Evidence `docs/PORTABILITY_AND_INSTRUCTIONS.md`.

**P129 (2026-11-07, `logs/p129/`; two bench fixtures in `logs/` - **no `src/` or
`configs/` change, nothing adopted, no reference re-recorded**): the decision
book's nail (i) is measured and **killed on K2** - a four-pad ring **centres and
loads all four pads at the measured pair friction 1.35**, so `mu_pair < 1` is not
the term that decides the enclosure.  **The algebra first** (`algebra.py`): the
four-pad residual is **`mu s`**, not the book's `(2 mu - 1) min(s, cap/(2 mu k))`
- P111's headline formula is not what P111's own `closed_form` computes
(`mu s + mu_b m g/(2k)`) nor the 2-D geometry; the threshold `mu = 1` is right and
the residual is 2x smaller at `mu = 0.6`.  The **four-contact** state is a
*window*: a pad counts at 0.5 N, so `k in [0.5/(s(1-mu)), cap/(s(1+mu))]`, empty
above **`mu = (cap-0.5)/(cap+0.5) = 0.815`** per fruit and **0.613 pool-wide** with
one stiffness (`s_max/s_min` = 2.35) - at `mu 0.6` the window is
**`[4223, 4400] N/m`**, a 1.04x sliver that **excludes the shipped 1e5**; at the
measured mu the four-pad window is **EMPTY** while the three-pad's is
`[3113, 3677]`, containing P111's measured `[2.9e3, 3.8e3]`.  A third condition is
the one the line meets: capture from an offset needs `mu < cap/(2 k s)` = 1.07-2.51
at `k 3300` and **0.05-0.12 at the shipped 1e5**.  **Bench A** (P117's rig, 60
cells + 18 sled): **A0** - authoring `pad_mu = 2t - mu_payload` delivers the pair
to **+0.02-0.03** (measured **0.43 / 0.63 / 0.82 / 1.02 / 1.22 / 1.38** at targets
0.40-1.36, `sumN` 9.80 N), so `mu < 1` is real and controllable; **A1** - the
`flat` control reproduces P117 to the digit (8.47/9.07/0.98/12.42), the
**load-axis** creep (`dz`) is **-0.03..+0.03 mm at every mu** (so the book's creep
clause passes on the axis the load acts along), the **total** creep is
**mu-invariant** (pear 8.47 -> 8.68 -> 8.70 -> 8.55 -> 8.59; P117's A6 confirmed on
a 2.2x ladder, which is why the *total* cannot be the verdict - it fails the
incumbent too), and the **trade is retention**: the break-away falls to
**0.48-0.49x** at pair 0.6 and the **34-37 mm fruits are ejected during the seat on
12/12 cells at pair 0.6 and 0.8** (0 pads, 1.2 m fall) against **12/12 held at pair
1.0+** - a squeeze-out at P117's **5 mm** seat, harsher than the line's 1 %.
**Bench B** (P112's protocol; payload = a **square prism**, the algebra's own 2-D
case; 160 cells): the support proof passes (drift **0.0000 mm**, a frictionless
payload centres 10.00 -> 0.02 mm), and a **sphere cannot test this** (every sphere
cell centred at both mus because its surface leaves the 26 mm plate beyond
`delta ~ 9 mm` - recorded, and why the payload is a prism).  **The full close is
clean 8/8 at every pair 0.6-1.35 and both stiffnesses (80/80 cells**, `off_end`
0.00-0.86 mm) - the algebra's threshold is not what a *position-controlled* close
realises, because the near pad keeps pushing at its cap (4.9 N) while the friction
is `2 mu N_perp` (0.8-2.1 N).  **The freeze is the term that denies the
enclosure**: at the shipped close it is **3/8 clean at the 1.35 control and 5/8 at
pair 0.6/0.8** (+2 cells, 0/5 mm arrivals only) and **2/8 at every mu** at the soft
close; the 20 mm residual is 3.3-33 mm at every mu, and the line's arrival is
**55.8 mm**.  **Kill**: K1 does not fire (pair < 1 achievable), **K2 fires**
(control 4/4 clean from 10-20 mm under a full close), K3 not uniform -> **no
build, no cell**.  **Read rules**: the algebra's centring is a *sub-mm* residual
and the line's problem is a *6-56 mm* one; a V-block on the line is the
**widest-extent law + the first-contact freeze**, not friction; a fixture's
payload must be the algebra's 2-D case (a square prism) or its geometry silently
removes the term; and a creep clause is read on the **load axis** (the total is a
mu-invariant seat shift).  **Named next, priced**: the ring with
`FRUIT_DYNAMIC_CLOSE_FREEZE=0` and the **shipped** material - the fixture says it
envelopes 0-20 mm with all four pads (8/8 clean) - a single-arm `cage4` cell at 2
seeds x 20 attempts, endpoints P110's clean enclosure + placed count; and, if a
low-mu pad is ever wanted elsewhere, its price is A1 (0.48-0.49x break-away, the
small class ejected at a 5 mm seat, the load-axis creep unchanged) - scope it to
the ring.  **Guards**: selfcheck **PASS (0 failures, 1 skipped)** with the new
`P129 pad material` leg (18 checks: the four cage knobs' unset path, the openarm
finger material's two default sites, the pair arithmetic 1.25-1.46, and the
algebra's 0.815 / 0.613 / 4223-4400 thresholds), `106` OK, `107` PASS, and
`scripts/accept.sh` with every knob unset **8/10 + `fingerprint: matches`** with
its `[fruit]` stream **identical** to `logs/p127/accept_restored.log`.  Pins
unchanged: `tasks.py` `50fd799d`, `cage_hand.py` `42c4eb64`, `scene.py` `b3bf8067`,
`assets.py` `24d29679`, `rl_env.py` `3aed67b9`; refs **`30fb99f8` / `30fb99f8` /
`8952c320`**; ckpt `moe_v13s` `61da390a`.  New: `logs/p129/{algebra.py,
algebra.txt, fixture_pinch.py, fixture_pinch.log, fixture_ring.py,
fixture_ring_cage4.log, p129_report.py, p129_report.txt, run_p129_pinch.sh,
run_p129_ring.sh, METHOD.md, PREREG.md, PREREG.md5, RESULTS.md}`,
`scripts/265_p129_material_selftest.py` + the selfcheck leg.  Evidence
`logs/p129/`.

**P130 (2026-11-07, `logs/p130/`; P129's named cell, **the knob is shipped**:
`FRUIT_DYNAMIC_CLOSE_FREEZE=0`, no `src/` or `configs/` change, the cage hand
stays opt-in): the freeze-off ring **converts the rate** - `cage4`, single arm,
20 attempts x seeds 5/6, **19/40 = 47.5 %** against the same seeds' freeze-on
controls' **6/32 = 18.8 %**, **+28.7 points, Fisher p = 0.0135** - and **does not
convert the enclosure**: the clean split (P110's jam/over-closure/clean, joined
to the approach's `end=`) reads **8/40 against 2/32, p = 0.169**, because the
dominant failure becomes **over-closure** (22/40: the measured aperture is below
`dia - 4 mm`, the ring driving its pads inside the fruit - the closure-law defect
P108 measured, not the freeze). **The ring still loses to the shipped hand**
(47.5 % against the two-line's 58/80 = 72.5 % at four seeds), so the lane stays
opt-in and the next named term is the **closure law** (`0.98 x` the widest
extent; the `FRUIT_GRIPPER_SQUEEZE` family was already measured negative at 0.94
on the old aperture) plus the moving arrival (56 mm, which no closure law
fixes). Evidence `logs/p130/`.

**P131 (2026-11-08, `logs/p131/`; default off, **nothing adopted**, no `configs/`
change, no reference re-recorded): the owner's closure-law question is answered -
the over-closure is the **law**, not the drive, and P130's 22/40 is **7/40**
once two metric artefacts are removed; the fix removes it exactly (**0/40**,
p = 0.0117) and **exposes the V-block** (3/40 -> 13/40, p = 0.0103), so the
clean enclosure (13/40 -> 11/40, p = 0.81) and the placed count (20/40 -> 12/40,
p = 0.11, a branch) do not convert.**  The **census** (`census.py`, offline, 72
rows from P130's freeze-off cells + P108's freeze-on controls, the extents
recomputed from `meshes.axis_extent` with `pxr` stubbed): on the 80 shipped-law
freeze-off rows `aper / (0.97 min(radial, axial))` is in **[0.96, 1.02] on
75/80 (p50 0.998)** - the close runs to the **two-jaw** `deep = 0.97 x
min(radial, axial)`, i.e. the fruit's **height** on an upright flat fruit, never
to the ring's `0.98 x widest` - and the measured span is at or above the command
on every row (`sep_end - aper` p10 **+0.0 mm** on `F5`/`F6`; the P131 close-time
`sep - aper` p10 **+0.00 / -0.01 mm**), so **the drive is not the term**.  The
**two metric corrections**, both pre-registered: the strawberry's class `dia` is
its **height** (`R/dia = 0.792`, so `aper < dia - 4` flags every strawberry grasp
at `aper/R` 0.95-0.98) and a ring that **missed** the fruit (`off > 15 mm`) also
reads `aper < dia - 4` with no fruit between its pads; corrected (seated =
`off <= 15 mm`; over = `aper < R - 4 mm` or `F > 29.4 N`), P130's split is
**clean 11/40, over 7/40, miss 15/40, vblock 4/40, jam 1/40**, the 7
over-closures are tomato 2 / peach 2 / apple 3 at `aper/R` p50 **0.874**, and
**6 of the 7 placed** (the misses are the failure class).  **The build** is
`FRUIT_CAGE_APERTURE` = `shipped` (default, the P107 expression bit for bit) |
`max_extent` | `pad_axes` (the max over the ring's own four **base-frame** pad
axes, the P112 analogue; equal to the shipped axes for a top-down hand) on
`CageHand.aperture_extent`, plus the one task route that makes it operative: for
an armed radial hand `deep = pinch_width x FRUIT_GRIPPER_SQUEEZE` and the
two-jaw **2.5 mm interference floor is dropped** (the ring reaches its cap at
`cap/k` = 0.049 mm; 2.5 mm is 8.5 % of a 29 mm berry); unset keeps the shipped
target and floor on every hand; the `[cage]` row gains `law= ext= deep= sep=`
(the measured span at the flush; probe default off, and the acceptance stays
421/421).  **The cells** (`cage4` + freeze off, the scripted single arm, the P130
scenario - `FRUIT_BIARM` left unset so the refused cage scheduler still scopes
the wave/balanced supply - 20 attempts, the P108/P110 instrumentation): **U5/U6
(the fresh same-tree controls) 10/10 placed**, **P5/P6 (`pad_axes`) 3/9**, **M5
(`max_extent`) 3**; over-closure **7/40 -> 0/40** with the witness a 62 mm
tomato at **50.7 -> 59.8 mm** (`aper/R` 0.818 -> 0.965, drive at
61.3 mm) and the 69-70 mm apples **61.0-61.7 -> 68.0-68.2 mm**; but clean
**13/40 -> 11/40** and **V-block 3/40 -> 13/40** because the arrival is `off0`
p50 **3.6/3.5 mm** (control) / **4.3/5.6** (treatment) against P110's
`delta < 0.6 mm` - the old 10-13 % over-closure was **masking** the V-block by
driving every pad deep, and its force was already at the 4.9 N/pad cap.
**`max_extent` is a measured negative**: 9/20 rows have `ext > R + 2 mm`
(pear 4, kiwi 2, **strawberry 3** - its height is its largest axis) and **0/9
place**.  **Guards**: crush **0 legs**; landing payload-present **9/9, 10/10,
10/10, 10/10, 3/4, 9/9, 3/3** - the one failure is `P5` attempt 4 (a 3.0 cm
lychee held at 9.97 N in a V-block, flung **2.0 m** during the place leg, the
cage's closed loaded-slide class, not a release miss), so `gates.sh` **rc = 1**
on that letter only; descent budgets **PASS on all five** (worst `|v|max`
0.130-0.144 vs 0.160-0.162, lurch 0.039-0.065 vs 0.291, not re-tuned); no new
reason key; **no-harm** `accept.sh` **8/10, 9.0 s/attempt, `fingerprint:
matches`, `190: PASS`, 421/421** identical to `logs/p127/accept_restored.log`;
`selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new `P131 cage aperture
law` leg; `106` OK, `107` PASS (21 checks).  **Recorded deviations**: **D1 the
cage cell is not bit-reproducible** - two identical unset runs diverge at
attempt 0 (`at pick pose` 0.84 vs 0.86 s, `fruit_y` 0.4832 vs 0.4812), so the
pre-registered `U5 == F5` replay is not available and the control is the fresh
same-tree `U5`/`U6` (the P39 `F1` precedent; every count is one branch draw);
**D2** the PREREG's D2 bar was the P130 control's 11/40, the fresh control is
13/40, and `pad_axes` is 11/40 (-2, inside the control's 5-7 per-cell spread;
p = 0.81); **D3** a P130 by-product the logs expose: `F5`/`F6` ran the
refused-default two-line **wave/balanced** supply while the P108 `B_s5`/`B_s6`
"controls" are `FRUIT_BIARM=0` **scatter** cells, so P130's 19/40 vs 6/32 crosses
two supplies and the freeze's same-supply effect is not in that record (P131's
controls are same-scenario).  **Verdict: the law was the bug, the fix is real,
and the over-closure was not the binding failure**; the remaining blocker is
**centring** (P110's 0.6 mm / a workstation), not the closure law.
`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`** stand.  Pins: `cage_hand.py` **`0f56b2ff`**,
`tasks.py` **`76dbfc6b`**, `rl_env.py` **`b11113fb`** (`TASKS_MD5` =
`76dbfc6b`), `scripts/266_p131_cage_aperture_selftest.py` **`de1d28f6`**,
`scripts/selfcheck.sh` **`5dd45f91`**; ckpt `moe_v13s` `61da390a`.  Evidence
`logs/p131/`.

**P132 (2026-11-08, `logs/p132/`; a fixture in `logs/` - **no `src/` or
`configs/` change, nothing adopted, no commit, every reference untouched**): the
owner's last geometric route - a **new pad asset** for the loaded-slide class - is
tested fixture-first and **no shape promotes**, so the **static pad-asset lane
closes**.  The hypothesis the record had not tried is the one geometric form that
acts on the direction the payload leaves in: **ridges perpendicular to the walk**
(across the pad's width, spaced along the tool axis), a ratchet.  Four faces, the
shipped 4.90 N/face, the pool's own mesh/mass/friction draw, 4 fruits x 3 repeats
(48 cells, 112 s, one session): `flat`, **`serr`** (5 ridges, 1.0 mm, 8 mm pitch,
60 deg flanks), **`serr45`** (the same at 45 deg flanks; the brief's "at 45 deg"
is read as the flank angle, not a rotated ridge line), **`lip20`** (the flat face
with a 20 mm lip - fixture-only; it extends 9.5 mm below the shipped distal plane,
where the belt is).  **A1 support proof**: zero pad force + weight compensated,
200 ticks -> **0.000 mm**; no compensation -> falls **613 mm**; 48/48 real cells
load **2 pads** at 4.38-4.93 N (the serrated off-side pad is 4.38 N, a recorded A2 deviation).  **The result**: the **load-axis walk** (the
displacement during the 0.75 s `m(g+5.83)` hold) is **at the rig's floor for the
incumbent and both serrations** - pear +0.03, orange/strawberry/lychee +-0.00 mm,
|walk| <= 0.03 everywhere - so the promotion rule's first clause
(`<= 0.6 x flat`) has **no resolvable signal**; the **2 mm break-away** (the
class's own trigger) is a draw to **worse on the small classes** (`serr` 0.77x
strawberry / **0.35x** lychee; `serr45` 0.75x strawberry) with one large species
positive (orange 3.44x) whose `Fexit` is 0.98x; the **one measurable walk** is
`lip20`'s pear **-2.82 mm** (down) with a **0.50x** 2 mm break-away - the deep cup
is a negative.  **A fixture defect was found and fixed, and it changes the flat
control**: P117's `author_pad` built the facet frame `(tan, nf, w_axis)`, which is
**left-handed for one pad of every pair**; the quaternion extraction rotated that
box 90 deg, so **one pad carried 62.2 mm on the thickness axis** (measured
`flat S00L (10.0/62.2/84.9)` vs `flat S00R (62.2/10.0/84.9)`), its face sat 30 mm
behind its body and the small fruits fell on **every long-axle profile including
the flat `lip20`** - the facet, not the serration.  The one-line fix
(`w = cross(tan, nf)`) makes every facet 10 mm; the **corrected flat control**
reads pear `creep_op` **6.70**, strawberry **12.22**, lychee **12.05** mm
(P117/P129's 8.62 / 0.98 / 12.42 were that rig's, and the strawberry's 0.98 was
the 62 mm block's cradle), so this phase's A/B is on the corrected rig for all
profiles.  The teeth are anchored at the **fruit's widest row**, not the pad's
face centre (the face centre sits 31.95 mm above the equator; P117's
`asin(|u*|/r)` is corrected to `|u* - u0|/r`), and the geometry check shows the
**downward** side has only the shipped 10.5 mm lip (the pear's widest is 2.5 mm
above the distal plane), less than one 8 mm pitch - a 5-ridge **downward** ratchet
is not buildable inside the lip, which is P39/P69's belt constraint from the other
side.  **No shape promotes -> no build, no two-line cell** (the rule: the fixture
first; a pad asset moves the collider set and would need same-seed controls).  The
**dynamic residual** is named, not hidden: the class is a dynamic pry (P75) and
this rig is a static pull, so the verdict closes the **static** pad-asset lane;
the **workstation** is the decision book's only remaining geometric route and the
owner's constraint (no stop/diverter/guide) excludes it.  **No-harm**: nothing
built - `FRUIT_FINGER_FACE` still defaults to `flat`, no `serr` token in `src/`,
the new `267` leg pins the unset path and the geometry; `scripts/accept.sh`
**8/10 = 80 %, 9.0 s/attempt, `fingerprint: matches`, `190: PASS`** with its **421
`[fruit]` lines 421/421 byte-identical** to `logs/p127/accept_restored.log`;
`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**; `106` **OK**, `107`
**PASS (21 checks)**.  Pins: `tasks.py` `76dbfc6b`, `rl_env.py` `b11113fb`,
`scene.py` `b3bf8067`, `assets.py` `24d29679`, `fruits.py` `c8f19228`,
`cage_hand.py` `0f56b2ff`, `scripts/267_p132_serr_selftest.py` `9d3a8ddf`,
`scripts/selfcheck.sh` `29958b29`; references **`30fb99f8` / `30fb99f8` /
`8952c320`** untouched; ckpt `moe_v13s` `61da390a`; `logs/p132/PREREG.md`
**`e31db91f`**.  Evidence `logs/p132/`.

**P133 (2026-11-08, `docs/END_EFFECTOR_DECISION.md` §7; design/handover only, no
`src/` or `configs/` change): the end-effector decision book is updated with the
bench that answered its two open nails.** `§4`/`§5` gain a STATUS note pointing
at the new **§7**, which records: **nail (i) `mu < 1` is closed** - the four-pad
residual is `mu s` (not the book's `(2mu-1) min(...)`), the pair is controllable
(`pad_mu = 2t - mu_payload`, +0.02) but its price is the **small-fruit ejection**
(12/12 cells at pair 0.6-0.8, break-away 0.48-0.49x), and the ring **centres and
loads all four pads at the incumbent 1.35** (80/80 full-close cells); **the ring's
real terms are the close freeze** (P130: +28.7 points, p = 0.0135, still 47.5 %)
**and the centring** (P131: the aperture law ran to the two-jaw target; the fix
removes the over-closure 7/40 -> 0/40 but exposes a 3.5-5.6 mm arrival against
the ring's 0.6 mm); **a new pad asset is closed** (P132: the ratchet's walk is at
the rig's floor, worse on the small classes, and the 10.5 mm lip cannot hold a
0.45 mm pitch) with the **fixture defect correction** (P117's strawberry 0.98 mm
was a left-handed facet frame, not the pinch). The revised recommendation: **no
geometric purchase**; the one open measurement is the **real-jaw force anchor**
(fidelity, not rate); the workstation is the only path to the ring's centring and
is excluded by the owner's constraint. `106` OK. Evidence
`docs/END_EFFECTOR_DECISION.md` §7.

**P135 (2026-11-09, `logs/p135/`, `docs/TRACKING.md`; default off, **nothing
adopted**, no `configs/` change, no reference re-recorded): the catch is a
**tracker** now, and the phase's measured result is that under a **varying
conveyor** the shipped scheduler misses the handover by **298-407 mm** while a
prediction-gated one catches in **16-17 ticks at 5.4-5.9 mm**. The shipped catch
is a formula in four places - the aim is `[fruit_x, station_y+lead, fruit_z]`
computed once at the pre-pose, the descent's start is
`fruit_y - grip_y <= speed*(t_desc+0.15)` with `speed` the **belt scalar**, the
descent is an open-loop min-jerk leg to the fixed aim, and the catch-up commands
`fruit_now + velocity*0.25` - and every one of them is exact only while the fruit
rides a constant-speed belt. **The build** (`src/fruit_sorting/tracking.py`, new):
`FruitTracker` is a Kalman filter over the centre, constant velocity with an
**adaptive process noise** (a velocity step is followed by the third tick); the
correction is defined **against the conveyor**,
`correction(t_go) = predict(t_go) - (p_at_descent_start + belt_v*(elapsed+t_go))`,
so it is **identically zero under the model** (1.8e-15 m over 120 frames, `268`)
and the shipped geometry, motion budget and two-line clearance are untouched
whenever the belt is the belt. `_approach` gains `track=t_remaining -> jaw point`,
re-evaluated **every tick** (same min-jerk schedule, moved endpoint); the catch-up
closes on `predict_at(lead)`; and **`FRUIT_TRACK_WAIT=1` replaces the speed gate
with a prediction gate** - start the descent when the estimate says the fruit will
be at the catch position when the leg ends (the shipped margin re-derived:
`predicted-grip <= 0.02` vs `fruit-grip <= v*(t_desc+0.15)` = `0.018`, which is why
the nominal cell does not move). Knobs: `FRUIT_TRACK=est`, `FRUIT_DESCENT_TRACK`,
`FRUIT_TRACK_WAIT` (+`_TOL`), `FRUIT_TRACK_CORR_MAX` 0.08 m,
`FRUIT_TRACK_CATCH_SPEED` (residual-proportional closing lead, measured **null**),
`FRUIT_TRACK_ACCEL` (CA form, **not** the default: one tick after an 80 mm/s step
its correction is **-147 mm** and the sign flips 40 ms later, while CV reads 16 mm
then < 3 mm), `FRUIT_TRACK_SOURCE=truth|depth`, `FRUIT_TRACK_APPLY` (the
measure-only bench), `FRUIT_TRACK_DIAG` (the `[track]`/`[catch]`/`[perceive]` rows).
**The belt-wave instrument** (`FRUIT_BELT_WAVE_AMP/_HZ`, a sine on the surface
speed; **the fruit ride it with no slip**): C **298/339 mm timeouts** at 0.04/0.5 Hz
and **407 mm** at 0.08/0.3 Hz; T (re-aim only) keeps them (the clamp is 80 mm and
the miss is created *before* the descent); A (CA) no better; **W (prediction gate)
converts every one: 5.6/5.4/5.9 and 5.9/5.6/5.5 mm in 17/16/16 and 16/15/17
ticks**, timeouts 2->0 and 1->0, `corr_max` 25-46 mm. **The nominal cell is a
measured tie**: `nom_w` 11/13/11 ticks at 5.5-5.9 mm against the control's
10/13/11, 0/3 placed against 0/3. **The impulse instrument**
(`FRUIT_PERTURB_DX/DY/DZ/_AT`, one velocity write on the **selected** fruit,
`FruitSpawner.impulse`) is a **negative for tracking and a confirmation of the
class split**: the belt's friction damps an impulse in ~30 ms, so the catch-up
absorbs every rung (lateral 0.10-0.35 m/s, downstream 0.10-0.30 m/s) in **<= 24
ticks**, 35 of 36 attempts grasped, and what the impulse costs is the **grasp quality** (at
dx 0.35 all three grasp and none place; the closed loaded-slide class,
`logs/p42/SIM_LIMIT.md`) - no tracker touches that. **Perception**
(`src/fruit_sorting/perception.py`, new): `FRUIT_TRACK_SOURCE=depth` renders
RGB + `distance_to_image_plane` + the target's instance mask, back-projects through
the **calibration** (the authored focal length/aperture - a ratio, so the stage's
units cancel - and the `/World/HeadCamera` prim's world pose; the frame's own shape
sets the intrinsics, so a `FRUIT_CAMERA_RES` override cannot desynchronise them)
and fits a **trimmed sphere**: bench (`FRUIT_TRACK_APPLY=0`, 44 frames, the shipped
pool) **position 4.70 mm median / 6.41 p90, diameter 3.42 / 4.29** - the registered
bars 5/10/5 pass; the fit is exact on a synthetic sphere (7.8e-12 mm), so the
residual is the *fruit* being an ellipsoid (the fitted sphere is 1.6-4.1 mm small,
and the error is a systematic **+y bias** of 3.5-6.3 mm - a reference-sphere
calibration, not a modelling error). **In the loop** (2 attempts, every knob on,
`FRUIT_PERCEPTION_CLOSE=1`): **2/2 grasped**, 1 placed, catch 13 and 38 ticks at
5.9 mm, the filter's error 5.3/3.6 mm and its velocity 0.116/0.118 m/s against the
belt's 0.120, 61 accepted frames and 17 refused for **occlusion** - the estimator
carries the descent through them. Two integration rules the path needed and that
are easy to re-introduce: **the descent's start must force a camera frame**
(30 Hz camera vs 120 Hz control: a single-tick anchor lands inside the period 3
times in 4, the filter is never created, and every aim falls back to the station's
nominal x - up to 140 mm off; `measure(force=True)`), and **a refused frame must
return `None`, not the cached estimate** (a cached position fed back is a lie the
filter cannot see, and inside the period it is counted 4x). **The camera's own
limit, measured**: the hand occludes the fruit exactly when it matters - the mask
shrinks 48 -> 22 px and the fit's z drifts 11 -> 44 mm - so `_perceive` refuses a
cap below `FRUIT_PERCEPTION_MIN_PX` (60) and the filter predicts through it;
**and once a full cap (`FRUIT_PERCEPTION_FULL_PX` 120) has set the radius, a
smaller cap fits only the centre with the radius held**
(`_fit_sphere_known_radius`) - the radius is a property of the fruit, not of the
frame, and freeing it on a 20-40 px sliver is what let z drift. The re-run reads
**2/2 grasped, 1 placed**, catch 13/37 ticks at 5.7-6.0 mm, 64 accepted and 17
refused frames. **The residual is a mounting offset, and it is calibrated**:
the fitted centre sits **+6.5 mm in `+y`** of the rigid body's origin on this
camera, stable across the pool and **not** a shape effect (`FRUIT_PERCEPTION_SHAPE=
spheroid` - two radii, the long one along the belt - reads 6.85 vs 6.79 mm and a
*worse* diameter, 3.52 vs 2.37 mm, so the sphere stays the default);
`configs/perception_calibration.json` carries the offset and the module subtracts
it, taking the bench **6.79 -> 1.98 mm median** (p90 10.01 -> 5.63) at an
unchanged 2.37 mm diameter, with the **wrong-sign control reading 13.16 mm** -
which is what proves it is a constant and not a fitted curve. In the loop with the
calibration (`perception/inloop9.log`): the filter's error at its last update is
**3.4 and 1.3 mm**, the catch **14 and 22 ticks at 6.0/5.8 mm**, 2/2 grasped.
A different mount or lens needs its own number (`FRUIT_PERCEPTION_BIAS=x,y,z`). A
wrist camera or a second view is the next spend for the occlusion window itself. **The aim is decided late** on
the depth path (`_track_late_grip`: the estimate's x/z at the descent start, the
schedule's y), because the fruit is far upstream and often out of frame at the
pre-pose - the fallback there is the **station's nominal pose**, never the rigid
body, and a run that cannot measure says so. **An eye-in-hand camera is added
and measured** (`FRUIT_WRIST_CAMERA=1`, default off; two RGB-D cameras at
`FRUIT_WRIST_RES` 240x424 with the head's annotators, authored at build time and
**driven from the jaw centre and approach axis on every rendered frame**,
`scene.set_wrist_pose`): the head's weakness is geometric (0.8 m away with the arm
between it and the fruit). **The aim decides everything** - aimed *at* the grasp
point (3 cm past the jaw) the fruit is 10 cm upstream when the leg starts and
leaves the frame (**94-402 px, 729 refusals**, 7.7 mm position, 5.8 mm diameter);
aimed **12 cm past the jaw** the mask *grows* as the hand closes (**1684-3241 px,
2-3 refusals**) and it is the **best sensor in the project**: position **3.54 mm**
median / 4.80 p90, diameter **0.90 mm** / 2.63 - 2x the head's position accuracy
and **2.6x its diameter**, with the occlusion gone. Its mount offset is its own
(+0.75, +2.60, -0.25 mm) beside the head's in `configs/perception_calibration.json`
(and it **must be re-measured when the aim changes** - the 3 cm mount read
-1.5/+3.3/-6.2 mm). **It is not yet a closed-loop sensor**: in the loop one
attempt of two diverges in **both** runs (the hand drives through the fruit,
`125.9 N`, the filter then tracks a 6.4 m/s object, the catch ends 0.4-11 m away),
while attempt 0 is clean (17-18 ticks, 6.0 mm). Two candidate causes are measured
out - the per-fruit radius carry-over is real and **fixed**
(`FruitPerception.reset()` at every attempt), and the instance mask cannot select
the wrong fruit (zero-padded `Fruit_%02d` names) - so the remaining hypothesis is
the **bracket**: the approach needs the camera down the corridor, the contact
needs it at the jaw, and one fixed aim loses one of them. **Eight variants are recorded** (`logs/p135/RESULTS.md` §9): three aims (3 cm,
6 cm, 12 cm past the jaw), the 114-degree lens, an aim that tracks the estimate
(**worse** - the view and the estimate form a feedback loop: 165 refusals, a 1.35
m/s phantom, `corr_n=0`), a **belt-velocity prior** (`FRUIT_TRACK_BELT_TAU`,
0.3 s mean-reverting velocity: the wrist refuses ~45 % of frames, so a free
velocity drifted 0.24 -> **0.137** m/s), a **measurement gate** (`FRUIT_TRACK_GATE`
40 mm with a 3-strike re-open: tracker error 78 -> **27 mm**) and a **relative
anchor** (correct against `p_now`, not the descent's first frame). **The last
three are real estimator improvements and are kept**, and the phase's working
results **re-check on them** (`logs/p135/recheck/`): the belt-wave `W` cell reads
**12/13/11 ticks at 5.4/5.8/6.0 mm and 2/3 placed** (was 17/16/16 and 0/3) and the
head loop **16/5 ticks** (was 14/22), both with the zero timeouts standing. **A second pass found that the mount model itself was wrong**: `look*axis` is the
**tool** axis, so "12 cm past the jaw" is 12 cm **below the hand**, not up the
conveyor - and the fruit arrives from the belt, 10-30 cm upstream and 7 cm lower.
That is why the 12 cm mount measures beautifully when it sees anything and only
sees the fruit when it is close: **the wrist is a contact-phase sensor, not an
approach one**. Two consequences, both kept: a mask that touches the image border
is **refused** (`FRUIT_PERCEPTION_CLIP_PX` 2) because a *truncated* cap reads a
0.21 mm rms, a correct diameter and a **24-32 mm** centre error (3309 px at
0.11 m); and tilting upstream (`FRUIT_WRIST_UPSTREAM`) is a **measured negative**
(0.16 m reads **1-6 frames per attempt** - the aim then sits above the belt). A
fixed mount cannot be both far upstream and low without a real tilt, which is what
a bracket buys. The head keeps the approach (it sees the whole belt) and the wrist
the contact. **The two-camera handover is built and hardened** - a **workcell ROI**
(`workcell_roi`, `FRUIT_PERCEPTION_ROI`: a fit outside the belt's own volume is
refused, because a wrong lock **0.8 m** from the fruit had *passed* the innovation
gate and put the aim a metre away, `corr_n=1312`), a **bounded wait for a first
measurement** (`FRUIT_TRACK_MEAS_WAIT` 240 ticks) instead of a blind descent, the
**band-centre fallback** (the station is the band's edge: 140 mm from a fruit at
0.20, 80 mm from the centre) and the border-clip gate - and it is **not
validated**: with two render products alive the second attempt accepts **zero**
frames (9-10 on the first, ~70 renders each, with and without a double `render()`)
while the same attempt on the **head-only** tree accepts **51** and the
**wrist-only** cells accept **13 and 28-75**. The sensor and its calibration are
sound; this build's per-sensor `instance_id_segmentation` is not (the annotator the
record already notes as fragile). Its cells do read attempt 0 at **12-16 ticks,
5.5 mm** (the best catch in the project) with accepted frames at **4.8-5.0 mm**.
**The per-attempt choice is implemented and does not help** (`FRUIT_WRIST_MODE`
= `pick` / `only` / `switch`; `pick` gives the wrist the first look at the
descent's start and whichever camera sees the fruit is that attempt's *only*
sensor): the cell reads attempt 0 at **11 ticks / 5.6 mm** from its one accepted
frame, then **1 and 0** accepted frames (`frames=4` of **210** renders). The
decisive control: author the wrist cameras and **never read them** - the head
camera then reads **27 frames (19 on attempt 0, 0 on attempt 1)** against **75
(27/51)** on the head-only tree. **Mere authorship of a second annotated camera
takes the first one's instance mask away**, attempt-dependently. **This build
supports one annotated camera per run**, not two; the remaining step is a scene
pipeline one (a second render product with an independent annotator graph), not a
tracking one. **Option A closes here: not adopted.** The head camera plus the estimator stays the
working loop, and with the knob unset **no camera is authored at all**. **No-harm**: `scripts/accept.sh`
with every knob unset is **8/10 = 80 %, 9.0 s/attempt, `fingerprint: matches`,
`190: PASS`**, and its **421 `[fruit]` lines are 421/421 byte-identical** to
`logs/p127/accept_restored.log` (`logs/p135/accept_final.log`, re-measured on the
wrist-camera tree at `logs/p135/accept_wrist.log` and again after the estimator's
prior/gate/anchor at `logs/p135/accept_final2.log`);
`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new `P135 tracker`
leg (33 checks: the exactness, the step, the CA negative, the zero correction, the
clamp, the calibration ratio, the synthetic sphere, every off default); `106` OK,
`107` PASS (21 checks). **Re-baseline: none** - nothing shipped,
`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`** stand. Pins: `tracking.py`
**`970e2139`** (new: the estimator, the belt prior, the measurement gate), `perception.py` **`7557d461`** (new), `tasks.py`
**`5b3a8ee6`**, `fruits.py` **`ad490ff0`** (`FruitSpawner.impulse`), `rl_env.py`
**`1c934199`** (the `TASKS_MD5` follow), `scripts/268_p135_track_selftest.py`
**`aa26a529`** (35 checks), `scripts/selfcheck.sh` **`d57ef4ab`**, `configs/perception_calibration.json`
**`963b5522`** (new; the depth path only - the scripted line never reads it),
`scene.py` **`5ba275ff`** (the wrist-camera author + `set_wrist_pose`), ckpt `moe_v13s`
`61da390a`; `logs/p135/PREREG.md` **`0250fdc7`**. Evidence `logs/p135/`,
`docs/TRACKING.md`.

**P143 (2026-11-12, `logs/p143/`; **the owner's adoption: the moving catch is the
direct/policy default**): `PickAndPlaceTask._dynamic_pick_mode` returns **True on
every hand and every path** with `FRUIT_DYNAMIC_PICK` unset (`=0` restores the P1
indexed line, `=1` forces the catch), so the policy handover now takes the fruit on
the fly exactly as the scripted line already did. The reason is P142's corrected
metric, in this order: the trigger already fires on a **predicted intercept** while
the indexed primitive aimed at a frozen `position(sample)` (0.06-0.36 m of drift at
0.12 m/s); the **correct-output rate doubles** (5 seeds x 15 per arm: **53/75 =
70.7 %** dynamic against **25/75 = 33.3 %** indexed once the mis-sorted placements
are subtracted); and the **cross-lane ledger goes to zero** (35 deliveries to the
wrong lane in 75 indexed episodes against **0**, Fisher p = 1.6e-13). The counts
alone are a direction, not a rate (**+13.3 points, 95 % CI [-15.2, +15.2]**, paired
sign p = 0.154) - the quality term carries it. **No-harm**: `scripts/accept.sh` is
**7/10 = 70 %, `fingerprint: matches`**, its **459 `[fruit]` lines 459/459
byte-identical** to `logs/p136/accept_final.log` (the scripted line already resolved
True, so the flip is inert there by construction); the **hybrid canary** reads
**8/10 = 80 % PASS** (2 grip losses, no reason outside the baseline set - the top of
its recorded 5-8/10 spread, and the interface of record is `handoff`, which the flip
does reach); `selfcheck.sh` **PASS (0 failures, 1 skipped)** with the P142 leg grown
to **35 checks** (the resolver table over `openarm x scripted`, `=0` restoring, `=1`
forcing, the adoption in the docstring, and the recorder's new view).
**The interface question the videos exposed**: with `FRUIT_POLICY_TRIGGER=off` (the
shipped default) the handover fires only when **the policy itself commands a close
within 6 cm** (`finger < 0.030`), and **`moe_v13s` never does** - **0/7 episodes
across two clips, with no `policy closed on the fruit` row at all**; `moe_v12`
closes in 2 of 6 (one placed). With `=arrival` an **external** intercept rule fires
the primitive (the policy then only gets the arm there) and the same checkpoint
reads **3/4**, while the handoff canary - which teleports the fruit to the jaw and
always runs the primitive - reads **8/10**. So the three numbers measure three
different things: the model's own close (0/7), the model as an approach controller
under an external trigger (3/4), and the station handoff (8/10). **What P143 settles
is the primitive, not the trigger**: whenever the handover fires it is the moving
catch, and whether the trigger should default on for direct is a **separate** flip
with its own re-baseline, **not** made here.
**Why the model cannot grasp unaided, in two numbers** (`FRUIT_HANDOVER_DIAG=1`,
one row per episode, tracked where the policy's own close is evaluated so it costs
no extra read): `gap_min` **128-155 mm** on **both** arms against a **60 mm** gate,
with `finger_min` **0.005-0.016** - i.e. the model **does** close, it closes ~13 cm
short (13 cm is ~1.1 s of belt travel at 0.12 m/s). `FRUIT_GOAL_LEAD=1.0` (the goal
moved forward by the fruit's own velocity, zero-shot) does **not** fix it (155 -> 158,
75 -> 83 mm): the goal is conditioning, the arm's position is the policy's learned
mapping, and the demonstrations all start with the arm **already at the grasp pose**,
so "one second behind a moving fruit" is not in the cloned distribution. That is the
whole gap between "the model" and "the model does approach -> grasp -> place"; the
lane that could close it is DAgger on the hybrid's own episodes (four nulls on this
interface so far: W7-C, W8-A, R9, P37), and the number above is what a training cell
can now be scored on. **The DAgger round (P143 section 9) is the first non-null on
that lane**: 24 episodes collected with the env's own `--dagger` expert (its command
is the label, the policy's action is kept as `policy_action`), fine-tuned 6 epochs,
and `gap_min`'s **median halves (140 -> 63 mm; same-seed 140 -> 70.5)** with **6/12
episodes reaching the 60 mm gate** - but **success is still 0/12**, because the gate
is a **conjunction on one tick** (`finger < 0.030` **and** `distance < 0.06`) and the
episodes split: arrive-and-hold-open (1-23 mm, `finger_min` 0.030-0.041) or
close-too-far (0.0-0.02 at 86-139 mm). One episode satisfied both and **grasped**
(`grasped=True placed=False`, the loaded slide). **Close-weighting 4x is worse** (86
mm) and is not adopted; neither candidate replaces `moe_v13s` (direct) or `moe_v12`
(canary, 8/10). Named next was a close-phase label, but **the label already is the conjunction**
(the expert's window is `dy in [-0.02, +0.05]`; the collected store's first
`finger < 0.030` frame sits at `fruit_y` 0.011-0.042 m), so step 2 became the
**fitting balance** instead: the fine-tune mixes `demos_v11` (50 scripted episodes
that all start at the grasp pose) at `--base-weight 1.0`, which fights "chase the
fruit". At **`--base-weight 0.3`, 8 epochs**: `gap_min` median 73.5 mm and
**1/12 `success=True grasped=True placed=True`** - the **first pure-policy
approach -> grasp -> place on this interface** (orange, right arm, `gap_min` 50 mm,
reward 0.9621). One of twelve is a draw, not a rate, and the median is *worse* than
the base-1.0 model (73.5 against 63 mm) while the count is better - the two metrics
rank them differently at n = 12. **Step 1 (a bigger store) made it worse**: 36 episodes (8/36 success, 1.2 GB) at
the same recipe read `gap_min` median **~107 mm** and **0/12** - and the takeover
counters say why: `expert_ticks 14804/15591 (95.0 %)` on the 24-episode store and
`18479/20156 (91.7 %)` on the 36 - with `--expert-tolerance 0.35` the **expert
drives the episode**, so the states are expert states, which is behaviour cloning,
not DAgger. **The fix is one flag**: `--expert-tolerance 99 --expert-window 0`
makes the expert never take over while the label is still recorded every decision,
so the store becomes the policy's own distribution (the 13 cm state included). The
number that condemns the 36-episode store is the **expert-tick share**, not the
episode count. **R3 then found the actual blocker and it was the interface**: the
learned close's gate was **0.06 m**, the model closes at **128-155 mm**, and the
primitive catches from **0.26 m** with a 200 mm catch-up budget (P48) - so every
close the model made was discarded. With **`FRUIT_POLICY_CLOSE_DIST=0.15`** (now the
**default**, `=0.06` restores) the **untouched `moe_v13s`** reads **2/4 success**
plus one `grasped=True` lost at the place, against **0/7** at the old gate - no
training, no trigger, no teleport; the witness is the model's own note,
`policy closed on the fruit (... |jaw-fruit|xy=15.0cm)`. The knob is
**direct-presentation only** (`policy_close` lives inside that branch), so the
scripted line and the `handoff` canary cannot read it. It does **not** fix the
right-arm case that never gets inside 243 mm - acquisition remains the open term.
`p143_dagger_bw` (24 ep, 1/12) stays the training candidate; `p143_dagger2` (36 ep)
is not adopted. **On the fixed interface the training loses to the baseline**:
`p143_dagger_bw` reads **0/4** against `moe_v13s`'s **2/4** in the same 4-episode cell,
because its near approaches (36/41 mm) happen while the **finger is still open** and
it closes later, farther out - so the DAgger lane is **not** the next spend. The
instrument was blind to that ( `gap_min` and `finger_min` are independent minima):
**`gap_close`** (the minimum distance over ticks with `finger < 0.030`) is now on the
row and is the number the gate actually reads. **The gate ladder is measured**: 0.06
-> 0/7; **0.15 -> 2/8** (and 2/4 in the earlier cell; pooled **4/12 = 33 %**), where
**every** episode closes at 148-155 mm - the gate sat *on* the model's close, so
1-2 mm decided it; **0.20 -> all eight fire** (197-200 mm) and **2/8 again**, with 5
grasping and losing the payload at the place. So the gate's whole contribution is the
**0 -> 2** jump and the default stays **0.15**; past it the binding term is the
closed loaded slide, not acquisition or training. The model lane's standing result, **pooled over every 0.15 m cell (24 episodes,
seeds 77/101/202)**: **9/24 = 37.5 % success**, 4/24 grasped-and-lost (the loaded
slide), **11/24 no grasp** - and the primitive runs on every episode (all twelve in
the formal table close), so those are the *primitive's* catch outcomes at a ~15 cm
handover. **`gap_close` is complete and uniform (min 112, p25 148, median 150, p75
155, max 180 mm) and no longer discriminates**: the five successes sit at 147-150 and
the failures at 112-180, with both at the same 148-150. What separates is the
**fruit**: pear/peach/orange 3/3, tomato 2/4, apple 0/1, **lychee 0/3, strawberry
0/1** - the small-fruit grip class of `logs/p42/SIM_LIMIT.md`, which the record has
closed from force, pad face, friction, seat, attitude, lift height and speed. **So no
interface or training term remains in the model lane**; the ceiling is that class.
**Re-baseline: every direct/policy rate, cycle and store recorded before P143 is an
indexed-primitive number; `FRUIT_DYNAMIC_PICK=0` restores it** (compose with the
earlier restores: `FRUIT_TRACK=0` for pre-P136, `FRUIT_SPEED_RELEASE=0` for pre-P87,
`FRUIT_ARM_PARK=ready` for pre-P43, `FRUIT_POLICY_TRIGGER_ACQ=0` for pre-P54, the P58
burst profile for pre-P58, `FRUIT_OUTPUT_LANES=2` for pre-P126). **Validation videos
(the owner's standing rule)**: `scripts/121_policy_video.py` gains a fourth camera,
**`overhead.mp4`** (960x540, eye z **2.35** with the shipped aim, **0 fully-black
rows**, both output lanes) - the policy's own `head.mp4` stays 424x240 and keeps its
aim because it *is* the model's input, so the raised view is a separate camera, not a
moved one. Clips for both adopted checkpoints are on
`/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/` (116 MB,
with a README naming each clip's checkpoint/md5/interface/outcome). Pins: `tasks.py`
**`4acf2d27`**, `rl_env.py` (`TASKS_MD5` follow), `scripts/121_policy_video.py`,
`scripts/270_p142_endpoint_selftest.py`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched; ckpt `moe_v13s` `61da390a`, `moe_v12` `3a9ccfc0`; evidence
`logs/p143/`.

**P144 (2026-11-13, `logs/p144/`; default off, nothing adopted, no reference
re-recorded): the head camera was searched over the **whole cycle** and the new
pose is a measured option, but it is a **null on the task**.** The search
(`logs/p143/camera_search.py`, 155 samples, the scripted line) projects the target
fruit into ten candidate cameras every 8th tick and reads the depth at its pixel
(`visible` = the fruit is the nearest surface). The shipped top-down camera sees
the fruit **14.6 %** of the cycle and **0 %** of the place - the arm is between the
lens and the fruit (a standalone probe: the fruit at 777 mm, the depth at its pixel
31 mm). A downstream camera at **(1.60, 0, 2.00) -> (0.34, 0, 1.15)** sees
**81.4 %** (approach 83.0, place 79.5) and is the only candidate good in both
halves; `down_high` 78.8, `down_x_140` 68.1. `assets.head_camera_override` +
`FRUIT_HEAD_CAMERA` make it selectable (unset is byte-identical: acceptance 7/10,
`fingerprint: matches`, **459/459**; an unknown name raises) and the store
manifest gains `scene.head_camera = {name, eye, target}` (a manifest without the
key predates P144). **The retrain was confounded and the control says so**: 45
single-arm episodes on the new camera, fine-tuned with `--base ""` ->
**0/12**, and the same recipe on the **old** camera is also **0/12 with zero
grasps**, so the 0/12 is the recipe (fine-tuning `moe_v13s` on 45 episodes without
the anchor overwrites it), not the view. **The zero-shot cell closes the
question**: the shipped checkpoint through the camera it never saw reads **4/12 =
33.3 %** against its **9/24 = 37.5 %** through the trained view, closing at the
same 149-150 mm - the policy's `goal` is the truth, so the image is an appearance
channel and its occlusion is not the limiter. **The camera is worth adopting for
watching and for the validation clips, not for the rate**; for the view to matter
the policy must be conditioned on the image alone (P145's measured goal).
**The transferable recipe rule**: a `moe_v13s` fine-tune needs `demos_v11` as the
anchor - `--base ""` on 45 episodes destroys the grasp on either camera. Pins:
`assets.py`, `scene.py`; references **`61fb5202` / `61fb5202` / `18b101bf`**
untouched. Evidence `logs/p144/`.

**P145 (2026-11-13, `logs/p145/`; the honest interface ships **default off**,
nothing adopted, no reference re-recorded): no handover, no trigger, no truth
goal and no encoder - the camera is now the only source of the goal, and the
policy's own 7 joints + finger must do the cycle.** Two switches, both
default-inert: **`FRUIT_POLICY_HANDOVER=0`** (the primitive never runs;
`grasped`/`placed` are read from the payload - lifted = rose 50 mm above its belt
rest, placed = on an output line at finalize) and
**`FRUIT_GOAL_SOURCE=perception`** (the goal is measured on the frame `_observe`
already rendered: depth + `instance_id_segmentation` -> trimmed sphere fit ->
`tracking.FruitTracker`, rewritten **every observation tick** with the measured
position, velocity and diameter; unset is the shipped truth goal, byte for byte).
**The measured goal is accurate**: position `err` p50 **1.9-9.5 mm**, p90 3.1-10.6
(the shipped head camera, 240x424), velocity **0.124-0.135 m/s** against the
belt's 0.120 with **no belt prior**, diameter 4-13 % small (the known sphere-fit
bias). **The no-handover baseline is 0/7 with zero lifts**: `gap_close` 69-149 mm
on every episode - the model closes **7-15 cm short**, and with the measured goal
it still closes at 172 mm, so **the sensor is not the bottleneck; the policy was a
timed replay of the static goal**. **The training interface** is the existing
DAgger expert as a **teacher only**: `FRUIT_DAGGER_NO_TAKEOVER=1` keeps the arm
100 % the policy's (the shipped early-close term otherwise hands over for one tick
at exactly the close; measured `interventions=0`, `expert_ticks=0`), and
`dagger_valid` marks the post-ramp frames the expert holds an already-grasped
fruit in (the loader drops them). `FRUIT_TRAIN_GOAL=moving` rebuilds every
demonstration's snapshot goal from its own per-frame `fruit_position` trace, so
the anchor and the measured store share one goal semantics (a store recorded with
`goal_source=perception` is left alone). Store `datasets/p145_dagger`: **30
episodes, 9,791 frames, 0/30 lifts, 600 focused windows (263 close)**
(`FRUIT_DAGGER_FOCUS=20`, `logs/p145/merge_shards.py`).
**What converts and what does not** (six fine-tuning arms, every one from
`moe_v13s` `61da390a`): the **tracking and the close timing convert** - the closest
xy gap falls **69-149 mm -> 1-43 mm** and `gap_close` becomes equal to `gap_min`
on 4 of 5 episodes - but **the grasp does not**: the jaw holds x = 0.28 (the
station line) while the fruit is at x = 0.20-0.36 and z = 1.29 while the fruit's
centre is 1.20, so the pads close **2-12 cm** from the fruit. **The mechanism is
action precision, and the offline instrument names it** (`logs/p145/close_fidelity.py`,
60 close windows, DDIM-16): the best fit is **0.068 rad** joint error on the close
windows (200 epochs on the DAgger store alone; the base's close fits to 0.084),
which is **~3-5 cm at the TCP** while the catch needs ~2 cm; under-trained arms
read 0.19-0.32 rad and the base-1.0 arms 0.276. A second, execution term: with
`execute_steps=4` the chunk's early ramp values re-sample before the finger
advances (`finger_min` 0.034-0.040); `--execute-steps 16` closes the finger
(0.013-0.019) at the closest approach but leaves the hand 22-116 mm away - **a
chunked policy trained on per-state feedback labels must be executed as
feedback**. The interface is honest and complete; the sensor, trigger and goal are
no longer the limiting terms. **The named next lever is the action precision**: a
**>= 150-episode DAgger store** with the same recipe, scored **offline** on the
close-window joint error (target **< 0.03 rad** ~ 1-2 cm), or a **feedback-shaped
action** (one executed step per decision / a cartesian delta) - a training-schema
change of its own. The touch ablation instruments are in place
(`FRUIT_TACTILE_ZERO=1`, `FRUIT_IMAGE_FREEZE=1`) and are the next cell.
**No-harm**: the acceptance is **7/10, `fingerprint: matches`, `190: PASS`**, its
**459 `[fruit]` lines 459/459 byte-identical** to `logs/p136/accept_final.log`;
`selfcheck.sh` PASS (0 failures, 1 skipped), `106` OK. References
**`61fb5202` / `61fb5202` / `18b101bf`** untouched. Evidence `logs/p145/`.

**P145b (2026-11-13, `logs/p145/` section 11; two **default-inert** interface
fixes, nothing adopted): scaling the DAgger store to >=150 episodes surfaced the
two defects that dominate the data volume.** (a) **The direct episode started at
the close pose.** `configs/waypoints.json`'s `grasp` is the scripted line's close
pose; the demonstrations' frame 0 is a wait pose **0.33-0.35 rad** away (measured
from `demos_v11`'s first action, left and right). The policy's first observation
was therefore a state the demos only reach at the close, with the fruit 0.4 m
upstream, and the DAgger expert's wait label was that close pose too - the demos
and the store taught **two different wait poses**, which is the stay-vs-descend
average the earlier arms measured. The `wait` waypoints are added (`+18` lines,
no existing value moved; P64's config pin re-pinned to **`6d2843a3`**), and
**`FRUIT_DIRECT_START=wait`** starts the direct episode there (default `grasp`,
byte-inert; a bad value raises; the DAgger expert's wait label follows it). (b)
**The 30 Hz demonstration stream was replayed at 120 Hz.** `act` executes one
chunk waypoint per control tick, so the trajectory the model was trained on is
compressed **4x** (P53's census read this as a 10x command dither and a 19.3 mm
same-tick residual; its C2 cell took the half-step `hold=2`). **`FRUIT_POLICY_ACTION_HOLD=4`**
holds each waypoint 4 ticks - the exact 30 Hz cadence. **Measured with both** (a
horizon-4 fine-tune on `demos_v11` alone, `FRUIT_TRAIN_GOAL=moving`, close weight
10, 40 epochs, loss 0.0145, `checkpoints/p145_demo_h4` `bcff04e6`, evaluated at
the wait start with `--execute-steps 4 FRUIT_POLICY_ACTION_HOLD=4`): the closest
xy gap is **9 mm** on the probe and **32-41 mm (left) / 64-94 mm (right)** over 12
episodes against the **69-149 mm** baseline; the catch-up does not convert - the
jaw tracks in xy, **stops at the grasp waypoint (z = 1.29)**, never makes the last
**8-9 cm** to the fruit (1.20), closes **0.4 s early** and lifts nothing
(**0/12**). The offline fit floor is **0.065 rad** (~3 cm at the TCP) and it is
**unchanged** between the 10k-window demonstrations and the 600-window DAgger arm
at 200 epochs - a **representation** limit, not a data-count limit, so more of the
same collection is not indicated. **The named next step is a phase-gated policy
(the 5-skill router already exists) or a cartesian-delta action with an exact IK**,
plus the touch ablation (`FRUIT_TACTILE_ZERO=1`, `FRUIT_IMAGE_FREEZE=1`, built).
Collection shape: 8/8 episodes in 5 min at `--horizon 520`; the 760-tick episode
wedges in the post-close phase (2/8, CPU busy / GPU 2 %), so a **timeout-guarded
chunked runner** is the supported form (`logs/p145/collect_chunks2.sh`). No shipped
default moved; `selfcheck.sh` PASS (0 failures, 1 skipped) after the P64 re-pin;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched.

**P227i (2026-11-21, `logs/p227/`; default off, **nothing adopted**, no `configs/`
change, no reference re-recorded): the owner's single-arm cell (a real gripper arm +
two side bins) named "the Panda's finger drive is weak or absent" as its blocker,
and **that diagnosis is overturned** - the drive tracks in one tick and the grasp
holds 12/12 once two measured constants are right.** The probe (`finger_probe.py`)
reads the asset's drive (k 400 N/m, c 80 Ns/m, **maxForce 7.2 N**; `joint2` a
`PhysxMimicJointAPI`, gearing -1, cap 0) and the repo's profile applied live
(k = 1e5, c = 2000): `set_gripper(0 .. 0.040)` gives **q 0 -> 0.040 and a jaw
0 -> 80.0 mm**, in **one tick**, with caps 60/300 N, the asset's gains and no
gain call all identical - so P227h's 0.0164-0.0195 m row was the **probe's end
pose** (the gripper test ran after the reach servo, pads inside the bin rim), not
the drive. **The defect that did exist is the pad faces**: with
`Usd.TraverseInstanceProxies` (`pad_geometry.py`; the finger links are a
*reference* and report no mesh bound without them - the OpenArm's instance-proxy
trap) each finger is a 76 mm plate whose **faces are 3 mm either side of the jaw
centre when the joints are closed**, i.e. a **6 mm gap at `q = 0`**, so every
close was commanded 6 mm too wide (sep == command, nothing held, 12/12 cells).
`ArmSpec` now carries `finger_face_offset` (OpenArm 0.0, Panda **-0.006**),
`joint_root` (`/World/OpenArm/panda_hand`) and `link_root`, and `arm_specs()`
(two OpenArms / one Panda) - and the build's finger **material**, **drive-cap
writer**, **cap readback** and **header** walk those instead of hard-coded
`openarm_*` prims (the first Franka build authored **no** material and **no**
cap); a real hand of either arm defaults to the measured pair `mu = 2.0`.
**The frame transfers**: the closed fingers separate along the hand's **-Y** and
the jaw is +58.4 mm along hand +Z, so `top_down_quaternion("x")` - the OpenArm's
pick attitude - closes **across the belt with the fingers down at 0.8 mm /
0.11 deg**, while the `"y"` form is 154 mm / 29 deg out of reach (`hand_frame.py`).
**The reach floor is the attitude, not the gains** (`ik_probe.py`): the servo
holds **0.9 mm** down to jaw z **1.240** and breaks at **1.22** (49.8 deg,
stalls 1.223, 23.6 mm xy at 1.20); the repo's tuned Cartesian drive adds a
constant -7.6 mm lag and does not help - P227f's "15.6 mm high" is this
function of the target. **The static grasp gate is 12/12**: belt surface velocity
written to 0 (`SortingScene.step` is `update_app`, so a probe never runs the
belt's own `step()` and the fruit would ride 0.12 m during the close), 4 fruits x
dz 0.035/0.042/0.050 above the fruit's **own** centre, lift **99.1-99.5 mm**,
slip **0.5-2.1 mm** at 0.042; the contact census reads the close **two-sided**
(4.04 + 4.06 N) and the payload +95 mm. **Two things it does not settle**: a
**fixed** jaw height is not equivalent (1/4 at z 1.240 - the Panda's aim must be
`jaw = fruit_centre + 0.042`, which the task's fixed `jaw_target("grasp")` is
not), and on the **moving** belt the close lags ~30 mm, loads one pad first,
drags the fruit 110 mm and loses it - the catch/lead problem, not the hand.
**No default moved**: `grasp_clearance` stays 0.095 and nothing in `configs/` was
re-recorded. No-harm: `accept.sh` **7/10 = 70 %, 9.5 s/attempt, `fingerprint:
matches`, `190: PASS`** with **458/458 `[fruit]` lines identical** to
`logs/p136/accept_final.log` (one pre-existing P227 build print dropped),
`selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new `282` leg (the jaw
laws, `arm_specs`, the spec-driven authoring, the OpenArm set/order, the profile),
`106` OK, `107` PASS. Pins: `control.py`, `scene.py`, `scripts/selfcheck.sh`,
`scripts/282_p227i_arm_spec_selftest.py`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched. **Named next**: the Panda's per-fruit pick aim, its own
`waypoints_franka.json` (`_pose()` is still the OpenArm's joint vectors), then the
moving catch's lead and one scripted attempt on the bins. Evidence
`logs/p227/`.

**P227m (2026-11-21, `logs/p227/`; default off, **nothing adopted**, no
reference moved): the single-arm cell **runs and places** - 4/12 over two seeds,
with **every success on the `right` label and every failure on `left`** - and the
failures are one measured catch class, not the hand.** The enabling wiring, each
scoped to its own cell: `tasks` reads the arm's own waypoint file
(`configs/waypoints_franka.json`, written by `logs/p227/franka_waypoints.py` -
the repo's calibration flow for one arm: `ready`/`wait`/`grasp`/`grasp_lift` +
each bin's above-pose, all six at **2.3-3.2 mm / 0.64-1.33 rad**; both arm labels
carry the same configurations because the task always builds two controllers and
the Panda resolves both to its one arm); `_place_xy_for` returns the **bin** when
`cfg.output_bins` (it returned the *belts'* lane point, so a bin attempt released
over the belt); `_pad_standoff` returns the Panda's **measured 42 mm** tool offset
(`FRUIT_FRANKA_GRASP_STANDOFF`) rather than `finger_len + PAD_LIFT`'s 70 mm; and
`tactile.default_finger_links()` follows the arm spec (with the OpenArm names the
`Contact(...)` constructor **raises** before the first attempt) with a single
sensor set answering for both labels. **Measured** (`FRUIT_ARM_KIND=franka
FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0`, the scripted dynamic catch, `run_attempt.sh`):
seed 5 **3/6**, seed 6 **1/6**, pooled **4/12 = 33 %**, `right 4/8 / left 0/7`;
the place is **in a bin** (`released at (-0.004, -0.606, 1.129)` inside bin N) and
`_place_xy_for` reports `lane 1 at (-0.1, -0.55)`. **The 8 failures are one
class**: the handover fires with the fruit already inside the lead
(`dy=+0.122..0.131 m` against `lead=0.189`), so the settle loop runs **0 steps**,
`coherent axis 1-cos=0.0107-0.0138` reports FAILED ("closing anyway"), the
fingertips are **130-137 mm** from the fruit at the close's start and the catch-up
ends **1329-1550 mm** out with the payload dragged **1170 mm**; the successes are
the attempts whose wait loop ran (131-206 steps), `1-cos = 0.0000`, fingertips
**34-40 mm**. `FRUIT_DYNAMIC_SELECT_S=3.5` (the "commit earlier" lever) is a
**measured negative**: the larger floor **starves the line** (attempts 1-5 `no
eligible fruit`, the candidates at 0.05-0.39 m) - the P56/P58 aperture class, so
the lever is the **pre-pose's length**, not a wider commitment window, and a
bigger `FRUIT_DYNAMIC_OVERHEAD_S` cannot help because the handover is evaluated
*after* the pre-pose. **No rate is claimed** (12 attempts is a direction, P93's
rule). No-harm: `accept.sh` **7/10 = 70 %, 9.5 s/attempt, `fingerprint:
matches`, `190: PASS`**, stream **458/458 identical** to
`logs/p136/accept_final.log` (the P227 build print dropped), `selfcheck.sh`
**PASS (0 failures, 1 skipped)**, `106` OK, `107` PASS. Pins:
`tasks.py`/`rl_env.py` (`TASKS_MD5` follow), `tactile.py`, `232`/`262`... see
`logs/p227/`; references **`61fb5202` / `61fb5202` / `18b101bf`** untouched.
**Named next**: the pre-pose length / in-place settle for this arm (the graph's
one arm cannot serve both fruit phases with a fixed lead), then the per-fruit aim
in the indexed path (the fixed pose holds 1/4). Evidence `logs/p227/`.

**P227n (2026-11-21, `logs/p227/`; default off, **nothing adopted**, no
reference moved): the single-arm cell's left/right split was an **arm-asset
assumption leaking through the arm *label***, and with it fixed the cell places
**15/17 = 88 %** against **4/12 = 33 %**.** The P227m diagnosis (pre-pose length /
settle) was the wrong lever. **The mirror**: the moving catch sets
`hold = top_down_quaternion("x")` and mirrors it for the `left` arm - correct for
the bimanual OpenArm (two mirrored arms, `scripts/97_reach_probe.py`: 2.1 mm with
against 28 mm without) and **wrong for the single-arm Panda**, which authors one
arm serving both labels: the mirror asks for the pads to close *along the belt*,
the P227j pose that is 154 mm / 29 deg out of reach. Measured
(`logs/p227/acq_diag_3_s6.log`): the `left` premove stalls **144 mm** out
(jaw y +0.111 m) against the `right`'s **8 mm**; `premove_probe.py` rules out the
target's x and a stale `_q_cmd` (18-19 mm at x 0.249/0.316/0.34, with and without
a sync, after either label drove the shared arm). `mirrored_arms()` gates all
three hold sites (`_run_impl`'s indexed hold, the catch's wait-at-hover hold, the
coherent block); the left premove reads **144 -> 7 mm** and its first grasp holds
(`lift +0.384 m`, `slip 2.5 mm`, 7.46 N). **The place prims**: `_fingertip_lowest_z`
hard-coded `/World/OpenArm/openarm_<side>_{left,right}_finger`, a null prim on the
Panda, and `UsdGeom.BBoxCache.ComputeWorldBound` **raised** after a good carry
(`attempt_6_s6_fix.log`); it now walks `arm_spec(side).finger_link_names` and skips
an invalid prim (OpenArm set/order unchanged). **The +Y bin needs a calibrated
start**: the carry's own `move_to` from the lift pose ends **181-223 mm** from
every +Y cell (x -0.10..0.06, z 1.38/1.30) and still **148 mm** through a routed
waypoint, while the -Y bin reads 18-31 mm; from the waypoint file's own
`bin0_above` configuration (solved at 3.2 mm) the same servo reaches **9.1-10.0
mm** (`place_reach_probe/staged/routes.log`). So a place leg on the single-arm
asset now **blends the joints** to that calibrated configuration (min-jerk, the
pre-poses' primitive, payload in the pads) and then runs the shipped Cartesian
transit - the OpenArm's place legs keep their measured Cartesian-only path. **The
cell** (`run_attempt.sh`, the scripted dynamic catch, one arm, `FRUIT_BIARM=0`):
seed 5 **6/6**, seed 6 **3/5** (one renderer wedge after 5; its strawberry at
31.13 N is the closed small-fruit class), fresh seed 101 **6/6**, pooled **15/17
= 88 %** placed and **16/17** grasped against P227m's 4/12. **No rate is claimed**
beyond these samples (P93); the mechanisms are: the `left` acquisition class and
the +Y place class are gone, and the residual is the closed small-fruit grip.
Pins: `tasks.py`/`rl_env.py` (`TASKS_MD5` follow), `logs/p227/`; references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched. Evidence `logs/p227/`.

**P227o (2026-11-21, `logs/p227/`; default off, **nothing adopted**, no
reference moved): two closed-loop criteria calibrated for the **other hand** are
made arm-aware, and the single-arm cell reaches **22/23 = 96 % placed**
(14.2-14.8 s/attempt) against **4/12 = 33 %** at the start of the arc.** (1) **The
close freeze**: `force + a stalled span` is the shipped criterion; force alone was
already known to false-fire (a 3 cm strawberry reads 30 N with the jaws 89 mm
open, `logs/p2b_diag_before_1` A4) and the single-arm hand's 76 mm plates plus its
drive breakaway make **both** true before the pads are near the fruit - the close
froze at **87.9 mm around a 31.4 mm strawberry** (4 ticks, 29.88 N, span 85.9 mm;
`logs/p227/attempt_6_s6_fix3.log`) and the lift followed nothing. A freeze wider
than the fruit is not a loaded pinch, so the criterion now also requires
`sep <= pinch_width + 10 mm` on the single-arm asset (`mirrored_arms()` gates it,
the OpenArm keeps the shipped test); the strawberry then freezes at **58.3 mm /
7.37 N / span 63.2 mm** and places. (2) **The catch-up's stop point**
(`desired_tip = fruit + _dynamic_pad_lift`): the 10 mm is the OpenArm's pad lift
under its jaw offset, while the single-arm hand's pads run 0-65 mm below the jaw
centre with the grasp aim 42 mm above the fruit's centre - so the loop chased a
point **33 mm** from any correctly-aimed hand and printed **27-29 mm on every
attempt, successes included** (`attempt_6_s6_cs05.log`), while the handover diag
showed the hand within **~1 mm** in x/y. Using the arm's own pair
(`_pad_standoff(True) - _fingertip_offset`) makes the residual the real error:
**27 -> 4.8-5.9 mm** (inside the 6 mm tolerance) and the attempt **17.0 -> 14.2-14.8 s**.
**The cell** (final tree, `run_attempt.sh 6 <seed>`): seed 5 **6/6**, seed 6
**6/6**, seed 101 **4/5**, seed 202 **6/6** - **22/23 = 96 %**. **Not adopted**:
`FRUIT_DYNAMIC_DESCEND_MARGIN=0.25` (5/6, residuals unchanged) and
`FRUIT_TRACK_CATCH_SPEED=0.05` (6/6 on one seed, residuals identical to the digit
- a branch draw, and the diag says the catch was already accurate). **The residual
class is the 6.9 cm pear** (3 of 23: contact made, 7.3 N, `lift +0.000`) - the
loaded-slide class at the pool's largest, tapered fruit. No rate is claimed
beyond these samples (P93). No-harm: `accept.sh` **7/10, 9.5 s/attempt,
`fingerprint: matches`, `190: PASS`**, stream **458/458 identical** to
`logs/p136/accept_final.log`; `selfcheck.sh` **PASS (0 failures, 1 skipped)**
(`282` grown to pin both criteria); `106` OK, `107` PASS. Pins:
`tasks.py`/`rl_env.py` (`TASKS_MD5` follow), `logs/p227/`; references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched.

**P227p (2026-11-21, `logs/p227/`; default off, **nothing adopted**, no
reference moved): the place blend must **lift clear** of the line first (a
joint-space sweep can dip the payload under the belt), and the 6.9 cm pear is
measured to be a **hand-vs-fruit geometry** question, not a criterion one.** A
pear-only supply (`FRUIT_SUPPLY_SPECIES=pear`, `pear_6_s5.log`) reads **3/6** with
three *different* mechanisms: one catch flail (`tilt0=106.7 deg`,
`q_margin=-0.724 @j7`, `res_end=311 mm`), one empty-hand close (`force@onset=0`,
`contacts@onset=0`, `sep_min=0.2 mm`, `fmax=213 N` - the pads met each other),
and one **clean lift lost in the place leg** (`clean_slip 0.8 mm` on the lift,
then `place0` `clean_slip_max=318 mm`, `onset_row=1`, `clr_win=-74 mm@belt`): the
P227n joint blend sweeps the hand through the main belt. The park's own transit
already has the shape this needs, so the place leg now makes a short vertical
**clear move** (`+0.10 m`, `FRUIT_PLACE_CLEAR`) before the blend - measured, the
pear cell **3/6 -> 5/6**, and the general cell **23/24 across seeds 5/6/101/202
at 15.1-15.6 s/attempt** (the clear costs ~0.4 s). **The pear is the marginal
fruit and it is seed-dependent**: pear-only 5/6 (s5) and 1/6 (s6); the finger
plate is **76 mm** wide along the belt against its 69.9 mm, i.e. **+-3.5 mm** of
centring, while the catch-up converges to the 6 mm tolerance (4.8-5.9 mm); the
failures carry contact (0.96-7.36 N) and no lift. **Tested and not adopted**: a
tighter catch tolerance (`FRUIT_DYNAMIC_CATCH_TOL=0.003`, 3/6 at seed 6 against
1/6 but never converging - residuals 2.9-7.7 mm and the loop burns its budget -
and seed 5's default already reads 5/6: a seed flip, not a mechanism); the close
*does* track the fruit per tick (`ik_step` with `frozen_x` and the live y/z), so
the miss is not a stale aim. **Named next**: `FRUIT_DYNAMIC_TRACE=1` on a pear
close to separate "the pads missed along the belt" from "the pear squeezed out",
then the hand-geometry price (a wider plate is the only lever on the +-3.5 mm,
and the OpenArm's +17 mm width cell was a measured negative). No-harm:
`accept.sh` **7/10, `fingerprint: matches`, `190: PASS`**, stream **458/458
identical** to `logs/p136/accept_final.log`; `selfcheck.sh` **PASS (0 failures,
1 skipped)** (`282` grown to pin the clear move); `106` OK, `107` PASS. Pins:
`tasks.py`/`rl_env.py` (`TASKS_MD5` follow), `logs/p227/`; references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched.

**P227q (2026-11-21, `logs/p227/`; measurement only - **no `src/` change**,
nothing adopted, no reference moved): the 6.9 cm pear is **size + closing-axis
offset**, three levers are negative, and the scripted path's dynamic trace is
**broken** (it writes 0 rows).** Pear-only with the handover/carry diagonals
(`pear_6_s6_hd.log`): the single success is the **60.0 mm** pear; the five
failures are the **65-70 mm** ones with a closing-axis (x) offset of **4.3-6.1
mm** against a 76 mm plate (+-3.5 mm centring), and their `[carry] grasp_lift`
rows read `force@onset=0`, `contacts@onset=0`, `sep@onset=54.7 mm` on a 66.7 mm
fruit - the pads are inside its width with no contact (the payload is no longer
between them) - while the 60 mm success reads `force_min=7.47 N` at
`sep_min=56.8 mm`. **Negative levers**: `FRUIT_DYNAMIC_CATCH_TOL=0.003` (3/6 at
seed 6 against 1/6, but the residual never converges - 2.9-7.7 mm, the loop burns
its budget - and seed 5's default is already 5/6); `FRUIT_DYNAMIC_MIN_INTERFERENCE=0.005`
(1/5, same class: a deeper squeeze cannot centre an off-centre fruit - the near
pad presses 5.5 mm in while the far one stays 4.5 mm out); P227o's margin
(5/6, residuals unchanged); and `FRUIT_DYNAMIC_CLOSE_LOCK_X=0` (2/6 against the
pinned 1/6 - a wash; the pin is a measured OpenArm property). The regrasp already re-aims at the fruit's live
centre and does not convert it, so this is `logs/p42/SIM_LIMIT.md`'s closed class
at the pool's largest fruit (a new pad asset, a force-controlled finger, or a
sub-3 mm presentation; a wider plate is the only lever on the +-3.5 mm and the
OpenArm's +17 mm width cell was a measured negative). **Instrument gap**: on the
scripted path `FRUIT_DYNAMIC_TRACE=1` writes **0 rows** (`logs/dynamic_trace_0*.json`)
because its `_AttemptLocal` buffer is in the attempt thread while
`_dynamic_trace_flush` runs in `run()` on the driver thread; the tracer works on
the direct env only. Evidence `logs/p227/RESULTS.md` §14; `src/` is unchanged from
the accepted P227p tree (`accept.sh` 7/10, `fingerprint: matches`, 458/458 to
`logs/p136/accept_final.log` by construction), references **`61fb5202` /
`61fb5202` / `18b101bf`** untouched.

**P227r (2026-11-21, `logs/p227/`; **one scoped default ships** - the release
trim now resolves on for the single-arm asset - and the place-speed cell is
measured and rejected): the cell's cycle is **14.2-16.6 s** with two dominant
blocks, `place` **4.00-4.13 s** and `release` **1.63 s**, and only the release
is free.** The trim is P86's S2 cell (`FRUIT_SPEED_RELEASE`: dwell 20 -> 0 and
the pad/finger ramps 3 -> 2 = **-76 ticks = -0.633 s**), which P87 shipped
two-line-scoped; a single-arm cell is not a two-line session, so its
`[cycle] release=` was still 1.63 s. Measured here: **1.63 -> 1.00 s (-0.63,
exact), 6/6 placed**, and **6/6 payload-present releases `on_belt=True`** with
`release_bottom -7..-24 mm` (the bin's floor is 70 mm below the belt top, so a
negative bottom is *inside* the bin) and impact -1.8..-2.1 m/s. It now resolves
on through `tasks._single_arm_asset()` while the OpenArm and two-line scopes are
unchanged (`247`/`248`/`249` pass; acceptance **458/458**). **The place is the
larger block and the wrong spend**: a faster clock (100/25 ticks with a 0.07
clear) reads `place 4.0 -> 2.8-3.2 s` and the mixed cell **5/5**, but the
**pear cell 5/6 -> 3/6 with two place-leg payload losses** - the class the cell
is already marginal on - while the safe clock (150/40/0.10) reads the pear cell
**4/5** with one place loss. **Not adopted** (the P88/P89 rule). **The cell on
the final tree**: seed 5 **6/6**, seed 6 **6/6**, seed 101 **5/6**, seed 202
**6/6** - **23/24 = 96 % placed at 14.4-14.9 s/attempt** (was 15.1-15.6); the
single loss is the pear (P227q's closed class) and two slots starved in seeds
5/6 (P56/P58's aperture class). No rate is claimed beyond these samples (P93).
No-harm: `accept.sh` **7/10, `fingerprint: matches`, `190: PASS`**, stream
**458/458 identical** to `logs/p136/accept_final.log`; `selfcheck.sh` **PASS (0
failures, 1 skipped)**; `106` OK, `107` PASS. Pins: `tasks.py`/`rl_env.py`
(`TASKS_MD5` follow), `logs/p227/`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched.

**P227s (2026-11-21, `logs/p227/`; one defect fixed in the instruction ledger,
default off): the model's **decision layer** now drives the single-arm bins cell,
and its ledger was scoring the **release** pose - which for a bin must be above
the rim.** With a descriptor for the two bins (`logs/p227/bins_two_dest.json`,
dest 0 at `(-0.10, +0.55)`, dest 1 at `(-0.10, -0.55)`, `reach: auto`) and the
instruction the cell *is* (`grade=A => 0` + `default => 1`, `262_sort_plan` reads
**OVERLAP none**, 40/80 cells), the run resolves the scenario and the capability
map (`left=[0] right=[1]`), covers the pool 16/16, and **places 6/6** with every
fruit dispatched by its rule - **3 grade-A to the +Y bin, 3 B/C to the -Y bin** -
releases **6-16 mm** from the instructed target: the instruction reproduces the
cell's grade routing. **The ledger read `in_destination=0 mis_sorted=6`**: it
tested `on_output_belt(release_pos)`, and a bin release sits **above the rim**
(1.36 m against a 1.26 m rim; the bin volume ends at 1.32), so every bin delivery
failed the "over the output body" test while its nearest destination was right.
A **bin** destination is now scored at the **settle sample** - the read `placed`
is already scored on, 0.5 s after the release - carried as
`EpisodeResult.settled_pos` (a copy of an existing read, only when an instruction
is armed); a **belt** destination keeps the release pose, because the belt
carries the payload away (its settle sample is 6+ cm downstream). Re-run:
**`in_destination=6 mis_sorted=0`**, settled distances 29-146 mm inside the
correct bin, **6/6 placed** (`logs/p227/attempt_6_s5_instr2.log`). No-harm: the
ledger only runs with an instruction armed and belt destinations keep the old
anchor (P114/P121's cells unchanged); `accept.sh` **7/10, `fingerprint: matches`,
`190: PASS`**, stream **458/458 identical** to `logs/p136/accept_final.log`;
`selfcheck.sh` **PASS (0 failures, 1 skipped)** with three new pins in `282`;
`106` OK, `107` PASS. Pins: `tasks.py`/`rl_env.py` (`TASKS_MD5` follow),
`logs/p227/{bins_two_dest.json,grade_ab.txt}`; references **`61fb5202` /
`61fb5202` / `18b101bf`** untouched. **(ii) a routing the shipped rule cannot
produce**: with `size<55 => 1` + `default => 0` (OVERLAP none, 78/42 cells,
pool dest0=11/dest1=5) the cell reads **6/6 placed, 6/6 `in_destination`, 0
mis-sorted** with the witnesses a **grade-A kiwi (5.4 cm) in the -Y bin** and a
**grade-B apple / grade-C orange (6.5/6.6 cm) in the +Y bin** - the arm label
follows the destination (one physical Panda; the capability map's bookkeeping) -
settled distances 32-126 mm inside the correct bin (`attempt_6_s5_size.log`).

**P227t (2026-11-22, `logs/p227/`; the **first demonstration store for this arm**
plus two provenance fixes; nothing shipped moved): option (b) of the owner's
choice - the learned lane on this cell - starts with the artifact any policy
needs, and it exists: `datasets/p227_panda`, **12 episodes / 2137 frames / 1933
windows, `106` OK**, collected by the shipped collector in its single-arm mode
(`FRUIT_EPISODES=12 FRUIT_DEMO_DIR=datasets/p227_panda FRUIT_ARM_KIND=franka
FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0 FRUIT_CAMERA_RES=240,424`, 13 attempts,
`gate_open=0.00 s`), with the action's arm columns plainly the Panda's
(`[0.441,-1.038,-0.260,-2.545,-0.225,1.521,-0.489]`, min/max -2.72/1.88). **Two
arm-specific provenance labels were wrong and are fixed**: (1) the store did
**not name its arm** - a Panda store and an OpenArm one differed only by an
`assets.py` md5 that moves for every edit - so `assets.scene_provenance` now
carries `scene.arm = {kind, usd, resolved, labels, arm_joints, finger_joints,
finger_links, tcp_link, open_value, jaw{offset,per_joint,face_offset}}` from the
resolved `ArmSpec` (one builder, both manifest writers; degrades to
`{kind, usd, resolved: false}` on the CPU probes); (2) `_finger_drive_readback`
compared every joint against `finger_maxforce_intent()`'s "asset's own" cap,
which is the **OpenArm's 10 N**, so this arm's manifest read `profile: custom` +
`readback_matches: false` while its joints carried the shipped pair - a cap is
only *intended* when the build wrote one, so the cap check now runs only then
(re-collected store: **`profile: finger_damp02`, `readback_matches: true`**,
`panda_finger_joint1 {k 1e5, c 2000, maxForce 7.2}`, joint2 the mimic 0), and the
collector's log names the read-back's own first row. **What this implies for the
policy, measured**: the action space is structurally the same (7 joints + a
finger scalar) but the values are a different arm's, so the existing checkpoints
and their `demos_v11` anchor cannot be reused (P144: `--base ""` on 45 episodes
destroys the grasp, 0/12) - a Panda policy needs a much larger from-scratch store
or a different recipe, which is the lane's next decision. No-harm: `accept.sh`
**7/10, `fingerprint: matches`**, stream **458/458 identical** to
`logs/p136/accept_final.log`; `selfcheck.sh` **PASS** with three new pins in
`282`; `106` OK (the new store audits clean), `107` PASS. Pins: `assets.py`,
`scene.py`, `scripts/40_collect_demos.py`, `scripts/282_p227i_arm_spec_selftest.py`;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched.

**P227u (2026-11-22, `logs/p227/`; one **scenario defect fixed in `fruits.py`**,
scoped to the bins cell; nothing shipped moved): a bins cell **never recycled a
placed payload**, so the 16-fruit pool drained and a long collection starved.** A
48-episode shard read **17 successes in 144 attempts** against the gate's 6/6 -
and the log carried only 17 `episode N:` rows, the other 127 being the
collector's **silent `select_target -> None`**. `FruitSpawner.update`'s
end-of-line sweep recognised only a belt's **discharge tray**
(`cfg.on_output_tray`), so a payload left in a bin stayed there forever. Fixed:
with `output_bins`, a payload inside a bin's volume (`output_lane_of`), nearly
still, is discharged after the tray's own dwell (`output_tray_dwell_s`) with the
same `discharged` counter and a `[bin N]` tag; the shipped belt/tray tests are
untouched (the gate never sees the defect - six attempts). Same shard re-run:
**48 successes in 49 attempts**, rows reading `discharged to the bin at
(-0.10,-0.57) (settled 17.6s) [bin 1]` (the dwell is the collector's
between-attempt update cadence, i.e. the payload is recycled at the next attempt
boundary). **The shard**: `datasets/p227_panda_c1`, **48 episodes / 7912 frames /
7096 windows, `106` OK**, `profile: finger_damp02`, `readback_matches: true`,
`scene.arm.kind: franka` - with `datasets/p227_panda` (12) the arm's first **60
episodes**, the precondition for the policy work and the reason a longer
collection could not have been made before this fix. No-harm: `accept.sh`
**7/10, `fingerprint: matches`**, stream **458/458 identical** to
`logs/p136/accept_final.log`; `selfcheck.sh` **PASS**; `211` **ok (115 checks)**;
`106` OK, `107` PASS. Pins: `fruits.py`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched.

**P227v (2026-11-22, `logs/p227/`; one **width** defect fixed in the policy
store; nothing shipped moved): the learned lane on this arm is blocked by an
observation width that was a module constant, not the store's property.** A
one-episode direct smoke with the Panda *starts* (the checkpoint loads, `[rl] env
ready`, an episode begins) and then the normaliser rejects the observation:
**shapes (13,) against (26,)**. The proprio is the **whole articulation's** DOF
vector + finger + 2 tactile forces - **25 on the bimanual OpenArm** (22 joints),
**13 on the single Panda** (9 joints + 1 + 2 + the speed channel) - while
`policy/data.py` declared `PROPRIO_DIM = 25` for every store although its windows
concatenate the *actual* arrays (9 + 3 = **12**). Fixed: `EpisodeStore.proprio_dim`
derives from the store's own first episode (`joint_positions.shape[1] + 1 + 2
[+ speed] [+ cmd]`), raising if episodes disagree; the constant remains the
empty-store fallback. Measured: `datasets/p227_panda_c1` -> **12** (13 with the
speed channel), `datasets/demos_v11` -> **25** unchanged; `selfcheck.sh` PASS. **The
lane's remaining requirement** is a training run built for 12/13-D that does not
use the OpenArm anchor (`demos_v11` is another arm's joint space; P144: `--base ""`
on 45 episodes destroys the grasp) - with 60 episodes the honest form is a small
**from-scratch** cell whose endpoint is the interface end to end, not a rate.
Pins: `policy/data.py`; references **`61fb5202` / `61fb5202` / `18b101bf`**
untouched.

**P227w (2026-11-22, `logs/p227/`; the **lanes's width guard** in the env made
arm-correct; nothing shipped moved): the arm's own 12-D checkpoint was refused by
`rl_env`.** `__init__`'s checkpoint guard compared the artifact against
`25 + speed + cmd` - the bimanual OpenArm's constant - while `proprio()` assembles
the **whole articulation's** DOF vector + finger + 2 tactile forces (25 on the
bimanual OpenArm, **12 on the single Panda**). The guard now derives the width it
will build (`len(robot.dof_names) + 1 + 2 [+ speed] [+ cmd]`) and its message says
which arm it is, so a checkpoint is refused on the *arm it was not trained on*
rather than on a constant. Measured: `checkpoints/p227_panda1` (12-D, trained
from scratch by `scripts/50_train_policy.py` on the 60 episodes - 4.59 M
parameters, val 0.0325, router 0.994) loads, `[rl] env ready`, and **both
episodes run to their horizon** (1266 / 1386 ticks) with `[rl] episode` rows;
they fail (`fruit fell off the line`) - a 20-epoch model on 48 episodes is not a
policy, the cell proves the lane. The P28 leg's "refuses a disagreeing
proprio_dim" pin was re-phrased onto the derived form (same comparison). No-harm:
`accept.sh` **7/10, `fingerprint: matches`**, stream **458/458 identical** to
`logs/p136/accept_final.log`; `selfcheck.sh` **PASS**; `106` OK, `107` PASS. Pins:
`rl_env.py`, `logs/p28i/check_speed_channel.py`; references **`61fb5202` /
`61fb5202` / `18b101bf`** untouched.

**P227x (2026-11-22, `logs/p227/`; a **merge provenance fix** and the lane's two
measured blockers): 156 episodes, a 12-D model trained from scratch, and the
deployment closes 15 cm short for a reason the record already knows.** The store:
`datasets/p227_panda_all` (12 + 48 + **96 in 100 attempts**), **156 episodes /
25775 frames / 23123 windows, `106` OK**; the merge had **lost the provenance**
(it read `scene.arm: null` while every shard carried `kind: franka`) so
`41_merge_demos.py` now carries the shards' descriptive blocks when they agree and
**reports** the ones that disagree (`episodes_target` 12/48/96 here) - the merged
store reads `arm: franka`, `panda_joint1/2`, `profile: finger_damp02`. The model:
from scratch sized by the store (`50_train_policy.py`), `proprio_dim=12
goal_dim=8`, **4.59 M params**, 12 epochs batch 64 -> `train 0.0286 val 0.0276
router 0.990` (vs 0.0325 on 48 episodes; the OpenArm lineage sits at 0.013-0.026),
`checkpoints/p227_panda156`. **The deployment** (3 episodes): the interface is
complete - the artifact loads, `env ready`, and every episode **closes on the
fruit** (`|jaw-fruit|xy` 14.8-15.0 cm) - but **at the 0.15 m gate**, then "fruit
did not follow the gripper": P143's finding, and here its cause is that the
**demonstrations start at the pick pose** (the collector records from the
pre-pose), so the policy has no approach to clone. P145b's fix is the one this arm
needs: collect and deploy from the **wait** pose (`FRUIT_DIRECT_START=wait` + this
arm's calibrated `wait` waypoint). **Also measured**: the trainer's skill
histogram over 156 episodes is `approach 9662 / grasp 2336 / lift 13735 / place
42` - the place phase is 0.18 % of the windows, a labelling/window property (the
episodes do reach the bin: fruit y 0.50 -> -0.55, z settles 1.11), so a
place-weighted cell is the training-side lever if the next checkpoint must own it.
No-harm: `selfcheck.sh` **PASS**, `107` **PASS (21 checks)**, `106` OK; references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched.

**P227y (2026-11-22, `logs/p227/`; three **hard-coded start-pose sources** made
arm-correct, and the deployment's start measured): the demonstrations are right
(finger closes at `|jaw-fruit|xy` **1.4 mm** p50 over 156 episodes) and the
deployment's 15 cm close was an interface mismatch, localised by recording one
episode and diffing it against a demo.** (1) `rl_env` loaded
**`configs/waypoints.json`** for its own start/park poses instead of the task's
file, so the reset teleported the Panda to the **OpenArm's joints** - the
recorded frame 0 was **~4 rad** from the demos'; fixed to
`self.waypoints = self.task.waypoints` (same file on the OpenArm), and the
residual start-pose distance falls **~4 -> 0.456 rad**. (2) The demos' frame 0 is
a **linear family in the fruit's x** (P160's `configs/start_pose_family.json`,
fitted on the OpenArm); **this arm's** family is now fitted on the 156 episodes
(`q_j(x) = a_j + b_j x`, **rms 0.006-0.018 rad**, mean 0.011 against the OpenArm's
0.014-0.017) into `configs/start_pose_family_panda.json`, used with
`FRUIT_DIRECT_START_ALIGN=1 FRUIT_START_FAMILY=...`. (3)
`119_rl_fidelity.py`'s width feed refused a 12-D artifact; it now feeds the
checkpoint's own width from the store (a width the store cannot supply still
refuses), and the readout measures the model at **0.100 rad / finger 0.0010 /
phase 95 %** (approach 100 %, grasp 100 %, lift 90 %) - the model is usable on its
own demonstrations. **What remains misaligned, measured**: the residual 0.456 rad
sits on j4/j6/j7 (the family pose lands, then the reset's settle and the first
action move it), and the episode still closes at the gate distance
(`finger=0.0046, |jaw-fruit|xy=14.9 cm`) with `fruit left the pick station during
the close (494 mm)`. The instrument for the next pass is the recorded pair
(`logs/p227/obs_cmp2/` vs the store) - the same diff that found these three.
No-harm: `selfcheck.sh` **PASS**; `106` OK. Pins: `rl_env.py`,
`configs/start_pose_family_panda.json`, `scripts/119_rl_fidelity.py`,
`logs/p28i/check_speed_channel.py`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched.

**P227z (2026-11-22, `logs/p227/`; **the deployment's observation was one channel
wrong** - the mask was fed at 255x - and with that and five related interface
defects fixed the single-arm learned lane goes **0/7 -> 12/12 placed**):
the demonstrations were already right (the finger command drops below 0.030 at
`|jaw-fruit|xy` **1.4 mm** p50 over 156 episodes), so a deployment that closed at
**14.8-15.0 cm** had to be an interface mismatch. P227y fixed two sources; this
phase found four more, and every one is measured by the same instrument - one
`--record` rollout diffed against the store's own frame 0, channel by channel.
**(1)** the start family had **only a `left` key** (the `right` key was a silent
fall-through to the IK form: `|q0 - family|` 0.002 rad on `left` episodes against
**0.468** on `right`), now written under both keys - the two bins fit the same
line to rms 0.010/0.011 rad, because there is one physical Panda.
**(2)** `FRUIT_DIRECT_START_ALIGN`'s gate accepted only the literal `"1"` while
its dispatch wanted `family`/`demo`, so **the family mode was unreachable**; the
gate now accepts any non-off value and `"1"` keeps the IK form.
**(3)** the deployment rendered at the scene default **480x848** while every
store is **240x424** - `FRUIT_CAMERA_RES=240,424`.
**(4)** `FRUIT_POLICY_ACTION_HOLD=1` replays a 16-waypoint chunk at **120 Hz**
while the demonstrations are **30 Hz** - the demos hold their start pose for ~50
frames and the deployment consumed the same chunk in 12 - so the recipe sets
**4**. **(5)** verified and **not** changed: the frame order. A first pass
"fixed" it to newest-first and the replay test below showed the store's frame 0
is the *older* one (the loader builds `[t-1, t]`, `for k in range(obs_horizon-1,
-1, -1)`), so that edit was backed out.
**A claim this phase made, measured, and WITHDREW - the mask was never wrong,
and the canary is what refused it.** An offline replay that fed the stored uint8
`target_mask` (0/255) straight into `runtime.push_frame` read the channel at
**0.0902** against the store's **0.0004**, which looked like a 255x deployment
defect and produced a `/255` in `push_frame`. It was wrong: **neither real caller
passes a raw mask** - `rl_env._observe` and `60_eval_policy.py:335` both build
`(seg == target_id).astype(np.float32)` first, which *is* the training scale - so
`push_frame`'s contract is a 0/1 mask and the divide made the deployment wrong.
**`scripts/accept_policy.sh` read 3/10 = 30 % with the divide in place, below its
0.60 floor against a 5-8/10 recorded band**, and that is the cell which caught
it (it is the only one whose caller normalises). Reverted: `policy/runtime.py`
now differs from its pre-phase state by **comments only**, and the comment names
the contract so the divide cannot be re-added. **The instrument rule**: an
offline replay is a control only when it enters through the same door as the
caller - same normalisation, order and dtype (P114/P136's `--same` discipline);
this one did not. The useful half still stands: replaying five store windows
through `push_frame` with the caller's own mask reproduces the loader's image
tensor to **1.4e-7**, so the deployment input *can* be shown to equal the
training input - it just was not the thing that was broken. **The single-arm
cell's arms were re-measured on the reverted tree and are recorded in
`logs/p227/RESULTS.md` 22.7** (the first 11/12 was measured with the divide in
place). **The canary is NOT ADJUDICABLE this phase**: 3/10 with the divide,
4/10 without, against a 5-8/10 band, and the same-batch control (the four files
`git stash`ed) **wedged twice with zero episode rows** - the machine had other
`dynvla` simulators holding ~16 GB of the GPU and this build wedges at the loop
header when it does. What decides it is **mechanical inertness**: `runtime.py`'s
diff is comments only, and `rl_env.py`'s three edits are the `START_ALIGN`
gating (unset resolves `"0"` -> skip, the same decision as before), the
`_aligned_start()` `is None` fix (under `FRUIT_CONTINUOUS_TRANSIT=1` only) and
prints behind `FRUIT_DIRECT_START_DIAG=1` - the canary sets none of them, so its
4/10 is this tree's number and the 5-8/10 band is stale (three-lane flip and
revert, park default, release clock) rather than contradicted.
**Model quality was never the binding term, and that is measured**: on *hold*
windows through the training loader, `moe_v13s` on `demos_v11` reads p50 **0.050
rad** and `p227_panda156` on its own store **0.061** - this arm's model is as
good as the shipped one on the phase that decides the wait. **What the wait
exposes**: the demos are *exactly* stationary (`|q(t)-q(0)|max = 0.000 rad` at
t=20/50) while the deployment drifts **0.3-1.3 rad**, because the model's hold
output carries a **deterministic** bias of 0.06 rad (std across sampler seeds
0.001-0.02; DDIM 8/16/32/64 all read 0.13-0.26, so it is not sampler noise), and
25 chained decisions make it the whole drift - the drifted arm then closes at the
P143 0.15 m gate instead of at the fruit. Two cheap repairs are measured and do
**not** work: a higher DDIM budget does not move a bias, and a delta-servo on the
chunk's own differences *is* the chunk's displacement (the differences
telescope). So the recipe ships the architecture the OpenArm lane already uses -
**the model approaches, the scripted primitive catches and places**,
`FRUIT_POLICY_TRIGGER=arrival` fires it on `t_arrive <= lead` independently of
the model's own close, and all 12 episodes below fire it. **The cell**
(`scripts/284_single_arm_policy_gate.sh` is the six-setting recipe): seed 901
**6/6**, seed 902 **6/6**, pooled **12/12 placed** (floors 0.60 and 0.80, both
PASS). Before this section the same checkpoint read **0/7** on four runs, every
episode firing its own close at 12.9-15.0 cm. **No rate is claimed** beyond
these two arms (P93); the claim is the class shift (the failures are no longer
"the arm never reached the fruit"). The cell was first read **11/12** with the
withdrawn mask divide in place and reads **12/12** on the reverted tree - the
direction the revert predicts, still one draw. **Validation video** (the owner's standing rule):
`logs/video_panda/` + the archive at
`/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/p227z_panda_policy/`
- five clips (observer / overhead / gripper / head / side_by_side), 35.4 s each,
3/3 placed (strawberry 3.1, lychee 3.7, peach 6.1 cm), with a README naming the
checkpoint and the recipe. **The continuous clip the owner asked for next is
built, and it exposed a latent abort**: `_begin_pick`'s transit branch read
`self._continuous_return(active, self._aligned_start() or start)`, and
`_aligned_start()` returns an **ndarray**, so `or` raised `ValueError: The truth
value of an array with more than one element is ambiguous` and the first
continuous clip died after pick 1 (`logs/121_policy_video_traceback.txt`) - two
opt-in features (the P225n transit and a start alignment) had never been run
together. Fixed to an `is None` test (the shipped per-episode reset never reaches
the branch) and pinned by the selfcheck leg **`P227z continuous return`**. The
clip is then **3/4 picks placed in one episode** (`logs/video_panda_cont/`,
archived alongside the per-episode five), 54.8 s at 30 fps, all four on the same
side with a **263-tick (~2.2 s)** return transit between picks, and **"no flash"
is measured**: ffmpeg's scene-change detector reports **zero** frames above a 0.10
score over `observer.mp4` (the clip's highest score is 0.0214), whereas a
teleport would move the arm ~1 m in one tick. The clip drew **4/4** while the
withdrawn divide was in place and **3/4** on the reverted tree - a draw, not an
arm (the loop conditions on rendered frames). **The five-minute continuous run**
(`--continuous 26 --capture-every 2 --views observer,overhead` - the sensor had to
grow a capture-set flag, because `121_policy_video.py` buffers every frame and
5 min x 4 views is ~60 GB of RAM): **26 picks in one episode, 350.07 s, 16/26
placed = 61.5 %**, one reset, two views, **zero** scene-change frames above 0.10
(max 0.0204). The deficit is **one transition class**: **5 picks fired the
arrival trigger with `t_arrive < 0.5 s`** - the fruit was already at or inside
the station when the approach finally reached its fire tick - and they placed
**1/5**, against **15/21 =
71 %** with a real lead (Fisher two-sided **p = 0.055**); the inter-pick gap is
**263 ticks** (the return transit and nothing more) on 7 transitions - but a
**10-pick cell on the same recipe reads 120-150 tick gaps and 9/10 placed with
every `t_arrive` at 1.56-2.81 s**, so the gap is **not** the mechanism (that
inference was over-read and is corrected in `logs/p227/RESULTS.md` 22.8); the
late fire is the *approach's* own timing. The class itself stands (no lead, no
catch-up room) and the software lever is the **skip rule** (`FRUIT_SKIP_LATE`,
22.9) - the owner's own cell semantics: several arms share a line, so a fruit
already inside this arm's window is another arm's.
No-harm:
`scripts/accept.sh` reads **7/10 = 70 %,
`fingerprint: matches`, `190: PASS`** and its **459 `[fruit]` lines are 458/459
identical** to `logs/p136/accept_final.log` - the single difference is P227i's
arm-spec build print (`... kind=openarm base_z=0.790`), not this phase - so the
scripted line is inert (it never imports the policy runtime). `selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `106` OK. Pins: `policy/runtime.py`,
`rl_env.py`, `configs/start_pose_family_panda.json`,
`scripts/284_single_arm_policy_gate.sh`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched; ckpt `moe_v13s` `61da390a`, `p227_panda156`. Evidence
`logs/p227/{RESULTS.md section 22,record_trig_901.log,record_trig_902.log,
video_panda.log,fidelity_panda156.log}`, `logs/video_panda/`.

**P227aa (2026-11-22, `logs/p227/`; the owner's two safety/ownership questions -
`FRUIT_SKIP_LATE` and the emission envelope ship **default off**, no reference
moved): the arm's "weird twisted motion" is the **doomed attempt**, and it is
removed by not running one.** Measured on the phase's 22 recorded episodes:
placed attempts carry a **0.10 rad** single-joint range and **9** direction
reversals p50, failed ones **1.18 rad** and **44** (worst **1.77 / 604**, the kiwi
whose fruit had left the line and whose loop ran the policy to the horizon). The
command-side cause is the policy's absolute 7-joint target: its per-tick step is
p50 0.16 rad with a **maximum 0.89 rad**, i.e. **20x** the arm's own
**0.0454 rad/tick** (5.45 rad/s) - `resolve_target_rate`'s docstring already
named the consequence, P207 built the fix, and this phase measured *when* it
happens. **Three rules, and the recipe now carries all three**: (1) **the
ownership rule the owner asked for** - `FRUIT_SKIP_LATE=<s>` (new,
`resolve_skip_late`, strict parsing, unset/`0` = the shipped path) ends the
attempt **on the tick the arrival trigger fires with `t_arrive` below the
threshold**, with the note `skipped: no lead (...) - not this arm's`; on a line
with several arms a fruit already inside this arm's window belongs to another
one, so it is handed off instead of chased. (2) `FRUIT_POLICY_TARGET_RATE=5.45`
ramps the emitted target at the arm's own `maxJointVelocity` (measured **6/6**
placed, so the cap is free in count). (3) `FRUIT_POLICY_JOINT_CLAMP=1` clips the
targets to `get_dof_limits()` (P53 C1, free). **Measured on the 26-pick
continuous cell** (seed 902, one reset, `--record`, the three rules on): **25/26
placed = 96.2 %**, joint range p50 **0.12** / worst **0.85**, reversals p50 **12**
/ worst **27**, and the worst episode is **43 frames** instead of 288 - the
failures' 1.18/44 signature is gone. **Read the count as a branch** (a 26-pick
episode re-times every presentation; 16 -> 25 is not the rules' count) - what
the rules changed is the **shape**. **The skip rule was not exercised by that
cell** (0 fires, that branch never put a fruit inside the window), so it is
proved separately: with `FRUIT_SKIP_LATE=3.0` - above every lead this cell
produces - **all 3 attempts of a 3-pick cell skip** (`picks placed 0/3`, three
`[skip]` rows, the loop advancing each time, nothing raising), so the rule is a
real hand-off and not a silent no-op. **Corrected in the same pass**: 22.8's
"a short inter-pick gap means the next fruit was already waiting" is **wrong** -
a 10-pick cell on the same recipe reads **120-150 tick** gaps and **9/10** placed
with every `t_arrive` at 1.56-2.81 s; the late fire is the **approach's** own
timing, and only the class (5 picks at `t_arrive<0.5 s`, 1/5 placed against
15/21) stands. Also recorded, and **not** the motion: the 38 `carry ...
re-anchoring` rows (470-941 mm) are a stale cross-pick `_grip_centre` corrected
before the leg runs. Pins: `rl_env.py` (`resolve_skip_late`, the guard site, the
`[skip]` row, `skip_late=` in the emit banner),
`scripts/284_single_arm_policy_gate.sh` (the three settings are in the recipe),
`scripts/selfcheck.sh` (`P227aa skip rule`: unset/`""` -> 0.0, `0.5` -> 0.5,
`-1`/`abc`/`nan`/`inf` refused); references **61fb5202 / 61fb5202 / 18b101bf**
untouched. Evidence `logs/p227/{RESULTS.md 22.9-22.10,skip26.log,skip26/,
skipforce.log,bedsel_cont10.log}`.

**P227ab (2026-11-24, `logs/p227/`; one warning and one disk-backed buffer, no
default moved, no reference moved): the "missing return motion" in the continuous
clips was a **dropped env var in my own recording command**, and the instrument
that had to catch it is `gap_ticks`, not the image.** The owner reported that from
`video_panda_5min_safe` onward the arm **no longer travels from the output bin
back to the belt** - it appears beside the belt. Root cause: when the three safety
rules were added to the recording command, `FRUIT_CONTINUOUS_TRANSIT=1` was
dropped, so `_begin_pick`'s `_transit` was False and every pick boundary fell back
to `teleport_joints`. **The discriminator is one log number**: `[cont] pick N`
prints `gap_ticks`, the simulated time between picks, and the return transit is
**150 ticks** (90 blend + 60 settle) plus a settle, so a continuous clip reads
**>= 263** - the good run `video_panda_5min` reads 245-644 and `video_panda_final`
263-647, while the two bad ones read **120 / 139 / 150**. **Two of this phase's
own readings are withdrawn with it**: (a) "the image does not jump there" - a
whole-frame mean dilutes a localized snap; (b) the block-max metric that replaced
it **does not separate the two cases either** (67 events above 20 grey levels in
the clip with the return against 79 in the one that teleports, 242 vs 165 frames
over threshold - a closing gripper, a catch and a snap look alike). **Read rule:
a continuous clip's continuity is proved by `gap_ticks` or by a joint trace, never
by an image metric.** **The counts are three-way, and my first read of them was wrong** (26 picks, seed
902, one reset, only the transit and the three rules varying): transit **on**/rules
off **16 placed of 26 offered, 0 skipped**; transit **on**/rules **on 13 placed, 10
skipped (`no lead`), 16 attempted**; transit **off** (teleport)/rules on **25
placed, 0 skipped**. A **hand-off is not a failure** - it is the owner's multi-arm
semantics - so the right denominators are **placed per attempted** and the hand-off
rate: **81 % (13/16)** with the rules against **62 % (16/26)** without, having
handed **38 %** of the offered fruit to the next arm, and the class that disappears
is exactly the doomed attempt (`grip/carry loss` **7 -> 1**, Fisher **p = 0.0496**);
the placed-per-attempted difference itself is **p = 0.30** at n = 26, a direction
and not a rate. **The teleport is still what inflates a raw count** (25 vs 13, **p =
0.0003**; 25 vs 16, **p = 0.0048**) because it returns the arm in one tick, and
22.10's 16 -> 25 stays **confounded and marked so in `logs/p227/RESULTS.md`**. **The
read rule**: a cell with a hand-off has three outcomes (placed / failed / not-this-
arm's), and a two-way denominator books the third as the second - the same class of
error as 22.12/22.13's image metric, in a different coat. The honest sentence one
level up is 22.12's: **the return is a throughput object** (2.2 s per pick), not a
cosmetic one.
**Two guards ship**: `121_policy_video.py` prints `[video] WARNING: --continuous
without FRUIT_CONTINUOUS_TRANSIT=1 - every pick boundary will TELEPORT the arm
back to the wait pose ...` at the one call site a demo uses (the knob stays opt-in
in the env - P225n's scope is unchanged), and every clip's overlay now carries a
**monotonic `T=`** beside the per-pick `t(pick)=` (the per-pick clock restarts at
every pick by construction - `start_tick` is taken when that pick begins - and
read as a cut to the owner; no frames were ever dropped: `nb_frames` 9442 at
30 fps = 314.733 s against a 314.734 s container). **The buffer fix is the other
half**: a 26-pick clip at 30 fps x 2 views is **~46 GB of arrays**, which thrashed
this machine's 2 GB swap and left a run **crawling for 16 h at pick 19 of 26
before it was killed** - `--frames-dir` now writes JPEGs and buffers paths, and
the encoders normalise **one frame at a time** (`prepared = [normalise(...)]` is
gone, so a disk-backed clip is never materialised twice). Measured in both modes
on a 2-pick cell: RAM 2/2 placed, 360 frames; disk 2/2, 358 frames, 716 JPEGs
(the difference is the loop's non-reproducibility, not the buffer). Pins:
`scripts/121_policy_video.py`, `scripts/selfcheck.sh` (`P227z video views`,
`P227aa skip rule`, `P227ab disk frame buffer`), `src/fruit_sorting/rl_env.py`
(the return's phase diag: `lift_moved`, `lift_ticks`, `lift_step`,
`blend_cmd_step`, `blend_err`, all under `FRUIT_CONTINUOUS_TRANSIT_DIAG=1` and
`if _diag else None`, so the shipped path is byte-identical). The correct clip is
`logs/video_panda_final/` (**4 min 24 s**, 15 fps, 3965 frames, 13/26 placed,
`gap_ticks` 263-647); `video_panda_5min_safe/` and `video_panda_30fps/` are kept as
**error references** with a banner in their READMEs. References
**61fb5202 / 61fb5202 / 18b101bf** untouched.

**P227ac (2026-11-24, `logs/p227/`; one knob and one explicit branch, both default
off / behaviour-preserving, no reference moved): "the arm reaches under the bin" is
**measured false**, and the odd posture is an **unbounded close chase**.** Measured
with `RL_ENV_DEBUG=1` over 8 bins episodes (177 sampled decisions): the jaw stays at
`y` **-0.108..+0.011**, `z` **1.259..1.335**, `x` 0.212..0.381, while the bins are
at `|y| = 0.55` (inner face 0.40), floor **1.10**, rim **1.26** - **zero** samples
below the floor, **zero** with `|y| > 0.40`, and the nearest wall **0.29 m** away.
The bins sit **behind** the robot (`x = -0.10`) while the arm works on the belt, so
a side or overhead camera overlaps them at a depth 0.3-0.4 m away: the "under the
bin" sighting is **perspective**, and `docs/`-style read rules apply - a claim about
where the hand is comes from `jaw=(x,y,z)`, never from a silhouette. **The posture
is real and had no bound**: the delivered clip's pick 4 reads `close: fruit drifted
**380 mm** off the pick centre (cross-belt); re-closing on it where it is`, and on
that attempt the arm's **j4 extended 0.85 rad** where placements span **0.42-0.46**
- the re-close follows the fruit to wherever it drifted (`gripper.follow_centre(
fruit_now)`) and only the **last** attempt aborted. New
**`FRUIT_CLOSE_DRIFT_MAX=<m>`** (default off = the shipped path bit for bit, strict
parse) sends a re-close beyond the threshold down the **existing** abort body (the
measured `fruit left the pick station ... aborting the attempt instead of chasing
it` path) with its own note. **Its status is recorded honestly: the path is rare** -
one fire in the delivered clip's 26 picks, **none** in 8+8 episodes at 0.10 m, none
in 3 at a forced 1 mm (the first close succeeded in all of them) - so it is pinned
by shape (`P227ac close chase cap`) and not exercised end to end. **Owner decision B
(2026-11-24), the place-height question: the height is the BIN's, not the belt's** -
the owner rejected the "keep the free fall" framing outright ("the height should be
decided by the bin itself - why is it still the belt?"), and they were right. The
defect: `_place_low`'s floor was `cfg.output_belt_top_z` **unconditionally** (1.35)
while the bins are a **1.10** floor with a 1.26 rim, so `need = bottom - 1.35 -
0.025` was **-0.057..-0.073** on every bins leg and the accompanied descent was
**skipped** - the payload was released ~5 cm above the rim and fell **0.20 m**.
`_place_low` now takes the **destination's** surface (`bin_floor_top_z` for a bin,
`output_belt_top_z` otherwise) with `bin_index` threaded in. Re-measured **6/6
placed**: `low_drop` **0.000 -> 0.182-0.197 m**, the payload stops **3.8-3.9 cm
above the bin floor**, the fingertips **4.0-5.5 cm above the floor** and 10.5-12.0 cm
below the rim - inside the mouth, 9+ cm clear of the walls, clear of the floor by
the fingertip margin. **The belt/rail cells are untouched** (the branch needs
`output_bins` *and* a destination index), so the acceptance is the no-harm gate.
Pinned by `P227ac place floor (bin)`. Instrument:
**`FRUIT_PLACE_HEIGHT_DIAG=1`** prints one `[place] bin= floor= rim= jaw_z=
payload_bottom= fingertip_z= low_need= low_drop= bin_hold= below_floor= below_rim=`
row per place leg (four reads the caller already has, plus config arithmetic).
Pins: `tasks.py`, `rl_env.py` (`TASKS_MD5` follow), `scripts/selfcheck.sh`;
references **61fb5202 / 61fb5202 / 18b101bf** untouched. Evidence
`logs/p227/{RESULTS.md 22.15,jaw_space.log,bin_hold.log,cap_0.10.log,cap_forced.log}`.

**P227ac addendum (2026-11-24, owner decision C): the bins are **shallow-rim**
now** (`bin_wall_height` **0.16 -> 0.030**, rim 1.26 -> **1.13**, overridable with
`FRUIT_BIN_WALL_HEIGHT`). Decision B (the place height is the bin's own floor) had a
consequence the owner would not accept: the accompanied descent put the fingertips
**10.5-12.0 cm below the rim** on every place. A shallow rim removes that without
giving up the descent: measured on 8 bins episodes, `low_drop` 0.179-0.193 m,
`payload_bottom` **1.139-1.140** (floor + 39-40 mm, unchanged), and **`below_rim`
+0.013 .. +0.028** - the pads stay **1.3-2.8 cm above the rim** while the payload
still stops ~3.9 cm above the bin floor, so the free fall is still ~0.04 m. The one
loss in that cell is a `grasped=False` lychee (the grip class, not the rim), and the
recycle census settles every placed payload **at the bin centres**
(`discharged to the bin at (-0.10..-0.11, +-0.54..+0.55)`, 3.0 s) - a 3 cm lip holds
them. **The margin is a paired design value, not a coincidence**: the descent stops
the payload at `FRUIT_PLACE_LOW_CLEARANCE` (**25 mm**) and the fingertips sit ~4 mm
higher, so a rim at `floor + 30 mm` leaves **~13 mm**; lowering the clearance below
~0.020 puts the pads under the rim again - **keep the pair together**. The belt/rail
cells never read this field (bins are only built with `FRUIT_OUTPUT_BINS=1`), so the
scripted acceptance is unaffected. Pinned by `P227ac shallow rim`; the scripted
single-arm gate (`scripts/283_single_arm_gate.sh`, which runs the *scripted* bins
cell through the same `_place_low`) is the other consumer.

**P227ad (2026-11-24, `logs/p227/`; a training flag, a trigger wire and a
measured simplification - **no default flipped**, references untouched): the owner
asked two questions that turned out to be the same question - *the fruit's position
and velocity must come from the model, reality will not give truth*, and *if the
model only approaches, are the other skill experts useless?* - and both are now
answered with measurements.** **(1) The router's other four experts are dead weight
at deployment, and that is measured**: on 400 store windows the router switches by
phase with 0.93-0.99 confidence (approach **0.982**, grasp **0.925**, lift
**0.992**) but **only the approach chunk is ever executed** (the primitive takes over
at the handover), and the store has **42 place windows of 23 123** and **no recovery
windows** - two of the five experts are barely trained. **Route A was built and
measured**: `--num-skills` (env `FRUIT_TRAIN_SKILLS`) with **1** expert and the
router losses switched off (with one expert `cross_entropy(1 logit, label 3)` is an
out-of-range index - on CUDA that surfaces as `device-side assert triggered` at the
next kernel, which is how the first run died). Same store, same 12 epochs:
**3.80 M params (-17 %)**, **best val 0.0266** (vs 0.0276), latency **36.5 / 65.0 ms**
against **29.3 / 62.8**, all-window action error **0.105 vs 0.100**, and the
**approach phase - the only one deployed - 0.075 vs 0.061 rad**. **The compute does
not change and that is the finding**: `_mix_experts` skips every expert whose weight
is ~0, so the 5-expert model already runs one expert per forward - the MoE costs
**parameters, not time**. Lane endpoint 6 episodes/arm: **1 expert 11/12** against
**5 experts 12/12** (a draw at n=12), so **route A is a simplification and the
default stays the 5-expert model**; `--num-skills 1` is the documented smaller form.
**(2) The decision layer now runs with no simulator truth in it.** The goal already
had `FRUIT_GOAL_SOURCE=perception` (depth + mask -> trimmed sphere fit ->
`FruitTracker`, published every observation tick as `predict_at(horizon)`, i.e. a
predicted *current* position, coast-capped). The missing wire was the **fire
decision**: new `_fruit_for_trigger()` makes **both** `should_fire` call sites read
the tracker's estimate for position and velocity, with a per-attempt
`[fire] source=percept|truth` row so the log cannot confuse them; unset returns the
simulator's state bit for bit. Measured: **6/6 `[fire] source=percept` per cell and
5/6 placed at both seeds (10/12 vs 12/12 with truth - a draw at n=12)**, the
estimate at **-0.118..-0.122 m/s against the belt's -0.120 (1.7 %)**, diameters
28.4-61.0 mm against a 29.6-69.6 mm pool, sphere-fit rms **0.21-0.51 mm**,
`missing=0`, 0-2 rejected frames per attempt; the two losses are **`grasped=False`
at normal leads** (2.04 / 2.06 s), the grip class the record owns. **The honest
limit**: the **contact layer is still truth-fed** - `grasp_carry_place` reads
`spawner.position/velocity` (117 sites) - so the split is *decision* (goal + fire,
model-derived) versus *contact* (scripted, truth-fed); closing the second half means
giving the primitive a hand-state + force path instead of a fruit position, which is
the `SIM_LIMIT.md` work and the named next step, not a claim. Pins: `train.py`,
`scripts/50_train_policy.py`, `rl_env.py`, `scripts/selfcheck.sh`
(`P227ad trigger source`); checkpoint `checkpoints/p227_panda1e` (3.80 M, val
0.0266). References **61fb5202 / 61fb5202 / 18b101bf** untouched.

**P227ae (2026-11-24, `logs/p227/`; three default-off levers, **nothing adopted,
no reference moved**): the primitive's pre-grasp reads can be driven by the tracker,
and the ladder prices what "no simulator truth in the contact phase" costs - the
bottleneck is **measurement availability**, not the estimator.**
`FRUIT_PRIMITIVE_ESTIMATE=1` routes the **pre-grasp** reads (17 of the 22 in the
attempt's first phase) through a new `tasks._fruit_state()`; the **post-grasp** reads
(36) stay on the simulator **on purpose**, because after the grasp the payload
follows the hand and the code already dead-reckons it (`_gripper_offset`) - replacing
all 117 would be wrong, and the selfcheck leg asserts the split. **The ladder**
(6 episodes per arm): truth goal + truth primitive **12/12**; tracker goal/fire +
truth primitive **10/12**; tracker everywhere **with the camera running through the
contact phase 2/6**; tracker everywhere with **no camera in the contact phase
0/12**. **The zero has a named cause**: the primitive runs **2226-2519 ticks
(18.6-21.0 s)**, `_observe` fired only in the policy loop, so the tracker's last
update was **~10 s old** and every attempt read `close: fruit drifted **1170-1210
mm**` - 1.17 m is exactly 9.7 s of belt travel, i.e. staleness rather than error;
the coast cap was right to refuse. **Making the camera run inside the contact phase
took two wiring discoveries**, both recorded: `task.frame_callback` fires at only
**15 named legs** (a capture-style hook stayed silent - the frame count did not
move), and `_step_sim` - the primitive's own tick path - **deliberately does not
render**; the hook therefore lives in `_step_sim` (`primitive_tick_hook`, opt-in)
and `_observe(force=True)` bypasses the `_observed_step == _step` guard, because
`_step` is the **policy** tick and does not advance inside the primitive. With that
the drift rows disappear and the cell moves **0/6 -> 2/6**. **Why it is still 2/6,
as a census**: per attempt the camera gave **rejected 242-322** frames against
**accepted 45-61** (**~15-18 % usable**, `missing = 0`, so the refusals are the fit
gates - hand occlusion of the pad region, small fruit, clipping), so the tracker
coasts **0.1-0.2 s** into the contact instant = **12-24 mm** of belt travel against
a **6 mm** catch tolerance; the residual failures are all `fruit did not follow the
gripper` (the hold, not the aim). **So the decision layer runs truth-free (10/12,
the same code path the shipped lane uses with the lever unset) and the contact layer
does not**: it needs a usable in-contact measurement in 1 of 6 frames today, which is
the **wrist view the build cannot annotate** (P135: a second annotated camera takes
the first one's mask) or a **force-first close** (`logs/p42/SIM_LIMIT.md`'s lane) -
not a better estimator, which already reads **4.70 mm** when it can see the fruit.
Pins: `tasks.py` (`_fruit_state`, the `_step_sim` hook), `rl_env.py`
(`_estimate_now`, `_primitive_frame`, `_observe(force=True)`, the
`FRUIT_PRIMITIVE_ESTIMATE`/`_PERCEPT` resolvers and their guards),
`scripts/selfcheck.sh` (`P227ad primitive estimate`); references
**61fb5202 / 61fb5202 / 18b101bf** untouched. Evidence
`logs/p227/{RESULTS.md 22.20, policy_cell_*_s5/s902.log}`.

**P252 (2026-11-25, `logs/p252/`; the **deployment shape** measured, no `src/` change -
`--continuous` and `FRUIT_CONTINUOUS_TRANSIT` already existed): continuous, no per-pick
reset, **19/20 = 95 % at 0.08 m/s and ~12.0 s/cycle**.** Every number this engagement
has quoted came from the **per-episode** harness (each pick ends, the arm teleports to
the aligned start, the belt is re-primed) and **a real cell never does that**, so the
question was whether the reset is doing part of the work. It is not. Cells: `v=0.08`,
one continuous episode of 10 picks per seed, the P227z/P249 recipe verbatim:
**s901 9/10, s902 10/10, pooled 19/20 = 95.0 %**, with **0 hand-offs** (`skip`),
**`gap_ticks` median 268-269 against the 263-tick pure return transit** (5-6 ticks of
waiting is the whole inter-pick cost, i.e. **no starvation**) and cycle
**11.85-12.21 s** - the same **~12.0 s** the per-episode cells read after P249
(13.55 -> 12.13), so the 263-tick transit is **not** more expensive than the
teleport + settle it replaces. **So the deployment shape is at least as good as the
harness (95 % against 11/12 = 91.7 %, P230), the ownership rule costs nothing at the
target speed (0 fires), and the line keeps the arm fed.** **The same recipe at 0.12
reads 11/20 = 55 %** (the first pass did not pin the belt and took the shipped
0.12): **3 `fruit fell off the line`** (s901), **4 hand-offs** ("the fruit is already
inside the catch window, `t_arrive` 0.00-0.11 s < 0.50 s") and one
`fruit did not follow the gripper` - so continuity at 0.12 is **not** a wash, the two
terms that move are the **hand-off rule** (it fires when the arm is slower to return
than the fruit is to arrive) and the **lost payload**, and **no cross-speed rate is
claimed** (20 attempts each; the per-episode 0.12 cell is 10/12 - a draw at this n,
mechanism named, not measured). Pins unchanged: `tasks.py` **`b68ac8d1`**, `rl_env.py`
`TASKS_MD5` follow, references **`61fb5202` / `61fb5202` / `18b101bf`**, ckpt
`p227_panda156` - `accept.sh` stands at P250's **459/459 + `fingerprint: matches`**.
Evidence `logs/p252/`. **Addendum (§6): the ownership rule is
**topology-dependent**.** `FRUIT_SKIP_LATE=0.5` ends an attempt when the arrival
trigger fires with `t_arrive < 0.5 s` ("another arm's fruit") - and **in a
single-arm cell there is no other arm, so a hand-off is a discard**. Measured at
**0.12 continuous, everything else identical**: skip **0.5** reads **11/20 = 55 %**
(s901 4/10, s902 7/10, **4 skips**) against skip **0** **15/20 = 75 %** (8/10 + 7/10,
**0 skips**). **The mechanism is arithmetic** - a discarded pick cannot be placed, so
the rule's cost is a ceiling; **the per-seed split is a branch** (s901 +4, s902 0) and
at n=20 the pooled difference is p = 0.20, a direction. **At 0.08 the rule is inert**
(0 hand-offs in 20 picks), so the target-speed number is unaffected; the cost appears
where the arm's 263-tick return is slow against the fruit's arrival, i.e. exactly what
raising the belt does. **So the recipe is speed- and topology-dependent in one line**:
`0.5` for a multi-arm line, **`0` for a single-arm cell at 0.12 and above**; the
rule's original rationale (the doomed attempt's 1.18 rad / 44 reversals) is now
bounded by `FRUIT_POLICY_TARGET_RATE=5.45` + `FRUIT_POLICY_JOINT_CLAMP=1`, and **the
no-skip arm's motion quality is not measured here** (named next instrument). The 0.12
step therefore reads **55 % -> 75 %** by turning off a rule written for a different
topology; the **0.08 deployment number is unchanged (19/20 = 95 %)**. **The
recipe's default now follows the measurement**: `scripts/284_single_arm_policy_gate.sh`
is the **single-arm** gate and it defaulted `0.5` (the multi-arm value) - it now
defaults **0**, with the topology rule in its header, and a multi-arm caller exports
`0.5`; **confirmed at 0.08 with the new default** (seed 901, 10 continuous picks, the
knob not exported): **10/10, 0 hand-offs**, so the deployment number does not depend
on the rule at the target speed.

**P251 (2026-11-25, `logs/p251/`; two knob ladders on the hard instance, **no `src/`
change** - every knob already existed): the residual class is a **failed grasp
probe**, the IK gain is **not** its actuator, and the record's "1 m excursions" are a
**lost payload**.** **Gain ladder** (`FRUIT_IK_GAIN` 0.5/1.0/2.0, 6 one-episode runs
each on seed 901's 2.8 cm lychee): **3/6, 2/6, 2/6** - a draw, so the persistent
0.18-0.27 rad lag is not the thing to fix by gain (the controller integrates on the
**commanded** joint vector, so `lag = _q_cmd - measured` *is* the following error;
slowing the command does not help). **What separates is the `grip` block**: over 18
runs **`grip` 1.58 s on 10 of 11 passes and 4.53 s on 10 of 11 failures** (= 1.58 +
2.95, i.e. **two failed re-grasp probes**), while **`seat` is not the discriminator** -
a *passing* attempt also ran the full 200-tick catch-up (`g1.0/r5`, seat 1.67, grip
1.58, placed), the same correction P250 made from the start-offset side. **So the
chain is: the catch-up ends 39-46 mm off -> `close` 1.10 s of ramp onto a fruit that
is not between the pads -> the probe fails -> two re-grasps fail -> lost** (the one
note a failing node prints: `carry grasp_lift: stored pad centre 102 mm from the
measured pads; re-anchoring`). **A longer budget is worse and it corrects the
record**: `FRUIT_DYNAMIC_CATCH_TICKS=400` reads **1/6** with residuals **1182-1362
mm**, and the worst decomposes to `(x=-8.2 y=-391.7 z=+1274.5)` - **z = +1274 mm is
the payload 1.27 m BELOW the tip**: the fruit has left the belt and the loop keeps
chasing it, the arm moving nowhere. **That is what the record's "runaway excursions"
are**: P241's 41.6 mm (x=+34.8) is a genuine arm stall, **P242's 419 mm (z=+410.8)
and P244's 1079 mm (z=+1075.9) are lost payloads read as the loop's target** - same
shape, same magnitude, now with a mechanism; P243's 97 mm (x=-96.9) sits between and
is not settled. **So the excursions are a consequence of the catch failing, not a
cause** - which is why P243/P244/P246 could not attribute them: they were explaining
the *arm*, and the number was the *fruit*. **The honest position for the objective**:
per-size success is **80 % (0-4 cm) / 90-95 % (4-7 cm)** and the residual class's
software actuators are now **measured out** (exit, budget, gain, limits, singularity,
start offset, seat); what remains is `logs/p42/SIM_LIMIT.md`'s hardware list (a new
pad asset or a real-jaw clamp-force anchor) or a station/aim change for the smallest
class - **neither is a knob**. **No rate is claimed** for the class (11 attempts per
arm at 33-50 % cannot separate these rungs). Pins unchanged: `tasks.py`
**`b68ac8d1`**, `rl_env.py` `TASKS_MD5` follow, references **`61fb5202` / `61fb5202` /
`18b101bf`**, ckpt `p227_panda156` - so `accept.sh` stands at P250's **459/459 +
`fingerprint: matches`**. Evidence `logs/p251/`.

**P250 (2026-11-25, `logs/p250/`; one **instrument fix** - the catch-up trace's name is
per-process - plus a census and four traced runs; no behaviour change, no default
moved): the "first-attempt" class is **one instance**, and its mechanism is a
**drive-tracking stall**.** The census (312 episodes, 39 runs already on disk) first
looks like an episode-position defect - **ep 0 38/55 = 69.1 %** against **ep >= 1
95.5 %** - and it is **composition**: ep 0's median diameter is **2.80 cm** against
**6.10 cm**, because the shuffle's first draw is a small grade-A fruit. Split by
species the separation is complete: **lychee ep 0 13/30 = 43.3 % against ep >= 1
29/29 = 100 %**, while the *other* small class drawn at ep 0 (strawberry) passes
**23/23**. **Every lychee failure is the same body** (`d=2.8 cm, arm=left`, seed 901's
first draw), so the class is **"the pool's smallest instance"** - not "episode 0",
not "a small fruit", not a cold start (the first decision's `[lat] d` is 51-171 on
**every** run and does not order the outcome: 171 passes, 130 fails). **The failure
budget in one table**: 0-4 cm **72/90 = 80.0 %**, 4-5 **18/20 = 90.0 %**, 5-6
**59/63 = 93.7 %**, 6-7 **132/139 = 95.0 %**, with lychee the worst species (**42/59 =
71.2 %**) and the 2.8 cm instance carrying **17 of 31 failures**. **Four one-episode
traced runs** (2/4 = the census rate) give the mechanism and falsify three hypotheses:
**the start offset does not separate** (a pass starts at 50.8 mm, a failure at 44.9)
and **a pass also runs the full 200 ticks and places** - what separates is the
**persistent joint-space lag**, failures **0.18-0.27 rad** (one still growing) against
passes **0.11**; **no joint-limit clipping on any of the 200 samples of every run**
(`limit_margin` **+0.43..+1.42**, the failing runs having *more* margin), and
**no singularity** (`sigma_min` 0.153-0.214). So the arm stops following its own
commanded target, the catch-up's residual plateaus at **39-46 mm**, and the close then
finds the fruit outside the pads (`close: fruit drifted ... ; re-closing` ->
`fruit did not follow the gripper`). **Why it lags on this instance is not identified**
(candidates: a torque/gravity limit at that extension, or a commanded target that
outruns the drive - one lag is still growing); the instruments exist (`dq`/`lag` per
tick in this trace plus the drive readback). **This narrows P246's open item rather
than closing it**: the 1 m runaways of P241-P244 are inside this instance class (same
body, 200 ticks, residuals 41-1113 mm), not a separate object. **The instrument fix**
is the phase's only shipped change: `FRUIT_CATCH_TRACE` wrote
`catch_{seq:02d}_{arm}.json` with the sequence restarting per process in a **shared**
directory, so a second run overwrote the first - the name now carries the **process
id** (`catch_{pid}_{seq:02d}_{arm}.json`, no live consumer parses it), which is what
made the failing traces readable at all. **No-harm**: `selfcheck.sh` **PASS (0
failures, 1 skipped)**, `accept.sh` **fingerprint: matches**, its **459 `[fruit]`
lines 459/459 identical** to `logs/p227/accept_final.log` (the trace path is gated on
`FRUIT_CATCH_TRACE=1`, which the scripted line never sets). **Named next, priced, not
built**: a **feed-forward/integral term on the arm's own joint error** (P246's open
item 2) - now with a magnitude (**0.18-0.27 rad** against 0.11) and an endpoint (the
2.8 cm class **43 % -> 80 %** would put the cell at **97 %**) - and it moves every leg
on every cell, so it owes its own pre-registration, the acceptance, **both** references
and a store re-baseline (P248's price for a default flip). Pins: `tasks.py`
**`b68ac8d1`** (the trace name only), `rl_env.py` `TASKS_MD5` follow; references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt `p227_panda156`. Evidence
`logs/p250/`.

**P249 (2026-11-25, `logs/p249/`; **the axis-aware exit ships as the direct lane's
default** - scoped, and the scripted/two-line paths are byte-identical): P248's
powered cell passed (40/40 against 38/40, catch-up 200 -> 21 ticks, cycle -1.42 s),
so `FRUIT_CATCH_TOL_AXIS` now resolves **on for `presentation == "direct"`** with the
env unset, `scope-off` everywhere else, an explicit `0`/`1` winning and anything
else raising. **The scoped form is the point**: the knob is read at task
construction, so a global default would move the scripted acceptance, the two-line
session, the collector and the canary and would owe the two-line gate + **both**
references + every store; the `_dynamic_profile` scope (P87/P88/P89's pattern) owes
none of it. **A defect was found and fixed before the flip worked**: the first
attempt applied the flag **before `self.task` existed** (the apply sat beside
`self.spawner.belt`, the task is constructed ~500 lines later), so the `getattr`
guard swallowed it and the lever was **silently inert** - the direct cell read
`catch ticks 200 200 200 200 200`, `seat=1.67s` five times and **zero** `[rl] catch
tol axis:` rows. That is **P97's defect class** (a predicate read before its object
exists) in a new place; the apply moved to directly after `PickAndPlaceTask(...)`
and the selfcheck leg now pins the **order** (`index('self.task =
PickAndPlaceTask(') < index('self.task.catch_tol_axis = ...')`), so the guard cannot
swallow it again. **The direct cell after the fix**: row `on (default)
presentation=direct`, catch ticks **200/21/80/21/21**, `seat`
**1.67/0.17/0.66/0.17/0.17 s**, cycle **16.68/12.31/12.37/11.93/12.03 s**, placed
**4/5** with the one loss **episode 0** (the 44.4 mm first-attempt row - the class
P246 bounded, x-dominated, no new class). **No-harm, measured**: `scripts/accept.sh`
is **7/10 = 70 %, 9.5 s/attempt, `fingerprint: matches configs/motion_reference.json`**
and its **459 `[fruit]` lines are 459/459 identical** to `logs/p227/accept_final.log`,
with **0** `[rl] catch tol axis:` rows in the scripted log (the row is gated on
`scope-off`) - and since the shipped acceptance **is** the two-line cell, that run
covers the two-line gate too. **So the flip is resolution-only on the direct lane,
no reference was re-recorded and none is owed.** Delivered: the direct lane's cycle
**~13.55 -> ~12.13 s (-10.5 %)** at no measured quality cost. Pins: `tasks.py`
**`0f580754`** (the exit's flag is caller-owned, the env read stays the base),
`rl_env.py` (the resolver table, the apply after construction, the gated row),
`scripts/selfcheck.sh` (the `P249 catch tol scope` leg + the ordering pin);
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt `p227_panda156`.
Evidence `logs/p249/`.

**P248 (2026-11-25, `logs/p248/`; measurement only, no `src/`/`configs/` change; the
**powered cell** the axis exit owed): **P1/P2/P3 all PASS - the axis-aware exit is
a candidate default on 40 attempts per arm.** 2 arms x 2 seeds x **20 episodes =
40/arm**, identical instrumentation both arms, `PREREG.md` pinned first. **Placed:
C shipped 38/40 = 95.0 %, T axis exit 40/40 = 100 %** - the bar was `T >= C - 2`
and the observed +2 is **a draw at n=40 (Fisher p = 0.49)**, so the claim is **"no
quality cost at 40 attempts"**, not "better". **Mechanism**: catch-up ticks median
**200 -> 21** (bar <= 45; **35 of 40** control catches ran the full budget, **0 of
40** treatment), `seat` median **1.67 -> 0.17 s** (bar <= 0.40, p90 0.35). **Cycle**:
`[cycle] total` **13.55 -> 12.13 s = -1.42 s** (bar >= 0.8) and the independent
episode-ticks reading **-1.38 s/attempt** (17.11 -> 15.73), agreeing to 0.04 s.
**P4 (reported, not gated)**: the **control** arm carries the runaway (**1113.7
mm**), the treatment **none** - one more confirmation of P246: **the excursion is
not the lever's**. **The flip is NOT taken here**: the knob is read at task
construction, so a default moves **every** path (scripted acceptance, two-line
session, collector) and the record's price is the **two-line gate**, **both motion
references re-recorded** from same-batch runs and **every store re-baselined** -
a separate priced step and the **owner's decision**. **The cheaper scoped form is
named, not built**: gate it to `two_line`/`direct` with the `_dynamic_profile`
pattern P87/P88/P89 used, which keeps the scripted acceptance untouched. Pins
unchanged: `tasks.py` **`9ce34845`**, `rl_env.py` untouched; references
**`61fb5202` / `61fb5202` / `18b101bf`**; ckpt `p227_panda156`. Evidence
`logs/p248/`.

**P247 (2026-11-25, `logs/p247/`; measurement only, no `src/`/`configs/` change;
the **handover page** `docs/SINGLE_ARM_SPEC.md` lands with it): the axis-aware exit
holds in a fresh cell - **15/16**, and **26/28 pooled** with P243.** `v=0.08`,
`FRUIT_CATCH_TOL_AXIS=1`, seeds 901/902 x **8**: seed 901 **7/8** (catch ticks
**200**, 21, 33, 21, 21, 21, 21, 21), seed 902 **8/8** (24, 21, 39, 24, 41, 21, 21,
21), residuals **8.6-10.5 mm** everywhere but the single outlier (**36.9 mm**). So
**the 200-tick tax is gone on 27 of 28** - not a branch, not a seed - the **placed
count is at parity** with the shipped 11/12 (26/28 = **92.9 %**), and the saving is
the measured **-1.44 s of ~13.3 s (-11 %)**. **The one 200-tick row is seed 901's
episode 0 again** - the same position as every excursion in P241-P246 and the one
attempt of the 16 that did not place - i.e. exactly the bound P246 recorded (at most
one per run, first episode, 0-1 placement); it **stays open, no rate quoted**.
**Promotion to default still owes P93's powered cell (~40/arm), the two-line gate,
both references and a store re-baseline** - this phase adds the parity-plus-saving
the decision starts from. **`docs/SINGLE_ARM_SPEC.md`** is the one-page handover:
what the cell is, the delivered spec by speed (0.06/0.08/0.12/0.18 = 11/10/11/11 of
12, 0.20 = 58 %, >=0.22 does not engage), the cycle decomposition, the 1.44 s
mechanism and its status, **the eight closed levers with one line each**, the four
open items (first-attempt excursion, vertical integral/gravity feed-forward, faster
belts need hardware, perception contact layer), the reproduce commands and the four
read rules (a 6-episode cell is a draw; a diag cell is not a rate; "does not
engage" is a boundary not 0 %; evaluate latency at `FRUIT_EVAL_LATENCY=auto`).
Pins unchanged: `tasks.py` **`9ce34845`**, `rl_env.py` untouched; references
**`61fb5202` / `61fb5202` / `18b101bf`**; ckpt `p227_panda156`. Evidence
`logs/p247/`, `docs/SINGLE_ARM_SPEC.md`.

**P246 (2026-11-25, `logs/p246/`; a **reading of existing logs**, no run, no `src/`
change): the first-attempt excursion is **not initialisation, not the diagnostic,
not attributable** - and is closed as open with its bounds measured.** P245's
"initialisation" hypothesis (first fruit far upstream + arm parked, catch-up budget
short) is **refuted on the disk**: every run's `episode 0` row prints its fruit and
arrival, and the **same `lychee grade=A d=2.8cm arm=left y=+0.596`** appears in a
**clean** cell (P236) and in an **excursion** cell (P245), while seed 902's first
fruit is **further** upstream (`strawberry y=+0.610`) and clean. **The other named
mechanisms are refuted too**: not the catch-row diagnostic (P239/P240 ran it, 18
attempts clean; P245 ran only it and is not), not the cycle report (P241-P244 had it
and all show one), not the per-tick component subtraction (P245 removed it and the
excursion stays), not the command offset (it appears on the shipped command). **No
measured variable separates the clean cells from the excursion cells**, so the class
is **real, reproducible in some runs, and unattributed**: at most **one episode per
run** (the first), **0-1 placement**, never in the five later episodes. **Recorded
as open with its bounds, not narrated as a lever** - the record's rule is that an
unexplained class is not a lever, and **no rate is quoted** for it (the earlier
"7 %" was withdrawn in P244 and this phase removes the last mechanism that could
have supported a variant). **Unchanged for the objective**: 0.08 **11/12 = 91.7 %**,
cycle ~13.3 s; the catch-up's exit is a **6.6 mm vertical steady-state error**
(P241); the shipped loop exits on its **200-tick budget** (P239); the **axis-aware
exit recovers 1.44 s on 11 of 12 with the command untouched** (P243) → cycle
**~11.9 s (-11 %)**. Pins unchanged: `tasks.py` **`9ce34845`**, `rl_env.py`
untouched; references **`61fb5202` / `61fb5202` / `18b101bf`**; ckpt
`p227_panda156`. Evidence `logs/p246/`.

**P245 (2026-11-25, `logs/p245/`; one **instrument fix**, no behaviour change):
the per-tick subtraction is **exonerated**, the 1.44 s recovery **stands**, and the
last open object on this axis is **seed 901's first catch**.**
`FRUIT_TRACK_DIAG=1` with the residual's components now computed **once at the
loop's exit** (P244 suspected the per-tick `tip - desired_tip` of perturbing the
first catch). 12 attempts, both seeds: **the excursion survives** - `54.5 mm
(x=+39.2 y=-36.0 z=+12.2)`, 200 ticks - on **seed 901's episode 0**, with 11/12
placed and the other eleven catches at the shipped floor (6.5-6.7 mm / 200 ticks,
two at 27-28). **So the instrument is not the cause**, and P244's suspicion is
refuted by its own control. **The association that is left is perfect and
unexplained**: every excursion across P241-P245 is **seed 901's first catch**
(41.6 / 419.1 / 97.2 / 1079.4 / 54.5 mm), **none** at seed 902's first (5.8-7.1),
and the P236-P240 cells - which ran seed 901 **without** `FRUIT_TRACK_DIAG` - show
**0/6** there. **It has no mechanism**: on the direct lane `_track_diag` gates only
(i) `_track_row`, which is called from **`note_result`** (`tasks.py:4071`) and the
direct path never runs it, and (ii) the `[catch]` row, which prints **after** the
loop it would have to perturb - a print issued after the fact cannot move the ticks
before it. Five of five at p = 0.5 is 1 in 32: unlikely, and still not a mechanism.
**What the arc establishes with the excursion out of the way**: the catch-up's exit
is a **6.6 mm vertical steady-state error** (P241), the shipped loop therefore exits
on its **200-tick budget** (P239), and the **axis-aware exit recovers 1.44 s on 11 of
12 with the command untouched** (P243) - the excursion is neither the component
field (this phase) nor the command offset (P243/P245), so the recovery stands. **The
only open object on this axis is seed 901's first catch**, which is an
**initialisation** question, not a lever: once per run, first episode, one seed,
0-1 placement. Its instruments already exist (`FRUIT_DIRECT_START_ALIGN` / the
start-pose family, the reset's teleport-plus-settle, `FRUIT_TRACK_MEAS_WAIT`); the
cheapest discriminator is a **1-episode cell per seed** reading the cycle's
`descent` for episode 0. **Not run** - recorded rather than opening a sixth sub-arc
on one seed's first attempt. Selfcheck **PASS (0 failures, 1 skipped)**;
`accept.sh` **fingerprint: matches**, its **459 `[fruit]` lines 459/459 identical**
to `logs/p227/accept_final.log`. Pins: `tasks.py` **`9ce34845`** (+ the `TASKS_MD5`
follow); references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt
`p227_panda156`. Evidence `logs/p245/`.

**P244 (2026-11-25, `logs/p244/`; measurement only, no `src/` change): the
"7 % x excursion" is **instrument-suspect and WITHDRAWN** - P243's class claim does
not survive the audit.** The four gross catch-up excursions are **41.6 / 97.2 /
419.1 / 1079.4 mm**, they are **not one direction** (`x` once, `z` three times,
`z = +1076 mm` in the worst), and **all four are the first catch of their run**.
**The control exists and it is clean**: P236-P240 ran the same cell **30 times with
the same instrumentation minus the component field and produced zero excursions**,
and the field added in P241 is subtracted **unconditionally on every tick** - which
is exactly the per-tick work AGENTS section 2 warns about. So `shipped 0/30` against
`field-on 4/42` is consistent with a cell property **and** with the instrument
perturbing the first catch, and **the data cannot separate them** because every
cell that shows an excursion also carries the field. **Withdrawn**: "the class is
`x`, 3/42 = 7 %". **Two instrument defects recorded, not fixed (deliberately - the
next cell's first step)**: (a) the catch trace is `catch_{seq}_{arm}.json` with a
per-task sequence and a shared directory, so a second process **overwrites** the
first run's files (7 survived 12 catches, and the outlier's trace is gone); (b) the
component subtraction is **not gated**, so "the row is a diagnostic" is not true of
its cost. **What stands**: the catch-up's exit is a **6.6 mm vertical steady-state
error** (P241), the shipped loop exits on its **200-tick budget** (P239), and the
**axis-aware exit recovers 1.44 s on 11 of 12 with the command untouched** (P243) -
that holds because the 50 non-excursion attempts all show the same 21-42 ticks, and
it is independent of the excursions. **The next cell**: `FRUIT_CATCH_COMP_DIAG`
(default 0) gating the subtraction plus a **per-run** trace directory, then one cell
answering shipped-vs-field-on; **until it runs, no rate is quoted for the
excursions**. Pins unchanged: `tasks.py` **`58460874`**, `rl_env.py` untouched;
references **`61fb5202` / `61fb5202` / `18b101bf`**; ckpt `p227_panda156`. Evidence
`logs/p244/`.

**P243 (2026-11-25, `logs/p243/`; one **default-off knob**, nothing adopted, no
reference moved): the axis-aware exit recovers the 1.44 s with **no quality price** -
and the runaways are an **x** excursion, so P242's association was wrong.**
`FRUIT_CATCH_TOL_AXIS=1` replaces the catch-up's 3-D-norm exit with two per-axis
conditions - **`|y| <= 6 mm`** (the belt direction, unchanged) and
**`|z| <= 10 mm`** (the gravity droop, contained) - and **moves no command**. 12
attempts, both seeds: **`catch ticks` 200 -> 21-42 on 11 of 12 (median 23)**,
**`seat` 1.67 -> 0.17-0.34 s**, **11/12 placed**, i.e. **-1.44 s of ~13.3 s (-11 %)**
at both seeds. **P2 falsified, usefully**: the registration predicted zero runaways
on the argument that P242's came from the 6.6 mm offset; **there is one with the
shipped command** - `ticks=69 residual=97.2mm (x=-96.9 y=+4.6 z=-7.0)`, i.e. a
**97 mm across-belt excursion** with ordinary y and z. So the runaway class is
**not** the offset's (P242's association was spurious: the components row did not
exist before P241, so its two instances could not be inspected), it is **`x`**, and
its rate across the three cells that print it is **~3/42 = 7 %**. **P1/P3/P4 PASS.**
**The condition the win depends on, stated**: it works because at 0.08 the belt
direction is already **5.2-5.8 mm inside 6 mm** - the loop was only ever blocked by
`z` - so it is a **speed-dependent** recovery and will revert to the budget when the
belt speeds up. **Ranking**: the axis exit **dominates** P242's command offset (same
-1.44 s, command untouched, and the offset has no advantage now that the runaway is
not its); it stays **default off** until a powered cell. **Its "x excursion, 7 %"
reading is WITHDRAWN by P244** (the control is clean at 0/30 and the excursions
appear only in cells carrying the unconditionally-computed component field). Selfcheck
**PASS**; `accept.sh` **fingerprint: matches**, its **459 `[fruit]` lines 459/459
identical** to `logs/p227/accept_final.log`. Pins: `tasks.py` **`58460874`** (+ the
`TASKS_MD5` follow); references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
ckpt `p227_panda156`. Evidence `logs/p243/`.

**P241/P242 (2026-11-25, `logs/p241/`, `logs/p242/`; one **default-off knob** plus
the field that found it; **nothing adopted**, no reference moved): the 1.44 s
catch-up tax is a **6.6 mm steady-state VERTICAL error**, and a constant command
offset recovers it - at a **~11 % runaway price**. P241 first added the residual's
**components** to the `[catch]` row: at 0.08 the shipped exit is
`(x=-0.1 y=+0.5 z=-6.6) mm`, i.e. **the belt direction is already tracked** and the
hand sits **6.6 mm below** the commanded standoff, 0.6 mm outside the 6 mm
tolerance - which is why the loop always exits on its 200-tick budget (P239). That
retires P240's question (the y-lead could not move it because it was never y).
**`FRUIT_CATCH_Z_FF=<mm>`** then raises the catch-up's **command** (the residual's
reference stays put). Measured: `z` moves to **-2.1..-2.8**, the norm to
**5.4-5.9 mm**, and `catch ticks` collapses **200 -> 22** (10 of 12 in P242, 22-29
in P241) so **`seat` 1.67 -> 0.17-0.23 s** - **-1.44 s of a 13.3 s cycle (-11 %)**,
reproducible at both seeds. **The price is a runaway class**: **2 of 18 attempts**
end with the pad point **100-420 mm above** its command and burn the full budget;
the shipped cells show **0/30** in P236-P240, so the class is at least strongly
associated with the offset (two readings - the offset steers the command into a
vertical region where this arm's solve diverges, or a pre-existing rare flail is no
longer masked by a 200-tick crawl - and **n = 18 cannot separate them**). The
arithmetic: **saved 1.44 x 0.89 = 1.28 s**, **paid 1.67 x 0.11 = 0.18 s**, **net
~+1.1 s/attempt**, with **1 lost placement in 18** - a time win with a quality cost,
so **not a default** (a lever that can lose a placement needs P93's powered cell,
then the two-line gate, both references and a store re-baseline). **The principled
version is named, not built**: the 6.6 mm is a *steady-state* error, so the fix is a
**vertical integral term or a gravity feed-forward on the axis**, not a constant
offset on the command (which is what pushes into the runaway region). The offset
stays a default-off measurement lever. Selfcheck **PASS**; `accept.sh`
**fingerprint: matches**, its **459 `[fruit]` lines 459/459 identical** to
`logs/p227/accept_final.log`. Pins: `tasks.py` **`e3795cf4`** (+ the `TASKS_MD5`
follow); references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt
`p227_panda156`. Evidence `logs/p241/`, `logs/p242/`.

**P240 (2026-11-24, `logs/p240/`; measurement only, no `src/` change): the
catch-up's residual is **not** a following lag - the belt-direction lead does not
move it, and a larger lead runs away.** `FRUIT_DIRECT_CATCH_LEAD` 0.25 -> **0.33**
(+82 ms, exactly the measured 6.6 mm / 0.08 m/s lag), seed 901 x 3, both arms
instrumented: **the residual is unchanged (6.6 / 6.7 mm)**, `catch ticks` stays
**200**, `seat` stays **1.67 s** - and **one attempt runs away to 102.3 mm** and
costs a placement (**2/3 against 3/3**). So **P1 is falsified**: a pure time lag
would shrink when the lead is extended; this one is invariant, i.e. its dominant
component is in a direction the lead cannot touch. **The hypothesis this leaves**
(not tested here): the stop point is `fruit + [0, 0, standoff]` (P227o's fix, 42 mm
on this hand), so a **z** error explains everything measured - the residual is a
**floor** at 6.6-6.7 mm that no lead moves, 0.6 mm above a round 6 mm tolerance,
and (P239) `seat` is bimodal only because two attempts happened to cross 5.7-5.8.
**The instrument is one field**: the residual's **components** (`x= y= z=`) in the
`[catch]` row - one subtraction on arrays the row already has - and it decides
between "the lead is still wrong" (y) and "the hand cannot reach the commanded
standoff" (z). **Not added this phase**, deliberately: the phase's lesson is that
a mechanism claim needs its discriminating instrument first. **Also closed**: the
docstring sentence "a 0.18 s lead left the tip riding ~6-7 mm behind the fruit" is
a **description** of the floor, not a cure - the 6-7 mm is reproduced at **two**
leads; and `FRUIT_DIRECT_CATCH_MAX = 0.035 m` is load-bearing (it is what the
overshoot runs into, which is why the failure is a runaway and not a bias). Pins
unchanged: `tasks.py` **`e72b2c7c`**, `rl_env.py` untouched; references
**`61fb5202` / `61fb5202` / `18b101bf`**; ckpt `p227_panda156`. Evidence
`logs/p240/`.

**P239 (2026-11-24, `logs/p239/`; measurement only, no `src/` change): the catch-up
exits on its **budget**, not on convergence - the exit tolerance sits below the
controller's own steady-state lag.** `FRUIT_CYCLE_REPORT=1` + `FRUIT_TRACK_DIAG=1`
on 6 attempts at 0.08 pair the `[catch] ticks= residual=` row with the `seat=`
block: **27 ticks -> 5.7 mm -> 0.22 s**, **98 -> 5.8 -> 0.81**, and **four of six
at 200 ticks -> 6.6/6.7 mm -> 1.67 s**. So P238's identification is **confirmed**
(`seat` is the pursuit to the hundredth, `200 x 8.33 ms = 1.667`), and the
mechanism is sharper than "the approach is off": **`FRUIT_DYNAMIC_CATCH_TOL` is
6 mm while the pursuit's steady-state following error at 0.08 m/s is 6.6-6.7 mm
(82 ms of lag)**, so the loop's exit condition is essentially **unsatisfiable at
this speed** and it stops on `FRUIT_DYNAMIC_CATCH_TICKS` (200) - **0.6 mm short of
the line it is waiting to cross**. The two fast attempts are the ones whose error
happened to cross 5.7-5.8 mm. **The 1.44 s is therefore a fixed tax for a 0.6 mm
miss**, and it also re-reads P48: the "8/8 no-grasp above 6 mm" boundary was
measured while the loop mostly ran at 6.6-6.7 mm anyway, i.e. **the tolerance and
the achievable error are the same number**, which is why the block's cost is
bimodal rather than graded. **Levers named, not built**: **(a) reduce the
following error** (a lead/feed-forward on the pursuit - the principled one, since
it makes the exit satisfiable; P233 showed the same class of error on the trigger's
speed source), **(b) raise the tolerance to 8 mm** (-1.4 s, but P48 measured 6 mm
as the class boundary, so it is a catch-quality trade needing a powered cell), and
**(c) the budget** (truncates a pursuit that is 0.6 mm from its goal). Pins
unchanged: `tasks.py` **`e72b2c7c`**, `rl_env.py` untouched by this phase;
references **`61fb5202` / `61fb5202` / `18b101bf`**; ckpt `p227_panda156`.
Evidence `logs/p239/`.

**P237 (2026-11-24, `logs/p237/`; two **default-off sub-marks**, no behaviour change,
nothing adopted): the `close` block is `seat + ramp`, and **`seat` is a cross-layer
attitude cost the primitive pays for the approach.** Two `_cycle_mark`s inside the
close (`seat` before the `_close_attempt` loop, one `attempt` per try; no-ops
unless `FRUIT_CYCLE_REPORT=1`) decompose P236's 2.77 s over 8 attempts at 0.08:
**`ramp` is a constant 1.10 s** (6/6 placed attempts, four fruits, both seeds - the
profile, not the fruit) and **`seat` is bimodal: 1.67 s on 4 of 6, 0.23 / 0.67 on
the other two**. `1.67 s = 200 ticks`, **first attributed to the attitude servo and then
FALSIFIED (P238)**: a `[seat] init` row reads the wrist at the servo's entry at
**0.0-0.6 deg** against the 8.1 deg tolerance on six attempts, so the servo exits
on its first check; the 200-tick loop in that segment is
**`FRUIT_DYNAMIC_CATCH_TICKS` (default 200)** - the primitive's **pursuit**. So
`seat` is bimodal because **the catch-up converges in ~26 ticks when the fruit is
where the aim expected it, and runs its full budget when it is not**, and the lever
is **"arrive closer", not "arrive more vertical"**. **That is 4T's interface cost made visible**: the approach owns
where the pads arrive, the primitive owns the pursuit, and **neither layer is
charged for the 1.44 s the primitive spends closing the aim residual the approach
left** (the attitude, measured, is already square). The cycle is now decomposed: **place 3.48, release
2.16-2.27 (incl. the 0.5 s settle), grip 1.58, seat 0.23-or-1.67, descent 1.5-4.9
(incl. the wait), lift ~1.2, ramp 1.10, return 0.50** - **~10 s fixed of ~13.5
(75 %)**, and `seat` is the only *bimodal* block, i.e. the only one where the same
cell is already **1.44 s faster on some attempts**. **The lever it names, not
built**: make the approach arrive with the tool axis vertical - either a
training/conditioning change on the last chunk or an explicit wrist command at the
handover - worth **-1.44 s/attempt (~11 %)** and success-neutral if the attitude is
right; **the cap alone (`FRUIT_AXIS_SERVO` 180 -> 60) is NOT the lever** (it would
truncate the servo while the attitude is still wrong, and P64/P65 measured the
attitude as load-bearing). Selfcheck **PASS**; `accept.sh` **fingerprint: matches**,
its **459 `[fruit]` lines 459/459 identical** to `logs/p227/accept_final.log`.
Pins: `tasks.py` **`74300602`** (+ `TASKS_MD5` follow); references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt `p227_panda156`.
Evidence `logs/p237/`.

**P236 (2026-11-24, `logs/p236/`; one **default-off instrument path**, no behaviour
change, nothing adopted, no reference moved): the direct single-arm lane gets the
block report P235 found missing - and it prices a block the record never saw.**
`FRUIT_CYCLE_REPORT=1` printed **nothing** on the direct lane because
`_cycle_begin`/`_cycle_mark` live in `_grasp_carry_place_impl` while
`_cycle_report` is only called by **`note_result`**, which the scripted driver runs
and the direct entry never does - the marks landed in `None`. Fixed with an
**ownership test** in `grasp_carry_place` (`_cycle_marks is not None and not
_cycle_marks`): it begins and reports the cycle when the env owns the attempt,
`note_result` keeps its own report, and the scripted path is untouched (off is a
no-op). **Measured at 0.08, 6 placed attempts, both seeds**:
`place 3.47-3.51 s` (constant), **`close 2.77 s` (constant, 5 of 6)**,
`release 2.14-2.41`, `grip 1.57-1.59`, `lift 1.18-1.89`, `descent 0.98-2.12`,
`return 0.50`, **total 11.7-14.1 s**. **The finding**: P91's `[cycle]` audit - which
priced every "speedable" block - read the **two-line** cell, where `close` is
**1.36 s**; on the direct single-arm lane it is **2.77 s, twice that**, and it is
the *fixed* part of the cycle (same on a lychee and a pear, both seeds; it spans
the coherent track + axis servo + the `_close_attempt` retries). So the lane's
**grasp establishment is ~4.3 s (`close` + `grip`) = 30 % of the attempt** and no
record entry had ever priced it. **Read rules carried**: the marks bound *phases*,
not profile cells - this `release=` includes P142's 0.5 s post-release settle and
the retreat, so it must **not** be quoted against P86's `release=` cell (2.35 ->
1.63) or read as "the trim is off"; and `descent` includes the arrival wait (P91:
`lead/speed - margin`, not shorten-able by a faster leg). **The next lever is now
measurable**: the two constants are `place 3.48` + `close 2.77` = 6.2 s of the
~13.3 s cycle. Selfcheck **PASS** with the new leg `P236 direct cycle report`;
`accept.sh` **7/10, 9.5 s/attempt, `fingerprint: matches`, 190 PASS**, its **459
`[fruit]` lines 459/459 identical** to `logs/p227/accept_final.log`. Pins:
`tasks.py` **`a8ca62cf`** (+ `TASKS_MD5` follow), `scripts/selfcheck.sh`;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt
`p227_panda156`. Evidence `logs/p236/`.

**P235 (2026-11-24, `logs/p235/`; measurement only - **no `src/`/`configs/` change**):
the throughput cell is **not readable on this lane** - the leg the place knob moves
is not the cycle's block.** `FRUIT_SPEED_PLACE=0.52` at 0.08 (the P227r S1 cell
that was negative at 0.12), seeds 901/902 x 6: **12/12 vs 11/12** (a tie in the
draw) and the episode **grew +46 ticks (+0.38 s)** - the P86/P88/P89 shape. **The
registered falsifier fired**: `FRUIT_CYCLE_REPORT=1` prints **no `[cycle]` rows at
all** on the direct single-arm lane (the block report is the scripted two-line's),
and `FRUIT_MOTION_REPORT=1` shows why - `carry place0` is **6 cm / 84 ticks** in
the control and **83** in the treatment, i.e. **acceleration-bound and unchanged**
(P89's ~0.225 m regime switch; 6 cm is far below it). So the "place block ~4.0 s"
that P227r shortened at 0.12 is the **transit** (the joint blend to
`bin{i}_above` + the Cartesian run), which no per-leg 6 cm row can show - and
**this lane has no block-level instrument**, so a place-speed cell cannot be read
here. **The +46 ticks is branch noise on a cell whose block did not move**, quoted
only to show what a re-drawn acquisition does at n=12. **What this leaves for
分拣速度**: the lever's target is the transit, and any further cell needs a
direct-lane block report first; the two readable profile cells are both negative
(P88 place at 0.12, P89 lift), and the only measured shortening in the record is
P227r's **release trim** (a dwell, shipped). No `src/`/`configs/` change;
`tasks.py` **`c16c8291`**, references **`61fb5202` / `61fb5202` / `18b101bf`**
untouched; ckpt `p227_panda156`. Evidence `logs/p235/`.

**P234 (2026-11-24, `logs/p234/`; measurement only - **no `src/`/`configs/` change**):
the **spatial** disturbance rung - a **0.22 m** lateral band costs nothing at 0.08,
so the lateral axis is **not** the binding disturbance.** `FRUIT_SUPPLY_X_MIN=0.17
FRUIT_SUPPLY_X_MAX=0.39` (shipped `0.20-0.36`), `v=0.08`, seeds 901/902 x 6 reads
**12/12 = 100 %** (the shipped band's own cell is 11/12), and the `[supply] scatter`
row confirms the planned band. **The registered prediction (falls below 9/12) is
falsified - P4 applies** - with the caveat the phase states: **12 attempts cannot
price a rare event** (P38 put the below-floor class at ~0.06 %/episode), so the
sentence is *no cost observed at 12 attempts*, not *the tails are free*. **The
diag cell is a different branch and says so**: `FRUIT_FIRE_DIAG=1` on the same
band and seed reads **4/6** - the P230/P232 lesson at the level of a *count*, so a
diag cell's rate is never the cell's rate. **A number that does not match the
record**: the delivered `fruit_x` reads **0.169** - below the shipped floor (0.20)
**and** below the arm's documented admission floor (P38: right 0.1730, left 0.1800)
- and **it fired and was attempted**, so either the floor's single-`station_x`
derivation does not describe this cell's gate or the `[fire]` row's `fruit_x` is
not the gate's input; **the floor must not be quoted as a hard bound** until a
gate-tick row prints `dx`, `lateral` and the x each side used. **The ladder now
reads**: temporal 0.08 free to **±75 %**, temporal 0.18 costs at **±17 %** (P233),
spatial 0.08 free at **0.22 m** - **the bound is speed**. Pins unchanged:
`tasks.py` **`c16c8291`**, `rl_env.py` untouched by this phase, references
**`61fb5202` / `61fb5202` / `18b101bf`**; ckpt `p227_panda156`. Evidence
`logs/p234/`.

**P233 (2026-11-24, `logs/p233/`; one **default-off correctness fix**, **not
adopted**, no reference moved): the trigger now sees the belt it is on, and the
disturbance loss is the **speed ceiling**, not the schedule.**
`FRUIT_TRIGGER_SURFACE_SPEED=1` routes `Conveyor.surface_speed` (P141) to both
`should_fire` sites instead of `encoder_speed` - the setpoint echo P232 caught
printing `speed=0.080` under a wave. Cell: `v=0.18`, wave `0.03` (surface
**0.15-0.21**), seed 901 x 6, A shipped vs B fixed. **P1 PASSES decisively**: B's
fire row prints **five distinct speeds** (0.151/0.162/0.164/0.171/0.210) where A
prints one value six times. **P2 needed a correction**: the registration predicted
the signature on `dy`, which scatters in **both** arms (sd 3.56 vs 3.91 cm) because
`lead` carries the jaw-station distance (P228's nuisance variable again); the
branch-free field is **`t_arrive` itself**, and it tightens **sd 0.20 -> 0.15 s**
(a 25 % reduction, and the minimum rises 0.94 -> 1.12 s) - at 0.18 m/s, 0.20 s of
sd is **36 mm** of mis-scheduled travel. **The count is a tie** (4/6 both, both
failures the grip class), so P3 is not established and P4 does not fire. **The
phase's real finding is the ladder's shape**: at `v=0.18` a **±17 %** wave costs a
quarter of the placements - 0.18 constant **11/12** (P229) against **8/12 = 67 %**
pooled here - while at 0.08 a **±75 %** wave was free (P232). The fix does **not**
recover them because the failure is the **crest**: 0.21 m/s is past the usable
ceiling (~0.18-0.20), and no scheduling arithmetic changes how fast a fruit moves.
**So the disturbance tolerance is bounded by the speed ceiling, not the trigger**,
and a deployment's spec is the line's **peak** surface speed, not its mean. The
fix stays default off (a correctness fix with a count-null needs the two-line gate,
both references and a store re-baseline - P87's price for a smaller effect). Pins:
`rl_env.py` (the knob + the field selection at both sites), `scripts/selfcheck.sh`
(leg `P233 trigger speed`); `tasks.py` **`c16c8291`** unchanged; references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt `p227_panda156`. Evidence
`logs/p233/`.
**Scope correction carried in the same phase**: the "peak-speed limiter" named as
the next rung is **not available to this cell** - the owner's standing constraint
(P119: *the dynamic scattered pipeline must be preserved - no diverter, stop gate,
guide/limit or pause*) forbids intervening on the line. It is a **line-design note
for a buyer**, not a lever this record may build; the arm side is measured closed
(P229/P230/P231).

**P232 (2026-11-24, `logs/p232/`; one **instrument fix** in `rl_env.advance`,
nothing adopted, no reference moved): the objective's first disturbance rung -
**a real line's speed varies - costs zero placements, and the trigger is blind to
it.** `FRUIT_BELT_SPEED=0.08` with `FRUIT_BELT_WAVE_AMP=0.04`,
`FRUIT_BELT_WAVE_HZ=0.5` (surface speed sweeps **0.04-0.12 m/s**, a **±50 %**
disturbance) reads **11/12 = 91.7 %** - the same count as the constant-speed
baseline (P230's 11/12) and as the same wave applied to the primitive only - at
both seeds (5/6, 6/6); the fire's `dy` moves 0.136 -> 0.154 m and `t_arrive`
1.71 -> 1.93 s. **Two instrument defects, both found only by running it**:
(a) P135 ticked the wave inside the task's `_step_sim`, so an armed wave disturbed
the **contact phase and not the approach** - exactly the phase a varying speed
matters in; `rl_env.advance` now ticks it too, gated on the task's own flag (False
unless the amp is set, so every shipped path is unchanged, and the acceptance is
**459/459**); (b) that fix then killed two runs at startup (`0/0`, no episode
rows) because `advance(30)` also runs in `__init__`'s scene prime **before
`self.task` exists** - guarded with `getattr(self, "task", None)`. With P230's
two (`self._say`, `self._step`) the pattern is explicit: **an instrument on this
tree fails at construction or edge sites, and only a run - ideally with a cell
known to work - finds it**; both P232 runs that died would have read as "the cell
cannot do 0.08 under a wave". **The finding**: every fire row in **all three**
cells prints `speed=0.080m/s/encoder` - P141's finding again, `encoder_speed` is a
**setpoint echo** (computed only while the cleats exist; they are off), while the
belt that moves is `surface_speed`. So on a varying line the trigger computes
`t_arrive = dy / 0.080` against a fruit moving **0.04-0.12** - an error of up to
**2x** in the one number the handover is scheduled on - and **the cell still reads
91.7 %** because the layer below compensates: the primitive's hover/descent use
`_belt_speed_estimate()` (the surface speed) and the hover wait absorbs the
mismatch. That is the 4T layering paying off **and** a named latent defect: the
compensation is a **wait**, and a wait spends the lead. **Verdicts**: P1 partial
(the wave is armed and reaches both paths, but the *log* cannot show it in the
trigger row - the missing instrument is a **surface-speed print at the fire**),
**P2 PASSES** (11/12 >= 9/12), P3 does not apply (the one W2 failure is
`fruit left the pick station during the close`, P41's station class), **P4 does
not fire**. **Next rung, named not run**: a wider or faster wave, where the
hover's absorption runs out. Pins: `rl_env.py` (the wave tick in `advance`,
guarded), `scripts/selfcheck.sh` (leg `P232 belt wave`: both tick paths, guarded,
inert unless armed, `advance`'s stepping rule unchanged); `tasks.py`
**`c16c8291`** unchanged; references **`61fb5202` / `61fb5202` / `18b101bf`**
untouched; ckpt `p227_panda156`. Evidence `logs/p232/`.

**P231 (2026-11-24, `logs/p231/`; one **default-off lever**, **not adopted**, no
`configs/` change): "the lift travels with the belt" fails, and the failure is
**geometric** - the lift is longer than the hand's travel.** `FRUIT_LIFT_TRACK_BELT=1`
adds `v x t` to the `grasp_lift` command's y for the whole leg (bounded by
`FRUIT_LIFT_TRACK_MAX`, default 0.12 m), so the pads would ride with the belt and
the drag the pinch resists would go to ~0 - the term P230 named as the only one
not already closed in `logs/p42/SIM_LIMIT.md`. **A/B at 0.24** (`ext=0.10`, 3
episodes each, both arms with `FRUIT_CARRY_DIAG=1`): **1/3 in both**, and
`clean_slip_max` on the two failing lift legs **rises** (1141 -> 2039, 1275 ->
1724 mm) - **P1 falsified**; the *successful* leg is **byte-identical** (191 ticks,
0.0 mm in both arms), so the lever only touched the failures and made them worse.
**The reason is arithmetic**, printed by the lever itself: the lift is
**1.6-4.0 s** at 0.24, so the belt travels **382-964 mm** while the hand is
capped at 120 mm - **262-844 mm of drag left** - and the cell's usable y band from
the pick pose is a few hundred millimetres (the R10-A/P123 reach maps), so
**matching the belt through this lift is physically infeasible**; the 0.12 lift
needs only **90-100 mm**, which is why the same lever is clean there (**2/2
placed**, `clean_slip` 0.0-0.1 mm - **P3 inertness PASSES**). **Partial tracking
is worse than none**, which is what the larger slip says. **Closed**: velocity
matching as a software lever on this cell - it needs a lift short enough that
`v x t_lift` fits the travel (P89 already measured the lift's speed cap
negative, so the two levers fight), or a hand/axis that rides the belt
(hardware), or the ~0.18 m/s band the objective's "success first" already sits in
(0.06-0.18: **11 / 10 / 11 / 11 of 12**). **So the remaining lever for 分拣速度 is
the cycle time at the reliable speeds, not the belt speed** (place ~4.0 s of
~14.5 s/attempt; release ~1.0 s after P227r's trim). Pins: `tasks.py`
**`c16c8291`** (+ `TASKS_MD5` follow), `scripts/selfcheck.sh` (leg
`P231 lift track`: default off, lift-only, bounded, belt axis only); references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt `p227_panda156`.
Evidence `logs/p231/`.

**P230 (2026-11-24, `logs/p230/`; one **default-off diagnostic**, nothing adopted,
no `configs/` change): the objective's starting speed is confirmed and the 0.24
failure is moved one phase later - **the close grips; the loss is after it.**
`FRUIT_BELT_SPEED=0.08` reads **11/12 = 91.7 %** (5/6 + 6/6, `t_arrive` 1.71 s,
`lead` 1.83 s, `dy` 0.136 m, one grip failure), the same plateau as 0.06 / 0.12 /
0.18 - the slow belt is **inside** the envelope, not at its edge. **The
instrument** is `FRUIT_CLOSE_TRACE=1` (default off): one `[close-trace]` row per
close tick, after the step - `cmd`, `aim_minus_fruit` (= `v x lead` in mm),
`x_off`, this pad's `n`/`f`. **It failed twice before it ran and only the
control caught it**: `self._say` and `self._step` are the *env's*, not the task's,
and either raise **inside the close loop**, killing the attempt before any
episode row - at 0.24 that is indistinguishable from the known 0/3, so **a
mechanism cell needs a cell that is known to work** or a broken instrument reads
as a broken line. **The control (0.12)**: contact at close **tick 22** at
`cmd 28.9 mm`, holding **8.46 N** to the end, with `aim - fruit = -21.7 mm` =
`0.12 x 0.181 s` (the shipped `FRUIT_DYNAMIC_TRACK_LEAD`). **At 0.24 all three
closes grip** (`n_end = 2`, **5.7-9.4 N**, first contact ticks 24/50/48, aim lead
43.2 mm growing to 21.4 / 63.1 / 75.8) - **including the two episodes that end
`grasped=False`**. **So two of the phase's own readings are falsified, and the fix
they implied is NOT built**: (a) the aim-lead criterion `L - d/2 <= cmd/2`
predicts no contact at `L = 43.2 mm` and the measurement contacts at tick 24 -
the pads are **26-61 mm wide plates**, not fingertips meeting at `cmd`, so the
criterion must be stated on the plate's footprint; (b) P229's
`contacts@onset = 0` / `force@onset = 0.00 N` / `sep_end = 0.0 mm` row is measured
on the **lift** leg, by which time the payload is already gone - **it says nothing
about the close**, so `FRUIT_CLOSE_LEAD_CAP` was a fix for a mechanism that is
working and was not built. **What the failure is**: the payload is held at
5.7-9.4 N when the close ends and is gone by the lift - the record's loaded slide
(`logs/p42/SIM_LIMIT.md`), whose force / face / friction / seat levers are all
measured out, and the one term **not** in that closed set is the **relative
velocity**: at 0.24 the belt drags twice as fast while the hand is nearly
stationary in y through the lift. **Registered, not built**: `FRUIT_LIFT_TRACK_BELT`
- translate the hand **with the belt** through `grasp_lift` (add `v x t` to the
lift's y target) so the pads do not drag the payload; prediction: `clean_slip`
through the lift falls and `grasped` rises at 0.20-0.24 with the close untouched.
**Caveat carried**: the trace adds one tactile read per close tick, so the
untraced 0.24 cell (0/6) and the traced one (1/3) are **different branches** - no
rate is quoted from a traced cell. Selfcheck **PASS** with the new leg
`P230 close trace`; references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
ckpt `p227_panda156`. Pins: `tasks.py` **`1434f4b2`** (+ the `TASKS_MD5` follow),
`scripts/selfcheck.sh`. Evidence `logs/p230/`.

**P229 (2026-11-24, `logs/p229/`; measurement only - **no `src/`/`configs/` change,
nothing adopted, no reference moved**): the single-arm bins cell's **belt-speed
envelope**, measured for the first time - two ceilings, and the **usable** one is
the contact phase, not the time budget or the runway (the addendum at the end of
this paragraph is what separated them).** The ladder is `FRUIT_BELT_SPEED ∈ {0.06, 0.12, 0.18, 0.24, 0.30}` x
seeds 901/902 x 6 episodes plus a `{0.20, 0.22, 0.23}` bisect, **48 episodes**,
every cell at **`FRUIT_EVAL_LATENCY=auto`** (P228's conclusion), `PREREG.md`
pinned before any cell. **Inside the envelope**: 0.06 **11/12**, 0.12 **10/12**,
0.18 **11/12**, 0.20 **1/2** (a bisect point, not an arm) - pooled **33/38 =
86.8 %** - and the failures are **4 x `fruit did not follow the gripper`**, the
record's grip class; **no catch-up class and no new key**. **Above it the cell does
not degrade, it does not engage**: `v >= 0.22` raises
`RuntimeError: no graspable fruit reached the selection window in 40 feed rounds`
(zero fires, zero episodes - a 0/0 cell is not a rate). **The arithmetic** (read
off the code, `tasks.py:10248` + `assets.py:311` + `reset`'s feed loop): a fruit is
selectable only while `floor(v) <= distance <= depth`, with
`floor(v) = min(v*(0.40 + t_desc + 0.15) + 0.03, 0.80) + 1.5*v + 0.03`,
`depth = spawn_y - pick_y = 0.68 m`, `t_desc = 86 ticks = 0.717 s`, and the
selector polls every **P = 30 ticks = 0.25 s** - so the **eligible band**
`depth - floor(v)` must be alive long enough to be *seen*: **30.3 polls at 0.06,
9.6 at 0.12, 2.7 at 0.18, 1.3 at 0.20, 0.2 at 0.22, negative at 0.24**, and
`v_max = 0.62/(1.267 + 1.5 + 0.25) = 0.2055 m/s`, **validated by the bisect**
(0.20 engages, 0.22 does not). The phase's own first estimate used the floor
crossing alone (`0.224`) and was **one poll period optimistic** - the band has to
be *wide enough to be seen*, not merely positive. **So the shipped 0.12 sits at
58 % of the envelope with 9.6 polls of margin against the ceiling's 1.** **The
pre-registered verdicts**: **P1 PASS** (`speed=` is the cell's speed;
`dy = t_arrive x v`); **P2 FALSIFIED as written** - `lead` is **not** flat
(2.63 / 1.56 / 1.54 s) because the acquisition window's `|jaw-station|/0.20` term
moves with the arm's position (at 0.06 the arm is still far when the fire
condition first holds), which is the mechanism working, while the *distance* was
as predicted (`dy` 0.157 / 0.186 / 0.274 with `v`); **P3 FALSIFIED both halves** -
the break is at **0.20 < v <= 0.22**, not 0.24, and the class is **not** the
catch-up: the cell stops engaging before any chase; **P4 NOT RUN** (its
conditional never fired - 0.30 does not engage at any latency); **P5 APPLIES to
the time budget** - 0.06-0.18 hold at 11/10/11 of 12, so **no arithmetic change
is justified and none was made**. **Two corrections carried in**: the
architecture doc's "the lead is a constant distance `0.19 m`" was **wrong**
(`_dynamic_pick_lead` is `v x time budget`; the 317 attempts read 0.189 m because
they all ran at 0.12), and what *is* hard-coded is the **time terms** - and none
carries P228's 66 ms, which at 0.12 is 8 mm = **2.7 % of the 0.29 m band**, real
but non-binding. **Both levers are priced options, not free knobs**:
`FRUIT_BELT_UPSTREAM` (P225t, default 0) gives `+0.05 -> 0.222`, `+0.10 -> 0.239`,
`+0.15 -> 0.255 m/s` and is a **scene change** (belt collider grows, owes both
references and a store re-baseline); halving the poll to 15 ticks gives **0.220**
and is **not made** (at 0.24 the band is already negative, so no cadence helps).
**The addendum (`PREREG_UPSTREAM.md`, 2x2 `ext` x `v`) separated two ceilings that
this paragraph's first draft ran together**: the equation predicts **engagement**
and does (3/4, the miss *conservative*: `ext=0.10` engages at 0.24 where it
predicts 0.2387, and `+0.10 m` of belt moved the ceiling by the predicted +0.03),
**but the belt extension bought zero placements** - at 0.24 both extensions fire
3/3 and place **0/3**, and the delivered scene places 0/6. **The usable ceiling
is the contact phase, not the runway**: 0.18 **11/12**, **0.20 7/12 (58 %, 5/6 vs
2/6)**, 0.22 1/3, 0.24 **0/6**, i.e. the cell runs out of *grasp* before it runs
out of *runway* (which is why the runway lever is worth nothing here). **Traced**
(`FRUIT_CARRY_DIAG=1`, ext 0.10, v 0.24): the failure reads
`contacts@onset=0`, `force@onset=0.00 N`, `sep_end=0.0 mm` on a 40.0 mm fruit with
`gap_start=14.1 mm` - **the pads closed on air** - against the placed attempt's
`contacts@onset=2`, `force_min=7.88 N` at a 34.4 mm span on 44.0 mm; and
`clean_slip_max = 1769 mm` on the failure is the **hand's own travel**, not a
hold, so **`grasped=False` alone cannot separate "never touched" from "touched and
lost" - `contacts@onset`/`force@onset` is the separator** (any future speed cell
must run `FRUIT_CARRY_DIAG=1`). So the shipped 0.12 sits at **67 %** of the usable
ceiling, and **the lever is the contact phase** (descent duration `v x t_desc` =
172 mm at 0.24 against a 6 mm tolerance, the close's duration, the catch-up
budget), which is Stage 2/3 of the architecture doc. **Harness gap named, not fixed**: `reset` **raises** instead of idling when no
fruit can be selected - in a real cell this is a starvation alarm and a hand-off,
and the direct env has no graceful form. Pins: `tasks.py` **`3f9ef6ea`** and
`rl_env.py` **`41e006a6`** **unchanged**, `scripts/288_speed_ladder.sh`,
`scripts/289_speed_report.py`; references **`61fb5202` / `61fb5202` / `18b101bf`**
untouched; ckpt `p227_panda156` used as-is. Evidence `logs/p229/`.

**P228 (2026-11-24, `logs/p228/`; one **default-off evaluation** lever, nothing
shipped, no `configs/` reference moved): the shipped direct loop evaluates on a
**paused world** - `sample_chunk` runs the model while `SimulationManager` is
never stepped - so its inference latency costs **zero belt travel**, the metric
inflation ReflexBench (arXiv 2608.14379) and LIBERO-Dynamic (arXiv 2610.24579)
name. `FRUIT_EVAL_LATENCY=<d>` advances **`d` control ticks with the arm holding
still** after a decision's inference returns and before its chunk executes
(`sync-hold`, LIBERO-Dynamic's protocol), **without observing or recording**
during the pause; `auto` divides this machine's measured `act()` wall by the
control period, an integer is the controlled sweep, and unset/`0` is the shipped
path byte for byte. It is refused with `FRUIT_RTC`/`FRUIT_VLASH` (the chunker
models the same delay by interleaving, and both would double-count) and with
`--record` (the paused ticks would not enter `ticks_total`, breaking P173's store
invariant). **At the shipped 0.12 m/s one control tick is exactly 1.0 mm**, so
`d` reads as millimetres. The sweep (`scripts/285_latency_bench.sh`) is 5 `d` x
seeds 901/902 x 6 episodes, the `284` recipe verbatim, `PREREG.md` **`b677897e`**
pinned before any non-zero cell. **P1 PASS**: `[lat]` resolves `d` to 4.0 / 8.0 /
16.0 / 8.0(auto p50) and `d=0` carries no row. **The count does not move and P3
does not fire**: 11 / 10 / 9 / 11 / 11 of 12 (pooled **52/60 = 86.7 %**, 95 % CI
[75.8, 93.1]; every arm's CI spans a third of the range), not monotone, and
`d=16` is 11 vs 11 with per-seed **+1 / -1**. **The mechanism is the phase's
content, and its first instrument was wrong** (`RESULTS.md` 4b): `t_arrive` at
the fire is **confounded** - the trigger fires on the first tick `t_arrive <=
lead`, and `lead` is `1.50 + |jaw-station|/0.20`, so `t_arrive` inherits the arm's
own distance to the station (**sd 0.18 s**, larger than the 0.13 s effect a
`d=16` delay would make; means 1.672 / 1.723 / 1.729 / 1.562, rho -0.252 - read
as suggestive only). The clean read is **`lead - t_arrive` at the fire**, whose
baseline is one tick by construction: medians **5 / 10 / 10 / 10 ms** at
`d = 0/4/8/16` (**no typical fire delay**) while the tail grows - `> 33 ms` on
**0/12, 0/12, 1/12, 4/12** and 3/12 (auto). The cause is the injector's own
fidelity, a property of `sync-hold` and not of the cell: the pause is a bare
`advance(1)` loop, so the **whole control loop including the trigger** is
suspended, and a crossing inside it waits. So the sentence is **the chunk is
always delayed, the fire only sometimes** (4/12 at `d=16`), and **the cell
absorbed both**. The catch-up's own loss rows are flat too
(`close: fruit drifted` 1/1/0/1/0). **`auto` is the arm that matters** because
its latency is a distribution, not a constant: p50 **8 ticks**, mean **9.7-10.0**,
range 6-16, plus **one cold-start decision per episode at 55 and 70 ticks**
(620 ms first call) - and it reads **11/12**, the same as `d=0`. **The number the
phase delivers is the latency itself**: in-loop **66 ms p50** (per-cell medians
57-86) against the offline bench's **26.4 ms** (P141), i.e. **8 mm = 1.3x the
6 mm catch tolerance**, not the 0.4x the bench suggests; the gap is **not
diagnosed** (candidates: `_observe` renders immediately before the sample, so the
model competes with a just-issued render; and a different checkpoint). So **from
here a cell is evaluated at `FRUIT_EVAL_LATENCY=auto` (or `8`) and reports the
resolved `d`** - a `d=0` cell reports a latency the machine does not have.
**Classes**: only the record's two known keys (6 x `fruit did not follow the
gripper`, 1 x `fruit left the pick station during the close`), but unevenly -
**0/12 at `d=0` against 6/48 armed (Fisher p = 0.333)**, a direction, not a
result, and a powered cell is not registered. **Verdict = the PREREG's P5 null
branch, which is a positive result about the architecture**: a late chunk costs a
**constant lag** (every decision re-observes) rather than an accumulating error,
and the scripted catch-up re-aims every tick with a **200-tick / 200 mm** budget
against a **6 mm** tolerance, so **<= 133 ms is absorbed** - the L4-approach /
L5-contact split is what buys that, and the real 30 Hz deployment's ~33 ms
(1 tick) is four times tighter than the worst cell here. **Instrument deviations
recorded**: the report's first pass read `t_arrive = nan` (the `[rl] episode`
row *carries* the notes, so an `elif` chain stopped at the episode match; fixed
and the cells re-read from the same logs, no re-simulation), and the `[lat]`
row's `belt_mm` was a literal `0.12` before reading `cfg.belt_speed` (same number
here, so no cell moved, but the cells span two `rl_env` revisions; `tasks.py`
unchanged throughout). Selfcheck **PASS (0 failures, 1 skipped)** with the new leg
`P228 eval latency` (the resolver table, the control period pinned against
`tasks.py`'s literal, and the injector **executed** on a stub: `d` ticks advanced,
**no observe, no record**, `_tick`/`_step` moved with the physics, a
no-inference decision pays nothing, `auto` 26.4 ms -> 3 ticks, the call site
before the execution loop, and both refusals). **No-harm**: `scripts/accept.sh`
reads **7/10 = 70 %, 9.5 s/attempt, `fingerprint: matches`, `190: PASS`** and its
**459 `[fruit]` lines are 459/459 identical** to `logs/p227/accept_final.log`
(the scripted line never constructs `SortingRLEnv`, so this is an import guard).
Pins: `rl_env.py` **`41e006a6`**, `tasks.py` **`3f9ef6ea`** (unchanged),
`scripts/285_latency_bench.sh`, `scripts/286_latency_report.py`,
`scripts/287_p228_latency_selftest.py`, `scripts/selfcheck.sh`,
`scripts/284_single_arm_policy_gate.sh` (the log name is now overridable);
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt
`moe_v13s` `61da390a`, `p227_panda156` used as-is. Evidence `logs/p228/`.

**P142 (2026-11-11, `logs/p142/`; two defect fixes + a declared metric,
**nothing adopted, no reference moved**): the direct lane's two *bookkeeping*
failures are removed and its zero is shown to be the station reselect's timing.
**(1) The P139 handover guard was dormant**: it was written inside
`if FRUIT_SAMPLE_DIAG == "1"`, so the shipped loop never ran it - measured on the
live rollout, `openarm fingertips 103342 mm from the fruit; closing anyway` with the
guard present. It now runs on every close, outside the diag gate, and its abort is
**physical**: `sample.parked` or `pad_error > FRUIT_HANDOVER_PAD_ERROR_MAX` (default
**1.0 m**). The flag term (`_foreign`: the attempt's `protected` index names another
fruit) is **reported, not gated** - the station reselect legitimately adopts the
presented fruit and re-protects it, so the flags lag by a call, measured twice
(`idx=9 protected=1` at **349 mm**, `idx=15 protected=6` at **77 mm**) against the
defect's **101-103 m** and the largest legitimate row in the record (415 mm).
**(2) `FruitSpawner.update`'s despawn loop skipped only `parked`**, so
`_recycle_end` parked a `held`/`protected` body **while the attempt still read
`position(sample)`** - a teleport to `(60 + 3i, 0, -50)`. The recycle is now
**deferred** (`_pending_recycle`): the body leaves the line and is parked by the
next `update()` after the attempt releases it, so the reads see the truth - the
`[sample]` row now reads `pos=(-0.185,-0.221,+0.820)`, a real position 0.4 m below
the belt, instead of the slot. **(3) The score endpoint is declared**:
`success = lifted and on_output_belt(final)` is reachable-False after a successful
place because with `FRUIT_OUTPUT_RAILS=none` (P71) a payload released **onto** the
line can roll off in the ~1 s between the release's own 60-tick settle and the
finalize (`logs/p139/guard2.log` episode 1). `FRUIT_SCORE_ENDPOINT=release` scores
the task's own `placed` - `on_output_belt` sampled **0.5 s after the release**
(`tasks.py:17194`) - and the episode row prints `endpoint=release` **only** when
armed, so the shipped row is byte-identical. **Measured**: with
`FRUIT_POLICY_TRIGGER=arrival`, the P141 checkpoint, the wave and
`FRUIT_STATION_RESELECT=0`, 2 episodes read **1/2 with `success=True
grasped=True placed=True`** - the **first `success=True`** of the whole
investigation, and scored by the declared endpoint (one episode: not a rate). With
the reselect **on**, both cells read 0/2 and the mechanism is in the log:
`reselecting across lanes: presented index 9 ... openarm fingertips 1144 mm` - the
presented fruit **was** at the station when adopted (`station_sample` filters
`along` and `|x-belt_center| <= 0.30`) and by the close it is 1.14 m away or on the
floor. **That reading is a symptom, and the cause is structural**: the reselect is
gated `and not dynamic_capture` and it **ran**, so the direct handover was running
the **P1 indexed** primitive - whose descent aims at a **frozen**
`position(sample)` read once (`tasks.py:14159`) - against a trigger that computes a
**predicted intercept**. On a 0.12 m/s belt that is 0.06-0.36 m of travel between
the aim and the close. `FRUIT_DYNAMIC_PICK=1` (the moving catch, the v8/P1
directive) closes it: the same cell reads **2/2 (`success=True grasped=True
placed=True`, reward 0.9715 / 0.9595)** with the `[sample]` rows healthy
(`protected == idx`, `is_protected=True`, `pos=(+0.225,+0.173,+1.200)` = belt top +
radius, not the slot and not 1.1 m away). **The 2-arm A/B** (`logs/p142/run_p142_ab.sh`,
seeds 77/101/202 x 5, same checkpoint, same wave, same declared endpoint, only
`FRUIT_DYNAMIC_PICK` differs): **dynamic 13/15 = 86.7 % against indexed 10/15 =
66.7 %**, paired 4 dynamic-only / 1 indexed-only, sign **p = 0.375** - a
**direction, not a rate** (P93's rule); what is stronger is the class ledger: the
indexed arm's failures carry **8x `cross-lane station fruit`**, 3x
`fruit did not follow the gripper` and 2x `sample swapped or recycled before the
close`, and the dynamic arm carries **none** (the moving catch skips the reselect
by construction, so the arm never adopts a lane-1 fruit onto lane 0 - a **sort
error** in the ledger either way). **Not adopted**: the flip re-baselines every
direct/policy number, the canary's primitive and the stores' provenance, and the
adoption price is the WS-4.2 shape (N=5 x 15 per arm, ~4-5 h) plus the canary
re-measure. **Both of the dynamic arm's two failures are the closed class**: each log reads
`carry grasp_lift -> carry place0 -> (no release row)`, i.e. grasped and **lost
before the release block** (`logs/p42/SIM_LIMIT.md`'s loaded slide), while every
one of the indexed arm's five failures carries a bookkeeping/acquisition note - so
the catch removes the terms this phase can remove and leaves the one the record
cannot. **The quality cost is separate and the metric is blind to it**
(`logs/p142/grade_ledger.py`): the indexed arm's reselect delivers **8 cross-lane
fruits in 15 episodes, 5 of them on attempts that placed** (`cross-lane station
fruit (index 10) placed on lane 0`), against **0/15** on the dynamic arm - i.e.
~0.5 mis-delivered fruit per episode that the success count does not see.
**The finished adoption batch** (5 seeds x 15 = 75 per arm, `logs/p142/ab5/`):
**dynamic 53/75 = 70.7 % against indexed 43/75 = 57.3 %**, per seed 12/10/12/9/10
against 4/11/12/9/7, paired **25 dynamic-only / 15 indexed-only, sign p = 0.1539**,
pooled **+13.3 points, 95 % CI [-15.2, +15.2]** - a **direction, not a result**
(three of five seeds are a draw; 77 and 404 carry the gap; P93's power note puts
13 points at ~364 attempts per arm). **The ledger is not a direction**: **35
cross-lane deliveries against 0**, Fisher **p = 1.6e-13**, i.e. the indexed
reselect delivers a lane-1 fruit to lane 0 about **once every two episodes** and
the count is blind to it (5 of the first 8 happened on attempts that placed).
**Not adopted, and the reason is a recorded decision**: the policy's dynamic
handover has been deliberately opt-in since P54 (it measured 32/45 = 71.1 % against
16/45 = 35.6 % and still kept the indexed default, because the canary was measured
on it); this phase's rate is inside the noise, so the one decisive term is a
quality argument a flip would pay for with a canary re-measure and a full
direct/policy re-baseline (section 10 of the results). **The corrected metric is
the phase's cleanest number** (a `cross-lane station fruit ... placed on lane M`
note **is** a mis-sorted placement, because the episode's `placed=True` describes
the adopted fruit): on seeds 77/101/202 (45 each) the indexed arm's 27 "placements"
decompose into the **same 15 correct** deliveries as the refusal arm plus **12
wrong-box** ones - so `FRUIT_RESELECT_SAME_LANE=1` (refuse the cross-lane adoption)
is **not a throughput trade**, it is the same correct output with 12 fewer mistakes
(12/45 vs 0/45, Fisher **p = 1.05e-04**), and its scripted acceptance is **provably
inert** (459/459, 0 fires). On the full 75-episode arms the primitive is what
doubles the correct rate: indexed **25/75 = 33.3 %** (43 placed, 18 mis-sorted)
against dynamic **53/75 = 70.7 %** (0 mis-sorted). Read
rule: a direct count is only comparable with `FRUIT_SCORE_ENDPOINT` **and**
`FRUIT_DYNAMIC_PICK` named. **No-harm**:
`scripts/accept.sh` **7/10 = 70 %, `fingerprint: matches`**, its **459 `[fruit]`
lines 459/459 byte-identical** to `logs/p136/accept_final.log`;
`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new **`P142
endpoint + handover`** leg (**26 checks**: the endpoint table + refusal, the guard's
source order inside `if openarm:`, the pad-error knob, the deferred-recycle branch
**executed both ways** on a stub, and the drain keeping a still-owned body);
`211` **ok (115 checks)**. References **`61fb5202` / `61fb5202` / `18b101bf`**
untouched. Pins: `tasks.py` **`50138850`**, `fruits.py` **`41e2e0de`**,
`rl_env.py` **`8feb1016`**, `scripts/270_p142_endpoint_selftest.py`
**`d144bc05`**, `scripts/selfcheck.sh` **`e9fb2a60`**; evidence `logs/p142/`.

**P141 (2026-11-11, `logs/p141/`; three gated inputs + one defect fix, **nothing
adopted, no default moved, no reference re-recorded**): the belt's state becomes an
observation, because it cannot be seen - on the record's 0.04 m/s x 0.5 Hz wave two
frames 33 ms apart differ by ~1.3 mm, inside the camera's own 1.98 mm error, so the
wave is unobservable from the image horizon at any length. **The defect the first
wave collection exposed is the phase's real find**: a 3-episode cell recorded
`belt_speed` with **ptp 0.0000** because the channel read `Conveyor.encoder_speed`,
which is computed inside `step()` **only while the cleats exist** and the cleats
have been off by default since P43/P71 - it is a setpoint echo of the value it was
initialised with. **`Conveyor.surface_speed`** now returns the value `_apply_speed`
writes into `PhysxSurfaceVelocityAPI`, and **both** readers use it
(`tasks._belt_speed_estimate` and `data.belt_speed_scalar`); on the shipped constant
belt the two are the same number, which is why the acceptance is byte-identical,
and under a wave only the new one is the belt that is moving - before the fix the
trigger, the descent's schedule and the 26th channel all saw 0.12 while the belt
ran 0.08-0.16. **The three inputs**: the goal gains **`(v_belt, a_belt)`** (8 -> 10,
`FRUIT_OBS_GOAL_AUX=1`), refreshed **every tick** from the belt (dims 0-7 stay the
selection snapshot); the 26th proprio column becomes **per frame** when the store
carries the trace (the collector writes `belt_speed` under `FRUIT_OBS_SPEED=1`; a
pre-P141 store still reads its pin, byte for byte); the visual horizon is a
config (`--obs-horizon 4`). `a_belt` has **one** implementation
(`data.belt_accel_trace`, tau 0.05 s) used by the loader, and the live loop runs the
same filter. Units are **fixed**, not store statistics (the P28-B rule): `v_belt`
reuses the channel's `(0.12, 0.05)`, `a_belt` is `(0.0, 0.15)` - on a constant belt
every frame has `a = 0`, so a derived std would divide by ~1e-6. **Every widening is
a warm start that preserves the function at step 0**: the goal's two columns are
zeros (the `widen_proprio` identity), and the horizon is `new_w = 0.5*[old_w, old_w]`
on `visual.net.0.weight`, which reproduces the 2-frame embedding to **4.8e-07** on a
static window. **Measured**: the wave store is **10 episodes / 1733 windows**, 1923
frames, `belt_speed` **0.0800-0.1600** with median per-episode **ptp 0.0800**; the
fine-tune (`moe_v13s` + the store + `demos_v11`, 11011 windows, 6 epochs) reads loss
**0.0149**, router 0.993, `demo_val` **0.0133**, and the artifact carries
`goal_dim=10 proprio_dim=26 obs_horizon=4`, **4.603 M** params, first conv
`(32, 20, 5, 5)`. **The model uses the channels, and at a measurable size**: the
deterministic sampler is exact (a repeat is **0.00000 rad**, and a 1e-6 goal nudge is
below float32), and replacing the belt channels with the **constant-belt belief**
moves the chunk **0.00084 rad** through the goal pair, **0.00043** through the 26th
proprio column, **0.00094** together - calibrated against the input the policy already
had (**goal x +1 mm = 0.00054 rad**, +5 mm = 0.00231, `diameter +1 mm = 0.00091`), so
the belt state is worth about **2 mm of fruit position**: the same order as the
camera's error and a third of the 6 mm catch tolerance. **Latency** (the budget the
roll trades against): one `act` is **26.4 ms p50 / 27.3 p95** at DDIM 16 and
**13.4 / 14.2 ms** at 8 (**1.96x**), so `FRUIT_POLICY_EXEC_STEPS=2`'s 16.7 ms budget
is **inference-bound at 16 steps and fits at 8** - the coherent pair is
`EXEC_STEPS=2 DDIM=8`, implemented and env-resolved, **not** adopted. **No-harm**:
`scripts/accept.sh` with every knob unset is **7/10 = 70 %, 9.5 s/attempt,
`fingerprint: matches`, `190: PASS`**, and its **459 `[fruit]` lines are 459/459
byte-identical** to `logs/p136/accept_final.log` - twice, after the plumbing and
again after `surface_speed`; `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**
with the new **`P141 observation aux`** leg (**53 checks**: the gate table, the
per-frame column vs the pin, the 10-D goal, the fixed normaliser, all three wideners,
the static-window identity, a real `moe_v13s` loading and forwarding at 10/26/4, the
single-sited wiring, and the env's assembly + filter **executed** on a stub). **The
live integration passes the width guards** (`[rl] loaded ... obs_horizon=4`,
`env ready`, the episode steps) and then hits **P139's park-slot defect** - the direct
lane's standing item, not this phase's. **Not claimed**: no rate (the wave store is 10
single-arm episodes; the direct A/B is blocked by P139 and the
`on_output_belt(final)` scorer), no task-time gain from the latency knobs, and the
two-line wave store is unbuilt (the collector wedged on its first attempt - the known
renderer-bridge class). **References untouched**: `configs/motion_reference.json` /
`..._twoline.json` **`61fb5202`**, `..._single.json` **`18b101bf`**. Pins: `tasks.py` **`c83fd7c5`**, `conveyor.py`
**`85b3a7b9`**, `rl_env.py` **`937103a5`**, `policy/data.py` **`70befd71`**,
`policy/finetune.py` **`717ca56c`**, `scripts/111_rl_finetune.py` **`a916c7e4`**,
`scripts/269_p141_obs_aux_selftest.py` **`94c105a2`**, `scripts/selfcheck.sh`
**`d53765bf`**, ckpt `p141_wave` **`44ee38e1`**; evidence `logs/p141/`.

**P139 (2026-11-10, `logs/p139/`; **one opt-in reporting fix, default off** -
nothing adopted): the direct loop's dominant failure key, `fruit fell off the
line`, names the **wrong event** - the fruit is in the spawner's *park* slot.**
`_episode_events` ends an episode when the selected fruit is 0.25 m below the belt
top; a one-row instrument (`FRUIT_FALL_DIAG=1`, default off) printed the position
at the event on three episodes: **`(+63, 0, -50)`, `(+96, 0, -50)`, `(+81, 0,
-50)`** - `(60 + 3*index, 0, -50)` is `fruits.FruitSpawner.park`'s own slot, with
`held=False attached=False`. So the episode ended because the **feeder recycled the
fruit** (the attempt outlived the belt: 1500 ticks = 12.5 s carries a fruit ~1.5 m),
not because anything fell. **Load-bearing**: the record's direct ledgers, the
"no new reason" gates and P38's `fell off` census all read that string. The
**discriminating cells** (all at the trained camera 240,424) say the drift is not
ours and not any documented restore: shipped **0/15**, `FRUIT_TRACK=0
FRUIT_SELECT_LIVE_SPEED=0` **0/15**, `FRUIT_SUPPLY_PATCH=1` 0 at 9,
pre-P58 restores 0/3, `FRUIT_ARM_PARK=ready` 1/3 (one episode, not evidence) -
against P54's 75 % and P59-p3's 57.8 %. **CORRECTION (same day, section 5 of the RESULTS): the 0/15 was the *harness*, not
the tree** - `TriggerSettings.from_env` defaults `FRUIT_POLICY_TRIGGER` to **`off`**
(`policy/trigger.py:146`), so `should_fire` returned False on every tick and
`_run_primitive` was never entered (the tell: **no `[motion]` legs** and **no
`[rl] trigger=` row**, which prints only when enabled). **P138's "the direct
interface is blocked / 0/15 against P59's 57.8 %" is WITHDRAWN.** With
`FRUIT_POLICY_TRIGGER=arrival` the primitive runs; the remaining defect is that
`FRUIT_STATION_RESELECT` adopts the presented fruit and by the close its body is at
the **park slot** (`openarm fingertips 102976 mm`) while `sample.parked` reads
**False** - a `parked`/body desync; the reselect now refuses a parked sample, which
does not catch this one. **The A/B itself remains unrun** (one line: the trigger
in `AB_EXTRA_ENV`), and with `FRUIT_POLICY_TRIGGER=arrival FRUIT_STATION_RESELECT=0`
the primitive runs with a **sane pose** (`fingertips 59 mm`) and the failure becomes
a **named trigger refusal** - `intercept trigger (dy=26.3/30.6 cm, dx=-11.6/-8.2 cm)`
- i.e. the **acquisition geometry** the record already names (P32/P48/P49's
delivered-x tail; the record's lever is P50's release-offset compensation). So the
direct lane's chain is: (1) arm the trigger, (2) the reselect can adopt a parked
fruit (`=0` sidesteps it), (3) **the remaining refusal is NOT acquisition
geometry** - the full note carries every term and they all pass (`t_arrive 2.19 s
<= lead 2.20`, `dy 26.3 <= reach 31 cm`, `dx -11.6 <= lateral 16 cm`, `finger
0.020 <= 0.030`), so `dx` is the band itself and **P50's compensation is not
indicated**; the blocker is the second note, `fruit left the pick station during
the close (85392 mm)`, i.e. the sample's body in the **park slot**. **A real defect
is added to the chain**: `FruitSpawner.scan_despawn` skipped `parked`/`held` and
**not `is_protected`** while `_pick_recyclable` says "held, protected, or
output-line fruit are never taken", so an in-flight sample crossing `despawn_y` is
parked mid-attempt; the term is added (`211` ok 115 checks, selfcheck PASS) but is
**not sufficient** - the same cell still reads `fingertips 101584 mm` and a gate
recirculation, so at least one more path moves a body to the slot. **The `[sample]` row answers it** (`FRUIT_SAMPLE_DIAG=1`, default off; printed where
the handover is decided): `idx=9 parked=True held=True protected=1
is_protected=False pos=(+87,0,-78.7)` - the task closes on a **parked** fruit while
the attempt protects **index 1**, i.e. a **swap** (the station reselect adopts the
presented fruit) followed by a **park**, with the body at `60 + 3*9` fallen to
`z = -78.7` (the slot is in mid-air). The only remaining `park()` caller that can
take a `held=True` sample is **`spawner.reset()`**, which parks *every* sample
unconditionally, so the next read is a reset/episode-boundary interleaving with an
in-flight attempt. **The guard the row justifies is built** (abort when `sample.parked`, or when
`not is_protected(sample)` while the attempt's `protected` is another index) and it
works: episode 0 ends at **684 ticks** instead of 1746 with a truthful note. **The
reset is cleared** (`[reset] parking 16 sample(s): held=[] protected=[]`), so the
swap+park happens inside the attempt, not at the boundary. **And the lane places**:
episode 1 is `grasped=True placed=True` (`place low: bottom 1462 -> 48 mm`) - the
first placement in this investigation - yet still `success=False`, because
`success = _lifted and on_output_belt(final)` and the fruit is **not within the
6 cm margin of a lane at `_finalize`** with `FRUIT_OUTPUT_RAILS=none` (P71): it
rolls off the slab after the release. So the direct lane's 0 rate decomposes into
four terms - the trigger default (harness), the reselect adopting a parked fruit
(guard), the 100 m chase (same guard), and **the scoring term** - and only the last
is open. The guard's `sample swapped or recycled before the close` is a **new key**
in the direct lane's reason set (declared; no rate claimed on it). **The fix
shipped is opt-in**: `FRUIT_FALL_PARKED=1` makes a **parked** sample not end the
episode on that note (it is left to its horizon); it changes the failure-reason
ledger, so it is its own cell and was armed in no measurement here. The **owed**
work is the direct interface's regression diagnosis, with the `[fall]` row plus
the per-episode `decision=`/`ticks=` as the instrument. `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**, `106` OK, `107` PASS (21 checks); references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt `moe_v13s` `61da390a`.
Pins: `rl_env.py` **`8cbba5a4`**. Evidence `logs/p139/`.

**P138 (2026-11-10, `logs/p138/`; **a recollection + a fine-tune, nothing
adopted** - no `src/` change, no `configs/` change, no reference moved): the store
that P136's branch change owes is recorded, learned, and its behaviour is
unmeasured at the required N.** The shipped two-line with the tracker on
(`track=1(default)`, the P136 catch) collected **45 episodes / 8,847 windows**
(seed 901, left 23 / right 22; `106`: `entries=45 files=45 index_frames=9612
file_frames=9612 unique_content=45 OK`); its `manifest.json` carries
**`physics.tracking`** (`origin: default`), which is what makes a post-P136 store
identifiable (a pre-flip one reads `scope-off` or has no key). Fine-tune with the
lineage recipe (`111_rl_finetune`, `moe_v13s` `61da390a` init, `demos_v11` base, 6
epochs, lr 5e-5, `ones`, base-weight 1.0) -> **`checkpoints/p138_track`**
(`policy_best.pt` **`316f8dd3`**), final weighted loss **0.0205**, router 0.992,
demo_val 0.0121. **Fidelity** (offline, `119`, 192 windows, a *diagnostic*): the
candidate is **0.57x** the init's paired action error - **0.240 -> 0.138 rad**,
fing 0.0016 -> 0.0008, **155 improved / 37 worse, sign p < 0.0001**, and it
improves on every skill slice (approach 0.135->0.083, grasp 0.335->0.165, lift
0.275->0.179, place 0.297->0.173) - it learned the store. **Behaviour, a smoke**:
the hybrid canary (the interface P136 leaves on the pre-tracker catch), init vs
candidate, seed 77, 3 episodes each: **2/3 vs 2/3**, baseline reasons only, both
PASS - **no discrimination at n = 3** against the canary's recorded 5-8/10 spread,
which is the only honest reading. **No rate is claimed**: the direct A/B
(`112_rl_ab.sh`, N = 5 x 15, the WS-4.2 protocol) is **1.5-2 h** and named, not
run, and the tree already carries three nulls on this interface (W7-C/W8-A, R9,
P37); a 45-episode store is also below the 150-200 the lineage recollections used.
`accept_policy.sh`'s default checkpoint is **unchanged** (`moe_v12`) - the
candidate is an artefact, not a default. **The A/B itself is BLOCKED**: its first
cell read **0/15** with all 15 episodes `fruit fell off the line`, and the
discriminating cells say the drift is not ours - **init with
`FRUIT_TRACK=0 FRUIT_SELECT_LIVE_SPEED=0` (P136/P137 neutralised) is also
0/15**, `FRUIT_SUPPLY_PATCH=1` is 0 successes at 9 episodes, and the log names a
**107 m** hand-to-fruit state (`openarm fingertips 107626 mm from the fruit;
closing anyway`) plus `[belt] recirculating ... waited 60 s` on four fruits, while
the **park arms differ by one episode at n = 3** (0/3 default vs 1/3 `ready`) and
that is not evidence. So the **direct loop reads ~0/15 where P59-p3 read 26/45 =
57.8 %**, the **hybrid canary still PASSes (2/3)**, and a checkpoint comparison
here would measure the drift, not the candidate. The 107 m row is a
**late-episode** symptom (absent in every 3-episode cell), not the park's own
state. **The blocker is a phase of its own** - the record's direct numbers are not
reproducible on this tree, and nothing in this phase claims otherwise. `scripts/selfcheck.sh` **PASS (0
failures, 1 skipped)**, `106` OK, `107` PASS (21 checks); references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt `moe_v13s` `61da390a`;
`logs/p138/PREREG.md` **`48c8dbc7`**, `logs/p138/RESULTS.md` **`d86157f4`**.
Evidence `logs/p138/`.

**P137 (2026-11-10, `logs/p137/`; **one shipped change - the selector sizes its
window with the belt's own speed** - no reference re-recorded): the last place
the catch read a speed that is not the belt's is gone.** `select_target` sizes its
station window in *metres* from a *time* (`FRUIT_PREPOSE_LEAD_S` 0.9 s + the
0.12 m pre-pose lead, plus `_dynamic_select_floor`'s 1.5 s setup) and multiplied
it by the **authored** `cfg.belt_speed`; `_selector_speed(task)` now returns the
**live** `_belt_speed_estimate()` (config fallback for an encoder-less stub,
`FRUIT_SELECT_LIVE_SPEED=0` restores the old read), at `_prepose_lead_value` (the
selector's edge and the reach path) and `select_target`'s two pre-pose terms. **The
gate is inertness, and it passes**: the shipped acceptance reads **7/10 = 70 %,
`fingerprint: matches`, `190: PASS`**, and its **459 `[fruit]` lines are 459/459
byte-identical** to `logs/p136/accept_final.log` - on a constant belt the encoder
*is* the authored speed, so no reference re-record is owed and none was made. **The
term does not bind**: the belt-wave cell (0.04 m/s at 0.5 Hz, P135's scenario, 3
attempts) reads **12/13/11 ticks at 5.4/5.8/6.0 mm and 2/3 placed, identical to
the pre-change cell** (`logs/p135/recheck/wave_w.log`) - the window's error (<= 36
mm) is inside the selector's slack here, which is what the record said from the
other side (P99: the interval is the sequencing of two overlapped arms, not the
arrival; P58/P59: the depth means do not rank the arms). **Not a lever**: a
correctness fix whose measured behaviour is identical in both scenarios the
project has; it ships because it is inert on the acceptance and wrong without it.
Every speed the catch consults (the descent's schedule, the gate, the catch-up's
lead, the selector's window) now reads the belt's own. `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)** with three new checks in `176` (stub -> config,
live encoder -> follows, `=0` -> config), `106` OK, `107` PASS (21 checks). Pins:
`tasks.py` **`e3d3331c`**, `scripts/176_twoline_selftest.py`; references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt `moe_v13s` `61da390a`;
`logs/p137/PREREG.md` **`828f7048`**. Evidence `logs/p137/`.

**P136 (2026-11-10, `logs/p136/`; **one shipped change - the prediction-gated
handover is the scripted line's default** - and both motion references
re-recorded): the moving catch's aim, descent and catch-up now run on the
estimator for the **scripted** line, and the two policy interfaces are scoped out
by construction.** The owner chose the flip after P135's measurement (a varying
conveyor: the shipped *speed* gate misses the handover by **298-407 mm**, the
prediction gate converts every one at 12/13/11 and 16/15/17 ticks, timeouts
2->0 / 1->0). **One resolver** (`tracking.tracking_resolution`, in `tracking.py`
so it is offline-testable): `FRUIT_TRACK` unset -> **on for the scripted line**
(`default`), **off for the policy interfaces** (`scope-off`); `=0` restores the
pre-P136 path; `FRUIT_DESCENT_TRACK` / `FRUIT_TRACK_WAIT` unset **follow**
`FRUIT_TRACK` and an explicit value wins; the scope is the **task**
(`PickAndPlaceTask(scripted=True/False)`), not the session - `release_speed_resolution`'s
two-line predicate cannot be read at construction (the P97 defect). **The scope is
enforced at the constructor**: `rl_env` and `scripts/60_eval_policy.py` pass
`scripted=False`, so the direct/policy env and the **hybrid canary** keep the
pre-P136 catch (their rows print `track=0(scope-off)`). **Measured**: the shipped
acceptance is **7/10 = 70 %**, 9.5 s/attempt, **budgets pass** (worst `|v|max`
0.126 against 0.161, lurch 0.059 against 0.291) with the fingerprint moved - so
**both references were re-recorded from same-batch flipped runs**:
`configs/motion_reference.json` = `..._twoline.json` = **`61fb5202`** (from
`logs/p136/accept_flip.log`, `190: PASS` against it; the **final** acceptance on
the committed tree reads **7/10, `fingerprint: matches`, `190: PASS`** with its
**459 `[fruit]` lines 459/459 identical** to that run, `logs/p136/accept_final.log`) and
`configs/motion_reference_single.json` = **`18b101bf`** (from the `FRUIT_BIARM=0`
run, 5/9, 15.4 s/attempt; the pre-flip `8952c320` archived at
`logs/p136/motion_reference_single_pre_flip.json`); the two pre-flip two-line-side
files are archived beside it. **The canary smoke reads 2/2 and `track=0(scope-off)`**,
so the interface of record is comparable; `scripts/234`'s reference-arrangement
pin now asserts the post-P136 single-arm record. **Provenance**: the store manifest
gains **`physics.tracking`** (`scene._tracking_provenance`, one builder, both
writers via `finger_physics_provenance`): `{on, descent, wait, mode: cv, gate,
tau, corr_max, source, scripted, origin, label}` - a manifest without the key
predates P136, and a policy store reads `origin: scope-off`. Verified in a
1-episode collector probe (`logs/p136/demo_probe/manifest.json`). **No rate is
claimed**: on the nominal belt the tracker is a measured **tie** (P135 §4),
so 7/10 against 8/10 is a branch draw; the argument is the wave mechanism.
**Re-baseline: every scripted acceptance/rate recorded before P136 is a
pre-tracker number; `FRUIT_TRACK=0` restores it** (compose with the earlier
restores: `FRUIT_BIARM=0` for the single arm, `FRUIT_SPEED_RELEASE=0`,
`FRUIT_ARM_PARK=ready`, `FRUIT_POLICY_TRIGGER_ACQ=0`, `FRUIT_BIARM_PREPOSE_CLEAR=0`
per their own notes). `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with
the P135 leg extended to **40 checks** (the resolver table), `106` OK, `107` PASS
(21 checks). Pins: `tracking.py` **`559203e8`** (the resolver + the estimator), `tasks.py`
**`55053493`**,
`rl_env.py` **`1c6e5ebd`** (`TASKS_MD5` follow + `scripted=False`), `scene.py`
**`e614f06d`** (`_tracking_provenance`), `scripts/60_eval_policy.py` (`scripted=False`),
`scripts/40_collect_demos.py`, `scripts/268_p135_track_selftest.py`,
`scripts/234_p64_precomp_selftest.py`; references **`61fb5202` / `61fb5202` /
`18b101bf`**; ckpt `moe_v13s` `61da390a`; `logs/p136/PREREG.md` **`bcdc6eba`**.
Evidence `logs/p136/`.

**P134 (2026-11-09, `docs/CLOSEOUT.md` §6; design/handover only, no `src/` or
`configs/` change): the engagement closes out for the owner** - a one-page
section appended to the project close-out: the shipped state (two lanes, 8/10,
58/80 = 72.5 %, the instruction layer on both lines), what the engagement
measured and closed (the descriptor/instruction/ledger arc, the third lane
opt-in at -17.5 points, the loaded-slide families all negative or a draw, the
μ<1 pad dead, the ring's freeze and centring, the acquisition tail), the
owner's constraints as they stand, what the hardware partner should take away
(the decision book and its §7), and the pointers. It is the owner-facing summary
of `logs/p104`-`logs/p133`; `106` OK. Evidence `docs/CLOSEOUT.md` §6.

## 3. What changed -> what to run

| you changed | run |
| --- | --- |
| a **belt-speed** or **scene-runway** change (a faster line, `FRUIT_BELT_UPSTREAM`, a selector-floor or poll-cadence change) | `scripts/288_speed_ladder.sh` - it prints the envelope, not a rate: read **`does not engage`** (the `no graspable fruit ... 40 feed rounds` abort) as a boundary and never as 0 %. Compute the band `depth - floor(v)` per speed and require **>= 1 poll** (`P = 30 ticks = 0.25 s`): `v_max = 0.62/(1.267 + 1.5 + 0.25) = 0.2055 m/s` on this cell, and the shipped 0.12 sits at 58 % of it (P229) |
| **any claim that a cell is "real-time"**, or a policy/episode number quoted as a deployable rate | `FRUIT_EVAL_LATENCY=auto scripts/285_latency_bench.sh` (or `D_LIST="0 8"` for a same-machine pair), then `scripts/286_latency_report.py` - **report the resolved `d`**: the shipped loop never steps the world while the model runs, so a `d=0` cell reports a latency the machine does not have. Read the `d_meas`/`infer_ms` columns **first** (the manipulation check: a cell with no `[lat]` rows measured nothing), then the mechanism (`t_arrive` at the fire stays flat when only the chunk is delayed; a fire delayed by the injection would fall by `d/120` s), then the count as a branch. At 0.12 m/s **1 tick = 1 mm**, and the in-loop latency is **66 ms = 8 mm p50** against the offline bench's 26.4 ms (P228) |
| a **throughput or rate** claim (a speed profile, a scheduler/supply change, a wall number) | `scripts/186_w6_report.py` on **>= 2 seeds** with **both denominators** (placement window and batch span) **and the wall column** (`logs/p80/p80_report.py` is the template: wall from per-line stamps, never inferred), that scenario's own motion gate (single arm: `105 --fingerprint configs/motion_reference.json`; two-line: `scripts/190_twoline_gate.sh` against a reference of the **same attempt count**), then `scripts/accept.sh` |
| a **per-leg profile or dwell** change (`FRUIT_SPEED_RELEASE/PLACE/LIFT`, a `[cycle]` block that moves) | `FRUIT_CYCLE_REPORT=1 FRUIT_PLACE_TRACE=1` on **both** arms, **>= 2 seeds**, then the `[cycle]` per-leg block table **by median** (`logs/p86/p86_report.py --blocks`): the **block** is the mechanism, **never the attempt span** - the span carries the supply-phase acquisition legs and re-draws with the shifted attempt boundary (`logs/p86/RESULTS.md` §3, P44 §3). Delivered: the interval (pooled **and** per arm), both denominators, the wall and `placed/min wall`. Landing: `FRUIT_PLACE_TRACE`'s `on_belt` on **every payload present at the release** (`release_bottom >= 0`; the -184 mm rows are the upstream-lost class, reported separately). Then the scenario's own motion gate - a profile change **moves the fingerprint by construction**, so budgets-only for the treatment and a same-seed reference for its control |
| the **release clock's scoped default** (`tasks.release_speed_resolution`, `speed_cell_defaults(two_line)`, the `[biarm] release profile:` row, `scene._release_provenance`, the manifest's `physics.release`) | `scripts/selfcheck.sh` (the `247` leg: the resolver table - unset/no-scope **is** `_SPEED_SHIPPED` exactly, unset/two-line is the trim, `=0` restores, `=1`/`FRUIT_SPEED_ALL` win globally, `=0` beats the union, the settle is read only when on - the clock arithmetic, the single scoped call site, the row printing only inside `run_bimanual`, and `physics.release` in both writers), then **the replay first**: the same-seed cells must be **byte-identical to the pre-flip record** on the `[fruit]` stream with the phase's rows dropped (`logs/p87/p87_report.py --same`; P87's four cells are 865/865 / 868/868 / 814/814 / 821/821 against P86's), then **the inertness pair** - `FRUIT_BIARM=0 scripts/accept.sh` **raw 346/346** against `logs/p71/accept_rails_none.log` (+ `fingerprint: matches configs/motion_reference_single.json`) and a shared-station `=1 FRUIT_BIARM_TWOLINE=0` pair unset-vs-`=0` compared with `--same` **and** `--profile` (the row's `origin` field legitimately differs; the **clock** must not) - then a 10-attempt shipped acceptance to re-record the two-line references, then `scripts/accept.sh` |
| the **place cap's scoped cell** (`tasks.place_speed_resolution`, `PLACE_TWO_LINE_DEFAULT`, the `[biarm] place profile:` row, `scene._place_provenance`, the manifest's `physics.place`) | `scripts/selfcheck.sh` (the `248` leg: unset/no-scope **is** `_SPEED_SHIPPED` exactly, unset/two-line is **also** the shipped pair because the default is off, the explicit `=0.52` is the measured arm with its **362 -> 244-tick** clock at the named **0.55 m** reference, the override table, the profile clock reproducing `motion.jerk_limited` in **both** the speed- and acceleration/jerk-limited regimes, both consumers on the session predicate, the row printing only inside `run_bimanual`, and `physics.place` in both writers), then the same replay/inertness shape as the release row (`--same` against the pre-change record, `FRUIT_BIARM=0 scripts/accept.sh` **raw 346/346**, the shared-station `--profile` pair), and read the delivered side on **both denominators**: the interval **is** `window/(n-1)`, so the window rate and the interval are **one statistic** - a place cell that lengthens the placement window reads as a worse interval even with more placements (`logs/p88/RESULTS.md` §3) |
| the **lift cap's scoped cell** (`tasks.lift_speed_resolution`, `LIFT_TWO_LINE_DEFAULT`, `_LIFT_SCOPED_VMAX` / `_LIFT_REFERENCE_DISTANCE`, the `[biarm] lift profile:` row, `scene._lift_provenance`, the manifest's `physics.lift`) | `scripts/selfcheck.sh` (the `249` leg: unset/no-scope **is** `_SPEED_SHIPPED` exactly, unset/two-line is **also** the shipped pair because the default is off, the explicit `=0.37` is P44's **S3-v** with its **162 -> 136-tick** clock at the named **0.21 m** reference, **`=1`/`FRUIT_SPEED_ALL` keep S3/S13's measured 0.36/1.9** while a `0.37` value means 1.0 however it is written, `..._AMAX` pins the acceleration, the profile clock reproducing `motion.jerk_limited` in both regimes **and the short-leg null below 0.225 m**, both consumers on the session predicate, the row printing only inside `run_bimanual`, and `physics.lift` in both writers), then the P88 shape - `--same` against the pre-change record, `FRUIT_BIARM=0 scripts/accept.sh` **raw 346/346**, the shared-station `--profile` pair, and a fresh unset `N5` replay - and read the block on the **mean plus the per-leg read**, never a median across legs of different lengths (`logs/p89/RESULTS.md` §1) |
| **any `[cycle]` block** you are about to "speed" (the `descent`/`grip`/`close`/`hover`/`prepose` family, or a per-attempt **tick** constant such as `FRUIT_DYNAMIC_PROBE_TICKS`) | **the audit first, offline** (`python3 logs/p91/audit.py`, `--predict`, `--schedule`, `--grip`): a block is **wait + tax + motion**, and only the motion is a lever - the `descent`'s whole block is `lead/speed − margin` and **cannot move** (a faster leg waits longer; `logs/p91/AUDIT.md` §3), the `grip`'s mean carries P40's probe tax, the `close`'s direction is contested (R11-B), and the `hover`/`prepose` have no profile (an IK step cap and a tuned blend). Then the scoped-resolver shape (`probe_ticks_resolution` is the fourth; the `[biarm] take-off profile:` row + `physics.takeoff`) and the P91 battery: `--blocks` reads **P1b on the clean-mode instance** (the block's deterministic constant), **never the mean**, because a tick trim that makes a *validation* harder moves the **mode mix** against you (P91: clean −0.31 s exact, block mean **+0.23/+0.38**, first-probe success 14/20 → 5/20) - and read the **pinch** (`[carry] force_min`, the P41 9.7-9.9 N plateau) and the loaded-slide guard, because a tick cell can be coupled to a **force** (`logs/p91/RESULTS.md` §2) |
| **the descent's timing** (the hover wait, `FRUIT_DYNAMIC_DESCEND_MARGIN` / `FRUIT_DYNAMIC_LEAD_MARGIN`, `_dynamic_pick_lead`, the selector floor it feeds) | **read the row's arithmetic before you read the row**: `[task] dynamic descent` prints `fruit dy`, and `intercept = fruit − speed*t_desc` makes it **algebraically invariant** to the margin (`dy == speed*t_desc`; P109 measured 83.0 / 82.0 / 83.0 mm at margins 0.15 / 0.075 / 0) - the gap a timing knob sets is **`g0 = fruit dy + shift = deadline = speed*(t_desc + margin)`**, so register `g0`, never `fruit dy`. Then the **arrival sign**: `g0 − 0.12 m/s * steps` must stay **positive** (the fruit upstream when the pads stop), because the catch-up commands `fruit + v*0.25 s` - 30 mm *downstream* - and the loop is bistable, not graded: it exits at the 6 mm tolerance or runs away to 200-270 mm, with **nothing in between** (P109: `past_aim` 0/76 at 0.15, 9/75 at 0.075, **79/79** at 0; runaways 0 / 0 / 5 of ~78). Read it as **`residual > 50 mm`** (`logs/p109/p109_report.py`), not `> tol`: the tol read is the tolerance itself in every arm. Watch the **branch** - the selector floor moves with the same term, so the selected sequence changes and a count delta across arms is partly a draw - then the acceptance A/B (the two-line reads this knob too, both stations) and `logs/p109/RESULTS.md` §5's clause table |
| the **park return's clock** (`tasks.park_profile_resolution`, `PARK_TWO_LINE_DEFAULT`, `FRUIT_BIARM_PARK_BLEND`/`_SETTLE`, the `[ready]` row's `blend`/`settle`/`q_step`, the `[biarm] park profile:` row, `scene._park_provenance`, the manifest's `physics.park`) | `scripts/selfcheck.sh` (the `254` leg: unset/no-session **is** the shipped 90/120, the env is **not read** without a two-line session - the driver's pre-session prime transit keeps the shipped clock, unset/two-line is also the shipped pair because the default is **off**, the explicit `60/75` is the measured arm with its **135-of-210-tick** clock (`-0.625 s`), the halves are independent overrides with the read sites' clamps, the shipped pair **is** `READY_TRANSIT_BLEND_TICKS` and `_ready_settle`'s own default, `q_step` is arithmetic inside the diag block, `physics.park` in both writers), then the **control replay first** (`python3 logs/p100/p100_report.py --same logs/p100/C5.log logs/p99/C5.log`, dropping `[ready]`, the park row and `[bed-sel]`) - that one comparison proves the tree inert, the control valid and `FRUIT_READY_DIAG` neutral - then **>= 4 seeds**, the **park block** as the mechanism (`park moving -> park done`, and the `[ready]` decomposition), `q_step <= 0.15 rad/tick` and **`post_err` against its own same-seed control** (the shipped park sits ~5x inside `TRANSIT_TOL`, a trim spends that margin), then the **slot dead time split** (`logs/p99/census.py`): **the park is a motion inside the slot loop, and the slot loop is not the interval either** (-0.62 s/slot bought a pooled interval of +0.5 %; the gate and the starved polls take it back), then both denominators + the wall, then the trace-pair clearance census (`--clearance`, no rate from those cells; this tree reads 48 mm min, so the historical 1.9-2.6 mm must not be quoted) - `logs/p100/RESULTS.md` |
| docs, or a number's provenance/data size | `python3 scripts/106_index_audit.py` and `python3 scripts/107_collect_merge_test.py` |
| motion, control, `trajectory` limits, IK | `python3 scripts/96_motion_check.py`, then `scripts/accept.sh` |
| collection (`40_collect_demos.py`) or merging (`41_merge_demos.py`) | `scripts/107_collect_merge_test.py`, then `python3 scripts/106_index_audit.py` |
| simulator behaviour, scene, gripper, conveyor | `scripts/accept.sh`, then `scripts/demo_2min.sh` |
| the supply schedule (`fruits.py`, `bed.py`) | `python3 scripts/211_bed_audit.py`, then `scripts/selfcheck.sh` |
| a **supply-geometry** change (the lateral band `FRUIT_SUPPLY_X_MIN/MAX`, the release schedule, a station/column move) | the **census first**, offline: `python3 logs/p92/census.py` and `python3 logs/p92/chase.py` name the class you are trying to move and the servo's `closed > 0` signature (`logs/p92/CENSUS.md`); then the **manipulation check** - `x` is one `uniform(x_min, x_max)` draw and no code branches on it, so the *planned* band is proved by the `[supply] lateral x=` row and the *delivered* x is a **distribution** (plan + a per-instance offset: `0.36 -> 0.3908` at the top), never a bound; then 20 attempts x **>= 2 seeds, of which at least two must be FRESH** (P93: two seeds reuse the same two control branches and over-state the gain - the band's `28 -> 36` became `58/80 -> 65/80` at four, with the two fresh controls reading 15/20 twice against seed 6's 12/20) with the class counts (`cnp` / never-held / chase) as the primary, **both denominators + the wall** as the rest, `bash logs/p92/gates.sh` (**budgets only** - every 20-attempt two-line reference in the tree predates P87's release clock, so any post-P87 cell reads `fingerprint: DIFFERS` by construction; the control proof is the line-identity replay against `logs/p91/{C5,C6}.log`), `python3 scripts/211_bed_audit.py`, and `scripts/accept.sh` |
| a **new hand kind** (`FRUIT_GRIPPER_KIND`, `src/fruit_sorting/*gripper*.py` or `cage_hand.py`, the `RIGID_TOOL_HANDS` predicate, `_pad_standoff`/`_fingertip_offset`/`_hand_separation`, the `track_arm` hook) | the **geometry probe first, with no attempt loop** (`logs/p107/m1_cage.py`: the aperture vs command, the tool offset across the range, the pad-pad corner gap, the distal plane and the lip - all off the **built** prims); then `scripts/selfcheck.sh`; then one 1-2 attempt smoke for the mount; then the **two-line-scoped** checks are unchanged because `tasks.py:9543` refuses a non-`openarm` hand in a `CoopSession` (if that refusal is ever lifted, the two-line gate is owed); then **the hand cells with their own same-seed controls on the same tree** (a hand moves the collider set - P71's rule - so compare **budgets + rate**, never a fingerprint) plus `scripts/accept.sh` with `FRUIT_GRIPPER_KIND` unset, which must read `fingerprint: matches` and a `[fruit]` stream byte-identical to the record (`logs/p107/RESULTS.md` §5). Read a mount defect in this order: plate width vs aperture, plate length vs the flange, the **asset's** finger colliders (`FRUIT_FINGER_COLLIDERS=0` does not remove them), the drive damping vs the pad mass (`c ~ 2*sqrt(k*m)` for a standalone joint tree), whether the hand **rides the arm every tick**, the open aperture vs the line's pursuit error, and the radial close law |
| a **presentation / centring element** at the station (a passive guide, a metering gate, a station magazine, a "hold the fruit while the belt slips" element) | the **census first, offline** (`python3 logs/p110/census.py`): the split at the band entry is **55.8 mm along-belt / 2.6 mm lateral** and the term is `speed * t_desc` (a descent property, P109), so a **lateral** element can remove **0 %** of the binding axis (`A_y = 2(dy + r)` is unchanged) - that alone kills a guide; then the **gate's three couplings**, all read off the code before a build: the **selector cannot see a parked fruit** (the moving floor is 0.389 m, the indexed station window's lower edge 0.10 m), the **rate** (0.83-2.9 s delivered against a 15.1 s pick = **8.1 fruit = 1.81 m** queued into a 1.60 m belt), and the **height** (the hand's lowest solid part at the grip is **14.5 mm**, `tasks.FINGER_TIP_BELOW_JAW`). Then the fixture (`logs/p110/fixture_gate.py`, a `logs/` probe - the gate's contact mechanics only, no arm) with `P110_H` x the **whole pool** and the **stream cells** at the shipped cadence (`P110_N`, `P110_GAP`), reading the **hold's span** (not just "held"), the **parking spread across the pool**, the steady drag, and whether the stream **singulates** or wedges; then `logs/p110/p110_report.py`. **Judge it against the ring's own requirement, not against "does it hold"**: the cage's closure is one radial synergy on force-capped position pads, so it needs `delta < 0.01 d = 0.6 mm` (the elastic allowance is `cap/k` = 0.049 mm) while the line's positioning is the **6 mm** catch tolerance and the gate's hold is 1.8 mm within / 17.5 mm across - if that inequality stands, **no presentation element can enclose** and the lane closes to a **compliant closure** (a hand change) or a sub-mm tolerance (only with a stationary fruit). A gate is a **scenario** element: a flip owes both references, every store, and the `scene` manifest block (`assets.scene_provenance`) naming the collider set |
| a **scene change**, or a new fixture that prices one (a pad face, a friction coefficient, a presentation element, a station move) | **the fixture's own support proof first, and say which form it takes**: a *grasp* fixture has no passive support, so the admissible test is the inverse - zero pad force ⇒ the payload falls, the pads at their home ⇒ it falls, the pads closed ⇒ it is held (`logs/p117/fixture.py`'s A1: 613 mm of fall vs **0.0000 mm** with the weight compensated and the velocity pinned) - while a *support* fixture (a pocket, a table, a belt) must show the payload does not move, and the honest bar is **no worse than the belt the line already uses** (`logs/p117` B1: the pocket 0.364 mm/200 ticks against the belt's own 0.018-0.382 mm straight-line residual, because the 0.05 mm bar is under the sim's jitter floor - P107/P112's failure was 2 mm + 4-5 mm *monotone*). Then the endpoint: **a break-away is not a creep**, and the creep must be **split into its load-axis and lateral components** (`[p117] seat`'s `dz` - P104's 3.20 mm is `dx=-3.20, dz=+0.02`, a jaw-axis seat shift), and **a groove needs a different closure law** (`r - sqrt(r^2-R^2)` deeper per pad, `contact_travel`). Price a candidate against the shipped knobs that already exist (`FRUIT_FINGER_FACE`, `FRUIT_FINGER_MU`) before adding one, and read the *rate* only in a two-line battery at >= 2 seeds + 2 fresh. **Check the owner's constraint first (2026-11-06): the dynamic scattered pipeline must be preserved - no diverter, stop gate, guide/limit or pause.** P117's pocket was withdrawn on it (the build reverted, patch archived at `logs/p118/pocket_build.patch`) and the belt 0.15 is a measured negative on the shipped two-line (`logs/p119`: 9/20 against 16/20, grip losses 20 against 8, interval 16.85 against 10.59 s) |
| the **`[cage]` enclosure endpoint** ("`pads >= 3`" from `FRUIT_CAGE_PROBE=1`, any P107/P108 successor) | **do not read the pad count alone**: join each `[cage]` row to its attempt's `[motion] approach ... end=` and its own `aper`/`F`, and split it into **jam** (`end > 15 mm`), **over-closure** (`aper < dia - 4 mm` or `F > 4 cap 1.5`) and **clean** - P110's 74-attempt census reads **11/74 raw but 2/74 clean** (jams `F` up to 2920 N, over-closures 119 N), and the modal 2-pad grasp is a V-block with `n = 2`, i.e. the shipped pinch's own capacity (`logs/p110/RESULTS.md` §3). **P131 corrects two terms and adds the law knob**: the over-closure is `aper < R - 4 mm`, where `R` is the fruit's **horizontal** extent (the strawberry's class `dia` is its **height**, `R/dia` = 0.792, so `dia - 4` flags every strawberry grasp), and a **miss** (`off > 15 mm` at the close's end) is not an over-closure - corrected, the freeze-off cells read **7/40 over**, not 22/40. The operative target is the **two-jaw** `deep = 0.97 x min(radial, axial)` (the fruit's height), not the ring's law; `FRUIT_CAGE_APERTURE=shipped|max_extent|pad_axes` (default `shipped`, the shipped expression bit for bit) routes a radial hand's `deep` through its own stated extent (the `pad_axes` base-frame law; the two-jaw 2.5 mm interference floor is dropped with it). Read the variant against the **same-seed freeze-off control on the same tree** (the cage cell is **not bit-reproducible** - two identical unset runs diverge at attempt 0 - so P130's `F5`/`F6` are not a control) and read `sep` vs `aper` (the drive) beside `aper` vs `R` (the law): `pad_axes` removes the over-closure (7/40 -> 0/40) but turns it into **V-blocks** (3/40 -> 13/40) because the arrival is 3.5-5.6 mm off-axis - the clean enclosure does not move (`logs/p131/RESULTS.md`) |
| a **candidate-planning / selector** change on the two-line (`select_target`'s lane rules, `_dynamic_select_floor`, the `FRUIT_GRADE_ROUTING` fallback, a prefetch/prepared/reservation path) | **the census first, offline**: `python3 logs/p99/census.py <cell>.log` + `python3 logs/p99/p99_report.py` read the per-slot wait split (park-gate / park-motion / feed / starved polls), the per-decision candidate set and the **convertible seconds per mechanism** (`FRUIT_BED_DIAG=2` + `FRUIT_BIARM_PARK_TRACE=1` on the census cell; prove the instrument neutral by replaying the same-seed record with its rows dropped - `census.py --same`, P99's `974/974` / `970/970`). **A wait is not a throughput number**: quote the interval, both rates and the arm split before calling one convertible, and read the *mechanism* columns, which are branch-free - `window <= 1` (a forced choice), the delay-aware headroom (0.000 s on the shipped two-line, so "take the nearest" is already shipped), `own-lane-empty-while-cross-lane-present`, and the park-gate time (the overlap's price, not a fruit wait). **A cross-lane rule is a sort error on this cell** (left = lane 0 = grade A, right = lane 1 = grade B, `run(state, bin_index)` places on the arm's own lane), so price it with `FRUIT_GRADE_ROUTING=0` and report the **grade-purity ledger**, never as a free lever - P99: starvation 37 -> 0, arrival wait 1.62 -> 0.67 s, **interval +6.8 % / +5.3 % at the two seeds**, window rate worse at both, 17/40 mis-sorted |
| a **scenario descriptor or a sort instruction** (`FRUIT_SCENARIO`, `FRUIT_SORT_INSTRUCTION`, `src/fruit_sorting/scenario.py`, `tasks._sort_admits`/`_place_xy_for`/`_calibrate_sort_destinations`, the `[sort]` rows) | `scripts/selfcheck.sh` (the `259`/`260` legs: the strict descriptor schema and its cached unset resolution, the shipped-path fallbacks in `tasks.py`, the descriptor's `SceneConfig`/`SupplyPlan` application and the scope refusals; then the instruction leg's grammar, precedence, unset resolver, capability map and every refusal); then **the unset replay first** - `scripts/accept.sh` must be 8/10 + `fingerprint: matches` with its `[fruit]` stream **byte-identical** to `logs/p110/accept_noharm.log` (P114: 421/421, no `[sort]`/`[scenario]` row); then **an instruction that restates today's routing** must replay the same stream with the `[sort]` rows dropped (`python3 logs/p114/p114_report.py --same`); then the ledger (`--ledger`) on the cell - **assignment accuracy is the endpoint, never the placed count** - and for a new destination mark it `reach: auto` (the startup solve prints `reachable`/`UNREACHABLE` at the 25 mm bar) and prove an unreachable mapping is **refused before the first attempt**, not mis-sorted (P114's tray: 1138.3 mm -> `ScenarioError`). A new **physical** lane/hand/camera is still a scene build; the descriptor only moves a target on an existing lane. **P115** adds the `261` leg (`and` terms, `FRUIT_SORT_STRICT`, the rule table, the `rule=` field): when a rule carries `and`, read the **per-rule histogram** (`python3 logs/p115/p115_report.py --ledger <log>`) so the decision names the rule, and use **`FRUIT_SORT_STRICT=1`** when a dropped fruit must be a startup refusal rather than a silent skip. **P116** adds the **offline plan/lint** (`scripts/262_sort_plan.py --instruction <file> [--strict-overlap]`): rule table with arms, **overlap pairs with the winning rule and an example fruit**, the partition over the 120-cell attribute space, and the cells that match no rule - run it **before** a new instruction, quote the partition and the overlap, and keep `--strict-overlap` green when the instruction must be a true partition (use `grade!=A`, `species!=apple` to write "the rest of the apples" without relying on order) |
| a **third output body** (`FRUIT_OUTPUT_LANES=3`, `SceneConfig.output_lane_layout`, `conveyor.OutputBelt`'s lane argument, `scene._add_output_belts`, `assets.output_tray_of`, `tasks._payload_clearance`/`_output_belt_edge_y`, the `scene.output_lanes` manifest key) | the **scene survey first** (`scripts/run.sh logs/p123/probe.py` section S, or `logs/p123/survey.txt`): the output deck's free space is `\|y\| 0..0.425` inboard and `> 0.675` outboard, and only `\|y\| 0.28-0.40 at x >= 0.48` is both reachable and clear of the place transits. Then the **offline layout** (`python3 logs/p123/layout.py`): the place point against P90's `NAT` box, the delivered point against the slab in sd, the **crossing of every other lane's inboard edge as a delta from the shipped crossing** (`d clr = d z`; the direct low lift loses 0.30 mm/mm inboard, a body **x-offset downstream** loses nothing), the body/tray/chute air gaps and the camera footprint. Then the **exact reach solve** (`scripts/run.sh logs/p123/probe.py` section R, both arms, both heights, the gate in `logs/p123/PREREG.md`); a cell that does not pass is a kill **before** the build. Then the build's own tests: `scripts/selfcheck.sh` (the `264` leg - the unset path reproduces every shipped scalar and the generalised belt/tray/discharge tests equal the pre-P123 expressions on a dense grid, the third lane's geometry, the delivered point >= 3 sd inside its slab, the body upstream of every transit and downstream of the fruit band, the tray census), and the manifest (`assets.scene_provenance(...)["output_lanes"]`, 2 entries shipped / 3 with the body). Then the **cell with its own same-seed control on the same tree**: the endpoints are the **tray census** (`[belt] ... discharged ... [tray N]`, joined to the `[sort] attempt idx=`) and the **ledger** (`in_destination`), never a target proximity; read `python3 logs/p123/p123_report.py --cells C T --check` (the guards: every payload-present release on a belt, `clr`/`clr_edge` > 0 on every held place leg, the descent budgets via `105 --min-success-rate 0`). **A scene change moves the collider set**, so an unset acceptance must be the no-harm gate (P123: 8/10 + `fingerprint: matches` + 421/421) and a count is a branch - two seeds here read -6 and +2. A flip owes both references, a re-based acceptance, every store re-baselined and the direct/policy interface measured. **P126 flipped the default to 3 and P127 reverted it**: the 20-attempt battery reads **44/80 on three lanes against 58/80 on two, 4/4 seeds worse** - the scene's collider set re-draws every grasp (P71), so **a scene flip is carried by the 20-attempt battery with same-seed controls**, not by the acceptance (one attempt's 7 vs 8 hid -17.5 points), the tray census (it proves the destination) or the canary (an interface check). |
| a **pad-material / friction** claim (`FRUIT_FINGER_MU`, `FRUIT_CAGE_PAD_MU`, a `mu_pair` target, a "slippery pad" or "no-slip pad" idea, a creep/break-away number) | **the algebra first** (`python3 logs/p129/algebra.py`): the four-pad residual is `mu s`, the four-*contact* state is a stiffness **window** `[0.5/(s(1-mu)), cap/(s(1+mu))]` which is empty above `mu = 0.815` per fruit and `0.613` pool-wide, and capture from an offset needs `mu < cap/(2 k s)` (the condition a **rigid** close fails at any mu) - so say which one you mean. Then **the pair itself** (`logs/p129/fixture_pinch.py` A0: a flat cube between two pads, `mu = F/(sum N)`; the authored `pad_mu = 2t - mu_payload` delivers the pair to +0.02) - never quote a pad's authored mu as the pair. Then the **creep on the load axis** (P117's `dz`), never the total (a mu-invariant seat shift: 8.5-12.4 mm at every mu), and the **retention** (at pair <= 0.8 the 34-37 mm fruits are ejected at P117's 5 mm seat, 12/12 cells). For a **ring's centring** use `logs/p129/fixture_ring.py`: the payload must be the algebra's 2-D case (a **square prism**; a sphere slides in friction-free because its surface leaves the 26 mm plate beyond `delta ~ 9 mm`), and the **protocol is a cell variable** - a full close is clean 8/8 at every pair 0.6-1.35, while the line's first-contact freeze is 3/8 at the control and does not improve with mu. **A `mu < 1` pad is not the ring's lever** (`logs/p129/RESULTS.md`); the freeze is, and its cell is named there. |
| a **new destination or output lane** (a third tray, a zone on an existing belt, a "put it in box 3") | the **spacing spec first** (`logs/p122/SPEC.md`, `python3 logs/p122/spacing.py`): a destination is a **physical output body** (belt + chute + tray - the cell has two, one tray per belt), so a target on an existing belt is the **same** destination, not a third. If zones must share a body, attribution needs the **calibrated** offset (**+48 mm x, +-35..37 mm y**), then **x >= 50 mm** (0/20 000; 30-40 mm is 1.5 %) - **never uncalibrated** (50 mm reads 33 % wrong) and **never a (50,50) diagonal** (2.1 %; P121's 1/23). A real third needs the **place reach** (P90: x 0.38-0.48, |y| 0.35-0.55) and a **station solve**, and it owes both references + every store |
| a **direct/policy instruction route** (`rl_env.direct_dispatch`, `_sort_armed`, the `_begin_pick`/`_run_primitive` wiring, `tasks.dispatch_destination`/`sort_ledger_attempt`/`arm_for_destination`, `FRUIT_SORT_THIRD_DEST`, the manifest's `sort` block) | `scripts/selfcheck.sh` (the `263` leg: the dispatch table - unset **is** the shipped `grade A -> 0/left, else 1/right` expression, today's routing, a non-grade rule, `skip`/unmatched refused - the goal-channel OOD gate, the capability map incl. the unreachable tray, `_begin_pick`'s goal channel, `_run_primitive`'s thread-local place target + `finally` cleanup + ledger, the 7+1 action, and the manifest block); then the **direct cells**: an un-instructed control and an instructed arm on the **same seeds**, `logs/p121/p121_report.py --check` on their logs (the endpoint is the ledger's `in_destination/released` and the per-destination table; the placed count is a branch draw, never a rate), and a third destination only with `FRUIT_SORT_THIRD_DEST=1` + its own descriptor - a third target 71 mm from lane 0 was **reachable but not separable** under the line's 40-70 mm release scatter (1/23 mis-sort), so check the separation before promising it; then `scripts/accept.sh` as the no-harm proof (the scripted path never reads `direct_dispatch`) |
| the **single-arm (Franka Panda + two side bins) cell**, or a shared path it rides (`tasks.py`'s close/catch/place, `_pad_standoff`, the instruction ledger) | `scripts/283_single_arm_gate.sh [attempts] [seed] [floor]` - it runs the cell (`FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0`), prints the per-attempt table and the last `[cycle]`, and exits non-zero below the floor (default 0.80: one loss in six, the two-line gate's convention for a cell whose measured count is 96 %). With `FRUIT_SORT_INSTRUCTION`/`FRUIT_SCENARIO` exported it also requires the ledger to be **clean** (`in_destination == released`, `mis_sorted == 0`) - the bins cell's endpoint is the assignment accuracy, scored at the **settle** sample for a bin and at the release for a belt. Measured arms: seed 5 **6/6**, seed 6 **6/6**, and the size rule at seed 202 **5/5 with 5/5 in_destination**; then `scripts/accept.sh` for the shipped cells (the cell shares `tasks.py`, so its no-harm is the acceptance's 458/458 stream) |
| the bimanual scheduler (`bimanual.py`, or the task loop under `FRUIT_BIARM=1`) | `scripts/selfcheck.sh` (the 152 leg), the rate batch (`scripts/153_biarm_rates.sh two-line 5`; `shared` and `single` are the other two modes), then `scripts/accept.sh` (it gates whatever session it ran) |
| the **shipped scheduler default** (`bimanual.resolve_biarm`/`resolve_twoline`, `tasks.bimanual_enabled`/`two_line_enabled`, the supply package's `two_line=` scope, `scripts/accept.sh`'s gate branch) | `scripts/selfcheck.sh` (the `246` leg: the resolver table, the session scope, the entry wiring, the manifest keys, the accept branch), then **both restores** - `FRUIT_BIARM=0` at ten attempts against `configs/motion_reference_single.json` and a `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0` smoke - then a 20-attempt default rate run compared line-for-line with the pre-flip record (drop only `[fruit] [carry]`, `[fruit] [diag] carry-assist` and the `[biarm] scheduler:` banner; `logs/p85/p85_report.py --same-with-diag`, template `logs/p85/RESULTS.md`), then `scripts/accept.sh` and `scripts/demo_2min.sh` |
| the arbiter / main-thread bridge (`bimanual.py` `TickRelay`, `MainBridge`, `CoopSession`), or anything that claims a **wall** speedup on the two-line | `scripts/selfcheck.sh` (the 152 leg), then **the same cell twice** (knob unset vs set) with `logs/p80/stamp.py` and require the `[fruit]` stream to be **byte-identical** (`python3 logs/p82/p82_report.py --same <control.log> <cell.log>`) - a scheduler change must not move the physics - plus `scripts/190_twoline_gate.sh` on the cell (its own reference for its own attempt count) and one `FRUIT_BIARM=1` pair for the shared-station consumer; read the wall with `logs/p82/p82_ab.py` and quote **wall/sim**, `wall/pick` and `placed/min wall` against the single arm at **>= 2 seeds** (`logs/p82/RESULTS.md` §4-§6). The arbiter's idle is measured by `logs/p82/timers.py`; do not add per-tick timers to `ik_step` (AGENTS §2) |
| the policy, training or the dataset schema | `scripts/selfcheck.sh`, `scripts/accept.sh` (scripted baseline), `scripts/accept_policy.sh` (policy loop) |
| the direct supply profile (`rl_env.py` `_resolve_supply_profile`, the `fruits.py`/`tasks.py` kwargs) | `scripts/selfcheck.sh` (the `230` leg), `scripts/accept.sh` (import guard: 377/377 + `fingerprint: matches`), one two-line run + `scripts/190_twoline_gate.sh`, `python3 scripts/211_bed_audit.py` |
| a **place-station move** (`assets.py` `output_place_x/y`, `output_place_clearance`) | the map **first**, offline: `bash logs/p90/run_p90.sh` (the 588-cell `T0`/`NAT`/`C0` sweep over +-0.15 m at 1.450 and 1.530, both arms, ~47 min) and `python3 logs/p90/cost_map.py --check` - **the shipped point is at the corner of the solvable box** and the `NAT` best-solved tilt there is already 77.75 deg, so a candidate must beat that or there is nothing to buy; then the `238` leg, `scripts/accept.sh` (the branch moves by construction - the release point is in the camera's frame), one two-line run + `scripts/190_twoline_gate.sh`, and **every store re-baselined** (`logs/p90/COST.md` §6) |
| the output station (`assets.py` `output_rails` / `output_belt_top_z`, `conveyor.OutputBelt`) | `scripts/selfcheck.sh` (the `238` leg), `scripts/accept.sh`, one two-line run + `scripts/190_twoline_gate.sh`, then the direct cell with `FRUIT_CARRY_DIAG=1` (the crossing `clr`/`clr_win` **and the P72 corner `clr_edge`/`clr_edge_min`** per held place leg, read with `logs/p72/p72_report.py --check`) - and re-record both references if the flip is shipped (`logs/p71/RESULTS.md` §5) |
| the scene's collider set or a store's provenance (`assets.scene_provenance`, the manifests) | `scripts/selfcheck.sh` (the `239` leg), then one collection or direct run and check its `manifest.json` carries the `scene` block (`logs/p72/manifest_probe.py` does it without a simulator app) |
| a store's **supply** provenance (`assets.supply_provenance`, the `supply.band` key in both manifests) | `scripts/selfcheck.sh` (the `239` leg's section 6: the builder's signature and arithmetic, all four branch orders, the `SupplyPlan` field set read from the dataclass's own AST, one call site per writer), then one collection or direct run and check its `manifest.json` carries `supply.band.x_min`/`x_max`/`grades`/`schedule` - **a manifest without it predates P93**, and the collector's flat `supply.x_min`/`x_max` are then the witness (`logs/p93/RESULTS.md` §6) |
| a new default-off diagnostic field on the `[carry]` row (or a new `[place]`/`[seat]` line, or a new `[place-trace]` per-tick print) | `scripts/selfcheck.sh` (the field's own leg - `235`/`239`/`240`/`241` are the pattern), then **one direct run with `FRUIT_CARRY_DIAG=1`** to read it, then `scripts/accept.sh` and require its **346/346 `[fruit]` lines** to be byte-identical to the pre-change record - a diag-only change must be inert on the scripted path (`logs/p73/P1_RESULTS.md` §5, `logs/p75/RESULTS.md` §5) |
| a **per-tick fruit instrument** or an **acquisition-disturbance claim** (where an incoming fruit's velocity/spin comes from: `FRUIT_FRUIT_TRACE`, the `[ftrace]` rows, a pre-leg pad contact) | `scripts/selfcheck.sh` (the `252` leg: the switch table, the one `_step_sim` hook and that it is *not* in `ik_step`, the fruit-only default path, the no-op arm returning before any read, the single arming/disarm/flush sites, the executed row shape, the 0.15 m neighbour filter, the arm gate), then **the neutrality proof before the claim**: run the fruit-only cell and require its `[fruit]` stream to be **byte-identical** to the same-seed record (`python3 logs/p95/probe.py --same <cell> <record>`; P95: 970/970 and 974/974), and only then add `FRUIT_FRUIT_TRACE_ARM=1` - and re-prove that cell too, because a *narrow* link read (3 prims/arm) is inert while the wide sweep is not. Read the attribution with `python3 logs/p95/probe.py`: a **contact** is `pad gap <= 6 mm` **and** that hand's measured span swing `>= 2 mm` within +-4 ticks - the span is the verdict (the finger drive is stiffness-limited to 0.1 mm, so a displaced span cannot be commanded) and the gap is a +-5 mm indicator (the plates are angled at a 98 mm span). The leg's start is `first_descent_tick - [motion] approach steps=`, never the `descent` label (`_cycle_mark("descent")` fires *after* `_approach`) |
| a **reactive slip lever** (`FRUIT_SLIP_REGRIP`, the `[regrip]` rows, `logs/p103/p103_report.py`, a mid-carry re-seat, or a claim that a tactile reflex converts `cnp`) | `scripts/selfcheck.sh` (the `256` leg: the resolver and its 1 mm floor, the `False` default flag, the `guard_armed` term, the trigger's four terms in the registered order - P102's seat, the threshold, the shipped abort ceiling, and **no** cooldown or per-leg cap - the `[regrip]` branch using the **same six expressions** as the shipped `slip_enabled` block with **no `ik_step` and no `_step_sim`**, the two-line session scope, and both row grammars through the report's own readers), then **the off-path replay first** (`--same` on the acceptance and on the batch's own controls - P103: 419/419, 825/825, 837/837), then **four seeds, two fresh**, with `FRUIT_CARRY_DIAG=1` **and** `FRUIT_PLACE_TRACE=1` on **both** arms (P83's G2 shape - the instrumentation must be in both arms or the A/B is the instrumentation), and read it in **this order**: the `[regrip]` **ledger**, the **conversions** on the **same-instance** pairs (`p103_report.py conv` - an unpaired row is a branch, not a conversion), the class counts, the interval on **both denominators + the wall**, then the guards. **Do not price a reactive lever by its clock**: P103's action costs **0 ticks** and still moved the delivered interval **+15.3 %**, because the reaction's failures re-draw the slot loop - and it **destroyed 2 of 2 placements it touched** on the false-positive class, so a lever that fires on a slide the pinch would survive is a *harm*, not a no-op (P102's "2 of 60 held legs, both placed" was measured **without acting**). And check the ceiling first: a two-line attempt whose lift leg reads `clean_slip_max >= FRUIT_CARRY_MONITOR_CONFIRM_MM` (**8.0 mm**, the P10-C monitor, armed by default in a two-line session) is truncated at the leg boundary, so **a reaction that cannot hold under 8 mm cannot convert however well it holds the pinch** (`logs/p103/RESULTS.md` §6) |
| the finger drive's force cap, or a leg-scoped drive write (`FRUIT_FINGER_MAXFORCE`, `FRUIT_FINGER_MAXFORCE_SCOPE=place-left|grasp-left`/`..._SCOPED`, `tasks.finger_cap_scope_for`, `_carry`'s wrapper) | `scripts/selfcheck.sh` (the `244` leg), then **one direct run with `FRUIT_CARRY_DIAG=1`** and read the `[drive] ... finger cap raise/restore` rows **and** the delivered force by leg class - **the site proof is the pair**: `place-left` -> `place*` at the scoped cap with `grasp_lift` at ~9.7 N (`logs/p78/RESULTS.md` §0), `grasp-left` -> `grasp_lift` at the scoped cap with `place*` at ~10 N (`logs/p79/RESULTS.md` §1); then `scripts/accept.sh` + one two-line run + `scripts/190_twoline_gate.sh` **with the knob armed** and require **346/346 `[fruit]` lines + both fingerprints** to be unmoved (`logs/p78/RESULTS.md` §7, `logs/p79/RESULTS.md` §6) - the scoped form must move no reference; a **global** `FRUIT_FINGER_MAXFORCE` instead owes both references and every store. Read `fmax` as a **peak transient** that exceeds the cap on single legs even at 10 N, and `force_min` as the leg's weakest moment - neither is a `place*`-was-re-clamped test on one cell (`logs/p79/PREREG.md` §9 A1); the structural rows are. **A global 60 N on the shipped two-line was a measured draw** (P120: a four-seed screen read 66/80 against 58/80, p = 0.18, but the pre-registered replication at 303/404 read 31/40 against 32/40, p = 1.0, and the six-seed pool 97/120 against 90/120, p = 0.35) - **the shipped 10 N stays** (owner decision); do not re-run the global cap without a new mechanism |
| a **carry-command** change (the `_gripper_offset` reading or its use, `FRUIT_CARRY_OFFSET_MAX`, `_carry`'s assisted-branch target, the `hand_is_jaw` fallback) | `scripts/selfcheck.sh` (the `251` leg: the resolver table, **one** site, the jaw-hand scope, the two branch expressions **executed** - inside the bound the command is `centre - rot @ offset` bit for bit, above it `centre`, and the kinematic-pad hand keeps its offset at any magnitude - and the diag row printing the **issued** target so the census reads the applied jump with no new field), then the **jump census first**: `python3 logs/p94/census.py` on the control records (the reading `|_gripper_offset|` per leg and the applied jump `|jaw_target - cmd_centre|`) - a reading above the bound is the defect class, and a leg **below** it must not move (F1); then the four-seed battery with the `logs/p94/run_p94.sh` shape and the **prefix identity** (`python3 logs/p94/p94_report.py --same`) - a treatment cell must equal its same-seed control's `[fruit]` stream up to the **first guarded row**, and the seeds the guard cannot act on must replay **end to end** (P94: 970/970, 1001/1001, 986/986); then `scripts/accept.sh` **twice** - `FRUIT_CARRY_OFFSET_MAX=0` and unset - with `FRUIT_CARRY_DIAG=1` on both, requiring the `=0` arm to reproduce the recorded reference and the unset arm to differ first at the guarded row; the single arm (`FRUIT_BIARM=0`, 346/346) is the other half of guard (e). A change that moves **every** leg (the unconditional `hand_is_jaw` form) is a re-calibration, not a fix: it owes a full four-seed battery, both references and every store, and cannot be attributed on a 20-attempt cell (`logs/p94/RESULTS.md` §8-§9) |
| an **early end of a carry leg** (a new skip/trip on `_carry_monitor_skip`/`_fail_fast_trip`, a new threshold, `_attempt_ended_early`, or a new failure path out of `_grasp_carry_place_impl`) | `scripts/selfcheck.sh` (the `245` leg is the pattern: the resolver table, the refuse-below floor, **one** trip site, the attempt-local latch, the scope, the arming clause, and that the trip adds **no `result.notes` entry**), then **the tracker-only control first**: `FRUIT_CARRY_DIAG=1` alone on the same seed must be **byte-identical** to the shipped run (`--same`, diag rows dropped) - otherwise the treatment differs by instrumentation and no time claim is admissible (`logs/p83/RESULTS.md` §6 G2) - then the A/B against **that** control on **>= 2 seeds**, reading **the failed attempt's own span** as the mechanism number (branch-free) and the interval/count as the claim, plus `scripts/accept.sh` and require its `[fruit]` stream to be byte-identical to the pre-change record |
| a **two-line pre-pose** change (the clearance pose: `prepose_clear_resolution`, `_prepare_two_line_stations`' solve, `FRUIT_BIARM_PREPOSE_CLEAR[_Z|_HOLD]`, the `[biarm] pre-pose` row, `collection.prepose_clear`) | `scripts/selfcheck.sh` (the `253` leg: the resolver table - unset/no-session `scope-off`, unset/two-line the scoped default, `=0` the pre-P96 path, `=1` on, the band raising outside `[0.155, 0.25]` - the **height arithmetic** (`jaw_achieved = target - residual`, so a P95-floor target achieves *below* the floor), the one solve site with the **pick-point skip bypassed**, both hold forms, the **gated print** (the pre-P96 path adds no line) and the three manifest keys), then **the offline map before any battery**: `bash logs/p96/run_p96.sh`'s battery is only owed if a station admits the pose - `scripts/run.sh logs/p96/prepose_map.py` + `prepose_check.py` (the depth ladder, `T0`/`C0`/`NAT`/`CFG`, the joint margin and the authored **pad bodies' lowest point**), and a station that does not admit it means the transit/park bias or the station geometry, with **no battery spent** (P96 PREREG F1); then the four-cell A/B (`C5`/`T5`/`C6`/`T6`, 20 attempts, **identical instrumentation** so the census, the count, the interval and the landing come from one cell each) with `python3 logs/p96/pg_census.py` (**the primary endpoint**: P95's contact = `pad gap <= 6 mm` **and** the other hand's span swing `>= 2 mm`; the gap alone cannot reach 0 - its floor is the fixed 31 mm proxy radius), `python3 logs/p96/p96_report.py`, `bash logs/p96/gates.sh` (**G0** the control cells byte-identical to their own record with the phase's `[ftrace]` + the sealed diag rows dropped; **G5** budgets-only for the treatments, and a control's over-budget leg must equal its record's) and `scripts/accept.sh` with the knob **unset** (it must be inert: 419/419 + `fingerprint: matches`). Expect **no** cell to replay if the lever moves the pre-pose on every attempt: the treatment is its own branch, the **control** is what proves the instrumentation neutral (`logs/p96/RESULTS.md` §0/§7) |
| a **two-line A/B** (a per-attempt knob on the scripted primitive reaching `run_bimanual`, e.g. `FRUIT_FAIL_FAST`) | the same protocol, with four two-line differences: (a) the control must replay **that scenario's own** record modulo the phase's diag rows (`logs/p82/p82_report.py --same`, dropping `[fruit] [carry]`, `[diag] carry-assist` and `[biarm] … park`) - P84's `D5`/`D6` are `logs/p80/{T20,T6}.log` at **865/865** and **814/814**; (b) **each seed is its own scenario**, so every seed needs its **own** 20-attempt reference (P80's file is seed 5; write another seed's from its own record into `logs/`, **never** `configs/`), and the treatment is a **DIFFERS-by-construction** arm gated on **budgets only** (`105 --min-success-rate 0.0`); (c) the interval is split over two overlapping arms, so quote the pooled **and** per-arm interval, both denominators, the wall and the **park-gate wait / lock-on / idle** triple - the "the overlap absorbs the abort" read; (d) the saving must be quoted **by class**: the shipped two-line already truncates a lost attempt twice (the `not result.grasped` return after the lift and the **P10-C monitor**, armed by default in a two-line session), so the fail-fast increment is ~1.2-1.5 s on a never-grasped attempt and ~3.3 s on a `cnp`, not P83's 5.14 s - and a 20-attempt two-line count is a branch draw whose **own control swings 16 -> 10** between seeds (`logs/p84/RESULTS.md` §2/§4) |

To compare two **policy** arms, use the harness rather than two runs:

```bash
EPISODES=12 RUNS=3 scripts/140_policy_ab.sh          # ARM_A / ARM_B are env assignments
```

It runs each arm N times back to back in one session with a seeded sampler, then
reports the per-episode outcomes per arm, the per-class rates, and whether the arms'
ranges overlap (`scripts/141_policy_ab_report.py`). Aggregate the *outcome* per
episode; a continuous quantity such as peak lift varies run to run even when every
episode succeeds.

Two cautions from its first uses. **Instrumentation is part of the measurement**: the
closure diagnostic changes the outcome (arm A scored 92 % with it off and 67 % with it
on), so compare arms inside one instrumented batch and quote a rate together with how
it was measured. And `AB_EXTRA_ENV="FRUIT_CLOSURE_DEBUG=1"` is the way to get the
mechanism (the grip geometry) from the same runs that give the rates - which is how the
extent-close question was settled.

## 3b. How to run a comparison that means something

**A single run is a measurement again, but only because of a fix - keep it.** The
same command used to land its fruit at 8.5 cm from the pick point on one run and
8.7 cm on the next, because `app_utils.update_app(steps=N)` is not a fixed step (sixty
calls advanced 118 ticks on one run and 120 on the next). `FRUIT_FIXED_STEPPING`
(default on) routes every scripted advance through `SimulationManager.step`, and with
it five probes and three acceptance runs came out bit-identical
(WORKLOG: "found it: `update_app` is not a fixed step"). Two rules follow:

* **never add a new `app_utils.update_app(steps=...)` to a scripted path** - it
  silently reintroduces the non-determinism; step the physics explicitly instead;
* **but do not drop the pump either.** `update_app` also services the camera and
  sensor callbacks, so `SimulationManager.step` alone starves them (it crashed the
  evaluator with an empty frame). `advance()` in the two entry scripts does
  `SimulationManager.step(steps)` and then `app_utils.update_app(steps=0)`, and the
  evaluator calls `RenderingManager.render()` before reading the camera;
* **the policy loop is still not reproducible** even with all of that: seeding
  `FRUIT_POLICY_SEED` removes the unseeded `torch.randn` in DDIM sampling, and two
  runs still differed (6/6 vs 5/6). The remaining candidate is the rendered frames
  the policy conditions on - since confirmed: with constant frames three runs are
  bit-identical, with real frames they are not, and disabling TAA/DLSS does not help
  (the variance is in RTX rendering itself). So **a policy A/B needs N per arm**, and
  aggregate the *outcome* per episode rather than a continuous quantity like peak
  lift, which varies even when every episode succeeds;
* anything measured **before** that fix was measured on an arbitrary branch, so for
  old data compare distributions rather than single runs. For new data:

1. **Probe the branch first**, then run both arms in the same stretch and probe
   again afterwards; discard the comparison if the branch changed:

   ```bash
   ATTEMPTS=1 FRUIT_MOTION_REPORT=1 scripts/run.sh scripts/20_pick_place.py \
     | grep -oE 'approach\(cartesian\): [0-9.]+ cm, [0-9]+ samples' | head -1
   # 8.5 cm / 328 ticks and 8.7 cm / 334 ticks are two different branches;
   # a run of the other branch is a different scenario, not a repeat.
   ```

2. **Or compare distributions**, at least five runs per arm, quoting median and
   range rather than a pair of numbers (`scripts/108_fruit_size_probe.py --contrast`
   rank-sums one log; run it per arm and compare the summaries).
3. **Prefer per-leg motion metrics and direct mechanism measurements** over success
   counts. The closure interference and the IK push signature are read off the
   grasp or the leg itself and do not depend on which branch a run took.

## 4. Where the reasoning lives

`WORKLOG.md` is append-only, and every claim above has an entry there. Section
headings, quoted verbatim so they can be grepped:

* **the two constraints of section 2:**
  `### The outcome is quantized, and that changes how the A/Bs must be read`
  `### Correction: it is the arm-link readback, not reads in general`
* **what the motion work found, negatives included:**
  `### The descent's "roughness" is one IK command, not the trajectory`
  `### Catching the lurch: a kinematic hand collider inside the arm`
* **the collector/merge bugs:**
  `### The dataset index did not match the dataset`
  `### Both fixes now have a regression test that fails on purpose`
* **which figures are re-checkable and which are history:**
  `### Documentation audit: every motion number, and whether it can be re-checked`
  `### Same audit, policy and data side`

Report-ready summaries are in `项目总结报告.md` (Chinese) and `README.md`; route
trade-offs are in `决策与交付.md`; design-intent vs actual is in
`实现方案总结.md`. When a number changes, update those *and* the log entry that
justifies it.

The long-form plan is `docs/ROADMAP.md` (the current state in one screen, the
backlog grouped into WS-1..WS-7, the phases R0-R9, the resource budget and the
owner-decision register); the periodic ops self-check and its anti-stall
playbook are in `docs/OPS.md` - run `scripts/191_ops_selfcheck.sh` (verdicts
OK / STALLED / ACTION), at the start and end of every work block and every
30-60 min while a simulator phase is active.
