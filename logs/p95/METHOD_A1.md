# P95 METHOD amendment A1 (applied during the analysis, declared)

`logs/p95/METHOD.md` (md5 `b79e9a081209466aa316c45f5f7fae5b`) is the pre-run
registration and is **not** rewritten. This amendment records the three analysis
decisions taken after the first probe pass, with what they changed and what they
did not.

## A1.1 The spin-jump threshold: 0.5 -> 2.0 rad/s

METHOD §3 set a jump at `|Δ|v|| >= 0.03 m/s` **or** `|Δ|ω|| >= 0.5 rad/s`. At 0.5
the seed-6 cell produced **149 "departures"**, almost all of them the fruit's own
tumble: a kiwi is a prolate ellipsoid and rolls, so its spin oscillates 0-6 rad/s
on the belt with its centre at belt speed (`logs/p95/probe.txt` prints the
sequence). The threshold is now **2.0 rad/s**; the speed thresholds are unchanged
(0.03 m/s per tick for a jump, 0.05 m/s for a departure).

**What this did not change:** the witness's attribution. It reads `arm-other`
under both thresholds - the strike cluster's spin change is **21.6 rad/s**, ten
times the new bar.

## A1.2 The contact verdict is the pair, not the gap

METHOD §4 defined the classes from "the pads are within a few mm", which needs a
pad geometry the trace does not have exactly. The finger plates are **angled** at a
98 mm span, so the pad-point model (`jaw - 0.0805 z`, `±sep/2` along X) is a
**±5 mm indicator**: on seed-5 attempt 16 it reads a **0.0 mm** clearance while the
physics shows a pure tangential graze (`|v|` exactly 0.120 m/s, spin exactly 0.0,
`sep` 98.0 throughout - no impulse at all).

The verdict is therefore `pad gap <= 6 mm` **and** that hand's *measured* jaw-span
swing `>= 2 mm` within ±4 ticks - the span cannot be commanded (the finger drive is
stiffness-limited to 0.1 mm at P41's `k = 1e5 N/m` and the 10 N cap), so a
displaced span is a contact and a zero swing is a graze. The gap is used to **rank
and report** the exposure.

## A1.3 The descent leg's start is log-derived

METHOD §3 assumed the phase label could locate the leg. It cannot:
`_cycle_mark("descent")` fires **after** `_approach`, so the `descent` run is the
leg's **end** (the catch-up's first tick). A jaw-height rule finds that end too
(its first match going backwards is the deceleration). The start is
`first_descent_tick - steps`, with `steps` from that leg's own
`[motion] approach(cartesian) … steps=`; the traces are paired to the log's rows by
the sim time of each leg's end (the arbiter serialises the two arms, so print order
is sim order). **Validation:** on seed 6 attempt 0 the rule gives tick 339,
`t = 17.225 s`, and that row reproduces P93's `descent` row to every digit
(position, `v`, `ω`). Every leg's `first_descent - start` then equals its logged
`steps` on **20/20** attempts of both seeds.

## A1.4 What A1 costs the claims

Nothing in the *attribution* (§2 of `RESULTS.md`) and nothing in the *exposure*
census (§3) depends on the pre-amendment thresholds: the witness is a 21.6 rad/s
event with a 26-38 mm pad displacement, and its neighbours' swings are
`<= 0.0004 m/s`. What A1 does change is the **noise floor** of the census - the
149-count at 0.5 rad/s is a list of rolling transients, not events, and quoting it
as a departure count would have been wrong.
