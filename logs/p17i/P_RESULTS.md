# P17-B Stage-P results: the slide gate outcome battery (2026-10-19)

Status: **closed negative — K2 fires decisively on all three seeds. The slide gate
(`FRUIT_DYNAMIC_SLIDE_GATE`) is NOT adopted; the knob stays default-off.** The mechanism win
(the s11 arrest / walk read, `SCREEN_RESULTS.md`) stands as measured; the outcome side loses mass
on every class and every seed. This is the fourth mechanism-win / outcome-negative instance in the
close/carry family (P11-C, P15-M2, and this).

## 1. The battery

Seeds 11/5/23, ATTEMPTS=20, the mass-base scenario (two-line, patch sheet, balanced mix,
`FRUIT_PHYSICS_REAL_MASS=1`); each seed run twice (K3 doubles). Controls: the on-disk mass base
`logs/p12a2/{10,11,12}_*_mass.log`. Read: `logs/p17i/read_stage_p.py` →
`logs/p17i/60_stage_p_read.txt`.

| seed | arm | ok | no-grasp | carried | total fail | falls (rows) | partials | responses |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | control | 11 | 7 | 2 | 9 | 4 | 1 | - |
| 11 | slide gate | 10 | 5 | 5 | 10 | 5 | 0 | 12 |
| 5 | control | 17 | 0 | 3 | 3 | 0 | 0 | - |
| 5 | slide gate | 15 | 1 | 4 | 5 | 1 | 0 | 1 |
| 23 | control | 17 | 1 | 2 | 3 | 3 | 0 | - |
| 23 | slide gate | 12 | 4 | 4 | 8 | 5 | 2 | 5 |
| **pooled** | **control** | **45/60** | **8** | **7** | **15** | 7 | 1 | - |
| **pooled** | **slide gate** | **37/60** | **10** | **13** | **23** | 11 | 2 | 18 |

**K3: all three doubles bit-identical** ([fruit] streams, `[trace]` path lines excluded):
1016/1016, 1068/1068, 1067/1067. **K4: PASS — the current-tree knob-off control replay vs
`logs/p12a2/10_seed11_mass.log` is byte-identical (0 diff lines on the `[fruit]` streams;
`logs/p17i/71_k4_diff.txt`, chain `logs/p17i/run_k4_replay.sh`).** The tree drift since the
mass-base battery is zero, so the comparison above is the pure knob effect.

## 2. The verdict (K2)

**K2 fires on every letter**: the total failure mass does not fall (15 → 23; **every seed worse**:
11→10, 17→15, 17→12); the carried grows ≥ 2 (7 → 13, +6); the no-grasp grows ≥ 2 (8 → 10, +2).
The falls rise too (7 → 11 rows; the partials 1 → 2 — a non-rise condition fails). **Negative,
not adopted.**

The seed pattern is informative: **s11 (12 responses) is the mechanism-active seed** — its census
is the trade (nc 7→5, carried 2→5); **s5/s23 fire 1/5 responses** yet still lose ok (17→15,
17→12) — the cascade of a single re-shaped branch is enough to move the census, so the battery's
outcome movement is not a clean dose-response. Both readings point the same way.

## 3. The mechanism read (what stands)

* The arrest is real when it fires: 18 responses across the battery; the s11 read (12 responses,
  post-response rates 12.8–70.6 mm/s vs trigger 62.8–275.3) and the walk tail (54.8 → 37.5 mm max,
  median 38.1 → 31.9) are as recorded in `SCREEN_RESULTS.md`.
* **But the arrest is not durable (the Oracle's Gap C, confirmed in the survival read):** the
  release fires on the first below-band sample, so several attempts release at 54–58 mm/s and the
  payload then walks out during probe-1 (e.g. `left idx=6 probe1: rate_max=278.6 drift_max=116.4mm`);
  only some fired attempts survive (drift_max 0.8–18.4 mm in probe-1).
* The trigger's specificity is poor in practice: at s11 it fired on 7 attempts including 3 that
  placed, with peaks up to 275 mm/s — the 60 mm/s threshold sits inside the ok per-tick transient
  range (the P18-C analysis).

## 4. What is claimed / not claimed

* **Claimed**: the gate's arrest mechanism works as implemented; the outcome battery is negative
  on all three seeds and every class (K2); the knob stays default-off; the mass-base census
  correction (the CORRECTION in `logs/p15/OUTCOME_RESULTS.md`) is the prior for future batteries.
* **Not claimed**: any rate delta; any cross-configuration comparison (the outcome is quantized
  per AGENTS §2 — the per-seed class censuses are the read); no adoption recommendation.
* **The named residuals**: the trigger specificity (the P18-C threshold analysis), the arrest
  durability (a survival-gated release would be the bounded variant if the family re-opens), and
  the branch-cascade effect (a single response re-shapes the remaining attempts — the census
  movement is not dose-additive).

## 5. Provenance

* Runs: `logs/p17i/{50,51}_seed11_slide*.log`, `{52,53}_seed5_slide*.log`, `{54,55}_seed23_slide*.log`
  (chain `run_stage_p.sh`; driver `91_stage_p_driver.log`); controls `logs/p12a2/{10,11,12}_*_mass.log`.
* K3/K4: `logs/p17i/60_stage_p_read.txt`, `logs/p17i/71_k4_diff.txt`.
* Tree: `tasks.py` `3d88408d` (the P17-B knobs default-off), `rl_env.py` `60f46236`.
* The M screen: `logs/p17i/SCREEN_RESULTS.md`; the design `logs/p17/CAPTURE_LEVER_DESIGN.md`;
  the gate review `logs/p17i/ORACLE_GATE.md`.
