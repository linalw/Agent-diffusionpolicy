# P10-D.1 implementation record: the GDP OoD-scored population selection (default off)

Lane: implementation only - offline, **no simulator run**, no retraining, no shipped default
changed. The A/B battery is a separate lane and runs from `logs/p10d1/PREREG_GDP_AB.md`
(frozen at `93e0bb4`). Branch `p-supply`; this lane's base tree `93e0bb4`. Written 2026-10-17.

## 1. The mechanism and the paper's exact OoD score

Source: `docs/papers/MECHANISMS.md` item #5 (line 36) - "K in {2,3} DDIM-16 samples from
different noise (~12 ms each, fits the tick), take the min OoD score (or min inside a
plausibility band); log per-candidate finger spread". Paper: **#32, "Two-Step Diffusion
Policy for Robotic Manipulation via Genetic Denoising"** (NeurIPS 2025), extract
`Paper/fulltext_ca/20260928__NeurIPS-2025-two-steps-diffusion-policy-for-robotic-manipulation-via-genetic-denoising-Paper-Conference.txt`.

**The formula (readable; no fallback needed).** Eq. (4), extract lines 331-335:

```
phi_stein,f,T(x_t, t) = T * f(|| eps_theta(x_t, t) ||)
phi_clip,f,T (x_t, t) = T * f(x_hat_0 - CLIP(x_hat_0)),   x_hat_0 = (x_t - sqrt(1-a_t) eps_theta(x_t,t)) / sqrt(a_t)
```

where "T is a temperature factor, f is a scaling function". Algorithm 1 (lines 297-324)
computes the score at every denoising step and selects survivors with a multinomial
sampler weighted by the fitness, duplicating survivors to fill the population (lines
326-330; populations 4-32, temperature 1-1000). The paper's own ranking of the simple
heuristics is explicit (appendix, line 1091): **"minimizing the stein score (or the norm
of the estimated noise) is the best of simple genetic algorithm heuristics"** - the clip
family "distorts the sampled distribution by removing the mode with large values".

**What this implementation ports (the simplest faithful version).** T = 1, f = identity,
Stein family: the per-candidate score is the **mean over the 16 denoising steps of
||eps_theta(x_t, t)||** (each step's norm evaluated before its update, exactly where
Algorithm 1 evaluates it), and the **minimum-score candidate is executed**. The
per-step multinomial survivor machinery is not ported: it is the population-generation
half (needed when the whole population must keep sampling); for one chunk per candidate
the min-OoD rule is the faithful reduction of "minimizing the stein score". The
**plausibility-band variant is not implemented** - the paper's exact score is readable and
its appendix names min-Stein best; a band would need a calibrated plausibility threshold
that does not exist offline, and the frozen prereg's arm B pins the min form. The
per-candidate finger-command spread is logged (the mission's requirement; a diagnostic,
not a selection input).

**The P6 adversarial re-read's take (quoted, `logs/p6/B2_reread.md` section 12).**
"Previous verdict: NO-GO (latency class). Reread verdict: PARTIALLY REFUTED. The latency
dismissal is still right, but the *quality mechanism* was missed ... (iv) GDP fitness =
noise-estimator norm or clip residual, multinomial survivor selection ... (vii) their own
limitation: on Robomimic, improving denoising buys little because the bottleneck is
*conditioning* of the noise model - a sentence that could have been written about our
state-conditioned policy." The corrections table (`MECHANISMS.md` line 131) records the
same: "partially refuted: the quality mechanism (OoD population selection) was missed;
the schedule-start half is already fixed in-repo". The re-read's own falsifier (lines
356-359) is the battery's real risk: "log that the candidate spread is dominated by
observation-frame noise rather than initial noise, or that the OoD score is uncorrelated
with episode outcome on replay - then the mechanism is inert".

## 2. The implementation (`src/fruit_sorting/policy/runtime.py` only)

Default-off, byte-inert, inference-time only. One file changed: **215 insertions, 8
deletions**; the only deleted lines are the shipped `ddim_sample` call (7 lines),
re-indented verbatim into the `else` branch of the new gate.

* **`GDPSettings`** (env resolution, `from_env`): `FRUIT_POLICY_GDP` (default 0),
  `FRUIT_POLICY_GDP_K` (default 2, clamped to **1..4** - `GDP_K_MIN/GDP_K_MAX`),
  `FRUIT_POLICY_GDP_DIAG` (default 0). Read once in `PolicyRunner.__init__` (the
  `FRUIT_POLICY_SEED` convention). A class-level `gdp = GDPSettings()` default keeps
  checkpoint-free `__new__`-built runners (`scripts/128_rtc_selftest.py`) resolving
  disabled - that fixture calls `runner.act()` through the RTC chunker and selfcheck
  caught the missing attribute; the class default is the fix that keeps it byte-inert.
* **`ddim_sample_scored`**: a mirror of `DiffusionSchedule.ddim_sample` for eta=0 (same
  noise draw, same update order - pinned bit-identical by the stub) that additionally
  accumulates the per-step Stein norms on-device and syncs once. Decorated
  `@torch.no_grad()` like the shipped sampler; the first measurement run without the
  decorator read +2.5 ms/candidate of pure autograd-graph overhead.
* **`select_gdp_candidate`**: `min(range(len(scores)), key=...)` - the minimum score
  wins, ties to the first candidate.
* **`_gdp_sample`** (called from `act` when `enabled and k > 1`): K candidates drawn
  **sequentially from the runner's noise source** - the `FRUIT_POLICY_SEED` generator
  when set (the battery's `AB_POLICY_SEED=11`), else fresh noise. Candidate 0 of the
  first call uses exactly the shipped path's noise draw; the K draws per call replace the
  shipped 1 draw per call. Selection score = mean of the per-step norms.
* **`[gdp]` diag row** (`FRUIT_POLICY_GDP_DIAG=1`, default off; timing calls exist only
  under diag):
  `[gdp] k=2 chosen=1 scores=30.6922,27.3367 fingers=0.0312,0.0311 cost_ms=42.5,26.5`
  (`fingers` = range of the finger-opening channel 7 over each candidate chunk; `cost_ms`
  = wall cost per candidate).
* **Scope**: the synchronous `act` path only. The interleaved RTC sampler
  (`FRUIT_RTC`/`FRUIT_VLASH`) draws its own noise and is not GDP-scored (pinned by an AST
  check in the stub). With RTC on, only the first chunk of an episode (sampled via `act`)
  would be GDP-selected - documented in the module docstring; the battery runs the
  shipped synchronous path (`FRUIT_RTC` unset).

**Byte-inertness (prereg kill 1) is proven, not assumed**: with the knob off (or K=1)
`act()` equals the pre-P10-D1 path - the same single draw from `self.generator`, the same
`ddim_sample` call, bitwise-equal chunks and identical generator states, both on the fake
model (stub) and on the real `moe_v13s` checkpoint in fp16/CUDA
(`logs/p10d1/20_real_inert.txt`).

## 3. The wall cost (offline, checkpoint-only; no simulator)

`logs/p10d1/measure_gdp_cost.py` -> `logs/p10d1/10_wall_cost.txt`. Real checkpoint
`checkpoints/moe_v13s/policy_best.pt`, fp16, RTX 5090 (no simulator or other GPU work at
measurement time; nvidia-smi 5-8 % before, ~39-43 % during - the sampler's own load).
30 timed iterations after 3 warmups, CUDA-synchronized:

| quantity | median (final run) | repeat (earlier run) |
| --- | --- | --- |
| shipped `ddim_sample`, one DDIM-16 chain | **26.55 ms** | 24.79 ms |
| GDP `ddim_sample_scored` (chain + scores) | 26.06 ms | 24.41 ms |
| `act()` GDP off (K=1, condition build + chain) | 27.04 ms | 25.34 ms |
| `act()` GDP on K=2 (2 chains + selection) | **52.87 ms** | 49.65 ms |
| K=2 / K=1 act | 1.96x | 1.96x |

**Against the claims, honestly:**

* **The menu's "~12 ms/candidate" is 2.1-2.2x optimistic for DDIM-16 on this checkpoint.**
  The measured per-candidate cost is 24.8-26.6 ms across repeats, matching the repo's own
  recorded DDIM-16 baseline (23.69 ms/chunk, WORKLOG benchmark ladder; ~26 ms in the
  v5-C entry). The 12 ms-class numbers are DDIM-8/torch.compile-8 (11.96/11.87 ms) and
  belong to the "~12 ms/chunk" claim in `docs/research_dynamic_grasp_methods.md`, which
  the menu carried forward as per-candidate.
* **Against the 1/120 s tick (8.33 ms): one candidate is ~3.0-3.2x OVER the tick.**
* **Against the real re-plan window** (`EXECUTE_STEPS=4` control steps = 33.3 ms):
  K=1 fits (25-27 ms), **K=2 does not** - 49.7-52.9 ms = **1.5-1.6x OVER**.
* The **scoring bookkeeping itself is free at this scale** (-0.4 to -0.5 ms within noise
  once under `no_grad`); the cost is the second 16-step forward chain (1.96x).
* The **simulator loop is stepped, not wall-clocked**: the cost does not change the
  simulated-time cycle (the prereg's kill 3 is a sim-clock check); it shows up as wall
  time - roughly +25 ms per re-plan, ~+12-15 s wall per direct episode at ~450-600
  re-plans/episode, i.e. ~2x the policy-sampling wall on arm B.

## 4. Verification (offline only)

* `python3 -m py_compile` on `runtime.py` + all three `logs/p10d1/*.py`: OK.
* **`scripts/selfcheck.sh`: PASS, 0 failures, 1 skipped** (motion budgets, no run log
  given) - `logs/selfcheck.log`. The RTC leg initially failed on the missing instance
  attribute (fixed by the class default, section 2); every other leg PASS.
* **`logs/p10d1/check_gdp_stub.py`: STUB PASS, 40 checks** (`logs/p10d1/30_stub_check.txt`)
  - checkpoint-free, CPU, exit 0. Layers: (1) source/AST checks (one read per knob with
  the documented defaults; the shipped call site untouched; the gate expression; RTC
  classes free of GDP; `rl_env.TASKS_MD5` still matches `tasks.py`); (2) knob resolution
  + K clamp (0/-3 -> 1, 5/7/99 -> 4); (3) selection on synthetic score vectors (min wins;
  ties -> first); (4) the scored chain bit-identical to `ddim_sample` + the score values;
  (5) the knob-off byte-inert proof (off == manual shipped draw == on/K=1, chunks bitwise
  + generator states equal; class-default and instance-missing runners take the shipped
  path); (6) the GDP path end-to-end on a switching fake model (two sequential draws; the
  lower-score candidate wins and its chunk is reproduced independently; tie -> first;
  K=4 -> four candidates); (7) the `[gdp]` row exact-format + regex parse.
* **`logs/p10d1/check_gdp_real_inert.py`: PASS on the real checkpoint**
  (`logs/p10d1/20_real_inert.txt`): GDP off == the manual shipped draw bit-for-bit; K=2
  reproducible across runners (chunks bitwise, diag rows equal modulo `cost_ms`); the
  executed chunk is the candidate chain the row names (real row:
  `chosen=1 scores=30.6922,27.3367 fingers=0.0312,0.0311` - a real ~11 % score split).
* `tasks.py` and `rl_env.py` untouched (`rl_env.TASKS_MD5` 6574d92e... still matches);
  no `configs/`, `datasets/`, `checkpoints/`, `Paper/` writes; no simulator started.

## 5. md5s (this lane's artifacts)

| file | md5 |
| --- | --- |
| `src/fruit_sorting/policy/runtime.py` (the whole diff) | **379ac7064fd49df8417e94dbf6ed2616** |
| `src/fruit_sorting/tasks.py` (unchanged) | 6574d92eafe38f1025b880d39a9410f9 |
| `src/fruit_sorting/rl_env.py` (unchanged) | 8413fece2203c1bccd84b0d5c3830eb3 |
| `logs/p10d1/check_gdp_stub.py` | e1295a63281aa31067dc64f2c14d0588 |
| `logs/p10d1/measure_gdp_cost.py` | 79b0f26e24715a2fbbd10d6307206ebc |
| `logs/p10d1/check_gdp_real_inert.py` | 8491c3b94350d24324fc038f4e3e7225 |
| `logs/p10d1/10_wall_cost.txt` | ac2692e8d98c16831ad436b828ca41a3 |
| `logs/p10d1/20_real_inert.txt` | 91ba972c12faf2d1e2d3a70c76ce503e |
| `logs/p10d1/30_stub_check.txt` | 11c7eae67562ed521736ad6d7af19636 |

(`logs/` is gitignored; the stub + record + outputs need `git add -f` to be committed -
the prereg already was, at `93e0bb4`.)

## 6. The battery (deferred; a separate lane)

Stage 1, exactly per `logs/p10d1/PREREG_GDP_AB.md`:

```
RUNS=3 EPISODES=15 AB_SEEDS="77 101 202" ARM_A_ENV="" \
  ARM_B_ENV="FRUIT_POLICY_GDP=1 FRUIT_POLICY_GDP_K=2" scripts/112_rl_ab.sh
```

Arm B adds nothing else: both arms get `AB_POLICY_SEED=11` (the harness), `moe_v13s`
`61da390a...`, `FRUIT_ACQ_DIAG=1` where the `[acq]` readouts need it. The endpoint is the
close-start |dx| distribution + the no-fire count; the wall cost is reported from section
3; the no-harm bar is the shipped acceptance + the two-line dense re-record + selfcheck +
`172`. Kill 1 (byte-inertness) is already satisfied by section 4's proofs; kill 4 (the
stub suite) passes. Stage 2 (N=5 paired carried-class) only if stage 1 reads non-worse.
The diag row (`FRUIT_POLICY_GDP_DIAG=1`) is available for the mechanism record but is not
part of the battery's own readouts.
