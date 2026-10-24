# P37 phase 1 pre-registration — the park-collected recollection and its N = 5 adoption A/B

Written 2026-10-24 **before any run of this phase** (no collection shard, no
fine-tune, no A/B exists when this file is written). It fixes the scenario, the
store, the recipe, the A/B, the endpoints, the decision rule, the falsifiers and
the confounds of phases 1-2 of `.slim/deepwork/p37-park-recollection.md`.
**No shipped default changes**: `FRUIT_ARM_PARK` stays default off
(`rl_env.py`), `FRUIT_PROPRIO_SPOOF` stays default off and is **not** used here,
and the scripted/hybrid acceptance paths are untouched by construction (the park
is `presentation='direct'` only — the env raises otherwise).

## 0. What is measured, what is not, and why this phase exists

**Measured (P35, `logs/p35/C_RESULTS.md`)**: with the *inactive* left arm at
`back` instead of `ready`, on the direct interface's patch scenario, the right
arm's **carried-not-placed** class goes **25/51 -> 0/50** and its success
**23/51 (45 %) -> 47/50 (94 %)**; run-level **5/5**, one-sided p = 0.031; pooled
24/75 -> 49/75; the manipulation check shows the park removes the fruit's band
occlusion (fully-hidden band calls **68.1 % -> 0 %**).

**Measured (P36, `logs/p36/A_RESULTS.md`)**: the park's win is **image-borne**
(image main effect p = 8.8e-15; proprio p = 0.687; the parked image with a
`ready` proprio reproduces 0/28 carried). The **proprio-spoof and image-spoof
are inconsistent input pairs and do not ship**.

**Not measured, and the object of this phase**: whether a checkpoint **trained on
the parked distribution** keeps the win. P35/P36 measured a
*checkpoint-specific input-shift* effect on `moe_v13s`; every rollout store and
checkpoint on this tree is pre-park. The shipping path for the lever is a
**recollection collected under the park** (both input channels fixed at once)
with its own A/B. That is the question here.

**What this phase cannot show.** It cannot separate the image from the proprio
(P36 did, at N = 3); it cannot establish a *rate gain* (the base is at 94 % of a
~6 %-headroom ceiling, and the arm is set by the fruit's grade, so the pooled
rate is dominated by the left arm's post-trigger carry class); and a pass is
**not** an adoption — the shipped default is the owner's decision
(`.slim/deepwork/p37-park-recollection.md` phase 3).

## 1. The question

**Does a fine-tune on the policy's own rollouts collected under the park
preserve the park's win on the deployment configuration?** Two named outcomes:

* **preservation** — the candidate is not worse than `moe_v13s` on the parked
  scenario by more than the pre-registered margin (the adoption *candidate*);
* **erasure** — the candidate loses the win (the recollection re-anchored on the
  shipped `ready` distribution), in which case the recollection closes negative
  and published.

## 2. The scenario (the deployment configuration, verbatim)

The direct presentation, the W6-A 2D patch sheet, the W8-A/P35 interface of
record. Every run of this phase (collection, A/B) uses exactly this block:

```
FRUIT_ARM_PARK=back
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_POLICY_TRIGGER_ACQ=1
FRUIT_DYNAMIC_PICK=1
FRUIT_CAMERA_RES=240,424
FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1
scripts/110_rl_rollout.py --presentation direct --execute-steps 4 --ddim 16
```

`FRUIT_POLICY_TRIGGER_LATERAL` is **not** set: the shipped 0.16 is the W4
default and the patch band's calibrated value. `FRUIT_POLICY_TRIGGER_ACQ=1` is
the **R5 measurement interface, not a shipped default**; the park is
`presentation='direct'` only, so the direct interface *is* the deployment
configuration this lever can ship on — the hybrid canary
(`scripts/accept_policy.sh`) cannot run the park at all and is unaffected.

**Pins at the pre-registration** (md5, `logs/p37/tree_md5_before.txt` is written
by the phase-1 driver before its first run): `tasks.py` `cdde6bd2`,
`rl_env.py` `aa54b022` (the P36 tree, park + spoof + `store_guard_reason`),
`policy/trigger.py` `d7ec85fc`, `policy/runtime.py` `379ac706`, `meshes.py`
`41efc522` (post-pear), `configs/arm_parks.json` `42ab4fb7`,
`configs/motion_reference.json` `25ade92b`; checkpoint `moe_v13s`
`checkpoints/moe_v13s/policy_best.pt` md5 `61da390a`; base store `datasets/demos_v11`
`index.json` md5 `922ca995`.

## 3. The store (phase 1: collection)

**Why the direct-rollout store and not the collector.** `scripts/40_collect_demos.py`
parks through `tasks.go_ready` (the scripted path): it has **no park**, so a
collector store cannot carry the parked image. The faithful path is
`scripts/110_rl_rollout.py --record` under the park — the same env, the same
reset, the same observation assembly the deployment uses. The P36 guard
(`rl_env.store_guard_reason`) refuses `--record` **only** with
`FRUIT_PROPRIO_SPOOF`; `FRUIT_ARM_PARK` is explicitly allowed and named in the
manifest's `arm_park` block. This phase runs **no spoof**.

**The recipe as executed** (`scripts/221_p37_collect.sh`):

* one recorded shard per spawn seed, **15 episodes per shard**, seeds
  **505 / 606 / 707 / 808 / 909 / 1010** (disjoint from the A/B's
  77/101/202/303/404);
* **target 90 episodes; pre-registered floor 60** (a shard dir is **never
  re-run** — `RolloutRecorder` restarts its file numbering at 0, so a second
  run into the same dir would overwrite earlier episodes; a wedged shard's
  finished episodes are kept and the next seed is run instead. The declared
  spare seeds **1111 / 1212** run only if the six shards leave the total below
  the floor. If the total reaches >= 60 the merge proceeds and the shortfall
  against 90 is recorded, not hidden);
* `FRUIT_POLICY_SEED=11` (provenance: the sampler state is recorded in each
  manifest; the A/B uses the same seed, and the store's states differ, so no
  action stream is shared);
* **no diagnostics** (`FRUIT_ACQ_DIAG` / `FRUIT_CARRY_DIAG` / `FRUIT_PARK_DIAG`
  all off): the store is training data. Per-call articulation reads change the
  outcome (P35: the park diag moved the control's pooled rate 29/75 -> 24/75),
  and a recorded store must be the pure deployment path;
* shards merged by `scripts/197_r9_merge_rollouts.py` into
  **`datasets/rl_rollouts/p37_park`** (a byte copy with renumbering + a `shard`
  stamp + `merge_manifest.json`), the R9 schema unchanged.

**Expected composition** (from P35's B arm; the audit reports the measured
counts, and a deviation is reported, not smoothed): ~68 % right-active
(the parked-image population; ~94 % ok, ~0 carried, ~6 % no-grasp) and ~32 %
left-active (the inactive **right** arm has no park vector — `arm_parks.json` is
left-only — so those episodes carry the shipped inactive-arm distribution and
fail at ~92 % in the carried class). Pooled success ~65 %. **All episodes are
kept, successes and failures**, by the recorder's design.

**Store audit** (`logs/p37/store_audit.py`, the `106`-style check plus the RL
fields): every index row's file exists, `frames` matches the npz, no unlisted
file, no duplicate entry/content; the class counts (`ok / carried-not-placed /
no-grasp`) per arm and pooled; the grade/species/diameter distributions; the
window count the loader will see; and the provenance block — the merged store's
`merge_manifest.json` shard md5s, each shard's `manifest.json`
**`arm_park` = `back`** (file + sides) and `checkpoint_md5` = `61da390a`,
`tasks_md5`, `belt_speed` = 0.12, `camera_res` = 240,424, `trigger` = the block
above. **Recorded limitation**: the rollout manifest has **no supply block**
(the collector's `supply.patch` field has no rollout twin), so the patch sheet is
pinned by the recorded command line + `logs/p37/collect_*.log`, not by the
manifest. Adding that field moves the `rl_env.py` pin and is its own change; it
is a named follow-up, not done here.

## 4. The fine-tune (phase 2)

**Recipe** (the lineage recollection recipe, `moe_v12 -> moe_v13s` and
`moe_v12 -> moe_v13p`):

```
scripts/111_rl_finetune.py --ckpt checkpoints/moe_v13s/policy_best.pt \
    --rollouts datasets/rl_rollouts/p37_park --base datasets/demos_v11 \
    --out checkpoints/p37_park --epochs 6 --lr 5e-5 --weight-mode ones \
    --base-weight 1.0 --batch-size 32 --seed 0
```

* **`weight_mode=ones`** — the W7-C recollection mode, and the mode all three
  lineage checkpoints were trained with (`moe_v13s`, `moe_v13p`: `ones`,
  6 epochs, lr 5e-5, base `demos_v11`). The two alternatives carry **measured
  negatives on this interface**: `success` weighting *is* RWR iteration 1
  (binary 1.0/0.05, measured 49 % vs 63 %), and `awr` is R9 (`rl_awr1` 18/75 vs
  25/75, the paired carried class 5-4 p = 0.500, and its fidelity readout moved
  the policy **away** from its own rollouts, 0.087 -> 0.174 rad, producing 6
  reach-cliff flails vs 1). Choosing either would re-run a measured negative
  rather than test the recollection.
* **Why `ones` over a mixed store is still the right mode**: the store's
  failures are **not the recorded phase's failures** — the policy phase is the
  pre-trigger approach, and R9 measured the carry window to be
  **branch-invariant** (the scripted primitive owns it after the trigger). An
  outcome-weighted store would therefore select *approaches* by a label their
  phase does not own, which is exactly the R9 failure mode. `ones` keeps the
  parked input distribution (the object of the recollection) at full weight.
* **Anchor** `moe_v13s` (arm A of the A/B) so the comparison isolates the
  store; **base** `demos_v11` (50 episodes / 9,378 windows) — the single-arm
  anchor both `moe_v13s` and `moe_v13p` used.
* **Candidate path** `checkpoints/p37_park/policy_best.pt`; its md5 and
  `finetune_history.json` are recorded in `logs/p37/tree_md5_ab.txt` **before**
  the A/B starts. **One-way**: the A/B may not be re-run with a different
  candidate under this pre-registration.

**Declared confound (the one that can erase the win, stated a priori)**: the
store is ~3-5k windows against the base's 9,378, i.e. a rollout window share of
~30 % against the recollection precedent's 77 % (`demos_v13p`: 32,284 vs 9,378).
The base is the **`ready` distribution** and dominates the update by count, so a
`ones` pass at this ratio can pull the sampler back toward the pre-park
behaviour. This is not tuned away: the recipe is the lineage recipe, and the
confound is measured by the fidelity readout below and by the A/B. If the
primary fails, this is the first named cause (section 9).

**Diagnostic (not a gate)**: `scripts/119_rl_fidelity.py` base vs candidate on
the park store and on `demos_v11`, 192 windows, DDIM-16, fixed per-window noise
(R9's readout; it predicted R9's downstream degradation). It is run before the
A/B and reported with it.

## 5. The A/B (phase 2, the adoption gate)

`scripts/112_rl_ab.sh` inside **one** `154_claim_run.sh` claim (the P36
convention: one claim, several sessions):

* **N = 5 runs x 15 episodes per arm** (~45-52 right-arm episodes per arm at the
  measured 64-68 % right share), seeds **77 / 101 / 202 / 303 / 404**, sampler
  seed 11, **interleaved A,B** inside each run;
* **both arms parked** (`FRUIT_ARM_PARK=back`): A = `moe_v13s` `61da390a`,
  B = `checkpoints/p37_park/policy_best.pt`;
* the whole section-2 block on both arms, plus the **same instrumentation on
  both** (`FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1`) — AGENTS
  section 3b: arms compared inside one instrumented batch;
* **manipulation check (gates the outcome read)**, from the batch's own
  `[park] episode` rows, right-active episodes only: `park=back`,
  `m1_hold_ok=1` and `m2_arm_ok=1` (`arm_px = 0`) on **>= 95 %** of them, and
  the band census (`band_calls > 0`). If it fails, the batch is **void for the
  outcome** and re-run; it is not read with a caveat. (P35 read 50/50 and
  0/1236 arm-tainted calls, so this is a regression guard, not a discovery.)

**Known design notes, recorded rather than fixed**: `112_rl_ab.sh` runs A then B
inside each run (no randomisation), so an order term is confounded with the
checkpoint — the same caveat P35 recorded; and the direct loop's rendered frames
are not bit-reproducible, so **one run is one sample** and the pooled batch
(with its own arm A as baseline) is the measurement.

## 6. The endpoints and the decision rule

Classes (the P33/W8-A convention, from the `[rl] episode` rows): **ok** =
`success`/`placed`; **carried-not-placed** = `grasped and not placed`;
**no-grasp** = `not grasped` (the same class `196_r9_report.py` prints as
`no-contact`); **composite failure** = carried + no-grasp.

**Primary (the preservation bar, one-sided non-inferiority).** The **right arm**
is the park's population (the park moves the *inactive left* arm; a right-active
episode is the one that sees it). Pooled over the batch:

```
pass  <=>  ok_B / n_B  >=  ok_A / n_A  -  0.10          (MARGIN = 0.10 absolute)
```

**Why 0.10, fixed in advance** (`logs/p37/power_check.py`, design-only,
`logs/p37/power_check.txt`): at the expected n = ~50 right-arm episodes per arm
and a base of 0.94, a preserved candidate (p = 0.94) passes in **99.1 %** of
batches (a 0.9 % false-erasure rate, the test's own cost); the erasure state
(the parked win gone, p ~ 0.45 = P35's control) passes in **0.0 %**; a candidate
at p = 0.85 is ambiguous (60.8 %) and is reported as ambiguous, not rounded.
PASS/FAIL is read on the pooled counts; the **run-level direction** (B's right
ok >= A's per run, count of 5) is reported, not gated (P35's 5/5 was a two-arm
contrast with a 49-point gap; here the expectation is a tie).

**Secondary (reported, no separate gate — they are the same events in other
cuts, so gating them would double-count the primary):**

* **S1 the right-arm class table** (ok / carried-not-placed / no-grasp) and the
  **P33 paired carried-class conversion** on exact same-fruit pairs
  (run + episode + species + diameter + arm). **Pre-registered degeneracy**: the
  park's own B arm read **0/50 carried**, so the carried-class endpoint this
  repo has used since P33 has almost no events under the park; its sign test is
  reported with that denominator, and the pairing is in any case conditioned on
  a post-treatment variable (P35's 22/75-usable lesson);
* **S2 the standardised rates** (direct standardisation to arm A's right-arm
  species mix, and to diameter tertiles) — the arms draw different fruit after
  the first divergence, so the crude and standardised tables are both shown;
* **S3 no new failure reason**: the normalized reason sets (`113`'s suffix
  normalization) — candidate reasons must be a subset of the base's. **The gate
  is the pooled set over both arms**; the **right-arm cut** — the primary's
  population — is reported beside it as a specifier (the left arm is a no-op
  with its own large carried class). In the 2026-10-25 batch the single novelty
  is a right-arm event, so the two cuts agree;
* **S4 cycle**: pooled median ticks, candidate <= base x 1.05;
* **S5 the left arm** (a **no-op** for the park — the inactive right arm has no
  park vector, so left-active episodes are identical in both arms): reported as
  the batch's **one-sided noise floor**. At the measured ceiling (~2/25 ok) no
  bar can call a regression at n ~ 25; it is reported, not gated (P36 section 4's
  formulation).

**Decision rule (pre-registered).** The candidate is an **adoption candidate**
iff **primary PASS and S3 PASS and S4 PASS**. It is **not adopted** here in any
case: the shipped default (`FRUIT_ARM_PARK` off) is the owner's phase-3
decision, and a pass licenses *that* decision — it does not flip it.
**Kill criterion**: primary FAIL (or S3/S4 FAIL) closes the recollection
**negative and published**; no interim criterion moves, and the batch is the
endpoint. *(On the 2026-10-25 record the rule fired on S3; the event is a
scenario tail, so the formal closure stands and the reading is qualified -
section 7's note.)*

## 7. The falsifiers

* **The recollection erases the win** (the falsifier fires): the candidate's
  right-arm ok rate falls more than 0.10 below the base's, i.e. the fine-tune
  re-anchored on `ready` and the park's win was a checkpoint-specific input
  shift that a `ones` recollection at a ~30 % rollout share cannot preserve.
  **Named causes, in order**: (a) the base-store window dominance (the declared
  confound of section 4), (b) the store's ~32 % left-active failure frames at
  weight 1.0 diluting the parked signal, (c) the small store / 6-epoch overfit.
  The re-entry is a `base_weight`-matched variant (rollout share matched to the
  precedent's) with **its own pre-registration**; the park stays a documented
  default-off interface lever (P35) and the shipping path stays closed.
* **The recollection preserves it** (the falsifier does not fire): the primary
  passes, no new reason appears and the cycle is not worse — the recollection is
  consistent with a park-compatible checkpoint and phase 3 takes the owner's
  decision. Note what this is worth: a **pass is a preservation result at
  n = 50**, not evidence that training under the park improves anything over
  `moe_v13s` (the ceiling argument of section 0).

**Reading of the 2026-10-25 record (added with the Gate-2 conditions, no
pre-registration change).** The **first** bullet above is the *erasure* branch,
and it did not fire: the primary passed at A 0.977 / B 0.959. Its closing
sentence — "the park stays a documented default-off interface lever (P35) and
the shipping path stays closed" — is therefore **the erasure branch's wording
and does not describe this record**; the second bullet's branch applies (the
shipped default stays off because it is the shipped default and because the
candidate shows no gain, not because the recollection failed). The S3 rule
failed on a single **scenario-tail** event (the trigger's lateral gate is a pure
function of the fruit's x and the delivered supply's 0.148-0.364 m leaves a
~2.5 cm systematically unfirable tail; `logs/p37/P2_RESULTS.md` §4.5) — the
mechanical rule has no severity threshold, so the candidate is not an adoption
candidate, but the event carries essentially no evidence about the checkpoint.

## 8. The confounds (what this design cannot separate)

1. **The store's composition** — right-active (parked image, ~94 % ok) vs
   left-active (shipped inactive-arm distribution, ~92 % carried). The store is
   the deployment mixture, not a designed balance; the fine-tune sees both, and
   the left frames carry the failure class at full weight.
2. **The image and the 7 proprio channels are fixed together** in the store (the
   park is a real scene change). The recollection cannot say which channel it
   fixed; P36's 2x2 answered that separately at N = 3, and this phase inherits
   that read without re-testing it.
3. **The base:rollout window ratio** (section 4) — the recipe's one undeclared-
   until-here parameter. It is declared, measured by the fidelity readout, and
   not tuned.
4. **The policy loop's variance** — rendered frames condition the sampler and
   are not bit-reproducible; one run is one sample; the batch's own arm A is the
   baseline; no cross-batch rate comparison is made (the same checkpoint reads
   28 % in W8-A and 33 % in R9).
5. **The order** (A then B, fixed) and the **arm assignment** (by fruit grade, so
   the per-arm denominators drift between branches) — both reported.
6. **The collection's shard structure** — a wedged shard is retried; a merged
   store's composition depends on which shards completed. The audit reports the
   realized counts and the merge manifest pins each shard's index md5.
7. **A single collection** (one parked branch) — not a supply distribution; the
   store's fruit mix is the patch sheet's seeded draw, not a designed population.

## 9. No-harm and the shipped byte-identity

* `scripts/selfcheck.sh` PASS before and after (the `106` dataset audit, the RL
  env smoke, the `tasks.py` pin, the `197` merge self-test and the rest).
* The phase changes **no `src/` file and no shipped default**; the tree md5s are
  recorded before/after (`logs/p37/tree_md5_before.txt` /
  `tree_md5_after.txt`). The scripted acceptance with the knobs **unset** is run
  as the no-harm check; it is expected to read **6/10 + `fingerprint: matches`**
  (the pre-existing P32 pear-on branch, so the rate-only FAIL and `exit=1` are
  expected) with its `[fruit]` stream **identical** to the P35/P36 record
  (`logs/p36/A2_accept_raw.log`, 376 lines).
* `FRUIT_ARM_PARK` unset is byte-inert (one dict lookup per arm); the collection
  writes only `datasets/rl_rollouts/p37_*` and `logs/p37/`.

## 10. Deviations register

**#1 (before the collection, instrumentation).** A **2-episode smoke** ran with
`FRUIT_PARK_DIAG=1` and `--record` (`logs/p37/smoke.log`, store
`datasets/rl_rollouts/p37_smoke`), after this file and before the first shard, to
validate the env startup, the park's application, the recorder's index rows and
`logs/p37/store_audit.py`. It is **not** part of the store (not merged, seed 505,
2 episodes, a different out root) and carries **no outcome claim**. The audit
script's raw-shard manifest resolution was fixed on it, before the real store
existed; the fix reads metadata only.

**#2 (the collection, no deviation).** Six shards, 15 episodes each, first pass,
no wedge, no retry, no spare seed, 90 episodes — the pre-registered target, so
the floor clause was not used and the seed set is exactly 505/606/707/808/909/
1010. The realized composition (right 64.4 %, pooled ok 63.3 %) is reported
against the P35 expectations in `P1_RESULTS.md` section 2.

**#3 (the audit, a reading choice).** `scripts/106_index_audit.py` was run with
`--fast` (no content hashing; it would hash every rollout store under
`datasets/rl_rollouts`, not only this one); the duplicate-content check is
`logs/p37/store_audit.py`'s, which hashes **this** store's 90 files and reads
90 unique contents. Data-independent.

Any later post-batch change (print-only fixes, an analysis-side correction, a
data-independent edit inside a batch window) is appended here with its
data-dependence argument, the P36 section-10 convention.


**#4 (before the batch, the Gate-1 H1/H2 implementation).** The report
`logs/p37/p37_report.py` was written and its `--self-test` passed **before** the
fine-tune and the batch; its batch-time md5 is **`e17aef37`** (recorded in
`logs/p37/B_ab/B_header.txt`). The H1 definitions were fixed there, not after
the data: the exact unconditional non-inferiority p (sup over the nuisance rate
at the null boundary, full binomial enumeration), the Newcombe hybrid-score
one-sided 95 % lower bound (Wald reported beside it), the crude-vs-standardised
straddle = ambiguous rule, the near-zero behaviour bar (`|delta action| <= 0.01`
rad from `119`), and the label rule (a pass at `p_hat < 0.94` and/or a near-zero
change prints "PASS inside the ambiguous band / no-op"). The H2 gate is the
dispatch's wording: M1-held (`m1_hold_ok=1` and `m1_hold <= 0.02` vs
`q_settled`), M1-applied from the row's **own `q`** (`|q-back| <= 0.15`,
`|q-ready| >= 0.30`, `drift <= 0.02`; P35's `m1_prime` reads `q_settled`), and
M2a (`max_frac < 0.10`), each >= 95 % **per arm**, plus one `[park]` row per
episode; `arm_px = 0` is the census report only. The report refuses the outcome
read on a failed term or an incomplete design (`exit 2`).

**#5 (post-batch, print-only, data-independent).** The report's `[9]` M1 line
printed the Newcombe bound as `[x, 1]`; it is a one-sided **lower** bound and
the wording was corrected. The md5 moved `e17aef37` -> **`e606bf3f`**;
`B_ab/B_report.txt` was regenerated on the same logs and **no number, decision
or label changed** (the `M1`-`M4` values are identical). The batch-time md5 is
preserved in `B_ab/B_header.txt`; the self-test passes on both versions.

**#6 (the batch, report-not-deviation).** The realized right-arm n is **44 (A) /
49 (B)**, below the ~50 the power table assumes (the arm follows the fruit's
grade and the streams diverge); the PREREG's clause is "report, not re-run", and
the power table's n = 40 row is the applicable one (98.2 % pass for a preserved
candidate). The batch completed all 10 sessions with no wedge; `112`'s trailing
`113` verdict exits 1 (no *improvement* at the ceiling) and is not a run
failure.

**#7 (the Gate-2 conditions, post-batch, no number/label/decision change).** The
review's conditions land as record corrections plus one code hardening; the
enumerated table is `logs/p37/P2_RESULTS.md` §9. (a) **S3's reading**: the fail
is the pre-registered formal gate firing on a **systematic scenario tail** - the
trigger's lateral gate is a pure function of the fruit's x (`dx = x - 0.333`,
gate 0.16 -> admits only `x >= 0.173`) while the delivered supply is
**0.148-0.364 m** (min +0.148, p10 +0.205, p50 +0.279, p90 +0.348, max +0.364;
`logs/v1/12b_supply_after_free.log` line 409), so ~2.5 cm is systematically
unfirable and the batch's 1/92 right is ~a coin flip at n ~ 45 - it carries
essentially no evidence about the checkpoint; "closes negative and published" is
withdrawn. (b) **No gate widening**: the reach-edge ladder reads 8.3 mm at x = 0.16
(6.0 mm at 0.18, 20.4 mm at 0.14; `logs/v3/60_station_reach_edge.log`) - marginal,
not a flail (the flail class starts ~170 mm downstream), so a wider `FRUIT_POLICY_TRIGGER_LATERAL`
would trade a no-fire for a grip-quality failure; the defect is the **delivered
drift tail** or the **harness's no-re-selection on a lateral refusal**, each a
scenario change with its own pre-registration. (c) The **adoption
recommendation** rests on the **no-gain** (B 0.959 vs A 0.977, carried 0 vs 0;
the base at ~0.98 of its ceiling and the shipped `moe_v13s` already delivering
the park's P35 94 %), not on the S3 event. (d) The **erasure-branch wording** is
identified as such (section 7's note above). (e) The **interval's power**: at
equality the Newcombe bound is already at/over the bar (-0.0885 at 47/50 vs
47/50, -0.1045 one margin-step in), so the **point rule is the only gate** and
the realized n is the n = 40 row. (f) The **pooled rate is an arm-mix artifact**
(right -1.8 / left +0.6; standardised ~ -1 point) and the right-arm primary is
the read. (g) The **fidelity direction is a diagnostic, not a measurement**.
(h) `logs/p37/p37_report.py`'s `_P_EXACT_CACHE` key carries `(margin, steps)`
(md5 `e606bf3f` -> **`50dae91d`**; the re-render is byte-identical apart from the
header's own md5 line, `--self-test` PASS). (i) The **S3 arm cut is specified**
(pooled gate, right-arm specifier), the "outer-band" wording is corrected to
"below the band's 0.20 m floor", and the fixed **A-then-B** order is noted with
its confound. Nothing in this list changes a number, a label or the decision.
