# P251 results: the residual class is a **failed grasp probe**, the gain is not its actuator, and the "1 m excursions" are a **lost payload**

**2026-11-25, `logs/p251/`.** Two knob ladders on the hard instance (seed 901's
2.8 cm lychee), 18 + 6 one-episode runs. **No `src/` change** - every knob used
already existed (`FRUIT_IK_GAIN`, `FRUIT_DYNAMIC_CATCH_TICKS`, `FRUIT_TRACK_DIAG`,
`FRUIT_CYCLE_REPORT`).

---

## 1. The gain ladder is a draw: "the command outruns the drive" is not the actuator

`FRUIT_IK_GAIN` scales the differential-IK step (the controller integrates on a
**commanded** joint vector `_q_cmd`, so `lag = _q_cmd - measured` is exactly the
drive's following error). Six one-episode runs per rung:

| gain | placed | `lag_norm` (P250's trace) |
|---|---|---|
| 0.5 | **3/6** | - |
| 1.0 (shipped) | **2/6** | 0.18-0.27 on failures, 0.11 on passes |
| 2.0 | **2/6** | - |

**A draw at n = 6.** Slowing the command down does not help and speeding it up does
not hurt, so the persistent 0.18-0.27 rad lag is **not** the thing to fix by gain.

## 2. What *does* separate: the `grip` block, on every failure

The 18-run cycle decomposition (block report, one attempt each). The discriminator is
not `seat` and not `descent`:

| block | passes | failures |
|---|---|---|
| **`grip`** | **1.58 s on 10 of 11** (one 1.60) | **4.53 s on 10 of 11** (one 4.43) |
| `seat` | 0.17-0.78, **one at 1.67** | mostly 1.67 |
| `descent` | median 4.81 | median 4.78 (one 7.67, one 12.16) |
| `close` | 1.10 | 1.10 |

`grip` 4.53 s = **1.58 (the clean probe) + 2.95 (two failed re-grasp probes)**. So
the failure is **"the pads close off the fruit, three times"**, and `seat` is *not*
the discriminator: **a passing attempt also ran the full 200-tick catch-up**
(`g1.0/r5`, seat 1.67, grip 1.58, placed). This is the same correction P250 made from
the other side (a pass with a 50.8 mm start).

**So the chain is: the catch-up ends 39-46 mm off -> the close is 1.10 s of ramp onto
a fruit that is not between the pads -> the probe fails -> two re-grasps fail -> the
attempt is lost.** Consistent with the one note a failing run prints:
`carry grasp_lift: stored pad centre 102 mm from the measured pads; re-anchoring`
(the payload's bookkeeping is 102 mm off, i.e. no payload was between the pads).

## 3. A longer budget makes it **worse**, and that corrects the record

`FRUIT_DYNAMIC_CATCH_TICKS=400` (6 runs): **1/6 placed**, and the residuals become
**1333 / 1348 / 1362 / 1182 mm** instead of 39-46. The components of the worst one:

```
[catch] idx=3 arm=left ticks=400 residual=1333.4mm (x=-8.2 y=-391.7 z=+1274.5)
```

**`z = +1274 mm` is the payload 1.27 m BELOW the tip**: the fruit has left the belt
(it fell / was recycled) and the loop keeps chasing it. The arm is not moving anywhere.

**That is what the record's "runaway excursions" are.** P241's 41.6 mm is a genuine
arm stall (x = +34.8); **P242's 419 mm (z = +410.8) and P244's 1079 mm (z = +1075.9)
are lost payloads read as the loop's target** - the same `z`-dominated shape and the
same magnitude, now with a mechanism instead of a hypothesis. P243's 97 mm (x = -96.9)
sits between the two and is not settled by this phase.

**So: the excursions are a *consequence* of the catch failing, not a cause** - which
is why P243/P244/P246 could not attribute them: they were trying to explain the
*arm*, and the number was the *fruit*.

## 4. What the objective gets from this

| | |
|---|---|
| the 2.8 cm class's failure is | a **failed grasp probe** (`grip` 1.58 -> 4.53 on 10/11 failures) |
| its actuator is **not** | the IK gain (draw), the catch-up exit (a pass also ran 200 ticks), the time budget (a longer budget loses), a joint limit or singularity (P250), the start offset (P250) |
| the record's "1 m runaway" | is a **lost payload**, not an arm excursion |

**The honest position**: the cell's per-size success is **80 % (0-4 cm) / 90-95 %
(4-7 cm)** and the residual class is a **small-instance grasp** whose software
actuators are now measured out (exit, budget, gain, limits, singularity, start
offset, seat). What remains is the record's own hardware list
(`logs/p42/SIM_LIMIT.md`: a new pad asset or a real-jaw clamp-force anchor) or a
station/aim change for the smallest class - **neither is a knob**, and both are
priced there.

**No rate is claimed for the class**: 11 attempts per arm at 33-50 % cannot separate
these rungs, and every rung is one draw of the loop.

## 5. Pins

No `src/` or `configs/` change (the tree is P250's: `tasks.py` `b68ac8d1`,
`rl_env.py` `TASKS_MD5` follow, references **`61fb5202` / `61fb5202` / `18b101bf`**,
ckpt `p227_panda156`); `accept.sh` therefore stands at P250's
**459/459 + `fingerprint: matches`**. Evidence `logs/p251/`.
