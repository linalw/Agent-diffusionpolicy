# P57 DESIGN — the `CandidateBoard`: parallel candidate handling at the pick boundary

Phase 1 (offline). No simulator, no `src/` edit, no commit. Owner's ask: *a
module that handles the candidate fruit **in parallel with the pick**, so the
continuous line never waits.*

**Verdict in one paragraph.** The module is **buildable and cheap, and its
parallel form is a tick-wise planner, not a thread** - but the phase-1 census
says the thing worth parallelising is not the *selection* (its compute has never
even been isolated from noise) and not the *belt* (the module cannot create
supply: the catchable band holds **2-4 fruit** (0.281 m of geometry, ~0.15 m
of observed stock) while one 15 s pick traverses **1.80 m / ~15 fruit**, P56
addendum). What is worth parallelising is
the **feeder**: at 8 of the 8 starved pick boundaries the belt holds **no
usable candidate at all** and the live-fruit forecast is infinite - and it is
*structurally* infinite, because the belt runs -Y, so a fruit below the 0.399 m
floor is **leaving** the band and no live fruit ever enters it (`spawn_y` 0.68
is inside the band; the usable `along` max over the corpus is 675 mm). The
truth is one 30-tick round, its cause is a **pump backlog of 11.0-12.5 s**
(≈11 due rows at the patch period) that **one pump call** burns, and the
separator is exact on the corpus: pump lag **+11.01..+12.46 s at 8/8 starved
instants** vs **-1.32..-0.00 s at 15/15 successful picks** (23/23, an 11 s
margin). So the board's job is to forecast *the feeder* (the band has nothing
to forecast) and to census the band it already has, and the actuator it unlocks
is a **pump-before-decide** call plus a **park folded into the wait**.
Measured ceiling of the whole module on the P56 continuous arm: **240 ticks =
2.0 s = 0.83 % of the 239.6 s span** (gap mean 86.4 -> 69.3), against a 50-tick
per-transition floor that no module can remove (the calibrated `grasp` teleport
+ settle). Everything below the 0.83 % is a *measurement* contribution (the
forecast, the pre-decision, the `[board]` row), and that is how the PREREG should
spend it.

---

## 1. A — the selection path as it stands (quoted)

### 1.1 `select_target` — one synchronous pass over the live set

`src/fruit_sorting/tasks.py:5571-5922`. Per state, in this order (the diag row
records **the first predicate that refused it**):

| gate | line | refusal string in `[bed-sel]` |
|---|---|---|
| `exclude` (the other arm's in-flight fruit) | `:5680` | `excluded` |
| pure grade routing (two-line only) | `:5683` | `grade X != Y` |
| lane filter (bimanual only) | `:5691` | `other lane N` |
| `max_retries` | `:5699` | `diverted (max_retries)` |
| `z < belt_top - 0.02` (fell off) | `:5703` | `below belt z=...` |
| `diameter > gripper_max_object` | `:5706` | `too big ... m` |
| `|x - belt_center_x| > 0.30` (not the main belt) | `:5715` | `off belt x=... z=... (output conveyor or off the line)` |
| `z > belt_top + 0.12` (on an output belt / stacked) | `:5722` | `above belt z=... (output belt/stacked)` |
| station window `station_floor <= along <= pick_y + 0.18` | `:5775-5783` | `below window along=... floor=...` |
| upstream window `upstream_floor < along <= pick_y + 0.85` | `:5790` | `below window along=... floor=...` |
| **moving-catch floor** `along >= pick_y + _dynamic_select_floor()` | `:5821` | `below catch floor A < B` |
| else | `:5833` | `usable` / `chosen` |

The order matters for the board: a fruit is `usable` **iff** it passed every
gate *and* is at/above the floor, so `usable` is a strictly narrower set than
"alive". The single-arm rule then takes `self._balance_arm(usable)` ->
`ordered[-1][1]` on the moving-catch path (`:6013-6014`), i.e. **the
farthest-upstream floored fruit** - the list is sorted ascending by `along`
(`:5840`). `direct=True` (`rl_env.py:2345`, `:4948`) forces
`FRUIT_SELECT_NEAREST_ABOVE_FLOOR=0` (`:5881`), so the direct interface always
takes the farthest-upstream one.

### 1.2 The floor the path prices (`tasks.py:5959-5992`)

```
floor = _dynamic_pick_lead() + v * setup + margin
      =       0.189 m        + 0.12 * 1.5 + 0.03
      = 0.399 m                                   (printed in every block)
```
`_dynamic_pick_lead()` = `min(v*(overhead + t_desc + descend_margin) + margin,
0.80)` (`:6053-6074`) -> 0.189 m = **1.575 s** of belt travel; `setup` is
`FRUIT_DYNAMIC_SELECT_S` = 1.5 s = **180 ticks**; `margin` 0.03 m.
So the selector does not *wait* 1.5 s - it **refuses** any fruit that would need
less than 1.5 s of setting-up, and the catch's hover absorbs the surplus.

### 1.3 The direct env's call sites

| site | line | when | rounds |
|---|---|---|---|
| `reset` | `rl_env.py:2307-2356` | once per run/episode; **pumps 30 ticks first** (`for _ in range(30): advance(1); spawner.update(); enforce_transport()`), then selects | up to 40 |
| `_begin_next_pick` | `:4918-4989` | at every pick boundary of `FRUIT_DIRECT_CONTINUOUS`; selects **first**, waits only if it must (`for _ in range(30): advance(1)`) | up to 40 |
| `_reseed_step` | `:4199-4230` | P38 refuse/re-seed, default off | 4 scans/refusal |

Two facts fall out of that table and they decide the whole design:

1. **The reset pumps before it selects; the boundary does not.** The reset's
   round is `advance + spawner.update` x30, so its *first* selection already
   sees a burnt backlog. `_begin_next_pick` selects against the raw state and
   only pumps if that fails - which is exactly the measured 30-tick round.
2. **The round is quantised, not kinematic.** 30 control ticks = 0.25 s =
   **0.030 m** of belt travel. Nothing at 3 cm can make a fruit usable from
   below a 0.399 m floor. So the round's value is the *pump calls* it makes -
   and §2.2 derives that **one** call is enough (the loop burns the backlog and
   only counts *delivered* rows against `burst_max`, `fruits.py:2293-2320`), so
   the honest wait is **1-2 ticks**, not 30.

### 1.4 The `[bed-sel]` row (`tasks.py:5469-5518`)

Header (one per selection instant):

```
[bed-sel] attempt N t=<sim> live= on_belt= admitted= window= pick=<cat>@<along>
          pump_next= lag=+/- rebased= dropped= skipped= refused= placed=
```
- `window` = rows whose reason is `usable` or `chosen` - **the catchable set**;
- `admitted` also counts `below catch floor` (the ones the window floor let in
  but the moving-catch floor refused);
- `pick=none` is a starved instant; `pump_next`/`lag` are
  `spawner._next_release` and `now - _next_release`.

Per-row:

```
[bed-sel]   <category:10s> along=+0.000 x=0.000 z=0.000 r=0.000 grade=A -> <reason>
```
**The row does not print `index` or `dia`.** Both are in the `diag` dicts
(`:5647-5658`: `index`, `category`, `grade`, `along`, `x`, `z`, `dia`,
`reason`) - they are simply dropped by the print at `:5513-5518`, and `r` is
`0.5*dia`, not the diameter. So a board's `next_target()` cannot currently be
compared to the selector's `chosen` **by identity**: with a 16-fruit pool over 8
species, `category` + a 3-dp `along` is not a key. **The smallest diagnostic is
`index=` and `dia=` on that print line** (print-only, no control-loop read).

Second finding on the same line: `bed_diag_report`'s `on_belt` only excludes
the `off belt x=` reason (`:5487`), so a fruit that fell off the line
(`below belt z=0.02`) is counted as stock. Recomputing it against the selector's
own z gates (`logs/p57/cand_census.py::belt_candidate`) changes the number on
**8 of B_1's 23 blocks** and **9 of Q12's 24** - precisely at the starved
instants, and it moves the median **6 -> 5** (B) and **6 -> 4** (Q12). The P56
P3 endpoint (`on_belt` median 5 vs 6) is therefore a *generous* stock reading.

### 1.5 The trigger's arrival model (`policy/trigger.py`)

`should_fire` already contains the board's per-fruit clock:

```
t_arrive = max(dy, 0.0) / speed        # :339-340, dy = fruit_y - reference_y
if t_arrive > lead: return False       # :341-342
```

with `lead` from `acquisition_window` (`:225-251`): the fixed 0.90 s, or with
`FRUIT_POLICY_TRIGGER_ACQ` (the direct default since P54) `lead + 0.60 +
|jaw-station|/0.20` capped at 4.50 s. Measured in B_1: `t_arrive` **1.95-2.17 s**
at the fire tick, `dy` **0.233-0.260 m**, `lead` **1.96-2.18 s** - the model and
the measurement agree to a few ms because both are `dy/v`.

That is the same arithmetic the board's `t_enter`/`t_feed` model uses, one layer
earlier and for a different reference: the trigger asks "will *this* fruit reach
the jaw line inside the lead?", the board asks "is *any* fruit past the floor
now, and if not when does the feeder land one?" - and for the second question
`dy/v` is **not** applicable (§2.1: a fruit below the floor recedes). The
trigger's model therefore contributes exactly one thing to the design: the
confirmation that `dy/v` is the right clock for a fruit approaching a
*stationary* line. The board has no such fruit, so its clock is the feeder's
due time instead (§2.2) - and the trigger's numbers are quoted here only to show
that the two layers agree on `v = 0.120 m/s` (encoder, `0.120m/s/encoder` in
every note).

### 1.6 The reach map and the arm rule

- `logs/r10/reach_intercept_{left,right}.json` (33 rows/arm): per measured
  lateral column `x in {0.20, 0.28, 0.36}` the along-belt offsets `dy` whose
  grip residual is `<= 6 mm`:

  | arm | x = 0.20 | x = 0.28 | x = 0.36 |
  |---|---|---|---|
  | left | -0.10..+0.15 | -0.05..+0.10 | 0.00..+0.10 |
  | right | -0.10..+0.10 | -0.10..+0.05 | -0.10..0.00 |

  The bands **nest** (AGENTS §1 "R10-A"), so a fruit between columns takes the
  next column's band; every cell contains `dy = 0`, so at the shipped station the
  **lateral** membership is the only discriminator. The clean lateral band from
  the `174` probe is `x = 0.18-0.39` with a hard cliff at 0.42.
- The arm is decided by the grade: `bin_index = 0 if grade == "A" else 1`,
  `active = "left" if bin_index == 0 else "right"` (`rl_env.py:2391-2392`), so
  **A -> left, B and C -> right** and the balanced patch mix (A:B:C
  0.375/0.375/0.25) offers the right arm 62.5 % of the picks (B_1: left 6,
  right 9 of 15).

---

## 2. B — the candidate census (measured, `logs/p57/cand_census.txt`)

Corpus: the three logs that carry `[bed-sel]` blocks - `logs/p56/p2/A_1.log`
(15 picks / 15 episodes, no boundary wait), `logs/p56/p2/B_1.log` (15 picks in
one episode, **23 selection instants** = 15 picks + 8 starvation rounds),
`logs/p56/p3/Q12_s77.log` (the `FRUIT_QUEUE_MAX=12` addendum, 24 instants).
Belt **0.12 m/s along -Y** (`cleated belt built: ... surface velocity -0.12
m/s`), tick 1/120 s, catch floor **0.399 m** (printed), pump floor
`pick_y + 0.10` (`fruits.py:2247`), `spawn_y +0.68`, `despawn_y -0.70`.

### 2.1 The direction, which decides the whole model

The belt carries fruit **downstream** (along decreases), and a release is
placed at `along = spawn_y - min(late*v, 1.60)` (`fruits.py:2315`) - i.e. at the
position it *would have reached*. The band is therefore a **window on a moving
stream**:

| fruit | `t_enter` (ticks to become usable) |
|---|---|
| `along >= 0.399` (at/above the floor) | **0** - usable now |
| `along < 0.399` | **infinite** - it is *leaving* the band (it will be at the station, then off the end) |
| not yet released | the feeder clock (2.2) |

And nothing is ever upstream of the band: the window's upstream edge is
`pick_y + 0.85 = 0.85` while `spawn_y = 0.68`, and the measured usable `along`
maxima are **p50 574 mm / max 675 mm** over the corpus. So **no live fruit can
ever enter the band** - fruit enter it only at release, and leave it at the
floor. That is why the first pass of this census (which read `t = (floor -
along)/v`) was wrong in sign, and why the correction is the phase's first
result.

| log | blocks | on-belt candidates | usable (`along >= floor`) | leaving (`t_enter = inf`) |
|---|---|---|---|---|
| A | 15 | p50 6 (3-8) | p50 2 (1-4) | p50 3 |
| B | 23 | p50 5 (0-7) | **p50 1** (0-3); **at the 8 rounds: 0 every time** | p50 3 |
| Q12 | 24 | p50 4 (0-13) | p50 1 (0-4); at the 9 rounds: 0 | p50 3 |

So the **candidate set** at a boundary is 0-7 belt rows of which 1-3 are usable
(B's `window` distribution: {1: 4, 2: 8, 3: 3}), and the usable along-span is
**median 20 mm** when there are two (A: 160 mm) - the band is one or two deep.

### 2.2 The only finite arrival is the feeder

`[bed-sel]`'s header carries the feeder's clock and splits the corpus perfectly:

| instant class | n | `lag = now - _next_release` | `max(0,-lag)*120 + 1` |
|---|---|---|---|
| successful pick | 15 | **-1.32 .. -0.00 s** | p50 **98**, max 159 ticks (the next top-up) |
| starved round | 8 | **+11.01 .. +12.46 s** | **1 tick**, all 8 |

23/23 with an 11 s gap between the classes. The mechanism, from the pump loop
(`fruits.py:2293-2320`) plus the log:

1. 30 ticks after a starved instant the belt holds **6 new rows at along
   0.069..0.672** (t=145.36 -> 145.61). That is a **burst, not travel**: 30
   ticks move the belt 3 cm, and the row positions are exactly `0.68 - late*v`
   for latenesses of 0.07/1.7/3.5/5.1 s. `[bed-fall]` rows in the same round
   show the 6 fruit that had fallen off the end being recycled, so the round is
   `spawner.update` doing a **detect-falls + burn-backlog** pass.
2. **One call suffices**: the loop `continue`s on a skipped row without
   consuming the `burst_max = 6` budget (`fruits.py:659`), so a single call
   burns the whole ≈11-row backlog - it delivered 6 (`supply_skipped +5` in the
   same pair, `on_belt` 0 -> 6).
3. Only the **tail** of the burst is usable: the rows land across
   `[0.10, 0.672]` (the pump's own floor is `pick_y+0.10`, so a row below that
   is skipped), i.e. **2-3 of the 6** cleared the 0.399 m catch floor. Measured
   B_1: `window=3` right after the round.

**This is the finding the module must be built on: the boundary wait is a
*feeder* event with 1-call granularity (predicted wait **1 tick**), measured
through a 30-tick window - so the module's job at a starved boundary is not to
"see further up the belt" (there is nothing up the belt) but to know that the
pump is owed a call and to make that call before deciding.**

### 2.3 The pre-decision question

Was the next pick's target already on the belt one transition earlier? Project
the chosen fruit back by `v*dt` (dt ≈ 16.6 s -> **1.99 m**) and look for it in
the previous block: **0/14 in all three logs** - and structurally so, because
1.99 m of projection against a **1.38 m** belt (`spawn_y` 0.68 to `despawn_y`
-0.70) means the next target *cannot* be on the line yet. So a pre-decision
drawn from the live set is impossible by geometry, and the only look-ahead left
is the **release plan**:

- **knowable** (read-only, no RNG consumption): the next release's due time
  (`spawner._next_release`), its **grade** and radius (`samples[_cursor % n]`,
  the pool order is shuffled once at build, `fruits.py:978-986, 1543`), the arm
  from that grade, the backlog `lag / _release_period()`, and `burst_max`;
- **not knowable**: the release's lateral `x` (drawn at release), the release
  times beyond the next one (each gap is drawn per release), and the physics
  settle (P38's per-instance offset, -36..+69 mm).

That is exactly enough for the two things the module needs: **which arm** the
next pick will use, and **whether the pump is owed a call before the selection**.

### 2.4 The tree already carries a candidate for the *cause* (not this phase's edit)

While this phase was being written the working tree gained an **uncommitted,
P57-labelled change that this phase did not author**: `tasks.py` `b6de439c ->
c7eef701` adds `_feed_scope()` and widens `FRUIT_FEED_CADENCE` from
`_prepared_scope(scripted)` to every single-arm path (`rl_env.py`'s
`TASKS_MD5` follows to `c7eef701`; HEAD is `6f58c32`). That knob - already
implemented, default **off** - pumps the feeder on the primitive's own ticks,
which is the *cause-level* fix for §2.2: with `_feed_on` the pump runs through
the close/carry/place phase (line 2379-2380), so the schedule never falls 11-12 s
behind and the boundary selection finds a stocked band.

This matters for the phase's reading, and it is why the PREREG's first arm is
**F** (`FRUIT_FEED_CADENCE=1`) rather than the board:

- if F removes the starvation rounds, **the boundary wait was a pumping-scope
  artifact**, the board's A1 actuator is redundant, and the module's remaining
  value is the forecast + the pre-decision (its measurement contribution) - which
  is still worth exactly what §3.6 says and no rate;
- if F does not remove them, the backlog has a second cause and §2.2's one-call
  burst model is the thing to test with A1/B1.

The phase-1 census was measured on the P56 logs, i.e. **before** this edit, and
its numbers describe the shipped default (cadence off). Nothing here endorses or
reviews the in-flight change; it is recorded because a phase-2 read that ignored
it would attribute F's effect to the board.

## 3. C — the module

### 3.1 `CandidateBoard` (pure Python, no Isaac, no USD)

```
CandidateBoard(
    floor: float,            # pick_y + _dynamic_select_floor()   [m]
    station: tuple[float, float],   # (x, y) of _trigger_station - a CACHED pair
    speed: float,            # _belt_speed_estimate() (signed, encoder when live)
    r10: dict[str, dict[float, tuple[float, float]]],   # from the JSON
    spawn_y: float, despawn_y: float, period: float, burst_max: int,
)
board.refresh(now, states, lag, release_grade, release_r)   # one snapshot
board.rows() -> list[Row]                                    # per fruit
board.next_target(now) -> Row | None
board.forecast_starvation(now, horizon_s) -> Forecast
```

`Row` (frozen dataclass, all SI):

| field | derivation |
|---|---|
| `index`, `grade`, `r`, `along`, `x`, `z` | from `spawner.state()` |
| `arm` | `"left" if grade == "A" else "right"` (the env's own rule) |
| `on_line` | the selector's z / x / diameter gates (see 3.3 - **shared**, not copied) |
| `usable` | `along >= floor` and every §1.1 gate passed - the selector's `usable` |
| `t_enter` | **`0`** if `usable`, else **`inf`** (§2.1: a fruit below the floor is leaving the band; the belt runs -Y) |
| `reachable` | `x in [0.18, 0.39]` **and** `dy = along - pick_y` inside the R10 column band for that `x` (`logs/r10/...json`). `dy` is the *current* offset, not a predicted intercept, because the intercept is the station line at the shipped station - and `dy = 0` is in every R10 cell, so here it reduces to the lateral test |
| `rank` | `(not usable, not reachable, -along)` - the shipped farthest-upstream order among the usable ones, `None` when the set is empty |

`forecast_starvation(now, horizon_s)` returns
`(verdict, t_next_usable_ticks, source, conf)`:

1. **band term**: `0` if any `usable & reachable` row exists, else `inf`
   (there is no growing set to look forward to - §2.1);
2. **feeder term**: `t_feed = ceil(max(0, -lag) / TICK) + 1` ticks - the due
   time of the next release plus the one pump call that lands it. When the
   pump is overdue (`lag > 0`) that is **1 tick**, and the call burns the whole
   backlog and delivers `<= burst_max` rows at `0.68 - late*v`
   (`fruits.py:2293-2320`). `source = "feed-blocked"`, `t_feed = inf`, when
   `n_due > 0` but no free pool sample exists (`_pick_recyclable` would return
   `None`; the board can only *count* free samples, never call it - it mutates
   `_cursor`);
3. `t_next_usable = min(band, feed)`; `verdict = "usable now" | "wait k ticks" |
   "no supply in horizon"`; `source ∈ {band, feed, feed-blocked, none}`;
   `conf = "exact"` for the feeder term (a pure function of `_next_release`,
   `period` and the free-sample count), `"model"` for the *landing point* of the
   burst (its `along` depends on the lateness of each burnt row, and its `x` is
   drawn at release, so **how many** of the delivered rows clear the floor is
   the model part - measured 2-3 of 6, §2.2).

**`conf` is the honest part**: the feeder term is deterministic arithmetic on
the spawner's own clock, while the band term is a straight-line model of a
physics transport whose lateral offset is a measured per-instance constant. The
board must never report them as the same kind of number.

### 3.2 The "parallel" form: **(ii) a tick-wise incremental planner**, not a thread

**Recommendation: (ii).** Reasons, in order of weight:

1. **Nothing to hide.** The board is O(<= 16 fruit) arithmetic - tens of µs
   against a 15 s pick (1.3e-6). Measured context: the whole decision loop's
   non-policy/non-render/non-camera bucket is 10.7 % of wall and **84 % of the
   loop is the scripted primitive + physics stepping** (P43 L2, `logs/p43/`).
   A thread cannot pay for its own handoff, let alone its lock.
2. **The reads it needs are the safe class, and a thread would break that.**
   AGENTS §2: per-tick *articulation link* reads shift a run by 3-14 s of sim
   time and one or two picks; **fruit-pose reads, camera reads and pure
   reporting do not**. `spawner.state()` is a fruit-pose read (safe). But a board
   that validated the hover pose, or a reach-anywhere intercept, against the
   **live arm** would need `arm.jaw_centre()` (or the link poses) per refresh -
   exactly the unsafe class. The design therefore takes the station from
   `_trigger_station` (**cached once** at the grasp teleport, `rl_env.py:2478`),
   the reachability from the static R10 table, and never touches the
   articulation from the board. A worker thread would have to read USD to do anything useful, and
   this tree has never done an off-thread `get_world_pose`: its only cross-thread
   machinery is `bimanual.py`'s **main-thread arbiter + `TickRelay` + a single
   run permit**, built precisely so that no worker ever touches the stage
   concurrently.
3. **Determinism.** Every measurement in this repo is read on byte-identical
   replays. A thread's interleaving is wall-clock dependent; a tick-wise planner
   is a pure function of `(tick, snapshot)` and replays bit-for-bit.
4. **The staleness question has a cheap answer without a thread.** A
   double-buffered snapshot only exists because a consumer runs concurrently;
   with a tick-wise planner the buffer *is* the tick's own state, and staleness
   is bounded by construction: `refresh()` runs once per control tick (or every
   4th tick, matching the observation cadence) and visits at most `look = 4`
   candidates round-robin, so the whole board is <= `ceil(16/4) = 4` ticks old.

**How staleness is validated at use** (the part that must not be assumed):
every `next_target()` result carries `(stamp_tick, index, along_at_stamp)`.
Immediately before the pick starts, the caller re-checks it against the live
state: the same `index` exists, `|along_now - (along_at_stamp + v*dt)| <= 0.01 m`,
and it is still `on_line` and above the floor. On any mismatch the caller falls
back to the **synchronous** `select_target` (the shipped path) and the `[board]`
row records `stale=1`. So the board can only ever *save* the setup, never change
which fruit is picked - unless the shared classifier says so (3.3).

### 3.3 One predicate source (the anti-drift rule)

The board must not re-implement §1.1's gates: a second implementation is a silent
divergence generator, and the phase's own endpoint (board vs selector agreement)
would then measure the two implementations rather than the plan. The design
therefore extracts `select_target`'s per-state classification into one pure
function

```
classify(state, *, pick_y, floor, station_y, cfg, failures, max_retries,
         exclude, lane, prefer_lane, pure_grade) -> (verdict, along)
```
returning the same `(verdict, along)` the selector already computes, with
`select_target` calling it (byte-identical: same order, same strings) and the
board calling it per row. With that, `board.next_target()` and
`select_target()` **cannot** disagree on a fresh snapshot, and the registered
"disagreement rate" endpoint measures **staleness only** - a much sharper test.

### 3.4 Where it plugs in

| # | site | change | default |
|---|---|---|---|
| 1 | `rl_env._begin_next_pick` (`:4946`) | `board.refresh(...)` + **`spawner.update(now)` before the first `select_target`** (the pump-before-decide actuator; the reset already does this) | off (`FRUIT_DIRECT_BOARD=0`) |
| 2 | same, wait loop (`:4973`) | replace `for _ in range(30): advance(1)` with the forecast's `k` ticks, clamped to `[1, 30]` and to the same 40-round bound | off |
| 3 | same, before `_begin_pick` | park the just-carried arm **inside the wait** when a wait exists (`prev_active != next_active`), else leave the shipped switch rule | off |
| 4 | `reset` (`:2307`) | same forecast sizing for its round (it is 0/15 starved today, so this is a no-op by measurement, and stays for symmetry) | off |
| 5 | `_begin_pick` (`:2381`) | print the `[board]` row beside `bed_diag_report` (the **validation channel**) | off (`FRUIT_BOARD_DIAG=1` arms it) |
| 6 | `tasks.bed_diag_report` (`:5513`) | add `index=` and `dia=` to the per-row print | always (print-only) |

No change to `select_target`'s decision, to `_dynamic_select_floor`, to the
trigger, or to the supply schedule. The scripted line never constructs
`SortingRLEnv`, so items 1-4 are unreadable on it by construction (the P43
no-harm pattern).

### 3.5 The actuators, and the measured budget

B_1's 14 transitions are 1210 ticks (`gap_ticks=86.4` mean), and the classes are
exactly additive:

| term | ticks | share | removable? |
|---|---|---|---|
| 20-tick settle after the `grasp` teleport | 280 | 23 % | **no** - the policy's frame 0 |
| 30-tick `grasp` teleport | 420 | 35 % | **no** - same |
| 30-tick arm-switch park (9 of 14) | 270 | 22 % | only against a wait |
| 30-tick starvation round (8 of 14; 4 of them co-occur with a switch -> the 110 gaps) | 240 | 20 % | **yes** - 1 pump call (1 tick), quantised to 30 |

- **A1 pump-before-decide** (item 1): the *symptom-level* alternative to §2.4's
  F (one call at the boundary instead of pumping throughout). All 8 rounds. The
  predicted wait is
  **1 tick** (§2.2), so the saving is **232 ticks = 1.93 s = 0.81 %** of B's
  239.6 s span; the **240-tick / 0.83 %** figure is the `wait -> 0` ceiling
  (gap mean 86.4 -> 69.3). The corpus cannot resolve below 30, because 30 is
  the only re-check unit ever measured - hence F9.
- **A2 park-in-wait** (item 3): 120 ticks *if it ran alone* (the 4 co-occurring
  rounds), and **it is not additive with A1**: once the wait is 1 tick there is
  nothing left to fold a 30-tick park into, so the park term stays 270 and A2
  buys 0. A1 and A2 are **alternatives**, and A1 is the larger one - so the
  module's realistic ceiling is **232 ticks (0.81 %)**, not 352.
- **A3 pre-decision** (item 1's `next_target` + item 5): 0 ticks by itself; it
  is what makes the *park* pre-decidable at a non-starved boundary if a later
  phase finds a place to overlap it (none exists today: the single-arm direct
  env has one arm, so the park can only overlap a *wait*), and it is the
  interface a *staged-queue* scenario would need. Its value is the forecast,
  not the gap.
- **Not removable at all**: the 700 ticks of settle + teleport, and the 270 of
  park. The floor for any module is therefore **50 ticks/transition**, and
  "the line never waits" is not an achievable endpoint on this scenario.

### 3.6 What the board cannot fix (the honest bound)

The aperture. At a boundary the belt typically holds **1-3 usable fruit**
(B_1 `window` {1:4, 2:8, 3:3}, along span **median 20 mm** when two are
usable) inside a band that is **0.281 m** of geometry (`[0.399, spawn_y 0.68]`)
and ~0.15 m of observed stock, while one 15 s pick consumes **1.80 m** (~15
fruit) - **6.4x** by geometry, **12x** by observed stock
(`logs/p56/P3_QUEUE_MAX.txt`). No candidate module manufactures supply; a board
that pretends otherwise would just re-select faster into an empty band. When the pump is 12 s behind (8/8 rounds), even a
perfect band forecast says "nothing" and the answer is *the feeder*, which is
what the forecast's `source` field is for.

---

## 4. The smallest instruments (what phase 2 must print)

1. **`[board]` row**, one per selection instant and one per wait round:
   ```
   [board] t=T n_live= n_line= n_reach= n_usable= floor=0.399 target=<idx>/<grade>/<arm>
           pred=usable now|wait k|none src=band|feed|feed-blocked|none t_band= t_feed=
           lag= n_due= burst= stale=0 us=12.3
   ```
   `pred`/`t_next` are the forecast; the *measured* arrival is the next block's
   `t=` (`[bed-sel]`), so the forecast error is `t_next - (t_selected - t0)`.
   `us=` is the board's own wall cost - the number the thread question is
   actually about, and today unmeasured.
2. **`index=` / `dia=` on the `[bed-sel]` rows** - without it, `target=` cannot
   be compared to `chosen` by identity (§1.4).
3. **A `[pump]` row at the boundary** (only if A1 is spent): `n_due`, `period`,
   `burst`, `released`, `skipped` deltas for the call that is moved earlier, so
   the burst arithmetic of §2.2 is confirmed rather than inferred.

All three are reporting only. Per AGENTS §2 fruit-pose reads and pure reporting
do not move the result; the board must not read the articulation (§3.2).

---

## 5. What this phase did not do

- No simulator run: the one-call burst (§2.2) is **derived** from the pump
  loop's skip semantics, `period = slice/v` and the printed lag, not measured
  per call.
  The `[pump]` row is the diagnostic that would make it a measurement.
- No `src/` edit and no decode of `samples[_cursor]` at run time: the
  release-grade look-ahead is a **code fact** (`fruits.py:978-986, 1543`), not a
  measured accuracy.
- No `functools`/`dataclass` choice is registered, no thread is built (§3.2 says
  not to), and no claim is made about the *placed* count: B_1's 8/15 against
  A_1's 11/15 is a different branch (the pair agrees at attempt 0 and first
  diverges at attempt 1 - `logs/p57/PREREG.md` P5 corrects P56 §4's "from pick
  1"), and per AGENTS §2 a quantised outcome across two attractors is not a
  rate.
- The **staged-queue** scenario (a third belt segment between the catch floor
  and the station) is out of scope: it is a station-geometry change with its own
  pre-registration (`P38b`'s supply margin, `logs/p56/P56_RESULTS.md` §7).

## 6. Files

- `logs/p57/DESIGN.md` - this file.
- `logs/p57/PREREG.md` - the phase-2 endpoints, falsifiers and spend.
- `logs/p57/cand_census.py` - the census (offline, read-only).
- `logs/p57/cand_census.txt` / `.json` - its output on the three logs.
