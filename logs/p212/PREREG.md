# P212 pre-registration - the right arm's place transit speed

The direct lane's right arm is ~48 % against the left's ~70 %. The record's right-arm
software levers are spent (P182b's contact lead 0.20, the park, the pad width, the force
cap); the remaining class is the loaded slide in the **place leg**. The place transit's
0.20 m/s is a **global** P173 peak (0.15 -> 8/16, 0.20 -> 14/16, 0.25 -> 7/16) measured
on the mixed cell; the two arms have different paths, and a right-only slower transit
costs only the right's cycle.

**Knobs.** `FRUIT_PLACE_SERVO_VMAX_LEFT/RIGHT` (metres/second, unset = the global
`FRUIT_PLACE_SERVO_VMAX`), one side selection in `_apply_place_servo`; default off and
byte-inert.

**Cell.** A B-heavy supply (`FRUIT_SUPPLY_GRADES=A:0.10,B:0.80,C:0.10`, 2/12/2 of the
16-fruit pool) so almost every episode is the right arm; the adopted P207 R5 recipe plus
`FRUIT_CARRY_DIAG=1` and `FRUIT_PLACE_SERVO_DIAG=1`. Seed 808, 6 episodes per arm:
control right vmax 0.20, treatment 0.15. The supply mix is the same in both cells; it is
a mechanism cell, not a rate on the shipped mix.

**Endpoints.** Right-arm placed count (report only), the place leg's `clean_slip` and
`force_min`/`sep@loss`, the `[pservo]` transit/at_place tick split, and the attempt span.
Falsifiers: F1 the right place slips do not move; F2 right placed falls by 2 or more;
F3 the attempt span rises by more than 15 % with no slip gain. A pass earns a seed-303
repeat and the shipped mix; no default is flipped.
