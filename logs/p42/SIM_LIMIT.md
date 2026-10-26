# The carried-not-placed class is this sim's documented limit

**Status: this is a limit record, not a bug report.** Written 2026-10-26 (P42
phase 2) on `c2760bf` + the P42 seat instrument/lever, and finalised at the
close-out in commit **`2e5afd8`** (`tasks.py` **`e2d0f12a`**, `rl_env.py`
**`50980bf5`**; the measured tree was `3e6ea4cf`, and the close-out edit is the
`_seat_centre_step` docstring in **comment only**). It exists
so that no later reader re-opens a measured family, and so that any rate quoted
on this tree is quoted with the class in view. Every number below carries the
file it was measured in.

**The class, one sentence.** The scripted / policy hand carries a fruit out of
the jaw and drops it on the way to the output line ("carried-not-placed",
`cnp`), while the pads are still closed and loaded: a **loaded slide**, not a
grip failure, not a force shortage, and not a seating error.

---

## 0. The mechanism (measured, three independent corpora)

1. **The jaws are symmetric by construction.** The two finger links are joined by
   `PhysxMimicJointAPI:rotY` with `gearing = -1`, `naturalFrequency = 0` and no
   drive on the second joint
   (`assets/openarm_flat/openarm_flat_deinst.usda:3822-3843`), i.e. a **rigid**
   mimic: "one finger lags" cannot happen, and a dual drive is moot
   (`logs/p42/SEAT_CENSUS.md` §1; the published `maxForce = 0.0 N` read on
   `joint2` is in `logs/p41/P3_RESULTS.md` §1).
2. **The pinch is not the limiting force.** After the P41 drive-profile flip the
   delivered pinch is **9.75-9.9 N** (2.2x the pre-flip 4.38-4.42 N) at
   **1.00-1.01x wall** (`logs/p41/P3_RESULTS.md`, `logs/p41/P2_RESULTS.md` §2).
   At the close freeze both pads are **in contact on 20/20 grips** with a
   balanced split, **`asym` 0.01-0.35** (median 0.06-0.17), and the escapes are
   the *more* balanced grips, not the less
   (`logs/p42/SEAT_CENSUS.md` §3-§4; per-grip tables
   `logs/p42/p2/seat_{accept,pear}_table.txt`).
3. **The payload walks, in the hand frame, mid-lift.** From the freeze
   (`d` = pads - fruit, re-referenced as `drift = d - d_freeze`) the displacement
   by the lift's 99 % sample is **28-58 mm on placed legs** (pear median 40.0,
   acceptance 48.3) and **104-276 mm on the escape legs** (pear median 194.8,
   range 104.3-276.0), reaching **302-375 mm** by the place leg's first ticks
   (with the payload 283-288 mm *below* the pads, i.e. it left through the
   bottom of the jaw)
   (`logs/p42/SEAT_CENSUS.md` §5, both corpora).
4. **The contact goes one-sided as it walks.** One pad has lost contact on
   **18 of 32 escape carry samples vs 0 of 48 placed** ones, and the first
   one-sided sample is at the lift's first, middle or last sample (k = 1-3),
   **never at the freeze**
   (`logs/p42/SEAT_CENSUS.md` §5; the same signature in
   `logs/w8/B_RESULTS.md`, `logs/r6/B_RESULTS.md` §"reaction path",
   `logs/r11/B_RESULTS.md` §4.1-4.2).
5. **The onset is force-neutral.** At the slip onset the force is still at its
   carry level (W8-B: 0.45-12.9 N, **median 4.90 N**, single-sided; contact loss
   follows the 2 mm crossing by 2-132 ticks, median 25) and with the P41 profile
   the jaws are still held to their **98.5 mm open stop** on the escape legs
   (`sep_max` 98.5 / 76.0 / 77.4 / 64.2 mm against 98.3 / 98.2 / 77.9 on the
   control's) - **the pads hold and the payload slides**
   (`logs/w8/B_RESULTS.md`, `logs/p41/P3_RESULTS.md` §2).
6. **The pre-onset window is not the term.** Through the belt break, the
   take-off probe and the close the payload's hand-frame pose moves **0 mm** to
   the 0.5 mm trace resolution (3-8 mm through the close); the escape begins
   inside `grasp_lift` (`logs/r11/B_RESULTS.md` §4.1, `logs/p18b/B_RESULTS.md`
   §4). The frame-free metric for it is `clean_slip`: **0.02-1.43 mm** on 33
   clean leg-outs vs **17.9-957 mm** on 31 escapes, **no overlap**
   (`logs/w8/B_RESULTS.md`; live in the default-off `FRUIT_CARRY_DIAG=1`
   `[carry]` row, offline in `logs/w8/B_metric.py`).
   **Do not quote the legacy `[motion] ... slip_max` for this hand**: it is
   frame-contaminated (25.6-104.7 mm of ghost slip on *placed* carries) - use
   `clean_slip`.

**Therefore**: the class is a **flat, rigid, drive-capped pad sliding on a
curved, compliant payload under a vertical load**. Nothing in the force path or
the seating geometry sets it; the pad *shape* and the absence of envelopment
do.

---

## 1. The force family is closed (every lever measured, none adopted)

| lever | result | evidence |
|---|---|---|
| drive profile `c/k` (`FRUIT_FINGER_STIFFNESS`, shipped `finger_damp02` k=1e5 c=2000) | **shipped** (a parameterization fix, not a lever): pinch 4.4 -> 9.8 N = 2.2x at 1.00x wall; **the class does not convert** (acceptance 6/10, pear 6/10) | `logs/p41/P3_RESULTS.md`, `logs/p41/DEVIATION.md` (the pre-registered F2 fired) |
| `FRUIT_FINGER_MAXFORCE` 10 -> 30 -> 60 N | **deletes the pad pry** (`sep_max` 98.5 -> 43.5 -> 31.2 mm) and the class **worsens**: pear 6/10 -> 4/10, two-line 8/10 -> 6/10; at 60 N a 3.7 cm strawberry is crushed out of the hand (`clean_slip` 641 mm at `F@onset` 62.3 N). Not adopted (default off) | `logs/p41/P3_RESULTS.md` §2-§4, `logs/p41/p3/pry_sep_max_mf{30,60}.txt` |
| raising the effective friction (`FRUIT_FINGER_MU=8`, `frictionCombineMode=max`) | **6/10** against the compliant baseline's **7/10**, and it re-ejects the strawberry | P3-faces, `WORKLOG.md` "P3-faces" material sweep; `logs/p3face/` |
| squeeze-side: the relief cap (`FRUIT_CARRY_RELIEF`, down to 0.5 mm of interference) | **physically inert**: releasing the command by 12-23 mm leaves the contact force unchanged (4.15-4.47 N) because the drive is force-saturated. Default off, not adopted | `logs/r6/B_RESULTS.md` §"The interference is physically inert", `logs/r6/B_relief_smoke.txt` |
| post-freeze load shaping (`FRUIT_CLOSE_LOAD_RATE` 0.04 m/s, `_CONTACT_LEAD`, `FRUIT_PLUCK_DWELL`) | converts the carried class on the **direct** interface (48 -> 27, class-stratified p = 0.0026) but is **negative on all three scripted measurements** (stage-P 12/20 vs 13/18; two-line 28/60 vs 45/60, no-contact 8 -> 25): a slow close is incompatible with a never-stop catch. Default off, not adopted | `logs/r11/B_RESULTS.md`, `logs/p18b/B_RESULTS.md` §4-§5, `logs/p21/RESULTS.md`, `logs/p20/ORACLE_GATE3.md` |
| compliant pad **body** (D2, `FRUIT_FINGER_SOFT_PAD`, k=5000 N/m, 5 mm travel) | **falsifier fired** (the pre-registered in-hand slide < 30 mm + placed): 7/10, the slide unchanged, the pads compress 0.2-1.0 mm - the deformation is not where the escape happens | `logs/d2_mechanism/` (preregistration, `rate_d2pad_mech_1.log`, trace clip) |
| contact-face shapes `v/h/x/c` (additive) and `v2/h2/x2/c2` (recessed) | **2-6/10** against flat 6-8/10; the additive wings protrude 3 mm into the entry envelope and **bat the catch**, the recessed boxes replace the plate with hard edges | P3-faces table (`WORKLOG.md` "P3-faces"), `logs/p3face/screen_*.log`, the shape x compliance matrix `logs/dyn_v4/{label}.log` |
| deep plates (`FRUIT_FINGER_FACE=p`, 12 mm past the fingertip; and deep=0) | **5/10** (deep 12: batters the catch, A4 ejected in the hold at 23.3 N) and **7/10** (co-planar only: A2/A8 unchanged) | `logs/dyn_v6/mech_v6p.log`, `logs/dyn_v6/mech_v6p0.log`, `WORKLOG.md` "v6 exp 2" |
| cradle / scoop (`FRUIT_FINGER_SCOOP=1`, one ledge per finger) | the ledges **bat the payload**: no-contact 2 -> 9 of 15, flails 1 -> 7, `sep@onset <= 22 mm` on the new class; battery 6/20 x2 | `logs/r8/A_RESULTS.md` §3 |
| grip-plane drop (`FRUIT_GRIP_PLANE_DROP`, the z/standoff lane) | D2a: the escape signature persists, the lift population moves into the > 400 mm band (11 -> 2 vs 2 -> 10), flails 1 -> 14, one descent over budget | `logs/r8/A_RESULTS.md` §2 |
| finger-tip delta (`FRUIT_FINGER_TIP_DELTA`, -4 mm) | no arm improves in any **evaluable** comparison; the `47` clearance probe **jams** so the belt-clearance claim is *untested, not measured zero*; +4 mm withheld | `logs/p39/P1_READ.md`, `logs/p39/p3/RESULT.md` §0, §3 |
| ability to detect/recover online (the "watcher") | **not buildable on the measured signal**: carry losses keep 2-8 N on one finger (32-46 N on one), and where the force collapses the payload is out within 0-3 ticks; a pose-only key fires on successes | `logs/w5/` (W5-C), `logs/w8/B_RESULTS.md` |

**Read the table as one statement**: at **2.2x force** (and at 6x), **at every
face shape**, **at every depth**, **with a compliant body**, and **with the
interference released to 0.5 mm**, the carried class persists. It is not a
force budget, a squeeze depth, a drive gain or a contact-material problem.

---

## 2. The seat geometry is closed: the pads are centred on the payload

Four independent reads, all negative:

1. **The census** (`logs/p42/SEAT_CENSUS.md` §0, §3, §6): at the close freeze the
   pads' midpoint is **1.36-4.65 mm** from the fruit's centre in x/y on **all 20
   grips** of both corpora (median 1.7-2.4 mm), two-sided on 20/20, and the
   offset **does not predict the escape** - on the species-locked pear battery
   the four escapes are the *tightest* seat cluster (1.36-2.06 mm, median 1.72)
   while the corpus's largest lateral offset (4.65 mm) **placed**. The only
   systematic axis is `dz = +69.3..+71.7 mm`, which **is** the commanded
   `_pad_standoff` (a grip-plane question, and D2a above is its measured
   negative), not an error.
2. **The bounded centring lever** (`logs/p42/P2_RESULTS.md`): `FRUIT_SEAT_CENTRE`
   issues the registered one-shot `clip(-d_xy, +-10 mm)` re-aim on every grip
   (|c| median **2.99 mm** pear / **2.91 mm** acceptance, clamp never binding)
   and the freeze seat is back to the control's value by the freeze:
   **paired median change +0.00 mm** (pear) and **+0.01 mm** (acceptance). The
   class does not convert (the pear's counts differ on a moved branch with the
   left attempt count 6 -> 4, so they are a report, not a verdict; the
   acceptance is 6/10 in both arms on two attractors). The reason the command is
   absorbed is a measured one: **the close is coherent** - its own flag reads
   `True` on 20/20 grip closes and it re-aims at the fruit's live centre every
   tick - and the PREREG's premise (the carry bookkeeping's
   `self._coherent[side]`, `False` on 60/60 legs) is a **different variable**.
3. **The per-slot class is not a stable function of the fruit.** The P42
   acceptance's own attempt 0 (peach) reads a freeze seat of 2.63 mm against the
   control's 2.62 mm and lifts 27.5 mm of `slip_max` where the control lifted
   266.2 mm; P39 found the mirror case inside one arm (a kiwi of identical size
   and interference, `cnp` at attempt 3 and placed at attempt 9,
   `logs/p39/p3/RESULT.md` §0).

4. **The family's other arms, so "closed" is not read as "only the one-shot".**
   The x/y aim has been screened in four forms and the one that **ships** is the
   *bounded* one:

   | arm | what it moves | measured |
   |---|---|---|
   | **P2b live-x steering** (per tick, unbounded; the pre-P2b close; `FRUIT_DYNAMIC_TRACK_WALK=1` reproduces it) | the aim's **x**, every close tick, onto the live fruit | **measured to expel the payload**: it left the span *during* the close (cross-belt +122/+147 mm, force 0 through the whole hold) - which is why the shipped default **pins** x at the first close tick (`FRUIT_DYNAMIC_CLOSE_LOCK_X=1`; the P2b block `tasks.py:9889-9904`, trace `logs/p2_trace10`) |
   | **R2 walk lead + bounded x-track** (`FRUIT_DYNAMIC_WALK_LEAD` 0.0 = off; `FRUIT_DYNAMIC_X_TRACK_VMAX` **0.12**, `_VX_MAX` **0.05**, `_LATCH` **1** - **shipped**) | the aim's **x**, per tick, at a bounded rate and ahead of a measured walk | the **shipped centring form**: it seeks only until the freeze fires, and a fruit already walking at contact is left pinned (`FRUIT_DYNAMIC_WALK_LEAD` was measured *worse*: 1265 mm drag, `s9_walklead`; the unbounded tracker is the P2b row). **This is why the freeze seat already reads centred to 1-5 mm** - the family's x/y correction is *on*, in its bounded form, so the one-shot lever had nothing left to add |
   | **R8-A D2a z drop** (`FRUIT_GRIP_PLANE_DROP=0.008`, default off) | the commanded **standoff** (z) | **negative**: the escape signature persists, the lift population moves into the > 400 mm band (11 -> 2 vs 2 -> 10), flails 1 -> 14, one descent over budget (`logs/r8/A_RESULTS.md` §2; cited in §1 above) |
   | **P42 pre-close one-shot** (`FRUIT_SEAT_CENTRE`, default off) | x/y, **once**, before the close ramp | **absorbed** by the close's own per-tick absolute aim (§2 item 2): \|c\| median 2.99 mm issued, paired freeze change **+0.00 mm**, clamp never binding |

**Ceiling of the seat lane**: ~4.6 mm observed, ~3 mm commanded, against a
**104-276 mm** mid-lift walk - a factor of 30-60. There is no version of
"seat it better" that reaches the walk.

**Scope of every seat statement here**: measured on the **scripted single arm**
(the `20_pick_place.py` moving catch, `ATTEMPTS=10 SEED=5`). The close is
**shared code** - the two-line scheduler and the direct/policy handover run the
same ramp and the same `_pad_standoff`/x-lock/`centre` aim - but neither has been
run with the seat instrument or the centring lever, so **their seat is
unmeasured**, and a `cnp` count from them is their scenario's count (§3 item 5).

---

## 3. How to read this tree (rules for later work)

1. **Any quoted rate on this tree carries the class.** A 6/10 or 9/10 means
   nothing without the `cnp` count beside it: the scripted line's typical
   branch is 6-9 placed of 10 with the remaining attempts split between
   `cnp` and no-grasp, and AGENTS §2's attractor rule applies (compare per-leg
   motion, not cross-configuration counts). Every `[run] attempt` row prints
   `placed=`, so the count is always available.
2. **Do not re-open the force family** (drive force, max force, squeeze depth,
   interference, friction, load rate) **or the seat family** (pre-close
   centring, grip-plane drop, x/y aim) without either **(a) a new asset** - a
   pad form with real envelopment - or **(b) a real-jaw clamp-force anchor**
   (see §4). Each is closed with a mechanism above, and re-running one measures
   the attractor again.
3. **The class is a sim/hardware property, not evidence about a real jaw.**
   These fingers are **flat rigid plates** with no compliant enveloping and no
   distal feature, driven against a **10 N/joint cap** on a curved, deformable
   payload. A real compliant jaw (rubber-faced, self-aligning, or a two-finger
   form that closes around the equator) would not be expected to behave this
   way, and nothing here says it does. The sim-to-real reasons the two differ
   are catalogued in `logs/p40/LIT_REVIEW.md` §4 (friction-combine defaults,
   penetration-based grasp force being timestep-dependent, and a rigid backing
   where a real jaw cantilevers) - so the class is *expected* to be
   sim-specific, not merely suspected. Conversely, **do not** cite this class as
   a predictor of field failures, and **do not** cite "the sim can hold the
   fruit" - the acceptance still reads 6/10 and the pear 6/10 under the shipped
   profile (`logs/p41/P3_RESULTS.md`, `logs/p42/P2_RESULTS.md` §3).
4. **The gripper's force read is a tactile estimate, not a clamp-force
   measurement**: the same-tick projected joint reaction agrees to 0.1-0.5 %
   (`logs/p40/GRIP_CENSUS.md` §3), the *command* is at its 10 N/joint cap on
   40/40 contact rows while the delivered reaction is 22 % of it pre-P41, and
   the `F/err` ratio is an operating-point timestep signature, not a stiffness
   (`logs/p40/EFFORT_READ.md`, `logs/p41/P2_RESULTS.md` §2). Quote `N` as the
   *delivered pinch* (4.4 pre-P41, 9.8-9.9 after), never as a clamp force.
5. **A two-line or policy `cnp` count is a different scenario's count.** The
   two-line's class split, the direct interface's (carried 27 of 75 with the
   load-rate lever on, `logs/p18b/B_RESULTS.md` §4) and the scripted single
   arm's are not interchangeable: quote the interface, the supply and the
   attractor with the number.

---

## 4. What would change it

Only one of these two, and each has a precondition:

1. **An asset-level pad form**: a pad that **envelops** the payload - a
   compliant body with real travel under load, a V/concave face *with* depth,
   or a distal feature that resists the axial walk. Precondition: it must be
   authored as a *new asset variant* and screened with `scripts/144_contact_face_probe.py`
   plus a two-cell trace batch, and it must not protrude into the entry
   envelope (every additive face so far has been measured to bat the catch,
   §1). The closed variants (scoop, deep plate, v/h/x/c, soft pad body) name the
   failure modes to avoid: **entry interference** and **hard edges replacing the
   plate**.
2. **A real-jaw clamp-force anchor**: a bench measurement of the actual OpenArm
   jaw's delivered pinch and its compliance on the fruit, so the sim's 9.8 N /
   10 N-cap / force-saturated drive can be anchored to hardware. Precondition:
   this gates a *fidelity* claim only; it does not convert the class, and it is
   the item the P41 record already names
   (`logs/p40/P4_RESULTS.md` §"What is measured vs what is claimed" item 3,
   `logs/p41/P2_RESULTS.md` §4, `logs/p41/DEVIATION.md`).

Anything else - a bigger force, a deeper squeeze, a softer drive, another face
shape, a better seat - is a re-measurement of a closed family.

---

## 5. Provenance

P42 phases 1-2 were measured on `c2760bf` + `tasks.py` **`3e6ea4cf`** /
`rl_env.py` **`b4d4accc`**; the close-out ships as commit **`2e5afd8`** with
`tasks.py` **`e2d0f12a`** (the `_seat_centre_step` docstring corrected in
**comment only** - a reverse substitution of the old block reproduces `3e6ea4cf`
byte-for-byte, so every number here is that code) and `rl_env.py` **`50980bf5`**
(`TASKS_MD5` follow). `configs/motion_reference.json` **8a399626** and
`configs/motion_reference_twoline.json` **2246f83c** are **untouched**;
`scene.py` `27e3d64a` and `control.py` `9384ff4f` are unchanged by this phase.
The Oracle's close-out gate reads **ACCEPT WITH AMENDMENTS** (five): §2 item 4
(the family's other arms), this provenance, the scope sentence in §2, the
`PREREG.md` A1 correction block and the docstring correction. The class's
mechanism corpus: `logs/w8/B_RESULTS.md` (W8-B, the metric and the reaction
path), `logs/r6/B_RESULTS.md` (R6-B, the drive-saturated pinch),
`logs/r11/B_RESULTS.md` + `logs/p18b/B_RESULTS.md` (the load path),
`logs/p41/P3_RESULTS.md` (the force cap), `logs/p42/SEAT_CENSUS.md` (the seat).
The levers' negatives are cited in-line in §1-§2. The policy-side counterpart
(the hybrid canary and the direct A/Bs that quote a carried count) is in
`logs/p37/`, `logs/p33/`, `logs/p35/`, `logs/p36/` and AGENTS §2; the class is
the same one, and the same rule applies: **quote the interface, the supply and
the attractor with the number**.
