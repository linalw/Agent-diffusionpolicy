# P68 results — the climb + the wrist hold: the hold makes it WORSE, and the trade is now measured

Written by the orchestrator from the batch's own logs (`logs/p68/pop2_batch.out`,
`A_77/A_101/B_101`); the lane's report was not written before its context ended.
Population cell (all-grade-A supply, every attempt left), `FRUIT_LIFT_DZ=-0.08
FRUIT_LIFT_CLIMB=0.18` in both arms.

## The result

| arm | extra knob | left placed (seed 77 / 101) | place-leg `clean_slip_max > 800 mm` rows |
|---|---|---|---|
| **A** | **+ `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0`** | **0/18 / 0/18** | 2 / 2 |
| **B** | none (P67's pair) | (P67: 3/18 on seed 77) / **3/18** | 0 |

**The wrist hold is negative**: 0/18 against the pair's 3/18. It does not keep the
payload through the climb; if anything it loses more. (A_77's place rows read
`clean_slip 881-1157 mm` with `clr -216..-218` - the payload is gone before the
crossing, so the clearance fields fall back to the on-belt phase.)

## The trade, now fully measured

| form | the carry class | the rail crossing | left placed |
|---|---|---|---|
| shipped (0.36) | 25 deg rotation, 0/25 | +30/+29 mm | **0/25** |
| low lift only (0.20) | **0.7 deg, 14/25** | **+5 mm (floor +33)** | **14/25** |
| low lift + climb 0.18 | 1.1 deg | **+33..+54 mm (passes)** | **3/18** |
| + the wrist hold | 1.1 deg | (payload gone) | **0/18** |

**So the two closed classes meet**: the lift's height fixes the *carry* rotation
(P66: 0.7 deg, 0/25 -> 14/25, N=5, 5/5), and the *only* way to restore the rail
crossing is a vertical transfer at the place leg's start - which drops the payload
on `SIM_LIMIT.md`'s loaded-slide class (3/8 climbed legs, 0.92-1.00 m), and the
record's wrist hold does not save it. **No net gain is shippable today.**

## What this means for the next spend

The left's deficit is **not** a policy/training problem (the class is the
primitive's) and **not** a single knob: it is the **interface's inability to carry
a vertical transfer** plus the **lift height** that forces the rotation. The
remaining levers are exactly the two `SIM_LIMIT.md` sanctions - **a new pad asset**
(P30-C's 24-45 mm magnitude, still owner-gated) or **a real-jaw clamp-force
anchor** - or a **workstation/transfer change** (lower the output rail or shorten
the transit) with both references re-recorded. A recollection/retrain is **not
indicated**: the policy is not where the loss is.
