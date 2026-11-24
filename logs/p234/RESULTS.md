# P234 results: a 0.22 m lateral band costs nothing at 0.08 - and the admission floor does not hold as documented

**2026-11-24, `logs/p234/`.** Measurement only: **no `src/` or `configs/` change.**
Pre-registration: `logs/p234/PREREG.md`.

---

## 1. The cells

`FRUIT_BELT_SPEED=0.08`, `FRUIT_SUPPLY_X_MIN=0.17`, `FRUIT_SUPPLY_X_MAX=0.39`
(the shipped band is `0.20-0.36`), seeds 901/902 x 6.

| cell | planned band | placed |
|---|---|---|
| shipped (P230) | 0.20-0.36 | 11/12 |
| **widened** | **0.17-0.39** | **12/12 = 100 %** [76, 100] |
| widened + `FRUIT_FIRE_DIAG=1` | 0.17-0.39 | 4/6 (**not comparable**, section 3) |

**P1 (manipulation) PASSES**: the `[supply] scatter ... lateral x=` row reads
**0.17-0.39** in both cells.

## 2. The verdict: P2 fails, P4 applies - with a caveat the phase states

The registered prediction was that placed falls below 9/12. **It did not: 12/12.**
So the cell tolerates a **0.22 m** band - wider than the shipped 0.16 - and that is
the optimistic branch.

**The caveat is the one that matters**: 12 attempts cannot price a *rare* event.
P38's census puts the below-floor class at **~0.06 %/episode** at the shipped band
and the delivered-x tail at `-41 .. +69 mm` of per-instance release offset; a
widened band moves more mass into those tails, but at a rate that needs hundreds
of attempts to see (P38's own conclusion: at 75 episodes/arm an A/B "cannot
measure the class"). **So the honest sentence is: no cost observed at 12 attempts,
not "the tails are free".**

## 3. The diag cell is a different branch, and it says so

`FRUIT_FIRE_DIAG=1` (which prints the per-fire-tick row) reads **4/6** on the same
band and seed. That is the P230/P232 lesson at the level of a **count**: a
per-tick print added to the close path shifts the branch, so **a diag cell's rate
is not the cell's rate**. It is quoted here only for the x it exposes.

## 4. A number that does not match the record

The delivered `fruit_x` values in the diag cell were **0.169** and 0.224. `0.169`
is below the shipped band's floor (0.20) **and** below the arm's documented
admission floor (P38: right **0.1730**, left **0.1800** - derived from
`dx = x - station_x`, `|dx| <= lateral = 0.16`). **A fruit 4 mm below the floor
fired and was attempted.**

So one of two things is true, and this phase does not know which: the floor's
derivation (a single `station_x` per arm) does not describe this cell's gate, or
the `[fire]` row's `fruit_x` is not the value the gate compared. **Either way the
floor must not be quoted as a hard bound until that is settled** - and the
instrument that would settle it is one row printing `dx`, `lateral` and the x each
side used, at the gate tick, not at the servo tick.

## 5. What this gives the objective

* **The lateral axis is not the binding disturbance** at the objective's starting
  speed: doubling the band's spread costs nothing measurable, while a
  **17 %** belt-speed crest at 0.18 costs a quarter (P233). The specification the
  cell imposes on a line is therefore **peak speed**, and the lateral band is
  generous.
* **The disturbance ladder now reads**: temporal 0.08 free to ±75 %; temporal 0.18
  costs at ±17 %; spatial 0.08 free at 0.22 m. The bound is speed.
* **Two instrument facts**: a per-tick print can move a 6-episode count by two
  (4/6 vs 12/12 on the same configuration), and the delivered-x/admission-floor
  pair needs a gate-tick row before it is quotable.

## 6. Pins

No `src/` or `configs/` change; `tasks.py` **`c16c8291`**, `rl_env.py` unchanged by
this phase; references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
checkpoint `p227_panda156` used as-is. Evidence
`logs/p234/{PREREG.md, lat089/, lat089diag/}`.
