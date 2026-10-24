# P36 — The P35 mechanism discriminator (proprio-spoof x image-spoof)

Started 2026-10-24 (owner: "继续"). Full delegated authority; an Oracle gate per
phase.

## 1. The question (from P35)

The P35's park is a **measured interface lever** (the right 23/51 -> 47/50, the
carried class 25 -> 0, B > A 5/5 runs, one-sided p = 0.031), but the **mediator
is not identified**: the park changes the image (the arm silhouette 3497 -> 4155
px) **and** the 7 inactive-arm joints of the 25-D proprio, and the control
**succeeds with the fruit invisible** (9 of its 23 right successes read px=0 at
every band call; the successes' fully-hidden share 0.84 vs the failures' 0.60) -
so a simple perception bottleneck is not the story.

## 2. The design (the 2x2)

| cell | the inactive arm (the image) | the obs proprio | the role |
|---|---|---|---|
| 1 | ready | ready | the control (the shipped) |
| 2 | park (`back`) | park (`back`) | the lever - reproduce the P35 |
| 3 | park (`back`) | ready | the **image-only** probe |
| 4 | ready | park (`back`) | the **proprio-only** probe |

- The image main effect = ((2+3) - (1+4)) / 2; the proprio main effect =
  ((2+4) - (1+3)) / 2; the interaction = (2 - 3) - (4 - 1).
- The endpoints: the right's carried-not-placed (the primary), the right's
  placed/composite, the pooled; the per-class; the no-new-reason; the cycle.
- The N: 3 runs x 15 per cell (180 episodes), the seeds, interleaved; a power
  note (the P35 effect is 25 -> 0 at n=51).
- The OOD caveat: the cells 3/4 are **synthetic** (the policy never saw the
  park's image with the ready proprio, or vice versa) - probes, not deployable
  configurations; a positive in a spoof cell names the channel, it does not
  ship.

## 3. The plan

| # | Phase | Deliverable | Owner | Gate |
|---|-------|-------------|-------|------|
| 1 | The pre-registration + the 2x2 implementation | the PREREG (the cells, the endpoints, the N, the analysis, the falsifiers); the `FRUIT_PROPRIO_SPOOF` knob (the 7 inactive-arm joints in the obs; default off; byte-inert) + the existing `FRUIT_ARM_PARK`; the offline obs-diff check | @general | Oracle 1 |
| 2 | The 2x2 A/B | the 4 cells x 3 runs; the analysis (the main effects + the interaction + the per-cell); the honest read | @general | Oracle 2 |
| 3 | The integration + the decision | the docs/commits; the adoption path (the image-borne -> a recollection's own A/B; the proprio-borne -> the checkpoint/proprio interface; both) | @general + orchestrator | Oracle 3 |

Oracle budget: 3 gates (1 initial + up to 2 re-reviews each).

## 4. The risks

- The spoof cells are OOD probes; the policy's response to them is a
  mechanism readout, not a deployment.
- The 180-episode batch is ~3-4 h; the per-cell n=45.
- The composition/pairing (the P35 lessons: the run level + the standardised
  counts; the pairing is post-treatment-conditioned).
- The image-spoof implementation must leave the **active** arm and the fruit
  untouched; the proprio-spoof must touch only the 7 inactive-arm indices.

## 5. The log

- 2026-10-24: the file; the design; Phase 1 dispatched.
- 2026-10-24: **Phase 1 delivered.** `logs/p36/PREREG.md` (the 4 cells, the
  endpoints, N = 3x15/cell interleaved with a rotated order, the two exact
  Fisher main effects + the within-stratum interaction permutation, the
  redundancy/synergy reading of the interaction, the effect-fraction bands, the
  falsifiers, the OOD caveat). The knob **`FRUIT_PROPRIO_SPOOF=<pose>`**
  (default off; writes only the inactive arm's 7 joints - left
  `0,2,4,6,8,10,12`, right `1,3,5,7,9,11,13` - from
  `configs/proprio_spoof.json`, whose vectors are the P35 measured `q_settled`
  poses), the `[spoof]` certificate diag, the manifest block, and the
  `proprio spoof check` selfcheck leg. **The offline check: failures=0** (the
  vectors == the P35 rows; the layout == `logs/33_dof.log`; 7 written / 6 read
  as changed / the other 15 bit-identical; the rest-of-vector hash equal). **The
  smoke** (6 one-episode cells, `logs/p36/P1_smoke.txt`): S1-S4 pass - the
  no-op drift 0.0059 (ready) / 0.0141 (back) rad against the 0.02 bar, the
  substitution 0.6035/0.6036, `rest_same=1`, the image cell follows the arm
  (`arm_px` 234 vs 0), and **the pre-spoof proprio hash is bit-identical inside
  each physical pair** (cells 1/4 `68e0e753`, cells 2/3 `98b0df03`). No-harm:
  acceptance **6/10 + `fingerprint: matches`** with **376/376 `[fruit]` lines
  identical** to the P35 record; selfcheck PASS. Phase-2 tooling written and
  self-tested (`scripts/219_p36_cells.sh`, `scripts/220_p36_report.py`).
  Evidence `logs/p36/P1_IMPL.md`.
- 2026-10-24: **Phase 2 dispatched** (the 4 cells x 3 runs x 15 episodes, one
  claim, then `scripts/220_p36_report.py`).
- 2026-10-24: **Phase 2 delivered (Oracle 2 pending).** The 12-run batch (one
  claim, `RUN_LIMIT=25200`, 19:39-21:04, 5146 s) with the randomised rotation
  `2 3 1 4 / 3 1 4 2 / 1 4 2 3`. **The manipulation check passes** from the
  batch's own rows (S1 28/28 + 30/30 written bitwise; S1c 0.0020/0.0040 rad vs
  the physical counterpart; S2 180/180; S3 115/115; **S4** the image follows the
  arm, not the spoof: 670/670 and 724/724 calls with arm pixels in cells 1/4 vs
  0/741 and 0/680 in cells 2/3, no-op side 0/1555). **The 2x2** (right-arm
  carried): cell 1 **18/27 = 0.667**, cell 2 **0/30**, cell 3 **0/28**, cell 4
  **17/30 = 0.567**; image **0/58 vs 35/57, p = 8.8e-15**; proprio **17/60 vs
  18/55, p = 0.687**; interaction **+0.100, p = 0.581**; fractions
  **+1.00 / +1.00 / +0.15** (standardised +1.00/+1.00/+0.10). **Reading:
  IMAGE-BORNE** - the parked image alone reproduces the whole conversion, the
  parked proprio alone sits at the control level and inside the no-op left arm's
  own contrast (0.050 vs 0.119; the left is at the carried ceiling
  0.73-0.89). Gate-1 fixes landed pre-batch: H1 (`RUN_LIMIT` + a driver refusal
  below 7200 s), H2 (a 3-complete-run refusal, exercised on the partial tree),
  M1 (`|T*| >= |did|` with the miss-centred form pinned at 0.5013 vs the fixed
  0.0050), M2 (S1-S4 as gating assertions), M3 (n = 60/arm, the
  0.998/0.977/0.894/0.724 quartet), M5 (the OOD asymmetry: ready max |z| 0.59;
  back j2 at -4.26 sigma), plus the Fisher epsilon (8.1e-13 -> the exact
  8.8e-15) and the `--record` store guard. No-harm: acceptance **6/10 +
  `fingerprint: matches`** with **376/376** `[fruit]` lines identical to the P35
  record; selfcheck PASS. Evidence `logs/p36/A_RESULTS.md`, `A_ab/`. **No commit;
  no shipped default changed.** **The next decision is the orchestrator's**: the
  shipping path stays a recollection's own A/B (this read is consistent with a
  pixel fix, not a substitute for it); the image statistic (occlusion vs
  context) is the named open question.
- 2026-10-24: **Gate 2 (Oracle 2) - the reading narrowed to the channel, the
  record fixes landed, the P36 work committed.** The claim is now **the image
  channel, with the fruit's sightline the leading *unseparated* candidate**
  (A_RESULTS §3/§5/§7, the WORKLOG heading + the new Gate-2 entry, `220`'s
  `READING_TEXT`, `PREREG` §7/§10), and the recollection's A/B is described as
  **consistent with** a pixel fix, not substituted by this probe. **The OOD
  summary rests on j2's range violation** (the only channel outside either
  store's observed range; the 4-5 sigma summary is a mixture statistic;
  conservative direction, no downstream change) - in `PREREG` §8a, A_RESULTS §5,
  the report text, and `ood_proprio.py`'s new per-vector range line (its numeric
  table re-runs byte-identically). The interaction is reported as the
  **pre-registered descriptor only** ("adds nothing measurable under the
  ceiling"). `220`'s manipulation gate gains **M2's count invariance**
  (`4 x 15 x n_runs`, >= 1 `[park]` row per cell-run) and a self-test that
  deletes one row and expects **exit 2**; the batch reads **180/180**. The
  `218` self-test now drives the real `check_vectors` (accepts the file's
  vector, rejects a perturbed one) instead of comparing constants. Provenance
  disclosed: `ood_proprio.py` 19:43 (data-independent), `power_check` design-only,
  `PREREG.md` 21:20 = the post-batch item 8; `219`'s header now pins the driver
  (`md5sum "$0"`). **N = 3 is a probe; the recollection's A/B must be N = 5**
  (WS-4.2). No number and no decision changed; the probes do not ship.
