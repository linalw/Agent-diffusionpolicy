# P222 result - the right arm is fine with the scripted skill; the left learned is the residual

**The control.** The scripted dynamic catch on a B-heavy pool (right arm), seed 808, 6
attempts: **6/6**, forces 9.96-15.58 N, lifts 0.298-0.497 m (kiwi, strawberry, peach,
lychee, strawberry, orange). The learned right on the same B-heavy cell was 2/6 (P212).

**The route.** `FRUIT_HANDOVER_SIDE=right` sends every right-arm sample to
`_run_scripted`; the left stays learned. Mixed pool, seed 303, 6 episodes, with
`FRUIT_SMALL_HANDOVER=1`:

| arm | route | placed |
|---|---|---:|
| right | scripted | **3/3** (kiwi, tomato, lychee) |
| left | learned | **1/3** (apple; orange and 5.9 cm pear fail at 541/507 ticks) |

Mixed **3/6**, against P219's 5/6 on the same seed. The right handover is doing its job;
the left learned branch is the reason the mixed count fell. The P219 5/6 had a favourable
left branch (left 1/1); the P222 cell has left 1/3. **The side route is a mechanism, not a
mixed success lever**, and the learned left large fruit is the residual.

The left failures are the loaded-slide class (the `[close]` rows are at 19 mm; the
`[fire]` row is at `dx=-84 mm` after the fruit walked). The right scripted 6/6 says the
hand/primitive is fine on that side; the learned left is not.

**Verdict: not adopted as a success claim.** The knob (`FRUIT_HANDOVER_SIDE`, default
off) stays as a measurement/route capability. A full scripted fallback is the scripted
two-line's 72.5 %; the learned left 70 % is not worse on the branch, and the right side
route moves the count only as far as the left branch allows.

**Pins.** `rl_env.py` **`223c8172`**, `scripts/281_p222_side_handover_selftest.py`
**`997e91c5`**, `selfcheck.sh` **`809af770`**; evidence `logs/p222/scripted_bheavy.log`,
`SIDE_s303.log`. No default change.
