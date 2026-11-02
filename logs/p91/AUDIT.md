# P91 STEP 1 — the audit of the five never-profiled `[cycle]` blocks

Offline, from the existing records: no simulator ran for this document and no
number here is re-derived from anything the log can check. The instrument is
`FRUIT_CYCLE_REPORT=1` and the readout is `logs/p91/audit.py` →
`logs/p91/audit.txt`.

```
python3 logs/p91/audit.py                 # the table over three logs
python3 logs/p91/audit.py --predict       # the profile arithmetic, per candidate
python3 logs/p91/audit.py --grip          # the grip block by outcome class
```

Logs read (all shipped two-line cells, seed 5 unless said otherwise):

| log | cell | why |
| --- | --- | --- |
| `logs/p87/T5.log` | the **shipped** tree (two-line + P87 release trim) | the current scenario, 20 attempts |
| `logs/p86/C5.log` | P87's control (`FRUIT_SPEED_RELEASE=0`) | the same scenario at the 2.35 s release clock — the pre-P87 record |
| `logs/p89/C5.log` | P89's control | a third same-tree record (identical to `T5` line for line, as P89's G0 proved) |
| `logs/p44/p2/accept_s5_C.log` | the **single arm**, probe 40 | the cross-check that the probe is a 1:1 lever (§4) |

## 1. What each block *is* — the marks, verbatim

`_cycle_report` prints one segment per consecutive pair of marks and names the
segment after the mark that **ends** it:

```python
segments = " ".join(
    f"{nxt[0]}={nxt[1] - cur[1]:.2f}s" for cur, nxt in zip(marks, marks[1:])
)
```

so `descent=3.64s` is the time between `_cycle_mark("hover")` and
`_cycle_mark("descent")`. `_cycle_begin()` sets `("start", t)` and each block is:

| block | start event | end event (the mark) | what runs in between |
| --- | --- | --- | --- |
| **prepose** | `_cycle_begin()` — `tasks.py:9969`, the first statement of the attempt after the selection and the reach-aim reset | `_cycle_mark("prepose")` — `tasks.py:10148`, immediately after `move_time = self._sim_time() - t0` and the `[task] at pick pose after …` print | `_transit_to(arm, "grasp", ticks=FRUIT_PREPOSE_TICKS=45, settle=0)` (`tasks.py:10072`) + the session's 20-tick pump (`SimulationManager.step(steps=20)`, `tasks.py:10135`) |
| **hover** | the `prepose` mark | `_cycle_mark("hover")` — `tasks.py:10205`, after `move_to(self._dynamic_hover_point())` and the `FRUIT_DYNAMIC_HOVER_SETTLE` (20) hold loop | the hover move `arm.move_to(hover, max_steps=300, tolerance=0.008)` at `FRUIT_HOVER_STEP=0.04` (`tasks.py:10179`) + a 20-tick hold at that pose |
| **descent** | the `hover` mark | `_cycle_mark("descent")` — `tasks.py:11487`, inside the `if self._dynamic_arrive_diag` block and **after** `self._approach(...)` returned | **three different things**, in this order: (a) the **fruit-arrival wait** `for step …` (`tasks.py:10234-10395`, `arrived=True after N steps`); (b) a second `move_to(hover)` + `_settle_to_rest` (`tasks.py:11219-11252`, `FRUIT_DYNAMIC_SETTLE_TICKS=0` on the dynamic path); (c) the **scheduled wait** `while waited < max_wait` (`tasks.py:11334-11349`, `dynamic descent: waited N ticks`); (d) the **profiled descent** `self._approach(arm, grip, v_max=dyn_v_max …)` (`tasks.py:11430`, the `[motion] approach(cartesian): …` row) |
| **close** | the `descent` mark | `_cycle_mark("close")` — `tasks.py:12539`, after the `FRUIT_DYNAMIC_HOLD` (48) hold loop | the **catch-up** `for _ in range(catch_ticks)` (`tasks.py:11749`, `dynamic catch-up: residual=… (tol 6 mm)`), the close ramp `for _close_step …` (`tasks.py:11889`, `dynamic close: sustained contact after N ticks`), then the fixed 48-tick `hold_ticks` loop (`tasks.py:12471`) |
| **grip** | the `close` mark | `_cycle_mark("grip")` — `tasks.py:13457`, immediately before `self._carry(arm_name, sample, "grasp_lift")` | the probe/regrasp loop `for _regrasp in range(regrasp_cap)` (`tasks.py:12927`; `probe_ticks` = 60 on the two-line, `z_ramp = min_jerk_ramp(0, 0.006, 60)`), the squeeze-harder 60-tick block on the failure path, then the **velocity-matched belt-break** `for i in range(track_ticks + ticks)` (`tasks.py:13380`, `match 0.20 + trans 0.25` = 54 ticks, the P3 anti-shear clock), then the pluck dwell (`FRUIT_PLUCK_DWELL=0`) |

Two things the definitions settle immediately, and both matter:

* **the descent block is not a descent.** It contains the *fruit-arrival wait*
  and the *scheduled* wait before the profiled leg starts. The `[motion]` row is
  only the last part of it.
* **the grip block is not a grip.** It is the take-off validation (a 6 mm test
  lift), the belt-break, and — on a failed attempt — the regrasp tax. The
  profiled `grasp_lift` leg is in the **lift** block, after the mark.

## 2. The decomposition (T5, the shipped tree, 20 attempts)

Every number below is the sum of the block over the 20 `[cycle]` rows divided by
20, unless a `n` says otherwise; the sub-terms are the **printed** loop counts
× 1/120 s. `unmodelled` = the block minus every named loop in it, i.e. the part
of the block this audit cannot attribute from the log — it is reported, never
used as a lever.

| block | mean s | share | motion (named) | wait / settle | failure tax | **speedable** | ceiling |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **descent** | **3.64** | 23.7 % | approach **0.74** (88.8 ticks) | arrival wait **2.17** (259.9 ticks) + scheduled wait **0.59** (70.7 ticks) | — | **0.00** | **0** (schedule-invariant, §3) |
| **grip** | **2.36** *(clean 1.75)* | 15.4 % | probe **0.50** (60) + belt-break **0.45** (54) | — | **0.61** mean (+1.53 per failed probe, +2.29 a burnt cap) | **0.50** (the probe) | **−0.30** |
| **close** | **1.36** *(clean 1.21)* | 8.9 % | ramp **0.18** (22 ticks printed) | catch-up **0.63** + fixed hold **0.40** (48) | — | **0.20** (the hold) | −0.20 |
| **hover** | **0.75** | 4.9 % | `move_to` ~0.58 | settle **0.17** (20) | — | **0.00** (no profile: IK step cap) | 0 |
| **prepose** | **0.71** | 4.6 % | blend **0.38** (45 ticks) | session pump **0.17** (20) + ~0.17 | — | **0.38** | −0.13 |
| | **8.82** | **57.5 %** | **3.63** | **4.09** | **0.76** | **1.08** | |

`unmodelled` per block: descent 0.15, grip **0.80**, close 0.15, prepose 0.00,
hover 0.00. The grip's 0.80 s is the largest unattributed chunk in the five and it
is **constant across both probe values** (§4), so it is not the lever.

### The grip block by outcome class (the tax, measured — `--grip`)

| cell | clean, 1 probe | 1 failed probe | 2 probes (the P40 cap) |
| --- | --- | --- | --- |
| `logs/p87/T5.log` | n=14, **1.75 s = 209 ticks** | n=2, 3.28 s (**+1.53**) | n=4, 4.04 s (**+2.29**) |
| `logs/p86/C5.log` | n=10, **1.75 s = 210 ticks** | n=6, 2.57 s (+0.82) | n=4, 3.99 s (+2.23) |

The block is **bimodal**, not noisy: a clean attempt is 1.72-1.79 s, a burnt cap
is 3.99-4.12 s, and the never-grasped class (`grasped=False`, the four `fruit did
not follow the gripper` rows) is exactly the 4.0 s group. That is P40's cap and
P40's 1.24 s/probe figure reproduced one order up: a failed probe costs **1.5 s
in this cell**, and the *mean* grip block carries **0.61 s** of it.

## 3. Why the descent is **not** speedable — the schedule

The dynamic catch's descent is deliberately early: the wait loop exits when the
fruit is one descent away,

```python
deadline = speed_now * (t_desc + FRUIT_DYNAMIC_DESCEND_MARGIN)   # tasks.py:11311
while waited < max_wait:
    fruit_now = ...
    if float(fruit_now[1]) - float(grip[1]) <= deadline and waited >= hold_ticks:
        break
```

with `t_desc` the *predicted duration of the leg about to run*
(`_approach_duration(TCP distance, dyn_v_max, dyn_a_max)`). So the descent
starts exactly `t_desc` before the fruit reaches the aim, and

```
block = wait + leg = (lead/speed − t_desc − margin) + t_desc = lead/speed − margin
```

**the block does not contain the leg's duration at all.** A faster profile makes
the wait longer by exactly the ticks the leg saves. The audit's measurement
agrees: `[motion] approach` 88.8 ticks + scheduled wait 70.7 ticks + arrival
2.17 s reconstructs the 3.64 s block to **0.15 s** (4 %) on all three logs, and
the two `t_desc` values in the log (`0.68`/`0.71` s) sit inside that slack.

The profile arithmetic confirms it from the other side (`audit.py --predict`) —
the leg is **jerk-bound**, not speed-bound:

| `v_max` / `a_max` | ticks for 5.5 cm |
| --- | --- |
| 0.15 / 0.8 (shipped) | 86 |
| 0.15 / 1.6 (a_max ×2) | **86** (no change: `j_max=25` binds) |
| 0.25 / 0.8 | 79 |
| 0.25 / 1.6 | 64 |
| 0.30 / 1.9 | 64 |

So even the most aggressive admissible pair buys 22 ticks — and the schedule
takes them back. The descent is the phase's *biggest* block and its **speedable
seconds are zero**; a cell there can only move the catch window (that is the
guard, not the win).

**The measurement can't refute the invariance, and it can show the leg is not the
block's variable** (`audit.py --schedule`). Both records print `waited` and
`t_desc` on the same row, so `waited + t_desc*120` is the block's own schedule in
ticks:

| log | `waited` | `t_desc` (the leg) | `waited + leg` |
| --- | --- | --- | --- |
| `logs/p87/T5.log` | 57-87 ticks (**0.25 s** spread) | 81.6-85.2 (**0.03 s**) | 139.8-171.2, sd **8.9** ticks |
| `logs/p86/C5.log` | 51-87 ticks (**0.30 s** spread) | 81.6-85.2 (**0.03 s**) | 135.0-171.2, sd **10.0** ticks |

The leg's **entire range is 0.4x the block's standard deviation**: inside this
cell the leg's duration is not an available variable at all — what moves the
block is the per-fruit handover lead, one order of magnitude larger. (The
correlation `corr(waited, t_desc)` is only −0.17/−0.20 because `t_desc` spans
0.03 s while the lead noise is 0.3 s: the lever to *measure* the slope does not
exist in the shipped cell, which is the point.)

## 4. The probe is a 1:1 lever on the grip block — the cross-check

`_dynamic_profile("FRUIT_DYNAMIC_PROBE_TICKS", "40", "60")`: the single arm runs a
**40**-tick probe over 10 mm, the two-line a **60**-tick probe over 6 mm (W1's
grip profile). Comparing the clean blocks:

| record | probe | clean `grip` block | ticks | non-probe remainder |
| --- | --- | --- | --- | --- |
| `logs/p44/p2/accept_s5_C.log` (single arm) | 40 | 1.57-1.70, median **1.585** | **190** | 150 |
| `logs/p87/T5.log` (two-line) | 60 | 1.72-1.79, median **1.75** | **210** | 150 |

Δ = **20 ticks = exactly the probe's own 20 ticks**, and the remainder is the
same 150 in both (belt-break 54 + 96 unmodelled). So the probe's tick count is a
**1:1** lever on the block, and the 96 unmodelled ticks are not affected by it.
(The single-arm record is a different tree — P44 — so it is a cross-*tree*
cross-check, which is why the battery's control/treatment pair is same-tree and
the prediction below is the *same-tree* delta.)

## 5. The ranking, and what it leaves

| candidate | speedable | ceiling | why not / why |
| --- | --- | --- | --- |
| **descent** (3.64, the biggest) | **0.00** | 0 | §3: schedule-invariant; a profile cell can only break the catch window |
| **grip** (2.36, clean 1.75) | **0.50** probe (+0.45 belt-break not touched) | **−0.30** | **the winner**: the largest single profile among the five, and the only one whose tick count is a clean 1:1 lever (§4) |
| **close** (1.36) | 0.20 (the 48-tick hold) | −0.20 | the direction is **contested**: R11-B/P18b measured a *slower* close converting the direct line's carried class (48 → 27), so speeding it is the opposite of the one measured-good direction; P41/P42/P75 closed the contact family |
| **hover** (0.75) | 0.00 | 0 | `move_to` at the IK step cap — there is no profile to raise; R3's hot-arm residency (the related lever) is measured negative on the two-line |
| **prepose** (0.71) | 0.38 | −0.13 | the 45-tick blend is already tuned and the 20-tick pump is the session's camera service; R3's residency negative applies here too |

Outside the five, for completeness (not candidates): the `return` block is
**0.66 s** = a hard-coded 60-tick settle after the pads open (pure dwell, 4.3 %),
the `place` (3.14) and `lift` (1.68) blocks are measured (`logs/p88`, `logs/p89`)
and the `release` (1.70) shipped in `logs/p87`.

**The audit's headline: the 8.82 s of never-profiled span is 4.09 s of wait
(3.8 s of it inside the "descent"), 0.76 s of failure tax, 3.63 s of arm motion
of which the descent's 0.74 s is schedule-invariant and the hover's 0.58 s has no
profile — leaving 1.08 s (7 % of the 15.34 s span) genuinely speedable across
five blocks, and the largest of them is the 60-tick probe ramp.**

## 6. What the winner does **not** do

The probe's other side is the tax: at the shipped probe the cell spends 0.61 s of
its 2.36 s on average in regrasp machinery, and P40 already cut the cap from 3 to
2 (a third probe produced nothing in 109 attempts). So the audit **measures the
tax and does not speed it** — a profile cannot buy it back, only a lower failure
rate can, and that is a supply/acquisition object, not a profile one.
