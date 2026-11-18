# P216 pre-registration - the phase close's along window gets a lower bound

The small-fruit `[close]` rows are the phase gate firing with the fruit **behind** the
hand: `[close] xy=442mm dz=+122mm`, `[fire] gap=459mm dy=-442mm` at seed 808 (P215).
The code's phase trigger is `dy <= FRUIT_CLOSE_RAMP_DY` (0.014 m), which is true for
**any negative dy** - a fruit half a metre downstream satisfies it. The contact servo's
own upstream-only arming refuses a fruit behind (`BEHIND_TOL` 0.02 m), but the close ramp
does not.

**Knob.** `FRUIT_CLOSE_RAMP_DY_LO` (metres, default `-inf` = the shipped one-sided path):
the phase trigger becomes `dy_lo <= dy <= dy_hi`. The treatment is `-0.02`, the contact
servo's measured "level or just behind" window.

**Cell.** Lychee-only supply, P207 R5 recipe, seed 808, 6 episodes. The same-seed control
is P215's 60 N cell (1/6; the successful one is the 3.7 cm lychee, the 3.1-3.6 class
fails). Endpoints: does any `[close]` row still have `dy < -20 mm` (the bug), does the
close latch at a near fruit, and the placed count. Falsifiers: F1 a `-0.02` run still has
a close with dy < -20 mm (the knob did not bind); F2 the count falls by 2 or more; F3 the
close disappears entirely (the policy never re-approaches) with no count gain.

A pass earns a seed-303 repeat and the mixed pool. The default stays `-inf` until a pass.
