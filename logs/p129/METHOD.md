# P129 - method

**The question.**  The decision book's nail (i) (`docs/END_EFFECTOR_DECISION.md`
section 4.1): a **pad material whose pair friction with the fruit is below 1**
should let a four-pad ring centre (P111's algebra says it cannot at the measured
1.25-1.46), and it must not cost the pinch.  Bench first, then the sim.

**Why a bench and not a cell.**  The claim is a *contact* property: the pair
friction and the payload's motion between loaded pads.  A cell confounds it with
the aim, the descent, the catch-up and the delivery - P111 and P112 both had to
build fixtures to separate those, and this phase inherits both rigs rather than
invent one.

---

## 1. The three steps

### 1.1 The algebra (`logs/p129/algebra.py`)

Offline, 2-D, the **tangential projection** (P112's model, re-implemented so this
phase's numbers cannot inherit a convention it did not check).  It answers, in
order: the static fixed point `delta_inf(mu, s, k, cap)` for four and three pads;
the **four-contact** condition (every pad >= the 0.5 N trigger, not merely
`delta < s`), which is a *stiffness window* and a *friction ceiling*; the price
(`n mu N` against the cell's own demand).

Two record corrections come out of it, and both are checked by the benches:

* **P111's headline formula is not its own solver.**  The decision book quotes
  `delta_inf = (2 mu - 1) min(s, cap/(2 mu k))`; P111's `closed_form` returns
  `mu s + mu_b m g/(2k)`, and the 2-D geometry gives `mu s`.  The threshold is
  `mu = 1` either way; the residual differs 2x at `mu = 0.6`.
* **The four-contact state is a window, not a threshold.**  `k in [0.5/(s(1-mu)),
  cap/(s(1+mu))]`, which is empty above `mu = (cap - 0.5)/(cap + 0.5) = 0.815`
  per fruit and above **0.613** over the whole pool with one stiffness.

`P112's algebra.py` has a sign error in `fixed_point` (it subtracts the drive, so
every trial runs *away* from the ring's centre); its closed forms are unaffected
and its fixture numbers are the measurement.  This phase's solver moves along the
drive and is checked against both closed forms (<= 2 % inside the linear regime).

### 1.2 Bench A - the pinch (`logs/p129/fixture_pinch.py`)

P117's rig, one app session, the payload teleported between stations.

* **A0, the pair friction** (the book's first endpoint: "report the pair, not the
  pad alone").  A **40 mm flat cube** between two pads: face-face contact, so the
  normal force is the drive's cap (measured 9.80 N over two pads) and the tangent
  is the plate's face.  The cube's own mu is 0.70, the pads are authored
  `mu = 2 t - 0.70`, and the cube is pulled down until it slides:
  `mu_measured = (F_applied + m g) / sum(N)`.  Six targets, three repeats.
  *Why a cube*: it removes the fruit's curvature from the normal-force bookkeeping
  and makes the pair the only unknown.
* **A1, the ladder.**  `flat` (pad mu 2.0 - P117's own cells, the same-batch
  control and a reproduction check) and `pair06/08/10/12` (the pad mu resolved per
  fruit so the **pair** is the target).  Four fruits, three repeats, 60 cells,
  P117's protocol unchanged: a 5 mm commanded interference (its constant-delivered
  force design), a 90-tick settle, a 90-tick `m (g + 5.83)` hold, then a 5 N/s
  break-away ramp.
  Endpoints: the **load-axis** creep (`dz`, the friction term's own direction),
  the **total** creep (reported, because it is the book's letter - and it is
  mu-invariant, see RESULTS), the axial break, the pad count, and **retention**.

### 1.3 Bench B - the ring (`logs/p129/fixture_ring.py`)

P112's protocol, three changes, each forced by the question:

* **payload = a square prism**, the algebra's own 2-D case (see RESULTS section 2
  for the sphere smoke that forced it);
* **five rings on one stage**, one per pair target, authored by
  `cage_hand.author_cage` with the module's `PAD_MU` set per ring (`_material`
  reads it at call time, so the material is authored, never edited after `play()`);
* **the close stiffness is a cell variable** (4300 = the algebra's window at
  mu 0.6; 1e5 = the shipped drive) and **the protocol is a cell variable**
  (full close vs the task's first-contact freeze) - because the algebra says the
  material is only half a package.

Gravity off (P112's accepted support proof) and two support cells before any real
one: pads home -> no motion; a frictionless prism -> it centres, to the algebra's
value.  Measured aperture/per-pad force from the pad bodies; the pad count is
taken from the **maximum each pad carries over the settle**, because the tensor
API's contact-force matrix is not populated on every tick with an existing
contact pair (measured: 0 N at the flush while the pads are 0.2 mm inside the
prism and the spring law says 0.8 N - `logs/p129/fixture_ring.log`).

---

## 2. Read rules fixed before the cells

1. **A break-away is not a creep**, and the creep is split into its **load-axis**
   and lateral components (P117's correction).  The decision book's total-creep
   clause is reported but cannot be the verdict: on this rig the *total* is 8.62 mm
   on the pear at the shipped mu, so it fails every material including the
   incumbent.
2. **The ring's endpoint is the enclosure**, not the raw pad count: a ring that
   centres and loads all four pads is one state; a ring that jams with four pads
   is another; a ring that centres and unloads (the frozen-aperture case) is a
   third.  The class is named per cell.
3. **A cell count is a branch** - no count is quoted from this phase (no cell ran).
4. **A fixture must prove its support** (P107/P112's lesson), and the proof is
   *quantitative* where the algebra gives a number (the frictionless prism must
   land at `mu_pair * s`).

## 3. What this bench cannot say

* It measures **rigid, adhesion-free** pads in a **weightless** fixture.  A real
  elastomer's pair friction against a real fruit is a *physical* bench (a printed
  coupon and a fruit), not this one; this phase answers "if a material with pair
  friction `t` exists, what does it buy and cost?".
* The 5 mm commanded interference is P117's design (it makes every profile deliver
  the same normal force).  It is harsher than the line's 1 % seat, so the
  small-fruit ejection A1 measures is a *squeeze-out at that seat*, not a
  prediction of the line's seat.
* The prism is isotropic.  A real fruit's anisotropy is P112's measured term and
  is the reason the four-pad ring's perpendicular pair is short on the line; a
  material cannot close a *geometric* gap.
