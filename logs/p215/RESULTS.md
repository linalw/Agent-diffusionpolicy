# P215 result - the small-fruit class is not force-limited

Lychee-only supply (all 3.1-3.7 cm), P207 R5 recipe, seed 808, 6 episodes per arm. The
global direct cap stays 60 N; only the branch for fruit <= 4.0 cm differs:

| small-fruit cap | placed | the one success | `[drive]` row |
|---|---:|---|---|
| 60 N (= global) | **1/6** | 3.7 cm lychee, left | `10.00 -> 60.00 N (..._SMALL)` |
| 20 N | **1/6** | 3.7 cm lychee, left | `10.00 -> 20.00 N (..._SMALL)` |

The 3.1 / 3.1 / 3.1 / 3.4 / 3.6 cm lychees fail at **both** caps; the 3.7 cm one places at
both. The size-dependent cap is armed and visible (`[drive]`), but it does not convert
the class. The head estimate on the 3.1 cm fruit is **1.74-2.13 mm** (P214), so it is not
perception either. With 20-60 N both failing, the remaining term is the **pad/finger
geometry on a 3 cm object**, not the clamp force.

**Verdict: not force-limited; not adopted.** The size-dependent cap
(`FRUIT_FINGER_MAXFORCE_DIRECT_SMALL`, default 0 = global) stays as a measurement
capability. The small-fruit residual is the hardware/new-pad class the record already
names (`docs/END_EFFECTOR_DECISION.md`); no software knob is left on it.

**Pins.** `rl_env.py` **`f7ebb7cb`**, `scripts/278_p215_small_clamp_selftest.py`
**`ef36266f`**, `selfcheck.sh` **`1b51e26b`**; evidence `logs/p215/{SM60N_s808.log,
SM20N_s808.log}`. No default change.

## Correction (P216, same day) - the force comparison is confounded; the geometry claim is withdrawn

P216 added a lower bound to the phase close's along window. With it, the 3.1-3.4 cm fruit
read **`[fire] fired=0` at the attempt's end with the fruit 0.65-1.18 m behind the hand** -
they never reach the pads. The P215 60 N/20 N comparison therefore did **not** measure the
hand; the 3.7 cm lychee closes at 25 mm and places at both caps. The sentence "the
remaining term is the pad/finger geometry" is **withdrawn**: the small-fruit residual is
the **policy approach/phase**, not force and not the hand. The one-sided close at 442 mm
was the symptom that hid it.
