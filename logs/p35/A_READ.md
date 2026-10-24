# P35 phase 1 — the inactive arm's park and the sightline: measured, and the lever is the park

Measured 2026-10-24 on `21b9acc` (clean tree). **Default off, no shipped default
changed**; the code change is `rl_env.py` `FRUIT_ARM_PARK` (+50 lines, inert when
unset) and the new `configs/arm_parks.json`. The instruments: the park sweep
`logs/p35/park_probe.py` (one scene, 53 parks x 2 arms, rendered silhouette +
depth + both arms' link poses), the offline map `scripts/217_arm_park_map.py`,
the long-hold probe `logs/p35/park_hold.py`, the static-fruit render
`logs/p35/park_render_probe.py`, and two one-episode first-call renders
(`logs/p35/40/41`). Pre-registration for the A/B: `logs/p35/PREREG.md`.

**The one-line answer.** The inactive **left** arm at the shipped `ready` pose
sits directly between the head camera and the belt's approach band: it covers
**98 %** of a 58 mm fruit's disc at along +0.35, **57 %** at +0.40 and **0.382**
on average over the scored stream, while the belt shows the fruit there
(`212` visible 1.00). The park named **`back`** (j1 -0.50 / j2 -0.60 / j4 -0.50
rad from `ready`) moves the arm up and downstream into the spawn corner and
takes the marginal cover to **0.002** — the arm stops costing any visibility the
belt would have given. A static 68 mm pear at (x 0.219, y +0.399) reads **0.378
visible at `ready` -> 0.878 with `back`** rendered; a 58 mm fruit at (0.19,
+0.35) reads **0.000 -> 0.953**. Every camera pose is worse than the park
(best: eye x -0.10, marginal cover 0.075 against the park's 0.002), so **the arm
park is the lever; the camera is second**.

## 1. The inactive arm's pose path (the call that sets it)

**Policy path (the direct env).** `SortingRLEnv.reset` — with
`presentation="direct"` it loops over **both** arms and calls
`arm.set_gripper(arm.OPEN)` then
`arm.teleport_joints(waypoints["arms"][name]["ready"])`, and *then* puts the
active arm at `grasp` (`rl_env.py` lines 1386-1401). Nothing moves the inactive
arm afterwards: the policy's `act` writes only the active arm's dofs, so the
inactive arm is a **static scene element at `ready` for the whole episode**. The
warm-up at construction parks both arms at `ready` too (lines 1019-1025).

**Scripted path.** `tasks.go_ready` -> `_ready_move` -> `_blend_to(side, ready)`
with `_lift_clear` / `_ready_transit` routing around the main conveyor; the
`ready` jaw target is `(pick_x, pick_y +- 0.05, belt_top + 0.20)` =
**(0.34, +-0.05, 1.37)** (`tasks.jaw_target`). That is the pose that occludes:
measured left jaw `(0.333, 0.055, 1.363)`, `link3` at `(0.061, 0.178, 1.483)` —
0.55 m from the camera, i.e. the first thing on the ray to the approach band.

**The lever.** `FRUIT_ARM_PARK=<name>` reads `configs/arm_parks.json` at init and
substitutes the named 7-vector for the `ready` teleport of that side only. Unset
(or `=ready`): no file read, one `dict.get` per arm, the shipped call unchanged.
Only `left` is defined — see section 3 for why the right stays shipped.

## 2. The candidate parks (53 per side) and what each costs

`park_probe.py` sweeps `ready` (candidate 0) plus one-joint deltas on each of the
seven joints (0.25/0.5/0.8 rad, both signs, clipped to the limits), six named
multi-joint folds and a four-step ladder of the deepest fold. Per park it
records both arms' `link_pose` chains, the rendered silhouette, the depth frame,
the joint hold at 90 ticks, the lowest link origin, whether a link origin sits in
the belt's slab footprint, the parked-to-active link gap and the torso gap. A
read is accepted only when two consecutive renders are byte-identical
(segmentation **and** depth) — the stale-frame guard P34-B did not have.

The top of the table (shipped camera; `cover` = the fraction of the fruit's disc
hidden by the arm, depth-gated so "behind the fruit" never counts; `cost` = the
share of the *stream* the belt would have shown and the arm hides, i.e. the
marginal loss):

| park | hold @90 | px | hand over belt | cost | stream | by along +0.30/+0.35/+0.40/+0.45 | pear 68 mm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ready` (shipped) | 0.0132 | 3497 | 0.115 m | **0.382** | 0.38 | 0.81/0.98/0.57/0.01 | 0.55 |
| **`back`** | 0.0316 | 4155 | 0.287 m | **0.002** | 0.08 | 0.00/0.00/0.00/0.00 | 0.00 |
| `side_deep` (runner-up) | 0.0114 | 1830 | out (x~0) | 0.036 | 0.04 | 0.04/0.01/0.00/0.00 | 0.00 |
| `j1+080` | 0.2090 | 1842 | out | 0.007 | 0.01 | 0.00/0.00/0.00/0.00 | 0.00 |
| `j1-080` | 0.0120 | 6067 | 0.416 m | 0.381 | 0.58 | 0.34/0.49/0.87/1.00 | 0.68 |
| `j2+080` | 0.0081 | 3876 | 0.125 m | 0.192 | 0.19 | 0.00/0.00/0.00/0.00 | 0.00 |
| `high` | 0.0051 | 3815 | 0.134 m | 0.190 | 0.19 | 0.00/0.00/0.00/0.00 | 0.00 |
| `fold_85` | 0.0154 | 2213 | out | 0.142 | 0.14 | 0.26/0.10/0.03/0.01 | 0.00 |
| `low` | 0.0400 | 2719 | 0.140 m | 0.342 | 0.44 | 0.41/0.63/0.73/0.64 | 1.00 |

What the sweep says:

* **No single-joint move clears the band without relocating the occlusion.**
  `j2+080` and `high` clear the approach and the first view (0.00 from +0.30 up)
  and move the arm onto the **decision zone** (+0.20/+0.25: 0.90/0.63 for
  `j2+080`, 0.87/0.65 for `high`); `j1-080` covers *more* (+0.40/+0.45:
  0.87/1.00); `fold_85` (the deepest fold at 0.85 scale) re-enters the band at
  0.41/0.33 because its hand lands on the belt's inner edge (x 0.102).
* **`j1+080` is the lowest-cost pose measured (0.007) and it is not a park.**
  Clipped at the joint limit it settles 0.209 rad from the command and puts a
  link below the belt top (z 1.141, beside the belt). Rejected on the hold.
* **`back` is the measured winner** and it is *holdable*: 0.0316 rad at 90 ticks,
  **0.0007 rad over 900 ticks** and a 0.3 mm jaw drop (`30_park_hold.log`), hand
  0.287 m above the belt, 0.187 m from the active arm's link chain, 0.688 m from
  the torso link. Its residual occlusion is the **spawn corner** (+0.50/+0.55:
  0.10/0.54) where `212` already reads the belt at 0.17/0.00 — so it costs 0.002.
* `side_deep` is the runner-up: clears +0.30 and above, leaves 0.11/0.13 at
  +0.20/+0.25 (the belt's inner edge, x 0.19, where its folded hand sits at
  x 0.05), and holds to 0.0001 rad / 900 ticks.

## 3. The right arm is not part of the lever (measured)

The same sweep for the **right** arm at `ready` reads **0.00** cover on every
scored pose: its `ready` pose is on the -y side of the station and never crosses
the camera's ray to the belt. Its `back` vector also **fails**: 0.174 rad hold
residual and the fingertip in the belt footprint (z 1.172). So the park is
**one-sided, left arm only** — which also fixes the population the treatment can
act on: the direct env presents grade B/C to the **right** arm, so the lever's
endpoint is the right arm's outcome (PREREG section 3).

## 4. The rendered checks (the map's own validation)

The offline map's `cover` is computed from the rendered arm mask + the depth
frame, so it needs an independent read. `park_render_probe.py` places four
static fruit-sized spheres at the map's poses and counts *their own* instance
pixels (current frames, two identical renders required):

| proxy (x, y, d) | `ready` | `back` | `side_deep` |
| --- | --- | --- | --- |
| pear (0.219, 0.399, 68 mm) | **0.378** | **0.878** | **0.878** |
| outer_mid (0.190, 0.350, 58 mm) | **0.000** | **0.953** | 0.829 |
| inner (0.300, 0.400, 58 mm) | 0.051 | 0.940 | 0.940 |
| outer_edge (0.230, 0.400, 58 mm) | 0.016 | 0.105 | 0.105 |

* The map and the render agree within **0.07** at the pear, `outer_mid` and
  `inner` (map cover 0.55/1.00/0.90 vs render 0.62/1.00/0.95). The pear/proxy
  differences are the analytic-area normalisation: a fully visible proxy reads
  0.878-0.953, not 1.00, so quote the rendered fraction with the pose, not as an
  absolute 1.0.
* `outer_edge` stays at 0.105 visible with either park while the map's **arm**
  cover there is 0.65 at `ready` and 0.00 with either park: the remaining
  occluder is the **output belt's frame** (`/World/OutputBeltP/FrameN`, the same
  prim that dominates the first-call bboxes), not the arm. The park cannot fix
  that one - it is a different lever (the belt's structure), and it is why the
  outer-band edge point is not part of the manipulation-check band.
* The picture `50_parks.png` shows the three parks' silhouettes with the proxy
  discs: at `ready` the arm lies across the discs, at `back` it is a column in
  the spawn corner, at `side_deep` it is a horizontal fold at the robot's side.

## 5. The camera alternatives (rendered, not modelled)

One `RtxCamera` per pose at the shipped focal/aperture/resolution, the inactive
arm at `ready` (the shipped park). The shipped pose rendered through its own
camera reproduces the head camera's mask at **IoU 0.959 (left) / 0.937 (right)**
— the equivalence check before any other pose is priced. Marginal cost and the
mean visible fraction over the stream:

| camera | cost | visible (belt+arm) | first view cover | pear 68 mm |
| --- | --- | --- | --- | --- |
| shipped (2.00 m) | 0.382 | 0.39 | 0.15 | 0.56 |
| x -0.10 | **0.075** | 0.69 | 0.01 | 0.03 |
| y -0.25 | 0.327 | 0.44 | 0.83 | 0.51 |
| y +0.25 | 0.190 | 0.58 | 0.00 | 0.00 |
| z 2.20 | 0.303 | 0.47 | 0.00 | 0.02 |
| z 1.80 | 0.416 | 0.35 | 0.66 | 1.00 |
| x +0.12 | 0.377 | 0.39 | 0.12 | 0.81 |

The best camera (`x -0.10`, i.e. the mount moved 0.15 m back) reaches cost
0.075 / visible 0.69; the arm park at the shipped camera reaches **0.002 /
0.77**, which is the belt-only ceiling. Every camera also changes the whole
frame (the fruit's apparent size, the belt's shadow), so it is dominated twice.

## 6. The first-call render, the stale frame, and the P34-B correction

Two one-episode renders at seed 77 (the outer-band pear), park off vs
`FRUIT_ARM_PARK=back`:

* **The first-call mask is not a usable manipulation check.** At the shipped
  reset the fruit is at along +0.541, where `212` reads the +Y belt at **0.00**;
  the first call (`step 4`) reads `target_px=0` and a bbox of
  `OutputBeltP/FrameN` 173 px + `Belt` 67 px with **no arm instance** (the fruit
  is belt-hidden there, so this call cannot discriminate the arm whether or not
  the frame is current). With `back` the same call reads `target_px=0` and a bbox of
  `openarm_left_link4` 105 px + `link3` 73 px: the park applied (the arm moved
  into the spawn corner), the frame is still the stale one, and the fruit is
  belt-hidden either way. So the PREREG's check is read **per call**, at the
  first call whose target along is in +0.30..+0.45 (the band the arm occludes and
  the belt does not): the target's mask against the episode's own maximum plus
  the parked arm's pixels in its bbox - the counters the phase-1 `[probe]` row
  already prints, as a default-off env diagnostic. The reset-time render is
  *not* enough: at the shipped reset the belt, not the arm, is the occluder.
* **The park never touches the active arm.** The first version of the reset
  loop applied the park to every arm; because `teleport_joints` runs its own
  30-tick settle, that would have added a settle's worth of belt travel to a
  left-arm episode (the active left would be parked, then teleported to
  `grasp`). The guard is now `name == active -> no park`, and the check is
  `42_firstcall_left_active.log` (seed 101, the A-grade apple, park on): its
  reset reads `along_reset=+0.443`, first call `+0.439`, `target_px=158` - the
  P34-B left control's numbers exactly (`B_rel_L_ship.log`) - so the treatment
  is inert on left-arm episodes, as designed. The same row also shows no arm
  instance in the left's first-view bbox (`Fruit_13` 158 + belt 54 + frame 28),
  i.e. the inactive **right** arm at `ready` does not occlude the left, which is
  the map's 0.00 for the right side.
* **P34-B's right-arm numbers are corrected.** Its `0.077/0.131` at along
  +0.441/+0.445 are read off that same pre-reset frame: the bboxes there are
  **222/213 px of `/World/Conveyor/Belt`** with the fruit absent, not the arm
  (the arm contributes 24/12 px *beside* the disc). Its +0.399 row is real — the
  arm dominates that bbox (127 px) — and the phase-1 proxies quantify the case:
  the pear is 0.378 visible at `ready`, not 0.115. The plan's premise holds for
  **along +0.30..+0.45** (the approach/decision band, cover 0.81-0.98), not for
  the first call at the shipped reset, where the belt is the occluder.

## 7. The recommendation

**Run the A/B on `FRUIT_ARM_PARK=back`** (the park is the lever; the camera is
second and not proposed). Reasons, in the measured order: it removes the arm's
marginal cost on the belt's visibility (0.382 -> 0.002, i.e. the stream reaches
the belt-only ceiling 0.77), it holds (0.0007 rad / 900 ticks), it keeps the hand
0.287 m above the belt and 0.187 m from the active arm, its residual occlusion
lands where the belt already hides the fruit, and it needs no scene, camera or
calibration change. `side_deep` is the pre-registered fallback if `back`'s hold
fails in-scenario.

**Implementation plan (phase 2).** `FRUIT_ARM_PARK=back` on the direct env, the
P33 A/B protocol (N=5x15, seeds 77/101/202/303/404, policy seed 11, interleaved),
the per-call park check (M1/M2, `PREREG.md` section 2) +
`FRUIT_RESET_ALIGN_DIAG=1` + `FRUIT_ACQ_DIAG=1` on both
arms, endpoints per `PREREG.md` section 4 (primary: the right arm's paired
carried-not-placed class), and the no-harm set (selfcheck; the scripted line does
not touch `rl_env.py`). Phase 3 ships **nothing** unless the recollection gate in
`PREREG.md` section 5 is met: the knob stays default off either way.

## 8. Files, provenance, no-harm

* `src/fruit_sorting/rl_env.py` — `FRUIT_ARM_PARK` / `FRUIT_ARM_PARK_FILE`
  (+50/0; `arm_park` in the manifest; both branches exercised: `40` off, `41`
  on, `42` the active-arm guard). md5 `6026267e` (the pre-guard file was
  `96a02e84`; the guard changes only which arms the park is applied to).
* `configs/arm_parks.json` — `ready` (null), `back`, `side_deep`; left only.
  md5 `42ab4fb7`.
* `scripts/217_arm_park_map.py` — the offline map (rendered masks + depth, the
  `212` camera model, the disc occlusion, the camera table, the `by_along`
  profiles). md5 `d73618f9`.
* `logs/p35/park_probe.py` (`2ae67e24`) — the sweep, `10/11/12_park_sweep*.log`;
  the shipped-camera sweep of record is `12` (53 parks/side, the fold ladder
  included) and it is what `park_sweep.json` (`4d15513f`) + `park_masks.npz`
  (`565e66c8`, 7.7 MB, 571 arrays: silhouette, active-arm mask and
  depth per park, plus the camera pass) hold.
* `logs/p35/park_hold.py` (`6ba41ab0`) + `30_park_hold.log` — the 900-tick hold.
* `logs/p35/park_render_probe.py` (`6cb0d019`) + `50_proxy_render.log` — the
  static-fruit validation, the label dump (`/World/Proxy_*` ids 73-76).
* `logs/p35/40_firstcall_ready.log` / `41_firstcall_back.log` /
  `42_firstcall_left_active.log` / `43_firstcall_nolabels.log` — the one-episode
  renders (park off; park on with the right active; park on with the left
  active; the knob-off repeat of P34-B's `B_rel_R_ship` scenario);
  `50_parks.png` — the three silhouettes.
* A **rejected instrument**: an analytic capsule model (links' origins + a
  radius fitted to each link's rendered area) was written first and measured
  against the rendered silhouette over 20 poses x 2 arms: the right arm matched
  exactly (0.00), the **left was optimistic by up to +1.00 and +0.37 on
  average** because a link's area-fitted capsule is thinner than its housing.
  It is not used anywhere; the camera table above is rendered.
* **No-harm**: `scripts/selfcheck.sh` PASS (see `60_selfcheck.log`, re-run after
  the active-arm guard); the scripted acceptance is **not** re-run (its path does
  not touch `rl_env.py`) and the knob is unset by default. `configs/*` otherwise
  untouched. The knob-off episode (`43`, the same scenario as P34-B's
  `B_rel_R_ship`) reproduces that record's per-call `along`/`x`/`aw`/`target_px`
  on all 13 calls with the joints agreeing to **+-0.001 rad** - the residual is
  the policy loop's documented run-to-run variance, not a branch change.
* **Risks.** (a) The lever's population is the right arm only (0.625 of the
  mix); the left is a no-op control, so the effective N is ~47 paired attempts
  per arm and the primary is a sign test on class conversions — a screen, not a
  confirmatory test (`PREREG.md` section 3). (b) The map's `cover` is a
  *geometric* occlusion on a current frame; the policy's own first call is a
  stale frame, so the treatment's benefit in the policy's terms is bounded by
  the frame lag until that is fixed (a separate item, P34-B section 3). (c) The
  park shifts every frame (static scene change): a null is OOD-confounded, a
  positive needs a recollection to ship. (d) `back`'s hold was measured in an
  empty scene; in-scenario the active arm's motion cannot touch it
  (`enabledSelfCollisions=0`) but its 0.187 m link gap ties `side_deep`'s for the
  smallest measured among the holdable parks, and its spawn-corner silhouette is
  closer to the camera than `ready`'s (4155 vs 3497 px).
