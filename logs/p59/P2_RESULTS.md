# P59 phase 2 results — the catch-margin arms (both fail E1; the bar is not adjudicable)

**Verdict (Oracle 2): KEEP cap 4. No shipped default change.** The lane closes as
**non-binding**, not as "cap 5 lost": nothing behavioural moves between cap 4 and
cap 5, and E1's 2.57 bar is a third estimator that matches no row of the table.

## The table (45 `[bed-sel]` blocks per cell, pooled)

| cell | `window` mean | `==1` | `==0` | starved (`sel_gap>=169`) | final `skipped` | `on_belt` | `admitted` | below-window/block | placed (report only) | wall s/pick |
|---|---|---|---|---|---|---|---|---|---|---|
| burst control (pre-P58) | **2.600** | 4/45 | 0 | 0/42 | 104/107/105 | 5.22 | 5.00 | 0.20 | 33/45 | 444.8 |
| **control cap 4 (shipped)** | **2.378** | 9/45 | 0 | **0/42** | 8/4/9 | 10.93 | 4.69 | 6.24 | 28/45 | 531.1 |
| **A: `BAND_MAX=5`** | **2.533** | **4/45** | 0 | **0/42** | 6/11/4 (21) | 11.82 | 5.33 | 6.47 | 27/45 | 530.2 |
| **B: `TARGET_FROM=0.40`** | 2.267 | 10/45 | 0 | **0/42** | 3/2/3 (8) | 11.62 | 5.09 | 6.49 | 29/45 | 519.9 |

## Why cap 5 does not ship

1. **E1's bar is mis-footed.** 2.57 is the burst cell pooled over **51** blocks - it
   includes the 5-pick aborted run (`logs/p58/p1/A_77_aborted_5picks.log`); every
   other cell is 45 blocks, and on 45 the burst reads **2.600**. The bar sits
   **0.03 below its own cell** and matches no row.
2. **The mean leg has no power at n=45.** A's `window` sd is 0.859 -> SE 0.128,
   95 % CI **[2.282, 2.784]**; the bar sits **0.26 SE inside** A's own interval,
   and two such arms need |delta| >= 0.50 to separate at 95 %.
3. **Nothing behavioural moves.** `window==0` 0/45 and starved rounds 0/42 in all
   four cells; `sel_gap` is the **identical multiset** for cap 4 and cap 5
   ({139x8, 140x25, 141x9}); `skipped` totals **21 = 21**; placed 27 vs 28;
   wall 530.2 vs 531.1 s/pick. Cap 5 moves a counter that no behaviour in this
   scenario reads.
4. The one direction-consistent signal - the marginal share 9/45 -> 4/45, non-worse
   in 3/3 seeds, per-run exact p = 0.125, pooled Fisher p = 0.24 - is real-looking
   and **not resolvable** at this n. It is recorded, not acted on.

## Why `TARGET_FROM=0.40` is rejected mechanically

`window` counts only `usable`/`chosen` (`tasks.py:5515`), so the "below catch floor"
rows live in `admitted`, never in `window`; the arm's registered "12.9 % dead sliver"
rationale targeted the report's **re-derived occupancy**, not the endpoint. On the
real counter B reads **2.244 vs 2.711**, while `below catch floor` **rises 2.31 ->
2.82 per block**: it moves stock **into** the sliver it meant to delete. Its
`skipped` 8 vs 21 at zero starvation is the recorded residual trade.

## The residual (verbatim, per Oracle 2)

> the shipped profile's instantaneous window depth is **2.378 (9/45 marginal
> blocks)** against the pre-P58 burst control's **2.600 (4/45)**, and that gap
> produces **no measurable difference** in `sel_gap`, starvation, `skipped` or the
> placed count in any of the four cells; the registered bar (2.57) is a 51-block
> pool including an aborted run and is 0.26 SE inside cap 5's own 95 % interval,
> so **no depth mean at n=45 ranks the arms**.

## What a reopening needs

1. a **same-tree 45-block control** (this registration named "the P59 phase-1 logs,
   45 selections" - phase 1 ran 2/1/continuous-10/continuous-8 picks and never
   produced one; the substitute was the cross-tree P58 phase-3b cell, `rl_env`
   `ddcb7816` vs `1b1e5cdf`, whose cap-4 membership rests on `A2_header.txt`
   because it predates the `[supply] direct profile` row);
2. a **behavioural endpoint** (`sel_gap`, a starve, or a skip), never a depth mean.

**Cap 6 is predicted flat** (dose-response saturated: cap 3 -> 4 = +0.36, 4 -> 5 =
+0.156; the aperture is bounded by the 0.399 m catch floor and P33's ~1.8 eligible
per grade-pure lane), and it must not be registered on a depth mean.

## Artifact

`logs/p59/p2_report.py` runs **exit 0** on its six logs (the arm check matches the
`[supply] direct profile` row, not the scatter row) and writes
`logs/p59/p2_report.txt`; the table above is its output.
