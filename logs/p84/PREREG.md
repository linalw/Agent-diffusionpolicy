# P84 PREREG — fail fast on the two-line: does the overlap absorb the abort?

Registered 2026-11-01, **before any run of this phase**, on the P83-final tree
(HEAD `1a2eec2`, `tasks.py` `f1e44af6`, `bimanual.py` `7e2b7d7e` (the P82
wake-on-request flip), `rl_env.py` `d786279c`, `scene.py` `07d6fdad`,
`assets.py` `540406fa`, `control.py` `9384ff4f`, `fruits.py` `c7461d41`,
`conveyor.py` `fb2c58c6`, `configs/motion_reference.json` `8952c320`,
`configs/motion_reference_twoline.json` `eb697f23`).

**Measurement only: nothing adopted, no default change, no commit, no `src/`
change, `configs/` untouched.** This is P83's **registered re-entry**
(`logs/p83/RESULTS.md` §8): the same knob, the scenario where the presentation
is not the binding term.

## 0. Why this is the right next cell

P83 measured the mechanism on the **scripted single arm** and lost on the
throughput:

* the abort **halves a failed attempt by exactly -5.144 s = -617 ticks at both
  seeds** (15/15 trips at `force = 0.00 N` *and* `contacts = 0`, 34/34 carry legs
  of the 17 placed attempts read `ticks = X/X`, the off path byte-identical to
  P80's `S20`);
* and the **interval got worse** (26.72 -> 35.26 s at seed 5, +4.8 % at seed 6),
  because on the single arm the abort **re-times the presentation**: the belt
  keeps moving, the next slot is handed a different fruit, `attempts/placement`
  rose 1.583 -> 2.333, and six slots then starved on a pool whose only
  above-floor body was already `diverted` (`logs/p83/RESULTS.md` §4, §7b).

The two-line is a different object. P80/P81 measured it:

* its **per-arm attempt span is the single arm's** (15.0-15.6 s against 15.09 s):
  the pipelined scheduler **overlaps attempts, it does not shorten one**;
* its gain is therefore **occupancy** — a mean 1.58 (seed 5) / 1.44 (seed 6) arms
  busy per attempt, against the single arm's 0.83;
* and an arm that finishes early **parks on the other arm**, not on the belt
  (`_biarm_park` waits for the other arm's station owner and payload, `tasks.py`;
  W6-C measured that gate as "left gate-blocked idle 25.2 -> 0.2 s" when it was
  opened earlier).

So on the two-line a freed 5.14 s should be spent as **occupancy**, not as a
re-drawn fruit. That is the hypothesis, and it is the one thing this phase
tests.

## 1. The lever (unchanged from P83 — no code is added here)

`FRUIT_FAIL_FAST=<mm>` (`tasks.py`, `parse_fail_fast`), **unset/0 = off = the
shipped path**. One compare per guarded tick on the W8-B tracker's own per-leg
operand `clean_slip_max` (the payload's displacement in the leg's own frame,
the number the `[carry]` row already prints). On a trip:

* the leg breaks at that tick; the rest of its profile, its 50-tick tail, the
  attempt's other carry leg, the release block (~253 ticks) and the
  retreat/return (~76 ticks) do not run;
* the attempt ends through the **two early-exit sites the P7-2b monitor already
  uses** (`_attempt_ended_early()`), it adds **no `notes` entry** (so the class
  is what the run-out would have scored: `cnp` from `grasped=True,
  placed=False`, or the shipped `fruit did not follow the gripper` when the peak
  lift is below 0.05 m), and the payload is recycled by `run()`'s own `finally`;
* scope: `scripted` only, armed class = dynamic-capture carry legs. The two-line
  worker runs the **same** `run()` -> `_run_impl` -> `grasp_carry_place(
  scripted=True)` path as the single arm, so it inherits the knob by
  construction (`dynamic_capture = True` on the OpenArm scripted line) — this is
  **verified on the log**, not assumed (§5 G4: the `[fail-fast]` rows exist and
  the trips are audited).
* **The value stays 150 mm** — P83's pre-run corpus census (0/249 placed
  attempts ever reach it, the worst placed leg is 76.3 mm; the code refuses
  anything under 100 mm). No new ladder is spent; a second value would be a
  dose-response on a threshold the corpus already separates.

## 2. The arithmetic this phase is registered against

The two-line's interval is not `attempts/placement x span + idle` — two arms
overlap — so the same saving is divided by the **concurrency** (P81's own
identity: `batch sim seconds per attempt = mean span / arms busy`):

`interval ≈ (attempts/placement x mean span) / concurrency + idle / concurrency`

With P83's **-5.144 s per failed attempt**, at the **control's own failure
rate**:

| seed | control | attempts/placement | concurrency | predicted interval fall | predicted interval |
| --- | --- | --- | --- | --- | --- |
| 5 | `T20`: 16/20, 4 failures, 10.77 s | 1.25 | 1.58 | (4/16) x 5.144 / 1.58 = **-0.81 s** | 10.77 -> **9.96 s (-7.6 %)** |
| 6 | `T6`: 10/20, 10 failures, 19.34 s | 2.00 | 1.44 | (10/10) x 5.144 / 1.44 = **-3.57 s** | 19.34 -> **15.77 s (-18.5 %)** |
| pooled | 15.06 s | — | — | — | **-13.6 %** |

The **span term alone** (`attempts/placement x mean span`, branch-free given the
failure count) is predicted to fall **-1.29 s** (seed 5) and **-5.14 s** (seed 6).

**What "the overlap absorbs the abort" means numerically, and what falsifies it.**
The abort is absorbed only if the freed sim seconds appear in the **delivered**
interval — i.e. the **per-arm idle and the park gate-blocked / lock-on waits fall
by roughly the freed amount**, and the pooled interval falls with them. The
registered **null** is the other shape: the arm finishes early and then **waits
longer for the belt** (the P81 supply-bound regime — its right arm reports no
eligible fruit on 65-93 % of its polls), so the **idle rises by ~5.14 s per
failure** and the interval is **flat or worse**. The two-line would then say what
the single arm said (P83), and the phase publishes that as the answer rather than
as a failed experiment.

**Consequence of R0 for the prediction:** the abort moves the branch (the belt
keeps moving, so the next slot is presented a different fruit). The prediction
above is an *at-the-control's-failure-rate* statement; the delivered interval is
whatever that branch delivers, and the **mechanism** read (§3 E3/E9) is the
branch-free number.

## 3. Arms (all `HEADLESS=1 ATTEMPTS=20`, the shipped two-line scenario)

Every arm: `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1` (P80/P81's convention) **plus
`FRUIT_CARRY_DIAG=1 FRUIT_BIARM_PARK_TRACE=1`**. No supply/grade/speed knob —
the two-line's own package (dense wave sheet + balanced A:B:C + pure routing) is
its shipped default and is left alone; `FRUIT_OUTPUT_RAILS` unset (shipped
`none`, P71). More than one cell of the scheduler's concurrency: `FRUIT_BIARM`
stays `1` (shared belt, two stations).

`FRUIT_BIARM_PARK_TRACE=1` is **pure reporting** (`say()` on entry to the park
gate, on its break and on completion) and it is on **both** arms, so the A/B is
instrumented identically. Its lines are `[biarm]`-prefixed, **not `[fruit]`**, so
it cannot disturb the `[fruit]` stream identity test that proves the tree is on
P80's branch (§5 G1).

| arm | seed | env on top of the set | what it is |
| --- | --- | --- | --- |
| **D5** | 5 | (set only) | **control, scheduler only** — the same configuration as P80's `T20`, re-run on this tree |
| **F5** | 5 | `FRUIT_FAIL_FAST=150` | the lever |
| **D6** | 6 | (set only) | control, second seed (P80's `T6` configuration) |
| **F6** | 6 | `FRUIT_FAIL_FAST=150` | the lever, second seed |

Interleaved by seed (**D5, F5, D6, F6**), one `scripts/154_claim_run.sh` claim and
one simulator at a time, each arm wall-stamped per line (`logs/p80/stamp.py`
through a `one_run.sh` copy), so the wall column is **measured, never inferred**.

**Both arms carry the tracker** (P83's G2 proved `FRUIT_CARRY_DIAG` run-neutral on
the **single arm** at 710/710 and 708/708 `[fruit]` lines). On the two-line that
is **re-proved here** against P80's records (§5 G1), because the treatment then
differs from the control by **the abort alone** — no tracker-only arm is spent.

The seed-5/6 **controls are re-run**, not read from P80: the tree has moved since
P80 (P82's `bimanual.py` wake-on-request is the two-line's own path), so a
control that does not replay `T20`/`T6` is exactly the information the phase
needs — and if it does replay them (expected: P82 proved W1/W2/W3 = `T20`
865/865 with the knob on), the branch is P80's and the phase's numbers are
comparable to P80 §3 and P81 §3.

## 4. Endpoints (registered so the number cannot drift)

| # | endpoint | source |
| --- | --- | --- |
| **E1** | **inter-placement interval**, **pooled** mean / p50 / p90 **and per arm** | `logs/p80/p80lib.py` (186's parser: a placement is the attempt's `t1`) |
| **E2** | **placed/min** on the **placement window**, the **batch span**, **and the wall** (60·placed/wall) — all three, never mixed | p80lib + `.stamps` |
| **E3** | **the failed attempt's own span** (branch-free mechanism number): mean `t1-t0` over the failed attempts, per arm and pooled | the `[run] attempt` rows |
| **E4** | **per-arm idle** (gap between one attempt's end and that arm's next start, over the arm's span) | p80lib `per_arm` |
| **E5** | **lock-on** per arm (previous attempt end -> `station acquired at t=`) and its **retries** (starved polls) | p80lib `lock_on`, 186 `retries` |
| **E6** | **park gate-blocked** time per arm (wait-start -> moving) and the return motion (moving -> done), plus the number of parks and the arms that were already at ready | the `[biarm] ... park` rows (`FRUIT_BIARM_PARK_TRACE=1`) |
| **E7** | **starved polls** per arm (`no eligible fruit`), and whether any *slot* was lost | 186 `retries`, p80lib `pending_slots` |
| **E8** | `s/attempt`, the `[biarm]` summary line, the per-arm attempt counts and placed counts | `[stats]` / `[biarm] ... pipelined slots` |
| **E9** | **the aborted-leg audit**: per trip the leg, the tick, `clean_slip`, `sep`/`gap`, `force`, `contacts`, `onset_row`/`loss_row`; and **every placed attempt's** `ticks=X/X` + `clean_slip_max` | `[fail-fast]` + `[carry]` rows |
| **E10** | `[cycle]` decomposition by arm (which block the abort removes) | `[cycle]` rows |
| **E11** | **wall**: `wall/pick`, `wall/sim`, and the placed/min wall rate | the `.stamps` stream |

Definitions fixed here: a **placement** is the attempt's `t1`; the **placement
window** is `t_last_place - t_first_place` (the steady-state rate is
`60 / pooled_interval_mean` — one statistic, P3's identity); the **batch span**
is `t_last_end - t_first_start`; **wall** is `[run] attempt 0` -> `[fruit] DONE`
on the stamp stream (**reported, never gated** — harness cost, P80 §6).

**Wall is read within this batch only.** P82's wake-on-request ships default on,
so the two-line's wall/sim is ~1.69 here against P80's recorded 2.57; a wall
number compared to P80's column would be two different harnesses, not two arms.

## 5. Guards (all must pass for a positive reading)

| # | guard | test |
| --- | --- | --- |
| **G1** | **the tracker and the park trace are neutral on the two-line**: the control's `[fruit]` stream equals P80's record's **modulo `[fruit] [carry]` rows** | `logs/p82/p82_report.py --same` after dropping `[fruit] [carry]`: `D5` vs `logs/p80/T20.log`, `D6` vs `logs/p80/T6.log` |
| **G2** | **in-batch prefix identity** — the treatment equals the control up to its first trip | the `[fruit]` streams of `D5`/`F5` share a prefix that ends exactly at `F5`'s first `[fail-fast]` trip (and `D6`/`F6`) |
| **G3** | **no new failure reason** — the treatment's reason set is a subset of the control's ledger, and every aborted attempt scores the class the run-out would have scored | p80lib `reasons` + the per-arm class split |
| **G4** | **the abort only fires on a lost payload** — every trip reads `force = 0.00 N` **and** `contacts = 0` at the trip tick, with `clean_slip >= 150 mm`; and the trip rows prove the knob is **live on the two-line** (the worker's path inherits it) | E9 |
| **G5** | **no placed leg is shortened** — every carry leg of every **placed** attempt reads `ticks = X/X`, and the worst placed-leg `clean_slip_max` is far below 150 mm (P83's corpus: 76.3 mm is the worst ever) | E9 |
| **G6** | **the two-line motion gate** — `scripts/190_twoline_gate.sh` against a reference of the **same attempt count** (`logs/p80/motion_reference_twoline_p80_20.json`, 20 attempts) with the two-line floor: the **control must PASS** (fingerprint matches + rate at/above the floor). The **treatment is its own attractor** (the abort re-times the presentation — R0), so it is gated on **budgets only** (`105`, no fingerprint) and its `190` DIFFER is recorded, not read as a break | `190`, `105` |
| **G7** | **no wedge, nothing lost** — each arm completes (`attempts = placed + failed`, `diverted` reported), the driver exits 0, no retry storm | `[stats]`, driver logs |
| **G8** | **the worker's abort path is the one it already handles** — an aborted attempt prints its `[biarm] result ...` row like any failed attempt, the arm is parked afterwards (`[biarm] ... park` row or an immediate-return park), and the *next* attempt on that arm is a normal (unaborted unless it also fails) attempt | the `[biarm] result` + park rows around each trip |

## 6. Decision rule

The **mechanism must hold first** (it is branch-free):
* **M1** = **G4 + G5** (every trip is on an empty pinch; no placed leg shortened), **and**
* **M2** = the **failed attempt's own span (E3) falls >= 3.0 s** against that
  seed's control, **at both seeds** (P83 measured -5.144 s at both), **and**
* **M3** = **G1, G2, G3, G6, G7, G8**.

**ADOPT (recommendation only — this phase changes no default)** iff M1-M3 hold
**and**
* **T1** the **pooled interval mean falls >= 3 % at both seeds** and **>= 8 %
  pooled** over the two seeds (§2 predicts -7.6 % / -18.5 %, pooled -13.6 %), **and**
* **T2** the **mean per-arm idle fraction (E4) falls at both seeds** — the
  phase's own hypothesis: the freed time becomes occupancy, not belt waiting, **and**
* **T3** placed/min improves on **both sim denominators** at the pooled level
  (window **and** batch), and the **wall** rate does not fall by more than 5 %.

Otherwise: **not adopted**, and the phase publishes the mechanism (M1/M2), the
interval pair, the idle/lock-on/park decomposition and the reason it fell short.

**Falsifiers** (the phase still reports; the reading is qualified):
* **F1** — G1 fails on a control: the tracker or the park trace **is** a control
  input on the two-line. Then the A/B is *instrumentation + abort*, no
  cross-arm time claim is made, and only M2 is published (the instrument itself
  is the finding — AGENTS §2).
* **F2** — G2 fails *before* any trip: instrumentation moved the branch; F1's
  verdict applies.
* **F3** — no trip at all in a treatment arm: the knob is inert on that branch,
  the arm is reported as `0 trips` and **no time claim is made from it** — the
  phase would then need the failure class the two-line actually draws.
* **F4** — G4 fails on one leg (a live pinch tripped): the threshold is
  inadmissible for this scenario and the form fails.
* **F5** — G5 fails on one leg (a placed leg shortened): the form fails, full
  stop.
* **F6** — G3 fails (a new reason text): the form fails (the class must be the
  outcome, not the abort).
* **F7** — a run wedges (renderer freeze) or exits non-zero: re-run once; a
  second failure is recorded as a missing arm, never inferred.

## 7. Read rules (binding)

* **R0 — the abort moves the branch, and that is registered.** The freed sim
  seconds are seconds the belt keeps moving, so after the first trip the
  treatment is a different scenario: **the count is a draw**, and so is any
  per-class rate (P83 R0/R1). The claims are the **time** (E1-E4) and the
  **per-attempt mechanism** (E3, E9).
* **R1 — quote `placed/min wall`, never `wall/pick` alone.** A run that places
  fewer divides a much smaller wall by a smaller count and reads faster per pick
  (P83 §5).
* **R2 — both denominators, always.** A rate without its denominator is a
  defect.
* **R3 — the trip is the pair** (`clean_slip >= 150 mm` **and** `force = 0.00 N`
  with `contacts = 0`). The slip alone is a norm and says nothing about the
  pinch.
* **R4 — read the cut off the leg's own row** (`[carry] ticks=<trip>/<total>`)
  and the attempt's own `[run]` span; never infer it.
* **R5 — two seeds, same-direction.** A seed-5-only reading is a sample, and the
  two-line's count is a known seed draw (P80 §7b: 1.27x then 0.73x).
* **R6 — the failed-attempt span is the mechanism; the interval is the claim.**
  They are reported separately and never merged.

## 8. What is NOT run, and why

* **No threshold ladder.** 150 mm is P83's corpus-justified value; a second value
  would be a dose-response on a separation already measured.
* **No third seed.** The registration is 5 and 6 (P80/P81's pair). A third seed
  is the named spend if the two disagree.
* **No grip lever, no supply lever, no speed cell.** The `cnp` class is closed
  (`logs/p42/SIM_LIMIT.md`); the supply's density and the speed union are
  measured (P1c, P44, P46, P51, P80).
* **No direct/policy arm.** `FRUIT_FAIL_FAST` resolves off there by construction
  (the direct handover owns the P10-C monitor), and the hybrid canary never
  reaches it.
* **No default change, no commit, no `src/` edit, no `configs/` write.**
