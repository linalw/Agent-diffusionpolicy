# P11-C.2 RESULTS (2026-10-18): the from-open + chase-stop combination - negative (the chase stop hurts)

Pre-registration: `logs/p11c/PREREG_C2_CHASE_STOP.md`. Tree: `tasks.py` 810658b8 / `rl_env.py`
9a2c3872 (env-only battery; no code change).

| seed | A (shipped) | P11-C B (from-open only) | **C2 B (from-open + `FRUIT_FORCE_REENTRY=1`)** |
| --- | --- | --- | --- |
| 11 (primary) | 10/20, 7 falls | 13/20, 3 falls | **6/20, 6 falls** |
| 5 | 13/20, 4 falls | 10/20, 4 falls | 13/20, 3 falls |
| 23 | 16/20, 3 falls | 12/20, 3 falls | 12/20, 6 falls |
| pooled | 39/60 | 35/60 | **31/60** |

**Verdict: negative; the kills fire.** The primary endpoint (the falls fall >= 2/3 at seed 11)
fails (6 vs the control's 7); the pooled outcomes are the worst of the three arms; the seed-11
branch degraded sharply vs the from-open-only arm (13 -> 6). The acceptance no-harm PASSes
(9/10 + fingerprint matches + 385/385).

**Reading:** the chase stop (`FRUIT_FORCE_REENTRY=1`) is the wrong instrument for the depth
half - its contact-gated force mode changes the close/servo behavior beyond the chase (the
seed-11 branch's outcomes collapse), so the "arrival clean + depth capped" goal needs the
**depth floor** instead (cap `keep_gap` at the live extent), not the force-mode re-entry. The
corrected plow re-run (`logs/p11b/90/91_plow_fix_*`) now supports the depth reading: a TRUE
descend-onto-the-fruit ejects at the deeper interferences (tomato delta >= 10: 2/3; apple
delta >= 2: 3/3) and not at the shallow ones - so a floor at the extent (delta 0) sits below
the measured escape threshold for the tomato and at the edge for the apple.
**The named next (P11-C.3): the from-open arrival + the keep-gap depth floor (the extent +
margin), env-only if the floor knob is added or code if not.**
