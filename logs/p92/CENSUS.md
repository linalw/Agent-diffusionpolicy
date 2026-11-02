# P92 CENSUS — what the shipped two-line cell actually loses, class by class

Offline, from the records. Reproduce with

```bash
python3 logs/p92/census.py          # the shipped cell  -> logs/p92/census.txt
python3 logs/p92/census.py --pre    # the pre-P87 block (a different clock)
python3 logs/p92/chase.py --all     # the force servo's own travel per attempt -> chase.txt
```

Both scripts are read-only, open logs, and print. The classifier lives in
`census.py` and the report scripts import it, so no number here can drift from
the one a phase report prints.

## 1. The corpus, and what counts as a sample

**The shipped cell = 40 distinct attempts.** `logs/p87/{T5,T6}` are the two
distinct scenario cells (seeds 5 and 6); every other same-tree log the brief
lists is a **byte-identical replay** of one of them, by that phase's own proof
and re-verified here on the `[fruit]` stream:

| cell | log | replays (dropped from the pool) |
| --- | --- | --- |
| seed 5, 20 attempts | `logs/p87/T5.log` | `p88/C5`, `p88/N5`, `p89/C5`, `p91/C5`, `p91/N5` |
| seed 6, 20 attempts | `logs/p87/T6.log` | `p88/C6`, `p89/C6`, `p91/C6` |

**A third, pre-P87 clock is kept separate and never pooled**: `logs/p84/{D5,D6}`
(same scenario, the 2.35 s release; `logs/p80/{T20,T6}` are their replays, and
they carry no `[carry]` diag, so 4-5 of their rows are unclassifiable - they are
reported as such, never guessed). Everything below is the shipped cell unless it
says *pre-P87*.

## 2. How a failure is classified

Per **attempt**, from that attempt's own evidence, never from the summary text:

* **the attempt boundary** is `[task] target <fruit> ... with <arm> arm` (start)
  and `[biarm] result <arm> index=...` (end); the `[carry]` rows between them
  that name that arm are its legs. The two-line arms run concurrently, so the
  per-arm buffer is what associates them - the *arm-agnostic* `[task]` prints
  (`dynamic close: ...`, `catch-up residual`) are used only as corroboration,
  and are counted rather than attributed where they cannot be tied to an arm.
* **`cnp` (carried, not placed)** - the payload was in a pinch and left it:
  `placed=False` with `grasped=True`, or `grasped=False` on a leg that *did*
  carry a pinch (`fmax > 0`). Evidence: `loss_row` set, `force_min == 0.00 N`
  after a real `fmax`, `clean_slip_max > 100 mm`, `sep_max` at or past the
  ~98 mm open stop. This is the **closed loaded-slide class**
  (`logs/p42/SIM_LIMIT.md`) - *counted, not chased*.
* **never-held** - the pads closed on air: the leg's `contacts@onset == 0`,
  `force@onset == 0.00 N` **and** `fmax == 0.00 N`, i.e. no pinch ever existed
  (P76 A3's exclusion read positively), and `sep_end` is at the pads' own
  closed limit rather than at the fruit.
* **`fell off the line`** - the note names it (lost upstream of the grasp).
* **`diverted`** - not an attempt class: a *pool slot* retired after two failed
  attempts (the reject chute). Counted separately.
* **starvation** - a poll with no eligible fruit (`no eligible fruit; station
  released`). Also not an attempt class: it costs **time**, and a lost slot
  only when the attempt never runs. Counted separately.
* **anything else** - printed with its own row.

## 3. The table (shipped cell, 40 distinct attempts, 28 placed = 70 %)

| class | n | share of failures | share of attempts | scenario-addressable? |
| --- | --- | --- | --- | --- |
| `cnp` / loaded slide | **9** | 75.0 % | 22.5 % | **no** - the closed class (`logs/p42/SIM_LIMIT.md`) |
| never-held (pads on air) | **3** | 25.0 % | 7.5 % | **yes in principle** - pre-contact / close geometry |
| `fruit fell off the line` | **0** | - | - | n/a |
| starvation (lost slot) | **0** | - | - | not a failure class here |
| diverted (a slot retired) | 1-2 | - | - | a book-keeping consequence |
| anything else | **0** | - | - | - |

Sub-splits: `cnp` by the leg it was lost on - **lift 7, `place*` 2**
(`clean_slip` 11-855 mm, `force_min` 0.00-0.24 N); never-held = **3 kiwis**
(5.4 / 5.6 / 6.2 cm); per arm **left 15/21, right 13/19**; per species
**peach 5/10 failed, kiwi 4/10, pear 2/9, orange 1/5, strawberry 0/3,
tomato 0/3** (n too small for a species claim, reported because it is asked).

**The class the brief calls scenario-addressable is 3 attempts - 25 % of the
failures - and that is the whole of it.** The 75 % is the closed class.

## 4. The addressable class, and the mechanism that actually decides it

The three never-held attempts are *exactly* the attempts whose
`dynamic catch-up: residual` exceeds the 6 mm tolerance, and there are no
others: **3/3 failed vs 0/37** at or below it (residuals **87.6 / 251.0 /
480.6 mm**). That is P47/P48's live pre-close discriminator, reproduced on the
two-line.

But the sharper read is not the residual - it is the **close**:

**(a) `gap_start - dia`.** The `[carry]` row prints the commanded pad gap the
carry leg *found* (`gap_start`). Against the fruit's own width this is the
close's seat:

| population | n | failed |
| --- | --- | --- |
| `gap_start - dia <= -14 mm` (the pads commanded **into** the fruit) | **5** | **5** |
| everything else (`-9.4 .. +5.6 mm`) | 35 | 7 |

Hypergeometric one-sided **p = 0.0012**. The five are the 3 never-held **and**
the 2 seed-5 `cnp` - the same event seen at the leg start. The T5 peach is the
plainest read: its close froze at **66.3 mm** around a **68.9 mm** fruit (-2.6 mm,
a correct seat) and the *lift* leg then started at **54.5 mm** - the pads were
crushed 11.8 mm inside the fruit between the freeze and the carry.

**(b) The servo's own travel.** The `[task] force servo:` row that prints per
attempt carries, per arm, how far the servo's integral law walked the command
inward (`closed=`, `trips=`). Pooled over the 40 attempts:

| | n | failed |
| --- | --- | --- |
| `closed > 0` (the servo chased) | **11** | **11** |
| `closed == 0` | 29 | **1** |

p = C(12,11)/C(40,11) = **5.2e-09**. The 11 hold **all 3 never-held and 8 of the
9 `cnp`** - i.e. **the whole failure set of this cell is one mechanism**, and it
is the force servo's chase: `_force_servo_step` closes by `STEP` whenever the
force stays under `max(2.0 N, 0.8 * ref)` for 3 ticks, bounded by
`FRUIT_DYNAMIC_FORCE_RANGE = 15 mm`. On a grip that is marginal or already lost
the settle reference is **`ref=0.00 N`**, so nothing tells the servo the jaws
are empty and it walks the full range (`closed=15.00 / 18.00 / 20.20 / 25.00 mm`,
`trips=38-88`). The pre-P87 block reproduces it exactly: **14 chases, 14
failures; 0 failures in 26** (`chase.txt`).

**So the census's answer to "what is scenario-addressable" is: almost
nothing.** The 3 never-held are not a supply-geometry miss - they are the same
close collapse as the 75 %, detected one phase earlier (the pads close through
the fruit's own span, so the peak-lift predicate reports `grasped=False`). The
superficially attractive supply reading - 2 of the 3 sit at the delivered
x = 0.386 / 0.391 m, at the record's 0.39 m clean edge - **does not survive the
pre-P87 block**, whose six never-held span x = **0.273 / 0.279 / 0.291 / 0.368 /
0.391 / 0.414 m**, and does not survive this cell either (10 failures in 36
in-band attempts vs 1 in 3 above the designed top: no separation).

## 5. The classes that are *not* the loss (measured, so nobody re-derives them)

* **Starvation is not a failure.** Every cell ran its full 20 attempts. The
  `no eligible fruit` polls are 45 (seed 5) / 37 (seed 6) - they are **wait**,
  and the wait is inside P91's audit's `descent` block. The failures' descent
  blocks are *longer* than the successes' (3.50 vs 3.05 s seed 6; 4.21 vs 3.50 s
  seed 5), i.e. the failures are not the starved ones.
* **The catchable depth is not the loss.** `queue=` at the handover is 2-5 on
  every attempt: **mean 3.25 on successes, 3.17 on failures** - no signal.
* **The diversion is book-keeping.** `diverting <fruit> (index N) after 2 failed
  attempts` is a *pool slot*, and the two attempts on it are separated by
  several other attempts. At seed 5 both sit at **x = 0.239 / 0.241** (the same
  instance, still on the belt, re-selected - the one genuine instance retry in
  the corpus); at seed 6 they sit at **x = 0.299 / 0.343** (44 mm apart - the
  slot was **recycled**, so the second attempt is a *different* fruit). A
  "retire it sooner" rule would therefore change one attempt in 40 and remove a
  pool slot; it is not the lever, and it is recorded as a non-lever rather than
  proposed.
* **`fell off the line` is zero** on this scenario in 40 attempts, and the
  delivered x minimum is **0.1998 m** - 20 mm above the left arm's 0.180 m
  admission floor. **P38b's registered-not-run low-tail lever (a 0.237 m floor
  against a -0.057 m excursion) has no events here**; the tail that exists is at
  the *top* (see §4), and it is not the discriminator either.
* **What the closed class has already been shown not to answer to** (so it is
  not re-tried): force 4.4 -> 9.8 N and the 10/30/45/60 N ladder (P41/P76/P77),
  the scoped caps (P78/P79), the seat (P42), the pad geometry (P39/P69), the
  attitude (P62/P63/P64/P65), the lift/transfer height and the place station
  (P66/P67/P73/P90), the place speed and the dwell (P73/P74), the fail-fast
  (P83/P84) and the profile blocks (P86/P87/P88/P89).

## 6. What the census hands on

Two things, and the phase measured both:

1. **The scenario lane is empty.** The one supply lever the brief's lineage
   names (P38b's margin purchase) is at the wrong end of a distribution with no
   low-tail events, and the top of the band is not a discriminator (§4). It is
   still registered and measured, because a negative from a pre-registered arm
   is worth more than an argument: `logs/p92/PREREG.md`, cells `T5`/`T6`,
   `FRUIT_SUPPLY_X_MAX=0.36 -> 0.33`.
2. **The mechanism is the force servo's chase, 11/11 (and 14/14 pre-P87).** The
   cell already has a documented, default-off lever for exactly that discipline
   (`FRUIT_FORCE_REENTRY`, P7's "FARM Port A": run the integral law only while
   the contact estimate is confident, otherwise *hold* the gap instead of
   chasing it). That is `logs/p92/PREREG_A1.md`, cells `R5`/`R6`.

Neither changes `configs/` or `src/` in this phase; both are env-only arms.
