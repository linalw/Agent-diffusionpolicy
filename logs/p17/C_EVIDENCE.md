# P17-C C_EVIDENCE: the KB-refresh scouting log (query log + source ledger)

Status: **Tier-C, offline, web-scouting lane** (branch `p-supply`, 2026-10-19). No simulator run,
no `src/`/`scripts/`/`configs/`/`datasets/`/`Paper/` edit, no commit; the only writes are
`docs/papers/UPDATE_2026_10.md` and this directory (`logs/p17/`). Tree pins as read:
`tasks.py` `54f70584b07fa249418f1efe30f30af0` (the P16-I tree), `fruits.py`
`d28546d26137d4540421caa7fa34a139`; HEAD `05c83fd`.

**Mission.** P17-C: refresh the knowledge base (`docs/KNOWLEDGE_BASE.md` +
`docs/papers/MECHANISMS.md`, both 2026-10-16) against the measured findings since (P12–P16), with
a targeted 2024–2026 literature scout for the NEW findings: (a) the capture/grip transient under
belt motion (P14-B), (b) the conserved failure mass (P15), (c) the sim-to-real fruit physics
(P12-A/A.2), (d) the conditioning-side policy work (P13/P14-C), (e) the bimanual line-sorting
throughput (the BIMANUAL.md KB). Every external finding carries its URL, a confidence mark
(`FULL-READ` = the body was read in this lane; `ABSTRACT+BODY-SNIPPET` = search-indexed body
text, the artifact itself over the fetch cap; `ABSTRACT-ONLY` = abstract/snippet only), and a
transfer sketch. Local claims point at their log.

---

## 1. The local inputs read (all read-only)

| file | what it supplied |
| --- | --- |
| `docs/papers/MECHANISMS.md`, `docs/KNOWLEDGE_BASE.md`, `docs/papers/BIMANUAL.md`, `docs/papers/INDEX.md` | the current menu, map, bimanual goal KB, the 84-paper index |
| `logs/p14b/TRACE_RESULTS.md` (+ `master_table.md`) | the capture transient: the payload slides at belt speed during the hold; the no-grasp class disjoint (294.8–95 403.7 vs ok 0–27.2 mm); the re-seat floor dead as initiator (F1); the close/hold family selected |
| `logs/p15/OUTCOME_RESULTS.md` | the M2 hold-window lead: mechanism win (no-grasp 7→4), carried trade (2→6), pooled 45→38, interval +8 %; the conserved failure mass (third instance) |
| `logs/p16i/SCREEN_RESULTS.md` | the H1 completed descent: `end=` 9.4→5.9, catch-up 14.0→6.7, the walk unmoved (K1) — the shortfall does not feed the capture |
| `logs/p13/B_RESULTS.md`, `logs/p13/B_N5_RESULTS.md`, `logs/p13/NOHARM_RESULTS.md` | the ev1 event-structure heads: N=3 +3; N=5 +6 (43→49/75, p=0.0898); the acquisition p90 266.8→5.5; the chases 15→4; the canary anomaly + revert |
| `logs/p14/A_RESULTS.md` | the canary separation closed as instrument variance (20–80 % across 10 runs); the ≥5-runs/side standing rule |
| `logs/p14c/IMPLEMENTATION.md` | the P14-C.1 ablations (A1/A2/A3) in flight |
| `logs/p12/A_RESULTS.md`, `logs/p12a2/A2_RESULTS.md` | the real-physics batch and the component decomposition: mass-only +6 pooled, falls 14→6 rows; rest neutral; compliance −9; the mass base |
| `logs/p11c/C_RESULTS.md` | the first instance of the mechanism-win/class-re-draw pattern (the from-open arrival) |
| `logs/p16/BOUNDARY_DESIGN.md` | the descent-boundary diagnosis refresh and the option ranking |
| `.slim/deepwork/sorting-pipeline-v3.md` (P14–P17 PLAN) | the phase context and the P17-B sibling lane |

## 2. The query log (10 searches + 8 fetches; 2026-10-19)

Searches (in order; the mission's topic tags):

| # | query | topic | outcome |
| --- | --- | --- | --- |
| S1 | dynamic grasping moving conveyor belt slip arrest force control 2025 | (a) | Maranci et al. (= local #64, already indexed), Islam CTMP (2020/21, context), MDPI mine-conveyor MATD3 |
| S2 | grasp force modulation impact transient robotics 2025 | (a) | adaptive grasp-force tracking (2412.02335), shear-based grasp control (2503.17501), Nazari Nature MI (= already in EXTERNAL-C), step-load transient modulation |
| S3 | robotic grasping failure mode trade-off redistribution manipulation learning 2025 | (b) | GTP-FA (2606.03385), GOMP, RL-critic grasp scoring, failure-mode prediction (2020 + Springer 2024) |
| S4 | deformable fruit simulation contact model validation robot harvesting sim-to-real 2025 | (c) | OrchardBench, Gazebo Plants, blueberry-cane validation, Find the Fruit, strawberry zero-shot |
| S5 | event structure conditioned diffusion policy manipulation phase prediction transition 2026 | (d) | SCDP, DPTG, PAF, SADiff |
| S6 | bimanual dual-arm robot conveyor sorting throughput coordination 2026 | (e) | T&F value-of-information 2026, BiKC, Bombile & Billard, WBCD competition |
| S7 | impact-aware grasping capture relative velocity conveyor belt robot 2026 | (a) | IMA-Catcher (2506.20801), kinodynamic trajectory manifold catching (2605.28462), OSW (2609.29020), GEM path shaping (= the closed repo GEM lane's paper) |
| S8 | manipulation policy improvement failure modes shift redistribution robot learning 2025 2026 | (b) | MonoDuo, phase-conditioned IL w/ recovery, Z-1, "Robot Learning as an Empirical Science" |
| S9 | fruit grasp friction slip force measurement apple tomato robot gripper experiment 2025 | (a)+(c) | How Firm Should a Grasp Be? (CoRL 2026), FruitTouch, grasp-state classification (2508.11588), IMU slip detection (Frontiers 2025), force-regulated low-cost gripper (2602.10013) |
| S10 | dual-arm robotic sorting cell conveyor cycle time throughput 2026 study | (e) | ROBOCYCLE (2607.03616), NIST MRF review 2026, RSS layout studies, T&F value-of-information |
| S11 | failure diagnosis improving manipulation policies runtime monitoring consistency progress 2025 | (b) | **FAILED** (tool error) |
| S12 | robot manipulation failure diagnosis recovery policy Sagar Duan 2025 | (b) | RoboMD (ICLR 2026), "Cracking Mobile Manipulation" (2610.19600) |

Fetches:

| # | URL | result |
| --- | --- | --- |
| F1 | `https://www.tandfonline.com/doi/full/10.1080/21681015.2026.2638174` | **FAILED** (certificate verification error) — kept at search-snippet confidence |
| F2 | `https://arxiv.org/html/2506.20801v1` (IMA-Catcher) | OK, FULL-READ |
| F3 | `https://arxiv.org/html/2609.29020v1` (OSW) | OK, FULL-READ |
| F4 | `https://arxiv.org/html/2606.03385` (GTP-FA) | OK, FULL-READ |
| F5 | `https://arxiv.org/html/2406.10093v2` (BiKC) | OK, FULL-READ |
| F6 | `https://link.springer.com/article/10.1007/s00521-024-10856-1` | **BLOCKED** (auth redirect) — recorded, not used |
| F7 | `https://arxiv.org/html/2607.03616v1` (ROBOCYCLE) | **FAILED** (certificate verification error) — kept at search-snippet confidence |
| F8 | `https://cave.cs.columbia.edu/Statics/publications/pdfs/Beveridge_CoRL26.pdf` | **OVER CAP** (7.6 MB > 2 MB fetch limit) — kept at search-indexed-body confidence |

## 3. The source ledger (URL + confidence + the one-line)

Grouped by the mission's topics. The transfer sketches are in `docs/papers/UPDATE_2026_10.md`
section 2; this ledger records provenance.

### (a) the capture/grip transient under belt motion

| source | URL | mark | the one-line |
| --- | --- | --- | --- |
| Tassi, Zhao, Lahr, Gava, Monforte, Glover, Bartolozzi, Ajoudani (IIT), IMA-Catcher, IJRR 45(1):100–127, 2025 (arXiv 2506.20801) | `https://arxiv.org/html/2506.20801v1` | **FULL-READ** | impact-aware nonprehensile catching in two designed phases: pre-catching velocity-matching QP + reflected-mass minimization; post-catching human-learned variable-stiffness dissipation; impact force ∝ relative velocity (F̂ = −(1+e)Δv / (uᵀ(Λ⁻¹+1/m_o)u)); "the same task without velocity matching would be infeasible due to excessive joint torques"; stiffness cannot affect the impact itself (few-ms duration) |
| Pei, Wu, Su, Qi, Liu, Navarro-Alarcon, Liu, Zhou, "Outcome-Sensitive Motion Search for Impact-Aware Dexterous Catching", arXiv 2609.29020, Sep 2026 | `https://arxiv.org/html/2609.29020v1` | **FULL-READ** | the outcome-sensitive window (OSW) = the short pre-contact interval where local motion interventions flip downstream outcomes; demonstration construction by manifold + geodesic search localized to the OSW, validated by complete rollouts under a calibrated student-error model; student 90.3 % vs teacher 85.2 %, f_max −8.6 %; refinement helps impact, repair helps success; xArm7 + ORCA hand, MuJoCo |
| Beveridge et al., "How Firm Should a Grasp Be?", CoRL 2026 | `https://cave.cs.columbia.edu/Statics/publications/pdfs/Beveridge_CoRL26.pdf` | **ABSTRACT+BODY-SNIPPET** (PDF 7.6 MB > cap) | online estimation of shape/mass/elasticity/friction during the grasp (GelSight Minis + load cells) → the minimum grasp force; a 29 real fruit/vegetable property dataset; a tribological drop test measures µ and interfacial shear τ by reducing force until optical-flow-detected slip; nectarine optimal force 1.12 N; parallel-jaw UR5 + WSG50 |
| FruitTouch, arXiv 2602.18991, 2026 | `https://arxiv.org/html/2602.18991v1` | **ABSTRACT+BODY-SNIPPET** | a perceptive gripper with slip detection + force control: cherry tomato open-loop 58.3 % → slip 100 % → slip+force 100 %; strawberry 12.5 % → 37.5 % → 75 %; on slip, close an extra 2 mm and retry; force-guided retries (2 N + 1 N steps) collapse force variance |
| "Shear-based Grasp Control for Multi-fingered Underactuated Tactile Robotic Hands", arXiv 2503.17501, 2025 | `https://arxiv.org/pdf/2503.17501v1` | **ABSTRACT-ONLY** | PID on the change in tactile shear (ΔF_x, ΔF_y) with a zero-shear setpoint retains objects under disturbances; needs shear-capable tactile |
| Cheng et al., "An Adaptive Grasping Force Tracking Strategy for Nonlinear and Time-Varying Object Behaviors", arXiv 2412.02335, 2025 | `https://arxiv.org/html/2412.02335v2` | **ABSTRACT-ONLY** | online LSTM generalized-stiffness estimation adapts a PI force-tracking controller; objects incl. eggs, sandbags, water balloons; force tracking of unknown stiffness |
| Bombile & Billard, "Dual-Arm Control for Coordinated Fast Grabbing and Tossing of an Object", IEEE RAM 2022 (and RAS 2023) | `https://infoscience.epfl.ch/entities/publication/8940fa0d-e052-4671-8e74-212e82a3d893` | **ABSTRACT-ONLY** | grasping with non-zero relative velocity; contact forces controlled prior to and following impact to stabilize the grip; EPFL dual-arm, one-swipe grab-and-toss (outside the 2024–26 window; recorded for the mechanism lineage) |

### (b) the conserved failure mass / trade

| source | URL | mark | the one-line |
| --- | --- | --- | --- |
| Wang, Tang, Yu, Wu, Fang, Li, Zhong et al., "Cracking Mobile Manipulation: From Failure Diagnosis to Agentic Robot System", arXiv 2610.19600, Oct 2026 | `https://arxiv.org/html/2610.19600v1` | **FULL-READ** | failure attribution over 81 failed episodes (planning 21.0 %, navigation/base 25.9 %, local manipulation 53.1 %); the **moving failure frontier**: "improving one stage exposes the next bottleneck along the pipeline"; tracked failure-distribution shifts under progressive interventions (19 % → 47 % success; targeted modes 9→0, 11→1, 10→3); recovery-window attribution rules (recovered-within-3-replans excluded); three Codex diagnoses + human review (Fleiss κ=0.86) |
| Wang, Zhang, Yu, Fu, Chen, Xiang, Yu, Fu, Wang, "Grasp-Then-Plan with Failure Attribution", arXiv 2606.03385, Aug 2026 | `https://arxiv.org/html/2606.03385` | **FULL-READ** | failure modes {FM-G1 task-irrelevant grasp, FM-G2 unstable grasp/slip, FM-P planning/policy}; weak labels from K repeated trials per grasp (terminal success rate); a discriminator + grasp-conditioned embedding; **diagnosis-driven routing** of optimization pressure (grasp side vs planning side); ablations: single-side optimization is insufficient (planning-only −27.9/−54.5 pp for PPO/SAC; grasp-only negative for all), naive joint optimization still hurts PPO/SAC; full routing improves PPO +31.3, BC +54.0, DP +25.7, π0.5 +17.8 pp; real robot 11.2 % → 76.8 % |
| Sagar, Duan, Vasudevan, Zhou, Ben Amor, Fox, Senanayake, RoboMD, ICLR 2026 (arXiv 2412.02818) | `https://arxiv.org/html/2412.02818v4` | **ABSTRACT-ONLY** | deep-RL active search for failure modes in a VLM embedding space; ranks seen/unseen conditions by failure likelihood; fine-tuning on discovered failures (top-3 failures 85.5 % → 92.8 % in the slide) |
| "Robot failure mode prediction with deep learning sequence models", Neural Computing & Applications, 2024 | `https://link.springer.com/article/10.1007/s00521-024-10856-1` | **BLOCKED** (auth wall) | predicting grasp failure at the early stages of end-effector motion from sequences — recorded for the monitor lane; body not read, no numbers used |

### (c) the sim-to-real physics for fruit handling

| source | URL | mark | the one-line |
| --- | --- | --- | --- |
| (How Firm Should a Grasp Be? — cross-listed under (a): the property estimation + friction/shear drop test + the 29-fruit dataset is the fruit-physics validation core) | see (a) | ABSTRACT+BODY-SNIPPET | — |
| "Gazebo Plants: Simulating Plant-Robot Interaction with Cosserat Rods", arXiv 2402.02570, 2024 | `https://arxiv.org/pdf/2402.02570` | **ABSTRACT-ONLY** | Cosserat-rod plants; fruit-detachment threshold calibrated against a real tomato pick (C_max = 0.1 matches the real detach time); simulation-to-real-time 0.93 |
| "How Well Do Pseudo-Rigid Body Models Capture Real Plants? In-Field Validation", arXiv 2609.13627, 2026 | `https://arxiv.org/html/2609.13627v1` | **ABSTRACT-ONLY** | force-displacement validation of lumped-parameter cane models against in-field measurements; significant error in the naïve comparison; viable for small deflections only |
| "Find the Fruit: Zero-Shot Sim2Real RL for Occlusion-Aware Plant Manipulation", arXiv 2505.16547, 2025 | `https://arxiv.org/html/2505.16547v3` | **ABSTRACT-ONLY** | FEM plant in Isaac Lab + domain randomization + a compliant low-level controller; 86.7 % physical vs 96.1 % sim; the decoupling of high-level planning from uncertain contact dynamics |
| Williams & Polydoros, "Zero-Shot Sim-to-Real RL for Fruit Harvesting" (FruitGym), arXiv 2505.08458, 2025 | `https://arxiv.org/abs/2505.08458` | **ABSTRACT-ONLY** | a custom MuJoCo strawberry-cluster sim; Franka Panda; the dense-cluster harvesting pipeline |
| OrchardBench, arXiv 2607.06337, 2026 | `https://arxiv.org/html/2607.06337v1` | **ABSTRACT-ONLY** | GPU-parallel apple-orchard benchmark; Newton contact; stem-tension detachment; "sim-to-real transfer is a design goal we support, not a result we demonstrate"; harvest completeness 0.12, 1.9 fruit/min |

### (d) the conditioning-side policy work

| source | URL | mark | the one-line |
| --- | --- | --- | --- |
| Liu et al., "DPTG: diffusion policy with tactile feasibility guidance", Front. Robot. AI 13:1851102, 2026 | `https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2026.1851102/full` | **ABSTRACT-ONLY** | tactile as a *feasibility constraint / phase-awareness regulator*, not as an action-generating input ("tactile signals are event-driven and temporally sparse; forcing policies to directly generate actions from such signals often leads to degeneration"); phase awareness derived from tactile feasibility |
| Kim et al., "Spatially Conditioned Diffusion Policy", CoRL 2026 (arXiv 2606.14535) | `https://arxiv.org/html/2606.14535v2` | **ABSTRACT-ONLY** | conditioning the diffusion U-Net on features sampled along intermediate EE trajectories (spatial attention anchors); +4.0 ms latency vs DP at 16 DDIM steps |
| Chen et al., "Phase-Conditioned Affordance Fields for SE(3)-Equivariant Visuomotor Policies", CoRL 2026 (arXiv 2610.17281) | `https://paf-policy.github.io/` | **ABSTRACT-ONLY** | a phase-context encoder (six SE(3)-invariant statistics from state history) → per-point affordance scores that re-anchor observation and action; a phase-conditioned *spatial* anchor |
| "Skill-Aware Diffusion for Generalizable Robotic Manipulation" (SADiff), arXiv 2601.11266 | `https://arxiv.org/html/2601.11266v2` | **ABSTRACT-ONLY** | skill tokens + a router selecting motion primitives per state; skill contrastive learning |
| "Phase-Conditioned Imitation Learning with Autonomous Failure Recovery for Robust Deformable Object Manipulation", arXiv 2605.29407, 2026 | `https://arxiv.org/html/2605.29407v1` | **ABSTRACT-ONLY** | phase detector + phase-conditioned ACT + hybrid impedance controller; "without explicit phase information the policy implicitly learns a mixture whose competing modes produce averaged or oscillatory behavior at aliased states"; recovery from 40/44 hanging + 4/8 takeoff contact failures |

### (e) the bimanual line-sorting throughput (newer than the ETH/SPT-FIFO findings)

| source | URL | mark | the one-line |
| --- | --- | --- | --- |
| "The value of information in automated sorting: leveraging look-ahead in multi-conveyor systems with articulated robotics for pick and place", Int. J. Logistics Management (T&F), Feb 2026 | `https://www.tandfonline.com/doi/full/10.1080/21681015.2026.2638174` | **ABSTRACT-ONLY** (fetch cert-blocked; search-indexed body) | a probability-based continuous-time controller for multi-arm conveyor packing with strong sequence dependence; a prepended buffer conveyor outside arm reach = look-ahead; **greater reach for early-stage arms beats extending downstream reach**; buffer benefit plateaus; look-ahead increases selectivity but "inherently experiences longer waiting times, leading to a decrease in tray throughput" |
| Yu, Xu, Chen, Pan, "BiKC: Keypose-Conditioned Consistency Policy for Bimanual Robotic Manipulation", arXiv 2406.10093, 2024 | `https://arxiv.org/html/2406.10093v2` | **FULL-READ** | keypose predictor (contact-mode change / motion stalling / case rules) + one-step consistency-model generator; bimanual keypose **merging** = sort(unique(per-arm keypose indices)) "eliminates the need for manual coordination of pause-or-proceed decisions"; real ALOHA "Placing and Picking on Conveyor" (74 mm/s): ACT 0/20, DP 10 %, CP 100 %, BiKC 100 %; inference 22.6–27.8 ms vs DP 114–116 ms; ACT fails via temporal-ensembling decision delay |
| ROBOCYCLE, arXiv 2607.03616, 2026 | `https://arxiv.org/html/2607.03616v1` | **ABSTRACT-ONLY** (fetch cert-blocked) | dual-arm recycling: "only one arm enters the grasping zone at a time" (temporal synchronization node) with parallel removal; behavior trees; 84.3 % task success; 8.3 s/item cycle; RF-DETR 20.45 FPS |
| Haldankar & Schumacher, "Robotic sorting and AI in material recovery facilities: a review", Waste Management 226:115830, 2026 | `https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=960572` | **ABSTRACT-ONLY** | review: multi-arm systems (4–6 arms) scale system throughput; "comparisons ... should specify whether figures are reported per unit, per arm, or per installed system"; delta robots fastest per pick, articulated arms slowest |
| MonoDuo, arXiv 2605.29298, 2026 | `https://arxiv.org/pdf/2605.29298` | **ABSTRACT-ONLY** | bimanual policies learned from single-arm robot demos + human collaboration; failure analysis: 71.2 % of failures are grasping errors — "primarily limited by contact-sensitive execution, rather than task-level sequencing" |

### Context (in-library or previously-scouted; no new transfer claimed)

* Maranci, Avizzano, D'Avella, "Reactive grasp controller for dynamic grasping of moving objects",
  RAS 200:105401, 2026 (`https://www.sciencedirect.com/science/article/pii/S0921889026000746`) —
  **= local paper #64** (already FULL in `Paper/`); the reactive trace controller + 1 kHz velocity
  commands; already recorded in MECHANISMS.md item 10.
* Islam, Salzman, Agarwal, Likhachev, "Provably constant-time planning and replanning for
  real-time grasping objects off a conveyor belt", IJRR 40(12-14), 2020/21
  (`https://cris.technion.ac.il/en/publications/provably-constant-time-planning-and-replanning-for-real-time-gras`)
  — **ABSTRACT-ONLY**, outside the window; the constant-time-planning guarantee for conveyor
  interception (planning-side context).
* Nazari et al. (Nature MI 2025, trajectory modulation for slip control), GEM (path shaping,
  arXiv 2508.14042) — already in the repo's P9-E scouts / the closed GEM lane; not re-claimed.
* "Robot Learning as an Empirical Science: Best Practices" (arXiv 2409.09491) — **ABSTRACT-ONLY**;
  evaluation-methodology context for the branch discipline.

## 4. What this lane did NOT do

No simulator run; no `src/`/`scripts/`/`configs/`/`datasets/`/`Paper/` write; no branch
operation; no commit; no default changed. The scouted papers are external sources, not in the
local `Paper/` library; the KB page records them as such. Numbers from unread bodies are never
quoted as numbers of record (the F6-blocked and F8-over-cap items are marked accordingly).
