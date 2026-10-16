# P1c PREREGISTRATION: the composition-controlled control for the density lever

Written 2026-10-16, branch `p-supply`, **after** the Oracle review of P1/P2
(`logs/p3/ORACLE_REVIEW.md`), which found that the P1/P2 headline is confounded.

## The finding that forces this test

P1/P2 reported that raising `FRUIT_SUPPLY_PATCH_DENSITY` (D) raises the two-line's throughput and
placement rate (60 % -> 90 % at D=1.60; the interval 16.53 -> 11.25 s). The review's objection,
independently re-derived here with `scripts/200_composition_audit.py`:

1. **`186`'s two "independent" endpoints are one number.** The placement-window throughput is
   `60 / pooled_interval_mean` by the report's own definition, and the batch throughput is
   `success / s_per_attempt`. With a fixed 20 attempts and a flat 9.8-10.7 s cadence, **every
   headline number in P1/P2 is a monotone transform of the success count** - quoting the interval
   instead of the rate selects the config with the best success count.
2. **The success count is class-dominated and the mix moves with D.** The density changes the
   release geometry, so each arm is presented a *different* class multiset at every D. The pooled
   per-(arm, fruit) placement rate spans **0.44..1.00** (left orange 0.44, left kiwi 0.45, left
   lychee 0.73, right pear 0.73, ..., right peach 1.00). Direct standardisation of each config's
   placements against its own mix:

   | config | observed | class-adjusted | gap |
   | --- | --- | --- | --- |
   | patch control (D=1.0) | 12/20 | 13.89 | +1.89 |
   | D=1.5 | 15/20 | 13.92 | -1.08 |
   | D=1.25 | 11/20 | 14.05 | +3.05 |
   | D=1.4 | 16/20 | 14.68 | -1.32 |
   | **D=1.6** | **18/20** | **14.43** | **-3.57** |
   | D=1.75 | 15/20 | 15.12 | +0.12 |

   The adjusted column is **flat to within ~1 slot** across the ladder while the observed column
   swings 11->18. So the positive effect is, to first order, **which fruit each arm was handed**,
   not the density.

3. What *does* survive is the negative: **D=2.0's collapse** (-7 slots adjusted) is a real density
   effect, with the measured mechanism (crowding breaks the acquisition).

**Therefore the P1/P2 adoption recommendation (D=1.60) is withdrawn pending this test**, and this
is the test the review names as the one that matters.

## The design: hold the presented multiset fixed by construction

The only way to hold the mix fixed while the geometry changes is to **remove the class dimension
from the supply**: a single-grade supply. Then every fruit the arm sees is the same species, at
every D, and the presented multiset is identical by construction (no sampling variation at all).

| config | supply | D | line |
| --- | --- | --- | --- |
| C0 | `FRUIT_SUPPLY_GRADES=apple:1`, patch sheet | 1.0 | single arm |
| C1 | `FRUIT_SUPPLY_GRADES=apple:1`, patch sheet | **1.60** | single arm |
| C2 | `FRUIT_SUPPLY_GRADES=apple:1`, patch sheet | 1.60 | single arm (the determinism double) |

ATTEMPTS=20, SEED=5, the shipped single-arm line (the two-line's pure grade routing would starve
one arm on a single-grade supply, so it is out of scope here - stated, not hidden).

Why apple: a mid-grade fruit with a measured two-line placement rate inside the middle of the
0.44-1.00 band (right apple 0.80, the only apple cell with >= 3 attempts), so the test is not run
on the class that fails anyway. This is a **single-species control**, and that is its limitation -
it does not test the mixed-grade cell. What it does test is the thing the review says cannot be
seen otherwise: **does the density change the per-attempt success and the arrival wait when the
fruit is held constant?**

## The criteria (pre-registered)

- **Primary**: the **placements per attempt** and the **no-eligible-fruit starved-slot count per
  attempt** (the arrival-wait channel the review says is the only non-redundant readout), with the
  class fixed. A density effect is claimed only if **both** move in the predicted direction and the
  gap exceeds the branch spread (the P1/P2 history's own run-to-run spread on a fixed config: the
  pooled interval's p90 is 20-46 s, so treat anything under ~1 slot per 20 attempts as noise).
- **Secondary**: the interval decomposition (the attempts-inside vs the idle share), the cadence
  (`s/attempt`) - which the review confirms is flat and must stay flat for the mechanism to hold.
- **Fail conditions**: (a) the starved-slot count per attempt does not fall (then the density does
  not relieve the wait and P1's mechanism claim is false); (b) the placements per attempt do not
  rise (then the P1/P2 gains were composition); (c) any descent outside its motion budget; (d) no
  determinism on C1/C2.
- **The no-harm**: nothing in `src/` changes for this test (it is env-only on the existing knob),
  so the acceptance is not at risk; `172` and `190`'s references are untouched.

## What this test can and cannot settle

- **Can**: separate "density" from "which fruit" on the per-attempt success and the wait.
- **Cannot**: re-establish the mixed-grade cell number (the composition is held fixed by
  construction). If the effect survives here, the honest statement becomes "the density helps
  within a species and the P1/P2 ladder additionally shifted the mix", which is a much smaller
  claim than "adopt D=1.60".
- Either way the conclusion is publishable, and the ladder's **raw** rates must be reported beside
  the standardised ones from now on (`logs/p2d/82_standardised.txt`).