# P82 — where the two-line's per-tick wall goes, and the one removable third of it

Measurement phase plus **one** behaviour-neutral optimization. **Nothing adopted, no
default changed, no commit**: the one code change is behind a **default-off** knob
(`FRUIT_BIARM_WAKE_ON_REQUEST=1`), `configs/` is untouched, and the decision is the
owner's. Registered in `logs/p82/METHOD.md` (buckets, instruments, the adoption test,
and the four hypotheses) before any run.

## 0. The answer in one table

P80/P81 asked this and could not answer it: the two-line's advantage is **simulated
clock** (1.87-1.88x) and on this machine's wall it was a wash (**1.02x pooled**),
because the two-line pays **wall/sim 2.57 against the single arm's 1.38**. Here is
that 1.86x, decomposed (20 attempts, seed 5, the P80 cell):

| bucket | two-line (R1, exact per-round timers) | share of wall | single arm (R4, py-spy proportions) |
| --- | --- | --- | --- |
| **the PhysX step** (`SimulationManager.step` = one `simulate`) | **10.87 ms/tick = 1.30 wall/sim** | **51.0 %** | 71.3 % of its wall |
| the two arms' control (permit → next request) | 1.70 ms/segment x 1.97 = 3.35 ms/tick | 15.7 % | ~12 % (attempt/driver code + small tensor-API reads) |
| the app pump (`update_app`) | 0.06 s total (render is a no-op here) | **0.0 %** | **12.7 %** (`update_app(steps=20)` in the pre-pose/feed) |
| the arbiter's own Python (`schedule` - step) | 1.14 s total = **0.024 ms/round** | **0.2 %** | — (no arbiter) |
| fruit/state reads | inside the control segment | — | inside the control share |
| **dead poll latency** (both workers parked, main thread asleep in `queue.get`) | **~6.9 ms/tick = 0.83 wall/sim** | **~32 %** | **0** |
| rounds / rounds per shared tick | 47,795 / **2.03** | | |

**The dominant term is not the arbiter and not the render: it is the physics step
(51 %, irreducible) plus a 5 ms poll timeout the arbiter pays twice per shared tick
(32 %, removable).** The arbiter's Python work is 0.2 % — H2 (render) is refuted at
0.0 %, and the "shared-tick arbiter runs both arms' control" story is real but is
only 15.7 %, not the 1.86x.

The mechanism, from the timers: `CoopSession.run` drives `bridge.serve_while`, whose
body is `relay.schedule()` then `MainBridge.pump(0.005)`. `pump`'s queue only ever
receives *bridged main-thread jobs*; the tick requests that `TickRelay.request` files
never reach it. So after granting a permit the main thread sleeps out the rest of the
5 ms while the 1.70 ms segment runs: **measured 5.03 ms per round, 99.2 % of them
timeouts** (`logs/p82/R1.timers.json`).

## 1. The runs, and why they are the recorded branch

Nothing here is a new scenario: every cell is P80's `ATTEMPTS=20 SEED=5` battery
(`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`, shipped scenario), and each profile
build's `[fruit]` stream is compared line-for-line with the canonical record.

| cell | arm | instrument | placed | sim span | wall | wall/sim | `[fruit]` identity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `T20` (P80) | two-line | none | 16/20 | 193.3 s | 497.2 s | 2.57 | the record |
| **R1** | two-line | I2 timers | 16/20 | 193.3 s | 502.2 s | 2.60 | **865/865 vs T20** |
| **R3** | two-line | I1 py-spy | 16/20 | 193.3 s | 526.5 s | 2.72 | **865/865 vs T20** |
| `S20` (P80) | single | none | 12/19 | 286.7 s | 478.0 s | 1.38 | the record |
| **R2** | single | I2 timers (inert) | 12/19 | 286.7 s | 480.3 s | 1.39 | **710/710 vs S20** |
| **R4** | single | I1 py-spy | 12/19 | 286.7 s | 518.8 s | 1.50 | **710/710 vs S20** |

So both instruments are *measurements of the recorded branch*: I2 costs +1.0 % of wall
and I1 +5.9 % (two-line) / +8.5 % (single), and neither moves a single `[fruit]` line.
I2 on the single arm is inert by construction (no `CoopSession`, `rounds=0`), which is
itself the control that the timers only touch the arbiter path.

## 2. The decomposition, and what it rules out

`logs/p82/R1.timers.json` (two-line, 47,795 rounds, 23,530 shared ticks):

| term | total | per round | per tick | note |
| --- | --- | --- | --- | --- |
| `SimulationManager.step` | 255.9 s | 10.87 ms | 10.87 ms | 1 step per shared tick; `step` is one PhysX `simulate(dt)` |
| `TickRelay.schedule` self | 1.14 s | **0.024 ms** | 0.05 ms | **the arbiter's Python work is 0.2 % of wall** |
| worker segment (permit → request) | 78.9 s | 1.70 ms | 3.35 ms | 46,388 samples = 1.97/tick (both arms active) |
| `MainBridge.pump` | 240.5 s | **5.03 ms** | 10.2 ms gross | 47,414/47,794 = **99.2 % timeouts** |
| `_tick_frame` (render/camera) | **0.059 s** | — | — | 21,544 calls; no frame callback, no recorder |
| residual (wait not overlapped, handoff, feed) | 166.2 s | — | — | 161.6 s of it is the poll not covered by a segment |

**H1 (the arbiter's per-round Python work) is falsified as a cost**: 0.024 ms/round.
It is real as a *structure* (2.03 rounds per shared tick, one permit each), but the
Python is free; the *wait* is what costs. **H2 (render) is falsified**: 0.059 s in
the whole batch, because the scripted battery has no `frame_callback` and no recorder,
so `_tick_frame` is two attribute reads. **H3 (physics) is confirmed as the largest
single term and is not removable**: one shared `simulate` per tick, 10.87 ms, 51 %.
**H4 (the second arm's work) is 15.7 %** — the arms' segments are the only part of the
1.86x that is "two arms doing two arms' work", and they are serialized by the permit
(one runs at a time), so the two-line's control cost is ~2x the single arm's per tick,
not 2x its total.

The dead wall is measured three ways that agree: `pump total` 240.5 s minus the
segments it covers 78.9 s = **161.6 s (32.2 %)**; the `residual` above; and the
per-round histogram, whose wait is a single spike at 5.07-5.08 ms (p50 5.069, p90
5.082) — a timer, not a distribution of work.

**The single arm's side** (R4, py-spy, 545.7 s sampled on the main thread): samples
whose stack is **inside `step`** (the PhysX call *and* the USD change notices the app
runs inside it) are **71.3 %** of its wall - the `step` leaf alone is 63.9 % and the
notices are most of the remainder - plus `update_app` **12.7 %**, start-up ~4 %, and
the rest small tensor-API frames (the arm state reads) and the driver. The two
instruments agree on the same physical quantity: **py-spy 52.5 % / I2 51.0 %** on the
two-line (stack-contains-`step` vs `step_s / wall`). **The single arm has no arbiter
and no poll**, so its wall/sim (1.38) is physics plus an app pump the two-line does
not pay.

## 3. The one optimization: the arbiter's wake-on-request (`FRUIT_BIARM_WAKE_ON_REQUEST`)

Behaviour-neutral by construction: it moves *when* `schedule` is called, never which
tick is stepped, which attempt holds the permit, or what any control input is. Three
changes in `src/fruit_sorting/bimanual.py` (87 insertions, 10 deletions; applied by
`logs/p82/apply_wake_patch.py`, whose 12 anchors each assert):

1. `MainBridge` gains `wake_on_request` (default **False**) and a `threading.Event`;
2. `pump` waits on the event instead of the fixed timeout (`_next_job_waiting`: a
   queued job, else a pending wake, else wait; the timeout stays as the safety net,
   so a lost wake costs latency, never a stall). `call` also wakes;
3. `TickRelay.register/enter/request/pause/resume/release` call `_notify()` =
   `_cv.notify_all()` + `bridge.wake()`. **`schedule`'s own notify is left alone** —
   waking from inside `schedule` would make the next `pump` return without waiting
   and turn the driver loop into a spin.

The knob is read once per `CoopSession`; with it unset every path is the shipped one
(one attribute test per wake), so every recorded wall baseline still reproduces.

## 4. The A/B, same session, same tree, both seeds

`ATTEMPTS=20`, shipped scenario, `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`; the
control is P80's own seed-5/6 record, re-run on the post-patch tree as `W0` to prove
the off path did not move. `logs/p82/p82_ab.py` prints this table.

| cell | placed | wall | wall/pick | wall/sim | placed/min wall |
| --- | --- | --- | --- | --- | --- |
| two-line **OFF**, seed 5 (`T20`) | 16/20 | 497.2 s | 24.9 s | 2.57 | 1.93 |
| two-line **OFF**, seed 5 (`W0`, post-patch) | 16/20 | 501.1 s | 25.1 s | 2.59 | 1.92 |
| **two-line ON**, seed 5 (`W1`) | 16/20 | **327.1 s** | **16.4 s** | **1.69** | **2.94** |
| **two-line ON**, seed 5 (`W2` repeat) | 16/20 | **327.8 s** | 16.4 s | 1.69 | 2.93 |
| two-line ON, seed 5 (`W3`, + timers) | 16/20 | 333.9 s | 16.7 s | 1.73 | 2.88 |
| two-line **OFF**, seed 6 (`T6`) | 10/20 | 476.8 s | 23.8 s | 2.47 | 1.26 |
| **two-line ON**, seed 6 (`W4`) | 10/20 | **312.9 s** | **15.6 s** | **1.62** | **1.92** |
| single arm, seed 5 (`S20` / `R2`) | 12/19 | 478.0 / 480.3 s | 25.2 s | 1.38 / 1.39 | 1.51 / 1.50 |
| single arm, seed 6 (`S6`) | 13/19 | 478.8 s | 25.2 s | 1.40 | 1.63 |

**Wall/pick falls 25.1 -> 16.4 s at seed 5 (-34.6 %) and 23.8 -> 15.6 s at seed 6
(-34.4 %), with the same counts and the same simulated span** (193.3 / 193.2 s,
9.70 s/attempt). The repeat `W2` is 0.7 s from `W1` (0.2 %), so the effect is two
orders of magnitude outside the run-to-run spread.

### 4a. Where the saved wall came from (the timers, ON vs OFF)

Same instrument, same scenario, `logs/p82/{R1,W3}.timers.json`:

| term | OFF (R1) | ON (W3) | note |
| --- | --- | --- | --- |
| rounds / shared ticks | 47,795 / 23,530 | **48,021 / 23,530** | same tick count, **+0.5 % rounds -> no spin** |
| rounds per shared tick | 2.031 | 2.041 | unchanged |
| per-round wall | 10.51 ms | **6.95 ms** | |
| per-tick wall | 21.34 ms | **14.19 ms** | |
| physics | 255.9 s (51.0 %) | 250.7 s (75.1 %) | same work (profile noise +-2 %) |
| worker segments | 78.9 s (15.7 %) | 76.7 s (23.0 %) | same work |
| **main-thread poll wait** | **240.5 s (47.9 %)** | **77.6 s (23.2 %)** | mean 5.03 -> **1.62 ms**; timeouts 99.2 % -> 5.4 % |
| arbiter Python | 1.14 s (0.2 %) | 1.06 s (0.3 %) | unchanged |
| residual (wait not covered by a segment, handoff, feed) | **166.2 s (33.1 %)** | **5.5 s (1.6 %)** | **the dead wall, gone** |
| render (`_tick_frame`) | 0.059 s | 0.056 s | 0.0 % in both |

The pump's wait **histogram** is the mechanism: OFF it is one spike in the 5-10 ms
bin (47,414 of 47,795 samples = the timeout itself); ON it is the *worker's* own
distribution (mean 1.62 ms against the segment's 1.65 ms, p90 3.45 vs 3.44) — i.e.
the main thread now wakes when the arm finishes its segment instead of 3.4 ms later.

So the wall fell by 168.3 s (502.2 -> 333.9) against 161.6 s of measured dead wait:
the difference is the extra `schedule` calls and the handoff. **No work was removed;
the waiting was.**

## 5. The bit-identity proof

`logs/p82/p82_report.py --same <reference> <candidate>` compares every
`[fruit]`-prefixed line — the physics record, the `[biarm]` scheduler rows, `[task]`,
`[motion]`, `[cycle]`, `[stats]` — in order.

| candidate | reference | result |
| --- | --- | --- |
| `R1` two-line + I2 timers | `logs/p80/T20.log` | **865/865 identical** |
| `R3` two-line + py-spy | `logs/p80/T20.log` | **865/865 identical** |
| `W0` knob **off**, post-patch tree | `logs/p80/T20.log` | **865/865 identical** |
| `W1` knob **on** | `logs/p80/T20.log` | **865/865 identical** |
| `W2` knob **on**, repeat | `logs/p80/T20.log` | **865/865 identical** |
| `W3` knob on + timers | `logs/p80/T20.log` | **865/865 identical** |
| `W4` knob **on**, seed 6 | `logs/p80/T6.log` | **814/814 identical** |
| `R2` single + I2 | `logs/p80/S20.log` | **710/710 identical** |
| `R4` single + py-spy | `logs/p80/S20.log` | **710/710 identical** |
| `A1` accept, knob **set**, single arm | `logs/p71/accept_rails_none.log` | **346/346 identical** (after dropping the `[cycle]` prints the accept does not normally carry: my driver exported `FRUIT_CYCLE_REPORT=1`) |

That is the whole claim: **the same run, 34.5 % less wall.** The lever moves the
arbiter's wake-up, and nothing else can move because the run is byte-identical at two
seeds, with the timers installed and without them, and on the single-arm path.

## 6. The practical consequence: the wall arithmetic

`logs/p82/p82_ab.py`, mean of the two seeds' per-cell rates (P80's convention):

| quantity | two-line OFF | two-line ON | single arm |
| --- | --- | --- | --- |
| **placed/min wall** | 1.59 | **2.43** | **1.57** |
| ratio to the single arm | **1.02x** (P80's number, recomputed) | **1.55x** | 1.00 |
| wall/pick | 24.4 s | **16.0 s** | 25.2 s |
| wall/sim (the harness factor) | 2.52 | **1.66** | 1.39 |
| sim clock (batch span / attempt) | 9.7 s | 9.7 s | 18.2 s |

**The arithmetic, stated as a chain:**

* the two-line's **simulated** clock is **1.88x** the single arm's (9.7 vs 18.2 s of
  simulated time per attempt) — P80's number, unchanged by the lever, as it must be;
* its harness cost was **1.81x** the single arm's wall per simulated second (2.52 vs
  1.39), so the wall gain was **1.88 / 1.81 = 1.03x** per pick (P80's wash);
* the lever takes the harness factor to **1.19x**, so the wall gain is
  **1.88 / 1.19 = 1.57x** per pick;
* the **placed rate** multiplies that by the count, which is a seed draw and not the
  lever's: pooled placed per attempt is **0.650 (two-line) vs 0.658 (single)** in both
  arms, so the rate ratio is the per-pick ratio plus noise — **1.55x pooled** (1.95x at
  seed 5, 1.18x at seed 6);
* **the two-line therefore crosses P80's 1.02x bar and the standing 1.25x bar on the
  wall denominator**, not just on the sim denominator.

What is left of the harness after the fix (1.19x) is **measured and not a poll**: the
two arms' control work per shared tick (3.3 ms against the single arm's ~0) plus the
permit handoff, with the physics step (10.7 ms/tick, 75 % of the remaining wall) the
floor that no arbiter change can move. The two-line's wall/sim 1.66 is the honest
number for this design; 1.39 would require the second arm to cost nothing.

## 7. What this does not show, and the honest limits

* **It removes idle latency, so it needs a machine that is not CPU-saturated.** This
  box runs the cell at ~3 of 32 cores (measured: 351 CPU-s over 120 s of wall during a
  wake-on run), so the run is latency-bound and 32 % of its wall was a timer. On a
  saturated machine the same work would queue, and the win would shrink towards zero.
  The measured CPU *work* is unchanged (physics 51->75 %, segments 15.7->23.0 % of a
  shorter wall in §4a) — this is not a cheaper run, it is a denser one.
* **The dead wall is not zero on a saturated loop**: 5.4 % of pump calls still time
  out (rounds where nothing was pending) and the residual is 1.6 %.
* **It is not the second arm's cost.** The remaining harness 1.19x is the two arms'
  control plus handoff; a scheduler that let both arms work *concurrently* would be a
  different design (the permit exists because PhysX reads are not thread-safe), and
  nothing here says it would be faster - only that the poll was pure waste.
* **No motion reference is re-recorded and none is owed**: the change cannot move the
  physics (proved), so `configs/motion_reference*.json` (`8952c320` / `eb697f23`) stand.
* **The two-line's count advantage is not the lever's**: pooled placed/attempt is the
  same in both arms (0.650 vs 0.650 ON/OFF; 0.650 vs 0.658 against the single arm).
* **P80/P81's wall column is a pre-P82 number.** Every two-line wall figure in those
  documents (1.93 placed/min, 24.9 s/pick at seed 5) is the **shipped** behaviour and
  stays valid for the shipped tree, because the knob is off by default; with the knob
  on, the same cells read 2.94 placed/min and 16.4 s/pick.

## 8. The other consumer of the same code: the F2 shared-station scheduler

`bimanual.py` serves both schedulers, so the shared-station pipeline
(`FRUIT_BIARM=1`, 10 attempts, seed 5) was run OFF then ON. It is the same code and
the same arbiter, so it pays the same poll.

| cell | placed | wall | wall/pick | wall/sim | placed/min wall |
| --- | --- | --- | --- | --- | --- |
| `F0` shared-station **OFF** | 8/10 (left 3/5, right 5/5) | 317.6 s | 31.8 s | 2.22 | 1.51 |
| `F1` shared-station **ON** | 8/10 (left 3/5, right 5/5) | **201.8 s** | **20.2 s** | **1.41** | **2.38** |

**499/499 `[fruit]` lines identical** between the two, `-36.5 %` wall. So the lever's
mechanism is the arbiter's poll and not anything two-line-specific, and the second
scheduler gets the same bit-identical speedup. (Its wall/sim 2.22 -> 1.41 lands at the
single arm's 1.39, because on this scheduler only one arm owns the station and the two
attempts overlap less - a different scenario, not a better one.)

## 9. Gates, provenance, limits

* **`scripts/190_twoline_gate.sh` PASS on `W1`** against P80's own 20-attempt two-line
  reference (`logs/p80/motion_reference_twoline_p80_20.json`): every descent inside its
  budget, the fingerprint matches, 16/20 above the 0.5 floor. The carry cones are
  reported, not gated (the dynamic line's convention).
* **`scripts/accept.sh` with the knob set** (`A1`): **6/9, `fingerprint: matches
  configs/motion_reference.json`**, worst descent `|v|max` 0.1100 (budget 0.160-0.161),
  lurch 0.017 (budget 0.291) — the standing rate-only FAIL on the P71/P72 branch, and
  the physics stream is 346/346 identical to `logs/p71/accept_rails_none.log`.
* **`scripts/selfcheck.sh` PASS, 0 failures** on the final tree (`logs/p82/selfcheck.log`).
* **Pins**: `tasks.py` `e8dfa6d8` (untouched), `bimanual.py` `980923a6` **-> `146e6252`**
  (the `FRUIT_BIARM_WAKE_ON_REQUEST` patch, default off; `logs/p82/header.txt` carries
  the before/after list), `configs/motion_reference.json` `8952c320` and
  `configs/motion_reference_twoline.json` `eb697f23` **untouched** (nothing was
  re-recorded: the physics cannot move), checkpoint `moe_v13s` `61da390a`.
* **Nothing adopted, no commit**: the change is one default-off knob. Flipping it is an
  owner decision with a named consequence — it re-baselines every two-line wall number
  (P80 §6, P81 §6) from ~2.5 wall/sim to ~1.66, and it changes no sim-time number at
  all.
* **Not measured here**: a saturated machine (the win is latency), the `collector`
  path (it runs the same `run_bimanual`, so it inherits the knob - unmeasured), and a
  concurrent-arm scheduler (a different design; the single permit exists because PhysX
  reads are not thread-safe).

## 10. Evidence

`logs/p82/METHOD.md` (the registration), `RESULTS.md` (this), `header.txt` (pins),
`timers.py` + `profile_20.py` (I2: per-round arbiter timers; `R*.timers.json`,
`W3.timers.json`), `run_pyspy.sh` + `ps_agg.py` (`R3/R4.speedscope.json.gz`,
`R3/R4.profile.txt`; 12.5 MB and 5.0 MB of raw samples, gzipped to 183 kB and
153 kB, kept because they are the only per-function record), `one_run.sh`, `run_p82.sh`, `run_p82_stage2.sh`,
`apply_wake_patch.py`, `p82_report.py`, `p82_ab.py` (+ its `ab.txt`), `identity.txt`
(the ten
identity checks above, machine-printed), and the cells
`{R1,R2,R3,R4,W0,W1,W2,W3,W4,F0,F1,A1}.log` + `.stamps` + `.driver`
(`A1`'s gate output is in `A1.driver` - `scripts/154_claim_run.sh` redirects the claimed
command's stdout there, not to the wrapper's own redirect - and `smoke/` holds the four
pre-flight probes, including the two launcher attempts that failed before `run_pyspy.sh`
was rewritten to go through `scripts/run.sh`).
