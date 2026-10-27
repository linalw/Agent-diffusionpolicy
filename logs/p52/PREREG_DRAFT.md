# P52 — PREREG (draft): the action time-scale first, then two success levers

Written 2026-10-27 against `logs/p52/MODEL_CENSUS.md` (offline, HEAD `da0c914`). **Nothing
here is measured yet**; this is the registration the phases 2-3 run against.

**The question, in one line.** The policy's actions are executed at the demonstrated rate
(one action per 30 Hz control tick, 4 of 16 per decision - census §1.3); the model's own
emitted chunk has **2.3-3.3x** of joint-velocity headroom while the re-plan discontinuity
already exceeds j4's limit (census §3.2). **Does re-timing the executed chunk - the same
predicted path in fewer ticks - buy sim time, and what does it cost in placements?**

**The lane's stop rule, restated as this PREREG's F1**: if the re-timing buys no sim time,
the lane closes with that measurement (`.slim/deepwork/p52-model-lane.md` §4). A speed
gain that costs placements is **not** adopted unless the cost is named as the documented
class and the owner's speed-first directive is honoured in the record (P44-P51 practice).

---

## 1. Phase 2 — the arm: `FRUIT_POLICY_TIME_SCALE`

### 1.1 The knob

| item | value |
| --- | --- |
| name | **`FRUIT_POLICY_TIME_SCALE`** |
| semantics | `s > 1` executes the same predicted chunk **faster**: the arm's 7 joint targets (and the finger channel) advance `s` actions per control tick, linearly interpolated |
| default | **`1.0`** = the shipped path, byte-identical |
| registered cells | **1.0 (control) / 1.25 / 1.5** |
| scope | the direct presentation's chunk execution (the handoff/canary path shares `_apply`, so it inherits the knob - §1.4) |
| guard | `s * execute_steps <= action_horizon` must hold (4 x 1.5 = 6 <= 16); the resolver raises otherwise |
| site | `rl_env.py::act`'s chunk lookup (the `arr[index]` at `2970-2972`), i.e. **one expression**, and `_apply` is untouched |

### 1.2 The implementation (one expression, and the exactness argument)

For tick `index` of a decision, let `i = s * index`, then

```
action = lerp(chunk[floor(i)], chunk[min(floor(i) + 1, H - 1)], i - floor(i))
```

At `s = 1.0` the weight is exactly 0.0, so `action = chunk[index]` - the shipped path. The
exactness must be proven **offline** (`np.array_equal` on a unit test over random chunks at
`s=1.0`), because the direct loop is **not** bit-reproducible (rendered frames, AGENTS §3b)
and the scripted acceptance never constructs the env - so no run can prove it. This is the
P38-M4 / P43-style honesty: the scripted `[fruit]` stream is a **near-tautological** guard
here and will be reported as such.

Two properties to pin in the same selfcheck leg: `s >= 1` only (a slow-down is not
registered), and the finger channel interpolated by the same `i` (a 4.4 cm span, so this
only re-times the open/close ramp; the close is a 48-tick clock in the *primitive*, not
here).

**What the knob does not touch**: the decision cadence (a model call every 4 ticks stays),
the 16-action planning horizon's unused tail (executed 4 of 16 as shipped, now 4-6), the
scripted primitive (45 % of an episode), the belt floor (25 % of the policy phase), and the
re-plan discontinuity (chunk k+1's action 0 is applied unchanged).

### 1.3 The battery (the P43 protocol, verbatim scenario)

| item | value |
| --- | --- |
| driver | `logs/p43/p3/run_batch.sh` as the template (interleaved, one `scripts/154_claim_run.sh` claim, `112_rl_ab.sh` per pair) |
| arms | **T0** `FRUIT_POLICY_TIME_SCALE` unset / **T125** `=1.25` / **T150** `=1.5` |
| checkpoint | `checkpoints/moe_v13s/policy_best.pt` (`61da390a`) on **all** arms - the P43 corpus's checkpoint, so the control is comparable to the 94.6 % record |
| scenario | the P43 `SCEN_ENV` + `PATCH_ENV` verbatim: patch sheet, balanced A:B:C 0.375/0.375/0.25, `FRUIT_POLICY_TRIGGER=arrival`, lead 0.9, **ACQ=1**, `FRUIT_DYNAMIC_PICK=1`, the park default (`back` on the direct presentation) |
| N | **3 runs x 15 episodes per arm**, seeds **77/101/202** (the W8-A/C_ab set), `FRUIT_POLICY_SEED=11`, interleaved T0/T125/T150 per seed |
| instruments | **all arms identical**: `FRUIT_ACQ_DIAG` + `FRUIT_CARRY_DIAG` + `FRUIT_PARK_DIAG` + `FRUIT_RESET_ALIGN_DIAG` (the P43 set; the instrument sits inside the contrast, AGENTS §3b) |
| the motion report | one **extra report-on run per arm** (`FRUIT_RTC_REPORT=1`, 5 episodes) - the executed-stream `step`/`boundary`/`jerk` census, **report only, never gating** (it adds wall inside the loop) |
| canary | **one** `accept_policy.sh` run per cell as a **placement/no-harm smoke** (10 episodes, ~12 min each). It **cannot** show speed: its policy window is `APPROACH_STEPS = 400` ticks (`60_eval_policy.py:243-285`), so a speed reading would need that count scaled - out of scope, named as the follow-up (`FRUIT_APPROACH_STEPS` already exists as a knob) |
| cost | 9 runs x 15 x ~28 s of episode wall ≈ **63 min** + startup ≈ 75 min; the report runs ≈ 10 min; the canaries ≈ 37 min. **~2 h** |

### 1.4 The readouts (pre-registered, in this order)

| # | endpoint | statistic | bar (pass) | source of the number |
| --- | --- | --- | --- | --- |
| **P1** | **sim time per placed episode** (the speed) | median + mean `ticks` over each arm's placed episodes, and the per-seed paired difference (same seed = the same spawn set) | **T125 falls >= 8 %** vs T0 (the census's prediction is 11-12 %); T150 reported | `[rl] episode ... ticks=` |
| **P2** | **wall per episode** | the app wall / episodes (report only) | **no gate** - the loop is primitive-bound at a 10.7 % pause share (P43 L2) | `run wall end ... duration` |
| **P3** | **placements (the guard)** | right-arm placed proportion, the per-run counts, and a one-sided 95 % Newcombe lower bound on the difference | **>= -0.10** (the P36/P37/P43 margin) **and** no new failure reason vs this batch's own T0 **and** the run level not worse in all 3 pairs | `placed=True` |
| **P4** | **failure classes** | the per-arm `cnp` / no-grasp / escape counts, and the `[carry]`/`[acq]` class census | reported; a class that grows in **both** speed cells at the same arm is a **fail** | the P43/E parser (`model_census.py` §E) |
| **P5** | **the motion census** | the executed stream's `step`/`boundary`/`jerk` per decision and the joint-limit exceedance share | reported; **the census predicts** 0 % of executed joint-steps over a limit at s=1.0 -> **0.07 % at 1.25** (census §3.2) | `FRUIT_RTC_REPORT=1` |

**Pre-run prediction (written before the run).** P1: **-190 to -205 ticks (-1.6 to -1.7 s,
11-12 %)** at s = 1.25, from the census's arm-motion budget (6.38-6.84 s of the policy
phase, minus its 25 % belt floor) - an upper bound that assumes the drive turns the extra
ramp into achieved speed. At s = 1.5: -255 to -275 ticks (14-15 %). P3: the park's 94.6 %
(right) is the ceiling of a ~5 %-resolution measurement at n ≈ 50, so **0-3 placement
changes is the expected noise** and any reading inside [-0.10, +0.05] is "the same".

### 1.5 The falsifiers (pre-declared, each one kills or repairs a clause)

| # | falsifier | consequence |
| --- | --- | --- |
| **F1** | T125's placed-episode ticks do **not** fall >= 8 % | **the lever is null -> close the lane with the measurement** (the lane's own stop rule). Report the achieved-vs-command ratio and the decision count to say *why* (the drive does not follow, or the phase is not motion-bound) |
| **F2** | the right-arm placed difference is **< -0.10** at either cell | that cell is not adopted; the other cell is read on its own |
| **F3** | a **new failure reason** appears in both speed cells | not adopted regardless of the speed |
| **F4** | the **decision count** per episode moves materially at s (it must not - the cadence is fixed) | an implementation error, not a result: stop and repair |
| **F5** | the boundary-jump census (`P5`) **rises** with s (it must not - chunk k+1's first action is untouched) | an implementation error, not a result |

### 1.6 Adoption rule (phase 2)

Adopt iff **P1 passes at 1.25** (>= 8 % sim-time) **and P3 passes** (>= -0.10, no new
reason) - then the ceiling of the two passing cells is taken as the default candidate and
the *scripted* line is untouched (the knob is direct-scoped, `FRUIT_POLICY_TIME_SCALE`).
P2 (wall) and P5 (motion) are reported, not gated: the wall is the primitive's, and the
motion census has no scripted-equivalent gate on this interface.

---

## 2. Phase 3 — the two success levers (each its own claim, never combined)

Ranked by measured prior, both **env-only, default-off**, both on the same scenario and the
same N as phase 2 (3 runs x 15, seeds 77/101/202, one claim each).

### S1 `FRUIT_POLICY_EVENT=1` — the continuity-triggered decision horizon

* **Prior**: the **best measured arm on record**: 33/45 = 73.3 % vs the base 30/45 = 66.7 %
  (**+6.7 pt**), every run delta >= 0, no new failure reason, strawberry +5 pt - it missed
  its own pre-registered **+8 pt** bar at N = 3, so it was never adopted and **never run at
  N = 5** (WORKLOG path-3).
* **Why it is also a speed lever**: it replaces the fixed 4-tick horizon with one chosen
  from the chunk's continuity (`rl_env.py:2939-2940, 3560-3582`), so it **reduces the
  model-call count** - the loop's pause is a measured 10.7 % of the episode wall and a
  decision costs 47.4 ms against 33.3 ms of sim (P43 L2). Register the decision count as
  its mechanism readout.
* **Endpoints**: pooled placed non-inferiority (>= -0.10) **and** the decision count per
  placed episode falls **and** no new reason. The pre-registered bar for a *success* claim
  stays **+8 pt** (its own, unchanged).
* **Cost**: 2 arms x 3 x 15 ≈ **42 min**.

### S2 `FRUIT_POLICY_TRIGGER_ACQ` — on/off, i.e. whether the shipped default is the measured one

* **Prior / the gap**: `ACQ=1` is in **every park-era batch** (P35/P36/P37/P43 `SCEN_ENV`),
  so the 94.6 % right-arm record **is an ACQ=1 number**, while the shipped default is
  **ACQ off** (R5 decision 4; `trigger.py:167`). **The shipped direct configuration's
  post-park placement count does not exist.** ACQ's own mechanism is the strongest single
  one in the acquisition family (left no-contact 9 -> 1, close-start median 88.8 -> 1.4 mm,
  pooled +11 pt at N = 3, p = 0.0898).
* **Endpoints**: the right-arm placed difference between ACQ=1 and ACQ=0 (>= -0.10 keeps
  the shipped default; a **positive** ACQ=1 delta of >= +0.10 with no new reason makes the
  default flip a candidate on **its own** pre-registration); the `no-grasp` class count
  (the only open class on the right); the `[acq]` close-start residual as the mechanism.
* **Cost**: 2 arms x 3 x 15 ≈ **42 min**.

---

## 3. What is **not** registered (already measured, do not spend)

| item | why |
| --- | --- |
| a new checkpoint / fine-tune | five spends, five no-gains (census §4): `moe_v13p` +1/75, `p33_pear` -8/45, `p37_park` -0.018, `rl_awr1` -7/75, `moe_v13s`/`moe_v12` interface-dependent. What they target is the **closed** grip class |
| the per-step correction layer (`FRUIT_A2C2`) | it exists and is measured **negative**: 21/45 = 46.7 % vs 30/45 = 66.7 % (**-20.0 pt**) at N = 3x15 (WORKLOG path-3, `moe_v11_correction` `5d52d1b1`) |
| `FRUIT_POLICY_TRACK` / `FRUIT_VLASH` | +2.2 pt FAIL / -31.1 pt with a new class |
| RTC / VLASH at `moe_v12` | null-to-negative on rate twice, and the per-tick wall does not fall; P43 L2 already measured the pause at 10.7 % (< the 25 % bar) and closed the loop lever |
| the **left** arm (direct) | 94.7 % of its failures are `cnp`, i.e. `logs/p42/SIM_LIMIT.md`'s closed loaded slide, and `configs/arm_parks.json` has a left-only vector so the park cannot move it |
| a wider trigger lateral gate / an x-ceiling | P38 (0.06 % of episodes) and P49 (a binding ceiling refuses 0/40 selections) |
| the scripted speed cells (S1/S2/S3/S13) | the P44 cells are real (-1.45 s/attempt) but their cost is the pre-contact acquisition class and P51's map shows the union + the P50 compensation **cannot** be class-clean |
| the release-offset compensation (P50) | its own count gate failed (6/10 -> 4/10) on a moved branch; it stays opt-in |
| the canary as a *speed* probe | its policy window is a fixed 400 ticks; it is a placement/no-harm smoke here (§1.3) |

---

## 4. Power, plainly

* **P1 (sim time) is very well powered**: among placed episodes the per-episode ticks have
  **sd 71-73** (P43 corpus, n = 33-53), so the predicted **-190 ticks** is **~2.7 sd**, and
  even a third of it (-65 ticks) is 6 SEM at n = 45. The speed question is the cheap one.
* **P3 (placements) is the weak one**: at n ≈ 50 right-arm episodes/arm and a ~95 % base,
  one episode is 2 % and the resolution is ~±0.10 - which is why the bar is a
  **non-inferiority margin**, and why a *positive* placement claim would need the N = 5 /
  75-episode form (the WS-4.2 convention).
* No cross-configuration **rate** comparison is made: every count is one attractor, and the
  three arms are three different command streams by construction. The per-episode ticks,
  the per-run counts and the class tables are the measurements.

---

## 5. Provenance and open items this PREREG inherits

* The census (`logs/p52/MODEL_CENSUS.md`) fixes the numbers this registration quotes; its
  §5 lists what it does not claim.
* **The census's B2 is offline** (checkpoint on demo observations, seeded), so the emitted
  stream's headroom is a property of the *model*, not of the closed loop.
* **`moe_v12` vs `moe_v13s`**: the park corpus (and therefore the 94.6 %) is `moe_v13s`,
  the shipped default is `moe_v12`, and no post-park `moe_v12` direct measurement exists.
  Phase 2 uses `moe_v13s` on all arms (the P43 rule: a configuration that cannot be
  deployed is not measured); the `moe_v12` gap is a separate, unregistered question.
* **The hybrid canary's lease**: if phase 2 passes, the canary needs
  `FRUIT_APPROACH_STEPS` scaled with `s` before it can carry the speed claim - registered
  here as the follow-up, not as part of this phase.
