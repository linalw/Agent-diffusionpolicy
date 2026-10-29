# P61 phase 2 — amendments to `logs/p61/PREREG.md`

## A1 — the grasp-axis **names** in §3's map were wrong (names only)

**When.** Written after the batch started (seed 77 complete, seeds 101/202
running) and after one single-seed smoke read of the report script. **What it
changes:** the *physical names* attached to the hand-frame axes. **What it does
not change:** every endpoint (P1–P5), every threshold (escape 50 mm, transient
5 mm, mixed 0.70, dead zone 5 mm), every vector (they are `R^T·v` computed from
`configs/waypoints_oriented.json`, not from a label), and the decision rule,
which is applied to the same three components of the same printed field. No
number in any result depends on which name an axis carries.

**The error.** §3 labelled world `±x` "the jaw axis", following
`_carry_attitude`'s docstring ("jaws close along X, travel along -Y"). That
sentence describes a **top-down** attitude. For the *calibrated* quaternions the
jaw opening axis is the TCP's **column 1** — `kinematic_gripper.py:407`,
`axis = rot[:, 1]`, with the pads placed at
`centre ± axis·(gap/2 + …)` — and the **tool axis** (the direction the fingers
extend, the wrist sitting behind the pads along `−down`) is **column 2**
(`down = rot[:, 2]`). The correct world directions are:

| grasp axis | left (world) | right (world) | cos with the belt (−y) |
|---|---|---|---|
| hand x | (+0.075, −0.034, +0.997) | (+0.075, +0.034, +0.997) | +0.034 |
| **hand y = jaw opening axis** | (−0.514, **−0.858**, +0.010) | (+0.514, **−0.858**, −0.010) | **+0.858** |
| **hand z = tool axis (finger length)** | (**+0.854**, −0.513, −0.082) | (**+0.854**, +0.513, −0.082) | **+0.513** |

So the corrected reading of the §3 decision table is:

| hand-frame | means | world |
|---|---|---|
| **+y** (0.858) | along the **jaw opening axis** — slid through the pads | ≈ belt **−y** |
| **−x** (0.997) | **down** (the payload lags the lift) | −z |
| **±z** (0.854) | along the **tool axis** — out along the finger length | ≈ ±x (across the belt) |

**A confound this exposes, registered now:** the jaw opening axis is only
**30°** from the belt direction (`cos = 0.858`), because this calibrated grasp is
diagonal — the pads press the fruit from upstream/downstream, not across the
band. A pure *direction* therefore **cannot** separate "dragged by the belt"
from "slid through the jaws"; both live on hand +y. The belt hypothesis is
therefore only falsifiable in the form the brief states it — **hand +y
dominant** — and the tool-axis hypothesis is hand ±z, the lift-axis hypothesis
hand −x. Reporting both the hand-frame components and the world-frame vector is
what makes the two separable-ish; the residual ambiguity is stated in the
results, not resolved by this instrument.

## A2 — the right-arm contrast is expected to be unmeasurable (no change)

§4's contingency already covers it: if the right has `< 3` escaping legs, the
primary read is the left's own direction. Stated here in advance of the pooled
read so it cannot look like a post-hoc retreat: **P60's right had 0 cnps**, and
the right's four transients were 2.6–11.3 mm, far below the 50 mm escape bar.
The right's `slip_xyz` on transients is reported as evidence, never as a
contrast.

## A3 — the direction read is restricted to **in-hand slides** (found in the data)

**When.** Written after the batch (3/3 exit 0, no wedge; 10:38:27–11:06:43) and
after the first pooled read, on seeing two rows that cannot be in-hand motion.
**What it changes:** which rows enter P2's distribution. **What it does not
change:** P1, P3, P4, P5, the escape threshold (50 mm), the dominant-axis rule,
or the frame map.

**The rows, and why they are not slips.**

| row | `clean_slip_max` | why it is not an in-hand slide |
|---|---|---|
| `S_202` ep3 left `grasp_lift` | **49 596.8 mm** | `onset_row=1`, `sep@onset=98.3 mm` (the pads already at their open stop), `force@onset=27.73 N`, `in-hand_vmax=9.208 m/s`, `loss_row=9`: a **close-time ejection**, not a slide. Its `place0` row reads 126 532.6 mm (a respawn teleport). |
| `S_202` ep8 left `place0` | 102 692.7 mm | the same: a teleport, no in-hand meaning || 13 × left `place0` (1 095–1 444 mm) | 1.1–1.4 m | the **downstream view** of a payload already gone (P60 §3.4): the metric then measures the hand's own 0.5–0.6 m transfer away from a static fruit |
| `S_101` ep12 left `place0` | 696.2 mm | the payload was held through the lift and lost in the transfer, so the vector mixes the arm's travel with the slip |
| `S_202` ep2 right `place1` | 158.7 mm | same class, right arm |

**The rule (mechanical, quoted with the count it removes).** The direction read
uses the attempt's **first `grasp_lift` leg with `50 < clean_slip_max <=
1000 mm`**:

* **`grasp_lift` only**, because the frame-free property holds only while the
  payload is in the hand; P60 measured **19/19** left escapes as `grasp_lift`
  and this cell reproduces **14/14**;
* **`<= 1000 mm`**, because W8-B's escape corpus tops at **957 mm**, the hand's
  own transfer is 0.5–0.6 m, and the two > 10 m rows are ejections/teleports
  whose printed vector has no physical slip behind it.

**What it removes and what it leaves.** Registered set (any first escaping leg,
`> 50 mm`): **16** left attempts; the slide set: **14**. The two dropped are the
ejecta row and the 696 mm transfer loss. Because one of them is 49.6 m, the
**registered set's signed mean y is −2 446.5 mm** while the slide set's is
**+65.3 mm** — i.e. the raw mean on the registered set is one ejection's
artefact. **Both are printed** in `logs/p61/p2_report.txt`, the registered set on
its own line, so the exclusion is visible rather than silent. The right arm is
unaffected (its one escape is a `grasp_lift` at 329.5 mm).

**Consequence for the reading.** P2's verdict rests on the 14-leg slide set and
is stated with `n = 14`; the ejecta row is reported as its own tail (1/45
episodes, a close-time ejection at the pads' open stop) and is **not** pooled
into any direction statistic.
