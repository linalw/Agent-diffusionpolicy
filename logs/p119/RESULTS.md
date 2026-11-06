# P119 - the belt speed on the shipped two-line: 0.15 is a negative, so the dynamic scene lane closes

Owner's constraint (2026-11-06): the scene may change, but the **dynamic scattered
fruit pipeline must be preserved** - no diverter, no stop gate, no guide/limit, no
pause. That voids P117's pocket station (a stopped fruit) and leaves the belt
speed as the only scene lever with a measured, dynamic-compatible prior: P117's
own record cites R3 §4's **0.12 -> 0.15 = 3.63 -> 4.69 window placed/min (+29 %)**
and 0.18's starvation. But R3 ran the **single-arm patch battery on the pre-P85
tree**, and the shipped cell is the **two-line**, whose interval is the two arms'
sequencing (P80/P99) - so the prior does not transfer by assertion. This phase
re-tests it on the shipped cell at one seed.

**No `src/` change, no default change, no reference.** One 20-attempt cell,
`FRUIT_BELT_SPEED=0.15`, seed 5, the shipped scripted two-line, the P80/P84
instrumentation; the control is the same-seed record `logs/p92/C5.log` (16/20,
10.59 s interval, 5.66 / 5.05 placed/min).

| | **0.12 (C5, control)** | **0.15 (this cell)** |
| --- | --- | --- |
| placed | **16/20 = 80 %** | **9/20 = 45 %** |
| grip losses (`did not follow`) | **8** | **20** |
| `no eligible` polls | 45 | 47 |
| pooled interval (mean / p50 / p90) | **10.59 / 13.30 / 17.40 s** | **16.85 / 13.55 / 33.50 s** |
| left / right interval mean | 19.30 / 26.02 s | 33.70 / 37.67 s |
| `s/attempt` | 9.5 | 9.0 |
| sim span | 44.6 -> 203.5 s | 46.1 -> 180.9 s |
| encoder | -0.120 m/s | **-0.150 m/s (command -0.150)** |

**The mechanism is the grip class, not the schedule**: the `no eligible` count is
flat (45 -> 47), while the grip losses **double** (8 -> 20) and the interval mean
rises +59 %. At 0.15 the catch hands the pads a faster fruit (the same 83 mm lead
is now 0.69 s of travel instead of 0.83 s?) - the lead is a *time*, so the belt
travel per lead grows 25 %, and the pads close on a fruit that is further through
the catch-up.  The single-arm +29 % therefore **does not transfer**: the two-line
already overlaps the attempt, so the descent wait it shortens is the slack the
other arm uses (P99's sentence, one level down), while the faster catch costs the
grip.

**Verdict: NOT ADOPTED** - 0.15 is worse on the shipped cell (rate and interval),
so the belt speed is not a free speed lever and the **dynamic-only scene lane is
closed** by measurement:

| scene candidate | verdict |
| --- | --- |
| pad face (concave/V) | **closed** (P117: 1.56-2.89x worse creep on the pear) |
| pad friction | **closed** (P117: capacity 1.45-1.84x, creep -5 %) |
| station pocket / gate / diverter | **forbidden** (owner: dynamic pipeline) |
| belt speed 0.15 | **negative** (this phase: 9/20 vs 16/20) |
| pick-station / output-station geometry | **measured** (P66's 150-cell sweep, P90's 588-cell map: 0 pass) |
| supply band / scatter | **measured** (P92/P93: seed-dependent) |

What remains for the **success** rate is therefore *not* a scene change: P50's
release-offset compensation (the delivered-x tail, the 25 % acquisition class,
opt-in per-pool tables) and the hardware sanctions (`docs/END_EFFECTOR_DECISION.md`
- a new pad asset or a real-jaw force anchor), or a different hand.

## Files

`logs/p119/belt015_s5.log` (the cell), this file. No `configs/` or `src/` change;
references `30fb99f8` / `30fb99f8` / `8952c320` untouched.
