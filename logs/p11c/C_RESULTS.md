# P11-C RESULTS (2026-10-18): the re-seat arrival geometry (from-open) - the mechanism partially works, the class re-draws, NOT adopted

Pre-registration: `logs/p11c/PREREG_REGRASP_ARRIVAL.md` (frozen). Tree: `tasks.py`
**810658b802d22bbd63013726fc78af81**, `rl_env.py` **9a2c38721b32f0af91371ca3e8809196**
(`TASKS_MD5` matching). Branch `p-supply`.

## 1. The battery (6 runs; the A runs verified byte-identical to the flip records)

| seed | A (the shipped two-line) | B (+ `FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1`) |
| --- | --- | --- |
| **11 (primary)** | 10/20, interval 18.70 s, cycle 13.73 s, **7 falls** | **13/20 (+3), interval 14.73 s (-21 %), cycle 15.06 s (+9.7 %), 3 falls + 1 partial + 1 blowup** |
| 5 (control) | 13/20, 15.07 s, cycle 14.58 s, 4 falls | 10/20 (-3), 19.84 s (+32 %), cycle 14.44 s (-1 %), 4 falls |
| 23 (control) | 16/20, 11.22 s, cycle 14.79 s, 3 falls | 12/20 (-4), 16.36 s (+46 %), cycle 14.94 s (+1 %), 3 falls |
| pooled | **39/60** | 35/60 |

**The no-harm**: the three A runs replay the P10-C.3 flip records **0 diff lines** (modulo the
reporting rows) - the diff is inert at knob-off on the shipped two-line path. 105 PASS on all
three B runs (65 %/50 %/60 %); no new failure reasons (the same two classes).

## 2. The mechanism (the P10-E falsifier's task-level read)

* **The regrasp cycles changed**: the seed-11 B run carries 14 ` [from-open]` markers (the
  W1 re-seat ran the new arrival on 14 cycles).
* **The falls halved at the primary seed**: seed 11 A 7 falls -> B 3 falls (+1 partial drop
  -185 mm +1 solver blowup). **They did NOT disappear** (the prereg's kill 2: "the
  falls/blowups do NOT disappear on B" - **the kill FIRES**).
* **The class re-drew**: seed 11: no-grasp 8 -> 6, carried 2 -> 1, ok 10 -> 13; seed 5:
  no-grasp 4 -> 6; seed 23: no-grasp 1 -> 5. The fix's opening/closing disturbs the marginal
  grips at the controls (exactly the `C_DECISION.md` prediction: "a re-seat that does not
  press in cannot restore a lost grip - the class may shift; the rate may not improve").

## 3. The verdict (per the frozen prereg)

**NOT adopted.** The kill 2 fired (the falls did not disappear); the pooled outcome moved
-4 (39 -> 35/60) and the pooled interval +13 % (14.99 -> 16.98 s), while the cycle rose +9.7 %
at the primary (beyond the +5 % non-inferiority margin). The seed-11 branch is a genuine
positive (+3 outcomes, -21 % interval, the falls 7 -> 3) - but it is ONE branch of three, and
the controls moved against B; per the one-sample discipline the pooled reading governs.

**The mechanism reading (honest):** the fix does what it was built to do *at the arrival* -
the falls at the primary seed halve - but it **trades the falls for lost marginal grips**
(the no-grasp class rises at the controls), because the horizontal close still runs to the
**chased** `keep_gap` (the sub-width depth the force servo walked): the arrival is clean, the
depth is not. **The named next iteration (P11-C.2): the fix + the chase stop together**
(`FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1` + `FRUIT_FORCE_REENTRY=1`), so the horizontal close
lands at the *recorded* depth instead of the chased one - the prereg's own optional arm,
now the measured requirement. Also named: the cycle cost (+9.7 % at the primary) comes from
the extra open-close phases; a chase-stopped variant shortens the gap walk and may recover
part of it.

## 4. What stands / what was withdrawn

* Stands: the P10-E diagnosis (the class's B1 chain), the probe's `belt`/`air` negatives
  (close-from-open never ejects), the parameter insensitivity, the drop baselines, the
  P11-A audit's property findings.
* Withdrawn (the P11-B Oracle R1): the probe's plow escape (0.202 m/s) as the re-seat's
  mechanism - the probe ran a rise-and-return, not the shipped descent; the corrected re-run
  (`logs/p11b/90_plow_fix_*`) decides what a true descent does. This battery's task-level
  data (the falls 7 -> 3 at the primary) is independent evidence that the arrival geometry
  matters.

## 5. The no-harm bar

| item | status |
| --- | --- |
| the knob-off two-line pair (A) vs the flip records | **PASS**: 0 diff lines x3 |
| the shipped acceptance on the P11-C tree | the chain runs after the plow-fix re-run (the claim serializes); to be recorded in the wrap |
| `selfcheck.sh` / `172` | **PASS** (the implementation lane) |
