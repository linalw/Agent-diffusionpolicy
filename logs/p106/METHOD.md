# P106 method - the Allegro mounted in the cell, and P104's pull test on it

Written 2026-11-03. **No `src/` change, no `configs/` change, no shipped default
moved.** The artefacts are this file, `RESULTS.md`, the probe
(`m1_mount_probe.py`), its driver (`run_p106.sh`), the census/measurement outputs
(`mount_census.txt`, `m2a_allegro.txt`, `m2a_control.txt`), the asset census
(`inspect_allegro.py`), the units pre-flight (`units_probe.py`), and the
AGENTS/WORKLOG/plan paragraphs.

This is the first sim-only step of `docs/HAND_STAGE_PLAN.md`: **M1** (a hand asset
mounted in this scene) and **M2a** (P104's pull test reproduced on it). The plan's
own kill is quoted so the phase cannot drift from it:

> **M2a's kill**: both forms read **< 1.5x** -> buy no hand.

And its prediction, also pre-registered:

> the Allegro's sustained axial capacity on the pear reads **1.2-1.6x** the pinch,
> i.e. at or below the bar, while the radial surrogate reads **1.87-2.05x**.

---

## 1. What the probe is, and what it is not

A standalone probe scene - the cell's **environment** and the real OpenArm
articulation, no conveyor, no camera, no scheduler, no policy, no attempt loop.
The Allegro USD is referenced under `/World/OpenArm/openarm_left_ee_tcp`, welded,
and driven; the arm holds the shipped `ready` waypoint.

It **can** decide whether the asset mounts in this scene, what its DOF/drive/
collision authoring is, where its grasp centre sits relative to the flange (the
number that replaces `_pad_standoff`'s 70 mm), and whether the mounted hand can
close on a fruit and hold it under P104's axial ramp.

It **cannot** decide: the approach and acquisition (`M2b`), the scripted
pick-and-place (`M3`), the policy (`M4`), a real jaw's clamp force, or a soft
pad's behaviour. The sim's contacts are rigid and adhesion-free
(`logs/p42/SIM_LIMIT.md` §3), so this can falsify, never confirm.

## 2. The mount, and the two defects it exposed

The asset is `WonikRobotics/AllegroHand/allegro.usd` on the tree's own asset root
(HTTP 200, 1 626 251 B). Measured census (`inspect_allegro.py`, `mount_census.txt`):

| quantity | measured |
|---|---|
| default prim / articulation root | `/kuka_allegro` |
| links / rigid bodies | 21 |
| revolute joints | **16** (index/middle/ring `joint_0..3`, thumb `joint_0..3`) |
| joint limit authoring | **degrees** in USD, read back in radians by the articulation (`index_joint_1` `[-0.279, +1.728]`) |
| asset drive | `angular`, `type=force`, `k=1e7`, `c=1e5`, `maxForce=21 N.m`, target 0 |
| colliders | 18 `CollisionAPI` prims on the mesh children; no link carries one itself |
| mass (sum of its 21 bodies) | **2.135 kg** (the plan carried ~1.1 kg [R]) |
| DOF after the mount | **22 -> 38** = 22 arm + 16 hand (one hand on both arms would be 54) |

**Defect 1 - the asset's world anchor survives a reference.** `root_joint` is a
`PhysicsFixedJoint` from **world** to `allegro_mount`. `stage.RemovePrim` does
**not** defeat a prim that comes from a reference (the reference still composes
it), so the hand stayed pinned to the world origin while the mount joint pulled it
to the flange. The result is not a warning, it is a destroyed articulation: at
play the arm read `openarm_left_joint1 = -82.19` (its limit is -3.49 rad), and a
`+0.300` command moved it `-34.39`. `prim.SetActive(False)` is the fix; with it the
arm reads 0.000 at play and a `+0.300` command reads `+0.2894`.

**Defect 2 - `ArmController.move_to` stalls from the hanging pose.** Two attempts
to servoing the flange to `(0.30, 0.00, 1.28)` from the rest pose (one direct, one
through a 40-waypoint straight line) ended **186 mm** and **326 mm** short, with
the tool axis tilted up to 30 deg. The probe therefore places the arm by
**teleporting to the shipped `ready` waypoint** (`configs/waypoints.json`) and does
not move it again except a short straight lift. The pull test needs a held pose,
not a station, and this is recorded as a *limitation of the probe*, not of the arm.

**The unit check** is on the merged articulation, because the merger is exactly the
kind of thing that can silently change it: `+0.300` on arm joint 1 reads
`+0.2894` (radians), and every hand limit reads back in radians.

**The mount joint.** `PhysicsFixedJoint` from the flange to `allegro_mount`,
identity local frames (the mount's own transform is authored on the prim, so the
two frames coincide by construction). The hand's own `allegro_mount_joint`
(mount -> palm) is left as authored.

## 3. The tool offset (replaces `_pad_standoff`)

`_pad_standoff` is 70.0 mm = `FRUIT_FINGER_LEN` 60 + `PAD_LIFT` 10. The Allegro's
grasp centre is **not** a constant: it moves with the finger posture, and it is
**further** from the flange than the pad hand's:

| posture (finger curl, thumb abduction) | seat along the tool axis | from the flange |
|---|---|---|
| curl 0.5, thumb 0.4 | **+216.1 mm** | 233.6 mm |
| curl 1.1, thumb 1.3 | **+161.5 mm** | 194.2 mm |
| curl 1.1, thumb 1.5 | **+166.8 mm** | 198.2 mm |
| mid posture of the sweep (1.0, 0.9) | **+170.7 mm** | 199.5 mm |

So the mount's tool offset is **~100-216 mm along the tool axis**, i.e. **1.4-3.1x**
the pad hand's 70 mm, and any hand stage must re-derive it per posture rather than
copy it. The probe reports the number it used for the seat it closed at.

## 4. The grasp seat, and why it is measured rather than assumed

Three candidate definitions were tried and the first two were **rejected by
measurement**, which is worth recording because each looked reasonable:

1. **The four-tip centroid.** It puts the payload outside the grasp: the thumb sits
   100-170 mm from the finger cluster, so the centroid lands between them and the
   payload touches two fingers. First sweep: `index 3.12 N`, the other three `0.00`.
2. **A least-squares sphere through the four tips.** Four near-coplanar points make
   the algebraic problem singular: `r_fit` read **233-1404 mm**.
3. **The seat that puts the most fingertips on a sphere of the payload's radius**
   (`best_seat`): a +/-50 mm grid at 5 mm over the tip centroid, a tip counts as
   touching when `|d - r| <= 12 mm` (the tip *link origin* sits inside the pad
   surface). This is the definition the probe uses, and its own output - **how many
   tips can touch at all** - is the phase's central topology measurement.

## 5. The close: what the drive can and cannot be asked for

The plan (§1.4) predicts that a force cap is not a torque cap and that the hand's
drive must be tuned to a *measured* target. Both halves are measured here:

* **The torque cap is a step function.** At the shipped drive (k=1e7) the pear
  reads **no contact at cap 0.46 N.m** and **10.5 N per contact at 0.48 N.m**; there
  is no operating point in between. The reason is that a stiff position servo
  cannot be made gentle by capping its torque - below the threshold the finger
  never reaches the payload at all.
* **A softer drive (k=20 N.m/rad, c=0.4) does give intermediate forces** (2-6 N per
  loaded finger) but the delivered force depends on the *penetration*, so it must be
  set by a closed-loop close on a force instrument - and the force instruments on
  this asset are not trustworthy: a per-link contact view is what `tactile.py`
  uses on the *pads*, but on the hand's links it reads `Physics contact view is not
  valid` or reports 60-90 mm-away fingers, and the drive-torque readback
  `k*(target-q)` divides by a `k` the API reports as **5.73e8** against an authored
  1e7.

So the probe closes with a **fixed over-curl past the just-touching posture** (the
analogue of P104's `INTERFERENCE`), and the per-contact force is whatever that
produces. This is the honest limit of the phase: **the Allegro's cell is not at a
matched 4.90 N per contact**, so its ratio cannot be quoted against the pinch's as
a contact-count comparison.

## 6. The pull test

P104's protocol, reused unchanged where it applies: a **5 N/s axial ramp with
gravity to a 40 N cap**, the payload pinned while the grasp closes, `clean_slip >
2 mm` for the survey's criterion, 30 mm for "gone", and the **creep** as the
payload's displacement over a 0.75 s settle under its own weight (0.17-1.20 N).

For the in-scene cell the ramp direction is the **measured tool axis** (the flange
`+z`, which at `ready` reads `(0.000, -0.045, -0.999)`), i.e. the same "down the
tool axis, with gravity" load the fixture applies. The controls are P104's own
fixture **unchanged** (`logs/p104/fixture_probe.py`, `P104_FORMS="pinch_plate
quad"`), re-run in this batch so the table is same-batch.

The four M1/M2a tables that follow are in `RESULTS.md`.
