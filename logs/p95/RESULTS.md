# P95 RESULTS — the incoming fruit's disturbance is the **other arm's pads**

Registration: `logs/p95/METHOD.md` (md5 `b79e9a08…`, pinned before any run, not
rewritten; the one amendment `A1` - the spin threshold 0.5 -> 2.0 rad/s, the
contact verdict as the gap **and** the measured span swing, and the log-derived
leg start - is `logs/p95/METHOD_A1.md`). Battery: `logs/p95/run_p95.sh` →
`logs/p95/*.driver`. Readout: `python3 logs/p95/probe.py` →
`logs/p95/probe.txt`; the traces are `logs/p95/tr6/` (seed 6) and `logs/p95/tr5/`
(seed 5).

**Verdict in one line: P93's open item is closed, and the answer is (a) — the
*other* arm.** The seed-6 attempt-0 kiwi is struck by the **left** hand's pads
**2 mm from its surface**, while that hand is running its own pre-pose blend to
its own station; the fruit takes `+0.40 m/s` in `x` and **21.6 rad/s** of spin
0.25 s before its descent leg, is already **28 mm** sideways of the aim the hover
latched when the leg starts (43 mm by its end), and the attempt fails as
`never_held`. It is **1 of 40 attempts**
(two seeds) and **4-5 of 40** pass within 6 mm of that hand; the class is
**structural** — the downstream lane's fruit must cross the upstream station —
and the fix is a **pre-pose clearance pose**, priced in §6 and **not built**.

## 0. The instrument, and the measurement-of-the-measurement

`FRUIT_FRUIT_TRACE=<max rows>` (`tasks.py`, **default off**): **one row per
control tick for the selected fruit** through its whole attempt — position,
linear and angular velocity, the belt's encoder speed, and every live fruit
within 0.15 m with its offset, velocity, mass, diameter and carried flag. Armed
at the attempt's start (before the pre-pose blend), flushed from `note_result`,
one JSON per attempt. `FRUIT_FRUIT_TRACE_ARM=1` adds each arm's jaw centre, TCP,
both finger-link positions, their distances and the measured jaw span — the
articulation-link read of AGENTS §2, so a **separately declared** cell.

The key sentence of the phase is the admissibility test, and it came out
stronger than predicted:

| cell | reads | `[fruit]` stream vs the record |
| --- | --- | --- |
| `F6` (seed 6) | fruit only | **970/970 identical** to `logs/p94/T6.log` (= `logs/p92/C6.log`) |
| `A6` (seed 6) | fruit **+ both arms' link reads** | **970/970 identical** |
| `A5` (seed 5) | fruit + both arms' link reads | **974/974 identical** to `logs/p94/T5.log` |

So: **the fruit-only per-tick trace is branch-neutral**, as AGENTS §2 predicts,
and — measured, not assumed — **so is this two-arm link read on this cell**. That
does not repeal §2's rule: the rule was measured on **7-10 link prims per tick
across many links** (a 3-14 s shift, one or two picks, `logs/434…451`), while this
instrument reads **3 prims per arm** and the baseline already reads the active
arm's TCP and both fingers every tick. What matters for the phase is that the
geometry below is read **on the recorded branch**: every number in §2-§3 is a
number of the shipped seed-6/seed-5 stream, not of a moved probe cell.

## 1. The witness, reproduced to the digit

`logs/p93/diag.txt` §1a says the seed-6 attempt-0 right-arm kiwi is at
`(-0.253, -0.125, +0.034) m/s` with `|w| = 8.36 rad/s` **when the descent leg
starts**. On the unmodified branch this trace reads the leg's start at
**tick 339, t = 17.225 s**:

```
this trace   v = (-0.2529, -0.1254, +0.0338)   w = (0.1955, -8.3608, -0.1637)
P93 recorded v = (-0.25292, -0.12544, +0.03384)  |w| = 8.36 rad/s
fruit position (0.24465, 0.0002, 1.19947)  ==  P93's own `descent` row
```

`2.37x` belt speed. So the phase starts from a **verified** witness, not from a
transcription — and the reproduction also settles a documentation detail the
record should carry:

> **`_cycle_mark("descent")` fires *after* `_approach`.** The rows labelled
> `descent` are the leg's **end** (the catch-up's first tick); the leg's start is
> `first_descent_tick - steps`, where `steps` is that leg's own
> `[motion] approach … steps=`. So the phase-per-sample `FRUIT_DYNAMIC_TRACE`
> emits its first catch-sequence row *at the leg's start*: everything before it —
> the hover move, the descent's own wait and the whole pre-pose — is simply
> absent, and the `descent` label it does print names the leg's end.

That is why P93 wrote "its source is open". The instrument covers it.

## 2. The attribution: the other arm, at its own pre-pose

The departure, tick by tick (`probe.txt` §2 prints all of it). `Lsep`/`Rsep` are
the two hands' **measured** jaw spans, `Lpad` the left hand's pad-point clearance
to the fruit's surface, `Ldy` that pad's along-belt offset:

| tick | t | phase | fruit y | z | \|v\| | /belt | spin | Δ\|v\| | Lsep | Lpad | Ldy | Rsep |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 309 | 16.97 | hover | +0.041 | 1.197 | 0.120 | 1.00 | 0.0 | - | 98.0 | +3 | -17 | 98.0 |
| **310** | **16.98** | hover | +0.040 | 1.197 | 0.144 | 1.20 | 3.7 | +0.024 | 97.9 | **+2** | -16 | 98.0 |
| 311 | 16.99 | hover | +0.039 | 1.197 | 0.216 | 1.80 | 10.6 | +0.072 | 97.1 | +2 | -16 | 98.0 |
| **312** | **17.00** | hover | +0.039 | 1.198 | **0.482** | **4.02** | **21.6** | +0.266 | 90.7 | +2 | -17 | 98.0 |
| 316 | 17.03 | hover | +0.034 | 1.198 | 0.278 | 2.32 | 10.2 | -0.033 | 71.6 | +4 | -15 | 98.0 |
| 320 | 17.07 | hover | +0.029 | 1.198 | 0.382 | 3.18 | 14.8 | +0.167 | 64.9 | +4 | -13 | 98.0 |
| 325 | 17.11 | hover | +0.020 | 1.199 | 0.252 | 2.10 | 9.4 | -0.033 | **59.8** | +4 | -6 | 98.0 |
| 329 | 17.14 | hover | +0.013 | 1.199 | 0.357 | 2.98 | 7.3 | +0.133 | 68.3 | +4 | 0 | 98.0 |
| 333 | 17.18 | hover | +0.006 | 1.199 | 0.390 | 3.25 | 11.3 | -0.050 | 92.1 | +6 | +10 | 98.0 |
| 339 | 17.23 | hover | +0.000 | 1.199 | 0.284 | 2.37 | 8.4 | -0.004 | 97.5 | +22 | +31 | 98.0 |
| 345 | 17.27 | hover | -0.007 | 1.200 | 0.259 | 2.16 | 7.0 | -0.015 | 98.0 | +32 | +45 | 98.0 |

Three facts, all measured on the same ticks:

1. **The left hand's measured jaw span collapses 98.0 → 59.8 mm over 15 ticks and
   springs back to 98.0 by tick 345.** A *commanded* close does not spring back,
   and the finger drive is stiffness-limited: at P41's `k = 1e5 N/m` and the
   10 N/joint cap a driven deflection is **0.1 mm**, so a 38 mm span change cannot
   be commanded by anything — it is a contact displacing the pads. The left arm's
   **own** close on its own pear is much later (its `[cycle]` has
   `prepose=0.71 hover=0.75 descent=3.05`, its descent starts at 20.475 s).
2. **The left hand's pad is 2 mm from the fruit's surface at that tick**, and the
   pad is **16 mm downstream of the fruit's centre** in `y` — i.e. it is *beside*
   the fruit in the belt direction, so the fruit runs into it.
   (The pad *point* is a ±5 mm indicator: the finger plates are angled at a 98 mm
   span, which is why §5 uses the *span displacement*, not the gap, as the verdict.)
3. **The active (right) hand is 160-190 mm away** at those ticks, at its hover
   (`Rsep` 98.0, jaw `z = 1.322`, above the belt, no descent yet) — so (e) is out.

What the other arm was doing is in the log, and it is exactly the pre-pose:

```
[biarm] left: station acquired at t=16.4s
[task] target pear (grade A, 6.9 cm) with left arm        <- left attempt 1 starts 16.45
[task] at pick pose after 0.71 s ... jaw=[0.3429, 0.0122, 1.2795]   <- pre-pose ends ~17.16
[cycle] attempt 1: prepose=0.71s hover=0.75s ...
```

The left jaw descends from its parked `z = 1.3581` (where it sat through
13.45-15.2) to `1.2795` during that blend: the **pad plane sweeps from
`belt_top + 0.107` down to `belt_top + 0.029`**, i.e. *through* the fruit band
(the kiwi's top is `belt_top + 0.058`), and it ends **29 mm below the fruit's
top**. The strike happens 0.53 s into that 0.71 s blend, at pad clearance +2 mm.

### The other four classes, excluded by measurement

| class | evidence against |
| --- | --- |
| **(b) spawn / release** | No teleport: the position is continuous at every strike tick and the velocity is not zeroed. The release *is* a real departure class — the fruit is dropped onto the belt, airborne at `z = 1.230` with `|v|` up to 0.665 m/s — but only **2/40** attempts start that way and both settle in 8 ticks, ~4 s before the leg. P38/P50's release offset is the *static* per-instance shift (mechanism closed, `logs/p50/`); this phase adds nothing to it. |
| **(c) belt / cleat** | The kick is `+0.402 x` and `+0.133 z` with `21.6 rad/s` of spin; the belt drives `-y` only, and P38 measured the transport's lateral contribution as **exactly 0.000 mm over 475 transits**. No cleat row exists on this line (cleats off by default). |
| **(d) depenetration / fruit-fruit** | The nearest neighbour at the strike is the left pear at **125 mm**, running at **0.1201-0.1205 m/s** with **no** speed change on the strike ticks (`nb swing = 0.0004 / 0.0001 / 0.0 / 0.0 m/s` at ticks 310/312/320/329); the second is the tomato 143 mm *upstream*. A mutual impulse would show in the neighbour's velocity and in mass-weighted momentum — neither moves. |
| **(e) the grasping arm** | 160-190 mm away, at its hover, `sep` 98.0, no descent for another 0.25 s. |

## 3. The census — 40 attempts, both seeds, and the exposure asymmetry

Departures before the descent leg (`probe.txt` §3), with a departure defined as a
jump cluster whose peak one-tick speed change is `>= 0.05 m/s`:

| class | seed 6 (20 attempts) | seed 5 (20 attempts) |
| --- | --- | --- |
| release drop (airborne at the attempt's start) | 2 | 2 |
| unattributed (fruit still upstream, `y = 0.42-0.65`, rolling transient after its release) | 2 | 2 |
| **arm-other** | **3 clusters, all in attempt 0** | **0** |
| arm-self | 0 | 0 |
| fruit-fruit | 0 | 0 |

And the P93 quantity at every leg's start (`probe.txt` §4):

| cell | legs at `<= 1.15x` belt | overspeeding |
| --- | --- | --- |
| `F6` (seed 6) | **19/20** | `2.37x` (attempt 0, the witness) |
| `A5` (seed 5) | **20/20** | none |

The payload arriving late/overspeeding is therefore **not** a general property of
the line — it is one event, and that event is the pad strike.

**The exposure is structural and one-directional** (`probe.txt` §5). The stations
are `left y = +0.000`, `right y = -0.100`, and the belt runs `-y`: a **right**-arm
fruit must cross the left station, a **left**-arm fruit stops at its own. Measured
closest approach of the *other* hand's pad point to the fruit before the leg:

| the fruit belongs to | n | min gap, median | min gap, min | `<= 6.4 mm` |
| --- | --- | --- | --- | --- |
| **right** arm (crosses the left station) | 19 | **31.6 mm** | **0.0 mm** | **5/19** |
| left arm (stops at its own station) | 21 | 217.2 mm | 126.3 mm | 0/21 |

Four of those 40 come within 6 mm, and of those four **one** displaces the pads by
`>= 2 mm` — the witness (26.4 mm) — while the other three are zero-impulse
grazes (e.g. seed-5 attempt 16 passes at 0.0 mm with `|v|` exactly 0.120 m/s,
spin exactly 0.0 and `sep` 98.0 throughout: a tangential brush carrying no
momentum). So the class is **1 contact / 40 attempts, inside a 4-5/40 contact
band**, and the mechanism that decides whether a near-miss *is* a strike is the
penetration depth, i.e. the fruit's own `x` against the hand's fixed pre-pose `x`.

## 4. Why a struck fruit fails: the aim is stale, not the grip

The hover latches the grip point (`_dynamic_grip_target`) from the fruit's
position **at the hover** (t ≈ 14.9, `x = 0.273`), and the descent is a static,
open-loop leg (`intercept=-0.0828`, the same 88 commanded samples in every cell).
By the leg's start the strike has carried the fruit to `x = 0.245` (**28 mm** off
the latched aim) and by the leg's end to `0.202` (**71 mm**, i.e. 43 mm of drift
during the leg alone), while `y` travels 63 mm against the 88 mm the schedule
prices. The pads then come down 28-71 mm off-centre and close **on** the fruit
instead of around it (58.15 N after 5 ticks, span 99.1 mm frozen at 88.3 mm),
drive it down through the belt (`z 1.198 → 0.818`) and the attempt ends
`never_held`
(`force@onset = 0.00 N`, `contacts@onset = 0`, `notes=['fruit did not follow the
gripper']`). The chain is the record's own `logs/p93/diag.txt` §1a/§1a'; what this
phase adds is **what started it**.

The phase does **not** claim a conversion, and needs none: there is no
counterfactual cell (the strike is deterministic given the fruit's `x` and the
left arm's blend phase), and the defect is an *invariant* violation — a hand
inside another lane's fruit band — not a rate.

## 5. The mechanism in one sentence, and why it is not a tuning problem

> The two-line's pre-pose is the **calibrated grasp configuration** at the arm's
> own station `x`; its pad plane sits **29 mm below a fruit's top**. The upstream
> station's arm holds that pose for 0.7 s at the start of every one of its own
> attempts, and the downstream lane's fruit must cross that station. Whether that
> is a strike is the fruit's own random `x` against the hand's fixed `x`.

Two consequences worth recording:

* **The hover is already clear.** The hover puts the pad plane at `belt_top +
  0.072` = **13.5 mm above** the tallest fruit's top. The exposure exists only
  because the pre-pose dives to the grasp plane and the hover move then lifts the
  hand back to where it could have started. The dip is also a (small) feed-time
  cost.
* **No existing knob reaches it.** `FRUIT_HOVER` moves the hover (already clear),
  `FRUIT_ARM_PARK` is the *direct* env's inactive-arm pose (the two-line arms run
  concurrent attempts, so neither is inactive), the park-gate lever
  (`FRUIT_BIARM_PARK_EARLY`) acts on the *station box*'s ownership, not on the
  pre-pose height, and R3's residency lever (`FRUIT_BIARM_HOT_ARM`) holds the
  *previous* turn's station-side pose — measured negative on the interval.

## 6. The fix, priced — registered as the next phase, **not built**

The fix form is the **clearance pre-pose**: the two-line pre-pose must be a pose
whose **pads clear the tallest fruit** (`jaw_z >= belt_top + grasp_clearance +
FRUIT_HOVER`, i.e. `>= belt_top + 0.155`), with the descent still starting from
the hover as it does today. The left station has no such pose today — P39 recorded
why: *"the left station is the calibrated pick point (`y = 0.00 = cfg.pick_y`), so
`_prepare_two_line_stations` skips its solve"* — so the change is a **second
station solve at hover height**, using the machinery the *right* station already
runs (residual 6.7 mm), not a new mechanism.

**Not a one-liner, so not built here.** The pose is a solved joint vector, not a
scalar, so there is no `FRUIT_*`-style bound; the alternatives are worse:

| form | invariant | price |
| --- | --- | --- |
| **clearance pre-pose** (solve a hover-height station pose) | pads clear the band at every non-descending pose | **both motion references re-recorded** (it is the shipped acceptance's scenario), the acceptance/two-line gate re-based, every two-line store re-baselined, `236`-style solver pins updated |
| **cross-lane pre-pose gate** (don't blend while the other lane's fruit is inside the station's `y ± 0.15`) | no pre-pose while another lane's fruit is in the box | W6-C-style A/B; costs the pipeline overlap the two-line's rate is made of (the left's pre-pose *is* its setup) |
| **station separation** | stations further apart in `y` | bounded: the right station is already at the deepest reachable `-0.10` (R10-A's intercept map) and P90 closed the *place* station's map; a `y` move re-baselines both stores |

**Why the rate cannot be the argument, and what the argument is:** at 1/40 the
expected conversion is `2.5` points, against P93's own power statement of **364
attempts per arm** for an 8.75-point difference at 80 % power. So the adoption
argument has to be the **invariant** — a hand inside another lane's fruit band is
a defect regardless of its rate — which is P94's precedent, with one difference
that decides the sequencing: P94's fix was **bounded** (`|offset| > 0.20 m` ⇒ the
pads), so it could not move a leg below the bound. A pre-pose change moves
**every** two-line attempt, so it owes the full battery and both references.

**Registered as P96**: the clearance pre-pose, its offline invariant map (the
`jaw_z >= belt_top + 0.155` clause at every station, both arms, from the same
sweep shape as P66's station map), a 2-seed 20-attempt A/B with the **pre-leg
contact census of this report as the primary endpoint** (see §7's instrument) and
the delivered side as a report.

## 7. What a next phase gets for free

The instrument is default-off and shipped, so the endpoint the next phase needs —
*does a pre-leg pad contact happen* — is now one command:

```
FRUIT_FRUIT_TRACE=2500 FRUIT_FRUIT_TRACE_ARM=1 ATTEMPTS=20 SEED=<s> bash logs/p80/one_run.sh <log> <stamps>
python3 logs/p95/probe.py            # "5. THE EXPOSURE and the CONTACT TEST"
```

and its criterion is the pair `pad gap <= 6 mm` **and** `other-hand span swing
>= 2 mm` within ±4 ticks (the span is the verdict; the gap ranks). The census must
be run **on the arm-reading cell** (the geometry needs it) and both cells of this
phase are proven branch-true, so a treatment/control pair is admissible as long
as each side's own `[fruit]` stream is compared to its own record first.

## 8. No-harm, provenance

* `scripts/selfcheck.sh` **PASS, 0 failures, 1 skipped** (`logs/p95/selfcheck.log`
  is the run that includes the new **P95 fruit trace** leg, 67 checks: the switch
  table, the one `_step_sim` hook and that it is *not* in `ik_step`, the
  fruit-only default path, the no-op arm returning before any read, the single
  arming/disarm/flush sites and their thread-locality, the executed row shape, the
  0.15 m neighbour filter, the arm gate, and the four env names).
* **The shipped acceptance is inert**: `scripts/accept.sh` (knob unset, the
  two-line default) reads **8/10 = 80 %**, `fingerprint: matches
  configs/motion_reference.json`, `190: PASS`, and its **420 `[fruit]` lines are
  byte-identical (420/420)** to `logs/p94/accept_final.log` — the record of the
  same scenario on the same tree before this phase (`logs/p95/accept_noharm.log`;
  the gate is the standing 1.53x reported cone, unchanged).
* `src/` change: the instrument only (default off) plus `rl_env.py`'s
  **metadata-only** `TASKS_MD5` follow. `configs/` **untouched**
  (`motion_reference.json` / `..._twoline.json` `30fb99f8`,
  `..._single.json` `8952c320`), no reference re-recorded — and none is owed: the
  instrument is inert on every shipped path, which §0 proves on **3 cells /
  2,914 `[fruit]` lines** instead of asserting it.
* The phase's own run writes: `logs/p95/{F6,A6,A5}.{log,stamps,driver}`,
  `logs/p95/tr6/`, `logs/p95/tr5/` (40 traces, 32 MB, gitignored with the rest of
  `logs/`).

### Pins

| file | md5 |
| --- | --- |
| `src/fruit_sorting/tasks.py` | `cc4eea6625d3bc8334b6a952c179c03a` |
| `src/fruit_sorting/rl_env.py` | `416089129c8a686781ecf25a240fcd8f` (`TASKS_MD5` follow `19cd4028` → `cc4eea66`) |
| `scripts/252_p95_ftrace_selftest.py` | `880ce131da9e036ba36bfda6a5c00835` |
| `scripts/selfcheck.sh` | `ed646df63d5ae8eeb1fc471be5b6f134` |
| `logs/p95/probe.py` | `a78f0924a344aa033e2e1de38514b27f` |
| `logs/p95/METHOD.md` | `b79e9a081209466aa316c45f5f7fae5b` (pre-run, un-rewritten) |
| `logs/p95/METHOD_A1.md` | the amendment (`A1.1`-`A1.4`) |
| `logs/p95/run_p95.sh` | `4011c8d5…` at the header pin; `272d047d…` after the `A5` cell and the per-cell `FRUIT_FRUIT_TRACE_DIR` were appended, so the `A5` cell ran on the later tree (its own pins are in `logs/p95/A5.log`'s banner) |
| `configs/motion_reference{,_twoline}.json` | `30fb99f8824aa4cea906e40ebf5dfa58` (untouched) |
| `configs/motion_reference_single.json` | `8952c320d798ef42e03ba815c9e96b23` (untouched) |
| checkpoint | `moe_v13s` `61da390a` (untouched) |

### METHOD A1 (the short form; the amendment itself is `logs/p95/METHOD_A1.md`)

1. The spin-jump threshold is **2.0 rad/s**, not 0.5: a kiwi is an ellipsoid and
   rolls, so 0.5 rad/s fires on the transport's own tumble (the run at 0.5
   produced 149 "departures", almost all rolling jitter). The speed threshold
   stays 0.03 m/s and the *departure* bar 0.05 m/s.
2. A **contact** is `pad gap <= 6 mm` **and** the other hand's span swing
   `>= 2 mm` within ±4 ticks. The gap alone is a ±5 mm indicator (the finger
   plates are angled at a 98 mm span); the measured span displacement is the
   verdict, because it cannot be commanded (0.1 mm at the drive's stiffness).
3. The **descent leg's start** is `first_descent_tick - steps` (the `[motion]
   approach … steps=` of that leg), not a jaw-height rule: `_cycle_mark("descent")`
   fires after the leg, and a height rule finds the leg's *end*.
