# P27-A: the belt-speed premise, audited (Tier-C offline)

**Scope.** Branch `p-supply`, tree as of 2026-10-21 09:0x. Read-only on
`src/`, `scripts/`, `configs/`; no simulator run was made for this
document. Every number below is either (a) re-derived offline with the
shipped code (marked *derived*), or (b) quoted from a named log. The P27
driver (`logs/p27/run_p27.sh`) was running throughout; the results that
landed while this was written are in section 4.3, labelled with their read
time.

**The premise under test** (owner, verbatim in substance): *"I introduced
the conveyor belt speed encoder precisely so the model adapts to different
belt speeds; even if faster-than-training fails, at slower speeds the
grasp/sort success should hold or improve. The system should adapt to
different constant-velocity belts."*

---

## 0. Verdict in four lines

1. **What adapts is the *schedule*, not the model.** `encoder_speed` feeds
   the trigger's arrival arithmetic, the catch lead, the selector floor and
   the descent deadline. In the shipped build it is **not a measurement**:
   with the cleats off (default) `Conveyor.step` returns *before* the
   encoder update, so `encoder_speed` stays at `cfg.belt_speed`; the
   runner's own `[stats]` line prints `no cleats to measure travel`.
   "The encoder adapts the line to a belt speed" is therefore, today,
   "the `FRUIT_BELT_SPEED` value is threaded through the schedule".
2. **The policy never sees the belt speed.** Its input is a 2-frame
   128x128 RGB-D(+mask) stack, 25-D proprio and an 8-D goal; there is no
   speed channel. The one speed-correlated scalar is `goal[3:6]`, the
   *target fruit's measured velocity at selection* — episode-constant,
   rolling-contaminated, and (0.08 vs 0.12) a ~1.1 sigma move in a
   normalizer that is **centred on the 0.06 store**. So the premise's
   "the model adapts" is, on this interface, the **trigger's timing**.
3. **The record says the measured 0.12 -> 0.15 step is flat on every
   interface that has a mechanism readout** (two-line patch 11/20 ->
   10/20 same seed+mass; direct 32/45 -> 31/45; two-line patch
   pre-mass 12/20 -> 14/20) and **loud and negative only on the single-arm
   acceptance** (9/10 -> 3/9), where the P27-B isolation has now separated
   it: 0.12+flip 7/10, 0.15+flip 3/9, 0.15 no-flip 5/9 - the 3/9 needs
   *both* changes, so it is not the belt alone (one sample per cell). The
   full direct ladder landed while this was written: **6, 6, 2, 5 of 15**
   at 0.08 / 0.10 / 0.12 / 0.15 (one seed each, one tree; every pairwise
   Fisher p >= 0.215) - **no resolved speed effect, and the 0.12 point is
   the low draw, not a trend**. The escape *magnitudes* did **not** shrink
   at any speed (section 4.3).
4. **The direct interface is speed-flat over 0.08-0.15, and the mechanism
   it would have to improve is not the belt.** The dominant failure is the
   carried-not-placed class, a *hand-frame* escape of 17.9-957 mm (median
   278 mm) over ~25 ticks, while the belt can feed at most `v * 0.21 s` of
   it — **24 mm at 0.12, 17 mm at 0.08, i.e. <= 10 % of the median
   escape**. The ladder measures exactly that: **median escape 270 / 298 /
   279 / 251 mm at 0.08 / 0.10 / 0.12 / 0.15** with a belt-fed share of
   **6-11 % (median) at every speed**, and a rate of 6/6/2/5 of 15 with no
   pairwise p below 0.215. So: no resolved speed effect on either side of
   0.12, the escape magnitude is independent of the belt, and any rate
   movement is the *incidence* (the contact/impulse channel), not the
   belt-fed transport and not the model. The *costs* are unambiguous (a
   longer hover wait per attempt, a 1.5x longer arrival cadence, a 1.5x
   longer recycle loop).

---

## 1. The encoder's path, exactly

### 1.1 What `encoder_speed` *is* in this build

`src/fruit_sorting/conveyor.py:164-173`:

```python
#: Belt encoder [m/s]: the speed the belt *furniture* actually travels,
#: differenced from the cleat phase each step rather than read back from the
#: commanded surface velocity. In this build the two agree by construction
#: (the cleats are kinematic, so they cannot slip) ...
self.encoder_speed = float(cfg.belt_speed)
```

`src/fruit_sorting/conveyor.py:475-503`:

```python
def step(self, dt: float) -> None:
    ...
    if self.ramp_enabled and self.speed != self.target_speed:
        ... self._apply_speed(...)
    if not self.enabled:          # <-- cleats off: the shipped default
        return                    #     encoder_speed is NEVER updated
    self.pulley_angle += ...
    previous_phase = self.phase
    self.phase = (self.phase + self.speed * dt) % self.cleat_span
    self.encoder_speed = (self.phase - previous_phase) / max(dt, 1e-9)
    ...
```

and `conveyor.py:195-197` disables the only thing that could be
differenced:

```python
if os.environ.get("FRUIT_CLEATS", "0") != "1":
    self.cleat_count = 0
    self.enabled = False
```

Consequences, in order of importance:

* **Shipped build (`FRUIT_CLEATS` unset): `encoder_speed == cfg.belt_speed`
  for the whole run.** It does not follow a ramp, a `stop()`, or a real
  belt's deviation. The runner says so itself
  (`src/fruit_sorting/tasks.py:1474-1488`):

  ```python
  encoder = float(getattr(belt, "encoder_speed", float("nan")))
  command = float(getattr(belt, "speed", float("nan")))
  spread = abs(encoder - command)
  if getattr(belt, "cleats", None):
      encoder_text = f"encoder={encoder:+.3f} m/s (command {command:+.3f}, spread {spread:.4f})"
  else:
      encoder_text = (f"encoder={command:+.3f} m/s nominal (command {command:+.3f}, "
                      "no cleats to measure travel)")
  ```

  Every shipped run therefore logs, e.g.
  `encoder=-0.150 m/s nominal (command -0.150, no cleats to measure travel)`
  (`logs/p26/10_accept_015.log`, last `[stats]`), and the pre-P26
  acceptance at 0.12 logs `encoder=-0.120 ... nominal` (`logs/accept.log`).
* **With `FRUIT_CLEATS=1` the encoder is a difference of the *commanded*
  phase**, i.e. it reproduces the applied `belt.speed` (the cleats are
  kinematic and the surface velocity is written from the same number). It
  is a consistency check, not an independent readback: it can only differ
  during the modulo wrap, which the code corrects.
* **A real independent readback exists only on the fruit**
  (`spawner.velocity`), which is why `transport_speed()` prefers the
  encoder when it is non-zero: the measured fruit velocity is
  rolling-contaminated (the docstring quotes a demo's stored `vy` of
  -0.0225 against a -0.06 belt, `policy/trigger.py:206-213`).

So the honest statement of the premise is: **the encoder is a setpoint
echo; the line is belt-speed *parameterised*, not belt-speed *adaptive*.**
On real hardware this is exactly the failure mode the owner would care
about (a conveyor whose encoder reads 0.091 while the config says 0.12):
the code would *use* 0.091 correctly for every schedule quantity below,
but nothing in this build would ever produce 0.091.

### 1.2 The command source and the documented scenario

`src/fruit_sorting/assets.py:208-216`:

```python
# The shipped default (v7 directive) is the dynamic line's measured band,
# **0.12 m/s** ...
belt_speed: float = field(
    default_factory=lambda: -abs(float(os.environ.get("FRUIT_BELT_SPEED", "0.15")))
)
```

The comment says 0.12; the code says **0.15**. Git says the default was
flipped on purpose: `5268a8c` ("P26 ... the belt 0.15: the `FRUIT_BELT_SPEED`
default 0.12 -> 0.15 (the lead/floor already belt-speed-aware)"). **So the
current shipped scenario is 0.15, the documents' "shipped 0.12" is the
pre-P26 scenario, and the collectors' stores are 0.12** (section 3). Every
speed statement in this repo must say which of the two it means; the
acceptance's own `[stats]` line is the only place a log records it.

### 1.3 Who reads the speed, and what each reader does with it

| consumer | code | formula | scales with `v`? | invariant in *time*? |
| --- | --- | --- | --- | --- |
| trigger's approach speed | `policy/trigger.py:198-222` | `encoder` if finite/non-zero, else `-measured vy` | yes (value) | - |
| trigger's arrival | `policy/trigger.py:335-338` | `t_arrive = max(dy,0)/v`; fire iff `t_arrive <= lead` | no (`t_arrive`) | **yes: fire at `dy <= v*lead`** |
| trigger's reach gate | `policy/trigger.py:329` | `dy > reach` (0.20 m) | no | no (time window `0.20/v`) |
| trigger's lateral gate | `policy/trigger.py:327` | `abs(dx) > lateral` (0.16 m) | no | no |
| ACQ lead (W7-B) | `policy/trigger.py:246-250` | `lead + margin + \|jaw-station\|/0.20`, `reach = max(reach, v*lead_eff + 0.05)` | only the *reach* term | **yes: the lead is a time** |
| catch lead (scripted) | `tasks.py:4348-4369` | `min(v*(0.4 + t_desc + 0.15) + 0.03, 0.80)` | yes | **yes** (`_dynamic_pick_lead` is a time converted to metres) |
| selector floor | `tasks.py:4254-4287` | `_dynamic_pick_lead() + v*1.5 + 0.03` | yes | **yes** |
| descent hover deadline | `tasks.py:7430-7437` | `deadline = v*(t_desc + 0.15)` | yes | **yes** |
| prepose lead (scripted select) | `tasks.py:4126-4136` | `max(0.12, \|cfg.belt_speed\|*0.9)` | yes, from **cfg** not the encoder | **yes** |
| reach-anywhere intercept | `tasks.py:4481-4495` | `y = y_f + vy*(setup + hover + t_desc + margin)`; `vy` = **measured** fruit velocity, encoder as fallback | measured | yes |
| takeoff belt match | `tasks.py:9426-9452` | `v_ref = fruit measured vy` (encoder fallback), ramp to 0 over `trans_s=0.25` | measured | yes |
| feeder cadence | `fruits.py:1171-1177` | `period = _release_gap()/\|cfg.belt_speed\|` | yes, from **cfg** | no: the *time* cadence is 1/v |
| feeder backlog placement | `fruits.py:1285-1302` | `along = spawn_y - late*\|cfg.belt_speed\|` | yes, from **cfg** | - |

Derived at the four sweep speeds (`_approach_duration(0.06, 0.15, 0.8) =
0.775 s`, so the primitive's lead time is `0.4 + 0.775 + 0.15 = 1.325 s`):

| `v` [m/s] | trigger fire distance `0.9v` | primitive lead distance | selector floor | spawn->station `0.68/v` | patch slice period `0.18/v` | recycle loop `1.38/v` |
| --- | --- | --- | --- | --- | --- | --- |
| 0.08 | 7.2 cm | 13.6 cm | 0.286 m | 8.50 s | 2.25 s | 17.3 s |
| 0.10 | 9.0 cm | 16.3 cm | 0.343 m | 6.80 s | 1.80 s | 13.8 s |
| **0.12** | 10.8 cm | 18.9 cm | 0.399 m | 5.67 s | 1.50 s | 11.5 s |
| **0.15** | 13.5 cm | 22.9 cm | 0.484 m | 4.53 s | 1.20 s | 9.2 s |
| 0.18 | 16.2 cm | 26.8 cm | 0.569 m | 3.78 s | 1.00 s | 7.7 s |

**The whole handover is a *time* schedule.** Everything that has a `v` in
it is a `v * (fixed seconds)` conversion, so the *schedule* is
speed-invariant in time and only its *distance equivalent* changes. This
is the correct design (it is what makes the line work at 0.06 and 0.15
with one set of constants), and it also means **a slower belt cannot
"give the hand more time"** — the handover always starts 1.325 s before
the fruit arrives, at every speed.

### 1.4 Three sources of speed, and they are not the same one

1. `encoder_speed` — the trigger, the catch lead, the selector floor, the
   descent deadline. (A setpoint echo, section 1.1.)
2. `cfg.belt_speed` — the feeder cadence and the prepose lead
   (`tasks.py:4134`, `fruits.py:1174/1285`).
3. the *measured fruit velocity* — the reach-anywhere intercept and the
   takeoff's belt-match `v_ref` (`tasks.py:4491`, `9431`).

They agree today (all are the same number). They would **not** agree if
the encoder ever became a real measurement while `cfg.belt_speed` did not:
the supply would keep its old cadence and the takeoff would track the
fruit's rolling velocity. That is a named gap, not a bug on any shipped
path — but it is the first thing to fix before "the encoder adapts the
cell" can be claimed on hardware.

---

## 2. What the policy actually observes

`src/fruit_sorting/rl_env.py:57-64`:

```
Observation interface (identical to training): the head-camera frame is rendered
and read every 4 physics ticks (30 Hz), downsampled and buffered by
``PolicyRunner.push_frame``; proprioception is all 22 joint positions + the finger
opening + the two tactile forces (25-D); the goal is the 8-D
``[position(3), velocity(3), diameter, bin_index]`` vector the demonstrations
recorded.
```

* `proprio()` — `rl_env.py:1213-1240` — 22 dof + finger + 2 tactile = **25,
  no belt term**.
* the goal — built once per episode at `rl_env.py:1034-1042` from
  `select_target`'s `state()` (`fruits.py:1620-1621`, `"velocity":
  self.velocity(sample)`), i.e. the **rigid body's measured velocity**.
* the image stack — `obs_horizon = 2` frames at 30 Hz (33 ms apart), 128x128,
  5 channels (RGB + depth + mask). At 0.12 m/s the fruit moves **4.0 mm**
  between the two frames; at 0.08, 2.7 mm.
* the model — `policy/model.py:112-117`, `goal_dim = 8`, `proprio_dim = 25`.

**There is no belt-speed channel.** The only channel that even correlates
with it is `goal[3:6]`, and it is a poor speed signal by construction: it
is the *target's* velocity at the moment of selection, constant for the
whole episode (`within-episode std = 0.0000` over all stores), and it
includes the fruit's rolling and its state at selection. Per-episode means
by store (25 episodes each, offline read of the `.npz` goals):

| store | collection belt | goal `vy` mean | sd | range |
| --- | --- | --- | --- | --- |
| `demos_v7` | 0.06 | -0.0606 | 0.0423 | -0.219 .. -0.021 |
| `demos_v9` | 0.06 | -0.0540 | 0.0353 | -0.219 .. 0.000 |
| `demos_v10` | 0.06 | -0.0569 | 0.0366 | -0.251 .. 0.000 |
| `demos_v11` | 0.12 | -0.1186 | 0.0298 | -0.200 .. -0.026 |
| `demos_v12` | 0.12 | -0.1145 | 0.0374 | -0.212 .. +0.038 |
| `demos_v13p` | 0.12 | -0.1197 | 0.0341 | -0.240 .. -0.014 |
| `demos_v12_015` | 0.15 | -0.1537 | 0.0571 | -0.272 .. -0.028 |

So the channel *does* move with the collection speed (this is the only
place in the repo where a store's belt speed can be inferred at all —
see the manifest gap in section 7), but the spread at a fixed speed is
0.03-0.06, i.e. **the 0.12 -> 0.08 step is ~1 sd of the training spread**.

The checkpoint normalizer is **0.06-centred** (`moe_v12` and `moe_v13s`
share it: `goal_mean[vy] = -0.0570`, `goal_std = 0.0366`):

| belt | z of the goal `vy` |
| --- | --- |
| 0.08 | **-0.63** |
| 0.10 | -1.17 |
| 0.12 | **-1.72** |
| 0.15 | -2.54 |

Read carefully: the *deployment* speed (0.12) sits at z = -1.7, while
0.08 sits at -0.6. That is a statement about the normalizer, not about
the fine-tune data (moe_v12 was fine-tuned on `demos_v10` at 0.06 as the
base and `demos_v11` at 0.12 as the rollouts; `moe_v13s` on `demos_v11`
base + `demos_v12` rollouts, both 0.12). It does mean 0.08 is **not** an
out-of-distribution input for this channel; it means the channel cannot be
the mechanism either way.

**Plainly: the model does not see the belt speed. Whatever "adaptation"
the owner has observed is the encoder's arithmetic in the trigger and in
the scripted primitive's schedule, plus (in the shipped policy line) the
fact that the primitive — not the policy — owns the grasp.**

---

## 3. The training distribution and the predicted transfer

### 3.1 The distribution

* All policy stores are 0.12 except the older lineage (`v7/v9/v10` at 0.06,
  which are in moe_v12's base) and one 25-episode shard at 0.15
  (`datasets/v12_s0_015` -> `demos_v12_015`, the P2b ladder's step b).
* The *grasp-relevant* part of an episode is the wait loop through the
  close: median 209 frames at 30 Hz ~ 7 s (`demos_v12`), i.e. the recorded
  approach is ~0.84 m of belt travel at 0.12.
* The *labels* come from the scripted primitive, whose timing is itself
  speed-aware (section 1.3) — so a demo collected at speed `v` encodes
  `v`-correct timings, and behaviour cloning at one speed teaches *that*
  speed's timing.
* **Manifests do not record the belt speed** (section 7), so the training
  speed of a store is inferred from the collection script and the goal
  `vy`, not from the artifact.

### 3.2 Slower (0.08/0.10): what gets easier, what gets harder

Easier (all *derived* from the code, none yet measured at 0.08):

1. **The relative displacement during every fixed-time contact phase is
   proportional to `v`.** The close reaches sustained contact in 16-31
   ticks (0.12: 1.6-3.1 cm of fruit travel; 0.08: 1.1-2.1 cm); the
   visible-jaw gate's 6 cm distance window is 0.50 s at 0.12 and 0.75 s at
   0.08 — the primitive gets *more* wall-clock to close.
2. **The catch residuals shrink**: the descent ends 10.9-14.4 mm before the
   aim (R11-A.1, at 0.12), the catch-up then closes it; both terms scale
   with `v`.
3. **The selector's usable band grows**: the floor falls 0.399 -> 0.286 m
   while the upstream edge (0.85 m) is fixed, so the candidate band grows
   ~25 % (0.45 -> 0.56 m). The belt's *spatial* layout is invariant (gaps
   are drawn in metres), so the number of candidates in the band is
   unchanged; only the time between them grows.
4. **The crash contacts** (the 0.15 acceptance's 49.8 N *close* and 80.3 N
   *lift*) are the one place where speed enters quadratically (an impulse);
   they should soften at 0.08.

Harder:

1. **The arrival cadence is `1/v`**: every release period, the
   spawn->station travel (8.5 s vs 5.7 s) and the recycle loop
   (17.3 s vs 11.5 s) stretch. For the *single* arm this is not
   starvation — the patch sheet delivers ~1.6 fruit per 0.18 m = 8.9
   fruit/m, i.e. ~0.7-1.3 fruit/s against a 0.067/s demand, and the band
   *count* is invariant — but it does change the *timing* of the
   selection, the queue interlock and the collector's wall clock.
2. **The hover wait per attempt may grow** (a *prediction* to measure, not a
   derivation): the time-schedule terms are constant, yet R3 *measured* the
   cycle report's descent block at 3.19 / 2.40 / 1.88 s for 0.12 / 0.15 /
   0.18 (a slope of ~26 s per m/s, `logs/w8/R3_RESULTS.md` s4) - whatever
   the block's exact decomposition, that slope extrapolates to **~+1.1 s
   per attempt at 0.08**, i.e. ~+7 % span at the same success count. Endpoint
   E4/E6 measures it directly.
3. **In the *learned-gate* path (trigger off) the hand is parked in the
   fruit's path longer.** The direct arm parks at the *grip* pose
   (`FRUIT_DIRECT_HOVER=0`) and holds `FRUIT_DIRECT_HOLD_TICKS=20`; the
   learned gate is the 6 cm *distance* test, so its fire is 0.50 s before
   arrival at 0.12 and 0.75 s at 0.08 - the open jaws sit in the approach
   line ~1.5x longer. (With the trigger on, the fire is a *time* lead, so
   that exposure is speed-invariant; with ACQ=1 it is a longer, constant
   ~1.5-2 s.) No record has measured a consequence of the exposure (the
   pre-contact class in W5/W7-B is a *setup* deficit, not a jaw
   obstruction), but it is the only mechanism by which slower can *lose*
   on the acquisition channel.
4. **The transport model's own assumption** (`fruits.py:1424-1455`):
   `enforce_transport` re-sets a stalled fruit to `0.4 * belt.speed`
   (`transport_efficiency = 0.40`) whenever `|v_y| < 0.02 m/s`. At 0.08
   that rescue is 0.032 m/s; at 0.06 it is 0.020, exactly the threshold.
   This is a low-speed artefact to watch with `scripts/170`, not a
   predicted failure at 0.08.

### 3.3 Faster (0.15): the reverse

All of the above flip sign: less time per fixed-time phase, larger
residuals, a narrower band (floor 0.484 m), a shorter hover wait, more
crash-prone closes. The record (section 4) already reads 0.15 as flat on
the two interfaces with mechanism data and negative on the single-arm
acceptance.

---

## 4. What the existing numbers already say

### 4.1 Every existing speed point

| interface | belt | N | result | source |
| --- | --- | --- | --- | --- |
| scripted single arm, acceptance | 0.12 | 10 | **9/10, 15.2 s/attempt** | `logs/accept.log` (pre-P26 tree) |
| scripted single arm, acceptance | 0.15 | 9 | **3/9, 15.4 s/attempt** | `logs/p26/10_accept_015.log` (P26 default, + B1c flip) |
| scripted single-arm *collection* | 0.12 | - | "72 % per attempt" | `logs/p2b/WORKLOG_ENTRY.md` |
| scripted single-arm *collection* | 0.15 | 45 | **25/45 = 55.6 %** | `logs/p2b/40_collect_v12_s0_015.log` |
| direct interface (P2b A/B) | 0.12 | 45 | **32/45 = 71.1 %** | `logs/p2b/ab012/` |
| direct interface (P2b ladder a) | 0.15 | 45 | **31/45 = 68.9 %** | `logs/p2b/ladder015_control/` |
| + fine-tune on 0.15 data (`moe_v13`) | 0.15 | 45 | **30/45 = 66.7 %** | `logs/p2b/ladder015_v13/` |
| two-line patch (pre-mass base) | 0.12 | 20 | 12/20, 3.63 placed/min, interval 16.53 s, starved 19/22 | `logs/w8/R3_RESULTS.md` s4 |
| two-line patch (pre-mass base) | 0.15 | 20 | 14/20, **4.69** placed/min, 12.80 s, starved 17/25 | same |
| two-line patch (pre-mass base) | 0.18 | 20 | 14/20, 3.82 placed/min, 15.71 s, **starved 115**/38 | same |
| two-line patch (real mass, P12-A seed 11) | 0.12 | 20 | **11/20** | `logs/p12/A_RESULTS.md` |
| two-line patch (real mass, P26 seed 11) | 0.15 | 20 | **10/20** (left 5/10, right 5/10) | `logs/p26/211_patch015_seed11.log` |
| two-line patch (real mass, pooled) | 0.12 | 60 | 45/60 | `logs/p12/A_RESULTS.md` |
| direct patch, ACQ=1 (N=5) | 0.12 | 75 | 21/75 (per-seed 4,4,4,4,5) | `logs/w8/A_direct_ab/` |
| **direct (P27-C1)** | **0.08** | 15 | **6/15** | `logs/p27/20_direct_008.log` |
| **direct (P27-C1)** | **0.10** | 15 | **6/15** | `logs/p27/21_direct_010.log` |
| **direct (P27-C1)** | **0.12** | 15 | **2/15** | `logs/p27/22_direct_012.log` |
| **direct (P27-C1)** | **0.15** | 15 | **5/15** | `logs/p27/23_direct_015.log` |
| **scripted acceptance, + B1c flip** | **0.12** | 10 | **7/10** | `logs/p27/10_acc_012_flip.log` |
| **scripted acceptance, flip off** | **0.15** | 9 | **5/9** | `logs/p27/11_acc_015_noflip.log` |
| scripted dynamic ladder (older tree) | 0.06 / 0.09 | 10 each | 6/10, 4/10 (failure sets; the 0.12 row mixed three code versions) | 项目总结报告 P2 |

### 4.2 Reading it

1. **The same 0.12 -> 0.15 step changes sign with the base**: +2/20 on
   the pre-mass two-line patch, **-1/20** on the real-mass base at the same
   seed, -1/45 on the direct A/B, -16 pt on the single-arm
   collector. Per the AGENTS section 2 rule each of these is a different
   scenario; the transportable reading is the *mechanism*, and the one
   mechanism number that moves monotonically is the **arrival structure**
   (the descent block 3.19 -> 2.40 s, the attempt span 15.08 -> 14.33 s,
   the catch leg flat at `|v|max` 0.106-0.116 and `end` 8.2-12.2 mm). The
   rate cannot carry the speed question; the interval/starvation can.
2. **The 0.18 point is the only unambiguous negative**, and its mechanism
   is the *floor*, not the catch: the fixed 1.5 s setup floor is 0.27 m of
   belt at 0.18, so the usable band shrinks 0.45 -> 0.27 m and the
   starved slots explode (115 left vs 19 at 0.12). At 0.08 the floor is
   *smaller* (0.286 m) and the band *grows* — so the 0.18 mechanism
   predicts **no** starvation at the slow end. The R11-A result (a
   band-relative floor of ~0.20 m collapsing the stocked scattered line
   9/10 -> 4/10) is a warning about *removing* the floor, not about the
   speed.
3. **The 0.15 fine-tune is the one direct test of "train for the new
   speed"** and it did not transfer (31/45 -> 30/45 with 25 fresh 0.15
   episodes; offline fidelity improved, 0.149 -> 0.133 rad,
   `logs/p2b/44_fidelity_015.txt`). A 25-episode fine-tune is small, but
   it is a *measured* null on the "retrain for the speed" route.
4. **The P26 3/9 is not attributable yet.** Its failure set is a *contact*
   set, not a timing set, **and it has a supply-side component**: 3 placed
   (pear, strawberry, orange), 3 carried-not-placed (attempts 0/1/5), 3
   `grasped=False` "fruit did not follow the gripper" (forces 80.3 / 4.1 /
   0.0 N), plus **one skipped slot** ("no eligible fruit"; the run's supply
   stats read `fell_off=18` of `released=22`, `supply_skipped=67` — the
   counter includes payloads released off the belt, and the 0.12 acceptance
   never reaches that line, so it has no 0.12 comparator), one "fruit
   drifted 1168 mm off the pick centre" blowup, and two anomalous closes
   (49.8 N / 27.3 mm span, 12.2 N / 44.5 mm) against the 0.12 acceptance's
   ten closes at 3.68-4.77 N. The P27-B isolation
   (`logs/p27/10_acc_012_flip.log` = 0.12 + the B1c flip, and
   `11_acc_015_noflip.log` = 0.15 without it) has now run: **7/10 and
   5/9**, so the 3/9 needs both changes (section 4.3).
5. **The one existing manipulation of the *pre-arrival park time* moved the
   failure mass into the class the owner wants to fix.** The W7-C ACQ A/B
   (`logs/w7/C_ab/`, patch sheet, `moe_v13s`, N=3x15, interleaved, same
   tree, differing only in the fire lead: 0.90 s vs a median 2.11 s left /
   1.89 s right) moved the left no-contact class **15 -> 0** and the
   close-start offset **120.1 -> 2.5 mm**, but the carried-not-placed class
   **14 -> 32** (left 6 -> 10, right 8 -> 22) and the rate **16/45 -> 12/45**.
   The record's mechanism: the earlier fire makes the primitive *park and
   hold* 0.37-1.40 s before the push, and the right arm's probe re-seats on
   a fruit that has not reached the seat line. **So lengthening the
   pre-arrival park converts acquisition failures into carry escapes.** A
   slower belt lengthens that park only where the fire is *distance*-coded
   (the learned 6 cm gate: 0.50 -> 0.75 s); with the trigger it is a *time*
   and the park is speed-invariant. This is the measured precedent behind
   the S2b arm (section 5.1) and behind section 6.

### 4.3 The isolation and the first speed ladder (P27-B complete; P27-C1 0.08/0.10/0.12/0.15 complete, 1 seed each; read 10:10)

**The acceptance isolation (P27-B), one sample per cell:**

| config | result | per-attempt |
| --- | --- | --- |
| 0.12, no flip (pre-P26 reference) | 9/10 | 15.2 s |
| **0.12 + B1c flip** | **7/10** (`diverted=1`) | 15.1 s |
| **0.15 + B1c flip** (the P26 default) | **3/9** (`diverted=1`) | 15.4 s |
| **0.15, flip off** | **5/9** (`diverted=1`) | 14.7 s |

The 3/9 is **not** the belt alone: the flip alone costs ~2 attempts at 0.12
(9 -> 7) and ~2 at 0.15 (5 -> 3), and the belt alone costs ~1.3 (7/10 ->
5/9). So the P26 3/9 needs *both* changes in this branch - or it is one
draw. One sample per cell cannot separate them further, and the two
"0.15" cells differ by 2/9 with identical speed, so the flip is at least
as loud as the belt on this scenario.

**The direct speed ladder (P27-C1, patch sheet, `moe_v13s`, ACQ=1, seed 77,
15 episodes each; one driver, one tree, one env - only `FRUIT_BELT_SPEED`
differs):**

| belt | result | ok / carried / no-grasp | `grasp_lift` escapes `clean_slip_max` (mm) | belt-fed share of the escape |
| --- | --- | --- | --- | --- |
| **0.08** | **6/15** | 6 / 8 / 1 | n=9, 53-369, **median 270** | 2-26 %, median 6 % |
| **0.10** | **6/15** | 6 / 9 / 0 | n=7, 273-329, **median 298** | 0.3-16 %, median 9 % |
| **0.12** | **2/15** | 2 / 12 / 1 | n=10, 120-426, **median 279** | 6-13 %, median 9 % |
| **0.15** | **5/15** | 5 / 10 / 0 | n=9, 153-385, **median 251** | 4-18 %, median 11 % |
| 0.12 record anchor (W8-A `A_1`, 2026-10-13 tree) | 4/15 | 4 / 10 / 1 | (carry diag off) | - |
| 0.12 record, carry diag (R9 `A_1`, 2026-10-14 tree) | 4/15 | 4 / 8 / 3 | n=5, 194-303, median 260 | 7-18 % |

Readings, in order of confidence:

1. **The 0.12 control is a different branch from the record's anchor, but
   not a resolvably different level.** The p27 manifest and the W8-A `A_1`
   manifest differ in exactly one field: `tasks_md5` (`e98d9836` ->
   `b54b5406`; checkpoint `61da390a`, seed 77, policy seed 11, trigger
   block, camera, `execute_steps=4`, `ddim=16` all identical). 2/15 vs 4/15
   is one draw (Fisher p = 0.65), so the tree moved the branch, not the
   level. Quote the batch's own 0.12, not the record's.
2. **There is no resolved rate effect anywhere in 0.08-0.15.** The ladder
   is 6, 6, 2, 5 of 15: against the batch's 0.12 the pairs are p = 0.215,
   0.215, 0.390; against the record's 4/15 they are p = 0.70, 0.70, 1.00.
   The 0.12 point is the *low draw*, not a trend - both its neighbours are
   higher. A 15-episode point cannot resolve this (its sampling error is
   ±13 pt). **What the data support is the absence of a collapse**: no
   speed in 0.08-0.15 is worse than any other beyond the draw, and the
   failures stay in the same class. A slow-side "gain" must not be quoted.
3. **The mechanism is not the belt-fed slip, and this is now a four-point
   result.** The `grasp_lift` escape magnitudes are **flat across a 2x
   speed range** (median 270 / 298 / 279 / 251 mm at 0.08 / 0.10 / 0.12 /
   0.15), and the belt-fed upper bound is a **median 6-11 %** of the escape
   at every speed. The escape is a hand-frame event 1-2 orders above the
   belt's contribution. The *incidence* (grasp-lift escapes 5 / 2 / 10 /
   9 of 15; carried totals 8 / 9 / 12 / 10) rises toward 0.12 from both
   sides, which is the same draw effect as the rate - not a speed curve.
4. **The trigger's time geometry holds** (F3): at 0.08 the fire notes read
   `dy` 13.7-23.1 cm / `t_arrive` 1.71-2.89 s / `speed=0.080/encoder`; at
   0.10 `dy` 16.6-27.4 cm / `t_arrive` 1.66-2.74 s; at 0.12 `dy` 18.7-25.0
   cm / `t_arrive` 1.56-2.08 s; at 0.15 the same pattern. `dy` scales with
   `v`, `t_arrive` does not (the residual spread is the ACQ lead's
   jaw->station term).

**The one-sentence read of the batch:** *the direct interface is
speed-flat across 0.08-0.15 within the draw, and the failure it would have
to improve (the hand-frame escape) is unchanged in magnitude at every
speed - so the premise's slow-side expectation is supported only in its
"does not degrade" half, and the "improves" half has neither a rate nor a
mechanism.*

---

## 5. The sweep design (P27-C)

The driver already exists (`logs/p27/run_p27.sh`, running): B = the
acceptance isolation; C1 = direct at 0.08/0.10/0.12/0.15; C2 = two-line at
0.08/0.10. What follows is the design it should be read against, plus the
arms it is missing.

### 5.1 Arms

| arm | interface / env | speeds | N | question it answers | budget |
| --- | --- | --- | --- | --- | --- |
| **S1** | scripted single arm, acceptance env, 20 attempts | 0.08/0.10/0.12/0.15 | 20 each | the shipped *scripted* line's slow-side response; the 0.12 control on the current tree is **7/10** (`logs/p27/10_acc_012_flip.log`, B1c flip on; the pre-P26 9/10 needs `FRUIT_READY_SKIP=0 FRUIT_READY_SKIP_RESYNC=0`) | ~40 min |
| **S2** | direct, `moe_v13s`, patch sheet + grades, `TRIGGER=arrival` + `ACQ=1` + `CARRY_DIAG` | 0.08/0.10/0.12/0.15 | 1 seed x 15 per speed (the running C1, **done**: 6/6/2/5) + 2 more seeds | the owner's interface; **the 0.12 point is the batch's own control** - it read 2/15 against the record's 4/15 (W8-A `A_1`, older tree), so anchor on the batch's 0.12, not the record's; the extra seeds are what the flat ladder still needs | ~80 min |
| **S2b** | S2 with `FRUIT_POLICY_TRIGGER=off` | 0.08/0.12 | 3x15 | the **model**'s own adaptation (the learned close) — a *mechanism* arm: with no trigger the learned gate may never fire (`logs/798`'s no-fire class), and then the answer is the fire/tick statistics, not the rate | ~40 min |
| **S2c** | S2 with `FRUIT_POLICY_TRIGGER_ENCODER=0` | 0.08/0.12 | 1x15 | what the encoder buys over the measured velocity | ~15 min |
| **S3** | two-line patch, real mass, seed 11/5 | 0.08/0.10 (+ 0.12/0.15 from the record) | 2 seeds x 20 | the interval, the starvation, the dwell/park coupling | ~60 min |
| **S4** | `scripts/170_transport_probe.py` | 0.08/0.10/0.12/0.15 | - | the encoder's **validity precondition**: the fruit/belt ratio, spin, stalled ticks | ~10 min |
| **S5** | S2/S3 with the supply cadence *time-normalised* (the scattered line's `FRUIT_SUPPLY_GAP_MIN/MAX` scaled by `v`; the patch sheet only via `FRUIT_SUPPLY_PATCH_DENSITY`, which also raises the abreast probability) | 0.08 and 0.15 | 1 seed | separates the belt from the supply's `1/v` cadence | ~25 min |

Total ~4 h. **Every run needs `FRUIT_BELT_SPEED` in a sidecar** (`env.txt`
next to the log): the rl_env manifest does not record it (section 7).

### 5.2 Endpoints

Primary (per-leg, cheap, resolved at every attempt):

* **E1 the fire** — the `intercept trigger (dy=..., dx=..., t_arrive=...,
  speed=.../encoder, frame=..., finger=..., lead=...)` note
  (`rl_env.py:1583-1591`). The signature to test: `dy` scales with `v`,
  `t_arrive` is constant. A *constant dy* would mean the fire is
  distance-coded (the learned gate) and the encoder is doing nothing.
* **E2 the close** — the `[acq]` line's `close_start=(dx,dy,dz) mm`,
  `setup[premove axis hover wait catchup] s`, `catchup=Nt res=..mm`,
  `contact`, `freeze`, `span`, `Fmax` (`tasks.py:8504-8520`). This is the
  model-vs-trigger discriminator (section 5.5).
* **E3 the carry** — the `[carry]` line's `clean_slip_max`, `in-hand_vmax`,
  `force@onset`, `sep@onset`, `min_contacts`, `loss_row`, `guard`,
  `re-seat`. The speed decomposition: `belt-fed <= v * (loss_row-onset_row)/120`,
  compare with `clean_slip_max`.
* **E4 the catch/descent** — the `[motion] approach/descent` `|v|max`,
  `end=`, the catch-up residual, the wait ticks (the `wait` stage of
  `[acq]`).

Secondary (per batch, quantised — quote the table, not the delta):

* **E5 the supply** — `starved slots`, `idle %`, `queue_peak`,
  `supply_skipped`, `recirculated`, `reached_end`.
* **E6 the throughput** — the attempt span, the inter-placement interval
  (p50/p90), placed/min (`scripts/186_w6_report.py`), the `[cycle]` marks.
* **E7 the rate** — the per-episode `success/grasped/placed` and the class
  split (ok / no-grasp / carried-not-placed / other), per arm and per seed
  (`logs/w7/C_class_split.py` is the read-only re-derivation).

### 5.3 Confounds, and the control for each

| confound | why it matters here | control |
| --- | --- | --- |
| **the supply's time cadence is `1/v`** | at 0.08 the same *metre* gaps arrive 1.5x less often; a rate or interval change may be the feeder, not the belt | **S5** (scale the gaps by `v` to hold the time cadence; on the patch sheet the density knob also changes the pair rate, so S5's clean form runs on the scattered line) |
| the spawn->station travel and the recycle loop | 8.5 s / 17.3 s at 0.08 vs 5.7 / 11.5 at 0.12; the first attempt and the pool inventory shift | fixed seed; report `supply_skipped`/`recirculated`; ignore the first attempt in the per-leg stats |
| **transport validity** | the encoder's whole arithmetic assumes `v_fruit ~ v_belt` (measured 1.01-1.14x at 0.12, `logs/173`) | **S4** at every speed, before the rate runs |
| the intervention itself | the p27 direct arm enables `FRUIT_POLICY_TRIGGER_ACQ=1`, a **default-off** knob (R5 decision 4) — the result is the ACQ interface, not the shipped direct default; on this very patch sheet the W7-C `C_ab` measured ACQ on = 12/45 vs off = 16/45 with the class trade (no-contact 15 -> 1, carried 14 -> 32), so the C1 arm's baseline is the **carry-heavy** branch | name it in every manifest; add an `ACQ=0` 0.12 control (the `C_ab` A arm = 16/45) and never compare a rate across the two branches |
| the physics base | the P12 mass base is the two-line's reference; the single-arm/direct interfaces were never re-measured on it | hold the base per interface (S1/S2 default, S3 real mass) and never pool across them |
| the tree / checkpoint / seed | the manifests pin `tasks.py`, `rl_env.py`, `trigger.py`, the checkpoint md5 — but not the belt | sidecar + the `[stats]` `encoder=` line as the second witness |
| **the outcome is quantised** | each speed is its own attractor (AGENTS section 2) | E1-E4 are the primaries; E7 is reported as a per-episode table with the class split |

### 5.4 Falsifiers

**F1 (the premise's core).** On the same checkpoint, tree and seeds,
`success(0.08) >= success(0.12)` and `success(0.10) >= success(0.12)` on
S2 (direct) **and** S1 (scripted). One-sided; the direction is the
owner's. A drop at 0.08 that is larger than the same-config seed spread
(W8-A: 4,4,4,4,5 / 15) refutes "slower holds".

**F2 (the mechanism of the improvement).** The carried-not-placed class
and the median `clean_slip` fall monotonically with decreasing `v`, **and**
the reduction is explained by the belt-fed share
(`v*(loss_row-onset_row)/120`). If `clean_slip` is flat while the rate
moves, the rate movement is scenario noise.

**F3 (the trigger adapts).** At every speed, `dy/v` at the fire equals the
effective lead (0.9 s, or the ACQ lead) within one tick, and the note's
`speed=` says `encoder`. This should pass by construction; it is the
*proof that the observed adaptation is the trigger's*.

**F4 (the model adapts).** With the trigger **off** (S2b), the learned
close's *time-to-arrival* `dy_close/v` is constant across speeds. If
`dy_close` is constant while `v` changes (i.e. the close is
position-coded), the model is **not** adapting and the line only works
because the trigger/primitive carries it.

**F5 (the encoder's contribution).** `TRIGGER_ENCODER=0` (S2c) changes the
fire's `dy`/`t_arrive` scatter but not the rate -> the encoder is a
cleaner estimator of the same quantity, not an adaptation channel.

**F6 (the supply confound).** On S5 (time-normalised supply), if the
0.08 result moves to the 0.12 value, the speed effect was the feeder's
cadence; if it stays, the belt/contact channel is real.

**F7 (the throughput cost).** The attempt span and the interval are
monotone in `1/v` even when the success is flat. Reported as the
"slower holds on success but costs throughput" outcome.

### 5.5 What a "model adaptation" claim would require

Beyond the trigger's timing, a claim that *the policy* adapts to belt
speed needs all six of these:

1. **An input.** The encoder (or any speed scalar) in the observation —
   today the 25-D proprio and the 8-D goal contain none (section 2).
   Alternatively a visual cue with *variance across speeds in training*; at
   one speed the cue is confounded with position.
2. **The right target variable.** The learned close must be a function of
   *time-to-arrival*, not of distance. The current learned gate is a
   distance test (`finger < 0.030` and `|jaw-fruit|xy < 0.06`), and the
   `[acq]` close-start tip-fruit offset is a few millimetres (the R9 `A_1`
   sample: |offset| 5-11 mm) — i.e. position-coded. A
   distance-coded close fires *earlier in time* at a slower belt, which is
   the opposite of the trigger's constant-time behaviour: the two paths
   adapt in different variables (this is testable with F1/F4).
3. **The capacity.** This one already holds: the chunk is 16 ticks
   (0.133 s) and replans every 4 ticks (0.033 s), against a close window
   of 0.50 s at 0.12 and 0.75 s at 0.08 — 4-6 chunks. The interface can
   represent a speed-adaptive close.
4. **Training coverage at >= 2 speeds on one tree**, with the *same
   weights* evaluated at each speed. The repo has the embryo (`v10` 0.06,
   `v12_015` 0.15) but no such A/B was ever run on one checkpoint; the
   closest is the P2b fine-tune, which was a null.
5. **The measurement** (F4): with the trigger off, the close-start `dy`
   must scale with `v`, and the *bucket* of successes must not move.
   Without this, "the model adapts" is indistinguishable from "the
   primitive underneath retimes itself and the model is a passenger".
6. **A null that separates the primitive**: at 0.12 with the trigger on,
   the direct path already reads 1/45 from the scripted ceiling
   (P2b 71.1 % vs 73.3 %) — so the *primitive* is the ceiling. A claim
   that the *model* adapts must show the model's own contribution moving
   *relative* to that ceiling across speeds, which means the scripted
   arm (S1) must be run at the same speeds as the policy arm (S2).

---

## 6. The strongest reason the owner's expectation could fail

**In one sentence: the belt is not the channel the failure runs through, so a
slow-side gain cannot be the encoder's adaptation — and where the fire is
distance-coded, slowing the belt actively lengthens the park that the record
shows converts acquisition failures into carry escapes.**

**The escape is not belt-fed.** Take the two measured facts together:

* the direct interface's dominant failure is carried-not-placed (W7-C:
  32 of 33 failures; W8-A: 49 of 54 failures at N=5);
* that escape is a *hand-frame* displacement of **17.9-957 mm (median
  278 mm)** reached within **~25 ticks (0.21 s)** of the 2 mm crossing
  (W8-B), i.e. a median hand-frame slip rate of **~1.3 m/s** — eleven
  times the 0.12 belt;
* the belt can only add `v * 0.21 s` to that displacement: **24 mm at
  0.12, 17 mm at 0.08**. That is **<= 10 % of the median escape**, and the
  belt-fed share is an *upper bound* (the payload is belt-matched during
  the close and the takeoff's `match_s`, so the belt's relative
  contribution is only the part where the grip has already failed).
* **the slow points now measure it** (section 4.3): the `grasp_lift`
  escapes read **262-369 mm (median 270) at 0.08** against **194-303 mm
  (median 260) at 0.12**, with the belt-fed bound at 4-18 % in both - the
  escape did not shrink when the belt was slowed by a third.

Halving the belt speed therefore removes at most a few millimetres from a
278 mm escape, and the 0.08/0.10 points measure exactly that (the escapes
are 270 mm median at 0.08 and 295 mm at 0.10, not smaller; n = 5 and 3). The escape's driver is the *arm/pad*
relative motion and the geometry — a drive-saturated pinch whose command
sits 11.9 mm inside the payload's measured span (R6-B) — and that is
invariant to `v`. This is why every grip-side lever aimed at this class has
been a measured null (the W8-B guard, the R6-B relief/retune, the R8-A
geometry).

**What the ladder changes about the verdict, precisely:** the rate is
6/6/2/5 of 15 across 0.08-0.15 with no pairwise p below 0.215, so **the
interface neither degrades nor improves in a resolved way**, and the *escape
mechanism* (the magnitude) is flat across the same 2x speed range with a
6-11 % belt-fed share. So the honest statement is **"the direct line is
speed-flat within the draw, and any movement is the contact/impulse
incidence, not the encoder's belt-fed slip"**; the sweep's E2/E3/E7 plus the
extra seeds are what would separate those. The premise's *mechanism* claim
("the model adapts") remains unsupported in every reading: no speed input,
no time-coded close, and the trigger/primitive own the timing.

Two corollaries:

* **The "improves" half is not attributable to the model or the encoder.**
  There is no resolved rate gain to keep (6/6/2/5, all p >= 0.215); if one
  exists it can only sit on the *contact* channel (the escape magnitudes are
  unchanged at every speed), i.e. the primitive's close/pluck softening -
  not the model adapting and not the trigger's arithmetic. A claim that the
  *system adapts* is not what this measures.
* **Where the fire is distance-coded, slower can *lose*.** The one
  *measured* manipulation of the pre-arrival park (section 4.2 item 5: the
  ACQ A/B, 0.9 -> 2.1 s) moved the carried class **14 -> 32** and the
  no-contact class **15 -> 0**. Slower lengthens that park by 1.5x in the
  learned-gate path (6 cm: 0.50 -> 0.75 s), i.e. the same direction, so the
  S2b arm is the test of whether the slow side trades acquisition for
  carry there.
* **The slow side's unambiguous cost is throughput, not success**: the
  hover wait per attempt is predicted to grow by ~1.1 s (the R3
  descent-block slope, extrapolated), the arrival cadence and the recycle
  loop stretch by 1.5x,
  and the collector's per-episode wall clock grows. A report that quotes
  "slower holds" must quote the placed/min and the interval with it, or it
  is quoting half of the result.

If the owner's expectation is instead read as **"the line must not
collapse at a different constant belt speed"**, then the record already
supports it on the two interfaces with mechanism data (0.12 -> 0.15 is
flat), the 0.18 collapse is a *floor* artefact that does not apply at the
slow end, and the open question is only the 0.08 contact behaviour. That is
a weaker and much more defensible claim than "the model adapts".

---

## 7. Provenance gaps found while auditing

1. **`encoder_speed` is a setpoint echo in the shipped build** (cleats
   off). The name and the docstring promise a measurement; the code path
   does not deliver one. Fix before any hardware claim: read the encoder
   from the drive (`belt.speed` is the applied value) or from the cleat
   phase with the cleats on, and *do not* silently fall back to
   `cfg.belt_speed` (`tasks.py:4371-4377`) — a fallback that hides exactly
   the case the owner wants to detect.
2. **No run manifest records the belt speed.** `rl_env.py:927-935` stores
   `handoff_mode`, `no_attach`, `no_sleep`, `policy_seed` — not
   `FRUIT_BELT_SPEED`, though the trigger block is stored. The collection
   manifests (`datasets/*/manifest.json`) record `collection.*` and
   `supply.*` but no belt field either, so **no store in the repo can be
   assigned a belt speed from its own artifact** (only from the collection
   script and, indirectly, the goal `vy`). A speed sweep must add
   `supply.belt_speed` / `scenario.belt_speed` to both, or write a
   sidecar per run.
3. **Three sources of the same quantity** (encoder / `cfg.belt_speed` /
   measured `vy`, section 1.4). They agree by construction today; they
   would diverge the moment the encoder became real.
4. **`assets.py`'s comment says 0.12, its default is 0.15**, and the
   documents still say "shipped 0.12" (AGENTS section 2, README). The
   acceptance's `[stats]` line is currently the only record of which speed
   a given log used.
5. **`enforce_transport` still assumes `transport_efficiency = 0.40`**
   (`fruits.py:1437`) — the value the belt-body fix superseded (the
   measured ratio is 1.01-1.14x). It only fires on a near-stalled fruit,
   so it is a rescue, but at 0.08 it sets a rescued fruit to 0.032 m/s
   while the belt runs at 0.08.
