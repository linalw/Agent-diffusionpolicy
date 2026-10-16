# P3 RESULTS: the place-leg shortening is closed by geometry

Branch `p-supply`. Pre-registration: `logs/p3/PREREGISTRATION.md`.
Evidence: `logs/p3/10_patch_shift10.log`, `logs/p3/11_patch_shift11.log`
(the double and the wave transfer were cancelled once the geometry closed - see below).

## 1. What the knob did, and what it cost

`FRUIT_PLACE_INNER_SHIFT` (default 0, off) moves the place target's `y` toward the body, capped at
90 % of the output belt's half width (`output_belt_size[1]`/2 = 0.125 m), in `jaw_target`.

| config | place leg distance | place leg ticks | success |
| --- | --- | --- | --- |
| control (patch D=1.60, `logs/p2d/52_d160.log`) | 45.1 cm | 297 | 18/20 = 90 % |
| `FRUIT_PLACE_INNER_SHIFT=0.10` | **36.1 cm** | **237** | **6/20 = 30 %** |

The kinematics worked exactly as designed (-9 cm of carry, -60 ticks ~= -1.0 s of the arm span)
and the result is a **30 % success rate** - the pre-registered fail condition (a) fires.

**The mechanism is geometric, and it is the finding.** The release point's y in the control is
`|0.553|` and `|0.572|` (the payload's position at release, from the `[task] released at` lines);
with the 10 cm shift it becomes `|0.410|` and `|0.208|`. The output belt spans
`|y| = 0.375 .. 0.625` (`output_place_y` 0.5 ± the half width 0.125), so the shifted releases
land **beside the lane**, and the log says so directly:
`released at [..., 0.208, ...], placed=False (on/next to output belt 0)`.

Two things follow, and they close the lever:

1. **The shift is not a clean geometric offset.** The measured displacement (0.14-0.36 m) is
   larger and more variable than the commanded 0.10 m: the shortened transfer changes the wrist
   configuration the IK settles into, so the release geometry scatters.
2. **There is almost nothing to shorten.** The control's payload already releases at |y| ~ 0.55,
   only 35 mm inside the belt's inner edge at 0.375. The maximum shift that keeps the payload on
   the belt is therefore ~**30 mm** - about 18 ticks, ~0.2 s, **1.3 % of the 15 s arm span**, far
   below the pre-registered 4 % bar. The other axis (along the belt, x: the drop is at 0.43 and
   the belt runs to 1.20) is limited by the arm's reach at the place height, which is not
   measured - and the W4-era note (`tasks.py`, `FRUIT_CARRY_HOLD_QUAT`) records the IK stalling
   ~12 cm short of the output line when the transfer attitude is held, so the x headroom needs its
   own probe before it can be claimed.

**Verdict: not adopted; the lever is closed as designed** (default 0, byte-identical; only the
10 cm and 11 cm candidates were run, and the 11 cm run is strictly worse by construction since the
cap is monotone - the double-run and the wave transfer were cancelled as the criterion was already
decided).

## 2. What this leaves for the span

The place+release block (5.2 s, 35 % of the arm span) is **not** attackable by moving the release
point: the geometry forbids it. The remaining candidates on the measured binding term are

| block | s | status |
| --- | --- | --- |
| place + release | 5.2 | **closed by geometry** (this phase); the release *ordering* (`FRUIT_RELEASE_SUPPORT`, the dwell) is untested but the W1/W2 place negatives stand |
| descent | 3.0 | the documented boundary shortfall (every descent ends 40-90 mm short, `AGENTS.md`); the fix is "a descent command that respects the reachable band", which needs the R10 reach map applied to the *descent target*, not a supply redesign |
| close + grip | 2.9 | the W1 grip profile already retunes this on the two-line (6 mm / 60 ticks, step 0.01) |
| lift | 1.8 | the carry-class leg; R11-B read the escape as a mid-lift one-sided slide |
| prepose + hover | 1.5 | the park gate (W7-A) already made the park conditional |

So the span's next real target is the **descent's boundary shortfall**, which is a
commanded-target fix with the measured evidence already in place.

## 3. The no-harm

The knob is default-off and only enters `jaw_target`'s `py` when set, so no shipped path is
touched. `tasks.py` changed (the knob + the `math` import), so `rl_env.py`'s `TASKS_MD5` follows
(`3b15f3ff...` -> `bcb1fb72d80511a35f8b89cad0ca0a23`, metadata-only). The P2-tree acceptance
(9/10 + `fingerprint: matches`, `logs/p2d/90_accept_claim.log`) was measured **before** this change,
so a re-run is required before this branch merges - recorded as an open item, not claimed as done.