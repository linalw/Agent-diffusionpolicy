# P222 pre-registration - the side-conditioned scripted skill

The scripted B-heavy control places **6/6 right-arm fruit** (kiwi, strawberry, peach,
lychee, strawberry, orange; 10-15.6 N), while the learned right is 2/6 (P212) and the
right large failures (7.0 apple, 6.8 tomato, 6.9 pear) recur in the hybrid cells. The
right class is the learned policy's loaded-slide/approach, not the hand.

**Knob.** `FRUIT_HANDOVER_SIDE=right` (default off; `left`/`both` also accepted) routes
every right-arm sample to `_run_scripted`, the same `task.run` as the scripted control;
the left stays learned. Combined with `FRUIT_SMALL_HANDOVER=1`, the learned policy owns
only left large fruit; the right and all small fruit are scripted.

**Cell.** Mixed pool, seed 303, 6 episodes, `FRUIT_SMALL_HANDOVER=1
FRUIT_HANDOVER_SIDE=right`; control P219's mixed 5/6 (right apple fail). Endpoints: placed
count; the per-arm route (`decision=0` on the scripted picks); the scripted right force/
lift. Falsifiers: F1 a right sample still runs the policy; F2 the count is below 5/6; F3
the per-attempt span rises above 20 s. A pass earns seed 808 and the continuous variant.
This is a **hybrid**, not a learned right policy.
