# P262 results: the settle threshold was 5x stricter than the arm needs - **-0.27 s at 60/60**

**2026-11-25, `logs/p262/`.** Two candidate knobs on the `grip` block, one closed as inert
and one adopted into the deployment recipe. **No `src/` or `configs/` change.**

---

## 1. The block, from P261's split

`grip` (1.58 s) is **not** the load leg - it is the belt-break ramp (`lift_takeoff`
**0.78 s**) plus `_settle_to_rest` (`lift_settle` **0.79 s**). The settle is the largest
single *wait* in the attempt after the fruit-arrival wait.

## 2. `FRUIT_PLACE_LOW_TUCK_SETTLE=0` - **inert on this hand**, and that closes it

`_place_low` opens with a 30-tick "tuck" settle (0.25 s) before the accompanied descent,
which looked like a fixed hold of the kind P258/P260 removed. Measured (20 picks x 2
seeds): the attempt **10.03 -> 10.03 / 9.88 s**, i.e. **nothing** - the tuck is inside a
branch the **jaw hand** does not take (the Panda's pads are the fingers, not a separate
kinematic pad), so on this cell it is already skipped. Recorded so the knob is not
re-tried here.

## 3. `FRUIT_SETTLE_EPS` 0.002 -> 0.01 - **half the settle, no acceleration cost**

`_settle_to_rest` exits when the TCP moves slower than `FRUIT_SETTLE_EPS` (default
**2 mm/s**) for five consecutive ticks. After the belt-break the arm is dragged at the
belt's 0.08 m/s, so 2 mm/s means waiting for it to be *essentially stopped*.

| arm | `lift_settle` | attempt `total` | placed |
|---|---|---|---|
| control (2 mm/s) | **0.79 s** | **10.03 s** | 20/20 |
| 10 mm/s, s905 | **0.48 s** | **9.66 s** | **20/20** |
| 10 mm/s, s906 | **0.47 s** | **9.76 s** | **20/20** |

**-0.31 s of settle, -0.37 / -0.27 s of the attempt, 40/40 placed.** And the *reason the
settle exists* was checked, not assumed: starting a leg on a moving arm shows up as an
acceleration spike, so the `[motion]` report was read on both arms -

* the lift leg's commanded peak is unchanged (`|a|cmd` **0.74** both);
* the **line's `|a|max` is 31.7 at 10 mm/s against 35.7 at the 2 mm/s control** - lower,
  not higher;
* the lift leg's ticks (93-101) and `clean_slip` (0.0 mm) are unchanged.

## 4. Where it lives: the recipe, not a default

`FRUIT_SETTLE_EPS` is read by **every** `_settle_to_rest` in the tree, the two-line's
included, so a default would move the two-line acceptance and owe a reference re-record.
It is a **deployment-recipe** setting (`scripts/290_single_arm_continuous.sh`, with the
measurement in its header), `FRUIT_SETTLE_EPS=0.002` restores.

**The recipe cell confirms it carries** (seed 909, 20 picks, everything else at the
defaults): **20/20, cycle 9.71 s**. Pooled over the three cells: **60/60 = 100 %**, cycle
median **9.71 s**.

## 5. Where the cycle now is

| phase | attempt cycle | change |
|---|---|---|
| arc start | 13.55 s | - |
| P249 | 12.13 s | axis-aware catch exit |
| P258 | 11.43 s | duplicated clearance |
| P259 | 10.85 s | over-timed place blend |
| P260 | 10.49 s | release holds |
| P261 | 9.97 s | the right arm's 16 cm of unmeasured lift |
| **P262** | **9.71 s** | the settle threshold |

**-28.3 % over the arc** at ~99 % placed. **Remaining blocks**: `place` 3.01 (clear 0.43 +
blend 1.25 + Cartesian 0.68 + low 0.65), `rel_low` 1.23 (the accompanied descent, at the
profile's own 0.30 m/s cap), `grip` now **1.26** (0.78 + 0.47), `descent` 1.1-1.9,
`close` 1.10, `lift` 1.20.

**Honest caveat unchanged**: `gap` is bimodal per cell, so throughput is a **range
(~4.7-4.9 picks/min at 0.08)**, never a point.

## 6. Pins

No `src/` or `configs/` change (the tree is P261's: `tasks.py` `6e1600ac`, `rl_env.py` with
`_lift_dz_arms`, references **`61fb5202` / `61fb5202` / `18b101bf`**, ckpt
`p227_panda156`); `scripts/290_single_arm_continuous.sh` carries the new setting and its
measurement; `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**. Evidence
`logs/p262/`.
