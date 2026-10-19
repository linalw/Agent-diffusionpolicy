# P14-C.1 IMPLEMENTATION (2026-10-19): the ev1 ablation trainings (A1/A2/A3) - three 6-epoch fine-tunes from `moe_v13s` under the preserved P13 code; all three checkpoints load in the shipped runtime and the tree is restored byte-identically

The P14-C plan (`.slim/deepwork/sorting-pipeline-v3.md` line 2893): the ev1
attribution. The P13-B A/B read a positive mechanism (+3 outcomes, p = 0.2266
at N=3; the left close-start 178.5 -> 3.5 mm; the chases 11 -> 2) but ev1
differs from `moe_v13s` in three ways at once (the Oracle's confound note,
`logs/p13/IMPLEMENTATION.md` section 9): (a) the event heads + aux loss
(training-only), (b) the transition-weighted loss + chunk gamma, (c) the 6
extra epochs. This lane runs the three matching fine-tunes so the later
mechanism screen (P14-C.2) can attribute the movement to a single factor:

| arm | flags | isolates | out dir |
| --- | --- | --- | --- |
| **A1** | `--event-heads 1 --event-transition-weight 0` | the heads + aux loss only | `checkpoints/ev_a1` |
| **A2** | `--event-heads 0 --event-transition-weight 1.0` | the transition-weighted loss + chunk gamma only | `checkpoints/ev_a2` |
| **A3** | `--event-heads 0 --event-transition-weight 0` | the 6-epoch-only control | `checkpoints/ev_a3` |

All three use the ev1 recipe's flags verbatim otherwise (`logs/p13/40_train_ev1.log`
line 22): `--ckpt checkpoints/moe_v13s/policy_best.pt --rollouts datasets/demos_v12
--base datasets/demos_v11 --epochs 6 --lr 5e-5 --weight-mode ones` (seed 0,
batch 32, cuda by default). The event-chunk gamma stays at its default 0.8; per
the P13 code it is applied only when `event_transition_weight > 0`, so **A1's
loss carries no gamma and no transition weights** (its `weighted` == `mse` by
construction) and **A2's carries both** (the P13 record bundles them; the two
are separable only in a further ablation).

## 1. The tree state and the swap

The event-heads code is **reverted on the branch** (precautionary revert
`489325c`, back to `63594c4`; the P14-A battery closed the canary anomaly as an
instrument artifact, `logs/p14/A_RESULTS.md`) and **preserved at `e078f43`**.
This lane swaps the three files in for the trainings and restores HEAD after
(`logs/p14c/run_ablations.sh`; the restore is the script's `EXIT` trap, so it
fires on success, on any training failure and on TERM/INT):

| file | pre-swap (HEAD) md5 | e078f43 (trained tree) md5 | post-restore md5 |
| --- | --- | --- | --- |
| `src/fruit_sorting/policy/model.py` | `890002664d6d3ca057942a083b33b755` | `a4de9cb1f99f271d57734dbb4eeb2e0a` | `890002664d6d3ca057942a083b33b755` |
| `src/fruit_sorting/policy/finetune.py` | `214d197204bd8346ba7a33d54602eaa3` | `3bb1a0621a809e758b3961be33d5b71f` | `214d197204bd8346ba7a33d54602eaa3` |
| `scripts/111_rl_finetune.py` | `3eb6ae73a44b3eedb8f628030a0eb036` | `5e9f8ad8fac563d4d2049bd81be8abd0` | `3eb6ae73a44b3eedb8f628030a0eb036` |

Driver steps: (1) `pgrep -fc "[p]ython.sh"` = 0 and `checkpoints/ev_a1|ev_a2|ev_a3`
absent; (2) pre-swap md5s saved (`00_md5_saved.txt`); (3) `git show e078f43:<path>`
into each of the three paths, md5-verified (`00_md5_e078f43.txt`); (4) `py_compile`
+ `--help` sanity (`01_help.txt`); (5) the three trainings sequentially with
`/usr/bin/time -v`, stop-on-first-failure; (6) `git checkout HEAD -- <the three
paths>` + md5 diff vs saved. Nothing touched `checkpoints/moe_v13s` or
`checkpoints/ev1` (both md5s re-verified after the battery:
`61da390a85fa209496b54477a8255d23` / `c2656cc292c9c65eff0ba19b6632d59a`), and
the only writes outside `logs/p14c/` are the three new checkpoint dirs.

## 2. The training records

The exact commands (also in each log's `/usr/bin/time -v` block):

```bash
python scripts/111_rl_finetune.py --ckpt checkpoints/moe_v13s/policy_best.pt \
  --rollouts datasets/demos_v12 --base datasets/demos_v11 --out checkpoints/ev_a1 \
  --epochs 6 --lr 5e-5 --weight-mode ones --event-heads 1 --event-transition-weight 0
# A2: --out checkpoints/ev_a2 --event-heads 0 --event-transition-weight 1.0
# A3: --out checkpoints/ev_a3 --event-heads 0 --event-transition-weight 0
```

All three printed the identical data lines (`rollouts=datasets/demos_v12 (158
episodes, success 158)`; `base=datasets/demos_v11 (50 episodes)`; `windows=38990
weight_mode=ones vbar=0.0000 ...`). A1/A2 printed the event lines with the label
stats (`rollout: phase_frames {0: 8187, 1: 4749, 2: 12330, 3: 7032},
close_found 158, carry_found 155, place_found 158`; `base: {0: 3248, 1: 1788,
2: 3000, 3: 2192}, 50/50/50`) - identical to the ev1 run's, as they must be
(same stores, same rules). A2's transition-weight stats reproduce ev1's to the
digit (`mean_weight` 1.157966809817727 / 1.1602292812634964; `transition_windows`
4710/29612 and 1500/9378), a cross-check that the weighting path is the same
code. A3 printed no event lines by construction.

**A1** (heads + aux only; no gamma, no transition weights - `weighted` == `mse`):

| epoch | mse | weighted | router_ce | router_acc | demo_val | phase_acc | ttt_mae | s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0251 | 0.0251 | 0.044 | 0.984 | 0.0115 | 0.813 | 0.2454 | 203.4 |
| 2 | 0.0239 | 0.0239 | 0.036 | 0.988 | 0.0130 | 0.893 | 0.2038 | 203.9 |
| 3 | 0.0235 | 0.0235 | 0.029 | 0.989 | 0.0121 | 0.913 | 0.1942 | 205.4 |
| 4 | 0.0226 | 0.0226 | 0.025 | 0.992 | 0.0228 | 0.925 | 0.1889 | 204.3 |
| 5 | 0.0216 | 0.0216 | 0.023 | 0.992 | 0.0166 | 0.933 | 0.1847 | 204.8 |
| 6 | 0.0213 | 0.0213 | 0.020 | 0.993 | 0.0164 | 0.938 | 0.1811 | 204.0 |

**A2** (transition-weighted loss + gamma 0.8; no heads - no phase/TtT metrics):

| epoch | mse | weighted | router_ce | router_acc | demo_val | s |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0250 | 0.0258 | 0.043 | 0.985 | 0.0122 | 203.1 |
| 2 | 0.0234 | 0.0241 | 0.034 | 0.988 | 0.0138 | 203.8 |
| 3 | 0.0227 | 0.0233 | 0.030 | 0.989 | 0.0129 | 202.5 |
| 4 | 0.0216 | 0.0222 | 0.027 | 0.990 | 0.0232 | 202.9 |
| 5 | 0.0210 | 0.0217 | 0.022 | 0.992 | 0.0169 | 202.6 |
| 6 | 0.0205 | 0.0211 | 0.020 | 0.993 | 0.0168 | 203.7 |

**A3** (the plain 6-epoch control; `weighted` == `mse`):

| epoch | mse | weighted | router_ce | router_acc | demo_val | s |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0252 | 0.0252 | 0.044 | 0.985 | 0.0121 | 202.2 |
| 2 | 0.0237 | 0.0237 | 0.034 | 0.988 | 0.0128 | 202.0 |
| 3 | 0.0231 | 0.0231 | 0.030 | 0.990 | 0.0122 | 200.7 |
| 4 | 0.0223 | 0.0223 | 0.027 | 0.991 | 0.0211 | 201.0 |
| 5 | 0.0216 | 0.0216 | 0.023 | 0.992 | 0.0155 | 201.5 |
| 6 | 0.0211 | 0.0211 | 0.020 | 0.993 | 0.0153 | 201.4 |

ev1 for comparison (`logs/p13/40_train_ev1.log`; both knobs on):

| epoch | mse | weighted | router_ce | router_acc | demo_val | phase_acc | ttt_mae | s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0251 | 0.0261 | 0.044 | 0.984 | 0.0123 | 0.812 | 0.2459 | 204.9 |
| 6 | 0.0207 | 0.0214 | 0.020 | 0.993 | 0.0167 | 0.938 | 0.1812 | 203.4 |

(As in the P13 record: `mse` is the plain per-window mean, `weighted` carries
the gamma when the transition mode is on - so A1/A3's two columns coincide by
construction; the loss curves are not quality claims - `demo_val` ends above
its epoch-1 value in every arm, the same shape as v13s/ev1.)

**Wall time / resources / artifacts** (`/usr/bin/time -v`, all exit 0):

| arm | wall (h:mm:ss) | CPU | max RSS | checkpoint md5 | bytes |
| --- | --- | --- | --- | --- | --- |
| A1 | 21:52.50 | 196 % | 48,609,172 KB | **`0c18f6bec929745ba7ac3359079fe608`** | 18,574,997 |
| A2 | 21:45.20 | 196 % | 48,484,624 KB | **`74a58e4a1b758908eab0310fd22bec39`** | 18,426,699 |
| A3 | 21:35.34 | 193 % | 48,426,908 KB | **`275e06f9f55a3341dcc1789896dd1151`** | 18,425,931 |

Battery total: 17:21:30 -> 18:26:45 = **1:05:15** (three runs back to back).
Each dir carries `policy_best.pt` + `finetune_history.json` (4,128 / 4,015 /
2,867 bytes); every provenance names `base_checkpoint_md5 =
61da390a85fa209496b54477a8255d23` (moe_v13s), `epochs=6`, `lr=5e-5`,
`weight_mode=ones`; A1 carries the full event knob set + label stats, A2 the
event set without the heads block, A3 no event fields at all. The recorded
`tasks_md5` in all three is the `rl_env.TASKS_MD5` pin constant
`54f70584b07fa249418f1efe30f30af0` (a literal import; the offline fine-tune
does not read `tasks.py`).

## 3. The runtime-load + payload verification

`logs/p14c/check_ablations.py` (run on the restored tree; output
`50_runtime_check.txt`): **PASS, all checks** - for each of ev_a1/ev_a2/ev_a3
(and ev1 re-checked for comparability):

* the **shipped `PolicyRunner`** (strict `load_state_dict`) constructs from the
  checkpoint and one `act()` returns a finite chunk;
* `payload["model"]` is **base keys only** (no `event.*`) in all three - the
  shipped runtime interface is intact;
* A1: the `event_heads` block carries **8 prefix-free tensors**; the provenance
  says heads on / transition weight 0.0; the history rows carry
  `event_phase_acc` + `event_ttt_mae`; the heads **re-attach** through the
  e078f43 `model.py` (imported standalone) and emit finite `(3, 4)` / `(3,)`
  outputs;
* A2: no `event_heads` block; provenance heads off / transition weight 1.0;
* A3: no `event_heads` block; provenance has **no event fields** (the plain
  path, byte-identical in kind to the shipped fine-tune);
* base pin, epochs, lr, weight_mode and the 6-row history match in all three.

## 4. The weight-delta read (where the training moved the weights)

`payload["model"]` vs `moe_v13s`, per-module max |delta| (the P13
`60_weight_delta.txt` format; `50_runtime_check.txt`):

| module | ev1 | **A1** (heads) | **A2** (loss) | **A3** (control) |
| --- | --- | --- | --- | --- |
| overall mean \|d\| | 0.002196 | 0.002283 | 0.002032 | 0.002077 |
| **condition.proprio** | **0.151849** | **0.150916** | 0.029422 | 0.031255 |
| blocks | 0.025468 | 0.029791 | 0.026391 | 0.028258 |
| router | 0.072094 | 0.070783 | 0.074380 | 0.072360 |
| experts | 0.032360 | 0.026022 | 0.037429 | 0.027352 |
| visual | 0.029529 | 0.029025 | 0.025675 | 0.027133 |
| condition.goal | 0.025268 | 0.026141 | 0.025403 | 0.025730 |
| head | 0.018115 | 0.024563 | 0.020284 | 0.020342 |
| time | 0.012910 | 0.013847 | 0.009335 | 0.010659 |
| action_in | 0.004868 | 0.003880 | 0.004578 | 0.003815 |

(The ev1 column reproduces `logs/p13/60_weight_delta.txt` exactly - 0.002196
over 4,594,926 params - a consistency check on the read.)

**The reading (a weight-delta read, not a behavioral claim):** the
`condition.proprio` concentration is present exactly when the **heads** are on
- ev1 0.1518, A1 0.1509 - and absent when they are off - A2 0.0294, A3 0.0313
(the same order as each other). The transition-weighted loss + gamma alone does
**not** move the shared proprio encoder; the heads' auxiliary supervision does,
which is the P13 design intent ("the auxiliary loss trains the shared proprio
encoder itself"). The remaining attribution question - whether the behavioral
movement the P13-B A/B measured (the close-start/chases/fire-path) follows the
heads or the loss - is **P14-C.2's endpoint** (the W7-B-pin mechanism screen,
seed 77; the P13 records reused as the `moe_v13s`/ev1 controls). The overall
mean |delta| is nearly flat across arms (0.0020-0.0023), as expected for six
epochs at lr 5e-5 from a converged checkpoint.

## 5. The restore verification

`00_driver.log` tail:

```
[p14c] ALL DONE 18:26:45
[p14c] RESTORE START rc=0 18:26:45 -- git checkout HEAD -- the three files
[p14c] RESTORE VERIFIED: post-restore md5s == pre-swap md5s
```

* `00_md5_saved.txt` == `00_md5_after_restore.txt` (diff of the hash columns
  empty): the three files are byte-identical to their pre-swap state;
* `git diff HEAD -- <the three paths>` is empty - they are at HEAD (`05c83fd`);
* `checkpoints/moe_v13s` and `checkpoints/ev1` md5s re-verified unchanged
  (above); the three new dirs `checkpoints/ev_a1|ev_a2|ev_a3` exist and nothing
  else was written outside `logs/p14c/`.

**Note on the working tree (not this lane's):** at battery end the tree also
carries an **uncommitted `src/fruit_sorting/tasks.py` edit by the concurrent
P17-B lane** (its own "P17-B H1 - the hold/probe-1 slide gate" comment block;
file mtime 18:26:19; live md5 `a9114225ceb39b252afa3eb9f93ae8c5` vs the
`rl_env.TASKS_MD5` pin `54f70584...`). It was present only in the last seconds
of A3 (which does not read `tasks.py`), it is not this lane's change, and it
was **not touched** by this lane.

## 6. Deliverables / artifacts under `logs/p14c/`

`run_ablations.sh` (the driver), `check_ablations.py` (the post-training
verification), `00_driver.log`, `00_md5_saved.txt`, `00_md5_e078f43.txt`,
`00_md5_after_restore.txt`, `01_help.txt`, `A1_train.log`, `A2_train.log`,
`A3_train.log`, `50_runtime_check.txt`, `IMPLEMENTATION.md` (this file),
`WORKLOG_entry.md`. New checkpoints: `checkpoints/ev_a1` `0c18f6be`,
`checkpoints/ev_a2` `74a58e4a`, `checkpoints/ev_a3` `275e06f9`.

## 7. Deviations / notes of record

* The mission's three arms are as specified; nothing else was varied (the
  ev1 recipe's defaults - seed 0, batch 32, `--event-chunk-gamma 0.8`,
  aux/ttt weights 0.20/0.02 - were left in place).
* A1's loss applies no gamma (the code gates it on `transition_weight > 0`);
  so "heads only" is exactly that. A2 bundles DAM-VLA's transition weighting
  with the `gamma**j` chunk decay - the P13 record's own bundling; splitting
  those two is a further ablation, not run here.
* The ablations share the single-factor comparison basis with ev1's third
  factor (the 6 epochs): **A3 is that control**, so the P14-C.2 screen has
  `moe_v13s` / ev1 / A1 / A2 / A3 as its five points.
* No simulator was run and no simulator script was started; the battery is
  GPU-only (RTX 5090, 31 GB free at launch; peak RSS ~48.6 GB of the 125 GB).
