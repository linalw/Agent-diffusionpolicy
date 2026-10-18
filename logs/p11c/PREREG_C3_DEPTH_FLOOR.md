# P11-C.3 PREREG (FROZEN): the from-open arrival + the keep-gap depth floor

Frozen 2026-10-18 before any run. Branch `p-supply`; the P11-C.2 wrap at the C2 commit.

## Why

P11-C: the from-open arrival halves the falls at the primary but the close still runs to the
chased (deep) `keep_gap` -> the class re-draws at the controls. P11-C.2: the chase stop
(`FRUIT_FORCE_REENTRY=1`) is the wrong instrument (the primary collapses 13 -> 6). The
corrected plow re-run: a true descend ejects at the deeper interferences (tomato delta >= 10
2/3, apple delta >= 2 3/3) and not at the shallow ones -> **the depth itself must be capped**.
The natural instrument: a **keep-gap floor** at the live measured extent + a margin (the
P11-A audit's option 1: `keep_gap = max(squeeze_gap, live_extent + margin)`, margin >= 0).

## The mechanism (needs a small code change: the floor knob)

`FRUIT_DYNAMIC_REGRASP_FLOOR_MM` (default 0 = off, byte-inert): when > 0, the re-seat's
`keep_gap` and the ratchet are floored at `pinch_width(sample, quat) + margin` (the live
extent read the close already uses). Two-line-scoped via `_dynamic_profile`. Arm B =
`FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1 FRUIT_DYNAMIC_REGRASP_FLOOR_MM=2.0`.

## Endpoints / kills / no-harm

As P11-C.2 (the falls >= 2/3 at the primary; the no-grasp class rise <= +1; no new reasons;
the cycle <= +5 %; the acceptance 385/385; the A records replay). The honest prior: the
arrival+floor combo may still trade the falls for the marginal grips (the floor removes the
deep close, which is also the grip mechanism) - the class-shift check is the decisive one.
