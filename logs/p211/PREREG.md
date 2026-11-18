# P211 pre-registration - the small-fruit selector floor

The P207/P209/P210 cells leave the small-fruit class (3.0-3.4 cm) as the residual: in
the E4/E4T seed-808 cells the two failures are 3.1 cm lychees, and the record's
`[fire]` census says the failed small fruit begin **level with or behind the hand**. The
global selector-timing knobs were all negative (P200's uniform +0.18 m floor: 6/12 against
8/12, upstream-at-latch 5/11 against 7/12), so this is the **narrower** form: a
size-conditioned refusal.

**Knobs.** `FRUIT_SELECT_SMALL_EXTRA` (metres, default 0 = shipped) and
`FRUIT_SELECT_SMALL_DIA` (default 0.040 m), direct/policy path only. A candidate with
`diameter <= dia` must sit at least `extra` further upstream than the normal moving-catch
floor; otherwise it is refused and the selector waits for/chooses another candidate. The
belt is never stopped, diverted or gated; a refused small fruit is simply not attempted.

**Cell.** The adopted E4 recipe (P207 R5, clamp, release endpoint) plus
`FRUIT_SELECT_SMALL_EXTRA=0.15`, `FRUIT_SELECT_SMALL_DIA=0.040`, seed 808, 6 episodes.
The control is the same-batch P209 E4 cell (4/6, the two failures 3.1 cm lychee and a
6.5 cm right apple).

**Endpoints.** The per-attempt ledger: does a 3.1 cm lychee still get attempted inside the
floor, or is it refused (`below catch floor` diag row)? Placed count (report only),
`[fire]` close gap, small-fruit success, and the number of selection wait rounds. Falsifiers:
F1 the small fruit is still attempted at the same along-position (the knob did not bind);
F2 the small fruit is skipped but no other fruit is selected within the reset's 40 feed
rounds (starvation); F3 the placed count falls by 2 or more. A pass earns a seed-303
repeat and the WS-4.2 cell; no default is flipped.
