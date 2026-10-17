# P10-D.1 PREREG (FROZEN): the GDP OoD-scored population selection - the direct-interface A/B

Frozen 2026-10-17 before any Tier-A run. Tree pin recorded at battery time (the implementation
lane's md5). Branch `p-supply`; the P10-C.3 wrap at `ed166a8` (tag `p10c3-gate`).

## Why (the P10-B KB's rank 5; `docs/papers/MECHANISMS.md` item #5)

The owner's goal includes the model side (the diffusion policy + the fast closed loop). The
mechanism menu's item #5 is the pre-committed model item: a **training-free** sampling
improvement - K in {2,3} DDIM-16 samples from different noise, select by the paper's OoD
score (or the min within a plausibility band), logging the per-candidate finger spread. Its
named endpoints: "no-fire + close-start |dx| (seeds 77/101/202); then N=5 paired
carried-class". The P6 adversarial re-read's correction (the menu's corrections table) is
part of the mechanism read and is quoted in the implementation record.

## The arms (the direct presentation; the R5 interface rules)

| arm | env | notes |
| --- | --- | --- |
| **A** | the shipped sampling (`moe_v13s`, `checkpoints/moe_v13s/policy_best.pt` `61da390a...`) | the control |
| **B** | A + `FRUIT_POLICY_GDP=1 FRUIT_POLICY_GDP_K=2` | the treatment (K=2; K=3 is a named follow-up if K=2 passes) |

Both arms instrumented (`FRUIT_ACQ_DIAG=1` where the readouts need it, per the W7-B form);
the same `AB_POLICY_SEED` so the sampler differences are the same across arms.

## Stage 1 (the mechanism endpoint; the pre-registered decision point)

`RUNS=3 EPISODES=15 AB_SEEDS="77 101 202" ARM_A_ENV="" ARM_B_ENV="FRUIT_POLICY_GDP=1
FRUIT_POLICY_GDP_K=2" scripts/112_rl_ab.sh` (interleaved A,B,A,B,A,B; ~3 h wall).

1. **Primary: the close-start tip-fruit |y| offset distribution** (`[acq]` `close_start`
   index 1; the W7-B report's `close-start |y| mm` line - **not** the trigger's `dx` column) -
   B must not be worse than A on the median and the p90 (the tail = the 90th percentile of
   |y|); the pre-registered positive form: the median falls or holds with the p90 non-worse
   and the no-fire count non-worse.
2. The no-fire count (the "timeout: no grasp" / the trigger no-fire classes).
3. The per-arm outcomes (reported, not gated - the draw discipline).
4. The wall cost: the per-candidate sampling time measured offline; reported against the
   ~12 ms/candidate claim and the 8.3 ms tick (the honest overrun note).

## Stage 2 (only if stage 1 reads non-worse; the full protocol)

The WS-4.2 N=5 paired carried-class form (5 runs/arm x 15 episodes, the full seed schedule
[77,101,202,303,404]), the paired carried-class conversion endpoint (the 6-0 edge at N=5 for
p <= 0.05), the cycle non-inferiority margin (+5 %), and the no-harm bar.

## Kills (any one; stage 1)

1. The knob-off byte-inert proof fails (the GDP-off path must equal the shipped path - the
   same noise draw);
2. a new failure reason appears;
3. the cycle rises more than +5 % (the per-attempt span in simulated time - the wall cost
   cannot enter the sim clock under fixed stepping, so this gates the action-side cycle
   drift);
4. the offline stub suite fails.

## The no-harm bar

The shipped acceptance on the GDP tree (the GDP default off): 9/10 + `fingerprint: matches` +
385/385 vs `logs/p2d/90_accept.log`; the two-line dense re-record against its **post-P10-C.3
branch** - the dense reference re-recorded from the re-run and `190` PASS against the new
reference (the pre-flip W7-A 442/442 identity no longer applies: the P10-C.3 flip arms the
carry monitor in every two-line session - `logs/p10c2/PREREG_ADOPT_FLIP.md`; the dense
re-record is the named follow-up, `logs/p10c3/C3_RESULTS.md` section 4); `selfcheck.sh` PASS;
`172` PASS.

## What this does NOT do

It does not retrain (no checkpoint change); it does not touch the shipped single-arm/two-line
scripted defaults (the policy knobs are default-off); it does not claim a carried-class
conversion from stage 1 (that is stage 2's endpoint).

---

## Amendment (FROZEN 2026-10-17, before the battery; the boundary pin)

**Stage 1's boundary envs are the W7-B/W4-pinned direct form** (so the mechanism readouts
compare directly to the W7-B record): `AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival
FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=0
FRUIT_POLICY_TRIGGER_LATERAL=0.06 FRUIT_ACQ_DIAG=1"`, the sampler seed 11, both arms the
`moe_v13s` checkpoint; arm B adds `FRUIT_POLICY_GDP=1 FRUIT_POLICY_GDP_K=2`. The runner is
`logs/p10d1/run_stage1.sh` (the W7-B `run_w7b_ab.sh` shape); the mechanism report is
`logs/w7/B_ab_report.py --dir logs/p10d1/stage1`.


---

## Amendment 2 (FROZEN 2026-10-17, the Oracle gate's required fixes; before any result is read)

F3: the dense no-harm leg is restated for the post-P10-C.3 branch (above). M3: stage-1
endpoint 1's "tail" is the p90 of |dx|. The rest of the prereg is unchanged. (The Oracle's
M2 - recording `FRUIT_CARRY_MONITOR_TWOLINE` in the collector manifest alongside the master -
is deferred until after the live stage-1 battery so the battery's tree pin stays frozen.)


---

## Amendment 3 (FROZEN 2026-10-17, the P10-D.1 Oracle gate's F1/F3/F6; before any result is read)

- F1: endpoint 1 is the close-start tip-fruit **|y| offset** (the W7-B report's `close-start
  |y| mm` line), not the trigger's `dx` column. F3: kill 3 gates the action-side cycle drift.
- F6: **the falsifier follow-up** - the P6 re-read's falsifier has two halves: the
  score-vs-outcome half is testable by a diag-on mechanism run on arm B
  (`FRUIT_POLICY_GDP=1 FRUIT_POLICY_GDP_K=2 FRUIT_POLICY_GDP_DIAG=1`, the same boundary pin,
  seed 77) joining the `[gdp]` scores to the per-episode outcomes (a named follow-up, not
  part of stage 1); the frame-vs-noise attribution half is **not testable** from the `[gdp]`
  row as implemented (`fingers` is a within-chunk range of channel 7, not a cross-candidate
  dispersion; it needs a fixed-noise/fixed-frame probe) and stays recorded as untested.
- The stage-1 record must state that arm B's treatment provenance is the driver env echo +
  the frozen runner (F7's manifest field is deferred until after the live battery).
