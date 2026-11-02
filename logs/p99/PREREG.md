# P99 PREREG - is the candidate planning between the feeder and the arms a lever?

Pinned **before** the two census cells (`logs/p99/{C5,C6}.log`) are read. The
cells were started at 22:43:35 (`C5`) to produce the per-fruit candidate sets
the shipped records do not carry; at pin time only the 1-attempt smoke's first
decision (`/tmp/opencode/p99_smoke.log`) and the offline slot chains had been
looked at.

## 0. The question

The owner: *"can the candidate fruit planning between the feeder and the arms
raise efficiency, because the inter-placement interval looks long?"*

The record's priors, quoted so this phase either confirms or refutes them:

* the wait is **arrival-bound** - `logs/w8/R3_RESULTS.md`: the adaptive
  selection lead is bit-identical to the shipped 1.5 s because the shipped floor
  **is** the measured setup, and the tight lead binds and is worse;
* the supply is **not starving** the line - `logs/p58`/`logs/p59`: 0/42 starved
  feed rounds; `logs/p80`: 44 starved polls but **0 lost slots**;
* the two-line selector **already takes the nearest fruit of its own grade**
  at/above `_dynamic_select_floor()` (`tasks.py:8111-8115`: `usable` sorted
  ascending, `prefer_lane` + pure routing -> `usable[0]`), i.e. the delay-aware
  rule is the shipped rule for this line.

So the census must answer three things with numbers, per station slot:

1. **the wait the arm paid**, split into park-gate / park-motion / feed /
   starved polls / selection;
2. **the candidate set** at the decision tick, and how often the arm's own lane
   had nothing at/above the floor while a cross-lane fruit did;
3. **the convertible seconds** per mechanism, as a share of the interval.

## 1. The census layers (offline first)

**L1 - the slot chain, every record.** The two-line worker's per-slot rows are
`[biarm] <arm>: station acquired at t=`, `... no eligible fruit; station
released`, `[biarm] result <arm> ... sim=`, and the `[cycle] attempt N` blocks;
`FRUIT_BIARM_PARK_TRACE=1` supplies the attempt-END timestamp (`park wait
start`) and the gate/park split. Attempt end = `acquired + sim`, placement
instant = attempt end minus the `[cycle]` `return`+`end` blocks. **This
derivation is validated against the published numbers before any claim**:
`logs/p94/T5.log` -> interval **9.37 s**, `T6` -> **11.08**, `logs/p94/N5.log`
-> **10.59** must reproduce `logs/p94/RESULTS.md` §5 to the digit, and
`logs/p84/D5.log` -> **10.77 s** must reproduce `logs/p80`/`logs/p84`'s D5.

**L2 - the candidate set, the two P99 cells** (`FRUIT_BED_DIAG=2`: one row per
live fruit with `idx/grade/along/x/z/r` and the **first predicate that refused
it**, plus the selector floor at that decision). Reporting only; the neutrality
proof is a replay of the cell's `[fruit]` stream against the same-seed P94
record with the instrument's own rows dropped (`logs/p99/census.py --same`).

**L3 - the in-attempt arrival wait**, which is where a slot that *has* a target
still waits: `logs/p91/AUDIT.md` measured the `descent` block as
arrival-wait + scheduled-wait + leg (2.17 + 0.59 + 0.74 s on `logs/p87/T5.log`).
The census re-reads it on the shipped cell from the chosen fruit's own `along`
(`arr = (along - floor)/v + 1.5 + 0.03/v`, so arrival order **is** `along`
order at a decision) and reports it; the block split itself is quoted from
`logs/p91`, not re-derived.

## 2. The counterfactuals, defined before the read

For each decision at time `t`, with the arm's own grade `G` (left `A`, right
`B`, the shipped pure routing) and the floor `f`:

* `own` = every live fruit of grade `G` that passes the non-grade predicates
  (`z` within `[belt_top-0.02, belt_top+0.12]`, `2r <= 0.08`) and `along >= f`;
  `best_own` = its minimum `along` (the earliest arrival).
* `cross` = the same test with grade `!= G`; `best_any` = the minimum `along`
  over `own ∪ cross`.
* The **non-grade predicate classes are reported as counts** (`below belt`,
  `output belt`, `too big`): on the main belt they must be empty for supplied
  instances (the pool's largest fruit is 6.9 cm), so a non-empty class is a
  finding, not a filter.
* **(i) cross-lane**: convertible = `Σ max(0, arr(best_own) - arr(best_any))`
  over decisions where `best_any` is cross-lane, plus **0.5 s per starved
  poll** at which a cross-lane fruit was at/above the floor (the poll's own
  cost, `max(60, gap_ticks)` ticks).
* **(ii) delay-aware**: convertible = `Σ max(0, arr(chosen) - arr(best_own))`.
  The shipped rule takes the nearest, so this is **predicted 0** and a non-zero
  value would be a bug, not a lever.
* **(iii) joint**: convertible = `Σ` park-gate wait (the ticks the arm spent
  blocked on the other arm's station/payload). The capture token and the start
  gap are default off and are not re-measured here.

## 3. The decision rule

Let `C` be the pooled (2-seed) convertible seconds **per placement**:

```
C = (C_i + C_ii + C_iii) / placed
```

* **`C >= 0.5 s/placement`** on the pooled read -> the census names a gap, and
  the mechanism with the largest contribution is built as a **default-off**
  selector knob in the two-line decision site, with its own PREREG (md5 pinned
  before its runs), `ATTEMPTS=20`, **2 seeds of which at least two are fresh**
  (P93's rule), endpoints = slot wait / starved polls, then the interval
  (pooled and per-arm), both `placed/min` denominators, the wall, the class
  split and the grade-purity ledger.
* **`C < 0.5 s/placement`** -> **no lever is built**. The write-up says the
  candidate planning is not the lever and names what the interval *is*:
  `interval = attempts/placement x attempt span + idle` on the shipped cell,
  with the slot-loop dead time (park motion + feed) and the in-attempt arrival
  wait as the two account heads.
* **Special case, decided now**: if the whole of `C` is **mechanism (i)** -
  cross-lane - then the lever is a **routing-semantics change** (the owner's
  W3/R5 pure-grade decision: left arm grade A only, right arm grade B only,
  grade C never selected) and **not a free lever**. It may be measured with the
  existing `FRUIT_GRADE_ROUTING=0` knob, but it is **not shipped** and is
  reported as the price of the semantics, with the per-lane grade ledger.

## 4. Guards (any cell)

* the landing: `FRUIT_PLACE_TRACE`'s `on_belt` on every payload-present
  release;
* the motion budgets: the per-leg descent `|v|max` against the shipped
  budget, never re-tuned (`AGENTS` §2);
* `scripts/accept.sh` on the final tree (`fingerprint: matches` against
  `configs/motion_reference.json`; the rate-only FAIL at the standing branch is
  expected);
* `scripts/selfcheck.sh` at the end.

## 5. What would falsify the record's prior

The prior is "the wait is at its floor". It is **refuted** for a mechanism if
that mechanism's convertible seconds clear 0.5 s/placement, and **confirmed**
if all three are below it. A starved poll is *not* a cost by itself: it only
counts when the arm that polls is the one the cell is waiting for - so the
report carries both the raw poll seconds and the slot-chain share.
