# P207/P208 results - the emitted joint target's rate cap and the servo hand-back

The owner's report: occasional very distorted actions and a completed sort followed by
twitching. P203 removed the post-sort idle. This phase is about the **in-task** outlier
and the command stream that produces it.

## 1. The instrument and the defect

`FRUIT_POLICY_TRACE=1` prints one `[cmd]` row per executed waypoint (every 4 control
ticks at `FRUIT_POLICY_ACTION_HOLD=4`). The row carries the emitted target, the
measured joints and, with the cap armed, the **requested** target. The control cells:

| cell | per-waypoint target step p50 | p95 | max | > 0.10 rad |
|---|---|---|---|---|
| C303 (6 eps) | 0.021 | 0.136 | 0.660 | 6.2 % |
| C808 (6 eps) | 0.028 | 0.198 | **2.633** | 13.6 % |

The arm cannot follow a 2.6 rad step: the measured step is capped by the joint's
5.45 rad/s (0.182 rad per 4 ticks) and the visible response is the "weird pose". The
p95 is already above the 0.10 rad a reader calls smooth.

**One measurement correction:** the analyzer only differences adjacent printed rows
(`dt == 4`). A servo hand-back skips many ticks; three of C303's 780 adjacent pairs
spanned 248/696/940 ticks and owned its 0.508/1.078 rad "max". The achieved/target
ratio also excludes measured steps above the arm's own 5.45 rad/s (a physics event, not
a tracking read); unfiltered it read impossible ratios > 1.

## 2. The cap

`FRUIT_POLICY_TARGET_RATE=<rad/s>` (default 0 = the shipped untouched target) ramps
each joint from the last **emitted** target toward the request by at most
`rate/120` per tick. The state is per arm, re-seeded from the measured joints at every
attempt and whenever a servo hands the hand back. A request already inside the cap is
emitted exactly; it is not a filter.

| arm | seed | placed | emitted p95 / max | > 0.10 | request p95 / max | residual p95 / max | binding |
|---|---|---|---|---|---|---|---|
| C | 303 | 3/6 | 0.136 / 0.660 | 6.2 % | - | - | - |
| R2 (2.0) | 303 | 1/6 | 0.067 / 0.067 | 0.0 % | 0.185 / 1.024 | 0.278 / 1.043 | **76.6 %** |
| R4 (4.0) | 303 | 2/6 | 0.061 / 0.134 | 2.6 % | 0.087 / 0.730 | 0.058 / 0.681 | 24.7 % |
| C | 808 | 4/6 | 0.198 / 2.633 | 13.6 % | - | - | - |
| R4 | 808 | 4/6 | 0.134 / 0.156 | 28.4 % | 0.412 / 2.621 | 1.289 / 2.259 | 54.7 % |
| R5 (5.45) | 808 | 3/6 | 0.181 / 0.182 | 7.8 % | 0.171 / 2.001 | 0.220 / 1.956 | 24.0 % |
| **R5 (5.45)** | **303** | **4/6** | **0.093 / 0.182** | **4.2 %** | 0.097 / 0.544 | 0.081 / 0.937 | **15.7 %** |

**Pooled count (report only, 12 episodes per arm): C 7/12, R5 7/12, R4 6/12.**
R5 is equal to the control pooled, +1 at seed 303 and -1 at seed 808 - a draw on the
count and a real reduction in the command tail. The seed-303 cell is also the cleanest
mechanism read: p95 0.136 -> 0.093, max 0.660 -> 0.182, binding 15.7 %, achieved p95
0.030 -> 0.022.

**What the table says.** The cap works: R4/R5 cut the emitted **max** by 93-94 % and
R5 preserves the control's p95 (0.181 against 0.198) while removing the tail. R5 binds
only 24 % of waypoints (the requests above the arm's own joint-speed limit), so it is a
**hardware-consistent** cap, not a speed limit. R2 binds 76.6 % - it is a speed limit -
and its count is not a claim.

The `> 0.10 rad` fraction is **not** a monotone smoothness metric once the cap sits
above 0.10: a cap at 0.134 or 0.181 turns one 2.6 rad outlier into several 0.13-0.18
rad steps, so the fraction can rise while the max falls 15x. Quote the max/p95 and the
binding fraction together.

## 3. The state bug the cap exposed

At `logs/p207/C_s303.log` t=996, after the place servo declined, the policy chunk
generated **before** the servo commands j1 -1.066 while the measured j1 is +0.684
(1.75 rad): the chunk is stale by the servo's whole displacement. The cap smooths it
into a ~1 s sweep but cannot remove it. `FRUIT_REPLAN_ON_SERVO_END=1` drops the
remaining chunk, forces one fresh observation (the hand-back can land between 4-tick
observation phases), and re-plans. At seed 808:

| arm | placed | emitted p95 / max | residual p95 / max | binding | replans |
|---|---|---|---|---|---|
| R4 | 4/6 | 0.134 / 0.156 | 1.289 / 2.259 | 54.7 % | 0 |
| R4P = R4 + replan | 3/6 | 0.134 / 0.134 | **0.344 / 2.431** | 46.1 % | 10 |

The residual p95 falls 73 % and the achieved step p95 falls 46 % (0.091 -> 0.049), but
the residual **max** rises 7.6 % (a *new* 2.46 rad request after the replan, not a
stale one) and the count is -1 on a different branch. **P208 is a smoothness fix, not a
count fix.**

## 4. Counts are branch draws

The same seed does not select the same fruit after the first attempt: the attempt's
duration changes which fruit is at the station. C303 and R4 303 both start with the
orange that fails; C's next fruit is a kiwi, R4's a 3.1 cm strawberry. At seed 808 the
first fruit (3.1 cm lychee) fails in every arm and the later sequences diverge. The
6-episode count is a **report**, not a rate.

## 5. One instrumentation defect found and fixed

Every recipe in the record (including the P202/P204 clips) exported
`FRUIT_JOINT_CLAMP=1`, but P53's canonical knob is `FRUIT_POLICY_JOINT_CLAMP`. The
short spelling was **silently inert**, so those clips ran with the clamp **off**. P207
adds the short spelling as a direct-only alias (canonical wins when both are set; a
non-direct wrapper that exports the short name stays inert instead of aborting). The
C cells in this phase are the **first direct cells with the clamp actually on**:
`[emit]` reads out_pre 4.9 % (ep4) and out_post 0.0 % on C303, and 0.0 % on the calm
episode. The P202 README and the video index carry the correction.

## 6. Recommendation

Ship as **recipe settings**, not code defaults (the code default stays 0, so every
unset path is byte-inert):

```bash
FRUIT_POLICY_JOINT_CLAMP=1        # canonical; the short alias is now honoured too
FRUIT_POLICY_TARGET_RATE=5.45     # rad/s = the arm's own 312 deg/s joint limit
# optional, smoothness-only:
FRUIT_REPLAN_ON_SERVO_END=1
```

R5 is the ship rung: **equal pooled count (7/12 against 7/12)**, emitted p95 0.198 ->
0.181 / 0.136 -> 0.093, max 2.633 -> 0.182 / 0.660 -> 0.182, binding 15.7-24.0 %. It
has a physical meaning: no emitted joint target exceeds the arm's own 5.45 rad/s joint
speed. R4 is a stronger smoothing option (p95 -32 to -55 %, binding 25-55 %) but its
pooled count is 6/12 and it is a real speed limit on some branches; R2 is measured out.
P208 is smoothness-only and is not part of the ship recipe unless a user wants the
residual p95 lower at a possible count cost.

## 7. Gates and the smoothness clip

* `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**, with the new `271` (target
  rate) and `272` (replan) legs. The P53 `229` leg was updated for the longer scope guard.
* `scripts/accept.sh` **7/10 = 70 %, `fingerprint: matches`, `190: PASS`**. The scripted
  line never constructs `SortingRLEnv`, so the direct-only knobs cannot reach it; this is
  the same import-guard shape P203's release boundary used.
* `python3 scripts/106_index_audit.py` **OK**, `scripts/107_collect_merge_test.py`
  **PASS (21 checks)**.
* `logs/video_p207/` - six sorts at seed 303 with the cap and the real clamp: **4/6**,
  56.6 s. Its `[cmd]` stream reads p95 **0.046 rad**, max **0.182**, > 0.10 rad **1.7 %**,
  cap binding **12.1 %**, residual p95 **0.027 rad**. Archived as
  `p207_smooth_4of6_s303/` in the media index.

No default was flipped, no reference was re-recorded, and `configs/` is untouched.
`logs/p207/manifests/` carries each arm's rollout manifest (C303 predates the per-arm
out-directory and its manifest was overwritten by the first R2 start; its `[emit]` banner
and `[emit]` summary are in `logs/p207/C_s303.log`).
