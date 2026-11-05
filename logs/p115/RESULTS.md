# P115 - the instruction becomes an operator tool

Owner's sentence that this phase serves: *"它要可以根据指示自己判断把果蔬分拣放到什么
位置"*.  P114 delivered the mechanism (a descriptor, an instruction resolver and a
capability map) but an instruction could only test **one attribute per rule**, and
an instruction that forgot a case dropped fruit **silently** - the coverage row
printed the count after the first attempt, never before it.  P115 closes both
gaps, default off, with the shipped cell byte-identical.

## What is new (all default off, no shipped default changed)

| piece | behaviour |
| --- | --- |
| `and` terms | a rule conjoins up to **three** attribute terms (`species=apple and size>=66 => 1`); every term must match.  `or` stays written as more rules, because the first match wins. |
| `rule=` in the ledger | every `[sort] attempt` row names the **firing rule** (1-based; `default` counts as a rule), so "which rule decided this" is read from the log, not inferred. |
| the rule table | an armed run prints one `[sort] rule N: <rule text> (arm X)` row per rule before the first attempt. |
| `FRUIT_SORT_STRICT=1` | a fruit no rule matches (`None`) becomes a **startup refusal** naming the dropped fruit; a deliberate `skip` is still allowed (it is a decision, not an oversight). |
| `configs/instructions/` | four canonical files: `shipped_grade.txt` (today's routing), `by_size.txt`, `species_split.txt`, `compound.txt`. |
| the selfcheck leg | `scripts/261_p115_instruction_selftest.py` (54 checks: grammar, precedence, every refusal, the four files, the `tasks.py` shape of the table + the guard). |

## The three cells

All cells are the shipped scripted two-line cell (P85/P87/P100 clock, P71
geometry), one claim per run, `SKIP_SELFCHECK=1` (the standalone selfcheck is run
separately).  The endpoint is the **ledger's assignment accuracy** and the
per-rule histogram, never a placed count.

| cell | knobs | placed | released | in the instructed destination | mis-sorted | rc |
| --- | --- | --- | --- | --- | --- | --- |
| unset (P110 replay) | none | **8/10** | - | - | - | 0 |
| compound | `FRUIT_SORT_INSTRUCTION=configs/instructions/compound.txt`, 20 attempts | 12/20 | 12 | **12/12 = 100 %** | **0** | 0 |
| strict | `"grade=A => 0"` + `FRUIT_SORT_STRICT=1` | 0 | 0 | - | - | 1 (refused at construction) |

## What the compound cell shows

Instruction:

```
species=apple and size>=66 => 1
size<45 => 1
default => 0
```

* **Coverage**: `pool=16 mapped=16 unassigned=0 skip=0` - the `default` rule
  covers everything, so the strict guard has nothing to refuse.
* **Per rule** (`logs/p115/ledger_compound.txt`):

  | rule | attempts | released | in destination |
  | --- | --- | --- | --- |
  | 1 `species=apple and size>=66` | 1 | 1 | **1** |
  | 2 `size<45` | 8 | 6 | 6 |
  | 3 `default` | 11 | 5 | 5 |

* **The witness** (attempt 16): `apple d=7.0cm grade=C arm=right rule=1 dest=1
  ... in_dest=1`.  A **grade-C apple** crossed to the right belt because the
  compound rule fired - the shipped grade routing sends grade C to no arm at
  all.  That is the requirement's own sentence, measured end to end (selection,
  dispatch, place, ledger).
* **Assignment accuracy 100 %**, 0 mis-sorted.  12 releases landed in their
  destination: dest 0 5/5, dest 1 7/7.

**No rate is claimed.**  12/20 is a branch draw: the shipped family's own
seed-6 control read 12/20 (`logs/p92/C6.log`) and 10/20 (`logs/p80/T6.log`), and
the routing changes which arm sees which fruit (grade mix per arm), not a grasp
parameter.

## The strict refusal

`FRUIT_SORT_INSTRUCTION="grade=A => 0"` with `FRUIT_SORT_STRICT=1`:

```
fruit_sorting.scenario.ScenarioError: [sort] REFUSED: FRUIT_SORT_STRICT=1 but
the instruction leaves 10 of 16 fruit unassigned (lychee 34mm grade C,
strawberry 37mm grade B, apple 65mm grade B, pear 61mm grade B, ...); add a rule
(e.g. 'default => 0') or unset FRUIT_SORT_STRICT
```

Thrown from `PickAndPlaceTask.__init__` (line 2713), **before `go_ready` and
before the first attempt**: zero attempts, zero placements.  The same
instruction **without** `STRICT` runs and reports `unassigned=10` in the
coverage row - the P114 behaviour, now a deliberate choice rather than the only
one.

## No-harm

* `logs/p115/accept_unset.log`: **8/10, `fingerprint: matches`,
  `190: PASS`**, and its **421 `[fruit]` lines are 421/421 byte-identical** to
  `logs/p110/accept_noharm.log` (`logs/p115/compare_unset.txt`) - the new
  prints, the `rule=` field and the strict read are all inside
  `if self._instruction is not None`.
* The compound branch's motion budgets: **PASS** (worst descent `|v|max` 0.1210
  against 0.160-0.161, lurch 0.036 against 0.291; carry cones reported, not
  gated).
* `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new `261`
  leg; `106` OK; `107` PASS (21 checks).
* `configs/` references untouched (`30fb99f8` / `30fb99f8` / `8952c320`).

## Pins

`scenario.py` (the `Rule.terms` tuple, `SortInstruction.match`, the `and`
parser), `tasks.py` (`_sort_rule_for`, the rule table, `_sort_require_coverage`,
the `rule=` ledger field), `rl_env.py` (`TASKS_MD5` follow),
`configs/instructions/{shipped_grade,by_size,species_split,compound}.txt`,
`scripts/261_p115_instruction_selftest.py`, `scripts/selfcheck.sh`,
`logs/p114/p114_report.py` (the attempt regex gained an optional `rule=` group;
P114 logs still parse).

## What this does not do

* a **compound condition across destinations** (`... => 2 if ... else 1`) - not
  expressible, and not needed: write two rules, the first match wins;
* a **new physical lane / height / camera** - still a scene build
  (`docs/END_EFFECTOR_DECISION.md`, P114 §4);
* **perception** - `colour` is still refused by the parser; `grade`/`ripeness`
  are drawn labels, so an instruction over them is exact only where the label
  is the ground truth.
