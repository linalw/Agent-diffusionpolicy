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

**So the direct lane's remaining term is the station reselect's timing, not the
park slot and not the metric.** The recorded sidestep is
`FRUIT_STATION_RESELECT=0` (close on the fruit the descent aimed at); the fix, if
it is wanted, is a reselect that is *decided before the descent* rather than
during the close. Neither is built here.

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
