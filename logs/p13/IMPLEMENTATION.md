# P13-A IMPLEMENTATION (2026-10-19): the event-structure handover heads + the transition-weighted loss - implemented, trained into `checkpoints/ev1`, the A/B deferred

Mechanism-menu item #6 (`docs/papers/MECHANISMS.md` line 37): "Event-structure
handover heads (phase + time-to-transition) + transition-weighted loss"
(ForeTime-VLA #50 + DAM-VLA #42). This lane is the implementation + the training
only; the the W7-B shape (N=3x15, seeds 77/101/202) as launched; the menu's N=5 paired is the confirmatory follow-on only if the mechanism read moves direct-interface A/B is P13-B (a separate lane, no
simulator runs here).

Branch `p-supply`. No shipped default changed: both knobs are default off and
every knob-off path is byte-identical (pinned by the stub below). `tasks.py` is
untouched, so the `rl_env.TASKS_MD5` pin is unchanged (checked).

## 1. The diff

| file | change | md5 (of record) |
| --- | --- | --- |
| `src/fruit_sorting/policy/model.py` | +82: the `EventHeads` module (GRU 128->64 over the 8-step history + phase/TtT heads); `ConditionalUNet1D(event_heads=False)`; the optional `proprio_history` argument on `forward`/`denoise`; `last_event` | `a4de9cb1f99f271d57734dbb4eeb2e0a` |
| `src/fruit_sorting/policy/finetune.py` | +430/-16: the knob resolution, the label derivation, `transition_gauss`, `_EventWindows`, the `_OffsetWindows` event-aware offset, the transition-weighted `_window_weights`, `window_loss_terms`, `event_state_split`, and the fine-tune integration (aux loss + metrics, payload split, provenance) | `3bb1a0621a809e758b3961be33d5b71f` |
| `scripts/111_rl_finetune.py` | +29: `--event-heads`, `--event-transition-weight`, `--event-aux-weight`, `--event-ttt-weight`, `--event-chunk-gamma` (all env-defaulted) | `5e9f8ad8fac563d4d2049bd81be8abd0` |
| `logs/p13/check_event_heads.py` | new offline stub, 39 checks | `80d4bffe43249fa49b7c5417f4d72eab` |
| `logs/p13/smoke_finetune_ev1.py` | new end-to-end smoke (tiny synthetic store, CPU) | `e8231a0c2c126d6c4e4c596446f55c89` |
| `logs/p13/check_ev1_runtime.py` | new post-training runtime-load check | (see `50_runtime_check.txt`) |

Record artifacts under `logs/p13/`: `40_train_ev1.log` (the full training log),
`21_stub_check.txt` (39/39), `22_smoke_finetune.txt`, `30_selfcheck.txt` +
`30_selfcheck.log`, `50_runtime_check.txt`, `60_weight_delta.txt`,
`IMPLEMENTATION.md` (this file), `WORKLOG_ENTRY.md`. (The sibling P13-C lane's
`10_*`, `11_*`, `90_*`, `run_c.sh` in the same directory are not this lane's.)

Not touched: `tasks.py`, `rl_env.py` (the `TASKS_MD5` pin still matches
`810658b802d22bbd63013726fc78af81`), `policy/trigger.py`, `policy/train.py`,
`runtime.py`, `configs/*`, `Paper/*`.

## 2. The design decision (what "closest-to-shipped" resolved to)

The menu offers two ways to *use* the heads: **near-zero-init gates** (ForeTime
injects the phase/time tokens into the student's conditioning with gates init
0.05) or **the trigger input** (the heads feed the handover decision in
`policy/trigger.py`). Both need a runtime-side source for the 8-step history,
and this lane's write scope excludes `runtime.py`/`rl_env.py` (and the A/B lane
must be able to run the trained checkpoint with the *shipped* `PolicyRunner`,
whose `load_state_dict` is strict). A gate that opens during training but
cannot be fed at inference would be a train/inference mismatch - the repo's
conventions forbid shipping an unmeasurable half.

The form implemented is therefore the **auxiliary-supervision subset with the
heads attached to the shared conditioning side**:

* `EventHeads` reads the *shared* `ConditionEncoder.proprio` MLP over the
  history (`condition.proprio` embeddings per step -> GRU -> heads), so the
  auxiliary loss trains the shared proprio encoder itself - the conditioning
  the P10-D.1 residual names as the bottleneck;
* the heads are **read-only**: `cond` and the action output are bit-identical
  with or without a history (pinned); at inference the heads are simply not
  run, and the trained change rides the shared encoder weights;
* the checkpoint keeps the shipped interface: `payload["model"]` is the
  base-key state_dict (strict-loadable by the shipped `PolicyRunner`), and the
  head parameters travel under `payload["event_heads"]` (prefix-free, so
  `model.event.load_state_dict(...)` re-attaches them directly).

The two menu forms are recorded as the enable paths, each with its hook point:
(i) the near-zero-init gated injection needs `PolicyRunner` to keep a proprio
ring buffer and pass `proprio_history` into `denoise` (then a gate + projection
can be added to `cond`); (ii) the trigger input needs the env loop to run the
heads per tick and pass phase/TtT into `should_fire`. Neither is built here.

**Correction to the menu text:** the P6 synthesis says "26-D proprio"; our
proprio is **25-D** (joint 22 + finger 1 + tactile 2). The heads use the
actual 25-D layout. The 8-step causal history is edge-padded with frame 0.

## 3. The label derivation (free signals only)

`finetune.episode_event_labels(episode)` per frame `t`:

* **close** = first frame with recorded finger command < `CLOSE_FINGER`
  (0.0435) - the existing `close_start_frames` rule (the demos hold 0.044 until
  the ramp);
* **carry** = first frame of the `lift` leg (skill == 2), **place** = first
  frame of the `place` leg (skill == 3), both from the free `label_episode`
  skill labels the `EpisodeStore` already derives (fruit position + finger +
  goal);
* **phase**: 0 before close, 1 in `[close, carry)`, 2 in `[carry, place)`,
  3 from `place` on. A missing boundary simply leaves its phase without
  frames (the 3 of 208 store episodes with no `grasp`-leg frame extend the
  close window to the place);
* **TtT** = `min((next_transition - t) / H, 1)` with `H = 120` frames (4.0 s at
  30 Hz) and 1.0 after the last transition. Measured over demos_v11+v12
  (208 episodes, 42,526 frames): distance-to-next-transition p50 28, p90 66,
  p99 95, max 111 - so `H = 120` is the smallest round horizon with no
  clipping except the by-construction tail.

Label stats (printed by the training run, `40_train_ev1.log`; the same rules
applied to both stores, 208 episodes / 42,526 frames in total):

| store | episodes | phase frames 0/1/2/3 | close / carry / place found | mean transition weight | windows at >= 1.5x |
| --- | --- | --- | --- | --- | --- |
| demos_v12 (rollout) | 158 | 8187 / 4749 / 12330 / 7032 | 158 / 155 / 158 | 1.158 | 4710 / 29612 (15.9 %) |
| demos_v11 (base) | 50 | 3248 / 1788 / 3000 / 2192 | 50 / 50 / 50 | 1.160 | 1500 / 9378 (16.0 %) |

The 3 missing `carry` boundaries are the demos_v12 episodes with no
`grasp`-leg frame (the close window extends to the place; the earlier store
scan found the same 3 of 208).

The head input is the normalized causal history `[proprio[t-7..t]]` (oldest
first) in the same layout and normalization as the model's proprio input
(`episode_event_data`).

## 4. The loss

* **Auxiliary**: `L += 0.20 * CE(phase_logits, phase) + 0.02 * MSE(ttt, ttt)`
  (ForeTime's reported loss-weight schedule 0.20/0.02; the mapping to our two
  terms is our choice, recorded). The auxiliary gradient flows into the shared
  `condition.proprio` encoder.
* **Transition-weighted action loss** (`FRUIT_POLICY_EVENT_TRANSITION_WEIGHT`,
  default 0 = off): each window's weight is multiplied by `1 + alpha * g(d)`
  with `g` DAM-VLA's asymmetric Gaussian (`sigma_lead = 6` frames before the
  transition, `sigma_trail = 2` after; `d` = signed distance to the *nearest*
  transition), and the per-chunk MSE gets DAM-VLA's `gamma**j` position decay
  (`gamma = 0.8`). The weighted mean divides by `sum(w)`, so a global rescale
  is a no-op and no separate normalization step is needed (recorded as a
  deliberate simplification). The ev1 run used `alpha = 1.0` (peak boost 2x).
  The `gamma**j` chunk decay is bundled into the same mode (the synthesis's
  port description bundles them); the two are separable in a later ablation.

## 5. The training record

Command (branch `p-supply`, GPU free at launch: `pgrep -fc "[p]ython.sh"` = 0;
the "2" echoed into the log is the wrapper's own command line self-matching the
pattern, not a simulator):

```bash
python scripts/111_rl_finetune.py \
  --ckpt checkpoints/moe_v13s/policy_best.pt \
  --rollouts datasets/demos_v12 --base datasets/demos_v11 \
  --out checkpoints/ev1 --epochs 6 --lr 5e-5 --weight-mode ones \
  --event-heads 1 --event-transition-weight 1.0
```

Base pin: `moe_v13s` md5 **61da390a85fa209496b54477a8255d23**; rollouts
demos_v12 (158 episodes / 29,612 windows) + base demos_v11 (50 / 9,378);
`weight_mode=ones`, seed 0, batch 32, cuda. Full log:
`logs/p13/40_train_ev1.log`.

| epoch | mse* | weighted* | router_ce | router_acc | demo_val | phase_acc | ttt_mae | s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0251 | 0.0261 | 0.044 | 0.984 | 0.0123 | 0.812 | 0.2459 | 204.9 |
| 2 | 0.0236 | 0.0244 | 0.036 | 0.988 | 0.0138 | 0.892 | 0.2040 | 203.7 |
| 3 | 0.0229 | 0.0235 | 0.029 | 0.990 | 0.0125 | 0.913 | 0.1944 | 203.1 |
| 4 | 0.0218 | 0.0224 | 0.025 | 0.991 | 0.0245 | 0.925 | 0.1891 | 203.6 |
| 5 | 0.0210 | 0.0216 | 0.023 | 0.992 | 0.0183 | 0.933 | 0.1848 | 202.8 |
| 6 | 0.0207 | 0.0214 | 0.020 | 0.993 | 0.0167 | 0.938 | 0.1812 | 203.4 |

\* with the chunk `gamma=0.8` in the mode, `mse`/`weighted` are the
gamma-weighted means (early chunk positions dominate) - **not comparable** to
the w3 curve's numbers, which are unweighted; `demo_val` is the unweighted
demo loss on the base slice and is comparable. The run also starts from
`moe_v13s` (itself 6 epochs from `moe_v12`), so every absolute loss value is
lower than the w3 run's by construction.

Wall: **21:50.24** total (`/usr/bin/time -v`; user 2,540 s, 195 % CPU; 6 epochs
203-205 s each + ~2.5 min store load), max RSS 48.6 GB, exit 0.

Artifact: `checkpoints/ev1/policy_best.pt`, **md5
`c2656cc292c9c65eff0ba19b6632d59a`** (18,575,253 bytes), plus
`checkpoints/ev1/finetune_history.json`. The payload: `model` = the base-key
state_dict; `event_heads` = 8 prefix-free head tensors + the knob record;
`provenance` names the base pin, both stores, every event knob and the label
stats. The head accuracies are **training-set** metrics (no head-only
validation split was held out; the policy's `demo_val` is the held-out read).

**Where the training moved the weights** (`logs/p13/60_weight_delta.txt`, ev1
vs the base): overall mean |delta| 0.0022; the per-module max |delta| is
largest in **`condition.proprio` 0.152** (vs `blocks` 0.025, `condition.goal`
0.025, `visual` 0.030, `router` 0.072) - the auxiliary supervision
concentrated on the shared proprio encoder, the intended conditioning-side
channel. This is a weight-delta read, not a behavioral claim; the behavior is
P13-B's endpoint.

**Named confound for the A/B:** ev1 is 6 further epochs from `moe_v13s`, so a
`moe_v13s` vs ev1 delta mixes the event supervision with 6 extra epochs of the
same recipe. If P13-B shows movement, the matching control is a plain 6-epoch
re-run with both knobs off (component-pinned (construction + loss/weight arithmetic); the end-to-end control is the knob-off re-run); the
mission's spec pins the base as `moe_v13s`, which this lane follows.

## 6. The verification

* `python3 -m py_compile` on all three touched files: OK.
* `scripts/selfcheck.sh`: **PASS, 0 failures** (`logs/p13/30_selfcheck.txt`,
  full log `logs/p13/30_selfcheck.log`) - includes the rtc runtime selftest
  which constructs the shipped model through the changed `model.py`.
* `logs/p13/check_event_heads.py`: **PASS, 39/39** (`logs/p13/21_stub_check.txt`):
  the knob resolution (env default off, `None`-resolved `finetune` params); the
  knob-off model byte-identity (state_dict key set == the shipped checkpoint's,
  identical RNG stream, bit-identical outputs with/without a history); the
  head shapes; the label derivation on synthetic transitions + the fallback +
  three real demos_v11 episodes; the history construction; the loss-weighting
  arithmetic (`transition_gauss` exact values, the `_window_weights` identity
  and boost, `window_loss_terms` bit-equal to the shipped formula and to the
  manual `gamma**j` mean); `event_state_split`; and the VLASH-offset/event
  label alignment.
* `logs/p13/smoke_finetune_ev1.py`: **PASS** (`logs/p13/22_smoke_finetune.txt`) -
  a full `finetune` epoch on a tiny synthetic store, knobs off (payload has no
  event block, shipped key set) and on (payload split, strict base load,
  head re-attachment, provenance fields).
* `logs/p13/check_ev1_runtime.py`: **PASS** (`logs/p13/50_runtime_check.txt`) on
  the real artifact - the shipped `PolicyRunner` loads `checkpoints/ev1`
  strictly and returns a finite action chunk; the payload carries the event
  block and the moe_v13s base pin; the heads re-attach.

## 7. The A/B (P13-B) - deferred, and what it needs

Nothing here ran a simulator. P13-B runs the direct interface (the W7-B pin:
`FRUIT_POLICY_TRIGGER_LATERAL=0.06`-pinned branch per W4, seeds 77/101/202,
`moe_v13s` base pinned) with `ARM_B = checkpoints/ev1/policy_best.pt`, and the
pre-registered endpoints: the fire-path classification error, the handover-time
distribution and the fallback chases, the W7-B shape (N=3x15, seeds 77/101/202) as launched; the menu's N=5 paired is the confirmatory follow-on only if the mechanism read moves, kill on a re-seat rise
(R11-A 0->10). The checkpoint is directly usable by the shipped runtime
(`logs/p13/check_ev1_runtime.py` pins the strict load), so the A/B needs no
code change beyond its own battery harness.

## 8. Deviations / corrections of record

* the auxiliary-only form (vs the menu's two deployment forms) - section 2;
* 25-D proprio, not the menu text's 26-D - section 3;
* the auxiliary loss weights 0.20/0.02 are ForeTime's schedule, mapped to
  phase CE / TtT MSE by us (their five weights' exact mapping is not stated in
  the re-read);
* DAM-VLA's "normalized" trajectory weights are a no-op under the existing
  per-batch weighted mean (section 4);
* `H = 120` is our measured choice (the paper's horizon is its own prediction
  horizon).


## 9. The Oracle's confound note (2026-10-19)

**ev1 differs from `moe_v13s` in three ways at once**: (a) the auxiliary heads - **training-only**
(the shipped `PolicyRunner` never runs them; the checkpoint carries them under
`payload["event_heads"]`, dropped at inference), so any A/B movement is **weight-mediated**;
(b) the transition-weighted loss + the chunk gamma; (c) the 6 extra epochs. The matching
controls, if the mechanism read moves: the knob-off 6-epoch re-run plus the two single-factor
ablations. The end-to-end degradation read is the A/B itself (the action-loss curve's
monotone fall is not a quality claim - `demo_val` ends above its epoch-1 value, the same shape
as the v13s run).
