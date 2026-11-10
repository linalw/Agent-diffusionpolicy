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
