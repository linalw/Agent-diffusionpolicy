# P242 results: the vertical feed-forward holds - 22 ticks on 10 of 12, one runaway, 12/12 placed

**2026-11-25, `logs/p242/`.** The confirmation P241's verdict owed:
`FRUIT_CATCH_Z_FF=6.6` at 0.08, seeds 901/902 x 6.

---

## 1. The cells

| | result |
|---|---|
| catches | **12** (one per episode) |
| `catch ticks` | **22** on 10 of 12; 35 once; **200 once** |
| residual | **5.4-5.9 mm** on the 11 normal, with **`z = -2.1..-2.8`** (the shipped floor was `z = -6.6`) |
| **runaways (`residual > 50 mm`)** | **1/12** (419.1 mm) |
| placed | **12/12** |

Pooled with P241's six attempts: **18 attempts, 17 placed, 2 runaways (11 %), the
non-runaway catch-up a flat 22 ticks**.

## 2. What this settles

**The mechanism is real and reproducible**: the catch-up's 200-tick tax was a
**6.6 mm steady-state vertical error**, and offsetting it makes the loop exit on
its tolerance in **22 ticks** - **1.44 -> 0.18 s**, on 89 % of attempts, at both
seeds.

**The price is a runaway class**: ~**1 in 9** attempts ends with the pad point
100-420 mm above its command and burns the full budget. Two readings remain
possible and n = 18 cannot separate them (the control shows **0/30** in P236-P240,
so the class is at least strongly associated with the offset):

* the 6.6 mm offset steers the command into a vertical region where this arm's
  solve diverges on some approaches;
* or the pre-existing rare flail (P47/P48) is simply more likely to be *seen*
  because the loop now exits early and a divergent approach is no longer masked by
  a 200-tick crawl.

**The placement cost is 1 in 18** (P241's seed-901 episode 0), i.e. the runaways are
not free even when the cell places (P242's runaway still placed).

## 3. The arithmetic, stated so it is not over-read

```
saved      1.44 s x 0.89 = 1.28 s per attempt
paid       1.67 s x 0.11 = 0.18 s  (the runaway burns the same budget)
net        ~+1.1 s per attempt on a ~13.3 s cycle  (-8 %)
quality    1 lost placement in 18
```

**A time win with a quality cost is not a default** - this record's rule is that a
lever which can lose a placement needs the powered cell (P93's ~40/arm) before any
flip, and the two-line gate and both references after it.

## 4. The principled version, named

The 6.6 mm is a **steady-state** error, so the correct fix is a **vertical integral
term or a gravity feed-forward on the axis** - not a constant offset on the command,
which is what pushes the command into the region the runaways appear in. That is a
controller change with its own instruments (the axis's own following error and the
joint torques) and it is **not built**. The constant offset stays a **default-off
measurement lever**.

## 5. What the objective gets from this arc

The cycle at 0.08 is **~13.3 s**, and P236-P242 took it apart:

| block | s | settled |
|---|---|---|
| `place` | 3.48 | constant; P227r's cell moved it at 0.12, negative |
| `release` | 2.2 | dwell trimmed (P227r) |
| `grip` | 1.58 | constant |
| `seat` | **0.17-1.67** | **the 1.44 s is a 6.6 mm vertical droop; a constant offset recovers it at an 11 % runaway price, a real feed-forward is the unbuilt fix** |
| `descent` / `lift` / `ramp` / `return` | see P237 | measured, not movable |

## 6. Pins

`tasks.py` **`e3795cf4`** (unchanged by P242), `rl_env.py` `TASKS_MD5` follow;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156`. Evidence `logs/p242/ff12/`.
