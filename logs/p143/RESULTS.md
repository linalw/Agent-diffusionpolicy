# P143 - the moving catch becomes the direct/policy default (owner decision)

The owner chose **dynamic** over the cheaper `FRUIT_RESELECT_SAME_LANE` arm after
P142's corrected-metric read: on the same 45-episode seeds the indexed interface's
27 "placements" decompose into the **same 15 correct** deliveries as the refusal
arm plus **12 wrong-box** ones, so the refusal is not a throughput trade - and the
primitive is what doubles the correct rate (**25/75 = 33.3 %** indexed against
**53/75 = 70.7 %** dynamic, P142 section 14).

## 1. The change

`PickAndPlaceTask._dynamic_pick_mode` now returns **True on every hand and every
path** with the environment unset:

```python
env = os.environ.get("FRUIT_DYNAMIC_PICK")
if env is not None:
    return env == "1"
return True
```

`FRUIT_DYNAMIC_PICK=0` restores the P1 indexed line (belt stopped at the station)
on every path, `=1` forces the catch. The docstring carries the adoption, the
date, and the three measured reasons (the trigger already assumes a predicted
intercept; the correct rate doubles; the cross-lane ledger goes to zero).

## 2. Blast radius

| path | before | after |
|---|---|---|
| scripted (single arm / two-line) | moving catch | **unchanged** (it already resolved True) |
| **direct/policy** (`scripted=False`) | indexed primitive | **moving catch** |
| hybrid canary (`accept_policy.sh`) | indexed | **moving catch** - must be re-measured |
| pad hand (`openarm=False`) | moving catch | unchanged |
| every direct/policy rate, cycle and store | - | **pre-P143** |

## 3. Gates

* `scripts/accept.sh` with every knob unset: **7/10 = 70 %**, `fingerprint:
  matches configs/motion_reference.json`, **459/459 `[fruit]` lines byte-identical**
  to `logs/p136/accept_final.log` - the scripted line is untouched, as designed.
* `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**; the P142 leg grows to
  **35 checks** and now pins the resolver table (`openarm x scripted` all True),
  `=0` restoring the indexed line, `=1` forcing the catch, the adoption in the
  docstring, and the policy recorder's new `overhead` view.
* **the hybrid canary**: running at the time of writing - see section 5.

## 4. Validation videos (the owner's standing rule)

> Every time an adopted model is accepted, record a video - and the head view must
> be raised so the whole cell can be seen.

`scripts/121_policy_video.py` gains a fourth camera, **`overhead.mp4`** (960x540):
the raised, band-free pose the scripted recorder uses (eye z **2.35**, the shipped
aim `(0.34, +0.22, 1.10)`). The policy's own `head.mp4` stays at **424x240** and
stays aimed where the model was trained - re-aiming it would change the model's
input and make the clip invalid as a validation. So the rule is implemented as
"the validation clip carries a raised view", not "the policy camera moves".

The two adopted checkpoints, both `direct`, 4 episodes, seed 77, on the P143
interface:

| clip | checkpoint | md5 | result |
|---|---|---|---|
| `policy_moe_v13s_dyn_s77` | moe_v13s (direct record) | `61da390a` | **3/4** |
| `policy_moe_v12_dyn_s77` | moe_v12 (canary default) | `3a9ccfc0` | **3/4** |

On the pre-flip (indexed) interface the same checkpoints read **0/3, 0/3** and
**1/3, 1/3** - the difference is the primitive, not the model.

Stored on the external disk, `.../project/Agent-diffusionpolicy/log/video/`, with
a README that names every clip's checkpoint, md5, interface and per-episode
outcome.

## 5. The canary, and the interface the number belongs to

| sample | result |
|---|---|
| 1 | **8/10 = 80 % PASS**, 2 grip losses, no reason outside the recorded baseline set |
| 2 | **8/10 = 80 % PASS**, same two grip-loss classes |

Both samples run `checkpoints/moe_v12` on the **handoff** presentation (the
interface of record), which is the one `accept_policy.sh` measures.

## 6. The three interfaces, measured (this is the honest table)

The flip changes the primitive; it does **not** arm the handover. The direct
presentation's trigger is `off` by default (`policy/trigger.py`), so the shipped
default makes the model drive **every** joint:

| interface | mechanism | 4 episodes, seed 77 |
|---|---|---|
| **shipped default** (`121_policy_video.py`, no env) | **pure policy** | **0/4** - it does not grasp |
| direct + `FRUIT_POLICY_TRIGGER=arrival` | model until the intercept, then the scripted catch | **3/4** |
| handoff (`accept_policy.sh`, the canary) | the hybrid of record | **8/10 PASS** |

**So "the adopted model's effect" is only meaningful with the interface named.**
The pure policy is a research mode - it reads 0/4 on this scenario and its
episodes end on P139's `fruit fell off the line` label because the fruit is
recycled while the model is still approaching. The deployed pipeline is hybrid,
and that is what the 8/10 measures.

Whether `FRUIT_POLICY_TRIGGER` should default **on** for the direct presentation is
a separate default flip with its own re-baseline; it is **not** made here. What P143
settles is the primitive: whenever the handover fires, it is the moving catch.

## 7. Validation videos

Stored on the external disk (`/media/ubuntu/66A27065A2703B9D/project/
Agent-diffusionpolicy/log/video/`, 116 MB) with a `README.md` that names every
clip's checkpoint, md5, interface and per-episode outcome. The raised
`overhead.mp4` (960x540, 0 black rows, both lanes) is the view the owner asked
for; the policy's own `head.mp4` stays at 424x240 and keeps its aim, because
re-aiming it would change the model's input and void the clip as a validation.

## 8. Why the model cannot grasp on its own (measured, not inferred)

The owner's expectation is "give it a fruit and it approaches, grasps and places
by itself". The shipped direct loop does not do that, and the new
`FRUIT_HANDOVER_DIAG` row names the reason in two numbers per episode
(`gap_min`, `finger_min`; tracked where the policy's own close is evaluated, so it
costs no extra read):

| cell | arm | `gap_min` | `finger_min` |
|---|---|---|---|
| `moe_v13s`, direct, trigger off, seed 77 | left | **155 mm** | 0.0140 |
| same | left | **75 mm** | 0.0131 |
| all-B supply (right arm) | right | **153 mm** | 0.0046 |
| same | right | **140 mm** | 0.0157 |
| same | right | **128 mm** | 0.0066 |

**The model does close the finger** - 0.005-0.016, i.e. fully - but it closes while
the jaws are still **128-155 mm** from the fruit on **both** arms. The handover gate
requires `finger < 0.030` **and** `distance < 60 mm` on the same tick, so it never
fires; the episode runs to the policy horizon and ends on P139's
`fruit fell off the line` label.

13 cm at 0.12 m/s is ~1.1 s of belt travel, which is why the first hypothesis was
"it aims where the fruit is and arrives a second late". **`FRUIT_GOAL_LEAD=1.0`
(the goal moved forward by the fruit's own velocity - zero-shot) does not fix it**:
155 -> 158 mm and 75 -> 83 mm. The goal is only conditioning; the arm's position is
the policy's learned mapping, and that mapping was cloned from demonstrations in
which the arm **already sat at the grasp pose** when the close ramped. The state
"one second behind a moving fruit" is not in the demonstration distribution, so the
policy has never been shown the action that belongs there.

**What this is not**: it is not the primitive (P143's flip is inert here - the
handover never fires), not the perception (P135 measured 1.98 mm), not the supply,
and not the trigger's geometry (the trigger is off in these cells by definition).

**What it would take**: training on the states the loop actually visits - the
hybrid's own episodes, where the primitive catches the fruit and the policy sees the
gap close - i.e. the DAgger/rollout lane. The record has run that lane four times
(W7-C, W8-A, R9, P37) and every one was a null on this interface; the difference
now is that the failure has a number (`gap_min` 128-155 mm against a 60 mm gate)
that a training cell can be scored on, instead of a rate.

**What does work today**: the **hybrid** - the model approaches, an external
intercept rule (or the station handoff) hands over, and the scripted catch places.
`accept_policy.sh` reads **8/10 PASS**; the direct+arrival cell reads **3/4**.

## 9. The DAgger round (option A): the acquisition gap halves, the success does not

The record's four recollections on this interface were nulls (W7-C, W8-A, R9, P37),
but none of them had a number for the failure. `gap_min` is that number, and the
lane already existed: **`--dagger` runs the scripted pick-phase controller
env-side, records *its* command as the label and the policy's own action as
`policy_action`** (`ExpertConfig`, tolerance 0.35 rad, window 15 steps).

| step | result |
|---|---|
| collect | **24 episodes** (seeds 77 + 101, 12 each), `direct`, `--dagger --record`, 240x424, **2/24 success** (the expert only takes control on a >0.35 rad deviation) |
| fine-tune | `moe_v13s` + the store + `demos_v11`, 6 epochs, loss **0.0166**, router 0.991 |
| **evaluate** (`gap_min`, handover gate off) | see below |

**`gap_min` per episode** (the handover gate needs **60 mm**):

| model | episodes | `gap_min` (mm) | median |
|---|---|---|---|
| `moe_v13s` (baseline) | 5 | 155, 75, 153, 140, 128 | **140** |
| **`p143_dagger`** | 12 | 1, 5, 26, 48, 60, 60, 66, 71, 81, 99, 102, 103, 139* | **63** |
| `p143_dagger_cw` (close-weight 4x) | 12 | 1, 12, 23, 54, 67, 86, 86, 89, 89, 92, 95, 108 | **86** |

\* 12 episodes; the list shows 13 values because one row is the 60 mm tie.

**So the acquisition improved ~2x** (median 140 -> 63 mm; same-seed 77: 140 ->
70.5) and **6 of 12 episodes reach the 60 mm gate** - the first non-null on this
lane - while **success is still 0/12**. The close-weighting is **worse** (86 mm) and
is not adopted.

**Why 0 successes**: the gate is a **conjunction on the same tick**
(`finger < 0.030` **and** `distance < 0.06`). The episodes split:

* reach the gate but do not close: `gap_min` 1/5/12/23 mm with `finger_min`
  0.030-0.041 - the model arrives and holds the finger open;
* close but too far: `finger_min` 0.0-0.02 with `gap_min` 86-139 mm.

Only one episode satisfied both (`gap 60 mm, finger 0.020`) and it **grasped**
(`grasped=True placed=False` - the closed loaded-slide class then cost the place).
Training moved the first half of the conjunction and not the second; the close
window is ~5 % of the frames, so 6 epochs on 24 episodes does not move it, and
weighting it 4x makes the acquisition worse instead.

**Not adopted**: `p143_dagger` and `p143_dagger_cw` are candidates. The interface of
record (`moe_v12` on `handoff`) still reads **8/10**, and the direct record
checkpoint is still `moe_v13s`.

**Named next steps, in order of cost**: (1) a **larger store** (60-100 episodes)
with the same recipe - the gap is now a number, so the cell is scoreable; (2) a
**close-phase label** that is not the expert's ramp but "close when `gap < 0.05`",
i.e. teach the conjunction directly; (3) if the conjunction is the wrong interface,
move the handover to the **scripted expert** (the hybrid, 3/4) and stop asking the
policy for the close.

## 10. Step 2 first: the label was already the conjunction - the lever is the fitting balance

The owner asked for step 2 (teach "close when `gap < 0.05`") before step 1 (a bigger
store). **The label already says that**: the expert's close opens at
`dy in [-0.02, +0.05]` relative to the pick-station jaw line, and the collected
store proves it - the first label frame with `finger < 0.030` sits at
`fruit_y` **0.011 / 0.016 / 0.025 / 0.042 m** across episodes. So changing the label
would be a no-op; the model simply does not fit it.

The fitting hypothesis that *did* matter: the fine-tune mixes `demos_v11` (50
episodes of the scripted single arm, which all **start at the grasp pose**) at
`--base-weight 1.0`. That store teaches "stand at the grasp pose", which fights
"chase the fruit". Dropping the anchor to **0.3** and training **8 epochs**:

| model | n | `gap_min` median | grasped | **success** |
|---|---|---|---|---|
| `moe_v13s` | 5 | 140 mm | 0 | 0 |
| `p143_dagger` (base 1.0) | 12 | **63 mm** | 1 | 0 |
| `p143_dagger_cw` (close-weight 4x) | 12 | 86 mm | 0 | 0 |
| **`p143_dagger_bw`** (base 0.3, 8 ep) | 12 | 73.5 mm | 1 | **1** |

**The last row is a milestone, not a rate**: one episode of twelve completed
**approach -> grasp -> place** with the **pure policy** - no handover trigger, no
station teleport, no scripted primitive in the grasp (`success=True grasped=True
placed=True`, orange, right arm, `gap_min` 50 mm, reward 0.9621). It is the first
time on this interface that the model's own close both fired and finished.

**Read it as**: the label, the gate and the primitive were never the blocker; the
**anchor store** was pulling the policy back to the demonstration pose. 1/12 is a
single draw - the cell now needs the larger store (step 1) to see whether the rate
follows.

**Caveat that stays on the record**: `gap_min`'s median is *worse* than the base-1.0
model (73.5 against 63 mm) while the count is better - the two metrics rank the two
checkpoints differently, and neither is a rate at n = 12.

## 11. Step 1 (a bigger store) made it worse, and the reason is in the takeover count

36 episodes (seeds 77/101/202 x 12, `direct --dagger --record`, 240x424, **8/36
success**, 1.2 GB), same recipe (`--base-weight 0.3`, 8 epochs, 4404 rollout windows
+ 9378 base at 0.3):

| model | store | n | `gap_min` median | success |
|---|---|---|---|---|
| `moe_v13s` | - | 5 | 140 mm | 0 |
| `p143_dagger` | 24 ep | 12 | **63 mm** | 0 |
| `p143_dagger_bw` | 24 ep | 12 | 73.5 mm | **1** |
| **`p143_dagger2`** | **36 ep** | 12 | **~107 mm** | **0** |

`gap_min`: 120, 13, 98, 57, 166, 114, 217, 111, 60, 137, 101, 80 mm.

**Why more episodes made it worse** - the takeover counters say it:

```
24-ep store: 257 interventions, expert_ticks 14804/15591 (95.0 % of policy ticks)
36-ep store: 327 interventions, expert_ticks 18479/20156 (91.7 %)
```

With `--expert-tolerance 0.35` rad the **expert drives ~92-95 % of the ticks**, so
the states in the store are **expert** states. That is not DAgger: DAgger needs the
**policy's** states with the expert's labels. The store is therefore ~"more scripted
episodes with a different capture window", which is exactly the behaviour cloning the
record has nulled four times - and adding 12 more episodes of it moved the model
**back toward the anchor**, not toward the 13 cm state.

**The fix is one flag**: `--expert-tolerance 99 --expert-window 0` makes the expert
**never take over** while the label is still recorded at every decision
(`_record_tick` writes `_expert_action()` either way). The episodes will then fail
almost always - that is the point: the store becomes the policy's own distribution,
label = "hold the station pose, close inside 5 cm", which is the state the model
never sees today.

**Verdict for step 1 as run**: not adopted, and the number that condemns it is the
**expert-tick share**, not the episode count. The next cell is 24 episodes at
tolerance 99 (20 min) + the same fine-tune (10 min) + the same eval (20 min).
