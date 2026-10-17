# P11-A: the simulator's physics properties vs the real fruit cell — the "ejection" fidelity audit

Status: **offline, read-only audit** (no simulator run; the P10-D.1 policy battery was running on the
same machine throughout and was not touched). Branch `p-supply`. All writes under `logs/p11/`; no
`src/`, `scripts/`, `configs/`, `datasets/` or `Paper/` write; no commit by the lane (the
orchestrator committed the audit at 45170e5). Date 2026-10-18.

**The question.** The owner asks whether the simulator's physics properties are realistic, prompted
by a measured behaviour: the two-line regrasp cycle commands the gripper pads to a keep-gap
**narrower than the fruit** (the census sentence reads 1.7-17.5 mm narrower in 15 of 18 B1 cases;
the per-attempt pairs enumerated in the same paragraph reach -18.4 mm), under the full squeeze
force, and the **rigid** fruit is then "ejected" - it squirts out and falls to the floor (13/18 of
the B1 class end ≈1.3 m below the belt top in the current census text; an earlier revision of the
same census read 12/18 - the same class, +/-1 attempt).
The owner's intuition: real fruit deforms/absorbs (it may bruise or be damaged, but does not fly).

**The evidence base.** (1) The measured behaviour: `logs/p10e/NOGRASP_DIAGNOSIS.md` (the B1
probe/regrasp census over the P10-C/C.2/C.3 batteries) and `logs/p10e/WORKLOG_entry.md`; the raw
rows in `logs/p10c/*`, `logs/p10c2/*`, `logs/p10c3/*`. (2) The tree: `src/fruit_sorting/*.py` and
`assets/openarm_flat/openarm_flat_deinst.usda` (the shipped de-instanced robot). (3) The build's
schema defaults: `extscache/omni.usd.schema.physx-110.1.13+.../plugins/PhysxSchema/resources/
schema.usda` in the Isaac 6.0 install (`/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/
release`), and the installed deformable plugin `plugins/OmniUsdPhysicsDeformableSchema`. (4) The
repo's own measurements of the compliant-contact and soft-pad experiments (WORKLOG "P3-faces",
"d2_mechanism", `logs/w8/B_RESULTS.md`, `logs/r11/B_RESULTS.md`). (5) Real-world numbers: the
repo paper library (mostly VLA/diffusion policy - the only hardware paper with grip-force numbers
is #73, the soft-gripper paper) plus targeted web sources, each with a confidence mark.

**The measured behaviour this audits** (P10-E, verbatim numbers). 30 unique no-grasp attempts over
7 distinct two-line runs; 18 are the B1 probe/regrasp class (60 % of the class count, 66 % of its
mass). In 29/30 the close found a real sustained contact (3.5-4.9 N) and the fruit was gone by the
carry start. The first regrasp keep-gap vs the fruit's extent (the current census paragraph):
51.9 vs 68.3 = **-16.4 mm**; 61.8 vs 68.2 = -6.4; 64.7 vs 66.4 = -1.7; 53.4 vs 68.2 = -14.8;
16.0 vs 33.5 = -17.5; 32.7 vs 37.2 = -4.5; 49.7 vs 68.1 = -18.4; 41.8 vs 57.0 = -15.2; 53.8 vs
68.7 = -14.9 (and the exceptions 32.0 vs 29.6 = +2.4, 45.5 vs 36.6 = +8.9 x2) - i.e. **15/18 first
keep-gaps 1.7-17.5 mm narrower than the fruit, reaching -18.4 mm**. Outcome of the 18 B1 attempts:
**13 end ≈1.3 m below the belt top** (in-hand |v|max 4.78-5.05 m/s = free fall from 1.17 m), 3 end
216-384 mm below (short drop/roll-off), 2 are physics blowups. The 4 blowups over the 30 no-grasp
attempts show in-hand |v|max 19.8-12 022 m/s and clean_slip 30.9-100.4 m - outright solver
divergence. (The mission prompt cites 12/18 falls; that was an earlier revision of the same
census - quote the current text with its revision in the record.)

---

## 1. The parameter audit (provenance-first)

Every value below is the **shipped default** (env unset) unless stated. "Override" = the code path
that can change it at runtime.

### 1.1 The fruits

| # | property | shipped value | where set (file:line) | runtime override |
|---|---|---|---|---|
| F1 | body type | `UsdPhysics.RigidBodyAPI` on the fruit mesh prim | `fruits.py:657`, `740` | none |
| F2 | collider | the fruit **visual mesh** (a procedural surface-of-revolution, 28 segments, +/-6 % length bias, bumps, 5 lobes for apple) with `UsdPhysics.CollisionAPI` + `MeshCollisionAPI` approximation **`convexHull`** | `meshes.py:339-377` (`author_fruit`), `meshes.py:370-377` | `FRUIT_COLLISION_APPROX` (default `convexHull`) |
| F3 | mass | `density * (4/3)pi*(d/2)^3 * 0.82` authored via `UsdPhysics.MassAPI` | `fruits.py:655`, `716-717` | none (recomputed on `rescale`, same formula) |
| F4 | density | strawberry 700, lychee 850, kiwi 900, tomato **780**, apple 850, orange 900, peach 820, pear 880 kg/m^3 | `meshes.py:172-213` (`FRUIT_SHAPES`); used at `fruits.py:655` | none |
| F5 | diameters | strawberry 30-45, lychee 28-38, kiwi 50-68, tomato 50-68, apple 62-70, orange 60-70, peach 58-70, pear 58-70 mm (uniform draws) | `assets.py:400-417`; draw at `fruits.py:632-633` | `FRUIT_SIZE_FILTER` (small/large) |
| F6 | static/dynamic friction | uniform draw per shape: strawberry (0.55,0.85), lychee (0.55,0.85), kiwi (0.75,1.05), tomato (0.50,0.75), apple (0.45,0.70), orange (0.70,1.00), peach (0.55,0.85), pear (0.45,0.70) - static = dynamic = the same drawn number | `meshes.py:172-213`; `fruits.py:656, 663-664` | none |
| F7 | restitution | **uniform(0.02, 0.20)**, drawn per fruit | `fruits.py:665`, `746` | none |
| F8 | contact/rest offset | **not authored anywhere** | - (grep: no `contactOffset`/`restOffset` in `src/`) | `PhysxCollisionAPI` never applied; schema default `-inf` = "default is picked by the simulation based on the shape extent"; rest offset 0 for rigid bodies (`schema.usda:781,793`) |
| F9 | CCD | **off** (`CreateEnableCCDAttr().Set(False)`) | `fruits.py:670-671`; `fruits.py:40-41` | none |
| F10 | sleep | **`sleepThreshold = 0` (never sleep)** because `FRUIT_KINEMATIC_GRIPPER` defaults to `"1"` in this check | `fruits.py:682-686` | `FRUIT_NO_SLEEP=0/1` |
| F11 | damping | 0 (not authored) | `fruits.py:42-54` (`tune_contact_body`) | `FRUIT_LINEAR_DAMPING`, `FRUIT_ANGULAR_DAMPING` (default 0) |
| F12 | max depenetration velocity | **not authored** | `fruits.py:43` | `FRUIT_MAX_DEPEN_VELOCITY` (default 0 = skip). Schema default **3.0 m/s** (`schema.usda:596`); the PhysX SDK doc line says "Default: 5.0 * tolerancesLength". The code comment calls it "unlimited" - **flagged, unverified** (§4) |
| F13 | max velocity | not authored | - | none. Schema default `inf` (`physxRigidBody:maxLinearVelocity`, `schema.usda:549`) |
| F14 | compliant contact on the fruit material | **none** - the fruit material authors only static/dynamic friction + restitution; a rigid contact | `fruits.py:661-668` | none |
| F15 | deformable body / plasticity | **none anywhere in the repo** (grep `deformable` in `src/` = 0 hits) | - | none. (The build *can* author them: `OmniUsdPhysicsDeformableSchema` + `physxDeformableBody:*`/`physxVolumeDeformableSim:*` tokens are installed - see §5b) |

**Computed shipped masses** (mid-diameter, the formula of F3): strawberry 15.8 g, lychee 13.1 g,
kiwi 79.4 g, tomato 68.8 g, apple 104.9 g, orange 106.1 g, peach 92.3 g, pear 99.0 g. The
**0.82** factor is a fixed "shape" discount on the bounding sphere; there is no per-shape volume
model.

### 1.2 The gripper

The shipped hand is **the robot's own jaws**, not the purpose-made pads: `FRUIT_GRIPPER_KIND`
defaults to `"openarm"` (`scene.py:331`, `tasks.py:428-441`, `assets.py:70`) and builds
`OpenArmHand` (`kinematic_gripper.py:121-189`). The pad hand (`KinematicGripper`) is opt-in.

| # | property | shipped value | where set (file:line) | runtime override |
|---|---|---|---|---|
| G1 | finger drive (the driven joint) | `openarm_{left,right}_finger_joint1`: prismatic, axis Y, limits [0, 0.044] m, `drive:linear:physics:type = "force"`, **stiffness 1e6 N/m, damping 100 Ns/m, maxForce 10 N**, `maxJointVelocity = 1` | asset `openarm_flat_deinst.usda:3798-3820` (left), `4061-4084` (right) | `FRUIT_FINGER_STIFFNESS`/`FRUIT_FINGER_DAMPING` via `set_dof_gains` (`control.py:164-173`); default 0 = **no override**, the asset's k=1e6/c=100 stand |
| G2 | finger drive (the second joint) | `finger_joint2` has **no drive at all** - it is a **mimic** of joint1 (`PhysxMimicJointAPI:rotY`, gearing -1, `naturalFrequency 0`, `dampingRatio 0`) | asset `:3822-3844` (left), `:4085-4107` (right) | none |
| G3 | command path | `set_gripper(q)` -> `set_dof_position_targets` on both finger dofs; face separation `= 0.010 + 2*q` clipped to [0, 0.044] => **achievable face gap 10-98 mm** | `control.py:234-239`, `241-245`, `61-67`, `79` | none |
| G4 | finger contact material | bound on the finger *link* prims: static = dynamic = **mu 2.0** (`FRUIT_FINGER_MU`), restitution **0.0**, **compliant contact k = 30 000 N/m** (`FRUIT_FINGER_COMPLIANCE`), damping **c = 80 Ns/m** | `scene.py:358-394`; the defaults are set process-wide in `assets.py:62-63`; `_add_physics_material` `scene.py:115-176` | `FRUIT_FINGER_MU`, `FRUIT_FINGER_COMPLIANCE`, `FRUIT_FINGER_CONTACT_DAMPING`, `FRUIT_FINGER_FRICTION_COMBINE` (default empty) |
| G5 | friction combine mode | **not set** (schema default `"average"`, `schema.usda:1231`); the code comments claim PhysX defaults to *minimum* (`scene.py:159-163`, `kinematic_gripper.py:150-153`) - **flagged, unverified** (§4) | `scene.py:150-167` (applied), `:384` (print) | `FRUIT_FINGER_FRICTION_COMBINE` |
| G6 | finger collision geometry | the finger **visual meshes** (`.../visuals`, Mesh prims) get `CollisionAPI` + `PhysxConvexHullCollisionAPI`; the asset's own `collisions/` subtree is an instance proxy and cannot be used | `scene.py:423-467`; asset choice `assets.py:26-48, 66-74`; hard gate `scene.py:337-351` | `FRUIT_FINGER_COLLIDERS` (default 1 in openarm mode) |
| G7 | finger link mass | 0.036 kg each | asset `:5404-5413`, `:5506-5511` | none |
| G8 | finger pad option | `FRUIT_FINGER_PADS` default 0 (no extra pads); face shapes `flat` default | `scene.py:325-326, 395-401` | `FRUIT_FINGER_PADS`, `FRUIT_FINGER_FACE` |
| G9 | D2 soft-pad bodies (opt-in) | real pad body per finger on a prismatic spring-damper: **k = 5000 N/m, c = 25 Ns/m**, travel -5/+1 mm, 20 g, front face 0.25 mm proud, joint `maxForce 50 N` | `scene.py:896-956` | `FRUIT_FINGER_SOFT_PAD=1` + its sub-knobs |
| G10 | force servo (the dynamic line) | on for the dynamic OpenArm catch; law: close `FRUIT_DYNAMIC_FORCE_STEP = 0.4 mm` every `TICKS = 3` ticks while `F < max(MIN 2.0 N, DROP 0.8 * ref)`, `ref` = median of the first 48 samples capped at 4.0 N; open 3 mm (`BACKOFF`) above `MAX 12.0 N`; **travel bounded to -15 mm (`RANGE`) / +3 mm around the grip depth** | `tasks.py:1042-1100`, `_force_servo_step` `tasks.py:1786-1927` | `FRUIT_DYNAMIC_FORCE_*`; `FRUIT_FORCE_REENTRY` (default 0) gates the law on confident contact |
| G11 | close depth | `grip_gap = pinch_width * FRUIT_GRIPPER_SQUEEZE (0.98)`; dynamic: `deep = min_extent * FRUIT_DYNAMIC_CLOSE_DEEP (0.97)`; the live-extent clamp keeps `max(3 %, FRUIT_DYNAMIC_MIN_INTERFERENCE 2.5 mm)` of interference | `tasks.py:7350-7375`, `7395-7408`, `7832-7851` | the env knobs named |
| G12 | W1 two-line regrasp profile | `FRUIT_DYNAMIC_REGRASP_KEEP = 1`, probe 6 mm over 60 ticks, test step 0.01 (scoped to a two-line session) | `tasks.py:6654-6665` (`_dynamic_profile`) | env override wins |
| G13 | the regrasp re-seat | `keep_gap = squeeze_gap` (the **chased** gap, else `grip_gap`); 40 ticks of `follow_centre(fruit, quat, keep_gap)` while descending to the fruit's measured centre; then the ratchet closes the joint command by `FRUIT_DYNAMIC_REGRASP_STEP 0.0015` per cycle = **3 mm of face separation per cycle** (1.5 mm/finger) | `tasks.py:8683-8720`, `8792-8801` | `FRUIT_DYNAMIC_REGRASP_STEP`, `FRUIT_REGRASPS` (3) |
| G14 | tactile | contact-force readers on the finger links; `normal_force` = **sum of the magnitudes of the net contact forces**, `contact_count` = loaded links | `tactile.py:29-39, 56-140` | always on with the openarm hand |
| G15 | pad hand (opt-in) | two kinematic pad boxes 40 x 6 mm x 5 cm on the fingers, mu 2.0, **rigid contact unless `FRUIT_PAD_CONTACT_STIFFNESS` > 0**, faces commanded to `gap/2` around the fruit centre; `FRUIT_HAND_VMAX` 0 (teleport allowed) | `kinematic_gripper.py:31-72, 250-283, 379-430` | the named env knobs |

### 1.3 The belt and the cell

| # | property | shipped value | where set (file:line) | runtime override |
|---|---|---|---|---|
| B1 | belt surface | box slab 0.46 x 1.60 x 0.06 m, `CollisionAPI`, physics material **static = dynamic mu 0.9, restitution 0.0** | `conveyor.py:111-114`; `assets.py:217` | `FRUIT_*` belt knobs |
| B2 | belt body | **kinematic rigid body** (mass 50 kg) - required for the surface-velocity API; `FRUIT_BELT_KINEMATIC=0` restores the static slab | `conveyor.py:116-125` | `FRUIT_BELT_KINEMATIC` |
| B3 | belt drive | `PhysxSurfaceVelocityAPI` `(0, -0.12, 0)` m/s, ramped at 2.0 m/s^2 | `conveyor.py:127-129`, `assets.py:214-217` | `FRUIT_BELT_SPEED`, `FRUIT_BELT_ACCEL`, `FRUIT_BELT_RAMP` |
| B4 | cleats | off by default | `conveyor.py:96-100` | `FRUIT_CLEATS=1` |
| B5 | output belts / trays | output belts mu 0.9 with the same velocity API; tray 0.50, chute 0.25 | `conveyor.py:415-421`; `assets.py:368-369` | `FRUIT_OUTPUT_*` |
| B6 | time step | physics dt **1/120 s**, `FRUIT_SUBSTEPS` default **1** (opt-in 4 => 480 Hz) | `scene.py:1407-1430`; `common.py:13-25` | `FRUIT_SUBSTEPS` |
| B7 | scene / solver | no `PhysicsScene` gravity or solver authoring in the repo (Isaac defaults, g = 9.81); schema defaults of note: `maxDepenetrationVelocity 3.0`, `compliantContactStiffness 0.0` (rigid), friction/restitution combine `"average"`, contact/rest offset `-inf` | - ; `schema.usda:596, 1270, 754, 761, 781, 793` | - |

**A code-path note that matters for the squeeze force (G1/G2).** The pinch is not bounded by the
10 N drive: `finger_joint1` is force-limited at 10 N, but `finger_joint2` is a **rigid mimic
constraint with no drive and no force limit**, so the reaction side can transmit more than 10 N.
The logs carry the evidence: pad-pad clamp forces of 7.5-56 N at the carry onset after the fruit is
gone (`logs/p10e/NOGRASP_DIAGNOSIS.md` §1.3), and the R11-A.1 servo rows read `F_max` up to 176.8 N.
The "full squeeze force" is therefore **10 N from the driven finger plus an uncapped mimic reaction**.

---

## 2. The real-world reference

Confidence marks: **FULL** = the complete paper text read in this audit (or the repo's FULL read);
**abstract** = abstract / summary only; **snippet** = a search-result fragment; **est.** = an
order-of-magnitude estimate computed here from FULL-read material constants (stated).

### 2.1 Fruit mass, size, density

| fruit | real value | source | conf. |
|---|---|---|---|
| apple (Fuji, Japanese) | 81.29 mm diameter, **220 g** sample; model density **840 kg/m^3**; Poisson 0.35 | Jia et al. 2026, Eng. Agric. (SciELO) `eagri/v46/e20250087` | FULL |
| tomato | 52.84 mm mean diameter, **83.67 g**, volume 87.85 cm^3, **true density 0.96 g/cm^3** | Geasa & Hassan 2022, JSSAE 13(3) (semanticscholar mirror of `jssae.journals.ekb.eg/article_226784`) | FULL |
| tomato (cultivar range) | real density **0.83-0.97 g/cm^3** | journals.ekb.eg `article_214361` | abstract |
| orange (Thompson Navel) | fruit density **0.97-1.03 g/cm^3** | Int. Agrophysics / CABI summaries | abstract |
| peach (Tabrizi) | mass **137.37 g** (SD 25.45), mean diameter ~60 mm | idosi.org WASJ 12(1):119-122 (2011) | FULL |
| strawberry (context) | ~10-25 g for 30-45 mm fruit | standard produce data (not audited here) | est. |

Sim vs real: the sim's fixed 0.82 sphere-volume factor plus the densities of F4 put the shipped
fruit **~11 % (apple) to ~44 % (peach); tomato ~41 % at 53 mm below** the measured masses; see §4.

### 2.2 Flesh stiffness / elastic modulus (small deformation)

| fruit | real value | source | conf. |
|---|---|---|---|
| apple | compressive **elastic modulus 2.091 MPa** (the value used in a validated apple-impact simulation); storage modulus 2.91-3.75 MPa (Fuji, Red Delicious) | SciELO `eagri/v46/e20250087`; Lee et al. 2012, J. Biosyst. Eng. 37(1) | FULL / abstract |
| apple | yield limit **0.125 MPa** (stress at damage onset) | Zhang et al. 2022, Int. J. Food Prop. 25(1) | abstract |
| tomato (whole fruit) | triple-element Maxwell: **E0 0.222 +/- 0.017 MPa**, E1 0.068, E2 0.082 MPa, T1 0.355 s, T2 8.67 s; Caputo relaxation modulus 0.388 MPa | Ru et al. 2024, Foods 13(14):2166 (PMC11276429) | FULL |
| tomato (tissue/cells) | cell-wall elastic modulus **30-80 MPa** (tissue-scale; not the whole-fruit response) | RSC "Mechanical Properties of Tomato Fruit and Tissues" | abstract |
| tomato (firmness) | **0.2-3.3 N/mm^2** average firmness range; Geasa: 2.8 N/cm^2 = 0.028 N/mm^2 at the penetrometer (probe 0.6 cm dia) | ResearchGate snippets of the tomato mechanical-properties papers; Geasa FULL | snippet/FULL |
| peach | tangential elasticity modulus **1.53 MPa**; probe rupture force 10-15 N (8 mm probe) | idosi.org WASJ 12(1):119-122 | FULL |

**Derived whole-fruit contact stiffness** (Hertzian sphere-vs-flat, F = (4/3) E* sqrt(R) d^1.5,
E* = E/(1-nu^2); computed here - **est.**): tomato (E = 0.30 MPa, nu = 0.45, R = 26.5 mm):
**3.9 N/mm at 1 mm**, 5.5 N/mm at 2 mm, F(2 mm) = **7.3 N**. Apple (E = 2.09 MPa, nu = 0.35,
R = 33 mm): **27 N/mm at 1 mm**, F(1 mm) = 18 N, F(2 mm) = 52 N. The tomato number lands on the
independently measured bruise force (§2.3) - a consistency check on the estimate.

### 2.3 Bruise / damage thresholds (force, energy, pressure)

| fruit | real value | source | conf. |
|---|---|---|---|
| apple (Golden Delicious) | bruise detection limit at impact energy **0.05 J with a 25.8 N peak force** (25 mm-radius spherical metal impactor); levels 2/3 = 0.10 J/66.2 N and 0.19 J/101.5 N | Zarifneshat et al. 2010, Am. J. Agric. Biol. Sci. 5(2):114-121 | FULL |
| apple | critical impact velocity **0.5 m/s** for 170-180 g apples (drop height 13 mm) - the bruise threshold in a drop test | "Determining the coefficient of restitution of apples..." (ResearchGate) | snippet |
| apple | critical compression energy **~100 N*mm (0.1 J)** during elastic interaction | Liu et al. 2022, Foods 11(13):1851 | abstract |
| apple | free drop height must be < 3 cm to keep fruit-to-fruit bruising negligible | Fu et al. 2020, Agronomy 10(1):59 | abstract |
| tomato | **> 7 N causes internal and external bruising**; "turning" stage bruised at **7.2 +/- 1.99 N**, "pink" at 8.8 +/- 1.41 N (rupture/splits at the stem scar) | Smith et al. 2019, JOJ Hortic. Arboric. 2(3):555586 | FULL |
| tomato | ripe tomatoes dropped on cork at 26.7 cm show severity 3/5 internal bruising; > 35 cm on steel/cardboard severity 2 | same | FULL |
| peach | rupture resistance **10 N (MT, 8 mm probe) / 15 N (peeled)**; stiffness 11.35 N (peeled) / 15.31 N (unpeeled) | idosi.org WASJ 12(1):119-122 | FULL |

### 2.4 Friction (fruit skin vs engineering surfaces)

| pair | real value | source | conf. |
|---|---|---|---|
| apple vs rubber (conveyor rubber) | static **0.46-0.94**, dynamic **0.52-1.03** | Puchalski et al. 2003, CIGR J. FP 03 002 | FULL |
| apple vs paper/cardboard | static 0.28-0.42, dynamic 0.21-0.45 | same | FULL |
| apple vs plastic | static 0.21-0.31, dynamic 0.18-0.58 | same | FULL |
| apple vs masonite | static 0.26-0.48, dynamic 0.25-0.50 | same | FULL |
| tomato vs wood / plastic / rubber / carton / galvanized steel (static) | **0.40 / 0.27 / 0.33 / 0.26 / 0.29** | Geasa & Hassan 2022 | FULL |
| tomato simulation recommendation | "average coefficient of friction values higher than 0.22 are recommended" | ResearchGate summaries of the tomato property papers | snippet |

### 2.5 Restitution (coefficient of restitution, COR)

| pair | real value | source | conf. |
|---|---|---|---|
| apple vs apple | **COR 0.4** (calibration used in a validated bin-filling simulation); static friction 0.5 | SciELO `eagri/v46/e20250087` | FULL |
| apple vs PE bin | **COR 0.5** | same | FULL |
| apple (fresh market) | "the CoR should be over **0.84** to avoid bruise damage" (fruit-to-fruit sliding method) | Fu et al. 2022, Biosyst. Eng. 224:183 (abstract) | abstract |
| fruit generally | COR decreases with impact velocity; tomatoes measured as a function of drop height (green vs ripe) | Lichtensteiger et al. 1988, Trans. ASAE 31(2):595-602 (abstract page only) | abstract |
| kiwifruit (context) | COR measured vs drop height 400-650 mm, wall material (stainless/rubber) | "Coefficient of restitution of kiwifruit without external interference" (ResearchGate) | snippet |

### 2.6 Gripper pad compliance / grip force (the real end-effector side)

| item | real value | source | conf. |
|---|---|---|---|
| soft-gripper finger design force | **5 N per finger** (the paper's crank-torque sizing target); impulse test peak 23.5 N over 100 ms = 1.175 N*s; sliding test max normal force 1.5 N | repo paper #73: "A soft gripper with an adaptive grasp control system..." (Kim et al., `Paper/fulltext_ca/20261010-DynamicVLA__A soft gripper...txt`) | FULL (repo library) |
| soft-gripper pads | silicone/soft-finger pads conform around the object; the paper's finger models are qualitative (contact force vs object displacement curves) - no N/mm given | same | FULL |
| industrial gripper pads (context) | a 3.2 mm rubber tip with secant modulus 1.5 MPa at 1.5 mm deformation was used as an apple-firmness reference tip - order 1 MPa pad modulus | ASABE "A Bioyield Tester for Measuring Apple Fruit Firmness" | abstract |
| pad stiffness estimate | for a Shore-20-50A silicone pad 5-10 mm thick, k ~ E*A/t ~ **10-80 N/mm** for a 20 x 20 mm pad (**est.**, no single source) | computed here | est. |

---

## 3. The "ejection" mechanics (rigid-body contact terms)

### 3.1 What the controller commands (the chain, with numbers)

1. The close freezes the commanded face separation at the first sustained contact + span stall -
   force 3.5-4.9 N, span typically +6..+12 mm wider than the fruit's extent (a tip/edge contact;
   P10-E §2.1). `_closed_gap = squeeze_gap` = the frozen depth.
2. The 6 mm probe fails (the fruit does not rise >= 4 mm) -> the W1 regrasp profile runs.
3. **Before** the re-seat, the force servo has chased the force collapse: with the payload leaving
   the jaws the tactile reads 0 N, the law closes at 0.4 mm/3 ticks, and the command walks the full
   `RANGE = 15 mm` down. Every no-grasp attempt's servo row reads `F_min = 0.00 N` and `closed`
   15.0-26.0 mm (each regrasp re-anchors and re-arms another 15 mm).
4. The re-seat drives the pads back onto the fruit's **measured centre** at
   `keep_gap = squeeze_gap` = (grip depth - up to 15 mm) - i.e. **1.7-17.5 mm narrower than the
   fruit in 15/18 cases (up to -18.4 mm in the enumerated pairs)** (P10-E). The 40-tick loop tracks
   the fruit while holding that gap; the ratchet then
   closes another 3 mm of face separation per cycle.
5. The carry then runs with the fruit gone: the pads clamp on each other (`sep@onset ~ 10 mm` - the
   hard-stop gap of the calibration `0.010 + 2q`, q -> 0 - with a pad-pad force 7.5-56 N) or sit on
   air at the commanded gap.

### 3.2 The rigid-body contact analysis

* **The interference is not a force command; it is a position command.** `follow_centre(gap)` sets
  the finger drive's *target* to a face separation below the fruit's width. The drive is a stiff PD
  servo (k = 1e6 N/m) clipped at 10 N, so whenever the finger is more than ~10 um from its target
  it pushes at **the 10 N limit, continuously**. The mimic joint (G2) couples the second finger
  rigidly; the constraint is not force-limited (measured peaks 7.5-176 N are transient; the
  sustained pinch is bounded by the drive in the static reading).
* **The contact spring is far too stiff to absorb the interference.** The finger material carries
  `compliantContactStiffness = 30 000 N/m`; the fruit material carries none (rigid). At the 10 N
  drive limit the pad-face penetration is **10/30 000 = 0.33 mm** - so of the commanded
  1.7-17.5 mm of interference, **~0.3 mm can be elastic and the rest has nowhere to go but into
  motion of the fruit** (or into the solver's depenetration). This is the same statement the repo makes for the
  carry: "the material compliance (contact penetration, sub-mm at k=30 kN/m)" (WORKLOG d2_mechanism).
* **The contact geometry is a wedge whenever the pads are not exactly symmetric about the fruit's
  widest section.** With a commanded gap below the fruit's width, the pads cannot reach their target
  height without pressing on the fruit's flanks; the contact normal at each pad acquires a large
  component along the free axis (up/down along the faces, or across the belt if the hand is tilted
  by any of the pose residuals the close tolerates). A 10-20 N push on a **70-105 g** rigid body at
  a 30-45 deg normal angle is an acceleration of 50-200 m/s^2 - **>1 m/s in a few ticks**.
* **The 120 Hz step resolves this as an impulse, not a spring.** The repo's own note
  (`common.py:13-19`): at dt = 1/120 s the resolvable contact frequency for a ~0.1 kg payload is
  ~40 Hz; the shipped contact (30 kN/m, 0.1 kg) sits at f = (1/2 pi) sqrt(k/m) = **87 Hz**, i.e.
  above the band. `FRUIT_SUBSTEPS = 4` (480 Hz) is the opt-in escape hatch. The observable
  consequence: the **4/30 solver blowups** (|v|max up to 12 km/s, clean_slip up to 100 m) and the
  rest of the class leaving at the free-fall speed from the 1.17 m belt top.
* **Energy bookkeeping.** The work the drive can do while pushing the interference through is
  F * d = 10 N * 0.0164 m = **0.164 J**; a 100 g fruit given that energy leaves at 1.8 m/s. The
  real bruise thresholds are 0.05 J (apple) and ~6-8 mJ (tomato elastic to 7-9 N at ~2 mm) - the
  commanded interference at full force carries **3-27x the energy that damages real fruit**.
* **Mass and restitution.** Lighter fruit accelerate more for the same force (the sim's fruit are
  8-40 % light, §4). Restitution (0.02-0.2) plays no role in the launch itself - it only shapes the
  bounce after the fall; a real fruit at COR 0.4-0.5 would bounce *more*, not less.
* **Friction.** The sim's effective finger-fruit friction is at least the fruit's own 0.45-1.1 and
  probably the average with mu = 2.0 (schema default combine, G5) - comparable to the measured
  apple-rubber 0.52-1.03. Friction resists *sliding*; it cannot prevent a wedge ejection, because
  the ejection is driven by the normal force's free-axis component and the fruit is not
  kinematically constrained (no nest, no opposing stop).

### 3.3 What a deformable (viscoelastic) fruit does instead

* The interference is absorbed by **deformation**, not motion: a real tomato's contact stiffness is
  ~3.9 N/mm at 1 mm and it reaches its **7-9 N damage threshold at ~2 mm** of compression
  (§2.2/2.3). An apple is ~27 N/mm at 1 mm and tolerates ~26 N / 0.05 J before bruising.
* Under the same commanded sub-fruit gap, a real fruit + real force-controlled gripper does not
  launch: the drive stalls at its force limit against a *deforming* body, the contact patch
  **flattens** (the normals spread toward the squeeze axis instead of staying at a wedge angle), and
  the remaining commanded travel is simply never realized. The failure mode is **bruise / rupture /
  crush** (tomato splits at the stem scar at 7-9 N; peach ruptures at 10-15 N), not a ballistic
  escape.
* The viscoelastic character matters twice: the deformation itself (Hertzian force-displacement,
  F ~ d^1.5) and the **damping** (stress relaxation times T1 ~ 0.36 s, T2 ~ 8.7 s for tomato) -
  a real fruit eats the approach energy of a fast pad over those time constants. The sim has neither
  (rigid body, no fruit-side damping, restitution 0.02-0.2 only).

### 3.4 Which audited parameters make the artifact stronger / weaker

| parameter | direction | why |
|---|---|---|
| fruit rigidity (F1/F14/F15) | **stronger** | the whole interference must go into motion; no flattening of the contact patch |
| keep-gap command below the extent (G13) | **stronger** | sets the magnitude of the interference (1.7-17.5 mm, up to -18.4 mm) |
| force-servo chase, 15 mm range (G10) | **stronger** | creates the sub-fruit keep-gap in the first place |
| ratchet 3 mm/cycle (G13) | **stronger** | adds interference on every regrasp cycle |
| finger contact stiffness 30 kN/m (G4) | **stronger** | 0.33 mm of elastic give at the force limit; also above the resolvable band |
| drive force limit 10 N + mimic uncapped (G1/G2) | **stronger** | a continuous saturated push; the mimic can exceed the nominal force |
| fruit mass low by 8-40 % (F3/F4) | slightly stronger | same force => larger acceleration |
| restitution 0.02-0.2 (F7) | neutral (post-fall only) | does not drive the launch |
| friction 0.45-1.1 (F6) | neutral/slightly weaker | resists sliding but not a wedge escape |
| 1/120 s single substep (B6) | **stronger (variance)** | turns the contact into an impulse; enables the 4/30 solver divergences |
| depenetration cap unauthored (F12) | unresolved | 3 m/s (schema) or 5 m/s (SDK) caps the push-out speed; the code comment claims "unlimited" |

---

## 4. Per-parameter verdicts

Verdicts: **reasonable** = inside the measured real range; **off** = measurably outside it;
**artifact-prone** = inside a plausible range but structurally unable to represent the real
phenomenon; **unverified** = the shipped value cannot be established offline.

| parameter | current value + provenance | real-world range (source) | verdict | artifact relevance |
|---|---|---|---|---|
| fruit body type | rigid (`RigidBodyAPI`; `fruits.py:657`); no deformable, no fruit-side compliance | all fruit are viscoelastic solids (E 0.22-2.1 MPa; tomato relaxes over 0.36/8.7 s) | **artifact-prone (the #1 gap)** | **DRIVES** - the interference cannot be absorbed, so it becomes fruit motion |
| finger contact stiffness | 30 000 N/m (k), 80 Ns/m (c) (`assets.py:62-63`; `scene.py:363-364`) | tomato ~3 900 N/m at 1 mm; apple ~27 000 N/m at 1 mm; pad estimate 10 000-80 000 N/m | **off (8x a tomato) / artifact-prone** | **DRIVES** - 0.33 mm give at the 10 N limit; above the 120 Hz band |
| fruit mass model | density x sphere x 0.82 (`fruits.py:655`) | measured: apple 840 kg/m^3 (220 g @ 81 mm); tomato 0.96 g/cm^3 (83.7 g @ 53 mm); peach 137 g @ 60 mm | **off** - sim ~11 % (apple) to ~44 % (peach); tomato ~41 % light | PARTIAL - lighter fruit launch farther |
| fruit density (per class) | 700-900 kg/m^3 (`meshes.py:172-213`) | tomato 0.83-0.97; orange 0.97-1.03; apple 0.84 g/cm^3 | **off** (tomato 780 vs 960; orange 900 vs 970-1030) | PARTIAL (via mass) |
| fruit friction | 0.45-1.05 per class (`fruits.py:656`) | apple-rubber 0.52-1.03; apple-paper 0.21-0.45; tomato-steel 0.29 | **reasonable** | NONE/minor |
| finger friction + combine | mu 2.0, combine **not set** (`scene.py:358-394`); comments claim "minimum", schema default "average" | no fruit surface reaches 2.0; effective pair 0.45-1.55 depending on the rule | **unverified** (G5) | minor (does not drive the squirt) |
| restitution | 0.02-0.2 (`fruits.py:665`) | apple-apple 0.4, apple-bin 0.5 | **off (low)** | MINOR (post-fall bounce) |
| fruit collider | convex hull of the visual mesh, no CCD (`meshes.py:370-377`, `fruits.py:671`) | n/a (shape approximation) | reasonable for a rigid proxy | NONE (the convex hull is fine for a convex fruit) |
| contact/rest offsets | not authored (schema: simulation-chosen / 0) | n/a | **unverified** | MINOR |
| depenetration / max velocity | not authored (`fruits.py:43`); code comment says "unlimited"; schema default 3 m/s | n/a | **unverified** | PARTIAL - caps how fast the push-out can be |
| gripper drive | k 1e6, c 100, maxForce **10 N**, `maxJointVelocity 1`; mimic joint uncapped (asset `:3798-3820`, `:3822-3844`) | soft gripper design 5 N/finger (#73); the mimic makes the sim's pinch unbounded | **off (the mimic) / reasonable (10 N)** | **DRIVES** - a saturated, unbounded push |
| keep-gap command | `keep_gap = squeeze_gap` = grip depth - up to 15 mm (`tasks.py:8688`) | no real controller commands a gap inside the part; it stops on force | **artifact-prone (control side)** | **DRIVES (the trigger)** |
| force servo | 15 mm one-way travel, re-anchored per cycle (`tasks.py:1097`) | force control stops at the target force; no 15 mm blind travel | **artifact-prone** | **DRIVES (the trigger)** |
| belt | mu 0.9, restitution 0, kinematic slab, 0.12 m/s surface velocity (`conveyor.py:111-129`) | conveyor rubber 0.9-1.0; 0.1-0.3 m/s lines are normal | **reasonable** | NONE |
| time step | 1/120 s, substeps 1 (`common.py:20`; `scene.py:1407`) | n/a (sim choice) | **artifact-prone for the contact** | PARTIAL - impulse resolution + the blowups |
| tactile | sum of net contact-force magnitudes, 1 reading per finger link (`tactile.py:120-140`) | real grippers: per-pad normal force (F/T or capacitive) | reasonable as a proxy | NONE (but the `F_min = 0` chase is read from it) |

---

## 5. The fix options (sketch, for P11-C)

### (a) Control-side - no physics change

The squirt's **trigger is a command**: `keep_gap` below the fruit's extent, created by the chase and
re-issued by the re-seat. The candidate changes, all in `tasks.py`, all two-line-scopeable through
`_dynamic_profile` (`tasks.py:3979-3996`):

1. **A keep-gap floor at the live measured extent.** At `tasks.py:8688-8692`,
   `keep_gap = max(squeeze_gap, live_extent - margin)` where `live_extent = self.pinch_width(
   sample, quat_now)` (the same geometric read the close already uses, `tasks.py:9783-9800`) and
   `margin` ~ 0-0.3 mm (0 = no overlap at all; the contact's elastic give is only ~0.3 mm at the
   10 N limit and `pinch_width` is good to a few percent, so a hard no-overlap guarantee needs
   margin <= 0 - a standoff). The same floor on
   the ratchet at `tasks.py:8792-8801` (`fingers` must not go below
   `gripper_value_for_separation(live_extent - margin)`), and on `grip_gap`/`squeeze_gap` if a
   global floor is wanted. New env knob, default off, two-line-scoped, e.g.
   `FRUIT_DYNAMIC_REGRASP_FLOOR`.
2. **Stop the chase** with the existing `FRUIT_FORCE_REENTRY=1` (`tasks.py:1139-1157`,
   `1786-1927`): the servo holds the commanded gap when the contact estimate is gone, so
   `squeeze_gap` stays at the recorded depth and the re-seat keeps it. The P7-2a prior (single-arm
   acceptance: chase 5 -> 0, carried 5 -> 5, zero conversions) says this is *necessary but not
   sufficient* - the chase is a symptom of the loss, but it is the *actuator* of the sub-fruit
   keep-gap. A cheaper variant is to cut `FRUIT_DYNAMIC_FORCE_RANGE` (15 mm) to the fruit scale
   (~1-2 mm) so even a full chase cannot go sub-fruit.
3. **A force-based re-seat rule.** Enter the re-seat only when the tactile still reads a plausible
   hold (`F >= 1-2 N` and `contact_count >= 1`, the same signals the FARM gate consumes); if the
   fruit is already gone, skip the re-seat entirely (the pads clamping on each other is what the
   `sep@onset ~ 10 mm` rows show). The `FRUIT_FORCE_REENTRY_ENTER/EXIT` hysteresis is the existing
   implementation of exactly this signal.
4. **Bound the cycle** with `FRUIT_REGRASPS=1` (the P10-E Lever 2): a diagnostic that removes the
   repetition/ratchet; expected to move the B1 mass toward B2/C rather than to fix it.

**Could this remove the squirt without touching physics? Yes, for the re-seat interference, by
construction** (with margin <= ~0.3 mm; the floor removes the re-seat/ratchet interference, not
the close's own designed 2.5 mm clamp - `tasks.py:7830-7844`, the grip mechanism itself). With no
commanded interference there is no geometric overlap for the solver to resolve, no saturated push to
sustain, and no wedge force - the failure that remains is a *slip* of a marginal grip (the B2/C
classes), not a launch. The physics (rigid fruit, 30 kN/m contact) then only decides how a marginal
grip fails, not whether the fruit flies. **Two honest caveats.** (i) The P10-E falsifier must still
be run: if the first keep-gaps stay >= the extent and the class does not move, the re-seat is not
the ejector and the probe's own 6 mm lift owns it (the logs cannot separate these; §6). (ii) The
control fix does not make the grip itself realistic - the marginal tip contact and the
drive-saturated pinch remain, and a real tomato held at 4.5 N is fine while a real *regrasp* at
10 N+ is a bruise. The realism question is separable from the failure class.

**Cost.** Two-line-scoped knobs: the shipped single-arm acceptance stays byte-identical (the
P10-C.3/W7-A pattern); the two-line scenario needs its references re-recorded only if the *default*
is flipped (`configs/motion_reference_twoline.json` / `motion_reference_patch.json` + `scripts/
190_twoline_gate.sh` + the collector manifest field), plus a pre-registered battery at seed 11
(the hard seed) with seeds 5/23 as controls - the P10-E §3 protocol.

### (b) Physics-side

1. **Compliant contact on the fruit material (the cheapest real change).** The mechanism exists
   per-material: `physxMaterial:compliantContactStiffness/Damping` (`schema.usda:1270-1290`); today
   only the *finger* material carries k = 30 kN/m. Authoring a per-class fruit stiffness
   (tomato ~4 kN/m, apple ~25 kN/m - the Hertzian values of §2.2) would give the pair a compliant
   series response. **Measured anchor already in the tree**: the D2 soft pads (k = 5 kN/m) gave
   **0.2-1.0 mm** of compression at the 4.9 N grip and did *not* stop the A2 carry escape (7/10 vs
   the 8/10 baseline, `logs/d2_mechanism`) - so a fruit-side k of the right order is a *precondition*
   for realism, not a fix for the *regrasp* ejection, which needs (a) anyway (the 16 mm command is
   beyond any fruit's elastic range: it is a crush).
2. **A deformable-body proxy.** Two forms. (i) The **soft-pad bodies already in the tree**
   (`FRUIT_FINGER_SOFT_PAD=1`, k = 5 kN/m, travel -5/+1 mm; `scene.py:896-956`) - a real compliant
   body on a prismatic spring-damper, measured (7/10, pads compress 0.2-1.0 mm). (ii) **True
   deformable bodies**: this Isaac 6.0 build ships the `OmniUsdPhysicsDeformableSchema` plugin
   (`OmniPhysicsDeformableBodyAPI`, `OmniPhysicsVolumeDeformableSimAPI` /
   `OmniPhysicsSurfaceDeformableSimAPI`, `OmniPhysicsDeformableMaterialAPI`, tet/vertex
   attachments) and the PhysX plugin exposes `physxDeformableBody:*`
   and `physxScene:gpuMaxDeformableVolumeContacts`; the volume-sim properties live under
   `OmniPhysicsVolumeDeformableSimAPI` (`omniphysics:*`, e.g. `omniphysics:restTetVtxIndices`) -
   i.e. volume/tet deformables are authorable.
   Cost: tet-meshed fruit assets (the current fruit are surface meshes with convex-hull colliders),
   the deformable solver's own stability/timestep constraints, and a re-measure of every contact
   path.
3. **A damage / bruise model.** Not a solver feature - a *metric*: accumulate per-fruit contact
   impulse / peak normal force / contact energy over the grip and compare to the thresholds of §2.3
   (tomato 7-9 N, apple 26 N / 0.05 J, peach 10-15 N). PhysX `contactReportAPI`
   (`schema.usda` `PhysxContactReportAPI`, threshold-based) or the existing tactile path could feed
   it. **Constraint**: per AGENTS.md §2, per-tick work inside the control loop changes the run - so
   a damage meter must be default-off or report-only (the `FRUIT_CARRY_DIAG` pattern), and its
   output is a metric, not a contact response.
4. **The re-baseline cost of any physics change (per AGENTS.md §2).** A contact-physics change is a
   **new scenario**, and it invalidates the whole lineage: the scripted acceptance (`scripts/
   accept.sh`, 9/10 + `fingerprint: matches`), the motion references
   (`configs/motion_reference.json`, `_twoline.json`, `_patch.json` - re-recorded with
   `--write-fingerprint`), the two-line
   gates (`scripts/190_twoline_gate.sh`, `105`), the selfcheck legs, the W6-A patch battery and the
   dense W3/W4 records, `scripts/170_transport_probe.py` (AGENTS.md: any fruit change must be
   re-measured there) and the shared-station bimanual batch (`logs/biarm/`, `logs/g/`,
   `scripts/153_biarm_rates.sh`), **and the demonstration stores** (`datasets/demos_v11/v12/v12d_s02/v13p` - all
   collected on the rigid physics; their collector manifests pin the tree) **and the checkpoints
   trained on them** (`moe_v12/v13s/v13p`), i.e. the policy canary and the direct-interface
   measurements. The conservative reading: one physics change = a fresh collection + fine-tune +
   canary + every reference re-recorded. That is the reason option (a) is the first move: it is
   two-line-scoped, needs no physics change, and its re-baseline is one pre-registered battery plus
   (only on adoption) the two-line references.

---

## 6. Honest limits of this audit

1. **No per-tick pad-fruit geometry in the logs.** `FRUIT_ACQ_DIAG` was off in the P10-C batteries,
   so the B1 chain ("the re-seat at the chased keep-gap is the ejector") is medium-confidence in
   P10-E's own words; the named alternative (the probe's 6 mm lift shears the marginal grip and the
   clamp comes after) cannot be excluded from the logs alone. This audit adds the *physics* reading
   of why the ejection is possible at all; it does not re-attribute the class.
2. **Two schema-default questions are unresolved offline**: (i) the effective
   `maxDepenetrationVelocity` when the attribute is unauthored (schema default 3.0 m/s vs the SDK
   doc's 5.0 * tolerancesLength vs the code comment's "unlimited"); (ii) the friction combine rule
   the runtime applies (schema default "average"; the code comments claim "minimum"). Both are
   cheap to settle in P11-C with a schema query or a two-fruit probe - neither changes this
   document's conclusions.
3. **The mimic joint's force transmission is read from the asset schema** (a rigid coupling with
   `naturalFrequency 0`), not measured directly; the observable evidence is the 7.5-176 N pad-pad
   clamp readings.
4. **The real-world numbers are literature ranges for other cultivars, not for this cell's fruit.**
   Several are abstract/snippet-level (marked); the apple/tomato/peach modulus and bruise numbers
   are FULL reads. The Hertzian stiffness values are order-of-magnitude estimates computed here.
5. **No simulator run was made.** The audit is of the shipped tree + the existing logs; every
   "artifact" claim is a mechanism statement about the code path, not a new measurement.

## 7. The three-line answer to the owner

* **Most unrealistic parameters**: (1) the fruit is a **rigid body** - no deformability, no
  plasticity, no fruit-side compliance anywhere; (2) the finger contact stiffness **30 kN/m** (8x a
  tomato, 0.33 mm of give at the drive limit, above the 120 Hz resolvable band); (3) the fruit
  **mass/density model** (0.82 sphere factor + densities 780-900 => ~11-44 % light vs measured);
  (4) **restitution 0.02-0.2** vs the real 0.4-0.5; (5) the **un-authored depenetration/velocity
  caps + the uncapped mimic joint** (the pinch force is not bounded by the 10 N drive).
* **The artifact's key drivers**: the force-servo **chase** (15 mm) creating a sub-fruit keep-gap,
  the W1 **re-seat** re-issuing it onto the fruit (1.7-17.5 mm inside, up to -18.4 mm), and the **rigid fruit +
  saturated drives + 120 Hz impulse resolution** converting that commanded interference into
  fruit motion (0.164 J of drive work vs 0.05 J apple / ~6-8 mJ tomato damage energy), with 4/30
  attempts diverging outright.
* **Can the control-side fix remove the squirt without touching physics?** Yes - the trigger is the
  commanded interference, and flooring the keep-gap at the measured extent (+ stopping the chase +
  capping the ratchet) removes the interference, the saturated push, and the wedge. What remains is
  a *slip* of a marginal grip, not a 1.3 m fall. The physics still makes the sim's grip less
  forgiving than a real one (no bruise/absorb), but it stops being the thing that launches the
  fruit.

---

## Appendix A: provenance index (the exact sites)

* fruits: `src/fruit_sorting/fruits.py:25-54` (tune_contact_body), `631-702` (_create_fruit:
  mass 655, friction 656/663-664, restitution 665, CCD 670-671, sleep 682-686), `710-750` (rescale),
  `752-830` (respawn).
* fruit shapes/collider: `src/fruit_sorting/meshes.py:149-213` (FruitShape + FRUIT_SHAPES),
  `339-377` (author_fruit; collision 370-377).
* gripper: `src/fruit_sorting/kinematic_gripper.py:31-41` (pad geometry), `44-72` (_material:
  compliant 65-71), `121-189` (OpenArmHand), `192-283` (KinematicGripper), `379-430` (follow_centre
  for the pads); `src/fruit_sorting/control.py:61-79` (joint calibration), `164-173` (finger gains),
  `234-245` (set_gripper / value-for-separation); `src/fruit_sorting/scene.py:325-419` (hand
  selection, finger material 358-394, face shapes 395-401, soft pads 402-409), `423-467`
  (finger colliders), `896-956` (soft pads).
* asset: `assets/openarm_flat/openarm_flat_deinst.usda:3798-3820` (left finger joint1 drive),
  `3822-3844` (left finger joint2 mimic), `4061-4084` / `4085-4107` (right), `5404-5413` /
  `5506-5511` (finger link masses 0.036 kg).
* force servo / regrasp: `src/fruit_sorting/tasks.py:49` (PAD_LIFT), `1042-1100` (servo knobs),
  `1786-1927` (_force_servo_step), `4496-4515` (_pad_standoff), `6654-6665` (W1 profile),
  `7350-7375` (grip_gap), `7395-7408` (dynamic close), `7832-7851` (live-extent clamp),
  `8683-8720` (re-seat at keep_gap), `8759-8801` (ratchet).
* belt/cell: `src/fruit_sorting/conveyor.py:111-129` (slab + body + surface velocity), `415-421`
  (output belts); `src/fruit_sorting/assets.py:62-63` (compliance setdefaults), `214-217` (belt),
  `400-417` (fruit dimensions), `368-369` (tray/chute friction); `src/fruit_sorting/scene.py:1407-
  1430` (dt), `src/fruit_sorting/common.py:13-25` (substeps).
* schema defaults (Isaac 6.0 install): `extscache/omni.usd.schema.physx-110.1.13+110.1.2.lx64.r
  .cp312.u7f4/plugins/PhysxSchema/resources/schema.usda:596` (maxDepenetrationVelocity 3.0),
  `1231/1239` (combine modes "average"), `781/793` (contact/rest offset -inf), `1270-1290`
  (compliant contact); deformables: `plugins/OmniUsdPhysicsDeformableSchema/resources/
  generatedSchema.usda` (`OmniPhysicsDeformableBodyAPI` etc.).

## Appendix B: reproduction commands (read-only)

```bash
# the measured behaviour (P10-E)
sed -n '215,300p' logs/p10e/NOGRASP_DIAGNOSIS.md
grep -h "mm kept)" logs/p10c/*.log logs/p10c2/*.log | grep -oE "gap [0-9.]+ mm kept" | sort -u
# the shipped fruit physics
grep -n -E "mass|friction|Restitution|CCD|Sleep" src/fruit_sorting/fruits.py | sed -n '1,30p'
grep -n -A6 '"apple"' src/fruit_sorting/meshes.py
# the gripper drive + mimic
sed -n '3798,3844p' assets/openarm_flat/openarm_flat_deinst.usda
# the keep-gap command
sed -n '8683,8720p' src/fruit_sorting/tasks.py
# the schema defaults
sed -n '549p;596p;781p;793p;1231p;1239p;1270,1290p' \
  /home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release/extscache/omni.usd.schema.physx-110.1.13+110.1.2.lx64.r.cp312.u7f4/plugins/PhysxSchema/resources/schema.usda
```

## Appendix C: external sources (URLs)

* Apple impact/bruise force levels 25.8/66.2/101.5 N at 0.05/0.10/0.19 J:
  `https://thescipub.com/pdf/ajabssp.2010.114.121.pdf` (Zarifneshat et al. 2010).
* Apple bruise threshold vs mass/drop height (hyperbolic threshold, 80-190 g, 20-60 mm):
  `https://journal.pan.olsztyn.pl/pdf-98033-30764?filename=30764.pdf` (Stropek & Golacki 2007).
* Apple simulation calibration (density 840, E 2.091 MPa, COR 0.4/0.5, friction 0.5/0.364):
  `https://www.scielo.br/j/eagri/a/9kwTCDfvkz3WPfX6VxGTFky/?format=pdf&lang=en` (Jia et al. 2026).
* Apple friction vs rubber/paper/plastic/masonite:
  `https://cigrjournal.org/index.php/Ejounral/article/download/429/423` (Puchalski et al. 2003).
* Tomato whole-fruit viscoelastic parameters (E0 0.222 MPa etc.):
  `https://pmc.ncbi.nlm.nih.gov/articles/PMC11276429/` (Ru et al. 2024).
* Tomato bruise force 7.2-8.8 N:
  `https://juniperpublishers.com/jojha/JOJHA.MS.ID.555586.php` (Smith et al. 2019).
* Tomato physical/mechanical properties incl. friction 0.40/0.27/0.33/0.26/0.29, mass 83.67 g,
  density 0.96 g/cm^3: `https://jssae.journals.ekb.eg/article_226784.html` (Geasa & Hassan 2022;
  PDF mirror `https://pdfs.semanticscholar.org/4c25/f15fe4b8409b2b4c1713d3dfcf402136116d.pdf`).
* Peach mass/stiffness/rupture 10-15 N: `http://www.idosi.org/wasj/wasj12(1)11/19.pdf`.
* Apple COR 0.84 to avoid bruising (fruit-to-fruit): `https://www.sciencedirect.com/science/
  article/abs/pii/S1537511022002392` (Fu et al. 2022).
* Tomato impact parameters (COR vs drop height; abstract only):
  `https://elibrary.asabe.org/abstract.asp?aid=30753&t=2` (Lichtensteiger et al. 1988).
* Repo paper #73 (soft gripper, 5 N/finger): `Paper/fulltext_ca/20261010-DynamicVLA__A soft
  gripper with an adaptive grasp control system allowing stable and.txt`.
