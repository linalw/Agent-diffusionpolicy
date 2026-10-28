# P57 phase 1: the wave was the feeder's scope gate, not the supply design

## The mechanism (measured)

`FruitSpawner.update` is the **only** place the release schedule advances, and on
the policy line it ran in exactly two places: the reset's target-selection loop
and (since P55) `SortingRLEnv.advance`, i.e. **only inside the policy phase**.
The primitive phase - the scripted catch/carry/place, ~12-13 s of a ~15 s pick -
never pumped it, so:

* `_next_release` fell **12-16 s behind** the clock during every pick;
* the pump's late backlog was placed at its *virtual* position
  (`spawn_y - late*speed`) and every slot whose virtual position had already
  passed the station was **skipped** (`logs/p56/p3/Q12_s77.log`: `lag=+15.72`,
  `skipped` 2 -> **50** over 15 picks);
* so the fruit entered the belt in **one burst per policy phase** - the owner's
  "一波一波 / 定时刷新".

The feeder had a mid-attempt pump all along (`FRUIT_FEED_CADENCE=1` ->
`Task._feed_tick` on **every control tick of every attempt phase**), but it was
armed through `_prepared_scope()`, which returns False when `not scripted`. That
is right for the *pre-pose/return* levers (a `reset()` throws a pre-positioned
hand away) and wrong for the *feeder*: a supply clock has no such conflict. The
direct line therefore never pumped during the primitive phase.

## The change (`tasks.py` `b6de439c` -> `c7eef701`, default-off path inert)

`_feed_on` now resolves through a new `_feed_scope()` = `self._active_session is
None` (every single-arm path, scripted **and** direct; a `CoopSession` installs
its own `feed_pump`, so the two-line stays excluded). `_prepared_on` keeps
`_prepared_scope(scripted)`. With `FRUIT_FEED_CADENCE` unset - the shipped
default - the expression is `0 and ...` in both trees, so every existing
configuration is byte-unchanged.

## The measurement (seed 77, the same 15-pick continuous episode, `FRUIT_DIRECT_FEED=1`)

| | cadence off (`logs/p56/p3/Q12_s77.log`) | cadence on (`logs/p57/cad_s77.log`) |
|---|---|---|
| pump lag at the selection | **+11.9 .. +15.7 s** | **-0.11 .. -1.64 s** |
| `skipped` slots (cumulative) | 2 -> **50** | 2 -> **3** |
| `on_belt` at the selection | 1-14, median **5-6** | **9-13, median 12** |
| `window` (usable) = 0 | **8/14 transitions** | **2/16 selections** |
| gap classes (ticks) | [50, 80x9, 110x4] | [50x4, 80x8, 82, 110x2, 230] |
| placed | 8/15 (right 8/9, left 0/6) | 7/15 (right **7/7**, left 0/8) |

The belt is **continuously stocked** now (`on_belt` 9-13 with the same patch
sheet and the same pool), which is exactly what the owner asked for. The placed
counts are **different branches** and are not a rate comparison (AGENTS §2); the
left arm's 0/8 and 0/6 are the closed grip/`cnp` class (P42 `SIM_LIMIT.md`).

## What this does NOT do

It does not enlarge the **catchable band** (~0.15 m between the 0.399 m floor and
the window's upstream edge). A stock of 12 over ~0.9 m still leaves 2-3 in that
band, so a selection can still read `window=0` (2/16 here). The remaining term is
the same geometry P56 named; the supply clock is now correct.

## Scope / next

Default off (`FRUIT_FEED_CADENCE`), no `configs/` change. The own A/B that would
adopt it (cadence off vs on, the same seeds, the endpoint = `window>=2` share and
the `lag`/`skipped` census, the placed count reported only) was not spent here:
phase 1 is the mechanism + the 15-pick read. `tasks.py` `c7eef701`;
`rl_env.py` `TASKS_MD5` metadata-only follow.
