# BIMANUAL: the two-arm line vs the owner's goal (P10-B, 2026-10-17)

Deliverable of P10-B (`.slim/deepwork/sorting-pipeline-v3.md` "P10 PLAN"). Tier-C:
no simulator, no `src/` change, no shipped default. This file consolidates, against
the owner's goal, (1) the four measured bottleneck families of the two-arm line,
(2) the ranked mechanism menu (local 84-paper library + the P9-E external scouting
+ a new targeted 2026 search), and (3) the standing **knowledge-acquisition method**
with the resource rules. Every external finding carries its URL and a confidence
mark (`FULL-READ` = the body was read; `ABSTRACT-ONLY` = abstract/snippet only;
`PRACTICE` = vendor docs). Local claims point at their log; the summary is mine,
quotes are short.

**The goal (owner, 2026-10-17): a robot using both arms to quickly sort scattered
fruit on a uniformly moving conveyor line** ("双臂快速地分拣匀速运动水流线上的散乱的
果蔬"). Platform of record: the belt (0.12 m/s, never stops) - not a water flume;
if the flume reading was intended, the transport model (buoyancy/drag) is a
scenario change to flag, not a blocker.

## 0. The platform record in one screen (what "the two-arm line" is today)

* **The scheduler**: `FRUIT_BIARM_TWOLINE=1` (opt-in; `FRUIT_BIARM=1` alone is the
  older shared-station pipeline). Each arm owns a station on the shared belt:
  **left y = 0.00, right y = -0.10** (0.10 m separation - the right station is the
  deepest one its top-down reach holds <= 6 mm across the supplied band). Pure
  grade routing: left takes A only, right B only, C passes both stations
  (`FRUIT_GRADE_ROUTING`, R5-decided two-line-only). One arm owns the station from
  its pre-pose until its carried payload clears a box around it; the other
  pre-poses meanwhile; the **park gate** (payload-clear predicate:
  `|y - station_y| > 0.28 m` or `x > 0.52 m`) is **default on for the two-line
  since the W7-A owner flip**. The scripted pick is the never-stop dynamic catch;
  the hybrid policy touches only the close (opt-in; the pinned canary is the
  interface of record, R5).
* **The measured records** (each a deterministic branch; quantized outcomes, never
  compare success rates across configurations - AGENTS section 2):
  * W6-B patch baseline (pre-flip): two-line **10/20, 2.78 batch / 2.70 window
    placed/min**, pooled interval 22.20 s mean / 45.50 p90, idle 26 %/29 %; the
    same-scenario single arm **13/18, 2.12/2.17** -> **1.24x** (`logs/w6/BASELINE.md`).
  * W6-C park-gate lever -> W7-A default (bit-identical replay, 861/861): **12/20,
    3.64/3.63 placed/min, pooled interval 16.53 / 17.30 / 19.90 s, idle 18 %/24 %**;
    timing-only **+10 %**, residual x1.22 is the branch (`logs/w6/C_RESULTS.md`).
  * W1 grip-profile branch (shipped on the two-line): **7/10 x5 bit-identical,
    9.2 s/attempt, 4.59 placed/min = 1.29x** against the same-branch single arm
    3.55 (`logs/w1/`); idle 42 % -> 17 %/18 %; delivered per-slot starvation
    4/9 left (all batch-start belt-prime; steady-state 0/5).
  * W3/W4 dense sheet (balanced mix): two-line **8/10, 11.2 s/attempt, 4.27
    placed/min** vs the same-scenario single arm 9/10, 3.59 -> **1.19x < the 1.25x
    bar** (`logs/w3/`, `logs/w4/`).
  * W7-A dense re-record (fingerprint `configs/motion_reference_twoline.json`,
    `181c9151`): **7/10, 9.1 s/attempt, 4.60 placed/min** (left 2/5, right 5/5,
    `diverted=0`); the park-gate control replays the pre-flip record bit-for-bit
    (`logs/w7/`).
  * Older references for the ratio set: F2 1.30x, G (shared-station, Gate-19
    place) **1.05x**.
* **The bar and the decisions**: the pre-registered replacement bar is
  **1.25x placed/min**; the R5-decisions (2026-10-13) kept the two-line **opt-in**
  (`FRUIT_BIARM_TWOLINE=1`), the clearance a **per-config report** (F2's 45 mm /
  zero-under-30 convention unmet; no arm-arm contact is possible in this build,
  `enabledSelfCollisions=0`), pure C routing two-line-only, and the hybrid pinned
  canary as the shipping gate.
* **Current tree**: post-W7-A, post-W1, with the P9-A ready-transit knobs present
  but default-off and single-arm-scoped. The **P10-A current-tree bimanual
  baseline is being measured** (`logs/p10/`, not present at this writing; the
  rankings below are against the W6-B/W6-C/W7-A records above). The committed
  current-tree patch control is `logs/p8/36_patch_control.log` (861/861 identical
  to W6-C's `31_lever_park_1.log`; reference `configs/motion_reference_patch.json`)
  and the dense control `logs/w7/10_dense_twoline_1.log` (442/442).

## 1. The goal decomposed into the four measured bottleneck families

### (a) The per-arm span and the inter-attempt gap

**Measured.** Per-attempt span on W6-B: **14.92 s pooled** (left 14.47 / right
15.48), decomposed by `[cycle]` means: prepose 0.71 / hover 0.88 / descent 3.05
(incl. the ~2.4 s supply-coupled arrival wait) / close 1.28 / grip 2.32 / lift 1.79
/ place 2.70 / release 1.64 / return 0.51. The inter-attempt cycle adds the
per-arm gap: park (gate wait + the arm's own return transit) + the ~0.5 s feed gap,
then the next slot's acquisition/selection/pre-pose. The single-arm line's gap is
measured exactly: clean p50 **5.1-5.2 s on every log, every scenario** (nine logs;
`logs/p9/GOREADY_OFFLINE.md`): 60 feed ticks + 30 advance ticks + ~534 `go_ready`
ticks, of which **two 210-tick `_blend_to` (90 ramp + 120 settle) transits run on
every gap, one of them a genuine no-op on the parked arm** (measured `dq_max`
0.0005 rad/tick).

**The P9-A work and what it does not cover.** The single-arm lever
`FRUIT_READY_SKIP=1` (B1) removes that passive no-op: 230 ticks
(`catch_up 20 + blend 90 + settle 120`) = 1.917 s = **0.23 m of belt travel per
skip**; measured **-1.95 s/gap (-8.6 % wall), the largest single-term timing win
in the project - but NOT adopted**, because the acceptance floor failed (9/10 ->
6/10 at SEED=5) and the movement is a belt-phase **re-draw** (P9-C/P9-D): the
catch itself is phase-robust (intercept span 17.0-18.0 mm across >= 1.6 m of
demonstrated phase offset; zero chases; failing vs passing alignment <= 0.5 mm
apart), the gains are clock-exact, and the outcome movement is branch/draw noise
(placebo arm B'' with `SKIP_HOLD=230`: gap back to 5.15 s, the empty poll gone,
outcomes 8 ok + 2 g-n-p vs A's 9 + 1). The multi-seed check is in flight
(`logs/p9f/`: A vs B' at SEED=11/23). **The lever is deliberately single-arm-scoped**
(`_ready_move`: `scope = self._active_session is None and not self.two_line_enabled()`),
because **the two-line park logic differs and its own no-op transit is UNMEASURED**:
`_biarm_park(arm)` early-outs when the arm is within `TRANSIT_TOL` (0.08 rad) of
ready, then gates on the other arm, then runs `go_ready(arm)` - a per-arm staged
transit (catch-up + lift + blend 90 + settle 120 + occasional `_recover_ready`)
whose per-gap share has never been instrumented on the two-line. The pure-reporting
`FRUIT_READY_DIAG=1` is **scoped-safe for the two-line** (the diag is global; only
`skip` is scope-gated), so the measurement that decides P10-C1 is one default-off
run away.

**What the family is not.** The interval is **not arrival-bound**: the cadence is
flat across the density ladder and the lock-on does not fall (P1/P2), the L1
prefetch hook measured **0/40 attempt-end reservations** (W6-C), and the
attempts-per-placement multiplier is the first-order driver of the interval
(W6-B: left 1.83, right 2.25, single 1.38 attempts per placement - see family (d)).
The descent arrival wait (~2.4 s) is supply-coupled; the place block is
geometry-closed (P3); the descent's boundary shortfall is scenario/motion
(AGENTS section 2).

### (b) The station/contention machinery and the park gate

**Measured.** One shared belt; two stations **0.10 m apart**; one station owner at
a time; the pre-pose of the second arm proceeds while the first carries; the park
gate blocks the returning arm's return while the other arm's payload is gripped
(shipped rule) or, since W2/W6-C/W7-A, until the payload **clears its station box**
(the measured win). W6-B idle split (trace): left idle 56.0 s of which
**gate-blocked 25.2 s (45 %)** and return motion 24.4 s (44 %); right 7.8 s (14 %)
because the right's grip phase (3.00 s vs left 1.76) staggers the gates. The
park-gate lever deleted the left's gate blocking (25.2 -> **0.2 s**) and moved the
pooled interval **22.20 -> 16.53 s mean, 45.50 -> 19.90 s p90**, window rate
2.70 -> 3.63 placed/min - on a **different branch** (12/20 vs 10/20), so the
quotable readings are the timing-only +10 % and the residual x1.22. Clearance is
a per-config report: W1 branch min 13.9 mm, 62/10672 samples < 30 mm; W7-A dense
branch min **2.59 mm**, 863/10042 = 8.6 % < 30 mm (the carry-past class); no
attempt has ever failed by arm-arm contact (structure: self-collisions disabled).
Lock-on (selection latency) on W6-B: left 5.60 s / right 7.04 s; the right's
starvation (41 starved slots, mostly grade-B lane polls) is a routing/supply
interaction, not a park cost. **The 0.10 m separation is the concurrency
mechanism**: wider stations were a W2 lever and cost the rate.

### (c) The draw/composition coupling

**Measured.** Every schedule/phase change **re-draws which fruit each arm is
presented** (P9-D "the re-draw"): outcomes are class-dominated (per-arm/species
placement 0.44-1.00, P1/P2), so a moved timing lever's success delta is a branch
attribute, not a mechanism claim. The phase-coupling analysis bounded the real
channels: (1) poll-vs-band timing - the empty poll's top candidate pear sat
**13 mm (13 ticks) under the ~0.40 m selection floor** after 460 ticks of shift;
(2) the re-draw - e.g. the left arm met two peaches + one kiwi under the shifted
schedule vs three kiwis under the shipped one; both new failures were peach
carry-class legs that exist in the no-lever branches too (left pooled placement
6/9 control vs 5/8 lever - indistinguishable). No signal available at the skip
instant separates the failures (confusion matrix R1-R4 in `logs/p9d/`; the
"next-arm"/"next-fruit" separators are branch artifacts that fire in the no-lever
controls); a conditional skip needs a **new default-off supply-peek readout**
(nearest eligible candidate's y vs the floor per `go_ready`) before a rule can
even be stated. P1/P2's rule follows: **class-standardize every composition-
sensitive read** and quote per-class tables; the density ladder's apparent
throughput gains were composition (class-standardized flat, 13.89-15.12 adjusted).

### (d) The carry/grip class (the failure mass)

**Measured.** W6-B two-line failures: 4/20 takeoff grip loss ("fruit did not
follow the gripper") + 6/20 grasped-not-placed; the single arm has none of the
former and 5/18 of the latter. The mechanism (W8-B/R6-B): a **mid-lift one-sided
loaded slide** with a **0-2 tick reaction window** - force at onset median 4.90 N,
jaws pried toward their 98-99 mm limit in 17/31 escapes, contact loss 2-132 ticks
after the 2 mm crossing (median 25); the squeeze side is **drive-saturated** (the
lift command sits a median 11.9 mm inside the payload span while contact force
reads the drives' 4.1-4.5 N; releasing the command to 0.5 mm interference leaves
the force unchanged). Closed in-scenario: the in-window guards (p = 0.1094 /
0.3125), the squeeze family, the shape side (R8-A D screen: plane-drop, scoop,
nested station all FAIL), the re-seat guard, the BC recollections (W8-A p = 1.0),
R9's AWR-RWR lane, the pre-onset load knobs (stage-P 12/20 vs 13/18). The two-line
W1 profile (regrasp re-seats in place after a failed probe, gentler 6 mm/60-tick
probe) is the shipped in-scenario improvement (4.59 placed/min = 1.29x). **The
family's interval relevance is first-order**: its failures consume whole attempts
(1.83-2.25 attempts per placement), and the residual levers are the owner-gated
geometry direction (D3-proper: a pick station clear of the belt / a
boundary-respecting descent) and the external **lift-profile** family (section 2).

## 2. The mechanism table (ranked)

Rank = expected movement against the four families above per unit cost x risk.
Every row: **candidate (source) -> bottleneck -> expected metric movement ->
cost -> falsification**. All candidates default-off, scoped, pre-registered;
scripted/two-line claims answer the per-scenario gate (`190` + the scenario
reference), mechanism claims on the direct interface answer the N=5 paired
protocol, shipping answers the hybrid pinned canary (R5). "L" = local (84-paper
library or repo lineage), "X" = external.

| # | candidate (source) | bottleneck | expected movement | cost | falsification |
| --- | --- | --- | --- | --- | --- |
| 1 | **Two-line park/transit instrumentation + the scoped skip/settle** (L: P9-A extension; `FRUIT_READY_DIAG` + a two-line-scoped `FRUIT_READY_SKIP`; P9-C item (i)) | (a) | the two-line's **own** park-transit share (unmeasured; upper bound = the single-arm no-op class, 1.92 s/gap; the `TRANSIT_TOL` early-out means likely less) -> per-arm gap, then interval | S (1 diag run + 1-2 batteries) | diag shows the per-gap transit <= 0.3 s (nothing to remove) or every park is load-bearing; gap p50 falls < 0.5 s; any gate/floor fail; phase re-draw not read per class |
| 2 | **Selection-allocation refit, offline replay first** (L: BiDexGrasp #74 primary-then-conditional, 61.9 vs 45.5; SPaSM #75 live-variable refit; X: Jermann FULL-READ, Teck ABSTRACT-ONLY, DYNAMIT ordering) | (b) + (c) | **starved polls** (41 on the patch control: left 19 / right 22) and lock-on; pooled interval secondary; never the carry class | S offline -> M in-loop | replay changes < 5 % of selections, or starvation/interval unmoved vs the park-gate baseline at N >= 3; new reasons; owner semantics (pure A/B routing) must stay (within-lane by default) |
| 3 | **Lift-profile modulation + the offline lift-phase audit** (X: Nazari et al. Nature MI 2025 FULL-READ; CoRL 2022 FULL-READ) | (d) | per-leg slip-band shift (clean / 2-100 / 100-400 / >400 mm) and **paired carried-class conversion** (6-0 edge, p <= 0.05); attempts/placement down | S | **offline first**: if the first `clean_slip` growth tick clusters at constant velocity rather than the accel/decel phases of the lift, stop; else no band shift or paired null; cycle > +5 % |
| 4 | **Earliest-feasible-meeting ordering + descent-start scheduling / computed residual** (X: DYNAMIT FULL-READ; Chen et al. ICRA 2025 FULL-READ; L: R10-A.1 hover-settle cousin) | (a) wait + (c) | the `[cycle]` descent-wait segment toward its setup floor; **not** the span (the fruit's travel time is the floor); no-fire/chase counts | S-M (motion-touching if the profile changes) | wait unchanged (supply-coupled - the computed-residual audit resolves this cheaply); R11-A signature (re-seats 0 -> 10; left post-catch hold failures) must not reproduce; R11-A family overlap flagged |
| 5 | **FPTE terminal scoring on the two-line selector** (L: MECHANISMS item 2; C-1) | (b)/(c) | no-fire/chase-slot conversion; on the direct line C-1 measured **no terminal separation** (P7-1 NO-GO) - the two-line readout is starvation, not aim quality | S | slot conversion absent at N >= 3; any new reason; the direct-line NO-GO generalises (then close) |
| 6 | **Park-return retiming / fly-by** (X: Ruckig RSS 2021 FULL-READ; Lin et al. ICRA 2021 partial; PRACTICE: vendor blending) | (a) | the active arm's park tail: settle 1.0 s + corner blend 0.2-0.5 s per attempt (ceiling; the two-line's gate interacts) | M | clearance (min jaw-z through the blended pass) cannot hold without the stop; retiming is a no-op if the blend already rides the gates |
| 7 | **Carry monitor fast-skip + the conformal retry** (L: MECHANISMS item 1; P7-2b killed the first form: interval -24.0 % paired 33-0 but 5 clean aborts > cap 2; next = JCAC-conformal signal or a stricter FP gate) | (d) + (a) | interval on failed attempts (truncate the doomed carry to free the shared station earlier); carried-class conversion only via the bounded re-seat half | M | FP cap on clean legs; the K2 kill (live 5/19 vs replay 1/20); no new reasons |
| 8 | **Two-line recollection -> model iteration** (L: W7-C store `demos_v13p`; W8-A superseded the N=3 read, p = 1.0; the W3-supply canary FAIL 1/10 is open scenario coverage) | (d)/(c) | policy-side carried-class + the hybrid path on the two-line scenario; the direct-transfer risk measured null once | M | N=5 paired carried-class null with no new reasons; canary stays the shipping gate |
| 9 | **GDP OoD population sampling + event-structure handover heads** (L: MECHANISMS items 5/6) | (c)/(d) | no-fire + close-start lateral dx (seeds 77/101/202), then N=5 paired; the direct interface | S-M | no separation on no-fire/dx; re-seat signature; retrain non-neutral to the canary |
| 10 | **ExS2D single->dual action expansion** (X: Cao et al. arXiv 2606.19897 FULL-READ: -54.4 % execution steps on tabletop, zero bimanual demos; precedence-aware greedy allocation) | model lane | none on the conveyor yet - the evidence is tabletop rearrangement; the MLLM coordinator's inference cost exceeds our tick | M+ | not evaluable on the belt without a new perception/planning stack; keep as the form-reference for the allocation refit (#2) |
| 11 | **Layout/allocation studies of multi-robot sorting cells** (X: Engelen ABSTRACT-ONLY +3.6 % efficiency / +37.5 % pick rates; Nupim ABSTRACT-ONLY priority-based dual-arm; Righettini ABSTRACT-ONLY; Teck ABSTRACT-ONLY > 4 % over traditional rules) | (b) | unverified; candidate numbers only after full-text reads | L (scenario/design) | no pre-registration before the full texts; any layout change is the D3-proper owner-gated class |

**Readings of the table.** (1) The single highest-value *bimanual-specific* row is
#1: it is cheap, its instrument (`FRUIT_READY_DIAG`) is already scoped-safe, and
its outcome decides whether the P9-A win has a two-line analogue at all. (2) Rows
2/4/5 share one offline step (the replay): the allocation/ordering question can be
screened without a simulator, and the replay-first discipline is the standing rule
for selector changes. (3) Row 3 is the only ranked external lever aimed at the
failure mass; its offline phase test makes it cheap to kill. (4) Rows 6/9/10 are
second-tier: real mechanisms, but their expected movement is bounded by the
measured phase-robustness (6), the null from the first form (9), or the wrong
domain (10).

### 2b. External findings of this scout (URL + confidence + transfer sketch)

New queries this session (14 searches + direct fetches; log below). Findings that
are usable in a pre-registration:

* **Jermann, Kolvenbach, Esquivel Estay, Kraemer, Hutter (ETH Zurich, 2024),
  "An Efficient Multi-Robot Arm Coordination Strategy for Pick-and-Place Tasks
  using Reinforcement Learning"** - `https://arxiv.org/abs/2409.13511` -
  **FULL-READ**. Two-robot waste sorting on one conveyor (identical arms on both
  sides, non-overlapping workspaces, no collision avoidance considered). The
  coordination problem is **which object each robot picks next**; the baseline is
  a robust combinatorial-game-theory rule set whose measured optimum for two
  robots is **[SPT; FIFO]** - one "hard worker" taking the shortest-processing
  object, one "leftover picker" taking the farthest upstream; a trained PPO policy
  with global state (each robot's busy flag + time-until-available) beats it by
  **up to 16 % picking rate**, wins most on dense object patterns, and raises the
  all-picked belt speed **11.9 %** (0.042 -> 0.047 m/s); validated on a real
  two-robot station. **Transfer**: our two-line's lanes both take the *nearest
  usable* fruit; the [SPT; FIFO] asymmetry and the other-arm state term are the
  untested deltas - *what to port* = the other-arm busy/until-available term in
  the within-lane candidate score (rule-based first, learned only if the rule
  moves the metric); *bottleneck link* = (b)+(c); *expected movement* = starved
  polls + lock-on, conditional on the replay; *cost* = S; *falsification* = no
  selection/interval movement at N >= 3, or a routing-semantics violation.
* **Cao, Li, Ding, Gu, Chen (2026), "One-to-Two Acting: ... Single-arm Agent
  Action Expansion to Dual Arms" (ExS2D)** - `https://arxiv.org/abs/2606.19897` -
  **FULL-READ**. Dual-arm throughput via parallel execution without bimanual
  demos: structured subtasks + precedence levels, greedily allocated to arms by a
  motion-cost heuristic (distance to pick + pick-to-place), collision-checked;
  **-54.4 % execution steps** at comparable success vs the single-arm baseline on
  tabletop rearrangement; the ablations measure the allocation half directly -
  a fixed arm order raises the motion cost to 3.58 vs the full model's 2.02
  (and 2.24 without precedence reasoning). **Transfer**: the outcome
  evidence that dual-arm parallelism is where the throughput lives, and the
  motion-cost allocation form; *no conveyor*, MLLM inference, so it lands as the
  form-reference for table row #2, not as a lever.
* **Teck, Engelen, Peeters, Kellens, Vansteenwegen (KU Leuven), IJPR 63(23),
  2025** - `https://doi.org/10.1080/00207543.2025.2517835` - **ABSTRACT-ONLY**
  (search snippet; the PDF exceeds the fetch cap; the P9-E-B scout reached the
  model but not the results). Per-object **pick time windows** per robot on a
  moving conveyor with explicit "wait until a_i"; the reported headline is
  "improves system performance by **over 4 %**" vs the best traditional decision
  rules. **Transfer**: the window formalism is the vocabulary for our two lanes'
  41 starved polls (left 19 / right 22); *truthful weight* = 4 % class of gain,
  not 16 %.
* **Engelen et al., Robotics 2025, 14(3):22, "System Layout and Grasp Efficiency
  Optimization for a Multirobot Waste Sorting System"** -
  `https://www.mdpi.com/2218-6581/14/3/22` - **ABSTRACT-ONLY** (publisher 403;
  PDF > fetch cap): reported picking-efficiency gains up to **3.6 %** and pick
  rates up to **37.5 %** (the latter is a specific configuration change; do not
  quote without the body). **Collect before use.**
* **Righettini & Cortinovis, Robotics 2025, 14(11):150, "High Fidelity Real-Time
  Optimization of Multi-Robot Lines Processing Shared and Non-Deterministic
  Material Flows"** - `https://doi.org/10.3390/robotics14110150` -
  **ABSTRACT-ONLY** (number-free abstract; 3.1 MB PDF over cap). A methodology
  item for shared-flow multi-robot lines; collect before use.
* **Nupim & Wannapanon (2026), "Optimization of Dual-Arm Robotic Waste Sorting
  via Digital Twin Simulation and Priority-Based Algorithms"** - Semantic Scholar
  entry (conference paper, May 2026) - **ABSTRACT-ONLY** (no full text available
  at access time). Task allocation under heavy load for a dual-arm waste sorter;
  collect only.
* **RoboPARA (arXiv:2506.06683)**, LLM-driven dual-arm task parallelism planning -
  **SNIPPET-ONLY** (the fetch failed); recorded as the same "task-parallelism
  planning" form as ExS2D; do not cite numbers.
* **Li et al. (EJOR 2026), "Robot scheduling, destination assignment, and layout
  design"** for a circular robot-arm sortation system -
  `https://www.sciencedirect.com/science/article/pii/S0377221726000949` -
  **SNIPPET-ONLY**; collect if layout work re-opens.
* **Folded from the P9-E scouts (already in-repo, quoted for completeness)**:
  the motion family (Ruckig RSS 2021 FULL-READ; Lin ICRA 2021 partial; the
  industrial "completion is a predicate" PRACTICE rule; Wachter IROS
  place/rest-pose ABSTRACT-ONLY; Marauli IFAC 2025 ABSTRACT-ONLY) -
  `logs/p9e/EXTERNAL_A_MOTION.md`; the conveyor/catch family (DYNAMIT MERL TR
  2026 FULL-READ; prescribed-time interception MDPI 2024 FULL-READ; Chen ICRA
  2025 FULL-READ; FANUC/UR vendor PRACTICE) -
  `logs/p9e/EXTERNAL_B_CONVEYOR.md`; the slip family (Nazari Nature MI 2025
  FULL-READ; CoRL 2022 FULL-READ; Wong & Zhu / FORTE / universal / inertial
  detectors FULL-READ, sim NO-GO; the CBF friction-cone audit form FULL-READ) -
  `logs/p9e/EXTERNAL_C_GRASP.md`. Those files carry the URLs, the query logs and
  the per-finding confidence marks; this scout does not duplicate them.

### 2c. Measured negatives - do not re-propose without a materially different mechanism

Class-standardization or a different mechanism is required for any of these; every
one has a log:

* **Density / "put more fruit on the belt"** (the owner-correction instinct):
  composition-free single-species ladder strongly negative (P1c: 65 % -> 17-30 %
  per attempt; 0/20 -> 14/20 empty slots; D = 1.6 double physics-identical);
  class-standardized two-line ladder flat (P1/P2); D = 2.0 crowding collapse is
  the real density effect; the **trickle** supply cap regressed both lines
  (single 4/8 vs 9/10; two-line 7/20 vs 12/20, starved polls 41 -> 81; P8-A).
* **Place-leg shortening** (P3: 45.1 -> 36.1 cm carry collapses 90 % -> 30 %;
  release at |y| 0.21-0.41 vs the belt edge 0.375 - geometry-closed; max safe
  shift ~30 mm = ~0.2 s).
* **L1 prefetch/reserve** (0/40 attempt-end reservations; W6-C null),
  **adaptive selection lead** (bit-identical; R3), **hot-arm residency** (fires
  4/18, flat; R3), **capture token** (2/10; W2/W3), **W2/W3 park redesigns**
  (cost rate; keep the park gate as the mechanism).
* **Load-floor monitor / C-3 fast-skip**: interval -24.0 % paired 33-0 (P7-2b)
  and -21.8 % (P8-B) but killed by clean-leg aborts (5 > cap 2) / the lock-on
  +8.8 % > +5 % bar - the form stays closed until a conformal signal exists.
* **In-window reaction family** (guards p = 0.1094/0.3125; force Port A null -
  chase 5 -> 0, zero conversions; the W5 watcher), **squeeze side**
  (drive-saturated; R6-B), **shape side** (R8-A D screen), **pre-onset load
  knobs** (stage-P 12/20 vs 13/18), **reach-anywhere / meet-it-upstream**
  (R11-A: acceptance 4/10 vs 9/10 deterministic; floored variant 4/9; the
  enable-path pair now pins `FRUIT_REACH_SHIPPED_FLOOR`), **place squeeze/wrist
  hold**, **finger-face variants**, **BC recollections** (W7-C underpowered;
  W8-A p = 1.0), **R9 AWR-RWR** (p = 0.5), **FPTE on the direct interface**
  (no terminal separation; P7-1), **faster samplers / async seam / discrete-token
  latency** (12 ms fits the tick).
* **External families closed by the above**: detect-slip -> squeeze harder
  (drives saturated; EXTERNAL-C section 3); catch-in-flight / free-flight
  (embodiment; EXTERNAL-B F7); dual-arm asynchronous overlap as a *single-arm*
  gap lever (needs a second active agent - and our overlap lever, the park gate,
  already ships; EXTERNAL-A F9); MA-VLA-style unified learned coordination (R5
  scripted-coordination decision; B3b NO-GO confirmed); naive force conditioning
  (three independent backfires).

## 3. The knowledge-acquisition method (the standing loop)

The loop that produced this file, to be run every P10 cycle. Six steps, in order;
each one has its standing artifact and its discipline:

1. **Measure** - build the bottleneck map from the *current tree*, never from an
   old branch. The four families (section 1) are the map; every claim points at a
   log; every rate is one deterministic branch (AGENTS section 2). The P10 loop
   opens with the bimanual baseline re-measure (P10-A); the next cycle opens with
   its successor.
2. **Search** - **local first**: the 84-paper library (`docs/papers/INDEX.md`;
   `Paper/fulltext_ca/` is the read corpus) answers most bottlenecks, and the
   P6 menu already ranks them. **External web scouting when, and only when, a
   named gap has no mechanism in the library** (the standing capability; the
   P9-E files are the scouts of record). Every external finding carries its URL
   and a confidence mark: `FULL-READ` / `ABSTRACT-ONLY` / `PRACTICE` - and a
   headline number from an unread body is never a number of record.
3. **Extract** - the **mechanism card**, five fields, no exceptions:
   *mechanism* (what is ported, in one paragraph), *our bottleneck link* (which
   of the four families, with the measured link), *expected movement* (a named
   metric and its plausible band), *cost* (S/M/L + which resources), *falsification
   criterion* (the cheap test that kills it **before** a battery, wherever one
   exists). Section 2's table is 11 cards in exactly this format; a card without
   a falsifier is not a card.
4. **Pre-register** - freeze before any Tier-A run: numeric endpoints, the
   kill criteria, the no-harm bar, and the tree pins (md5s of the touched files +
   the branch + the frozen control log). Amendments are separate frozen docs
   (the P9-A calibration amendment is the pattern). Running rules: one Tier-A
   battery at a time (the single simulator channel is claimed through
   `scripts/154_claim_run.sh`), **no `src/` writer while a battery is live** (the
   P9-a mid-battery rule), and check for an existing chain before launching (the
   P9-b duplicate-chain incident).
5. **Test** - the battery plus the standing gate stack: `105_motion_regression`
   (per-leg budgets; the shipped fingerprint only for the shipped branch),
   `190_twoline_gate.sh` (two-line scenario + its own reference + its own floor),
   `186_w6_report.py` (interval/lock-on/idle/throughput), `compare_streams.py
   --physics-only` (byte no-harm), `selfcheck.sh`, `172_supply_selftest.py`.
   **Attribution controls are part of the test**: double runs (determinism is a
   proof, not a sample), a trace-off repeat when the trace moves the branch,
   placebo arms where a coupling is suspected (P9-A's `SKIP_HOLD=230`), branch
   probes between arms (AGENTS section 3b), and per-class tables for any
   composition-sensitive read (the section 2c rule). Instrumentation defaults
   off; per-tick work inside `ik_step` is banned.
6. **Fold** - update the KB/menu and the log entry; **publish the negatives like
   the positives** (section 2c grows every cycle); state which attractor the run
   is in and which reference/fingerprint applies; then the loop's next Measure.
   A closed lane stays closed until a materially different mechanism appears -
   that is what section 2c exists for.

**Resource rules.** Tier C (measurement analysis, scouting, mechanism cards,
offline replays, offline audits, this document) runs **free and in parallel -
use it first and use it more**. The single Tier-A channel (one simulator) is
allocated by **expected movement per unit cost x risk**, ordered: (1) P10-A-style
baselines that define the map; (2) the highest-ranked lever from the current
table; (3) the model iteration (P10-D). An offline falsifier that can kill a
lever before it reaches the channel is worth more than any optimization of the
battery.

## 4. The top-3 levers to test first on the bimanual line

Pre-registration sketches; each is a frozen-doc candidate (P10-C), not yet run.

**L1 - the two-line per-arm park/transit measurement, then the scoped skip/settle
(local, P9-A extension).** *Question*: what does the two-line's own inter-attempt
park actually cost per arm per attempt, and does removing the removable part
shorten the interval? *Arms*: A = shipped two-line (knob off, double run); A+diag
= `FRUIT_READY_DIAG=1` (branch-neutrality checked modulo `[ready]` rows against
A); B = the two-line-scoped skip/settle if, and only if, the diag shows a parked
or partially-converged transit with a removable share (the P9-A calibration logic:
`FRUIT_READY_SETTLE` only if the diag's `ramp_err` is already inside tolerance;
`SKIP_DG` judged against the measured `dg` distribution). *Scenario*: the W6-B
patch battery (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_PATCH=1`,
`ATTEMPTS=20 SEED=5`, balanced mix, patch reference
`configs/motion_reference_patch.json`) plus the dense 10-attempt re-record
(`configs/motion_reference_twoline.json`); the single-arm acceptance as the
no-harm leg. *Endpoints*: primary = the per-arm per-gap park transit share (tick
sums from the `[ready]` rows, per stage: catch-up/lift/blend/settle/recovery)
and the park-trace wait split; secondary = the per-arm clean-gap p50 (outcome
windows + park trace), pooled interval, window placed/min (186), starved polls,
lock-on. *Kills*: the transit share is <= 0.3 s or every stage is load-bearing
(the lever dies, the measurement stands); the gap p50 falls < 0.5 s; any descent
outside budget; any new failure reason; the two-line gate (`190`) fails its floor
or reference; and if the branch moves, the P9-D discipline applies - per-class
tables plus the `SKIP_HOLD=230` placebo as the attribution control. *No-harm*:
single-arm acceptance 9/10 + `fingerprint: matches` + 385/385 stream identical;
dense 442/442 + `190` PASS knobs-off; `selfcheck.sh` PASS; `configs/*` untouched.

**L2 - the two-line selection-allocation refit, offline replay first (local +
external).** *Question*: given the same supply, does changing *which* eligible
fruit each lane takes - with the other arm's state and the pick-window structure
in the score - reduce the starved polls and the interval? *Step 0 (Tier C, no
simulator)*: an offline replay over the current two-line logs (patch control
`logs/p8/36_patch_control.log`, dense `logs/w7/10_dense_twoline_1.log`) that
reconstructs each selection instant's candidate sets and re-scores them under
alternatives: (a) shipped nearest-usable per lane; (b) primary-then-conditional
with an inter-arm term (the other arm's estimated free time + its lane's
candidate set; the BiDexGrasp 61.9-vs-45.5 form; the Jermann other-arm-state
term; the [SPT; FIFO] asymmetry); (c) earliest-feasible-meeting ordering within
the lane (DYNAMIT `tau* = max(arm, fruit)`); (d) the Teck window order for the
starved polls. Kill at step 0 if < 5 % of selections change or the starvation
count does not move in the replay. *If step 0 passes*: arms A = park-gate-on
shipped / B = the refit (default-off, within-lane; any cross-lane fallback needs
the owner to re-open the W3 pure-routing semantics), N >= 3 patch batteries + the
dense re-record, interleaved. *Endpoints*: starved polls (the primary: 41 on the
control), lock-on, pooled interval + window rate class-standardized. *Kills*: no
starvation movement at N >= 3; a new failure reason; the two-line gate fails;
routing semantics moved without sign-off. *No-harm*: knobs-off byte-identity
(365/365, 643/643, 442/442 + `190`), `configs/*` untouched.

**L3 - the lift-profile modulation for the carry class, with the offline
lift-phase audit as step 0 (external, EXTERNAL-C rank 1).** *Question*: are the
carry escapes initiated by the lift's acceleration/jerk phases (then the profile
can prevent them) or not (then stop)? *Step 0 (Tier C)*: reconstruct each escape
leg's commanded lift profile from the existing trace corpora
(`logs/w8/B_traces_mech`, the W7-B pinned run, the R5 corpora) and classify the
first `clean_slip` growth tick against the accel/decel/constant-velocity phases;
falsification is the constant-velocity clustering. *If step 0 passes*: arm A =
shipped / arm B = jerk-limited/quintic-smoothed `grasp_lift` ramp, same span and
distance (default-off `FRUIT_LIFT_PROFILE`, scripted lift shared by both
interfaces), N = 5 paired direct + the per-scenario scripted gate + the two-line
patch gate. *Endpoints*: per-leg slip-band shift (clean / 2-100 / 100-400 /
>400 mm) and the paired carried-class conversion (6-0 edge, p <= 0.05),
strawberry non-inferior, cycle <= +5 %; the two-line's placed-False share (6/20
on W6-B) as the descriptive secondary. *Kills*: no band shift; paired null; any
descent over budget; re-seat rise; new reasons; the acceptance floor. *No-harm*:
the standing triple (385/385, 643/643, 442/442 + `190`) + `selfcheck.sh`.

**Honourable mention (4th)**: the DYNAMIT/Chen descent-start + computed-residual
scheduler - cheap, but its honest ceiling is the wait segment only; run it after
L1/L2 if the map still shows the wait as the largest supply-coupled term.

## 5. Blockers and the named next measurements

1. **No current-tree P10-A baseline at this writing** (`logs/p10/` not yet
   present). Sections 0-1 rank against the W6-B/W6-C/W7-A records; Gate B should
   be read with that qualification, and P10-C's readings should be against the
   fresh P10-A numbers once they exist.
2. **The two-line's own no-op transit is unmeasured** - L1's diag run is the
   gate for whether the P9-A family has a two-line analogue at all.
3. **The phase-coupling discipline** (P9-D): every schedule-shifting lever
   re-draws the composition; read per class, use the placebo, and do not quote a
   cross-configuration rate delta as a mechanism (AGENTS section 2). The
   conditional-skip form additionally needs the new supply-peek readout before a
   rule can be stated.
4. **The 1.25x placed/min bar is unmet on the dense supply** (1.19x on W3/W4;
   the W1 1.29x does not carry there). The named path is the grip/failure class
   (L3), not more supply or more levers on the park.
5. **Owner-gated items stay gated**: D3-proper (station/feeder/descent geometry),
   any change to the two-line routing semantics, and the ACQ shipping question
   (R5). Full-text collection precedes any use of the flagged `ABSTRACT-ONLY`
   numbers (Teck, Engelen, Nupim, Righettini).

## 6. Provenance

**Queries run (14 websearches + 14 direct fetch attempts, 2026-10-17):** dual-arm robot
sorting conveyor belt throughput 2025 bimanual pick and place; multi-robot
pick-and-place scheduling moving conveyor line balancing throughput 2024 2025;
dual-arm robot cycle time optimization coordination throughput cell 2025;
dual-arm coordination dynamic picking moving objects reachability scheduling
2025; throughput-oriented bimanual manipulation task allocation parallel arms
2024 2025 arxiv; robotic waste sorting line dual-arm throughput optimization
2025; "Optimization of Dual-Arm Robotic Waste Sorting" digital twin priority-based
algorithms pdf; Jermann multi-robot arm coordination reinforcement learning ethz
pdf; Teck Engelen multi-robot conveyor belt "pick time window" heuristic results
near-optimal pdf; Righettini "High Fidelity Real-Time Optimization of Multi-Robot
Lines" results cycle time; robot sorting cell line balancing workload allocation
dual-arm cycle time industrial deployment 2025; bimanual robot conveyor sorting
deployment parcel throughput 2025; discrete event simulation dual-arm robot
sorting cell allocation policy throughput conveyor; marginal throughput gain from
a second robot arm sorting conveyor picking station shared workspace. Direct
fetches: arXiv HTML (Jermann, ExS2D - full bodies), the KU Leuven lirias PDF and
the MDPI PDF routes (over the fetch cap), Semantic Scholar, T&F and
ScienceDirect (403 / JS wall), the ETHZ repository (500).

**Confidence ledger (this session's new findings).** FULL-READ: Jermann et al.
(arXiv HTML, full body); Cao et al. ExS2D (arXiv HTML, full body). ABSTRACT-ONLY:
Teck et al. IJPR 2025 (abstract + one snippet), Engelen et al. Robotics 2025
(search abstract; publisher 403), Righettini & Cortinovis Robotics 2025
(abstract; PDF over cap), Nupim & Wannapanon 2026 (Semantic Scholar entry).
SNIPPET-ONLY: RoboPARA, Li et al. EJOR 2026. The folded P9-E scouts keep their
own marks (`logs/p9e/EXTERNAL_A_MOTION.md`, `EXTERNAL_B_CONVEYOR.md`,
`EXTERNAL_C_GRASP.md`). No number from an unread body is used in a
pre-registration; the two `ABSTRACT-ONLY` numbers quoted (the 4 % and the
3.6 %/37.5 % pair) are collection items only.

**Local sources.** AGENTS.md section 2 (the W/R record + R5);
`docs/papers/MECHANISMS.md` (the P6 menu, gaps, corrections);
`docs/KNOWLEDGE_BASE.md` (the map + the negatives register); `logs/w6/SPEC.md` +
`BASELINE.md` + `C_RESULTS.md`; `logs/w1/RESULT.md`; `logs/w3/`; `logs/w4/`;
`logs/w7/` (A/B/C); `logs/p6/B3b_reread.md` + `B4_reread.md`;
`logs/p8/A_RESULTS.md` + the B-lane offline files; `logs/p9/GOREADY_OFFLINE.md` +
`PREREG_GOREADY_B1.md`; `logs/p9a/`; `logs/p9b/RESULTS.md`; `logs/p9c/RESULTS.md`;
`logs/p9d/PHASE_COUPLING.md`; `logs/p9e/EXTERNAL_{A,B,C}*.md`; the P10 plan
(`.slim/deepwork/sorting-pipeline-v3.md` "P10 PLAN"). Tree reads for the park
semantics: `src/fruit_sorting/tasks.py` `go_ready`/`_ready_move` (the scope
predicate), `_biarm_park` (gate + early-out + `go_ready(arm)`), and the worker
cycle (`_biarm_worker` finally-block order). No simulator run; no `src/` change;
the only writes are this file and the evidence record under `logs/p10/`.

---

**Fold (2026-10-17, the Oracle gate's required update):** P10-A (2026-10-17,
`logs/p10/A_RESULTS.md`): two-line 12/20, 3.64/3.63 placed/min, interval 16.53/17.30/19.90 vs
single 13/18, 2.12/2.17 (window 1.67x; branch discipline per section 1); records replay
bit-for-bit (861/861, 643/643, 365/365). Blockers 1-2 closed: the per-gap park transit is
load-bearing (only the batch-boundary re-ready is a no-op, 2 x 1.92 s/batch, outside the
window) - L1's kill fired. P9-A multi-seed: the gap falls on all 3 seeds (5.2/5.1/5.1 ->
3.25/3.3/3.3), pooled success net-positive (A 20/30 vs B' 23/30); the seed-5 floor kill was a
branch; the adoption path = a new multi-seed pre-registration. The P10-C prereg (the monitor
extended to the two-line) is frozen at `logs/p10/PREREG_MONITOR_TWOLINE.md`.
