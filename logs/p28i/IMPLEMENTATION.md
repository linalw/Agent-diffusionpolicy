# P28-B IMPLEMENTATION: the belt-speed channel (26th proprio scalar)

Lane P28-B (recommendation **(b)** of `logs/p28/SPEED_CHANNEL_DESIGN.md`),
implementation only, 2026-10-21, branch `p-supply`, tree at `9cbcfa2`
("P28-A: the collector manifest's `supply.belt_speed` field") plus this lane's
working-tree diff. **No simulator run was made** - a P28-C collection battery was
in flight the whole time (`datasets/ss008` → `ss015`); everything below is
offline. No commit; no branch/merge/push. `tasks.py`, `model.py`, `runtime.py`,
`configs/`, `datasets/`, `checkpoints/` are **untouched**.

## 0. The verdict in one paragraph

The 26th proprio scalar exists end to end and is **off by default**: with
`FRUIT_OBS_SPEED` unset every pre-existing path is byte-inert (the observation
stays 25-D, the stores return the shipped concatenation, the normaliser is the
shipped computation, no belt read is added to the control loop). Armed, the
observation is 26-D carrying `trigger.transport_speed()` - the estimator the
scripted primitive's schedule acts on - with a **fixed `(0.12, 0.05)`
normaliser** and a **zero-initialised** new input column, so the widened anchor
is the anchor: the deployed (batch-1) forward pass and the sampled action chunk
are **byte-identical** to `moe_v13s`, and the channel's *value* has exactly zero
influence at step 0 (0.0 / 0.08 / 0.12 / 0.15 are bit-identical). One part of
the design's B0 claim does **not** hold as stated and is corrected here: a
*batched* (training-shape) forward pass transmits the channel through a K=25→26
GEMM and therefore differs by float32 summation order (measured ≤ 2.9e-6 on the
denoiser output, 1.2e-7 on the conditioning vector, 0.0 in a float64 reference
of the same layer). See §5.

## 1. Diff summary

```
 src/fruit_sorting/rl_env.py            +74  -5    the gate, proprio()'s 26th
                                                   scalar, the checkpoint-width
                                                   guard, _MANIFEST_SOURCES
                                                   (+policy/data.py,
                                                   +policy/finetune.py), the
                                                   manifest's belt_speed /
                                                   speed_channel
 src/fruit_sorting/policy/data.py      +289  -17   the channel's definition +
                                                   pin chain + the single
                                                   proprio assembly +
                                                   compute_normalizer's fixed
                                                   pair
 src/fruit_sorting/policy/finetune.py  +151  -8    widen_proprio (the splice),
                                                   the store pins + the
                                                   width cross-check, the
                                                   provenance block, and the
                                                   VLASH state offset routed
                                                   through the store
 src/fruit_sorting/policy/correction.py +14   -3   the audit bug: slice with the
                                                   loaded head's config
 scripts/111_rl_finetune.py             +42   -0   --store-speed / --base-speed
 scripts/60_eval_policy.py              +36  -13   the second assembly site + the
                                                   same width guard
 logs/p28i/*                                    this record + the stub
```

`logs/p28i/10_diff.patch` is the exact diff (970 lines). `src/fruit_sorting/
policy/model.py`, `train.py` and `policy/runtime.py` are **unchanged**: the
model's dims are a constructor argument read from the checkpoint's config
(`runtime.py`), a from-scratch train reads them from the sample (`train.py`), and
the normaliser is loaded from the artifact (`runtime.py`) - so none of the three
needs a P28-B edit. That is the design's own claim (§3.1) and it held.

## 2. The gate

| env | effect |
| --- | --- |
| `FRUIT_OBS_SPEED` unset (default) | the shipped 25-D observation. `rl_env.proprio()` is the old concatenation, the value is **not computed** (no encoder attribute read, no rigid-body read), `EpisodeStore` returns 25 dims, `compute_normalizer` is the old computation. |
| `FRUIT_OBS_SPEED=1` | the 26-D observation. The 26th scalar is `policy.data.belt_speed_scalar(spawner, sample, use_encoder=<the trigger's setting>)`, i.e. `trigger.transport_speed()`; the stores append the per-episode pin; the normaliser's last entry is the fixed `(0.12, 0.05)`. |

The gate is read **once** per object (`SortingRLEnv.__init__`,
`EpisodeStore.__init__` via `speed_channel=`, `60_eval_policy` at module import),
like the other env knobs. A caller can arm a store explicitly
(`EpisodeStore(..., speed_channel=True)` or `belt_speed=<m/s>`) without the env -
`belt_speed=` implies the channel, so a pin can never be silently dropped.

**The mismatch is loud in both directions.** `SortingRLEnv.__init__` refuses a
checkpoint whose `config["proprio_dim"]` disagrees with the gate
(`want_proprio = 25 + (1 if self._speed_channel else 0)`), `60_eval_policy.py`
does the same at load, and `finetune()` refuses a store width that disagrees
with the checkpoint (`rollouts store proprio_dim=... but the checkpoint expects
...`). A 26-D checkpoint is therefore *self-describing and self-enforcing*: it
cannot be run by a harness that would feed it 25 dims.

## 3. The semantics

### 3.1 The value (design C1)

`proprio[25] = transport_speed()`, the **same estimator the primitive acts on**:
the encoder when it is finite and non-zero, the fruit's measured rigid-body
velocity otherwise. The wrapper is shared by both assembly sites
(`rl_env.proprio()` and `scripts/60_eval_policy.py`), so the model and the
schedule cannot disagree about the speed. In this build the encoder is a
setpoint echo (P27), so the value *is* `cfg.belt_speed`'s magnitude; if the
encoder is ever made real the channel follows it for free.

The measured-velocity read is **lazy**: the helper calls the estimator first and
only pays the rigid-body read when the estimator reports `"measured"`. On the
shipped side that is one attribute read per observation tick, in contrast to
adding a per-tick pose/velocity read to the control loop (the instrumentation
rule in AGENTS §2).

### 3.2 The units (design C2)

The channel's normaliser is the **fixed** pair `(0.12, 0.05)` - written by the
surgery (`widen_proprio`) and by `EpisodeStore.compute_normalizer`, never derived
from a store. z-grid: 0.06 → −1.20, 0.08 → −0.80, 0.10 → −0.40, 0.12 → 0.00,
0.15 → +0.60 (all inside |z| ≤ 1.3). Deriving it would be a trap the design
names: the fine-tune never recomputes the normaliser, so a later retrain would
silently redefine the channel's units.

### 3.3 The pin chain (design §2.2 "store conversion: none")

The channel is a per-episode constant, so the artifact stays unchanged and the
column is synthesised at load:

```
index.json entry -> "shard" -> <shard>/manifest.json -> supply.belt_speed
                  -> (no shard)  <root>/manifest.json -> supply.belt_speed | belt_speed
                  -> the caller's declared pin (--store-speed / belt_speed=)
                  -> 0.12
```

* The chain is **per episode**, not per store: a merged store can carry two
  speeds (the design's `demos_ss`), and the stub pins that
  (`[0.08, 0.15]` from two shard stamps).
* A **declared pin that contradicts a manifest raises** (`SPEED_PIN_TOL = 1e-3`).
  That is design §2.2 risk 2 - the one silent failure this design has to
  exclude - and it is the *only* place the loader refuses.
* **Deviation from the design, on the mission's instruction:** a store with no
  speed evidence *defaults* to 0.12 (with one printed `[data] speed channel:
  ... sources={'default': n}` line) instead of requiring an explicit pin. The
  design wanted a hard requirement for any store outside the four known-0.12/
  0.06 ones. The consequence is named: `demos_v12_015` (0.15, no `supply` block)
  and any pre-`9cbcfa2` 0.06 store must be pinned with `--store-speed`, and the
  loader tells you which source it used, per store, on every load.
* `rl_env._build_manifest` now records `belt_speed` (the magnitude; the config
  is signed along −Y) so a rollout run dir's *own* manifest closes the chain for
  the stores `scripts/110_rl_rollout.py --record` writes - `--store-speed` is
  only needed for legacy stores.
* The pin table for the existing stores is the design's §4.3 table
  (`demos_v7/v9/v10=0.06`, `demos_v11/v12/v13p=0.12`, `demos_v12_015=0.15`,
  `ss008=0.08`, `ss015=0.15` - the last two now self-pin through their
  `supply.belt_speed`).

### 3.4 The single assembly site

`EpisodeStore.proprio(ep_index, t=None)` is now the only place the vector is
built: `__getitem__` (one frame), `compute_normalizer` (all frames) and
`finetune._OffsetWindows` (the VLASH state offset, which *duplicated* the
concatenation and would have silently dropped the new dim) all call it. The
gate-off outputs are bitwise the pre-P28-B expressions (stub §4).

## 4. The 13 design sites, and what happened to each

| # | site (design §2.2 table) | status |
| --- | --- | --- |
| 1 | `rl_env.py:1213-1240` `proprio()` | **done** - 26th scalar under the gate, from `transport_speed()`; `spawner.belt is None` → 0.0 |
| 2 | `rl_env.py:1034-1042`, `1538-1550` the goal | **unchanged**, as designed (the channel is not in the goal) |
| 3 | `policy/data.py:97-105` `EpisodeStore.__init__` | **done** - `belt_speed=` / `speed_channel=`, `proprio_dim`, per-episode pins |
| 4 | `policy/data.py:187-193` the append | **done** - in `proprio()`, appended last |
| 5 | `policy/data.py:207-227` `compute_normalizer` | **done** - same assembly, fixed pair *written* |
| 6 | `policy/finetune.py:289-296` the 26-entry normaliser | **done** - read from the (possibly widened) checkpoint; the store width is cross-checked |
| 7 | `policy/finetune.py:379-387` the splice | **done** as `widen_proprio(...)` - zero column, bias kept, config/normaliser grown, idempotent |
| 8 | `policy/correction.py:39-40,151-153` the constant slicing | **done** - slices with `self.head.config["obs_dim"/"goal_dim"/"action_dim"]` |
| 9 | `scripts/60_eval_policy.py:328-340` the second builder | **done** - same helper, same gate, same width guard |
| 10 | `scripts/114_rl_obs_diff.py:99` the layout line | **unchanged** (outside this lane's write set). The guard passes: it runs with the gate off and prints the shipped 25-D layout. With the gate on its printed line is stale - named as a follow-up (§8). |
| 11 | `rl_env.py:282-295` `_MANIFEST_SOURCES` | **done** - `policy/data.py` **and** `policy/finetune.py` (design §2.5 item 2) |
| 12 | `scripts/111_rl_finetune.py:28-42` `--store-speed`/`--base-speed` | **done** - repeatable `PATH=SPEED`, resolved per role, printed |
| 13 | `policy/finetune.py:482-497` provenance | **done** - a `speed_channel` block: enabled, width, gate value, normaliser pair, both declared pins, and the loader's resolved pins/manifests per store |

Plus the two provenance items the design found (§6.1, §2.5.2 - the run
manifest's `belt_speed`/`speed_channel` and the loader/finetune pins) and one
extra site the design did not list: **`finetune._OffsetWindows`** (the VLASH
state offset re-assembled the 25-D vector itself; it now goes through the
store).

## 5. B0 identity - what holds exactly, and the one correction

`python3 logs/p28i/check_speed_channel.py` (exit 0, 53 checks; log
`logs/p28i/00_check_speed_channel.log`), against
`checkpoints/moe_v13s/policy_best.pt` (md5 **61da390a85fa209496b54477a8255d23**,
`proprio_dim=25`, `obs_mean`/`obs_std` = 25):

| claim | result |
| --- | --- |
| the widened first layer is `(128,25) -> (128,26)` and the **new column is exactly 0** | **exact** (`torch.equal(col, zeros)`) |
| the 25 old columns, the bias and **every other tensor** are bitwise the artifact's | **exact** |
| the normaliser gains **exactly** `(0.12, 0.05)` and nothing else changes | **exact** (float32(0.12) = 0.119999997…) |
| the surgery is idempotent (2nd call is a no-op, no double append) | **exact** |
| the **channel's value** has no influence at step 0 (0.0/0.08/0.12/0.15) | **exact, 0.0** at every batch size |
| **batch-1** forward pass (the deployed shape) | **bit-identical, 0.0** |
| `PolicyRunner.act` chunk, moe_v13s (25-D) vs the widened artifact (26-D), CPU/fp32, seeded | **byte-identical, 0.0** |
| float64 reference of the same first layer | 2.2e-16 (fp64 summation floor; no algorithmic difference) |
| **batched** forward (the training shape, batch 3 / 32) | **not** bit-identical: conditioning 1.2-2.4e-7, denoiser output 2.4-2.9e-6 |

**The correction.** The design (§2.2, §5.1 F-F) claims "a zero weight times any
input is 0.0, and adding 0.0 to a float sum is exact, so the conditioning vector
is bit-identical". That is true for a *sequential* sum but not for a blocked
GEMM: growing K from 25 to 26 makes BLAS re-order the reduction of the **old**
25 terms, so a batched forward differs in the last float32 bits. The numbers
above are the measurement. Nothing leaked - the difference appears at batch 2,
is the size of a reduction re-order, is 0.0 at batch 1, and is exactly the same
when the channel's value changes (i.e. it is *not* the new column doing it).

**Therefore the B0 acceptance must be stated as:** (i) the splice invariants
(column exactly 0, prefix/bias/other tensors bitwise) - exact; (ii) the channel's
value has zero influence - exact; (iii) the **deployed** forward/action chunk -
exact 0.0; (iv) a *batched* offline fidelity read - `<= 1e-5` on the output,
with the fp64 reference as the proof it is arithmetic. A tool that prints
"exactly 0" for a *batched* paired read is measuring the GEMM, not the channel.

**A structural note on the design's prescribed B0 tool.** §5.1 says to run
`scripts/119_rl_fidelity.py --base checkpoints/moe_v13s --candidate
checkpoints/spd_init`. That cannot run after the splice: `119` builds **one**
`EpisodeStore` and hands the same `obs["proprio"]` to both policies, so a 25-D
base and a 26-D candidate cannot both be fed (with the gate off the store is
25-D and `spd_init` fails; with it on the store is 26-D and `moe_v13s` fails).
`119` is outside this lane's write set, so the B0 is delivered as this lane's
stub instead (real artifact, real model class, real `PolicyRunner`); a
`119`-level B0 needs a `--proprio-pad 25->26` mode and is named as the follow-up
(§8). For the record the design's intent - "if it is not 0, the zero-column
splice leaked" - is fully covered by (i)-(iii), and (iii) is *stronger* than a
window-level paired delta because it is the deployed sampler.

## 6. Verification

| check | result |
| --- | --- |
| `python3 -m py_compile` on all six touched files | PASS |
| `scripts/selfcheck.sh` (21 legs + the motion-budget skip) | **PASS, 0 failures** (`logs/p28i/50_selfcheck.log`) |
| `logs/p28i/check_speed_channel.py` (new stub, 53 checks) | **PASS** (`logs/p28i/00_check_speed_channel.log`) |
| `scripts/114_rl_obs_diff.py` (the two-assembly-site guard) | **exit 0**, torch section executed (`logs/p28i/10_114_rl_obs_diff.txt`) - its default output path was redirected into this lane to respect the write set |
| every pre-existing `logs/*/check_*.py` (19 stubs) | 14 PASS, 5 **pre-existing** FAIL - see below (`logs/p28i/20_existing_stubs.log`) |
| gate-on fine-tune smoke (`111`, 1 epoch, 2-episode synthetic store, CPU) | PASS - widened 25→26, per-episode pins `[0.08, 0.15]`, saved artifact reloads in `PolicyRunner` (26-D) and `act` returns a finite chunk (`logs/p28i/30_finetune_smoke.log`, `31_artifact_read.txt`) |
| the same command with the gate unset | PASS - 25-D artifact, no widening, no channel keys in the model |
| the pin-conflict guard | raises with the two speeds and the manifest path (stub §3; also hit live when smoke-tested with a deliberately wrong `--speed` pin) |

**How the gate-off inertness is proven, and its limit.** The *training-side*
inertness is numeric: the store's per-frame vector, its all-frames form and
`compute_normalizer` are compared bitwise against the pre-P28-B expressions
(stub §4). The *env-side* inertness is structural (no simulator was available):
the AST check pins that the only `belt_speed_scalar` call in `proprio()` sits
inside `if self._speed_channel:`, that the gate is read once in `__init__`, and
that the concatenation's first three parts are unchanged - so with the gate off
the method returns the same array from the same reads. The two assembly sites
are once again pinned by `scripts/114_rl_obs_diff.py`, which passes (exit 0)
with the gate off and the torch section executed.

**The five pre-existing stub failures** (none touches this lane's files; both
`tasks.py` and `policy/model.py` are byte-identical to the pre-lane tree -
`b54b5406...` and `89000266...` - so they failed before it):

* `logs/p12a2/check_subknobs.py`, `logs/p12/check_physics_real.py` - assert
  `tasks.py == 810658b8...` (the P11-C.3 baseline). The current `tasks.py` is
  `b54b5406...` (the md5 `rl_env.TASKS_MD5` pins; unchanged since commit
  `5268a8c`, P26), so these are historical pins that later commits moved.
* `logs/p13/check_ev1_runtime.py`, `logs/p13/check_event_heads.py` - expect the
  **reverted** event-head API (`ConditionalUNet1D(event_heads=...)`,
  `model.EventHeads`), reverted in `489325c` and documented in AGENTS §2.
* `logs/path1/check_bar.py` - a CLI that needs a 112 fidelity table; with no
  argument it prints usage and exits 1.

## 7. Provenance / md5

| file | md5 |
| --- | --- |
| `src/fruit_sorting/rl_env.py` | `661e467bc545059246daa34d1fcaf430` |
| `src/fruit_sorting/policy/data.py` | `104260325869acee675e123653d8ed1e` |
| `src/fruit_sorting/policy/finetune.py` | `ffac6e8ab9711030c62ab01c8ca72fcf` |
| `src/fruit_sorting/policy/correction.py` | `e1dccf8f7780481e510d59fcc4a1a7ea` |
| `scripts/111_rl_finetune.py` | `b6613d387468c629f13dde6e52bb0832` |
| `scripts/60_eval_policy.py` | `a3bf44e6bb4764a56daa8eca6f82bf02` |
| `logs/p28i/check_speed_channel.py` | `3eea43d6f367d595cba777adf1791057` |
| `src/fruit_sorting/policy/model.py` (untouched) | `890002664d6d3ca057942a083b33b755` |
| `src/fruit_sorting/tasks.py` (untouched) | `b54b54064607c50f7ed0adc906c97a45` |
| `src/fruit_sorting/policy/runtime.py` (untouched) | `379ac7064fd49df8417e94dbf6ed2616` |
| `checkpoints/moe_v13s/policy_best.pt` (read-only) | `61da390a85fa209496b54477a8255d23` |

`TASKS_MD5` is unchanged (`b54b5406...`), so the RL env still starts on this
tree. The manifest's `sources` dict gains two keys; `129_rtc_report.py` unions
the key sets, so runs before and after this lane stay comparable.

The pre-existing dirty files in `git status` (`logs/p21i/90_driver.log`,
`logs/p24/ORACLE_GATE5.md`, `logs/p27/*`, `logs/p9a/*`) were modified before
this lane and are **not** part of this diff.

`logs/` is gitignored in this repo (`.gitignore:7`), so this record and the stub
are on disk but untracked; add them with `git add -f logs/p28i/...` when the
phase is committed (the pattern `logs/p10c2/` was committed the same way, while
`logs/p28/SPEED_CHANNEL_DESIGN.md` itself is still untracked).

## 8. What this lane did not do (named)

1. **The verification battery** (design §5): the 3-speed x 2-arm N=5 direct A/B,
   the collection (`ss008`/`ss015` are being collected by P28-C), the fine-tune
   `spd_init -> spd_v1`, and F-A/F-B/F-C/F-D/F-E. This lane delivers the
   *interface* and its proofs; every endpoint is unchanged from the design.
2. **`spd_init` is not written to `checkpoints/`.** The stub writes it to
   `logs/p28i/_tmp/spd_init.pt`; `checkpoints/` is outside this lane's write set.
   The surgery command for the verification phase is exactly
   `111 --ckpt checkpoints/moe_v13s/policy_best.pt ...` - the widening is
   automatic and idempotent, so no separate init artifact is strictly needed;
   the design's `spd_init` exists only to make the B0/F-D reads explicit.
3. **`scripts/119_rl_fidelity.py`** - a mixed-width pair cannot run through it
   (§5); a `--proprio-pad` mode is the follow-up if a window-level B0 or an
   F-D read through `119` is wanted.
4. **`scripts/114_rl_obs_diff.py`'s layout line** still prints "25-D"; it is
   outside this lane's write set and is correct for the shipped (gate-off) path.
   When the channel is armed the line should print 26 and name the channel - a
   two-line change in a later phase.
5. **`scripts/146_train_correction.py`** trains the A2C2 head with the module
   constants (25/8). The controller now slices by config, so a 26-D head would
   *load and run* correctly, but no 26-D head has been trained - the A2C2 path
   stays default-off and 25-D.
6. **The direct/scripted primitive's own encoder path** is untouched: the
   channel is a model input only.
