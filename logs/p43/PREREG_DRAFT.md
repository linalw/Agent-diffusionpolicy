# P43 PREREG (DRAFT) — phase 2 (rate + policy loop) and phase 3 (the park's deployment)

**Draft for Oracle gate 1, 2026-10-26.** Written before any phase-2/3 run.
Tree pinned at HEAD **`53e5ccf`**, `tasks.py` **`e2d0f12a`**, `rl_env.py`
**`50980bf5`**, `control.py` **`9384ff4f`**, `policy/runtime.py` `379ac706`,
`policy/trigger.py` `b09d3cb2`; `configs/motion_reference.json` **`8a399626`**,
`configs/motion_reference_twoline.json` **`2246f83c`**,
`configs/arm_parks.json` `42ab4fb7`; checkpoints `moe_v12` `3a9ccfc0` (shipped),
`moe_v13s` `61da390a`.

**Three levers, three decisions, one no-harm contract.** Nothing here re-opens
the grip/seat class (`logs/p42/SIM_LIMIT.md`), the supply density (P1c), the
place geometry (P3), the belt speed (R3), the cadence (R1/R3) or the seat (P42).
If a lever fails its pre-registered endpoint the phase records the negative and
does not re-run it in another form in this phase.

---

## 0. The no-harm contract (applies to **every** arm of every lever below)

Run once per phase, on the phase's tree, with every new knob at its
**pre-adoption** value (`FRUIT_SELECT_NEAREST_ABOVE_FLOOR=0`, `FRUIT_ARM_PARK`
unset, `FRUIT_RTC` unset) — i.e. the no-harm claim is that the **code change is
inert while the knob keeps its old value**. The new default has its own evidence
(E1/E2 for L1, P1-P8 for L3) and, on adoption, its own re-recorded reference.

| # | check | pass condition |
| --- | --- | --- |
| N1 | `scripts/selfcheck.sh` | PASS, 0 failures |
| N2 | `scripts/accept.sh` (scripted single arm) | `fingerprint: matches configs/motion_reference.json` (**8a399626**) and its `[fruit]` stream **byte-identical** to `logs/p41/p2/accept_profile.log` (457 lines after dropping `[seat]`/`[attitude]`) |
| N3 | one two-line dense run + `scripts/190_twoline_gate.sh` | `fingerprint: matches configs/motion_reference_twoline.json` (**2246f83c**) and **byte-identical** to `logs/p41/p2/twoline_profile.log` |
| N4 | `python3 scripts/96_motion_check.py` | PASS |
| N5 | `configs/*` and every checkpoint md5 | unchanged unless a lever's *adoption* decision says otherwise, and then the archive is written beside the new file |

A no-harm failure stops the phase (it is a tree defect, not an outcome).

---

## L1 — `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` as a **scoped default** (phase 2a)

### L1.1 The change

`tasks.py::select_target` (the current signature is `tasks.py:5424-5430`) gains an
explicit, caller-supplied scope instead of relying on the env default:

```python
def select_target(self, states, ..., reach_anywhere=True, diag=None,
                  direct: bool = False):        # <- new keyword
    ...
    # resolved like the regrasp cap: an explicit env value wins on both paths
    _default = "0" if direct else "1"
    if os.environ.get("FRUIT_SELECT_NEAREST_ABOVE_FLOOR", _default) == "1":
        near = [item for item in usable if item[0] >= floor + margin]
        if near:
            return _chosen(near[0][1])
    return _chosen(self._balance_arm(usable))
```

and `rl_env.py:1703` becomes
`self.task.select_target(self.spawner.state(), reach_anywhere=False, direct=True)`.

* **On**: the scripted dynamic catch (the acceptance, the pear/species batteries,
  the demo collector). **Off**: the direct/policy env's episode selection
  (`direct=True` → the shipped farthest-upstream rule, byte-equivalent).
  Structurally excluded already: the two-line selector (`prefer_lane` set) and
  the shared-station worker (`lane` set) return above the branch.
* **Offline proof of the scope** (a new selfcheck leg): a pure-function test on
  two synthetic candidate lists (one where nearest ≠ farthest) asserting
  `direct=True` returns the farthest and the scripted default returns the
  nearest, plus an assertion that `rl_env`'s call site passes the flag. This is
  the analogue of `152`'s scheduler invariants and it is what makes the scope a
  code fact rather than a claim.
* **Provenance**: the collector inherits the on-default, so the shard manifest
  gains `collection.nearest_above_floor` (the `collection.park_early` precedent)
  **before** any post-flip collection. No collection is run in this phase.

### L1.2 Endpoints

Two batteries, each a same-batch **control (A, knob pinned off) → treatment (B,
default on)** pair in **one claim**, 10 attempts, SEED=5: the **acceptance**
(`FRUIT_SUPPLY_*` shipped) and the species-locked **pear**
(`FRUIT_SUPPLY_SPECIES=pear`). `FRUIT_CYCLE_REPORT=1` on **both** arms of both
batteries (it is currently absent from the single-arm line — this gives the
current tree's first single-arm `[cycle]`; the instrument sits inside the
comparison, per `AGENTS.md` §3b).

| # | endpoint | bar |
| --- | --- | --- |
| **E1** | **the arrival wait** (`fruit at pick point … after N steps`), mean per attempt | falls by **≥ 0.30 s** vs A **in both batteries** (P40's point estimate is 0.44 s; the bar allows a 32 % shortfall). Current-tree A is expected near **1.28 s** (acceptance) and **1.80 s** (pear). |
| E2 | the attempt span (`sim=A-Bs` per attempt) and `[stats] s/attempt` | falls; report the delta |
| E3 | **placed** | `≥ A − 1` in each battery |
| E4 | new failure reasons | **none** (the reason sets are subsets of A's after `113`'s number normalisation) |
| E5 | the pear's **left cnp** count | does not rise (the lever changes *which arm* works: the P40 read moved the left's placements 1 → 2, so the left's class is the pre-registered risk) |
| E6 | the per-attempt wait distribution | the 10 per-attempt waits are reported with the mean/median/spread, and the number of attempts whose fruit is identical to A's is stated (the streams diverge at the first differing selection) |
| E7 | the two-line | **byte-identical** replay of `twoline_profile.log` (N3) — the scope did not leak |

### L1.3 Falsifiers

1. **F1**: the wait falls by **< 0.30 s** in *either* battery → the P40 result
   does not reproduce on this tree → **no adoption**.
2. **F2**: `placed < A − 1` in either battery.
3. **F3**: a new failure reason in either arm.
4. **F4**: N3 is not byte-identical → **stop** (a scope leak; the change is
   withdrawn before any outcome is read).
5. **F5**: the direct env's `[rl] episode N: <fruit> grade=… y=…` presentation
   rows at seed 77 (15 episodes, one smoke run) differ from `logs/p37/B_ab/A_1.log`'s
   → **report only**; a mismatch blocks the flip pending a code read (it would
   mean the flag is not reaching the call site).

### L1.4 Adoption, and what it costs

Adopt (default on for the scripted catch) iff **E1 in both batteries ∧ E3 ∧ E4 ∧
E7**. On adoption: re-record `configs/motion_reference.json` from the
**same-batch** B run (the single-arm reference moves — the fruit sequence
changes), archive the old file beside it, and quote the pear battery as a
replication without a reference. On failure: the knob keeps its current
meaning (default off) and this file records the negative.

**Cost**: 4 scripted runs (acceptance A/B + pear A/B) + 1 two-line replay + 1
direct smoke + selfcheck ≈ **35 min of simulator wall**, budget **1 h**.

**What L1 cannot claim**: the 0.4 s is 2.7 % of a 15 s span and the branches
move, so the `placed` counts are **not** a rate comparison. The verdict is the
wait (a per-attempt continuous quantity), replicated across two batteries.

---

## L2 — the policy loop's pause, measured; **one** RTC cell if (and only if) it is material (phase 2b)

### L2.1 Step 1 — the measurement (no A/B)

One direct run at the P37/W8-A scenario, `moe_v13s` `61da390a`, seed 77, 15
episodes, **`FRUIT_RTC_REPORT=1`** on the **shipped** path (RTC off — the flag
only adds per-call wall timing).

Endpoints, from the `[rtc]` totals and the run's own wall row:

* `policy_ms` median / p90 per call, `policy_ms/step`, `control_ms` median;
* `decisions`, the decision rate, and `steps`;
* the episode wall (`[rl] run wall end … duration=`), and
* **the pause share** = `policy_ms/step x steps / 1000 / episode_wall_s` (the
  `[rtc] summary` line prints `policy_ms/step` and `steps`, not the total, so
  the product is the derived wall; state the arithmetic in the report).

**Materiality bar (pre-registered):** the pause share is **≥ 25 %** → run step
2. Below 25 % the wall is not the policy's and the item **closes with a number**
(no RTC cell).

### L2.2 Step 2 — one cell (conditional)

`FRUIT_RTC=1` (E = `execute_steps` 4, `EXP`, guidance 1) vs the control, **N = 5
runs x 15 episodes per arm**, seeds 77/101/202/303/404, sampler seed 11,
interleaved, **one claim**, the same scenario and checkpoint as step 1, both
arms with `FRUIT_RTC_REPORT=1` (the instrument sits inside the comparison).

| # | endpoint | bar |
| --- | --- | --- |
| **R1** | **wall per episode** (the only reason to adopt) | falls by **≥ 10 %** |
| **R2** | pooled placed | non-inferiority **delta ≥ −0.10** with the exact unconditional p (the P37 form); the standardised species/diameter deltas must agree in sign |
| R3 | the right-arm carried class | not worse (report the counts) |
| R4 | new failure reasons | none |
| R5 | the executed stream's step/jerk | falls (the known mechanism — a **report**, already measured 3-5x at `moe_v10`) |

### L2.3 Falsifiers

1. **F1**: R1 < 10 % → close (the prior from v5-B is exactly this: the async
   wait is paid in the control loop, `control_ms` 9.7 → 22.5 ms at E4).
2. **F2**: R2 fails (a rate drop beyond the margin).
3. **F3**: R4 fails.
4. **F4**: step 1's pause share < 25 % → step 2 is **not run** (recorded as the
   answer).

### L2.4 What L2 is not

* **Not a rate lever.** A policy decision costs 24-100 ms of wall against 33.3 ms
  of sim; RTC can only hide the wall, and the sim cycle is the scripted
  primitive's. No `placed/min` of sim time is at stake.
* **Not an unexplored knob.** `FRUIT_RTC`/`FRUIT_VLASH` were measured on
  `moe_v10` (v5-B: E2 +24 pt p = 0.09, E1/E4 flat) and `moe_v11` (path-3:
  VLASH −31 pt). This phase measures **the pause on this tree** and **one** cell
  on the current checkpoint — no ladder, no VLASH.

**Cost**: step 1 ≈ **8 min**; step 2 ≈ **80 min** of machine time (10 sessions x
~28 s/episode). Budget **1.5 h**.

---

## L3 — the park's re-measurement on the current tree (phase 3)

### L3.1 Design

**A = the shipped direct env (no park), B = `FRUIT_ARM_PARK=back`**, both arms on
**`moe_v13s` `61da390a`**, the P35/P36/P37 scenario verbatim, the same three
diagnostics on both arms, **N = 5 runs x 15 episodes per arm**, seeds
77/101/202/303/404, policy seed 11, interleaved, **one claim**. (P37's "both
arms parked" belongs to *its* variable, the checkpoint; here the variable is the
park, so A must be un-parked. Everything else is the P37 shape.) The realised
right-arm n will be **~44-51 per arm** (P35 51/50, P37 44/49) because the arm
follows the fruit's grade; every power statement below is for n ≈ 50.

The manipulation check is read **before** the outcomes, per arm, and is the
gate: M1-held and M1-applied **against the pose the reset achieved** (the P35
command-relative 0.02 rad bar is **not** used: the shipped `ready` reset is
itself 0.037 rad from its command, so the command form discriminates nothing),
M2a `max band arm_frac < 0.10`, plus the band census (fully-hidden calls,
inactive-arm pixels) as a **report**.

### L3.2 Endpoints

| # | endpoint | bar |
| --- | --- | --- |
| **P0** | **the baseline read**: A's pooled right-arm carried rate on this tree | decides which endpoint is primary: **≥ 0.40 → branch A** (the class contrast is evaluable); **< 0.40 → branch B** (it is not: at n ≈ 50 a halving from 0.40 is the last point at p ≤ 0.05) |
| **P1** | **right-arm carried-not-placed, B vs A** (pooled 2x2) | **branch A only**: exact two-sided Fisher **p ≤ 0.05**, with the observed contrast reported (the implied floor is ≈ 0.20-0.22 at this n) |
| **P2** | **right-arm placed**, B vs A | **delta ≥ −0.10**; the standardised (species + diameter tertile) deltas agree in sign |
| **P3** | **pooled placed** | **gain ≥ +0.10 absolute** (P35 read +0.33) |
| P4 | the left arm (the park's no-op guard) | no regression > 0.05 |
| P5 | new failure reasons | none (`113`'s number normalisation) |
| P6 | the median cycle | not worse by > 5 % (P37's S4 bar) |
| P7 | the run level | B ≥ A in **≥ 4/5** runs on P1's class (branch A) / on P2 (branch B) |
| P8 | the check | M1-held/applied and M2a **100 %** per arm; the band census reports 0 fully-hidden calls in B |

### L3.3 Falsifiers and the decision

* **Adopt** (the direct env's default on; `FRUIT_ARM_PARK=ready` restores the
  shipped pose) iff **P8 ∧ P5 ∧ P2 ∧ P3 ∧ P7** and (**branch A**: P1 significant,
  with P0 ≥ 0.40) — or, if P0 < 0.40, on the same set **without** P1, labelled
  **"no class-level evidence at this n; the pooled/placed read carries it"**
  (P4 and P6 are guards and must not fail).
* **Stay opt-in** iff P1 is not significant in branch A, or P2/P3 fail, or P5
  fails, or P7 disagrees with the pooled read.
* **No outcome claim** iff P8 fails (the check is the attribution).
* **Either way, record**: the park corpus is a **4.4 N** corpus; the shipped
  grip is **9.8-9.9 N**; a default flip re-baselines every direct number
  (P33/W7-C/W8-A/R9/P35/P36/P37/P38 become "pre-park"), so the docs must say so
  and the direct A/B reports must carry the park state.
* **Not registered**: a `moe_v12` direct arm — the canary (`60_eval_policy.py`)
  does not construct `SortingRLEnv`, so `FRUIT_ARM_PARK` has no code path on the
  interface that would deploy it; a `moe_v12` park arm would answer a question
  nobody can ship — and any change to `configs/arm_parks.json` (the two parks
  `back`/`side_deep` are both left-only, measured).

### L3.4 Cost

**150 episodes x 27.7 s ≈ 69 min** of episode wall (the measured P35/P37
precedent: 71 / 72.6 min for a full two-arm batch) + 10 app startups + N1/N2.
**Budget 2-3 h** with one re-run allowance — **quote the measured 1.2-1.4 h**,
the 3 h is the envelope.

---

## 4. Phase order, gates, and the budget

| phase | levers | gate | wall (measured / budget) |
| --- | --- | --- | --- |
| 2 | L1, then L2 (step 1 always; step 2 only if material) | Oracle 2 | L1 35 min / 1 h; L2 8 min (+80 min) / 1.5 h |
| 3 | L3 | Oracle 3 | 1.2-1.4 h / 2-3 h |
| 4 | docs, the deployment recommendation, the commits | Oracle 4 | — |

**Total simulator budget for phases 2-3: ~2-3 h measured, ~5 h enveloped.**

### The stop rules (whole-phase)

* A **no-harm** failure (§0) stops the phase.
* **L1 F4** (a scope leak) withdraws L1 before any outcome read.
* **L2 F4** (pause < 25 %) closes L2's cell without running it.
* **L3 P8** (the check) failing means no park claim is made — the batch is
  still recorded, because the direct interface's current-tree rate comes out of
  it as a by-product.

---

## 5. What this PREREG refuses (and why, in one line each)

| refused | reason |
| --- | --- |
| any grip/force/seat lever | `logs/p42/SIM_LIMIT.md`: closed with a mechanism, at 2.2x and 6x force, every face, every depth, centred to 1.4-4.6 mm |
| `FRUIT_CARRY_GUARD`, `FRUIT_CARRY_RELIEF`, `FRUIT_CLOSE_LOAD_RATE` | measured and not adopted (W8-B, R6-B, R11-B); the last one is negative on all three scripted measurements |
| a new recollection / fine-tune | three spends, three no-gains (P33 −8/45, W8-A +1/75, P37 −0.018) |
| `FRUIT_VLASH` | negative twice (−31 pt; equal-or-below RTC) |
| widening the trigger's lateral gate | P38: 0.06 % class, 8.3 mm reach residual at the edge |
| `FRUIT_SUBSTEPS` | 2.2x force for 3.1x wall, class unchanged |
| the supply density / belt speed / place distance / hot-arm | closed (P1c, R3, P3, R3) |
| a "shorter setup" / a new selection floor | `logs/p40/ARRIVAL_SPLIT.md` §5: the arm block is fully overlapped; the floor's margin is not spent by L1 (`~0.10-0.15 m` remains) |
| `scripts/189_w7a_chain.sh` | it rewrites the two-line reference; never run casually |

---

## 6. Provenance to record per phase

* tree md5s before/after (`tasks.py`, `rl_env.py`, `control.py`, `scene.py`,
  `policy/*`, `configs/*`, the checkpoints used);
* the claim line of every simulator batch;
* the `[fruit]`-stream identity checks (N2/N3) with their filtered line counts;
* for L2 and L3: the per-episode `[rtc]` / `[rl] episode` / `[park]` rows the
  endpoints are read from, so the numbers are re-derivable offline.
