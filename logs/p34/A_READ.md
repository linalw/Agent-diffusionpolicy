# P34 phase 2 — the reset alignment A/B (the first-view lever)

Measured 2026-10-23 on the P33/P34 tree (P33 close-out `b486719`; the pre-A/B
pins `logs/p34/60_ab_tree_md5_before.txt`), **default off, no shipped default
changed**; committed as the P34 record. Pre-registration: `logs/p34/PREREG.md`
(written before the batch). Phase 1 (the occlusion map) is `logs/p34/REPORT.md`
+ `README.md`. All Gate-2 corrections are applied; the ambiguous ones are
itemised in section 6b.

The one-line answer: **aiming the first call at 0.399 with the reset pose does
not move the left, and the visible-first-view hypothesis is untested.** The
manipulation check passes on the aligned arm at 96 % and fails on the control at
12 %, so the knob does what it says - but it moves the fruit's *along*, not its
visibility: the **rendered** target mask is empty at the first call in **A 72/75
and B 71/75** episodes, because the **left arm** occludes that view
(`openarm_left_link3` fills the target's projected bbox, 127 px vs the fruit's
16 at +0.399). A treatment that never presents a visible first view cannot test
whether a visible first view helps; the A/B compares two arm-occluded first
calls. What it does show is that the fruit's along is not the lever: the left's
paired carried class does not convert (0 B-only / 1 A-only, p = 1.0), and the
left's unpaired moves are 1-3 episodes.

## 1. The question and the manipulation check

Phase 1 measured a train/eval mismatch at the direct env's first observation:
the demos' first-detected target sits at along **+0.399 m** (p50,
`20_demos.json`; the **two-line** stores - the single-arm store reads +0.441,
see sections 4/6), while the shipped direct reset presents the target at
**+0.583** and the model's first call then meets it at **+0.455..+0.551** (the
P31 anatomy) — the +Y output belt's fully-hidden band is +0.515..+0.870. The
lever aligned the **first model call** to the demos' +0.399. Note the direction:
0.399 is **42 mm downstream** of the single-arm store's first view (+0.441
p50) — later in the fruit's travel, not earlier — and the two A/B arms' first
calls (+0.484 / +0.398) **bracket** that store first view.

The pre-registered manipulation check (per episode): the first call's
`along = fruit.y - _expert_jaw_y` within **0.399 +- 0.02 m** **and** the
analytic visible fraction of `scripts/212_occlusion_map.py` at that
`(x, along, diameter)` **>= 0.90**; the aligned arm passes if >= 90 % of its
pooled episodes and >= 12/15 in each run. The A/B tests the hypothesis only if
the check passes (a failure would be an implementation failure) - and the
check's second leg is **analytic** (the belt alone): the rendered target-mask
cross-check is what says whether the first view was actually visible, and it is
empty on both arms (sections 3/4), so **passing the check does not establish
that the treatment presented a visible view.**

## 2. The implementation (default off)

`src/fruit_sorting/rl_env.py` only (188 inserted lines, 0 deleted at the batch's
pin `2e392f48`), direct presentation only. The committed file also carries the
**P34-B** follow-on (`FRUIT_RESET_SETTLE`, default 20 = the shipped
`advance(20)`, plus the `[align]` row's `settle`/`q_r`/`q_f` fields), so
`git diff HEAD` at the commit reads **216/1**, not 188/0; the settle knob is
default-identical and is not part of this A/B's arms.

* `FRUIT_RESET_ALIGN=1` (default 0): after the reset's own setup (the arm
  teleport to the calibrated grasp pose, `advance(20)`, `belt.start()`), advance
  the line tick-by-tick with the control loop's own pair (`advance(1)` +
  `spawner.enforce_transport()`) until the target's along is
  `0.399 + belt_speed * execute_steps / 120 = 0.403`; the **first model call**
  is `execute_steps` (=4) control ticks later, at 0.399. `FRUIT_RESET_ALIGN_ALONG`
  (0.399) and `FRUIT_RESET_ALIGN_MAX_TICKS` (600) override. No feeder `update`
  (the release schedule is not advanced), no arm command change (the arm holds
  the grasp pose, like the demos' wait loop), and the advance is before
  `_episode_t0`, so the attempt's own span excludes it.
* `FRUIT_RESET_ALIGN_DIAG=1` (default 0, both A/B arms): one `[align]` row per
  episode — the selection `y0`, the reset-return along, the alignment ticks, the
  first call's along/x/diameter and target-mask pixels, the first visible call
  and the hidden-call count, the fire-zone mask counters, and the model calls.
  Pure reporting (one fruit-pose read and a sum over the already-read mask).
* The manifest records `reset_align` (on/along/max_ticks/diag; `null` when off).
* **Byte-inertness**: with the knob unset the shipped path gains one False
  branch in `reset`, one in `sample_chunk` and one in `_finalize`, and reads
  nothing; `TASKS_MD5` and the scripted `[fruit]` stream are untouched.

The 4-tick pricing was validated by the `[align]` rows: the reset-return ->
first-call travel is **4.0 mm in every episode of both arms** (the measured
1.000 mm/tick belt slope, P31).

## 3. The A/B

**The batch.** 10 runs x 15 episodes (5 per arm), interleaved A,B,... in one
`154_claim_run.sh` claim (18:31-19:41). The driver's exit 1 is
`scripts/113_rl_report.py`'s negative verdict, not a missing run: every
`A_N/B_N` log has 15/15 episodes (150 total). The two arms are the same
checkpoint (`moe_v13s` `61da390a`) and the same scenario (the P33 W8-A patch
sheet + arrival trigger + ACQ); the only per-arm environment is
`FRUIT_RESET_ALIGN=1` on B. `FRUIT_RESET_ALIGN_DIAG=1` (and the P33 batch's
`FRUIT_ACQ_DIAG=1`) on **both** arms.

**The manipulation check (PREREG section 2).**

| | A (control) | B (aligned) |
| --- | --- | --- |
| first-call along p50 (p10..p90) | +0.484 (+0.405..+0.557) | +0.398 (+0.398..+0.399) |
| 212 visible fraction p50 (min) | 0.41 (0.00) | 1.00 (1.00) |
| **PASS** (\|along-0.399\| <= 0.02 and vis >= 0.90) | **9/75 = 12 %** | **72/75 = 96 %** |
| per run (of 15) | 2 / 0 / 3 / 0 / 4 | 15 / 14 / 15 / 14 / 14 |
| reset-return along p50 | +0.488 | +0.402 |
| alignment steps p50 (max) | 0 | 88 (193) |
| reset -> first-call travel | 4.0 mm every episode | 4.0 mm every episode |

The 3 B misses are the target already below the window at the reset return
(along +0.360/+0.372/+0.376, the selection floor's edge), so the loop cannot
advance; their 212 visible fraction is still 1.00. **The manipulation check
passes** (>= 90 % pooled and >= 12/15 in each run). It is a check on the
**fruit's along** and its **analytic belt-only** visibility - not on the rendered
first view: the cross-check mask is empty at the first call on **both** arms
(the last paragraph of this section), so the visible-first-view hypothesis is
untested.

**The outcomes.**

| | A (control) | B (aligned) |
| --- | --- | --- |
| pooled placed | 20/75 (27 %) | 23/75 (31 %) |
| left: n / placed / no-grasp / carried | 29 / 1 / 4 / 24 | 27 / 2 / 1 / 24 |
| right: n / placed / no-grasp / carried | 46 / 19 / 3 / 24 | 48 / 21 / 1 / 26 |
| cycle ticks p50 | 1859 | 1800 (-3.2 %) |
| model calls per attempt p50 | 60 | 44 (-27 %) |
| same-fruit pairs, pooled | 27 pairs, 48 excluded | B-only 2 / A-only 3 (p = 0.8125); carried->ok 2 / 3 |
| same-fruit pairs, left | 9 pairs, 20 excluded | B-only 0 / A-only 1; carried->ok 0 / 1 |

Two-sided Fisher on the unpaired counts: left no-grasp 4/29 vs 1/27 **p = 0.35**;
left placed 1/29 vs 2/27 **p = 0.60**; left carried 24/29 vs 24/27 **p = 0.71**;
pooled 20/75 vs 23/75 **p = 0.72**. None is significant and the paired left does
not favor B. The left's carried count is **24 in both arms, but that is a count,
not a set**: of the 9 paired left episodes the members moved - 6
carried->carried, 1 ok->carried, 1 no-grasp->carried, 1 no-grasp->no-grasp (the
pooled transition matrix also carries the single carried->no-grasp, which is not
a left pair). The two pairing rules agree in direction and neither is
significant: the pre-registered key (run, episode, species, arm; see the
tolerance note below) reads 2 B-only / 3 A-only, **p = 0.8125** (27 pairs, 48
excluded), and the pinned `A_pairs.py` species-only key reads 3 B-only / 4
A-only, **p = 0.7734** (43 excluded). The left's own pairing is 0 B-only / 1
A-only, **p = 1.0** - the 0.81 is the **pooled** read, not the left's. The
pairing's diameter tolerance is **0.05 m** (`align_report.py`; the docstring
said 0.5 mm and is corrected), but every retained pair matched exactly at the
store's 0.1 mm resolution, so the guard is inert on this batch.

The pre-registered decision rule is **ambiguous on this outcome**, and the
honest read is the primary: the left's paired carried class does not move, the
left's placed count is up by one and the composite failure mass (carried +
no-grasp) is down by three (28 -> 25) - all 1-3 episode moves, non-significant.
The script's own verdict line (`A_align.txt`) is the middle branch, "no measured
improvement of the primary endpoint", which fired on `placed up or mass down`;
that clause was pre-registered as a **relocation guard** (PREREG section 4: "so
a class *relocation* (carried -> no-grasp) cannot pass"), not as a win
condition, so it is not a positive result. The third bullet (the pure falsifier)
requires *no* left placed gain and *no* composite reduction, which is literally
not the case. Neither the positive nor the falsifier bullet is met cleanly; what
is met is the primary.

**The first-view run (the phase-1 correction's measurement).** The control's
first call is at p50 +0.484; the analytic fully-hidden (212 vis<0.01) share at
the first *call* is **26/75 = 35 %** (not the reset's 88-90 %); the model's
fully-hidden calls are p50 **0** (p90 11) and its calls to full visibility
(vis>0.99) p50 **8** (p90 25). The phase-1 "33 model calls" is the
reset-to-full-visibility *travel*; the reset's own ~0.10 m of it carries **no**
model call (the first call comes after the second frame at control step 4).

The **rendered** target mask at the first call is empty in **72/75 (A) and
71/75 (B)** episodes. That is not the belt: among the episodes whose first call
is **belt-clear** (212 vis >= 0.90), the mask is empty in **25/26 (A) and 71/75
(B)**. The probe (section 4) names the occluder: the **left arm's
`openarm_left_link3`** fills the target's projected bbox (127 px against the
fruit's 16 px at +0.399). So the alignment removes the *belt* occlusion from
the first call (212 0.41 -> 1.00) but **not the rendered first view**: the
policy's first observation is arm-occluded in ~96 % of episodes on **both**
arms. **That is the Gate-2 restatement of the conclusion: the treatment did not
present a visible first view, so this A/B does not measure whether a visible
first view would help.** The first-view mismatch phase 1 diagnosed is real, but
its occluder at the aligned position is the arm; the belt is only the
control's occluder, and the arm is present on both arms.

One separate, smaller pipeline finding: in the probe the **step-0** observation
(the reset's frame 0) also has an empty target mask, and its projected bbox's
pixels are the main belt - i.e. the first `instance_id_segmentation` read after
the reset returns the *pre-reset* frame (the same one-frame staleness the
phase-1 render pair met). **`obs_horizon = 2`, so the first model call at step 4
conditions on the window [step 0, step 4]: the stale frame is one of the two
frames of the first observation** (the step-4 frame is the arm-occluded one), so
the first observation is *half* stale-masked, not clean. The demos' windows have
the same [t-1, t] structure and the stores' first recorded frame carries the
same stale mask (`213`'s first-detectable along sits downstream of frame 0's
y), so the staleness is in both stores' training distribution and is not a
lever - but it does mean the first call never sees two clean target masks.

## 4. The arm occlusion at the fire zone and the first view (the named alternative)

The +Y belt cannot occlude at along 0.15-0.30 (downstream of its +0.515..+0.870
band), so a zero target mask there is a **foreground** occluder. Measured from
the direct env's own frames at the model calls in the zone (the `[align]`
counters):

| | A (control) | B (aligned) |
| --- | --- | --- |
| fire-zone calls | 1305 | 1424 |
| zero target mask | **358 = 27 %** | **252 = 18 %** |
| left | 126/427 = 30 % (29 eps) | 94/525 = 18 % (27 eps) |
| right | 232/878 = 26 % (46 eps) | 158/899 = 18 % (48 eps) |
| rendered visible fraction p50 (p10) | 0.67 (0.09) | 0.82 (0.08) |

Phase 1 measured **0.23-0.60 zero-mask** at the same window in the two-line
demos (the arm over the belt); the control sits inside that range and the
aligned arm at its lower edge. So the alignment **reduces** the decision-zone
foreground occlusion (left 30 % -> 18 %) - that drop is **measured**; its cause
is a **hypothesis**. The aligned arm makes fewer model calls per attempt (44 vs
60), but it makes **more** zone calls (1424/75 = 19.0 vs 1305/75 = 17.4 per
attempt), so "the arm walks less upstream" is **not measured**: the span is
shorter by construction and the arm's own trajectory differs between the
branches (the feeder state has advanced ~1.2 s at the reset), which changes the
*share* of calls inside the 0.15-0.30 zone. The left's carried class does not
move.

**The attribution probe** (`260_mask_probe.py`: **one episode per arm**, the same
scenario - a single sample, not a distribution; the aggregate zone counters above
are the corroboration. The log rows rank the instance ids **inside the target's
projected bbox by pixel count**, i.e. the foreground candidates that could hide
the fruit, **not a depth order**):

| first call | the bbox's dominant instances (px) | the target |
| --- | --- | --- |
| A, along +0.541 | `OutputBeltP/FrameN` 173 + `OutputBeltP/Belt` 67 | 0 px (the belt, as phase 1 says) |
| B, along +0.399 | **`openarm_left_link3` 127** + `Conveyor/Belt` 104 + `openarm_left_link4` 9 | 16 px |
| B, along +0.291 | the fruit 118 vs the arm 97 | the fruit wins at ~0.29 |

So at the aligned first call the **arm's mask dominates** (127 vs 16 px) and
the fruit only becomes the dominant instance at along ~0.29; the probe's
control at +0.541 is belt-dominated exactly as the phase-1 map predicts. The
step-4 frame is the one that fails, not the stale step-0 frame: the store's own
first window at its first detectable frame is [the prior frame empty (the stale
read), that frame visible 0.83], while the direct env's aligned first window is
[step 0 empty (stale), step 4 empty (the arm)] - **that is the mismatch measured
here**, and it is why the A/B had no visible first view to test.

The arm is the named alternative in the falsifier. **It is not, however, the
single-arm store's distribution** - the first pass pooled the store's two arms
and read the direction backwards. Re-derived per arm from `datasets/demos_v11`
(the same `213` normalisation):

* `+0.25..+0.30` zero-mask: **left 0.56 (n=63) / right 0.92 (n=558)**. The
  0.88-0.90 quoted above is the **right's** number - the two arms do not share a
  first view, and the pooled read was the right's.
* `+0.35..+0.40`: left **zero 0.00, median 0.93** (p10 0.89); right **zero
  0.42, median 0.04** - at the left's first view the fruit is visible, at the
  right's it is not.
* The left at the store's own x band (x 0.32-0.36, world y 0.35-0.45): **125
  frames, zero-mask 1 %, median 0.94** (p10 0.89; the `213` per-episode
  distance normalisation - the rendered/segment-calibrated read of
  `216_store_arm_baseline.py` puts the same frames at ~0.86-0.89, the
  calibration differs and the conclusion does not).

Against that, the **direct env's left** first calls at x 0.32-0.37 are **11/11
(control) and 6/6 (aligned) empty**, and the aligned ones sit at along
0.398-0.399 - *inside* the store's left-visible band. So this is a **new
direct-env/reset mismatch**, not the store's distribution: at the same x band
and the same along, the store's left frame is visible and the policy env's left
first call is not. The direction claim also corrects: **0.399 is 42 mm
downstream of the single-arm first view (+0.441 p50), not upstream of it**, and
the two A/B arms' first calls (+0.484 / +0.398) bracket that first view.

**What differs is then the arm's pose, not the fruit's along** - a hypothesis,
not a measurement: the per-arm baseline (`scripts/216_store_arm_baseline.py`:
the rendered visible fraction against `212`'s unoccluded area with the store's
own p99.5 calibration, the frame-0 arm pose against the `grasp`/`ready`
waypoints, and the `--ab` join to this batch; output `logs/p34/B_store.*`)
reads the store's left frame-0 pose at |q-grasp|max p50 **0.161** against the
right's 0.217, and the store's own frame 0 is zero-mask 1.00 with the first
*detectable* frame at +0.451 (left) / +0.440 (right) and rendered visibility
0.83 / 0.82. The reset's **arm pose/settle** is the leading candidate; the
`B_probe_*` settle sweep re-probes the first call as a follow-on, and **the
cause is not measured by this A/B** (the probe's link3 row is one episode per
arm).

So what the A/B shows is narrower than "the arm is the mechanism": **moving the
fruit to 0.399 with this reset pose leaves the arm in the first view, and the
left does not move.**



## 5. The verdict

**The manipulation check passes on the aligned arm (96 %) and fails on the
control (12 %)**: the first model call moves from p50 +0.484 (212 visible
fraction 0.41; fully hidden in 26/75 = 35 %) to +0.398 (1.00; 0/75 hidden), at
the measured 4.0 mm cost and with no arm command change. **It checks the fruit's
along, not its visibility**: the rendered target mask at the first call is empty
in **72/75 (A) and 71/75 (B)** episodes, because the arm occludes the first view
on both arms (section 4). The treatment therefore did not present a visible
first view, and **the visible-first-view hypothesis is untested**.

**The primary endpoint does not move.** The paired left carried-class conversion
is **0 B-only / 1 A-only (p = 1.0)**; the left's carried count is 24 in both arms
but the 9 paired left members moved (6 carried->carried, 1 ok->carried, 1
no-grasp->carried, 1 no-grasp->no-grasp). The unpaired left counts move by 1-3
episodes (placed 1 -> 2, no-grasp 4 -> 1, the composite failure mass 28 -> 25),
all non-significant (two-sided Fisher 0.35-0.71) and not reproducible in the
paired comparison (pooled 2/3, p = 0.8125; species-only 3/4, p = 0.7734). The
pooled rate 27 % -> 31 % is +3 episodes (p = 0.72); the cycle is 3.2 % shorter by
construction (the alignment removes 16 model calls and the pre-first-view wait
from the attempt).

**The decision rule is ambiguous, and the primary is the read that matters.** The
pre-registered positive bullet needs the paired carried class to favor B, which
it does not; the falsifier bullet needs *no* left placed gain and *no* composite
reduction, which is also literally not the case (placed +1, composite -3 - both
1-3 episode, non-significant moves). The script's own verdict line (`A_align.txt`)
is the middle branch - "no measured improvement of the primary endpoint" - whose
`placed up or mass down` clause was pre-registered as a **relocation guard**
(PREREG section 4), not a win condition. So the honest statement is: **the
primary does not move; the composite and placed moves are too small to read and
were not the win condition; the outcome claim is limited to "aiming the first
call at 0.399 with this reset pose does not move the left", and the
visible-first-view hypothesis is untested.**

**What did move is acquisition-side and non-significant**: the decision-zone arm
occlusion falls (left 30 % -> 18 %; the drop is measured, its cause is a
hypothesis - the span is shorter by construction but the zone receives *more*
calls, 19.0 vs 17.4 per attempt), the left's no-grasp count falls 4 -> 1
(p = 0.35), and the left's close-start `|y|` maximum falls **177.4 -> 5.2 mm**
(one A flail episode resolved) - `A_class_split.txt`. Neither is the P33 class,
and no new failure reason appears.

So: **the reset alignment is a correct interface change that does not pay.** It
ships **default off, not adopted**; the direct-path history and any checkpoint
stay on the shipped reset. The early-view question is **not retired - it is
untested at a visible first call**; the scene lever (+Y belt y +0.04) remains
Phase 3 and was not run, and the next measurement the arm side needs is the
reset's **arm pose/settle** (the new direct-env/store mismatch of section 4),
not another fruit-along move. The A/B leaves three interface findings: the
**first model call is arm-occluded in ~96 % of episodes on both arms** even when
the belt is clear (the probe: the left arm's link3); the **step-0 observation's
target mask is one frame stale and is one of the two frames the first call
conditions on** (`obs_horizon = 2`; shared with the demos); and the single-arm
store's **left** first view is **visible** at its own x band while the direct
env's left first call is not.


## 6. The Gate-1 documentation corrections (phase-1 files)

| the correction | the corrected statement |
| --- | --- |
| the "33 model calls" | Phase 1 computed `(reset along - 0.45) / 4 mm = 0.133 m = 33` and called the quotient model calls. **The reset's own ~0.10 m of selection/setup travel carries no model calls** (the first call comes after the second frame at control step 4). Measured control: the first call's along p50 **+0.484** (p10 +0.405, p90 +0.557), the **fully hidden** (212 `vis<0.01`) share at the first call **26/75 = 35 %**, the fully-hidden model calls p50 **0** (p90 11), and the calls to full visibility (212 `vis>0.99`) p50 **8** (p90 25). The model's not-fully-visible run is **~4x smaller** than "33" (8 vs 33). |
| the "88-90 % start hidden" | That is the **reset** (the selection header) - a state with no model call. At the **first model call** the fruit is at p50 +0.484 and fully hidden (212 `vis<0.01`) in **26/75 = 35 %** of control episodes, partially visible in the rest. The first-view train/eval mismatch is real but smaller and differently caused; see the next row. |
| the demos' first view (0.399) | **Store- and arm-dependent.** The two-line stores (`p33_pear`, `demos_v12`) read first-detectable p50 **0.398-0.399** with 0.04-0.60 zero-mask at +0.35..+0.45; the **single-arm** store `demos_v11` (the direct env's own lineage) reads **+0.441** (p10 0.430, p90 0.451), and per arm its masks differ: `+0.25..+0.30` zero-mask **left 0.56 (n=63) / right 0.92 (n=558)** - the 0.88-0.90 figure of the first pass is the **right's** - while at `+0.35..+0.40` the left is **zero 0.00, median 0.93** and the right **zero 0.42, median 0.04**. So the single-arm store's **left** first view is visible (125 frames at x 0.32-0.36, y 0.35-0.45: zero 1 %, median 0.94), and the direct env's left first call is empty there (11/11 A, 6/6 B) - a **new direct-env/reset mismatch** (hypothesis: the reset's arm pose/settle), not the store's distribution. The direction also corrects: 0.399 is **42 mm downstream** of the single-arm first view, not upstream. `logs/p34/21_demos_v11.*`. |
| the README's "1.25 s after the fruit emerges" | The shipped 0.9 s lead fires at y ~ 0.108, i.e. **2.85 s** after the fruit emerges (0.45 -> 0.108 at 0.12 m/s); **1.25 s** is the *minimum* window from the band's edge to the fire **zone's upstream end** (0.301), not to the fire. |
| the window p50 | The delivered visible window from the band's edge (0.45) to the **measured** fire (p50 dy 0.226 m) is **p50 ~1.9 s**; the 1.16-1.45 s figure is the worst case (a fire at 0.301). |
| the 2.9 s band vs the 2.3 s travel | The fully hidden band's **width** is 0.355 m = **2.96 s** at 0.12 m/s, but a fruit is released at the spawn **+0.68**, 0.155 m inside the band: its own fully-hidden run is 0.165 m = **1.38 s** and its travel from the spawn to full visibility (+0.40) is 0.28 m = **2.33 s**. Quote 2.9 s as the band's width, 2.3 s as the fruit's travel. |
| the 17 mm landing margin | With the +Y belt at y +0.04 the hand centre keeps **35 mm** (0.50 - 0.465) and the **fruit's** inner edge keeps **~17 mm** at the release p10 (0.512 - 0.030 - 0.465); the +0.08 lever is 5 mm inboard. |

The corrections are applied in `logs/p34/README.md` and `logs/p34/REPORT.md`
(items 3-6 verbatim; items 1-2 read the phase-2 control's measured rows), and
the `.slim/deepwork/p34-occlusion.md` spawn y is corrected to 0.68.

## 6b. The Gate-2 corrections (this read)

The five substantive corrections are applied throughout; the ambiguous ones are
flagged here so the record keeps the difference between what was measured and
what was inferred:

| the correction | what changed |
| --- | --- |
| B1 the treatment presented no **visible** first view | The conclusion is restated: **"aiming the first call at 0.399 with the reset pose does not move the left; the visible-first-view hypothesis is untested"**. The old "the early view is not the mechanism" claimed a test the data cannot support - the rendered first-call target mask is empty in A 72/75 and B 71/75 (the arm occludes both). |
| B2 the "arm is the true second occluder in the training data" | A **pooling + direction error**; replaced with the per-arm store reads of section 4 (left 0.56/right 0.92 at +0.25..+0.30; the 0.88-0.90 is the right's; left visible at +0.35..+0.40 and at its own x band), the **new direct-env/reset mismatch** (left first calls at x 0.32-0.37: 11/11 A, 6/6 B empty) with the reset's arm pose/settle as the **unmeasured hypothesis**, and the direction (**0.399 is 42 mm downstream of +0.441**, not upstream; the A/B arms bracket it). |
| B3 the decision rule | The primary (the paired left carried class) does not move (0/1, p = 1.0); the composite/placed moves (28 -> 25, 1 -> 2) are **3-episode, non-significant**, and the composite is a **relocation guard, not a win condition**. The script's own middle verdict line is what fired; the pure falsifier bullet did not literally fire. The "the left does not move" phrasing is dropped. |
| B4 "24/24 identical" | A **count, not a set**: the 9 paired left episodes moved - 6 carried->carried, 1 ok->carried, 1 no-grasp->carried, 1 no-grasp->no-grasp (the carried->no-grasp cell in the pooled matrix is not a left pair). |
| M1 "the arm walks less upstream" | **Unmeasured**: B makes *more* zone calls (19.0 vs 17.4 per attempt). The zero-mask drop (left 30 % -> 18 %) is measured; its cause is a hypothesis. |
| M2 the step-0 staleness | Corrected: `obs_horizon = 2`, so the first call's window is **[step 0, step 4]** and **includes** the stale reset frame; the old "the first call does not use that frame" was wrong. |
| M3 the probe's scope | **One episode per arm** (a sample; the aggregate zone counters are the corroboration); the bbox ranking is **foreground candidates by pixel count, not a depth order**. |
| M4 the pairing tolerance / the reads | The code's tolerance is **0.05 m**, not the docstring's 0.5 mm (docstring corrected; inert on this batch - every retained pair matched at the store's 0.1 mm resolution). Both species-only reads quoted (3-4, p = 0.7734 vs 2-3, p = 0.8125); the left's **p = 1.0** (0.81 is the pooled read). |
| M5 the line count | **188** inserted lines in `rl_env.py`, not 175 (`git diff --stat`). |

**The post-batch timestamp.** `logs/p34/align_report.py` and its output
`logs/p34/A_align.txt` carry **19:44**, three minutes after the batch's last log
(`B_5.log`, 19:41, and the other nine logs 18:38-19:34). The script is
**read-only** over `A_ab/*.log` (it opens them and writes nothing), and the batch
logs' mtimes are their run times, so no outcome data was regenerated; the
amended part is the *reporting* section (the pairing/occlusion cross-checks).
The pre-registered endpoints also come from the pinned `A_pairs.py` /
`C_class_split.py` / `113_rl_report.py` runs (`A_pairs.txt`, `A_class_split.txt`,
`A_verdict.txt`, 19:41). Quote `A_align.txt` as a **post-batch read**, not as a
pre-registered artifact.

## 7. Files, provenance, no-harm

* `logs/p34/PREREG.md` — the pre-registration (before the batch).
* `src/fruit_sorting/rl_env.py` — the knob, the diag, the manifest block (the
  only `src/` change; `TASKS_MD5` unchanged).
* `logs/p34/run_p34_ab.sh` — the A/B driver (one `154_claim_run.sh` claim, the
  P33 W8-A scenario, interleaved arms, then the read-only reports);
  `logs/p34/run_p34_after.sh` — the probe + the acceptance.
* `logs/p34/A_ab/{A,B}_N.log` — the batch (`scripts/112_rl_ab.sh`);
  `A_align.txt` (`align_report.py`: the manipulation check + the occlusion;
  **19:44, post-batch** - read-only over the logs, see section 6b),
  `A_verdict.txt` (`scripts/113_rl_report.py`), `A_class_split.txt`
  (`logs/w7/C_class_split.py`), `A_pairs.txt` (`logs/w8/A_pairs.py`),
  `A_mech.txt` (`logs/w7/B_ab_report.py`). `align_report.py`'s same-fruit key
  carries a **0.05 m** diameter guard (the docstring's 0.5 mm was wrong; the
  guard is inert on this batch) and quotes the pinned species-only read
  alongside.
* `scripts/212_occlusion_map.py`, `scripts/213_occlusion_demos.py`,
  `scripts/215_occlusion_policy.py` — phase 1's analytic map, the store masks
  and the policy logs (the scripts are new; their outputs are `10/11/20/21/50*`).
* `logs/p34/260_mask_probe.py` + `260/261_probe_*.log` — the occluder
  attribution probe (which instance fills the target's projected bbox; **one
  episode per arm**).
* `scripts/216_store_arm_baseline.py` + `logs/p34/B_store.*` + `B_probe_*.log`
  — the per-arm store baseline (rendered visible fraction vs `212`, the frame-0
  arm pose, the `--ab` join) and the first-call re-probe at the aligned pose;
  these supply the B2 re-derivation (the tool is the Gate-2 B2 check).
* The tree pins before/after the batch (`71/72_tree_md5_*.txt`); the checkpoint
  `moe_v13s` `61da390a`. The batch ran `rl_env.py` **2e392f48** (the only src
  change; **+188/0**); `tasks.py` `cdde6bd2`, `trigger.py` `d7ec85fc`,
  `runtime.py` `379ac706`, `meshes.py` `41efc522` are unchanged; the batch's
  before/after pins are identical. **At commit time** the file is the P34-A
  align knob **plus** the P34-B `FRUIT_RESET_SETTLE` follow-on (default 20 = the
  shipped `advance(20)`; `[align]` gains `settle`/`q_r`/`q_f`), so the committed
  diff reads +216/1 - the batch's +188/0 is the pin, not the commit's stat.
* **No-harm**: acceptance `scripts/accept.sh` with the knob unset ->
  `73_accept_no_harm.log`, compared to the current record
  `logs/p33/40_accept_final.log` (`74_accept_identity.txt`); `selfcheck.sh`
  PASS.
* **Risks**: the alignment changes the branch (the feeder state advances ~1.2 s,
  so the fruit sequence diverges after episode 0 and the same-fruit pairing
  shrinks to 27 pooled / 9 left); the first-call rendered mask is a *foreground
  occlusion* measure (the probe names the arm; a fruit ahead of the target in
  the sight line is not separated by the mask alone); the step-0 observation's
  mask is one frame stale and **is** one of the two frames of the first call's
  window; the direct loop is not bit-reproducible (frames), so this is the
  N=5 sample protocol and a 1-3 episode unpaired move is within noise; the
  treatment-vs-visibility gap above means the A/B cannot be quoted as a test of
  the visible-first-view hypothesis.
