# P58 phase 3a — cell A′: the supply triple on the SHIPPED per-pick interface

Measured **2026-10-28** on HEAD `fdc65d9` (the P57/P58 tree: `rl_env.py`
`ddcb7816`, `tasks.py` `c7eef701`, `fruits.py` `55921c46`, checkpoint `moe_v13s`
`61da390a` — phase 2 is docs-only, so the `src/` pins are phase 1's). Three runs,
one claim each, wall **1651 s** (`logs/p58/p3a/Ap_batch_outer.log`). **No
default flip, no `src/`/`configs/`/`datasets/` write, no checkpoint write, no
commit.** Registered in `logs/p58/PREREG_A_APRIME.md` **before the first run**.
Report: `logs/p58/Ap_report.txt` (`python3 logs/p58/Ap_report.py`), raw logs
`logs/p58/p3a/Ap_{77,101,202}.log`.

---

## 0. Verdict

**E2, E3 and E4 PASS; E1 FAILS on one boundary in one run — so the registered
all-pass condition is NOT met and this cell does not certify the flip.**
The cell answered Oracle 1's confound and the answer is the *opposite* of the
branch the registration was built to catch:

* **The triple carries the stock and the clock on its own.** With the shipped
  per-pick interface and no multi-pick episode, `on_belt` reads **9** pooled
  (control **5**, full stack **10**) and final cumulative `skipped` **41 / 36 /
  39** (control **104 / 107 / 105**, stack **40 / 36 / 38**). Phase 1's
  mechanism gains are the **triple's**, not the 15-pick episode's.
* **What the episode buys is the boundary, and the triple pays for it once.**
  One of A′'s 42 pick boundaries needed a **second 30-tick feed round**
  (`sel_gap` **170.2** ticks, seed 101, boundary 8→9) where the control's 42
  boundaries all read **139-141** — one starve in 42, not zero as registered.
  The successful selection there was a fruit at the **top** of the band
  (`along=+0.680` = `spawn_y`, just released): the boundary waited for the next
  release, it did not run out of fruit (`on_belt` 9-11 at that instant).

| endpoint | verdict | the number |
| --- | --- | --- |
| **E1** no selection-clock gap > 141 ticks | **FAIL** | 41/42 boundaries at 139-141; **1 at 170.2** (seed 101, one starved 30-tick round). Control: 42/42 at 139-141, **0** starved |
| **E2** stock + scheduler (the owner's object) | **PASS** | `on_belt` pooled median **9** (bar >= 8; control 5, stack 10), per run **10 / 9 / 10**; final `skipped` **41 / 36 / 39** (bar <= 60; control 104/107/105, stack 40/36/38) |
| **E3** `window>=1` at every selection | **PASS** | **45/45 = 100 %**, distribution `{1: 12, 2: 20, 3: 13}` (max 3 = the interlock's `_BAND_MAX` ceiling) |
| **E4** no new failure reason | **PASS** | A′ keys ⊆ phase-1 control keys ∪ the P43/P54 baseline; per-seed novelty **none**; the only failure class is `fruit did not follow the gripper` (the closed grip/`cnp` class) |
| **placed** | reported | **24/45** (left 3/23, right 21/22) vs control 33/45 (1/12, 32/33) and stack 30/45 (3/16, 27/29) — **arm-mix**, no rate claim |
| **wall** | reported | **34.07 s/pick** (1533 s / 45) = **+14.9 %** on the control's 29.66, against the stack's +15.9 % — at a **flat simulated span** (+0.3 %: 1833 vs 1827 ticks/pick) |

**Decision, stated the way the registration reads:** the first clause ("E1-E4
pass -> the triple is flippable for `direct`") is **not satisfied**, and neither
of the two other branches fires (E2 passes, E3 passes). The registration has no
branch for an E1-only failure, so the cell hands the owner a precise choice,
not a flip:

1. **Owner exception on the E1 letter.** Treat 1 starved boundary in 42 (2.4 %)
   as inside the intent — the boundary waited **0.25 s** for a fruit that was
   already on its way — and flip the three defaults. The stock, scheduler and
   reason endpoints are all at the stack's level.
2. **Spend the already-named free knob first.** The phase-2 map named
   `FRUIT_SUPPLY_BAND_MAX` 3 -> 4-6 and `FRUIT_SUPPLY_TARGET_FROM` 0.35 -> 0.40
   as "free, unmeasured, first response to any starve with a `skipped`
   increment" (`.slim/deepwork/p58-continuous-supply.md`, phase 2 outcome; the
   phase-3 tuning cell is conditional on exactly that). **That condition is now
   met** (E1's single event carries `skipped` +4 and the thinned window below),
   and re-running this same cell with `_BAND_MAX=4` or 5 is the cheap test of
   whether the starve is the ceiling's or the schedule's. Not run here: it is a
   second cell and this PREREG registers one.

## 1. The cell (as registered and as run)

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1
FRUIT_FEED_CADENCE=1 FRUIT_SUPPLY_BAND_INTERLOCK=1 FRUIT_SUPPLY_BAND_MAX=3
FRUIT_DIRECT_FEED=1
scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
    --presentation direct --episodes 15 --seeds <77|101|202>
```

`FRUIT_DIRECT_CONTINUOUS`, `FRUIT_POLICY_TRIGGER_ACQ` and `FRUIT_ARM_PARK`
**unset** — the shipped `direct` interface and the shipped ACQ/park defaults.
Every run prints `park=back(default)` and
`acq=on(speed=0.20,margin=0.60,cap=4.50,reach_margin=0.05)`, i.e. post-P43/P54.
All six construction checks hold: 15 picks per run, **0 `[cont]` rows**
(`cont_rows=0` in all three — the shipped interface, G2 does not fire), 15/15
`[bed-sel]` rows with `patch=on` and `grades=A:0.375,B:0.375,C:0.25`
(provenance, PREREG §4), `[feed]` rows **15 / 15 / 14** (the missing one is seed
202's episode 12, a `grasped=False` attempt that ended before its release
segment — the cadence ran on every attempt that reached a release), tree pins
identical before and after (`Ap_header.txt` vs `Ap_tree_md5_after.txt`), all
three exits **0**, no wedge, no retry (G1/G3 do not fire).

Controls are free and paired: **phase 1's arm A** (`logs/p58/p1/A_<seed>.log`,
same tree, same scenario, same seeds, `--episodes 15`, no triple) and **phase 1's
arm B** (the full stack, 15-pick episode). Nothing was re-run to produce them.

## 2. The table

Unit = one pick = one `[rl] episode ... success=` row. 15 picks per run, 45 per
arm.

| run | picks | placed (left/right) | `on_belt` med | `skipped` final | longest `sel_gap` | wall | s/pick |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A′ 77 | 15 | **7** (2/9, 5/6) | 10 | **41** | 141 | 512.1 s | 34.1 |
| A′ 101 | 15 | **7** (1/9, 6/6) | 9 | **36** | **170** | 509.4 s | 34.0 |
| A′ 202 | 15 | **10** (0/5, 10/10) | 10 | **39** | 141 | 511.6 s | 34.1 |
| **A′ pooled** | 45 | **24** (3/23, 21/22) | **9** | 41/36/39 | 170 (1/42) | 1533 s | **34.07** |
| control (P1 arm A) | 45 | 33 (1/12, 32/33) | 5 | 104/107/105 | 141 (0 starved) | 1334 s | 29.66 |
| stack (P1 arm B) | 45 | 30 (3/16, 27/29) | 10 | 40/36/38 | 80 (`[cont]`) | 1547 s | 34.37 |

## 3. The mechanism — where phase 1's gain actually lives

**The stock.** A′ sits **between** the two phase-1 arms and much closer to the
stack than to the control: `on_belt` **9** (mean 9.18) vs control **5** (5.18)
and stack **10** (9.58). So the 15-pick episode contributed **~0.6** bodies of
the ~4.4 the stack added — the triple did the rest. Everything else follows from
the same place: `live` **10 / 9 / 10**, `admitted` **median 4** (mean 3.96) vs
control 5 (4.98) — the P57 inversion (more fruit overall, fewer of them in the
window the catch can no longer reach) reproduces exactly.

**The clock.** Final `skipped` **41 / 36 / 39** against the control's
104/107/105 and the stack's 40/36/38: the cadence pump, on the per-pick interface
too, is the whole difference. The pump's own rows say the same thing:
**4 602-4 966 updates over 18 434-19 894 ticks** per 15 picks (~68-72 % of every
pick's ticks at stride 4, the phase-1 68-76 % band), **143-149 fruit released**
and **27-31 slots skipped** per run; `bed_rebased = 0` and `late_dropped = 0.0 s`
in every run, so the difference is the clock, not a re-basing artefact.
`lag` reads **-0.93 / -0.71 / -0.93 s** (the control's -0.92): the printed lag was
*already* current in the control — what moved is that the pump now runs every 4
ticks instead of only inside the reset, so the *backlog at each service* is small.

**The boundary, and the cost.** The per-pick reset is a fixed 140 ticks (30 feed
+ 3x30 teleport + 20 settle). A′'s 42 boundaries read **139-141 on 41 of them**
(the 6 x 141 are the 2-dp `t=` print quantization, measured on the control as
8 x 141 of 42; the realizable grid is `140 + 30k` so nothing can land at 145-168).
The **one** substantive event is seed 101 boundary 8→9 at **170.2** ticks: the
reset's first 30-tick round found no eligible candidate and a second round did.
The belt was **not** short at the preceding selection (the starved round prints
no row — PREREG §E3/A1.1: `on_belt` 9, `live` 10, `admitted` 3, `window` 2), and
the fruit it finally took was at `along=+0.680` = `spawn_y` — a slice that had
just been released. So the boundary waited **0.25 s** for the next release, and
`skipped` moved +4 across it (typical +1..+3).

**Why that is the interlock's own trade, not a supply shortage.** The interlock
caps the *approach band* at 3 and pushes stock upstream, which **thins the
station window**: mean `window` **2.02** vs the control's **2.57**,
`window == 1` at **12/45** vs **4/45**, max `window` **3** (vs the control's 10
selections at 4). A thinner window is exactly what makes a 140-tick boundary
occasionally have to wait one round, and it is the same "aperture is a
stock-depth ceiling" reading P33 measured on the two-line bed. The control never
shows the event (0/42) because its window is deeper (mean 2.57) — and the stack
never shows it because its boundary is 50/80 ticks, i.e. **the multi-pick episode
hides this trade rather than fixing the supply**.

**The wall is the pump, not the episode.** A′ costs **+14.9 %** wall per pick
(29.66 -> 34.07 s) at a **flat simulated span** (+0.3 %: 1 833 vs 1 827
ticks/pick), and the full stack costs **+15.9 %** at 1 847 ticks/pick. So the
15-pick episode contributed at most **~1 %** of the wall; the rest is the pump's
per-tick Python at stride 4 — the same attribution P33 made on the two-line
(+20.9 % wall = +4.4 % sim x +15.7 % per-sim-second). Phase 1 could not separate
these; A′ does.

**The failure class is the documented one.** A′'s only note is `fruit did not
follow the gripper` (1 `grasped=False`, the rest carried-not-placed) — the closed
grip/`cnp` class of `logs/p42/SIM_LIMIT.md`, no new key in any seed (E4). The
pooled placed count (24/45) is lower than both phase-1 arms **because the arm mix
moved**, not because an arm degraded: A′ drew **23 left attempts of 45** (control
12, stack 16), and the left is 3/23 = 13 % (the closed class) while the **right —
the arm the belt feeds — reads 21/22 = 95.5 %** against the control's 32/33 =
97.0 % and the stack's 27/29 = 93.1 %. Per AGENTS §2 and P58 §4.1 this is a
count with an arm split, **not a rate delta**.

## 4. What this cell does and does not show

* **It does show** that phase 1's two headline mechanism numbers (`on_belt`
  5 -> 10, `skipped` 105 -> 38) are the **triple's**, not the multi-pick
  episode's, and that the wall cost is the pump's, not the episode's. Oracle 1's
  precondition is therefore answered on the mechanism.
* **It does not certify the flip**, because the per-pick boundary is not free:
  the interlock's window thinning costs **1 starved boundary in 42**, which the
  registered E1 bar (`<= 141` in every run) forbids and the control does not
  exhibit.
* **It does not attribute the event beyond the reading above.** One event cannot
  separate "the `_BAND_MAX=3` ceiling" from "the patch slice spacing at that
  point in the schedule" — both predict a ~0.25 s wait. The registered
  discriminator is the free `_BAND_MAX` 3 -> 4-6 cell (§0 option 2), and a
  `FRUIT_SUPPLY_TARGET_FROM` 0.35 -> 0.40 tweak addresses the 0.049 m dead sliver
  the phase-2 map named.
* **Not covered:** the hybrid canary (`60_eval_policy.py` never constructs
  `SortingRLEnv`), the two-line scheduler (`CoopSession` installs its own pump;
  the cadence is single-arm scoped), any store collected under the triple (no
  `--record`), and the tuning cell itself.
* **Three runs of a non-reproducible loop.** The direction holds 3/3 on
  `on_belt` and `skipped` (every run near the stack, every run far from the
  control); E1's event is 1/42 and is reported as an event, not a rate.

## 5. Files

`logs/p58/PREREG_A_APRIME.md`, `logs/p58/run_aprime.sh` ->
`logs/p58/p3a/Ap_batch_outer.log`, `logs/p58/p3a/Ap_{77,101,202}.log`,
`logs/p58/p3a/Ap_header.txt`, `logs/p58/p3a/Ap_tree_md5_after.txt`,
`logs/p58/Ap_report.py` -> `logs/p58/Ap_report.txt`, this file.
**Nothing was flipped, edited in `src/`, recorded to a store, or committed.**
