### P11-A physics-fidelity audit (2026-10-18, branch `p-supply`, offline): the fruit is a rigid body - the two-line regrasp "ejection" is a commanded-interference artifact (the keep-gap goes 1.7-17.5 mm inside the fruit, up to -18.4 mm), and the control-side keep-gap floor can remove it without touching physics; the fruit-side compliance is the top fidelity gap, not the fix

**Scope: read-only, no simulator** (the P10-D.1 policy battery was running throughout; no simulator
command, `pgrep`, or run-script invocation was issued). All writes under `logs/p11/`; no `src/`,
`scripts/`, `configs/`, `datasets/`, `Paper/` write; no commit. The prompt: the owner asks whether
the simulator's physics properties are realistic, prompted by the measured behaviour - the two-line
regrasp commands the pads to a keep-gap **narrower than the fruit** (the census sentence reads
1.7-17.5 mm in 15 of 18 B1 attempts; the enumerated pairs reach -18.4 mm) under the full squeeze
force, and the **rigid** fruit squirts out and falls to the floor (13/18 of the B1 class end
≈1.35 m below the belt top in the current census text - the prompt's 12/18 was an earlier revision
of the same census - in-hand |v|max 4.78-5.05 m/s = free fall from the 1.17 m belt top).

**What was audited (provenance-first).** The shipped tree (`src/fruit_sorting/*.py` + the
de-instanced asset), the Isaac 6.0 schema defaults (`omni.usd.schema.physx 110.1.13`), the repo's
own compliant-contact / soft-pad measurements, the P10-E census, and the repo paper library +
targeted web sources for the real values. The full tables are in `A_PHYSICS_AUDIT.md` §1-2.

**The 5 most unrealistic parameters.** (1) **The fruit is rigid**: `RigidBodyAPI`, no deformable
anywhere (grep = 0), no compliant contact on the fruit material - while real fruit flesh is
0.22 MPa (tomato) to 2.09 MPa (apple) and *yields* at 7-9 N (tomato) / ~26 N or 0.05 J (apple).
(2) **The finger contact stiffness 30 000 N/m** (`FRUIT_FINGER_COMPLIANCE`, `assets.py:62-63`): 8x
a tomato's whole-fruit stiffness (~3.9 N/mm at 1 mm), and 0.33 mm of penetration at the 10 N drive
limit - so of a commanded 1.7-17.5 mm interference, ~0.3 mm can be elastic and the rest becomes
fruit motion; it also sits at 87 Hz, above the repo's own ~40 Hz resolvable band at 1/120 s
(`common.py:13-19`). (3) **Mass/density**: `density * sphere * 0.82` (`fruits.py:655`) with
densities 780-900 kg/m³ gives fruit 8 % (apple) to ~40 % (tomato, 68.8 g vs a measured 83.7 g at
53 mm / 0.96 g/cm³) light. (4) **Restitution 0.02-0.2** (`fruits.py:665`) vs the measured
apple-apple 0.4 / apple-bin 0.5 (validated simulation calibration). (5) **The solver boundary**: the
depenetration/velocity caps are unauthored (the code comment says "unlimited"; the schema default is
3 m/s - flagged), and the pinch force is **not bounded by the 10 N drive** because `finger_joint2`
is a rigid **mimic** constraint with no drive (`openarm_flat_deinst.usda:3822-3844`) - the logs show
7.5-56 N pad-pad clamps and 176 N servo peaks.

**The artifact's key drivers.** The force servo's integral law closes up to
`FRUIT_DYNAMIC_FORCE_RANGE = 15 mm` when the contact collapses (every no-grasp row: `F_min = 0.00`,
`closed` 15-26 mm); the W1 re-seat then drives the pads back onto the fruit at
`keep_gap = squeeze_gap` (`tasks.py:8688`), i.e. 1.7-17.5 mm **inside** it (up to -18.4 mm), and the ratchet closes
another 3 mm of face separation per cycle. With a rigid fruit the position-servo interference has
nowhere to go: the drive pushes at its 10 N limit continuously, the contact spring can only absorb
0.33 mm, and the wedge geometry of a sub-diameter gap converts the squeeze into a free-axis launch
on a 70-105 g body (the drive's work 0.164 J vs the 0.05 J apple / ~0.01 J tomato damage energy).
The 120 Hz single-substep step resolves the contact as an impulse - and in **4 of the 30** no-grasp
attempts the solver diverges outright (|v|max 19.8-12 022 m/s, clean_slip 30.9-100.4 m).

**The real-world counterpart.** Under the same command a real fruit deforms instead of flying: a
tomato's contact stiffness (~3.9 N/mm at 1 mm, Hertzian from E = 0.30 MPa) reaches its measured
7-9 N damage threshold at ~2 mm of compression; an apple (E = 2.09 MPa, ~27 N/mm) tolerates ~26 N /
0.05 J. The failure mode is bruise/rupture/crush (tomato splits at the stem scar), and a real
force-controlled gripper stalls at its target force rather than walking 15 mm blind. Sim vs real:
the *command* is out of range, and the *rigid body* is what turns the out-of-range command into a
ballistic escape.

**Can the control-side fix remove the squirt without touching physics? Yes.** The trigger is the
commanded interference: floor `keep_gap` at the live measured extent minus 0-1 mm
(`pinch_width(sample, quat_now)`, `tasks.py:9783-9800`) at `tasks.py:8688-8692` and on the ratchet
(`tasks.py:8792-8801`), stop the chase with the existing `FRUIT_FORCE_REENTRY=1` (or cut
`FRUIT_DYNAMIC_FORCE_RANGE` to the fruit scale), and gate the re-seat on a plausible tactile hold -
all default-off, two-line-scoped via `_dynamic_profile`, so the shipped single-arm acceptance stays
byte-identical (the P10-C.3/W7-A pattern). With no interference there is no overlap, no saturated
push, no wedge - the residual failure is a slip of a marginal grip, not a 1.3 m fall. The honest
caveats: P10-E's named falsifier (the probe's own 6 mm lift as the alternative ejector) still has to
be run, and the control fix does not make the *grip* realistic (a real 10 N+ regrasp is a bruise) -
the realism question is separable from the failure class. Physics-side options for P11-C if the
owner wants the model itself: a per-class `compliantContactStiffness` on the fruit material
(tomato ~4 kN/m, apple ~25 kN/m), the measured soft-pad bodies already in the tree (k = 5 kN/m,
D2 lane 7/10 - a *precondition*, not a fix), or true deformable bodies (the build ships the
`OmniUsdPhysicsDeformableSchema` + `physxVolumeDeformableSim` tokens); any of them invalidates the
whole lineage (the references, the acceptance, the demo stores `demos_v11/v12/v12d/v13p` and the
checkpoints trained on them) - which is why the control-side move is first.

**Deliverable**: `logs/p11/A_PHYSICS_AUDIT.md` (the fruit/gripper/belt parameter tables with
file:line provenance and override paths; the real-world reference tables with URLs + confidence
marks; the rigid-body ejection mechanics + the deformable counterpart; the per-parameter verdict
table; the (a)/(b) fix options with their re-baseline costs; the honest limits; the provenance
index and reproduction commands). No tree change; no simulator run.
