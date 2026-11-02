# P104 method - the axial break-away fixture (stage (ii)'s T1)

Written 2026-11-03. **No `src/` change, no `configs/` change, no shipped default
moved, no commit into `src/`.** The artifacts are this file, `RESULTS.md`, the
fixture (`fixture_probe.py`, `run_p104.sh`), its record (`fixture.txt`,
`fixture_table.txt`), the analytic frame (`analytic.py`, `analytic.txt`), and the
AGENTS/WORKLOG/`docs/PLATFORM_SURVEY.md` paragraphs.

The question is `docs/PLATFORM_SURVEY.md` §3.3's **T1** and §5.2's pre-purchase
gate, quoted verbatim so this phase cannot drift from it:

> If the hand does not beat the pinch by **>= 1.5x** in the axial direction (the
> measured escape direction, P61), the hypothesis is dead for **< $0**, and no
> hardware is bought.

Stage (i) closed in P103 (the tactile reflex: detected, not convertible, and a
net harm on the false-positive class). This is stage (ii)'s free half: **does
more contact beat the two-pad pinch on the axial drag?**

---

## 1. What the test can and cannot decide - stated before the numbers

**It can decide** whether a grasp with more, or better-placed, contacts has a
larger **static axial break-away load** on the sim's own fruit meshes and the
tree's measured pad geometry and pinch force, at the same per-contact normal
force. That is one number per form, and the bar is a ratio of two of them.

**It cannot decide**, and none of these is a defect of the execution:

1. **The full pick-and-place.** No arm, no scheduler, no attempt loop, no
   policy, no camera. A positive is **necessary, not sufficient** (§6).
2. **The acquisition.** A hand changes the approach: it is bulkier, its fingers
   arrive from more directions, and the tree's own record says the pre-contact
   class is where 4 of the 11 failures live (`logs/p47`, `logs/p48`) and where
   the scoop/ledge geometry already measured **negative** (`logs/r8/A_RESULTS.md`
   §3 - the ledges bat the payload: no-contact 2 -> 9 of 15).
3. **A real hand's kinematics and compliance.** A 16-25 DoF tendon hand is not
   `n` independent prismatic pads: its fingers are coupled, its contacts are
   soft, and its force per contact is 12 N at best (DexHand 021) against the
   4.9 N per face this fixture uses - i.e. the fixture's per-contact force is
   *already* the hand's ballpark, which is the fair comparison and also the
   limit of it.
4. **Whether a `cnp` converts.** The static axial capacity is not the load the
   cell applies; §5 of `RESULTS.md` measures that gap and it is 10-20x.
5. **Adhesion, peel, soft pads, visuotactile.** The sim's pads are rigid and
   adhesion-free (`logs/p42/SIM_LIMIT.md` §3), so the sim can falsify, never
   confirm (§3.3's own caveat).

---

## 2. The analytic frame (`analytic.py`, offline)

**Model.** `n` independent *point* contacts, Coulomb friction `mu`, no peel, a
rigid payload, quasi-static. The seat puts every contact normal **perpendicular
to the tool axis** (the pads' faces are parallel to it, and a pad clamps where
the payload's surface is tangent - its widest ring; `logs/p42/SEAT_CENSUS.md` §0
measures the pads' midpoint 1.4-4.7 mm off the payload's centre, i.e. an
equatorial grip, not a cap). An axial pull is therefore tangential at every
contact and

    F_crit = n * mu * N_c                    (tangential / friction mode)

so the **ratio is `n/2` and is mu-free**:

| form | n | F_crit at `mu_eff` 0.45 | at the measured pair 1.13-1.45 | ratio |
|---|---|---|---|---|
| (a) two-pad pinch | 2 | 4.41 N | 11.07-14.21 N | 1.00 |
| (b) 3-contact tripod | 3 | 6.62 N | 16.61-21.32 N | **1.50** |
| (c) 4-contact | 4 | 8.82 N | 22.15-28.42 N | **2.00** |
| (d) two-pad + distal lip | 2 + block | not a friction quantity | | **unbounded** (ideal) |

* **(a)-(c) are the friction count.** The bar is met by (b) **exactly at its
  letter** (1.50) and by (c) with a 0.5x margin - in this model, for **any** mu.
  This is the honest weakness of the test: `n/2` is arithmetic, so the analytic
  half cannot fail, and what the fixture can actually falsify is whether the
  arithmetic *survives contact* (the contacts stay loaded, the payload does not
  rotate out, no peel) - see `RESULTS.md` §2-§3.
* **(d) is a different mode**: the pull is carried by a contact *normal*
  anti-parallel to it, so the axial degree of freedom is blocked, not
  friction-limited. The ideal ratio is unbounded; in reality it is the lip's or
  the jaw's strength. This is the geometry case the survey's hypothesis actually
  names ("win by envelopment, not force"), and it is the one the tree has
  **already measured as negative in the pipeline** (`logs/r8/A_RESULTS.md` §3).
* The model ignores **peel** (a real pad peels from one edge and the contact
  migrates), **contact independence** (a 3-pad squeeze is statically
  indeterminate), and the **payload's own rotation** - which is why the fixture
  also runs a moment-loaded variant (`RESULTS.md` §6), where the model's
  prediction is weakest.

**The load the cell applies, for scale** (`analytic.txt` §3): the shipped
lift/place cap is `a = 1.089 m/s^2`, so the axial demand is `m(g+a)` =
**0.17 N** (strawberry) / **0.91 N** (pear) / **1.20 N** (orange). The
conservative analytic pinch capacity is 4.41 N, i.e. **3.7-26x the demand** - and
the cell still loses the payload. This is the paper's central caveat: *the static
axial capacity is not the binding term, so a ratio on it need not convert a
single `cnp`.*

---

## 3. The fixture (`fixture_probe.py`)

One fruit, `n` pad bodies on prismatic joints, one force ramp. No arm, no
scheduler, no attempt machinery, no camera, no rendering (app `headless`,
320x240).

**Geometry, from the tree's measurements, not invented**

| item | value | source |
|---|---|---|
| pad face (plate cell) | 61.000 x 84.902 mm | `logs/p66/COLLIDER_READ.md` |
| distal plane below the jaw centre | 80.5 mm | `tasks.FINGER_TIP_BELOW_JAW` |
| payload centre below the jaw centre | 70 mm (`FRUIT_FINGER_LEN` 60 + `PAD_LIFT` 10) | `tasks._pad_standoff` |
| lip below the payload's equator | **10.5 mm** (80.5 - 70) | the two rows above |
| tip cell | 16 x 30 mm, same distal plane, same lip | the matched control |
| per-contact normal force | **4.90 N** | `logs/p41/P3_RESULTS.md`: 9.75-9.9 N total over two faces |
| drive | position drive, k = 1e5 N/m (`finger_damp02`), **force-capped at 4.90 N** | `control.finger_drive_profile`, `logs/p41` |
| pad friction | `mu = 2.0`, restitution 0 | `FRUIT_FINGER_MU` default |
| fruit | the pool's own mesh, mass, per-class friction draw | `meshes.author_fruit` / `FruitSpawner` |

**Why a force-capped position drive.** The shipped finger drive is a position
drive at a 10 N/joint cap and the delivered pinch is at that cap (P40: "the
*command* is at its 10 N/joint cap on 40/40 contact rows"). A capped position
drive reproduces the two properties that matter: the contact force is **4.90 N
whatever the penetration**, and the pad **yields** if the payload pushes it out.
Because the drive is saturated for the whole measurement, neither k nor c enters
the measured break-away - the **cap** does, and the cap is the measured pinch.

**Cells** (`P104_FORM`, one app session per form because the pad set is authored
before `play()`):

| form | pads | note |
|---|---|---|
| `pinch_plate` | 2 x 61 mm at 0/180 deg | the shipped pinch, literally |
| `pinch_tip` | 2 x 16 mm at 0/180 deg | the matched control for the multi-contact cells |
| `tripod` | 3 x 16 mm at 30/150/270 deg | the hand topology (a 3-finger grasp) |
| `quad` | 4 x 16 mm at 45/135/225/315 deg | a 4-finger/thumb topology |
| `lip` | 2 x 16 mm + a static distal ledge | the geometry case (d) |
| `pinch_tip_moment` | `pinch_tip` with the pull 20 mm off-axis | the pipeline's actual load (a payload hanging off a 2-point contact line) |
| `tripod_moment` | `tripod`, same 20 mm offset | the same, 3 contacts |

**Procedure per cell.** Close the pads on a *pinned* payload over 150 ticks
(a free payload falls 0.7 m during the close), pin 230 ticks, release, settle 90
ticks, then ramp an external axial force on the payload at **5 N/s** (0.0417 N
per 1/120 s tick) to a 40 N cap. The pull is along the tool axis and **with
gravity** (the hand is above the payload), so the load on the grasp is
`F_applied + m g`. Break is the survey's criterion: the payload's displacement
reaches **2 mm**; the sustained break is the load when it is **lost** (30 mm).

**Units and controls.** 3 fruits (`pear` 60.6 mm / 83.9 g, `orange` 65.8 mm /
110.2 g, `strawberry` 37.2 mm / 15.5 g) x 3 repeats x 7 forms = **63 cells**,
2 m 51 s of wall. The fixture is deterministic where the seat is (see §4) and the
repeat spread is reported per cell.

---

## 4. Recorded deviations (all post-hoc, all disclosed)

**A1 - the interference, and the manipulation check that forced it.** The first
seat used a 3 mm commanded interference inside the profile's `axis_extent`. The
per-contact force read 4.9 N on the two-pad cells but **3.09 N on one of the
tripod's three pads** at the break, and the tripod then measured **11.32 N
against the pinch's 11.20 (1.01x)** - i.e. the third contact was present but
unloaded. The cause is the per-instance mesh deformation (`meshes.py`: a +/-6 %
length bias and +/-1 % lobing), which makes `axis_extent` a few percent
optimistic. The registered manipulation check is "every contact carries the same
normal force"; the fix is a deeper target (the drive is force-capped, so a deeper
target cannot raise N, only guarantee contact). **5 mm** was adopted after a
5 mm / 10 mm screen: at 10 mm the pear's seat slid 7.6 mm sideways (the squeeze
pushes a lobed payload off-centre), at 5 mm it slides 3.8 mm and every pad reads
4.85-4.94 N. **`RESULTS.md` §3 reports the manipulation check per cell**; the
0.003 arm is kept as this paragraph's number, not as a cell.
**Read it as a result**: *the third contact pays only when it is loaded* - at a
3 mm interference the same 3-pad form was worth **1.01x**, not 1.5x.

**A2 - the ledge was authored with the xform ops in the wrong order** and was
invisible for one run (USD composes ops left to right, so a scale authored
before the translate scales the translation too; fixed to translate-then-scale,
`author_pads`). The affected run is not in the record; the fix is a comment in
the code (`# Translate *then* scale`).

**A3 - the moment cells were added after the first axial battery**, as the
diagnostic for the one prediction the Coulomb model is weakest on (§6 of
`RESULTS.md`). They use the same pads, the same cap and the same seat.

**A4 - the lips.** The `lip` cells never break inside the 40 N ramp, so their
ratio is a **bound** (`>40 N`), not a measurement. The earlier 10 mm-interference
run had the strawberry escape at 29.6 N on the same geometry, so the bound is
real and the geometry is not infinitely strong.

**A5 - the pull is applied at the payload's centre of mass** (axial cells) via
one `RigidPrim.apply_forces` per tick; the moment cells apply it at a world point
20 mm off-axis through `apply_forces_and_torques_at_pos`. Both are external
forces on a rigid body - no arm, no controller, so no tracking error enters the
number.

**A6 - `FRUIT_SUBSTEPS` is asserted 1.** A per-tick applied force is per
*substep*, so a substep count > 1 would divide the ramp.
