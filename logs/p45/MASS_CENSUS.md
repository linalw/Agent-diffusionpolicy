# P45 phase 1 — MASS_CENSUS: does a lighter fruit let the faster cells run safely?

Measured **offline** 2026-10-27 (no simulator, no `src/` edit, no commit).
Tree: HEAD **`1bae811`** (P44 amend), clean working tree.
`fruits.py` **`6f65e423`**, `meshes.py` **`41efc522`**, `assets.py` **`61baf52b`**,
`tasks.py` **`b6de439c`**, `grasp.py` **`6417e1d2`**, `control.py` **`9384ff4f`**,
`scene.py` **`27e3d64a`**; `configs/motion_reference.json` `8a399626`,
`..._twoline.json` `2246f83c`.

Reproduce every number below with

```bash
python3 logs/p45/mass_census.py --write      # ~0.1 s, reads no stage, imports no pxr
```

`logs/p45/MASS_CENSUS_out.txt` is the run of record (265 lines); sections
(A) masses, (B) the real-mass table, (C) inertia, (D) the slip ratio,
(E) the fling, (E2) the contact/walk term, (F) the implied density, (G) the
measured anchors, (H) the knob register.

---

## 0. The answer, before the arithmetic

**A mass cut cannot buy safety here, and it is a two-sided bet that loses more
than it wins.**

1. **The slip ratio moves — the sketch's premise is backwards.** `N` is
   grip-set (a position-drive preload), so the supply `mu*N` is a **constant in
   m** and `r = m|a+g|/(mu*N)` is **proportional to m**: 0.25x mass = 0.25x
   ratio (the arithmetic is §3) — but the *measured* ratio is the one quantity
   `logs/p9` shows is **non-discriminative** (escapes median 0.36, held legs
   0.37), so the improvement lands on a number that does not separate the
   classes.
2. **Both 1/m channels point the other way.** The ejection is an impulse
   (`v = J/m`), so a lighter fruit is flung **farther** (§4); and at a fixed
   friction force `mu*N` the roll-out angular acceleration is
   `2.5*mu*N/(m R)`, so the walk **spins up faster** as the mass falls (§6).
3. **0.25x is not produce.** At a fixed size it means a **205-225 kg/m³**
   design density — cork (§5) — i.e. a 6.5 cm peach with a **1.93 mm**
   hollow wall. The physical version of the same experiment is a *smaller*
   fruit (4.1 cm), which changes the pinch span and therefore the geometry the
   class lives in.

So the hypothesis is testable and is expected to fail, but it must be tested
because the owner asked and because the answer ("which term do the faster cells
touch") is worth having. The design is §8 / `PREREG_DRAFT.md`.

**One correction to the phase brief, and it is the load-bearing one.** The
sketch says the ratio is "mass-independent *if* the normal force is set by the
grip". That is inverted: mass-independence is the **weight-set** case
(`N = m g / mu`, the textbook model, and the model `motion.accel_budget` uses —
`motion.py:16-27`). With a **grip-set** `N` the ratio is `∝ m`. The conclusion
the sketch draws from it ("a lighter fruit does not buy slip margin, but it does
lower the absolute demand") is therefore half wrong: it **does** buy ratio, and
the margin it buys is the non-discriminative one.

---

## 1. The shipped mass table (part A)

### 1.1 How the mass is derived

One path, one formula, two densities:

```
mass = fruit_density(shape) * (4/3) pi (d/2)^3 * 0.82        fruits.py:977 (create)
                                                              fruits.py:1039 (rescale)
```

* `d` is the per-instance diameter drawn `uniform(lo, hi)` from
  `SceneConfig.fruit_dimensions` (`assets.py:439-456`), re-authored as a mesh at
  the final size — **never** a scaled prim (`meshes.py:1-8`).
* the `0.82` is a fixed "sphere-shape discount" on the bounding sphere; there is
  **no per-shape volume model** (P11 audit F3, `logs/p11/A_PHYSICS_AUDIT.md`).
* `fruit_density(shape)` (`meshes.py:399-410`) returns `shape.density` — the
  shipped per-class value — or `shape.density_real` when
  `physics_real_mass()` is on (`meshes.py:384-395`). Both are read **once at
  import** (`meshes.py:355-358`), so the choice cannot change mid-run.
* the value is authored with `UsdPhysics.MassAPI ... CreateMassAttr().Set(mass)`
  and **nothing else** (`fruits.py:980-981`, `:1063`).

### 1.2 The actual kg, per class and per size

Densities and friction ranges: `meshes.py:261-310`. Sizes: `assets.py:447-455`.
`2x m@mid` is the class's share of the 16-fruit pool (2 of each class).

| class | d lo-hi [cm] | ρ [kg/m³] | m@lo [g] | **m@mid [g]** | m@hi [g] | 2x m@mid [g] | μ range |
| --- | --- | --- | --- | --- | --- | --- | --- |
| strawberry | 3.0-4.5 | 700 | 8.1 | **15.8** | 27.4 | 31.7 | 0.55-0.85 |
| lychee | 2.8-3.8 | 850 | 8.0 | **13.1** | 20.0 | 26.2 | 0.55-0.85 |
| kiwi | 5.0-6.8 | 900 | 48.3 | **79.4** | 121.5 | 158.7 | 0.75-1.05 |
| tomato | 5.0-6.8 | 780 | 41.9 | **68.8** | 105.3 | 137.6 | 0.50-0.75 |
| apple | 6.2-7.0 | 850 | 87.0 | **104.9** | 125.2 | 209.8 | 0.45-0.70 |
| orange | 6.0-7.0 | 900 | 83.5 | **106.1** | 132.5 | 212.2 | 0.70-1.00 |
| peach | 5.8-7.0 | 820 | 68.7 | **92.3** | 120.8 | 184.6 | 0.55-0.85 |
| pear | 5.8-7.0 | 880 | 73.7 | **99.0** | 129.6 | 198.1 | 0.45-0.70 |

**The pool's mass range is 8.0-132.5 g, not "~20-200 g"** (the phase brief's
number, taken from the P40 note). Both ends are wrong: the lightest possible
draw is a 2.8 cm lychee at **8.0 g**, the heaviest a 7.0 cm orange at
**132.5 g**. The P40 arithmetic's `0.106 kg` is right — it is the orange at its
mid diameter (`logs/p40/GRIP_CENSUS.md` §4.1).

**The class split is 2 of each of 8 classes** (16 fruit; every shipped log
prints `classes=strawberry:2,lychee:2,kiwi:2,tomato:2,apple:2,orange:2,peach:2,pear:2`
on its `[supply]` line). The mass ordering is *not* the alphabetical one; the
light half (strawberry, lychee) is 8-27 g and the heavy half 69-133 g, i.e. a
**1:16 mass ratio inside one pool** with the grade mix (A:B:C 0.5/0.3/0.2)
overlaid on it.

### 1.3 The real-mass path (`FRUIT_PHYSICS_REAL_MASS=1`)

Per-class `density_real` (`meshes.py:261-310`; sources in
`logs/p11/A_PHYSICS_AUDIT.md` §2.1): apple 840 (measured), tomato 960
(measured), orange 1000, peach 1000, pear 950, kiwi 1050, lychee 1000,
strawberry 950.

| class | ρ ship | ρ real | m@mid ship | m@mid real | Δ |
| --- | --- | --- | --- | --- | --- |
| strawberry | 700 | 950 | 15.8 | 21.5 | **+35.7 %** |
| lychee | 850 | 1000 | 13.1 | 15.4 | +17.6 % |
| kiwi | 900 | 1050 | 79.4 | 92.6 | +16.7 % |
| tomato | 780 | 960 | 68.8 | 84.7 | +23.1 % |
| apple | 850 | 840 | 104.9 | 103.7 | −1.2 % |
| orange | 900 | 1000 | 106.1 | 117.9 | +11.1 % |
| peach | 820 | 1000 | 92.3 | 112.6 | +22.0 % |
| pear | 880 | 950 | 99.0 | 106.9 | +8.0 % |

Real-mass pool range **9.4-147.3 g**. Note the sign: the real path makes the
pool **heavier**, not lighter, and it moves the *light* classes most
(strawberry +36 %). It is therefore **not** a mass-reduction lever and must be
held constant across any mass experiment.

### 1.4 The inertia the physics uses

**No fruit authors a `physics:diagonalInertia`.** Verified by grep over the whole
tree: the only `physics:diagonalInertia` prims are the OpenArm links
(`assets/openarm_flat/openarm_flat_deinst.usda:4166` et al.). The fruit authors
`mass` only (`fruits.py:980-981`, `:1063`), so **PhysX derives the tensor from
the collider's volume at the authored mass** — a uniform-density solid hull. The
collision approximation is `FRUIT_COLLISION_APPROX` (default `convexHull`,
`meshes.py:626-634`), i.e. the hull of the procedural surface of revolution,
which for a near-spherical fruit is the sphere to a few percent. For a sphere:

```
I_xx = I_yy = I_zz = (2/5) m R^2
```

| class | d mid [cm] | m [g] | R [mm] | **I = 2/5 m R² [kg·m²]** | I/m [m²] |
| --- | --- | --- | --- | --- | --- |
| strawberry | 3.8 | 15.8 | 18.8 | 2.23e-06 | 1.41e-04 |
| lychee | 3.3 | 13.1 | 16.5 | 1.43e-06 | 1.09e-04 |
| kiwi | 5.9 | 79.4 | 29.5 | 2.76e-05 | 3.48e-04 |
| tomato | 5.9 | 68.8 | 29.5 | 2.39e-05 | 3.48e-04 |
| apple | 6.6 | 104.9 | 33.0 | **4.57e-05** | 4.36e-04 |
| orange | 6.5 | 106.1 | 32.5 | 4.48e-05 | 4.23e-04 |
| peach | 6.4 | 92.3 | 32.0 | 3.78e-05 | 4.10e-04 |
| pear | 6.4 | 99.0 | 32.0 | 4.06e-05 | 4.10e-04 |

**Consequence for the design (and it is good news for once):** because `I` is
*derived* from the mass, a `mass *= s` knob scales the inertia by exactly `s`
with **no second attribute to keep in sync**. "mass + inertia applied
consistently" is one line, not two — and it cannot be got wrong.

### 1.5 Every knob / site that changes mass or density

| knob | default | site | what it does |
| --- | --- | --- | --- |
| `FRUIT_PHYSICS_REAL` | unset | `meshes.py:355, 362` | master: `=1` turns on all three P12-A components |
| `FRUIT_PHYSICS_REAL_MASS` | unset (follows the master) | `meshes.py:356, 384, 399-410` | switches `fruit_density` to `density_real`; read **once at import** |
| `FruitShape.density` | 700-900 kg/m³ | `meshes.py:261-310` | the shipped per-class density |
| `FruitShape.density_real` | 840-1050 kg/m³ | `meshes.py:261-310` | the P12-A per-class real density |
| *(the mass site)* | — | `fruits.py:977` (create), `fruits.py:1039` (rescale) | `ρ · 4/3πr³ · 0.82` → `CreateMassAttr().Set(mass)` |
| *(the inertia)* | — | `fruits.py:980-981`, `:1063` | **not authored** — PhysX derives it from the collider volume at that mass |
| `FRUIT_FORCE_FACTOR` | `100` | `tasks.py:11003`, `grasp.py:223` | **mass-proportional close budget** `clip(m·g·100, 25, 60) N` |
| *(same channel, load-up)* | `60` | `tasks.py:11029` | `clip(m·g·60, 20, 40) N` |
| `SceneConfig.fruit_dimensions` / `FRUIT_SIZE_FILTER` | 8 classes, 2.8-7.0 cm | `assets.py:439-456` | mass ∝ d³ — a size change is a mass change |

**There is no scale knob.** `grep 'FRUIT_[A-Z_]*MASS' src/` finds only the two
P12-A switches plus `FRUIT_FINGER_SOFT_PAD_MASS` (`scene.py:1575` — the *opt-in
padded hand's* pad mass, not a fruit). `FRUIT_MASS_SCALE` is
`PREREG_DRAFT.md`'s design, not shipped code.

Note the last two rows of the table are the **only mass terms in a control
path**, and they are on the **indexed / policy** close (`GraspPrimitive`) — not
on the shipped dynamic line (§3.1). A mass experiment on the scripted dynamic
line is therefore clean, but a *policy* arm of the same experiment would have
its close force moved by the knob. That is a registered confound.

---

## 2. The friction the grip sets (part B.1, the supply term)

`mu_eff = FRUIT_MU_SAFETY × gripper.mu = 0.6 × 2.0 = 1.2` is the **trajectory
budget** (`tasks.py:3479-3481`, `motion.py:125-140`) and is *not* the physical
coefficient; the physical pair friction is `min(pad 2.0, fruit draw)` =
**the fruit's own draw** (PhysX takes the minimum, `scene.py:151-168`), i.e.
**0.45-1.05** across the pool with **0.45 the worst** (apple, pear).

The **normal force** is the P41 finger-drive preload: k = 1e5 N/m, c = 2000 N·s/m
(**c/k = 0.02** is the mechanism), Fsat 10 N/joint, delivering **9.75-9.9 N**
per pinch (`control.py:63-64`, `:86-103`, `:234-236`; `logs/p41/P2_RESULTS.md`).
The pre-P41 asset pair (k = 1e6, c = 100) delivered **4.42 N** and is what every
P40/P9 margin number is quoted against.

---

## 3. The slip ratio at 1x / 0.5x / 0.25x (part B.1)

### 3.1 Is `N` really grip-set? Yes — four checks

1. The dynamic grip's depth is a **function of geometry**: `pinch_width * 0.98`
   (`tasks.py:9768-9771`), where `pinch_width` is the mesh's extent along the
   closing axis (`axis_extent`, `meshes.py:430`, read at `tasks.py:12529-12546`).
   No mass in it.
2. The force servo's reference is the **measured tactile median**, capped at
   `FRUIT_DYNAMIC_FORCE_REF_MAX = 4.0 N` (`tasks.py:2705-2710`) — a measurement,
   not `m·g`.
3. `grep 'sample.mass' src/fruit_sorting/tasks.py` returns **two** hits, both the
   indexed close budget (`:11003`, `:11029`) — not the dynamic line.
4. The closure's commanded interference is what builds the force, and the same
   interference is commanded for a 13 g lychee and a 106 g orange (P41: the
   delivered pinch is 9.75-9.9 N across the pool).

The weight does enter, but as an **asymmetry, not as capacity**. The release
traces put the pad-centre axis `|dz|/|axis| = 0.60-0.96` (p50 **0.84**, n = 11
holding traces, `logs/p44/p2/amend_F_{C,S2}.log`), so the payload's weight has an
along-axis share of 0.6-1.0 `m g` = **0.62-1.03 N on the heaviest fruit, 6-10 %
of the 9.85 N grip**. In a position-controlled pinch that shifts force from one
pad to the other (`N1 - N2`), leaving `N1 + N2` = the drive's preload. It cannot
unload a pad by itself at these masses, which is consistent with `logs/p9`'s
finding that the single-sided onsets are a **seating** property (its two
ratio-1 legs both carry at ~2.2 N, i.e. a degraded contact, not a saturated
actuator).

### 3.2 The arithmetic

Worst class = **apple** (104.9 g at mid, `mu_lo` **0.45**). `r = m|a+g|/(μ N)`;
`1/r` is the margin.

**At the measured worst single-tick carry transient `|a| = 5.83 m/s²`**
(`logs/p40/GRIP_CENSUS.md` §4.1, the largest any carry leg reports), N = 9.85 N:

| scale | m [g] | demand `m(a+g)` [N] | **r** @ N 9.85 | margin 1/r | r @ N 4.42 (P40) | margin |
| --- | --- | --- | --- | --- | --- | --- |
| **1.00** | 104.9 | 1.641 | **0.370** | **2.70x** | 0.825 | 1.21x |
| **0.50** | 52.5 | 0.820 | **0.185** | **5.40x** | 0.413 | 2.42x |
| **0.25** | 26.2 | 0.410 | **0.093** | **10.80x** | 0.206 | 4.85x |

**At the commanded caps** (lift `a_max` 1.0; place 1.089): r = 0.256 / 0.128 /
0.064 and 0.258 / 0.129 / 0.064 — same 2x/4x scaling, lower intercept.

**Does a lighter fruit change it? Yes — exactly proportionally.** Three
conventions, all linear in m:

| convention | r(1x) | r(0.5x) | r(0.25x) |
| --- | --- | --- | --- |
| P40 scalar sum `m(a+g)` | 0.370 | 0.185 | 0.093 |
| vector `m|a-g|` (horizontal transient, 11.41 m/s²) | 0.270 | 0.135 | 0.068 |
| tangential only, measured pad axis (g-share 0.54) | 0.263 | 0.132 | 0.066 |

and against the pre-P41 4.42 N pinch the same 1x case is **0.825** — which is
the record's "1.20x margin" and the reason P41's profile change was worth
shipping.

### 3.3 Why that improvement is probably worth nothing

`logs/p9/FRICTION_AUDIT.md` computes this ratio from the measured per-tick
acceleration and tactile force over 55 attempts:

* escape legs: **0.10-0.78** of the available friction on **29/31** legs
  (median **0.36**);
* held legs: median **0.37**;
* at the lowest plausible μ, **0/31** escape legs and **0/33** held legs exceed
  1 during sustained contact.

So the class **does not separate on `r`**, and a 0.25x mass drives a
non-discriminative number from 0.37 to 0.09. That is the honest state of the
mass hypothesis on the slip term: **the margin it buys was never the binding
constraint.**

---

## 4. The fling `v = J/m` (part B.2)

### 4.1 The anchor

`logs/473_probe_final.log` **trial 16**: a **2.8 cm lychee**, released by the
fast **symmetric** relax, leaves at **peak |v| = 1.335 m/s**. On the same pool,
offsets and close/carry/lower (`logs/474_probe_asym.log`, trial 16) the **shipped
asymmetric** relax reads **0.695 m/s**, and that run's maximum **0.748 m/s is the
`<= 0.75 m/s` convention**.

The fruit: 2.8 cm at ρ 850 →
`m = 850 · (4/3)π(0.014)³ · 0.82 = 8.01 g`. The impulse that produced it:

```
J = m v = 8.01e-3 × 1.335 = 10.70 mN·s
```

### 4.2 The scaling

| scale | m [g] | **v at the same J [m/s]** | × the 0.75 convention |
| --- | --- | --- | --- |
| 1.00 | 8.01 | **1.33** | 1.8x |
| 0.50 | 4.01 | **2.67** | 3.6x |
| 0.25 | 2.00 | **5.34** | 7.1x |

The same `J = 10.7 mN·s` is **0.102 m/s** on a 6.6 cm apple (104.9 g). The
ejection speed is a pure `1/m` statement *about the same contact state* — which
is exactly why the **light fruit is the one that flies**, and why the pool's
lightest class (lychee, 8-20 g) owns the corpus's worst ejection.

**Bounds on the scaling**, so the PREREG's falsifier is not over-claimed:
`v ∝ 1/m` holds when the impulse is set by the pad's motion (true here — the
pads are kinematic and position-driven, so `∫(kδ + cδ̇)dt` is set by the ramp,
not the payload). If instead the pad's stored elastic energy were the whole
story, `v ∝ 1/√m` — **1.41x at 0.5x, 2.0x at 0.25x**. If the depenetration
velocity cap (`FRUIT_MAX_DEPEN_VELOCITY`, schema default 3.0 m/s,
`logs/p11/A_PHYSICS_AUDIT.md` F12) were binding, `v` would be mass-independent.
**In no case does halving the mass reduce the fling.**

### 4.3 What the line reads today (the metric, and a trap)

`FRUIT_RELEASE_DEBUG=1` prints one `release trace:` row per attempt with
`peak |v|` over the whole release block (`tasks.py:12206-12232`). On the P44 **C**
arm (`logs/p44/p2/amend_F_C.log`, 10 attempts) the ten rows split three ways:

* **6 of 10 — the placed ones — read 0.771-0.932 m/s** (`grasped=True
  placed=True`), i.e. the *line* already sits **at/above** the 0.75 convention
  (which is a *probe* number, not a line number);
* **2 read ~0.12 m/s**: the payload never moved off the belt (`fruit` at
  z = 1.198, `events=0`) — an acquisition miss, not a release;
* **2 read 4.782 / 4.810 m/s**, and the trace shows `z` falling 0.38 → 0.013 m
  with `place trace ... on_belt=False`: that is **free fall from the place
  height** of a payload already lost upstream, not an ejection.

So the fling endpoint must be **arm-vs-control, restricted to payloads still in
the hand at the release** — otherwise the metric measures gravity on a fruit that
was already lost, and a mass cell that *converts* losses would read as an
improvement.

---

## 5. What 0.25x means physically (part B.3)

Held-size scaling is not physical produce. Two equivalent readings of the same
number: the **design density** ρ (what `fruit_density` returns) and the
**solid-equivalent** `m/V_sphere` (what a physicist would call the density; the
0.82 is only a shape fudge).

| fruit | d [cm] | m ship [g] | ρ ship | ρ @0.5x | **ρ @0.25x** | solid-equiv @0.25x |
| --- | --- | --- | --- | --- | --- | --- |
| **peach** | 6.5 | 96.7 | 820 | 410 | **205** | **168** |
| **kiwi** | 5.6 | 67.9 | 900 | 450 | **225** | **184** |
| apple | 6.6 | 104.9 | 850 | 425 | 212 | 174 |
| orange | 6.5 | 106.1 | 900 | 450 | 225 | 184 |

References [kg/m³]: water 1000, **real peach ≈ 1000** (the P11 audit's own
137 g at 60 mm implies **1215**), **real kiwi ≈ 1050**, cork ≈ 240, balsa ≈ 160,
pine ≈ 500.

* **0.5x → 410-450 kg/m³**: softwood; it floats; not fruit.
* **0.25x → 205-225 kg/m³**: cork; it floats high; definitely not fruit.

The one way to make it physical is a **hollow shell of real-density flesh**:

| | 0.5x | 0.25x |
| --- | --- | --- |
| peach 6.5 cm | 48.3 g → wall **4.15 mm** | 24.2 g → wall **1.93 mm** |
| kiwi 5.6 cm | 33.9 g → wall **3.98 mm** | 17.0 g → wall **1.84 mm** |

— a 2 mm rind of 1000 kg/m³ material. That is a *bladder*, not a peach.

**And the physical version of the same experiment is a smaller fruit**: at the
real density, 0.25x the mass is a **4.1 cm peach** / **3.5 cm kiwi**. Those are
real sizes — but they change `pinch_width`, the pad standoff (`PAD_LIFT`) and the
reach, i.e. **the geometry the failure class lives in**. So:

> `FRUIT_MASS_SCALE` at a fixed size is a **mechanism probe**, not a candidate
> scenario. It isolates the mass term by holding everything else fixed — and by
> construction it cannot be shipped as a default, because the default's job is to
> represent a real fruit.

That framing is the PREREG's most important line: the experiment's value is the
**answer** (does the mass term move the class?), not a new default.

---

## 6. The contact / rolling term: does mass enter the walk at all? (part B.4)

**No — not through the geometry.** Every site that defines the walk is length
algebra:

| site | what it is | mass? |
| --- | --- | --- |
| `pinch_width()` = `axis_extent(shape, d, local_axis)` (`tasks.py:12529-12546`, `meshes.py:430`) | the fruit's extent along the closing axis, from the shape profile | no |
| close depth `pinch_width * 0.98` (`tasks.py:9768-9771`) | the commanded overlap | no |
| the pad's local-width shrink during the carry | the fruit's projected width between two advancing rigid faces | no |
| release relax `pinch_width + PAD_THICK + margin` (`tasks.py:12151-12172`) | geometry + a 6 mm margin | no |
| `clean_slip` (`FRUIT_CARRY_DIAG=1`) | the payload's displacement in the leg's own frame | a readout |

So the "geometric walk" is a **kinematic condition**, and mass enters it only
through the two `1/m` channels of §4:

* the friction **force** is `mu*N` (grip-set), so the roll-out angular
  acceleration `α = τ/I = mu*N·R / ((2/5) m R²) = 2.5·mu·N/(m R)` — on the 6.6 cm
  apple that is **3.2e3 rad/s²** at 1x and **2x/4x that** at 0.5x/0.25x. The walk
  (if it is the rotational mode `logs/p9` §5.2 names) gets **faster**;
* a depenetration kick's speed is `J/m` (§4).

Meanwhile the *translational* force margin `r` (§3) improves. **The two channels
point opposite ways, and the one that improves is the one the record shows is
non-discriminative.**

**A consequence the PREREG can use as an exact null:** because every leg is
**tick-clocked by its profile** (`logs/p44/CAP_CENSUS.md` rule 1 — the model
reproduces each leg to ±1.4 % and the profiles are pure kinematics), a mass
change **cannot move the timing**. The `[cycle]` block times and every leg's tick
count must be identical across mass cells. If they are not, the mass is leaking
into a control path the census did not find — which would itself be the finding.

---

## 7. The measured anchors (part C)

| readout | value | source |
| --- | --- | --- |
| pool mass range, shipped | **8.0-132.5 g** | §1.2, `mass_census.py` |
| pool mass range, `REAL_MASS=1` | 9.4-147.3 g | §1.3 |
| pool composition | 16 fruit, **2 of each of 8 classes** | every `[supply]` line |
| grip, delivered pinch | **9.75-9.9 N** (P41) / 4.42 N (pre-P41) | `logs/p41/P2_RESULTS.md` |
| carry force on held legs | 4.1-4.5 N; 9.31/9.74 N under P41 + park | `logs/p9` §3.4, `logs/p43` P3 |
| worst carry transient | **5.83 m/s²** single tick | `logs/p40/GRIP_CENSUS.md` §4.1 |
| slip ratio measured | escapes **0.10-0.78** (med 0.36); held med 0.37 | `logs/p9` §1 |
| release peak, probe shipped | **0.748 m/s**, 20 trials | `logs/474_probe_asym.log` |
| release peak, probe symmetric | **1.335 m/s** (2.8 cm lychee) | `logs/473_probe_final.log` t16 |
| release peak, line, in hand | **0.771-0.932 m/s**, 6 of 10 (= the placed) | `logs/p44/p2/amend_F_C.log` |
| release peak, line, never moved | 0.120-0.121 m/s, 2 of 10 (acquisition) | same |
| release peak, line, already lost | 4.78/4.81 m/s (free fall) | same |
| `clean_slip`, clean legs | **0.02-1.43 mm**, median **0.04** (n = 33) | `logs/w8/B_RESULTS.md` |
| `clean_slip`, escape legs | **17.9-957 mm**, median **278** (n = 31) | same |
| walk length on escapes | **104-276 mm** by the lift's 99 % sample | `logs/p42/SEAT_CENSUS.md` |
| live `clean_slip_max`, P44 C | 0.1 mm clean / 978-1402 mm lost | `logs/p44/P2_RESULTS.md` §9.2 |

The `clean_slip` separation is the sharpest instrument in the whole chain: clean
legs are **sub-millimetre** and escapes are **hundreds of millimetres**, with no
overlap. That is what the mass cell's walk endpoint should read.

---

## 8. The design (what `PREREG_DRAFT.md` registers)

Summary only — the registration is the other file.

* **The knob**: default-off `FRUIT_MASS_SCALE=<x>` (1.0 = shipped), a resolver in
  `meshes.py` beside `fruit_density`, applied at **both** mass sites
  (`fruits.py:977` create, `fruits.py:1039` rescale) and **nowhere else**. Size,
  mesh, `pinch_width`, `sample.diameter` and the collider are untouched — that is
  the experiment. Unset = skip the multiply entirely (byte-identity by
  construction, not by `×1.0`).
* **Cells**: {C, M50, M25} × {speed off, `FRUIT_SPEED_ALL=1`} = 6 arms.
* **Batteries**: the acceptance seed 5 + seed 6, and the species-locked pear
  (the P44 grid), same-tree control, interleaved, one claim per battery.
* **Endpoints**: `placed` (per battery, ≥ C−1); the **fling** = the release
  payload peak speed on payloads still in hand at the release, arm-vs-control
  and against the 0.75 convention; the **walk** = `clean_slip` arm-vs-control
  plus the `force_min == 0` leg count; the **cycle** = `s/attempt` **and** the
  exact leg-tick null (§6).
* **Falsifiers**: a lighter fruit does not improve the class; it worsens the
  fling; it changes nothing (the mass is not the term — or the knob did not
  apply).

---

## 9. What this document does not claim

* **No rate.** Nothing here is a success fraction; §7's counts are the corpora
  they came from.
* **No claim that the mass cell will help.** §0/§3/§6 predict it will not, on
  the class; the experiment exists to make that a measurement instead of an
  argument.
* **No claim about the measured walk's mechanism.** `logs/p9` §6.1 is explicit
  that the cone test is *translational* and cannot rule the rotational mode in
  or out; §6's `α ∝ 1/m` is an order-of-magnitude statement about that mode, not
  a measurement of it.
* **No inertia measurement.** §1.4 is PhysX's documented derivation
  (mass authored, tensor derived from the collider volume); it was **not**
  read back from a live articulation. A readback (one `get_mass`/`get_inertia`
  probe) would be needed to make it a measurement — named as a phase-2 nicety,
  not a gate.
* **No claim that a size change is equivalent.** §5 says the opposite: the
  physical way to a lighter fruit changes the geometry, so the fixed-size cell
  is a probe of the mass term only.
