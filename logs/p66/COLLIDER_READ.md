# P66 phase 1b - the static read of the authored finger-tip collider prims (S vs F1)

**VERDICT (first line): the read exists, it needs no physics, and the arithmetic
holds.** `S` (`FRUIT_FINGER_TIP_DELTA=0`) authors a **33.261 x 61.000 x 84.902 mm**
box; `F1` (`-0.004`) authors **33.261 x 61.000 x 80.902 mm**; the long dimension
differs by **4.000 mm**, the tilt of the box's long axis from the vertical at the
authored pose is **theta = 0.0000 deg**, and **`4*cos(theta) = 4.0000 mm`** - the
identity holds to **< 0.001 mm** on all four finger links, in both the box's own long
axis and the vertical (world-z) reading. The proximal plane does not move
(`941.301 mm` in both arms) and the distal plane rises exactly `4.000 mm`
(`856.399 -> 860.399 mm`). The build print reproduces P39's own
(`long 84.9 -> 80.9 mm`, `distal plane 80.5 -> 76.5 mm`).

Written 2026-10-30 on HEAD `2331733`. **No `src/` edit, no `configs/` edit, no default
change, no commit**; and unlike P39's `47` probe, **no attempt loop, no jam and no
physics step**.

---

## 1. Why this instrument, and why it needs a stage

P39's registered N4 used `scripts/47_robot_collision.py` - a straight `-0.35 m` z
descent that was supposed to seat the plate's distal plane on the belt. It **jammed
laterally** (0.13-0.17 m of x, 0.16-0.18 m of y for 0.03-0.06 m of z, and arm C ended
90 deg rotated against S/F1), and it printed **no tool axis**, so `delta*cos(theta)` had
no measured `theta`. Amendment A3 therefore withdrew the belt-clearance claim to
*untested* and named the valid instrument: "a **static-pose read of the authored
collider prims** (`S - F1` must differ by `4*cos(theta)`), with no attempt loop and no
jam" (`logs/p39/PREREG.md` A3.1, `logs/p39/p3/RESULT.md` §10.1.3).

**This file is that instrument.** The box prims do not exist in any USD file - they are
authored by `scene._author_finger_tip_delta` -> `_author_flat_face`
(`src/fruit_sorting/scene.py:1297/1332`) at **build** time, at
`{finger link}/contact_faces/tip_delta`, as a `UsdGeom.Cube` with
`size = 1` and `scale = (thick, width, length)`. So a stage is required, but **not a
simulation**:

* the build is **`parts=("robot",)`** - the smallest that contains the fingers (there is
  no finger-only asset: the hand is a subtree of
  `assets/openarm_flat/openarm_flat_deinst.usda`), and it is the same code path that
  authored the boxes in the P39 batch;
* **`scene.start()` is never called**: no physics scene step, no `Articulation`, no
  attempt, no belt, no contact. The read is off the **authored** transforms
  (`ComputeLocalToWorldTransform` at `Usd.TimeCode(0)`);
* with `parts=("robot",)` the two entry gates still run, so a broken finger-collider
  build cannot masquerade as a measurement (`assert_finger_colliders`).

**Accessors, not matrix indexing.** `Gf.Matrix4d` is read through
`ExtractTranslation()` / `ExtractRotationQuat()` and points through
`matrix.Transform(Gf.Vec3d(...))`. Nested `matrix[r][c]` indexing silently transposed
the matrix in this build, which drops exactly the translation column: the first pass
read a world AABB centred on the origin and a `7.2 mm` vertical span instead of
`84.9 mm`. Every number below comes from the accessor path and is cross-checked
against the build print's authored `long`/`distal plane`.

## 2. The two boxes (all four finger links, identical values)

| link | face (mm) | mid (mm) | **long (mm)** | theta (deg) | span_z (mm) | d_long | d_span_z | 4*cos(theta) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `openarm_left_left_finger` | 33.261 | 61.000 | **84.902 -> 80.902** | 0.0000 | 84.902 -> 80.902 | **4.000** | **4.000** | **4.000** |
| `openarm_left_right_finger` | 33.261 | 61.000 | 84.902 -> 80.902 | 0.0000 | 84.902 -> 80.902 | 4.000 | 4.000 | 4.000 |
| `openarm_right_left_finger` | 33.261 | 61.000 | 84.902 -> 80.902 | 0.0000 | 84.902 -> 80.902 | 4.000 | 4.000 | 4.000 |
| `openarm_right_right_finger` | 33.261 | 61.000 | 84.902 -> 80.902 | 0.0000 | 84.902 -> 80.902 | 4.000 | 4.000 | 4.000 |

* **The two boxes differ only in the long axis**: face `33.261 mm` and mid
  `61.000 mm` are bit-identical between S and F1, so the delta is purely axial.
* **The proximal plane is fixed**: `proximal_world_z = 941.301 mm` in **both** arms
  (to 0.001 mm) - exactly the design (`origin` is placed at `bounds[2]`, the plate's
  proximal end; only the distal plane moves).
* **The distal plane moves `+4.000 mm`**: `856.399 -> 860.399 mm`.
* **Exactly one collider is enabled per finger link** (`1/3` collision prims: the box
  is the only enabled one; the visual mesh and the asset's convex-decomposition proxy
  are the two disabled) - i.e. the re-author really replaced the plate, it did not add
  a second collider.
* `long_world` is `(0, 0, -1)` on all four links at the authored pose: the fingers hang
  **straight down** in the rest pose, which is why `theta = 0.0000 deg` here.

## 3. The angle, and which reading the formula names

`theta` is the tilt of the box's long axis from the vertical. The 4 mm shift is along
the **plate's long axis**, so it decomposes as

```
vertical (world z) shift   = 4 * cos(theta)      <- what bears on belt clearance
along-belt horizontal shift = 4 * sin(theta)     <- what bears on the lip/reach
```

Two readings, both checked here:

1. **the box's own long dimension**: `84.902 - 80.902 = 4.000 mm` - the projection
   factor is **1** by construction there (the dimension *is* along the long axis);
2. **the vertical (world-z) span**: `84.902 - 80.902 = 4.000 mm` and
   `4*cos(0.0000 deg) = 4.0000 mm` - **the register's formula is this one**, and it
   holds to `< 0.001 mm` on all four links.

So `S - F1 = 4*cos(theta)` is **confirmed at the authored pose**, where `theta = 0`.

**What `theta` does at other poses is arithmetic on measured attitudes, not a second
read** (the box is rigid in the link frame, so it rotates with the link):

| theta | `4*cos(theta)` vertical | `4*sin(theta)` along-belt | attitude it belongs to |
| --- | --- | --- | --- |
| 0.0 deg | 4.000 mm | 0.000 mm | the authored rest pose (this read); also `T0`'s vertical finger |
| 24.6 deg | **3.637 mm** | 1.665 mm | P63's measured left **carry** drift (median of the failing legs) |
| 85.3 deg | **0.328 mm** | 3.987 mm | the **shipped station** tool axis: 5.4 deg *below horizontal*, i.e. 85.3 deg from vertical (`|t_z| = 0.0819`, P62 §1; P62's measured `approach_axis` `|z| = 0.095` gives 0.380 mm) |

The point of that table: the 4 mm tip shortening is **4 mm of *belt* clearance only when
the finger is vertical**. At the shipped station attitude it is ~0.33-0.38 mm of
vertical clearance (P62's measured `|approach_z| = 0.095` gives 0.380 mm) and at the
measured carry tilt ~3.64 mm - which is the "lip vs clearance" 1:1 trade P39's
`P1_READ.md` §2 states, projected into the world frame.

## 4. What it does and does not settle

**Settles.** The geometry change is **authored and exact**: `-4 mm` on the distal plane,
`+4 mm` on the world-z span at `theta = 0`, on all four links, with the proximal plane
and the other two dimensions untouched, and with the plate's mesh colliders gone
(`1/3` enabled). The arithmetic A3 asked for is **computable and it holds** - the
`47` probe's missing `theta` is not needed here because `theta` is read off the same
prims.

**Does not settle.** This is **not** a belt-clearance measurement: the belt is not in
the scene and no contact is made, so "4 mm of tip clearance" remains a *geometric
consequence* of `delta*cos(theta)`, not a measured stop. P39's A3 withdrawal stands for
any *hardware/clearance* claim that needs the belt (the `47`-style instrument is still
broken); what changes is that the **precondition** A3 named is now satisfied rather than
untested. Also not tested here: `F2` (`+4 mm`, owner-gated), the `+1.00 mm` jaw-floor
difference (`47`'s rotated-jam artifact), and the visual mesh (untouched by design, so
the rendered image is unchanged).

## 5. Cost and reproduce

Two headless builds, **18-19 s each** (`16:25:21 -> 16:25:58` for both), no physics.

```bash
FRUIT_FINGER_TIP_DELTA=0      scripts/run.sh logs/p66/collider_read.py   # arm S
FRUIT_FINGER_TIP_DELTA=-0.004 scripts/run.sh logs/p66/collider_read.py   # arm F1
python3 logs/p66/collider_report.py                                      # 24/24 checks
```

**Pins:** `logs/p66/collider_read.py` **8d7cb9c6**, `logs/p66/collider_report.py`
**f591c747**, `collider_read_0.json` **fecf2129**, `collider_read_m0p004.json**
**ab24b980**, `collider_S.log` **fe53dff8**, `collider_F1.log` **0cc3bb45**,
`collider_report.txt` **4c290208**; HEAD **2331733**; `scene.py` `27e3d64a`
(**untouched** - this phase only read it). **`logs/` is gitignored**: `git add -f` at
the close-out.
