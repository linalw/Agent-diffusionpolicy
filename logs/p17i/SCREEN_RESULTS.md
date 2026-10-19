# P17-B Stage-M screen results (2026-10-19)

Status: **screen read complete**. M1 (the slide gate + bounded re-centre) **passes the mechanism
gate (K1) and is promoted to Stage P** (the outcome battery, launched: `logs/p17i/91_stage_p_driver.log`).
M2 (the freeze-side two-sided gate) **fails K1** (the walk does not fall; the outcome is worse) and
closes at Stage M. The seed-11 class census of M1 shows the K2 signature (the conserved-mass
re-draw) — the Stage-P battery is what decides it; nothing is adopted here.

## 1. The runs

| arm | knob | log | traces | outcome (seed 11) |
| --- | --- | --- | --- | --- |
| M0 (control, on disk) | — | `logs/p14b/10_seed11_trace.log` | `logs/p14b/traces_s11` | **11/20 ok**; no-grasp 7, carried 2 |
| M1 | `FRUIT_DYNAMIC_SLIDE_GATE=1` (+ `_DIAG=1`) | `logs/p17i/20_m1_trace.log` | `logs/p17i/traces_m1` | **10/20 ok**; no-grasp 5, carried 5 |
| M2 | `FRUIT_DYNAMIC_FREEZE_TWOSIDED=1` (+ `_DIAG=1`) | `logs/p17i/21_m2_trace.log` | `logs/p17i/traces_m2` | **8/20 ok**; no-grasp 8, carried 4 |

Env byte-matched to the control except the knob (two-line, patch sheet, balanced mix, mass base,
SEED 11, 20 attempts; `FRUIT_DYNAMIC_TRACE=1`). The read tool: `logs/p14b/trace_p14b_analysis.py`
verbatim via the adapter copies `logs/p17i/trace_m{1,2}_analysis.py` →
`logs/p17i/41_m1_walk.txt`, `42_m2_walk.txt`; the control's own output is
`logs/p17i/40_m0_control_analysis.txt`.

## 2. M1 — the mechanism (K1: PASS)

**The gate fires and the arrest is real.** 12 response rows across 7 fruit-attempts (fruit 0 ×3
attempts, fruit 6, fruit 12 ×2, fruit 8, fruit 13); every response drops the drift rate:

| attempt (fruit) | trigger rate | post-response rate | end |
| --- | --- | --- | --- |
| fruit 0 (att 1, placed) | 114.2 → 118.3 mm/s | **19.5 → 57.9 mm/s** | release |
| fruit 0 (att 6) | 124.4 → 134.3 | 12.8 → 54.2 | release |
| fruit 0 (att 14) | 128.8 → 137.1 | 38.4 → 19.7 | release |
| fruit 6 (att 19) | 91.4 → 96.9 | 46.3 → 25.5 | release |
| fruit 12 (probe1, ×2 atts) | 62.8 → 102.5 | 55.4 → 43.9 | release |
| fruit 8 (probe1) | 112.0 | 70.6 | phase |
| fruit 13 (att) | 86.5 | 34.5 | release |

**The walk falls.** The control's hold-walk B1s: **38.1 / 31.9 / 54.8 mm**; M1's hold-walk B1s:
**31.9 / 37.5 / 15.6 mm** (max 54.8 → 37.5, −32 %; median 38.1 → 31.9). The class distributions
(section H): ok walk max 15.0 (control 12.8), B1 median 23.8 (control 31.6).

**The fruit-tracked conversions (the rule's read).** The control's worst fruit class — **fruit 0
(orange, left): 0/3 placed** in the control (no-grasp at walks 38.1 / 54.8 / 0.0) — reads
**3/5 placed** in M1 (walks 15.0 ✓ / 31.9 / 1.3 ✓ / 15.6 ✓ / 0.0 ✓; the ≤ 20 mm band on 4 of 5
attempts, the branch moved). Fruit 11 (tomato, right): control 0/2 → M1 1/3 (one placed at
+0.349). Fruit 6 (tomato, left): control 0/2 → M1 0/2 (one converted to carried, walk 37.5 stays).

**The probe-1 side (b).** Departure phases: M1 takeoff_probe 4 / hold 5 / takeoff 1 / carry 3 vs
control 3 / 6 / 1 / 3 — not rising; probe-1 dz (section H): M1 ok median 6.6 mm vs control 8.4 mm —
not worsening.

**The class census (the K2 letter).** no-grasp **7 → 5 (−2)**; carried **2 → 5 (+3)**; ok
**11 → 10 (−1)**; the total failure mass **9 → 10 (does not fall)**. Two independent K2 triggers
fire at seed 11. The mechanism of the trade is visible in the fruit-tracked table: **fruit 12
(peach, right) regressed 2 ok → 2 carried, with the gate firing in its probe-1 phase both times**
(62.8/102.5 mm/s triggers; the re-centre during the lift probe); the lychee 7 partly regressed
(3/4 → one no-grasp at walk 0.3).

**Verdict (M1).** K1 PASS (the walk moves in the predicted direction; the arrest read confirms).
Promotion rule: (a) satisfied (the no-grasp count falls ≥ 2 with the fruit-0 conversions; the
≤ 20 mm band on the fruit-0 class; the arrest read ✓); (b) ✓; (c) ✓ (no new failure reasons; the
never-grasped count falls; ≤ 2 responses per attempt). **Promoted to Stage P** — where the K2
outcome question (does the seed-11 trade persist across seeds?) is decided on the battery.

## 3. M2 — the mechanism (K1: FAIL)

**The two-sided condition mostly attains** (18 `straddle` commits / 2 `fallback` of 20; e.g.
`commit=straddle tick=36 depth=63.7mm span=73.9mm ft=(7.33,2.29)N run=3 ship=19t/69.9mm` — the
straddle commits later/shallower than the shipped criterion).

**But the walk does not fall.** M2's hold-walk B1s: **38.1 / 47.5 / 25.2 / 25.9 mm** (a new 47.5
appears; the 38.1 and the 31.9-class are unchanged/reshuffled). **The outcome is worse on every
class**: ok 11 → 8, no-grasp 7 → 8, carried 2 → 4, total failures 9 → 12.

**Verdict (M2).** K1 FAILS ("no arm's walk moves in the predicted direction") → **closed at
Stage M**; the commitment form is a measured negative (the freeze-timing change does not arrest
the transient and degrades the outcome).

## 4. What is claimed, and what is not

* **Claimed**: the arrest mechanism works (M1); the recovery-form response converts the control's
  worst hold-walk fruit class; the commitment form (M2) is a negative; the seed-11 class census of
  M1 shows the conserved-mass re-draw (K2 signature).
* **Not claimed**: any adoption or any rate delta; the K2 verdict (Stage P's); any cross-arm rate
  comparison (single seeds; the outcome is quantized per AGENTS §2).
* **The next read**: Stage P (`run_stage_p.sh slide FRUIT_DYNAMIC_SLIDE_GATE=1 ...`; seeds 11/5/23
  + K3 doubles; primaries traced) → the total failure mass per seed and pooled vs
  `logs/p12a2/{10,11,12}_*_mass.log`; K2/K3/K4 then decide.
