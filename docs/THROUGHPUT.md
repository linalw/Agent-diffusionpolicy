# The cell's throughput: what it is, what the levers are, and how to read a rate

One page. It condenses P80-P84 (`logs/p80/`..`logs/p84/`, AGENTS §2's paragraphs)
into the measured throughput of the shipped tree, the two levers priced against it,
the one that shipped, the two that did not, and the read rules that bind the next
number anybody quotes. Every figure traces to a log in `logs/`.

## The number today

**Since P85 the two-line is the shipped scripted cell** (`FRUIT_BIARM` and
`FRUIT_BIARM_TWOLINE` both default `1`, the owner's sign-off on the grade-pure
routing semantics; `logs/p85/RESULTS.md`). The table below is that cell as it
ships - the "single arm" column is the pre-P85 shipped cell, restored with
`FRUIT_BIARM=0`. Nothing in the two-line row moved by the flip: the pre-flip
*explicit* two-line records are replayed **865/865** (seed 5) and **814/814**
(seed 6) `[fruit]` physics lines, so the flip changed reachability, not physics.

Shipped scripted cell, 20 slots, seed 5 (`logs/p85/` = P80's scenario with P82's
wall):

| | placed | sim s/attempt | inter-placement interval | placed/min (window / batch) | wall/pick |
| --- | --- | --- | --- | --- | --- |
| **two-line (shipped)** | 16/20 = 80 % | **9.70** | **10.77 s** mean / 18.00 p90 | **5.57 / 4.96** | **16.6 s** |
| single arm (`FRUIT_BIARM=0`) | 12/19 = 63 % | **15.10** | **26.72 s** mean / 36.90 p90 | **2.25 / 2.08** | 25.2 s |

The shipped **acceptance** is the two-line scenario at ten attempts: **7/10,
9.2 s/attempt**, fingerprint `configs/motion_reference.json` = `eb697f23` (the
same bytes as `configs/motion_reference_twoline.json` - see "What is left").
The single arm's own acceptance record is archived and shipped as
`configs/motion_reference_single.json` (6/9).

Two facts fix the interpretation:

* **The interval is `attempts-per-placement x attempt span + idle`.** On the single
  arm that is `1.45 x 15.1 s + 4.8 s = 26.7 s`, so **a failure costs a whole
  attempt** and the failure rate is a throughput term, not just a quality term.
* **The interval is bimodal**: 17.5-19.6 s between two placements, 35.6-38.2 s
  across a failure. The seven failures at seed 5 are **all `cnp`** (left 1/7 vs
  right 11/12) - the closed grip class of `logs/p42/SIM_LIMIT.md`.

## Lever 1: the two-line overlaps attempts (measured, and it is the biggest one)

The two-line does **not** shorten an attempt: its **per-arm** span is 15.0-15.6 s,
the single arm's 15.09. It **overlaps** two of them, so `2.38x = 1.88x clock x 1.27x
count`. At a second seed the **clock replicates (1.87x) and the count reverses**
(10 vs 13 placed), so the pooled figure is **1.86x on simulated time with the count
equal (26/40 vs 25/38)**.

The scheduler-only control (`logs/p81/RESULTS.md`: the same scheduler on the single
arm's shipped supply) separates the halves:

* **the clock is the scheduler's own** - **1.80x / 1.82x**, i.e. 96-97 % of the
  package-on clock, with 1.30-1.42 arms busy against the single arm's 0.83;
* **the feed is the package's** - without it the right station reports **no
  eligible fruit on 93.3 % / 82.0 %** of its polls (65.5 / 63.0 with it), starvation
  is 2.86x / 2.03x, right idle reaches 43 % and the interval 19.47 s against 10.77.

So: **needing the package is a scheduling answer, not a delivery one.** The
two-line's default is therefore a *semantics* decision (the W3 pure routing sends
grade A to the left, B to the right and recycles C) - **the owner took it in P85**
(`logs/p85/`): the shipped cell is the two-line with its package, `FRUIT_BIARM=0`
restores the single arm and `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0` the
shared-station pipeline.

## Lever 2: the wall - the arbiter was sleeping (shipped, P82)

The two-line's simulated clock was **1.02x of wall** before P82, because it paid
**wall/sim 2.57 against the single arm's 1.38**. Two profile builds whose `[fruit]`
streams are byte-identical to the record decomposed that 1.86x
(`logs/p82/RESULTS.md` §2):

| term | share of the two-line's wall | removable? |
| --- | --- | --- |
| the PhysX step (one shared `simulate` per tick, 10.87 ms) | **51.0 %** | no |
| the two arms' control (1.70 ms per segment, 1.97 per tick) | 15.7 % | no - that is two arms |
| the arbiter's own Python (`schedule`, 0.024 ms per round) | 0.2 % | - |
| the render (`_tick_frame`, 21,544 calls) | **0.0 %** | - |
| **`MainBridge.pump`'s fixed 5 ms timeout** (99.2 % timeouts, ~2.03 rounds per tick) | **32.2 %** | **yes** |

The mechanism: after granting a permit the main thread slept out the rest of the
5 ms poll while the arm's 1.70 ms segment ran, because the tick requests
`TickRelay.request` files **never reach the queue `pump` waits on**. Waking on the
request instead (the timeout stays as the safety net) gives:

* **wall/pick 25.1 -> 16.4 s (-34.6 %) at seed 5 and 23.8 -> 15.6 s (-34.4 %) at
  seed 6**, wall/sim **2.59 -> 1.69**, rounds 47,795 -> 48,021 (**no spin**);
* **the run is byte-identical**: 865/865 and 814/814 `[fruit]` lines against the
  record, 710/710 on the single arm, 346/346 on the acceptance, 499/499 on the
  shared-station consumer;
* **wall placed/min 1.02x -> 1.55x pooled** - the two-line now clears the standing
  1.25x bar on the **wall** denominator, not only on the simulated one.

It ships as the bimanual arbiter's default (`FRUIT_BIARM_WAKE_ON_REQUEST=0`
restores the timeout); a post-flip 4-attempt pair reads 85.9 s against 119.0 s of
`[fruit]` span with byte-identical streams. **This is a latency fix, not a physics
change** - no motion reference and no store moves because of it.

## The two negatives (do not re-spend them)

**Fail fast on a lost payload** (P83 single arm, P84 two-line) looked like the
cheapest 10 %: the cell runs a ~400-tick place leg after the payload is already
gone. The abort works - P83 halves the failed attempt by **-5.144 s = -617 ticks at
both seeds**, with 15/15 trips at `force = 0.00 N` *and* `contacts = 0` and 34/34
placed-attempt legs unshortened - and **throughput does not follow**: the interval
worsens by +32 % at seed 5 because the abort **re-times the presentation**
(`attempts/placement` 1.583 -> 2.333) and six slots then starve on a pool whose only
body above the 0.399 m catch floor was `diverted`. On the two-line the sign flips
between seeds (+33.6 % / -36.9 %) and the saving is only **1.2-1.5 s on a
never-grasped attempt and ~3.3 s on a `cnp`**, because the shipped two-line already
truncates a lost attempt twice (the `not result.grasped` return after the lift and
the P10-C monitor, armed by default in a two-line session). **A lever that shortens
a failure must not raise `attempts/placement`; this one does.**

**A speed profile** (P44's union, `FRUIT_SPEED_ALL=1`, re-priced in P80) is a
**cycle-time** lever, not a throughput lever: -1.70 s/attempt on the single arm and
-1.00 s on the two-line, -12 % wall/pick, but the interval **+4.9 %** and the
placement window **-4.9 %**, its count cost being P51's closed acquisition class.

## The read rules (they bind the next rate claim)

1. **Quote both denominators and the wall column.** The placement window and the
   batch span are different numbers (2.25 vs 2.08 above), and the wall is measured
   from per-line stamps (`logs/p80/stamp.py`), never inferred.
2. **Quote `placed/min wall`, never `wall/pick` alone.** A run that places less
   divides a smaller wall by a smaller count: P83 read 25.33 -> 21.62 s/pick while
   the rate **fell 1.50 -> 1.19**.
3. **>= 2 seeds, and a seed is a scenario.** The two-line's count advantage
   reversed at seed 6; its 20-attempt reference is per-seed (P80's file is seed 5,
   P84 wrote seed 6's into `logs/`, never `configs/`).
4. **A count is a branch draw; the branch-free numbers are per-leg and
   per-attempt** (a leg's `ticks = X/X`, a failed attempt's own span, the number of
   pried legs). Quote the mechanism, then the interval, then the count.
5. **The interval's three terms** are `attempts/placement`, the attempt span and the
   idle. A lever that moves one of them can lose on the other two - both negatives
   above are exactly that.

## What is left

* **The two-line is the default (P85, done).** The clock (1.87x) and the wall
  (1.55x) are both measured and both ship now; the collector and every store are
  re-baselined (`collection.biarm_resolved` / `..._defaulted` tell a post-flip
  shard from a pre-flip one). **Re-baseline rule: every rate, acceptance and
  store recorded before P85 is a single-arm (or explicitly opt-in two-line)
  number.**
* **The first acceleration read on the new default (P85-ACC, `logs/p85/ACCEL.md`).**
  The P44 speed union's *time* transfers exactly - `place` -0.84 s, `release`
  -0.72 s, `lift` -0.13 s, **-1.00 s/attempt at both seeds** - and its *delivered*
  side has no stable sign: 16 -> 13 placed at seed 5, 10 -> 14 at seed 6, pooled
  26 -> 27 of 40. Not adopted; the class that absorbs it is the closed grip class
  below.
* **The residual 1.19x of wall** - two arms' control plus the permit handoff, with
  the shared physics step at **75 % of what remains**. No arbiter change can move
  it; it is the cost of two arms in one PhysX scene.
* **The interval's binding term is the failure rate**, and the failures are the
  closed grip class (`logs/p42/SIM_LIMIT.md`, `docs/LEFT_ARM.md`) - so the next
  throughput step is a success-rate step, not a scheduling one.
