# P52 frontier note — action-completion speed for chunked policies, and what would change *this* model

**Prepared:** 2026-10-27 · **Scope:** external literature only; no simulator run, no repo code change.
**Reading convention:** every claim carries `(Title, Year — URL)`. Each section ends with a
**measured** vs **claimed** split. Items that could not be verified from a primary source are marked
⚠ and collected in §6.

**What this note does *not* repeat.** `logs/p40/LIT_REVIEW.md` already established ForceDelta-VLA's
three-stage recipe, Eka VFA's unverifiability, the slip/grip-force literature, the PhysX friction
combine-mode material, and the RTC/VLASH latency results. `logs/p45/FRONTIER.md` already recorded
ForceDelta verified against its abstract, the delta robots' pick-rate claims, and the payload-mass
question. This note goes *deeper* on the one axis those two left as a pointer: **execution-time
re-timing of a chunked policy** — the formulation, the numbers, and the failure boundary — plus the
2026 model-side alternatives and a repo-anchored ranking.

---

## 0. The premise check that governs everything below (read this first)

The four strongest speed papers of 2025-26 all solve one problem: *a policy inherits the timing of
its demonstrations, and teleoperation is slow.* RACE states it as its motivation
(Time Optimal Execution of Action Chunk Policies Beyond Demonstration Speed, ICLR 2026 —
https://proceedings.iclr.cc/paper_files/paper/2026/file/fab80bb9d97e9b9ff5c19f91f72838c6-Paper-Conference.pdf);
SAIL formalises it as a new problem setting (SAIL, CoRL 2025 — https://arxiv.org/abs/2506.11948);
DemoSpeedup opens with "tardy demonstrations collected by human operators are the primary cause"
(DemoSpeedup, CoRL 2025 — https://arxiv.org/html/2506.05064v2).

**This tree does not have that problem.** Its demonstrations are emitted by a *scripted* cell, not by a
teleoperator, and that cell can run at any speed the owner chooses. The 15.0 s/attempt is not an
inherited constraint — P44's census showed **48 % of the 15.05 s cycle sits in three blocks
(`place` 3.35 s, `release` 2.04 s, `lift` 1.82 s) that are tick-clocked by a chosen profile**, and the
friction cone does not bind on `lift` (a = 1.0 of 1.962) or `place` (1.089 of 4.273) — AGENTS §2 "P44".
So:

* **What does not transfer:** the entire "beat the demo speed" framing, and every headline multiplier
  built on it (§1). A 4× policy speedup cannot give this tree a 4× cycle, because the learned policy
  does not own the cycle.
* **What does transfer, and is the real content of this note:** (a) *where* along a motion it is safe to
  be fast, which the frontier has now measured to a hard boundary (§2); (b) the *imitation target*
  change that makes a policy robust to execution timing (§1.1, §4.3); and (c) the latency arithmetic
  that bounds any speed-up of this repo's 30 Hz × 16-action loop (§5).

A second premise check, on the policy's share of the wall: P43's L2 measurement found the loop's pause
is **10.7 % of the episode wall** (model 47.4 ms + render 20.0 ms + camera 3.6 ms per decision) and
**84 % is the scripted primitive plus physics stepping** — so a policy-side speedup is capped at the
remaining ~16 % unless the primitive moves too (AGENTS §2 "P43"; `logs/p43/P2_RESULTS.md`).

---

## 1. Action-completion speed for chunked policies

### 1.1 RACE (ICLR 2026) — the re-timing formulation in full

**Identity.** *Time Optimal Execution of Action Chunk Policies Beyond Demonstration Speed*, Sunwoo Kim
(SNU), Jeongjun Kim (Vital Robotics), Joseph J. Lim (KAIST / Vital Robotics). ICLR 2026 poster, Fri
24 Apr 2026. (2026 — paper PDF
https://proceedings.iclr.cc/paper_files/paper/2026/file/fab80bb9d97e9b9ff5c19f91f72838c6-Paper-Conference.pdf;
OpenReview forum `INsLvSCJ4z`; project page https://clvrai.github.io/RACE/).

**Why naive fast-forwarding fails — the paper's own diagnosis (three named causes).**

1. *Altered transition dynamics.* The low-level controller is PD-like, so the force it applies over a
   shorter interval lands the robot at a *different* state than the demonstrated next state. In
   open-loop chunk execution that "state error" accumulates.
2. *Physical unreachability.* At high speed the required joint torque/velocity exceeds the limit, so no
   admissible control follows the path — the paper's framing is **reachability**, not tracking error.
3. *Asynchronous-inference misalignment.* The new chunk is computed from a stale state, so the robot's
   actual state may be outside the new path's controllable set, and generative sampling can bifurcate
   (a topologically different chunk), creating a discontinuity at the handover.

**The three-part solution, in the paper's own order.**

**(1) Reached states as actions.** Instead of `(s_t, a_t)` pairs, train/fine-tune on `(s_t, s_{t+1})` —
the *reached* state is the imitation target ("desired state" during rollout). Because the target is a
pose the robot actually attained, it is largely invariant to which controller tracks it, so the policy
can be run with a *different, higher-gain* controller at execution without the target itself shifting.
The paper is explicit that this matters even for absolute actions: "even when action commands are
absolute actions, there is a difference between the action and the reached state". A gripper-speed fix
is applied to *all* methods for fairness.

**(2) TOPP-RA retiming of the state chunk.** The chunk (a sequence of joint waypoints) is interpolated
by a **cubic spline with the current velocity as a boundary condition** to give a geometric path
`q(s)`, `s ∈ [0, s_end]`. TOPP-RA (Pham & Pham, 2018 — https://doi.org/10.1109/TRO.2018.2819195)
projects generalized second-order constraints
`A(q)q̈ + q̇ᵀB(q)q̇ + f(q) ∈ C` into the phase plane `x = ṡ²`, `u = s̈`, giving
`a(s)u + b(s)x + c(s) ∈ C(s)` with
`a = A q′`, `b = A q″ + q′ᵀB q′`, `c = f`. It discretises the path, runs a **backward pass** to build the
controllable sets `K_i` (intervals of squared speed that can still reach `K_{i+1}`), then a **forward
pass** taking the largest reachable `x`. Boundary conditions are set to `ṡ²₀ = 1`,
`ṡ²_{N,min} = 0`, `ṡ²_{N,max} = 1` — i.e. the first waypoint's speed is pinned and the last is left free
so the chunk does not decelerate merely because it ends. **If `K₀` is empty (the initial state is not
controllable) it falls back to the original control frequency and re-plans at the next waypoint until a
solution exists.** Torque and velocity limits are the constraints; a **0.9 safety margin** is applied
because "hitting exact torque limits can trigger protective stops due to unmodeled friction or noise".

**(3) Test-time search over chunks (only under async inference).** Best-of-N over sampled chunks, scored
by a length-normalised curvature functional

```
J(q(s)) = s_end / ∫₀^{s_end} ||q″(s)||² ds
```

The justification is not aesthetic — it is a *solvability* argument. In `b(s) = A q″ + q′ᵀB q′`, `q″` is
the only term that varies strongly across samples that share `(q(0), q′(0))`, so smaller curvature ⇒
smaller `|b(s)|` ⇒ a larger controllable set `K₀` ⇒ the TOPP solve succeeds from the drifted state. The
paper gives a proposition and proof in Appendix B.

**Measured numbers.**

*Simulation* — Robomimic Lift / Can / Square / Tool Hang, **diffusion policy, prediction horizon
Tp = 32**, 200 proficient-human demos, 1000 epochs, **200 rollouts per data point**, frequencies
20 / 40 / 80 Hz.

| Task | SAIL SR / SOD | **RACE SR / SOD** |
| --- | --- | --- |
| Lift | 0.930 / 2.520 | **0.995 / 2.068** |
| Can | 0.890 / 1.970 | **0.965 / 1.805** |
| Square | 0.750 / 1.620 | **0.805 / 1.819** |
| Tool Hang | 0.610 / 0.940 | **0.715 / 2.053** |

(RACE Table 1; SOD = speedup over demonstration = mean duration of successful episodes ÷ mean
demonstration duration.)

**Component ablation** (RACE Table 2):

| Method | Square SR / SOD | Tool Hang SR / SOD |
| --- | --- | --- |
| RACE | 0.86 / 1.74 | 0.62 / 1.86 |
| w/o TTS | 0.81 / 1.74 | 0.59 / 1.85 |
| w/o TOPP | 0.85 / 1.42 | 0.61 / 1.36 |
| w/o TOPP, TTS | 0.82 / 1.43 | 0.59 / 1.39 |

**Read this table carefully — it is the cleanest decomposition in the literature.** TOPP buys the
*speed* (+0.32 / +0.50 SOD) and costs essentially nothing in success; the test-time search buys the
*success* (+0.05 / +0.03) and no speed. Neither is doing both. In simulation, RACE reaches **>2× demo
speed without success degradation**, and in precision tasks it beats a naive 80 Hz (4×) fast-forward on
*both* axes — the naive 4× is where the success curve collapses.

*Real world, high precision* — Door Insertion (FurnitureBench), 150 demos, 50 rollouts per point,
10 / 20 / 40 / 80 Hz (8× excluded for async, "near-zero success"). RACE is Pareto-optimal and "achieves
task completion speed far past baselines, including one with an 8× acceleration rate", stated as **up
to 4× the original policy**; task times for the 8× arm were not comparable. (Per-point values are in
Figure 5, not in text — ⚠ not extracted.)

*Real world, throughput* — Fruit Packaging and Trash Cleaning, **π0.5 fine-tuned on DROID**, 15 objects,
15 Hz base vs 45 Hz naive vs async 15/30 Hz; RACE has the highest cumulative successes over 60 s in
both. The stated failure mode of the baselines: "missing the object when grasping".

*Real world, dynamics* — Conveyor Belt Pick, 106 demos (RACE Table 8):

| Method | SR @ original speed | Time | SOD | SR @ 2.5× speed | Time | SOD |
| --- | --- | --- | --- | --- | --- | --- |
| Base 15 Hz | 0.03 | 21.3 s | 0.61× | 0.00 | — | — |
| Base 45 Hz | 0.27 | 15.4 s | 0.84× | 0.00 | — | — |
| **RACE** | **0.63** | **9.8 s** | **1.32×** | **0.53** | **6.4 s** | **2.02×** |

Note the base policy here is *bad* (3 % at demo speed), so the 0.03 → 0.63 jump is not a
speed-vs-success trade — it is a badly-timed demo being retimed into a working one. Read it as evidence
that re-timing can repair timing, not that re-timing is free.

**Code availability: not verifiable.** The paper says "detailed implementations of our core algorithm are
available in the supplementary material. We will release the full codebase … upon publication"
(§Reproducibility). The project page `clvrai.github.io/RACE/` failed to fetch (TLS
`UNKNOWN_CERTIFICATE_VERIFICATION_ERROR`, twice); no GitHub repository surfaced (and ICLR 2026 is a
future-dated venue in this environment, ⚠ §6). **The one thing that *is* public is the solver**:
`toppra` (https://github.com/hungpham2511/toppra, docs https://hungpham2511.github.io/toppra) —
`SplineInterpolator(ss, way_pts)` + `JointVelocityConstraint` + `JointAccelerationConstraint` +
`algo.TOPPRA([pc_vel, pc_acc], path)`. That is enough to reproduce RACE's component (2) on any path,
including a scripted profile's, without their code.

### 1.2 RoboPace (Oct 2026) — the direct successor, and it runs on *this arm*

**Identity.** *RoboPace: Contact-Aware Time-Optimal Retiming for Action-Chunk Policies*, Takehiko
Ohkawa, Takuya Okubo, Nicola Scianca, Tatsuya Matsushima, Kei Ota. arXiv 2610.09696v1, 8 Oct 2026
(2026 — https://arxiv.org/html/2610.09696v1).

**Why it matters more than its citation count:** the platform is a **dual-arm 7-DoF OpenArm v1.0** with
YUBI hands, π0.5 fine-tuned end-to-end at **action horizon 32**, two wrist cameras, an RTX 5070 Ti. That
is the same arm family this repo drives. It is the only measured contact-aware re-timing result on an
OpenArm.

**The formulation it adds.** RACE's problem, plus one constraint (RoboPace Eq. 1):

```
min_{s(·),T}  T
s.t.  s(0)=0, s(T)=1, ṡ(t) ≥ 0
      |q̇_i(t)| ≤ v_max,i ,  |q̈_i(t)| ≤ a_max,i          i = 1..n
      v_b(t) ≤ v_contact   for each hand body b, if s(t) ∈ C
      ṡ(0) = ṡ₀
```

`C ⊂ [0,1]` is the **contact-critical set of path positions**. The Cartesian ceiling is converted into a
*position-dependent joint velocity ceiling* so it stays attached to the same waypoints when the timing
changes:

```
v_i(k) = (1 − g(k))·v_max,i + g(k)·min( v_max,i , v_contact·|q′_i(k)| / ℓ′(k) )
```

with `ℓ′(k)` the hand path-length derivative at waypoint `k`, and `g(k)` a cosine ramp rising 0 → 1
over `ρ` source steps on either side of the critical waypoint. `ℓ′ → 0` (hand stationary) imposes no
contact ceiling. Because both arms share one path parameter, **a contact constraint on either hand
slows both**. Boundary speeds are set by projecting the commanded joint velocity onto the new path
tangent and clipping to `[0, μ·ṡ_max(0)]`, `μ = 0.99`; the exit targets the largest admissible terminal
speed, relaxed ×1 / 0.75 / 0.5 / 0.25 / 0 until the solve is feasible, "so a chunk never decelerates
merely because it ends". Chunk-to-chunk blending is `qᵐ_blend = β_m qᵐ_new + (1−β_m) q_old(p+m)` with
linear / cosine / tanh schedules listed (Eq. 2–3).

**Contact cues (two, either can tighten the ceiling).** Geometric: hand-mesh proximity
`d_slow = 0.08 m` to the other hand, `d_env = 0.02 m` to the table. Learned: `stc`, the number of source
steps to hand–object contact, from the wrist camera + gripper angle at 10 Hz — EfficientNet-B0 + GRU,
**4.69 M parameters**, trained on 8,601 recordings from the same human demos (no extra data), predicting
0.1/0.5/0.9 quantiles of the countdown, median used. Threshold `stc_th = 20` source steps. **At contact
onset the median prediction is off by 0.80 source steps = 0.027 s, over 1,540 onsets.**

**Measured numbers** — three contact-rich tasks / five commands (Cup, Socks, Pyramid phases), 10 trials
per command, π0.5, H = 32, N_r = 16 requery, 30 Hz plan clock, `σ = 0.9`, `ρ = 4`,
`v_contact = 0.02 m/s` (0.04 for Socks), Linear-N3 blend:

| Arm | Success | Note |
| --- | --- | --- |
| **RoboPace** | **32/50 = 64 %** | no command below the decelerated rate; 45–59 % of decelerated `t_succ` on 4/5 |
| Decelerated, uniform 10 Hz | 22/50 = 44 % | 2–6× the demo-speed `t_succ` |
| Demo speed, 30 Hz | (Fig. 5) | RoboPace beats it on 4 of 5 commands |
| Accelerated, uniform 50 Hz (1.67×) | **4/50 = 8 %** | |
| **RACE-style** (kinematic limits only, RACE's 0.9 margin + chunk selection, no reached-state retraining) | **1/50 = 2 %** | task times not recorded |

**The `1/50` is the single most important number in this note** (§2). Sensitivity (Pyramid phase 2,
5 trials): `v_contact = 0.01` → 3–5/5 successes at 23–33 s; `0.02` → 4/6 schedules get 4/5 at 16–22 s;
`0.04` → ≤2/5 at 8–10 s. Success is *more* sensitive to the contact speed limit than to the blend
schedule. Hand speed under the gate: ungated motion has **median 0.17 m/s, peaks ~0.5 m/s**; gated
motion has **median 0.01 m/s** — a 17× asymmetry inside one trajectory.

**Stated limitation.** One robot, one policy family. And a telling one: while a hand still holds an
object the contact predictor stays at zero, so the camera cue keeps that hand contact-limited through
transport (they add a held-hand exclusion for the handover study only). **A naive port of this gate to a
pick-and-place would therefore slow the entire carry leg** — which is the opposite of this repo's need.

### 1.3 The other alternatives, with numbers where numbers exist

| Method | Mechanism | Measured | Cost / data |
| --- | --- | --- | --- |
| **SAIL** (CoRL 2025 — https://arxiv.org/abs/2506.11948) | 4 components: error-adaptive CFG guidance (EAG), reached-pose targets + high-gain tracking controller, adaptive speed modulation on a critical-action flag, latency-aware scheduling with `δ_t = max(c_t δ*, δ_lb)`, `δ_lb > δ_delay/(H_p − H_c)` | **up to 4× sim, 3.2× real**, 12 tasks; 6/7 real tasks improve TPR *and* SOD at 5×; **10× (`c_t = 0.1`) still improves TPR in ideal sim**; bimanual serving 5.4× throughput, ~1.8× SR | DP base; code linked from project page https://nadunranawaka1.github.io/sail-policy |
| **DemoSpeedup** (CoRL 2025 oral — https://arxiv.org/html/2506.05064v2) | *Training-time*: entropy-guided piecewise down-sampling of demos (proxy policy's action entropy → HDBSCAN precision/casual labels), replicate-before-downsample, geometrically-consistent chunk length | **~2× average, max 3×**; ACT 77 % → **82 %** at 2.1×; DP 55 % → **59 %** at 1.9×; ACT-2× 69 % at 1.7×; **naive test-time 2× down-sampling costs −8 % average success**; ablate RBD → 29 % (ACT) / 26 % (DP) | MIT code https://github.com/lingxiao-guo/DemoSpeedup |
| **DEHP** (arXiv 2606.11408v2, Aug 2026 — https://arxiv.org/html/2606.11408v2) | *Execution horizon* as the lever: a categorical head over `h ∈ {1..H}` conditioned on obs + the full predicted chunk, trained by PPO with the base policy **frozen**; SMDP formulation with a return-invariance proposition | **+23.03 % average** over the best fixed-horizon BC; one-leg **95.18 % vs 70.30 %** (best fixed = 24 actions); round-table **29.90 % → 93.80 %** (low rand), **18.50 % → 53.03 %** (medium); needle–syringe **10.20 % → 29.00 %** | 800 (FurnitureBench) / 1,000 (IsaacLab) trajectories; **no base-policy retraining** |
| **B-spline Policy** (arXiv 2607.09648, Jul 2026 — https://arxiv.org/abs/2607.09648) | Replace the discrete chunk with a continuous B-spline (knots + control points) so the trajectory can be **temporally scaled at execution** | Abstract claims "significantly reduces task completion time … while maintaining strong success rates" — **no numbers in the abstract** ⚠ | needs retraining the representation; project page https://b-spline-policy.github.io/ |
| **PACE** / **TRACT** / **TempoVLA** / **SpeedAug** / **AutoSpeed** / **ESPADA** | phase-aware horizon / temporally routed chunks / speed-conditioned policy / tempo-enriched policy + RL / stage-adaptive speed / semantic demo down-sampling | Citations verified via RoboPace's reference list (Nie 2026 arXiv 2606.00537; Liu 2026 arXiv 2607.29285; Jing 2026 arXiv 2606.06491; Nam 2025 arXiv 2512.00062; Hu ECCV 2026; Kim RA-L 11(9):10305, 2026). **Numbers not extracted** ⚠ | — |
| **RTC / masked action chunking** | async chunk continuity (freeze prefix, inpaint) | See p40 §5 for RTC's measured 480-episode battery; **ICLR 2026 masked chunking** is the newer sibling (Wang et al., ICLR 2026 — https://proceedings.iclr.cc/paper_files/paper/2026/file/c35834443b7881e782e52b3519fe27c7-Paper-Conference.pdf) | inference-only |

**The practical convergence.** Every one of these, arrived at independently, does the same thing: it
changes *when* to be fast, not *how fast the network is*. RACE: TOPP under limits. SAIL: critical-action
flag × preset rates. DemoSpeedup: entropy-labelled segments. RoboPace: contact-gated ceiling. DEHP:
per-step horizon. **None of them reports a win from making the model itself faster** — the model-side
speed literature (distillation, parallel decoding) is explicitly framed by RACE as "complementary".

### 1.4 Measured vs claimed — §1

**Measured.** RACE's Table 1/Table 2 (200 rollouts/point, 4 tasks, SAIL's numbers re-run by SAIL's own
authors with torque constraints on), the Door Insertion and conveyor tables, the 2× / 4× statements.
RoboPace's 32/50 vs 22/50 vs 4/50 vs 1/50, the `v_contact` sensitivity, the 0.027 s contact-prediction
error, the 0.17 vs 0.01 m/s gated speed. SAIL's 4×/3.2× and its ablation magnitudes. DemoSpeedup's
per-task table and the −8 % naive-acceleration figure. DEHP's +23.03 % and per-task rates.

**Claimed / weaker.** RACE's "Pareto-optimal" is a *within-suite* claim on Robomimic, whose base
success rates are already 0.6–1.0 — a 4-task suite cannot separate a real effect from a lucky attractor
(this tree's own AGENTS §2 is the same warning). RoboPace's "64 % vs 44 %" is **one robot, 50 trials,
no timeout, operator-stopped trials scored as failures** — a real but small-n result, and its own §5.3
handover analysis is explicitly *qualitative, one run*. SAIL's "up to 4×" is a maximum, not a mean, and
its own limitation section concedes object–robot dynamics are unmodelled (a can is "thrown out of the
workspace"). DemoSpeedup's "up to 3×" likewise. B-spline's speed claim is unquantified in the abstract.

---

## 2. The speed/success trade-off — what is actually measured

### 2.1 The measured ladder (the strongest evidence in the whole note)

RoboPace ran the ladder on **one policy, one robot, one set of action chunks**, varying only execution
timing (RoboPace §5.2, 10 trials × 5 commands):

| How the same chunks are executed | Success | Δ vs demo speed |
| --- | --- | --- |
| Uniform **10 Hz** (decelerated, 3× slower) | 22/50 = 44 % | pays 2–6× time |
| Uniform **30 Hz** (demo speed, the training rate) | (Fig. 5) | reference |
| Uniform **50 Hz** (1.67× faster) | **4/50 = 8 %** | ≈ −0.9 of the rate for +0.67× speed |
| **RACE-style** kinematic-limit retiming (faster in free space *and* at contact) | **1/50 = 2 %** | the *fastest* arm is the *worst* arm |
| **Contact-gated** retiming (same speed in free space, ≤0.02 m/s at contact) | **32/50 = 64 %** | +0.2 over the *slowest* arm, at half its time |

**This is the result to design against, and it says something sharper than "there is a trade-off":**

1. **The trade-off is not speed vs success in general — it is speed *at contact* vs success.** The
   contact-gated arm is *faster than the demo* on 4 of 5 commands and *more successful than the slowest
   arm*. There is no global speed/accuracy frontier here; there is a *position-dependent* one.
2. **A 1.67× uniform increase already costs 84 % of the success rate** on contact-rich, precision work.
   That is the honest safe-ratio datum for a hard contact task, and it is far below the 2–4× headlines.
3. **Kinematic limits are not the binding constraint at contact.** RACE-style, which respects every
   joint torque and velocity limit exactly as RACE prescribes, is *worse than doing nothing* (1/50). The
   binding constraint is the *contact* one, which no amount of correct dynamics modelling supplies.
   This directly refutes the intuition that "the robot can physically do it, so it is safe".

### 2.2 Corroboration from three other directions

**SAIL's ablation on the imitation target** is the second-strongest number here: replacing reached poses
with commanded poses as the training target **drops success by 55 % on Square and reduces average TPR by
0.08** (SAIL §5.1, Table K.6); removing adaptive speed modulation costs **up to 31 %** on Square and Mug.
So of SAIL's four components, the two that matter most are (a) *what you imitate* and (b) *where you slow
down* — again not the controller, not the network.

**SAIL's failure taxonomy at 5×** (their Fig. 8, from real rollouts) names exactly the mechanisms this
repo already measures:
*imprecise grasping* (grasping two cups, missing the eraser/chicken), *low-fidelity tracking*
(colliding with other cups, missing a handle), *jerky motion* (fruit drops). The last one is this tree's
`carried-not-placed` class. SAIL's own conclusion: it "does not explicitly tackle the dynamics shift of
robot–object interaction", and it is "slightly worse than DP in the wiping task … the high-gain tracking
controller's inability to adjust to the new robot–object dynamics (sustained contact during wiping) at a
higher speed". **Sustained contact is the exception in every paper that tests it.**

**DemoSpeedup's −8 %** for naive test-time down-sampling (vs +5 % success for the *training-time*
version at the same speedup) is the third: the same nominal speed-up applied at execution and applied to
the data have opposite signs. Restated: **the distribution shift is in the observation distribution the
policy sees, and it can be removed only by putting the shifted observations into training.**

**DEHP's noise result** is the fourth and it is quantitative about *why*: the best fixed execution
horizon **depends on the execution-noise level** — at low action noise, executing 6 actions per chunk is
best; at noise 0.15, **executing 2 beats executing 6** (DEHP §4.1, 1,000 environments × 3 seeds). Faster
chunk consumption under error means *more* frequent replanning, not less. This is the measured form of
"short chunks help only if you re-plan more": a speed-up with a *fixed* horizon converts execution error
into drift.

### 2.3 Mitigations, ranked by measured effect

| Mitigation | Measured effect | Source |
| --- | --- | --- |
| **Contact-aware speed ceiling** (position-dependent) | 1/50 → **32/50** at ~half the slow arm's time | RoboPace 2026 |
| **Reached-state imitation target** | commanded → reached costs **55 % SR** (i.e. the fix is worth up to that) | SAIL 2025 |
| **Adaptive speed modulation** (slow at critical actions) | removing it costs **up to 31 %** | SAIL 2025 |
| **Test-time smoothness search** (best-of-N curvature) | +0.05 / +0.03 SR at equal SOD; recovers async misalignment | RACE 2026 |
| **Training-time demo re-timing** (entropy-guided) | **+5 points** over naive at the same speedup; −8 % if done at test time | DemoSpeedup 2025 |
| **Dynamic execution horizon** | **+23.03 %** average over best fixed horizon | DEHP 2026 |
| **Force-conditioned residual** | +11.7 points over the teacher; +200 ms latency penalty −15 vs −25 | ForceDelta-VLA 2026 (§3) |
| **Higher policy rate** | ⚠ **negative** for jitter: 21.8 % jitter failures at 100 Hz vs 5.0 % at 10 Hz | Tune to Learn 2026, via p40 §5.2 |

### 2.4 The safe-ratio evidence, stated as a rule

Collected from the papers that measure both axes:

* **Free space, no contact, quasi-static:** 2–4× is safe with a good retimer (RACE 2× sim / 4× real;
  SAIL 4× sim / 3.2× real; DemoSpeedup 2–3× training-time). Up to **10×** remains throughput-positive in
  *ideal simulation* (SAIL).
* **Contact-rich, precision, real hardware:** **1.67× uniform costs 84 % of success** (RoboPace); the
  safe ratio at contact is *below* demo speed, with the paper's operating point at **0.02 m/s hand speed**
  — and its own sensitivity table shows 0.04 m/s halves the success count (≤2/5 vs 4/5).
* **The ratio is not a scalar.** RoboPace's own trajectory contains 0.17 m/s median free-space motion
  (peaks 0.5 m/s) and 0.01 m/s gated motion — i.e. **the correct object is a speed *profile* conditioned
  on predicted contact, not a multiplier.**

### 2.5 Measured vs claimed — §2

**Measured.** The RoboPace ladder (the five rows above), its `v_contact` sensitivity, SAIL's 55 % / 31 %
ablations and its 6/7-task real result, DemoSpeedup's −8 %/+5 % contrast, DEHP's noise-dependent horizon,
Tune to Learn's jitter fractions.

**Claimed / weaker.** That these ratios transfer across robots (RoboPace: "limited to one robot and one
policy family"; SAIL: two platforms). That "4×" is a property of a method rather than of a task suite.
RACE's claim that its speed-ups do not degrade success is *true on its four tasks* and *refuted on
RoboPace's three* — the difference is task contact-richness, which is the variable this repo should care
about. No paper reports a per-*phase* safe ratio measured on the same hardware, which is exactly the
measurement this repo is positioned to make.

---

## 3. Force/state correction layers at the *execution* level (the ForceDelta line, deeper)

p40 §1 and p45 §1 already cover *what ForceDelta-VLA is* (the three-stage paired-prediction
distillation, the 82.2 / 54.4 / 70.6 means). What was not extracted there, and is what decides whether
the shape is implementable here, is the **execution contract**: latency, bounds, expiry, and what the
residual is structurally unable to fix. Source for this section: arXiv 2609.18242v1
(https://arxiv.org/html/2609.18242v1), §III-E, §IV-C, §IV-D, §IV-F.

### 3.1 The execution contract, stated exactly

| Property | Value | Consequence for a 120 Hz loop |
| --- | --- | --- |
| Reference (slow) forward pass | **189.7 ms** avg | 22.8 physics ticks at 120 Hz — the reference is ~23 ticks stale on arrival |
| Correction forward pass | **2.43 ms** | **3.4× margin** inside one 8.33 ms tick; it could run every tick |
| Robot command transmission | limited to **100 Hz** (10 ms) | the correction was designed to fit a 10 ms interval; ours is 8.33 ms — still fits |
| Correction horizon | **K = 5** pose corrections | 5 steps at the action-sample rate, i.e. sub-chunk, not chunk-length |
| Reference chunk | **H = 50** steps at 30 Hz | 1.67 s of motion per reference — much longer than this repo's 0.53 s |
| Bounds | "**clips the two corrections separately**" — *no numeric clip range is given in the main text* ⚠ (§6) | the bound exists but is unpublished; any port must choose its own |
| Expiry | "Expired steps are skipped; a valid correction step is held until its next timestamp or a newer valid result becomes available" | timestamped, self-healing; a missed correction degrades to the reference, it does not fail |
| Dove into the pipeline | between the reference action and the executor, in **normalized pose coordinates** (translation + continuous 6D rotation, then Gram–Schmidt) | corrections are pose-only; **the gripper command is taken from the reference unchanged** |

Two structural facts follow, and they are the reason to be careful:

1. **The residual cannot reverse.** The paper's own failure analysis: "Once the connector jammed, the
   reference action often continued advancing, and the corrected motion did not retreat far enough to
   clear the jam and retry." A correction layer bounded around a moving reference inherits the
   reference's *direction*; it can trim, not turn around.
2. **Pose-only, gripper from the reference.** So it is a *pose/alignment* correction, not a grip-force
   correction. For this repo's closed carry class it is therefore the wrong actuator — which is
   consistent with p40's E1/E6 ranking and with `logs/p42/SIM_LIMIT.md`.

### 3.2 The measured deltas that matter for a fast layer

From the ablation table (20 trials/variant × 4 tasks) and the latency sweep:

| Change | Effect |
| --- | --- |
| Remove the **force** correction | **−15 / −17.5 points**; peak force **+3.7 / +4.3 N** |
| Remove the **delay** correction | **−7.5 points** on both platforms |
| **Single combined** correction head | **−10 points** on both |
| Demonstration-derived target instead of paired-teacher | **−12.5 / −17.5 points** |
| No asynchronous **schedule replay** | **−7.5 / −12.5 points** |
| +200 ms reference latency | success **−15 points** (the teacher alone: −25); peak force +3.7 N (teacher +9.6 N) |
| Zeroed force *input* but branch kept | worse than removing the force output entirely — the branch provably uses force |

**The delay head is the transferable one for this tree.** Its target is

```
ΔA^delay_{T,k→t,j} = P(A^ref_{T,t|k,j}) − P(A^ref_k(t_j)) + Γ(S_t, S_k)
```

i.e. *the difference between a reference computed at an older state and what the current state would
produce, plus a state-alignment term*. This repo's W7-B finding is the same pathology in a different
costume: a **fixed 0.9 s handover lead** against a measured **1.36–7.68 s** setup on every no-contact
failure (AGENTS §2 "W7-B"), and R10-A.1's just-in-time handover that removes the hover settle. ForceDelta
is the published evidence that (a) treating staleness as an explicit supervised target is worth ~7.5
points, and (b) a *constant* lead cannot be right, because the quantity being corrected is a function of
the current state.

### 3.3 What is testable in a 120 Hz scripted+policy hybrid — and what the test would mean

The repo has the three ingredients ForceDelta needs *at inference*: 120 Hz physics (8.33 ms), per-finger
force readouts in the `[carry]` / `FRUIT_GRIP_EFFORT` rows, and a TCP pose read (`[attitude]`, one read
per carry leg, P39). A **hand-written, bounded pose residual** evaluated every tick is therefore
implementable with no teacher and no distillation:

```
a_cmd(t) = a_ref(t)              ← the policy's (or the profile's) current pose command
         + clip( Δ̂_force(t) ,  ±δ )   ← from the finger-force derivative / asymmetry
         + clip( Δ̂_delay(t) ,  ±δ )   ← from (current pose − pose the reference was computed at)
```

**What the latency budget allows.** At 120 Hz the tick is 8.33 ms; a 2.43 ms-equivalent correction
network plus a force read fits with 3.4× margin, and even a 5 ms hand-written evaluation fits with 1.7×.
**What it cannot do:** run at the reference's 30 Hz and still react, because 33.3 ms is 4 ticks — the
layer's whole point is to be evaluated *between* reference updates.

**The honest prior for this repo is low, and the reason is measured, not assumed:** the carry class is
closed (`logs/p42/SIM_LIMIT.md` — the pads hold and the payload slides; the force family measured
negative at 10/30/60 N and at 0.25× mass), and the acquisition class is a *timing/selection* problem
(§5). A force-conditioned *pose* residual has no measured target in either. The one gap it would address
— the handover lead's variability — is better addressed directly (make the lead state-dependent) than
through a learned corrector, and the repo has already measured that a *learned* corrector on this
interface does not transfer (three recollections, R9's RWR iteration).

### 3.4 Measured vs claimed — §3

**Measured.** 189.7 / 2.43 ms and the 100 Hz command limit; the six ablation magnitudes; the latency
sensitivity curve; the failure analysis (jam → no retreat).

**Claimed / unpublished.** The correction clip bounds (⚠ — the placeholder `clip()` above is *this note's*
choice, not the paper's). The paper's internal claim that the delay head generalises beyond sampled
schedules. That the 26 % peak-force reduction would appear on a *grip*-limited system — it will not, by
the paper's own pose-only construction.

---

## 4. The 2026 "big model" alternatives — could any be a genuine overhaul here?

### 4.1 Is a bigger/faster VLA the answer? The measured answer is *no for this task class*

The most useful single source is a survey-level statement from someone who reviews the field: on the
standard sim benchmarks, **"LIBERO is basically solved and showing 99 % vs 98 % is not very helpful and
you don't need VLAs and large-scale pretraining to get competitive results"**, and "a properly tuned
Diffusion Policy can get you there without VLAs although the most cited DP baselines is showing worse
results" (State of VLA Research at ICLR 2026, Reuss, 2025 —
https://mbreuss.github.io/blog_post_iclr_26_vla.html). The same post records that all four concurrent
*discrete-diffusion* VLAs land at **95–98 %** LIBERO average — i.e. the benchmark cannot discriminate, so
none of those numbers are evidence about this repo's problem.

That survey is secondary (⚠ §6), but it is corroborated by the primary results in this note: the two
papers that *do* measure a pick-and-place line with a real cost accounting (RoboPace, RACE) both get
their wins from the **execution layer, not the model**, and RACE's own real-world throughput tasks use a
π0.5 fine-tuned on DROID with **no additional data collected**.

**The one model-side idea that is genuinely interesting:** *HYPERVLA — Efficient Inference in
Vision-Language-Action Models via Hypernetworks* (ICLR 2026 submission, OpenReview `bsXkBTZjgY`, as
summarised by Reuss 2025 — URL above) uses a hypernetwork to **generate a small task-specific policy
conditioned on the language instruction and initial image**, so that only the compact generated policy
runs during execution. This is the correct shape of "big model" for a fixed cell: **pay the big model
once, offline; execute a tiny one.** It is the same economics as this repo's scripted-primitive-plus-
policy split, arrived at from the model side. ⚠ Numbers not verified (submission-stage, no table read).

### 4.2 Flow matching vs DDIM at equal compute — the honest state of the evidence

**No primary robotics head-to-head at equal NFE was found.** What exists:

* A **structural** argument: flow matching's linear interpolant makes the probability path straighter, so
  a first-order solver needs fewer steps — commonly quoted as ~10 NFE for an FM Heun solver vs 30–50 for
  DDIM (Diffusion model vs flow matching, Paiteq, 2026 — https://www.paiteq.com/blog/diffusion-vs-flow-models).
  That is an **image-generation** source and a vendor blog ⚠; it is a claim about NFE, not about
  manipulation success.
* A **robotics** datum on the related question of generative-vs-regression: "both methods achieve high
  success rates on the training distribution, which aligns with recent findings by Pan et al. (2026).
  However, the generative approach exhibits significantly higher resilience to environmental
  perturbations, whereas the regression variant fails to generalize" (Action-to-Action Flow Matching,
  arXiv 2602.07322v2 — https://arxiv.org/html/2602.07322v2). **So at equal in-distribution success, the
  generative head's value is robustness, not accuracy** — which argues against replacing DDIM with a
  regressor to buy speed, and says nothing in favour of swapping DDIM for FM.
* RoboPace notes a *system-level* cost of the DP/DDIM head that FM would not fix: "this is partly due to
  the DP inference delay. The sudden pause caused by the delay between faster movements can make the
  motions of DP a little more jittery" (DemoSpeedup §4.2, 2025 — https://arxiv.org/html/2506.05064v2).

**Verdict for this repo: not worth a retrain.** The repo's DDIM head runs 16 actions per forward pass;
the cost that binds is the 71 ms *decision* cost (model 47.4 + render 20.0 + camera 3.6) of which the
sampler is a minority — so a 2–3× sampler speed-up buys at most ~1–2 % of the episode wall.

### 4.3 Action space: delta vs absolute, joint vs Cartesian — the one place the frontier agrees

| Evidence | Direction | Magnitude |
| --- | --- | --- |
| SAIL trains on **reached absolute EE poses** vs commanded poses | reached ≫ commanded | **55 % SR drop on Square**, −0.08 TPR, when built from commanded poses |
| RACE trains on **reached/desired states** vs action commands | states ≫ commands | the ablation baseline (State Fast-forward) sits *below* RACE on every task; without it, 80 Hz naive "rates a similar success rate" only on Tool Hang |
| RoboPace converts *body-frame pose deltas* → SE(3) targets → joint waypoints via damped-least-squares IK, truncating at a **0.15 m** Cartesian residual and dropping only unreachable waypoints | deltas are fine *if* you IK them and truncate the unreachable tail | the mechanism that lets it reuse a delta-chunk policy |
| ⚠ "absolute action spaces … memorization" vs "delta actions … fast error accumulation" (Rho, arXiv 2609.38164v1, 2026 — snippet only) | contested | not verified |

**The repo-relevant reading.** This tree has a *systematic, already-measured* commanded-vs-reached gap:
**every descent ends 40–90 mm short** because the pick pose is outside the reachable band, and the
post-descent solver finishes the approach (AGENTS §2; `logs/160/161`). Any policy trained to imitate the
*commanded* pose on such a leg is being asked for an unattainable target — and the frontier's largest
single ablation (SAIL's 55 %) says that is worth more than any execution layer. **This is the strongest
model-side idea in the note, and it is a relabelling, not a new architecture.**

### 4.4 Compute and data cost, stated for each candidate

| Candidate | Data | Training cost | Inference cost |
| --- | --- | --- | --- |
| RACE (retiming only, no retrain) | 0 new | 0 (uses existing policy) | TOPP-RA per chunk; `toppra` is a pip package |
| RACE (reached-state retrain) | existing demos + reached-pose labels | ~1 policy retrain (DP, Tp = 32, 1000 epochs on 200 demos) | unchanged |
| RoboPace (retiming + gate) | 0 new for the gate's geometric cue; 8,601 recordings for the 4.69 M-param predictor | ~1 small CNN+GRU train | 10 Hz predictor + TOPP-RA per chunk; RTX 5070 Ti |
| DEHP (horizon head) | 800–1,000 trajectories for the *base*; head trained by online RL | base frozen, **head-only PPO** | one extra forward pass per decision |
| ForceDelta (full) | 200 demos × 9 tasks | 3 stages, 2× RTX 4090 | 2.43 ms correction + 189.7 ms reference |
| π0.5-class VLA | 8,736 + 5,288 episodes (RoboPace) or DROID-scale (RACE) | full fine-tune | 97 ms model, **108 ms** total static / **139 ms** mobile (Real-Time Action Chunking, PI, 2026 — https://www.pi.website/research/real_time_chunking) |
| HYPERVLA | as above + a hypernetwork | one hypernet train | a *small* generated policy at execution ⚠ |

**The comparison that matters for a 125 GB, one-workstation project:** DEHP's head-only PPO and RACE's
TOPP-RA are the only two entries whose cost is *not* a retrain of the action generator; everything else
in this table is a full retrain of a policy that has already had three recollections read no-gain
(P33/P37/R9).

### 4.5 Measured vs claimed — §4

**Measured.** SAIL's 55 % / 31 % ablations; RACE's Table 2; RoboPace's IK/truncation design and its
32/50; DEHP's +23.03 %; the π0.5 latency table (97 / 108 / 139 ms); Action-to-Action FM's
generative-vs-regression claim on training distribution.

**Claimed / unverified.** LIBERO saturation as an argument (secondary source, and "solved" is a claim not
a measurement of this task). HYPERVLA's numbers ⚠. The FM-fewer-NFE figure ⚠ (image domain, vendor blog).
The Rho action-space remark ⚠ (snippet). **No paper measures flow-vs-DDIM at matched wall-clock on a
pick-and-place cell**, so any claim that swapping samplers would help here is unsupported.

---

## 5. Ranked, testable for this repo

Ranking logic: expected value = P(mechanism is live in *this* tree) × (effect on the owner's target:
**action-completion speed first, success second**) ÷ cost. Anchors used throughout: the scripted demo
speed is **15.0 s/attempt**; the policy runs **30 Hz of sim, 16-action chunks, 4 control ticks per
action**; the loop's pause is **10.7 %** of the episode wall (model 47.4 + render 20.0 + camera 3.6 ms
per decision) and **84 % is the scripted primitive + physics**; the direct baseline with the park is
**right 94.6 % (53/56) / left 4.8 % (1/21)**; **every recollection has read no-gain** (P33 8/45 vs 16/45;
P37 no gain over `moe_v13s`+park; R9 18/75 vs 25/75; W7-C 13/45 vs 10/45 → W8-A 22/75 vs 21/75).

### E1 — Contact-gated speed ceiling on the scripted profile (the RoboPace mechanism) ★ highest EV

**What.** Keep the P44 speed cells' fast free-space motion, but replace the *global per-leg* `v_max` with
a **position-dependent ceiling** that binds only inside a window around the station approach, the place
release band and the belt contact. Concretely: `v_i(k) = (1−g)·v_max,i + g·min(v_max,i, v_contact·|q′_i|/ℓ′)` with a
cosine ramp over a few ticks, exactly as RoboPace Eq. 4, evaluated inside the existing per-leg profile
(`tasks.py`'s `_SPEED_SHIPPED` block already has the per-leg override plumbing). Default off.

**Why it should work here — the evidence is a match, not an analogy.** P44 measured that each speed cell
buys time and costs **one new `fruit did not follow the gripper` row per cell**, with the pad span at
onset 59–63 mm → the failure is **pre-contact acquisition**, i.e. the fast leg *re-times which fruit is
offered at the close* (P46 named the same class on the two-line). RoboPace is the measured fix for
exactly this shape: kinematic-limit-only retiming **1/50**, contact-gated retiming **32/50** on the same
chunks. The gate is the difference between the two arms, and it is a ~20-line change.

**Cost.** Low: one knob + one A/B; **but both motion references move** (a position-dependent ceiling
changes the branch), so budget two re-records and the `190` two-line gate.

**Read.** `carried-not-placed` pairing, the acquisition class count, `s/attempt` and placed/min, and
`[motion]`'s per-leg `|v|max` (the ceiling must *not* exceed the reference's profile peak on any gated
leg). **Kill:** the gate fires on >20 % of ticks with no acquisition-class movement, **or** the recovered
time is <0.3 s/attempt (then the P44 blocks are not where the speed was going).

### E2 — Retarget the policy's imitation labels from commanded to reached poses

**What.** Re-collect (or re-derive from the logged TCP reads) the direct-path demonstrations with the
**achieved** pose as the action label instead of the commanded pose, and retrain. This is RACE component
(1) and SAIL component (2) — the two papers' *largest single ablation* (SAIL: **55 % SR drop** if you use
commanded poses; RACE: Table 2's `w/o TOPP,TTS` baseline is the commanded-action arm).

**Why here, specifically.** This tree has a documented **40–90 mm** commanded-vs-reached shortfall on
*every* descent (the pick pose is outside the reachable band), and the direct path's flail class is
"close starting 0.17–0.92 m downstream, joint at its limit" with capped 3.33 s pre-moves (R2). A policy
trained to hit a pose the arm cannot reach is being supervised toward a target that is *known
unattainable* — RACE/SAIL's exact premise, and the flail/pre-move-cap class is its symptom. Removing the
caps is a **speed** win (3.33 s of dead time per capped pre-move) as well as a success win.

**Cost.** Medium: one recollection + one fine-tune (the repo's standard `40`→`41`→ fine-tune path), plus
verifying the collector actually stores the reached pose per tick (⚠ — **check `40_collect_demos.py`'s
recorded fields first; if only commands are stored, this needs a collector change and a fresh shard**).

**Read.** The flail count and capped pre-moves (R2's table), close-start offset, right-arm placed rate
(the 94.6 % baseline), and cycle. **Kill:** the measured commanded-vs-reached residual on the policy's own
pre-grasp legs is **<5 mm** — then there is nothing to retarget and the hypothesis is dead. Measure that
*first*, offline, from existing logs; it is a ~10-minute check and it gates the whole experiment.

### E3 — Execution-horizon knob (DEHP's lever, no RL)

**What.** Expose the executed prefix length `s` (currently the full 16) as a default-off knob and sweep
`s ∈ {16, 12, 8, 4}` per phase, with the re-plan continuity the repo already has (the policy is
re-queried per chunk).

**Why.** DEHP's measured result is that the best fixed horizon is task- and noise-dependent (**6 at low
noise, 2 at noise 0.15**, +23.03 % average over the best fixed horizon, and **one-leg 95.18 % vs 70.30 %**
for a *frozen* base policy). This repo has never swept it — it runs 4 control ticks per action and
consumes the whole 16-action chunk.

**The arithmetic that bounds it (do this before spending a run).** With a per-decision cost of 71 ms and
a 33.3 ms action, SAIL's floor `δ_t > δ_delay/(H_p − H_c)` gives `s ≤ H_p − δ_delay/δ_t = 16 − 2.13 ≈ 13`
actions at 30 Hz. So `s = 16` is *already* over the floor by ~2 actions, and **`s` cannot go below ~13
without also cutting inference cost** — which is why this ranks third, not first: the knob's interesting
range is mostly blocked. It becomes interesting only if the model is made cheaper (§4.2) or the chunk
longer. **Read:** placed rate, acquisition class, `s/attempt`. **Kill:** all four horizons reproduce
within the attractor (fingerprint matches) — then the horizon is not a lever here, which is itself a
useful negative.

### E4 — Adopt one P44 speed cell with its own pre-registration (the owner's actual speed question)

**What.** S1 (`FRUIT_SPEED_PLACE=0.52`) is the largest **clean** single cell: `place0` −135.4 ticks,
`place1` −64.2, **−1.13 / −0.53 s**, 6/10 at **both** seeds (P44 amend §9). The union
(`FRUIT_SPEED_ALL`) buys **−1.45 s/attempt** but fails E2 on seed 6 (**5/10 vs 8/10**).

**Why it is here and not higher.** The speed is real and reproducible; the **count** is branch-drawn
(P46: seed 5 +12 %, seed 6 −2 placed). So the honest adoption is S1 with a pre-registered 2-seed
confirmation and the two reference re-records — and it is *the* lever that actually moves the 15.0 s
anchor (unlike E3, which is bounded by latency). **Read:** `s/attempt` primary, placed count secondary and
attractor-named; report the acquisition class as the *documented* cost, not as a fix. **Kill:** a new
failure reason, or the seed-6 branch repeats 5/10.

### E5 — The force/state residual (ForceDelta shape), scoped to the handover, not the grip

**What.** Only if E1-E2 leave the handover class alive: a **hand-written** bounded pose residual whose
delay term is state-dependent, replacing the fixed 0.9 s lead. Not a distillation, not a learned head.

**Why last among the positives.** The measured target is thin: the carry class is closed
(`SIM_LIMIT.md`), the grip force family measured negative at 10/30/60 N and 0.25× mass (P41/P45), and
this repo's own learned-corrector attempt (R9's AWR iteration) read **18/75 vs 25/75**. ForceDelta's
7.5-point delay-head ablation is the only support, and it needs a *frozen teacher with a force-agnostic
twin* this project does not have. **Kill:** E2 shows the handover is an acquisition-timing artefact, in
which case fix the lead directly.

### E6 — A flow-matching head or a HYPERVLA-style distilled task policy (explicitly *not* recommended now)

**What.** Swap DDIM for FM at equal NFE, or distil a small execution policy offline.
**Why not now.** §4.2: **no primary evidence at equal compute** for a manipulation cell, and the sampler
is a minority of the 71 ms decision. §4.1: the model is not the bottleneck — 84 % of the wall is not the
policy at all. A retrain here would be the **fourth** post-training pass on an interface that has read
no-gain three times. Re-entry condition: a measured demonstration that the *decision cost* (not the
sampler) is the binding term after E1-E4.

### 5.1 What would NOT transfer — stated once, with the reason

1. **"4× faster than the demonstration."** This tree has no demonstration-speed constraint: the demos come
   from a scripted cell that can run at any speed, and the 15.0 s is a *profile choice* (P44: 48 % of the
   cycle in three profile-clocked blocks, cone not binding). Every headline multiplier in §1 is a
   solution to a problem this tree does not have. The transferable content is *where* to be fast.
2. **The absolute success numbers.** RoboPace's 64 % is π0.5 at H = 32, 50 trials, contact-rich assembly;
   this tree's direct right arm already reads **94.6 %**. Nothing in §1-2 predicts a gain from adding a
   slower layer to a policy already at its ceiling.
3. **RACE's "2× without degradation."** Refuted on contact-rich hardware by RoboPace (**1/50** for
   RACE-style). Do not import the headline; import the gate.
4. **DemoSpeedup's premise.** Its method assumes demos are slow *because teleoperators are slow*. Here the
   demos are scripted and can be regenerated at any speed — the constraint is success, not speed, so the
   *training-time* half of its argument has no purchase. (The −8 % vs +5 % contrast still transfers as a
   warning.)
5. **The ForceDelta distillation.** Three stages, a frozen force-aware teacher, a force-agnostic twin,
   and 200 demos × 9 tasks; this project's three recollections and one RWR iteration all read no-gain, and
   its own ablation says the *paired-teacher target* is worth 12.5–17.5 points over a demonstration-derived
   one — i.e. the cheap version is the one that does not work.
6. **The delta robots' 100–200 picks/min.** A parallel-kinematic architecture on a different task
   (p45 §3); the gap is not a tuning constant.
7. **"Raise the policy rate."** Measured *negative* for jitter (21.8 % at 100 Hz vs 5.0 % at 10 Hz, Tune
   to Learn 2026 via p40 §5.2). The right shape is a high-rate inner loop under a moderate-rate policy —
   which is what this tree's 120 Hz scripted primitive already is.

---

## 6. Could not verify / low confidence

1. **RACE's code.** "We will release the full codebase … upon publication" + supplementary material; the
   project page `clvrai.github.io/RACE/` failed twice with a TLS `UNKNOWN_CERTIFICATE_VERIFICATION_ERROR`
   and no GitHub repo surfaced. The *solver* is public (`toppra`), so component (2) is reproducible
   without their code; components (1) and (3) are described completely enough to re-implement but were
   not verified against released code.
2. **RACE's per-point real-world values.** Door Insertion's Figure 5 and Fruit Packaging's Figure 6 are
   plots; only the aggregate statements ("up to 4×", "past an 8× baseline", "highest cumulative
   successes") are in text. The 8× arm's "near-zero success" is stated for async only.
3. **ForceDelta's correction clip bounds.** §III-E says corrections are "clipped separately" but the
   numeric range is in the supplementary, not the main text. Any port must pick its own — flagged in §3.
4. **HYPERVLA.** Read from Reuss's ICLR-2026 survey (a secondary source) as an OpenReview submission
   (`bsXkBTZjgY`); no numbers extracted, and submission-stage status means the final paper may differ.
5. **Flow matching vs DDIM at equal compute in robotics.** *No primary source found.* The NFE figures
   quoted (DDIM 30–50 vs FM ~10) come from an image-generation vendor blog; the only robotics datum found
   (Action-to-Action FM) compares generative vs *regression*, not FM vs DDIM, and its "recent findings by
   Pan et al. (2026)" was not opened.
6. **The action-space remark from Rho** (arXiv 2609.38164v1) — "absolute action spaces … memorization" vs
   "delta actions … fast error accumulation" — is a search-result snippet, not a read section; treat as
   contested, not as evidence.
7. **B-spline Policy's speedups.** Abstract only ("significantly reduces task completion time … while
   maintaining strong success rates"); no numbers in the abstract, PDF not fetched. Its project page
   (`b-spline-policy.github.io`) was not visited.
8. **PACE / TRACT / TempoVLA / SpeedAug / AutoSpeed / ESPADA.** Citations verified against RoboPace's and
   DEHP's reference lists (venues, years, arXiv IDs), but **no result numbers were read**. Do not quote
   them.
9. **The Reuss survey's "LIBERO is solved" framing** is one researcher's blog (Oct 2025) about ICLR 2026
   *submissions*. It is used here only for the "you don't need a VLA for this benchmark class" point, which
   the primary papers in §1-3 independently support.
10. **Venue dating.** ICLR 2026, CoRL 2025 and the 2026 arXiv IDs are future-dated relative to this
    environment's training data; all were read at the publisher/arXiv URLs given, and the page metadata
    (last-modified headers, PDF pagination) was consistent. This is flagged for honesty, not because a
    fetch failed.

---

## 7. Sources

| # | Source | Year | URL |
| --- | --- | --- | --- |
| 1 | Time Optimal Execution of Action Chunk Policies Beyond Demonstration Speed (RACE) — ICLR 2026, Kim/Kim/Lim | 2026 | https://proceedings.iclr.cc/paper_files/paper/2026/file/fab80bb9d97e9b9ff5c19f91f72838c6-Paper-Conference.pdf |
| 2 | RACE OpenReview forum | 2026 | https://openreview.net/forum?id=INsLvSCJ4z |
| 3 | RACE project page (unreachable, TLS) | 2026 | https://clvrai.github.io/RACE/ |
| 4 | RoboPace: Contact-Aware Time-Optimal Retiming for Action-Chunk Policies (arXiv 2610.09696) | 2026 | https://arxiv.org/html/2610.09696v1 |
| 5 | SAIL: Faster-than-Demonstration Execution of Imitation Learning Policies — CoRL 2025 (arXiv 2506.11948) | 2025 | https://arxiv.org/html/2506.11948v2 |
| 6 | SAIL project page / code | 2025 | https://nadunranawaka1.github.io/sail-policy |
| 7 | DemoSpeedup: Accelerating Visuomotor Policies via Entropy-Guided Demonstration Acceleration — CoRL 2025 (arXiv 2506.05064) | 2025 | https://arxiv.org/html/2506.05064v2 |
| 8 | DemoSpeedup code (MIT) | 2025 | https://github.com/lingxiao-guo/DemoSpeedup |
| 9 | Dynamic Execution Horizon Prediction for Chunk-based Robot Policies (DEHP, arXiv 2606.11408) | 2026 | https://arxiv.org/html/2606.11408v2 |
| 10 | B-spline Policy: Accelerating Manipulation Policies via B-spline Action Representations (arXiv 2607.09648) | 2026 | https://arxiv.org/abs/2607.09648 |
| 11 | ForceDelta-VLA: Distilling Force-Conditioned Action Corrections for Contact-Rich Manipulation (arXiv 2609.18242) | 2026 | https://arxiv.org/html/2609.18242v1 |
| 12 | Action-to-Action Flow Matching (arXiv 2602.07322) | 2026 | https://arxiv.org/html/2602.07322v2 |
| 13 | State of VLA Research at ICLR 2026 (M. Reuss, blog) | 2025 | https://mbreuss.github.io/blog_post_iclr_26_vla.html |
| 14 | Real-Time Action Chunking with Large Models (π0.5 latency table) | 2026 | https://www.pi.website/research/real_time_chunking |
| 15 | Real-Time Execution of Action Chunking Flow Policies (RTC, arXiv 2506.07339) | 2025 | https://arxiv.org/html/2506.07339v1 |
| 16 | Real-Time Robot Execution with Masked Action Chunking — ICLR 2026 | 2026 | https://proceedings.iclr.cc/paper_files/paper/2026/file/c35834443b7881e782e52b3519fe27c7-Paper-Conference.pdf |
| 17 | toppra — time-optimal path parameterization library (TOPP-RA solver) | — | https://github.com/hungpham2511/toppra |
| 18 | A new approach to time-optimal path parameterization based on reachability analysis (Pham & Pham) | 2018 | https://doi.org/10.1109/TRO.2018.2819195 |
| 19 | HYPERVLA (ICLR 2026 submission, via source 13) | 2026 | https://openreview.net/attachment?id=bsXkBTZjgY&name=pdf |
| 20 | Rho: A Foundation for Efficiently Adaptable VLA Models (arXiv 2609.38164) ⚠ snippet only | 2026 | https://arxiv.org/html/2609.38164v1 |
| 21 | Diffusion model vs flow matching (vendor blog) ⚠ | 2026 | https://www.paiteq.com/blog/diffusion-vs-flow-models |

**Repo sources referenced (no simulator run, no code change):** AGENTS.md §1-3 (P41/P42/P43/P44/P46
paragraphs), `logs/p40/LIT_REVIEW.md`, `logs/p45/FRONTIER.md`, `logs/p43/P2_RESULTS.md`,
`logs/p44/P2_RESULTS.md` (+ amend §9), `logs/p46/P1_RESULTS.md`, `logs/p42/SIM_LIMIT.md`,
`logs/p47/ACQ_CENSUS.md`, `logs/p48/HANDOVER_CENSUS.md`, `logs/160`, `logs/161`.





