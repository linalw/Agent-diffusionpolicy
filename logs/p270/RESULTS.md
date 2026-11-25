# P270 results: with the landing trace on, **every release lands** - the clause's corrected form passes where it can be read

**2026-11-25, `logs/p270/`.** Two cells that answer P269's open question as far as it can be
answered from a cell. **No `src/` change.**

---

## 1. Why these cells

P269 failed its P2 on **one** `grasped=True placed=False` row, and that row could not be
classified: `placed` is `bool(cfg.on_output_belt(pos))` at the sample, so a payload lost in the
place leg and one released off-target read the same `False`, and neither cell carried
`FRUIT_PLACE_TRACE`. **The re-registered clause is "no place-leg loss with the payload present
at the release", and `FRUIT_PLACE_TRACE` reports exactly that (`on_belt` per place).**

## 2. The cells

0.12, the tolerance's arm (`FRUIT_DYNAMIC_CATCH_TOL=0.007`), seeds 907/908, 20 picks each,
with **`FRUIT_PLACE_TRACE=1` + `FRUIT_CARRY_DIAG=1` + `FRUIT_TRACK_DIAG=1`**:

| cell | placed | place traces | **`on_belt`** |
|---|---|---|---|
| `T_tr_s907` | **18/20** | 18 | **18 True / 0 False** |
| `T_tr_s908` | **16/20** | 16 | **16 True / 0 False** |
| **pooled** | **34/40 = 85 %** | **34** | **34 True / 0 False** |

**Every attempt that reached the place leg landed on the output body**, and **no
`grasped=True placed=False` row appeared at all** - the losses (2 and 4) are all upstream of the
place.

**The landing height corroborates the bins cell**: `release_bottom = -211.8 / -211.9 mm`
against the belt top, i.e. the payload's bottom sits **38 mm above the 1.10 m bin floor** -
P227ac measured **39-40 mm** for the accompanied descent, so the trace is reading the same
geometry the record already has.

## 3. What it settles, and what it does not

**Settled**: the class the P2 clause guards against - **a place-leg loss with the payload
present at the release** - **is absent** in the arm where the clause failed, at the same seeds,
with the instrument that can see it (34/34 releases on the belt).

**Not settled**: the original row's class. It **did not recur** in these cells (the trace adds
per-place rows, so the branch differs), so it stays **unclassified** - which is the honest
state, and P269's withdrawal of the first reading stands.

**And it does not license the tolerance**: this batch is the **T arm only**. The PREREG's shape
needs both arms (the count is a decision rule and the class rate a claim); a **C arm with the
same trace** (2 more cells) is what a full re-registration would read. Nothing ships on a
clause read alone.

## 4. The state of the tolerance, stated once

| | |
|---|---|
| the **class** effect | measured at the registered power: true stalls **19 % -> 9 %** (P269, 40/arm) |
| the **quality** clause | passes in its corrected form where readable (**34/34 on the belt**, this phase) |
| the **count** | a draw (30 vs 32 of 40) |
| **the decision** | **not adopted** - the tolerance stays at 6 mm; a full re-read wants the C arm with the trace, and an adoption would then owe the four items PREREG lists (two more seeds, the two-line gate, both references, every store) |

## 5. No-harm

No `src/` or `configs/` change (the tree is P268's: `tasks.py` `141cd178`, references
**`61fb5202` / `61fb5202` / `18b101bf`**, ckpt `p227_panda156`); `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `accept.sh` stands at P268's **459/459 +
`fingerprint: matches`**. Evidence `logs/p270/`.
