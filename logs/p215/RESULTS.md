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
