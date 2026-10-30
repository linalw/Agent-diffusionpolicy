# P66 phase 2 results — the lift-end-height ladder (the left's rotation is a height problem)

Written by the orchestrator (the lane that ran the batch died on a connection reset
after the batch completed; its logs are intact and the table below is re-derived
from them). Tree: HEAD `2331733` + the P66 phase-2 instrument/knob (uncommitted at
the time). **No shipped default changed**; `configs/*` untouched.

Registration: `logs/p66/PREREG_P2.md` (the lift-end ladder, the predicted
`drift_end` 24.6 / 8 +- 3 / 3 +- 2, the endpoints, F1-F4).

## The cell

3 seeds (77/101/202) x 15 picks, **interleaved control -> L1 -> L2 -> control**,
one claim per run, the shipped direct profile + `FRUIT_CARRY_DIAG=1`; logs
`logs/p66/p2/{C1,L1,L2,C2}_{seed}.log`. `FRUIT_LIFT_DZ` unset = control (0.36),
`0.00` = L1 (0.28), `-0.08` = L2 (0.20).

## The table (the left's `grasp_lift` legs, from the `[carry]` rows)

| arm | lift end | `drift_end` median [range] | `res_end` | left placed | right placed | wall s/pick |
|---|---|---|---|---|---|---|
| C1 (shipped) | 0.36 | **23.8 [21.5-28.0]** | 80.6 mm | **1/13** | 29/32 | 35.40 |
| C2 (repeat) | 0.36 | **25.7 [20.8-28.3]** | - | **0/21** | 23/24 | 34.26 |
| L1 | 0.28 | **9.7 [7.0-14.0]** | 33.7 mm | **1/18** | 24/27 | 35.52 |
| **L2** | **0.20** | **0.7 [0.6-6.0]** | **13.3 mm** | **10/16** | **26/29** | **34.16** |

Controls pooled **1/34 = 2.9 %**; L2 **10/16 = 62.5 %** (~21x). **The right arm is
flat in shape** (88.9-95.8 % across the arms) and **its `drift_end` does not move**
(26.0 / 25.9 / 26.2 / 26.2) - the left-only scope holds.

## The mechanism (two instruments and an offline cross-check)

1. **The mediator has zero overlap**: 23.8/25.7 (controls, n=34) vs 9.7 (0.28) vs
   **0.7 [0.6-6.0]** (0.20) - monotone in one variable, per leg, not a count.
2. **The achieved position error collapses with it**: `res_end` **80.6 -> 33.7 ->
   13.3 mm** - the arm stops trading position for orientation.
3. **The static sweep predicted it with no payload, no controller, no profile**:
   `T0` at `belt_top + 0.36` is **24.27-60.00 deg** off with `margin +0.000` on
   25/25 cells (`logs/p66/STATION_SWEEP.md`), so P63's *live* 24.6 deg **is** the
   static number - the drift was never a controller defect.
4. **The dose is the achieved belt projection, not the tilt's share**: `|tool_y|`
   **0.322 / 0.327 -> 0.162 -> 0.002** (the "share" reading is withdrawn - at 0.20
   `sin(tilt) = 0.012`, so the share is a knife-edge quotient of a vanishing
   vector).

## The cost

**Flat**: wall **35.40 / 34.26 -> 34.16** s/pick, sim **15.0 -> 14.7** s/pick (the
lift is ~77 ticks shorter and the place leg only 7-9 longer). The wall column is
renderer-dominated; the sim column is the one to quote.

## The residue (do not read the win as "the carry class is fixed")

L2's **6/16 `cnp` are place-leg losses** (`clean_slip` 833-931 mm on the four
seed-77 cases; 18-21 mm re-seats even on two *placed* legs), on legs whose tilt
reads **75-91 deg** with `tool_y +0.65..+0.70` - **the place leg reinstates the
belt-aligned attitude by reach and the lift's height cannot touch it**. The
**control has no loaded left place legs at all** (every control place row reads
`contacts@onset = 0`: the payload was already gone), so that class's baseline is
the right arm's, not the left's.

## The registered clauses (dispositioned in `logs/p66/DEVIATION.md`)

* **F1 fired on its letter** (0.7 vs 3 +- 2) - a **favourable** miss: the prediction
  scaled the static curve linearly and the live response is steeper at the bottom;
  monotonicity and ordering held. No re-run.
* **F4 fired falsely**: `fruit fell off the line` is shared with the **pre-grasp
  supply** class; 4/4 events are right-arm `grasped=False`, `decision == ticks`
  kiwis and **2 of them are in the control**. The intended read (place-leg payload
  loss) is 6/16 at 0.20 and **unmeasurable in the control**.
* **P3 was self-contradictory** ("projection unchanged +0.32..+0.37" AND "the drift
  falls to 3 deg" cannot both hold) - amended to `|tool_y|` as the dose.

## Status of the adoption

**Not adopted at this phase.** Oracle gate 2 returned **CONFIRM-FIRST**:
- the count is **3 seeds** and the convention for a default is **WS-4.2 N=5**
  (5/5 gives p = 0.031, the design's ceiling); the *mediator* does not need it (it
  has zero overlap);
- **one unmeasured cost can still block**: the lift's end is 0.16 m lower, so the
  payload crosses the output rail ~30 mm lower, and the record's clearance
  arithmetic is 1:1 per mm (+35 mm at the shipped transfer; -45 mm at
  transfer-lift 0). The P2 battery ran with `FRUIT_MOTION_REPORT` unset, so **no
  `[motion] carry place0 clearance` row exists** - the instrument is a print-only
  `clr` field on the `[carry]` row (`tasks.py` already measures it every tick);
- **the rung is a decision, not a guess**: the response is a **cliff** (0.28 ->
  9.7 deg and still 1/18), so the N=5 batch carries **0.24 as well as 0.20**; if
  0.24 matches, ship 0.24 and halve the cost.
The N=5 x 3-rung batch is `logs/p66/p3/` (in flight).
