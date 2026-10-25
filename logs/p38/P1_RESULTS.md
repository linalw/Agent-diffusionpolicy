# P38 phase 1 — the delivered-x drift tail and the harness's no-re-selection (the measurement)

Measured 2026-10-25, offline where possible (two claimed probe runs plus eleven
minutes of claimed simulator time for the drift probe). **No `src/` change, no
`configs/` change, no shipped default changed.** The pre-registration for
phase 2 is `PREREG.md` (same directory). The lane is
`.slim/deepwork/p38-drift-tail.md`.

**The one-line answers.**

1. **The delivered x is the spawn band shifted by a fixed per-instance settle
   offset, and the transport contributes exactly 0.000 mm.** The cascaded
   lateral drift hypothesis (belt/cleat/friction/rolling) is **falsified** by
   measurement: over 475 full transits in five configurations the across-belt x
   of every fruit is constant to the print precision while it rides the belt,
   because a sphere rolling on a laterally uniform moving surface has no
   lateral force at all (and the cleats are off by default,
   `conveyor.py:189-197`). The only stage that moves x is the release/settle,
   and its displacement is a **fixed per-instance offset**: at one supply seed
   the same two instances per class reproduce their own value to 0.2 mm across
   the schedule (scatter vs patch) and across the arm pose (none / `ready` /
   `grasp`), and the pool's per-seed scale draw makes a different seed a
   different set of instances (`-35.9..+69.2 mm` over the two seeds sampled).
   So the delivered x = `spawn x + offset(instance)`.
2. **The tail is real but rare, and it is arm-dependent.** The trigger's
   admission floor is `station_x - 0.16`, and the station x is *not* the same
   for both arms: **right 0.3330 (n = 431) → x >= 0.1730**, **left 0.3400
   (n = 219) → x >= 0.1800**. On the direct patch population (653 episodes)
   **5/653 = 0.77 %** deliver below 0.180 and **2/653 = 0.31 %** below 0.173.
   The two episodes below 0.173 are one 1500-tick timeout (the P37 S3 event,
   x = 0.159) and one `fruit fell off the line` (x = 0.162) — the same tail,
   two different terminal notes.
3. **The S3 class on the shipped interface is 2/3103 = 0.06 %**, and 2 of the
   4 "never-fired" episodes in the whole committed record that are *not* the
   pre-W4 gate class are the opt-in reach-cliff guard's own high-x refusals
   (x = 0.398/0.412, `FRUIT_POLICY_TRIGGER_X_MAX` runs only). At that rate a
   WS-4.2 N = 5 x 15 arm expects 0.05 events: **no A/B at the project's N can
   measure this class.** Phase 2 therefore measures the *mechanism* on a forced
   band and the *safety* on the shipped band — the PREREG's design.
4. **The harness path is a single silent return.** `should_fire` refuses on
   `|dx| > lateral` and returns `False` **with no marker**, the candidate is
   chosen once per episode at the reset, and nothing re-selects; the attempt
   then burns the whole 1500-tick policy horizon (`rl_env.py:2668-2674`) and
   the only record is `timeout: no grasp within 1500 ticks`. Options (a) a
   bounded re-selection, (b) an explicit terminal class, (c) both — measured in
   phase 2, all default off and direct-only.
5. **The supply lever is a margin purchase, not a drift fix**, and it must
   raise the ceiling with the floor. To keep the delivered x above the *left*
   floor 0.180 with the worst observed downward excursion (-0.057 m from the
   0.20 floor) the release floor has to be >= 0.237; the patch pair rule
   (`x0 ~ U(x_min, x_max - sep)`, sep 0.085-0.12) then needs the ceiling at
   >= 0.38. That is a scenario change: three motion references, the scripted
   acceptance, both two-line gates and every store — its own phase (P38b), not
   phase 2.

---

## 1. The delivered-x distribution, per scenario

Two station-zone populations and one design reading:

* **[1] the scripted lines** — one sample per *attempt* from the primitive's
  `wait step=0 fruit_x=` row (`tasks.py:7775`), the fruit the attempt actually
  got;
* **[2] the direct line** — one sample per *episode* from the `[park] call
  ... x=` band census (P35/P36/P37 only; the census is off elsewhere), the
  fruit the *episode* got;
* **[3] the on-belt design reading** — the `[supply] lateral x:` summary each
  `171_supply_probe` run writes (all along positions pooled, no selection).

**Bit-identical replays are deduped.** The committed logs contain many replays
of one scenario (no-harm re-runs, trace-on/off pairs), and a replay reproduces
an attempt's `(x, along)` to 4 dp. [1]'s `n` is therefore the number of
*unique attempts* and `raw` counts the replays too (3-6x). [2] needs no dedupe
(one sample per log/episode; the batches use different seeds).

The baselines: the spawn draw is `rng.uniform(0.20, 0.36)` (`fruits.py:1089`);
the trigger admits `|x - station_x| <= 0.16` with the per-arm station x of
§3; the measured top-down reach band is x = 0.18-0.39 (~6 mm residual) with a
cliff at x >= 0.42 (`scripts/174_station_reach.py`,
`logs/v3/60_station_reach_edge.log`).

### [1] the scripted station-zone x (unique attempts)

| scenario | n | p10 | p50 | p90 | min | max | < 0.173 | < 0.20 | > 0.36 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| single scatter (the shipped acceptance) | 209 | 0.209 | 0.272 | 0.347 | 0.177 | 0.373 | 0 | 8 (3.8 %) | 5 (2.4 %) |
| single patch | 272 | 0.208 | 0.270 | 0.349 | **0.158** | 0.376 | 1 (0.37 %) | 18 (6.6 %) | 9 (3.3 %) |
| two-line wave (the dense sheet) | 682 | 0.212 | 0.276 | 0.344 | 0.169 | 0.403 | 2 (0.29 %) | 23 (3.4 %) | 13 (1.9 %) |
| two-line patch | 2016 | 0.206 | 0.280 | 0.347 | **0.143** | 0.410 | 9 (0.45 %) | 130 (6.5 %) | 69 (3.4 %) |
| two-line bed | 38 | 0.196 | 0.275 | 0.364 | 0.183 | 0.371 | 0 | 6 (15.8 %) | 10 (26.3 %) |
| single bed | 47 | 0.200 | 0.357 | 0.369 | 0.172 | 0.394 | 1¹ | 5 (10.6 %) | 21 (44.7 %) |

¹ two rows of one attempt each (the same scenario at two settle settings,
10 and 20) — the bed's 0.20 column delivered 28 mm low, from a kiwi.

The KS distance to the spawn band is 0.035-0.13 for the schedules that draw
*freely* (two-line wave 0.035, single scatter 0.082, single patch 0.097, direct
patch 0.132): the core of the distribution is the band. **The patch and bed
schedules do not draw uniformly on the band** (a pair's first member is drawn
from `[x_min, x_max - sep]`, so the marginal is skewed low), which is why the
p50 reads 0.26-0.28 rather than 0.28; read the tail counts, not the KS.

Two tails, and they are not symmetric: **below the spawn floor 3.4-15.8 %**,
**above the ceiling 1.7-44.7 %**. The high tail dominates (the bed's 44.7 % is
the 0.36 column's own drift upward) but the *low* tail is the one that costs an
attempt, because the trigger's admission floor sits only 0.027-0.034 m below
the spawn floor while the reach band's upper edge (0.39) sits 0.03 m above the
ceiling.

### [2] the direct station-zone x (episodes, P35/P36/P37)

| n | p1 | p10 | p50 | p90 | p99 | min | max | < 0.173 | < 0.180 | < 0.20 | > 0.36 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 653 | 0.187 | 0.216 | 0.264 | 0.341 | 0.364 | **0.159** | 0.376 | 2 (0.31 %) | 5 (0.77 %) | 23 (3.5 %) | 11 (1.7 %) |

The 23 below the spawn floor by class: **kiwi 8, orange 7, strawberry 5,
lychee 2, apple 1** — kiwi and orange over-represented against a balanced
mix (expected ~3 each), which is the same ordering the probe's per-class settle
offset gives (§2). Within an episode the census's `along` spans a median
0.096 m (max 0.148) while `x` does not move: **the delivered x is fixed before
the band** — the first direct evidence that the drift is not a transport
process.

### [3] the on-belt design reading (`[supply] lateral x:`)

| log | schedule | min | p10 | p50 | p90 | max |
| --- | --- | --- | --- | --- | --- | --- |
| `v1/12b_supply_after_free` (the shipped scatter, free cadence) | scatter | **0.148** | 0.205 | 0.279 | 0.348 | 0.364 |
| `v1/11b_supply_after_driver` (driver cadence) | scatter | 0.147 | 0.200 | 0.249 | 0.352 | 0.373 |
| `w6/00_probe_supply_free` (the patch sheet) | patch | 0.187 | 0.209 | 0.264 | 0.346 | 0.373 |
| `w6/00_probe_supply_worker` (the two-line worker cadence) | patch | 0.181 | 0.206 | 0.261 | 0.353 | 0.368 |
| `v1/10_supply_before_driver` (the pre-v9 fixed line, control) | fixed | 0.308 | 0.319 | 0.334 | 0.363 | 0.365 |

The pre-v9 fixed line (spawn within ±5 mm of the belt centre 0.34) delivered
0.308-0.365 — *above* the scatter's core and with no low tail at all. The
scattered band's floor (0.20) is what puts 3-7 % of attempts into the 0.15-0.20
window.

## 2. The drift mechanism: the transport is exactly 0, the release is everything

`logs/p38/probe_drift.py` (new, read-only) builds the shipped scene + spawner,
runs the **free cadence** with **no attempt**, and records every live fruit's
`(x, y, vx)` once per physics tick, splitting one *transit* per release (the
pool is recycled, so a body index repeats). It reports the drift relative to
the *spawn tick* (total) and relative to the first edge 0.04 m downstream
(transport only), per class.

| run | schedule | arms | transits | transport drift | total (spawn -> delivery) drift, mm |
| --- | --- | --- | --- | --- | --- |
| `probe_drift_s5.log` | scatter | none | 68 | **0.00 / 0.00** | mean +2.26, sd 11.67, **min -35.89**, max +26.22; 18 with \|d\|>10 |
| `probe_drift_scatter_none_s77.log` | scatter | none | 62 | **0.00 / 0.00** | mean +0.47, sd 6.72, min -20.20, max +15.04; 11 with \|d\|>10 |
| `probe_drift_patch_none_s77.log` | patch | none | 121 | **0.00 / 0.00** | mean +0.36, sd 7.07, min -20.20, max +15.04; 22 with \|d\|>10 |
| `probe_drift_patch_s77_ready.log` | patch | both `ready` | 126 | **0.00 / 0.00** | mean +0.15, sd 6.84, min -20.20, max +15.04; 22 with \|d\|>10 |
| `probe_drift_patch_s77_grasp.log` | patch | left `ready`, right `grasp` | 98 | **0.00 / 0.00** | mean +0.28, sd 7.00, min -19.98, max +15.01; 17 with \|d\|>10 |

**The transport's contribution is zero, not small.** A sphere rolling on a
plane whose surface velocity is along `-y` has a contact slip along `-y` only:
the friction force is along `-y`, the spin is about `x`, and there is **no
lateral force term** — so `vx` stays exactly 0 and x is frozen. The measured
`transport mean 0.00 sd 0.00 min 0.00 max 0.00` over 475 transits is that
identity, not a small number. The cleats — the one part of the conveyor that
could push a sphere sideways — are **off by default** (`conveyor.py:186-197`,
`FRUIT_CLEATS=0`), and the per-tick step detector finds a single 2.2-2.5 mm
step class in the whole corpus (8 apples in the patch runs, at the release
edge, where `respawn` drops the fruit 3 cm).

**The release/settle is the only stage that moves x, and its displacement is a
fixed per-instance offset.** The pool has two instances per class; each
instance reproduces its own value to 0.2 mm:

* at seed 77 the same values appear in the `scatter/none`, `patch/none`,
  `patch/ready` and `patch/grasp` runs (e.g. kiwi **-20.20** and **+15.04**,
  peach **-10.53** and **+0.72**, tomato **+3.88** and **+4.59**, apple
  **+0.39** and **+2.58**, orange **-1.23** and **-2.66**, pear **+1.24** and
  **+2.24**, lychee **-0.17** and **+6.40**, strawberry **-0.17** and
  **+3.48**) — the mean of each class is the mixture of its two instance
  values, so per-class means move with the sample composition (n = 7-16) while
  the instance values do not;
* seed 5 draws a different instance scale per pool slot (`FruitSpawner`
  seeds the diameter/ripeness/friction draw from `SEED`), and its offsets are a
  different set: kiwi **+12.06 / +26.22**, strawberry **-35.89 / +19.96**,
  peach **+5.12 / +6.83**, apple **-2.46 / -0.71** — same mechanism, different
  bodies.

So the settle offset is a **deterministic per-instance property of the pool**
(its mesh and its seeded scale), with a measured range of **-35.9..+69.2 mm**
across the instances sampled (the +69.2 is the patch run's out-of-band list: a
kiwi drawn at 0.343 delivered at 0.413, twice, identically). The delivered x is
then `spawn x + offset(instance)`, the low tail is the *negative* offsets
meeting a draw near the 0.20 floor, and the class ordering in §1 (kiwi and
orange over-represented below the floor) is the ordering of the instance
offsets.

**A corollary that names the real supply lever (P38b).** Because the offset is
*fixed per instance*, it can be **measured once (this probe) and compensated at
spawn** (`respawn` would place the body at `target x - offset(instance)`), which
removes the tail exactly instead of buying margin with a wider gap. That is a
scene change with the same reference cost as the floor raise, and a better one.

**What this does not show (the open residual).** The deepest low-side
delivered x in the *attempt* loop is 0.143-0.159, i.e. **-41..-57 mm** from the
0.20 floor, while the probe's worst release offset is **-35.9 mm** (a
strawberry at seed 5; -20.2 mm for the deepest kiwi at seed 77). So a further
low-side displacement of ~5-20 mm happens inside the attempt loop and this
probe does not see it. The named candidates, none separated here:

* the **active** arm's jaws/links sweeping the fly-by band while the policy
  moves from the reset `grasp` pose (the direct interface puts the active arm
  at the grasp pose at the reset, and the selection floor keeps the target at
  along >= ~0.40 m — exactly where the hand's approach starts);
* a **re-release under a moving arm** (the recycled body is teleported to the
  spawn end while the arm may be anywhere);
* a **pair depenetration at release** when two large fruit are abreast (the
  patch's pair separation is 0.085-0.12 m and the `gripper_max_object` bound is
  above it).

The discriminator for phase 2 (optional, its own claim): replay a *recorded
action stream* through `probe_drift.py` with `FRUIT_DRIFT_ARMS` following the
recorded joints, and compare the delivered-x tail with the static-pose control
above. It is not needed for the harness lever (which acts on the consequence),
only for the supply lever's margin arithmetic — and §4's floor is computed from
the *empirical* delivered distribution, so it is valid either way.

## 3. The S3-class census (the never-fired episodes)

The census is over **every direct-loop log in the repository** that prints an
episode-end row (549 logs), grouped by the trigger line the log itself carries
(`[rl] trigger=... lateral=...`) and by whether the log has any `x-edge refuse`
row (the opt-in reach-cliff guard). A never-fired episode is one whose only
note is `timeout: no grasp within 1500 ticks`; the `[acq]` rows confirm the
primitive never ran.

| population | episodes | placed | carried-not-placed | never-fired | rate |
| --- | --- | --- | --- | --- | --- |
| **gate 0.16, guard off (the shipped interface)** | **3103** | 1149 | 1652 | **2** | **0.06 %** |
| gate 0.16, guard on (the opt-in high-x cliff refusal) | 120 | 19 | 24 | 2 | 1.7 % |
| gate 0.06 (pre-W4, the refused outer band) | 3195 | 1715 | 209 | 180 | 5.6 % |
| gate 0.20 (the W4 sweep) | 48 | 13 | 0 | 0 | 0 % |
| pre-trigger / trigger off (the historical policy-gate no-fire) | 864 | — | — | 414 | 47.9 % |

**The two shipped-interface events, in full:**

| log | ep | class | arm | ticks | target x |
| --- | --- | --- | --- | --- | --- |
| `logs/p37/B_ab/B_1.log` | 6 | kiwi | right | 1500 | **+0.159** (25 band calls) |
| `logs/w7/C_eval/direct_ab/B_3.log` | 12 | peach | left | 1500 | not recorded (no park census) |

and **one more low-x episode that did not become a timeout**:
`logs/p35/B_ab/A_4.log` ep 14 (orange, right, **x = +0.162**) ended at tick
1298 as `fruit fell off the line`. So the low-x tail's measured terminal notes
are **1 timeout + 1 fell-off** among the 2 episodes below the right floor.

**The two guard-on events are the opposite tail**: `x-edge refuse: fruit
x=0.398` (`logs/r6/A_c2_hsteps150.log` ep 1) and `x = 0.412`
(`logs/r7/A_cap_only_fix.log` ep 2) — a fruit past the *upper* band edge, refused
by the operator's `FRUIT_POLICY_TRIGGER_X_MAX` and then timed out. They are
absent from the shipped default (the guard is off) and must not be pooled with
the low-x class.

**The per-arm admission floor** ([5b] of the census; 650 episodes with both a
band x and an intercept-trigger `dx`):

| arm | n | station x median (p10/p90) | admission floor |
| --- | --- | --- | --- |
| right | 431 | 0.3330 (0.3320 / 0.3330) | **x >= 0.1730** |
| left | 219 | 0.3400 (0.3400 / 0.3410) | **x >= 0.1800** |

The left arm's grasp pose sits 7 mm farther out, so **the left refuses a 7 mm
wider slice of the low tail than the right**. That inverts the usual left-bad
reading on this axis, and it matters for the PREREG's population: the class is
not arm-symmetric.

**Power.** At 2/3103 = 0.06 %/episode, a WS-4.2 arm of 75 episodes expects 0.05
events (P(>= 1) = 4.7 %); the P37 batch saw 1/150, a 10x over-representation
that is batch clustering (one supply seed stream per batch), not a rate. **No
A/B at the project's N can measure this class**, which is why phase 2's primary
is a mechanism endpoint at 100 % incidence on a forced band (§PREREG).

## 4. The harness path, the options, and the supply lever

### 4.1 The exact path

1. **Selection happens once per episode** (`rl_env.py:1538-1560`): the direct
   presentation calls `task.select_target(spawner.state(), reach_anywhere=False)`
   in a 40-round feed loop, then builds `self._sample`, `self._goal` (8-D:
   position, velocity, diameter, bin) and `self._active`/`self._bin_index` from
   the **grade** (`A -> left/bin 0`, everything else -> right/bin 1). There is
   no re-selection API; `self._sample` is replaced only by the default-off
   P4b2 `present` path (`FRUIT_POLICY_TRIGGER_PRESENT=1`, `rl_env.py:2810-2850`),
   which is the *only* existing mid-episode goal switch.
2. **The per-tick gate** (`rl_env.py:2739-2908`): `fruit =
   spawner.position(self._sample)`, `distance = |fruit[:2] - jaw[:2]|`,
   `policy_close = finger < 0.030 and distance < 0.06`, `intercept, info =
   should_fire(...)`, `direct_fire(intercept, policy_close, gate_refuse)`.
3. **The silent refusal** (`trigger.py`, `should_fire`): `if abs(dx) >
   settings.lateral: return False, info` — an unmarked `False`. The `info` dict
   carries `dx` but no refusal key, so the env cannot distinguish "too far
   laterally" from "not yet in the reach window" and does not try.
4. **The only exit** is `self._tick >= self.reward.horizon` (1500 control
   ticks = 12.5 s of the *policy phase*; the scripted primitive's own steps run
   after the cap, `rl_env.py:2668-2674`). `_episode_events`
   (`rl_env.py:3240-3254`) ends early only for `fruit fell off the line`
   (z < belt_top - 0.25) or the handoff teleport.
5. So a laterally refused candidate costs the whole 12.5 s horizon and leaves
   the note `timeout: no grasp within 1500 ticks` — a class with no severity
   and no mechanism (the P37 Gate-2 lesson).

### 4.2 The options

**(a) a bounded re-selection.** On the first tick where the candidate is
*provably* unfirable — every other trigger gate passes and only the lateral one
refuses (`dy <= reach_eff`, `dy >= -0.05`, `speed > 1e-3`, `|dx| > lateral`) —
call `select_target(state, reach_anywhere=False, lane=self._bin_index,
exclude={old})`, adopt the result (same grade lane, so the arm and bin stay
valid), rebuild `_goal`/`_belt_rest`, `unprotect(old)`/`protect(new)`, and
repeat at most `_MAX` (2) times before `self._triggered`. **Feasible within
the horizon**: the refusal is detected at dy ~ 0.30 m (tick ~300 at 0.12 m/s),
the re-selected fruit is at along >= the moving-catch floor (~0.40 m, ~3.3 s),
and only the *fire* has to happen before tick 1500 — the primitive's own time
is outside the cap. **The cost is an observation change**: `_goal` switches
mid-episode, an input pair the checkpoint never saw (the P4b2 `present`
precedent, default off, never shipped).

**(b) an explicit terminal class.** At the same provable refusal, end the
episode with `notes=["no firable fruit: candidate x=... beyond the lateral
gate (x >= ... admitted)"]` plus an `outcome` field, instead of burning the
horizon. **No observation change**, and it names the mechanism, but the episode
is still a failure (the rate denominator is unchanged) and its `ticks` collapse
from ~1500 to ~300, so the **cycle metric becomes incomparable** on those
episodes — the PREREG compares the cycle over fired attempts only.

**(c) both** (the recommended arm): re-select first; if the selector returns
`None` (nothing eligible in the lane) or the cap is hit, end with the explicit
class. Coverage is preserved where the line has an alternative, and attributed
where it does not.

**The reporting effect that constrains the design.** `113_rl_report.py`'s
`reasons()` (lines 166-176) digit-normalises every failure note, so *any new
note text is a new failure reason*. An adaptive S3 gate on top of a new note
would fire on the lever's own diagnostic. The PREREG therefore makes the
attribution note a **run-neutral diagnostic that is ON in every arm**
(`FRUIT_POLICY_REFUSE_DIAG=1`) and compares only the *terminal* behaviour —
the AGENTS §3b rule ("compare arms inside one instrumented batch").

### 4.3 The supply lever

The arithmetic, all from the measurements above:

* the admission floors are **0.1730 (right) / 0.1800 (left)**;
* the delivered low tail is **0.143** (two-line patch), **0.159** (direct),
  **0.148** (on-belt), i.e. a worst downward excursion of **-0.057 m** from the
  0.20 spawn floor (and **-0.041** in the direct population);
* to hold the delivered x above 0.180 against the worst observed excursion the
  release floor must be **>= 0.237** (0.180 + 0.057); against the *probe's*
  worst measured instance offset (-0.036) it would be 0.216 — the empirical
  number governs, and the gap between the two (0.021) is the §2 residual;
* the patch pair rule needs `x_max - x_min >= sep` (0.085-0.12) with
  `x0 ~ U(x_min, x_max - sep)`, so a floor of 0.24 *and* the shipped ceiling
  0.36 leaves exactly 0.12 and degenerates the rule; **the ceiling has to rise
  with the floor**: 0.24-0.38 or 0.26-0.38;
* the reach band's upper edge is 0.39 (~6 mm residual) with the cliff at 0.42,
  so a 0.38 ceiling is inside it (and the bed's 0.36 column would become 0.38);
* a ceiling/floor raise moves the delivered p50 from 0.264 to ~0.30 — *closer*
  to the right arm's 0.333 station, i.e. the mean `|dx|` falls by ~0.035 and
  the trigger gains margin on both sides. That is the lever's real value.

**The cost**: a scenario change. Three motion references must be re-recorded
(`configs/motion_reference.json`, `motion_reference_twoline.json`,
`motion_reference_twoline_bed.json` — the third only if the bed moves), the
scripted acceptance re-run and re-referenced, both two-line gates re-run, and
every dataset/checkpoint store becomes a *pre-change* store, so any policy
claim on the new band needs its own recollection. **It is not a phase-2
candidate**; the PREREG registers it as P38b with this arithmetic.

**The transport's lateral control is not the lever.** The transport contributes
0.000 mm; a lane keeper (damping `vx`) has nothing to damp. The honest fix is
at `respawn`: **per-instance settle-offset compensation** (§2), which removes
the tail instead of buying margin, and costs the same references as the floor
raise. The floor raise is the fallback if the compensation turns out not to
hold across a fresh pool (the offset is measured per instance, and every seed
draws new scales).

## 5. The recommendation

* **Phase 2 = the harness lever (c), default off, direct-only**, with the
  primary endpoints on a **forced band** (100 % refused) and a **mixed band**
  (28 % refused) and the *safety* endpoint on the shipped patch band. §PREREG.
* **The supply floor is deferred** to P38b with the arithmetic of §4.3; it is
  the only lever that removes the *cause*, and it is the most expensive.
* **Do not widen the trigger gate.** Confirmed: the reach residual at x = 0.16
  is 8.3 mm against the handover's 6 mm tolerance, and the left arm's floor is
  already 7 mm farther out than the right's.

## 6. Files, pins, and how to re-check

| artefact | md5 |
| --- | --- |
| `logs/p38/drift_census.py` | (see `logs/p38/MD5.txt`) |
| `logs/p38/drift_census.txt` | idem |
| `logs/p38/probe_drift.py` | idem |
| `logs/p38/probe_drift_s5.log` / `_patch_none_s77` / `_scatter_none_s77` / `_patch_s77_ready` / `_patch_s77_grasp` | idem |

Tree pins at measurement time (unchanged after): HEAD `dd53d15`, `rl_env.py`
`aa54b022`, `policy/trigger.py` `d7ec85fc`, `tasks.py` `cdde6bd2`,
`fruits.py` `6f65e423`, `conveyor.py` `b0d95a08`, `assets.py` `61baf52b`,
`configs/motion_reference.json` `25ade92b`.

Re-check:

```bash
python3 logs/p38/drift_census.py --self-test      # parsers, KS, percentiles, tails
python3 logs/p38/drift_census.py                  # -> the [1]..[5b] tables above
SEED=77 FRUIT_SUPPLY_PATCH=1 scripts/154_claim_run.sh logs/p38/probe_drift_x.log \
    FRUIT_DRIFT_ARMS=none scripts/run.sh logs/p38/probe_drift.py
```

## 7. What this does not show

* **The residual low-side displacement inside the attempt loop** (up to
  ~35 mm beyond the probe's worst release offset) is not attributed. The
  harness lever does not need it; the supply lever's floor is computed from the
  empirical delivered distribution, which already includes it.
* **No rate.** Nothing here measures a success rate; the two forced bands of
  phase 2 are probes, not scenarios, and their rates are not quotable.
* **The probe's `arms=none/ready/grasp` poses are static.** A moving arm could
  push a fruit; the probe bounds the *static* interference at zero, which is
  why the open residual above exists.
* **The class is rare enough that no arm-level rate claim is possible** at
  WS-4.2 N: the phase-2 safety endpoint is a safety check with the exposure
  reported, not a power test.
