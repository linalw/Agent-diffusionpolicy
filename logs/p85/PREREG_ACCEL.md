# P85 acceleration pre-registration - the P44 speed union on the shipped cell

Pinned **before any simulator run of this cell**. Pin: `logs/p85/PREREG_ACCEL.md5`.
Parent: `logs/p85/PREREG.md` (the flip). The flip is green before this runs.

## 0. Which acceleration item, and why this one

The flip's own numbers name two candidates, and they are not comparable in kind:

* **the idle/park family** - P80's two-line idle is 18-21 % of the wall and P84
  measured a 7.1-21.8 s park-gate wait plus a 4.19-5.04 s lock-on. In wall terms
  this is the **larger** term, but every lever that touches it has already been
  measured: the W7-A park gate is **already the default** (its remaining wait is
  the other arm's carry - the overlap itself), and W2's start-gap / station
  widening, W3's capture token, W6-C's prefetch (0/40 reservations) and R3's
  L2/L3 lead/residency screens are all negative or bit-identical. There is no
  unspent lever, only a bigger number.
* **the P44 speed union** (`FRUIT_SPEED_ALL=1`: `place` 0.52, the release clock
  floor, `lift` 0.36) - the only knob on the tree that removes **profile** time
  the primitive actually spends, and the only one whose two-line read
  (P80: -1.00 s/attempt, interval +3.9 %, class-identical at seed 5) was taken
  on the **opt-in** arm. P46 then re-ran it at a fresh seed and fired its own
  F2 (count 9 -> 7 at seed 6), and P51 closed the acquisition family: the cost
  is the closed grip class, not a supply-x object.

So: **the measurement is the speed union re-priced on the now-default cell.**
The park/idle term is reported as the larger-but-leverless context, not spent.

## 1. Cell (existing knobs only, no `src/` change, no second default change)

* The shipped default (`FRUIT_BIARM`/`FRUIT_BIARM_TWOLINE` unset = the
  two-line), 20 attempts, `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`,
  `SEED=5` and `SEED=6`, one claim per run.
* **C (control)** = the flip's own default runs at both seeds (P85's A3). They
  are admissible as controls only if they replay P80's `T20`/`T6` modulo the new
  scheduler banner; if A3 fails they are still the control (same tree, same
  batch) and the cross-tree comparison is dropped.
* **U (treatment)** = `FRUIT_SPEED_ALL=1` at both seeds.
* P80's `U20` (the union on the *single* arm) and `V20` (the union on the opt-in
  two-line) are the cross-references; neither is re-run.

## 2. Endpoints (fixed before the runs)

* **E1 - mechanism (primary).** The per-attempt simulated span falls at **both**
  seeds: `s/attempt(C) - s/attempt(U) >= 0.80 s`. Rationale: P44's per-leg
  arithmetic is -1.45 s on the single arm and -1.10 s on the two-line, P80
  measured -1.00 s at seed 5; a two-line attempt is scheduled in parallel, so
  the per-attempt span is the *right* denominator for the mechanism (the
  interval is not - see E2). The `[cycle]` block must show the three legs moving
  in the registered direction (`place` -0.5..-0.9 s, `release` -0.7..-1.0 s,
  `lift` -0.2..-0.3 s).
* **E2 - the delivered side (the read).** At **each** seed: `placed(U) >=
  placed(C) - 1` **and** the pooled placement-window rate (`60 / interval mean`)
  not worse than -5 % of the control. P46's seed-6 reversal is the reason this
  is a per-seed gate rather than a pooled one.
* **E3 - class.** After mapping the known notes to their classes (the P44/P46
  `fruit did not follow the gripper` acquisition row is the named cost), **no
  new failure reason** and the held-leg slip guard not worse: the `[carry]`
  `clean_slip_max > 50 mm` count and the `force_min == 0` count.
* **E4 - wall (report only, never gated).** `placed/min wall` and `wall/pick`
  from the stamps (P83's rule: quote `placed/min wall`, not `wall/pick` alone).

## 3. Decision rule

E1 and E2 and E3 on **both** seeds -> "the union transfers to the shipped cell;
recommend it as the next adoption candidate (its own phase, both references and
every store)". Any failure -> **measured, not adopted**, and the failing endpoint
is what the next attempt on this cell must beat. **No default changes in this
phase either way.**

## 4. Falsifiers

* F1: the union's `s/attempt` gain is < 0.80 s at either seed (E1 fails).
* F2: a seed loses >= 2 placements or the window rate falls > 5 % (E2 fails).
* F3: a new failure reason, or the held-leg slip guard worsens (E3).
* F4: the control is not on the flip's tree (then no cross-tree claim).

## 5. Read rules

* Counts are branch draws; the interval is split over two overlapping arms, so
  quote the pooled **and** per-arm interval, both denominators and the wall.
* The `place` leg is where the union's time is; the `release` block is the
  clock floor (P44 amend: 130 ticks, -0.96 s) - if either is flat the resolver
  was not armed and the run is a manipulation failure, not a null.
