# P92 PREREG_A1 — the census's own lever: gate the force servo on a confident contact

**Pinned before the R-cell runs** (md5 in `logs/p92/PREREG_A1.md5`). This is an
**amendment**, and the reason it exists is recorded rather than hidden: the
phase's first registration (`logs/p92/PREREG.md`) picked the supply band's top
from the *shipped-cell* census; reading the **pre-P87 block** the brief also
required (`logs/p80/T20`, `logs/p84/{D5,D6}` - same scenario, 2.35 s release
clock) then showed that the never-held class is **not** x-clustered (its six
events span x = 0.273 / 0.279 / 0.291 / 0.368 / 0.391 / 0.414 m), so the x band
has no mechanism link. That registration is **still measured and published**
(`T5`/`T6`); it is not withdrawn. This amendment registers the lever the census
actually names.

## 0. What the census found (and what it is)

Reproduce: `python3 logs/p92/chase.py` -> `logs/p92/chase.txt` (offline, the
records only). Per attempt, the `[task] force servo:` row that `note_result`
prints carries, per arm, the servo's own travel: `closed=<x>mm`,
`opened=<y>mm`, `trips=<n>` and the settle `ref=<F>N`.

**`closed > 0` is the cell's failure signature.** Pooled over the 40 distinct
shipped-cell attempts: **11 attempts carry `closed > 0` and all 11 failed**
(seed 5: 4/4; seed 6: 7/7) **against 1 failure in the 29 attempts that carry
`closed == 0`**. Hypergeometric one-sided p = C(12,11)/C(40,11) ~ **1e-8**.
The classes it contains are **exactly** the census's addressable set plus part
of the closed one: it holds **all 3 never-held** and **2 of the 9 cnp** (the
collapsed-close pair), and it is the *same* population as `gap_start - dia <=
-14 mm` (5/5 failed, `census.py`'s table) - the two reads are the same event
seen at the leg start and at the servo.

**The mechanism, in the code's own words.** `_force_servo_step` closes the
command by `FRUIT_DYNAMIC_FORCE_STEP` whenever the measured force stays below
`max(FRUIT_DYNAMIC_FORCE_MIN=2.0 N, 0.8 * ref)` for 3 ticks, bounded to
`FRUIT_DYNAMIC_FORCE_RANGE = 15 mm` below the gap the grip closed with. On a
grip whose contact is marginal or lost the reference is `0.00 N`, so the floor
is the absolute 2 N and **nothing** tells the servo the jaws are empty: it
walks the full 15 mm (and, after a re-seat, further - the observed rows read
`closed=15.00/18.00/20.20/25.00 mm`, `trips=38-88`). Measured consequences on
the failures:

* the T5 peach's close froze at **66.3 mm** around a **68.9 mm** fruit (-2.6 mm,
  a correct seat) and the *lift* leg then started at **54.5 mm** - the servo
  crushed the pads **11.8 mm inside** the fruit between the freeze and the
  carry, and the payload was gone (`force_min 0.00 N`, `sep_max 43.5 mm`);
* the three never-held rows read `gap_start = dia - 16.7 mm` and a `sep_max` of
  22-34 mm, i.e. the pads had swept through the fruit's own span before the
  lift began;
* the seed-6 `close: fruit drifted 379 mm off the pick centre` row is the same
  loop's dry-run check on a grip that was already empty (`force=58.15 N`,
  `span=99.1 mm` - a fully open span with a crush load: the pads came down on
  the fruit).

## 1. The change (one line, no code)

```
FRUIT_FORCE_REENTRY=1              # default 0, `tasks.py` (P7's "FARM Port A")
FRUIT_FORCE_REENTRY_DIAG=1         # the knob's own counts-only readout
```

The existing, documented, **default-off** gate: the servo runs its integral law
**only while it has a confident contact estimate** - `force >= ENTER (1.0 N)`
and `contacts >= ENTER_CONTACTS` for `ENTER_TICKS`, with hysteresis down to
`EXIT (0.3 N)` - and **out of force mode it holds the commanded gap** (no
chase). It is read only inside `_force_servo_step` and only while
`_dynamic_capture_active`, so it is exactly the scripted dynamic catch (the
two-line and the single-arm dynamic line) and nothing else; with the knob unset
the shipped line is byte-identical. The shipped healthy hold reads **9-11 N
with 2 contacts**, i.e. far above the 1.0 N enter threshold, so a healthy grip
must stay in force mode and behave as it does today.

`FRUIT_FORCE_REENTRY_DIAG=1` adds one counts-only `[task] force reentry:` row
per attempt (entries / exits / gated ticks) - the manipulation check.

## 2. Endpoints

**Primary: the placed count (pooled over the two seeds) - a count, and a
draw.** Shipped **28/40** (seed 5 16, seed 6 12). Prediction **30-33**
(seed 5 17-18, seed 6 13-15): the 11 chase attempts hold 3 never-held + 2
collapsed-close `cnp` + 6 ordinary `cnp`; the lever can only convert the ones
whose collapse *caused* the loss (the 5 collapsed-close, of which the 2 `cnp`
were already counted as the closed class), so the honest expected gain is
**+2 to +5**, not +11.

**Secondary:**
* the **chase set** (`closed > 0`) count: 11 -> predicted **<= 5**;
* the **never-held** class: 3 -> predicted **<= 1**;
* the **`cnp`** class: 9 -> must not rise (it may fall if the collapse was its
  cause on those legs);
* the **held legs' delivered pinch** (`force_min` median over held
  `grasp_lift`/`place*` legs): must stay at the P41 plateau **>= 9.0 N** - this
  is the guard that the gate did not starve a healthy grip;
* the interval (pooled + per arm, both denominators) and the wall;
* the class-standardised placed rate at the control's arm x species mix.

## 3. Guards

* **G1 the held-leg force floor** (`force_min` median >= 9.0 N over the held
  legs): a fall means the gate is holding back a grip that needs the servo.
* **G2 the `cnp` class must not rise** (<= 9 pooled; <= 2 / <= 7 per seed).
* **G3 no new failure reason** (the notes' key set stays inside the control's).
* **G4 the landing**: every payload-present release `on_belt=True`.
* **G5 the motion budgets** on every cell (budgets-only; a behaviour change
  moves the fingerprint by construction).
* **G6 20 attempts per cell, no lost slot.**
* **G7 the manipulation check**: the diag rows must show **entries > 0** and
  **gated ticks > 0** on the failing legs; a cell where the gate never engages
  is not a measurement of the lever.
* **G8 the shipped tree is inert with the knob unset** (`selfcheck.sh`,
  `accept.sh` unchanged) - proven by the C5/C6 cells of PREREG.md.

## 4. Decision rule

**Adopt only if** the pooled placed count **>= 30** and neither seed falls below
its own control **and** G1-G8 pass. Otherwise not adopted and published as a
negative.

**Stated up front:** the count is a draw (the same control swings 16 -> 12
between these seeds), so the *primary* is a paired-level read too: the
per-seed delta and, where the branches have not diverged, the slot-paired
outcome. The **mechanism** claim is the chase-set count, which is a per-attempt
leg-level read (11/11 vs 1/29) and does not depend on the branch.

## 5. Falsifiers

* **F1** the gate is inert (the diag reads `entries = 0` or `gated = 0`
  everywhere).
* **F2** the chase set does not fall (`closed > 0` still >= 9).
* **F3** the placed count falls pooled or at a seed.
* **F4** the held-leg force floor breaks (G1) - the gate starves a healthy
  grip, which is the failure mode the knob's own design is meant to avoid.
* **F5** a new reason, a landing regression, or a motion-budget failure.

## 6. Cells

| cell | env | role |
| --- | --- | --- |
| `R5` | `ATTEMPTS=20 SEED=5 FRUIT_FORCE_REENTRY=1 FRUIT_FORCE_REENTRY_DIAG=1` | the gate, seed 5 |
| `R6` | `ATTEMPTS=20 SEED=6 FRUIT_FORCE_REENTRY=1 FRUIT_FORCE_REENTRY_DIAG=1` | the gate, seed 6 |

Controls: `C5`/`C6` from `run_p92.sh` (same tree, same instrumentation, one run
each, and their own replay check against `logs/p91/C5.log` / `logs/p91/C6.log`).
Instrumentation otherwise identical to the C cells, plus the knob's own diag.

Scope note: the knob is **dynamic-capture-scoped**, so it is the scripted
dynamic catch on both the two-line and the single-arm dynamic line; the direct
policy path (`DirectSortEnv`) is not a dynamic capture and cannot see it. If it
ships it is a *cell-control* default, not a supply change: no motion reference
moves (the physics is unchanged on a healthy grip, and the gate only ever
*withholds* a motion), and the store provenance needs `physics.force_reentry`
in both manifest writers - named as an adoption item, not built here.
