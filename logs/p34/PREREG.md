# P34 phase 2 pre-registration — the reset alignment (the first recommended lever)

Written **before** any phase-2 simulator run (2026-10-23T10:19Z, the tree pins
in `60_ab_tree_md5_before.txt`: `rl_env.py` `d4a3c4a9`, `tasks.py` `cdde6bd2`,
`checkpoint moe_v13s` `61da390a`). Phase 1 (`logs/p34/REPORT.md`) measured the
+ Y output belt's occlusion; this phase tests whether the **direct env's first
observation** is the mechanism for the left lane's acquisition/failure class.
The scene lever (+Y belt y +0.04) is **Phase 3** and is not run here.

## 1. The question

The demos' frame 0 has the target **visible** at along p50 **+0.374**
(first-detectable p50 +0.399); the direct env's shipped reset presents it at
p50 **+0.583**, inside the +Y slab's analytic fully-hidden band
(+0.515..+0.870). Does aligning the direct env's **first model call** to
along ≈ 0.399 (the demos' first view) improve the **left arm's acquisition and
outcome** (the left's placed count, the carried-not-placed and no-grasp
classes) against the same checkpoint, scenario and batch with the knob off?

Why the left: the P33 census (`logs/p33/51_phase2_read.md` §1.2) reads 33/33
carried-not-placed episodes on the left, 0/48 on the right; the left reset is
p50 +0.599 vs the right's +0.573 (a 26 mm difference, not a cleaner split than
the P33's own class) and the left is the arm whose direct-path failures are
pre-contact acquisition (W7-B) plus carry escapes (W8-B/R6-B). The lever is
**first-view only**: the fire zone is unoccluded (visible fraction 1.00) and the
trigger is encoder-based.

## 2. The manipulation check (per episode; gates the whole A/B)

Two measurements per episode, from the **first model call** (not the reset
header — the reset advances the line before any model call):

1. `first` = the target's along-distance to the pick station
   (`fruit.y - _expert_jaw_y`) at the **first** `policy.act` call, logged by the
   new `[align]` row. Target **0.399 m ± 0.02 m** (the demos' first-detectable
   p50; ±5 % of the 0.39 m visible run).
2. `vis212` = the analytic visible fraction of `scripts/212_occlusion_map.py`
   at that call's `(x, first, d)`; target **>= 0.90**. The rendered target-mask
   pixels at the same call (`first_px`) are reported against the analytic
   unoccluded area as the rendered cross-check (not the gate).

**Pass bar:** the aligned arm (B) meets **both** on **>= 90 % of its pooled
episodes** and **>= 12/15 in each B run**. The control (A, knob off) is
measured with the same diagnostic and is expected to fail (phase 1: 0.455..0.551
with vis 0.00..0.93, the reset itself 90 % hidden).

**The A/B tests the hypothesis only if the manipulation check passes.** If it
fails, the phase reports an implementation failure and the hypothesis stays
untested (no outcome claim).

## 3. The arms and the batch

* **A = control**: the shipped direct env; `FRUIT_RESET_ALIGN` unset (0).
* **B = aligned**: `FRUIT_RESET_ALIGN=1` (default 0; `FRUIT_RESET_ALIGN_ALONG`
  0.399; the advance after the reset's setup prices the `execute_steps`=4
  control ticks between the reset return and the first call: aim 0.403 m at the
  reset return).
* Same checkpoint (`checkpoints/moe_v13s/policy_best.pt`, `61da390a`), same
  scenario: the P33 W8-A env verbatim
  `FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
  FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
  FRUIT_POLICY_TRIGGER_ACQ=1`, `FRUIT_CAMERA_RES=240,424`, headless, no attach,
  no sleep.
* **N = 5 runs x 15 episodes per arm**, seeds **77 / 101 / 202 / 303 / 404**
  (the WS-4.2 protocol), policy sampler seed 11, **interleaved A,B,A,B...** in
  one batch, one simulator (`scripts/112_rl_ab.sh` under
  `scripts/154_claim_run.sh`). One `FRUIT_RESET_ALIGN_DIAG=1` on **both** arms
  (the manipulation check needs the control's first call too); `FRUIT_ACQ_DIAG=1`
  on both (the P33 batch's instrumentation, so the mechanism read is comparable).

## 4. The endpoints

**Primary (the P33 protocol)**: the **left's carried-not-placed class and its
paired conversion**. Same-fruit pairing by (run, episode, species, diameter,
arm); the class transition matrix, the B-only vs A-only carried->ok
conversions, the one-sided sign test; the 6-0 edge is p<=0.05 at N=5.
Reported with the left's `n` (the arm is set by the fruit grade, so the
per-arm n can differ between arms after the branch moves).

**Primary-secondary**: the **left's no-grasp class** (grasped=False) count and
share, and the composite failure mass (carried + no-grasp), so a class
*relocation* (carried -> no-grasp) cannot pass.

**Secondary**: the pooled placed count, the per-arm placed counts, the median
cycle (ticks; the aligned arm's span is expected to be shorter by the ~1.5 s
the reset advance removes from the attempt by construction — quoted as a
consequence, not evidence), the model calls per attempt (the alignment removes
~45 chunks of the pre-first-view wait), and the fire-time `dx`/effective lead
(`[acq]`) for a mechanism check.

**The arm occlusion (the named alternative)**: the target mask at the
**decision/fire zone** (along 0.15-0.30, the P34 phase-1 arm window) from the
direct env's own frames: the `[align]` row's `zone_n`, `zone_zero`, `zone_px`
per episode, aggregated per arm as the zero-mask fraction and the rendered
visible fraction (`zone_px / 212's unoccluded projected area`). Phase 1 read
0.23-0.60 zero-mask in the demos at that y (the arm over the belt). If the
zone's zero-mask fraction is high in the direct env too, the **arm** is named
as the co-occluder in the falsifier (it would mean the fruit is (partly)
hidden at the decision zone by the policy's own arm, which the reset alignment
does not touch).

## 5. The decision rule and the falsifier (fixed now)

* **Manipulation check fails** (B < the bar in §2): implementation failure; no
  outcome claim; diagnose the first-call along/vis and re-record.
* **Manipulation check passes and the left's outcome moves the pre-registered
  way** (the left's placed count >= A and the carried-class pairing favors B,
  or the left's carried + no-grasp mass falls with no new failure reason):
  the reset alignment is a measured interface win; it still ships **default
  off** (a separate adoption gate: the direct-path history and any checkpoint
  are re-baselined, the scripted line is untouched by construction).
* **Manipulation check passes and the left does not move** (no carried-class
  conversion in B's favor, no left placed-count gain, no composite-failure
  reduction): **the falsifier fires — the early view is not the mechanism** of
  the left's acquisition/outcome on this scenario; publish the negative and
  leave the scene lever (Phase 3) as the remaining candidate. This is the
  pre-registered default expectation of a first-view lever.
* New failure reasons, or a right-arm/class regression, are reported and block
  any adoption claim.

## 6. The implementation (fixed now)

`rl_env.SortingRLEnv.reset` only, `presentation == "direct"` only, default
off: after the reset's setup (the arm teleport, `advance(20)`, `belt.start()`)
advance the line tick-by-tick (`advance(1)` + `spawner.enforce_transport()`,
the control loop's own pair) until the target's along is `0.399 + belt_speed *
execute_steps / 120` = 0.403 m (so the **first call**, 4 ticks later, is at
0.399). Cap `FRUIT_RESET_ALIGN_MAX_TICKS` 600. No feeder `update` (the release
schedule is not advanced), no arm command change (the arm holds the calibrated
grasp pose, like the demos' wait loop). The advance happens before
`_episode_t0`, so the attempt's own span/ticks exclude it. The `[align]` row
(`FRUIT_RESET_ALIGN_DIAG=1`) is pure reporting: the selection `y0`, the reset
along, the alignment ticks, the first call's along/x/d and target-mask pixels,
the first visible call and hidden-call count, and the fire-zone mask counters.

**No-harm**: with the knob unset the block is one False branch, no sensor /
articulation read and no physics advance; `self._sample`, the RNG stream and
the `[fruit]` stream are unchanged. The acceptance (`accept.sh`, the scripted
line) is run with the knob unset and its `[fruit]` stream compared to the
current record (`logs/p33/40_accept_final.log`). `selfcheck.sh` is run at the
end.

## 7. Provenance

`logs/p34/A_ab/` (the batch: `A_N.log` / `B_N.log`), `A_align.txt` (this
pre-registration's manipulation check + arm occlusion), `A_verdict.txt`
(`scripts/113_rl_report.py`), `A_class_split.txt` (`logs/w7/C_class_split.py`),
`A_pairs.txt` (`logs/w8/A_pairs.py`), the driver `run_p34_ab.sh`, the tree
pins before/after. No shipped default changed.

## 8. Post-batch erratum (Gate 2, 2026-10-23)

The pre-registered text above is left verbatim; these are the corrections
found when the batch was read.

* **The manipulation check is a fruit-position check, not a visibility check.**
  Its second leg uses `212`'s **analytic belt-only** visible fraction; the
  *rendered* target mask was reported as a cross-check and then turned out to be
  empty at the first call in **72/75 (A) and 71/75 (B)** episodes because the
  left arm occludes it. So the aligned arm never presented a visible first
  view: **the visible-first-view hypothesis is untested** and the report's
  outcome claim is limited to "aiming the first call at 0.399 with this reset
  pose does not move the left".
* **The §5 bullets are ambiguous on this outcome.** Bullet 2's "the left's
  carried + no-grasp mass falls" fired by 3 episodes (28 -> 25) but was written
  as the §4 **relocation guard** (a class relocation must not pass), not as a
  win condition; bullet 3's "the left does not move" requires *no* left placed
  gain and *no* composite reduction, which is literally not the case (placed
  1 -> 2). The primary (§4) is the paired carried-class conversion: **0 B-only /
  1 A-only, p = 1.0** - no adoption.
* **§1/§4's "the demos' first view +0.399" is the two-line stores' value.** The
  single-arm store `demos_v11` reads **+0.441**, and 0.399 is **42 mm
  downstream** of it (the A/B's first calls +0.484 / +0.398 bracket it). Its
  masks are **per-arm**: at +0.25..+0.30 the zero-mask is left 0.56 (n=63) /
  right 0.92 (n=558), and the left is visible at its own x band (125 frames,
  zero 1 %, median 0.94) - so the store does not supply the arm occlusion the
  direct env shows; the direct env's left first calls at x 0.32-0.37 are empty
  in 11/11 (A) and 6/6 (B), a **new direct-env/reset mismatch** (hypothesis: the
  reset's arm pose/settle; **unmeasured**).
* **The pairing's diameter guard is 0.05 m** in the report script (the docstring
  claimed 0.5 mm; corrected). Every retained pair matched at the store's 0.1 mm
  resolution, so the guard is inert on this batch; the pinned species-only read
  (3 B-only / 4 A-only, p = 0.7734) is quoted alongside the report's (2/3,
  p = 0.8125).
* **The report is a post-batch read.** `align_report.py` and `A_align.txt`
  carry 19:44, three minutes after the batch's last log (19:41). The script is
  read-only over `A_ab/*.log` and the batch logs' mtimes are their run times, so
  no outcome data was regenerated - but the amended reporting section is not a
  pre-registered artifact.
