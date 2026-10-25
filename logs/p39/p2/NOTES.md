# P39 phase 2 — the implementations (evidence)

2026-10-25, tree `e061d94` + the phase-2 working-tree diff (no commit, no
`configs/` change, no shipped default changed). Pre-registration:
`logs/p39/PREREG.md` + **Amendment A1** (arms C / S / F1; W withdrawn).

## 1. What was added (both default off)

| knob | file | gate |
| --- | --- | --- |
| `FRUIT_FINGER_TIP_DELTA=<m>` (signed) | `src/fruit_sorting/scene.py` | **presence**: `tip_delta_text = os.environ.get("FRUIT_FINGER_TIP_DELTA"); if tip_delta_text is not None:` (`os.environ.get` with no default returns `None` only when the variable is absent) |
| `FRUIT_CARRY_ATTITUDE=1` | `src/fruit_sorting/tasks.py` | value: `attitude = os.environ.get("FRUIT_CARRY_ATTITUDE", "0") == "1"`, read once per `_carry` leg |

`rl_env.py` is a **metadata-only** follow (`TASKS_MD5` -> the new `tasks.py`
md5); no behaviour change on the direct/policy path.

`scene.py` symbols used (the phase-1 text's `PLATE_MID` does not exist as a
symbol - the extents come from the build's own readout):

* `_finger_face_frame` (line ~207) -> `e_face, e_mid, e_long, face_coord,
  mid_coord, tip_coord, extents=(33.3, 61.0, 84.9), bounds=(mid_lo, mid_hi,
  long_lo, long_hi)`; the box is `origin = e_face*face_coord +
  e_mid*mid_coord + e_long*long_lo`, `length = tip_coord + delta - long_lo`,
  `width = extents[1]` (61.0 mm), `thick = extents[0]` (33.3 mm);
* `_author_flat_face` (line ~861) authors it (same face plane, same material
  path: `FRUIT_FINGER_MU` / `_COMPLIANCE` / `_CONTACT_DAMPING`);
* `_disable_link_colliders` (line ~723) is **not** called (it disables every
  CollisionAPI under a link). A new `_disable_finger_plate_colliders` disables
  only prims inside `<link>/visuals` and `<link>/collisions`, and returns any
  foreign collider path **left enabled**; `_link_collider_counts` reads the
  before/after state.

Palm proof: in the asset the palm is a **sibling** link
(`assets/openarm_flat/openarm_flat_deinst.usda:5603` `openarm_left_hand`; the
right hand is its analogue), not a descendant of a finger link; the runtime
print reads both palms' CollisionAPI counts before and after (0 prims each,
unchanged) and the per-link enabled count after authoring is 1 (the box).

## 2. Offline

* `scripts/selfcheck.sh` -> **PASS: 0 failures, 1 skipped** (`motion budgets`
  skips without a run log).
* `python3 scripts/96_motion_check.py` -> **all motion checks passed**.
* Presence-gate byte-identity, **measured**: `a0_prechange.log` (the tree with
  the diff stashed, i.e. `e061d94`) and `a_unset.log` (the final tree, knob
  unset) are **identical on all 92 `[fruit]` lines** (md5 `a713575c51d691870
  75a4940860cebae` both).

## 3. Smokes (`scripts/154_claim_run.sh`, `ATTEMPTS=2`, `RUN_LIMIT=1500`)

| log | env | result |
| --- | --- | --- |
| `a0_prechange.log` | (diff stashed, tree `e061d94`) | 0/2, exit 0 - the presence-gate control |
| `a_unset.log` | - | 0/2, exit 0, **no** new print; 92/92 `[fruit]` identical to `a0` |
| `b_delta0.log` | `FRUIT_FINGER_TIP_DELTA=0` | build print (box 33.3/61.0/84.9, distal 80.5), 2/2, exit 0 |
| `b2_delta0_final.log` | same, on the **final** `scene.py` (`ed78374a`) | identical print and outcomes (`b` superseded by `b2`) |
| `c2_delta-4mm_attitude.log` | `=-0.004` + `FRUIT_CARRY_ATTITUDE=1` | box long 80.9, distal **76.5**, 4 `[attitude]` lines, 2/2, exit 0; **98 `[fruit]` lines = 93 physics/task + 4 `[attitude]` + 1 build print** (see A2.2) |
| `c_delta-4mm_attitude.log` | same, before a print-wording fix | superseded by `c2` (same numbers, earlier wording) |

Final tree md5: `scene.py` **ed78374a**, `tasks.py` **e77c985b**,
`rl_env.py` **6946fb9e** (metadata-only `TASKS_MD5` follow).

The build print (verbatim, `delta = -4 mm`):

```
finger tip delta -4.0 mm: 4/4 finger links re-authored, shipped plate colliders
disabled=8 (visuals+collisions), colliders left enabled outside the plate=0; box
face/mid/long=33.3/61.0/80.9 mm (closing x across x down the finger), face
plane=5.8 mm, distal plane=76.5 mm (shipped tip 80.5 mm), enabled colliders per
link after=1 (contact_faces/tip_delta), palms unchanged: openarm_left_hand=0
prims, openarm_right_hand=0 prims
```

`[attitude]` (verbatim in `c2_delta-4mm_attitude.log:409-441`, wrapped here):

```
[attitude] left grasp_lift: tilt=31.6deg from world -Z, pad_fruit_dz=+51.0mm
(world +Z, + = pads above the fruit centre), lip=+11.0mm (vertical tip drop
+62.0mm at this tilt, minus dz)
[attitude] left place0:     tilt=96.2deg, dz=-17.5mm, lip=+9.6mm (drop -7.9mm)
[attitude] right grasp_lift: tilt=45.0deg, dz=+47.1mm, lip=+4.3mm (drop +51.4mm)
[attitude] right place1:     tilt=92.4deg, dz=-1.7mm,  lip=-1.4mm (drop -3.0mm)
```

## 4. Risks carried into phase 3

1. The replacement box is the plate's **AABB**, not its convex hull: arm S is
   "box == AABB", so a C-vs-S difference includes the mesh-vs-AABB step. F1-vs-S
   is the clean `delta` comparison.
2. Whether PhysX honours `collisionEnabled=false` on the asset's `collisions/`
   collection root is a **USD-level** claim (proved by the build print) and not a
   physics-level one. A surviving double surface would read as "`delta` has no
   effect" and is exactly what PREREG N4/O3 (the `47` probe's jaw floor shifted
   by `delta*cos(theta)` vs S) detects.
3. The visual mesh is untouched, so the rendered image still shows the shipped
   tip: the finger arms are scripted-line only (P1_READ §2.4); never run them
   behind the policy evaluator.
4. `FRUIT_FINGER_TIP_DELTA` is refused (with a print) when combined with
   `FRUIT_FINGER_FACE`, `FRUIT_FINGER_PADS`, `FRUIT_FINGER_SOFT_PAD` or
   `FRUIT_FINGER_SCOOP`, and `= ""` (present but empty) is a FATAL parse rather
   than a silent fallback to the shipped hand.
5. `[attitude]`'s `lip` is model-derived (`FINGER_TIP_BELOW_JAW` **80.5 mm** +
   `delta`, corrected in A2.3 below) plus the corner term; only `tilt`, the tool
   axis and `pad_fruit_dz` are free of the model. On the place legs
   `tilt > 90 deg`, so the tip's vertical drop is negative there (printed).
6. `scripts/selfcheck.sh` rewrites the tracked `logs/p36/offline_obs_diff.txt`
   with the current `rl_env.py` md5; it is restored here so this tree's status is
   the three `src/` files only. Phase 3 will see it dirty again for the same
   (pre-existing) reason.

## 5. Amendment A2 (2026-10-25) — parse hardening, print hygiene, the corrected tip constant

Three code changes on the phase-2 diff (A2.1-A2.3 of `logs/p39/PREREG.md`);
A2.4-A2.7 are text only and untouched. No shipped default changed: both knobs
stay **default off**. Final pins: `scene.py` **988985ef**, `tasks.py`
**112d2cb1**, `rl_env.py` **238e90a4** (the `TASKS_MD5` metadata-only follow
`e77c985b` -> `112d2cb1`; `scripts/selfcheck.sh`'s *tasks.py pin* leg PASSes).
Run-time pins: `scene.py` = the final `988985ef` for all three runs; `tasks.py`
= `d50f4795` during the runs and `112d2cb1` after a **docstring-only** reflow of
the `_carry_attitude` paragraph (no code, no print string, no constant changed;
the pass criterion is that the run log's `[attitude]` strings are unchanged).

### A2.1 — the parse refuses non-finite and absurd values

`build()`'s presence-gated block now sends **a bad parse and a non-finite or
`|delta| > 0.05` value to the same FATAL path** (`say(...)` + `os._exit(1)`):

```
[fruit] FATAL: FRUIT_FINGER_TIP_DELTA='nan' must be a finite tip delta in [-0.05, 0.05] m
[fruit] FATAL: FRUIT_FINGER_TIP_DELTA='1.0' must be a finite tip delta in [-0.05, 0.05] m
```

Measured, one claimed 1-attempt run each (`a2_fatal_nan.log`,
`a2_fatal_1m.log`, `RUN_LIMIT=900`): **exit 1 and exit 1**, 16 s and 15 s wall,
both die in `build()` before `scene built` (21 `[fruit]` lines, 0 `[attitude]`).
`nan` needed the gate for a second reason: NaN compares False against the
downstream `length < 0.005` guard, so it would have authored an undefined plate;
`1.0` would have authored a 1 m plate. `float("")` still takes the same path
(ValueError -> NaN). The accepted value is echoed in the build print.

### A2.2 — the build print is a plain `[p39]` print

`say()` prefixes `[fruit]` unconditionally (`common.py:28-30`), so the phase-2
build print was counted as physics. It is now a **plain `print(..., flush=True)`**:

```
[p39] finger tip delta accepted -4.0 mm (FRUIT_FINGER_TIP_DELTA='-0.004'): 4/4 finger links re-authored, ... (rest unchanged)
```

`[attitude]` rows **keep** the `[fruit]` prefix (unchanged format family, A2.3
below adds fields). **The exact filter** for the `[fruit]` census on any
knob-set run:

```
grep '\[fruit\]' <log> | grep -v '\[attitude\]'
```

On the phase-2 logs the old build print is additionally filtered by
`grep -v 'finger tip delta'`; from A2.2 on, `[p39]` rows are not `[fruit]` at all.

Raw vs filtered counts, every run this amendment touched:

| log | scheme | raw `[fruit]` | `[attitude]` | filtered | note |
| --- | --- | --- | --- | --- | --- |
| `a_unset.log` (phase 2) | 0/2 | 92 | 0 | 92 | different branch: both attempts re-took the left peach |
| `c2_delta-4mm_attitude.log` (phase 2) | 2/2 | 98 | 4 | **93** | 98 = 93 physics/task + 4 `[attitude]` + 1 build print (pre-A2.2) |
| `a2_smoke_delta-4mm_attitude.log` (A2.2) | 2/2 | **97** | 4 | **93** | the build print left the prefix; filtered stream **93/93 byte-identical to `c2`'s filtered stream** |

The smoke's raw `97` is **93 physics/task + 4 `[attitude]`**; the brief's
expectation of "raw = `a_unset`'s 92" cannot hold while `[attitude]` rows keep
`[fruit]` (92 + 4 = 96) *and* is a different outcome branch. The load-bearing
facts are (a) the filtered stream is **93/93 identical to `c2`** - the same
scenario in phase 2, same 2/2 - so A2.2 moved **zero** physics rows, and (b) the
only `[fruit]`-count change against `c2` is the build print itself (98 -> 97).
The `92` vs `93` gap to `a_unset` is the branch, not the print: `a_unset` is
0/2 with **both** attempts the left peach (it re-took the same fruit), the smoke
is 2/2 on a left peach + a right strawberry. Multiset difference of the
normalised rows: the smoke gains two `[task] place low` rows and loses one
`[task] dynamic close` row (the second attempt never entered the dynamic-close
path) - net +1. `a2_smoke`: `[p39]` rows = 1, `[fruit] [p39]` rows = 0.

### A2.3 — `FINGER_TIP_BELOW_JAW` 76.8 -> 80.5 mm, and the richer `[attitude]` line

The constant is now `0.0805` with its provenance in the comment: the shipped
collider **is** the visual mesh (convex hull), and the build print reads its
distal plane at **80.5 mm** (`_finger_face_frame`'s `tip_coord`); `logs/166`'s
**76.8 mm** is a **contact stop** (penetration + rest offset, ~3.7 mm short) and
stays in the comment as a documented stop, not geometry. The phase-2 line
under-estimated the lip by `3.7 * cos(tilt)` = **2.6-3.2 mm** (ordering across
arms survives, magnitude does not).

The line is still **one line, one TCP read per leg**; it now carries `tip=`
(the constant + delta actually used), the tool axis as three world components
(so the corner's azimuth relative to the belt is derivable: jaws close along
world X, travel along -Y) and **both** candidate corner drops
(`16.65 * sin(tilt)` = half the 33.3 mm closing-direction thickness,
`30.5 * sin(tilt)` = half the 61.0 mm along-belt width). Verbatim, smoke:

```
[fruit] [attitude] left grasp_lift: tilt=31.6deg from world -Z, tool_axis=(+0.2231,-0.4735,-0.8520) (TCP col 2, world; jaws close along X, travel along -Y), tip=+76.5mm (base 80.5 + delta -4.0), pad_fruit_dz=+51.0mm (world +Z, + = pads above the fruit centre), lip=+14.2mm (vertical tip drop +65.2mm at this tilt, minus dz), corner drop 16.65*sin(tilt)=+8.7mm / 30.5*sin(tilt)=+16.0mm
[fruit] [attitude] left place0: tilt=96.2deg from world -Z, tool_axis=(+0.7559,+0.6456,+0.1087) (...), tip=+76.5mm (base 80.5 + delta -4.0), pad_fruit_dz=-17.5mm (...), lip=+9.2mm (vertical tip drop -8.3mm at this tilt, minus dz), corner drop 16.65*sin(tilt)=+16.6mm / 30.5*sin(tilt)=+30.3mm
[fruit] [attitude] right grasp_lift: tilt=45.0deg from world -Z, tool_axis=(+0.7076,-0.0008,-0.7066) (...), tip=+76.5mm, pad_fruit_dz=+47.1mm, lip=+6.9mm (drop +54.1mm), corner drop +11.8mm / +21.6mm
[fruit] [attitude] right place1: tilt=92.4deg from world -Z, tool_axis=(+0.7637,-0.6442,+0.0415) (...), tip=+76.5mm, pad_fruit_dz=-1.7mm, lip=-1.5mm (drop -3.2mm), corner drop +16.6mm / +30.5mm
```

The constant's effect, same scenario as `c2`: `lip` on the left `grasp_lift`
**+11.0 -> +14.2 mm** (delta 3.2 = `3.7 * cos(31.6)`); the two place legs move
0.1-0.4 mm because their vertical drop is already tiny (`tilt > 90 deg`).
The tilt values are unchanged (`c2` -> this run), so only the derived columns
moved. The corner term at the measured 31-45 deg is 8.7-21.6 mm, larger than the
whole 4 mm `delta` budget - the A2.3/A2.4 reading.

Nothing else changed: `scripts/selfcheck.sh` **PASS, 0 failures, 1 skipped**
(`motion budgets`, no run log), and `logs/p36/offline_obs_diff.txt` (which the
check rewrites with `rl_env.py`'s md5) is restored, so the tree's status is the
three `src/` files.
