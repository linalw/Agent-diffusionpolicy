# P37 — The park-collected recollection + the N=5 A/B (the adoption gate)

Started 2026-10-24 (owner: "继续你想做的", following P36). Full delegated
authority; an Oracle gate per phase.

## 1. The question

The P35's park is a **measured image-borne interface lever** (the right arm
45 % -> 94 %, the carried class 25 -> 0, B > A 5/5 runs; the P36 2x2: the image
channel, the proprio null), but the probes (the spoof cells) **do not ship**.
The shipping path is a **recollection collected under the park** (both channels
fixed) with its **own N = 5 A/B** (the WS-4.2 convention). Does a park-collected
fine-tune preserve the park's win on the deployment configuration?

## 2. The established facts

- The park: `FRUIT_ARM_PARK=back` (the **inactive left arm**, the **direct**
  presentation's reset; the image-borne; `configs/arm_parks.json`, the P35's
  `q_settled`).
- The collector (`40_collect_demos.py`) parks through `tasks.go_ready` (the
  scripted path, **no park** - the P35 Gate-1 L15), so the park-collected store is
  either (a) the **direct-rollout store** (`110_rl_rollout --record` with the
  park; the R9 `datasets/rl_rollouts` precedent) or (b) a tasks-side park + the
  collector. The direct-rollout store is the faithful path (the park is the
  direct env's reset); `--record` + the spoof is refused, the park is not.
- The base: `moe_v13s` `61da390a`; the anchor store `demos_v11`; the W7-C/R9
  fine-tune recipes.
- The A/B: the new checkpoint vs the base, **both with the park on** (the
  deployment config), N = 5 x 15, the seeds, interleaved; the endpoints: the
  P33's paired carried-not-placed + the placed + the park's class counts; the
  falsifiers: the recollection erases the win (an OOD shift) / preserves it (the
  adoption candidate).

## 3. The plan

| # | Phase | Deliverable | Owner | Gate |
|---|-------|-------------|-------|------|
| 1 | The pre-registration + the park-collected store | the PREREG (the scenario, the store/recipe, the N = 5 A/B, the endpoints, the confounds); the direct-rollout collection under the park; the store audit | @general | Oracle 1 |
| 2 | The fine-tune + the N = 5 A/B | the fine-tune (the W7-C/R9 recipe) + the paired A/B (the new vs the base, both parked) | @general | Oracle 2 |
| 3 | The integration + the adoption decision | the docs/commits; the adoption recommendation (the shipped default stays off unless the gate passes) | @general + orchestrator | Oracle 3 |

Oracle budget: 3 gates (1 initial + up to 2 re-reviews each).

## 4. The risks

- The direct-rollout store's composition (the park's ~65 % rate; the
  success-only bias; the R9's AWR weighting option).
- The park fixes the image **and** the 7 proprio channels in the store; the
  recollection is expected to resolve the checkpoint's OOD - a fine-tune that
  collapses the win fails the gate.
- The N = 5 ~2.5 h; the quantized outcomes; the policy loop's variance.
- The shipped default stays off unless the adoption gate passes (the owner's
  decision).

## 5. The log

- 2026-10-24: the file; the plan; Phase 1 dispatched.
- 2026-10-24/25, **Phase 2 done** (Oracle 2 applied). The Gate-1 H1/H2 report
  (`logs/p37/p37_report.py`, batch-time md5 `e17aef37`, self-test PASS) was
  written **before** the batch; the fine-tune
  (`scripts/222_p37_finetune.sh`) produced `checkpoints/p37_park` `3fa45c96`
  (`ones`, 6 ep, lr 5e-5, base `demos_v11` 1.0, loss 0.041195, 7.4 min, 28.3 %
  rollout window share); the N = 5 x 15 A/B (`scripts/223_p37_ab.sh`, both arms
  parked, one claim 00:07:05-01:19:41) reads the manipulation **PASS** 100 % on
  every H2 term (A 44/44, B 49/49), the primary **PASS** (right placed A 43/44 =
  0.977 vs B 47/49 = 0.959, delta -0.018, carried 0 vs 0), S2 **consistent**
  (species -0.017, diameter -0.021), S4 **PASS** (-0.8 %), and **S3 FAIL** on one
  novel no-fire reason (`timeout: no grasp within 1500 ticks`, 1/92 right, a kiwi
  at x=+0.159 refused by the shipped 0.16 lateral gate).
  **The reading (Gate 2, F1-F9 in `logs/p37/P2_RESULTS.md` §9):** the **preservation
  read stands** (the erasure falsifier did not fire -> the preservation branch
  applies; the adoption decision is the owner's), and the S3 fail is the
  **pre-registered formal gate on a scenario tail** - the lateral gate is a pure
  function of the fruit's x (gate 0.16 vs the 0.333 station -> only x >= 0.173 is
  admitted) while the delivered supply is 0.148-0.364 m, so ~2.5 cm is
  systematically unfirable at ~1 %/episode - **it carries essentially no evidence
  about the checkpoint**. The candidate is therefore **not an adoption candidate**
  and, on the **no-gain** (B 0.959 vs A 0.977, carried 0/0; the base at ~0.98 of
  its ceiling and the shipped `moe_v13s` already delivering the park's P35 94 %),
  a park-trained checkpoint **adds nothing and is not needed to ship the park**;
  the shipped default stays off. Fidelity (a **diagnostic, not a measurement**):
  action delta max 1.268 rad (not a no-op), the direction reading away from the
  park store / toward `demos_v11` (the declared confound's signature). No-harm:
  selfcheck PASS, acceptance 6/10 + `fingerprint: matches`, 376/376 `[fruit]`
  lines identical to the P36 record, no `src/`/`configs/` change. Record:
  `logs/p37/P2_RESULTS.md`, WORKLOG "P37 phase 2"; the phase-3 close-out commits
  the docs + `logs/p37/` + `scripts/221/222/223` (the checkpoint and the store are
  gitignored). **The next spend is the supply/transport drift tail + the
  harness's no-re-selection on a lateral refusal** (F2), each with its own
  pre-registration.
