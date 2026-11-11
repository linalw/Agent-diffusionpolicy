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
