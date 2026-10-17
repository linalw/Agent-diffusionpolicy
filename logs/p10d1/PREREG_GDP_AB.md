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

1. **Primary: the close-start |dx| distribution** (`[acq]` rows; the W7-B form) - B must not
   be worse than A on the median and the tail; the pre-registered positive form: the median
   |dx| falls or holds with the no-fire count non-worse.
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
3. the cycle rises more than +5 % (the per-attempt span; the sampling cost must not leak into
   the loop);
4. the offline stub suite fails.

## The no-harm bar

The shipped acceptance on the GDP tree (the GDP default off): 9/10 + `fingerprint: matches` +
385/385 vs `logs/p2d/90_accept.log`; the two-line dense re-record 442/442 + `190` PASS;
`selfcheck.sh` PASS; `172` PASS.

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
