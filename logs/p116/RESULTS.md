# P116 - the owner's two-rule example: the overlap is real, and it is now visible before a run

The owner's sentence:

> **"把 A 级果放在左边盒子里，把苹果放在右边盒子里"**

Two rules, and an **A-grade apple satisfies both**. The runtime resolves that by
**precedence** (first match wins), which is correct but invisible: the ledger
said `dest=0`, never *why*. P116 makes the conflict explicit, adds the operator
that removes it (`!=`), and demonstrates the whole thing on a live cell.

**Nothing shipped; the shipped default is unchanged; `configs/` references
untouched.** Everything new is either an offline tool or a file an operator
writes.

## 1. What the two-rule example does (measured offline)

`scripts/262_sort_plan.py` evaluates an instruction over the cell's own
attribute space (species x 5 diameters x 3 grades = 120 cells, from
`SceneConfig`), reports the **overlap pairs** and the **partition**, and never
touches the simulator.

### (a) the sentence, literally (A first)

```
grade=A => 0
species=apple => 1
default => skip
```

```
OVERLAP: 1 pair(s) - the earlier rule wins:
  rule 1 (grade=A => 0) x rule 2 (species=apple => 1): 5 cell(s); rule 1 wins
    e.g. apple 62mm grade A -> dest 0 (not 1)

PARTITION over 120 attribute cells:
  dest 0                  40 cell(s)
  dest 1                  10 cell(s)
  skip (never selected)   70 cell(s)
```

### (b) the other reading (apples first)

```
species=apple => 1
grade=A => 0
default => skip
```

Same overlap pair, **winner flipped**: `dest 0` 35 / `dest 1` 15 - the 5
A-grade apple cells move to the right.

### (c) the unambiguous form (no overlap at all)

```
grade=A => 0
species=apple and grade!=A => 1
default => skip
```

```
OVERLAP: none - the rules partition the attribute space
dest 0 40 / dest 1 10 / skip 70   (identical to (a), but by construction)
```

`!=` is the new operator (P116): `grade!=A`, `species!=apple`. It is the natural
way to say *"the rest of the apples"* without relying on rule order, and the
linter then proves the partition instead of asking the reader to infer it.

`--strict-overlap` exits 1 when any pair overlaps - usable as a pre-commit
check for an instruction library.

## 2. The live cell (the sentence as written, on an apple-only pool)

The shipped scripted two-line cell, `FRUIT_SUPPLY_SPECIES=apple` (so every
attempt is an apple and the overlap actually occurs), the literal instruction
(a), 10 attempts:

| | placed | released | **in the instructed destination** | mis-sorted |
| --- | --- | --- | --- | --- |
| total | **8/10** | 8 | **8/8 = 100 %** | **0** |
| dest 0 (left, rule 1) | - | 5 | 5/5 | 0 |
| dest 1 (right, rule 2) | - | 3 | 3/3 | 0 |

**Per rule**: rule 1 `grade=A => 0` 5 attempts / 5 released / 5 in destination;
rule 2 `species=apple => 1` 5 / 3 / 3.

**The witness** - five **A-grade apples went LEFT** (attempts 2, 4, 6, 8, 10,
e.g. `apple d=6.3cm grade=A arm=left rule=1 dest=0 ... in_dest=1`), which is
exactly the overlap the plan tool printed, resolved by rule order.  A non-A
apple goes right (`rule=2 dest=1`).  The cell therefore demonstrates both the
precedence and the sort: **8 of 8 released payloads landed in the box the
instruction named.**

No rate claim: 8/10 is one branch of the apple-only cell (the shipped mixed pool
reads 28-29/40 at the same seeds); the endpoint is the ledger.

## 3. What this means for "give the machine an instruction"

The instruction layer is a **deterministic rule compiler**, not a language
model:

```
natural language ──(① front-end, not built)──▶ rule DSL ──(② today)──▶
    capability map ──▶ selector / dispatcher ──▶ ledger (did it land there?)
```

* **② is done and measured** (P114/P115/P116): the DSL, the precedence, the
  overlap lint, the startup refusal for unreachable destinations or uncovered
  fruit, and the per-destination ledger.
* **① is the only missing piece for free-form text**, and it is deliberately a
  *compiler*: an LLM (or a template) emits rules; the **linter validates them**
  (`--strict-overlap`, unreachable destinations, unknown attributes, unknown
  species/grades) before anything moves.  That keeps the model out of the
  control loop - the executor stays deterministic and auditable, which is why
  the same instruction replays bit-for-bit.
* **the policy line still refuses the instruction** (`rl_env.py:1708`): the
  direct model conditions on `bin_index` and the primitive owns the place
  (`P116`'s predecessor note).  Threading the destination through the policy
  handover is P117.

## 4. Files and pins

`scenario.py` **`662369aa`** (the `!=` operator + public `rule_matches`),
`configs/instructions/owner_a_left_apples_right.txt` **`1ad67958`** /
`owner_apples_first.txt` **`5ffbfdb2`** / `owner_precise.txt` **`0d4df6a2`**,
`scripts/262_sort_plan.py` **`d510cb1e`** (the plan/lint tool),
`scripts/261_p115_instruction_selftest.py` **`10bd9faa`** (63 checks, now with
`!=` and the owner's overlap), `scripts/selfcheck.sh` **`92e65259`** (the
`P116 sort plan` leg).  Selfcheck **PASS (0 failures, 1 skipped)**, `106` OK,
`107` PASS (21 checks).  References **`30fb99f8` / `30fb99f8` / `8952c320`**
untouched.  Evidence `logs/p116/`.
