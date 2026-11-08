# P131 results - the over-closure is the **law**, not the drive; fixing it exposes the V-block

**VERDICT (first line).**  The over-closure is the **aperture law**, not the
force-capped drive: on the freeze-off cells the commanded aperture equals the
two-jaw ramp's load target `0.97 x min(radial, axial)` (the fruit's **height**)
on **38/40** rows (`aper/ramp` p50 **0.998**), and the measured pad span is at
or above the command on every row (`sep - aper` p10 **+0.00 mm**).  P130's
**22/40** shrinks to **7/40** once the two metric artefacts are removed (the
strawberry's class `dia` is its height, `R/dia = 0.792`; a ring that **missed**
the fruit also reads `aper < dia - 4`).  The new default-off law variant
(`FRUIT_CAGE_APERTURE=pad_axes`) **removes the over-closure exactly** (7/40 ->
**0/40**, p = **0.0117**) - but it does **not** raise the clean enclosure
(13/40 control -> **11/40**, p = 0.81) and the **V-block rises 3/40 -> 13/40**
(p = 0.0103), because the ring arrives **3.5-5.6 mm** off-centre and the correct
3 % squeeze cannot load the far pads (P110's `delta < 0.6 mm` requirement).  The
placed count is a branch (20/40 -> 12/40, p = 0.11; per seed 10/10 -> 3/9) and
is **not a rate**.  `max_extent` is a measured negative: **9/20** rows have
`ext > R + 2 mm` (pear, kiwi **and the strawberry**, whose height is its largest
axis) and **0/9** place.  **Nothing is adopted**: the default stays `shipped`
(the expression bit for bit), `configs/` is untouched.

## 0. Admissibility

| check | result |
|---|---|
| `scripts/selfcheck.sh` | **PASS (0 failures, 1 skipped)** with the new `P131 cage aperture law` leg |
| `scripts/accept.sh` (every knob unset) | **8/10, 9.0 s/attempt, `fingerprint: matches configs/motion_reference.json`, `190: PASS`** |
| its `[fruit]` stream vs `logs/p127/accept_restored.log` | **421/421 identical** (md5 `57595eeb9c3de92043b47c36cd866024` both) |
| `scripts/106_index_audit.py` / `107_collect_merge_test.py` | **OK** / **PASS (21 checks)** |
| `bash logs/p131/gates.sh` | **rc = 1**, on the P5 landing letter only (below) |

## 1. The census (`census.py` -> `census.txt`, offline, before the cells)

**The command is the two-jaw ramp, not the ring's law.**  `ramp = 0.97 x
min(R, A)`, `law = 0.98 x R`; on the 80 shipped-law freeze-off rows (P130's
`F5`/`F6` + P131's `U5`/`U6`) **75/80** read `aper/ramp` in **[0.96, 1.02]**
(p50 **0.998**).  The freeze-on controls read 1.09-1.66 (the first-contact
freeze holds an aperture too wide, P129's mechanism).

**The two metric corrections, both pre-registered (`PREREG.md` section 1):**

* **`dia` is not the width for every class.**  The strawberry's class diameter
  is its height: `R/dia = 0.792`, so `aper/dia` p50 **0.773** while `aper/R`
  p50 **0.976**.  Five of P130's 22 are this.
* **A miss is not an over-closure.**  A ring whose payload sits `off > 15 mm`
  from its axis at the close's end reads `aper < dia - 4` with no fruit between
  its pads.  Every seated row reads `off <= 10.1 mm`, every miss `>= 92 mm`.

The corrected split of P130's freeze-off cells is **clean 11/40, over 7/40,
miss 15/40, vblock 4/40, jam 1/40**.  The 7 over-closures are **tomato 2,
peach 2, apple 3**, all flat fruit, `aper/R` p50 **0.874** (12.6 % inside the
width), all with the delivered force at the cap (4.5-4.9 N/pad) - and **6 of
the 7 placed**.  The over-closure is a **geometry defect**, not the dominant
*failure*: the 15 misses are.

**The drive test.**  The pads are position drives; the measured span cannot be
pulled through its target.  The record's `sep_end - aper` p10 is **+0.0 mm** on
the freeze-off rows, and the P131 cells' close-time `sep` gives `sep - aper`
p10 **+0.00 / -0.01 mm**.  No cell has a drive overshoot.  The over-closure rows'
`F` is at the 4.9 N/pad cap, not above it on a seated row (the 128-660 N rows
are impacts on misses).

## 2. The build (`cage_hand.py`, `tasks.py`; default off)

`FRUIT_CAGE_APERTURE` = `shipped` (default) | `max_extent` | `pad_axes`:

* `shipped` - the P107 expression **bit for bit** (the selfcheck recomputes it
  independently on five species);
* `max_extent` - the mesh's largest axis (a screen);
* `pad_axes` - the max over the ring's **own four pad axes** in the cage base
  frame (the P112 analogue; equal to the shipped axes for a top-down hand, the
  pads' own axes for a tilted one - pinned by the selfcheck).

For a radial hand with a variant armed, the close's load target is the hand's
extent at `FRUIT_GRIPPER_SQUEEZE` (0.98) and the two-jaw **2.5 mm interference
floor** is dropped (the ring's drive reaches its cap at `cap/k` = 0.049 mm; the
floor is 8.5 % of a 29 mm berry).  Unset keeps the shipped `min_extent` target
and the floor on every hand.  The `[cage]` row gains `law= ext= deep= sep=` (the
measured span at the flush; the probe is default off, and the acceptance proves
the shipped path inert at 421/421).

## 3. The cells

`FRUIT_GRIPPER_KIND=cage4 FRUIT_DYNAMIC_CLOSE_FREEZE=0`, the scripted single
arm, the shipped supply **package** exactly as P130's `F5`/`F6` (the `[biarm]`
default is refused by the cage, but its dense wave + balanced mix is what the
supply gets), 20 attempts, the P108/P110 instrumentation on both arms.
Same-tree same-seed controls: `U5`/`U6` (unset).  The control is **fresh** -
D1 explains why.

| cell | law | seed | placed | diverted | clean | over | vblock | miss | jam | n/c | P110 c/j/cr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `F5` (P130) | shipped | 5 | 9/20 | 2 | 5 | 3 | 3 | 7 | 1 | 0 | 2/1/7 |
| `F6` (P130) | shipped | 6 | 10/20 | 2 | 6 | 4 | 1 | 8 | 0 | 0 | 6/2/4 |
| **`U5`** | shipped | 5 | **10/20** | 1 | 7 | 3 | 2 | 6 | 1 | 0 | 4/2/8 |
| **`U6`** | shipped | 6 | **10/20** | 2 | 6 | 4 | 1 | 8 | 0 | 0 | 6/2/4 |
| **`P5`** | `pad_axes` | 5 | **3/20** | 6 | 4 | **0** | 7 | 8 | 0 | 1 | 3/0/2 |
| **`P6`** | `pad_axes` | 6 | **9/20** | 4 | 7 | **0** | 6 | 5 | 0 | 1 | 7/2/1 |
| `M5` | `max_extent` | 5 | 3/20 | 6 | 3 | **0** | 7 | 8 | 0 | 1 | 3/1/1 |

* **The over-closure is removed**: `pad_axes` **0/40** against the control
  **7/40**, exact Fisher **p = 0.0117** (per cell 3, 4 -> 0, 0).  The rows that
  were over-closed now read `aper/R = 0.96-0.99` and `sep >= aper`: e.g. a
  62 mm tomato that closed at **50.7 mm** (0.818 R) closes at **59.8 mm**
  (0.965 R) with the drive at 61.3 mm; the 69-70 mm apples move 61.0-61.7 ->
  **68.0-68.2 mm**.  That is the law's mechanism, measured.
* **It does not convert the enclosure**: clean **13/40 -> 11/40** (p = 0.81);
  the **V-block rises 3/40 -> 13/40** (p = 0.0103) and the misses are flat
  (14 -> 13, p = 1.0).  The wider, correct target is not a centring mechanism:
  with `off0` p50 **3.6/3.5 mm** on the controls and **4.3/5.6 mm** on the
  treatments, the far pads stand off by `2 x delta` - P110's arithmetic
  (`delta < 0.01 d = 0.6 mm` for all four to reach).  The old 10-13 %
  over-closure was **masking** the V-block by driving every pad deep; the force
  was at the cap, so the ring "enclosed" violently and 6/7 of those attempts
  still placed.  The law fix is a **force/geometry correction, not a
  throughput lever**.
* **The placed count is a branch**: 20/40 -> 12/40 (p = 0.11), per seed 10 -> 3
  and 10 -> 9; the P5 draw also carries the cell's one 2.0 m ejection.  Do not
  quote it as a rate (P130's own freeze-off pair is one draw too).
* **`max_extent` is a negative screen**: **9/20** rows with `ext > R + 2 mm` -
  pear **4** (72.7-81.7 vs 61-68 mm), kiwi **2** (63.2 vs 56), **strawberry 3**
  (36.1 vs 29.3: its height is its largest axis) - and **0/9 placed**; the
  ring closes on air (`no-contact`/V-block).  A blind "close wider" is not the
  fix; the law has to be the width.

## 4. Guards

* **Crush** (`sep@loss - dia >= -15 mm`): **0/12, 0/10, 0/10, 0/10, 0/18,
  0/11, 0/19** legs.  The over-closure is a 4.9 N/pad-capped squeeze, not a
  force excursion; the 128-660 N rows are misses hitting the world.
* **Landing** (`on_belt` on every payload-present release): **9/9, 10/10,
  10/10, 10/10, 3/4, 9/9, 3/3**.  The one failure is **P5 attempt 4**, a 3.0 cm
  lychee held at 9.97 N (a 2-pad V-block) and flung **2.0 m**
  (`final=(-0.608,+2.536,0.013)`, `impact=-5.87 m/s`) during the place leg -
  the cage's closed loaded-slide/eject class, **not** a release-clock miss (the
  release block is the shipped one; the other four cells are 100 %).  Recorded
  as a guard-letter failure; `gates.sh` exits 1 on it (the P103 convention).
* **Descent budgets** (`105 --min-success-rate 0.0`, not re-tuned): **PASS on
  all five cells** - worst `|v|max` **0.130 / 0.144 / 0.138 / 0.130 / 0.131**
  against 0.160-0.162, lurch **0.039-0.065** against 0.291.  The `a_win5`
  warnings (2.2-4.8 vs 2) are the dynamic line's reported roughness.
* **No new failure-reason key**: the only note in any cell is the baseline
  `fruit did not follow the gripper` (the cage's eject class).
* **No-harm** (the acceptance above): 8/10, `fingerprint: matches`,
  **421/421** identical to `logs/p127/accept_restored.log`; the cage refuses a
  `CoopSession` by construction, so the shipped path cannot reach the variant.

## 5. Deviations

* **D1 - the pre-registered `U5 == F5` replay is not available: the cage cell
  is not bit-reproducible.**  Two identical unset runs (`SEED=5`, 20 attempts,
  the same tree and env) diverge at attempt 0: `at pick pose after 0.84 vs 0.86
  s`, the peach's `fruit_y 0.4832 vs 0.4812`.  The 4 dynamic pads on standalone
  prismatic joints in the dense wave sheet are a new mode (P39's `F1`
  precedent), so `F5`/`F6` are a **different branch** and the control is the
  fresh same-tree `U5`/`U6`.  The P130 records are quoted as pre-phase context.
  This also means every P131 count is one branch draw.
* **D2 - the pre-registered D2 bar was written against the P130 control's
  11/40.**  The fresh same-tree control is **13/40** (U5's clean 7 vs F5's 5);
  `pad_axes` is **11/40**: equal to the pinned number, **-2** against the fresh
  control, inside the control's own 5-7 per-cell spread.  Read as a **draw**
  (p = 0.81), not a gain.
* **D3 - a P130 by-product the logs expose: its rate comparison crosses two
  supplies.**  `F5`/`F6` were run with `FRUIT_BIARM` unset (the cage refuses the
  scheduler, one `[biarm] ... ignored` row, and the supply gets the two-line
  **wave + balanced** package); the P108 `B_s5`/`B_s6` "controls" were run with
  `FRUIT_BIARM=0` per `logs/p108/cells.sh` (the single-arm **scatter**, 50/30/20;
  `wave=off`, no `[biarm]` row).  So P130's 19/40 vs 6/32 confounds the freeze
  with the supply; the freeze's own same-supply effect is not in that record.
  P131's controls are same-scenario (wave on).
* **D4 - the P5 landing letter fails** (one place-leg ejection).  See guards.

## 6. The verdict, and what remains

**The law was the bug; the fix is real; the over-closure was not the binding
failure.**  The two-jaw `deep` target is the wrong law for a radial hand, and
`FRUIT_CAGE_APERTURE=pad_axes` corrects it exactly (0/40) with the drive
following every command.  But the same measurement shows what the over-closure
was hiding: the ring's arrival is **3.5-5.6 mm** off-axis, so at the correct
3 % squeeze only the near pads load (a V-block), and the clean enclosure and the
placed count do not improve.  **The remaining blocker is centring, not the
closure law**: P110's `delta < 0.6 mm`, or a workstation that presents the fruit
on the ring's axis (P107/P110's named terms).  `max_extent` is closed as a
negative.  `FRUIT_CAGE_APERTURE` stays **default `shipped`**; the measured arm
is `pad_axes` if the owner ever pairs it with a centring step.

**The transferable sentences**: (1) a radial hand's close target must be its
**own** stated extent, not the two-jaw `min_extent` - and the freeze-off cell
is what exposes the difference (the freeze-on cells freeze at first contact and
never run the ramp); (2) a metric that uses the class `dia` as the width is
wrong on the strawberry by 21 %, and a miss is not an over-closure - P130's
22/40 is **7/40**; (3) fixing a masking defect can expose the real one: the
over-closure was a 4-pad squeeze that hid an off-centre arrival, and removing it
turns 7 over-closures into 13 V-blocks.

## 7. Files and pins

`logs/p131/{METHOD.md,PREREG.md,PREREG.md5,census.py,census.txt,cells.sh,
run_p131.sh,p131_report.py,p131_report.txt,RESULTS.md,gates.sh}`, the cells
`{U_s5,U_s6,P_s5,P_s6,M_s5}.{log}`, `streamA.log`, `streamB.log`,
`accept_noharm.log`.

Pins: `cage_hand.py` **`0f56b2ff`** (`APERTURE_MODES`, `aperture_mode`, the two
law branches, the build row), `tasks.py` **`76dbfc6b`** (the `cage_law_armed`
route + the dropped floor + the `[cage]` fields), `rl_env.py` **`b11113fb`**
(the metadata-only `TASKS_MD5` = **`76dbfc6b`** follow),
`scripts/266_p131_cage_aperture_selftest.py` **`de1d28f6`**,
`scripts/selfcheck.sh` **`5dd45f91`**; `configs/motion_reference.json` = `..._twoline.json` =
**`30fb99f8`**, `..._single.json` = **`8952c320`** (all untouched); ckpt
`moe_v13s` `61da390a`.
