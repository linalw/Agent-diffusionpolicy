# P83 PREREG — fail fast: a lost payload should not cost a whole attempt

Registered 2026-11-01, **before any run of the new knob**, on the P82-final tree
(HEAD `3d0a30d`, `tasks.py` `e8dfa6d8`, `rl_env.py` `7d26eb5b`, `scene.py` `07d6fdad`,
`assets.py` `540406fa`, `control.py` `9384ff4f`, `fruits.py` `c7461d41`,
`conveyor.py` `fb2c58c6`, `bimanual.py` `7e2b7d7e` (the P82 wake-on-request flip),
`configs/motion_reference.json` `8952c320`,
`configs/motion_reference_twoline.json` `eb697f23`).

Owner directive: **the cell pays a full attempt for every failure; fail fast.**
Default off, nothing adopted by this phase unless its own gate passes, **no
default change, no commit, `configs/` untouched.**

## 0. The lever, and why it is the biggest one left

P80 measured the shipped scripted cell (20 slots, seed 5): **12/19 placed,
15.10 s/attempt, inter-placement interval 26.72 s mean / 36.90 s p90**, and the
whole interval is `26.72 = 4.8 s idle + 1.45 attempts x 15.1 s`. Every one of the
7 failures is `grasped, not placed` (`cnp`): the payload leaves the pinch
mid-carry, and the cell **still runs the leg out** — the place transfer, the
release block and the return — before scoring the attempt. At a ~37 % failure
rate, ending an attempt the moment the payload is provably gone is worth
`~1 failure x (place 3.19 + release 2.11 + return 0.63 s) = ~5.9 s` per
placement, i.e. **~20 % of the interval**, for the same placements.

The measurement already exists inside the leg: the W8-B `clean_slip` (the
payload's displacement in the leg's own frame, accumulated per tick under
`FRUIT_CARRY_DIAG`/the guard, `tasks.py` `_carry_leg`) separates the classes with
no overlap — placed legs **0.0-76.3 mm** (P83 §3 census, n=249), escapes
**> 800 mm** with `force_min = 0.00 N` (P75/P76/P60).

**What the abort is NOT.** It does not fix the grip, it does not convert a `cnp`
into a placement, and it does not change the failure class. It is a **clock
lever on a loss that already happened**: the outcome stays `cnp`; only the ticks
spent after the loss are removed.

## 1. The knob

`FRUIT_FAIL_FAST=<mm>` (`tasks.py`), **default unset/0 = off, the shipped path.**

* Trip rule: **one** threshold, on the leg's own running `clean_slip_max`
  (the same per-leg operand the `[carry]` row prints — the payload's displacement
  since the leg's first tick, in the leg's frame). When it reaches the threshold
  the attempt ends **at that tick** through the existing early-exit machinery.
* **Refused values**: anything `0 < mm < 100` raises at task construction; a
  clean leg can never trip the knob at a value the corpus cannot separate.
  `mm = 0` or unset = off; negative/`nan`/`inf`/non-numeric raise.
* **Scope**: `scripted` only (the single arm, the two-line worker, the
  collector). The direct/policy handover and the hybrid canary keep their own
  loop and their own `P10-C` monitor; this knob resolves `(off)` there.
* **Armed class**: dynamic-capture carry legs only (`hand_is_jaw and
  _dynamic_capture_active`), i.e. `grasp_lift` and `place*` on the moving-catch
  line. The indexed path never trips it (its payload does not leave the pads).
* **What the abort skips**, in order of the code: the remaining ticks of the
  tripping leg, that leg's 50-tick tail (30-tick settle + the `FRUIT_CARRY_FREEZE`
  ramp), the other carry leg of the attempt (`place*` if the lift tripped), the
  whole release block (`~253` ticks) and the retreat/return (`~76` ticks). It does
  **not** skip the driver's post-attempt `go_ready`, which is outside the attempt
  span by construction.
* **The arm is safe by construction**: the next pre-pose goes through the
  calibrated teleport (`go_ready` -> `_goto` teleports first), which is the same
  path every shipped failure already takes — an aborted attempt ends *before*
  the flat-wrist place pose, not after it, so it is strictly easier.
* **The payload is recycled** by the attempt's own `finally` (`run()` clears
  `held` and unprotects the index), which is the shipped failure path; no new
  recycle code is added.
* **The class is unchanged**: no note is appended to `result.notes`, so the
  failure-reason parser sees exactly what the shipped run would have seen
  (`cnp` from `grasped=True, placed=False`, or `fruit did not follow the
  gripper` if the peak lift is below 0.05 m — the same predicate as shipped).
* **Instrumentation**: the trip needs the per-tick `clean_slip` tracker live, so
  the treatment arms also run the W8-B block (`guard_armed`). The gate therefore
  includes a **tracker-only arm** (§2 `D`), because the treatment differs from
  the shipped path by *tracker + abort* unless the tracker is proven neutral.

### The registered value: 150 mm

The threshold has to sit above every **placed** leg and below every escape. The
pre-run corpus census (`logs/p83/census.py`, `logs/p83/census.txt`; 43 scripted
logs that already carry `[carry]` rows, 249 placed attempts / 165 failed):

| population | n | p50 | p90 | p99 | max |
| --- | --- | --- | --- | --- | --- |
| **placed** attempts, worst leg | 249 | 0.1 | 11.6 | 62.1 | **76.3 mm** |
| **failed** attempts, worst leg | 165 | 1152.5 | 1402.3 | 1683.0 | 3830.7 mm |

`>= 150 mm`: **0/249** placed, **164/165** failed. So 150 mm is a **1.97x margin
over the worst placed leg** and inside the failure population; the code floor of
100 mm keeps a 1.31x margin. **One arm, one threshold** — no ladder is spent.

## 2. Arms (all `HEADLESS=1`, `ATTEMPTS=20`, the shipped scenario)

Instrumentation on **every** arm: `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`
(the P80 convention). No supply/grade/speed knob; `FRUIT_OUTPUT_RAILS` unset
(shipped `none`, P71).

| arm | seed | env on top of the set | what it is |
| --- | --- | --- | --- |
| **C5** | 5 | — | the control **re-run on the post-patch tree** — must replay P80's `S20.log` |
| **D5** | 5 | `FRUIT_CARRY_DIAG=1` | **tracker only** — the neutrality control for the treatment's instrumentation |
| **F5** | 5 | `FRUIT_FAIL_FAST=150 FRUIT_CARRY_DIAG=1` | the lever |
| **D6** | 6 | `FRUIT_CARRY_DIAG=1` | tracker neutrality at the second seed |
| **F6** | 6 | `FRUIT_FAIL_FAST=150 FRUIT_CARRY_DIAG=1` | the lever, second seed |

`FRUIT_CARRY_DIAG=1` is on in `D`/`F` because the trip *is* that tracker: the
`[carry]` row is the aborted-leg audit (tick, `sep`, `force_min`, `clean_slip`,
`onset_row`, `loss_row`) and the placed-leg census, and it is the only way to
show that no placed leg approaches the threshold.

The seed-6 **control** is P80's own `S6.log` (`13/19`, `15.00 s/attempt`,
interval `26.12 / p90 38.6 s`) — the same tree, no re-run (the only change since
P80 is `bimanual.py`'s P82 wake-on-request, which the single-arm path never
reaches; and P80's `S20`/`S6` are reproduced by `C5`'s byte-identity check).

One `scripts/154_claim_run.sh` claim and one simulator at a time; each arm is
wall-stamped with `logs/p80/stamp.py` (via a `one_run.sh` copy) so the wall
column is measured, never inferred. Order: **C5, D5, F5, D6, F6** — interleaved
by seed so a tree or machine drift cannot masquerade as the lever.

## 3. Endpoints (registered, so the number cannot drift)

| # | endpoint | source |
| --- | --- | --- |
| **E1** | **inter-placement interval**: pooled mean / p50 / p90 | `logs/p80/p80lib.py` (186's parser) |
| **E2** | **placed/min** on the **placement window** *and* the **batch span** — both, never mixed | p80lib |
| **E3** | **the cost of a failed attempt, in ticks**: the mean `sim=` span of the failed attempts, control vs treatment (the aborted attempts are the treatment's failed ones) | the `[run] attempt` rows |
| **E4** | `s/attempt` over all attempts (the `[stats]` figure) | `[stats]` |
| **E5** | per-attempt span of the **placed** attempts (a placement must not get slower) | `[run]` rows |
| **E6** | placed count and class split (reported; a **draw**, see R1) | p80lib `classes` |
| **E7** | **wall**: `wall/pick`, `wall/sim`, placed/min wall | the `.stamps` stream |
| **E8** | the motion gate on the legs that ran: per-leg **budgets** (`|v|max`, lurch, cone) on the 20-attempt logs, plus `105_motion_regression.py` with no fingerprint at 20 attempts (**a 20-attempt log cannot match the 10-attempt reference**) | `105`, `[motion]` rows |
| **E9** | **the aborted-leg audit**: per trip, the tick, the leg, `clean_slip`, `sep`, `force_min`, `contacts`, `onset_row`, `loss_row`; and every placed leg's `clean_slip_max` | `[fail-fast]` + `[carry]` rows |
| **E10** | `[cycle]` decomposition by arm (what the saved block is) | `[cycle]` rows |

Definitions fixed here: a **placement** is the attempt's `t1`; the **placement
window** is `t_last_place - t_first_place`; the **batch span** is
`t_last_end - t_first_start`; **wall** is `[run] attempt 0` -> `[fruit] DONE` on
the stamp stream (never gated — harness cost, P80 §6).

## 4. Read rules (binding)

* **R0 — the abort moves the branch, and that is registered.** The saved sim
  seconds are seconds the **belt keeps moving**, so the next attempt is
  presented a **different fruit** (the feeder keeps an absolute schedule). The
  treatment is therefore a *different scenario* after its first trip: the
  **count is a draw**, and so is any per-class rate. The claim is the **time**
  (E1-E5) and the **per-attempt mechanism** (E3, E9).
* **R1 — no cross-arm count as a rate.** A placed count is one draw of a
  deterministic branch (AGENTS §2). Counts are reported with the branch caveat.
* **R2 — the interval is the claim, both denominators are quoted.** A rate
  without its denominator is a defect.
* **R3 — a placement must not get slower and no successful leg may be
  shortened** (G5). If one is, the form fails *whatever* the interval does.
* **R4 — two seeds, same-direction.** A seed-5-only reading is a sample.
* **R5 — the wall is reported, never gated** (harness cost).

## 5. Guards (all must pass for a positive reading)

| # | guard | test |
| --- | --- | --- |
| **G1** | **off-path inertness** — the knob unset is byte-identical to the shipped path | `python3 logs/p82/p82_report.py --same logs/p80/S20.log logs/p83/C5.log` reads `IDENTICAL` |
| **G2** | **tracker neutrality** — the tracker alone does not move the physics | `--same C5.log D5.log` reads `IDENTICAL` (and `D6` vs `S6`) |
| **G3** | **in-batch prefix identity** — the treatment's first attempt(s) equal the control's up to the first trip | the `[fruit]` streams of `C5` and `F5` share a prefix that ends exactly at the first `[fail-fast]` trip |
| **G4** | **the abort only fires on lost payloads** — at the trip tick the pinch is gone: `force_min = 0.00 N` or `contacts = 0` (and the leg's `sep`/`loss_row` on the same side), and **no placed leg anywhere in the corpus reaches the threshold** (§1 census + the treatment's own placed legs) | E9 |
| **G5** | **no successful leg is shortened** — every carry leg of every **placed** attempt reads `ticks=X/X` (ran to completion) and its `clean_slip_max < 150 mm` | E9 |
| **G6** | **no new failure reason** — the treatment's failure-reason set is a subset of the control's, and every aborted attempt scores `cnp` (or the `fruit did not follow the gripper` class it would have scored) | p80lib `reasons` |
| **G7** | **motion budgets** on the logged legs; no descent leaves the speed/lurch budget | E8 |
| **G8** | **no wedge, no lost slot** — every armed run completes with `attempts = placed + failed`; an aborted attempt is followed by a normal attempt; the payload's index is not retried forever | `[stats]`, `[run]` |

## 6. Decision rule (the one table the phase owes)

The **mechanism must hold first** (it is branch-free):
* **M1** = G4 and G5 (the abort fires only on lost payloads; no placed leg is
  shortened), **and**
* **M2** = the **failed-attempt cost (E3) falls by >= 3.0 s** against that
  seed's control (the leg arithmetic predicts 5-6 s: place 383 ticks + release
  253 + return 76 = 5.9 s, minus the trip's position inside the leg), **and**
* **M3** = G1, G2, G3, G6, G7, G8.

**ADOPT (recommendation only — this phase changes no default)** iff M1-M3 hold
**and**
* **T1** the pooled interval mean falls **>= 8 %** against that seed's control
  at **both** seeds (the arithmetic predicts -8..-14 % at 5-6 s per failure), **and**
* **T2** the placed count is non-inferior at both seeds (`>= control - 1`), **and**
* **T3** placed/min improves on **both** denominators at the seed-5 pair.

Otherwise: **not adopted**, and the phase publishes the mechanism (M1/M2), the
interval pair and the reason it fell short (T1/T2/T3).

**Falsifiers** (the phase still reports, the reading is qualified):
* **F1** — G1 fails: the post-patch tree has moved the shipped branch; then
  every arm is a different scenario from P80's and no cross-arm time claim is
  made until the branch is named, and the seed-6 control is re-run.
* **F2** — G2 fails: the tracker is **not** neutral. Then the treatment differs
  from the control by *tracker + abort*, the interval claim is **unadjudicable**
  on this design, and only M2 (per-attempt arithmetic) is published. A
  tracker-only arm that moves the physics is itself a finding (the W8-B block
  would then be a control input on the scripted line, which AGENTS §2 forbids).
* **F3** — G3 fails *before* any trip: instrumentation, not the abort, moved the
  branch, and F2's verdict applies.
* **F4** — G4 fails on one leg (a live pinch tripped): the threshold is
  inadmissible and the form fails.
* **F5** — G5 fails on one leg (a placed leg was shortened): the form fails,
  full stop.
* **F6** — G6 fails (a new reason appears): the form fails (the class must be
  the outcome, not the abort).
* **F7** — a run wedges (renderer freeze) or exits non-zero: re-run once; a
  second failure is recorded as a missing arm, never inferred.

## 7. What is NOT run, and why

* **No threshold ladder.** One arm, one value (150 mm), justified by the §1
  corpus census; a ladder would multiply the runs to buy a dose-response the
  census already pins.
* **No two-line arm.** The knob is scripted-scoped so the two-line inherits it,
  but P80/P81 measured the two-line as a *simulated-time* lever whose wall is a
  wash on this harness; its fail-fast share is a separate phase.
* **No direct/policy arm.** The direct handover already owns the P10-C monitor
  (a slip-classifier fast-skip at the leg boundary); the P83 lever is the
  scripted line's, and the direct corpus is out of scope.
* **No grip fix.** The `cnp` class is closed (`logs/p42/SIM_LIMIT.md`).
* **No default change, no commit, no `configs/` write.**
