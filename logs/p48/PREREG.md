# P48 phase 2 — pre-registration: the hand-over timing, two default-off levers, and its kill criterion

Written **before any run**, 2026-10-27, from `logs/p48/HANDOVER_CENSUS.md` (phase 1).
Tree clean at HEAD `2eec1a4`; `tasks.py` **`b6de439c`**, `fruits.py` `dff684b1`,
`rl_env.py` `93e35ef7`, `configs/motion_reference.json` **`8a399626`**,
`..._twoline.json` **`2246f83c`**. **No `src/` edit is registered**: both levers are
existing env knobs whose unset state is the shipped tree. No `configs/` write, no
commit (phase 3 owns those).

The registration exists because P48's item is *"find the hand-over timing lever"*
and phase 1 found that the census **predicts a null for every lever in that
list**. A registered, cheap, decisive null is worth more than an unregistered
suite of knobs, and the kill criterion (§6) is the deliverable that lets the next
phase spend on the lever the census did measure.

---

## 1. The two levers

| | **L1 — the hand-over lead** | **L2 — the catch-up budget** |
| --- | --- | --- |
| knob | `FRUIT_DYNAMIC_LEAD_MARGIN=0.20` (shipped 0.03) | `FRUIT_DYNAMIC_CATCH_TICKS=400` (shipped 200) |
| site | `_dynamic_pick_lead()`, `tasks.py:6053`, formula `:6062-6078` | the pre-close loop, `tasks.py:9958-10037`; read `:9930` |
| resolved effect | lead **0.189 -> 0.359 m** (189 -> 359 ticks of belt travel before the station); the descent is unchanged (arrival-synchronised) | the loop may chase for 400 ticks instead of 200 (+1.667 s) |
| second-order effect | **the selector floor moves with it** - `_dynamic_select_floor()` = lead + 0.12x1.5 + 0.03: **0.399 -> 0.569 m** against a measured `dy0` max of 0.570 m | none; 309/317 closes break at <= 6 mm before the horizon |
| registered cost | **+1.42 s of hover per attempt** (9 % of the acceptance's 15.0 s) + the floor's starvation risk (the P1c class) | +0.04 s/attempt pooled (2.5 % of attempts x 1.67 s) |
| why it is registered | it is the **namesake hypothesis** of the item, and the census says the lead is a **constant 0.189 m on all 8 failing rows and all 309 converged ones** - so a *strong* form is the only way to falsify "the hand-over timing is the mechanism" | it is P47's **"2.4x the reach budget"** claim turned into a measurement: if the gap is a *budget* deficit a longer loop converges, and if it is a *reach* deficit the residual grows by ~+200 mm |
| scope | scripted single-arm (`_dynamic_pick_lead` is also read by the two-line's selector; the battery is single-arm) | both lines; the battery is single-arm |

`U` = `FRUIT_SPEED_ALL=1` (the P44 union: place 0.52 / lift 0.36+1.9 / release
dwell 0 + 3->2 settle). It is the *speed context* the item came from (P44/P46) and
the only arm in which a lead change competes with a shorter cycle.

## 2. The arms and the scenarios

Per scenario: **C** (unset) / **L1** / **L1+U** / **L2** / **L2+U** — i.e. each
lever against its own control and against the union, with C shared.

| stage | scenario | arms | why |
| --- | --- | --- | --- |
| **1** | **S1** = the acceptance, seed 5 (the shipped scenario) | C, L1, L1+U, L2, L2+U (5 runs) | the gate-of-record scenario; its C is the recorded **6/10, 150.5 s, 15.0 s/attempt** (`p44/p2/accept_s5_C.log` = `p41/p2/accept_profile.log`, both 6/10) |
| **2** | **S3** = the acceptance seed 5 + `FRUIT_SPEED_RELEASE=1` (P44's S2 cell) | C, L1, L1+U, L2, L2+U (5 runs) | **the event leg**: this cell reproduced **E1/E2 in 2/2** historical runs (`accept_s5_S2` 219.6 mm, `amend_F_S2` 245.8 mm at x = 0.3966-0.3969); its C is the recorded **6/10, 143.4 s, 14.3 s/attempt** |
| **3** | **S2** = the pear battery, seed 5 (species-locked) | C, L1, L1+U, L2, L2+U (5 runs) | the composition-free no-harm leg; its C is the recorded **6/10, 157.1 s, 15.7 s/attempt** |

Order inside a stage: **C -> L1 -> L1+U -> L2 -> L2+U**, one claim per stage.
**Staged stop:** stage 1 runs first; if **F5** fires there the phase closes at
~25 min and stages 2-3 are **not** run; otherwise they follow in order.
**Hard cap: 15 runs.**

Not in the battery (and why): the two-line legs (E3/E4 live there, s5 C = 8/10,
s6 C = 9/10). They need `scripts/190_twoline_gate.sh`, their own reference and a
0.60 floor, and their failures are the *wave sheet's* own events on both arms -
a separate registration, not this item's.

## 3. Endpoints (all registered now)

| # | endpoint | definition | read from |
| --- | --- | --- | --- |
| **E1** | **the mechanism (primary)** | the descent's final gap `end=` per attempt: distribution (p50/p90/**max**) per arm | the `[motion] approach(cartesian) ... end=N mm` row, printed on every attempt (phase 1: population 8.1-10.6 mm on 315/317 closes; **the only two values above 10.6 mm are E1 15.3 and E2 14.8**) |
| **E2** | the residual's tail | the **> 6 mm count** and values per arm, each named by attempt/fruit | `[task] dynamic catch-up: residual=` |
| **E3** | placed | per arm, per scenario (10 attempts each) | `[stats] successes=` / `[run] attempt N: ...placed=` |
| **E4** | cadence | `s/attempt` (the `[stats]` sim span / attempts) | `[stats]` |
| **E5** | no new reason | the failure-reason set vs the C arm of the same stage, notes digit-normalised | the gate's reason table (`105`/the battery's own) |
| **E6** | the motion gate | `scripts/105_motion_regression.py` PASS (all descents inside the budgets); no `configs/` re-record | `105` |
| **E7** | starvation | `no eligible fruit` slots per arm (the L1 floor coupling) | `[stats]` + the `[run]` skip rows |
| **E8** | the branch check | the arm's physics `[fruit]` stream vs its stage's C: identical = the same attractor (then a count delta is meaningful); different = a **moved branch** (then only the mechanism reads travel) | the streams, `diff` after the tags are stripped |

## 4. The instrument (and its neutrality proof)

`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1` + `FRUIT_CARRY_DIAG=1` on **every** arm,
and **`FRUIT_HANDOVER_DIAG=1` on every arm** - it prints the one row phase 1 could
not reconstruct: `[diag] catchup <arm>: residual=... jaw=[...] fruit=[...]
tip_y-fruit_y=...` (`tasks.py:10040-10052`; three pose reads + one print per
**attempt**, not per tick).

**Condition on judging anything:** the diag's neutrality is proven by a
same-configuration **double run** in stage 1's C arm whose `[fruit]` stream is
byte-identical with the `[diag]` rows removed. If it is not, stage 1 is re-run with
the diag off and only the `end=`/residual endpoints are read (AGENTS §2/§3b:
instrumentation is part of the measurement).

## 5. Predictions, written down before the runs

| # | prediction | basis |
| --- | --- | --- |
| P1 | **L1 converts 0 of 4 events and leaves `end=` unchanged** (max within 10.6 mm, no value above it unless the branch draws a new x-tail instance) | the lead is 0.189 m on all 8 failing rows; the entry gap is produced *after* the hand-over (phase 1 §2.2) |
| P2 | **L1 costs +1.4 s/attempt** and, if the floor binds, loses >= 1 slot to `no eligible fruit` | lead follows `_dynamic_pick_lead` -> the floor follows (0.399 -> 0.569 m) |
| P3 | **L2 is a null on 309/317 closes** and, on any reproduced > 6 mm event, the residual is **~200 mm larger** | the residual is the belt travel (200 mm per 200 ticks) plus a 20-51 mm entry gap; the tip has recovered <= 25 % of the fruit's motion (phase 1 §2.2) |
| P4 | **U moves the branch** on S1/S3 (its release cell *is* S3's cell), so C-vs-U counts are not rates and only per-leg/mechanism reads travel | P44/P46 (AGENTS §2) |
| P5 | **the verdict is not adopted** on all arms | P1-P4 |

These are predictions, not results: the phase's job is to test them, and a
surprise (any arm that converts an event or moves `end=`) is the phase's finding.

## 6. Falsifiers and the decision rule

| id | condition | consequence |
| --- | --- | --- |
| **F1** | an arm places **2 fewer** than its stage's C | that arm is not adopted (the P44/P46 rule) |
| **F2** | a **new failure reason** appears (not in the C arm's set) | not adopted |
| **F3** | a **motion budget fails** (`105`) on any arm | not adopted, and the arm's branch is not re-gated |
| **F4** | L1's `no eligible fruit` slots exceed C's by **>= 2** | the strong lead form is abandoned (the floor coupling is confirmed); L1 is closed without a small-form retry |
| **F5** | **the phase's kill**: `E1`'s max is **<= 10.6 mm** on both L1 arms **and** no event is converted **and** `E2`'s count does not fall | **the hand-over timing is closed as the acquisition lever**; the item moves to P38b (the supply's per-instance release-offset compensation), which the census measures as the only lever that removes the 3 x-tail events by construction |
| **F6** | L2's residual on a reproduced event is **larger** than C's by >= 100 mm | P47's "budget" reading is confirmed as a **non-lever** (a mechanism result, published) |
| **F7** | any arm's `E8` differs from C's stream **and** its count differs | a **moved branch**: only the mechanism reads are used, no rate claim |

**Adoption rule (all must hold):** the arm improves **E1** (its max below the
stage's C max and no value above 10.6 mm) **or** converts a named event, **and**
`E3` is non-inferior on **every** stage, **and** `E5`/`E6` pass. Only then does
phase 3 own a default flip (which additionally owes both motion references'
re-record and the AGENTS §2 documentation). Anything else is published as a
negative with its mechanism.

## 7. Cost, protocol, and what this does not claim

* **Cost:** 15 runs at the measured 250-300 s/run on these scenarios = **63-75 min
  of simulator wall**, plus 3 claim overheads. Stage 1 alone is **~22-25 min** and
  is where the kill criterion (F5) is read; if F5 fires there, stages 2-3 are not
  run and the phase closes at ~25 min.
* **Protocol:** `scripts/selfcheck.sh` first (no `SKIP_SELFCHECK`); one
  `154_claim_run.sh` claim per stage, arms interleaved inside the stage; every run
  `HEADLESS=1` with the instruments of §4; logs under `logs/p48/p2/`; no
  `configs/` write, no commit.
* **Quantity of record:** `placed` and `s/attempt` are one draw of a
  deterministic branch per arm (AGENTS §2), so a count delta is *that branch's*
  count and the mechanism endpoints (E1/E2) are the reads that travel. The event
  counts are **instance-bound**: the x-tail kiwi is a per-instance release offset,
  so an arm that does not draw it cannot convert it, and an arm that draws a new
  instance can *create* an event - both are recorded, neither is a rate.
* **What this does not claim:** no rate, no clearance claim, no policy/direct/
  hybrid arm (out of scope), no two-line arm (§2), no claim that a null on these
  two levers closes the *acquisition* class - it closes the **hand-over-timing**
  reading of it, which is F5's wording.
* **Pre-registered deviations to watch:** if `FRUIT_DYNAMIC_LEAD_MARGIN=0.20`
  starves S1 so hard that the arm places <= 4/10, that is F4/F1 firing, not a
  measurement of the lead; the log will say so and the arm is closed rather than
  re-tuned (a re-tuned lead would be a new registration).
