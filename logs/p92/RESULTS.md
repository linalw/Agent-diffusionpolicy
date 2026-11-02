# P92 RESULTS — the scenario lane: the supply band's top moves the success rate, and one leg costs the adoption

Registrations: `logs/p92/PREREG.md` (md5 `07c54712…`, pinned before the first
run) and the amendment `logs/p92/PREREG_A1.md` (md5 `e5150253…`, pinned before
its runs). Census: `logs/p92/CENSUS.md` (+ `census.txt`, `chase.txt`). Battery:
`logs/p92/run_p92.sh` → `logs/p92/battery_driver.log`; A1:
`logs/p92/run_p92_a1.sh` → `logs/p92/a1_driver.log`. Readout:
`logs/p92/p92_report.py` → `logs/p92/p92_report.txt`,
`logs/p92/p92_a1_report.py` → `logs/p92/p92_a1_report.txt`. Gates:
`logs/p92/gates.sh` → `{C5,T5,C6,T6}.budgets`.

**Verdict in one line: the registered change converts 8 of 12 failures at both
seeds (28/40 → 36/40) and the pre-registered rule still returns NOT ADOPTED,
because one descent at seed 6 leaves its speed budget by 38 % (0.222 vs 0.161
m/s) and the same seed's branch carries a violent carry leg (419 N, a 1.3 m
pad-centre bookkeeping offset).**

## 0. Admissibility first: the controls are the tree, and they replay

`C5`/`C6` are the shipped scenario in this batch (no env but the instrumentation).
Both replay the P91 records on the **`[fruit]` stream**: **1033/1033** and
**970/970** lines identical **modulo one profile row's origin label**
(`FRUIT_DYNAMIC_PROBE_TICKS=60(explicit)` in P91's battery form vs
`…=60(two-line)` here - the resolved clock is identical; the field exists to
name the origin, and P87 recorded the same difference as its own A1). Their
counts are the record's: **16/20 and 12/20 = 28/40 = 70 %**, never-held 2 + 1 = 3,
`cnp` 2 + 7 = 9, chase set 4 + 7 = 11.

The `census.py` md5 in `header.txt` (`9e908d7d`) predates the final file
(`2a59e74d`): the edit is `main()`'s `--pre` block selection (the pre-P87 cells
the census reads separately). `parse()` and `classify()` - what every cell below
is read with - are untouched, and `census.txt`'s shipped-cell rows are identical
before and after.

## 1. The manipulation (PREREG §1)

| cell | `[supply]` row | delivered x min / p50 / max | > 0.36 | ≥ 0.39 |
| --- | --- | --- | --- | --- |
| C5 | `lateral x=0.20-0.36` | 0.1998 / 0.2861 / **0.3908** | 4 | 1 |
| **T5** | `lateral x=0.20-0.33` | 0.1781 / 0.2872 / **0.3616** | 1 | 0 |
| C6 | `lateral x=0.20-0.36` | 0.2055 / 0.2994 / **0.3597** | 0 | 0 |
| **T6** | `lateral x=0.20-0.33` | 0.2051 / 0.2941 / **0.3622** | 1 | 0 |

**F1a (the band took effect) PASS** - the build row prints `0.20-0.33` in both
treatment cells, and the supply draw is one `uniform(x_min, x_max)` whose *count*
does not change (`fruits.py:1417`), so the release schedule is the same stream.
**F1b (the delivered top ≤ 0.362) is a mis-specified bound and the record says
so**: the delivered x is the plan **plus a per-instance release offset**, so its
maximum is a distribution, not a bound. The controls show the offset directly -
C5's `0.36 → 0.3908` is **+31 mm** - and the treatment's `0.33 → 0.3622` is
**+32 mm**, i.e. the *same* offset with the band moved. T5 meets the number
(0.3616), T6 misses it by **0.2 mm** (0.3622). The mechanism clause is F1a; F1b
is recorded as a prediction error, not as a failed manipulation.

One cost is visible and reported rather than smoothed: **T5 delivers a strawberry
at x = 0.1781 m** (a −22 mm offset on a 0.20 draw). It is admissible for the
right arm (whose admission floor is 0.1730; the *left*'s is 0.1800) and it
**failed** (a `cnp`, one of T5's two). So the band's bottom is still exposed to
negative per-instance offsets: this change buys the top, it does not bound the
bottom. That is P50's territory (`FRUIT_RELEASE_OFFSET`, default off), not this
change's.

## 2. The primary: the class counts (PREREG §2)

| cell | placed | `cnp` | never-held | chase (`closed > 0`) | chased & failed |
| --- | --- | --- | --- | --- | --- |
| C5 | 16/20 | 2 | 2 | 4 | 4 |
| **T5** | **18/20** | 2 | **0** | **2** | 2 |
| C6 | 12/20 | 7 | 1 | 7 | 7 |
| **T6** | **18/20** | **1** | 1 | **3** | 2 |
| **pooled** | **28 → 36** (+8) | **9 → 3** | **3 → 1** | **11 → 5** | 11 → 4 |

**The registered prediction is met exactly on its class clause and exceeded on
its count clause** (predicted never-held `3 → 1`: seed 5 `2 → 0`, seed 6 `1 → 1`;
predicted placed 29-30, measured **36**). The never-held conversion is the one
the change was aimed at: at seed 5 both never-held presentations sit at the top
of the shipped band (`x = 0.3908` and `0.3857`) and **both are gone** - the
first-attempt kiwi is the cleanest read in the phase, because it is the *same
slot, same fruit, same release time, same instrumentation*, differing only in
its lateral position (`0.3908 → 0.3550` planned, `0.3908 → 0.3616` delivered):

```
C5 attempt 0 (left kiwi 5.4 cm, x = 0.3908): never_held  (catch-up residual > 6 mm, pads close on air)
T5 attempt 0 (left kiwi 5.4 cm, x = 0.3616): placed      (lift +0.29 m, 9.5 N)
```

**The count over-delivery is not the claim, and must not be quoted as a rate.**
The same control swings 16 → 12 between these two seeds, so 28 → 36 is a draw on
a moved branch; what is *branch-free* is the class set and the per-leg chase
read. But the class movement is not small either: the closed **loaded-slide**
class, which the record closed in its parameter space, falls **9 → 3 pooled** -
**all of it at seed 6 (7 → 1)**, with seed 5 *flat* at 2 → 2 but its *instances*
changed (the peach that failed twice becomes one peach `cnp` and one strawberry
`cnp` at x = 0.1781, the phase's one new low-tail presentation) - and the servo's
chase, which the census shows is the **signature** of every failure on this cell
(11/11, `p = 5.2e-09`), falls **11 → 5** with 4 of the remaining 5 chases still
failing. So the effect is in the mechanism the census named, not only in the
count - but it is **not uniform across the two seeds**, and the seed-5 flat
`cnp` count is stated rather than smoothed.

**Mechanism, as far as this phase measures it.** Both stations sit at a *band
edge* of the measured top-down reach at the shipped band's top: R10-A's map
(`logs/r10/A_RESULTS.md`) reads left x = 0.36 → y `0.00..+0.10` with the left
station at y = 0.00, and right x = 0.36 → y `-0.10..0.00` with the right station
at y = **-0.10**. At x ≤ 0.33 both stations are inside the neighbouring column's
band (x = 0.28: left `-0.05..+0.10`, right `-0.10..+0.05`). A fruit presented at
the band's top therefore asks the arm to close at the edge of what it can hold,
and the pinch that results is the one whose servo then chases. This is an
**interpolation between two measured columns** - not a new reach measurement -
and it is the named next spend if the first attempt's conversion is to be
generalised.

## 3. The delivered side (read, not gated)

| cell | pooled interval | p90 | left | right | window/min | batch/min | wall s | placed/min wall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C5 | 10.59 | 17.80 | 19.30 | 26.02 | 5.66 | 5.05 | 330.1 | 2.91 |
| **T5** | **10.13** | 16.80 | 19.13 | **21.64** | 5.92 | 5.66 | 342.4 | **3.15** |
| C6 | 11.08 | 17.60 | 24.38 | 18.26 | 5.41 | 3.94 | 304.0 | 2.37 |
| **T6** | **9.84** | 15.50 | 18.59 | 19.47 | **6.10** | 5.81 | 322.9 | **3.35** |

The interval falls at both seeds on both denominators, and the wall column
follows the sim clock (the walls differ by +3.7 % / +6.2 %, i.e. the harness, not
the cell). A supply change is not *supposed* to move the interval - the reading
is "flat within the branch spread, and any movement is a branch draw" - and that
is what this is: fewer failed attempts means fewer 10 s aborts, which is a
consequence of §2, not a throughput lever.

## 4. Guards (PREREG §3) - and the one that fails

| guard | reading | verdict |
| --- | --- | --- |
| G1 the `cnp` class must not rise | C5 2 → T5 2; C6 7 → T6 **1** | **PASS** |
| G2 the landing | 64/64 payload-present releases `on_belt=True` (16/16, 18/18, 12/12, 18/18) | **PASS** |
| G3 the motion budgets | T5 20/20 inside; **T6 leg 1 `|v|max` 0.222 vs 0.161 (38 % over)**. The *control* C6 is not clean either: its leg 12 reads 0.164 vs 0.160 (+2.5 %, the standing branch leg P86/P87/P88 recorded, D6); the treatment's is a different leg and 15x the excursion | **FAIL** |
| G4 no new failure reason | `fruit did not follow the gripper` ×3 + `grasped, not placed (no note)` ×1 - both recorded buckets (P88 saw the second in 3 of 4 cells); no new key | **PASS** |
| G5 the control replay | C5 1033/1033, C6 970/970 (modulo the origin label) | **PASS** |
| G6 20 attempts per cell | 4/4 cells at 20, no lost slot | **PASS** |
| G7 the tree is inert unset | `scripts/selfcheck.sh` **PASS** (0 failures, 1 skipped); `scripts/accept.sh` **7/10 + `fingerprint: matches configs/motion_reference.json` + `190: PASS`** (this tree's standing branch, `logs/p92/accept_noharm.log`) | **PASS** |
| G8 the supply audit | `python3 scripts/211_bed_audit.py` **ok (115 checks)** | **PASS** |

**G3's failure is one leg, and it is a real rough descent, not a print
artefact.** T6's second descent reads `|v|max 0.222` against its per-leg budget
0.161 with `a_med 0.97 m/s²` (the healthy legs sit at 0.22-0.26) and the leg is
marked `rough`. The budget was **not** re-tuned (AGENTS §2 forbids admitting a
configuration by moving the budget), so the VERDICT below follows the
pre-registered rule.

**A second, unregistered red flag rides the same seed and is reported because a
guard should not hide it**: T6's branch carries **one violent carry leg** - a
right `grasp_lift` with `fmax = 419.25 N`, `in-hand |v|max = 1.545 m/s`,
`hold_drift 110.8°`, `cone = 6.18x` and three `carry-assist` rows whose stored
pad centre sits **up to 1313 mm** from the measured pads. Neither control has a
leg above 1.57x or any such offset (0 rows > 500 mm in C5/C6/T5). The cone is
*reported, not gated* on the dynamic line (AGENTS §2, its escapes are the failure
mechanism), so it does not change the verdict on its own - but it is the reason
to call seed 6's branch *disturbed* rather than *clean*, and it is named as the
first thing an adoption phase must diagnose.

## 5. Verdict (PREREG §4's rule, applied to the numbers above)

The rule: adopt only if the pooled never-held class falls to ≤ 1 **and** neither
seed rises **and** the placed count does not fall at either seed **and** G1-G8
all pass.

* never-held `3 → 1` (seed 5 `2 → 0`, seed 6 `1 → 1`): **the class clause passes**;
* placed `28 → 36`, no seed below its control (`16 → 18`, `12 → 18`): **passes**;
* G1, G2, G4-G8 pass; **G3 fails** (T6's leg 1, 38 % over its descent budget).

**→ NOT ADOPTED.** `FRUIT_SUPPLY_X_MAX` stays **0.36**; `configs/` is untouched
and no reference is re-recorded. The measured arm reproduces as
`FRUIT_SUPPLY_X_MAX=0.33` (env only, no code change), which is what any re-entry
runs.

**Why the rule was right to stop it, said plainly.** The gain is the largest this
record has measured from a scenario change (12 → 4 failures at both seeds), and
it is exactly the kind of change that must not be shipped on one batch: the
branch it buys is *not* clean (one rough descent, one 419 N contact episode), and
the count is a draw on a moved branch. The pre-registered rule exists to stop the
*number* from being the argument.

**The re-entry, named and priced.** A follow-up registration with, in order:
(1) **diagnose T6's leg 1 and the 419 N leg** (the first is a descent profile
question - is it the catch-up chasing a moved fruit, or the pre-pose? the second
is the `carry-assist` bookkeeping: `|offset| = 1313 mm` is a hand-frame
pathology, and the `stored pad centre … re-anchoring` rows are the same family);
(2) a **third seed** (the two seeds agree on 18/20, which is suspiciously tight
and deserves a fresh draw); (3) if the branch comes back clean, the full package
- both motion references re-recorded from same-batch runs, the acceptance and the
two-line gate re-based, every store's provenance (the supply band is **not** in
`assets.scene_provenance` today: a store under 0.20-0.33 and one under 0.20-0.36
are indistinguishable - the `supply.x_min/x_max` field must go in before any
recollection), and the direct/policy interface measured (it builds its own supply
profile from the same `SupplyPlan.from_env`, so it would inherit the band).

## 6. What this phase settles that is not about this lever

1. **The scenario lane was not empty.** The census said the addressable class was
   3 attempts and the record's own candidate (P38b's low-tail margin) had zero
   events; the *top* of the band turned out to carry the closed class's rate as
   well - the delivered band's top column is where the pinch is taken at the
   reach edge. So the record's "the closed class is closed" is true of the
   *cell's* parameter space (force, seat, pads, attitude, height, station, speed,
   clock) and **not** of the *presentation*: which lateral column the fruit is
   presented in moves the same class, 9 → 3.
2. **The failure signature is the servo's chase** (`closed > 0`): 11/11 failures
   on the shipped cell and 14/14 on the pre-P87 block, against 1/55 without it
   (`p ≈ 5e-09`). That is the census's most general finding and it is the reason
   PREREG_A1 exists (§7 below).
3. **Starvation, the diversion and P38b's low tail are not this cell's loss**
   (0 lost slots, a slot-level divert, 0 low-tail events) - measured so nobody
   re-derives them.

## 7. Amendment A1 — the servo's contact gate: the chase is the *signature*, not the cause

Registration `logs/p92/PREREG_A1.md`; readout `logs/p92/p92_a1_report.txt`;
`FRUIT_FORCE_REENTRY=1` (default **0**, P7's "FARM Port A": the servo runs its
integral law only while the contact estimate is confident, and **holds** the gap
instead of chasing when it is not), cells `R5`/`R6` against the same `C5`/`C6`.

| cell | placed | `cnp` | never-held | chase (`closed > 0`) | gate | interval | window/min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C5 | 16/20 | 2 | 2 | 4 | - | 10.59 | 5.66 |
| **R5** | **16/20** | **3** | **1** | **1** | entries 31 / 890 ticks withheld | **11.59** | 5.18 |
| C6 | 12/20 | 7 | 1 | 7 | - | 11.08 | 5.41 |
| **R6** | **12/20** | **5** | **3** | **2** | entries 29 / 1730 ticks withheld | **13.48** | 4.45 |
| pooled | **28 → 28** | 9 → 8 | 3 → 4 | **11 → 3** | engaged | worse at both | worse at both |

**The gate works exactly as designed and the success rate does not move.** The
manipulation is clean on all three of its own reads: the diag rows report
**31 and 29 force-mode entries** with **890 and 1730 withheld chase ticks**; the
chase set falls **11 → 3**; and the *held-leg* pinch is untouched (median
`force_min` **9.42 / 9.36 / 9.72 / 9.10 N** in C5/R5/C6/R6 - the P41 plateau on
every cell, G1 PASS). The landing is clean (28/28 payload-present releases on
belt), and **both treatment arms' descent budgets are clean - 20/20 legs each,
0 over budget** (so arm 2 does not disturb the motion the guard failed arm 1 on).
And the failures **re-distribute rather than disappear**: `cnp` 9 → 8
(seed 5 **up** 2 → 3, seed 6 down 7 → 5) against never-held 3 → **4** (seed 5
down 2 → 1, seed 6 **up** 1 → 3), with five `grasped, not placed (no note)` rows
on the treatment arms.

**So the census's strongest read is a symptom, and this arm is what proves it.**
With the chase withheld the payload still leaves the pinch (or was never in it),
and the attempt then presents one phase later as never-held: the same physical
event, a different label. The count is flat at **both** seeds (16 → 16, 12 → 12;
pooled 28 → 28 against the 30 bar) and the interval is **worse** at both seeds
(10.59 → 11.59, 11.08 → 13.48): a withheld chase is a grip held at the gap it
had, and the extra ticks are spent not recovering. **G2 fails at seed 5**
(`cnp` 3 > the 2 bound), so:

**→ NOT ADOPTED.** `FRUIT_FORCE_REENTRY` stays **0**; `src/` and `configs/` are
untouched.

**What that leaves, and why it strengthens §5's re-entry.** The two arms are
complementary and they point at the same object. Arm 1 moves the *presentation*
and converts 8 attempts with both classes falling (9 → 3, 3 → 1) at both seeds.
Arm 2 moves the *recovery* and converts none, moving the same failures between
labels. A presentation that seats the pinch properly needs no recovery; a
recovery loop cannot un-lose a payload. The re-entry's ranked first item is
therefore **the presentation** (the band, with T6's leg 1 and the 419 N leg
diagnosed), not the servo.

One more measured detail worth keeping: with the gates on, the branch **re-draws
into the high-x tail** - R5 presents a left kiwi at **x = 0.405** (a `cnp`) and R6
at **x = 0.388 / 0.364** - which is precisely the zone arm 1 removes. The two
levers are not interchangeable: a *recovery* change lets the presentation wander;
a *supply* change bounds it.

## 8. Pins and files

No `src/`, `configs/`, `datasets/` or checkpoint change: `tasks.py` `7ba4bb58`,
`bimanual.py` `9b7fc33f`, `fruits.py` `dcabe16b`, `scene.py` `3681aad3`,
`assets.py` `540406fa`, `control.py` `9384ff4f`, `conveyor.py` `fb2c58c6`,
`rl_env.py` `e618ae67`; `configs/motion_reference.json` = `..._twoline.json` =
`423896f7`, `..._single.json` = `8952c320` (all untouched, nothing re-recorded);
ckpt `moe_v13s` `61da390a`. New files under `logs/p92/`: `census.py`
`2a59e74d`, `census.txt`, `chase.py` `b36a1c75`, `chase.txt`, `CENSUS.md`,
`PREREG.md` `07c54712`, `PREREG_A1.md` `e5150253`, `p92_report.py`
`aebc0a3b`, `p92_a1_report.py` `2d39924c`, `run_p92.sh`, `run_p92_a1.sh`,
`chain_a1.sh`, `gates.sh`, `header.txt`, `header_r.txt`, the cells
`{C5,T5,C6,T6,R5,R6}.{log,stamps,driver,budgets}`, `accept_noharm.log`,
`selfcheck.log`, `battery_driver.log`, `a1_driver.log`, `p92_report.txt`,
`p92_a1_report.txt`.

## 9. Deviations, all recorded

* **D1** `PREREG.md` registered the supply band's top from the shipped-cell
  census *before* the pre-P87 block was read; that block (`logs/p84/{D5,D6}`)
  showed the never-held class is not x-clustered, so the registration is
  **published as measured** and the mechanism lever was registered separately as
  `PREREG_A1` (pinned before its own runs). Neither registration was edited
  after its runs.
* **D2** `F1b`'s delivered-max bound (`≤ 0.362 m`) is **mis-specified**: the
  delivered x is the plan plus a per-instance offset (the control's own
  `0.36 → 0.3908` is +31 mm), so its maximum is a distribution. T6 reads
  `0.3622` (+0.2 mm). `F1a` (the build row prints `0.20-0.33`) is the
  manipulation check and it passes.
* **D3** the fingerprint clause of `190`/`105` is **recorded, not gated**: every
  20-attempt two-line reference in the tree predates P87's release clock
  (`logs/p80/…p80_20.json`, `logs/p86/…C6_20.json`), so every post-P87 cell -
  the controls included - reads `DIFFERS` by construction (P91 recorded the same
  clause). The control proof is the **line-identity replay** against
  `logs/p91/{C5,C6}.log` (G5). The first `gates.sh` form wrote `{C5,T5}.gate`
  with `190`'s FAIL *on that same fingerprint clause*; it was superseded inside
  this phase and the two files were removed so a stale `190: FAIL` cannot be
  misread - the `.budgets` files carry both the budget verdicts and the recorded
  fingerprint clause.
* **D4** `census.py` was edited after `header.txt` was pinned (`main()`'s
  `--pre` cell selection; `parse`/`classify` untouched), and `p92_report.py`
  evolved after the same pin (the guard readers and the replay normalisation).
  The final md5s are in §8; the cell logs are unaffected.
* **D5** `chase.py` is a **new instrument created after `PREREG.md`** (it is the
  readout `PREREG_A1` registers). Its md5 is pinned in `header_r.txt` and in
  §8; the shipped-cell rows it reads (`chase.txt`) are from logs that no run in
  this phase writes.
* **D6** the control at seed 6 carries its **own standing over-budget leg**
  (leg 12: `0.164` vs `0.160`, +2.5 %) - the same leg P86/P87/P88 recorded as a
  branch fact. The treatment's is a *different* leg (leg 1) at **+38 %**. The
  guard comparison is stated against that, not against a hypothetical clean
  control.
