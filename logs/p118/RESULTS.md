# P118 results - the pocket station: gate 1 passes, the station is VOID under the owner's constraint

**VERDICT (first line).** The drop-out pocket station was built and both of
P117's named gates were spent, and then the owner's constraint of 2026-11-06
closed the lane: **the dynamic scattered fruit pipeline must be preserved - no
diverter, stop gate, guide/limit or pause.** The pocket is a stop gate (the
selected fruit is dropped out of the stream and the line is held for the static
pick), so the station is **VOID**: the build was reverted (`src/` and `configs/`
clean, no default changed, no reference re-recorded), no ten-attempt proof was
run, and only gate 1's reach table is kept as evidence. Gate 2's actuator timing
is kept as a **fixture datum**, not as a station.

---

## 1. Gate 1 - the reach at the pocket pick pose (kept)

`reach_probe.py` is `logs/p90/station_map.py`'s machinery (itself P66's): the same
`solve_to` recipe, the same `pad_lowest_z` read, the same attitudes, both arms,
and the scene built **without the conveyor** (`environment`, `pedestal`,
`robot`) because the question is the arm's capability at the pose, not the path
through the line. Target: the fruit rests on the pocket floor at
`floor = belt_top - 0.100`; its centre is `floor + r`; the jaw target is
`floor + r + 0.070` (top-down `T0`, the attitude the descent holds). Grid: the
delivered x band `0.188, 0.24, 0.274, 0.32, 0.397`; the measured landing y
spread `-0.05, 0, +0.05`; r `14.7, 18.0, 21.5, 25.0, 30.0, 34.8` mm.

Criterion (`PREREG` of the phase, pinned before any cell): **primary =
residual <= 6 mm AND margin >= 0.05 rad**. Reported beside it: `qerr <= 2 deg`
(T0/C0) or `tilt <= 5 deg` (NAT), `pad_lowest_z - floor >= 2 mm`, and the pose's
own extra clause - the **fingertip clearance** `jaw_z - 0.0805 - floor`, whose
nominal value is `r - 10.5 mm`. **Kill**: no pose passes the primary clause at
any r, or the nominal fingertip clearance is negative at r >= 20 mm.

| r [mm] | arm | n | pass | best margin [rad] | @ x,y | best residual [mm] | nominal tip [mm] | achieved tip [min,max] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 14.7 | left | 15 | 3 | +0.175 | 0.274, +0.05 | 6.0 | 4.2 | [-8.2, +27.7] |
| 18.0 | left | 15 | 3 | +0.183 | 0.274, +0.05 | 6.0 | 7.5 | [-4.9, +30.5] |
| 21.5 | left | 15 | 4 | +0.179 | 0.274, +0.05 | 5.8 | 11.0 | [-1.3, +33.5] |
| 25.0 | left | 15 | 4 | +0.168 | 0.274, +0.05 | 5.8 | 14.5 | [+2.3, +36.4] |
| 30.0 | left | 15 | 3 | +0.149 | 0.274, +0.05 | 5.9 | 19.5 | [+7.6, +40.7] |
| 34.8 | left | 15 | 3 | +0.130 | 0.274, +0.05 | 5.9 | 24.3 | [+12.8, +44.7] |
| 14.7 | right | 15 | 3 | +0.173 | 0.274, -0.05 | 5.8 | 4.2 | [-8.2, +27.7] |
| 18.0 | right | 15 | 4 | +0.181 | 0.274, -0.05 | 5.8 | 7.5 | [-4.9, +30.5] |
| 21.5 | right | 15 | 4 | +0.182 | 0.274, -0.05 | 5.9 | 11.0 | [-1.3, +33.5] |
| 25.0 | right | 15 | 4 | +0.170 | 0.274, -0.05 | 5.9 | 14.5 | [+2.4, +36.4] |
| 30.0 | right | 15 | 3 | +0.150 | 0.274, -0.05 | 5.9 | 19.5 | [+7.7, +40.7] |
| 34.8 | right | 15 | 3 | +0.131 | 0.274, -0.05 | 6.0 | 24.3 | [+12.8, +44.8] |

**Gate 1 passes**: 41 of 180 `T0` poses pass the primary clause (3-4 of 15 at
every arm x r); the nominal fingertip clearance is `r - 10.5` = `+4.2 .. +24.3`
mm (so `+9.5 .. +24.3` at r >= 20), and the kill does not fire. **But the
coverage is a window, not the band** - by x:

| x [m] | T0 pass | best margin [rad] | residual range [mm] | reading |
| --- | --- | --- | --- | --- |
| 0.188 | **0/36** | +0.028 @ j3 | 5.7-6.0 | the margin fails (j3), not the solve |
| 0.240 | **12/36** | +0.160 @ j3 | 5.7-6.0 | reachable |
| 0.274 | **20/36** | +0.183 @ j6 | 5.6-6.0 | the best column |
| 0.320 | **9/36** | +0.065 @ j3 | 5.6-60.2 | reachable, degrading |
| 0.397 | **0/36** | +0.002 @ j2 | 32.3-127.3 | unreachable |

So a pocket pick pose existed for the **middle ~third** of the delivered band
(x 0.24-0.32) and **not at either edge** - a real limitation of the 100 mm-lower
pick pose, independent of the owner's constraint. The full three-attitude
control grid (540 cells) is in `reach_rows_full.json`: `T0` 41/180 primary,
`C0` 140/180 primary / 128/180 full, `NAT` 160/180 primary / 0/180 full (its
tilt clause is the belt-aligned control's own failure). The achieved tip column
above is reported, never gated: an unreachable cell's 60-125 mm IK residual
lowers the jaw, which is a reach failure, not a fingertip-clearance failure.

## 2. Gate 2 - the shutter actuator (fixture datum only; void as a station)

The mechanism was built as the build would have it: the transport belt split into
two segments with the **0.148 m** gap (P117's authoring; each segment's surface
value divided by **its own** y-length - P117's scaled-local-frame lesson), the
shutter a **kinematic, belt-like** plate (a static plate stops a fruit in
0.6 mm) on a `UsdPhysics.PrismaticJoint` (axis Y, limits `[-0.148, 0]`, position
target) and a trapdoor floor on a second joint. PhysX **rejects a joint between
two non-dynamic bodies** ("cannot create a joint between static bodies"), and the
kinematic form is required for the surface velocity, so the USD joint carries the
axis/limits/target and the pose is written by a **bounded trapezoid** (v_max
1.5 m/s, a_max 12 m/s^2) along that axis - the time is produced by the travel,
not a teleport.

Measured (one cell, `logs/p118/shutter_servo.log`): **open 0.183 s and close
0.183 s** (22 ticks each; the triangular profile's peak 1.35 m/s, predicted
`sqrt(a*d)` = 1.33 m/s), against the **0.833 s** fast cadence - a **0.65 s**
margin. The open's belt travel is `0.12 * 0.183 = 22 mm` against the 74 mm
half-mouth -> **52 mm** arrival clearance. The closed shutter transports a
69.6 mm apple at **1.00x** the commanded surface speed. The **dynamic-drive
control did not move** (0.002 m in 2.0 s): a dynamic plate in the
zero-clearance slot is friction-locked between the adjacent slabs, which is why
the build used the kinematic servo. These are **fixture data**; the station they
would have served is void.

## 3. Why the station is void, and what is in the tree

The owner's constraint (2026-11-06) preserves the **dynamic scattered
pipeline**; a drop-out pocket stops the selected fruit and (to make the pocket
pickable through the closed plate) holds the line for the pick window - a stop
gate/pause in both senses. The station is therefore **VOID**, and the build was
reverted:

* no `src/` or `configs/` change survives (`git status` clean on both), no
  default moved, no motion reference re-recorded;
* the build is archived at `logs/p118/pocket_build.patch` and
  `pocket_build_v2.patch` (the parent's two captures);
* one 1-attempt smoke was run before the stop; it is **not** a proof and no
  number from it is claimed here.

## 4. No-harm (the reverted tree)

`scripts/accept.sh` reads **8/10, 9.0 s/attempt, `fingerprint: matches
configs/motion_reference.json`, `190: PASS`**, and its **421 `[fruit]` lines are
421/421 byte-identical** to `logs/p117/accept_final.log` (`logs/accept.log`,
copied to `logs/p118/accept_revert.log`); `scripts/selfcheck.sh` **PASS
(0 failures, 1 skipped)**; `106_index_audit.py` **OK**;
`107_collect_merge_test.py` **PASS (21 checks)**. References
`30fb99f8` / `30fb99f8` / `8952c320` untouched.

## 5. Files

`logs/p118/`: `reach_probe.py` (gate 1), `reach_probe.log` + `reach_rows.json`
(the 180-cell T0 gate run), `reach_table.txt` (the table above),
`reach_probe_full.log` + `reach_rows_full.json` (the 540-cell T0/C0/NAT
controls), `pocket_build.patch` / `pocket_build_v2.patch` (the reverted build),
`accept_revert.log` (no-harm), `README.md`, this `RESULTS.md`. No `AGENTS.md`
paragraph is added by this record: the owner's withdrawal and the P119 belt
result are already recorded there. Evidence commit `3bb1335` (the gate-1 files);
this file follows.
