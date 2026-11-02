# P93 PREREG — the re-entry: diagnose the two red flags, add the seeds, and (only then) ship the band

**Pinned before any run.** md5 in `logs/p93/PREREG.md5`. Predecessor:
`logs/p92/{PREREG.md,RESULTS.md,CENSUS.md}` (committed).

## 0. Where P92 left it, in one paragraph

P92's registered change (`FRUIT_SUPPLY_X_MAX=0.33`, the supply band's top,
env only) converted **8 of the cell's 12 failures at both seeds**: placed
`28/40 -> 36/40`, `cnp` `9 -> 3`, never-held `3 -> 1`, the servo chase
`11 -> 5`, the interval better at both seeds. The pre-registered rule still
returned **NOT ADOPTED**, on **G3** only: seed 6's **leg 1** descent read
`|v|max` **0.222** against its **0.161** budget (+38 %), and the same seed's
branch carried an unregistered red flag - one right `grasp_lift` leg with
`fmax = 419.25 N`, `in-hand |v|max = 1.545 m/s`, and `carry-assist` rows whose
stored pad centre sat **1313 mm** from the measured pads. P92's close-out named
this phase's four items: diagnose the two, add a third seed, put the band in the
provenance, and only then either ship the package or state the failing clause.

## 1. The two diagnostics (no gate; they decide *whether the seeds mean anything*)

Both red flags are on the **same attempt** - seed 6, attempt 0, the right arm's
first kiwi. Everything below is read off that attempt.

### 1a. `T6`'s leg 1: a chase, or a boundary strain?

The record's own discriminator (`logs/160`/`logs/158`, AGENTS section 2) is
**`end=` plus the fruit's displacement**, not `|v|max`:

* a **chase** closes a residual against a *moving* target, so the leg's target
  moves with the fruit and the fruit stays inside the pads' band;
* a **boundary strain** has a *fixed* target the arm cannot reach: the leg ends
  at or beyond the documented 40-90 mm shortfall, the profile carries on, and -
  the decisive clause - **the fruit is untouched**.

Read for this leg, before any run (`logs/p92/T6.log`):

| read | T6 (treatment) | C6 (control, same seed) |
| --- | --- | --- |
| descent target | fixed, `intercept=-0.0831` (station -0.1000) | fixed, `intercept=-0.0828` (station -0.1000) |
| fruit at the descent's start | `dy=+0.0830` | `dy=+0.0830` |
| commanded samples | 88 | 88 |
| `|v|max` | **0.222** | 0.108 |
| `end=` | **58.9 mm** | 10.6 mm |
| `a_win5` | 4.44 | 1.31 |
| the next row (the catch-up) | residual **1169.1 mm** | **480.6 mm** |
| the close it forces | `sustained contact after 5 ticks, 206.69 N, span 100.1 mm` | `5 ticks, 58.15 N, 99.1 mm` |

**Pre-committed reading.** The command is *open-loop and identical* (fixed target,
same 88-sample profile, same fruit offset), so **a chase is excluded by
construction** - there is no moving target in this leg. What separates the two
remaining readings is the fruit:

* **boundary strain** if the pads never contact the fruit during the descent
  (`force < 0.5 N`, `contacts == 0` on every descent row) and the fruit's
  displacement over the leg is <= 20 mm; the leg's `end=` then sits at the
  documented shortfall and the fruit's later drift belongs to a *separate*
  contact in the catch-up/close;
* **a push** if the descent's own rows show contact and the fruit's displacement
  over the leg is >= 100 mm.

**Trace**: `FRUIT_DYNAMIC_TRACE=1` writes one row per tick for the `descent`,
`catchup`, `close` and `carry` phases (`logs/dynamic_trace_NN.json`), including
`fruit`, `jaw`, `tip`, `offset`, `force` and `contacts`. Two cells
(`D6C`/`D6T`, seed 6, `ATTEMPTS=4`, the other's band) provide it. The trace is a
mechanism instrument: its cells are **not** compared to the untraced ones for
rate, and if the traced leg 1 differs from the untraced one the phase says so and
reads the mechanism from the trace, the magnitudes from the record.

### 1b. The 419 N / 1313 mm leg: a payload event, or a bookkeeping artifact?

The code path, read before the run (`src/fruit_sorting/tasks.py`):

* `_gripper_offset[side]` is set at the **grasp routine's start** to
  `rot.T @ (spawner.position(sample) - tcp_position())` (`tasks.py:11047`) -
  i.e. **the fruit's position minus the TCP's**, in the tool frame. It is a
  *tool* offset only while the pads are on the fruit.
* `_carry`'s **coherent** branch commissions `arm.tcp_target_for_jaw(centre)` for
  this hand (`hand_is_jaw`, `:5331`) and the place loop does the same
  (`:6079`); the **incoherent** branch commissions
  `arm.tcp_target_for_jaw(centre - rot @ offset_tool)` **without** consulting
  `hand_is_jaw` (`:5361-5366`).

So the offset is only ever applied on the incoherent branch, and it is applied
to a hand whose real tool offset is the jaw itself. The measured offset on every
other leg in this batch is **20-62 mm** (`[diag] carry-assist ... |offset|=`).

**Pre-committed reading.**

* **artifact** if (i) the logged `|offset|` equals the *fruit-minus-TCP* distance
  at that attempt's close, (ii) the commanded `jaw_target` sits > 0.5 m from the
  measured pads (i.e. the offset is being applied as a translation, not a tool
  frame), and (iii) the pads are on the fruit when the leg starts
  (`contacts@onset >= 1`, `sep@onset` inside the fruit's span);
* **payload event** if the pads are on the fruit and the fruit leaves under a
  pinch at the shipped ~10 N, i.e. the closed class of `logs/p42/SIM_LIMIT.md`.

The reading does **not** depend on which of those the arm then does: an artifact
that commands the TCP 1.3 m away *produces* a real violent leg, so the leg is
registered as **an artifact with a physical consequence** - a state-integrity
defect, not a payload event, and (see 1c) not a cost of the band.

### 1c. When is a red flag a *systematic cost of the narrower band*?

Fixed now, because this is the clause the whole phase hangs on:

> A red flag is a **systematic cost of the band** iff it is present in the
> treatment and **absent in the same-seed control**, *or* present in both but
> **monotone in the band across two seeds**. Otherwise it is a **branch
> artifact**: the seed's own branch carries it, and the band's amplitude on it
> is not evidence about the band.

The seed-6 first attempt is already known to be a standing artifact of the
scenario, independent of this phase: the **480.6 mm** first catch-up residual is
byte-identical in **every** seed-6 record on the tree (`logs/p80/T6`,
`logs/p84/D6`, `logs/p87/T6`, `logs/p88/C6`, `logs/p89/C6`, `logs/p91/C6`), and
seed 5 has no such event at all (`5.9 mm` at `logs/p91/C5`, `logs/p87/T5`). So
the seed-6 first attempt is a **scenario branch fact**; the question §1 answers
is only whether the *treatment's larger amplitude* is the band's.

**If either diagnostic returns "a systematic cost of the band", the phase stops
there, the band does not ship, and the clause is named.**

## 2. The seeds

Two fresh seeds, **101** and then **202** if the machine time is available: each
a control cell (unset) and a treatment cell (`FRUIT_SUPPLY_X_MAX=0.33`), 20
attempts, the shipped two-line default, **P92's instrumentation verbatim**
(`HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1`), wall via `logs/p80/stamp.py`, one claim per run.

**A fresh seed's control has no record to replay, and the phase states that
rather than inventing one** (P84's rule: a seed is a scenario). The
admissibility read for a fresh control is therefore its **own** first-attempt
signature and its own guard set, plus the two-seed record's replay at seeds 5/6
(which P92 proved and this phase does not re-run).

## 3. Endpoints

**Primary (a class count): the never-held class**, per seed and pooled over the
four seeds. P92's two-seed reading is `3 -> 1` (control 3, treatment 1).

**Secondary (read, never the decision's only basis):** the placed count per
seed; the `cnp` class count; the chase set (`force servo ... closed > 0`); the
delivered-x distribution (the manipulation check: the build row's
`lateral x=` and the delivered min/p50/max); the interval on both denominators
plus the wall column; the landing (`on_belt` on every payload-present release).

## 4. Guards (all must pass, per cell)

* **G1 the closed class must not rise**: `cnp` at a treatment cell <= its
  control's, per seed.
* **G2 the landing**: every payload-present release lands `on_belt=True`.
* **G3 the motion budgets**: `scripts/105_motion_regression.py
  --min-success-rate 0.0` on every cell; **every descent inside its per-leg
  budget**, with one pre-registered exception route: a leg that is not inside
  fails the cell **unless §1 has already proven** that the over-budget motion at
  that seed is produced by the seed's own first-attempt artifact (which the
  control carries) and not by the band. **A leg at a fresh seed with no such
  antecedent fails the gate, always.** The budget is **never** re-tuned
  (AGENTS section 2).
* **G4 no new failure reason**: the treatment's note-key set stays inside the
  control's (the recorded buckets are `fruit did not follow the gripper` and
  `grasped, not placed (no note)`).
* **G5 the control replay**: at seeds 5/6 as P92 proved it (recorded, not
  re-run); at 101/202 the control is its own cell and is read as one, with the
  fresh-seed statement above.
* **G6 no starvation**: 20 attempts per cell, zero lost slots; the
  `no eligible fruit` poll count reported, not gated.
* **G7 the tree is inert with the knob unset**: `scripts/selfcheck.sh` PASS,
  `scripts/accept.sh` unchanged (`fingerprint: matches`, its `[fruit]` stream
  byte-identical to the P87/P89 record), `python3 scripts/211_bed_audit.py` OK.
* **G8 the provenance prerequisite** (section 6) is in the tree **before** the
  decision is written.

## 5. Decision rule (fixed now)

**Adopt the band (`FRUIT_SUPPLY_X_MAX` default `0.36 -> 0.33`) only if all of:**

1. **(class)** the pooled never-held class over the four seeds falls, and no
   seed's treatment exceeds its control's;
2. **(count)** no seed's placed count falls below its control's, and the pooled
   placed count does not fall;
3. **G1-G8 pass**, G3 through the clause in section 4;
4. **§1 returns "not a systematic cost"** for both red flags.

Otherwise **not adopted**, and the phase names the failing clause and publishes
the numbers as a negative.

**What this rule cannot do, said up front.** Four seeds of 20 attempts is 80
attempts per arm and the control's own two-seed record swings `16 -> 12` placed
between seeds, so the *count* is a branch draw and only the *class* is the
primary. A class of 3 events in the control cannot certify a rate at n = 80
either; the phase's claim is the mechanism, exactly as P92 registered it.

## 6. The provenance prerequisite, and what adoption would re-baseline

**Built in this phase, shipped either way** (metadata only, no stream effect):

* `assets.supply_provenance(plan)` - a pure builder returning the resolved
  **band** (`x_min`, `x_max`), the **mix** (`grades`, `classes`) and the resolved
  schedule name (`bed`/`patch`/`wave`/`scatter`). Called by **both** manifest
  writers (the direct env's `supply` block and the collector's shard), so the
  two cannot drift (the P41 `physics` / P72 `scene` rule).
* Why: the **collector's** shard manifest already carries
  `supply.x_min`/`x_max` and the mixes (`datasets/v12d_s02/manifest.json` has
  `x_max: 0.36`), so a *collection* store is already distinguishable. The
  **direct env's** rollout manifest carries only the P58 profile fields - no
  band, no mix - so a **direct/rollout** store under 0.20-0.33 and one under
  0.20-0.36 are indistinguishable today. That is the gap this closes.
* Pinned in the existing provenance leg (`scripts/239_p72_clr_edge_selftest.py`).

**If the band ships**, it moves the scenario for every scripted path, so:

* `configs/motion_reference.json` and `configs/motion_reference_twoline.json`
  are re-recorded from **same-batch** runs (both are the shipped acceptance's
  scenario; `configs/motion_reference_single.json` too **iff** the single arm's
  own acceptance stream moves - it is measured, not assumed);
* the old files are archived under `logs/p93/`;
* `scripts/accept.sh` / the two-line gate are re-based if their floors move;
* a **re-baseline note** is written: every rate, acceptance, reference and store
  recorded before P93 is a **0.20-0.36** number;
* the **direct/policy interface** is measured: it builds its own supply profile
  from the same `SupplyPlan.from_env` and pins `two_line=False`, so it inherits
  the band - one 15-episode direct cell, **report only**, says whether it moves.

## 7. Cells (one claim per run)

| cell | env | role |
| --- | --- | --- |
| `D6C` | `ATTEMPTS=4 SEED=6` + `FRUIT_DYNAMIC_TRACE=1 FRUIT_OPENARM_TRACE=6` | §1a/§1b mechanism, control |
| `D6T` | `+ FRUIT_SUPPLY_X_MAX=0.33` | §1a/§1b mechanism, treatment |
| `C101` | `ATTEMPTS=20 SEED=101` | the control at a fresh seed |
| `T101` | `+ FRUIT_SUPPLY_X_MAX=0.33` | the treatment |
| `C202` | `ATTEMPTS=20 SEED=202` | the control at the second fresh seed |
| `T202` | `+ FRUIT_SUPPLY_X_MAX=0.33` | the treatment |

The four seed cells carry P92's instrumentation verbatim so the class census
(`logs/p92/census.py`) reads them unchanged.

## 8. Falsifiers (any one kills the lever as stated)

* **F1** the diagnostic returns "a systematic cost of the band" for either red
  flag;
* **F2** at a fresh seed the never-held class rises or the placed count falls by
  more than the control's own branch spread;
* **F3** a descent leaves its budget at a fresh seed with no first-attempt
  antecedent (G3's hard clause);
* **F4** a `cnp` rise or a new failure reason;
* **F5** a landing regression;
* **F6** a fresh control cell cannot run its 20 attempts (a lost slot).
