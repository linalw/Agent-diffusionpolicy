### P13-A (2026-10-19): the event-structure handover heads + the transition-weighted loss are implemented and trained into `checkpoints/ev1`; the A/B is deferred

The mechanism-menu #6 lane (ForeTime-VLA #50's phase + time-to-transition
subset + DAM-VLA #42's transition weighting), implementation + training only -
no simulator ran (P13-B owns the battery). Branch `p-supply`; the whole diff is
default-off and the shipped paths are byte-identical (pinned below).

**What was built.** `model.EventHeads`: a GRU (128->64) over an **8-step causal
proprio history** with a 4-class phase head and a normalized-TtT head, attached
to the model's **shared conditioning side** - the heads read the
`ConditionEncoder.proprio` embeddings per history step, so the auxiliary loss
trains the shared proprio encoder itself (the P10-D.1 residual's named
bottleneck). The heads are **read-only**: `cond` and the action output are
bit-identical with or without a history (pinned), so the shipped inference path
is untouched and `payload["model"]` stays strict-loadable by the shipped
`PolicyRunner`; the head parameters travel under `payload["event_heads"]`
(prefix-free, re-attachable). The menu's two deployment forms - the
near-zero-init gated injection into `cond` (ForeTime) and the trigger input
(`policy/trigger.py`) - both need a runtime-side proprio history (out of this
lane's write scope) and are recorded as the enable paths, not built.

**The labels are free** (`finetune.episode_event_labels`): close = the first
frame of the recorded finger ramp (< 0.0435, the existing `CLOSE_FINGER`
rule); carry/place = the first frames of the skill labels' lift/place legs.
Phase 0/1/2/3 = approach / close window / carry / place; TtT =
`min(distance-to-next-transition / 120 frames, 1)` (the measured max distance
is 111, so only the after-place tail clips). Over the two stores (208 episodes,
42,526 frames): phases 8187/4749/12330/7032 (v12) + 3248/1788/3000/2192 (v11);
3 demos_v12 episodes lack a grasp-leg frame and extend the close window to the
place.

**The loss.** Auxiliary: `+0.20 * phase CE + 0.02 * TtT MSE` (ForeTime's
reported weight schedule, mapped to our two terms). The default-off
transition-weighted mode (`FRUIT_POLICY_EVENT_TRANSITION_WEIGHT`): per-window
weight `* (1 + alpha * g(d))` with DAM-VLA's asymmetric Gaussian (sigma 6
leading / 2 trailing, signed distance to the nearest transition) and the
`gamma=0.8` chunk-position decay; the weighted mean makes any global rescale a
no-op, so DAM-VLA's "normalized" step is vacuous here (recorded). The ev1 run
used `alpha = 1.0`.

**The training** (the mission's recipe, from `moe_v13s` md5
`61da390a85fa209496b54477a8255d23`; rollouts `demos_v12` 158/29,612 + base
`demos_v11` 50/9,378, `weight_mode=ones`, 6 epochs, lr 5e-5, seed 0, cuda;
`logs/p13/40_train_ev1.log`): the gamma-weighted action loss 0.0261 -> 0.0214,
router_acc 0.984 -> 0.993, the heads **phase_acc 0.812 -> 0.938 / ttt_mae
0.2459 -> 0.1812** (train-set metrics), `demo_val` 0.0123-0.0245 (unweighted;
the w3-curve comparisons do not apply - this run starts from `moe_v13s` and its
loss is gamma-weighted). Wall **21:50.24** (`/usr/bin/time -v`, max RSS
48.6 GB), exit 0. Artifact **`checkpoints/ev1/policy_best.pt` md5
`c2656cc292c9c65eff0ba19b6632d59a`** (18.6 MB) + `finetune_history.json`. The
weight-delta vs the base (`logs/p13/60_weight_delta.txt`) is largest in
`condition.proprio` (max |delta| 0.152 vs ~0.025 for the other encoders) - the
supervision concentrated on the intended channel.

**Verification.** `py_compile` OK; `scripts/selfcheck.sh` **PASS 0 failures**
(`logs/p13/30_selfcheck.txt`); the new stub `logs/p13/check_event_heads.py`
**39/39** - knob resolution, the knob-off byte-identity (default `state_dict`
== the shipped checkpoint's key set, identical RNG stream, bit-identical
outputs with/without a history), head shapes, the synthetic + real label
derivation, the `transition_gauss`/`_window_weights`/`window_loss_terms`
arithmetic (bit-equal to the shipped formula at the defaults), the state split
and the VLASH-offset label alignment; the CPU smoke
`logs/p13/smoke_finetune_ev1.py` (full epoch, both knob states, payload shape);
the real-artifact runtime check `logs/p13/check_ev1_runtime.py` (the shipped
`PolicyRunner` loads ev1 strictly and `act()` returns a finite chunk).

**Deferred / named items.** (1) P13-B: the the W7-B shape (N=3x15, seeds 77/101/202) as launched; the menu's N=5 paired is the confirmatory follow-on only if the mechanism read moves direct-interface A/B
(seeds 77/101/202, the W7-B pin) with the endpoints fire-path classification
error + handover-time distribution + fallback chases and the re-seat-rise kill;
the checkpoint needs no code change to run. (2) The confound: ev1 = 6 further
epochs from `moe_v13s`; the matching control for any movement is a plain
6-epoch re-run (knobs off, pinned byte-identical by the stub). (3) The menu's
deployment forms (gated injection / trigger input) remain the enable paths if
the A/B shows the conditioning moved. No shipped default changed;
`tasks.py`/`rl_env.py`/`trigger.py`/`runtime.py`/`configs/*` untouched.
