# P34-B pre-registration — the early view at the store's own first-view along (conditional)

Written 2026-10-23, **before any A/B of this phase** (no such A/B has been
run). The evidence that motivates and constrains it is `logs/p34/B_READ.md`;
the phase-2 A/B is `logs/p34/A_READ.md` + `PREREG.md`. **Default off, no shipped
default changed**; this phase's files are uncommitted (the orchestrator commits).

**Status: conditional and not to be run as-is.** The measured precondition is
**unmet**: the valid (episode-0) renders show the direct env's **left** first
call already visible at the shipped reset's near-neighbour (0.439: `first_rel`
0.893) and at the phase-2 aim (0.398: 0.972). An along-only A/B would move a
visible first view to a visible first view, and the phase-2 A/B already read the
outcome null at 0.399. The A/B below is therefore pre-registered with an
explicit **re-entry condition**; if that condition is met (a corrected
first-view measurement shows the *left's* shipped-reset first call hidden), the
A/B is runnable unchanged.

## 1. The question and the re-entry condition

At the **single-arm store's own first view** (first-detectable along p50 +0.451
left / +0.440 right; the frame-0 groups +0.455/+0.444), does presenting the
target there at the **first model call** - instead of the shipped reset's
p50 +0.488 (left) - improve the left arm's acquisition and outcome on the P33
W8-A scenario?

**Re-entry condition (all three):**

1. The first-call frame is **current** (the `[align]` row's `first_px > 0`
   tracks a live fruit; today it is the pre-reset frame for every episode >= 1
   of a process - `B_READ.md` section 3), *or* the treatment check is read on
   the **episode-0** valid sample (5 per arm) by design.
2. On that corrected read, the **shipped** reset's left first call is **not**
   visible: `first_rel < 0.9` in >= 4/5 of the left's valid episodes. (Measured
   today: 0.893 at the shipped 0.439, 0.972 at 0.398, 0.893 at 0.441/0.445 with
   the aim unreachable - i.e. visible, so this fails.)
3. The left's **outer-band** fraction (x < 0.26) of valid first calls is
   reported, because that is where the surviving occlusion lives (`B_READ.md`
   section 3); if the treatment's effect is confined to x >= 0.26, the A/B's
   population is pre-split by x.

If (1) or (2) fails, **do not run this A/B**: the named next lever is the arm
park / camera sightline (`B_READ.md` section 4), with its own pre-registration,
and the reset-pose (hover) alignment is the secondary.

## 2. The arms

* **A = control**: the shipped direct env; `FRUIT_RESET_ALIGN` unset (0). The
  first call is at the reset's own along (p50 +0.488 left on the phase-2
  control), i.e. inside the +Y belt's band for >= 44 mm fruit.
* **B = the store's first view**: `FRUIT_RESET_ALIGN=1`,
  `FRUIT_RESET_ALIGN_ALONG=0.441` (the requested aim), with
  `FRUIT_RESET_SETTLE=20` (the shipped settle; the settle is a measured pose
  null, `B_READ.md` section 2, so it is held fixed, not a variable).
  `FRUIT_RESET_ALIGN_ALONG=0.445` is a **pre-registered secondary** because
  0.441 is at the belt's near edge for >= 58 mm fruit (the measured replay at
  0.439 reads `first_rel` 0.893, `vis212` 0.98) and because the reset can return
  already below the aim (the measured left process returned at +0.443, so both
  the 0.441 and the 0.445 aim took **0 steps** and the first call sat at
  +0.439). Only one B is run per batch; the choice is fixed before the batch:
  **0.441** unless the pre-run probe at 0.441 reads `first_rel < 0.9` for the
  left, in which case **0.445**.
* Same checkpoint (`checkpoints/moe_v13s/policy_best.pt`, `61da390a`), same
  scenario as the phase-2 A/B verbatim (`FRUIT_SUPPLY_SCATTER=1
  FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
  FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
  FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_TRIGGER_ACQ=1`, `FRUIT_CAMERA_RES=240,424`,
  headless, no attach, no sleep), `FRUIT_RESET_ALIGN_DIAG=1` on **both** arms,
  `FRUIT_ACQ_DIAG=1` on both.
* **N = 5 runs x 15 episodes per arm**, seeds 77/101/202/303/404, policy sampler
  seed 11, interleaved A,B,... in one `scripts/154_claim_run.sh` claim.

## 3. The treatment check (gates the A/B)

Two measurements per episode, from the **first model call** (`[align]` row):

1. the along within **0.441 +- 0.02 m** (or the chosen secondary 0.445 +- 0.02);
2. the rendered visible fraction = **`first_rel` >= 0.90** with `first_px > 0`,
   where `first_rel` is the first call's (mask / analytic unoccluded area at that
   pose) over the episode's maximum of the same ratio - the depth- and mesh-free
   normalisation of `B_READ.md` sections 1/3 (the raw `px/px_max` is depth-biased
   and reads 0.883 where `first_rel` reads 0.893). The `[align]` row's
   `pfc`/`pcm` (px x camera distance^2, first and max) is the A/B's own
   approximation of it; *and* the analytic `212` visible fraction at that pose
   >= 0.90 (the belt check). Measured reference: the left apple at 0.439 reads
   `pfc/pcm` 137/151 = **0.907** (`B_rowcheck.log`).

**Pass bar:** B meets **both** on **>= 90 % of its *valid* episodes** and
**>= 4/5 in each B run**. With the current frame staleness the valid episodes
are the **episode-0s only** (one per run); the pre-run item is either the
frame fix or the acceptance of this 5-episode check. **If the check fails, the
phase is an implementation failure**: no outcome claim, and the reason is
diagnosed (the frame, the belt edge, the arm) before any re-run.

## 4. The endpoints (the P33 protocol, unchanged)

**Primary**: the **left's carried-not-placed class** and its paired conversion
(same-fruit pairing by run, episode, species, diameter, arm; the class
transition matrix; B-only vs A-only carried->ok; the one-sided sign test; the
6-0 edge is p <= 0.05 at N=5).

**Primary-secondary**: the left's **no-grasp** class and the **composite failure
mass** (carried + no-grasp), so a class *relocation* cannot pass.

**Secondary**: the pooled and per-arm placed counts, the median cycle ticks (the
alignment's span is shorter by construction - quote as a consequence), the model
calls per attempt, the fire-time `dx`/effective lead (`[acq]`).

**Mechanism**: the first-call along/x/`px`/`first_rel` (`pfc`/`pcm`) per arm, the
fire-zone mask counters (`zone_n`, `zone_zero`, `px_max`), and the arm-pose rows `q_r`/`q_f`
(they must be identical between the arms - the alignment does not command the
arm).

## 5. The decision rule and the falsifier (fixed now)

* **Treatment check fails** -> implementation failure; no outcome claim.
* **Check passes and the left's outcome moves the pre-registered way** (left
  placed >= A and the carried-class pairing favours B, or the left's
  carried + no-grasp mass falls with no new failure reason) -> the along lever
  is a measured interface win; it still ships **default off** (a separate
  adoption gate: the direct-path history is re-baselined).
* **Check passes and the left does not move** (no carried-class conversion, no
  placed gain, no composite reduction) -> **the falsifier fires**: the early
  view is not the mechanism. This is the expected outcome given `B_READ.md`
  (the view was already visible in the phase-2 A/B), and it would close the
  along lever for good; the surviving lever is the arm park/camera.
* New failure reasons or a right-arm regression block any adoption claim.

## 6. No-harm

With the knobs unset the tree is the phase-2 no-harm tree (`rl_env.py`'s
alignment block off, the settle at its shipped 20, the diag off): the scripted
`[fruit]` stream is byte-unchanged. The batch runs `scripts/selfcheck.sh` before
and after; the scripted acceptance is run once with the knobs unset and its
`[fruit]` stream compared to `logs/p33/40_accept_final.log` (the documented
6/10 owner-exception branch, 376/376 identical in phase 2).

## 7. Provenance (to be filled by the run)

`logs/p34/B_ab2/` (the batch), the `[align]` read per arm, the tree md5s before
and after, the selfcheck and acceptance logs, the checkpoint md5. The pre-run
probe log at the chosen aim. No commit; no shipped default changed.
