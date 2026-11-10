# P136 pre-registration - the prediction-gated handover becomes the default

**Written after the flip's first acceptance (7/10) and first single-arm run (5/9),
and before the reference re-record, the final gate and the commit** - recorded as
such rather than presented as a blind pre-registration. The decision rule below
was applied to those runs, and both were re-run/re-gated on the final tree.

## 0. What flips, and why

P135 measured that under a **varying conveyor** the shipped handover gate - a
*speed* formula, `fruit - grip <= speed*(t_desc + 0.15)` - starts the descent at
the wrong time and the fruit arrives **298-407 mm** from the hand; the catch-up
then spends its 200-tick budget and the attempt is a `never_held`. The
prediction-gated handover (start when the estimate says the fruit will be at the
catch point when the leg ends) converted **every** such miss at both wave rungs
(12/13/11 and 16/15/17 ticks at 5.4-5.9 mm, timeouts 2 -> 0 and 1 -> 0).

The cost is that the gate moves the descent's start tick, so on the *nominal*
belt the cell is a measured **tie**, not an identity: `nom_w` read 11/13/11 ticks
at 5.5-5.9 mm against the control's 10/13/11 (0/3 placed against 0/3). A tie is
not an identity, so the acceptance's branch moves and the references are owed.

## 1. Scope

`FRUIT_TRACK` unset resolves **on for the scripted line** (`default`) and **off for
the two policy interfaces** (`scope-off`): `SortingRLEnv` and
`scripts/60_eval_policy.py` construct the task with `scripted=False`. Reason: the
tracker's measured results are all on the scripted catch, and the direct/policy
action loop and the trigger were never measured with it; flipping them would move
the interface of record and every policy store at once.

`FRUIT_TRACK=0` restores the pre-P136 path bit for bit. `FRUIT_DESCENT_TRACK` and
`FRUIT_TRACK_WAIT` unset follow `FRUIT_TRACK`; explicit values win.

## 2. Decision rule (stated before the acceptance)

The flip is adopted only if **all** hold:

1. the shipped acceptance (`scripts/accept.sh`, the two-line cell) is **at or
   above its 0.60 floor**, and every descent is inside its speed and lurch budget
   (`190` gates those, not the rate);
2. the **policy canary** still resolves the pre-P136 catch (`track=0(scope-off)`)
   and, on a smoke, does not lose its floor or gain a new failure reason;
3. a store written after the flip names the tracker in its manifest
   (`physics.tracking`), and one written before it does not;
4. both motion references are re-recorded **from same-batch runs of the flipped
   tree** (the two-line from the acceptance's own log, the single arm from
   `FRUIT_BIARM=0`), with the pre-flip files archived, and the acceptance then
   reads `fingerprint: matches` + `190: PASS`;
5. `scripts/selfcheck.sh` passes and `106`/`107` are clean.

The **count is not the argument** (a count is a branch here); the argument is §0's
mechanism. A count *fall* below the floor is a fail; a count *difference* is a
draw and is reported as such.

## 3. What is explicitly not claimed

* No rate improvement on the nominal belt - the measured result there is a tie.
* No change to the direct/policy or hybrid interfaces (they are scoped out).
* No store re-baseline in the sense of re-collecting: the existing stores keep
  their own manifests, and a post-flip store is identified by
  `physics.tracking.origin`.
