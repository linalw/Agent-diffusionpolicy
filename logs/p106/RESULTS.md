# P106 results - the Allegro mounted, and P104's pull test on it (M1 + M2a)

**VERDICT (first line).** **M1 passes on the mount and fails on the close+lift
gate as a rate** (1 of 4 close+lift cells held), and **M2a does not fire the plan's
kill**: the **4-pad radial surrogate clears 1.5x on all three fruits on both legs**
(sustained **1.98 / 1.87 / 2.05x**, at 2 mm **1.82 / 1.80 / 2.10x**, creep
**0.11-0.25 mm** against the pinch's **0.85-3.20 mm**), while the **Allegro is not
evaluable** - its cell cannot be brought to the pinch's per-contact force, and on
the four draws that exist one held and three dropped the payload at the first
release. So the plan's predicted **1.2-1.6x** for the Allegro is **neither
confirmed nor refuted**; what is measured is the *mechanism the prediction was
about*: this hand's fingertips span **116-123 mm**, so **at most 3 of its 4
fingers can touch one 37-66 mm payload at any posture tested**.

Read that in the plan's own terms: **a 3+1 anthropomorphic topology is not
demonstrated to be enough and the radial form is**, which is the design input
§1.7 asked for - and nothing here licenses buying a *specific* hand, because the
only form that passed is the surrogate we authored, which cannot approach a fruit.

---

## 0. Scope, before the numbers

A probe, not a policy run: the cell's environment plus the real OpenArm
articulation, no conveyor, no camera, no attempt loop. `METHOD.md` §1 fixes what
it can and cannot decide. `configs/` untouched; no `src/` change; no shipped
default moved.

## 1. M1 - the mount (structural: PASS)

From `mount_census.txt`, one deterministic run.

| clause | measured |
|---|---|
| asset loads | `WonikRobotics/AllegroHand/allegro.usd`, HTTP 200, 1 626 251 B, default prim `/kuka_allegro` |
| mounted on the flange | referenced under `/World/OpenArm/openarm_left_ee_tcp`, `PhysicsFixedJoint` to `allegro_mount`, identity frames |
| DOF count and order | **38** = 22 arm + 16 hand, hand half `index/middle/ring/thumb _joint_0..3` in that order |
| the articulation is one | the merged arm reads `+0.2894` for a `+0.300` command (radians), all joints 0.000 at play |
| joint limits (rad) | `index_joint_0 [-0.558,+0.558]`, `index_joint_1 [-0.279,+1.728]`, `thumb_joint_0 [+0.279,+1.571]`, `thumb_joint_3 [-0.279,+1.763]` |
| drive | `angular/force`, asset `k=10^7`, `c=10^5`, `maxForce=21 N.m`; the API's *readback* is `5.73e8` / `5.73e6`, which is not the authored pair (recorded, not used) |
| mass | **2.135 kg** over its 21 bodies (the plan carried ~1.1 kg [R]) |
| tool offset (replaces `_pad_standoff` 70 mm) | **170.7 mm** along the tool axis at the sweep's mid posture, **100-216 mm** across the sweep |
| the arm still holds a pose | the shipped `ready` waypoint, flange `(0.332, 0.051, 1.282)`, tool axis `(0.000, -0.045, -0.999)` |
| the pads are out of the way | `FRUIT_FINGER_COLLIDERS=0` (no pad collider in the contact set) |

**Two defects the mount exposed, both recorded in `METHOD.md` §2**: the asset's
`root_joint` is a **world** anchor that survives `RemovePrim` through a reference
(destroying the articulation: arm joint 1 read **-82.19 rad** and a `+0.3` command
moved it **-34.39**), and `ArmController.move_to` from the hanging pose **stalls
186-326 mm short**.

### The close+lift gate: 1 of 4

The plan's M1 gate is "closes on a pear and a strawberry and lifts them >= 50 mm",
read by the primitive's own test (`fruit_z - z_before > 4 mm`).

| cell | lift | held | creep under its own weight |
|---|---|---|---|
| pear (draw 1) | **+59.7 mm** | **yes** | **39.75 mm** |
| pear (draw 2) | -0.7 mm | no | 1080 mm (to the floor) |
| orange | -1.7 mm | no | 1089 mm (to the floor) |
| strawberry | +0.0 mm | no | 1071 mm (to the floor) |

**Provenance of the holding draw, stated plainly**: it came from an earlier run of
the *same* configuration, and `m2a_allegro.txt`'s recorded re-run of that
configuration did **not** reproduce it (the pear dropped there too). So the hold is
**1 of 4 draws and not reproducible**, which is a second reason not to quote its
>40 N bound.

**So the gate is not met as a rate**, and the one draw that held had already crept
**39.75 mm** under 0.82 N - **12x the pinch's 3.20 mm** and **40x the plan's
1.0 mm** creep bar. The failure is not a force shortfall: the fingers **knock the
payload out of the seat as they close** (the measured per-tip contact reads
`index -0.80 N` with the other three at 0.00 at the post-release tick, and the
payload is on the floor 0.75 s later).

## 2. The topology - the phase's central measurement

`best_seat` asks, for a posture, how many of the four fingertips can touch a sphere
of a given radius (`|d - r| <= 12 mm`, the tip link origin sitting inside the pad).
Across a 4 x 4 posture sweep (finger curl 0.5-1.4 rad x thumb abduction 0.4-1.5 rad),
`mount_census.txt`:

| posture class | 3-finger span | thumb-to-fingers | tips that can touch r=30.3 (pear) | r=32.9 (orange) | r=18.6 (strawberry) |
|---|---|---|---|---|---|
| open (curl 0.5) | 116-119 mm | 153-208 mm | 2 | 2 | 1-2 |
| mid (curl 1.1) | 121.6 mm | 58-134 mm | 2-3 | 2-3 | 2 |
| closed (curl 1.2-1.4) | 102-129 mm | 43-79 mm | 2-3 | 2-3 | 1-2 |

**Never 4.** The three fingers alone span **116-123 mm** when the hand is open, and
a 37-66 mm payload is geometrically smaller than that spread - the fingertips
cannot be placed on one sphere because the pairwise distances between them
(up to **102 mm** between the index and ring tips) already exceed the payload's
diameter. On a 60.6 mm pear the hand is a **2-3 contact** grasp at every posture
the sweep visited.

**This is the plan's §1.7 concern measured.** Its arithmetic said "three fingers'
normals point roughly the same way, so `n_eff ≈ 2`" (1.0x); the measured reason
is blunter - **three of the four fingertips cannot even reach the payload at the
same time**. It also means a per-contact-force comparison at 4 contacts is not
available on this hand, whatever the drive does.

## 3. M2a - the pull test, three forms, one batch

The controls are P104's fixture **unchanged**, re-run in this batch
(`m2a_control.txt`); they reproduce P104 to the digit (its `fixture.txt` was
generated by the same deterministic fixture). The Allegro cell is the in-scene
probe (`m2a_allegro.txt`).

| form | fruit | n | N/contact | sustained break | 2 mm | creep | pry |
|---|---|---|---|---|---|---|---|
| pinch (control) | pear | 2 | 4.90 | **11.03 N** | 10.62 | 3.20 mm | 0.37 mm |
| pinch (control) | orange | 2 | 4.90 | **14.21 N** | 13.83 | 0.85 mm | 0.30 mm |
| pinch (control) | strawberry | 2 | 4.90 | **12.69 N** | 12.19 | 2.68 mm | 0.13 mm |
| **4-pad radial** | pear | 4 | 4.80 | **21.81 N (1.98x)** | 19.28 (1.82x) | **0.25 mm** | 0.75 mm |
| **4-pad radial** | orange | 4 | 4.88 | **26.59 N (1.87x)** | 24.83 (1.80x) | **0.15 mm** | 0.55 mm |
| **4-pad radial** | strawberry | 4 | 4.90 | **25.97 N (2.05x)** | 25.61 (2.10x) | **0.11 mm** | 0.30 mm |
| **Allegro** | pear (draw 1) | 2-3 | **not matched** | **> 40 N (bound, >3.63x)** | 13.20 (1.24x) | **39.75 mm** | 2.24 mm |
| **Allegro** | pear / orange / strawberry (draws 2-4) | - | - | **no grasp** | - | 1.07-1.09 m | - |

**The surrogate clears the bar on both legs.** Sustained **1.87-2.05x** and the
2 mm criterion **1.80-2.10x** (P104's caveat - a 4-contact form does not re-seat
past 2 mm, so both criteria pass), and the creep is **9-24x better than the
pinch's** at the load the cell actually applies. The pad's own travel at break is
**0.30-0.75 mm**, i.e. the pads do not pry - the same reading P104 published.

**The Allegro cannot be priced.** Its one holding draw is **above** the bar on the
sustained leg (a bounded `> 40 N`) and **below** it on the 2 mm leg (1.24x), at a
per-contact force the phase could not measure or match; and it fails the creep leg
by 40x. Its other three draws do not grasp at all. Quoting "> 3.63x" as a win
would be wrong twice over: the force is not matched, and the same grasp had
already walked 39.75 mm under 0.82 N before the ramp started.

## 4. Did the prediction fire?

**Not as written, and the reason is itself the result.**

| prediction (`docs/HAND_STAGE_PLAN.md` §1.7) | outcome |
|---|---|
| Allegro sustained **1.2-1.6x** | **not adjudicated** - no reproducible grasp at a matched per-contact force; the one draw reads 1.24x on the 2 mm criterion (in band) and >3.63x on the sustained one (out of band), on 1/4 cells |
| radial surrogate **1.87-2.05x** | **fires**: 1.87 / 1.98 / 2.05x sustained, 1.80 / 1.82 / 2.10x at 2 mm |
| "the hand's win is form closure, not the contact count" | **supported in the direction it can be measured**: the Allegro's four fingertips cannot be brought onto one payload (<= 3 of 4), so the extra joint count buys nothing on a 37-66 mm fruit |

The prediction's *direction* is right (3+1 does not deliver the radial form's
2x) and its *magnitude* is untested. A future phase could test it only with a
drive that can be commanded as a **force** (an effort actuator with a feed-forward
torque), not a position servo whose cap is a step function.

## 5. So what does this license?

**M2a's kill does not fire**, by the plan's own rule: the surrogate clears 1.5x on
every fruit and on both legs. The plan's clause then applies verbatim - *"if only
the surrogate passes, the surrogate is what licenses the purchase and the
Allegro's number is recorded as the 3+1 topology's own"*.

**But the licence is for a shape, not a product.** What passed is a radial
4 x 90 deg arrangement at a matched 4.80-4.90 N per contact; no buyable hand was
measured, and the surrogate cannot approach a fruit or run a precision grasp. The
decision this phase supports is **"if a hand is bought, it must be radial or
strongly enveloping, not anthropomorphic 3+1"** - which changes *which vendor*,
not *whether to buy*. The purchase itself remains the owner's, and the plan's
own gate for it (M3: a scripted hand running the cell at >= 8/10) is untouched.

**What this does not decide, stated plainly:**

* **The purchase.** No hardware is licensed by a sim probe; the plan buys nothing
  before M3.
* **The policy work.** Nothing here touches the 14.2 % policy phase, the store,
  the schema or the recollection.
* **The approach (`M2b`).** Unspent. A hand that bats the fruit is a pipeline
  negative no matter what it can hold (`logs/r8/A_RESULTS.md` §3, 2 -> 9 of 15
  no-contact), and this phase did not run it. The Allegro's failure mode here -
  knocking the payload out of the seat as the fingers close - is exactly the class
  M2b would have to score.
* **The scripted hand (`M3`).** Unspent, and it is the gate that actually licenses
  a purchase.
* **A real jaw's clamp force and a soft pad's imaging.** [U] as before
  (`logs/p42/SIM_LIMIT.md` §3).

## 6. Files and pins

`logs/p106/`: `METHOD.md`, `RESULTS.md`, `m1_mount_probe.py`, `run_p106.sh`,
`mount_census.txt` (the M1 census + the 16-posture geometry sweep),
`m2a_allegro.txt`, `m2a_control.txt` (the pinch + quad, P104's fixture unchanged),
`inspect_allegro.py` (asset census), `units_probe.py` (the units pre-flight).
`configs/` untouched; no reference re-recorded (the scripted line never runs this
code); ckpt `moe_v13s` `61da390a` unchanged.
