# P43 phase 1 — POLICY_STATUS: the checkpoints, the canary, the loop, and what is worth measuring

Written **offline** 2026-10-26 (no simulator, no `src/` edit, no commit). Tree
HEAD **`53e5ccf`**, `rl_env.py` **`50980bf5`**, `tasks.py` **`e2d0f12a`**,
`policy/runtime.py` **`379ac706`**, `policy/trigger.py` **`b09d3cb2`**,
`control.py` `9384ff4f`; `configs/motion_reference.json` **`8a399626`**.

**The one-sentence state.** The **shipped default is `moe_v12`** and it is the
only checkpoint with a post-P41 hybrid-canary sample (**7/10**, one sample); the
**direct interface's** numbers belong to `moe_v13s` (and to the **park**, which
takes its right arm to **94-97.7 %**); **five alternative checkpoints have been
measured and none beats its baseline**; and the policy loop's **wall** is the
only unmeasured cost left, with both of its knobs (`FRUIT_RTC`, `FRUIT_VLASH`)
already measured to be **null-to-negative on rate** at other checkpoints.

---

## 1. The checkpoints, and what was actually measured

All md5s read from `checkpoints/*/policy_best.pt` on this tree. "Canary" = the
**hybrid** closed loop (`accept_policy.sh`, fixed pre-v9 supply, 10 episodes,
`MIN_RATE` 0.60). "Direct" = the **direct** env (`110_rl_rollout` /
`112_rl_ab.sh`), a different interface with a different failure denominator.

| checkpoint | md5 | lineage | hybrid canary | direct A/B measured | tree it was measured on |
| --- | --- | --- | --- | --- | --- |
| **`moe_v12`** (shipped) | `3a9ccfc0` | P2b fine-tune of `moe_v11` on `demos_v11` (fixed pre-v9 supply) | **6/10** (P2), **5/10** & **6/10** (P2b), **5/10** (P32 D0), **7/10** (**P41, the current tree**) | **33/45 = 73.3 %** (W4 pinned, lateral gate 0.06) — the best **pooled** direct count on record; 14/45 dense 0.06; 17/45 shipped default 0.16 | W4 / P2b (pre-P32, pre-P40, pre-P41) |
| **`moe_v13s`** | `61da390a` | dense fine-tune of `moe_v12` on `demos_v12` (158 eps, two-line collection, pre-W7-A task pin `c8854d6c`) | **8/10** pinned (W4 `30`, W7-C `canary_pinned`); **6/10** dense (`w3/81b`); **6/10** pinned-dense; **5/10** patch (W7-C) | 28/45 pinned 0.06 (W4); 19/45 dense 0.16; **21/75** (W8-A A); **25/75** (R9 A); **16/45** (P33 A, cnp 26); **43/44 = 97.7 %** with the park (P37 A); **47/50 = 94 %** with the park (P35 B) | W3/W4/W7-C/W8-A/R9/P33/P35/P36/P37 (all pre-P41) |
| `moe_v13p` | `fed54993` | W7-C fine-tune of `moe_v12` on the two-line patch rollouts (`demos_v13p`) + `demos_v11` base | 5/10 patch; 8/10 pinned | **22/75 = 29 %** vs `moe_v13s` **21/75 = 28 %**; carried 49 → 47; pairing **0 B-only / 2 A-only**, sign p = 1.0000 → **no gain** | W8-A (N = 5 x 15, seeds 77/101/202/303/404) |
| `p33_pear` | `31751eaa` | post-pear store `datasets/p33_pear` (180 eps) fine-tune of `moe_v13s` | 5/10 (smoke) | **8/45 = 18 %** vs `moe_v13s` **16/45 = 36 %**; carried **33 vs 26**; left 1/21 vs 2/16; right 7/24 vs 14/29 → **negative** | P33 phase 3 (`logs/p33/E_ab/`, N = 3 x 15) |
| `p37_park` | `3fa45c96` | `moe_v13s` fine-tuned on 90 park-collected direct rollouts (28.3 % rollout-window share) | not run | **47/49 = 0.959** with both arms parked vs `moe_v13s` **43/44 = 0.977**; carried **0 vs 0** → **no gain** (P37) | P37 (N = 5 x 15, both arms parked) |
| `rl_awr1` | `a1766ecd` | R9 AWR/RWR iteration on its own 56 fresh rollouts (outcome-weighted) | not run | **18/75 = 24 %** vs `moe_v13s` **25/75 = 33 %**; carried-class 5 B-only / 4 A-only, p = 0.500 → **negative** | R9 (N = 5 x 15) |
| `moe_v13s_spaced` | `84cc5863` | the superseded spaced-burst store's fine-tune | 8/10 on the **spaced** supply | — | W4 history only |

**Two things this table settles and one it does not.**

* **Settled:** **no alternative checkpoint beats its own baseline** on the
  interface it was measured on. `moe_v13p` (+1/75, p = 1.0), `p33_pear`
  (-8/45), `p37_park` (-0.018, no gain), `rl_awr1` (-7/75). The **four**
  fine-tune spends are all no-gain, and P33/P37 name why: the class they
  targeted is the loaded slide, i.e. the family the closing record treats as
  geometry-bound on the scripted line (`logs/p42/SIM_LIMIT.md`).
* **Settled:** the **shipped** checkpoint is not the strongest *direct* one on
  record (`moe_v12` 33/45 vs `moe_v13s` 28/45 on the W4 pinned branch), and the
  park's win was measured on `moe_v13s`, not `moe_v12`. **Interface matters
  more than checkpoint here**: the hybrid canary and the direct env disagree on
  which arm is better, and the canary has no `moe_v13s` sample on this tree.
* **Not settled:** whether `moe_v13s` beats `moe_v12` **on the hybrid canary on
  this tree**. That is one measurement (§3 item 1), and it is the only
  checkpoint question that matters for a deployment.

---

## 2. The canary and the loop

### 2.1 The recorded spread, and the P41 smoke

`accept_policy.sh`'s documented spread for this path at the v7 scenario, fixed
pre-v9 supply: **5-8/10**. The named samples:

| sample | checkpoint | result | log |
| --- | --- | --- | --- |
| F2 | `moe_v11` | 8/10 | `logs/biarm/30_canary_moe_v11.log` |
| P2 | `moe_v12` | 6/10 | P2 |
| P2b run 1 / run 2 | `moe_v12` | **5/10** / **6/10** | `logs/p2b/21_canary_moe_v12.log`, `22_canary_moe_v12_run2.log` |
| P32 D0 (post-pear) | `moe_v12` | **5/10** | `logs/p32/D0_accept_policy_pear.log` |
| **P41 (this tree)** | `moe_v12` | **7/10** | `logs/p41/p4/accept_policy_profile.log` |

**The P41 sample, exactly.** 7/10 at the 0.60 floor, **2 grip losses + 1
pick-station escape** (`fruit left the pick station during the close
(1416 mm)` — the apple had already drifted 283 mm during the close, and on the
preceding kiwi the fingertips were **575 mm** from the fruit when the close
started: the policy's hand, not the finger drive). The gate **FAILs on its
reason clause only** (that note is outside the recorded baseline reason set);
the verdict is printed in `logs/p41/p4/accept_policy_claim.log`. Its app wall is
**740.5 s for 10 episodes = 74 s/episode** (the W3-supply canary, for contrast,
was 1 020.1 s = 102 s/episode for 10 — `logs/r5/30_canary_w3supply.log`).

**One canary is one sample.** The loop is **not** bit-identical run to run: with
the same spawn seed the ten targets come out in the same order, but the outcomes
differ because the policy conditions on **rendered frames** (constant frames →
bit-identical; real frames → not, and disabling TAA/DLSS does not help). So
7/10 is a sample of the p33-era grip/station class, **not a rate**.

### 2.2 The loop's cadence and latency (code-read + measured)

| item | value | site |
| --- | --- | --- |
| control / physics tick | 1/120 s, `FRUIT_SUBSTEPS` **1** | `control.py:30`, `common.py:18-25` |
| observation + model call | every **4th** control tick → **30 Hz of sim time** | `rl_env.py:2231` (`if self._step % 4 == 0`) |
| chunk execution | 1 action per control tick, `execute_steps = 4` | `rl_env.py:861/882` |
| action horizon / obs horizon / denoising | 16 / 2 / DDIM-16 | `rl_env.py:1326/2330/2751` |
| episode reward horizon | **1 500 policy control steps = 12.5 s of sim**, then the scripted primitive runs ~3 000 more ticks | `rl_env.py:457-481`, `515` |
| **measured** decisions / episode (direct) | **232** mean (199-345), over **1 829 ticks** (15.2 s) → **7.89 ticks/decision** averaged over the episode | `logs/p37/B_ab/A_*.log` (75 episodes) |
| **measured** policy call | `policy_ms` med **23.6 / 25.0 / 52.2 / 100.0 ms**, p90 33.3-115.7 | `logs/rtc/` batches, `logs/p40/RATE_CENSUS.md` §5 |
| **measured** control step | `control_ms` med **9.2 / 32.7 / 111.4** (the policy call excluded) | same |
| full per-tick wall (RTC batch) | **~62 / ~35 / ~23 ms** at E = 1 / 2 / 4 → real-time factors **0.14 / 0.25 / 0.36** | v5-B timing table (WORKLOG) |
| measured direct episode wall | **27.7 s**/episode (P37), **27.2 s** (P35) | `run wall end … duration=` |

So one decision costs **24-100 ms of wall against 33.3 ms of sim** (4 ticks): the
loop is **not real-time and cannot be made one by shortening the chunk**. Over an
episode that is **5.6-23.2 s of the 27.7 s wall (20-84 %)** — never measured
directly on this tree.

### 2.3 RTC / VLASH — measured, twice, and not for rate

Both live in `src/fruit_sorting/policy/runtime.py` (`RTCSettings.from_env`),
**default off** (`FRUIT_RTC=0`, `FRUIT_VLASH=0`); the shipped path is the
single-sample chunk, byte-for-byte. `FRUIT_RTC` runs the next chunk's sampling
spread over the pending actions (freeze + EXP soft-inpaint); `FRUIT_VLASH=1`
implies guidance off plus the state roll-forward.

**There are rate measurements — at other checkpoints.** They are in the WORKLOG,
not in a P-phase file:

| arm | checkpoint | pooled | verdict |
| --- | --- | --- | --- |
| v5-B E1 RTC vs legacy | `moe_v10` | 22/45 vs 21/45 | wash |
| v5-B E2 RTC vs legacy | `moe_v10` | **22/45 vs 11/45 (+24 pt)** | **not significant**, p = 0.09, and the legacy dip is one run (1/15) |
| v5-B E4 RTC vs legacy | `moe_v10` | 24/45 vs 22/45 | +2 pt |
| v5-B E1/E2/E4 `FRUIT_VLASH` | `moe_v10_vlash` | 15/45, 21/45, 15/45 | equal-or-below RTC at every E |
| path-3 `vlash` | `moe_v11_vlash` | **16/45 = 35.6 % vs base 30/45 = 66.7 % (-31 pt)** | **negative**, new failure class (`fruit fell off the line`), finger left open at fire |
| path-3 `event` (not RTC) | `moe_v11` | 33/45 = 73.3 % (+6.7 pt) | pre-registered +8 pt bar not met → not adopted |

**And the wall does not fall either**: `control_ms` rises 9.5 → 33.5 ms (E2) and
9.7 → 22.5 ms (E4) because the async wait is paid in the control loop, so the
full per-tick cost is flat-to-worse. The **real** measured RTC win is
**motion quality**: the executed stream's step/jerk fall **3-5x** (E2 0.11/0.22
→ 0.03/0.05; E4 0.08/0.15 → 0.04/0.06) at identical `policy_ms/step`.

**The honest state:** RTC/VLASH are **not** an unexplored knob — they were
measured on `moe_v10`/`moe_v11`, twice, and the rate effect is null-to-negative.
What is **not** measured is (a) **the pause itself** on this tree (the policy-call
share of the episode wall), and (b) RTC on `moe_v12`/this tree. P43 registers
(a) as a measurement and (b) as **one** cell, conditional (§3 item 2).

---

## 3. What is worth measuring next (ranked, at most three)

### 3.1 `moe_v13s` vs `moe_v12` on the **hybrid canary** — the only open checkpoint question

* **Why**: the canary is the interface of record (`AGENTS.md` §3: "the hybrid
  pinned canary stays the interface of record"), the shipped default is
  `moe_v12`, and the **only** post-P41 canary sample is one 7/10. Meanwhile the
  direct interface (a *different* interface) puts `moe_v13s` behind `moe_v12`
  (28/45 vs 33/45 on W4's pinned branch) but `moe_v13s` is the checkpoint that
  carries the park's 94-97.7 %. Those two facts cannot be reconciled without a
  canary A/B.
* **Design**: N = 3 runs x 10 episodes per arm, interleaved in one claim, the
  canary's own scenario (fixed supply, `scatter=0`), the same reasons baseline.
  N = 3 because the endpoint is a 10-episode rate with a 0.60 floor and the
  loop's own spread is 5-8/10 — a **3-run range** is the minimum that separates
  "same" from "worse", and the loop is not reproducible per run.
* **Cost**: ~**74 min** of machine time (3 runs x 2 arms x 12.3 min).
* **What it cannot do**: prove either checkpoint is good — 7/10 is inside the
  recorded spread. It can only answer "does the alternative fall out of the
  spread".

### 3.2 The policy loop's **pause**, measured — then one RTC cell only if it is material

* **Why**: the wall is the last unquantified cost on this interface, and it
  decides how many direct experiments fit per hour (P43's phases 3 and any
  future direct work pay it).
* **Step 1 (measurement, no A/B)**: one direct run at the P37 scenario with
  **`FRUIT_RTC_REPORT=1`** (the shipped path; the flag adds per-call wall timing
  and is *not* an RTC switch). Read `policy_ms`, `policy_ms/step`, `control_ms`,
  `decisions`, the decision rate, and the pause share = policy wall / episode
  wall. **8 min.**
* **Step 2 (conditional)**: one `FRUIT_RTC=1` cell at the shipped E = 4 vs
  control, N = 5 x 15 per arm, one claim. **~80 min.**
* **The prior is negative** (§2.3): the rate effect was null at `moe_v10` and the
  per-tick wall did not fall. Registering it as *one cell, no ladder* is the
  honest form; the materiality bar is pre-registered in `PREREG_DRAFT.md` L2.

### 3.3 The park re-measurement (phase 3) — the only policy-side lever with a measured large effect

This is registered in `PARK_STATUS.md` §2-§3 and `PREREG_DRAFT.md` L3: **N = 5 x
15 per arm**, `moe_v13s`, ~**70 min** of episode wall. It is the only
policy-side item with a measured **+0.33 pooled / 0.667 → 0 carried** effect, and
it is the one that makes the right arm deployable at all.

### 3.4 What is **not** worth measuring (already measured, do not spend)

| item | why not |
| --- | --- |
| **a new recollection / fine-tune** | four spends, four no-gains: `moe_v13p` +1/75 (p = 1.0), `p33_pear` −8/45, `p37_park` −0.018, `rl_awr1` −7/75. What they target is the **loaded slide** (measured on the direct interface too, `logs/w8/B_RESULTS.md`), and the force family that was tried against it is closed on the scripted line — more demos of the same motion cannot convert it. |
| **VLASH** | negative twice (−31 pt on `moe_v11`; equal-or-below RTC on `moe_v10`), plus a fine-tune requirement and a new failure class. |
| **a wider trigger lateral gate** | P38: the class is 0.06 % of episodes and the reach residual at x = 0.16 is 8.3 mm — widening trades a no-fire for a grip-quality failure (P37 §"not the fix"). |
| **`FRUIT_SUBSTEPS`** | 2.25x force for 3.08x wall, and the class does not convert (P40 §C). |
| **the left arm (direct)** | it is at the **ceiling** of the carried class in every cell (0.889 / 0.800 / 0.882 / 0.733, P36 §4) — the same grip class, and no policy-side lever moves it. The left's direct rate (4-8 %) is a hardware class, not a checkpoint property. |
| **a new supply / density** | P1c: flat cadence, class-standardised flat, negative on a single-species pool. |
| **the ACQ knob as a shipped default** | R5 decision 4: measurement interface only, default off. |

---

## 4. Provenance and limits

* Every canary sample above is **one run**; the spread (5-8/10) is the record,
  not any single number. The P41 7/10 is the only sample on the current tree and
  it carries a **new-reason FAIL** on its reason clause.
* The direct A/Bs are all on **pre-P41** trees (the pinch was 4.4 N). No direct
  A/B has been run under the shipped 9.8-9.9 N profile; the park re-measurement
  (P43 phase 3) is the first, and it will also give the current-tree direct rate
  as a by-product.
* `moe_v12`'s 33/45 is a **W4 pinned-branch** number (lateral gate 0.06) on a
  pre-P32 tree; it is not comparable to a post-P32 direct run without its own
  control.
