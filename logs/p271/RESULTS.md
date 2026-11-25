# P271 results: the re-registration **passes its letter** and the class effect **does not reproduce**

**2026-11-25, `logs/p270/` (the C arm completes the pair).** Both arms with the landing trace.
**Nothing adopted**, and the tolerance's class effect is now **unresolved**.

---

## 1. The two arms, both with the trace

0.12, seeds 907/908, 20 picks each, `FRUIT_PLACE_TRACE=1` + `FRUIT_CARRY_DIAG=1` +
`FRUIT_TRACK_DIAG=1` on **both** arms:

| arm | placed | catches | **true stalls** | place traces | `on_belt` | `grasped=True placed=False` |
|---|---|---|---|---|---|---|
| **C, 6 mm** | **34/40** | 37 | **5 (14 %)** | 34 | **34/34** | **0** |
| **T, 7 mm** | **34/40** | 38 | **4 (11 %)** | 34 | **34/34** | **0** |

## 2. The registered endpoints both pass

* **P1** (T's true-stall rate **<= 15 %**): **11 %** -> PASS.
* **P2** (count `>= C - 2` and **no place-leg loss with the payload present at the release**):
  **34 >= 32** and **34/34 `on_belt` on both arms, 0 `grasped=True placed=False`** -> PASS.
* **P3** (report): the cycle is flat in every cell of this arc.

**So the re-registration passes.** And it should not be read as a win, for the reason in §3.

## 3. The comparison is a **draw**, and that is the finding

**14 % against 11 %** - 5 of 37 catches against 4 of 38 - is a difference the batch cannot
separate. **P269 measured 19 % -> 9 % on the same seeds without the trace.** With the trace on
(the branch differs by construction: it adds per-place rows) the same pair of arms reads
**14 % -> 11 %**.

**So the tolerance's class effect did not reproduce under the trace instrumentation**, and the
honest state is **unresolved**: one batch says it halves the class, the other says it moves it
3 points inside a 40-pick draw.

**And the PREREG's P1 was written as an absolute bar** (`T <= 15 %`) rather than a
**difference**. That is a **design defect** for a quantity that varies by branch - it can be
passed by a branch where *both* arms are low. It was, here: C itself read 14 %, so "T <= 15 %"
would also have passed with the knob **off**.

## 4. Verdict

| | |
|---|---|
| the registered endpoints | **pass** |
| the mechanism (the difference) | **does not reproduce** |
| the decision | **nothing adopted** - the tolerance stays at 6 mm, no default, no reference, no store |
| the class effect | **unresolved** (19->9 without the trace, 14->11 with it) |
| what would settle it | a **difference** endpoint with a paired design (both arms, same seeds, trace **on** for both) at >= 2 fresh seeds - and a **powered** one, because a 3-point difference at 37-38 catches is not separable |
| what it would then owe | PREREG's four items: two more seeds, the two-line gate, both references, every store |

**The record's read rule, added**: an **absolute** bar on a branch-dependent class rate is not
a test of a lever - the control arm's own level can satisfy it. Register the **difference**, and
register it **powered**.

## 5. Where the 0.12 step stands, after the whole arc

| | |
|---|---|
| 0.12 continuous, mixed pool | **72.5-85 %** across draws |
| the two classes | **grip/hold** (hardware, `logs/p42/SIM_LIMIT.md`) and the **free-space chase** (arrival side or the y-axis, P268) |
| the tolerance (P267/P269/P271) | the class effect is **unresolved**; nothing ships |
| the clock and the force exits (P266/P268) | **closed** (they truncate conversions / cannot see the class) |
| the cycle work (P249-P263) | **-28 %** on the attempt, at 0.08 **99.3 %** placed - and it does not touch 0.12's success (P264) |

## 6. No-harm

No `src/` or `configs/` change (the tree is P268's: `tasks.py` `141cd178`, references
**`61fb5202` / `61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `accept.sh` stands at P268's **459/459 +
`fingerprint: matches`**. Evidence `logs/p270/`.
