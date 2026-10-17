### P10-D.1 implementation (2026-10-17): the GDP OoD-scored population selection landed default-off in `policy/runtime.py` - the paper's Stein score (eq. 4, min wins) over K in 1..4 DDIM-16 candidates, the knob-off path proven byte-inert on the real checkpoint, and the wall cost measured honestly: **24.8-26.6 ms/candidate (2.1-2.2x the menu's ~12 ms claim, 3.0-3.2x the 8.33 ms tick), K=2 act 49.7-52.9 ms = 1.5-1.6x the 33.3 ms re-plan window** - no simulator run, no retraining, no shipped default changed

Branch `p-supply`, base `93e0bb4` (the frozen prereg `logs/p10d1/PREREG_GDP_AB.md`). Writes:
`src/fruit_sorting/policy/runtime.py` (+215/-8; the only deleted lines are the shipped
`ddim_sample` call re-indented verbatim into the new `else` branch) and
`logs/p10d1/{check_gdp_stub.py, measure_gdp_cost.py, check_gdp_real_inert.py,
IMPLEMENTATION.md, 10_wall_cost.txt, 20_real_inert.txt, 30_stub_check.txt}` + this entry.
`tasks.py`/`rl_env.py` untouched (`rl_env.TASKS_MD5` 6574d92e still matches); no
`configs/`/`datasets/`/`checkpoints/`/`Paper/` writes; no simulator started.

**The mechanism (MECHANISMS item #5, paper #32).** The extract's eq. (4) is readable:
`phi_stein,f,T(x_t,t) = T * f(||eps_theta(x_t,t)||)` (and the clip family; T a temperature,
f a scaling function; extract lines 331-335), and the appendix ranks the heuristics
outright: "minimizing the stein score (or the norm of the estimated noise) is the best of
simple genetic algorithm heuristics" (line 1091). The port is the simplest faithful
version: `FRUIT_POLICY_GDP=1` (default 0) + `FRUIT_POLICY_GDP_K` (default 2, clamp 1..4)
make `PolicyRunner.act` draw K candidates sequentially from the runner's noise source
(the `FRUIT_POLICY_SEED` generator when set - the battery's `AB_POLICY_SEED=11`; candidate
0 of call 0 is exactly the shipped draw), score each by the **mean per-step Stein norm**
via the new `ddim_sample_scored` (a bit-identical eta=0 mirror of
`DiffusionSchedule.ddim_sample` plus the norm bookkeeping; `@torch.no_grad()` like the
shipped sampler), and execute `select_gdp_candidate`'s minimum (ties -> first). The
paper's per-step multinomial survivor machinery is the population-generation half, not
ported; the plausibility-band variant is not implemented (the exact score is readable and
min-Stein is the paper's own best; a band needs an offline-nonexistent calibrated
threshold; the prereg's arm B pins the min form). The default-off `FRUIT_POLICY_GDP_DIAG=1`
prints one `[gdp] k= chosen= scores= fingers= cost_ms=` row per selection (per-candidate
finger-command spread = the range of channel 7; wall cost per candidate). Scope: the
synchronous `act` path only; the RTC/VLASH interleaved sampler is not GDP-scored (pinned
by an AST check).

**Byte-inertness (prereg kill 1) is proven twice.** Checkpoint-free (CPU, fake model):
GDP off == a direct shipped `ddim_sample` call with the same draw == GDP on/K=1, chunks
bitwise and generator states identical; the scored chain is bitwise-equal to the shipped
chain. Real checkpoint (`moe_v13s`, fp16, CUDA): the same identity holds and the K=2 run
is reproducible across runners (chunks bitwise; diag rows equal modulo `cost_ms`), with
the executed chunk verified to be the candidate chain the row names (real row:
`chosen=1 scores=30.6922,27.3367 fingers=0.0312,0.0311`). One real defect the fix pins:
`scripts/128_rtc_selftest.py` builds a `PolicyRunner` via `__new__` without the new
attribute and calls `act` through the RTC chunker - selfcheck's RTC leg caught the
AttributeError, fixed by a class-level `gdp = GDPSettings()` default (disabled) so every
historical checkpoint-free fixture stays byte-inert.

**Wall cost (`logs/p10d1/10_wall_cost.txt`, 30 CUDA-synced iters, no simulator; two
repeats).** Shipped one-candidate chain **24.79-26.55 ms** (matches the recorded 23.69
ms/chunk baseline); GDP scored candidate 24.41-26.06 ms (the scoring bookkeeping is
within noise once under `no_grad` - the first run without the decorator read +2.5 ms of
pure autograd overhead); `act` K=1 25.34-27.04 ms, **K=2 49.65-52.87 ms (1.96x)**. The
menu's "~12 ms each, fits the tick" is the repo's DDIM-8/torch.compile-8 number
(11.96/11.87 ms) carried forward as per-candidate: **2.1-2.2x optimistic for DDIM-16**,
one candidate is **3.0-3.2x OVER the 8.33 ms tick**, and K=2 is **1.5-1.6x OVER the
shipped 33.3 ms re-plan window** (K=1 fits). The sim loop is stepped, not wall-clocked:
the cost cannot change the simulated-time cycle (kill 3 is a sim-clock check) and shows
up as ~+25 ms per re-plan, ~2x the policy-sampling wall on arm B.

**Verification.** `py_compile` OK; `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**
after the class-default fix; the new stub `logs/p10d1/check_gdp_stub.py` **PASS (40
checks)** covering knob resolution + the K clamp, the selection rule on synthetic scores
(min wins, ties -> first), the scored chain's bit-identity, the knob-off byte-inert proof
(including the class-default/instance-missing runners), the GDP path end-to-end on a
switching fake model (lower score wins, tie -> first, K=4), and the `[gdp]` row format;
`check_gdp_real_inert.py` PASS on the real checkpoint.

**No-harm / battery.** No shipped default changed; `selfcheck.sh` PASS. The A/B is the
separate lane per the frozen prereg + amendment (runner `logs/p10d1/run_stage1.sh`, the
W7-B direct-boundary pin: `AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival
FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=0
FRUIT_POLICY_TRIGGER_LATERAL=0.06 FRUIT_ACQ_DIAG=1"`, both arms `AB_POLICY_SEED=11`;
arm B adds `FRUIT_POLICY_GDP=1 FRUIT_POLICY_GDP_K=2`; stage 1 = close-start |dx| +
no-fire; stage 2 N=5 paired carried-class only if stage 1 reads non-worse; the wall cost
is reported above; kills 1 and 4 already satisfied). The battery started 23:08 on the
working tree carrying this uncommitted diff. Tree pin for the battery: `runtime.py`
**379ac7064fd49df8417e94dbf6ed2616** (`tasks.py` 6574d92e, `rl_env.py` 8413fece,
unchanged; HEAD `4d6a128` adds only the runner + the prereg amendment). Named next: run
the battery; if stage 1 fails its endpoint, the mechanism menu's item #5 closes with the
re-read's falsifier (score uncorrelated with outcome / candidate spread dominated by
observation noise) as the recorded reason.
