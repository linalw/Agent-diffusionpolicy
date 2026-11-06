# P118 - the pocket station: voided by the owner's constraint, the reach probe kept

P118 began as the build of P117's promoted drop-out pocket station, gated on two
items (the reach at the pocket pick pose, and the shutter's actuation). The
owner's constraint of 2026-11-06 - **the dynamic scattered fruit pipeline must be
preserved: no diverter, stop gate, guide/limit or pause** - voids the pocket (it
stops the fruit for the pick), so the build was reverted: `src/` and `configs/`
are clean, no default changed, no reference re-recorded. The disposition is
recorded in `AGENTS.md` (P117 amendment / P119) and `logs/p119/RESULTS.md`.

**What is kept here**

| file | what it is |
| --- | --- |
| `reach_probe.py` | gate 1's static IK sweep (`logs/p90/station_map.py`'s machinery, no conveyor) |
| `reach_table.txt` | the compact `r x arm` table: passes, best margin, residual, nominal/achieved fingertip clearance |
| `reach_probe.log` | the T0 gate run (180 cells, both arms) |
| `reach_rows.json` | its rows |
| `reach_probe_full.log`, `reach_rows_full.json` | the 540-cell control grid (T0/NAT/C0, both arms) |
| `pocket_build.patch`, `pocket_build_v2.patch` | the reverted build, archived (the parent's two captures) |

**Gate 1's result (the one measurement this phase keeps).** Target:
`jaw_z = floor + r + 0.070` with `floor = belt_top - 0.100`, the delivered x band
`0.188-0.397`, the landing y spread `-0.05..+0.05`, r `14.7-34.8 mm`.
**PASS**: 41 of 180 `T0` poses pass `residual <= 6 mm` and `margin >= 0.05 rad`,
at every arm x r combination; the nominal fingertip clearance `r - 10.5 mm` is
`+9.5..+24.3 mm` at `r >= 20 mm`, so the kill does not fire. The pockets of
reachability are real: the best cells sit at `x = 0.274, |y| = 0.05` with
`+0.13..+0.18 rad` of joint margin, while `x = 0.397` fails (60-125 mm IK
residual) - i.e. the pose is reachable across most of the band but not at its
outer edge.

**What is void with the build.** The shutter's prismatic actuation (gate 2), the
static-pick sequencing and the drop/recovery path are not part of the tree: the
station stops the fruit, which the owner's constraint forbids. Their code and
the measured cells live only in the archived patches.
