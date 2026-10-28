# P59 phase 2 pre-registration: the catch-margin arms (written before any run)

## The question

P58's shipped profile keeps 2-3 bodies in the catchable window (`window` mean
**2.38** at cap 4) against the control's **2.57** - but the control's depth is
bought by the per-episode re-stock (the timed refresh the owner rejected). The
open question is whether one of the two **substitute** supply knobs closes the
0.19 gap *continuously*, without losing the zero-starve property.

## The arms (one variable each, never both - `logs/p58/GEOMETRY.md` §1.3)

| arm | change from the shipped profile | why it could help |
|---|---|---|
| **A: cap 5** | `FRUIT_SUPPLY_BAND_MAX=5` | the band holds 0.38 m x ~8.9/m = 3.4 bodies by design density, so 5 leaves headroom for the patch's partners |
| **B: upstream edge** | `FRUIT_SUPPLY_TARGET_FROM=0.40` | deletes the 0.049 m dead sliver below the 0.399 m catch floor (12.9 % of the counted window) |

Both are env-only; the shipped profile stays the control (the P59 phase-1
logs, 45 selections).
Seeds 77/101/202, `--episodes 15`, one claim per run, logs `logs/p59/p2/{A,B}_{seed}.log`.
Scenario = the P58 one (patch sheet, balanced mix, trigger arrival 0.9,
`FRUIT_DYNAMIC_PICK=1`, `FRUIT_BED_DIAG=1`, policy seed 11, `moe_v13s`); **no**
`FRUIT_DIRECT_CONTINUOUS`, ACQ and park unset (P54/P43 defaults).

## Endpoints (registered)

* **E1 (primary)**: `window` mean **>= 2.57** (the control's post-burst depth) with
  `window==1` **<= 4/45** (the control's share) - i.e. the margin is recovered.
* **E2**: **zero** starved feed rounds (`sel_gap >= 169`) in every run.
* **E3**: final `skipped` **<= 20** (the shipped profile reads 8/4/9).
* **E4**: no new failure reason (113's normalisation); placed **reported only**.
* **E5**: wall **reported only** (a harness cost of live-body count; P58:
  0.0162 -> 0.0194 s/tick at 6 -> 12 bodies - never a throughput reading).

## The reading rules (P59 gate 1, binding)

1. **`placed_so_far` under-reports by one** (printed before the pick's outcome);
   quote the summary line, never the running counter.
2. **`gap_ticks_mean` is censored**: the starve path returns before the gap is
   appended, so an arm that starves *lowers* its mean. "No starvation" is
   asserted from the **absence** of `waiting for a candidate` / `no candidate`
   lines, never from the mean.
3. **`supply_skipped` is not the drop counter** on the non-bed path (the
   depth-capped release re-bases `_next_release` silently); copy the P58 lesson.
4. **`on_belt` is not a catch metric** (`on_belt = admitted + below_window`;
   at cap 4, 54 % of candidate rows are past the 0.180 window floor).
5. **Cap adoption**: if an arm moves the cap default, the P59 phase-1 film
   becomes pre-phase-2 and must be re-shot (`logs/p59/run_p1.sh 4`).

## Decision rule

Adopt the arm that meets E1-E4 **and** beats the control on `window==1`; if both
meet it, adopt the one with fewer bodies (`on_belt`) because wall tracks the
live-body count; if neither meets E1, change nothing and record the residual
(the aperture ceiling is then the named limit, as P33/P56 measured).
