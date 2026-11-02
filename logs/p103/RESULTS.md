# P103 results — the sim-only perfect-detector re-grip **converts nothing, destroys two placements, and the tree's own 8 mm slip gate is why**

**One default-off knob, no control law of its own, nothing adopted.** The action
is the tree's **shipped** slip re-seat (`_carry_leg`'s `slip_enabled` block),
reached from P102's patch channel instead of from the 25 mm `FRUIT_SLIP_TRIGGER`;
the trigger is `dc >= 2.12 mm` on a **seated** leg (P102's own seat test); the
scope is a two-line session and `FRUIT_SLIP_REGRIP` unset or `0` is the shipped
path **bit for bit** (proved: §7 G1/G2). `configs/` untouched, no reference
re-recorded, and none is owed.

---

## 0. Verdict

`docs/PLATFORM_SURVEY.md` §5.1 asked the *reaction* question after P102 settled
the *signal*: **does catching the loaded slide at 2.12 mm convert `cnp`?**
Measured on four seeds × 20 attempts (80 attempts, two fresh seeds per P93's
rule):

| read | bar | measured | verdict |
|---|---|---|---|
| **the conversions** | the only number that matters | **1 of 12 re-seated legs placed**; on the **7 same-instance pairs: 0 of 5 control `cnp`s converted, 2 of 2 control placements destroyed** | **null + harm** |
| **P2a** (survey literal, seeds 5+6, 40) | `cnp` <= 4 **and** placed +8 points | `cnp` **7 -> 3** **and** placed **29/40 -> 29/40, +0.0 points** | **FAIL** (the count clause passes only because the class moved) |
| **P2b** (pooled, 80) | `cnp` **-30 %** and placed **+8 points** | `cnp` **11 -> 9 (-18 %)** and placed **59/80 -> 54/80 (-6.2 points)**, Fisher **p = 0.49** | **FAIL** on both |
| **P3** (the price) | interval <= **+5 %** | **11.04 -> 12.72 s (+15.3 %)**, worse at **4 of 4** seeds (+5.1 / +16.6 / +6.2 / +31.8 %) | **FAIL** |

**So the survey's stage (i) closes: DETECTED BUT NOT CONVERTIBLE.** P102's
mechanism stands untouched - the patch really does see the slide 21-113 ticks
early, and this phase did not test that. What dies is the premise that *acting*
on it at 2 mm buys the placement.

**And the more useful half of the answer is *why*, which the ledger measured:**
the re-seat does hold the payload (12 legs: `clean_slip_max` 5.7-437 mm against
the controls' 100-2372 mm, 7 of them under P74's "the payload never left"
100 mm) - but the **two-line session's own P10-C carry monitor is armed with an
8.0 mm confirm gate**, so an attempt whose lift leg reads `clean_slip_max >=
8.0 mm` is truncated at the leg boundary and cannot place. **1 of 12 legs stayed
under 8 mm, and that one placed.** The reaction's ceiling on this tree is
**8 mm, not 100 mm**.

**The sensor answer follows, and it is "no".** The perfect detector did not pay,
so a real pad cannot be justified by this reaction. What a pad *can* still be
justified by is the answer P102 gave (the slide is visible for 0.17-0.94 s), and
that is a **supervision/labelling** case, not a reflex one. Nothing ships; the
knob stays opt-in and the decision is the owner's.

---

## 1. The build, and what it costs when it is off

**The trigger** (`_carry_leg`, inside the W8-B `guard_armed` block): each armed
tick reads the patch centroid's displacement `dc` since the leg's first tick -
the same number P102's `[tactile]` row prints - and requires **P102's seat**
(`max(f0, f1) > 1.0 N` **and** `edge > -TACTILE_PAD_HALF_LONG`, so the arm
carrying an empty hand cannot trip it) plus the shipped abort ceiling
`slip <= FRUIT_SLIP_REACT_MAX` (60 mm). It fires on **every** tick the trigger
holds - the shipped block's own temporal shape.

**The action** is not new code in the control sense: `_carry_leg` already carries
a slip re-seat behind `FRUIT_SLIP_RECOVERY`, and it computes
`target = fruit - rot @ slip_ref` (the pad centre that restores the leg-start
relation), applies `correction = target - pads` in one go, **re-bases the leg's
remaining command list** onto it and re-engages the force servo. The `[regrip]`
branch runs those same six expressions. What the knob changes is only the
**trigger**: the shipped block's `not hand_is_jaw` gate exists because it was
written for the kinematic pad hand, and on the OpenArm hand the pads *are* the
robot's fingers, so the relation has to be restored by re-basing the arm's own
command list - which is exactly what the block does.

**Off path, proved inert** (§7 G1/G2): `FRUIT_SLIP_REGRIP` unset reads
**419/419** `[fruit]` lines identical to the pre-phase acceptance record
(`logs/p98/accept_revert.log`, `fingerprint: matches`, `190: PASS`, **8/10**),
and the batch's own controls replay P102's current-tree controls **825/825**
(seed 5) and **837/837** (seed 6). So the A/B is the action, not the
instrumentation and not the batch.

**Read set, declared** (AGENTS §2): one `jaw_positions()` (the two finger prim
world poses - the same read `jaw_separation()` already takes every guarded tick)
plus one tactile set per armed tick, **no `ik_step` work and no articulation
read**. P95 proved a 3-prims-per-arm read set inert on this line (970/970,
974/974), and the read set here is inside it. With the knob unset there is **no
per-tick work at all** - the trigger is one bool.

## 2. The trigger ledger

Four treatment cells, 80 attempts, **137 carry legs, 12 re-seated**:

| cell | legs | re-seated | re-seat ticks | placed among them |
|---|---|---|---|---|
| `T5` | 35 | 2 | 100 | 0 |
| `T6` | 35 | 2 | 30 | **1** |
| `T101` | 36 | 4 | 379 | 0 |
| `T202` | 31 | 4 | 292 | 0 |
| **pooled** | **137** | **12** | **801** | **1** |

```
arm   leg         attempt  t/tot    dc_mm corr_mm seat_f seat_edge seat_frac fires slip_max outcome
left  grasp_lift   T5 17   39/173    2.30    2.57  10.90   +11.3   0.938    63   153.1   cnp
left  grasp_lift   T5 18   28/167   14.94   27.47   2.38   -31.9   0.000    37   218.0   no-grasp
left  grasp_lift   T6  2   59/159    3.07    3.06   2.85   +10.5   0.604    25     8.3   cnp
right grasp_lift   T6  9   24/178    5.74    5.99   4.73   +20.0   0.771     5     5.7   PLACED
left  place0      T101 4  163/399    2.20    8.90  14.42   +10.7   0.771   189   256.7   cnp
right place1      T101 5    7/315    2.31    3.17  15.31    -5.6   0.354    20   437.4   cnp
right grasp_lift  T101 6  100/204    2.32   14.93  21.52    +9.3   0.833    17   232.1   cnp
left  grasp_lift  T101 14   9/162    2.38    7.26   9.80    -5.9   0.375   153    22.7   no-grasp
left  grasp_lift  T202 0    5/168    2.14    2.79  11.03    -8.8   0.292   163    11.9   no-grasp
left  grasp_lift  T202 2    7/164    2.39    3.07   2.89    +7.5   0.500    11    10.0   cnp
left  grasp_lift  T202 13  98/160    2.92    5.01   9.53   +11.7   0.708    57    21.0   cnp
left  grasp_lift  T202 17  93/160    3.15    3.21   8.73   +12.0   0.729    61    17.8   cnp
```

**The trigger behaves as registered on 11 of 12 legs**: the first fire lands at
`dc` **2.14-5.74 mm** (median **2.38 mm**) - P102's 2.12 mm crossing, at the pad
scales it was measured on - and **5-163 ticks into its leg** (median 49). It
also fires **often** (5-189 re-seats per leg, median **59**), which is the
shipped block's per-tick shape, not a defect.

**The one trigger defect, recorded**: `T5 attempt 18` first fired at
`dc = 14.94 mm` with `seat_frac = 0.000, seat_edge = -31.9 mm`, i.e. the leg was
**not seated until 15 mm of walk had accumulated**. The reference is the leg's
**first tick**, and P102's seat test is evaluated *now*: on a leg that starts
unloaded (`f = 0 N`), `dc` accumulates unobserved and the first legal fire is
late. Every leg in P102's corpus seated at tick 0, so this could not appear
there. It is a **coverage hole, not a threshold one** - and it matters, because
that leg (a `no-grasp`) is one of the 4 legs that stayed under 100 mm and still
failed.

## 3. The conversions

Joined per leg to its attempt (P102's join: a side's k-th `grasp_lift` leg *is*
that side's k-th attempt - checked, one `[run]` row per `grasp_lift` per side),
then to the same index on the **same seed's control**:

| seed | attempt | arm | leg | fruit | treatment | control | same instance |
|---|---|---|---|---|---|---|---|
| 5 | 17 | left | `grasp_lift` | lychee | **fail** (`cnp`) | **PLACED** | **yes** |
| 5 | 18 | left | `grasp_lift` | tomato | fail (`no-grasp`) | strawberry PLACED | no |
| 6 | 2 | left | `grasp_lift` | peach | fail (`cnp`) | peach fail (`cnp`) | **yes** |
| 6 | 9 | right | `grasp_lift` | kiwi | **PLACED** | strawberry PLACED | no |
| 101 | 4 | left | `place0` | kiwi | fail (`cnp`) | kiwi fail | **yes** |
| 101 | 5 | right | `place1` | apple | fail (`cnp`) | apple fail | **yes** |
| 101 | 6 | right | `grasp_lift` | lychee | fail (`cnp`) | lychee fail | **yes** |
| 101 | 14 | left | `grasp_lift` | kiwi | fail (`no-grasp`) | lychee PLACED | no |
| 202 | 0 | left | `grasp_lift` | kiwi | fail (`no-grasp`) | kiwi fail | **yes** |
| 202 | 2 | left | `grasp_lift` | apple | **fail** (`cnp`) | **PLACED** | **yes** |
| 202 | 13 | left | `grasp_lift` | peach | fail (`cnp`) | kiwi fail | no |
| 202 | 17 | left | `grasp_lift` | peach | fail (`cnp`) | lychee PLACED | no |

**On the 7 same-instance pairs:**

* **0 of 5** control `cnp` attempts converted (seeds 6/2, 101/4, 101/5, 101/6,
  202/0) - the class the action exists for;
* **2 of 2** control **placements** it touched were **destroyed** (seed 5/17
  lychee, seed 202/2 apple).

The other 5 pairs are **not pairable**: the branches diverge as soon as the
action moves a command (P92/P93's rule), and two of those five show the control
placing while the treatment's *different* instance failed - which is the branch,
not the action.

**The harm is measured, the same instance, and it is the false-positive class
P102 warned about.** Seed 5 attempt 17 is the cleanest single witness on this
tree (identical fruit, identical slot, one arm difference):

| | control (`C5`) | treatment (`T5`) |
|---|---|---|
| `clean_slip_max` | **5.8 mm** | **153.1 mm** |
| `force_min` | 6.17 N | **0.00 N** |
| `fmax` | 88.08 N | **117.87 N** |
| `sep_max` (around a 29.6 mm fruit) | 41.9 mm | **98.4 mm** - the pads at their open stop |
| outcome | **PLACED** | fail |

P102 registered `dc >= 2.12 mm` as a cheap trigger because *2 of 60 held legs
tripped and both placed*. That number was measured **without acting**. Acting on
that population is what costs the placement: the re-seat drives the pads against
a payload the pinch was holding and pries them to their stop. **The
false-positive cost of this trigger is not its clock (it has none) - it is its
physics.**

## 4. P2 — the class does not convert, it relabels

| | control (C) | treatment (T) |
|---|---|---|
| placed | **59/80 = 73.8 %** | **54/80 = 67.5 %** (**-6.2 points**, Fisher p = 0.49) |
| `cnp` | 11 | 9 (p = 0.81) |
| never-grasped | 10 | **17** (p = 0.20) |
| `force_min == 0` legs | 21 | 23 |
| per-seed placed | 17, 12, 15, 15 | 14, 15, 14, 11 (worse at 3 of 4) |

**The survey's P2a sub-clause passes for the wrong reason.** On the survey's own
two-seed form `cnp` falls **7 -> 3**, inside its "<= 4 of 40" bar - but **placed
does not move at all** (29/40 -> 29/40) because 4 of those `cnp`s became
**never-grasped**: the payload was lost *before* the lift's peak rather than
during the carry. The action moved failures **between labels** without
converting one, which is the shape P92 measured for the force servo ("the chase
is the signature, not the cause") with a harm added.

Note the pooled count differences are **not significant at n = 80** (placed
p = 0.49, never-grasped p = 0.20): they are the delivered numbers the survey's
P2/P3 are written in, and they are mostly **branch**, since the action only
touched 12 legs. The **attributable** evidence is §3's paired instances.

## 5. P3 — the price

| | control | treatment | delta |
|---|---|---|---|
| interval (pooled per seed) | 9.37 / 11.08 / 12.16 / 11.53 s | **9.85 / 12.92 / 12.92 / 15.19 s** | **+5.1 / +16.6 / +6.2 / +31.8 %** (mean-of-seeds **+15.3 %**) |
| placement-window rate | 6.40 / 5.41 / 4.93 / 5.20 | 6.09 / 4.64 / 4.64 / 3.95 | mean **5.49 -> 4.83** |
| batch-span rate | 5.63 / 3.94 / 4.87 / 4.98 | 4.74 / 4.51 / 4.60 / 3.45 | mean **4.86 -> 4.33** |
| `s/attempt` | 9.10 / 9.10 / 9.20 / 9.00 | 8.90 / 10.00 / 9.10 / 9.60 | mean **9.10 -> 9.40 (+3.3 %)** |
| wall/pick | 16.21 / 15.39 / 16.76 / 15.47 | 15.44 / 16.74 / 16.67 / 15.93 | mean **15.96 -> 16.20 (+1.5 %)** |
| `placed/min` wall | 3.70 / 3.90 / 3.58 / 3.88 | 3.89 / 3.58 / 3.60 / 3.77 | mean **3.77 -> 3.71 (-1.6 %)** |

**The action costs no tick by construction** (it moves the command, not the
clock), so the interval movement is **not a clock cost**: it is the branch. The
re-seated attempts fail (12 legs, 1 placed) and a failed attempt re-draws the
slot loop, which is P83/P88/P89/P91's "a block delta is not deliverable on this
cell" one level down. The `s/attempt` figure (+3.3 %) is the fairest clock read
and it is small; the **delivered** rate is what P3 registers, and it fails at
every seed.

## 6. The false-positive ledger, and why the ceiling is 8 mm

P102's reference: of 60 held legs, 2 move `dc >= 2.12 mm` and both placed. In
this batch the treatment re-seated 12 legs; **7 of them stayed under P74's
"the payload never left" 100 mm** (5.7, 8.3, 10.0, 11.9, 17.8, 21.0, 22.7 mm) -
i.e. the re-seat *did* hold them. Only **1 of those 7 placed**.

The reason is measured, not argued:

* the two-line session's **P10-C carry monitor is armed by default** with
  `FRUIT_CARRY_MONITOR_CONFIRM_MM = 8.0` (`_resolve_carry_monitor_knobs`), and a
  leg reading `clean_slip_max >= 8.0 mm` marks the attempt for the monitor's
  **leg-boundary skip** - the place leg does not run;
* of the 12 re-seated legs **1 stayed under 8 mm** (5.7 mm, seed 6 attempt 9) and
  it **placed**; the other 6 "held" legs sat at 8.3-22.7 mm and were truncated;
* so on this tree the reaction's **conversion ceiling is 8 mm of residual slip**,
  and a re-seat that lands at 10-23 mm cannot convert even though the payload is
  still in the pinch.

**That is a descriptor, not a result** (the 8 mm gate was not part of the
registration): it says what a *future* reaction would have to achieve, and it
also says the class boundary is a **harness constant**, not physics. A phase
that wanted to spend this would have to register the monitor's gate as part of
the lever - which is a different cell (and a different, larger change: the
monitor is what stops the cell paying for a lost attempt).

## 7. Guards

| guard | clause | result |
|---|---|---|
| **G1 off-path inertness** | acceptance, knob unset: `fingerprint: matches`, `190: PASS`, stream byte-identical to the pre-phase record | **PASS** - **8/10**, `matches`, `190: PASS`, **419/419** lines identical to `logs/p98/accept_revert.log` (sealed: P100's park row dropped) |
| **G2 the archived controls are admissible** | `C5`/`C6` replay `logs/p102/{C5,C6}.log` on the `[fruit]` stream | **PASS** - **825/825** and **837/837** |
| **G3 landing** | every payload-present release `on_belt=True` | **PASS** - **113/113** on the belt, **0** off; 2 upstream-lost rows reported apart (T5 1, C101 1) |
| **G4 descent budgets** | budgets-only (`105 --min-success-rate 0.0`) on every cell, over-budget legs named | **4 named legs of 160**, and **arm-symmetric: 2 controls, 2 treatments** - `C6` leg 12 **0.164/0.160** (+2.5 %, the standing branch leg P86/P87 recorded), `C101` leg 9 **0.224/0.160** (+40 %), `T101` leg 9 **0.261/0.160** (+63 %), `T202` leg 11 **0.226/0.161** (+40 %). **The budget was not re-tuned** (AGENTS §2); this is P93's own finding - an over-budget descent is a stochastic branch property at ~2.5 % of legs in either arm, uncorrelated with the catch-up |
| **G5 no new failure reason** | treatment keys a subset of the control's | **FAIL by its letter at seeds 5 and 202**: the bucket `grasped, not placed (no note)` appears in the treatment only. It is the bucket P100's A4 already recorded as present in two *controls* of the same battery, i.e. a key-level reading that a branch can move; **recorded, not re-read** |
| **G6 accounting** | placed + `cnp` + never-grasped == attempts, no lost slot, 20 per cell | **PASS** - 20/20 on all eight cells, no slot lost |

`logs/p103/gates.sh` exits **1**, and the only failing clause in it is **G4's
four named legs** (2 of which are controls): the script's own rule is "any
over-budget leg fails", which is stricter than the registered G4 ("name it with
its seed, arm and ratio"). Recorded as a deviation in the script, not in the
result.

## 8. Scope, and the sensor decision

**Transfers.** The reaction's *reach*: a 2.12 mm patch trigger fires 5-163
ticks into the leg on all 12 legs it hit, the re-seat holds the payload (7 of 12
under 100 mm), and the delivered outcome is decided by the harness's own 8 mm slip
gate, not by the pinch. Also the **harm**: on the false-positive class (a leg
whose slip the pinch survives) the re-seat drives the pads and loses the
payload - `sep_max` to the 98.4 mm open stop under 117.87 N against the control's
41.9 mm and 88.08 N on the same 29.6 mm fruit.

**Does not transfer.** Whether a **soft** pad images a 2.12 mm centroid shift -
unchanged from P102, and irrelevant to this result: the sim's patch is derived
from the ground-truth pose, so this is a **perfect detector** and the reaction
failed *with* perfect information. A real sensor can only do worse on the
trigger and cannot change the action's physics.

**The sensor purchase is not justified by this outcome.** Spending ~$1,020 on two
GelSight Minis would buy the channel P102 already showed is *fast enough*; this
phase shows the thing that channel would drive does not pay. What is left of
stage (i) is P102's own case - the slide is visible for 0.17-0.94 s, which is a
**supervision/labelling** use (and a fault log), not a reflex. **The owner's
decision is whether to buy a pad for that**, and this phase does not argue for a
reflex.

**Named next items** (not built, and deliberately not registered):

1. **The 8 mm gate is the binding term.** A reaction would have to keep
   `clean_slip_max < 8.0 mm` to let the place leg run, and the one leg that did
   (5.7 mm) placed. Whether a *bounded, one-shot* correction can achieve 8 mm
   without the prying feedback is an open question; the per-tick re-fire measured
   here cannot.
2. **The false-positive class has to be separated first.** P102's own channel
   cannot tell "the pinch will survive this" from "it will not" at 2 mm - 7 of 12
   re-seated legs were going to be fine, and 2 of those 7 were placements.
3. **Do not re-tune the descent budget** for the four over-budget legs (P93's
   precedent).

## 9. Deviations, recorded

* **D1 - the build smoke changed the action's temporal form.** The first build
  re-seated at most once per 40 ticks. `logs/p103/smoke.log` (6 attempts) read
  the payload walking **3.07 -> 30.41 mm inside that window** (0.33 s at
  ~80 mm/s), so the registered form is the shipped block's per-tick shape
  (`PREREG.md` §0.2, pinned before any 20-attempt cell). No count, rate or
  interval is taken from the smoke.
* **D2 - G1's registered letter named "7/10".** The record on this tree is
  **8/10** (P98's own count), and the clause's substance (byte-identity) passes
  at **419/419**. The count in `PREREG.md` §7 was a mis-citation; recorded here,
  not re-read.
* **D3 - the trigger's seat reference is the leg's first tick**, so a leg that
  starts unloaded accumulates `dc` unobserved and its first legal fire can be
  late (measured once: 14.94 mm). Recorded as a coverage hole (§2).
* **D4 - `FRUIT_PLACE_TRACE=1` was added to both arms before the first cell**
  (it is G3's `on_belt` source), because the PREREG's G3 requires it. Both arms
  carry it, so the A/B is unaffected.

## 10. Reproduction

```bash
bash logs/p103/run_p103.sh          # C5,T5,T6,C6,C101,T101,T202,C202 (~50 min)
python3 logs/p103/p103_report.py ledge logs/p103/T5.log logs/p103/T6.log \
    logs/p103/T101.log logs/p103/T202.log > logs/p103/ledger.txt
python3 logs/p103/p103_report.py conv logs/p103/C5.log logs/p103/T5.log \
    logs/p103/C6.log logs/p103/T6.log logs/p103/C101.log logs/p103/T101.log \
    logs/p103/C202.log logs/p103/T202.log > logs/p103/conv.txt
python3 logs/p103/p103_report.py ab (the same eight) > logs/p103/ab.txt
python3 logs/p103/p103_report.py --landing (the same eight)
python3 logs/p103/p103_report.py --same logs/p102/C5.log logs/p103/C5.log   # G2
python3 logs/p103/p103_report.py --same logs/p98/accept_revert.log \
    logs/p103/accept_final.log                                              # G1
bash logs/p103/gates.sh             # G1-G4 (rc=1 on G4's four named legs)
python3 scripts/256_p103_regrip_selftest.py
scripts/selfcheck.sh
```

Pins: `tasks.py` **`9e3e657b`** (the cells ran on **`73a90461`**; the close-out
is a docstring-only edit, and the final tree's acceptance is **419/419**
identical to the pre-phase record, which is what proves it inert), `rl_env.py`
`TASKS_MD5` follow `b257687d` -> `9e3e657b`, `tactile.py` `dee9121a`,
`scene.py` `472bfb6c`, `assets.py` `eb30c77a`, `control.py` `9384ff4f`,
`bimanual.py` `9b7fc33f`, `fruits.py` `dcabe16b`,
`scripts/20_pick_place.py` `3d34342b`,
`logs/p103/p103_report.py` **`e52de9a5`** (batch-time; the `conv`/`ledge`
reader additions are read-side only and re-run over the same logs),
`scripts/256_p103_regrip_selftest.py`, `scripts/selfcheck.sh`,
`logs/p103/gates.sh`; `logs/p103/PREREG.md` **`73bdf35e`**; references
`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`**, all **untouched** - **no reference was
re-recorded and none is owed** (the knob is default-off and G1/G2 are the proof);
ckpt `moe_v13s` `61da390a`. Evidence `logs/p103/`.
