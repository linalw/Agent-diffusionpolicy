# P19-B P9-A B1 results: the go_ready skip-when-ready lever (2026-10-19)

Status: **closed negative — the pre-registered acceptance floor kill fires (arm B 6/10 = 60 % <
the 0.75 floor). The wall saving is real and the placebo confirms its mechanism (the clock
shift), but the lever is NOT adopted and stays default-off.** The outcome loss has a measured
cause: the shifted belt phase produces an empty slot ("no eligible fruit" at y = +0.386 against
the ~0.40 m selection floor).

## 1. What ran

The frozen pre-registration `logs/p9/PREREG_GOREADY_B1.md` + the calibration addendum
`logs/p9a/PREREG_ADDENDUM_DG.md`: the first battery was a **byte-identical null** (A == B, 0 diff)
because the skip predicate missed on `dg` (measured 0.0131-0.0135 vs the frozen 0.01 tolerance;
`logs/p9a/80_ready_diag.log`). The v2 battery: arms **A** (shipped) / **B** (`FRUIT_READY_SKIP=1
FRUIT_READY_SKIP_DG=0.02`) / **P** (the Oracle's placebo: the same + `FRUIT_READY_SKIP_HOLD=230`),
on the acceptance (10 attempts) and the patch battery (20, SEED 5), each double-run (12 runs;
`run_b1_v2.sh`).

## 2. The primary endpoint (the gap) — PASS

| arm | acceptance gap p50 | patch gap p50 | acceptance span p50 | patch span p50 | doubles |
| --- | --- | --- | --- | --- | --- |
| A | **5.20 s** | **5.20 s** | 15.40 | 15.30 | identical |
| B | **3.25 s** | **3.20 s** | 15.60 | 15.25 | identical |
| P (placebo) | **5.15 s** | **5.15 s** | 15.50 | 15.50 | identical |

**The lever saves 1.95-2.00 s per gap** (the P9 prediction: 210 ticks = 1.75 s + the 20-tick
no-op catch-up = 1.92 s). **The placebo holds the shipped clock (5.15) while removing the same
micro-history** — so the saving is the **clock shift** the skip performs, exactly as designed. The
span is flat (B vs A: +0.20 s acceptance / -0.05 s patch). All six doubles bit-identical.

## 3. The outcome side — the kill

| arm | acceptance placed | patch placed |
| --- | --- | --- |
| A | **9/10** | 13/20 |
| B | **6/10** | 15/20 |
| P | 8/10 | 15/20 |

The pre-registered kill "the acceptance floor missed in either arm (0.75 of ten)" fires on **B:
6/10 = 60 %**. The cause is measured: **B run 1's attempt 2 logs "no eligible fruit"** — the
active fruits sit at pear y = -0.573, peach y = +0.175, pear y = +0.386, i.e. the only catchable
candidate is 0.386 m, just under the ~0.40 m selection floor at 0.12 m/s. The 1.92 s clock shift
moves the belt phase relative to the attempt slots, so a slot that the shipped clock fills with an
eligible fruit is empty under the skip. The rest of the difference is branch-specific carried
class (attempts 0/3/8 grasped-not-placed).

The patch battery runs the other way (B 15 vs A 13) — the effect is scenario-dependent, and the
pre-registered kill is on the shipped acceptance.

**The motion side**: every descent's |v|max ≤ 0.120 m/s (A 0.116/0.112, B 0.116/0.111,
P 0.116/0.120) — inside the budget; no new failure reasons.

## 4. The verdict and the named next

**Not adopted.** The B1 is a genuine wall-clock lever (-38 % of the inter-attempt gap) whose
outcome cost is a **supply coupling**: the shortened gap shifts the belt phase against the
feeder's absolute schedule and the selector's floor. The bounded follow-up (if the family
re-opens) is the coupled form — the skip with a floor/lead adjustment (or the feeder schedule
re-anchored to the skipped clock) — which would need its own pre-registration and the same
acceptance-floor kill. Until then the knob stays default-off and the shipped 9/10 + fingerprint
is untouched.

## 5. Provenance

* Runs: `logs/p9a/{90..95}_acc_{A,B,P}_{1,2}.log`, `logs/p9a/{96..9b}_pat_{A,B,P}_{1,2}.log`
  (chain `run_b1_v2.sh`; driver `9c_b1v2_driver.log`); the first (null) battery `50..63_*.log`;
  the diagnostic `80_ready_diag.log`.
* Pins: `tasks.py` `3d88408d`, `scripts/20_pick_place.py` `88fa42bf`, `configs/motion_reference.json`
  `b9e72ca7` (`70_b1_battery_pins.txt`).

---

### CORRECTION (2026-10-19; the Oracle Gate-3 re-read, `logs/p20/ORACLE_GATE3.md`)

1. **Two endpoints were collected and not reported.** The **wall per attempt**: A 15.40 + 5.20 =
   **20.60 s** vs B 15.60 + 3.25 = **18.85 s (-8.5 %)** — matching the P9 prediction (~19.0 s). The
   patch battery: A 15.30 + 5.20 = 20.50 vs B 15.25 + 3.20 = 18.45 (-10 %). The pooled
   inter-placement interval tracks the wall (the attempts run back-to-back); the `186` window rate
   is not computed here and is not claimed.
2. **The kill decomposes, and the record over-attributed it.** Arm B's acceptance loses 3: **one**
   empty slot (attempt 2) **+ three carried-class losses** (attempts 0/3/8, grasped-not-placed) —
   and the placebo P loses 2 of the same carried class, so the carried losses are not all the
   skip's. The empty slot is the supply-coupling instance; the carried class is a second,
   branch-level effect.
3. **The coupling is the lever's nature, not a defect.** 1.92 s x 0.12 m/s = 0.23 m ≈ 1-1.6 patch
   slices: the skip **re-rolls the presented slice** at every slot; a feeder re-anchor would hand
   the saving back as a wait, and the only coherent form is a **supply-conditional skip** (skip
   only when the next slot's presentation is comfortable). The design lane is drafting it
   (`logs/p20/B1C_DESIGN.md`).
4. **Scope note (binding for the goal):** the B1 is **single-arm by construction**
   (`tasks.py:3797`: `_active_session is None and not two_line_enabled()`), and the two-line's
   inter-attempt wall is only ~1.45 s of real motion (return 0.67 + prepose 0.71) — **the B1
   cannot serve the bimanual throughput goal**; its value is the shipped single-arm line only.
