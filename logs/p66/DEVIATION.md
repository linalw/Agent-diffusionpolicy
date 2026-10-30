# P66 phase 3 — DEVIATIONS (written **before** any phase-3 run, 2026-10-30 12:05)

Oracle gate 2 (`CONFIRM-FIRST`) dispositions the three registered clauses that the
phase-2 ladder's own numbers moved. Nothing here changes a measurement: every
number below is re-read from `logs/p66/p2/` (the phase-2 cell,
`logs/p66/P2_RESULTS.md`'s tables), and the two dispositions that concern a
falsifier are recorded so that phase 3 cannot be read as if the ladder had passed
them untouched.

The phase-2 cell of record: 3 seeds (77/101/202) x 15 picks, interleaved
`C1 -> L1 -> L2 -> C2`, `FRUIT_LIFT_DZ` = unset / `0.00` / `-0.08` (lift end
`belt_top + 0.36 / 0.28 / 0.20`).

---

## D1 — **F1 fired on its letter** (a favourable miss; recorded, no re-run)

`PREREG_P2.md` §Falsifiers **F1**: *"`drift_end` misses the predicted band -> the
dose-response is wrong; stop the ladder."* The prediction was
`24.6 / 8 ± 3 / 3 ± 2 deg` for `0.36 / 0.28 / 0.20`.

| arm | lift end | `drift_end` median [range] | predicted | verdict |
|---|---|---|---|---|
| C1 | 0.36 | 23.8 [21.5-28.0] | 24.6 ± 3 | inside (0.8) |
| L1 | 0.28 | 9.7 [7.0-14.0] | 8 ± 3 | inside (1.7) |
| **L2** | **0.20** | **0.7 [0.6-6.0]** | 3 ± 2 | **outside (2.3)** |
| C2 | 0.36 | 25.7 [20.8-28.3] | 24.6 ± 3 | inside (1.1) |

**Disposition: fired on the letter, and the miss is favourable.** The prediction
scaled the static reachability curve linearly in height; the live response is
**steeper at the bottom**. The phase-1 sweep's own cells are the evidence: the
static achieved tilt is `0.79 deg at z = 0.09`, `6-10 deg at 0.25`,
`26-42 deg at 0.36` (`logs/p66/STATION_SWEEP.md`), i.e. the curve is convex, so a
linear interpolation to `z = 0.20` over-predicts. The measured `0.7 deg` is the
static curve's **bottom** value (0.79 at 0.09), two-and-a-half degrees *better*
than the interpolation. **Monotonicity and ordering held** (23.8 -> 9.7 -> 0.7 ->
25.7 across the four arms, and each arm's ladder position is the order the
prediction named), which is what F1 exists to protect: a *wrong direction* or a
non-monotone dose would have invalidated the ladder. **No re-run, no re-band** —
the phase-2 numbers stand as measured, and the band is quoted with the miss
attached wherever it is used.

## D2 — **F4 fired falsely**: the note key is shared with the pre-grasp supply class

`PREREG_P2.md` §Falsifiers **F4**: *"the place leg loses payloads -> the cell is
inadmissible; restore +0.08."* The report's F4 read `fruit fell off the line`
and fired on 4 events. Read at the episode level, **all four are the same
pre-grasp supply event and none is a place-leg payload loss**:

| log | episode | fruit | arm | `grasped` | `ticks` / `decision` |
|---|---|---|---|---|---|
| C1 (77) | 5 | kiwi 6.3 cm | right | **False** | 1280 / 1280 |
| C1 (77) | 8 | kiwi 6.3 cm | right | **False** | 1251 / 1251 |
| L1 (77) | 10 | kiwi 6.3 cm | right | **False** | 1193 / 1193 |
| L2 (77) | 1 | kiwi 6.3 cm | right | **False** | 1101 / 1101 |

Every one is `grasped=False` with `decision == ticks` (the episode ended at the
policy's horizon with nothing ever grasped) on the **right** arm — the arm the
knob does not touch — and **two of the four are in the control arms**. The note
is the supply/transport event P60's census already carries (`fruit fell off the
line` fires when a candidate rides off the belt end before the trigger admits
it), not a payload dropped out of the hand.

**The intended read — a payload lost on the place leg — is a different
population, and it is measured**: on the left, the legs whose *lift* was clean
(`clean_slip_max <= 50 mm`) and whose `place0` then escaped read

| arm | left cnps | lift-class | **place-class** | share of the lift legs |
|---|---|---|---|---|
| C1 | 12 | 11 | **1** | 1/13 |
| C2 | 20 | 19 | **1** | 1/21 |
| L1 | 16 | 2 | **14** | 14/17 |
| **L2** | 6 | 0 | **6** | **6/16** |

so the place-leg loss is **6/16 at the 0.20 rung** against **2/34 in the pooled
controls**, and the rungs move it in the *opposite* direction to a payload-loss
defect (it is the *replacement* class for a lift that no longer escapes). **In
the control the endpoint is barely measurable at all**: 12/13 of C1's and 21/21
of C2's left place rows read `contacts@onset = 0`, i.e. the pads entered the
place leg with the payload already gone (the lift-class escape) — only the
single C1 leg records a place-leg loss the instrument can see.

**Disposition: F4 fired on a shared note key, not on its mechanism.** The
registered clause's *intent* (a place-leg payload loss makes the cell
inadmissible) is **not** what the four events are; the place-class read is the
6/16 above, and which arm it is read in is the new rung's. Phase 3 therefore
carries **F4 restated**: a `fruit fell off the line` on a **left** episode with
`grasped=True`, or any **place-class** leg at a rate above the control's, is the
inadmissibility trigger; a bare note-key hit with `grasped=False` is supply.

## D3 — **P3 was self-contradictory**: the dose is `|tool_y|`, the share is withdrawn

`PREREG_P2.md` §Endpoints, the manipulation check, asked for two things that
cannot both hold: *"the achieved belt projection **unchanged (+0.32..+0.37 ±
0.03)**"* **and** *"`drift_end` falls to 3 deg"*. The projection is
`sin(tilt) * share`, so holding it fixed while the tilt falls 24.6 -> 0.7 deg
would require the share to rise ~30x — it cannot.

Measured (`logs/p66/p2_report.txt` P3): the **`|tool_y|` dose** is
`0.322 / 0.327 -> 0.162 -> 0.002` for `0.36 / 0.36 -> 0.28 -> 0.20`, i.e. it
collapses with the tilt exactly as the geometry requires. The registered
"unchanged" clause is **withdrawn**: it described a test that would have asked the
ladder to be a *drag* test rather than a *rotation* test, and the ladder is a
rotation test (grip, station, azimuth and command held; one height moved).

`share = |tool_y| / sin(tilt)` is **not** an invariant to test either: at the
0.20 rung the denominator is `sin(0.7 deg) = 0.012`, so the quotient is a
knife-edge ratio — a 0.1 deg tilt change moves the share by tens of percent
(measured share at L2: `0.16 [0.04-0.52]`, vs `0.72 / 0.74 / 0.71` above it).
**Disposition: the dose is `|tool_y|` (and, for free, `drift_end` itself, which
*is* the tilt on these legs — `|drift_end - tilt|` median 0.1-3.6 deg); the
share is withdrawn and must not be quoted as an invariant in either direction.**

---

## D4 — **the phase-3 brief's rung values contradict its rung labels** (new)

The brief names the two rungs *"the 0.20 and 0.24 rungs"* (three times: the
`clr` question, the "does 0.24 match 0.20 at half the cost" verdict, and the
recommendation line) and gives their env values as *"the rungs `-0.12` and
`-0.16`"*, with `FRUIT_LIFT_DZ=+0.08` as the control. **Those two sets are not
the same experiment.**

`FRUIT_LIFT_DZ` is read by `tasks.jaw_target("grasp_lift")` as

```
z = belt_top + 0.28 + dz        # armed: dz *replaces* the hand's 0.08 add
```

(phase 2's own header and the `[grasp] lift_dz:` row both state it; the phase-2
table in `PREREG_P2.md` is `+0.08 / 0.00 / -0.08` = `0.36 / 0.28 / 0.20`). The
brief's `-0.12` / `-0.16` are `target - 0.36`, i.e. **measured from the shipped
height instead of from the 0.28 base**:

| brief's label | brief's env value | target under `0.28 + dz` | target under `0.36 + dz` |
|---|---|---|---|
| 0.24 rung | `-0.12` | **0.16 m** | 0.24 m |
| 0.20 rung | `-0.16` | **0.12 m** | 0.20 m |

**Disposition: the labels are run, the values are corrected to the code's own
base — `0.24 rung = FRUIT_LIFT_DZ=-0.04`, `0.20 rung = FRUIT_LIFT_DZ=-0.08`.**
Three independent reasons, in order of weight:

1. **Physics.** At `0.12 m` above the belt the pads (which hang 0.08 m below the
   jaw centre) sit **0.04 m** above the belt and the payload's lowest point is
   ~0.02-0.03 m above it — a "lift" that is still in contact with the main belt,
   so the lateral transfer would drag the payload along it. That is not a rung of
   this ladder, it is a different (broken) cell.
2. **"half the cost".** `0.24` is `|dz| = 0.04` below the 0.28 base against the
   0.20 rung's `0.08` — **exactly half**, which is the phrase the brief uses and
   the question it asks. `0.16` would be *twice* the cost of 0.20, not half.
3. **The mediator is already flat.** Phase 2 measured `drift_end` = **0.7 deg**
   at 0.20 (the static curve's floor is 0.79 at 0.09). A deeper rung cannot buy
   more rotation; it can only spend clearance. Phase 3's question is therefore
   necessarily *shallower* than 0.20, never deeper.

**What this costs the brief's reading**: the batch answers "is 0.24 enough, and
does the place leg keep its clearance", not "how deep can the lift go". The
brief's own stop rule is preserved and made sharper: **if the 0.20 rung's place
`clr` minimum is negative, stop and report — the lever must be re-shaped, not
shipped**, and the same rule applies to 0.24 (a negative there ends the lane
outright, since 0.24 is the cheaper rung).

---

## D5 — **the package's default is the 0.20 rung in the code's own units** (new)

The brief's step 2 asks for *"the direct default `-0.16` with `FRUIT_LIFT_DZ=+0.08`
as the documented restore"*. `-0.16` is the same `target - 0.36` slip as D4: under
`0.28 + dz` it would be `0.12 m`. **The package therefore carries
`LIFT_DZ_DIRECT_DEFAULT = -0.08` (= `0.20 m`, the phase-2 L2 rung, the rung the
brief's `-0.16` denotes), and `FRUIT_LIFT_DZ=+0.08` restores the shipped
`0.36 m`.** The constant is named once (`rl_env.LIFT_DZ_DIRECT_DEFAULT`) and
printed with its height, so the units cannot drift: the row reads
`dz=-0.0800(default) -> 0.2000 m above the belt`.

Nothing is adopted by writing it (**no commit, no `configs/` edit**), and the
batch cannot see it (every arm passes `FRUIT_LIFT_DZ` explicitly, so all three
arms print `(explicit)`). If the batch recommends the **0.24** rung instead, the
package's default moves to `-0.04` — one constant, and the flip is still one
line.

## What is **not** deviated

* The cell is the brief's: seeds **77/101/202/303/404**, 15 picks, one claim per
  run, `FRUIT_CARRY_DIAG=1`, `FRUIT_MOTION_REPORT` **unset** (the new `clr` field
  carries the clearance), the shipped direct profile with no supply env, the P43
  park default and the P54 `ACQ` default as shipped.
* The control arm passes **`FRUIT_LIFT_DZ=+0.08` explicitly** (the brief's
  control), so the arms are `+0.08` / `-0.04` / `-0.08` = `0.36 / 0.24 / 0.20`
  and the phase-3 default flip (D5, `rl_env`'s `-0.08` default) is **inert in
  the batch** — every arm names its own value.
* The scripted line is untouched (`accept.sh` 377/377 + `fingerprint: matches`,
  an import guard), `configs/*` untouched, no commit.
