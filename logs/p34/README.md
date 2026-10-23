# P34 phase 1 — the occlusion of the main belt's fruit by the raised output belts

Evidence directory. Phase 1 is measurement only: no `src/` change, no shipped
default, no commit.

## Files

| file | what it is |
| --- | --- |
| `10_map.txt`, `10_map.json` | `scripts/212_occlusion_map.py`: the analytic visibility map (the band, the visible fraction at the policy's waypoints, the -Y belt, the camera's frame coverage) |
| `11_map_levers.txt`, `11_map_levers.json` | the same with `--levers`: the lever candidates and their occlusion gain |
| `20_demos.txt`, `20_demos.json` | `scripts/213_occlusion_demos.py`: the recorded demos' target mask vs world y (distance-normalised), the first-detectable frame, the camera-model check (both stores) |
| `21_demos_v11.txt`, `21_demos_v11.json` | the same check on the **single-arm** store `demos_v11` (the direct env's own lineage): first-detectable p50 **+0.441**, and **per arm** `+0.25..+0.30` zero-mask **left 0.56 (n=63) / right 0.92 (n=558)** - the pooled 0.88-0.90 is the right's; the left is visible at `+0.35..+0.40` (zero 0.00, median 0.93) and at its own x band (x 0.32-0.36, y 0.35-0.45: 125 frames, zero 1 %, median 0.94) - phase 2's store correction |
| `PREREG.md` | P34 phase 2's pre-registration (the reset-alignment A/B, the manipulation check, the endpoints, the falsifier) |
| `A_READ.md` | P34 phase 2's read: the A/B, the manipulation check, the occluder probe, the verdict |
| `A_ab/`, `A_align.txt`, `A_verdict.txt`, `A_class_split.txt`, `A_pairs.txt`, `A_mech.txt` | the phase-2 A/B (10 runs x 15 episodes) and its read-only reports |
| `260/261_probe_*.log`, `260_mask_probe.py` | the occluder attribution probe (the instance ids inside the target's projected bbox) |
| `73_accept_no_harm.log`, `74_accept_identity.txt` | the phase-2 acceptance (knob unset): 376/376 `[fruit]` lines identical to `logs/p33/40_accept_final.log` |
| `50_policy.txt`, `50_policy.json` | `scripts/215_occlusion_policy.py`: the direct-policy logs' reset position vs the band, the outcome cuts, the trigger fire positions |
| `frames/` | annotated head-camera frames: `edge_y0.479.png` (the tomato at the band's edge, half hidden), `annot_vis25.png` / `annot_zero25.png` (the fruit at y=0.23 / 0.30 with the arm over it), `y+0.45*` |
| `probe_attempt/` | the attempted with/without-belt render probe: its script (archived out of `scripts/` because it did not produce a usable frame), the logs and the identical with/without images (see "The render pair" below) |
| `explore_projection.py` | the first-pass camera-model fit (the nominal 16 mm/36 mm intrinsics are within 1.8 px; kept for provenance) |

## The measured geometry (analytic, `10_map`)

Camera (0.05, 0, 2.00) -> (0.34, 0.22, 1.10), 16 mm on a 36 x 20.25 mm sensor,
240 x 424: **fx = fy = 188.44 px, cx = 211.5, cy = 119.5, hFOV 96.73 deg**. The
recorded demo masks confirm it: the mask centroid vs the projected fruit body
centre reads **1.57 px median / 3.76 px p90** (n = 3939) on `p33_pear` and
**1.80 / 3.44** (n = 2786) on `demos_v12`.

The +Y slab (y 0.425-0.675, z 1.30-1.35, x 0.10-1.20) casts a shadow on the main
belt. For a fruit of diameter d at x = 0.20-0.36:

| d | top point blocked | vis < 0.99 | vis < 0.50 | vis < 0.01 | vis > 0.99 | visible window to y=0.301 |
| --- | --- | --- | --- | --- | --- | --- |
| 31 mm | 0.485..0.905 | 0.475 | 0.490 | 0.510 | 0.945 | 0.174 m / 1.45 s |
| 58 mm | 0.465..0.875 | 0.450 | 0.485 | 0.515 | 0.950 | 0.149 m / 1.24 s |
| 69 mm | 0.460..0.865 | 0.440 | 0.480 | 0.520 | 0.950 | 0.139 m / 1.16 s |

The bbox fraction (visible pixels / the fruit's projected bbox) reads 0.79 at
y=0.40, 0.14 at 0.50, 0.00 through the band, 0.27 at 0.90 and 0.74 at 0.95, so
the silhouette and the bbox agree on the band. So the **fully hidden band is y = +0.52..+0.87**:
its **width is 0.355 m = 2.96 s of belt travel** at 0.12 m/s, but a fruit is
released at the spawn **+0.68**, i.e. 0.155 m *inside* the band, so **a fruit's
own travel through it is 0.165 m = 1.38 s** and its travel from the spawn to
full visibility (+0.40) is **0.28 m = 2.33 s** — the band's 2.9 s is a width,
not the fruit's exposure. The 0.45-0.52 and 0.87-0.95 edges are the partial
transitions. The **x column is a null**
(±0.01 m); the **diameter moves the near edge by 0.035 m** (a taller fruit emerges
later, because its top is closer to the slab). The visible fraction at the
waypoints (d = 58 mm, x = 0.28): **spawn 0.68 = 0.00**, the first model call
0.551 = 0.00, 0.455 = 0.93, 0.50 = 0.17, the trigger's fire zone 0.30 = 1.00,
the station 0.00 = 1.00. The -Y belt's band is -0.465..-0.87, i.e. downstream of
the station and at the very bottom of the frame (the frame's edge on the belt
centre line is y ~ -0.52); it occludes no incoming fruit.

The two-line catchable band (world y >= 0.40 left / >= 0.30 right, stocked to
0.73) overlaps the occlusion band by 0.21 m = **64 % of the left's 0.33 m and
49 % of the right's 0.43 m**; the right's 0.10 m longer band is its station
offset (1.30x). The scripted selector reads no camera, so this is a geometric
coincidence, not the mechanism (the P33 census already names the grade drought).

## The recorded evidence (`20_demos`)

* **The recorded demos never see the fruit inside the band**: the recording starts
  at the wait loop - frame 0 at world y **p50 0.374** (p10 0.191, p90 0.438),
  **0/180 and 1/158 inside the band**, first-detectable along p50 0.399 (p10
  0.255, p90 0.48-0.51) in both stores and both arms. The rendered frame at the
  edge (`frames/edge_y0.479.png`) shows the slab's edge cutting the tomato's
  top. The direct env's reset is the opposite: **88-90 % of its episodes are
  reset with the fruit inside the band** (`50_policy`). Note what that number
  is and is not: it is the **reset** state (the selection header), and **no
  model call happens there** - the direct loop calls the model only after the
  second frame at control step 4 - so it is not the model's first view. The
  first *model* call meets the fruit at **+0.455..+0.551 m** (the P31 anatomy),
  i.e. at the band's edge where the visible fraction is 0.00 at 0.551 and 0.93
  at 0.455: a **train/eval mismatch at the first observation**, but a partial
  one, and the phase-2 control arm measures its per-episode distribution
  (below).
* The visible fraction below the band reads **0.93-0.98** at world y 0.35-0.45
  (the 1.0 reference is the episode's own maximum, distance-normalised).
* A second, phase-dependent occluder is the **arm**: at world y 0.15-0.30 the
  zero-mask fraction is **0.23-0.60** (the scripted descent / the forearm over
  the belt). It is not the output belt, and it is the *decision zone's* upstream
  half - the policy env's arm sits at the grasp pose there too, so it is a
  candidate the owner's hypothesis does not name.

## The policy evidence (`50_policy`, 150 direct episodes from the P31 A/B)

* The reset position is **p50 +0.583** (p10 0.516, p90 0.662) and **88-90 % of
  the episodes are reset with the target fully hidden** (analytic vis < 0.01);
  the current tree's P33 A/B reproduces it (p50 0.587, 88 %). But the reset is
  a state with **no model call** (the first call comes after the second frame at
  control step 4), so that share is not the model's first view. The P31
  anatomy's first model call at 0.455-0.551 is the fruit after 0.03-0.13 m of
  setup - at the band's edge; **phase 2 measured it at p50 +0.484** (150
  direct episodes, the A/B control).
* The hidden run from the reset to the visibility onset is **p50 0.133 m =
  1.11 s** (p90 0.212 m / 53 calls) **of belt travel, but it carries no model
  calls**: measured from the first model call, the analytic fully-hidden share
  is **26/75 = 35 %**, the fully-hidden model calls p50 **0**, and the calls to
  full visibility p50 **8** (p90 25) - the "33 model calls" was the travel
  quotient, ~4x the model's own run.
* **The trigger is never in the band**: fire dy 0.184-0.305 m (n = 150, the ACQ
  lead 2.05-2.27 s), 0/150 inside 0.45-0.95. With the shipped 0.9 s lead the
  fire sits at y ~ 0.108, i.e. **2.85 s after the fruit emerges** (0.45 -> 0.108
  over 0.12 m/s); the **1.25 s** that the phase-1 text quoted is the *minimum*
  window from the band's edge to the fire **zone's upstream end** (0.301), not
  to the fire. The delivered window is longer: with the ACQ lead the fire reads
  **p50 0.226 m**, so from the band's near edge (0.45) it is **p50 ~1.9 s** of
  visible fruit before the fire (`(0.45 - 0.226)/0.12 = 1.87 s`); the 1.16-1.45 s
  figure is the worst case (a fire at the zone's upstream end).
* **No reproducible outcome dose-response**: the P31 corpus reads left 32 %
  (y0 < 0.599) vs 4 % (y0 >= 0.599) but the P33 corpus reads 0 % vs 16 % -
  opposite directions - and within the left's large-fruit group the P31 cut is
  2/15 vs 1/15. The reset position is the feed schedule's backlog, not
  randomised, and it correlates with the fruit's diameter (small fruit ride in
  lower and succeed more).

## The levers (`11_map_levers`)

| lever | occlusion gain (window to y=0.301) | the cost it was measured against |
| --- | --- | --- |
| +Y belt y +0.04 | 1.24 -> 1.66 s | the place command y=0.50 (at the reach boundary) and the release \|y\| p10 0.512/0.541 vs the rail's inner face 0.400+delta: +0.04 keeps 35 mm of hand margin (0.50-0.465) and ~17 mm of the *fruit's* landing margin at the p10 release (0.512-0.030-0.465), +0.08 is 5 mm, +0.12 puts the hand inboard |
| +Y belt top_z +0.10 | 1.24 -> 1.95 s | the transfer waypoint +0.10 m at the reach boundary; the rail clearance is unchanged (both move); the vertical reach is unmeasured (needs `422`) |
| inner edge +0.05 (width 0.25 -> 0.20) | 1.24 -> 1.74 s | identical to the y lever for the inner edge (the release p10 0.512 vs the rail 0.450), plus a narrower landing zone |
| camera z 1.80 | 1.24 -> 1.45 s | the frames change: the policy is frame-conditioned (a recollection) |
| camera y -0.25 | 1.24 -> 1.53 s | the same, plus the head mast moves |
| camera z 2.20 / y +0.25 | 1.12 / 0.87 s (**worse**) | - |
| fruit x band | ±0.01 m (**null**) | - |
| reset alignment (policy interface) | the demos' frame 0 at along 0.399 is visible; the env's reset at 0.583 is not | ~20 lines in `rl_env._reset` + a re-baseline (the direct A/B history is on the old reset) |

## Phase 2 (2026-10-23) — the reset alignment A/B (the first-view lever)

Pre-registration `PREREG.md`; read `A_READ.md`. `FRUIT_RESET_ALIGN=1` (default
off, `rl_env.reset`, direct only; **+188/0** lines at the batch's pin
`2e392f48` - the committed file reads +216/1 because it also carries P34-B's
default-identical `FRUIT_RESET_SETTLE`) advances the line after the
reset's setup so the **first model call** is at along 0.399 (the two-line stores'
first view; 42 mm **downstream** of the single-arm store's +0.441). N = 5 x 15
per arm, seeds 77/101/202/303/404, one interleaved batch, `moe_v13s`
(`61da390a`), the P33 W8-A scenario; both arms carry the same diagnostics.

| | A (control) | B (aligned) |
| --- | --- | --- |
| first-call along p50 | +0.484 | +0.398 |
| 212 visible fraction p50 | 0.41 | 1.00 |
| manipulation check (\|along-0.399\|<=0.02 and vis>=0.90) | 9/75 = 12 % | **72/75 = 96 %** |
| pooled placed | 20/75 (27 %) | 23/75 (31 %) |
| left (n / placed / no-grasp / carried) | 29 / 1 / 4 / **24** | 27 / 2 / 1 / **24** |
| same-fruit pairs (pooled / left) | - | 2 B-only/3 A-only (p=0.8125) / 0/1 (p=1.0) |
| cycle ticks p50 | 1859 | 1800 (-3.2 %) |
| model calls per attempt p50 (zone calls) | 60 (17.4) | 44 (19.0) |
| fire-zone zero target mask (left) | 27 % (30 %) | 18 % (18 %) |
| **rendered** first-call target mask empty | **72/75** | **71/75** |

**Aiming the first call at 0.399 with the reset pose does not move the left, and
the visible-first-view hypothesis is untested.** The manipulation check passes
(the fruit's along and its analytic belt-only visibility), but the *rendered*
first-call target mask is empty in 72/75 (A) and 71/75 (B) episodes - the **left
arm** occludes both arms' first view (`openarm_left_link3` 127 px vs the fruit's
16 at the aligned first call), including the belt-clear ones (25/26, 71/75). So
the treatment moved the fruit, not its visibility, and the A/B compares two
arm-occluded first views. The primary does not move: the paired left carried
class is 0 B-only / 1 A-only (p = 1.0); the left's **carried count is 24 in both
arms but the members moved** (6 carried->carried, 1 ok->carried, 1
no-grasp->carried, 1 no-grasp->no-grasp of 9 pairs). The placed/composite moves
(1->2, 28->25) are 3 episodes and non-significant (Fisher 0.35-0.71); the
composite is a relocation guard, not a win condition, so the pre-registered
rule's middle branch fired and the pure falsifier bullet did not - **no
adoption**. The store correction: the single-arm store `demos_v11` is **not**
arm-occluded on the left (per arm: `+0.25..+0.30` zero-mask left 0.56/right
0.92; the left is visible at its own x band, 125 frames, zero 1 %, median 0.94),
while the direct env's left first calls at x 0.32-0.37 are 11/11 (A) and 6/6 (B)
empty - a **new direct-env/reset mismatch** (hypothesis: the reset's arm
pose/settle), not the store's distribution. The decision-zone zero-mask drop
(left 30 % -> 18 %) is measured; its cause is a hypothesis (B makes *more* zone
calls, 19.0 vs 17.4 per attempt). The knob ships **default off, not adopted**;
the scene lever (+Y belt y +0.04) was **not** run (Phase 3) and the arm
occlusion is its named input. No-harm: 376/376 `[fruit]` lines identical to
`logs/p33/40_accept_final.log`.

`align_report.py` / `A_align.txt` carry a **post-batch** timestamp (19:44 vs the
batch's last log 19:41); the script is read-only over `A_ab/*.log` and the batch
logs are unchanged - quote it as a post-batch read (`A_READ.md` section 6b). The
per-arm store baseline is `scripts/216_store_arm_baseline.py` -> `B_store.*` +
`B_probe_*.log` (the B2 re-derivation: rendered visible fraction vs `212`, the
frame-0 arm pose, the `--ab` join).

## The render pair

`FRUIT_SCENE_PARTS` drops the belts, so a two-run with/without pair is the
supported path. It was attempted (`40_probe_with.log`, `41_probe_robot.log`,
`30-34_dbg.log`) and **did not produce a usable frame**: the head camera's
annotators return one frame per run (hiding the belt roots and re-rendering came
back bit-identical, with and without a physics step in between), and the probe's
fruit never appeared in the instance map. The rendered evidence in this phase is
therefore the recorded demo frames + the camera-model check above, not a
with/without render.
