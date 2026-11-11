# P142 - the direct lane's two fabricated failures, and a declared score endpoint

The direct lane read `0/15`-style rates that did not measure the policy. Two of
those terms are **bookkeeping**, and this phase removes them; the third is the
metric itself, and it is now a declared choice rather than an accident.

## 1. The handover guard was dormant

P139 added a guard against closing on a recycled sample. It was written **inside**
`if FRUIT_SAMPLE_DIAG == "1"`, so the shipped loop never executed it. Measured on
the live rollout (`logs/p141/rollout.log`):

```
[task]   openarm fingertips 103342 mm from the fruit; closing anyway
```

with the guard present and never reached. The guard is now outside the gate, and
its abort is driven by **physical** terms (section 3).

## 2. The despawn scan parked bodies an attempt owned

`FruitSpawner.update`'s despawn loop skipped only `sample.parked`;
`_recycle_end` therefore parked a body that was `held`/`protected` **while the
attempt still read `position(sample)`** - a teleport to `(60 + 3i, 0, -50)`, i.e.
a 100 m pad error. The recycle is now **deferred**: the body is taken off the
line and parked by the next `update()` after the attempt releases it, so the
attempt's reads see the truth (and the env's `fruit fell off the line` test sees a
body 0.25 m below the belt instead of a park slot).

```
[sample] arm=left idx=15 parked=False held=True protected=6 is_protected=False
         pos=(-0.185,-0.221,+0.820)
```

That row is the deferral working: a real position on the floor, not the slot.

## 3. The abort is physical, not flag-based

| term | measured |
|---|---|
| park slot | **101-103 m** (the defect) |
| cross-lane reselect, live fruit | **349 mm, 1144 mm** |
| a legitimate close | **77 mm** |
| largest legitimate value in the record | 415 mm (R11-A's acquisition row) |

`FRUIT_HANDOVER_PAD_ERROR_MAX` defaults to **1.0 m** (2.4x the largest legitimate
row, 100x below the park slot). The flag term `_foreign` (the attempt's
`protected` index names another fruit) is **reported, not gated**: the station
reselect legitimately adopts the presented fruit and re-protects it, so the two
flags lag by a call - measured twice (`idx=9 protected=1`, `idx=15 protected=6`)
with live fruits at 349 mm and 77 mm.

## 4. The endpoint is declared

`success = lifted and on_output_belt(final)`: with `FRUIT_OUTPUT_RAILS=none` (P71)
a payload released **onto** the line can roll off in the ~1 s between the
release's own settle and the finalize, so `placed=True, success=False` is
reachable - measured in `logs/p139/guard2.log` episode 1.

`FRUIT_SCORE_ENDPOINT=release` scores the task's own `placed`, which is
`on_output_belt` sampled **0.5 s after the release** (`tasks.py:17194`, after the
release's 60-tick settle). Default `final`; the episode row prints `endpoint=release`
only when it is armed, so the shipped row stays byte-identical.

## 5. No-harm

* `scripts/accept.sh` with every knob unset: **7/10 = 70 %**, `fingerprint: matches`,
  **459/459 `[fruit]` lines byte-identical** to `logs/p136/accept_final.log`.
* `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new
  **`P142 endpoint + handover`** leg (**26 checks**: the endpoint table and its
  refusal, the guard's source order inside `if openarm:`, the pad-error knob, the
  deferred-recycle branch **executed** both ways on a stub, and the drain keeping
  a still-owned body).
* `scripts/211_bed_audit.py` **ok (115 checks)**.

## 6. What the direct lane reads now, and what it still is

With `FRUIT_POLICY_TRIGGER=arrival`, the P141 checkpoint, the wave and
`FRUIT_SCORE_ENDPOINT=release`, two 2-episode cells read **0/2 and 0/2** - and the
mechanism is visible, not inferred:

```
reselecting across lanes: presented index 9 (grade C) belongs to lane 1,
but the left arm serves lane 0; placing it on the arm's own lane
openarm fingertips 1144 mm from the fruit; closing anyway
```

`station_sample()` filters by `along` and `|x - belt_center| <= 0.30`, so the
presented fruit **was** at the station when it was adopted; by the close it is
1.14 m away or on the floor (`z = 0.820`). The arm descends on the fruit the
**trigger** selected and the reselect adopts a **different** one, then the
descending hand knocks it off the line - the P95 class (a hand sweeping a fruit
band) inside one attempt.

So the fruit was at the station when it was adopted and had left by the close.
That reading is consistent but **it is a symptom**, and section 7 finds the cause.

### 6.1 The cell that closes it

`FRUIT_STATION_RESELECT=0` (close on the fruit the descent aimed at) with
everything else unchanged, 2 episodes, seed 77:

```
episode 0: pear   success=False grasped=False placed=False ticks=1842
episode 1: orange success=True  grasped=True  placed=True  ticks=2928
           reward=0.9611
```

**The first `success=True` of this whole investigation** - and it is scored by the
declared endpoint, not by a loosened one: the payload was released onto the line
(`placed=True`) and the row says `endpoint=release` only because it was armed.

That is one episode, so it is **not a rate**. It is the demonstration that the
three terms this phase touched are the ones that were in the way:

| term | before | after |
|---|---|---|
| the close's pose | a park slot, 101-103 m | the fruit, or an honest abort |
| a body the attempt owns | teleported mid-attempt | deferred until the attempt releases it |
| a successful place | could score False | scores what the task's `placed` says |

and the one term this phase did **not** touch is named in section 6: the station
reselect adopts a presented fruit during the close, after the descent has already
aimed at another one.

## 7. The cause: the direct handover ran the **indexed** primitive against a **predicted** intercept

The trigger computes an intercept (`intercept trigger ... t_arrive=1.93s`), and the
reselect is gated `and not dynamic_capture`. The reselect **ran**, so
`dynamic_capture` was False: the direct handover was running the **P1 indexed**
primitive, whose descent aims at a **frozen** `position(sample)` read once
(`tasks.py:14159`) and then spends a premove plus a track window getting there.
On a belt moving 0.12 m/s that is 0.06-0.36 m of travel between the aim and the
close - the 1.14 m row is the tail of it.

`FRUIT_DYNAMIC_PICK=1` is the moving catch (`_dynamic_pick_mode`, the v8/P1
directive). Same cell, only that knob added:

```
[sample] arm=left  idx=1 parked=False held=True protected=1 is_protected=True
         pos=(+0.225,+0.173,+1.200)
[sample] arm=right idx=3 parked=False held=True protected=3 is_protected=True
         pos=(+0.357,+0.186,+1.185)
episode 0: pear       success=True grasped=True placed=True ticks=1751 reward=0.9715
episode 1: strawberry success=True grasped=True placed=True ticks=1859 reward=0.9595
[run] summary: 2/2
```

**2/2** - and the rows are the healthy state: the sample is the attempt's own
(`protected == idx`, `is_protected=True`) at a real belt position (`z = 1.185-1.200`
= belt top + radius), not the park slot and not 1.1 m away.

**That is one cell of two episodes: not a rate.** What it establishes is narrower
and firmer: the three bookkeeping terms of sections 1-4 are gone, the metric is
declared, and the acquisition mismatch has a name - **the direct handover must run
the catch its trigger assumes**. The recorded numbers for that combination are
pre-P41 (32/45 = 71.1 %, `logs/p2b/ab012`; 27/45 = 60 % with `moe_v12`, P54), so
the next spend is an **N=5 direct A/B** (the WS-4.2 protocol) with
`FRUIT_DYNAMIC_PICK=1`, not another 2-episode smoke.

### 7.1 The cell, verbatim

```bash
FRUIT_CAMERA_RES=240,424 FRUIT_OBS_SPEED=1 FRUIT_OBS_GOAL_AUX=1 \
FRUIT_POLICY_TRIGGER=arrival FRUIT_DYNAMIC_PICK=1 \
FRUIT_SCORE_ENDPOINT=release FRUIT_SAMPLE_DIAG=1 \
FRUIT_BELT_WAVE_AMP=0.04 FRUIT_BELT_WAVE_HZ=0.5 \
SKIP_SELFCHECK=1 scripts/run.sh scripts/110_rl_rollout.py \
  --ckpt checkpoints/p141_wave/policy_best.pt --presentation direct \
  --episodes 2 --seeds 77 --out logs/p142/rollout4
```

`logs/p142/rollout{2,3,4}.log` are the three cells of this section: reselect on
(0/2), reselect off (1/2), dynamic catch (2/2). Only the first is the shipped
direct configuration; the other two are `FRUIT_STATION_RESELECT=0` and
`FRUIT_DYNAMIC_PICK=1` respectively.

## 8. The A/B: the moving catch against the shipped direct primitive

`logs/p142/run_p142_ab.sh`, both arms on seeds **77 / 101 / 202** x 5 episodes,
the same checkpoint (`p141_wave`), the same wave (0.04 m/s x 0.5 Hz), the same
declared endpoint (`FRUIT_SCORE_ENDPOINT=release`); **only `FRUIT_DYNAMIC_PICK`
differs**. `logs/p142/ab_report.py`:

| arm | n | placed | % | success |
|---|---|---|---|---|
| **dynamic** (`=1`, the moving catch) | 15 | **13** | **86.7 %** | 13 |
| **indexed** (`=0`, the shipped direct primitive) | 15 | **10** | 66.7 % | 10 |

Per seed: dynamic 5/5, 3/5, 5/5 - indexed 4/5, 3/5, 3/5.
Paired on `(seed, episode)`: **4 dynamic-only, 1 indexed-only, sign test
p = 0.3750** (n = 15). So the count is a **direction, not a rate** - the record's
own rule (P93) puts a 20-point difference at n = 15 inside the noise.

**What is stronger than the count is the class ledger.** The indexed arm's five
failures carry exactly the events this phase named:

```
note  8x cross-lane station fruit        <- the reselect adopting a lane-1 fruit
note  3x fruit did not follow the gripper
note  2x sample swapped or recycled before the close
```

and the dynamic arm carries **none of them** (its only note is the trigger's own
diagnostic row, which is appended to every attempt).

Two consequences, one measured and one structural:

1. **The 8 cross-lane events disappear** because the moving catch skips the
   station reselect by construction (`and not dynamic_capture`) - so the arm never
   adopts a lane-1 fruit onto lane 0. Those events are **sort errors** in the
   ledger regardless of whether the attempt placed.
2. The 2 `sample swapped or recycled` notes are the same class, seen at the close
   after the reselect.

**Not adopted.** Flipping the direct default is a re-baseline (every direct/policy
number, the hybrid canary's primitive, and the stores' provenance), and 15 paired
episodes cannot carry it. The adoption price is the recorded WS-4.2 shape: N = 5
runs x 15 episodes per arm (~4x this batch, ~4-5 h at this wall), plus the canary
re-measure - because `accept_policy.sh` builds the direct presentation and would
inherit the flip.

**Read rule from here**: the direct lane's count is only comparable with
`FRUIT_SCORE_ENDPOINT` named and `FRUIT_DYNAMIC_PICK` named; the two arms differ by
the primitive, so their ticks are not a speed comparison either.
