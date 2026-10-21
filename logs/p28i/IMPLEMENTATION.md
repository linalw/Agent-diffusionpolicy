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

**P28 Gate A revision (2026-10-21, after `logs/p28/ORACLE_GATE_A.md`).** Three
items changed the shipped implementation: **B2** - the pin is resolved per
episode through the shard manifest, the store-level pin is the *legacy* fallback,
a manifest and a legacy pin must agree, and **an unpinned store with no manifest
value now raises instead of silently training at 0.12**; **B3** -
`scripts/119_rl_fidelity.py` gained `--data-speed` and a **two-width feed** (each
checkpoint gets the prefix its own `config["proprio_dim"]` declares), and the B0
criterion is **≤ 1e-6**, not equality; and `CorrectionController` reads its
widths from its **payload** (config, cross-checked against the normaliser) and
refuses a mismatched observation. Two further Gate-A findings in this lane's own
code were fixed with them: the `0.0` no-belt sentinel (now the configured speed,
or a raise) and the channel inheriting `FRUIT_POLICY_TRIGGER_ENCODER` (it no
longer does - a trigger knob must not change the model's input). The gate's
default stays **0**.

## 1. Diff summary

```
 src/fruit_sorting/rl_env.py            +82  -5    the gate, proprio()'s 26th
                                                   scalar, the checkpoint-width
                                                   guard, _MANIFEST_SOURCES
                                                   (+policy/data.py,
                                                   +policy/finetune.py), the
                                                   manifest's belt_speed /
                                                   speed_channel
 src/fruit_sorting/policy/data.py      +364  -17   the channel's definition +
                                                   the per-episode pin chain
                                                   (no silent default), the
                                                   single proprio assembly +
                                                   compute_normalizer's fixed
                                                   pair
 src/fruit_sorting/policy/finetune.py  +158  -8    widen_proprio (the splice),
                                                   the store pins + the
                                                   width cross-check, the
                                                   pin-with-the-gate-off raise,
                                                   the provenance block, and
                                                   the VLASH state offset routed
                                                   through the store
 src/fruit_sorting/policy/correction.py +44  -12   payload-derived widths +
                                                   the slicing fix + the
                                                   observation-width guard
 scripts/111_rl_finetune.py             +42   -0   --store-speed / --base-speed
 scripts/60_eval_policy.py              +40   -9   the second assembly site + the
                                                   same width guard
 scripts/119_rl_fidelity.py             +98   -3   --data-speed, the two-width
                                                   feed, the B0 <= 1e-6 readout
 logs/p28i/*                                    this record + the stub
```

`logs/p28i/10_diff.patch` is the exact diff against the pre-lane base
`ffbd439` (1293 lines; `11_uncommitted.patch` is the part HEAD does not have
yet). `src/fruit_sorting/policy/model.py`, `train.py` and `policy/runtime.py`
are **unchanged**: the model's dims are a constructor argument read from the
checkpoint's config (`runtime.py`), a from-scratch train reads them from the
sample (`train.py`), and the normaliser is loaded from the artifact
(`runtime.py`) - so none of the three needs a P28-B edit. That is the design's
own claim (§3.1) and it held.

## 2. The gate

| env | effect |
| --- | --- |
| `FRUIT_OBS_SPEED` unset (default **0**) | the shipped 25-D observation. `rl_env.proprio()` is the old concatenation, the value is **not computed** (no encoder attribute read, no rigid-body read), `EpisodeStore` returns 25 dims, `compute_normalizer` is the old computation. |
| `FRUIT_OBS_SPEED=1` | the 26-D observation. The 26th scalar is `policy.data.belt_speed_scalar(spawner, sample, fallback=<the configured belt speed>)`, i.e. `trigger.transport_speed()`; the stores append the per-episode pin; the normaliser's last entry is the fixed `(0.12, 0.05)`. |

Two Gate-A corrections live in the value itself: the helper does **not**
inherit `FRUIT_POLICY_TRIGGER_ENCODER` (a trigger knob must not change the
model's observation - an A/B arm would otherwise move two things), and with no
belt on the spawner it reports the configured speed (`abs(cfg.belt_speed)`)
instead of `0.0`, which under the fixed pair is z = -2.40 and *means* "the belt
stopped". With neither a belt nor a fallback it raises. (During a real belt
**stop** the encoder is a setpoint echo, so the channel still reads the
commanded speed - the same caveat P27 §7.1 records for the trigger; the channel
is therefore scoped to the never-stop line, which is where the A/B runs.)

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

### 3.3 The pin chain (design §2.2 "store conversion: none"; P28 Gate A B2)

The channel is a per-episode constant, so the artifact stays unchanged and the
column is synthesised at load:

```
index.json entry -> "shard" -> <shard>/manifest.json -> supply.belt_speed
                  -> (no shard)  <root>/manifest.json -> supply.belt_speed | belt_speed
                  -> the caller's declared pin (--store-speed / belt_speed=)
                  -> the documented legacy table SPEED_PIN_KNOWN
                  -> none of the above: RAISE
```

* The chain is **per episode**, not per store: a merged store can carry two
  speeds (the design's `demos_ss`), and the stub pins that
  (`[0.08, 0.15]` from two shard stamps). A *declared* pin is a single value, so
  declaring one for a mixed store is a conflict unless every shard agrees - by
  design: the declaration is an assertion, not a default.
* **The store-level pin is the legacy fallback** (the caller's `--store-speed`),
  and a manifest value and a legacy pin **must agree** (`SPEED_PIN_TOL = 1e-3`).
  That is design §2.2 risk 2 - the one silent failure this design has to exclude
  - and it is the only place the loader refuses a *combination*.
* **There is no silent default any more (B2).** The gate's finding was that
  `SPEED_PIN_DEFAULT = 0.12` made an unpinned store train at 0.12 with no error.
  The replacement is a **provenance** table (`SPEED_PIN_KNOWN`) of the legacy
  basenames whose speed is documented by the design's §4.3 (collection script +
  log) and cross-checked here against each store's recorded goal-`vy` mean
  (0.06 -> -0.060, 0.12 -> -0.119..-0.120); **`demos_v12_015` (0.15) is
  deliberately absent**, so it must be pinned. Anything else raises with the
  store, the episode and the `--store-speed` command to use. Verified against
  the real stores (`logs/p28i/42_pin_probe.txt`):

  | store | declared | result |
  | --- | --- | --- |
  | `demos_v7` / `v10_s0` / `demos_v10` | - | `0.06`, `known:<shard>` |
  | `v11_s0` / `v12d_s02` / `v13p_probe` | - | `0.12`, `known:<shard>` |
  | `demos_v12_015` | - | **raises** (`no belt-speed pin ... --store-speed ...`) |
  | `demos_v12_015` | 0.15 | `0.15`, `declared` |
  | `ss008` (post-P28-A) | - | `0.08`, `manifest:.../ss008/manifest.json` |
  | `ss008` | 0.12 | **raises** (`pin conflict ... declared pins 0.1200 ... records 0.0800`) |

* A pin declared while the channel is **off** raises in `finetune()` instead of
  being ignored (`a belt-speed pin was declared ... but the speed channel is
  off`) - a silently dropped pin is the same bug class as a silent default.
* `rl_env._build_manifest` records `belt_speed` (the magnitude; the config is
  signed along −Y) so a rollout run dir's *own* manifest closes the chain for the
  stores `scripts/110_rl_rollout.py --record` writes - `--store-speed` is only
  needed for legacy stores.
* The table is provenance, not a policy: extend it (with the same goal-`vy`
  witness) when a legacy store is added; a store collected since P28-A never
  needs it.

### 3.4 The single assembly site

`EpisodeStore.proprio(ep_index, t=None)` is now the only place the vector is
built: `__getitem__` (one frame), `compute_normalizer` (all frames) and
`finetune._OffsetWindows` (the VLASH state offset, which *duplicated* the
concatenation and would have silently dropped the new dim) all call it. The
gate-off outputs are bitwise the pre-P28-B expressions (stub §4).

## 4. The design's sites (and the B0 tool), and what happened to each

| # | site (design §2.2 table) | status |
| --- | --- | --- |
| 1 | `rl_env.py:1213-1240` `proprio()` | **done** - 26th scalar under the gate, from `transport_speed()`; no belt → the configured speed (never 0.0) |
| 2 | `rl_env.py:1034-1042`, `1538-1550` the goal | **unchanged**, as designed (the channel is not in the goal) |
| 3 | `policy/data.py:97-105` `EpisodeStore.__init__` | **done** - `belt_speed=` / `speed_channel=`, `proprio_dim`, per-episode pins |
| 4 | `policy/data.py:187-193` the append | **done** - in `proprio()`, appended last |
| 5 | `policy/data.py:207-227` `compute_normalizer` | **done** - same assembly, fixed pair *written* |
| 6 | `policy/finetune.py:289-296` the 26-entry normaliser | **done** - read from the (possibly widened) checkpoint; the store width is cross-checked |
| 7 | `policy/finetune.py:379-387` the splice | **done** as `widen_proprio(...)` - zero column, bias kept, config/normaliser grown, idempotent |
| 8 | `policy/correction.py:39-40,151-153` the constant slicing | **done** - the controller reads its widths from the **payload** (`config`, cross-checked against `obs_mean`/`goal_mean`), slices with them, and refuses an observation of the wrong width |
| 9 | `scripts/60_eval_policy.py:328-340` the second builder | **done** - same helper, same gate, same width guard |
| 10 | `scripts/114_rl_obs_diff.py:99` the layout line | **unchanged** (outside this lane's write set). The guard passes: it runs with the gate off and prints the shipped 25-D layout. With the gate on its printed line is stale - named as a follow-up (§8). |
| 11 | `rl_env.py:282-295` `_MANIFEST_SOURCES` | **done** - `policy/data.py` **and** `policy/finetune.py` (design §2.5 item 2) |
| 12 | `scripts/111_rl_finetune.py:28-42` `--store-speed`/`--base-speed` | **done** - repeatable `PATH=SPEED`, resolved per role, printed |
| 13 | `policy/finetune.py:482-497` provenance | **done** - a `speed_channel` block: enabled, width, gate value, normaliser pair, both declared pins, and the loader's resolved pins/manifests per store |
| 14 | `scripts/119_rl_fidelity.py` (the B0 tool, **P28 Gate A B3**) | **done** - `--data-speed` (legacy pin) and `FRUIT_OBS_SPEED=1` (self-pinning stores) arm the store, and each checkpoint is fed the prefix its own `config["proprio_dim"]` declares (`proprio_for`), so a 25/26 pair is measured instead of crashing; the report prints the store width, the feed widths, the device/fp16 and the B0 line `[...] [B0 criterion <= 1e-6]` |

Plus the two provenance items the design found (§6.1, §2.5.2 - the run
manifest's `belt_speed`/`speed_channel` and the loader/finetune pins) and one
extra site the design did not list: **`finetune._OffsetWindows`** (the VLASH
state offset re-assembled the 25-D vector itself; it now goes through the
store).

## 5. B0 identity - what holds exactly, and the one correction

`python3 logs/p28i/check_speed_channel.py` (exit 0, 67 checks; log
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

**A structural note on the design's prescribed B0 tool - and its fix (B3).** §5.1
says to run `scripts/119_rl_fidelity.py --base checkpoints/moe_v13s --candidate
checkpoints/spd_init`. As shipped it could not run: `119` built **one**
`EpisodeStore` and handed the same `obs["proprio"]` to both policies, so a 25-D
base and a 26-D candidate could not both be fed (gate off: the candidate fails;
gate on: the base fails). Gate A's B3 asked for `--data-speed` plus a two-width
feed, and that is now in: the store is armed by `--data-speed M/S` (a legacy
pin) or `FRUIT_OBS_SPEED=1` (a manifest-pinned store), and `proprio_for()`
gives each checkpoint the prefix its own `config["proprio_dim"]` declares - the
25-D arm receives exactly the shipped vector (the store appends the channel
last), the 26-D arm the whole vector, anything else refuses.

The B0 measured **through `119`, on real windows** (`datasets/v11_s0`, the
anchor's own 0.12 shard, CPU/fp32, 24 windows, DDIM-8, identical noise):

```
base checkpoints/moe_v13s = 0.133 rad / fing 0.0008 / phase 96%
cand logs/p28i/_tmp/spd_init.pt   = 0.133 rad / fing 0.0008 / phase 96%
paired delta (cand - base): median +0.0000 rad, 0 improved / 0 worse / 24 ties
action delta (cand - base): max 0.000e+00 rad, finger max 0.000e+00  [B0 criterion <= 1e-6]
```

`logs/p28i/41_b0_119.txt`. A **non-identity control** on the same store and
noise (candidate = `moe_v12`) reads `max 8.070e-01 rad` / finger `7.96e-03`
(`logs/p28i/43_119_nonidentity.txt`), so the zero is a measurement, not a dead
line. On CUDA the runtime runs fp16 and the difference is quantised - the tool
now prints `fp16=True` and says to run B0 with `--device cpu`.

**Therefore the B0 acceptance is:** (i) the splice invariants (column exactly 0,
prefix/bias/other tensors bitwise) - exact; (ii) the channel's value has zero
influence - exact; (iii) the **deployed** forward/action chunk - exact 0.0; (iv)
the `119` action/finger delta on real windows - **≤ 1e-6** (measured 0.0), with
the fp64 reference as the proof that any residual is arithmetic. A tool that
prints "exactly 0" for a *batched* paired read is measuring the GEMM, not the
channel.

## 6. Verification

| check | result |
| --- | --- |
| `python3 -m py_compile` on all eight touched files | PASS |
| `scripts/selfcheck.sh` (21 legs + the motion-budget skip) | **PASS, 0 failures** (`logs/p28i/50_selfcheck.log`) |
| `logs/p28i/check_speed_channel.py` (new stub, **67** checks) | **PASS** (`logs/p28i/00_check_speed_channel.log`) |
| `scripts/114_rl_obs_diff.py` (the two-assembly-site guard) | **exit 0**, torch section executed (`logs/p28i/10_114_rl_obs_diff.txt`) - its default output path was redirected into this lane to respect the write set |
| **B0 through `119` on real windows** (`v11_s0`, CPU/fp32, 24 windows, DDIM-8) | **action delta 0.0 rad, finger 0.0** (`logs/p28i/41_b0_119.txt`); the non-identity control is 0.807 rad (`logs/p28i/43_119_nonidentity.txt`) |
| the B2 resolver on the real stores | as designed (`logs/p28i/42_pin_probe.txt`): legacy lineages resolve, `demos_v12_015` raises, `ss008` self-pins at 0.08, a wrong declaration is a conflict |
| every pre-existing `logs/*/check_*.py` (19 stubs) | 14 PASS, 5 **pre-existing** FAIL - see below (`logs/p28i/20_existing_stubs.log`) |
| gate-on fine-tune smoke (`111`, 1 epoch, 2-episode synthetic store, CPU) | PASS - widened 25→26, per-episode pins `[0.08, 0.15]`, saved artifact reloads in `PolicyRunner` (26-D) and `act` returns a finite chunk (`logs/p28i/30_finetune_smoke.log`, `31_artifact_read.txt`) |
| the same command with the gate unset | PASS - 25-D artifact, no widening, no channel keys in the model |
| both B2 failure modes | raise: a wrong `--store-speed` (conflict with the shard manifest) and a pin with the gate off (would be silently dropped) - same log, blocks 3-4 |

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
| `src/fruit_sorting/rl_env.py` | `c0b311d52e2af2dbdf52e2570b7bd0cb` |
| `src/fruit_sorting/policy/data.py` | `b4940d74a1961df0c09179eb74b30652` |
| `src/fruit_sorting/policy/finetune.py` | `7a619a4b7b523da8d67ffbf7bbabcb75` |
| `src/fruit_sorting/policy/correction.py` | `bc864088702673c1504f938f55a31b2b` |
| `scripts/111_rl_finetune.py` | `b6613d387468c629f13dde6e52bb0832` |
| `scripts/60_eval_policy.py` | `290b0ec48196f9b5afab1a4075cb2213` |
| `scripts/119_rl_fidelity.py` | `ac97fcddcba9cd1292755ca13623b627` |
| `logs/p28i/check_speed_channel.py` | `6c27247d6cacb5b57625dc45620913b7` |
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

**A note on the history.** The orchestrator committed this lane mid-flight as
`d2b7847` (11:06:30). That commit carries the four `src/` files at their final
(post-Gate-A) content and `logs/p28i/*`, but **not** the three scripts - so the
worktree still has `scripts/111_rl_finetune.py`, `scripts/60_eval_policy.py`
and `scripts/119_rl_fidelity.py` uncommitted. The lane diff of record is
therefore `git diff ffbd439 -- src/ scripts/` (pre-lane base -> worktree), and
`logs/p28i/10_diff.patch` is that diff; `logs/p28i/11_uncommitted.patch` is the
sub-set HEAD does not have yet.

`logs/` is gitignored in this repo (`.gitignore:7`), but `d2b7847` force-added
`logs/p28i/*` (the `logs/p10c2/` pattern), so this record, the stub and the
logs are tracked from that commit on; the edits made after 11:06:30 are the
uncommitted `M logs/p28i/...` entries.

## 8. What this lane did not do (named)

1. **The verification battery** (design §5): the 3-speed x 2-arm N=5 direct A/B,
   the collection (`ss008`/`ss015` are being collected by P28-C), the fine-tune
   `spd_init -> spd_v1`, and F-A/F-B/F-C/F-D/F-E. This lane delivers the
   *interface* and its proofs; every endpoint is unchanged from the design. The
   Gate A precondition (B1, the fire-path split) is not a code item and is
   untouched here.
2. **`spd_init` is not written to `checkpoints/`.** The stub writes it to
   `logs/p28i/_tmp/spd_init.pt`; `checkpoints/` is outside this lane's write set.
   The surgery command for the verification phase is exactly
   `111 --ckpt checkpoints/moe_v13s/policy_best.pt ...` - the widening is
   automatic and idempotent, so no separate init artifact is strictly needed;
   the design's `spd_init` exists only to make the B0/F-D reads explicit.
3. **`scripts/114_rl_obs_diff.py`'s layout line** still prints "25-D"; it is
   outside this lane's write set and is correct for the shipped (gate-off) path.
   When the channel is armed the line should print 26 and *the value* (Gate A
   B4) - a small change in a later phase, together with a live 26-D run of the
   guard (a simulator run).
4. **`scripts/146_train_correction.py`** trains the A2C2 head with the module
   constants (25/8). The controller now takes its widths from the payload and
   refuses a mismatched observation, so a 26-D head would load and run
   correctly - but no 26-D head has been trained, and the trainer would need the
   same treatment before one could be.
5. **The direct/scripted primitive's own encoder path** is untouched: the
   channel is a model input only.
6. **The B2 provenance table** (`SPEED_PIN_KNOWN`) is a hand-checked list of the
   legacy lineages that exist on disk at this commit. A new legacy store (or a
   moved one) must be added with its goal-`vy` witness; a store collected since
   P28-A never needs it. This is the deliberate cost of removing the silent
   default.
