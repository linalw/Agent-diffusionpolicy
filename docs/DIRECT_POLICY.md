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
```

Every knob is opt-in; **no shipped default was flipped**, `configs/` is untouched and the
motion references (`30fb99f8 / 30fb99f8 / 8952c320`) were never re-recorded.

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
0.15 and 0.25 (8/16, 7/16 against 14/16); and the **pad width 78 mm** (4/8 against the
61 mm control's 5/8) - the second negative hardware item after the pad *shapes* of
`logs/p132/`.

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

## 9. Pointers

`logs/p145/RESULTS.md` sections **S51-S64** are this lane (S1-S50 are the earlier
exploration: the camera diagnosis, the crop, the start family, the ramp, the action forms,
the two-model hybrid, the place servo's first working trajectory, the release-recording
defect). The scripts and cells are in `logs/p176_*` ... `logs/p190_*`; the checkpoints are
`checkpoints/p177_full` (adopted) and `p169_freewrist`, `p171_tail`, `p174_fasthead`,
`p178_h1`, `p176_release` (ablation arms). The task's own provenance blocks
(`scene`, `physics.*`, `supply.band`, and the new `finger = {pad_wide, tip_delta}`) name
everything a store was recorded with.
