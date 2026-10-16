# MECHANISMS: the paper-derived mechanism menu vs the measured bottlenecks (P6, 2026-10-16)

This is the committed distillation of the P6 adversarial re-read: 84 papers read in full
twice (P5, then P6 on a column-aware corpus), five adversarial re-read lanes
(`logs/p6/B{1,2,3a,3b,4}_reread.md`), and one cross-batch synthesis
(`logs/p6/SYNTHESIS.md`). **Rank = expected movement against the measured bottleneck map per
unit cost x risk.** Every item is default-off, scoped, and enters through its pre-registered
gate first (direct claims: N=5 paired; scripted/two-line: per-scenario gate + fingerprint;
byte-level no-harm everywhere). Paper numbers are `docs/papers/INDEX.md` indices.

## 1. The bottleneck map this menu is ranked against (post-H1)

**Still binding:** (a) **per-attempt arm span ~15.4 s** - only its ~2.4 s descent arrival wait
is supply-coupled; the place block is geometry-closed (P3); (b) **inter-attempt gap ~5.3 s**
(25 % of wall; ~4.3-4.7 s is the dual-arm `go_ready` smooth transit) - **no paper mechanism in
any of the five batches moves this term**; (c) **carry class: mid-lift one-sided loaded slide,
0-2 tick window** - the post-H1 residual failure; squeeze side drive-saturated, shape side and
in-window reaction measured closed; (d) **policy handover / gate path** (the W7-C fire-path
residual); (e) **two-line interval + mix confound** (class-standardize every read).

**Closed:** burst-drain starvation (**H1 positive**: trickle actuator 70 % -> 0 % empty, placed
1 -> 11, shape move not rate move), pool depth (H2 killed), density (P1c refuted
composition-free), place-leg shortening (P3 geometry), in-window reaction (W5/R11-B), plus the
standing closes (reach-anywhere adoption, pre-onset load knobs, hot-arm residency, adaptive
lead, both BC recollections, R9's AWR-RWR, fast tactile reflex, faster samplers/async seam).

## 2. The ranked mechanism menu

| # | mechanism (sources) | what to port | landing zone | endpoint + gate | cost |
| --- | --- | --- | --- | --- | --- |
| 1 | **Attempt-granularity carry monitor + fast-skip / one bounded re-seat** (#66 Sentinel, #1 JCAC, #47 EmbodiedSkills) | a tiny classifier over *online* grip signals (finger separation, two tactile forces, jaw velocity - not privileged payload pose) answering "still seated?"; on no, end the attempt at the next leg boundary | `tasks.py` dynamic-capture/hybrid loop, default-off `FRUIT_CARRY_MONITOR`; labels from `FRUIT_CARRY_DIAG=1` + the W8-B corpus | replay gate first (Sentinel critical-state F1, Normal excluded, near-zero FP on clean carries); then N=5 paired carried-class + interval non-inferior + cycle <=+5 % | S-M |
| 2 | **FPTE plan-to-all-K, evaluate-at-terminal selection** (#9) | compute the clipped interception for K<=3-5 candidates, score each *at its terminal* (reach margin, velocity-matched close margin, R10-A.1 descent residue), execute the best; cache per slot | `tasks.py` selector (`_dynamic_select_floor` / `_reach_anywhere_select`), default-off; reach bands from `scripts/183` | eligible/feasible/chosen + lock-on; no-fire/chase-slot conversion; per-scenario gate + fingerprint; the missing third leg of R11-A.1 | S |
| 3 | **Force lane, Port A: contact-gated force-mode re-entry** (#37 FARM) | enter force mode only on confident both-side contact; hysteresis exit; mode-transition counter | `tasks.py` dynamic-capture scope, default-off `FRUIT_FORCE_REENTRY` | the R11-A.1 chase subtype (F_min=0 trips, closed-at-range) + carried-not-placed; scripted gate + fingerprint | S |
| 4 | **Two-line primary-then-conditional selection + live-variable refit** (#74 BiDexGrasp, #75 SPaSM) | choose the primary arm's fruit by the shipped rule; choose the second conditioned on the first via a pairwise compatibility fitted from logged pair outcomes (sequential beats joint in the source: 61.9 vs 45.5); keep the second target live under motion feasibility | offline replay over two-line logs first; in-loop behind the park-gate default | pooled interval + starved/infeasible slots vs park-gate-on at N>=3 batteries, class-standardized; `190` gate + scenario reference | S-M |
| 5 | **GDP-style OoD-scored population selection** (#32) | K in {2,3} DDIM-16 samples from different noise (~12 ms each, fits the tick), take the min OoD score (or min inside a plausibility band); log per-candidate finger spread | `policy/runtime.py`, default-off, no retraining | no-fire + close-start \|dx\| (seeds 77/101/202); then N=5 paired carried-class | S |
| 6 | **Event-structure handover heads (phase + time-to-transition) + transition-weighted loss** (#50 ForeTime, #42 DAM-VLA) | two auxiliary heads on an 8-step causal proprio history predicting phase (labels free from gripper transitions) + normalized TtT; near-zero-init gates or trigger input; weight the loss by distance to transitions | `policy/model.py`/`train.py` + `policy/trigger.py`; `moe_v13s` base | fire-path classification error + handover-time distribution + fallback chases; N=5 paired; kill on re-seat rise (R11-A 0->10) | S-M |
| 7 | **D²PPO dispersive loss on the denoiser's middle layers** (#21) | `L_diff + lambda*L_disp` (InfoNCE-L2 over denoiser MLP mid-layer activations; lambda ~0.5, swept 0.3/0.5/1.0); stage 1 alone first | `policy/train.py`/`finetune.py`, one retrain from `moe_v13s` | pairwise feature similarity on our rollout states + N=5 paired carried-class/acquisition | M |
| 8 | **Post-training retry discipline: boundary-success selection + orthogonality-constrained adapter** (#66 SECL) | if the R9 lane is retried: select boundary successes (the 20/80 band), LoRA adapter with orthogonality penalty (beta 0.5) + EMA merge (0.9) so the update cannot degrade the handover channel it degraded in R9 | `policy/finetune.py` / `scripts/111_rl_finetune.py` | handover-fidelity readout non-worse than base + N=5 paired carried-class | S |
| 9 | **Contact-stability curation + metadata-conditioned stores** (#17 RDP, #5/#39 pi0.7) | score every store episode by contact stability (freeze-zone face speed, `clean_slip`, force variance), then drop/re-weight or annotate with metadata + per-field dropout | collector/merge index + fine-tune lane; precondition: a store that mixes outcomes | its own N=5 paired carried-class pre-registration - never sold as "another recollection" | M |
| 10 | **Reactive per-tick trace-controller re-aim for the scripted catch** (#64) | regenerate the straight line to the live predicted intercept each tick; distance-scaled advance; sigmoid micro-interpolation | `tasks.py` `_dynamic_aim`/`_approach`, default-off `FRUIT_DYNAMIC_TRACE_AIM`; every change re-records fingerprints | chase/fallback count on the R11-A battery; kill on any descent over budget or a re-seat rise | S-M |
| 11 | **Perception companions: SPGrasp promptable tracking + GeoPredict track-head supervision** (#82, #63) | prompt the selected fruit once and track identity (59-73 ms/frame; SAM2-Small 48.6 ms fallback); training-side: an auxiliary H-step keypoint-trajectory head dropped at inference | a perception module + `policy/model.py`/`train.py`; ObstaDiff's TOB encoder is the heavier C-6 variant | acquisition/no-fire + starvation slots on the dense sheet, class-standardized, N=5; **mandatory prerequisite: the visual-ablation harness first** (vision is sub-noise; the target-mask channel is empty) | S-M |

**Recorded, not ranked** (one-line reasons in the lane files): DemoDiffusion's noised-scripted
prior (needs its own falsifier), FDP's factorized close/transport split (re-architecture),
SMP sticky routing (readout first), VLA-Pilot bounded proposal search (no usable scorer at
20 Hz), DexSinGrasp neighbour-clearance selector (replay cost readout first), Grasp-to-Act
wrench pre-screen (shape side closed), IMLE's cIMLE head (only if mode-averaging is ever
measured).

### 2b. Conflicts, resolved

* **Force conditioning (B2 vs B3b).** B3b records three independent negatives against naive
  force/touch conditioning (ForceVLA's pi0-fast backfire 31.0 -> 14.2; VLA-Touch RDT+tactile
  ~+4 %; VisualThink dense-beats-routed 85.8 vs 83.5 on the contact task) and ForceVLA's own
  compact-policy guardrail. Resolution: one program, ordered **Port A (scripted mode
  discipline, S) -> the compact-size / naive-force pre-check -> Port B (policy-side late,
  phase-routed, top-1 additive fusion, M)**. No naive concatenation; no in-window claims; the
  sim tactile exposes normal force + contact count only.
* **RL family.** SimpleVLA-RL is a GO with an architecture caveat (diffusion heads are
  excluded from PPO as-is - TT-VLA's appendix); GenPO demoted by FlowRL's independent
  benchmark; R9 measured the weighting lane null. The diffusion-compatible routes are a
  D²PPO-style gradient or a scoped discrete decision; the branch-invariant carry window caps
  conversion at the acquisition/handover/interval classes.
* **C-1 implementations.** Analytic terminal scoring (FPTE) first; the NavDP learned critic
  second; the DQ-Net memory bank is an in-loop enabler, not a lever.
* **C-3 implementations.** Sentinel's event classifier first (online signals only,
  post-window scheduling); JCAC's conformal action-space risk as the complementary signal;
  EmbodiedSkills' preflight/verify/recover contract as the loop skeleton. The closed W5
  watcher is not re-opened - these decide *between* attempts, not inside the window.
* **SkipVLA (C-5) demoted**: transit-like segments are ~14 % of our span; R10-A's re-aim
  lengthened the interval; the re-anchoring half is already in-tree (R2's reseed).
* **Perception vs sub-noise vision**: every perception build gates on the visual-ablation
  harness first; GeoPredict's state-history track head is the cheaper half.

### 2c. Diagnostics / protocol exports worth adopting regardless

Sentinel's critical-state F1 protocol (the standard replay-gate metric) · MAP-VLA RDP+DTW
stage labelling (validate against `[cycle]`/gripper boundaries) · SkipVLA gripper-event
labels · AHEAD's ablation ladder around `_reach_predict` (its own control: a
constant-acceleration prior recovers most of the clean-motion gap, learned dynamics is worse)
· the FRB friction-cone feasibility audit over existing carry logs (quantifies the withdrawn
grip-margin hypothesis offline) · Cocos condition-utilization diagnostic · Realtime-VLA V2
failure-timestamp clustering · DynamicVLA LAAS rules + chunk-seam readout (document only while
inference is far under the tick) · DySL-VLA continuity proxy · SwiftVLA randomized-history-K
augmentation (fold into any future retrain; readout first).

## 3. Gaps (stated plainly)

**No mechanism in any batch:** the `go_ready` transit (~4.3-4.7 s - the dominant term of the
5.3 s gap; an **in-house engineering item**, not a paper item); the descent arrival wait
(~2.4 s); the in-window 0-2 tick slide itself (every candidate is pre- or post-window); the
descent workspace-boundary shortfall (motion-profile/scenario-redesign); the policy-gate
bypass (only partially touched); the two-line mix confound (a measurement correction).

**Needing a collection / infrastructure before pre-registration:** contact-stability curation
(implies a curated retrain; a re-recorded store is a new branch with manifest pins);
metadata-conditioned stores (need a mixed-outcome store; the R9 rollout store is the
candidate); force Port B (sim tactile scope); GeoPredict's depth head (needs depth renders);
C-6/SPGrasp (visual-ablation harness + dense-sheet policy data); any PPO-family RL (tokenized
or adjoint action head + multi-env infra). No ranked item needs another full-paper read - two
image-bound supporting tables are not load-bearing (T-Rex recipe labels; FDP tables).

## 4. Corrections of record (P5 -> P6)

Across the 83 indexed entries (79 unique after duplicate pairs) there were **two verdict-level
movements** and two promotions; everything else confirmed with numeric/emphasis corrections.
Full table: `logs/p6/SYNTHESIS.md` §5. The load-bearing corrections:

| # | paper | correction |
| --- | --- | --- |
| 62 | TT-VLA | GO -> **NO-GO as published** (formulated for discretization-based policies; the appendix excludes diffusion heads from PPO; the residual feeds the closed R9 lane) |
| 31 | GenPO | open -> **demoted** (FlowRL's independent benchmark: PPO best/most stable; high Jacobian cost) |
| 37 | FARM | **promoted**: second, scripted-side mechanism (contact-gated force-mode re-entry) targeting the R11-A.1 servo chase |
| 28 | NavDP | **promoted**: the privileged contrastive critic is a selection mechanism (the learned C-1 form), not only sim-to-real prep |
| 32 | GDP | partially refuted: the quality mechanism (OoD population selection) was missed; the schedule-start half is already fixed in-repo |
| 34 | PPGuide | "28 -> 34-36 %" is the 500-epoch cell; at 550 the alternating variant reads 28 (vs DP's 30) |
| 64 | Reactive | the 30 Hz headline is refuted (>=15 Hz suffices at 8 m/min; cliff at 10 Hz); the sim bar is pose-reaching, not grasp rates |
| 81 | ShapeGrasp | "fusion improves every metric" is false (free-space hurts; visuo-haptic < tactile-only; 84/91 % are multi-attempt rates) |
| 73 | soft gripper | wire deploys ~55.94 ms (not ~1 s) - still ~7 ticks, above the window |
| 60 | VLA-Cache | abstract 1.7x/+15 % matches neither table setting (1.63x/+8.5 %) - quote per-setting |
| 20 | T-Rex | "pretrain-only 18 %" unsupported (row labels image-bound); all four combos read 18/34/45/65 |
| 55 | HiF-VLA | dense history hurts (90.4 < 91.0 baseline), not the figure's -29 %/-58 % |
| 8/46 | DynamicVLA | quote the text speed band 0-0.75 m/s (not the figure's 0-1); CR/DA baselines ~20 %; LS gain +33.0 pts |

**Provenance.** `Paper/fulltext_ca/` (column-aware, 84/84, 1,982 pages, page markers;
`scripts/202_paper_text_extract.py`; control bytes stripped, visible text unchanged);
five re-read lanes (`logs/p6/B*_reread.md`); synthesis (`logs/p6/SYNTHESIS.md`); corpus audit
(`logs/p6/QUALITY.md`). No P5 GO verdict was flipped by the corpus fix, and no P5 number was
found corrupted by column interleave - the fix was preventive, and the re-read's value is the
21 corrections plus the mechanism-level mining above.
