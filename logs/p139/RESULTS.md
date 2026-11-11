# P139 - the direct loop's dominant failure key names the wrong event

## 1. What the note actually reports

`SortingRLEnv._episode_events` ends an episode with **`fruit fell off the line`**
when the *selected fruit's* centre is more than **0.25 m below the belt top**
(`z < belt_top - 0.25`, `rl_env.py`). The A/B's cells read it on 14-15 of 15
episodes, so a one-row instrument (`FRUIT_FALL_DIAG=1`, default off) printed the
position at the event:

| episode | fruit | position at the event |
|---|---|---|
| 0 | idx 1 | `(+63.000, -0.000, -50.000)` |
| 1 | idx 12 | `(+96.000, +0.000, -50.000)` |
| 2 | idx 7 | `(+81.000, +0.000, -50.000)` |

`(60 + 3*index, 0, -50)` is **`fruits.FruitSpawner.park`'s own slot** ("each fruit
gets its own far-away slot: parking several bodies at the same point makes them
interpenetrate"). So the episode ended because the **feeder recycled the fruit** -
`held=False`, `attached=False` - not because anything fell.

**This is a reporting defect, and it is load-bearing**: the record's direct
ledgers, the "no new reason" gates and P38's `fruit fell off the line` census
(the 0.06 % class) all read that string. On the direct path it is mostly the
parked pose.

## 2. Why the fruit was recycled

The selected fruit rides the belt while the attempt runs; the direct episode lasts
up to 1500 ticks (12.5 s) and the belt moves ~1.5 m in that time, so a fruit that
is not closed on is carried to the end and recycled. That is the *consequence* of
no grasp, not an independent event.

## 3. The discriminating cells (all at the trained camera 240,424)

| cell | n | result | note |
|---|---|---|---|
| `moe_v13s`, shipped direct config | 15 | **0/15** | 14 `fell off` (parked) |
| + `FRUIT_TRACK=0 FRUIT_SELECT_LIVE_SPEED=0` | 15 | **0/15** | not P136/P137 |
| + `FRUIT_SUPPLY_PATCH=1` | 9 | 0 | not the supply |
| + pre-P58 restores | 3 | 0/3 | not the P58 profile |
| `FRUIT_ARM_PARK=ready` | 3 | 1/3 | one episode, not evidence |

**So the direct loop reads ~0/15 where P54/P59 recorded 75 %/57.8 %**, with the
camera at the trained resolution and with every documented restore applied. The
cause is **not identified** in this phase; what is identified is that the
dominant *key* is a recycle, and that the policy never closes.

## 4. The fix shipped (opt-in) and the one owed

`FRUIT_FALL_PARKED=1` (default off): a **parked** sample no longer ends the
episode on the "fell off" note - the episode is left to its horizon. It changes
the failure-reason ledger, so it is its own cell and was not armed in any
measurement here.

**Owed**: the direct interface's regression diagnosis. The instrument is the row
above plus the `[rl] episode N: ... decision= ticks=` line; the next thing to
read is *where* the close stops - the trigger's fire tick, the close's span and
the pad-to-fruit distance at the close, on one episode at 240,424.

## 5. Correction: the A/B was invalid, and it is *my* harness error

The cells in section 3 were run **without `FRUIT_POLICY_TRIGGER`**, which
`TriggerSettings.from_env` defaults to **`off`** (`policy/trigger.py:146`). With
the trigger off, `should_fire` returns False on every tick, so `_run_primitive`
is never entered, the arm never leaves `ready`, and the episode burns to its
horizon while the belt carries the fruit to the recycle. The evidence is in the
rows: **no `[motion]` legs at all**, `refusals=0 policy_close_seen=0`, and - the
tell I missed - **no `[rl] trigger=...` row**, which `rl_env` prints only when the
trigger is enabled (`rl_env.py:2698`).

With `FRUIT_POLICY_TRIGGER=arrival` the row appears
(`trigger=arrival ... acq=on`) and the primitive **does** run. So:

* **P138's "the direct interface is blocked / reads 0/15 against P59's 57.8 %" is
  withdrawn** - the 0/15 was a loop that never fired. `112_rl_ab.sh` mentions the
  trigger only in a comment (`:34`), and the demo (`130_policy_demo.sh:92`) is the
  only script that sets it.
* The direct A/B still needs the trigger in `AB_EXTRA_ENV`; that is a one-line
  change to the driver, and the A/B itself remains unrun.

**What the armed run then showed** is a second, real defect: the trigger fires,
`FRUIT_STATION_RESELECT` adopts the *presented* fruit, and by the close that
sample's body is at the **park slot** (`openarm fingertips 102976 mm from the
fruit; closing anyway`) while `sample.parked` reads **False** - so a `parked`
guard at the reselect (added here) does not catch it. The desync is between
`FruitSample.parked` and the rigid body: `release` writes the pose and clears the
flag together, so the body moved to the slot *without* the flag being set, i.e.
through `park()` - which does set it - or through a path that moves bodies
wholesale.

**The next instrument** is one episode with `FRUIT_POLICY_TRIGGER=arrival
FRUIT_STATION_RESELECT=0` (no adoption): if the close then lands on the selected
fruit, the reselect is the path; if not, the recycle happens under the attempt and
`protect`/`held` is the term.

## 6. With the trigger armed and the reselect off, the direct lane names its own blocker

One cell, 2 episodes, seed 77, `FRUIT_POLICY_TRIGGER=arrival
FRUIT_STATION_RESELECT=0 FRUIT_FALL_DIAG=1`:

| episode | ticks | notes |
|---|---|---|
| 0 | 1746 | `intercept trigger (dy=26.3cm, dx=-11.6cm, t_arrive=...)` |
| 1 | 3628 | `intercept trigger (dy=30.6cm, dx=-8.2cm, t_arrive=...)` |

and, for the first time in this phase, the primitive **runs with a sane pose**:
`[task] openarm fingertips 59 mm from the fruit; closing anyway`.

So with the trigger armed the park-slot rows disappear and the failure becomes a
**named trigger refusal**: at the last evaluated tick the fruit is **8-12 cm
laterally** off the station (`dx`) and 26-31 cm upstream (`dy`) - i.e. **the
acquisition geometry**, the class the record already names (P32/P48/P49: the
delivered-x tail; `|dx|` at the fire 0.06-0.12 m against the 0.16 m gate). The
record's own lever for it is **P50's release-offset compensation** (opt-in,
per-pool tables), which took the isolated tail 8/96 -> 0/96 cells and was blocked
only by an underpowered count gate.

**So the direct lane's chain is now:**
1. harness: the trigger must be armed (`FRUIT_POLICY_TRIGGER=arrival`) - **fixed in
   this phase's understanding; P138's "blocked" withdrawn**;
2. the station reselect can adopt a **parked** fruit (body at the pad slot while
   `parked` is False) - the reselect now refuses a `parked` sample, which does not
   catch the desync, and `FRUIT_STATION_RESELECT=0` sidesteps it;
3. the remaining refusal is **acquisition geometry** (`dx` 8-12 cm at the fire),
   whose record lever is P50.

**No rate is claimed** (2 episodes, one seed), and the A/B remains unrun - but it
now has a stated precondition (1) and a candidate for (3).

## 7. The `dx` quantified: it is not the blocker

The full refusal note carries every term, and it settles the question:

```
intercept trigger (dy=26.3cm, dx=-11.6cm, t_arrive=2.19s, speed=0.120m/s/encoder,
                   frame=station, finger=0.0202, lead=2.20s/reach=0.31)
fruit left the pick station during the close (85392 mm)
```

| term | value | gate | verdict |
|---|---|---|---|
| `t_arrive` | **2.19 s** | `lead 2.20 s` | **passes** (by 10 ms) |
| `dy` | 26.3 cm | `reach 31 cm` | passes |
| `dx` | **-11.6 cm** | `lateral 16 cm` | passes |
| `finger` | 0.020 | 0.030 | passes |

So **`dx` is in range and is not the refusal**: it is the *band* (x 0.20-0.36
against the station's 0.34), i.e. the record's delivered-x, and the trigger's
lateral gate was calibrated to admit exactly that. **P50's release-offset
compensation is therefore not indicated** - the trigger is not refusing on the
lateral term.

The blocker is the **second note**: `fruit left the pick station during the close
(85392 mm)` - the sample's body is in the **park slot** while the close runs, so
the attempt was already lost before the drift check.

## 8. One more real defect: the despawn sweep ignores `protected`

`FruitSpawner.scan_despawn` skipped `sample.parked or sample.held` and **not**
`is_protected(sample)`, while `_pick_recyclable`'s own docstring says "held,
protected, or output-line fruit are never taken". So an in-flight sample that
crosses `despawn_y` **is parked mid-attempt**, and every reader downstream sees
the park slot. The term is added (`fruits.py`); `211` stays **ok (115 checks)**
and `selfcheck` **PASS**.

**It is not sufficient on its own**: with the term the same 2-episode cell still
reports `fingertips 101584 mm` and `[belt] recirculating lychee (index 13):
waited 60s at the gate`, so at least one more path moves a body to the slot (or the
sample handed to the close is not the protected one). The instrument for the next
step is a one-row `[sample]` print at the close entry: `sample.index`,
`sample.parked`, `spawner.protected`, `is_protected(sample)`, and the body's
position.

## 9. The `[sample]` row: the close is handed a **parked** sample while the attempt protects another

One row, printed where the handover is decided (`FRUIT_SAMPLE_DIAG=1`, default off):

```
[sample] arm=left idx=9 parked=True held=True attached=False
         protected=1 is_protected=False pos=(+87.000,+0.000,-78.745) task_sample=None
```

Read it term by term:

* **`idx=9` but `protected=1`** - the attempt owns index 1 and the task is closing
  on index **9**: the sample was **swapped** (the station reselect adopts the
  presented fruit; `held=True` is the reselect's own write).
* **`parked=True`** and the body at **x = 87 = 60 + 3*9** - the park slot - with
  `z = -78.7` instead of `-50`: the body was **parked and then fell freely** (the
  slot is in mid-air, nothing supports it). So the park happened some time before.
* **`is_protected=False`**, `attached=False`, `task_sample=None` (the env does not
  set `current_sample` on this path).

So the chain is: the trigger hands over -> the reselect adopts the **presented**
fruit (index 9) -> that fruit is **parked** before the close -> the close runs on
the park slot -> the drift check reports 85 m and the episode ends.

**The remaining `park()` caller that can take a `held=True` sample is
`spawner.reset()`**, which parks *every* sample unconditionally. The feeder's other
two routes are excluded by the code itself (`_pick_recyclable`: "held, protected,
or output-line fruit are never taken"; `scan_despawn`: skips `parked`/`held`/now
`protected`). That points at a **reset interleaving with an in-flight attempt**
(the direct env's episode boundary versus the primitive), which is the next thing
to read - one row in `spawner.reset()` naming how many samples it parked and
whether any was `held`/`protected`.

**The guard this row justifies** (not built here): at the handover, if
`sample.parked` - or `not is_protected(sample)` while the attempt's `protected` is
a different index - **abort the attempt** instead of closing. A close on the park
slot costs the whole episode and yields a 100 m chase that the drift check then
labels as a station escape.

## 10. The reset is cleared, the guard works, and the direct lane **places** - the rate is a scoring term

One cell, 2 episodes, seed 77, `FRUIT_POLICY_TRIGGER=arrival FRUIT_SAMPLE_DIAG=1
FRUIT_FALL_DIAG=1`, with the two new terms (the `[reset]` row and the handover
guard):

**`[reset] parking 16 sample(s): held=[] protected=[]`** - at the reset no sample
was `held` or `protected`, so `spawner.reset()` is **not** the thief; the swap+park
happens inside the attempt (the reselect adopts the presented fruit and that fruit
is parked before the close).

**The guard fires and the chase is gone**: episode 0 ends at **684 ticks** (against
1746) with `abort: the sample handed to the close is not the attempt's (idx=9
parked=True protected=1)` and the note `sample swapped or recycled before the
close` - a truthful end instead of a 100 m close.

**Episode 1 grasped AND placed** - the first placement in this whole
investigation: `grasped=True placed=True`, `place low: bottom 1462 -> 48 mm`, 2858
ticks. And it is still scored `success=False`, because

```
success = bool(self._lifted) and bool(self.cfg.on_output_belt(final))
```

with `_lifted = True` (the task grasped) and **`on_output_belt(final)` false**: the
fruit is placed (the task's own release says so, and `placed=True`) but at
`_finalize` it is not within `margin=0.06` of a lane - with `FRUIT_OUTPUT_RAILS=none`
(P71) nothing keeps it from rolling off the slab after the release.

So the direct lane's 0 rate decomposes into **four** terms, in the order they were
found: (1) the trigger default (harness), (2) the reselect adopting a parked
fruit (guard added), (3) the 100 m chase (same guard), (4) **the scoring term** -
`on_output_belt(final)` after a successful place. Only (4) is still open, and it is
a *scoring/geometry* term, not the policy.

**Note on the ledger**: the guard's `sample swapped or recycled before the close`
is a **new key** in the direct lane's failure-reason set (declared here; no rate is
claimed on it), and `intercept trigger (...)` is a **diagnostic note** that is
appended to every episode - it does not enter `success` (which is the `_lifted`
and `on_output_belt` pair) but it does enter the *reason* set.
