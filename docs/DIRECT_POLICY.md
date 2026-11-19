# The direct policy lane: vision + touch, end to end, 6.3 % -> 68.8 %

This page is the authoritative record of the **direct/policy** lane: the cell where one
learned diffusion policy does approach -> grasp -> place on the moving-belt cell with
**no truth goal, no external trigger and no scripted primitive handover**. Every number
here has a section in `logs/p145/RESULTS.md` (S1-S64) and a commit behind it; the
pointers are at the end.

## 1. What "end to end" means here, stated honestly

The learned policy owns the **decisions** and the approach; two **measured-target
servos** own the last centimetres of the two contact events. That is a *hierarchical*
policy, and it is written down rather than implied:

| layer | owns | instrument that verified it |
|---|---|---|
| diffusion policy (`p177_full`) | the approach, *when* the contact phase begins, the finger's close, and which bin | the phase gate + the committed ramp's `[close]` row |
| contact servo (`FRUIT_CONTACT_SERVO`) | the aim for the ~0.2 s before the close, re-derived **every tick** from the *perceived* fruit | `[servo]`: aim error, `hold=`, the latch's `xy/dz` |
| place servo (`FRUIT_PLACE_SERVO`) | lift clear, transit to the destination's own pose (`task.jaw_target("place{bin}")`), lower, release | `[pservo]`: phase, `far=` to the place point, `hold=` |

Nothing reads the rigid body for control (a bench switch `FRUIT_CONTACT_SERVO_SOURCE=truth`
exists **only** to separate perception from geometry, and it is not part of the recipe).
The belt encoder is auxiliary. The pipeline is never stopped, diverted, gated or paused.

## 2. The adopted recipe

Checkpoint `checkpoints/p177_full` (the shipped `moe_v13s` lineage, fine-tuned on
`datasets/p174_all` + `datasets/p145_dagger_wait`), with the interface that was already
shipped before this lane (64-px foveal crop, `FRUIT_DIRECT_START_ALIGN=family`,
`FRUIT_SKILL_LIFT_RAMP=1`, `FRUIT_CLOSE_RAMP_DY=0.014`, the perception phase gate) and:

```bash
FRUIT_CONTACT_SERVO=1
FRUIT_CONTACT_SERVO_LEAD=0.10          # left arm: its reach band is upstream
FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20    # right arm: downstream band, needs the longer lead
FRUIT_PLACE_SERVO=1
FRUIT_PLACE_SERVO_VMAX=0.20            # the transit's reference speed (a measured peak)
FRUIT_FINGER_MAXFORCE_DIRECT=60        # the real-jaw clamp spec
FRUIT_SCORE_ENDPOINT=release           # score the place where the payload is released
FRUIT_POLICY_JOINT_CLAMP=1             # clip the 7 targets into the arm's own limits
FRUIT_POLICY_TARGET_RATE=5.45          # rad/s: the arm's own 312 deg/s joint limit
FRUIT_CLOSE_RAMP_DY_LO=-0.02           # phase close: level or just behind, never 0.44 m
# optional hybrid skill for the small-fruit class (<= 0.040 m):
FRUIT_SMALL_HANDOVER=1                 # small -> the scripted task.run skill; large -> the policy
```

Every knob is opt-in; **no shipped default was flipped**, `configs/` is untouched and the
motion references (`30fb99f8 / 30fb99f8 / 8952c320`) were never re-recorded.

### 2b. Smoothness: the command tail is capped at the arm's own joint speed

The visible "weird pose" was a single emitted waypoint step of **0.66-2.63 rad** in the
control cells (p95 0.136-0.198 rad per 4 ticks), which the arm physically cannot follow.
P207 adds `FRUIT_POLICY_TARGET_RATE` (rad/s, default 0 = untouched): the emitted 7-joint
target is ramped from its last value at no more than `rate/120` per control tick, with the
state per arm re-seeded from the measured joints at every attempt and after a servo. At
**5.45 rad/s** - the arm's own `maxJointVelocity` - the pooled count is **7/12 against the
control's 7/12**, the emitted p95 falls 0.198 -> 0.181 / 0.136 -> 0.093 and the **max falls
2.633 -> 0.182 / 0.660 -> 0.182 rad**; the cap binds only 16-24 % of waypoints (the
requests above the physical joint speed). R4 (4.0 rad/s) smooths harder but is a measured
speed limit on some branches (count 6/12), and R2 (2.0 rad/s) binds 76.6 % and is measured
out.

The second half is a **state bug** the cap exposed: after a servo the policy chunk
generated before it is stale by the servo's displacement (measured 1.75 rad), so the arm
is sent back to its pre-place pose. `FRUIT_REPLAN_ON_SERVO_END=1` drops the remaining
chunk, forces one fresh observation and re-plans. It is smoothness-only: the residual p95
falls 1.289 -> 0.344 rad but the count is 3/6 against 4/6 on a different branch, so it is
not in the ship recipe. **The instrumentation defect matters for every earlier clip**:
they exported `FRUIT_JOINT_CLAMP=1`, but the canonical name is
`FRUIT_POLICY_JOINT_CLAMP`; the short spelling is now a direct-only alias, and the P202/
P204 clips therefore ran **unclamped** (corrected in their READMEs).

## 3. The numbers

| configuration | placed |
|---|---|
| shipped 10 N, single lead, direct aim, 10-N clamp | **2/32 = 6.3 %** |
| + real-jaw clamp 60 N | **8/32 = 25.0 %** |
| + per-arm contact lead (0.10 / 0.20) | **8/16 = 50.0 %** |
| + place transit 0.15 m/s | **25/40 = 62.5 %** |
| **+ place transit 0.20 m/s (adopted)** | **22/32 = 68.8 %** (4 seeds, 2 fresh) |
| *the scripted two-line, for scale* | *58/80 = 72.5 %* |

Per arm at the adopted recipe: **left ~70 %**, **right ~48 %**. The non-monotone
dose-response of the transit speed (0.15 -> 8/16, **0.20 -> 14/16**, 0.25 -> 7/16 on the
same two seeds) is the strongest single piece of evidence in the lane that the knobs
measure an optimum rather than a branch.

## 4. Each term, its mechanism and its instrument

| term | what it was | the fix | evidence |
|---|---|---|---|
| acquisition | the fruit is 1-4 px in the full frame | the 64-px foveal crop (projection 1.3 px) | the close latch fired 28/30 against 1-2/12 |
| start state | the demos' frame 0 is a wait pose **IK-solved at the fruit's x** | `FRUIT_DIRECT_START_ALIGN=family` (rms 0.014-0.017 rad) | jaw z 1.314 (in support) vs 1.373-1.385 |
| close timing | a 30 Hz decision cannot predict 32 mm of belt travel with a 30 mm error (18.4 mm sampler spread + 24.4 mm bias) | `FRUIT_CLOSE_RAMP_DY=0.014` + the ramp's own gate | `[close] xy` 12-22 mm, `dz +59..+84` (the seat is +70) |
| contact aim | the shipped ramp latches on a 1-D criterion while the lateral error was 75-86 mm | the per-tick **contact servo** | `[close] xy` 83-104 -> **12-22 mm**; `[close-hold]` F 45-60 N, n=2 |
| right arm | 0-3 % grasps, and **not** the station, the perception, the finger law, the clamp or the squeeze scale | the servo's lead, **per arm** (0.10 left / 0.20 right): it moves `dlat` monotonically | all-right 0/4 -> **10/12** at three seeds |
| carry/place | the payload slid in the place transit (`hold=` 72 -> 96 mm) | the transit's reference speed limit (`VMAX`), a measured **peak at 0.20** | 0.15/0.20/0.25 = 8/14/7 of 16 |
| clamp | a real jaw must deliver a force | `FRUIT_FINGER_MAXFORCE_DIRECT=60` (a runtime spec, written by the task) | 2/32 -> 8/32; the pry needs > 30 N (P76) |
| scoring | a placed payload is carried off and despawned before `finalize`, so `on_output_belt(final)` read the spawner's park slot | **score at the release event** (`FRUIT_SCORE_ENDPOINT=release`, one sticky flag from a read the loop already takes) | `final=(+63, 0, -50)` on a good place |

## 5. The two data/harness defects the lane found

1. **No demonstration in the project contains a release.** 0 of **366** stored episodes
   ended with the finger open, because `_record` is never sampled inside the release
   block (the stores end 0.9-1.0 s before the attempt does). Fixed with one guarded
   `_record`; a 60-episode recollection (`datasets/p174_all`) now ends open on every
   episode. **Every store recorded before that fix is a no-release store** and must not
   be mixed.
2. **The direct episode's budget was shorter than a pick-and-place.** `--horizon 900`
   (7.5 s) against a 12-15 s attempt meant every grasp timed out mid-carry, and the
   timeout note claimed "no grasp" on episodes that had grasped. The note now says
   `timeout: horizon reached while carrying` and the adopted recipe runs 2600 ticks.

## 6. Instruments (all reporting-only, default off unless noted)

| row | reads | what it answers |
|---|---|---|
| `[close]` | `xy`, `dz`, `dx`, `sep=` (the measured pad span at the latch) | was the hand on the fruit, and did the pads move |
| `[close-ramp]` / `[close-hold]` | per-4-tick `sep`/`F`/`n`; one row at the ramp's end with `F=`, `n=`, `jax=`, `pL=`, `pR=`, `tax=`, `tilt=`, `dax=`, `dlat=` | *why* a close was empty: `dlat` (the payload's lateral offset from the tool axis) against the plate's 61 mm width |
| `[servo]` / `[pservo]` | aim error, `hold=` (the payload's distance from the jaw) | where a held payload is lost, per tick |
| `[pservo]` phases | `ph`, `far=` (distance to the place point), `at=` | the transit's progress and the release |
| the episode row | `success/grasped/placed`, `fing=`, `final=`, `on_out=` | the outcome and where the payload ended |

**Read rules learned the hard way**: `grasped` on the policy path is a *lift* test
(`_max_lift > 0.05`), so it is not a pinch test; `final` is a *park slot* once the
payload despawns; `dlat` and `dy/r` correlate with success but do not *cause* it (the pad
width widened to 78 mm changed nothing); and `jaw_separation()` is the **finger link
origins**, which `OpenArmHand` declares to be the pad faces (`pad_face_offset = 0.0`).

## 7. Everything measured and **not** adopted (so it is not re-derived)

Action forms `posvel`/`rel`/`dq`/`jaw`/`tcp`/`hybrid` (12-D) and the two-model hybrid;
GDP selection and K-sample averaging (both nulls); a horizon-1 policy; the phase-dependent
view (crop pre-close, wide after: the place error rose 48.4 -> 68.7 mm); the 900-tick
horizon; the station offset (demos say y = -0.10 for the right, the env 0.00: 0/6 either
way); the squeeze scale 0.90/0.92; the latch window 0.03/0.05; the close ramp 45 ticks
(a wash, and worse for the left); the transit clearance 0.20 m (0/8); the transit speed
0.15 and 0.25 (8/16, 7/16 against 14/16); the **pad width 78 mm** (4/8 against the
61 mm control's 5/8) - the second negative hardware item after the pad *shapes* of
`logs/p132/`; **executing half the chunk** (`--execute-steps 2`: 2/6 against 4/6, p95
0.182 against 0.101); and **execute-2 + temporal ensembling 0.5** (4/6, but p95 0.122
against 0.101 and equal count - it rescues E2, it does not beat E4); and the
**size-conditioned small-fruit selector floor** (`FRUIT_SELECT_SMALL_EXTRA`: 5/6 at seed
808 but 3/6 at 303 with 0.15, 3/6 with 0.25; the small fruit admitted at +0.673 still
fails, so the class is not selection timing); and the **right-only place transit speed**
(0.15: 2/6 against 0.20's 2/6, with `hold=` already 115-120 mm before the place, so the
slip is in the lift/carry, not the transit); and the **size-dependent direct clamp**
(20 N on <= 4 cm fruit: 1/6, identical to 60 N). **P216 then corrected the cause**: the
phase close's one-sided `dy <= hi` trigger was firing with the fruit **behind** the hand
(`[close] xy=442 mm`, `[fire] dy=-442 mm`); with a two-sided `FRUIT_CLOSE_RAMP_DY_LO=-0.02`
the small fruit read **`fired=0` at 0.65-1.18 m behind**, i.e. the policy never approaches
them. The small-fruit residual is the **policy approach/phase**, not force and not the
hand; the 3.7 cm lychee closes at 25 mm and places. **P217's scripted control is
decisive**: the same hand and lychee-only pool place **5/6 at 9.65-10.61 N** on the
shipped dynamic catch, while the learned direct line places 1/6 (60 N), 1/6 (20 N) or
0/4 (two-sided close, `fired=0`). The hand is fine; the **policy approach** is the
bottleneck. The full 4-waypoint chunk is the ship; the next spend is a size-aware phase
gate/retrain, a cartesian action, or a size-conditioned handover to the scripted
primitive (5/6) while the learned policy keeps the large fruit. The **small handover
itself is delivered**: `FRUIT_SMALL_HANDOVER=1` places **5/6 lychees** (P218) and the
mixed seed-303 cell reads **5/6** (learned large 4/4 + scripted small 1/1; the one failure
is the right-arm large class), against the learned control's 3/6 (C303) / 4/6 (R5); at
seed 808 the hybrid is 4/6, equal to its control, and the small class is 2/2 (P219). It
is a **hybrid**, not a learned small-fruit policy; the mixed count is a branch, the class
mechanism is the result. **Continuous**: the handover's finalize returns to the next pick,
so a lychee-only 6-pick continuous episode places **5/6** (`[cont] picks=6/6 placed=5`,
10,290 ticks, 15.3 s/pick) against the learned continuous P204's 2/6. The mixed continuous
seed-303 cell completes **4/6** (equal to its learned control, no small fruit in the
sequence); seed 505 still wedges in the learned large-fruit post-close path (P220).
**P222's right-side route** is a mechanism, not a mixed gain: the scripted B-heavy control
places **6/6** right-arm fruit, `FRUIT_HANDOVER_SIDE=right` places the right **3/3** at seed
303, but the learned left is **1/3** (loaded slide), so the mixed cell is 3/6 against
P219's 5/6. The learned left large fruit is the residual, and **P223 shows it is the hand,
not the policy**: the scripted dynamic catch is **6/6 on a B-heavy (right) pool** but
**1/6 on an A-heavy (left) pool** (kiwi/peach/lychee grasped-not-placed, 0.106-0.246 m
lifts), while the learned left is ~70 %. The best per-arm route is **right -> scripted,
left -> learned**; the left 70 % / left pad is the system cap.

## 8. What is left: the acquisition's selection timing, throughput, a certificate

**The acquisition is the residual, and it is the *estimator*, not a close, a servo or a
selector.** A pre-registered floor cell (`FRUIT_DYNAMIC_SELECT_S` 1.5 -> 3.0 s, +0.18 m of
selection lead, `logs/p200/PREREG.md`) **failed both of its endpoints** - placed 6/12 against
8/12 and the upstream-at-latch fraction 5/11 against 7/12 - and under the larger floor the
latch's true `dy` still spans **-853 .. +109 mm**, i.e. selecting earlier only makes the hand
wait. The latch fires when the *goal* comes within 14 mm of the jaw, and the goal is the
estimator's output, so a wrong or coasting lock moves the landing; every decision-side knob
(the floor, the 50 mm gate, the upstream-only arming, the 0.2 s coast, the latch window, the
gap window) does nothing or hurts. The next spend is the **estimator** (a second view, a
tighter fit) or an honest acceptance of the lane at its measured rate.

**The older reading, kept because it is what the census measured:**
The `[fire]` census (one row per attempt at the committed ramp's latch) reads **12/12
latched attempts placed** at seeds 808 and 303, with every failure a small fruit (3.1-3.4 cm)
whose fruit was already level with or behind the hand when the attempt began - the servo
then chased it downstream for its whole window (`aim y -0.242 -> -0.562` at the belt's own
speed, jaw 500 mm behind, `hold` 536 mm) and never latched. The successful latches happen
with the **true** fruit **84-144 mm upstream**, because the goal (`predict_at`, coast 1.0 s)
**leads** it - the intercept the latch needs. Shortening that coast is negative (0.2 s reads
3/8 and 2/8 against 6/8 and 6/8), as are the upstream-only arming (9/16 against 12/16), the
50 mm alignment gate (3/8, 4/8) and the force-triggered close (a wash, with the pinch never
reaching its target). So the remaining lever is the **selector/supply timing** - do not
offer a fruit that is already level with the hand - which is a registration of its own.

## 8b. Also open: hardware or throughput

* **The right arm (48 %)**. Six software candidates and the pad width are ruled out. The
  two remaining directions are the ones `docs/END_EFFECTOR_DECISION.md` names: a **new pad
  shape** (a different *form*, not a wider plate) or a **force-controlled finger** (the only
  form that can be stiff in the approach and compliant inside the closure).
* **Throughput**: the adopted recipe spends ~2.1-2.4 k ticks per attempt (the transit's
  speed limit is the price of the place rate). A production setting would choose the
  (speed, rate) pair from the measured curve, not from a default.
* **A rate certificate** beyond n = 32 needs the P93 power note's ~364 attempts per arm.

## 8c. P225 (2026-11-19): the no-scripted-skill target is met at 0.12-0.15 m/s

The owner's target - **> 55 %**, **< 12 s per fruit**, belt **> 0.08 m/s**, with
**no scripted skill padding the count** - was measured with both handover routes
off (`FRUIT_SMALL_HANDOVER=0`, `FRUIT_HANDOVER_SIDE=`, `FRUIT_POLICY_HANDOVER=0`)
and the selector changed from farthest-upstream to **nearest-above-floor**
(`FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1`, P40's 0.21 m / 1.75 s commit). With
`FRUIT_SCORE_ENDPOINT=release FRUIT_EPISODE_END=release`:

| belt | cell | placed | success release times |
|---|---:|---:|---|
| 0.15 | `logs/p225/N15_s77` | **5/8 = 62.5 %** | **6.6-9.9 s** |
| 0.12 | `logs/p225/N12_s77` | **6/8 = 75 %** | **7.3-11.6 s** |
| 0.12 | `logs/p225/N12_s101` (right-heavy) | 2/8 | 9.3 s |
| 0.10 | `logs/p225/N10_s77` (stopped at a wedge) | 4/6 | 6.8-12.0 s |
| 0.12 | five-seed record (`25/40`) | 62.5 % | 8.3-11.3 s |

Pooled over the phase's four nearest-selector servo cells: **17/30 = 56.7 %**;
by arm **left 14/17 = 82 %**, **right 3/13 = 23 %**. **The strict no-servo
ablation is 0/7** (`FRUIT_CONTACT_SERVO=0 FRUIT_PLACE_SERVO=0`): the analytic
contact/place servos are load-bearing, so the result is the **hierarchical**
learned lane, not a bare policy. The right arm is the residual; the 0.08 cell is
OOD for the 0.12-trained demos (`1/4`, 14-19 s), which is the case for
speed-randomized demos. **The right-only control**
(`FRUIT_SUPPLY_GRADES=A:0.01,B:0.98,C:0.01`) is **2/8 = 25 %**, with every
`[close]` on the fruit (`xy 13-19 mm`) and the failures in the lift/hold
(`grasped=False`) - the cap is the right's lift class, not the mix. At a 50/50
arm mix the arm-standardised pooled is **53.5 %**, so the target is met on the
left-heavy cells (and the record's 60/40 split), not robustly at 50/50. The
**4-frame temporal-context fine-tune** (`--obs-horizon 4`, StreamPI/TEMPO) is a
measured negative: it matches the 2-frame model on the first mixed episodes and
wedges on the right apple/pear; not adopted (`logs/p225/finetune/`). The
**right-only fine-tune** (31 right demos + 15 right dagger, 10 epochs,
`demo_val` 0.0178) is also a **null/wedge**: the same first-four right outcomes
as p177 and a wedge on the right orange, so more right data does not convert
the right - the cap is the lift/hold physics. The **right low-lift
recollection** (`FRUIT_COLLECT_LIFT_DZ_RIGHT=-0.08`, 10 right episodes) plus a
39-episode mixed fine-tune (`p225_lowmix`, md5 `9a2786f4`) doubles the
right-only rate **2/8 -> 4/8 = 50 %**; the single lowmix model costs the left
(3/4 vs 5/5), so the adoption is the **arm router**
`FRUIT_POLICY_CKPT_RIGHT=checkpoints/p225_lowmix` with p177 on the left. At the
observed left 82 % / right 50 % the **50/50 arm-standardised estimate is
66 %**, but the router's mixed cells **do not confirm it at the cell level**:
`RT12_s77` is 2/3 then a wedge, and the completed 0.15 `RT15_s77` is **2/8**
(the p177 left's two tomatoes are `grasped=True placed=False`, the lowmix right
is 0/4 on the small lychee/strawberry/kiwi). The p177 single's 0.15 **5/8** and
0.12 **6/8** remain the target samples; the clean low-lift gain is the
right-only **2/8 -> 4/8**; the right's small fruit and the place remain the
residual. The active-only frame push (the right buffer only on right episodes)
halves the per-frame crop/resize and let the 0.15 router cell run all 8 without
the wedge. The **carry force servo** (`FRUIT_CARRY_FORCE=45`, default off) -
P192's force-controlled finger extended past the close - doubles the right-only
rate **2/8 -> 4/8 = 50 %** on the untouched p177 with no new data; the
size-aware floor margin 0.002 is a 3/8 tie/negative, and the mixed `N12F45` 3/8
is a right-heavy branch. The 50/50 arm-standardised stays **66 %** (left 82 %,
right 50 %); the small lychee/strawberry remain the approach class. **Videos**:
`/media/.../video/p225_p177_continuous` is the continuous clip (6 picks, 5
placed, 62.6 s, seed 303); `p225_p177_demo` 2/6 and `..._s303` 1/6 are the
video-render branch; the existing `p177_adopted` 4/6 is the better demo. The
**small-fruit fine-tune** (78 small episodes, 15 epochs, loss 0.0223,
`p225_small` md5 `9fb8335d`) is **0/6** on the lychee-only cell against p177's
0/5: the `[close]` rows fire with the **true** fruit 88-383 mm away and
`sep=98` (the pads at their open stop), so the close is on the **perception's
goal** and the small fruit (~12 px at 240x424) is refused by
`FRUIT_PERCEPTION_MIN_PX=60`; the cap is the perception, not the data.
The feedback's fix is the **size-scoped floor**:
`FRUIT_PERCEPTION_MIN_PX_SMALL=12` for <= 4 cm (the 5-7 cm pool keeps 60) turns
the lychee-only cell from **0/5 to 3/4** (`err_close_p50` 1.5-4.9 mm; the
`[close]` on the fruit at `xy 14-18 mm`), and the mixed `N12P12FS` reads
**6/8 = 75 %** (lychee **3/3**, right 4/6, left 2/2) with the carry force
scoped to > 4 cm (`FRUIT_CARRY_FORCE_SMALL_DIA=0.040`; the force on the small
is 2/4, a measured negative). The 0.15 cell is 4/8 on its branch (the left's
place failures); the 0.12 is the strong speed. The remaining small class is
the **strawberry** (3.1 cm, conical). The spheroid was then measured: the
strawberry-only cell reads **sphere 3/6 vs spheroid 2/6** (the spheroid's `rms`
14-56 mm at the 12 px; the sphere's 0.1-0.3), so the sphere stays the default
and `FRUIT_PERCEPTION_SHAPE_SPECIES` is an opt-in negative. The mixed cells
with the min-px 12 + the carry force scoped > 4 cm are **0.12 6/8 = 75 %** and
**0.15 5/8 = 62.5 %**, every success 7.7-10.6 s - the target is met at both
speeds. The remaining classes are the 0.15's tomato place (the left), the
6 cm orange, and the strawberry's 3/6. Full record and runners:
`logs/p225/RESULTS.md`,
`logs/p225/{run_cell_near.sh,run_cell.sh,run_cell_strict.sh,parse.py}`.

## 9. Pointers

`logs/p145/RESULTS.md` sections **S51-S64** are this lane (S1-S50 are the earlier
exploration: the camera diagnosis, the crop, the start family, the ramp, the action forms,
the two-model hybrid, the place servo's first working trajectory, the release-recording
defect). The scripts and cells are in `logs/p176_*` ... `logs/p190_*`; the checkpoints are
`checkpoints/p177_full` (adopted) and `p169_freewrist`, `p171_tail`, `p174_fasthead`,
`p178_h1`, `p176_release` (ablation arms). The task's own provenance blocks
(`scene`, `physics.*`, `supply.band`, and the new `finger = {pad_wide, tip_delta}`) name
everything a store was recorded with.
