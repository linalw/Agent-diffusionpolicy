# P99 CENSUS - where the two-line's wait actually is, and what candidate planning could move

Registration: `logs/p99/PREREG.md` (md5 `0acc5692e6b22f0879f7abb40d8519f5`,
pinned 2026-11-02 22:46:03, before any census cell was read).
Readouts: `python3 logs/p99/census.py logs/p99/{C5,C6}.log` (-> `census.txt`),
`python3 logs/p99/p99_report.py [--check]` (-> `p99_report.txt`), per-slot tables
`slots_C5.csv` / `slots_C6.csv`. Cells: `logs/p99/run_p99.sh` (census),
`logs/p99/run_p99_grade.sh` (the pricing A/B).

## 0. The answer, in one line and in numbers

**The candidate planning is not a lever on this line: the choice is forced
(37 of the 40 selection instants had exactly **one** own-grade fruit at/above
the pick floor, and the other 3 had two), the delay-aware rule is already the
shipped rule (0.000 s of headroom on 40/40), and every second a different
assignment could save is a cross-lane second - i.e. a fruit of the *other*
arm's grade, which on this cell physically lands in the wrong output lane.**

| reading | seed 5 | seed 6 | pooled |
| --- | --- | --- | --- |
| placed | 17/20 | 12/20 | 29/40 |
| inter-placement interval | **9.38 s** | **11.08 s** | - |
| per-attempt slot dead time (park + feed + polls + gate) | 2.94 s | 4.62 s | - |
| of which **starvation** (starved polls) | 0.17 s | 0.86 s | - |
| the arm's **in-attempt arrival wait** | 1.62 s | 1.49 s | - |
| **(i) cross-lane** convertible, arrival wait | 1.154 s/pl. | 1.406 s/pl. | **1.258 s/pl.** |
| **(i') cross-lane** convertible, starved polls | 0.147 s/pl. | 1.250 s/pl. | **0.603 s/pl.** |
| **(ii) delay-aware** convertible | 0.000 s/pl. | 0.000 s/pl. | **0.000 s/pl.** |
| **(iii) joint / park-gate** convertible | 0.035 s/pl. | 1.233 s/pl. | **0.531 s/pl.** |
| candidate planning total (i)+(i') | 1.30 s/pl. | 2.66 s/pl. | **1.862 s/pl. = 18.2 % of the interval** |

The 18.2 % is the **price of grade-pure routing**, not a free lever: it is
paid because the left arm sorts grade A and the right grade B, and each arm's
output belt *is* that grade's bin (left = lane 0 = A, right = lane 1 = B;
`tasks.py:11688-11705`: "the arm cannot change lanes mid-attempt ... the sort
error is recorded"). Section 5 measures what happens when the fallback is
switched on with the shipped `FRUIT_GRADE_ROUTING=0` - the starvation goes to
zero, the interval gets **worse** at both seeds, and 17 of 40 fruit go to the
wrong lane.

## 1. Method, and the two proofs the numbers rest on

**The instrument.** The shipped records print the slot chain but not the
attempt's end, and `[bed-sel]` (`FRUIT_BED_DIAG=1`) prints only counts. P99 adds
**one reporting block**: `FRUIT_BED_DIAG=2` prints, after the shipped summary
row and from the same `diag` list `select_target` already fills, the **selector
floor** of that decision and **one row per live fruit** with its
`idx/grade/along/x/z/r` and the first predicate that refused it
(`tasks._biarm_bed_census`). No read is added to any control path, nothing is
computed differently, and `=1`/unset are byte-unchanged. The attempt end and the
park split come from `FRUIT_BIARM_PARK_TRACE=1` (proven line-neutral by P84:
`D5` = `logs/p80/T20.log` 865/865).

**Proof 1 - the cells are the shipped branch, byte for byte.** Both census cells
replay their same-seed P94 record with the instrument's own rows dropped
(`p99_report.py --check`, `census.py --same`):

```
   C5 vs logs/p94/T5.log: 974/974 [fruit] lines, IDENTICAL
   C6 vs logs/p94/T6.log: 970/970 [fruit] lines, IDENTICAL
```

So P98's revert is inert on this cell (the pre-pose knob resolves off) **and**
the whole instrument - **279 + 515** `[bed-sel]` rows and 60 park rows
per cell - moves nothing. A 1-attempt smoke pair had already read 78/78 identical.

**Proof 2 - the derivation reproduces the published numbers.** The attempt end
is `station-acquired + result.sim`, the placement instant is the attempt end
minus the `[cycle]` `return`+`end` blocks, and the interval recomputed from
those reproduces every published value to the digit: `logs/p94/T5.log` ->
**9.37 s**, `T6` -> **11.08**, `N5` -> **10.59** (`logs/p94/RESULTS.md` §5),
`logs/p84/D5.log` -> **10.77 s** (`logs/p80`). The park split calibrates to a
fixed **2.5 s** motion and a **0.25 s** feed gap, with every gap closing to
±0.05 s.

**Guards.** Landing: 17/17 and 12/12 payload-present releases read
`placed=True (on/next to output belt N)`, and the belt index equals the arm
(9 on belt 0 / 8 on belt 1 at seed 5). Grade ledger: **0 cross-lane fruit in
both cells** (left A=10, right B=10 / left A=11, right B=9), i.e. the shipped
routing is pure. Motion budgets and `selfcheck.sh` are in §7.

## 2. (A) The wait the arm paid, per slot

Per attempt slot, seconds, both arms pooled (`census.txt`):

| cell | arm | slots | starved polls (n) | park-gate | park-motion | feed | polls (s) | dead | attempt span |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C5 | left | 9 | 5 | 0.00 | 2.49 | 0.28 | 0.28 | 3.04 | 15.01 |
| C5 | right | 9 | 1 | 0.07 | 2.46 | 0.27 | 0.06 | 2.84 | 15.16 |
| C5 | all | 18 | 6 | **0.03** | **2.47** | **0.27** | **0.17** | 2.94 | 15.08 |
| C6 | left | 10 | 16 | 0.00 | 2.46 | 0.25 | 0.80 | 3.51 | 13.46 |
| C6 | right | 8 | 15 | 1.85 | 2.97 | 0.25 | 0.94 | 6.01 | 14.04 |
| C6 | all | 18 | 31 | **0.82** | **2.69** | **0.25** | **0.86** | 4.62 | 13.72 |

Read it as: **the slot-loop wait is dominated by the park return (2.5 s of
motion per attempt) and the feed gap (0.25 s), not by waiting for fruit.** The
starvation term is 0.17 s/attempt at seed 5 (0.9 % of the interval) and
0.86 s/attempt at seed 6 (3.9 %). The park-gate term - the arm blocked on the
*other* arm's payload clearing its station box - is 0.03 s at seed 5 and 0.82 s
at seed 6 (the right arm waits 1.85 s/attempt there).

Two starvation populations, and they must not be pooled:

* **the batch prime** - 6 polls on each seed before the arm's first attempt
  (t = 13.4-16.4 s), the belt's first own-grade fruit not yet arrived. 3.0 s
  once per batch, i.e. 0.17 s/placement;
* **in-chain starvation** - 6 polls at seed 5, 31 at seed 6, over 18 slots each.

**The arrived-too-late class is the mechanism.** `census.py` splits every live
fruit into own-grade-at/above-floor, cross-lane-at/above-floor,
inside-the-catch-floor, and ineligible. Per decision:

| cell | decisions | live (mean) | own-grade ≥1 | own-grade mean | cross-lane ≥1 | cross mean | inside the floor | ineligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C5 | 32 | 6.7 | **20/32** | 0.66 | 27/32 | 1.19 | 2.34 | 1.81 |
| C6 | 57 | 7.0 | **20/57** | 0.39 | 53/57 | 1.44 | 2.70 | 1.70 |

So the belt is stocked (7 live fruits at the decision instant) and the arm still
has nothing its own grade can catch in 12/32 and **37/57** decisions - and in
~2.5 of those the own-grade fruit is *already inside the catch floor*, i.e. it
will be past the pick point when the 1.5 s setup ends. **The starvation is a
grade-rhythm mismatch with the arm's cycle, not a shortage of fruit.**

## 3. (B) The candidate read: was there something a different assignment could take?

`window ≤ 1` on **37 of 40** selections (19/20 and 18/20): the arm's own-grade
set at/above the floor holds exactly **one** fruit, so there is no choice to
optimise - the rule's "take the nearest own-grade fruit above the floor"
(`tasks.py:8111-8115`: `usable` sorted ascending, pure routing -> `usable[0]`)
is the only candidate.

The three mechanisms, measured (`census.txt` section [B]):

* **own-lane empty while a cross-lane fruit was at/above the floor**: 10/32
  decisions at seed 5, **35/57 at seed 6** (61 % of all decisions). At those
  instants the belt held a fruit the arm could physically catch, and the only
  thing refusing it was its grade.
* **cross-lane fruit arrives sooner than the chosen own-grade one** (both
  above the floor): 24/32 and 49/57 decisions. Mean earlier arrival 1.15 s
  (seed 5) / 1.41 s (seed 6) per placement.
* **delay-aware**: the chosen fruit *is* the nearest own-grade fruit in
  **40/40** selections to 0.000 s. This mechanism has no headroom on this line
  by construction, and the census confirms it empirically rather than assuming
  it (the record's `logs/w8/R3_RESULTS.md` prior).
* **joint**: the only cross-arm coupling in the loop is the park gate
  (`_biarm_park`'s `payload_clear` wait): 0.03 s/attempt at seed 5, 0.82 s at
  seed 6. The capture token and the start gap are default off and were not
  re-measured (W2 measured the start gap negative: a 4 s gap cost the span
  ~1:1).

## 4. (C) The convertible seconds, and the share of the interval

Per placement, pooled over the two seeds (29 placements):

| mechanism | s/placement | share of the 10.2 s mean interval |
| --- | --- | --- |
| (i) cross-lane, in-attempt arrival wait | **1.258** | 12.3 % |
| (i') cross-lane, in-chain starved polls | **0.603** | 5.9 % |
| (ii) delay-aware | **0.000** | 0.0 % |
| (iii) joint / park-gate | **0.531** | 5.2 % |
| candidate planning (i)+(i') | **1.862** | **18.2 %** |
| *memo*: batch-prime polls of the same kind | 0.172 | 1.7 % |

**(ii) is zero and (iii) is not candidate planning.** (iii) exists because the
arms overlap - which is the throughput mechanism itself (P80: the two-line is
1.88x the single arm on the sim clock) - and the block is a *clearance*
constraint on the park return, whose levers were measured in P43/P69/P90 (the
workstation map closed at 0/588 cells). So the candidate-planning question is
(i)+(i') = 1.86 s/placement, and the whole of it is **cross-lane**.

## 5. The pricing A/B: what cross-lane is actually worth

`FRUIT_GRADE_ROUTING=0` is the shipped V2 fallback (grade preference with an
any-grade fallback): it takes the own grade when one is available and otherwise
the nearest any-grade fruit. Two cells, same instrumentation, same seeds
(`run_p99_grade.sh`, `G5`/`G6`). **This is a pricing measurement, not an
adoption candidate** - with one output belt per arm a cross-lane pick lands on
the arm's own lane, i.e. it is a sort error.

| seed | arm | placed | interval | sim span | window placed/min | batch placed/min | dead time | starved polls | cross-lane fruit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | C | 17/20 | 9.38 | 181.1 | 6.40 | 5.63 | 2.94 | 6 | **0/20** |
| 5 | G | 17/20 | **10.01** | **174.3** | **5.99** | **5.85** | 3.39 | **0** | **9/20** |
| 6 | C | 12/20 | 11.08 | 182.6 | 5.42 | 3.94 | 4.62 | 31 | **0/20** |
| 6 | G | 13/20 | **11.66** | **166.9** | **5.15** | **4.67** | 3.29 | **0** | **8/20** |

**What the fallback does, exactly as the census predicted, and why it does not
pay:**

* **the starvation is deleted** - 37 in-chain starved polls across the two
  census cells become **0/0**; both arms always have work;
* **the arrival wait halves** - 1.62 s -> **0.67 s** at seed 5 (the arm takes a
  nearer fruit), and `window <= 1` falls from 19/20 to 5/20 because the choice
  is finally a choice;
* **the park gate pays for it** - the arm blocked on the other arm's payload
  clearing its station box rises 0.03 -> **0.62 s/attempt** at seed 5
  (0.82 -> 0.54 at seed 6): with both arms never idle, their station dwells
  collide, which is the intra-arm clearance constraint the shipped starvation
  was *absorbing*;
* **the interval is worse at both seeds** (+0.64 s = +6.8 %, +0.58 s = +5.3 %)
  and the placement-window rate is worse at both (6.40 -> 5.99, 5.42 -> 5.15);
* **the batch span is better at both** (181.1 -> 174.3, 182.6 -> 166.9) and so
  is the batch rate (5.63 -> 5.85, 3.94 -> 4.67) - the two denominators
  disagree in sign, which is exactly why the read rules demand both;
* **the count is a draw** (17 -> 17, 12 -> 13; pooled 29 -> 30 of 40);
* **it is mis-sorted**: 9 of 20 and 8 of 20 attempts take a fruit of the other
  arm's grade and place it on the arm's own belt; the placement trace confirms
  every one of them lands `on_belt` - on the **wrong** belt (10 left releases to
  belt 0, 7 right to belt 1 at seed 5, i.e. the arm's own lane, always);
* and at seed 6 it also loses **2 payloads upstream** (`release_bottom = -184
  mm`, the loaded-slide class - the two-line's stranding class, not a landing
  regression).

**The transferable sentence: the wait is not the interval.** Removing ~1.1 s
per attempt of pure fruit wait (0.95 s of arrival + 0.17 s of polls at seed 5)
took **0.57 s off the per-attempt cycle (18.02 -> 17.45 s) and 0.64 s *onto* the
interval**, because
the interval is the *sequencing* of two overlapped arms, not the sum of their
waits: seed 5's placements bunch in pairs (gaps 4.5 / 1.8 / 0.4 s between the
two arms, then 16-18 s), and G5's are evenly spread (p50 13.00 -> 11.70 s,
mean 9.38 -> 10.01 s). A wait that one arm pays is often the slack the other
arm's sweep needs.


## 6. What the interval is, then

`interval` is the pooled inter-placement time of two overlapped arms. Per arm
the attempt cycle is `span + dead`, and the census's account heads are:

| head | seed 5 | seed 6 | convertibility |
| --- | --- | --- | --- |
| profiled legs + the descent's scheduled wait | 13.46 s | 12.23 s | measured negative in P44/P86/P88/P89/P91 |
| **in-attempt fruit-arrival wait** | 1.62 s | 1.49 s | cross-lane only (see above) |
| park motion | 2.47 s | 2.69 s | a scene/return-path lever (P69/P90 closed it) |
| feed gap | 0.27 s | 0.25 s | fixed 30 ticks |
| starved polls | 0.17 s | 0.86 s | cross-lane only |
| park gate | 0.03 s | 0.82 s | overlap price |

So the owner's "the interval looks long" is, in order: **the attempt span**
(15 s of profile, 85 % of the cycle), **the park return** (2.5 s), and then the
fruit wait (1.5-1.6 s, all of which is grade purity). Nothing in the *choice*
of fruit is left: the choice is forced, and the one rule that could choose
differently (cross-lane) is a sort error.

## 7. Guards

| guard | reading |
| --- | --- |
| landing (census cells) | 17/17 and 12/12 payload-present releases `placed=True`, belt index = arm |
| landing (pricing cells) | G5 17/17; G6 13/13 payload-present of 15 release rows, the other 2 `release_bottom = -184 mm` (payload lost upstream, reported separately per P86's convention) |
| grade ledger (census cells) | 0 cross-lane fruit; left A=10/11, right B=10/9 |
| grade ledger (pricing cells) | **9/20 and 8/20 cross-lane** - the price, by construction |
| motion budgets | the census cells are byte-identical to `logs/p94/{T5,T6}.log`, whose budgets are P94's (0 legs over; `T6`'s leg 12 at 0.164/0.160 is that record's own documented branch leg). The pricing cells are a moved branch: `105 --min-success-rate 0.0` reads **PASS** on both (budgets only; G5 worst descent 0.86x, G6 inside every descent bound) |
| `scripts/selfcheck.sh` | PASS, 0 failures, 1 skipped |

## 8. What this closes, and what it does not

**Closed:** the "is the inter-placement interval caused by waiting for fruit"
question. It is not: 18.2 % of the interval is the *most* any candidate rule
could touch, all of it cross-lane, and swapping it on (section 5) deletes the
starvation and makes the interval 5-7 % worse while mis-sorting 42 % of the
fruit. The record's priors are confirmed and now measured on the shipped tree:
the delay-aware form is already shipped (0.000 s), the supply is not starving
the loop (0.17-0.86 s/attempt of polls, all of it grade-rhythm), and the
`logs/w8/R3_RESULTS.md` "the 1.5 s floor IS the measured setup" reading extends
to "the pick is a forced choice".

**Not closed** (and not touched): the **park return** - 2.5 s of motion per
attempt, ~13 % of the interval - is the largest single dead term and it is a
return-path/clearance object (`_ready_transit` sweeping through the station
volume), not a planning one. Its levers were measured in P43 (park pose), W2/W3
(start gap, park bias), P69/P90 (workstation) and all closed; what has never
been tried is a **shorter return path** (a ready pose on the station side of the
body) - which P32's `FRUIT_PREPARED_NEXT`/R3's hot-arm both approached from the
scheduling side and both measured as non-binding.

