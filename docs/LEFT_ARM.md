# The left arm's deficit: the mechanism, the eliminations, and what is left

One page. It condenses P60-P68 (`logs/p6*/`, AGENTS §2's paragraphs) into the
chain, the closed classes, and the two registered paths. Every number traces to a
log in `logs/`.

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

## The cost: the two closed classes meet

The low lift **spends the rail margin**: the place transit then crosses the output
rail at **+5 mm** against the project's **+33 mm** floor (shipped +30/+29; no
contact, 0/16 legs negative). And the crossing is **1:1 with the transfer height**
but only **0.175:1** with the lift, so the rung ladder cannot buy it back.

The re-shape (a vertical climb of 0.18 m at the place leg's start) **clears the
crossing** (+33..+54, 6/9 held legs >= floor) **but the hand cannot carry it**:
**8/16 climbed legs lose the payload** (`clean_slip` 0.92-1.00 m, onset at the climb's
exit) - `logs/p42/SIM_LIMIT.md`'s loaded slide - and the record's wrist hold makes it
**worse** (**16/16**, because the hold is a full 6-DoF pin that spends the per-tick
step budget the position command needs; the right achieves it to 0.8 deg, the left
cannot).

| form | carry class | rail crossing | left placed |
|---|---|---|---|
| shipped 0.36 | 25 deg | +30/+29 | **0/25** |
| low lift 0.20 | **0.7 deg** | **+5** (floor +33) | **14/25** |
| low lift + climb | 1.1 deg | **+33..+54** | **8/16 held** |
| + the wrist hold | 1.1 deg | - | **0/16** |

## What is NOT the answer

- **Not the policy**: the loss is in the primitive's grip (the loaded slide), and
  three recollections read no-gain.
- **Not a training run, a new checkpoint, or an architecture change.**
- **Not more supply**: the supply is solved (0/42 starved rounds).
- **Not a knob**: every parameter-level candidate measured is closed (the pose
  family, the seat, the force family, the pre-compensation, `max_step`, the joint
  clip, the pads' line, the direct carried-class lever - which converts the
  **right**, 28 -> 5 cnp, and not the left, 20 -> 22, p = 1.0).

## The two registered paths (P69)

1. **A new pad asset** (`logs/p69/A_PREREG.md`): P30-C's **24-45 mm** shorter tip,
   the one `SIM_LIMIT.md` sanction that needs no scenario change. The **free static
   read** comes first (the authored collider prims, the `S - F1 = 4*cos(theta)`
   identity, the distal plane), then a geometry probe; the cost is **both motion
   references + the acceptance** (the collider is authored in `scene.py`).
2. **A workstation/transfer change** (`logs/p69/B_PREREG.md`): the rail-crossing
   options ranked by gain per cost (a lower outer rail, a shorter transit, a raised
   transfer), each with its reference/acceptance/store consequences.

**Nothing is adopted.** The shipped defaults are unchanged: the lift at
`belt_top + 0.36`, no climb, no wrist hold, `configs/*` untouched, both motion
references as recorded. The levers above are **opt-in and default off**.
