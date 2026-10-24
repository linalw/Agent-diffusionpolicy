# P35 phase 1 pre-registration — the inactive arm's park and the outer-band sightline

Written 2026-10-24 **before any A/B of this lever** (no park A/B exists; the only
runs under this phase are the offline maps and the read-only renders listed in
`logs/p35/A_READ.md`). **Default off, no shipped default changed**: the lever is
`FRUIT_ARM_PARK=<name>` in `rl_env.py`, read from `configs/arm_parks.json`, and
unset it is one dict lookup per arm at reset (the shipped `ready` teleport).
This phase's files are uncommitted (the orchestrator commits).

> **Reading note (added 2026-10-24, Gate-2):** section 5's positive clause is the
> *prediction* and is kept verbatim as pre-registration text. The measured
> conclusion is **narrower**: the **park is a measured interface lever**, the
> check shows it **removes the fruit's band occlusion**, and **the mediator (the
> image vs the 7 inactive-arm proprio channels) is not identified** - the
> control's invisible-fruit successes argue against a simple perception
> bottleneck. Read `logs/p35/C_RESULTS.md` section 3 for the record; do not quote
> this file's "the sightline is a measured interface lever" as the conclusion.

## 0. What is measured, and what is not

Measured (phase 1, `A_READ.md`): the inactive left arm at `ready` covers the
main belt's approach band — **98 % of a 58 mm fruit's disc at along +0.35, 57 %
at +0.40**, mean **0.382** over the scored stream at the shipped camera — and the
park named `back` takes that to **0.002** (mean) with the hand 0.29 m above the
belt. A static-fruit render agrees: a 68 mm pear at (x 0.219, y +0.399) reads
**0.378 visible at `ready`, 0.878 with `back`**; a 58 mm fruit at (0.19, +0.35)
reads **0.000 -> 0.953**.

Not measured: the outcome. And one prior claim is corrected: **the arm is not the
occluder of the direct env's first call at the shipped reset** (along +0.541) —
the output belt is (212 visible fraction 0.00 there), and P34-B's right-arm
`first_rel` 0.077-0.131 at along +0.441/+0.445 is the pre-reset frame (its bbox
is 222/213 px of `/World/Conveyor/Belt` with the fruit absent). The arm's real
occlusion is one band downstream of the first call (along +0.30..+0.45), which is
the approach/decision zone the trigger fires in.

## 1. The question

With the **inactive** arm parked out of the belt's sightline instead of at the
shipped `ready` pose, does the direct policy see an outer-band fruit it
currently cannot see, and does the outcome move on the arm that fruit is
presented to?

The lever is **one-sided by measurement**: the left arm at `ready` covers 0.38
of the stream, the right arm 0.00 (`217`, both sides). A fruit is presented to
the **right** arm when its grade is B or C (the direct env sets the arm from the
grade), so the population the treatment can act on is the **right-arm
episodes**; left-arm episodes are the treatment's no-op control inside the same
batch.

## 2. The manipulation check (gates the A/B)

The check must answer "did the treatment present the view it claims to test" on
a **current** frame, at the pose the mechanism is about. Phase 1 fixed both
terms: the arm's occlusion lives at **along +0.30..+0.45** (cover 0.81-0.98 at
`ready`, depth-gated), while the *first* call sits at along +0.44..+0.54 where
the **output belt** hides the fruit for either arm (`212` 0.17 at +0.50, 0.00 at
+0.55). So the check is read per call, at the band where the arm is the
occluder:

* **M1 - the park applied**: the inactive arm's joints at the first model call
  are within **0.02 rad** of the `back` vector (one extra articulation read at
  the first call, default-off diag).
* **M2 - the sightline in vivo**: on the **first call whose target along is in
  +0.30..+0.45** (the fruit has left the belt's band), the target's mask is
  **>= 0.85 x the episode's own maximum** of the same ratio (`first_rel`, which
  normalises the analytic-area bias: a fully visible proxy reads 0.878-0.953),
  **and** the parked arm's link pixels inside the target's projected bbox are
  **< 0.10 x the target's pixels**. The same counters the phase-1 `[probe]` row
  already prints (`target_px` + the top instances in the bbox) - a small
  default-off addition to the env's diagnostic, run on **both** arms.

**Measured references for the bar** (phase 1, current frames): the 68 mm pear at
(x 0.219, y +0.399) reads **0.378 visible at `ready` / 0.878 with `back`**; a
58 mm fruit at (0.19, +0.35) reads **0.000 / 0.953**; the 58 mm fruit at (0.30,
+0.40) reads 0.051 / 0.940. The bar is 0.85, not 0.9, because the analytic-area
normalisation caps a fully visible proxy at 0.878-0.953.

**Pass bar**: M1 on >= 95 % of episodes and M2 on **>= 90 % of the treatment's
episodes whose target enters +0.30..+0.45** (and >= 4/5 in each treatment run).

**Why not the `[align]` first call.** P34-B proved the first call's target mask
is one or more renders behind (the pre-reset frame); phase 1 re-measured it with
the park on: at seed 77's outer-band pear the first call still reads
`target_px=0` at along +0.541 while the parked arm's `link3`+`link4` fill the
bbox. A first-call mask threshold would pass or fail on the frame lag, not on
the park. (In episode 0 the later calls are current - `43_firstcall_nolabels.log`
shows the target's mask rising 4 -> 55 px as the along falls +0.521 -> +0.497 -
which is why M2 is read per call and not at the reset.)

**If the per-call counter is not built**, the check degrades to M1 plus the
phase-1 offline proxies, and the A/B must be labelled **"mechanism measured
offline, not in vivo"** - the P34 outcome this lane exists to avoid.

If (M1) or (M2) fails the phase is an **implementation failure**: no outcome
claim, and the reason (the frame, the pose, the pose drift) is diagnosed before a
re-run.

## 3. The arms

* **A = control**: the shipped direct env; `FRUIT_ARM_PARK` unset. Both arms at
  `ready`, the active at `grasp`.
* **B = the park**: `FRUIT_ARM_PARK=back` (left arm only: the vector in
  `configs/arm_parks.json`, j1 -0.50 / j2 -0.60 / j4 -0.50 rad from `ready`,
  measured hold 0.0316 rad at 90 ticks and 0.0007 rad over 900 ticks, hand
  0.287 m above the belt, 0.187 m from the active arm's links, torso gap
  0.688 m). `side_deep` is the **pre-registered runner-up** (arm cost 0.036,
  hold 0.0001 rad, hand out of the belt footprint but 9 mm above it at x ~0.0)
  and is run only if `back` fails item (3) of the check.
* Same checkpoint (`checkpoints/moe_v13s/policy_best.pt`, `61da390a`) and the
  same scenario as the P33 A/B verbatim (`FRUIT_SUPPLY_SCATTER=1
  FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
  FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
  FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_TRIGGER_ACQ=1`, `FRUIT_CAMERA_RES=240,424`,
  headless, no attach, no sleep); the per-call park check (M1/M2, section 2),
  `FRUIT_RESET_ALIGN_DIAG=1`, `FRUIT_ACQ_DIAG=1` on **both** arms.
* **N = 5 runs x 15 episodes per arm** = 75 attempts per arm, seeds
  77/101/202/303/404, policy sampler seed 11, interleaved A,B,... in one
  `scripts/154_claim_run.sh` claim.

**Power, stated honestly.** The right-arm share of the mix is 0.625, so ~47
paired right-arm attempts per arm. The primary is the paired **class
conversion**, whose one-sided sign-test edge at N=5 is 6-0 (p = 0.031) or 5-1
(p = 0.219): this phase is a **screen**, not a confirmatory test, and a
non-significant paired count is the expected outcome even if the lever is real.
The measured reference spreads are the P33 D0 canary 5/10 and the recorded
pre-pear 5-8/10, so a rate claim needs the per-episode table, not the headline.

## 4. The endpoints (the P33 protocol, unchanged)

**Primary**: the **right arm's carried-not-placed class** and its paired
conversion (same-fruit pairing by run, episode, species, diameter, arm; the
class transition matrix; B-only vs A-only carried->ok; the one-sided sign test).

**Primary-secondary**: the right arm's **no-grasp** class and the right's
**composite failure mass** (carried + no-grasp), so a class *relocation* cannot
pass; and the **outer-band subgroup** (the right-arm attempts whose check-frame
x < 0.26), reported paired.

**Guard (a regression blocks any claim)**: the **left arm's** placed and
no-grasp counts - left-arm episodes are the treatment's no-op (the left is the
active arm then, and the right arm at `ready` covers 0.00) - and the pooled
placed count.

**Secondary**: the cycle ticks, the model calls per attempt, the fire-time `dx`
and effective lead (`[acq]`), the failure-reason set (a new reason blocks
adoption).

**Mechanism**: the `[park]` rows (target pixels, arm pixels in the bbox, joint
residual), the per-arm first-call x/along, and the right-arm outer-band share.

## 5. The decision rule and the falsifier

* **Check fails** -> implementation failure; no outcome claim.
* **Check passes and the right's carried class converts** (>= 5 B-only / <= 1
  A-only, or the composite falls with no new reason and the left does not
  regress) -> the sightline is a measured interface lever on this scenario. It
  still ships **default off**: every recorded store frame has the left arm at
  `ready`, so a policy-side gain needs a **recollection** (the OOD cost below),
  and the adoption gate is that recollection's own A/B.
* **Check passes and the right does not move** -> **the falsifier fires**: the
  arm's sightline is not the mechanism for this checkpoint. The lever closes for
  `moe_v13s`; the honest reason is "the park changes the frames the checkpoint
  was trained on", so the closure is scoped to the checkpoint, and a
  recollection-first version becomes a budget decision, not a measurand.
* A new failure reason, a left-arm regression, or an arm-pose residual > 0.02 rad
  blocks any adoption claim.

## 6. The OOD / recollection caveat (the cost, measured, not assumed)

The park is a **static scene change in every frame**: the policy's input has the
left arm somewhere it has never been. Phase 1 measured the shift as a
silhouette: 3497 px at `ready` vs 4155 px at `back` (the arm moves up and
downstream, into the spawn corner), and `back`'s residual occlusion is exactly
there (along +0.50/+0.55: 0.10/0.54 cover) where the +Y belt already hides the
fruit (`212` 0.17/0.00) - the marginal cost is 0.002. A positive result is
therefore a statement about **this checkpoint on shifted frames**; a negative is
weak evidence (it can be the shift, not the sightline). The same caveat applies
to every camera pose, which is why the camera is priced but **not** proposed: the
best camera (`x -0.10`, arm cost 0.075) is dominated by the park (0.002) and
moves every pixel of the frame.

## 7. No-harm

* With the knob unset the tree is byte-inert by construction: `_arm_park_poses`
  is empty, and the reset's teleport is the shipped `json -> np.asarray -> ready`
  call (one `.get` per arm). Both branches are exercised in phase 1: the
  knob-off episode-0 probe (`40_firstcall_ready.log`), the knob-on
  (`41_firstcall_back.log`), and the **active-arm guard** (`42_firstcall_left_active.log`:
  with the left active and the park on, the reset reads `along_reset=+0.443` and
  `target_px=158`, the P34-B left control's numbers - the park must not add a
  second settle to the active side).
* `scripts/selfcheck.sh` before and after; the scripted acceptance is not
  re-run (its path does not touch `rl_env.py`; the scripted park is
  `tasks.go_ready`), and the phase-1 evidence states that.

## 8. Provenance (to be filled by the run)

`logs/p35/A_ab/` (the batch), the `[park]` rows per arm, the tree md5s before and
after, the selfcheck log, the checkpoint md5, the manifest's `arm_park` block.
No commit; no shipped default changed.
