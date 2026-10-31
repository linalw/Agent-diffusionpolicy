# P75 results — the place leg's onset is an **expulsion**, and it is neither a slide at constant `sep` nor a command transient

**Diagnostic-only phase.** One default-off trace (`FRUIT_PLACE_ONSET_TRACE`), two
registered direct cells (seeds 77 and 101) plus one declared extension cell at a
longer window, **no adoption, no default change, no commit**. The method and the
classification rule were written and pinned before the runs
(`logs/p75/METHOD.md`, md5 `479bb8969cbf2b66b7bca03238db94ed`).

---

## 0. Verdict

**The escapes are (a) expulsions - a wedge/pry runaway - and the trace resolves
them at one tick.** Every one of the six left place-leg escapes is
`clean_slip_max > 800 mm` and `cnp`; in the leg that the 200-tick window covers
completely, the payload's hand-frame displacement is **exactly 0.0 mm for 110
ticks**, the force then collapses **in two ticks** (5.03 → 4.11 → 0.00 N), the
measured jaw separation starts **rising** on the same tick, and within **9 more
ticks** the pads are driven to their **98.1 mm mechanical open stop** while the
commanded gap is *closing* (68.7 → 66.7 mm). Nothing commanded steps: (c) is
refuted by measurement, on 26 traced legs.

* **Not (b):** `sep` does **not** stay at its leg-start value while the payload
  walks - it grows 78.0 → 98.1 mm (+20.1) in 9 ticks against a *closing* command.
  A slide through a holding gap is the `SIM_LIMIT.md` picture; on this interface
  the pads visibly **do not hold**, they are pushed to their travel limit.
* **Not (c):** **0 of 26** traced legs show a commanded-speed discontinuity
  (`|Δv_cmd| >= 0.10 m/s` at any tick), and at the escape tick every commanded
  quantity is smooth: `v_cmd` 0.202 → 0.205 → 0.207 → 0.210 over t = 110..113 and
  `tcp_err` on a straight monotone ramp (+0.6 mm/tick). A **held** leg carries the
  same ramp (25.1 → 46+ mm over the same window) and holds, so the ramp is not the
  actuator either. There is therefore **no profile-continuity lever at the leg
  boundary** and nothing is registered for one.
* **The escape has two firing sites, one mechanism.** The same wedge event fires
  either at the end of the **lift** (2 of 6 escapes: the place leg then *starts*
  with one face at 0.00 N and the jaws at 85-98 mm) or inside the place leg at
  t = 105-159 (4 of 6). Which one happens is settled before the place leg begins;
  the place leg only carries the consequence.

**What this changes.** P73 closed the transfer height, P74 the profile speed, and
both left "the payload is gone before the leg rotates" standing. P75 says *what*
takes it: not a slide, not a clock, but a **pry that reaches the pad stop in ~9
ticks**. The lever family that touches that is the pad **face geometry**
(envelopment / depth), which is `logs/p42/SIM_LIMIT.md`'s "new pad asset"
sanction - and the force family stays closed (P41: 9.8 N is the profile's
ceiling and 60 N still loses a strawberry).

---

## 1. What was read, and the two cells

`FRUIT_PLACE_ONSET_TRACE=60` on the P66-phase-3 / P71-phase-2 / P73 / P74 cell
verbatim (seeds 77 and 101, 15 picks, `moe_v13s` `61da390a`, `FRUIT_CARRY_DIAG=1`
+ `FRUIT_MOTION_REPORT=1`), then `=200` on one declared extension cell.

| cell | wall | traced place legs | left escapes (`slip_max > 800 mm`) |
|---|---|---|---|
| `A_77` (registered) | 532 s (35.5 s/pick) | 12 (6 left / 6 right) | **3** - 832.5 / 833.6 / 806.8 mm, all `cnp` |
| `A_101` (registered) | 529 s (35.3 s/pick) | 14 (6 left / 8 right) | **3** - 895.7 / 844.8 / 851.9 mm, all `cnp` |
| `B_101_t200` (extension, **not** a registered cell) | 8 of 15 episodes | 6 (2 left) | 1 resolved end-to-end (apple 7.0 cm) |

**Twelve left place legs, six escapes, six holds** - and the held/escaped split
agrees with the attempt outcome on **12/12** legs (`escape <=> cnp`), so
`clean_slip_max` is a faithful proxy here. **No rate is quotable**: the trace arms
the carry block and adds two reporting reads per traced tick, the direct loop is
not reproducible, and 6 escapes over two cells is a sample.

## 2. The two firing sites (tick, and the order of the symptoms)

### 2a. Inherited at the boundary - 2 of 6 escapes (seed 77 only)

`A_77` ep11 / ep13 (pear 6.1, orange 6.8) plus ep9 (pear 6.8, pried but 13.9 mm
and **placed**) share a first-tick state no shipped row can show, because the
reference is the leg's own first tick:

| leg | t0 `sep` | t0 `gap` | offset | t0 `f` (N) | `n` | 2 mm crossing | lift `slip` | outcome |
|---|---|---|---|---|---|---|---|---|
| ep9 | 98.1 | 66.9 | **+31.2** | (0.00, 14.23) | **1** | t=4 (13.9 mm total) | 10.4 | placed |
| ep11 | 85.4 | 60.1 | **+25.3** | (0.00, 9.26) | **1** | t=4 | 11.3 | cnp |
| ep13 | 98.1 | 69.6 | **+28.5** | (0.00, 20.48) | **1** | t=7 | 7.9 | cnp |
| 23 normal legs | - | - | **+8.5 .. +14.7** (median 11.0) | two-sided 4.3-5.1 each | 2 | none | 0.0-3.4 | - |

The pad-shell offset `sep - gap` separates the two states **with no overlap**
(8.5-14.7 vs 25.3-31.2 mm). The three pried legs are also the three whose **lift**
leg slipped 7.9-11.3 mm - but that separator is **not clean**: eight of the other
nine left lifts read 0.0-3.2 mm and the ninth (`A_101` ep14) reads **7.5 mm**,
0.4 mm below the pried set, and its place leg still starts **normal** (+8.8 mm,
two-sided). So a lift-leg slip alone does not produce a pried boundary; the
**first-tick pinch state** is the discriminator, and it says the wedge fired
during `grasp_lift` and the place leg inherits a jaw already at or near its open
stop with one face unloaded. **Pried is necessary, not sufficient**: ep9 held at
13.9 mm.

### 2b. Inside the place leg - 4 of 6 escapes, at t = 105-159

These legs start **clean** (n=2, f two-sided 4.28-4.95 / 4.89-5.07, offset
+8.8..+13.1) and `|d|` stays **0.0 mm for the whole 60-tick window** - which is
itself the finding: the payload does not begin to go in the first 60 ticks.

The 200-tick extension resolves one of them end-to-end (`B_101_t200` ep0, apple
7.0 cm, left, `cnp`); the table is the trace verbatim:

| tick | `|d|` | `d=(x,y,z)` mm | `sep` | `gap` | `f=(f0,f1)` N | `n` | `tcp_err` | `v_cmd` | `v_ach` |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.0 | (0,0,0) | 78.0 | 68.7 | (0.00, 4.93) | 1 | 29.2 | 0.000 | 0.000 |
| 90 | 0.0 | (0,0,0) | 78.0 | 68.7 | (0.00, 5.04) | 1 | 20.8 | 0.153 | 0.100 |
| 110 | 0.0 | (0,0,0) | 78.0 | 68.7 | (0.00, 5.03) | 1 | 32.4 | 0.202 | 0.152 |
| **111** | **0.3** | (+0.3,+0.2,+0.1) | 77.8 | 68.7 | (0.00, **4.11**) | 1 | 33.0 | 0.205 | 0.151 |
| **112** | 1.3 | (+0.9,+0.8,+0.4) | **78.8** | 68.7 | (0.00, **0.00**) | **0** | 33.6 | 0.207 | 0.148 |
| 115 | 4.2 | (+2.8,+2.8,+1.4) | 83.7 | 68.3 | (0.00, 0.00) | 0 | 35.4 | 0.214 | 0.158 |
| 121 | 12.6 | (+6.6,+10.1,+3.6) | **98.1** | 66.7 | (0.00, 6.76) | 1 | 38.8 | 0.228 | 0.176 |
| 199 | 247.1 | - | 98.1 | - | - | 1 | - | - | - |

**The order is settled and it is not a slide:** `sep` is constant to the print for
110 ticks, the force collapses in two ticks, the pad separation **rises on the same
tick the first 0.3 mm appears**, and it reaches the **98.1 mm stop** 9 ticks later
*while the force servo closes the command* (68.7 → 66.7). The payload is pried out
through a widening gap, not dragged through a holding one. The two other late
escapes of that cell could not be re-drawn (the direct loop is not reproducible
and `B_101_t200` was stopped at 8 episodes to bound the phase); the registered cells' own rows
agree on the outcome of the sequence - `sep_end` 42.6-53.7 mm on all four late
escapes, i.e. the jaws come back to the servo's closed form once the payload is
gone, not to the 98 mm stop.

## 3. The three candidate classes, scored

| class | prediction | measured | verdict |
|---|---|---|---|
| **(a) expulsion** | `sep` collapses / `fmin` drops **before** the displacement grows | 2/6 escapes: already collapsed at t=0 (inherited); 4/6: `f` 5.03→0.00 in 2 ticks and `sep` 78.0→98.1 in 9 ticks **before** the payload has moved 2 mm, against a closing command | **the class** |
| **(b) slip at constant `sep`** | the displacement grows while `sep` and `f` stay at their leg-start values | on every escaped leg `sep` moves (to 98.1 or from 85-98 to 42-54 mm); the only constant-`sep` legs are the **held** ones | **refuted** |
| **(c) command transient** | `tcp_err` or `|v|cmd|` steps at the boundary before the displacement | **0/26** legs have a `|Δv_cmd| >= 0.10 m/s` step; the 4 legs whose `tcp_err` starts above its own steady state (+20 mm) are 3 escapes **and 1 hold**, and at the escape tick the ramp is smooth (+0.6 mm/tick) and shared by a holding leg | **refuted** |

Across all three logs - **32 traced place legs** - the pinned rule returns
**`a0=3, a=2, b=0, c=0, none=27`**: not one leg classifies (b) or (c), on any of
the two registered cells or the extension.

**What each would have implied, and what holds now.** (a) means the pinch *depth
and face geometry* is the object - so the place leg is not a profile problem and
not a clock problem, and the family to spend on is the pad face
(`SIM_LIMIT.md`'s new-pad-asset sanction, still owner-gated), **not** more force
(P41 closed it: 9.8 N is the drive's ceiling at 120 Hz and 60 N still loses a
strawberry). (b) would have left `SIM_LIMIT.md` exactly as written. (c) would
have bought a boundary-blend lever; **there is none to buy**, and nothing is
registered for one.

## 4. A post-hoc marker worth registering (not a result)

The four **late** escapes' *preceding lift* leg ended **27.6-58.9 mm behind its
own command** (`res_end`), against **8.6-14.6 mm** on the eight legs that held or
were pried at the boundary - **no overlap**, n = 12 left legs. That is a 4-vs-8
post-hoc split on one instrument reading, so it is **not** a result: it is the
named next registration ("does the lift leg's tracking deficit predict the place
leg's escape?"), which needs its own PREREG, more seeds, and the mechanism named
before it is measured. Note it does **not** fit a simple "the catch-up feeds the
slip" story: `|d|` is 0.0 mm through the fastest part of the catch-up (t = 1-60)
and the wedge fires at t = 111, on a leg where `v_cmd` was already 0.20 m/s.

## 5. The instrument, its cost, and the no-harm gate

**The instrument** (`src/fruit_sorting/tasks.py`, default **0 = off**):
`FRUIT_PLACE_ONSET_TRACE=<ticks>` prints one `[place-trace]` row per tick for the
first `<ticks>` ticks of every `place*` leg, post-step, inside the existing W8-B
carry block (setting it **arms** that block, so the trace is self-sufficient):
`t`, `|d|` and `d=(x,y,z)` (the hand-frame displacement, P61's axis), `sep`
(measured) and `gap` (commanded), `f=(f0,f1)`, `n`, `tcp_err`, `v_cmd`, `v_ach`
and this tick's `q_margin=…@jN`. **No articulation read is added** - `rot_now`,
`pads`, `_tcp_pos`, `_marg` and `gap_command` are the block's own; the two
additions are `jaw_separation()` and one tactile set per traced tick, both
reporting readers. Pinned by `scripts/241_p75_place_trace_selftest.py` (a
`selfcheck.sh` leg) and read by `scripts/242_p75_classify.py`.

**Cost, measured:** at 60 ticks the two registered cells ran at **35.5 / 35.3
s/pick**, i.e. inside the untraced P74 cell's own 29.7-35.4 s/pick range; at 200
ticks the extension ran at ~3.5 min/episode, so the cost is **super-linear in
traced ticks** and 200 is a batch-lane setting, not a casual one. Neither number
is a rate.

**No-harm (the shipped path is byte-inert).** `scripts/accept.sh` with the knob
unset reads **6/9, `fingerprint: matches`, and its 346 `[fruit]` lines are
byte-identical to `logs/p73/accept_noharm.log`'s 346** - both streams md5
**`d0079a237202e2f9b0e152655af32a77`** (`logs/p75/accept_noharm.log`, driver
`logs/p75/accept_noharm.driver`). The run's exit is **1 on the rate floor only**
(6/9 = 67 % < the shipped 75 %), which is this tree's standing branch since P32
(P71/P73 both read 6/9-6/10 on the same 346 lines). `scripts/selfcheck.sh`
**PASS, 0 failures**. The scripted path never constructs `SortingRLEnv`, and
`_place_onset_trace == 0` leaves `guard_armed`'s boolean unchanged, so the
shipped stream is byte-identical.

**Provenance / tree drift (recorded, not resolved).** The two registered cells and
the `accept.sh` no-harm run were measured on `tasks.py` **`303d025d`** (the P75
tree, commit `85dc38b`), where `scripts/selfcheck.sh` read **PASS, 0 failures**
(`logs/selfcheck.log` `1895d7f2`). A **concurrent P76 lane** then began building
on that code in the same file (`scripts/243_p76_sep_selftest.py` +
`guard_sep_max`/`sep_min` readouts), so the *current working tree* is not the
measured one, and its `rl_env.TASKS_MD5` follow was not yet in place when this
note was written - which is why `scripts/selfcheck.sh` on the current tree reports
the `TASKS_MD5`-following legs (P62/P64 and the tasks.py pin) failing. **That is
P76's in-flight state, not a P75 result**: every P75 leg passes on both trees, and
the `[fruit]` byte-identity above was established on the measured one.

## 6. Deviations recorded (all before or outside the counted cells)

* **A1** (before the measured cells, after a 1-episode smoke): the
  `v_ach >= 1.5*v_cmd + 0.05` clause was **withdrawn** - on a *clean* leg the
  achieved TCP speed reads 0.095-0.099 m/s for t=1..3 while `v_cmd` is 0.000
  (the arm closing the previous leg's residual), so it fired on every leg.
* **A2** (after the measured cells): the force reference became the **stronger**
  face at t=0 instead of the weaker, because a leg that starts single-sided
  (`f=(0, 14)`) would otherwise read "collapsed" against its own zero. **No leg's
  class changes** under A2 except by removing that artefact.
* **A3** (after the measured cells): a leg that is **already** single-sided with
  `sep - gap >= 20 mm` at t=0 is labelled **`a0`** (expulsion, inherited at the
  boundary) instead of falling through to (b) - on such a leg `sep` *cannot* fall
  further, because it is already at the mechanical stop, so the literal
  in-window first-crossing test has no room to fire. Under the pre-A3 rule seed
  77 read `a=2 b=1`; the b was that artefact. The **mechanism** verdict is the
  same either way: all three of those legs had no live pinch at the boundary.
* **A4**: the 200-tick extension cell is **not** a registered cell - it was run
  after the two cells showed that 4 of 6 escapes start outside a 60-tick window,
  to resolve one of them at 1-tick resolution. It is labelled as an extension, it
  is not counted in the 6, and no rate comes from it.

**Nothing is adopted.** `FRUIT_PLACE_ONSET_TRACE` stays default off until a lane
needs it; `configs/*` and both motion references are untouched (`8952c320` /
`eb697f23`), and no reference was re-recorded.

Pins: `tasks.py` **`303d025d`** (`303d025d7085236ce2ee93b735c55f73`, the trace),
`rl_env.py` (the metadata-only `TASKS_MD5` follow),
`scripts/241_p75_place_trace_selftest.py`, `scripts/242_p75_classify.py`,
`logs/p75/p75_report.py`; checkpoint `moe_v13s` `61da390a`. Log pins: `A_77.log`
**`23a9f18a`**, `A_101.log` **`d79504a9`**, `B_101_t200.log` **`39fe6bb8`**,
`accept_noharm.log` **`6aa199f3`**, `p75_report.txt` **`556f2d4b`**,
`logs/selfcheck.log` **`1895d7f2`**.

## 7. Evidence layout

```
logs/p75/METHOD.md            the instrument + the pinned rule + A1        (md5 479bb896)
logs/p75/PREREG.md5           the registration md5 + timestamp
logs/p75/header.txt           the md5 pin block of the batch
logs/p75/direct/A_77.log      registered cell, seed 77, trace 60
logs/p75/direct/A_101.log     registered cell, seed 101, trace 60
logs/p75/direct/B_101_t200.log  extension cell, seed 101, trace 200 (6 of 15 episodes)
logs/p75/smoke.log            the 1-episode smoke (A1's evidence)
logs/p75/p75_report.py/.txt   the per-leg table (lift / first tick / place row / class)
```
