# ROADMAP: the long project-optimization plan

Status: **written 2026-10-12** on branch `w8-confirm` (PP-P2 of the P-PLAN,
`.slim/deepwork/sorting-pipeline-v3.md`), **gate-fixed as P2.1**; **state
updated by W8-B.1** (2026-10-13, branch `w8-carry` - R1's outcome and the
tree/branch pins in section 1); **WS-2 outcomes added by the R2 pass**
(2026-10-13, branch `w8-residuals`), **gate-fixed as R2.1** (the three-term
numbers re-derived to `logs/w8/R2_flail_analysis.txt` /
`R2_probe_report.txt`, the selector-leg verdict downgraded, the 5/10 -> 6/10
canary-note propagation into `logs/w7/C_RESULTS.md`); **WS-3 outcomes added by
the R3 pass** (2026-10-13, branch `w8-speed`, `logs/w8/R3_RESULTS.md`).
Numbering: the plan's phases are **R0-R6** (this document), and the P-PLAN
deliverables carry the **`PP-` prefix** (PP-P1 ops tool / PP-P2 this roadmap /
PP-P3 validation) so the two schemes cannot collide. Scope: the work after
W8-A - the shipped lines, the open levers, the phases, the budgets, the
self-check cadence, and the owner-decision register. It is the durable
counterpart of the progress file; `WORKLOG.md` remains the append-only evidence
ledger and `logs/` the evidence store.

Discipline (binding, AGENTS.md section 2 - do not re-derive):

* The scripted line's outcome is **quantized per configuration**: compare
  per-leg motion metrics and mechanism, name the attractor/branch, and never
  quote a success-rate delta between configurations. A two-line log is a
  different scenario with its own reference (`configs/motion_reference_twoline.json`,
  gate it with `scripts/190_twoline_gate.sh`).
* Every quoted number is **Tier A solo** (`154_claim_run.sh`); Tier B (<=3,
  `180_claim_slot.sh`) is mechanism probes only; Tier C (no sim) is free.
* The **shipped single-arm default stays byte-unchanged** (acceptance +
  `fingerprint: matches`); new levers are default-off, two-line- or
  policy-scoped via `_dynamic_profile`, and negatives are published like
  positives.
* Branch-per-phase + version tags; a phase is merged only after its gate
  (owner, 2026-10-11).

Report-ready summaries are in `项目总结报告.md` (Chinese); route trade-offs in
`决策与交付.md`; design intent vs actual in `实现方案总结.md`; the frontier
menus in `logs/w5/FRONTIER.md` (failure mechanisms) and
`logs/w6/FRONTIER_THROUGHPUT.md` (throughput/interval).

---

## 1. The current state (one screen)

| piece | state | evidence |
| --- | --- | --- |
| **Shipped single-arm dynamic line** (OpenArm, never-stop catch, v9/V1 scattered supply, `FRUIT_DYNAMIC_PICK` unset) | **9/10, 15.2 s/attempt, 3.55 placed/min**; the one failure is a left place/carry escape; x5 bit-identical | `logs/v1/31_accept_supply_verified.log`, `logs/v1/20_rate_supply_1..5.log`, AGENTS.md section 2 |
| Acceptance of record on the current code tree (`tasks.py` `0c51cfa5`, R3; every R3 knob off, L2/L3 two-line only) | **9/10, 15.2 s/attempt, motion gate PASS, `fingerprint: matches`**; its 385/385 `[fruit]` lines are byte-identical to the R2 acceptance (`logs/w8/R2_accept.log`), itself identical to W8-B/W7-A | `logs/w8/R3_accept.log`; single-arm reference `configs/motion_reference.json` (`b9e72ca7`) |
| **Two-line opt-in** (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`; left station y=0.00 grade A, right y=-0.10 grade B, C passes; patch sheet) | W6-B baseline **10/20, 2.78 batch / 2.70 window placed/min**; same-scenario single arm **13/18, 2.12/2.17** -> pre-registered window ratio **1.24x** (< the 1.25x flip bar); pooled interval 22.20 / p90 45.50 s | `logs/w6/BASELINE.md` |
| **Park-gate lever is the two-line default** (W7-A; `FRUIT_BIARM_PARK_EARLY` resolves to 1 under a two-line session) | replays W6-C bit-for-bit: **12/20, 3.64 batch / 3.63 window**, pooled interval **16.53 / 17.30 / 19.90 s**, left gate-blocked idle **25.2 -> 0.2 s**, idle 18 %/24 %; timing-only +10 %, residual x1.22 branch factor; **R3 (WS-3) adds no speed lever on top**: the L2 adaptive lead is bit-identical (the fixed 1.5 s floor *is* the measured setup; 0/20 floor-bound), the L2 tight override probe is negative (8/20, window 2.59; zero new failure reasons), and the L3 hot-arm residency fires **4/18** and leaves the interval flat-to-worse (window 3.41, pooled 17.62 s; idle 27 %/27 %) - all default off | `logs/w7/A_RESULTS.md` (861/861 physics lines vs `logs/w6/31/32`); `logs/w8/R3_RESULTS.md` + `R3_l2_checks.txt`/`R3_l3_checks.txt` |
| Dense W3/W4 wave sheet re-record (moved branch) | **7/10, 9.1 s/attempt, 4.60 placed/min**, `diverted=0`; own reference `configs/motion_reference_twoline.json` (`181c9151`); pre-flip control replays W4 bit-for-bit with `PARK_EARLY=0`; re-recorded on the W8-B tree (W8-B.1): `logs/w8/70_w8b1_twoline.log` is 442/442 `[fruit]`-identical to the W7-A pair and `scripts/190_twoline_gate.sh` PASS | `logs/w7/A_RESULTS.md`, `logs/w7/15_dense_control_park_off.log`, `logs/w8/B_RESULTS.md` |
| **Policy** | shipped default **`moe_v12`** (`accept_policy.sh` line 75); direct causal loop is the measurement, the hybrid canary is the gate | `logs/w4/VERDICT.md`, `logs/w7/C_RESULTS.md` |
| `moe_v13p` (W7-C patch recollection) | **not adopted**: W8-A N=5 confirmatory batch **21/75 = 28 % vs 22/75 = 29 %, sign p = 1.0000**, carried-class pairing 0 B-only / 2 A-only (the N=3 3-0 was noise); the carry class is 89-91 % of failures on both arms | `logs/w8/A_RESULTS.md` |
| ACQ knob (`FRUIT_POLICY_TRIGGER_ACQ`) | default **off**; the direct evaluation pins `=1` (it removes the acquisition class: left no-contact 15 -> 0, close-start 120 -> 2.5 mm); no N=5 ACQ-off mirror exists | `logs/w7/C_RESULTS.md` section 1, `logs/w7/B_RESULTS.md` |
| Pinned canary, `moe_v13p` ckpt (shipped scenario, fixed supply; **not** the shipped default `moe_v12`) | **8/10 PASS** (floor 60 %); matches the `moe_v13s` sample | `logs/w7/C_eval/canary_pinned.log` / `.out` |
| W3-supply (dense sheet) hybrid canary | **still open** (spaced supply measured ~15-20 min/episode; diagnose the handoff station wait first) | `logs/w3/HANDOFF.md` |
| **Clearance** | dense W3/W4 moved branch **2.59 mm min, 863/10042 = 8.6 % < 30 mm**; patch battery **1.9 mm, 4.7 % < 30 mm**; the F2 **45 mm / zero-under-30 convention is not met**; no arm-arm contact is possible (`enabledSelfCollisions=0`) and no attempt has ever failed by contact | `logs/w7/A_RESULTS.md` section 4, `logs/w6/C_RESULTS.md` section 3 |
| Branch/tag state | `w8-carry` = the W8-B commit `d682a62` (the carry metric + the default-off guard, measured-not-adopted) + the W8-B.1 gate-fix docs (`e7d1ed3`), on top of `78e822e` (W8-A.1), which carries the W8-A/plan chain (`c973020`, `38d4699`, `cb39de8`, `459b00f`); `w8-confirm` sits at `78e822e`; `main` and `origin/main` are at `e7d1ed3` (the W8-A + P-PLAN + W8-B chain is pushed); **`w8-residuals` = the R2 commit + the R2.1 gate fixes on top of `e7d1ed3` (tag `v0.8b`): the WS-2 outcomes + the two default-off direct-path knobs; `w8-speed` = the R3 commit from `fd273fb` (R2.1): the WS-3 outcomes + the default-off L2/L3 two-line knobs, local**; tags `v0.6-w6` (`9f91c75`), `v0.7-w7a/b/c`, `v0.8` (`78e822e`), `v0.8b` (`e7d1ed3`) | `git log` / `git rev-parse`, `WORKLOG.md` "W8-A" / "W8-B" / "P-PLAN" / "R2" / "R2.1" / "R3", `logs/w8/B_RESULTS.md`, `logs/w8/R2_RESULTS.md`, `logs/w8/R3_RESULTS.md` |

Open thread carried from the record: the two-line **store -> single-arm direct
transfer** question (does a two-line recollection transfer to the direct
interface?) is tested only weakly - W8-A's null cannot distinguish "no lever"
from "no transfer" (`logs/w8/A_RESULTS.md` section 4; `logs/w7/C_RESULTS.md`
section 5.2).

---

## 2. The backlog, grouped into workstreams

Each item: **goal / evidence / dependency / budget / success criterion**.
Budgets are Tier A wall estimates from the measured units in section 3.2
(scripted 10-attempt run ~5 min, 20-attempt battery ~10 min, policy 15-episode
run ~7 min, acceptance ~5 min sim + offline checks, single-shard collection
~1.3 min/episode).

### WS-1 - W8-B (R1, done 2026-10-13): the carry mechanism

| | |
| --- | --- |
| **Goal** | a carry-phase **grip-margin metric** (payload-in-hand relative motion / force / margin through lift-carry-place, from the existing traces; a new `[carry]` diag line only if the traces cannot separate the classes), the **left carry-escape mechanism** run on that metric, and **one bounded default-off lever** (grip margin / carry profile) measured against it |
| **Evidence** | W8-A section 4: 89-91 % of failures are carried-not-placed on both arms, close-start 2.8-4.0 mm, the loss happens **after** the close; W7-C.1: the `[acq]` close-phase `Fmax` does **not** separate successes from carry losses (5.47 N vs 5.96 N) - the metric must cover the carry window, not the close; W8-A section 4's crush/no-slip close is a co-occurrence, not a failure signature: the `[acq]` `Fmax` >= 24 N + `freeze=none` close carries on 4 successes (A r1e12/r1e13/r5e10, B r3e5) as well as the 4 strawberry failures, so W8-B must find the separator in the carry window; W7-C section 7 (also W7-B section 4 item 3): the scripted two-line's left failures are the same class (a scripted-side grip fix would move both lines) |
| **Dependency** | W8-A done (the class population is named); the metric before the lever (W7-C.1 lesson); one `tasks.py` lane |
| **Budget** | 1 mechanism trace run + analysis (~1.5 h), 1-2 lever batteries (2 x 20-attempt ~20 min), acceptance (~10 min); offline readouts are free |
| **Success criterion** | the metric **separates** success vs carry-loss classes with a gap (or the mechanism is named and the metric is discarded); the lever converts carry losses on the **paired class counts** (not a rate delta) with zero per-arm regressions; no-harm: single arm 9/10 + `fingerprint: matches`, two-line gated by `scripts/190_twoline_gate.sh` |

**Outcome (R1, 2026-10-13, `logs/w8/B_RESULTS.md` + WORKLOG "W8-B"):** the
metric half is **met** - the frame-free `clean_slip` separates the clean
leg-outs (**0.02-1.43 mm**, median 0.04, n=33) from the carry escapes
(**17.9-957 mm**, median 278, n=31) with **no overlap** (the 2 mm trigger is
~50x the clean median and ~9x below the smallest escape) - and the mechanism
is named (a **loaded slide**: force at its carry level at onset, median
4.90 N; single-sided contact; the pads feed the relative motion; the jaws pry
toward the 98-99 mm limit in 17/31 escapes; contact loss 2-132 ticks after
the 2 mm crossing, median 25). The lever half is **negative at adoption
strength**: `FRUIT_CARRY_GUARD` (default off, direct-scoped) moved the paired
carried class 5 B-only / 1 A-only, carried-not-placed 50 -> 42 and the rate
22/75 -> 28/75, but reads sign **p = 0.1094** (> 0.05) with **+5.4 % cycle**,
so per the pre-registered rule it is **not adopted** and the R1 lever slot is
**closed by that negative**, with the named residuals (the place-leg scope;
the untuned hold/derate cost; the tail-escape class). No-harm: the acceptance
`logs/w8/60_accept_w8b.log` reads **9/10 + motion gate PASS +
`fingerprint: matches`**, its 385/385 `[fruit]` lines byte-identical to the
W7-A acceptance (`logs/w7/50_accept_w7a.log`); the frozen-tree two-line
re-record (`logs/w8/70_w8b1_twoline.log`, `SEED=5`, 10 attempts) is
**bit-identical to the W7-A dense records** (442/442 `[fruit]` lines vs
`logs/w7/10_dense_twoline_1.log` / `11`) and **190 PASS** (7/10,
9.1 s/attempt, 4.60 placed/min). The legacy
`[motion] carry slip_max` must not be quoted for the OpenArm hand
(frame-contaminated; use `clean_slip` - `logs/w8/B_RESULTS.md` section 1 and
README's grip-quality paragraph).

### WS-2 - W8-C: the residuals

| item | goal | evidence | dependency | budget | success criterion |
| --- | --- | --- | --- | --- | --- |
| **2.1 C coverage of the patch store** | decide the grade-C story for the two-line interface: a C top-up collection **or** an explicit scoped note (grade C is never selected by pure routing - it rides to `despawn_y=-0.70` and is recycled) | `datasets/demos_v13p/index.json` = A 89 / B 84 / **C 0**; the base `datasets/demos_v11` carries **C 21**; `logs/w7/C_RESULTS.md` section 3 | none (decision); interacts with the owner C-semantics scope (WS-5.3) | a C-only shard ~40 min if chosen | the store or the note names which behaviour teaches C, or the record states C is out of scope for the two-line interface |
| **2.2 Patch canary label + floor** | give the patch canary a correct lane label (the "cross-lane station fruit placed on lane M" note is **not failure-specific**: it appears on 2 failures and 4 successes of 10; R2 correction) and its own floor **if** the patch scenario becomes a shipped gate | `logs/w7/C_RESULTS.md` sections 5.1 / 7 (patch canary 5/10, all failures grip-loss; the note count corrected inline in R2.1); `logs/w8/R2_RESULTS.md` section 2 | policy interface decision (WS-4.5) | 1 canary ~8 min + evaluator label fix (offline) | the label agrees with the primitive's placement on a recorded 10-episode canary, and an explicit floor is on the record (or the patch canary is retired as a gate) |
| **2.3 Reach-cliff flail (x ~ 0.39-0.42)** | name and fix the lateral reach cliff: the left joint sits at its limit while both `move_to` calls run to their caps (3.33 + 4.17 s); it is a **reach/pose or selection** problem, not a fire-time lever | `scripts/174_station_reach.py`; `logs/w7/B_RESULTS.md` sections 1.4 / 4 (fruit x ~ 0.39-0.42); `logs/w8/A_RESULTS.md` section 3 (left close-start `|y|` outliers 276.8 / 388.3 + 301.7 mm) | none (scripted-side) | 1 reach/selection probe (~1 h) + acceptance | zero catch-up timeouts with joint-limit margin ~0 on the pinned supply, or the selector refuses cliff candidates **without** starving (per-arm starved slots reported) |

**Outcome (R2, 2026-10-13, branch `w8-residuals`, `logs/w8/R2_RESULTS.md` +
WORKLOG "R2").** All three residuals are closed with measured verdicts.

* **2.1 C coverage: the scoped note (no top-up run).** A two-line rollout store
  cannot carry C (W3 pure routing never selects it); the direct interface
  presents C and measures it as its **best** grade (W8-A 22/51 = 43 %, W8-B
  22/48 = 46 %, confounded with the arm), and the C windows train from the
  single-arm base anchor `demos_v11` (C 21/50) that every recipe includes. The
  named top-up path (only for a future C-specific need or after the WS-5.3
  C-semantics decision) is a single-arm collection with
  `FRUIT_SUPPLY_GRADES=C:1`, merged as a named add-on - never into a two-line
  store. What zero rollout-C blocks: a C-specific fine-tune arm beyond the 21
  base episodes; nothing measured today.
* **2.2 patch canary label: a real event, not a harness bug.** The
  `cross-lane station fruit (index N) placed on lane M` note is emitted by the
  primitive at the moment it takes the station-presented fruit (patch pair /
  queue) onto the arm's own lane - a deliberate, recorded sort error. Recorded:
  `canary_pinned` 1/10, `canary_patch` **6/10** (the W7-C text's 5/10 /
  "three successes" is **corrected**), reproduction 4/10. Not failure-specific;
  the only limitation is the evaluator header naming the *selected* target. No
  control-path change; the named fix (print the result's own index/grade/lane,
  own floor) is deferred until/unless the patch scenario becomes a shipped
  gate (WS-4.5).
* **2.3 reach-cliff flail: the mechanism decomposes into three terms; two
  bounded default-off screens measured, neither adopted.** Offline 18 flail
  legs / 390 instrumented attempts (14 left / 4 right); the forced edge-band
  probe (15 episodes
  per run) reads: **P0** off 10/15 flails with 9/15 premoves at the 3.33 s cap;
  **P1** `FRUIT_POLICY_TRIGGER_X_MAX=0.39` 7 refusals recorded but 7/12
  attempts still flail (sub-cap fires + the **policy-gate bypass**: 4 of 7
  refusals attempted anyway, all 4 flailed, WS-4.6); **P2** shipped band,
  guard on: 15
  attempts, **0 refusals / 0 flails** (no starvation); **P3/P4**
  `FRUIT_DIRECT_RESEED=1`: flails 13/30 = 43 % pooled vs 67 %, premove cap
  0-1/run, median error 43 -> 21 mm - the reseed removes the
  premove/configuration term, the hover/reach-edge term (8 mm tolerance
  unattainable at x >~ 0.39) and the fast catch-up stall (28-181 mm residuals)
  remain. The
  roadmap's "zero catch-up timeouts" leg is **not** met by either lever alone;
  the selector leg is **not met at effect level**: the refusal accounting is
  delivered (7 refusals, 3 rides-past) and there is no shipped-band starvation,
  but 4 of the 7 refusals were attempted anyway through the policy-gate bypass
  (all 4 flailed) - the residual is the WS-4.6 item (+ WS-4.7). Named
  next screen: the combination + the hover tolerance / catch-up term, with a
  same-band control before any adoption. No-harm: acceptance **9/10 + motion
  gate PASS + `fingerprint: matches`**, 385/385 `[fruit]` lines byte-identical
  to `logs/w8/60_accept_w8b.log`; final pins `tasks.py` `d83167b1`,
  `rl_env.py` `c57db999`, `trigger.py` `763ad89e` (the probe manifests pin the
  pre-reseed tree as well).

### WS-3 - the frontier speed levers (scripted, one `tasks.py` lane)

| item | goal | evidence | dependency | budget | success criterion |
| --- | --- | --- | --- | --- | --- |
| **3.1 L2 adaptive lead** | replace the fixed setup floor with a **measured per-arm EWMA** lead, so a nearer fruit is selectable; the prerequisite is the **floor override** - `_dynamic_select_floor` takes `max(1.5, min_lead)`, so the shipped `FRUIT_BIARM_SELECT_LEAD_S=1.4` is **inert** (SPEC 7.3) | wait-to-handover inputs measured: left **2.93 s mean / p90 3.7**, right **3.39 / 4.4** (`logs/w6/C_RESULTS.md` section 4); the under-lead catch-miss failure mode is the v9 1/10 selection-floor case | W8-B/C for a frozen tree (one lane owns `tasks.py`); L1 prefetch is a measured null hook (`FRUIT_BIARM_PREFETCH`, re-fire gate: reservations > 0 AND a consumption) | 2 batteries + 1 trace (~1 h sim) | hover wait / pooled interval move **with the catch taxonomy unchanged** (zero new failure reasons); default off until gated; no-harm |
| **3.2 L3 hot-arm residency** | when a target is reserved, hold the arm at the **station-side pre-pose** instead of a full park + re-pre-pose; park only on starvation or the clearance gate | `logs/w6/FRONTIER_THROUGHPUT.md` section 3.3; pre-pose + hover **move** is 7 % of the interval (`logs/w6/BASELINE.md` section 3); the dense clearance sub-30 mm class is the **carry-past** (the carrying hand passing the other arm's descent/pre-pose; `logs/w7/A_RESULTS.md` section 4), and W2 showed park redesigns cost rate | 3.1 (reservation semantics); the clearance convention owner decision (WS-5.2) | 2 batteries + clearance trace (~1 h) | interval gain with the **per-config clearance traced and reported** (min, % < 30 mm); no contact failure possible in this build, but the convention is the owner's |
| **3.3 L4 place/return re-timing** | **conditional**: only if the battery's decomposition shows the return block matters (the R3 plan's condition; the arms already idle 18-24 % waiting for fruit). Overlap the return with the next feed (drop the 30-tick gap when a target is reserved; start the return from the release pose) | place alone 5.3-5.7 s per interval, place+release+return 29-34 % (`logs/w6/BASELINE.md` section 3); W1/W2 measured place/carry re-timing negatives - do not touch the descent or the close | 3.1/3.2's measured intervals | 1-2 batteries (~20 min) | interval moves without touching descent/close; single-arm fingerprint re-checked |
| **3.4 Belt-speed / patch-density screen** | find **where arrivals stop limiting**: the 20-attempt battery at 0.12/0.15/0.18 m/s and at patch densities, with per-leg catch metrics | `logs/w6/FRONTIER_THROUGHPUT.md` section 3.4 / [T8] (dispatching raised max belt speed +11.9 %); the AGENTS ladder records 0.15 as a wash, 0.18 not run | scenario-level (S*), no code change; each config = one branch | 3-6 batteries (~1-1.5 h) | the arrival-limited vs servo-limited boundary is named (per-leg metrics + branch), not a rate delta; every pre-patch supply stays byte-reproducible |

**Outcome (R3, 2026-10-13, branch `w8-speed`, `logs/w8/R3_RESULTS.md` +
WORKLOG "R3").** All four rows are closed; **no lever is adopted** (every knob
default off, two-line only; the shipped single-arm default is byte-unchanged).

* **3.1 L2 adaptive lead: the plumbing delivered, the adaptive form measurably
  inert, the tight form negative.** `_dynamic_select_floor` now takes a
  `lead_override_s` that *replaces* the shipped 1.5 s setup (`SPEC` 7.3's
  inert `FRUIT_BIARM_SELECT_LEAD_S` is plumbed), and
  `FRUIT_BIARM_SELECT_LEAD_ADAPT=1` feeds it a per-arm EWMA of the measured
  selection -> wait-loop-entry setup, clamped to 0.9/1.5 s. Measured on the
  patch battery: the shipped 1.5 s **is** the measured setup (left 1.467 s,
  right 1.516 s), 0/20 selections are floor-bound (38-316 mm of slack), and
  the adaptive config is **bit-identical to the control (821/821 physics
  lines)**. The explicit tight probe (`FRUIT_BIARM_SELECT_LEAD_S=1.0`, floor
  0.339 m) **binds** (1/10 selections per arm) and moves the branch (first
  divergence the left slot-10 peach-vs-lychee) with **zero new failure
  reasons** (the v9 under-lead class does not appear) - but the pooled
  interval/rate on that branch are worse (8/20, window 2.59 vs 3.63, pooled
  23.16 vs 16.53 s) with the damage in the shared placed-False class (11 vs
  7). The measured lever capacity is one arm's wait (-0.31 s) on >=1/10
  selections, not the fleet interval; the plumbing stays for any future
  scenario-calibrated lead.
* **3.2 L3 hot-arm residency: measured, not adopted.** `FRUIT_BIARM_HOT_ARM=1`
  defers the park to after the attempt-boundary feed and replaces it with a
  station-side hold (lift + a measured-convergence blend, 140+80 ticks) when a
  target is imminent and the other arm grips nothing; the next attempt skips
  its pre-pose blend behind a 0.08 rad guard (the hover move stays - it is the
  calibrated descent entry). Measured: **4 holds / 18 non-final turns**
  (starvation 7, clearance 7, budget 2), only 2 survive to the next attempt,
  1 of 4 jammed (1.55 rad, recovered by the park); the hold costs the same
  order as the park return it replaces (2.4/2.9 s), the pooled attempt span is
  **identical** (15.08 s - the interval is arrival-bound), the window rate is
  0.22 placed/min lower (3.41 vs 3.63), the idle/starvation rise, and the
  pooled interval mean/p90 worsen (+1.09/+13.70 s; p50 -3.10 s). Clearance
  per config: min **1.9 -> 4.7 mm**, < 30 mm **4.7 -> 5.6 %** (the W2/W3
  carry-past class; no contact possible in this build). The W2 lesson (park
  redesigns cost rate) re-measured.
* **3.3 L4 place/return re-timing: not run - the condition is not met.** The
  control's decomposition has return 0.59/0.64 s per attempt (~4 %), not a
  dominant block, and the interval is arrival-bound (the arms already idle
  18 %/24 % waiting for fruit), so re-timing it would only re-absorb into
  idle; W1/W2's place/carry re-timing negatives still stand, and the
  descent/close are untouched by R3.
* **3.4 belt-speed screen: the arrival-limited boundary is 0.15-0.18 m/s.**
  One branch per point on the patch battery: 0.12 -> 0.15 -> 0.18 m/s reads
  window **3.63 -> 4.69 -> 3.82** placed/min, pooled interval **16.53 ->
  12.80 -> 15.71 s**, with the catch leg in-band/stable across the three
  speeds (20 descent legs/run, `|v|max` 0.106-0.116 m/s, `end` 8.2-12.2 mm,
  zero catch-miss notes; not byte-identical across speeds - 0/20
  `approach(cartesian)` lines shared) and the
  arrival structure speeding up monotonically (descent 3.19 -> 2.40 -> 1.88 s;
  attempt span 15.08 -> 14.33 -> 13.73 s). At 0.18 the starved-slot idle
  explodes (left 115 vs 19; idle 39 %/32 %) and the rate falls back - the
  binding term has moved from catch/arrivals to lane/schedule starvation,
  made structural by the speed-dependent fixed-time floor window
  (`v*1.5` = 0.27 m at 0.18, usable band 0.45 -> 0.27 m). 0.15 is not the old
  ladder's wash on the patch sheet; the named fix is a scenario-calibrated
  floor per speed, not the adaptive EWMA (section 1.4).

### WS-4 - the policy

| item | goal | evidence | dependency | budget | success criterion |
| --- | --- | --- | --- | --- | --- |
| **4.1 ACQ shipping decision (the ACQ=0 mirror)** | before any ACQ=1 direct interface ships, run the **ACQ=0 vs ACQ=1 mirror at N=5** on the patch scenario; the W7-C N=3 read (off 36 % vs on 27 %, p = 0.875, different branches) is underpowered and points the wrong way, and W8-A ran **both arms ACQ=1** so the knob itself is untested | `logs/w7/C_RESULTS.md` section 1; `logs/w8/run_w8a.sh` (`FRUIT_POLICY_TRIGGER_ACQ=1` on both arms) | owner interface decision (4.5); the W8-A harness (`scripts/112_rl_ab.sh` + `logs/w8/run_w8a.sh`) | ~70 min Tier A | p <= 0.05 with the strawberry bucket non-inferior (the P4 criteria), or the knob stays default off and every direct report states the pin |
| **4.2 N=5 confirmation protocol for any future lever** | one template for every policy lever: N=5 runs/arm x 15 episodes, interleaved, seeds [77,101,202,303,404], sampler seed 11, **both arms inside one instrumented batch**, manifests pinning `tasks.py` / `rl_env.py` / `trigger.py`, and the P4 rule (paired sign p <= 0.05 + strawberry non-inferior, or cycle >= 5 % lower with success non-inferior; no new failure reason) | W8-A is the calibration: the W7-C 3-0 carried pairing was **noise** at N=5 (0-2), p = 1.0000; one run = one sample (rendered frames) | none | ~70 min per lever | the pre-registered rule is applied and negatives are published; a directional N=3 read is never promoted to a rate |
| **4.3 Recollection improvements (the carry class, anchor discipline)** | if recollection resumes: target the **carry/lift windows** (the W8-B metric now names them per attempt - `[carry]` onset row/force/contact/direction, `logs/w8/B_RESULTS.md` - so the target no longer has to be guessed), keep the **single-arm base anchor** `demos_v11` distinct (two-line stores are rollout stores, never the base), and re-test with the N=5 shape | W8-B: the carry window is measurable per attempt and the metric separates, but its one scripted lever screen is negative at adoption strength - W8-A's "not another behaviour-cloning pass" still governs a further pass; W8-A section 4: another behaviour-cloning pass is **not** the lever for the carry class at this measurement strength (second null for `moe_v13p`); W7-C section 4/5.2 anchor discipline; W3's dense direct eval `moe_v13s` 15.6 % | WS-1's metric (**delivered**: `clean_slip` + `logs/w8/B_metric.py`); the owner interface decision | collection **~3 h 41 m as run** (the W7-C chain: 173 episodes over 9 shard-runs, wedges + skips included; ~1.3 min/episode per clean single shard) + fine-tune ~22 min + N=5 A/B ~70 min | the carry metric moves **and** the paired class/rate test confirms at N=5; or the negative is published and the line stops |
| **4.4 W3-supply hybrid canary** | close the open canary on the W3 dense/wave supply (or diagnose the handoff's station wait first - ~15-20 min/episode there) | `logs/w3/HANDOFF.md`; the W6-E scope names it | none | a long window (~3 h) or 1 diagnosis run | a PASS/FAIL canary on the W3 supply is on the record, or the scenario is retired with the reason |
| **4.5 Interface decision** | decide whether the **shipped policy interface** stays the hybrid station handoff (inert by construction: zero actions scored 10/10) or the **causal direct loop** becomes the gate of record | P4 design review (the handoff teleports the fruit to the policy's jaw); `logs/w8/A_RESULTS.md` (the direct loop is the measurement); never compare direct vs hybrid | owner | offline | one interface is named the gate of record and the other scoped mechanism-only; no mixed rate claim |
| **4.6 The policy-gate fire path** | name and close the class that bypasses the trigger entirely: the `finger < 0.030` and jaw-fruit `\|xy\| < 0.06` gate fires on **4/18 of the W4 left attempts** (W7-B section 4 item 3b); a future lever could route it through the same acquisition window the ACQ knob fixes | `logs/w7/B_RESULTS.md` section 4 item 3(b); W4 left 4/18 (3 no-contact + 1 carried) | owner interface decision (4.5); interacts with 4.1 | offline + the 4.2 N=5 shape if the gate path changes | the gate class is named and either folded into the interface decision or fixed with zero regressions |
| **4.7 Reach-cliff combination screen + the hover/catch-up fix** | the R2 named next screen: run the default-off pair **together** (`FRUIT_DIRECT_RESEED=1` + `FRUIT_POLICY_TRIGGER_X_MAX=0.39`) on the forced edge band at N per arm against a same-band control, and fold in a fix for the residual terms - the hover's 8 mm tolerance (the 500-step `move_to` cap) and the fast catch-up stall (28-181 mm residuals) | `logs/w8/R2_RESULTS.md` section 3 (three terms; P0-P4 are N=1x15 mechanism reads; neither knob adopted); the R2.1 re-derivation `R2_flail_analysis.txt` / `R2_probe_report.txt` | WS-4.5 interface decision (the bypass is the WS-4.6 policy-gate item); one `tasks.py` lane; the R2 knobs stay default-off until gated | 2-4 probe batteries (~15 min each) + 1 acceptance | the flail class is zeroed on the stress band or the residual is named with the joint-limit margin; a same-band control confirms it; no-harm: acceptance 9/10 + `fingerprint: matches`, new envs default off |

### WS-5 - the owner decisions

| item | the question | evidence | what it blocks |
| --- | --- | --- | --- |
| **5.1 The flip bar (1.25x stands)** | the same-branch W6-B ratio is **1.24x** (just under the bar); the with-park branch reads **3.63 / 2.17 = 1.67x** cross-branch - does the owner accept the cross-branch reference, ask for a same-branch single-arm re-baseline in the park branch (~10 min), or keep the recommendation **no**? | `logs/w6/BASELINE.md` (1.24x window), `logs/w6/C_RESULTS.md` section 2 (timing-only +10 %, residual x1.22), `logs/w7/A_RESULTS.md` (park battery 3.63) | the two-line default (`FRUIT_BIARM=1` meaning); every future two-line rate claim |
| **5.2 The clearance convention** | the F2 bar is **45 mm / zero-under-30**; measured: dense **2.59 mm / 8.6 % < 30 mm**, patch **1.9 mm / 4.7 %**; no contact is possible in this build and no attempt failed by contact - gate or per-config report? | `logs/w7/A_RESULTS.md` section 4, `logs/w6/C_RESULTS.md` section 3, `logs/w2/RESULT.md` | the two-line default flip; any two-line clearance gate; L3's risk statement |
| **5.3 The C-semantics scope** | pure per-arm routing (left A, right B, **C never selected**) is two-line-only today; the single-arm selector still picks C (byte-unchanged). Does C-pass become global, and how is C accounted (recycled at the belt end)? | owner decision 2026-10-10 (W3); `datasets/demos_v13p` zero C vs `demos_v11` C 21 | any global routing change; WS-2.1's C-coverage decision |

### WS-6 - infrastructure

| item | goal | evidence | dependency | budget | success criterion |
| --- | --- | --- | --- | --- | --- |
| **6.1 Renderer-wedge mitigation** | stabilise long collections: the blocking `RenderingManager.render()` under the bimanual bridge wedged **9 times across 9 shard-runs** in W7-C; the collector's **soft per-episode watchdog** skipped/retried 14 attempts, the hard progress window exits with a stack dump, and `gate_open=0.0 s` / zero `indexed:` held as the **enforced** invariant | `logs/w7/C_RESULTS.md` section 3; the single-shard probe collected 32 episodes cleanly | the collector (two-line mode) | sequential single-shard collection ~40 min / 30 episodes | a collection shard completes a full batch without a wedge, or the wedge rate + recovery is named and the single-shard sequential shape is the default |
| **6.2 Tier B parallel harness (X1) + the tier policy** | keep the X1 machinery as the execution rule: `scripts/180_claim_slot.sh` (flock slots, stale recovery, `--status`), `181` selftest, `182` comparator, `183` probe, `184` equivalence batch; **Tier A never concurrent**, Tier B <= 3 only with a re-proven equivalence and a unique namespace; **two X1 items stay pending**: the force-servo N=4 mechanism test (`FRUIT_DYNAMIC_FORCE_SERVO=0`) and the completed 10-attempt 3-concurrent equivalence batch (stopped by the co-lane W3 collector stall) | X1 result: **16/17 single-attempt runs bit-identical over N = 1-4**, one N=4 divergence (the force servo; `logs/x1/REPORT.md` section 1), ceiling N* = 3; 3313 MiB per scripted instance; the equivalence batch stays partial (`logs/x1/REPORT.md` section 5) | none | offline + the equivalence run per batch | every Tier B batch re-proves equivalence (bit-identical `[fruit]` lines or the divergence reported with its mechanism); no Tier A job runs concurrently; the two pending items close (the force-servo probe names the N=4 divergence's actuator, and the 3-concurrent batch completes == the sequential line) |
| **6.3 Ops self-check (PP-P1) + anti-stall rules** | **delivered** `cb39de8`; **hardened by P1.1** (true resume semantics, guarded group-kill, GPU-idle gate, `[wrap]` suppression, path-anchored sim matching): `scripts/191_ops_selfcheck.sh` (the P-PLAN PP-P1 deliverable) + `docs/OPS.md` - sims + log growth, lanes, claims, newest artifact per area, git/branch/tag state, GPU, pending-gate items; verdicts **OK/STALLED/ACTION** with the recommended recovery, a `--watch` loop, and a synthetic-stall test | P-PLAN (`.slim/deepwork/sorting-pipeline-v3.md`); the observed stall classes (a)-(e) in section 4 below | done (offline; ran parallel with W8-A's wrap) | offline | the synthetic-stall test **PASS** (`logs/ops/11_selftest.txt`; now a `scripts/selfcheck.sh` leg) and the tool ran live on the real state: one-shot `logs/ops/10_live.txt`, the `OPS_CHAIN_S=60` real `ACTION [wrap]` (`12_stalled_chain.txt`), and a live Tier A sim with its claim wrapper (`13_live_capture.txt`); section 4's playbook is its specification |

### WS-7 - longer term / frontier (enter only with the owner)

| item | goal | evidence / menu |
| --- | --- | --- |
| **7.1 Sim-to-real directions** | domain randomization + CACTI-style scene augmentation before any real-cell transfer; the cell is deterministic and measured, so transfer starts from the dynamic-line calibration | `logs/w6/FRONTIER_THROUGHPUT.md` section 1.3 [T29-T31]; the cell's scenario pins |
| **7.2 RL / DAgger lanes** | one lane continues the P4 line on the **fixed action semantics** (v8; `moe_v9` direct 53 % before the v13 recollections): DAgger in the direct env with the ACQ interface pinned, then RWR with AWR clipping or the trigger-margin fix - under the 4.2 N=5 protocol | WORKLOG "P4"; `docs/research_dynamic_grasp_methods.md` section 4; W7-B section 4 item 4 (the knob shrinks the policy-controlled window - pin the interface) |
| **7.3 Learned catch** | keep closed unless the scripted catch becomes the ceiling; the frontier menu is MPC interception / learned catch / vision+RL conveyor picking | `logs/w5/FRONTIER.md` **row 8** (learned catch / MPC interception; [S2][S5-S7]); **row 9 is the space-separation rework [S8][S13]**, not the learned catch; the scripted catch is ~9/10 and not the blocker |
| **7.4 Grip-margin methods** | the WS-1 metric first (**satisfied** 2026-10-13: `clean_slip` separates clean vs escape with no overlap, `logs/w8/B_RESULTS.md`), then the W5 survey **rows 2-3** - row 2's form (slip guard with derate + bounded re-seat) is measured **negative at adoption strength in R1** (`FRUIT_CARRY_GUARD`), row 3 (place-entry contact maintenance) is untested - and the tactile fast branch (RDP/TDP/FARM) if the carry class survives a scripted lever; **row 1 is the ACQ-knob line** (shipped default-off, WS-4.1); **rows 5 (TPG-lite) and 10 (soft fingers) stay closed/stretch** (`logs/w5/FRONTIER.md` section 5), not budgeted | `logs/w5/FRONTIER.md` sections (c) and the ranked table; W7-C.1 (the close-phase force does not separate - measure the carry window); W8-B (the metric delivered; the R1 guard screen negative) |

**Closure rule.** An item closes with a log pointer in `logs/` + a WORKLOG entry;
a default change needs its own Oracle gate and the byte-unchanged single-arm
acceptance.

---

## 3. The phased sequence, the gates, and the resource budget

### 3.1 Phases (R0-R6; the P-PLAN deliverables are `PP-P1`/`PP-P2`/`PP-P3`)

| # | phase | scope | depends on | gate | Oracle budget |
| --- | --- | --- | --- | --- | --- |
| **R0 (done)** | **PP-P1 + PP-P2 landed; W8-A reviewed and gated** | PP-P1 ops tool delivered (`cb39de8`: `scripts/191_ops_selfcheck.sh` + `docs/OPS.md`; `--selftest` PASS + live OK) + PP-P2 this roadmap (offline, gate-fixed as P2.1); W8-A wrap: acceptance 9/10 + fingerprint, WORKLOG entry + commit landed (`c973020`); the W8-A.1 gate fixes landed (`78e822e`) | - | **PP-P3 validation (folded)**: real-state checks recorded (`logs/ops/`), AGENTS/README wired (P2.1); the W8-A + P-PLAN chain is pushed (`main`/`origin/main` at `78e822e`); the W8-B + W8-B.1 commits are local | 0-1 |
| **R1 (done 2026-10-13)** | **W8-B the carry mechanism** (WS-1) | metric -> mechanism -> one lever; full evidence `logs/w8/B_RESULTS.md` (+ WORKLOG "W8-B"/"W8-B.1") | R0's W8-A wrap; one `tasks.py` lane (guard default-off; `tasks.py` `a3b82a11`) | **metric separates PASS** (0.02-1.43 vs 17.9-957 mm, no overlap) + mechanism named; lever **not adopted** (p = 0.1094, +5.4 % cycle) -> slot closed with the named residuals; no-harm **PASS** (single arm 9/10 + `fingerprint: matches` + the 385/385 identity; two-line `190` PASS + 442/442 identical to the W7-A dense record) | 1 + 2 re-reviews (used) |
| **R2 (done 2026-10-13; gate-fixed as R2.1)** | **W8-C residuals + integration** (WS-2) | WS-2.1-2.3; docs + tag; R2.1 re-derives the three-term numbers from `R2_flail_analysis.txt` / `R2_probe_report.txt`, downgrades the selector-leg verdict and slots WS-4.7 | R1's metric (**delivered**: `clean_slip` + `logs/w8/B_metric.py`); owner C/clearance for the notes | **folded** (no shipped scenario or default changed; both new knobs default off, direct-path only) - the outcome block under WS-2 carries the three verdicts + the acceptance | 0-1 |
| **R3 (done 2026-10-13; local)** | **the speed levers** | WS-3.1 -> 3.2 -> 3.3 (conditional); 3.4 interleaved as its own Tier A batch | R1/R2 for the frozen tree; one `tasks.py` lane | **folded** (no shipped default changed; both levers default off, two-line only) - the outcome block under WS-3 carries the four verdicts + the no-harm; every lever: mechanism + interval movement + no-harm, negatives published | 1 + 2 per lever (used) |
| **R4** | **the policy** | WS-4.2 protocol; 4.1 mirror (if shipping); 4.3 recollection (if the WS-1 metric names a target); 4.4 canary; 4.6 the gate fire path; 4.7 the R2 combination screen | WS-1's metric; the owner interface decision (4.1/4.5) | per arm: the N=5 P4 rule; canary + acceptance | 1 + 2 |
| **R5** | **owner decisions + integration** | WS-5.1-5.3; the flip question; docs (`AGENTS.md`, `README.md`, the Chinese docs) + merge + version tag | R1-R4's measured numbers | a panel review (folded if no default changes) | 0-1 |
| **R6** | **longer term / frontier** | WS-7 lanes | owner go | per lane | - |

Gate order is strict where the tree is shared (R1 -> R3 -> R4: one `tasks.py`
lane at a time); R2's offline items and 6.3 can run beside a Tier A sim. W8-A
already discharged the "is `moe_v13p` better?" question (no), so R4 starts from
`moe_v12` + the ACQ pin, not from a new checkpoint recalibration.

**PP-P3 (validation + integration) remains the P-PLAN tail**: the real-state
checks are recorded (the idle one-shot `logs/ops/10_live.txt`, the
`OPS_CHAIN_S=60` real `ACTION [wrap]` `logs/ops/12_stalled_chain.txt`, and the
live Tier A sim capture `logs/ops/13_live_capture.txt`), and the AGENTS/README
pointers are wired in this P2.1 docs commit; what remains is the **push** of the
W8-B + W8-B.1 commits on `w8-carry` (the W8-A + P-PLAN chain is already pushed:
`main`/`origin/main` = `78e822e`). PP-P1 landed `cb39de8` (hardened by P1.1);
this document is PP-P2 (state-updated by W8-B.1).

### 3.2 The resource budget (measured units)

| unit | measured wall time | evidence |
| --- | --- | --- |
| Tier A scripted 10-attempt dense run | **4.5-5 min** (claim included) | `logs/w7/00_driver.log` (08:39:37 -> 08:44:15; lines 13-15) |
| Tier A 20-attempt two-line patch battery | **9-11 min** | `logs/w7/00_driver.log` (08:44:15 -> 08:53:08 and 08:53:08 -> 09:03:26; lines 18-26) |
| Tier A single-arm 20-attempt run | **~9 min** | `logs/w6/00_battery_driver.log` |
| Worker-cadence supply probe (120 s) | ~1.5 min | `logs/w6/00_battery_driver.log` |
| Acceptance (10 attempts + gate + fingerprint) | **~5 min sim + the offline gate/fingerprint checks** | `logs/w7/00_driver.log` (09:12:13 -> 09:17:49; lines 690-692), `scripts/accept.sh`, `logs/w8/A_RESULTS.md` section 5 |
| Policy 15-episode direct run | **~7 min** | `logs/w8/A_RESULTS.md` section 1 (10 runs in ~70 min) |
| Policy A/B N=5 x 15 x 2 arms | **~70 min** | `logs/w8/A_RESULTS.md` section 1 |
| Collection, single shard | **~1.3 min/episode** (32 episodes ~41 min, `C_probe1`; 30 episodes ~41 min, `C_final`; the W3 single-arm dense sheet: 158 in 2 h 06) | `logs/w7/C_probe1_driver.log` (14:54:47 -> 15:35:36), `logs/w7/C_final_driver.log` (16:02:46 -> 16:43:35), `logs/w3/HANDOFF.md` |
| Collection, W7-C store (173 episodes, 9 shard-runs, 9 wedges) | **3 h 41 m** shard-runs | `logs/w7/C_collect_driver.log` (13:02:20 start; first wedge 13:52) + `logs/w7/C_final_driver.log` (-> 16:43:49) |
| Fine-tune `moe_v13p` (6 epochs, 41,662 windows) | **21.5 min** (215 s/epoch) | `logs/w7/C_chain_driver.log` (16:46 -> 17:09) |
| Full W7-C chain (collection -> merge -> train -> canaries -> direct A/B) | **~5 h 11 m** | 13:02:20 -> 18:13:08: `logs/w7/C_collect_driver.log` + `logs/w7/C_final_driver.log` (collection), `logs/w7/C_chain_driver.log` (16:45:52 -> 18:13:08) |
| Disk per store | **8.2 GB / 173 episodes**; the machine cap is ~125 GB (do not stack anchor stores) | `logs/w7/C_RESULTS.md` section 4 |
| GPU | **~3.3 GB per scripted instance**, N* = 3; training ~5 GB beside at most one sim | X1 (`scripts/183_concurrency_probe.sh`) |

Planning rule of thumb: **one 20-attempt battery ≈ 10 min of Tier A sim; one
policy A/B ≈ 70 min; one recollection+fine-tune+eval chain ≈ one long day.**
Every number quoted in a document is Tier A solo.

---

## 4. The self-check cadence and the anti-stall playbook

**Tool.** `scripts/191_ops_selfcheck.sh` (PP-P1; **delivered** `cb39de8`;
**hardened by P1.1**; offline) - reports the running
sims and their log growth, the lanes (claim wrappers/drivers alive), the
claims, the newest artifact per area, the git/branch/tag state, the GPU, and
the pending-gate items; verdicts
**OK / STALLED-SIM / STALLED-CHAIN / ACTION** with the recommended recovery;
`--watch` for a loop; `--selftest` for the offline synthetic-stall test.
**Ship thresholds (defaults): `OPS_STALL_S=300 s` (sim log frozen) and
`OPS_CHAIN_S=600 s` (chain log stale); a frozen sim escalates to `ACTION` only
with corroboration - a wedge marker, zero growth across the state window, or an
idle GPU with the freeze age >= 2x `OPS_STALL_S`.**
`docs/OPS.md` is the full contract (thresholds, modes, recovery commands); the
playbook below is its specification. **Cadence: at the start and end of
every work block, and every 30-60 min while a simulator phase is active** (the
owner rule: do not sit on a stall and burn time/resources). Record every
detected stall + recovery in `WORKLOG.md`.

| # | stall class (observed) | detection / threshold | recovery |
| --- | --- | --- | --- |
| a | lane stuck on an **unanswerable permission** (the plugin transport cannot reply on this host; the deepwork P2 lane's `/tmp` loop and the parked fix-3 are the precedents) | lane state `waiting_input` > 10 min, and/or a pending permission ask in the tool's `permissions` section | respawn with a corrected prompt: no `/tmp`, no external directories, all artifacts under `logs/`; do not wait |
| b | **renderer wedge** (a claimed sim with no log growth; the blocking `RenderingManager.render()` under the bimanual bridge) | claimed sim + no log growth > `OPS_STALL_S` (300 s shipped); `ACTION` when corroborated (wedge marker, zero growth across the window, or GPU idle with the freeze age >= 600 s); the sim-clock floor (< 1 s per 60 s wall; the hard guard fired at 0.25-0.94 s per 600 s, `logs/w7/C_RESULTS.md` section 3) stays the physics-level fallback | the collector's soft per-episode watchdog skips/retries; the hard progress window exits with a stack dump; kill the session, then resume by **re-running the same wrapper invocation** (the wrappers do not retry; a re-run reclaims a slot via flock); a collector shard **restarts from zero** into a fresh dir (the store is the union of shard dirs) |
| c | **dead lane after a detached chain** (wrap never ran; W8-A died after `B_5` before the wrap) | completion marker (`fingerprint: matches` / `[claim_*] exit=0` / `[fruit] DONE`) with the chain log stale > `OPS_CHAIN_S` (600 s shipped) and the tree dirty; the tool downgrades it to a hint while a claim wrapper/driver is alive | resume from the recorded evidence: re-generate the offline readouts from the batch logs (W8-A's four reports were re-derived, no re-run), then append the WORKLOG entry and commit |
| d | **long-idle lane** | no new artifact and no message for > `OPS_CHAIN_S` (600 s shipped) with queued work | ping, then respawn with the next concrete step |
| e | **resource waste** (sim running with no consumer, GPU idle with queued work, stale claims) | stale claims (dead owner pid); an idle GPU with the sim's log frozen >= 2x `OPS_STALL_S` (GPU-idle alone is not corroboration); claim older than the run it covers; a sim whose log is not a consumed artifact (operator: GPU idle > 15 min with queued Tier A work) | stop the sim, release the claim (`180 --status`, stale recovery), start the queued Tier A job |

**Escalation to the owner** (do not loop): after **two failed recovery attempts**
for the same class, when a stall exceeds **60 min**, when a phase's gate has
failed twice with no new lever, or when the blocker is a decision - file it in
the register (section 5) and keep the pipeline busy with an independent Tier B/C
item meanwhile. Never parallelize a Tier A job to "make up" lost time; never
read a concurrent run as a quoted number.

---

## 5. The owner-decision register

| # | open item | evidence snapshot | what it blocks | recommendation / next request |
| --- | --- | --- | --- | --- |
| 1 | **Two-line default flip** (bar 1.25x stands; W7: not renegotiated) | same-branch W6-B **1.24x** (< bar); with-park cross-branch **3.63/2.17 = 1.67x**; all parked-lever numbers are on a different branch | the shipped default (`FRUIT_BIARM=1` meaning) and every future two-line rate claim | decide: accept the cross-branch reference, authorize a same-branch single-arm re-baseline (~10 min Tier A), or keep **no** |
| 2 | **Clearance convention** | F2 **45 mm / zero-under-30** vs measured dense **2.59 mm / 8.6 %** and patch **1.9 mm / 4.7 %**; no contact possible, no contact failure ever | the flip, any two-line gate, L3's risk statement | decide: per-config report (current) or re-impose a convention (which changes every two-line gate) |
| 3 | **C-semantics scope** | pure A/B/C-pass is two-line-only; the single arm picks C (byte-unchanged); `demos_v13p` has zero C, the base `demos_v11` carries C 21 | any global routing change; WS-2.1's C-coverage decision | decide: keep two-line-only or make C-pass global (with the accounting rule) |
| 4 | **ACQ shipping / direct-interface decision** | knob default **off**; the direct eval pins `=1`; no ACQ=0 mirror exists; the only knob A/B is W7-C N=3 36 % vs 27 %, p = 0.875 | any direct-interface shipping claim; whether 4.1's mirror is funded; **depends on row 5** - if the hybrid stays the gate of record the mirror is mechanism-only, if the direct loop becomes the gate it is mandatory (~70 min) | decide whether the ACQ=1 interface is a shipping candidate; if yes, authorize the N=5 mirror (~70 min) |
| 5 | **Policy interface of record** | the hybrid handoff is inert by construction (zero actions 10/10); the direct loop is the causal measurement; direct and hybrid are never comparable | which gate judges the policy; the canary/patch-label scope (WS-2.2) | decide: keep the hybrid canary as the gate and the direct loop as mechanism, or move the gate to the direct loop with its own floor |
| 6 | **W3-supply canary scope** | the dense-supply hybrid canary is open; the spaced supply measured ~15-20 min/episode on the handoff | any policy claim on the W3 dense supply | authorize the long window (~3 h) or a station-wait diagnosis first, or retire the scenario with a note |

Closed (not open): the park-gate lever default (W7-A, owner-approved); the
two-line grade semantics (W3 owner decision); branch-per-phase + tags (W7
owner decision); the L1 prefetch default (measured null; stays a default-off
hook).

---

*Every claim above carries its log/doc pointer; when a number changes, update
this roadmap, `AGENTS.md`/`README.md`, the Chinese docs
(`项目总结报告.md`, `决策与交付.md`) and the WORKLOG entry that justifies it.*
