# P34-B — the per-arm store baseline, the reset's first-call pose, and the 0.441 treatment check

Measured 2026-10-23/24 (after the P34 phase-2 A/B and its Gate-2 review).
**Default off, no shipped default changed**; this phase's files are uncommitted
(the orchestrator's `1786fae` carries the phase-2 record and this phase's code
as of 23:43). The instruments: the offline store baseline
`scripts/216_store_arm_baseline.py`, the reset-pose/render probe
`logs/p34/B_mask_probe.py`, and 23 probe runs under
`scripts/154_claim_run.sh` (one episode each, the only valid first-call frame).
Pre-registration for the follow-on: `logs/p34/B_PREREG.md`.

**The one-line answer.** The Gate-2 B2 premise - *the direct env's left first
call is 0-4 % visible while the store's left is 89-91 % at the aligned
along/x* - **is a frame-staleness artifact, not an arm pose**. The A/B's
first-call target mask is the **pre-reset frame** after a mid-process reset: in
150 A/B episodes `first_px > 0` occurs in exactly the **10 episode-0s** (one per
run). The valid (episode-0) renders show the left's first call **visible**
(`first_rel` 0.89-0.97) at the shipped reset and at both the 0.399 and the 0.441
aim, and the only first-view occlusion left is the **inactive left arm parked at
`ready`** over the outer x band (x ~0.22), which no along aim touches
(`first_rel` 0.077-0.131 for 0.399/0.441/0.445). The reset pose is the calibrated
grasp waypoint (<= 0.026 rad) and the settle is a measured pose **null** (20/60/
120 ticks give the same joints to 0.001 rad); the store's frame 0 is a
*different, stable* pose (0.16-0.33 rad from grasp) - the dynamic catch's hover -
but that difference is not what hid the first view.

## 1. The per-arm store baseline (the Gate-2 numbers, confirmed and corrected)

`scripts/216_store_arm_baseline.py` (offline; `target_mask` + `fruit_position` +
`joint_positions`; along = `fruit.y - station_y`). Rendered visible fraction =
mask area / the analytic **unoccluded** area of `scripts/212_occlusion_map.py`
at the same (x, along, d), scaled by the store's own p99.5 ratio (the
segmentation-per-ray scale `k`; a fully visible fruit reads 1.0). The
`213`-normalised value (mask x depth^2 over the episode's maximum, phase 1's
measure) is quoted next to it because the Gate-2 89-91 % is that measure.

| store (scenario) | arm | n | frame-0 along p50 | first-detectable p50 | first view 0.40-0.50: zero / rendered p50 / `213` frame-0 p50 (non-zero) | decision zone 0.15-0.30: zero / rendered p50 | `|q0-grasp|max` p50 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `demos_v11` (single-arm, fixed supply) | left | 5 | +0.455 (mask stale) | **+0.451** | **0.04 / 0.86 / 0.92** | 0.80 / 0.00 | **0.161** |
| `demos_v11` | right | 45 | +0.444 (mask stale) | **+0.440** | 0.28 / 0.21 / 1.00 | 0.54 / 0.00 | 0.217 |
| `demos_v12` (two-line, wide x band) | left | 80 | +0.406 | +0.406 | 0.01 / 0.78 / 0.76 | 0.48 / 0.01 | 0.545 |
| `demos_v12` | right | 78 | +0.412 | +0.412 | 0.37 / 0.20 / 0.15 | 0.29 / 0.31 | 0.583 |
| `demos_v13p` (two-line, wide x) | left | 89 | +0.393 | +0.393 | 0.01 / 0.76 / 0.92 | 0.47 / 0.02 | 0.380 |
| `demos_v13p` | right | 84 | +0.421 | +0.421 | 0.27 / 0.54 / 0.92 | 0.23 / 0.57 | 0.590 |
| `p33_pear` (two-line, wide x, post-pear) | left | 92 | +0.399 | +0.399 | 0.01 / 0.64 / 0.94 | 0.55 / 0.00 | 0.326 |
| `p33_pear` | right | 88 | +0.399 | +0.399 | 0.20 / 0.60 / 0.94 | 0.12 / 0.64 | 0.526 |

What this confirms and what it corrects:

* **Confirmed (the direction and the magnitude).** The store's left *does* see
  the fruit at its first view: 0.01 zero-mask (two-line stores) or 0.04
  (`demos_v11`), `213`-normalised 0.92-0.94, rendered/analytic 0.64-0.86. The
  Gate-2 "~89-91 %" is the `213`-normalised value of the non-zero first frames
  (0.92-0.94 in v11/v13p/p33); the rendered/analytic value is 3-20 points lower
  because a pear's mesh silhouette is narrower than the analytic sphere of the
  same diameter, and the two normalisations disagree by that much by
  construction. Quote the measure with the number.
* **Corrected 1 - the single-arm store's first view is *not* arm-occluded.** The
  phase-2 sentence "the single-arm store's first view is arm-occluded too
  (zero-mask 0.88-0.90 at +0.25..+0.30)" applies the *pooled* `+0.25..+0.30`
  bins (which are the **right's**, n=45 of 50) to the left. Per arm the left is
  **0.80 zero in the whole 0.15-0.30 window, 0.56 in +0.25..+0.30, 0.00 in
  +0.30..+0.35**, and its first view is 0.86 visible. The left's arm occlusion
  sits *downstream* of the first view (the decision zone), the right's starts
  higher up.
* **Corrected 2 - the store's x band is not the direct env's.** `demos_v11` was
  collected on the **fixed** supply: x p10-p90 **0.323-0.348** (both arms). The
  patch sheet (the direct env's scenario) spans **0.21-0.36**; the direct env's
  first calls sit at x p50 0.279 (left) / 0.262 (right) with a p10 near 0.21.
  The single-arm store therefore has **no frames in the outer band**; the
  wide-band stores are two-line (`p33_pear`'s own manifest:
  `collection.mode = two_line`, stations 0.00 / -0.10), so their arm poses are
  not the direct env's. At the same (along, x) a store comparison is only
  possible against the two-line stores, and there the first view is 0.58-0.71
  visible in the outer band - so a visible first view at x 0.22 is possible, but
  not with the single-arm park.

## 2. The reset's first-call diagnostic (the pose and the settle)

The `[align]` row now carries the active arm's joints at the reset return
(`q_r`) and at the first model call (`q_f`) - `FRUIT_RESET_ALIGN_DIAG=1`, pure
reporting - and `FRUIT_RESET_SETTLE` (default **20**, the shipped value)
overrides the reset's own settle.

**The reset's pose is the grasp waypoint.** Measured `q_r` (7 joints):

| arm | `q_r` (probe, episode 0) | `|q_r - grasp|max` | `|q_first - q_reset|max` |
| --- | --- | --- | --- |
| right (seed 77) | +1.222 +0.090 -1.571 +0.967 +1.147 +0.614 -1.343 | **0.026 rad** | 0.000 |
| left (seed 101) | -1.251 -0.064 +1.571 +0.928 -1.185 -0.667 +1.324 | **0.019 rad** | 0.000 |

**The settle is a pose null.** 20 / 60 / 120 ticks give the *same* `q_r` and
`q_f` to 0.001 rad on both arms (the arm is already at the grasp target when
`teleport_joints`' own 30-tick settle returns). What the settle changes is only
the fruit's position: the aim is reached either way (the first call reads
+0.399/+0.399/+0.398 at aim 0.399 and +0.441/+0.441/+0.440 at aim 0.441),
because the alignment absorbs the extra belt travel.

**The store's frame 0 is a different, stable pose.** `|q0-grasp|max` p50
**0.161** (`demos_v11` left) / 0.217 (right) / 0.326-0.590 (the two-line stores),
and the pose does not drift over the first 60 frames (the same error at t=0 and
t=59). It is neither grasp nor ready (`|q0-ready|` 0.26-0.34): the scripted
dynamic catch's wait is a **hover at the predicted intercept**
(`tasks._dynamic_hover_point` = the grip point + `FRUIT_DYNAMIC_HOVER` 0.06 m),
which the recorded frame 0 carries and the direct reset does not. That is a real
train/eval pose difference - it is simply **not** the cause of a hidden first
view (section 3).

## 3. The first-call render: valid episodes only, and the two aims

**The blocker: the first call's target mask is the pre-reset frame.** Across the
phase-2 A/B's 150 episodes the `[align]` row's `first_px > 0` occurs in exactly
the **10 episode-0s** (A and B, all 10 runs); every episode >= 1 reads 0. The
labels probe shows the instance resolution itself is correct (`want =
/World/Fruits/Fruit_15`, id 70 = the fruit, id 88 = its stem also matching the
substring) and that the mask at the *reset* is 0 while the fruit is visible
(along 0.389, `vis212` 1.00) - i.e. the **frame is one or more renders behind**
and after a mid-process reset it predates the reset. (The one non-zero
episode >= 1 seen anywhere is a two-episode probe whose *previous* episode was
aborted with the fruit still at 0.39: the stale frame then still contains it - so
the rule is "the previous frame", and a normal episode's last frame has the
target placed or carried away.) So the phase-2 statement
"the rendered target mask is empty at the first call in 71/75 (B) / 72/75 (A),
even in the belt-clear cases" and the Gate-2 "0-4 % visible" are **the stale
frame, not the arm**. (The model's first call is at step 4 and its 2-frame
horizon contains that same step-0 frame, so the *policy* sees the stale frame
too; that is a new, small observation artifact, separate from the occlusion.)

The valid renders are therefore **one episode per process**. Measured (episode 0
of its run; `px` = the target-mask pixels, `px_max` = the episode's largest raw
count over 30 calls, `first_rel` = **(px / the analytic unoccluded area at that
pose) / the episode's maximum of the same ratio** - the depth- and mesh-free
normalisation, i.e. phase 1's measure applied per call):

| fruit (arm) | x | aim | first along (reset return) | `px` | `px_max` | first_rel | `vis212` | the bbox's dominant instances |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pear (right) | 0.219 | shipped | +0.541 | 0 | 174 | **0.000** | 0.00 | `OutputBeltP/FrameN` + `Belt` (the +Y belt) |
| pear (right) | 0.219 | 0.399 | +0.399 | 16 | 144 | **0.115** | 1.00 | **`openarm_left_link3` 127** + belt 104 |
| pear (right) | 0.219 | 0.441 | +0.441 | 21 | 160 | **0.131** | 1.00 | belt 222 (background) + **`link3` 24** |
| pear (right) | 0.219 | 0.445 | +0.445 (reset +0.449, 96 steps) | 13 | 166 | **0.077** | 1.00 | belt + **`link3`** |
| apple (left) | 0.240 | shipped | +0.439 (+0.443) | 158 | 179 | **0.893** | 0.98 | **the fruit 158** + belt 54 |
| apple (left) | 0.240 | 0.399 | +0.398 (+0.402) | 174 | 179 | **0.972** | 1.00 | **the fruit 174** + belt 82 |
| apple (left) | 0.240 | 0.441 | +0.439 (+0.443, **0 steps**) | 158 | 179 | **0.893** | 0.98 | **the fruit 158** + belt 54 |
| apple (left) | 0.240 | 0.445 | +0.439 (+0.443, **0 steps**) | 158 | 179 | **0.893** | 0.98 | **the fruit 158** + belt 54 |

* **The left's first view is visible at every aim** (0.89-0.97, the fruit the top
  instance in its own projected bbox). The 0.399 aim the phase-2 A/B used was
  *not* arm-occluded on this valid sample - so the A/B did present a visible
  first view on the left and its outcome null stands.
* **The left's shipped reset sometimes already presents the store's first view.**
  This episode's reset returns at along +0.443, below both the 0.441 and the
  0.445 aim, so the alignment takes **0 steps** and the first call is at +0.439 -
  the store's own first view. The treatment is only *reachable* on the episodes
  whose reset lands higher (the A/B's control left first-call along p50 is
  +0.470, and its reset p10 is +0.409 - so ~10 % of episodes are already below
  +0.445 and the aim is a no-op there).
* **The right's outer-band first view is occluded at every aim** (0.115 / 0.131 /
  0.077 for 0.399 / 0.441 / 0.445, `q` unchanged) - and the occluder is the
  **inactive left arm parked at `ready`**, not the active arm and not the reset
  pose: the same `ready` pose is in every recorded right-arm demo
  (`demos_v11`: the inactive arm is at ready to 0.014 rad, sd 0.000). The
  recorded single-arm supply never places a fruit at x 0.22 (its band is
  0.323-0.348), so the combination is absent from that store.
* **The in-env row agrees.** A two-episode rollout with the diag on
  (`B_rowcheck.log`, seed 101, aim 0.445) prints, for its episode 0 (the same
  left apple), `first=+0.439 first_px=158 px_max=196 pfc=137 pcm=151` ->
  **pfc/pcm = 0.907** (vs the probe's `first_rel` 0.893 on the same fruit), and
  its episode 1 reads `first=+0.445 first_px=0 pfc=0` - the stale first frame
  reproduced on a *finalized* episode.
* **The raw `px / px_max` is depth-biased** (the fruit is closer to the head
  camera when downstream); on these samples it reads 0.883 where the
  depth-corrected 0.893 is the same measurement, so quote `first_rel` - the
  `[align]` row carries `pfc`/`pcm` (px x camera distance^2, first and max) for
  the A/B's own read.

## 4. The 0.441 treatment check and the verdict

The task's treatment check - *the rendered first-call mask non-empty and the
visible fraction >= 0.9* - on the depth-/mesh-normalised measure (`first_rel`):

| arm (x) | shipped | 0.399 | 0.441 | 0.445 |
| --- | --- | --- | --- | --- |
| left (0.240) | 0.893 | **0.972** | 0.893 (aim unreachable) | 0.893 (aim unreachable) |
| right (0.219) | 0.000 (belt) | 0.115 | 0.131 | 0.077 |

**It passes for the left** (0.97 at the A/B's 0.399 aim; 0.89 when the reset
already presents 0.439) and **fails for the right at x 0.22 at every aim**
(0.08-0.13). The 0.441 aim is at the belt's near edge for >= 58 mm fruit
(`vis212` 0.98 at 0.439 for the 70 mm apple) and the reset can already present
the target **below** the aim: the measured left process returned at +0.443, so
the 0.441 aim took **0 steps** and the first call sat at 0.439. The A/B's
control reset is p10 +0.409 / p50 +0.488, so the aim is reachable on ~90 % of
episodes and a no-op below +0.445. So:

1. **The Gate-2 B2 finding is refuted as stated** - the 0-4 % is the stale first
   frame; the left's valid first view is visible at the aligned along (0.97),
   and the per-arm store baseline says the same of the store's left (0.86
   rendered / 0.92 `213`).
2. **The early-view lever is closed for the left.** The phase-2 A/B tested the
   belt-occlusion fix on the outcome and it was null; the valid renders now show
   that the null was not an implementation failure: the treatment *did* present
   a visible first view on the left (0.97 at 0.399). The 0.441 aim changes
   nothing (both aims visible; 0.441 is even marginally worse because it sits at
   the belt's edge and can be unreachable).
3. **The surviving first-view mismatch is right-arm + outer band** (x < 0.26;
   **44-48 %** of the A/B's first calls): the inactive left arm at `ready`
   (link3 127-199 px inside the target's bbox) hides the fruit at every aim. The
   single-arm store has no such frame (x band 0.32-0.35); the wide-band stores
   are two-line with a different park. This is **not** the reset pose and **not**
   the settle.
4. **The reset pose is a real but separate distribution difference** (grasp vs
   the store's hover, 0.16-0.33 rad). Aligning it is a bounded lever, but the
   measured expectation is small for the first view (the left is already visible
   at the grasp pose) and it cannot touch the right's outer-band case (the
   inactive arm's park).
5. **The first-view metric is blocked** until the first-call frame is current:
   read it one episode per process (as here) or after a synchronized render -
   otherwise every episode >= 1 reads the previous episode's frame.

**Recommendation (fixed now, details in `B_PREREG.md`).** Do **not** run the
along-only A/B as a first-view test: the treatment is measured to change a
visible view to a visible view (0.97 -> 0.89) and the phase-2 A/B already read
the outcome null. The named next lever is the **arm park / camera sightline for
the outer band** (options: park the inactive arm out of the sightline instead of
at `ready`; narrow the single-arm supply's x band to the store's; move the head
camera - each with its own cost and its own pre-registration), with the
**reset-pose (hover) alignment** as the low-expectation secondary. The
pre-registration is written so the A/B can be run if a corrected first-view
measurement reverses the 0.97, which it currently does not.

## 5. Files, provenance, no-harm

* `scripts/216_store_arm_baseline.py` — the offline per-arm store baseline
  (`--ab` reads the A/B's per-arm first calls; `--match` reads a store at a
  pose). Outputs: `B_store.txt/.json` (v11 + p33_pear), `B_store_twoline.txt/
  .json` (v12 + v13p), `B_ab_store.json` (the A/B's first calls).
* `src/fruit_sorting/rl_env.py` — `q_r`/`q_f`/`px_max`/`pfc`/`pcm` in the `[align]` diag,
  `FRUIT_RESET_SETTLE` (default 20 = shipped), the manifest's `settle` field.
  Diag only; the shipped path is unchanged (one env read at init, one False
  branch, `advance(20)`).
* `logs/p34/B_mask_probe.py` + `B_probe_*.log` (`control`, `a399_s20/s60/s120`,
  `a441_s20/s60/s120`, `L_*`, `labels`, `MR_*`, `ML_*`, `B_rel_*`), the drivers
  `run_p34b_probe.sh`, `run_p34b_probe_left.sh`, `run_p34b_probe_max.sh`,
  `run_p34b_probe_rel.sh`, and their outer logs - 23 probe runs (the episode-0
  frame of each is the valid one; the rest are one render behind), one
  simulator, via `scripts/154_claim_run.sh`; `B_rel_*` is the depth-normalised
  set quoted in sections 3-4. `B_rowcheck.log` is the two-episode
  `110_rl_rollout.py` run that verifies the new `[align]` fields end-to-end
  (`pfc`/`pcm`) and reproduces the stale first call on a finalized episode.
* **No-harm**: `scripts/selfcheck.sh` PASS (0 failures, 1 skipped;
  `B_selfcheck.log`), re-run on the final tree. The scripted acceptance was
  **not** re-run in this phase (the scope is offline + the cheap renders); its
  path is unchanged by construction - one env read at init, `advance(20)` with
  the settle at its shipped 20, and every diag block behind
  `FRUIT_RESET_ALIGN_DIAG`/`FRUIT_RESET_ALIGN` - so the phase-2 acceptance's
  376/376 identity still describes this tree's scripted line.
* **Risks.** (a) The valid first-call renders are **one fruit per arm** (the
  same fruit across the four aims; every other episode's first frame is stale) -
  the 0.97/0.11 are single fruits, and the x dependence is inferred from the bbox
  attribution, not swept. (b) The store's pose is named
  as the hover from its distance to grasp (0.16-0.33) and the scripted hover's
  definition, not from a live hover-vs-grasp render pair. (c) The `213`- and
  rendered/analytic normalisations differ by 3-20 points, so a Store number must
  name its measure. (d) The stem instance also matches the prim-path substring;
  the resolution took the fruit here (id 70 < 88), but the match is order-
  dependent. (e) The 0.441 aim is at the belt's near edge for >= 58 mm fruit.
