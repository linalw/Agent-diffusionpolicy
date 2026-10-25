# P40 lane B / TASK 1 — does `FRUIT_REGRASPS` ever rescue an attempt?

**Verdict: bounding it is free at `3 -> 2` and costs the only measured conversion at
`3 -> 1`.** Over **109 attempts / 54 re-seat rows** (the brief's five logs plus four
more that carry the row), **20 attempts printed at least one re-seat and exactly one of
them placed** (1/20 = 5.0 %), against **69/89 = 77.5 %** with no re-seat. That one
rescue came on the **second probe** (`k=1`); the **17 attempts that burned all three
probes never even closed on the fruit** (grasped 0/17, `lift <= 0.004 m`). So a third
probe has produced nothing in this corpus while costing a measured **1.24 s (two-line) /
1.50 s (single arm)** per attempt, and the knob value to test is **`FRUIT_REGRASPS=2`**
(**free**, saves 1.24-1.50 s on every attempt that currently burns three); `=1` would
save 2.48-3.00 s but removes the second probe, i.e. the one path that ever converted.

---

## 1. The rows and the code

`src/fruit_sorting/tasks.py`, the probe/regrasp loop
(`for _regrasp in range(int(os.environ.get("FRUIT_REGRASPS", "3"))):` —
**`tasks.py:10343` at HEAD** `112d2cb1`; **10555** in the working tree, which carries the
parallel P40-G0 effort lane's uncommitted +212 lines, `7a20eb80` — the regrasp block
itself is byte-identical between them: `git diff | grep -c regrasp` = 0):

| row | where | when |
| --- | --- | --- |
| `[task]   dynamic regrasp: re-seated on the moving fruit` | `tasks.py:10632` (was 10844) | `dynamic_capture` and **not** `regrasp_keep` — the shipped single-arm dynamic line |
| `[task]   dynamic regrasp: re-seated in place (gap N mm kept)` | `tasks.py:10591` (was 10803) | `regrasp_keep` — the **two-line** W1 profile (`FRUIT_DYNAMIC_REGRASP_KEEP` 0/1 via `_dynamic_profile`), plus ` [from-open]` when `FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1` |
| `[task]   recovery: re-grasped (open, re-seat, close)` | `tasks.py:10665` (was 10877) | `FRUIT_REGRASP_REOPEN=1`, default **off**, only on the last iteration |

The two `re-seated` rows are inside `if verbose:` **and** inside
`if self._dynamic_capture_active:`; the `recovery:` row is at loop level (any path,
still `if verbose:`) but behind a default-off knob.
That has a hard consequence for the policy lane: `_dynamic_pick_mode` returns
`(openarm and scripted) or not openarm`, and the direct/policy handover is
`scripted=False`, so `dynamic_capture` is **False** there and the two re-seat rows are
**unreachable by construction** — on top of `DirectSortEnv(verbose=False)`
(`rl_env.py:823`). Measured: **0** occurrences of either row anywhere under
`logs/w7/C_eval/`, and 0 in the `*_ab/` directories of `logs/p35/` and `logs/p37/`
(the 18 rows that do exist under `logs/p35`/`p37` are the **acceptance no-harm** logs,
i.e. the scripted primitive, not the direct loop).

`FRUIT_RESEATS` (default 2, `tasks.py:8560`) is a *different* loop — the indexed
close-phase re-seat — and does not print; it is out of scope here.

**One structural fact the counting depends on:** a re-seat row is printed once per
**failed** probe (the block sits after the lift test, inside the loop), so on this line
`k` = "how many probes failed", `k` in `{0,1,2,3}`, and `FRUIT_REGRASPS` is the cap on
`k`. An attempt with `k=1` **did** get a second probe and that probe **succeeded** —
which is what the one rescue is.

## 2. The corpus and why the two lines are counted differently

* **single arm** (`accept_C`, `pear_C`, `g/20_rate_single_1`, `D1_accept_pear`, the three
  P35/P37 no-harm acceptances): one attempt at a time, so the rows between
  `[run] attempt N: picking` and `[run] attempt N: grasped=` are that attempt's. Exact.
* **two-line** (`twoline_C`, `A0_bed_twoline_1`, `10_dense_twoline_1`): the two arms'
  grip phases **interleave** in the file and the row carries neither an arm nor a tick
  (`logs/p39/p3/twoline_C.log` lines 436-451: 6 rows for 2 attempts). Positional
  attribution is therefore impossible; the per-attempt count is read from that attempt's
  own `[cycle] grip` segment, whose value is a deterministic function of the iteration
  count. The classes are far apart and the read **closes** against the row total in
  every file:

  | line | `[cycle] grip`, k=0 | k=1 | k=3 | closure |
  | --- | --- | --- | --- | --- |
  | two-line | **1.74 s** median, 1.67-1.95 (n=26) | **3.08** (3.08-3.28, n=3) | **5.45** (5.38-5.45, n=11) | 13 = 13 rows (`twoline_C`), 22 = 22 (`bed`), 1 = 1 (`dense`) |
  | single arm | **1.58 s** (1.57-1.59, n=9, `g/20` only) | - | **6.07** (n=1) | exact by position |

  (`1.95 s` occurs 3x in the bed log and is **k=0**: it is 0.22 s over the healthy
  median, i.e. not a re-seat. If it were counted as one the bed's closure would read
  25 rows against 22 printed.)

## 3. The conditional

```
attempts parsed            : 109   (69 single-arm, 40 two-line)
attempts with >=1 re-seat  :  20   placed  1   P(placed | k>=1) = 0.050
attempts with  0 re-seats  :  89   placed 69   P(placed | k==0) = 0.775
  exactly k=1              : n=3   grasped 2 (0.67)   placed 1 (0.33)
  exactly k=3              : n=17  grasped 0 (0.00)   placed 0 (0.00)
```

The **primary corpus only** (the brief's five logs, 79 attempts / 45 rows) reads the same:
17 attempts `k>=1` -> 1 placed (0.059), 62 `k=0` -> 51 placed (0.823); `k=1` 1/3 placed,
`k=3` 0/14. The three P35/P37 rows add three more `k=3` attempts of the *same*
acceptance branch (the orange at attempt 3) and no conversions.

The whole `k>=1` population (one row per attempt; `grip` = `n/a` where the log has no
`[cycle]`):

```
accept_C            att 3  k=3 orange      placed=False grasped=False lift=+0.001  grip   n/a
twoline_C           att 0  k=3 peach       placed=False grasped=False lift=+0.003  grip  5.44s
twoline_C           att 1  k=3 kiwi        placed=False grasped=False lift=+0.001  grip  5.42s
twoline_C           att 4  k=1 peach       placed=True  grasped=True  lift=+0.319  grip  3.28s   <-- the rescue
twoline_C           att 6  k=3 strawberry  placed=False grasped=False lift=+0.000  grip  5.45s
twoline_C           att 9  k=3 orange      placed=False grasped=False lift=+0.000  grip  5.45s
A0_bed_twoline_1    att 0  k=1 pear        placed=False grasped=True  lift=+0.089  grip  3.08s
A0_bed_twoline_1    att 2  k=3 lychee      placed=False grasped=False lift=+0.001  grip  5.43s
A0_bed_twoline_1    att 4  k=3 orange      placed=False grasped=False lift=+0.000  grip  5.38s
A0_bed_twoline_1    att 11 k=3 peach       placed=False grasped=False lift=+0.000  grip  5.45s
A0_bed_twoline_1    att 12 k=3 lychee      placed=False grasped=False lift=+0.000  grip  5.45s
A0_bed_twoline_1    att 13 k=3 peach       placed=False grasped=False lift=+0.002  grip  5.45s
A0_bed_twoline_1    att 14 k=3 pear        placed=False grasped=False lift=+0.004  grip  5.45s
A0_bed_twoline_1    att 16 k=3 apple       placed=False grasped=False lift=+0.004  grip  5.45s
10_dense_twoline_1  att 8  k=1 peach       placed=False grasped=False lift=+0.045  grip  3.08s
g/20_rate_single_1  att 6  k=3 kiwi        placed=False grasped=False lift=+0.000  grip  6.07s
D1_accept_pear      att 3  k=3 orange      placed=False grasped=False lift=+0.001  grip   n/a
B_accept_no_harm    att 3  k=3 orange      placed=False grasped=False lift=+0.001  grip   n/a
C_accept_no_harm    att 3  k=3 orange      placed=False grasped=False lift=+0.001  grip   n/a
accept_no_harm      att 3  k=3 orange      placed=False grasped=False lift=+0.001  grip   n/a
```

Note the shape: **`grasped=True` only ever appears at `k=1`** (2 of 3), never at `k=3`
(0 of 17), and every `k=3` attempt ends `notes=['fruit did not follow the gripper']`
with `lift <= 0.004 m`. The rule of three puts the 95 % upper bound on the third
probe's conversion rate at `3/17 = 17.6 %` — not a proof of zero, but the corpus
contains no example of it.

Attribution caveat, stated because it is the one soft number here: the two-line `k` comes
from the `[cycle] grip` segment, not from the row's position (see §2). The one rescue is
**not** inferred that way — its block is readable line by line in
`logs/p39/p3/twoline_C.log` 556-584: the right peach's close (`6.63cm around a 6.89cm
fruit`), one `re-seated in place (gap 58.7 mm kept)`, then `carry grasp_lift: 3 cm, 67
ticks` and `lift +0.3191 m, grasped=True` — i.e. the second probe held and the attempt
placed.

## 4. The cost, measured

The `[cycle] grip` segment covers exactly this loop (`_cycle_mark("close")` ->
`_cycle_mark("grip")` brackets the probe/regrasp/squeeze block), so the loop's price is
printed per attempt:

* **`k=3` vs `k=0`**: two-line **5.45 - 1.74 = 3.71 s**, single arm **6.07 - 1.58 = 4.49 s**.
* per failed probe iteration: **1.24 s** (two-line, n=11 `k=3` attempts) and **1.50 s**
  (single arm, n=1) — against the code path's own tick count, `probe + descent/chase +
  squeeze` = **160 ticks = 1.33 s** (two-line, `FRUIT_DYNAMIC_PROBE_TICKS=60`) and
  **185 ticks = 1.54 s** (single arm, 40-tick probe). The measured values bracket the
  code path, so the per-iteration price is known two independent ways.
* `k=1` costs `3.08 - 1.74 = 1.34 s` (two-line) — one iteration, as expected.

**Sim seconds the re-seats consume on *failed* attempts** (`sum over failed attempts of
k x per-iteration cost`):

| log | failed attempts with k>=1 | re-seat sim-s on failed attempts |
| --- | --- | --- |
| `p39/p3/twoline_C.log` | 4 (all k=3) | **14.8 s** of a 90.2 s batch |
| `p32/A0_bed_twoline_1.log` | 8 (7 k=3 + 1 k=1) | **27.2 s** of a 171.8 s batch |
| `w7/10_dense_twoline_1.log` | 1 (k=1) | 1.2 s of 91.3 s |
| `accept_C` / `D1` / `P35 B` / `P35 C` / `P37` | 1 each (k=3) | **4.5 s** of a 150.1 s batch each |
| `pear_C` | 0 | 0.0 s |

## 5. What a bound would save, and the exact knob to test

| bound | keeps | loses | saves per attempt that burns three |
| --- | --- | --- | --- |
| `FRUIT_REGRASPS=1` | the first probe and one re-seat+squeeze, then lifts | the **second probe** — i.e. the only measured conversion path (2/3 grasped, 1/3 placed) | **2.48 s** (two-line) / **3.00 s** (single arm) |
| **`FRUIT_REGRASPS=2`** | probes 1 and 2 (the rescue path) | the third probe, which converted **0/17** | **1.24 s** (two-line) / **1.50 s** (single arm) |

Batch arithmetic from the same logs (removing one iteration from each `k=3` attempt, all
placements unchanged):

```
twoline_C   10 attempts, 6 placed, span  90.2 s : 3.99 -> 4.22 placed/min (+5.8 %)
bed         20 attempts, 12 placed, span 171.8 s: 4.19 -> 4.41 placed/min (+5.2 %)
accept_C    10 attempts,  6 placed, span 150.1 s: 2.40 -> 2.42 placed/min (1 of 10 attempts)
dense       10 attempts,  7 placed, span  91.3 s: 4.60 -> 4.60 (no k=3 attempt)
```

So the honest size of the prize is **+5 % on the two lines that carry a `k=3`
population** and ~nothing on the current single-arm acceptance (it burns three on 1 of 10
attempts). It is a *rate* lever with no success-rate claim attached, and it is not the
`grip` block's dominant term: on the `k=3` attempts the tax is 3.71 s of the ~15 s cycle.

## 6. What this implies

`FRUIT_REGRASPS` is not a recovery mechanism in this build — it is a **retry that only
ever pays on its second try**. The generator of that is the probe itself: the first
10 mm test lift (single arm) / 6 mm (two-line) fails when the fruit sat at the edge of
the span, and the re-seat is what re-centres it; the second probe then holds or it does
not, and if it does not, probes three is a third identical chance against a grip that has
already failed twice at the same geometry — the measured 0/17 says the state does not
change between them. Two things follow. **For the rate work (P40 phase 3):** test
`FRUIT_REGRASPS=2` in the two-line battery and the single-arm acceptance as a default-off
candidate — it is the largest measured recoverable slice of a failing attempt (3.71 s of
the 5.45 s `grip` segment on a `k=3` attempt, second only to the grip/close class that
segment already belongs to) and it cannot move a success rate except through the `k=1`
class, which `=2` keeps. **For the grip work (P40 phase 2):**
do not read the re-seat rows as evidence about grip quality — the `k=3` population is the
same failure the census already owns (the fruit is out of the span / the pads are
drive-saturated), and squeezing harder on the third try is a measured non-lever. If the
`k=3` cost is ever worth removing outright, the target is the *first* probe's failure
(the same `grasp_lift` escape the retention work is chasing), not the retry cap.

## 7. Reproduce

```bash
# the rows, both branches
grep -n "dynamic regrasp: re-seated" src/fruit_sorting/tasks.py
grep -c "dynamic regrasp: re-seated in place" logs/p39/p3/twoline_C.log   # 13 (the two-line form)
grep -c "dynamic regrasp: re-seated on the moving fruit" logs/p39/p3/accept_C.log  # 3 (the single-arm form)
grep -rn "dynamic regrasp: re-seated" logs/w7/C_eval logs/p35/*_ab logs/p37/*_ab   # none: not printed on the direct loop

# the per-attempt parse + the conditionals + the cost block
python3 logs/p40/regrasp_yield.py            # -> logs/p40/regrasp_yield_out.txt

# the two structural facts the counts rest on
grep -n 'FRUIT_REGRASPS' src/fruit_sorting/tasks.py
grep -n 'for _reseat in range' src/fruit_sorting/tasks.py   # FRUIT_RESEATS, the *other* loop
sed -n '436,451p' logs/p39/p3/twoline_C.log                 # 6 rows, 2 attempts: why position cannot attribute
sed -n '556,584p' logs/p39/p3/twoline_C.log                 # the one rescue, line by line
```

Pins at parse time: `src/fruit_sorting/tasks.py` **7a20eb80** (working tree; HEAD
`112d2cb1`), `src/fruit_sorting/rl_env.py` **1e94345d**; the regrasp block is unchanged
between HEAD and the working tree.
