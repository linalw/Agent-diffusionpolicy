# P103 pre-registration — the sim-only perfect-detector **re-grip**, scored on the survey's P2/P3

Pinned **before** any 20-attempt cell of this phase is read. Written after one
**6-attempt build smoke** (`logs/p103/smoke.log`, seed 6), which is a build
check and not a measurement: §0 records the two design facts it produced, and
**no count, rate or interval is taken from it**.

---

## 0. What the build smoke settled (recorded, not measured)

The smoke ran the treatment env on 6 attempts to prove the trigger fires and the
action runs. Two facts and one design change:

1. **The trigger fires on the right leg, at the right scale.** One leg tripped,
   `dc = 3.07 mm` at tick 59 of 159 with `seat_f = 2.85 N, seat_edge = +10.5 mm,
   seat_frac = 0.604` - P102's seat, on P102's channel. The same leg on the
   control record (`logs/p102/T6.log`, second left `grasp_lift`, 159/159) reads
   `clean_slip_max = 292.4 mm, force_min = 0.00 N`; with the re-grip it reads
   **31.9 mm / 2.27 N**. So the action acts on the class.
2. **A cooldown treadmills.** The first build fired at most once per 40 ticks.
   The payload walked 3.07 -> 30.41 mm **inside** that window (0.33 s at
   ~80 mm/s), so the second fire corrected 29.7 mm with the patch already
   `frac = 0.208, edge = -15.4 mm` off the pad. **The registered form therefore
   has no cooldown and no per-leg cap**: it re-seats on *every* tick the trigger
   holds, which is the shipped block's own temporal shape (`if slip_trigger <
   slip <= slip_react_max:` re-fires every tick - `logs/264` reads 128 events).
   This is safe because the re-seat's target is **absolute** (`fruit - rot @
   slip_ref`), so a repeat cannot accumulate into a growing endpoint shift.
3. Consequence for the harness: `recoveries` counts re-seat **ticks**, so a
   re-seated leg is exempt from the motion checker's cone gate by its own rule
   (`scripts/105_motion_regression.py:402`: `recoveries > 0` = a rescued leg).
   The carry cones are therefore **reported, not gated**, on the treatment arm;
   the descent budgets - which is what the gate protects - are unaffected.

## 1. The question

`docs/PLATFORM_SURVEY.md` §5.1's stage (i) ends on P2/P3, and P102 measured the
**signal** but not the **reaction** (§6: "registered, not built"). This phase
spends the window: **does catching the loaded slide at 2.12 mm convert `cnp`?**

The cell is the survey's own **sim-only perfect detector**: the trigger is the
sim's `clean_slip`-class patch statistic, not a soft-pad image. It measures the
**reaction's** upper bound. Whether a real pad images a 2 mm centroid shift is
the survey's T2 bench and is **not** what this phase answers.

## 2. The trigger (frozen)

Per guarded tick, on a carry leg of a **two-line session**:

| term | value | source |
| --- | --- | --- |
| `dc` | the patch centroid's displacement since the leg's **first** tick, `hypot(du, dv)` in the pad's face frame | P102's `[tactile]` row prints the same number (`tactile_patch_state`) |
| **seat** | `max(f0, f1) > 1.0 N` **and** `edge > -TACTILE_PAD_HALF_LONG` | P102's `census.py:analyse` - a loaded pinch *and* the patch on the pad, so the empty-hand `never_held` class cannot trip it |
| threshold | **`FRUIT_SLIP_REGRIP = 2.12 mm`** = 5 % of the pad's half-length (42.451 mm) | P102 §3: the lead is insensitive to the threshold, so the 5 % value is taken rather than tuned |
| ceiling | only while the leg's own `clean_slip <= FRUIT_SLIP_REACT_MAX` (60 mm) | the shipped abort ceiling - past it the tree deliberately stops reacting |
| rate | **every tick** the trigger holds | §0.2 |

## 3. The action (frozen)

**The tree's own slip re-seat, and no new control law.** `_carry_leg` already
carries one behind `FRUIT_SLIP_RECOVERY` (the `slip_enabled` block): it computes
`target = fruit - rot @ slip_ref` - the pad centre that restores the **leg-start**
relation - applies `correction = target - pads` in one go, re-bases the leg's
remaining command list onto it (`commands[i+1:] = reseated + (positions[i+1:] -
positions[i]) * direction`), and re-engages the force servo. That block is gated
`not hand_is_jaw` because it was written for the kinematic pad hand; on the
OpenArm hand the pads *are* the robot's fingers, so the relation is restored by
re-basing the arm's own command list - which is exactly what the block does.

`FRUIT_SLIP_REGRIP` therefore reaches **that block** from the patch channel
instead of from the 25 mm `FRUIT_SLIP_TRIGGER`. Nothing else changes: no gap
change beyond the shipped `FRUIT_SLIP_SQUEEZE_STEP` (0), no new IK step, no new
profile.

**Cost, stated as a prediction before the run**: the re-seat moves the command,
not the clock, so the **added cycle time is 0 ticks**; what it can cost is a
**branch change** (the presentation re-times the next attempt, as every
intervention on this cell does) and an endpoint shift bounded by the slide.
P102 §6 priced a 1.24 s re-grip at 2.6 % of an attempt; this action is cheaper
and the registered P3 bar is unchanged.

## 4. Scope

**Two-line session only** (`Task.two_line_enabled()`, the P87/P88/P89/P91
pattern), resolved once per attempt. `FRUIT_SLIP_REGRIP` unset or `0` is the
shipped path **bit for bit**; `0 < mm < 1` raises at construction (P102's held
legs read `dc_max` median 0.02 mm / p90 0.10 mm over 60 legs, so a
sub-millimetre threshold is a trigger on the seat's own noise).

The single arm, the shared-station pipeline, the direct/policy handover and the
hybrid canary have no session here and resolve to off, so their records stand.

## 5. The cells

`ATTEMPTS=20`, the shipped two-line scenario, `FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1` on **every** cell, and **both** `FRUIT_CARRY_DIAG=1`
(the class ledger's `clean_slip`/`force_min`) **and** `FRUIT_PLACE_TRACE=1`
(the landing guard's `on_belt`) on **every** cell - so the two arms differ by the
knob alone (P83's G2 shape: the instrumentation must be in both arms before an
A/B is admissible). Both are proven inert on this line (`logs/p86/RESULTS.md`
§C5/C6: `[carry]` 710/710 and 708/708; the place trace 865/865 with its rows
dropped).

| cell | seed | env |
| --- | --- | --- |
| `C5` / `C6` / `C101` / `C202` | 5 / 6 / 101 / 202 | `FRUIT_CARRY_DIAG=1` |
| `T5` / `T6` / `T101` / `T202` | 5 / 6 / 101 / 202 | `+ FRUIT_SLIP_REGRIP=2.12` |

Interleaved by seed, alternating C->T / T->C (P77's convention).
**Four seeds, two of them fresh** - P93's rule: P92's two-seed band gain did not
survive fresh seeds, and a 20-attempt count is a branch draw, so two seeds cannot
separate a lever from a draw.

**Which records are admissible on this tree.** `logs/p102/{C5,C6}.log` are the
current tree's cells (`tasks.py b257687d`, this phase's base) with the identical
env, so they are the **same-batch-equivalent** controls for seeds 5/6 and are
re-checked against the fresh `C5`/`C6` by a line-identity replay. `logs/p94/*` is
pre-P99/P100 instrumentation and `logs/p91/C5.log` is **not admissible** (it
predates P94's `_gripper_offset` guard - P102 §1 measured the divergence at its
own guarded row). The cells run here are the record regardless; the replay is the
proof that the archived pair *would* have been valid.

## 6. Endpoints

**Primary - the conversions (branch-free, per leg).** Every `[regrip]` row is a
leg; the leg's attempt is its side's k-th `[run]` row (P102's join, exact on this
cell). Reported:

* the **trigger ledger**: side, leg, first-fire tick / leg ticks, `dc`, `slip`,
  `seat_f`, `seat_edge`, `seat_frac`, fire count, first correction;
* of the tripping legs, how many led to a **placed** attempt;
* the **false-positive ledger**: legs whose patch moved `>= 2.12 mm` that
  **still placed** in the control (P102: 2 of 60 held legs), and whether their
  attempt placed in the treatment too.

**P2 - the survey's clause (`docs/PLATFORM_SURVEY.md` §5.1).**

* **P2a** (the survey's literal form, seeds 5+6, 40 attempts): `cnp` **6 -> <= 4**
  and placed **29 -> >= 32** of 40 (+8 points).
* **P2b** (pooled, 4 seeds, 80 attempts): `cnp` falls **>= 30 %** **and** placed
  rises **>= 8 points**, with the per-seed direction reported (a pooled gain that
  is one seed's branch is a fail).

**P3 - the price.** The inter-placement interval, pooled **and** per arm,
`<= +5 %` on the mean; plus both denominators (placement window and batch span)
and the wall (`placed/min wall`, from the per-line stamps - never inferred).

**Class ledger and the closed-class guard.** `cnp` / `never-grasped` /
`grasped-not-placed` / `did not land` / `force_min == 0` legs, per seed and
pooled. The `force_min == 0` count is the loaded-slide guard: a re-grip that
merely relabels the class must not raise it.

## 7. Guards (all reported; none is a rate)

| guard | clause |
| --- | --- |
| **G1 off-path inertness** | `FRUIT_SLIP_REGRIP` unset: `scripts/accept.sh` reads **7/10, `fingerprint: matches`, `190: PASS`**, and its `[fruit]` stream is **byte-identical** to the pre-phase record (`logs/p98/accept_revert.log`) |
| **G2 arm instrumentation** | `C5`/`C6` (this batch, `FRUIT_CARRY_DIAG=1`, no knob) replay `logs/p102/{C5,C6}.log` **line for line** on the `[fruit]` stream - so the A/B is the action alone |
| **G3 landing** | every payload-present release (`release_bottom >= 0`) reads `on_belt=True`; the `-184 mm` rows are the upstream-lost class, reported separately |
| **G4 descent budgets** | `scripts/190_twoline_gate.sh` on each treatment cell: **budgets only** (`105 --min-success-rate 0.0`), because a re-seat moves the fingerprint by construction. Any over-budget leg is named with its seed, arm and ratio |
| **G5 no new failure reason** | the reason keys of the treatment's failures are a subset of the control's (after the shipped notes), per seed |
| **G6 accounting** | 20 attempts per cell; no lost slot; `NO-GRASP`/`cnp`/placed sum to the attempt count |

## 8. The decision rule (stated before any run)

* **P2 AND P3 pass** -> the **sim upper bound is positive**: report the
  conversion count, the P2 movement and the interval cost, and leave the knob
  **opt-in** (`FRUIT_SLIP_REGRIP` unset everywhere). The adoption question then
  becomes the **sensor**: the cell only says a perfect detector converts, so the
  owner's decision is whether to buy one (GelSight Mini / 9DTact) and run the
  survey's T2 bench. **Nothing ships by default either way.**
* **P2 fails** -> **null, and stage (i) closes as "detected but not
  convertible"**. P102's mechanism stands (the lead is real, 21-113 ticks); what
  dies is the premise that catching the slide at 2 mm buys the placement. The
  report says so plainly, and the named residual is the class P42/P75/P76 closed
  (the pry/pry-escape is a pad-face-geometry object, not a control one).
* **P2 passes, P3 fails** -> the lever converts but does not pay; report both and
  do not ship.
* **A pooled pass that is one seed's branch** -> fail (P2b's per-seed clause).

No clause here may be re-read after the runs. A clause that turns out to be
non-evaluable (P100's and P102's precedent) is **recorded, not re-read**.
