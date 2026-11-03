# P109 results - the descent margin is load-bearing: it sets the *sign* of the arrival, and spending it costs the catch

Owner's item: P108's ①, `FRUIT_DYNAMIC_DESCEND_MARGIN` **0.15 -> 0**. Pre-registered
in `logs/p109/PREREG.md` (md5 **`192a0c1b`**, `PREREG.md5`, pinned at 18:57 before
any run). **Nothing adopted, no default changed, `configs/` untouched, no commit.**

**The one-sentence answer.** The knob moves the descent-start gap to the aim
**exactly 18 mm** and it moves **every** attempt's end-of-descent arrival from
the correct side of the aim to the wrong one (`past_aim` **0/76 -> 79/79**); the
catch-up then enters its measured bistable failure (converge to the 6 mm
tolerance, or run away to **233-269 mm**), which it does on **5 of 79** battery
attempts (0 of 76 in the control) and **3 of 10** acceptance attempts (1 of 10),
and the placed count falls at **4 of 4** seeds. The margin is what makes the
static descent a *catch-up*; without it the fruit is past the pads when they
stop.

## 0. The instrument is proven inert, and the P108 controls are admissible

The replay the tree's rule asks for (P95's lesson), before any claim:

| pair | result |
|---|---|
| `M0_s5.log` vs `logs/p108/S_s5.log` | **IDENTICAL 860/860** (`[cycle]` 21 + `[stats]` 2 rows dropped) |
| `M0_s6.log` vs `logs/p108/S_s6.log` | **IDENTICAL 853/853** |
| `accept_m0.log` vs `logs/p108/accept_noharm.log` | **IDENTICAL 419/419** |
| `accept_final.log` vs `accept_m0.log` (final tree) | **IDENTICAL 419/419** |

So in one comparison each: the tree is unchanged since P108, the P108 cells are
valid same-tree controls, **`FRUIT_CYCLE_REPORT` is run-neutral on this line**
(it is the only row this phase adds), and the shipped acceptance is this tree's
branch of record (`8/10`, `fingerprint: matches 30fb99f8`).

All twelve cells carry the same instrumentation (`FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1`), so the arms are
compared inside one batch. `logs/p109/p109_report.txt` is the generated table.

## 1. The mechanism, and why P108's "18 mm of the 83" is the wrong gap

**1.1 `fruit dy` cannot respond to this knob - measured, not argued.**
`[task] dynamic descent` prints `dy_now = fruit_y - intercept_y` with
`intercept_y = clip(fruit_y - speed*t_desc, ...)`, so in the unclipped regime
`fruit dy == speed*t_desc`: both terms carry the margin and it cancels. The cells
read **`fruit dy` p50 83.0 / 82.0 / 83.0 mm** for M0 / M0.5 / M1 - flat across a
full removal of the margin, in all twelve cells. The algebra in `PREREG.md` §1 is
confirmed live; a phase that registered only this number would have reported a
null that means nothing.

**1.2 The gap the margin sets is `g0 = fruit dy + shift`** (the descent-start
distance from the fruit to the aim), which is what `deadline` commands:

| arm | `deadline` | `shift` | `g0` p50 | `g0` p90 | `waited` |
|---|---|---|---|---|---|
| M0 (0.15) | 100-101 mm | +17.4..17.6 | **100.1** | 101.0-101.7 | 67-76 ticks |
| M0.5 (0.075) | 91 mm | +8.4..8.6 | **90.9** | 91.7-93.3 | 75-77 |
| M1 (0) | 83 mm | -0.7..-0.3 | **82.3** | 82.9-84.4 | 70-77 |

Per seed the M0 -> M1 step is **+17.6 / +18.3 / +17.6 / +17.7 mm** and the
half-margin arm sits **exactly** in the middle (+9 mm): the knob is a clean,
graded, deterministic actuator on `g0`. **E1b passes its clause at every seed**
(>= 12 mm registered). The hover wait is nearly unchanged (74 -> 74 ticks)
because the handover lead falls by the same 18 mm (195 -> 174 mm printed).

**1.3 What it does to the arrival.** The descent is a static, open-loop profiled
leg to the station at a measured 1.00x belt ratio, so the whole window shifts by
the same 18 mm and the fruit's position **relative to the aim at the descent's
end** is `g0 - 0.12 m/s * steps` (steps 88-94 printed by the motion row):

| arm | arrival at the descent's end, p50 | p10..p90 | fruit **past** the aim |
|---|---|---|---|
| M0 | **+10.6 mm** (still upstream) | +9.0..+13.0 | **0 / 76** |
| M0.5 | **+1.3 mm** | -0.1..+3.8 | **9 / 75** |
| M1 | **-7.3 mm** (past) | -8.8..-5.1 | **79 / 79** |

This is a *derived* column (belt speed x the leg's own `steps=`), not a measured
fruit pose, and it is the phase's mechanism: the catch-up wants the fruit
**upstream** of the tip when the descent ends, because its command is
`fruit + v*0.25 s` - **30 mm further downstream**. With the fruit already 5-8 mm
past the aim that command is 35-38 mm *ahead* of a tip that has to move
downstream at the belt's own 1 mm/tick to hold station: the loop becomes a race
it can lose.

## 2. The catch's guard: a bistable failure, not a gradual degradation

The catch-up's outcome is **bimodal**: it exits at its 6 mm tolerance
(p50 5.8-5.9 mm in every arm, including the failures) or it runs away to the
belt's 200-tick budget. Nothing lands in between.

| arm | res > tol | res > 50 mm | worst residual |
|---|---|---|---|
| M0 | 0 / 76 | **0 / 76** | ≤ 6.0 mm |
| M0.5 | 0 / 75 | **0 / 75** | ≤ 6.0 mm |
| M1 | **5 / 79** | **5 / 79** | **261.8 mm** |

Every one of the five is at **seed 5** (5/20 against the control's 0/19, Fisher
**p = 0.047**), spread through the run (attempts 0, 1, 6, 13, 17), and **all
five** end `fruit did not follow the gripper` with `grasped=False`. Pooled with
the acceptance (§4) the runaway class is **8/89 = 9.0 % vs 1/86 = 1.2 %**,
Fisher **p = 0.035**. The three other battery seeds read **0/60**, and the
shipped arm itself produced **one** runaway in the acceptance - so this is a
*rate*, not a step: the margin does not eliminate the instability, it depresses
it about sevenfold.

**The other no-grasp events are a different class.** M0's single one (seed 6)
and all three of M0.5's (seed 101) have residuals of 5.8-6.0 mm, i.e. the
catch-up **converged** and the close still lost the fruit - the converged
close/grip class the record already carries (`logs/p42/SIM_LIMIT.md`). Only M1
produces the > 200 mm timing runaways, which is what makes the guard's reading
specific to this knob.

**Aim quality is unchanged** (E2): the descent's `end=` reads p50 **9.0 / 9.2 /
9.0 mm** and p90 9.9 / 10.2 / 10.4 across the three arms - the standing P32
boundary shortfall, untouched by the knob and **not re-tuned**. The catch-up's
own p50 residual is the tolerance in every arm, so it is a *threshold* read, not
a quality read; the quality read is §1.3.

## 3. The count, and the branch it rides on

| arm | seed 5 | seed 6 | seed 101 | seed 202 | pooled |
|---|---|---|---|---|---|
| M0 | 12/19 | 13/19 | 13/19 | 11/19 | **49/76 = 64.5 %** |
| M0.5 | 14/19 | 14/20 | 10/18 | 11/18 | **49/75 = 65.3 %** |
| M1 | 10/20 | 10/20 | 11/20 | 10/19 | **41/79 = 51.9 %** |

M1 is **down at every seed** (-2 / -3 / -2 / -1; pooled -12.6 points, Fisher
p = 0.143, sign 4/4). M0.5 is a **draw** (+1 / +1 / -3 / +1; pooled +0.8 point,
Fisher p = 1.0).

**Read the count with E0 in hand**: the selector floor is
`_dynamic_pick_lead() + speed*select_s + margin`, so it moves with the knob by
the same 18 / 9 mm and the **selected fruit sequence differs at every seed** from
attempt 1-3 onward (`p109_report.txt`, the species ledger). A count delta across
those branches is partly a branch draw (AGENTS §2), which is exactly why the
phase's registered clauses put the *class* first. The class result is the one
that transfers: **the timing runaway is new, and it is only in M1.**

## 4. The acceptance A/B (the catch's own gate, and the two-line)

`scripts/accept.sh`, ten attempts, the shipped two-line session - so this is also
the phase's only read of the **two-line** under the knob (it *does* read it: the
`[task] dynamic descent` shifts move to ~0 on both stations, and the runaways
rise).

| arm | placed | no-grasp | runaways | descent budgets | fingerprint |
|---|---|---|---|---|---|
| **unset (0.15)** | **8/10 = 80 %** | 2 | **1** | all inside (worst `|v|max` 0.112 / 0.160) | **matches `30fb99f8`** |
| **M1 armed** | **4/10 = 40 %** | 5 | **3** | all inside (worst 0.110 / 0.160, lurch 0.017 / 0.291) | **DIFFERS** by construction |

`190: PASS` on the unset arm and `FAIL` on M1 - the FAIL is the fingerprint (the
knob moves every attempt's arrival) **and** the rate: 40 % is below the two-line
0.60 floor. So **PREREG §5's gate fires**: M1 is not a candidate whatever the
cells say. The budgets are clean in both arms, so the 4/10 is not a motion
regression.

The final tree's own acceptance (`accept_final.log`, run after every cell and
every text edit) reads **8/10, 80 %, `fingerprint: matches
configs/motion_reference.json`, `190: PASS`**, and is **419/419 identical** to
`accept_m0.log` - the unset arm is this tree's branch, unchanged by the phase.

## 5. The decision rule, clause by clause

| clause | registered | measured | verdict |
|---|---|---|---|
| **E1b** the offset falls | `g0` p50 down >= 12 mm at every seed | +17.6 / +18.3 / +17.6 / +17.7 | **PASS** |
| **E3** the catch does not rise | no-grasp <= M0 at every seed | seed 5: **5 > 0**; seeds 6/101/202: 0/0, 0/0, 0/0 | **FAIL** |
| **E4** the count holds | not down by more than one per seed | -2 / -3 / -2 / -1 | **FAIL** (3 of 4) |
| **the acceptance gate** | >= the 0.60 floor | 4/10 = 40 % | **FAIL** |

**VERDICT: the margin is worth keeping.** It is not a cushion - it is the term
that makes the arrival residual positive, and the catch-up can only converge
from that side. **The honest alternative** for the along-belt term is what P108
named: the **aperture** (its measured precondition - `clr < 0` 32/51 -> 4/57,
p = 1.4e-8) or a **centring guide / workstation presentation**. Shortening the
descent itself is not available either: it is jerk-bound on a 5.5 cm leg (86
ticks at `a_max` 0.8 *and* 1.6, P91 §3) and its `|v|max` is the motion gate's.

## 6. The dose axis (M0.5 = 0.075), reported

Half the margin is **not** the same failure and is **not** a win:

* `g0` 90.9 mm, arrival **+1.3 mm** (9 of 75 attempts cross to the past side,
  p10 -0.1 - it sits *on* the boundary), **0 runaways in 75**;
* placed **a draw** (49/75 vs 49/76, p = 1.0) and every seed within one;
* no-grasp 3/75 against M0's 1/76 - but all three are at **seed 101** where both
  neighbours read 0, and all three are the **converged** class (residual
  5.8-5.9 mm), so E3 as written still fails at that seed and the *timing*
  mechanism is not responsible.

So the ladder is: **9 mm keeps the catch's sign and buys nothing measurable;
18 mm puts every attempt on the wrong side and costs the catch.** The boundary
sits between 0.075 and 0 - which is why the "free half" is not a recommendation:
there is no throughput on the other side of it.

## 7. Deviations

* **D1 - a description error in `PREREG.md` §1, pinned before any cell.** The
  parenthetical reads "+12.8 mm *(fruit already 13 mm past the aim)*" - **+12.8
  means still upstream**; the formula on the line above is right and the report's
  column is right. No endpoint, clause or verdict depends on the prose; the sign
  is corrected here (§1.3) and the derivation is `arr = g0 - speed*steps`.
* **D2 - a build smoke, not a cell.** `logs/p109/smoke_m1.log` (3 attempts, seed
  5, M1) was run after the pin to validate the env plumbing and time a cell. Its
  attempt 0 reproduces the battery cell's 259.0 mm runaway **exactly**, and its
  attempts 0-1 are two of the five - a reproducibility datum, not evidence.

## 8. What a flip would owe (it is not licensed, and would not be wanted)

Nothing shipped, so `configs/motion_reference.json` = `..._twoline.json` =
**`30fb99f8`** and `..._single.json` = **`8952c320`** stand, no reference was
re-recorded and none is owed. Had the gate passed, a flip would owe: both motion
references re-recorded from same-batch 10-attempt runs (the knob moves **every**
dynamic catch on **every** path - single arm, the two-line's wait loop, and the
`FRUIT_DYNAMIC_PICK=1` direct handover; the shipped hybrid canary runs the
indexed primitive and has no path), the acceptance re-based, and every store
re-baselined. The owner's approval would be the precondition, not the formality.

## 9. Files, instruments and pins

`logs/p109/{PREREG.md,PREREG.md5,RESULTS.md,cells.sh,run_p109.sh,p109_report.py,p109_report.txt}`,
the twelve cells `{M0,M05,M1}_s{5,6,101,202}.{log,driver}`, the acceptance pair
`accept_{m0,m1}.{log,driver}`, the smoke `smoke_m1.log`.

Tree pins (unchanged by this phase; the 860/860 and 419/419 replays prove the
behaviour): `tasks.py` **`d341b0da`**, `rl_env.py` **`bf4c56fa`**, `bimanual.py`
`9b7fc33f`, `fruits.py` `dcabe16b`, `assets.py` `eb30c77a`, `scene.py`
`a0199097`; references **`30fb99f8`** / **`30fb99f8`** / `8952c320`; ckpt
`moe_v13s` `61da390a`.
