# The left arm's deficit: the mechanism, the eliminations, and what is left

One page. It condenses P60-P74 (`logs/p6*/`, `logs/p7*/`, AGENTS §2's paragraphs)
into the chain, the closed classes, the shipped package, and what is left. Every
number traces to a log in `logs/`.

**Status (P71, 2026-10-31): the fix ships.** The direct presentation's lift is
`belt_top + 0.20` by default and the output belts carry no side rails, so the
left's carry rotation is 0.7 deg and its placed count reads **10/17** (N = 3,
`logs/p71/RESULTS.md` §3) against **4/20** for the pre-P71 package measured in the
same batch. The sections below are the chain that got there; §"The cost" says how
the rail gate was resolved.

**Status (P90, 2026-11-01): the workstation path is measured and closed.** The
output **place station** has **no top-down configuration** - 0 of 588 static IK cells
over +-0.15 m at the place height and the transfer, both arms, in three attitude
modes - and the **best solved attitude anywhere in that envelope is 77.75 deg, at the
shipped station itself**, so the station is not improvable by moving it
(`logs/p90/MAP.md`). The cliff is one 10 mm step at `|y| = 0.51`, even the arm's own
calibrated attitude has no margin there (best +0.037 rad), and the only sub-40 deg cell
the whole phase can produce (28 deg, left only, `|y| = 0.35`) is 75 mm inboard of the
slab, i.e. a release into the void. So §"What is NOT the answer" and the two registered
paths below are the **whole** list.

**Status (P79, 2026-10-31): the force lane is measured out; the residue is a
geometry limit.** The pry is real (P75: the pads are driven to their 98.1 mm stop
in 9 ticks while the command closes), force deletes its **radial** half and never
its **axial** half (P76-P78), and no scoped force reproduces the global count
(P78/P79: 0.688 and 0.529 against controls at 0.524-0.556, while the global 0.85
is one draw). §"The force lane" has the thresholds and the decomposition.

**Status (P74, 2026-10-31): what is left on the left is one closed class.** The
place leg - where the remaining left losses are - has now had its three candidate
mechanisms measured out (**the transfer's height**, **the rotation**, **the
profile's speed / dwell**: §"The place leg"), and the escape is the same
single-sided loaded slide as the carried class. So the left's deficit is no
longer an open question: it is `logs/p42/SIM_LIMIT.md`'s class, and only its two
sanctions (**a new pad asset** at a magnitude the current authorization does not
cover, a **real-jaw clamp-force anchor**) or a **workstation move** can touch it.
Everything the record calls a lever has been measured and is closed.

## The question

Under the shipped direct profile the post-profile number is **26/45 = 57.8 %**
(P59), split **right 24/25 (96 %)** / **left 2/20 (10 %)**. The supply is not the
binding term by then (0/42 starved rounds, `window >= 1` 45/45). What is the left's
**47x** deficit, and can it be fixed?

## The chain (each link measured)

1. **The payload leaves along the finger axis** (P61): the leg-frame mean slip unit
   vector is `(-0.351, +0.240, +0.905)` - **25.2 deg from the tool axis**, 48.9 deg
   from the belt. The instrument (`slip_xyz`, default off) holds
   `|slip_xyz| == clean_slip_max` on 88/88 rows to 0.072 mm.
2. **It happens during a ~25 deg attitude rotation** (P63): `hold_drift` reads
   **23.8-25.7 deg** on the control's lifts, and the **azimuth is the belt axis on
   the left** (3/3 legs downstream, 77 % of the tilt on the belt axis) while the
   right's lands across it (0/6). The magnitude is **arm-common** - the right places
   29/30 at 25.8 deg - so only the azimuth is left-specific.
3. **The rotation is not a controller defect** (P62, P64, P65): the yaw family is
   **IK-infeasible** (0/3 at +31 deg, pads 3 mm from the belt; +62 deg drives them
   14 mm into it); the commanded attitude is **already the top-down one**; the
   pre-compensated command is **inadmissible** (0/3, 42.6-72.9 mm residual, joints
   at zero margin, a 28.9 mm pad-height twist); `max_step` never binds (6 % of its
   cap); the joint clip is a **standing condition** (0.000 rad on 86/86 legs, both
   arms) and the drift **precedes** the margin's minimum by 41 ticks.
4. **It is the lift's height** (P66): a 150-cell station sweep finds **no point in
   the delivered band where the top-down attitude holds** (0/75 of its own cells
   pass the 0.05 rad margin clause), and at the **lift's end height** it is
   **statically unsolvable** (qerr 24.3-60.0 deg, margin 0.000) **with no payload,
   no controller and no transient**. The live 24.6 deg **is** the static number.
5. **So the lever works**: lowering the lift's end 0.36 -> 0.24/0.20 moves
   `drift_end` **25.1 -> 3.4 -> 0.7 deg** and the left **0/25 -> 12/30 -> 14/25**
   (N=5, interleaved, **5/5 runs**; Fisher ~2e-4), with a flat cycle (sim 15.0 ->
   14.7 s/pick).
6. **What is left is the place leg, not the carry** (P73/P74, §"The place leg"): the
   shipped package's remaining left losses are held through the transit and lost
   **on the way to the release**, and the three candidates for that leg - the
   transfer's **height**, the **rotation**, the profile's **speed / dwell** - are
   each measured out. The escape is the same single-sided loaded slide.

## The cost: the two closed classes meet - and how P71 resolved it

The low lift **spends the rail margin**: the place transit crosses the output rail
at **+5 mm** against the project's **+33 mm** floor (shipped +30/+29; no contact,
0/16 legs negative). And the crossing is **1:1 with the transfer height** but only
**0.175:1** with the lift, so the rung ladder cannot buy it back.

**P71 shipped the lever that does: the rail is gone** (`FRUIT_OUTPUT_RAILS` now
defaults to `none`), so the surface the payload crosses is the slab's inboard top
edge instead of a 35 mm fence. Measured on the direct line with both flips in
effect (N = 3 x 15, `logs/p71/RESULTS.md`): the left's held place legs pass
**+14..+50 mm above the belt top** (median +35, 8/10 at or above the +33
convention, `clr_win` +10..+45) with **no contact signature** (`|a|max`
0.31-8.69 m/s² against G0's 14.9-32.7 contact population) and the payload is
35 mm **below** where the rail top used to be - which is why P66's
`+33 at the rail` gate read `+5` and would read `+5` for ever: a lower lift
cannot raise a payload over a fence, it can only be given a crossing that is not
fenced. `docs`-level consequence: the low lift is now the **direct
presentation's default** (`belt_top + 0.20`), and the crossing is a *margin*
report rather than a rail gate.

The re-shape (a vertical climb of 0.18 m at the place leg's start) **clears the
crossing** (+33..+54, 6/9 held legs >= floor) **but the hand cannot carry it**:
**8/16 climbed legs lose the payload** (`clean_slip` 0.92-1.00 m, onset at the climb's
exit) - `logs/p42/SIM_LIMIT.md`'s loaded slide - and the record's wrist hold makes it
**worse** (**16/16**, because the hold is a full 6-DoF pin that spends the per-tick
step budget the position command needs; the right achieves it to 0.8 deg, the left
cannot). That is why the climb is not the shipping path.

| form | carry class | rail crossing | left placed |
|---|---|---|---|
| shipped 0.36 + rails | 25 deg | +30/+29 | **0/25** |
| low lift 0.20 + rails | **0.7 deg** | **+5** (floor +33) | **14/25** |
| low lift + climb | 1.1 deg | **+33..+54** | **8/16 held** |
| + the wrist hold | 1.1 deg | - | **0/16** |
| **P71 shipped: low lift 0.20, no rails** | **0.7 deg** | **+14..+50 vs the belt top** (0/10 vs the rail top, which no longer exists) | **10/17** (N = 3, `logs/p71`) |

## The place leg (P73/P74): three more mechanisms measured out

With the carry fixed, the left's remaining losses are **place-leg loaded slides**
(`logs/p71/RESULTS.md`: 6 of 7 at `loss_row` 103-150, i.e. held through the
transit and lost on the way to the release). Three mechanisms were registered and
measured, and all three are out:

| candidate | how it was measured | result |
| --- | --- | --- |
| **the transfer's height** sets the required wrist rotation (`FRUIT_OPENARM_TRANSFER_LIFT` 0.08/0.14/0.20) | P73, 3 arms, seed 77 | the rotation moves **the wrong way** (**78.7 -> 93.8 -> 105.2 deg**) and the class is **flat (1 / 1 / 1)**: falsifier fires |
| **the rotation** drags the payload | the new `t45`/`tilt_rate` schedule (P73) | **all 8 losses start before the leg's 45 deg crossing**, at a tilt below 45 deg, while the 90-105 deg sweep happens at **73-79 % of the leg** - after the failure; and the **right reaches 107.3 deg and slips 0.0-0.1 mm on 10/10** legs |
| **the dwell** in a top-down pinch (the "creep" reading of P73's slow arm) | P74, 2 arms x **3 seeds**, `FRUIT_SPEED_PLACE` 0.352 -> 0.52 | the escape rate is **50 / 42 / 50 %** across a **2.6x** range of leg ticks (680/405/262): **flat** (p = 0.733), so the creep reading is withdrawn |

**Two instrument lessons came out of it, and they bind the next reader.**

1. **A leg-end sample cannot see this class.** The `[attitude] tilt` at the leg's
   end reads 80.8-94.6 deg on **both** the lost and the placed legs of the shipped
   corpus; a screen using it alone would have reported "the height does not move
   the rotation" and been wrong. The schedule (`tilt0/tilt_end/tilt_max/t45/t75/
   tilt_rate`, `[carry]` under `FRUIT_CARRY_DIAG`) is what makes it readable.
2. **`clean_slip_max > 800 mm` is not speed-invariant.** The reported walk after
   an escape is `rate x (ticks - loss_row)`; a faster place raises the rate
   **3.2 -> 4.0 mm/tick** and cuts the remaining leg **38 %**, so escapes migrate
   under the 800 mm line without the escape rate moving (S drew four near-misses
   at 659.6-799.1 mm). **Quote the escape count (`> 100 mm`) for any speed
   change**; the 800 mm threshold stays usable for height / rotation / retiming,
   where the remaining leg is constant (that is why P71's `15 -> 7` stands).
3. **A 15-pick single seed is not a direction on this class.** P74's seed 77 read
   `2/4 -> 1/6` in the predicted direction and would have published a 15-point
   win; seeds 101 (`4/7 -> 4/5`) and 202 (`2/8 -> 2/3`) reverse it. **>= 3 seeds.**

**What that leaves on the place leg:** the escape's signature is
speed-invariant and is the **same single-sided loaded slide** as the carried
class (`force@onset` at the pinch's own ~10 N, then `fmin 0.00`, jaws ending at
**17-54 mm**, never the 98 mm open stop, `contacts@onset` 1 on most) - i.e. the
payload walks out along the finger axis while the pads hold. So the levers that
can still touch it are exactly `logs/p42/SIM_LIMIT.md`'s two sanctions (**a new
pad asset**, **a real-jaw clamp-force anchor**) or **a workstation move that
shortens the lateral transit at top-down** - pose, rotation and clock are spent.

## The force lane (P75-P79): what the pads actually do, and why force is not the answer

P75's per-tick trace settled the mechanism at one tick: the payload's hand-frame
displacement is **0.0 mm for 110 ticks**, the force then collapses in **two**
(5.03 -> 4.11 -> 0.00 N), the measured `sep` **starts rising on the same tick**,
and within **9 ticks** the pads sit at their **98.1 mm mechanical stop** while the
commanded gap is **closing** (68.7 -> 66.7 mm). So the class is a **wedge/pry**,
not a slide at constant `sep` (that reading of the P41 census - "the pads hold and
the payload slides" - is not this interface), and it is not a command transient
(0 of 26 traced legs show a `|dv_cmd| >= 0.10 m/s` step; a held leg carries the
same `tcp_err` ramp and holds).

The force ladder then separates three thresholds that the record had conflated
(P76, six cells, 26-55 left legs each):

| question | answer |
| --- | --- |
| when do the pads stop being **pried to their travel stop**? | **> 30 N**; gone at **45 N** (0/26 legs past 95 mm) |
| when does the **payload** stop being pried out? | **> 45 N**; gone at **60 N** (0/26 pried, 0/26 escaped, the pear at 75.2 mm and 0.0 mm slip) |
| when is the **smallest fruit crushed**? | **not at 60 N** on this interface (the 3.6 cm berry reads `sep@loss - dia` **+0.5 mm** under a 60.16 N pinch and places) - P41's "60 N crushes a strawberry" is a **seating** event (the close landed 24.7 mm inside the fruit), not a force threshold |

**Then the count did not survive replication, and that is the lane's real result.**
P77's **global** 60 N read left placed **11/21 -> 17/20** (Fisher p = 0.043) - but
P78 and P79 scoped the same write to the two carry classes with **zero blast
radius** (the scripted acceptance stays **346/346 byte-identical** with
`fingerprint: matches`, the two-line passes `190`, no reference moves) and read
**0.688** (`place-left`) and **0.529** (`grasp-left`) against controls that agree
at **0.524 / 0.556 / 0.550**. Neither half reproduces the global arm, the dose is
not monotone (30 N reads 0.706/0.800 against 60 N's 0.688/0.529), and the one
class the global cap touched that no `_carry` token can reach is **the close**
(where its `never-held` 3 -> 0 must have happened) - so the honest reading is
that **the global 0.85 is one draw of a branch**, not a force effect.

**What force does do, mechanically, is delete the radial pry and leave the axial
walk.** At 10 N, 5 of 7 escapes leave with the pads **13.5-39.9 mm** past the
fruit's width; at 60 N, **2 of 3** leave at **+3.4 / +7.9 mm** - the pads
essentially closed, the payload walking out along the **tool axis** (P61's
measured direction, 25.2 deg off the axis). So the class **decomposes**: the
radial half is force-limited, the axial half is a **geometry** limit - there is no
distal lip to block the walk. That is `logs/p42/SIM_LIMIT.md`'s new-pad-asset
sanction, now with a **specific target** (block the axial exit, not lengthen the
plate: P30-C's 24-45 mm shortening was measured closed because it was aimed at the
wrong dimension).

**And the honesty item that governs any force adoption:** 60 N per joint is
**jaw-feasible** (commercial parallel jaws cover 20-235 N) but it **would bruise a
3.6 cm berry**, and **this simulator has no bruise model, no damage model and no
flesh-compliance model**. A clean read at 60 N is a statement about **geometry and
retention**, never about fruit quality - which is the other reason the geometry
lane is the physical one.

## The left hand as an *obstacle* (P95/P96/P97)

One row belongs to the left that is not about its own grasp: the left hand **strikes
the other lane's fruit**. The two-line's pre-pose is the calibrated grasp
configuration, so the left hand dives to a pad plane **29 mm below a fruit's top**
at its own station on every attempt - and a **right**-arm fruit must cross that
station (`left y=+0.000` upstream of `right y=-0.100` on a `-y` belt). P95 caught
the witness (the left jaw span knocked 98.0 -> 59.8 mm and springing back, 2 mm
from the fruit's surface, `21.6 rad/s` of spin) and P96 built the clearance pose:
`FRUIT_BIARM_PREPOSE_CLEAR=1` solves **both** stations' pre-poses at
`belt_top + 0.165` with the arm's own measured attitude, which lifts the shipped
pose's **pad point from 46 mm below the tallest fruit's top to 20 mm above it**,
takes the contact census **1/40 -> 0/40**, and costs no time (`prepose` 0.71 s
unchanged, `hover` **0.78 -> 0.61 s**). **P97 (2026-11-02) ships it as the
two-line session's default** - the owner's decision is the **invariant**, not the
count: P96's two-seed count is the draw **29/40 -> 27/40** (seed 5 -5, seed 6
+3, per arm -1/-1) and is **not claimed**. `FRUIT_BIARM_PREPOSE_CLEAR=0` restores
the pre-P96 path bit for bit, and the shipped acceptance's own `=0` A/B
reproduces the pre-P97 record (8/10 + `fingerprint: matches 30fb99f8`, 419/419
physics lines identical to `logs/p94/accept_final.log`), so **every two-line
rate, interval, acceptance and store recorded before P97 is a
pre-clearance-pre-pose number**. What it changes for *this page* is that the
left's station pose is now a **measured, parameterised object**
(`_prepare_two_line_stations` solves it, the log names its jaw height/tilt/margin,
the shard manifest carries `prepose_clear`), rather than a calibrated constant
with no clearance story - and the shipped default's own census reads **0
contacts** (`logs/p97/RESULTS.md`).

## What is NOT the answer

- **Not the policy**: the loss is in the primitive's grip (the loaded slide), and
  three recollections read no-gain.
- **Not a training run, a new checkpoint, or an architecture change.**
- **Not more supply**: the supply is solved (0/42 starved rounds).
- **Not a knob**: every parameter-level candidate measured is closed (the pose
  family, the seat, the force family, the pre-compensation, `max_step`, the joint
  clip, the pads' line, the direct carried-class lever - which converts the
  **right**, 28 -> 5 cnp, and not the left, 20 -> 22, p = 1.0 - and, since P73/P74,
  the place **transfer's height**, the place-leg **rotation**, and the place
  **profile's speed / dwell** as well; see the place-leg section above).
- **Not a carry-command artefact** (P94): the one place where the carry commanded
  the arm from a number that was not a tool offset - `_gripper_offset` applied
  unguarded in `_carry`'s assisted branch - is now **bounded**
  (`FRUIT_CARRY_OFFSET_MAX`, 0.20 m). It was real and it destroyed one leg per
  ~40 attempts (a **1313 mm** reading -> a 419 N / 1.545 m/s flight, P93; a
  **350 mm** one -> `|v|max 1.108` on the arm, P94), but **removing it converts
  nothing**: the two guarded legs stay `never_held` / `cnp`, no seed loses a
  placement, and three of four seeds replay their records line for line. Read it
  as *state integrity*, never as a grip lever (`logs/p94/RESULTS.md`).


## The two registered paths (P69)

1. **A new pad asset - MEASURED CLOSED at the authorized magnitude**
   (`logs/p69/A_PREREG.md`). The free static read is exact (the plate's long
   dimension 84.902 -> 80.902/60.902/49.902/39.902 mm at 0/-4/-24/-35/-45 mm; the
   distal plane rises by `|delta|*cos(theta)`; the proximal plane does not move; the
   identity holds to 9.7e-7 mm), and it **kills the magnitude by contact geometry**:
   at the shipped aim (jaw standoff 0.070 m) the plate's lower edge would sit
   **+13.5/+24.5/+34.5 mm above the fruit's equator**, so the pads close **without
   touching any of the 8 pool classes** (closest approach +2.6 mm; +0.3 mm even
   under D2a's -8 mm seat). The **admissible band is +3.5 .. -7.9 mm** (patch intact)
   / **-13.1 mm** (any contact), and the probe confirms it on the same peach:
   control `grasped, lift +0.289 m, force 10.00 N`; at -24 mm `grasped=false, lift
   +0.000, force_min 0.00 N`. What the cut would buy: descent **+24/+35/+45 mm of
   tip-belt clearance - unconsumed** (the tip already clears by 3.5-24.5 mm; the
   descent's residual is a **jaw-plane** 8.1-10.3 mm, and the probe reads
   `end=8.1 mm` in both arms), carry **+21.8/+31.8/+40.9 mm** (= the lip lost, 1:1),
   **rail crossing +0.0 mm**. So the lane is registrable only in a band **1.8-10.8x
   smaller** than authorized, where every move is **4.1-10.9 %** (patch intact) / **6.0-16.0 %** (any contact) of the phenomenon: the
   reopen conditions are a **real-jaw clamp-force anchor**, the class-indicated
   **+3.5 mm extension** (owner-gated, predicted null: 1.3-3.4 % of the 104-276 mm
   walk), or a genuinely new pad design.
2. **A workstation/transfer change** (`logs/p69/B_PREREG.md`): the rail-crossing
   options ranked by gain per cost (a lower outer rail, a shorter transit, a raised
   transfer), each with its reference/acceptance/store consequences. **P71 shipped
   the rail removal** (the strongest of this family at 1:1) and re-recorded both
   motion references. **P90 then closed the station-layout half**: the output place
   station has no top-down configuration in +-0.15 m (0 of 588 cells), the shipped
   point is the best the envelope offers (77.75 deg is the best *solved* tilt), and
   the cost columns came back cheap because there is nothing to buy
   (`logs/p90/MAP.md`, `logs/p90/COST.md`).

**What is shipped today (P71).** The lift is `belt_top + 0.20` for the **direct**
presentation (`FRUIT_LIFT_DZ=+0.08` restores 0.36), the output belts carry **no
side rails** (`FRUIT_OUTPUT_RAILS=both` restores), no climb, no wrist hold, and
both motion references are the P71 re-records (`8952c320` / `eb697f23`,
`logs/p71/RESULTS.md` §5). The climb, the wrist hold, the pre-compensation, the
seat and the pad families remain **opt-in and default off** (measured negative).

**The crossing, as it now reads (P72).** The `clr`/`clr_win` fields sampled the
**removed rail's face**; the P72 `clr_edge`/`clr_edge_min` sample the **slab's own
inboard edge** (0.425 m), which is the only surface left. On the shipped package
the held place legs read **min +26 mm, median +77.5, max +109, `<= 0` on 0/10**,
with every `|a|max` **<= 4.49** against G0's measured contact population of
**14.9-32.7 m/s²**. The new-frame floor is therefore **`clr_edge > 0`** and it is a
**bracket, not a calibrated floor**: no dose ladder can close it, because the
transfer follows the belt 1:1 while the lift end is anchored to the main belt
(`d clr/d lift = d clr/d belt = 0.175`), and the +33 mm convention was calibrated
against a raised rail top that no longer exists.

**The hybrid canary (the interface of record) after the rail flip: 8/10 PASS**
(`logs/p72/RESULTS.md`), two `fruit did not follow the gripper` grip losses, no
reason outside the recorded baseline, both upstream of the output line - so the
rail removal is not implicated. One smoke, and 8/10 is the **top** of the
interface's recorded 5-8/10 spread: a sample, not a rate.
