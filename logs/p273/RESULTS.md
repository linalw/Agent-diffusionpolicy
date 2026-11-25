# P273 results: the tolerance's difference **flips sign** on fresh seeds - the lever closes as not reproduced

**2026-11-25, `logs/p273/`.** The registration P271 asked for: a **difference** endpoint, powered
(**4 fresh seeds 909-912, 20 picks each = 80 per arm, 8 cells**, the landing trace on **both**
arms). **P1 fails on its direction; P2 passes. Nothing ships - the tolerance closes.**

---

## 1. The cells

`v = 0.12`, `FRUIT_PLACE_TRACE=1` + `FRUIT_CARRY_DIAG=1` + `FRUIT_TRACK_DIAG=1` on **both**
arms:

| arm | placed | catches | **true stalls** | `on_belt` | `grasped=True placed=False` | cycle |
|---|---|---|---|---|---|---|
| **C, 6 mm** | **63/80 = 79 %** | 74 | **7 (9.5 %)** | **63/63** | **0** | 9.61 s |
| **T, 7 mm** | **62/80 = 78 %** | 75 | **12 (16.0 %)** | **62/62** | **0** | 9.57 s |

Per cell: C 14/17/19/13, T 17/15/16/14 of 20.

## 2. The registered verdicts

**P1 FAILS, and on the sign**: the bar was *"T at least 5 points **lower**"*; the measurement is
**6.5 points higher** (C-T = **-6.5**), Fisher exact two-sided **p = 0.326**.

**P2 PASSES**: `62 >= 63 - 4`, and **no place-leg loss with the payload present at the
release** in either arm (**63/63** and **62/62** `on_belt`, zero `grasped=True placed=False`).

**P3 (report)**: cycle **9.57 vs 9.61 s** - flat, as everywhere in this arc.

## 3. Three batches, three readings, and the last one reverses

| batch | seeds | cells | trace | C | T | reading |
|---|---|---|---|---|---|---|
| P269 | 907/908 | 40/arm | **off** | 19 % | 9 % | **-10 points** |
| P271 | 907/908 | 40/arm | on | 14 % | 11 % | -3 points |
| **P273** | **909-912** | **80/arm** | on | **9.5 %** | **16.0 %** | **+6.5 points** |

**The largest and freshest batch reverses the sign of the first.** The two "positive" batches
were 40-pick draws (7 and 5 stalls respectively); at 80 picks per arm the effect is **not
there**.

**So the tolerance's class effect is closed as NOT REPRODUCED.** It is not "unresolved" any
more: with the powered difference read, the honest statement is that **the 7 mm exit does not
reduce the true-stall rate**, and the two earlier readings were draws.

## 4. What that does to the 0.12 acquisition sub-arc

| lever | measured | verdict |
|---|---|---|
| the catch-up's **clock** (P266) | true stalls 10 -> 3, but it truncated chases that **were** converging | **closed** |
| the pad **force** (P268) | 10 of 10 stalls, only 2 had the contact the criterion needs | **closed** (no contact) |
| the exit **tolerance** (P267/P269/P271/**P273**) | -10, -3, **+6.5** points at 40/40/80 per arm | **closed as not reproduced** |

**All three software exits on this class are now measured and closed.** What is left is what
P268 named: **the arrival side** (`past_aim` vs upstream, P109's window, whose far end is the
bistable runaway at 4 of 4 seeds) or **the y-axis / hardware** - and the grip/hold class, which
is `logs/p42/SIM_LIMIT.md`'s list.

**And the read rule this arc earns**: a class-level effect that **changes sign** across three
batches of 40-80 picks per arm is not a lever - **one 40-pick batch cannot rank two exits**, and
an effect that survives only at 40 is a draw with extra steps.

## 5. No-harm

No `src/` or `configs/` change (the tree is P268's: `tasks.py` `141cd178`, references
**`61fb5202` / `61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `accept.sh` stands at P268's **459/459 +
`fingerprint: matches`**. Evidence `logs/p273/` (`PREREG.md` pinned before the cells).
