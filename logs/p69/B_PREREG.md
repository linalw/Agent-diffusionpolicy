# P69 phase B — the workstation/transfer pre-registration (the rail-crossing margin)

Written by the P69-B lane, **registration + arithmetic only**: no run, no `src/` or
`configs/` edit, no default change, nothing adopted. Every number below is either
the code's own expression (with the file/line) or a measurement already in
`logs/`; nothing here is new data.

The question: P66/P67/P68 left the low lift (`FRUIT_LIFT_DZ=-0.08`, lift end
1.370 m) as the only lever that fixes the left arm's carry rotation
(`drift_end` 25.1 -> 0.7 deg, left placed 0/25 -> 14/25 at N=5,
`logs/p66/P3_RESULTS.md`), and it **fails gate (a)**: the place transit then
crosses the output line's inner rail at **+0 mm (window) / +5 mm (centreline)**
against the record's **+33 mm** floor (`logs/p66/P4_RESULTS.md` §3), and the two
re-shapes tried since both cost more than they buy (the climb: +33..+54 on 6/9
held legs but 5/10 left place legs lost, `logs/p67/RESULTS.md`; the climb + the
wrist hold: 0/16 held, `logs/p68/RESULTS.md`). So: is there a *workstation or
transfer* change that restores the floor **without spending the carry**?

---

## 0. Verdict

**Three options reach the crossing and one does not. Ranked by crossing-gain per
unit of the thing that costs (mm of clearance per mm of the lever, then what
else moves):**

| rank | option | gain | dose for +33 | moves | carry exposure | blast radius |
|---|---|---|---|---|---|---|
| **1** | **flush the inner output rail** (inner-only height 0.05 -> **0.015**; zero-code equivalent `FRUIT_OUTPUT_RAIL_HEIGHT=0.015`, which also flushes the outer box) | **1.00 mm/mm** (the obstacle drops, the trajectory is untouched) | **34 mm needed; the whole 35 mm (flush) is the setting** | a static box's height | **none** (orthogonal: no trajectory, attitude or tick change) | the whole scene: branch move, both references, every store's image population |
| 2 | raise the **transfer** only (a new place-only knob; or the scene's `output_place_clearance`) | **0.83-1.00 mm/mm** (0.825:1 in z, x the measured 0.89 hang slope) | **41-46 mm** (1.530 -> 1.571-1.576) | the transit's *end* pose | **unmeasured**: the left's reach at the transfer (`res_end` 13.3 mm at 1.53 from the low start) and a 10 % steeper diagonal | direct-only if 2a; the scene if 2b |
| 3 | shorten the transit (place pose inward, `FRUIT_PLACE_INNER_SHIFT`) | **0.24 mm/mm** | **144 mm** against a measured ~30 mm safe budget | the release point | **measured negative** (P3: 100 mm -> 90 % -> 30 % placed) | the scene |
| — | the shared `FRUIT_OPENARM_TRANSFER_LIFT` (both of its sites) | 1.00 mm/mm | 34 mm | **the lift end too** | **it *is* the carry loss**: the 0.36 rung, `drift_end` -> 25 deg | — |

**Recommended: option 1, registered as an inner-only rail height of
`h = 0.015`** (the rail's top face flush with the belt's top, the 25 mm-wide
ledge kept, the far-side fence untouched; `FRUIT_OUTPUT_RAIL_HEIGHT=0.015` is the
zero-code equivalent that flushes the outer box too). It is the only option whose
gain is **orthogonal to the class being fixed** — it moves the obstacle, not the
payload's path — it is the best gain per mm (1:1), and its cost class is already
measured at the *extreme*: removing the inner rail outright
(`FRUIT_OUTPUT_RAILS=outer`) was **placement-neutral in three arms** (6/9 = 6/9,
11/20 = 11/20, acceptance 7/10 -> 8/10 one draw, `logs/p30a/RESULTS.md` §2, §3,
§5), which bounds a *lowered* rail's risk from above — the lowering keeps the
ledge the removal deletes.

**The one thing that can make it not worth it** is the ledge itself: 2.3 % of
10 195 logged releases land on that 25 mm top face and are placed **96.6 %** of
the time, against **47.6 %** for releases inboard of it (§2.2). A flush shelf may
behave like the inboard class *or* trap the fruit at the belt's lip. That is a
**fixture-measurable** question (§8, F1) and it is the registered decision.

**Restore:** the inner/outer pair's defaults (0.05/0.05) and
`FRUIT_OUTPUT_RAIL_HEIGHT=0.05` both reproduce the shipped box exactly (the
builder's arithmetic, `conveyor.py:584-601`), so the whole option is one value and
the shipped default does not move unless a later phase adopts it.

---

## 1. The arithmetic (the code's own expressions)

### 1.1 The geometry constants (`assets.py`, `conveyor.py`, `tasks.py`)

| quantity | value | site |
|---|---|---|
| main belt top | 1.170 | `assets.py` `belt_center`/`belt_size` |
| output belt top | 1.350 | `assets.py:309` `output_belt_top_z` |
| output place clearance / drop-point z | 0.10 / **1.450** | `assets.py:380`, `:494` `output_place_z` |
| transfer pose (place target z) | **1.530** = 1.450 + 0.080 | `tasks.py:3304-3308` |
| lift end, shipped / low | **1.530** / **1.370** = 1.170 + 0.28 + 0.08 / -0.08 | `tasks.py:3249-3270`, `rl_env.py` `LIFT_DZ_*` |
| inner rail: y (centreline, top face) | **0.4125**, 0.400..0.425 | `tasks.py:3346` `_output_rail_y`, `conveyor.py:591` |
| inner rail: z (bottom, top) | 1.335 .. **1.385** (35 mm proud) | `conveyor.py:585,596` |
| place point | (0.43, **+/-0.50**) | `assets.py:374-379` |
| crossing fraction | **f = 0.4125 / 0.50 = 0.825** | `rl_env.py:3015-3019` (the `lift_climb` row's own derivation) |
| the rail's y footprint in the clearance report | `0.40 < abs(y) <= 0.46` | `tasks.py:3336-3343` |

**Naming, because it is easy to get backwards:** the rail the payload crosses is
the **inner** one (robot side, outer face flush with the slab's inner edge at
|y| = 0.425). `FRUIT_OUTPUT_RAILS=outer` is the *mode that keeps only the far-side
rail*, i.e. it **removes** the one in the path. This document says "the inner
rail" for the box and quotes the mode name only where it means the mode.

### 1.2 The crossing's lever arms

The place leg is a straight line from the lift end to the transfer pose, and the
payload reaches the rail's centreline at 82.5 % of its `y` travel:

```
z_crossing = transfer - (1 - f) * (transfer - lift_end),   (1 - f) = 0.175
```

so, at the low lift (lift end 1.370, transfer 1.530) — the run's own sum
(`rl_env.py:3021`, printed by every P67/P68 leg as `z_crossing 1.5020 m`):

| lever | d(z_crossing)/d(lever) | why |
|---|---|---|
| **rail height** | **0** (the crossing's z does not move) — but the *obstacle* moves **1:1** | `clr = payload_lowest - rail_top`; the trajectory is a function of `y` only |
| **transfer height** | **0.825** | `1 - (1 - f)` |
| **lift end / climb** | **0.175** | `(1 - f)` — the P66 phase 4 / P67 result |
| **place `y` (inward shift `s`)** | `+0.16 * 0.4125 / (0.50 - s)^2` = **0.264** at `s = 0` | `f = 0.4125/(0.50 - s)` |

### 1.3 The measured slope, and the doses

P66 phase 4's pair gives the clearance-per-z slope on this leg: control +30 mm at
z 1.530, L2 +5 mm at z 1.502 -> **0.893 mm of clearance per mm of z** (P67 §2
used the same number to solve the climb's 0.18 m). The *population* (P67's
control, 4 in-place left legs) reads crossing **+12 [+3..+17]**, window
**+8 [-1..+13]** — so the worst held leg needs **+34 mm** to reach +33.

| lever | dose to put the worst held leg at +33 | arithmetic |
|---|---|---|
| rail height | **34 mm** (h 0.05 -> 0.016); the registered setting is **0.015 = flush**, the knob's own endpoint (35 mm) | 1:1, no hang slope (the leg does not move) |
| transfer | **+46 mm** (1.530 -> 1.576); **+41 mm** if the hang does not change | 34 / 0.893 / 0.825 = 46.1 mm |
| place `y` inward | **144 mm** (0.50 -> 0.356) | 34 / 0.893 / 0.264 |
| climb | **~180 mm — measured**: P67's solve is 0.179 m and it *does* clear the floor (+33..+54, worst +33) at 5/10 left place legs lost | 31.5 mm of z / 0.175 |

**The rail is the only lever whose sufficient dose is smaller than its own
travel** (34 of the 35 mm it has). The transfer's is 46 mm of a pose that is
already at the left's reach boundary; the place `y`'s is 4.8x its measured safe
budget; the climb's is already measured to cost the payload.

---

## 2. Option 1 — flush the inner rail (recommended)

### 2.1 What it buys

The knob already exists and is **unmeasured**: `FRUIT_OUTPUT_RAIL_HEIGHT`
(`assets.py:356`, `conveyor.py:584`), default `0.05`, "lowers the containment
without removing it" (P30-A §6). The box's *bottom* is fixed at
`belt_top - 0.015` and its top is `bottom + h`, so **h is the proud height plus
15 mm** and every mm removed from h is a mm of crossing clearance:

| h | rail top | proud | crossing (`clr`) | window (`clr_win`) | vs the +33 floor |
|---|---|---|---|---|---|
| 0.050 (shipped) | 1.385 | 35 mm | +5 (P66 P4, L2 leg) / +12 [+3..+17] (P67 pop.) | +0 / +8 [-1..+13] | **fails** |
| 0.030 | 1.365 | 15 mm | +25 / +32 | +20 / +28 | fails |
| **0.015 (registered dose)** | **1.350 = the belt top** | **0** | **+40 / +47** | **+35 / +43** | **passes** (worst leg +34 by construction) |

`0.015` is also the knob's natural endpoint: below it the rail's top sinks *under*
the belt and the belt becomes the binding surface anyway, so the lever has no more
to give.

**But the knob is scene-wide**: the builder applies one `rail_height` to *every*
kept rail (`conveyor.py:587-601`), i.e. the inner **and the outer** box of **both**
output belts. The outer one is not in the place path and flushing it is pure
containment risk (§2.2 item 3), so the registered treatment is the **inner-only**
form: an `output_rail_height_inner` / `_outer` pair in `assets.py` and the
builder's keep branch (~10 lines, both defaulting to `0.05` = byte-inert, the
P30-A `output_rail_keep` pattern). `FRUIT_OUTPUT_RAIL_HEIGHT=0.015` stays the
**zero-code equivalent** for a first read, with its outer-rail side effect named
in F4.

Two independent cross-checks that 1:1 is the right slope here: (a) P30-A's
"the inner rail costs **~40 mm of transfer height**" is the same number read from
the other side (35 mm of rail + a few mm of hang); (b) P30-A's A4/A5 pair — the
only arm where the rail is *hit* — reads 18-20 m/s^2 on the three legs that go
1-35 mm below its top and 4-8 m/s^2 with it removed, i.e. the vertical gap is the
mechanism, not the lateral proximity.

**The gain is margin, not rate.** P66 phase 3's C20 arm already places **14/25**
on the low lift *with the shipped rail* (+0/+5, measured non-contacting: 0/16
held legs negative, no jolt, `force_min` 9.97 N). So option 1 buys **+34 mm of
documented clearance at zero carry cost** — it makes the package certifiable
under the record's own gate (a), which the lift-only form fails. It is *not*
expected to add placements.

### 2.2 What it breaks (the jobs the rails do, and the branch)

1. **The catch ledge** (the decision risk). Of **10 195** logged releases,
   **234 (2.3 %)** land on the rail's 25 mm top face and are placed **96.6 %** of
   the time, against **47.6 %** for the **552 (5.4 %)** that land *inboard* of it
   (`logs/p30a/RESULTS.md` §7.3, `RAILS_DESIGN.md`). A flush shelf keeps the
   *box* and the *width* but removes the 35 mm of lip: the same landing is now
   a release 12.5 mm inboard of the belt's edge at the belt's own plane. Two
   outcomes are possible and this document does not assume either: the moving
   belt takes it (no loss) or it stays on a static shelf at the lip (a jam, or a
   lost placement) — the 47.6 % class is the pessimistic bound.
   **Quantified if the pessimistic bound holds: 0.023 x (0.966 - 0.476) = 1.1
   points of release->placed** — small against the left's +56-point carry gain,
   and *measurable as a fixture* (§8, F1).
2. **The containment of an inward roll.** With the inner rail present, a fruit
   that rolls inboard meets the fence; with it flush there is nothing above the
   belt plane and an inward roll is a *lost placement* (the main belt is 180 mm
   below). P30-A measured this class as **not occurring** in its samples ("it
   does not occur in these samples") — so it is a stated risk, not a measured
   one, and it shares F1's fixture.
3. **Its mirror: the *outer* rail.** The far-side fence is what stops an
   *outboard* roll (a fruit released past the belt's centre). It is not in the
   place path, and the scene-wide knob would flush it too — which is why the
   registered treatment is inner-only (§2.1). P30-A's census puts the measured
   loss on the inboard side and does not quote an outboard class; F4 names the
   mirrored fixture (`FRUIT_OUTPUT_PLACE_Y=0.687`) if the scene-wide shortcut is
   used.
4. **The branch.** Any change to the stage's shape set moves the run's branch:
   P30-A's `outer` arm is numerically identical for three attempts and then
   diverges on a **placed fruit's post-release discharge row**
   (`logs/p30a/RESULTS.md` §2). Expect the same here (a smaller box, a different
   solver ordering) and read every count as **one draw of a new branch**.

### 2.3 The instrument defect this option exposes (a precondition, print-only)

`tasks._payload_clearance` **hard-codes the shipped rail top**:

```python
if y <= 0.46:
    rail = float(self.cfg.output_belt_top_z) + 0.035      # tasks.py:3341
```

so `clr=` / `clr_win=` — the fields gate (a) is read from — would keep reporting
against 1.385 and be **blind to the lever**: the run would print +5 mm while the
true clearance is +40. The fix is one expression,
`output_belt_top_z - 0.015 + <the inner rail's height>` (identical at 0.05, and
correct for either knob shape), and it must land **before** the cell or the gate
cannot be read. A second hard-coded consumer, `scripts/461_release_probe.py:93`
(`rim = floor + 0.035`), is a probe's report line and should read the config if
the probe is ever re-run. `_output_rail_y` needs **no** change (the height does
not move the `y`), so the crossing's latch ticks are the same ticks.

Also required for provenance (§6.5): a `scene` block in the manifests.

### 2.4 The two forms of option 1, and which one is registered

* **(a) inner-only flush, `h_inner = 0.015`, `h_outer = 0.05`** — the **registered
  treatment** (the ~10-line builder change of §2.1): the minimum change that meets
  the floor, the ledge box and its 25 mm top face kept, the far-side fence
  untouched. The scene-wide `FRUIT_OUTPUT_RAIL_HEIGHT=0.015` is its zero-code
  equivalent and flushes the outer rail too.
* **(b) removed, `FRUIT_OUTPUT_RAILS=outer`** — the *measured* analogue (three
  arms, placement-neutral) but it deletes the ledge and is a bigger shape change.
  **Registered as the fallback**, to be taken only if F1 shows the flush shelf
  traps the ledge class (§9).

---

## 3. Option 2 — a raised transfer (the runner-up, and the fallback)

### 3.1 What "the transfer" is, and the two ways to move it

The transfer pose z *is* the place target: `output_place_z + the hand's add`
(`tasks.py:3304-3308`) = 1.53 today. The shipped design applies **the same 0.08
add at both sites** (`tasks.py:3269` for `grasp_lift`, `:3308` for `place*`), which
is exactly why the shipped transit is horizontal (1.530 -> 1.530). Moving it:

* **2a — a new place-only, direct-only knob** (a resolver + one add in the place
  branch, the `FRUIT_LIFT_DZ` pattern). Scripted/two-line paths untouched ->
  **no motion reference moves**. This is the form worth registering.
* **2b — the scene** (`output_place_clearance`, 0.10 -> 0.15). Shared with the
  scripted line and the two-line -> both references, the acceptance's drop height
  and every store move. Strictly worse than 2a for the same crossing gain.

### 3.2 What it buys, and the dose

`d(z_crossing)/d(transfer) = 0.825`, then clearance = 0.893 x z (the measured
hang slope, though that slope was measured across two *lift* ends, so the
transfer's conversion is an assumption: the honest band is 0.825-1.00 mm/mm).
**Dose: +46 mm (1.530 -> 1.576); +41 mm on the optimistic 1:1 reading.** It does
*not* touch the lift end, so in principle `drift_end` stays in the 0.20 rung's
band.

### 3.3 What it costs

1. **The reach — the named risk, unmeasured.** P67 §6 flagged it: "the transfer
   pose is where the left's TCP already reads `res_end ~30 mm` short, so its
   reach has to be measured before it is believed". The measured numbers are
   `res_end` **80.6 / 33.7 / 13.3 mm** at lift ends 0.36 / 0.28 / 0.20
   (`logs/p66/P2_RESULTS.md`) — and all three are at the **same** transfer height
   (1.53), so the achieved error at the transfer is a property of the *route*, not
   of the target alone (13.3 mm from the low lift, 80.6 mm from the high one).
   What a 46 mm **higher** target does is untested; `assets.py`'s own note is that
   the reach boundary at this height sits at about `y_off = 0.41` from the
   shoulder (i.e. `|y| = 0.50`), so the transfer is *on* the boundary. The
   registered arm must therefore read `res_end`/`dz_end` at the new transfer
   before it believes the clearance it computes: a **negative** z shortfall
   **eats the clearance it buys** — the lever's own failure mode.
2. **The release geometry — cheap, and checkable.** The release is not the
   transfer: `_place_low` descends the payload to `FRUIT_PLACE_LOW_CLEARANCE`
   0.025 above the belt top before the jaws open (`tasks.py:12804-12830`), and
   that descent is at the place point (`|y| = 0.50`), *past* the rail. So the
   released height and the drop do not move; the descent is 41-46 mm longer
   (~26-29 ticks), inside `FRUIT_PLACE_LOW_MAX_DROP = 0.30`.
3. **A 10 % steeper diagonal.** The transit's climb grows from 0.160 m over
   0.45 m of `y` to 0.206 m. The place leg runs with **no wrist hold** (P68 §1),
   and P67's fatal case was a *vertical segment*, not a slope — so this is a
   **different, unmeasured** exposure. It is the reason 2a is the fallback and
   not the recommendation.
4. **The re-shape family is screened out.** "An earlier or faster climb" does
   not change the lever arm: every form that moves the *transit's start* buys
   **0.175:1** (f is fixed by the scene's `y`'s), and P67's losses cluster at the
   climb's **exit** (rows 113-152 of a 121-tick climb), so halving the segment's
   duration does not remove the exit — only a *shorter* climb would, and that
   buys less than the dose needs. A waypoint at a different `y` is the same
   vertical segment in a different place.

---

## 4. Option 3 — a shorter transit (not viable)

The only place-pose lever is `FRUIT_PLACE_INNER_SHIFT` (P3, `tasks.py:3299-3303`;
capped at 90 % of the belt half-width, `|y| >= 0.3875`). Inward shift `s`:

* **gain 0.24 mm of clearance per mm** (`d(z_cross)/ds = 0.264`, x 0.893), so the
  floor needs **s = 144 mm** — the release at `|y| = 0.356`, i.e. **inboard of
  the belt's inner edge at 0.375**;
* **the measured safe budget is ~30 mm** (`+7 mm` of clearance), because P3's
  100 mm shift collapsed the acceptance **90 % -> 30 %**: the payload releases at
  `|y| 0.21-0.41` while the belt's inner edge is 0.375, so the shifted releases
  land in the 47.6 % inboard class (§2.2) instead of on the belt;
* an *outward* shift is worse, not neutral: `f = 0.4125/(0.50 + s)` falls, so the
  crossing happens earlier, closer to the low lift end (moving the place point
  50 mm out gives `f = 0.75` and costs ~11 mm of clearance).

**Verdict: option 3 cannot reach the floor inside its own safe budget by a
factor of 4.8, and its cost is a measured place-path loss.** It also would not
be free of the scene (the release point is `SceneConfig`), so it has option 1's
blast radius with none of its gain.

---

## 5. Excluded — the shipped `FRUIT_OPENARM_TRANSFER_LIFT` itself

It is read at **two** sites (`tasks.py:3269` lift end, `:3308` transfer) and at
three more for reporting (`rl_env.py:2566, 2972, 3011`), from one process-wide
environment value. So raising it raises the **lift end 1:1 with the transfer**:
the crossing gains 1:1 (the transit stays horizontal), and the lift end goes back
up — which is precisely the 0.36 rung whose `drift_end` is 25 deg and whose left
placed is **0/25** (`logs/p66/P3_RESULTS.md`). **It is not an option: it *is* the
carry loss.** Splitting it is option 2a, and that is a new knob, not this one.

---

## 6. The chosen option's full cost

### 6.1 Code (all of it small, none of it a trajectory change)

| what | where | note |
|---|---|---|
| **the inner/outer height pair** | `assets.py` (`output_rail_height_inner`/`_outer`, default 0.05/0.05 = shipped) + `conveyor.py:584-601` (choose by `keep_inner`) | the registered treatment (§2.1); byte-inert at the defaults, reported by the existing audit `say()` |
| the rail height's own expression in the report | `tasks.py:3341` | **precondition** (§2.3); byte-inert at 0.05 |
| the manifest's `scene` block | `rl_env.py` `_manifest` (next to `physics`/`supply`), the collector's shard manifest | `{rails: mode, rail_height_inner_m, rail_height_outer_m, rail_proud_m, rail_centre_y_m, top_z_m}` — so a store is identifiable by field, not by md5 archaeology (the P41/P58 precedent) |
| the probe's rim constant | `scripts/461_release_probe.py:93` | if that probe is ever re-run |

### 6.2 The motion references — conditionally, from the same batch

The fingerprint is per-leg `[samples, |v|max]`, so a static box cannot move it
*unless* the run's branch moves. P30-A's precedent says it does (the first
divergence is a placed fruit's ride to the discharge), so the registration is:

| file | md5 today | when |
|---|---|---|
| `configs/motion_reference.json` (single arm) | `8a399626` | re-record **iff** the acceptance's `[fruit]` stream moves; always from the **same-batch control** of the new geometry |
| `configs/motion_reference_twoline.json` | `2246f83c` | re-record **iff** the two-line control moves; `190` re-gated after |
| `configs/motion_reference_patch.json` | `7b028049` | only if the W6/W7 patch battery is re-run (it uses this file) |
| `configs/motion_reference_twoline_bed.json` | `dcd19758` | only if the P32 bed battery is re-run |

Each re-record must come from **its own** same-batch control (the reference rule
in AGENTS §1/§2), and `scripts/189_w7a_chain.sh` must **not** be run casually (it
re-writes the two-line file from `logs/w7/10`).

### 6.3 The scripted acceptance

Shared scene -> **it moves if the branch moves.** The scripted lift is the
shipped 0.36 (the `FRUIT_LIFT_DZ` lever is `direct`-only), so its place legs
already read +33..+55 and the rail is **not** a safety object there: the change
is expected to buy nothing on the scripted line and to move its branch. Run as a
pair (control vs flush) and quote the count as one draw (P30-A: 7/10 -> 8/10).

### 6.4 The two-line

Same two output belts -> the same geometry, the same expected branch move:
`scripts/190_twoline_gate.sh` (default reference `motion_reference_twoline.json`,
floor 0.60) on its own control + flush pair, and its own re-record if it moves.

### 6.5 The collector and the stores

* **Provenance already exists**: `src/fruit_sorting/conveyor.py` and `assets.py`
  are in both pin lists (`40_collect_demos.py:240-247`, `rl_env._MANIFEST_SOURCES`),
  so a post-flush shard is identifiable by md5 — but *by field* is what §6.1 adds.
* **Every existing store is pre-flush**: `demos_v11`, `demos_v12`, `demos_v12d_s02`,
  `demos_v13p`, `datasets/p33_pear`, `datasets/rl_rollouts/p37_park`. The rail is
  in the camera's frame, and P36 measured that image statistics *do* carry outcome
  information on this interface — so a pre-flush store is a different **image
  population**, not a transferable one.
* **The re-baseline note**: every direct number on this tree is *pre-flush*;
  `FRUIT_OUTPUT_RAIL_HEIGHT=0.05` restores it exactly. The package **already
  re-baselines** the direct line (the low lift is a new direct default), so the
  rail's marginal store cost is *shared*, not added: one re-baseline, not two.
  Compose with `FRUIT_ARM_PARK=ready` (pre-P43), `FRUIT_POLICY_TRIGGER_ACQ=0`
  (pre-P54) and the P58 burst profile for the older baselines.

### 6.6 The hybrid canary

`60_eval_policy.py` builds its own `FruitSpawner` + `PickAndPlaceTask` from the
same `SceneConfig`, so the rail is shared; its lift is the scripted 0.36, so its
crossing is +33..+55 before and +68..+90 after — **no safety object**, only a
re-sample of the recorded 5-8/10 spread. No deployment path to the direct knobs.

### 6.7 What does not move

The pick station, the supply (`fruits.py`), the belt's transport, the release
(`_place_low`), the waypoints, the checkpoint, the datasets' schema, the
`FRUIT_LIFT_DZ` / `FRUIT_LIFT_CLIMB` / `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S` knobs.

---

## 7. The expected benefit

With the low lift retained and the rail flushed:

* **crossing `clr` and window `clr_win` in +34..+47 mm** on the left's in-place
  place legs (the worst held leg +34 by construction from §1.3; the population's
  median +43..+47 from §2.1), and the binding surface becomes the **belt top** —
  the stronger claim: the payload clears the *conveyor*, not just its fence;
* **the left's carry class at the 0.20 rung's measured level** — 14/25 placed
  against the control's 0/25 (N=5, `logs/p66/P3_RESULTS.md`) — with the record's
  clearance convention met, i.e. the **first form of the low lift that is
  certifiable under gate (a) without spending the carry** (the climb cleared it
  and lost 5/10 place legs; the climb + hold lost 16/16);
* **the cost, in one line**: the rail's 35 mm of lip, of which 2.3 % of releases
  use the top face (96.6 % placed) — bounded by the removal's measured
  placement-neutrality.

---

## 8. The cell

Four cells, all required before any adoption; the shipped defaults do not move
until every endpoint passes.

**G1 — the geometry cell (the gate).** The P67/P68 *population* protocol: all-A
supply (`FRUIT_SUPPLY_GRADES=A:0.96,B:0.02,C:0.02`, so every attempt is a left
place leg), the general scenario's env verbatim otherwise (seed `s`,
`FRUIT_POLICY_SEED=11`, the shipped direct profile, `moe_v13s` `61da390a`,
`FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1`), 8 picks/run:

| arm | env |
|---|---|
| **C (control)** | `FRUIT_LIFT_DZ=-0.08` (rail shipped) |
| **R (treatment)** | `FRUIT_LIFT_DZ=-0.08 FRUIT_OUTPUT_RAIL_HEIGHT_INNER=0.015` (the §2.1 builder change; the zero-code first read is `FRUIT_OUTPUT_RAIL_HEIGHT=0.015`, which also flushes the outer box) |

**N = 5 seeds (77/101/202/303/404), interleaved C -> R per seed, 10 runs.**
N = 4 is the floor and reads "not certified" (the P66 phase-3 precedent); the
truncation at 8 picks/run is P67's (the all-A line is the slow arm, ~3.4
min/episode), and it costs nothing the read needs — the unit is the *leg*.

**G2 — the ledge fixture (the decision falsifier).** `FRUIT_PLACE_LOW=0
FRUIT_OUTPUT_PLACE_Y=0.4125`: every release is a free drop from the transfer
height onto the rail's top face, **10 attempts per geometry** (arm C = rail 0.05,
arm R = rail 0.015), both at the same forced `y` so the comparison is
geometry-vs-geometry and the reach confound cancels. Read: the spawner's own
outcome class per drop (`on_output_belt`/`discharged` vs `fell_off`,
`assets.py:506-630`).

**G3 — the scripted pair.** `scripts/accept.sh` control vs `FRUIT_OUTPUT_RAIL_HEIGHT=0.015`
(one run each, same batch): the branch-identity measurement, the motion budgets,
and the reference decision (§6.2/§6.3).

**G4 — the two-line pair.** The dense 10-attempt battery control vs flush, gated by
`scripts/190_twoline_gate.sh` (§6.4).

### Endpoints

| # | endpoint | read | verdict form |
|---|---|---|---|
| P1 | **the gate**: `clr_win >= +33` and `clr >= +33` on **every** in-place left place leg (`clean_slip <= 50 mm`, held at the crossing tick — P66's convention) | the `[carry]` fields, after §2.3's report fix | pass/fail per leg |
| P2 | **manipulation check**: `drift_end` on the left's `grasp_lift` legs stays in the 0.20 rung's band (median <= 2 deg, range 0.6-25) | `[carry] hold_drift/drift_end` | else the cell is confounded |
| P3 | the carry class | left placed/composite per arm, quoted as a **branch** | report only |
| P4 | **the ledge class** (G2) | placed rate of the forced-landing drops | **>= 0.80 to pass** |
| P5 | containment / discharge | no **new** `fell_off` or `diverted` row; `discharged` count equal; an inward-roll lost placement counts against the lever | pass/fail |
| P6 | no contact | the place legs' `|a|max` <= the control's (the rail-contact signature is 18-20 m/s^2, P30-A A4); in-hand `|v|max` unchanged | pass/fail |
| P7 | the scripted line | `accept.sh` pair: motion budgets PASS, the `[fruit]`-stream identity measured (expected to move), the count one draw, the fingerprint matches after the re-record | pass/fail |
| P8 | the two-line | `190` PASS at the 0.60 floor on its own control + flush pair (and its own re-record if it moves) | pass/fail |

---

## 9. The falsifiers, the decision rule, and what would make it not worth it

**F1 (the decisive falsifier) — the ledge.** G2's forced-landing placed rate
under the flush rail **< 0.80** (the shipped-geometry baseline is 96.6 %; the
inboard class is 47.6 %): the flush shelf behaves like the inboard class or jams
the lip. **Then option 1's margin costs places and is not worth it.**
**F2 — the crossing does not clear.** If, at the flush dose, any in-place leg
still reads `clr_win < +33`, the rail lever is **exhausted** (it has no headroom
left) and the fallback is option 2a (§3) with its own registration.
**F3 — the carry is confounded.** P2 fails -> the cell is not about the rail;
re-run rather than interpret.
**F4 — the discharge breaks.** A new `fell_off`/`diverted`, or the flush arm's
`discharged` count below the control's -> the containment loss is real (P5). If
the scene-wide `FRUIT_OUTPUT_RAIL_HEIGHT` shortcut is used, this falsifier gains
the mirrored fixture (`FRUIT_OUTPUT_PLACE_Y=0.687`, the outer rail's side).
**F5 — the scripted line regresses beyond the branch spread.** P7's acceptance
count **>= 2 attempts** below the same-batch control (P30-A's own spread on a
single pair was +1/-1, so 2 is outside it) **and** F1 fired -> the scene-wide
cost is not paid for. F5 alone is *not* decisive (counts are quantized draws); it
is a corroborator.
**F6 — a contact.** Any place leg's `|a|max` > 10 m/s^2 at the crossing, or a
negative `clr_win` on a held leg: the lowering did not remove the obstacle it
was meant to (P6).

### The decision rule

> **Adopt** the pair (`FRUIT_LIFT_DZ=-0.08` + the inner rail at `h = 0.015`)
> **iff** P1 passes on every in-place leg, P2 passes, P4 >= 0.80, P5 and P6 pass,
> P7 passes (budgets + the re-recorded fingerprint) and P8 passes.
> **If F1 fires** (P4 < 0.80) **and** F5 corroborates (>= 2 attempts below the
> control), the option is **not worth it**: ship the low lift
> **alone**, with the crossing at +0..+5 mm recorded as a **measured,
> non-contacting geometric graze** (0/16 held legs negative, no jolt, 9.97 N) —
> which is P66 §5's honest reading and needs no new geometry.
> **If F2 fires** (no headroom), the fallback is **option 2a**, registered
> separately (its own reach endpoint: the left's `res_end` at the new transfer
> must stay <= 30 mm, else the lever eats its own gain).

### What would make the whole line not worth it

The one-sentence version: **if the 2.3 % ledge class is what the 35 mm of lip was
buying, then the margin is being paid for out of the place path** — and since the
low lift *already* works with the rail untouched (no contact, no jolt, +0/+5 mm),
the correct answer would be to **document the graze and change nothing**, not to
trade a measured placement class for a convention. Everything else in the option
(the branch move, four reference files, the store re-baseline) is mechanical and
already paid by the low-lift package.

---

## 10. Budget, pins, and what this document is not

**Budget** (the P58/P66/P67 wall figures, this machine): G1 10 runs x ~27 min =
**~4.5 h**; G2 2 x 10 attempts = **~40 min**; G3 the acceptance pair **~50 min**;
G4 one two-line pair **~30 min**; the optional general-scenario class cell (3
seeds x 2 arms x 15 picks, ~9 min each) = ~55 min. **Total ~7 h wall** for
G1-G4, one claim at a time, the `scripts/154_claim_run.sh` + `scripts/run.sh`
contract (the single-simulator rule).

**Pins at registration** (HEAD `c5c8f25`): `tasks.py` **`e5168578`**,
`conveyor.py` **`b0d95a08`**, `assets.py` **`61baf52b`**, `rl_env.py`
**`d88c3729`**; `configs/motion_reference.json` **`8a399626`**,
`..._twoline.json` **`2246f83c`**, `..._patch.json` **`7b028049`**,
`..._twoline_bed.json` **`dcd19758`**; checkpoint `moe_v13s` **`61da390a`**. No
`configs/` or `src/` file was touched by this phase.

**What this document is not.** It is not a measurement: P1-P8 are unrun. It does
not adopt anything (`FRUIT_OUTPUT_RAIL_HEIGHT` stays unset = `0.05`, and
`FRUIT_LIFT_DZ` stays off/opt-in). It does not re-open the two closed classes:
the carry/loaded-slide class stays as `logs/p42/SIM_LIMIT.md` records it (this
option *keeps* the low lift's gain rather than adding a new one), and the
pad-asset path (P30-C's 24-45 mm) is P69-A's, not this phase's. And it is not a
claim that the +33 mm floor is a *contact* threshold — it is the record's
convention (min +33 over 42 place legs in four arms), and the low lift's +0/+5 mm
is measured **without contact**; the option buys the convention back, not safety
that was lost.

**The arithmetic is re-derivable offline** and should be pinned as a selfcheck
leg when the option is armed: `f`, the three lever arms of §1.2, the 0.015
setting (0.05 minus the knob's whole 35 mm, against the 34 mm the floor needs),
and the `_payload_clearance` expression's byte-identity at 0.05 — the
`scripts/237_p67_climb_selftest.py` pattern.
