# P47 phase 1 — the pre-contact acquisition census

Offline phase: **no simulator, no `src/` edit, no commit.** Tree read at HEAD
`61660a4`; the only files written are this one, `PREREG.md` and the read-only
census tool (`census.py` -> `census_out.txt`, both in this directory).

The question this phase answers: the two `closing anyway` rows are a deliberate
never-stop compromise (`tasks.py:9370`, `:9385`), and P44-P46 attribute the speed
cells' cost to it ("the pads close with the fruit 52-65 mm away"). **Does the
printed distance measure the acquisition error, and does it predict the
failure?** The answers are *no* and *not that number* — and the corpus names the
quantity that does.

---

## 1. The rows, the fields, and the code path

### 1.1 The two print strings

| branch | exact string (the `say()` prefix is `[fruit] `) | fields |
| --- | --- | --- |
| **finger** | `[fruit] [task]   openarm fingertips {N} mm from the fruit; closing anyway` | **one** field, `N = round(pad_error * 1000)` (0 dp). **No tick, no arm, no species, no attempt index.** |
| **axis** | `[fruit] [task]   openarm hand attitude not settled (1-cos={x:.4f}); closing anyway` | **one** field, the axis error `1 − cos(tool_z, −ẑ)` (4 dp). No tick, no arm. |

The parent `verbose` rows carry the same numbers one digit finer and do carry the
tick count:

```
[fruit] [task] coherent track {track_ticks} ticks: fingertip-to-fruit={pad_error*1000:.1f} mm
[fruit] [task] coherent axis: 1-cos={axis_error:.4f} (ok|FAILED)
```

`track_ticks` is **0 on every dynamic (never-stop) attempt** (`tasks.py:9256-9263`:
`FRUIT_DYNAMIC_TRACK` defaults to `"0"` when `dynamic_capture`), so the tick
field that does exist is the constant 0 — there is no per-close tick in either
`closing anyway` row. Any census that wants a tick has to reconstruct it from
the neighbouring rows (`dynamic descent: waited N ticks`, `dynamic catch-up:
residual=…`), which is what §2 does.

### 1.2 What `N` is measured against — and why it is a constant

The block is `tasks.py:9308-9396`, inside the scripted attempt
(`_run_impl` → the coherent track):

1. **Track** (`:9308-9318`): for `track_ticks` ticks the arm `ik_step`s toward
   `fruit + [0, 0, _pad_standoff(...)]`, then steps the sim. On the dynamic line
   `track_ticks == 0`, and `fruit` is **not** the fruit's live position: `:9264-9265`
   sets `aim = self._dynamic_aim(sample)` and `fruit = aim`. `_dynamic_aim`
   (`:6415`) returns the **station aim** (the fruit's measured x/height at the
   pick station; the R10 interception point when `FRUIT_REACH_ANYWHERE` is on).
2. **Fingertip and error** (`:9324-9328`):
   `fingertip = jaw_centre + R @ [0,0,finger_len]` (`finger_len` = 0.060), and
   `pad_error = |fingertip − fruit|` = `|fingertip − aim|`.
3. **Attitude servo** (`:9340-9354`): up to `FRUIT_AXIS_SERVO` = 180 ticks of
   `ik_step` until `1 − cos ≤ FRUIT_AXIS_TOL` = **0.01**; prints the axis row.
4. **The two "closing anyway" branches**:
   * `axis_error > 0.01` (`:9362`): OpenArm → **print only**; the pad-hand variant
     sets `coherent = False`.
   * `pad_error > FRUIT_COHERENT_FALLBACK` (**default 0.020 m**, `:9375`):
     OpenArm → **print only**; the pad-hand variant drops to the assisted pad
     frame. `pad_error ≤ 0.020` (the `else`, `:9395`) is the **only** place
     `self._coherent[arm] = True`.

**So the fallback threshold is 20 mm and the OpenArm branch has no fallback to
take** — the jaws are the only grip, so the branch is *print-only by
construction*. That is what "closing anyway" means: the attempt proceeds and the
lift check decides.

**The number is a geometry constant, not an error.** At the print, the arm sits
at the pre-pose/hover target `premove = aim + [0,0,standoff] + [0,0,hover]`
(`:9274-9297`, `standoff = finger_len + pad_lift`, `hover = FRUIT_DYNAMIC_HOVER`
= **0.060**). The fingertip is `finger_len` *below* the jaw centre, so

```
pad_error(nominal) = hover + pad_lift = 0.060 + 0.010 = 70 mm
```

— `finger_len` cancels. The measured 58-65 mm is that 70 mm minus 5-12 mm of
pre-move/settle sag. **`N` does not depend on where the fruit is**: on the
dynamic line it is the distance from the fingertips to the *station*, sampled
before the hover, the descent and the catch-up — i.e. the commanded hover
clearance.

The corpus agrees exactly: **317 of 317 attempted closes print the row**
(`census_out.txt`; the only three attempts without one are `no eligible fruit`
skips, which never close), the whole 317-row population spans **58-65 mm**
(p50 60, p90 63), and the **axis branch never fires — 0 rows in 317** (the
attitude servo converged to `1-cos ≤ 0.01` on every attempt; 0 `FAILED` rows).

### 1.3 The consequence that the P42 note already recorded

Because `pad_error` (≈60 mm) is *always* above the 20 mm fallback, the `else` at
`:9395` is unreachable on this line, so **`self._coherent[arm]` is never set
True — 0/317**. That is precisely the P42 amendment's observation ("`False`
60/60 legs; the flag is only set True on the `pad_error <= FRUIT_COHERENT_FALLBACK`
branch, never reset on the OpenArm's closing-anyway branches"). The census
supplies the general form: it is never *entered*, on any attempt, and it is a
property of the standing distance, not of the attempt.

---

## 2. Frequency and distance, and whether the distance predicts the failure

### 2.1 Method

`census.py` parses the scripted logs and pairs every row with its attempt
(single-arm: exact, by the `[run] attempt N:` block; two-line: ordinal, the k-th
row with the k-th `[biarm] result`, flagged `ordinal` because the two arms'
blocks interleave). It extracts three per-attempt quantities:

* **`tip`** — the `closing anyway` fingertip number (§1: the hover clearance);
* **`catch`** — `dynamic catch-up: residual={r} mm (tol 6 mm)`, the **real**
  pre-close error: the catch-up loop's own break test, `|fingertip − (fruit +
  pad_lift)|` measured against the **live fruit**, after up to **200 ticks**
  (`FRUIT_DYNAMIC_CATCH_TICKS`) at a **6 mm** tolerance (`FRUIT_DYNAMIC_CATCH_TOL`);
* **`[carry]` onset** (`contacts@onset`, `force@onset`, `gap_start`) where
  `FRUIT_CARRY_DIAG=1` is on.

### 2.2 Rows per battery

| battery | logs | attempts | rows | row rate | placed | cnp | no-grasp | skip |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| shipped (`p41/p2/accept_profile`, `p39/p3/pear_C`) | 2 | 20 | **19** | 19/19 closes | 12 | 7 | 0 | 1 |
| P44 speed (`p44/p2/*`, 16 measured logs) | 16 | 160 | **159** | 159/159 | 104 | 44 | 11 | 1 |
| P45 mass (`p45/p2/*`) | 10 | 100 | **99** | 99/99 | 59 | 40 | 0 | 1 |
| P46 two-line (`p46/p1/*`) | 4 | 40 | **40** | 40/40 | 32 | 0 | 8 | 0 |
| **pooled** | 32 | 320 | **317** | **317/317 closes** | 207 | 91 | 19 | 3 |

**There is no "attempts without a `closing anyway` row".** The comparison the
brief asks for is empty by construction: 100 % of closes print it, on every
battery, in every arm. It cannot be a rare event and its *presence* cannot be a
failure signal.

### 2.3 The print's distance, and the outcome

| battery | `tip` min / p50 / p90 / max (mm) |
| --- | --- |
| shipped | 59 / 60 / 63 / 63 |
| P44 | 58 / 60 / 63 / 65 |
| P45 | 59 / 60 / 63 / 65 |
| P46 | 58 / 59 / 62 / 64 |
| **pooled** | **58 / 60 / 63 / 65** (n = 317) |

Outcome against the print's number, pooled (bands; the whole population is
> 50 mm, so a "> 50 mm" cut is degenerate — every row is a hit):

| band | rows | placed | cnp | no-grasp |
| --- | --- | --- | --- | --- |
| ≤ 59 mm | 102 | 72 | 21 | 9 |
| 60-61 mm | 112 | 80 | 27 | 5 |
| 62 mm | 50 | 30 | 16 | 4 |
| ≥ 63 mm | 53 | 25 | 27 | 1 |

**The distance does not predict the failure.** The high band is the *better* one:
`≥ 63 mm` reads 25 placed / 1 no-grasp, `≤ 59 mm` reads 72 placed / 9 no-grasp.
Pooled `no-grasp | ≥ 62 mm` = 5/103 vs `| ≤ 60 mm` = 12/181: **Fisher exact
two-sided p = 0.61**. For the dominant failure class (`cnp`, 91/317 = 29 %) the
print's number is likewise flat (the `≥ 63 mm` band is 27 cnp against 25 placed,
the only mild association in the table, and it is a branch artefact — the four
P46 rows at ≥ 63 mm are all placed).

### 2.4 The distance that *does* separate, and its limit

`catch` (the live pre-close fingertip error) is bimodal with **nothing in
between**: min 5.4, p50 5.9, p90 6.0 mm (the loop's own 6 mm tolerance), then a
gap, then **219.6 / 245.8 / 251.0 / 480.6 mm**.

| cut | rows | placed | cnp | no-grasp | no-grasp rate |
| --- | --- | --- | --- | --- | --- |
| `catch > 6 mm` | **8** | 0 | 0 | **8** | **100 %** |
| `catch ≤ 6 mm` | **309** | 207 | 91 | **11** | **3.6 %** |

Fisher exact two-sided **p = 3.3e-11**: above the tolerance the attempt never
once grasped. But two caveats decide what it is worth:

1. **Coverage is 42 %.** 11 of the 19 no-grasp rows *converged* (5.4-6.0 mm) and
   still failed — the pads reached the fruit and lost it in the close/regrasp.
   The worked example is `p44/p2/amend_E_S1.log` attempt 1: catch-up 5.5 mm,
   `dynamic close: sustained contact after 22 ticks (force=9.24 N, span 70.1 mm)`,
   `kinematic grip closed to 6.17 cm around a 5.58 cm fruit` (i.e. 5.9 mm wider
   than the payload), two `re-seated on the moving fruit` rows, and the carry's
   onset at row 1 with `contacts@onset=0`, `sep 31.7 mm`, `gap_start 46.7 mm`,
   `force_min 0.00 N` — the pads closed **through** where the fruit had been.
   No distance guard reaches these.
2. **The 8 rows are 4 distinct attempt-events.** The two-line logs reproduce an
   attempt on both arms and across paired arms, and `S2` ran twice:

| distinct event | residual | where (rows) |
| --- | --- | --- |
| S2 acceptance attempt 1, kiwi, single arm | 219.6 mm | `p44/p2/accept_s5_S2` |
| S2 (amend re-run), same arm, same slot | 245.8 mm | `p44/p2/amend_F_S2` |
| two-line s5, kiwi, **left** | 251.0 mm | `p44/p2/twoline_s5_{C,S13}`, `p46/p1/twoline_s5_{C,U}` (4 rows) |
| two-line s6, kiwi, **right** | 480.6 mm | `p46/p1/twoline_s6_{C,U}` (2 rows) |

   The two-line pairs are the same attempt bit-for-bit through the acquisition
   (the C arm draws it too), so it is the **scenario's** event, not the cell's.

### 2.5 What the failing distances actually are

The 480.6 mm row is **2.4x the catch-up's own travel budget** (200 ticks =
200 mm at 0.12 m/s): a target that ends the loop 480.6 mm from the goal was
never inside the catch's reach, so this is a **hand-over timing / selection**
miss (the arm was handed a target far off the station and the 200-tick catch-up
could not fetch it), not a "the pads closed a few centimetres early" miss. The
same branch shows the geometry in words elsewhere — `p46/p1/twoline_s6_C.log`
prints `close: fruit drifted 379 mm off the pick centre (cross-belt); re-closing
on it where it is` — i.e. this scenario does present fruit far off the station.
(That line's arm attribution is ambiguous in the interleaved two-line log, so it
is quoted as the branch's shape, not as this attempt's datum. The
`dynamic catch-up: residual` row *is* per-attempt and is the number used above.)

### 2.6 The documentation correction this forces

P44 §5 and P46 §8 quote "fingertip-to-fruit **52-65 mm** at the close" as the
class signature and cite the `[carry]` fields beside it. Those 52-65 mm numbers
are **`sep@onset` / `gap_start`** — the **pad span** the jaws closed to — not a
distance to the fruit. The three quantities are distinct and must not be
interchanged:

| quantity | where | value on a failing attempt | value on a placed attempt |
| --- | --- | --- | --- |
| `closing anyway` number | `[task] openarm fingertips` | 58-65 mm (a constant) | 58-65 mm |
| pad **span** after the close | `[carry] sep@onset` / `gap_start` | 29.8-64.8 mm (closed on air or through) | 26.9-76.5 mm (closed around) |
| **miss distance** at the close | `dynamic catch-up: residual` | **219.6-480.6 mm** | 5.4-6.0 mm |

P44/P46's *verdicts* stand (the class is pre-contact acquisition, the grip is
clean, nothing is adopted) — but "the pads close with the fruit 52-65 mm away"
over-states the retrievability by 4-9x, and that is exactly what decides whether
a bounded wait can be the lever (§3).

---

## 3. The belt arithmetic, the close's own budget, and the never-stop constraint

Per-tick geometry: belt **0.12 m/s** (`assets.py:214`, `FRUIT_BELT_SPEED`);
control **120 Hz** (`tasks.py:53`, `CONTROL_DT = 1/120`) → **1.0 mm per tick**.

| fruit closing distance | ticks | seconds |
| --- | --- | --- |
| 20 mm | 20 | 0.167 |
| 35 mm | 35 | 0.292 |
| 50 mm | 50 | 0.417 |
| 200 mm (the catch-up's full horizon) | 200 | 1.667 |

**The close's own tick budget.** The dynamic close is a two-phase min-jerk ramp
(`tasks.py:9780-9900`): `FRUIT_DYNAMIC_CLOSE_FAST` = **24** + `FRUIT_DYNAMIC_CLOSE_LOAD`
= **60** → **84 ticks (0.70 s)** per close attempt, up to `FRUIT_CLOSE_ATTEMPTS`
= **2** attempts (168 ticks) when the cross-belt drift check re-closes. The
measured `close` block in the `[cycle]` rows is **1.18-1.22 s (142-146 ticks)**
— the ramp plus the catch-up that precedes it.

**The waiting already in the pipeline** (this is the number the guard competes
with):

| stage | budget | measured |
| --- | --- | --- |
| arrival wait before the descent | deadline-synchronised (`fruit dy ≤ deadline`) | `waited 53-87 ticks` (0.44-0.73 s) |
| **catch-up at the close entry** | **200 ticks / 6 mm** | 5.4-6.0 mm on 309/317; 220-481 mm on 8/317 |
| close ramp | 84 ticks (+84 on a re-close) | 1.18-1.22 s block |

**The never-stop constraint.** The belt is never stopped on this line: the supply
keeps an absolute schedule (`fruits.py`, the feeder's backlog re-base) and the
arm is already at the station (the descent is station-relative and
arrival-synchronised, `_dynamic_aim`). So a wait at the close is *free of
collision risk but not of physics*: the fruit keeps moving **1 mm per tick**, and
a wait only helps while the fruit is **upstream** of the pads. A fruit 200 mm
downstream moves 200 mm further away in the same 200 ticks.

**The convertible band.** A guard that waits up to `N` ticks can convert only a
miss whose distance is in `(threshold, threshold + N mm]` — for the registered
`35 mm / 40 ticks` that is **35-75 mm**. The corpus has **0 rows in 35-75 mm**
(§2.4: the mass is 5.4-6.0 mm, the next value is 219.6). The wait that would be
needed for the observed misses is **220-481 ticks (1.8-4.0 s)** — **1.1-2.4x**
the catch-up's own 200-tick horizon and **12-27 %** of a 15.0 s attempt — a
different lever, and not one the never-stop line can take at the station.

---

## 4. What this census settles, and what it hands to phase 2

1. **The `closing anyway` row is a standing-property print, not an event.** It
   fires on 317/317 closes with a 7 mm-wide value band that is the hover
   clearance (70 mm nominal, `hover + pad_lift`), measured against the *station*,
   before the hover and the descent. Its presence and its value carry **no**
   information about the outcome (Fisher p = 0.61), and the axis sibling is
   **dead** (0/317 — the attitude servo always converges).
2. **The fallback it names is unreachable:** `pad_error > 20 mm` is always true,
   so `self._coherent[arm]` is never set (0/317) — the P42 note's mechanism,
   generalised.
3. **The live pre-close error is the discriminator, and it is printed on every
   attempt:** `dynamic catch-up: residual`. Above its 6 mm tolerance: 8/8
   no-grasp; below: 11/309 = 3.6 % (p = 3.3e-11). But it explains only **42 %**
   of the no-grasp class, and its failing values are **220-481 mm**, not 52-65.
4. **The distance is not the trigger for the guard as registered.** The
   convertible band (35-75 mm) is empty in 317 closes, so a `35 mm / 40 tick`
   guard is predicted to fire on **8/317 = 2.5 %** of closes and convert **~0**;
   the lever that the census *does* point at is the **hand-over timing /
   selection** (a target 2.4x the catch-up's reach budget away) plus the
   **11 converged close losses**, neither of which is a distance wait.
   `PREREG.md` registers the guard anyway —
   with that prediction written down before the run, and with its own
   instrumented trigger count so the phase's verdict is measured, not inferred.

Evidence: `logs/p47/census.py` (the reader), `logs/p47/census_out.txt` (its full
output), and the counts above; every log cited is an existing artefact of
P39/P41/P44/P45/P46.
