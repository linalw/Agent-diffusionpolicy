# Paper library index: 84 PDFs → 84 extractions

Verified 2026-10-16 (P4-B audit). Paths are repo-relative. `Paper/` is local-only
and is never committed; this index plus `docs/KNOWLEDGE_BASE.md` are the durable record.

- **Inventory: 84 PDFs** (5 + 7 + 3 + 1 + 4 + 19 + **33** + 12 = 84; the audit's
  "35 in `20261009-VLA/`" was a miscount, corrected here), **84 first-two-page
  `pdftotext` extractions + `DIGEST_all.txt` = 85 `.txt` files, 839,858 bytes
  (~820 KB)** — not "948 KB".
- **Mapping rule: `Paper/论文/<DIR>/<file>.pdf` ↔ `Paper/text/<DIR>__<file>.txt`.**
  Verified 1:1 for all 84 (no orphan PDF, no orphan extraction).
- **5 duplicate pairs → 79 unique logical papers**: Semantically-Structured-MoE
  (title spacing variant), ABSTRACTING-MoE (identical basename, two dirs), π0.7
  (filename spacing variant), DynamicVLA (short vs full title), ExpReS-VLA
  (byte-duplicate `(1)` pair).
- **Evidence grades (P5, 2026-10-16)**: `FULL` = the complete paper text was read
  (all 84, via `Paper/fulltext/` — 1,982 pages, 9,457,715 chars, manifest
  `Paper/fulltext/MANIFEST.tsv`); per-paper method cards live in `logs/p5/B{1,2,3a,3b,4}_cards.md`.
  Superseded grades from the P4-B pass: `E2-deep` (two-page mechanism read, 26 papers),
  `E2-scan` (title + digest + extraction scan). MA-VLA's body was verified present inside
  its 698-page proceedings-volume PDF (the 573-byte front-matter extraction was proceedings
  boilerplate, not the paper).
- **Clusters**: ACT fast action/inference · FRC force/tactile · PRED predictive
  interception · CLU clutter/singulation · BI bimanual · SEL selection/scheduling/
  recovery · SIM sim-to-real · RL RL/post-training/imitation · MOE MoE/multitask ·
  GEO geometry/perception · MOB mobile-manipulator analog · GEN general foundation ·
  NA not applicable to this cell.

## `20260804/` (5)

| # | PDF file | extraction file | status | cluster |
|---|---|---|---|---|
| 1 | FabriVLA A Lightweight Vision-Language-Action Model with Conformal Action.pdf | 20260804__FabriVLA A Lightweight Vision-Language-Action Model with Conformal Action.txt | OK, FULL | ACT |
| 2 | Semantically Structured Mixture-of-Experts forCompositional Robotic Manipulation.pdf | 20260804__Semantically Structured Mixture-of-Experts forCompositional Robotic Manipulation.txt | OK, FULL, DUP (pair: #19, title spacing variant) | MOE |
| 3 | Topologically Consistent Multi-view 3D Head Reconstruction via.pdf | 20260804__Topologically Consistent Multi-view 3D Head Reconstruction via.txt | OK, FULL | NA (head reconstruction) |
| 4 | VGGT Visual Geometry Grounded Transformer.pdf | 20260804__VGGT Visual Geometry Grounded Transformer.txt | OK, FULL | GEO |
| 5 | π0.7 a Steerable Generalist Robotic Foundation.pdf | 20260804__π0.7 a Steerable Generalist Robotic Foundation.txt | OK, FULL, DUP (pair: #39, spacing variant) | GEN |

## `20260821/` (7)

| # | PDF file | extraction file | status | cluster |
|---|---|---|---|---|
| 6 | Collaborative_Object_Search_and_Grasp_via_Vision-Language_Guided_Reinforcement_Learning.pdf | 20260821__Collaborative_Object_Search_and_Grasp_via_Vision-Language_Guided_Reinforcement_Learning.txt | OK, FULL | CLU |
| 7 | DexSinGrasp_Learning_a_Unified_Policy_for_Dexterous_Object_Singulation_and_Grasping_in_Densely_Cluttered_Environments.pdf | 20260821__DexSinGrasp_Learning_a_Unified_Policy_for_Dexterous_Object_Singulation_and_Grasping_in_Densely_Cluttered_Environments.txt | OK, FULL | CLU (dexterous hand; jaw-transfer limited) |
| 8 | DynamicVLA  A Vision-Language-Action.pdf | 20260821__DynamicVLA  A Vision-Language-Action.txt | OK, FULL, DUP (pair: #46, short vs full title) | ACT/PRED |
| 9 | First_Plan_Then_Evaluate_Multi-Target_Planning_With_Post-Planning_Success_Evaluation_Improves_Learning-Based_Grasping_Pipelines.pdf | 20260821__First_Plan_Then_Evaluate_Multi-Target_Planning_With_Post-Planning_Success_Evaluation_Improves_Learning-Based_Grasping_Pipelines.txt | OK, FULL | SEL |
| 10 | Grasping_a_Handful_Sequential_Multi-Object_Dexterous_Grasp_Generation.pdf | 20260821__Grasping_a_Handful_Sequential_Multi-Object_Dexterous_Grasp_Generation.txt | OK, FULL | CLU (Allegro-DoF-subset mechanism; no jaw analogue) |
| 11 | mathcalDmathcalR_mathcalO_Grasp_A_Unified_Representation_of_Robot_and_Object_Interaction_for_Cross-Embodiment_Dexterous_Grasping.pdf | 20260821__mathcalDmathcalR_mathcalO_Grasp_A_Unified_Representation_of_Robot_and_Object_Interaction_for_Cross-Embodiment_Dexterous_Grasping.txt | OK, FULL | CLU (cross-embodiment dexterous; jaw limited) |
| 12 | Toward_a_Multi-Embodied_Grasping_Agent.pdf | 20260821__Toward_a_Multi-Embodied_Grasping_Agent.txt | OK, FULL | CLU |

## `20260828-移动抓取/` (3)

| # | PDF file | extraction file | status | cluster |
|---|---|---|---|---|
| 13 | An_Architecture_for_Reactive_Mobile_Manipulation_On-The-Move.pdf | 20260828-移动抓取__An_Architecture_for_Reactive_Mobile_Manipulation_On-The-Move.txt | OK, FULL | MOB (analogical only) |
| 14 | Continuous_Mobile_Manipulation_for_Wheeled_Humanoid_Robots_via_Head-Mounted_Egocentric_Vision.pdf | 20260828-移动抓取__Continuous_Mobile_Manipulation_for_Wheeled_Humanoid_Robots_via_Head-Mounted_Egocentric_Vision.txt | OK, FULL | MOB (analogical only) |
| 15 | Reactive_and_Decoupled_Control_of_Mobile_Manipulators_via_Spatially_Modulated_Velocity_Fields.pdf | 20260828-移动抓取__Reactive_and_Decoupled_Control_of_Mobile_Manipulators_via_Spatially_Modulated_Velocity_Fields.txt | OK, FULL | MOB (closest of the three to the catch loop) |

## `20260902-动态抓取/` (1)

| # | PDF file | extraction file | status | cluster |
|---|---|---|---|---|
| 16 | Multi-fingered Hand Grasps with Visuo-Tactile Fusion via Multi-Agent Deep.pdf | 20260902-动态抓取__Multi-fingered Hand Grasps with Visuo-Tactile Fusion via Multi-Agent Deep.txt | OK, FULL | FRC (multi-finger; jaw-transfer limited) |

## `20260910扩散策略相关/` (4)

| # | PDF file | extraction file | status | cluster |
|---|---|---|---|---|
| 17 | 20_Reactive_Diffusion_Policy_S.pdf | 20260910扩散策略相关__20_Reactive_Diffusion_Policy_S.txt | OK, FULL | ACT/FRC (slow latent DP + fast tactile reflex) |
| 18 | ABSTRACTING ROBOT MANIPULATION SKILLS VIA.pdf | 20260910扩散策略相关__ABSTRACTING ROBOT MANIPULATION SKILLS VIA.txt | OK, FULL, DUP (pair: #22, identical basename) | MOE |
| 19 | Semantically Structured Mixture-of-Experts for Compositional Robotic Manipulation.pdf | 20260910扩散策略相关__Semantically Structured Mixture-of-Experts for Compositional Robotic Manipulation.txt | OK, FULL, DUP (pair: #2) | MOE |
| 20 | T-Rex Tactile-Reactive Dexterous Manipulation.pdf | 20260910扩散策略相关__T-Rex Tactile-Reactive Dexterous Manipulation.txt | OK, FULL | FRC (variable-rate MoT: slow action + fast tactile expert) |

## `20260928/` (19)

| # | PDF file | extraction file | status | cluster |
|---|---|---|---|---|
| 21 | 17891-AAAI26.ZouG-IR.pdf (**D²PPO**; identity only recoverable from extraction content) | 20260928__17891-AAAI26.ZouG-IR.txt | OK, FULL | RL |
| 22 | ABSTRACTING ROBOT MANIPULATION SKILLS VIA.pdf | 20260928__ABSTRACTING ROBOT MANIPULATION SKILLS VIA.txt | OK, FULL, DUP (pair: #18) | MOE |
| 23 | DemoDiffusion_One-Shot_Human_Imitation_Using_Pre-Trained_Diffusion_Policy.pdf | 20260928__DemoDiffusion_One-Shot_Human_Imitation_Using_Pre-Trained_Diffusion_Policy.txt | OK, FULL | RL |
| 24 | Flexible_Multitask_Learning_With_Factorized_Diffusion_Policy.pdf | 20260928__Flexible_Multitask_Learning_With_Factorized_Diffusion_Policy.txt | OK, FULL | MOE |
| 25 | FLOWRL A Taxonomy and Modular Framework for.pdf | 20260928__FLOWRL A Taxonomy and Modular Framework for.txt | OK, FULL | RL |
| 26 | ICLR-2026-improving-reasoning-for-diffusion-language-models-via-group-diffusion-policy-optimization-Paper-Conference.pdf | 20260928__ICLR-2026-improving-reasoning-for-diffusion-language-models-via-group-diffusion-policy-optimization-Paper-Conference.txt | OK, FULL | RL (diffusion *language* models — analogical only) |
| 27 | Learning When to Stop Prefix-Optimal Dynamic.pdf | 20260928__Learning When to Stop Prefix-Optimal Dynamic.txt | OK, FULL | ACT |
| 28 | NavDP_Learning_Sim-to-Real_Navigation_Diffusion_Policy_with_Privileged_Information_Guidance.pdf | 20260928__NavDP_Learning_Sim-to-Real_Navigation_Diffusion_Policy_with_Privileged_Information_Guidance.txt | OK, FULL | SIM |
| 29 | NeurIPS-2025-conditioning-matters-training-diffusion-policies-is-faster-than-you-think-Paper-Conference.pdf | 20260928__NeurIPS-2025-conditioning-matters-training-diffusion-policies-is-faster-than-you-think-Paper-Conference.txt | OK, FULL | GEN |
| 30 | NeurIPS-2025-dynaguide-steering-diffusion-polices-with-active-dynamic-guidance-Paper-Conference.pdf | 20260928__NeurIPS-2025-dynaguide-steering-diffusion-polices-with-active-dynamic-guidance-Paper-Conference.txt | OK, FULL | ACT ("polices" typo is in the original filename) |
| 31 | NeurIPS-2025-genpo-generative-diffusion-models-meet-on-policy-reinforcement-learning-Paper-Conference.pdf | 20260928__NeurIPS-2025-genpo-generative-diffusion-models-meet-on-policy-reinforcement-learning-Paper-Conference.txt | OK, FULL | RL |
| 32 | NeurIPS-2025-two-steps-diffusion-policy-for-robotic-manipulation-via-genetic-denoising-Paper-Conference.pdf | 20260928__NeurIPS-2025-two-steps-diffusion-policy-for-robotic-manipulation-via-genetic-denoising-Paper-Conference.txt | OK, FULL | ACT |
| 33 | ObstaDiff Generalizable Diffusion Policy Learning.pdf | 20260928__ObstaDiff Generalizable Diffusion Policy Learning.txt | OK, FULL | CLU (target–obstacle–background representation; jaw-compatible) |
| 34 | PPGuide Steering Diffusion Policies with.pdf | 20260928__PPGuide Steering Diffusion Policies with.txt | OK, FULL | ACT |
| 35 | PolicyTrim Boosting Intrinsic Policy Efficiency of.pdf | 20260928__PolicyTrim Boosting Intrinsic Policy Efficiency of.txt | OK, FULL | ACT (lives in `20260928/`, not `20261009-VLA/`) |
| 36 | Sparse ActionGen Accelerating Diffusion Policy with Real-time Pruning.pdf | 20260928__Sparse ActionGen Accelerating Diffusion Policy with Real-time Pruning.txt | OK, FULL | ACT (lives in `20260928/`, not `20261009-VLA/`) |
| 37 | Tactile-Conditioned_Diffusion_Policy_for_Force-Aware_Robotic_Manipulation.pdf | 20260928__Tactile-Conditioned_Diffusion_Policy_for_Force-Aware_Robotic_Manipulation.txt | OK, FULL | FRC (force in observation *and* predicted grip-force in action) |
| 38 | Time-Unified Diffusion Policy with action discrimination for robotic.pdf | 20260928__Time-Unified Diffusion Policy with action discrimination for robotic.txt | OK, FULL | ACT |
| 39 | π0.7a Steerable Generalist Robotic Foundation.pdf | 20260928__π0.7a Steerable Generalist Robotic Foundation.txt | OK, FULL, DUP (pair: #5) | GEN |

## `20261009-VLA/` (33)

| # | PDF file | extraction file | status | cluster |
|---|---|---|---|---|
| 40 | 03702-AAAI26 MoLe-VLA Dynamic Layer-skipping Vision Language Action Model via.pdf | 20261009-VLA__03702-AAAI26 MoLe-VLA Dynamic Layer-skipping Vision Language Action Model via.txt | OK, FULL | ACT (`03702-AAAI26` is a submission prefix) |
| 41 | AR-VLA Autoregressive Action Expert for.pdf | 20261009-VLA__AR-VLA Autoregressive Action Expert for.txt | OK, FULL | ACT |
| 42 | DAM-VLA A Dynamic Action Model-Based Vision-Language-Action.pdf | 20261009-VLA__DAM-VLA A Dynamic Action Model-Based Vision-Language-Action.txt | OK, FULL | PRED |
| 43 | Deltoris Enabling Real-time VLA Inference in Embodied AI via.pdf | 20261009-VLA__Deltoris Enabling Real-time VLA Inference in Embodied AI via.txt | OK, FULL | ACT (algorithm–hardware co-design; headline speedup needs their ASIC) |
| 44 | DyQ-VLA DYNAMIC QUANTIZATION AND COMPEN-.pdf | 20261009-VLA__DyQ-VLA DYNAMIC QUANTIZATION AND COMPEN-.txt | OK, FULL | ACT (filename itself truncated) |
| 45 | DySL-VLA Efficient Vision-Language-Action Model Inference via.pdf | 20261009-VLA__DySL-VLA Efficient Vision-Language-Action Model Inference via.txt | OK, FULL | ACT |
| 46 | DynamicVLA A Vision-Language-Action Model for Dynamic Object Manipulation.pdf | 20261009-VLA__DynamicVLA A Vision-Language-Action Model for Dynamic Object Manipulation.txt | OK, FULL, DUP (pair: #8, full title) | ACT/PRED |
| 47 | EmbodiedSkills A Unified Framework for.pdf | 20261009-VLA__EmbodiedSkills A Unified Framework for.txt | OK, FULL | GEN |
| 48 | ExpReS-VLA_Specializing_Vision-Language-Action_Models_Through_Experience_Replay_and_Retrieval.pdf (+ byte-duplicate `... (1).pdf`) | 20261009-VLA__ExpReS-VLA_Specializing_Vision-Language-Action_Models_Through_Experience_Replay_and_Retrieval.txt (+ `... (1).txt`) | OK, FULL, DUP (byte-duplicate pair) | GEN |
| 49 | FlashVLA Streaming Action Decoding for.pdf | 20261009-VLA__FlashVLA Streaming Action Decoding for.txt | OK, FULL | ACT (staggered-noise streaming buffer; no explicit future-state predictor) |
| 50 | ForeTime-VLA Causal Future-Token Distillation from a World Action.pdf | 20261009-VLA__ForeTime-VLA Causal Future-Token Distillation from a World Action.txt | OK, FULL | PRED (frozen teacher → 64-D future code; conveyor-belt data) |
| 51 | Grasp_to_Act_Dexterous_Grasping_for_Tool_Use_in_Dynamic_Settings.pdf | 20261009-VLA__Grasp_to_Act_Dexterous_Grasping_for_Tool_Use_in_Dynamic_Settings.txt | OK, FULL | CLU (dexterous tool-use; jaw-transfer limited) |
| 52 | ICLR-2026-simplevla-rl-scaling-vla-training-via-reinforcement-learning-Paper-Conference.pdf | 20261009-VLA__ICLR-2026-simplevla-rl-scaling-vla-training-via-reinforcement-learning-Paper-Conference.txt | OK, FULL | RL (online outcome-driven RL recipe; R9 used AWR-RWR instead) |
| 53 | IMLE-VLA Fast Single-Step Action Generation for.pdf | 20261009-VLA__IMLE-VLA Fast Single-Step Action Generation for.txt | OK, FULL | ACT |
| 54 | Intercepting the Future Latent-Space Predictive.pdf (**AHEAD**; filename is a title fragment) | 20261009-VLA__Intercepting the Future Latent-Space Predictive.txt | OK, FULL | PRED (frozen-VLA wrapper + uncertainty-halting horizon) |
| 55 | Lin_HiF-VLA_Hindsight_Insight_and_Foresight_through_Motion_Representation_for_Vision-Language-Action_CVPR_2026_paper.pdf | 20261009-VLA__Lin_HiF-VLA_Hindsight_Insight_and_Foresight_through_Motion_Representation_for_Vision-Language-Action_CVPR_2026_paper.txt | OK, FULL | PRED |
| 56 | MA-VLA Multi-arm Vision-Language-Action Model for Collaboration and Compositional Generalization.pdf | 20261009-VLA__MA-VLA Multi-arm Vision-Language-Action Model for Collaboration and Compositional Generalization.txt | OK, FULL (paper body verified present inside the 698-page proceedings-volume PDF) | BI (full text read; verdict NO-GO — contradicts the scripted-coordination/station-fixed decisions) |
| 57 | MAP-VLA_Memory-Augmented_Prompting_for_Vision-Language-Action_Model_in_Robotic_Manipulation.pdf | 20261009-VLA__MAP-VLA_Memory-Augmented_Prompting_for_Vision-Language-Action_Model_in_Robotic_Manipulation.txt | OK, FULL | GEN |
| 58 | NeurIPS-2025-fast-in-slow-a-dual-system-vla-model-unifying-fast-manipulation-within-slow-reasoning-Paper-Conference.pdf | 20261009-VLA__NeurIPS-2025-fast-in-slow-a-dual-system-vla-model-unifying-fast-manipulation-within-slow-reasoning-Paper-Conference.txt | OK, FULL | ACT (parameter-shared dual system; our hybrid is already a dual system by construction) |
| 59 | NeurIPS-2025-forcevla-enhancing-vla-models-with-a-force-aware-moe-for-contact-rich-manipulation-Paper-Conference.pdf | 20261009-VLA__NeurIPS-2025-forcevla-enhancing-vla-models-with-a-force-aware-moe-for-contact-rich-manipulation-Paper-Conference.txt | OK, FULL | FRC (phase-aware force MoE routing during decoding) |
| 60 | NeurIPS-2025-vla-cache-efficient-vision-language-action-manipulation-via-adaptive-token-caching-Paper-Conference.pdf | 20261009-VLA__NeurIPS-2025-vla-cache-efficient-vision-language-action-manipulation-via-adaptive-token-caching-Paper-Conference.txt | OK, FULL | ACT |
| 61 | Ni_SwiftVLA_Unlocking_Spatiotemporal_Dynamics_for_Lightweight_VLA_Models_at_Minimal_CVPR_2026_paper.pdf | 20261009-VLA__Ni_SwiftVLA_Unlocking_Spatiotemporal_Dynamics_for_Lightweight_VLA_Models_at_Minimal_CVPR_2026_paper.txt | OK, FULL | ACT |
| 62 | On-the-Fly VLA Adaptation via Test-Time Reinforcement Learning.pdf | 20261009-VLA__On-the-Fly VLA Adaptation via Test-Time Reinforcement Learning.txt | OK, FULL | RL |
| 63 | Qian_GeoPredict_Leveraging_Predictive_Kinematics_and_3D_Gaussian_Geometry_for_Precise_CVPR_2026_paper.pdf | 20261009-VLA__Qian_GeoPredict_Leveraging_Predictive_Kinematics_and_3D_Gaussian_Geometry_for_Precise_CVPR_2026_paper.txt | OK, FULL | GEO |
| 64 | Reactive grasp controller for dynamic grasping of moving objects.pdf | 20261009-VLA__Reactive grasp controller for dynamic grasping of moving objects.txt | OK, FULL | PRED (per-tick path reshaping + 1 kHz velocity commands; scripted-catch analogue) |
| 65 | Realtime-VLA V2 Learning to Run VLAs Fast, Smooth, and Accurate.pdf | 20261009-VLA__Realtime-VLA V2 Learning to Run VLAs Fast, Smooth, and Accurate.txt | OK, FULL | ACT |
| 66 | Sentinel-VLA A Metacognitive VLA Model with Active Status Monitoring for.pdf | 20261009-VLA__Sentinel-VLA A Metacognitive VLA Model with Active Status Monitoring for.txt | OK, FULL | SEL (attempt-granularity monitor + recovery; not an in-window guard) |
| 67 | SkipVLA Skipping VLA Steps with Classical Planning.pdf | 20261009-VLA__SkipVLA Skipping VLA Steps with Classical Planning.txt | OK, FULL | ACT (classical planner for transit, VLA for contact; self-supervised hover targets) |
| 68 | Song-2026-Fast-dvla-accelerating-discrete-dif (1).pdf | 20261009-VLA__Song-2026-Fast-dvla-accelerating-discrete-dif (1).txt | OK, FULL | ACT (discrete-token caveat; no second copy present) |
| 69 | Towards_Deploying_VLA_Without_Fine-Tuning_Plug-and-Play_Inference-Time_VLA_Policy_Steering_via_Embodied_Evolutionary_Diffusion.pdf | 20261009-VLA__Towards_Deploying_VLA_Without_Fine-Tuning_Plug-and-Play_Inference-Time_VLA_Policy_Steering_via_Embodied_Evolutionary_Diffusion.txt | OK, FULL | ACT |
| 70 | Visual Intermediate.pdf | 20261009-VLA__Visual Intermediate.txt | OK, FULL | ACT |
| 71 | VLA-Touch_Enhancing_Vision-Language-Action_Model_With_Dual-Level_Tactile_Feedback.pdf | 20261009-VLA__VLA-Touch_Enhancing_Vision-Language-Action_Model_With_Dual-Level_Tactile_Feedback.txt | OK, FULL | FRC (dual levels without fine-tuning the base VLA) |

## `20261010-DynamicVLA/` (12)

| # | PDF file | extraction file | status | cluster |
|---|---|---|---|---|
| 72 | A forward-reflected-backward method with adaptive stepsize for .pdf | 20261010-DynamicVLA__A forward-reflected-backward method with adaptive stepsize for .txt | OK, FULL | FRC (real-time grasp-force optimization; filename truncated) |
| 73 | A soft gripper with an adaptive grasp control system allowing stable and.pdf | 20261010-DynamicVLA__A soft gripper with an adaptive grasp control system allowing stable and.txt | OK, FULL | NA (hardware paper; scenario-redesign class) |
| 74 | BiDexGrasp Coordinated Bimanual Dexterous.pdf | 20261010-DynamicVLA__BiDexGrasp Coordinated Bimanual Dexterous.txt | OK, FULL | BI (filename truncated; bimanual dataset at 30–80 cm tabletop scale — not this cell; coordination-module form only) |
| 75 | Differentiable_Particle_Optimization_for_Fast_Sequential_Manipulation.pdf (**SPaSM**) | 20261010-DynamicVLA__Differentiable_Particle_Optimization_for_Fast_Sequential_Manipulation.txt | OK, FULL | SEL (GPU-parallel joint placement + trajectory; needs a given action skeleton) |
| 76 | Eye-to-action Real-time robotic grasping via lightweight gaze estimation.pdf | 20261010-DynamicVLA__Eye-to-action Real-time robotic grasping via lightweight gaze estimation.txt | OK, FULL | NA (human-in-the-loop gaze; no operator in this cell) |
| 77 | Fast Generative Grasping via Lie Group-Constrained MeanFlow.pdf | 20261010-DynamicVLA__Fast Generative Grasping via Lie Group-Constrained MeanFlow.txt | OK, FULL | CLU (1-NFE grasp *synthesis*, not a latency lever for the 4.59M policy) |
| 78 | HybridFlow A 2-NFE Generative Policy for Real-Time Robotic Manipulation.pdf | 20261010-DynamicVLA__HybridFlow A 2-NFE Generative Policy for Real-Time Robotic Manipulation.txt | OK, FULL | ACT (MeanFlow proposal + refine; no distillation) |
| 79 | Learning_Approach_to_Optimal_Grasping_Planning_Using_Vision-Based_Tactile_Perception.pdf | 20261010-DynamicVLA__Learning_Approach_to_Optimal_Grasping_Planning_Using_Vision-Based_Tactile_Perception.txt | OK, FULL | FRC |
| 80 | NeurIPS-2025-fast-monte-carlo-tree-diffusion-100-speedup-via-parallel-and-sparse-planning-Paper-Conference.pdf (**Fast-MCTD**) | 20261010-DynamicVLA__NeurIPS-2025-fast-monte-carlo-tree-diffusion-100-speedup-via-parallel-and-sparse-planning-Paper-Conference.txt | OK, FULL | SEL (long-horizon planning *search*, not action-chunk latency) |
| 81 | ShapeGrasp Simultaneous Visuo-Haptic Shape Completion and Grasping for Improved Robot Manipulation.pdf | 20261010-DynamicVLA__ShapeGrasp Simultaneous Visuo-Haptic Shape Completion and Grasping for Improved Robot Manipulation.txt | OK, FULL | FRC (shape side is closed by the D screen — do not re-propose) |
| 82 | SPGrasp_Spatiotemporal_Prompt-Driven_Grasp_Synthesis_in_Dynamic_Scenes.pdf | 20261010-DynamicVLA__SPGrasp_Spatiotemporal_Prompt-Driven_Grasp_Synthesis_in_Dynamic_Scenes.txt | OK, FULL | GEO (promptable spatiotemporal *tracking* through clutter; perception-side companion) |
| 83 | Whole-Body Coordination for Dynamic Object Grasping with Legged Manipulators.pdf | 20261010-DynamicVLA__Whole-Body Coordination for Dynamic Object Grasping with Legged Manipulators.txt | OK, FULL | MOB (legged-mobile embodiment mismatch) |
