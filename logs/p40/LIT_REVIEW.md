# Literature review: ForceDelta-VLA, Eka VFA, slip/grip-force control, sim-to-real grip force, and closed-loop action rate

**Prepared:** 2026-10-25 · **Scope:** external literature only; no simulator runs, no repo code changes.
**Reading convention:** every claim carries `(Title, Year — URL)`. Each section ends with a
**what is measured** vs **what is claimed** split. Items marked ⚠ could not be verified from a
primary source and are repeated in §7.

---

## 0. Identity in one line each

| Name | Identity |
| --- | --- |
| **ForceDelta-VLA** | A 2026 arXiv paper (Dong et al., Univ. Hamburg TAMS + TU Munich): a **correction-distillation** layer on top of a force-aware VLA. It learns a fast **force correction** and **delay correction** added to a slow reference action chunk. Nine real-robot tasks, 82.2 % mean success vs 54.4 % for ForceVLA. (ForceDelta-VLA, 2026 — https://arxiv.org/abs/2609.18242) |
| **Eka VFA** | **Eka Robotics** (Cambridge, MA; founded 2024 by Pulkit Agrawal and Tuomas Haarnoja): the company's **vision-force-action** model, a force-sensitive gripper plus a policy trained by large-scale RL in simulation. **No paper, no architecture disclosure, no benchmark.** All numbers are company claims. (Eka Robotics raises $150M…, 2026 — https://ekarobotics.com/blog/eka-robotics-raises-150m-to-build-superhuman-intelligence-for-the-physical-world) |

---

## 1. ForceDelta-VLA

### 1.1 What the work is

Paper: **"ForceDelta-VLA: Distilling Force-Conditioned Action Corrections for Contact-Rich
Manipulation"**, Ju Dong, Yu Fu, Jian Chen, Yimeng Liu, Haocheng Zhao, Lei Zhang, Kaixin Bai,
Liding Zhang, Diwen Zheng, Alois C. Knoll, Angela P. Schoellig, Jianwei Zhang. arXiv 2609.18242,
submitted 16 Sep 2026, 8 pages. (2026 — https://arxiv.org/abs/2609.18242; HTML full text
https://arxiv.org/html/2609.18242v1)

It builds directly on **ForceVLA** (Yu et al., 2025 — https://arxiv.org/abs/2505.22159), which is
both the teacher backbone and the main baseline. It cites a dense 2026 force-VLA literature:
ForceVLA2, TA-VLA, FAVLA, DAM-VLA, ImplicitRDP, PhaForce, FD-VLA, ForceMimic, CRAFT, FM-VLA.

### 1.2 The model, and what "force delta" actually means

**Architecture: three training stages, two run-time paths.**

1. **Stage 1 — temporal force-conditioned teacher.** A ForceVLA backbone whose *instantaneous*
   force embedding is replaced by a **FAVLA-style causal TCN over a force history**. Inputs:
   images `V_t`, language `L`, robot state `S_t` (TCP pose), and wrench history
   `F_t = {(s, w(s)) : t-T_F <= s <= t}` with `w(s) = [f(s); tau(s)] ∈ R^6` (end-effector force
   and torque, in the arm base frame). Output: an `H`-step action chunk relative to `S_t`.
2. **Stage 2 — learned force-agnostic reference mode.** The teacher is **frozen**; a learned
   missing-modality token `z_∅F` plus a rank-ρ adapter on the action expert's pose channels is
   trained so the same network can produce a *reference action* with **no force input**. This is
   the crux: unavailable force is distinguished from a measured zero force.
3. **Stage 3 — paired correction targets.** For the same cached visual–language prefix, state,
   and flow noise, the paper computes **two** teacher predictions: force-conditioned and
   force-agnostic. Their pose difference defines the **force correction target**
   `ΔA_force = P(A_cond) − P(A_ref)`. A second **delay target** compares the current
   force-agnostic prediction to the stored, older reference, including a reference-state
   alignment term `Γ(S_t, S_k)`.

At run time the command is **exactly a residual/delta composition**:

```
P(A_cmd) = P(A_ref) + ΔÂ_force + ΔÂ_delay
```

where corrections are predicted in normalized **pose coordinates** (translation + continuous 6D
rotation, Gram–Schmidt projected), and **the gripper command is taken from the reference action
unchanged** — the learned corrections modify pose only. (ForceDelta-VLA, 2026,
§III-A eq. 1 — https://arxiv.org/html/2609.18242v1)

**So "force delta" is two things at once, and the distinction matters for transfer:**

* the **signal** is a *delta action*: a force-conditioned additive correction to a reference pose
  action, not a force input token appended to the observation, and not a force setpoint;
* the **supervision** is a *difference of two teacher predictions*, which is how the method gets
  explicit correction labels out of ordinary demonstrations that contain only the final action.

The fast student reads: pooled cached task context, a causal force encoding of the recent wrench
history, current state, the interpolated reference action segment, and timing features (cache age,
interpolation phase). A **shared attention module with a learned query** is evaluated twice — once
with all tokens (force head), once with the force token masked (delay head) — and two heads emit
`K`-step corrections. The mask prevents the delay output from depending on force.

**Deployment:** the teacher refreshes the reference asynchronously; the student keeps querying
and applies corrections to the latest completed reference. Corrections are clipped separately and
expire/skip by timestamp. Training uses **asynchronous schedule replay** with sampled query
periods and inference latencies, so the student is trained on the delay distribution it will see.

### 1.3 Hardware, sensing, rates

| Item | Value | Source |
| --- | --- | --- |
| Single-arm platform | 7-DoF Franka Emika Panda, wrist-mounted + external Intel RealSense D405 | §IV-A, same URL |
| Bimanual platform | "X Square Robot", one wrist camera per arm + one shared external camera | §IV-A |
| Force sensing | **No wrist F/T sensor.** Robot-provided **joint-torque-based wrench estimates**, as in ForceVLA | §IV-A |
| Recording rates | multi-view images, robot state, commanded actions at **30 Hz**; timestamped wrench at **100 Hz** | §IV-A |
| Wrench history | **100 ms** | §IV-A |
| Teacher chunk | `H = 50` steps | §IV-A |
| Student corrections | `K = 5` pose corrections | §IV-A |
| Reference forward pass | **189.7 ms** (the paper also says "approximately 55 Hz for serial inference", which is inconsistent with 189.7 ms = 5.3 Hz — likely pipelined throughput; ⚠ §7) | §IV-C |
| Correction forward pass | **2.43 ms** (< the 10 ms command interval) | §IV-C |
| Command transmission | limited to **100 Hz** | §IV-A |
| Demonstrations | 200 per task; SpaceMouse (single arm), leader–follower (bimanual) | §IV-A |
| Compute | workstation, 2× RTX 4090 | §IV-A |

### 1.4 Tasks and results

Nine real-robot tasks (5 single-arm, 4 bimanual), **20 trials per method per task**: USB
insertion, button pressing, plug insertion, whiteboard wiping, drawer opening (single-arm);
and four bimanual tasks including object flipping and whiteboard wiping. Baselines: ForceVLA,
π0.5, TA-VLA, ImplicitRDP, and the Stage-1 teacher executed directly.

| Metric | Value |
| --- | --- |
| Mean success, ForceDelta-VLA | **82.2 %** |
| Mean success, ForceVLA | **54.4 %** |
| Mean success, Stage-1 Temporal Teacher (direct) | **70.6 %** |
| Largest gains vs ForceVLA | USB insertion, button pressing, plug insertion (per-task table not extracted — ⚠ see §7) |
| Peak contact force, successful trials | **−4.2 N** (single-arm) and **−4.3 N** (bimanual) vs ForceVLA, ≈ **−26 %** on both |
| Completion time | **−5.2 s** (single-arm), **−5.9 s** (bimanual) vs ForceVLA |
| vs teacher | +11.7 points mean success; peak force −3.3 N / −2.2 N; time −3.9 s / −3.4 s |
| +200 ms injected reference latency | success **−15 points** (vs **−25 points** for the teacher); peak force **+3.7 N** (vs **+9.6 N**) |
| Unseen objects (3 tasks) | +26.7 points over the teacher; peak force −8.2 N |

**Ablations (4 tasks, 20 trials each) — the useful part for us:**

| Ablation | Effect |
| --- | --- |
| Remove the force correction | **−15 / −17.5 points**; peak force **+3.7 / +4.3 N** |
| Zero the force history (keep the branch) | worse than removing the output entirely → the branch really uses force |
| Single combined correction head | **−10 points** on both platforms |
| Remove the delay correction | **−7.5 points** both platforms |
| No schedule replay | **−7.5 / −12.5 points** |
| Demonstration-derived target instead of paired-teacher target | **−12.5 / −17.5 points** |

### 1.5 What is measured vs what is claimed

**Measured (real robot, 20 trials/task, same demos and limits across methods):** the 82.2 % vs
54.4 % vs 70.6 % means; the force/time deltas; the latency-sensitivity curve; the six ablations;
the 2.43 ms vs 189.7 ms forward passes.

**Claimed / inferred:** that the gain comes from *separating* reference from correction rather
than from extra capacity or longer training (the ablations support this but do not isolate every
confound); that the method generalizes beyond these nine tasks; the bimanual "X Square Robot"
details are not expanded. The abstract's "55 single-arm and 44 bimanual tasks" is inconsistent
with the nine tasks / 20 trials description — most likely a typo for *trials* (⚠ §7).

### 1.6 What transfers to a parallel-jaw fruit pick-and-place

**Transfers well:**

* **The decomposition itself.** Our hybrid loop is already a two-rate system: a slow learned
  acquisition and a scripted 120 Hz carry/place. ForceDelta is evidence that the right place for
  force is a **fast additive correction on top of a slow reference**, not another input token in
  the slow model. The paper's 2.43 ms correction vs 189.7 ms reference is the quantitative case
  for keeping contact control out of the diffusion forward pass.
* **The supervision trick.** If we ever want a *learned* grip correction, paired
  force-conditioned / force-masked predictions of the same checkpoint give correction labels from
  the existing demonstration store — no new labelling. This is directly applicable because our
  policy already conditions on proprioception and could be given a force-masked variant.
* **Delay as a first-class target.** The project's own ASYNC/handover timing problems (a fixed
  0.9 s lead vs measured 1.36–7.68 s setup, W7-B) are the same phenomenon the delay head models:
  the correction must account for *how stale the reference is*, not just for force.
* **The negative result too.** Corrections modify pose only; the gripper command is the
  reference's. ForceDelta does **not** solve grasp force — it solves contact *pose* adjustment.
  For a drop problem, it is not a grip-force method.

**Does not transfer directly:**

* Input modality: end-effector **wrench from joint-torque estimates**, 6-D, 100 Hz. Our per-finger
  normal/tangential contact forces are a different signal at a different location; a 6-D EE wrench
  cannot tell one-sided finger contact from two-sided.
* Task family: insertion/pressing, where the failure is *alignment under contact*. Our failure is
  *payload retention during carry*, which is a friction-cone problem, not a pose-correction one.
* Cost: 189.7 ms teacher at 50-step chunks and a 3-stage training recipe is not a cheap add.

---

## 2. Eka VFA (vision–force–action)

### 2.1 Identity

**Eka Robotics**, Cambridge MA, founded 2024. Co-founders **Pulkit Agrawal** (MIT professor,
Improbable AI Lab) and **Tuomas Haarnoja** (ex-Google DeepMind). The model is named
**Vision-Force-Action (VFA)**. $150 M Series A led by a16z and F-Prime, announced 20 Oct 2026,
$1.45 B post-money. (Eka Robotics raises $150M…, 2026 —
https://ekarobotics.com/blog/eka-robotics-raises-150m-to-build-superhuman-intelligence-for-the-physical-world;
TechCrunch, 2026 — https://techcrunch.com/2026/10/20/eka-is-worth-1-45-billion-thanks-to-a-physical-ai-model-that-has-experts-raving/;
MIT News clip, 2026 — https://news.mit.edu/news-clip/techcrunch-273)

**There is no paper and no technical report.** The company blog has exactly three posts (the
funding announcement and two press clips) as of 2026-10-25
(https://ekarobotics.com/blog). A search of arXiv/GitHub for an Eka technical artifact returned
nothing. The founders **explicitly declined to describe the training method**, calling it their
commercial edge (WIRED, 2026 —
https://www.wired.com/story/when-robots-have-their-chatgpt-moment-remember-these-pincers/).

### 2.2 Architecture: what is actually knowable

| Question | What the record supports |
| --- | --- |
| Modalities | Vision + **force**, with "action" as output. The force comes from **custom grippers that incorporate a sense of touch** (WIRED, 2026). The exact transducer (strain gauge? tactile array? joint torque?) is **not disclosed**. |
| Fusion | **Unknown.** No statement on whether force is an input channel, a token, a residual, or a controller setpoint. |
| Training | **Large-scale reinforcement learning in simulation**, with "realistic joints and motors" and physics such as mass and inertia; sim-to-real transfer is claimed to be the differentiator. No human-demonstration corpus is claimed — explicitly positioned against imitation/VLA-from-video approaches. |
| Control rate | **Not disclosed.** No number appears in any source. |
| Output | End-effector motion / gripper commands (inferred from demos; not stated). |

The only *architectural* claim in the record is the framing: forces are treated as a **first-class
representation** ("Forces are the language of the physical world", Pulkit Agrawal, LinkedIn, 2026 —
https://www.linkedin.com/posts/pulkit-agrawal-967a4218_forces-are-the-language-of-the-physical-world-activity-7454937523186814978-RHXh),
and the model learns "how the weight and speed of its movement interact with the objects in its
grasp" (WIRED, 2026). That is a research direction, not an architecture.

### 2.3 What is measured vs what is claimed

**Independently observed (not a benchmark):** WIRED's reporter watched live demos — picking a
light bulb, earplug box, hairbrush, a set of keys with a plush keyring — including a visible
recovery from a fumble, and a chicken-nugget pick-and-place demo with a moving conveyor. This is
**qualitative demo evidence**, not a measured rate. (WIRED, 2026 — URL above)

**Company claims (no independent verification, no protocol, no denominator):**

| Claim | Value | Source |
| --- | --- | --- |
| Picking throughput | **~1,500 objects/hour**, vs ~600/hour human baseline | company blog, 2026; TechCrunch, 2026 |
| Pick reliability | **">95 %"** of the time | TechCrunch, 2026 (attributed to Eka) |
| Object range | up to **1 kg** | MIT News clip, 2026 |
| Gripper hardware cost | **< $1,000**, rated **5 M duty cycles** (target 20 M) | TechCrunch, 2026 |
| Tasks | picks, arranges, places, **screws in a light bulb, inserts wires** | company blog, 2026 |
| Sim-to-real | "the typical sim-to-real barrier is falling" | company blog, 2026 |

**What is verifiable:** the company exists, the funding round, the founders, the live demos, and
the existence of a custom force-sensitive gripper. **What is not:** every number above; the
architecture; the control rate; whether the 1,500/hour uses one arm or a cell; the failure
definition behind ">95 %"; whether the demos are autonomous or teleoperated (WIRED describes
autonomous behaviour but the company would not detail the setup).

**Do not cite Eka as evidence for any mechanism.** It is useful as an existence proof that a
force-first, sim-RL pick-and-place product is being funded and demoed at speed, and as a source of
plausible target numbers (1,500/hr ≈ 25/min, vs this project's 3.6 placed/min — a different
system, different objects, not comparable).

---

## 3. Slip detection and grip-force control

### 3.1 Friction-cone margins

The classical framing is the **friction cone**: a grasp is stable while the ratio of tangential to
normal contact force stays below the local friction coefficient. **Incipient slip** is the
precursor: parts of the contact patch slip while the object as a whole has not moved. Tremblay &
Cutkosky used exactly this to (a) detect imminent gross slip and (b) **estimate the friction
coefficient online** from the normal/tangential force ratio at the moment of incipient slip, then
raise grasp force pre-emptively. (Estimating Friction Using Incipient Slip Sensing During a
Manipulation Task, 1993 — http://bdml.stanford.edu/oldweb/touch/publications/tremblay_icra93.pdf)

In humans, the same structure appears as a **safety margin**: grip force is set above the minimum
slip force by an amount that **scales with friction** — the grip force/load force ratio rises as
the surface gets more slippery (Westling & Johansson, 1984 —
https://pubmed.ncbi.nlm.nih.gov/6705863; Johansson & Westling, 1984 PDF —
http://wexler.free.fr/library/files/johansson%20(1984)%20roles%20of%20glabrous%20skin%20receptors%20and%20sensorimotor%20memory%20in%20automatic%20control%20of%20precision%20grip%20when%20lifting%20rougher%20or%20more%20slippery%20objects.pdf).
In a lateral-pinch push task the measured margin averaged **25 % of MVC** (Dependence of safety
margins in grip force on isometric push force levels in lateral pinch, 2009 —
https://pmc.ncbi.nlm.nih.gov/articles/PMC8853688) — a different task, but a useful order of
magnitude.

**Friction-cone sensing is slow-ish in practice:** friction-cone-based slip detection methods
report **>20 ms** delay (Universal slip detection of robotic hand with tactile sensing, 2025 —
https://pmc.ncbi.nlm.nih.gov/articles/PMC11843555, citing Beccai et al., 2008).

### 3.2 Incipient-slip detection from force and tactile signals

Three signal families, with measured performance:

1. **Tactile pin/feature velocity (optical tactile).** The T-MO hand (three TacTip sensors,
   **60 fps**, on-board pin tracking) with an SVM: single-finger **F1 = 0.972**, whole-hand
   **F1 = 0.833**; classification itself **sub-millisecond**, hand response **>5 ms**. Online, it
   caught the object **74 %** of the time with a 1-frame trigger (mean slip **21 mm**, 20 % false
   positives) and **72 %** with a 2-frame trigger (mean slip **29 mm**, **0 % FP**); whole-hand
   averages **88.75 %** true positive, **8.75 %** FP, **2.5 %** drops, average slip **31 mm**
   (range 12–63 mm). The 2-frame rule eliminated false positives at the cost of 8 mm more slip.
   (Slip detection for grasp stabilisation with a multi-fingered tactile robot hand, 2021 —
   https://arxiv.org/abs/2010.01928)
2. **Force derivative / force ratio.** The force-based route detects the *onset* of the tangential
   load ratio change rather than surface motion; reported detection delays are **10–50 ms** for
   force-based systems vs **sub-10 ms** for high-rate tactile, with a stated practical target of
   **sub-10 ms** for most materials (Force Control vs Tactile Sensing: Which Detects Micro-slip
   Earlier?, 2025 — https://eureka.patsnap.com/report-force-control-vs-tactile-sensing-which-detects-micro-slip-earlier)
   ⚠ (industry report, not peer-reviewed — §7). Su et al. (2015) predicted slip **30 ms before**
   an IMU on the object detected it, using a BioTac (as reported in James & Lepora, 2021).
3. **Vibration / accelerometer.** Howe & Cutkosky embedded accelerometers in an artificial skin
   for slip and texture perception (1989, cited in James & Lepora, 2021). The same review notes
   Li et al. (2017) reached **96 %** slip-detection success with a 3×8 tactile array plus
   fingertip force sensors, but **without** a reaction loop.

**Recent low-cost designs give the cleanest numbers for a production cell:**

* **FORTE** (3D-printed fin-ray fingers with internal air channels): force estimate **0–8 N**,
  average error **0.2 N**, force channel at **100 Hz** with **<10 ms** update; slip detector at
  **500 Hz** with typical detection latency **<100 ms**; grasps slippery/delicate objects without
  damage. (FORTE: Tactile Force and Slip Sensing on Compliant Fingers for Delicate Manipulation,
  2025 — https://arxiv.org/html/2506.18960v3)
* **Event-camera (DAVIS) incipient slip:** average **44.1 ms** latency, with **11 experiments
  below 10 ms**, against a 1000 fps reference camera; the paper notes other tactile sensors achieve
  **1–3 ms** latency at 100 fps. (A Novel Event-Based Incipient Slip Detection Using DAVIS, 2018 —
  https://www.mdpi.com/1424-8220/18/2/333)

### 3.3 The latency budget (why the numbers matter)

The reusable relation is trivial but decisive:

```
allowed_latency ≈ allowed_slip_distance / slip_velocity
```

At a **2 mm** slip budget and 0.2 m/s of relative motion, the whole detect+act budget is **10 ms**.
At **20 mm** and 0.1 m/s it is **200 ms**. The measured systems sit exactly where you would expect:

* human reactive grip: **60–80 ms** (Johansson & Westling, 1988 —
  https://pubmed.ncbi.nlm.nih.gov/3416959; a second source gives **60–90 ms**, Cole, 1988 —
  https://journals.physiology.org/doi/pdf/10.1152/jn.1988.60.4.1513);
* T-MO reaction loop: 60 Hz sensing + >5 ms actuation, resulting in **21–31 mm** of slip before
  the object is arrested;
* FORTE: **<100 ms**, sufficient for delicate produce because it is paired with a compliant
  fin-ray finger that limits slip speed;
* high-rate tactile: **1–3 ms** sensor latency, which is what buys sub-millimetre slip.

**The design rule for a parallel-jaw produce cell:** a reflex is only useful if
`(sense period + decision + actuation) < allowed_slip / slip_speed`. Compliance (soft pads,
fin-ray fingers) buys time by reducing slip speed and by letting the contact patch deform before
gross motion — it is a latency multiplier, not just a grip aid.

### 3.4 Grip-force adaptation loops

* **Incipient-slip-triggered force increase.** Tremblay & Cutkosky raise grasp force when
  incipient slip is sensed, and reuse the force ratio at that instant as a friction estimate
  (1993, URL above).
* **Independent per-finger controllers.** Veiga, Edin & Peters run one tactile slip predictor and
  one grip-force controller per finger, with **no central communication**, and show stable grasps
  emerge on multi-digit hands and resist perturbations across many objects (BioTac/BioTac SP).
  (Grip Stabilization through Independent Finger Tactile Feedback Control, 2020 —
  https://www.mdpi.com/1424-8220/20/6/1748; preprint https://arxiv.org/abs/1806.05031)
* **Grip tightening as the corrective action.** In T-MO the corrective action is a small
  additional finger closure (2 % of the motion range) plus 1.5 mm of extra compression on the
  single-finger rig — enough force to arrest the object without crushing the sensor. (2021, URL
  above)
* **Release-to-find-the-minimum.** Veiga et al. also slowly release grip until slip is predicted,
  then re-tighten — an explicit search for the friction-cone boundary rather than a fixed margin
  (2020, URL above).

### 3.5 What is measured vs what is claimed

**Measured:** T-MO's F1 0.972/0.833, 60 fps, sub-ms classification, 21–31 mm caught slip, 0–20 %
FP trade-off; FORTE's 0–8 N ± 0.2 N, 100/500 Hz, <100 ms; DAVIS 44.1 ms mean with 11 sub-10 ms
trials; human 60–80 ms reactive latency and friction-scaled safety margin; friction-cone methods
>20 ms; Su et al. 30 ms early prediction; Veiga's per-finger stabilization working without central
communication.

**Claimed / weaker:** "sub-10 ms is required for practical applications" (industry report);
"1–3 ms tactile sensors" is a sensor-level number, not a closed-loop number; the 25 % safety
margin is from lateral pinch, not precision grip; T-MO's 88.75 % TP is on a lab rig with an
ArUco marker, not a production cell.

---

## 4. Sim-to-real grip force: why a simulated jaw drops what a real jaw holds

### 4.1 PhysX/Isaac specifics that directly change grasp force

**(a) Friction is combined, and the default is `average`.** PhysX material pairs resolve friction
through a per-material **combine mode**: `average`, `min`, `multiply`, `max`, with precedence
`average < min < multiply < max` when the two sides disagree. "The default value of each material
combine mode is average. In the absence of any explicit changes… the default behaviour of each
contact is therefore also average." (Rigid Bodies — Omni Physics, 2026 —
https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/rigid_bodies.html;
Physics Simulation Fundamentals, Isaac Sim 5.1 —
https://docs.isaacsim.omniverse.nvidia.com/5.1.0/physics/simulation_fundamentals.html)

Consequence: a rubber pad authored at μ = 1.0 against a fruit authored at μ = 0.4 yields an
effective **μ = 0.7** under `average`, not the ~1.0 a real rubber pad would deliver on a wet
fruit. This alone can turn a stable grasp into a marginal one. Isaac Sim's own gripper tutorial
therefore sets pad friction to **0.8 with combine mode `Max`** (Rig Closed-Loop Structures,
Isaac Sim 5.1 —
https://docs.isaacsim.omniverse.nvidia.com/5.1.0/robot_setup_tutorials/rig_closed_loop_structures.html).
This is the single cheapest sim-to-real lever in the whole review.

**(b) Friction model depth depends on version.** For Isaac Sim **< 5.0 only the static friction
coefficient is set**; **5.0+** sets static, dynamic and viscous, combining Coulomb friction with a
viscous term (isaaclab.assets — Isaac Lab documentation, 2026 —
https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.assets.html). A build that only
authors static friction will not reproduce the stick–slip behaviour that governs a loaded slide.

**(c) Timestep is a grasp-force parameter.** Isaac Sim's own tutorial is explicit: the Robotiq
hand holds a 200 g cylinder but **"when we increase its mass to the maximum payload… 2.5 kg, it
just slips and fails the grasp"** at the default rate; **"by increasing it to at least 80 steps
per second, the grasp is successful even at the maximum payload"** (Rig Closed-Loop Structures,
Isaac Sim 5.1 — URL above). This is a measured vendor statement that a sim grasp failure at a
given mass is a **solver-rate artifact**, not a physics verdict.

**(d) Rigid vs compliant contact.** PhysX supports a **compliant contact model** via
`PhysxMaterialAPI` compliant-contact **stiffness and damping**; if either material in a pair is
compliant, the contact follows the spring–damper model, and if both are, stiffness/damping are
combined by the same precedence rules (Rigid Bodies — Omni Physics, 2026 — URL above; isaaclab
spawners, 2026 —
https://isaac-sim.github.io/IsaacLab/main/source/api/lab_physx/isaaclab_physx.sim.spawners.html).
With the default rigid contact, normal force is a constraint force with no compliance; the grasp
"force" is whatever the position drive produces against a hard constraint, which is not the
force–displacement curve of a rubber pad.

### 4.2 The measured case that compliant jaws matter

**IPC-GraspSim** is the cleanest controlled comparison. It notes that "soft compliant jaw tips are
almost universally used with parallel-jaw robot grippers due to their ability to increase contact
area and friction," and that rigid-body simulation cannot represent the interaction. On **2,000
physical grasps** it reports grasp-quality prediction:

| Model | AP | AR |
| --- | --- | --- |
| Soft Point (analytic) | 0.76 | 0.55 |
| REACH (analytic) | 0.82 | 0.66 |
| 6DFC (analytic) | 0.82 | 0.67 |
| **Isaac Gym (rigid)** | **0.75** | **0.79** |
| **IPC-GraspSim (compliant jaws)** | **0.86** | **0.84** |

It also documents the failure mode directly: "in simulation, the gripper backings are perfectly
rigid, and do not account for this bending phenomenon" — i.e. the real jaw backing **cantilevers
away** under closing force and pushes the object out, while the sim jaw stays rigid and predicts a
hold. (Simulation of Parallel-Jaw Grasping using Incremental Potential Contact Models, ICRA 2022 —
https://autolab.berkeley.edu/assets/publications/media/2022-ICRA-IPC-GraspSim-kim-submission-highres.pdf;
project page https://sites.google.com/berkeley.edu/ipcgraspsim)

**Reading:** rigid sim is not uniformly optimistic or pessimistic — it is **miscalibrated**. It
over-predicts holds where real compliance pushes the object out (AP 0.75 vs 0.86), and it
under-predicts holds where real compliance increases contact area and friction. For a produce
cell the second direction dominates: a rigid jaw has a point/line contact with μ from the combine
mode, while a real rubber pad conforms, increases area, and adds adhesion.

### 4.3 Drive force, penetration, and "interference" commands

Three mechanisms, in decreasing order of how well they are documented:

1. **Drive force limit.** A position-controlled jaw's grip force is not a simulated sensor; it is
   whatever the drive produces against the contact, capped by the drive's force/effort limit. If
   the limit is set below the real gripper's rated force, the sim grasp is weaker than reality by
   construction. (Mechanism, not a measured citation — ⚠ §7. It is consistent with this project's
   own finding that a "drive-saturated pinch" reads 4.1–4.5 N and does not change when the
   commanded interference is relieved to 0.5 mm — AGENTS §2, R6-B.)
2. **Penetration-based grasp.** Commanding the jaws to a width narrower than the object makes the
   solver generate a restoring force from penetration. That force depends on contact stiffness
   and timestep, not on the real pad's compression curve; at coarse timesteps the correction
   impulse can also eject the object (the "pop" failure). The Isaac tutorial's 80 Hz result is the
   measured instance of this class.
3. **Rigid backing / cantilever.** Documented by IPC-GraspSim above: real jaw backings flex, sim
   ones do not.

### 4.4 What is measured vs what is claimed

**Measured:** PhysX default combine = average and the precedence order (vendor docs); Isaac Sim
tutorial 2.5 kg slip at default rate and success at ≥80 Hz (vendor docs, with a video); Isaac
Lab's static-only friction for <5.0 (vendor docs); IPC-GraspSim's AP/AR table on 2,000 real
grasps (peer-reviewed); compliant-contact stiffness/damping API (vendor docs).

**Claimed / mechanism:** that combine mode is a *large* contributor in our specific scene (not
measured here); that drive limits bind (not measured here, though the project's own force data is
consistent); that penetration ejection explains any particular failure (hypothesis).

**Caveat:** all Isaac/PhysX facts above are **vendor documentation**, not independent studies.
The 80 Hz tutorial result is a single vendor demo, not a controlled experiment.

---

## 5. Closed-loop action rate: frequency, latency, and reflexes on top of a slow policy

### 5.1 What systems actually run at

| System | Control rate | Notes |
| --- | --- | --- |
| π0 / π0.5 | **50 Hz** (`Δt = 20 ms`), `H = 50` chunk | π0 spends **46 ms** on KV-cache prefill alone on an RTX 4090 *before* denoising (Real-Time Execution of Action Chunking Flow Policies, 2025 — https://arxiv.org/abs/2506.07339) |
| Diffusion Policy | **10 Hz** on real robots, action horizon 16 | (Diffusion Policy, 2023 — https://arxiv.org/abs/2303.04137) |
| ACT | **50 Hz**, chunk 100 | (Action Chunking with Transformers, 2023 — https://arxiv.org/abs/2304.13705) |
| OpenVLA (optimized) | **321 ms** latency on an A100, i.e. ~3 Hz | measured by Kim et al., reported in RTC, 2025 |
| ForceDelta-VLA | reference **189.7 ms** (~5.3 Hz), correction **2.43 ms** at a **100 Hz** command | §1.3 |
| Human reactive grip | **60–80 ms** | §3.3 |

### 5.2 Measured effects of frequency and latency

**(a) Latency, measured directly (RTC, NeurIPS 2025).** π0.5 at `H = 50`, `Δt = 20 ms`, 5 denoising
steps: model latency **76 ms** (97 ms with RTC) plus **10–20 ms** LAN, giving an inference delay
`d ≈ 6` controller steps. Injecting **+100 ms** and **+200 ms** (`d ≈ 11`, `d ≈ 16`):

* **synchronous** chunk execution "degrades linearly" with delay;
* both **temporal-ensembling** variants "do not run at all" at +100/+200 ms — oscillations large
  enough to trigger the robot's **protective stop**;
* **RTC** shows **no degradation** across the range, and is **statistically significantly better**
  at +100 and +200 ms;
* RTC executes the same motion **20 % faster** than synchronous inference, and completes more of
  each task earlier (fewer mistakes, less retrying) even with pauses removed;
* the battery is 6 real bimanual tasks, **480 episodes, 28 h** of robot execution.
(Real-Time Execution of Action Chunking Flow Policies, 2025 — https://arxiv.org/abs/2506.07339)

**(b) Execution horizon, measured.** In the Kinetix benchmark (12 dynamic tasks, 2,048 rollouts
per point, delays 0–4 steps at `H = 8`), **only RTC and bidirectional decoding improve as the
execution horizon shrinks**; naive async and temporal ensembling get worse. This is the measured
statement that *shorter chunks help only if chunk transitions are handled* — a policy that simply
re-plans more often without continuity is worse, not better. (RTC, 2025 — URL above)

**(c) Policy frequency, measured — but read the metric carefully.** A 2026 study ablates policy
frequency at **10 / 20 / 50 / 100 Hz** with the physics and the real controller rate held fixed
(zero-order hold of position commands), across a grid of PD gains, on a Franka FR3 joint-reach
sim-to-real task (30 real rollouts per setting). Its measured result: **the fraction of jitter
failures drops from 21.8 % at 100 Hz to 5.0 % at 10 Hz, with the sharpest reduction between 50 Hz
and 20 Hz.** The paper's conclusion is that low policy frequency is *more* robust to actuation
mismatch, not that low frequency is faster. (Tune to Learn: How Controller Gains Shape Robot
Policy Learning, 2026 — https://arxiv.org/abs/2604.02523)

This is the counter-intuitive result worth carrying: **higher policy rate is not automatically
better**; it amplifies sim-to-real motor mismatch at contact. What you want is a *high-rate inner
loop* (impedance/force) under a *moderate-rate policy*, not a 100 Hz learned policy.

### 5.3 Force-triggered reflexes on top of a slow policy

Three independent pieces of evidence:

1. **ForceDelta-VLA** is the explicit architecture: a 189.7 ms reference plus a **2.43 ms**
   force-conditioned correction running at the 100 Hz command rate, improving mean success from
   70.6 % (teacher alone) to 82.2 %, and cutting the penalty of +200 ms reference latency from
   −25 to −15 points. The correction path is what makes the slow path tolerable.
   (2026 — https://arxiv.org/abs/2609.18242)
2. **Human motor control** is the biological version: a **60–80 ms** triggered grip-force
   response layered on a slower programmed action, with the trigger coming from tactile afferents
   at slip onset (Johansson & Westling, 1988 — https://pubmed.ncbi.nlm.nih.gov/3416959).
3. **Tactile slip reflexes in grasping** close the loop in 5–100 ms depending on sensor, and the
   measured cost of not having one is 17–63 mm of slip (T-MO) or a dropped object (FORTE,
   DAVIS — §3).

**Synthesis:** the literature does not support "run the VLA faster". It supports a **cascade**:
slow generative reference (5–50 Hz) → fast correction/reflex (100 Hz–1 kHz) → hardware loop
(1 kHz+). RTC makes the slow layer's latency invisible; ForceDelta makes its force-blindness
irrelevant; T-MO/FORTE show the reflex layer's latency budget.

### 5.4 What is measured vs what is claimed

**Measured:** π0.5 76 ms / 50 Hz / `H = 50`; RTC's +100/+200 ms results, protective-stop failures
of TE, 20 % faster motion, 480 episodes; Kinetix horizon result; Tune to Learn's 21.8 % → 5.0 %
jitter-failure fraction; ForceDelta's 2.43 ms vs 189.7 ms and +200 ms penalty; human 60–80 ms.

**Claimed / weaker:** that "20 % faster" generalizes beyond the six tasks; that RTC's mechanism is
the only way to get async continuity (BID also improves with shorter horizons); that 10 Hz is
"better" — Tune to Learn measures *jitter failures* in a joint-reach sim-to-real task, not task
success or throughput, and it does not report a success-rate comparison across policy frequencies.

---

## 6. Transferable to this project — six cheap experiments, ranked by expected value

**Ranking logic:** expected value = (probability the mechanism is live in *this* tree) × (effect on
the target metric) ÷ cost. Costs assume the existing harness (`scripts/140_policy_ab.sh`,
`accept.sh`, `accept_policy.sh`, `105/190` gates) and the existing default-off knobs.
Target metrics: **(a) fewer drops** = the `carried-not-placed` / grip-loss class and `clean_slip`;
**(b) higher placed/min** = placed fruit per minute at a fixed attempt count, read per-leg and
with the attractor named.

### E1 — (a) A 120 Hz slip reflex on the existing finger-force channels  ★ highest EV

**What:** a default-off, direct/hybrid-scoped reflex that watches per-finger normal force (and its
derivative) during `grasp_lift`/`carry` and, on a slip signature, adds a bounded grip-force bump
(e.g. +15–25 % for 30–60 ticks) instead of waiting for the policy or the scripted profile.
**Why it should work here:** the project's own W8-B measurement gives the latency budget — the
escape crosses 2 mm and contact is lost a median **25 ticks later** at 120 Hz ≈ **208 ms**; a
60–80 ms reflex (human) fits with ~3× margin, and even a 100 ms tactile loop (FORTE) fits.
The escape is a **loaded slide** with force already at its carry level (median 4.90 N,
single-sided contact), so the correct actuator is more normal force, not a re-approach.
**Sources:** human 60–80 ms (Johansson & Westling, 1988); T-MO 21–31 mm caught slip with a 60 Hz
sensor and >5 ms actuation (2021); FORTE <100 ms (2025); Tremblay & Cutkosky's incipient-slip
force increase (1993).
**Cost:** one knob + one A/B (~1 day of runs). **Read:** carried-class pairing, `clean_slip`
median, and fired-only cycle. **Kill:** reflex fires >20 % of legs with no carried-class movement,
or adds >2 % cycle.

### E2 — (a) Friction/contact audit: combine mode, pad μ, timestep, compliant contact

**What:** a 2×2×2 screen — friction combine `average` vs `max`; pad μ 0.6 vs 1.0; physics step
60 vs 120 Hz (and ≥80 Hz per the Isaac tutorial) — with the *same* attractor check (fingerprint),
because this moves the branch.
**Why:** PhysX's default is `average`, which can halve the effective μ; the Isaac Sim gripper
tutorial needs `Max` + μ 0.8 and **≥80 Hz** to hold 2.5 kg that otherwise slips; rigid contact
cannot represent the pad conformity that IPC-GraspSim shows is worth **AP 0.75 → 0.86** on 2,000
real grasps.
**Cost:** near-zero (config only). **Read:** `mu_required = |F_t|/|F_n|` per carry leg from the
existing `[carry]` rows, `clean_slip`, carried class — **not** success rate (different attractor).
**Kill:** the control replays bit-identically and the carried class does not move at any cell.

### E3 — (a) Commanded-interference → normal-force calibration + drive-effort sweep

**What:** sweep the commanded jaw interference (0, 2, 4, 6 mm inside the payload span) against the
measured normal force at lift, then sweep the drive effort limit at the best interference.
**Why:** R6-B found a **drive-saturated pinch** — the command sits a median 11.9 mm inside the
payload span, force reads 4.1–4.5 N, and relieving the command to 0.5 mm of allowed interference
leaves the force **unchanged**. That means the current force is set by the drive, not by the
command; a force-margin experiment that only moves the command is measuring nothing. The real
knob is the drive limit (or pad compliance). This is also the calibration E1's bump needs.
**Cost:** low (one probe script, no policy). **Read:** force-vs-interference curve, then
`mu_required` at the chosen setpoint. **Kill:** force is flat across the whole interference range
*and* flat across the effort range → the limiter is elsewhere (solver/friction), go to E2.

### E4 — (b) Asynchronous chunk execution (RTC-style) in the hybrid loop

**What:** instrument the policy loop's inference latency and the pause it induces per attempt;
then overlap inference with execution (freeze executed prefix, inpaint the rest) — no retraining.
**Why:** RTC's measured result is the strongest available: π0.5 at 50 Hz with 76 ms latency and
d=6 is **robust to +200 ms** while synchronous degrades linearly and temporal ensembling triggers
protective stops; RTC is **20 % faster** at equal task score. The project's hybrid loop is a
cascade already, but a synchronous inference pause is exactly the failure mode RTC removes.
**Cost:** medium (inference plumbing, no training). **Read:** pause seconds per attempt, placed/min,
and the per-leg motion gate (the pause changes the branch). **Kill:** measured pause <0.3 s/attempt
→ no headroom, stop.

### E5 — (b) Phase-scoped execution horizon (short in contact, long in transit)

**What:** keep the long chunk for the approach, shorten the execution horizon (1–5 actions) only
during pick/carry/place; measure per-phase.
**Why:** RTC's Kinetix result — **only** methods with chunk continuity improve as the execution
horizon shrinks; naive re-planning gets worse. Tune to Learn adds the caution: at 100 Hz the jitter
failure fraction is **21.8 %** vs **5.0 %** at 10 Hz, sharpest 50→20 Hz, so shorten the horizon
without raising the policy rate.
**Cost:** low (config + policy loop). **Read:** placed/min and the contact-phase failure classes.
**Kill:** shorter horizon increases no-contact/acquisition failures without a placed/min gain.

### E6 — (b) Offline-distilled force/state corrector (the full ForceDelta idea, cheaply)

**What:** instead of a 3-stage VLA distillation, fit a small MLP/corrector on **logged** hybrid
rollouts: inputs = current force history + proprio + the policy's last pose command; target =
the residual between the scripted primitive's next pose and the policy's command during contact.
Train offline, evaluate as a default-off fast layer at 120 Hz.
**Why:** ForceDelta's ablation is the evidence that a *separate* force correction is worth
15–17.5 points over a combined head, and its 2.43 ms correction is what buys the 82.2 % vs 70.6 %
teacher gap. Our logs already contain the pairs; no simulator time is needed to *train*.
**Cost:** medium (offline training + A/B), highest ceiling but lowest EV per cost, hence last.
**Read:** carried class, `clean_slip`, fired-only cycle. **Kill:** no carried-class movement at
N=5, or a new failure reason.

### Ranking summary

| # | Target | Experiment | Cost | Why ranked here |
| --- | --- | --- | --- | --- |
| E1 | (a) drops | 120 Hz slip reflex | low | 208 ms measured budget vs 60–100 ms reflex; directly matches the measured loaded-slide mechanism |
| E2 | (a) drops | friction/contact audit | very low | default `average` combine and 60 Hz step are documented sim artifacts; config-only |
| E3 | (a) drops | interference→force calibration | low | the project's own data says the drive, not the command, sets force |
| E4 | (b) rate | RTC-style async chunks | medium | largest measured latency result (480 episodes); no retraining |
| E5 | (b) rate | phase-scoped horizon | low | measured that only continuity-aware short horizons help |
| E6 | (b) rate | offline force corrector | medium | highest ceiling, but needs training and the ForceDelta evidence is from a different task family |

**Explicitly not recommended as first spends:** raising the policy rate (Tune to Learn: 100 Hz is
*worse* for jitter than 10 Hz); adding more supply density (project-measured negative, P1c);
another two-line clearance lever (all measured negative, R3/W3); a learned slip detector on
tactile signals (the project has no tactile array, and T-MO's advantage is 60 Hz *contact-patch*
motion, which finger force alone cannot see).

---

## 7. Could not verify / low confidence

1. **ForceDelta-VLA per-task table.** Only the 82.2 / 54.4 / 70.6 means and the force/time deltas
   were extractable; the per-task numbers and the TA-VLA / π0.5 / ImplicitRDP values were not
   pulled from Table I. The abstract's "55 single-arm and 44 bimanual tasks" conflicts with the
   nine-task / 20-trial description and is almost certainly a typo for trials. The paper's
   "189.7 ms, corresponding to approximately 55 Hz for serial inference" is arithmetically
   inconsistent (189.7 ms = 5.3 Hz); the 2.43 ms correction figure is the one to trust for the
   correction path.
2. **Eka VFA — everything technical.** No paper, no technical blog, no architecture, no control
   rate, no fusion scheme, no independent benchmark. The founders explicitly declined to disclose
   the method (WIRED, 2026). Treat all throughput/accuracy numbers as marketing until a paper or
   an independent replication exists.
3. **Exact human safety-margin percentage.** Westling & Johansson (1984) define and measure it and
   show friction scaling; the precise % was not extractable from an accessible copy. The 25 % MVC
   figure is from a lateral-pinch *push* task (Seo et al., 2009), not precision grip — use it as an
   order of magnitude only.
4. **"Force-based detection 10–50 ms, tactile sub-10 ms"** comes from an industry report
   (eureka.patsnap.com), not a peer-reviewed measurement. Directionally consistent with the
   peer-reviewed sources, but do not quote as a measured result.
5. **Drive-force-limit mechanism in PhysX.** That a position drive's max force caps grip force is
   mechanically certain, but I did not find a primary PhysX document page stating it, and no
   controlled study measuring its effect on grasp success. The project's own 4.1–4.5 N constant
   under relief (R6-B) is the closest evidence and is internal.
6. **The Isaac Sim 80 Hz / 2.5 kg result** is vendor tutorial documentation with a video, not a
   controlled experiment. It is still the most specific Isaac-specific grasp-timestep datum found.
7. **Eka's "1,500 operations/hour"** has no published denominator (one arm? a cell? what object
   mix? what failure rate counts?). MIT News and TechCrunch both attribute it to Eka.

---

## 8. Source list

| # | Source | Year | URL |
| --- | --- | --- | --- |
| 1 | ForceDelta-VLA: Distilling Force-Conditioned Action Corrections for Contact-Rich Manipulation (arXiv 2609.18242) | 2026 | https://arxiv.org/abs/2609.18242 |
| 2 | ForceVLA: Enhancing VLA Models with a Force-aware MoE (arXiv 2505.22159) | 2025 | https://arxiv.org/abs/2505.22159 |
| 3 | Eka Robotics — $150M Series A announcement | 2026 | https://ekarobotics.com/blog/eka-robotics-raises-150m-to-build-superhuman-intelligence-for-the-physical-world |
| 4 | TechCrunch — "Eka is worth $1.45B…" | 2026 | https://techcrunch.com/2026/10/20/eka-is-worth-1-45-billion-thanks-to-a-physical-ai-model-that-has-experts-raving/ |
| 5 | MIT News clip — TechCrunch Eka coverage | 2026 | https://news.mit.edu/news-clip/techcrunch-273 |
| 6 | WIRED — "I've Covered Robots for Years. This One Is Different." | 2026 | https://www.wired.com/story/when-robots-have-their-chatgpt-moment-remember-these-pincers/ |
| 7 | Tremblay & Cutkosky — Estimating Friction Using Incipient Slip Sensing | 1993 | http://bdml.stanford.edu/oldweb/touch/publications/tremblay_icra93.pdf |
| 8 | Westling & Johansson — Factors influencing the force control during precision grip | 1984 | https://pubmed.ncbi.nlm.nih.gov/6705863 |
| 9 | Johansson & Westling — Programmed and triggered actions to rapid load changes | 1988 | https://pubmed.ncbi.nlm.nih.gov/3416959 |
| 10 | Cole — Grip force adjustments evoked by load force perturbations | 1988 | https://journals.physiology.org/doi/pdf/10.1152/jn.1988.60.4.1513 |
| 11 | Seo et al. — Dependence of safety margins in grip force on isometric push force | 2009 | https://pmc.ncbi.nlm.nih.gov/articles/PMC8853688 |
| 12 | James & Lepora — Slip detection for grasp stabilisation with a multi-fingered tactile robot hand | 2021 | https://arxiv.org/abs/2010.01928 |
| 13 | Veiga, Edin & Peters — Grip Stabilization through Independent Finger Tactile Feedback Control | 2020 | https://www.mdpi.com/1424-8220/20/6/1748 |
| 14 | FORTE — Tactile Force and Slip Sensing on Compliant Fingers | 2025 | https://arxiv.org/html/2506.18960v3 |
| 15 | Event-Based Incipient Slip Detection Using DAVIS | 2018 | https://www.mdpi.com/1424-8220/18/2/333 |
| 16 | Universal slip detection of robotic hand with tactile sensing | 2025 | https://pmc.ncbi.nlm.nih.gov/articles/PMC11843555 |
| 17 | Force Control vs Tactile Sensing: Which Detects Micro-slip Earlier? (industry report) | 2025 | https://eureka.patsnap.com/report-force-control-vs-tactile-sensing-which-detects-micro-slip-earlier |
| 18 | Rigid Bodies — Omni Physics (combine modes, compliant contact) | 2026 | https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/rigid_bodies.html |
| 19 | Isaac Sim 5.1 — Physics Simulation Fundamentals | 2026 | https://docs.isaacsim.omniverse.nvidia.com/5.1.0/physics/simulation_fundamentals.html |
| 20 | Isaac Sim 5.1 — Rig Closed-Loop Structures (gripper tutorial, 80 Hz) | 2026 | https://docs.isaacsim.omniverse.nvidia.com/5.1.0/robot_setup_tutorials/rig_closed_loop_structures.html |
| 21 | Isaac Lab — isaaclab.assets (static/dynamic/viscous friction) | 2026 | https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.assets.html |
| 22 | Isaac Lab — isaaclab_physx.sim.spawners (compliant contact, combine modes) | 2026 | https://isaac-sim.github.io/IsaacLab/main/source/api/lab_physx/isaaclab_physx.sim.spawners.html |
| 23 | Kim et al. — Simulation of Parallel-Jaw Grasping using IPC Models | 2022 | https://autolab.berkeley.edu/assets/publications/media/2022-ICRA-IPC-GraspSim-kim-submission-highres.pdf |
| 24 | Black et al. — Real-Time Execution of Action Chunking Flow Policies (RTC) | 2025 | https://arxiv.org/abs/2506.07339 |
| 25 | Bronars, Park & Agrawal — Tune to Learn: How Controller Gains Shape Robot Policy Learning | 2026 | https://arxiv.org/abs/2604.02523 |
| 26 | Chi et al. — Diffusion Policy | 2023 | https://arxiv.org/abs/2303.04137 |
| 27 | Zhao et al. — Action Chunking with Transformers (ACT) | 2023 | https://arxiv.org/abs/2304.13705 |
| 28 | Black et al. — π0: A Vision-Language-Action Flow Model | 2024 | https://arxiv.org/abs/2410.24164 |
