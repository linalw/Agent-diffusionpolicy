# P229 / Stage 1 pre-registration: the belt-speed ladder

**Pinned 2026-11-24, before `scripts/288_speed_ladder.sh` finished and before any
cell was read.** No cell of this phase has been inspected; the only prior
knowledge is the code read below and P228's latency measurement.

## The correction this phase starts from

`docs/ARCHITECTURE_4T.md` (first draft) claimed the handover lead is a **constant
distance** `0.19 m`. Reading the code, that is **wrong**, and the correction is
recorded before the measurement rather than after it:

```
_dynamic_pick_lead() = min( v * (0.40 + t_desc + 0.15) + 0.03 , 0.80 )   # tasks.py:10363
acquisition_window() = 0.90 + 0.60 + |jaw-station| / 0.20   [s, capped 4.5]  # trigger.py:246
```

Both are **time budgets converted at the belt speed** (the second is already a
time). The 317 attempts that all read "0.189 m" did so because they all ran at
**0.12 m/s**. What is actually hard-coded is the **terms inside the budgets**
(`0.40 s` setup, `0.15 s` descend margin, `0.03 m`, and the trigger's
`0.90 + 0.60`), and **none of them carries the measured decision latency**
(P228: 66 ms = 8 mm at 0.12 m/s, 20 mm at 0.30).

So the question is not "is the lead a constant" but: **does the time budget still
hold when the belt speeds up, and if not, which term is short?**

## The cells

`FRUIT_BELT_SPEED ∈ {0.06, 0.12, 0.18, 0.24, 0.30}` x seeds {901, 902} x 6
episodes = 60 episodes, the `284` recipe verbatim, **`FRUIT_EVAL_LATENCY=auto`**
on every cell (P228's conclusion: a `d=0` cell reports a latency the machine does
not have). The arm's lag in **distance** therefore scales with the belt: 8 mm at
0.12 m/s, 20 mm at 0.30, against a **6 mm** catch tolerance.

Two declared notes: the direct lane's `FRUIT_POLICY_TRIGGER_ACQ` resolves **on**
for `presentation=direct` (P54), so the trigger lead is the acquisition form, not
`0.90 s`; and `FRUIT_SKIP_LATE=0.5` is unchanged, so a fruit whose `t_arrive`
falls below 0.5 s is **handed off**, not attempted - at 0.30 m/s that is 0.15 m
from the station.

## Predictions

**P1 (manipulation).** Every `intercept trigger` row's `speed=` equals the cell's
`speed` (the encoder reads the applied surface velocity), and the fire's `dy`
equals `t_arrive x speed` to the printed precision. A cell whose `speed=` does not
match its name is not a speed cell.

**P2 (the lead is a time).** The trigger's `lead` is **flat across speeds** - it
is `0.90 + 0.60 + distance/0.20`, none of which is a function of belt speed - so
`dy` at fire **scales linearly** with `v`. If `lead` moves with speed, something
other than the acquisition window is setting it and that has to be found before
any other read.

**P3 (where it breaks, and with what class).** The cell is expected to hold at
0.06-0.12 and to degrade at >= 0.24. The registered failure class at high speed
is the **catch-up** (`dynamic catch-up` / never-held / `fruit fell off the line`),
**not** the grip class - because the catch-up's closing speed is
`arm_speed - belt_speed` and at 0.30 m/s the fruit crosses the borrowable 0.19 m
in 0.63 s. If instead `fruit did not follow the gripper` dominates, the belt
speed is acting through the **grasp** (relative velocity at contact), which is a
different mechanism and has to be reported as such.

**P4 (the latency term's share - conditional).** `auto`'s lag is 8 mm at 0.12 and
20 mm at 0.30. **Only if P3 breaks at 0.30**, run the same speed at
`FRUIT_EVAL_LATENCY=0` (2 seeds); if the failure survives with no injected
latency, the latency is not its cause and the budget's other terms are.

**P5 (the null branch).** If the placed count is flat from 0.06 to 0.30, then the
shipped budget **already scales** and the arithmetic change has no measured
justification. That is a result: report it, do not change the formula, and move to
Stage 2. A formula rewrite without a measured failure is exactly the kind of
change this record refuses.

## Read rules

* 6 episodes x 2 seeds is a **branch draw** (P93); the CIs are printed. The
  mechanism columns - `speed`, `lead`, `t_arrive`, `dy`, the failure keys - are
  what the phase can claim.
* A `nan` column means the row was absent. An absent trigger row is itself a
  measurement: that attempt never fired.
* No cross-speed rate comparison as a rate; the speed ladder is a **scenario**
  change (the supply's arrival spacing in time changes with `v` at a fixed
  metre gap), so quote per-cell counts and the mechanism.
