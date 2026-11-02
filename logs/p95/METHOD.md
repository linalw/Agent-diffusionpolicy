# P95 METHOD — where does an incoming fruit get its disturbance?

**Question (P93 §1a / P94 §2).** On the seed-6 attempt-0 right-arm kiwi **both**
cells show the payload already at **2.4x belt speed** (`0.284 / 0.286 m/s`) with
**4.2-4.7 rad/s** of spin **when the descent leg starts**, and the descent itself
does not displace it (`logs/p93/diag.txt`). P93 wrote: *"the disturbance
predates the leg and is present in both arms; its source is open (no trace covers
the wait/pre-pose window; the leading candidate is the other arm's pre-pose
transit)"*. This phase instruments that window and attributes the jump.

## 1. The instrument

`FRUIT_FRUIT_TRACE=<max rows per attempt>` (`tasks.py`, **default off**):
**one row per control tick for the selected fruit**, armed at the attempt's start
(after `_cycle_begin`, before the pre-pose blend) and flushed from
`note_result`, for the whole attempt — the pre-pose blend, the hover move, the
descent's own hover wait, the catch and the carry. That is the window the
phase-sampled `FRUIT_DYNAMIC_TRACE` cannot see: its first row *is* the descent's
start.

Row: `phase` (the last `FRUIT_CYCLE_REPORT` mark — join by construction, no new
bookkeeping), `t`, `p` (m), `v` (m/s), `w` (rad/s), `|v|`, `|w|`, the belt
encoder speed, `held`, and every live fruit within **0.15 m**: its index,
species, offset (mm), velocity, speed, mass, diameter and whether it is being
carried (up to four, nearest first).

**Read class.** These are **fruit-only** reads — the class AGENTS §2 measures as
branch-neutral (WORKLOG *"Correction: it is the arm-link readback, not reads in
general"*: fruit poses *and* velocities were bit-identical at ten attempts;
`logs/451`). The hook is one attribute read per tick on the shipped path and it
lives in `_step_sim`, **never inside `ik_step`**. So the instrument is *claimed*
branch-neutral and the claim is **tested, not asserted** (§3).

**The one read that is not neutral.** `FRUIT_FRUIT_TRACE_ARM=1` adds each arm's
jaw centre, TCP, both finger-link positions, their distances to the fruit and the
jaw span to every row. That is the articulation-link read AGENTS §2 says shifts a
run by 3-14 s and one or two picks, so it is a **separate, declared probe cell**
(`A6`): its *timing* numbers are not quoted, only the geometry it reports, and
`F6` (fruit-only) supplies the branch-true timing. `FRUIT_FRUIT_TRACE_NOOP=1` is
the instrument's own control arm (same hook, same per-tick call, **no readback**,
the `FRUIT_PROXIMITY_TRACE=2` pattern) and is run only if `F6` moves.

## 2. The cells

| cell | seed | attempts | env | purpose |
| --- | --- | --- | --- | --- |
| `F6` | 6 | 20 | shipped + `FRUIT_FRUIT_TRACE=1` | branch check vs `logs/p94/T6.log`, and the jump census over 20 attempts |
| `A6` | 6 | 20 | as `F6` + `FRUIT_FRUIT_TRACE_ARM=1` | **declared branch-moving**: the two hands' distances at the jump |

Seed 6 is P93's witness seed and `logs/p94/T6.log` is that seed's post-P94 record
(P94 §3: seeds 6/101/202 replay their pre-fix records line for line). The
admissibility test is `logs/p94/p94_report.py --same`-shaped: the `[fruit]`
stream of `F6` must be **byte-identical** to `T6` with only the `[ftrace]` rows
dropped. If it is, the fruit-only trace is on the recorded branch and its
velocity history *is* the shipped branch's.

## 3. The jump definition (pinned before the runs)

* `belt` = the belt's encoder speed on the row (`-0.120 m/s` on `-y`).
* **A jump tick** is a row where the selected fruit's speed changes by
  `|Δ|v|| >= 0.03 m/s` in one tick, **or** its spin by `|Δ|ω|| >= 0.5 rad/s` in
  one tick. (A friction/belt drag is a *ramp*: `μ g dt` = 0.04-0.08 m/s per tick
  at μ 0.5-1.0, so the threshold is deliberately above a single tick of sliding
  friction, and a real contact shows as a multi-tick *cluster*.)
* **The departure tick** = the first row with `|v| > 1.25 x belt` that is followed
  by three more rows above it (so a one-tick numerical blip is not a departure).
* For each jump the table prints: tick, `t`, `y` (along-belt position), `|v|`,
  `|w|`, `Δ|v|`, `Δ|w|`, the `dy` to the arm's station, and for every neighbour
  within 0.15 m its `Δv` **on the same tick** and its mass.

## 4. The attribution classes (one per jump, by evidence)

| class | evidence required |
| --- | --- |
| **(a) the other arm's transit** | the other arm's jaw/finger distance to the fruit is at its minimum within the jump cluster and `<= 0.10 m`, and the other arm is in a *moving* phase (pre-pose blend / hover move / descent / carry) — measured on `A6`; `F6` supplies the tick. |
| **(b) the spawn / release** | the fruit's position is discontinuous (a jump > 1 mm in one tick with no contact) **and** the velocity is zeroed at that tick (`spawner.place`/`stop`), i.e. a teleport, not a kick. |
| **(c) the belt / cleat** | the speed change is a *ramp* (friction-bounded, `<= 0.08 m/s` per tick repeated over `>= 5` ticks) and the direction is along `-y` only. P38 already measured the belt's lateral contribution as **exactly 0.000 mm** over 475 transits, so a cross-belt component excludes it. |
| **(d) a depenetration** | the jump is a *pair* event: a neighbour's `Δv` on the same tick is anti-parallel and mass-weighted momentum closes (`|m1 Δv1 + m2 Δv2| < 0.25 |m1 Δv1|`) — i.e. the fruit was pushed out of an overlap. |
| **(e) the grasping arm** | the **active** arm's jaw/finger distance is `<= 0.10 m` at the jump and it is in a moving phase. |

Momentum bookkeeping is the discriminator between (a)/(e) and (d): an arm's
contact is one-sided (`Σ m Δv != 0`), a fruit-fruit collision is not.

## 5. Pre-run prediction (falsifiable, recorded before any run)

* **P1**: the departure is **tick-scale** (`|Δ|v|| >= 0.05 m/s` inside <= 2
  ticks), not a ramp — because a 2.4x overspeed decays to belt speed within
  0.02-0.03 s under fruit-belt friction, so a disturbance seen 0.4 s before the
  descent must be *recent*.
* **P2**: the jump carries a **cross-belt (x) or vertical (z)** component or a
  spin jump — the belt's own drive is `-y` only.
* **P3**: it happens while the fruit is within **0.20 m of a station's `y`**
  (`left 0.000 / right -0.100`), because that is where the two hands are.
* **P4**: the *active* arm is holding its hover (stationary, `|v_tcp| ~ 0`) at the
  jump — it is not yet descending — so (e) requires a moving pre-pose, not the
  descent.

A jump that satisfies P1/P2 but has no neighbour and no hand within 0.15 m would
be un-attributable on this instrument, and that outcome would be reported as
such rather than assigned to the leading candidate.

## 6. What this phase will not do

No `src/` lever is built from the attribution: a transit/pre-pose clearance or a
station/supply change is a scene/timing change and needs its own
pre-registration, both motion references, a scripted re-baseline and every
store's re-baseline. The only in-phase change is the instrument itself, which is
default-off. If the attribution lands on (b) the phase stops: P38/P50 measured
the release offset as a **static per-instance shift** and the mechanism is
closed (`logs/p50/`).
