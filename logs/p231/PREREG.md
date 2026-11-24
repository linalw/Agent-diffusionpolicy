# P231 pre-registration: the lift travels with the belt

**Pinned 2026-11-24, before any `FRUIT_LIFT_TRACK_BELT` cell was read.**

## The measured gap

P230 traced the 0.24 m/s cell tick by tick: **all three closes grip** (2 contacts,
5.7-9.4 N at the close's end), and the two episodes that finish `grasped=False`
**were holding the fruit when the close ended**. The payload is gone by the lift.

That is the record's loaded slide (`logs/p42/SIM_LIMIT.md`), whose force / pad-face
/ friction / seat levers are all measured out. The term that is **not** in that
closed set is the **relative velocity**: through `grasp_lift` the hand is nearly
stationary in y while the belt drags the payload at `v`, so the pinch carries
`v x t_lift` of drag - 60 mm at 0.24 m/s against 30 mm at 0.12.

## The lever

`FRUIT_LIFT_TRACK_BELT=1` (default off) adds `v x t` to the `grasp_lift`
command's y for the whole leg (bounded by `FRUIT_LIFT_TRACK_MAX`, default 0.12 m),
so the pads travel **with** the belt and the relative velocity at the grip is ~0.
The profile shape - and its friction cone - is unchanged; only the frame is
translated. It prints one `[lift-track]` row per armed lift (`v`, ticks, `dy`).

## Cells

| cell | `v` | `ext` | `LIFT_TRACK_BELT` | episodes |
|---|---|---|---|---|
| A (control) | 0.24 | 0.10 | off | 3 |
| B (treatment) | 0.24 | 0.10 | **on** | 3 |
| C (no-harm at the shipped speed) | 0.12 | 0 | **on** | 2 |

All three run with `FRUIT_CARRY_DIAG=1`, so `clean_slip_max` and
`contacts@onset` are read from the same instrument in both arms (P230's lesson:
the trace/ diag changes the branch, so the A/B must share it).

## Predictions

**P1 (the endpoint, branch-free).** On the `grasp_lift` legs, `clean_slip_max`
falls from the control's distribution to a few millimetres: when the hand moves
with the belt there is no drag to slide against. This is a **per-leg** quantity
and does not depend on which branch the episode took.

**P2 (the count, a direction).** At 0.24, `grasped=True` rises above the
control's 1/3. 3 episodes is a draw - the claim is the direction plus P1's
mechanism.

**P3 (inertness at the shipped speed).** At 0.12 the offset is
`0.12 x t_lift` = 30 mm, which is inside the reachable band; the placed count
does not fall and `clean_slip` does not rise. If 0.12 degrades, the lever is
**not** inert and cannot be adopted at any speed.

**P4 (the cost, reported).** The lift's y travel is 60 mm at 0.24 - the hand ends
further downstream, so the following place leg starts from a different point. The
`[motion]`/`[carry]` rows are reported; a place-side regression would be a real
cost and is named, not hidden.

## Falsifier

If `clean_slip_max` on the lift legs **does not fall**, the relative velocity is
not what loads the grip and the lever is wrong - report the negative, do not
tune the bound. If it falls but `grasped` does not move at all, the loss is
happening for a different reason and the next instrument is the payload's pose in
the hand frame at the lift's first 10 ticks (the hand-relative reference the
`[carry]` row already computes).

## What is not claimed

No rate (3 episodes/arm). No claim about the shipped 0.08-0.12 numbers - those
are unaffected and are the objective's "success first" plateau.
