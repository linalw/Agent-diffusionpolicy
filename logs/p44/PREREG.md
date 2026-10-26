# P44 PREREG — the speed profiles (the "VFA half"), with the force-delta half scoped out

Registered 2026-10-27, **before any edit or run**, on the P43-final tree `ca99148`
(`rl_env.py` `0cefb13d`, `tasks.py` `a1b3d673`, `control.py` `9384ff4f`,
`scene.py` `27e3d64a`; refs `8a399626` / `2246f83c`; working tree clean).
Evidence: `logs/p44/CAP_CENSUS.md`, `logs/p44/FRONTIER.md`,
`logs/p40/LIT_REVIEW.md`.

## 0. What the census changed

The owner's question was whether **not locking** the arm's acceleration/rotation
caps would let it sort fast. The census answers it: the joint velocity limits
carry **2.1x** headroom over the fastest reference, the effort limits **2.4x**,
and **the drive gains cannot change duration** because every leg is tick-clocked
by its profile (reproduced to +-1.4 %). What looks like a lock is a **profile
choice**, and **48 % of the cycle sits in three blocks** whose caps are 6.10 s of
parameter:

| block | time | of which | recoverable |
| --- | --- | --- | --- |
| `place` | 3.35 s (22.3 %) | 3.16 s = one jerk-limited profile at `v_max` 0.35 | **1.09-1.38 s** |
| `release` | 2.04 s (13.6 %) | **1.57 s = three open-loop holds** (20 + 120 + 48 ticks) | **0.63-1.02 s** |
| `lift` | 1.82 s (12.1 %) | 1.37 s = the profile at `v_max` 0.30 | **0.23-0.56 s** |

And **the friction cone does not bind** on `lift` (a = 1.0 of 1.962) or `place`
(1.089 of 4.273), so a faster leg is not a grip-risk by the cone.

## 1. The item, and what is *not* run

**Item S - the speed profiles** (default off, one knob each so the cells are
attributable):
- **S1 `place`**: `v_max` 0.35 -> 0.52 (and the associated `a_max` within the
  census's 0.61 ceiling);
- **S2 `release`**: the three open-loop holds (20 + 120 + 48 ticks) -> the
  measured-safe form (a 3 -> 2 tick finger settle and the 120-tick dwell -> 0,
  keeping the drop);
- **S3 `lift`**: `v_max` 0.30 -> 0.36 with `a_max` 1.9 (the census's ceiling).

**Not run, and why**: the **force-delta pose residual** (the "ForceDelta half")
has **no target** - the carry's failure class is closed (`logs/p42/SIM_LIMIT.md`)
and the cone does not bind, so a force-derived residual would act on a segment
that is not failing. It stays a **named remedy** if S1-S3 re-open a slip (E4
below is exactly that guard). No joint-limit/gain change is run (the census
shows it cannot move duration).

## 2. Arms and batteries

- Arms: **C** (shipped), **S1** (place), **S2** (release), **S3** (lift), and
  **S13** (S1+S2+S3) - the last is the candidate for adoption; the single cells
  attribute the time and catch a class change.
- Batteries: the acceptance (10 attempts, **seeds 5 and 6**), the species-locked
  pear battery, the two-line (the dense sheet). Same-tree control; interleaved
  inside one claim per battery.

## 3. Endpoints

| # | endpoint | pass |
| --- | --- | --- |
| **E1** | `s/attempt` on the acceptance + the pear | falls **>= 1.0 s** (median of the two seeds) |
| **E2** | `placed` per battery | **>= C - 1** in every battery |
| **E3** | the per-leg motion gate | every budget passes, no new over-budget leg |
| **E4** | **the grip guard**: the carry's slip/cone and any `fruit did not follow the gripper` row | unchanged or better; **any new grip-loss row fails the cell** |
| **E5** | the two-line | placed non-inferior, the pooled interval non-inferior, `190` PASS on its own reference |
| **E6** | failure reasons | no new reason |

## 4. Falsifiers

**F1** a new grip-loss row on a faster cell (the speed re-opens the class -> the
force-delta remedy is justified, and the cell is not adopted); **F2** a motion
budget fails; **F3** `placed` falls by > 1 in any battery; **F4** the release cut
loses the payload (a `cnp` with the release as the first divergence); **F5** a
new failure reason.

## 5. N, cost, and the claims

- **N** as the per-battery seeds (2 for the acceptance and the pear, 1 for the
  two-line); the scripted line is deterministic per configuration **per mode**
  (P39's F1 is the exception), so a same-configuration repeat is a determinism
  check, not a variance estimate.
- **Cost**: ~5 arms x 3 batteries x 5 min ~ 75 min of simulator, one claim per
  battery.
- **What may be claimed**: the **cycle time** per leg/phase and the **placed
  count** per battery, with the motion gate and the grip guard; **not** a
  cross-attractor rate, and **not** a claim about the joint limits or the gains.
