# P34 — The camera occlusion by the raised output belts (the owner's hypothesis)

Started 2026-10-23 (owner: the left-lane candidate/effectiveness and the short
graspable window may come from the **+Y raised output belt occluding the main
belt's fruit below it** — the fruit is seen late; adjust the fixture placement
or the fruit-holder's shape/position to reduce the occlusion and test the
success rate). Full delegated authority; an Oracle gate per phase.

## 1. The geometry (measured)

- The policy/head camera: **(0.05, 0.0, 2.0) looking at (0.34, 0.22, 1.1)**,
  res 240x424 (`scene.py:1390-1402`; the `[fruit] head camera at ...` line).
- The two raised output belts: **1.10 x 0.25 x 0.05 m at (0.65, +-0.55), top
  1.35, underside 1.30**, carrying along +X; the main belt top 1.17; the
  underside clears it by 0.130 m; the tallest fruit (pear body 84 mm) 46 mm
  (`assets.py:306-314`, `scene.py`, `conveyor.py`).
- The fruit: the main belt x 0.11-0.57 (the supply x 0.20-0.36), the top ~1.21;
  the spawn y **0.68** (the belt's slab runs to 0.80); the pick station y 0.00;
  the place release |y| ~0.41.
- **The analytic first pass** (the camera rays to a fruit top at (0.34, y,
  1.21)): the +Y belt's slab (y 0.425-0.675, z 1.30-1.35) blocks the fruit in
  roughly **y 0.48-0.88** (the ray crosses the slab there); the fruit at
  y < ~0.48 is seen *under* the belt and at y > ~0.88 *over* its far edge. The
  policy's first model call is at **+0.455..+0.551 m upstream** (the P31 wait
  gate's anatomy) — i.e. **inside the occlusion band**. This is the owner's
  hypothesis, geometrically plausible; it needs the measured visibility map.

## 2. The plan

| # | Phase | Deliverable | Owner | Gate |
|---|-------|-------------|-------|------|
| 1 | The occlusion measurement | the visibility map (the camera rays vs the two belts; the fruit's visible fraction vs y/x/z), the demos'/policy's first-view evidence (the target mask vs y, the first detectable frame, the trigger lead), the left/right window correlation, the lever candidates + their trade-offs (the place's geometry/reach, the P30-A lift, the policy's OOD) | @general | Oracle 1 |
| 2 | The scene lever A/B | the chosen lever (the +Y belt's y and/or height, the belt width, the camera if justified) + the visibility metric + the scripted/policy A/B (the success/window), the no-harm | @general | Oracle 2 |
| 3 | The integration + the commits | the docs/commits, the acceptance's reference if the scene changes the branch | @general + orchestrator | Oracle 3 |

Oracle budget: 3 gates (1 initial + up to 2 re-reviews each).

## 3. The lever trade-offs to measure (not assume)

- **The +Y belt's y** (0.55 -> upstream): the place's release is at |y| ~0.41
  and the belt's inner edge is 0.375; moving the belt upstream moves the inner
  edge and the place's reach - the left arm's place geometry and the P3's
  place-leg findings apply.
- **The belt's height** (the underside 1.30): raising it reduces the occlusion
  but raises the place's transfer lift (the P30-A's lift 0.08 / the rails);
  lowering it worsens the occlusion.
- **The belt's width** (0.25): a narrower belt shrinks the occlusion band but
  the release at 0.41 needs the inner edge <= 0.41.
- **The camera** (pose/res): a higher/closer camera shrinks the band, but the
  policy is frame-conditioned - a camera change is an observation-distribution
  change (the P33 recollection's OOD lesson).
- **The fruit's presentation** (x band): no effect on the along-belt occlusion.

## 4. Risks

- The occlusion may be partial/seasonal (the fruit visible over the belt's far
  edge at y > 0.88) - the measured visibility map decides.
- The lever may move the place/reach or the policy's frames (the OOD).
- The success-rate A/B needs the same-scenario comparison (the quantized
  outcome rules; the per-leg motion + the visibility metric).

## 5. Log

- 2026-10-23: the geometry checked (the camera + the belts); the plan; Phase 1
  dispatched.
- 2026-10-23 **Phase 2 measured — the reset alignment** (`logs/p34/PREREG.md`,
  `A_READ.md`, `A_ab/`, `260/261_probe_*.log`). `FRUIT_RESET_ALIGN=1` (default
  off, `rl_env.reset`, direct only; the batch's +188/0 at the pin `2e392f48`,
  the commit's +216/1 because the file also carries P34-B's default-identical
  `FRUIT_RESET_SETTLE`) puts the first model call at along
  0.399. The manipulation check: control **9/75 = 12 %** vs aligned **72/75 =
  96 %** (first-call along +0.484 -> +0.398; 212 vis 0.41 -> 1.00; the 0.399 aim
  is **42 mm downstream** of the single-arm store's +0.441, not upstream) ->
  **PASS** on the fruit's position. The outcomes: pooled **20/75 (27 %) ->
  23/75 (31 %)**, left 29/1/4/24 -> 27/2/1/24 (n/placed/no-grasp/carried); the
  left's carried **count** is 24 in both arms but the 9 paired members moved
  (6 carried->carried, 1 ok->carried, 1 no-grasp->carried, 1
  no-grasp->no-grasp); the same-fruit pairs **2 B-only / 3 A-only** (p = 0.8125;
  species-only 3/4, p = 0.7734; the left 0/1, p = 1.0); all unpaired Fisher
  p >= 0.35. The placed/composite moves (1->2, 28->25) are 3 episodes and the
  composite is a **relocation guard, not a win condition**, so the middle
  pre-registered branch fired and the pure falsifier bullet did not; no
  adoption. **The reason the A/B cannot settle the early-view question: the
  treatment did not present a visible first view** - the rendered target mask is
  empty at the first call in **72/75 (A) / 71/75 (B)** episodes (the left arm:
  `openarm_left_link3` 127 px vs the fruit's 16 in the probe's aligned episode;
  one episode per arm), including the belt-clear ones (25/26, 71/75). So:
  **aiming the first call at 0.399 with the reset pose does not move the left;
  the visible-first-view hypothesis is untested.** The store correction: the
  single-arm store's masks are **per-arm** (`+0.25..+0.30` zero-mask left 0.56
  (n=63) / right 0.92 (n=558) - the pooled 0.88-0.90 is the right's; the left is
  visible at its own x band, 125 frames, zero 1 %, median 0.94), while the direct
  env's left first calls at x 0.32-0.37 are empty 11/11 (A) and 6/6 (B) - a **new
  direct-env/reset mismatch** (hypothesis: the reset's arm pose/settle,
  unmeasured), **not** the store's distribution. The fire-zone zero-mask falls
  **27 % -> 18 %** (left 30 % -> 18 %) - measured; its cause is a hypothesis (B
  makes *more* zone calls, 19.0 vs 17.4 per attempt, so "the arm walks less
  upstream" is unmeasured) - but the carry class does not move.
- 2026-10-23 **the Gate-1 corrections + one new correction** (in
  `logs/p34/README.md` / `REPORT.md`): the "33 model calls" -> the first call
  p50 +0.484, the fully-hidden first-call share 26/75 = 35 %, the calls to full
  visibility p50 8 (p90 25); the "88-90 % start hidden" -> the **reset**, not
  the first call; the README's 1.25 s -> **2.85 s**; the window **p50 ~1.9 s**;
  the band **2.9 s width vs the fruit's 2.3 s travel**; the **17 mm** fruit-edge
  landing margin. New: the "demos' first view 0.399" is the **two-line** stores'
  value - the **single-arm** store `demos_v11` reads first-detectable **+0.441**
  with per-arm masks (`logs/p34/21_demos_v11.*`), so the phase-1 evidence used a
  different arm pose from the single-arm direct env. No-harm: acceptance
  **376/376 `[fruit]` identical** to `logs/p33/40_accept_final.log` (6/10,
  rate-only, fingerprint matches - the documented exception) and `selfcheck.sh`
  PASS. **The +Y belt scene lever is Phase 3 and was not run**; the arm
  occlusion is its named input.
- 2026-10-23 **the Gate-2 corrections + the commit** (B1-B4, M1-M5; itemised in
  `logs/p34/A_READ.md` section 6b and `logs/p34/PREREG.md` section 8):
  (B1) the conclusion is restated as "aiming the first call at 0.399 with the
  reset pose does not move the left; the **visible-first-view hypothesis is
  untested**" - the rendered first-call target mask is empty in A 72/75 / B
  71/75, so the treatment presented no visible first view; (B2) the pooled
  "arm occlusion is in the training data" claim is replaced by the **per-arm**
  store reads (left 0.56 / right 0.92) and the **direction** (0.399 is 42 mm
  *downstream* of +0.441), and the direct-env left emptiness at the store's own
  x band is a **new reset mismatch** (hypothesis: the reset's arm pose/settle);
  (B3) the decision rule: the primary (paired left carried) does not move
  (0/1, p = 1.0), the composite/placed moves are 3 episodes and the composite is
  a **relocation guard**, and the report script's post-batch timestamp (19:44
  vs 19:41) is stated; (B4) "24/24" is a count - the 9 paired left members
  moved; (M1) the zero-mask drop is measured, "the arm walks less upstream" is
  not (19.0 vs 17.4 zone calls); (M2) `obs_horizon=2` puts the stale reset frame
  in the first call's window; (M3) the probe is one episode/arm and ranks
  foreground candidates by pixels, not depth; (M4) the pairing guard is 0.05 m
  (docstring corrected) and both species-only reads + the left's p = 1.0 are
  quoted; (M5) 188 inserted lines at the batch pin `2e392f48` (the commit reads
  216/1 because `rl_env.py` also carries P34-B's default-identical settle
  knob). Committed with the code, the new scripts
  (`212/213/215_occlusion*`) and the `logs/p34/` evidence.

## 6. Close-out + the next lane (owner: "按你说的，继续", 2026-10-23)

**P34 closes negative on the lever, positive on the measurement.** The output
belt's occlusion is real and measured (the band y +0.52..+0.87; the demos' first
frame at 0.374 visible; the direct reset at 0.583), but the pre-registered
reset-alignment A/B (N=5x15, `FRUIT_RESET_ALIGN=1`) passes the manipulation
check on the fruit's **position** (12 % -> 96 % first-call along/belt-vis) and
does **not** move the outcome: the paired left carried class is **0 B-only / 1
A-only** (p = 1.0; the carried count is 24 in both arms but the 9 paired members
moved; the composite 28->25, placed 1->2 are 1-3 episodes, p 0.35-0.71, and the
composite is a guard, not a win). And the A/B cannot settle the early-view
question: **the treatment did not present a visible first view** - the rendered
target mask is empty at the first call in 72/75 (A) / 71/75 (B) because the
**left arm's `openarm_left_link3`** occupies it (127 px vs the fruit's 16 at the
aligned first call) - so the visible-first-view hypothesis is **untested**, not
rejected. The single-arm store does **not** show the same on the left
(per-arm: 0.56 left / 0.92 right zero-mask at +0.25..+0.30; the left visible at
its own x band), while the direct env's left first call is empty there (11/11
A, 6/6 B) - a **new direct-env/reset mismatch**, leading hypothesis the reset's
arm pose/settle (unmeasured). The knob stays default off; the code change
(`rl_env.py`, +188/0 at the batch pin; the commit adds P34-B's default-identical
`FRUIT_RESET_SETTLE`) is kept as a measurement interface; the +Y belt scene
lever was not run (its expected gain is small and the arm remains).

**The next lane (the arm occlusion)** - a second occluder, measured in the direct
env but **not** shown to be in the single-arm store's distribution:
- The measured facts: the fire-zone zero target mask 18-30 % (the left 30 ->
  18 with the alignment); the arm's link3 at the aligned first call (one probe
  episode per arm, corroborated by the aggregate counters); the store's masks
  are arm-dependent (left visible at its own band, right not); the direct env's
  left first call is empty even at the store's left-visible x band; the step-0
  frame's target mask is one frame stale and is one of the two frames of the
  first call's `obs_horizon=2` window.
- The candidate levers: (a) the camera pose (higher/closer/side) - the frames
  change -> a policy recollection; (b) the camera mounting/position on the
  cell (not the arm); (c) the arm's idle/pre-pose pose during the wait (the
  policy's own actions - a training change); (d) a wider/fisheye lens (a
  distribution change); (e) **the reset's arm pose/settle** (the cheapest: it
  is the mismatch the A/B found, and it needs its own pre-registration before
  any outcome claim).
- The pre-registration must state: the offline occlusion map for the candidate
  cameras/poses (the arm's silhouette vs the decision zone, the fruit's
  fraction at the first call/fire zone), the OOD cost (a recollection), the
  endpoints (the left's acquisition/carried, the P33 protocol), the falsifier -
  and a **manipulation check on the rendered target mask**, not only on the
  analytic belt visibility (the Gate-2 lesson: the treatment must present the
  view it claims to test).
- The bounded first deliverable: the offline measurement + the
  recommendation (which camera/pose, if any, removes the arm from the decision
  zone without a place/reach cost); the A/B is the named follow-on (owner's
  budget: a recollection).

**Phase plan (the continuation)**: A - **done** (the P34 Gate 2 + the record +
the commit); B - the arm-occlusion pre-registration + the camera/pose
measurement; C - the integration/docs/commits. Oracle: 3 gates.

- 2026-10-23 **Phase B measured — the per-arm store baseline, the reset pose,
  and the first view** (`logs/p34/B_READ.md`, `B_PREREG.md`,
  `scripts/216_store_arm_baseline.py`, `B_mask_probe.py` + `B_probe_*`, 15
  one-episode renders). The Gate-2 B2 premise (the direct env's left first call
  0-4 % visible at the aligned along/x vs the store's 89-91 %) is **the stale
  first frame, not the arm pose**: in the 150 A/B episodes `first_px > 0` in
  exactly the **10 episode-0s** (one per run, both arms; the label dump shows
  the instance resolution is correct and the mask at the reset is 0 while the
  fruit is visible - the frame predates the reset). The valid episodes: the
  **left's first call is visible** (`px/px_max` 0.98 at 0.399, 0.88 at 0.439),
  the reset's joints **are** the grasp waypoint (|dq|max 0.019 left / 0.026
  right) and the **settle is a pose null** (20/60/120 identical to 0.001 rad);
  the store's frame 0 is a different stable pose (|q0-grasp| 0.16-0.33 rad, the
  dynamic catch's hover) - a real distribution difference, not the cause. The
  **store baseline per arm** (rendered/analytic and `213`-normalised): v11 left
  0.86/0.92 (right 0.21/1.00), v12 left 0.78/0.76, v13p left 0.76/0.92, p33
  left 0.64/0.94; the per-arm decision zone is 0.80 (v11 left) vs 0.54 (right)
  zero-mask - the pooled 0.88-0.90 was the right's; and **v11's own x band is
  0.323-0.348**, so the single-arm store never saw the patch sheet's outer band
  (x < 0.26 in **44-48 %** of the first calls). The surviving first-view
  occlusion is the **inactive left arm parked at `ready` over that outer band**
  (`link3` 127-199 px inside the target's bbox; `first_rel` **0.11 -> 0.13** at
  0.399 -> 0.441 with `q` unchanged) - no along aim touches it, and the 260/261
  probe's `openarm_left_link3` was that *inactive* arm (its episode is
  `arm=right`), not the left arm's own view. The 0.441 aim also sits on the
  belt's near edge for >= 58 mm fruit and the reset can return below it
  (`along_reset` 0.443 in one left process). **The along-only A/B is
  pre-registered as conditional and not to be run**; the named next lever is the
  arm park / camera sightline (outer band), with the reset-pose (hover)
  alignment as the low-expectation secondary. No default changed; the code
  change is the `[align]` diag's `settle`/`q_r`/`q_f`/`px_max`/`pfc`/`pcm` +
  `FRUIT_RESET_SETTLE` (default 20 = shipped). `selfcheck.sh` PASS (0 failures,
  1 skipped).
