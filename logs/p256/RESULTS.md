# P256 results: the instance's **mass and friction do not separate** the outcome - the tail is broader than one body

**2026-11-25, `logs/p256/`.** One new default-off instrument
(`FRUIT_INSTANCE_DIAG=1`) and two cells at 0.08. **Nothing adopted.** The instrument
delivers `FruitSample`'s own `mass` and `friction` (no new simulator read).

---

## 1. Why this instrument

P255 showed a 2.8 cm lychee placing 2/2 in a different pool, which removed **size** as
the term and left "the draw" as the candidate. `FruitSample` already carries `mass` and
`friction`, so one print per pick answers the follow-up question - **is the tail a
physical draw?** - at zero read cost:

```
[inst] idx=3 sp=lychee d=2.8cm mass=8.3g mu=0.62 grade=A
```

## 2. The cells (0.08, continuous 6 picks, diag on - **no rate is claimed**)

**seed 901, 4/6:**

| idx | species | d | mass | mu | outcome |
|---|---|---|---|---|---|
| 3 | lychee | 2.8 | **8.3 g** | 0.62 | **fail** |
| 9 | tomato | 5.1 | **44.2 g** | **0.53** | **fail** |
| 0 | strawberry | 4.0 | 19.2 g | 0.69 | pass |
| 11 | apple | 6.3 | 90.7 g | **0.49** | pass |
| 14 | orange | 6.6 | 109.4 g | 0.81 | pass |
| 2 | peach | 5.8 | 69.7 g | 0.79 | pass |

**seed 903, 6/6:** strawberry 3.2 cm / 9.9 g / 0.84, pear 6.5 / 102.9 / 0.67,
peach 5.9 / 72.4 / 0.72, peach 6.7 / 105.0 / 0.61, lychee 3.8 / 19.9 / 0.84,
tomato 6.5 / 93.9 / 0.60 - **all placed**.

## 3. The result is a **negative**, and it is informative

**Neither parameter separates:**

* **mass**: the failures are **8.3 g** and **44.2 g**; the passes span **9.9-109.4 g**,
  including a **9.9 g** strawberry - i.e. a *lighter* fruit than one failure placed.
* **friction**: the failures are **0.62** and **0.53**; the passes span **0.49-0.84**,
  including a **0.49** apple - i.e. a *slipperier* fruit than one failure placed.
* **size and species**: unchanged from P255 - a 2.8 cm lychee places, and the 5.1 cm
  tomato fails.

**And it corrects P255's scope**: that phase said "the residual is a per-instance tail"
on the strength of the lychee census. **The 5.1 cm tomato failing here shows it is not
one body** - the corpus's 31 failures split **17 on the 2.8 cm lychee draw** and **14
across kiwi (6), strawberry (3), peach (2), orange/tomato/apple (1 each)**, so the
2.8 cm lychee is a **concentration, not the class**.

**The honest statement**: the tail is **not** predicted by any parameter this project
can read off a fruit (size, species, mass, friction). P250's mechanism work stands - a
drive-tracking stall that ends the catch-up 39-46 mm off and burns two re-grasps - but
**which** attempts enter that stall is not a property of the fruit's published numbers.

## 4. What that means for the objective

| | |
|---|---|
| 0.08 deployment, mixed pool | **98 %** (49/50, P253) |
| 0.08, hardest single species | **100 %** (20/20, P255) |
| the residual | **not** size, species, mass or friction - a per-attempt stall whose trigger is unidentified |
| what is left to try | a **per-attempt** instrument (the stall's onset, not the fruit's labels) - the trace exists (`FRUIT_CATCH_TRACE`), the parameter does not |

**Reading rule added**: a per-instance physical parameter is only a mechanism if the
failures and passes **do not overlap** on it - here both do, and a lighter *and* a
slipperier fruit placed than one that failed, so "low mass" or "low friction" must not
be written into any document as the tail's cause.

## 5. No-harm

The row is gated on `FRUIT_INSTANCE_DIAG=1` and reads only dataclass fields:
`scripts/accept.sh` with the knob unset is **`fingerprint: matches
configs/motion_reference.json`** with its **459 `[fruit]` lines 459/459 identical** to
`logs/p227/accept_final.log`; `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**
with the new `P256 instance diag` leg.

## 6. Pins

`rl_env.py` (the gate + the row, `TASKS_MD5` unchanged - `tasks.py` `b68ac8d1`),
`scripts/selfcheck.sh`; references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
ckpt `p227_panda156`. Evidence `logs/p256/`.
