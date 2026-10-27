# P52 phase 2, lane A — the contact-gated action time-scale (the claimed battery)

Measured **2026-10-27/28** on branch `p-supply`, work tree at `da0c914` (the code
and this file were then committed by the orchestrator as `aae9377` / `8862fec` /
`b4a7899`; the §3.1b correction below is a **post-commit working-tree edit** and
is not in those commits). Claimed battery `logs/p52/p2/` (~45 min of episode
wall, one claim, 90 episodes).

**The four sentences this phase exists to support.**

1. **The lever runs, and its whole design is worth less than 5 %.** The
   pre-registered **P1 fails**: placed-episode ticks 1800 → 1748 median
   (**−2.9 %**, bar −8 %); the same statistic on the two runs taken entirely on
   one tree reads **−5.0 %** (§3.1c). The paired per-episode read is
   **−48.1 ticks** (−2.7 %, n = 23, 17/23 negative). **The effect cannot be
   attributed to the arm** (§3.1b: the arms' initial conditions are not
   matched), and it does not need to be — the **ceiling** of sentence 2 is what
   decides the lane.
2. **That is not an implementation null — it is the arithmetic.** A 1.5x
   re-timing can only shorten the **policy phase**, which is measured at
   **14.2 %** of a placed episode (256 of 1800 ticks); a 1.5x on the *whole*
   phase is therefore worth at most **86 ticks = 4.8 %**, and with the contact
   gate at a **44.1 %** duty the ungated 56 % is worth **48 ticks = 2.7 %**.
   **The 8 % bar was unreachable by construction** — it needs 56 % of the entire
   policy phase removed — and no cell of this knob can reach it.
3. **The gate is expensive and that is the honest cost.** It clamps **44.1 % of
   decisions** (4492 of 10202 ticks; by force 2226, by finger 2744, overlap 478)
   with a peak force of 216.4 N — the direct approach is *in contact* about as
   often as it is in free space. Removing the gate halves the duty and would at
   most lift the gain to the 4.8 % ceiling, still under the bar.
4. **Nothing is adopted.** `FRUIT_POLICY_TIME_SCALE` / `FRUIT_POLICY_RETIME_GATE`
   stay **default off**; the direct interface's episode time is 85 % scripted
   primitive, which no policy-side execution lever can touch (AGENTS §2 "P43"
   already said 84 %; this phase measures the split that bounds it).

---

## 1. What was built (default off, unset = the shipped path)

| knob | default | semantics |
| --- | --- | --- |
| `FRUIT_POLICY_TIME_SCALE=<s>` | **unset = 1.0** | execute the active chunk's waypoints at rate `s`: on control tick `index` the applied action is `lerp(chunk[floor(i)], chunk[floor(i)+1], frac(i))` with **`i = s · index`** (the PREREG's formula), for all 9 channels (7 absolute arm joint targets + the finger channel twice) |
| `FRUIT_POLICY_RETIME_GATE=1` | **off** | the contact gate: with the hand **in contact** the effective scale is clamped to **1.0** (the demonstrated rate), otherwise it is `s` |
| `FRUIT_POLICY_RETIME_FORCE` | 1.0 N | the gate's force threshold (strict `>`) |
| `FRUIT_POLICY_RETIME_OPEN` | 0.020 m | the gate's finger threshold (strict `<`; see §1.2) |

Pure helpers in `src/fruit_sorting/rl_env.py`: `resolve_time_scale` (**only
`s ≥ 1`**; a slow-down, a zero, a non-finite or a non-number is a hard error),
`retime_action`, `retime_contact`. Env sites: the chunk lookup in `act`
(`action = self._retime_step(arr, index)`), the two gate channels cached in
`proprio()`, the per-decision `[retime]` row, the per-episode `[retime] episode`
summary, the manifest's `retime` block, and a `[rl] retime:` banner.

**Where the re-timing lives, and where it does not.** In the **chunk lookup**,
not in `_apply`: the 4-ticks-per-action cadence is untouched, so the model is
still called every 4 ticks on both arms (`decision=` / 4 reproduces the
instrument's own decision count exactly; §3.4), and the **re-plan boundary is
untouched** — chunk k+1's action 0 is applied unchanged, which is the jump a
time-scale cannot scale (census §2.3).
Scope is `presentation == "direct"` and the constructor **raises** otherwise
(`handoff`/canary, scripted, bimanual are all untouched); RTC is refused (it
never hands `act` a chunk, so the knob would silently be a no-op arm).

### 1.1 The `s = 1` byte-identity

`retime_action(chunk, index, 1.0)` returns `chunk[index]` **exactly** — `i` is
the integer `index`, the fraction is 0, and the arithmetic short-circuits before
any float operation touches the values. Pinned by
`scripts/228_p52_retime_selftest.py` (`np.array_equal` over 24 random chunks x 4
indices each, signed zeros and repeated waypoints included; 239 checks total),
which is the *only* valid proof: the direct loop conditions on rendered frames
and is not bit-reproducible (AGENTS §3b), so no run can prove it. **At runtime
the shipped path never even reaches the interpolation** — `act` keeps its
original `action = arr[index]` as the `_retime_on` else-branch (pinned by AST),
`proprio()` skips the cache, and `_finalize` skips the row. The knobs unset also
keep `_apply` byte-for-byte (no retime reference in it, pinned).

### 1.2 The gate's two channels, and why the finger threshold is 2 cm

Both are **already-sampled** env channels (the tactile normal force and the
active arm's finger opening, both read in `proprio()`); the gate adds **no
sensor read** to the control loop — the value a tick uses is the decision's own,
at most 3 ticks old (AGENTS §2: per-tick work inside the loop is what shifts a
run).

The task's parenthetical — "an open finger = not holding" — is correct but the
**channel cannot separate holding from open on this interface**, and that is a
measured fact: the pool's diameters are 2.8-7.0 cm and the finger channel's
ceiling is 4.4 cm, so a *loaded* finger reads 2.5-4.4 cm. The measured
distribution over the 2567 decisions of the treatment arm reads
**p10 8.3 / p50 24.7 / p90 42.9 mm** — the policy's ordinary approach posture
sits *below* any fruit's width. A threshold at the trigger's own
`finger < 0.030` close test therefore gates on the approach posture, not on
contact (measured: 14 % of decisions). The default is **0.020 m — below every
class's diameter** — so the criterion fires only on a **collapsed** finger, the
one state the channel does identify; it is a *fallback*, and the **force is the
primary signal**. Both thresholds are reported, and §3.4 gives the duty-cycle
split, so a reader can re-price the gate.

---

## 2. The battery (the P43 protocol, verbatim)

| item | value |
| --- | --- |
| tree | `da0c914` + this change; `rl_env.py` `29297e0c`, `tasks.py` `b6de439c`, `control.py` `9384ff4f`, `scene.py` `27e3d64a`; `configs/` **untouched** (`8a399626` / `2246f83c`) |
| checkpoint | `checkpoints/moe_v13s/policy_best.pt` `61da390a` on **both** arms |
| scenario | `FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1`, `FRUIT_POLICY_SEED=11`, park unset on both arms (the direct presentation's resolved default `back`, verified in the manifests) |
| instruments | `FRUIT_ACQ_DIAG` / `FRUIT_CARRY_DIAG` / `FRUIT_PARK_DIAG` / `FRUIT_RESET_ALIGN_DIAG` on **both** arms (the P43 set; AGENTS §3b) |
| arms | **T0** = both knobs unset · **TG** = `FRUIT_POLICY_TIME_SCALE=1.5 FRUIT_POLICY_RETIME_GATE=1` |
| N | **3 runs × 15 episodes per arm**, seeds 77/101/202, interleaved T0-then-TG per seed pair, one claim |
| cost | batch wall **2683 s = 44.7 min**; 90 episodes |
| provenance | `P2A_header.txt` / `P2A_tree_md5_after.txt`; manifests `logs/p52/p2/raw/{A,B}_*/` — T0 reads `"retime": null`, TG reads `{"scale": 1.5, "gate": true, "force_n": 1.0, "open_m": 0.02}` |

---

## 3. The endpoints

### 3.1 P1 — the speed: **FAIL**

Placed-episode `ticks=` (sim time, the census §3 metric), the pre-registered
statistic:

| arm | n | median | mean | sd | min / max |
| --- | --- | --- | --- | --- | --- |
| T0 | 32 | **1800** | 1809.8 | 74.3 | 1642 / 1935 |
| TG | 28 | **1748** | 1758.9 | 76.6 | 1640 / 1937 |

**median −2.9 %, mean −2.8 %**, bar **−8 %** → **FAIL**. Per-seed paired medians
(same seed = the same spawn set): seed 77 **+14** ticks, seed 101 **−110**,
seed 202 **−48** — 2 of 3 negative, and one *positive*.

The **per-episode paired** read (same run + index, **placed in both arms**,
n = 23, of which 10 keep the same species and diameter):

| object | mean | median | sd / sem | negative |
| --- | --- | --- | --- | --- |
| **ticks (total)** | **−48.1** | −36 | 89.2 / 18.6 | **17/23** |
| policy phase (`decision=`) | −28.0 | −3 | 93.4 / 19.5 | 13/23 |
| scripted phase | −20.1 | −11 | 72.7 / 15.2 | 14/23 |

The 10 same-fruit pairs read −1.1 ticks (sd 36.4) — **no power at that n**, and
not quoted as a result either way.

### 3.1b The arms are not matched on the initial condition (measured)

The two arms' **target fruit does not start at the same place on the belt**, and
this is a *downstream* quantity, not a controlled one: the spawner runs an
absolute release/pump schedule, so where the next fruit sits when an episode
resets depends on how long the previous episode ran. Measured from the
`FRUIT_RESET_ALIGN_DIAG` rows (`[align] episode N ... reset=<along>`):

| quantity | value |
| --- | --- |
| `reset` along, T0 | p50 **0.510 m**, mean 0.505 m |
| `reset` along, TG | p50 **0.499 m**, mean 0.484 m |
| paired difference, all 45 same-run+index pairs | **mean −21.0 mm**, p50 −4.0 mm |
| paired difference, the 12 pairs on the clean-tree runs | **mean −46.1 mm** |
| in belt ticks at 0.120 m/s | 21 / 46 ticks |
| paired difference at episode 0 of each run (identical starting state) | **0.0 mm** (3/3) |

So the treatment arm's fruit starts **closer** — and the gap is *larger* on the
subset where the effect is *larger* (−46.1 mm at −76.2 ticks). That is the
signature of a **feedback**, not of a bias: a shorter episode leaves the line
further advanced, so the next fruit starts nearer, so the next episode is shorter
again. **The initial condition is part of the system under test**, and a
per-episode tick comparison cannot separate "the arm moved faster" from "the line
presented the fruit sooner".

**Consequence, stated as a limit rather than a correction.** The arm's own
contribution is **not resolved** by this battery: it is bounded above by the
whole difference (−2.9 % registered, −5.0 % clean-tree) and below by ~0. What
decides the lane is therefore not the point estimate but the **ceiling** of §3.5,
which is independent of the pairing: **a 1.5x on the entire policy phase is worth
at most 4.8 % of the episode, so the 8 % bar cannot be met by any cell of this
knob** — and the measured −5.0 % clean-tree read sits right at that ceiling.

### 3.1c Provenance: one of the six runs started on an earlier `rl_env.py`

The per-run manifests (`logs/p52/p2/raw/*/`) record every source md5, and they
split:

| run | started | `rl_env.py` |
| --- | --- | --- |
| **A_1** | 23:23:22 | **`db4cd585`** |
| A_2, A_3, B_1, B_2, B_3 | 23:31 - 00:00 | `29297e0c` (the committed file) |

The change between them is a **comment** I edited after launching the batch (the
manifest's `retime` block's "absent = off" → "null = off"), i.e. no code. It is
not reconstructible from the working tree, so it is reported rather than
asserted away — and it does not matter for the control arm: **A_1 is a T0 run,
where `_retime_on` is `False` on every tick**, so the whole retime block
(comment included) is never entered, and the shipped `action = arr[index]`
statement is what executed. The registered P1 statistic is reported with all
three runs; **§3.1's −5.0 % is the same statistic on the five clean-tree runs'
two pairs**, which is the sensitivity to that one run.

### 3.2 P2 — the placements: **PASS** (with its power stated)

| arm | right placed | left placed | pooled |
| --- | --- | --- | --- |
| T0 | **30/31 = 96.8 %** | 2/14 = 14.3 % | 32/45 = 71 % |
| TG | **28/29 = 96.6 %** | 0/16 = 0.0 % | 28/45 = 62 % |

Right-arm delta **−0.002**, bar **≥ −0.10** → **PASS**. Per-run right counts:
T0 `12/12, 10/11, 8/8`; TG `12/12, 7/8, 9/9`; run level TG better 0 / worse 1
(exact sign p = 1.000). The one-sided 95 % **Newcombe lower bound is −0.142**,
i.e. the interval does **not** resolve ±0.10 at n = 29-31 right-arm episodes
per arm — the PREREG §4 power statement, measured; the bar is met on the
point statistic it was written against, and the interval is reported so no
reader mistakes it for a demonstrated equivalence.

The right arm's **class split is identical between the arms**: `placed 30,
cnp 0, no-grasp 1` (T0) vs `placed 28, cnp 0, no-grasp 1` (TG). The whole pooled
32 → 28 difference is the **left** arm's 2 vs 0 placed (14.3 % → 0 %, n = 14/16,
the closed `cnp` class — `logs/p42/SIM_LIMIT.md`); it is a draw on a 15 %-base
arm, not a lever effect, and it is not a rate.

### 3.3 P3 — the failure reasons: **PASS**

Per-arm class table (all failures):

| arm | side | n | placed | cnp | no-grasp |
| --- | --- | --- | --- | --- | --- |
| T0 | left | 14 | 2 | 12 | 0 |
| T0 | right | 31 | 30 | 0 | 1 |
| TG | left | 16 | 0 | 15 | 1 |
| TG | right | 29 | 28 | 0 | 1 |

**No new reason.** Both arms carry exactly the same two note families: the
`intercept trigger (...)` note (an attribution note, present on every episode
including the successes) and `fruit did not follow the gripper` (T0 1, TG 2 —
the pre-contact acquisition class, present in the control). `scripts/113_rl_report.py`
independently agrees: `failure reasons A` and `B` are the same set
(`P2A_113.txt`). The left's `cnp` count moves 12 → 15 on a 14 → 16 denominator;
`cnp` is the closed loaded-slide class and is not a new reason.

### 3.4 P4 — the wall and the gate's duty cycle (reports, not gates)

| report | T0 | TG |
| --- | --- | --- |
| app wall / episode | 28.8 s | **27.8 s** (−3.5 %) |
| gate: decisions clamped | — | **1131/2567 = 44.1 %** |
| gate: ticks clamped | — | **4492/10202 = 44.0 %** |
| gate ticks by force / by finger | — | 2226 / 2744 (overlap 478; finger-only 2266, force-only 1748) |
| peak tactile force seen | — | 216.4 N |
| decisions per placed episode (F4) | 63.5 (`decision/4`) | 58.2 |
| cadence (ticks per action) | 4 | **4** (untouched) |

**F4 restated honestly:** the *cadence* does not move — 4 control ticks per
action on both arms, so the model is still asked once per 4 ticks (max 84 model
calls per episode on either arm; the PREREG's "it must not move" is about the
cadence). The *count* **does** fall (63.5 → 58.2) because it is
`policy_phase_ticks / 4` and the phase is shorter — a consequence, not an
implementation error. The nearest-tick cross-check is exact: `decision=303` with
`[retime] decisions=75` = 75 complete + 1 partial, on both arms.

The wall follows the ticks (the loop is primitive-bound, P43 L2); a −3.5 % wall
for a −2.9 % sim-time change is the same measurement twice, not a second gain.

**The gate is not a rare event.** 44 % of decisions are in contact, and the
force channel alone accounts for 21.8 % of decisions. This is the direct path's
documented geometry (the hand rides inside the belt; AGENTS §2 "the descent is
blocked by the conveyor"), not a gate mis-calibration — the RoboPace *premise*
(mostly free space, slow only at contact) does not hold on this interface.

### 3.5 The mechanism — where the time actually is (the phase's main finding)

`ticks = decision + (ticks − decision)` — the policy phase and the scripted
primitive. Over **placed** episodes:

| corpus | n | policy phase | scripted | policy share |
| --- | --- | --- | --- | --- |
| P43 park A/B (`moe_v13s`) | 86 | 266 ticks (2.22 s) | 1514 (12.61 s) | **15 %** |
| P35 park A/B (`moe_v13s`) | 73 | 252 (2.10 s) | 1517 (12.64 s) | **14 %** |
| this batch | 60 | 256/228 | 1552/1529 | **14 %** |

**`logs/p52/MODEL_CENSUS.md` §1.4 reports a 54-57 % policy phase and 6.4-6.8 s
of "arm motion" per episode, and its 11-12 % prediction is built on that. It
does not reproduce.** `decision=` is a **tick index** (set at
`rl_env.py::_run_primitive`: `self._decision_step = self._step`), not a count of
4-tick decisions; it is 250-270 ticks on every corpus, i.e. **smaller than the
census's own 2.08-2.23 s belt floor**. The policy phase *is* the belt
rendezvous, and the `[acq]` row says the same thing from the other side: of a
~2.2 s phase, `premove + axis + hover` ≈ 1.9 s of wall and `wait` ≈ 1.6 s — the
arm finishes its approach and **waits for the fruit**.

**The arithmetic that closes the lane, all terms measured:**

```
policy phase                     256 ticks of 1800 = 14.2 % of the episode
a 1.5x on the WHOLE phase        -86 ticks  = 4.8 %   <- the ceiling
with the gate at 44.1 % duty     -48 ticks  = 2.7 %   <- the envelope
registered (n=3)                 -2.9 %   median placed ticks  }
clean-tree (runs 2-3)            -5.0 %                         } both inside the
paired (n=23)                    -48.1 ticks                    } ceiling, none
pre-registered bar               -144 ticks = 8.0 %   <- unreachable by construction
```

**Do not quote the −48 / −48 coincidence as a validation.** The two numbers are
the same size, but the initial condition is not matched between the arms (§3.1b),
so the pairing cannot attribute the difference to the arm. **The ceiling is the
claim, not the match.**

The lever sits **inside its envelope and the envelope is the problem**: the whole
policy phase is 14 % of the episode, so **no time-scale can reach an 8 %
episode-time bar on this interface** (the bar needs 56 % of the entire policy
phase removed; a 1.5x can remove at most a third of it, and the gate lets only
56 % of the ticks move). A 2x on the whole phase would be 128 ticks = 7.1 %, and
2x is already a different regime (the census's joint-velocity exceedance goes
0.0 % → 0.13 %). The named ceiling for this lane is therefore **~4.8 % at 1.5x
ungated (7.1 % at 2x)**, against the census's 11-12 %.

The clean-tree read (−5.0 % = −90 ticks) is **above** the geometric envelope
(−48 ticks) — which is the pairing confound of §3.1b showing itself, not a
mechanism: the treatment arm's episodes are shorter *and* its fruit starts
nearer, and the two feed each other. So the honest reading of the mechanism is
the negative one: **nothing here separates "the servo tracks the re-timed path"
from "the line presented the fruit sooner", and the ceiling says the separation
would not change the verdict.** The census's §2.4 note ("the drive is a 0.2 s
first-order lag at a saturated torque, so a jump is filtered into a ramp and a
ramp is tracked") remains untested *inside* the policy phase.

The 44 % duty cycle is the *only* thing the gate costs (4.8 → 2.7 % envelope),
and the gate is what keeps the contact legs at the demonstrated rate — the half
of the RoboPace ladder this tree can test (`logs/p52/FRONTIER.md` §2.1:
contact-gated 32/50 vs uniform-1.67x 4/50 vs RACE-style 1/50). **On this
interface the contact-gated cell and the ungated cell differ by at most 4.8 % vs
2.7 % of episode time and by 0.002 of right-arm placement** — the contact cost
the frontier measures on a 50-trial contact-rich assembly is not visible here at
this n.

---

## 4. Verdicts, and what is not claimed

| # | endpoint | bar | measured | verdict |
| --- | --- | --- | --- | --- |
| **P1** | placed-episode ticks | TG ≥ 8 % below T0 | **−2.9 %** median (−2.8 % mean; −2.7 % paired; **−5.0 %** on the clean-tree pair); the ceiling is 4.8 % | **FAIL** |
| **P2** | right-arm placed | ≥ −0.10 | **−0.002** (Newcombe lower −0.142) | **PASS** (point; interval unresolved) |
| **P3** | failure reasons | none new | none new (same two families) | **PASS** |
| **P4** | wall / motion | report | wall −3.5 %; duty 44.1 %; 216.4 N peak | reported |

**Adoption: no.** Both knobs stay **default off**; no `configs/` change, no
commit, no shipped default moved. The lane's stop rule
(`.slim/deepwork/p52-model-lane.md` §4) is satisfied by measurement, and its
F1 falsifier fired: **the re-timing buys 2.7 % of an episode, so the lane closes
with that number** — not because the implementation failed, but because the
policy phase is 14 % of the episode and the arm-side ceiling is 4.8 %.

**What is not claimed.**

* **No rate.** Every count is one attractor: the pooled 32/45 vs 28/45 is the
  left arm's draw on the closed `cnp` class, and the two arms are two different
  command streams by construction.
* **No "the arithmetic reproduces to the tick" claim.** The paired total (−48.1)
  coincides with the envelope (−48), but the arms are not matched on their
  starting state (§3.1b), so the coincidence is not a validation. Quote the
  **bound** (≤ 4.8 %), not the match.
* **No attribution of the saved ticks.** Whether the arm moved faster or the line
  presented the fruit sooner is **not separated** by this battery, and the
  feedback in §3.1b makes the two observationally entangled. A separating design
  would need a fixed initial condition (a controlled reset) or a policy-phase
  TCP-speed trace.
* **No claim that 1.5x is the best cell.** 1.25 and 2.0 were registered in the
  PREREG but this lane ran the contact-gated cell only (the task's scope). The
  arithmetic says the same bound holds for all of them (2.0 → 4.8 % ungated),
  so the cell choice cannot change the verdict.
* **The ungated cell is not measured here.** The 4.8 % figure is arithmetic
  from the measured phase share and the measured duty cycle, not an arm.
* **The policy phase's internal achieved speed was not traced.** A
  `FRUIT_RTC_REPORT` run or a TCP-speed read inside the policy phase would
  settle the 56 % figure; it cannot change the ceiling.
* **The canary was not run.** `60_eval_policy.py` never constructs
  `SortingRLEnv`, and the knob *raises* on `presentation != "direct"`, so the
  hybrid canary cannot read it; and its policy window is a fixed
  `APPROACH_STEPS = 400` ticks, so it cannot carry a speed claim at all
  (census §4).

## 5. Files

| artefact | what |
| --- | --- |
| `src/fruit_sorting/rl_env.py` | `resolve_time_scale` / `retime_action` / `retime_contact`, the knob block, the `act` chunk lookup, the `proprio` cache, `_retime_step` / `_retime_row`, the manifest block, the banner. `29297e0c` |
| `scripts/228_p52_retime_selftest.py` | the offline pin (239 checks): the `s=1` exact identity, the rate, the terminal hold, the finger channels, the gate truth table, the resolver, and the env wiring by AST |
| `scripts/selfcheck.sh` | the `P52 retime scale` leg |
| `logs/p52/p2/run_batch.sh` | the battery driver (the P43 template, 2 arms, 3×15, interleaved) |
| `logs/p52/p2/p2a_report.py` → `P2A_report.txt` | P1-P5 |
| `logs/p52/p2/p2a_mechanism.py` → `P2A_mechanism.txt` | the paired phase split and the arithmetic bound |
| `logs/p52/p2/policy_share.py` → `policy_share_out.txt` | the census §1.4 correction, over three corpora |
| `logs/p52/p2/P2A_113.txt` | the `113_rl_report.py` cross-check (its own criterion: no improvement, as expected) |
| `logs/p52/p2/P2A_header.txt` / `P2A_tree_md5_after.txt` / `raw/` | provenance |
| `logs/p52/p2/smoke/` | the two implementation smokes + the T0 counterpart (kept, not part of the battery) |
| `logs/p52/p2/P2A_accept_noharm.log` | the scripted acceptance (see the framing below) |

**The no-harm framing, stated honestly.** The scripted acceptance never imports
`rl_env`, so its result is an *import guard* on this change (the P38-M4 / P43
pattern) — the real no-harm evidence is (a) the offline `s = 1` exact identity,
(b) the `selfcheck.sh` PASS including the `rl_env` import and the `TASKS_MD5` pin,
and (c) the T0 arm of this batch, which *is* the unset path driven for 45 live
episodes. It was run anyway (`SKIP_SELFCHECK=1 scripts/accept.sh`,
`logs/p52/p2/P2A_accept_noharm.log`): **6/10, `fingerprint: matches
configs/motion_reference.json`** — the shipped P32/P40/P41 branch (AGENTS §1
records the shipped 6/10), with the FAIL rate-only and expected. `configs/*` is
byte-untouched (`8a399626` / `2246f83c`, `P2A_tree_md5_after.txt`).
