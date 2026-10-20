# P18-D M1c screen results: the recalibrated slide gate at 90/2 (2026-10-19)

Status: **screen positive on both the mechanism and the seed-11 census — promoted to its Stage P**
(launched: `logs/p17i/94_stage_p_m1c_driver.log`). One seed, one run: the outcome read is Stage P's.

## 1. The arm

The P18-C operating point (`logs/p17c2/THRESHOLD_ANALYSIS.md`): `FRUIT_DYNAMIC_SLIDE_GATE=1`
with `_MMPS=90` (was 60), `_TICKS=2` (was 3), `_WINDOW_MM=60` (unchanged; never binds), plus
`FRUIT_DYNAMIC_SLIDE_GATE_DIAG=1`; traced; SEED 11, the mass-base scenario (env byte-matched to
the M0/M1 screens: `logs/p17i/run_m1c_screen.sh`).

## 2. The seed-11 census (the three arms)

| arm | ok | no-grasp | carried | total fail | responses |
| --- | --- | --- | --- | --- | --- |
| M0 control (on disk) | 11 | 7 | 2 | 9 | - |
| M1 (60/3) | 10 | 5 | 5 | 10 | 12 |
| **M1c (90/2)** | **14** | **4** | **2** | **6** | **8** |

The M1c recovers the control's carried count (2) while cutting the no-grasp 7 → 4 and adding
+3 placements (11 → 14). This is the pattern the M1's Stage-P lacked: no class re-draw into the
carried.

## 3. The mechanism (the fire read)

8 response rows across ~6 fired attempts; **every trigger is a genuine high-rate walk**
(99.8–155.4 mm/s at the trigger; the post-response rates 51.1–87.0 mm/s), matching the P18-C
prediction that 90/2 has **zero ok false-fires** on the control corpora (the shipped 60/3 fired
3–5/45 oks). The walk table (`logs/p17i/43_m1c_walk.txt`): the ok class walks 0.0–9.5 mm (all
inside the 12.8 band); the fails: B1 56.6/24.5/2.0, B2 25.2, carried 2.7/9.1.

The one 56.6 mm B1 walk is the residual the P18-C named (the recall ceiling: some walks fall
outside the monitored window/rate); it is a failure either way.

## 4. What is claimed / not claimed

* **Claimed**: at the P18-C operating point the trigger fires only on genuine walks (0 ok fires
  observed) and the seed-11 census improves on both classes (nc −3, carried flat, ok +3).
* **Not claimed**: the outcome (one seed, one run — the Stage-P's); any rate; any adoption. The
  M1's Stage-P already showed a single seed can reverse; this screen's job was to show the
  recalibrated trigger is not the M1's mis-calibrated one.
* **The next read**: `run_stage_p_m1c.sh` (seeds 11/5/23 + K3 doubles, primaries traced) →
  the total failure mass vs `logs/p12a2/{10,11,12}_*_mass.log`; K2/K3/K4 decide.
