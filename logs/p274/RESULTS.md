# P274 results: the deployment cell holds over **40 consecutive picks** - 80/80 on two seeds

**2026-11-25, `logs/p274/`.** The horizon question the record had never asked: its longest
continuous cell was **20 picks** (P253/P257) and **26** once (P227ab). A real cell runs for
hours, so the long-horizon stability - repeated pool recycling, supply fatigue, drift - has to
be measured. **No `src/` change.**

---

## 1. The cells

`scripts/290_single_arm_continuous.sh 40 <seed> 0.08`, one continuous episode of **40 picks**
each, two seeds:

| cell | placed | cycle | `gap` | s/pick | picks/min | discharged |
|---|---|---|---|---|---|---|
| seed 907 | **40/40** | **9.69 s** | 257 | 11.83 | **5.07** | 39 |
| seed 913 | **40/40** | **9.71 s** | 324 | 12.41 | **4.83** | 39 |
| **pooled** | **80/80 = 100 %** | 9.70 s | - | - | **4.8-5.1** | 78 |

## 2. What it shows

* **No drift over the horizon**: the attempt cycle is **9.69 / 9.71 s**, i.e. identical to the
  20-pick cells (9.6-9.9 s), and the per-decile placement deltas are **flat** (8/9/9/9 on both,
  where the first "8" is the boundary print starting at pick 2).
* **The pool recycles cleanly**: **39 `discharged to the bin`** per cell, **0 recirculated** -
  16 fruits cycling **2.5 times** each through the line with no stall, no lost slot and no
  accumulation.
* **The rate is the `gap`'s, not the cycle's**: 257 against 324 ticks is the record's bimodal
  `gap` again (P269's read rule) - **5.07 vs 4.83 picks/min** on the same 9.7 s attempt. Quote
  the range, never a point.

## 3. Where the delivered spec stands

| | |
|---|---|
| **0.08 continuous, nominal, 20 picks** | 139/140 = **99.3 %** (P261/P262) |
| **0.08 continuous, nominal, 40 picks** | **80/80 = 100 %** (this phase), **4.8-5.1 picks/min** |
| 0.08 continuous, belt wave ±75 % | 19/20, cycle 9.61 s (P272) |
| 0.08 continuous, lateral band 0.17-0.39 | 20/20, cycle 9.66 s (P272) |
| 0.08, hardest single species (lychee) | 20/20 = 100 % (P255) |
| 0.12 continuous | 72.5-85 %, two classes closed as software levers (P264/P268/P273) |
| cycle | 13.55 -> **9.7 s (-28 %)** |

**Honest caveat**: two seeds, one cell each; "no drift" is over **40 picks** per cell (2.5 pool
cycles), not over an hour. The recycled-pool behaviour is the part that could still bite at
100+ picks, and the instrument for it (per-cycle identity of the recycled body) is not in place.

## 4. No-harm

No `src/` or `configs/` change (the tree is P268's: `tasks.py` `141cd178`, references
**`61fb5202` / `61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `accept.sh` stands at P268's **459/459 +
`fingerprint: matches`**. Evidence `logs/p274/`.
