# P131 - the ring's over-closure: is it the aperture **law** or the **drive**?

Owner's question, after P130: `cage4` + `FRUIT_DYNAMIC_CLOSE_FREEZE=0` converts the
rate (+28.7 points, p = 0.0135) but the record's over-closure count (22/40, the
measured aperture below `dia - 4 mm`) is now the dominant failure. Is the ring
driven inside the fruit by the **force-capped drive**, or is the **aperture law**
wrong (the horizontal extent at the freeze, wrong for a tilted ellipsoid)?

This file is pinned **before any 20-attempt cell** (`PREREG.md5` is the md5 of
this text). The offline census that decides the question is `census.py` /
`census.txt` and is already written; it reads only records on disk.

## 1. The census, and what it already fixes

`python3 logs/p131/census.py logs/p130/F5.log logs/p130/F6.log
logs/p108/B_s5.log logs/p108/B_s6.log` reads 72 `[cage]` rows, joins each to its
attempt's `[motion] approach ... end=`, its `grasp_lift` `[carry]` row and its
`[run] attempt` outcome, and recomputes the fruit's extents from the pool's own
mesh profiles (`meshes.axis_extent`):

* **The command is the two-phase ramp's load target.** On the 40 freeze-off rows
  `aper / (0.97 x min(radial, axial))` is in **[0.96, 1.02] on 38/40**, p50
  **0.998**.  The freeze-on controls read 1.09-1.66 (the first-contact freeze
  holds an aperture too wide) - which is why the freeze was the rate term.
* **The ring's own law never reaches the close.** `pinch_width` returns
  `0.98 x the widest horizontal extent`, but the dynamic path's `deep` is
  `0.97 x min(radial, axial)` - the **height** on an upright flat fruit - and
  with the freeze off the ramp runs to that end.  The over-closure rows read
  `aper / R` p50 **0.874** (12.6 % inside the fruit's width).
* **Two metric artefacts inflate P130's 22/40.**
  1. The strawberry's class `dia` is its **height**: `R / dia = 0.792`, so
     `aper < dia - 4 mm` calls every strawberry grasp over-closed although
     `aper / R` is 0.95-0.98.  Five of the 22 are this.
  2. A ring that **missed** the fruit (`off > 15 mm` at the close's end) also
     reads `aper < dia - 4 mm`, but there is no fruit between its pads - the
     P107 aim class, which no closure law fixes.  P130 counts those too.
  Corrected (seated = `off <= 15 mm`; over = seated and `aper < R - 4 mm` or
  `F > 29.4 N`), the freeze-off cells read **clean 11/40, over 7/40, miss
  15/40, vblock 4/40, jam 1/40**.  The 7 over-closures are **tomato 2, peach 2,
  apple 3** - all flat fruit, all `aper / R` 0.818-0.887, all with the delivered
  force at the cap (4.5-4.9 N/pad) and none with the pad span below the command.
  **6 of the 7 placed.**  The over-closure is a force/geometry defect, not the
  dominant *failure*: the 15 misses are.
* **The drive is not the term.** The pads are position drives with a 4.9 N/pad
  cap; the measured span at the carry leg's end is at or above the command on
  every cell (`sep_end - aper` p10 **+0.0** on the freeze-off rows), and the
  over-closure rows' force is at the cap.  A position drive can be pushed back
  by the payload, not pulled through its target.  The **commanded target** is
  the term.

**Prediction this registration commits to**: the over-closure is the **law**,
specifically the two-jaw `deep` inherited by the radial hand; a hand-law load
target (`pad_axes`) removes the 7 over-closures and raises the clean enclosure;
the placed count does not move much (6/7 already placed) and the residual gap to
the shipped hand is the 15/40 aim misses (P107's blocker), not the closure law.

## 2. The build (default off; the shipped expression bit for bit)

`FRUIT_CAGE_APERTURE` = `shipped` (default) | `max_extent` | `pad_axes`:

* **`shipped`** - the P107 expression, `max over the hand x/y axes of
  axis_extent`, **bit for bit**; the dynamic close keeps its two-jaw `deep` and
  its 2.5 mm interference floor.  A selfcheck leg pins the unset path.
* **`max_extent`** - the mesh's largest axis.  **A screen, not a candidate**:
  it fixes the flat fruit (largest = width) and breaks the elongated upright
  fruit (largest = height, so the ring closes on air).
* **`pad_axes`** - the max over the ring's **own four pad axes** in the cage
  base frame (the P112 analogue: the law belongs to the hand, not to the TCP).
  On this line's upright fruit it is the horizontal width; on a tilted hand it
  reads the axes the pads actually close along.

For a radial hand with a variant armed, the close's load target `deep` becomes
the hand's stated extent at `FRUIT_GRIPPER_SQUEEZE` (0.98), and the two-jaw
2.5 mm interference floor is dropped (the ring's drive reaches its cap at
0.05 mm; the floor is 8.5 % of a 29 mm berry).  Everywhere else - unset, the
shipped hand, the cage3 law - the code is the shipped expression.

## 3. The cells

`FRUIT_BIARM=0`, the shipped supply, `ATTEMPTS=20`, the P108/P110 instrumentation
on both arms: `FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1`; every cell also `FRUIT_GRIPPER_KIND=cage4
FRUIT_DYNAMIC_CLOSE_FREEZE=0`.

| cell | seed | `FRUIT_CAGE_APERTURE` | role |
|---|---|---|---|
| `U5` | 5 | unset | the replay: must equal P130's `F5` on the `[fruit]` stream (minus `[cage]` rows) |
| `P5` | 5 | `pad_axes` | the candidate law |
| `P6` | 6 | `pad_axes` | the candidate law, second seed |
| `M5` | 5 | `max_extent` | the screen (predicted negative on pear/kiwi) |

The **same-seed freeze-off control** is P130's `F5`/`F6` (the tree's unset path is
proved byte-identical by `U5`).  P130's freeze-on `B_s5`/`B_s6` are context, not
the control.

## 4. Endpoints and the decision rule

1. **D1 (mechanism, primary)**: on `P5`/`P6`, the corrected over-closure count
   is **0** (the control is 7/40) and the `[cage]` row's measured `sep` is at
   the command (`|sep - aper| <= 1 mm` p50) - the law is the term.  A row with
   `sep < aper - 1 mm` would be a drive overshoot and would reject D1.
2. **D2 (enclosure)**: the corrected **clean enclosure** is at or above the
   control's **11/40**, and neither `miss` nor `jam` rises by more than one.
3. **D3 (placed)**: report only - a count is a branch (P130's own freeze-on
   pair reads 6/32; the off pair 19/40).  No count gate.
4. **D4 (`max_extent` screen)**: report the mechanism.  The prediction is that
   the 4 pear/kiwi attempts per cell lose contact; a `max_extent` that *beats*
   `pad_axes` would falsify the census's "the law must be the width" reading.
5. **D5 (no-harm)**: `scripts/accept.sh` with every knob unset is 8/10 +
   `fingerprint: matches` + its `[fruit]` stream **421/421 identical** to
   `logs/p127/accept_restored.log`; `scripts/selfcheck.sh` PASS; `106` OK;
   `107` PASS.  The cage refuses a `CoopSession` by construction, so the
   acceptance cannot reach the variant.

**Guards**: crush (`sep@loss - dia >= -15 mm`), landing (`on_belt` on every
payload-present release), descent budgets (not re-tuned - P93's ~2.5 % of legs
is a branch property), no new failure-reason key.

**Verdict rule**: if D1 and D2 pass, the phase publishes the law as the measured
fix (opt-in; `FRUIT_CAGE_APERTURE` stays default `shipped`, the owner decides
adoption).  If D1 fails (the drive), the phase publishes that and prices a
force-limited closure (stop the drive when the measured force reaches the cap)
as a named, unbuilt option.  Nothing in `configs/` moves either way.

## 5. Read rules carried in

* A count is a branch; the **clean enclosure** is the endpoint (P110's split,
  with the two metric corrections above stated in the PREREG, not after).
* The raw pad count is not the endpoint; jam / over / miss / clean are joined to
  the approach's `end=` and the close's `off`.
* The ring's battery is 18-25 % before P130 and 47.5 % with the freeze off, so
  the law's gain is read against the **same-seed freeze-off control** (`F5`,
  `F6`), never the old freeze-on records.

## 6. Pins (this tree, before the cells)

`tasks.py` `50fd799d` -> the phase's edit (the `deep` route + the probe fields);
`cage_hand.py` `42c4eb64` -> the phase's edit (`APERTURE_MODES`,
`aperture_mode`, the two law branches); `scene.py` `b3bf8067`;
`assets.py` `24d29679`; `fruits.py` `dcabe16b`; `rl_env.py` `3aed67b9`
(`TASKS_MD5` follows); refs `30fb99f8` / `30fb99f8` / `8952c320` untouched.
