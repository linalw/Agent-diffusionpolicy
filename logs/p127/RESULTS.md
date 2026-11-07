# P127 - the three-lane scene's own baseline catches the flip's cost: 44/80 against 58/80, reverted

P126 shipped the third lane on the acceptance (7/10), the P123 tray census
(25/25) and the canary (7/10, P125's band). It never ran a **20-attempt
battery** on the new scene. This phase does - four seeds, the shipped two-line,
no instruction, the third lane as the only difference - and the scene reads
**44/80 = 55.0 % against the pre-P126 controls' 58/80 = 72.5 %**: **-17.5 points,
worse at all four seeds**.

| seed | two lanes (pre-P126 control) | three lanes (this battery) | delta |
| --- | --- | --- | --- |
| 5 | 16/20 | **12/20** | -4 |
| 6 | 12/20 | **8/20** | -4 |
| 101 | 15/20 | **11/20** | -4 |
| 202 | 15/20 | **13/20** | -2 |
| pooled | **58/80 = 72.5 %** | **44/80 = 55.0 %** | **-17.5 pts** |

The class moves with it: seed 6's grip losses go **2 -> 10** (`did not follow`),
seed 5's 8 -> 10, and the `no eligible` count shifts both ways (45 -> 22 at seed
5, 37 -> 49 at seed 6) because the scene's physics also re-times the supply. The
three-destination cell still works on the same tree (**11/20, ledger 11/11,
0 mis-sorted**) - **the destination is fine; the scene's physics is the cost**.

**The mechanism** is the one P71 established: a scene's collider set changes the
solver ordering and the release geometry (P71 measured an 8 mm release-y shift
from a rail change), so every grasp in the cell is re-drawn. The third body is
not physics-neutral just because the pick station is 140 mm away.

**Verdict: the flip is reverted** (for the second time, and now on the right
instrument): `FRUIT_OUTPUT_LANES` defaults to **2** again, the third lane stays
opt-in, the three references are restored to `30fb99f8` / `30fb99f8` /
`8952c320`, and the restore's acceptance reads **8/10, `fingerprint: matches`,
`190: PASS`** (421 `[fruit]` lines, the two-lane scene). The pre-P126/R126
archives and the P125 store stay: the store is still the three-lane candidate,
and the lane is a per-run capability.

## What this corrects in P126

P126's re-registration chose the **acceptance (10 attempts) + the tray census**
as the flip's carrier and demoted the canary. Both were the wrong instruments for
**the scene's physics cost**: the acceptance is one 10-attempt sample (7/10 vs
8/10 = one attempt, inside the spread) and the tray census measures the
destination, not the cell. The instrument that decides a scene flip is the
**20-attempt battery at >= 2 seeds (4 here) with same-seed controls** - the
repo's own standard for a rate - and the canary is a third, independent leg that
happened to be flat (P125: 56.7 % vs 55.0 %).

**Read rule: a scene flip is carried by a 20-attempt battery on the shipped cell
with same-seed controls; the acceptance is a smoke, the tray census proves the
destination, and the canary is an interface check.** A flip that changes the
collider set must show the battery first - the acceptance cannot see a
-17-point scene cost.

## Files

`logs/p127/S{5,6,101,202}.log` (the battery), `T5.log` (the three-destination
cell), `accept_restored.log` (the two-lane restore), `report.py`. No `src/` or
`configs/` change beyond the restore; the references are the pre-P126 records.
