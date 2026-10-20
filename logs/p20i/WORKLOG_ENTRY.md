### P20-C (2026-10-20): the B1c feeder re-anchor is implemented default-off — the skipped ticks are credited to the feeder's *schedule* cursor (not the arm's gap), the debit is code-exact (210 or 230 ticks, not a flat 230), and the placebo still cancels it one-for-one

Tier-C implementation lane (branch `p-supply`; the mission forbade simulator runs - a Tier-A
battery is in flight - so this is implementation + offline verification only, no default
change). Design: `logs/p20/B1C_DESIGN.md` section 4.1 form (b), the recommended form.
Deliverables `logs/p20i/{IMPLEMENTATION.md,check_resync.py,05_diff.patch,06_diff_mine_only.patch}`,
artifacts `logs/p20i/{00_tree_pins,01_py_compile,02_selfcheck,03_stubs,04_check_resync}*`.
Pins at hand-off: `tasks.py` **455f1a33**, `rl_env.py` (`TASKS_MD5`) **88bcde27**, `fruits.py`
**d28546d2** (untouched), `configs/*` untouched. The pre-lane tree was `tasks.py` 3d88408d (the
design's pin).

**What the lever does, restated in code terms.** The scattered feeder releases on an absolute
schedule (`_next_release`, one drawn gap per due slot) and the driver pumps it only inside the
60-tick feed window, so each poll's supply is a function of the *pump instant*: `late =
sim_time - _next_release` -> `along = spawn_y - late*v`. A skip that removes `D` ticks from the
gap moves that instant `D` ticks earlier on the grid, and because it fires at every gap the debt
is cumulative: 230 ticks = 1.917 s = **0.230 m = 82 % of the usable 0.281 m band per gap** (0.46 m
at slot 2, 1.38 m at slot 6, 1.84 m at slot 8) - the B1 empty-poll class. The fix credits the same
`D` to the schedule clock, so the pump instant stays the *shipped virtual* time: the supply is
pre-delivered by the dead time the lever removed and nothing waits.

**The debit is code-exact, and the design's formula is 20 ticks high on part of the band.**
`K = catch_up + 90 + _ready_settle()` with `catch_up = 20` **only when `dg > 0.01`**: the skip
predicate's `dg` is literally `_catch_up_drive`'s own no-op gap (`_ready_residuals` computes the
same `max|q_target - q_measured|`), so the 20-tick ramp is code-exactly present or absent.
`_ready_transit`'s lift never runs (it returns early below `READY_STAGE_ERR` 0.35 vs the skip's
0.03), so there is no third term. The battery runs `FRUIT_READY_SKIP_DG=0.02` at a measured
`dg` 0.0131-0.0135, i.e. the 230 rows - but with the default `SKIP_DG=0.01` the skip can only
fire at `dg <= 0.01`, where the design's flat `20+90+settle = 230` would over-credit **20 ticks
(0.02 m)** per gap. Implemented as the conditional form; the stub pins the `dg = 0.01` edge
(210) and one tick past it (230).

**The implementation deviates from the sketch's *file*, not its algebra.** The design puts
`_supply_shift` + `advance_supply_clock` in `fruits.py` and adds it at the pump's four schedule
sites (`while`, `late`, the queue interlock, the top-up). This lane may only write `tasks.py`, so
the shift is applied to the other side of the same four comparisons, once, at the skip site:
`spawner._next_release -= ticks * CONTROL_DT`. All four sites are affine in the cursor
(`sim + s >= cursor` <=> `sim >= cursor - s`; same for the subtraction and for both
`max(cursor, sim + s + p)` relaxations), and every real-time read (`_last_sim_time`, `_waited`,
`_tray_dwell`, the recycle/despawn tests) is untouched in both forms. The stub proves it end to
end on the shipped gap band: the control stream, the shift-form stream and the cursor-form stream
have identical due/released/past, identical `late`/`along` and identical draw consumption over 10
slots (29 released, 108 gaps drawn), while the *un-anchored* lever is a different stream. The
credit is gated to the scattered pump (`supply.scatter and supply.stream` - `update`'s own gate),
so the pre-v9 fixed line cannot inherit a shift, and `fruits.py` is byte-untouched, which also
means the design's form cannot later be added on top and double-credit (pinned by source check).

**The placebo is preserved exactly.** The `FRUIT_READY_SKIP_HOLD` loop runs before the credit and
`debt = K - max(0, hold)`, so with `HOLD=230` the arm spends 230 ticks of dead time and the credit
is 0: gap *and* pump instant both shipped, i.e. the P9-A P arm replays. Put as arithmetic,
`sim + hold + credit = sim + K` either way - the pump phase is invariant to the hold and the hold
only spends wall time, which is the whole difference between (b) and the placebo.

**The readout** is one trailing field on the existing `[ready]` line, **only when the knob is on**:
`credit=<ticks>`, the session-cumulative integer sum (slot `k` on the acceptance should read
`k*230`). Knob off -> the line is byte-identical to the P9-A format (and the unanchored regex in
`logs/p9b/ready_summary.py` still matches). `fruits.py` was not touched, so the design's own
falsifier - the `[supply-diag]` `late=` band tracking arm A's instead of ramping 1.92 s/gap - is
readable unchanged.

**Offline verification** (all under `logs/p20i/`): `py_compile` clean; `scripts/selfcheck.sh`
**PASS 0 failures, 1 skipped** (the motion leg needs a run log); the seven pre-existing stubs
(two-line scope, confirm gate, P9-A skip predicate, flip resolution, regrasp arrival, arrive,
slide gate) **7/7 PASS**; the new `logs/p20i/check_resync.py` **PASS**: the knob resolves
(`"1"` only - `true`/`yes` do not arm it), the default-off path runs neither helper (booby-trapped)
and leaves the cursor at 0.0, the credit moves the cursor by exactly `ticks/120` s and accumulates
exactly (230 + 210 = 440; five skips 1150), the placebo credits 0, a partial hold credits the
remainder, and the end-to-end schedule model reproduces the control bit-for-bit while the debt
ladder reads 0.23/.../1.84 m at slots 0-7.

**Not measured here, stated plainly:** the acceptance no-harm (9/10 + `fingerprint: matches` + the
385/385 `[fruit]` identity vs `logs/p9a/90_acc_A_1.log`), the patch A 681/681, the two-line dense
442/442 + `190`, and every claim about the poll class, the wall or the outcome - those need the
battery's arm A/B/P. The offline evidence is that the default tree executes none of the new code
and that the shipped artifacts are byte-identical.

**Concurrent-tree note (a hazard for whoever reads the pin).** A second lane is editing
`tasks.py` in this checkout (`FRUIT_RELEASE_PAD_HOLD` / `FRUIT_RELEASE_FINGER_HOLD` in the release
pads, both defaulting to the shipped literal 3; the two FOREIGN hunks of
`logs/p20i/05_diff.patch`, excluded from `06_diff_mine_only.patch`). Its `TASKS_MD5` attempt
(`97a40185`) matches neither the base tree nor `HEAD` + its own hunks (`f0fa5d6e`), so this lane
set the pin to the hand-off md5 and recorded the whole diff; if that lane edits `tasks.py` again,
re-follow the pin (the new stub fails loudly until someone does).

**Named next:** the battery (design section 5 is unchanged): arms A / B (`SKIP=1 SKIP_DG=0.02
SKIP_RESYNC=1`) / P (`+HOLD=230`, expected byte-identical to the P9-A P), the acceptance at SEED
5/11/23 double-run, the patch battery, one diag run per arm, endpoint 1 (the presentation stream,
zero drift) as the mechanism verdict, the empty-poll count, the clean-gap p50 saving >= 1.5 s,
the pooled 3-seed placement per class, the seed-5 floor as the gate of record, and the no-harm set.
