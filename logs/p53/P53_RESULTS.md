# P53 — the policy's own emission defect: the joint clamp (C1) and the action hold (C2)

Measured **2026-10-28** on the P43 direct protocol. Two default-off cells, one
battery (N = 3 runs x 15 episodes per arm, seeds 77/101/202, one claim, wall
**4211 s**). Registered in `logs/p53/PREREG.md` **before** the battery's first
arm finished.

**The four sentences this phase exists to support.**

1. **C1 removes the defect completely and buys nothing.** The policy's emissions
   are out of the joint range on **10.9 % of joint-steps (8 341 of 76 587) on
   65.0 % of the applied ticks**; the clamp makes that **0 of 70 938** at zero
   time cost (wall/episode 29.5 -> 28.9 s, ticks 15.30 -> 15.07 s) - and the
   placements read **30/45 -> 29/45** (per run `+1/-1/-1`, the right arm
   **29/30 -> 28/28**). **E1 PASS** (no-harm, no new reason), and the overshoot
   was **not** the binding term.
2. **C2 halves the decisions and the wall, and does not buy placements.**
   `action_hold=2` reads **61.2 -> 28.9 decisions/episode (-53 %)** and
   **29.5 -> 27.4 s wall/episode (-7.1 %)** at a flat sim time (15.30 -> 15.24 s),
   with **26/45** placed (per run `0/-1/-3`). **E2 FAIL** on its registered bar.
   On the arm the cells act on it is **flat, not worse**: right **26/26** vs T0's
   29/30, and **arm-standardised at T0's own mix the count is 30.0/45 vs
   30.0/45** - the pooled loss is the **left's closed `cnp` class** taking more
   of the 45 slots (T0 15 left attempts, C2 19).
3. **The mechanism is a measured correction to P2B §2.5.** Halving the command
   rate lowers the achieved arm rate **16 %** (0.87 -> 0.73 rad/s, same 30 Hz
   grid), so the "10x dither" is **not free**: it is (partly) the motion. The
   same-tick residual falls 21.8 -> 17.1 mm p50, but the residual at a *fixed*
   command step is flat-to-worse and nothing converts into achieved speed.
4. **F1 fires: the model lane's emission path is exhausted.** Both cells are
   null on placements, one of them free. What remains on the right arm's ~5 % is
   the **scripted close/handover/grip** class (P35-P43), not the policy's
   targets.

---

## 1. What was registered

`logs/p52/P2B_FEASIBILITY.md` §1.6: the policy's own emissions are out of the
joint range on **13.1 % of joint-steps, on 74.3 % of ticks**, with **no clamp**
on the direct path, while its same-tick task-space residual reads **19.3 mm
p50**; §2.5 names the mechanism (the training stream is 30 Hz, the loop replays
it at 120 Hz) and registers the **action hold** as the one cheap cell; §4 names
the **clamp** as a "cheap, low-prior cell" justified only if a class moves.

| cell | knob (default off) | what it does | cost |
| --- | --- | --- | --- |
| **C1** | `FRUIT_POLICY_JOINT_CLAMP=1` | clip the 7 absolute joint targets into the arm's **own** `arm_lo`/`arm_hi` (one `get_dof_limits()` read at construction, `control.py:197-202`), after the A2C2/track shapers and before `set_dof_position_targets` | zero |
| **C2** | `FRUIT_POLICY_ACTION_HOLD=2` | each chunk waypoint held for 2 control ticks (`np.repeat` the chunk, so the shipped `arr[index]` lookup stays the lookup) = 60 Hz command, 8 ticks/decision | 2x ticks/decision, half the decisions |

Battery: the P43 protocol verbatim (`checkpoints/moe_v13s` `61da390a` on all
arms, the W6-A/W8-A patch sheet, balanced A:B:C, trigger `arrival` + lead 0.9 +
`ACQ=1`, `FRUIT_DYNAMIC_PICK=1`, the P43 park default `back`), N = 3 x 15,
interleaved **T0 -> C1 -> C2** per seed. Instruments on **all three arms**
(AGENTS §3b): `FRUIT_ACQ_DIAG`, `FRUIT_CARRY_DIAG`, the new `FRUIT_EMIT_DIAG`
(one `[emit]` row per episode) and `--record` (the same-tick
`(action, joint_positions)` pair for the dither). Stores live in
`/tmp/opencode/p53/raw` (2.0 GB, `logs/` stays textual); the nine manifests of
record are copied to `logs/p53/p3/manifests/`.

The manifests identify the arms by themselves:
`emit: null` (T0) / `{joint_clamp: true, action_hold: 1, ticks_per_decision: 4}`
(C1) / `{joint_clamp: false, action_hold: 2, ticks_per_decision: 8}` (C2), with
`arm_park: {name: back, defaulted: true}` on all three.

## 2. The shipped path is byte-identical

Three independent proofs, because the direct loop conditions on rendered frames
and is **not** bit-reproducible (AGENTS §3b), so no ordinary run can show it:

1. **Offline algebra** (`scripts/229_p53_emit_selftest.py`, 104 checks, a
   selfcheck leg): both resolvers return the shipped constants when unset; the
   clamp helper is **element-identical inside the range** (signed zeros
   included) and **never edits its input** (it returns a copy, because a float64
   chunk row would otherwise be rewritten in place); `hold_index(t, 1) = t`; and
   the shipped `action = arr[index]` survives verbatim in `act` (the hold
   `np.repeat`s the chunk instead of re-indexing the lookup), the clip is the
   last shaping before the drives, behind `if self._joint_clamp:`.
2. **The deterministic vehicle this tree has for this loop** - `--ablate zero`
   applies a fixed chunk and conditions on no rendered frame, so it *is*
   bit-reproducible (WORKLOG "The hybrid loop's variation is the rendered
   frames"). The pre-edit and post-edit runs (`logs/p53/00_id_pre.log`,
   `01_id_post.log`, the same 2-episode seed-77 command) compare
   **47/47 `[fruit]` lines identical**, both `[rl] episode` rows included (same
   1 849 ticks, same trigger geometry), modulo the manifest path and the
   wall-clock stamps. The manifest gains one null key (`"emit": null`) and the
   new `rl_env.py` md5 - provenance, not a behaviour change.
3. **The tree-level no-harm**: `scripts/selfcheck.sh` PASS 0 failures (with the
   new P53 leg) and the scripted acceptance
   (`logs/p53/03_accept_noharm.log` + the run copy
   `logs/p53/03b_accept_noharm_run.log`) reads **6/10, 15.0 s/attempt,
   `diverted=0`, `gate_open=0.0 s`, `fingerprint: matches
   configs/motion_reference.json`** - the shipped tree's own recorded state -
   with its **377/377 `[fruit]` lines byte-identical** to both the P42 same-tree
   control and the P44 s5 control (excluding the `[cycle]` rows those runs
   printed and this one did not). The gate's `FAIL: success 6/10 below 75 %` is
   the expected rate-only verdict of this tree (P32-P44 record it identically);
   `rl_env.py` is not imported by the scripted line, so this is an **import
   guard**, stated as such (the P38-M4/P43 convention).

## 3. The battery

Nine runs, 135 episodes, no wedge (all `exit=0`, 15/15 episodes and 15/15
`[emit]` rows in every log, so the registered "retry once" clause was never
used). Wall 4211 s. Files `logs/p53/p3/{T0,C1,C2}_{1,2,3}.log`, the report
`logs/p53/p3/P53_report.txt` (`logs/p53/p53_report.py`), the independent
cross-checks `P53_113_T0_{C1,C2}.txt`.

`113_rl_report.py` exits **1** on both contrasts, and that is its own verdict
branch ("no measured improvement"), not a parser failure: its tables, the paired
counts, the per-class rows and the reason sets all print (`P53_113_T0_{C1,C2}.txt`).
Two independent reports plus the raw `[rl] rollout success N/15` lines agree on
every count.

## 4. Results

### 4.1 Placements

| arm | pooled | right | left | cnp | no-grasp | per run | delta vs T0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **T0** | **30/45** | 29/30 | 1/15 | 14 | 1 | 11, 10, 9 | - |
| **C1** | **29/45** | **28/28** | 1/17 | 16 | 0 | 12, 9, 8 | `+1, -1, -1` (sum **-1**) |
| **C2** | **26/45** | **26/26** | 0/19 | 19 | 0 | 11, 9, 6 | `0, -1, -3` (sum **-4**) |

Read it as **two arms, not one count**. The **right arm** - the arm the park
made work (P43) and the only one with headroom - reads **29/30, 28/28, 26/26**;
every difference there is one episode (Fisher p = 1.0 in both contrasts). The
**left arm** is the closed loaded-slide class (`logs/p42/SIM_LIMIT.md`): 1/15,
1/17, 0/19. So:

| arm | right rate | left rate | 50/50 standardised | at T0's mix (left 33.3 %) |
| --- | --- | --- | --- | --- |
| T0 | 96.7 % | 6.7 % | 0.517 | 30.0/45 |
| C1 | 100 % | 5.9 % | 0.529 | **30.9/45** |
| C2 | 100 % | 0 % | 0.500 | **30.0/45** |

**The pooled deltas are the arm mix**: the share of the 45 episode slots the
left takes moved 15 -> 17 -> 19, and on this non-reproducible loop the episode
stream is a branch outcome, not a controlled variable (P37/P43 precedent: "the
pooled rate is an arm-mix artifact"). Arm-standardised, **C1 +0.9/45 and C2
+0.0/45** - both flat.

Failure classes: T0 `{cnp: apple 4, pear 6, peach 2, kiwi 1, orange 1;
no-grasp: lychee 1}`, C1 `{cnp: apple 5, pear 7, orange 2, peach 1, kiwi 1}`,
C2 `{cnp: apple 3, peach 4, pear 8, kiwi 2, orange 2}`. `113_rl_report.py`'s
digit-normalised note keys are a **strict subset** of T0's in both contrasts
(T0's extra key is `fruit did not follow the gripper` from its one no-grasp):
**no new failure reason in either arm**. The paired test is uninformative by
construction - 29/45 pairs excluded (fruit class differs) and **0 discordant
pairs** among the survivors.

### 4.2 The emission census (the `[emit]` rows)

| arm | episodes | applied ticks | decisions | per episode | out-of-range joint-steps | on ticks | largest overshoot |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T0 | 45 | 10 941 | 2 752 | **61.2** | **8 341/76 587 = 10.9 %** | **65.0 %** | 1.350 rad (77 deg) |
| C1 | 45 | 10 134 | 2 551 | 56.7 | pre **7 832/70 938 = 11.0 %** -> **post 0/70 938 = 0.0 %** | 68.4 % | 1.017 rad |
| C2 | 45 | 10 250 | **1 301** | **28.9** | 8 830/71 750 = 12.3 % (unchanged: no clamp) | 69.8 % | 0.587 rad |

* **The defect is real and reproducible**: 10.9 % of joint-steps over 45 episodes
  on the shipped arm, in the census's order (its 13.1 % is the `p37_park` +
  `r9_awr` stores; this is the patch sheet with `moe_v13s`). The `over_max`
  1.35 rad is a **mode snap** (a target a whole joint range away), not the
  typical overshoot - the census's 3-9 deg p50 and the store's p90 below are the
  typical read. Note the arithmetic: the **4.8 %** a single C1 episode prints
  (`out_pre=101/2093`) is that episode's policy phase; the 45-episode corpus
  reads **10.9-11.0 %**, which is the number to quote for the defect.
* **C1 removes it exactly**: `out_post = 0` in all 45 episodes, while its `pre`
  count (11.0 %) matches T0's (10.9 %) - the same policy, the same suppression,
  so the check is that the clamp's input is the shipped stream. Zero time cost.
* **C2 halves the decisions**: 61.2 -> 28.9 per episode, i.e. **8.0 ticks per
  decision** (4.0 in T0/C1) - the knob does what it says. The emission *rate*
  per tick is unchanged (12.3 % vs 10.9 %, a branch difference).

### 4.3 The dither (the store, P2B's own metric)

Same-tick `|command - achieved|` on the 30 Hz frames, task space at the 0.30 m
lever (`p50 |dq| x 0.30 m`), so the numbers are comparable to the census's
19.3 mm.

| arm | frames | p50 | p90 | right p50 | right p90 | left p50 | command rate | **achieved rate** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T0 | 2 739 | **21.8 mm** | 82.6 | 26.5 | 100.8 | 14.5 | 4.98 rad/s | **0.87 rad/s** |
| C1 | 2 536 | **18.2 mm** | 73.4 | 22.8 | 102.3 | 13.3 | 4.13 | **0.84** |
| C2 | 2 569 | **17.1 mm** | 58.4 | 22.2 | 70.8 | 12.8 | 2.83 | **0.73** |

* **The unconditional residual falls on both cells** (-17 % / -22 %), which is
  the direction P2B predicted - but part of that is the **frame mix**: with
  `hold = 1` every recorded frame is a chunk-boundary frame, with `hold = 2`
  every second one is intra-chunk (the slow-frame share moves 38.3 % -> 46.0 % ->
  63.8 % on a *pooled* cut of `max|da| <= 0.130 rad`).
* **At a fixed command step the residual does not improve** (pooled slow-half
  14.3 -> 13.3 -> 14.1 mm; on the right 15.6 -> 13.9 -> **18.3**). The residual
  is a **lead proportional to the command's own speed**, not a tracking
  deficiency - which is exactly why the census's "the joint command is reached
  to ~10 mrad while the Cartesian aim is missed by 34-87 mm" reads the way it
  does.
* **The achieved rate is the decisive number: it does not rise.** Halving the
  command rate takes the arm's achieved joint rate from **0.87 to 0.73 rad/s
  (-16 %)**. P2B §2.5's sentence "nothing in the loop converts the extra command
  rate into motion" is therefore **corrected by measurement**: the dither *is*
  partly the motion (the drive integrates the 120 Hz ramps), so a smoother
  command is a *slower* arm, not the same arm with less noise.

### 4.4 The cost columns

| arm | ticks/placed ep | decisions/ep (mean; per-run medians) | wall/ep | sim s/ep |
| --- | --- | --- | --- | --- |
| T0 | 1 836 | **61.2** (67 / 51 / 58) | **29.5 s** | 15.30 |
| C1 | 1 809 (-1.5 %) | 56.7 (63 / 48 / 58) | 28.9 (-2.2 %) | 15.07 |
| C2 | 1 829 (-0.4 %) | **28.9 (-53 %)** (27 / 24 / 35) | **27.4 (-7.1 %)** | 15.24 |

C2's wall saving is the **model calls**: 32 fewer decisions per episode x 71 ms
(`logs/p43/P2_RESULTS.md` §5.1) = **2.3 s of the measured 2.1 s**. That is
P2B §2.3's "the saving is wall only" prediction, confirmed to ~0.1 s; the sim
time is flat because the episode is tick-clocked by the belt floor and the
scripted primitive.

## 5. Verdicts

**E1 (C1 the clamp) - PASS.** No-harm on the registered per-run bar
(`+1/-1/-1`, all within -1), no new failure reason, the right arm 28/28 and the
arm-standardised count +0.9/45; and the out-of-range count falls to **0** while
the pre-clamp count matches T0's. Zero time cost. **Nothing is adopted**: a
no-harm cell that changes no class is a null, and the flip is an owner decision.

**E2 (C2 the hold) - FAIL on its bar, null on its mechanism.** Pooled 26/45 vs
30/45 with a `-3` run, so the pre-registered bar fails and the cell is **not
adopted**. The honest decomposition is the arm mix (§4.1): right 26/26, C2
100 % of its own arm's attempts, arm-standardised 30.0/45 = T0. The wall -
decisions and wall - is a **real, measured win** (-7.1 % wall/episode, -53 %
decisions, no sim-time cost) that this battery cannot convert into placements;
it stays a default-off instrument.

**F1 - the model lane closes.** Both cells null on placements. With P52 (the
policy's own phase is 14.2 % of an episode, its speed lever is bounded at 4.8 %
and measured -2.9 %/-5.0 %; the supervision is sound; the chunks carry no phase
structure) and P53 (the emission defect is removable for free and worth
nothing), the policy's **own** levers are exhausted. The right arm's remaining
~5 % (1 no-grasp in 30 here) is the **scripted close/handover/grip** class that
P35-P43 already own.

**The one place this battery adds a mechanism fact**: the P2B replay-rate
hypothesis is **half true and half refuted** - the command rate is a dither
(it halves) *and* it is motion (the achieved rate falls 16 %). A future
re-timing lane must therefore treat the achieved rate as the object, not the
command rate.

## 6. What this does not claim

* **No rate.** N = 3 x 15 per arm on a non-reproducible loop; the `-1/15`
  per-run bar is a no-harm bar (a 15-episode binomial at p ~ 0.7 has sd ~ 2.5
  episodes), not a rate test. The arm-standardised counts are reported *because*
  the pooled ones are an arm-mix artifact, not as a substitute rate.
* **No claim that C2's left-arm loss is caused by the slower arm.** The left is
  the closed `cnp` class and its 19 attempts are a branch draw; the achieved-rate
  measurement is the actuator, not a proved causal path.
* **No claim that the clamp is useless in general.** It removes a real defect at
  zero cost and reduces the residual 17 %; it simply moves no class on this
  interface. On a hardware limit-stop it could matter; nothing here tests that.
* **No claim about the hybrid canary.** `60_eval_policy.py` never constructs
  `SortingRLEnv`, so both knobs raise there (direct-only by construction) - the
  canary path is untouched and untested.
* **`over_max` is a per-episode maximum** over 45 episodes (a mode snap); the
  typical overshoot is the census's 3-9 deg p50 and the store's residual.

## 7. Files and pins

| artefact | md5 / note |
| --- | --- |
| `src/fruit_sorting/rl_env.py` | **`a1ae217a561a995db8a89b2d80d7086d`** (+282/-0: the two resolvers, four pure helpers, the `[emit]` row and manifest block, the `act`/`_apply` wiring, the constructor guards) |
| `scripts/229_p53_emit_selftest.py` | **`1d4ef07753c9b5c06174c33d68bca0d1`** - the new selfcheck leg, 104 checks |
| `logs/p53/run_batch.sh` | **`dba7606ec286d11759fcdc13b120c27e`** - the battery (3 arms interleaved, one claim) |
| `logs/p53/p53_report.py` | **`e7b178ec5b611f09da7044c9c2943746`** - the report (logs + stores) |
| `logs/p53/PREREG.md` | **`31099dc4fe64458d2b559edbca417b78`** - the registration (before the first arm finished) |
| `logs/p53/00_id_pre.log` / `01_id_post.log` | `831902864c50e2bc9e2974a85e4488d2` / `cc117e5bd69cd1d0567389855c5e7d61` - the byte-identity pair (47/47 `[fruit]` lines) |
| `logs/p53/02_smoke_c1c2.log` | `dbf0dfbc4fbfc7eb15353ea67afa6ba5` - the both-cells smoke (banner + `[emit]` + post-clamp 0) |
| `logs/p53/03_accept_noharm.log` | `fc468d169da30d6e3d1897ba3453c4cb` - the scripted acceptance summary (tree no-harm) |
| `logs/p53/03b_accept_noharm_run.log` | the acceptance run stream (377/377 `[fruit]` lines identical to the P42/P44 controls) |
| `logs/p53/p3/{T0,C1,C2}_{1,2,3}.log` | the nine battery logs (15/15 episodes, 15/15 `[emit]` rows each) |
| `logs/p53/p3/P53_report.txt` (`e9305e96`), `P53_113_T0_{C1,C2}.txt`, `P3_header.txt`, `P3_tree_md5_after.txt`, `manifests/` | the report, the cross-checks, the pins |
| stores | `/tmp/opencode/p53/raw/{T0,C1,C2}_{1,2,3}` (2.0 GB, 9 manifests archived) |

Untouched: `configs/*` (both motion references and `arm_parks.json`),
`datasets/*`, every checkpoint. `checkpoints/moe_v13s/policy_best.pt`
`61da390a` on all three arms. Battery tree HEAD `dae1256` + this phase's
`rl_env.py`.
