# P9-A RESULTS: the go_ready skip-when-ready lever (B') - the gap falls 1.95 s, the success moves with the phase

Tree: `caa5f268` (the calibration edit; `tasks.py` `caa732d9`); retry chain `logs/p9c/`
(8 runs, all exit=0). The frozen pre-registration + the calibration amendment:
`logs/p9/PREREG_GOREADY_B1.md`. Readout: `logs/p9b/readout.py`.

## 1. The two batteries

**Battery #1 (tree `255f2819`): threshold under-fire.** A/B bit-identical everywhere; the
`FRUIT_READY_DIAG` readout reads `skip=0` on all 22 acceptance transits and every patch
transit - the no-op candidates sit at `pre_err` 0.0131-0.0135 (inside the 0.03 gate) but
`dg` 0.0131-0.0135, above the 0.01 sync gate the implementation borrowed. The lever never
actuated; the battery measured the threshold. This is the pre-registered kill with its
predicted cause.

**Battery #2 (the calibration retry, tree `caa732d9`, B' = `FRUIT_READY_SKIP=1
FRUIT_READY_SKIP_DG=0.02`): the skip fires - 18 `skip=1` events in the patch diag, each
removing the full transit (`catch_up=0 lift=0 blend=0 settle=0`, the 210 ticks gone).**

| scenario | arm | gap clean p50 | wall/real | slot/real/empty | outcome class | gate |
| --- | --- | --- | --- | --- | --- | --- |
| acceptance | A (knob off) | 5.2 s | 20.65 s | 10/10/0 | 9 ok, 1 g-n-p | 9/10 PASS |
| acceptance | **B'** | **3.25 s** | **18.88 s (-8.6 %)** | 10/9/**1** | **6 ok, 3 g-n-p** | **6/9 = 67 % < 0.75 FAIL** |
| patch (20 att) | A | 5.2 s | 20.74 s | 20/18/2 | 13 ok, 5 g-n-p | - |
| patch (20 att) | **B'** | **3.2 s** | **19.09 s** | 20/18/2 | **15 ok, 3 g-n-p** | - |

B' doubles are bit-identical (20/21 and 40/41); the alternative-arm endpoints stand from
battery #1 (bit-identical to A).

## 2. The verdict against the frozen endpoints

* **Primary (the gap must fall >= 1.5 s): PASS, large.** 5.2 -> 3.25 s (-1.95 s) on the
  acceptance and 5.2 -> 3.2 s on the patch battery; the wall falls 20.65 -> 18.88 s
  (-8.6 %), matching the code-exact prediction (-1.75 s) within the schedule-shift noise.
* **The span stays flat** (15.16 -> 15.59 s acceptance; 15.24 -> 15.29 s patch) - the gain
  is the transit, not a stretched task.
* **The `_recover_ready` count falls 1 -> 0** (acceptance) - the arm no longer needs the
  corrective re-blend.
* **Kill #2 FIRES: the acceptance floor (0.75 of ten) is missed in the B' arm (6/9 = 67 %).**
  Per the pre-registered rules the lever is **NOT ADOPTED**. The motion gate FAIL on B' is
  rate-only (all descents inside budget, no new failure reason).
* **No-harm chain PASS on the new tree**: the knob-off acceptance is 365/365 identical to
  `logs/p2d/90_accept.log`; the new-tree patch A is bit-identical to `logs/p9b/30_patch_A1.log`;
  the new-tree dense two-line re-record is bit-identical to the W7-A record
  (`logs/w8/70_w8b1_twoline.log`); selfcheck PASS. The calibration edit is default-inert.

## 3. The mechanism (measured) and the residual

The skip removes the *passive* arm's measured no-op transit (210 ticks, `dq_max`
0.0005 rad/tick). Because the driver's slot loop advances the belt by a fixed number of
ticks per slot, every skip shifts the next attempt's start ~0.21 m of belt travel earlier.
The catch is phase-calibrated to the shipped schedule, so the phase shift moves the outcome
**by scenario, in both directions**: the acceptance loses 3 placements (9 -> 6, all
carry-class, plus one slot that finds no eligible fruit), while the patch battery gains 2
(13 -> 15). Both are deterministic branches; per AGENTS.md section 2 the cross-configuration
success movement is a branch attribute, but the **acceptance floor is the pre-registered
adoption bar and it fails**.

**The named residual is the phase coupling, not the lever.** Two bounded follow-ups, in
order: (a) a **phase-compensation probe** - under B', sweep a small delay/lead
compensation (a few values) on the acceptance to test whether the success recovers while
the gap gain is kept; (b) a **conditional skip** - skip only when the next catch's phase
allows (needs the phase readout the diag can supply). Neither is pre-registered yet.

## 4. What this changes

* **The largest single-term timing win measured in this project: -1.95 s/attempt (-8.6 %
  wall) from a ~10-line, default-off change**, with the mechanism (the passive no-op) proven
  by instrumentation. The literature-side scouting (F3 "completion as a predicate") named the
  same mechanism from the industrial practice side; this is its measured form.
* **Not adopted** (the acceptance floor). The knob stack stays default-off; the calibration
  knob (`FRUIT_READY_SKIP_DG`) defaults to the shipped constant.
* **The coupling class now has three members** (the monitor's lock-on +8.8 %, the trickle's
  stocking-band cut, and this phase shift): the cell's per-attempt scheduling is tightly
  coupled to the belt phase, and any schedule change re-phases the catch. That is the
  standing obstacle for every timing lever, and it is now measured three times.
