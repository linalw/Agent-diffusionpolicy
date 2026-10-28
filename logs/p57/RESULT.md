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

---

# P57 phase 2: the interlock measured the wrong region

## The inversion

`_queue_depth()` counts the **station window** `[pick_y - 0.05, pick_y + 0.45]`.
With the dynamic catch, everything below the **0.399 m catch floor** is already
too close or past - and that is exactly what the window counts. So six bodies
"south" of the catch floor hold the release shut while the segment the selector
draws from (`[0.399, spawn_y 0.68]`, 0.281 m) is empty. The bed solved the same
problem with `_bed_stock_depth` (`logs/p32/60_probe_nocap.log`: the station check
blocked 1 due row in 3 and 8/10 selections found nothing); the single-file
schedules never got the equivalent.

The census names it (`logs/p57/cad_s77.log` attempt 3, 11 bodies on the belt):
**nine** at along -0.581..+0.068 (`below window ... floor`), **four** usable at
+0.464..+0.611 - i.e. the belt is crowded where it cannot be picked and thin
where it can.

## The change (`fruits.py` `e81051c1` -> `55921c46`, default off)

`FRUIT_SUPPLY_BAND_INTERLOCK=1` + `FRUIT_SUPPLY_BAND_MAX=3` (defaults off / 3):
the non-bed schedules pace on `_approach_depth()` (the selector's own approach
band, `FRUIT_SUPPLY_TARGET_FROM` = 0.35 -> `spawn_y`) with a **depth** ceiling
that preserves the linear density (3 / 0.58 m = 5.2/m), through two new helpers
`_interlock_depth()` / `_interlock_max()` used at both release sites. Bed
schedules keep `_bed_stock_depth`; with the knob off both helpers return the
shipped values, so the default path is byte-unchanged (selfcheck PASS, `211`
115 checks ok).

## Measured (seed 77, the same 15-pick continuous episode as phase 1)

| | cadence off (P56 `Q12`) | cadence on (P57 `cad_s77`) | **+ band interlock (`band_s77`)** |
|---|---|---|---|
| pump lag | +11.9..+15.7 s | -0.1..-1.6 s | **-0.5..-1.0 s** |
| `skipped` | 50 | 3 | **3** |
| `on_belt` | 5-6 (median) | 9-13 (median 12) | **8-10** |
| `admitted` (in the band) | 0-4 | - | **3-6** |
| `window` = 0 | 8/14 transitions | 2/16 | **1/16** |
| longest gap | 140 x14 / 230 | 230 | **110 (one)** |
| placed | 8/15 | 7/15 | **11/15** (right **10/10**, left 1/5) |

A 12-pick video run on the same settings (`logs/p57/video_band/`, 170 s
side-by-side) reads **9/12 (right 7/7, left 2/5)** with **no starvation gap**
(`[50, 80, 50, 50, 80, 110, 50, 50, 80, 50, 80, 66]`).

**Read it as a branch, not a rate.** The placed counts move with the fruit
sequence (the supply changes which fruit are presented); what the mechanism
endpoints say - and what the owner asked for - is that the belt is now
**continuously stocked in the segment that can be picked** (`admitted` 3-6, a
`window=0` in 1 of 16 selections instead of 8 of 14) and the release clock is
current. The right arm at 10/10 in the 15-pick run is a single draw of a
non-reproducible loop.

## What is still true

The catchable segment is **0.281 m**; a 15 s pick consumes **1.8 m**. The band
interlock can keep 2-3 bodies in it, and that is the ceiling of what supply alone
can do - a pick that starts at the wrong phase of the stream can still find
`window=0` (1/16). Enlarging the segment is the station-geometry lever P56 named.

## Defaults

Both new knobs are **off** (`FRUIT_FEED_CADENCE`, `FRUIT_SUPPLY_BAND_INTERLOCK`);
no `configs/` change. The adoption path is the pre-registered A/B (3 seeds, the
cadence-off control vs cadence + band, the endpoints `window>=1` share / longest
gap / `admitted` / no new reason, the placed count reported only).
