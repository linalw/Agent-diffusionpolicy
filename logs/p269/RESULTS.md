# P269 results: the tolerance halves the true-stall rate at the registered power - and fails P2 on one row of a **different class**

**2026-11-25, `logs/p269/`.** The powered cell PREREG'd for the catch exit tolerance
(6 -> 7 mm): **fresh seeds 907/908, 20 picks x 2 cells = 40 per arm**, both arms
instrumented. **Verdict: P1 PASS, P3 flat, P2 FAIL by its letter -> nothing ships.**

---

## 1. The cells

| arm | placed | catches | **true stalls** | slow-converged | `>= 100` ticks | cycle |
|---|---|---|---|---|---|---|
| **C** (6 mm) | **32/40 = 80 %** | 37 | **7 (19 %)** | 2 | 9 | 9.70 s |
| **T** (7 mm) | **30/40 = 75 %** | 34 | **3 (9 %)** | 3 | 8 | 9.63 s |

Per cell: `C_s907 17/20`, `C_s908 15/20`, `T_s907 15/20`, `T_s908 15/20`.

## 2. The registered verdicts

**P1 (the class endpoint) PASSES at the registered power.** The true-stall rate is
**9 % against 19 %** - 3 of 34 catches against 7 of 37. This is the strongest statement the
record has about the 0.12 acquisition class: **an exit 1 mm wider halves it**, and it
reproduces P267's single-draw reading (29 % -> 8 %) at a fresh pair of seeds.

**P2 FAILS by its letter**, on the second of its two clauses:

* the count clause **passes** - `T 30 >= C 32 - 2`, and the difference is a draw (p ~ 0.8);
* the **"no place-side loss"** clause fails: T has **one** `grasped=True placed=False` row
  (`T_s908` episode 8, kiwi 5.3 cm, right arm) and C has none in this batch.

**P3 (the clock, report)** is flat: cycle **9.63 vs 9.70 s**, `s/pick` **12.80 vs 12.85**.

## 3. That one row is **not** the class the clause was aimed at

The row's own `notes` carry **only** the intercept trigger - **no failure note** - and its fire
was **late**: `dy=-4.0 cm`, `t_arrive=0.00 s`, i.e. the fruit was already inside the window
when the trigger fired. That is the record's **`grasped, not placed (no note)`** bucket, which
P100's A4 and P103's G5 both found **in controls**, not a landing miss.

The clause was written to catch *"the 1 mm further offset at the close is costing landings"* -
a place-leg loss **with the payload present at the release**. This row is the carry class,
five seconds earlier in the attempt, on an attempt whose geometry was already lost at the
fire. **So the clause's letter fails and its intent is not implicated** - and the record's
rule is that the letter stands: **the tolerance stays at 6 mm.**

**The clause is recorded as badly designed** (the P100 A4 / P103 G5 / P262 precedent): a
`grasped=True placed=False` bucket mixes "lost in the hand" with "missed the target", so the
correct form is **"no place-leg loss with the payload present at the release"**.

## 4. What this leaves

| | |
|---|---|
| **the class lever is real** | the 7 mm exit halves the true-stall rate at **40/arm, fresh seeds** (19 % -> 9 %) |
| **it cannot ship on this cell** | P2's letter failed on one row of the carry class |
| **the re-entry is one clause** | re-register P2's second term as a **landing miss** (payload present at the release) and repeat at **these same seeds** - the cells are on disk, so the count/class read is unchanged and only the clause's reading is re-scoped |
| **the tolerance stays 6 mm** | no default moves, no reference moves, no store re-baselined |

**And the honest sentence about the 0.12 step is unchanged**: **72.5-85 %** across draws, the
grip/hold class (hardware) and the free-space chase (arrival side or axis, P268), with the
tolerance's class effect measured but unpriced.

## 5. No-harm

No `src/` or `configs/` change (the tree is P268's: `tasks.py` `141cd178`, references
**`61fb5202` / `61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `accept.sh` stands at P268's **459/459 +
`fingerprint: matches`**. Report: `logs/p269/p269_report.py` (MISSING is not zero);
method: `logs/p269/METHOD.md`.
