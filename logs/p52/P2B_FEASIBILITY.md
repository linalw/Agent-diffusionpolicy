# P52 phase 2, lane B — offline feasibility: the reached-state check (E2) and PACE

Measured **offline** 2026-10-27 (no simulator, no `src/` edit, no commit). Tree HEAD
**`da0c914`**. Reproduce every number with

```bash
python3 logs/p52/p2b_feasibility.py            # ~2 min: one GPU pass + the stores
```

which writes `logs/p52/p2b_feasibility_out.txt` (315 lines) and re-uses
`logs/p52/p2b_chunks_abs.npz` (the absolute chunks; delete it or pass `--force` to
re-sample). Sections **A** the reached-state check, **B** the PACE feasibility
(B1 sampling, B2 the speed profiles, B3 the positive control, B4 the replans,
B5 the latency arithmetic, B5c the replay rate), **B6** the census corrections.

**Line numbers are cited at HEAD `da0c914` (`rl_env.py` md5 `93e35ef7`).** The
working tree's `rl_env.py` was being edited by lane A (`FRUIT_POLICY_TIME_SCALE`,
+313 lines) while this ran, so its numbers move; the code facts below are from the
committed file.

**Two reading rules.** (1) No count here is a rate: the stores are one attractor
each (AGENTS §2). (2) The measured objects are the per-tick and per-joint
quantities; a "residual" is always `commanded - achieved` in the units named.

---

## 1. (A) The reached-state check — is the policy supervised toward unreachable poses?

### 1.1 Where an achieved joint position exists offline

The action is **7 absolute joint positions** (`_apply`, `rl_env.py:3020-3045`), so
the question is asked in joint space. **`checkpoints/moe_v12/finetune_history.json`
names the supervision exactly**: `rollouts = datasets/demos_v11` (50 episodes,
9 378 windows) and `base = datasets/demos_v10` (154 episodes, 70 219 windows) - both
stores are the labelled stream the shipped checkpoint learned, and both are recorded
in the same 30 Hz `(action, joint_positions)` pair. The achieved state exists in the
following places only, and **not** in the plain logs:

| source | cadence | what it carries |
| --- | --- | --- |
| `datasets/demos_v10/*.npz` (154 episodes, **72 837 frames**) | 30 Hz | the **base half of the supervision**: `action` (the commanded 9-D target) beside `joint_positions` (the measured 22-D dof row), same tick |
| `datasets/demos_v11/*.npz` (50 episodes, 10 228 frames) | 30 Hz | the **fine-tune half** of the supervision, the same pair |
| `datasets/rl_rollouts/{p37_park,r9_awr}/*.npz` (90 + 56 episodes) | 30 Hz | the **policy's own applied commands** in the same pair (`_record_tick`, `rl_env.py:3767-3821`) |
| `logs/trace159/approach_*.json` (10 descents, 2 849 ticks) | **120 Hz** | the scripted descent's per-tick `command` / `measured` / `lag` / `task_err` / `limit_clipped` / `limit_margin` (`control.py:342-460`) |

The logs carry **no per-tick 7-joint readback**: the `[motion]` row carries the
*task-space* end gap (`motion.py:359-368`) and the `[acq]` row carries the TCP
close geometry plus `clip_min` (the joint-limit margin, e.g. `+2.3mrad@j2`), not
the joint row. `[attitude]` (P39) is one TCP pose per carry leg. So A rests on the
stores (supervision + policy) and on the descent traces (120 Hz).

The 22-D layout is interleaved (`rl_env.py:444-452`): left arm = dofs
`0,2,4,…,12`, right = `1,3,5,…,13` (verified: the wrong mapping returns 3 rad
residuals, the right one 0.01-0.2 rad, and the index's `arm` field agrees).

### 1.2 The per-joint residual (mrad), same tick and +1 frame

| stream | n | p50 per joint j1..j7 | p90 per joint | task-space p50 / p90 |
| --- | --- | --- | --- | --- |
| **demos_v10** (base half) | 72 837 | **11.3 2.8 4.3 0.6 3.6 7.1 5.4** | 46 42 33 93 59 41 54 | **1.3 mm / 15.7 mm** |
| **demos_v11** (fine-tune half) | 10 228 | **11.7 21.8 0.5 33.3 8.5 0.0 3.0** | 142 87 8 162 141 121 235 | **2.2 mm / 37.8 mm** |
| `p37_park` (policy, park era) | 3 364 | **83.7 71.9 50.0 87.9 67.6 33.1 77.7** | 220 194 166 270 251 138 359 | **19.3 mm / 67.3 mm** |
| `r9_awr` (policy, pre-park) | 3 261 | 50.7 41.9 23.3 57.9 42.9 24.2 37.0 | 176 152 85 205 144 90 130 | 11.1 mm / 43.9 mm |

Per-joint **max** (mrad): demos_v10 `139 149 86 186 178 177 257`, demos_v11
`289 170 149 270 256 504 560`, `p37_park` `2141 575 2789 792 2112 1059 2607` — those
tails are **mode jumps** (the grasp-config snap / a re-plan boundary), not tracking
numbers, which is why the p50/p90 pair and the hold subset below are the reading.

Task space is converted at the census's own lever (`logs/p44/CAP_CENSUS.md` §1.1:
"the measured 8.1-10.4 mm tool lag is ~30 mrad at a ~0.3 m lever").

### 1.3 The decisive subset: the HOLD frames

A "hold" is a frame whose command is stationary over ±1 frame (≤2 mrad on every
joint): the residual there is a **static reach/tracking error**, not a lead.

| stream | hold frames | p50 per joint (mrad) | task space |
| --- | --- | --- | --- |
| demos_v10 | **44 781 (61.5 %)** | **9.93 2.70 4.20 0.50 3.53 8.22 5.45** | **0.84 mm** |
| demos_v11 | **3 230 (31.6 %)** | **11.57 0.41 0.51 0.05 0.01 0.01 0.00** | **0.01 mm** |
| p37_park | 0 | — (the policy's command is never stationary at 30 Hz) | — |

So the **supervision's poses are reached**: with the command held - which is 61.5 %
and 31.6 % of the two supervision halves - every joint sits on it to **≤0.5-9.9 mrad
(≤3 mm at the tool)**, and the *whole* labelled stream has **0 out-of-range targets
in 581 455** joint values. The moving residual is the *label stream's own jumps* (the
scripted leg boundaries: 1.3-2.2 mm p50 but p90 15.7-37.8 mm, and 20.6-37.4 % of
joint-steps past the 5 mm-equivalent) that a 0.2 s drive cannot absorb inside one
33 ms frame.

### 1.4 Consequence: a reached-state relabel is a **low-pass of the labels**

RACE's relabel replaces each command with the state it reached. On this tree that
is, by the hold measurement, the identity on 61.5 % / 31.6 % of frames and a
15.7-37.8 mm p90 softening on the jumps. Note that the labels are **joint-space targets** (the recorded command), while
the 34-87 mm Cartesian shortfall (1.5) is the *IK's input*, not a channel of the
action space — so the frontier's premise (labels at an unattainable Cartesian pose)
has no purchase here.

### 1.5 The task-space residuals that do exist

* **`[motion] approach ... end=`** — the pad centre vs the pose the leg was sent to,
  over **11 703 descents in 1 026 logs**: **median 8.9 mm, p90 10.5 mm** (max 435 mm
  on the known outliers). This is the *settled* gap on the current tree.
* The **40-90 mm** figure the frontier and AGENTS §2 quote is that row on the
  **pre-arrive tree** (`logs/160_endgap028.log`: 42.1-89.7 mm; `logs/168...`:
  40.4-88.1 mm). It is not a current measurement.
* The **120 Hz traces**: pooled `|command - measured|` **p50 9.7 mrad, p90 85.7,
  max 233.3** (per joint p50 7.4 11.7 8.9 **58.7** 22.0 3.8 5.0), while
  `task_err@end` is **34.4-86.9 mm** with **0 joint-limit clips** and **≥119 mrad**
  of limit margin on every tick. That is the exact decomposition: the *joint* command
  is reached to ~10 mrad, the *Cartesian* aim is missed by 34-87 mm, and the miss is
  kinematic (workspace), not a joint limit.

### 1.6 Verdict on E2

* **E2 as stated — "the policy is supervised toward poses the arm cannot reach" — is
  DEAD.** The supervision is **0/581 455 out-of-range** and its held poses are reached
  to **0.84 mm (base half) / 0.01 mm (fine-tune half)**, with a moving p50 of 1.3-2.2 mm
  — inside the frontier's 5 mm kill. A relabel would rewrite a stream that is already
  the reached one and, at most, low-pass its jump tail (p90 15.7-37.8 mm) — a retrain
  to learn a filter that can be applied at execution for free.
* **A different defect is real and is on the policy side**: its **own** emissions are
  out of the joint range on **13.1 % of joint-steps (3 087/23 548), on 74.3 % of
  ticks** (j3 1 750, j2 981, j7 256), by a small overshoot (**2.8-3.2° p50, 8.2-8.6°
  p90, ≤21°**) while the measured joint sits **at the stop** (0.03° away on j3).
  There is **no clamp** on this path (`rl_env.py:3033-3040`; MODEL_CENSUS §1.5), so
  the drive pushes into the stop. But the residual is **65.2 mrad inside vs 64.0 mrad
  on those ticks**, so the stop is *not* the residual's mechanism: a clamp is a
  cheap, low-prior cell (see §4), not the fix.

---

## 2. (B) The PACE feasibility — would a phase-aware horizon do anything?

### 2.1 What was sampled

60 chunks on **direct-policy observations** (`p37_park`, 2 frames × 30 episodes) and
72 on demo observations (24 episodes × frames 40/90/140, the census's config), all
`moe_v12`, DDIM-16, `FRUIT_POLICY_SEED=11`. The census's `policy_chunks.npz` keeps
only `|delta|` magnitudes, so the **absolute** chunks had to be re-sampled
(`p2b_chunks_abs.npz`); the re-sample reproduces the cache's p99 to ~15 % but not its
single worst step (CUDA/DDIM sampling is not bit-reproducible), which is why §3 item 3
quotes the census's **own** cache rather than my draw. **The rate convention is the crux**: one
action is applied for **one control tick**, so the chunk's own rate is **120 Hz**
(§3 item 3). PACE's own thresholding was not readable from a primary source
(FRONTIER §6 item 8), so the rule below is *this note's*, stated and swept:
a step `k` is a transition when the max-joint speed is a local minimum below `tau`
with a ≥3× prominence over its ±2-step neighbourhood; the horizon is the first such
`k` (else 16).

### 2.2 The chunk's speed structure — there is none

| object | per-step p10 / p50 / p90 [rad/s] | within-chunk min p50 | `|2nd|/|1st|` | chunks with a transition, τ = 0.20 / 0.30 |
| --- | --- | --- | --- | --- |
| **direct-policy chunks** | **2.14 / 6.21 / 16.56** | 2.44 | **1.16** | **0/60 / 0/60** |
| demo-observation chunks | 0.73 / 2.75 / 6.33 | 1.24 | 0.84 | 3/72 / 5/72 |
| **the scripted stream** (positive control) | 0.00 / 0.42 / 1.74 | — | — | 22.4 % of its 16-step windows |

* The policy's chunks are **noise, not trajectories**: `|2nd diff| ≈ |1st diff|`
  (1.16) means there is no smooth path to retime, and the median within-chunk
  minimum (2.44 rad/s) is above any sensible "slow phase" threshold.
* **The positive control works**: on the scripted stream the same rule finds a
  transition in **22.4 %** of 16-step decision windows (19.5 low-speed plateaus per
  episode, median 4). So the rule is not broken — the *policy* carries no phase
  structure.
* **Why, structurally**: the policy's phase is the **belt-arrival wait** (2.0-2.2 s,
  §3 item 1); the approach / lift / place / release phases belong to the **scripted
  primitive**, which the policy does not drive. There is nothing in its chunk to
  segment, and 16 actions at 120 Hz (133 ms) is shorter than any phase
  (1.0-3.3 s) even if there were.
* At 120 Hz the chunks are also **at/over the joint-velocity limits**: the census's
  own cached deltas give an **executed** (first-3-step) p99 of **170 %/157 %** of the
  j3/j4 limit, and **10/1512 joint-steps over a limit at s = 1.0** (16 at 1.25, 33 at
  1.5); on the direct-policy chunks my re-sample reads 6.06 % over at s = 1.0. The
  census's 2.3-3.3× "headroom" is the 30 Hz artefact of §3 item 3.

### 2.3 The horizons and the replan count

The measured counts first. The census's "246-259 decisions/episode" is a misreading
(§3 item 1); the direct count is the `[loop]` row: **73, 62, 57, 77, 53 → mean
64.4**, cross-checked against the `[rl] episode` handover step (78-393, mean 252 =
63.9 decisions = **14 % of the episode's ticks**).

| rule | horizons | decisions/episode | wall (71 ms each) |
| --- | --- | --- | --- |
| shipped `execute_steps=4` | 4 | **64** | **4.57 s** of 28.6 s |
| PACE, policy chunks, τ = 0.20 | **16 everywhere** | **16** (−48) | **1.14 s** (−3.4 s, −12 %) |
| PACE if the chunks had the scripted boundary content (22.4 % at h=4) | 16 / 4 | 27 (−37) | 1.9 s (−2.3 s) |

The saving is **wall only**: the sim time, the handover step and the placements are
tick-clocked and do not move. And note the sign: where a boundary *is* found the
rule **shortens** the horizon (more replans), which is the frontier's intent — so
PACE can only add replans at boundaries or keep 16 where there is no boundary.

### 2.4 The latency arithmetic, and the census's "13 actions"

* A decision costs **71.0 ms** (policy 47.4 + render 20.0 + camera 3.6,
  `logs/p43/P2_RESULTS.md` §5.1) = **8.52 actions** of sim time, because **one
  action is one control tick = 8.33 ms**.
* Executing `h` of a 16-action chunk leaves `16 - h` actions of buffer, so a chunk
  in flight requires `h ≤ 16 - 8.52 = 7.48` → **h ≤ 7**. The shipped `h = 4` leaves
  12 actions = 100 ms = **1.4×** the decision cost (not 3×).
* The census's **13** is the same formula with **33.3 ms per action** (the *decision*
  period) instead of 8.33 ms: `16 - 71/33.3 = 13.87`. And the FRONTIER E3 sentence
  reads it as a **floor** ("`s` cannot go below ~13") when it is a **ceiling** — the
  direction is inverted twice.
* It also **does not bind this loop at all**: the shipped path is **synchronous**
  (RTC/VLASH default off, `runtime.py:100-124`), so no chunk is in flight while
  actions execute. `h = 16` is latency-free here; the only cost is staleness
  (0.12 m/s × 0.133 s = 16 mm of belt travel).
* Under lane A's re-timing `s` the bound becomes `h ≤ 16 - 8.52·s`: s = 1.25 → 5,
  s = 1.5 → 3 (only for an async form).

### 2.5 The finding the speed profile actually exposes: the replay rate

* The recorded stores hold **one frame per 4 control ticks** (`_record_tick` when
  `_observed_step == _step`, `rl_env.py:3771`; `_observe` at `_step % 4 == 0`, 2945),
  and the training chunk is **16 consecutive frames** (`policy/data.py:537`) =
  **533 ms** of demonstration.
* The loop applies **one action per control tick** (`act` → `_apply` → `advance(1)`,
  `rl_env.py:2979-2986`, 1716-1724), so the same 16 actions are replayed in
  **133 ms**. There is no hold; the drive target is overwritten every tick. The
  hybrid canary does the same (`60_eval_policy.py:445` steps one tick per loop,
  `:344` re-plans every `FRUIT_EXEC` = 4 steps), so this is both entry points.
* Measured consequence (max-joint speed, rad/s): demo stream **0.42 / 1.74**
  (p50/p90), emitted chunk **6.21 / 16.56**, **achieved joint motion 0.64 / 1.85**.
  The drive is a 0.2 s low-pass: it turns a **4× replay** of a 30 Hz-trained stream
  into a **10× dither** with a **19.3 mm p50** tracking error, and the arm's achieved
  rate is the demo's own. Nothing in the loop converts the extra command rate into
  motion.

---

## 3. The census errors this lane measured (all four are in `MODEL_CENSUS.md`)

1. **Decisions/episode**: `246-259` → **53-84 (mean 64)**. The `[rl] episode` row's
   `decision=` field is the **control step at which the primitive takes over**
   (`_run_primitive` `_decision_step = self._step`, `rl_env.py:3864`; read in
   `_finalize`, 3917), not a decision count. Consequence: the policy phase is
   **2.0-2.2 s (13-14 %)** of a 15.1 s episode, not 8.6 s (54-60 %) — and the belt
   floor the census itself computes (0.25-0.27 m at 0.12 m/s = **2.08-2.23 s**)
   already covers it, so the "6.4-6.8 s of arm motion a time-scale can touch" is
   **not 3-4× too large but ≈0**: the phase *is* the arrival wait.
2. **Chunk duration**: 16 actions × 1 tick = **133 ms**, not 533 ms (§1.3's
   "0.533 s planning horizon").
3. **The chunk's rate**: §2.3/§3.2 convert intra-chunk deltas at **30 Hz** (the
   recorded-frame rate) while the chunk is executed at **120 Hz**, so every
   intra-chunk speed and every headroom ratio is **4× too small**. From the
   census's **own** `policy_chunks.npz`, at the correct rate:
   the executed p99 is **51/46/170/157/41/26/30 %** of each joint's limit (its table
   says 5-43 %), so the p99 margin is **0.83×** at j4 (its "2.35×" executed /
   "3.34×" all-15 become **0.83×**), the worst single step is **3.5×** the limit (its
   "1.14×"), and the over-limit counts are **10/1512 at s = 1.0, 16 at 1.25, 33 at
   1.5** (its table: 0, 1, 1). An over-limit *command* is not an over-limit motion
   (the drive is a torque source), but the census's "1.25 and 1.5 sit inside the legal
   envelope" is only true of 2-3 % of the steps, not of the p99.
4. **The "13 actions" bound**: it is **h ≤ 7**, it is a **ceiling**, and it does not
   bind the synchronous shipped loop (§2.4).

---

## 4. Phase-3 recommendation (offline verdicts first)

* **Do not spend a PACE battery.** The hypothesis dies offline: 0/60 chunks carry a
  usable low-speed transition, the chunk is noise (`|2nd|/|1st|` = 1.16), and the
  phases PACE would segment are the *primitive's*, not the policy's.
* **Do not spend a reached-state recollection.** E2's premise is absent from the
  labels (0 out of range, 0.01 mm at hold); the relabel's whole content is a
  low-pass of the label stream's jump tail.
* **The one cheap cell this lane found: the action hold.** Register `h_sim` = 2 and
  4 ticks per action (the s < 1 direction, or a hold counter with
  `execute_steps = 16`) and measure, on the direct A/B (P43 protocol, N = 3 × 15):
  the per-tick lead residual (from the store's own pair), the achieved joint rate,
  decisions/episode (64 → 16 at 4), sim time, placed, cycle. **Kill**: the residual
  does not fall and the placed falls. Note lane A's `resolve_time_scale` currently
  **hard-errors on s < 1**, so this must be registered as a *hold*, not as a
  slow-down, to avoid a collision.
* **A joint clamp** (default off) is the only lever that acts on the 13 %/74 %
  out-of-range emissions; its prior is weak (65 vs 64 mrad in/out of range), so it
  is justified only if the acquisition class moves.
* **Order**: the hold cell first — it is the only lever that matches the training
  cadence, it is one knob, and it also *tests* the census's "the chunk is replayed at
  30 Hz" claim, which the code contradicts.

---

## 5. What this does **not** claim

* **No rate.** The stores are one attractor each; nothing here compares success
  across configurations.
* **No claim that the hold cell is faster.** It is a *measurement* of the replay
  rate; the sim time cannot fall (the belt floor sets the policy phase) and the wall
  fall is 3.4 s of 28.6 s at best.
* **No claim that the 4× replay is a bug of intent.** The code and the training
  stream disagree by 4×; which one the owner wants is a decision, and the discriminating
  measurement is named in §4.
* **The traces are the pre-arrive tree's** (`logs/trace159`), i.e. they measure the
  *scripted* descent's IK, not the policy's. They are used only for the per-tick
  decomposition (joint lag vs Cartesian aim), which the stores corroborate.
* **The joint-range table is P44's** (`CAP_CENSUS.md` §1.1) and was cross-checked
  against the measured ranges in both stores (the measured values sit inside it and
  pile up at j3 = ±90°, which is the stop the overshoots hit).

---

## 6. Files and pins

| artefact | md5 |
| --- | --- |
| `logs/p52/p2b_feasibility.py` | `e42eb9f2af19fee2de2b55046329b104` |
| `logs/p52/p2b_feasibility_out.txt` (315 lines) | `daa530413c0a77488260c5fd9012f22e` |
| `logs/p52/p2b_chunks_abs.npz` (72 demo + 60 direct chunks) | `7f1148990388bf7b6bdee0b32472e8ae` |
| `logs/p52/policy_chunks.npz` (the census's cache, unchanged) | `a852cdc6cb7ecf01724dd993d7f7eb45` |

Sources used: `src/fruit_sorting/rl_env.py` (HEAD `93e35ef7`),
`src/fruit_sorting/policy/data.py:537`, `src/fruit_sorting/control.py:342-460`,
`src/fruit_sorting/motion.py:359-368`, `datasets/demos_v10`, `datasets/demos_v11`,
`datasets/rl_rollouts/{p37_park,r9_awr,direct_zero_seed99}`, `scripts/60_eval_policy.py`, `logs/trace159/`,
`logs/160_endgap028.log`, `logs/168_accept_after_probe.log`,
`logs/p43/p2/l2_loop_timing_e5.log`, `logs/p43/p3/[AB]_*.log`,
`logs/p44/CAP_CENSUS.md` §1.1.
