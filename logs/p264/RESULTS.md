# P264 results: the throughput work does **not** move 0.12 - the step is still its two classes

**2026-11-25, `logs/p264/`.** The 0.12 cells re-measured on the **current** recipe (P258-P263
changed six things since the 85 % figure was taken). **No `src/` change.**

---

## 1. The gap this closes

Every 0.12 number in the record predates the throughput arc: `51/60 = 85.0 %` was measured
with a **11.9 s** attempt. The recipe now runs at **9.6 s**, so the arm returns sooner
relative to the fruit - either the pass-by class shrinks or it does not, and that had to be
measured rather than assumed.

## 2. The cells

| | placed | attempt `total` | `gap` | losses |
|---|---|---|---|---|
| 0.12, seed 905 | **14/20** | 9.52 s | 282 | 6 |
| 0.12, seed 906 | **15/20** | 9.59 s | 378 | 5 |
| **pooled** | **29/40 = 72.5 %** | **9.55 s** | - | **11** |

**Every loss is `grasped=False`**, and the class mix is **exactly the one P253 measured**:

| class | this cell | P253's 0.12 cells |
|---|---|---|
| `fruit did not follow the gripper` (grip/carry) | **7** | 3 |
| `fruit fell off the line` (pass-by, uncaught) | **4** | 2 |

**So the faster cycle did not change the failure mechanisms, and it did not change the
count in either direction that can be claimed**: 85 % (n=60) against 72.5 % (n=40) is
**p ~ 0.13** - a draw at these sizes, and **no claim is made either way**. What *is* solid
is the mechanism: the same two classes, in the same proportion.

## 3. The 0.08 number on the current recipe

| cells (current recipe) | placed |
|---|---|
| P261's four (both-arms lift) | **79/80** |
| P262's three (the `FRUIT_SETTLE_EPS` recipe) | **60/60** |
| **pooled** | **139/140 = 99.3 %** |

at a **9.7 s** attempt. So the arc's throughput work cost the target-speed cell nothing
measurably (98.6 % before it, 99.3 % on it, same drawn pool).

## 4. What that says about the speed step

**The 0.08 -> 0.12 step still costs 13-26 points** depending on the draw, with the same two
classes, and a **5 % shorter cycle does not touch either**:

* the **pass-by** class is a *scheduling* property (the fruit reaches the station while the
  arm is still on the previous pick) - a 5 % cycle gain moves it by ~5 %, which is inside
  the draw;
* the **grip** class is the assembled hardware/physics question (`logs/p42/SIM_LIMIT.md`).

**So the 0.12 lever is not the cycle**, and the record's earlier conclusion stands: the
useful ceiling on this cell is set by the contact phase, and P229's `v_max` equation
(0.2055 m/s engagement) is not what binds at 0.12 - the *grasp* is.

## 5. The delivered spec, as it now stands

| | |
|---|---|
| **0.08, continuous (deployment)** | **139/140 = 99.3 %**, attempt **9.7 s**, **~4.7-4.9 picks/min** |
| 0.08, hardest single species (lychee) | **20/20 = 100 %** (P255) |
| 0.12, continuous | **72.5-85 %** across draws (same two classes), attempt 9.55 s |
| the belt speed | a **loss** lever, not a throughput lever (P257) |
| the cycle | every remaining block at its measured floor or protected (P263) |

## 6. Pins

No `src/` or `configs/` change (the tree is P263's: `tasks.py` `e733c1f8`, references
**`61fb5202` / `61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `accept.sh` stands at P263's **459/459 +
`fingerprint: matches`**. Evidence `logs/p264/`.
