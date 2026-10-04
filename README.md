# Agent-DiffusionPolicy: bimanual fruit sorting on a dynamic conveyor

Research code for an Agent + diffusion-policy controller that sorts fruit moving on a
conveyor line, built on NVIDIA Isaac Sim 6.

The long-term design (slow Agent loop, skill-routed diffusion policy, experience memory)
is summarised in [`实现方案总结.md`](实现方案总结.md). This repository holds the working
implementation: the simulation cell, the data pipeline, and the policy training code.

> **Layout v3 (current).** The output bins, the pop-up pick lifter and the belt
> gate are **gone** - none of them has a counterpart in a real produce line, and
> the owner asked for them out. Two **raised output conveyors** now flank the
> robot, running along +X above the main belt (top `z=1.35`, surface `0.10 m/s`):
> the robot lifts the fruit over the line and releases it 10 cm above the near
> half of the belt, and the belt carries it away. Each belt ends in a **discharge
> chute and a shallow collection tray** at `x=1.65` (a settled fruit is counted
> `discharged`, not `fell_off`). The release is a free drop
> (`FRUIT_RELEASE_SUPPORT=0`; the old floor-supported set-down is kept as a knob).
> The release point is `(0.43, +-0.50, 1.45)`, **not** the belt centre, because
> IK measured the belt centre `(0.65, +-0.55)` 211 mm outside the reach at this
> height (`logs/422/423`). The main line is unchanged: it still runs across the
> robot's front (along Y, robot beside the line like a worker), the grasp is
> solved top-down with the jaws closing across the belt, and the guide rails are
> gone. A four-attempt smoke run scored 3/4 with every placement on the belt
> (`logs/424`). The **shipped hand** is now the robot's own visible jaws
> (`FRUIT_GRIPPER_KIND=openarm`): their close takes ~1 s, so they take an
> **indexed** pick (`FRUIT_DYNAMIC_PICK=0` - the belt stops the fruit at the
> station and restarts after the lift). The **kinematic pad hand**
> (`FRUIT_GRIPPER_KIND=kinematic`) keeps the older **dynamic on-the-fly** line
> with the belt never stopping; the "belt never stopped" numbers below
> (`logs/482_v3b.log`) are that pad-era line and are history for the default.
>
> **P2 moving catch (built, measured, not shipped).** A scheduled on-the-fly
> catch for the OpenArm jaws now exists behind `FRUIT_DYNAMIC_PICK=1` (and
> `FRUIT_BELT_SPEED`): the hand waits at the station hover and meets the fruit
> with a static descent, the two-phase close follows the fruit's live extent, and
> the lift breaks the belt contact vertically. The catch itself works (5/5
> instrumented at 0.12 m/s, close-start y within 3 mm, `gate_open=0.0s`), but the
> grip fails 6 of ten attempts at 0.12 m/s on the frozen P2b tree, so the shipped
> default remains the P1 indexed line. **The corrected failure record:** the final
> P2 instrumented run (`logs/p2_trace10.log`, 7/10) showed the centered failures
> losing the fruit *while the jaws closed* (cross-belt +122/+147 mm, force 0
> through the hold), but the P2b re-measurement on the frozen tree does **not**
> reproduce that lateral expulsion (every close-phase |dx| <= 20.6 mm before the
> fix, <= 15.7 mm after it): the frozen-tree failures are **3 catch-misses**
> (the arrival-synchronised descent/catch-up ends 35-107 mm from the fruit, so
> the jaws close late) plus **3 lift-slips** (the close and hold hold the
> payload, which is then lost at the 50 mm belt-clear/first lift). The band
> numbers previously quoted mix three code revisions and are **not** a speed
> curve; the per-speed failure sets are 0.06: A1/A3/A7/A9 (6/10); 0.09:
> A0/A1/A3/A4/A7/A9 (4/10, kiwi and apple hold). **The P2b close fix** (freeze
> the closing command at first sustained contact; stop steering the hand along
> the closing axis) reduced close-phase dx ~4x but the rate is unchanged:
> N=5 trace-off runs before the fix 4/10 five times (bit-identical to
> `canonical5/6`), N=5 after 4/10 five times (same six failures). Pre-final and
> post-fix dynamic runs also breach the payload-free descent budget (up to
> **0.100 m/s** against 0.06; 0.065 post-fix) and the failure legs carry
> friction-cone breaches, so the dynamic line never passed the motion gate. The
> next lever is the catch-up/intercept and the take-off, not the close depth
> (WORKLOG entries "P2 correction: ...", "P2b diagnosis ..." and "P2b
> result ..."). **Shipped default re-checked on the fixed tree:**
> `ACCEPT_LOG=logs/p2b_accept_fixed.log scripts/accept.sh` gives **10/10, motion
> gate PASS, fingerprint matches** `configs/motion_reference.json`, and its
> `[fruit]` lines are bit-identical to the P2 `logs/accept.log` - no fingerprint
> re-record was needed.
>
> **P3 arrival + take-off (P2b's named next levers; measured, not shipped).**
> Two changes inside the opt-in dynamic path, frozen at
> `logs/p3_arrival_takeoff/tree_rates.sha256` (`tasks.py` sha256
> `a4b4057f...`). (1) The descent is now timed by the leg's *actual* profile
> duration (the old estimate fed the jaw-space hover height - 0.06 m - 12 %
> longer than the 0.054 m TCP distance the leg really covers) and the predicted
> intercept is printed; a target shift ("aim downstream") was tried and measured
> worse - it lengthens the descent, so the fruit overshoots more and the
> stationary hand gets hit from upstream (`logs/p3_arrival_takeoff/smoke1.log`
> A1 residual 175.3 mm against 46.0 mm). (2) The catch-up commands
> `fruit + v * 0.25 s` *while the tip is upstream* and the fruit itself when the
> tip is already downstream, removing the drive-lag equilibrium that stranded
> A1/A6/A7 35-107 mm short. The take-off now rides the belt: the probe tracks
> the fruit and does a force-limited 1 mm squeeze in its first 0.1 s, the
> belt-clear matches the payload's measured velocity for 0.2 s while lifting,
> then decelerates to the world frame in 0.25 s. **Measured** (trace off,
> N=5 x 10 at 0.12 m/s, frozen tree): **6/10 five times, bit-identical**
> (161.0 s each, `gate_open=0.0 s`, zero `indexed:`) against 4/10 before; the
> catch-up residual is **<6 mm on 10/10** (A1/A7 fixed: 46.0/35.1 -> 6.0/5.9).
> The four remaining failures are A2/A8 (left-arm carry slip: the lane-0 grip
> sits ~8 mm off-centre in y and slides down mid-lift), A4 (strawberry crush,
> pre-existing) and A6 (kiwi walks +x ~50 mm through the x-locked close): the
> take-off trace shows force steady at 4.4-4.5 N through all 94 probe+clear
> ticks and the loss moved into the `grasp_lift` carry. **Corrected** (WORKLOG
> "P3-fix"): on the frozen revision the left grip is centred (hold offset
> +0.7/+0.4 mm) and the carry tracking error is symmetric, the carry speed and
> the grip height were falsified as fixes, the 2.5 mm squeeze floor cannot be
> reduced into a gentler clamp (the force is the 10 N/joint drive cap), and
> tracking the kiwi's walk chases the squeeze-out. All four classes are one
> contact-geometry limitation of the flat, hard pads; the audit tool is
> `scripts/143_dynamic_classes.py`. **<9/10, so the dynamic
> line stays opt-in** (`FRUIT_DYNAMIC_PICK=1`; the default remains the P1
> indexed 10/10 line), the 0.18/0.24/0.30 curve is not measured, and no clip is
> recorded. Shipped acceptance on the same tree:
> `ACCEPT_LOG=logs/p3_arrival_takeoff/accept_shipped.log scripts/accept.sh`
> gives **10/10, motion gate PASS, fingerprint matches** - no re-record (WORKLOG
> "P3 arrival + take-off").
>
> **P3 contact faces (the lever P2d named; measured, not shipped).** The
> remaining dynamic classes were attacked from the *face asset/material*
> (`scene.py`; no `tasks.py` change was needed). Every knob defaults off, so the
> default build is the P3-fix one byte for byte. Two V/cup families were authored
> against the finger links' exact contact frame (the prismatic joint axis and the
> TCP tip direction, not the mesh PCA - the PCA version is tilted ~15 deg and put
> a 16 mm wing into the jaw gap, jamming the catch-up,
> `logs/p3face/probe_geom_v`): **additive** wings whose valley is on the face
> plane and which protrude 3 mm (`v`, `h`, `x`, `c`), and **recessed** grooves
> whose valley is 3 mm behind it with the shipped mesh collider replaced by a
> complete box-built face (`h2`, `v2`, `x2`). Measured (trace on, 10 attempts,
> 0.12 m/s, `logs/p3face/screen_*`): flat hard 6/10 -> `v` 4/10, `h` 5/10,
> `x` 2/10, `x`+soft 4/10, `h2` 6/10, `h2`+soft 5/10, `v2`+soft 3/10,
> `x2`+soft 1/10 - the protruding faces bat the fruit on entry, the recessed ones
> remove the entry problem but also the self-locking wedge. The material side is
> the one positive: a **compliant contact** on the flat faces (spring-damper
> `F = k*penetration + c*d(penetration)/dt`, k=30000 N/m, c=80 Ns/m,
> `FRUIT_FINGER_COMPLIANCE`) fixes the strawberry class (close force spike
> 65.4 -> 21.1 N, close dx +11.3 -> +0.5 mm, hand slide 1352.9 -> 0.0 mm) and
> lifts the dynamic rate to **7/10, bit-identical x5** (161.7 s each,
> `gate_open=0.0 s`, zero `indexed:`), robust for k=1e4..1e5. Raising the
> effective friction (`frictionCombineMode=max`, `FRUIT_FINGER_MU=8`) does *not*
> fix the carry slide or the kiwi walk and re-ejects the strawberry (6/10).
> **7/10 < 9/10, so the dynamic line stays opt-in** (`FRUIT_DYNAMIC_PICK=1` plus
> `FRUIT_FINGER_COMPLIANCE=30000`), the speed curve is not measured, and the clip
> is a labelled mechanism clip (`logs/p3face/video_dynamic_k30/`). Shipped
> acceptance: `ACCEPT_LOG=logs/p3face/01_accept_p3face_shipped.log
> scripts/accept.sh` **10/10, motion gate PASS, fingerprint matches** - no
> re-record (`logs/accept.log` untouched); selfcheck PASS. **Correction** to
> P2d's "one limit": only A4 is a hard-contact force limit; A2/A6/A8 survive
> compliance, higher friction and every groove tried (WORKLOG "P3-faces").
>
> **v4 shape x compliance retest (the P3-face screen, redone with the dynamic
> controls).** P3's faces were screened *before* the bounded x-seek, the
> loaded-grip re-close guard and the walk latch, so the combination was re-measured
> on the v3-C2 robust line (0.12 m/s, compliance k=30000 c=80, trace on, 10
> attempts per design, `logs/dyn_v4/`): flat **8/10**; additive `v` 5/10, `h`
> 6/10, `x` 4/10, `c` 5/10; recessed `v2` 2/10, `h2` 5/10, `x2` 3/10, `c2` 1/10.
> The protruding wings bat the catch and re-crush the strawberry (Fmax 12-71 N);
> the recessed box faces crush harder (Fmax 76-180 N, span -> 0-1 mm). Trace-off
> rates on the frozen tree: flat **8/10 x5**, bit-identical (A2 place fall-through
> + A6 kiwi lift escape); best shape `h` **7/10 x5** (A2/A6/A8, F 0.00 N). The
> 0.12 bar (>=9/10) is not met, so the dynamic line stays opt-in and the speed
> curve is not run (WORKLOG "v4-D"). Acceptance:
> `ACCEPT_LOG=logs/dyn_v4/01_accept_frozen.log scripts/accept.sh` **10/10, motion
> gate PASS, fingerprint matches** - no re-record; selfcheck PASS. Labelled
> mechanism clip `logs/dyn_v4/video_mechanism_flat/`.
>
> **v5 force servo (the v4-D named lever).** The close freezes the commanded jaw
> separation at the depth the fingers found the fruit at, so the drives hold a
> fixed face separation and a shrinking local width runs the faces out of travel
> (`sep` converges onto `gap_cmd`, F 4.4 -> 0 in two ticks). The
> `FRUIT_DYNAMIC_FORCE_*` servo (default **off**) reads the tactile force every
> grip tick and moves the commanded separation by at most 0.4 mm/tick: below
> `max(2.0 N, 0.8*ref)` for 3 ticks it closes, above 12 N it backs off, bounded
> to -15/+3 mm around the closed gap, with `ref` the grip's own settle force
> capped at 4 N; the manifest records the knobs. It runs through the hold, the
> take-off probe, the belt-break and both carry branches of the openarm hand.
> Measured (0.12 m/s, trace off): **all four configurations are 8/10** - the
> v4-D baseline (A2 place + A6 artifact), the lift-origin fix alone (A2 place +
> A8, kiwi placed), the servo alone (A2 lift + A6 lift, x3) and servo + fix
> (A2 lift + A8 lift, x5) - the >=9/10 bar is not met and the A6/A8 slot
> alternates with the branch while A2 fails in every config, so the ceiling is
> the first-lift contact geometry, not the force law. The servo's mechanism is
> visible: it tracked A2's shrinking width for the full 15 mm (38 trips), left
> the kiwi at 0 trips, and backed the strawberry off its >12 N crush. The per-class measurement also
> found the A6 "kiwi lift escape" was a **book-keeping artifact**: the kiwi is
> squeezed up ~0.4 m during close/hold, the carry descends to its nominal goal,
> and the lift metric taken after the probe read -0.11 m while the hand carried
> the payload (clearance +381 mm, 4.4 N through 505 carry ticks); moving the
> metric origin before the probe places the kiwi on that branch - but v6's
> dwell+ramp branch re-entered the artifact (the final z sat 10 mm *below* the
> pre-probe origin after the carry's descent), and v7's peak-hold metric
> (maximum payload z through the probe/belt-break/first carry, default on only
> inside the dynamic path) is the fix that holds across branches: the kiwi
> reads +0.185 m and places, 7/10 -> 8/10 on that branch, while A2/A8 stay real
> escapes (see WORKLOG "v7"). The A2 place trajectory was
> checked and is not the differentiator (every attempt tracks ~26 mm below the
> command; A2 falls because its seat slid 27 mm during the lift). Policy arm
> (trigger, moe_v10): 13/45 = 29 % -> 10/29 = 34 % (on arm aborted at episode 29
> on a contact grind), paired 5 vs 4 discordant = no measurable grip-loss
> shrink. Dynamic stays opt-in (`FRUIT_DYNAMIC_PICK=1`), no speed curve.
> Acceptance `logs/dyn_v5/01_accept_v5_servo.log` **10/10 + gate + fingerprint
> (stats identical to the v4-D run)**; selfcheck PASS; labelled mechanism clip
> `logs/dyn_v5/video_mechanism_servo/`.
>
> **Layout v2 (history).** The lifter/bins numbers (`logs/416`, 9/10, `hand_gap`
> 28-48 mm) describe parts that no longer exist and are kept only as history; the
> v1 (end-on) numbers are older history still. Do not compare success counts
> across layouts.

## Current status

| Piece | State |
| --- | --- |
| Isaac Sim headless bring-up on this machine | working (`scripts/smoke_test_isaacsim.py`) |
| Robot: OpenArm bimanual upper body (2x 7-DoF arms + parallel grippers) | loading, articulated, verified |
| Sorting cell: pedestal, main conveyor with surface velocity, two raised output conveyors with discharge chutes and collection trays | built and verified |
| Head RGB-D camera (single camera, wide FOV) | capturing rgb + depth + instance ids |
| Randomized fruit on the moving belt | spawning, transporting, recycling |
| Scripted pick-and-place, **layout v3, shipped OpenArm hand** (`FRUIT_GRIPPER_KIND=openarm`, indexed pick `FRUIT_DYNAMIC_PICK=0`, two raised output conveyors) | **working** - **10/10** in `logs/accept.log`, motion gate PASS and fingerprint matches `configs/motion_reference.json` (descent `\|v\|max` 0.029 against 0.06, lurch 0.016 against 0.12, carry cones 0.85-0.96x), visible jaws pinch the fruit at 2.38-23.00 N |
| Scripted pick-and-place, layout v3 **pad hand, dynamic line** (`FRUIT_GRIPPER_KIND=kinematic`) *(pad-era history)* | **10/10** in `logs/482_v3b.log`, belt never stopped, 35.6 s of simulated time per attempt, motion gate PASS against the then-shipped baseline |
| Point-tactile sensing on the grippers | **working** (per-finger contact sensors) |
| Demonstration collection | **working** (`scripts/40_collect_demos.py`) |
| Skill-Routed MoE diffusion policy | **implemented + trained**; current checkpoint `checkpoints/moe_v6` (v2 layout, val 0.0297, router 0.988, hybrid 9/10) |
| Inference speed | 3.3 ms/chunk at 2 DDIM steps, 6.4 ms at 4 (budget is 50 ms; `scripts/80_benchmark_policy.py`) |
| Realistic fruit assets | procedural meshes, per-category shape/colour/friction/density |
| Cleated belt conveyor with friction transport | working |

> **汇报入口**：[项目总结报告.md](项目总结报告.md)（单一文档，含图表与日志编号）；路线取舍见 [决策与交付.md](决策与交付.md)；一键演示 `scripts/demo_2min.sh`。

> **Contributing?** [AGENTS.md](AGENTS.md) lists the three commands to run before
> finishing, the two measurement constraints this repository depends on, and a
> "what you changed -> what to run" table.

## Results so far

| Stage | Result |
| --- | --- |
| **Scripted pick-and-place, layout v3, shipped OpenArm hand** (indexed pick `FRUIT_DYNAMIC_PICK=0`; the visible jaws are the gripping bodies) | **10/10** (`logs/accept.log`, motion gate **PASS**, fingerprint matches `configs/motion_reference.json`); descents `\|v\|max` **0.029** (budget 0.06), single-tick lurch **0.016** (0.12), all carry legs inside the friction cone (0.85-0.96x), finger tactile **2.38-23.00 N**, lift **+0.287-0.303 m**; belt **indexed** (stops at the station, restarts after the lift) |
| Scripted pick-and-place, layout v3, pad hand (`FRUIT_GRIPPER_KIND=kinematic`), dynamic line *(pad-era history)* | **10/10** (`logs/482_v3b.log`, motion gate **PASS** against the then-shipped baseline), belt **never stopped** (`gate_open=0.0s`), **35.6 s of simulated time per attempt**; descents `\|v\|max` **0.029** (budget 0.06), single-tick lurch **0.020** (0.12), all 20 carry legs inside the friction cone (0.83-0.85x), **0/20** hand-speed rescues; 8 of the 10 placed fruit were followed all the way into the discharge trays and recycled as `discharged` during the run (the last two were still on the line when it ended). The current reference no longer matches this run (re-recorded for the OpenArm hand, `logs/motion_reference_pad_baseline.json` preserves the pad-era fingerprint) |
| **Scripted pick-and-place, layout v2 (belt across the front, taken on the fly)** | **10/10** (`logs/370`, motion gate PASS), belt **never stopped** (`gate_open=0.0s`), **33.6 s of simulated time per attempt**; descent `end=` **4-35 mm** (v1: 40-90 mm short on every leg), `\|v\|max` worst 0.057 against 0.06, one carry rescue reported |
| Scripted pick-and-place (realistic scene) | 8/8, ~98% over a 46-attempt collection run *(history)* |
| Scripted pick-and-place, sustained run on the improved pipeline | 18/20 (90 %), 41.1 s of simulated time per pick, 1 divert (`logs/355`, *history - pre-`a_win5`, not re-checkable*) |
| Scripted pick-and-place, v1 default (profiled approach) *(history)* | **9/10**, **34.7 s of simulated time per attempt** / 38.6 s per successful pick (`logs/accept_run1`, motion gate PASS); descent `|v|max` worst **0.051 m/s** - never past the 0.06 m/s reference - and `a_win5` worst **1.41 m/s^2** against a 2 m/s^2 friction budget. An earlier default scored 10/10 *with* a 2.77 m/s single-tick lurch on one descent (`logs/428`); see the success-rate caveat below |
| Demonstrations collected | **210 episodes**, 60,507 frames, all 8 categories, both arms (`datasets/demos_v5`, counted from the `.npz` files) |
| Demonstrations collected, **layout v2** | **42 episodes**, 21,681 frames, 20,967 training windows, 8 categories, both arms (`datasets/demos_v6`, `logs/381`; `scripts/106_index_audit.py` OK) |
| Skill-Routed MoE training, **layout v2** | 4.59 M params, 15 epochs, val loss **0.0297**, router accuracy **0.988** (`checkpoints/moe_v6`, `logs/382`) |
| Skill-Routed MoE training | 4.59M parameters, 15 epochs, val loss **0.0156**, router accuracy **0.998** (`checkpoints/moe_v5/history.json`) |
| Policy closed-loop evaluation | **5/10** successful cycles (`logs/116_eval.log`) |
| Policy closed-loop evaluation (v3, data from the improved pipeline) | **8/10** hybrid, val **0.0581** (`logs/333`, `checkpoints/policy_kin_v3`) |
| Policy closed-loop evaluation (v3all) | **12/15** hybrid, val **0.0410** (`logs/336`, `checkpoints/policy_kin_v3all`) |
| Policy closed-loop evaluation, **layout v2** (hybrid, physical contact) | **9/10**, all 8 categories, one peach grip loss (`logs/387`, `checkpoints/moe_v6`, val 0.0297) |
| Slow loop (design §4) landed: graph + experience memory + structured goal | decisions at **0.15 ms**, memory retrieval active; with the arrival gate fixed (60 -> 120 mm) the agent scores **10/10 (100 %)**, matching the built-in selector's **8/8** (`logs/364/365`); weight ablation (memory vs arrival profile) is flat; **candidate-level decision logs + an offline ridge-logistic fit (`scripts/102_fit_slow_loop.py`) show no learnable selection signal at n=14** (all coefficients ~0, train acc 79%), i.e. the residual failures are grasp-physics, not selection; an LLM policy hook (`FRUIT_SLOW_LOOP_POLICY=llm`, OpenAI-compatible, 2 s timeout, rule fallback) is validated against a local stub at 42.5 ms |
| Parallel collection throughput | 3 workers x ~1.4 episodes/min (~3x single worker) |
| Policy inference | 3.4 ms/chunk at DDIM 2, 25 ms at DDIM 16 |

The policy tracks the scripted controller imperfectly: 18 demos gave 2/8, 45 gave
4/10, 210 give 5/10. Using more inference compute does not help (DDIM 16 with
re-planning every 4 steps scores the same), so the limit is not sampling.

> **Confirmed, with one correction.** A later A/B with matched instrumentation puts
> the unmodified closing rule at **67 % overall and 20 % on strawberries** (three runs
> of twelve episodes), against **100 % / 100 %** for the measured-extent rule - so the
> strawberry failure described below is real, and the mechanism is measured (every
> one of 15 strawberry closures had *negative* interference). What is *not* stable is
> the absolute rate: the closure diagnostic itself perturbs the run (92 % with it off,
> 67 % with it on), so quote a rate only with its instrumentation. See the WORKLOG
> entry "five runs per arm, and a correction to the correction".

**The closed loop's stable failure is the strawberry, not the policy.** Five
ten-episode hybrid runs at one checkpoint score 100 / 90 / 90 / 70 / 90 % (mean
88 %, worst 70 %) with the same ten targets every time, and the failures
concentrate: the 3.4 cm strawberry fails in three of the five while every other
fruit fails at most once. A fifty-episode small-fruit run pins the cause down
(`logs/108_small50.log`, `scripts/108_fruit_size_probe.py --contrast`): **lychee
26/26 = 100 %, strawberry 9/24 = 38 %** - the same size band, so it is the
strawberry's *shape* (conical, pointed, against flat pads) and not fruit size. 13
of the 15 failures are "fruit did not follow the gripper" with a peak lift under
1.6 cm, i.e. the grip does not survive closure. None of the logged grasp-time
quantities predicts an individual failure - see the rank-sum table in the WORKLOG.

**And the shape problem has a measured cause and a fix.** The task now logs the
geometry it closed with (`FRUIT_CLOSURE_DEBUG=1`): the pad-face separation along the
closing axis, the fruit's own extent along that axis, and the resulting
interference. The code closed to `diameter x 0.98`, which is the right interference
only for a sphere - a lychee's extent equals its diameter (+0.6/+0.7 mm
interference, 100 % success) while a "37.5 mm" strawberry is only 29.4 mm across the
closing axis, so the pads arrived **7.4 mm apart from the fruit**, touched nothing,
and left it behind. `FRUIT_CLOSE_ON_EXTENT=1` closes on the fruit's measured extent
instead; the strawberry's interference goes from -7.4 mm to +0.6 mm, and in the
same fifty-episode protocol the strawberry goes from **9/24 = 38 %** to **19/19**
(run stopped at 40 of 50 episodes, 40/40 overall).

**It is the default now (`FRUIT_CLOSE_ON_EXTENT=1`).** Making it the default was
first blocked by the project's own motion gate - three descents exceeded the gate's
`a_win5 <= 2.0` budget - and that block turned out to be the gate's fault, not the
flag's: 2.0 m/s^2 is `mu_eff * g`, the acceleration **pad friction can transmit while
carrying a payload**, and a payload-free descent carries nothing. The gate now judges
the two legs of an attempt by the two budgets that govern them (descent: commanded
speed plus a single-tick lurch bound; carry: the friction cone), and keeps the old
number as a non-blocking roughness warning so the descent difference stays visible.
The promoted default is bit-identical to the flag-on runs it replaces
(`logs/145_accept_extent_default` = `logs/142_accept_extent_default_1/2`), and the
ten-attempt baseline fingerprint was re-recorded from it. Details, the calibration
logs and what is **still** open (the descent's unlocated end-of-leg blips) are in the
WORKLOG entry "the motion gate was judging the descent by a carrying budget".

**That rejection reason was then found to be wrong, which is worth more than the
decision.** Reverting the flag and re-running the *unmodified* default reproduces
the same motion-gate failure (|v|max 0.148, a_win5 2.78, two legs over budget), so
the breach is not the closure fix's doing. What moved is the attractor: today's
plain default now produces the **identical ten-leg fingerprint** that only
*instrumented* runs produced before (`logs/455/457/458` vs `logs/120/121`), i.e. the
attractor is **not a function of the active code path** and can shift between
sessions. Every cross-configuration success comparison in these documents, including
this closure A/B, was measured across sessions and should be read with that in mind.
The mechanism (negative interference for the strawberry, positive after the fix) is
measured directly and is unaffected. See the WORKLOG entries "closure geometry" and
"promoting the closure fix was tried and rejected by the project's own gate".

That red gate was then diagnosed as a defect in the gate rather than in the default,
and `FRUIT_CLOSE_ON_EXTENT` was promoted (the paragraph above has the resolution). The
descent's end-of-leg blip is a real, still-open item; it is now reported as a warning
instead of being enforced through a carrying budget the descent does not have.

Scaling the *improved* pipeline's data does move the imitation metric but not the
closed loop: 22 episodes / 8,595 training windows -> val 0.0581, 64 episodes /
25,867 windows -> val **0.0410** (the training logs' own counts, `logs/332` and
`logs/335`; `scripts/106_index_audit.py` reproduces both window counts from the
files). Note that the merged sets contain byte-identical episodes - `demos_kin_v3m`
is 22 files but 18 unique, `demos_kin_v3all` 64 files but 60 unique - so the
checkpoints were trained with four episodes seen twice. The merges' *frame counts*
were also stale until this was fixed; see the WORKLOG entry "the dataset index did
not match the dataset". While the
hybrid closed-loop rate stays at **80 %** (8/10, then 12/15) with every failure
being a physical grip loss (`fruit did not follow the gripper`). More data is no
longer the bottleneck for the closed-loop number; the grasp primitive is.

Two things still separate it from the scripted controller's ~100%:

* demonstration volume - the design document's own guidance is 400-600 episodes
  per skill, and the curve is still rising at 210;
* grasp fidelity - the OpenArm finger colliders do not reliably hold fruit in
  this build, so the demonstrations (and therefore the policy's training target)
  use a modelled grasp. The evaluator applies the same model so the comparison is
  like-for-like.

### Motion quality (smoothness and physical realism)

Every gripper move is a **jerk-limited profile with a friction-cone acceleration
budget** (`src/fruit_sorting/motion.py`): the minimum-jerk quintic is
time-scaled so that velocity, acceleration and jerk all stay inside their limits,
and while a fruit is held the acceleration budget is clipped to what pad friction
can actually transmit (`|a + g z| <= mu_eff g`). The jaws and the joint-space
moves use the same quintic blend, and the belt ramps its surface velocity instead
of stepping it.

Measured on the same seed, replacing the old constant-velocity interpolation
(`FRUIT_CARRY_PROFILE=0`) with the profile:

| leg | velocity step at the ends | ticks |
| --- | --- | --- |
| lift 26 cm | 9.27 m/s2 -> **0.00** | 400 -> 330 |
| transfer 40 cm | 14.26 m/s2 -> **0.00** | 400 -> 241 |
| lower 14 cm | 5.04 m/s2 -> **0.03** | 400 -> 93 |

The hand is a rigid, orientation-frozen tool: the pad frame is captured when the
grip closes, so the pads cannot twist off the payload when the arm's IK lags, and
slip compensation is a bounded 9 mm/s crawl rather than a teleport. Slip over a
26 cm lift is **0.1-0.3 mm**, i.e. the fruit is carried by real contact friction
(the earlier code moved the pads onto the fruit every 20 ticks, which is what
actually carried it).

Every approach line also reports **`end=`**: where the leg finished against the point
it was commanded to. It is the one number that says the descent *arrived*, and on both
the shipped default and the carry-cap candidate it reads **40-90 mm on all ten legs**
(`logs/160/161`). That is the cell's documented limit, not a new fault - the pick pose
is outside the arm's reachable band, so the arm runs to its boundary and the
post-descent solver finishes the approach. It also explains the descent's speed
excursions: in an isolated cell with no fruit, 16 descents stay at 0.92-0.96x their
commanded speed (`logs/155`), and the anomaly trace found nothing near the arm at the
jitter ticks (`logs/158`).

Knobs: `FRUIT_CARRY_VMAX` (0.38), `FRUIT_CARRY_AMAX` (2.0), `FRUIT_CARRY_JMAX`
(25), `FRUIT_LIFT_VMAX` (0.18), `FRUIT_LIFT_AMAX` (1.0), `FRUIT_MU_SAFETY` (0.6),
`FRUIT_SLIP_STEP` (0.0015), `FRUIT_BELT_RAMP` (1), `FRUIT_BELT_ACCEL` (2.0).
Set `FRUIT_MOTION_REPORT=1` to print per-leg metrics, and run
`python3 scripts/96_motion_check.py` for the offline unit checks.

**Peak vs. body.** `|a|max` alone is a misleading summary of a leg, so every
motion line also reports `a_med`, `peak@` (where in the leg the peak sits),
`first10`, `last10` and `a_win5` (the acceleration smoothed over 5 control ticks).
On the grasp descent the distinction is the whole story: the interior of the leg
is `a_med` 0.03-0.22 m/s^2 against a 2 m/s^2 friction budget, and the peak is a
start-of-leg transient in the first 3 % of the leg. `|a|max` differences two
1/120 s samples, so on a leg whose steps are tenths of a millimetre it mostly
measures jitter - a 1 mm/tick wobble at 0.06 m/s reads as 14 m/s^2 - which is why
`a_win5` exists and why the peak *speed* is the number to quote. See
`scripts/104_approach_probe.py` (repeat one leg on demand) and the "descent's
roughness is one IK command" entry in the WORKLOG, including the one descent in
twenty across two seeds that still contains an unfixed upward push.

Shipped default, ten attempts (`logs/accept_run1`, checked by
`scripts/105_motion_regression.py` - see "Checking a run against the motion
budgets"): descent `|v|max` worst **0.051 m/s**
against a 0.06 m/s reference, `a_win5` worst **1.41 m/s^2** against a 2 m/s^2
friction budget, `a_med` 0.03-0.27 m/s^2.

**The last lurch was a collider, not a controller.** Tracing every IK step
(`FRUIT_APPROACH_TRACE=1`) showed a single tick in which the *measured* joints
move 0.30 rad while the command moves 6e-5 rad, with a zero velocity target - a
push, not a command. The pusher is the kinematic hand's wrist block, mounted 9 cm
behind the pads and therefore inside the arm's own wrist links. It is visual-only
now (`FRUIT_HAND_WRIST_COLLIDER=0`, the default); restoring the collider puts the
2.8 m/s shove back (`logs/428` vs `logs/439`). It is a win on both seeds, not a
trade: 10/10 + 7/10 across SEED=5 and SEED=11 with the collider on, **9/10 + 9/10**
with it off, and the worst descent 332.8 / 83.4 -> **4.7 / 53.6 m/s^2**. Filtering
the hand against the arm instead was measured **worse** (6/10, `logs/435`), and one
descent in twenty still contains a genuine vertical push of ~3.7 mm
(`logs/440`) - see the WORKLOG for both.

**Instrumentation caveat.** Reading rigid-body poses *inside* the control loop
can change the run, and the effect is specific: reading the **articulation's link
world poses** every control tick does (a per-tick hook reading fruit pose and the
camera does not - `logs/450/451` are bit-identical to the baseline `logs/449`,
while adding arm-link reads shifts the run by 3-14 s of simulated time and one to
two picks, `logs/447/448/452`). The shipped code reads only the TCP and the two
finger prims per tick, so the numbers above stand; values quoted from a trace
that reads more describe a neighbouring scenario and are used only for mechanism.
Adding per-tick work inside `ik_step` shifts it too, even two small array copies
(`logs/453/455`), which is why the triggered anomaly detector is gated off by
default and `logs/456` reproduces the baseline to the digit. Seven runs
(`logs/434/439/441/449/450/451/456`) agree exactly. See the "correction" and "the
residual push cannot be caught from inside the loop" entries in the WORKLOG.

**Read the success-rate A/Bs with care.** The run is deterministic per
configuration but the outcome is *quantized*: every configuration tried falls into
one of two discrete attractors at a given seed - seven runs at 9/10 / 347.2 s and
three at 10/10 / 364.0 s, each bit-identical within itself
(`logs/455/457/458`; see the WORKLOG). A success-rate comparison across two
configurations in different attractors therefore measures the attractor, not the
change under test, so treat e.g. the `FRUIT_HAND_WRIST_COLLIDER` 10/10-vs-9/10 as
"these land in different scenarios". The collider fix itself rests on mechanism
evidence - a kinematic body mounted inside the arm's wrist links pushed joint 5 at
~34 rad/s against a zero velocity target - and on the per-leg motion numbers,
which are measured on the leg in question.

**And the run is reproducible again - the cause was found.** The same command used to
land its first fruit at 8.5 cm from the pick point (328-tick descent) on one run and
8.7 cm (334 ticks) on another, with the whole run following. The measurement that
settled it: sixty `app_utils.update_app(steps=1)` calls advanced **118 ticks on one
run and 120 on the next**, i.e. `update_app` is not a fixed step (the app timeline
moves physics by wall-clock time; `assets.py` already warned that one call can
advance hundreds of milliseconds). `FRUIT_FIXED_STEPPING` (default on) routes every
scripted advance through `SimulationManager.step` instead, and the pipeline is
reproducible: **five of five probes identical, and three ten-attempt acceptance runs
bit-identical in every statistic and every per-leg metric** (`logs/127/128/129`).
`scripts/accept.sh` passes end to end against the current default
(`logs/162_accept_final`, reproduced bit-identically from `logs/151` and
`logs/152`): **10/10**, 364.3 s of simulated time (36.4 s/attempt), worst descent
`|v|max` **0.0550 m/s**
against the 0.06 reference, worst single-tick lurch **0.060 m/s** against the 0.12
bound, worst held-grip cone **0.95x**, one descent roughness warning. The same suite
also passed on the two earlier defaults (`logs/145/146` with the 1 mm slip squeeze and
`logs/136` with the nominal close). The baseline fingerprint was re-recorded each time
the default changed; the earlier copies are kept at
`logs/motion_reference.pre_fixed.json` (pre-fixed stepping) and
`logs/motion_reference.extent_close_squeeze.log.json` (extent close with the 1 mm
squeeze). `AGENTS.md` section 3b still explains how to confirm which branch a run is
on; the distribution advice there applies to data recorded before this fix.

Two things to know about the fix itself. It has to **keep the app pump**:
`update_app` also services the camera/sensor callbacks, so stepping physics without it
starves the sensors (it crashed the evaluator with an empty frame until
`advance()` was changed to `SimulationManager.step(steps)` + `update_app(steps=0)`, and
the evaluator now renders before reading the camera). And it does **not** fix the
policy loop: seeding the diffusion sampler (`FRUIT_POLICY_SEED`) removed one source of
variation, but two hybrid runs at the same seed still differed (6/6 vs 5/6), because
the policy conditions on rendered frames. A policy A/B therefore still needs
N-per-arm distributions - and that protocol is what settled the `FRUIT_CLOSE_ON_EXTENT`
question, which is now the default.

That last point is now pinned down: `FRUIT_POLICY_FRAME_MODE=zero` (a constant frame
instead of the camera) makes three hybrid runs **bit-identical**, while with real
frames they differ in peak lift by up to 0.7 cm - and switching TAA/DLSS off does not
help, so the variance is in RTX rendering itself. The per-episode *outcome* was
identical across all three arms, so aggregate that (not a continuous quantity) and use
N per arm.

**The standard way to compare two policy arms** is now one command, and its first
use already corrected the record:

```bash
EPISODES=12 RUNS=2 scripts/140_policy_ab.sh    # ARM_A / ARM_B select the two arms
```

Two runs of twelve small-fruit episodes per arm, unmodified closing rule against the
measured-extent one: **92 % (83-100 %) overall and 80 % (60-100 %) on strawberries**
for the unmodified rule, **100 %** for the extent rule - **overlapping, so this sample
does not separate them** and the extent close stays opt-in
(`logs/policy_ab_extent/`, WORKLOG "the A/B, and a result that invalidates the
strawberry numbers"). The same run is what withdraws the 38 % strawberry figure
quoted above.

With the closure diagnostic on for both arms (three runs each) they do separate:
**67 % overall / 20 % strawberries** against **100 % / 100 %**, and the closure records
show why (negative interference on all 15 strawberries versus a positive median) -
`logs/policy_ab_extent5`, WORKLOG "five runs per arm, and a correction to the
correction". Promoting the measured-extent close was still tried and **reverted**: the
scripted line then scores 10/10 and is reproducible, but three of its descents break
the motion gate's windowed-acceleration budget (worst 2.740 against 2.0, versus 1.800
with the flag off), so the flag stays opt-in until the end-of-leg transient is fixed or
that budget is re-derived for an unloaded leg.

**Hand-off.** The fruit is picked up *where the indexed belt left it*
(`FRUIT_HANDOFF=contact`, the default): the pads are placed on the fruit's
measured position, so no teleport is needed. The old
`spawner.place(...)` pop is kept only as a logged fallback for a fruit that
stopped more than `FRUIT_HANDOFF_MAX` (0.30 m) from the pick centre.

**Known limit, now measured.** The arms' own jaws sit ~22 cm from the kinematic pads
(`hand_gap=` in the log): the calibrated pick pose is outside the arm's reachable
band at belt height, so the hand acts as a longer rigid tool and the arm
translates it. Raising the pick station was tried (`FRUIT_NEST=0.05`) and made the
IK worse (610 mm residual, logs/242); fixing it properly needs a self-centring
feeder plus a multi-seed IK, which is the open workstream (see WORKLOG).

The band is bounded by a **collision, not by joint limits**, and that is what every
descent's 40-90 mm shortfall (`end=`) actually is. `scripts/47_robot_collision.py`
drives the jaw 35 cm straight down from the calibrated grasp configuration:

| scene | travel | stops at |
| --- | --- | --- |
| with the conveyor (`logs/166`) | **3.8 cm** | z = 1.247, i.e. 8 cm above the belt top (1.170), with the finger geometry inside the belt |
| without it (`FRUIT_PARTS=environment,pedestal,robot`, `logs/167`) | 23 cm | z = 1.049 |

So the descents are commanded into the belt, they end where the hand hits it, and the
`|v|max` excursions the gate flags are the servo pressing into it. Gains and integral
action were both measured against that and change nothing (`logs/163/165`); the fixes
are a pick station the hand can reach clear of the belt, or a descent command that
respects the boundary by construction.

**Measured, not assumed.** A multi-start IK probe (`scripts/97_reach_probe.py`)
shows both arms *can* present a top-down hand at the pick point - fingers
pointing at the ground with the jaws closing along y reach 5.8-7.1 mm residual
(the earlier "no top-down wrist" result was a wrong closing-axis choice plus a
sign error in the probe). The coherent hand is implemented behind
`FRUIT_COHERENT_HAND=1` and its parts are each verified: a solve-measure-correct
servo reaches **0.3-5.4 mm** fingertip accuracy, an explicit attitude servo holds
the tool axis to `1-cos <= 0.005`, station re-selection keeps it on the presented
fruit, and one attempt has grasped and placed at `hand_gap = 63 mm` (the real
finger-length scale). It is still not *reliable*, and the reason is measured:
when the pads are mounted on the physical fingertips, every residual of the arm's
pose (0.3-19 cm depending on the instant) is fed into the closing geometry, so the
2 % closing overlap ejects the fruit instead of trapping it (`logs/325`:
`lift = -1.17 m`). The assisted pad frame - pads commanded to the fruit's measured
centre - stays the default and is unaffected (**10/10 twice**).

**Gripper models explored.** The shipped gripper models the grip by commanding the
pad faces *inside* the fruit (an interference closure). A force-limited,
1-DoF-per-finger **actuated** gripper was also built
(`src/fruit_sorting/actuated_gripper.py`, `FRUIT_GRIPPER_KIND=actuated`) and is the
only model in the project that reports a non-zero contact force (16.9 N), but it is
not competitive: best screening **3/5** against **10/10** for the kinematic model in
the same probe, and under wrist noise it throws the fruit out of the world. Its
authoring recipe (explicit prismatic-joint frames, pads as children of the finger
body, drives commanded through USD) and the full screening matrix are in the
WORKLOG.

**The belt is finally a belt.** It was not carrying the fruit: measured with a belt
encoder (`scripts/170_transport_probe.py` reads the cleat travel, i.e. what a real
encoder measures), a fruit resting on the surface (z = belt + radius) travelled at
**18-22 %** of the commanded speed and *span*, and `transport_efficiency = 0.40` was
recording that as normal. `PhysxSurfaceVelocityAPI` only drags a contacting body when
the collider belongs to a rigid body, and the belt slab was a *static* collider. As a
kinematic rigid body (`CleatedBelt.build`, default; `FRUIT_BELT_KINEMATIC=0` restores
the old slab) the same fruit travels at **1.01-1.14x** the surface speed and the spin
ratio drops from 1.4-4.3 to 0.08-0.86. The belt is constant either way - the encoder's
spread is **0.0000 m/s**, and every `[stats]` line now prints it
(`encoder=-0.060 m/s (command -0.060, spread 0.0000)`). Speed is **0.06 m/s**, inside
the 0.05-0.2 m/s range asked for. Ten attempts on that default: **9/10**, the one loss a
release that landed 0.6 m outside the bin, plus three descents over their speed
reference from the belt-collision strain described under "Known limit". (That run is
**v2 history** - the output bins it mentions were removed in v3.)

**(v2 history.)** What was still open from the same request there: the pick loop
still *stopped* the belt and gated the fruit (a dynamic, on-the-fly pick needs a
tracking descent and a cleat-aware window); the arms are on one bimanual base
0.187 m apart, so "one arm on each side of the belt" needs a narrower belt or a
re-authored asset; the side guard rails, a wider belt and rimless bins are
geometry edits that go with that layout. The v3 layout resolved the first of
these (picks are taken on the fly, the belt never stops) and removed the bins.
See the WORKLOG entry "what the new spec still asks for, and what each item
costs".

**Product gating (v2 history).** The fruit was no longer "cut loose" by the script
in v2: a narrow ridge on the belt centre line (`FRUIT_PICK_STOP`, 8 mm tall,
inside the gap between the closed pad faces) gated the fruit, so the line indexed
it to rest by contact. Arrival error dropped from **38-116 mm** to
**-6..+27 mm** (`logs/259`), with the pads still placed on the measured fruit.
The ridge - and the flag - were removed in v3: the line now takes fruit on the
fly with the belt never stopping.

**Grip quality is measured.** Each carry leg reports the payload's motion in the
hand frame as `slip_max=` in the motion report, and the *hand's* own speed as the
`|v|max` that follows `recoveries=`. A reactive regrasp (`FRUIT_SLIP_RECOVERY`, on
by default) re-seats the hand on the payload when the in-hand deviation crosses
25 mm; the reaction no longer squeezes harder (`FRUIT_SLIP_SQUEEZE_STEP=0`), because
the payload is not lost to insufficient normal force - it is *ejected* along the pad
faces, so added interference adds to the ejection. That A/B: 4 affected legs and 17
re-seats with the 1 mm squeeze against **2 legs and 6 re-seats** without it, at 10/10
either way (`logs/145/146` against `logs/149`, reproduced in `logs/151`/`logs/152`).

Reading the hand's speed is what shows where the visible roughness in a carry comes
from: on the shipped run 26 of 30 carry legs hold the pads at the commanded
0.176-0.371 m/s while the 4 legs that slipped move them at **2.96-4.95 m/s** - the
re-seat teleports the hand 25-40 mm in a single tick, and `in-hand |v|max` on those
legs *is* that teleport, not fruit motion. Capping it (`FRUIT_HAND_VMAX`) was measured
and **makes things worse** - the pads then cannot catch a payload that is already
leaving, the relation degrades to the 60 mm cut-off beyond which the controller stops
reacting, and the lagging pads break the carry cone budget (`logs/150`) - so it stays
off and the checker *reports* the number instead of gating it. Stopping the ejection
(a retention feature on the pads, or a transfer that does not load the pad faces) is
the open item - and one version of it is already measured and ready:
`FRUIT_CARRY_VMAX=0.28` takes the carry side to **0/30 rescued legs**, the hand never
faster than its command (worst 0.274 m/s) and every held grip inside its cone, at
+2.3 % simulated time. It is not the default because *that* configuration's branch
contains one descent whose achieved speed is 1.43x what it was commanded. That
excursion is now diagnosed as the arm straining at the workspace boundary rather than
a push (see the `end=` note below and the WORKLOG entries "the carry cap that works,
and why it is not shipped" and "the descent transient is the arm straining at a
boundary it cannot reach"); admitting it means deciding what the descent's speed
budget should mean, which is the owner's call.

**Arrival tolerance (v2 history).** With a gate the line queued, so
`FRUIT_ARRIVE_TOL_STOP` (60 mm) accepted a fruit that stopped behind another one.
That was the last repeatable failure mode; the default 5-attempt suite was
**5/5 with zero errors** (`logs/270_final5.log`). The flag went with the gate in
v3.

**In-hand jitter, measured.** Every carry leg reports `in-hand |v|max`, the
payload's speed in the hand frame: 0.68 m/s peak, typically 0.02-0.24 m/s
(`logs/271`). It comes from the interference grip - the normal force that carries
the fruit *is* the solver pushing it out of the commanded overlap. Two ways of
removing it were measured and both lose the grip (capping the depenetration
velocity: 0/3; a soft compliant contact at 120 Hz: 0/3), because they remove the
load-bearing force; the knobs stay opt-in and the principled fix is a substepped
compliant contact (see WORKLOG).

**Line-full interlock.** A queue at the pick station makes one big contact
island (35 min for four attempts in v2, when the belt gate held the fruit
there). The spawner still holds the release while the queue is
`FRUIT_QUEUE_MAX` (6) deep: 5 attempts in 8.4 min, **5/5 with zero errors**
(`logs/278_queue6.log`).

**Physics substepping.** `FRUIT_SUBSTEPS=N` runs physics at N times the control
rate (default 1 = unchanged). With 4 substeps plus a compliant pad material the
lift-phase jitter goes to **0.000 m/s** (from 0.02-0.68 m/s), but the same grip
then loses the payload in the faster transfer legs and costs ~3x wall clock, so
the default stays the rigid grip; the knobs (`FRUIT_PAD_CONTACT_STIFFNESS`,
`FRUIT_PAD_CONTACT_DAMPING`) and the numbers are in the WORKLOG.

**Throughput.** `FRUIT_MOTION_REPORT=1` runs print a `[stats]` line with
machine-independent numbers - simulated seconds per attempt and per success,
gate-open time and queue depth - because the wall clock on a shared machine
varies by 3x for identical work. Cycle time has come down from **56.5 s to 32.0 s
of simulated time per attempt** (skipping a pointless 4-restart IK: 20.9 s ->
4.4 s; feeding the line only once the arm is in position; abandoning a wait as
soon as the line is empty). A fruit that fails twice is **diverted**
(`FRUIT_MAX_RETRIES=2`, logged as a reject-chute event) and a fruit that waits
`FRUIT_MAX_WAIT_S` (60 s) in the queue is **recirculated** to the feeder; both are
observed firing in `logs/294` and `logs/297`.

Ten consecutive attempts on the released defaults: **10/10 successful, zero
errors, 42.3 s of simulated time per pick**, no reject or recirculation needed
(`logs/299_ten_verify.log`; wall clock 741 s with the simulator at 350-397 % CPU).
Repeated a second time after all later edits: **10/10 again, 42.3 s/pick, zero
errors** (`logs/322_default10_final.log`).

Those two runs are history: they predate the profiled approach (which is ~8 %
faster) and are quoted per *pick* rather than per attempt. The current default,
accepted end to end by `scripts/accept.sh`, is **9/10, 34.7 s of simulated time
per attempt and 38.6 s per successful pick** (`logs/accept_run1`).

## Scene realism

**Fruit** (`src/fruit_sorting/meshes.py`) are procedural meshes, not spheres. Each
is a surface of revolution generated **at its final size in metres** - never via
a Scale xform op, because PhysX mis-cooks scaled collision shapes (a scaled
sphere ends up with no collider that the robot can touch at all; see WORKLOG).

| Category | Profile | Colour | mu | Density |
| --- | --- | --- | --- | --- |
| apple | hand-traced silhouette, stem cavity, 5-lobe lobing | red / green / golden | 0.45-0.70 | 850 |
| pear | narrow neck, bulbous base | yellow-green | 0.45-0.70 | 880 |
| orange | sphere, dimple, bumpy peel | orange | 0.70-1.00 | 900 |
| tomato | flattened sphere | red | 0.50-0.75 | 780 |
| peach | soft dimple | pink-orange | 0.55-0.85 | 820 |
| kiwi | elongated, strong surface noise | brown | 0.75-1.05 | 900 |
| lychee | small, bumpy | red-brown | 0.55-0.85 | 850 |
| strawberry | conical, pointed | deep red | 0.55-0.85 | 700 |

Every instance gets its own deformation, colour jitter and friction sample, so no
two fruit are identical. Apple and pear also get a stalk. Mass follows the real
density: a 6.4 cm apple is 94 g, a 3.7 cm strawberry is 15 g.

**Conveyor** (`src/fruit_sorting/conveyor.py`) runs along `Y` across the robot's
front and is a cleated track belt rather than a sliding slab:

* a rubber belt surface with `PhysxSurfaceVelocityAPI` plus a friction material,
  so fruit are carried by **friction** (a static collider is not dragged by that
  API - see the WORKLOG);
* optional cleats (off by default: with the surface velocity fixed the belt
  carries by friction on its own, and cleats meet small fruit below their centre
  and spin them);
* head and tail pulleys and an aluminium frame; the guide rails are off by
  default (`FRUIT_RAILS=1` restores them).

Measured on the new layout (`scripts/170_transport_probe.py`, `logs/366`): the
fruit ride at **0.059-0.061 m/s** against a commanded 0.060, with a roll ratio
`|omega| r / |v|` of **0.02-0.18** - they travel with the belt and *slide* rather
than roll. The belt surface speed is 0.06 m/s, inside the requested 0.05-0.2 m/s.

**Lighting** is a studio setup: sky dome, a 2.5-degree sun with soft shadows, a
large rectangular fill panel, a concrete floor and a backdrop wall.

## Policy architecture

The policy follows the design discussion rather than a single monolithic net:

```
head-camera RGB + depth + target mask   goal: pose, velocity, size, output lane
              │                                    │
        VisualEncoder                        ConditionEncoder  ──┐
              └──────────────┬───────────────────────┘            │
                       condition vector                         proprioception
                             │                                    │
                    Skill Router (5 classes)                      │
                             │                                    │
     action chunk → shared 1-D UNet backbone ←─────────────────────┘
                             │
          + Σ_k w_k · Expert_k(features)      (residual adapters)
                             │
                        predicted noise
```

* **Skill Router**: 5 classes (approach / grasp / lift / place / recovery).
  Labels come from robot state rules in `policy/skills.py` - no manual annotation.
* **Experts**: lightweight residual adapters initialised as no-ops, so the routed
  model starts identical to the shared backbone.
* **Training**: first 2 epochs **hard routing** (the labelled expert is forced),
  then **soft routing** with a router cross-entropy and a load-balancing loss.

Measured training run, `checkpoints/moe_v1` (`history.json`); its dataset size is
not recoverable from the surviving logs, so the epoch numbers are cited from the
checkpoint rather than from a run log; 4.59M parameters:

| Epoch | Routing | Router accuracy | Val loss |
| --- | --- | --- | --- |
| 1 | hard | 0.536 | 0.169 |
| 2 | hard | 0.770 | 0.115 |
| 3 | soft | 0.923 | 0.096 |
| 5 | soft | 0.989 | 0.076 |
| 8 | soft | **0.993** | **0.056** |

## Inference speed

`scripts/80_benchmark_policy.py` on the RTX 5090, single action chunk. Re-measured
on the current checkpoint with
`python3 scripts/80_benchmark_policy.py --ckpt checkpoints/policy_kin_v3all/policy_best.pt`;
the numbers are within 4 % of the first measurement (which used `moe_v1`), so both
are listed:

| Variant | ms/chunk (`policy_kin_v3all`, re-measured) | ms/chunk (`moe_v1`, first measurement) | Control rate if re-planned every step |
| --- | --- | --- | --- |
| eager fp32, DDIM 16 | 24.3 | 25.2 | 41 Hz |
| eager fp32, DDIM 8 | 12.6 | 12.8 | 79 Hz |
| eager fp32, DDIM 4 | 6.4 | 6.5 | 157 Hz |
| eager fp32, DDIM 2 | 3.3 | 3.4 | 302 Hz |
| fp16, DDIM 8 | 13.4 | 13.3 | 75 Hz |
| torch.compile, DDIM 8 | 12.2 | 12.4 | 82 Hz |

The dominant lever is the DDIM step count, not precision: this model is small
enough that fp16 and `torch.compile` are overhead-bound. Because the policy
produces an action chunk and only re-plans every N steps, the amortised cost is
`ms/chunk / N` - at DDIM 8 with N = 8 that is **1.6 ms per control step**, far
inside the 50 ms / 20 Hz sorting budget.

## Robot choice

The task calls for an **upper-body-only, dual-arm, gripper** robot. The OpenArm bimanual
platform ([enactic/openarm](https://github.com/enactic/openarm)) is an open-source humanoid
upper body with two 7-DoF arms and a 1-DoF parallel gripper per arm, and it ships as an
official Isaac Sim 6 asset with an Isaac Lab configuration. Full humanoids in the asset
catalogue (Unitree G1, AgiBot A2D, Tien Kung, Fourier GR-1) either include legs or use
multi-finger hands rather than grippers, so they do not match the brief.

Since OpenArm has no head, the cell adds a short mast with a single wide-angle RGB-D camera
in the position a humanoid head would occupy. That camera is the policy's only exteroceptive
sensor.

## Layout

Robot at the origin facing `+X`; the main conveyor runs along `Y` **across the
robot's front**, so the robot stands beside the line the way a worker does. Two
raised output conveyors, one per side, run along `+X` above the main belt and
carry the sorted fruit away.

```
        infeed (+Y, upstream)
  ===== main conveyor, fruit travel -Y =====   (belt top z=1.17)
  [ output belt +Y, travel +X, top z=1.35 ]  [ left arm ]
        [ pedestal + OpenArm ]  (head camera on mast)
        pick station at (x=0.34, y=0.0)
  [ output belt -Y, travel +X, top z=1.35 ]  [ right arm ]
        outfeed: chute -> shallow tray at x=1.65
```

The main belt is **end-on to nothing**: it crosses the robot, so the OpenArm jaws
would open *along* the flow. The grasp attitude is therefore solved top-down with
the jaws closing across the belt (along X) - both arms hold it at the station
with a **2.1 mm** residual (`scripts/97_reach_probe.py`), and the left arm takes
the mirror of the right's attitude. See the WORKLOG entry "the line now runs
across the robot's front".

Cell dimensions were derived from a measured reachability sweep
(`scripts/12_reach_calibration.py`): shoulders sit at `(0, +/-0.0935, 1.448)` m with a TCP
reach of ~0.68 m. The main belt surface is at `z = 1.17` m; the output conveyors
are 1.10 x 0.25 x 0.05 m slabs centred at `(0.65, +-0.55)`, surface `z = 1.35`,
driven along `+X` at `0.10 m/s` (`FRUIT_OUTPUT_SPEED`). They are built like the
main belt - a **kinematic rigid body** with `PhysxSurfaceVelocityAPI` (a static
slab does not drag fruit; measured `logs/171`) plus a framed body, legs and
colliding side rails. Measured on the raised belts
(`scripts/422_v3_layout_probe.py`): fruit ride at **1.01x** the commanded speed
with a roll ratio of 0.00-0.02, i.e. sliding as intended.

**Each output belt discharges into a shallow tray.** At the `+X` end face
(`x=1.20`) a 0.28 m sheet at 55 deg drops to a 0.60 x 0.34 m tray (floor
`z=0.92`, 0.14 m walls on a 0.90 m stand, centre `x=1.65`); the fruit slides and
falls into it by gravity and contact only. Before this existed a placed fruit
left the belt at `x=1.20`, hit the floor after ~7.7 s, and the spawner counted it
`fell_off` and respawned it upstream; a fruit that settles in the tray is now
counted `discharged` (a normal end-of-line event) after a 3 s dwell
(`FRUIT_TRAY_DWELL_S`) - or, if the feeder's release schedule reaches its slot
first, at the moment that recycle takes it - and re-enters the pool at the
feeder.

Clearances (builder messages and `scripts/422_v3_layout_probe.py`, all positive):

| Gap | Value |
| --- | --- |
| belt underside (1.30) vs main belt top (1.17) | 130 mm |
| belt underside vs tallest fruit on the main belt (7 cm -> 1.24) | 60 mm |
| belt inner edge (y=0.425) vs robot pedestal (y=0.35) | 75 mm |
| inner support leg face vs main belt frame-rail outer face | **10 mm** (the leg's x-span no longer passes through the rail) |
| inner support leg face vs main belt slab edge | 34.5 mm |
| outer support leg face vs discharge chute start | 50 mm |
| chute lower edge (z=1.12) vs tray rim (z=1.06) | 60 mm |
| belt body vs camera mast | 155 mm in x |
| pick point to nearest belt surface | 425 mm in y |

**The robot places the fruit on the near half of the belt, not its centre.** The
measured IK residual for a release at the belt centre `(0.65, +-0.55, 1.45)` is
**211 mm**; even `(0.43, +-0.55)` leaves 13-40 mm. The reach boundary at this
height sits at about `y_off = 0.41` from the shoulder, so the release point is
`(0.43, +-0.50, 1.45)`, where both arms solve to **7.9-8.0 mm** (`logs/422/423`).
The pads open there (the fruit drops the last ~10 cm onto the moving belt) and the
fingers stay above the belt top; the belt does the rest of the transport.

The pop-up pick lifter (`FRUIT_LIFTER`) and the belt gate (`FRUIT_PICK_STOP`) that
the v2 cell used are **removed**: neither exists on a real line. `grasp.py` still
calls the main belt's immediate `hold()` when the deterministic primitive indexes
the line - that serves the main belt's index, not the lifter.

Grasp geometry, measured in `scripts/36_static_grasp.py`:

| Quantity | Value |
| --- | --- |
| Finger faces at full opening | 0.0758 m apart |
| Finger link origins at full opening | 0.098 m apart |
| Finger span below the jaw centre | 0.076 m |
| Largest fruit the gripper can straddle | ~0.072 m |

## Environment

| Item | Path / value |
| --- | --- |
| Isaac Sim (built from source) | `/home/ubuntu/linalw/App/isaacsim`, launcher `_build/linux-x86_64/release/python.sh` |
| Isaac Sim version | 6.0.1-rc.7 |
| Isaac Lab | `/home/ubuntu/linalw/App/IsaacLab/IsaacLab` |
| GPU | RTX 5090 32 GB, driver 580 |
| Asset root | `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0` |

All scripts are run with the Isaac Sim Python launcher, from the repository root -
and through `scripts/run.sh`, which raises the file-descriptor limit first (see
"Seeing it run" below; without it this build dies ~40 s into the first camera read):

```bash
export ISAAC_SIM_DIR=/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release
export OMNI_KIT_ACCEPT_EULA=YES
scripts/run.sh scripts/10_build_scene.py
```

Set `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` first if the asset server is slow.

## Reproducing the pipeline

```bash
export ISAAC_SIM_DIR=/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release
export OMNI_KIT_ACCEPT_EULA=YES FRUIT_CAMERA_ANNOTATORS=rgb,distance_to_image_plane

# 1. Calibrate the arm waypoints for the current cell (writes configs/waypoints.json)
scripts/run.sh scripts/30_calibrate_waypoints.py

# 2. Collect scripted demonstrations
FRUIT_EPISODES=28 FRUIT_DEMO_DIR=datasets/demos_v1 \
  scripts/run.sh scripts/40_collect_demos.py

# 3. Train the diffusion policy (plain PyTorch; no Isaac Sim needed)
EPOCHS=8 /home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python \
  scripts/50_train_policy.py --data datasets/demos_v1 --out checkpoints/policy_v1

# 4. Evaluate closed loop in the cell
FRUIT_CKPT=checkpoints/policy_v1/policy_best.pt FRUIT_EPISODES=10 \
  scripts/run.sh scripts/60_eval_policy.py
```

`datasets/` and `checkpoints/` are gitignored; regenerate them with the commands above.

### Checking the dataset bookkeeping

```bash
python3 scripts/106_index_audit.py          # every index vs the files it describes
python3 scripts/107_collect_merge_test.py   # regression test for both known bugs
```

### Pre-flight self-check (one command, no simulator)

```bash
scripts/selfcheck.sh                      # three checks; the fourth is skipped
scripts/selfcheck.sh logs/accept_run1.log # ... and judge a pick-and-place run too
```

Runs the offline motion checks, the dataset index audit, the collect/merge
regression test and (given a run log) the motion budgets, printing
`name / result / elapsed` per item and writing everything to `logs/selfcheck.log`.
Any failure makes it exit non-zero; the motion-budget check is *skipped with an
explanation* when no log is passed, because producing one is a ten-attempt Isaac
Sim run (`scripts/accept.sh`).

It takes about **7 s**, almost all of it the dataset index audit hashing ~900
episodes, and it runs **automatically** as the first step of `scripts/accept.sh`
and `scripts/demo_2min.sh` - so a broken tree fails in seconds instead of after a
ten-minute simulator run. Use `SKIP_SELFCHECK=1` to bypass it when you are
iterating on the simulator scripts themselves and already know the offline checks
pass; the gate prints that switch in its own banner.

Neither needs the simulator. The audit checks entry counts, frame counts and
byte-identical episodes across `datasets/*/` and exits non-zero on a mismatch; it
also prints the training-window count per dataset, which is what reproduces the
"N windows" lines in the training logs. The regression test rebuilds the two
situations that produced the mismatch (a collector restarted onto the same output
directory, and a merge of a shard holding a byte-identical episode) and asserts the
fixed behaviour; its docstring records how to make it fail on purpose.

### Checking a run against the motion budgets

```bash
scripts/accept.sh          # ten attempts + the gate + the baseline fingerprint
scripts/accept_policy.sh   # ten hybrid policy episodes + the policy floor and failure-reason gate
```

It prints the per-attempt stats, a per-descent table and a PASS/FAIL verdict, and
exits non-zero on failure - so it is safe to put in front of a report. `demo_2min.sh`
runs the same gate on its own (shorter) run before declaring success.

`accept_policy.sh` does the same for the *policy* closed loop: it evaluates the
shipped checkpoint in hybrid mode, writes `logs/accept_policy.log`, and requires a
success rate at or above `MIN_RATE` (default 0.60) with no failure *reason* the
baseline did not also produce. It fails immediately if the checkpoint is missing,
before starting a simulator, and `JUDGE_ONLY=1 ACCEPT_POLICY_LOG=<log>` re-judges a
saved log without one. Read one run as one sample: five recorded runs score
100 / 90 / 90 / 70 / 90 % (mean 88 %, worst 70 %) with the same ten targets, and the
failures concentrate on the 3.4 cm strawberry, which fails in three of them. The
floor is a regression alarm, not a claim - quote the mean over runs, and see the
WORKLOG entry "five runs of the policy loop".

The checker itself needs no simulator:

```bash
python3 scripts/105_motion_regression.py LOG [--fingerprint configs/motion_reference.json]
```

It judges the two kinds of leg by the two budgets that actually govern them. A
**descent** is payload-free: it must not travel faster than it was commanded (0.06 m/s)
and must not absorb an impulse (one 1/120 s tick may not change its speed by more than
twice the cruise, 0.12 m/s). A **carry** holds the payload, so it is held to the
friction cone parsed from the `[motion] carry` lines (0.84-0.95x budget when the grip
holds); carry legs that fired a reactive re-seat are reported but not gated, because
the re-seat teleports the pads and the finite difference then measures the correction.
The old 2 m/s^2 `a_win5` budget for the descent is still printed as a non-blocking
**roughness warning**. With `--fingerprint` it also compares the per-leg fingerprint
against the recorded ten-attempt baseline, which is how it tells you a run landed in a
**different attractor** - and therefore that its success count must not be compared
with the reference log's. The v3 baseline in `configs/motion_reference.json` was
re-recorded from `logs/427_v3.log` (the v2 reference was a different attractor by
construction); `logs/455` (instrumented) fails on two legs at 0.112 and 0.148 m/s
against the 0.06 m/s reference, and `logs/428` fails on both the speed and the
lurch criterion (2.774 m/s in a single tick).

## Seeing it run

**Watch it live.** Every run script takes `HEADLESS=0`, which opens the Isaac Sim
GUI on the machine's display. Always launch through `scripts/run.sh`: it raises
the file-descriptor limit first, without which this Isaac build dies with
`dup failed ... Too many open files` about 40 s into the first camera read:

```bash
HEADLESS=0 FRUIT_GUI_SMOOTH=1 scripts/run.sh scripts/20_pick_place.py   # live scripted
scripts/130_policy_demo.sh                                            # live trained policy
FRUIT_CYCLES=2 scripts/run.sh scripts/70_record_video.py               # record
FRUIT_MOTION_REPORT=1 ATTEMPTS=5 scripts/run.sh scripts/20_pick_place.py
```

`scripts/130_policy_demo.sh` is the live demo of the *trained* model: the causal
`direct` policy interface with the belt-encoder intercept trigger
(`checkpoints/moe_v10/policy_best.pt`, `FRUIT_CAMERA_RES=240,424`,
`EPISODES=20 SEEDS=77` by default; every setting is an overridable env var and is
documented in the script's header). It refuses to start while another simulator
runs, and `HEADLESS=1` runs the same loop without a window.

**Watch a recording.** `scripts/70_record_video.py` writes:

| File | Content |
| --- | --- |
| `logs/video/observer.mp4` | fixed external view of the whole cell |
| `logs/video/head.mp4` | what the robot's head camera sees (the policy input) |
| `logs/video/gripper.mp4` | close-up on the pick station: is the hand actually on the fruit? |
| `logs/video/side_by_side.mp4` | both views stacked |

The files are H.264/yuv420p with `+faststart` (encoded through ffmpeg), so they
play in any normal player or browser; `FRUIT_VIDEO_DIR` puts them somewhere else.
Capture is tick-exact: one frame every `FRUIT_VIDEO_FPS`-matching physics stride
(4 ticks at the default 30 fps), and the same fps is written into the MP4, so the
clip plays at real speed (the recorder prints a `[video] capture cadence`
evidence line - tick-gap histogram, playback ratio and per-frame render cost).
The current default's clip is `logs/video_v3b/` (2 cycles + a ride-out tail,
44.8 s, 1344 frames; the observer view shows the placed fruit riding its output
belt into the discharge tray); `logs/video_demo/` is the previous layout's clip,
where the pads close on the fruit's measured extent so they actually touch it;
`logs/video_smooth/` is the tick-exact capture clip (3 cycles; the jerk-limited
motion reference clip that used to live there is preserved in
`logs/video_smooth_20260927/`), and `logs/video/mpeg4_backup/` is the only set
still in the old MPEG-4 Part 2 codec that some players refuse to open.

**Look at stills.** `scripts/20_pick_place.py` with `FRUIT_CAPTURE=1` saves
`logs/pick_observer.png` and `logs/pick_head.png` after the cycles finish.

**Inspect the data.** `scripts/106_index_audit.py` checks every dataset's
`index.json` against the `.npz` files it describes (entry count, frame counts, and
byte-identical episodes) and exits non-zero on a mismatch; it also prints the
training-window count per dataset, which is what reproduces the "N windows" lines
in the training logs. Each episode in `datasets/*/` is a compressed `.npz` with
`image_rgb`, `image_distance_to_image_plane`, `joint_positions`, `tactile`,
`goal`, `action` and `fruit_position`, plus an `index.json` summary.

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/smoke_test_isaacsim.py` | Minimal launch check: physics, RGB-D capture |
| `scripts/02_load_robot.py` | Load OpenArm, print joints/limits/TCPs |
| `scripts/03_camera_debug.py` | Verify camera optics from several viewpoints |
| `scripts/10_build_scene.py` | Build the full cell, run the belt, capture frames |
| `scripts/11_bisect_scene.py` | Build selected scene parts (crash bisection) |
| `scripts/12_reach_calibration.py` | Sample the arm workspace |
| `scripts/20_pick_place.py` | Scripted pick-and-place cycles, sorted onto the two output conveyors |
| `scripts/30_calibrate_waypoints.py` | Solve and save `configs/waypoints.json` |
| `scripts/31_reach_sweep.py` | Reachable jaw heights at the pick pose |
| `scripts/32_hold_test.py` | Hold a waypoint; verify joint tracking |
| `scripts/36_static_grasp.py` | Grasp geometry and finger-face mapping |
| `scripts/40_collect_demos.py` | Collect scripted demonstrations into `datasets/demos` |
| `scripts/50_train_policy.py` | Train the diffusion policy (runs outside Isaac Sim) |
| `scripts/60_eval_policy.py` | Closed-loop policy evaluation in the cell |
| `scripts/105_motion_regression.py` | Check a run log against the motion budgets and the baseline fingerprint (no simulator) |
| `scripts/106_index_audit.py` | Check every dataset index against its `.npz` files; `--repair` / `--dedupe` (no simulator) |
| `scripts/107_collect_merge_test.py` | Regression test for the collector-index and merge-duplicate bugs (no simulator) |
| `scripts/selfcheck.sh` | One command for all four simulator-free checks; non-zero exit on failure |
| `scripts/accept.sh` | One-command acceptance: ten attempts, then that gate, non-zero exit on failure |
| `scripts/accept_policy.sh` | One-command policy acceptance: ten hybrid episodes, then the policy floor + failure-reason gate |
| `scripts/demo_2min.sh` | One-command demo: a few picks, a video clip, then the gate |

## Package layout

```
src/fruit_sorting/
  assets.py    SceneConfig (cell geometry) and robot/asset constants
  common.py    numpy/warp helpers, look-at quaternion, logging
  scene.py     SortingScene: builds and drives the cell
  fruits.py    FruitSpawner: randomized fruit, belt release/recycle, state readout
  tactile.py   (planned) contact sensors on the gripper fingers
```

## Known issues in this Isaac Sim build

* The `instance_segmentation` and `pointcloud` camera annotators segfault the headless app
  (6.0.1-rc.7). `instance_id_segmentation`, `semantic_segmentation`,
  `bounding_box_2d_tight` and `normals` work. The cell uses `instance_id_segmentation`.
* `occlusion` and `camera_params` annotators raise on creation.
* Camera optics are expressed in tenths of a scene unit, so on a metre stage a 16 mm lens
  is `0.016` and a 36 mm sensor is `0.036`.
* Kit's fast shutdown discards buffered stdout; every log line is flushed.
