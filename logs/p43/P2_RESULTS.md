# P43 phase 2 — the rate levers: L1 (the selector's scope) and L2 step 1 (the loop's pause)

Measured 2026-10-26. **No commit.** Tree pinned at HEAD **`53e5ccf`**.

**Verdicts, one line each.**

* **L1 — the scoped `nearest-above-floor` default: the mechanism is measured
  exactly, the pre-registered gate FAILS, and the flip is NOT adopted.** The
  wait falls in 4 of 4 arm-pairs (**-0.35 / -0.32 s** acceptance, **-0.73 /
  -0.61 s** pear) and the mechanism is the along-distance conversion to 2 ms
  (the treatment's chosen fruit is nearer by 0.235 m = 1.958 s; the measured
  wait drop on that attempt is 1.960 s) - but `placed` falls on 3 of 4 pairs
  (0 / **-3** / -1 / -1), both treatment acceptance runs lose a slot to
  `no eligible fruit` (0 in either control), the pear's left cnp rises 4 -> 5 on
  seed 5, and the mechanism's **prevalence is 20 %** of attempts on the
  acceptance supply against the pre-registered **50 %**. E3 and E5 fail, the
  mechanism endpoint fails on the acceptance, so `NEAREST_ABOVE_FLOOR_SCRIPTED`
  ships **"0"** (the pre-P43 pick). The *machinery* ships: the `direct` keyword,
  the per-path default and the env override, so the measured treatment stays
  reproducible as `FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1` with no code change.
* **L2 step 1 — the pause is not material and there is no loop lever left.**
  On the shipped loop (E=4, RTC off) a decision owns **47.4 ms** of model call,
  **20.0 ms** of render and **3.6 ms** of camera against **33.3 ms** of sim; the
  registered pause share (`policy_ms/step x steps / wall`) is **10.7 %**, and
  policy+render+camera is **16.0 %** of the episode wall. F4 fires: **step 2
  (the RTC cell) is not run**. The wall is **not** render-bound (render 4.5 %,
  camera 0.8 %) and **not** the loop's: 84 % of the episode is the scripted
  primitive plus physics stepping.

---

## 1. The scope implementation (what makes the flip safe, and the F5 gate)

`select_target` gains one keyword and one named default (`tasks.py`):

```python
NEAREST_ABOVE_FLOOR_SCRIPTED = "0"          # module constant, documented
...
def select_target(..., diag=None, direct: bool = False):
    ...
    nearest_default = "0" if direct else NEAREST_ABOVE_FLOOR_SCRIPTED
    if os.environ.get("FRUIT_SELECT_NEAREST_ABOVE_FLOOR", nearest_default) == "1":
```

and `rl_env.py`'s episode selection passes the flag:
`select_target(self.spawner.state(), reach_anywhere=False, direct=True)`.

**Why the flag is needed at all**: the direct env's task runs
`_prefer_upstream=True` (`tasks.py:581` resolves it from the *scripted* mode
flag), so this unlaned call **is** the nearest rule's code path - a bare default
flip would silently re-baseline every direct store and direct A/B
(P33/W7-C/W8-A/R9/P35/P36/P37/P38). **Offline proof** (new selfcheck leg,
`scripts/224_p43_selftest.py`, the `213`/`198` stubbed-task pattern, the real
selector): the direct call keeps the farthest-upstream pick whatever the
scripted default is; the scripted call follows the constant; `=0`/`=1` win on
both paths; the `lane=`/`prefer_lane=` callers return the **same fruit** with the
env unset/`0`/`1` (three-way identity - the two-line and shared-station paths
cannot reach the rule); the AST census shows 8 `select_target` sites in
`tasks.py` (all laned, `**kwargs`-pass-through, or one-item re-checks) and 2 in
`rl_env.py` (the laned reseed probe, and the episode selection with
`direct=True`); `TASKS_MD5` follows `tasks.py`.

**F5 is a GATE and it passes, in both directions** (`110_rl_rollout`,
`--presentation direct`, 2 episodes, seed 77, `moe_v13s` `61da390a`, the
P37/W8-A patch scenario):

| arm | ep 0 selection | ep 1 selection |
| --- | --- | --- |
| unset (the new default) | apple grade C, **y = +0.642** | tomato A, y = +0.549 |
| `=0` (pre-P43) | apple grade C, **y = +0.642** | tomato A, y = +0.544 |
| `=1` (explicit) | **kiwi C, y = +0.402** | apple B, y = +0.529 |

So the default is **inert** on the direct path (ep 0 identical to the digit),
and the flag is what does it: with `=1` the same call site takes a fruit
**0.240 m** nearer. (ep 1's 5 mm is the documented non-reproducibility of the
policy loop - the same fruit, grade, bin, arm and diameter; ep 0's outcome
differs, which moves the supply.) This is the strongest form of the gate: it
shows both that the protection works *and* that it is not a dead call site.

**The other callers, and how they are scoped.**

* `40_collect_demos.py:630` and `70_record_video.py:280` call
  `task.select_target(spawner.state())` with **no lane**, so they inherit the
  **scripted** default (the same selector the acceptance uses). They are *not*
  scoped out: a flip would change what a post-flip shard contains, which is why
  PREREG L1.1 requires a `collection.nearest_above_floor` manifest field
  **before** any post-flip collection. **Not added and not needed here**: the
  flip is not adopted, so both surfaces are byte-unchanged, and no collection
  was run.
* The two-line worker (`prefer_lane=` + `station_y=`) and the shared-station
  worker (`lane=`) return above the rule - pinned two ways: the AST census and
  the **shared-station replay** (below, 331/331 identical).

---

## 2. D0 — the census, and the pre-registration written from it

One control run per battery with `FRUIT_BED_DIAG=1` (print-only; proven by the
treatment pair below). Per attempt: the usable set (candidates at/above the
catch floor), the near-vs-far along delta, and whether a choice existed at all.

### 2.1 The census (`d0_accept_A_s5.log`, `d0_pear_A_s5.log`, knob = 0)

| battery | usable set size (mean / median / max) | affected attempts (window >= 2) | along delta on the affected | along delta **per attempt** |
| --- | --- | --- | --- | --- |
| acceptance, seed 5 | **1.20 / 1 / 2** | **2/10 = 20 %** | 0.235, 0.250 (mean 0.2425) | **0.0485 m** |
| pear, seed 5 | **1.50 / 1.5 / 2** | **5/10 = 50 %** | 0.105-0.236 (mean 0.1496) | **0.0748 m** |

The acceptance's supply delivers a **single** floored candidate on 8 of 10
attempts: the shipped rule's 0.21 m over-commit (`logs/p40/ARRIVAL_SPLIT.md`) is
mostly *not* a choice, it is the only fruit in the window. The pear's band is
denser - exactly half its attempts have a choice.

### 2.2 The pre-registration (written after the census, before the treatment)

* **E1** (the pre-registered form): `E1_hat = 0.6 x (mean along drop / 0.12
  m/s)` with the drop taken **per attempt** (0 on an unaffected attempt) -
  **0.243 s** acceptance, **0.374 s** pear. Undiscounted (`drop / 0.12`):
  0.404 s / 0.623 s. Bar unchanged: E1 passes only if the measured wait falls
  **>= 0.30 s in both batteries**.
* **Mechanism endpoint**: the chosen fruit's along **drops >= 0.10 m on >= 50 %
  of attempts**. `E1_hat` and this endpoint are stated per battery, and both
  must hold (E1's own structure).
* **Prediction at the census**: the acceptance is **predicted to fail the
  mechanism endpoint** (20 % < 50 %) and to land a 0.24-0.40 s wait drop -
  i.e. **the lever is supply-bound on the acceptance, and the pear is the
  battery where it can act**.

The treatment arm's own census (batch 2, `FRUIT_BED_DIAG=1` with the default on)
agrees and shows the rule doing exactly what it says: acceptance **2/10**
affected (drops 0.235, 0.244), pear **5/10** (drops 0.236, 0.149, 0.178, 0.153,
0.194), and on **all 7 affected attempts the chosen fruit is the near one**.
The diag is print-only: the pair with the plain treatment run is **344/344** and
**378/378 IDENTICAL**.

---

## 3. The measurements (A = `=0`, B = the new default; 2 seeds each)

`ATTEMPTS=10`, `FRUIT_MOTION_REPORT=1`, `FRUIT_CYCLE_REPORT=1` on both arms;
acceptance = the shipped supply, pear = `FRUIT_SUPPLY_SPECIES=pear`.

### 3.1 The batteries

| run | attempts | placed | span (s) | s/attempt | wait mean | wait median | diverted | discharged |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acceptance A seed 5 | 10 | **6** | 150.5 | **15.00** | **1.28** | 1.10 | 0 | 5 |
| acceptance B seed 5 | 9 | **6** | 131.5 | **14.60** | **0.93** | 0.42 | 0 | 4 |
| acceptance A seed 6 | 10 | **8** | 146.4 | **14.60** | **1.41** | 1.44 | 0 | 7 |
| acceptance B seed 6 | 9 | **5** | 129.4 | **14.40** | **1.09** | 1.11 | 0 | 3 |
| pear A seed 5 | 10 | **6** | 157.1 | **15.70** | **1.80** | 1.82 | 0 | 5 |
| pear B seed 5 | 10 | **5** | 148.9 | **14.90** | **1.07** | 1.12 | 1 | 5 |
| pear A seed 6 | 10 | **5** | 151.8 | **15.20** | **1.54** | 1.53 | 0 | 4 |
| pear B seed 6 | 10 | **4** | 142.8 | **14.30** | **0.93** | 0.84 | 0 | 3 |

`gate_open = 0.0 s`, `queue_peak = 0`, `recirculated = 0` on every run.
`discharged` is the tray-discharge row count (`[belt] ... discharged to the ...`),
which can trail `placed` by one: a payload placed in the last seconds is still
sliding when the run ends.
**Both treatment acceptance runs make 9 attempts, not 10**: attempt 5 is a
`no eligible fruit` slot (`window=0` in the B census). Neither control has one.
That is the one *mechanical* cost in the corpus, and it is not a grasp outcome.

### 3.2 The paired endpoints

| pair | wait A | wait B | delta | 95 % CI (Welch) | s/att delta | placed A -> B |
| --- | --- | --- | --- | --- | --- | --- |
| acceptance seed 5 | 1.28 (n=10) | 0.93 (n=9) | **-0.35** | [-1.11, +0.41] | -0.40 | 6 -> 6 |
| acceptance seed 6 | 1.41 (n=10) | 1.09 (n=9) | **-0.32** | [-0.88, +0.23] | -0.20 | **8 -> 5** |
| pear seed 5 | 1.80 (n=10) | 1.07 (n=10) | **-0.73** | [-1.29, **-0.18**] | -0.80 | 6 -> 5 |
| pear seed 6 | 1.54 (n=10) | 0.93 (n=10) | **-0.61** | [-1.07, **-0.15**] | -0.90 | 5 -> 4 |

**Power, stated rather than bar-gated** (the Oracle's amendment): the
per-attempt wait spread is ~0.8 s, so at n = 9-10 the standard error of a mean
is ~0.25 s and of the difference ~0.35 s - **the 0.30 s bar is ~1 SE** and can
false-fail about half the time. The pear's two intervals exclude 0; the
acceptance's two span it, which is exactly what a 0.24-0.40 s effect looks like
at this n.

### 3.3 The mechanism, to 2 ms

The acceptance, seed 5, **attempt 1** is the seeded instance (same supply, same
window in both arms):

* control: `usable = {+0.435, +0.670}`, chosen **+0.670**, wait **2.38 s**;
* treatment: same window, chosen **+0.435**, wait **0.42 s**;
* `delta_along / v = (0.670 - 0.435) / 0.12 = **1.958 s**` against the measured
  `delta_wait = **1.960 s**`.

So the conversion factor is **1.0**, not 0.6: the pre-registered E1 discount is
too conservative by 40 %, and the measured deltas sit at the *undiscounted*
prediction (0.404 s acceptance / 0.623 s pear against -0.35/-0.32 and
-0.73/-0.61). The lever is fully understood; its **prevalence** is the limit.

### 3.4 The `[cycle]` decomposition (the corpus's first single-arm blocks)

| run | descent | total | prepose | hover | close | grip | lift | place | release | return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acceptance A s5 | **2.75** | **15.05** | 0.88 | 0.77 | 1.19 | 1.61 | 1.82 | 3.35 | 2.04 | 0.64 |
| acceptance B s5 | **2.40** | **14.61** | 0.88 | 0.77 | 1.19 | 1.59 | 1.81 | 3.23 | 2.09 | 0.65 |
| pear A s5 | **3.27** | **15.71** | 0.88 | 0.79 | 1.19 | 1.59 | 1.77 | 3.51 | 2.05 | 0.67 |
| pear B s5 | **2.55** | **14.89** | 0.88 | 0.77 | 1.19 | 1.57 | 1.58 | 3.59 | 1.97 | 0.60 |

**The descent is the only segment that moves** (-0.35 s acceptance, -0.72 s
pear - the wait deltas) and every other block is flat to within 0.1 s. So the
lever does not cost setup anywhere else; the cost it has is the supply state.

---

## 4. The endpoint ledger

| # | endpoint | result |
| --- | --- | --- |
| **E1** | wait falls >= 0.30 s **in both batteries** | **PASS**: 4/4 pairs (-0.35, -0.32, -0.73, -0.61); pear CIs exclude 0, acceptance CIs span it |
| E2 | the attempt span / `s/attempt` falls | **PASS**: -0.40 / -0.20 / -0.80 / -0.90 s; `[cycle] total` -0.44 / -0.82 (descent only) |
| **E3** | `placed >= A - 1` in each battery | **FAIL**: acceptance seed 6 is **5 vs 8** (-3). Seed 5 is equal (6/6), pear -1 and -1 |
| E4 | no new failure reason | **PASS on 3 of 4 pairs; FAIL literally on pear seed 6** (one `fruit did not follow the gripper`, a class the acceptance *control* on this tree also has). The reason sets are otherwise equal; the starved slot is a supply state, not a note |
| **E5** | the pear's left cnp does not rise | **FAIL on seed 5** (4 -> 5); flat on seed 6 (5 -> 5). Left is the documented cnp lane, so this is a count at n = 5-6, but the registered reading is "does not rise" |
| E7 | the two-line byte-identity | **Not run - replaced by the Oracle amendment**: (i) the AST proof that every lane/prefer_lane caller is above the rule, (ii) the three-way invariance in the new selftest, (iii) the **shared-station replay** `FRUIT_BIARM=1 ATTEMPTS=10 SEED=5`: A vs B **331/331 `[fruit]` lines IDENTICAL** (8/10, 144.5 s both). `configs/motion_reference_twoline.json` is untouched (**2246f83c**) |
| **F5** | the direct/policy selection untouched | **PASS**: ep 0 identical unset vs `=0`; `=1` moves it by 0.240 m (§1) |
| **mech** | chosen-along drop >= 0.10 m on >= 50 % of attempts | **FAIL on the acceptance (2/10 = 20 %, control and treatment)**, **PASS on the pear (5/10 = 50 %)** |
| gate | the motion gate | every **budget** passes on all eight A/B runs (no leg over its speed budget, no over-budget descent). Acceptance A seed 5 reads `fingerprint: matches configs/motion_reference.json`; the other three read `DIFFERS` - seed 6 by construction (a different spawn seed) and both B runs because a moved branch is the expected outcome of a real selection change. The gate's FAILs are the rate clause only (6/10, 6/9, 5/9) |

**Verdict: NOT ADOPTED** (E3 and E5 fail, and the mechanism endpoint fails on
the acceptance). `NEAREST_ABOVE_FLOOR_SCRIPTED` ships **"0"**.

**The mechanism of the cost, named and not measured.** The near pick removes the
fruit that the *next* selection would have taken and leaves the upstream one,
which is still below the catch floor when that selection happens (the next
attempt starts at once, and the far fruit needs 0.2-0.6 s to arrive). Both
treatment acceptance runs then report `no eligible fruit` at attempt 5; neither
control does (2/2 vs 0/2). The counter-observation that keeps this a hypothesis:
the `[cycle]` blocks and the `s/attempt` show no other cost, and the pear
(where the band is denser) never starves. A pooled test of the starvation rate
needs a battery aimed at it, not this one.

**The reopen path is one env var and one condition.** `=1` reproduces this
phase's treatment byte-identically (§7), so a future owner needs no code change;
what it needs is a supply whose floored set carries two candidates on >= 50 % of
attempts - the pear is exactly at that boundary and reads -0.61/-0.73 s with
placed -1/-1, i.e. inside E3's guard.

---

## 5. L2 step 1 — the loop's pause, measured

One direct run, the P37/W8-A scenario, `moe_v13s` `61da390a`, seed 77, 5
episodes, the shipped loop (**E = 4, RTC off**), `FRUIT_RTC_REPORT=1` (the
existing per-step timer) **plus** the new default-off `FRUIT_LOOP_TIMING=1`,
which splits the observation's `RenderingManager.render()` from the camera
`get_data` reads and times the model call separately at the same sites.

### 5.1 The per-episode wall and the split

Run wall **142.9 s / 5 = 28.6 s per episode**; `sim/wall = **0.55**` on the
env's own `_ticks` convention (15.8 s from the reset's *end*: the 10.8 s of
policy stepping below plus ~5 s of scripted primitive) against a wall that
starts at the reset, and **0.38** on the policy-phase stepping alone (1294 steps
= 10.78 s). `decisions = 322`, `decisions/s = 29.9` of stepping time,
`steps = 1294`, `control_ms` median **9.67** (p90 12.01, max 16.95).

| stage | per decision | share of the episode wall |
| --- | --- | --- |
| model inference | **47.4 ms** (median 45.6, p90 51.4) | **10.6 %** |
| render (`RenderingManager.render()`) | **20.0 ms** (11.4-29.9) | **4.5 %** |
| camera (`get_data` reads + mask) | **3.6 ms** (2.9-3.8) | **0.8 %** |
| everything else (episode remainder) | not a per-decision cost | **84.1 %** |

**The registered pause share** (PREREG L2.1's formula, `policy_ms/step x steps /
wall` = 11.78 x 1294 / 1000 / 142.9) is **10.7 %** - **below the 25 %
materiality bar, so L2.2's F4 fires and the RTC cell is not run.**

Two honest readings inside that row:

* a decision costs **71.0 ms** (policy + render + camera) against **33.3 ms** of
  sim - **2.13x**; the model call alone is **1.42x**. The loop cannot be made
  real-time by hiding one stage.
* **"other" is not a per-decision quantity** and must not be read as one: it is
  the episode wall minus the three stages, divided by the decisions, and it
  contains the *scripted primitive phase* (which issues no decisions at all)
  plus the stepping, the `ik_step` path and the observation assembly.

### 5.2 Is any loop lever left?

**No, and the reason is measured.** A *free* loop would buy at most **16.0 %**
of the episode wall (policy+render+camera) and **10.7 %** if only the model call
were free - while RTC's own recorded mechanism pays its wait back in
`control_ms` (**9.2 -> 32.7 ms** in the stored cells) and its rate record at
other checkpoints is null-to-negative (v5-B E2 +24 pt p = 0.09; VLASH -31 pt).
Two further facts close the "it is render-bound" premise of the amendment: the
render is **4.5 %** of the wall (20.0 ms/observation, i.e. 0.6 s per running
second at 30 obs/s) and the camera **0.8 %** - the loop is **primitive-bound**,
which is the same scripted cycle the ledger already measures. A note on the
split's resolution: `advance()` calls `update_app(steps=0)`, so any asynchronous
GPU work the render leaves pending lands in `other`; the *combined*
render+camera block (23.6 ms, 5.3 %) is the number to quote, not the render
alone.

---

## 6. No-harm (the PREREG §0 contract)

| # | check | result |
| --- | --- | --- |
| N1 | `scripts/selfcheck.sh` | **PASS, 0 failures** (on the final tree, and on the measured treatment tree) - including the new `P43 selector scope` leg |
| N2 | the acceptance with the knob at its pre-adoption value | **IDENTICAL, 377/377** filtered `[fruit]` lines to `logs/p41/p2/accept_profile.log`; the pear pair likewise **378/378** to `logs/p41/p2/pear_profile.log`. `fingerprint: matches` (8a399626) |
| N3 | the two-line | **not run** (the Oracle amendment replaced it, §4/E7); `configs/motion_reference_twoline.json` untouched at **2246f83c** |
| N4 | `python3 scripts/96_motion_check.py` | **PASS** ("all motion checks passed") |
| N5 | `configs/*` and the checkpoints | **unchanged**: `motion_reference.json` **8a399626**, `..._twoline.json` **2246f83c**, `arm_parks.json` 42ab4fb7, `moe_v13s` **61da390a**. `scripts/106_index_audit.py` and `scripts/107_collect_merge_test.py` also PASS |
| - | post-revert identity (the flip not adopted) | `unset` (shipped default) **377/377 IDENTICAL** to the knob-0 control **and `fingerprint: matches`**; `=1` **344/344 IDENTICAL** to the measured treatment |

The `[fruit]` filter used for every identity line above drops the instrument
rows (`[bed-sel]`, `[bed-fall]`, `[cycle]`, `[carry]`, `[diag]`, `[seat]`,
`[attitude]`), which is what makes an instrumented run comparable to an
uninstrumented record; the counts are printed by `p2_report.py --identity`.

---

## 7. What this phase does **not** claim

* **No cross-configuration rate claim.** `placed` is one draw of an attractor
  (AGENTS §2): the acceptance seed-6 pair is `8/10` vs `5/9`, and the seed-5
  control is `6/10` vs `6/9`. E3 is reported as the registered guard failing,
  not as "the lever costs 3 placements".
* **No claim that the acceptance's -0.32/-0.35 s is distinguishable from 0** -
  its CIs span it; the pear's do not. The lever's *existence* is carried by the
  2 ms mechanism, not by the means.
* **The starvation mechanism is a hypothesis**, not a measurement (2/2 vs 0/2
  is a count at n = 2 pairs).
* **Nothing here re-opens** the grip/seat class (`logs/p42/SIM_LIMIT.md`), the
  supply density (P1c), the place geometry (P3), the belt speed (R3), the
  cadence, or the retention tax.
* **The two-line and the collector were not re-measured**: the two-line is
  provably above the rule (AST + invariance + the shared-station identity), and
  no collection was run.
* **L2 is a one-run measurement** (5 episodes, one seed) and its split is a wall
  measurement of an instrumented run, not a rate pair. It is not an A/B and does
  not need one: the endpoint is a share, and the share is 10.7 %.

---

## 8. The runs, the files, and the pins

### 8.1 Pins

* HEAD **`53e5ccf`** (nothing committed).
* **Measured tree (both L1 arms)**: `tasks.py` **`d1ab5326`** (scripted default
  ON), `rl_env.py` **`dddc79b6`** (the `direct` keyword + `FRUIT_LOOP_TIMING`),
  `control.py` 9384ff4f, `scene.py` 27e3d64a, `policy/runtime.py` 379ac706,
  `policy/trigger.py` b09d3cb2, `configs/*` as N5.
* **Final tree**: `tasks.py` **`a1b3d673`** (the default constant back to "0" +
  the scope docs), `rl_env.py` **`6324b60b`** (`TASKS_MD5` follow + the
  `loop_timing` manifest field), `scripts/224_p43_selftest.py` **new**,
  `scripts/213_prepared_next_selftest.py` gains the `=1` sub-test,
  `scripts/selfcheck.sh` registers the new leg. `logs/p36/offline_obs_diff.txt`
  is **regenerated** by the `218` selfcheck leg (it embeds `rl_env.py`'s md5) -
  that is the only touched file outside this phase's own set.
* **18 simulator runs, ~75 min of app wall** (batch 1 = 14 runs in 56 min, batch
  2 = 2 runs in 9 min, batch 3 = 2 runs in 9 min).

### 8.2 Files

```
logs/p43/P2_RESULTS.md              this file
logs/p43/p2/run_batch.sh            batch 1: the L1 A/B x 2 seeds x 2 batteries,
                                    the D0 censuses, the shared-station replay,
                                    the F5 pair, the L2 run
logs/p43/p2/run_batch2.sh           batch 2: the treatment's own census (2 runs)
logs/p43/p2/run_batch3.sh           batch 3: the post-revert identity (2 runs)
logs/p43/p2/batch_header.txt        the pins at run time
logs/p43/p2/batch{,_driver}.log     the driver rows (exit code + wall per run)
logs/p43/p2/*.log                   the 18 run logs
logs/p43/p2/p2_report.py            the report: census / batteries / pairs /
                                    sequence / cycle / direct / loop / identity
logs/p43/p2/p2_report.txt           its output
scripts/224_p43_selftest.py         the offline scope selftest (selfcheck leg)
```

Reproduce every number:

```bash
python3 logs/p43/p2/p2_report.py          > logs/p43/p2/p2_report.txt
python3 logs/p43/p2/p2_report.py --bed logs/p43/p2/d0_accept_A_s5.log
python3 logs/p43/p2/p2_report.py --identity
python3 scripts/224_p43_selftest.py
scripts/selfcheck.sh
```
