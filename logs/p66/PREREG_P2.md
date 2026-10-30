# P66 phase 2 PRE-REGISTRATION — the lift-end-height ladder (written before any run)

Oracle 1 replaced the registered C0 cell with this one. The reason is in the doc's
verbatim text (`logs/p66/STATION_SWEEP.md` + the gate): `hold_drift` is the per-leg
**max**, and at a lift's first tick the arm sits ~100.66 deg from C0, so a
`hold_drift <= 5` bar is unreachable by construction; and C0 moves the achieved
projection the **wrong way** (+0.32..+0.37 -> +0.516) while adding ~100 deg of
loaded wrist rotation. The ladder instead manipulates the **mediator** (the
rotation) with everything else held.

## Cell

Direct-scoped constant `lift_dz` threaded to the `grasp_lift` target height (the
P64 `carry_hold_override` precedent; `FRUIT_OPENARM_TRANSFER_LIFT` is
scripted-visible, so it must be scoped, not flipped):

| arm | `lift_dz` | target height (belt_top + ) |
|---|---|---|
| control | **+0.08** (shipped 0.36) | 0.36 |
| L1 | **0.00** | 0.28 |
| L2 | **-0.08** | 0.20 |

3 seeds (77/101/202) x 15 picks, **interleaved control -> L1 -> L2 -> control**,
one claim per run, logs `logs/p66/p2/{C0,L1,L2}_{seed}.log`.

## Prediction (pre-registered, from `sweep_rows.json` y = 0, live/static ~ 0.75)

`hold_drift` **at the leg's end** = **24.6 / 8 +- 3 / 3 +- 2 deg**.

## Endpoints

- **Primary (the result)**: the left's **cnp count**, and on the escaping legs
  `onset_row` (P63: 104.5 median) and `clean_slip_max`.
- **Manipulation checks**: `drift_end` inside the predicted band; the **achieved
  belt projection unchanged (+0.32..+0.37 +- 0.03)** - this is what makes it a
  rotation test, not a drag test; `q_margin`/`q_cmd_margin` unchanged.
- **Instrument (new, one dot per leg)**: `drift_end` (the last tick's drift, not
  the max) and `res_end`/`dz_end` (the achieved position error at the lift's end) -
  the live split the interpretation rests on.
- **Secondary**: the right arm unchanged; s/attempt; the place leg lands on the
  belt (`on_belt`, no `fruit fell off the line`); no new failure reason.

## Falsifiers

- **F1** `drift_end` misses the predicted band -> the dose-response is wrong; stop
  the ladder.
- **F2** `clean_slip`/`onset_row` move but the cnp count does not -> the slip is
  not the class.
- **F3** a new failure reason.
- **F4** the place leg loses payloads -> the cell is inadmissible; restore +0.08.

## Readings

- **Positive** = the rotation is the mediator -> the lever is the lift's height (or
  a grip attitude needing no rotation); price the lowered lift for adoption.
- **Null at 3 deg** = the rotation is **not** the mediator -> with P41/P42/P62/P64
  closed, **the attitude lane closes** and phase 3 (the big move) is justified.

## No-harm

`--ablate scripted` byte-identity, `accept.sh` **377/377 + `fingerprint: matches`**
(an **import guard**: the scripted line never constructs `SortingRLEnv`),
`selfcheck.sh` PASS, `configs/*` untouched.
