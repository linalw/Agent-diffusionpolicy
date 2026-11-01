# The cell's throughput: what it is, what the levers are, and how to read a rate

One page. It condenses P80-P89 (`logs/p80/`..`logs/p89/`, AGENTS §2's
paragraphs) into the measured throughput of the shipped tree, the levers priced
against it, the three that shipped and the ones that did not (with the read rules
that keep a measured negative from being spent twice). Every figure traces to a
log in `logs/`.

## The number today

**Since P87 the shipped two-line cell runs the release trim** (`FRUIT_SPEED_RELEASE`
resolves **on for a two-line session**, off everywhere else - the P86 cell, shipped
scoped; `logs/p87/RESULTS.md`), so the cell is **-76 ticks = -0.633 s of pure dwell
per placed attempt** faster than every figure P80-P86 printed on the same scenario.
**Since P85 the two-line is the shipped scripted cell** (`FRUIT_BIARM` and
`FRUIT_BIARM_TWOLINE` both default `1`, the owner's sign-off on the grade-pure
routing semantics; `logs/p85/RESULTS.md`). The table below is that cell as it
ships - the "single arm" column is the pre-P85 shipped cell, restored with
`FRUIT_BIARM=0`. Nothing in the two-line row moved by the P85 flip: the pre-flip
*explicit* two-line records are replayed **865/865** (seed 5) and **814/814**
(seed 6) `[fruit]` physics lines, so the flip changed reachability, not physics;
the P87 cells are likewise replayed **865/865** and **814/814** against P86's own
four, so the scoped trim *is* the arm P86 measured.

**P88 measured the next lever - the `place` block - and shipped nothing**
(`logs/p88/RESULTS.md`, "Lever 4"), so **every number in this page is unchanged
by it**: the place cell's mechanism is exact but the delivered interval rose at
both seeds, and `FRUIT_SPEED_PLACE` stays off by default.

**P89 measured the last of the three profile blocks - the `lift` - and shipped
nothing either** (`logs/p89/RESULTS.md`, "Lever 5"): the block falls as the
profile prices it (-0.175/-0.173 s against the predicted -0.177/-0.193, per leg
exact), the **delivered interval rises at both seeds** (10.59 -> 13.43 and
11.08 -> 12.38 s) and the class does not improve, so `FRUIT_SPEED_LIFT` stays off
and **no number in this page moves**. With that, **all three profile blocks are
measured**.

Shipped scripted cell, 20 slots, seed 5 (`logs/p85/` = P80's scenario with P82's
wall; the P87 row is `logs/p87/T5.log`, the same scenario with the trim):

| | placed | sim s/attempt | inter-placement interval | placed/min (window / batch) | wall/pick |
| --- | --- | --- | --- | --- | --- |
| **two-line (shipped, pre-P87 clock)** | 16/20 = 80 % | 9.70 | **10.77 s** mean / 18.00 p90 | **5.57 / 4.96** | 16.6 s |
| **two-line (shipped, P87 trim)** | 16/20 = 80 % | **9.50** | **10.59 s** mean / 17.80 p90 | **5.66 / 5.05** | **16.3 s** |
| single arm (`FRUIT_BIARM=0`) | 12/19 = 63 % | **15.10** | **26.72 s** mean / 36.90 p90 | **2.25 / 2.08** | 25.2 s |

The shipped **acceptance** is the two-line scenario at ten attempts: **7/10,
9.4 s/attempt**, fingerprint `configs/motion_reference.json` = `423896f7` (the
same bytes as `configs/motion_reference_twoline.json` - see "What is left"); it
was `7/10, 9.2 s` and `eb697f23` before P87. The single arm's own acceptance
record is archived and shipped as `configs/motion_reference_single.json` (6/9),
**untouched by the flip** - and proven byte-identical end to end (346/346).

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

## The three negatives (do not re-spend them)

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

**A per-seed attempt-span gate** (P86's P1b) is not a lever but a *test design*
that fails: a profile cell's saving is exact in the `[cycle]` block and **not**
in the attempt span, because the span carries the acquisition legs and they
re-draw whenever the attempt boundary moves (residual +0.17 / -0.12 s - it
sign-flips across two seeds). Read rule 6 keeps this closed.

## Lever 3: the release block - pure dwell, shipped in P87

P44's S2 cell (`FRUIT_SPEED_RELEASE`) is the **separable** third of the speed
union: the place leg's three open-loop holds, `dwell` **20 -> 0** and the pad /
finger settles **3 -> 2** = **-76 ticks = -0.633 s** at 120 Hz, with no
trajectory endpoint moved. P86 measured it on the shipped two-line and P87
shipped it **scoped to the two-line session**:

* the `[cycle] release=` **median** falls **-0.645 / -0.640 s (77 / 77 ticks)**
  at seeds 5 / 6, and in **all four arm-seed cells** (-0.640/-0.640,
  -0.635/-0.615) - exact against the arithmetic;
* the pooled interval falls at **both** seeds (10.77 -> 10.59 and 19.34 ->
  11.08 s) and on **both arms at both seeds**; the seed-5 pair is the clean read
  (identical 16/20 and an identical 9/10 + 7/10 arm split), seed 6's -8.26 s
  carries a +2 count draw;
* **28/28** payload-present releases land on the output belt in the control's own
  height/impact/bounce band (32.1-64.3 mm, -0.93..-0.61 m/s, bounce <= 4.9 mm),
  the failure ledger gains **no class**, and the `force_min == 0` loaded-slide
  guard is flat at seed 5 (4 -> 4) and better at seed 6 (11 -> 7);
* the **scope is what shipped**: the trim is read at a site every presentation
  shares, so it is defaulted **on for a two-line session and off everywhere else**
  (`FRUIT_SPEED_RELEASE=0` restores; `=1` still wins globally). The single-arm
  acceptance is **346/346 raw identical** to its pre-flip record and the shared
  station's clock is unchanged (20/3/3, 188 ticks), which is the inertness proof;
* **one descent leg on one seed is 2.5 % over its budget** (leg 12, 5.9 cm,
  0.164 against 0.160) - the same leg P86 recorded, so the 40-attempt sample says
  it is a **branch property of that seed, not a draw**: the flip shipped as a
  **considered trade**, and the descent profile was **not** re-tuned to admit it.

## Lever 4: the place block - measured, NOT shipped (P88)

P44's S1 cell (`FRUIT_SPEED_PLACE=0.52`, `v_max` 0.35 -> 0.52 at the shipped
`a_max` 1.089) is the third and last separable block, and after P87's trim it is
the **largest remaining** one (3.14-3.19 s against `release` 1.70 and `lift`
1.65). P88 built the same **two-line-scoped** form as the release cell, measured
it at seeds 5/6 (controls explicit `=0`, treatments unset), and **did not ship
it** - the gate fails:

* **the mechanism is exact.** The block is **`transit(0.52, d) + 0.583 s`**: the
  `place low` remainder is 0.583 s (range 0.578-0.588) in all four cells, the
  per-leg tick count matches the profile re-generated at 0.52 from the leg's own
  printed distance to **median 0.0 / +0.5 ticks (max |2|)**, `|v|cmd` matches the
  profile's own peak to **<= 0.009 m/s**, and the median leg cruises at **0.508
  m/s** (control 0.341-0.343). The block's **mean** falls **-0.774 / -0.767 s**
  against the predicted -0.776 / -0.801; the **median** reads -0.770 / -0.915
  against -0.904 / -0.892, i.e. **seed 5 misses the registered +-0.12 s band by
  0.014 s**, and the miss is the **leg mix** (the treatment drew a longer median
  leg; predicted from **its own** legs the median is off by -0.008 / +0.014 s).
* **the delivered side does not follow.** The pooled interval **rises at both
  seeds** (10.59 -> 13.23 and 11.08 -> 12.11 s). At seed 5 the count falls
  **16 -> 11** (the left's never-held legs **1 -> 4**, `force@onset = 0.00 N`,
  `sep@onset` 59-63 mm - the **pre-contact acquisition** class, not the place
  transfer); at seed 6 the count rises **12 -> 15** but the placements spread
  over a **wider** window (121.9 -> 169.5 s), which is the interval rising with
  **more** placements. **Pooled 28 -> 26 of 40, `placed/min wall` 2.65 -> 2.61
  (-1.6 %)** while the wall itself falls 5.6 %.
* **the class guard is negative** (the cell does not create the loaded slide):
  place-leg escapes **0/27** in the treatment against **1/29** in the control,
  all-leg escapes **5 vs 8**, `force_min == 0` **6 vs 8**, landing **16/16,
  11/11, 12/12, 15/15**, and both treatments' descent budgets clean (the
  control's seed-6 leg 12 at 0.164 vs 0.160 is the standing branch leg).
* **not shipped**: `PLACE_TWO_LINE_DEFAULT = False`, so `FRUIT_SPEED_PLACE`
  stays off on every path; the measured arm is `FRUIT_SPEED_PLACE=0.52`, the
  `[biarm] place profile:` row and `physics.place` say which cap ran, and the
  shipped tree is inert (C5/C6 replay P87's T5/T6 **868/868** and **821/821**,
  a fresh unset run replays C5 **868/868**, the single arm is **346/346 raw**
  identical, both references untouched).

## Lever 5: the lift block - measured, NOT shipped (P89)

P44's **S3-v** (`logs/p44/P2_RESULTS.md` §9: `grasp_lift` `v_max` 0.30 -> **0.37**
with the shipped **`a_max` 1.0** - the acceleration raise bought 0.00 s and spent
transient, so it is deliberately *not* part of the cell) is the **last** of the
three blocks, and it is also a **class site**: the lift leg's window is where the
payload is seated, and P75 measured that 2 of 6 place-leg escapes fire at the
lift's *end*. P89 built the same **two-line-scoped** form as the release and the
place cells, measured it at seeds 5/6 (controls explicit `=0`, treatments unset),
and **did not ship it**:

* **the mechanism is exact.** `[cycle] lift=` is the `grasp_lift` leg plus a
  constant remainder (**0.412-0.422 s** in both arms), so the block **mean** falls
  **-0.175 / -0.173 s** against the predicted **-0.177 / -0.193** (each control
  attempt's own printed distance re-generated at 0.37/1.0); the per-leg tick count
  matches that profile to **median 0.0 (max |5|)** and the leg's `|v|cmd` to
  **0.013 m/s** of its own peak (median 0.350 against the control's 0.293). At
  the 0.21 m reference the clock is **162 -> 136 ticks = -0.217 s**. **The two
  regimes switch at d = 0.225 m** (0.148 shipped), which is why a short leg saves
  nothing: the raised cap is an **acceleration**-bound clock, not a speed-bound
  one, and the cell is smaller than the block it prices.
* **the delivered side does not follow, for two different reasons.** The pooled
  interval **rises at both seeds** (10.59 -> 13.43 and 11.08 -> 12.38 s). At
  seed 5 the **count** is the story (16 -> 12 placed, `attempts/placement` 1.25 ->
  1.67, the left arm 9/10 -> 5/10, and the left's lift legs are where its three
  new escapes are); at seed 6 the count **rises** (12 -> 14) and the interval
  rises anyway because the placements spread over a **wider** window (121.9 ->
  160.9 s) - P88's seed-6 pattern, read rule 7. Pooled **28 -> 26 of 40**,
  `placed/min wall` **2.67 -> 2.60** on 629 -> 601 s.
* **the class neither improves nor moves to a new site.** P44's single-arm
  finding (S3-v dropped the `force_min == 0` legs 5 vs 7, no new failure row) does
  **not** transfer: the two-line's lift-leg escapes read **7 -> 10 of 40** and its
  `force_min == 0` legs **8 -> 10** (seed 5 worse 2 -> 6, seed 6 better 5 -> 4 -
  a draw at n = 20 per arm). The escapes' onset rows are **early** in their legs
  (median share of the leg 0.05) - the **take-off** loaded slide, not P75's
  "place leg starts with one face at 0.00 N because the payload left at the lift's
  end": the treatment's **place-leg escapes are 0/27** against the control's 1/29.
  One new reason key (`grasped, not placed (no note)` x1) and the class clauses'
  letter fail at seed 5.
* **not shipped**: `LIFT_TWO_LINE_DEFAULT = False`, so `FRUIT_SPEED_LIFT` stays
  off on every path; the measured arm is `FRUIT_SPEED_LIFT=0.37` (0.37 / 1.0), the
  `[biarm] lift profile:` row and `physics.lift` say which cap ran, and the
  shipped tree is inert (C5/C6 replay P88's own **C5/C6** 868/868 and 821/821, a
  fresh unset run replays C5, the single arm is **346/346 raw** identical, both
  references untouched at `423896f7`).

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
6. **A per-seed attempt span is not branch-free** - it contains the acquisition
   legs, which re-draw whenever the attempt boundary moves. For a profile cell the
   mechanism is the moved `[cycle]` block (read by **median**), the delivered
   number is the interval, and the span is a report (P86, `logs/p86/RESULTS.md`
   §3 - there the span moved -0.48 s where the block moved -0.64 s, with a
   sign-flipping +0.17/-0.12 s acquisition residual).
7. **The interval *is* the placement window, inverted** - `mean_gap =
   (t_last - t_first)/(n-1)`, so it and the window rate are **one statistic**.
   A cell that lengthens the window can read a worse interval with **more**
   placements (P88's seed 6: 12 -> 15 placed, window 121.9 -> 169.5 s, interval
   11.08 -> 12.11 s). Quote the count and the batch denominator beside it.
8. **A block whose clock is a function of distance needs the mean (or the
   per-leg read), not the median.** The release's holds are a fixed clock, so a
   median is exact; the place leg's ticks are `f(distance)`, so a median across
   two arms is **mix-sensitive** - P88's seed-5 median missed its band by 0.014 s
   while the mean matched to 0.002 s and every leg matched the profile within 2
   ticks (`logs/p88/RESULTS.md` §1). The **lift** is not a transit but its clock
   is still `f(distance)` and it has *two* regimes (speed-bound above
   `5.774 v^2/(1.875^2 a)` = 0.225 m at 0.37, 0.148 m at 0.30), so P89 gated the
   **mean** (-0.175 against the predicted -0.177) and the **per-leg** read
   (`logs/p89/RESULTS.md` §1). Same lesson as 6, one level down.
9. **A scoped default owes a replay and an inertness pair, not an argument.**
   P87's proof shape: the same-seed cells must be **byte-identical to the
   pre-flip record** on the `[fruit]` stream (`logs/p87/p87_report.py --same`,
   the phase's own new row dropped) - that is what makes "the shipped default is
   the measured arm" a fact rather than a reading - and every path the scope must
   not touch owes its own byte identity: the single arm **raw 346/346** against
   its pre-flip acceptance, the shared station a pair whose **clock** must match
   (`--profile`: the row's `origin` field is *supposed* to differ, that is the
   label's job). A default that moves a path with no such record has not been
   scoped, only declared.
10. **The release clock is provenance now.** A store recorded under the trim
   differs from a pre-P87 one in its **attempt timing** without moving a
   trajectory endpoint, so both manifest writers carry
   `physics.release={dwell,pad_hold,finger_hold,...}`; a manifest **without** the
   key predates P87, and park/no-park-style mixing of the two is not allowed.
   The place cap has its own `physics.place={v_max,a_max,ticks,...}` (P88) and the
   lift its own `physics.lift={v_max,a_max,ticks,...}` (P89); their `ticks` are
   priced at a named **reference distance**, because both are `f(distance)` and a
   stored tick count without its distance means nothing.

## What is left

* **The two-line is the default (P85, done).** The clock (1.87x) and the wall
  (1.55x) are both measured and both ship now; the collector and every store are
  re-baselined (`collection.biarm_resolved` / `..._defaulted` tell a post-flip
  shard from a pre-flip one). **Re-baseline rule: every rate, acceptance and
  store recorded before P85 is a single-arm (or explicitly opt-in two-line)
  number.**
* **The release trim on it (P87, done).** Shipped **two-line-scoped**; see "Lever
  3". **Re-baseline rule: every two-line rate, span or interval recorded before
  P87 is a 2.35 s-release number; `FRUIT_SPEED_RELEASE=0` restores it**, and a
  store without `physics.release` predates the flip. The one open number is the
  **descent excursion** (seed 6's leg 12, 0.164 vs 0.160) - priced as a branch
  cost, and a third seed is the spend that would price it further.
* **The first acceleration read on the new default (P85-ACC, `logs/p85/ACCEL.md`).**
  The P44 speed union's *time* transfers exactly - `place` -0.84 s, `release`
  -0.72 s, `lift` -0.13 s, **-1.00 s/attempt at both seeds** - and its *delivered*
  side has no stable sign: 16 -> 13 placed at seed 5, 10 -> 14 at seed 6, pooled
  26 -> 27 of 40. Not adopted; the class that absorbs it is the closed grip class
  below. **Its `release` third is now the shipped clock (P87)**, and its **`place`
  and `lift` thirds have since been measured on their own and both are negative**
  (P88, P89) - so the union's measured -1.00 s is **fully spent or priced**, and
  P51 is why the two remaining cells cannot be made class-clean. The union stays
  `FRUIT_SPEED_ALL=1`: opt-in and global.
* **The release block, priced on its own (P86, `logs/p86/`).** `FRUIT_SPEED_RELEASE=1`
  (dwell 20 -> 0, pad ramp 3 -> 2, finger ramp 3 -> 2 = **-76 ticks = -0.633 s**)
  moves the `[cycle]` release block by **-0.615..-0.640 s = 74-77 ticks in all
  four arm-seed cells** (2.33 s of a 15.78 s per-arm span), lands **28/28**
  payload-present releases on the output belt, and lowers the interval on both
  arms at both seeds (10.77 -> 10.59 at seed 5 with an identical 16/20 and an
  identical arm split; 19.34 -> 11.08 at seed 6, confounded with a +2 count
  draw). P86 recorded it as a measured positive and **not adopted** - its own
  attempt-span clause missed its band (read rule 6) and one R6 descent leg read
  2.5 % over its budget with the descent profile untouched. **P87 shipped it
  two-line-scoped** (Lever 3): the span clause was a test-design defect, not a
  property of the cell, and the descent leg reproduced as the branch's cost.
* **The place block (P88, measured, NOT shipped).** The third and last profile
  block: the mechanism is exact (`transit(0.52, d) + 0.583 s`; per-leg ticks
  within 2; mean **-0.774/-0.767 s** against the predicted -0.776/-0.801) but
  the **delivered** interval rose at both seeds (10.59 -> 13.23, 11.08 -> 12.11
  s) and the window density fell at both, so `FRUIT_SPEED_PLACE` stays off
  (`PLACE_TWO_LINE_DEFAULT = False`). **Re-baseline: none** - nothing shipped,
  both references untouched (`423896f7`), the acceptance still 7/10 at 9.4
  s/attempt with `fingerprint: matches`. The measured arm is
  `FRUIT_SPEED_PLACE=0.52`; the **re-entry** is a scenario where the place block
  binds the interval rather than the count, or a class-first registration argued
  on the -0.77 s wall saving alone. See "Lever 4".
* **The lift block (P89, measured, NOT shipped) - the profile table is closed.**
  The last of the three: the mechanism is exact (`[cycle] lift=` = the leg +
  0.412-0.422 s; mean **-0.175/-0.173 s** against the predicted -0.177/-0.193;
  per leg median 0.0 ticks) but the delivered interval rose at both seeds
  (10.59 -> 13.43, 11.08 -> 12.38 s), the pooled count fell (28 -> 26 of 40) and
  the class did not improve (lift-leg escapes 7/40 -> 10/40), so
  `FRUIT_SPEED_LIFT` stays off (`LIFT_TWO_LINE_DEFAULT = False`). **Re-baseline:
  none** - nothing shipped, both references untouched. The measured arm is
  `FRUIT_SPEED_LIFT=0.37` (0.37 / 1.0). With release (shipped), place (negative)
  and lift (negative) all priced by the same instrument, **the next throughput
  step is not a profile block**: it is the success rate (the closed grip class)
  or the arbiter's remaining 1.19x of wall. See "Lever 5".
* **The residual 1.19x of wall** - two arms' control plus the permit handoff, with
  the shared physics step at **75 % of what remains**. No arbiter change can move
  it; it is the cost of two arms in one PhysX scene.
* **The interval's binding term is the failure rate**, and the failures are the
  closed grip class (`logs/p42/SIM_LIMIT.md`, `docs/LEFT_ARM.md`) - so the next
  throughput step is a success-rate step, not a scheduling one.
