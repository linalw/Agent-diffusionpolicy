# KNOWLEDGE BASE: the `Paper/论文/` library vs this project's measured state

Built 2026-10-15 (R-PLAN2 phase P2); **revised 2026-10-16 (P4-B audit)**.
84 papers indexed (`docs/papers/INDEX.md`), the library stays local; this file + the
index are the durable record.
**The ranking is against OUR measured boundaries** (AGENTS.md section 2 + `logs/w8`,
`logs/r6`, `logs/r9`, `logs/r10`, `logs/r11`, `logs/p`, `logs/p1c`, `logs/p2d`,
`logs/p3`), not a generic survey. The end of the file
lists what is already measured negative here so the shortlist does not repeat it.

Evidence grades **(P5, 2026-10-16): `FULL` = the complete paper text was read for all
84 papers** (`Paper/fulltext/`, 1,982 pages, 9,457,715 chars; per-paper method cards in
`logs/p5/B{1,2,3a,3b,4}_cards.md`). Superseded P4-B grades: `E2-deep` (two-page mechanism
read, 26 papers), `E2-scan`, `THIN`. Index numbers (#N) below refer to
`docs/papers/INDEX.md`.

The project's measured state in one paragraph: a bimanual fruit-sorting cell; the belt never
stops; each arm owns a station; the pick is a scripted never-stop dynamic catch; pure grade
routing (left A, right B, C passes); a 4.59M diffusion policy (DDIM-16, ~12 ms/chunk on a
5090, re-plans every 4 steps at 20 Hz) drives the close in the hybrid interface. The measured
bottleneck map, **revised by P1/P1c/P2**: (1) the per-attempt **arm span (~15 s) is the binding
term** - the cadence is flat across the density ladder and the lock-on does not fall, so the
interval is **not** arrival-bound; the earlier "44-45% selection+arrival-wait" reading measured
failed/empty attempts between placements, and P1c refuted density as a positive lever on the
composition-free single-arm line (the two-line hides the starvation by parking and waiting);
(2) the carry escape is a **mid-lift one-sided loaded slide** with a **0-2 tick reaction window**
(the command/squeeze side and the shape side both measured closed; the drive-saturated pinch);
(3) the policy's left deficit was pre-contact acquisition (fixed in-scenario by the ACQ knob + the R7-A shared x-edge refusal; both default-off, so C-6 pins ACQ=1 + R7-A);
(4) the visual ablation is **sub-noise** - the policy is state-conditioned and the 5th "target
mask" channel is empty in the data; (5) any rate claim needs the N=5 paired protocol; (6) quoted
rates are class-dominated until standardized (the P1c correction).

## 1. The ranked table (method -> our bottleneck -> expected movement -> cost/risk -> source)

Rank = the expected movement per unit cost/risk against the map above. All sources are PDF paths
under `Paper/论文/`; extraction counterparts follow the `Paper/text/<DIR>__<file>.txt` rule
(`docs/papers/INDEX.md`).

### Rank 1-4: selection/scheduling under disorder + the fast loop's transit term

| # | paper | our bottleneck | expected movement | cost/risk | source |
| --- | --- | --- | --- | --- | --- |
| 1 | **First Plan Then Evaluate: multi-target planning with post-planning success evaluation** (RA-L) | selection/scheduling on the stocked belt (the v9 pre-fix failure mode) | keep the shipped candidate generators, evaluate K aims at their planned terminals (reachability + intercept feasibility + velocity-matched close margin), execute the max-likelihood one | S / planning K candidates per slot costs ticks - cap K, cache per slot | `20260821/First_Plan_Then_Evaluate_Multi-Target_Planning_With_Post-Planning_Success_Evaluation_Improves_Learning-Based_Grasping_Pipelines.pdf` (#9, FULL) |
| 2 | **SPaSM (Differentiable Particle Optimization for Fast Sequential Manipulation)** | the two-line joint selection + park timing (independent greedy selection + the park gate) | jointly optimize which fruit each arm takes + pre-pose/park targets over a GPU-parallel particle set; prototype offline on log replay before any in-loop build | M / needs a kernel lane the repo lacks; SPaSM assumes a given action skeleton (the attempt cycle provides it) | `20261010-DynamicVLA/Differentiable_Particle_Optimization_for_Fast_Sequential_Manipulation.pdf` (#75, FULL) |
| 3 | **Sentinel-VLA (metacognitive status monitoring + error recovery)** | the carried-not-placed class, acted on **after** the 0-2-tick window (early-abort a doomed carry or one bounded station re-seat) | convert some carried-not-placed into fast skips (interval down) or recovered placements; replay precision/recall gate before any live run | S-M / false-positive aborts waste good carries | `20261009-VLA/Sentinel-VLA A Metacognitive VLA Model with Active Status Monitoring for.pdf` (#66, FULL) |
| 4 | **SkipVLA (classical planning for transit, VLA for contact)** | the pre-pose/park transit segment (transit share per the W6 `[cycle]` decomposition — cite log/table) | a lightweight hover-target scoring head on frozen features, self-supervised from gripper events already in the demo stores; shorten transit distance, not inference latency | S / mispredicted targets cost more than they save - confidence-gated fallback | `20261009-VLA/SkipVLA Skipping VLA Steps with Classical Planning.pdf` (#67, FULL) |

### Rank 5-7: predictive interception + the dense-sheet approach

| # | paper | our bottleneck | expected movement | cost/risk | source |
| --- | --- | --- | --- | --- | --- |
| 5 | **ForeTime-VLA: Causal Future-Token Distillation from a World Action Model for Conveyor-Belt Manipulation** | the dynamic catch's handover (the setup model's missing x-term) | a distilled future code from the exact belt state (encoder + per-fruit poses); endpoint = the handover-time distribution, not the carry class | M / headroom is small (descent-end error already +3.4 mm); price any settle time into `t_setup` from the start (the R10-A lesson) | `20261009-VLA/ForeTime-VLA Causal Future-Token Distillation from a World Action.pdf` (#50, FULL) |
| 6 | **AHEAD ("Intercepting the Future": latent-space predictive world model)** | the same | a frozen-policy wrapper with adaptive-horizon patch prediction (+4.9M params class on a frozen backbone) | M / same caveats | `20261009-VLA/Intercepting the Future Latent-Space Predictive.pdf` (#54, FULL; filename is a title fragment) |
| 7 | **ObstaDiff (target–obstacle–background structured encoder)** | the dense-sheet approach (neighbouring fruit) | restructure visual conditioning into target/obstacle/background roles; SPGrasp-style spatiotemporal memory (#82, GEO) as the perception-side companion for tracking through pair/queue occlusion | M-L / retraining + dense-sheet curation; run the visual-ablation harness first | `20260928/ObstaDiff Generalizable Diffusion Policy Learning.pdf` (#33, FULL) |

### Rank 8-10: force-aware conditioning (adaptation, not reaction) + the fast-loop seam

| # | paper | our bottleneck | expected movement | cost/risk | source |
| --- | --- | --- | --- | --- | --- |
| 8 | **ForceVLA: force-aware MoE for contact-rich manipulation** (NeurIPS-2025) | the close/acquire class; the "force real-time adjustment" (owner #3) | phase-aware expert routing over vision-language + 6-axis force during decoding; the force must **shift the load path before the window**, not react inside it (W5/R11-B bound) | M / retraining; sim tactile exposes normal force + contact count only | `20261009-VLA/NeurIPS-2025-forcevla-enhancing-vla-models-with-a-force-aware-moe-for-contact-rich-manipulation-Paper-Conference.pdf` (#59, FULL) |
| 9 | **Tactile-Conditioned Diffusion Policy (FARM)** (ICRA 2026) | the same | force estimates as observation **and** predicted grip-force as *action* (dual-mode position/force gripper control) — the action-space distinction vs ForceVLA/VLA-Touch | M / same bounds | `20260928/Tactile-Conditioned_Diffusion_Policy_for_Force-Aware_Robotic_Manipulation.pdf` (#37, FULL) |
| 10 | **FlashVLA: streaming action decoding** | the fast action loop's seam (chunk-boundary continuity), **not** raw latency (12 ms/chunk already fits the 50 ms tick) | staggered-noise streaming buffer with chunk-wise causal attention; bridge the seam with the fresh state/proprio+force stream while vision is cached (our ablation: vision sub-noise, state 5-6x noise) | S-M / the async seam can double-apply correction; no explicit future-state predictor in the paper | `20261009-VLA/FlashVLA Streaming Action Decoding for.pdf` (#49, FULL) |

### Rank 11-14: bimanual coordination (heavy) + sim-to-real prep + representation RL

| # | paper | our bottleneck | expected movement | cost/risk | source |
| --- | --- | --- | --- | --- | --- |
| 11 | **SPGrasp (spatiotemporal prompt-driven grasp synthesis)** | tracking the selected fruit through pair/queue occlusion on the dense sheet | promptable video-stream tracking (59-73 ms/frame); perception-side companion to #7, no grip change | S-M / perception only | `20261010-DynamicVLA/SPGrasp_Spatiotemporal_Prompt-Driven_Grasp_Synthesis_in_Dynamic_Scenes.pdf` (#82, FULL) |
| 12 | **MA-VLA (multi-arm VLA for collaboration)** | the two-line coordination (currently scripted) | one policy coordinating both arms/stations — the heavy alternative to the scripted C-2-style optimizer | M-L / **P5: full paper verified present inside the 698-page proceedings-volume PDF and read (FULL) — verdict NO-GO**: atomic action assignment contradicts the scripted-coordination/station-fixed decisions (R5); the coordination-module *form* is the only transferable part | `20261009-VLA/MA-VLA Multi-arm Vision-Language-Action Model for Collaboration and Compositional Generalization.pdf` (#56, FULL) |
| 13 | **NavDP (privileged-information guidance)** | the sim-to-real prep (WS-7.1) | a privileged-state-supervised trajectory critic used to *select* data/behaviors + the pre-registered contact-parameter screen; ceiling is a hardened sim + sensitivity map, stated up front | S-M / owner-gated entry | `20260928/NavDP_Learning_Sim-to-Real_Navigation_Diffusion_Policy_with_Privileged_Information_Guidance.pdf` (#28, FULL) |
| 14 | **SimpleVLA-RL (online outcome-driven RL)** | post-training (R9 closed only AWR-clipped RWR weighting) | veRL-style online RL with trajectory sampling + parallel multi-env rendering — a materially different mechanism (outcome-driven exploration) from R9's weighting lane | M-L / the branch-invariant carry window caps its ceiling at handover/acquisition classes | `20261009-VLA/ICLR-2026-simplevla-rl-scaling-vla-training-via-reinforcement-learning-Paper-Conference.pdf` (#52, FULL) |

## 2. The clusters (the rest of the library, one line each)

- **Fast action / inference**: `HybridFlow` (#78, 2-NFE MeanFlow — a substrate only if
  control moves past 20 Hz, since 12 ms fits the tick), `Deltoris` (#43, temporal
  bit-sparsity + speculation — headline speedup needs their ASIC), `MoLe-VLA` (#40),
  `DySL-VLA` (#45), `VLA-Cache` (#60), `SkipVLA` (#67, ranked), `Fast-dVLA` (#68,
  discrete-token caveat), `IMLE-VLA` (#53), `Realtime-VLA V2` (#65),
  `FabriVLA` (#1, conformal chunk uncertainty), `Ni_SwiftVLA` (#61),
  `DyQ-VLA` (#44), `AR-VLA` (#41), `DAM-VLA` (#42, dynamic action model),
  `PolicyTrim` (#35, lives in `20260928/`), `Sparse ActionGen` (#36, lives in
  `20260928/`), `Learning When to Stop` (#27), `Two-Steps DP` (#32),
  `DynaGuide` (#30), `PPGuide` (#34), `Time-Unified DP` (#38),
  `Conditioning Matters` (#29, training efficiency), `Visual Intermediate` (#70),
  `Towards_Deploying_VLA_Without_Fine-Tuning` (#69, inference-time steering),
  `Fast Generative Grasping via Lie Group-Constrained MeanFlow` (#77 — grasp
  *synthesis*, not a latency lever).
- **Tactile / force control**: `T-Rex` (#20, variable-rate MoT slow/fast experts —
  fast branch declined: sim tactile buys 0-2 ticks), `Reactive Diffusion Policy`
  (#17, slow latent DP + fast reflex — same decline on the fast branch),
  `A forward-reflected-backward method` (#72, adaptive-stepsize force optimization),
  `Multi-fingered Hand Grasps with Visuo-Tactile Fusion via Multi-Agent DRL` (#16),
  `Learning Approach to Optimal Grasping Planning Using Vision-Based Tactile
  Perception` (#79), `ShapeGrasp` (#81 — shape side closed by the D screen),
  `Grasp to Act` (#51, dexterous tool-use), `A soft gripper with an adaptive grasp
  control system` (#73 — hardware; scenario-redesign class).
- **Clutter / singulation / dexterous**: `DexSinGrasp` (#7 — unified singulation+grasp
  RL, but the vehicle is a dexterous hand; transferable part is "separate-then-grasp"
  as *approach-lane selection*, not pushing), `SeqGrasp` (#10 — Allegro DoF-subset
  mechanism, no jaw analogue), `D(R,O) Grasp` (#11), `Toward a Multi-Embodied
  Grasping Agent` (#12), `Collaborative Object Search and Grasp` (#6),
  `Differentiable Particle Optimization` = SPaSM (#75, ranked under SEL).
- **Mobile-manipulator analogs (no conveyor in any of them)**: `On-The-Move` (#13),
  `Continuous Mobile Manipulation` (#14), `Spatially Modulated Velocity Fields`
  (#15 — closest of the three to the catch loop), `Whole-Body Coordination for
  Dynamic Object Grasping with Legged Manipulators` (#83 — embodiment mismatch).
- **RL / post-training**: `D²PPO` (#21 — filename is the bare submission ID
  `17891-AAAI26.ZouG-IR.pdf`; dispersive-loss representation lever, distinct from
  R9's weighting lane), `GenPO` (#31), `FLOWRL` (#25), `On-the-Fly VLA Adaptation
  via Test-Time RL` (#62), `Group Diffusion Policy Optimization` (#26 — diffusion
  *language* models, analogical only), `DemoDiffusion` (#23),
  `Flexible Multitask Learning with Factorized DP` (#24).
- **MoE / multitask / memory / foundation**: `Semantically Structured MoE` (#2/#19),
  `ABSTRACTING … MoE Diffusion Policies` (#18/#22), `EmbodiedSkills` (#47),
  `MAP-VLA` (#57), `HiF-VLA` (#55), `ExpReS-VLA` (#48, byte-duplicate pair),
  `Sentinel-VLA` (#66, ranked under SEL), `GeoPredict` (#63),
  `π0.7` (#5/#39), `VGGT` (#4, geometry only).
- **Not applicable**: `SHELLS` 3D head reconstruction (#3), `Eye-to-action` (#76 —
  gaze-driven HRI, needs a human operator; not inference acceleration),
  `A soft gripper` (#73, hardware).

## 3. The shortlist for P4-C (the combinations to implement, per the owner's directives)

> **P6 (2026-10-16): superseded by `docs/papers/MECHANISMS.md`.** All 84 papers were re-read in
> full on a column-aware corpus (`Paper/fulltext_ca/`, `logs/p6/QUALITY.md`), five adversarial
> lanes challenged every verdict (`logs/p6/B*_reread.md`), and the cross-batch synthesis
> (`logs/p6/SYNTHESIS.md`) produced the committed 11-item mechanism menu with the P6 ranking:
> **1 C-3 carry monitor, 2 C-1 FPTE terminal scoring, 3 force Port A (contact-gated re-entry),
> 4 C-2 two-line primary-then-conditional, 5 GDP OoD sampling, 6 event-structure handover
> heads, 7 D²PPO dispersive, 8 SECL retry discipline, 9 contact-stability curation,
> 10 reactive trace re-aim, 11 perception companions.** P6 corrections of record: TT-VLA
> GO -> NO-GO (diffusion heads excluded from PPO); GenPO demoted (FlowRL benchmark); FARM and
> NavDP promoted; PPGuide/Reactive/ShapeGrasp/VLA-Cache numbers corrected; SkipVLA (C-5)
> demoted (transit ~14 % of span). The C-1..C-8 text below is kept for provenance.

The owner's goal: **bimanual dynamic fast sorting under scattered/unordered supply + fast
action closed loops + force real-time adjustment**; combinations, bold with evidence, do not
stop at the first performance drop.

- **C-1 (selection first, scripted, S)**: FPTE plan-then-evaluate over candidate aims
  (rank #1). Endpoint: paired carried-class + no-fire-slot conversion (sign p≤0.05);
  mechanism readouts = `eligible/feasible/chosen` splits + lock-on; kill on any new reason
  or acceptance drift.
- **C-2 (joint two-arm selection + placement optimizer, SPaSM-style, M)**: offline
  log-replay re-selection before any in-loop build (rank #2). Endpoint: pooled interval +
  starvation slots at N≥3 batteries vs the park-gate-on baseline.
- **C-3 (attempt-granularity monitor + recovery, Sentinel-style, S-M)**: replay
  precision/recall gate first, then N=5 paired carried-class conversion with cycle
  non-inferiority (rank #3). Structurally different from the closed in-window guards.
  **P5 additions**: (a) **JCAC conformal action-chunk calibration (#1, FabriVLA)** — a
  post-training, frozen-policy, 0.58M-param recipe for exactly the attempt-granularity risk
  ranking C-3 needs (joint-prefix coverage, episode-max-radius failure ranking; Cost S);
  complements a VLM-side monitor with an action-space signal. (b) **EmbodiedSkills (#47)**
  attempt-granularity preflight/verify/recover — same slot, scripted-side form.
- **C-4 (learned predictive interception, M)**: ForeTime/AHEAD form for the setup x-term
  (rank #5/#6). Endpoint: the handover-time distribution + fallback chases; kill if re-seats
  rise (the R11-A 0→10 signature) or any descent leaves budget. **P5 backups**: GeoPredict
  (#63, training-time predictive supervision — heavier infra, behind ForeTime/AHEAD); the
  reactive grasp controller (#64, per-tick path reshaping + 1 kHz velocity commands) as the
  named **scripted-catch alternative** if the learned lane stalls — materially distinct from
  the closed guards (acts on the path, not inside the contact window).
- **C-5 (self-supervised hover-target predictor, S)**: SkipVLA transferable bit for the
  pre-pose/park transit (rank #4; transit share per the W6 `[cycle]` decomposition — cite log/table). Endpoint: transit-segment timing + fallback-rate cap.
- **C-6 (TOB-structured dense-sheet approach, M-L)**: ObstaDiff + SPGrasp tracking companion
  (rank #7/#11). Endpoint: N=5 paired acquired-fidelity + starvation slots,
  **class-standardized** (the P1c correction); ACQ=1 + R7-A pinned.
- **C-7 (privileged-critic sim-to-real prep, S-M, prep not a rate lever)**: NavDP recipe +
  the contact-parameter screen, owner-gated (rank #13).
- **C-8 (frozen-policy failure-mode steering, PPGuide #34, S-M)**: steer the frozen diffusion
  policy away from failure via an MIL-labelled success/failure classifier + alternating-step
  guidance — no demos, no dense rewards, no world model; structurally distinct from closed
  in-window guards. **P5 new finding.** Endpoint: replay precision/recall gate first, then N=5
  paired carried-class conversion; kill on no conversion, new reasons, or per-fruit tuning
  that does not transfer.

Each combo is default-off, scoped (direct or two-line), pre-registered with a numeric
criterion + kill criteria, and evaluated with the N=5 paired protocol (direct claims) or the
per-scenario gate + fingerprint (scripted/two-line claims) + the byte-level no-harm.

## 4. Already measured negative here - do not re-propose without a materially different mechanism

RTC (-20 pt), VLASH (-31 pt), A2C2 (-20 pt) — none are in `Paper/`; they are repo-measured
negatives — cite `logs/w5/FRONTIER.md` and the log dirs it names (`logs/811_rtc_ab_moe_v10/`,
`logs/path3b/`), not `Paper/`; `docs/research_dynamic_grasp_methods.md` §§1–5 describes the
methods, not these results. The
event-triggered horizon (+1.3 pt, failed N=5), GEM tracking (flat), verify-dwell/ramp-lift, the
finger-face variants, the place squeeze/wrist hold, the squeeze-side family
(force/depth/relief - drive-saturated), the shape side (the grip plane/cradle/station - the D
screen), the reactive guards (p=0.1094/0.3125), the two behaviour-cloning recollections (W7-C
underpowered; W8-A p=1.0), AWR-clipped RWR-2 (p=0.5 — weighting only; SimpleVLA-RL/D²PPO are
different mechanisms and stay open as questions, not commitments), the adaptive selection lead
(bit-identical), the hot-arm residency (fires 4/18, flat), the pre-onset load path knobs
(stage-P 12/20 vs 13/18), the reach-anywhere adoption (the acceptance 44% vs 90%), the density
as a positive lever (P1c single-species negative; D=2.0 crowding collapse is the real density
effect), the place-leg shortening (geometry-closed, P3). The fast-tactile-reflex branch of
RDP/TDP/FARM is declined (sim tactile buys 0-2 ticks); faster samplers / 2-NFE / speculative /
discrete-token VLA are declined as latency levers (12 ms fits the tick). D3-proper, the two-line
default flip, single-arm pure routing, and ACQ shipping stay owner-gated / R5-decided.

## 5. Sources / provenance (corrected by the P4-B audit)

`Paper/text/` = the first-two-page `pdftotext` extraction of each PDF (**84 files**) plus
`DIGEST_all.txt` = **85 `.txt` files, 839,858 bytes (~820 KB)** — the old "84 files, 948 KB"
is corrected. **P5 adds the full-text corpus: `Paper/fulltext/` = all 84 papers, every page
(1,982 pages, 9,457,715 chars; manifest `Paper/fulltext/MANIFEST.tsv`), with per-paper
FULL method cards in `logs/p5/B{1,2,3a,3b,4}_cards.md` (83 cards; the ExpReS byte-duplicate
pair shares one card).** `DIGEST_all.txt` (850 lines) carries a generator artifact: lines 841–850 append a
`### DIGEST_all` section repeating the FabriVLA entry. 5 duplicate pairs → **79 unique logical
papers**. The old §1 source column mixed PDF paths with extraction paths (`DIR__file.txt`) and
mis-housed PolicyTrim/Sparse ActionGen under `20261009-VLA/` — all corrected above to PDF paths
(the extraction counterpart always follows the `Paper/text/<DIR>__<file>.txt` rule). Filename
traps recorded: D²PPO = `20260928/17891-AAAI26.ZouG-IR.pdf`; AHEAD = the "Intercepting the
Future" title fragment; Fast-dVLA = `Song-2026-Fast-dvla-accelerating-discrete-dif (1).pdf`;
DyQ-VLA and the two force-paper filenames are truncated in the repo. The ranking above is
derived from the extractions plus the project's own measured record (AGENTS.md section 2 +
logs/w8, logs/r6, logs/r9, logs/r10, logs/r11, logs/p, logs/p1c, logs/p2d, logs/p3).

## 6. Open questions for P4-C (protocol/owner answers needed before any build)

1. Endpoint hierarchy: keep paired carried-class conversion (6-0 edge, p≤0.05) primary with
   rate secondary and class-standardized (the P1c lesson)?
2. Interface pins: ACQ=1 + R7-A fix + `moe_v13s` (`61da390a`) frozen for every direct arm?
3. Gate of record: hybrid pinned canary for shipping, direct N=5 for mechanisms (R5) — each
   pre-reg states which gate it answers; direct-vs-hybrid comparisons stay forbidden.
4. Store choice for representation work (`demos_v11` anchor vs two-line stores; 125 GB ceiling).
5. Keep the P4 conjunction (strawberry non-inferior AND cycle within +5% AND zero new reasons)?
6. MA-VLA: **CLOSED by P5** — full paper read (via the proceedings volume), verdict NO-GO
   (contradicts the R5 scripted-coordination/station-fixed decisions); coordination stays
   scoped to the scripted SPaSM-style optimizer (C-2).
7. WS-7.1 entry for the contact-parameter screen + privileged critic, ceiling accepted?
8. D²PPO as a future representation lever (distinct from R9's weighting lane) — **P5: B2
   promotes it on a measured complex-task scaling law** (dispersive pre-training + PPO
   fine-tuning, endpoint N=5 paired carried-class conversion); still needs the scope decision.
