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
the 26-D widened artifact.

**The correction.** The design says a zero weight times any input is 0 and adding
0.0 to a float sum is exact, "so the conditioning vector is bit-identical". True
for a sequential sum, false for a blocked GEMM: K grows 25 -> 26 and BLAS
re-orders the reduction of the *old* 25 terms. Measured on the anchor - batch 3:
2.4e-7 on the conditioning vector, 2.9e-6 on the denoiser output; batch 32:
1.2e-7 / 2.4e-6; batch 1: **0.0**; float64 reference of the same layer: 2.2e-16
(the fp64 floor, i.e. no algorithmic difference). It is not the new column: the
same delta appears with the channel at 0.0. So the B0 acceptance is: splice
invariants exact, the channel's influence exactly nil, the **deployed** forward
and chunk exact 0.0, and a *batched* offline fidelity read within `1e-5` with the
fp64 reference as the proof that it is arithmetic. A batched paired read that
prints "exactly 0" would be measuring the GEMM.

**The design's B0 tool cannot run, structurally.** `119_rl_fidelity.py` builds
one `EpisodeStore` and hands the same `proprio` to both policies, so a 25-D base
and a 26-D candidate cannot both be fed (gate off: the candidate fails; gate on:
the base fails). `119` is outside this lane's write set; the B0 is delivered as
`logs/p28i/check_speed_channel.py` (real artifact, real model class, real
`PolicyRunner`) and a `--proprio-pad 25->26` mode on `119` is the named
follow-up. The design's intent - "a leak, or no B0" - is covered by the three
exact identities, and the deployed-chunk equality is strictly stronger than a
window-level delta.

**Two audit bugs fixed with the same change.** `policy/correction.py` sliced the
concatenated correction input with the module constants `OBS_DIM/GOAL_DIM`
instead of the loaded head's `config` - a 26-D proprio would have fed a
silently shifted vector into a 25-D head (default-off A2C2 path, no shipped run
affected, but the ablation corpus would have become unreadable). And
`rl_env._MANIFEST_SOURCES` now pins `policy/data.py` *and* `policy/finetune.py`:
the loader decides what the model sees, and for a design whose whole content is
*how the input is assembled* an unpinned loader means two runs are
indistinguishable. The run manifest also gains `belt_speed` (the P28-A collector
field's rollout-side twin) and `speed_channel`, which is what lets a rollout run
dir pin its own speed through the store chain - so `--store-speed` is needed only
for legacy stores.

**One extra site the design did not list.** `finetune._OffsetWindows` (the VLASH
state offset) re-assembled the 25-D vector itself; it now calls
`EpisodeStore.proprio()`, which is the single assembly site for
`__getitem__`, `compute_normalizer` and the offset. Duplicating an assembly is
exactly how a new dimension gets silently dropped.

**Verification (offline only; a P28-C collection battery held the simulator).**
`py_compile` on all six files; `scripts/selfcheck.sh` **PASS, 0 failures** (21
legs); the new stub **PASS, 53 checks**; `scripts/114_rl_obs_diff.py` **exit 0**
with its torch section executed (gate off: the shipped 25-D layout, as it should
print); all 19 pre-existing `logs/*/check_*.py` stubs run, 14 PASS and 5 FAIL for
**pre-existing** reasons (two pin the historical `tasks.py 810658b8` from the
P11-C.3 baseline, which later commits moved - the current `tasks.py` is
`b54b5406`; two expect the reverted P13 event-head API; one is a CLI that needs a
112 fidelity table) - `tasks.py` and `policy/model.py` are byte-identical to the
pre-lane tree. A 1-epoch CPU fine-tune on a synthetic 2-episode store exercises
the whole training path: widening, per-episode pins `[0.08, 0.15]`, the
provenance block, and an artifact that reloads in `PolicyRunner` as 26-D and
samples a finite chunk; the same command without the gate produces a 25-D
artifact and no channel keys.

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
