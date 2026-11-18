# P216 result - the phase close's one-sided trigger was a real bug; fixing it exposes the policy

The P215 `[close]` rows on small fruit read `xy=442 mm`, `[fire] dy=-442 mm`: the phase
gate closed the pads with the fruit **behind the hand**. The code's trigger was
`dy <= FRUIT_CLOSE_RAMP_DY` (0.014 m), which is true for any negative dy. P216 adds
`FRUIT_CLOSE_RAMP_DY_LO` (default `-inf` = the shipped one-sided path); the treatment is
`-0.02`, the contact servo's own "level or just behind" window.

| cell | placed | close rows | `[fire]` on 3.1-3.4 cm |
|---|---:|---|---|
| control P215 (60 N, `-inf`) | 1/6 | one at `xy=442 mm` (the phantom) | `fired=1`, gap 459 mm, dy -442 mm |
| treatment `-0.02` | **0/4** (partial; every small attempt ran its horizon) | one at `xy=25 mm` (a 3.4-3.7 cm fruit) | **`fired=0`, gap 647-1180 mm, dy -554..-1145 mm** |

**The fix is correct and the bug is gone**: no close has `dy < -20 mm`; the only close is
at 25 mm. But the small fruit now show the real state: **`fired=0` at the attempt's end
with the fruit 0.65-1.18 m behind the hand**. The policy never approaches those fruit;
the one-sided trigger had been ending the attempt with a bogus close at 0.44 m, which
looked like a grasp attempt but was not.

**This corrects P215.** The 20 N vs 60 N comparison could not measure the hand: the 3.1 cm
fruit never reached the pads. The 3.7 cm lychee closes at 25 mm and places at both caps.
The small-fruit residual is **the policy's approach/phase**, not force and not pad
geometry. The P215 "pad/hand geometry" sentence is withdrawn.

The treatment is a partial cell (4 attempts, no full 6) because the refused phantom close
makes every small attempt run to its 2600-tick horizon; the 0/4 is not a rate. The
mechanism is categorical and the `[fire]` rows carry it. `FRUIT_CLOSE_RAMP_DY_LO=-0.02` is
a **correctness setting** for the recipe; the default stays `-inf` until a policy fix
makes the small fruit reachable. The next spend is the **policy**: a size-aware phase
gate or a retrain/cartesian action that actually approaches a 3 cm fruit.

**Pins.** `rl_env.py` **`8f3c350f`**, `scripts/279_p216_close_lo_selftest.py`
**`281521ec`**, `selfcheck.sh` **`69c566b2`**; evidence `logs/p216/LO_s808.log`,
`logs/p217/RESULTS.md` and `logs/p216/scripted_lychee.log`. No default change: the knob
defaults to `-inf`; the recipe setting is `-0.02`.
