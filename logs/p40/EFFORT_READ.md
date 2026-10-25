# P40 G0 — the drive-effort readout: the tactile is not a scaled read, and the
# shipped substeps deliver 22 % of the drive's cap

Measured 2026-10-26 on the P39-final tree `1790b87` + the default-off
`FRUIT_GRIP_EFFORT` instrument (`tasks.py` `34275f07`, the `rl_env.py`
`TASKS_MD5` metadata-only follow `e137eb59`). **No shipped default changed, no
`configs/` file touched, no commit.** Two claimed runs, `logs/p40/p2/`:

| run | log | scenario | substeps | census | sim | wall |
|---|---|---|---|---|---|---|
| (a) shipped | `effort_sub1.log` | acceptance, `ATTEMPTS=10 SEED=5` | 1 (120 Hz) | **6/10** | 150.2 s | 266 s |
| (b) 480 Hz | `effort_sub4.log` | same | 4 (480 Hz) | **8/10** | 156.8 s | 819 s (3.08x) |

Per-event table: `logs/p40/p2/effort_table.txt` (`effort_table.py` re-derives it).

---

## 0. The answer in one screen

* **The 2.2x under-read is REFUTED.** On the shipped substeps the tactile sum is
  **4.42 N** (median of 40 contact rows across the 10 grabs' freeze and carry events) and the **same-tick
  projected joint force** — a different buffer, the physics' own reaction along
  the joint axis — sums to **4.42 N** (ratio **0.999**; per face 2.24/2.28 N vs
  the joint it rides 2.25/2.23 N). A sensor-only 0.44x scaling cannot produce
  that agreement, so **every friction capacity in `GRIP_CENSUS` §3/§4 stands as
  written** and nothing is multiplied by 2.2.
* **The 4.5 -> 10.0 N step `logs/p11b` §4/§6.3 measured is real, and it is a
  force step, not a calibration step.** At `FRUIT_SUBSTEPS=4` the tactile sum is
  **9.95 N** and the joint reaction sums to **10.00 N** (ratio **0.995**). The
  delivered normal force **doubles with the physics rate** (4.42 -> 9.95 N,
  **2.25x**); the instrument tracks it to 0.5 % both times.
* **The drive's *command* is at its 10 N cap on 40/40 contact rows; what it
  *delivers* is 22 % of it.** Pooled over the contact rows it
  delivers **2.21 N per joint on the shipped substeps (22.1 % of the cap)** and
  **5.00 N per joint at 480 Hz (50.0 %)**; at the close freeze alone the medians
  are 1.58 N (15.8 %) and 4.95 N (49.5 %). The PREREG's Branch A obtains ("the drive is position-limited
  rather than force-limited"), but not for the reason the census hypothesised:
  the authored k = 1e6 N/m is **not** the force constant in effect (see §4).
* **`get_dof_efforts` exists and is useless here**: it returns **+0.00 N on all
  98 sampled event-rows in both runs**. The claim rests on
  `get_dof_projected_joint_forces` + the drive law, reported side by side (§2).
* **Neutrality: PASS.** 425 `[fruit]` lines = the archived control's 376 + 49
  `[effort]`; after filtering the instrument out, **374/376 lines are
  byte-identical** and the two that differ are the *output-belt clearance print
  lines* (the documented P32 print-only variant, §5).
* **The force lever is the solver rate, not the squeeze** (and it is not free):
  +2.25x normal force for **3.08x wall** and **+0.66 s/attempt of span**
  (`[stats]` 150.2 -> 156.8 s over 10 attempts; quote that, not "+0.90 s" or
  "+4 %") — `FRUIT_SUBSTEPS=4`, a global physics
  setting with its own reference/attribution needs. Nothing is adopted here.

---

## 1. What was added (default-off, reporting only)

`FRUIT_GRIP_EFFORT=1` in `src/fruit_sorting/tasks.py`. Unset, the knob is one
`bool` read per tick at two hook sites and one `dict.pop` per leg boundary, and
`_grip_effort_begin` returns before touching any pose, and the physics stream
stays **byte-identical** to the archived control (§5). Nothing else in the task loop changed - no command, no
threshold, no existing print, no control path.

Three event families, one line each, **5-tick medians** (the pool's contact
`Fmax` reaches 612 N on isolated ticks, so one sample is a spike):

* `close_freeze` - armed at the close ramp's end, sampled over the **first 5
  ticks of the post-close hold**, i.e. the loaded state the reported `N`
  describes (the freeze pins `cmd` at the first sustained contact and the hold
  re-commands that same gap every tick);
* `carry_start:<leg>` / `carry_end:<leg>` - the leg's **first 5** and **last 5**
  profile ticks, for `grasp_lift` and `place<lane>`;
* a one-time banner naming the accessors, the joint names, the gains and the
  runtime `maxForce`.

Line format (one row of `logs/p40/p2/effort_sub1.log`):

```
[fruit] [effort] left idx=3 close_freeze sub=1 t=11.667s n=5 | tact[N]=2.24,2.28
  sum=4.52 contacts=2 | openarm_left_finger_joint1: eff[N]=+0.00 proj[N]=-2.25
  kpc[N]=-4207.85 Fsat[N]=-10.00 q[mm]=30.39 tgt[mm]=26.18 err[mm]=-4.21 |
  openarm_left_finger_joint2: eff[N]=+0.00 proj[N]=-2.23 kpc[N]=+0.00
  Fsat[N]=+0.00 q[mm]=30.39 tgt[mm]=26.18 err[mm]=-4.21
```

(wrapped here for width; it is one `say()` line, prefixed `[fruit] ` by the
logger)

**Frame and units.** The finger joints are **prismatic, axis Y, metres**; every
force column is **newtons along that axis** (positive = the joint's positive
direction, so a *closing* push reads negative). `tact[N]` is the per-finger
contact-sensor `value` in newtons the logs' `N` comes from (`tactile.py:104-146`),
printed **in joint order** - `joint1` -> `openarm_<side>_right_finger`, `joint2` ->
`openarm_<side>_left_finger` (the asset's `physics:body1`, usda `:3798` / `:3822`;
`tasks.py` `FINGER_JOINT_FACE_INDEX`) - so face k and joint k are one finger.
`err` = **`drive_target - position`**, in mm.

## 2. The accessor chain, and which one carries the claim

| column | accessor | what it is | usable? |
|---|---|---|---|
| `eff` | `Articulation.get_dof_efforts(dof_indices=[j1,j2])` -> the tensor API's `get_dof_actuation_forces()` | what the **drive says** it applied | **no** - `+0.00 N` on **98/98** rows in both runs (this build's implicit-PD position drives do not populate the actuation buffer) |
| `proj` | `Articulation.get_dof_projected_joint_forces(...)` | the physics' own **reaction along the joint's motion direction**, i.e. what the joint actually carried | **yes** - and it is the second instrument the census lacked |
| `kpc` | the drive's own law from `get_dof_gains`: `k*(target-q) + c*(v_target - v)` | the force the *authored* gains would command | computed, **not** the delivered force (§4) |
| `Fsat` | `clip(kpc, +-maxForce)`, `maxForce` from `get_dof_max_efforts` | the force that law could deliver inside the cap | the cap is never binding (§4) |

Runtime confirmation of the asset, read through the API (not the USD text):
`k = 1000000 / 0 N/m`, `c = 100 / 0 Ns/m`, `maxForce = 10.0 / 0.0 N` for
`joint1`/`joint2`. **`openarm_<side>_finger_joint2` is a drive-less mimic** -
0 stiffness, 0 damping, 0 cap - which is why the force claim rests on `joint1`
and on the substeps pair. The mimic's *reaction* is still real and reads in
`proj` (it is the second face of the pinch).

## 3. The numbers, per grab (close freeze, 5-tick medians)

`tact[0]/tact[1]` are joint1's and joint2's faces; `j1proj` is joint1's physics
reaction. Both runs, all 10 grabs:

| run | grab | tact face0/face1 | **tact sum** | `j1eff` | **`j1proj`** | `j1kpc` | `j1` err |
|---|---|---|---|---|---|---|---|
| sub1 | left idx 3 | 2.24 / 2.28 | **4.52 N** | +0.00 | **-2.25 N** | -4207.9 N | -4.21 mm |
| sub1 | left idx 12 | 1.42 / 2.91 | **4.23** | +0.00 | **-1.38** | -4511.7 | -4.51 |
| sub1 | left idx 2 | 2.43 / 1.72 | **4.15** | +0.00 | **-2.41** | -5446.9 | -5.45 |
| sub1 | left idx 10 | 1.80 / 2.68 | **4.44** | +0.00 | **-1.79** | -3945.9 | -3.95 |
| sub1 | right idx 1 | 1.71 / 2.32 | **4.03** | +0.00 | **-1.94** | -5396.0 | -5.40 |
| sub1 | right idx 5 | 1.90 / 3.23 | **5.13** | +0.00 | **-1.85** | -6790.4 | -6.79 |
| sub1 | right idx 11 | 1.28 / 2.91 | **4.19** | +0.00 | **-1.36** | -7571.8 | -7.57 |
| sub1 | right idx 14 | 0.81 / 3.79 | **4.57** | +0.00 | **-0.59** | -5732.7 | -5.73 |
| sub1 | right idx 15 | 1.17 / 2.68 | **3.85** | +0.00 | **-1.17** | -5941.8 | -5.94 |
| sub1 | left idx 0 | 4.24 / 3.80 | **8.04** | +0.00 | **-0.90** | -6537.3 | -6.53 |
| sub4 | left idx 3 | 4.99 / 5.00 | **9.99** | +0.00 | **-5.00** | -3866.7 | -3.86 |
| sub4 | left idx 12 | 2.21 / 6.70 | **8.91** | +0.00 | **-2.33** | -5175.9 | -5.17 |
| sub4 | left idx 2 | 5.00 / 5.00 | **10.00** | +0.00 | **-5.00** | -4373.9 | -4.37 |
| sub4 | left idx 10 | 1.38 / 7.89 | **9.92** | +0.00 | **-1.38** | -4647.4 | -4.64 |
| sub4 | right idx 1 | 4.90 / 5.09 | **9.99** | +0.00 | **-4.90** | -5721.5 | -5.72 |
| sub4 | right idx 5 | 5.20 / 4.12 | **9.32** | +0.00 | **-5.20** | -5688.9 | -5.69 |
| sub4 | right idx 11 | 4.74 / 6.30 | **11.10** | +0.00 | **-4.73** | -7194.0 | -7.19 |
| sub4 | left idx 12 | 5.00 / 5.02 | **10.01** | +0.00 | **-5.00** | -5119.9 | -5.12 |
| sub4 | left idx 13 | 4.13 / 5.82 | **9.96** | +0.00 | **-4.17** | -5071.4 | -5.07 |
| sub4 | left idx 6 | 5.00 / 4.95 | **9.95** | +0.00 | **-5.01** | -4727.8 | -4.72 |

Pooled over **all** contact rows (`tact_sum > 1 N`), which is the read of record:

| run | contact rows | tact sum (median) | `proj` sum (median) | tact/proj | `abs(j1proj)` | load / cap | `abs(err)` | `F/err` (N/m) | authored `k*err` |
|---|---|---|---|---|---|---|---|---|---|
| sub1 | 40 | **4.42 N** | **4.42 N** | **0.999** | **2.21 N** | **0.221** | 5.87 mm | 377 N/m | 5870 N |
| sub4 | 44 | **9.95 N** | **10.00 N** | **0.995** | **5.00 N** | **0.500** | 4.79 mm | 1045 N/m | 4785 N |

The carry legs read the same as the freeze (sub1 median 4.42 N, `j1proj` 2.40 N;
sub4 9.90 N, 5.00 N); the rows where the payload was already gone read
`tact 0.00 / proj +-0.03..0.26 N`.

## 4. What force the drive actually delivers - and why the 10 N premise fails

At the freeze **`err` = 3.95-7.57 mm** (median 5.59 mm at sub-1) and the joint
carries a median **1.58 N**. The authored law would command
`1e6 x 5.59 mm = 5.87 kN`, clamped to `Fsat = 10 N`. So:

* the delivered force at the freeze is **1.6 N per joint, 3.2 N per pinch
  (15.8 % of cap)**; pooled over the contact rows it is **2.21 N per joint,
  4.4 N per pinch at 120 Hz (22.1 %)**, and **5.00 / 10.0 N at 480 Hz (50.0 %)**.
  The 10 N cap is never **delivered** (it only clips the *command*, on every
  row) and is not what sets the force;
* the authored **k = 1e6 N/m is not the force constant in effect**: the
  **operating-point `F/err` ratio** is `2.21 N / 5.87 mm = 377 N/m` pooled at
  sub-1 (283 N/m from the freeze pair) and `5.00 / 4.79 mm = 1045 N/m` at sub-4 -
  **1/2650 and 1/957 of the authored stiffness**, and not even constant between
  the freeze and the carry. **This is a ratio, not a stiffness**: it is the
  delivered force divided by the commanded position error at that operating
  point, and it is a **timestep signature** (it nearly triples when the step
  shrinks 4x) — the *law* behind it is **not identified** by this run. What it
  does say is that `GRIP_CENSUS` §2.5's second branch ("...or the joint's
  effective stiffness is ~0.8 kN/m, not 1e6") is the one that obtained, in the
  weaker sense that the measured ratio sits in the census's own 0.8 kN/m
  ballpark (283-1045 N/m) - a coincidence of the operating point, not a
  calibrated constant;
* **the delivered force scales with the physics rate, not with the commanded
  depth.** 4x substeps -> **2.25x** the normal force (4.42 -> 9.95 N) at
  essentially the same `err` (5.87 -> 4.79 mm), while p11b measured *20 mm of
  extra commanded interference to be inert* at a fixed rate. So what caps the
  force is the **drive/contact pair at that timestep** (a 30 kN/m contact spring
  and a drive that cannot push harder than ~2.2 N inside one 1/120 s step), not
  the `maxForce` field and not the command. The exact scaling law is **not**
  identified (2.25x for a 4x rate is neither dt^-1 nor dt^-2), and this run does
  not separate stiffness from damping or from the solver's implicit-spring
  regularisation.

## 5. Neutrality - exact

The instrument is additive and the run it produced is the archived control's:

* line census of run (a): 425 `[fruit]` lines = **376 control lines + 49
  `[effort]` lines**; the mix otherwise matches exactly (258 `[task]`, 48
  `[motion]`, 31 `[run]`, 4 `[belt]`, 1 `[supply]`, 1 `[stats]`);
* the filtered `[fruit]` stream against `logs/p32/D1_accept_pear.log`
  (376 lines): **374 identical, 2 differ**, and both are the *output-belt
  clearance print lines* (line 13/15: the pear instance scale prints 1.06 / 89 mm
  in the P32 record and 1.07 / 90 mm now - the print-only variant AGENTS §1
  already names for that record). **No `[task]`, `[motion]`, `[run]` or `[belt]`
  line differs**, so the physics stream is byte-identical;
* class census: **6/10, the same ten rows** (left peach cnp, left peach cnp,
  left kiwi cnp, left orange no-grasp, then six right/left placements with the
  same `N=` and `sim=` in every row);
* the motion gate: `fingerprint: matches configs/motion_reference.json`
  (`25ade92b`), exit 1 on the **rate only** (6/10 vs the 0.75 dynamic floor -
  the expected P32 branch, `logs/p40/p2/10_gate_sub1.txt`);
* run (b) is gated for completeness and **passes**: 8/10, every descent inside
  budget (worst `|v|max` 0.115 vs 0.160-0.161), worst cone 1.22x reported
  (`11_gate_sub4.txt`); against the shipped reference it reads
  `fingerprint: DIFFERS` (`12_gate_sub4_fp.txt`), which is what a physics-rate
  change is expected to do. Its 8/10 is **a different attractor** (480 Hz is a
  different physics setting, not an instrument state) and is *not* compared with
  6/10.

## 6. The friction margins, re-derived with the measured force

`GRIP_CENSUS` §3 capacity is `mu_eff x N_total` with `N_total` = the two-face
sum, which is exactly what the tactile reads (§1-§3). Nothing doubles.

Demand (unchanged): 1.04 N static (orange), 1.66 N at the measured 5.83 m/s^2
following-error transient.

| `mu_eff` | capacity @ **4.42 N** (shipped) | margin over 1.66 N | capacity @ **9.95 N** (480 Hz) | margin over 1.66 N |
|---|---|---|---|---|
| **0.45** (`min` x apple/pear) | **1.99 N** | **1.20x** | **4.48 N** | **2.70x** |
| 1.05 | 4.64 | 2.80x | 10.45 | 6.29x |
| **1.20** (0.6 x 2.0, the profile's own) | **5.30** | **3.20x** | **11.94** | **7.19x** |
| 1.49 | 6.59 | 3.97x | 14.83 | 8.93x |
| 2.00 | 8.84 | 5.33x | 19.90 | 11.99x |

`GRIP_CENSUS` §4.4's "N for 2x / 5x" is a *demand* table and is unchanged
(`mu 0.45`: 7.4 / 18.4 N; `mu 1.20`: 2.8 / 6.9 N). Graded against what is now
measured:

* at `mu_eff` 0.45 the shipped line delivers **4.42 of the 7.38 N** the 2x target
  needs (**0.60x**) and **0.24x** of the 5x target; at 480 Hz it delivers
  **1.35x** of the 2x target and **0.54x** of the 5x;
* at `mu_eff` 1.20 the required normal force for a 5x margin is **6.92 N** and the
  line delivers **4.42 N** (**0.64x** of it), so 5x is out of reach even at the
  model's own mu; at 480 Hz **9.95 N clears it (1.44x)**. For the 2x target at
  `mu_eff` 1.20 the requirement is 2.77 N and both settings clear it
  (**1.60x / 3.60x**).

So the census's conclusion letter stands and sharpens: **the binding term is the
friction coefficient, and the worst-case fruit is under-margined at every
`mu_eff <= 1.2`** (1.20x / 3.20x shipped, 2.70x / 7.19x at 480 Hz, against a
2x target). What *changes* is where the normal force can come from: **not** from
more squeeze (measured inert twice: 20 mm of command, and the relief cap), and
**not** from the 10 N cap — **the *command* is at the 10 N cap on 40/40 contact
rows** (the authored law times a 3.9-7.6 mm error is 4-8 kN, so `Fsat` clips to
10 N every time; `EFFORT_READ` §3's `Fsat` column), **while the *delivered
reaction* is 22 % of it** (2.21 N/joint). So the cap is not a headroom anyone can
spend: the force is **not** limited by `maxForce`, it is limited by what the
drive/contact pair can transmit inside one timestep — and that is why the
**physics rate** is the lever: at 2.25x the force for 3.08x the wall.

## 7. What this does to the record

1. **`GRIP_CENSUS` §7's "the largest remaining unknown" is closed as *no
   scaling*.** The tactile is the joint's reaction to 0.1-0.5 %; §3's capacities
   and §4's margins stand; the sentence "if the 4.4 N read is a 0.44x scaling ...
   every margin doubles" is **withdrawn** (it does not).
2. **§2.5's premise is falsified**: a 1e6 N/m position drive stalled 4-8 mm past
   its target does *not* have to be at its 10 N cap - it carries 2.2 N. The
   "2.2x discrepancy" was never a discrepancy: it compared the tactile to a cap
   the drive never reaches.
3. **PREREG A1.1's stated ground ("the drive is at its 10 N/joint cap") does not
   hold**: the **command** is at the cap on 40/40 rows, the **delivered reaction**
   is 22 % (shipped) / 50 % (480 Hz) of it. A1 is executed as written -
   **G1 not run** - but if the post-freeze load phase is ever revived its
   premise must be re-registered against this reading, because "extra depth is
   inert" now has a *different* mechanism (a timestep-limited drive, not a
   saturated one).
4. **New, measured, not adopted**: `FRUIT_SUBSTEPS=4` is the first knob on this
   line that moves the delivered normal force (**+2.25x**, verified by two
   instruments), at **3.08x wall** and as a *global* physics setting. Its span
   cost is **+0.66 s/attempt** (`[stats]` 150.2 -> 156.8 s over 10 attempts —
   say *that*, not "+0.90 s" and not "+4 %"). It needs
   its own pre-registration, its own motion reference (it is a different
   attractor: 8/10 vs 6/10 and `fingerprint: DIFFERS` against `25ade92b`,
   `logs/p40/p2/12_gate_sub4_fp.txt`; that pre-P40 reference is archived at
   `logs/p40/motion_reference_single_pre_p40.json` — the shipped file was
   re-recorded on a different branch in phase 4, so a sub-4 log must be gated
   against the archive, never against the current `configs/motion_reference.json`)
   and a check of the known
   480 Hz side effects (p11b: escape speed -6 %, displacement -10 %).
5. **Honest limit**: the pair `tact` vs `proj` rules out a *sensor-only* scaling
   (the hypothesis under test). It cannot rule out a *common-mode* error in the
   solver's force accounting, and no instrument in this build can -
   `logs/p11b` §6.3: the fruit-side contact view is invalid (`F_fruit` reads 0).

## 8. Reproduction

```bash
RUN_LIMIT=1800 scripts/154_claim_run.sh logs/p40/p2/effort_sub1.log \
    FRUIT_GRIP_EFFORT=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10 SEED=5 \
    scripts/run.sh scripts/20_pick_place.py
RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p40/p2/effort_sub4.log \
    FRUIT_GRIP_EFFORT=1 FRUIT_MOTION_REPORT=1 FRUIT_SUBSTEPS=4 ATTEMPTS=10 SEED=5 \
    scripts/run.sh scripts/20_pick_place.py
python3 logs/p40/p2/effort_table.py > logs/p40/p2/effort_table.txt
grep "\[fruit\]" logs/p40/p2/effort_sub1.log | grep -v "\[effort\]" \
    | diff - <(grep "\[fruit\]" logs/p32/D1_accept_pear.log) | grep -c '^[<>]'   # 4
```

Pins: `src/fruit_sorting/tasks.py` **34275f077fe18ce1acb2c0f760e57734**,
`src/fruit_sorting/rl_env.py` **e137eb59311ef49af43950ad29553467**,
`configs/motion_reference.json` **25ade92b** (untouched), HEAD `1790b87`.
Evidence: `logs/p40/p2/{effort_sub1.log,effort_sub4.log,effort_table.txt,effort_table.py,10_gate_sub1.txt,11_gate_sub4.txt,12_gate_sub4_fp.txt,smoke_effort.log,smoke2_effort.log,00_tree_pins.txt}`.
