# P229 / Stage 1 results: the belt-speed envelope is the runway, not the time budget

**2026-11-24, `logs/p229/`.** 8 speed cells + a 3-point bisect, 48 episodes.
**No `src/` or `configs/` change; nothing adopted; no reference moved.**
Pre-registration pinned before any cell was read: `logs/p229/PREREG.md`.

---

## 1. What ran

| | |
|---|---|
| ladder | `FRUIT_BELT_SPEED ∈ {0.06, 0.12, 0.18, 0.24, 0.30}` x seeds {901, 902} x 6 episodes |
| bisect | `{0.20, 0.22, 0.23}` x seed 901 x 2 episodes |
| recipe | `scripts/284_single_arm_policy_gate.sh` verbatim, **`FRUIT_EVAL_LATENCY=auto`** (P228: a `d=0` cell reports a latency the machine does not have) |
| driver / report | `scripts/288_speed_ladder.sh` / `scripts/289_speed_report.py` |

**Four of the eight ladder cells never started.** At `v >= 0.22` the direct env's
`reset` raises, after 40 x 30-tick feed rounds:

```
RuntimeError: no graspable fruit reached the selection window in 40 feed rounds
```

That is not a failed attempt: **the cell does not engage**. It is the phase's
central result, and section 3 shows it is predictable from the code.

## 2. The envelope, measured

| `v` (m/s) | placed | fires | `t_arrive` at fire | `lead` | `dy` at fire |
|---|---|---|---|---|---|
| 0.06 | **11/12** | 12 | 2.61 s | 2.63 s | 0.157 m |
| 0.12 | **10/12** | 12 | 1.55 s | 1.56 s | 0.186 m |
| 0.18 | **11/12** | 12 | 1.52 s | 1.54 s | 0.274 m |
| 0.20 | **1/2** | 2 | 1.33 s | 1.50 s | 0.266 m |
| 0.22 | **does not engage** | 0 | - | - | - |
| 0.23 | **does not engage** | 0 | - | - | - |
| 0.24 | **does not engage** | 0 | - | - | - |
| 0.30 | **does not engage** | 0 | - | - | - |

Inside the envelope **33/38 = 86.8 %**, and the failures are **4 x
`fruit did not follow the gripper`** - the record's known grip class
(`logs/p42/SIM_LIMIT.md`). **No catch-up class, no new key:** the cell does not
degrade as the belt speeds up, it stops being able to start.

The `0.20` row is the interesting one: the trigger fired at **1.33 s**, *below*
its own 1.50 s budget, because the fruit was only *selected* at `dy = 0.266 m`.
**The selection, not the trigger, is the binding term.**

## 3. Why: the eligible band against the poll cadence

Two shipped formulas meet at the station. Neither is a mystery; both are read off
the code:

```
selector floor   floor(v) = min(v*(0.40 + t_desc + 0.15) + 0.03, 0.80) + 1.5*v + 0.03
belt runway      depth    = spawn_y - pick_y = 0.68 m
selector poll    P        = 30 ticks = 0.25 s          (reset's feed loop: `range(30)`)
```

with `t_desc = 86 ticks = 0.717 s` (the 5.5-6 cm descent leg's jerk-limited
duration, P91). A fruit is selectable only while

```
floor(v) <= distance <= depth
```

so the **eligible band** is `depth - floor(v)` metres, alive for
`(depth - floor(v))/v` seconds, and it has to contain at least one poll:

| `v` | floor | band | band time | polls inside |
|---|---|---|---|---|
| 0.06 | 0.226 | 0.454 m | 7.57 s | **30.3** |
| 0.12 | 0.392 | 0.288 m | 2.40 s | **9.6** |
| 0.18 | 0.558 | 0.122 m | 0.68 s | **2.7** |
| 0.20 | 0.613 | 0.067 m | 0.33 s | **1.3** |
| 0.22 | 0.669 | 0.011 m | 0.05 s | **0.2** |
| 0.24 | 0.724 | **-0.044 m** | - | **-0.7** |

Solving for one poll inside the band:

```
v_max = (depth - 2*margin) / ((0.40 + t_desc + 0.15) + 1.5 + P)
      = 0.62 / (1.267 + 1.5 + 0.25) = 0.62 / 3.017 = 0.2055 m/s
```

**Validated by the bisect**: `0.20` engages and `0.22` does not. The first estimate
in this phase's own notes used the floor crossing alone (`0.224 m/s`) and was
**wrong by one poll period** - the band has to be *wide enough to be seen*, not
merely positive. That correction is the analysis.

So the cell's speed ceiling is set by **the belt's stocked runway divided by the
time the selector spends getting ready**, and the shipped point (0.12) has
**9.6 polls of margin** while the ceiling has **1**.

## 4. The pre-registered verdicts

* **P1 (manipulation) PASS.** Every fired row's `speed=` is the cell's speed
  (`0.060 / 0.180 / 0.200 m/s/encoder`) and `dy = t_arrive x speed` holds to the
  printed precision.
* **P2 (the lead is a time) FALSIFIED as written.** `lead` is **not** flat:
  2.63 / 1.56 / 1.54 s. The cause is the acquisition window's own
  `|jaw-station|/0.20` term: at 0.06 m/s the arm is still far from the station
  when the fire condition first holds, so the lead inflates to give it the
  travel time; at 0.12 and up the arm is already there (~0.01 m) and the lead
  sits at its 1.50 s floor. **The formula did move, but through its own input
  (the arm's position), which is the mechanism working.** The *distance* was as
  predicted: `dy` scales with `v` (0.157 / 0.186 / 0.274 at 0.06 / 0.12 / 0.18).
* **P3 (breaks at >= 0.24 with the catch-up class) FALSIFIED, both halves.** The
  break is at **0.20 < v <= 0.22**, not 0.24, and the class is **not** the
  catch-up: the cell stops engaging before any chase can start, and inside the
  envelope the only failures are the grip class.
* **P4 (d=0 control at 0.30) NOT RUN, and its conditional never fired**: 0.30 does
  not engage at any latency, so there is nothing to control for.
* **P5 (the null branch) APPLIES to the time budget.** From 0.06 to 0.18 the
  shipped budget holds (11 / 10 / 11 of 12). **No arithmetic change is justified**
  and none was made: the budget already scales with speed, and the binding term at
  the top is the runway, not a missing latency term.

## 5. What this changes

1. **The cell has a measured speed envelope**: `v <= ~0.205 m/s` for this belt,
   this selector and this arm; the shipped 0.12 sits at **58 %** of it, with 9.6
   polls of selection margin against the ceiling's 1.
2. **The lever is priced and it is not arithmetic.** `FRUIT_BELT_UPSTREAM`
   (P225t, default 0) lengthens the belt upstream and, by the same equation,
   raises the ceiling: `+0.05 -> 0.222`, `+0.10 -> 0.239`, `+0.15 -> 0.255 m/s`.
   It is a **scene change** (the belt's collider grows) and owes both references
   and a store re-baseline if shipped - so it stays a measured option, not a
   default.
3. **The other lever is the poll cadence** (`P = 30 ticks` in `reset`'s feed loop,
   direct-only). Halving it to 15 ticks would raise `v_max` to **0.220 m/s**.
   That is a one-constant code change with a testable prediction; **not made**
   here, because the phase's rule is that a change needs a measured failure it
   fixes, and the failure the cell shows at 0.22+ is *starvation at the selector's
   own floor*, which a faster poll only half-fixes (at 0.24 the band is negative
   and no cadence helps).
4. **The time budget's latent gap is documented but not acted on**: nothing in it
   carries the measured 66 ms decision latency (P228). At 0.12 m/s that is 8 mm
   against a 0.29 m band - **2.7 % of the margin** - so it is a real but
   non-binding term at this point of the envelope; `docs/ARCHITECTURE_4T.md`
   §4 keeps it as the term to add when the envelope is pushed.

## 6. The harness gap this exposed

`reset` **raises** rather than idling when no fruit can be selected. In a real
cell the condition is "the line is faster than this station can serve", which is a
starvation alarm and a hand-off, not an exception. The direct env has no graceful
form; a deployment would need one. Named, not fixed (it is a harness behaviour,
and the abort did its job: it made the boundary impossible to miss).

## 7. Deviations

1. The ladder's own `0.24` / `0.30` cells were **run and produced no episode**;
   they are reported as "does not engage", not as 0 % (a 0/0 cell is not a rate).
   `scripts/289_speed_report.py` prints the warning that names them.
2. One arithmetic estimate in this phase's working notes (the message before the
   bisect) read `v_max = 0.224 m/s` from the floor crossing alone and projected
   `FRUIT_BELT_UPSTREAM=0.10 -> 0.260 m/s`. Both were **one poll period
   optimistic**; the corrected values are `0.2055` and `0.2387`, and the bisect is
   what found the difference.
3. `0.20` has **2 episodes**, not 6: it is a bisect point, not an arm. Its 1/2 is
   a single draw and is quoted for the engagement, not for a rate.

## 8. Pins

`tasks.py` **`3f9ef6ea`** and `rl_env.py` **`41e006a6`** unchanged by this phase,
`scripts/288_speed_ladder.sh`, `scripts/289_speed_report.py`; references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156` used as-is. Evidence `logs/p229/{PREREG.md, RESULTS.md, speed/}`.

---

## 9. Addendum: the equation predicts **engagement**, and engagement is the wrong ceiling

`PREREG_UPSTREAM.md` tested the equation's **slope** with a 2x2
(`ext` x `v`), 3 episodes each, seed 901.

| cell | `ext` | `v` | equation | measured | verdict |
|---|---|---|---|---|---|
| A | 0.10 | 0.22 | engage | **engage**, 1/3 | PASS |
| B | 0.10 | 0.24 | **no** | **engage**, 0/3 | **FAIL (conservative)** |
| C | 0.15 | 0.24 | engage | **engage**, 0/3 | PASS |
| D | 0.15 | 0.30 | no | **no engage** | PASS |

**3/4, and the one miss is conservative**: at `ext=0.10` the ceiling is
`>= 0.24`, not the `0.2387` the equation computes - an error of `>= 0.0013 m/s`
(and the slope matched: `+0.10 m` of belt moved the ceiling by **+0.03** against
the predicted **+0.0332**). So the equation is a **conservative lower bound on the
engagement ceiling**, good to `~0.01 m/s`.

**But the extension bought zero placements.** At `v=0.24` both extensions fire
3/3 and place **0/3**; the delivered scene also places 0/6 at 0.24 across the two
cells. The ceiling that matters is a different one.

### 9.1 The usable ceiling, measured

| `v` | placed | 95 % CI | classes |
|---|---|---|---|
| 0.06 | **11/12** | [65, 99] | 1 grip |
| 0.12 | 10/12 | [55, 95] | 2 grip |
| 0.18 | **11/12** | [65, 99] | 1 grip |
| **0.20** | **7/12 = 58 %** (5/6 and 2/6) | [32, 81] | 5 grip |
| 0.22 | 1/3 | [6, 79] | 2 grip |
| 0.24 | **0/6**, two extensions | [0, 39] | 6 grip |

The drop is **between 0.18 and 0.20** (92 % -> 58 %), and it is **not** where the
engagement equation says the cell stops (0.2055). **The cell runs out of *grasp*
before it runs out of *runway*** - which is exactly why the runway lever was worth
nothing.

### 9.2 The mechanism at 0.24, traced (`FRUIT_CARRY_DIAG=1`, `ext=0.10`, `v=0.24`)

One failed attempt and one placed attempt, the same cell:

| field | failed | placed |
|---|---|---|
| `contacts@onset` | **0** | 2 |
| `force@onset` | **0.00 N** | (held) |
| `min_contacts` | 0 | 2 |
| `force_min` | **0.00 N** | **7.88 N** |
| `sep_end` / `gap_start` | **0.0 / 14.1 mm** | 34.4 / 34.6 mm |
| fruit diameter | 40.0 mm | 44.0 mm |
| `clean_slip_max` | 1769 mm | 0.2 mm |

**`sep_end = 0.0 mm` with `gap_start = 14.1 mm` on a 40 mm fruit and zero
contacts means the pads closed completely on air** - the hand was not at the fruit
when the close finished. (`clean_slip_max = 1769 mm` is *not* evidence of a hold:
on a leg with nothing in the jaws it is the hand's own travel relative to a
stationary payload.) The placed attempt is a proper two-sided pinch
(`force_min 7.88 N` at a 34.4 mm span). `res_end` was 241 mm on the failure and
162 mm on the success, so it is **not** a clean "chasing" indicator on this cell
and is reported, not used.

So the 0.22-0.24 class is **acquisition** - the classic "grasp where the object
*was*" - and its trigger is `v x (t_desc + close)` outrunning the catch-up, not the
selector.

### 9.3 What this changes

1. **The cell's usable speed is ~0.18 m/s** (11/12), with 0.20 **marginal**
   (7/12, and seed-dependent: 5/6 vs 2/6). The shipped 0.12 sits at **67 %** of
   that, not at 58 % of the engagement ceiling.
2. **`FRUIT_BELT_UPSTREAM` is the wrong lever for throughput**: it lifts the
   *engagement* ceiling, which the cell does not reach before the grip fails. It
   stays a priced scene option for the *starvation* class only.
3. **The lever is the contact phase** - the descent's duration against the belt
   (`v x t_desc` = 172 mm at 0.24 against a 6 mm tolerance), the close's duration,
   and the catch-up's budget. That is Stage 2/3 of
   `docs/ARCHITECTURE_4T.md`, now with a measured reason to go there instead of
   to the scene.
4. **A second instrument lesson**: `grasped=False` alone does **not** separate
   "never touched" from "touched and lost" (a 1769 mm `clean_slip_max` is
   consistent with both). The separator is **`contacts@onset` / `force@onset`**,
   and any future speed cell must run with `FRUIT_CARRY_DIAG=1` or it cannot name
   its own failure.

### 9.4 Pins for the addendum

No `src/`/`configs/` change; the cells are scene options (`FRUIT_BELT_UPSTREAM`),
the addendum's registration is `logs/p229/PREREG_UPSTREAM.md`. Cells:
`logs/p229/{up10,up15,ceiling,diag024}/`.
