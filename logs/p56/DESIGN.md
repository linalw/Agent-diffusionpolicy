# P56 DESIGN — the continuous supply + continuous sorting scenario

Phase 1 (offline). No simulator, no `src/` change, no commit. Owner's intent
(`.slim/deepwork/p52-model-lane.md` §9): *"规划候选果就是要连续输送果蔬和分拣场景"* —
a sorting cell whose belt never stops feeding and whose arm sorts fruit one after
another, instead of the direct env's **one fruit per episode**.

**Verdict in one paragraph.** The scenario the owner means is real and it is
**not** a throughput lever on this tree: the reset's own cost is **140 ticks =
1.167 s of sim per pick (6.4-6.7 % of the span)**, and 50-80 of those ticks are
*load-bearing* (the next pick must still start at the calibrated `grasp` pose, so
the teleport + settle cannot go). Continuity therefore buys **2.97-4.45 % of a
pick** in sim time (measured arm-switch rate 55-64 %), and it buys **nothing** on
the larger term: the arrival wait is **2.07-2.13 s = 13.5-14.4 % of the cycle** and
is unchanged by continuity. What the census *also* shows is that **the supply is
already stocked at every selection** (the belt is loaded to 72-99 % of the
release point in both the fed and unfed runs) — so "continuous feeding" is not
the missing ingredient either. The honest value of
`FRUIT_DIRECT_CONTINUOUS=<n>` is **scenario validity and accounting**: one
`done` per *n* picks, one reward, one logical episode, the belt never frozen —
which is what a deployment-facing evaluation and a real "sort a box of fruit"
task need. It should be pre-registered as a **non-inferiority** change with a
mechanical gap endpoint, never as a speed claim.

---

## 1. A — The episode lifecycle census (code sites)

### A.1 What `reset` does, and what a continuous mode must not repeat

`SortingRLEnv.reset` — `src/fruit_sorting/rl_env.py:2201-2571`. It runs in this
order, and the split between *world* state and *pick* state decides everything:

| # | site | what it does | must a continuous mode do it per pick? |
|---|------|--------------|------------------------------------------|
| 1 | `rl_env.py:2208-2214` | `_loop_*` timer reset (P43 L2 wall split) | **no** — accumulate |
| 2 | `:2215-2218` | `recorder.abort()` on a leaked episode | no (but `begin`/`finish` per pick, see A.3) |
| 3 | `:2219-2224` | `spawner.rng.seed(seed)` on the first episode only | **no** — once per run |
| 4 | `:2225` | `self._episode += 1` | **yes** — it is the recorder's npz index (A.3) |
| 5 | `:2234-2279` | the **feed loop**: `for _ in range(30): advance(1); spawner.update(); enforce_transport()` then `task.select_target(...)`, up to 40 rounds | **no** — with the feeder live the belt is already stocked; 30 ticks/pick |
| 6 | `:2280-2298` | `_sample/_active/_bin_index/_goal/_belt_rest` from the target (grade A → left, else right) | **yes** |
| 7 | `:2311-2329` | **both arms** teleported to `ready`/their park, then the **active arm** to `grasp` — 3 × `teleport_joints(settle=30)` (`control.py:552`) = 90 ticks | **partly** — the active arm to `grasp` is mandatory (it is the demos' frame 0); the inactive-arm park only when the arm switches |
| 8 | `:2330-2345` | gripper `OPEN`, written to **both** the commanded and the measured dof (the policy reads the finger channels as its wait/close cue) | **yes** |
| 9 | `:2346` | `advance(_reset_settle)` = 20 ticks (`FRUIT_RESET_SETTLE`, `:1247`) | **yes** — the teleport must settle |
| 10 | `:2349-2354` | `_expert_jaw_y`, `_trigger_station` measured at the post-settle grasp pose | **yes** — the trigger's station is per-pick |
| 11 | `:2355-2356` | `spawner.belt.start()` | **no** — once |
| 12 | `:2381-2384` | `policy.reset()` (**clears the 2-frame obs horizon**, `policy/runtime.py:698`) and `rtc.reset()` | **yes** — see A.3 |
| 13 | `:2386-2550` | ~45 per-episode bookkeeping fields (`_tick`, `_step`, `_grasp_done`, `_notes`, `_x_refused`, the P38 refusal latch, the DAgger buffers, the diag buffers, …) | **yes** — a stale field is a silently different experiment |
| 14 | `:2428` | `_episode_t0 = sim_time()` — the pick's clock | **yes** |
| 15 | `:2430` | `spawner.protected = target index` (the feeder must not recycle the target) | **yes** |
| 16 | `:2555-2568` | `recorder.begin({... "index": self._episode ...})` | **yes** |
| 17 | `:2570` | `_observe()` (first head-camera frame) | **yes** |

**The prompt's premise needs one correction, and it is the good news:** `reset`
does **not** rebuild the belt and does **not** re-create the pool. Both are
process-scoped, built once in `__init__` — `spawner.create_pool()` at
`rl_env.py:1627` and `spawner.prime(count=6)` at `:1632` (the only two call sites
in `src/`). So **the world is already continuous**; what is discontinuous is
(a) the *release schedule*, because `spawner.update` was only ever called from
the reset's feed loop (`:2239`), which is exactly what P55's
`FRUIT_DIRECT_FEED` block in `advance` (`:2167-2196`) fixed, and (b) the
*episode*, which is one pick.

Measured consequence of (a): in the **unfed** 12-pick run the release schedule
runs on `30 ticks × 12 = 360` of `23 103` ticks = **1.56 % of the sim span**; in
the **fed** run it runs on **100 %** (every `advance`). That is the whole of the
"one burst per episode" phenomenon.

### A.2 What `act`/`_finalize` do at the end of a pick, and what re-targeting needs

`act` — `:3428-3542`. Per control tick: `_observe()` every 4th step (`:3457`),
`_apply(action, index)` (`:3503`), `_record_tick()` (`:3507`), `advance(1)`
(`:3508`), `enforce_transport()` (`:3516`), `_tick += 1` / `_step += 1`
(`:3515-3517`), `_episode_events()` (`:3519`), and the horizon test
`_tick >= reward.horizon` → `_finalize(timeout)` (`:3521-3527`).

The pick ends **inside the scripted primitive**, not in the policy:
`_apply`'s fire decision (`:3837-3874`) calls `_run_primitive()` (`:4498`), which
runs `task.grasp_carry_place(active, sample, bin_index, result)` (`:4512`) — the
whole grasp → lift → carry(**place**) → release sequence — then sets
`_grasped/_placed/_lifted` and calls `_finalize(notes)` (`:4532`).

`_finalize` — `:4550-4722`:
- `_ticks = round((sim_time() - _episode_t0) * 120)` (`:4553`) — **per-pick clock**;
- `success = _lifted and cfg.on_output_belt(final_position)` (`:4560`);
- `reward = self.reward.compute(success, decision)` (`:4561`) — `RewardConfig`
  (`:767-791`): `1 - 0.2·T/1500` on success, else 0, **terminal only**;
- the `_outcome` dict (`:4563-4588`) — which is what `StepResult.info` returns and
  what `StepResult.reward` reads (`_step_result`, `:4905-4912`);
- `recorder.finish(...)` (`:4628`);
- `spawner.protected = None` (`:4637`) and **`_done = True`** (`:4638`).

There are **four** `_finalize` call sites, and a continuous mode has to decide
each: the primitive's normal end (`:4532`), "fruit fell off the line"
(`_episode_events`, `:4475-4478`), the P38 `no firable fruit` terminal
(`:4175`), and the scripted ablation (`:4542/:4548`). In a continuous cell a lost
fruit ends **the pick**, not the run.

**What re-targeting the next candidate mid-episode actually needs** (nothing
more): after the primitive returns, instead of `_finalize` → `_done`,
1. clear `spawner.protected` (`:4637` is where it clears today);
2. `target = self.task.select_target(self.spawner.state(), reach_anywhere=False,
   direct=True)` — **the same call as `:2270-2272`**; it already rejects fruit on
   the output conveyors and above the main belt (`tasks.py:5709-5727`), so the
   fruit just placed cannot be re-picked, and it applies the same
   `_dynamic_select_floor` (`tasks.py:5959-5992`, ≈ 0.40 m at 0.12 m/s) so the
   new pick starts at the same belt geometry as today;
3. run the per-pick part of `reset` (`:2280-2570`) — the teleport + settle + the
   trigger station + the bookkeeping + `policy.reset()` + `recorder.begin`;
4. keep going (`_done = False`).

### A.3 The policy's observation/state and the episode boundary

- **The obs history is the only load-bearing policy-side boundary.**
  `_observe()` (`:2576-2630`) renders the head camera and calls
  `policy.push_frame(...)` (`:2630`); `PolicyRunner` keeps a 2-frame horizon
  (`obs_horizon=2`) and `PolicyRunner.reset()` (`policy/runtime.py:698-699`)
  empties it. `proprio()` (`:2632`) is **live** (22 joints + the active arm's
  finger + 2 tactile), so it has no episode state. **If a continuation keeps the
  history**, pick *k+1*'s first chunk is conditioned on pick *k*'s carry/place
  frames — a state no demonstration contains (the demos start at `grasp` with
  `|q-grasp| ≤ 0.011 rad`). That is the OOD risk, and it is removable at zero
  cost: **call `policy.reset()` per pick** (as `reset` does). With it, the
  per-pick observation stream is the same distribution as today's; only the
  bookkeeping is shared.
- **The recorder is safe only if the index increments per pick.**
  `RolloutRecorder.finish` names the file `rollout_{meta['index']:05d}.npz`
  (`:1042`) from the index captured in `begin` (`:2558`). Two picks under one
  index would **overwrite the first npz** and the store would silently lose
  every pick but the last. With `self._episode += 1` per pick (today's `:2225`)
  one run dir holds *n* episodes, `index.json` gets *n* rows, and **no recorder
  code changes**. (A single-episode n-pick session would need a `pick` field and
  a schema change — avoid.)
- **The reward and the horizon are per pick.** `_tick` (`:2386`) and
  `_episode_t0` (`:2428`) must reset, or pick 2 inherits pick 1's ticks and the
  1500-tick horizon cuts it short; `_outcome` must be cleared, or
  `StepResult.reward` returns the *previous* pick's reward (`:4909`). The
  episode-level numbers (`reward_total`, `picks`, `picks_placed`,
  `ticks_total`) go in `_outcome["continuous"]` and are printed once at the real
  end.
- **The trigger has per-episode state** that must be cleared per pick or a
  pick-2 refusal is silently suppressed: `_trigger_station` (`:2354`),
  `_x_refused` / `_gate_refused` (`:2406-2409`), the P38 latch
  (`_refuse_latch`, `_refuse_count`, `_policy_close_seen`, `_policy_best_gap`,
  `:2412-2426`), `_notes`.

**Net: the reset is load-bearing for the policy only through `policy.reset()`
and the `grasp` re-pose — both of which a continuation keeps. It is *not* a
large refactor.** The refactor is mechanical: split `reset` into
`reset = (loop timer, seed, episode++, select) + _begin_pick(target)`, and add a
continuation branch in `_finalize`. ~150 lines, one knob, direct-presentation
only.

---

## 2. B — The continuity census (measured)

`logs/p56/continuity_census.py` → `logs/p56/CENSUS.txt`. Sources: the two
12-pick direct recordings, `logs/p54/video_fed` (`FRUIT_DIRECT_FEED=1`) and
`logs/p54/video_continuous` (shipped), both `moe_v13s` `61da390a`, seed 77,
`execute_steps=4`, `acq=on`, `park=back` — i.e. one knob apart, but **different
fruit streams** (the feeder changes the RNG draw count), so per AGENTS §2 they
are two branches and no rate delta is quoted.

| quantity | fed | unfed |
|---|---|---|
| episodes / picks | 12 | 12 |
| ticks per pick (min/median/max) | 1639 / 1888.5 / 2448 | 1675 / 1786 / 1920 |
| **inter-attempt gap** | **140, 140, …, 140** (11/11) | **140, 140, …, 140** (11/11) |
| gap as share of the span | 6.39 % | 6.67 % |
| extra feed rounds (starvation) | **0/11** | **0/11** |
| stocked depth at selection (median) | 0.583 m (86 % of `spawn_y` 0.68) | 0.572 m (84 %) |
| stocked depth (min…max) | 0.491…0.675 | 0.517…0.641 |
| arrival wait `t_arrive` (median) | 2.07 s (13.5 % of the cycle) | 2.13 s (14.4 %) |
| arm switches between picks | 7/11 (64 %) | 6/11 (55 %) |
| `spawner.update` coverage | **100 %** of ticks | **1.56 %** (360 / 23 103) |
| placed | 7/12 | 8/12 |
| placed/min (sim, span **incl.** the gaps) | 2.09 | 2.49 |
| wall / pick | 37.7 s | 34.0 s |
| sim/wall | 0.444 | 0.473 |

Readings:

1. **The gap is exactly 140 ticks and it is structural, not supply-dependent.**
   Both runs, every transition. It matches the code arithmetic to the tick:
   **30** (feed round) + **3 × 30** (`teleport_joints(settle=30)`: two arm parks +
   the active arm to `grasp`) + **20** (`_reset_settle`) = **140**. 1.167 s of
   sim, ~2.5 s of wall at the measured 0.44-0.47 sim/wall.
2. **There is no starvation.** All 11 gaps are exactly 140, so the selection loop
   broke at **round 0** every time — the reset never waited for fruit.
3. **The belt is already stocked at selection, in both runs.** The direct
   selector is the shipped farthest-upstream rule (`select_target(...,
   direct=True)` → `_balance_arm`, `tasks.py:5900`), so the episode line's `y=` is
   the *most upstream* usable fruit's position, i.e. the stocked depth. It reads
   0.491-0.675 against the release point `spawn_y = 0.68` (`assets.py:236`):
   **72-99 % of the release band is loaded**, median 86 % (fed) vs 84 % (unfed).
   The live feeder moves the median **+11 mm** — nothing.
4. **The dominant per-pick wait is the arrival, not the reset.** `t_arrive`
   median 2.07/2.13 s = **13.5-14.4 %** of the cycle (≈ 250 ticks), against the
   reset's 6.4-6.7 %. Continuity does not touch it: the next candidate is
   selected at the catch floor (~0.40 m = 3.3 s of travel) either way.
5. **The feeder's own cost is measured and it is negative:** +11.1 % wall
   (452.7 vs 407.5 s, i.e. 2.25 vs 2.12 s wall per sim-second) for **no** stock
   gain and a different branch. That is the P32-C live-body cost class again.
6. **What the reset/feed costs, and what continuity can remove:**

   | block | ticks | removable by continuity? |
   |---|---|---|
   | the feed round (select from a live belt) | 30 | **yes** |
   | the inactive arm's park | 30 | only when the arm does **not** switch |
   | the active arm → `grasp` (demos' frame 0) | 30 | **no** |
   | the settle after the teleport | 20 | **no** |

   → same-arm continuation 50 ticks, **saves 90 = 0.75 s = 4.45 %** of a pick;
   arm-switch continuation 80 ticks, **saves 60 = 0.50 s = 2.97 %**. With the
   measured 55-64 % switch rate the expected saving is **~3.5 %**, i.e.
   **placed/min ≈ +3.5 % at best**, and only if nothing else moves.

**Do not read the fed 7/12 vs unfed 8/12 as a rate.** Different fruit sequences
(pear/tomato/kiwi vs apple/peach/orange), 12 picks each.

---

## 3. C — The design: `FRUIT_DIRECT_CONTINUOUS=<n_picks>` (default off)

### 3.1 Semantics

One **logical episode = n picks**. Inside it: the belt never stops, the feeder
runs every tick, the pool and the world are untouched (they already are), the
policy is re-primed per pick, the reward and the outcomes accumulate. `done` is
returned once, at pick *n* (or when the belt can no longer present a candidate).

### 3.2 The minimal change (seven edits, six in `rl_env.py`)

1. **The knob** (beside `_direct_feed`, `:1146-1154`):
   `self._continuous_picks = int(os.environ.get("FRUIT_DIRECT_CONTINUOUS", "0"))`
   — raise unless `presentation == "direct"` and `ablate == "none"`; and
   `self._direct_feed = self._direct_feed or self._continuous_picks > 0`
   (the mode implies P55's feeder; the two knobs must not be separable or the
   A/B measures two things).
2. **Factor `_begin_pick(target_state) -> dict`** out of `reset`: rows 4 and 6-17
   of the A.1 table (`:2225`, `:2280-2570`). `reset` keeps rows 1-3 and 5 (the
   loop timer, the recorder abort, the seeding, the 30-tick × rounds
   feed/select loop) and returns `self._begin_pick(target_state)`. Moving
   `self._episode += 1` into `_begin_pick` is what keeps the recorder's npz index
   unique per pick (A.3/R3).
3. **Continue in `_finalize`** (before `_done = True`, `:4638`): if the mode is
   on, `self._picks_done + 1 < self._continuous_picks`, and this is not a
   scripted ablation → **still print the outcome row** (the `[rl] episode N: …
   success= … notes=[…]` line at `:4644-4651` is what `scripts/113_rl_report.py`
   and `logs/p54/p54_report.py` parse — one outcome row per pick, never zero and
   never two), *then* accumulate (`_picks.append({...})`,
   `_episode_reward += reward`), `spawner.protected = None`, re-select with the
   same `select_target(...)`, and on a candidate `self._begin_pick(target)`,
   `self._done = False`, **return** — skipping only the *episode-level* rows
   (`[loop]`, `[cont]`, the diag summaries), which belong to the real end. If
   `select_target` returns `None`, append
   `"continuous: no candidate on the belt; ending the episode"` and fall through
   to the real end — **never raise** (the reset's `RuntimeError` after 40 rounds
   is not available mid-episode).
4. **Clear `_outcome`** in `_begin_pick` so `StepResult.reward` cannot return the
   previous pick's value (`:4909`).
5. **The summary row**, printed once at the true end when the mode is on:
   `[cont] episode {n}: picks={k}/{n} placed={p} reward={Σ} ticks={Σ} gap_ticks={mean}`
   — plus, in `_outcome["continuous"]`, `{"picks", "picks_placed", "reward_total",
   "ticks_total", "gap_ticks"}`. `StepResult.reward` for a pick stays that pick's
   own reward (so a per-pick consumer is unchanged); the episode total is in the
   info dict.
6. **The census the current logs lack — and it already exists.** `select_target`
   takes a `diag: list` (`tasks.py:5576`) and `bed_diag_report(attempt, diag)`
   (`tasks.py:5469-5518`) prints one `[bed-sel]` block per selection with
   `live`, `on_belt`, `admitted`, **`window` (= the candidates at/above the catch
   floor, i.e. `usable`)**, `pick=<fruit>@<along>`, and a per-row
   `along/x/z/grade -> reason`. The scripted driver already does this in three
   lines (`scripts/20_pick_place.py:232-235`). The direct env simply never passes
   `diag` — so the fix is to pass `diag = [] if FRUIT_BED_DIAG else None` at
   `rl_env.py:2270-2272` (and in the continuation) and call `bed_diag_report`.
   **No new format, and `scripts/215_p32_phase_a_report.py`'s parser applies.**
   It must be enabled in **both** arms (AGENTS: instrumentation is part of the
   measurement). Without it, "the belt stock stays > K" is not measurable — that
   is today's instrumentation gap, and it is a finding of this census.

7. **The driver's episode count.** Arm B is **`--episodes 1`** with
   `FRUIT_DIRECT_CONTINUOUS=15` (one episode = 15 picks); `--episodes 15` on the
   same env would deliver 225 picks. That belongs in the batch driver as an
   assertion (`picks_seen == 15`), not in a comment.

### 3.3 Scope

`presentation == "direct"` **and** `ablate == "none"` only; no `FRUIT_BIARM*`, no
collector, no `60_eval_policy` (the hybrid canary never constructs
`SortingRLEnv`); the two-line, scripted, hybrid and collector paths never read
the knob. `policy.reset()` and `rtc.reset()` stay **per pick**. The reward config
is unchanged.

### 3.4 Risks

- **R1 — the policy's OOD (the only real one).** Removable and therefore
  mandatory: `policy.reset()` per pick. If it is dropped (a "smoother" stream) the
  policy conditions on the previous pick's carry frames and every number becomes a
  new experiment. Pre-registered as falsifier F2.
- **R2 — the trigger's per-pick state.** `_trigger_station` must be re-measured
  after the continuation's settle, and `_x_refused/_gate_refused/_refuse_*` must
  be cleared, or refusals are suppressed across picks (`:2406-2426`).
- **R3 — the recorder.** The npz name is the episode index (`:1042`); the index
  **must** increment per pick or picks silently overwrite each other.
- **R4 — the branch.** Turning the feeder on changes the fruit sequence (AGENTS
  §2): one continuous run is one draw; the mechanical endpoints (gap, stock,
  reward sum, the grasp-pose check) are the ones that carry.
- **R5 — the wall.** The feeder costs +11.1 % wall (measured); the mode inherits
  it, and any wall saving from the 60-90 fewer ticks is inside that noise.
- **R6 — the `protected` scalar and the diverter.** `spawner.protected` must move
  to the new target; `task.failures` accumulates per fruit across picks, so a
  fruit that failed twice is diverted (`tasks.py:5699`) — the same rule as today,
  but now inside one episode.

### 3.5 The fallback (if the re-target is judged too invasive)

**The "no-rebuild reset" — and it is already shipped.** Because `reset` never
rebuilds the belt or the pool, `FRUIT_DIRECT_FEED=1` + the existing driver loop
(`scripts/121_policy_video.py:308-320`, `scripts/110_rl_rollout.py:257-264`) *is*
a continuous-supply cell: the belt streams for 100 % of the run, the pool is the
same 16 bodies, nothing is reconstructed between picks. The only things it lacks
are (i) the 60-90 ticks of the per-pick re-pose path, (ii) the logical n-pick
episode (one reward / one recorder episode), (iii) the mid-pick re-selection.
**If P56's gate is not funded, this is the cheapest honest alternative and it
needs no code at all** — but its own A/B (fed vs unfed, the same seeds) is the
*prior* measurement, because the census already shows the feeder does not raise
the stock at selection and costs +11.1 % wall.

A second-order alternative, if even the feeder A/B is not funded: change nothing
and record that the direct interface's "one fruit per episode" is a
**scenario property**, not a defect — the cell's cycle is 15.7 s of sim of which
the reset is 1.167 s and the arrival wait 2.5 s.

---

## 4. What this phase did **not** do, and why that is the honest bound

- It did not build the mode (offline phase; the PREREG in `logs/p56/PREREG.md`
  is the gate).
- It did not re-measure the feeder A/B (P55's own named next step). The census
  gives it a *prior*: stock +11 mm, wall +11.1 %, different branch.
- It did not claim a rate. The two source runs are different attractors.
- The **throughput ceiling of the continuous mode is +3.5 % (2.97-4.45 %)** in
  sim time, and **~0** in wall. Any PREREG that asks for a speed gain is asking
  for something the code cannot deliver; the gate is non-inferiority + the
  scenario properties.

## 5. Files

- `logs/p56/DESIGN.md` — this file.
- `logs/p56/PREREG.md` — the phase-2 pre-registration (arms, endpoints,
  falsifiers, N, cost).
- `logs/p56/continuity_census.py` — the census (offline, reads only the two
  `video.json`s and their logs).
- `logs/p56/CENSUS.txt` — its output.
- Sources read: `src/fruit_sorting/rl_env.py` (`:1146-1154`, `:1247`,
  `:1626-1632`, `:2158-2196`, `:2201-2571`, `:2576-2630`, `:3428-3542`,
  `:3837-3874`, `:4464-4496`, `:4498-4532`, `:4550-4722`, `:4905-4912`),
  `src/fruit_sorting/policy/runtime.py:698-722`,
  `src/fruit_sorting/tasks.py:5699-5922`, `:5959-5992`,
  `src/fruit_sorting/control.py:552-569`, `src/fruit_sorting/assets.py:236-240`,
  `src/fruit_sorting/fruits.py:1597-1703`, `:1862-1881`,
  `scripts/121_policy_video.py:308-320`, `scripts/110_rl_rollout.py:257-264`,
  `logs/p54/video_fed{,.log}`, `logs/p54/video_continuous{,.log}`,
  `WORKLOG.md` "P55", `.slim/deepwork/p52-model-lane.md` §9.
