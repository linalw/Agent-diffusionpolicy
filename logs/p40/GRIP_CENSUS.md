# P40 phase 1 — GRIP_CENSUS: the grip force chain, from the drive to the slip margin

Measured **offline** 2026-10-25/26 (no simulator, no `src/` change, no commit).
Tree: HEAD `1790b87` + the phase-1 working files (`logs/p40/` only).

Reproduce every number below with:

```bash
python3 logs/p40/grip_census.py > logs/p40/grip_census_out.txt   # ~50 s, reads 6 400+ logs
```

The script prints the raw table this file quotes (`logs/p40/grip_census_out.txt` is the
run of record). Its three corpora, and what each one can and cannot say:

| corpus | rows | what it measures |
| --- | --- | --- |
| per-attempt `force=` / `N=` | **12 619** | `result.max_tactile_force` per attempt (the number in `[run] … N=4.43`), with its outcome |
| `force servo:` | **9 253** | one row per grip: carry-phase `F[min,max]`, the servo's `ref`, its trips, `gap`/`sep` |
| `[acq]` (`FRUIT_ACQ_DIAG=1`) | **198** (175 with a frozen close) | the **measured world-pose jaw span** at the close plus the frozen *command* — the only paired achieved/commanded reading in the record |
| `[carry]` (`FRUIT_CARRY_DIAG=1`) | **2 749** (1 789 `grasp_lift`) | `force@onset`, `contacts@onset`, `sep@onset - gap_start`, `clean_slip_max` |

---

## 1. The finger drive: what actuates the pads

The shipped hand is the OpenArm's **own jaws** (`FRUIT_GRIPPER_KIND=openarm`,
`assets.py:70-74`), presented through `OpenArmHand` (`kinematic_gripper.py:121-189`).
There is no separate finger actuator: the pads the fruit touches are the robot's own
finger plates, and the only actuator is the finger prismatic joint.

| # | item | shipped value | site |
| --- | --- | --- | --- |
| 1 | driven joint | `openarm_{left,right}_finger_joint1`, prismatic, axis Y, limits **[0, 0.044] m** | `assets/openarm_flat/openarm_flat_deinst.usda:3798-3820` (left), `:4061-4084` (right) |
| 2 | drive type | `drive:linear:physics:type = "force"`, i.e. a PD **force** drive | usda `:3806` |
| 3 | drive stiffness | **1 000 000 N/m** | usda `:3804` |
| 4 | drive damping | **100 Ns/m** | usda `:3802` |
| 5 | **max force** | **10 N** | usda `:3803` (`drive:linear:physics:maxForce = 10`) |
| 6 | joint velocity cap | `physxJoint:maxJointVelocity = 1` (m/s) | usda `:3819` |
| 7 | second finger joint | `finger_joint2` has **no drive at all** — it is a `PhysxMimicJointAPI:rotY` mimic of joint1, `gearing −1`, `offset 0`, `naturalFrequency 0`, `dampingRatio 0`, limits [−0.0088, 0.0528] | usda `:3822-3843` |
| 8 | gain override | `FRUIT_FINGER_STIFFNESS` default **0** → `set_dof_gains` is **never called**; the asset's k=1e6/c=100 stand | `control.py:169-173` |
| 9 | command path | `OpenArmHand.follow_centre(gap)` → `arm.set_gripper(gripper_value_for_separation(gap))` → `q = (gap − 0.010)/2`, clipped to [0, 0.044] → `set_dof_position_targets` on **both** finger dofs | `kinematic_gripper.py:169-173`, `control.py:241-245`, `:234-239`, constants `:61-67`, `:79` |
| 10 | achievable face gap | `0.010 + 2q` → **10-98 mm** (`0.098` at full open) | `control.py:61-67` |
| 11 | finger collider | the finger **visual** meshes get `CollisionAPI` + convex hull; the asset's own `collisions/` subtree is an instance proxy and is unused | `scene.py:467-585` |
| 12 | finger material | static = dynamic = **mu 2.0** (`FRUIT_FINGER_MU`), restitution 0, **compliant contact k = 30 000 N/m, c = 80 Ns/m** | `scene.py:359-395` → `_add_physics_material` `:116-170` |
| 13 | where those two defaults come from | `assets.py` sets them **process-wide** at import: `FRUIT_FINGER_COMPLIANCE=30000`, `FRUIT_FINGER_CONTACT_DAMPING=80` | `assets.py:62-63` |
| 14 | contact soft-pad bodies | opt-in only (`FRUIT_FINGER_SOFT_PAD=1`): k=5000 N/m, c=25 Ns/m, 50 N joint cap | `scene.py:448-453`, `:1228-1246` |

**Correction to the phase-1 brief.** The brief's context block says
"`FRUIT_FINGER_COMPLIANCE` 0 (rigid)". That is the *scene.py* default
(`scene.py:364`), but `assets.py:62-63` overrides it at import for every entry
script, so **the shipped build runs the compliant contact: k = 30 kN/m, c = 80
Ns/m**. `logs/p11/A_PHYSICS_AUDIT.md:86` already records the shipped values
correctly; the brief's "rigid" is the knob default, not the shipped state. This
matters because the compliance is what sets the force-versus-interference slope
(section 2).

### 1.1 What the logs' three "separation" numbers actually are, and one inconsistency

Three different quantities are printed as if they were "the jaw gap":

| printed as | what it is | site |
| --- | --- | --- |
| `[task] kinematic grip closed to X cm` | **the commanded** face gap at the end of the close (`grip_gap`), not a measurement | `tasks.py:9966-9969` |
| `force servo: … gap=Xmm sep=Ymm` | `gap` = the servo's current command; `sep` = `0.010 + 2·mean(q_joint1, q_joint2)`, a **joint-model reconstruction** | `tasks.py:9587-9591`, report `:2400-2465` |
| `[acq] … span=90.0->Xmm` | **the measured world-pose link separation** `arm.jaw_separation()` — the only real span in the record | `tasks.py:9861-9862` |

The inconsistency: `gripper_value_for_separation` maps a requested gap to **one** joint
value and writes it to **both** finger dofs (`control.py:241-245`, `:234-239`), while the
asset's mimic is `gearing = −1, offset = 0` (usda `:3838-3842`), i.e. `q2 = −q1`. Under
that relation `sep = 0.010 + 2·mean(q1, q2)` is a **constant 10 mm**, and it is not: it
reads **71-81 mm** across the batteries (`logs/p40/grip_census_out.txt`). In one
measured attempt (`logs/p8/55_accept_control_diag.log`, attempt 1) the close's frozen
command is **72.4 mm**, the command it ends at is **66.5 mm** (the drift check's second
close re-ramps; the servo itself reports `closed=0.00 mm, trips=0`), and `sep` reads
**81.0 mm** — 14.5 mm wider than the command either way.

Two consequences:

* **R6-B's "interference = measured sep − commanded gap, median 11.9 mm" is a
  joint-model quantity**, not the face-to-fruit interference (`logs/r6/B_RESULTS.md`
  §2). The physical achieved-vs-commanded figure is the `[acq]` one: **median 6.8 mm**
  (§2.4). The two are close in magnitude, which is why the error was invisible, but
  they are different instruments and must not be substituted for each other;
* **the acceptance batteries never print the achieved span at all** — no `[acq]` row
  exists in any acceptance or two-line log in the tree
  (`grep -rl '\[acq\]' logs --include='*accept*.log'` and `'*twoline*.log'` are both
  empty; the 198 rows that do exist are all on the *direct/policy* interface, `logs/p18b`,
  `logs/r7`, `logs/w7`, `logs/w8`). So the current tree's own scripted records cannot
  answer "how far short did the pads stop"; that is the measurement to add, and it needs
  no code change — `FRUIT_ACQ_DIAG=1` on one acceptance run.

`FINGER_FACE_OFFSET = 0.0` (`control.py:79`) and the P11-B probe's blocking span
(`extent + 11.2 mm`, §2.5) cannot both be right; the probe is the measurement.

**"The drive is force limited by the asset (10 N per finger)"** — this docstring claim
(`kinematic_gripper.py:133-134`) is correct for joint1 only. joint2 has no drive and
no force limit; its load path is the mimic constraint, which is why the two-finger
*sensor sum* can exceed 20 N (measured maxima 21.25, 110, 1 450 N in transient rows —
`logs/p40/grip_census_out.txt`, "carry (all logs)").

---

## 2. Where the reported `N = 4.4` comes from

### 2.1 The code path (not a drive effort — a contact sensor)

1. **A position command, not a force command.** The close builds a two-phase ramp —
   24 ticks to `wide = max(pinch_width·1.02, d·1.02)`, then 60 ticks to
   `deep = min_extent · FRUIT_DYNAMIC_CLOSE_DEEP (0.97)` (`tasks.py:9092-9124`) —
   then clamps it every tick to `live_extent − interference`,
   `interference = max(3 % of the live extent, FRUIT_DYNAMIC_MIN_INTERFERENCE 2.5 mm)`
   (`tasks.py:9534-9553`).
2. **The command freezes on the first sustained contact.** `force ≥
   FRUIT_DYNAMIC_CONTACT_FORCE (0.5 N)` **and** the joint span stalled for
   `FRUIT_DYNAMIC_CONTACT_TICKS (3)` ticks → `freeze_cmd = cmd` and the depth stops
   growing (`tasks.py:9562-9649`; knobs `:9340-9344`).
3. **The frozen gap becomes the jaw command** through the chain of section 1 #9, and a
   rate-bounded integral **force servo** then rides on it (`tasks.py:2256-2380`,
   knobs `:1459-1518`): close 0.4 mm per 3 ticks while `F < max(2.0 N, 0.8·ref)`,
   open 0.4 mm per 3 ticks while `F > 12 N`, travel bounded to −15 mm/+3 mm around
   the frozen gap. `ref` = median of the grip's **first 48 samples capped at 4.0 N**
   (`FRUIT_DYNAMIC_FORCE_REF_MAX`, `:1507-1509`).
4. **The number in the log is a contact-sensor sum.** `tactile.read()` sums
   `ContactSensorReading.value` over the two finger-link sensors
   (`tactile.py:104-146`); the close stores it in `result.max_tactile_force`
   (`tasks.py:10046`, `:10300`) and `scripts/20_pick_place.py:350` prints it as
   `N=`. It is **not** a drive effort and **not** a solver impulse.

So `N = 4.4 N` is *the contact force the close happened to stop at*, held by a frozen
position command. Two independent measurements say so:

* the force servo **never tripped on 5 196 of 9 253 grips (56 %)**, and its reference
  sits at the 4.00 N cap on ≥ 75 % of them — the servo is a *floor* guard, not a force
  regulator, so it cannot raise or lower the hold force (`logs/p40/grip_census_out.txt`);
* `FRUIT_CARRY_RELIEF` released the command by 12-23 mm (down to 0.5 mm of allowed
  interference) and the force was **unchanged, 4.15-4.47 N**
  (`logs/r6/B_RESULTS.md` §2) — the command past contact does not set the force.

### 2.2 The measured force population

| reading | value |
| --- | --- |
| per-attempt `N=`, all 12 619 attempts | min 0.00 / p25 3.08 / **median 4.41** / p75 4.52 / max 612.8 N |
| at or below 5 N | **84 %** of attempts; `> 10 N` 12 %; exactly 0 N (no contact) **20 %** |
| force at the close's freeze (acceptance C, n=10) | **4.21 N** median (p25 4.12, p75 4.47), 17-31 ticks after the close started |
| carry-phase `F_min` (9 253 grips) | median **3.44 N**; `F_max` median **5.03 N** |

### 2.3 **The force does not discriminate success from failure** (the key reading)

Pooled over every log in the tree (`logs/p40/grip_census_out.txt`, "all logs: grip
force by outcome"):

| outcome | n | median grip force | p25 | p75 |
| --- | --- | --- | --- | --- |
| placed | 8 407 | **4.43 N** | 4.04 | 4.51 |
| carried-not-placed | 1 921 | **4.36 N** | 3.95 | 4.51 |
| no grasp (no contact) | 2 291 | 3.71 N | 0.00 | 4.55 |

The cnp class carries **98 % of the placed class's force, with an identical p75**. On
the acceptance itself it is 4.46 (placed, n=6) vs 4.45 (cnp, n=3). The grip is not
force-starved: it fails **while loaded**.

### 2.4 How far the pads get from their own command — and the one knob that moves it

The `[acq]` rows print both the frozen command (`freeze=Dmm@Nt`) and the **measured
world-pose link separation** (`span=90.0->Xmm`, `tasks.py:9838-9869`). Their difference:

| corpus | achieved span − frozen command (mm) | close `Fmax` (N) |
| --- | --- | --- |
| WS-4.2 N=5, **arm A** (shipped), n=64 | p25 5.50 / **median 6.80** / p75 8.52 | median **5.71** |
| WS-4.2 N=5, **arm B** (`FRUIT_CLOSE_LOAD_RATE=0.04`, the R11-B C1), n=71 | p25 1.50 / **median 1.60** / p75 2.10 | median **10.06** |
| R7-A edge-band probes, n=40 | p25 5.97 / median 7.00 / p75 7.68 | median 5.99 |

The close rows of the acceptance batteries give the *joint-model* version of the same
shortfall (`sep − frozen command`): 5.5-9.5 mm (median 9.25 on
`logs/p39/p3/accept_C.log`, 9.0 on the pear battery, 5.8 on the two-line, 9.5 on the
bed) — in the same band as the measured `[acq]` figure, from a different instrument.
**The shipped close stops ~6-9 mm short of its own commanded gap; the slow close (C1)
lands within 1.6 mm and more than doubles the close force.** That is a measured normal-force actuator, and it is the *only* one in the
record (R11-B measured it: carried class 48 → 27, p = 0.0026 on the direct interface,
and negative on all three scripted measurements —
`logs/p18b/B_RESULTS.md` §4, `AGENTS.md`'s R11-B paragraph).

### 2.5 The controlled probe: the force is insensitive to the commanded depth

`scripts/210_squeeze_probe.py` (P11-B, `logs/p11b/B_EJECTION_PROBE.md`) closes the
shipped jaws on a stationary 51.0 mm tomato and sweeps the commanded gap:

| commanded gap (mm) | 66.0 | 56.0 | 51.0 | 49.0 | 46.0 | 41.0 | 36.0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| achieved span (mm) | 66.0 | **62.4** | **62.4** | **62.4** | **62.4** | **62.4** | **62.4** |
| finger force (N), `contacts=2` | 0.00 | **4.56** | **4.49** | **4.49** | **4.49** | **4.48** | **4.49** |

(`logs/p11b/10_sweep_tomato.log`, group `air`; the no-fruit baseline `gap_cmd=12.0`
reaches `span_end=12.0` **exactly**, so the drive tracks its command with no load.)

Two consequences, both load-bearing for the lever set:

1. **Over 20 mm of extra commanded interference the achieved state is bit-identical**
   (0.082 m/s peak, 13.1 mm displacement, 4.49 N, every repeat). The pads stop at a
   **blocking span of `extent + 11.2 mm`** — i.e. the pad faces sit ≈ 5.6 mm inboard of
   each link origin. `control.py:79` sets `FINGER_FACE_OFFSET = 0.0` ("the pad surfaces
   are essentially at the link origins", `:72-78`); the probe says the offset is
   **≈ 11.2 mm in link-span terms**. That constant is what makes every "commanded
   interference" number in the record read ~11 mm optimistic.
2. **The force saturates at ~4.5 N, not at the 10 N drive cap.** A position drive
   stalled **6.4-26.4 mm** past its target (command 56 down to 36 mm against an achieved
   62.4 mm) with k = 1e6 N/m would be at its 10 N cap; it reads 4.5 N. Either the
   sensor under-reports by ~2.2x or the joint's effective stiffness is ~0.8 kN/m, not
   1e6. **This is the census's largest unknown** (section 7) and it is a two-line
   measurement to settle.

---

## 3. The friction model: coefficient, combine mode, and where the cone enters

| # | item | shipped value | site |
| --- | --- | --- | --- |
| 1 | finger mu | **2.0**, static = dynamic, `FRUIT_FINGER_MU` | `scene.py:359-384` |
| 2 | **combine mode** | **unset** (`FRUIT_FINGER_FRICTION_COMBINE` empty → the material carries no `frictionCombineMode`) | `scene.py:151-168` |
| 3 | what "unset" means | the PhysxSchema default. `logs/p11/A_PHYSICS_AUDIT.md:87` reads that default as **`"average"`** (schema `:1231`); the code comments in `scene.py:159-163` and `kinematic_gripper.py:150-153` claim PhysX takes the **minimum**. **The two disagree and neither is verified in-run** | audit §4, flagged "unverified" |
| 4 | fruit mu | per-class draw, static = dynamic: apple/pear **(0.45, 0.70)**, tomato (0.50, 0.75), peach (0.55, 0.85), lychee (0.55, 0.85), strawberry (0.55, 0.85), orange (0.70, 1.00), kiwi (0.75, 1.05) | `meshes.py:261-310`; drawn and authored at `fruits.py:977-978`, `:129-159` |
| 5 | fruit contact compliance | shipped **rigid** (no `PhysxMaterialAPI` on the fruit unless `FRUIT_PHYSICS_REAL_COMPLIANCE=1`) | `fruits.py:129-159` |
| 6 | `FRUIT_MU_SAFETY` | **0.6**, and it enters at exactly **two** sites | `tasks.py:2878-2880` (carry legs), `tasks.py:11532-11537` (place-low descent) |
| 7 | what it does | `mu_eff = 0.6 × gripper.mu = 1.2`; a vertical leg's accel budget becomes `a_max = g(√(1 + mu_eff² − 1) − 1) = 0.2 g = 1.962 m/s²`; `limited_by_cone` then clamps `a_max`, `j_max`, `v_max` | `motion.py:16-27`, `:125-140`, `:180-189`; comment `tasks.py:2904-2910` |
| 8 | where the *measured* cone is reported | `MotionMonitor.summary` → `cone=` = `abs(a + g) / (mu_eff * g)` on the **achieved** leg | `motion.py:313-318`, printed `:337-342` |

**Effective tangential capacity at the measured force.** A two-face pinch whose sensor
sums both faces transmits `mu_eff · N_total` whatever the split (two faces at `N/2`
each contribute `mu·N/2` each; a single loaded face contributes `mu·N`), so:

| `mu_eff` | source of that value | capacity at N = 4.4 N |
| --- | --- | --- |
| **0.45** | `min` combine × the lowest fruit mu (apple/pear) | **1.98 N** |
| 1.05 | `min` combine × the highest fruit mu (kiwi) | 4.62 N |
| **1.20** | `0.6 × 2.0` — the model the carry profile itself uses | **5.28 N** |
| 1.49 | `average` combine with a mid fruit mu (0.97) | 6.56 N |
| 2.00 | `max` combine | 8.80 N |

The capacity is therefore **1.98 N in the worst case and 5.28 N in the model's own
case** — a 2.7x spread that is entirely the unverified combine mode.

---

## 4. The slip margin, with arithmetic

### 4.1 Payload mass and the force the carry actually demands

Mass from `fruits.py:977` (`rho · 4/3πr³ · 0.82`, the shipped per-class density in
`meshes.py:261-310`) at each class's mid diameter (`assets.py:439-456`):

| class | d (mm) | m (g) | m·g (N) | +1.0 m/s² (N) | +5.83 m/s² (N) |
| --- | --- | --- | --- | --- | --- |
| strawberry | 37.5 | 15.8 | 0.16 | 0.17 | 0.25 |
| lychee | 33.0 | 13.1 | 0.13 | 0.14 | 0.21 |
| kiwi | 59.0 | 79.4 | 0.78 | 0.86 | 1.24 |
| tomato | 59.0 | 68.8 | 0.67 | 0.74 | 1.08 |
| apple | 66.0 | 104.9 | 1.03 | 1.13 | 1.64 |
| **orange** | 65.0 | **106.1** | **1.04** | 1.15 | **1.66** |
| peach | 64.0 | 92.3 | 0.91 | 1.00 | 1.44 |
| pear | 64.0 | 99.0 | 0.97 | 1.07 | 1.55 |

The acceleration column comes from `motion.TrajectoryLimits`:
`FRUIT_CARRY_AMAX` 2.0, but **while a payload is held** the leg is clipped to the cone
(1.962 m/s² at `mu_eff` 1.2); the dynamic lift is further capped at
`FRUIT_DYNAMIC_LIFT_AMAX = 1.0` (`tasks.py:2913-2915`) and the place at
`FRUIT_DYNAMIC_PLACE_AMAX = 1.089` (`:2936-2939`). The **5.83 m/s²** column is the
largest single-tick `|a|max` any carry leg actually reports on the current tree
(`[motion] carry place0 … |a|max=5.826`, `logs/p39/p3/accept_C.log`) — i.e. a
*following error transient*, not the reference.

**Worst case = 1.04 N static, 1.07 N at the commanded lift cap, 1.66 N at the measured
transient.**

### 4.2 Which term binds

| term | magnitude | verdict |
| --- | --- | --- |
| gravity | **1.04 N** | the base load |
| the profile's acceleration | +0.02 N at the 1.0 m/s² lift cap, +0.11 N at 1.089, **+0.62 N** at the measured 5.83 transient | not a first-order term; the achieved leg sits at `0.86-0.95x` of the model's cone (§4.3) |
| **prying** (the jaws at 98-99 mm) | the pads are commanded **10 mm above the fruit's centre** (`PAD_LIFT`, `tasks.py:49`), so gravity's line is 10 mm off the contact line: `M = m·g·0.010` = **0.0104 N·m** (`1.04 N × 0.010 m`). The friction couple that resists it is `mu·N·w` with the chord `w = 2√(R² − 0.01²)` = 61.8 mm on the 65 mm orange: **0.122 N·m at mu 0.45** | **12x margin — not binding.** And 98-99 mm *is* the joint limit (`0.010 + 2×0.044 = 0.098 m`), i.e. the reading is **post-loss**: the fingers run to full open after the payload leaves. It is a consequence, not a cause |

So by arithmetic the **binding term is the friction coefficient**, and specifically the
`min`-versus-`average` combine question: at `mu_eff` 0.45 the margin over the measured
transient is **1.2x**; at the model's 1.2 it is **3.2x**; at `max` it is 5.3x. Nothing
else in the chain is within a factor of two.

### 4.3 The cone the command itself already uses

`cone=` on the achieved carry legs, current tree (`logs/p40/grip_census_out.txt`):

| battery | `grasp_lift` median / max | legs over 1.0 | the same leg at `mu_eff` 0.45 |
| --- | --- | --- | --- |
| acceptance C | 0.93 / 1.27 | 1 of 10 | **2.5x over** |
| pear battery C | 0.91 / 1.03 | 1 of 9 | **2.4x over** |
| place legs (all) | 0.86-0.93 | 1-2 of 4-5 | 2.3x over |

The shipped profile is already at **86-95 % of a `mu_eff = 1.2` cone**. If the real
`mu_eff` is 0.45, every one of those legs is 2.3-2.5x over its cone *by the model's own
metric* — which is exactly the observed escape class, and it also means **the profile
has no headroom left at the low-mu end**: shrinking the acceleration cannot buy the
worst-case fruit out of a 2.4x deficit.

### 4.4 Normal force needed for 2x and 5x

At the 1.66 N transient demand:

| `mu_eff` | N for 2x | N for 5x | inside the 10 N/joint cap? |
| --- | --- | --- | --- |
| **0.45** | **7.4 N** | **18.4 N** | 2x only (5x needs the ~20 N two-face sum and is at the actuator's edge) |
| 1.05 | 3.2 N | 7.9 N | both |
| 1.20 | 2.8 N | 6.9 N | both |
| 1.49 | 2.2 N | 5.6 N | both |
| 2.00 | 1.7 N | 4.1 N | both |

The measured 4.4 N is **44 % of one joint's cap**. So the 2x target (7.4 N) is reachable
*within the actuator* in the worst-mu case; the 5x target is not (per joint), and at
`mu_eff ≥ 1.05` even 5x sits at 4-8 N, i.e. inside what the C1 close already produced
(10.06 N close `Fmax`).

---

## 5. Every knob that touches the chain

| knob | default | site | what it changes physically | risk |
| --- | --- | --- | --- | --- |
| `FRUIT_FINGER_MU` | **2.0** | `scene.py:359` | the finger material's mu (static = dynamic) | only governs if the combine is `max`; measured **negative** on the pre-v7 line (mu 8.0 → 6/10 vs 7/10, "friction breaks A4", `WORKLOG.md:8412-8414`) |
| `FRUIT_FINGER_FRICTION_COMBINE` | **unset** | `scene.py:151-168` | `min` / `average` / `max` of the pad-fruit pair, i.e. the effective mu (0.45-2.0, §3) | `max` measured **6/10 vs 7/10** on the P3-face screen (`logs/p3face/screen_fk30max.log`); it re-breaks the strawberry (the close's own tangential load) |
| `FRUIT_FINGER_COMPLIANCE` (shipped 30000) | 0 in `scene.py`, **30000 set by `assets.py:62`** | `scene.py:364`, `assets.py:62` | the contact spring `F = k·δ + c·δ'`, i.e. the force-per-interference slope | swept 10 k / 30 k / 100 k N/m: **all 7/10** (`WORKLOG.md:8404-8407`) — flat |
| `FRUIT_FINGER_CONTACT_DAMPING` | 80 (shipped) | `assets.py:63` | the damping term of the same contact | part of the same sweep; no separate reading |
| `FRUIT_MU_SAFETY` | **0.6** | `tasks.py:2878`, `:11532` | the *budget* mu, not the physics: it clips `a_max`/`v_max` on held legs | raising it admits a rougher profile (more inertial demand, same friction) — the wrong direction for retention; lowering it slows the cycle |
| `FRUIT_FINGER_STIFFNESS` / `_DAMPING` | **0 / 0** (no override) | `control.py:169-173` | replaces the asset's k=1e6/c=100 | untested in the record; a soft drive would make the achieved span lag *more*, not less |
| `FRUIT_GRIP_PLANE_DROP` (D2a) | 0.0 | `tasks.py:1169-1171`, `5728-5747` | seats the hand N m lower on the payload (shorter pry arm, more pad face below) | measured and **failed** (-8 mm: escapes worse, 5/20; -4 mm also fails; `logs/r8/A_RESULTS.md`) |
| `_pad_standoff` = `finger_len + PAD_LIFT` | 0.060 + **0.010** | `tasks.py:5728-5747`, `:49` | where on the fruit the pads sit; the contact plane vs the equator | `FRUIT_PAD_LIFT` <0 screens pre-v7 negative; `FRUIT_DYNAMIC_PAD_LIFT_FRAC` measured negative (`logs/p3fix/probe_padfrac`) |
| `FRUIT_DYNAMIC_CLOSE_DEEP` | 0.97 | `tasks.py:9092` | how far past the extent the **fast** ramp targets | inert past contact (§2.5) |
| `FRUIT_DYNAMIC_CLOSE_LIVE` / `MIN_INTERFERENCE` | 0.97 / 2.5 mm | `tasks.py:9321`, `9535-9546` | the live clamp's interference | the *command*, not the force (§2.5); the measured relief screen closed this family (`logs/r6/B_RESULTS.md`) |
| **`FRUIT_CLOSE_LOAD_RATE`** | **0.0 (off)** | `tasks.py:1423-1441`, `:9095-9124`, `:9554-9560` | caps the close's commanded face speed → the pads **reach** the clamp depth (1.6 mm vs 6.8 mm short) and the close force more than doubles | **the one measured normal-force actuator**; negative on the scripted never-stop catch (nc 8 → 25, 28/60 vs 45/60), positive on the direct interface (carried 48 → 27, p = 0.0026) |
| `FRUIT_DYNAMIC_CONTACT_FORCE` / `_TICKS` | **0.5 N / 3** | `tasks.py:9340-9344` | when the close's depth freezes → the hold force | never swept; the freeze fires at 4.2-4.5 N *because* of the 3-tick debounce (§2.1), so this is a force set-point in disguise |
| `FRUIT_DYNAMIC_FORCE_MIN` / `_DROP` / `_REF_MAX` / `_STEP` / `_RANGE` | 2.0 / 0.8 / **4.0** / 0.4 mm / 15 mm | `tasks.py:1497-1518` | the hold servo's floor and rate | the 4.0 N `ref` cap is why the *hold* force cannot rise; a floor guard, not a regulator (§2.1) |
| `FRUIT_CARRY_VMAX/AMAX/JMAX` | 0.38 / 2.0 / 25 | `motion.py:158-178` | the leg profiles, then clipped by the cone | already inside the cone at `mu_eff` 1.2; at 0.45 no profile is safe (§4.3) |
| `FRUIT_DYNAMIC_LIFT_VMAX/AMAX` | 0.30 / 1.0 | `tasks.py:2910-2915` | the lift | swept 0.20/0.25/0.30 → 8/8/9 of 10 (`logs/fast/sweep_iso_p035_l0*`) |
| `FRUIT_DYNAMIC_PLACE_VMAX/AMAX` | 0.35 / 1.089 | `tasks.py:2936-2939` | the place | swept 0.20/0.25/0.30/0.35 → 7/7/8/9 of 10 (same battery) |
| `FRUIT_CARRY_RELIEF` | off | `tasks.py:1296-1310`, `:3260-3290` | caps the commanded interference during the carry | measured: force unchanged, escapes unchanged (`logs/r6/B_RESULTS.md`) |
| `FRUIT_CARRY_GUARD` (+`_HOLD_TICKS`/`_RESEAT_MAX`/`_DERATE`) | off | `tasks.py:1257-1290`, `:3400-3520` | the slip response (re-seat) | two N=5 batches: 5-1 then 3-1, p 0.11 / 0.31 — **not adopted** (`logs/w8/B_RESULTS.md`, `logs/r6/B_RESULTS.md`) |
| `FRUIT_FINGER_SOFT_PAD` | off | `scene.py:448-453` | a real compliant pad body per finger | screened, not adopted |
| `FRUIT_FINGER_FACE` (`v`/`h`/`x`/`c`) | `flat` | `scene.py:443-445` | pad-face geometry (grooves, cups) | all seven forms measured worse: 1-6 of 10 (`WORKLOG.md:8384-8398`) |
| `FRUIT_FINGER_TIP_DELTA` | unset (presence-gated) | `scene.py:396-438` | shortens/extends the finger plate | P39: the −4 mm is bimodal and fails; `+4` withheld (`logs/p39/P1_READ.md`) |
| `FRUIT_FINGER_SCOOP` | off | `scene.py:454-462` | a ledge under the fingertip | measured: it **bats** the payload, 6/20 (`logs/r8/A_RESULTS.md`) |

---

## 6. Cross-check against the record: what was already measured, what is new

| claim in this file | status |
| --- | --- |
| the drive is 10 N/joint, k=1e6, and joint2 is a drive-less mimic | **already measured/read**: `logs/p11/A_PHYSICS_AUDIT.md` G1-G2 (same numbers, same asset lines) |
| the shipped finger contact is **compliant 30 kN/m / 80 Ns/m** (not rigid) | **already correct in the audit** (`A_PHYSICS_AUDIT.md:86`), **wrong in the P40 brief** — this file corrects the brief |
| the combine mode is unset and the "min" comment is unverified | **already flagged** by the audit G5 ("flagged, unverified"); this file quantifies what it is worth (**1.98 vs 5.28 N of capacity, 2.7x**) — new arithmetic |
| the force is set by the freeze, not by any force target | **already measured**: `logs/r6/B_RESULTS.md` §2 ("the drive is force-saturated, so the commanded interference beyond the contact does not set the normal force"); this file supplies the *mechanism* (freeze at 0.5 N + 3 ticks, servo is a floor) — new code trace |
| the force does not separate placed from cnp | **new**: the pooled 8 407 / 1 921 split (4.43 vs 4.36 N) has not been published before |
| the pads stop 5.5-9.5 mm short of their own command, and C1 lands within 1.6 mm | **new as a census** (R6-B's "11.9 mm interference" is a different quantity: `sep − gap` from the joint model, median 9.6 mm over 9 253 grips — the two must not be conflated) |
| the pads stop at `extent + 11.2 mm` regardless of the command; 4.5 N at the stall | **already measured** by the P11-B probe (`logs/p11b/B_EJECTION_PROBE.md` §0); **not** in any grip document, and it contradicts a 1e6 N/m drive — this file carries it forward as the open question |
| single-sided contact at the escape onset | **already measured** by W8-B (31 escapes); this file extends it to **1 125/1 317 (85 %)** over the whole tree |
| the clean/escape `clean_slip` split | **already measured** by W8-B **offline** (0.02-1.43 mm vs 17.9-957 mm). **Caveat, new**: the *live* `[carry] clean_slip_max` on the lift leg reads a **median 303.8 mm over 1 789 lift legs** — it includes the belt-break drag, so it cannot be thresholded at W8-B's 2 mm |
| the lower grip plane / scoop / nest / tip-delta lanes | **already measured negative**: `logs/r8/A_RESULTS.md`, `logs/p39/P1_READ.md`, `logs/p33/51_phase2_read.md`; this file does not re-open them |
| the prying (98-99 mm) is not the binding term | **new arithmetic**: the prying moment is 0.0104 N·m against a 0.122 N·m friction couple (12x), and 98-99 mm *is* the joint limit (`0.010 + 2·0.044`), so it is a post-loss signature |
| a 5x margin needs 18.4 N in the worst case, 2.8-7.9 N at `mu_eff ≥ 1.05` | **new arithmetic** |

---

## 7. What this implies for the lever set

* **Do not spend on friction first.** The record already has two friction screens
  (`FRUIT_FINGER_FRICTION_COMBINE=max`, `FRUIT_FINGER_MU=8.0`) reading **6/10 vs the
  7/10 control**, with the stated mechanism "friction breaks A4" — raising mu also
  raises the close's own tangential load. The arithmetic agrees that the capacity is
  thin in the worst case, but it is *not* the lever with a measured win.
* **The normal force is controllable, and only one knob has ever moved it.** The
  shipped close stops 5.5-9.5 mm short of its own clamp depth and sits at 44 % of the
  drive cap; the C1 close rate lands within 1.6 mm and doubles the close force. Scope
  it as a **post-freeze load phase** (the fruit is already between the pads) rather
  than as a slower close: that keeps the never-stop catch's window, which is exactly
  what made C1 negative on the scripted line.
* **Resolve the `min`/`average` combine before any mu lever is planned.** It is a
  bounded, cheap read (the one-line material dump at the end of this section) and it moves
  the capacity by 2.7x; without it the same
  experiment can be predicted to succeed or fail depending on which comment is right.
* **Do not chase the force floor.** `FRUIT_CARRY_RELIEF` (0.5 mm of allowed
  interference) left the force at 4.15-4.47 N and the escapes unchanged, and the
  servo's 4.0 N `ref` cap means the *hold* force cannot rise through the servo at all.
* **The escape is a loaded slide, not a light grip**: 85 % of the load-taking escapes
  are single-sided at onset, the force is at the carried level (median 5.83 N), and the
  cnp class carries 98 % of the placed class's force. Any retention lever has to act on
  the **contact geometry or the closed-loop response**, not on the squeeze magnitude.
* **The profile has no headroom at the low-mu end** (86-95 % of a `mu_eff` 1.2 cone;
  2.3-2.5x over at 0.45), so "slow the carry down" cannot rescue the worst fruit — it
  only buys the *mid* class a margin it already has.
* **Fix the metric before using it.** The live `[carry] clean_slip_max` (median
  303.8 mm on lift legs) is not W8-B's `clean_slip`; a slip-triggered lever must read
  the post-belt-break segment or it will fire on every attempt.
* **The one number nobody has measured is the drive effort.** If the 4.4 N read is a
  0.44x scaling of a saturated 10 N pinch, then every margin in §4 is 2.2x larger and
  the whole "raise N" family is already at the actuator's limit — which would flip the
  ranking of every lever above.

### The single largest remaining unknown (grip)

**Whether the tactile `value` equals the contact normal force.** The pads stall at a
fixed span with a fixed 4.5 N while the drive (k = 1e6 N/m, 6.4-26.4 mm of position
error, 10 N cap) should be saturated at 10 N — a 2.2x discrepancy that no offline read can
settle, because the fruit-side contact view is invalid in this build
(`logs/p11b/10_sweep_tomato.log`: "fruit contact view invalid … F_fruit reads 0"), so
there is no second sensor to cross-check against.

**Settle it in one claimed simulator run, no new knob:** read the finger dofs' *applied
effort* during a held carry and print it beside the tactile reading. The repo has never
read a joint effort (`grep -rn "get_dof_efforts" src/` is empty), so the accessor is the
one unknown in this measurement — Isaac's core `Articulation` exposes `get_dof_efforts`,
and `control.py`'s trace rows already prove the same articulation object can be read for
`drive_target`/`drive_velocity_target`, which is the fallback (effort = k·(target −
measured) + c·(v_target − v_measured), the drive's own law). Print
`effort_left/right` beside `tactile.read()` on the same tick, for ~20 grips, in the
patch battery. If `effort ≈ 10 N` while the sensor reads 4.4 N, the sensor is a scaled
readout and §4's capacity column must be multiplied by ~2.2 before any lever is ranked;
if `effort ≈ 4.4 N`, the drive is **not** saturated, the P11-B stall has another
explanation (the mimic's zero offset is the leading candidate), and the lever set keeps
its current order.
