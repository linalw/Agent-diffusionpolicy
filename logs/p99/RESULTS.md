# P99 RESULTS - the candidate planning is not the lever; the wait is not the interval

Registration: `logs/p99/PREREG.md` md5 `0acc5692e6b22f0879f7abb40d8519f5`,
pinned 2026-11-02 22:46:03, before any census cell was read. Commands:
`logs/p99/run_p99.sh` (census cells), `logs/p99/run_p99_grade.sh` (pricing);
readouts `logs/p99/census.py` -> `census.txt`, `logs/p99/p99_report.py
[--check]` -> `p99_report.txt`, per-slot tables `slots_{C5,C6}.csv`; the
gate driver `bash logs/p99/gates.sh` -> `gates.out` (rc=0).

## 0. The verdict

**No lever is built and no default changes.** The census names a gap - 18.2 % of
the inter-placement interval is convertible *in principle* - but **the whole of
it is cross-lane**, i.e. a fruit of the other arm's grade, and on this cell each
arm's output belt *is* its grade's bin, so taking it is a **sort error**. Priced
with the shipped fallback knob at both seeds: the starvation is deleted
completely (36 starved polls -> 0), the in-attempt arrival wait halves
(1.62 -> 0.67 s), and the **interval gets 5-7 % worse at both seeds** while
**17 of 40 fruits are sorted onto the wrong lane**. The mechanisms that *are*
available are already at their floor: the delay-aware form is the shipped rule
(**0.000 s** of headroom on 40/40 selections), the joint/park-gate term is
0.53 s/placement and is the price of the overlap, and the pick is a **forced
choice** (`window <= 1` on 37 of 40 selections).

## 1. What was built: one reporting block, and the proof it is inert

The shipped records carry the slot chain but not the attempt's end, and
`FRUIT_BED_DIAG=1` prints only counts. P99 adds `FRUIT_BED_DIAG=2`
(`tasks._biarm_bed_census`): after the shipped summary row, and from the same
`diag` list `select_target` already fills, it prints the **selector floor** of
that decision and **one row per live fruit** (`idx/grade/along/x/z/r` + the
first refusing predicate). Not one read is added to a control path; `=1` and
unset are byte-unchanged. The attempt end and the park split come from the
existing `FRUIT_BIARM_PARK_TRACE=1`.

**The instrument is neutral, and the tree is P98's, both proved by replay** -
the same-seed P94 record with the instrument's rows dropped
(`census.py --same`, `p99_report.py --check`):

```
   C5 vs logs/p94/T5.log: 974/974 [fruit] lines, IDENTICAL
   C6 vs logs/p94/T6.log: 970/970 [fruit] lines, IDENTICAL
```

(1-attempt smoke pair first: 78/78 identical.) So the P98 revert resolves off on
this cell exactly as it should, and ~500 `[bed-sel]` rows plus 120 park rows
move nothing.

**The derivation reproduces the record**: attempt end = `acquired + result.sim`,
placement instant = attempt end minus the `[cycle]` `return`+`end` blocks, and
the recomputed interval reads `logs/p94/T5.log` **9.37 s**, `T6` **11.08**,
`N5` **10.59** (P94 §5), `logs/p84/D5.log` **10.77 s** (P80). The park split
calibrates to a fixed **2.5 s** of motion + **0.25 s** feed, every gap closing
to ±0.05 s.

## 2. The wait split (mechanism numbers, branch-free)

Per attempt slot (`census.txt` §[A]):

| cell | park-gate | park-motion | feed | starved polls | dead | attempt span | interval |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C5 (seed 5, 17/20) | 0.03 | 2.47 | 0.27 | **0.17** | 2.94 | 15.08 | 9.38 |
| C6 (seed 6, 12/20) | 0.82 | 2.69 | 0.25 | **0.86** | 4.62 | 13.72 | 11.08 |

**The slot-loop wait is the park return plus the feed gap, not fruit.** The
starvation term is 0.9 % of the interval at seed 5 and 3.9 % at seed 6. Two
populations, never pooled: the **batch prime** (6 polls before each arm's first
attempt, 3.0 s once per batch = 0.17 s/placement) and the **in-chain** polls
(6 and 31).

## 3. The candidate read

| cell | decisions | live (mean) | own grade at/above floor | cross-lane at/above floor | inside the catch floor | ineligible |
| --- | --- | --- | --- | --- | --- | --- |
| C5 | 32 | 6.7 | **20/32** (mean 0.66) | 27/32 (1.19) | 2.34 | 1.81 |
| C6 | 57 | 7.0 | **20/57** (mean 0.39) | 53/57 (1.44) | 2.70 | 1.70 |

* the belt is **stocked** (7 live fruits at the decision instant) and the arm
  still has nothing its own grade can catch in 12/32 and **37/57** decisions;
  ~2.5 of those fruits are *already inside the catch floor* (they will be past
  the pick point when the 1.5 s setup ends);
* `window <= 1` on **37 of 40** selections: when the arm does have a candidate
  there is exactly one, so **there is no choice to optimise**;
* **own lane empty while a cross-lane fruit was at/above the floor**: 10/32 and
  **35/57** decisions (61 % at seed 6);
* **delay-aware headroom: 0.000 s on 40/40** - the chosen fruit *is* the nearest
  own-grade fruit, verified rather than assumed.

## 4. The convertible seconds and their share of the interval

Pooled over the two seeds (29 placements, mean interval 10.2 s):

| mechanism | s/placement | share |
| --- | --- | --- |
| (i) cross-lane, in-attempt arrival wait | **1.258** | 12.3 % |
| (i') cross-lane, in-chain starved polls | **0.603** | 5.9 % |
| (ii) delay-aware | **0.000** | 0.0 % |
| (iii) joint / park-gate | **0.531** | 5.2 % |
| **candidate planning ((i)+(i'))** | **1.862** | **18.2 %** |
| *memo*: batch-prime polls of the same kind | 0.172 | 1.7 % |

(iii) is not candidate planning: it exists *because* the arms overlap - the
throughput mechanism itself - and it is a clearance constraint on the park
return (its levers measured in P43/P69/P90). So the question is (i)+(i'), and it
is entirely cross-lane.

## 5. The pricing A/B (the shipped `FRUIT_GRADE_ROUTING=0` fallback)

| seed | arm | placed | interval | sim | window/m | batch/m | dead | polls | cross-lane |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | C | 17/20 | **9.38** | 181.1 | **6.40** | 5.63 | 2.94 | 6 | 0/20 |
| 5 | G | 17/20 | **10.01** | 174.3 | **5.99** | 5.85 | 3.39 | **0** | **9/20** |
| 6 | C | 12/20 | **11.08** | 182.6 | **5.42** | 3.94 | 4.62 | 31 | 0/20 |
| 6 | G | 13/20 | **11.66** | 166.9 | **5.15** | 4.67 | 3.29 | **0** | **8/20** |

Both seeds: **starvation 37 -> 0**, **arrival wait 1.62 -> 0.67 s** (seed 5),
`window <= 1` 19/20 -> 5/20, **park gate 0.03 -> 0.62 s/attempt**, **interval
+6.8 % / +5.3 %**, **window rate worse at both**, **batch span better at both**,
count a draw (29 -> 30 of 40), **17/40 mis-sorted**, and seed 6 loses 2 payloads
upstream (`release_bottom = -184 mm`, the stranding class).

**The transferable finding: the wait is not the interval.** ~1.1 s/attempt of
pure fruit wait removed (0.95 s of arrival + 0.17 s of polls) took **0.57 s off
the per-attempt cycle (18.02 -> 17.45 s) and 0.64 s onto the interval**, because the interval is the *sequencing* of two overlapped arms:
seed 5's placements bunch in pairs (4.5 / 1.8 / 0.4 s between the two arms,
then 16-18 s) and G5's are evenly spread (p50 13.00 -> 11.70 s, mean 9.38 ->
10.01 s). One arm's wait is often the slack the other arm's sweep needs.

## 6. The decision, and the owner's semantics

* **No lever**: nothing is added to the selector, no default changes,
  `configs/` untouched, both references untouched (`30fb99f8` / `30fb99f8` /
  `8952c320`).
* **Cross-lane is not a semantics choice on this cell - it is a bin error.**
  Left arm = lane 0 = grade A, right arm = lane 1 = grade B; the place is
  `run(state, bin_index)` with the arm's own lane, and the code already records
  the corresponding note ("the arm cannot change lanes mid-attempt ... the sort
  error is recorded", `tasks.py:11688`). So the 18.2 % is the **price of
  grade-pure routing**, and it can only be spent by changing the workstation
  (a diverter or a second bin per arm), not by planning.
* If the owner ever wants that price paid, the measurement is here: +5-7 % of
  interval and 42 % mis-sorts, on a count that is a draw.
* **The named open item is the park return** (2.5 s/attempt, ~13 % of the
  interval), a return-path/clearance object, not a planning one.

## 7. Guards

| guard | reading |
| --- | --- |
| landing, census cells | 17/17 and 12/12 `placed=True`, belt index = arm |
| landing, pricing cells | G5 17/17; G6 **13/13 payload-present** of 15 release rows, the 2 others `release_bottom = -184 mm` (payload lost upstream, reported separately per P86's convention) |
| motion budgets | census cells byte-identical to `logs/p94/{T5,T6}.log` (P94's budgets, 0 legs over); pricing cells are a moved branch, `105 --min-success-rate 0.0` **PASS** on both |
| grade ledger | census 0/40 cross-lane; pricing 17/40 |
| `scripts/selfcheck.sh` | **PASS**, 0 failures, 1 skipped |
| **acceptance** | `scripts/accept.sh` **8/10, 9.0 s/attempt, `fingerprint: matches configs/motion_reference.json`, `190: PASS`**, and its **420/420 `[fruit]` lines are byte-identical to `logs/p98/accept_revert.log`** - the diag-only change is inert on the scripted path, and both references stand untouched |

## 8. Pins

`src/fruit_sorting/tasks.py` **`7c1386e902756212bc427777d8fbf2ec`** (P98's
`6ce29b56` + the `FRUIT_BED_DIAG=2` block, +17/-1, reporting only),
`src/fruit_sorting/rl_env.py` `TASKS_MD5` metadata-only follow,
`logs/p99/{census.py,p99_report.py,run_p99.sh,run_p99_grade.sh,PREREG.md}`,
`logs/p99/PREREG.md5` = `0acc5692e6b22f0879f7abb40d8519f5`; tree `13726ca`,
`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`**,
`configs/motion_reference_single.json` = **`8952c320`** (all untouched),
ckpt `moe_v13s` `61da390a`.
