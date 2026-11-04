# P112 method - the three-jaw ring: algebra, build, fixture, battery

The owner's choice was P111's **item 2**, the three-jaw ring, on P111's own
algebra: *the count of tangential contacts is the lever, not the drive*.  This
file records the protocol and, in section 2, the **seven fixture iterations** -
because the decisive test needed a payload support that could be trusted, and
three plausible ones were not.

## 0. The order of work (and the kill)

1. **The algebra, before any build** (`algebra.py` -> `algebra.txt`): the 3-pad
   contact set, the 2-D quasi-static fixed point, the cap branch, the stiffness
   window, and the registered **kill** - *if `delta_inf >= s` at the measured
   `mu` pair, the 3-jaw does not centre either and the phase stops before
   building.*  Measured: `delta_inf/s` = 0.84-0.92 over the pool and
   `mu` 1.25-1.46, so **the kill does not fire**.
2. **The build** (`cage_hand.py`, a third hand kind, default off).
3. **The fixture** (`fixture_cage3.py`): the closure's own mechanics, no arm.
   **If the fixture cannot centre, no battery is owed.**  Measured: 0-20 mm
   arrivals end at 0.5-1.9 mm, so the battery is owed.
4. **The battery** (`PREREG.md` md5 `77720306e9328cf6e7853427cbe41f94`, pinned
   before any cell; `cells.sh`, `p112_report.py`).
5. The verdict, the hardware price and the no-harm.

## 1. The algebra (`logs/p112/algebra.txt`)

Three pads at 120 deg, a payload of radius `R` offset by `delta` along `phi`;
penetrations `p_k = s + delta cos(theta_k - phi)` with `s = R - a/2`.

* **The contact set is wider than the 4-jaw's**: the minimum penetration is
  `s - delta/2`, so all three pads stay loaded to `delta = 2s` where a 4-jaw's
  far pad leaves at `delta = s`.
* **The drive and the friction**, in 2-D and with the **tangential projection**
  the P111 closed forms dropped:
  `D = -sum N_k u_k`, `F = mu sum N_k sqrt(1 - (m.u_k)^2) + mu_b m g`.
* **The fixed point** `D = F` at 3 pads, offset toward one pad:
  `delta_inf = sqrt(3) mu s / (1.5 + (sqrt(3)/2) mu)` = **0.84-0.92 s** at the
  measured `mu` pair (1.25-1.46).  The 4-jaw's, under the same solver, is
  **`mu s` = 1.00-1.46 s**.  The thresholds are `mu < sqrt(3) = 1.73` (three
  jaws) and `mu < 1` (four) - and the measured pair friction sits between them,
  which is the phase's whole premise.
* **P111's closed forms are one term out**, and the phase records it rather than
  re-quoting them: `(2mu-1)s` (4-jaw) and `2 mu s/(1.5+mu)` (3-jaw) both drop
  the projection.  Against this solver they are 20-30 % pessimistic on the
  4-jaw and ~9 % optimistic on the 3-jaw; **both verdicts survive**, and the
  3-jaw's margin is smaller than P111's paragraph implied.
* **The cap branch is the design constraint**: `N_k = min(k p_k, cap)` saturates
  the *near* pad first, which removes drive without removing friction and pushes
  the fixed point outward.  Two conditions bound `k`:
  `k >= 0.5/(s - delta_inf/2)` (the two narrow pads must count) and
  `k <= cap/(s + delta_inf)` (the wide pad must not saturate early).  Over the
  whole pool at `mu` 1.46 the window is **[2.9e3, 3.8e3] N/m** and the build
  takes its geometric mean, **3300 N/m** (c = 2 sqrt(k m) = 16.2 Ns/m).

## 2. The fixture: three supports that could not be trusted

The fixture is one payload at a known offset, a ring closing on it at the task's
clock, and `off0 -> off` read from the same instrument the line uses.  Each
iteration below is a measured defect, and the fourth is the one that works.

1. **Static table, nominal seat.**  The payload was placed on a static box at
   `table_top + r + 0.2 mm`.  Measured: the payload **drifted 3.9-4.7 mm** during
   the settle with **zero pad force** (`f = [0, 0, 0]` on three pads).  Cause:
   `meshes.axis_extent` is the *undeformed* profile, the **mesh is 2-6 % bigger**,
   so a nominal seat embeds the payload and PhysX's depenetration kicks it
   sideways.
2. **Static table, 4 mm clearance, settle-then-replace.**  Measured: the payload
   **sank 2 mm through the table and slid at 0.5 m/s^2**.  A static scaled cube
   does not hold it (`logs/p110/fixture_gate.py` uses a *kinematic* body).
3. **Kinematic table.**  Identical numbers to (2) to two decimals - i.e. the
   table was never the thing holding the payload: it was falling past it.
4. **The shipped belt at 0 m/s.**  The proven collider from P110.  Measured: the
   same 2 mm sink and a 4-5 mm creep, still with zero pad force.  **This is the
   finding that forced the decision**: the artifacts are all the same size as
   the quantity the fixture exists to resolve, and the phase could not make a
   passive support honest in the time available.
5. **Zero gravity, no support (the adopted form).**  The closure is a **2-D**
   problem: the payload is a free body with the scene's gravity magnitude set to
   0 (`/PhysicsScene`).  What this drops is the support's own friction term
   (`mu_b m g` = 0.1-1.3 N against a 5-15 N drive) - stated, not hidden.  Two
   smaller bugs were found while getting here and are recorded because they cost
   the phase time:
   * **the world azimuth vs the authored azimuth.**  `cage_hand` authors the
     ring with its pads at **+z** in the base frame and the grasp at **-z**,
     because on the arm `_write_base` rotates the base so its +Z is the tool axis
     *down the fingers*.  A fixture with an identity base has its pads 50.5 mm
     **above** the payload and reads **0.00 N on three pads 0.6 mm inside the
     fruit**.  The ring's root is therefore turned over by 180 deg about x, and
     a pad's **world** direction is `(cos theta, -sin theta)` - reading the
     authored theta instead put one pad's face radius *negative*.
   * **the force view must be filtered to the payload**
     (`RigidPrim(pad, contact_filter_paths=[fruit])`), P104's own pattern; an
     unfiltered read is 0.00 N.
6. **The first honest cells**: with the ring turned over and the payload
   weightless, a 0 mm arrival stays at 0.71 mm and a 5 mm arrival is pulled to
   0.85 mm, with **3/3 pads loaded** (`fmax` 1.8 N).  That is the algebra's
   centring, measured.
7. **The k ladder and the protocols** (`run_p112_fixture.sh`: 2 hands x 3
   protocol arms x 3 fruits x the k ladder x 5 offsets = 390 closures).

## 3. The fixture's result (`fixture_report.txt`)

The registered gate was "does `off` fall below `off0`".  It does, for **both**
hands, and that is the first thing to say because P111's *line* read was "+0.2 to
+2.0 mm":

| arrival | cage3 `off_end` (p50) | cage3 pads 3/3 | cage4 `off_end` (p50) | cage4 pads 4/4 |
|---|---|---|---|---|
| 0 mm | 0.71 | 4/6 | 0.51 | **0/6** |
| 2 mm | 0.54 | 6/6 | 0.68 | **2/6** |
| 5 mm | 0.82 | 4/6 | 0.74 | **0/6** |
| 10 mm | 0.97 | 2/6 | 0.85 | **0/6** |
| 20 mm | 1.88 | 2/6 | 1.02 | **0/6** |

(the delivered configuration: the task's freeze, the 1e5 hard stop, k = 3300.)

**Read it as two separate statements.**

* **Centring is not the ring's problem in isolation.**  A closure with a clean
  arrival and no arm centres 0-20 mm to under 2 mm, at both pad counts.  P111's
  +0.2 mm on the line is therefore *not* evidence that a ring cannot centre; it
  is evidence that on the line the arrival, the tracking and the freeze dominate
  (P108: the close-time offset is 2.9-3.1 mm and the *aim* offset is 8.8 mm).
* **The 3-jaw is the only one that loads its own pads.**  `pads == 3` on 18 of 30
  cells at the delivered configuration, against **`pads == 4` on 2 of 30** for
  the 4-pad ring - and 0/30 in the full-close arm.  That is the algebra's own
  claim, measured at the closure: **the 4-jaw cannot load its opposed pair at a
  0.98 x widest aperture, and the 3-jaw loads all three because its aperture law
  takes the narrowest of its own axes.**  This is what the licensed
  `n mu N` capacity (3 x 4.9 N = 1.5x the pinch) needs.

The cost is measured too: the min-extent law **over-closes on the smallest
fruit** (`sep - dia` down to **-7.9 mm** on a 29.6 mm lychee, against the 4-pad
ring's -1.8 mm), i.e. a 27 % radial interference - within the -15 mm crush rule
but the reason the battery's crush guard is an endpoint rather than a formality.

## 4. The battery protocol

`PREREG.md` (md5 `77720306e9328cf6e7853427cbe41f94`), pinned before any cell.
The scripted single arm (`FRUIT_BIARM=0`; a `CoopSession` refuses a non-`openarm`
hand, `tasks.py:9543`), `ATTEMPTS=20`, seeds 5/6/101/202 (P93's fresh-seed rule),
**identical instrumentation on both arms** (`FRUIT_CAGE_PROBE`,
`FRUIT_MOTION_REPORT`, `FRUIT_CARRY_DIAG`, `FRUIT_PLACE_TRACE`), the shipped hand
as the control:

```
C:  (nothing)                                   the delivered reference
T:  FRUIT_GRIPPER_KIND=cage3 FRUIT_CAGE_OPEN_FACE_R=0.100
    FRUIT_CAGE_PAD_STIFFNESS=3300 FRUIT_CAGE_PAD_DAMPING=16.2
    FRUIT_CAGE_HOLD_STIFFNESS=100000
```

The open aperture is **200 mm**, not 120: P108 measured that a 120 mm ring
blocks the descent on this line (`end` p50 57.9 mm).  The 200 mm ring is also
what P108/P111's cage cells used, so the count is comparable with the rigid
4-pad ring's 19/76.

## 5. What this phase does NOT measure

* The **two-line** scheduler (it refuses a non-`openarm` hand by construction).
* The **direct/policy** interface (the shipped hand is what it runs).
* A **real three-jaw chuck**: the sim closes one scalar aperture open-loop; a
  real scroll chuck closes until each jaw's force limit, per jaw.
* **Fruit damage**: the sim has no bruise model, so the -7.9 mm over-closure is
  a geometric number, not a quality claim.
