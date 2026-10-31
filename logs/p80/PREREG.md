# P80 PREREG — the cell's current throughput on the shipped tree, and what the two measured throughput levers are worth on it

Registered 2026-11-01, **before any run**, on the P79-final tree (HEAD `0de4d35`,
clean worktree; `tasks.py` `e8dfa6d8`, `rl_env.py` `7d26eb5b`, `scene.py` `07d6fdad`,
`assets.py` `540406fa`, `control.py` `9384ff4f`, `fruits.py` `c7461d41`,
`conveyor.py` `fb2c58c6`, `bimanual.py` `980923a6`,
`configs/motion_reference.json` `8952c320`,
`configs/motion_reference_twoline.json` `eb697f23`).

Owner directive: the left-arm lane is **closed**; the work moves to **throughput**.
Nothing is adopted by this phase, no default changes, no commit. This is a
**measurement** phase: it establishes today's number and prices the levers
against it.

## 0. Why a baseline is owed (what moved under every earlier rate)

The shipping package changed the cell **after** the last rate measurements:

| change | what it touched | does it reach **this** battery? |
| --- | --- | --- |
| **P71** `FRUIT_OUTPUT_RAILS` `both` -> `none` | the scene's collider set, every path | **yes** — the scripted line's output station |
| **P71** `FRUIT_LIFT_DZ` direct default `+0.08` -> `-0.08` | `rl_env.LIFT_DZ_DIRECT_DEFAULT`, direct only | **no** — the scripted lift stays 0.36 m (`FRUIT_LIFT_DZ` unset = `+0.08`) |
| **P43** arm park default `back` | `SortingRLEnv` only | **no** — `20_pick_place.py` never constructs `SortingRLEnv` |
| **P58** direct supply profile | `SortingRLEnv._resolve_supply_profile` only | **no** — the scripted spawner reads the raw env defaults |

So the **only** shipping change inside this battery's contrast is the **rails**.
The last scripted throughput numbers are P44's (`logs/p44/p2/`, 10 attempts,
seeds 5/6, pre-P71), and the last two-line number is `logs/p71/twoline/none.log`
(10 attempts, **one draw**: 7/10, 9.2 s/attempt, 4.54 batch / 5.93 window
placed/min). The lift/park/supply flips are **not** re-measured here; they are
direct-line levers and this battery is scripted. Stated here so the report cannot
imply otherwise.

## 1. Arms

Every run: `HEADLESS=1`, **`ATTEMPTS=20`**, **`SEED=5`**, one
`scripts/154_claim_run.sh` claim (one simulator), and the **same instrumentation
set on every arm**: `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1` (the P44
convention; both are proven run-neutral on these scenarios — P44's batch header
carries the byte-identity evidence). The scenario is the **shipped** one: no
`FRUIT_SUPPLY_PATCH`, no `FRUIT_SUPPLY_GRADES`, no knobs.

| arm | env on top of the set above | what it is |
| --- | --- | --- |
| **S** | — | the shipped single arm |
| **T** | `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1` | the two-line (opt-in; **its first measurement on the shipped tree**) |
| **U** | `FRUIT_SPEED_ALL=1` | the single arm on P44's speed union (place 0.52 / release dwell 0 / lift 0.36) |
| **V** | `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SPEED_ALL=1` | the two-line on the same union — **only if U holds up** (§4 R2) |

Order: **S5, T5, U5**, then V5 if licensed, then the seed-6 pair (§4 R3).

### The two 10-attempt gate arms (the math makes this unavoidable)

`scripts/105_motion_regression.py`'s fingerprint is the **per-descent**
`(samples, |v|max)` list, so a 20-attempt log **cannot** match a 10-attempt
reference. The motion gates are therefore run on the standard 10-attempt
batteries, in the same session:

| gate arm | command | gate |
| --- | --- | --- |
| **G-S10** | `SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p80/S10.log scripts/accept.sh` (10 attempts, seed 5, `FRUIT_MOTION_REPORT=1` exactly as shipped) | `105 … --fingerprint configs/motion_reference.json` — must read **`matches`** |
| **G-T10** | 10 attempts, seed 5, `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, `FRUIT_MOTION_REPORT=1` | `scripts/190_twoline_gate.sh` (default ref `configs/motion_reference_twoline.json` `eb697f23`, floor 0.60) — **record what it reads**; a mismatch is *not* forced into a match |

The 20-attempt arms get their **budgets** judged (`105 … ` with no
`--fingerprint`) and the two-line 20-attempt arm gets **its own** reference
written to `logs/p80/motion_reference_twoline_p80_20.json`
(`--write-fingerprint`) so V20 can be gated against T20 as an
import/branch guard. **The shipped `configs/` files are never overwritten.**

## 2. Endpoints (the metric set is the record's, W6/P33)

Pre-registered **first** because a success count across arms is a count across
attractors (AGENTS §2): the primary reading is **time**, not counts.

| # | endpoint | source |
| --- | --- | --- |
| **E1** | per-attempt span `s/attempt` (and the per-arm median) | `[stats]` / `[run] attempt` rows |
| **E2** | **inter-placement interval**: per-arm and **pooled**, mean / p50 / p90 | `scripts/186_w6_report.py` |
| **E3** | **placed/min** by the **placement window** and by the **batch span** — *both printed, never mixed* | 186 |
| **E4** | **lock-on** (previous attempt end -> station acquired), with retries | 186 (two-line arms; the single arm has no acquisition line) |
| **E5** | **idle fraction** per arm | 186 |
| **E6** | `[cycle]` block decomposition (prepose/hover/descent/close/grip/lift/place/release/return/end) | 186 (+ `FRUIT_CYCLE_REPORT=1`) |
| **E7** | class split: per-arm grasp/place classes and the first failure reason per attempt | 186 + a P80 script |
| **E8** | **wall vs sim**: process wall per attempt, the batch sim span, and the wall/sim ratio over the same interval | `logs/p80/*.stamps` (per-line elapsed) + `[stats]` |
| **E9** | the motion gates | §1 |

**Definitions fixed here** (so the number cannot drift after the fact):
* a **placement** is the attempt's `t1` (the `[run]` window's end) — 186's
  convention, identical for both arms;
* the **placement window** is `t_last_place - t_first_place`; the **batch span**
  is `t_last_end - t_first_start`; a rate quoted without its denominator is a
  defect;
* **wall** is the per-line elapsed stamp's `[run] attempt 0` start to
  `[fruit] DONE`, and the **sim** figure over the same interval is the batch
  sim span; the ratio is reported, **never gated** (it is harness cost);
* a **starved slot** (`no eligible fruit`) is a lost slot and stays in the
  denominators (it is what the two-line's park-and-wait exists to avoid).

## 3. Read rules (binding)

* **R0 — no cross-arm counts as a rate.** A placed count is one draw of a
  deterministic branch; two arms in different attractors are different
  scenarios. The **interval/time** endpoints are the claim; counts and class
  splits are **reported**, and the *mechanism* is quoted with them.
* **R1 — the union's claim is the interval/time, never the count** (P51: its
  cost is the closed `SIM_LIMIT.md` grip class, so a count difference is
  expected and is not the lever's verdict).
* **R2 — V is only run if U pays.** Licensing: U's `s/attempt` falls
  **>= 1.0 s** below S's (P44's registered E1 bar) **or** U's pooled interval
  mean falls **>= 10 %** below S's. Otherwise V is not spent and the record says
  so.
* **R3 — the second seed.** For whichever arm's **interval** moves most against
  S, the **same seed-6 pair** is run (that arm at `SEED=6` **and** S at
  `SEED=6`), because P46 measured that the union's two-line gain did not
  replicate at a fresh seed and P74/P76/P78/P79 re-learned one seed is not a
  direction. A seed-5-only reading is labelled a **sample**, not a direction.
* **R4 — instrumentation is inside the contrast.** All 20-attempt arms carry the
  identical instrumentation set; the gate arms carry exactly the shipped
  instrumentation (the acceptance's and `190`'s own commands) so the fingerprint
  comparison stays valid.

## 4. Decision rules (the one table the phase owes)

**(a) What is the cell's throughput today?** Read E1-E3 for S and T, on **both**
denominators, with E2's interval mean/p90. "Today" = the shipped single arm
(S); T is the opt-in alternative.

**(b) Is the two-line worth defaulting now?** The standing bar is **1.25x
placed/min** on the **placement-window** denominator (W1 met it once at 1.29x;
the dense sheet did not at 1.19x; R5 kept it opt-in). **DEFAULT = yes** iff

1. `T.window_placed_per_min / S.window_placed_per_min >= 1.25`, **and**
2. T's placed count is non-inferior (`T.placed >= S.placed - 1`), **and**
3. the seed-6 pair does not invert the ratio below 1.25 (`2` above is not a
   direction at one seed).

Otherwise **keep opt-in** and publish the measured ratio, the interval pair and
the mechanism. A ratio met at seed 5 only is published as **"one sample meets
the bar"**, never as a default recommendation.

**(c) Does the speed union still pay with the rails gone?** **PAYS = yes** iff
U's `s/attempt` falls **>= 1.0 s** below S's **and** the pooled interval mean
falls (not just the per-attempt span, which also shrinks through fewer
re-attempts). Counts reported per R1. If it pays, V tests whether the two-line
inherits it (reported, not a separate adoption).

**(d) The wall/sim split** is reported for every arm: `wall/pick`,
`sim/pick`, and `wall/sim`. It is a harness fact, not a gate — and it bounds
what a *sim-time* speed lever can ever return to the operator.

## 5. Falsifiers / things that would make this phase void

* **F1** — G-S10 does not read `fingerprint: matches` against `8952c320`.
  Then the shipped scripted branch has moved since P71 and the 20-attempt arms
  are measured on an unrecorded branch: the phase still reports, but **no
  cross-arm time claim is made** until the branch is named (the run is then
  archived and a re-record proposed, not performed).
* **F2** — a run wedges (renderer freeze) or exits non-zero: the arm is
  re-run **once**; a second failure is recorded as a missing arm, never
  inferred.
* **F3** — the two 20-attempt arms of a pair differ in *instrumentation* (not
  possible by construction, checked against the header) or in scenario env
  other than the arm's own knob: the pair is void.
* **F4** — the two-line arm's own 20-attempt reference cannot be written
  (a motion-budget failure): then V20 has no gate and the record says the
  gate is **budgets-only**.

## 6. What is NOT run, and why

* No supply change (P33/P58/P59 measured the density/band profile: the cadence
  is flat across the ladder and the binding term is the per-attempt span).
* No place/lift/release retiming beyond the registered union (P44's S1/S2/S3
  cells were priced; P46/P51/P74 closed their cost class).
* No policy, no store, no checkpoint, no `configs/` write, no commit.
* No `FRUIT_*` default change: every arm is env-only, and the shipped path is
  proven byte-inert by the G-S10 acceptance replay.
