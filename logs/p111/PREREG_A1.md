# P111 pre-registration A1 - the `off0` reference, corrected from the control cells

Pinned **before any treatment cell** (`T1`/`T2`/`S1`).  The only cells that exist
at pin time are the two **replay** controls (`C_s5`, `R_s5`), which are
byte-identical to `logs/p108/{S,E}_s5.log` (621/621 and 531/531 `[fruit]` lines,
the phase's rows dropped; the 19 `[cage]` rows identical with `off0`/`off`
stripped).  The md5 of this file is appended to `PREREG.md5`.

## What was wrong

`PREREG.md` §1 and §5 describe the arrival as **8.8 mm** (P108's close-time aim
census).  That number is the **aim** offset - the distance between the commanded
grip point and the payload *before* the catch-up - and the phase's own instrument
(`[cage] off0=`, new) measures the offset **at the close's start**, i.e. after the
catch-up has converged to its 6 mm tolerance.  On the two control cells:

| class | `off0` p50 | `off` p50 |
|---|---|---|
| normal rows (19 of 30) | **2.4-4.9 mm** | 0.7-3.5 mm |
| the jam rows (11 of 30, `aper` 88-89 mm, `F` up to 2920 N) | **208-400 mm** | 226-330 mm |

So the phase's arrival is **2-5 mm**, not 8.8 mm, and the algebraic ratio the
falsifier asks for (1.5x below the rigid arm's median) is a **stronger** test than
the text implied, because the starting point is smaller while the predicted
terminal offset `(2 mu - 1) s` is unchanged (it depends on `s`, not on `off0`).

## What changes, and what does not

**Unchanged**: every arm, seed, attempt count, endpoint, guard, the decision rule
(§4) and the falsifier **rules** F1-F5.

**Changed, descriptive only**: F1's reference.  The comparison is the **rigid
arm's own `off` distribution on the same seeds** (pooled, per-arm medians), not
the 8.8 mm figure.  F5's predicted absolute value stands as registered
(0.8-1.3 mm) and is expected to **fire**: `off` is measured to the ring's axis,
which the task commands at `payload + v*lead` (`FRUIT_DYNAMIC_TRACK_LEAD` 0.18 s
-> 21 mm downstream at 0.12 m/s), so `off` carries a *tracking* floor the 1-D
static model has no term for.  A fired F5 is therefore a statement about the
instrument's floor, and it is reported as such - it does not retract F1, which is
a *relative* read across arms under the same command law.

## The one addition to the read (no rule changes)

Because `off` carries that floor, the report also quotes:

* **`off - off0` per attempt** (the offset's *change* over the close: negative =
  the payload moved toward the axis, positive = it was carried away).  This is the
  cleanest of the three centring numbers and it needs no new read.
* **`bat_rel`** (P107's launch measure: the payload's displacement minus the
  belt's own travel over the close) as the *launch* endpoint beside `off`.

Both are arithmetic on data the `[cage]` row already carries.
