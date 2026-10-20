# P21 results: the C1 on the two-line, the release trim, and the B1c (2026-10-20)

Status: **all three closed. The C1 does not transfer to the scripted two-line (28/60 vs 45/60);
the release trim passes both timing bars but fails the census guard (K2) — and its landing trace
shows the trim itself is CLEAN, so the loss is a branch shift; the B1c's acceptance reads 7/10
(the design's predicted branch) and its multi-seed part was invalidated by a scope error (the
two-line env — the skip is single-arm-scoped) and is re-running.**

## 1. The C1 on the scripted two-line — NEGATIVE (does not transfer)

The battery (`logs/p21c1/run_c1_twoline.sh`; 6 runs, K3 doubles identical on s11):

| seed | control (ok/nc/carried) | C1 0.04 | delta |
| --- | --- | --- | --- |
| 11 | 11/7/2 | 7/12/1 | -4 |
| 5 | 17/0/3 | 11/7/2 | -6 |
| 23 | 17/1/2 | 10/6/4 | -7 |
| **pooled** | **45/8/7** | **28/25/7** | **-17** (nc 8 -> 25) |

The slow close (the face speed capped at 0.04 m/s) is **incompatible with the never-stop dynamic
catch**: the no-grasp class explodes (8 -> 25). The direct-interface effect (carried 48 -> 27,
stratified p = 0.0026) is **interface-specific** and does not carry to the moving catch. The C1
stays default-off; its value is the direct/policy path only.

## 2. The release tail trim — timing PASS, K2 FAIL (not adopted)

The battery (`logs/p21i/run_release.sh`; A/B x seeds 11/5/23 x doubles; `FRUIT_PLACE_TRACE=1`):

| endpoint | A | B | bar |
| --- | --- | --- | --- |
| `[cycle] release` p50 | 2.31 s | **1.31 s** | P1 <= 1.45 **PASS** |
| `[cycle] total` p50 | 15.02 s | **14.10 s** | P2 <= 14.50 **PASS** |
| placed | 90/120 | **62/120** | K2 >= 90/120 **FAIL** |
| nc / carried / falls | 16 / 14 / 14 | **32 / 26 / 38** | K2 (the census) **FAIL** |

**The mechanism split (the design's own guard, `[place trace]`):** the B arm's landings are
**cleaner** — roll p50 206 -> 102 mm, bounce 3.3 -> 1.5 mm, skid 70 -> 54 mm, settle 708 -> 600 ms
(n = 90 A / 58 B). The release trim does not damage the release. **The loss is the branch**: the
-1.00 s/attempt clock shift re-rolls the presentation against the feeder's absolute schedule (the
same systemic coupling the B1 measured at -1.92 s/gap), and the re-rolled branch carries more
no-grasp/carried/falls draws. The named fix is the **release + supply-clock resync** (the B1c's
`FRUIT_READY_SKIP_RESYNC` mechanism applied to the span saving) — a new bounded knob.

## 3. The B1c — the acceptance valid, the multi-seed part voided by scope

The acceptance (single-arm, `FRUIT_READY_DIAG=1`): **A 9/10, B 7/10, P 8/10** — exactly the
design's predicted branch (`repairing the poll gives 7/10`); the gaps A 5.20 / B 3.30 / P 5.15 s
(the skip works; the resync credits, `credit=` rows).

**The scope error:** the multi-seed part of my chain used the two-line env (`FRUIT_BIARM=1
FRUIT_BIARM_TWOLINE=1`) — but the skip is single-arm by construction (`tasks.py`: `scope =
_active_session is None and not two_line_enabled()`), so those 9 runs never skipped
(`skip=1` rows 0, `credit=0`, census == control). **The corrected single-arm patch battery is
re-running** (`logs/p20i/run_b1c_singlearm.sh`; A/B/P x seeds 11/5/23).

## 4. The systemic finding

Two independent levers (the B1's gap skip -1.92 s/gap; the release's span trim -1.00 s/attempt)
changed the wall and moved the outcome census, while their direct mechanisms were clean (the B1's
placebo isolates the clock; the release's landing traces are better). **On this supply the
presentation is phase-locked to the feeder's absolute schedule, so any per-attempt wall change
re-rolls which fruits are presented.** Every future wall lever must either carry a supply-clock
resync or be read as a branch draw. This is the supply-coupling discipline the P21 arc adds.

## 5. Provenance

* The C1: `logs/p21c1/{10..15}_*_c1_c1b*.log`, chain `run_c1_twoline.sh`;
  read = the census script (this doc) + `logs/p17i/read_stage_p_m1c.py` (the same shape).
* The release: `logs/p21i/{10..13}_*_rel[AB]_*.log`, chain `run_release.sh`; `read_release.py`.
* The B1c: `logs/p20i/{20,21,22}_acc_*.log` + the mass runs (voided); `run_b1c_battery.sh`;
  the corrected chain `run_b1c_singlearm.sh`.
* Pins: `tasks.py` `455f1a33`, `rl_env.py` `88bcde27`, checkpoint `61da390a`.
