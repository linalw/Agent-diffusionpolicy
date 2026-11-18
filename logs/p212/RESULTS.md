# P212 result - the right arm's place transit speed is not the lever

B-heavy supply (`A:0.10,B:0.80,C:0.10`, 2/12/2 of the pool) so almost every episode is the
right arm; seed 808, 6 episodes per arm, same P207 R5 recipe, only
`FRUIT_PLACE_SERVO_VMAX_RIGHT` differs:

| arm | placed | `[pservo]` rows | last `hold=` |
|---|---|---|
| control right 0.20 | **2/6** (tomato, kiwi) | 428 | 115-120 mm |
| right 0.15 | **2/6** (apple, peach) | 887 | 115-120 mm |

The slower transit **doubles the place-servo ticks** and does not recover the payload:
the `hold=` (the payload's distance from the jaw) grows to 115-120 mm in both arms, i.e.
the fruit is already out of the pinch **before** the place transit can be the cause. The
right's failures in this cell are the 3.1-3.5 cm small fruit and an orange that loses the
payload in the lift/carry, not the place speed. **F1 fires (the slip does not move) and
F3 fires (the span rises); not adopted.** The per-arm knob stays default-off as a
measurement capability; the right-arm residual is the grip/lift class, not the transit.

`FRUIT_PLACE_SERVO_VMAX_LEFT/RIGHT` is default-inert (unset = the global); the banner and
manifest print only when an arm differs. No rate is claimed (6 episodes, B-heavy
mechanism cell).

**Pins.** `rl_env.py` **`b7a2698a`**, `tasks.py` **`d1b18e2a`**,
`scripts/275_p212_place_vmax_selftest.py` **`409c56e6`**, `selfcheck.sh`
**`82dda3df`**; evidence `logs/p212/{PREREG,RESULTS}.md`, `R020_s808`, `R015_s808`.
