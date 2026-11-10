# P137 pre-registration - the selector's last constant-speed term

**Written before the wave cell was read; the acceptance had already run once (it
is the inertness proof, not the endpoint).**

## 0. The term

`select_target` sizes its station window in **metres** from a **time**: the
pre-pose lead (`FRUIT_PREPOSE_LEAD_S` 0.9 s, plus `FRUIT_PREPOSE_LEAD` 0.12 m) and
`_dynamic_select_floor`'s 1.5 s setup. Both multiplied the **authored** speed,
`cfg.belt_speed`, not the belt's own. On a constant belt they are the same number;
on a conveyor whose speed varies they differ by

    FRUIT_PREPOSE_LEAD_S * |v - v_nominal|   (up to 36 mm at +-0.04 m/s)

and the window is then sized for a belt that is not running. The upstream edge is
a *minimum*, so an over-large window refuses a valid fruit (starvation) and an
under-large one admits a fruit that is already too close (a miss).

## 1. The change

`_selector_speed(task)`: the live `_belt_speed_estimate()`, with the config value
as the fallback when there is no encoder (the offline stubs) and behind
`FRUIT_SELECT_LIVE_SPEED=0`. Three call sites: `_prepose_lead_value` (the selector's
own edge and the reach path) and `select_target`'s two pre-pose-lead terms.

## 2. Decision rule

1. **Inertness is the gate**: on the shipped (constant-speed) acceptance the
   `[fruit]` stream must be **byte-identical** to the pre-change record
   (`logs/p136/accept_final.log`, 459 lines) with `fingerprint: matches` and
   `190: PASS`. If it is not, the change is not resolution-only and does not ship.
2. **The mechanism cell**: the belt wave (0.04 m/s at 0.5 Hz, the P135 scenario).
   Report the catch residuals, the ticks and the count. **A count is not the
   endpoint** - the endpoint is whether the selection changes at all.
3. If (1) holds, the change ships (it removes a wrong input, it is not a lever);
   an unchanged wave cell is recorded as **not binding**, not as a null failure.

## 3. Not claimed

No rate, no throughput, no starvation change. The record's own P99/P58/P59
selector work says the interval is not arrival-bound, so this is a **correctness**
change: the selector stops reading a number the belt is not running at.
