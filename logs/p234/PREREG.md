# P234 pre-registration: how wide a lateral band does the cell tolerate?

**Pinned 2026-11-24, before any widened-band cell was read.**

## Why this rung

The disturbance ladder so far is **temporal** (P232: a belt-speed wave) and it
found the bound is the line's **peak** speed. The other axis a real line presents
is **spatial**: the fruit does not arrive on a single centre line. The shipped
supply draws `x` uniformly in `[0.20, 0.36]` (`fruits.SUPPLY_X_MIN/MAX`), and the
record has three measured edges around it:

* the reach map's **clean** top-down band is `x = 0.18-0.39` with a hard cliff at
  `0.42` (`scripts/174_station_reach.py`, `logs/v1/61_station_reach_seeded.log`);
* the trigger's **admission floor** is per arm: right `x >= 0.1730`, left
  `x >= 0.1800` (P38's census) - a fruit below it is refused, and the episode ends
  `no firable fruit` / `fruit fell off the line`;
* the delivered `x` is spawn `x` **plus a per-instance release offset**
  (`-41 .. +69 mm`, P38), so the tails are wider than the planned band.

The shipped band sits **inside** all three edges. This rung asks how much margin
there is.

## The cells

`FRUIT_BELT_SPEED=0.08`, `FRUIT_SUPPLY_X_MIN=0.17`, `FRUIT_SUPPLY_X_MAX=0.39`
(the two measured boundaries exactly), seeds 901/902 x 6 episodes,
`FRUIT_EVAL_LATENCY=auto`. Baseline: P230's shipped-band 0.08 cell (**11/12**).

## Predictions

**P1 (manipulation).** The `[supply] ... lateral x=0.20-0.36` row reads
**0.17-0.39** in both cells. A cell whose row still shows the shipped band did not
take the override.

**P2 (the count).** Placed falls **below 9/12**. The two added tails are each
3 cm, and both are outside a *measured* edge (the low one below the admission
floor, the high one at the clean band's top).

**P3 (the mechanism, and which tail bites).** The **low** tail produces the
P38 refusal class (`lateral refuse` / `no firable fruit` / `fell off the line`);
the **high** tail produces acquisition residuals or the reach cliff. The failure
keys name which tail is the binding one - and that is the rung's real output,
because a line's splitter decides which tail it can afford.

**P4 (the optimistic branch).** If it holds **>= 11/12**, the cell tolerates a
**0.22 m** band - wider than the shipped 0.16 - and that is a *widening*
opportunity (more supply variety at no placement cost), which would need the
`supply.band` manifest field (P93) to be honoured rather than re-recorded.

## Read rules

* 6 x 2 is a draw (P93); the class counts are the claim.
* The band change is a **supply** change, so the
  `[supply] scatter ... lateral x=` row is the manipulation check and the
  `[bed-*]`/`[fall]` rows are the mechanism.
