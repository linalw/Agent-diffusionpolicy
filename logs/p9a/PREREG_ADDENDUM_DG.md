# P19-B ADDENDUM to the frozen P9-A prereg (2026-10-19): the B1 calibration fix + the placebo arm

**Why this addendum exists.** The first B1 battery (`logs/p9a/run_b1_battery.sh`; runs
`50..63_*.log`) read **byte-identical A and B streams** (0 diff) — the lever never fired. The
`FRUIT_READY_DIAG=1` run (`logs/p9a/80_ready_diag.log`) shows why: at the no-op ready calls the
arm reads `pre_err = 0.0131-0.0135` (inside the 0.03 band) but **`dg = 0.0131-0.0135`, above the
frozen `READY_SKIP_SYNC_TOL = 0.01`** — the predicate misses by ~3 mrad. The P9 calibration came
from the biarm passive arm's stream; on the single-arm path the steady `dg` is 13.1-13.5 mrad.

**The deviation, stated.** `FRUIT_READY_SKIP_DG=0.02` (the implementation's own env override for
the sync tolerance; default stays 0.01) so the skip fires on the measured no-op state. This
changes the lever's operating point from the frozen text, so the battery is re-run in full and the
deviation is recorded here; the frozen prereg's endpoint (the clean-gap p50 ≤ 3.7 s; the interval
~19 s; the span flat; the motion budgets; the determinism) is unchanged.

**The placebo arm (the Oracle's design, already in the implementation).**
`FRUIT_READY_SKIP_HOLD=230` re-inserts the deleted 230 ticks as dead sim time, so arm P keeps the
shipped clock while removing the micro-history. Three arms, therefore:

| arm | env | isolates |
| --- | --- | --- |
| A | (shipped) | the control |
| B | `FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02` | the full lever (clock + micro-history) |
| P | the same + `FRUIT_READY_SKIP_HOLD=230` | the micro-history alone (the clock held) |

**The reads.** A vs B: the wall (gap p50, the interval); **B vs P: the micro-history question**
(if B == P on the outcomes, the effect is the clock only; if B beats P, the skipped micro-history
helps); the span must stay flat (the transit is inside the gap, not the attempt span); the
outcomes (placed counts, per-class) must not move; the motion budgets; each arm double-run
bit-identical.

**The battery.** (i) the acceptance scenario (10 attempts) and (ii) the W6-A patch battery
(20 attempts, SEED 5, balanced mix), arms A/B/P, each double-run: 12 runs (~85 min), chained
through `scripts/154_claim_run.sh`.
