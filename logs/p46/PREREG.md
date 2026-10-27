# P46 phase 1 — PRE-REGISTRATION: the P44 speed union, two-line-scoped

Written **2026-10-27, before any P46 battery run** (the gate is on this file, not
on the result). Phase 1 is measurement only: **no `src/` edit, no `configs/`
change, no commit.** The union exists in the tree already (`FRUIT_SPEED_ALL=1`,
P44, `tasks.py` `b6de439c`); this phase measures it on the two-line at **two
seeds** and decides whether the two-line-scoped default is implemented in
phase 2.

Prior of record: `logs/p44/P2_RESULTS.md` §4/§6/§9, `logs/p44/CAP_CENSUS.md` §2/§4,
`logs/p45/P2_RESULTS.md` (the mass negative: the two-line/speed union's speed is
the cells', mass buys 0.0-0.1 s). Two-line prior, **one seed, one draw**,
`logs/p44/p2/twoline_s5_{C,S13}.log`:

| seed 5, two-line, 10 attempts | C | union |
| --- | --- | --- |
| placed | 8/10 (left 4/5, right 4/5) | 8/10 (left 4/5, right 4/5) |
| batch span / `s/attempt` | 98.0 s / 9.80 | 87.5 s / **8.70 (-1.10 s)** |
| pooled inter-placement interval | 9.13 s mean / 8.10 p50 | 8.27 s / 4.90 |
| throughput batch / window | 4.90 / 6.57 placed/min | **5.49 / 7.25 placed/min (+12 %)** |
| grip guard | 2 notes (`grasped=False`), 0 load losses | 2 notes, **0 load losses - the same two attempts** |
| `190` | PASS, fingerprint matches | floor PASS, fingerprint differs (moved config) |

---

## 1. The item (phase 2's change, NOT implemented in phase 1)

**The default.** `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1` resolves the speed union
(`FRUIT_SPEED_ALL=1`'s value: `place` `v_max` 0.35 -> 0.52 with `a` left at
1.089; `grasp_lift` `v_max` 0.30 -> 0.36 with `a` 1.0 -> 1.9; the release
clocks dwell 20 -> 0, pad/finger hold 3 -> 2) unless an explicit `FRUIT_SPEED_*`
is set. Resolution belongs to the same place the two-line's park default is
resolved (`_dynamic_profile` / one helper), so it is one string default, not a
new code path.

**Explicitly unchanged** (each a phrase that must be true in phase 2's diff, and
each with its own no-harm evidence):

| path | why it must not move | evidence Phase 2 owes |
| --- | --- | --- |
| the scripted **single-arm** line (`20_pick_place.py`, `accept.sh`) | it is the shipped baseline whose counts and references are the project's spine | 385+/376+ `[fruit]` lines byte-identical to `logs/p44/p2/accept_s5_C.log`; `105 --fingerprint configs/motion_reference.json` still `matches` |
| the **collector's single-arm** path (`40_collect_demos.py`, `FRUIT_BIARM` unset) | a recollected store would silently be a new branch | the collector's shard manifest pins `tasks.py`; the default resolution must print `speed=shipped` on that path (a build/manifest row), and the demo index audit stays OK |
| the **indexed / policy handover** (`60_eval_policy.py`, `accept_policy.sh`) | its `grasp_lift` is 0.18 m/s and its clock budget is mass-shaped; the cells are scripted-dynamic only (P45 §1) | `accept_policy.sh` unchanged canary is **not** run in phase 1; phase 2 states the resolution is `direct`/`handoff` = shipped and pins it offline |
| the **shared-station biarm** (`FRUIT_BIARM=1` alone) | it is a different scheduler with its own clearance/park calibration, and the union is measured only on the two-line | offline pin (the resolver's presentation input) + `FRUIT_BIARM=1` acceptance byte-identity if phase 2 claims it |

**Blast radius named now, not discovered later:** the two-line **collector**
(`40_collect_demos.py` with `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) drives the
same `run_bimanual` session and therefore inherits the flip with no env set -
exactly the W7-A park-flip guardrail. Phase 2 must record it in the shard
manifest (`collection.speed`) and must not mix a pre-P46 two-line store with a
post-P46 one; phase 1 does not collect (a store is a different spend, and the
P37/P43 record shows a remembered store is not the same object as a new one).

## 2. The battery (phase 1, this phase)

* **Scenario:** the two-line dense-sheet branch, verbatim P44 battery D:
  `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, `ATTEMPTS=10`, `SEED=5|6`,
  `HEADLESS=1` (the shipped two-line supply: `FRUIT_SUPPLY_WAVE` auto-on, the
  balanced A:B:C 0.375 mix, `FRUIT_GRADE_ROUTING` pure, the W7-A park gate auto).
* **Arms:** **C** = the shipped tree (nothing set) and **U** =
  `FRUIT_SPEED_ALL=1`. Nothing else differs.
* **Order:** one claim for the whole battery (`scripts/154_claim_run.sh`
  wrapping a `run_arms.sh`), **C -> U for seed 5, then C -> U for seed 6**
  (4 runs). One claim so no other lane can slip a simulator between the arms.
* **Instruments, identical on every arm** (AGENTS §3b: the instrument sits
  inside the contrast): `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`
  (row-neutral, P43/P44) plus `FRUIT_CARRY_DIAG=1` (E3's walk) and
  `FRUIT_PLACE_TRACE=1` (E6's landing). `CARRY_DIAG`/`PLACE_TRACE` are the P44
  amend / P45 set; neutrality is **checked, not assumed**: C seed 5's core
  stream (`[run]`/`[stats]`/`[cycle]`/`[motion]`/`[biarm]`/`[supply]` + summary)
  is diffed against `logs/p44/p2/twoline_s5_C.log`, which also re-proves the
  default-off tree. If it differs, the arms are re-run **without** the two
  added instruments before any endpoint is judged (recorded as a deviation).
* **Logs:** `logs/p46/p1/{twoline_s5_C,twoline_s5_U,twoline_s6_C,twoline_s6_U}.log`,
  `batch_header.txt` (tree + md5 pins), `driver.log`, `run_arms.sh`,
  `p46_report.py` -> `P1_report.txt`, `gates.txt`.
* **Pins of record (must hold at the end):** `tasks.py` `b6de439c`,
  `motion.py` `7f2443c1`, `control.py` `9384ff4f`, `scene.py` `27e3d64a`,
  `fruits.py` (P45 tree), `configs/motion_reference.json` `8a399626`,
  `configs/motion_reference_twoline.json` `2246f83c`, HEAD `5ed38d6`.

**Reference and floor:** the two-line gate is `scripts/190_twoline_gate.sh`
(never 105's single-arm 0.75 floor), reference `configs/motion_reference_twoline.json`,
floor **0.60**.

## 3. Endpoints (operational, per seed unless stated)

**E1 — `placed` does not fall.** PASS = `placed_U >= placed_C` in **both** seeds.
A fall of **exactly 1** in a seed is a **report** (it does not stop the phase, it
is stated in the verdict); a fall of **>= 2** is F2. Denominator is 10 attempts
per arm per seed; per-arm splits are reported because the two-line's own record
moves the left/right split between branches.

**E2 — the speed is real.** PASS = `s/attempt_U <= s/attempt_C - 0.50 s` in
**both** seeds (`s/attempt` = batch span / 10, the `[stats]` value), and the
pooled mean delta <= -0.50 s. P44 read **-1.10 s** at seed 5, so the bar is 45 %
of the prior. The placement-window `placed/min`, the batch `placed/min` and the
pooled inter-placement interval (`186_w6_report.py`) are reported beside it:
CAP_CENSUS rule 4 says the two-line's `s/attempt` is a *batch span over two
concurrent arms*, so a placed/min rise at a flat count is the throughput read,
not a rate claim.

**E3 — the guard (the pillar).** With `FRUIT_CARRY_DIAG=1` on **both** arms, the
P44 rule (§9.2), per seed:

| clause | PASS condition | role |
| --- | --- | --- |
| E3a **new grip row** | no `fruit did not follow the gripper` row in U that is a **held-then-lost** row (one where `grasped=True` at the `[run]` row) while C has none in the same seed. Every U note is classified: `grasped=False` = the pre-contact acquisition class (the shipped line's own 2.0 %/attempt, and the two-line's own 2/10 at seed 5); `grasped=True` = the W8-B carry class. | **gate** |
| E3b-i **loaded-slide legs** | `force_min == 0` leg count (U) <= (C) in **both** seeds | **gate** |
| E3b-ii **the walk** | held legs with `clean_slip_max > 50 mm` (U) <= (C) in **both** seeds | **gate** |
| E3b-iii `clean_slip_max` p50 over clean legs, and the max over held legs | reported arm-vs-control per seed; **no absolute bar** (the live value is not W8-B's offline `clean_slip`; W8-B's clean 0.02-1.43 mm / escape 17.9-957 mm separation is the offline instrument) | report |

`sep@loss`/`sep_end` and `force@onset` are reported (P41's pad-stop read: the
pads reaching their own 98 mm open stop while the payload walks out is the
loaded-slide signature).

**E4 — the motion gate on every leg.** PASS = no descent leaves its `|v|max` or
lurch budget for **any** leg of **either** arm in **either** seed (the `190`/`105`
per-leg output), the carry cone and the hand-speed counts are **reported**
(the two-line's cone is a report, never a gate: AGENTS §2 and P44 §6), and
`105 --strict-cone` is run on both arms as a **relative** report (it fails on
this scenario's control too, P44 §9.3). The `190` **rate** clause is E1's
business, not E4's.

**E5 — the gate of record.** Phase 1 records the **current** verdicts only:
C seed 5 must read `fingerprint: matches configs/motion_reference_twoline.json`
(the default-off proof); U's verdict per seed is recorded (it **differs by
construction** - the fingerprint contains each leg's `|v|max`, which is exactly
what the union moves) and is **not** a failure in phase 1. Phase 2's E5 (only if
phase 1 passes) = a two-line reference re-recorded from phase 2's own control
arm, `190` **PASS** on the union arm, plus the archive of the pre-P46 file under
`logs/p46/`.

**E6 — the release lands the payload.** `FRUIT_PLACE_TRACE=1` on both arms.
PASS = **every** trace with `release_bottom > 0` (the payload was at or above the
belt top when the pads opened) reads `on_belt=True`. A trace with
`release_bottom > 0` and `on_belt=False` is a **landing miss** (F4). Traces with
`release_bottom ~ -184 mm` / `impact 0.00` / `settle nan` are the payload lost
**upstream** of the release (P44 §9.4's reading): they are counted in the
carry/acquisition class and are **not** landing failures, but their count is
reported because it is the same fruit the E3 notes name.

## 4. Falsifiers (any one fires -> STOP, write the negative, no phase 2)

* **F1 — the grip/walk guard fails.** A new **held-then-lost** `fruit did not
  follow the gripper` row in U (E3a), or a worse walk by E3b-i/E3b-ii. Stop. The
  cells stay opt-in.
* **F2 — a count collapse.** `placed_U <= placed_C - 2` in either seed.
* **F3 — a motion budget fails** on any leg of any arm/seed (E4's first clause).
* **F4 — the release throws a payload**: any `release_bottom > 0` trace with
  `on_belt=False` (E6).
* **F5 — the single-arm stream is not byte-identical after the flip**
  (phase 2's check; not evaluable in phase 1, and it is the reason phase 2 is the
  only phase that may touch `src/`).

## 5. Decision rule (written before the run)

**Phase 2 is a GO iff** no falsifier fired **and** E2 passed (both seeds,
>= 0.50 s) **and** E3 passed all three gate clauses **and** E4 passed **and**
E6 passed (with E6 evaluable: at least one `release_bottom > 0` trace per arm,
else E6 is *not evaluable* and phase 2's registration must add a landing check
that is), and E1's outcome is "no fall" **or** "a fall of 1 in exactly one seed"
(the registered report). E5 in phase 1 is a record, not a gate.

**If any falsifier fires** the phase records the **negative**: the union stays
opt-in (`FRUIT_SPEED_ALL=1`), the two-line keeps the shipped speeds, and the
document is the honest read of why.

**If E2 misses at both seeds** but nothing else fires, the outcome is **"no flip,
no falsifier"**: the P44 -1.10 s did not reproduce at two seeds, so the cells stay
opt-in and the doc records the shrinkage (P44's stop rule: a shrinking gain is not
a reason to flip).

## 6. What this does not claim (before the numbers exist)

* **The outcome is quantized** (AGENTS §2): each configuration is deterministic
  per mode, but the union **moves the branch** (P44 §8: `diverted` flips, the
  feeder is attempt-relative), so each seed's `placed` is **one draw of an
  attractor**, and no rate is compared across branches. The two-seed design is
  the *smallest* check that a -1 collapse is not just a branch draw; **two seeds
  are not five** (WS-4.2's N), so a "no fall at 2/2 seeds" statement is
  non-inferiority-flavoured **evidence**, not a rate estimate.
* **The two-line's `s/attempt` is not a cycle time** (CAP_CENSUS rule 4).
* **The note is a closure test, not a slip test** (`tasks.py` appends it iff
  `not result.grasped`); every row is quoted with its class split.
* **Instrumentation is part of the measurement**: `CARRY_DIAG`/`PLACE_TRACE` are
  on **both** arms and their neutrality on this scenario is checked against a
  recorded no-diag log (§2), not assumed.
* **Not measured here**: the policy/direct interface, the collector's stores, the
  shared-station biarm, the clearance convention (a per-config report), and the
  single-arm cells (they stay opt-in by P44's own verdict).

## 7. Deviations (to fill after the run; empty at registration)

**Appended 2026-10-27 after the battery (this section is append-only).**

* **No protocol deviation.** One claim, C -> U inside each seed, both instruments
  on both arms, `ATTEMPTS=10`, seeds 5 and 6. The registered condition on judging
  any endpoint was met: C seed 5's core stream is **453/453 rows identical** to
  the recorded no-diag `logs/p44/p2/twoline_s5_C.log` (and U's is **446/446**
  identical to `twoline_s5_S13.log`), so no instrument-free re-run was triggered.
* **Reading note 1 — seed 5 is a reproduction, not new evidence.** Because both
  seed-5 arms are row-identical to P44's, the "two-seed confirmation" is one
  bit-identical replay plus one fresh draw. The fresh draw is the finding.
* **Reading note 2 — E3b-i is not class-specific on this scenario.** The
  registered `force_min == 0` leg counter also counts **never-held** legs (the
  pads never touch, so the leg reads 0.00 N exactly as a loaded slide does). At
  seed 6 it therefore rises 1 -> 3 on the same events F2 counts, and F1's letter
  is satisfied without its named mechanism (a loaded slide / a worse walk) being
  present. Measured outcome, hazards and the decision: `logs/p46/P1_RESULTS.md`.
