# P228 / Stage 0 results: the latency the world pays, and what the cell absorbs

**2026-11-24, `logs/p228/`.** One default-off **evaluation** lever, one 5-point
latency sweep, 60 episodes. Nothing adopted in the shipped policy path; no
`configs/` reference touched.

Pre-registration pinned before any non-zero-`d` cell was read:
`logs/p228/PREREG.md` md5 **`b677897e`**.

---

## 1. What ran

| | |
|---|---|
| cells | `FRUIT_EVAL_LATENCY ∈ {0, 4, 8, 16, auto}` x seeds {901, 902} x **6 episodes** = **60** |
| recipe | `scripts/284_single_arm_policy_gate.sh` verbatim (Panda + two bins, `FRUIT_POLICY_TRIGGER=arrival`, `FRUIT_SKIP_LATE=0.5`, the six interface settings, `FRUIT_POLICY_ACTION_HOLD=4`) |
| checkpoint | `checkpoints/p227_panda156` (12-D, 4.59 M, trained from scratch) |
| driver | `scripts/285_latency_bench.sh` -> `logs/p228/latency/D<d>_s<seed>.log` |
| report | `scripts/286_latency_report.py` |
| declared pre-existing run | one **1-episode build smoke** at `d=4`, seed 901, **1/1 placed** (`/tmp/lat4.log`) - it existed to confirm the row prints and nothing crashed |

The injector (`rl_env._inject_latency`) advances `d` control ticks **after** a
decision's inference returns and **before** its chunk executes, with the arm
holding still, and **does not observe or record during the pause**. Refused with
`FRUIT_RTC`/`FRUIT_VLASH` (they model the same delay by interleaving) and with
`--record` (the paused ticks would not enter the store's tick accounting).

**At the shipped 0.12 m/s one control tick is exactly 1.0 mm of belt**, so the
`d` column is also millimetres of displacement.

## 2. The manipulation check (P1): PASS

| `d` | `[lat]` rows | resolved `d` (median) | `sim_ms` |
|---|---|---|---|
| 0 | **0** | - | - |
| 4 | 46 / 60 | **4.0** | 33.3 |
| 8 | 35 / 49 | **8.0** | 66.7 |
| 16 | 26 / 42 | **16.0** | 133.3 |
| auto | 42 / 46 | **8.0** (p50) | 66.7 |

`d=0` carries no `[lat]` row at all, and every armed cell resolves to the value
the file name says. The injector measured what it claims to measure.

## 3. The count: **P3 does not fire** (no improvement either)

| `d` | placed | % | 95 % CI (Wilson) |
|---|---|---|---|
| 0 | **11/12** | 91.7 | [65, 99] |
| 4 | 10/12 | 83.3 | [55, 95] |
| 8 | 9/12 | 75.0 | [47, 91] |
| 16 | **11/12** | 91.7 | [65, 99] |
| auto | **11/12** | 91.7 | [65, 99] |
| pooled | **52/60** | **86.7** | [75.8, 93.1] |

The registered rule was *"`d=16` loses >= 2 of 12 against `d=0`, in the same
direction at both seeds"*. It is **11 vs 11 of 12**, and per seed **+1 / -1** -
so **P3 does not fire**. The table is also **not monotone** (11, 10, 9, 11),
which is what a 6-episode cell at a ~90 % base looks like: every arm's CI spans
roughly one third of the range. **No count claim is made in either direction.**

The one arm that matters most is **`auto`**, because it is the only one whose
latency is a *distribution* rather than a constant: p50 **8 ticks**, mean
**9.7-10.0**, range **6-16**, plus **one cold-start decision per episode at 55
and 70 ticks** (620 ms first call). It reads **11/12**, the same as `d=0`.

## 4. The mechanism (P2): the fire is **not** delayed

`t_arrive` is the time the fruit still needs to reach the catch point, read at
the tick the arrival trigger fires (one row per attempt, 6 per cell):

| `d` | mean `t_arrive` | sd | n | what a fire delayed by `d/120` s would read |
|---|---|---|---|---|
| 0 | 1.672 | 0.184 | 12 | 1.672 |
| 4 | 1.723 | 0.179 | 12 | 1.639 |
| 8 | 1.729 | 0.197 | 12 | 1.605 |
| 16 | 1.562 | 0.090 | 12 | 1.539 |
| auto | 1.710 | 0.239 | 12 | - |

Rank correlation across the 48 fixed-`d` attempts: **rho = -0.252**. A trigger
that was itself delayed by the injection would read a strong negative
(**~ -0.7**) with the `d=16` mean at **1.54** and the `d=8` mean at **1.61**.
Measured, the two middle rungs go the *wrong way* (+0.05, +0.06 against `d=0`)
and only `d=16` dips (-0.11, ~2 SE of its own cell).

**So the pre-registered alternative does not obtain**: the injection delays the
**chunk**, not the **fire**. The trigger is evaluated inside the execution loop
at true simulated time, and it stays there. That is the intended semantics and
it is now measured, not assumed.

The catch-up's own loss rows are flat as well: `close: fruit drifted` fires
**1 / 1 / 0 / 1 / 0** times (d = 0 / 4 / 8 / 16 / auto) over 60 episodes.

**Why the cell absorbs it** (mechanism, from the code and consistent with the
flat `t_arrive`): a late chunk costs a *constant lag* - the arm is `d` mm behind
the fruit for the rest of the approach - rather than an accumulating error,
because every decision re-observes; and the scripted catch-up re-aims every tick
from the measured fruit with a **200-tick / 200 mm** budget against a **6 mm**
tolerance. 16 mm of lag is inside that budget. This is the P5 null branch: **the
layer split (L4 approach owns the chunk, L5/the primitive owns contact) is what
buys the tolerance**, and that is a measured argument for the 4T structure, not
a claim that latency is harmless.

## 5. The number this phase actually delivers

**The model's in-loop decision latency is ~66 ms p50, not the offline bench's
26.4 ms.**

| | p50 | p95-ish | source |
|---|---|---|---|
| offline, `moe_v13`, dedicated bench | **26.4 ms** | 27.3 | P141 (`scripts/123/137`) |
| **in the loop, this cell** | **65.7 / 66.7 ms** | ~86 (per-cell medians 57-86) | this phase, `[lat] infer_ms` |
| cold start, first decision of an episode | **620-740 ms** | | this phase |

The gap is **not diagnosed here**. Two candidates, both stated as hypotheses:
`_observe` renders the camera immediately before the sample, so the model
competes with a just-issued render on the same GPU; and the two measurements are
different checkpoints. **Quote 66 ms as this cell's in-loop latency** - and
**`auto` resolves to 8 ticks = 8 mm**, i.e. **1.3x the catch tolerance**, not the
0.4x the bench number would suggest.

The honest consequence, and the reason this phase exists: **a cell evaluated at
`d=0` is reporting a latency the machine does not have.** From here, evaluate at
`FRUIT_EVAL_LATENCY=auto` (or `8`), and report the resolved `d`.

## 6. Failure classes (P4): the two known keys, and one direction

Across 60 episodes: **6 x `fruit did not follow the gripper`** and **1 x
`fruit left the pick station during the close`** - both are the record's known
classes (`logs/p42/SIM_LIMIT.md`'s grip class and P41's station escape). **No new
key.**

They are also **unevenly placed**: `d=0` carries **0/12**, the armed cells
**6/48** (Fisher two-sided **p = 0.333**). That is a direction, not a result -
the seeds draw different fruit, and the cell's residual is the grip class the
record already owns. A powered cell (>= 40 per arm) is the only way to move it;
it is **not** registered here.

## 7. Deviations and defects found in the phase's own instruments

1. **The report's first pass read `t_arrive = nan`.** The `[rl] episode` row
   *contains* the notes, so an `elif` chain stopped at the episode match and
   never reached the trigger regex. Fixed (`scripts/286_latency_report.py`) and
   the cells re-read **from the same logs** - no re-simulation. Recorded because
   the first table anyone would have quoted was empty in that column.
2. **The `[lat]` row's `belt_mm` was a literal `0.12`** for the first cells and
   `cfg.belt_speed` afterwards. The two are the same number here
   (`0.12 x d x 8.33 ms = d` mm), so no cell's number moved - but the cells
   therefore span two revisions of `rl_env.py`. `tasks.py` is unchanged
   throughout (**`3f9ef6ea`**), and the report's `d_meas`/`sim_ms` columns come
   from the row, not from the constant.
3. **`--record` is now refused with the lever.** The injector advances the world
   without applying an action, so a recorded episode's `ticks_total` would be
   short of the simulated time it covers - P173's store invariant. Caught while
   reading the code, not by a run.

## 8. Verdict

* **P1 PASS**, **P3 does not fire**, **P2 = the "fire on true time" branch**,
  **P4 = the two known keys**, **P5 applies**.
* The decision-latency claim of this cell changes: **66 ms / 8 mm p50**, and the
  cell still places **11/12** with a *distribution* of that latency - i.e. the
  layer split absorbs it.
* **Nothing shipped.** `FRUIT_EVAL_LATENCY` is default off and unset is the
  shipped path byte for byte (proved structurally by `P228 eval latency`; the
  scripted acceptance never imports `rl_env`, so it is an import guard).
* **The next layer is Stage 1** (the intercept arithmetic): `d` is now a
  measured quantity, so `T_lead` has one of its four terms.

## 9. Pins

`rl_env.py` **`41e006a6`** (the resolver, the injector, `CONTROL_DT`, the two
refusals), `tasks.py` **`3f9ef6ea`** (unchanged),
`scripts/285_latency_bench.sh`, `scripts/286_latency_report.py`,
`scripts/287_p228_latency_selftest.py`, `scripts/selfcheck.sh` (leg
`P228 eval latency`), `scripts/284_single_arm_policy_gate.sh` (the log name is
now overridable); references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
checkpoint `p227_panda156` used as-is.
