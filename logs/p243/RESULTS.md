# P243 results: the axis-aware exit recovers the 1.44 s with no quality price - and the runaway is an x excursion, not the offset

**2026-11-25, `logs/p243/`.** One default-off knob (`FRUIT_CATCH_TOL_AXIS`), 12
attempts, both seeds. **The 200-tick tax is gone on 11 of 12 and 11/12 placed.**

---

## 1. The cells

`v=0.08`, `FRUIT_CYCLE_REPORT=1` + `FRUIT_TRACK_DIAG=1`, seeds 901/902 x 6,
`FRUIT_CATCH_TOL_AXIS=1` (exit when `|y| <= 6 mm` and `|z| <= 10 mm`).

| | shipped (P239/P240) | **axis-aware exit** |
|---|---|---|
| `catch ticks` | **200** every attempt | **21-42** on 11 of 12 (median **23**), one 69 |
| residual components | `(y=+0.5, z=-6.6)` | `(y=-5.2..-5.8, z=-4.4..-8.7)` |
| `seat` | **1.67 s** | **0.17 / 0.17 / 0.17 / 0.17 / 0.18 / 0.19 / 0.21 / 0.28 / 0.32 / 0.34 / 0.57 s** |
| placed | 6/6 (and 6/6 in P242's FF cells) | **11/12** |

**P1 PASSES** (the loop exits on its criterion, not on the budget), **P3 PASSES**
(11/12), **P4 PASSES**: `seat` 1.67 -> **~0.2 s**, i.e. **-1.44 s of ~13.3 (-11 %)**,
at both seeds, **without moving the command**.

## 2. P2 falsified, and the falsification is the useful part

The registration predicted **zero runaways** here on the argument that P242's
runaways came from the 6.6 mm command offset. **There is one runaway - with the
command byte-identical to the shipped one:**

```
ticks=69 residual=97.2mm (x=-96.9 y=+4.6 z=-7.0)
```

**`x = -96.9 mm`.** Every normal attempt reads `x = -0.1 .. -3.1`; the rare event is
a **97 mm across-belt excursion**, with `y` and `z` ordinary. So:

* **P242's association was spurious**: the runaway class is not the offset's, and it
  is present on the shipped command (it simply had no instrument printing the
  components before P241, so the two P242 instances could not be inspected).
* **The class is `x`**, a direction neither the belt lead (y) nor the droop (z)
  touches - a separate object, now named, with the `[catch]` components row as its
  instrument. Frequency so far: **3 in 42 attempts** across the three cells that
  print it (P241 1/6, P242 1/12, P243 1/12), i.e. **~7 %**, and it costs 0-1
  placement per occurrence.

## 3. The condition the win depends on, stated

The axis exit works **because `y` at 0.08 m/s is already 5.2-5.8 mm, inside the
6 mm tolerance** - the loop was *only* ever blocked by `z`. It is therefore a
**speed-dependent** recovery: at a higher belt the y-lag grows (P240 measured 6.6 mm
at 0.08 for the *lead* case; the following lag scales with `v`), `|y| <= 6` stops
holding, and the exit reverts to the budget. **The lever is not a general fix for
the loop; it removes the one term that was unreachable at this speed.**

## 4. What this closes, and the honest ranking

| lever | recovers | price |
|---|---|---|
| **axis-aware exit (this phase)** | **-1.44 s**, `seat` 1.67 -> 0.2 | **none observed**: 11/12 placed, command untouched |
| command offset (P242) | -1.44 s | showed the same 7 %-class runaway; **no longer distinguishable from this one**, so the offset has **no advantage** and is the worse lever (it moves the command) |

So the record's recommendation is the **axis-aware exit**, default off until a
powered cell (12 attempts cannot certify 11/12 against 11-12/12), and the offset
is demoted.

**The x excursion is now the open object** on this axis: ~7 %, 97 mm, and it costs
the full budget plus sometimes a placement. Its instrument exists (the components
row); its mechanism does not.

## 5. Pins

`tasks.py` **`58460874`** (the axis exit), `rl_env.py` `TASKS_MD5` follow;
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156`. Evidence `logs/p243/{PREREG.md, axis/}`.
