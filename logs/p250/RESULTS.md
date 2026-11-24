# P250 results: the "first-attempt" class is **one instance**, and its mechanism is a drive-tracking stall

**2026-11-25, `logs/p250/`.** A corpus census (312 episodes already on disk) plus four
one-episode runs with the catch-up IK trace. **One instrument fix shipped** (the trace
name is per-process); no behaviour change, no default moved.

---

## 1. The census: "episode 0 is worse" is a **composition** effect, not a position one

Over **312 episodes** in 39 runs (`logs/p23x`–`logs/p25x`, all on the same cell):

| episode index | placed |
|---|---|
| **ep 0** | **38/55 = 69.1 %** |
| ep 1 | 49/53 = 92.5 % |
| ep 3 | 32/32 = 100 % |
| ep 4-7 | 66/69 = 95.7 % |
| ep >= 8 | 47/48 = 97.9 % |

**All 31 failures are `no-grasp`** (not a place, not a release). The first split
looks like an episode-position defect. It is not:

| | median diameter | 
|---|---|
| ep 0 | **2.80 cm** |
| ep >= 1 | **6.10 cm** |

The first draw of the shuffle is a small grade-A fruit, so ep 0 is almost always the
**same instance**. Split by species:

| species | ep 0 | ep >= 1 |
|---|---|---|
| **lychee** | **13/30 = 43.3 %** | **29/29 = 100 %** |
| strawberry | 23/23 = 100 % | 25/28 = 89.3 % |
| kiwi | 2/2 | 27/33 = 81.8 % |
| pear / orange / apple / peach / tomato | - (never drawn at ep 0) | 93.8-100 % |

**Every lychee failure in the corpus is the same body**: `d=2.8 cm, arm=left`, i.e.
seed 901's first draw. **All other lychee instances pass 29/29.** The strawberry -
which is the *other* small class and also drawn at ep 0 - passes **23/23**.

So the class is **"the pool's smallest instance"**, not "episode 0", not "a small
fruit", and not "a cold start".

**The failure budget of the cell, in one table** (all episodes):

| diameter | placed |
|---|---|
| **0-4 cm** | **72/90 = 80.0 %** |
| 4-5 cm | 18/20 = 90.0 % |
| 5-6 cm | 59/63 = 93.7 % |
| 6-7 cm | 132/139 = 95.0 % |

with lychee the worst species (**42/59 = 71.2 %**) and the 2.8 cm instance carrying
**17 of the 31 failures**.

## 2. The trace: it is a **tracking** stall, and three hypotheses are falsified

Four one-episode runs at seed 901 (the hard instance), `FRUIT_CATCH_TRACE=1`:
**2/4 placed** (43 % - the census rate). Each run's trace now lands in its own file
(§4), so the failing ones were readable for the first time:

| run | outcome | `task_err` first -> last | min | `lag_norm` mid -> last | clipped | min margin | min sigma |
|---|---|---|---|---|---|---|---|
| r1 | **FAIL** | 56.5 -> **39.5** | 38.4 | 0.202 -> **0.269** | 0 | +0.512 | 0.153 |
| r3 | **FAIL** | 44.9 -> **46.3** | 41.9 | 0.179 -> **0.182** | 0 | +0.542 | 0.159 |
| r2 | pass | 31.6 -> 23.9 | 23.9 | 0.112 -> **0.106** | 0 | +0.454 | 0.214 |
| r4 | pass | 50.8 -> 28.6 | 27.4 | 0.114 -> **0.116** | 0 | +0.429 | 0.205 |

**What separates see from not-see is not the start offset**: r4 starts **worse**
(50.8 mm) than r3 (44.9) and converges to 27 mm; r1 starts at 56.5 and stalls at 39.
**What separates them is the persistent joint-space lag**: failures hold **0.18-0.27
rad** (r1's still *growing*), passes settle at **0.11 rad** - i.e. the arm's normal
following error.

**Three hypotheses falsified by this table:**

1. **joint limit**: `limit_clipped = 0` on **all 200 samples of every run**, and
   `limit_margin` is **positive and large** (+0.43 to +1.42 rad) - the failing runs
   have *more* margin than the passing ones;
2. **singularity**: `sigma_min` 0.153-0.214 on every sample (failures only modestly
   worse), no collapse;
3. **the catch-up's start offset**: see above - r4 pass with the worst start.

**And the exit is not the failure**: r4 also ran the **full 200 ticks** and placed.
So P239/P243's 200-tick tax and this failure are **different objects**; the axis
exit removes the tax, and it cannot fix a stalled arm.

**What the failure is, stated exactly**: the arm does not follow its own commanded
target (0.18-0.27 rad of persistent joint lag against 0.11 normal), so the catch-up's
residual plateaus at 39-46 mm and the close then finds the fruit outside the pads
(`close: fruit drifted ... ; re-closing` -> `fruit did not follow the gripper`). **Why
the arm lags on this instance is not identified** - the candidates are a torque/gravity
limit at that extension and a commanded target that outruns the drive's rate (r1's lag
still grows), and the instruments for both exist (`dq`/`lag` per tick in this trace,
plus the joint drive readback).

## 3. What this corrects in the record

* **P246's open item narrows**: the "first-attempt excursion" is not a first-attempt
  property at all - it is **one instance** at **43 %**, drawn at ep 0 because the
  shuffle's first draw is the smallest fruit. The **1 m runaways** of P241-P244 are
  a different (still open) object: those ran 200 ticks *and* printed residuals
  41-1113 mm on the same instance class, so they are inside it, not beside it.
* **P249's 4/5 cell** loses exactly this instance (ep 0, 44.4 mm) - consistent.
* **The honest rate statement**: the 0.08 cell's rate is **80 % on 0-4 cm and 95 % on
  >= 6 cm**, with everything above 4 cm at **93-100 %**. **No pooled rate is
  claimed** - the pool's size mix decides it.

## 4. The instrument fix (shipped)

`FRUIT_CATCH_TRACE` wrote `catch_{seq:02d}_{arm}.json` with the sequence restarting in
every process and a **shared** directory, so a second run **overwrote** the first
run's traces (P244: 7 files survived 12 catches and the outlier's was gone). The name
now carries the **process id** (`catch_{pid}_{seq:02d}_{arm}.json`); no live consumer
parses the name (only the frozen `logs/p2b` and `logs/w1` copies, which are
historical), and the analysis globs. **This is what made §2 possible.**

No other code change: the per-tick component subtraction P244 flagged was already
moved to the loop's exit in P245.

## 5. The named next lever, with its measured target

The residual success lever on this cell is **one class**: the pool's smallest
instance at **43 %** (17 of 31 failures), and its mechanism is a **drive-tracking
stall**, not the aim, not the exit, not a limit, not a singularity. The record's
already-named principled fix is the one that acts on a persistent tracking error: a
**feed-forward / integral term on the arm's own joint error** (P246 open item 2) -
now with a magnitude (**0.18-0.27 rad** against 0.11) and an endpoint (**the 2.8 cm
class, 43 % -> 80 %** would put the cell at 97 %).

**Not built in this phase**: a controller term on the shared `ik_step` path moves
every leg on every cell, so it owes its own pre-registration, the acceptance, both
references and a store re-baseline - the same price P248 priced for a default flip.

## 6. Pins

`tasks.py` **`b68ac8d1`** (the trace name only), `rl_env.py` `TASKS_MD5` follow;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156`. Evidence `logs/p250/{trace/, ep1/}`; census inputs the
`logs/p23x`-`logs/p25x` cells.
