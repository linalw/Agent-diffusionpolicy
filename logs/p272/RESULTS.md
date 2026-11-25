# P272 results: the deployment recipe holds under **both** disturbances - 39/40 with the loss in the known class

**2026-11-25, `logs/p272/`.** The two disturbance cells **on the current deployment recipe**
(they had only ever been measured per-episode, on the pre-P249 recipe). **No `src/` change.**

---

## 1. The gap this closes

`docs/SINGLE_ARM_SPEC.md` quotes the disturbances from **P232** (`±75 %` belt wave, **11/12**)
and **P234** (lateral band, **12/12**) - both **per-episode** and both measured **before** the
throughput arc changed the cycle by 28 %. The objective asks for disturbance tolerance
explicitly, so the deployment shape has to carry its own cells.

## 2. The cells

`scripts/290_single_arm_continuous.sh`, `v = 0.08`, seed 907, **20 picks**, one continuous
episode:

| cell | setting | placed | `[cycle]` | `gap` | losses |
|---|---|---|---|---|---|
| **A, belt wave** | `FRUIT_BELT_WAVE_AMP=0.06` `_HZ=0.5` (**0.02-0.14 m/s**, ±75 %) | **19/20** | **9.61 s** | 285 | 1 - `fruit did not follow the gripper` (kiwi 5.5 cm) |
| **B, lateral band** | `FRUIT_SUPPLY_X_MIN=0.17` `_MAX=0.39` | **20/20** | **9.66 s** | 257 | 0 |
| **pooled** | | **39/40 = 97.5 %** | 9.6 s | | **the one loss is the grip class** |

**Nominal for comparison**: **139/140 = 99.3 %** at **9.9 s** (P261/P262).

## 3. What it says

* **The disturbances cost nothing measurable**: 39/40 against the nominal's 139/140, and the
  single loss is the **grip/carry** class (`grasped=False`, `fruit did not follow the
  gripper`) - the class that is the record's hardware question (`logs/p42/SIM_LIMIT.md`), not
  a disturbance effect.
* **The cycle does not move under the wave** (9.61 s against the nominal's 9.9 s, both inside
  the cell-to-cell spread) - which is P257's finding **restated under a ±75 % speed
  disturbance**: the attempt is the arm's own work, so a varying belt changes *when* the fruit
  arrives, not how long the pick takes.
* **The per-episode cells agree** (P232's 11/12 and P234's 12/12), so the recipe change did not
  buy or cost tolerance.

**The honest caveat unchanged**: one cell each, one seed; the nominal's own cells span 9.5-10.0 s
and 139/140, so "costs nothing" is a **draw**, not a proof of zero.

## 4. Where the delivered spec stands

| | |
|---|---|
| **0.08 continuous, nominal** | **139/140 = 99.3 %**, attempt 9.9 s, **4.3-5.0 picks/min** (the `gap` is bimodal) |
| **0.08 continuous, belt wave ±75 %** | **19/20**, cycle **9.61 s** |
| **0.08 continuous, lateral band 0.17-0.39** | **20/20**, cycle **9.66 s** |
| 0.08, hardest single species (lychee) | 20/20 = 100 % (P255) |
| latency | 66 ms = 8 mm in-loop; the cell absorbs <= 133 ms (P228) |
| 0.12 continuous | 72.5-85 %, two classes named (P264/P268/P271) |
| cycle | 13.55 -> 9.7 s (**-28 %**, P249-P263) |

## 5. No-harm

No `src/` or `configs/` change (the tree is P268's: `tasks.py` `141cd178`, references
**`61fb5202` / `61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `accept.sh` stands at P268's **459/459 +
`fingerprint: matches`**. Evidence `logs/p272/`.
