# P37 phase 2 — the park-collected fine-tune and its N = 5 adoption A/B (the record)

Measured 2026-10-25, Tier A solo. Phase 2 of
`.slim/deepwork/p37-park-recollection.md`. **No shipped default changed**
(`FRUIT_ARM_PARK` stays default off), **no `src/` or `configs/` change**. The
pre-registration is `logs/p37/PREREG.md`; the phase-1 record is
`P1_RESULTS.md`. The tree pins at batch time are in `logs/p37/B_ab/B_header.txt`
(`tasks.py` `cdde6bd2`, `rl_env.py` `aa54b022`, `trigger.py` `d7ec85fc`,
`runtime.py` `379ac706`, `meshes.py` `41efc522`, `fruits.py` `6f65e423`,
`arm_parks.json` `42ab4fb7`, `motion_reference.json` `25ade92b`, HEAD
`8d6bca5`) and are unchanged after (`P2_tree_md5_after.txt`). The **Gate-2
conditions** are applied in §9 (record-side rewording, one report-code key fix;
no number, label or decision changed).

**The one-line answer.** The recollection **preserves the park's win on the
pre-registered primary** (right-arm placed **A 43/44 = 0.977 vs B 47/49 =
0.959**, delta **-0.018** against the -0.10 margin), nothing is erased (carried
**0 vs 0**), and it is **not a no-op** (the fidelity action delta is 1.27 rad).
The **pre-registered adoption gate fails on S3**: the candidate produced **one**
failure reason the base never did — a single `timeout: no grasp within 1500
ticks` (1 of 92 right-arm episodes, run 1 ep 6, a kiwi at x = +0.159 - **below
the patch band's 0.20 m floor**, in the delivered drift tail - that the shipped
trigger's 0.16 lateral gate never admitted). **That event is a systematic
scenario tail, not a candidate result** (~1 %/episode; §4.5): it fails the
formal gate as written, and it carries **essentially no evidence about the
checkpoint**. So: **the preservation read stands** (the pre-registered *erasure*
falsifier did not fire), the candidate is **not an adoption candidate** under
the rule, and the **adoption recommendation rests on the no-gain** — the base
sits at ~0.98 of its ceiling and the shipped `moe_v13s` already delivers the
park's P35 94 %, so a park-trained checkpoint adds nothing and is **not needed
to ship the park** (§4.7). The shipped default stays off; the park remains the
documented default-off interface lever of P35/P36; the adoption decision is the
owner's.

## 1. The Gate-1 H1/H2 implementation (before the batch)

`logs/p37/p37_report.py`, md5 **`e17aef37`** at batch time (recorded in
`B_ab/B_header.txt`), **`e606bf3f`** after the one post-batch print-only fix of
§8, **`50dae91d`** after the §9 Gate-2 code change (a cache key + a docstring;
the §9 re-render is byte-identical apart from the header's md5 line). It imports
`scripts/113_rl_report.py`'s episode parser (`c27c49b8`) and
`logs/p35/park_ab_report.py`'s `[park]` regex / reference vectors / class
definition (`a796db0b`), and prints all three md5s in its header so a report is
identifiable. `--self-test` PASS: parser, the H2 terms, the primary, the
standardisation straddle, S3, S4, the label and the fidelity parser, on
synthetic logs (including the refusals).

**H2 — the manipulation gate** (`[1]`): on **right-active** episodes with
>= 1 band call, per arm, >= 95 % on each of

* **M1-held** — `m1_hold_ok=1` and `m1_hold <= 0.02` rad vs the `q_settled` the
  reset achieved;
* **M1-applied** — the row's **own `q`**: `max|q-back| <= 0.15` **and**
  `max|q-ready| >= 0.30` **and** `drift <= 0.02` (references
  `configs/arm_parks.json` / `configs/waypoints.json`); this is P35's
  `m1_prime` term except that it reads `q`, not `q_settled` (the dispatch's H2
  wording), and it **rejects a `ready` arm** — the P35 A arm reads 0/51 on it,
  the check that the gate is not vacuous;
* **M2a** — the band's worst call `max_frac < 0.10` (the `max_frac` field,
  `arm_px / target_px`);
* plus **one `[park]` row per episode** (the P36 M2 count-invariance rule).

`arm_px = 0` is **not** a gate term: the per-call band census is printed as a
report only. A failed term refuses the outcome read (`exit 2`).

**H1 — the endpoints** (`[2]`-`[9]`): the primary (pooled right-arm placed,
`B >= A - 0.10`) with the **exact unconditional non-inferiority p** (sup over
the nuisance rate at `p_B = p_A - margin`, full binomial enumeration, integer
exact comparisons) and the **Newcombe hybrid-score one-sided 95 % lower bound**
(Wald beside it); S1 the left noise floor; S2 species- and diameter-tertile
standardisation with the **crude-vs-standardised straddle = ambiguous** rule;
S3 the new-reason set diff with the count and arm of every novelty; S4 the cycle
bar; S5 the manipulation gate; the realized n; the `119` fidelity readout; and
the **label**: a pass at `p_hat < 0.94` and/or a near-zero behaviour change
(`|delta action| <= 0.01` rad) prints **"PASS inside the ambiguous band /
no-op"**, never "preserved". `M1`-`M4` are printed as the mandated summary.

## 2. The fine-tune

`scripts/222_p37_finetune.sh` (the PREREG section-4 contract verbatim), offline,
no simulator, 23:57:24 -> 00:04:45 (**7.4 min**), exit 0:
`moe_v13s` `61da390a` -> **`checkpoints/p37_park/policy_best.pt` md5
`3fa45c96`**; `--rollouts datasets/rl_rollouts/p37_park` (90 episodes, 3,698
windows) + `--base datasets/demos_v11` (9,378 windows) at 1.0, `weight_mode=ones`,
6 epochs, lr 5e-5, batch 32, seed 0. **Rollout window share 28.3 %** — the
declared confound, now with its number (the recollection precedent
`demos_v13p` was 77 %).

| epoch | mse / weighted | router ce / acc | demo_val |
| --- | --- | --- | --- |
| 0 | 0.049623 | 0.1521 / 0.9636 | 0.024729 |
| 1 | 0.043641 | 0.0423 / 0.9847 | 0.019598 |
| 2 | 0.041060 | 0.0327 / 0.9885 | 0.016456 |
| 3 | 0.040717 | 0.0260 / 0.9904 | 0.013641 |
| 4 | 0.039122 | 0.0225 / 0.9916 | 0.019514 |
| 5 | 0.041195 | 0.0205 / 0.9921 | 0.013663 |

`finetune_history.json` is copied to `logs/p37/P_finetune_history.json`; the
candidate md5 is `logs/p37/P_ckpt_md5.txt`, written **before** the batch
(one-way).

**The fidelity readout** (`scripts/119_rl_fidelity.py`, 192 windows, DDIM-16,
fixed per-window noise; `logs/p37/fidelity.txt`) is a **diagnostic, not a
measurement** and not a gate - it reads the candidate's *action* distance from
the base on a fixed window set, which is a property of the two checkpoints, not
of the deployment loop:

| store | paired delta (cand - base) | improved / worse / ties | action delta max |
| --- | --- | --- | --- |
| `datasets/rl_rollouts/p37_park` | **+0.0281 rad** | 71 / 121 / 0 (p = 0.9999) | **1.268 rad** |
| `datasets/demos_v11` | **-0.0104 rad** | 120 / 72 / 0 (p = 0.0003) | 0.415 rad |

So the fine-tune **moved the policy materially** (the no-op bar is 0.01 rad).
The **direction** of that movement - away from the park store's recorded actions
and toward the `ready` base anchor - is the **diagnostic reading** of the
declared confound, *not* a measurement of what the policy does on the
deployment interface (§5); the interface read is the A/B. The movement did not
cost the right-arm placed rate (§3).

## 3. The A/B batch

`scripts/223_p37_ab.sh`: **N = 5 runs x 15 episodes per arm**, seeds
**77/101/202/303/404**, sampler seed 11, A-then-B inside each run, **both arms
parked** (`FRUIT_ARM_PARK=back`), the PREREG section-2 block verbatim (patch
sheet, `arrival`/0.9/ACQ, `FRUIT_DYNAMIC_PICK=1`), the same three diagnostics on
both arms, one `scripts/154_claim_run.sh` claim, 00:07:05 -> 01:19:41
(**72.6 min**, 7.3 min/session; `B_ab/B_driver.log`). The claim's `exit=1` is
`112`'s trailing `113` verdict (no *improvement* at the ceiling), not a run
failure: all 10 sessions completed 15 episodes. **The order is fixed A then B**
(PREREG §8.5): any order term is confounded with the checkpoint, which is why
the batch's own arm A is the baseline and one run is one sample.

**Realized n**: A 75 episodes (**right 44**, left 31), B 75 (**right 49**, left
26) — right share 58.7 % / 65.3 % (P35 read 68 %; the arm follows the fruit's
grade, so the denominators drift with the branch).

## 4. The result

### 4.1 The manipulation check (S5) — PASS

| term | arm A | arm B |
| --- | --- | --- |
| M1-held (<= 0.02 rad vs `q_settled`) | **44/44** | **49/49** |
| M1-applied (`|q-back|<=0.15`, `|q-ready|>=0.30`, drift<=0.02) | **44/44** | **49/49** |
| M2a (max band `arm_frac < 0.10`) | **44/44** | **49/49** |
| the conjunction | **44/44** | **49/49** |
| `[park]` rows | 75/75 | 75/75 |

`|q-back|` median 0.093 (max 0.093), `|q-ready|` median 0.602 (min 0.602),
drift max 0.010 rad, band calls per episode median 25 (A 16-25, B 15-25).
**Census (report only)**: A 1,078 right-active band calls, fully hidden 0/1,078,
any inactive-arm pixel 0/1,078; B 1,196 calls, hidden 0/1,196, arm pixels
**8/1,196 = 0.7 %** (the single ep-6 band-edge call, 14 px, `max_frac` 0.080).
The P35 report's reported-only `M2b` reads 34/44 and 36/49 (the running
normalisation's raster-drift readout) — not the gate.

### 4.2 The primary (M1) — PASS

**A 43/44 = 0.977, B 47/49 = 0.959, delta -0.018** (margin -0.10).

* **exact unconditional non-inferiority p = 0.2195** (discrete and conservative
  at this n — the sup over the nuisance rate);
* **one-sided 95 % lower bound**: Newcombe **-0.095** (inside the margin),
  Wald -0.077, z = 2.27, p = 0.0116;
* realized n 44 / 49 (the design assumed ~50; the power table at n = 40 gives
  98.2 % pass for a preserved candidate).

The point rule and the interval both pass; the exact p does not (it is the
conservative discrete form). Per the PREREG the **gate is the point rule** — and
§5 shows why the interval cannot carry a decision here (it has ~no power at
MARGIN = 0.10).

**Right-arm class table**: A ok 43 / carried 0 / no-grasp 1; B ok 47 / carried 0
/ no-grasp 2 (composite 1 vs 2). The two non-timeout right-arm failures are the
same class in both arms — the **3.4 cm strawberry** (A run 4 ep 14; B run 4
ep 7). The P33 exact-instance pairing is **degenerate as pre-registered**:
25 usable right pairs, 25 both-ok, 0 discordant (50 excluded on fruit class) —
the park's own arm reads 0/50 carried, so the carried-class endpoint has no
events under the park.

**Per run (right ok)**: A 10/10, 9/9, 6/6, 5/6, 13/13; B 9/10, 9/9, 6/6, 11/12,
12/12 — B >= A in **4/5** runs, strictly worse in one (run 1, the no-fire).
Reported, not gated.

### 4.3 S1 the left noise floor (reported)

A left 1/31 ok (29 carried, 1 no-grasp), B 1/26 ok (24 carried, 1 no-grasp);
delta **+0.006**; exact-instance left pairs 13 usable, 0 B-only / 0 A-only. A
one-sided floor at the ceiling (1-3 ok per arm), as P36 section 4 formulated it.

### 4.4 S2 the standardised right rate — consistent

| cut | A | B | delta | coverage |
| --- | --- | --- | --- | --- |
| crude | 0.977 | 0.959 | **-0.018** | - |
| species (direct to A's mix) | 0.977 | 0.961 | **-0.017** | 1.00 |
| diameter tertiles (cuts 4.00 / 6.20 cm) | 0.977 | 0.956 | **-0.021** | 1.00 |

All three inside the margin → **not ambiguous** (the crude/standardised straddle
rule does not fire). Per-species and per-tertile tables are in
`B_ab/B_report.txt` `[5]`.

### 4.5 S3 new failure reasons — **FAIL** (the formal gate; a scenario tail, not a candidate behaviour)

`'timeout: no grasp within # ticks'` — **count 1, right arm 1** (run 1 ep 6,
kiwi 6.3 cm, 1,500 ticks, `decision=1500`, **no `[acq]` row**: the trigger never
fired). The **gate** is the **pooled** reason set over both arms (PREREG §6);
the **right-arm cut** — the primary's population — is reported beside it and
flags the same single event, so the arm cut is not in question.

**Why this is a systematic scenario tail, not a candidate result.** The
trigger's lateral gate is a **pure function of the fruit's x**
(`|dx| = |x - jaw.x| <= 0.16` against the station's 0.333 m jaw line), so it
**admits only x >= 0.173 m**. The delivered supply's lateral x is
**0.148-0.364 m** (min **+0.148**, p10 **+0.205**, p50 **+0.279**, p90
**+0.348**, max **+0.364**; `logs/v1/12b_supply_after_free.log` line 409), i.e.
a **~2.5 cm tail sits systematically below the admission boundary** and can
never fire. The failing fruit's x = **+0.159** is in that tail — it is **below
the patch band's 0.20 m floor**, not an "outer-band" fruit (the band is
x = 0.20-0.36). At the class's measured incidence (~1 %/episode) a 45-episode
arm meets it in about 40 % of batches, so **which arm it lands in is close to a
coin flip**: the batch's 1/92 right is **one such draw**, and a rerun with the
same two checkpoints could put it in arm A (S3 PASS) or in neither. The
pre-registered rule is mechanical and has no severity threshold, so **S3 FAILS
as written** — but the failure is a property of the **delivered drift tail**, it
is the same class W7-C recorded once ("not the policy-gate class"), and it
**carries essentially no evidence about the checkpoint**.

**What is *not* the fix.** Do **not** widen the trigger gate: the reach-edge
ladder reads **8.3 mm** of grip residual at x = 0.16 (6.0 mm at 0.18, 20.4 mm at
0.14, 34.6 mm at 0.12; `logs/v3/60_station_reach_edge.log`, WORKLOG "V3
integration" section 6) — marginal, but **not a flail** (the flail class starts
~170 mm downstream) — so widening it to admit x = 0.159 trades a **no-fire for a
grip-quality failure**, and `FRUIT_POLICY_TRIGGER_LATERAL` is a shipped default
measured on the W4 branch. The defect is either **(a) the delivered drift tail**
(the ~2.5 cm below 0.173 m: a supply/transport change) or **(b) the harness's
no-re-selection on a lateral refusal** (the fruit is refused, rides on, and the
attempt burns its 1,500-tick horizon instead of re-selecting: an env change).
Both are **scenario changes and each needs its own pre-registration** and
reference re-record.

### 4.6 S4 cycle — PASS

Pooled median **A 1,840 -> B 1,826 ticks (-0.8 %)**; right arm 1,784 -> 1,783
(-0.0 %). Model calls per attempt median A 61 / B 59.

### 4.7 M1-M4 and the decision

```
M1  delta -0.018 | lower bound (Newcombe) -0.095 | exact p 0.2195 | n A 44 / B 49 | PASS
M2  crude -0.018, species -0.017, diameter -0.021 -> consistent (not ambiguous)
M3  new reasons in B: 1 (right 1) -> S3 FAIL
M4  S4 cycle PASS | S5 manipulation PASS
LABEL: PASS (preservation candidate)   [p_hat 0.959 >= 0.94, behaviour change 1.27 rad]
adoption candidate: NO (primary pass, S3 fail, S4 pass, manipulation pass)
```

**The verdict.** **The preservation read stands.** Nothing is erased (carried
**0 vs 0**; the only shared non-timeout failure class is the 3.4 cm
strawberry), the primary passes the pre-registered point rule, and the
candidate is not a no-op. **The pre-registered erasure falsifier did not fire**
(PREREG §7), so the **preservation branch applies**: the recollection is
**consistent with a park-compatible checkpoint**, and the adoption decision is
the owner's. The candidate is **not an adoption candidate**, because the
decision rule also requires S3 and S3 fails — but **the S3 fail is the
pre-registered formal gate firing on a scenario tail (~1 %/episode, §4.5), not
on candidate behaviour, and it carries essentially no evidence about the
checkpoint.**

**The adoption recommendation rests on the no-gain, and it is "no".** B **0.959**
vs A **0.977** (delta **-0.018**), carried **0 vs 0**: the base sits at ~0.98 of
its ceiling and the shipped `moe_v13s` **already delivers the park's P35 win
(94 %)** with the park on. A park-trained checkpoint adds **nothing measurable**
on top and is **not needed to ship the park** — so there is nothing to adopt
here, independently of S3.

**On the wording.** "The recollection closes negative and published" and "the
park stays a documented default-off interface lever and the shipping path stays
closed" are the **erasure branch's** wording (PREREG §7, first bullet), and that
branch did not fire. The shipped state is unchanged — `FRUIT_ARM_PARK` defaults
**off**, and the park is documented as a default-off interface lever (P35) —
but that is the **shipped default**, not this phase's verdict; the verdict is a
**preservation read plus a no-gain recommendation**, and the adoption question
is the owner's phase-3 decision on these numbers.

## 5. What this does and does not show

* **It is a preservation result, not a gain** — and the adoption recommendation
  is the no-gain. The base is at ~0.98 of its ceiling; the candidate is 1.8
  points below it, inside the margin. There is no evidence that training under
  the park *improves* anything over `moe_v13s`, and the shipped checkpoint
  **already delivers the park's P35 94 %**, so a park-trained checkpoint is not
  needed to ship the park.
* **The S3 failure is a scenario tail, not a candidate result** (§4.5): the
  trigger's lateral gate is a pure function of the fruit's x (`dx = x - 0.333`,
  gate 0.16 -> it admits only x >= 0.173), the delivered supply is
  x = 0.148-0.364, so ~2.5 cm of the stream is systematically unfirable; the
  event (x = +0.159, below the band's 0.20 m floor) occurs at ~1 %/episode, and
  at n ~ 45 per arm **which arm sees it is close to a coin flip**. It fails the
  formal rule and it says essentially nothing about the checkpoint. The fix is
  **not** a wider gate (the reach-edge ladder reads 6.0 mm at x = 0.18 and
  8.3 mm at x = 0.16 - marginal, not a flail, and widening trades a no-fire for a
  grip-quality failure): it is the **delivered drift tail** or the **harness's
  no-re-selection on a lateral refusal**, each a scenario change with its own
  pre-registration.
* **The interval has ~no power at this margin.** -0.095 sits 0.005 inside -0.10,
  and at exact equality at the design n (47/50 vs 47/50) the same bound is
  **-0.0885**; at equality one margin-step in (p ~ 0.89) it reads **-0.1045**,
  i.e. *outside* the bar. A preserved candidate's interval therefore straddles
  the margin by construction: **the pre-registered point rule is the only gate
  that passes**, and the exact p (0.2195) and the interval are supporting only.
  The realized n (44/49) is the power table's **n = 40** row (98.2 % pass for a
  preserved candidate), not the n = 50 design row.
* **The pooled rate is an arm-mix artifact, not a result.** A **58.7 %** /
  B **64.0 %** pools two different populations, and the right share moves with
  the branch (**58.7 % vs 65.3 %**): the right arm's delta is **-1.8 points**
  and the left's **+0.6**, and standardised to a common arm mix the pooled delta
  is **~ -1 point (-0.8 at A's own mix, -1.1 at 70/30)** — a small loss, not the
  +5.3-point "gain" the raw pool prints. **The right-arm primary is the read**;
  the pooled number must not be quoted as a rate.
* **The fidelity direction is a diagnostic, not a measurement** (§2): it reads
  the two checkpoints' action distance on a fixed window set, and its "away from
  the park store, toward `demos_v11`" reading is the declared confound's
  signature at a 28.3 % rollout share - not a measurement of the deployment
  loop. A `base_weight`-matched variant (the precedent's 77 % share) would be a
  **new pre-registration**.
* **The image and the 7 proprio channels are fixed together** in the store
  (P36 separated them at N = 3); this phase inherits that read.
* **One sample of a non-bit-reproducible loop**, **A-then-B order** (an order
  term is confounded with the checkpoint), grade-assigned arms (A right 44 vs
  B 49), one collection. The batch's own arm A is the baseline; no cross-batch
  rate comparison is made.
* **The store has no supply block** (phase-1 limitation): the patch sheet is
  pinned by the recorded command + `logs/p37/collect_*.log`, not by the
  manifest.

## 6. No-harm

* `scripts/selfcheck.sh`: **PASS, 0 failures, 1 skipped** (`P2_selfcheck.log`).
* The scripted acceptance with both knobs **unset** (`P2_accept.out` /
  `P2_accept_raw.log`): **6/10 + `fingerprint: matches
  configs/motion_reference.json`** (the pre-existing P32 pear-on branch; the
  rate-only `exit=1` is expected), motion gate all descents inside budget (worst
  `|v|max` 0.110/0.161, lurch 0.017/0.291, worst cone 1.27x reported), and its
  **376 `[fruit]` lines are IDENTICAL** to the P36 record
  (`P2_accept_identity.txt`; `P2_accept_stream.log` vs
  `logs/p36/A2_accept_raw.log`).
* The tree pins are unchanged before/after (`P_tree_md5_before.txt` ==
  `P2_tree_md5_after.txt` for every `src/`/`configs/` file); the phase writes
  only `checkpoints/p37_park`, `datasets/rl_rollouts/p37_park`, `logs/p37/` and
  the three scripts. The checkpoint and the rollout store are **gitignored**
  (their provenance is `logs/p37/`); the commit carries the docs, `logs/p37/`
  (force-added) and `scripts/221/222/223`. **No shipped default changed.**

## 7. Files

`logs/p37/`: `p37_report.py` (H1/H2; md5 `e17aef37` batch-time, `e606bf3f`
after §8, `50dae91d` after the §9 Gate-2 code change), `P2_RESULTS.md` (this), `B_ab/` (`A_1..A_5.log`, `B_1..B_5.log`,
`B_header.txt`, `B_driver.log`, `B_report.txt`, `B_113.txt`, `B_park_ab.txt`,
`B_mech.txt`, `B_tree_md5_after.txt`, `raw/`), `B_outer.log`,
`P_finetune.log`, `P_finetune_history.json`, `P_ckpt_md5.txt`,
`P_tree_md5_before.txt`, `P_tree_md5_after.txt`, `fidelity.txt` (+
`P_fidelity.log`, `fidelity_smoke.txt`), `P2_selfcheck.log`,
`P2_accept.out` / `P2_accept_raw.log` / `P2_accept_stream.log` /
`P2_accept_identity.txt` / `P2_accept_claim.log` / `P2_accept_outer.log`,
`P2_tree_md5_after.txt`. Checkpoint: `checkpoints/p37_park/policy_best.pt`
(`3fa45c96`, gitignored). Drivers: `scripts/221_p37_collect.sh`,
`scripts/222_p37_finetune.sh`, `scripts/223_p37_ab.sh`.

## 8. Post-batch notes (print-only, data-independent)

1. The report's `[9]` M1 line printed the Newcombe bound as an interval
   `[x, 1]`; it is a **one-sided lower bound**, and the line now says so. The
   md5 moved `e17aef37` -> **`e606bf3f`**; `B_ab/B_report.txt` was regenerated
   on the same logs, and **no number, no decision and no label changed** (the
   `M1`-`M4` values are identical; the batch-time md5 is preserved in
   `B_ab/B_header.txt`).
2. No other post-batch edit was made to the analysis; the fidelity file, the
   logs and the checkpoint are as written during the phase.
3. **The Gate-2 code change** (§9, F8): `_P_EXACT_CACHE`'s key now carries
   `(margin, steps)` as well as `(k_b, n_b, k_a, n_a)`, so a future run at a
   different margin or grid cannot read a stale p; the S3 docstring also states
   the arm cut. The md5 moved `e606bf3f` -> **`50dae91d`**; the re-render of
   this batch is **byte-identical apart from the header's own md5 line**
   (`--self-test` PASS, `M1`-`M4`, label and decision identical), so the
   evidence file is left as the batch renders it.

## 9. The Gate-2 conditions (2026-10-25) and where each landed

Applied after the Gate-2 review; **no number, no label and no decision
changed** - the record's *reading* is corrected, and F8 is a code hardening.

| # | condition | landing |
| --- | --- | --- |
| F1 | the S3 fail is a **systematic scenario tail**, not a candidate result; the trigger gate is a pure function of the fruit's x (`dx = x - 0.333`, gate 0.16 -> admits only `x >= 0.173`), the delivered x is 0.148-0.364 (`logs/v1/12b_supply_after_free.log` line 409), so ~2.5 cm is systematically unfirable and 1/92 right is ~a coin flip at n ~ 45 | §4.5 (rewritten), §5, §4.7, the intro; the "closes negative and published" wording is withdrawn here and in the WORKLOG heading. The **preservation read stands; the S3 fail is the pre-registered formal gate on a scenario tail (~1 %/episode, not a candidate behaviour) and carries essentially no evidence about the checkpoint** |
| F2 | do **not** widen the trigger gate (the reach-edge ladder reads **8.3 mm** at x = 0.16, 6.0 mm at 0.18 - marginal, not a flail; widening trades a no-fire for a grip-quality failure); the defect is the **delivered drift tail** or the **harness's no-re-selection on a lateral refusal** (the 1500-tick timeout class), each a scenario change with its own pre-registration | §4.5 "What is *not* the fix", §5 |
| F3 | the adoption recommendation rests on the **no-gain**: B 0.959 vs A 0.977 (-0.018), carried 0 vs 0, the base at ~0.98 of its ceiling and the shipped `moe_v13s` already delivering the park's P35 94 % - a park-trained checkpoint adds nothing and is not needed to ship the park | §4.7 "The adoption recommendation", §5 |
| F4 | the mis-cited branch: "the park stays a documented default-off interface lever and the shipping path stays closed" is the **erasure** branch's wording; the falsifier did not fire, so the **preservation** branch applies (consistent with a park-compatible checkpoint; the adoption decision is the owner's) | §4.7 "On the wording"; PREREG §7 note |
| F5 | the Newcombe -0.095 is 0.005 inside -0.10 and at equality it is already at/over the bar (**-0.0885** at 47/50 vs 47/50; **-0.1045** at equality one margin-step in) -> the interval has ~no power; the **point rule** is the only gate that passes; realized n 44/49 is the **n = 40** row (98.2 %) | §5 "The interval has ~no power" |
| F6 | the pooled rate (A 58.7 %, B 64.0 %) is **arm-mix-confounded** (right -1.8, left +0.6; standardised ~ -1 point) - an artifact; **the right-arm primary is the read** | §5 "The pooled rate is an arm-mix artifact" |
| F7 | the fidelity **direction** is a diagnostic, not a measurement | §2 (rewritten), §5 |
| F8 | the `_P_EXACT_CACHE` key gains margin/steps | `logs/p37/p37_report.py` `e606bf3f` -> **`50dae91d`**, §8.3 (output identical apart from the md5 header) |
| F9 | the S3 arm cut specified (the gate is pooled; the **right arm** is the primary's population and is reported beside it); the "outer-band" wording (x = 0.159 is **below** the band's 0.20 m floor); the A-then-B order noted | §4.5 (arm cut + band floor), §3 (order), the report's S3 docstring, PREREG §6/§8.5 |
