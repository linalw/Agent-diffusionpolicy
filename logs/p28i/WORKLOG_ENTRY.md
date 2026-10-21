# WORKLOG entry (P28-B) - append to WORKLOG.md

> Append-only. Paste the block below at the end of `WORKLOG.md`, under §4's list
> of greppable headings. The design is `logs/p28/SPEED_CHANNEL_DESIGN.md`; the
> implementation record is `logs/p28i/IMPLEMENTATION.md`.

---

### The belt-speed channel is one proprio dim that starts inert - and a batched forward is not bit-identical to its parent

**What was built.** Recommendation (b) of P28-A, end to end and **off by
default**: a 26th proprio scalar carrying `trigger.transport_speed()` (the
estimator the scripted primitive's schedule acts on), armed by
`FRUIT_OBS_SPEED=1`. With the gate unset, `rl_env.proprio()` is the shipped 25-D
concatenation and the value is never computed, `EpisodeStore` returns 25 dims,
`compute_normalizer` is the shipped computation, and no extra sensor read enters
the control loop. Armed, the store synthesises the column from the pin chain
(`index.json` entry -> `shard` -> `<shard>/manifest.json` -> `supply.belt_speed`,
then the declared `--store-speed`, then 0.12), the normaliser's last entry is the
fixed `(0.12, 0.05)`, and a 25-D checkpoint is widened in `finetune()` with one
zero column plus that normaliser entry. No recorded array changes meaning.

**Why the width is enforced, not trusted.** The channel's failure mode is silent
(a wrong constant), so every boundary is loud instead: the env refuses a
checkpoint whose `config["proprio_dim"]` disagrees with the gate, `60_eval_policy`
does the same at load, `finetune()` refuses a store width that disagrees with the
checkpoint, and `EpisodeStore` **raises** when a declared pin contradicts a
manifest (`|Δ| > 1e-3`) - the design's §2.2 risk 2, and the only case where a
store is refused. A store with no speed evidence defaults to 0.12 *and says so*
(`[data] speed channel: ... sources={'default': n}`), which is the mission's
instruction and a deliberate softening of the design's "require an explicit pin"
(it makes `demos_v12_015` a store you must pin, not one the loader catches).

**B0: three exact identities, and one claim that does not survive measurement.**
Against `moe_v13s` (`61da390a`), the splice is exact where it matters: the new
column is exactly 0, the 25 old columns and every other tensor are bitwise the
artifact's, the normaliser gains exactly `(0.12, 0.05)`, the surgery is
idempotent, and **the channel's value has exactly zero influence** (0.0 / 0.08 /
0.12 / 0.15 give bit-identical outputs at every batch size). The **deployed**
path is byte-identical: the batch-1 forward pass and the sampled action chunk
from `PolicyRunner.act` are both exactly 0.0 apart between the 25-D anchor and
the 26-D widened artifact. `scripts/119_rl_fidelity.py` now measures the same
thing on real windows - it gained `--data-speed` and a **two-width feed** (each
checkpoint gets the prefix its own `config["proprio_dim"]` declares), so the
25/26 pair that used to be a shape error runs and reads **action delta 0.0 rad,
finger 0.0** over 24 windows of `v11_s0` on CPU/fp32 (`logs/p28i/41_b0_119.txt`);
the non-identity control (candidate `moe_v12`) reads 0.807 rad, so the zero is a
measurement. The criterion is **≤ 1e-6**, not equality.

**The correction.** The design says a zero weight times any input is 0 and adding
0.0 to a float sum is exact, "so the conditioning vector is bit-identical". True
for a sequential sum, false for a blocked GEMM: K grows 25 -> 26 and BLAS
re-orders the reduction of the *old* 25 terms. Measured on the anchor - batch 3:
2.4e-7 on the conditioning vector, 2.9e-6 on the denoiser output; batch 32:
1.2e-7 / 2.4e-6; batch 1: **0.0**; float64 reference of the same layer: 2.2e-16
(the fp64 floor, i.e. no algorithmic difference). It is not the new column: the
same delta appears with the channel at 0.0. So the B0 acceptance is: splice
invariants exact, the channel's influence exactly nil, the **deployed** forward
and chunk exact 0.0, and the `119` action/finger delta ≤ 1e-6 with the fp64
reference as the proof that any residual is arithmetic. A batched paired read
that prints "exactly 0" would be measuring the GEMM.

**The pin is per episode, the default is gone, and a wrong pin is loud (P28 Gate
A B2).** `EpisodeStore` resolves each episode through `entry["shard"]` ->
`<shard>/manifest.json` -> `supply.belt_speed` (so a merged cross-speed store is
one store with two pins), and the store-level `--store-speed` is the *legacy*
fallback. A manifest and a legacy pin must agree; and the old silent
`SPEED_PIN_DEFAULT = 0.12` is replaced by a **provenance table** of the legacy
lineages (`SPEED_PIN_KNOWN`, cross-checked against each store's recorded
goal-`vy`: 0.06 -> -0.060, 0.12 -> -0.119..-0.120), with **`demos_v12_015` (0.15)
deliberately absent** - so an unpinned store with no manifest value **raises**
instead of training at 0.12. Verified against the real stores
(`logs/p28i/42_pin_probe.txt`): `v11_s0`/`v12d_s02`/`v13p_probe` resolve 0.12,
`v10_s0` 0.06, `demos_v12_015` raises until pinned at 0.15, `ss008` self-pins at
0.08, and declaring 0.12 on `ss008` is a conflict. A pin declared while the gate
is off raises in `finetune()` too - a silently dropped pin is the same bug class
as a silent default.

**Two audit bugs fixed with the same change.** `policy/correction.py` sliced the
concatenated correction input with the module constants `OBS_DIM/GOAL_DIM`
instead of the loaded head's config (`Gate A`: read the widths from the
**payload** - the config, cross-checked against the normaliser's `obs_mean`/
`goal_mean` lengths - and refuse an observation of the wrong width), so a 26-D
proprio can no longer feed a silently shifted vector into a 25-D head
(default-off A2C2 path, no shipped run affected, but the ablation corpus would
have become unreadable). And `rl_env._MANIFEST_SOURCES` now pins
`policy/data.py` *and* `policy/finetune.py`: the loader decides what the model
sees, and for a design whose whole content is *how the input is assembled* an
unpinned loader means two runs are indistinguishable. The run manifest also
gains `belt_speed` (the P28-A collector field's rollout-side twin) and
`speed_channel`, which is what lets a rollout run dir pin its own speed through
the store chain - so `--store-speed` is needed only for legacy stores.

**Two more Gate-A defects in the channel's value.** The helper inherited
`FRUIT_POLICY_TRIGGER_ENCODER`, so a trigger knob would have changed the model's
observation as well as the trigger - an A/B arm would have moved two things at
once; it no longer does (`use_encoder` stays the estimator's default). And with
no belt on the spawner it emitted `0.0`, which under the fixed `(0.12, 0.05)`
pair is z = -2.40 and *means* "the belt stopped" - a healthy run would have read
as a policy failure with no error anywhere; it now reports the configured speed
and raises when neither a belt nor a fallback exists. (The remaining caveat is
the encoder's setpoint-echo nature during a real belt stop, P27 §7.1: the
channel is scoped to the never-stop line, which is where the A/B runs.)

**One extra site the design did not list.** `finetune._OffsetWindows` (the VLASH
state offset) re-assembled the 25-D vector itself; it now calls
`EpisodeStore.proprio()`, which is the single assembly site for
`__getitem__`, `compute_normalizer` and the offset. Duplicating an assembly is
exactly how a new dimension gets silently dropped.

**Verification (offline only; a P28-C collection battery held the simulator).**
`py_compile` on all eight files; `scripts/selfcheck.sh` **PASS, 0 failures** (21
legs); the new stub **PASS, 67 checks**; `scripts/114_rl_obs_diff.py` **exit 0**
with its torch section executed (gate off: the shipped 25-D layout, as it should
print); the B0 through `119` on real windows (above); the B2 resolver probe on
the real stores (above); both B2 failure modes raise (a conflicting
`--store-speed`, and a pin with the gate off); all 19 pre-existing
`logs/*/check_*.py` stubs run, 14 PASS and 5 FAIL for **pre-existing** reasons
(two pin the historical `tasks.py 810658b8` from the P11-C.3 baseline, which
later commits moved - the current `tasks.py` is `b54b5406`; two expect the
reverted P13 event-head API; one is a CLI that needs a 112 fidelity table) -
`tasks.py` and `policy/model.py` are byte-identical to the pre-lane tree. A
1-epoch CPU fine-tune on a synthetic 2-episode store exercises the whole
training path: widening, per-episode pins `[0.08, 0.15]`, the provenance block,
and an artifact that reloads in `PolicyRunner` as 26-D and samples a finite
chunk; the same command without the gate produces a 25-D artifact and no channel
keys.

**What is not done.** The verification battery (the 3-speed x 2-arm N=5 direct
A/B), the cross-speed collection (P28-C), `spd_init -> spd_v1`, and
F-A/F-B/F-C/F-D/F-E are untouched: this lane delivers the interface and its
proofs. The channel's whole claim - that a conditioning change is cheaper to
learn than a behaviour change, and that the 0.12 anchor survives the mix - is
still the design's bet, and F-D (`||W[:,25]||` and the paired fidelity) is the
cheap kill before any simulator time. For the record, the readout is already
computable on an artifact: after one epoch on the synthetic store the column's
norm moved off 0 (`||W[:,25]|| = 1.07e-3`), so the mechanics of the F-D read are
in place.
