# P235 results: the place-speed cell cannot be read on this lane - the leg it moves is not the cycle's block

**2026-11-24, `logs/p235/`.** Measurement only (env knob, no `src/` change).
Pre-registration: `logs/p235/PREREG.md`. **The registered falsifier fired.**

---

## 1. The cells

`FRUIT_BELT_SPEED=0.08`, `FRUIT_CYCLE_REPORT=1` on both arms, 6 episodes each,
seeds 901/902:

| arm | `FRUIT_SPEED_PLACE` | placed | episode `ticks` (median) |
|---|---|---|---|
| C (control) | unset (0.35) | **12/12** | 1988 |
| T (treatment) | **0.52** | 11/12 | **2033 (+46, +0.38 s)** |

The count is a tie inside the draw; **the attempt got *longer* in T**, which is the
P86/P88/P89 shape (a block moves, the delivery re-absorbs it).

## 2. The falsifier fired: the leg the knob moves is not the block

`FRUIT_CYCLE_REPORT=1` prints **no `[cycle]` rows at all** on this lane - the block
report exists for the scripted two-line path, not for the direct single-arm cell.
So the manipulation check had to be done with `FRUIT_MOTION_REPORT=1`, 2 episodes
per arm:

| arm | `carry place0` |
|---|---|
| C | 6 cm, **84 ticks** |
| T | 5 cm, **83 ticks** |

**The place leg is 6 cm and 0.7 s, and it does not move** (83 vs 84 ticks). The
reason is the one P89 measured from the other side: the min-jerk profile switches
regime at **~0.225 m**, and below that the leg is **acceleration-bound**, so a
higher `v_max` cannot shorten it. `place0` is far below the switch.

**So the "place block ~4.0 s" that P227r's cell shortened at 0.12 is not
`place0`** - it is the **transit** (the joint blend to `bin{index}_above` plus the
Cartesian run to the bin), which P227r's block-level `[cycle]` report spans and
which a per-leg 6 cm row cannot show. **This lane has no block-level instrument**,
so a place-speed cell cannot be read here at all: P1's registered falsifier
("if the block does not move, nothing is measured") is the honest verdict.

**The +46 ticks in T is therefore branch noise, not the lever** - and it is quoted
only to show that a 12-episode count difference is inside what a re-drawn
acquisition produces on a cell whose block did not move.

## 3. What this leaves for 分拣速度

1. **The lever's target is the transit, not `place0`.** Any further throughput cell
   on this lane must first have a **block-level report for the direct single-arm**
   (the `[cycle]` marks the two-line has), or it will keep measuring a leg that
   cannot move.
2. **The two profile cells that were readable are both negative** (P88 place at
   0.12, P89 lift), and P235 adds that the remaining place lever targets a block
   this lane cannot instrument. So the honest statement about 分拣速度 on this cell
   is unchanged: **≈14.5 s/attempt, cycle-bound, and no profile cell has shortened
   the delivered attempt** - the only measured shortening in the record is
   P227r's **release trim** (1.63 -> 1.00 s, shipped), which is a dwell, not a
   motion.
3. **The cycle's big terms are structural**: ~4 s place transit (a joint blend +
   Cartesian run over the bin reach), ~1.6 s lift (a grip establishment the record
   has measured as unsafe to speed up), ~2 s pre-pose/hover, ~1 s approach. Any of
   them needs a *motion* change with its own block instrument.

## 4. What this phase produced

* a **falsified** throughput hypothesis, honestly: the knob is not the block;
* the **instrument gap** named: no `[cycle]`-style block report on the direct
  single-arm lane - the thing any future speed cell needs first;
* one more data point on the P86/P88/P89 pattern: **an attempt's span is not a
  block**, and a 46-tick difference appeared on a cell whose block did not move.

## 5. Pins

No `src/` or `configs/` change; `tasks.py` **`c16c8291`**, `rl_env.py` unchanged
by this phase; references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
checkpoint `p227_panda156` used as-is. Evidence
`logs/p235/{PREREG.md, C/, T/, Cm/, Tm/}`.
