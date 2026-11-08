# P129 - the pad material: does `mu_pair < 1` centre a ring, and what does it cost?

**The owner's decision** (`docs/END_EFFECTOR_DECISION.md` section 4.1, nail (i)): a
pad whose **pair** friction with the fruit is below 1. Bench first, then the sim.
The claim under test is algebraic and specific: P111's closed form
`delta_inf = (2 mu - 1) * min(s, cap/(2 mu k))` says a four-pad ring cannot centre
at the measured pair friction **1.25-1.46**, and `mu < 1` would make the payload
slide to the ring's centre.

**What this phase is.**  Three steps, in order, and it stops at a kill:

1. the **algebra**, re-derived (`logs/p129/algebra.py` -> `algebra.txt`);
2. **bench A** - the pair friction itself, and the pinch's trade
   (`logs/p129/fixture_pinch.py`, P117's rig);
3. **bench B** - the ring's closure across the mu ladder, the close stiffness and
   the line's own first-contact freeze (`logs/p129/fixture_ring.py`, P112's
   protocol).

**The kill** (section 4) either publishes a negative or licenses a cell.  No cell
is run unless the bench passes.

**Version pins (this tree).** `tasks.py` `50fd799d`, `cage_hand.py` `42c4eb64`,
`scene.py` `b3bf8067`, `assets.py` `24d29679`, `rl_env.py` `3aed67b9`;
`configs/motion_reference.json` = `..._twoline.json` = `30fb99f8`,
`..._single.json` = `8952c320`; ckpt `moe_v13s` `61da390a`.  Nothing in `src/` or
`configs/` is changed by this phase: **both knobs it needs already exist**
(`FRUIT_FINGER_MU`, `FRUIT_CAGE_PAD_MU`, `FRUIT_CAGE_CLOSE_STIFFNESS`,
`FRUIT_CAGE_HOLD_STIFFNESS`, `FRUIT_DYNAMIC_CLOSE_FREEZE`).

---

## 1. The algebra first (offline, before any cell)

`logs/p129/algebra.py` re-derives the static fixed point for four and three pads
in 2-D with the **tangential projection** (P112's model, which reproduced P112's
fixture), at `mu = 0.6 / 0.8 / 1.0 / 1.2` and the measured control 1.25-1.46.

**Four pads, two opposed loaded and the perpendicular pair carrying the
friction:** `drive = 2 k delta`, `resist = 2 mu k s` (plus the belt), so

    delta_inf = mu s          (linear regime, far pad loaded, near pad not capped)

and **the far pad leaves at `delta = s`, so `delta_inf < s` is exactly `mu < 1`.**
The solver reproduces it to <= 2 % (0.59 / 0.80 / 0.98 s at mu 0.6 / 0.8 / 1.0 on a
29.6 mm fruit).

**A correction to the record.**  `docs/END_EFFECTOR_DECISION.md` section 2 quotes
`delta_inf = (2 mu - 1) * min(s, cap/(2 mu k))` from P111.  That is not what
P111's own solver computes (`closed_form` there returns `mu s + mu_b m g/(2k)`)
and it is not the 2-D geometry either: for a *round* payload the perpendicular
pair's penetration is `s` at **any** offset (the plane's distance from the centre
does not depend on the tangential offset), so the resistance is `2 mu k s` and the
residual is `mu s`.  Both forms put the threshold at `mu = 1`; they differ by 2x
in the residual at `mu = 0.6` (`0.2 s` vs `0.6 s`), and the bench decides which.

**The four-contact condition is not `delta < s`, it is `delta <= s - 0.5/k`**
(a pad counts as loaded at the 0.5 N contact trigger), which gives a **stiffness
window**:

    k >= 0.5 / (s (1 - mu))        the far pad must carry the trigger
    k <= cap / (s (1 + mu))        the near pad must not saturate first

They meet at **`mu = (cap - 0.5)/(cap + 0.5) = 0.815`** at the shipped 4.90 N cap:
above that, **no stiffness** leaves four pads loaded.  Over the whole pool with
one stiffness the window closes earlier still, at **`mu = 0.613`** (the largest
fruit's cap bound meets the smallest fruit's trigger bound, `s_max/s_min = 2.35`);
at `mu = 0.6` the pool-wide window is **`[4223, 4400] N/m`**, a 1.04x sliver that
**excludes the shipped 1e5 N/m close**.  So the material is at best *half* a
package: it needs a soft close too (`FRUIT_CAGE_CLOSE_STIFFNESS`), and the two
halves were never measured together.

**A third condition, and it is the one the line meets:** capture from an offset
beyond `s` needs the near pad's cap to beat the perpendicular pair's friction,
`mu < cap/(2 k s)` = 1.07-2.51 at `k = 3300`.  At `k = 1e5` that bound is 0.05-0.12,
i.e. **the shipped rigid close cannot even start to slide at any mu** - which is
P111's measured knee.

**The price (registered, not measured):** static axial capacity `n mu N` against
the cell's own operating demand `m (g + 5.83)` = **1.92 N** for the heaviest fruit:

| mu | pinch `2 mu N` | xdemand | 4-pad `4 mu N` | 3-pad `3 mu N` |
|---|---|---|---|---|
| 0.6 | 5.88 N | 3.1x | 11.76 N | 8.82 N |
| 0.8 | 7.84 | 4.1x | 15.68 | 11.76 |
| 1.36 (measured) | 13.33 | 6.9x | 26.7 | 20.0 |

**Predictions, registered:**
* **A0** the pair is controllable: authoring `pad_mu = 2 t - mu_payload` delivers
  `mu_pair = t` (the sim averages the pair, P104 section 7a) - a *check*.
* **A1** the pinch's axial break falls as `2 mu N` (13.3 -> 5.9 N) and its
  **load-axis** creep (P117's `dz`, the friction term's own direction) stays
  `<= 0.3 mm` because the capacity is still 3.1x the demand; its **total** creep
  is mu-invariant (a seat shift along the jaw axis, P117 A6).
* **B1** (full close) `mu <= 0.8` gives `centred + 4/4 loaded` from a 20 mm
  arrival; `mu >= 1` does not.
* **B2** (the task's first-contact freeze) the aperture freezes `2 delta0` too
  wide: at `mu < 1` the payload slides to the centre and **unloads** (0 pads), at
  `mu > 1` it jams at `delta0` carrying ~the freeze force (1-2 pads).  Either way
  the line's closure does not enclose.

## 2. Bench A - the pinch (`logs/p129/fixture_pinch.py`)

P117's fixture verbatim (same station geometry, same 4.90 N/face, same 0.75 s
`m(g + 5.83)` hold, same 5 N/s break-away ramp) with one addition and one family:

* **A0, the pair friction.**  A **40 mm flat cube** payload (face-face contact, so
  the normal force is the drive's own cap and the tangent is the plate's face)
  is pinched and pulled along the load axis; `mu = (F_applied + m g) / sum(N_pads)`
  at the 2 mm break.  Targets `0.4 / 0.6 / 0.8 / 1.0 / 1.2 / 1.36`, three repeats,
  `pad_mu = 2 t - 0.70`.
* **A1, the ladder.**  Profiles `flat` (pad mu 2.0, the shipped control) and
  `pair06 / pair08 / pair10 / pair12`; 4 fruits (pear, orange, strawberry, lychee -
  P117's set), 3 repeats, so **60 cells** with a same-batch control.

**Rejected readings, registered.**  The decision book's kill is "creep > 1.0 mm at
the operating load".  On this rig the **total** creep is 8.62 mm on the pear at the
shipped mu - it is a seat shift along the jaw axis and is mu-invariant (P117 A6
measured -4.8 % for mu 2.0 -> 4.0), so the letter of that clause fails **every**
material including the incumbent and cannot discriminate one.  The registered
reading is therefore the **load-axis component** (the direction the load acts,
tangential to both pad faces), with the total reported beside it; and a separate
**retention** clause (the payload must stay in the pinch on every fruit at the mu
that centres) because a material that loses the payload is a trade, not a win
(the book's own sentence).

## 3. Bench B - the ring (`logs/p129/fixture_ring.py`)

P112's protocol (the hand's own `cage_hand.author_cage` path, the task's 24 + 60
tick close, the 0.5 N / 3-tick rule, `off0 -> off`), with the payload replaced by
a **square prism** - the algebra's own 2-D case: its four faces are planes on the
four pad faces, so every pad's penetration is `s + delta cos(theta)` at any offset.
A *sphere* cannot test this and was refuted in the build smoke (below).

Cells: pair targets `0.6 / 0.8 / 1.0 / 1.2` **and the shipped pad mu 2.0 (pair
1.35)**; close stiffness `4300` (the algebra's window at mu 0.6) and `1e5` (the
shipped drive); protocol `full close` and `freeze`; arrivals `0 / 5 / 10 / 20 mm`;
two prism sizes (36 mm, 66 mm).  **160 cells**, two app sessions (one per hand
kind; cage4 is the round payload's own ring).

**Support proof** (P107/P112's lesson): gravity off (P112's accepted form); the
pads home -> the prism does not move over 200 ticks; a **frictionless** prism
(mu 0.0) closed from 10 mm -> it centres, to the algebra's `mu_pair = pad/2`
value.  If either fails, no real cell is spent.

## 4. The kill

The phase publishes a negative and stops if **any** of:

* **K1 - the material cannot be made.**  A0's measured pair at the ladder's pad
  values is `>= 1.0` (the four-jaw cannot centre whatever the form).
* **K2 - the material is not needed.**  B1's **control** cell (pair 1.35, full
  close) already reaches `centred (<= 1.5 mm) + 4/4 loaded` from a 10 mm arrival:
  then `mu < 1` buys nothing the incumbent does not have, and the nail closes
  whatever the other cells say.
* **K3 - the line's protocol denies the enclosure at every mu.**  B2's freeze
  cells read `< 3/4` pads at the flush on every mu including the control: the
  material cannot convert a closure the protocol freezes, and the purchase is the
  protocol, not the pad.

Recorded, not gated: the pinch's A1 ladder (capacity/creep/retention by mu) -
it prices the trade if K2/K3 had not fired.

## 5. The cell (only if no kill fires)

Single-arm `cage4` (a cage hand is refused in a `CoopSession`, so the shipped
two-line is out of scope), 20 attempts x 2 seeds, arms = the shipped ring vs the
low-mu + soft-close package.  Endpoint: **P110's clean enclosure** (join each
`[cage]` row to its own `[motion] approach ... end=` and split jam /
over-closure / clean - the raw pad count is never the endpoint) and the placed
count.  Guards: crush (`sep@loss - dia`), landing (`on_belt`), descent budgets
(not re-tuned), and `scripts/accept.sh` with every knob unset (8/10 +
`fingerprint: matches` + 421/421 identical to `logs/p127/accept_restored.log`).

## 6. Build smokes (run before this registration - recorded, not hidden)

P103's precedent: the rigs have to be built before the clauses can be written, and
two of the smokes changed the *form* of the bench.  None of the clauses above was
changed after the registered cells ran.

* **A1 smoke** (2 fruits, 1 repeat): the `flat` control reproduces P117's table
  (pear `creep_op` 8.47 vs 8.62, orange 9.07 vs 9.07, strawberry 0.98 vs 0.98,
  lychee 12.42 vs 12.42), so the rig *is* P117's rig.  At pair 0.6 the **strawberry
  and lychee are ejected during the seat** (0 pads, `creep_g` 1.24 m) with the rig's
  own 5 mm interference - which is why the retention clause exists.
* **A0 smoke** (4 targets, 1 repeat): `sumN` 9.80 N and `mu_meas` 0.43 / 0.63 /
  0.67 / 1.15 against targets 0.40 / 0.60 / 1.00 / 1.36 - the pair tracks the
  target at the low end and *saturates* near 1.2 (the same saturation P117 saw at
  pad mu 3.0/4.0).
* **B smoke with a sphere**: **every** cell centred to 0.00 mm with 4/4 pads at
  both pair 0.6 and 1.35, i.e. no discrimination at all.  The mechanism is
  geometric: a sphere's surface retreats from the perpendicular pair as it
  transits, and the pair's contact patch leaves the 26 mm plate beyond
  `delta ~ 9 mm`, so the payload slides in **friction-free whatever the material**.
  That is why the registered payload is a square prism.
* **B smoke with the prism** (pair 0.6/1.35, k 4300/1e5, offsets 0-20): full close
  = `0.00-0.07 mm, 4/4` at **both** mus and **both** stiffnesses; freeze =
  `1-2/4` pads at both mus.  Recorded here as the smokes' reading - the registered
  cells below are the same configuration run to completion.

## 7. Deviation register

Open.  Each deviation is appended with its date and the reason, and no cell is
re-labelled after it runs.
