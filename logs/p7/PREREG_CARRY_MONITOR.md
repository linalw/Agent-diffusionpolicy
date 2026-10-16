# P7-1 L1 pre-registration: the C-3 carry monitor (Phase 0 offline replay gate + Phase 1 battery)

Lane P7-1 L1, Tier C offline, 2026-10-16. Written **before** any fitting; the
corpora, the class denominators, the online feature set, the classifier family,
the cross-validation, the gate metric, the numeric FP cap and the live-phase
endpoints below are frozen by this file. Authority: `docs/papers/MECHANISMS.md`
item 1 (menu rank 1); `logs/p6/SYNTHESIS.md` section 2 item 1 + section 4 item
(1); the source lane's monitor card `logs/p6/B3b_reread.md` card 11 (M-0,
Sentinel-VLA #66) + `logs/p6/B1_reread.md` section 1 (JCAC/FabriVLA #1 as the
complementary signal) + `logs/p6/B3a_reread.md` (#47 EmbodiedSkills, loop
skeleton). No simulator run, no `src/` change, no commit; this lane delivers the
Phase-0 replay only, plus this pre-registration, plus `logs/p7/C3_REPLAY.md`.
The only new code is `scripts/203_c3_monitor_replay.py` (read-only offline
analysis).

**The structural claim being tested.** The closed W5 watcher died on the 0-2
tick in-window reaction (the onset is not preventable in time). This is a
different object: the escape is a **persistent state** (W8-B: contact loss
follows the 2 mm crossing by 2-132 ticks, median 25; the loaded slide keeps
evolving after the onset), and the action is a **scheduling decision at the
next leg boundary** - fast-skip the rest of a doomed attempt, or (B', only if B
passes) one bounded stationary re-seat. Nothing here reacts inside the window.

**The source lane's endpoint split (fixed by the P6-3 gate fix).** Sentinel's
M-0 card is explicit: *"The primary endpoint is the interval; the optional
bounded re-seat path is the only route to a success-rate effect and carries the
false-positive risk."* So:

* **B (fast-skip only)**: the interval route - the N=5 paired interval must
  **fall on the failed-attempt set**; plus lock-on and cycle <= +5 %, zero new
  reasons.
* **B' (one bounded re-seat, run only if B passes)**: the success-rate route -
  paired carried-class conversion at the 6-0 edge, p <= 0.05.

---

## 1. The arms and the scenario (Phase 1, executed in P7-2, not here)

Scenario: the W8-A/W8-B direct battery **verbatim** (`logs/w8/run_w8a.sh` /
`logs/w8/run_w8b.sh`): patch sheet
(`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`,
`FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25`), arrival trigger lead 0.9,
shipped lateral gate (0.16), dynamic never-stop handover,
`FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1` on both arms, direct
presentation, `RUNS=5 EPISODES=15`, seeds `77 101 202 303 404`, policy seed 11,
interleaved, one `154_claim_run.sh` claim (Tier A solo), via
`scripts/112_rl_ab.sh`. The tree carries the **R7-A bypass fix**; the pins are
recorded at battery time (this file's section 6 pins the writing-time tree).

| arm | checkpoint | env delta | readout |
| --- | --- | --- | --- |
| **A** | `moe_v13s` `61da390a...` | none (ACQ=1 + R7-A pinned) | the reference |
| **B** | same | `FRUIT_CARRY_MONITOR=1` (fast-skip only) | interval on the failed-attempt set |
| **B'** | same | `FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_RESEAT=1` | paired carried-class, only if B passes |

* `FRUIT_CARRY_DIAG=1` on **both** arms (the FP readout is symmetric).
* The monitor is **direct/hybrid-scoped**: it is consumed only inside the
  dynamic-capture carry loop when the direct handover owns the attempt (the
  same scope gate as `FRUIT_CARRY_GUARD`'s `direct_capture`); the scripted
  single arm and the two-line scheduler must never reach it (the no-harm bar).
* Monitor traffic is **trace/diag-only** until an adoption decision; the knob
  is default-off and byte-inert.
* Implementation lands in P7-2 in `src/fruit_sorting/tasks.py` next to
  `_carry_diag` (one tiny scorer + a skip flag; no new physics).

### 1.1 Endpoints (fixed now)

**B (fast-skip only):**
1. **Primary - the interval on the failed-attempt set.** The per-attempt span
   in simulated ticks (the `ticks=` field of the `[rl] episode ...` line; the
   `113_rl_report.py` cycle readout) over the attempts that carried a payload
   and failed in **A** (`grasped=True, placed=False` in A's paired run) must
   **fall in B** (pooled mean and median; the paired readout is the
   same-(run, episode) subset with both arms failed-carried, sign split
   reported). A rise (mean not lower) fails this endpoint.
2. **Lock-on.** The per-attempt setup latency read from the `[acq]` `setup`
   stamps (`premove+axis+hover+wait`, the W7-B report's aggregate; median over
   the battery) must not rise more than 5 % vs A.
3. **Cycle <= +5 %.** The pooled median per-attempt `ticks` over all episodes
   must not rise more than 5 % vs A (the W8-B cycle convention).
4. **Zero new failure reasons** (the `113_rl_report.py` reason parser's
   baseline reason set; a first-time reason string is a fail).

**B' (only if B passes):**
5. **Paired carried-class conversion.** Same fruit / same (run, episode index)
   pairing as the W8-A/B convention; the discordant carried-class pairs must
   read **6-0** at the lane's one-sided sign test (**p = 0.0156 <= 0.05**; the
   same test that read 5-1 = p = 0.1094 in W8-B). 5-1 does not pass.
6. Record the fast-skip timing (fire tick -> leg boundary) and the re-seat
   count per arm; a **re-seat rise without conversion is a kill** (the R11-A
   0 -> 10 signature).

### 1.2 Kill criteria (fixed now)

| # | kill | threshold |
| --- | --- | --- |
| K1 | Phase-0 replay gate | FAIL (section 3): macro-F1 < 0.86 or FP > 2/33 |
| K2 | monitor-triggered abort of a would-be placement | **> 2 per N=5 battery (75 attempts)** - an abort = a monitor fire on a leg whose live `[carry]` line reads `clean_slip_max <= 2.0 mm` and the attempt ends not-placed by the skip; the clean-leg denominator is reported |
| K3 | re-seat rise without conversion | B' only: re-seat count rises and endpoint 5 fails |
| K4 | any new failure reason | any string outside the baseline reason set |
| K5 | acceptance drift | the no-harm bar below fails (scripted acceptance or two-line drift; see section 4) |

### 1.3 What the replay gate means for the live battery

The live battery must also watch: the false-abort count (K2) against the SP
leg readouts from the `[carry]` lines on both arms; the fast-skip's
`gate_open`-style scheduling side effects (does an aborted attempt free the
station earlier -> lock-on down); and the branch-shift caveat (the arms draw
different fruit after the first divergence; quote class counts and intervals,
not cross-configuration rate deltas - AGENTS section 2).

## 2. Phase 0 corpus (fixed, from the existing logs only)

Four `FRUIT_DYNAMIC_TRACE=1` corpora named in `logs/w8/B_RESULTS.md` section 1
(55 traces total):

| corpus | traces | provenance |
| --- | --- | --- |
| `logs/w7/B_traces_mech` | 15 | the W7-B pinned direct mechanism run (`logs/w7/run_w7b_mech.sh`) |
| `logs/w5/traces_dense` | 10 | the W5 dense scripted run (`logs/w5/run_mech.sh`; cfg0 = the W4-record branch) |
| `logs/w8/B_traces_mech` | 15 | the W8-B patch-sheet direct mechanism run (`logs/w8/B_mechanism.sh`) |
| `logs/w8/B_traces_mech_run1` | 15 | the pre-fix instrumentation run, same scenario |

Legs and classes are re-derived by the W8-B metric (`logs/w8/B_metric.py`,
md5 `53cbf99b5a8fb8afb019cdd233bb3645`): carry rows split on time gaps
(> 0.02 s); `analyze_leg` at the 2.0 mm trigger; class map
`held -> clean`, `escape -> escape`, `no-contact -> excluded`.
**Expected counts (verified at write time by running the metric over the four
dirs): clean 33, escape 31, no-contact 25, jitter 0.** A mismatch is a hard
**STOP** (the corpus is the measurement; if it changed, this pre-registration
is void and the replay is NO-GO by protocol).

The gate is computed over the **64 critical legs** (33 clean + 31 escape); the
25 no-contact legs are the **Normal-class analogue and are excluded** (W8-A
section 4: the reach-cliff / catch-miss class is not a carry state; a
never-held payload trivially answers "not seated" but is handled by the outer
loop, and the shipped guard likewise blocks on it with `min_contacts > 0`).

## 3. Phase 0 protocol (frozen: features, labels, model, CV, gate)

### 3.1 Online features only (six; the privileged payload pose is forbidden)

Per tick of a leg, from the trace row fields that the live loop already
computes (the guard's read sites, `tasks.py` lines 2341-2410; `arm.jaw_separation()`,
`arm.jaw_positions()`, `tactile.read()`):

1. `sep` - the measured jaw separation (m);
2. `pry = sep - gap_cmd` - the commanded-gap offset (m);
3. `vsep` - the jaw (separation) velocity, `(sep_t - sep_{t-1}) / dt` (m/s),
   first tick 0;
4. `ft_min = min(ft0, ft1)` of the two finger tactile forces (N) - the weaker
   sensor;
5. `force = ft0 + ft1` - the summed normal force (N, the row's `force`);
6. `contacts` - the contact count (0-2).

**Forbidden at fit time and at live time:** `fruit`, `hand_rel`, `fruit_vel`,
`fruit_omega`, `offset`, `tip`, `cmd`, and anything derived from the payload
pose (`clean_slip` itself is label-side only, section 3.2).

### 3.2 Labels (offline only)

Per tick: positive iff the W8-B `clean_slip(t) > 2.0 mm` (the frame-free metric
of `logs/w8/B_metric.py`, recomputed on the same rows). Row 0 is always
negative by construction (it defines the reference). Every escape leg has
positive ticks (its `slip_max > 5 mm`); no clean leg has any (its
`slip_max <= 2 mm`). The label never enters the feature vector.

### 3.3 Model, CV, decision rule (frozen)

* **Model**: logistic regression, `p(escape|x) = sigmoid(w . (x - mu)/sigma + b)`.
  Features standardized with the training-fold tick mean/std (std floor
  `1e-6`). Zero init, full-batch gradient descent, loss = mean cross-entropy +
  `(lambda/2) * ||w||^2` with `lambda = 1e-3`, learning rate 0.5, **3000
  steps** (convergence reported: final loss + gradient norm).
* **CV**: **leave-one-trace-out** (all legs of the held-out trace predicted by
  a model trained on the ticks of the other 54 traces). Predictions pooled
  over the 55 folds. No per-fold threshold tuning; **threshold p >= 0.5**
  (z >= 0).
* **Decision**: a leg is predicted **escape** iff **>= 2 consecutive ticks**
  cross the threshold (`P = 2`, the persistence/debounce the live monitor will
  also carry; a persistent state does not need single-tick reflexes).

### 3.4 The gate (fixed; Sentinel's critical-state F1 + the numeric FP cap)

* Per-class F1 over the two critical classes and their **macro average** (the
  Sentinel protocol: class-balanced F1 over critical states only, Normal
  excluded - here `escape` vs `clean` over the 64 critical legs).
* **FP = clean legs predicted escape. Numeric cap: FP <= 2 of 33 (6.1 %); the
  denominator is fixed now.** (Target 0; 2 is the cap.)
* **Gate PASS iff macro-F1 >= 0.86 AND FP <= 2/33.** The 0.86 lower bound is
  the Sentinel-class bar (the source's sim 0.9024 / real 0.8567; the menu's
  falsification band 0.86-0.90). One pass, no rescue: if the gate fails, the
  verdict is **NO-GO** for this form and the recorded second signal is
  **JCAC's conformal action-space risk** (a residual-scale head on the frozen
  policy's executed prefix, calibrated on a disjoint split, episode-max-radius
  ranking; `logs/p6/B1_reread.md` section 1(e) / top-5 item 2) - **not built
  in this lane**.
* **Reported readouts (non-gating):** per-corpus breakdown of the CV
  predictions; detection latency per detected escape leg (first-fire tick vs
  onset row, vs the first contact-loss row, vs the leg's end); the clean-leg
  tick-level false-alarm fraction (pre-persistence); the standardized
  coefficients (mean over folds) and a **drop-one-feature ablation** (same CV,
  refit) as the feature attribution; the no-contact legs' raw fire counts
  (informational only); and per-attempt aggregation (an attempt is skipped iff
  any of its legs fires).

## 4. No-harm bar (Phase 1; fixed now)

With the knob unset the tree must be **byte-identical** to the pre-lane
record:

* `scripts/accept.sh`: **9/10 + `fingerprint: matches`** (the
  `configs/motion_reference.json` reference), its `[fruit]` stream identical
  to the record;
* the two-line dense re-record: **442/442 `[fruit]` lines + `scripts/190_twoline_gate.sh`
  PASS**;
* `scripts/selfcheck.sh` PASS;
* `FRUIT_CARRY_DIAG` off by default; the monitor's own traffic trace-only.

## 5. What is NOT in scope here

No implementation, no simulator, no `src/` change, no commit; the Phase-1
battery (section 1) is P7-2. This lane runs the frozen Phase-0 replay above
and publishes `logs/p7/C3_REPLAY.md` (verdict + numbers + failure modes). A
gate FAIL is a published negative, not a retry with different features; the
second signal is named in section 3.4 and is a different lane.

## 6. Pins (writing time, 2026-10-16)

* HEAD `908884c` (the P6-3 gate fix); branch `main`.
* `src/fruit_sorting/tasks.py` `bcb1fb72d80511a35f8b89cad0ca0a23`;
  `rl_env.py` `0c4f6b65993ea430eb432279cec0da8e`;
  `policy/trigger.py` `d7ec85fca5661a54473f7c6a69445fbc`;
  `policy/runtime.py` `ffb76bfd9bed1e71f6599c075d06a6c1`;
  `checkpoints/moe_v13s/policy_best.pt` `61da390a85fa209496b54477a8255d23`.
* Label source `logs/w8/B_metric.py` `53cbf99b5a8fb8afb019cdd233bb3645`;
  the four corpora as in section 2.
