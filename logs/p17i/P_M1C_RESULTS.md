# P18-D M1c Stage-P results: the recalibrated slide gate at 90/2 (2026-10-19)

Status: **closed negative — K2 fires (the pooled total failure mass does not fall: 15 → 17).
The M1c is NOT adopted; the knobs stay default-off.** The seed-11 improvement is real; the
seed-23 regression eats it; the mechanism read adds the durability residual (the probe-1 fires do
not arrest).

## 1. The battery

Seeds 11/5/23, the mass-base scenario, primaries traced + K3 doubles; the same controls
(`logs/p12a2/{10,11,12}_*_mass.log`); chain `run_stage_p_m1c.sh`; read
`read_stage_p_m1c.py` → `logs/p17i/66_m1c_read.txt`.

| seed | arm | ok | no-grasp | carried | total fail | responses |
| --- | --- | --- | --- | --- | --- | --- |
| 11 | control | 11 | 7 | 2 | 9 | - |
| 11 | M1c 90/2 | **14** | 4 | 2 | **6** | 8 |
| 5 | control | 17 | 0 | 3 | 3 | - |
| 5 | M1c 90/2 | 17 | 0 | 3 | 3 | **0** |
| 23 | control | 17 | 1 | 2 | 3 | - |
| 23 | M1c 90/2 | **12** | 7 | 1 | **8** | 5 |
| **pooled** | **control** | **45/60** | **8** | **7** | **15** | - |
| **pooled** | **M1c 90/2** | **43/60** | **11** | **6** | **17** | 13 |

**K3: all three doubles bit-identical** (1067/1087/1046 [fruit] lines). **The s5 arm fired 0
responses** — the run is the control's own replay (an internal no-op control) ✓.

## 2. The verdict (K2)

The pooled total failure mass **does not fall** (15 → 17) and the no-grasp grows +3 (8 → 11).
K2 fires → **negative, not adopted.** The per-seed structure is the finding:

* **s11 (the tight-supply seed, nc 7): −3** (9 → 6) — the screen's signal reproduced: the 8
  responses are all genuine walks (99–155 mm/s at trigger) with **0 ok false-fires**.
* **s23 (a near-perfect control seed, 17/1/2): +5** — of the 5 responses, **4 are probe-1-phase
  fires whose post-response rates are 64.4–198.8 mm/s — the response did not arrest the slide**
  (the Oracle Gate-2 Gap C reproduced): on attempts already sliding in the lift probe, the
  re-centre arrives too late and the branch cascades into 7 no-grasps.
* **s5: 0 responses, exactly the control.**

So the 90/2 trigger calibration fixed the *detection* problem (no ok false-fires) but not the
*response durability* problem: the hold-phase fires work; the probe-1-phase fires do not, and on a
seed with few hold-walks (s23) they only perturb the branch.

## 3. The capture family's closure

This is the fifth negative in the close/carry family (P15-M2, W8-B guard, R6-B retune, the M1
60/3, and now M1c 90/2). The consistent structure: the mechanism (the walk/arrest) moves, the
outcome does not improve, and the failure mass redistributes or grows. The remaining un-tried form
in this family would have to change the **response** (a durable arrest: e.g. a hold-phase-only
scope plus a survival-gated release) rather than the trigger; the data here say the probe-1-phase
response is the harm site and the hold-phase response alone has too few fires on the good seeds to
matter.

## 4. Provenance

* Runs: `logs/p17i/{60,61}_seed11_m1c*.log`, `{62,63}_seed5_m1c*.log`, `{64,65}_seed23_m1c*.log`
  (chain `run_stage_p_m1c.sh`; driver `94_stage_p_m1c_driver.log`); controls
  `logs/p12a2/{10,11,12}_*_mass.log`.
* K3/K4: `logs/p17i/66_m1c_read.txt` (K3 identical; the K4 tree identity is the P17-B closure's,
  same tree `tasks.py` `3d88408d`).
* The screen: `logs/p17i/SCREEN_M1C_RESULTS.md`; the operating point: `logs/p17c2/THRESHOLD_ANALYSIS.md`.
