# P57 PREREG — `CandidateBoard` (parallel candidate handling at the pick boundary)

Written **before** any simulator run of the module. Phase 1
(`logs/p57/DESIGN.md`) is offline and its numbers are fixed here as the
contrast, so phase 2 cannot move them.

**The question.** Does a candidate module that (a) forecasts the boundary
wait from the *feeder* as well as the band, (b) pre-decides the next target and
its arm, and (c) folds the arm-switch park into the wait, remove the **30-tick
starvation round** from the continuous-sorting pick boundary - and does its
forecast beat a constant 30-tick wait?

**The measured contrast (phase 1, immutable for this phase).**
`FRUIT_DIRECT_CONTINUOUS=15`, seed 77 (`logs/p56/p2/B_1.log`):

| quantity | value |
|---|---|
| gap classes, 14 transitions | **[50, 80 x9, 110 x4]**, mean 86.4, span 1210 ticks |
| starvation rounds | **8 of 14** transitions (4 of them inside a 110 gap, 4 inside an 80) |
| belt candidates at a starved instant | **0 usable** on 8 of 8 (0-7 belt rows, all below the floor) |
| live-fruit forecast at a starved instant | **infinite, structurally**: the belt runs -Y, so a fruit below the floor is *leaving* the band (usable `along` max over the corpus 675 mm vs `spawn_y` 680 mm) |
| feeder term at a starved instant (`lag`) | **+11.01..+12.46 s** (8/8) vs **-1.32..-0.00 s** at the 15 picks |
| burst arithmetic | `n_due = lag/period` ~ 11 rows (= the measured 5 skipped + 6 delivered in one call); skips are free, so **1 pump call** burns the backlog |
| next target visible one transition earlier | **0 of 14** (1.99 m of projection vs a 1.38 m belt) |
| feeder clock at a starved instant | `max(0,-lag)*120 + 1` = **1 tick**, all 8 (measured recovery 30, the only re-check unit) |
| burst | one pump call delivered 6 rows at along 0.069..0.672 with `supply_skipped +5`; **2-3 of the 6** cleared the 0.399 m floor |
| removable budget | **232 ticks = 1.93 s = 0.81 %** of the 239.6 s span (ceiling 240 / 0.83 % with the wait -> 0); per-transition floor 50 ticks |
| placed | **8/15** vs the per-pick arm's 11/15 - **a different branch (first diverges at attempt 1)** |

---

## 1. The arms

All arms: the P56 B scenario verbatim (patch sheet, `FRUIT_DIRECT_FEED=1`,
`moe_v13s` `61da390a`, `FRUIT_POLICY_SEED=11`, the P43 park default, ACQ on),
`--record --episodes 1 FRUIT_DIRECT_CONTINUOUS=15`, **and all three diagnostics
on in every arm** (`FRUIT_BED_DIAG=1 FRUIT_GRASP_DIAG=1 FRUIT_BOARD_DIAG=1`).
A diagnostic in every arm is the P38-M4 rule: a run-neutral report cannot be
compared against its absence.

The ladder has **two families**, because DESIGN §2.4 shows the boundary wait has
two causes and a different actuator each. Every endpoint is read **against its
own control**, never across families.

| arm | knobs | control for | what it isolates |
|---|---|---|---|
| **A** | none | - | the P56 B branch (cadence off, `lag`-bound). It must replay `[50, 80x9, 110x4]` / 8 rounds |
| **B1** | `FRUIT_DIRECT_PUMP_FIRST=1` | **A** | the pump-before-decide call alone (DESIGN §3.4 item 1) - the cadence-off actuator |
| **F** | `FRUIT_FEED_CADENCE=1` | **A** | the in-flight `_feed_scope` widening (DESIGN §2.4; **not this phase's edit**, `tasks.py` `c7eef701`). Already sampled once by another session (`logs/p57/cad_s77.log`, cited not claimed): `gaps=[80,110,80,50,80,80,230,80,50,80,50,50,80,50]` = `[50 x5, 80 x7, 110 x1, 230 x1]`, mean 82.1, **2 starved transitions paying 2 + 6 = 8 rounds** (the same total as cadence-off), `lag = -0.11 s` |
| **B2** | `FRUIT_FEED_CADENCE=1 FRUIT_DIRECT_BOARD=1` | **F** | the module in the pump-current world: exact wait sizing (item 2) + `next_target` (item 5) + park-in-wait (item 3) |
| **B3** | `FRUIT_DIRECT_BOARD=1` (cadence **off**) | **A** | the module in the `lag`-bound world (item 1's pump call + item 2 + item 5) |

**Order.** A first (it validates the tree). Then **F** (one run, ~8 min): it
decides which world the module ships into. Then the module's arm for that world
(B2 if F's wait is interlock-bound, B3 if F does not move the wait). The other
family's module arm is spent only if the first reads a null. If B2/B3 reach
P1a **and** P2, the remaining arm is still run - the registered question includes
the forecast, and a gap-only pass cannot answer P3.

---

## 2. Endpoints (the decision rule, written first)

Read in this order; a FAIL at P0 or F* stops the phase.

**P0 - the module is wired (manipulation check, read first).**
The `[board]` row exists at **every** selection instant (23 in A; one per
attempt in the board arms, which may be 15), and its `n_usable` equals the `[bed-sel]`
header's `window` on **100 %** of them, and `target=` is a live index.
Rationale: with the classifier shared (DESIGN §3.3) a disagreement here is a
wiring bug, not a measurement.

**P1a - the boundary gap (against the arm's own control).**
`median <= 80` **and** `max <= 90` over the 14 transitions.
- family A (B1/B3 vs A): control `[50, 80x9, 110x4]`, median 80 **max 110** ->
  **FAIL today**. Pre-computed prediction if the rounds go: the four 110s
  (switch + round) become 80 and the four 80s (round only) become 50, i.e.
  **`[50 x5, 80 x9]`, median 80, max 80** - a PASS exactly at the bar, so P1b is
  the sharper read.
- family F (B2 vs F): control `[50 x4, 80 x8, 110 x1, 230]`, median 80 **max
  230** -> `max <= 110` is the bar; `max <= 90` would require the 110 too.

**P1b - the mechanism (names the class).**
- family A: `count(gap == 110) == 0` **and** `count(gap == 50) >= 4` (the 4
  round-only 80s become 50; the 4 switch+round 110s become 80).
- family F: `count(gap >= 230) == 0` and `count(gap == 50) >= 4`.
Registered *because* P1a is a threshold on a quantised quantity: the class
composition is the result, the median/max are the bar.

**P2 - the starvation rounds.**
Read **against the arm's own control**:
- family A (B1 vs A): `rounds == 0 of 14` (control 8);
- family F (B2 vs F): `rounds_paid <= 2` total (control: **8 rounds** over 2
  transitions, 2 + 6) and no single wait longer than **2 rounds**, with
  `|pred_ticks - measured_ticks| <= 30` on each.
A partial pass is reported as `rounds = k/R` with `R` the rounds in the wait,
never as PASS.

**P3 - the forecast accuracy (the phase's scientific endpoint).**
The board is refreshed on the **pre-pump** snapshot (it is what decides whether
to pump), then the pump fires - so the feeder term is measurable in B2 even when
A1 removes every round. Over every instant the board predicts:
- the **class** (`usable now` / `wait k` / `none`) matches the measured outcome
  on **>= 90 %** of instants, and
- where `pred = wait k`, `|k - measured| <= 30` ticks on **>= 90 %** of them.
Control for the comparison: the **band-only** variant (no feeder term), which
phase 1 read as **0 of 8** correct on the rounds - structurally, not by luck
(no live fruit can enter the band). The feeder term must be the reason the class
is right: `src = feed` on **every** instant where the raw state has 0 usable and
the arm recovered inside the horizon (**8 of 8** in family A, **1 of 1** in
family F). A forecast that ties the band-only model is not a forecast; publish
it as such.

**P4 - the pre-decision agreement.**
`next_target().index == select_target`'s `chosen` index on **>= 98 %** of the 15
picks (a fresh snapshot must agree *exactly* - the shared classifier makes
disagreement a staleness event), and `pred_arm == launched arm` on **>= 90 %**.
Disagreements are reported with `stale=1` and the fallback path taken.

**P5 - the placed count (reported, never a rate).**
`placed` is reported for every arm with the mandatory caption "different branch,
no rate claim" (AGENTS §2). The two P56 arms agree at attempt 0 (both
`pear@0.559`, **left**) and first diverge at attempt 1 (`peach@0.657` in A_1 vs
`peach@0.473` in B_1) - a correction to P56's "different attractors from pick 1",
recorded here because this phase quotes that pair. The only registered reading is
the non-inferiority sanity check `|placed_B - placed_A| <= 4` (P56's P2 bar, kept
for comparability). **P5 does not gate adoption.**

**P6 - no new failure reason.**
B's normalised reason key set `⊆` A's `∪` the P43/P54 baseline set
(`logs/336_hybrid_v3all.log`'s keys). Any new key stops the phase.

**P7 - the no-harm (must hold in every arm).**
- `--ablate scripted`, one episode, knobs **unset** and knobs **set**:
  **byte-identical** `[fruit]` streams against each other and against the P56
  no-harm record (`logs/p56/p0/S_scripted_final.log`, 44/44 lines). The
  scripted line never constructs `SortingRLEnv`, so both must be identical by
  construction - the check is the proof that the env-only knobs stayed
  env-only.
- `scripts/selfcheck.sh` **PASS** (0 failures).
- the knob-off policy smoke (1 episode, patch sheet, no `FRUIT_BOARD_DIAG`):
  no `[board]` row, and the tick/outcome delta against a same-tree repeat is
  inside the rendered-frame nondeterminism (P56 measured a same-tree repeat that
  differed *more* than the pre/post pair: 9 diff lines, 1885 vs 1931 ticks).

---

## 3. Falsifiers (each stops the phase)

- **F1** P0 fails: the board's `window` disagrees with the selector's -> the
  classifier extraction is not equivalent; revert and publish.
- **F2** `src = feed` never fires on the 8 pre-pump instants (the feeder term is
  inert) -> the phase-1 mechanism (DESIGN §2.2) is wrong; the finding reverts to
  "the round is unexplained" and no wait is sized from a forecast.
- **F3** P1a **and** P2 both fail -> the module does not buy the 232-tick
  budget; publish the null (the same shape as P56's P1).
- **F4** P3 < 80 % class accuracy -> **the forecast is worse than a constant
  30-tick wait**; publish the negative and keep only the `[board]` diagnostic.
- **F5** P4 < 90 % -> the pre-decision is stale or the release look-ahead is
  wrong; drop items 1/5 and keep the pump actuator.
- **F6** P6 fails -> stop, publish the new reason.
- **F7** P7 fails -> the knobs are not env-only / not inert; revert.
- **F8** `placed` falls by **> 4** with no mechanism read to explain it -> the
  round is load-bearing beyond the pump (P56 §4 extended); publish and do not
  adopt.
- **F9** the post-A1 wait is **not** `< 30` ticks on **>= 6 of 8** rounds (the
  pump needs the full round after all) -> the one-call burst arithmetic is wrong;
  publish the correction, do not size waits.
- **F10** A fails to replay `[50, 80x9, 110x4]` -> the tree moved; the phase is
  re-based on the new control, not read against these numbers (F's own sample
  `logs/p57/cad_s77.log` is then the only F datum and the family-F read waits).
- **F11** family F only: the interlock term is not what predicts the round
  (prediction off by > 30 ticks on the one round, or `src != feed` there) -> the
  `t_free` model of DESIGN §3.1 is wrong; publish it and do not size a wait in
  the pump-current world.

---

## 4. What the phase may and may not conclude

**May**: the boundary gap's class composition; the presence, size and source of
the feeder term; the forecast's accuracy and its two sources' separate
reliability; whether the pre-decision can be trusted; the module's own wall cost
(`[board] us=`).

**May not**: any throughput or placed-per-minute claim (a quantised outcome on a
moved branch); anything phrased as "the line never waits" (the band holds 2-4
fruit - 0.281 m of geometry, ~0.15 m of observed stock - against 1.80 m consumed
per pick); any claim on the scripted line, the two-line or the hybrid canary
(all unreadable by construction); any claim that the module *creates* supply;
and any attribution of arm **F**'s effect (DESIGN §2.4) to the board.

---

## 5. N, cost, the order of the spend

- **One claim**, seed **77** (the control's own seed; B_1 is a fixed scenario, so
  a different seed is a different branch and not a replication).
- Order: **A** (the control), then **F** (one run) - F decides the world. Then
  the module's arm for that world (**B2** if F's wait is interlock-bound, **B3**
  if F leaves the `lag`-bound wait). Each rung is one continuous 15-pick episode
  at P56's measured 471 s, so A + F + one module arm ~= **24 min**, plus the
  no-harm pairs (~6 min) and the scripted byte-identity pair (~1 min). The
  second family's module arm is spent only on a null, and seeds 101/202 only if
  the ladder passes P1a + P2 + P3 (the P56 §6 rule).
- One selfcheck, one `accept.sh` (the shipped default's no-harm - the knobs are
  unset, so this is the P43-style import guard and is stated as such).

## 6. The record this phase must leave

- `logs/p57/p2/{A,F,B2,B3}_1.log` + the batch driver and its header, `P2_report.txt`
  re-deriving P1a/P1b/P2/P5/P6 from the logs.
- The `[board]` forecast table: instant, class, `t_band`, `t_feed`, `k`,
  measured, error (`forecast.txt`).
- The `[bed-sel]` rows **with `index=`/`dia=`** (the print-only fix), so every
  `target=` is checkable by identity.
- The gap-class table per arm, and the 14-transition decomposition (settle /
  teleport / park / round) per arm.
- The no-harm pair (scripted byte identity) and the knob-off policy smoke.
