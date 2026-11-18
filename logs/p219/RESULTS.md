# P219 result - the small handover lifts the mixed pool to 5/6 at seed 303

The shipped mixed pool (16 fruit, 3 small), P207 R5 recipe, `FRUIT_SMALL_HANDOVER=1`:
small fruit -> the scripted `task.run` skill, large -> the learned policy. Six episodes:

| seed | placed | per-episode |
|---|---:|---|
| 303 | **5/6** | orange, kiwi, peach, **lychee 3.0 (scripted, decision=0)**, peach; the one failure is a 7.0 cm right apple on the learned path |
| 808 | 3/4 partial | **lychee 3.1 (scripted)**, tomato right fail, **strawberry 3.1 (scripted)**, pear; the run was stopped after a renderer wedge on episode 4 |

The seed-303 cell is a full six: the learned large-fruit path is 4/4, the scripted small
path 1/1, and the only failure is the right-arm large-fruit class. The learned control at
the same seed was **3/6** (C303) / **4/6** (R5 303); the hybrid is +1 to +2 on one branch.
The seed-808 partial has the small class 2/2 and the large 1/1; its 3/4 is not a rate.

The cost: the scripted small attempts take 1700-1900 ticks against the learned 1100-1300,
so the mixed branch is ~10-15 % slower per small fruit; the count gain is the point. The
one right apple shows the handover cannot fix the right-arm large-fruit class.

**Verdict: a real class mechanism and a positive mixed seed-303 cell, but a hybrid.** The
learned small-fruit approach remains open; the recipe setting is opt-in.

**Pins.** `rl_env.py` **`bd1bf141`**, `scripts/280_p218_small_handover_selftest.py`
**`24c8bfad`**, `selfcheck.sh` **`a9314fe9`**; evidence `logs/p219/{MIX_s303.log,
MIX_s808.log,MIX_s808_partial.log}`. No default change.
