# P79 pre-registration — where does P77's count win come from: the **pick** or the
# place, and at what force

**Status: pinned before any cell ran.** Default off, nothing adopted, no default
change, `configs/*` untouched, no commit. md5 in `PREREG.md5`.

## 1. The question, and why it is asked this way

| record | cap | left placed | left `never-held` | left `cnp` | place-leg pries |
|---|---|---|---|---|---|
| P77 `C` | shipped 10 N, build time | 11/21 | **3** | 7 | 4/38 |
| P77 `T` | **global** 60 N, build time, both arms, every presentation | **17/20** (p = 0.043) | **0** | 3 | 1/40 |
| P78 `C` | shipped 10 N | 10/18 | 2 | 8 | 3/36 |
| P78 `S60` | runtime `place-left` 60 N, left `place*` only | 11/16 (p = 0.50) | 5 | 4 | 1/31 |

P78 contained the lever (zero blast radius) and reproduced its **place** mechanism
(pries 3/36 -> 1/31), but not its **count**. The one class that moved in P77's
global arm and did *not* move in P78's place arm is `never-held` (3 -> 0 vs 2 -> 5),
and `never-held` is a **pick** class (`fmax == 0` on a carry leg: the pads never
gripped). The global cap also raised the **close** and the **lift**; the place
cap raised neither. So the open question is whether the count lives in the pick
half, and at what force.

**Hypotheses, both registered:**

* **H-pick** — the count win is a pick-half effect. Falsifiable prediction: a cap
  armed on the left `grasp_lift` leg **only** moves left placed toward P77's
  `17/20` and moves the pick's own class (`never-held`, or the lift-leg pinch
  state that the place leg inherits) while the place transfer runs at the shipped
  cap.
* **H-place** — the count win is (only) the place transfer's, i.e. the lift-only
  arm reads flat and the P78 arm is the whole effect.

**H-pick has two distinct sub-paths, and the class ledger separates them:**

* **H-pick-a (acquisition)** — the lift's sustained pinch rescues a marginal
  close; the class that falls is `never-held` / no-grasp.
* **H-pick-b (lift state)** — the lift ends with one pad out of contact
  (`min_contacts <= 1`, `sep_end - gap_start` large; P75 measured 2 of 6 place
  escapes *start* with `n = 1` and `sep - gap` **+25.3/+28.5 mm** against
  **+8.5..+14.7 mm** on normal legs), so the **place leg inherits a compromised
  pinch**. Here the class that falls is `cnp`, and the lever is still the lift.
  This is *not* H-place: the place leg's own cap is never raised.

The **close itself is out of scope by construction** — it is not a `_carry` leg,
so `grasp-left` cannot touch it. If both classes stay flat, that is the finding:
the pick half's *lift* is not the actuator and the remaining candidate is the
close (a different site, its own registration).

## 2. The knob (default off, `direct` only, zero blast radius by construction)

`FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left` (+ `FRUIT_FINGER_MAXFORCE_SCOPED=<N>`,
default 60) arms a **runtime** cap on the left arm's single `grasp_lift` leg
through P78's machinery unchanged: `rl_env.resolve_finger_cap_scope` (strict
parsing; an explicit `FRUIT_FINGER_MAXFORCE` still wins; every non-`direct`
presentation resolves `(None, None)` before reading a value),
`tasks.finger_cap_scope_for` (the **only** site resolver, now keyed on
`"<side>:<legs>"`), and `_carry`'s wrapper (raise before the leg, restore the cap
the leg **found** in a `finally`).

The two tokens are **disjoint carry-leg classes** — `place-left` -> `{"left:place"}`
-> `place*`, `grasp-left` -> `{"left:grasp"}` -> `grasp_lift` — so a lift-only cap
cannot move the place transfer and a place-only cap cannot move the pick. Pinned
offline by `scripts/244_p78_scope_selftest.py` (extended, 72 checks).

**Not** touched: any build-time drive property, any default, `configs/*`, the
scripted line, the collector, the two-line scheduler, the hybrid canary.

## 3. The batch

Direct presentation, `moe_v13s` `61da390a`, the P66-phase-3 / P71-phase-2 / P73 /
P74 / P75 / P76 / P77 / P78 cell verbatim (patch sheet, balanced A:B:C, ACQ
trigger lead 0.9, park default, shipped supply profile, `FRUIT_CARRY_DIAG=1
FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1`), 15 picks per cell, one claim per
cell, seeds **77 / 101 / 202**, interleaved by seed (`C -> G30 -> G60` within a
seed, seed order ascending).

| arm | env | reg |
|---|---|---|
| **C** | `FRUIT_FINGER_MAXFORCE_SCOPE= FRUIT_FINGER_MAXFORCE_SCOPED=` | the shipped 10 N build cap |
| **G30** | `..._SCOPE=grasp-left ..._SCOPED=30` | the lift at 30 N |
| **G60** | `..._SCOPE=grasp-left ..._SCOPED=60` | the lift at 60 N |

Nine cells. **The global 60 N arm is P77's record and is not re-run**; the
place-only arm is P78's record and is not re-run. Both are quoted as records, not
as same-batch controls.

A **2-episode smoke** may be run before the batch to confirm the rows appear; it
is **not** a cell and no number from it is published.

## 4. The manipulation check (the site proof, three ways) — a cell is *not
evaluable* if any leg of it fails this

1. **The in-leg rows**: one `[drive] left grasp_lift finger cap raise: 10.00 ->
   <N> N (readback <N>)` and one `restore` per left `grasp_lift` leg, and **zero**
   raise/restore rows on any `place*` leg and on the right arm.
2. **The delivered force follows**: the left `grasp_lift` leg **peak** tactile
   force (`fmax`) median per arm tracks the cap (against C's ~10 N), and the
   leg's `force_min`median rises.
3. **The place stays as shipped**: the left `place*` leg `fmax` median stays
   inside C's own band (`<= 11.25 N`, P78's control spread 10.02-11.25), and the
   manifest's `physics.finger_cap_scope.sites` reads `left:grasp` with
   `finger_drive.readback_matches: true` at manifest time (the block is built
   *after* the last restore, so a leaked cap shows there).

`fmax` is the clamp read under a leg-scoped cap; `force_min` is a contact
transient and is reported, not gated (P78's recorded correction).

## 5. Endpoints

Pooled over the three seeds, left arm unless stated; per-seed values are printed
beside every pooled one.

| # | endpoint | why |
|---|---|---|
| **E1** | **left placed** / left attempts (primary) | the count |
| **E2** | **left `never-held`** (`fmax == 0` on a carry leg) and no-grasp notes | the pick's acquisition class |
| **E3** | **left `cnp`** (grasped, not placed) | the carry class |
| **E4** | left `grasp_lift` pinch state: `min_contacts <= 1` legs, `sep_end - gap_start`, `force_min` median | the lift's own integrity (H-pick-b) |
| **E5** | **place-leg escapes** (`clean_slip_max > 100 mm` with a pinch) and **pries** (`sep_max >= 95 mm`) | the guard: the place is as shipped |
| **E6** | **right placed**, right escaped/pried legs | non-inferiority |
| **E7** | cycle: `ticks/attempt`, `s/attempt` | a cost, reported |
| **E8** | the **strawberry** legs (3.4-3.9 cm): `sep_max - dia`, `fmax`, `fmin`, placed | the bruise-critical class |
| **E9** | the failure ledger by note class | what moved |

## 6. The decision rule (fixed now)

**P1 — the count.** All three:
* P1a `left placed(G60) >= left placed(C) + 3` (pooled);
* P1b `left placed(G60) >= left placed(C)` on **>= 2 of 3 seeds**, at least one
  strict;
* P1c `left placed rate(G60) >= 0.75` (i.e. within ~2 attempts of P77's global
  `17/20 = 0.85` at n ~ 20 — the "within 1 of the global arm" clause).

**P2 — the class.** At least one of:
* P2a `never-held(G60) < never-held(C)` pooled (**not evaluable** if `C` reads 0,
  which it has at these n);
* P2b `cnp(G60) < cnp(C)` pooled **and** E4 improves (fewer `min_contacts <= 1`
  lift legs or a smaller `sep_end - gap_start`) — the lift-state path.

**P3 — the site.** E1's three manipulation clauses, i.e. **no place leg is ever
re-clamped** and the place's force stays at C's band. A run whose `place*` peaks
move is not evidence for this token.

**P4 — the right.** `right placed(G60) >= right placed(C) - 1`.

**P5 — the crush guard.** **Zero** legs at G30/G60 with `sep@loss - dia <= -15 mm`
on a physical leg, and **zero** escape legs with `force_min >= 35 N` on a
**3.4-3.9 cm** fruit. A berry pinched at 60 N is the case a real jaw would bruise;
this sim has no bruise model, so the read here is geometry/retention only.

**P6 — the cycle.** `ticks/attempt(G60) <= 1.05 x C` (reported, not gated for a
count verdict).

**Verdicts (exclusive, in this order):**

* **PICK-ACQUISITION** — P1 + P2a + P3 + P4 + P5. The count is the pick's
  acquisition class, at a lift-only dose.
* **PICK-LIFT-STATE** — P1 + P2b + P3 + P4 + P5. The count flows through the
  lift's pinch state into the place leg, with the place never re-clamped.
* **COUNT-UNATTRIBUTED** — P1 but neither P2a nor P2b. The count moved and no
  registered class explains it; published as a count with no mechanism.
* **NO-PICK** — P1 fails. With P2 also failing, **F1 fires**.
* **DOSE-INADMISSIBLE** — P5 fails at 60 N; reported above every count verdict.

**Falsifiers (registered in advance):**

* **F1** — P1 fails **and** P2 fails: the left `grasp_lift`'s force is not the
  actuator, so P77's global count win does not come from the lift. The named
  remaining candidate is the **close** (not a `_carry` leg; a different site and
  its own registration) — and P78's place arm stays the only measured count path.
* **F2** — the count stays where P78's `place-left` arm put it (`+1` attempt,
  p ~ 0.5) while `never-held` and E4 do not move: the win is the place's, and this
  token is the wrong half (not a failure of the tree, a failure of H-pick).
* **F3** — a crush leg (P5) at 60 N: the dose is inadmissible for a real jaw
  regardless of its count, and the finding is published as a dose limit.
* **F4** — a manipulation clause fails in any cell (E1): that cell is not
  evaluable and its count is not quoted.

## 7. What a pass would and would not mean

A **PICK** verdict would say the count is available at a **site-scoped runtime
cap on one leg of one arm**, which is what makes it shippable at zero blast
radius — but the batch is **3 seeds x 15 picks with ~5-8 left attempts per cell**,
so every left number is a **count out of ~20, not a rate**: the loop is
conditioned on rendered frames and is not reproducible (P54/P58/P66), a
same-configuration replay diverges at episode 2, and the P74/P78 lesson is that
one seed is not a direction. `p` values are **descriptors**, and the run level
(2/3 seeds) is the design's ceiling at this n, not a strong result.

Nothing is adopted by this phase: no default moves, `configs/*` is untouched, and
both motion references (`8952c320` / `eb697f23`) stay as shipped.

## 8. The blast radius (the deliverable, re-proved with this token armed)

With the scope **armed** (`grasp-left` at 60 N):

* `scripts/accept.sh` -> **346/346 `[fruit]` lines byte-identical** to
  `logs/p76/accept_noharm_full.log` (md5 `d0079a237202e2f9b0e152655af32a77`) and
  `fingerprint: matches` against `configs/motion_reference.json` (`8952c320`);
* one two-line run -> `scripts/190_twoline_gate.sh` **PASS** against
  `configs/motion_reference_twoline.json` (`eb697f23`);
* **no reference re-recorded**; neither run prints a scope row (the scripted and
  two-line paths never construct `SortingRLEnv`, so the knob cannot be read
  there — structural, then measured).

A **global** `FRUIT_FINGER_MAXFORCE=60` would instead owe both references, a
scripted re-baseline and every store (P77 §8) — which is exactly the difference
this phase exists to quantify.

## 9. Deviations

Any correction to the above is recorded here, dated, with the reason, and the
report prints it beside the affected number (the P76 A1-A4 / P78 §0.1
convention). The pin (`PREREG.md5`) is taken before the first cell and is not
re-taken.

### A1 (2026-10-31, appended after the nine cells; the pin in `PREREG.md5` is the
### pre-run state, `0cdfd227`)

**§4 clause 3's per-cell band is not a valid test of a re-clamp, and it is
reclassified from a gate to a report.** The clause read "the left `place*` leg
`fmax` median stays inside C's own band (`<= 11.25 N`)". It fired in **1 of 6
armed cells** (`G30_202`, median **11.37 N**) and the leg behind it is an
**escaping** leg: `place0 fmax=12.13 N`, `force_min=0.00 N`, `loss_row=114`,
`clean_slip_max=940.1 mm` - i.e. a peak **contact transient while the payload
leaves**, at the shipped 10 N drive cap. `fmax` is the leg's peak instantaneous
tactile force, and such peaks exceed the drive cap on single legs even at 10 N:
this batch's own control reads **35.53 N** on a right `grasp_lift`, and P78's
control read **79.43 / 134.29 / 155.12 N**. So the band compared a transient
against a **pooled median** (P78's 10.02-11.25) and could not have separated a
re-clamp from an escape.

What the clause was *for* - "the place transfer was not re-clamped" - is
measured by two statements that do hold: **zero** `[drive]` raise/restore rows
on any `place*` leg or the right arm across all six armed cells (the scope's own
structural proof: `grep 'finger cap' logs/p79/direct/*.log | grep -v grasp_lift |
grep -v 'scope:'` = **0**), and the **pooled** left `place*` `fmax` **10.05 N**
against the control's **10.07 N**. P3 is evaluated on those two; the per-cell
band is printed beside them. **No verdict moves**: P1 fails independently
(P1a 9 < 11 + 3, P1c 0.529 < 0.75).
