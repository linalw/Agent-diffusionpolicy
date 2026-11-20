# The 2026-11-20 tactile set: what transfers to a 2-scalar parallel jaw, and what does not

Eleven papers in `~/linalw/Projects/Agent-diffusionpolicy/papers/20261120-tactile`
(read with `pdftotext`; the digests below are from the abstract/method/results).
The cell's tactile channel is **per-finger summed normal force** (2 scalars on
the OpenArm hand; 4 on the `cage4` ring), read at 120 Hz. No tactile image, no
contact centroid, no tangential force, no per-taxel map.

| paper | sensor | needs an image? | mechanism | transferable part |
|---|---|---|---|---|
| **CoorGrasp** (MPC, coordinated contact) | 3-axis force + contact pos/normal per fingertip (Tac3D) | no (consumes geometry) | approach MPC with a 0.2 N ceiling, phase switch on wrench residual, grasp MPC balancing `‖Gf‖²` with a ramped total force | **phase machine + force ceiling + a force ramp**; wrench allocation needs `G` (dead) |
| **GraspTune** (execution refinement) | visuo-tactile maps, 64×64, 100 Hz sim | **yes** | residual TCP motions (≤1.5 mm) to make contact bilateral; pause closure + shift away from the strong side on unilateral load | **the asymmetry rule** `sign(f_L−f_R)` → shift/pause; gains re-tuned, images dead |
| **High-Bandwidth Tactile-Reactive** | 200 Hz contact prob + 3-D contact position | no, but needs contact *position* | antipodal objective on the two contact normals + CFGD descent + a QP in joint space | only the **close/adjust/re-close latch** and "no judgement below a minimum normal force" |
| **LeTac-MPC** | one GelSight, 25 Hz | **yes** | learned latent dynamics + differentiable QP on **gripper aperture**, target = minimum width that just holds | the **actuator**: accel-limited aperture regulation on a force error, terminal-weighted horizon; the learned image model is dead |
| **Reactive Slip Control** | PzE vibration + PzR array, 12 pads | no (vibration 1-D) | detect slip, raise **internal force** along the null space (`Δτ = α Jᵀ f0*`), bounded α | the **response law** (symmetric, rate-limited squeeze ramp, no pose change); its 20 ms detector band is above our Nyquist |
| **TacMan-Turbo** | two marker pads, 120 Hz | **yes** | marker displacement → handle pose; constant-velocity prediction; velocity modulation | only "**constant-velocity, not higher-order**" prediction of a noisy signal |
| **TacRefineNet** | 11×9 taxel arrays | **yes** | Siamese ViT over current/target tactile images → wrist delta | the **observable-DoF discipline** (with 2 scalars at most a 2-D correction is servable) |
| **TactileAloha** | one GelSight + 3 webcams | **yes** | ACT chunked policy with tactile tokens + temporal-proximity ensembling | **drop the stale chunk on a contact discontinuity** |
| **Secure and Gentle Grasping** | 2 FSRs (one per jaw), 100 Hz | **no** | slip flag from a normalised force drop (`F < λ F_d` while the reference falls, λ=0.75) + a damage bound, robust MPC | **the λ-ratio slip test** and the probe-then-envelope procedure, both scalar-only |
| **T-Rex** | 5 fingertips × (6-axis wrench + depth map) | yes for the map | VLA with a fast tactile expert re-denoising the chunk tail at 20 Hz | **force alone carries 59 of 65 points** (the image is worth ~6) → put the value in the wrench/force channel; a 16-frame history at 120 Hz is 0.13 s |
| **Vi-TacMan** | marker pad per finger | **yes** | vision seeds; touch regulates to a **reference contact** by point registration | the **shape** (hold a reference contact, servo the deviation); the direction estimate needs the marker field (dead) |

## What survives on this cell

1. **A two-sided (bilateral) preload criterion** - CoorGrasp's ceiling, GraspTune's
   pause-on-unilateral, and High-Bandwidth's "no judgement below a minimum force"
   are the same rule: *a grasp is not formed until both pads carry force.* This is
   the one mechanism that needs nothing but `f0, f1`.
2. **Force regulation instead of position** (LeTac-MPC, Reactive Slip Control,
   Secure-and-Gentle): the actuator is a rate-limited squeeze target, never a
   pose change. Our `FRUIT_CARRY_FORCE` is already that; its *criterion* was the
   sum, which a one-sided pinch satisfies.
3. **The asymmetry `f_L − f_R` is the only geometry two scalars preserve**
   (GraspTune, CoorGrasp, Vi-TacMan). It is enough to say *which* side is
   unloaded, not enough to say where the object is.
4. **Drop the stale action chunk on a contact discontinuity** (TactileAloha):
   available (`FRUIT_REPLAN_ON_SERVO_END` exists) but the force collapse is late
   on the sum, so it is an abort, not a save.

**Ruled out by the sensor**: contact normals / antipodal geometry, wrench
allocation, contact-patch motion, marker registration, any learned tactile
encoder, the 30 Hz–2.5 kHz vibration band (above the 120 Hz Nyquist), and every
10-50 Hz tactile-image policy.

## What the measurement then said (RESULTS 4m)

`FRUIT_CARRY_BILATERAL=1` (the weakest pad's share replaces the sum in the carry
force loop) makes the carries **two-sided**: on the placed legs the one-sided
fraction reads **0.00** (the baseline's signature is P75's one-sided pinch), and
the payload-loss class falls **3 -> 1 in 16 attempts at 0.12** and the count is
**11/16 vs 10/16** (s101 4→6, s202 5→5) with **0.15/202 5→6**. The residual
failures are `grasped=False` - the pads closed on air, so **no tactile signal
exists to act on**. That is the same boundary P102 measured from the other side
(4 of 11 failures unreachable by any pad): the tactile lane is now closed for
the **carry**, and the open class is **acquisition**.
