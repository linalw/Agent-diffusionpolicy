# P228 / Stage 0 pre-registration: the latency the world pays

**Pinned 2026-11-24, after `scripts/285_latency_bench.sh` was launched and before
any non-zero-`d` cell was read.** One earlier run exists and is declared: a
**1-episode build smoke** at `FRUIT_EVAL_LATENCY=4`, seed 901, **1/1 placed**
(`/tmp/lat4.log`), whose purpose was to confirm that the injector prints
`[lat]` rows and does not crash. No 6-episode cell of any `d` has been read.

## Why this phase exists

The shipped direct loop never steps the simulator while the model runs
(`sample_chunk` computes, `act` then executes), so its inference latency costs
**zero belt travel**. That is the exact metric inflation ReflexBench
(arXiv 2608.14379) and LIBERO-Dynamic (arXiv 2610.24579) criticise - a policy
evaluated on a paused world is evaluated on a different task. Stage 0 of
`docs/ARCHITECTURE_4T.md` makes the pause real before any other layer is built.

At the shipped **0.12 m/s one control tick is exactly 1.0 mm of belt**, so the
knob reads directly as millimetres: `d=4` is inside the catch-up's 6 mm
tolerance, `d=16` is 2.7x it.

## The cell

`FRUIT_EVAL_LATENCY ∈ {0, 4, 8, 16, auto}` x seeds {901, 902} x 6 episodes, the
`scripts/284_single_arm_policy_gate.sh` recipe verbatim (Panda + two bins,
`FRUIT_POLICY_TRIGGER=arrival`, `FRUIT_SKIP_LATE=0.5`, the six interface
settings), checkpoint `checkpoints/p227_panda156` (12-D, trained from scratch).
`auto` converts this machine's measured `act()` wall - the smoke read
**49-122 ms** per decision after warm-up (620 ms on the first call), i.e.
`auto` lands around **6-15 ticks**.

The injector is `sync-hold`: after a decision's inference returns, the env
advances `d` control ticks with the arm holding still, then executes the chunk
(`rl_env._inject_latency`). The observation is **not** refreshed during the
pause - a real deployment cannot see the frames it did not wait for.

## Predictions (falsifiable, arithmetic where possible)

**P1 (manipulation check, must pass for any other read).** Every non-zero cell
carries `[lat]` rows with `d` equal to the arm's setting, `sim_ms = d x 8.33`,
and the `d=0` cells carry none. A cell with no `[lat]` rows measured nothing.

**P2 (where the harm lands - the phase's real question).** The trigger is
geometric and is evaluated **inside the execution loop**, i.e. at true simulated
time, so the prediction is that **the fire's `t_arrive` is flat across `d`** and
the harm appears in the **arm's pose relative to the fruit** (catch-up residual,
`close: fruit drifted` rows). The *alternative* - `t_arrive` falling by about
`d/120` s - would mean the injection is delaying the **fire** rather than the
chunk (a call-site bug, not a latency effect). Either outcome is informative;
they must be reported as one or the other, never as "latency hurt".

**P3 (the count is a direction, not a rate).** At n = 6 x 2 the placed count is
a branch draw (P93). The registered read is: `d=16` loses **>= 2 of 12** placed
attempts relative to `d=0`, in the same direction at **both** seeds; anything
less is reported as "no count effect at this n".

**P4 (class).** No new failure-reason key. The expected losers, if any, are
`dynamic catch-up` misses / `fruit did not follow the gripper`, not a new class.

**P5 (the null branch, and it is a positive result).** If the count and the
mechanism are both flat up to `d=16` (133 ms of simulated pause), the conclusion
is **not** "latency does not matter" - it is that **this cell's layer separation
absorbs it**: the scripted catch-up re-aims every tick from the fruit's measured
position, so a late chunk costs a constant lag rather than accumulating error,
and the 6 mm tolerance plus the 200 mm catch-up budget cover it. That would be a
measured argument *for* the 4T split (L4 owns approach, L5 owns contact) and it
would set the tolerance the real 30 Hz deployment has to meet: **~33 ms =
1 tick**, four times tighter than the worst cell here.

## Falsifiers of the instrument itself

* If `d=0` is not the shipped path (a `[lat]` row, a different branch), the
  knob is not inert-off and the sweep is void.
* If `[lat]`'s `sim_ms` is not `d x 8.33`, the row is printing a constant.
* If the `d` column in the report differs from the file name, the naming is
  wrong (the bench writes the name it ran).

## What is NOT claimed

* No rate: 6 episodes x 2 seeds, a loop that conditions on rendered frames.
* No claim about the *async* form. `FRUIT_RTC` models the same delay by
  interleaving denoising with execution and is **refused** with this knob (the
  two would double-count); the async comparison is Stage 3.
* No claim about real-robot `t_close` / `t_settle` - they are unmeasured and
  belong to Stage 4.
