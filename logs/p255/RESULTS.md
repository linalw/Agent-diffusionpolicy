# P255 results: the tail is **one instance**, not the smallest size class - lychee-only reads 20/20

**2026-11-25, `logs/p255/`.** A one-species (lychee) continuous cell at 0.08, the same
recipe. **No `src/` change.** It **corrects** P250/P251's reading of their own data.

---

## 1. The cells

`FRUIT_SUPPLY_SPECIES=lychee`, `v=0.08`, continuous, 10 picks per seed:

| seed | placed | diameters drawn |
|---|---|---|
| 903 | **10/10** | 2.8, 3.4, 3.7, 3.0, 3.1, **2.8**, 3.3, 2.9, 3.3, 3.3 |
| 904 | **10/10** | 3.6, 3.1, 3.5, 3.7, 2.9, 3.0, 3.6, 3.5, 3.7, 2.9 |
| **pooled** | **20/20 = 100 %** | 2.8 cm drawn **twice, both placed** |

## 2. What that corrects

P250 concluded that the residual class is **"the pool's smallest instance"** and P251
carried that forward; the size table in `docs/SINGLE_ARM_SPEC.md` reads **0-4 cm =
72/90 = 80 %**. **Both readings are now wrong in their causal claim.**

* **The 2.8 cm size is not the problem**: a dedicated lychee pool draws **2.8 cm twice
  and places both**, and the class as a whole reads **20/20**.
* **The 17 failures P250 counted are still one body**: every one of them was
  `d=2.8 cm, arm=left`, i.e. **seed 901's first draw** - and seeds 903/904's mixed-pool
  cells (P253) place **10/10 each**.
* So the tail is a **per-draw instance**, and the 80 % bucket is **that instance's
  incidence in the mixed corpus**, not a size effect.

**What survives from P250/P251 unchanged**: the failure *chain* was measured on that
body and is a real mechanism - the catch-up ends 39-46 mm off, the `grip` block reads
**4.53 s** (two failed re-grasps) against **1.58 s** on placements, the arm's joint lag
is **0.18-0.27 rad** against 0.11, with no limit clipping, no singularity, no
start-offset separation, and the gain is not the actuator. **What does not survive is
attaching it to a size class.**

## 3. What it means for the objective

| | |
|---|---|
| **0.08 deployment, mixed pool** | **49/50 = 98 %** (5 cells, 4 seeds; P253) |
| **0.08 deployment, worst species only (lychee)** | **20/20 = 100 %** (2 cells) |
| the residual tail | **one body per pool draw**, ~43 % failure when drawn |
| **generalisation claim** | the cell is **not** size- or species-limited in the measured range (2.8-7.0 cm); it has a **per-instance tail** |

**The honest sentence for the handover page**: at 0.08 the cell places **98 % of a mixed
pool and 100 % of the hardest single species**, and the one repeatable loss is a
**specific awkward draw** that fails about half the times it appears - **not** small
fruit, and **not** a species.

## 4. Read rule added

**A size bucket is not a class** when the same size passes in a different pool: before
quoting a bucket, run the one-species cell for that species - it is 10 minutes and it
separates "this size" from "this body". P250's own census could not separate them
(the 2.8 cm size appeared **only** at seed 901's first position in the mixed corpus),
which is exactly the confound a one-species pool removes.

## 5. Pins

No `src/`/`configs/` change (the tree is P254's: `rl_env.py` with the default-off blend
knob, `tasks.py` `b68ac8d1`, references **`61fb5202` / `61fb5202` / `18b101bf`**, ckpt
`p227_panda156`); `accept.sh` stands at P254's **459/459 + `fingerprint: matches`**.
Evidence `logs/p255/`.
