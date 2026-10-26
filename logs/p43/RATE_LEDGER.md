# P43 phase 1 — RATE_LEDGER: the current per-phase ledger, and what is still open

Measured **offline** 2026-10-26 (no simulator, no `src/` edit, no commit).
Tree: HEAD **`53e5ccf`**, `tasks.py` **`e2d0f12a`**, `rl_env.py` **`50980bf5`**,
`control.py` **`9384ff4f`** (the P41 `finger_damp02` profile shipped),
`scene.py` `27e3d64a`, `policy/runtime.py` `379ac706`, `policy/trigger.py`
`b09d3cb2`; `configs/motion_reference.json` **`8a399626`**,
`configs/motion_reference_twoline.json` **`2246f83c`**.

Reproduce every number below with

```bash
python3 logs/p43/ledger_census.py > logs/p43/ledger_census_out.txt   # ~1 s, reads logs only
python3 logs/p43/ledger_census.py --log <file>                      # one battery
```

The script prints, per battery: attempts / placed / the `[stats]` (or `[biarm]`)
sim span / `s/attempt` / `placed/min` / the retention-free ceiling / the
retention tax / the three wait-and-motion rows / the re-seat row count / the
`[cycle]` decomposition with its own pairing check (the worst segment-sum vs the
row's `total=` is **0.02 s** over every battery here).

**Two reading rules that the tables below obey, both from `AGENTS.md` §2:**

1. **A success count is one draw of an attractor, not a rate.** Every battery
   here is one branch; the *rate* columns (`placed/min`, `s/attempt`) are
   monotone transforms of the count when the attempt count and the cadence are
   fixed (`60 x placed / span`). The rate evidence is the per-leg numbers (the
   waits, the spans, the `[cycle]` blocks) and the same-attempt mechanisms.
2. **The two-line's `s/attempt` is not a cycle time.** It is the batch sim span
   (both arms concurrently) divided by the attempt count; the per-arm cycle is
   **15.0-15.3 s** on every branch. Compare lines by `placed/min`, never by
   `s/attempt`.

---

## 1. The ledger (current tree)

### 1.1 The scripted lines, in sim time

| battery | log | attempts | placed | sim span | s/attempt | placed/min | ceiling | tax | `[cycle]`? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **single arm, acceptance** (default) | `logs/p41/p2/accept_profile.log` | 10 | **6** (60 %) | 150.5 s | **15.05** | **2.39** | 3.99 | 40.6 % | no |
| single arm, acceptance (P42 seat instrument on) | `logs/p42/p2/seat_accept.log` | 10 | 6 | 150.5 s | 15.05 | 2.39 | 3.99 | 40.6 % | no |
| **single arm, pear** (species-locked) | `logs/p41/p2/pear_profile.log` | 10 | **6** (60 %) | 157.1 s | **15.71** | **2.29** | 3.82 | 39.8 % | no |
| single arm, pear (seat instrument on) | `logs/p42/p2/seat_pear.log` | 10 | 6 | 157.1 s | 15.71 | 2.29 | 3.82 | 39.8 % | no |
| **two-line, dense sheet** (default branch) | `logs/p41/p2/twoline_profile.log` | 10 | **8** (80 %) | 98.0 s | **9.80** | **4.90** | 6.12 | 17.6 % | **yes** |
| two-line, dense (P40 regrasp flip, pre-P41 profile) | `logs/p40/p3/regrasp2_twoline.log` | 10 | 7 (70 %) | 88.2 s | 8.82 | 4.76 | 6.80 | 26.6 % | yes |
| **two-line, bed** (20 attempts) | `logs/p32/A0_bed_twoline_1.log` | 20 | **12** (60 %) | 171.8 s | **8.59** | **4.19** | 6.98 | 37.7 % | yes |
| seek-and-sort reference (Gate-19 era, v7 supply) | `logs/g/20_rate_single_1.log` | 10 | 9 (90 %) | 158.1 s | 15.81 | 3.42 | 3.80 | 10 % (1 of 10; the log prints no per-attempt span) | yes |
| **hybrid policy canary** (fixed pre-v9 supply) | `logs/p41/p4/accept_policy_profile.log` | 10 | **7** (70 %) | **not printed** | **~74 s/ep of wall** | **0.57 of wall** | — | 3 of 10 (2 grip loss + 1 station escape) | no |

**The canary's row, stated in its own units.** The hybrid evaluator prints **no
sim span and no `[cycle]` marks** — it is the harness's handoff loop
(`60_eval_policy.py`), not the scripted task — so its `s/attempt` and
`placed/min` exist only in **wall** time: **740.5 s for 10 episodes = 74
s/episode**, 0.57 placed/min of wall. Its 3 losses are **2 grip losses + 1
pick-station escape** (`fruit left the pick station during the close
(1416 mm)`), i.e. the same carried/grip family, and the escape is a **new failure
reason** against the recorded baseline (the gate FAILs on that clause only,
`logs/p41/p4/accept_policy_claim.log`). The W3-supply canary, for the wall trend,
reads **1/10 in 1 020.1 s = 102 s/episode** (`logs/r5/30_canary_w3supply.log`).

**Which is the default branch, and why it matters.**

* The shipped single-arm default is `accept_profile.log`'s configuration (the
  P41 finger profile, the P40 path-scoped regrasp cap, the P32 pear-on supply).
  Its gate reads **6/10, rate-only FAIL (75 % floor), `fingerprint: matches
  configs/motion_reference.json` (8a399626)** — re-run for this ledger with
  `scripts/105_motion_regression.py`. The 6/10 is the documented post-P32
  branch; it is not a regression of anything in P40-P42.
* **`logs/p42/p2/seat_accept.log` and `seat_pear.log` are the same branch as the
  P41 pair**: dropping the `[seat]` rows, the filtered `[fruit]` streams are
  **457/457** and **458/458 IDENTICAL** (`grep '\[fruit\]' | grep -v '\[seat\]'`).
  So the current tree's single arm and pear are exactly the P41 numbers, and the
  P42 seat instrument is print-only on this pair.
* The **two-line default branch is `twoline_profile.log`** (the P41 profile, the
  dense wave sheet, the P40 regrasp flip): `scripts/190_twoline_gate.sh` reads
  **PASS** with `fingerprint: matches configs/motion_reference_twoline.json`
  (2246f83c). `logs/p41/p3/twoline_mf30.log` is a **moved branch**
  (`FRUIT_FINGER_MAXFORCE=30`, not adopted, `logs/p41/P3_RESULTS.md` §2) and is
  **not** a ledger row.
* **The bed's row is stale on two axes.** The last bed battery is **P32
  (2026-10-22)**: it predates both the P40 regrasp flip (it prints **22 re-seat
  rows in 20 attempts**, i.e. many `k=3` attempts the flip now caps at 2) and
  the P41 drive profile (4.4 N → 9.8-9.9 N). **No post-P41 bed run exists**
  (`grep` over `logs/p40/p3`, `logs/p41/p2`, `logs/p41/p3`, `logs/p42/p2`,
  `logs/p42/p3`: none). Its current-tree rate is **unmeasured** — §4.4.

### 1.2 The same rows in wall time (what a batch costs)

The app wall is the log's own `Simulation App Shutting Down` timer (one app per
battery, startup included).

| battery | sim span | app wall | sim / wall | placed/min of **wall** |
| --- | --- | --- | --- | --- |
| single arm acceptance | 150.5 s | 274.5 s | 0.55 | 1.31 |
| single arm pear | 157.1 s | 277.8 s | 0.57 | 1.30 |
| two-line dense | 98.0 s | 284.4 s | 0.34 | 1.69 |
| two-line bed | 171.8 s | 483.8 s | 0.36 | 1.49 |
| **direct loop** (P37, 15-ep run) | 15.2 s/ep | **27.7 s/ep** | 0.55 | 1.30 (90 placed in 4 152 s of episode wall) |
| **hybrid policy canary** (P41, 10 eps) | not printed | **740.5 s** total | — | **0.57** |

The last two rows are wall-only quantities: the direct/policy interfaces print
no `[stats]` sim span, and a policy decision costs **24-100 ms of wall against
an 8.3 ms tick** (`logs/p40/RATE_CENSUS.md` §5). The policy's *sim* rate is not
in question here — the cycle is the scripted primitive's. **What the policy loop
costs is episodes per hour**, and the hybrid canary is **2.7x the direct
interface's wall per episode** (74 s vs 27.7 s) with no decomposition anywhere in
the logs (§4.3).

### 1.3 The retention tax (the largest single block, and it is closed)

`tax` = the share of per-arm attempt time spent on attempts that placed nothing
(`Σ span(not placed) / Σ span(all)`, the RATE_CENSUS definition); `ceiling` is
"every attempt converts, same span".

| battery | placed | tax | ceiling − realised |
| --- | --- | --- | --- |
| single arm acceptance | 6/10 | **40.6 %** | **+1.59 placed/min** (2.39 → 3.99) |
| single arm pear | 6/10 | 39.8 % | +1.53 (2.29 → 3.82) |
| two-line dense (default) | 8/10 | 17.6 % | +1.22 (4.90 → 6.12) |
| two-line bed (P32) | 12/20 | 37.7 % | +2.79 (4.19 → 6.98) |
| Gate-19 single-arm reference | 9/10 | 10 % | +0.38 (3.42 → 3.80) |

The losses are **two classes, and which one dominates is per line** — this
matters for what each ceiling means:

| battery | not placed | cnp (carried, empty note) | no-grasp (`fruit did not follow the gripper`, lift ≤ 0.004 m) |
| --- | --- | --- | --- |
| single arm acceptance | 4 | **3** | 1 |
| single arm pear | 4 | **4** | 0 |
| two-line dense (default) | 2 | 0 | **2** |
| two-line bed (P32) | 8 | 1 | **7** |

So the **single arm's** ceiling is the carried-not-placed class, i.e. the
documented sim limit (`logs/p42/SIM_LIMIT.md`: the pads hold and the payload
slides — loaded slide — at 2.2x force, at every face shape, every squeeze depth,
and with the seat centred to 1.4-4.6 mm). The **two-line's** ceiling is the
**no-grasp** class (its two dense failures lift ≤ 0.002 m with
`fruit did not follow the gripper`, i.e. never held) — a **different mechanism**
from the loaded slide, screened on the two-line itself in W5-C (five
configurations; every one leaves the left class alive) and therefore also not an
open lever. **Neither ceiling is a lever in this phase**, and the `grip` retry
block (3.71-5.14 s on failed attempts) is inside the failed attempt, not a
separate saving. On the single arm the cnp half is **one lane**: the P33 census
reads the left lane **14/60 placed with 33 cnp** and the right **48/48** —
counts, not rates, because the 60 left attempts pool five branches over two
supply schedules (`logs/p33/51_phase2_read.md` §1.2).

---

## 2. The `[cycle]` decomposition

The single-arm acceptance carries **no** `[cycle]` marks, so its cycle is only
known from the Gate-19 reference (`logs/g/20_rate_single_1.log`). The two-line
rows are current-tree.

### 2.1 Single arm, `logs/g/20_rate_single_1.log` (10 attempts, 9/10, 15.81 s)

| phase | s | share | placed | not placed |
| --- | --- | --- | --- | --- |
| prepose | 0.88 | 5.5 % | 0.88 | 0.88 |
| hover | 0.74 | 4.7 % | 0.74 | 0.75 |
| **descent (net of the handover wait)** | **2.92** | **18.4 %** | 3.44 | 3.57 |
| close | 1.34 | 8.4 % | 1.18 | 2.77 |
| grip | 2.03 | 12.8 % | 1.58 | **6.07** |
| lift | 1.88 | 11.8 % | 1.81 | 2.46 |
| **place** | **3.09** | **19.5 %** | 3.09 | — |
| release | 2.31 | 14.6 % | 2.31 | — |
| return | 0.65 | 4.1 % | 0.65 | — |
| end | 0.03 | 0.2 % | 0.00 | 0.33 |
| **total** | **15.81** | 100 % | 15.81 | 15.81 |

Inside the descent segment, **71-74 % is waiting**: the arrival wait
(`fruit at pick point … after N steps`) plus the handover wait
(`dynamic descent: waited N ticks`). Current-tree arrival waits (mean / median):

| battery | arrival wait | handover wait | approach motion |
| --- | --- | --- | --- |
| single arm acceptance | **1.28 s / 1.10** | 0.65 s | 0.75 s |
| single arm pear | **1.80 s / 1.82** | 0.64 s | 0.75 s |
| two-line dense (default) | **1.96 s / 2.10** | 0.54 s | 0.74 s |
| two-line dense (P40 flip, pre-P41 grip) | 1.58 s / 1.47 | 0.57 s | 0.74 s |
| two-line bed (P32) | 1.55 s / 1.60 | 0.64 s | 0.75 s |
| Gate-19 single-arm reference | 2.00 s / 2.00 | 0.54 s | 0.73 s |

So the **arrival wait is 1.10-2.10 s per attempt and 7-13 % of the whole span** —
the largest named block after place+release, and pure waiting for the belt. The
P40 R-S lever (nearest-above-floor) is the only measured lever that touches it
(§4.1).

### 2.2 The two-line default branch, `logs/p41/p2/twoline_profile.log` (10 attempts, 8/10)

| phase | mean s | share | n rows | placed | not placed |
| --- | --- | --- | --- | --- | --- |
| prepose | 0.71 | 4.4 % | 10 | 0.71 | 0.71 |
| hover | 0.76 | 4.7 % | 10 | 0.76 | 0.77 |
| descent (net of the handover wait) | 2.88 | 18.0 % | 10 | 3.24 | 4.12 |
| close | 1.36 | 8.5 % | 10 | 1.20 | 2.00 |
| grip | 2.29 | 14.3 % | 10 | 1.93 | **3.71** |
| lift | 1.80 | 11.3 % | 10 | 1.75 | 2.04 |
| place | 3.21 | 20.1 % | 8 | 3.21 | — |
| release | 2.30 | 14.4 % | 8 | 2.30 | — |
| return | 0.67 | 4.2 % | 8 | 0.67 | — |
| end | 0.02 | 0.1 % | 10 | 0.00 | 0.09 |
| **total** | **15.29** | 100 % | | | |

`place` and `release` are only printed on attempts that reach the output line,
so they are averaged over the rows that carry them (8 of 10 here) — the `n rows`
column is that count, and it is why the "all" column is not a sum over 10.

**The regrasp flip is visible exactly where P40 said it would be**: `[cycle] grip`
on the same two-line supply reads **3.39 s on the P39 control** (pre-flip,
`logs/p39/p3/twoline_C.log`, `logs/p40/RATE_CENSUS.md` §1.1) → **2.39 s** on
`regrasp2_twoline.log` → **2.29 s** on the P41 profile, and the re-seat rows
**13 → 5 → 5**. That is ~1.0 s of mean grip on a 15 s arm cycle, from a shipped
change, already in the ledger.

### 2.3 The bed, `logs/p32/A0_bed_twoline_1.log` (20 attempts, 12/20)

| phase | mean s | share | placed | not placed |
| --- | --- | --- | --- | --- |
| prepose | 0.71 | 4.4 % | 0.71 | 0.71 |
| hover | 0.79 | 4.9 % | 0.77 | 0.82 |
| descent (net) | 2.41 | 14.8 % | 2.94 | 3.20 |
| close | 1.29 | 7.9 % | 1.22 | 1.41 |
| **grip** | **3.13** | **19.3 %** | 1.79 | **5.14** |
| lift | 1.96 | 12.0 % | 1.69 | 2.36 |
| place | 2.94 | 18.1 % | 2.94 | — |
| release | 2.36 | 14.5 % | 2.36 | — |
| return | 0.66 | 4.0 % | 0.66 | — |
| **total** | **14.51** | 100 % | 15.07 | 13.68 |

The bed is the **most grip-bound** branch in the ledger: `grip` 3.13 s mean,
**5.14 s on its not-placed attempts** (the `k=3` retry class), and 22 re-seat rows
in 20 attempts. Two of the three terms that produced that are now shipped
changes (the regrasp cap, the drive profile) — hence §4.4.

---

## 3. The closed blocks (one line each; do not re-open)

| block | measured | where |
| --- | --- | --- |
| place geometry (distance) | the safe shift is ~30 mm ≈ 0.2 s = 1.3 % of the span; 45.1 → 36.1 cm collapses the rate 90 % → 30 % | P3, `AGENTS.md` |
| place profile (speed) | already swept, 0.35/1.089 is the Gate-19 winner (place 5.64 → 2.85 s) | `logs/fast/sweep_iso_p035*` |
| lift profile | 0.20/0.25/0.30 → 8/8/9 of 10 | `tasks.py:2907-2909` |
| supply density | flat cadence across D = 1.00-2.00, class-standardised flat; negative on a single-species pool (65 % → 17-30 %) | P1c, `logs/p1c/PREREGISTRATION.md` |
| belt speed | 0.15/0.18 a wash | R3 §4 |
| control cadence | 30 Hz of sim time by construction (`_step % 4`, chunk 4 of a 16-action prediction) | `rl_env.py:2231`, RATE_CENSUS §5 |
| hot-arm residency / prefetch / adaptive lead | 3.41 vs 3.63 placed/min (worse); 0/40 reservations; bit-identical | R3, W6-C |
| retention class (force/seat/grip) | 2.2x force, every face, every depth, compliant body, centred seat — the class persists | `logs/p42/SIM_LIMIT.md` §1-§2 |
| the descent's 40-90 mm boundary shortfall | reach-band property, every descent ends short; do not re-tune the budget | `AGENTS.md` §2, `logs/160/161` |
| the lateral-refusal tail | 0.06 % of episodes, unmeasurable at this N | P38 |

---

## 4. What the ledger says is left

Ranked by **expected value per hour of machine time**, with the measured size of
each block. The retention tax is excluded: it is the largest block (+1.59
placed/min on the single arm) and it is **closed** — no phase may spend on it
except via a new pad asset or a real-jaw anchor (`SIM_LIMIT.md` §4).

### 4.1 `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` as a **scoped** default — the one measured wait lever

* **Measured (P40 R-S, `logs/p40/P3_RESULTS.md` §R-S)**: the arrival wait
  **1.41 → 0.97 s** mean (1.20 → 0.63 median), the attempt span 15.01 → 14.64 s,
  `s/attempt` **15.0 → 14.6 (-0.4 s, 2.7 %)**, placed 6 → 7, **no new failure
  reason**, all three falsifiers pass. The commit distance reads **~0.553 →
  ~0.501 m against a 0.399 m floor**, i.e. the rule still leaves **0.10-0.15 m**
  of margin above the shipped selection floor — it does **not** spend the margin
  the v9 pre-fix collapse needed.
* **The scope problem (and it is the whole cost)**: the knob sits on
  `select_target`'s single-arm return (`tasks.py:5715`), which is *also* the
  direct loop's episode rule — `rl_env.py:1703` calls
  `self.task.select_target(self.spawner.state(), reach_anywhere=False)` with no
  lane, so a default flip silently moves **every direct baseline**
  (P33/W7-C/W8-A/R9/P35/P36/P37/P38 numbers) without an A/B of its own. The
  two-line selector and the shared-station worker are structurally excluded
  (they return above that line); the **collector** is not — it drives the same
  scripted task, so a flip changes what a post-flip shard contains (precedent:
  `collection.park_early` in the shard manifest).
* **Current-tree baseline**: the acceptance's arrival wait is now **1.28 s**
  (not the P40 control's 1.41 s) and the pear's **1.80 s**, so the 0.44 s has to
  be **re-measured on this tree** before it is quoted as the current number.
* **Expected value**: 0.4 s of 15.05 s = **2.7 %** of the single-arm span; on the
  pear (1.80 s wait) the headroom is larger. **Cost ~1 h** (`PREREG_DRAFT.md` L1).
* **Measured in phase 2 and NOT adopted** (`logs/p43/P2_RESULTS.md`): the wait
  falls in 4/4 arm-pairs (-0.32/-0.35 s acceptance, -0.61/-0.73 s pear) with the
  mechanism exact to 2 ms, but the choice exists on only **20 %** of the
  acceptance's attempts (the supply delivers one floored candidate on 8/10), the
  `placed` count falls on 3/4 pairs and both treatment acceptance runs lose a
  slot to `no eligible fruit`. The knob is scoped (`select_target(...,
  direct=True)`) and ships **off**; `=1` reproduces the measured arm.

### 4.2 The policy loop's wall — measured size, unmeasured decomposition, null-to-negative priors

* **The wall, per decision**: `policy_ms` medians **23.6 / 25.0 / 52.2 / 100.0
  ms**, p90 33.3-61.2 / 115.7 (`logs/rtc/` batches; `logs/p40/RATE_CENSUS.md`
  §5). One decision is 4 control ticks = **33.3 ms of sim**, so a decision costs
  0.7-3x its own sim span in wall time: **the loop is not real-time and cannot
  be made one**.
* **The episode**: the direct loop averages **1 829 ticks (15.2 s of sim) and
  232 decisions** (`logs/p37/B_ab/A_*.log`, 75 episodes). At `execute_steps = 4`
  that is **~930 policy-stepped ticks** (a decision every 4 control ticks, i.e.
  30 Hz of sim) and **~900 ticks left to the scripted primitive**; the
  7.89 ticks/decision figure is the whole-episode average, diluted by the
  primitive. At 24-100 ms per decision the policy calls are
  **5.6-23.2 s of the 27.7 s episode wall (20-84 %)** — never measured directly
  on this tree.
* **The knobs exist and are off**: `FRUIT_RTC` (async chunk runner) and
  `FRUIT_VLASH` (`policy/runtime.py`, `RTCSettings`), both default 0.
* **Their measured rate record is null-to-negative, at other checkpoints**:
  `moe_v10` (v5-B, E1/E2/E4 RTC vs legacy = 22/21, **22/11**, 24/22 of 45; the
  E2 +24 pt is p = 0.09 and its legacy dip is one run) and `FRUIT_VLASH=1` with
  a matching fine-tune **16/45 = 35.6 % vs the base's 30/45 = 66.7 %** on
  `moe_v11` (path-3, a new failure class). The smoothness win is real and large
  (step/jerk **3-5x lower**) and **the full per-tick wall does not fall** —
  `control_ms` rises 9.5 → 33.5 ms (E2) and 9.7 → 22.5 ms (E4) because the async
  wait is paid in the control loop.
* **Expected value**: `0 placed/min of sim time`. The only thing it can buy is
  **wall per episode** (equivalently, episodes per hour) — and the prior at
  `moe_v10` is that it buys none. **Cost: 8 min to measure the pause share, and
  ~80 min for one cell** (`PREREG_DRAFT.md` L2).
* **Measured in phase 2 and closed with a number** (`logs/p43/P2_RESULTS.md`
  §5): on the shipped loop (E=4, RTC off) the registered pause share is
  **10.7 %** (< the 25 % bar → the RTC cell is not run), the model call is
  47.4 ms/decision against 33.3 ms of sim, and render+camera is 23.6 ms/decision
  (5.3 % of the episode wall) — so the loop is **primitive-bound**, not
  render-bound, and no loop lever is left.

### 4.3 The hybrid canary's 74 s/episode — large, unmeasured, and it is the gate of record

The canary is 10 episodes in **740.5 s** (P41) and **1 020.1 s** on the W3 supply
(r5) — **74-102 s per episode** for a ~10 s sort. The direct interface does the
same interface's episode in **27.7 s**. The gap (2.7x) is in the handover path
(the scripted handover/grasp primitive that runs after the policy horizon),
and **no log attributes it**. This is not a robot rate lever; it is the cost of
every policy adoption decision (a 3-run canary A/B is ~74 min). Unmeasured, and
the cheapest instrument is the same `FRUIT_RTC_REPORT` run as §4.2 plus the
already-printed `[eval]` per-episode rows.

### 4.4 The bed's ledger row is stale on two axes

Last run **P32 (2026-10-22)**: 12/20, 4.19 placed/min, **37.7 % retention tax**,
`grip` **3.13 s** mean / **5.14 s** on failures, **22 re-seat rows in 20
attempts**. Since then the shipped tree changed the retry cap (P40: 3 → 2 on the
dynamic line, measured 1.42-1.52 s per capped attempt) and the finger drive
(P41: 4.4 → 9.8 N at 1.00x wall). The bed is the branch with the **most `k=3`
attempts in the corpus**, so it is the branch where the P40 flip should show the
most — and **nobody has run it**. Its current-tree rate, its `grip` block and its
retention tax are all unmeasured. **Cost: one 20-attempt battery (8 min wall
measured) + its own reference re-record** (the bed has
`configs/motion_reference_twoline_bed.json`, `-m 0.5`).

### 4.5 The release block: 2.3 s of the two-line cycle, attributed by no row

`[cycle] release` is **2.25-2.39 s (14-16 %)** on every two-line branch and
**2.31 s** on the single-arm reference, and the only sub-row inside it is the
single arm's `place low: N ticks` (**0.68 s**) — so **~1.6 s is unnamed** (the
span relax, the dwell, the open, the 10 cm drop and its settle;
`tasks.py:11799`, `FRUIT_RELEASE_DWELL/_PAD_HOLD/_FINGER_HOLD` default
20/3/3 and already reduced). No phase has ever priced it. **Expected value
unknown, plausibly 0.5-1.5 s/attempt if a shorter release is free**; the
instrument exists (`FRUIT_RELEASE_DEBUG=1`) and the risk is the release-induced
ejection the debug flag was built to explain. **Not registered in P43** (the
phase budget is 2 levers + the park); it is the named item for a later phase.

---

## 5. What this ledger does **not** claim

* No cross-configuration rate comparison: every count above is one attractor of
  its configuration, and the P40/P41 pairs are in **moved** branches.
* No claim that the policy's wall is a rate problem. The sim cycle is the
  primitive's; the wall decides how many experiments per hour fit.
* No re-opening of the retention class, the density, the place, the belt speed,
  the cadence or the seat. Those rows are in §3 with their numbers so a later
  reader does not have to re-derive that they are closed.
