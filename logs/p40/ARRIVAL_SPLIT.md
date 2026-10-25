# P40 lane B / TASK 2 — the arrival wait: supply-bound or arm-bound?

**Verdict: supply-bound on both lines, to within 10 ms of a printed tick.** The wait
loop's tick count *is* the fruit's belt travel: `N/120` equals `(dy_at_loop_entry -
dy_at_handover)/0.12` with a **median residual of 0 ms and a worst case of 10 ms (one
tick) over 109 attempts**, and inside the loop the fruit's own along-position moves at
**-0.1200 m/s** while the arm re-commands one fixed joint target per tick. There is no
arm/queue term in the wait. The arm's own pre-pose + hover block (1.49 s median on the
two-line = **46 % of the 3.26 s commit->arrival gap**, 0.87-0.88 s pre-pose on the single
arm) runs **in parallel** with the fruit's travel and adds **0 s** to the gap: the gap is
the fruit's travel time from its position at the commit, `dy_commit` median **0.579 m**
two-line / **0.521 m** single arm.

---

## 1. The two ticks, as printed

| role | row | notes |
| --- | --- | --- |
| selector / station commit (two-line) | `[biarm] left: station acquired at t=16.4s` | the scheduler's lock-on. It **equals** the attempt's own first tick (`[run] attempt N (arm): ... sim=a-b`) on **40/40** attempts (checked in the script) |
| selector commit (single arm) | `[run] attempt N: picking <fruit> grade <G> ...` | printed by `20_pick_place.py:247` immediately before `task.run`; its tick is the outcome row's `sim=a` (the attempt's `t0`, `tasks.py:7455`) |
| arrival | `[task] fruit at pick point: dy=+0.1889 m arrived=True after 51 steps` | with `[task]   intercept handover: ... dy=+0.1889 m lead=0.189 m` on the line before it |
| pre-pose (arm) | `[task] at pick pose after 0.87 s` | same quantity as `[cycle] ... prepose=` |
| hover (arm) | `[cycle] attempt N: ... hover=0.80s ...` | **two-line: printed on all 40. Single arm: printed only in the `[cycle]`-instrumented `logs/g/20_rate_single_1.log`** — the other single-arm logs have no `[cycle]` marks (RATE_CENSUS §2) |
| fruit position at loop entry | `[task]   wait step=0 fruit_y=0.2403 ... dy=+0.2399` | steps 0-5 are printed, i.e. six consecutive ticks of the *same* attempt |
| the handover wait (a *different* block) | `[task] dynamic descent: waited N ticks ...` | after the arrival, inside `[cycle] descent`; not part of this gap |

**`arrived=True after N steps` is not the pick station.** The moving catch breaks the
wait loop at `dy <= lead` (~0.189 m), so the "arrival" is the *handover*: the fruit is
still 0.19 m upstream and the descent does the rest. `N` is the loop's iteration count
and every iteration is exactly one `_step_sim(1)` at 120 Hz, so `N/120` is sim seconds.

## 2. How the rows are paired (and why the belt identity is a check, not the definition)

The two-line interleaves its two arms, so the rows cannot be paired by position. Three
independent keys are used, none of which reads a tick count or a `dy` to make the pair it
is later checked against:

1. **cycle row -> attempt index**: the `total=` segment against the attempt's printed
   `sim=a-b` span (the `[cycle]` rows are printed in *completion* order, which is not
   index order in `logs/w7/10_dense_twoline_1.log`).
2. **`wait step=0` row -> attempt**: the row is emitted at the wait loop's first tick,
   i.e. at `commit + pre-pose + hover`, all of which the attempt prints itself — so the
   rows, in file order, pair with the attempts sorted by that entry tick.
3. **arrival row -> attempt**: by its printed `after N steps` against the wait that the
   attempt's *own* loop-entry position implies, `(dy0 - 0.189)/0.12`.

The belt identity, the `[cycle] descent` reconciliation (`descent - wait` = the handover
wait + approach + settle, **1.41-1.48 s on 9/10 `twoline_C` attempts**), and the
within-attempt `wait step=0..5` slope are then all *consequences* — and all three hold
on every attempt, which is what makes the pairing trustworthy. `arrival dy` lands in
0.188-0.190 m everywhere, and `gap <= span` everywhere; the script prints a `CHECK:` on
any violation and the current run has **0 checks in 109 attempts**.

## 3. Per-attempt tables (two representative logs)

`logs/p39/p3/accept_C.log` (current-tree single arm; `hover` unprinted -> `gap` here is
pre-pose + wait, a lower bound):

```
att fruit       commit  prepose hover  wait  gap    dy0    dy_arr  belt  resid slope   descent-wait
 0  peach          7.3   0.87  (n/p)  0.42  1.29 +0.240 +0.189   0.42   +0  -0.1200    -
 1  peach         24.5   0.88  (n/p)  2.35  3.23 +0.470 +0.189   2.35   +0  -0.1200    -
 2  kiwi          43.9   0.88  (n/p)  0.92  1.80 +0.300 +0.189   0.92   +0  -0.1200    -
 3  orange        61.7   0.88  (n/p)  1.03  1.91 +0.312 +0.188   1.03   -0  -0.1200    -
 4  lychee        78.9   0.88  (n/p)  2.48  3.35 +0.486 +0.189   2.48   +0  -0.1200    -
 5  strawberry    97.9   0.88  (n/p)  0.57  1.46 +0.258 +0.189   0.58   -0  -0.1200    -
 6  pear         115.4   0.88  (n/p)  0.68  1.56 +0.270 +0.189   0.68   -0  -0.1200    -
 7  orange       135.7   0.88  (n/p)  1.20  2.08 +0.332 +0.188   1.20   -0  -0.1200    -
 8  apple        153.5   0.88  (n/p)  2.27  3.15 +0.460 +0.188   2.27   -0  -0.1200    -
 9  lychee       172.5   0.88  (n/p)  2.18  3.06 +0.450 +0.188   2.18   -0  -0.1200    -
```

`logs/p39/p3/twoline_C.log` (all three terms printed; `entry` = commit + pre-pose + hover,
the loop-entry tick):

```
att arm   commit  entry prepose hover  wait  gap    dy0    dy_arr  belt  resid  descent-wait
 0  right   13.4   14.9   0.71  0.80  3.18  4.69 +0.570 +0.188   3.18   -0    1.47
 1  left    16.4   17.8   0.71  0.73  2.17  3.61 +0.449 +0.189   2.17   -0    1.41
 2  right   31.0   32.6   0.71  0.86  1.47  3.04 +0.364 +0.188   1.47   +0    1.43
 3  left    35.9   37.3   0.71  0.67  2.09  3.47 +0.439 +0.188   2.09   +0    1.48
 4  right   50.4   51.9   0.71  0.80  1.15  2.66 +0.326 +0.188   1.15   -0    1.47
 5  left    54.9   56.3   0.71  0.72  0.57  2.00 +0.257 +0.189   0.57   -0    1.46
 6  right   68.4   69.9   0.71  0.83  3.04  4.58 +0.554 +0.189   3.04   +1    1.47
 7  left    71.6   73.1   0.71  0.80  1.95  3.46 +0.422 +0.188   1.95   -0    1.48
 8  right   86.7   88.1   0.71  0.74  2.70  4.15 +0.513 +0.189   2.70   +0    1.86
 9  left    90.7   92.3   0.71  0.86  0.98  2.55 +0.307 +0.189   0.98   -0    1.47
```

`resid` is `wait - (dy0 - dy_arr)/0.12` in ms; `belt` is the same distance in seconds.
The `descent-wait` column is `[cycle] descent - wait`: 1.41-1.48 s on 9/10 (the outlier,
1.86 s, is the `k=1` regrasp attempt, whose descent carries a longer handover wait) —
that is the *independent* confirmation that the `wait` value belongs to that attempt,
because the descents themselves span 1.80-4.65 s.

## 4. Pooled

| | single arm | two-line |
| --- | --- | --- |
| n | 69 | 40 |
| printed wait, median / p90 | **1.87 s / 2.35 s** (range 0.42-2.48) | **1.69 s / 2.92 s** (range 0.31-3.18) |
| belt travel in that wait, median | **1.87 s** | **1.69 s** |
| residual (arm/queue inside the wait), median / max | **-0 ms / 10 ms** | **+0 ms / 1 ms** |
| within-attempt belt slope (`wait step=0..5`) | **-0.1200 m/s**, all 69 | **-0.1200 m/s**, all 40 |
| pre-pose + wait (comparable across every log), median / p90 | **2.75 s / 3.23 s** | **2.40 s / 3.63 s** |
| full gap incl. hover, median / p90 | **3.64 s** (`g/20` only, n=10) | **3.26 s / 4.46 s** |
| arm block (pre-pose + hover) | 0.87-0.88 s printed + 0.76 s hover (`g/20`) | **1.49 s** (1.37-1.60) = **46 %** of the gap |
| implied distance at the commit | **0.521 m** median, 0.344-0.637 (lower bound: no hover term) | **0.579 m**, 0.400-0.752 |
| belt time from the commit vs the gap | 3.65 s vs the 3.64 s gap (`g/20`) | **3.25 s vs 3.26 s** |

**Cross-check against the existing census** (RATE_CENSUS §3 quotes means, not medians):
`accept_C` wait mean **1.41 s = 169 ticks** (census 169.3) and `twoline_C` mean **1.93 s =
232 ticks** (census 231.6). Two independent parses of the same logs agree to a tick.

## 5. The split, stated as the brief asks

* **Share of the gap attributable to belt travel (distance / 0.12 m/s): 99.7-100 %.**
  Two-line: the fruit's travel from its commit position is 3.25 s of the 3.26 s gap.
  Single arm: 3.65 s of the 3.64 s gap (`g/20`). The residual (arm/queue time not
  explained by the fruit's motion) is **0.00-0.01 s**, i.e. one tick.
* **What the arm block is.** It is 1.49 s (two-line) / ~1.6 s (single arm incl. hover) of
  the *elapsed* gap, and the fruit travels 0.18-0.19 m during it. It is therefore
  **overlapped, not additive**: shortening the pre-pose/hover would move the same seconds
  from "arm moving" to "arm waiting" and leave the gap where it is. That is visible in
  the data: on `twoline_C` attempt 5 the hover is 0.72 s and the wait 0.57 s (gap 2.00 s)
  because its fruit was only **0.257 m** out, while attempt 0 has a 0.80 s hover and a
  3.18 s wait (gap 4.69 s) because its fruit was **0.570 m** out - within the same log the
  gap tracks `dy0`, not the arm block.
* **Where the seconds actually are.** The commit distance is the lever: the two-line
  commits to a fruit **0.579 m** out (0.400-0.752) and the single arm to **0.52 m**
  reconstructed (0.344-0.637, plus 0.09 m of travel during its 0.76 s hover). The single
  arm's selector floor is `lead + 0.12*1.5 + 0.03 = 0.399 m` (`_dynamic_select_floor`), so
  its reconstructed commit sits **0.04-0.33 m (median 0.21 m) beyond the floor** - it
  takes the *farthest-upstream* eligible fruit and pays that distance in waiting (0.21 m =
  1.75 s of belt travel). The two-line's lane rule takes the nearest usable one and still
  lands at 0.579 m median, i.e. its wait is **queue depth**, not the floor.

## 6. What this implies

The census's open question — "is the 1.4-2.0 s arrival wait supply-bound or arm-bound?" —
resolves as **supply-bound, and more precisely commit-distance-bound**: the wait is the
fruit's travel from wherever the selector found it, with zero arm/queue slack, and the
arm-side block is fully overlapped by that travel. The practical consequences for the
rate work are narrow but sharp. (i) **Do not spend on the pre-pose/hover speed** (R3's
L2/L3 lane, or a faster hover): on this evidence it cannot shorten the arrival gap, only
re-label it — the same conclusion R3 reached from the lead-slack side, now with the
per-attempt ticks. (ii) **The lever is the commit distance**: either the selector's
distance rule (the single arm's farthest-upstream pick sits 0.04-0.33 m beyond its own
floor and costs 0.3-2.8 s of wait for it, and the floor itself is `0.12*1.5 s` of setup)
or the belt speed, which divides the whole travel term (at 0.18 m/s the measured 0.579 m
commit would be 2.2 s instead of 3.25 s *if the commit distance held* - it would not,
because the floor is `lead + speed*1.5`, so a speed change has to be measured, not
scaled). (iii) **A two-line bay needs a shorter lane length or a denser stream near the
station**, not a faster arm: the 2.92 s p90 wait is the queue, and the 46 % the arm
contributes is free. (iv) Any *cycle-time* model that adds the arrival wait to the arm's
setup is wrong by ~1.5 s per attempt — they overlap.

## 7. Reproduce

```bash
# the two ticks
grep -nE "station acquired at t=|fruit at pick point" logs/p39/p3/twoline_C.log | head
grep -nE "\[run\] attempt [0-9]+: picking|fruit at pick point" logs/p39/p3/accept_C.log | head

# the belt identity by hand (twoline_C attempt 0): (0.570-0.188)/0.12 = 3.183 s
# vs `after 382 steps` = 382/120 = 3.183 s
sed -n '401p;420,421p' logs/p39/p3/twoline_C.log

# the within-attempt slope: six consecutive ticks, 1.0 mm/tick = 0.12 m/s
grep -m6 "wait step=" logs/p39/p3/twoline_C.log

# everything above, per attempt, with the pairing checks
python3 logs/p40/arrival_split.py            # -> logs/p40/arrival_split_out.txt
```

Pins at parse time: `src/fruit_sorting/tasks.py` **7a20eb80** (HEAD `112d2cb1`),
`src/fruit_sorting/rl_env.py` **1e94345d**. No `src/` file was modified by this lane.
