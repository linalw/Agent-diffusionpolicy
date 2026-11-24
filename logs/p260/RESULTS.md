# P260 results: `release` decomposed - the descent is 1.29 s, the ramps 0.94 s, and **-0.45 s** comes from the holds

**2026-11-25, `logs/p260/`.** One new **second-level** cycle instrument (default off), one
measured recipe change, and **the deployment cell is now a script**.

---

## 1. The instrument

`_cycle_mark(label)` records the duration **since the previous mark**, so inserting marks
inside `release` would change the shipped `[cycle]` row's shape for every existing
report. The split is therefore behind a **second switch**: `FRUIT_CYCLE_SUB=1` (with
`FRUIT_CYCLE_REPORT=1`) adds `rel_low`, `rel_pads`, `rel_fing`; unset, the row is
byte-identical. Pinned by the `P260 cycle sub` leg (three gated marks, inside the release
block, default off).

## 2. `release` = 2.23 s, split

One 0.08 cell, seed 905, 10 continuous picks (`FRUIT_CYCLE_SUB=1`):

| segment | median | what it is |
|---|---|---|
| **`rel_low`** | **1.29 s** | the accompanied descent (`_place_low`, 0.18 m to the bin floor, P227ac) plus the relax |
| **`rel_pads`** | **0.67 s** | the dwell (0 after P227r) + the **40-step pad ramp at 2 ticks/step** |
| **`rel_fing`** | **0.27 s** | the **16-step finger ramp at 2 ticks/step** |
| `release` (remainder) | **0.00 s** | - |

Sum 2.23 s, which is the block the earlier phases reported as ~2.16-2.23.

**So the ramps are 0.94 s of a 10.85 s attempt (8.7 %) purely because each ramp step
holds two ticks.** At one tick per step the two ramps are 0.47 s.

## 3. The measurement: `hold=1` is **-0.45 s at 39/40**

| arm | `release` | attempt `total` | placed |
|---|---|---|---|
| control (hold 2) | **2.17 s** | **10.96 s** | 20/20 |
| `FRUIT_RELEASE_PAD_HOLD=1 FRUIT_RELEASE_FINGER_HOLD=1`, s905 | **1.72 s** | **10.48 s** | **20/20** |
| ... s906 | **1.70 s** | **10.56 s** | **19/20** |

**-0.45 / -0.47 s of `release`, -0.48 / -0.40 s of the attempt**, and **39/40 placed**.
The single loss is **`grasped=False`** (`peach 5.9 cm`, `grasp_lift` stored pad centre
100 mm off) - the **grasp class**, not a release or landing loss: **every placement
landed**.

**Why it is a recipe setting and not a default**: these holds live in the release
profile (`_speed["release_pad_hold"]`), which the **two-line also reads**. A default
would move the two-line acceptance and owe a reference re-record - the price P87/P88/P89
priced. The scope that is free is the **single-arm deployment recipe**, so the two
settings went there (§4), and `=2` restores the old clock.

## 4. The deployment cell is now one command

`scripts/290_single_arm_continuous.sh [picks] [seed] [speed]` - the whole recipe the
`docs/SINGLE_ARM_SPEC.md` numbers were measured with (the cell, the six interface
settings, the deployment shape, the single-arm skip value, the two release holds, the
cycle report), with the three **shipped** defaults deliberately not named (the axis-aware
catch exit P249, the place blend 90 P259). First cell through it:

```
deployment cell: picks placed 20/20  seed=907 speed=0.08 picks=20
cycle 10.49 s, gap 257
```

**20/20 at a 10.49 s attempt** - the arc's best. This closes a reproducibility gap: the
long `110_rl_rollout.py` invocation existed only in ad-hoc command lines until now.

## 5. Where the cycle stands

| phase | attempt cycle | the change |
|---|---|---|
| start of the arc | **13.55 s** | - |
| P249 | 12.13 s | the axis-aware catch exit (`seat` 1.67 -> 0.17) |
| P258 | 11.43 s | the duplicated clearance (`return` 0.50 -> 0) |
| P259 | 10.85 s | the over-timed place blend (`place` 3.48 -> 2.99) |
| **P260** | **10.49 s** | the release holds (`release` 2.17 -> 1.70) |

**-22.6 % over the arc**, with the success at **98.6 %** pooled (0.08, mixed pool) and
**100 %** on the hardest single species. **The remaining blocks** are `place` 2.96
(clear 0.43 + blend 1.25 + transit/low 1.28), `release` 1.70 (`rel_low` 1.29 +
ramps 0.47), `grip` 1.58, `lift` 1.90, `close` 1.10, `descent` 1.1, `seat` 0.17.

**Honest caveat, unchanged**: `gap` is bimodal per cell (257-432), so throughput is a
**range (4.4-4.7 picks/min at 0.08)**, never a point from one cell.

## 6. No-harm

The sub-marks are gated on `FRUIT_CYCLE_SUB` (and on `FRUIT_CYCLE_REPORT`, which the
acceptance does not set): `scripts/accept.sh` is **`fingerprint: matches
configs/motion_reference.json`** with its **459 `[fruit]` lines 459/459 identical** to
`logs/p227/accept_final.log`; `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**.

## 7. Pins

`tasks.py` **`37888fb9`** (the second switch + the three marks), `rl_env.py`
(`TASKS_MD5` follow), `scripts/selfcheck.sh`,
`scripts/290_single_arm_continuous.sh`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched; ckpt `p227_panda156`. Evidence `logs/p260/`.
