# KNOWLEDGE BASE: the `Paper/论文/` library vs this project's measured state

Built 2026-10-15 (R-PLAN2 phase P2). 84 papers extracted (`Paper/text/`, `DIGEST_all.txt`),
the library stays local (656 MB); this file + the digest are the durable record.
**The ranking is against OUR measured boundaries** (AGENTS.md section 2 + `logs/w8`,
`logs/r6`, `logs/r9`, `logs/r10`, `logs/r11`), not a generic survey. The end of the file
lists what is already measured negative here so the shortlist does not repeat it.

The project's measured state in one paragraph: a bimanual fruit-sorting cell; the belt never
stops; each arm owns a station; the pick is a scripted never-stop dynamic catch (the hand
descends at the station and the fruit arrives under it); pure grade routing (left A, right B,
C passes); a 4.59M diffusion policy drives the close in the hybrid interface. The measured
bottleneck map: (1) the interval is selection+arrival-wait bound (44-45% of the interval; the
park-gate lever took the other half); (2) the carry escape is a **mid-lift one-sided loaded
slide** with a **0-2 tick reaction window** (the command/squeeze side and the shape side both
measured closed; the drive-saturated pinch); (3) the policy's left deficit was pre-contact
acquisition (fixed by the R7-A x-edge refusal); (4) the visual ablation is **sub-noise** - the
policy is state-conditioned and the 5th "target mask" channel is empty in the data; (5) any
rate claim needs the N=5 paired protocol.

## 1. The ranked table (method -> our bottleneck -> expected movement -> cost/risk -> source)

Rank = the expected movement per unit cost/risk against the map above. Paths are relative to
this file (`../../Paper/论文/`).

### Rank 1-4: the fast action closed loop + the force-aware conditioning (the owner's #3)

| # | paper | our bottleneck | expected movement | cost/risk | source |
| --- | --- | --- | --- | --- | --- |
| 1 | **FlashVLA: Streaming Action Decoding for Fast and Asynchronous VLA Inference** (2608.27384) | the fast action loop; our ablation says vision is sub-noise and the policy is state-conditioned | stream the action chunks asynchronously; bridge the seam with the fresh **state/proprio** stream while the heavy **vision** path is cached/skipped - our own measurement says the state dominates (5-6x noise) | S-M / the async seam can double-apply correction; the policy is 4.59M so the latency is small already - measure the seam gain | `20261009-VLA/FlashVLA Streaming Action Decoding for...pdf` |
| 2 | **ForceVLA: Enhancing VLA with a Force-aware MoE for contact-rich manipulation** (NeurIPS-2025) | the close/acquire class; the "force real-time adjustment" (owner #3) | a force-conditioned MoE expert on our existing both-finger `ft` stream (already logged) - the command-side squeeze family is closed, so the conditioning side is the open one | M / needs retraining; the tactile stream is sim-side and could shift the domain (see the sim-to-real prep) | `20261009-VLA/NeurIPS-2025-forcevla-enhancing-vla-models-with-a-force-aware-moe-for-contact-rich-manipulation...pdf` |
| 3 | **Tactile-Conditioned Diffusion Policy for Force-Aware Robotic Manipulation** (ICRA 2026) | the same - the force-aware close | the force-conditioned policy (the tactile token) on the close/carry window; the mechanism readout = the `clean_slip` onset force/geometry | M / the retraining cost; the class may be the mid-lift slide which the close cannot prevent (R11-B's conclusion) | `20260928__Tactile-Conditioned_Diffusion_Policy_for_Force-Aware_Robotic_Manipulation.txt` |
| 4 | **VLA-Touch: Enhancing VLA with Dual-Level Tactile Feedback** (RA-L 2026) | the same - the two-level (fast force + slow tactile) | our both-finger force + the relative-pose key as the two levels; the fast level is the closed loop the papers call "force real-time adjustment" | S-M / the policy change; verify against the 0-2 tick window finding | `20261009-VLA/VLA-Touch_Enhancing_Vision-Language-Action_Model_With_Dual-Level_Tactile_Feedback.txt` |

### Rank 5-8: the dynamic interception + the cluttered-sheet policies (the owner's core scenario)

| # | paper | our bottleneck | expected movement | cost/risk | source |
| --- | --- | --- | --- | --- | --- |
| 5 | **ForeTime-VLA: Causal Future-Token Distillation from a World Action Model for Conveyor-Belt Manipulation** | the dynamic catch's handover; our reach-anywhere interception (the map + the fixed point) | replace/augment the fixed-point prediction with a learned predictive model on the belt state (which we have exactly: the encoder + the per-fruit poses) | M / distillation; our scripted interception already reads a +3.4 mm descent-end error - the headroom is the setup model's missing x-term | `20261009-VLA/ForeTime-VLA Causal Future-Token Distillation from a World Action.txt` |
| 6 | **Intercepting the Future: Latent-Space Predictive World Model for Dynamic VLA Manipulation** (CMU) | the same - the interception timing | the latent future prediction for the handover tick (our measured actuator: the setup 1.36-7.68 s vs the 0.9 s lead) | M / same | `20261009-VLA/Intercepting the Future Latent-Space Predictive.txt` |
| 7 | **DexSinGrasp: Learning a Unified Policy for Dexterous Object Singulation and Grasping in Densely Cluttered Environments** (RA-L) | the scattered dense sheet (the owner's #1: the supply-side density) | the singulation-first policy for the sheet: separate-then-grasp vs our nearest-usable selection; the direct measure = the acquired fidelity in the dense sheet | M-L / a new skill + data; the dexterous hand is not ours (a 2-finger jaw) - the transferable part is the singulation policy form | `20260821__DexSinGrasp_Learning_a_Unified_Policy_for_Dexterous_Object_Singulation_and_Grasping_in_Densely_Cluttered_Environments.txt` |
| 8 | **Reactive grasp controller for dynamic grasping of moving objects** (RAS 2026) | the never-stop catch | the reactive (closed-loop) grasp controller form - a scripted win for the catch's close loop rather than a policy | S-M / the contact model differs; our close is a force servo already | `20261009-VLA__Reactive grasp controller for dynamic grasping of moving objects.txt` |

### Rank 9-12: the bimanual + the multi-object forms

| # | paper | our bottleneck | expected movement | cost/risk | source |
| --- | --- | --- | --- | --- | --- |
| 9 | **MA-VLA: Multi-arm VLA Model for Collaboration and Compositional Generalization** (ECCV 2026) | the two-line coordination (currently scripted) | ONE policy coordinating the two arms/stations - replaces the scripted scheduler's park/gate/separation | M-L / the whole coordination stack; the two-line is opt-in and its scripted form is measured | `20261009-VLA__MA-VLA Multi-arm Vision-Language-Action Model for Collaboration...txt` |
| 10 | **BiDexGrasp: Coordinated Bimanual Dexterous Grasps across Object Geometries** | the two-arm grasp (the shared payload class) | coordinated bimanual grasps when one arm needs help (the biggest fruit) - our carry escape is one-sided | M / dexterous vs jaw | `20261010-DynamicVLA__BiDexGrasp Coordinated Bimanual Dexterous.txt` |
| 11 | **SeqGrasp / Grasping a Handful: sequential multi-object grasp generation** (RA-L) | the interval (the per-attempt cost) | multi-object grasps (two fruit at once) - the interval per fruit halves if the carry class permits | M / the payload interaction; our carry margin is drive-saturated | `20260821__Grasping_a_Handful_Sequential_Multi-Object_Dexterous_Grasp_Generation.txt` |
| 12 | **First Plan Then Evaluate: Multi-Target Planning With Post-Planning Success Evaluation** (RA-L) | the selection (which fruit to take) | a post-planning success evaluation for the candidate aim (our `feasible` flag is exactly this, geometric only) | S / scripted | `.20260821__First_Plan_Then_Evaluate...txt` |

### Rank 13-18: the inference/real-time family (the fast loop's budget) + the sim-to-real

| # | paper | our bottleneck | expected movement | cost/risk | source |
| --- | --- | --- | --- | --- | --- |
| 13 | **HybridFlow: A 2-NFE Generative Policy for Real-Time Manipulation** (2602.13718) | the policy's inference latency in the fast loop | 2 function evaluations (vs our DDIM-16) - the closed-loop budget | M / the accuracy/latency trade; our latency is not the binding term (the interval is arrival-bound) - only matters inside combo A | `20261010-DynamicVLA__HybridFlow A 2-NFE Generative Policy...pdf` |
| 14 | **Fast Monte Carlo Tree Diffusion: 100x Speedup via Parallel Sparse Planning** (NeurIPS-2025) | the same | the parallel/sparse denoising | M | `20261010-DynamicVLA__NeurIPS-2025-fast-monte-carlo-tree-diffusion...pdf` |
| 15 | **Deltoris: real-time VLA inference via bit-level sparsity + speculative inference** | the same | the speculative decoding for the action expert | M | `20261009-VLA__Deltoris Enabling Real-time VLA Inference...txt` |
| 16 | **MoLe-VLA / DySL-VLA / PolicyTrim / Sparse ActionGen / VLA-Cache / SkipVLA** | the same | the layer-skip / token-cache / pruning family | S each / the degra | `20261009-VLA/` |
| 17 | **Fast-in-Slow: A Dual-System VLA Unifying Fast Manipulation within Slow Reasoning** (NeurIPS-2025) | our hybrid architecture (the scripted fast + the policy slow) | the dual-system timing unification - the fast loop's corrections inside the slow loop's cadence | M / the architecture | `20261009-VLA__NeurIPS-2025-fast-in-slow-a-dual-system-vla-model...pdf` |
| 18 | **NavDP: sim-to-real navigation diffusion policy with privileged information guidance** | the sim-to-real prep | the privileged-information guidance for the sim-to-real transfer; the sim-to-real contact screen (the R10-B design: ~1.5 h) | S-M | `20260928__NavDP_Learning_Sim-to-Real_Navigation_Diffusion_Policy...txt` |

## 2. The clusters (the rest of the library, one line each)

- **Inference acceleration (real-time family)**: `20260928__Sparse ActionGen`, `PPGuide`,
  `DynaGuide`, `Learning When to Stop (prefix-optimal dynamic DP)`, `Two-Steps DP via Genetic
  Denoising`, `Fast-dVLA`, `IMLE-VLA`, `Realtime-VLA V2`, `FabriVLA (conformal chunk
  uncertainty)`, `Conditioning Matters (training is faster than you think)`, `SkipVLA`,
  `VLA-Cache`, `MoLe-VLA`, `DySL-VLA`, `PolicyTrim`, `Fast Generative Grasping via Lie
  Group-Constrained MeanFlow`, `Eye-to-action`.
- **Tactile / force control**: `T-Rex`, `A forward-reflected-backward method ... real-time
  grasping force optimization`, `A soft gripper with an adaptive grasp control system`,
  `Multi-fingered Hand Grasps with Visuo-Tactile Fusion via Multi-Agent DRL`, `Learning
  Approach to Optimal Grasping Planning Using Vision-Based Tactile Perception`, `ShapeGrasp`,
  `Grasp to Act`.
- **Clutter / singulation / dexterous**: `D(R,O) Grasp`, `Toward a Multi-Embodied Grasping
  Agent`, `SPGrasp (dynamic scenes)`, `ObstaDiff (obstacle-aware)`, `Differentiable Particle
  Optimization for Fast Sequential Manipulation`, `Whole-Body Coordination for Dynamic Object
  Grasping`.
- **RL / post-training**: `SimpleVLA-RL`, `GenPO (on-policy RL)`, `D2PPO (dispersive loss)`,
  `FLOWRL`, `On-the-Fly VLA Adaptation via Test-Time RL`, `Group Diffusion Policy
  Optimization`.
- **MoE / multitask / composition**: `Semantically Structured MoE (x2 copies)`, `Abstracting
  Robot Manipulation Skills via MoE Diffusion Policies (x2)`, `Flexible Multitask Learning
  With Factorized Diffusion Policy`, `DemoDiffusion (one-shot)`, `MAP-VLA (memory-augmented)`,
  `EmbodiedSkills`, `Sentinel-VLA (metacognitive error recovery)`, `HiF-VLA`, `SwiftVLA
  (spatiotemporal dynamics)`, `GeoPredict`, `Visual Intermediate Reasoning`,
  `Collaborative Object Search and Grasp via VL-Guided RL`, `pi0.7 (steerable generalist)`,
  `VGGT (visual geometry)`, `SHELLS (3D head reconstruction - not applicable)`,
  `Time-Unified Diffusion Policy with action discrimination`,
  `ExpReS-VLA (experience replay and retrieval)`, `AR-VLA (autoregressive action expert)`,
  `DyQ-VLA`, `DAM-VLA`, `An Architecture for Reactive Mobile Manipulation On-The-Move`,
  `Continuous Mobile Manipulation for Wheeled Humanoid Robots`, `Reactive and Decoupled
  Control ... Spatially Modulated Velocity Fields`, `Tail`/leftovers noted in
  `Paper/text/DIGEST_all.txt`.

## 3. The shortlist for P3 (the combinations to implement, per the owner's directives)

The owner's goal: **bimanual dynamic fast sorting under scattered/unordered supply + fast
action closed loops + force real-time adjustment**; combinations, bold with evidence, do not
stop at the first performance drop.

- **Combo A (the fast action closed loop)**: FlashVLA-style **asynchronous streaming action
  decoding** where the seam is bridged by the fresh **state/proprio+force** stream and the
  **vision** path is cached/skipped (justified by our own ablation: the vision is sub-noise,
  the state is 5-6x noise, the mask channel is empty). Endpoint: the direct N=5 paired +
  the seam-quality mechanism readout. Kill criteria: the paired class count or the
  new-reason set worsens.
- **Combo B (the force real-time adjustment)**: **CORRECTED 2026-10-15** - the force channel is
  **already in the policy's observation**: the 25-D proprio is 22 joint positions + the finger
  opening + **the two tactile forces** (`src/fruit_sorting/rl_env.py`: "proprioception is all 22
  joint positions + the finger opening + the two tactile forces (25-D)"). So the papers' "feed the
  force to the policy" premise is satisfied by construction and the residual contribution is
  narrower: **use the force as an adaptation signal, not as an input channel** - a force-conditioned
  MoE expert (ForceVLA) that switches grip behaviour when the force reads low, or a dual-rate
  design (a fast force reflex at the control rate under the slow chunked policy, VLA-Touch's dual
  levels). **Both of those are bounded by our own measurements**: W5 read **no detection/react
  window** (the carry losses keep 2-8 N on one finger; where the force collapses the payload is out
  within 0-3 ticks) and R11-B read the **pre-onset load path is not the discriminator** (the
  payload is held to 0.5 mm through the window; the escape is a *mid-lift* one-sided loaded slide).
  So Combo B's live form is: the conditioning must **shift the load path before the window**, not
  react inside it - which is exactly what the conditioning-side papers claim and what we have not
  yet tested (our earlier tests were all *reaction* levers). Endpoint: the carried class +
  `clean_slip` under the N=5 protocol; the mechanism readout = the onset force/geometry.
- **Combo C (the scattered dense sheet)**: a **singulation-first + multi-arm coordination**
  policy (DexSinGrasp's separation + MA-VLA's coordination) trained on the dense sheet
  collected on the two-line (the W7-C store exists; the density lever is P1's). Endpoint: the
  acquired fidelity + the two-line placed/min under the N=5 protocol.
- **Combo D (the interception)**: the **predictive interception** (ForeTime/Intercepting)
  over the belt state we already have, replacing the fixed-point's missing x-term; the
  reach-anywhere map is the constraint set. Endpoint: the handover-time distribution + the
  carry class on the reach branch.
- **Combo E (the budget)**: the inference acceleration (HybridFlow 2-NFE / streaming) ONLY
  if combo A makes the inference latency binding - our measured interval is arrival-bound,
  so this is a supporting lever, not a primary.

Each combo is default-off, scoped (direct or two-line), pre-registered with a numeric
criterion + kill criteria, and evaluated with the N=5 paired protocol + the byte-level
no-harm.

## 4. Already measured negative here - do not re-propose

RTC (-20 pt), VLASH (-31 pt), A2C2 (-20 pt), the event-triggered horizon (+1.3 pt, failed
N=5), GEM tracking (flat), verify-dwell/ramp-lift, the finger-face variants, the place
squeeze/wrist hold, the squeeze-side family (force/depth/relief - drive-saturated), the shape
side (the grip plane/cradle/station - the D screen), the reactive guards (p=0.109/0.312), the
two behaviour-cloning recollections (W7-C underpowered; W8-A p=1.0), AWR-clipped RWR-2
(p=0.5), the adaptive selection lead (bit-identical), the hot-arm residency (fires 4/18,
flat), the pre-onset load path knobs (stage-P 12/20 vs 13/18), the reach-anywhere adoption
(the acceptance 44% vs 90%). The papers in the inference-acceleration cluster are NOT yet
measured in combination (A+E) - that is the one open slot in the family.

## 5. Sources / provenance

`Paper/text/` = the pdftotext extraction of the first two pages of each PDF (84 files,
948 KB); `Paper/text/DIGEST_all.txt` = the title+opening digest used for this ranking. The
ranking, the clusters, the shortlist and the negative list are derived from the digest plus
the project's own measured record (AGENTS.md section 2 + logs/w8, logs/r6, logs/r9, logs/r10,
logs/r11). Papers whose first two pages did not expose an abstract are ranked by title only
and marked in the digest.
