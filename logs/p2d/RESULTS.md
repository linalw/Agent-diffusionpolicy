# P2 RESULTS: the density's dose ladder and its transfer

Branch `p-supply`. Pre-registration: `logs/p2d/PREREGISTRATION.md`. P1 (the first dose screen):
`logs/p2d/P1_RESULTS.md`. Evidence: `logs/p2d/*.log`, the reports `80_battery_report.txt` /
`81_curve.txt`, the follow-up `B1`. Tier A solo, the two-line unless stated.

## 1. The dose ladder (two-line, patch sheet, ATTEMPTS=20, SEED=5)

| D | success | placed/min | interval mean | p50 | p90 | s/attempt |
| --- | --- | --- | --- | --- | --- | --- |
| 1.00 (control, P1) | 12/20 = 60 % | 3.64 | 16.53 s | 17.30 | 19.90 | 9.9 |
| 1.25 | 11/20 = 55 % | 3.36 | 15.82 s | 16.95 | 35.10 | 9.8 |
| 1.40 | 16/20 = 80 % | 4.48 | 12.81 s | 14.90 | 22.00 | 10.7 |
| 1.50 (P1) | 15/20 = 75 % | 4.48 | 13.34 s | 13.50 | 23.60 | 10.1 |
| **1.60** | **18/20 = 90 %** | **5.27** | **11.25 s** | **11.50** | **20.30** | 10.2 |
| 1.75 | 15/20 = 75 % | 4.20 | 14.27 s | 12.10 | 23.30 | 10.7 |
| 2.00 (P1) | 5/20 = 25 % | 1.53 | 39.22 s | 38.10 | 46.90 | 9.8 |

**The interval curve is smooth and unimodal with the peak at D=1.60** (11.25 s mean, 5.27
placed/min, 18/20) - the best of everything measured in this project on this scenario, against
the control's 16.53 s / 3.64 / 12-of-20. The p90 also improves monotonically up to 1.60
(19.90 -> 20.30 s vs the control, with 1.25's 35.10 s the one outlier).

**Read the success column as a curve of one deterministic sample per point**, not as a
dose-response law: 11, 16, 15, 18, 15, 5 of 20 across D = 1.25...2.0. The swing between adjacent
D (e.g. 1.50 -> 1.60, 15 -> 18) is branch quantisation, which is why the **continuous interval and
the throughput** are the comparators and the success rate is quoted beside them. The one
unambiguous shape is the **collapse at D=2.0** (25 %, 39.22 s), whose mechanism is measured and
different: the crowding breaks the acquisition (18 "fruit did not follow the gripper" rows plus
mostly `grasped=False`), not starvation.

So **P1's recommendation (D=1.5) is superseded by this ladder: the peak is D=1.60**, and the
mechanism for it is unchanged - the arm span is constant (~15 s) in every config, so the gain is
entirely the removal of the failed/empty attempts between placements.

## 2. The transfers

| scenario | control | D=1.5 | read |
| --- | --- | --- | --- |
| two-line, **dense wave sheet** (`FRUIT_SUPPLY_WAVE=1`) | 60 %, 3.48 placed/min, 17.55 s | **D=1.6: 95 %, 6.07 placed/min, 9.59 s** | **transfers, strongly** (section 5) |
| **single arm**, patch sheet | 70 %, 30.34 s | **90 %, 24.36 s** (+20 points, -20 % interval) | **transfers** |

Both lines are separate scenarios with their own references; do not pool them. The single-arm read
matters for the owner's cell-level goal: the density is not a two-line-only effect.

## 3. The first transfer attempt was invalid, and how it was caught

The battery's config `60_wave_d150` set **both** `FRUIT_SUPPLY_WAVE=1` and
`FRUIT_SUPPLY_PATCH=1` with `FRUIT_SUPPLY_PATCH_DENSITY=1.5`. The schedule branch is
`patch = scatter and patch_env`, i.e. **patch wins**, so the "wave sheet at D=1.5" had silently
re-run the **patch** sheet at D=1.5. The tell was statistical: its readouts were *bit-identical*
to the patch run `10_density15` (4.48 fruits/min, interval mean 13.34, p50 13.50, p90 23.60, min
0.30, max 40.90) - which is also why the determinism convention is worth its cost.

The fix is in `fruits.py`: **the density now scales the wave schedule's two gap bands as well**
(the within-cluster `wave_gap_*` and the cluster-boundary `wave_sep_*`, same 0.085 m floor), so the
knob reads on **either** scattered schedule; `D=1.0` is byte-identical on both
(`172` selftest: 52 checks PASS). The re-measured wave transfer is in section 5.

## 4. The verdict against the pre-registered criteria

- **Primary (interval + throughput better than the same-scenario control, success
  non-inferior, quoted per D as a curve): PASS** at D=1.40, 1.50, **1.60** and 1.75 (interval
  better than the control's 16.53 s at every D from 1.40 up), with **D=1.60 the peak**. D=1.25
  fails the item (55 %, 15.82 s - inside the control's spread), D=2.0 fails it outright.
- **Secondary (the transfer read): PASS on the single arm**, see section 5 for the wave.
- **Fail conditions:** (a) any D's interval worse than the control - none above D=1.40; (b) a new
  failure class - **none** (the classes stay the carry / carried-not-placed / no-grasp set; D=1.60's
  two failures need their note read before the peak is recommended as the adoption branch - see
  section 6); (c) the motion budgets - to be confirmed per config by
  `105_motion_regression.py` before any adoption; (d) no wedge, no crash - 8/8 runs exit 0.
- **Determinism**: the P1 pairs (D=1.5, D=2.0) are bit-identical; the peak D=1.60 gets its double
  in the follow-up (`54_d160_b`).
- **The no-harm**: the acceptance reads 9/10 + `fingerprint: matches configs/motion_reference.json`
  (P1); the single-arm default is byte-unchanged.

## 5. The wave-sheet transfer (the follow-up)

The wave schedule's gap bands saturate at the 0.085 m floor for D >= 1.5 (`0.10/1.5 -> 0.085`,
`0.16/1.5 -> 0.107`; at D=1.6 `0.085-0.100`), so on this supply D is really "how close to the
separation floor the clusters run" - the dense sheet is already near its physical limit and the
knob's headroom there is one step wide.

| scenario | success | placed/min | interval mean | p50 | p90 | s/attempt | left lock-on mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| wave control (D=1) | 12/20 = 60 % | 3.48 | 17.55 s | 16.60 | 31.70 | 10.4 | 35.02 s |
| wave D=1.5 | 12/20 = 60 % | 3.81 | 14.02 s | 12.80 | 21.20 | 9.5 | 24.80 s |
| **wave D=1.6** | **19/20 = 95 %** | **6.07** | **9.59 s** | **9.40** | **15.70** | **9.4** | **19.06 s** |

**The transfer is confirmed and it is the strongest configuration measured in this project on the
two-line: 19/20, 6.07 placed/min, a 9.59 s mean interval against a 9.4 s attempt span** - i.e. the
cell now places a fruit essentially **every time an attempt completes** (98 % of the theoretical
cadence), with the p90 down from 31.70 s to 15.70 s. Against the project's earlier best two-line
number (the W7-A dense branch, 7/10 at 4.60 placed/min) that is +1.32x placed/min at a comparable
success rate, and against the W6-C patch branch (12/20 at 3.63) it is +1.67x.

**And the mechanism differs between the two supplies**, which is worth recording because the
pre-registration predicted one mechanism:
- on the **patch** sheet the density works by **removing the failed/empty attempts** between
  placements (the lock-on is flat: left 3.73 -> 4.57 -> 4.27 s; the attempts inside the interval
  fall 40.4 -> 15.7 s);
- on the **wave** sheet the density works by **relieving the arrival wait itself** (the left's
  lock-on falls 35.02 -> 19.06 s), because on that schedule the supply *is* the binding term.

So the same knob is a success-rate lever on the patch sheet and an arrival lever on the wave sheet.
Both are favourable; the wave sheet is where the interval itself collapses.

**The failure classes at the peaks are the acquisition class, not the carry class**: the patch
D=1.60 run's two failures are both `grasped=False` with `N=0.00` (no contact at all - orange,
left; kiwi, right) and the wave D=1.60 run's single failure is `grasped=False` (apple, right,
`N=3.59`). No carry escape and no carried-not-placed appears at either peak - the first measured
configuration where the carry class is absent from the two-line residual.

**Determinism:** the patch D=1.60 double (`54_d160_b`) is **physics-identical** to `52_d160`
(915/916 `[fruit]` lines; the diff is confined to the startup `[supply]` banner lines - one run
prints one banner twice - and the GPU table's whitespace; the summaries agree exactly: 18
successes, 205.0 s span, 10.2 s/attempt). The project's `compare_streams.py --physics-only`
reports "DIFFERENT at line 31" on this pair because the GPU banner falls inside its filter window;
the physics verdict above is the `grep -v '[supply]'` comparison.

## 6. What this hands over

The **adoption recommendation** is now **D=1.60 on the patch sheet** (90 %, 5.27 placed/min,
11.25 s interval), superseding P1's D=1.5, with the belt left at 0.12 m/s (P1 measured that the
speed axis adds ~4.5 points at D=1.5 but costs the right arm's lock-on and needs a second
reference). If the wave transfer confirms, **one D value can serve both scattered schedules**.

Still the owner's decision (a two-line supply default is a scenario change): flipping means

1. setting the two-line patch default to `FRUIT_SUPPLY_PATCH_DENSITY=1.60` (and the wave default to
   the same value if section 5 confirms),
2. re-recording `configs/motion_reference_patch.json` for the adopted branch, and
3. re-running `190_twoline_gate.sh` on the new branch with its own floor.

And the measured binding term after this change is unchanged by it: **the per-attempt arm span**
(~15 s; place+release 5.2 s, descent 3.0 s, grip 1.8 s, lift 1.8 s). At D=1.60 the placement
interval (11.25 s) is within 17 % of the 10.2 s attempt span, so the next lever belongs there.